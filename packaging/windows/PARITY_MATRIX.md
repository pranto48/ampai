# AmpAI Functional Parity Matrix (Docker vs Windows Desktop)

This checklist is the acceptance gate for keeping both distributions functionally aligned.

## Test environments
- Docker mode: `docker compose up -d --build`
- Windows mode: installed `.exe` package launched via desktop shell/launcher

## Parity matrix

| Capability | Docker | Windows Desktop | Verification method | Env/config abstraction notes |
|---|---|---|---|---|
| Auth / login / admin | ☐ | ☐ | Login/logout, admin route access, user CRUD | Keep JWT/auth settings in env (`JWT_SECRET`, expiry values). |
| Chat + history persistence | ☐ | ☐ | Send chat turns, refresh app, verify sessions/messages persist | Abstract `DATABASE_URL`, `REDIS_URL`, session store paths. |
| Telegram webhook/polling | ☐ | ☐ | Enable integration, send test message, confirm response + session visibility | Keep bot token/webhook keys in config/env, normalize callback URL per mode. |
| Memory indexing / curation | ☐ | ☐ | Trigger memory capture + recall search; confirm indexing tasks run | Abstract index/db path and scheduler intervals via env. |
| Backup / restore flows | ☐ | ☐ | Create backup profile, run backup, restore into clean instance | Abstract filesystem target roots (`backup_root`) by runtime mode. |
| File uploads / media assets | ☐ | ☐ | Upload file/image, reference in chat, reload and verify retrieval | Abstract media upload directory and max-size settings. |
| Background jobs / scheduler | ☐ | ☐ | Verify recurring jobs execute and telemetry/log events are created | Abstract schedule config and timezone settings. |
| Config/settings secrets handling | ☐ | ☐ | Save/update keys in UI, restart app, verify masking/persistence | In Windows, use local secure storage; Docker via env/secret mounts. |

## Path/URL/permission abstraction requirements

All platform-sensitive values must be provided through environment/config indirection:

- **Service URLs/ports**
  - `PORT`
  - `DATABASE_URL`
  - `REDIS_URL`
  - integration callback/base URLs

- **Filesystem roots**
  - upload/media directory
  - backup/export/import directories
  - local DB/index paths where applicable
  - logs directory

- **Permissions/runtime behavior**
  - run-as user and writable directories
  - startup behavior (desktop auto-start vs container restart policy)
  - TLS/proxy/webhook assumptions by environment

## Execution protocol

1. Run Docker checks and mark column values with ✅/❌.
2. Run Windows desktop checks and mark column values with ✅/❌.
3. For each ❌, log: capability, failure symptom, env mismatch, and fix PR.
4. Release gating: all matrix rows must be ✅ in both modes.
