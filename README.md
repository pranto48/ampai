# AmpAI: Autonomous Personal AI Agent

AmpAI is a powerful, autonomous, and self-hosted personal AI agent architecture featuring long-term memory, real-time web search, browser automation scraping, sandboxed terminal access, and context-aware Telegram bot integration.

Designed to run locally or on a private server, AmpAI provides a secure cognitive layer that integrates with modern LLM providers (OpenAI, OpenRouter, Google Gemini, Anthropic, or fully local instances via Ollama).

---

## Key Features

* **Cognitive Memory Management**: Uses a hybrid architecture combining Redis for short-term session recall and PostgreSQL (`pgvector`) + ChromaDB for semantic long-term memory. Supports automated, LLM-based memory curation of facts.
* **Actuator Tools Layer**:
  * **Web Search**: Dynamic query execution via DuckDuckGo to synthesize real-time data into chat responses.
  * **Browser Automation**: Launches headless browser nodes to scrape page text while enforcing domain allowlists.
  * **Sandboxed Terminal**: Secure terminal shell access supporting safe diagnostics (`ping`, `df -h`, `uptime`) while automatically blocking dangerous commands (`rm -rf /`, `shutdown`, `regedit`) via strict regex policies.
* **Role-Based Access Control (RBAC)**: Fine-grained security scoping where regular users can only query/modify their own memories, while admin accounts can curate global memory indices.
* **Seamless Integrations**: Built-in webhook routing for Telegram bot interactions with session recall and context awareness.

---

## System Architecture

The application is fully containerized and deploys as a multi-container stack:

| Container Name | Service / Technology | Port Mapping | Purpose |
|----------------|----------------------|--------------|---------|
| `ampai-frontend` | React UI served via Nginx | `8080:80` | Glassmorphic desktop/web chat interface |
| `ampai-server` | FastAPI Backend | `8000:8000` | Core API, orchestration engine, and task queue |
| `ampai-relational-db` | PostgreSQL 16 | Internal (5432) | Relational store for users, logs, and sessions |
| `ampai-vector-memory-db` | PostgreSQL 16 + `pgvector` | Internal (5432) | Long-term semantic fact embeddings storage |
| `ampai-agent-redis` | Redis 7 | Internal (6379) | Short-term conversation session context history |
| `ampai-chromadb` | ChromaDB | `8001:8000` | Vector storage for document text extracts |
| `ampai-browser-node` | Browserless Chrome | Internal | Headless browser container for page scraping |

---

## Prerequisites

Before deploying AmpAI, ensure you have the following installed on your host system:

* **Git**: To clone the repository.
* **Docker & Docker Compose**: Core container runtime (Docker Compose v2.0+ recommended).
* **Network Ports**: Keep ports `8080` (UI), `8000` (API), and `8001` (ChromaDB) free.
* *(Optional)* **Ollama**: For running local open-source LLMs and embeddings offline.

---

## Quick Start Installation (Docker)

To deploy the entire environment with a single command:

1. Clone the repository and navigate to the project directory:
   ```bash
   git clone https://github.com/pranto48/ampai.git
   cd ampai
   ```

2. Make the installer script executable and run it:
   ```bash
   chmod +x install.sh
   ./install.sh
   ```

The `install.sh` script will automatically:
* Initialize a local `.env` configuration file.
* Generate secure, random secrets for authentication and database encryption.
* Build and start all Docker container services.
* Poll services until the PostgreSQL databases and Redis cache report as healthy.
* Create a default superadmin user account and print the credentials in the console.

---

## Manual Installation & Superadmin Seeding

If you prefer to configure the environment variables manually:

1. Copy the template configuration file:
   ```bash
   cp .env.example .env
   ```

2. Open `.env` in your preferred editor and configure the following required variables:

   * **PostgreSQL & Database Setup**:
     ```ini
     POSTGRES_PASSWORD=your_secure_db_password
     ```
   * **Authentication Secrets**:
     ```ini
     JWT_SECRET=your_32_character_hex_signing_key
     # Generate one using: openssl rand -hex 32
     ```
   * **Superadmin User Account Seeding**:
     On container startup, the backend checks for these variables and seeds a superuser account in the relational database:
     ```ini
     DEFAULT_ADMIN_EMAIL=superadmin@ampai.local
     DEFAULT_ADMIN_PASSWORD=your_secure_admin_password
     ```
   * **Terminal Configuration (Actuator Tools)**:
     ```ini
     TERMINAL_TOOLS_ENABLED=true
     TERMINAL_REQUIRE_CONFIRMATION=true
     ```

3. Build and launch the container stack in detached mode:
   ```bash
   docker compose up -d --build
   ```

4. Confirm that all containers are healthy and running:
   ```bash
   docker compose ps
   ```

---

## Running Local AI Models (Ollama)

To run fully offline models without relying on third-party cloud APIs (such as OpenAI or Gemini):

1. Download and run [Ollama](https://ollama.com) on your host machine.
2. Pull the default text and embedding models:
   ```bash
   ollama pull llama3.2
   ollama pull nomic-embed-text
   ```

AmpAI automatically connects to local Ollama instances at startup via the host gateway bridge mapping: `http://host.docker.internal:11434`.

---

## Verification & Tests

To run the automated Python test suite:

### Local Execution (Requires Python 3.11+)
```bash
pip install -r requirements.txt
pytest tests/ -v
```

### Docker Execution
```bash
docker compose exec core-backend pytest tests/ -v
```

---

## Stop Services

* To stop all running containers while preserving database volumes:
  ```bash
  docker compose down
  ```
* To stop containers and wipe all stored data (databases, redis, backups):
  ```bash
  docker compose down -v
  ```
