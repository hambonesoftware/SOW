"""LLM-backed Scope of Work extraction pipeline."""

from __future__ import annotations

import hashlib
import json
import logging
import textwrap
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable, Mapping, Sequence

from sqlalchemy import desc, select
from sqlmodel import Session

from ..config import Settings
from ..models import Document, DocumentPage, DocumentSection, SOWRun, SOWStep
from .lines import get_fulltext
from .llm import LLMResult, LLMService

LOGGER = logging.getLogger(__name__)

PROMPT_FENCE = "#sow#"
SECTION_KEYWORDS: tuple[str, ...] = (
    "scope of work",
    "scope",
    "sequence of operations",
    "system description",
    "functional description",
    "functional specification",
    "operational description",
    "process description",
)
MAX_SECTION_SNIPPETS = 8
SECTION_CHAR_LIMIT = 6000
PROMPT_TEMPLATE = textwrap.dedent(
    """
    Document ID: {document_id}
    Document filename: {filename}
    Document checksum: {checksum}

    Context excerpts:
    {context}

    Instructions:
    1. Act as an industrial automation engineer reviewing a Scope of Work / Sequence of Operations document.
    2. Extract the end-to-end workflow as atomic steps (one actionable idea per step).
    3. Preserve the original wording in `description` when possible; do not summarize aggressively.
    4. Populate metadata fields such as `phase`, `actor`, `location`, `inputs`, `outputs`, `dependencies`, and `header_section_key` when the source text implies them.
    5. Include reasonable `start_page` and `end_page` values (1-based page numbers) whenever the source span is known.
    6. Return ONLY valid JSON inside {fence} fences using this schema:

       {{"steps": [
           {{
             "order_index": 1,
             "step_id": "1",
             "phase": "Design",
             "title": "Review customer RFQ",
             "description": "...",
             "actor": "Integrator",
             "location": "Office",
             "inputs": "RFQ, standards",
             "outputs": "Clarifications",
             "dependencies": null,
             "header_section_key": "scope_of_work",
             "start_page": 3,
             "end_page": 4
           }}
       ]}}

    7. Omit any prose outside the JSON fences; no Markdown code blocks.
    """
)
PROMPT_HASH = hashlib.sha256(PROMPT_TEMPLATE.encode("utf-8")).hexdigest()

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are an experienced industrial automation engineer. Read the provided Scope of Work
    context and emit a precise list of execution steps that cover the described system lifecycle.
    Each step must be atomic, chronologically ordered, and grounded in the supplied text.
    """
).strip()


@dataclass(slots=True)
class SOWExtractionResult:
    """Container describing the outcome of an extraction attempt."""

    run: SOWRun
    steps: list[SOWStep]
    reused: bool


class SOWExtractionError(RuntimeError):
    """Raised when SOW extraction cannot be completed."""


class DocumentNotReadyError(SOWExtractionError):
    """Raised when the document is missing prerequisites (e.g., parsing)."""


def run_sow_extraction(
    document_id: int,
    *,
    session: Session,
    settings: Settings,
    force: bool = False,
    llm: LLMService | None = None,
) -> SOWExtractionResult:
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
        raise DocumentNotReadyError("Document text is unavailable; parse the document first")

    pages = _load_page_lookup(session, doc_id)
    sections = _load_sections(session, doc_id)
    snippets = _build_context_snippets(full_text, sections, pages, settings)
    rendered_context = _render_context(snippets)
    truncated_context = _truncate_text(rendered_context, _approx_char_limit(settings))
    source_hash = hashlib.sha256(truncated_context.encode("utf-8")).hexdigest()

    if not force:
        reused = _reuse_existing_run(session=session, document_id=doc_id, source_hash=source_hash)
        if reused is not None:
            return reused

    llm_client = llm or LLMService(settings=settings, cache_dir=settings.sow_cache_dir)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": PROMPT_TEMPLATE.format(
                document_id=doc_id,
                filename=document.filename,
                checksum=document.checksum,
                context=truncated_context,
                fence=PROMPT_FENCE,
            ),
        },
    ]

    params = {
        "max_tokens": settings.sow_llm_max_input_tokens,
        "temperature": 0.2,
    }
    start_time = time.perf_counter()
    result = llm_client.generate(
        messages=messages,
        model=settings.sow_llm_model,
        fence=PROMPT_FENCE,
        params=params,
        metadata={"document_id": doc_id, "feature": "sow"},
    )
    latency_ms = int((time.perf_counter() - start_time) * 1000)

    payload_text = (result.fenced or result.content or "").strip()
    if not payload_text:
        raise SOWExtractionError("LLM returned an empty response")
    payload = _load_json(payload_text)
    steps_payload = parse_sow_steps(payload)

    run, steps = _persist_run(
        session=session,
        settings=settings,
        document_id=doc_id,
        source_hash=source_hash,
        latency_ms=latency_ms,
        llm_result=result,
        steps_payload=steps_payload,
    )
    return SOWExtractionResult(run=run, steps=steps, reused=False)


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


def parse_sow_steps(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Coerce ``payload`` into a list of normalised step dictionaries."""

    if not isinstance(payload, Mapping):
        raise SOWExtractionError("SOW response must be a JSON object")

    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, Sequence) or not raw_steps:
        raise SOWExtractionError("SOW response is missing a non-empty 'steps' array")

    normalised: list[dict[str, object]] = []
    used_indices: set[int] = set()
    fallback_index = 1
    for entry in raw_steps:
        if not isinstance(entry, Mapping):
            continue
        provided_index = _coerce_int(entry.get("order_index"))
        if provided_index is not None and provided_index > 0:
            order_index = provided_index
        else:
            order_index = _next_available_index(fallback_index, used_indices)
            fallback_index = order_index + 1
        used_indices.add(order_index)
        title = str(entry.get("title", "")).strip()
        description = str(entry.get("description", "")).strip()
        if not description:
            description = title
        if not title:
            title = description or f"Step {order_index}"
        if not description:
            continue

        step_payload: dict[str, object] = {
            "order_index": order_index,
            "step_id": _coerce_str(entry.get("step_id")),
            "phase": _coerce_str(entry.get("phase")),
            "title": title,
            "description": description,
            "actor": _coerce_str(entry.get("actor")),
            "location": _coerce_str(entry.get("location")),
            "inputs": _coerce_str(entry.get("inputs")),
            "outputs": _coerce_str(entry.get("outputs")),
            "dependencies": _coerce_str(entry.get("dependencies")),
            "header_section_key": _coerce_str(
                entry.get("header_section_key") or entry.get("section_key")
            ),
            "start_page": _coerce_int(entry.get("start_page")),
            "end_page": _coerce_int(entry.get("end_page")),
        }
        normalised.append(step_payload)

    if not normalised:
        raise SOWExtractionError("LLM response did not contain any valid steps")

    normalised.sort(key=lambda item: (int(item["order_index"]), item.get("step_id") or ""))
    return normalised


