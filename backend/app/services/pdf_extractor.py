import re

import fitz


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""

    text = value.strip()
    if not text:
        return ""

    # Keep structure mostly intact: only reduce obvious whitespace noise.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf_text(pdf_bytes: bytes) -> dict[str, object]:
    pages: list[dict[str, object]] = []

    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        for idx, page in enumerate(document, start=1):
            text = _normalize_text(page.get_text("text"))
            if not text:
                continue
            pages.append({"page": idx, "text": text})

    full_text = "\n\n".join(page["text"] for page in pages if isinstance(page.get("text"), str)).strip()

    return {
        "page_count": len(pages),
        "pages": pages,
        "full_text": full_text,
    }
