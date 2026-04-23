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

# Models
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatOllama
from database import get_config, get_core_memories, add_core_memory, create_task, get_sql_chat_history

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


def _format_search_results(results: List[Dict[str, Any]]) -> str:
    if not results:
        return "No results found."
    lines = []
    for idx, item in enumerate(results, 1):
        title = item.get("title") or "Untitled"
        url = item.get("url") or ""
        snippet = item.get("snippet") or ""
        lines.append(f"{idx}. {title}\n   URL: {url}\n   Snippet: {snippet}")
    return "\n".join(lines)


def search_web(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Try web search providers in order:
    1) DuckDuckGo
    2) Optional configured fallback provider (SerpAPI/Bing/custom)
    """
    last_error = "Web search unavailable."

    # 1) DuckDuckGo
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            ddg_results = list(ddgs.text(query, max_results=max_results))
        normalized = [
            {
                "title": row.get("title", ""),
                "url": row.get("href", ""),
                "snippet": row.get("body", ""),
            }
            for row in ddg_results
        ]
        return {
            "ok": True,
            "provider": "DuckDuckGo",
            "results": normalized,
            "error": None,
        }
    except Exception as exc:
        last_error = f"DuckDuckGo failed: {exc}"

    # 2) Optional fallback provider
    fallback_provider = (get_config("web_fallback_provider") or "").strip().lower()
    if fallback_provider == "serpapi":
        serpapi_key = (get_config("serpapi_api_key") or "").strip()
        if serpapi_key:
            try:
                params = urllib.parse.urlencode({
                    "engine": "google",
                    "q": query,
                    "api_key": serpapi_key,
                    "num": max_results
                })
                url = f"https://serpapi.com/search.json?{params}"
                with urllib.request.urlopen(url, timeout=12) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                items = payload.get("organic_results", [])[:max_results]
                normalized = [
                    {
                        "title": row.get("title", ""),
                        "url": row.get("link", ""),
                        "snippet": row.get("snippet", ""),
                    }
                    for row in items
                ]
                return {"ok": True, "provider": "SerpAPI", "results": normalized, "error": None}
            except Exception as exc:
                last_error = f"SerpAPI failed: {exc}"
        else:
            last_error = "SerpAPI fallback selected but serpapi_api_key is missing."
    elif fallback_provider == "bing":
        bing_key = (get_config("bing_api_key") or "").strip()
        if bing_key:
            try:
                params = urllib.parse.urlencode({"q": query, "count": max_results})
                url = f"https://api.bing.microsoft.com/v7.0/search?{params}"
                req = urllib.request.Request(url, headers={"Ocp-Apim-Subscription-Key": bing_key})
                with urllib.request.urlopen(req, timeout=12) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                items = payload.get("webPages", {}).get("value", [])[:max_results]
                normalized = [
                    {
                        "title": row.get("name", ""),
                        "url": row.get("url", ""),
                        "snippet": row.get("snippet", ""),
                    }
                    for row in items
                ]
                return {"ok": True, "provider": "Bing", "results": normalized, "error": None}
            except Exception as exc:
                last_error = f"Bing failed: {exc}"
        else:
            last_error = "Bing fallback selected but bing_api_key is missing."
    elif fallback_provider == "custom":
        custom_url = (get_config("custom_web_search_url") or "").strip()
        custom_key = (get_config("custom_web_search_api_key") or "").strip()
        if custom_url:
            try:
                sep = "&" if "?" in custom_url else "?"
                url = f"{custom_url}{sep}{urllib.parse.urlencode({'q': query, 'limit': max_results})}"
                headers = {"Accept": "application/json"}
                if custom_key:
                    headers["Authorization"] = f"Bearer {custom_key}"
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=12) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                rows = payload.get("results") or payload.get("items") or payload.get("data") or []
                normalized = []
                for row in rows[:max_results]:
                    normalized.append({
                        "title": row.get("title", ""),
                        "url": row.get("url") or row.get("link", ""),
                        "snippet": row.get("snippet") or row.get("description", ""),
                    })
                return {"ok": True, "provider": "Custom", "results": normalized, "error": None}
            except Exception as exc:
                last_error = f"Custom provider failed: {exc}"
        else:
            last_error = "Custom fallback selected but custom_web_search_url is missing."

    return {"ok": False, "provider": None, "results": [], "error": last_error}

def get_llm(model_type: str, api_key: str = None):
    if model_type == "ollama":
        base_url = get_config("ollama_base_url") or os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        return ChatOllama(model="gemma", base_url=base_url)
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
        return ChatOpenAI(model="local-model", api_key=key, base_url=base_url)
    elif model_type == "openrouter":
        key = api_key or get_config("openrouter_api_key")
        if not key:
            raise ValueError("OpenRouter API key is required")
        # Default to a popular free model on OpenRouter if admin didn't specify one
        model_name = get_config("openrouter_model") or "meta-llama/llama-3-8b-instruct:free"
        return ChatOpenAI(
            model=model_name,
            api_key=key,
            base_url="https://openrouter.ai/api/v1"
        )
    elif model_type == "anythingllm":
        base_url = get_config("anythingllm_base_url")
        key = api_key or get_config("anythingllm_api_key") or "not-needed"
        workspace = get_config("anythingllm_workspace") or "my-workspace"
        if not base_url:
            raise ValueError("AnythingLLM Base URL is required")
        return ChatOpenAI(model=workspace, api_key=key, base_url=base_url)
    else:
        raise ValueError(f"Unsupported model type: {model_type}")

def chat_with_agent(session_id: str, message: str, model_type: str = "ollama", api_key: str = None, memory_mode: str = "full", use_web_search: bool = False, attachments: List[Dict] = None):
    if attachments is None: attachments = []
    llm = get_llm(model_type, api_key)
    
    core_mems = get_core_memories()
    core_facts_str = "\n".join([f"- {m['fact']}" for m in core_mems]) if core_mems else "None yet."
    
    web_context = ""
    web_search_status = {"ok": False, "provider": None, "results": [], "error": "Web search not requested."}
    if use_web_search:
        web_search_status = search_web(message)
        if web_search_status["ok"]:
            formatted_results = _format_search_results(web_search_status["results"])
            web_context = (
                f"\n\n--- LIVE WEB SEARCH RESULTS ({web_search_status['provider']}) FOR '{message}' ---\n"
                f"{formatted_results}\nUse this real-time information to answer accurately.\n"
            )
        else:
            error_msg = web_search_status["error"]
            logger.warning("Web search failed", extra={"error": error_msg})
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
            MessagesPlaceholder(variable_name="history"), # We still pass recent short-term history via RunnableWithMessageHistory
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
    
    if memory_mode == "indexed":
        history_factory = get_short_redis_history
    else:
        history_factory = get_redis_history

    chain_with_history = RunnableWithMessageHistory(
        chain,
        history_factory,
        input_messages_key="input",
        history_messages_key="history",
    )
    
    # Format input for vision models if there are images
    human_input = [{"type": "text", "text": message}] + image_contents if image_contents else message

    response = chain_with_history.invoke(
        {"input": human_input},
        config={"configurable": {"session_id": session_id}}
    )
    
    content = response.content
    
    # Parse for [SAVE_MEMORY: ...]
    match = re.search(r'\[SAVE_MEMORY:\s*(.*?)\]', content, re.IGNORECASE | re.DOTALL)
    if match:
        fact_to_save = match.group(1).strip()
        # Clean trailing brackets or punctuation if model included them
        fact_to_save = fact_to_save.rstrip('].')
        
        # Save to global prompt injection DB
        add_core_memory(fact_to_save)
        
        # Save to PGVector for semantic search indexing
        try:
            indexer = MemoryIndexer(model_type)
            indexer.add_fact(fact_to_save)
        except Exception as e:
            logger.exception("Failed to add fact to PGVector", exc_info=e)
            
        # Strip the tag from the final response sent to user
        content = re.sub(r'\[SAVE_MEMORY:\s*.*?\]', '', content, flags=re.IGNORECASE | re.DOTALL).strip()

    task_tags = re.findall(r'\[CREATE_TASK:\s*(.*?)\]', content, re.IGNORECASE | re.DOTALL)
    created_tasks = []
    for raw_task in task_tags:
        payload = raw_task.strip().rstrip("]")
        title = payload
        description = ""
        priority = "medium"
        due_at = None

        # simple key-value parser: title=..., description=..., priority=..., due=...
        kv_pairs = re.findall(r'(\w+)\s*=\s*([^|]+)', payload)
        if kv_pairs:
            data = {k.lower().strip(): v.strip() for k, v in kv_pairs}
            title = data.get("title") or payload
            description = data.get("description", "")
            priority = data.get("priority", "medium")
            due_at = data.get("due")
        elif "|" in payload:
            parts = [p.strip() for p in payload.split("|")]
            if parts:
                title = parts[0]
            if len(parts) > 1:
                description = parts[1]
            if len(parts) > 2 and parts[2]:
                priority = parts[2]
            if len(parts) > 3 and parts[3]:
                due_at = parts[3]

        task = create_task(
            title=title,
            description=description,
            priority=priority,
            due_at=due_at,
            session_id=session_id,
        )
        if task:
            created_tasks.append(task["id"])

    if task_tags:
        content = re.sub(r'\[CREATE_TASK:\s*.*?\]', '', content, flags=re.IGNORECASE | re.DOTALL).strip()
        if created_tasks:
            content += f"\n\n✅ Created {len(created_tasks)} task(s): #{', #'.join(str(tid) for tid in created_tasks)}"
    
    # Save Raw History to PostgreSQL for Admin Logging/Export
    sql_history = get_sql_chat_history(session_id)
    
    # Store images locally as markdown in raw history
    message_log = message
    if attachments:
        attachment_names = [a['filename'] for a in attachments]
        message_log = f"[Attachments: {', '.join(attachment_names)}]\n" + message
        
    sql_history.add_user_message(message_log)
    sql_history.add_ai_message(content)
    
    return {"content": content, "web_search_status": web_search_status}