def _reuse_existing_run(
    *, session: Session, document_id: int, source_hash: str
) -> SOWExtractionResult | None:
    statement = (
        select(SOWRun)
        .where(
            SOWRun.document_id == document_id,
            SOWRun.source_hash == source_hash,
            SOWRun.status == "ok",
        )
        .order_by(desc(SOWRun.created_at))
    )
    run = session.exec(statement).scalars().first()
    if run is None:
        return None
    steps = _load_steps_for_run(session, run.id or 0)
    return SOWExtractionResult(run=run, steps=steps, reused=True)


def _persist_run(
    *,
    session: Session,
    settings: Settings,
    document_id: int,
    source_hash: str,
    latency_ms: int,
    llm_result: LLMResult,
    steps_payload: Sequence[Mapping[str, object]],
) -> tuple[SOWRun, list[SOWStep]]:
    """Insert the :class:`SOWRun` and its associated :class:`SOWStep` rows."""

    timestamp = datetime.now(UTC)
    usage = llm_result.usage or {}
    run = SOWRun(
        document_id=document_id,
        model=settings.sow_llm_model,
        source_hash=source_hash,
        prompt_hash=PROMPT_HASH,
        tokens_prompt=_coerce_int(usage.get("prompt_tokens")),
        tokens_completion=_coerce_int(usage.get("completion_tokens")),
        latency_ms=latency_ms,
        status="ok",
        error_message=None,
        created_at=timestamp,
        updated_at=timestamp,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    stored_steps: list[SOWStep] = []
    for payload in steps_payload:
        step = SOWStep(run_id=run.id, **payload)
        session.add(step)
        stored_steps.append(step)
    session.commit()
    for step in stored_steps:
        session.refresh(step)
    return run, stored_steps


def _load_steps_for_run(session: Session, run_id: int) -> list[SOWStep]:
    statement = (
        select(SOWStep)
        .where(SOWStep.run_id == run_id)
        .order_by(SOWStep.order_index, SOWStep.id)
    )
    return list(session.exec(statement).scalars().all())


def _load_page_lookup(session: Session, document_id: int) -> dict[int, DocumentPage]:
    statement = (
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_index)
    )
    pages = session.exec(statement).scalars().all()
    lookup: dict[int, DocumentPage] = {}
    for page in pages:
        lookup[int(page.page_index)] = page
    return lookup


