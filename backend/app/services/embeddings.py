import os

from openai import OpenAI


EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return OpenAI(api_key=api_key)


def embed_texts(texts: list[str], model: str = EMBEDDING_MODEL) -> list[list[float]]:
    if not texts:
        return []
    client = _get_client()
    response = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]


def embed_query(text: str, model: str = EMBEDDING_MODEL) -> list[float]:
    vectors = embed_texts([text], model=model)
    if not vectors:
        return []
    return vectors[0]
