import "./styles.css";
import {
  ACCENT_K,
  AK,
  APP_VERSION,
  GITHUB,
  S,
  SK,
  SESSK,
  type Auth,
  type Msg,
} from "./state";
import { accountTab, esc, historyTab, md, serverTab } from "./tabs-a";
import { memoryTab, personasTab } from "./tabs-b";
import { adminTab, personaliseTab, settingsTab, updateTab } from "./tabs-c";
import { tasksTab } from "./tabs-tasks";
import { browserTab } from "./tabs-browser";
import { terminalTab } from "./tabs-terminal";

type Health = { ok: boolean; status: string; detail: string };

function norm(value: string): string {
  const raw = (value || "").trim();
  if (!raw) {
    return S.serverUrl;
  }
  const prepared = /^https?:\/\//i.test(raw) ? raw : `http://${raw}`;
  try {
    return new URL(prepared).origin;
  } catch {
    return S.serverUrl;
  }
}

function setAuth(auth: Auth | null): void {
  S.auth = auth;
  if (auth) {
    localStorage.setItem(AK, JSON.stringify(auth));
  } else {
    localStorage.removeItem(AK);
  }
}

function isAdmin(): boolean {
  return S.auth?.role === "admin";
}

function headers(extra?: HeadersInit): Headers {
  const out = new Headers(extra);
  if (!out.has("Content-Type")) {
    out.set("Content-Type", "application/json");
  }
  if (S.auth?.token) {
    out.set("Authorization", `Bearer ${S.auth.token}`);
  }
  return out;
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 25000);
  try {
    const response = await fetch(`${S.serverUrl}${path}`, {
      ...init,
      headers: headers(init.headers),
      signal: controller.signal,
    });
    const text = await response.text();
    const data = text ? JSON.parse(text) : {};
    if (!response.ok) {
      throw new Error(data?.detail || data?.message || response.statusText);
    }
    return data as T;
  } finally {
    clearTimeout(timer);
  }
}

function setThemeAccent(color: string): void {
  const root = document.documentElement;
  root.style.setProperty("--accent", color);
  root.style.setProperty("--accent-2", color);
  S.themeAccent = color;
  localStorage.setItem(ACCENT_K, color);
}

function applySidebarState(): void {
  const sidebar = document.querySelector(".sidebar");
  if (sidebar) {
    sidebar.classList.toggle("collapsed", !!S.sidebarCollapsed);
  }
}

