from pydantic import BaseModel, Field, field_validator


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question text")

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("질문은 공백일 수 없습니다.")
        return trimmed


class SourceItem(BaseModel):
    title: str | None = None
    page: int | None = None
    snippet: str
    file_id: str | None = None
    chunk_index: int | None = None
    score: float | None = None


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
