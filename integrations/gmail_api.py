import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List


TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


def refresh_access_token(credentials: Dict[str, Any]) -> Dict[str, Any]:
    payload = urllib.parse.urlencode(
        {
            "client_id": credentials.get("client_id", ""),
            "client_secret": credentials.get("client_secret", ""),
            "refresh_token": credentials.get("refresh_token", ""),
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    req = urllib.request.Request(TOKEN_URL, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    credentials["access_token"] = data["access_token"]
    credentials["expires_at"] = int(time.time()) + int(data.get("expires_in", 3600))
    return credentials


def _request_json(url: str, access_token: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_todays_messages(access_token: str, tz: str = "UTC", max_results: int = 25) -> List[Dict[str, str]]:
    _ = tz  # Kept for a shared adapter signature.
    start_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end_utc = start_utc + timedelta(days=1)
    query = f"after:{int(start_utc.timestamp())} before:{int(end_utc.timestamp())}"
    url = f"{API_BASE}/messages?{urllib.parse.urlencode({'q': query, 'maxResults': max_results})}"
    listing = _request_json(url, access_token)

    output: List[Dict[str, str]] = []
    for item in listing.get("messages", []):
        msg = _request_json(f"{API_BASE}/messages/{item['id']}?format=metadata", access_token)
        headers = msg.get("payload", {}).get("headers", [])
        header_map = {h.get("name", "").lower(): h.get("value", "") for h in headers}
        snippet = msg.get("snippet", "")
        output.append(
            {
                "provider": "gmail",
                "id": msg.get("id", ""),
                "from": header_map.get("from", ""),
                "subject": header_map.get("subject", "(No subject)"),
                "date": header_map.get("date", ""),
                "snippet": snippet,
            }
        )
    return output

