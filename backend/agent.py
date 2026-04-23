import os
import re
from langchain_community.chat_message_histories import SQLChatMessageHistory, RedisChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from memory_indexer import MemoryIndexer
from typing import List, Dict

# Models
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatOllama
from database import DATABASE_URL, get_config, get_core_memories, add_core_memory

from langchain_core.chat_history import BaseChatMessageHistory

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

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
    if use_web_search:
        try:
            from langchain_community.tools import DuckDuckGoSearchRun
            search = DuckDuckGoSearchRun()
            search_results = search.run(message)
            web_context = f"\n\n--- LIVE WEB SEARCH RESULTS FOR '{message}' ---\n{search_results}\nUse this real-time information to answer accurately.\n"
        except Exception as e:
            error_msg = str(e)
            print(f"Web search error: {error_msg}")
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
                print(f"Image read error: {e}")

    agent_directives = (
        "You are an intelligent AI assistant with a global memory system.\n"
        "Here are the CORE FACTS you must always remember about the user:\n"
        f"{core_facts_str}\n\n"
        "IMPORTANT DIRECTIVE: You must autonomously extract reliable information, important facts, or preferences about the user. "
        "If the user shares an important fact or explicitly asks you to remember something, "
        "you MUST append the following exact tag anywhere in your response: [SAVE_MEMORY: <the fact to save>]. "
        "Only save high-quality, reliable information.\n\n"
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
            print(f"Failed to add fact to PGVector: {e}")
            
        # Strip the tag from the final response sent to user
        content = re.sub(r'\[SAVE_MEMORY:\s*.*?\]', '', content, flags=re.IGNORECASE | re.DOTALL).strip()
    
    # Save Raw History to PostgreSQL for Admin Logging/Export
    sql_history = SQLChatMessageHistory(session_id=session_id, connection_string=DATABASE_URL)
    
    # Store images locally as markdown in raw history
    message_log = message
    if attachments:
        attachment_names = [a['filename'] for a in attachments]
        message_log = f"[Attachments: {', '.join(attachment_names)}]\n" + message
        
    sql_history.add_user_message(message_log)
    sql_history.add_ai_message(content)
    
    return content
