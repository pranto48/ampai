# Implementation Plan: AmpAI Personal Agent

## Overview

This plan implements the AmpAI Personal Agent feature across 15 task groups, building incrementally from infrastructure (Docker, config, migrations) through core services (memory, chat, models) to advanced features (browser, terminal, Telegram, tasks, skills) and finishing with desktop UI, backup, audit, testing, and documentation. Each task builds on previous steps, with checkpoints to validate progress.

## Tasks

- [x] 1. Docker Environment and Service Orchestration
  - [x] 1.1 Update docker-compose.yml with renamed services and health checks
    - Rename `db` → `agent_postgres` (image: pgvector/pgvector:pg16, container: ampai-agent-postgres)
    - Rename `redis` → `agent_redis` (image: redis:7-alpine, container: ampai-agent-redis)
    - Add health checks: pg_isready (interval 5s, timeout 5s, retries 20), redis-cli ping (interval 5s, timeout 3s, retries 20)
    - Configure ampai service with depends_on conditions (service_healthy), ports 8000:8000 and 8001:8000
    - Add all environment variables from design (DATABASE_URL, REDIS_URL, JWT_SECRET, AMPAI_ENV, etc.)
    - Add volumes: agent_postgres_data, agent_redis_data, ampai_data
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 1.2 Create .env.example with all documented variables
    - List every environment variable: DATABASE_URL, REDIS_URL, JWT_SECRET, AMPAI_ENV, AMPAI_DEFAULT_ADMIN_USERNAME, AMPAI_DEFAULT_ADMIN_PASSWORD, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, CONFIG_ENCRYPTION_KEY, OLLAMA_BASE_URL, ALLOWED_ORIGINS, TELEGRAM_BOT_TOKEN, WEB_SEARCH_PROVIDER, BROWSER_AUTOMATION_ENABLED, BROWSER_HEADLESS, TERMINAL_TOOLS_ENABLED, TERMINAL_REQUIRE_CONFIRMATION
    - Include description, example/default value, and required/optional status for each
    - Mark placeholder values clearly as needing replacement
    - _Requirements: 1.6, 17.3_

  - [x] 1.3 Update docker-entrypoint.sh with main.py path validation
    - Check for main.py existence at expected paths
    - Exit with non-zero status and log error if not found
    - _Requirements: 1.5_

- [x] 2. Configuration Validation and Security
  - [x] 2.1 Create config_validator.py with unsafe default detection
    - Implement UNSAFE_DEFAULTS dict for JWT_SECRET, AMPAI_DEFAULT_ADMIN_PASSWORD, POSTGRES_PASSWORD
    - Detect production mode from AMPAI_ENV (case-insensitive "production" or "prod")
    - In production: terminate with non-zero exit code and error log for unsafe defaults
    - In non-production: log warnings but allow startup
    - Ensure validation runs before any network listener binds
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 2.2 Integrate config_validator into main.py startup sequence
    - Call validate_config() before uvicorn bind in the startup lifecycle
    - Ensure no requests are served while configuration is unsafe
    - _Requirements: 2.6_

- [x] 3. Database Schema Consolidation and Migration
  - [x] 3.1 Refactor database.py to consolidate all table definitions
    - Remove duplicate Table() declarations across the codebase
    - Define single authoritative schema: users, app_configs, chat_message_store, session_metadata, core_memories, memory_candidates, memory_summary_nodes, memory_events, memory_embeddings, tasks, audit_events, browser_profiles, browser_sessions, automation_jobs, terminal_command_logs, telegram_users
    - Add all performance indexes per design (memory_candidates, memory_summary_nodes, memory_events, tasks, chat_message_store, session_metadata, audit_events)
    - _Requirements: 3.1, 3.3, 3.4_

  - [x] 3.2 Create migration_runner.py with safe additive-only migrations
    - Implement MigrationRunner class with register(), run_pending(), _get_applied_versions(), _mark_applied()
    - Create _migrations tracking table for applied versions
    - Use CREATE TABLE IF NOT EXISTS and ADD COLUMN IF NOT EXISTS patterns only
    - Implement rollback on failure: roll back changes from failed step, log error, leave existing data unmodified
    - Enforce 30-second timeout for all pending migrations
    - Implement connection retry: 3 attempts with 2-second delay
    - _Requirements: 3.1, 3.2, 3.5, 3.6, 3.7_

  - [x] 3.3 Integrate migration_runner into application startup
    - Call MigrationRunner.run_pending() after config validation but before router registration
    - Handle timeout and connection errors gracefully
    - _Requirements: 3.6, 3.7_

  - [ ]* 3.4 Write property test for idempotent migrations
    - **Property 5: Idempotent Migrations**
    - Running migration_runner multiple times produces the same schema state
    - All migrations use IF NOT EXISTS guards
    - **Validates: Requirements 3.1, 3.5**

