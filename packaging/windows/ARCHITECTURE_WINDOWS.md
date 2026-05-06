# AmpAI Windows Target Architecture (v1)

## Product shell
- Desktop shell: **Tauri** (`desktop/tauri`) for a smaller native installer footprint.

## Runtime services
- Backend service: packaged Python API binary (`PyInstaller`) produced by `packaging/windows/scripts/build_backend.ps1`.
- Data services: bundled local **Postgres + Redis** binaries for parity with Docker behavior.
- UI: existing frontend static build copied to staged installer assets.

## v1 parity goals
- Reuse the same backend/frontend code as Docker deployment.
- Keep Postgres + Redis behavior unchanged.
- Manage all local services from desktop launcher script.

## Installer packaging layout
- `AmpAI Desktop.exe` (desktop shell launcher)
- `backend/` packaged runtime
- `runtime/postgres/` portable postgres + data directory
- `runtime/redis/` redis binary + config
- `frontend/` static assets
- `config/.env` template

## Startup flow
1. Launcher starts Redis.
2. Launcher starts Postgres.
3. Launcher exports environment variables.
4. Launcher starts backend binary.
5. Health check passes then desktop shell opens UI.

## Installer strategy
- Inno Setup (`packaging/windows/installer/AmpAI.iss`).
- Supports install path, start menu shortcut, desktop shortcut.
- Optional run at startup task.
- Uninstall keeps user data stored in `%APPDATA%\AmpAI` by default.
