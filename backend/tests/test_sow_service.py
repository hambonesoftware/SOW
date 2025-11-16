from __future__ import annotations

import pytest

from backend.services.sow_extraction import SOWExtractionError, parse_sow_steps


def test_parse_sow_steps_normalises_payload() -> None:
    """LLM payloads should be normalised into deterministic step dictionaries."""

    payload = {
        "steps": [
            {
                "order_index": "2",
                "title": "Install PLC code",
                "description": "",
                "phase": "Build",
                "actor": "Integrator",
                "header_section_key": "sequence::20",
                "start_page": "5",
                "end_page": 6,
            },
            {
                "step_id": "1",
                "title": "Gather requirements",
                "description": "Gather requirements",
            },
        ]
    }

    steps = parse_sow_steps(payload)

    assert steps[0]["order_index"] == 1
    assert steps[0]["title"] == "Gather requirements"
    assert steps[0]["description"] == "Gather requirements"
    assert steps[0]["step_id"] == "1"

    assert steps[1]["order_index"] == 2
    assert steps[1]["title"] == "Install PLC code"
    assert steps[1]["description"] == "Install PLC code"
    assert steps[1]["phase"] == "Build"
    assert steps[1]["actor"] == "Integrator"
    assert steps[1]["header_section_key"] == "sequence::20"
    assert steps[1]["start_page"] == 5
    assert steps[1]["end_page"] == 6


def test_parse_sow_steps_requires_non_empty_array() -> None:
    """Missing or empty ``steps`` arrays should raise a descriptive error."""

    with pytest.raises(SOWExtractionError):
        parse_sow_steps({"steps": []})

    with pytest.raises(SOWExtractionError):
        parse_sow_steps({})
