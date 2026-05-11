# Chat History Canonical Migration Runbook

Canonical conversation storage is `chat_message_store` (or `CHAT_HISTORY_TABLE` override).

## Backfill

```bash
python backend/migrations/backfill_chat_history.py --dry-run
python backend/migrations/backfill_chat_history.py --run
```

## Post-migration validation

```bash
python backend/migrations/backfill_chat_history.py --validate
```

Validation checks:
- legacy vs canonical total row counts
- duplicate detection by `(session_id, message)` in canonical table
- duplicate report by session

## Rollback

1. Take a DB backup/snapshot.
2. Truncate canonical table if needed:
   ```sql
   TRUNCATE TABLE chat_message_store;
   ```
3. Re-run dry-run + run commands.
4. Re-run validation and ensure duplicate count is `0`.
