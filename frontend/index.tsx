import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";

type AuthResponse = {
  token?: string;
  role?: string;
  username?: string;
  detail?: string;
};

const styles: Record<string, React.CSSProperties> = {
  root: {
    margin: 0,
    fontFamily: "Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
    background: "radial-gradient(circle at top, #1e1b4b 0%, #020617 55%)",
    color: "#e2e8f0",
    minHeight: "100vh",
    display: "grid",
    placeItems: "center",
    padding: 20,
  },
  card: {
    width: "100%",
    maxWidth: 460,
    background: "rgba(15,23,42,.9)",
    border: "1px solid rgba(148,163,184,.22)",
    borderRadius: 14,
    padding: 20,
    boxShadow: "0 24px 60px rgba(0,0,0,.45)",
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
  row: { display: "flex", gap: 10, marginTop: 14 },
  btnPrimary: { flex: 1, padding: 10, border: 0, borderRadius: 8, background: "#4f46e5", color: "#fff", fontWeight: 600 },
  btnSecondary: { flex: 1, padding: 10, border: 0, borderRadius: 8, background: "#059669", color: "#fff", fontWeight: 600 },
  btnGhost: { flex: 1, padding: 10, border: 0, borderRadius: 8, background: "#334155", color: "#fff", fontWeight: 600 },
  error: { marginTop: 12, color: "#fda4af" },
  ok: { marginTop: 12, color: "#86efac" },
};

export default function IndexPage() {
  const [username, setUsername] = useState(localStorage.getItem("ampai_username") || "");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const token = localStorage.getItem("ampai_token") || "";
  const role = localStorage.getItem("ampai_role") || "user";
  const loggedIn = !!token;

  const statusText = useMemo(
    () => (loggedIn ? `Logged in as ${username || "user"} (${role})` : "Not logged in"),
    [loggedIn, role, username],
  );

  async function callAuth(path: string, body: Record<string, string>) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const raw = await res.text();
    let data: AuthResponse = {};
    try {
      data = JSON.parse(raw);
    } catch {
      data = { detail: raw };
    }
    if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
    return data;
  }

  async function onLogin() {
    setBusy(true);
    setError("");
    setOk("");
    try {
      const data = await callAuth("/api/auth/login", { username: username.trim(), password });
      localStorage.setItem("ampai_token", data.token || "");
      localStorage.setItem("ampai_role", data.role || "user");
      localStorage.setItem("ampai_username", data.username || username.trim());
      setOk("Login successful.");
      setPassword("");
      window.location.hash = "#/chat";
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  async function onRegister() {
    setBusy(true);
    setError("");
    setOk("");
    try {
      await callAuth("/api/auth/register", { username: username.trim(), password });
      setOk("Registration successful. You can log in now.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  function onLogout() {
    localStorage.removeItem("ampai_token");
    localStorage.removeItem("ampai_role");
    localStorage.removeItem("ampai_username");
    setOk("Logged out.");
    setError("");
    window.location.hash = "#/login";
  }

  return (
    <div style={styles.root}>
      <div style={styles.card}>
        <h1>AmpAI React Login</h1>
        <p>{statusText}</p>

        <label>Username</label>
        <input style={styles.input} value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />

        <label style={{ marginTop: 10, display: "block" }}>Password</label>
        <input
          style={styles.input}
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete={loggedIn ? "off" : "current-password"}
        />

        <div style={styles.row}>
          <button style={styles.btnPrimary} onClick={onLogin} disabled={busy} type="button">{busy ? "Working..." : "Login"}</button>
          <button style={styles.btnSecondary} onClick={onRegister} disabled={busy} type="button">{busy ? "Working..." : "Register"}</button>
        </div>

        {loggedIn && (
          <div style={styles.row}>
            <button style={styles.btnGhost} onClick={onLogout} type="button">Logout</button>
          </div>
        )}

        {error && <div style={styles.error}>{error}</div>}
        {ok && <div style={styles.ok}>{ok}</div>}

        <p style={{ marginTop: 16 }}>
          Default admin: <code>admin</code> / <code>P@ssw0rd</code>
        </p>
      </div>
    </div>
  );
}


const rootEl = document.getElementById("root");
if (rootEl) {
  createRoot(rootEl).render(<IndexPage />);
}
