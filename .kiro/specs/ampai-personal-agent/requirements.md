# Requirements Document

## Introduction

AmpAI Personal Agent is a comprehensive personal AI desktop and Docker agent that combines chat, long-term memory, offline/online AI model support, web search, Telegram bot integration, browser automation, and controlled terminal access into a unified platform. The system builds upon the existing AmpAI FastAPI backend, PostgreSQL with pgvector, Redis, and Tauri desktop application. This document specifies the requirements for completing and hardening all subsystems into a production-ready personal agent.

## Glossary

- **AmpAI_Server**: The FastAPI Python backend application serving the REST API on ports 8000 and 8001
- **Desktop_App**: The Tauri + Vite + TypeScript desktop application that connects to AmpAI_Server
- **Agent_Postgres**: The PostgreSQL 16 database service with pgvector extension for vector similarity search
- **Redis_Service**: The Redis 7 instance used for session message history and caching
- **Memory_System**: The subsystem responsible for capturing, indexing, retrieving, and managing long-term user memories
- **Memory_Indexer**: The component that performs vector similarity search using pgvector and hybrid retrieval
- **Chat_History_Store**: The SQL-based persistent storage for all chat messages organized by session
- **Session_Manager**: The component managing chat session lifecycle including creation, metadata, archival, and deletion
- **Model_Router**: The component that resolves and routes AI requests to the appropriate provider (Ollama, OpenAI, Gemini, Anthropic, OpenRouter, Generic, AnythingLLM, AmpAI_Default)
- **Web_Search_Engine**: The component that queries external search APIs and summarizes results for AI context injection
- **Browser_Automation_Engine**: The Playwright-based component that performs controlled browser actions on behalf of the user
- **Terminal_Executor**: The component that executes shell commands (macOS shell, Windows PowerShell, Windows CMD) within security constraints
- **Telegram_Bot**: The integration that connects a Telegram bot to the AmpAI chat and memory system
- **Backup_Engine**: The component responsible for scheduled and manual database and memory backups
- **Audit_Logger**: The component that records security-relevant actions (memory writes, browser actions, terminal commands, Telegram events, backup operations)
- **Skill_Engine**: The component that detects repeated workflows and suggests reusable skill creation
- **Migration_Runner**: The component that safely applies database schema changes with rollback support
- **Config_Validator**: The component that validates environment variables and blocks unsafe production configurations

## Requirements

### Requirement 1: Docker Environment and Service Orchestration

**User Story:** As a developer, I want to start the entire AmpAI stack with a single docker compose command, so that I can run the agent locally without manual service configuration.

#### Acceptance Criteria

1. WHEN `docker compose up -d --build` is executed, THE AmpAI_Server SHALL start the Agent_Postgres service using image pgvector/pgvector:pg16 with container name ampai-agent-postgres, volume agent_postgres_data:/var/lib/postgresql/data, and a health check that verifies PostgreSQL readiness using `pg_isready` with interval 5s, timeout 5s, and 20 retries
2. WHEN `docker compose up -d --build` is executed, THE AmpAI_Server SHALL start the Redis_Service using image redis:7-alpine with a health check that verifies connectivity using `redis-cli ping` with interval 5s, timeout 3s, and 20 retries
3. WHEN `docker compose up -d --build` is executed, THE AmpAI_Server SHALL start the ampai server service mapping host ports 8000 and 8001 to container ports 8000 and 8001, with startup blocked until both Agent_Postgres and Redis_Service report healthy status
4. THE AmpAI_Server SHALL read all service configuration from environment variables, including at minimum: DATABASE_URL, REDIS_URL, JWT_SECRET, AMPAI_DEFAULT_ADMIN_USERNAME, AMPAI_DEFAULT_ADMIN_PASSWORD, and ALLOWED_ORIGINS
5. IF the ampai server entrypoint cannot locate main.py, THEN THE AmpAI_Server SHALL exit with a non-zero status code and log an error message indicating which paths were checked
6. WHEN the .env file is missing, THE AmpAI_Server SHALL provide a .env.example file documenting all required variables (DATABASE_URL, REDIS_URL, JWT_SECRET) and optional variables (OLLAMA_BASE_URL, ALLOWED_ORIGINS, TELEGRAM_BOT_TOKEN, WEB_SEARCH_PROVIDER) with non-production placeholder values clearly marked as needing replacement

