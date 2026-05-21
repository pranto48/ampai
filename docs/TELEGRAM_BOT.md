# Telegram Bot Integration

## Overview

AmpAI integrates with Telegram to provide the same chat, memory, and task features available in the desktop app through a Telegram bot. Users can interact with their personal agent from any device with Telegram installed.

## Bot Setup

### Prerequisites

1. Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
2. Copy the bot token provided by BotFather
3. Set the token in your AmpAI configuration

### Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes (for Telegram) | Bot API token from @BotFather |

### Connecting the Bot

1. Set `TELEGRAM_BOT_TOKEN` in your `.env` file
2. Restart the AmpAI server
3. Use the admin API to save and test the bot configuration:

```
POST /api/admin/integrations/telegram/save
POST /api/admin/integrations/telegram/test
```

4. Enable either webhook or polling mode (see below)

## Message Delivery Modes

AmpAI supports two modes for receiving Telegram messages. Only one can be active at a time.

### Webhook Mode

The server receives messages via HTTP POST from Telegram's servers.

- Requires a publicly accessible HTTPS URL
- Lower latency, more efficient for production
- Telegram pushes updates to your server

```
POST /api/telegram/webhook    # Telegram sends updates here
```

### Long-Polling Mode

The server actively polls Telegram for new messages.

- Works behind firewalls and NAT without public URL
- Simpler setup for development and local deployments
- Enabling polling automatically deregisters any active webhook

```
POST /api/admin/telegram/enable-polling     # Start polling
POST /api/admin/telegram/disable-polling    # Stop polling
```

**Important**: Enabling polling deregisters any active webhook. Only one mode can be active at a time.

## User Mapping

Telegram users are mapped to AmpAI accounts via the `telegram_users` table:

| Column | Description |
|--------|-------------|
| `telegram_user_id` | Telegram's numeric user ID |
| `username` | Mapped AmpAI username |
| `display_name` | Telegram display name |

Messages from unmapped Telegram user IDs are silently discarded with an audit event logged.

## Session Management

Telegram conversations use the same `Chat_History_Store` and `Memory_System` as other interfaces. Session IDs are prefixed with `tg_` to distinguish them from desktop/web sessions.

## Supported Commands

All standard chat commands work through Telegram:

| Command | Description |
|---------|-------------|
| Regular messages | Chat with the AI agent |
| `remember ...` | Save a fact to memory |
| `search memory: ...` | Search long-term memory |
| `show pending memories` | View memory inbox |
| `approve memory {id}` | Approve a memory candidate |
| `reject memory {id}` | Reject a memory candidate |
| Task-related messages | Trigger task suggestions |

## Rate Limiting

To prevent abuse, the bot enforces rate limiting per user:

- **Limit**: 8 messages per 20-second window per user
- **Behavior**: Messages beyond the limit are silently discarded
- **Reset**: The window resets after 20 seconds of the first message in the window

## Tool Access Restrictions

By default, Telegram users **cannot** access:
- Browser automation commands
- Terminal execution commands

These tools must be explicitly enabled for Telegram access by an administrator via the admin configuration endpoint. This prevents remote execution of sensitive operations through a messaging platform.

## Error Handling

If message processing fails for any reason:
- A generic failure notification is sent to the user's Telegram chat
- An audit event is logged with the session ID and error details
- The bot continues processing subsequent messages normally

## Admin Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/integrations/telegram/status` | Bot connection status |
| POST | `/api/admin/integrations/telegram/save` | Save bot configuration |
| POST | `/api/admin/integrations/telegram/test` | Test bot token validity |
| POST | `/api/admin/telegram/enable-polling` | Start long-polling mode |
| POST | `/api/admin/telegram/disable-polling` | Stop long-polling mode |

## Security Considerations

- Only mapped Telegram user IDs can interact with the bot
- Unknown users are silently ignored (no error response to prevent enumeration)
- Browser and terminal tools are disabled by default for Telegram
- All messages and commands are logged to the audit system
- Rate limiting prevents message flooding
