"""Pydantic view models for header-related responses."""

from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field


class HeaderTracePayload(BaseModel):
    """Trace metadata captured during header extraction runs."""

    events: list[dict[str, Any]] = Field(default_factory=list)
    path: str | None = None
    summary_path: str | None = None
    json_path: str | None = None

    model_config = ConfigDict(extra="ignore")


class HeaderOutlineNode(BaseModel):
    """Hierarchical outline node returned by header extraction."""

    title: str | None = None
    numbering: str | None = None
    page: int | None = None
    children: list["HeaderOutlineNode"] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class SimpleHeaderPayload(BaseModel):
    """Flattened header entry used by alignment and UI helpers."""

    text: str
    number: str | None = None
    level: int = 1
    page: int | None = None
    line_idx: int | None = None
    global_idx: int | None = None
    section_key: str | None = Field(
        default=None,
        alias="sectionKey",
        validation_alias="sectionKey",
        serialization_alias="sectionKey",
    )
    source_idx: int | None = None
    strategy: str | None = None
    score: float | None = None

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class HeaderSectionPayload(BaseModel):
    """Section bounds derived from aligned headers."""

    section_key: str | None = Field(
        default=None,
        alias="sectionKey",
        validation_alias="sectionKey",
        serialization_alias="sectionKey",
    )
    header_text: str | None = None
    title: str | None = Field(default=None, alias="title")
    header_number: str | None = None
    number: str | None = Field(default=None, alias="number")
    level: int = 1
    start_global_idx: int
    end_global_idx: int
    start_page: int | None = None
    end_page: int | None = None

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class HeaderOrchestrationView(BaseModel):
    """Direct view over :mod:`backend.services.headers_orchestrator` output."""

    headers: list[dict[str, Any]] = Field(default_factory=list)
    sections: list[dict[str, Any]] = Field(default_factory=list)
    mode: str | None = None
    lines: list[dict[str, Any]] = Field(default_factory=list)
    doc_hash: str | None = None
    excluded_pages: list[int] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)
    fenced_text: str | None = None
    llm_failure_raw_response: str | None = None
    trace: HeaderTracePayload | None = None
    llm_headers: list[dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "HeaderOrchestrationView":
        """Normalise an orchestrator payload into a view model."""

        return cls.model_validate(payload)


class HeaderRunTokens(BaseModel):
    """Token accounting details for a header extraction run."""

    prompt: int | None = None
    completion: int | None = None

    model_config = ConfigDict(extra="ignore")


class HeaderRunMeta(BaseModel):
    """Metadata associated with stored header runs."""

    model: str | None = None
    promptHash: str | None = None
    sourceHash: str | None = None
    tokens: HeaderRunTokens | None = None
    latencyMs: int | None = None
    createdAt: str | None = None

    model_config = ConfigDict(extra="ignore")


class HeaderRunResponse(BaseModel):
    """Top-level payload returned from header APIs."""

    document_id: int = Field(alias="documentId")
    run_id: int | None = Field(default=None, alias="runId")
    outline: list[HeaderOutlineNode] = Field(default_factory=list)
    meta: HeaderRunMeta | None = None
    sections: list[HeaderSectionPayload] = Field(default_factory=list)
    simpleheaders: list[SimpleHeaderPayload] = Field(default_factory=list)
    llm_headers: list[dict[str, Any]] = Field(default_factory=list, alias="llm_headers")
    matches: list[dict[str, Any]] = Field(default_factory=list)
    doc_hash: str | None = Field(default=None, alias="docHash")
    mode: str | None = None
    messages: list[str] = Field(default_factory=list)
    trace: HeaderTracePayload | None = None

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "HeaderRunResponse":
        """Coerce a legacy headers payload into the canonical view."""

        return cls.model_validate(payload)


class HeaderOutlineResponse(BaseModel):
    """Outline-only slice returned by outline endpoints."""

    document_id: int = Field(alias="documentId")
    run_id: int | None = Field(default=None, alias="runId")
    outline: list[HeaderOutlineNode] = Field(default_factory=list)
    meta: HeaderRunMeta | None = None

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "HeaderOutlineResponse":
        """Normalise a legacy outline payload into the canonical view."""

        return cls.model_validate(payload)


class StoredHeadersView(BaseModel):
    """Cached header tree retrieved from the artifact store."""

    headers: list[dict[str, Any]] = Field(default_factory=list)
    sections: list[dict[str, Any]] = Field(default_factory=list)
    mode: str | None = None
    messages: list[str] = Field(default_factory=list)
    doc_hash: str | None = None
    created_at: str | None = None

    model_config = ConfigDict(extra="ignore")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "StoredHeadersView":
        """Create a typed view over stored header artifacts."""

        return cls.model_validate(payload)


HeaderOutlineNode.model_rebuild()


__all__ = [
    "HeaderOrchestrationView",
    "HeaderOutlineNode",
    "HeaderOutlineResponse",
    "HeaderRunMeta",
    "HeaderRunResponse",
    "HeaderRunTokens",
    "HeaderSectionPayload",
    "HeaderTracePayload",
    "SimpleHeaderPayload",
    "StoredHeadersView",
]