### Requirement 2: Configuration Validation and Security

**User Story:** As an administrator, I want the server to refuse to start in production mode with unsafe default credentials, so that the system is not accidentally deployed with known passwords.

#### Acceptance Criteria

1. WHEN JWT_SECRET equals "change-me" or "change-me-for-production" and the environment is production, THE Config_Validator SHALL terminate the process with a non-zero exit code and log an error message indicating which secret remains at its unsafe default value
2. WHEN AMPAI_DEFAULT_ADMIN_PASSWORD equals "P@ssw0rd" or "change-this" and the environment is production, THE Config_Validator SHALL terminate the process with a non-zero exit code and log an error message indicating the admin password is at its unsafe default value
3. WHEN all required environment variables (JWT_SECRET, AMPAI_DEFAULT_ADMIN_PASSWORD, AMPAI_ENV) are present and none match their unsafe default values listed in criteria 1 and 2, THE Config_Validator SHALL allow server startup to proceed without logging any validation errors
4. THE Config_Validator SHALL determine production mode from the AMPAI_ENV environment variable where values "production" and "prod" (case-insensitive) indicate production mode, and any other value or an unset variable indicates non-production mode
5. WHEN the environment is non-production and JWT_SECRET or AMPAI_DEFAULT_ADMIN_PASSWORD equals an unsafe default value, THE Config_Validator SHALL log a warning message indicating the unsafe default but SHALL allow server startup to proceed
6. THE Config_Validator SHALL execute all validation checks before any network listener is bound, so that no requests are served while configuration is unsafe

### Requirement 3: Database Schema Consolidation and Migration

**User Story:** As a developer, I want a single authoritative database schema without duplicate table definitions, so that migrations are predictable and data integrity is maintained.

#### Acceptance Criteria

1. THE Migration_Runner SHALL define each database table exactly once across the entire codebase, with no duplicate Table() declarations or CREATE TABLE statements for the same table name
2. WHEN a migration adds or alters columns on an existing table, THE Migration_Runner SHALL preserve all existing rows and their data without deletion or type-coercion loss
3. THE Migration_Runner SHALL create the following tables if they do not exist: users, app_configs, chat_message_store, session_metadata, core_memories, memory_candidates, memory_summary_nodes, memory_events, memory_embeddings, tasks, audit_events, browser_profiles, browser_sessions, automation_jobs, terminal_command_logs, telegram_users
4. THE Migration_Runner SHALL create performance indexes on the following columns: memory_candidates(username, status, created_at), memory_candidates(session_id), memory_summary_nodes(username, topic, created_at), memory_events(username, created_at), tasks(username, status, due_at), chat_message_store(session_id), session_metadata(updated_at), and audit_events(username, created_at)
5. IF a migration statement fails, THEN THE Migration_Runner SHALL roll back all changes from that migration step, log the error with the failed statement and exception detail to the application logger, and leave all pre-existing tables and data unmodified
6. WHEN the Migration_Runner executes on application startup, THE Migration_Runner SHALL complete all pending migrations within 30 seconds or abort with a timeout error logged to the application logger
7. IF the database is unreachable at migration time, THEN THE Migration_Runner SHALL retry the connection up to 3 times with a 2-second delay between attempts before raising a startup failure error

### Requirement 4: ChatGPT-Style Chat History

**User Story:** As a user, I want my chat sessions displayed in a sidebar like ChatGPT with search, pin, archive, and category features, so that I can easily navigate and organize my conversation history.

#### Acceptance Criteria

1. THE Desktop_App SHALL display chat sessions in a left sidebar sorted by pinned sessions first, then by most recently updated timestamp descending, paginated with a default page size of 40 sessions and the ability to load more on scroll
2. THE Desktop_App SHALL provide controls to create a new chat, rename a session display title (maximum 100 characters), search sessions, pin a session, archive a session, delete a session, and assign a category to a session
3. WHEN a user types a search query of at least 1 character into the session search field, THE Desktop_App SHALL filter the visible session list to sessions whose display title or category name contains the query text, updating results within 300 milliseconds of the last keystroke
4. WHEN a user sends a message, THE Chat_History_Store SHALL persist the user message, assistant response, timestamp, model provider used, memory retrieval metadata, web search metadata, and tool/action metadata within the same session record
5. THE AmpAI_Server SHALL expose endpoints GET /api/sessions, POST /api/sessions, PATCH /api/sessions/{id}, DELETE /api/sessions/{id}, and GET /api/history/{session_id} for session management
6. WHEN a session is deleted, THE Session_Manager SHALL remove the session metadata, all associated chat messages from the Chat_History_Store, and the session recall index entries, and SHALL return a success confirmation to the client
7. IF a session delete or archive operation fails due to a storage error, THEN THE Desktop_App SHALL display an error message indicating the operation could not be completed and SHALL leave the session in its previous state

