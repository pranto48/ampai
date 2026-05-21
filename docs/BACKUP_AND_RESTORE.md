# Backup and Restore

## Overview

AmpAI provides automated and manual backup capabilities for all database content including chat history, memories, users, configurations, personas, and tasks. Backups support local filesystem and FTP destinations with configurable retention policies.

## Backup Profiles

A backup profile defines where and how backups are stored.

### Profile Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Profile display name |
| `destination_type` | string | `local` or `ftp` |
| `destination_host` | string | FTP hostname (FTP only) |
| `destination_port` | int | FTP port (default: 21) |
| `destination_path` | string | Directory path for backup files |
| `destination_username` | string | FTP username (FTP only) |
| `credential_key_ref` | string | Reference to encrypted FTP password |
| `retention_count` | int | Number of backups to retain (default: 7) |
| `enabled` | bool | Whether this profile is active |

### Managing Profiles

```
GET   /api/admin/backup/profiles         # List all profiles
POST  /api/admin/backup/profiles         # Create a profile
PATCH /api/admin/backup/profiles/{id}    # Update a profile
```

## Scheduling

Backups run daily on an automated schedule. Manual backups can be triggered at any time:

```
POST /api/admin/backup/run
```

### Retention Policy

When `retention_count` is set on a profile, older backups beyond the count are automatically deleted after a successful backup (local destinations only).

## Backup Contents

Each backup includes:

| Data | Description |
|------|-------------|
| Chat sessions | All session metadata and messages |
| Core memories | Approved long-term facts |
| Memory candidates | Pending/rejected memory candidates |
| Users | Account information (username, role, password hash) |
| App configs | Application configuration key-value pairs |
| Personas | Custom AI persona presets |
| Tasks | User tasks with status and metadata |

## Backup Manifest

Every backup generates a manifest with:

```json
{
  "schema_version": "2.0",
  "timestamp": "2024-01-15T10:30:00Z",
  "session_count": 42,
  "message_count": 1523,
  "checksum_sha256": "a1b2c3...",
  "created_by": "admin",
  "job_id": "uuid-here"
}
```

The SHA-256 checksum covers the entire backup payload for integrity verification.

## Restore Procedure

### 1. Preflight Validation

Before any data is modified, the system performs preflight checks:

| Check | Description |
|-------|-------------|
| Archive exists | File is present and readable |
| Archive readable | Valid ZIP with JSON manifest |
| Schema version | Compatible with current schema |
| Checksum integrity | SHA-256 matches stored value |
| Database connectivity | Database is reachable |
| Disk space | Sufficient space for extraction |

### 2. Preflight Failure

If any preflight check fails, the restore is **rejected** with no data modification. The response includes each failed check with expected vs. actual values:

```json
{
  "ok": false,
  "errors": [
    "schema_version: expected=compatible with 2.0, actual=1.0",
    "checksum_integrity: expected=abc123, actual=def456"
  ]
}
```

### 3. Restore Execution

On successful preflight, data is restored using upsert semantics:
- Existing records are updated (e.g., user roles, config values)
- New records are inserted
- Conflicts are handled gracefully with `ON CONFLICT` clauses

### 4. Restore Options

The restore endpoint accepts options to selectively restore data:

| Option | Default | Description |
|--------|---------|-------------|
| `restore_chats` | true | Restore chat sessions and messages |
| `restore_core_memories` | true | Restore core memories |
| `restore_memories` | true | Restore memory candidates |
| `restore_users` | true | Restore user accounts |
| `restore_configs` | true | Restore app configurations |
| `restore_personas` | true | Restore persona presets |
| `restore_tasks` | true | Restore tasks |

## FTP Configuration

### Testing Connection

Before configuring an FTP backup profile, test the connection:

```
POST /api/admin/backup/test-ftp
{
  "host": "ftp.example.com",
  "user": "backup-user",
  "password": "secret",
  "remote_path": "/backups/ampai",
  "port": 21
}
```

### FTP Backup Flow

1. Backup data is collected from the database
2. A ZIP archive is built in memory (manifest + gzipped payload)
3. The archive is uploaded via FTP to the configured path
4. Connection timeout: 30 seconds

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/admin/backup/run` | admin | Trigger manual backup |
| GET | `/api/admin/backup/jobs` | admin | List backup history |
| POST | `/api/admin/backup/test-ftp` | admin | Test FTP connection |
| GET | `/api/admin/backup/profiles` | admin | List backup profiles |
| POST | `/api/admin/backup/profiles` | admin | Create backup profile |
| PATCH | `/api/admin/backup/profiles/{id}` | admin | Update backup profile |

## Audit Logging

All backup and restore operations are logged with:
- Actor username
- Operation type (backup or restore)
- Final status (success or failed)
- Job identifier
- Item counts (sessions, messages, memories, etc.)
- Error details on failure

## Failure Handling

If a backup fails due to destination unreachability or write error:
- The failure is recorded in the backup jobs history with error details
- An audit event is logged
- The system continues normal operation
- Subsequent scheduled backups will retry