def _load_sections(session: Session, document_id: int) -> list[DocumentSection]:
    statement = (
        select(DocumentSection)
        .where(DocumentSection.document_id == document_id)
        .order_by(DocumentSection.start_page, DocumentSection.start_global_idx)
    )
    return list(session.exec(statement).scalars().all())


def _build_context_snippets(
    full_text: str,
    sections: Sequence[DocumentSection],
    pages: Mapping[int, DocumentPage],
    settings: Settings,
) -> list[dict[str, str]]:
    snippets: list[dict[str, str]] = []
    for section in sections:
        if len(snippets) >= MAX_SECTION_SNIPPETS:
            break
        if not _looks_like_sow_section(section):
            continue
        section_text = _section_text(section, pages)
        if not section_text:
            continue
        snippets.append(
            {
                "label": _describe_section(section),
                "text": _truncate_text(section_text, SECTION_CHAR_LIMIT),
            }
        )

    if snippets:
        return snippets

    return [
        {
            "label": "Full Document Text",
            "text": _truncate_text(full_text, _approx_char_limit(settings)),
        }
    ]


def _describe_section(section: DocumentSection) -> str:
    start_page = section.start_page if section.start_page is not None else "?"
    end_page = section.end_page if section.end_page is not None else start_page
    return (
        f"Section: {section.title} (key={section.section_key}, pages {start_page}-{end_page})"
    )


def _section_text(section: DocumentSection, pages: Mapping[int, DocumentPage]) -> str:
    bounds = _section_page_bounds(section)
    if bounds is None:
        return ""
    start_idx, end_idx = bounds
    parts: list[str] = []
    for page_index in range(start_idx, end_idx + 1):
        page = pages.get(page_index)
        if page is None:
            continue
        text = str(page.text_raw or "").strip()
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _section_page_bounds(section: DocumentSection) -> tuple[int, int] | None:
    start = _coerce_int(section.start_page)
    end = _coerce_int(section.end_page)
    if start is None and end is None:
        return None
    if start is None:
        start = end
    if end is None:
        end = start
    start_idx = start - 1 if start and start > 0 else int(start or 0)
    if start_idx < 0:
        start_idx = 0
    end_idx = end - 1 if end and end > 0 else int(end or start_idx)
    if end_idx < start_idx:
        end_idx = start_idx
    return start_idx, end_idx


def _looks_like_sow_section(section: DocumentSection) -> bool:
    haystack = f"{section.title} {section.number or ''}".lower()
    return any(keyword in haystack for keyword in SECTION_KEYWORDS)


def _render_context(snippets: Sequence[Mapping[str, str]]) -> str:
    chunks = [f"{snippet['label']}\n{snippet['text']}" for snippet in snippets]
    return "\n\n".join(chunk.strip() for chunk in chunks if chunk.strip())


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    truncated = text[:limit].rsplit("\n", 1)[0].strip()
    return truncated + "\n…"


def _approx_char_limit(settings: Settings) -> int:
    return max(4000, int(settings.sow_llm_max_input_tokens) * 4)


def _load_json(raw: str) -> Mapping[str, object]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        # Attempt to locate the first top-level JSON object in the payload.
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


__all__ = [
    "DocumentNotReadyError",
    "SOWExtractionError",
    "SOWExtractionResult",
    "latest_sow_run",
    "parse_sow_steps",
    "run_sow_extraction",
]

