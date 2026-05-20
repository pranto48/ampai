# Technical Design Document

## Overview

This design document describes the architecture for completing AmpAI as a personal AI desktop + Docker agent. The system builds on the existing FastAPI backend, PostgreSQL with pgvector, Redis, Tauri desktop app, and LangChain-based AI provider routing. The design preserves all existing functionality while adding browser automation, terminal access, improved memory retrieval, and hardened security.

## Architecture

### System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Interfaces                              │
├──────────────┬──────────────┬──────────────┬────────────────────────┤
│ Tauri Desktop│  Web Browser │ Telegram Bot │  Scheduled Jobs        │
│ (TypeScript) │  (Frontend)  │  (Webhook/   │  (APScheduler)         │
│              │              │   Polling)   │                        │
└──────┬───────┴──────┬───────┴──────┬───────┴────────┬───────────────┘
       │              │              │                │
       ▼              ▼              ▼                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AmpAI FastAPI Server (:8000/:8001)                │
├─────────────────────────────────────────────────────────────────────┤
│  Routers: chat, sessions, memory, tasks, browser, terminal,         │
│           admin, auth, integrations, models, personas, skills       │
├─────────────────────────────────────────────────────────────────────┤
│  Services Layer                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ Memory   │ │ Browser  │ │ Terminal │ │ Web      │ │ Backup   │ │
│  │ Service  │ │ Automtn  │ │ Service  │ │ Search   │ │ Engine   │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│  Core: Config Validator, Audit Logger, Migration Runner             │
└──────┬──────────────┬──────────────┬────────────────────────────────┘
       │              │              │
       ▼              ▼              ▼
