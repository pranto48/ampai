from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


class RepoEditPolicyError(ValueError):
    """Raised when proposed edits violate repository editing policy."""


@dataclass
class PolicyDecision:
    allowed: bool
    risk_score: int
    labels: List[str]
    rejection_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    high_risk_files: List[str] = field(default_factory=list)


class RepoEditPolicy:
    DEFAULT_DENY_PREFIXES = (
        ".github/workflows/",
        "infra/",
        "terraform/",
        "ansible/",
        "k8s/",
    )
    DEFAULT_DENY_PATTERNS = (
        ".env",
        ".pem",
        ".p12",
        ".pfx",
        "id_rsa",
        "id_ed25519",
        "credentials",
        "secret",
        "secrets",
        "private_key",
    )
    DEFAULT_LOCKFILES = ("package-lock.json", "poetry.lock", "Pipfile.lock", "yarn.lock", "pnpm-lock.yaml")
    HIGH_RISK_KEYWORDS = ("auth", "billing", "infra", "migration")

    def evaluate(self, plan: Any, context: Any) -> PolicyDecision:
        constraints = getattr(context, "constraints", {}) or {}
        files: List[str] = sorted(set(getattr(plan, "files_to_modify", [])))
        hunk_map = {h.file_path: h for h in getattr(plan, "patch_hunks", [])}

        rejection_reasons: List[str] = []
        warnings: List[str] = []
        risk = 0

        allow_paths = tuple(getattr(context, "allow_paths", []) or [])
        deny_prefixes = tuple(constraints.get("deny_prefixes", self.DEFAULT_DENY_PREFIXES))
        deny_patterns = tuple(constraints.get("deny_patterns", self.DEFAULT_DENY_PATTERNS))
        allow_ci = bool(constraints.get("allow_ci_config", False))
        allow_lockfiles = bool(constraints.get("allow_lockfiles", False))

        for path in files:
            normalized = path.lower()
            name = Path(path).name.lower()
            if allow_paths and not path.startswith(allow_paths):
                rejection_reasons.append(f"Path not in allowlist: {path}")
            if any(path.startswith(prefix) for prefix in deny_prefixes):
                rejection_reasons.append(f"Path blocked by deny-prefix policy: {path}")
            if not allow_ci and path.startswith(".github/"):
                rejection_reasons.append(f"CI/CD config edit blocked unless allow_ci_config=true: {path}")
            if not allow_lockfiles and name in {lock.lower() for lock in self.DEFAULT_LOCKFILES}:
                rejection_reasons.append(f"Lockfile edit blocked unless allow_lockfiles=true: {path}")
            if any(token in normalized for token in deny_patterns):
                rejection_reasons.append(f"Sensitive/credential-like path blocked: {path}")

        max_files = int(constraints.get("max_files_changed", 25))
        if len(files) > max_files:
            rejection_reasons.append(f"File change count {len(files)} exceeds max_files_changed={max_files}")

        line_total = 0
        for file_path in files:
            hunk = hunk_map.get(file_path)
            if not hunk:
                continue
            line_total += len(hunk.content.splitlines())
        max_lines = int(constraints.get("max_lines_changed", 1200))
        if line_total > max_lines:
            rejection_reasons.append(f"Line change count {line_total} exceeds max_lines_changed={max_lines}")

        high_risk_files = self._detect_high_risk(files)
        if high_risk_files:
            risk += 60
            warnings.append(f"High-risk area edits detected: {', '.join(high_risk_files)}")

        if any("Path blocked" in reason or "Sensitive/credential" in reason for reason in rejection_reasons):
            risk += 40
        if len(files) > 10:
            risk += 15
        if line_total > 400:
            risk += 15

        requires_confirmation = bool(high_risk_files) and not bool(constraints.get("user_confirmed_high_risk", False))
        if requires_confirmation:
            rejection_reasons.append(
                "Explicit user confirmation required for high-risk edits (set constraints.user_confirmed_high_risk=true)"
            )

        labels = ["ai-generated"]
        if risk >= 60:
            labels.append("high-risk")
        if rejection_reasons or requires_confirmation or risk >= 40:
            labels.append("needs-human-review")

        decision = PolicyDecision(
            allowed=not rejection_reasons,
            risk_score=risk,
            labels=labels,
            rejection_reasons=rejection_reasons,
            warnings=warnings,
            requires_confirmation=requires_confirmation,
            high_risk_files=high_risk_files,
        )
        self._write_audit_log(context=context, plan=plan, decision=decision, line_total=line_total)
        return decision

    def _detect_high_risk(self, files: List[str]) -> List[str]:
        matched: Set[str] = set()
        for path in files:
            low = path.lower()
            if any(keyword in low for keyword in self.HIGH_RISK_KEYWORDS):
                matched.add(path)
        return sorted(matched)

    def _write_audit_log(self, context: Any, plan: Any, decision: PolicyDecision, line_total: int) -> None:
        constraints = getattr(context, "constraints", {}) or {}
        log_path = constraints.get("audit_log_path") or os.getenv("AMPAI_REPO_EDIT_AUDIT_LOG", "backend/logs/repo_edit_policy_audit.log")
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "owner": getattr(context, "owner", None),
            "repo": getattr(context, "repo", None),
            "base_branch": getattr(context, "base_branch", None),
            "files_to_modify": getattr(plan, "files_to_modify", []),
            "risk_score": decision.risk_score,
            "labels": decision.labels,
            "allowed": decision.allowed,
            "requires_confirmation": decision.requires_confirmation,
            "rejection_reasons": decision.rejection_reasons,
            "warnings": decision.warnings,
            "line_total": line_total,
        }
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
