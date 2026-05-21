# AmpAI Personal Agent

A personal AI agent with long-term memory, web search, browser automation, terminal access, and Telegram integration.

## Quick Start (Docker)

```bash
git clone https://github.com/pranto48/ampai.git
cd ampai
chmod +x setup.sh && ./setup.sh
docker compose up -d --build
```

That's it. The `setup.sh` script generates a `.env` file with secure random secrets.

**Access:**
- API: http://localhost:8000/docs
- Health: http://localhost:8000/healthz

**Admin credentials** are printed by `setup.sh`. Default username is `admin`.

## Manual Setup

If you prefer to configure manually:

```bash
cp .env.example .env
# Edit .env and replace all <CHANGE_ME> values
docker compose up -d --build
```

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `POSTGRES_PASSWORD` | Database password |
| `JWT_SECRET` | JWT signing key (generate: `openssl rand -hex 32`) |
| `AMPAI_DEFAULT_ADMIN_PASSWORD` | Admin account password |

## Verify

```bash
# Check all services are healthy
docker compose ps

# Check logs
docker logs ampai-server --tail=50

# Test the API
curl http://localhost:8000/healthz
```

## Stop

```bash
docker compose down        # Stop containers (keep data)
docker compose down -v     # Stop and delete all data
```

## Architecture

| Service | Container | Port |
|---------|-----------|------|
| PostgreSQL 16 + pgvector | ampai-agent-postgres | 5432 (internal) |
| Redis 7 | ampai-agent-redis | 6379 (internal) |
| AmpAI API (FastAPI) | ampai-server | 8000, 8001 |

## Optional: Local AI with Ollama

Install [Ollama](https://ollama.ai) on your host machine:

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

AmpAI auto-detects Ollama at `http://host.docker.internal:11434`.

## Documentation

See [`docs/`](docs/) for detailed documentation:

- [Memory Architecture](docs/MEMORY_ARCHITECTURE.md)
- [Browser Automation](docs/BROWSER_AUTOMATION.md)
- [Terminal Tools](docs/TERMINAL_TOOLS.md)
- [Telegram Bot](docs/TELEGRAM_BOT.md)
- [Backup and Restore](docs/BACKUP_AND_RESTORE.md)
- [Model Providers](docs/MODEL_PROVIDERS.md)
- [Security Policy](docs/SECURITY_POLICY.md)

## Desktop App

The Tauri desktop app is in `desktop/`. See [desktop/README.md](desktop/README.md) for build instructions.

## Development

```bash
# Run tests (inside Docker)
docker compose exec ampai pytest -q

# Run tests (local, requires Python 3.11+ and dependencies)
pip install -r requirements.txt
pytest tests/ -q
```