### Requirement 5: Long-Term Memory System

**User Story:** As a user, I want AmpAI to remember important facts about me across sessions and retrieve them efficiently using minimal tokens, so that conversations feel continuous and personalized.

#### Acceptance Criteria

1. WHEN a chat turn is completed, THE Memory_System SHALL evaluate the exchange for memory-worthy content and create a memory candidate with an importance score between 0.0 and 1.0, where candidates scoring below 0.15 are discarded and candidates scoring 0.15 or above are persisted with status "pending"
2. WHEN the user sends a message matching "remember ...", "save to memory ...", "add to memory ...", "store this in memory ...", or "memorize ...", THE Memory_System SHALL extract the fact (truncated to a maximum of 1000 characters), save it directly to core memories, and confirm the save to the user
3. WHEN the user sends a message matching "what do you remember about ...?" or "search memory: ...", THE Memory_System SHALL perform a hybrid search (vector + FTS) and return the top memories (limited by the memory_top_k setting, default 5) compressed to the memory_context_char_budget setting (default 1200 characters) or fewer
4. WHEN the user sends "forget memory {id}", THE Memory_System SHALL delete the specified memory from core memories and the vector index and confirm deletion to the user
5. IF the user sends "forget memory {id}" and no memory with that id exists, THEN THE Memory_System SHALL return an error indication stating the memory was not found
6. WHEN the user sends "show pending memories", THE Memory_System SHALL return all memory candidates with status "pending", limited to the 50 most recent candidates ordered by creation date descending
7. WHEN the user sends "approve memory {id}", THE Memory_System SHALL promote the candidate to core memories and index it in the vector store
8. IF the user sends "approve memory {id}" or "reject memory {id}" and no candidate with that id exists, THEN THE Memory_System SHALL return an error indication stating the candidate was not found
9. WHEN the user sends "reject memory {id}", THE Memory_System SHALL mark the candidate as rejected and exclude it from future retrieval results
10. THE Memory_System SHALL support configurable settings: memory_top_k (integer, range 1-8, default 5), memory_context_char_budget (integer, range 200-4000, default 1200), memory_recency_bias (float, range 0.0-1.0, default 0.0), memory_mode (one of: full, indexed, context_only, none), and memory_category_filter (string matching an existing category name or empty for no filter)
11. THE Memory_System SHALL return retrieval metadata with each response including retrieved_count, context_chars, pipeline used, and latency_ms

### Requirement 6: Offline Chat and Model Provider Routing

**User Story:** As a user, I want to chat with AmpAI even when I have no internet connection using a local AI model, so that the agent remains functional offline.

#### Acceptance Criteria

1. WHEN Ollama is running locally, THE Model_Router SHALL route chat requests to the configured Ollama model using the configured base URL and return the model's response to the user within the configured timeout period (default 30 seconds)
2. IF Ollama is unreachable (connection fails or no response within 8 seconds) and local_only_mode is enabled, THEN THE Model_Router SHALL route the request to the AmpAI_Default built-in response engine and return a response generated from rule-based intent detection and stored memory facts
3. IF local_only_mode is disabled and Ollama is unreachable, THEN THE Model_Router SHALL attempt cloud providers in the following order: OpenRouter, OpenAI, Gemini, Anthropic, Generic, skipping any provider whose API key is not configured, and routing to the first provider that responds successfully
4. IF local_only_mode is disabled, Ollama is unreachable, and all cloud providers in the fallback chain fail or lack configured API keys, THEN THE Model_Router SHALL route the request to the AmpAI_Default built-in response engine
5. THE AmpAI_Server SHALL expose a GET /api/models/options endpoint that returns the list of available providers (filtered to local-only providers when local_only_mode is enabled) and the configured model names for each provider
6. THE AmpAI_Server SHALL expose a GET /api/models/health endpoint that returns a JSON object for each configured provider containing: provider name, an "ok" boolean indicating reachability, and latency_ms
7. IF no cloud embedding API key is configured and Ollama is reachable, THEN THE Memory_Indexer SHALL use local embeddings with the nomic-embed-text model via Ollama at the configured base URL
8. IF no cloud embedding API key is configured and Ollama is unreachable, THEN THE Memory_Indexer SHALL report an error indicating that no embedding provider is available and disable vector-based memory retrieval until a provider becomes available

