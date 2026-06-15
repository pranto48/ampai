# tests/test_rag_flow.py
"""Integration test for the full RAG pipeline.

The test exercises the end‑to‑end flow:
1. Store embeddings for a couple of documents using ``store_embeddings``.
2. Perform a similarity search with a query that should match one of the stored chunks.
3. Verify that the returned results contain the expected metadata (source_file and chunk_index).

The test uses a temporary directory for the Chroma persistence to avoid polluting the
project data folder. It also runs against an in‑memory SQLite database for any
SQLAlchemy interactions (even though the current integration does not hit the DB).
"""

import os
import tempfile

import pytest

# Import the helpers after we can monkey‑patch the persistence directory
from rag import embedding_helpers
from rag.vector_store import _CHROMA_PERSIST_DIR, get_collection


@pytest.mark.asyncio
async def test_rag_end_to_end(tmp_path: "pathlib.Path"):
    # Override the Chroma persistence directory to a temporary location
    # The vector_store module reads the constant at import time, so we monkey‑patch it.
    # Note: we need to re‑initialise the client after changing the directory.
    from rag import vector_store as vs
    vs._CHROMA_PERSIST_DIR = str(tmp_path)
    # Reset the singleton client to force re‑creation with the new path
    vs._client = None

    # Prepare sample documents
    docs = [
        "Python is a popular programming language. It is used for web development, data science, and automation.",
        "The quick brown fox jumps over the lazy dog. This sentence contains every letter of the English alphabet.",
    ]
    source_name = "sample_doc.txt"

    # Store embeddings asynchronously
    await embedding_helpers.store_embeddings(docs, source_file=source_name)

    # Perform a search that should match the first document (keyword "web development")
    results = await embedding_helpers.search_embeddings("web development", top_k=3)

    # Verify that we get at least one result and that metadata includes our source file
    assert results, "No results returned from similarity search"
    ids, documents, metadatas = zip(*results)
    # At least one of the returned documents should contain the phrase "web development"
    assert any("web development" in doc.lower() for doc in documents)
    # All metadata dicts should contain the source_file key we provided
    for meta in metadatas:
        assert meta.get("source_file") == source_name
        assert "chunk_index" in meta

    # Clean up the collection to avoid interference with other tests
    collection = get_collection()
    collection.delete(ids=list(ids))
