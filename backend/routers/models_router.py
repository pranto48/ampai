"""Models router: GET /api/models/options and POST /api/admin/providers/test."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from core.deps import UserContext, require_admin_user, require_authenticated_user
from core.models import ProviderTestRequest
from database import get_all_configs
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(tags=["models"])


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
