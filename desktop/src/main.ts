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
      ${tabButton("server", "Server")}
      ${tabButton("account", "Account")}
      ${S.auth ? tabButton("history", "History") : ""}
      ${S.auth ? tabButton("memory", "Memory") : ""}
      ${S.auth ? tabButton("personas", "AI Personas") : ""}
      ${S.auth ? tabButton("settings", "Settings") : ""}
      ${S.auth ? tabButton("personalise", "Personalise") : ""}
      ${isAdmin() ? tabButton("admin", "Admin") : ""}
      ${isAdmin() ? tabButton("update", "Update") : ""}
    </div>
    <div class="tab-panels">
      ${tabPanel("server", serverTab())}
      ${tabPanel("account", accountTab())}
      ${S.auth ? tabPanel("history", historyTab()) : ""}
      ${S.auth ? tabPanel("memory", memoryTab()) : ""}
      ${S.auth ? tabPanel("personas", personasTab()) : ""}
      ${S.auth ? tabPanel("settings", settingsTab()) : ""}
      ${S.auth ? tabPanel("personalise", personaliseTab()) : ""}
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
      const data = await api<any>("/api/sessions?limit=100&archived=false");
      S.sessions = data.sessions || [];
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
    if (tab === "personas") {
      const data = await api<any>("/api/personas");
      S.personas = data.personas || [];
    }
    if (tab === "settings" && isAdmin()) {
      const [configs, telegram, modelOptions] = await Promise.all([
        api<any>("/api/admin/configs"),
        isAdmin()
          ? api<any>("/api/admin/integrations/telegram/status")
          : Promise.resolve(null),
        api<any>("/api/models/options"),
      ]);
      S.configs = configs || {};
      S.tgStatus = telegram;
      S.providers = modelOptions.providers || [];
      S.modelType = S.configs.default_model_provider || S.modelType;
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
    void loadTabData("history");
  });
  document.getElementById("session-search")?.addEventListener("input", (event) => {
    S.sessionSearch = (event.currentTarget as HTMLInputElement).value;
    render();
  });
  document.querySelectorAll<HTMLElement>("[data-cat]").forEach((chip) => {
    chip.addEventListener("click", () => {
      S.sessionCategoryFilter = chip.dataset.cat || "";
      render();
    });
  });
  document.querySelectorAll<HTMLElement>(".session-item[data-sid]").forEach((row) => {
    row.addEventListener("click", async (event) => {
      const target = event.target as HTMLElement;
      if (target.closest("[data-del-sid]")) {
        return;
      }
      const sessionId = row.dataset.sid || "";
      if (!sessionId) {
        return;
      }
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
  document.querySelectorAll<HTMLButtonElement>("[data-del-sid]").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      const sessionId = button.dataset.delSid || "";
      if (!sessionId || !confirm("Delete this chat session?")) {
        return;
      }
      try {
        await api(`/api/sessions/${encodeURIComponent(sessionId)}`, {
          method: "DELETE",
        });
        S.sessions = S.sessions.filter((item) => item.session_id !== sessionId);
        if (S.sessionId === sessionId) {
          newSessionId();
          S.msgs = [];
        }
        toast("Session deleted.", "info");
        render();
      } catch (error: any) {
        toast(error.message, "err");
      }
    });
  });
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
      await loadTabData("settings");
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
        memory_mode: S.memoryMode,
        use_web_search: S.useWebSearch,
        attachments: S.attachments,
      }),
    });
    pushMsg("assistant", response.response || response.message || "No response.");
    S.attachments = [];
    void loadTabData("history");
  } catch (error: any) {
    pushMsg("assistant", `Error: ${error.message || "Chat failed"}`);
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
