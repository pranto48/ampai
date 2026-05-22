import { S, ALL_PROVIDERS } from "./state";
import { esc } from "./tabs-a";

/**
 * AI Models & Providers tab — dedicated page for model selection and provider config.
 * Shows all providers, their API keys, and dynamically fetched model lists.
 *
 * Event delegation attributes rendered here (bound in bindAI() in main.ts):
 * - data-select-provider="{value}" — click sets S.modelType and triggers model fetch
 * - data-fetch-models="{value}" — click calls api(/api/models/fetch/{provider}) and stores result
 * - data-select-model="{id}" — click sets S.modelName
 */
export function aiTab(): string {
  const cfg = S.configs;
  const currentProvider = S.modelType || cfg.default_model_provider || "ollama";
  const currentModel = S.modelName || cfg.default_model || "";

  // Build provider cards — show model count from S.providerModels
  const providerCards = ALL_PROVIDERS.map(p => {
    const isActive = currentProvider === p.value;
    const hasKey = p.keyField ? !!(cfg[p.keyField] || "").trim() : true;
    const models = S.providerModels[p.value] || [];
    const modelCount = models.length;
    const statusBadge = p.local
      ? `<span class="badge ok" style="font-size:.65rem">Local</span>`
      : hasKey
        ? `<span class="badge ok" style="font-size:.65rem">Key Set</span>`
        : `<span class="badge bad" style="font-size:.65rem">No Key</span>`;

    return `<div class="provider-card${isActive ? " active" : ""}" data-select-provider="${esc(p.value)}">
  <div class="provider-card-header">
    <span class="provider-card-label">${esc(p.label)}</span>
    ${statusBadge}
  </div>
  <div class="provider-card-models">
    ${modelCount
      ? `<span style="font-size:.72rem;color:var(--muted)">${modelCount} model${modelCount > 1 ? "s" : ""}</span>`
      : `<button class="sm" data-fetch-models="${esc(p.value)}" style="font-size:.72rem">🔍 Fetch Models</button>`
    }
  </div>
</div>`;
  }).join("");

  // Build model list for current provider
  const providerModels: Array<{id: string; name: string; free?: boolean; context_length?: number}> =
    S.providerModels[currentProvider] || [];

  const modelListHtml = providerModels.length
    ? providerModels.map(m => {
        const isSelected = currentModel === m.id;
        const freeTag = m.free ? `<span class="badge ok" style="font-size:.6rem;margin-left:4px">FREE</span>` : "";
        const ctxTag = m.context_length ? `<span style="font-size:.68rem;color:var(--muted);margin-left:6px">${Math.round(m.context_length / 1000)}K ctx</span>` : "";
        return `<div class="model-item${isSelected ? " selected" : ""}" data-select-model="${esc(m.id)}">
  <span class="model-item-name">${esc(m.name || m.id)}</span>${freeTag}${ctxTag}
</div>`;
      }).join("")
    : `<div class="section-empty" style="padding:12px">
        <button class="primary" data-fetch-models="${esc(currentProvider)}" style="width:100%">🔍 Fetch Available Models</button>
        <div class="hint" style="margin-top:8px">Click to load models from ${esc(currentProvider)}</div>
      </div>`;

  // Current selection display
  const selectionDisplay = currentModel
    ? `<div class="ai-current-selection">
        <span class="hint">Active:</span>
        <strong>${esc(currentProvider)}</strong> / <code>${esc(currentModel)}</code>
      </div>`
    : `<div class="ai-current-selection">
        <span class="hint">No model selected. Choose a provider and model below.</span>
      </div>`;

  return `<div class="panel">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    🤖 AI Model Selection
    <button class="sm" id="btn-refresh-all-models">🔄 Refresh All</button>
  </div>
  ${selectionDisplay}
</div>

<div class="panel">
  <div class="panel-title">Providers</div>
  <div class="provider-grid">${providerCards}</div>
</div>

<div class="panel">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    Models — ${esc(ALL_PROVIDERS.find(p => p.value === currentProvider)?.label || currentProvider)}
    <button class="sm" data-fetch-models="${esc(currentProvider)}">🔍 Refresh</button>
  </div>
  <div class="model-list">${modelListHtml}</div>
</div>

<div class="panel">
  <div class="panel-title">Custom Model Name</div>
  <div class="hint" style="margin-bottom:8px">Type a model ID directly if not listed above (e.g., openai/gpt-oss-120b:free)</div>
  <form id="custom-model-form" class="row" style="gap:8px">
    <input id="custom-model-input" value="${esc(currentModel)}" placeholder="provider/model-name" style="flex:1"/>
    <button class="primary" type="submit">Set Model</button>
  </form>
</div>`;
}
