"""Models router: GET /api/models/options, GET /api/models/health, and POST /api/admin/providers/test."""

from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from core.deps import UserContext, require_admin_user, require_authenticated_user
from core.models import ProviderTestRequest
from database import get_all_configs
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(tags=["models"])
logger = logging.getLogger(__name__)

# Fallback chain order per Requirement 6.3
FALLBACK_CHAIN = ["ollama", "openrouter", "openai", "gemini", "anthropic", "generic", "ampai_default"]

# Provider API key config names
_PROVIDER_KEY_MAP: Dict[str, str] = {
    "openrouter": "openrouter_api_key",
    "openai": "openai_api_key",
    "gemini": "gemini_api_key",
    "anthropic": "anthropic_api_key",
}

# Timeout for Ollama reachability check in local_only_mode
_LOCAL_PROBE_TIMEOUT = 8


def _parse_config_list(raw_value: Optional[str], defaults: List[str]) -> List[str]:
    if not raw_value:
        return defaults
    values = [item.strip() for item in str(raw_value).replace(",", "\n").splitlines()]
    cleaned = [value for value in values if value]
    return cleaned or defaults


def _timed_probe(
    url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 8
) -> Dict[str, Any]:
    started = time.perf_counter()
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return {
            "ok": 200 <= resp.status < 300,
            "status_code": resp.status,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "url": url,
        }


@router.get("/api/models/options")
def get_model_options(_: UserContext = Depends(require_authenticated_user)):
    configs = get_all_configs()
    local_only_mode = str(configs.get("local_only_mode", "true")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    providers = [
        {"value": "ollama", "label": "Ollama (Local)"},
        {"value": "generic", "label": "LM Studio / OpenAI-Compatible (Local)"},
        {"value": "anythingllm", "label": "AnythingLLM (Local Workspace)"},
        {"value": "openrouter", "label": "OpenRouter (Free Models)"},
        {"value": "openai", "label": "OpenAI"},
        {"value": "gemini", "label": "Google Gemini"},
        {"value": "anthropic", "label": "Anthropic"},
    ]
    if local_only_mode:
        providers = [
            p for p in providers if p["value"] in {"ollama", "generic", "anythingllm"}
        ]
    return {
        "providers": providers,
        "models": {
            "ollama": _parse_config_list(
                configs.get("ollama_model_list"),
                ["llama3.2", "gemma", "mistral", "qwen2.5"],
            ),
            "generic": _parse_config_list(
                configs.get("generic_model_list"),
                ["local-model", "llama-3.1-8b-instruct", "qwen2.5-7b-instruct"],
            ),
            "anythingllm": _parse_config_list(
                configs.get("anythingllm_workspace_list"),
                ["my-workspace"],
            ),
            "openrouter": _parse_config_list(
                configs.get("openrouter_model_list"),
                [
                    "meta-llama/llama-3.3-8b-instruct:free",
                    "qwen/qwen3-4b:free",
                    "deepseek/deepseek-r1-0528:free",
                ],
            ),
        },
    }


@router.get("/api/models/health")
def get_model_health(_: UserContext = Depends(require_authenticated_user)):
    """Return reachability status for each configured provider.

    Returns a JSON object per provider with: name, ok (boolean), latency_ms.
    Implements the fallback chain: Ollama → OpenRouter → OpenAI → Gemini → Anthropic → Generic → AmpAI_Default.
    In local_only_mode, only Ollama and AmpAI_Default are checked.
    Cloud providers without configured API keys are skipped.
    """
    configs = get_all_configs()
    local_only_mode = str(configs.get("local_only_mode", "true")).strip().lower() in {
        "1", "true", "yes", "on",
    }

    results: List[Dict[str, Any]] = []

    for provider in FALLBACK_CHAIN:
        # In local_only_mode, only check Ollama and AmpAI_Default
        if local_only_mode and provider not in {"ollama", "ampai_default"}:
            continue

        # Skip cloud providers without configured API keys
        if provider in _PROVIDER_KEY_MAP:
            key_value = (configs.get(_PROVIDER_KEY_MAP[provider]) or "").strip()
            if not key_value:
                results.append({
                    "name": provider,
                    "ok": False,
                    "latency_ms": 0,
                    "reason": "api_key_not_configured",
                })
                continue

        health = _check_provider_health(provider, configs)
        results.append(health)

    return {"providers": results}


def _check_provider_health(provider: str, configs: Dict[str, Any]) -> Dict[str, Any]:
    """Check health/reachability of a single provider."""
    try:
        if provider == "ollama":
            base = (configs.get("ollama_base_url") or "http://host.docker.internal:11434").rstrip("/")
            result = _timed_probe(f"{base}/api/tags", timeout=_LOCAL_PROBE_TIMEOUT)
            return {"name": "ollama", "ok": result["ok"], "latency_ms": result["latency_ms"]}

        elif provider == "openrouter":
            key = (configs.get("openrouter_api_key") or "").strip()
            result = _timed_probe(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=8,
            )
            return {"name": "openrouter", "ok": result["ok"], "latency_ms": result["latency_ms"]}

        elif provider == "openai":
            key = (configs.get("openai_api_key") or "").strip()
            result = _timed_probe(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=8,
            )
            return {"name": "openai", "ok": result["ok"], "latency_ms": result["latency_ms"]}

        elif provider == "gemini":
            key = (configs.get("gemini_api_key") or "").strip()
            # Gemini uses API key as query param; probe the models list endpoint
            result = _timed_probe(
                f"https://generativelanguage.googleapis.com/v1/models?key={key}",
                timeout=8,
            )
            return {"name": "gemini", "ok": result["ok"], "latency_ms": result["latency_ms"]}

        elif provider == "anthropic":
            key = (configs.get("anthropic_api_key") or "").strip()
            # Anthropic doesn't have a simple models list; probe with a lightweight request
            started = time.perf_counter()
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                method="POST",
                data=b'{"model":"claude-3-haiku-20240307","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}',
            )
            try:
                with urllib.request.urlopen(req, timeout=8) as resp:
                    latency = round((time.perf_counter() - started) * 1000, 2)
                    return {"name": "anthropic", "ok": True, "latency_ms": latency}
            except urllib.error.HTTPError as exc:
                latency = round((time.perf_counter() - started) * 1000, 2)
                # 401 means key is invalid, but 400/429 means the API is reachable
                ok = exc.code not in (401, 403)
                return {"name": "anthropic", "ok": ok, "latency_ms": latency}

        elif provider == "generic":
            base = (configs.get("generic_base_url") or "").rstrip("/")
            if not base:
                return {"name": "generic", "ok": False, "latency_ms": 0, "reason": "base_url_not_configured"}
            headers = {}
            if configs.get("generic_api_key"):
                headers["Authorization"] = f"Bearer {configs.get('generic_api_key')}"
            result = _timed_probe(f"{base}/v1/models", headers=headers, timeout=8)
            return {"name": "generic", "ok": result["ok"], "latency_ms": result["latency_ms"]}

        elif provider == "ampai_default":
            # AmpAI_Default is always available (built-in engine)
            return {"name": "ampai_default", "ok": True, "latency_ms": 0}

        else:
            return {"name": provider, "ok": False, "latency_ms": 0, "reason": "unknown_provider"}

    except Exception as exc:
        logger.debug(f"Health check failed for {provider}: {exc}")
        return {"name": provider, "ok": False, "latency_ms": 0, "reason": str(exc)}