- [x] 4. Checkpoint - Ensure infrastructure tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Core Audit Logger
  - [x] 5.1 Create core/audit.py with AuditLogger class
    - Implement append-only insert into audit_events table
    - Store: username, action_type, session_id, category, details (max 2000 chars), server-generated timestamp
    - Implement query() with filters: action_type, username, date_from, date_to, session_id, limit (max 1000), offset
    - If audit logging fails, continue original operation and log failure to application error log
    - Define action type constants: memory_write, memory_read, memory_delete, browser_action, browser_navigate, terminal_execute, terminal_blocked, telegram_message, backup_run, backup_restore, login_attempt, web_search, config_change
    - _Requirements: 15.1, 15.6, 15.7_

  - [ ]* 5.2 Write property test for audit completeness
    - **Property 3: Audit Completeness**
    - Every browser action, terminal command, and memory write produces exactly one audit event
    - No security-sensitive operation completes without an audit record attempt
    - **Validates: Requirements 15.1, 15.2, 15.3**

- [x] 6. Memory Service and Endpoints
  - [x] 6.1 Create services/memory_service.py as unified memory facade
    - Implement MemoryService class wrapping memory_indexer, memory_curator, memory_persistence
    - Implement save_chat_turn(): persist message and trigger candidate evaluation (importance > 0.15 → pending)
    - Implement capture_candidate(): create memory candidate with importance score
    - Implement save_explicit_memory(): save directly to core_memories for "remember ..." commands (max 1000 chars)
    - Implement approve_candidate(): promote to core memory + vector index
    - Implement reject_candidate(): mark as rejected, exclude from retrieval
    - Implement search_memory(): hybrid search (vector + FTS), compress to char_budget (default 1200), return MemorySearchResult with metadata
    - Implement forget_memory(): delete from core_memories and vector index
    - Return retrieval metadata: retrieved_count, context_chars, pipeline, latency_ms
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 5.11_

  - [x] 6.2 Extend routers/memory.py with full memory endpoints
    - GET /api/memory/core: list core memories
    - POST /api/memory/core: add explicit memory
    - DELETE /api/memory/core/{id}: delete/forget memory (return error if not found)
    - GET /api/memory/inbox: list pending candidates (max 50, ordered by created_at DESC)
    - PATCH /api/memory/inbox/{id}: approve/reject candidate (return error if not found)
    - POST /api/memory/search: hybrid memory search with configurable settings
    - Integrate AuditLogger for memory_write, memory_read, memory_delete events
    - _Requirements: 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9_

  - [ ]* 6.3 Write property test for memory consistency
    - **Property 1: Memory Consistency**
    - A memory saved via "remember ..." is immediately searchable via "search memory: ..."
    - Core_memories table and vector index are updated atomically
    - **Validates: Requirements 5.2, 5.3**

  - [ ]* 6.4 Write property test for token budget enforcement
    - **Property 6: Token Budget Enforcement**
    - Memory context injected into LLM prompts never exceeds memory_context_char_budget (default 1200 chars)
    - MemoryService truncates and compresses results before returning
    - **Validates: Requirements 5.3, 5.10**