function toast(message: string, type: "ok" | "err" | "info" = "info"): void {
  const container = document.getElementById("toast-container");
  if (!container) {
    return;
  }
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function pushMsg(role: Msg["role"], content: string): void {
  S.msgs.push({
    role,
    content,
    time: new Date().toLocaleTimeString(),
  });
}

function newSessionId(): string {
  const id =
    globalThis.crypto?.randomUUID?.() ||
    `d-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  S.sessionId = id;
  localStorage.setItem(SESSK, id);
  return id;
}

function renderAttachPills(): string {
  return S.attachments
    .map(
      (attachment, index) => `
<div class="attach-pill">
  <span title="${esc(attachment.filename)}">${esc(attachment.filename.slice(0, 22))}</span>
  <button class="attach-del" data-del-attach="${index}">×</button>
</div>`
    )
    .join("");
}

function renderMsgs(): string {
  if (!S.msgs.length) {
    return `
<div class="chat-empty">
  <div class="msg-avatar" style="background:linear-gradient(135deg,#10b981,#3b82f6)">AI</div>
  <div class="chat-empty-bubble">
    <strong>Hello! I'm AmpAI.</strong><br/>
    I remember your conversations and can reuse them in future chats.<br/><br/>
    <span style="color:var(--muted);font-size:.85rem">Chat history, memory, admin settings, and integrations are shared between the web app and the Windows app.</span>
  </div>
</div>`;
  }
  const rows = S.msgs.map((msg) => {
    const userInitial = S.auth?.username?.[0]?.toUpperCase() || "U";
    const avatar =
      msg.role === "user" ? userInitial : msg.role === "system" ? "i" : "AI";
    const content =
      msg.role === "user"
        ? esc(msg.content)
        : `<div>${md(msg.content)}</div>`;
    return `
<div class="msg-row ${msg.role}">
  <div class="msg-avatar">${avatar}</div>
  <div>
    <div class="msg-meta">${esc(msg.role)} · ${esc(msg.time)}</div>
    <div class="msg-bubble">${content}</div>
  </div>
</div>`;
  });
  if (S.busy) {
    rows.push(`
<div class="msg-row assistant">
  <div class="msg-avatar">AI</div>
  <div class="msg-bubble">
    <div class="typing-dots"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>
  </div>
</div>`);
  }
  return rows.join("");
}

function render(): void {
  const app = document.getElementById("app");
  if (!app) {
    return;
  }
  app.innerHTML = `
<div class="app-shell">
  <aside class="sidebar${S.sidebarCollapsed ? " collapsed" : ""}">
    <div class="sidebar-header">
      <div class="sidebar-brand">
        <div class="brand-icon">AI</div>
        <div>
          <div class="brand-name">AmpAI</div>
          <div class="brand-sub">Shared Desktop + Web</div>
        </div>
      </div>
      <button class="collapse-btn" id="btn-sidebar-collapse">${S.sidebarCollapsed ? "»" : "«"}</button>
    </div>
    <div class="tab-bar">
      ${tabButton("server", "💬 Chat")}
      ${tabButton("account", "Account")}
      ${S.auth ? tabButton("history", "History") : ""}
      ${S.auth ? tabButton("memory", "🧠 Memory") : ""}
      ${S.auth ? tabButton("tasks", "📋 Tasks") : ""}
      ${S.auth ? tabButton("browser", "🌐 Browser") : ""}
      ${S.auth ? tabButton("terminal", "⌨️ Terminal") : ""}
      ${S.auth ? tabButton("personas", "AI Personas") : ""}
      ${S.auth ? tabButton("settings", "⚙️ Settings") : ""}
      ${S.auth ? tabButton("personalise", "🎨 Personalise") : ""}
      ${isAdmin() ? tabButton("telegram", "📱 Telegram") : ""}
      ${isAdmin() ? tabButton("admin", "🛡️ Admin") : ""}
      ${isAdmin() ? tabButton("update", "Update") : ""}
    </div>
    <div class="tab-panels">
      ${tabPanel("server", serverTab())}
      ${tabPanel("account", accountTab())}
      ${S.auth ? tabPanel("history", historyTab()) : ""}
      ${S.auth ? tabPanel("memory", memoryTab()) : ""}
      ${S.auth ? tabPanel("tasks", tasksTab()) : ""}
      ${S.auth ? tabPanel("browser", browserTab()) : ""}
      ${S.auth ? tabPanel("terminal", terminalTab()) : ""}
      ${S.auth ? tabPanel("personas", personasTab()) : ""}
      ${S.auth ? tabPanel("settings", settingsTab()) : ""}
      ${S.auth ? tabPanel("personalise", personaliseTab()) : ""}
      ${isAdmin() ? tabPanel("telegram", telegramSettingsTab()) : ""}
      ${isAdmin() ? tabPanel("admin", adminTab()) : ""}
      ${isAdmin() ? tabPanel("update", updateTab()) : ""}
    </div>
  </aside>
  <main class="chat-shell">
    ${chatTopbar()}
    <div class="chat-messages" id="msgs">${renderMsgs()}</div>
    <div class="chat-input-bar">
      <div class="attach-pills" id="attach-pills">${renderAttachPills()}</div>
      <div class="input-box">
        <textarea id="chat-textarea" class="chat-textarea" rows="1" placeholder="${S.auth ? "Message AmpAI…" : "Login to chat"}" ${S.auth ? "" : "disabled"}></textarea>
        <label class="attach-btn" title="Attach file">
          📎
          <input type="file" id="file-input" multiple style="display:none"/>
        </label>
        <button class="chat-send-btn" id="btn-send" ${S.auth && !S.busy ? "" : "disabled"}>${S.busy ? "…" : "Send"}</button>
      </div>
    </div>
  </main>
</div>
<div id="toast-container"></div>`;
  const msgBox = document.getElementById("msgs");
  if (msgBox) {
    msgBox.scrollTop = msgBox.scrollHeight;
  }
  applySidebarState();
  bind();
}

function tabButton(id: string, label: string): string {
  return `<button class="tab-btn${S.tab === id ? " active" : ""}" data-tab="${id}">${esc(label)}</button>`;
}

function tabPanel(id: string, content: string): string {
  return `<div class="tab-panel${S.tab === id ? " active" : ""}">${content}</div>`;
}

function chatTopbar(): string {
  const providers = S.providers.length
    ? S.providers
    : [
        { value: "ollama", label: "Ollama" },
        { value: "generic", label: "LM Studio" },
        { value: "anythingllm", label: "AnythingLLM" },
        { value: "openrouter", label: "OpenRouter" },
        { value: "openai", label: "OpenAI" },
        { value: "gemini", label: "Gemini" },
        { value: "anthropic", label: "Anthropic" },
      ];
  const session = S.sessions.find((item) => item.session_id === S.sessionId);
  return `
<div class="chat-topbar">
  <div class="chat-topbar-info">
    <div class="chat-topbar-title">${esc(session?.category || "AmpAI Chat")}</div>
    <div class="chat-topbar-sub">${esc(S.sessionId.slice(0, 20))}…</div>
  </div>
  <span class="ai-name-badge">${esc(S.configs.chat_agent_name || "AmpAI")}</span>
  <select class="chat-topbar-select" id="sel-model">
    ${providers
      .map(
        (provider) =>
          `<option value="${esc(provider.value)}"${S.modelType === provider.value ? " selected" : ""}>${esc(provider.label)}</option>`
      )
      .join("")}
  </select>
  <select class="chat-topbar-select" id="sel-memory">
    ${["full", "indexed", "context_only", "none"]
      .map(
        (mode) =>
          `<option value="${mode}"${S.memoryMode === mode ? " selected" : ""}>${esc(mode)}</option>`
      )
      .join("")}
  </select>
  <label class="chat-topbar-check"><input type="checkbox" id="chk-websearch" ${S.useWebSearch ? "checked" : ""}/> Web</label>
  <button class="sm" id="btn-new-session">New</button>
</div>`;
}

function telegramSettingsTab(): string {
  const cfg = S.configs;
  const tg = S.tgStatus;
  return `<div class="panel">
  <div class="panel-title">📱 Telegram Bot ${tg ? `<span class="badge ${tg.enabled ? "ok" : "bad"}" style="float:right;font-size:.69rem">${tg.enabled ? "Enabled" : "Disabled"}</span>` : ""}</div>
  ${tg ? `<div class="hint" style="margin-bottom:8px">Token: ${esc(tg.token_masked || "not set")} | Polling: ${tg.polling_enabled ? "On" : "Off"}</div>` : ""}
  <form class="stack" id="tg-form">
    <label class="field">Bot Token<input name="telegram_bot_token" value="${esc(cfg.telegram_bot_token || "")}" type="password" placeholder="123456:ABC-…"/></label>
    <label class="field">Webhook URL<input name="telegram_webhook_url" value="${esc(cfg.telegram_webhook_url || tg?.webhook_url || "")}" placeholder="https://yourdomain.com/webhook"/></label>
    <div class="row">
      <button class="primary" type="submit">💾 Save</button>
      <button type="button" id="btn-tg-test">🤖 Test</button>
    </div>
    <div class="row">
      <button type="button" id="btn-tg-connect">🔗 Set Webhook</button>
      <button type="button" id="btn-tg-disconnect">❌ Remove</button>
    </div>
    <div class="row">
      <button type="button" id="btn-tg-polling-on" class="success">▶ Enable Polling</button>
      <button type="button" id="btn-tg-polling-off" class="danger">⏹ Disable Polling</button>
    </div>
  </form>
</div>`;
}

async function checkServer(): Promise<void> {
  const candidates = Array.from(
    new Set([
      S.serverUrl,
      "http://127.0.0.1:8001",
      "http://127.0.0.1:8000",
      "http://192.168.20.5:8001",
      "http://192.168.20.5:8000",
    ])
  );
  for (const candidate of candidates) {
    try {
      const response = await fetch(`${candidate}/healthz`, {
        signal: AbortSignal.timeout(5000),
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        continue;
      }
      const data = await response.json();
      S.serverUrl = candidate;
      localStorage.setItem(SK, candidate);
      S.health = {
        ok: data.status === "ok",
        status: data.status || "ok",
        detail: `Connected: ${candidate}`,
      } as Health;
      render();
      return;
    } catch {
      continue;
    }
  }
  S.health = { ok: false, status: "offline", detail: "Cannot reach server" };
  render();
}

function versionParts(version: string): number[] {
  return version
    .replace(/^v/i, "")
    .split(".")
    .map((item) => Number.parseInt(item, 10) || 0);
}

function isVersionNewer(next: string, current: string): boolean {
  const left = versionParts(next);
  const right = versionParts(current);
  const size = Math.max(left.length, right.length);
  for (let i = 0; i < size; i += 1) {
    const a = left[i] || 0;
    const b = right[i] || 0;
    if (a > b) {
      return true;
    }
    if (a < b) {
      return false;
    }
  }
  return false;
}

async function loadDesktopRelease(): Promise<void> {
  try {
    const response = await fetch(
      `https://api.github.com/repos/${GITHUB}/releases/latest`,
      {
        headers: { Accept: "application/vnd.github+json" },
      }
    );
    if (!response.ok) {
      return;
    }
    const data = await response.json();
    const version = String(data.tag_name || data.name || "").replace(/^v/i, "");
    if (!version || !isVersionNewer(version, APP_VERSION)) {
      S.desktopUpdate = null;
      return;
    }
    const asset = Array.isArray(data.assets)
      ? data.assets.find((item: any) =>
          String(item.name || "").match(/\.(msi|exe)$/i)
        )
      : null;
    S.desktopUpdate = {
      version,
      url: asset?.browser_download_url || data.html_url,
    };
  } catch {
    S.desktopUpdate = null;
  }
}