### Requirement 7: Web Search API Integration

**User Story:** As a user, I want AmpAI to search the web and include summarized results in its responses, so that I get up-to-date information without leaving the chat.

#### Acceptance Criteria

1. THE AmpAI_Server SHALL expose POST /api/tools/web-search accepting a query string of 1 to 500 characters and returning summarized search results within 15 seconds
2. THE Web_Search_Engine SHALL support providers: DuckDuckGo (default, no key required), Tavily, SerpAPI, and Brave Search
3. WHEN web search is enabled for a chat request, THE Web_Search_Engine SHALL retrieve up to 5 results from the selected provider and summarize them into a context block of no more than 1200 characters before injecting into the AI context
4. WHEN a web search is performed, THE Audit_Logger SHALL record the search query, provider used, result count, and response latency in milliseconds
5. IF a web search provider fails to respond within 10 seconds or returns a non-success status, THEN THE Web_Search_Engine SHALL attempt the next configured provider in priority order
6. IF all configured web search providers fail, THEN THE AmpAI_Server SHALL return the chat response without web search results and include a status field indicating the search was unavailable along with the error reason

### Requirement 8: Browser Automation

**User Story:** As a user, I want AmpAI to automate browser tasks like navigating websites and extracting information, so that I can delegate repetitive web tasks to the agent.

#### Acceptance Criteria

1. THE Browser_Automation_Engine SHALL support actions: open browser, navigate to URL, click element, type text, submit form, extract page content, take screenshot, and summarize page
2. THE Browser_Automation_Engine SHALL be disabled by default and require explicit admin enablement via the BROWSER_AUTOMATION_ENABLED setting
3. WHILE browser automation is enabled, THE Browser_Automation_Engine SHALL only navigate to domains listed in the configured domain allowlist, and SHALL treat an empty allowlist as blocking all navigation
4. WHEN a browser action is requested, THE Browser_Automation_Engine SHALL present the pending action description to the user and wait up to 60 seconds for explicit approval before executing
5. IF the user denies confirmation or the 60-second confirmation timeout elapses, THEN THE Browser_Automation_Engine SHALL cancel the pending action and return a message indicating the action was not executed
6. THE Browser_Automation_Engine SHALL use a visible headed browser instance by default (BROWSER_HEADLESS=false) and log each action (action type, target URL or element, timestamp, and outcome) to the Audit_Logger
7. IF a browser action does not complete within 30 seconds, THEN THE Browser_Automation_Engine SHALL abort the action, close the affected browser tab, and return a message indicating a timeout occurred
8. THE Browser_Automation_Engine SHALL refuse to read saved browser passwords, bypass MFA or captchas, or bypass paywalls or access controls
9. WHEN login automation is requested, THE Browser_Automation_Engine SHALL use only user-provided credentials in the visible headed browser
10. IF a navigation request targets a domain not present in the configured domain allowlist, THEN THE Browser_Automation_Engine SHALL reject the request and return a message indicating the domain is not permitted
11. THE AmpAI_Server SHALL expose endpoints for browser operations under /api/browser/ including open, navigate, search, click, type, submit, extract, screenshot, close, jobs, and allowlist management
12. THE Desktop_App SHALL provide a Browser Automation tab showing automation enable/disable status, domain allowlist configuration, and a scrollable action history displaying the most recent 200 entries

### Requirement 9: Terminal, CMD, and PowerShell Access

**User Story:** As a user, I want AmpAI to execute terminal commands on my behalf within strict security boundaries, so that I can automate development tasks without risking system damage.

#### Acceptance Criteria

