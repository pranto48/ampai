import os
import re
import json
import uuid
import urllib.parse
import urllib.request
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from memory_indexer import MemoryIndexer
from typing import List, Dict, Any

from logging_utils import get_logger

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatOllama
from langchain_community.chat_message_histories import SQLChatMessageHistory
from database import DATABASE_URL, get_config, get_core_memories, add_core_memory, redact_pii_text
from memory_persistence import memory_persistence_manager

from langchain_core.chat_history import BaseChatMessageHistory

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ampai:ampai@db:5432/ampai")
logger = get_logger(__name__)

INDEXED_LOW_TOKEN_TOP_K_MAX = 3
INDEXED_TOP_K_MAX = 5
INDEXED_CONTEXT_CHAR_BUDGET = 1200







def get_redis_history(session_id: str):
    return RedisChatMessageHistory(session_id, url=REDIS_URL)


class ShortTermRedisMessageHistory(BaseChatMessageHistory):
    def __init__(self, session_id: str, k: int = 6):
        self.history = RedisChatMessageHistory(session_id, url=REDIS_URL)
        self.k = k

    @property
    def messages(self):
        msgs = self.history.messages
        return msgs[-self.k:] if len(msgs) > self.k else msgs

    def add_message(self, message):
        self.history.add_message(message)

    def clear(self):
        self.history.clear()


def get_short_redis_history(session_id: str):
    return ShortTermRedisMessageHistory(session_id=session_id, k=6)


TASK_CUE_PATTERNS = [
    r"\b(todo|to-do|task|tasks)\b",
    r"\bremind me\b",
    r"\bfollow up\b",
    r"\bdeadline\b",
    r"\baction item\b",
    r"\bshould I\b",
    r"\bneed to\b",
]


def _looks_like_task_intent(text: str) -> bool:
    sample = (text or "").lower()
    return any(re.search(pattern, sample) for pattern in TASK_CUE_PATTERNS)


def _parse_create_task_tags(content: str) -> List[Dict[str, Any]]:
    matches = re.findall(r"\[CREATE_TASK:\s*(.*?)\]", content or "", flags=re.IGNORECASE | re.DOTALL)
    suggestions: List[Dict[str, Any]] = []
    for raw in matches:
        parsed = {"title": "", "description": "", "priority": "medium", "due_at": None}
        for part in raw.split("|"):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            k = key.strip().lower()
            v = value.strip()
            if k == "title":
                parsed["title"] = v
            elif k == "description":
                parsed["description"] = v
            elif k == "priority":
                parsed["priority"] = v.lower() if v else "medium"
            elif k in {"due", "due_at"}:
                parsed["due_at"] = v or None
        if parsed["title"]:
            parsed["id"] = str(uuid.uuid4())
            parsed["source"] = "llm_tag"
            suggestions.append(parsed)
    return suggestions


def _build_fallback_suggestion(message: str, response: str) -> List[Dict[str, Any]]:
    if not (_looks_like_task_intent(message) or _looks_like_task_intent(response)):
        return []
    title = (message or "").strip().split("\n")[0][:120]
    if not title:
        title = "Follow up on recent conversation"
    return [{
        "id": str(uuid.uuid4()),
        "title": title,
        "description": (response or message or "").strip()[:500],
        "priority": "medium",
        "due_at": None,
        "source": "intent_heuristic",
    }]


def _parse_model_list(raw_value: str, defaults: List[str]) -> List[str]:
    if not raw_value:
        return defaults
    items = [line.strip() for line in raw_value.replace(",", "\n").splitlines()]
    cleaned = [item for item in items if item]
    return cleaned or defaults


def _coerce_positive_int(raw: Any, default_value: int) -> int:
    try:
        value = int(raw)
    except Exception:
        value = int(default_value)
    return max(1, value)


