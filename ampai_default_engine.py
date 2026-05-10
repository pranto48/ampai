"""
AmpAI Built-in Response Engine
================================
Provides intelligent responses WITHOUT any LLM API (no Ollama, no OpenAI, nothing).
This is the "default AmpAI" mode — works 100% offline using:
  - Core memory facts (stored in DB)
  - FTS5 cross-session search (SQLite)
  - Rule-based intent detection + template responses
  - Skill execution (if skills exist in DB)
  - Basic NLP patterns for common queries

When to use:
  - Ollama is not running
  - No external API keys configured
  - model_type = "ampai_default"
  - User explicitly wants local-only mode with no LLM
"""
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ── Intent patterns ────────────────────────────────────────────────────────────

_INTENTS: List[Tuple[str, str, str]] = [
    # (pattern, intent_key, display_name)
    (r"\b(hello|hi|hey|good morning|good afternoon|good evening|howdy)\b", "greeting", "Greeting"),
    (r"\b(who are you|what are you|introduce yourself|your name|ampai)\b", "identity", "Identity"),
    (r"\b(what can you do|help|capabilities|features|what do you know)\b", "help", "Help"),
    (r"\b(remember|save|note|store|keep in mind|don't forget)\b", "save_memory", "Save Memory"),
    (r"\b(what do you know about me|my info|my profile|my facts|know about me)\b", "my_facts", "User Facts"),
    (r"\b(time|date|today|now|current time|what time)\b", "datetime", "Date/Time"),
    (r"\b(tasks?|todo|to-do|what.*pending|what.*working on|remind me)\b", "tasks", "Tasks"),
    (r"\b(skills?|what.*skill|list.*skill|show.*skill)\b", "skills", "Skills"),
    (r"\b(memory|memories|remember|past.*conversation|previous.*chat)\b", "recall", "Memory Recall"),
    (r"\b(thank|thanks|thank you|appreciate|great|awesome|nice)\b", "thanks", "Thanks"),
    (r"\b(bye|goodbye|see you|later|cya|farewell)\b", "farewell", "Farewell"),
    (r"\b(weather|temperature|forecast|rain|sunny)\b", "weather", "Weather"),
    (r"\b(joke|funny|humor|laugh|make me laugh)\b", "joke", "Joke"),
    (r"\b(summarize|summary|tldr|brief|overview)\b", "summarize", "Summarize"),
    (r"\b(calculate|math|compute|add|subtract|multiply|divide|[0-9]+\s*[\+\-\*\/]\s*[0-9]+)\b", "math", "Math"),
    (r"\b(search|find|look up|look for|what is|who is|define|explain)\b", "search", "Search/Explain"),
    (r"\b(create|make|build|generate|write|draft|compose)\b", "create", "Create"),
    (r"\b(status|health|running|alive|online|system|how.*doing)\b", "status", "System Status"),
]

_JOKES = [
    "Why did the AI go to therapy? Because it had too many neural issues. 🤖",
    "I asked an AI to write me a haiku. It wrote: 'Processing… Please wait… Out of memory.' 😄",
    "What do you call an AI that sings? A-dell. 🎵",
    "Why don't AI assistants ever get lost? Because they always follow their training data! 🗺️",
    "I told AmpAI to make me a sandwich. It said 'poof, you're a sandwich.' 🥪",
]

_MATH_EXPR = re.compile(r"([\d\.]+)\s*([\+\-\*\/x×÷])\s*([\d\.]+)")


def _detect_intent(message: str) -> str:
    """Detect the user's intent from their message."""
    msg = message.lower().strip()
    for pattern, intent, _ in _INTENTS:
        if re.search(pattern, msg):
            return intent
    return "general"


def _try_math(message: str) -> Optional[str]:
    """Try to evaluate a simple arithmetic expression."""
    match = _MATH_EXPR.search(message)
    if not match:
        return None
    try:
        a = float(match.group(1))
        op = match.group(2).strip()
        b = float(match.group(3))
        if op in ("+",):
            result = a + b
        elif op in ("-",):
            result = a - b
        elif op in ("*", "x", "×"):
            result = a * b
        elif op in ("/", "÷"):
            if b == 0:
                return "I can't divide by zero! 🤔"
            result = a / b
        else:
            return None
        # Format cleanly
        if result == int(result):
            return f"The answer is **{int(result)}**. 🧮"
        return f"The answer is **{round(result, 6)}**. 🧮"
    except Exception:
        return None


def _format_core_facts(core_mems: List[Dict]) -> str:
    if not core_mems:
        return "I don't have any stored facts about you yet. Tell me something and I'll remember it!"
    lines = [f"• {m.get('fact', '')}" for m in core_mems[:20] if m.get("fact")]
    return "Here's what I know about you:\n\n" + "\n".join(lines)


