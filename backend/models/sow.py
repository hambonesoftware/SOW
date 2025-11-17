"""Scope of Work (SOW) persistence models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """Return the current UTC timestamp."""

    return datetime.now(UTC)


class SOWRun(SQLModel, table=True):
    """Metadata describing a single SOW extraction attempt."""

    __tablename__ = "sow_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id", index=True, nullable=False)
    model: str = Field(nullable=False, description="LLM model identifier used for extraction.")
    source_hash: str = Field(
        nullable=False,
        index=True,
        description="Hash of the document text that seeded this run.",
    )
    prompt_hash: str = Field(
        nullable=False, description="Hash of the prompt template and config used."
    )
    tokens_prompt: int | None = Field(
        default=None, description="Prompt token count reported by the LLM provider."
    )
    tokens_completion: int | None = Field(
        default=None,
        description="Completion token count reported by the LLM provider.",
    )
    latency_ms: int | None = Field(
        default=None, description="End-to-end latency for the LLM call in milliseconds."
    )
    status: str = Field(
        default="pending",
        description="Lifecycle status for the extraction run (ok/error/pending).",
    )
    error_message: str | None = Field(
        default=None, description="Optional error message captured when the run failed."
    )
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)


class SOWStep(SQLModel, table=True):
    """Structured representation of an extracted SOW step."""

    __tablename__ = "sow_steps"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="sow_runs.id", index=True, nullable=False)
    order_index: int = Field(
        nullable=False, index=True, description="Sequential order of the step."
    )
    step_id: str | None = Field(
        default=None, description="Optional hierarchical identifier such as '1.2'."
    )
    phase: str | None = Field(
        default=None, description="Lifecycle phase tag supplied by the LLM (Design/FAT/etc)."
    )
    label: str | None = Field(
        default=None, description="Optional human-friendly label such as 'Step 1.1'."
    )
    title: str = Field(nullable=False, description="Short name describing the step.")
    description: str = Field(
        sa_column=Column(Text, nullable=False),
        description="Detailed description copied from the document.",
    )
    actor: str | None = Field(
        default=None, description="Responsible party or stakeholder for the step."
    )
    location: str | None = Field(
        default=None, description="Location where the step takes place."
    )
    inputs: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Comma or newline separated list of inputs referenced by the step.",
    )
    outputs: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Comma or newline separated list of outputs referenced by the step.",
    )
    dependencies: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Free-text reference to prerequisite steps or conditions.",
    )
    header_section_key: str | None = Field(
        default=None,
        description="Section key associated with the paragraph that sourced this step.",
    )
    source_section_title: str | None = Field(
        default=None,
        description="Free-text label describing the originating section title.",
    )
    start_page: int | None = Field(
        default=None,
        description="Optional page number marking where the referenced span starts.",
    )
    end_page: int | None = Field(
        default=None,
        description="Optional page number marking where the referenced span ends.",
    )
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)


__all__ = ["SOWRun", "SOWStep"]