- [x] 7. Chat History and Session Management
  - [x] 7.1 Create routers/sessions.py with session CRUD endpoints
    - GET /api/sessions: list sessions paginated (default 40), sorted by pinned first then updated_at DESC
    - POST /api/sessions: create new session with optional title and category
    - PATCH /api/sessions/{id}: update title (max 100 chars), category, pinned, archived
    - DELETE /api/sessions/{id}: delete session metadata, all chat messages, and session recall index entries
    - GET /api/history/{session_id}: get all messages for a session
    - Enforce user ownership checks on all endpoints
    - _Requirements: 4.1, 4.2, 4.5, 4.6_

  - [x] 7.2 Extend routers/chat.py to persist full message metadata
    - Save user message, assistant response, timestamp, model provider, memory retrieval metadata, web search metadata, and tool/action metadata per session
    - Accept extended ChatRequest payload: session_id, message, model_type, model_name, memory_mode, memory_top_k, memory_recency_bias, memory_category_filter, use_web_search, enable_browser_tools, enable_terminal_tools, chat_output_mode, attachments
    - _Requirements: 4.4, 12.2_

  - [ ]* 7.3 Write property test for session isolation
    - **Property 2: Session Isolation**
    - Users can only access their own sessions unless they have admin role
    - All session endpoints enforce ownership checks
    - **Validates: Requirements 4.5, 4.6**

- [x] 8. Model Provider Routing
  - [x] 8.1 Extend routers/models_router.py with health and options endpoints
    - GET /api/models/options: return available providers filtered by local_only_mode
    - GET /api/models/health: return JSON per provider with name, ok boolean, latency_ms
    - Implement fallback chain: Ollama → OpenRouter → OpenAI → Gemini → Anthropic → Generic → AmpAI_Default
    - Handle local_only_mode: route to Ollama, fallback to AmpAI_Default if unreachable (8s timeout)
    - Handle cloud fallback: skip providers without configured API keys
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x] 8.2 Implement local embedding fallback in memory_indexer
    - If no cloud embedding API key configured and Ollama reachable: use nomic-embed-text via Ollama
    - If no cloud embedding API key and Ollama unreachable: report error, disable vector retrieval
    - _Requirements: 6.7, 6.8_

- [x] 9. Checkpoint - Ensure core services tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Web Search Service
  - [x] 10.1 Create services/web_search_service.py with multi-provider support
    - Implement WebSearchService with provider order: DuckDuckGo (default, no key), Tavily, SerpAPI, Brave Search
    - Implement search(): try providers in order until one succeeds
    - Implement summarize_for_context(): compress results to char_budget (1200 chars)
    - Enforce 10-second timeout per provider, fallback to next on failure
    - Return SearchHit objects with title, url, snippet, provider, timestamp
    - _Requirements: 7.1, 7.2, 7.3, 7.5, 7.6_

  - [x] 10.2 Add POST /api/tools/web-search endpoint
    - Accept query (1-500 chars), return summarized results within 15 seconds
    - Log search to AuditLogger: query, provider, result_count, latency_ms
    - If all providers fail, return response without search results with error status
    - _Requirements: 7.1, 7.4, 7.6_

  - [ ]* 10.3 Write unit tests for web search provider fallback
    - Test nominal path: primary provider returns results
    - Test error path: primary fails, fallback succeeds
    - Test all-fail path: returns empty with error status
    - _Requirements: 7.5, 7.6_

- [x] 11. Browser Automation
  - [x] 11.1 Create policy/browser_policy.py with domain allowlist enforcement
    - Implement domain allowlist check: empty allowlist blocks all navigation
    - Validate URLs against allowlist before any browser action
    - _Requirements: 8.3, 8.10_

  - [x] 11.2 Create services/browser_automation_service.py with Playwright integration
    - Implement BrowserAutomationService with all actions: open, navigate, click, type, submit, extract, screenshot, summarize, close
    - Enforce disabled-by-default (BROWSER_AUTOMATION_ENABLED=false)
    - Use headed browser by default (BROWSER_HEADLESS=false)
    - Implement confirmation flow: return confirmation_required, wait 60s for approval, cancel on timeout/denial
    - Enforce 30-second action timeout: abort action, close tab, return timeout error
    - Refuse password reading, MFA/captcha bypass, paywall bypass
    - Use only user-provided credentials for login automation
    - Log each action to AuditLogger: action type, target URL/element, timestamp, outcome
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10_

  - [x] 11.3 Create routers/browser.py with browser automation endpoints
    - POST /api/browser/open, navigate, search, click, type, submit, extract, screenshot, close
    - GET /api/browser/jobs: list automation jobs
    - GET /api/browser/allowlist (admin): get domain allowlist
    - POST /api/browser/allowlist (admin): update domain allowlist
    - _Requirements: 8.11_

  - [ ]* 11.4 Write property test for disabled-by-default tools
    - **Property 7: Disabled-by-Default Tools**
    - Browser automation returns HTTP 403 unless explicitly enabled by admin
    - Check occurs before any tool logic executes
    - **Validates: Requirements 8.2, 9.2**

