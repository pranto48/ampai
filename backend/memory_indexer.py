import math
import os
import threading
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.documents import Document
from langchain_postgres import PGVector
from sqlalchemy import text

from database import DATABASE_URL, engine, get_config


EMBED_CACHE_TTL_SECONDS = int(os.getenv("MEMORY_EMBED_CACHE_TTL_SECONDS", "300") or "300")
CANDIDATE_PREFILTER_LIMIT = 50


def get_embedding_model(model_type: str = "ollama"):
    if model_type == "openai":
        from langchain_openai import OpenAIEmbeddings

        key = get_config("openai_api_key") or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OpenAI API key missing for embeddings")
        return OpenAIEmbeddings(api_key=key)
    elif model_type == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        key = get_config("gemini_api_key") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ValueError("Google API key missing for embeddings")
        return GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=key)
    else:
        # Default to Ollama nomic-embed-text for local indexing
        from langchain_community.embeddings import OllamaEmbeddings

        base_url = get_config("ollama_base_url") or os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        return OllamaEmbeddings(model="nomic-embed-text", base_url=base_url)


class MemoryIndexer:
    _embed_cache: Dict[str, Tuple[float, List[float]]] = {}
    _cache_lock = threading.Lock()

    def __init__(self, model_type: str = "ollama"):
        self.last_retrieval_stats: Dict[str, Any] = {
            "pipeline": "vector_only",
            "latency_ms": 0,
            "prefilter_count": 0,
            "rerank_count": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }
        try:
            self.embedding_model = get_embedding_model(model_type)
            self.vectorstore = PGVector(
                embeddings=self.embedding_model,
                collection_name="chat_memory",
                connection=DATABASE_URL,
                use_jsonb=True,
            )
            self.enabled = True
        except Exception as e:
            print(f"Memory Indexer Disabled (PGVector initialization failed): {e}")
            self.enabled = False

    def _cache_key(self, namespace: str, value: str) -> str:
        return f"{namespace}:{(value or '').strip().lower()}"

    def _get_cached_embedding(self, key: str) -> Optional[List[float]]:
        now = perf_counter()
        with self._cache_lock:
            item = self._embed_cache.get(key)
            if not item:
                return None
            inserted_at, embedding = item
            if now - inserted_at > EMBED_CACHE_TTL_SECONDS:
                self._embed_cache.pop(key, None)
                return None
            return embedding

    def _set_cached_embedding(self, key: str, embedding: List[float]) -> None:
        with self._cache_lock:
            self._embed_cache[key] = (perf_counter(), embedding)

    def _cosine_similarity(self, left: List[float], right: List[float]) -> float:
        if not left or not right or len(left) != len(right):
            return -1.0
        dot = sum((a * b) for a, b in zip(left, right))
        left_norm = math.sqrt(sum((a * a) for a in left))
        right_norm = math.sqrt(sum((b * b) for b in right))
        if left_norm == 0 or right_norm == 0:
            return -1.0
        return dot / (left_norm * right_norm)

    def _hybrid_enabled(self) -> bool:
        env_val = (os.getenv("MEMORY_HYBRID_RETRIEVAL_ENABLED", "") or "").strip().lower()
        if env_val:
            return env_val in {"1", "true", "yes", "on"}
        cfg_val = (get_config("memory_hybrid_retrieval_enabled", "false") or "false").strip().lower()
        return cfg_val in {"1", "true", "yes", "on"}

    def add_fact(self, fact: str):
        if not self.enabled:
            return
        try:
            doc = Document(
                page_content=fact,
                metadata={
                    "type": "distilled_fact",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            self.vectorstore.add_documents([doc])
        except Exception as e:
            print(f"PGVector Add Error: {e}")

    def _prefilter_memory_candidates(
        self,
        query: str,
        *,
        username: Optional[str],
        status: Optional[str],
        category_filter: Optional[str],
        date_from: Optional[str],
        date_to: Optional[str],
        limit: int = CANDIDATE_PREFILTER_LIMIT,
    ) -> List[Dict[str, Any]]:
        if not engine:
            return []

        where_parts = ["mc.candidate_text IS NOT NULL", "mc.candidate_text <> ''"]
        params: Dict[str, Any] = {
            "query": (query or "").strip(),
            "limit": max(1, min(int(limit), 200)),
        }
        if username:
            where_parts.append("mc.username = :username")
            params["username"] = username
        if status:
            where_parts.append("mc.status = :status")
            params["status"] = status
        if category_filter:
            where_parts.append("COALESCE(sm.category, 'Uncategorized') = :category")
            params["category"] = category_filter
        if date_from:
            where_parts.append("mc.created_at >= :date_from")
            params["date_from"] = date_from
        if date_to:
            where_parts.append("mc.created_at <= :date_to")
            params["date_to"] = date_to

        sql = text(
            f"""
            SELECT
                mc.id,
                mc.username,
                mc.session_id,
                mc.candidate_text,
                mc.status,
                mc.created_at,
                COALESCE(sm.category, 'Uncategorized') AS category,
                ts_rank_cd(to_tsvector('simple', mc.candidate_text), plainto_tsquery('simple', :query)) AS lex_rank
            FROM memory_candidates mc
            LEFT JOIN session_metadata sm ON sm.session_id = mc.session_id
            WHERE {' AND '.join(where_parts)}
            ORDER BY lex_rank DESC NULLS LAST, mc.created_at DESC, mc.id DESC
            LIMIT :limit
            """
        )
        with engine.begin() as conn:
            rows = conn.execute(sql, params).mappings().all()
        return [dict(r) for r in rows]

    def _rerank_candidates(self, query: str, candidates: List[Dict[str, Any]], k: int) -> Tuple[List[str], Dict[str, int]]:
        if not candidates:
            return [], {"cache_hits": 0, "cache_misses": 0}

        cache_hits = 0
        cache_misses = 0
        query_key = self._cache_key("query", query)
        query_embedding = self._get_cached_embedding(query_key)
        if query_embedding is None:
            cache_misses += 1
            query_embedding = self.embedding_model.embed_query(query)
            self._set_cached_embedding(query_key, query_embedding)
        else:
            cache_hits += 1

        scored: List[Tuple[float, str]] = []
        missing_texts: List[str] = []
        missing_keys: List[str] = []

        for row in candidates:
            fact = (row.get("candidate_text") or "").strip()
            if not fact:
                continue
            row_key = self._cache_key("row", f"{row.get('id')}::{fact}")
            emb = self._get_cached_embedding(row_key)
            if emb is None:
                cache_misses += 1
                missing_texts.append(fact)
                missing_keys.append(row_key)
                scored.append((float("nan"), fact))
            else:
                cache_hits += 1
                scored.append((self._cosine_similarity(query_embedding, emb), fact))

        if missing_texts:
            generated = self.embedding_model.embed_documents(missing_texts)
            cursor = 0
            for idx, (score, fact) in enumerate(scored):
                if not math.isnan(score):
                    continue
                emb = generated[cursor]
                key = missing_keys[cursor]
                self._set_cached_embedding(key, emb)
                scored[idx] = (self._cosine_similarity(query_embedding, emb), fact)
                cursor += 1

        ranked = [text_value for _score, text_value in sorted(scored, key=lambda item: item[0], reverse=True)[: max(1, k)]]
        return ranked, {"cache_hits": cache_hits, "cache_misses": cache_misses}

    def search_facts(
        self,
        query: str,
        k: int = 5,
        recency_bias: float = 0.0,
        category_filter: str = None,
        username: Optional[str] = None,
        status: str = "approved",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ):
        if not self.enabled:
            return []
        started = perf_counter()
        try:
            if self._hybrid_enabled():
                top_k = max(1, min(int(k or 5), 5))
                candidates = self._prefilter_memory_candidates(
                    query,
                    username=username,
                    status=status,
                    category_filter=category_filter,
                    date_from=date_from,
                    date_to=date_to,
                    limit=CANDIDATE_PREFILTER_LIMIT,
                )
                reranked, cache_stats = self._rerank_candidates(query, candidates, top_k)
                self.last_retrieval_stats = {
                    "pipeline": "hybrid_prefilter_semantic_rerank",
                    "latency_ms": int((perf_counter() - started) * 1000),
                    "prefilter_count": len(candidates),
                    "rerank_count": len(reranked),
                    "cache_hits": cache_stats.get("cache_hits", 0),
                    "cache_misses": cache_stats.get("cache_misses", 0),
                }
                if reranked:
                    return reranked

            search_filter = {"type": "distilled_fact"}
            if category_filter:
                search_filter["category"] = category_filter
            results = self.vectorstore.similarity_search(query, k=k, filter=search_filter)
            if recency_bias > 0:
                now = datetime.now(timezone.utc)

                def _sort_key(doc):
                    created_at = doc.metadata.get("created_at") if getattr(doc, "metadata", None) else None
                    if not created_at:
                        return 0.0
                    try:
                        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
                        return 1.0 / (1.0 + age_days)
                    except Exception:
                        return 0.0

                top_n = max(1, int(k))
                recency_sorted = sorted(results, key=_sort_key, reverse=True)
                keep_recent = int(round(top_n * recency_bias))
                keep_recent = max(0, min(top_n, keep_recent))
                blended = recency_sorted[:keep_recent] + [doc for doc in results if doc not in recency_sorted[:keep_recent]]
                results = blended[:top_n]

            self.last_retrieval_stats = {
                "pipeline": "vector_only",
                "latency_ms": int((perf_counter() - started) * 1000),
                "prefilter_count": 0,
                "rerank_count": len(results),
                "cache_hits": 0,
                "cache_misses": 0,
            }
            return [doc.page_content for doc in results]
        except Exception as e:
            print(f"PGVector Search Error: {e}")
            self.last_retrieval_stats = {
                "pipeline": "error",
                "latency_ms": int((perf_counter() - started) * 1000),
                "prefilter_count": 0,
                "rerank_count": 0,
                "cache_hits": 0,
                "cache_misses": 0,
            }
            return []