┌────────────┐ ┌────────────┐ ┌────────────┐
│agent_postgres│ │ agent_redis │ │  Ollama    │
│(pgvector:16)│ │ (redis:7)  │ │  (local)   │
└────────────┘ └────────────┘ └────────────┘
```

### Component Architecture

```
ampai/
├── main.py                          # FastAPI app entry, startup hooks
├── config_validator.py              # NEW: Env validation, unsafe-default blocking
├── migration_runner.py              # NEW: Safe schema migration engine
├── database.py                      # REFACTORED: Single schema definition
├── agent.py                         # EXISTING: Chat engine, LLM routing
├── ampai_default_engine.py          # EXISTING: Offline fallback engine
├── memory_indexer.py                # EXISTING: PGVector hybrid search
├── memory_curator.py                # EXISTING: LLM-driven memory curation
├── memory_persistence.py            # EXISTING: Archiving, importance scoring
├── services/
│   ├── __init__.py
│   ├── memory_service.py            # NEW: Unified memory facade
│   ├── web_search_service.py        # NEW: Multi-provider web search
│   ├── browser_automation_service.py # NEW: Playwright browser control
│   ├── terminal_service.py          # NEW: Shell command executor
│   └── backup_service.py            # REFACTORED: From backup_helpers.py
├── routers/
│   ├── chat.py                      # EXISTING: POST /api/chat
│   ├── sessions.py                  # NEW: Session CRUD endpoints
│   ├── memory.py                    # EXISTING+EXTENDED: Memory endpoints
│   ├── tasks.py                     # NEW: Task CRUD endpoints
│   ├── browser.py                   # NEW: Browser automation endpoints
│   ├── terminal.py                  # NEW: Terminal execution endpoints
│   ├── admin.py                     # EXISTING+EXTENDED: Admin endpoints
│   ├── auth.py                      # EXISTING: Login/register/whoami
│   ├── integrations.py              # EXISTING+EXTENDED: Telegram endpoints
│   ├── models_router.py             # EXISTING+EXTENDED: Health/options
│   └── personas.py                  # EXISTING: Persona CRUD
├── core/
│   ├── deps.py                      # EXISTING: Auth dependencies
│   ├── helpers.py                   # EXISTING: Shared utilities
│   ├── models.py                    # EXISTING+EXTENDED: Pydantic models
│   └── audit.py                     # NEW: Audit logger service
├── ai/
│   └── providers.py                 # EXISTING: Repo-edit AI providers
├── integrations/
│   ├── telegram_api.py              # EXISTING: Telegram API helpers
│   ├── github/                      # EXISTING: GitHub integration
│   └── gmail_api.py                 # EXISTING: Gmail integration
├── policy/
│   ├── repo_edit_policy.py          # EXISTING: Repo edit security
│   ├── terminal_policy.py           # NEW: Terminal command security
│   └── browser_policy.py            # NEW: Browser domain security
├── desktop/                         # Tauri + Vite + TypeScript
│   └── src/
│       ├── main.ts                  # REFACTORED: App shell + routing
│       ├── state.ts                 # EXTENDED: New tab states
│       ├── tabs-a.ts                # REFACTORED: Server, Account, History
│       ├── tabs-b.ts                # REFACTORED: Memory, Personas
│       ├── tabs-c.ts                # REFACTORED: Settings, Admin
│       ├── tabs-browser.ts          # NEW: Browser automation tab
│       ├── tabs-terminal.ts         # NEW: Terminal tools tab
│       └── tabs-tasks.ts            # NEW: Tasks tab
├── docker-compose.yml               # UPDATED: Renamed services
├── .env.example                     # NEW: All env vars documented
├── Dockerfile                       # EXISTING: Python 3.11-slim
└── docs/                            # NEW: Documentation directory
```

## Data Models

### Database Schema (PostgreSQL with pgvector)

```sql
-- Core tables (existing, consolidated)
CREATE TABLE users (
    username VARCHAR PRIMARY KEY,
    role VARCHAR NOT NULL DEFAULT 'user',
    password_hash VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE app_configs (
    config_key VARCHAR PRIMARY KEY,
    config_value TEXT
);

-- Chat history (existing, extended)
CREATE TABLE chat_message_store (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR NOT NULL,
    message JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_chat_message_store_session ON chat_message_store(session_id);

CREATE TABLE session_metadata (
    session_id VARCHAR PRIMARY KEY,
    title VARCHAR(100),
    category VARCHAR DEFAULT 'Uncategorized',
    pinned BOOLEAN DEFAULT FALSE,
    archived BOOLEAN DEFAULT FALSE,
    owner_username VARCHAR,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    task_suggestions TEXT
);
CREATE INDEX idx_session_metadata_updated ON session_metadata(updated_at DESC);
CREATE INDEX idx_session_metadata_owner ON session_metadata(owner_username);

-- Memory system tables
CREATE TABLE core_memories (
    id SERIAL PRIMARY KEY,
    username VARCHAR NOT NULL DEFAULT 'system',
    fact TEXT NOT NULL,
    category VARCHAR DEFAULT 'general',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE memory_candidates (
    id SERIAL PRIMARY KEY,
    username VARCHAR NOT NULL,
    session_id VARCHAR,
    candidate_text TEXT NOT NULL,
    edited_text TEXT,
    source VARCHAR DEFAULT 'auto',
    confidence FLOAT DEFAULT 0.5,
    status VARCHAR NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ
);
CREATE INDEX idx_memory_candidates_user_status ON memory_candidates(username, status, created_at);
CREATE INDEX idx_memory_candidates_session ON memory_candidates(session_id);

CREATE TABLE memory_summary_nodes (
    id SERIAL PRIMARY KEY,
    username VARCHAR NOT NULL,
    session_id VARCHAR,
    topic VARCHAR,
    summary TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_memory_summary_user_topic ON memory_summary_nodes(username, topic, created_at);

CREATE TABLE memory_events (
    id SERIAL PRIMARY KEY,
    username VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    memory_id INTEGER,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_memory_events_user ON memory_events(username, created_at);

CREATE TABLE memory_embeddings (
    id SERIAL PRIMARY KEY,
    memory_id INTEGER NOT NULL,
    embedding vector(768),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tasks
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    username VARCHAR NOT NULL,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    status VARCHAR DEFAULT 'todo',
    priority VARCHAR DEFAULT 'medium',
    due_at TIMESTAMPTZ,
    session_id VARCHAR,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_tasks_user_status ON tasks(username, status, due_at);

-- Audit
CREATE TABLE audit_events (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR NOT NULL,
    action_type VARCHAR NOT NULL,
    session_id VARCHAR,
    category VARCHAR,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_events_user ON audit_events(username, created_at);
CREATE INDEX idx_audit_events_action ON audit_events(action_type, created_at);

-- Browser automation
CREATE TABLE browser_profiles (
    id SERIAL PRIMARY KEY,
    username VARCHAR NOT NULL,
    domain VARCHAR NOT NULL,
    credential_encrypted TEXT,
    approved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE browser_sessions (
    id SERIAL PRIMARY KEY,
    username VARCHAR NOT NULL,
    browser_id VARCHAR,
    status VARCHAR DEFAULT 'idle',
    current_url VARCHAR,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE automation_jobs (
    id SERIAL PRIMARY KEY,
    username VARCHAR NOT NULL,
    job_type VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'queued',
    request JSONB,
    result JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

-- Terminal
CREATE TABLE terminal_command_logs (
    id SERIAL PRIMARY KEY,
    username VARCHAR NOT NULL,
    command TEXT NOT NULL,
    working_directory VARCHAR,
    exit_code INTEGER,
    output_summary TEXT,
    execution_ms INTEGER,
    blocked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Telegram
CREATE TABLE telegram_users (
    id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT UNIQUE NOT NULL,
    username VARCHAR NOT NULL,
    display_name VARCHAR,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Key Pydantic Models (core/models.py extensions)

```python
class ChatRequest(BaseModel):
    session_id: str
    message: str
    model_type: str = "ollama"
    model_name: Optional[str] = None
    memory_mode: str = "indexed"
    memory_top_k: int = 5
    memory_recency_bias: float = 0.0
    memory_category_filter: Optional[str] = ""
    persona_id: Optional[str] = None
    use_web_search: bool = False
    enable_browser_tools: bool = False
    enable_terminal_tools: bool = False
    chat_output_mode: Optional[str] = None
    attachments: List[Attachment] = []

class SessionCreateRequest(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = "Uncategorized"

class SessionUpdateRequest(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    pinned: Optional[bool] = None
    archived: Optional[bool] = None

class TerminalRunRequest(BaseModel):
    command: str
    working_directory: Optional[str] = None
    timeout: int = 30

class BrowserNavigateRequest(BaseModel):
    url: str
    wait_for: Optional[str] = None

class BrowserActionRequest(BaseModel):
    action: str  # click, type, submit, extract, screenshot
    selector: Optional[str] = None
    value: Optional[str] = None

class WebSearchRequest(BaseModel):
    query: str
    provider: Optional[str] = None
    max_results: int = 5

class TaskCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    due_at: Optional[str] = None
    session_id: Optional[str] = None

class TaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_at: Optional[str] = None
```

## Components and Interfaces

### API Endpoints

#### Sessions (NEW: routers/sessions.py)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/sessions | user | List sessions (paginated, sorted by updated_at DESC, pinned first) |
| POST | /api/sessions | user | Create new session |
| PATCH | /api/sessions/{id} | user | Update title, category, pinned, archived |
| DELETE | /api/sessions/{id} | user | Delete session and all messages |
| GET | /api/history/{session_id} | user | Get all messages for a session |

#### Chat (EXISTING: routers/chat.py — extended payload)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/chat | user | Send message with full settings payload |

#### Memory (EXISTING+EXTENDED: routers/memory.py)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/memory/core | user | List core memories |
| POST | /api/memory/core | user | Add explicit memory |
| DELETE | /api/memory/core/{id} | user | Delete/forget memory |
| GET | /api/memory/inbox | user | List pending candidates |
| PATCH | /api/memory/inbox/{id} | user | Approve/reject candidate |
| POST | /api/memory/search | user | Hybrid memory search |

#### Tasks (NEW: routers/tasks.py)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/tasks | user | List tasks (paginated, filterable) |
| POST | /api/tasks | user | Create task |
| PATCH | /api/tasks/{id} | user | Update task |
| DELETE | /api/tasks/{id} | user | Delete task |

#### Models (EXISTING+EXTENDED: routers/models_router.py)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/models/options | user | Available providers and models |
| GET | /api/models/health | user | Provider reachability status |
| POST | /api/admin/providers/test | admin | Test specific provider connection |

#### Web Search (NEW: routers/web_search.py or inline in chat)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/tools/web-search | user | Execute web search query |

#### Browser Automation (NEW: routers/browser.py)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/browser/open | user | Open browser instance |
| POST | /api/browser/navigate | user | Navigate to URL (allowlist enforced) |
| POST | /api/browser/search | user | Search via browser |
| POST | /api/browser/click | user | Click element by selector |
| POST | /api/browser/type | user | Type into element |
| POST | /api/browser/submit | user | Submit form |
| POST | /api/browser/extract | user | Extract page text/tables |
| POST | /api/browser/screenshot | user | Take page screenshot |
| POST | /api/browser/close | user | Close browser instance |
| GET | /api/browser/jobs | user | List automation jobs |
| GET | /api/browser/allowlist | admin | Get domain allowlist |
| POST | /api/browser/allowlist | admin | Update domain allowlist |

#### Terminal (NEW: routers/terminal.py)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/terminal/run | user | Execute command (confirmation required) |
| GET | /api/terminal/logs | user | Get command execution history |
| GET | /api/terminal/policy | admin | Get current terminal policy |
| PATCH | /api/terminal/policy | admin | Update allowlist/denylist/folders |

#### Telegram (EXISTING+EXTENDED: routers/integrations.py)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/admin/integrations/telegram/status | admin | Bot connection status |
| POST | /api/admin/integrations/telegram/save | admin | Save bot config |
| POST | /api/admin/integrations/telegram/test | admin | Test bot token |
| POST | /api/telegram/webhook | none | Telegram webhook receiver |
| POST | /api/admin/telegram/enable-polling | admin | Start long-polling |
| POST | /api/admin/telegram/disable-polling | admin | Stop long-polling |

#### Backup (EXISTING+EXTENDED: routers/admin.py)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/admin/backup/run | admin | Trigger manual backup |
| GET | /api/admin/backup/jobs | admin | List backup history |
| POST | /api/admin/backup/test-ftp | admin | Test FTP connection |
| GET | /api/admin/backup/profiles | admin | List backup profiles |
| POST | /api/admin/backup/profiles | admin | Create backup profile |
| PATCH | /api/admin/backup/profiles/{id} | admin | Update backup profile |

#### Audit (NEW endpoint in routers/admin.py)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/admin/audit-logs | admin | Query audit events with filters |

#### Skills (EXISTING+EXTENDED)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/skills | user | List skills |
| POST | /api/skills | admin | Create skill |
| PATCH | /api/skills/{id} | admin | Update skill |
| DELETE | /api/skills/{id} | admin | Delete skill |
| POST | /api/skills/{id}/execute | user | Execute skill |
| GET | /api/skills/{id}/metrics | user | Skill performance metrics |

## Component Design Details

### 1. Config Validator (config_validator.py)

```python
UNSAFE_DEFAULTS = {
    "JWT_SECRET": {"change-me", "change-me-for-production", "change-this-long-random-secret"},
    "AMPAI_DEFAULT_ADMIN_PASSWORD": {"P@ssw0rd", "change-this", "admin123"},
    "POSTGRES_PASSWORD": {"change-this", "ampai"},
}

def validate_config() -> None:
    """Called before uvicorn binds. Exits with code 1 if production + unsafe."""
    env = os.getenv("AMPAI_ENV", "development").lower()
    is_production = env in ("production", "prod")
    errors = []
    warnings = []
    for var, unsafe_values in UNSAFE_DEFAULTS.items():
        current = os.getenv(var, "")
        if current in unsafe_values:
            if is_production:
                errors.append(f"{var} is set to unsafe default '{current}'")
            else:
                warnings.append(f"{var} is set to unsafe default (ok for dev)")
    if errors:
        for e in errors:
            logger.error(f"STARTUP BLOCKED: {e}")
        sys.exit(1)
    for w in warnings:
        logger.warning(w)
```

### 2. Migration Runner (migration_runner.py)

Design principles:
- Additive-only migrations (CREATE TABLE IF NOT EXISTS, ADD COLUMN IF NOT EXISTS)
- No DROP TABLE, no DROP COLUMN, no ALTER TYPE
- Each migration is a numbered Python function
- Retry connection up to 3 times with 2s delay
- 30-second timeout for all migrations combined
- Log each migration step result

```python
class MigrationRunner:
    def __init__(self, engine):
        self.engine = engine
        self.migrations = []  # List of (version, name, callable)

    def register(self, version: int, name: str):
        """Decorator to register a migration function."""

    def run_pending(self, timeout_seconds: int = 30) -> List[MigrationResult]:
        """Execute all pending migrations within timeout."""

    def _get_applied_versions(self) -> Set[int]:
        """Read from _migrations table."""

    def _mark_applied(self, version: int, name: str) -> None:
        """Record successful migration."""
```

### 3. Memory Service (services/memory_service.py)

Facade over existing memory_indexer, memory_curator, memory_persistence, and session_recall modules.

```python
class MemoryService:
    def __init__(self, engine, indexer: MemoryIndexer):
        self.engine = engine
        self.indexer = indexer

    def save_chat_turn(self, username, session_id, role, content, metadata) -> None:
        """Persist chat message and trigger candidate evaluation."""

    def capture_candidate(self, username, session_id, text, source="auto", confidence=0.5) -> dict:
        """Create a memory candidate for review."""

    def save_explicit_memory(self, username, session_id, text, category=None) -> dict:
        """Save directly to core_memories (user explicit command)."""

    def approve_candidate(self, candidate_id, edited_text=None) -> dict:
        """Promote candidate to core memory + vector index."""

    def reject_candidate(self, candidate_id) -> dict:
        """Mark candidate as rejected."""

    def search_memory(self, username, query, limit=5, mode="hybrid",
                      category=None, date_from=None, date_to=None,
                      recency_bias=0.0, char_budget=1200) -> MemorySearchResult:
        """Hybrid search returning compressed results within char_budget."""

    def summarize_session(self, session_id, username) -> str:
        """Generate and store a summary node for the session."""

    def rebuild_indexes(self, username=None, batch_size=100) -> dict:
        """Re-embed all core memories for a user."""

    def forget_memory(self, username, memory_id) -> bool:
        """Delete from core_memories and vector index."""

@dataclass
class MemorySearchResult:
    memories: List[dict]
    metadata: MemoryRetrievalMetadata

@dataclass
class MemoryRetrievalMetadata:
    pipeline: str  # "hybrid", "vector_only", "fts_only"
    latency_ms: int
    lexical_hits: int
    vector_hits: int
    summary_hits: int
    returned_count: int
    context_chars: int
    estimated_tokens: int
    cache_hits: int
    cache_misses: int
```

### 4. Web Search Service (services/web_search_service.py)

```python
class WebSearchService:
    PROVIDERS = ["duckduckgo", "tavily", "serpapi", "brave"]

    def __init__(self, configs: dict):
        self.provider_order = self._resolve_provider_order(configs)

    def search(self, query: str, max_results: int = 5) -> WebSearchResult:
        """Try providers in order until one succeeds."""

    def summarize_for_context(self, results: List[SearchHit], char_budget: int = 1200) -> str:
        """Compress search results into a context string."""

    def _search_duckduckgo(self, query, max_results) -> List[SearchHit]: ...
    def _search_tavily(self, query, max_results) -> List[SearchHit]: ...
    def _search_serpapi(self, query, max_results) -> List[SearchHit]: ...
    def _search_brave(self, query, max_results) -> List[SearchHit]: ...

@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    provider: str
    timestamp: str
```

### 5. Browser Automation Service (services/browser_automation_service.py)

```python
class BrowserAutomationService:
    def __init__(self, config: BrowserConfig):
        self.enabled = config.enabled  # BROWSER_AUTOMATION_ENABLED
        self.headless = config.headless  # BROWSER_HEADLESS (default False)
        self.domain_allowlist = config.domain_allowlist
        self.action_timeout = 30  # seconds
        self.confirmation_timeout = 60  # seconds
        self._browser = None
        self._page = None

    def check_enabled(self) -> None:
        """Raise if browser automation is disabled."""

    def check_domain(self, url: str) -> None:
        """Raise if domain not in allowlist."""

    async def open_browser(self) -> dict:
        """Launch Playwright Chromium in headed mode."""

    async def navigate(self, url: str) -> dict:
        """Navigate to URL after domain check."""

    async def click(self, selector: str) -> dict: ...
    async def type_text(self, selector: str, text: str) -> dict: ...
    async def submit_form(self, selector: str) -> dict: ...
    async def extract_text(self) -> dict: ...
    async def extract_tables(self) -> dict: ...
    async def screenshot(self) -> bytes: ...
    async def summarize_page(self, model_type: str) -> str: ...
    async def close(self) -> None: ...

    def _log_action(self, action: str, target: str, outcome: str) -> None:
        """Write to audit_events table."""

@dataclass
class BrowserConfig:
    enabled: bool = False
    headless: bool = False
    domain_allowlist: List[str] = field(default_factory=list)
    encryption_key: Optional[str] = None
```

### 6. Terminal Service (services/terminal_service.py)

```python
DANGEROUS_PATTERNS = [
    r"rm\s+(-rf?|--recursive)\s+/",
    r"\bformat\b",
    r"del\s+/[sS]",
    r"Remove-Item.*-Recurse.*(C:\\|/|\\Windows|\\System32)",
    r"\bshutdown\b",
    r"\bregedit\b|\breg\s+(add|delete)\b",
    r"mimikatz|sekurlsa|lsadump|credential.dump",
    r"token.dump|access.token.export",
    r"browser.*password.*export|chrome.*login.*data",
    r"keylog|key.?logger",
    r"stealth|hidden.*monitor",
]

class TerminalService:
    def __init__(self, config: TerminalConfig):
        self.enabled = config.enabled
        self.require_confirmation = config.require_confirmation
        self.allowed_folders = config.allowed_folders
        self.allowlist = config.command_allowlist
        self.denylist = config.command_denylist
        self.timeout = config.timeout  # default 30s
        self.max_output = config.max_output  # default 10000 chars

    def check_enabled(self) -> None:
        """Raise if terminal tools disabled."""

    def validate_command(self, command: str, cwd: str) -> ValidationResult:
        """Check against denylist, dangerous patterns, and folder restrictions."""

    def execute(self, command: str, cwd: str, shell: str = "auto") -> CommandResult:
        """Run command with timeout and output capture."""

    def _detect_shell(self) -> str:
        """Return 'bash', 'powershell', or 'cmd' based on OS."""

    def _is_dangerous(self, command: str) -> Optional[str]:
        """Return matched pattern name or None."""

    def _is_in_allowed_folder(self, cwd: str) -> bool:
        """Check if cwd is within allowed project folders."""

@dataclass
class TerminalConfig:
    enabled: bool = False
    require_confirmation: bool = True
    allowed_folders: List[str] = field(default_factory=list)
    command_allowlist: List[str] = field(default_factory=list)
    command_denylist: List[str] = field(default_factory=list)
    timeout: int = 30
    max_output: int = 10000

@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    execution_ms: int
    truncated: bool
    blocked: bool = False
    block_reason: Optional[str] = None
```

### 7. Audit Logger (core/audit.py)

```python
class AuditLogger:
    def __init__(self, engine):
        self.engine = engine

    def log(self, username: str, action_type: str, details: dict,
            session_id: str = None, category: str = None) -> None:
        """Append-only insert into audit_events table."""

    def query(self, action_type=None, username=None, date_from=None,
              date_to=None, session_id=None, limit=100, offset=0) -> List[dict]:
        """Query audit events with filters."""

# Action types:
# memory_write, memory_read, memory_delete
# browser_action, browser_navigate, browser_login
# terminal_execute, terminal_blocked
# telegram_message, telegram_command
# backup_run, backup_restore
# login_attempt, login_success, login_failure
# config_change
# web_search
```

### 8. Docker Compose (Updated)

```yaml
services:
  agent_postgres:
    image: pgvector/pgvector:pg16
    container_name: ampai-agent-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-ampai}
      POSTGRES_USER: ${POSTGRES_USER:-ampai}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD required}
    volumes:
      - agent_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-ampai} -d ${POSTGRES_DB:-ampai}"]
      interval: 5s
      timeout: 5s
      retries: 20

  agent_redis:
    image: redis:7-alpine
    container_name: ampai-agent-redis
    restart: unless-stopped
    volumes:
      - agent_redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 20

  ampai:
    build: .
    container_name: ampai-server
    restart: unless-stopped
    depends_on:
      agent_postgres:
        condition: service_healthy
      agent_redis:
        condition: service_healthy
    ports:
      - "8000:8000"
      - "8001:8000"
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-ampai}:${POSTGRES_PASSWORD}@agent_postgres:5432/${POSTGRES_DB:-ampai}
      REDIS_URL: redis://agent_redis:6379/0
      JWT_SECRET: ${JWT_SECRET:?JWT_SECRET required}
      AMPAI_ENV: ${AMPAI_ENV:-development}
      AMPAI_DEFAULT_ADMIN_USERNAME: ${AMPAI_DEFAULT_ADMIN_USERNAME:-admin}
      AMPAI_DEFAULT_ADMIN_PASSWORD: ${AMPAI_DEFAULT_ADMIN_PASSWORD:?AMPAI_DEFAULT_ADMIN_PASSWORD required}
      CONFIG_ENCRYPTION_KEY: ${CONFIG_ENCRYPTION_KEY:-}
      OLLAMA_BASE_URL: ${OLLAMA_BASE_URL:-http://host.docker.internal:11434}
      SESSION_RECALL_DB_PATH: /data/agent_data/session_recall.db
      ALLOWED_ORIGINS: ${ALLOWED_ORIGINS:-http://localhost:1420,http://127.0.0.1:1420,tauri://localhost}
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:-}
      WEB_SEARCH_PROVIDER: ${WEB_SEARCH_PROVIDER:-duckduckgo}
      BROWSER_AUTOMATION_ENABLED: ${BROWSER_AUTOMATION_ENABLED:-false}
      BROWSER_HEADLESS: ${BROWSER_HEADLESS:-false}
      TERMINAL_TOOLS_ENABLED: ${TERMINAL_TOOLS_ENABLED:-false}
      TERMINAL_REQUIRE_CONFIRMATION: ${TERMINAL_REQUIRE_CONFIRMATION:-true}
    volumes:
      - ampai_data:/data
    extra_hosts:
      - "host.docker.internal:host-gateway"

volumes:
  agent_postgres_data:
  agent_redis_data:
  ampai_data:
```

### 9. Desktop App State Extensions (desktop/src/state.ts)

```typescript
// Extended state for new features
export interface BrowserState {
  enabled: boolean;
  allowlist: string[];
  jobs: BrowserJob[];
  currentScreenshot: string | null;
  confirmationPending: BrowserConfirmation | null;
}

export interface TerminalState {
  enabled: boolean;
  policy: TerminalPolicy;
  logs: TerminalLog[];
  confirmationPending: TerminalConfirmation | null;
}

export interface TaskState {
  tasks: Task[];
  filter: { status?: string; priority?: string; search?: string };
}

// Added to S (global state):
// S.browserState: BrowserState
// S.terminalState: TerminalState
// S.taskState: TaskState
// S.enableBrowserTools: boolean (per-chat toggle)
// S.enableTerminalTools: boolean (per-chat toggle)
```

### 10. Security Policy Enforcement Flow

```
User Request → Router → Auth Check → Tool Enable Check → Policy Check → Execute → Audit Log

Browser: BROWSER_AUTOMATION_ENABLED → domain_allowlist → confirmation → execute → audit
Terminal: TERMINAL_TOOLS_ENABLED → folder_check → denylist → confirmation → execute → audit
Telegram: allowed_telegram_user_ids → rate_limit → tool_access_check → execute → audit
```

## Sequence Diagrams

### Chat with Memory Retrieval

```
Desktop → POST /api/chat {session_id, message, memory_mode="indexed", memory_top_k=5}
  → Router validates auth
  → MemoryService.search_memory(username, message, limit=5, mode="hybrid")
    → PGVector similarity search (top 10 candidates)
    → FTS5 lexical search (top 10 candidates)
    → Merge + rerank by recency_bias
    → Compress to char_budget (1200 chars)
    → Return MemorySearchResult with metadata
  → Build system prompt with compressed memory context
  → Route to LLM (Ollama → Cloud fallback → AmpAI Default)
  → Save chat turn to chat_message_store
  → Evaluate for memory candidates (importance > 0.15 → pending)
  → Detect task intent → create suggestions
  → Index in FTS5 session_recall
  → Return response + retrieval_metadata + task_suggestions
```

### Browser Automation Flow

```
Desktop → POST /api/browser/navigate {url: "https://example.com"}
  → check_enabled() → 403 if disabled
  → check_domain("example.com") → 403 if not in allowlist
  → Return confirmation_required: true, action_description: "Navigate to example.com"
Desktop → POST /api/browser/navigate {url: "...", confirmed: true}
  → Playwright navigate with 30s timeout
  → audit_log(browser_navigate, url, outcome)
  → Return {status: "ok", title: "...", url: "..."}
```

### Terminal Execution Flow

```
Desktop → POST /api/terminal/run {command: "git status", working_directory: "/project"}
  → check_enabled() → 403 if disabled
  → validate_command("git status", "/project")
    → check denylist → pass
    → check dangerous patterns → pass
    → check allowed_folders → pass
  → Return confirmation_required: true (if TERMINAL_REQUIRE_CONFIRMATION)
Desktop → POST /api/terminal/run {command: "...", confirmed: true}
  → subprocess.run with timeout=30s, capture_output=True
  → Truncate output to max_output chars
  → audit_log(terminal_execute, command, exit_code, execution_ms)
  → Return CommandResult
```

## Design Decisions

### 1. Service Layer Pattern
**Decision**: Introduce a `services/` directory with dedicated service classes rather than putting all logic in routers.
**Rationale**: The existing codebase has business logic spread across main.py (~8000 lines), routers, and utility modules. Service classes provide testable units with clear interfaces. Routers become thin HTTP adapters.

### 2. Additive-Only Migrations
**Decision**: Never drop tables or columns. Only CREATE IF NOT EXISTS and ADD COLUMN IF NOT EXISTS.
**Rationale**: The system stores personal data (memories, chat history). Destructive migrations risk data loss. Backward compatibility is critical for a personal agent.

### 3. Confirmation-Before-Execute for Dangerous Operations
**Decision**: Browser and terminal actions return a `confirmation_required` response first. The client must re-send with `confirmed: true`.
**Rationale**: This prevents accidental execution of sensitive operations. The desktop app shows a modal before confirming. This is a two-phase commit pattern at the API level.

### 4. Memory Compression to Token Budget
**Decision**: Always compress retrieved memories to `memory_context_char_budget` (default 1200 chars) before injecting into the LLM prompt.
**Rationale**: Prevents context window overflow and reduces cost. The existing `INDEXED_CONTEXT_CHAR_BUDGET = 1200` in agent.py already implements this pattern.

### 5. Existing LangChain Integration Preserved
**Decision**: Keep LangChain for LLM routing (ChatOllama, ChatOpenAI, ChatGoogleGenerativeAI, ChatAnthropic) and PGVector for embeddings.
**Rationale**: The existing agent.py already uses LangChain effectively. Replacing it would be a rewrite with no benefit.

### 6. Playwright for Browser Automation
**Decision**: Use Playwright (not Selenium) for browser automation.
**Rationale**: Playwright has better async support, faster execution, and built-in waiting strategies. It supports Chromium, Firefox, and WebKit. The `playwright` package is well-maintained.

### 7. Docker Service Naming Convention
**Decision**: Rename `db` → `agent_postgres`, `redis` → `agent_redis`. Container names: `ampai-agent-postgres`, `ampai-agent-redis`.
**Rationale**: User requirement. Clearer naming for multi-service Docker environments.

### 8. Audit as Append-Only
**Decision**: Audit events are insert-only. No UPDATE or DELETE operations on audit_events through the application.
**Rationale**: Audit integrity requires immutability. Admin can query but not modify audit records.

### 9. Desktop App: Extend Existing Tab System
**Decision**: Add new tab files (tabs-browser.ts, tabs-terminal.ts, tabs-tasks.ts) rather than rewriting the existing tab system.
**Rationale**: The existing desktop app has a working tab architecture in tabs-a/b/c.ts. Adding new files follows the same pattern without disrupting existing functionality.

### 10. Telegram Tool Access Isolation
**Decision**: Telegram bot cannot access browser or terminal tools unless explicitly enabled by admin.
**Rationale**: Telegram messages come from external networks. Allowing tool access by default would be a security risk. The admin must opt-in per tool category.

## Error Handling

### Service-Level Error Handling
- All service methods catch exceptions and return structured error responses rather than raising HTTP exceptions directly.
- Database connection failures trigger retry logic (3 attempts, 2s delay) before surfacing to the caller.
- External API failures (Ollama, search providers, Telegram) are caught and logged; the system degrades gracefully.

### Fallback Chains
- **Model routing**: Ollama → Cloud providers (in order) → AmpAI Default engine. Never fails completely.
- **Web search**: Primary provider → next provider → return response without search results.
- **Memory retrieval**: Vector search failure → FTS-only fallback → return empty context with error metadata.
- **Embeddings**: Cloud embedding → Ollama nomic-embed-text → disable vector search (FTS-only mode).

### Audit Logger Resilience
- If audit logging fails, the original operation continues uninterrupted.
- Audit failures are logged to the application error log for later investigation.

### Browser/Terminal Timeout Handling
- Browser actions timeout at 30s → abort action, close tab, return timeout error.
- Terminal commands timeout at configured limit → SIGTERM process, return partial output.
- Confirmation requests timeout at 60s → cancel pending action.

## Correctness Properties

### Property 1: Memory Consistency
A memory saved via "remember ..." is immediately searchable via "search memory: ..." within the same request cycle. The core_memories table and vector index are updated atomically.
**Validates: Requirements 5.2, 5.3**

### Property 2: Session Isolation
Users can only access their own sessions unless they have admin role or the session is shared via memory groups. All session endpoints enforce ownership checks.
**Validates: Requirements 4.5, 4.6**

### Property 3: Audit Completeness
Every browser action, terminal command, and memory write produces exactly one audit event in the audit_events table. No security-sensitive operation completes without an audit record attempt.
**Validates: Requirements 15.1, 15.2, 15.3**

### Property 4: Denylist Precedence
If a terminal command matches both the allowlist and denylist, the denylist takes precedence and the command is blocked. The denylist is evaluated first.
**Validates: Requirements 9.4, 9.5**

### Property 5: Idempotent Migrations
Running the migration runner multiple times produces the same schema state. All migrations use IF NOT EXISTS guards and are recorded in a _migrations tracking table.
**Validates: Requirements 3.1, 3.5**

### Property 6: Token Budget Enforcement
Memory context injected into LLM prompts never exceeds `memory_context_char_budget` (default 1200 characters). The MemoryService truncates and compresses results before returning.
**Validates: Requirements 5.3, 5.10**

### Property 7: Disabled-by-Default Tools
Browser automation and terminal tools return HTTP 403 unless explicitly enabled by admin configuration. The check occurs before any tool logic executes.
**Validates: Requirements 8.2, 9.2**

## Testing Strategy

- **Unit tests**: Each service class tested in isolation with mocked database/Redis/network.
- **Integration tests**: Docker-based tests for database migrations and provider connectivity.
- **Security tests**: Verify denylist blocking, domain allowlist enforcement, disabled-by-default behavior.
- **Test framework**: pytest with pytest-asyncio for async browser tests.
- **Mocking**: unittest.mock for external services (Ollama, Telegram API, search providers).

## Migration Path

1. Update docker-compose.yml (service rename, .env variables)
2. Refactor database.py (deduplicate tables, add new tables)
3. Add migration_runner.py and config_validator.py
4. Create services/ directory with new service classes
5. Add new routers (sessions, tasks, browser, terminal)
6. Extend existing routers (memory, integrations, admin)
7. Update desktop app with new tabs
8. Add tests
9. Create documentation