async function loadTabData(tab: string): Promise<void> {
  if (!S.auth) {
    return;
  }
  try {
    if (tab === "history") {
      S.sessionPage = 1;
      S.sessionHasMore = true;
      S.sessionError = "";
      const data = await api<any>("/api/sessions?limit=40&archived=false");
      S.sessions = data.sessions || [];
      if (S.sessions.length < 40) {
        S.sessionHasMore = false;
      }
    }
    if (tab === "memory") {
      const memories = await api<any>("/api/core-memories");
      S.memories = memories.core_memories || [];
      if (S.memSubTab === "inbox") {
        const inbox = await api<any>(
          `/api/memory/inbox?status=${encodeURIComponent(S.inboxStatusFilter)}`
        );
        S.memoryInbox = inbox.items || inbox.candidates || [];
      }
      if (S.memSubTab === "analytics") {
        S.memoryAnalytics = await api<any>("/api/memory/analytics?days=30");
      }
    }
    if (tab === "tasks") {
      const data = await api<any>("/api/tasks");
      S.taskState.tasks = data.tasks || [];
    }
    if (tab === "browser") {
      try {
        const jobs = await api<any>("/api/browser/jobs?limit=200");
        S.browserState.jobs = jobs.jobs || [];
        if (isAdmin()) {
          const allowlist = await api<any>("/api/browser/allowlist");
          S.browserState.allowlist = allowlist.domains || allowlist.allowlist || [];
        }
      } catch { /* browser endpoints may not be available */ }
    }
    if (tab === "terminal") {
      try {
        const logs = await api<any>("/api/terminal/logs?limit=200");
        S.terminalState.logs = logs.logs || [];
        if (isAdmin()) {
          const policy = await api<any>("/api/terminal/policy");
          S.terminalState.policy = policy;
          S.terminalState.enabled = policy.enabled ?? false;
        }
      } catch { /* terminal endpoints may not be available */ }
    }
    if (tab === "personas") {
      const data = await api<any>("/api/personas");
      S.personas = data.personas || [];
    }
    if (tab === "settings" && isAdmin()) {
      const [configs, modelOptions] = await Promise.all([
        api<any>("/api/admin/configs"),
        api<any>("/api/models/options"),
      ]);
      S.configs = configs || {};
      S.providers = modelOptions.providers || [];
      S.modelType = S.configs.default_model_provider || S.modelType;
    }
    if (tab === "telegram" && isAdmin()) {
      const [configs, telegram] = await Promise.all([
        api<any>("/api/admin/configs"),
        api<any>("/api/admin/integrations/telegram/status"),
      ]);
      S.configs = configs || {};
      S.tgStatus = telegram;
    }
    if (tab === "admin" && isAdmin()) {
      const [users, summary, health, systemHealth] = await Promise.all([
        api<any>("/api/admin/users"),
        api<any>("/api/analytics/summary"),
        api<any>("/api/admin/settings/health"),
        api<any>("/api/health"),
      ]);
      S.users = users.users || [];
      S.adminStats = {
        session_count: summary.total_sessions,
        memory_count: summary.total_memories,
        user_count: users.users?.length || 0,
        uptime: systemHealth?.checks?.app?.detail || systemHealth?.status || "ok",
        health_checks: health.checks || [],
      };
    }
    if (tab === "browser") {
      try {
        const [allowlistData, jobsData] = await Promise.all([
          api<any>("/api/browser/allowlist").catch(() => ({ domains: [] })),
          api<any>("/api/browser/jobs?limit=200").catch(() => ({ jobs: [] })),
        ]);
        S.browserState.allowlist = allowlistData.domains || allowlistData.allowlist || [];
        S.browserState.jobs = jobsData.jobs || [];
        S.browserState.enabled = allowlistData.enabled ?? S.browserState.enabled;
      } catch { /* handled per-call above */ }
    }
    if (tab === "update" && isAdmin()) {
      S.updateVersion = await api<any>("/api/admin/update/version");
      const status = await api<any>("/api/admin/update/status");
      S.updateStatus = status;
      S.updateLog = status.log_lines || [];
      await loadDesktopRelease();
    }
  } catch (error: any) {
    toast(error.message || `Failed to load ${tab}`, "err");
  } finally {
    render();
  }
}

function switchTab(tab: string): void {
  S.tab = tab;
  render();
  void loadTabData(tab);
}

