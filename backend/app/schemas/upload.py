from pydantic import BaseModel


class UploadResponse(BaseModel):
    message: str
    file_id: str
    filename: str
    page_count: int
    text_json_path: str
