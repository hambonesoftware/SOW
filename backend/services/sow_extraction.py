"""LLM-backed Scope of Work extraction pipeline."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable, Mapping, Sequence

from sqlalchemy import desc, select
from sqlmodel import Session

from ..api.sow import ProcessStep, SowRunRequest, SowRunResponse
from ..config import Settings
from ..models import Document, SOWRun, SOWStep
from .lines import get_fulltext
from .llm import LLMResult, LLMService
from .sow_prompts import build_sow_system_prompt, build_sow_user_prompt
from .text_chunker import TextChunk, chunk_text_for_llm

LOGGER = logging.getLogger(__name__)

PROMPT_FENCE = "#sow#"
_PROMPT_HASH_SOURCE = build_sow_system_prompt() + build_sow_user_prompt(
    TextChunk(index=1, total=1, text="{chunk_text}")
)
PROMPT_HASH = hashlib.sha256(_PROMPT_HASH_SOURCE.encode("utf-8")).hexdigest()


class SOWExtractionError(RuntimeError):
    """Raised when SOW extraction cannot be completed."""


class DocumentNotReadyError(SOWExtractionError):
    """Raised when the document is missing prerequisites (e.g., parsing)."""


@dataclass(slots=True)
class CachedRun:
    """Container for a cached SOW run and its associated steps."""

    run: SOWRun
    steps: list[SOWStep]


def run_sow_extraction(
    document_id: int,
    *,
    session: Session,
    settings: Settings,
    request: SowRunRequest,
    force: bool = False,
    llm: LLMService | None = None,
) -> SowRunResponse:
    """Execute the SOW extraction workflow for ``document_id``."""

    document = session.get(Document, document_id)
    if document is None:
        raise SOWExtractionError("Document not found")
    if document.id is None:
        raise SOWExtractionError("Document is missing a primary key")
    if not document.last_parsed_at:
        raise DocumentNotReadyError("Document must be parsed before extracting SOW steps")

    doc_id = int(document.id)
    full_text = get_fulltext(session, doc_id).strip()
    if not full_text:
        raise SOWExtractionError("Parsed document text is empty")

    model_name = request.model or settings.sow_llm_model
    max_context = min(
        max(1, request.max_context_tokens), settings.sow_llm_max_input_tokens
    )
    chunks = chunk_text_for_llm(full_text, max_context)
    if not chunks:
        raise SOWExtractionError("Parsed document text is empty")

    source_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()

    if not force:
        cached = _reuse_existing_run(
            session=session,
            document_id=doc_id,
            source_hash=source_hash,
            model_name=model_name,
        )
        if cached:
            LOGGER.info("Reusing cached SOW run for document %s", doc_id)
            return build_sow_response(doc_id, cached.run, cached.steps)

    llm_client = llm or LLMService(settings=settings, cache_dir=settings.sow_cache_dir)
    if not llm_client.is_enabled:
        raise SOWExtractionError("OPENROUTER_API_KEY is not configured")

    system_prompt = build_sow_system_prompt()
    all_chunk_steps: list[list[ProcessStep]] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0

    for chunk in chunks:
        result = _invoke_llm(
            llm_client,
            model_name=model_name,
            system_prompt=system_prompt,
            chunk=chunk,
            settings=settings,
            document_id=doc_id,
            temperature=request.temperature,
        )
        payload_text = (result.fenced or result.content or "").strip()
        if not payload_text:
            raise SOWExtractionError(
                f"LLM returned an empty response for chunk {chunk.index}"
            )
        payload = _load_json(payload_text)
        chunk_steps = parse_sow_steps(payload, chunk_index=chunk.index)
        all_chunk_steps.append(chunk_steps)

        usage = result.usage or {}
        total_prompt_tokens += _coerce_int(usage.get("prompt_tokens")) or 0
        total_completion_tokens += _coerce_int(usage.get("completion_tokens")) or 0

    normalised_steps = _normalise_steps(all_chunk_steps)

    run, stored_steps = _persist_run(
        session=session,
        document_id=doc_id,
        model_name=model_name,
        source_hash=source_hash,
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        steps=normalised_steps,
    )
    return build_sow_response(doc_id, run, stored_steps)


def latest_sow_run(
    *, session: Session, document_id: int
) -> tuple[SOWRun, list[SOWStep]] | None:
    """Return the most recent successful SOW run for ``document_id``."""

    statement = (
        select(SOWRun)
        .where(SOWRun.document_id == document_id, SOWRun.status == "ok")
        .order_by(desc(SOWRun.created_at))
    )
    run = session.exec(statement).scalars().first()
    if run is None:
        return None
    steps = _load_steps_for_run(session, run.id or 0)
    return run, steps


def parse_sow_steps(
    payload: Mapping[str, object], *, chunk_index: int = 0
) -> list[ProcessStep]:
    """Coerce ``payload`` into a list of normalised :class:`ProcessStep`."""

    if not isinstance(payload, Mapping):
        raise SOWExtractionError("SOW response must be a JSON object")

    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, Sequence) or not raw_steps:
        raise SOWExtractionError("SOW response is missing a non-empty 'steps' array")

    processed: list[ProcessStep] = []
    used_indices: set[int] = set()
    fallback_order = 1
    for index, entry in enumerate(raw_steps, start=1):
        if not isinstance(entry, Mapping):
            continue
        order_value = entry.get("order") or entry.get("order_index")
        order = _coerce_int(order_value)
        if order is None or order <= 0:
            order = _next_available_index(fallback_order, used_indices)
            fallback_order = order + 1
        else:
            order = _next_available_index(order, used_indices)
        used_indices.add(order)

        title = _coerce_str(entry.get("title"))
        description = _coerce_str(entry.get("description"))
        if description and not title:
            title = description.splitlines()[0]
        if title and not description:
            description = title
        if not description:
            continue
        if not title:
            title = f"Step {order}"

        step_id = (
            _coerce_str(entry.get("id"))
            or _coerce_str(entry.get("step_id"))
            or _fallback_step_id(chunk_index, index)
        )
        label = _coerce_str(entry.get("label"))
        phase = _coerce_str(entry.get("phase"))
        source_page_start = _coerce_int(
            entry.get("source_page_start") or entry.get("start_page")
        )
        source_page_end = _coerce_int(
            entry.get("source_page_end") or entry.get("end_page")
        )
        source_section_title = _coerce_str(
            entry.get("source_section_title") or entry.get("header_section_key")
        )

        processed.append(
            ProcessStep(
                id=step_id,
                order=int(order),
                phase=phase,
                label=label,
                title=title,
                description=description,
                source_page_start=source_page_start,
                source_page_end=source_page_end,
                source_section_title=source_section_title,
            )
        )

    if not processed:
        raise SOWExtractionError("LLM response did not contain any valid steps")

    processed.sort(key=lambda step: (step.order, step.id))
    normalised: list[ProcessStep] = []
    for idx, step in enumerate(processed, start=1):
        normalised.append(
            ProcessStep(
                id=step.id,
                order=idx,
                phase=step.phase,
                label=step.label,
                title=step.title,
                description=step.description,
                source_page_start=step.source_page_start,
                source_page_end=step.source_page_end,
                source_section_title=step.source_section_title,
            )
        )

    return normalised


def _invoke_llm(
    llm_client: LLMService,
    *,
    model_name: str,
    system_prompt: str,
    chunk: TextChunk,
    settings: Settings,
    document_id: int,
    temperature: float,
) -> LLMResult:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": build_sow_user_prompt(chunk)},
    ]
    params = {
        "max_tokens": settings.sow_llm_max_input_tokens,
        "temperature": temperature,
    }
    return llm_client.generate(
        messages=messages,
        model=model_name,
        fence=PROMPT_FENCE,
        params=params,
        metadata={
            "feature": "sow",
            "document_id": document_id,
            "chunk": chunk.index,
        },
    )


def _normalise_steps(chunks_steps: Sequence[Sequence[ProcessStep]]) -> list[ProcessStep]:
    """Flatten and renumber orders across all chunks."""

    normalised: list[ProcessStep] = []
    order = 0
    for chunk_steps in chunks_steps:
        for step in chunk_steps:
            order += 1
            normalised.append(
                ProcessStep(
                    id=step.id or f"S{order:04d}",
                    order=order,
                    phase=step.phase,
                    label=step.label,
                    title=step.title,
                    description=step.description,
                    source_page_start=step.source_page_start,
                    source_page_end=step.source_page_end,
                    source_section_title=step.source_section_title,
                )
            )
    return normalised


def _persist_run(
    *,
    session: Session,
    document_id: int,
    model_name: str,
    source_hash: str,
    prompt_tokens: int,
    completion_tokens: int,
    steps: Sequence[ProcessStep],
) -> tuple[SOWRun, list[SOWStep]]:
    timestamp = datetime.now(UTC)
    run = SOWRun(
        document_id=document_id,
        model=model_name,
        source_hash=source_hash,
        prompt_hash=PROMPT_HASH,
        tokens_prompt=prompt_tokens or None,
        tokens_completion=completion_tokens or None,
        latency_ms=None,
        status="ok",
        error_message=None,
        created_at=timestamp,
        updated_at=timestamp,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    stored_steps: list[SOWStep] = []
    for step in steps:
        record = SOWStep(
            run_id=run.id,
            order_index=step.order,
            step_id=step.id,
            label=step.label,
            phase=step.phase,
            title=step.title,
            description=step.description,
            actor=None,
            location=None,
            inputs=None,
            outputs=None,
            dependencies=None,
            header_section_key=None,
            source_section_title=step.source_section_title,
            start_page=step.source_page_start,
            end_page=step.source_page_end,
        )
        session.add(record)
        stored_steps.append(record)
    session.commit()
    for step in stored_steps:
        session.refresh(step)
    return run, stored_steps


def _reuse_existing_run(
    *,
    session: Session,
    document_id: int,
    source_hash: str,
    model_name: str,
) -> CachedRun | None:
    statement = (
        select(SOWRun)
        .where(
            SOWRun.document_id == document_id,
            SOWRun.source_hash == source_hash,
            SOWRun.model == model_name,
            SOWRun.prompt_hash == PROMPT_HASH,
            SOWRun.status == "ok",
        )
        .order_by(desc(SOWRun.created_at))
    )
    run = session.exec(statement).scalars().first()
    if run is None:
        return None
    steps = _load_steps_for_run(session, run.id or 0)
    return CachedRun(run=run, steps=steps)


def _load_steps_for_run(session: Session, run_id: int) -> list[SOWStep]:
    statement = (
        select(SOWStep)
        .where(SOWStep.run_id == run_id)
        .order_by(SOWStep.order_index, SOWStep.id)
    )
    return list(session.exec(statement).scalars().all())


def build_sow_response(
    document_id: int, run: SOWRun, steps: Sequence[SOWStep]
) -> SowRunResponse:
    process_steps = _steps_from_models(steps)
    return SowRunResponse(
        document_id=document_id,
        run_id=str(run.id or ""),
        model=run.model,
        steps=process_steps,
    )


def _steps_from_models(records: Iterable[SOWStep]) -> list[ProcessStep]:
    steps: list[ProcessStep] = []
    for record in records:
        steps.append(
            ProcessStep(
                id=record.step_id or f"S{record.order_index:04d}",
                order=int(record.order_index),
                phase=record.phase,
                label=record.label,
                title=record.title,
                description=record.description,
                source_page_start=record.start_page,
                source_page_end=record.end_page,
                source_section_title=record.source_section_title
                or record.header_section_key,
            )
        )
    return steps


def _load_json(raw: str) -> Mapping[str, object]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end <= start:
            raise SOWExtractionError("LLM response was not valid JSON") from exc
        snippet = raw[start : end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError as exc_inner:
            raise SOWExtractionError("LLM response was not valid JSON") from exc_inner


def _coerce_int(value: object | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_str(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _next_available_index(start: int, used: set[int]) -> int:
    candidate = max(1, start)
    while candidate in used:
        candidate += 1
    return candidate


def _fallback_step_id(chunk_index: int, local_index: int) -> str:
    chunk_part = f"C{chunk_index:02d}" if chunk_index else "C00"
    return f"{chunk_part}-S{local_index:02d}"


__all__ = [
    "DocumentNotReadyError",
    "SOWExtractionError",
    "build_sow_response",
    "latest_sow_run",
    "parse_sow_steps",
    "run_sow_extraction",
]