- [x] 12. Terminal Access
  - [x] 12.1 Create policy/terminal_policy.py with command security validation
    - Implement DANGEROUS_PATTERNS regex list per design
    - Implement denylist/allowlist with denylist precedence (max 500 entries each)
    - Implement allowed_folders check: reject commands referencing paths outside approved folders
    - _Requirements: 9.3, 9.4, 9.5_

  - [x] 12.2 Create services/terminal_service.py with shell command executor
    - Implement TerminalService with check_enabled(), validate_command(), execute()
    - Support macOS shell, Windows PowerShell, Windows CMD (auto-detect)
    - Enforce disabled-by-default with per-session confirmation
    - Enforce configurable timeout (default 30s, range 1-300s) and output limit (default 10000 chars, range 100-1000000)
    - Terminate on timeout with partial output
    - Log to AuditLogger: command, working_directory, exit_code, execution_ms, output (truncated)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.9_

  - [x] 12.3 Create routers/terminal.py with terminal endpoints
    - POST /api/terminal/run: execute command with confirmation flow
    - GET /api/terminal/logs: get command execution history
    - GET /api/terminal/policy (admin): get current terminal policy
    - PATCH /api/terminal/policy (admin): update allowlist/denylist/folders
    - _Requirements: 9.8_

  - [ ]* 12.4 Write property test for denylist precedence
    - **Property 4: Denylist Precedence**
    - If a command matches both allowlist and denylist, denylist takes precedence and command is blocked
    - Denylist is evaluated first
    - **Validates: Requirements 9.4, 9.5**

- [x] 13. Checkpoint - Ensure browser and terminal tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Telegram Bot Integration
  - [x] 14.1 Extend integrations/telegram_api.py with full bot lifecycle
    - Support webhook and long-polling modes (only one active; enabling polling deregisters webhook)
    - Resolve Telegram user ID to AmpAI username via telegram_users table
    - Silently discard messages from user IDs not in allowed_telegram_user_ids, log audit event
    - Use same Chat_History_Store and Memory_System with session_id prefixed "tg_"
    - Support memory commands and task commands through same chat pipeline
    - Refuse browser/terminal commands unless admin explicitly enables Telegram tool access
    - Implement rate limiting: discard messages beyond 8 per user per 20-second window
    - On processing failure: send generic failure notification, log audit event
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8_

  - [x] 14.2 Extend routers/integrations.py with Telegram admin endpoints
    - GET /api/admin/integrations/telegram/status: bot connection status
    - POST /api/admin/integrations/telegram/save: save bot config
    - POST /api/admin/integrations/telegram/test: test bot token
    - POST /api/telegram/webhook: webhook receiver
    - POST /api/admin/telegram/enable-polling: start long-polling
    - POST /api/admin/telegram/disable-polling: stop long-polling
    - _Requirements: 10.9_

  - [ ]* 14.3 Write unit tests for Telegram rate limiting and access control
    - Test rate limit: 9th message in 20s window is discarded
    - Test access control: unknown user ID is silently discarded with audit log
    - Test tool access: browser/terminal refused unless admin-enabled
    - _Requirements: 10.3, 10.6, 10.7_

- [x] 15. Task Memory and Suggestions
  - [x] 15.1 Create routers/tasks.py with task CRUD endpoints
    - GET /api/tasks: list tasks paginated (default 20), filterable by status, priority, due date range, searchable by title/description
    - POST /api/tasks: create task with title (max 150 chars), description (max 1000 chars), priority, due_at, session_id
    - PATCH /api/tasks/{id}: update task, allow status transitions (todo, in_progress, done) in any direction
    - DELETE /api/tasks/{id}: delete task
    - _Requirements: 11.2, 11.4, 11.5, 11.6_

  - [x] 15.2 Implement task intent detection in chat pipeline
    - Detect task-related intent keywords: todo, remind me, I need to, follow up, deadline, action item, task
    - Generate task suggestion with title, description, priority, optional due date
    - On approval: create task with status todo, link to source session
    - On rejection: mark suggestion as dismissed
    - _Requirements: 11.1, 11.4, 11.5_

  - [ ]* 15.3 Write unit tests for task intent detection
    - Test detection of task keywords in messages
    - Test suggestion approval creates task linked to session
    - Test suggestion rejection marks as dismissed
    - _Requirements: 11.1, 11.4, 11.5_