function bind(): void {
  document
    .querySelectorAll<HTMLButtonElement>(".tab-btn[data-tab]")
    .forEach((button) => {
      button.addEventListener("click", () => switchTab(button.dataset.tab || "server"));
    });

  document
    .getElementById("btn-sidebar-collapse")
    ?.addEventListener("click", () => {
      S.sidebarCollapsed = !S.sidebarCollapsed;
      localStorage.setItem("ampai.sidebarCollapsed", S.sidebarCollapsed ? "1" : "0");
      render();
    });

  document
    .querySelectorAll<HTMLButtonElement>(".quick-url[data-url]")
    .forEach((button) => {
      button.addEventListener("click", () => {
        S.serverUrl = norm(button.dataset.url || "");
        localStorage.setItem(SK, S.serverUrl);
        void checkServer();
      });
    });

  document.getElementById("server-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget as HTMLFormElement);
    S.serverUrl = norm(String(form.get("url") || ""));
    localStorage.setItem(SK, S.serverUrl);
    await checkServer();
  });

  document
    .getElementById("btn-test-server")
    ?.addEventListener("click", () => void checkServer());

  document.getElementById("login-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget as HTMLFormElement);
    S.busy = true;
    render();
    try {
      const auth = await api<Auth>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          username: form.get("username"),
          password: form.get("password"),
          remember_me: true,
        }),
      });
      setAuth(auth);
      pushMsg("system", `Signed in as ${auth.username} (${auth.role})`);
      S.tab = "history";
    } catch (error: any) {
      pushMsg("system", error.message || "Login failed");
    } finally {
      S.busy = false;
      render();
      if (S.auth) {
        void loadTabData(S.tab);
      }
    }
  });

  document.getElementById("btn-logout")?.addEventListener("click", () => {
    setAuth(null);
    S.sessions = [];
    S.memories = [];
    S.memoryInbox = [];
    S.personas = [];
    S.users = [];
    S.tab = "account";
    render();
  });

  document.getElementById("sel-model")?.addEventListener("change", (event) => {
    S.modelType = (event.currentTarget as HTMLSelectElement).value;
  });
  document.getElementById("sel-memory")?.addEventListener("change", (event) => {
    S.memoryMode = (event.currentTarget as HTMLSelectElement).value;
  });
  document.getElementById("chk-websearch")?.addEventListener("change", (event) => {
    S.useWebSearch = (event.currentTarget as HTMLInputElement).checked;
  });
  document.getElementById("btn-new-session")?.addEventListener("click", () => {
    newSessionId();
    S.msgs = [];
    S.attachments = [];
    render();
  });

  const textarea = document.getElementById("chat-textarea") as HTMLTextAreaElement | null;
  textarea?.addEventListener("keydown", (event: KeyboardEvent) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void doSend();
    }
  });
  textarea?.addEventListener("input", () => {
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 130)}px`;
  });
  document.getElementById("btn-send")?.addEventListener("click", () => void doSend());

  document.getElementById("file-input")?.addEventListener("change", async (event) => {
    const files = Array.from(
      (event.currentTarget as HTMLInputElement).files || []
    );
    if (!files.length) {
      return;
    }
    for (const file of files) {
      const formData = new FormData();
      formData.append("file", file);
      try {
        const response = await fetch(
          `${S.serverUrl}/api/upload?session_id=${encodeURIComponent(S.sessionId)}`,
          {
            method: "POST",
            headers: S.auth?.token
              ? { Authorization: `Bearer ${S.auth.token}` }
              : undefined,
            body: formData,
          }
        );
        if (!response.ok) {
          throw new Error(file.name);
        }
        const data = await response.json();
        S.attachments.push(data);
        toast(`Attached: ${file.name}`, "ok");
      } catch {
        toast(`Upload failed: ${file.name}`, "err");
      }
    }
    (event.currentTarget as HTMLInputElement).value = "";
    render();
  });

  bindAttachDelete();
  bindHistory();
  bindMemory();
  bindPersonas();
  bindSettings();
  bindPersonalise();
  bindTelegram();
  bindTasks();
  bindBrowser();
  bindTerminal();
  bindAdmin();
  bindUpdate();
}

function bindAttachDelete(): void {
  document
    .querySelectorAll<HTMLButtonElement>("[data-del-attach]")
    .forEach((button) => {
      button.addEventListener("click", () => {
        const index = Number.parseInt(button.dataset.delAttach || "-1", 10);
        if (index >= 0) {
          S.attachments.splice(index, 1);
          render();
        }
      });
    });
}

function bindHistory(): void {
  document.getElementById("btn-reload-sessions")?.addEventListener("click", () => {
    S.sessionPage = 1;
    S.sessionHasMore = true;
    void loadTabData("history");
  });

  // New chat button in sidebar
  document.getElementById("btn-new-chat-sidebar")?.addEventListener("click", () => {
    newSessionId();
    S.msgs = [];
    S.attachments = [];
    S.tab = "server";
    render();
  });

  // Debounced search (300ms)
  let searchTimer: ReturnType<typeof setTimeout> | null = null;
  document.getElementById("session-search")?.addEventListener("input", (event) => {
    const value = (event.currentTarget as HTMLInputElement).value;
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      S.sessionSearch = value;
      render();
    }, 300);
  });

  // Category filter chips
  document.querySelectorAll<HTMLElement>("[data-cat]").forEach((chip) => {
    chip.addEventListener("click", () => {
      S.sessionCategoryFilter = chip.dataset.cat || "";
      render();
    });
  });

  // Load more on scroll
  const scrollContainer = document.getElementById("sessions-list-scroll");
  scrollContainer?.addEventListener("scroll", () => {
    if (S.sessionLoadingMore || !S.sessionHasMore) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
    if (scrollTop + clientHeight >= scrollHeight - 50) {
      void loadMoreSessions();
    }
  });

  // Load more button
  document.getElementById("btn-load-more-sessions")?.addEventListener("click", () => {
    void loadMoreSessions();
  });

  // Click session to load it
  document.querySelectorAll<HTMLElement>(".session-item[data-sid]").forEach((row) => {
    row.addEventListener("click", async (event) => {
      const target = event.target as HTMLElement;
      if (target.closest("[data-del-sid]") || target.closest("[data-rename-sid]") ||
          target.closest("[data-pin-sid]") || target.closest("[data-archive-sid]") ||
          target.closest("[data-assign-cat-sid]") || target.closest("[data-rename-save]") ||
          target.closest("[data-rename-cancel]") || target.closest("[data-category-save]") ||
          target.closest("[data-category-cancel]") || target.closest("input")) {
        return;
      }
      const sessionId = row.dataset.sid || "";
      if (!sessionId) return;
      S.sessionId = sessionId;
      localStorage.setItem(SESSK, sessionId);
      try {
        const data = await api<any>(`/api/history/${encodeURIComponent(sessionId)}`);
        S.msgs = (data.messages || []).map((message: any) => ({
          role: message.type === "human" ? "user" : "assistant",
          content: message.content || "",
          time: "",
        }));
        S.tab = "server";
      } catch (error: any) {
        pushMsg("system", `Failed to load history: ${error.message}`);
      }
      render();
    });
  });

  // Delete session
  document.querySelectorAll<HTMLButtonElement>("[data-del-sid]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      const sessionId = button.dataset.delSid || "";
      if (!sessionId || !confirm("Delete this chat session?")) return;
      S.sessionError = "";
      try {
        await api(`/api/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
        S.sessions = S.sessions.filter((item) => item.session_id !== sessionId);
        if (S.sessionId === sessionId) {
          newSessionId();
          S.msgs = [];
        }
        toast("Session deleted.", "info");
        render();
      } catch (error: any) {
        S.sessionError = `Delete failed: ${error.message || "Unknown error"}`;
        toast(error.message || "Failed to delete session", "err");
        render();
      }
    });
  });

  // Pin/unpin session
  document.querySelectorAll<HTMLButtonElement>("[data-pin-sid]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      const sessionId = button.dataset.pinSid || "";
      if (!sessionId) return;
      const session = S.sessions.find((item) => item.session_id === sessionId);
      if (!session) return;
      const newPinned = !session.pinned;
      try {
        await api(`/api/sessions/${encodeURIComponent(sessionId)}`, {
          method: "PATCH",
          body: JSON.stringify({ pinned: newPinned }),
        });
        session.pinned = newPinned;
        toast(newPinned ? "Session pinned." : "Session unpinned.", "ok");
        render();
      } catch (error: any) {
        toast(error.message || "Failed to update pin", "err");
      }
    });
  });

  // Archive session
  document.querySelectorAll<HTMLButtonElement>("[data-archive-sid]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      const sessionId = button.dataset.archiveSid || "";
      if (!sessionId) return;
      S.sessionError = "";
      try {
        await api(`/api/sessions/${encodeURIComponent(sessionId)}`, {
          method: "PATCH",
          body: JSON.stringify({ archived: true }),
        });
        S.sessions = S.sessions.filter((item) => item.session_id !== sessionId);
        toast("Session archived.", "ok");
        render();
      } catch (error: any) {
        S.sessionError = `Archive failed: ${error.message || "Unknown error"}`;
        toast(error.message || "Failed to archive session", "err");
        render();
      }
    });
  });

  // Rename session - start
  document.querySelectorAll<HTMLButtonElement>("[data-rename-sid]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const sessionId = button.dataset.renameSid || "";
      if (!sessionId) return;
      const session = S.sessions.find((item) => item.session_id === sessionId);
      S.renamingSessionId = sessionId;
      S.renamingSessionTitle = session?.title || session?.category || "";
      render();
      // Focus the rename input
      setTimeout(() => {
        const input = document.getElementById(`rename-input-${sessionId}`) as HTMLInputElement | null;
        if (input) { input.focus(); input.select(); }
      }, 50);
    });
  });

  // Rename session - save
  document.querySelectorAll<HTMLButtonElement>("[data-rename-save]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      const sessionId = button.dataset.renameSave || "";
      if (!sessionId) return;
      const input = document.getElementById(`rename-input-${sessionId}`) as HTMLInputElement | null;
      const title = (input?.value || "").trim().slice(0, 100);
      if (!title) { toast("Title cannot be empty.", "err"); return; }
      try {
        await api(`/api/sessions/${encodeURIComponent(sessionId)}`, {
          method: "PATCH",
          body: JSON.stringify({ title }),
        });
        const session = S.sessions.find((item) => item.session_id === sessionId);
        if (session) { session.title = title; }
        S.renamingSessionId = null;
        S.renamingSessionTitle = "";
        toast("Session renamed.", "ok");
        render();
      } catch (error: any) {
        toast(error.message || "Failed to rename session", "err");
      }
    });
  });

  // Rename session - cancel
  document.querySelectorAll<HTMLButtonElement>("[data-rename-cancel]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      S.renamingSessionId = null;
      S.renamingSessionTitle = "";
      render();
    });
  });

  // Rename session - Enter key to save, Escape to cancel
  document.querySelectorAll<HTMLInputElement>(".session-rename-input").forEach((input) => {
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        const saveBtn = input.parentElement?.parentElement?.querySelector("[data-rename-save],[data-category-save]") as HTMLButtonElement | null;
        saveBtn?.click();
      }
      if (event.key === "Escape") {
        event.preventDefault();
        const cancelBtn = input.parentElement?.parentElement?.querySelector("[data-rename-cancel],[data-category-cancel]") as HTMLButtonElement | null;
        cancelBtn?.click();
      }
    });
  });

  // Assign category - start
  document.querySelectorAll<HTMLButtonElement>("[data-assign-cat-sid]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const sessionId = button.dataset.assignCatSid || "";
      if (!sessionId) return;
      const session = S.sessions.find((item) => item.session_id === sessionId);
      S.assigningCategorySessionId = sessionId;
      S.assigningCategoryValue = session?.category || "";
      render();
      setTimeout(() => {
        const input = document.getElementById(`category-input-${sessionId}`) as HTMLInputElement | null;
        if (input) { input.focus(); input.select(); }
      }, 50);
    });
  });

  // Assign category - save
  document.querySelectorAll<HTMLButtonElement>("[data-category-save]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      const sessionId = button.dataset.categorySave || "";
      if (!sessionId) return;
      const input = document.getElementById(`category-input-${sessionId}`) as HTMLInputElement | null;
      const category = (input?.value || "").trim() || "Uncategorized";
      try {
        await api(`/api/sessions/${encodeURIComponent(sessionId)}`, {
          method: "PATCH",
          body: JSON.stringify({ category }),
        });
        const session = S.sessions.find((item) => item.session_id === sessionId);
        if (session) { session.category = category; }
        S.assigningCategorySessionId = null;
        S.assigningCategoryValue = "";
        toast("Category updated.", "ok");
        render();
      } catch (error: any) {
        toast(error.message || "Failed to assign category", "err");
      }
    });
  });

  // Assign category - cancel
  document.querySelectorAll<HTMLButtonElement>("[data-category-cancel]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      S.assigningCategorySessionId = null;
      S.assigningCategoryValue = "";
      render();
    });
  });
}

