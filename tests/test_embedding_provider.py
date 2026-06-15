# tests/test_embedding_provider.py
"""Unit tests for the embedding utilities in the RAG pipeline.

These tests verify that the embedding functions return vectors of the expected
size and that batch processing works correctly.
"""

import pytest
from rag.embedding import get_text_embedding, get_batch_embeddings

@pytest.mark.asyncio
async def test_single_embedding_dimension():
    text = "The quick brown fox jumps over the lazy dog."
    embedding = await get_text_embedding(text)
    # The all-MiniLM-L6-v2 model produces 384‑dimensional vectors
    assert isinstance(embedding, list)
    assert len(embedding) == 384
    # Elements should be floats
    assert all(isinstance(v, float) for v in embedding)

@pytest.mark.asyncio
async def test_batch_embeddings_match_input_length():
    texts = ["first sentence", "second sentence", "third sentence"]
    batch = await get_batch_embeddings(texts)
    assert isinstance(batch, list)
    assert len(batch) == len(texts)
    for emb in batch:
        assert isinstance(emb, list)
        assert len(emb) == 384
        assert all(isinstance(v, float) for v in emb)
