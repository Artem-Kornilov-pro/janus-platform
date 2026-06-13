"""Split long documents into overlapping chunks for LLM processing."""

from __future__ import annotations

DEFAULT_MAX_CHARS = 6000
DEFAULT_OVERLAP_CHARS = 400


def chunk_text(text: str, max_chars: int = DEFAULT_MAX_CHARS, overlap_chars: int = DEFAULT_OVERLAP_CHARS) -> list[str]:
    """Split `text` into chunks of at most `max_chars`, grouping by paragraphs.

    Paragraphs (separated by blank lines) are kept whole where possible.
    A chunk that exceeds `max_chars` on its own is hard-split. Consecutive
    chunks overlap by approximately `overlap_chars` characters of trailing
    context from the previous chunk, to preserve cross-paragraph context.
    """
    text = text.strip()
    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    paragraphs = [p for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph

        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)

        if len(paragraph) > max_chars:
            for i in range(0, len(paragraph), max_chars):
                chunks.append(paragraph[i:i + max_chars])
            current = ""
        else:
            current = paragraph

    if current:
        chunks.append(current)

    if overlap_chars <= 0 or len(chunks) <= 1:
        return chunks

    overlapped = [chunks[0]]
    for i in range(1, len(chunks)):
        previous_tail = chunks[i - 1][-overlap_chars:]
        overlapped.append(previous_tail + "\n\n" + chunks[i])

    return overlapped