async function loadMoreSessions(): Promise<void> {
  if (S.sessionLoadingMore || !S.sessionHasMore) return;
  S.sessionLoadingMore = true;
  render();
  try {
    const nextPage = S.sessionPage + 1;
    const offset = (nextPage - 1) * 40;
    const data = await api<any>(`/api/sessions?limit=40&offset=${offset}&archived=false`);
    const newSessions = data.sessions || [];
    if (newSessions.length < 40) {
      S.sessionHasMore = false;
    }
    // Append new sessions, avoiding duplicates
    const existingIds = new Set(S.sessions.map((s: any) => s.session_id));
    for (const session of newSessions) {
      if (!existingIds.has(session.session_id)) {
        S.sessions.push(session);
      }
    }
    S.sessionPage = nextPage;
  } catch (error: any) {
    toast(error.message || "Failed to load more sessions", "err");
  } finally {
    S.sessionLoadingMore = false;
    render();
  }
}

function bindMemory(): void {
  document.querySelectorAll<HTMLButtonElement>("[data-mem-sub]").forEach((button) => {
    button.addEventListener("click", () => {
      S.memSubTab = (button.dataset.memSub as any) || "core";
      void loadTabData("memory");
    });
  });

  document.getElementById("mem-add-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget as HTMLFormElement);
    const fact = String(form.get("fact") || "").trim();
    if (!fact) {
      return;
    }
    try {
      if (S.editingMemId != null) {
        await api(`/api/admin/core-memories/${S.editingMemId}`, {
          method: "PATCH",
          body: JSON.stringify({ fact }),
        });
        S.editingMemId = null;
        S.editingMemFact = "";
        toast("Memory updated.", "ok");
      } else {
        await api("/api/core-memories", {
          method: "POST",
          body: JSON.stringify({ fact }),
        });
        toast("Memory added.", "ok");
      }
      await loadTabData("memory");
    } catch (error: any) {
      toast(error.message, "err");
    }
  });

  document.getElementById("btn-reload-memory")?.addEventListener("click", () => {
    void loadTabData("memory");
  });

  document.querySelectorAll<HTMLButtonElement>("[data-edit-mem]").forEach((button) => {
    button.addEventListener("click", () => {
      const id = Number.parseInt(button.dataset.editMem || "", 10);
      const memory = S.memories.find((item) => item.id === id);
      if (!memory) {
        return;
      }
      S.editingMemId = id;
      S.editingMemFact = memory.fact;
      render();
    });
  });

  document
    .querySelectorAll<HTMLButtonElement>("[data-cancel-edit-mem]")
    .forEach((button) => {
      button.addEventListener("click", () => {
        S.editingMemId = null;
        S.editingMemFact = "";
        render();
      });
    });

  document.querySelectorAll<HTMLButtonElement>("[data-save-mem]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = Number.parseInt(button.dataset.saveMem || "", 10);
      const textarea = document.getElementById(`mem-edit-${id}`) as HTMLTextAreaElement | null;
      const fact = textarea?.value.trim() || "";
      if (!fact) {
        return;
      }
      try {
        await api(`/api/admin/core-memories/${id}`, {
          method: "PATCH",
          body: JSON.stringify({ fact }),
        });
        S.editingMemId = null;
        S.editingMemFact = "";
        toast("Memory updated.", "ok");
        await loadTabData("memory");
      } catch (error: any) {
        toast(error.message, "err");
      }
    });
  });

  document.querySelectorAll<HTMLButtonElement>("[data-del-mem]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.delMem || "";
      if (!id || !confirm("Delete this memory?")) {
        return;
      }
      try {
        await api(`/api/admin/core-memories/${id}`, { method: "DELETE" });
        toast("Memory deleted.", "info");
        await loadTabData("memory");
      } catch (error: any) {
        toast(error.message, "err");
      }
    });
  });

  document.getElementById("recall-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget as HTMLFormElement);
    const query = String(form.get("q") || "").trim();
    const target = document.getElementById("recall-results");
    if (!query || !target) {
      return;
    }
    target.textContent = "Searching…";
    try {
      const data = await api<any>("/api/recall/search", {
        method: "POST",
        body: JSON.stringify({ q: query, session_id: "", limit: 10 }),
      });
      target.innerHTML = data.summary
        ? `<div style="white-space:pre-wrap">${esc(data.summary)}</div>`
        : `<div class="hint">No results found.</div>`;
    } catch (error: any) {
      target.textContent = error.message;
    }
  });

  document.getElementById("btn-reload-inbox")?.addEventListener("click", () => {
    void loadTabData("memory");
  });
  document.getElementById("inbox-status-filter")?.addEventListener("change", (event) => {
    S.inboxStatusFilter = (event.currentTarget as HTMLSelectElement).value;
    void loadTabData("memory");
  });
  document.querySelectorAll<HTMLButtonElement>("[data-inbox-approve]").forEach((button) => {
    button.addEventListener("click", () =>
      void updateInboxItem(button.dataset.inboxApprove || "", "approved")
    );
  });
  document.querySelectorAll<HTMLButtonElement>("[data-inbox-reject]").forEach((button) => {
    button.addEventListener("click", () =>
      void updateInboxItem(button.dataset.inboxReject || "", "rejected")
    );
  });
  document.querySelectorAll<HTMLButtonElement>("[data-inbox-del]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.inboxDel || "";
      if (!id || !confirm("Delete this inbox item?")) {
        return;
      }
      try {
        await api(`/api/memory/inbox/${encodeURIComponent(id)}`, { method: "DELETE" });
        await loadTabData("memory");
      } catch (error: any) {
        toast(error.message, "err");
      }
    });
  });
  document.querySelectorAll<HTMLButtonElement>("[data-inbox-edit]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.inboxEdit || "";
      const item = S.memoryInbox.find((row) => String(row.id) === id);
      if (!item) {
        return;
      }
      const edited = prompt(
        "Edit memory candidate",
        item.edited_text || item.candidate_text
      );
      if (edited == null) {
        return;
      }
      try {
        await api(`/api/memory/inbox/${encodeURIComponent(id)}`, {
          method: "PATCH",
          body: JSON.stringify({ edited_text: edited, status: item.status }),
        });
        await loadTabData("memory");
      } catch (error: any) {
        toast(error.message, "err");
      }
    });
  });

  document.getElementById("btn-reload-analytics")?.addEventListener("click", () => {
    void loadTabData("memory");
  });
}

