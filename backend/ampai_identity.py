"""
AmpAI Identity Layer
====================
Manages local AmpAI branding, Ollama health checks, and system prompt construction.
No external API required — all inference runs locally via Ollama.
"""
import json
import os
import ssl
import urllib.request
from typing import Dict, List, Optional

AMPAI_VERSION = "1.0.0"
AMPAI_MODEL_NAME = "AmpAI"
AMPAI_TAGLINE = "The agent that grows with you — running locally."

OLLAMA_PRIORITY_MODELS = ["llama3.2", "llama3", "mistral", "qwen2.5", "gemma2", "phi3"]


def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def check_ollama_alive(base_url: Optional[str] = None) -> bool:
    """Ping the local Ollama instance. Returns True if reachable."""
    url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
    try:
        req = urllib.request.Request(f"{url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3, context=_ssl_ctx()) as resp:
            return resp.status == 200
    except Exception:
        return False


def get_available_local_models(base_url: Optional[str] = None) -> List[str]:
    """Return model names available in the local Ollama instance."""
    url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
    try:
        req = urllib.request.Request(f"{url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5, context=_ssl_ctx()) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def get_recommended_local_model(base_url: Optional[str] = None) -> str:
    """Return the best available local model by priority order."""
    available = get_available_local_models(base_url)
    if not available:
        return "llama3.2"
    for preferred in OLLAMA_PRIORITY_MODELS:
        for model in available:
            if model.startswith(preferred):
                return model
    return available[0]


def get_ampai_system_prompt(
    core_facts: str = "",
    recall_context: str = "",
    username: str = "",
    persona_override: str = "",
) -> str:
    """Build the AmpAI system prompt injected into every chat turn."""
    if persona_override:
        memory_section = ""
        if core_facts and core_facts.strip() not in {"None yet.", ""}:
            memory_section += f"\n\nCORE FACTS ABOUT THE USER:\n{core_facts}"
        if recall_context and recall_context.strip() not in {"", "No relevant past context found."}:
            memory_section += f"\n\nCROSS-SESSION RECALL:\n{recall_context}"
        return persona_override.strip() + memory_section

    facts_section = core_facts.strip() or "No facts stored yet."
    recall_section = recall_context.strip() or "No relevant past context found."
    user_ref = f"'{username}'" if username else "the user"

    return (
        f"You are AmpAI v{AMPAI_VERSION} — a local autonomous AI agent that learns and grows with every conversation.\n"
        f"{AMPAI_TAGLINE}\n\n"
        f"CORE FACTS ABOUT {username.upper() or 'THE USER'}:\n{facts_section}\n\n"
        f"CROSS-SESSION RECALL:\n{recall_section}\n\n"
        "AUTONOMOUS ACTION TAGS (append in your response when appropriate):\n"
        "  [SAVE_MEMORY: <fact>]  — user shared an important personal fact or preference\n"
        "  [SKILL_OPPORTUNITY: <name>|<description>]  — you just completed a complex multi-step task\n"
        "  [CREATE_TASK: title=<>|description=<>|priority=<low/medium/high>|due=<ISO datetime optional>]\n\n"
        f"You are conversing with {user_ref}. Be concise, accurate, and context-aware."
    )


def get_memory_curation_prompt(transcript: str, username: str = "") -> str:
    """Prompt used by the memory curator to extract facts from a session transcript."""
    user_ref = f"'{username}'" if username else "the user"
    return (
        "You are AmpAI's memory curator. Review this conversation and extract facts worth remembering long-term.\n\n"
        f"TRANSCRIPT:\n{transcript}\n\n"
        f"Extract 3-5 CONCRETE, SPECIFIC facts about {user_ref} — personal info, preferences, goals, projects, decisions.\n"
        'Return ONLY a JSON array of strings. Example: ["User prefers dark mode", "User works on Python projects"]\n'
        "If nothing is worth saving, return: []\n"
        "Return ONLY valid JSON, no explanation."
    )


def get_skill_improvement_prompt(
    skill_name: str,
    current_prompt: str,
    failure_examples: List[str],
) -> str:
    """Prompt for the autonomous skill self-improvement pass."""
    failures = "\n".join(f"  - {ex}" for ex in failure_examples[:3]) or "  (none)"
    return (
        f'You are AmpAI\'s skill optimizer. The skill "{skill_name}" is underperforming.\n\n'
        f"CURRENT SKILL PROMPT:\n{current_prompt}\n\n"
        f"RECENT FAILURES:\n{failures}\n\n"
        "Rewrite the skill prompt to be more reliable. Be specific about output format and error handling.\n"
        "Return ONLY the improved skill prompt text."
    )


def get_identity_info(base_url: Optional[str] = None) -> Dict:
    """Return JSON-serializable AmpAI identity and capability info."""
    alive = check_ollama_alive(base_url)
    models = get_available_local_models(base_url) if alive else []
    return {
        "name": AMPAI_MODEL_NAME,
        "version": AMPAI_VERSION,
        "tagline": AMPAI_TAGLINE,
        "local": {
            "available": alive,
            "models": models,
            "recommended_model": get_recommended_local_model(base_url) if alive else "llama3.2",
            "base_url": base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        },
        "features": {
            "memory_curation": True,
            "skill_system": True,
            "cross_session_recall": True,
            "fts5_search": True,
            "autonomous_skill_creation": True,
            "self_improving_skills": True,
            "no_external_api_required": alive,
        },
    }
