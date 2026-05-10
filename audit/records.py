from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import text

from database import engine


def ensure_ai_audit_table() -> None:
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS ai_edit_audit_records (
                id BIGSERIAL PRIMARY KEY,
                trace_id TEXT NOT NULL,
                workspace TEXT NOT NULL,
                repository TEXT NOT NULL,
                username TEXT NOT NULL,
                prompt TEXT NOT NULL,
                selected_files TEXT NOT NULL,
                model_provider TEXT NOT NULL,
                commit_sha TEXT,
                pr_url TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        ))


def write_immutable_record(record: Dict[str, Any]) -> None:
    ensure_ai_audit_table()
    with engine.begin() as conn:
        conn.execute(text(
            """
            INSERT INTO ai_edit_audit_records
            (trace_id, workspace, repository, username, prompt, selected_files, model_provider, commit_sha, pr_url, created_at)
            VALUES
            (:trace_id, :workspace, :repository, :username, :prompt, :selected_files, :model_provider, :commit_sha, :pr_url, :created_at)
            """
        ), {
            "trace_id": record["trace_id"],
            "workspace": record["workspace"],
            "repository": record["repository"],
            "username": record["username"],
            "prompt": record["prompt"],
            "selected_files": json.dumps(record.get("selected_files", [])),
            "model_provider": record["model_provider"],
            "commit_sha": record.get("commit_sha"),
            "pr_url": record.get("pr_url"),
            "created_at": record.get("created_at") or datetime.now(timezone.utc),
        })


def list_activity_report(limit: int = 500) -> List[Dict[str, Any]]:
    ensure_ai_audit_table()
    with engine.begin() as conn:
        rows = conn.execute(text(
            """
            SELECT workspace, repository,
                   COUNT(*) AS total_edits,
                   MAX(created_at) AS last_activity_at
            FROM ai_edit_audit_records
            GROUP BY workspace, repository
            ORDER BY last_activity_at DESC
            LIMIT :limit
            """
        ), {"limit": limit}).mappings().all()
        return [dict(row) for row in rows]
