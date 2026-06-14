from database import engine
from sqlalchemy import text
import json

session_id = "302e4350-4326-4a7d-bf2b-ad6d6fb4b829"

print("--- DB Connection ---")
print(engine)

with engine.connect() as conn:
    print("\n--- session_metadata ---")
    meta_rows = conn.execute(
        text("SELECT * FROM session_metadata WHERE session_id = :sid"),
        {"sid": session_id}
    ).fetchall()
    print(meta_rows)

    print("\n--- chat_message_store count ---")
    cnt_rows = conn.execute(
        text("SELECT COUNT(*) FROM chat_message_store WHERE session_id = :sid"),
        {"sid": session_id}
    ).fetchall()
    print(cnt_rows)

    print("\n--- message_store count ---")
    msg_cnt = conn.execute(
        text("SELECT COUNT(*) FROM message_store WHERE session_id = :sid"),
        {"sid": session_id}
    ).fetchall()
    print(msg_cnt)

    print("\n--- All distinct session IDs in chat_message_store ---")
    distinct_sids = conn.execute(
        text("SELECT DISTINCT session_id FROM chat_message_store")
    ).fetchall()
    print(distinct_sids)

print("\n--- get_all_sessions() output ---")
from database import get_all_sessions
print(get_all_sessions())