def _resolve_generation_options(model_type: str, chat_output_mode: str = "normal") -> Dict[str, Any]:
    base_limit = _coerce_positive_int(get_config("chat_max_output_tokens_default", "120"), 120)
    mode = (chat_output_mode or get_config("chat_output_mode", "normal") or "normal").strip().lower()
    if mode not in {"compact", "normal"}:
        mode = "normal"
    if mode == "compact":
        base_limit = _coerce_positive_int(get_config("chat_max_output_tokens_compact", base_limit), base_limit)

    override_key_map = {
        "openai": "openai_max_output_tokens",
        "generic": "generic_max_output_tokens",
        "openrouter": "openrouter_max_output_tokens",
        "anythingllm": "anythingllm_max_output_tokens",
        "gemini": "gemini_max_output_tokens",
        "anthropic": "anthropic_max_output_tokens",
        "ollama": "ollama_num_predict",
    }
    provider_limit = _coerce_positive_int(get_config(override_key_map.get(model_type, ""), base_limit), base_limit)

    if model_type == "ollama":
        return {"num_predict": provider_limit}
    if model_type == "gemini":
        return {"max_output_tokens": provider_limit}
    return {"max_tokens": provider_limit}


def get_llm(model_type: str, api_key: str = None, model_name: str = None, generation_options: Dict[str, Any] = None):
    generation_options = generation_options or {}
    if model_type == "ollama":
        base_url = get_config("ollama_base_url") or os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        configured_models = _parse_model_list(
            get_config("ollama_model_list"),
            ["llama3.2", "gemma", "mistral", "qwen2.5"],
        )
        selected_model = (model_name or get_config("ollama_model") or configured_models[0]).strip()
        return ChatOllama(model=selected_model, base_url=base_url, **generation_options)
    elif model_type == "openai":
        key = api_key or get_config("openai_api_key") or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OpenAI API key is required")
        return ChatOpenAI(model="gpt-3.5-turbo", api_key=key, **generation_options)
    elif model_type == "gemini":
        key = api_key or get_config("gemini_api_key") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ValueError("Google API key is required")
        return ChatGoogleGenerativeAI(model="gemini-pro", google_api_key=key, **generation_options)
    elif model_type == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
            key = api_key or get_config("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")
            if not key:
                raise ValueError("Anthropic API key is required")
            return ChatAnthropic(model="claude-3-opus-20240229", api_key=key, **generation_options)
        except ImportError:
            raise ValueError("langchain-anthropic is not installed")
    elif model_type == "generic":
        base_url = get_config("generic_base_url")
        key = api_key or get_config("generic_api_key") or "not-needed"
        if not base_url:
            raise ValueError("Generic Base URL is required")
        configured_models = _parse_model_list(
            get_config("generic_model_list"),
            ["local-model", "llama-3.1-8b-instruct", "qwen2.5-7b-instruct"],
        )
        selected_model = (model_name or get_config("generic_model") or configured_models[0]).strip()
        return ChatOpenAI(model=selected_model, api_key=key, base_url=base_url, **generation_options)
    elif model_type == "openrouter":
        key = api_key or get_config("openrouter_api_key")
        if not key:
            raise ValueError("OpenRouter API key is required")
        configured_models = _parse_model_list(
            get_config("openrouter_model_list"),
            [
                "meta-llama/llama-3.3-8b-instruct:free",
                "qwen/qwen3-4b:free",
                "deepseek/deepseek-r1-0528:free",
            ],
        )
        selected_model = (model_name or get_config("openrouter_model") or configured_models[0]).strip()
        return ChatOpenAI(model=selected_model, api_key=key, base_url="https://openrouter.ai/api/v1", **generation_options)
    elif model_type == "anythingllm":
        base_url = get_config("anythingllm_base_url")
        key = api_key or get_config("anythingllm_api_key") or "not-needed"
        workspace = model_name or get_config("anythingllm_workspace") or "my-workspace"
        if not base_url:
            raise ValueError("AnythingLLM Base URL is required")
        return ChatOpenAI(model=workspace, api_key=key, base_url=base_url, **generation_options)
    else:
        raise ValueError(f"Unsupported model type: {model_type}")


