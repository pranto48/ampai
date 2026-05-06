# AmpAI Migration Guide (Desktop ↔ Docker)

Use this flow when moving environments.

## Export from source
1. Open AmpAI in source environment.
2. Go to backup/export tools.
3. Export sessions, memories, settings, and media assets.
4. Save archive locally.

## Import to destination
1. Start destination environment (Desktop or Docker).
2. Open restore/import tools.
3. Upload exported archive.
4. Validate user logins, chats, memory index, and integrations.

## Post-migration checks
- Auth/login/admin works
- Chat history visible
- Telegram mapping intact
- Media files available
- Scheduler/background jobs active
