import json
import os
from collections import defaultdict
from sqlalchemy import create_engine, inspect, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ampai:ampai@db:5432/ampai")
CANONICAL_TABLE = os.getenv("CHAT_HISTORY_TABLE", "chat_message_store")
LEGACY_TABLE = os.getenv("LEGACY_CHAT_TABLE", "message_store")


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


def migrate():
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)

    if not inspector.has_table(LEGACY_TABLE):
        print(f"Legacy table '{LEGACY_TABLE}' not found; nothing to migrate.")
        return

    migrated = 0
    skipped = 0
    failed_sessions = 0

    with engine.begin() as conn:
        _ensure_canonical_table(conn)

    with engine.connect() as conn:
        legacy_rows = conn.execute(
            text(f"SELECT id, session_id, message FROM {LEGACY_TABLE} ORDER BY id ASC")
        ).fetchall()

    by_session = defaultdict(list)
    for _, session_id, raw in legacy_rows:
        if session_id and raw:
            by_session[session_id].append(raw)

    for session_id, rows in by_session.items():
        try:
            with engine.begin() as conn:
                existing_payloads = {
                    row[0]
                    for row in conn.execute(
                        text(
                            f"SELECT message FROM {CANONICAL_TABLE} WHERE session_id = :session_id"
                        ),
                        {"session_id": session_id},
                    ).fetchall()
                }

                for idx, raw in enumerate(rows):
                    payload = None
                    try:
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict) and parsed.get("type") in {"human", "ai"}:
                            payload = raw
                    except (TypeError, json.JSONDecodeError):
                        payload = None

                    if payload is None:
                        # Legacy plain-text fallback: alternate human/ai to preserve sequence.
                        msg_type = "human" if idx % 2 == 0 else "ai"
                        payload = _canonical_payload(msg_type, raw)

                    if payload in existing_payloads:
                        skipped += 1
                        continue

                    conn.execute(
                        text(
                            f"INSERT INTO {CANONICAL_TABLE} (session_id, message) VALUES (:session_id, :message)"
                        ),
                        {"session_id": session_id, "message": payload},
                    )
                    existing_payloads.add(payload)
                    migrated += 1
        except Exception as exc:
            failed_sessions += 1
            print(f"Failed to migrate session '{session_id}': {exc}")

    print(
        f"Migration complete. migrated={migrated} skipped={skipped} "
        f"failed_sessions={failed_sessions} canonical_table={CANONICAL_TABLE}"
    )


if __name__ == "__main__":
    migrate()