1. THE Terminal_Executor SHALL support macOS shell, Windows PowerShell, and Windows CMD execution environments
2. THE Terminal_Executor SHALL be disabled by default and require explicit admin enablement with per-session confirmation, where a session is defined as the period between user login and logout or authentication token expiry
3. WHILE terminal access is enabled, THE Terminal_Executor SHALL only execute commands within admin-configured approved project folders and reject any command that references paths outside those folders with an error message indicating the path is not permitted
4. IF a submitted command matches the denylist or the blocked dangerous commands list (rm -rf /, format, del /s on system paths, Remove-Item -Recurse on system paths, shutdown, registry edits, credential dumping, token dumping, browser password export, keylogging, and stealth monitoring commands), THEN THE Terminal_Executor SHALL reject the command without execution and return an error message indicating the command is blocked by security policy
5. THE Terminal_Executor SHALL enforce a configurable command allowlist and denylist, where the denylist takes precedence when a command matches both lists, and each list supports a maximum of 500 entries
6. THE Terminal_Executor SHALL enforce a configurable timeout (default 30 seconds, range 1-300 seconds) and output size limit (default 10000 characters, range 100-1000000 characters) per command
7. IF a command exceeds the configured timeout, THEN THE Terminal_Executor SHALL terminate the command process and return an error message indicating the command was terminated due to timeout, along with any partial output captured up to the output size limit
8. THE AmpAI_Server SHALL expose POST /api/terminal/run, GET /api/terminal/logs, GET /api/terminal/policy, and PATCH /api/terminal/policy endpoints
9. WHEN a terminal command is executed, THE Audit_Logger SHALL record the command, working directory, exit code, execution time, and output truncated to the configured output size limit
10. THE Desktop_App SHALL provide a Terminal Tools tab showing terminal policy, command history (displaying the most recent 200 entries), and execution controls

### Requirement 10: Telegram Bot Integration

**User Story:** As a user, I want to chat with AmpAI through Telegram and have the same memory and history features available, so that I can interact with my agent from any device.

#### Acceptance Criteria

1. THE Telegram_Bot SHALL support both webhook and long-polling modes for receiving messages, where only one mode is active at a time and enabling polling SHALL deregister any active webhook
2. WHEN a Telegram message is received and a mapping exists in the telegram_users table, THE Telegram_Bot SHALL resolve the Telegram user ID to the mapped AmpAI username and route the message to that user's session
3. IF a Telegram message is received from a user ID not in the allowed_telegram_user_ids list, THEN THE Telegram_Bot SHALL silently discard the message and log an audit event
4. THE Telegram_Bot SHALL use the same Chat_History_Store and Memory_System as the desktop and web interfaces, storing conversation history under a session ID prefixed with "tg_"
5. THE Telegram_Bot SHALL support memory commands ("remember ...", "search memory: ...", "show pending memories") and task commands, processing them through the same chat pipeline used by other interfaces
6. THE Telegram_Bot SHALL refuse browser automation and terminal commands unless the admin explicitly enables Telegram tool access via the admin configuration endpoint
7. IF the Telegram_Bot receives more than 8 messages from the same user within a 20-second window, THEN THE Telegram_Bot SHALL silently discard additional messages until the window resets
8. IF message processing fails for any reason, THEN THE Telegram_Bot SHALL send a generic failure notification to the user's chat and log an audit event with the session ID
9. THE AmpAI_Server SHALL expose admin-only endpoints under /api/admin/integrations/telegram/ for saving bot configuration, testing the bot token, connecting and disconnecting the webhook, enabling and disabling polling, and viewing status

### Requirement 11: Task Memory and Suggestions

**User Story:** As a user, I want AmpAI to detect task intent from my conversations and suggest actionable tasks I can approve, so that I never forget follow-ups discussed in chat.

#### Acceptance Criteria

1. WHEN a chat message contains task-related intent (todo, remind me, I need to, follow up, deadline, action item, task), THE AmpAI_Server SHALL generate a task suggestion with title (maximum 150 characters), description (maximum 1000 characters), priority (low, medium, high, urgent), and optional due date
2. THE AmpAI_Server SHALL expose CRUD endpoints for tasks: GET /api/tasks (with pagination, default 20 items per page), POST /api/tasks, PATCH /api/tasks/{id}, DELETE /api/tasks/{id}
3. THE Desktop_App SHALL provide a Tasks tab with columns for todo, in_progress, and done statuses, priority indicators, due dates, source chat links, and controls to search by title or description text and filter by status, priority, and due date range
4. WHEN a task suggestion is approved by the user, THE AmpAI_Server SHALL create the task with the approved details, set its status to todo, and link it to the source session
5. WHEN a task suggestion is rejected by the user, THE AmpAI_Server SHALL mark the suggestion as dismissed and SHALL NOT create a task
6. WHEN a task is updated via PATCH /api/tasks/{id}, THE AmpAI_Server SHALL allow transitions between statuses todo, in_progress, and done in any direction