def _get_skill_list_text() -> str:
    """Return a plain-text list of available skills."""
    try:
        from skill_engine import list_skills
        skills = list_skills(status="active")
        if not skills:
            return "No skills have been created yet. Start a complex task and I'll suggest creating one!"
        lines = [f"• **{s['name']}** — {s.get('description', 'No description')}" for s in skills[:15]]
        return f"I have **{len(skills)}** skill(s) available:\n\n" + "\n".join(lines)
    except Exception:
        return "Skills are loading — try again shortly."


def _get_recall_text(message: str, username: Optional[str] = None) -> str:
    """Search FTS5 and return a plain-text summary."""
    try:
        from session_recall import search_recall, summarize_hits
        hits = search_recall(query=message, username=username, limit=8)
        if not hits:
            return "I searched my past conversations but couldn't find anything relevant to that."
        return "From my past conversations:\n\n" + summarize_hits(hits, max_items=5)
    except Exception:
        return "I couldn't search past conversations right now."


def _get_pending_tasks_text() -> str:
    """Return pending tasks from DB."""
    try:
        from database import list_tasks
        tasks = list_tasks()
        pending = [t for t in (tasks or []) if t.get("status") not in ("done", "completed")][:10]
        if not pending:
            return "You have no pending tasks! 🎉"
        lines = [
            f"• [{t.get('priority','medium').upper()}] **{t.get('title','-')}** — {t.get('status','todo')}"
            for t in pending
        ]
        return f"You have **{len(pending)}** pending task(s):\n\n" + "\n".join(lines)
    except Exception:
        return "Couldn't load tasks right now."


def _generate_response(
    message: str,
    intent: str,
    core_mems: List[Dict],
    username: str = "",
    skill_opportunity_detected: bool = False,
) -> str:
    """Generate a response based on detected intent."""
    now = datetime.now(timezone.utc)
    user_greeting = username or "there"

    if intent == "greeting":
        hour = now.hour
        time_of_day = "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"
        facts_hint = f" I have {len(core_mems)} fact(s) stored about you." if core_mems else ""
        return (
            f"Good {time_of_day}, {user_greeting}! 👋 I'm **AmpAI**, your local autonomous AI agent.{facts_hint}\n\n"
            "I'm running in **default mode** — no external AI model required. "
            "I can help with memory recall, tasks, skills, and more. What would you like to do?"
        )

    if intent == "identity":
        return (
            "I'm **AmpAI** — your local autonomous AI assistant. 🤖\n\n"
            "**What makes me special:**\n"
            "• 🧠 I remember facts across all your conversations\n"
            "• 🔧 I can create and reuse skills for recurring tasks\n"
            "• 🔍 I search past sessions for relevant context\n"
            "• 💡 I suggest memories worth saving (nudges)\n"
            "• 🏠 Running 100% locally — no data leaves your device\n\n"
            "I'm currently in **default mode** (no external AI model needed). "
            "For more complex reasoning, connect a local Ollama model or configure an API key in Settings."
        )

    if intent == "help":
        return (
            "Here's what I can help with:\n\n"
            "**💬 Chat & Memory**\n"
            "• Remember facts about you across sessions\n"
            "• Search past conversations for context\n"
            "• Suggest important facts to save (memory nudges)\n\n"
            "**🔧 Skills**\n"
            "• Run reusable skill templates for recurring tasks\n"
            "• Auto-create skills from complex conversations\n"
            "• Self-improving skills that get better over time\n\n"
            "**✅ Tasks**\n"
            "• Create and track tasks from conversations\n"
            "• View pending tasks and deadlines\n\n"
            "**🤖 AI Models**\n"
            "• Connect Ollama for full local AI reasoning\n"
            "• Or use OpenRouter / OpenAI / Gemini via Settings\n\n"
            "*Tip: Say 'connect Ollama' or go to Settings to enable a full AI model.*"
        )

    if intent == "datetime":
        local_str = now.strftime("%A, %B %d, %Y at %H:%M UTC")
        return f"The current date and time is:\n\n**{local_str}**"

    if intent == "my_facts":
        return _format_core_facts(core_mems)

    if intent == "tasks":
        return _get_pending_tasks_text()

    if intent == "skills":
        return _get_skill_list_text()

    if intent == "recall":
        return _get_recall_text(message, username=username or None)

    if intent == "thanks":
        return f"You're welcome, {user_greeting}! 😊 Happy to help anytime. Is there anything else you'd like to do?"

    if intent == "farewell":
        return f"Goodbye, {user_greeting}! 👋 Your memories are safe with me. See you next time!"

    if intent == "weather":
        return (
            "I don't have access to real-time weather data in default mode. 🌤️\n\n"
            "To get weather info, please:\n"
            "• Enable web search in the chat settings, or\n"
            "• Connect an AI model with web access (Ollama + web search)\n\n"
            "You can also ask me to set a weather-check reminder task!"
        )

    if intent == "joke":
        import random
        return random.choice(_JOKES)

    if intent == "status":
        from ampai_identity import check_ollama_alive, get_available_local_models
        ollama_alive = check_ollama_alive()
        models = get_available_local_models() if ollama_alive else []
        fact_count = len(core_mems)
        try:
            from session_recall import get_fts_stats
            fts = get_fts_stats()
            fts_turns = fts.get("total_turns_indexed", 0)
            fts_sessions = fts.get("distinct_sessions", 0)
        except Exception:
            fts_turns = fts_sessions = 0

        ollama_status = f"✅ Online ({len(models)} model(s))" if ollama_alive else "❌ Offline"
        return (
            "**AmpAI System Status** 🖥️\n\n"
            f"• **Local AI (Ollama):** {ollama_status}\n"
            f"• **Core Memories:** {fact_count} fact(s) stored\n"
            f"• **FTS5 Index:** {fts_turns} turns across {fts_sessions} session(s)\n"
            f"• **Mode:** {'Full AI' if ollama_alive else 'Default (no model)'}\n"
            f"• **Skills:** {_try_get_skill_count()} active skill(s)\n"
        )

    if intent == "math":
        math_result = _try_math(message)
        if math_result:
            return math_result

    if intent == "save_memory":
        return (
            "I'd love to remember that! 🧠\n\n"
            "In default mode, you can:\n"
            "• Go to **Memory** → **Core Memories** and add a fact directly\n"
            "• Or type your fact and I'll extract it automatically once an AI model is connected\n\n"
            "To enable automatic memory extraction, connect an Ollama model in Settings."
        )

    # General fallback
    recall_context = _get_recall_text(message, username=username or None)
    recall_note = f"\n\n*From my memory:*\n{recall_context}" if "couldn't find" not in recall_context else ""

    return (
        f"I'm AmpAI running in **default mode** (no AI model connected). "
        f"I received your message: *\"{message[:200]}{'...' if len(message) > 200 else ''}\"*\n\n"
        "For complex reasoning and answers, please:\n"
        "• Start **Ollama** locally (recommended — free, private, fast)\n"
        "• Or add an API key in **Settings** (OpenRouter has free models)\n\n"
        "I can still help with: tasks, memory recall, skills, date/time, and basic info."
        + recall_note
    )


