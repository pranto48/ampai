# Terminal Tools

## Overview

AmpAI can execute shell commands on behalf of the user within strict security boundaries. The terminal service supports macOS shell, Windows PowerShell, and Windows CMD with automatic OS detection. It is disabled by default and requires explicit admin enablement with per-session confirmation.

## Setup

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TERMINAL_TOOLS_ENABLED` | `false` | Master switch for terminal tools |
| `TERMINAL_REQUIRE_CONFIRMATION` | `true` | Require per-session confirmation |

### Enabling Terminal Tools

1. Set `TERMINAL_TOOLS_ENABLED=true` in your `.env` file
2. Restart the AmpAI server
3. Configure allowed folders and command policies via the admin API

## Policy Configuration

Terminal security is enforced through a layered policy system evaluated in order:

### 1. Dangerous Patterns (Always Blocked)

These patterns are blocked regardless of any allowlist configuration:

| Pattern | Description |
|---------|-------------|
| `rm -rf /` | Recursive delete from root |
| `format` | Disk formatting |
| `del /s` on system paths | Windows recursive delete |
| `Remove-Item -Recurse` on system paths | PowerShell recursive delete |
| `shutdown` | System shutdown |
| `regedit`, `reg add/delete` | Registry modification |
| `mimikatz`, `sekurlsa`, `lsadump` | Credential dumping |
| `token.dump`, `access.token.export` | Token extraction |
| `browser.*password.*export` | Browser credential export |
| `keylog`, `key.logger` | Keylogging |
| `stealth`, `hidden.*monitor` | Stealth monitoring |

### 2. Denylist

Admin-configurable list of blocked command patterns (max 500 entries). **Denylist always takes precedence over allowlist** — if a command matches both, it is blocked.

### 3. Allowlist

Admin-configurable list of permitted command patterns (max 500 entries). If the allowlist is non-empty, commands must match at least one entry to execute.

### 4. Allowed Folders

Commands are restricted to admin-approved project folders. Any command referencing absolute paths outside these folders is rejected. Relative paths are resolved against the working directory.

### Managing Policy

```
GET   /api/terminal/policy       # View current policy (admin)
PATCH /api/terminal/policy       # Update policy (admin)
```

Example policy update:
```json
{
  "command_allowlist": ["git", "npm", "python", "pip", "node"],
  "command_denylist": ["curl", "wget", "ssh"],
  "allowed_folders": ["/home/user/projects", "/opt/app"]
}
```

## Execution Parameters

| Parameter | Range | Default | Description |
|-----------|-------|---------|-------------|
| Timeout | 1–300 seconds | 30s | Max execution time per command |
| Output limit | 100–1,000,000 chars | 10,000 | Max captured output |

### Timeout Behavior

When a command exceeds the timeout:
- The process is terminated (SIGKILL)
- Partial output captured up to that point is returned
- The result includes `timed_out: true`

### Output Truncation

When combined stdout + stderr exceeds the output limit:
- Output is truncated to fit within the limit
- The result includes `truncated: true`

## Per-Session Confirmation

When `TERMINAL_REQUIRE_CONFIRMATION=true` (default), each session must explicitly confirm terminal access before any commands can execute. This prevents accidental command execution.

## Shell Detection

The service auto-detects the appropriate shell:

| OS | Shell | Invocation |
|----|-------|------------|
| macOS/Linux | Default shell (`$SHELL` or `/bin/sh`) | `$SHELL -c "command"` |
| Windows | PowerShell (preferred) | `powershell -NoProfile -Command "command"` |
| Windows | CMD (fallback) | `cmd /c "command"` |

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/terminal/run` | user | Execute command |
| GET | `/api/terminal/logs` | user | Command execution history |
| GET | `/api/terminal/policy` | admin | View current policy |
| PATCH | `/api/terminal/policy` | admin | Update policy |

### Execute Command

```json
POST /api/terminal/run
{
  "command": "git status",
  "working_directory": "/home/user/project",
  "timeout": 15
}
```

### Response

```json
{
  "command": "git status",
  "exit_code": 0,
  "stdout": "On branch main\nnothing to commit...",
  "stderr": "",
  "execution_ms": 127,
  "truncated": false,
  "timed_out": false,
  "blocked": false
}
```

## Audit Logging

Every terminal command (executed or blocked) is logged with:
- Command text
- Working directory
- Exit code
- Execution duration (ms)
- Output (truncated to configured limit)
- Whether it was blocked and the reason

## Desktop UI

The Terminal Tools tab shows:
- Terminal policy status (enabled/disabled, allowed folders, lists)
- Command history (most recent 200 entries)
- Execution controls
