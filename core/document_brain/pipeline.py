from core.document_brain.extractor import extract_document
from core.document_brain.models import StructuredDocument
from core.document_brain.structurer import structure_document


def process_document(file_path: str) -> StructuredDocument:
    """Run the full Document Brain pipeline: extract layout/text, then structure it."""
    extraction = extract_document(file_path)
    return structure_document(extraction)
