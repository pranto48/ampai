import { S } from "./state";
import { esc, fmtRel } from "./tabs-a";

export function terminalTab(): string {
  const state = S.terminalState;
  const statusBadge = state.enabled
    ? `<span class="badge ok">Enabled</span>`
    : `<span class="badge bad">Disabled</span>`;

  const policy = state.policy;

  const policyHtml = `<div class="terminal-policy-grid">
  <div class="terminal-policy-item"><strong>Require Confirmation:</strong> ${policy.require_confirmation ? "Yes" : "No"}</div>
  <div class="terminal-policy-item"><strong>Timeout:</strong> ${policy.timeout}s</div>
  <div class="terminal-policy-item"><strong>Max Output:</strong> ${policy.max_output} chars</div>
  <div class="terminal-policy-item"><strong>Allowed Folders:</strong> ${policy.allowed_folders.length ? policy.allowed_folders.map(f => esc(f)).join(", ") : "None configured"}</div>
</div>`;

  const logsHtml = state.logs.length
    ? state.logs.slice(0, 200).map((log) => {
        const statusClass = log.blocked ? "bad" : log.exit_code === 0 ? "ok" : "warn";
        const statusLabel = log.blocked ? "Blocked" : log.exit_code === 0 ? "OK" : `Exit ${log.exit_code}`;
        return `<div class="terminal-log-item">
  <div class="terminal-log-header">
    <span class="badge ${statusClass}">${esc(statusLabel)}</span>
    <code class="terminal-log-cmd">${esc(log.command.slice(0, 80))}</code>
    <span class="terminal-log-time">${fmtRel(log.created_at)}</span>
  </div>
  ${log.output_summary ? `<div class="terminal-log-output">${esc(log.output_summary.slice(0, 200))}</div>` : ""}
</div>`;
      }).join("")
    : `<div class="section-empty">No terminal commands executed yet.</div>`;

  return `<div class="panel">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    ⌨️ Terminal Tools ${statusBadge}
  </div>
  <div class="hint" style="margin-bottom:10px">Terminal tools allow AmpAI to execute shell commands within security boundaries.</div>
</div>
<div class="panel">
  <div class="panel-title">Policy</div>
  ${policyHtml}
</div>
<div class="panel">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    Command History <button id="btn-reload-terminal" class="sm">🔄 Refresh</button>
  </div>
  <div class="terminal-logs-list">${logsHtml}</div>
</div>`;
}
