from __future__ import annotations

import base64
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional
from urllib import error, request

JobStatus = Literal[
    "queued",
    "planning",
    "editing",
    "validating",
    "pushing",
    "pr_opened",
    "failed",
]


@dataclass
class RepoTargetContext:
    owner: str
    repo: str
    base_branch: str
    allow_paths: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    fetch_paths: List[str] = field(default_factory=list)


@dataclass
class PatchHunk:
    file_path: str
    content: str


@dataclass
class EditPlan:
    files_to_modify: List[str]
    patch_hunks: List[PatchHunk]
    rationale: str
    commit_message: Optional[str] = None
    summary: Optional[str] = None
    risk_notes: Optional[str] = None


@dataclass
class OrchestratorJob:
    id: str
    status: JobStatus
    phase: JobStatus
    context: RepoTargetContext
    instruction: str
    created_at: str
    updated_at: str
    branch_name: Optional[str] = None
    pr_url: Optional[str] = None
    changed_files: List[str] = field(default_factory=list)
    error: Optional[str] = None


class RepoEditOrchestrator:
    def __init__(
        self,
        github_token: str,
        planner: Callable[[str, RepoTargetContext, Dict[str, str]], EditPlan],
        api_base: str = "https://api.github.com",
    ) -> None:
        self.github_token = github_token
        self.planner = planner
        self.api_base = api_base.rstrip("/")

    def run(self, instruction: str, context: RepoTargetContext) -> OrchestratorJob:
        job = self._new_job(instruction, context)
        try:
            job = self._set_phase(job, "planning")
            snapshot = self._fetch_snapshot(context)
            plan = self.planner(instruction, context, snapshot)

            job = self._set_phase(job, "editing")
            self._validate_plan(plan, context)

            job = self._set_phase(job, "validating")
            workspace = self._apply_plan(plan, snapshot)

            job = self._set_phase(job, "pushing")
            branch_name = self._branch_name(instruction)
            commit_message = self._build_commit_message(plan, instruction)
            changed_files = sorted(plan.files_to_modify)
            self._push_branch(context, branch_name, workspace, commit_message)

            pr_payload = self._build_pr_payload(plan, context, branch_name, changed_files, instruction)
            pr_response = self._open_pr(context, pr_payload)

            job.status = "pr_opened"
            job.phase = "pr_opened"
            job.branch_name = branch_name
            job.pr_url = pr_response.get("html_url")
            job.changed_files = changed_files
            job.updated_at = datetime.now(timezone.utc).isoformat()
            return job
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.phase = "failed"
            job.error = str(exc)
            job.updated_at = datetime.now(timezone.utc).isoformat()
            return job

    def _new_job(self, instruction: str, context: RepoTargetContext) -> OrchestratorJob:
        now = datetime.now(timezone.utc).isoformat()
        return OrchestratorJob(
            id=f"job_{int(datetime.now(timezone.utc).timestamp())}",
            status="queued",
            phase="queued",
            context=context,
            instruction=instruction,
            created_at=now,
            updated_at=now,
        )

    def _set_phase(self, job: OrchestratorJob, phase: JobStatus) -> OrchestratorJob:
        job.status = phase
        job.phase = phase
        job.updated_at = datetime.now(timezone.utc).isoformat()
        return job

    def _fetch_snapshot(self, context: RepoTargetContext) -> Dict[str, str]:
        paths = context.fetch_paths or context.allow_paths
        if not paths:
            raise ValueError("No fetch paths configured for repository snapshot")
        snapshot: Dict[str, str] = {}
        for path in paths:
            payload = self._github_get(
                f"/repos/{context.owner}/{context.repo}/contents/{path}",
                params={"ref": context.base_branch},
            )
            if isinstance(payload, list):
                for entry in payload:
                    if entry.get("type") == "file":
                        snapshot[entry["path"]] = self._fetch_file_blob(entry["path"], context)
            elif payload.get("type") == "file":
                snapshot[payload["path"]] = base64.b64decode(payload["content"]).decode("utf-8")
        return snapshot

    def _fetch_file_blob(self, path: str, context: RepoTargetContext) -> str:
        payload = self._github_get(
            f"/repos/{context.owner}/{context.repo}/contents/{path}",
            params={"ref": context.base_branch},
        )
        return base64.b64decode(payload["content"]).decode("utf-8")

    def _validate_plan(self, plan: EditPlan, context: RepoTargetContext) -> None:
        allowed = tuple(context.allow_paths)
        for hunk in plan.patch_hunks:
            if allowed and not hunk.file_path.startswith(allowed):
                raise ValueError(f"Path not allowed: {hunk.file_path}")
            if hunk.file_path.lower().endswith((".png", ".jpg", ".gif", ".pdf", ".zip")):
                raise ValueError(f"Binary-like target rejected: {hunk.file_path}")
            if len(hunk.content.encode("utf-8")) > int(context.constraints.get("max_file_bytes", 500_000)):
                raise ValueError(f"Patched file too large: {hunk.file_path}")
            self._syntax_heuristics(hunk.file_path, hunk.content)

    def _syntax_heuristics(self, path: str, content: str) -> None:
        if path.endswith(".py"):
            if content.count("(") != content.count(")"):
                raise ValueError(f"Parentheses mismatch in {path}")
        if path.endswith((".json", ".jsonc")):
            try:
                json.loads(content)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    def _apply_plan(self, plan: EditPlan, snapshot: Dict[str, str]) -> str:
        workspace = tempfile.mkdtemp(prefix="ampai_repo_edit_")
        for file_path, content in snapshot.items():
            target = Path(workspace) / file_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        for hunk in plan.patch_hunks:
            target = Path(workspace) / hunk.file_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(hunk.content, encoding="utf-8")
        return workspace

    def _build_commit_message(self, plan: EditPlan, instruction: str) -> str:
        if plan.commit_message and plan.commit_message.strip():
            return plan.commit_message.strip()
        return f"chore(ai): apply requested repo edits\n\nInstruction: {instruction[:180]}"

    def _branch_name(self, instruction: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", instruction.lower()).strip("-")[:42] or "update"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"ai/{stamp}-{slug}"

    def _build_pr_payload(
        self,
        plan: EditPlan,
        context: RepoTargetContext,
        branch_name: str,
        changed_files: List[str],
        instruction: str,
    ) -> Dict[str, str]:
        summary = plan.summary or f"Automated repository edits for: {instruction}"
        risks = plan.risk_notes or "Review generated edits carefully before merge."
        files_list = "\n".join(f"- `{file}`" for file in changed_files)
        body = (
            f"## Summary\n{summary}\n\n"
            f"## Rationale\n{plan.rationale}\n\n"
            f"## Risk Notes\n{risks}\n\n"
            f"## Changed Files\n{files_list}\n"
        )
        return {
            "title": f"AI edits: {instruction[:72]}",
            "head": branch_name,
            "base": context.base_branch,
            "body": body,
        }

    def _push_branch(self, context: RepoTargetContext, branch_name: str, workspace: str, commit_message: str) -> None:
        # Stub integration point for local git flow; implement with subprocess in deployment.
        _ = (context, branch_name, workspace, commit_message)
        shutil.rmtree(workspace, ignore_errors=True)

    def _open_pr(self, context: RepoTargetContext, payload: Dict[str, str]) -> Dict[str, Any]:
        return self._github_post(f"/repos/{context.owner}/{context.repo}/pulls", payload)

    def _github_get(self, path: str, params: Optional[Dict[str, str]] = None) -> Any:
        query = ""
        if params:
            encoded = "&".join(f"{k}={v}" for k, v in params.items())
            query = f"?{encoded}"
        req = request.Request(f"{self.api_base}{path}{query}", headers=self._headers())
        try:
            with request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub GET failed {exc.code}: {body}") from exc

    def _github_post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.api_base}{path}",
            data=body,
            headers={**self._headers(), "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub POST failed {exc.code}: {raw}") from exc

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.github_token}",
            "User-Agent": os.getenv("AMPAI_GITHUB_UA", "ampai-repo-orchestrator"),
            "X-GitHub-Api-Version": "2022-11-28",
        }
