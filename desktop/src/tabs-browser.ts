import { S, type BrowserJob } from "./state";
import { esc, fmtRel } from "./tabs-a";

function jobStatusBadge(status: BrowserJob["status"]): string {
  const cls = status === "completed" ? "ok" : status === "running" ? "warn" : status === "failed" ? "bad" : "";
  return `<span class="badge ${cls}" style="font-size:.69rem">${esc(status)}</span>`;
}

export function browserTab(): string {
  const bs = S.browserState;

  const allowlistItems = bs.allowlist.length
    ? bs.allowlist.map(d => `<div class="allowlist-item"><code>${esc(d)}</code></div>`).join("")
    : `<div class="hint">No domains configured. All navigation is blocked.</div>`;

  const recentJobs = bs.jobs.slice(0, 200);
  const jobRows = recentJobs.length
    ? recentJobs.map(job => `<div class="browser-job-item">
  <div class="browser-job-info">
    <div class="browser-job-type">${esc(job.job_type)} ${jobStatusBadge(job.status)}</div>
    <div class="browser-job-meta">${fmtRel(job.created_at)}${job.request?.url ? ` · ${esc(String(job.request.url))}` : ""}</div>
  </div>
</div>`).join("")
    : `<div class="section-empty">No browser actions recorded yet.</div>`;

  return `<div class="panel">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    Browser Automation ${bs.enabled ? `<span class="badge ok">Enabled</span>` : `<span class="badge bad">Disabled</span>`}
  </div>
  <div class="hint" style="margin-bottom:10px">
    ${bs.enabled
      ? "Browser automation is active. Actions require confirmation before execution."
      : "Browser automation is disabled. An admin must enable it via BROWSER_AUTOMATION_ENABLED."}
  </div>
  <button id="btn-reload-browser" class="sm" style="margin-bottom:12px">🔄 Refresh</button>
</div>
<div class="panel">
  <div class="panel-title">Domain Allowlist</div>
  <div class="hint" style="margin-bottom:8px">Only these domains can be navigated to. Empty list blocks all navigation.</div>
  <div class="allowlist-list" style="margin-bottom:8px">${allowlistItems}</div>
  <form class="stack" id="browser-allowlist-form">
    <label class="field">Add domain<input name="domain" placeholder="example.com"/></label>
    <div class="row">
      <button class="primary" type="submit">Add Domain</button>
    </div>
  </form>
</div>
<div class="panel">
  <div class="panel-title">Action History <span style="font-size:.75rem;color:var(--muted)">(${recentJobs.length} entries)</span></div>
  <div class="browser-jobs-list" style="max-height:400px;overflow-y:auto">${jobRows}</div>
</div>`;
}
