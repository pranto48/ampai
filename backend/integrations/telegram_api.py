import json
import urllib.error
import urllib.request


API_BASE = "https://api.telegram.org"


def get_me(bot_token):
    url = f"{API_BASE}/bot{bot_token}/getMe"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError):
        return {"ok": False, "error": "request_failed"}


def set_webhook(bot_token, webhook_url):
    url = f"{API_BASE}/bot{bot_token}/setWebhook"
    data = json.dumps({"url": webhook_url}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError):
        return {"ok": False, "error": "request_failed"}


def delete_webhook(bot_token):
    url = f"{API_BASE}/bot{bot_token}/deleteWebhook"
    req = urllib.request.Request(url, data=b"{}", method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError):
        return {"ok": False, "error": "request_failed"}


def send_message(bot_token, chat_id, text):
    url = f"{API_BASE}/bot{bot_token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError):
        return {"ok": False, "error": "request_failed"}
