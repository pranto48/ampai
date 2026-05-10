import "./styles.css";

type HealthState = {
  ok: boolean;
  status: string;
  detail: string;
  checkedAt?: string;
};

type LoginState = {
  username: string;
  role: string;
  token: string;
};

type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
  time: string;
};

const DEFAULT_SERVER_URL = "http://127.0.0.1:8000";
const SERVER_KEY = "ampai.serverUrl";
const AUTH_KEY = "ampai.auth";
const SESSION_KEY = "ampai.sessionId";

const state = {
  serverUrl: normalizeServerUrl(localStorage.getItem(SERVER_KEY) || DEFAULT_SERVER_URL),
  health: {
    ok: false,
    status: "offline",
    detail: "Server not checked",
  } as HealthState,
  auth: readAuth(),
  sessionId: localStorage.getItem(SESSION_KEY) || createSessionId(),
  messages: [] as ChatMessage[],
  busy: false,
};

function normalizeServerUrl(value: string): string {
  const trimmed = value.trim().replace(/\/+$/, "");
  return trimmed || DEFAULT_SERVER_URL;
}

function escapeAttribute(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function createSessionId(): string {
  const id =
    globalThis.crypto?.randomUUID?.() ||
    `desktop-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  localStorage.setItem(SESSION_KEY, id);
  return id;
}

function readAuth(): LoginState | null {
  const raw = localStorage.getItem(AUTH_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as LoginState;
    if (parsed?.token && parsed?.username) return parsed;
  } catch {
    localStorage.removeItem(AUTH_KEY);
  }
  return null;
}

function writeAuth(auth: LoginState | null) {
  state.auth = auth;
  if (auth) {
    localStorage.setItem(AUTH_KEY, JSON.stringify(auth));
  } else {
    localStorage.removeItem(AUTH_KEY);
  }
  render();
}

function apiHeaders(extra?: HeadersInit): Headers {
  const headers = new Headers(extra);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (state.auth?.token) headers.set("Authorization", `Bearer ${state.auth.token}`);
  return headers;
}

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${state.serverUrl}${path}`, {
    ...init,
    headers: apiHeaders(init.headers),
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const detail = payload?.detail || payload?.message || response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload as T;
}

function setBusy(nextBusy: boolean) {
  state.busy = nextBusy;
  render();
}

async function checkServer() {
  const started = performance.now();
  try {
    const response = await fetch(`${state.serverUrl}/healthz`, {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = (await response.json()) as { status?: string; time?: string };
    const latency = Math.round(performance.now() - started);
    state.health = {
      ok: data.status === "ok",
      status: data.status || "unknown",
      detail: `Connected in ${latency} ms`,
      checkedAt: data.time,
    };
  } catch (error) {
    state.health = {
      ok: false,
      status: "offline",
      detail: error instanceof Error ? error.message : "Unable to reach server",
    };
  }
  render();
}

async function saveServerUrl(form: HTMLFormElement) {
  const formData = new FormData(form);
  state.serverUrl = normalizeServerUrl(String(formData.get("serverUrl") || ""));
  localStorage.setItem(SERVER_KEY, state.serverUrl);
  state.health = { ok: false, status: "pending", detail: "Server URL saved" };
  render();
  await checkServer();
}

async function login(form: HTMLFormElement) {
  const formData = new FormData(form);
  setBusy(true);
  try {
    const result = await apiFetch<LoginState>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: String(formData.get("username") || ""),
        password: String(formData.get("password") || ""),
        remember_me: true,
      }),
    });
    writeAuth(result);
    state.messages.unshift({
      role: "system",
      content: `Signed in as ${result.username}`,
      time: new Date().toLocaleTimeString(),
    });
  } catch (error) {
    state.messages.unshift({
      role: "system",
      content: error instanceof Error ? error.message : "Login failed",
      time: new Date().toLocaleTimeString(),
    });
  } finally {
    setBusy(false);
  }
}

async function sendChat(form: HTMLFormElement) {
  const formData = new FormData(form);
  const message = String(formData.get("message") || "").trim();
  if (!message || !state.auth) return;

  state.messages.push({
    role: "user",
    content: message,
    time: new Date().toLocaleTimeString(),
  });
  form.reset();
  setBusy(true);

  try {
    const result = await apiFetch<{
      response?: string;
      model_used?: string;
      ampai_default_mode?: boolean;
    }>("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        session_id: state.sessionId,
        message,
        model_type: "ollama",
        memory_mode: "indexed",
        memory_top_k: 5,
        use_web_search: false,
      }),
    });
    const model = result.model_used ? `\n\nModel: ${result.model_used}` : "";
    state.messages.push({
      role: "assistant",
      content: `${result.response || "No response returned."}${model}`,
      time: new Date().toLocaleTimeString(),
    });
  } catch (error) {
    state.messages.push({
      role: "system",
      content: error instanceof Error ? error.message : "Chat request failed",
      time: new Date().toLocaleTimeString(),
    });
  } finally {
    setBusy(false);
  }
}

function resetSession() {
  state.sessionId = createSessionId();
  state.messages = [];
  render();
}

