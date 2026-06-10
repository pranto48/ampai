# rag/embedding_helpers.py
"""Convenient helpers for storing and searching embeddings in the RAG pipeline.

These functions orchestrate the chunker, embedding generator and the Chroma vector store.
"""

from typing import List, Tuple, Optional

from .chunker import recursive_character_splitter
from .embedding import get_batch_embeddings, get_text_embedding
from .vector_store import upsert_chunks, similarity_search


def store_embeddings(texts: List[str], source_file: Optional[str] = None) -> None:
    """Chunk the given texts, embed them, and upsert into the vector store.

    Args:
        texts: List of raw document strings.
        source_file: Optional identifier of the source file for metadata.
    """
    ids: List[str] = []
    chunks: List[str] = []
    metadatas: List[dict] = []
    for doc_index, text in enumerate(texts):
        doc_chunks = recursive_character_splitter(text)
        for chunk_index, chunk in enumerate(doc_chunks):
            chunk_id = f"{source_file or 'doc'}:{doc_index}:{chunk_index}"
            ids.append(chunk_id)
            chunks.append(chunk)
            meta: dict = {}
            if source_file:
                meta["source_file"] = source_file
            meta["chunk_index"] = chunk_index
            metadatas.append(meta)
    # Generate embeddings for all chunks
    embeddings = get_batch_embeddings(chunks)
    # Upsert into Chroma collection
    upsert_chunks(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)


def search_embeddings(query: str, top_k: int = 5) -> List[Tuple[str, str, dict]]:
    """Embed a query string and retrieve the most similar stored chunks.

    Returns a list of ``(id, document, metadata)`` tuples.
    """
    query_embedding = get_text_embedding(query)
    if not query_embedding:
        return []
    return similarity_search(query_embedding, top_k=top_k)
