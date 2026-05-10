"""Recall router: FTS5 search, hybrid search, recall stats, and nudge curation."""

from __future__ import annotations

from core.deps import (
    UserContext,
    get_current_user_from_cookie,
    require_authenticated_user,
)
from core.models import (
    NudgeCurateTriggerRequest,
    RecallHybridSearchRequest,
    RecallQueryRequest,
    RecallSearchRequest,
)
from database import get_all_configs
from fastapi import APIRouter, Depends, HTTPException
from session_recall import (
    bulk_index_unindexed_sessions,
    get_fts_stats,
    search_recall,
    search_recall_hybrid,
    summarize_hits,
)

router = APIRouter(tags=["recall"])


# ── FTS search ────────────────────────────────────────────────────────────────


@router.post("/api/recall/search")
def recall_search(
    request: RecallSearchRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    hits = search_recall(
        query=request.q,
        username=user.username,
        session_id=request.session_id,
        limit=request.limit,
    )
    summary = summarize_hits(hits, max_items=5)
    return {"hits": hits, "summary": summary}


@router.post("/api/recall/hybrid-search")
def recall_hybrid_search(
    request: RecallHybridSearchRequest,
    user: UserContext = Depends(require_authenticated_user),
):
    configs = get_all_configs()
    enabled = str(
        configs.get("memory_hybrid_retrieval_enabled", "false")
    ).strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        raise HTTPException(
            status_code=400,
            detail="Hybrid recall is disabled. Set memory_hybrid_retrieval_enabled=true.",
        )
    hits = search_recall_hybrid(
        query=request.q,
        username=user.username,
        session_id=request.session_id,
        limit=request.limit,
        lexical_weight=request.lexical_weight,
        semantic_weight=request.semantic_weight,
        recency_weight=request.recency_weight,
    )
    summary = summarize_hits(hits, max_items=5)
    return {"hits": hits, "summary": summary, "hybrid_enabled": True}


@router.post("/api/recall/search", include_in_schema=False)
def api_recall_search(
    req: RecallQueryRequest,
    user: UserContext = Depends(get_current_user_from_cookie),
):
    """Extended search with optional LLM summarization."""
    hits = search_recall(query=req.query, username=user.username, limit=req.limit)
    summary = ""
    if req.use_llm and hits:
        try:
            from session_recall import llm_summarize_hits

            summary = llm_summarize_hits(hits, req.query, model_type=req.model_type)
        except Exception:
            summary = summarize_hits(hits)
    return {"hits": hits, "summary": summary, "count": len(hits)}


@router.get("/api/recall/stats")
def api_recall_stats(user: UserContext = Depends(get_current_user_from_cookie)):
    return get_fts_stats()


@router.post("/api/recall/reindex")
def api_recall_reindex(
    batch_size: int = 100,
    user: UserContext = Depends(get_current_user_from_cookie),
):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    stats = bulk_index_unindexed_sessions(batch_size=batch_size)
    return {"ok": True, "stats": stats}


# ── Nudge curation ────────────────────────────────────────────────────────────


@router.get("/api/nudges/pending")
def api_list_nudges(
    limit: int = 20,
    user: UserContext = Depends(get_current_user_from_cookie),
):
    from memory_curator import list_pending_nudges

    return list_pending_nudges(user.username, limit=limit)


@router.post("/api/nudges/{nudge_id}/accept")
def api_accept_nudge(
    nudge_id: int, user: UserContext = Depends(get_current_user_from_cookie)
):
    from memory_curator import accept_nudge

    fact = accept_nudge(nudge_id, user.username)
    if fact is None:
        raise HTTPException(
            status_code=404, detail="Nudge not found or already reviewed"
        )
    return {"ok": True, "saved_fact": fact}


@router.post("/api/nudges/{nudge_id}/dismiss")
def api_dismiss_nudge(
    nudge_id: int, user: UserContext = Depends(get_current_user_from_cookie)
):
    from memory_curator import dismiss_nudge

    ok = dismiss_nudge(nudge_id, user.username)
    return {"ok": ok}


@router.post("/api/nudges/curate")
def api_trigger_curation(
    req: NudgeCurateTriggerRequest,
    user: UserContext = Depends(get_current_user_from_cookie),
):
    from memory_curator import curate_session, run_scheduled_curation

    if req.session_id:
        facts = curate_session(
            session_id=req.session_id,
            username=user.username,
            model_type=req.model_type,
            dry_run=req.dry_run,
        )
        return {"ok": True, "facts": facts, "nudges_created": len(facts)}
    else:
        stats = run_scheduled_curation(model_type=req.model_type)
        return {"ok": True, "stats": stats}
