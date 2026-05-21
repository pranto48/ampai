# Implementation Plan: Stabilization Pass

## Overview

This plan implements a stabilization, verification, and security-hardening pass on the AmpAI codebase. All tasks are corrective or additive — no new user-facing features. The implementation proceeds from foundational infrastructure (rate limiter, confirmation tokens) through service hardening (memory isolation, terminal, browser) to integration verification (Docker, desktop, route audit).

## Tasks

- [x] 1. Create foundational services and infrastructure
  - [x] 1.1 Create `services/rate_limiter.py` with `RateLimiter` class
    - Implement `RateLimiter` with per-user per-minute (10) and per-day (100) counters
    - Support Redis backend with in-memory fallback when Redis is unavailable
    - Return `RateLimitResult` dataclass with allowed/denied status, remaining counts, and retry_after_seconds
    - Log rate limit violations to AuditLogger
    - Return HTTP 429 with descriptive message on limit exceeded
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 1.2 Create `services/confirmation_token.py` with `ConfirmationTokenService`
    - Implement HMAC-SHA256 signed token generation bound to username, session_id, command_hash, working_directory, shell_type
    - Include browser-specific fields: action_type, target_url, element_selector
    - Implement validation: signature check, 60-second TTL expiry, command hash match, binding field verification
    - Return structured `ValidationResult` with specific rejection reasons
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.4, 7.5, 7.6_

  - [x] 1.3 Implement `register_all_with_dedup` in `routers/__init__.py`
    - Replace `register_all` with `register_all_with_dedup` that detects duplicate (method, path) combinations
    - Skip duplicates and log WARNING-level messages identifying conflicting path and method
    - Return `RouteInventory` dataclass with registered routes and skipped duplicates count
    - _Requirements: 1.1, 1.4_

  - [x] 1.4 Add startup route inventory logging in `main.py`
    - Call `register_all_with_dedup` during app startup
    - Log complete route inventory at INFO level (one entry per line: METHOD /path)
    - Ensure all key routes are active: GET /api/sessions, POST /api/chat, POST /api/tools/web-search, POST /api/browser/open, POST /api/terminal/run, GET /api/tasks, GET /api/models/options
    - _Requirements: 1.3, 1.5_