def chat_with_agent(
    session_id: str,
    message: str,
    model_type: str = "ollama",
    api_key: str = None,
    model_name: str = None,
    memory_mode: str = "full",
    memory_top_k: int = 5,
    recency_bias: float = 0.0,
    category_filter: str = "",
    use_web_search: bool = False,
    attachments: List[Dict] = None,
    chat_output_mode: str = None,
    **kwargs,
):
    if attachments is None:
        attachments = []
    generation_options = _resolve_generation_options(model_type=model_type, chat_output_mode=chat_output_mode or "normal")
    llm = get_llm(model_type, api_key, model_name=model_name, generation_options=generation_options)

    core_mems = get_core_memories()
    core_facts_str = "\n".join([f"- {m['fact']}" for m in core_mems]) if core_mems else "None yet."

    web_context = ""
    web_search = {"enabled": use_web_search, "provider": None, "status": "disabled", "error": None}
    if use_web_search:
        try:
            from langchain_community.tools import DuckDuckGoSearchRun
            search = DuckDuckGoSearchRun()
            search_results = search.run(message)
            web_search = {"enabled": True, "provider": "duckduckgo-langchain", "status": "ok", "error": None}
            web_context = f"\n\n--- LIVE WEB SEARCH RESULTS FOR '{message}' ---\n{search_results}\nUse this real-time information to answer accurately.\n"
        except Exception as e:
            first_error = str(e)
            try:
                from ddgs import DDGS
                with DDGS() as ddgs:
                    results = list(ddgs.text(message, max_results=5))
                search_results = "\n".join([f"- {r.get('title','')} | {r.get('href','')} | {r.get('body','')}" for r in results])
                web_search = {"enabled": True, "provider": "ddgs-direct", "status": "ok", "error": first_error}
                web_context = f"\n\n--- LIVE WEB SEARCH RESULTS FOR '{message}' ---\n{search_results}\nUse this real-time information to answer accurately.\n"
            except Exception as e2:
                error_msg = f"{first_error}; fallback_error={e2}"
                print(f"Web search error: {error_msg}")
                web_search = {"enabled": True, "provider": "none", "status": "failed", "error": error_msg}
                web_context = (
                    "\n\n--- LIVE WEB SEARCH STATUS ---\n"
                    f"Web search failed with error: {error_msg}\n"
                    "If results are unavailable, say that clearly instead of inventing web facts.\n"
                )

    file_context = ""
    image_contents = []

    for attachment in attachments:
        if attachment.get("extracted_text"):
            file_context += f"\n--- Attached Document: {attachment['filename']} ---\n{attachment['extracted_text']}\n"
        elif attachment.get("type", "").startswith("image/"):
            import base64
            file_path = os.path.join(os.path.dirname(__file__), "..", "data", attachment['url'].strip("/"))
            try:
                with open(file_path, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                    image_contents.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{attachment['type']};base64,{encoded_string}"}
                    })
            except Exception as e:
                logger.exception("Image read error", exc_info=e)

    agent_directives = (
        "You are an intelligent AI assistant with a global memory system.\n"
        "Here are the CORE FACTS you must always remember about the user:\n"
        f"{core_facts_str}\n\n"
        "IMPORTANT DIRECTIVE: You must autonomously extract reliable information, important facts, or preferences about the user. "
        "If the user shares an important fact or explicitly asks you to remember something, "
        "you MUST append the following exact tag anywhere in your response: [SAVE_MEMORY: <the fact to save>]. "
        "Only save high-quality, reliable information.\n"
        "If the user clearly asks to create a task, append a tag in this exact format: "
        "[CREATE_TASK: title=<task title>|description=<details>|priority=<low/medium/high>|due=<ISO datetime optional>].\n\n"
        f"{web_context}"
        f"{file_context}"
    )
    requested_mode = (chat_output_mode or get_config("chat_output_mode", "normal") or "normal").strip().lower()
    if requested_mode not in {"compact", "normal"}:
        requested_mode = "normal"
    if requested_mode == "compact":
        compact_token_cap = generation_options.get("max_tokens") or generation_options.get("max_output_tokens") or generation_options.get("num_predict") or 120
        agent_directives += (
            f"\nAnswer in <= {compact_token_cap} tokens, concise bullets, no extra explanation unless asked.\n"
        )
    persona_prompt_override = kwargs.get("persona_prompt_override")
    username = kwargs.get("username", "system")
    is_admin = kwargs.get("is_admin", False)
    allowed_memory_categories = kwargs.get("allowed_memory_categories", [])
    persist_memory = kwargs.get("persist_memory", True)
    require_memory_approval = kwargs.get("require_memory_approval", False)
    pii_strict_mode = kwargs.get("pii_strict_mode", False)

    persona_prompt = (persona_prompt_override or "").strip()
    if persona_prompt:
        agent_directives = (
            f"PERSONA SYSTEM PROMPT (highest priority):\n{persona_prompt}\n\n"
            + agent_directives
        )

    retrieval_meta = {
        "enabled": memory_mode == "indexed",
        "top_k": None,
        "recency_bias": None,
        "category_filter": None,
        "retrieved_count": 0,
        "truncated_count": 0,
        "context_chars": 0,
        "pipeline": "vector_only",
        "latency_ms": 0,
        "prefilter_count": 0,
        "cache_hits": 0,
        "cache_misses": 0,
    }

    if memory_mode == "indexed":
        indexer = MemoryIndexer(model_type)
        k = max(1, min(int(memory_top_k or 5), INDEXED_TOP_K_MAX))
        effective_recency_bias = max(0.0, min(1.0, float(recency_bias if recency_bias is not None else 0.6)))
        use_low_token_cap = (chat_output_mode or "").strip().lower() == "compact"
        if use_low_token_cap:
            k = min(k, INDEXED_LOW_TOKEN_TOP_K_MAX)
        relevant_memories = indexer.search_facts(
            message,
            k=k,
            recency_bias=effective_recency_bias,
            category_filter=(category_filter or None),
            username=username,
            status="approved",
        )

        query_terms = {w for w in re.findall(r"\w+", (message or "").lower()) if len(w) > 2}

        def _score_snippet(snippet: str, idx: int) -> float:
            words = {w for w in re.findall(r"\w+", snippet.lower()) if len(w) > 2}
            overlap = len(query_terms.intersection(words))
            date_hits = len(re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", snippet))
            rank_decay = max(0.0, 1.0 - (0.05 * idx))
            return (overlap * 2.0) + (date_hits * effective_recency_bias) + rank_decay

        ranked_memories = sorted(
            [(snippet, _score_snippet(snippet, idx)) for idx, snippet in enumerate(relevant_memories or [])],
            key=lambda item: item[1],
            reverse=True,
        )
        context_snippets: List[str] = []
        context_chars = 0
        truncated_count = 0
        for snippet, _score in ranked_memories:
            normalized = (snippet or "").strip()
            if not normalized:
                continue
            if len(normalized) > INDEXED_CONTEXT_CHAR_BUDGET:
                normalized = normalized[:INDEXED_CONTEXT_CHAR_BUDGET].rstrip() + "…"
                truncated_count += 1
            separator_chars = 5 if context_snippets else 0  # "\n---\n"
            remaining = INDEXED_CONTEXT_CHAR_BUDGET - context_chars - separator_chars
            if remaining <= 0:
                truncated_count += 1
                continue
            if len(normalized) > remaining:
                normalized = normalized[:remaining].rstrip() + "…"
                truncated_count += 1
            context_snippets.append(normalized)
            context_chars += len(normalized) + separator_chars
            if context_chars >= INDEXED_CONTEXT_CHAR_BUDGET:
                break

        context_str = "\n---\n".join(context_snippets) if context_snippets else "No previous relevant facts found."
        retrieval_meta.update({
            "top_k": k,
            "recency_bias": effective_recency_bias,
            "category_filter": category_filter or None,
            "retrieved_count": len(context_snippets),
            "truncated_count": truncated_count,
            "context_chars": len(context_str),
        })
        retrieval_meta.update(indexer.last_retrieval_stats or {})
        system_msg = (
            agent_directives +
            "FAST INDEXED MEMORY MODE: Instead of full history, here are the most relevant distilled facts retrieved for this query:\n"
            f"{context_str}\n\n"
            f"Retrieval tuning: top_k={k}, recency_bias={effective_recency_bias}, category_filter={category_filter or 'none'}, context_char_budget={INDEXED_CONTEXT_CHAR_BUDGET}.\n"
            "Use these to provide highly contextual answers."
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])
    else:
        system_msg = agent_directives + "Use the conversation memory to provide contextual answers. Be concise and clear."
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])

    chain = prompt | llm
    history_factory = get_short_redis_history if memory_mode == "indexed" else get_redis_history

    chain_with_history = RunnableWithMessageHistory(
        chain,
        history_factory,
        input_messages_key="input",
        history_messages_key="history",
    )

    human_input = [{"type": "text", "text": message}] + image_contents if image_contents else message

    response = chain_with_history.invoke({"input": human_input}, config={"configurable": {"session_id": session_id}})
    content = response.content

    # Capture memory candidates using the persistence manager
    memory_persistence_manager.capture_memory_candidate(
        username=username,
        session_id=session_id,
        message_content=message,
        response_content=content,
        require_approval=require_memory_approval
    )
    
    # Score the memory candidate
    memory_persistence_manager.score_memory_candidate(
        username=username,
        session_id=session_id,
        message_content=message,
        response_content=content
    )

    match = re.search(r'\[SAVE_MEMORY:\s*(.*?)\]', content, re.IGNORECASE | re.DOTALL)
    allowed_categories_set = {str(c).strip().lower() for c in (allowed_memory_categories or []) if str(c).strip()}
    if match:
        fact_to_save = match.group(1).strip().rstrip('].')
        save_allowed = persist_memory and not require_memory_approval
        if save_allowed and allowed_categories_set:
            inferred_category = "preferences" if re.search(r"\b(like|prefer|favorite|always|usually)\b", fact_to_save, re.IGNORECASE) else "general"
            save_allowed = inferred_category in allowed_categories_set
        if save_allowed:
            add_core_memory(fact_to_save)
            try:
                indexer = MemoryIndexer(model_type)
                indexer.add_fact(fact_to_save)
            except Exception as e:
                print(f"Failed to add fact to PGVector: {e}")
        content = re.sub(r'\[SAVE_MEMORY:\s*.*?\]', '', content, flags=re.IGNORECASE | re.DOTALL).strip()

    task_suggestions = _parse_create_task_tags(content)
    content = re.sub(r"\[CREATE_TASK:\s*.*?\]", "", content, flags=re.IGNORECASE | re.DOTALL).strip()
    if not task_suggestions:
        task_suggestions = _build_fallback_suggestion(message, content)

    sql_history = SQLChatMessageHistory(session_id=session_id, connection_string=DATABASE_URL)
    message_log = message
    if attachments:
        attachment_names = [a['filename'] for a in attachments]
        message_log = f"[Attachments: {', '.join(attachment_names)}]\n" + message

        pii_redaction_enabled = pii_strict_mode or str(get_config("pii_redaction_enabled", "true")).strip().lower() in {"1", "true", "yes", "on"}
        if pii_redaction_enabled:
            message_log = redact_pii_text(message_log)
            content = redact_pii_text(content)

        sql_history.add_user_message(message_log)
        sql_history.add_ai_message(content)

    return {
        "response": content,
        "web_search": web_search,
        "task_suggestions": task_suggestions,
        "has_task_cues": bool(task_suggestions),
        "retrieval": retrieval_meta,
    }