- [x] 16. Agent Learning Loop and Skill Engine
  - [x] 16.1 Implement skill detection and CRUD endpoints
    - Detect repeated patterns (3+ sessions in 30-day window) and suggest skill creation
    - Require user/admin approval before activation
    - Assign safety levels: read-only, write (per-execution confirmation), privileged (admin approval + confirmation)
    - Implement endpoints: GET/POST/PATCH/DELETE /api/skills, POST /api/skills/{id}/execute, GET /api/skills/{id}/metrics
    - On failure: halt skill, preserve pre-execution state, return error
    - Record rejections, don't re-suggest same pattern unless user requests
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

- [x] 17. Checkpoint - Ensure all service tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 18. Desktop Application Upgrades
  - [x] 18.1 Refactor desktop/src/state.ts with new feature states
    - Add BrowserState, TerminalState, TaskState interfaces
    - Add S.browserState, S.terminalState, S.taskState to global state
    - Add S.enableBrowserTools, S.enableTerminalTools per-chat toggles
    - _Requirements: 12.1, 12.2_

  - [x] 18.2 Refactor desktop/src/main.ts with sidebar and tab routing
    - Implement collapsible left sidebar with tabs: Chat, Memory, Tasks, Browser, Terminal, Telegram Settings, Admin Settings
    - Persist sidebar collapse state to local storage
    - Implement server probe on startup (5s timeout per candidate), show Online/Offline status
    - Implement theme accent colour selection (predefined palette + custom hex), persist to local storage
    - Handle chat request failures: display error in chat area, re-enable send button within 1s
    - _Requirements: 12.1, 12.3, 12.4, 12.5, 12.6_

  - [x] 18.3 Create desktop/src/tabs-tasks.ts with task management UI
    - Display columns: todo, in_progress, done
    - Show priority indicators, due dates, source chat links
    - Implement search by title/description, filter by status/priority/due date range
    - _Requirements: 11.3_

  - [x] 18.4 Create desktop/src/tabs-browser.ts with browser automation UI
    - Show automation enable/disable status
    - Display domain allowlist configuration
    - Show scrollable action history (most recent 200 entries)
    - _Requirements: 8.12_

  - [x] 18.5 Create desktop/src/tabs-terminal.ts with terminal tools UI
    - Show terminal policy (enabled/disabled, allowed folders, allowlist/denylist)
    - Display command history (most recent 200 entries)
    - Provide execution controls
    - _Requirements: 9.10_

  - [x] 18.6 Update desktop/src/tabs-a.ts with ChatGPT-style session sidebar
    - Display sessions sorted by pinned first, then updated_at DESC, paginated (40 per page, load more on scroll)
    - Implement controls: new chat, rename (max 100 chars), search (filter within 300ms), pin, archive, delete, assign category
    - Display error on failed delete/archive operations
    - _Requirements: 4.1, 4.2, 4.3, 4.7_

- [x] 19. Backup and Restore
  - [x] 19.1 Refactor services/backup_service.py from backup_helpers.py
    - Implement daily automated backup of database (chat history, memories, core memories, users, configs, personas, tasks)
    - Generate manifest: schema version, timestamp, session count, message count, SHA-256 checksum
    - Support local filesystem and FTP destinations with configurable profiles (type, host, path, credentials, retention count)
    - Implement restore with preflight validation: schema version compatibility, checksum integrity, DB connectivity, disk space
    - Reject restore on preflight failure with list of failed checks (expected vs actual values)
    - Log backup/restore operations to AuditLogger: actor, operation type, status, job ID, item counts
    - Record failures with error details in backup status history
    - _Requirements: 13.1, 13.2, 13.4, 13.5, 13.6, 13.7_

  - [x] 19.2 Extend routers/admin.py with backup endpoints
    - POST /api/admin/backup/run: trigger manual backup
    - GET /api/admin/backup/jobs: list backup history
    - POST /api/admin/backup/test-ftp: test FTP connection
    - GET /api/admin/backup/profiles: list backup profiles
    - POST /api/admin/backup/profiles: create backup profile
    - PATCH /api/admin/backup/profiles/{id}: update backup profile
    - _Requirements: 13.3_

  - [ ]* 19.3 Write unit tests for backup preflight validation
    - Test successful preflight with valid archive
    - Test failed preflight: schema mismatch, checksum failure, DB unreachable
    - _Requirements: 13.4, 13.5_