async function updateInboxItem(id: string, status: string): Promise<void> {
  if (!id) {
    return;
  }
  try {
    await api(`/api/memory/inbox/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    toast(`Memory candidate ${status}.`, "ok");
    await loadTabData("memory");
  } catch (error: any) {
    toast(error.message, "err");
  }
}

function bindPersonas(): void {
  document.getElementById("btn-new-persona")?.addEventListener("click", () => {
    S.editingPersona = null;
    S.personaModal = true;
    render();
  });
  document.querySelectorAll<HTMLButtonElement>("[data-edit-persona]").forEach((button) => {
    button.addEventListener("click", () => {
      const id = Number.parseInt(button.dataset.editPersona || "", 10);
      const persona = S.personas.find((item: any) => Number(item.id) === id);
      if (!persona) {
        return;
      }
      S.editingPersona = persona;
      S.personaModal = true;
      render();
    });
  });
  document
    .querySelectorAll<HTMLButtonElement>("[data-default-persona]")
    .forEach((button) => {
      button.addEventListener("click", async () => {
        const id = button.dataset.defaultPersona || "";
        try {
          await api(`/api/personas/${encodeURIComponent(id)}`, {
            method: "PATCH",
            body: JSON.stringify({ is_default: true }),
          });
          await loadTabData("personas");
        } catch (error: any) {
          toast(error.message, "err");
        }
      });
    });
  document.querySelectorAll<HTMLButtonElement>("[data-del-persona]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.delPersona || "";
      if (!id || !confirm("Delete this persona?")) {
        return;
      }
      try {
        await api(`/api/personas/${encodeURIComponent(id)}`, {
          method: "DELETE",
        });
        toast("Persona deleted.", "info");
        await loadTabData("personas");
      } catch (error: any) {
        toast(error.message, "err");
      }
    });
  });
  document
    .querySelectorAll<HTMLButtonElement>(
      "#btn-persona-modal-close,#btn-persona-modal-close2"
    )
    .forEach((button) => {
      button.addEventListener("click", () => {
        S.personaModal = false;
        S.editingPersona = null;
        render();
      });
    });
  document.getElementById("btn-save-persona")?.addEventListener("click", async () => {
    const id = (document.getElementById("persona-edit-id") as HTMLInputElement | null)
      ?.value;
    const name =
      (document.getElementById("persona-name") as HTMLInputElement | null)?.value.trim() ||
      "";
    const tagsRaw =
      (document.getElementById("persona-tags") as HTMLInputElement | null)?.value || "";
    const systemPrompt =
      (document.getElementById("persona-prompt") as HTMLTextAreaElement | null)?.value.trim() ||
      "";
    const isDefault = !!(
      document.getElementById("persona-default") as HTMLInputElement | null
    )?.checked;
    if (!name || !systemPrompt) {
      toast("Name and system prompt are required.", "err");
      return;
    }
    const payload = {
      name,
      system_prompt: systemPrompt,
      tags: tagsRaw
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      is_default: isDefault,
    };
    try {
      if (id) {
        await api(`/api/personas/${encodeURIComponent(id)}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      } else {
        await api("/api/personas", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      S.personaModal = false;
      S.editingPersona = null;
      await loadTabData("personas");
    } catch (error: any) {
      toast(error.message, "err");
    }
  });
}

