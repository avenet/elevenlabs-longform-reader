from io import BytesIO

import pytest
from pypdf import PdfWriter

from app.services.extractor import extract_from_bytes, extract_from_text


def test_accepts_utf8_text():
    data = "Café résumé — hello 你好".encode()
    assert extract_from_bytes("notes.txt", data) == "Café résumé — hello 你好"


def test_rejects_unsupported_extension():
    with pytest.raises(ValueError, match="Only .txt and .pdf"):
        extract_from_bytes("notes.docx", b"hello")


def test_rejects_empty_text_input():
    with pytest.raises(ValueError, match="Text is empty"):
        extract_from_text("   \n")


def test_rejects_empty_upload_bytes_via_txt_content():
    assert extract_from_bytes("empty.txt", b"") == ""


def test_rejects_pdf_with_no_extractable_text():
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(buffer)
    with pytest.raises(ValueError, match="No extractable text"):
        extract_from_bytes("blank.pdf", buffer.getvalue())
