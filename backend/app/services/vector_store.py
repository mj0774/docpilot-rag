from pathlib import Path
from typing import Any

import chromadb

BASE_DIR = Path(__file__).resolve().parents[2]
CHROMA_DIR = BASE_DIR / "data" / "chroma"
COLLECTION_NAME = "docpilot_chunks"


def _get_collection():
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(name=COLLECTION_NAME)


def upsert_chunks(file_id: str, chunks: list[dict[str, Any]], embeddings: list[list[float]]) -> None:
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
    if not query_embedding:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    collection = _get_collection()
    return collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
