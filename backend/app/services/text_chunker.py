def chunk_document_with_page_metadata(
    pages: list[dict[str, object]],
    file_id: str,
    filename: str,
    chunk_size: int = 800,
    overlap: int = 160,
) -> list[dict[str, object]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")
    if overlap < 0:
        raise ValueError("overlap must be zero or positive.")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size.")

    normalized_pages: list[dict[str, int | str]] = []
    for page in pages:
        page_no = page.get("page")
        page_text = page.get("text")
        if isinstance(page_no, int) and isinstance(page_text, str):
            text = page_text.strip()
            if text:
                normalized_pages.append({"page": page_no, "text": text})

    if not normalized_pages:
        return []

    full_text_parts: list[str] = []
    page_ranges: list[dict[str, int]] = []
    cursor = 0

    for idx, page in enumerate(normalized_pages):
        if idx > 0:
            full_text_parts.append("\n\n")
            cursor += 2

        text = str(page["text"])
        start = cursor
        full_text_parts.append(text)
        cursor += len(text)
        end = cursor

        page_ranges.append(
            {
                "page": int(page["page"]),
                "start": start,
                "end": end,
            }
        )

    full_text = "".join(full_text_parts)
    step = chunk_size - overlap
    chunks: list[dict[str, object]] = []
    chunk_index = 0
    chunk_start = 0

    while chunk_start < len(full_text):
        chunk_end = min(chunk_start + chunk_size, len(full_text))
        piece = full_text[chunk_start:chunk_end]
        if piece.strip():
            touched_pages = [
                pr["page"]
                for pr in page_ranges
                if pr["end"] > chunk_start and pr["start"] < chunk_end
            ]
            page_start = touched_pages[0] if touched_pages else None
            page_end = touched_pages[-1] if touched_pages else None

            chunks.append(
                {
                    "text": piece,
                    "metadata": {
                        "file_id": file_id,
                        "filename": filename,
                        "page": page_start,
                        "page_start": page_start,
                        "page_end": page_end,
                        "chunk_index": chunk_index,
                    },
                }
            )
            chunk_index += 1

        if chunk_end == len(full_text):
            break
        chunk_start += step

    return chunks