def _try_get_skill_count() -> int:
    try:
        from skill_engine import list_skills
        return len(list_skills(status="active"))
    except Exception:
        return 0


# ── Public API ─────────────────────────────────────────────────────────────────

def ampai_default_chat(
    message: str,
    session_id: str,
    username: str = "",
    core_mems: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    AmpAI's built-in response engine — no external model needed.
    Returns a dict matching the shape of chat_with_agent()'s return value.
    """
    if core_mems is None:
        try:
            from database import get_core_memories
            core_mems = get_core_memories()
        except Exception:
            core_mems = []

    intent = _detect_intent(message)
    response = _generate_response(
        message=message,
        intent=intent,
        core_mems=core_mems,
        username=username,
    )

    # Auto-detect save_memory request from message
    memory_action = None
    memory_fact = None
    save_pattern = re.compile(
        r"\b(?:remember|save|note|store|keep in mind)[:\s]+(.+)", re.IGNORECASE
    )
    save_match = save_pattern.search(message)
    if save_match:
        fact_candidate = save_match.group(1).strip()
        if 5 < len(fact_candidate) < 500:
            memory_action = "pending_approval"
            memory_fact = fact_candidate

    # Index this turn into FTS5
    try:
        from session_recall import index_chat_turn
        index_chat_turn(session_id=session_id, username=username, role="human", content=message)
        index_chat_turn(session_id=session_id, username=username, role="ai", content=response)
    except Exception:
        pass

    # Persist to SQL history
    try:
        from database import DATABASE_URL
        from langchain_community.chat_message_histories import SQLChatMessageHistory
        sql_history = SQLChatMessageHistory(session_id=session_id, connection_string=DATABASE_URL)
        sql_history.add_user_message(message)
        sql_history.add_ai_message(response)
    except Exception:
        pass

    return {
        "response": response,
        "web_search": {"enabled": False, "status": "disabled", "provider": "ampai_default"},
        "task_suggestions": [],
        "has_task_cues": False,
        "retrieval": {"enabled": False, "context_chars": 0},
        "memory_action": memory_action,
        "memory_fact": memory_fact,
        "memory_category": None,
        "skill_opportunity": None,
        "recall_used": False,
        "ampai_default_mode": True,
        "intent_detected": intent,
    }