function bindSettings(): void {
  document
    .getElementById("cfg-model-form")
    ?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget as HTMLFormElement);
      const configs: Record<string, string> = {};
      for (const [key, value] of form.entries()) {
        configs[key] = String(value || "");
      }
      try {
        await api("/api/admin/configs", {
          method: "POST",
          body: JSON.stringify({ configs }),
        });
        Object.assign(S.configs, configs);
        S.modelType = configs.default_model_provider || S.modelType;
        toast("Settings saved.", "ok");
        render();
      } catch (error: any) {
        toast(error.message, "err");
      }
    });

  document
    .getElementById("btn-fetch-ollama-models")
    ?.addEventListener("click", async () => {
      try {
        const response = await fetch(
          `${S.configs.ollama_base_url || "http://127.0.0.1:11434"}/api/tags`
        );
        const data = await response.json();
        S.ollamaModels = (data.models || []).map((item: any) => item.name).filter(Boolean);
        toast(`Loaded ${S.ollamaModels.length} Ollama models.`, "ok");
        render();
      } catch (error: any) {
        toast(error.message || "Failed to fetch Ollama models.", "err");
      }
    });

  document
    .getElementById("btn-settings-export")
    ?.addEventListener("click", async () => {
      try {
        const data = await api<any>("/api/admin/settings/export?include_secrets=false");
        const blob = new Blob([JSON.stringify(data, null, 2)], {
          type: "application/json",
        });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `ampai-settings-${new Date().toISOString().slice(0, 10)}.json`;
        link.click();
        toast(`Exported ${data.meta?.exported_key_count || 0} keys.`, "ok");
      } catch (error: any) {
        toast(error.message, "err");
      }
    });

  document
    .getElementById("settings-import-file")
    ?.addEventListener("change", async (event) => {
      const file = (event.currentTarget as HTMLInputElement).files?.[0];
      if (!file) {
        return;
      }
      try {
        const payload = JSON.parse(await file.text());
        const result = await api<any>("/api/admin/settings/import", {
          method: "POST",
          body: JSON.stringify({
            configs: payload.configs || payload,
            dry_run: false,
            conflict_strategy: "overwrite",
          }),
        });
        toast(`Imported ${(result.results || []).length} settings.`, "ok");
      } catch (error: any) {
        toast(error.message, "err");
      }
    });
}

function bindSimpleAction(id: string, path: string, successMessage: string): void {
  document.getElementById(id)?.addEventListener("click", async () => {
    try {
      const result = await api<any>(path, { method: "POST" });
      toast(
        result?.description || result?.message || successMessage,
        "ok"
      );
      if (S.tab === "settings") {
        await loadTabData("settings");
      }
    } catch (error: any) {
      toast(error.message, "err");
    }
  });
}

function bindPersonalise(): void {
  document.querySelectorAll<HTMLElement>("[data-accent]").forEach((swatch) => {
    swatch.addEventListener("click", () => {
      const color = swatch.dataset.accent || S.themeAccent;
      setThemeAccent(color);
      render();
    });
  });
  document.getElementById("btn-apply-colour")?.addEventListener("click", () => {
    const value =
      (document.getElementById("colour-hex") as HTMLInputElement | null)?.value.trim() ||
      S.themeAccent;
    if (!/^#[0-9a-f]{6}$/i.test(value)) {
      toast("Enter a valid hex colour like #2563eb", "err");
      return;
    }
    setThemeAccent(value);
    render();
  });
  document.getElementById("btn-toggle-sidebar")?.addEventListener("click", () => {
    S.sidebarCollapsed = !S.sidebarCollapsed;
    localStorage.setItem("ampai.sidebarCollapsed", S.sidebarCollapsed ? "1" : "0");
    render();
  });
}

function bindTelegram(): void {
  document.getElementById("tg-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget as HTMLFormElement);
    try {
      await api("/api/admin/integrations/telegram/save", {
        method: "POST",
        body: JSON.stringify({
          bot_token: form.get("telegram_bot_token"),
          webhook_url: form.get("telegram_webhook_url"),
          enabled: true,
        }),
      });
      await loadTabData("telegram");
      toast("Telegram settings saved.", "ok");
    } catch (error: any) {
      toast(error.message, "err");
    }
  });

  bindSimpleAction("btn-tg-test", "/api/admin/integrations/telegram/test", "Telegram test ok.");
  bindSimpleAction(
    "btn-tg-connect",
    "/api/admin/integrations/telegram/connect",
    "Telegram webhook connected."
  );
  bindSimpleAction(
    "btn-tg-disconnect",
    "/api/admin/integrations/telegram/disconnect",
    "Telegram webhook removed."
  );
  bindSimpleAction(
    "btn-tg-polling-on",
    "/api/admin/integrations/telegram/enable-polling",
    "Telegram polling enabled."
  );
  bindSimpleAction(
    "btn-tg-polling-off",
    "/api/admin/integrations/telegram/disable-polling",
    "Telegram polling disabled."
  );
}

function bindTasks(): void {
  document.getElementById("btn-reload-tasks")?.addEventListener("click", () => {
    void loadTabData("tasks");
  });
  document.querySelectorAll<HTMLButtonElement>("[data-task-status]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.taskId || "";
      const status = button.dataset.taskStatus || "";
      if (!id || !status) return;
      try {
        await api(`/api/tasks/${encodeURIComponent(id)}`, {
          method: "PATCH",
          body: JSON.stringify({ status }),
        });
        await loadTabData("tasks");
      } catch (error: any) {
        toast(error.message, "err");
      }
    });
  });
  document.querySelectorAll<HTMLButtonElement>("[data-del-task]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.dataset.delTask || "";
      if (!id || !confirm("Delete this task?")) return;
      try {
        await api(`/api/tasks/${encodeURIComponent(id)}`, { method: "DELETE" });
        toast("Task deleted.", "info");
        await loadTabData("tasks");
      } catch (error: any) {
        toast(error.message, "err");
      }
    });
  });
}

function bindBrowser(): void {
  document.getElementById("btn-reload-browser")?.addEventListener("click", () => {
    void loadTabData("browser");
  });

  document.getElementById("browser-allowlist-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget as HTMLFormElement);
    const domain = String(form.get("domain") || "").trim();
    if (!domain) return;
    try {
      const updated = [...S.browserState.allowlist, domain];
      await api("/api/browser/allowlist", {
        method: "POST",
        body: JSON.stringify({ domains: updated }),
      });
      S.browserState.allowlist = updated;
      toast(`Domain "${domain}" added to allowlist.`, "ok");
      render();
    } catch (error: any) {
      toast(error.message || "Failed to update allowlist", "err");
    }
  });
}

function bindTerminal(): void {
  document.getElementById("btn-reload-terminal")?.addEventListener("click", () => {
    void loadTabData("terminal");
  });
}

