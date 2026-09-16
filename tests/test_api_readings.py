from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def no_enqueue(monkeypatch):
    monkeypatch.setattr(
        "app.routers.readings.enqueue_reading",
        AsyncMock(return_value=None),
    )


def test_create_reading_from_pasted_text(client, no_enqueue):
    response = client.post(
        "/api/readings",
        data={"text": "A short pasted reading for the test suite.", "title": "Demo"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["title"] == "Demo"
    assert payload["status"] == "queued"
    assert len(payload["sections"]) >= 1
    assert payload["sections"][0]["status"] == "pending"


def test_reject_neither_text_nor_file(client, no_enqueue):
    response = client.post("/api/readings", data={})
    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "text" in detail or "file" in detail


def test_reject_empty_upload(client, no_enqueue):
    response = client.post(
        "/api/readings",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_get_reading_status_and_sections(client, no_enqueue):
    created = client.post(
        "/api/readings",
        data={"text": "Status check body with enough content."},
    ).json()
    response = client.get(f"/api/readings/{created['id']}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == created["id"]
    assert "sections" in payload
    assert payload["sections"][0]["char_count"] > 0


def test_missing_reading_returns_404(client):
    response = client.get("/api/readings/999999")
    assert response.status_code == 404


def test_missing_audio_returns_404(client, no_enqueue):
    created = client.post(
        "/api/readings",
        data={"text": "Audio not ready yet for this section."},
    ).json()
    response = client.get(f"/api/readings/{created['id']}/sections/0/audio")
    assert response.status_code == 404


def test_unsupported_file_extension(client, no_enqueue):
    response = client.post(
        "/api/readings",
        files={"file": ("notes.docx", b"hello", "application/octet-stream")},
    )
    assert response.status_code == 400
