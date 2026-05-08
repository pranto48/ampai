import base64
import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from cryptography.fernet import Fernet

from database import get_config, set_config

GITHUB_API = "https://api.github.com"
REQUIRED_EDIT_SCOPES = {"contents:write", "pull_requests:write"}


def _json_request(url: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Any:
    data = None
    req_headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if headers:
        req_headers.update(headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url=url, data=data, method=method, headers=req_headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


@dataclass
class GitHubConnection:
    mode: str
    installation_id: Optional[int]
    encrypted_token: Optional[str]
    scopes: List[str]


class GitHubIntegrationService:
    def __init__(self, owner_key: str = "default") -> None:
        self.owner_key = owner_key

    def _cfg_key(self) -> str:
        return f"github:connection:{self.owner_key}"

    def _cipher(self) -> Fernet:
        key = os.getenv("GITHUB_INTEGRATION_ENCRYPTION_KEY") or os.getenv("CONFIG_ENCRYPTION_KEY")
        if not key:
            raise ValueError("Missing GITHUB_INTEGRATION_ENCRYPTION_KEY or CONFIG_ENCRYPTION_KEY")
        return Fernet(key.encode("utf-8"))

    def _encrypt(self, value: str) -> str:
        return self._cipher().encrypt(value.encode("utf-8")).decode("utf-8")

    def _decrypt(self, value: str) -> str:
        return self._cipher().decrypt(value.encode("utf-8")).decode("utf-8")

    def save_connection(self, mode: str, installation_id: Optional[int] = None, token: Optional[str] = None, scopes: Optional[Iterable[str]] = None) -> None:
        payload = {
            "mode": mode,
            "installation_id": installation_id,
            "encrypted_token": self._encrypt(token) if token else None,
            "scopes": sorted(set(scopes or [])),
            "saved_at": int(time.time()),
        }
        set_config(self._cfg_key(), json.dumps(payload))

    def load_connection(self) -> Optional[GitHubConnection]:
        raw = get_config(self._cfg_key(), "")
        if not raw:
            return None
        payload = json.loads(raw)
        return GitHubConnection(payload.get("mode", "app"), payload.get("installation_id"), payload.get("encrypted_token"), payload.get("scopes", []))

    def access_token(self) -> str:
        conn = self.load_connection()
        if not conn or not conn.encrypted_token:
            raise ValueError("GitHub connection is not configured")
        return self._decrypt(conn.encrypted_token)

    def ensure_edit_permissions(self) -> None:
        conn = self.load_connection()
        if not conn:
            raise PermissionError("GitHub connection missing")
        missing = REQUIRED_EDIT_SCOPES.difference(set(conn.scopes))
        if missing:
            raise PermissionError(f"Missing GitHub scopes: {', '.join(sorted(missing))}")

    def list_repos(self) -> List[Dict[str, Any]]:
        token = self.access_token()
        result = _json_request(f"{GITHUB_API}/user/repos?per_page=100", headers={"Authorization": f"Bearer {token}"})
        return result if isinstance(result, list) else []

    def repo_capabilities(self, owner: str, repo: str) -> Dict[str, Any]:
        token = self.access_token()
        data = _json_request(f"{GITHUB_API}/repos/{owner}/{repo}", headers={"Authorization": f"Bearer {token}"})
        return {
            "can_push": bool(data.get("permissions", {}).get("push")),
            "default_branch": data.get("default_branch"),
            "branch_protection_known": bool(data.get("allow_forking") is not None),
            "is_private": bool(data.get("private")),
        }

    def create_branch(self, owner: str, repo: str, new_branch: str, from_branch: str) -> Dict[str, Any]:
        self.ensure_edit_permissions()
        token = self.access_token()
        ref = _json_request(f"{GITHUB_API}/repos/{owner}/{repo}/git/ref/heads/{from_branch}", headers={"Authorization": f"Bearer {token}"})
        sha = ref.get("object", {}).get("sha")
        return _json_request(f"{GITHUB_API}/repos/{owner}/{repo}/git/refs", method="POST", payload={"ref": f"refs/heads/{new_branch}", "sha": sha}, headers={"Authorization": f"Bearer {token}"})

    def read_file_tree(self, owner: str, repo: str, branch: str) -> Dict[str, Any]:
        token = self.access_token()
        return _json_request(f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1", headers={"Authorization": f"Bearer {token}"})

    def read_file_content(self, owner: str, repo: str, path: str, ref: Optional[str] = None) -> str:
        token = self.access_token()
        qp = f"?ref={urllib.parse.quote(ref)}" if ref else ""
        data = _json_request(f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}{qp}", headers={"Authorization": f"Bearer {token}"})
        return base64.b64decode(data.get("content", "")).decode("utf-8") if data.get("content") else ""

    def create_commit_via_contents_api(self, owner: str, repo: str, path: str, content_text: str, message: str, branch: str, sha: Optional[str] = None) -> Dict[str, Any]:
        self.ensure_edit_permissions()
        token = self.access_token()
        payload = {"message": message, "content": base64.b64encode(content_text.encode("utf-8")).decode("utf-8"), "branch": branch}
        if sha:
            payload["sha"] = sha
        return _json_request(f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}", method="PUT", payload=payload, headers={"Authorization": f"Bearer {token}"})

    def open_pr(self, owner: str, repo: str, title: str, head: str, base: str, body: str = "") -> Dict[str, Any]:
        self.ensure_edit_permissions()
        token = self.access_token()
        return _json_request(f"{GITHUB_API}/repos/{owner}/{repo}/pulls", method="POST", payload={"title": title, "head": head, "base": base, "body": body}, headers={"Authorization": f"Bearer {token}"})

    def comment_on_pr_with_ai_summary(self, owner: str, repo: str, pr_number: int, summary: str) -> Dict[str, Any]:
        self.ensure_edit_permissions()
        token = self.access_token()
        return _json_request(f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr_number}/comments", method="POST", payload={"body": f"### AI Summary\n\n{summary}"}, headers={"Authorization": f"Bearer {token}"})
