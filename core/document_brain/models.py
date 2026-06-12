from pydantic import BaseModel


class TextBlock(BaseModel):
    page: int
    text: str
    bbox: tuple[float, float, float, float] | None = None
    source: str  # "text" (native PDF text) or "ocr"


class PageExtraction(BaseModel):
    page: int
    blocks: list[TextBlock]
    tables: list[list[list[str]]] = []


class DocumentExtraction(BaseModel):
    file_path: str
    pages: list[PageExtraction]

    def full_text(self) -> str:
        return "\n\n".join(
            block.text for page in self.pages for block in page.blocks
        )


class DocumentSection(BaseModel):
    title: str
    content: str
    section_type: str  # e.g. "preamble", "terms", "signatures", "appendix"


class StructuredDocument(BaseModel):
    document_type: str  # e.g. "contract", "court_ruling", "claim"
    title: str
    parties: list[str] = []
    dates: list[str] = []
    sections: list[DocumentSection] = []
    summary: str = ""
