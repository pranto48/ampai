# rag/embedding.py
"""Embedding utilities for the RAG pipeline.

This module provides a simple wrapper around the `sentence-transformers`
library to generate dense vector embeddings for arbitrary text. The model
is loaded lazily on first use to avoid unnecessary overhead during server
startup.
"""

from typing import List

# Lazy singleton pattern for the model
_model = None


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


def get_text_embedding(text: str) -> List[float]:
    """Generate an embedding for a single piece of text.

    Args:
        text: The input string to embed.

    Returns:
        List[float]: A 384‑dimensional float vector.
    """
    if not text:
        return []
    model = _load_model()
    # The model returns a NumPy array; convert to plain list for JSON / DB compatibility.
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def get_batch_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a batch of strings.

    Args:
        texts: A list of strings.

    Returns:
        List[List[float]]: List of embedding vectors.
    """
    if not texts:
        return []
    model = _load_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return [vec.tolist() for vec in embeddings]
