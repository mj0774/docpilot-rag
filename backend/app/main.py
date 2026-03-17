from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from app.schemas.ask import AskRequest, AskResponse

BASE_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20MB

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


@app.post("/upload")
async def upload(file: UploadFile = File(...)) -> dict[str, str]:
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
            detail="파일 크기는 20MB 이하여야 합니다.",
        )

    file_id = uuid4().hex
    stored_name = f"{file_id}.pdf"
    target_path = UPLOAD_DIR / stored_name

    try:
        target_path.write_bytes(content)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="파일 저장 중 오류가 발생했습니다.",
        ) from exc

    return {
        "message": "문서 업로드가 완료되었습니다.",
        "file_id": file_id,
        "filename": file.filename,
    }

@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    answer = f"현재 MVP 단계 응답입니다. 질문: {payload.question}"
    return AskResponse(answer=answer, sources=[])