- [ ] 2. Checkpoint - Ensure foundational services are correct
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Harden memory user isolation and inbox migration
  - [ ] 3.1 Enforce user isolation in `services/memory_service.py`
    - Add username filtering to `search_memory` for both vector and FTS paths
    - Add ownership verification to `approve_candidate` and `reject_candidate` (return None / raise if mismatch)
    - Ensure `save_explicit_memory` and `capture_candidate` always store authenticated username
    - Ensure vector index metadata includes username, session_id, category, memory_id, status
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ] 3.2 Migrate memory inbox to database backend in `routers/memory.py`
    - Replace `_load_config_list("memory_inbox_candidates")` calls with queries to `memory_candidates` table
    - Implement one-time startup migration from config-list to database (idempotent, check-before-insert)
    - Update `list_memory_inbox` to query database with username filtering
    - Update `update_memory_inbox` (PATCH) to update database, create `core_memories` row on approve scoped to username
    - Update `delete_memory_inbox` to delete from database with ownership check
    - Maintain backward-compatible request/response shapes
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ] 3.3 Add admin-only cross-user memory access endpoints
    - Add `/api/admin/memory/inbox` endpoint requiring admin role
    - Add `/api/admin/memory/search` endpoint requiring admin role
    - Log audit events for all admin cross-user memory access with admin username and target username
    - _Requirements: 3.5, 3.7_

  - [ ] 3.4 Add audit logging for all memory operations
    - Ensure every memory write, read, and delete produces an audit event with acting username and target memory ID
    - Log failed access attempts (non-admin trying to access another user's memory) with username, target ID, and operation
    - _Requirements: 3.8, 3.9_

  - [ ]* 3.5 Write property test for memory user isolation (Property 4)
    - **Property 4: Memory User Isolation**
    - For any two distinct users A and B, searching as user A never returns memories owned by user B
    - User A attempting to approve/reject/delete user B's memory is rejected with 403
    - **Validates: Requirements 3.3, 3.4, 4.5**

  - [ ]* 3.6 Write property test for memory metadata completeness (Property 5)
    - **Property 5: Memory Metadata Completeness**
    - For any memory save or index operation, the resulting record contains authenticated username
    - Vector metadata includes username, session_id, category, memory_id, and status
    - **Validates: Requirements 3.1, 3.2**

  - [ ]* 3.7 Write property test for inbox migration idempotence (Property 7)
    - **Property 7: Inbox Migration Idempotence**
    - Running the migration function multiple times produces the same set of rows as running it once
    - No duplicates created on repeated runs
    - **Validates: Requirements 4.2**

  - [ ]* 3.8 Write property test for inbox status transitions (Property 8)
    - **Property 8: Inbox Status Transition Correctness**
    - Approving a candidate creates exactly one core_memories row scoped to that user's username
    - Rejecting a candidate updates status without creating any core_memories row
    - **Validates: Requirements 4.3, 4.4**

- [ ] 4. Checkpoint - Ensure memory isolation and inbox migration are correct
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Harden terminal confirmation and web search rate limiting
  - [ ] 5.1 Integrate per-command confirmation tokens in `services/terminal_service.py`
    - Remove `_confirmed_sessions` set and `confirm_session`/`revoke_session`/`is_session_confirmed` methods
    - Require `ConfirmationToken` parameter in `execute()` when `TERMINAL_REQUIRE_CONFIRMATION` is true
    - Validate token hash matches SHA-256 of the exact command being executed
    - Validate token binding: username, session_id, working_directory, shell_type
    - Block dangerous commands regardless of token validity (denylist takes precedence)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ] 5.2 Integrate rate limiter into `routers/web_search.py`
    - Add `RateLimiter` as a FastAPI dependency on the POST /api/tools/web-search endpoint
    - Call `check_rate_limit(username, "web-search")` before executing search
    - Return HTTP 429 with descriptive error when limit exceeded
    - Log rate limit events to AuditLogger
    - _Requirements: 5.1, 5.2, 5.3, 5.6_

  - [ ]* 5.3 Write property test for rate limit enforcement (Property 9)
    - **Property 9: Rate Limit Enforcement**
    - The (N+1)th request within a window is rejected with 429 when N equals the configured limit
    - Each rejection produces an audit event
    - **Validates: Requirements 5.1, 5.2, 5.6**

  - [ ]* 5.4 Write property test for terminal confirmation token validation (Property 10)
    - **Property 10: Terminal Confirmation Token Validation**
    - Command only executes with valid token: correct signature, within 60s, matching command hash, correct username/session
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

  - [ ]* 5.5 Write property test for dangerous command blocking (Property 11)
    - **Property 11: Dangerous Command Blocking**
    - Commands matching denylist are blocked regardless of valid token
    - Denylist check takes precedence over token validation
    - **Validates: Requirements 6.5**

- [ ] 6. Checkpoint - Ensure terminal and rate limiter hardening are correct
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Harden browser automation and audit consistency
  - [ ] 7.1 Add confirmation token requirement to `services/browser_automation_service.py`
    - Require `ConfirmationToken` for destructive actions: login, form submit, POST, DELETE, upload
    - Validate token is within 60-second TTL
    - Validate token is bound to exact action_type, target_url, and element_selector
    - Verify disabled-by-default behavior (BROWSER_AUTOMATION_ENABLED defaults to false)
    - Verify empty allowlist blocks all navigation
    - Verify forbidden operation patterns are refused (password store, MFA bypass, captcha bypass, paywall bypass)
    - Verify headless mode requires admin role
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [ ] 7.2 Verify and fix audit consistency in `core/audit.py` and service integrations
    - Ensure every browser action attempt produces an audit event (action type, target URL, outcome, username)
    - Ensure every terminal command attempt (including blocked) produces an audit event
    - Ensure every web search produces an audit event (query, provider, result count, latency, username)
    - Verify audit failures never crash the user's operation (already implemented, add test coverage)
    - Add audit events for rate limit violations and failed access attempts
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ]* 7.3 Write property test for browser security enforcement (Property 12)
    - **Property 12: Browser Security Enforcement**
    - Empty allowlist blocks all navigation
    - Forbidden operation patterns (password store, MFA bypass, captcha bypass, paywall bypass) are refused
    - **Validates: Requirements 7.2, 7.3**

  - [ ]* 7.4 Write property test for browser confirmation token validation (Property 13)
    - **Property 13: Browser Confirmation Token Validation**
    - Destructive actions require valid token within 60s, bound to action_type, target_url, element_selector
    - **Validates: Requirements 7.4, 7.5, 7.6**

  - [ ]* 7.5 Write property test for audit completeness (Property 14)
    - **Property 14: Audit Completeness for Security Actions**
    - Every browser action, terminal command, and web search produces an audit event
    - **Validates: Requirements 8.1, 8.2, 8.3**

  - [ ]* 7.6 Write property test for audit failure resilience (Property 15)
    - **Property 15: Audit Failure Resilience**
    - When AuditLogger fails to write, the user's original action completes without exception
    - **Validates: Requirements 8.4**

