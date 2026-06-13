"""Extract raw text, layout blocks and tables from PDF documents.

Uses native text extraction (pdfplumber) where available and falls back
to OCR (pytesseract) for scanned pages with no extractable text layer.
"""

import pdfplumber
import pytesseract

from core.document_brain.models import DocumentExtraction, PageExtraction, TextBlock

OCR_LANG = "rus+eng"


def _extract_native_blocks(page: pdfplumber.page.Page, page_number: int) -> list[TextBlock]:
    blocks = []
    for word_group in page.extract_text_lines() or []:
        text = word_group.get("text", "").strip()
        if not text:
            continue
        bbox = (
            word_group["x0"],
            word_group["top"],
            word_group["x1"],
            word_group["bottom"],
        )
        blocks.append(TextBlock(page=page_number, text=text, bbox=bbox, source="text"))
    return blocks


def _extract_ocr_blocks(page: pdfplumber.page.Page, page_number: int) -> list[TextBlock]:
    image = page.to_image(resolution=300).original
    ocr_text = pytesseract.image_to_string(image, lang=OCR_LANG)
    blocks = []
    for line in ocr_text.splitlines():
        line = line.strip()
        if line:
            blocks.append(TextBlock(page=page_number, text=line, source="ocr"))
    return blocks


def extract_document(file_path: str) -> DocumentExtraction:
    pages: list[PageExtraction] = []

    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            native_blocks = _extract_native_blocks(page, i)

            if native_blocks:
                blocks = native_blocks
            else:
                blocks = _extract_ocr_blocks(page, i)

            tables = [
                [["" if cell is None else cell for cell in row] for row in table.extract()]
                for table in page.find_tables()
            ]

            pages.append(PageExtraction(page=i, blocks=blocks, tables=tables))

    return DocumentExtraction(file_path=file_path, pages=pages)
