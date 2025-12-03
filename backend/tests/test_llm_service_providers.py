from __future__ import annotations

from pathlib import Path

import pytest

from backend.config import Settings
from backend.services.llm import (
    LLMProviderError,
    LLMTransportRequest,
    LLMTransportResponse,
    LLMService,
)


def test_generate_returns_first_successful_provider(tmp_path: Path) -> None:
    calls: list[str] = []

    def primary(request: LLMTransportRequest) -> LLMTransportResponse:  # noqa: ANN001
        calls.append(f"primary:{request.model}")
        return LLMTransportResponse(content="primary-success", usage=None, raw=None)

    def secondary(request: LLMTransportRequest) -> LLMTransportResponse:  # noqa: ANN001
        calls.append(f"secondary:{request.model}")
        raise AssertionError("Secondary provider should not be called")

    settings = Settings(
        llm_provider="primary,secondary",
        openrouter_api_key="sk-test",
        upload_dir=tmp_path,
    )
    llm = LLMService(
        settings=settings,
        transport_overrides={"primary": primary, "secondary": secondary},
    )

    result = llm.generate(messages=[{"role": "user", "content": "hi"}])

    assert result.content == "primary-success"
    assert calls == ["primary:openrouter/auto"]


def test_generate_raises_after_all_providers_fail(tmp_path: Path) -> None:
    calls: list[str] = []

    def failing(request: LLMTransportRequest) -> LLMTransportResponse:  # noqa: ANN001
        calls.append(request.model)
        raise LLMProviderError("boom")

    settings = Settings(
        llm_provider="first,second",
        openrouter_api_key="sk-test",
        upload_dir=tmp_path,
    )
    llm = LLMService(
        settings=settings,
        transport_overrides={"first": failing, "second": failing},
    )

    with pytest.raises(LLMProviderError):
        llm.generate(messages=[{"role": "user", "content": "hi"}])

    assert calls == ["openrouter/auto", "openrouter/auto"]
