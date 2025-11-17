"""Scope of Work (SOW) API router."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlmodel import Session

from ..api.sow import SowRunRequest, SowRunResponse
from ..config import Settings, get_settings
from ..database import get_session
from ..models import Document
from ..services.sow_extraction import (
    DocumentNotReadyError,
    SOWExtractionError,
    build_sow_response,
    latest_sow_run,
    run_sow_extraction,
)

router = APIRouter(prefix="/api/sow", tags=["sow"])


@router.post("/{document_id}", response_model=SowRunResponse)
async def create_sow_run(
    document_id: int,
    *,
    request: SowRunRequest | None = Body(default=None),
    force: bool = False,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> SowRunResponse:
    """Trigger SOW extraction for the specified document."""

    _ensure_document_exists(session, document_id)
    run_request = request or SowRunRequest()
    try:
        return run_sow_extraction(
            document_id,
            session=session,
            settings=settings,
            request=run_request,
            force=force,
        )
    except DocumentNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except SOWExtractionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{document_id}", response_model=SowRunResponse)
async def get_latest_sow_run(
    document_id: int,
    *,
    session: Session = Depends(get_session),
) -> SowRunResponse:
    """Return the most recent successful SOW run for the document."""

    _ensure_document_exists(session, document_id)
    existing = latest_sow_run(session=session, document_id=document_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No SOW run found")
    run, steps = existing
    return build_sow_response(document_id, run, steps)


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


__all__ = ["router"]
