import argparse
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple

from sqlalchemy import create_engine, inspect, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ampai:ampai@db:5432/ampai")
CANONICAL_TABLE = os.getenv("CHAT_HISTORY_TABLE", "chat_message_store")
LEGACY_TABLE = os.getenv("LEGACY_CHAT_TABLE", "message_store")


@dataclass
class MigrationStats:
    migrated: int = 0
    skipped_existing: int = 0
    malformed_rows: int = 0
    duplicate_rows_seen: int = 0
    sessions_processed: int = 0
    failed_sessions: int = 0


def _canonical_payload(msg_type: str, content: str) -> str:
    return json.dumps(
        {
            "type": msg_type,
            "data": {
                "content": content,
                "additional_kwargs": {},
                "response_metadata": {},
                "type": msg_type,
                "name": None,
                "id": None,
            },
        }
    )


def _ensure_canonical_table(conn):
    conn.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS {CANONICAL_TABLE} (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                message TEXT NOT NULL
            )
            """
        )
    )


def _collect_duplicates(conn, table_name: str) -> Dict[str, int]:
    rows = conn.execute(
        text(
            f"SELECT session_id, message, COUNT(*) AS cnt "
            f"FROM {table_name} "
            "WHERE session_id IS NOT NULL "
            "GROUP BY session_id, message HAVING COUNT(*) > 1"
        )
    ).fetchall()
    counts: Dict[str, int] = {}
    for session_id, _message, count in rows:
        counts[session_id] = counts.get(session_id, 0) + (int(count) - 1)
    return counts


def _print_duplicate_report(label: str, duplicates: Dict[str, int]):
    total = sum(duplicates.values())
    print(f"{label}: sessions_with_duplicates={len(duplicates)} duplicate_rows={total}")
    for session_id in sorted(duplicates.keys()):
        print(f"  - {session_id}: {duplicates[session_id]}")


def _parse_payload(raw: str, fallback_index: int) -> Tuple[str, bool]:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and parsed.get("type") in {"human", "ai"}:
            return raw, False
    except (TypeError, json.JSONDecodeError):
        pass

    msg_type = "human" if fallback_index % 2 == 0 else "ai"
    return _canonical_payload(msg_type, raw), True


def migrate(dry_run: bool = False) -> MigrationStats:
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)
    stats = MigrationStats()

    if not inspector.has_table(LEGACY_TABLE):
        print(f"Legacy table '{LEGACY_TABLE}' not found; nothing to migrate.")
        return stats

    with engine.begin() as conn:
        _ensure_canonical_table(conn)

    with engine.connect() as conn:
        legacy_duplicates = _collect_duplicates(conn, LEGACY_TABLE)
        canonical_before = _collect_duplicates(conn, CANONICAL_TABLE)
        _print_duplicate_report("legacy_duplicates", legacy_duplicates)
        _print_duplicate_report("canonical_duplicates_before", canonical_before)

        legacy_rows = conn.execute(
            text(f"SELECT id, session_id, message FROM {LEGACY_TABLE} ORDER BY id ASC")
        ).fetchall()

    by_session: Dict[str, List[str]] = defaultdict(list)
    for _, session_id, raw in legacy_rows:
        if session_id and raw:
            by_session[session_id].append(raw)

    for session_id, rows in by_session.items():
        stats.sessions_processed += 1
        try:
            with engine.begin() as conn:
                existing_payloads = {
                    row[0]
                    for row in conn.execute(
                        text(f"SELECT message FROM {CANONICAL_TABLE} WHERE session_id = :session_id"),
                        {"session_id": session_id},
                    ).fetchall()
                }

                for idx, raw in enumerate(rows):
                    payload, was_malformed = _parse_payload(raw, idx)
                    if was_malformed:
                        stats.malformed_rows += 1

                    if payload in existing_payloads:
                        stats.skipped_existing += 1
                        stats.duplicate_rows_seen += 1
                        continue

                    if not dry_run:
                        conn.execute(
                            text(f"INSERT INTO {CANONICAL_TABLE} (session_id, message) VALUES (:session_id, :message)"),
                            {"session_id": session_id, "message": payload},
                        )
                    existing_payloads.add(payload)
                    stats.migrated += 1
        except Exception as exc:
            stats.failed_sessions += 1
            print(f"Failed to migrate session '{session_id}': {exc}")

    with engine.connect() as conn:
        canonical_after = _collect_duplicates(conn, CANONICAL_TABLE)
        _print_duplicate_report("canonical_duplicates_after", canonical_after)

    print(
        "Migration complete. "
        f"dry_run={dry_run} migrated={stats.migrated} skipped_existing={stats.skipped_existing} "
        f"malformed_rows={stats.malformed_rows} duplicate_rows_seen={stats.duplicate_rows_seen} "
        f"sessions_processed={stats.sessions_processed} failed_sessions={stats.failed_sessions} "
        f"canonical_table={CANONICAL_TABLE}"
    )
    return stats


def validate() -> int:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        legacy_count = conn.execute(text(f"SELECT COUNT(*) FROM {LEGACY_TABLE}")).scalar() or 0
        canonical_count = conn.execute(text(f"SELECT COUNT(*) FROM {CANONICAL_TABLE}")).scalar() or 0
        duplicates = _collect_duplicates(conn, CANONICAL_TABLE)

    print(
        f"Validation summary: legacy_count={legacy_count} canonical_count={canonical_count} "
        f"sessions_with_duplicates={len(duplicates)} duplicate_rows={sum(duplicates.values())}"
    )
    if duplicates:
        _print_duplicate_report("canonical_duplicates_validate", duplicates)
        return 1
    return 0


def print_rollback_instructions():
    print("\nRollback instructions:")
    print("1) Take a DB backup before rollback.")
    print(f"2) Optional: truncate canonical table: TRUNCATE TABLE {CANONICAL_TABLE};")
    print(
        f"3) Re-import from legacy with dry run first: "
        f"python backend/migrations/backfill_chat_history.py --dry-run"
    )
    print(
        f"4) Re-run migration: python backend/migrations/backfill_chat_history.py --run"
    )
    print(
        f"5) Re-run validation: python backend/migrations/backfill_chat_history.py --validate"
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Backfill canonical SQL chat history from legacy table.")
    parser.add_argument("--run", action="store_true", help="Execute migration writes (default is dry run).")
    parser.add_argument("--dry-run", action="store_true", help="Run migration without writes.")
    parser.add_argument("--validate", action="store_true", help="Run post-migration validation checks only.")
    parser.add_argument("--rollback-help", action="store_true", help="Print rollback instructions.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.rollback_help:
        print_rollback_instructions()
        raise SystemExit(0)
    if args.validate:
        raise SystemExit(validate())

    do_dry_run = True
    if args.run:
        do_dry_run = False
    elif args.dry_run:
        do_dry_run = True

    migrate(dry_run=do_dry_run)
    print_rollback_instructions()
