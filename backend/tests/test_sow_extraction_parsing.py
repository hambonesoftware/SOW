from __future__ import annotations

import json

import pytest

from backend.services.sow_extraction import _extract_sow_payload, SOWExtractionError


def _sample_payload() -> dict[str, object]:
    return {"steps": [{"title": "Do work", "description": "Do work"}]}


@pytest.mark.parametrize(
    "raw",
    [
        json.dumps(_sample_payload()),
        f"#sow#\n{json.dumps(_sample_payload())}\n#sow#",
        f"LLM response: {json.dumps(_sample_payload())}\n#sow# ignored #sow#",
        (
            "Here is your output:\n"
            + """{"steps": [{"title": "Do work", "description": "Do work"}]}"""
            + "\nThanks!"
        ),
    ],
)
def test_extract_sow_payload_accepts_json_variants(raw: str) -> None:
    payload = _extract_sow_payload(raw, chunk_index=1)
    assert isinstance(payload, dict)
    assert payload.get("steps")


def test_extract_sow_payload_rejects_invalid_json() -> None:
    with pytest.raises(SOWExtractionError):
        _extract_sow_payload("no json here", chunk_index=1)
