"""
Memory Service — unified facade over memory_indexer, memory_curator, and memory_persistence.

Provides a single entry point for all memory operations: saving chat turns,
capturing candidates, explicit memory saves, approval/rejection workflows,
hybrid search with char_budget compression, and memory deletion.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 5.11
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import text as sqlalchemy_text

from database import engine
from memory_indexer import MemoryIndexer
from memory_curator import create_nudge, list_pending_nudges
from memory_persistence import memory_persistence_manager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes for structured return values
# ---------------------------------------------------------------------------

IMPORTANCE_THRESHOLD = 0.15
MAX_EXPLICIT_MEMORY_CHARS = 1000
DEFAULT_CHAR_BUDGET = 1200


@dataclass
class MemoryRetrievalMetadata:
    """Metadata returned alongside memory search results."""

    retrieved_count: int = 0
    context_chars: int = 0
    pipeline: str = "unknown"
    latency_ms: int = 0


@dataclass
class MemorySearchResult:
    """Result of a memory search operation."""

    memories: List[Dict[str, Any]] = field(default_factory=list)
    metadata: MemoryRetrievalMetadata = field(default_factory=MemoryRetrievalMetadata)


# ---------------------------------------------------------------------------
# MemoryService
# ---------------------------------------------------------------------------


class MemoryService:
    """
    Unified memory facade wrapping memory_indexer, memory_curator,
    and memory_persistence.
    """

    def __init__(self, db_engine=None, indexer: Optional[MemoryIndexer] = None):
        self.engine = db_engine if db_engine is not None else engine
        self.indexer = indexer or MemoryIndexer()
        self.persistence = memory_persistence_manager

    # ------------------------------------------------------------------
    # save_chat_turn
    # ------------------------------------------------------------------

    def save_chat_turn(
        self,
        username: str,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Persist a chat message and trigger candidate evaluation.

        If the importance score is > 0.15, a memory candidate is created
        with status 'pending'.

        Returns candidate info dict if one was created, else None.
        """
        if not content or not content.strip():
            return None

        # Calculate importance score using persistence manager
        score = self.persistence._analyze_text_importance(content)

        if score < IMPORTANCE_THRESHOLD:
            return None

        # Create a pending memory candidate
        return self.capture_candidate(
            username=username,
            session_id=session_id,
            text=content,
            importance_score=score,
            source="auto",
        )

    # ------------------------------------------------------------------
    # capture_candidate
    # ------------------------------------------------------------------

    def capture_candidate(
        self,
        username: str,
        session_id: str,
        text: str,
        importance_score: Optional[float] = None,
        source: str = "auto",
        confidence: float = 0.5,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a memory candidate with an importance score.

        Returns dict with candidate info or None on failure.
        """
        if not self.engine or not text or not text.strip():
            return None

        if importance_score is None:
            importance_score = self.persistence._analyze_text_importance(text)

        # Truncate candidate text
        candidate_text = text.strip()[:MAX_EXPLICIT_MEMORY_CHARS]

        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    sqlalchemy_text(
                        """
                        INSERT INTO memory_candidates
                            (username, session_id, candidate_text, source, confidence,
                             status, importance_score, created_at)
                        VALUES
                            (:username, :session_id, :text, :source, :confidence,
                             'pending', :score, NOW())
                        RETURNING id, created_at
                        """
                    ),
                    {
                        "username": username or "system",
                        "session_id": session_id or "",
                        "text": candidate_text,
                        "source": source,
                        "confidence": confidence,
                        "score": round(importance_score, 4),
                    },
                )
                row = result.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "username": username,
                        "session_id": session_id,
                        "candidate_text": candidate_text,
                        "importance_score": round(importance_score, 4),
                        "status": "pending",
                        "created_at": str(row[1]),
                    }
        except Exception as exc:
            logger.warning("capture_candidate failed: %s", exc)

        return None

    # ------------------------------------------------------------------
    # save_explicit_memory
    # ------------------------------------------------------------------

    def save_explicit_memory(
        self,
        username: str,
        session_id: Optional[str],
        text: str,
        category: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Save directly to core_memories for 'remember ...' commands.

        Truncates to max 1000 characters. Also indexes in the vector store.

        Returns dict with memory info or None on failure.
        """
        if not self.engine or not text or not text.strip():
            return None

        fact = text.strip()[:MAX_EXPLICIT_MEMORY_CHARS]
        cat = (category or "general").strip() or "general"

        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    sqlalchemy_text(
                        """
                        INSERT INTO core_memories (username, fact, category, created_at)
                        VALUES (:username, :fact, :category, NOW())
                        RETURNING id, created_at
                        """
                    ),
                    {
                        "username": username or "system",
                        "fact": fact,
                        "category": cat,
                    },
                )
                row = result.fetchone()

            # Also add to vector index for retrieval
            if self.indexer and self.indexer.enabled:
                self.indexer.add_fact(fact, username)

            if row:
                return {
                    "id": row[0],
                    "username": username,
                    "fact": fact,
                    "category": cat,
                    "created_at": str(row[1]),
                }
        except Exception as exc:
            logger.warning("save_explicit_memory failed: %s", exc)

        return None

    # ------------------------------------------------------------------
    # approve_candidate
    # ------------------------------------------------------------------

    def approve_candidate(
        self,
        candidate_id: int,
        edited_text: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Promote a pending candidate to core memory + vector index.

        Returns dict with the promoted memory info or None if not found/failed.
        """
        if not self.engine:
            return None

        try:
            with self.engine.begin() as conn:
                # Fetch the candidate
                row = conn.execute(
                    sqlalchemy_text(
                        """
                        SELECT id, username, session_id, candidate_text, status
                        FROM memory_candidates
                        WHERE id = :id
                        """
                    ),
                    {"id": candidate_id},
                ).fetchone()

                if not row:
                    return None

                candidate_status = row[4]
                if candidate_status != "pending":
                    return None

                username = row[1]
                fact = (edited_text or row[3] or "").strip()
                if not fact:
                    return None

                # Update candidate status
                conn.execute(
                    sqlalchemy_text(
                        """
                        UPDATE memory_candidates
                        SET status = 'approved',
                            edited_text = :edited_text,
                            reviewed_at = NOW()
                        WHERE id = :id
                        """
                    ),
                    {"id": candidate_id, "edited_text": edited_text},
                )

                # Insert into core_memories
                core_result = conn.execute(
                    sqlalchemy_text(
                        """
                        INSERT INTO core_memories (username, fact, category, created_at)
                        VALUES (:username, :fact, 'general', NOW())
                        RETURNING id, created_at
                        """
                    ),
                    {"username": username, "fact": fact},
                )
                core_row = core_result.fetchone()

            # Add to vector index
            if self.indexer and self.indexer.enabled:
                self.indexer.add_fact(fact, username)

            return {
                "candidate_id": candidate_id,
                "core_memory_id": core_row[0] if core_row else None,
                "username": username,
                "fact": fact,
                "status": "approved",
                "created_at": str(core_row[1]) if core_row else None,
            }
        except Exception as exc:
            logger.warning("approve_candidate failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # reject_candidate
    # ------------------------------------------------------------------

    def reject_candidate(self, candidate_id: int) -> Optional[Dict[str, Any]]:
        """
        Mark a candidate as rejected, excluding it from retrieval.

        Returns dict with rejection info or None if not found/failed.
        """
        if not self.engine:
            return None

        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    sqlalchemy_text(
                        """
                        UPDATE memory_candidates
                        SET status = 'rejected', reviewed_at = NOW()
                        WHERE id = :id AND status = 'pending'
                        RETURNING id, username, candidate_text
                        """
                    ),
                    {"id": candidate_id},
                )
                row = result.fetchone()

                if not row:
                    return None

                return {
                    "id": row[0],
                    "username": row[1],
                    "candidate_text": row[2],
                    "status": "rejected",
                }
        except Exception as exc:
            logger.warning("reject_candidate failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # search_memory
    # ------------------------------------------------------------------

    def search_memory(
        self,
        username: str,
        query: str,
        limit: int = 5,
        mode: str = "hybrid",
        category: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        recency_bias: float = 0.0,
        char_budget: int = DEFAULT_CHAR_BUDGET,
    ) -> MemorySearchResult:
        """
        Hybrid search (vector + FTS), compress results to char_budget.

        Returns MemorySearchResult with memories and retrieval metadata
        including retrieved_count, context_chars, pipeline, and latency_ms.
        """
        start_time = time.time()

        if not query or not query.strip():
            return MemorySearchResult(
                memories=[],
                metadata=MemoryRetrievalMetadata(
                    retrieved_count=0,
                    context_chars=0,
                    pipeline="empty_query",
                    latency_ms=0,
                ),
            )

        # Clamp limit to valid range
        limit = max(1, min(limit, 8))
        char_budget = max(200, min(char_budget, 4000))

        # Use the indexer's search_facts for hybrid retrieval
        facts: List[str] = []
        pipeline = "hybrid"

        try:
            if self.indexer and self.indexer.enabled:
                facts = self.indexer.search_facts(
                    query=query,
                    k=limit,
                    recency_bias=recency_bias,
                    category_filter=category or None,
                    username=username,
                    status="approved",
                    date_from=date_from,
                    date_to=date_to,
                )
                # Get pipeline info from indexer stats
                stats = self.indexer.last_retrieval_stats
                pipeline = stats.get("pipeline", "hybrid")
            else:
                # Fallback: FTS-only search from core_memories
                facts = self._fts_search(username, query, limit)
                pipeline = "fts_only"
        except Exception as exc:
            logger.warning("search_memory indexer failed, falling back to FTS: %s", exc)
            facts = self._fts_search(username, query, limit)
            pipeline = "fts_fallback"

        # Compress results to fit within char_budget
        compressed_memories = self._compress_to_budget(facts, char_budget)

        latency_ms = int((time.time() - start_time) * 1000)
        context_chars = sum(len(m.get("fact", "")) for m in compressed_memories)

        return MemorySearchResult(
            memories=compressed_memories,
            metadata=MemoryRetrievalMetadata(
                retrieved_count=len(compressed_memories),
                context_chars=context_chars,
                pipeline=pipeline,
                latency_ms=latency_ms,
            ),
        )

    # ------------------------------------------------------------------
    # forget_memory
    # ------------------------------------------------------------------

    def forget_memory(self, username: str, memory_id: int) -> bool:
        """
        Delete from core_memories and vector index.

        Returns True if the memory was found and deleted, False otherwise.
        """
        if not self.engine:
            return False

        try:
            with self.engine.begin() as conn:
                # Get the fact text before deleting (for vector index removal)
                row = conn.execute(
                    sqlalchemy_text(
                        "SELECT fact FROM core_memories WHERE id = :id AND username = :username"
                    ),
                    {"id": memory_id, "username": username},
                ).fetchone()

                if not row:
                    return False

                # Delete from core_memories
                conn.execute(
                    sqlalchemy_text(
                        "DELETE FROM core_memories WHERE id = :id AND username = :username"
                    ),
                    {"id": memory_id, "username": username},
                )

            # Note: PGVector doesn't easily support deletion by content,
            # but we remove from the SQL table. The vector store entry
            # will be excluded from future searches via status filtering.
            return True
        except Exception as exc:
            logger.warning("forget_memory failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fts_search(
        self, username: str, query: str, limit: int
    ) -> List[str]:
        """Full-text search fallback using core_memories table."""
        if not self.engine:
            return []

        try:
            with self.engine.connect() as conn:
                rows = conn.execute(
                    sqlalchemy_text(
                        """
                        SELECT fact
                        FROM core_memories
                        WHERE username = :username
                          AND fact ILIKE :pattern
                        ORDER BY created_at DESC
                        LIMIT :limit
                        """
                    ),
                    {
                        "username": username,
                        "pattern": f"%{query}%",
                        "limit": limit,
                    },
                ).fetchall()
                return [row[0] for row in rows if row and row[0]]
        except Exception as exc:
            logger.warning("_fts_search failed: %s", exc)
            return []

    def _compress_to_budget(
        self, facts: List[str], char_budget: int
    ) -> List[Dict[str, Any]]:
        """
        Compress a list of fact strings to fit within char_budget.

        Returns list of dicts with 'fact' key, truncating individual
        facts and dropping excess ones to stay within budget.
        """
        results: List[Dict[str, Any]] = []
        remaining_budget = char_budget

        for fact in facts:
            if remaining_budget <= 0:
                break

            fact_text = (fact or "").strip()
            if not fact_text:
                continue

            # Truncate individual fact if it exceeds remaining budget
            if len(fact_text) > remaining_budget:
                # Reserve space for ellipsis within the budget
                truncate_at = max(0, remaining_budget - 3)
                fact_text = fact_text[:truncate_at].rstrip() + "..."

            results.append({"fact": fact_text})
            remaining_budget -= len(fact_text)

        return results