### Requirement 12: Desktop Application Upgrades

**User Story:** As a user, I want the Tauri desktop app to have a ChatGPT-like sidebar layout with tabs for all agent features, so that I can access chat, memory, tasks, browser, terminal, and settings from one interface.

#### Acceptance Criteria

1. THE Desktop_App SHALL display a collapsible left sidebar with tabs: Chat, Memory, Tasks, Browser, Terminal, Telegram Settings, and Admin Settings
2. WHEN the user sends a chat message, THE Desktop_App SHALL send a POST request to the AmpAI_Server chat endpoint with a JSON payload containing: session_id, message, model_type, model_name, memory_mode, memory_top_k, memory_recency_bias, memory_category_filter, use_web_search, enable_browser_tools, enable_terminal_tools, chat_output_mode, and attachments
3. WHEN the Desktop_App starts, THE Desktop_App SHALL probe the stored server URL with a per-candidate timeout of 5 seconds, and display a status indicator showing "Online" with the connected URL on success or "Offline" with "Cannot reach server" if all candidates fail
4. THE Desktop_App SHALL persist the sidebar collapse state to local storage so that on subsequent launches the sidebar renders in the same collapsed or expanded state as when the user last toggled it
5. WHEN the user selects a theme accent colour from the predefined palette or enters a custom hex colour value, THE Desktop_App SHALL apply the selected colour as the CSS accent variable and persist the selection to local storage
6. IF the chat request to the AmpAI_Server fails due to network error or server error, THEN THE Desktop_App SHALL display the error description in the chat message area and re-enable the send button within 1 second

### Requirement 13: Backup and Restore

**User Story:** As an administrator, I want daily automated backups of the database and memory with local and FTP storage options, so that I can recover from data loss.

#### Acceptance Criteria

1. THE Backup_Engine SHALL perform daily automated backups of the database including chat history, memories, core memories, users, configs, personas, and tasks, generating a manifest containing schema version, timestamp, session count, message count, and a SHA-256 checksum of the backup payload
2. THE Backup_Engine SHALL support local filesystem and FTP as backup destinations, each configurable via a backup profile specifying destination type, host, path, credentials, and retention count
3. THE AmpAI_Server SHALL expose admin-only endpoints: POST /api/admin/backup/run, GET /api/admin/backup/jobs, POST /api/admin/backup/test-ftp, GET /api/admin/backup/profiles, POST /api/admin/backup/profiles, and PATCH /api/admin/backup/profiles/{id}
4. WHEN a restore is requested, THE Backup_Engine SHALL perform a preflight validation checking schema version compatibility, archive checksum integrity, database connectivity, and available disk space before applying changes
5. IF preflight validation fails, THEN THE Backup_Engine SHALL reject the restore request and return the list of failed checks with their expected and actual values without modifying any data
6. WHEN a backup or restore operation completes or fails, THE Audit_Logger SHALL record the actor username, operation type (backup or restore), final status (success or failed), job identifier, and item counts
7. IF a backup operation fails due to destination unreachability or write error, THEN THE Backup_Engine SHALL record the failure with error details in the backup status history

### Requirement 14: Agent Learning Loop and Skill Engine

**User Story:** As a user, I want AmpAI to detect repeated workflows and suggest creating reusable skills, so that recurring tasks become automated over time.

#### Acceptance Criteria

