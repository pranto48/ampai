# rag/vector_store.py
"""Vector store abstraction using ChromaDB.

The RAG pipeline stores document chunks and their embeddings in a persistent
Chroma collection. This module provides helper functions to upsert chunks and
perform similarity search.
"""

import os
from typing import List, Tuple

import chromadb
from chromadb.config import Settings

# Determine a persistent directory for the Chroma database inside the app data folder.
_CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "chroma")

# Initialise a singleton client.
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = chromadb.Client(
            Settings(
                persist_directory=_CHROMA_PERSIST_DIR,
                # Optional: reduce memory usage for large collections.
                anonymized_telemetry=False,
            )
        )
    return _client


def get_collection(name: str = "rag_documents"):
    """Retrieve (or create) a Chroma collection.

    Args:
        name: The collection name. Defaults to ``rag_documents``.
    """
    client = _get_client()
    try:
        return client.get_collection(name)
    except Exception:
        # If the collection does not exist, create it.
        return client.create_collection(name)


def upsert_chunks(
    ids: List[str],
    documents: List[str],
    embeddings: List[List[float]],
    metadatas: List[dict] | None = None,
    collection_name: str = "rag_documents",
) -> None:
    """Insert or update document chunks in the vector store.

    Parameters
    ----------
    ids:
        Unique identifiers for each chunk (e.g., ``f"{source_file}:{index}"``).
    documents:
        Raw text of each chunk.
    embeddings:
        Corresponding embedding vectors.
    metadatas:
        Optional list of metadata dictionaries (e.g., source file, page number).
    collection_name:
        Target collection name.
    """
    collection = get_collection(collection_name)
    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def similarity_search(
    query_embedding: List[float],
    top_k: int = 5,
    collection_name: str = "rag_documents",
) -> List[Tuple[str, str, dict]]:
    """Return the *top_k* most similar chunks for a query embedding.

    Returns a list of tuples ``(id, document, metadata)``.
    """
    collection = get_collection(collection_name)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )
    # Chroma returns lists inside a dict; unpack a single query.
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    return list(zip(ids, docs, metas))
