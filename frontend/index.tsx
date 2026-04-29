import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";

type Role = "admin" | "user";
type Route = "login" | "dashboard" | "chat" | "models" | "admin";

type AuthResponse = {
  token?: string;
  role?: Role;
  username?: string;
  detail?: string;
};

type WhoAmI = {
  username: string;
  role: Role;
};

type AdminUser = {
  username: string;
  role: Role;
};

type ModelOptions = {
  providers?: Array<{ value: string; label: string }>;
  models?: Record<string, string[]>;
};

const styles: Record<string, React.CSSProperties> = {
  root: {
    margin: 0,
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
    background: "radial-gradient(circle at top, #1e1b4b 0%, #020617 55%)",
    color: "#e2e8f0",
    minHeight: "100vh",
    padding: 20,
  },
  container: { maxWidth: 980, margin: "0 auto" },
  card: {
    border: "1px solid rgba(148,163,184,.22)",
    borderRadius: 12,
    background: "rgba(15,23,42,.9)",
    padding: 18,
    marginBottom: 14,
  },
  input: {
    width: "100%",
    boxSizing: "border-box",
    padding: 10,
    borderRadius: 8,
    border: "1px solid #334155",
    background: "#020617",
    color: "#f8fafc",
    marginTop: 6,
  },
  row: { display: "flex", gap: 10, marginTop: 10, flexWrap: "wrap" },
  btn: { padding: "10px 12px", border: 0, borderRadius: 8, color: "#fff", fontWeight: 600, cursor: "pointer" },
  p: { background: "#4f46e5" },
  s: { background: "#334155" },
  g: { background: "#059669" },
};

