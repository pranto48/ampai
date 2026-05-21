# Memory Architecture

## Overview

AmpAI's memory system provides long-term, cross-session memory that makes conversations feel continuous and personalized. It combines vector similarity search (pgvector), full-text search, and LLM-driven curation into a unified retrieval pipeline.

## Components

| Component | Role |
|-----------|------|
| `MemoryService` | Unified facade over all memory subsystems |
| `MemoryIndexer` | PGVector hybrid search (vector + FTS) |
| `MemoryCurator` | LLM-driven importance scoring and candidate evaluation |
| `MemoryPersistence` | Archiving, importance scoring, lifecycle management |

## Data Flow

```
User Message
    │
    ▼
┌─────────────────────┐
│  save_chat_turn()   │  Evaluate importance score
└─────────┬───────────┘
          │ score >= 0.15
          ▼
┌─────────────────────┐
│  memory_candidates  │  Status: pending
│  (PostgreSQL)       │
└─────────┬───────────┘
          │ User approves
          ▼
┌─────────────────────┐     ┌─────────────────────┐
│   core_memories     │────▶│  memory_embeddings  │
│   (PostgreSQL)      │     │  (pgvector 768-dim) │
└─────────────────────┘     └─────────────────────┘
```

## Retrieval Pipeline

When a user queries memory (`search memory: ...`), the system executes:

1. **Hybrid Search** — Combines vector similarity (cosine distance on 768-dim embeddings) with full-text search (ILIKE pattern matching) for maximum recall.
2. **Recency Bias** — Optional weighting toward more recent memories (configurable 0.0–1.0).
3. **Category Filtering** — Optionally restrict results to a specific memory category.
4. **Budget Compression** — Truncate and compress results to fit within `memory_context_char_budget` (default 1200 chars) before injecting into LLM context.

### Search Modes

| Mode | Behavior |
|------|----------|
| `hybrid` | Vector + FTS combined (default) |
| `vector_only` | Only pgvector similarity search |
| `fts_only` | Only full-text pattern matching |
| `fts_fallback` | Automatic fallback when vector search fails |

## Configuration

| Setting | Type | Range | Default | Description |
|---------|------|-------|---------|-------------|
| `memory_mode` | string | full, indexed, context_only, none | indexed | How memory is used in chat |
| `memory_top_k` | int | 1–8 | 5 | Max memories returned per query |
| `memory_context_char_budget` | int | 200–4000 | 1200 | Max chars injected into LLM context |
| `memory_recency_bias` | float | 0.0–1.0 | 0.0 | Weight toward recent memories |
| `memory_category_filter` | string | — | "" | Filter by category (empty = all) |

## Memory Lifecycle

### Automatic Capture

Every chat turn is evaluated for importance. Messages scoring above 0.15 become pending candidates.

### Explicit Save

Commands like `remember ...`, `save to memory ...`, or `memorize ...` save directly to core memories (max 1000 characters).

### Approval Workflow

Pending candidates appear in the memory inbox. Users can:
- **Approve** — Promotes to core memory + vector index
- **Reject** — Marks as rejected, excluded from retrieval
- **Edit** — Modify text before approval

### Deletion

`forget memory {id}` removes from both core_memories table and vector index.

## Retrieval Metadata

Every search returns metadata for observability:

```json
{
  "retrieved_count": 3,
  "context_chars": 847,
  "pipeline": "hybrid",
  "latency_ms": 42
}
```

## Embedding Provider

- **Primary**: Ollama with `nomic-embed-text` model (768 dimensions)
- **Fallback**: If Ollama is unreachable and no cloud embedding key is configured, vector retrieval is disabled and the system falls back to FTS-only search.

## Database Tables

| Table | Purpose |
|-------|---------|
| `core_memories` | Approved long-term facts |
| `memory_candidates` | Pending/rejected candidates |
| `memory_summary_nodes` | Session topic summaries |
| `memory_events` | Memory lifecycle audit trail |
| `memory_embeddings` | 768-dim vectors for similarity search |
