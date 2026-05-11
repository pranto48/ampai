import json
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo


TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
MESSAGES_URL = "https://graph.microsoft.com/v1.0/me/messages"


def refresh_access_token(credentials: Dict[str, Any]) -> Dict[str, Any]:
    tenant_id = credentials.get("tenant_id") or "common"
    token_url = TOKEN_URL_TEMPLATE.format(tenant_id=tenant_id)
    payload = urllib.parse.urlencode(
        {
            "client_id": credentials.get("client_id", ""),
            "client_secret": credentials.get("client_secret", ""),
            "refresh_token": credentials.get("refresh_token", ""),
            "grant_type": "refresh_token",
            "scope": "offline_access Mail.Read",
        }
    ).encode("utf-8")
    req = urllib.request.Request(token_url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    credentials["access_token"] = data["access_token"]
    credentials["expires_at"] = int(time.time()) + int(data.get("expires_in", 3600))
    if data.get("refresh_token"):
        credentials["refresh_token"] = data["refresh_token"]
    return credentials


def _request_json(url: str, access_token: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_todays_messages(access_token: str, tz: str = "UTC", max_results: int = 25) -> List[Dict[str, str]]:
    tzinfo = ZoneInfo(tz)
    start_local = datetime.now(tzinfo).replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local.replace(hour=23, minute=59, second=59)
    start_iso = start_local.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z")
    end_iso = end_local.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z")

    q = {
        "$top": str(max_results),
        "$select": "id,subject,from,receivedDateTime,bodyPreview",
        "$orderby": "receivedDateTime desc",
        "$filter": f"receivedDateTime ge {start_iso} and receivedDateTime le {end_iso}",
    }
    url = f"{MESSAGES_URL}?{urllib.parse.urlencode(q)}"
    listing = _request_json(url, access_token)

    output: List[Dict[str, str]] = []
    for item in listing.get("value", []):
        output.append(
            {
                "provider": "outlook",
                "id": item.get("id", ""),
                "from": (item.get("from", {}).get("emailAddress", {}).get("address", "")),
                "subject": item.get("subject") or "(No subject)",
                "date": item.get("receivedDateTime", ""),
                "snippet": item.get("bodyPreview", ""),
            }
        )
    return output

