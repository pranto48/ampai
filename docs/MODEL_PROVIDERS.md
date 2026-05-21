# Model Providers

## Overview

AmpAI supports multiple AI model providers with automatic fallback routing. The system prioritizes local inference via Ollama for privacy and offline capability, with cloud providers available as fallbacks when needed.

## Supported Providers

| Provider | Type | API Key Required | Description |
|----------|------|-----------------|-------------|
| Ollama | Local | No | Local LLM inference, primary provider |
| OpenRouter | Cloud | Yes | Multi-model routing service |
| OpenAI | Cloud | Yes | GPT models |
| Gemini | Cloud | Yes | Google AI models |
| Anthropic | Cloud | Yes | Claude models |
| Generic | Cloud | Yes | Any OpenAI-compatible API |
| AmpAI_Default | Built-in | No | Rule-based fallback engine |

## Fallback Chain

When a chat request is made, the Model Router attempts providers in this order:

```
Ollama → OpenRouter → OpenAI → Gemini → Anthropic → Generic → AmpAI_Default
```

### Routing Rules

1. **Ollama reachable** → Route to Ollama (8-second connection timeout)
2. **Ollama unreachable + `local_only_mode` enabled** → Route to AmpAI_Default
3. **Ollama unreachable + `local_only_mode` disabled** → Try cloud providers in order, skipping any without configured API keys
4. **All providers fail** → Route to AmpAI_Default built-in engine

## local_only_mode

When `local_only_mode` is enabled:
- Only Ollama and AmpAI_Default are available
- Cloud providers are excluded from the fallback chain
- The `/api/models/options` endpoint returns only local providers
- Useful for air-gapped environments or strict data privacy requirements

## Health Checks

### Endpoint

```
GET /api/models/health
```

### Response

Returns reachability status for each configured provider:

```json
{
  "providers": [
    { "name": "ollama", "ok": true, "latency_ms": 45 },
    { "name": "openai", "ok": true, "latency_ms": 230 },
    { "name": "anthropic", "ok": false, "latency_ms": null }
  ]
}
```

### Available Models

```
GET /api/models/options
```

Returns the list of available providers and their configured models, filtered by `local_only_mode` setting.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama API endpoint |

### Provider Budget

Each provider operates within configurable resource limits:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_tokens` | 8,000 | Maximum tokens per request |
| `max_cost_usd` | $1.00 | Maximum estimated cost per request |
| `timeout_seconds` | 30s | Request timeout |
| `max_retries` | 2 | Retry attempts on failure |

## Embedding Provider

For memory vector search, the system uses embeddings:

| Scenario | Provider | Model |
|----------|----------|-------|
| Ollama reachable | Ollama | `nomic-embed-text` (768-dim) |
| Ollama unreachable + cloud key configured | Cloud embedding API | Provider-specific |
| Ollama unreachable + no cloud key | Disabled | Vector retrieval unavailable |

When vector retrieval is disabled, the memory system falls back to full-text search only.

## AmpAI_Default Engine

The built-in fallback engine provides basic responses without any external AI service:

- Rule-based intent detection
- Responses generated from stored memory facts
- Always available, no network dependency
- Limited capability compared to full LLM providers

## Usage Logging

All provider interactions are logged to `agent_data/provider_usage.jsonl` with:
- Provider name and model
- Token counts (prompt + completion)
- Latency in milliseconds
- Estimated cost
- Operation type

## Testing Provider Connections

Administrators can test specific provider connections:

```
POST /api/admin/providers/test
{
  "provider": "openai",
  "model": "gpt-4"
}
```
