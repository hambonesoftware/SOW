"""Pydantic schemas for the Scope of Work extraction API."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ProcessStep(BaseModel):
    """Single industrial process step extracted from the SOW."""

    id: str = Field(description="Stable identifier for the step.")
    order: int = Field(ge=1, description="Global order index across the document.")
    phase: Optional[str] = Field(
        default=None,
        description="Optional grouping such as phase, cell, or subsystem.",
    )
    label: Optional[str] = Field(
        default=None, description="Optional human-friendly label such as 'Step 1.1'."
    )
    title: str = Field(description="Short title describing the action.")
    description: str = Field(description="Detailed description of the action.")
    source_page_start: Optional[int] = Field(
        default=None, description="Approximate starting page for the step."
    )
    source_page_end: Optional[int] = Field(
        default=None, description="Approximate ending page for the step."
    )
    source_section_title: Optional[str] = Field(
        default=None, description="Section title or hint for the originating text."
    )


class SowRunRequest(BaseModel):
    """Options passed when requesting a new SOW extraction run."""

    model: Optional[str] = Field(
        default=None,
        description="Override the default LLM model name for this run.",
    )
    temperature: float = Field(
        default=0.1, ge=0.0, le=1.0, description="LLM sampling temperature."
    )
    max_context_tokens: int = Field(
        default=120_000,
        ge=1,
        description="Maximum context window used when chunking the document.",
    )
    trace: bool = Field(
        default=False,
        description="Reserved for future request tracing controls.",
    )


class SowRunResponse(BaseModel):
    """Response payload returned to the frontend after extraction."""

    document_id: int
    run_id: str
    model: str
    steps: List[ProcessStep]


__all__ = ["ProcessStep", "SowRunRequest", "SowRunResponse"]