const parseHashRoute = (): Route => {
  const raw = (window.location.hash || "#/login").replace(/^#\/?/, "").trim();
  if (["login", "dashboard", "chat", "models", "admin"].includes(raw)) return raw as Route;
  return "login";
};

const setRoute = (route: Route) => {
  window.location.hash = `#/${route}`;
};

async function authFetch(path: string, options: RequestInit = {}) {
  const token = localStorage.getItem("ampai_token") || "";
  const headers: Record<string, string> = { ...(options.headers as Record<string, string> || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  return fetch(path, { ...options, headers });
}

async function decodeResponse<T>(res: Response): Promise<T> {
  const raw = await res.text();
  try {
    return JSON.parse(raw) as T;
  } catch {
    return { detail: raw } as T;
  }
}

function Nav({ role, logout }: { role: string; logout: () => void }) {
  return (
    <div style={{ ...styles.card, position: "sticky", top: 10, zIndex: 2 }}>
      <div style={styles.row}>
        <button style={{ ...styles.btn, ...styles.s }} onClick={() => setRoute("dashboard")} type="button">Dashboard</button>
        <button style={{ ...styles.btn, ...styles.p }} onClick={() => setRoute("chat")} type="button">Chat</button>
        <button style={{ ...styles.btn, ...styles.s }} onClick={() => setRoute("models")} type="button">AI Model Connection</button>
        {role === "admin" && <button style={{ ...styles.btn, ...styles.g }} onClick={() => setRoute("admin")} type="button">Admin Panel</button>}
        <button style={{ ...styles.btn, ...styles.s, marginLeft: "auto" }} onClick={logout} type="button">Logout</button>
      </div>
    </div>
  );
}

function App() {
  const [route, setLocalRoute] = useState<Route>(parseHashRoute());
  const [username, setUsername] = useState(localStorage.getItem("ampai_username") || "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<Array<{ role: string; text: string }>>([]);
  const [busy, setBusy] = useState(false);
  const [me, setMe] = useState<WhoAmI | null>(null);
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
  const [newUser, setNewUser] = useState({ username: "", password: "", role: "user" as Role });
  const [modelOptions, setModelOptions] = useState<ModelOptions>({ providers: [], models: {} });

  const loggedIn = !!localStorage.getItem("ampai_token");
  const role = (localStorage.getItem("ampai_role") as Role) || "user";
  const sessionId = useMemo(() => {
    const existing = localStorage.getItem("ampai_session_id");
    if (existing) return existing;
    const generated = `sess_${Date.now()}`;
    localStorage.setItem("ampai_session_id", generated);
    return generated;
  }, []);

  useEffect(() => {
    const onHash = () => setLocalRoute(parseHashRoute());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    (async () => {
      if (!loggedIn) return;
      const who = await authFetch("/api/auth/whoami");
      if (who.ok) {
        const info = await decodeResponse<WhoAmI>(who);
        setMe(info);
        localStorage.setItem("ampai_username", info.username);
        localStorage.setItem("ampai_role", info.role);
      }
    })();
  }, [loggedIn]);

  useEffect(() => {
    if (loggedIn && route === "login") setRoute("chat");
    if (!loggedIn && route !== "login") setRoute("login");
  }, [loggedIn, route]);

  async function callAuth(path: string, body: Record<string, string>) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await decodeResponse<AuthResponse>(res);
    if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
    return data;
  }

  async function onLogin() {
    setBusy(true); setError(""); setOk("");
    try {
      const data = await callAuth("/api/auth/login", { username: username.trim(), password });
      localStorage.setItem("ampai_token", data.token || "");
      localStorage.setItem("ampai_role", data.role || "user");
      localStorage.setItem("ampai_username", data.username || username.trim());
      setPassword("");
      setOk("Login successful. Redirecting to chat...");
      setRoute("chat");
      setLocalRoute("chat");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed");
    } finally { setBusy(false); }
  }

  async function onRegister() {
    setBusy(true); setError(""); setOk("");
    try {
      await callAuth("/api/auth/register", { username: username.trim(), password });
      setOk("Registration successful. You can login now.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Registration failed");
    } finally { setBusy(false); }
  }

  async function sendChat() {
    const message = chatInput.trim();
    if (!message) return;
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", text: message }]);
    const res = await authFetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message, memory_mode: "full", use_web_search: false, attachments: [] }),
    });
    const data = await decodeResponse<any>(res);
    if (!res.ok) {
      setChatMessages((prev) => [...prev, { role: "assistant", text: `Error: ${data.detail || "chat failed"}` }]);
      return;
    }
    setChatMessages((prev) => [...prev, { role: "assistant", text: String(data.response || data.reply || data.message || "No response") }]);
  }

  async function loadAdminUsers() {
    const res = await authFetch("/api/admin/users");
    const data = await decodeResponse<{ users?: AdminUser[]; detail?: string }>(res);
    if (res.ok) setAdminUsers(data.users || []);
    else setError(data.detail || "Failed to load users");
  }

  async function createAdminUser() {
    const res = await authFetch("/api/admin/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newUser),
    });
    const data = await decodeResponse<{ detail?: string }>(res);
    if (!res.ok) {
      setError(data.detail || "Failed creating user");
      return;
    }
    setOk(`Created user ${newUser.username}.`);
    setNewUser({ username: "", password: "", role: "user" });
    loadAdminUsers();
  }

  async function loadModels() {
    const res = await authFetch("/api/models/options");
    const data = await decodeResponse<ModelOptions>(res);
    if (res.ok) setModelOptions(data);
  }

  function logout() {
    localStorage.removeItem("ampai_token");
    localStorage.removeItem("ampai_role");
    localStorage.removeItem("ampai_username");
    setMe(null);
    setRoute("login");
    setLocalRoute("login");
    setOk("Logged out.");
  }

  useEffect(() => {
    if (!loggedIn) return;
    if (route === "admin" && role === "admin") loadAdminUsers();
    if (route === "models") loadModels();
  }, [route, role, loggedIn]);

  if (!loggedIn || route === "login") {
    return (
      <div style={styles.root}><div style={styles.container}><div style={styles.card}>
        <h1>AmpAI Login</h1>
        <p>Default admin: <code>admin</code> / <code>P@ssw0rd</code> (legacy <code>admin123</code> also accepted).</p>
        <label>Username</label>
        <input style={styles.input} value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
        <label style={{ marginTop: 8, display: "block" }}>Password</label>
        <input style={styles.input} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
        <div style={styles.row}>
          <button style={{ ...styles.btn, ...styles.p }} onClick={onLogin} disabled={busy} type="button">{busy ? "Working..." : "Login"}</button>
          <button style={{ ...styles.btn, ...styles.g }} onClick={onRegister} disabled={busy} type="button">{busy ? "Working..." : "Register"}</button>
        </div>
        {error && <p style={{ color: "#fda4af" }}>{error}</p>}
        {ok && <p style={{ color: "#86efac" }}>{ok}</p>}
      </div></div></div>
    );
  }

  return (
    <div style={styles.root}>
      <div style={styles.container}>
        <Nav role={role} logout={logout} />

        {route === "dashboard" && (
          <div style={styles.card}>
            <h2>Dashboard</h2>
            <p>Welcome, {(me?.username || localStorage.getItem("ampai_username") || "user")} ({role}).</p>
            <ul>
              <li>Chat route active: <code>#/chat</code></li>
              <li>AI model connection page: <code>#/models</code></li>
              <li>Admin panel: <code>#/admin</code> (admin only)</li>
            </ul>
          </div>
        )}

        {route === "chat" && (
          <div style={styles.card}>
            <h2>AmpAI Chat</h2>
            <p>Your login is valid and chat route is active.</p>
            <div style={{ maxHeight: 280, overflowY: "auto", border: "1px solid #334155", borderRadius: 8, padding: 10, marginBottom: 10 }}>
              {chatMessages.length === 0 && <p style={{ margin: 0 }}>Start chatting with your assistant.</p>}
              {chatMessages.map((m, i) => <p key={i}><strong>{m.role === "user" ? "You" : "AI"}:</strong> {m.text}</p>)}
            </div>
            <input style={styles.input} placeholder="Type a message..." value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && sendChat()} />
            <div style={styles.row}><button style={{ ...styles.btn, ...styles.p }} onClick={sendChat} type="button">Send</button></div>
          </div>
        )}

        {route === "models" && (
          <div style={styles.card}>
            <h2>AI Model Connection</h2>
            <p>Connected providers and model options from backend.</p>
            <ul>
              {(modelOptions.providers || []).map((p) => <li key={p.value}><strong>{p.label}</strong>: {(modelOptions.models?.[p.value] || []).join(", ") || "No models configured"}</li>)}
            </ul>
          </div>
        )}

        {route === "admin" && (
          <div style={styles.card}>
            <h2>Admin Panel</h2>
            {role !== "admin" ? (
              <p style={{ color: "#fda4af" }}>Admin access required.</p>
            ) : (
              <>
                <p>Create admin/user accounts and review users.</p>
                <div style={styles.row}>
                  <input style={styles.input} placeholder="username" value={newUser.username} onChange={(e) => setNewUser((p) => ({ ...p, username: e.target.value }))} />
                  <input style={styles.input} type="password" placeholder="password" value={newUser.password} onChange={(e) => setNewUser((p) => ({ ...p, password: e.target.value }))} />
                  <select style={styles.input} value={newUser.role} onChange={(e) => setNewUser((p) => ({ ...p, role: e.target.value as Role }))}>
                    <option value="user">user</option><option value="admin">admin</option>
                  </select>
                  <button style={{ ...styles.btn, ...styles.g }} onClick={createAdminUser} type="button">Create User</button>
                </div>
                <table style={{ width: "100%", marginTop: 12 }}>
                  <thead><tr><th align="left">Username</th><th align="left">Role</th></tr></thead>
                  <tbody>{adminUsers.map((u) => <tr key={u.username}><td>{u.username}</td><td>{u.role}</td></tr>)}</tbody>
                </table>
              </>
            )}
          </div>
        )}

        {error && <div style={styles.card}><p style={{ color: "#fda4af", margin: 0 }}>{error}</p></div>}
        {ok && <div style={styles.card}><p style={{ color: "#86efac", margin: 0 }}>{ok}</p></div>}
      </div>
    </div>
  );
}

const rootEl = document.getElementById("root");
if (rootEl) createRoot(rootEl).render(<App />);
