from pathlib import Path

import pytest

from core.ingestion_pipeline.extractors import (
    UnsupportedFileTypeError,
    discover_documents,
    extract_text,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "ingestion"


def test_extract_txt():
    text = extract_text(FIXTURES / "sample.txt")
    assert "Договор оказания услуг" in text


def test_extract_md():
    text = extract_text(FIXTURES / "sample.md")
    assert "Дополнительное соглашение" in text
    assert "Прочие условия" in text


def test_extract_rtf():
    text = extract_text(FIXTURES / "sample.rtf")
    assert "Претензия" in text
    assert "10 дней" in text


def test_extract_docx():
    text = extract_text(FIXTURES / "sample.docx")
    assert "Акт приема-передачи" in text
    assert "Станок ЧПУ" in text  # table content included
    assert "2" in text


def test_unsupported_extension_raises():
    with pytest.raises(UnsupportedFileTypeError):
        extract_text(FIXTURES / "sample.txt.bak")


def test_discover_documents_finds_supported_files():
    paths = discover_documents(FIXTURES, recursive=True)
    suffixes = {p.suffix.lower() for p in paths}

    assert ".txt" in suffixes
    assert ".md" in suffixes
    assert ".rtf" in suffixes
    assert ".docx" in suffixes