- [x] 20. Audit Logging Endpoints and Retention
  - [x] 20.1 Extend routers/admin.py with audit log query endpoint
    - GET /api/admin/audit-logs: filter by action_type, username, date_range, session_id
    - Max 1000 results per request, support limit parameter for pagination
    - Enforce append-only: no UPDATE or DELETE through application
    - Implement 90-day retention policy eligibility
    - _Requirements: 15.4, 15.5, 15.6, 15.8_

- [x] 21. Checkpoint - Ensure all feature tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 22. Testing Suite
  - [x] 22.1 Create test suite with subsystem isolation
    - Write at least one nominal-path and one error-path test for each subsystem:
      - Docker environment validation (config_validator)
      - Memory system operations
      - Chat history CRUD
      - Task CRUD
      - Web search integration
      - Browser automation security constraints
      - Terminal command blocking
      - Telegram message handling
      - Backup and restore
      - local_only_mode enforcement
      - Desktop chat payload structure
    - Use mocks/stubs for database, Redis, network, third-party APIs
    - Ensure failure in one subsystem does not prevent other tests from running
    - Exit with non-zero code on any test failure
    - _Requirements: 16.1, 16.2, 16.3, 16.4_

- [x] 23. Documentation
  - [x] 23.1 Create docs/ directory with all documentation files
    - docs/MEMORY_ARCHITECTURE.md: memory system design, retrieval pipeline, configuration
    - docs/BROWSER_AUTOMATION.md: setup, domain allowlist, security constraints, usage
    - docs/TERMINAL_TOOLS.md: setup, policy configuration, dangerous command blocking
    - docs/TELEGRAM_BOT.md: bot setup, webhook/polling modes, rate limiting, tool access
    - docs/BACKUP_AND_RESTORE.md: backup profiles, scheduling, restore procedure, preflight checks
    - docs/MODEL_PROVIDERS.md: supported providers, fallback chain, local_only_mode, health checks
    - docs/SECURITY_POLICY.md: per-tool permitted/denied operations, override conditions
    - _Requirements: 17.1, 17.4_

  - [x] 23.2 Update README.md with quickstart instructions
    - Document `docker compose up -d --build` as primary setup method
    - List system prerequisites and required port availability
    - Include verification step confirming deployment is running
    - _Requirements: 17.2_

- [x] 24. Final Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at infrastructure, core services, advanced features, and final integration stages
- Property tests validate universal correctness properties defined in the design document
- Unit tests validate specific examples and edge cases
- The backend uses Python (FastAPI, SQLAlchemy, Playwright, pytest)
- The desktop app uses TypeScript (Tauri, Vite)
- All services follow the disabled-by-default security pattern for browser and terminal tools

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2", "3.1"] },
    { "id": 3, "tasks": ["3.2"] },
    { "id": 4, "tasks": ["3.3", "3.4", "5.1"] },
    { "id": 5, "tasks": ["5.2", "6.1"] },
    { "id": 6, "tasks": ["6.2", "6.3", "6.4", "8.1"] },
    { "id": 7, "tasks": ["7.1", "7.2", "8.2"] },
    { "id": 8, "tasks": ["7.3", "10.1", "11.1", "12.1"] },
    { "id": 9, "tasks": ["10.2", "10.3", "11.2", "12.2"] },
    { "id": 10, "tasks": ["11.3", "11.4", "12.3", "12.4"] },
    { "id": 11, "tasks": ["14.1", "15.1"] },
    { "id": 12, "tasks": ["14.2", "14.3", "15.2", "15.3"] },
    { "id": 13, "tasks": ["16.1"] },
    { "id": 14, "tasks": ["18.1", "19.1"] },
    { "id": 15, "tasks": ["18.2", "18.3", "18.4", "18.5", "19.2", "19.3"] },
    { "id": 16, "tasks": ["18.6", "20.1"] },
    { "id": 17, "tasks": ["22.1"] },
    { "id": 18, "tasks": ["23.1", "23.2"] }
  ]
}
```
