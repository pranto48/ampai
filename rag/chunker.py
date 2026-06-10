# rag/chunker.py
"""Utilities for splitting documents into overlapping chunks for RAG.
The RecursiveCharacterTextSplitter mimics LangChain's implementation but is a lightweight
standalone version to avoid extra dependencies.
"""

from typing import List


def recursive_character_splitter(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split *text* into chunks of *chunk_size* characters with *overlap* characters overlap.

    Args:
        text: The input document text.
        chunk_size: Desired maximum size of each chunk.
        overlap: Number of characters that each chunk overlaps with the previous one.

    Returns:
        List of chunk strings.
    """
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end]
        chunks.append(chunk)
        # Move start forward by chunk_size - overlap to create overlapping windows
        start += chunk_size - overlap
    return chunks
