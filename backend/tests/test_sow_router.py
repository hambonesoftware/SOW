from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlmodel import Session

from backend import database
from backend.config import reset_settings_cache
from backend.main import app
from backend.models import Document, DocumentPage, DocumentSection
from backend.services import sow_extraction
from backend.services.llm import LLMResult


def test_sow_router_creates_and_reuses_run(tmp_path, monkeypatch) -> None:
    """The /api/sow endpoints should create and reuse extraction runs."""

    db_path = tmp_path / "sow.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    database.reset_database_state()
    reset_settings_cache()
    database.init_db()
    engine = database.get_engine()

    with Session(engine) as session:
        document = Document(
            filename="sample.pdf",
            checksum="checksum-sow",
            last_parsed_at=datetime.now(UTC),
        )
        session.add(document)
        session.commit()
        session.refresh(document)
        doc_id = int(document.id or 0)

        session.add(
            DocumentPage(
                document_id=doc_id,
                page_index=0,
                width=8.5,
                height=11.0,
                text_raw="Scope of Work details",
                layout=[],
            )
        )
        session.add(
            DocumentSection(
                document_id=doc_id,
                section_key="scope::0",
                title="Scope of Work",
                number="1",
                level=1,
                start_global_idx=0,
                end_global_idx=10,
                start_page=1,
                end_page=1,
            )
        )
        session.commit()

    fake_payload = {
        "steps": [
            {
                "order_index": 1,
                "title": "Review requirements",
                "description": "Review requirements",
                "phase": "Design",
                "start_page": 1,
                "end_page": 1,
            }
        ]
    }

    class FakeLLM:
        calls = 0

        def __init__(self, *args, **kwargs):  # noqa: D401 - test stub
            pass

        def generate(self, **kwargs):  # noqa: D401 - test stub
            FakeLLM.calls += 1
            return LLMResult(
                content=f"{sow_extraction.PROMPT_FENCE} {json.dumps(fake_payload)} {sow_extraction.PROMPT_FENCE}",
                usage={"prompt_tokens": 10, "completion_tokens": 5},
                cached=False,
                fenced=json.dumps(fake_payload),
            )

    monkeypatch.setattr(sow_extraction, "LLMService", FakeLLM)

    with TestClient(app) as client:
        response = client.post(f"/api/sow/{doc_id}")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["steps"], payload
        assert payload["meta"]["model"]
        assert payload["reused"] is False
        assert FakeLLM.calls == 1

        reuse = client.post(f"/api/sow/{doc_id}")
        assert reuse.status_code == 200
        assert reuse.json()["reused"] is True
        assert FakeLLM.calls == 1, "Existing runs should be reused when force=false"

        fetched = client.get(f"/api/sow/{doc_id}")
        assert fetched.status_code == 200
        assert fetched.json()["steps"], fetched.text

        status_resp = client.get(f"/api/sow/{doc_id}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["sow"] is True
