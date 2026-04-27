import os
import re
import json
import urllib.parse
import urllib.request
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from memory_indexer import MemoryIndexer
from typing import List, Dict, Any

from logging_utils import get_logger

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatOllama
from database import (
    get_config,
    get_core_memories,
    add_core_memory,
    create_task,
    get_sql_chat_history,
    redact_pii_text,
    get_persona_for_user,
)

from langchain_core.chat_history import BaseChatMessageHistory

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
logger = get_logger(__name__)







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


def _parse_model_list(raw_value: str, defaults: List[str]) -> List[str]:
    if not raw_value:
        return defaults
    items = [line.strip() for line in raw_value.replace(",", "\n").splitlines()]
    cleaned = [item for item in items if item]
    return cleaned or defaults


def get_llm(model_type: str, api_key: str = None, model_name: str = None):
    if model_type == "ollama":
        base_url = get_config("ollama_base_url") or os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        configured_models = _parse_model_list(
            get_config("ollama_model_list"),
            ["llama3.2", "gemma", "mistral", "qwen2.5"],
        )
        selected_model = (model_name or get_config("ollama_model") or configured_models[0]).strip()
        return ChatOllama(model=selected_model, base_url=base_url)
    elif model_type == "openai":
        key = api_key or get_config("openai_api_key") or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OpenAI API key is required")
        return ChatOpenAI(model="gpt-3.5-turbo", api_key=key)
    elif model_type == "gemini":
        key = api_key or get_config("gemini_api_key") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ValueError("Google API key is required")
        return ChatGoogleGenerativeAI(model="gemini-pro", google_api_key=key)
    elif model_type == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
            key = api_key or get_config("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")
            if not key:
                raise ValueError("Anthropic API key is required")
            return ChatAnthropic(model="claude-3-opus-20240229", api_key=key)
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
        return ChatOpenAI(model=selected_model, api_key=key, base_url=base_url)
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
        return ChatOpenAI(model=selected_model, api_key=key, base_url="https://openrouter.ai/api/v1")
    elif model_type == "anythingllm":
        base_url = get_config("anythingllm_base_url")
        key = api_key or get_config("anythingllm_api_key") or "not-needed"
        workspace = model_name or get_config("anythingllm_workspace") or "my-workspace"
        if not base_url:
            raise ValueError("AnythingLLM Base URL is required")
        return ChatOpenAI(model=workspace, api_key=key, base_url=base_url)
    else:
        raise ValueError(f"Unsupported model type: {model_type}")


def chat_with_agent(
    session_id: str,
    message: str,
    model_type: str = "ollama",
    api_key: str = None,
    model_name: str = None,
    memory_mode: str = "full",
    use_web_search: bool = False,
    attachments: List[Dict] = None,
    persona_id: int = None,
    persona_prompt_override: str = None,
    username: str = "",
    is_admin: bool = False,
):
    if attachments is None:
        attachments = []
    llm = get_llm(model_type, api_key, model_name=model_name)

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
    persona_prompt = (persona_prompt_override or "").strip()
    if not persona_prompt and persona_id:
        persona = get_persona_for_user(persona_id=persona_id, username=username, is_admin=is_admin)
        if persona:
            persona_prompt = (persona.get("system_prompt") or "").strip()
    if persona_prompt:
        agent_directives = (
            f"PERSONA SYSTEM PROMPT (highest priority):\n{persona_prompt}\n\n"
            + agent_directives
        )

    if memory_mode == "indexed":
        indexer = MemoryIndexer(model_type)
        relevant_memories = indexer.search_facts(message, k=5)
        context_str = "\n---\n".join(relevant_memories) if relevant_memories else "No previous relevant facts found."
        system_msg = (
            agent_directives +
            "FAST INDEXED MEMORY MODE: Instead of full history, here are the most relevant distilled facts retrieved for this query:\n"
            f"{context_str}\n\n"
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

    match = re.search(r'\[SAVE_MEMORY:\s*(.*?)\]', content, re.IGNORECASE | re.DOTALL)
    if match:
        fact_to_save = match.group(1).strip().rstrip('].')
        add_core_memory(fact_to_save)
        try:
            indexer = MemoryIndexer(model_type)
            indexer.add_fact(fact_to_save)
        except Exception as e:
            print(f"Failed to add fact to PGVector: {e}")
        content = re.sub(r'\[SAVE_MEMORY:\s*.*?\]', '', content, flags=re.IGNORECASE | re.DOTALL).strip()

    sql_history = SQLChatMessageHistory(session_id=session_id, connection_string=DATABASE_URL)
    message_log = message
    if attachments:
        attachment_names = [a['filename'] for a in attachments]
        message_log = f"[Attachments: {', '.join(attachment_names)}]\n" + message

    pii_redaction_enabled = str(get_config("pii_redaction_enabled", "true")).strip().lower() in {"1", "true", "yes", "on"}
    if pii_redaction_enabled:
        message_log = redact_pii_text(message_log)
        content = redact_pii_text(content)

    sql_history.add_user_message(message_log)
    sql_history.add_ai_message(content)

    return {"response": content, "web_search": web_search}