def resolve_fallback_provider(configs: Optional[Dict[str, Any]] = None) -> str:
    """Resolve the best available provider using the fallback chain.

    Fallback chain: Ollama → OpenRouter → OpenAI → Gemini → Anthropic → Generic → AmpAI_Default.
    In local_only_mode: Ollama → AmpAI_Default (8s timeout for Ollama).
    Cloud providers without configured API keys are skipped.

    Returns the provider name string.
    """
    if configs is None:
        configs = get_all_configs()

    local_only_mode = str(configs.get("local_only_mode", "true")).strip().lower() in {
        "1", "true", "yes", "on",
    }

    if local_only_mode:
        # Try Ollama with 8s timeout, fallback to AmpAI_Default
        try:
            base = (configs.get("ollama_base_url") or "http://host.docker.internal:11434").rstrip("/")
            result = _timed_probe(f"{base}/api/tags", timeout=_LOCAL_PROBE_TIMEOUT)
            if result.get("ok"):
                return "ollama"
        except Exception:
            pass
        return "ampai_default"

    # Cloud mode: try each provider in fallback order
    for provider in FALLBACK_CHAIN:
        if provider == "ampai_default":
            return "ampai_default"

        # Skip cloud providers without API keys
        if provider in _PROVIDER_KEY_MAP:
            key_value = (configs.get(_PROVIDER_KEY_MAP[provider]) or "").strip()
            if not key_value:
                continue

        # Check if provider is reachable
        health = _check_provider_health(provider, configs)
        if health.get("ok"):
            return provider

    return "ampai_default"


@router.post("/api/admin/providers/test")
def test_provider_connection(
    request: ProviderTestRequest, _: UserContext = Depends(require_admin_user)
):
    provider = (request.provider or "").strip().lower()
    configs = get_all_configs()
    try:
        if provider == "ollama":
            base = (
                configs.get("ollama_base_url") or "http://host.docker.internal:11434"
            ).rstrip("/")
            return _timed_probe(f"{base}/api/tags")
        if provider == "generic":
            base = (configs.get("generic_base_url") or "").rstrip("/")
            if not base:
                raise HTTPException(
                    status_code=400, detail="generic_base_url is not configured"
                )
            headers = (
                {"Authorization": f"Bearer {configs.get('generic_api_key') or ''}"}
                if configs.get("generic_api_key")
                else {}
            )
            result = _timed_probe(f"{base}/v1/models", headers=headers)
            result["model"] = (configs.get("generic_model") or "").strip() or None
            return result
        if provider == "openrouter":
            key = (configs.get("openrouter_api_key") or "").strip()
            if not key:
                raise HTTPException(
                    status_code=400, detail="openrouter_api_key is not configured"
                )
            return _timed_probe(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
        if provider in {"openai", "gemini", "anthropic"}:
            key_name = {
                "openai": "openai_api_key",
                "gemini": "gemini_api_key",
                "anthropic": "anthropic_api_key",
            }[provider]
            has_key = bool((configs.get(key_name) or "").strip())
            return {
                "ok": has_key,
                "provider": provider,
                "message": "API key configured"
                if has_key
                else f"{key_name} is not configured",
            }
        if provider == "anythingllm":
            base = (configs.get("anythingllm_base_url") or "").rstrip("/")
            workspace = (configs.get("anythingllm_workspace") or "").strip()
            if not base or not workspace:
                raise HTTPException(
                    status_code=400,
                    detail="anythingllm base URL/workspace is not configured",
                )
            headers = (
                {"Authorization": f"Bearer {configs.get('anythingllm_api_key') or ''}"}
                if configs.get("anythingllm_api_key")
                else {}
            )
            return _timed_probe(f"{base}/api/v1/workspace/{workspace}", headers=headers)
        raise HTTPException(status_code=400, detail="Unsupported provider")
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "status_code": exc.code,
            "error": f"HTTP {exc.code}: {exc.reason}",
        }
    except HTTPException:
        raise
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
