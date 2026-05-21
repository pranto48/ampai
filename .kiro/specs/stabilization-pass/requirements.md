# Requirements Document

## Introduction

This specification defines a stabilization, verification, and security-fix pass on the existing AmpAI implementation. The goal is to make the current codebase production-safe for Docker and desktop deployment without adding new features. It addresses router registration inconsistencies, migration runner gaps, memory user isolation, inbox storage migration, web search rate limiting, terminal confirmation hardening, browser automation verification, audit consistency, and Docker/desktop verification.

## Glossary

- **Router_Registry**: The FastAPI application's collection of registered route handlers, managed via `app.include_router()` calls
- **Migration_Runner**: The `MigrationRunner` class in `migration_runner.py` responsible for executing additive-only database schema migrations at startup
- **Memory_Service**: The `MemoryService` class providing unified memory operations (save, search, approve, reject, delete)
- **Memory_Inbox**: The `/api/memory/inbox` endpoint and its backing storage for pending memory candidates
- **Memory_Candidates_Table**: The `memory_candidates` database table that stores pending, approved, and rejected memory candidates
- **Rate_Limiter**: The component enforcing per-user request frequency limits on the web search endpoint
- **Terminal_Service**: The `TerminalService` class that executes shell commands with security enforcement
- **Confirmation_Token**: A time-limited approval record linking a specific user, session, command, and timestamp
- **Browser_Automation_Service**: The `BrowserAutomationService` class performing Playwright-based browser actions with security enforcement
- **Audit_Logger**: The `AuditLogger` class that writes append-only records to the `audit_events` table
- **Route_Inventory**: A startup-time enumeration of all registered HTTP method + path combinations
- **Domain_Allowlist**: The configured list of permitted domains for browser navigation; empty list blocks all navigation
- **Dangerous_Command**: A shell command matching patterns in the terminal denylist (e.g., `rm -rf /`, `format`, `shutdown`)

## Requirements

### Requirement 1: Router Registration Audit

**User Story:** As a developer, I want all routers registered exactly once without duplicates, so that the API surface is predictable and no endpoints conflict.

#### Acceptance Criteria

1. WHEN the application starts, THE Router_Registry SHALL include all routers defined in the ALL_ROUTERS list in `routers/__init__.py` and any routers included directly in `main.py` without creating duplicate route path + method combinations
2. WHEN the application starts, THE Router_Registry SHALL preserve the auth endpoints defined inline in `main.py` (login, register, token validation, user management) that are intentionally kept separate from `routers/auth.py`
3. WHEN the application starts, THE Router_Registry SHALL log a complete Route_Inventory at INFO level showing all registered HTTP method + path combinations, one entry per line
4. IF a duplicate route path + method combination is detected during registration, THEN THE Router_Registry SHALL skip the duplicate, log a WARNING-level message identifying the conflicting path and method, and continue registering remaining routers
5. THE Router_Registry SHALL expose the following key routes as active: GET /api/sessions, POST /api/chat, POST /api/tools/web-search, POST /api/browser/open, POST /api/terminal/run, GET /api/tasks, GET /api/models/options
6. WHEN the test suite runs, THE test framework SHALL include a test that fails if any duplicate route path + method combination exists across all registered routes
7. WHEN the test suite runs, THE test framework SHALL include a test that verifies all key routes listed in criterion 5 are registered and return a non-404, non-405 HTTP status code when called with valid authentication

### Requirement 2: Migration Runner Completeness

**User Story:** As a developer, I want the migration runner to create all required tables at startup, so that the application functions correctly in a fresh Docker environment.

#### Acceptance Criteria

1. WHEN the application starts in a fresh database, THE Migration_Runner SHALL create all required tables: users, app_configs, chat_message_store, session_metadata, core_memories, memory_candidates, memory_summary_nodes, memory_events, memory_embeddings, tasks, audit_events, browser_profiles, browser_sessions, automation_jobs, terminal_command_logs, telegram_users
2. WHEN the application starts with an existing database, THE Migration_Runner SHALL preserve all existing row data and SHALL only apply additive schema changes (new tables or new columns)
3. WHEN the Migration_Runner executes, THE Migration_Runner SHALL use CREATE TABLE IF NOT EXISTS and ADD COLUMN IF NOT EXISTS patterns exclusively
4. WHEN the test suite runs in Docker, THE test framework SHALL include a test that verifies all 16 required tables exist after startup
5. IF a migration step fails, THEN THE Migration_Runner SHALL roll back changes from the failed step, log the error, and leave all previously applied migrations and existing data unmodified
6. IF the database is unreachable at startup, THEN THE Migration_Runner SHALL retry the connection up to 3 times with a 2-second delay between attempts before raising a connection error
7. WHEN the Migration_Runner executes, THE Migration_Runner SHALL track applied migration versions in a dedicated table and skip already-applied migrations on subsequent startups

### Requirement 3: Memory User Isolation

