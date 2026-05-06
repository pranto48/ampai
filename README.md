# AmpAI

AmpAI is a local-first autonomous agent platform focused on:

- conversational assistance without requiring cloud AI APIs,
- curated long-term memory,
- autonomous skill learning,
- self-improving skill rollouts,
- and cross-session recall.

---

## Vision (Hermes-style direction)

AmpAI is being built toward a Hermes-agent-like workflow:

1. **Local-first chat** (no mandatory OpenAI/Gemini key)
2. **Agent-curated memory with periodic nudges**
3. **Autonomous skill creation after complex tasks**
4. **Skill self-improvement during real usage**
5. **FTS5 session recall + summarization across sessions**

---

## Current roadmap status

### Phase 1 — Foundation ✅
- Local-only mode controls (`local_only_mode`)
- Curator nudge persistence + API
- Scheduled nudge generation for overdue tasks
- UI badges and acknowledge flows

### Phase 2 — Learning ✅
- Skill registry tables (`agent_skills`, `skill_versions`)
- Session-based skill synthesis API
- Skill listing API

### Phase 3 — Optimization ✅
- Skill run telemetry (`skill_runs`)
- Performance evaluation + optimize endpoint
- Canary rollout metadata
- Manual + automatic rollback/promotion guard

### Phase 4 — Recall ✅
- SQLite FTS5 cross-session indexing
- Recall search API
- Recall summary panel in chat UI

> Note: Some parts are intentionally lightweight today and will be hardened further with richer evaluation logic and stronger provenance/grounding controls.

---

## Architecture overview

### Backend
- **FastAPI** app (`backend/main.py`)
- **Postgres** for core operational data (users, memory metadata, tasks, skills)
- **Redis** for short-term message history and queue-like workflows
- **SQLite FTS5** for cross-session lexical recall (`backend/session_recall.py`)
- **Scheduler** (`backend/scheduler.py`) for nudges and rollout guards

### Frontend
- React/TSX chat interface in `frontend/chat.tsx`
- Model/provider selection, nudge panel, and recall search widgets

---

## Distribution options (product shape)

AmpAI ships in two aligned options that share the same backend/frontend codebase:

### Option A — AmpAI Desktop for Windows (.exe)
- One-click installer for end users
- Launches local UI automatically
- Manages local services (backend + runtime dependencies)
- Supports optional start-on-boot setup in installer/launcher policy

Starter assets in this repo:
- Tauri desktop scaffold: `desktop/tauri/`
- Windows build/packaging scripts: `packaging/windows/scripts/`
- Inno Setup installer spec: `packaging/windows/installer/AmpAI.iss`
- Windows release workflow: `.github/workflows/release-windows.yml`
- Windows target architecture spec: `packaging/windows/ARCHITECTURE_WINDOWS.md`

### Option B — AmpAI Docker
- For devops/power users and homelab deployments
- Runs via Docker Compose
- Keeps service behavior aligned with desktop build

Starter assets in this repo:
- Docker runtime: `Dockerfile`, `docker-compose.yml`
- Docker release workflow: `.github/workflows/release-docker.yml`

## Installation & quick start

## Prerequisites
- Docker + Docker Compose
- (Optional but recommended for local chat) Ollama runtime

## 1) Local development (recommended)

```bash
cp .env.example .env
docker compose up -d --build
```

Open:
- `http://localhost:8001`

Basic checks:

```bash
docker compose ps
docker compose logs --tail=200 agent-web-app
```

---

## Local-only chat setup (no cloud API keys)

1. Ensure local model runtime is running (example: Ollama).
2. Keep `local_only_mode=true` in app config.
3. Configure local provider model list (Ollama/LM Studio/AnythingLLM).
4. Do **not** set cloud provider keys unless intentionally testing hybrid mode.

If local-only mode is enabled and local runtime is unreachable, chat returns a clear error instructing you to start the local runtime or disable local-only mode.

---

## Configuration notes

Environment templates:
- `.env.example` (Docker local)
- `.env.dyad.example` (Dyad + Supabase)
- `.env.vercel.example` (Vercel template)

Related docs:
- `DEPLOYMENT_VERCEL_SUPABASE.md`
- `AUTH_ENV.md`
- `AI_RULES.md`

---

## Feature guide

## Curator nudges
- Automatically generated for overdue tasks
- Exposed via `/api/nudges`
- Acknowledge via `/api/nudges/ack`
- Periodic job controlled by scheduler and `curator_nudges_enabled`

## Skill learning
- Synthesize from session activity
- Track versions and runs
- Optimize/rollback workflow available via skill endpoints

## Cross-session recall
- Chat turns indexed to FTS5 store
- Recall search endpoint returns hits + summary
- Chat UI includes recall query + summary panel

---

## API surface (high level)

- `POST /api/chat`
- `GET /api/configs/status`
- `GET /api/models/options`
- `GET /api/nudges`
- `POST /api/nudges/ack`
- `POST /api/skills/synthesize`
- `GET /api/skills`
- `POST /api/skills/runs`
- `POST /api/skills/{skill_id}/optimize`
- `POST /api/skills/{skill_id}/rollback`
- `POST /api/recall/search`

---

## Testing / verification

Suggested checks:

```bash
python -m py_compile backend/main.py backend/database.py backend/scheduler.py backend/session_recall.py
npx tsc -p tsconfig.frontend.json --noEmit
```

Optional runtime checks:
- start app locally and call `/healthz`
- verify scheduler jobs register in logs
- smoke test nudges/skills/recall endpoints

---

## Security guidance

- Never commit real credentials.
- Keep secret/service keys server-side only.
- Prefer local-only mode by default for privacy-sensitive usage.

---

## Future improvements

Planned hardening work:

1. Better episode detection for skill synthesis quality
2. Stronger canary attribution (per-version run routing)
3. Recall provenance controls + evidence-grounded summaries
4. More robust policy UI for local-only and memory governance
5. Expanded observability dashboards for nudges/skills/recall KPIs

---

## Contributing

When contributing:
- keep local-first behavior intact,
- add tests for new autonomous behaviors,
- avoid regressions in local-only enforcement,
- document new config keys and scheduler jobs.

