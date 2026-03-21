from pathlib import Path
from typing import Any
import math

import chromadb

BASE_DIR = Path(__file__).resolve().parents[2]
CHROMA_DIR = BASE_DIR / "data" / "chroma"
COLLECTION_NAME = "docpilot_chunks"
MMR_LAMBDA = 0.7
MMR_CANDIDATE_MULTIPLIER = 4


def _get_collection():
    # Chroma PersistentClient:
    # 벡터 인덱스 파일을 backend/data/chroma 아래에 영구 저장한다.
    # 서버 재시작 후에도 인덱스를 재사용할 수 있다.
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(name=COLLECTION_NAME)


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if len(vec_a) == 0 or len(vec_b) == 0 or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _mmr_select_indices(
    query_embedding: list[float],
    candidate_embeddings: list[list[float]],
    k: int,
    lambda_mult: float = MMR_LAMBDA,
) -> list[int]:
    # Greedy MMR 선택:
    # 1) 질문과의 관련도는 높게 유지하고
    # 2) 이미 고른 청크와 너무 비슷한 후보는 감점한다.
    # 결과적으로 "관련도 + 다양성"을 동시에 확보한다.
    if len(candidate_embeddings) == 0:
        return []

    target = min(k, len(candidate_embeddings))
    selected: list[int] = []
    remaining = list(range(len(candidate_embeddings)))
    query_sims = [_cosine_similarity(query_embedding, emb) for emb in candidate_embeddings]

    # MMR 점수 계산을 반복하면서 최종 k개를 순차적으로 뽑는다.
    while remaining and len(selected) < target:
        best_idx = remaining[0]
        best_score = float("-inf")

        for idx in remaining:
            relevance = query_sims[idx]
            diversity_penalty = 0.0
            if selected:
                diversity_penalty = max(
                    _cosine_similarity(candidate_embeddings[idx], candidate_embeddings[s])
                    for s in selected
                )
            mmr_score = (lambda_mult * relevance) - ((1 - lambda_mult) * diversity_penalty)
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        selected.append(best_idx)
        remaining.remove(best_idx)

    return selected


def query_similarity_k(query_embedding: list[float], k: int = 3) -> dict[str, Any]:
    """기존 방식: 순수 유사도 기반 top-k 검색."""
    if not query_embedding:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    collection = _get_collection()
    return collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )


def upsert_chunks(file_id: str, chunks: list[dict[str, Any]], embeddings: list[list[float]]) -> None:
    # id를 file_id:chunk_index 규칙으로 고정해 upsert한다.
    # 같은 파일/청크가 다시 들어오면 중복 추가가 아니라 동일 id 레코드가 갱신된다.
    if not chunks:
        return
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings length mismatch")

    collection = _get_collection()
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []
    used_embeddings: list[list[float]] = []

    for chunk, emb in zip(chunks, embeddings):
        metadata = chunk.get("metadata", {})
        chunk_index = metadata.get("chunk_index")
        content = chunk.get("content", "")
        if not isinstance(chunk_index, int):
            continue
        if not isinstance(content, str) or not content.strip():
            continue

        ids.append(f"{file_id}:{chunk_index}")
        documents.append(content)
        metadatas.append(
            {
                "file_id": str(metadata.get("file_id", file_id)),
                "filename": str(metadata.get("filename", "")),
                "page": int(metadata["page"]) if isinstance(metadata.get("page"), int) else None,
                "chunk_index": int(chunk_index),
            }
        )
        used_embeddings.append(emb)

    if not ids:
        return

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=used_embeddings,
    )


def query_top_k(query_embedding: list[float], k: int = 3) -> dict[str, Any]:
    """현재 방식: MMR 기반 top-k 검색(관련도 + 다양성)."""
    if not query_embedding:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    collection = _get_collection()
    # 1단계) 먼저 similarity로 후보를 넉넉히 가져온다.
    # 예: 최종 k=5면 후보는 20개(k*4) 조회
    candidate_k = max(k * MMR_CANDIDATE_MULTIPLIER, k)
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=candidate_k,
        include=["documents", "metadatas", "distances", "embeddings"],
    )

    ids = result.get("ids", [[]])
    documents = result.get("documents", [[]])
    metadatas = result.get("metadatas", [[]])
    distances = result.get("distances", [[]])
    embeddings = result.get("embeddings", [[]])

    cand_ids = ids[0] if ids else []
    cand_docs = documents[0] if documents else []
    cand_metas = metadatas[0] if metadatas else []
    cand_dists = distances[0] if distances else []
    cand_embs = embeddings[0] if embeddings else []

    if len(cand_embs) == 0:
        # 예외 상황: 후보 임베딩이 없으면 MMR 재정렬이 불가능하므로
        # 기존 similarity 순서를 그대로 반환한다.
        return {
            "ids": [cand_ids[:k]],
            "documents": [cand_docs[:k]],
            "metadatas": [cand_metas[:k]],
            "distances": [cand_dists[:k]],
        }

    # 2단계) 후보를 MMR로 재정렬해 최종 k개를 선택한다.
    selected_indices = _mmr_select_indices(query_embedding, cand_embs, k)
    return {
        "ids": [[cand_ids[i] for i in selected_indices if i < len(cand_ids)]],
        "documents": [[cand_docs[i] for i in selected_indices if i < len(cand_docs)]],
        "metadatas": [[cand_metas[i] for i in selected_indices if i < len(cand_metas)]],
        "distances": [[cand_dists[i] for i in selected_indices if i < len(cand_dists)]],
    }