**User Story:** As a user, I want my memories to be private and inaccessible to other users, so that my personal data is protected.

#### Acceptance Criteria

1. WHEN a memory is saved, THE Memory_Service SHALL store the authenticated username in both the database record and the vector index metadata
2. WHEN a memory is indexed or re-indexed, THE Memory_Service SHALL include username, session_id, category, memory_id, and status in the vector metadata entry
3. WHEN a memory search is performed, THE Memory_Service SHALL filter results by the authenticated username in both vector and lexical search paths, returning an empty result set if no memories match
4. WHEN a memory is approved, rejected, or deleted, THE Memory_Service SHALL verify the authenticated username matches the memory owner before proceeding; IF the authenticated username does not match the memory owner, THEN THE Memory_Service SHALL reject the request with an HTTP 403 response and not modify the memory
5. WHEN an admin accesses another user's memories, THE Memory_Service SHALL require a dedicated admin-prefixed endpoint, verify the caller has admin role, and log an audit event containing the admin username and the target username
6. WHEN the test suite runs, THE test framework SHALL include a test verifying that user_a's saved memory is not returned in user_b's search results
7. WHEN the test suite runs, THE test framework SHALL include a test verifying that admin cross-user access is only possible through the dedicated admin-prefixed endpoint
8. WHEN a memory is written, read, or deleted, THE Audit_Logger SHALL record an audit event with the acting username and the target memory identifier
9. IF a non-admin user attempts to approve, reject, or delete a memory owned by a different user, THEN THE Audit_Logger SHALL record a failed access audit event with the acting username, target memory identifier, and attempted operation

### Requirement 4: Memory Inbox Database Migration

**User Story:** As a developer, I want the memory inbox to use the database as source of truth instead of config-list storage, so that memory candidates are durable and queryable.

#### Acceptance Criteria

1. WHEN the application starts, THE Memory_Inbox SHALL use the Memory_Candidates_Table as its source of truth for all inbox operations
2. WHEN the application starts for the first time after this change, THE Memory_Inbox SHALL migrate existing config-list candidates into the Memory_Candidates_Table once without creating duplicates
3. WHEN a PATCH /api/memory/inbox/{id} request is received with status "approved", THE Memory_Inbox SHALL update the candidate status in the Memory_Candidates_Table and create a core_memories row scoped to the authenticated username
4. WHEN a PATCH /api/memory/inbox/{id} request is received with status "rejected", THE Memory_Inbox SHALL update the candidate status in the Memory_Candidates_Table without creating a core_memories row
5. WHEN a DELETE /api/memory/inbox/{id} request is received, THE Memory_Inbox SHALL delete only candidates owned by the authenticated username unless the user has admin role
6. THE Memory_Inbox SHALL maintain backward compatibility by accepting the same request and response shapes as the current config-list implementation
7. WHEN the test suite runs, THE test framework SHALL include tests for approve, reject, and delete operations against the database-backed inbox

### Requirement 5: Web Search Rate Limiting

**User Story:** As an operator, I want web search requests rate-limited per user, so that the system is protected from abuse and excessive API costs.

#### Acceptance Criteria

1. THE Rate_Limiter SHALL enforce a limit of 10 searches per minute per authenticated user on POST /api/tools/web-search
2. THE Rate_Limiter SHALL enforce a limit of 100 searches per day per authenticated user on POST /api/tools/web-search
3. WHEN a user exceeds either rate limit, THE Rate_Limiter SHALL return HTTP 429 with a descriptive error message indicating which limit was exceeded
4. WHERE Redis is available, THE Rate_Limiter SHALL store counters in Redis
5. WHERE Redis is unavailable, THE Rate_Limiter SHALL fall back to safe in-memory counter storage
6. WHEN a rate limit event occurs, THE Audit_Logger SHALL log the event with the username, endpoint, and which limit was exceeded
7. WHEN the test suite runs, THE test framework SHALL include tests verifying HTTP 429 is returned after exceeding the per-minute limit and the per-day limit

### Requirement 6: Terminal Command Confirmation Hardening

**User Story:** As a user, I want each terminal command to require its own confirmation, so that approving one command cannot authorize a different command.

#### Acceptance Criteria

1. WHILE TERMINAL_REQUIRE_CONFIRMATION is set to true, THE Terminal_Service SHALL require a fresh Confirmation_Token for every command execution
2. THE Confirmation_Token SHALL be linked to: username, session_id, command hash (SHA-256 of the full command string), working_directory, shell type, and creation timestamp
3. WHEN a Confirmation_Token is older than 60 seconds, THE Terminal_Service SHALL reject the token and require a new confirmation
4. WHEN a Confirmation_Token is presented for a command whose hash does not match the token's command hash, THE Terminal_Service SHALL reject the execution
5. WHEN a command matches the dangerous command denylist, THE Terminal_Service SHALL block execution regardless of whether a valid Confirmation_Token exists
6. THE Terminal_Service SHALL not maintain a confirmed_sessions set that allows future commands without fresh approval
7. WHEN the test suite runs, THE test framework SHALL include a test verifying that confirming command_a does not authorize command_b
8. WHEN the test suite runs, THE test framework SHALL include a test verifying that dangerous commands remain blocked even with a valid Confirmation_Token

