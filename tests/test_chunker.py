# tests/test_chunker.py
"""Unit tests for the recursive_character_splitter utility used in the RAG pipeline.

The tests verify that:
- The function splits text into the expected number of chunks.
- Overlap between consecutive chunks is handled correctly.
- Edge‑cases such as empty input or invalid parameters raise appropriate errors.
"""

import pytest
from rag.chunker import recursive_character_splitter


def test_basic_chunking():
    text = "abcdefghijklmnopqrstuvwxyz" * 10  # 260 characters
    # chunk size 100, overlap 20 => expected 3 chunks: 0-100, 80-180, 160-260
    chunks = recursive_character_splitter(text, chunk_size=100, overlap=20)
    assert len(chunks) == 3
    # Verify that the overlapping region matches
    assert chunks[0][-20:] == chunks[1][:20]
    assert chunks[1][-20:] == chunks[2][:20]


def test_chunk_size_must_exceed_overlap():
    with pytest.raises(ValueError):
        recursive_character_splitter("hello world", chunk_size=50, overlap=60)


def test_empty_text_returns_empty_list():
    assert recursive_character_splitter("", chunk_size=100, overlap=20) == []


def test_single_chunk_when_text_shorter_than_chunk_size():
    text = "short text"
    chunks = recursive_character_splitter(text, chunk_size=100, overlap=20)
    assert len(chunks) == 1
    assert chunks[0] == text
