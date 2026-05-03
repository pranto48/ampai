import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
const styles = {
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
const parseHashRoute = () => {
    const raw = (window.location.hash || "#/login").replace(/^#\/?/, "").trim();
    if (["login", "dashboard", "chat", "models", "admin"].includes(raw))
        return raw;
    return "login";
};
const setRoute = (route) => {
    window.location.hash = `#/${route}`;
};
async function authFetch(path, options = {}) {
    const token = localStorage.getItem("ampai_token") || "";
    const headers = { ...(options.headers || {}) };
    if (token)
        headers.Authorization = `Bearer ${token}`;
    return fetch(path, { ...options, headers });
}
async function decodeResponse(res) {
    const raw = await res.text();
    try {
        return JSON.parse(raw);
    }
    catch {
        return { detail: raw };
    }
}
function Nav({ role, logout }) {
    return (_jsx("div", { style: { ...styles.card, position: "sticky", top: 10, zIndex: 2 }, children: _jsxs("div", { style: styles.row, children: [_jsx("button", { style: { ...styles.btn, ...styles.s }, onClick: () => setRoute("dashboard"), type: "button", children: "Dashboard" }), _jsx("button", { style: { ...styles.btn, ...styles.p }, onClick: () => setRoute("chat"), type: "button", children: "Chat" }), _jsx("button", { style: { ...styles.btn, ...styles.s }, onClick: () => setRoute("models"), type: "button", children: "AI Model Connection" }), role === "admin" && _jsx("button", { style: { ...styles.btn, ...styles.g }, onClick: () => setRoute("admin"), type: "button", children: "Admin Panel" }), _jsx("button", { style: { ...styles.btn, ...styles.s, marginLeft: "auto" }, onClick: logout, type: "button", children: "Logout" })] }) }));
}
function App() {
    const [route, setLocalRoute] = useState(parseHashRoute());
    const [username, setUsername] = useState(localStorage.getItem("ampai_username") || "");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [ok, setOk] = useState("");
    const [chatInput, setChatInput] = useState("");
    const [chatMessages, setChatMessages] = useState([]);
    const [busy, setBusy] = useState(false);
    const [me, setMe] = useState(null);
    const [adminUsers, setAdminUsers] = useState([]);
    const [newUser, setNewUser] = useState({ username: "", password: "", role: "user" });
    const [modelOptions, setModelOptions] = useState({ providers: [], models: {} });
    const loggedIn = !!localStorage.getItem("ampai_token");
    const role = localStorage.getItem("ampai_role") || "user";
    const sessionId = useMemo(() => {
        const existing = localStorage.getItem("ampai_session_id");
        if (existing)
            return existing;
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
            if (!loggedIn)
                return;
            const who = await authFetch("/api/auth/whoami");
            if (who.ok) {
                const info = await decodeResponse(who);
                setMe(info);
                localStorage.setItem("ampai_username", info.username);
                localStorage.setItem("ampai_role", info.role);
            }
        })();
    }, [loggedIn]);
    useEffect(() => {
        if (loggedIn && route === "login")
            setRoute("chat");
        if (!loggedIn && route !== "login")
            setRoute("login");
    }, [loggedIn, route]);
    async function callAuth(path, body) {
        const res = await fetch(path, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const data = await decodeResponse(res);
        if (!res.ok)
            throw new Error(data.detail || `Request failed (${res.status})`);
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
            setPassword("");
            setOk("Login successful. Redirecting to chat...");
            setRoute("chat");
            setLocalRoute("chat");
        }
        catch (e) {
            setError(e instanceof Error ? e.message : "Login failed");
        }
        finally {
            setBusy(false);
        }
    }
    async function onRegister() {
        setBusy(true);
        setError("");
        setOk("");
        try {
            await callAuth("/api/auth/register", { username: username.trim(), password });
            setOk("Registration successful. You can login now.");
        }
        catch (e) {
            setError(e instanceof Error ? e.message : "Registration failed");
        }
        finally {
            setBusy(false);
        }
    }
    async function sendChat() {
        const message = chatInput.trim();
        if (!message)
            return;
        setChatInput("");
        setChatMessages((prev) => [...prev, { role: "user", text: message }]);
        const res = await authFetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId, message, model_type: "ollama", memory_mode: "full", use_web_search: false, attachments: [] }),
        });
        const data = await decodeResponse(res);
        if (!res.ok) {
            setChatMessages((prev) => [...prev, { role: "assistant", text: `Error: ${data.detail || "chat failed"}` }]);
            return;
        }
        setChatMessages((prev) => [...prev, { role: "assistant", text: String(data.response || data.reply || data.message || "No response") }]);
    }
    async function loadAdminUsers() {
        const res = await authFetch("/api/admin/users");
        const data = await decodeResponse(res);
        if (res.ok)
            setAdminUsers(data.users || []);
        else
            setError(data.detail || "Failed to load users");
    }
    async function createAdminUser() {
        const res = await authFetch("/api/admin/users", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(newUser),
        });
        const data = await decodeResponse(res);
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
        const data = await decodeResponse(res);
        if (res.ok)
            setModelOptions(data);
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
        if (!loggedIn)
            return;
        if (route === "admin" && role === "admin")
            loadAdminUsers();
        if (route === "models")
            loadModels();
    }, [route, role, loggedIn]);
    if (!loggedIn || route === "login") {
        return (_jsx("div", { style: styles.root, children: _jsx("div", { style: styles.container, children: _jsxs("div", { style: styles.card, children: [_jsx("h1", { children: "AmpAI Login" }), _jsxs("p", { children: ["Default admin: ", _jsx("code", { children: "admin" }), " / ", _jsx("code", { children: "P@ssw0rd" }), " (legacy ", _jsx("code", { children: "admin123" }), " also accepted)."] }), _jsx("label", { children: "Username" }), _jsx("input", { style: styles.input, value: username, onChange: (e) => setUsername(e.target.value), autoComplete: "username" }), _jsx("label", { style: { marginTop: 8, display: "block" }, children: "Password" }), _jsx("input", { style: styles.input, type: "password", value: password, onChange: (e) => setPassword(e.target.value), autoComplete: "current-password" }), _jsxs("div", { style: styles.row, children: [_jsx("button", { style: { ...styles.btn, ...styles.p }, onClick: onLogin, disabled: busy, type: "button", children: busy ? "Working..." : "Login" }), _jsx("button", { style: { ...styles.btn, ...styles.g }, onClick: onRegister, disabled: busy, type: "button", children: busy ? "Working..." : "Register" })] }), error && _jsx("p", { style: { color: "#fda4af" }, children: error }), ok && _jsx("p", { style: { color: "#86efac" }, children: ok })] }) }) }));
    }
    return (_jsx("div", { style: styles.root, children: _jsxs("div", { style: styles.container, children: [_jsx(Nav, { role: role, logout: logout }), route === "dashboard" && (_jsxs("div", { style: styles.card, children: [_jsx("h2", { children: "Dashboard" }), _jsxs("p", { children: ["Welcome, ", (me?.username || localStorage.getItem("ampai_username") || "user"), " (", role, ")."] }), _jsxs("ul", { children: [_jsxs("li", { children: ["Chat route active: ", _jsx("code", { children: "#/chat" })] }), _jsxs("li", { children: ["AI model connection page: ", _jsx("code", { children: "#/models" })] }), _jsxs("li", { children: ["Admin panel: ", _jsx("code", { children: "#/admin" }), " (admin only)"] })] })] })), route === "chat" && (_jsxs("div", { style: styles.card, children: [_jsx("h2", { children: "AmpAI Chat" }), _jsx("p", { children: "Your login is valid and chat route is active." }), _jsxs("div", { style: { maxHeight: 280, overflowY: "auto", border: "1px solid #334155", borderRadius: 8, padding: 10, marginBottom: 10 }, children: [chatMessages.length === 0 && _jsx("p", { style: { margin: 0 }, children: "Start chatting with your assistant." }), chatMessages.map((m, i) => _jsxs("p", { children: [_jsxs("strong", { children: [m.role === "user" ? "You" : "AI", ":"] }), " ", m.text] }, i))] }), _jsx("input", { style: styles.input, placeholder: "Type a message...", value: chatInput, onChange: (e) => setChatInput(e.target.value), onKeyDown: (e) => e.key === "Enter" && sendChat() }), _jsx("div", { style: styles.row, children: _jsx("button", { style: { ...styles.btn, ...styles.p }, onClick: sendChat, type: "button", children: "Send" }) })] })), route === "models" && (_jsxs("div", { style: styles.card, children: [_jsx("h2", { children: "AI Model Connection" }), _jsx("p", { children: "Connected providers and model options from backend." }), _jsx("ul", { children: (modelOptions.providers || []).map((p) => _jsxs("li", { children: [_jsx("strong", { children: p.label }), ": ", (modelOptions.models?.[p.value] || []).join(", ") || "No models configured"] }, p.value)) })] })), route === "admin" && (_jsxs("div", { style: styles.card, children: [_jsx("h2", { children: "Admin Panel" }), role !== "admin" ? (_jsx("p", { style: { color: "#fda4af" }, children: "Admin access required." })) : (_jsxs(_Fragment, { children: [_jsx("p", { children: "Create admin/user accounts and review users." }), _jsxs("div", { style: styles.row, children: [_jsx("input", { style: styles.input, placeholder: "username", value: newUser.username, onChange: (e) => setNewUser((p) => ({ ...p, username: e.target.value })) }), _jsx("input", { style: styles.input, type: "password", placeholder: "password", value: newUser.password, onChange: (e) => setNewUser((p) => ({ ...p, password: e.target.value })) }), _jsxs("select", { style: styles.input, value: newUser.role, onChange: (e) => setNewUser((p) => ({ ...p, role: e.target.value })), children: [_jsx("option", { value: "user", children: "user" }), _jsx("option", { value: "admin", children: "admin" })] }), _jsx("button", { style: { ...styles.btn, ...styles.g }, onClick: createAdminUser, type: "button", children: "Create User" })] }), _jsxs("table", { style: { width: "100%", marginTop: 12 }, children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { align: "left", children: "Username" }), _jsx("th", { align: "left", children: "Role" })] }) }), _jsx("tbody", { children: adminUsers.map((u) => _jsxs("tr", { children: [_jsx("td", { children: u.username }), _jsx("td", { children: u.role })] }, u.username)) })] })] }))] })), error && _jsx("div", { style: styles.card, children: _jsx("p", { style: { color: "#fda4af", margin: 0 }, children: error }) }), ok && _jsx("div", { style: styles.card, children: _jsx("p", { style: { color: "#86efac", margin: 0 }, children: ok }) })] }) }));
}
const rootEl = document.getElementById("root");
if (rootEl)
    createRoot(rootEl).render(_jsx(App, {}));
