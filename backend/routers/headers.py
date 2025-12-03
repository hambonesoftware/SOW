"""Header router that wraps :mod:`backend.api.headers` with view models."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlmodel import Session

from ..api import headers as headers_api
from ..config import Settings, get_settings
from ..database import get_session
from ..services.headers import HeadersLLMClient as HeadersLLMClientImpl
from ..services.headers_orchestrator import (
    extract_headers_and_chunks as orchestrator_extract_headers_and_chunks,
)
from ..services.pdf_native import parse_pdf as parse_pdf_impl
from ..view_models.headers import HeaderOutlineResponse, HeaderRunResponse

router = APIRouter(prefix="/api", tags=["headers"])


@router.post("/headers/{document_id}", response_model=HeaderRunResponse)
async def compute_headers(
    document_id: int,
    *,
    force: bool = Query(
        False,
        description="Force new LLM headers; purge prior headers/sections and bypass caches.",
    ),
    align: str | None = Query(
        None,
        description="Header alignment strategy (sequential, legacy).",
    ),
    trace: bool = Query(
        False,
        description="Return inline trace events when available.",
    ),
    body: dict | None = Body(default=None),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Forward the request to :func:`backend.api.headers.extract_headers_and_chunks`."""

    effective_force = bool(force or (body or {}).get("force"))

    if effective_force:
        purge_cache = getattr(headers_api, "purge_llm_cache_for_document", None)
        if callable(purge_cache):
            try:
                purge_cache(document_id)
            except Exception:  # pragma: no cover - best-effort cleanup
                pass

    result = await headers_api.extract_headers_and_chunks(
        document_id=document_id,
        settings=settings,
        session=session,
        force=effective_force,
        trace=trace,
        align=align,
    )

    if isinstance(result, JSONResponse):
        return result

    return HeaderRunResponse.from_payload(result)


@router.get("/headers/{document_id}", response_model=HeaderRunResponse)
def get_headers(
    document_id: int,
    *,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Return the persisted headers payload for ``document_id``."""

    payload = headers_api.get_headers_from_db(
        session,
        document_id,
        settings=settings,
    )
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Headers not found",
        )
    return HeaderRunResponse.from_payload(payload)


@router.get("/headers/{document_id}/outline", response_model=HeaderOutlineResponse)
def get_headers_outline(
    document_id: int,
    *,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Return the persisted raw outline for ``document_id``."""

    payload = headers_api.get_outline_from_db(
        session,
        document_id,
        settings=settings,
    )
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outline not found",
        )
    return HeaderOutlineResponse.from_payload(payload)


parse_pdf = parse_pdf_impl  # Deprecated: prefer importing from services.pdf_native
extract_headers_and_chunks = (
    orchestrator_extract_headers_and_chunks
)  # Deprecated: prefer importing from backend.services.headers_orchestrator


@router.get("/headers/{document_id}/section-text", response_class=PlainTextResponse)
def section_text(
    document_id: int,
    start: int,
    end: int,
    *,
    section_key: str | None = Query(None),
    session: Session = Depends(get_session),
):
    """Compatibility shim for :func:`backend.api.headers.section_text`."""

    return headers_api.section_text(
        document_id=document_id,
        start=start,
        end=end,
        section_key=section_key,
        session=session,
    )
HeadersLLMClient = HeadersLLMClientImpl

__all__ = [
    "router",
    "compute_headers",
    "parse_pdf",
    "extract_headers_and_chunks",
    "section_text",
    "HeadersLLMClient",
]

