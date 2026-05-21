# AmpAI Personal Agent

AmpAI is a personal AI desktop and Docker agent combining chat, long-term memory, offline/online AI model support, web search, Telegram bot integration, browser automation, and controlled terminal access into a unified platform.

## Quickstart

### Prerequisites

- **Docker** (v20.10+) and **Docker Compose** (v2.0+)
- **Ports available**: `8000` and `8001` on the host machine
- **(Optional)** [Ollama](https://ollama.ai) running locally on port `11434` for local LLM inference

### Setup

1. **Clone the repository** and navigate to the project root:

   ```bash
   git clone <repository-url>
   cd ampai
   ```

2. **Create your environment file** from the provided template:

   ```bash
   cp .env.example .env
   ```

3. **Edit `.env`** and replace all `<CHANGE_ME>` placeholders with secure values. At minimum, set:

   - `POSTGRES_PASSWORD` — database password
   - `JWT_SECRET` — a long random string (generate with `openssl rand -hex 32`)
   - `AMPAI_DEFAULT_ADMIN_PASSWORD` — admin account password

4. **Start the stack**:

   ```bash
   docker compose up -d --build
   ```

   This builds and starts three services:
   - **agent_postgres** — PostgreSQL 16 with pgvector (container: `ampai-agent-postgres`)
   - **agent_redis** — Redis 7 (container: `ampai-agent-redis`)
   - **ampai** — the FastAPI application server (container: `ampai-server`)

   The server waits for both PostgreSQL and Redis to report healthy before accepting requests.

### Verify Deployment

Confirm all services are running and healthy:

```bash
docker compose ps
```

You should see all three containers with status `Up` and `(healthy)`. Then verify the API is responding:

```bash
curl http://localhost:8000/docs
```

A successful response (HTTP 200 with the Swagger UI page) confirms the deployment is running.

### Ports

| Port | Service |
|------|---------|
| 8000 | AmpAI API (primary) |
| 8001 | AmpAI API (secondary/mirror) |

### Stopping

```bash
docker compose down
```

To also remove persistent volumes (database data, Redis data, app data):

```bash
docker compose down -v
```

## Configuration

See [`.env.example`](.env.example) for a full list of environment variables with descriptions, defaults, and required/optional status.

## Documentation

Detailed documentation is available in the [`docs/`](docs/) directory:

- [Memory Architecture](docs/MEMORY_ARCHITECTURE.md)
- [Browser Automation](docs/BROWSER_AUTOMATION.md)
- [Terminal Tools](docs/TERMINAL_TOOLS.md)
- [Telegram Bot](docs/TELEGRAM_BOT.md)
- [Backup and Restore](docs/BACKUP_AND_RESTORE.md)
- [Model Providers](docs/MODEL_PROVIDERS.md)
- [Security Policy](docs/SECURITY_POLICY.md)
