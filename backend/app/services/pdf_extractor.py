import fitz


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return value.strip()


def extract_pdf_text(pdf_bytes: bytes) -> dict[str, object]:
    pages: list[dict[str, object]] = []

    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        for idx, page in enumerate(document, start=1):
            text = _normalize_text(page.get_text("text"))
            pages.append({"page": idx, "text": text})

    full_text = "\n\n".join(page["text"] for page in pages if isinstance(page.get("text"), str)).strip()

    return {
        "page_count": len(pages),
        "pages": pages,
        "full_text": full_text,
    }
