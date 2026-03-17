import os

from openai import OpenAI


CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    return OpenAI(api_key=api_key)


def generate_answer(question: str, contexts: list[str], model: str = CHAT_MODEL) -> str:
    if not contexts:
        return "관련 문서를 찾지 못했습니다. 질문을 더 구체적으로 입력해 주세요."

    context_block = "\n\n".join(
        f"[chunk {idx + 1}]\n{ctx}" for idx, ctx in enumerate(contexts) if ctx.strip()
    ).strip()
    if not context_block:
        return "관련 문서를 찾지 못했습니다. 질문을 더 구체적으로 입력해 주세요."

    system_prompt = (
        "너는 문서 기반 질의응답 도우미다. 반드시 제공된 문맥만 근거로 답변하고, "
        "문맥에 없는 내용은 모른다고 답해라. 답변은 간결한 한국어로 작성해라."
    )
    user_prompt = f"질문:\n{question}\n\n문맥:\n{context_block}"

    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content
    return content.strip() if isinstance(content, str) and content.strip() else "답변을 생성하지 못했습니다."
