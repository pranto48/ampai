# Browser Automation

## Overview

AmpAI provides Playwright-based browser automation that allows the agent to navigate websites, extract information, fill forms, and take screenshots on behalf of the user. The system is designed with security-first principles: disabled by default, domain-restricted, and confirmation-gated.

## Setup

### Prerequisites

- Playwright and Chromium browser installed (`playwright install chromium`)
- Browser automation explicitly enabled by an administrator

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BROWSER_AUTOMATION_ENABLED` | `false` | Master switch for browser tools |
| `BROWSER_HEADLESS` | `false` | Run browser without visible window |

### Enabling Browser Automation

1. Set `BROWSER_AUTOMATION_ENABLED=true` in your `.env` file
2. Restart the AmpAI server
3. Configure the domain allowlist via the admin API or desktop UI

## Domain Allowlist

Browser automation enforces a strict domain allowlist. Navigation is only permitted to domains explicitly listed.

### Rules

- **Empty allowlist blocks ALL navigation** — this is the default deny-all state
- Subdomains are permitted if the parent domain is listed (e.g., `example.com` allows `sub.example.com`)
- Matching is case-insensitive
- URLs without a valid hostname are rejected

### Managing the Allowlist

```
GET  /api/browser/allowlist       # View current allowlist (admin)
POST /api/browser/allowlist       # Update allowlist (admin)
```

Example payload:
```json
{
  "domains": ["github.com", "docs.python.org", "stackoverflow.com"]
}
```

## Security Constraints

### Disabled by Default

Browser automation returns HTTP 403 unless `BROWSER_AUTOMATION_ENABLED=true` is set. The check occurs before any tool logic executes.

### Confirmation Flow

Every browser action requires explicit user approval:

1. Action is requested → system returns `confirmation_required` status
2. User has 60 seconds to approve or deny
3. On timeout or denial → action is cancelled
4. On approval → action executes with 30-second timeout

### Forbidden Operations

The following operations are always refused:

- Reading saved/stored browser passwords
- Bypassing MFA or two-factor authentication
- Bypassing captchas
- Bypassing paywalls or access controls
- Credential export or dumping

### Login Automation

When login is required, the browser uses **only user-provided credentials** typed into the visible headed browser. The system never uses stored or generated passwords.

### Action Timeout

Each browser action has a 30-second timeout. If exceeded:
- The action is aborted
- The affected browser tab is closed
- A timeout error is returned to the user

## Available Actions

| Action | Endpoint | Description |
|--------|----------|-------------|
| Open | `POST /api/browser/open` | Launch browser instance |
| Navigate | `POST /api/browser/navigate` | Go to URL (allowlist enforced) |
| Search | `POST /api/browser/search` | Search via browser |
| Click | `POST /api/browser/click` | Click element by CSS selector |
| Type | `POST /api/browser/type` | Type text into element |
| Submit | `POST /api/browser/submit` | Submit a form |
| Extract | `POST /api/browser/extract` | Extract page text content |
| Screenshot | `POST /api/browser/screenshot` | Capture page screenshot |
| Close | `POST /api/browser/close` | Close browser instance |

## Audit Logging

Every browser action is logged to the audit system with:
- Action type (navigate, click, type, etc.)
- Target URL or element selector
- Timestamp
- Outcome (success, failed, timeout, blocked, denied)

## Usage Example

```python
# Navigate to an allowed domain
POST /api/browser/navigate
{
  "url": "https://github.com/user/repo"
}

# Extract page content
POST /api/browser/extract
{}

# Take a screenshot
POST /api/browser/screenshot
{}
```

## Desktop UI

The Browser Automation tab in the desktop app shows:
- Enable/disable status
- Domain allowlist configuration
- Scrollable action history (most recent 200 entries)
