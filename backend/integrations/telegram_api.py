import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict


API_BASE = "https://api.telegram.org"


def _telegram_request(bot_token: str, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{API_BASE}/bot{bot_token}/{method}"
    body = json.dumps(payload).encode("utf-8")
    max_attempts = 3

    for attempt in range(max_attempts):
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as err:
            raw = err.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                data = {}

            should_retry = err.code == 429 or 500 <= err.code <= 599
            if should_retry and attempt < max_attempts - 1:
                retry_after = 0
                if isinstance(data, dict):
                    retry_after = int(data.get("parameters", {}).get("retry_after", 0) or 0)
                time.sleep(max(retry_after, 1 + attempt))
                continue

            return {
                "ok": False,
                "error": "telegram_http_error",
                "status": err.code,
                "description": data.get("description", "http_error") if isinstance(data, dict) else "http_error",
            }
        except urllib.error.URLError:
            if attempt < max_attempts - 1:
                time.sleep(1 + attempt)
                continue
            return {"ok": False, "error": "telegram_network_error"}
        except json.JSONDecodeError:
            return {"ok": False, "error": "telegram_bad_json"}

    return {"ok": False, "error": "telegram_retry_exhausted"}


def send_telegram_message(bot_token: str, chat_id: int | str, text: str) -> Dict[str, Any]:
    return _telegram_request(
        bot_token=bot_token,
        method="sendMessage",
        payload={"chat_id": chat_id, "text": text},
    )


def set_telegram_webhook(bot_token: str, webhook_url: str, secret_token: str | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"url": webhook_url}
    if secret_token:
        payload["secret_token"] = secret_token
    return _telegram_request(bot_token=bot_token, method="setWebhook", payload=payload)


def delete_telegram_webhook(bot_token: str) -> Dict[str, Any]:
    return _telegram_request(bot_token=bot_token, method="deleteWebhook", payload={})
