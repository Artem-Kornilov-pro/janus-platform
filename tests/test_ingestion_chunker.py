from core.ingestion_pipeline.chunker import chunk_text


def test_short_text_returns_single_chunk():
    text = "Short paragraph."
    assert chunk_text(text, max_chars=100) == [text]


def test_empty_text_returns_no_chunks():
    assert chunk_text("   ") == []


def test_long_text_splits_by_paragraphs_with_overlap():
    paragraphs = [f"Paragraph {i} " + "x" * 50 for i in range(10)]
    text = "\n\n".join(paragraphs)

    chunks = chunk_text(text, max_chars=150, overlap_chars=20)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 150 + 20 + 2  # allow for overlap + separator

    # second chunk should start with the tail of the first (overlap)
    assert chunks[1].startswith(chunks[0][-20:])


def test_paragraph_longer_than_max_chars_is_hard_split():
    text = "x" * 500
    chunks = chunk_text(text, max_chars=200, overlap_chars=0)

    assert len(chunks) == 3
    assert "".join(chunks) == text