function el<K extends keyof HTMLElementTagNameMap>(
  tagName: K,
  options: {
    className?: string;
    text?: string;
    attrs?: Record<string, string>;
  } = {},
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tagName);
  if (options.className) node.className = options.className;
  if (options.text !== undefined) node.textContent = options.text;
  for (const [key, value] of Object.entries(options.attrs || {})) {
    node.setAttribute(key, value);
  }
  return node;
}

function serverPanel(): HTMLElement {
  const panel = el("section", { className: "panel" });
  panel.append(
    el("div", { className: "panel-title", text: "Docker Server" }),
    statusRow(),
  );

  const form = el("form", { className: "stack", attrs: { id: "server-form" } });
  form.innerHTML = `
    <label class="field">
      <span>Server URL</span>
      <input name="serverUrl" value="${escapeAttribute(state.serverUrl)}" placeholder="${DEFAULT_SERVER_URL}" />
    </label>
    <div class="button-row">
      <button class="primary" type="submit">Save</button>
      <button type="button" id="test-server">Test</button>
    </div>
  `;
  panel.append(form);

  const command = el("div", { className: "command" });
  command.append(
    el("span", { text: "Run server" }),
    el("code", { text: "docker compose up --build" }),
  );
  panel.append(command);
  return panel;
}

function statusRow(): HTMLElement {
  const row = el("div", { className: "status-row" });
  const badge = el("span", {
    className: `badge ${state.health.ok ? "ok" : "bad"}`,
    text: state.health.ok ? "Online" : "Offline",
  });
  const detail = el("div", { className: "status-detail" });
  detail.append(
    el("strong", { text: state.health.status }),
    el("span", { text: state.health.detail }),
  );
  row.append(badge, detail);
  return row;
}

function authPanel(): HTMLElement {
  const panel = el("section", { className: "panel" });
  panel.append(el("div", { className: "panel-title", text: "Account" }));

  if (state.auth) {
    const account = el("div", { className: "account" });
    account.append(
      el("strong", { text: state.auth.username }),
      el("span", { text: state.auth.role }),
    );
    const logout = el("button", { text: "Logout", attrs: { id: "logout", type: "button" } });
    panel.append(account, logout);
    return panel;
  }

  const form = el("form", { className: "stack", attrs: { id: "login-form" } });
  form.innerHTML = `
    <label class="field">
      <span>Username</span>
      <input name="username" value="admin" autocomplete="username" />
    </label>
    <label class="field">
      <span>Password</span>
      <input name="password" type="password" value="P@ssw0rd" autocomplete="current-password" />
    </label>
    <button class="primary" type="submit" ${state.busy ? "disabled" : ""}>Login</button>
  `;
  panel.append(form);
  return panel;
}

function chatPanel(): HTMLElement {
  const panel = el("section", { className: "chat-shell" });
  const header = el("div", { className: "chat-header" });
  const title = el("div");
  title.append(
    el("h1", { text: "AmpAI" }),
    el("span", { text: `Session ${state.sessionId.slice(0, 8)}` }),
  );
  const reset = el("button", { text: "New Session", attrs: { id: "reset-session", type: "button" } });
  header.append(title, reset);

  const messages = el("div", { className: "messages" });
  if (state.messages.length === 0) {
    messages.append(el("div", { className: "empty", text: "Connect, login, and start chatting." }));
  } else {
    for (const message of state.messages) {
      const item = el("article", { className: `message ${message.role}` });
      item.append(
        el("div", { className: "message-meta", text: `${message.role} - ${message.time}` }),
        el("p", { text: message.content }),
      );
      messages.append(item);
    }
  }

  const form = el("form", { className: "composer", attrs: { id: "chat-form" } });
  form.innerHTML = `
    <textarea name="message" placeholder="${state.auth ? "Message AmpAI" : "Login required"}" ${state.auth ? "" : "disabled"}></textarea>
    <button class="primary" type="submit" ${state.auth && !state.busy ? "" : "disabled"}>${state.busy ? "Working" : "Send"}</button>
  `;

  panel.append(header, messages, form);
  return panel;
}

function render() {
  const app = document.querySelector<HTMLDivElement>("#app");
  if (!app) return;
  app.replaceChildren();

  const shell = el("main", { className: "layout" });
  const sidebar = el("aside", { className: "sidebar" });
  sidebar.append(serverPanel(), authPanel());
  shell.append(sidebar, chatPanel());
  app.append(shell);

  document.querySelector<HTMLFormElement>("#server-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    void saveServerUrl(event.currentTarget as HTMLFormElement);
  });
  document.querySelector<HTMLButtonElement>("#test-server")?.addEventListener("click", () => {
    void checkServer();
  });
  document.querySelector<HTMLFormElement>("#login-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    void login(event.currentTarget as HTMLFormElement);
  });
  document.querySelector<HTMLButtonElement>("#logout")?.addEventListener("click", () => {
    writeAuth(null);
  });
  document.querySelector<HTMLFormElement>("#chat-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    void sendChat(event.currentTarget as HTMLFormElement);
  });
  document.querySelector<HTMLButtonElement>("#reset-session")?.addEventListener("click", resetSession);
}

render();
void checkServer();
