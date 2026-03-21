import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.schemas.ask import AskRequest, AskResponse
from app.schemas.ask import SourceItem
from app.schemas.upload import UploadResponse
from app.services.embeddings import embed_query, embed_texts
from app.services.generation import generate_answer
from app.services.pdf_extractor import extract_pdf_text
from app.services.text_chunker import chunk_document_with_page_metadata
from app.services.vector_store import query_top_k, upsert_chunks

BASE_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
MAX_UPLOAD_SIZE_MB = 50
MAX_UPLOAD_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024
CHUNK_SIZE = 800
CHUNK_OVERLAP = 160
# 질의 시 검색할 기본 chunk 개수.
# k를 너무 작게 잡으면 근거가 부족하고, 너무 크게 잡으면 노이즈가 늘어나므로
# 현재는 균형값으로 5를 사용한다.
ASK_TOP_K = 5

# 서버 시작 시점에 backend/.env를 로드해 OpenAI 키/모델 설정을 읽는다.
load_dotenv(BASE_DIR / ".env")

app = FastAPI(title="DocPilot-RAG API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    # 1) 업로드 입력 검증
    # - 파일명 존재 여부
    # - PDF 확장자 여부
    # - 빈 파일 여부
    # - 최대 용량 제한
    # 먼저 검증해서 불필요한 추출/임베딩 호출을 막는다.
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="파일 이름이 비어 있습니다.",
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDF 파일만 업로드할 수 있습니다.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="빈 파일은 업로드할 수 없습니다.",
        )

    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"파일 크기는 {MAX_UPLOAD_SIZE_MB}MB 이하여야 합니다.",
        )

    file_id = uuid4().hex
    stored_name = f"{file_id}.pdf"
    pdf_path = UPLOAD_DIR / stored_name
    json_path = UPLOAD_DIR / f"{file_id}.json"

    try:
        # 2) 원본 PDF 저장
        # 업로드 이력 추적과 재처리(디버깅/검증)를 위해 파일을 먼저 로컬에 저장한다.
        pdf_path.write_bytes(content)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="파일 저장 중 오류가 발생했습니다.",
        ) from exc

    try:
        # 3) RAG 인덱싱 파이프라인
        # 추출 -> 청킹 -> 임베딩 -> 벡터DB 저장 순서로 처리한다.
        # 이 단계가 끝나면 /ask에서 검색 가능한 상태가 된다.
        extracted = extract_pdf_text(content)
        chunks = chunk_document_with_page_metadata(
            pages=list(extracted.get("pages", [])),
            file_id=file_id,
            filename=file.filename,
            chunk_size=CHUNK_SIZE,
            overlap=CHUNK_OVERLAP,
        )
        chunk_contents = [str(chunk.get("content", "")) for chunk in chunks]
        chunk_embeddings = embed_texts(chunk_contents)
        upsert_chunks(file_id=file_id, chunks=chunks, embeddings=chunk_embeddings)

        # 4) 추출 결과 JSON 저장
        # 페이지 텍스트/청크를 파일로 남겨 retrieval 품질 점검 시 근거로 사용한다.
        payload = {
            "file_id": file_id,
            "original_filename": file.filename,
            "stored_pdf_path": str(pdf_path.relative_to(BASE_DIR)),
            "page_count": extracted["page_count"],
            "pages": extracted["pages"],
            "full_text": extracted["full_text"],
            "chunks": chunks,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PDF 텍스트 추출 중 오류가 발생했습니다.",
        ) from exc

    return UploadResponse(
        message="문서 업로드 및 텍스트 추출이 완료되었습니다.",
        file_id=file_id,
        filename=file.filename,
        page_count=int(extracted["page_count"]),
        text_json_path=str(json_path.relative_to(BASE_DIR)),
    )


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    try:
        # 질의 처리 흐름
        # 질문 -> 임베딩 -> 벡터 검색 -> LLM 답변 생성
        query_embedding = embed_query(payload.question)
        result = query_top_k(query_embedding, k=ASK_TOP_K)

        documents = result.get("documents", [[]])
        metadatas = result.get("metadatas", [[]])
        distances = result.get("distances", [[]])

        docs = documents[0] if documents else []
        metas = metadatas[0] if metadatas else []
        dists = distances[0] if distances else []

        sources: list[SourceItem] = []
        contexts: list[str] = []
        for idx, doc in enumerate(docs):
            metadata = metas[idx] if idx < len(metas) and isinstance(metas[idx], dict) else {}
            distance = dists[idx] if idx < len(dists) else None
            score = None
            if isinstance(distance, (float, int)):
                # Chroma의 distance는 "낮을수록 유사"이므로
                # UI에서 보기 쉬운 0~1 점수 형태로 변환해 내려준다.
                score = max(0.0, min(1.0, 1.0 - float(distance)))
            page_raw = metadata.get("page")
            page = page_raw if isinstance(page_raw, int) else None
            snippet = str(doc)

            sources.append(
                SourceItem(
                    title=str(metadata.get("filename", "")) or None,
                    page=page,
                    snippet=snippet,
                    score=score,
                )
            )
            # contexts는 실제로 GPT에게 전달되는 근거 문맥 목록이다.
            contexts.append(snippet)

        answer = generate_answer(payload.question, contexts)
        return AskResponse(answer=answer, sources=sources)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="질문 처리 중 오류가 발생했습니다.",
        ) from exc