1. WHEN a conversation pattern is detected as repeated in at least 3 sessions within a 30-day window, THE Skill_Engine SHALL suggest creating a skill with a name, description, and system prompt
2. WHEN a new skill is suggested, THE Skill_Engine SHALL require user or admin approval before activating the skill, and SHALL not execute the skill until approval is granted
3. THE Skill_Engine SHALL assign one of three safety levels to each skill: "read-only" (may retrieve data but not modify state), "write" (may modify user data with per-execution confirmation), or "privileged" (may invoke browser automation or terminal commands, requiring admin approval and per-execution confirmation)
4. IF a skill execution fails, THEN THE Skill_Engine SHALL halt the skill, preserve the pre-execution state, and return an error indication specifying the failure reason to the user
5. THE AmpAI_Server SHALL expose endpoints for skill CRUD (GET, POST, PATCH, DELETE), execution (POST /api/skills/{id}/execute), and performance metrics (GET /api/skills/{id}/metrics returning invocation count, success rate, and average execution duration) under /api/skills/
6. WHEN a user rejects a suggested skill, THE Skill_Engine SHALL record the rejection and SHALL not suggest the same pattern again unless the user explicitly requests re-evaluation

### Requirement 15: Audit Logging and Security

**User Story:** As an administrator, I want all security-sensitive actions logged in an audit trail, so that I can review agent behavior and detect misuse.

#### Acceptance Criteria

1. THE Audit_Logger SHALL record events for: memory writes, memory reads, browser actions, terminal commands, Telegram messages, backup operations, login attempts, and configuration changes, storing for each event the username, action type, session_id (if applicable), category, details (maximum 2000 characters), and a server-generated timestamp
2. WHEN a browser action is performed, THE Audit_Logger SHALL record the action type, target URL (maximum 2048 characters), domain, and timestamp
3. WHEN a terminal command is executed, THE Audit_Logger SHALL record the command text (maximum 2000 characters), working directory, exit code, and execution duration in milliseconds
4. THE AmpAI_Server SHALL expose GET /api/admin/audit-logs with filtering by action type, username, date range, and session_id, returning a maximum of 1000 results per request and supporting a limit parameter for pagination
5. THE Audit_Logger SHALL store credentials and session cookies only after the user confirms storage via an explicit approval prompt, and SHALL persist them in encrypted form using CONFIG_ENCRYPTION_KEY
6. THE Audit_Logger SHALL write audit records as append-only entries that cannot be modified or deleted through application-level operations
7. IF the Audit_Logger fails to persist an audit event, THEN THE Audit_Logger SHALL retain the operation's original behavior without interruption and SHALL log the audit failure to the application error log
8. THE AmpAI_Server SHALL retain audit log entries for a minimum of 90 days before they become eligible for retention policy cleanup

### Requirement 16: Testing

**User Story:** As a developer, I want automated tests covering all major subsystems, so that regressions are caught before deployment.

#### Acceptance Criteria

1. THE test suite SHALL include at least one nominal-path test and at least one error-path test for each of the following subsystems: Docker environment validation, memory system operations, chat history CRUD, task CRUD, web search integration, browser automation security constraints, terminal command blocking, Telegram message handling, backup and restore, local_only_mode enforcement, and desktop chat payload structure
2. WHEN the test suite is executed, THE test runner SHALL report pass/fail status for each subsystem such that a failure in one subsystem's tests does not prevent execution or reporting of other subsystem tests
3. THE test suite SHALL isolate each subsystem from external services by using mocks or stubs for database, Redis, network, and third-party API dependencies, so that tests execute without requiring running infrastructure
4. WHEN the test suite completes execution, THE test runner SHALL exit with a non-zero exit code if any test has failed

### Requirement 17: Documentation

**User Story:** As a developer or user, I want comprehensive documentation covering setup, architecture, and security policies, so that I can deploy and use AmpAI safely.

#### Acceptance Criteria

1. THE documentation SHALL include the following files in the repository root or a dedicated docs directory: README.md with quickstart instructions, .env.example with all variables documented, docs/MEMORY_ARCHITECTURE.md, docs/BROWSER_AUTOMATION.md, docs/TERMINAL_TOOLS.md, docs/TELEGRAM_BOT.md, docs/BACKUP_AND_RESTORE.md, docs/MODEL_PROVIDERS.md, and docs/SECURITY_POLICY.md
2. THE README.md SHALL document the `docker compose up -d --build` command as the primary setup method, including system prerequisites, required port availability, and a verification step that confirms the deployment is running
3. THE .env.example file SHALL list every environment variable read by the system, and for each variable SHALL include: the variable name, a description of its purpose, an example or default value, and whether it is required or optional
4. WHEN a security policy document is provided, THE documentation SHALL specify for each tool category: which operations are permitted by default, which operations are denied by default, and under what conditions a denied operation may be overridden
