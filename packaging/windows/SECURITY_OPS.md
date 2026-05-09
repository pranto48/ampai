# AmpAI Windows Security / Ops Decisions

## Secrets storage
- Do **not** persist secrets in plaintext project files for desktop runtime.
- Store API keys/tokens in Windows Credential Manager (preferred) or encrypted local secret storage.
- `.env` values should only be defaults/non-sensitive placeholders.

## Localhost-only service binding
- Desktop services (backend, Postgres, Redis) should bind to `127.0.0.1` only.
- Avoid exposing service ports to external interfaces by default.

## Diagnostics and logs
- Logs should be written to `%APPDATA%\\AmpAI\\logs`.
- Provide an **Export diagnostics** action in desktop UI that bundles:
  - launcher logs
  - backend logs
  - version/build metadata
  - sanitized config snapshot (no secrets)

Starter helper:
- `packaging/windows/scripts/export_diagnostics.ps1`

## Auto-update
- v1: optional/manual update path.
- v2: add signed auto-update channel (critical requirement) with staged rollout.