- [ ] 8. Checkpoint - Ensure browser and audit hardening are correct
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Migration runner completeness and schema verification
  - [ ] 9.1 Register real migrations for all 16 tables in `migration_runner.py`
    - Register migrations for: users, app_configs, chat_message_store, session_metadata, core_memories, memory_candidates, memory_summary_nodes, memory_events, memory_embeddings, tasks, audit_events, browser_profiles, browser_sessions, automation_jobs, terminal_command_logs, telegram_users
    - Use CREATE TABLE IF NOT EXISTS patterns exclusively
    - Ensure migrations are idempotent (safe to run on existing databases)
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 9.2 Add schema verification in `database.py`
    - Add startup verification that all 16 required tables exist after migration
    - Log WARNING if any table is missing
    - _Requirements: 2.4_

  - [ ]* 9.3 Write property test for migration data preservation (Property 2)
    - **Property 2: Migration Data Preservation**
    - Running migrations preserves all existing row data unchanged
    - **Validates: Requirements 2.2**

  - [ ]* 9.4 Write property test for migration idempotence (Property 3)
    - **Property 3: Migration Idempotence**
    - Calling run_pending() twice produces the same final state as calling it once
    - Second call detects all migrations as already applied and skips them
    - **Validates: Requirements 2.7**

- [ ] 10. Route deduplication and integration tests
  - [ ] 10.1 Write unit tests for router registration deduplication
    - Test that duplicate (method, path) combinations are skipped
    - Test that skipped duplicates are logged at WARNING level
    - Test that all key routes from Requirement 1.5 are registered
    - _Requirements: 1.4, 1.6, 1.7_

  - [ ]* 10.2 Write property test for route deduplication (Property 1)
    - **Property 1: Route Deduplication**
    - For any set of router definitions with duplicates, final route set has no duplicates
    - Count of skipped duplicates equals number of duplicate entries in input
    - **Validates: Requirements 1.4**

  - [ ]* 10.3 Write unit tests for terminal hardening
    - Test that confirming command_a does not authorize command_b
    - Test that dangerous commands remain blocked even with valid ConfirmationToken
    - _Requirements: 6.7, 6.8_

  - [ ]* 10.4 Write unit tests for browser verification
    - Test disabled-by-default returns 403
    - Test empty allowlist blocks navigation
    - Test forbidden operations are refused
    - Test confirmation is required for destructive actions
    - Test headless mode requires admin
    - _Requirements: 7.8_

  - [ ]* 10.5 Write unit test for desktop payload schema conformance
    - **Property 16: Desktop Payload Schema Conformance**
    - Verify desktop chat payload contains all required ChatRequest fields
    - _Requirements: 10.1, 10.3_

- [ ] 11. Docker and integration verification
  - [ ] 11.1 Write Docker integration test
    - Verify `docker compose config` validates without errors
    - Verify application container reaches healthy status after `docker compose up`
    - Verify route inventory is logged at startup
    - Verify all 16 tables exist after startup
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [ ]* 11.2 Write integration test for route inventory verification
    - Verify all registered routes return non-404, non-405 with valid auth
    - _Requirements: 1.7_

  - [ ]* 11.3 Write integration test for memory isolation with real database
    - End-to-end test: user_a saves memory, user_b search returns empty
    - _Requirements: 3.6_

- [ ] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation language is Python (matching the existing codebase and design document)
- All new test files go in `tests/properties/`, `tests/unit/`, or `tests/integration/` directories
- The `hypothesis` library is used for property-based tests (minimum 100 iterations each)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["1.4", "3.1", "3.2"] },
    { "id": 2, "tasks": ["3.3", "3.4", "5.1", "5.2"] },
    { "id": 3, "tasks": ["3.5", "3.6", "3.7", "3.8", "5.3", "5.4", "5.5"] },
    { "id": 4, "tasks": ["7.1", "7.2", "9.1"] },
    { "id": 5, "tasks": ["7.3", "7.4", "7.5", "7.6", "9.2", "9.3", "9.4"] },
    { "id": 6, "tasks": ["10.1", "10.2", "10.3", "10.4", "10.5"] },
    { "id": 7, "tasks": ["11.1", "11.2", "11.3"] }
  ]
}
```
