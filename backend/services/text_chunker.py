"""Helpers for slicing long documents into LLM-sized text chunks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(slots=True)
class TextChunk:
    """Simple container describing a single chunk of document text."""

    index: int
    total: int
    text: str


def approximate_token_count(text: str) -> int:
    """Return a coarse token estimate assuming ~4 characters per token."""

    if not text:
        return 0
    length = len(text)
    return max(1, length // 4)


def chunk_text_for_llm(full_text: str, max_context_tokens: int) -> List[TextChunk]:
    """Split ``full_text`` into roughly ``max_context_tokens``-sized pieces."""

    if max_context_tokens <= 0:
        raise ValueError("max_context_tokens must be positive")

    if not full_text:
        return []

    max_chars = max_context_tokens * 4
    chunks: list[TextChunk] = []
    start = 0
    index = 0
    total_length = len(full_text)

    while start < total_length:
        end = min(start + max_chars, total_length)
        index += 1
        chunk_text = full_text[start:end]
        chunks.append(TextChunk(index=index, total=0, text=chunk_text))
        start = end

    total_chunks = len(chunks)
    for chunk in chunks:
        chunk.total = total_chunks

    return chunks


__all__ = ["TextChunk", "approximate_token_count", "chunk_text_for_llm"]
