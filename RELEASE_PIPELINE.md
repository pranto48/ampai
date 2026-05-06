# AmpAI Parallel CI/CD Release Pipeline

## Versioning policy
- Use semantic version tags: `vMAJOR.MINOR.PATCH` (example: `v1.4.0`).
- Docker and Windows pipelines derive the same normalized version (`1.4.0`) from the same tag.

## Docker release channel
Workflow: `.github/workflows/release-docker.yml`

Pipeline:
1. Build image
2. Push `ghcr.io/<owner>/ampai:<semver>` and `:latest`
3. Publish `docker-compose.yml` and release notes as artifacts
4. Attach compose + release notes to GitHub Release

## Windows release channel
Workflow: `.github/workflows/release-windows.yml`

Pipeline:
1. Build frontend
2. Package backend executable (PyInstaller)
3. Stage bundled dependencies/runtime
4. Build installer `.exe` with Inno Setup
5. Sign installer (when signing secrets are configured)
6. Upload installer artifact and publish to GitHub Release

## Website/CDN publishing
- After GitHub Release, mirror installer artifact and release notes to website CDN using your deployment automation.
- Keep filenames versioned (e.g., `AmpAI-Setup-1.4.0.exe`).
