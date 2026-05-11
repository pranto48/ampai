import { S } from "./state";

export function esc(value: string): string {
  return (value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function md(value: string): string {
  return esc(value)
    .replace(/```([\s\S]*?)```/g, "<pre><code>$1</code></pre>")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br/>");
}

export function fmtRel(iso: string): string {
  if (!iso) {
    return "-";
  }
  const date = new Date(iso);
  const diff = Date.now() - date.getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) {
    return "just now";
  }
  if (minutes < 60) {
    return `${minutes}m ago`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }
  return `${Math.floor(hours / 24)}d ago`;
}

export function serverTab(): string {
  const health = S.health;
  return `<div class="panel">
  <div class="panel-title">Server Connection</div>
  <div class="status-row">
    <span class="badge ${health.ok ? "ok" : "bad"}">${health.ok ? "Online" : "Offline"}</span>
    <div class="status-detail"><strong>${esc(health.status)}</strong><span>${esc(health.detail)}</span></div>
  </div>
  <form class="stack" id="server-form">
    <label class="field">Server URL<input name="url" value="${esc(S.serverUrl)}" placeholder="http://127.0.0.1:8001"/></label>
    <div class="row">
      <button class="primary" type="submit">Save and Connect</button>
      <button type="button" id="btn-test-server">Test</button>
    </div>
  </form>
  <div class="divider"></div>
  <div class="panel-title">Quick Connect</div>
  <button class="quick-url" data-url="http://127.0.0.1:8001" style="width:100%;margin-bottom:5px">Local 127.0.0.1:8001</button>
  <button class="quick-url" data-url="http://192.168.20.5:8001" style="width:100%">Docker 192.168.20.5:8001</button>
  <div class="divider"></div>
  <div class="panel-title">Docker Start</div>
  <code>docker compose up --build</code>
</div>`;
}

export function accountTab(): string {
  if (S.auth) {
    return `<div class="panel">
  <div class="panel-title">Signed In</div>
  <div class="account-card">
    <div class="account-avatar">${S.auth.username[0].toUpperCase()}</div>
    <div><div class="account-name">${esc(S.auth.username)}</div><div class="account-role">${esc(S.auth.role)}</div></div>
  </div>
  <button id="btn-logout" style="width:100%;margin-top:10px">Logout</button>
</div>`;
  }
  return `<div class="panel">
  <div class="panel-title">Login</div>
  <form class="stack" id="login-form">
    <label class="field">Username<input name="username" value="admin" autocomplete="username"/></label>
    <label class="field">Password<input name="password" type="password" value="P@ssw0rd" autocomplete="current-password"/></label>
    <button class="primary" type="submit">Login</button>
  </form>
</div>`;
}

export function historyTab(): string {
  const categories = [...new Set(S.sessions.map((item) => item.category || "Uncategorized"))];
  const sessions = S.sessions.filter((item) => {
    const q = S.sessionSearch.toLowerCase();
    const matchesQuery =
      !q ||
      item.session_id.toLowerCase().includes(q) ||
      (item.category || "").toLowerCase().includes(q);
    const matchesCategory =
      !S.sessionCategoryFilter || item.category === S.sessionCategoryFilter;
    return matchesQuery && matchesCategory;
  });
  return `<div class="panel" style="padding-bottom:8px">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    Chat History <button id="btn-reload-sessions" class="sm">Refresh</button>
  </div>
  <input id="session-search" placeholder="Search sessions" value="${esc(S.sessionSearch)}" style="margin-bottom:6px"/>
  <div class="cat-filter">
    <span class="cat-chip${!S.sessionCategoryFilter ? " active" : ""}" data-cat="">All</span>
    ${categories
      .map(
        (category) =>
          `<span class="cat-chip${S.sessionCategoryFilter === category ? " active" : ""}" data-cat="${esc(category)}">${esc(category)}</span>`
      )
      .join("")}
  </div>
</div>
<div class="sessions-list">
  ${sessions.length
    ? sessions
        .map(
          (item) => `<div class="session-item${S.sessionId === item.session_id ? " active" : ""}" data-sid="${esc(item.session_id)}">
    <div class="session-item-info">
      <div class="session-item-id">${esc(item.category || "Untitled Chat")}</div>
      <div class="session-item-meta">${esc(item.session_id.slice(0, 14))} · ${(item.updated_at || "").slice(0, 10)}</div>
    </div>
    <div class="session-item-actions">
      <button class="sm danger" data-del-sid="${esc(item.session_id)}" title="Delete">Delete</button>
    </div>
  </div>`
        )
        .join("")
    : `<div class="section-empty">${S.sessions.length ? "No matching sessions." : "No sessions yet."}</div>`}
</div>`;
}
