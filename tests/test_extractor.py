from core.document_brain.models import DocumentExtraction, PageExtraction, TextBlock


def test_full_text_concatenates_blocks():
    extraction = DocumentExtraction(
        file_path="dummy.pdf",
        pages=[
            PageExtraction(
                page=1,
                blocks=[
                    TextBlock(page=1, text="Hello", source="text"),
                    TextBlock(page=1, text="World", source="text"),
                ],
            )
        ],
    )

    assert extraction.full_text() == "Hello\n\nWorld"
