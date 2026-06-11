"""Chat router: POST /api/chat — the core conversation endpoint."""

from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from queue import Queue
from typing import Any, Dict, List

from agent import _extract_explicit_memory_request, chat_with_agent, chat_with_agent_stream
from core.deps import UserContext, require_authenticated_user
from core.helpers import (
    _append_session_suggestions,
    _create_memory_candidate,
    _ensure_session_owner_for_user,
    _get_memory_policy,
    _load_config_list,
    _load_session_suggestions,
    _save_config_list,
)
from core.models import ChatRequest
from database import (
    add_core_memory,
    ensure_session_owner,
    get_config,
    get_effective_chat_preferences,
    log_audit_event,
    persist_chat_message_metadata,
    touch_session,
)
from fastapi import APIRouter, Depends, HTTPException
from memory_indexer import MemoryIndexer
from session_recall import index_chat_turn

router = APIRouter(tags=["chat"])

logger = logging.getLogger("ampai")

# Shared insight queue — populated here; consumed by the insight worker in main.py
# We define it here to be importable, but main.py owns the worker thread.
INSIGHT_QUEUE: "Queue[str]" = Queue(maxsize=1000)


@router.post("/api/chat")
def chat(request: ChatRequest, user: UserContext = Depends(require_authenticated_user)):
    try:
        logger.info(
            "CHAT REQUEST model_type=%s, model_name=%s, memory_mode=%s, user=%s",
            request.model_type,
            request.model_name,
            request.memory_mode,
            user.username,
        )

        local_only_mode = str(
            get_config("local_only_mode", "false")
        ).strip().lower() in {"1", "true", "yes", "on"}
        if local_only_mode and (request.model_type or "").strip().lower() not in {
            "",
            "ollama",
            "generic",
            "anythingllm",
            "ampai_default",
        }:
            requested = (request.model_type or "").strip().lower() or "unknown"
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Provider '{requested}' is blocked by local_only_mode=true. "
                    "Disable local_only_mode in Admin Configs to use cloud providers like OpenRouter."
                ),
            )

        # Auto-resolve model_type
        effective_model_type = (request.model_type or "ollama").strip().lower()
        if effective_model_type == "ollama":
            configured_default = (get_config("default_model_provider") or get_config("model_provider") or "").strip().lower()
            if (
                configured_default
                and configured_default != "ollama"
                and not local_only_mode
            ):
                effective_model_type = configured_default
                request.model_name = None # Reset model name since we switched provider
                logger.info(
                    "Auto-resolved model_type from 'ollama' to configured default '%s'",
                    effective_model_type,
                )
            else:
                ollama_url = get_config("ollama_base_url") or os.getenv(
                    "OLLAMA_BASE_URL", "http://host.docker.internal:11434"
                )
                ollama_alive = False
                try:
                    import urllib.request as _ur

                    _ur.urlopen(ollama_url, timeout=2)
                    ollama_alive = True
                except Exception:
                    pass
                if not ollama_alive:
                    if local_only_mode:
                        effective_model_type = "ampai_default"
                        logger.info(
                            "Ollama unreachable in local-only mode — switching to ampai_default engine"
                        )
                    else:
                        provider_keys = [
                            ("openrouter", "openrouter_api_key"),
                            ("openai", "openai_api_key"),
                            ("gemini", "gemini_api_key"),
                            ("anthropic", "anthropic_api_key"),
                            ("generic", "generic_api_key"),
                        ]
                        resolved = False
                        for prov, key_name in provider_keys:
                            if get_config(key_name):
                                effective_model_type = prov
                                request.model_name = None # Reset model name since we switched provider
                                logger.info(
                                    "Ollama unreachable; auto-resolved model_type to '%s'",
                                    prov,
                                )
                                resolved = True
                                break
                        if not resolved:
                            effective_model_type = "ampai_default"
                            logger.info(
                                "No AI provider available — using built-in ampai_default engine"
                            )
        request.model_type = effective_model_type

        # ── AmpAI Default Mode ─────────────────────────────────────────────────
        if effective_model_type == "ampai_default":
            from ampai_default_engine import ampai_default_chat
            from database import get_core_memories

            _ensure_session_owner_for_user(request.session_id, user)
            core_mems = get_core_memories()
            default_result = ampai_default_chat(
                message=request.message,
                session_id=request.session_id,
                username=user.username,
                core_mems=core_mems,
            )
            if default_result.get(
                "memory_action"
            ) == "pending_approval" and default_result.get("memory_fact"):
                _create_memory_candidate(
                    user.username,
                    request.session_id,
                    default_result["memory_fact"],
                    confidence=0.75,
                )

            # Persist full message metadata for ampai_default mode
            try:
                tool_action_meta = {
                    "enable_browser_tools": request.enable_browser_tools,
                    "enable_terminal_tools": request.enable_terminal_tools,
                    "persona_id": request.persona_id,
                    "memory_mode": request.memory_mode,
                    "memory_top_k": request.memory_top_k,
                    "memory_recency_bias": request.memory_recency_bias,
                    "memory_category_filter": request.memory_category_filter or "",
                    "chat_output_mode": request.chat_output_mode,
                    "attachments_count": len(request.attachments),
                }
                persist_chat_message_metadata(
                    session_id=request.session_id,
                    username=user.username,
                    user_message=request.message or "",
                    assistant_response=str(default_result.get("response") or ""),
                    model_provider="ampai_default",
                    model_name=None,
                    memory_retrieval_metadata=default_result.get("retrieval") or {},
                    web_search_metadata=default_result.get("web_search") or {},
                    tool_action_metadata=tool_action_meta,
                )
            except Exception:
                logger.debug("chat metadata persistence failed for ampai_default (non-blocking)")

            # ── Task intent detection for ampai_default mode (Req 11.1) ───────
            default_task_suggestions = []
            default_has_task_cues = False
            try:
                from services.task_intent_service import process_chat_for_task_intent

                existing_suggestions = _load_session_suggestions(request.session_id)
                intent_suggestions = process_chat_for_task_intent(
                    message=request.message,
                    session_id=request.session_id,
                    username=user.username,
                    response_text=str(default_result.get("response") or ""),
                    existing_suggestions=existing_suggestions,
                )
                if intent_suggestions:
                    default_task_suggestions = _append_session_suggestions(
                        request.session_id, intent_suggestions
                    )
                    default_has_task_cues = True
            except Exception:
                logger.debug("task intent detection failed in ampai_default mode (non-blocking)")

            return {
                "response": default_result["response"],
                "web_search": default_result.get("web_search", {}),
                "task_suggestions": default_task_suggestions,
                "has_task_cues": default_has_task_cues,
                "retrieval": default_result.get("retrieval", {}),
                "memory_action": default_result.get("memory_action"),
                "memory_fact": default_result.get("memory_fact"),
                "memory_category": None,
                "skill_opportunity": None,
                "recall_used": False,
                "ampai_default_mode": True,
                "intent": default_result.get("intent_detected", "general"),
                "model_used": "AmpAI Built-in",
            }

        _ensure_session_owner_for_user(request.session_id, user)
        persona_prompt = ""
        if request.persona_id:
            personas = _load_config_list("personas_library")
            persona = next(
                (p for p in personas if p.get("id") == request.persona_id), None
            )
            if persona and persona.get("system_prompt"):
                persona_prompt = str(persona.get("system_prompt")).strip()
        message_for_agent = request.message
        if persona_prompt:
            message_for_agent = f"[Persona Instructions]\n{persona_prompt}\n\n[User Message]\n{request.message}"
        effective_chat_prefs = get_effective_chat_preferences(user.username)
        requested_mode = (request.chat_output_mode or "").strip().lower()
        if requested_mode not in {"compact", "normal"}:
            requested_mode = (
                str(effective_chat_prefs.get("chat_output_mode") or "normal")
                .strip()
                .lower()
            )
        if requested_mode not in {"compact", "normal"}:
            requested_mode = "normal"
        low_token_mode = bool(effective_chat_prefs.get("low_token_mode"))
        requested_memory_mode = (request.memory_mode or "").strip().lower()
        if requested_memory_mode not in {"indexed", "full"}:
            requested_memory_mode = "indexed"
        effective_memory_mode = (
            requested_memory_mode if user.role == "admin" else "indexed"
        )
        requested_top_k = (
            request.memory_top_k if request.memory_top_k is not None else 5
        )
        max_top_k = 3 if low_token_mode else 5
        clamped_top_k = max(1, min(max_top_k, int(requested_top_k or 5)))
        raw_recency_bias = (
            request.recency_bias
            if request.recency_bias is not None
            else request.memory_recency_bias
        )
        effective_recency_bias = float(
            raw_recency_bias if raw_recency_bias is not None else 0.6
        )
        effective_recency_bias = max(0.0, min(1.0, effective_recency_bias))
        category_filter_value = (
            request.category_filter or request.memory_category_filter or ""
        ).strip()
        policy = _get_memory_policy(user.username)
        explicit_save_fact = _extract_explicit_memory_request(request.message)
        result = chat_with_agent(
            session_id=request.session_id,
            message=message_for_agent,
            model_type=request.model_type,
            api_key=request.api_key,
            model_name=request.model_name,
            memory_mode=effective_memory_mode,
            memory_top_k=clamped_top_k,
            recency_bias=effective_recency_bias,
            category_filter=category_filter_value,
            use_web_search=request.use_web_search,
            attachments=[a.dict() for a in request.attachments],
            chat_output_mode=requested_mode,
            username=user.username,
            is_admin=(user.role == "admin"),
            allowed_memory_categories=policy.get("allowed_categories") or [],
            persist_memory=bool(policy.get("auto_capture_enabled", True)),
            require_memory_approval=bool(policy.get("require_approval", False)),
            pii_strict_mode=bool(policy.get("pii_strict_mode", False)),
            force_save=bool(explicit_save_fact),
        )
        memory_action = (result.get("memory_action") or "").strip().lower()
        memory_fact = (result.get("memory_fact") or "").strip()
        if memory_action == "pending_approval" and memory_fact:
            _create_memory_candidate(
                user.username, request.session_id, memory_fact, confidence=0.9
            )
        elif memory_action == "saved" and memory_fact:
            try:
                add_core_memory(memory_fact)
            except Exception:
                logger.exception("chat saved-memory core write failed")
            try:
                MemoryIndexer(request.model_type).add_fact(memory_fact)
            except Exception:
                logger.exception("chat saved-memory index write failed")

        response_text = str(result.get("response") or "")
        retrieval_meta = result.get("retrieval") or {}
        injected_chars = int(retrieval_meta.get("context_chars") or 0)
        injected_tokens = max(0, injected_chars // 4)
        log_audit_event(
            username=user.username,
            action="memory.read.injected",
            session_id=request.session_id,
            details=f"chars={injected_chars},tokens={injected_tokens},mode={effective_memory_mode}",
        )
        suggestions: List[Dict[str, Any]] = []
        for match in re.finditer(
            r"\[CREATE_TASK:\s*(.*?)\]", response_text, re.IGNORECASE | re.DOTALL
        ):
            raw = match.group(1)
            fields: Dict[str, str] = {}
            for part in raw.split("|"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    fields[k.strip().lower()] = v.strip()
            title = (fields.get("title") or "").strip()
            if not title:
                continue
            suggestion = {
                "id": str(uuid.uuid4()),
                "username": user.username,
                "session_id": request.session_id,
                "title": title[:200],
                "description": (fields.get("description") or "")[:1000],
                "priority": (fields.get("priority") or "medium").lower(),
                "due_at": fields.get("due") or None,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            suggestions.append(suggestion)
        if suggestions:
            all_suggestions = _load_config_list("task_suggestions")
            all_suggestions = suggestions + all_suggestions
            _save_config_list("task_suggestions", all_suggestions[:500])
            result["task_suggestions"] = suggestions
            cleaned = re.sub(
                r"\[CREATE_TASK:\s*.*?\]",
                "",
                response_text,
                flags=re.IGNORECASE | re.DOTALL,
            ).strip()
            result["response"] = cleaned or response_text

        # ── Task intent detection from user message (Req 11.1, 11.4, 11.5) ───
        if not suggestions:
            try:
                from services.task_intent_service import process_chat_for_task_intent

                existing_session_suggestions = _load_session_suggestions(request.session_id)
                intent_suggestions = process_chat_for_task_intent(
                    message=request.message,
                    session_id=request.session_id,
                    username=user.username,
                    response_text=response_text,
                    existing_suggestions=existing_session_suggestions,
                )
                if intent_suggestions:
                    result["task_suggestions"] = intent_suggestions
                    result["has_task_cues"] = True
            except Exception:
                logger.debug("task intent detection failed (non-blocking)")

        if policy.get("auto_capture_enabled") and policy.get("require_approval"):
            user_msg = (request.message or "").strip()
            _AUTO_CAPTURE_RE = re.compile(
                r"\b(remember|my name is|i('m| am)|i work|i live|born on|date of birth|"
                r"i prefer|i like|i love|i dislike|my role|my job|co-founder|founder|"
                r"chairman|ceo|cto|manager|freelancer|cybersecurity|developer|designer|"
                r"i founded|acting|organization|company|nationality|citizen|from (dhaka|bangladesh)|always|usually)\b",
                re.IGNORECASE,
            )
            if user_msg and _AUTO_CAPTURE_RE.search(user_msg):
                _create_memory_candidate(
                    user.username, request.session_id, user_msg, confidence=0.75
                )
        ensure_session_owner(request.session_id, user.username)
        touch_session(request.session_id)
        created_suggestions = _append_session_suggestions(
            request.session_id, result.get("task_suggestions") or []
        )
        result["task_suggestions"] = created_suggestions
        log_audit_event(
            username=user.username,
            action="memory.write.chat",
            session_id=request.session_id,
            details=f"model={request.model_type}",
        )
        if created_suggestions:
            log_audit_event(
                username=user.username,
                action="task.suggestion.detected",
                session_id=request.session_id,
                details=f"count={len(created_suggestions)}",
            )
        try:
            index_chat_turn(
                request.session_id,
                user.username,
                "user",
                request.message or "",
                tags="chat",
            )
            index_chat_turn(
                request.session_id,
                user.username,
                "assistant",
                str(result.get("response") or ""),
                tags="chat",
            )
        except Exception:
            logger.exception("session recall indexing failed")
        result["memory_status"] = {
            "memory_action": memory_action or None,
            "memory_fact": memory_fact or None,
            "memory_category": (result.get("memory_category") or None),
        }
        try:
            INSIGHT_QUEUE.put_nowait(request.session_id)
        except Exception:
            pass

        # ── Persist full message metadata per session (Req 4.4, 12.2) ─────────
        try:
            tool_action_meta = {
                "enable_browser_tools": request.enable_browser_tools,
                "enable_terminal_tools": request.enable_terminal_tools,
                "persona_id": request.persona_id,
                "memory_mode": effective_memory_mode,
                "memory_top_k": clamped_top_k,
                "memory_recency_bias": effective_recency_bias,
                "memory_category_filter": category_filter_value,
                "chat_output_mode": requested_mode,
                "attachments_count": len(request.attachments),
            }
            persist_chat_message_metadata(
                session_id=request.session_id,
                username=user.username,
                user_message=request.message or "",
                assistant_response=str(result.get("response") or ""),
                model_provider=request.model_type or effective_model_type,
                model_name=request.model_name,
                memory_retrieval_metadata=retrieval_meta,
                web_search_metadata=result.get("web_search") or {},
                tool_action_metadata=tool_action_meta,
            )
        except Exception:
            logger.debug("chat metadata persistence failed (non-blocking)")

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("chat failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/chat/stream")
async def chat_stream(request: ChatRequest, user: UserContext = Depends(require_authenticated_user)):
    from fastapi.responses import StreamingResponse
    import json
    import asyncio

    logger.info(
        "CHAT STREAM REQUEST model_type=%s, model_name=%s, memory_mode=%s, user=%s",
        request.model_type,
        request.model_name,
        request.memory_mode,
        user.username,
    )

    _ensure_session_owner_for_user(request.session_id, user)
    
    # Check local_only_mode
    local_only_mode = str(
        get_config("local_only_mode", "false")
    ).strip().lower() in {"1", "true", "yes", "on"}
    if local_only_mode and (request.model_type or "").strip().lower() not in {
        "",
        "ollama",
        "generic",
        "anythingllm",
        "ampai_default",
    }:
        requested = (request.model_type or "").strip().lower() or "unknown"
        raise HTTPException(
            status_code=400,
            detail=(
                f"Provider '{requested}' is blocked by local_only_mode=true. "
                "Disable local_only_mode in Admin Configs to use cloud providers like OpenRouter."
            ),
        )

    # Auto-resolve model_type
    effective_model_type = (request.model_type or "ollama").strip().lower()
    if effective_model_type == "ollama":
        configured_default = (get_config("default_model_provider") or get_config("model_provider") or "").strip().lower()
        if (
            configured_default
            and configured_default != "ollama"
            and not local_only_mode
        ):
            effective_model_type = configured_default
            request.model_name = None # Reset model name since we switched provider
        else:
            ollama_url = get_config("ollama_base_url") or os.getenv(
                "OLLAMA_BASE_URL", "http://host.docker.internal:11434"
            )
            ollama_alive = False
            try:
                import urllib.request as _ur
                _ur.urlopen(ollama_url, timeout=2)
                ollama_alive = True
            except Exception:
                pass
            if not ollama_alive:
                if local_only_mode:
                    effective_model_type = "ampai_default"
                else:
                    provider_keys = [
                        ("openrouter", "openrouter_api_key"),
                        ("openai", "openai_api_key"),
                        ("gemini", "gemini_api_key"),
                        ("anthropic", "anthropic_api_key"),
                        ("generic", "generic_api_key"),
                    ]
                    resolved = False
                    for prov, key_name in provider_keys:
                        if get_config(key_name):
                            effective_model_type = prov
                            request.model_name = None # Reset model name since we switched provider
                            resolved = True
                            break
                    if not resolved:
                        effective_model_type = "ampai_default"
    request.model_type = effective_model_type

    # If ampai_default, we run the built-in default engine
    if effective_model_type == "ampai_default":
        from ampai_default_engine import ampai_default_chat
        from database import get_core_memories
        
        async def default_stream_generator():
            core_mems = get_core_memories()
            default_result = ampai_default_chat(
                message=request.message,
                session_id=request.session_id,
                username=user.username,
                core_mems=core_mems,
            )
            
            # Persist and audit tasks
            if default_result.get("memory_action") == "pending_approval" and default_result.get("memory_fact"):
                _create_memory_candidate(
                    user.username,
                    request.session_id,
                    default_result["memory_fact"],
                    confidence=0.75,
                )
            
            response_text = default_result.get("response", "")
            # Yield initial token chunk to client
            chunk_size = 8
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i+chunk_size]
                yield f"data: {json.dumps({'type': 'token', 'token': chunk})}\n\n"
                await asyncio.sleep(0.01)

            # Persist chat metadata
            try:
                tool_action_meta = {
                    "enable_browser_tools": request.enable_browser_tools,
                    "enable_terminal_tools": request.enable_terminal_tools,
                    "persona_id": request.persona_id,
                    "memory_mode": request.memory_mode,
                    "memory_top_k": request.memory_top_k,
                    "memory_recency_bias": request.memory_recency_bias,
                    "memory_category_filter": request.memory_category_filter or "",
                    "chat_output_mode": request.chat_output_mode,
                    "attachments_count": len(request.attachments),
                }
                persist_chat_message_metadata(
                    session_id=request.session_id,
                    username=user.username,
                    user_message=request.message or "",
                    assistant_response=str(default_result.get("response") or ""),
                    model_provider="ampai_default",
                    model_name=None,
                    memory_retrieval_metadata=default_result.get("retrieval") or {},
                    web_search_metadata=default_result.get("web_search") or {},
                    tool_action_metadata=tool_action_meta,
                )
            except Exception:
                pass

            default_task_suggestions = []
            default_has_task_cues = False
            try:
                from services.task_intent_service import process_chat_for_task_intent
                existing_suggestions = _load_session_suggestions(request.session_id)
                intent_suggestions = process_chat_for_task_intent(
                    message=request.message,
                    session_id=request.session_id,
                    username=user.username,
                    response_text=str(default_result.get("response") or ""),
                    existing_suggestions=existing_suggestions,
                )
                if intent_suggestions:
                    default_task_suggestions = _append_session_suggestions(
                        request.session_id, intent_suggestions
                    )
                    default_has_task_cues = True
            except Exception:
                pass

            final_meta = {
                "web_search": default_result.get("web_search", {}),
                "task_suggestions": default_task_suggestions,
                "has_task_cues": default_has_task_cues,
                "retrieval": default_result.get("retrieval", {}),
                "memory_action": default_result.get("memory_action"),
                "memory_fact": default_result.get("memory_fact"),
                "memory_category": None,
                "skill_opportunity": None,
                "recall_used": False,
                "ampai_default_mode": True,
                "intent": default_result.get("intent_detected", "general"),
                "model_used": "AmpAI Built-in",
            }
            yield f"data: {json.dumps({'type': 'done', 'metadata': final_meta})}\n\n"

        return StreamingResponse(
            default_stream_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )

    # Otherwise stream using the langchain agent
    persona_prompt = ""
    if request.persona_id:
        personas = _load_config_list("personas_library")
        persona = next(
            (p for p in personas if p.get("id") == request.persona_id), None
        )
        if persona and persona.get("system_prompt"):
            persona_prompt = str(persona.get("system_prompt")).strip()
    
    message_for_agent = request.message
    if persona_prompt:
        message_for_agent = f"[Persona Instructions]\n{persona_prompt}\n\n[User Message]\n{request.message}"

    effective_chat_prefs = get_effective_chat_preferences(user.username)
    requested_mode = (request.chat_output_mode or "").strip().lower()
    if requested_mode not in {"compact", "normal"}:
        requested_mode = (
            str(effective_chat_prefs.get("chat_output_mode") or "normal")
            .strip()
            .lower()
        )
    if requested_mode not in {"compact", "normal"}:
        requested_mode = "normal"
    low_token_mode = bool(effective_chat_prefs.get("low_token_mode"))

    requested_memory_mode = (request.memory_mode or "").strip().lower()
    if requested_memory_mode not in {"indexed", "full"}:
        requested_memory_mode = "indexed"
    effective_memory_mode = (
        requested_memory_mode if user.role == "admin" else "indexed"
    )
    requested_top_k = (
        request.memory_top_k if request.memory_top_k is not None else 5
    )
    max_top_k = 3 if low_token_mode else 5
    clamped_top_k = max(1, min(max_top_k, int(requested_top_k or 5)))
    raw_recency_bias = (
        request.recency_bias
        if request.recency_bias is not None
        else request.memory_recency_bias
    )
    effective_recency_bias = float(
        raw_recency_bias if raw_recency_bias is not None else 0.6
    )
    effective_recency_bias = max(0.0, min(1.0, effective_recency_bias))
    category_filter_value = (
        request.category_filter or request.memory_category_filter or ""
    ).strip()

    policy = _get_memory_policy(user.username)
    explicit_save_fact = _extract_explicit_memory_request(request.message)

    async def stream_generator():
        try:
            async for chunk in chat_with_agent_stream(
                session_id=request.session_id,
                message=message_for_agent,
                model_type=request.model_type,
                api_key=request.api_key,
                model_name=request.model_name,
                memory_mode=effective_memory_mode,
                memory_top_k=clamped_top_k,
                recency_bias=effective_recency_bias,
                category_filter=category_filter_value,
                use_web_search=request.use_web_search,
                attachments=[a.dict() for a in request.attachments],
                chat_output_mode=requested_mode,
                username=user.username,
                is_admin=(user.role == "admin"),
                allowed_memory_categories=policy.get("allowed_categories") or [],
                persist_memory=bool(policy.get("auto_capture_enabled", True)),
                require_memory_approval=bool(policy.get("require_approval", False)),
                pii_strict_mode=bool(policy.get("pii_strict_mode", False)),
                force_save=bool(explicit_save_fact),
                enable_browser_tools=request.enable_browser_tools,
                enable_terminal_tools=request.enable_terminal_tools,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as err:
            logger.exception("Error in SSE streaming generator")
            yield f"data: {json.dumps({'type': 'token', 'token': f'⚠️ Error during streaming: {str(err)}'})}\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

