# Local AI Model Strategy for AmpAI

## Current AmpAI capabilities you already have

AmpAI already supports local-first inference and memory building blocks:

- Local LLM provider integration via Ollama (`get_llm(... model_type='ollama' ...)`).
- Chat history persistence in Redis (`RedisChatMessageHistory`) and SQL history via `SQLChatMessageHistory`.
- Long-term memory persistence and policy gating (`memory_persistence_manager`, explicit save detection, category inference).
- Cross-session retrieval with SQLite FTS5 (`session_recall.py` search + summarize flow).
- Model selection in request payload (`ChatRequest.model_type`, `model_name`) and `/api/chat` workflow.

This means you **do not need to train a model from scratch** to get a memory-enabled "learning" local assistant.

## Recommended architecture (practical)

Use a 3-layer approach:

1. **Base open-source model (local inference)**
   - Run a quantized instruct model in Ollama.
   - Good starting options:
     - `qwen2.5:7b-instruct`
     - `llama3.1:8b-instruct`
     - `mistral:7b-instruct`

2. **Retrieval + memory (already in AmpAI)**
   - Keep short-term chat window in Redis.
   - Keep approved long-term facts in your memory tables.
   - Use recall search to pull prior sessions and inject compact evidence into prompts.

3. **Optional lightweight adaptation (not full training)**
   - If you need style/domain adaptation, do LoRA fine-tuning offline and export to GGUF for local runtime.
   - Start without fine-tuning first; retrieval quality usually gives the biggest gain.

## What "learning from chat history" should mean in production

Avoid online weight-updates inside the running web app. Instead:

- Learn by **memory extraction + retrieval** during runtime.
- Optionally run **batch fine-tuning** weekly/monthly from curated conversation datasets.

This keeps the app stable, avoids catastrophic forgetting, and remains privacy-safe.

## Concrete AmpAI implementation plan

### Step 1: strengthen model configurability

- Expand default Ollama model list in config UI and env examples.
- Allow per-persona default model selection.

### Step 2: improve memory retrieval quality

- Add semantic embeddings in addition to FTS5 lexical recall.
- Hybrid ranking: semantic score + recency + memory category match.
- Keep current approval workflow for memory safety.

### Step 3: add memory summarization loop

- Nightly job:
  - summarize long sessions,
  - deduplicate facts,
  - keep canonical memory cards (profile, preferences, projects, constraints).

### Step 4: add a local fine-tuning pipeline (optional)

- Export accepted chat pairs from DB.
- Filter/redact sensitive data.
- Train LoRA with a small recipe (QLoRA), then evaluate.
- Only promote new adapter after regression checks.

## Open-source models to consider

### Fast + balanced (most users)
- **Qwen 2.5 7B Instruct**: strong reasoning/coding for size.
- **Llama 3.1 8B Instruct**: robust general assistant behavior.

### Low-resource devices
- **Phi-3 mini / small instruct variants** (if available in your runtime).

### Higher quality (more VRAM/RAM)
- **Qwen 2.5 14B** or **Llama 3.1 70B** (server-class hardware).

## Hardware guidance

- 7B/8B quantized: comfortable on modern CPU; better with 8GB+ VRAM GPU.
- 14B quantized: usually 16GB+ VRAM recommended.
- 70B quantized: generally multi-GPU or very high RAM setups.

## Safety and privacy

- Keep `local_only_mode=true` for strict local operation.
- Never auto-save all chat text to long-term memory.
- Store only curated/approved facts + session summaries.
- Add retention controls and delete workflows (already aligned with existing retention utilities).

## Suggested near-term backlog for this repo

1. Add `memory_embedding_enabled` and embedding model config keys.
2. Implement embedding index table + retrieval API path.
3. Add nightly `memory_compactor` scheduler job.
4. Add `/api/admin/fine-tune/export` endpoint for curated datasets.
5. Add evaluation harness: latency, factuality-with-memory, and recall-hit rate.

