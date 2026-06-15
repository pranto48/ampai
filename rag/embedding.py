# rag/embedding.py
"""Embedding utilities for the RAG pipeline.

This module provides a simple wrapper around the `sentence-transformers`
library to generate dense vector embeddings for arbitrary text. The model
can be preloaded at startup to avoid runtime overhead.
"""

import asyncio
from typing import List

# Lazy singleton pattern for the model
_model = None
_embedding_semaphore = asyncio.Semaphore(2)


def _load_model():
    """Load the sentence‑transformers model.

    Returns:
        SentenceTransformer: The loaded model instance.
    """
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise RuntimeError(
                "sentence-transformers is not installed. Install it via 'pip install sentence-transformers'."
            ) from e
        # Using a compact, high‑speed model suitable for production.
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def preload_model():
    """Preload the sentence-transformers model into memory."""
    _load_model()


def _get_text_embedding_sync(text: str) -> List[float]:
    model = _load_model()
    # The model returns a NumPy array; convert to plain list for JSON / DB compatibility.
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def _get_batch_embeddings_sync(texts: List[str]) -> List[List[float]]:
    model = _load_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return [vec.tolist() for vec in embeddings]


async def get_text_embedding(text: str) -> List[float]:
    """Generate an embedding for a single piece of text asynchronously.

    Args:
        text: The input string to embed.

    Returns:
        List[float]: A 384‑dimensional float vector.
    """
    if not text:
        return []
    async with _embedding_semaphore:
        return await asyncio.to_thread(_get_text_embedding_sync, text)


async def get_batch_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a batch of strings asynchronously.

    Args:
        texts: A list of strings.

    Returns:
        List[List[float]]: List of embedding vectors.
    """
    if not texts:
        return []
    async with _embedding_semaphore:
        return await asyncio.to_thread(_get_batch_embeddings_sync, texts)
