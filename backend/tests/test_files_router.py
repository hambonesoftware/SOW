"""Regression tests for the files router."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


def test_delete_file_returns_no_content(monkeypatch) -> None:
    """DELETE /api/files/{id} must not include a response body."""

    def dummy_session():
        yield object()

    def fake_delete_document(*, session, document_id, settings):  # pragma: no cover - via FastAPI
        assert session is not None
        assert settings is not None
        assert document_id == 123
        return True

    monkeypatch.setattr("backend.routers.files.get_session", dummy_session)
    monkeypatch.setattr("backend.routers.files.delete_document", fake_delete_document)

    with TestClient(app) as client:
        response = client.delete("/api/files/123")

    assert response.status_code == 204
    assert response.content == b""
    # 204 responses must not emit a content type header according to RFC 9110.
    assert response.headers.get("content-type") is None
