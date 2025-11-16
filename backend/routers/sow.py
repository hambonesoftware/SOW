"""Scope of Work (SOW) API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from ..config import Settings, get_settings
from ..database import get_session
from ..models import Document, SOWRun, SOWStep
from ..services.sow_extraction import (
    DocumentNotReadyError,
    SOWExtractionError,
    latest_sow_run,
    run_sow_extraction,
)

router = APIRouter(prefix="/api/sow", tags=["sow"])


@router.post("/{document_id}")
async def create_sow_run(
    document_id: int,
    *,
    force: bool = False,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Trigger SOW extraction for the specified document."""

    _ensure_document_exists(session, document_id)
    try:
        result = run_sow_extraction(
            document_id,
            session=session,
            settings=settings,
            force=force,
        )
    except DocumentNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SOWExtractionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return _serialize_run(document_id, result.run, result.steps, reused=result.reused)


@router.get("/{document_id}")
async def get_latest_sow_run(
    document_id: int,
    *,
    session: Session = Depends(get_session),
):
    """Return the most recent successful SOW run for the document."""

    _ensure_document_exists(session, document_id)
    existing = latest_sow_run(session=session, document_id=document_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SOW run found")
    run, steps = existing
    return _serialize_run(document_id, run, steps, reused=True)


@router.get("/{document_id}/status")
async def sow_status(
    document_id: int,
    *,
    session: Session = Depends(get_session),
):
    """Return a lightweight status indicator for SOW extraction availability."""

    _ensure_document_exists(session, document_id)
    existing = latest_sow_run(session=session, document_id=document_id)
    if existing is None:
        return {
            "documentId": document_id,
            "sow": False,
            "runId": None,
            "status": None,
        }
    run, _ = existing
    return {
        "documentId": document_id,
        "sow": True,
        "runId": run.id,
        "status": run.status,
    }


def _ensure_document_exists(session: Session, document_id: int) -> None:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")


def _serialize_run(
    document_id: int,
    run: SOWRun,
    steps: list[SOWStep],
    *,
    reused: bool,
) -> dict:
    tokens = None
    if run.tokens_prompt is not None or run.tokens_completion is not None:
        tokens = {
            "prompt": run.tokens_prompt,
            "completion": run.tokens_completion,
        }
    meta = {
        "model": run.model,
        "sourceHash": run.source_hash,
        "promptHash": run.prompt_hash,
        "tokens": tokens,
        "latencyMs": run.latency_ms,
        "createdAt": run.created_at.isoformat() if run.created_at else None,
        "updatedAt": run.updated_at.isoformat() if run.updated_at else None,
    }
    return {
        "documentId": document_id,
        "runId": run.id,
        "status": run.status,
        "reused": reused,
        "meta": meta,
        "steps": [_serialize_step(step) for step in steps],
    }


def _serialize_step(step: SOWStep) -> dict:
    return {
        "id": step.id,
        "runId": step.run_id,
        "orderIndex": step.order_index,
        "stepId": step.step_id,
        "phase": step.phase,
        "title": step.title,
        "description": step.description,
        "actor": step.actor,
        "location": step.location,
        "inputs": step.inputs,
        "outputs": step.outputs,
        "dependencies": step.dependencies,
        "headerSectionKey": step.header_section_key,
        "startPage": step.start_page,
        "endPage": step.end_page,
    }


__all__ = ["router"]