### Requirement 7: Browser Automation Verification

**User Story:** As an operator, I want browser automation locked down by default with strict security controls, so that the system cannot be used for unauthorized access.

#### Acceptance Criteria

1. THE Browser_Automation_Service SHALL be disabled by default (BROWSER_AUTOMATION_ENABLED defaults to false)
2. WHILE the Domain_Allowlist is empty, THE Browser_Automation_Service SHALL block all navigation attempts
3. THE Browser_Automation_Service SHALL refuse operations that access saved password stores, credential files, OS credential stores, MFA/captcha bypass, or paywall bypass
4. WHEN a login, form submit, POST, DELETE, or upload action is requested, THE Browser_Automation_Service SHALL require a Confirmation_Token before proceeding
5. WHEN a browser action Confirmation_Token is older than 60 seconds, THE Browser_Automation_Service SHALL reject the token and require a new confirmation
6. THE browser action Confirmation_Token SHALL be linked to the exact action type, target URL, and element selector
7. WHERE headless mode is requested, THE Browser_Automation_Service SHALL require admin role
8. WHEN the test suite runs, THE test framework SHALL include tests verifying: disabled-by-default returns 403, empty allowlist blocks navigation, forbidden operations are refused, confirmation is required for destructive actions, headless mode requires admin

### Requirement 8: Audit Consistency for Web/Browser/Terminal

**User Story:** As an operator, I want every security-sensitive action to produce an audit record, so that I have a complete trail for incident investigation.

#### Acceptance Criteria

1. WHEN a browser action is attempted, THE Audit_Logger SHALL record an audit event with action type, target URL, outcome, and username
2. WHEN a terminal command is attempted (including blocked commands), THE Audit_Logger SHALL record an audit event with command, working directory, outcome, and username
3. WHEN a web search is performed, THE Audit_Logger SHALL record an audit event with query, provider, result count, latency, and username
4. IF the Audit_Logger fails to write an audit event, THEN THE system SHALL continue the user's original action without crashing and log the audit failure to the application error log
5. WHEN the test suite runs, THE test framework SHALL include a test verifying that a browser action produces an audit event
6. WHEN the test suite runs, THE test framework SHALL include a test verifying that a blocked terminal command produces an audit event
7. WHEN the test suite runs, THE test framework SHALL include a test verifying that audit failure does not crash the user action

### Requirement 9: Docker Verification

**User Story:** As a developer, I want the application to start cleanly in Docker with all services healthy, so that deployment is reliable.

#### Acceptance Criteria

1. WHEN `docker compose config` is run, THE Docker configuration SHALL validate without errors
2. WHEN `docker compose up -d --build` is run, THE application container SHALL reach healthy status
3. WHEN the application starts in Docker, THE application SHALL log the complete Route_Inventory
4. WHEN `docker compose exec ampai pytest -q` is run, THE test suite SHALL pass without failures
5. IF any Docker startup failure occurs, THEN the failure SHALL be fixed as part of this stabilization pass

### Requirement 10: Desktop Verification

**User Story:** As a developer, I want the desktop client to correctly communicate with the backend, so that all tabs function properly.

#### Acceptance Criteria

1. THE desktop client SHALL send chat payloads containing all required fields: session_id, message, model_type, model_name, memory_mode, memory_top_k, memory_recency_bias, memory_category_filter, use_web_search, attachments
2. THE desktop client tabs SHALL call real backend routes that are registered and reachable (sessions, chat, tasks, browser, terminal, memory)
3. WHEN the test suite runs, THE test framework SHALL include a test verifying the desktop chat payload structure matches the backend ChatRequest schema

### Requirement 11: Final Stabilization Report

**User Story:** As a developer, I want a summary report of all changes made during stabilization, so that I can review the state of the system.

#### Acceptance Criteria

1. WHEN the stabilization pass is complete, THE report SHALL list all changed files
2. WHEN the stabilization pass is complete, THE report SHALL include the registered route list
3. WHEN the stabilization pass is complete, THE report SHALL include the duplicate route check result
4. WHEN the stabilization pass is complete, THE report SHALL include the Docker startup result
5. WHEN the stabilization pass is complete, THE report SHALL include the test result summary with pass/fail counts
6. WHEN the stabilization pass is complete, THE report SHALL list any skipped tests with reasons
7. WHEN the stabilization pass is complete, THE report SHALL list known remaining issues
8. WHEN the stabilization pass is complete, THE report SHALL include the security status for each hardened subsystem (browser, terminal, memory, audit)
