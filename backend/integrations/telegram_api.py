"""
Telegram Bot API helpers.

All functions raise on failure so callers receive actionable error messages.
Previously errors were silently swallowed; this made debugging impossible.
"""
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request


API_BASE = "https://api.telegram.org"
_DEFAULT_TIMEOUT = 20


def _build_ctx() -> ssl.SSLContext:
    """Return a permissive SSL context that works inside Docker containers."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _do_request(url: str, data: bytes = None, method: str = "GET", timeout: int = _DEFAULT_TIMEOUT) -> dict:
    """
    Make an HTTP request to the Telegram API and return the parsed JSON body.
    Raises urllib.error.HTTPError, urllib.error.URLError, or ValueError on failure.
    """
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except ssl.SSLError:
        # Fallback: skip cert verification (common inside Docker)
        with urllib.request.urlopen(req, timeout=timeout, context=_build_ctx()) as resp:
            return json.loads(resp.read().decode("utf-8"))


def _read_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        body = (exc.read() or b"").decode("utf-8", errors="ignore")[:600]
        obj = json.loads(body)
        return obj.get("description") or body
    except Exception:
        return getattr(exc, "reason", str(exc))


def get_me(bot_token: str) -> dict:
    """
    Call getMe. Returns the raw Telegram JSON on success.
    Raises HTTPError (bad token → 401) or URLError (network/DNS).
    """
    url = f"{API_BASE}/bot{bot_token}/getMe"
    return _do_request(url)


def set_webhook(bot_token: str, webhook_url: str, secret_token: str = None) -> dict:
    url = f"{API_BASE}/bot{bot_token}/setWebhook"
    payload: dict = {"url": webhook_url}
    if secret_token:
        payload["secret_token"] = secret_token
    return _do_request(url, data=json.dumps(payload).encode(), method="POST")


def delete_webhook(bot_token: str) -> dict:
    url = f"{API_BASE}/bot{bot_token}/deleteWebhook"
    return _do_request(url, data=b"{}", method="POST")


def send_message(bot_token: str, chat_id, text: str) -> dict:
    url = f"{API_BASE}/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": str(text)[:4000]}).encode()
    return _do_request(url, data=payload, method="POST")


def get_webhook_info(bot_token: str) -> dict:
    url = f"{API_BASE}/bot{bot_token}/getWebhookInfo"
    return _do_request(url)


def get_updates(bot_token: str, offset: int = 0, timeout: int = 0, allowed_updates=None) -> dict:
    params = {"timeout": timeout, "offset": offset}
    if allowed_updates:
        params["allowed_updates"] = json.dumps(allowed_updates)
    qs = urllib.parse.urlencode(params)
    url = f"{API_BASE}/bot{bot_token}/getUpdates?{qs}"
    return _do_request(url, timeout=timeout + 10)
