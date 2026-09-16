from io import BytesIO
from unittest.mock import AsyncMock

from pypdf import PdfWriter

from app.services.errors import (
    GENERIC_INTERNAL_MESSAGE,
    PDF_NO_TEXT_MESSAGE,
    map_input_error,
)


def test_map_input_error_pdf_no_text():
    assert map_input_error(ValueError("No extractable text found in PDF")) == PDF_NO_TEXT_MESSAGE


def test_map_input_error_unknown_is_generic():
    assert map_input_error(ValueError("secret db url leaked")) == GENERIC_INTERNAL_MESSAGE


def test_blank_pdf_returns_safe_message(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.readings.enqueue_reading",
        AsyncMock(return_value=None),
    )
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(buffer)
    response = client.post(
        "/api/readings",
        files={"file": ("blank.pdf", buffer.getvalue(), "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == PDF_NO_TEXT_MESSAGE


def test_unexpected_error_returns_safe_500(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(
        "app.routers.readings.enqueue_reading",
        AsyncMock(return_value=None),
    )

    def boom(*args, **kwargs):
        raise RuntimeError("traceback with secret api key sk_live_123")

    monkeypatch.setattr("app.routers.readings.extract_from_text", boom)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/readings", data={"text": "hello world"})
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail == GENERIC_INTERNAL_MESSAGE
    assert "sk_live" not in detail
    assert "traceback" not in detail.lower()