function bindAdmin(): void {
  document
    .querySelectorAll<HTMLButtonElement>("[data-admin-sub]")
    .forEach((button) => {
      button.addEventListener("click", () => {
        S.adminSubTab = (button.dataset.adminSub as any) || "dashboard";
        render();
        bindAdmin();
      });
    });

  document.getElementById("btn-reload-admin-stats")?.addEventListener("click", () => {
    void loadTabData("admin");
  });

  const grid = document.getElementById("admin-health-grid");
  if (grid && Array.isArray(S.adminStats?.health_checks)) {
    grid.innerHTML = S.adminStats.health_checks
      .map(
        (check: any) => `
<div class="panel" style="margin:0;padding:10px">
  <div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start">
    <strong style="font-size:.8rem">${esc(check.key || "check")}</strong>
    <span class="badge ${check.status === "ok" ? "ok" : check.status === "warn" ? "warn" : "bad"}">${esc(check.status || "unknown")}</span>
  </div>
  <div class="hint" style="margin-top:6px">${esc(check.message || "")}</div>
  ${check.fix_hint ? `<div class="hint" style="margin-top:4px;color:var(--yellow)">${esc(check.fix_hint)}</div>` : ""}
</div>`
      )
      .join("");
  }

  document.getElementById("add-user-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget as HTMLFormElement);
    try {
      await api("/api/admin/users", {
        method: "POST",
        body: JSON.stringify({
          username: form.get("username"),
          password: form.get("password"),
          role: form.get("role"),
        }),
      });
      await loadTabData("admin");
      toast("User created.", "ok");
    } catch (error: any) {
      toast(error.message, "err");
    }
  });

  document.querySelectorAll<HTMLButtonElement>("[data-del-user]").forEach((button) => {
    button.addEventListener("click", async () => {
      const username = button.dataset.delUser || "";
      if (!username || !confirm(`Delete user "${username}"?`)) {
        return;
      }
      try {
        await api(`/api/admin/users/${encodeURIComponent(username)}`, {
          method: "DELETE",
        });
        await loadTabData("admin");
        toast("User deleted.", "info");
      } catch (error: any) {
        toast(error.message, "err");
      }
    });
  });

  document
    .getElementById("agent-settings-form")
    ?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget as HTMLFormElement);
      const configs = {
        chat_agent_name: String(form.get("chat_agent_name") || ""),
        chat_agent_avatar_url: String(form.get("chat_agent_avatar_url") || ""),
      };
      try {
        await api("/api/admin/configs", {
          method: "POST",
          body: JSON.stringify({ configs }),
        });
        Object.assign(S.configs, configs);
        toast("Agent settings saved.", "ok");
        render();
      } catch (error: any) {
        toast(error.message, "err");
      }
    });

  document.getElementById("backup-cfg-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget as HTMLFormElement);
    const configs: Record<string, string> = {};
    for (const [key, value] of form.entries()) {
      configs[key] = String(value || "");
    }
    try {
      await api("/api/admin/configs", {
        method: "POST",
        body: JSON.stringify({ configs }),
      });
      Object.assign(S.configs, configs);
      toast("Backup settings saved.", "ok");
    } catch (error: any) {
      toast(error.message, "err");
    }
  });

  document.getElementById("btn-run-backup")?.addEventListener("click", async () => {
    try {
      const result = await api<any>("/api/admin/backup", { method: "POST" });
      const status = document.getElementById("backup-status");
      if (status) {
        status.textContent = result.message || "Backup started.";
      }
      toast(result.message || "Backup started.", "ok");
    } catch (error: any) {
      toast(error.message, "err");
    }
  });

  document.getElementById("btn-load-backups")?.addEventListener("click", async () => {
    try {
      const result = await api<any>("/api/admin/update/backups");
      S.backups = result.backups || [];
      render();
    } catch (error: any) {
      toast(error.message, "err");
    }
  });

  document.getElementById("retention-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget as HTMLFormElement);
    try {
      const configs = {
        retention_max_age_days: String(form.get("retention_chat_days") || "365"),
        recall_index_days: String(form.get("recall_index_days") || "365"),
        logs_days: String(form.get("logs_days") || "30"),
      };
      await api("/api/admin/configs", {
        method: "POST",
        body: JSON.stringify({ configs }),
      });
      Object.assign(S.configs, configs);
      const status = document.getElementById("retention-status");
      if (status) {
        status.textContent = "Retention settings saved.";
      }
      toast("Retention settings saved.", "ok");
    } catch (error: any) {
      toast(error.message, "err");
    }
  });

  document.getElementById("btn-retention-dry-run")?.addEventListener("click", async () => {
    const form = document.getElementById("retention-form") as HTMLFormElement | null;
    if (!form) {
      return;
    }
    const data = new FormData(form);
    try {
      const result = await api<any>("/api/admin/retention/dry-run", {
        method: "POST",
        body: JSON.stringify({
          max_age_days: Number(data.get("retention_chat_days") || 365),
          archive_only: true,
        }),
      });
      const status = document.getElementById("retention-status");
      if (status) {
        status.textContent = JSON.stringify(result);
      }
    } catch (error: any) {
      toast(error.message, "err");
    }
  });
}

function bindUpdate(): void {
  document.getElementById("btn-check-version")?.addEventListener("click", async () => {
    try {
      S.updateVersion = await api<any>("/api/admin/update/version");
      await loadDesktopRelease();
      render();
    } catch (error: any) {
      toast(error.message, "err");
    }
  });

  document.getElementById("btn-trigger-update")?.addEventListener("click", async () => {
    if (!confirm("Pull latest code from GitHub and restart the server?")) {
      return;
    }
    try {
      const result = await api<any>("/api/admin/update/trigger", { method: "POST" });
      toast(result.message || "Update started.", "ok");
    } catch (error: any) {
      toast(error.message, "err");
    }
  });

  document
    .getElementById("btn-poll-update-status")
    ?.addEventListener("click", async () => {
      try {
        const result = await api<any>("/api/admin/update/status");
        S.updateStatus = result;
        S.updateLog = result.log_lines || [];
        render();
      } catch (error: any) {
        toast(error.message, "err");
      }
    });
}

async function doSend(): Promise<void> {
  const textarea = document.getElementById("chat-textarea") as HTMLTextAreaElement | null;
  if (!textarea || !S.auth || S.busy) {
    return;
  }
  const message = textarea.value.trim();
  if (!message && !S.attachments.length) {
    return;
  }
  textarea.value = "";
  textarea.style.height = "auto";
  pushMsg("user", message || "(attachment)");
  S.busy = true;
  render();
  try {
    const response = await api<any>("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        session_id: S.sessionId,
        message: message || "Please review the attached file.",
        model_type: S.modelType,
        model_name: S.modelName || undefined,
        memory_mode: S.memoryMode,
        use_web_search: S.useWebSearch,
        enable_browser_tools: S.enableBrowserTools,
        enable_terminal_tools: S.enableTerminalTools,
        attachments: S.attachments,
      }),
    });
    pushMsg("assistant", response.response || response.message || "No response.");
    S.attachments = [];
    void loadTabData("history");
  } catch (error: any) {
    pushMsg("assistant", `Error: ${error.message || "Chat request failed"}`);
    // Re-enable send button within 1 second per requirement 12.6
    setTimeout(() => {
      S.busy = false;
      render();
    }, Math.min(1000, 500));
    return;
  } finally {
    S.busy = false;
    render();
  }
}

setThemeAccent(S.themeAccent);
render();
void checkServer();
void loadDesktopRelease();
if (S.auth) {
  void loadTabData(S.tab);
}
