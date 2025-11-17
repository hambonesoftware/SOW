"""Prompt builders for SOW process-step extraction."""

from __future__ import annotations

from .text_chunker import TextChunk


def build_sow_system_prompt() -> str:
    """Return the high-level system persona for the LLM."""

    return (
        "You are an expert industrial automation engineer. You read scopes of work "
        "and produce a linear, detailed list of process steps that describe the full "
        "system operation. Each step must represent a single action or short "
        "sequence and must be grounded in the provided text."
    )


def build_sow_user_prompt(chunk: TextChunk) -> str:
    """Return the chunk-specific user prompt."""

    header = (
        f"This is chunk {chunk.index} of {chunk.total} from a scope-of-work document.\n"
        "Carefully read the entire chunk and extract all industrial process steps "
        "(material flow, station operations, robot motions, operator actions, "
        "inspections, etc.).\n\n"
        "Return ONLY a JSON object with a top-level 'steps' array using this shape:\n"
        "{\n"
        "  \"steps\": [\n"
        "    {\n"
        "      \"id\": \"S1\",\n"
        "      \"order\": 1,\n"
        "      \"phase\": \"Receiving\",\n"
        "      \"label\": \"Step 1.1\",\n"
        "      \"title\": \"Receive customer components\",\n"
        "      \"description\": \"Operators unload pallets...\",\n"
        "      \"source_page_start\": 3,\n"
        "      \"source_page_end\": 3,\n"
        "      \"source_section_title\": \"System Overview\"\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Each step must be a single row in 'steps'.\n"
        "- 'order' is local to this chunk; use sequential integers.\n"
        "- 'phase' is optional short text (Receiving, Assembly, Inspection, etc.).\n"
        "- 'label' is optional, e.g., 'Step 1.1'.\n"
        "- 'title' is a one-line summary.\n"
        "- 'description' can be multiple sentences copied from the text.\n"
        "- Page numbers may be approximate or null if unknown.\n"
        "- Do NOT include any extra keys or wrap the JSON in markdown fences.\n\n"
        "Here is the chunk:\n\n"
    )
    return f"{header}{chunk.text}\n"


__all__ = ["build_sow_system_prompt", "build_sow_user_prompt"]
