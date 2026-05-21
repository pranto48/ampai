# Security Policy

## Overview

AmpAI enforces a layered security model across all tool categories. The default posture is deny-by-default for sensitive operations, with explicit admin enablement required before any potentially dangerous tool can execute.

## Per-Tool Security Matrix

### Browser Automation

| Operation | Default | Override Condition |
|-----------|---------|-------------------|
| Navigate to allowed domain | Denied | Admin enables browser + domain in allowlist |
| Navigate to unlisted domain | Denied | Admin adds domain to allowlist |
| Click, type, submit | Denied | Admin enables browser + user confirms action |
| Extract page content | Denied | Admin enables browser + user confirms |
| Screenshot | Denied | Admin enables browser + user confirms |
| Read saved passwords | **Always denied** | Cannot be overridden |
| Bypass MFA/captcha | **Always denied** | Cannot be overridden |
| Bypass paywalls | **Always denied** | Cannot be overridden |
| Login with user credentials | Denied | Admin enables browser + user provides credentials |

**Override conditions for browser automation:**
1. `BROWSER_AUTOMATION_ENABLED=true` must be set
2. Target domain must be in the allowlist
3. User must approve the action within 60 seconds

### Terminal Execution

| Operation | Default | Override Condition |
|-----------|---------|-------------------|
| Execute command in allowed folder | Denied | Admin enables terminal + session confirmed |
| Execute command outside allowed folder | Denied | Admin adds folder to allowed list |
| Execute allowlisted command | Denied | Admin enables terminal + session confirmed |
| Execute denylisted command | **Always denied** | Cannot be overridden (denylist > allowlist) |
| Dangerous patterns (rm -rf /, format, etc.) | **Always denied** | Cannot be overridden |
| Credential dumping commands | **Always denied** | Cannot be overridden |
| Keylogging/stealth commands | **Always denied** | Cannot be overridden |

**Override conditions for terminal tools:**
1. `TERMINAL_TOOLS_ENABLED=true` must be set
2. Per-session confirmation must be granted
3. Command must not match denylist or dangerous patterns
4. Working directory must be within allowed folders
5. If allowlist is non-empty, command must match an entry

**Denylist precedence**: If a command matches both the allowlist and denylist, the denylist wins and the command is blocked.

### Memory System

| Operation | Default | Override Condition |
|-----------|---------|-------------------|
| Read memories | Permitted | User authenticated |
| Write explicit memory | Permitted | User authenticated |
| Auto-capture candidates | Permitted | Importance score >= 0.15 |
| Approve/reject candidates | Permitted | User authenticated |
| Delete memory | Permitted | User authenticated + owns memory |
| Search memory | Permitted | User authenticated |

### Telegram Bot

| Operation | Default | Override Condition |
|-----------|---------|-------------------|
| Chat messages | Permitted | User ID mapped in telegram_users |
| Memory commands | Permitted | User ID mapped in telegram_users |
| Task commands | Permitted | User ID mapped in telegram_users |
| Browser commands | Denied | Admin explicitly enables Telegram tool access |
| Terminal commands | Denied | Admin explicitly enables Telegram tool access |
| Messages from unknown users | **Always denied** | Must be added to telegram_users table |

### Backup and Restore

| Operation | Default | Override Condition |
|-----------|---------|-------------------|
| Trigger manual backup | Denied | Admin role required |
| View backup history | Denied | Admin role required |
| Restore from backup | Denied | Admin role + preflight validation passes |
| Manage backup profiles | Denied | Admin role required |

## Configuration Validation

### Production Mode Enforcement

When `AMPAI_ENV=production` or `AMPAI_ENV=prod`:

| Check | Unsafe Values | Consequence |
|-------|---------------|-------------|
| `JWT_SECRET` | "change-me", "change-me-for-production", "change-this-long-random-secret" | Server refuses to start |
| `AMPAI_DEFAULT_ADMIN_PASSWORD` | "P@ssw0rd", "change-this", "admin123" | Server refuses to start |
| `POSTGRES_PASSWORD` | "change-this", "ampai" | Server refuses to start |

In non-production mode, these generate warnings but allow startup.

## Audit Trail

All security-sensitive operations produce audit records:

| Category | Events Logged |
|----------|---------------|
| Authentication | login_attempt, login_success, login_failure |
| Memory | memory_write, memory_read, memory_delete |
| Browser | browser_action, browser_navigate |
| Terminal | terminal_execute, terminal_blocked |
| Telegram | telegram_message, telegram_command |
| Backup | backup_run, backup_restore |
| Configuration | config_change |
| Web Search | web_search |

### Audit Properties

- **Append-only**: Records cannot be modified or deleted through the application
- **Retention**: Minimum 90-day retention before cleanup eligibility
- **Resilience**: If audit logging fails, the original operation continues (logged to error log)
- **Detail limit**: Event details capped at 2000 characters

## Credential Storage

- Browser credentials are stored only after explicit user approval
- Stored credentials are encrypted using `CONFIG_ENCRYPTION_KEY`
- If no encryption key is configured, credential storage is unavailable

## Network Security

- CORS origins are explicitly configured via `ALLOWED_ORIGINS`
- JWT tokens are used for API authentication
- All admin endpoints require the `admin` role
- Telegram webhook endpoint is unauthenticated (validated by Telegram's infrastructure)

## Principle Summary

1. **Deny by default** — Browser and terminal tools are off until explicitly enabled
2. **Denylist wins** — Blocked operations cannot be overridden by allowlists
3. **Confirmation required** — Sensitive actions require explicit user approval
4. **Audit everything** — All security-relevant operations are logged
5. **Fail safe** — On error, operations are denied rather than permitted
6. **Least privilege** — Telegram users get chat/memory only, not system tools
