import React, { useEffect, useMemo, useState } from 'https://esm.sh/react@18.3.1';
import { createRoot } from 'https://esm.sh/react-dom@18.3.1/client';

const styles = {
  root: { margin: 0, fontFamily: 'Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif', background: 'radial-gradient(circle at top, #1e1b4b 0%, #020617 55%)', color: '#e2e8f0', minHeight: '100vh', padding: 20 },
  container: { maxWidth: 980, margin: '0 auto' },
  card: { border: '1px solid rgba(148,163,184,.22)', borderRadius: 12, background: 'rgba(15,23,42,.9)', padding: 18, marginBottom: 14 },
  input: { width: '100%', boxSizing: 'border-box', padding: 10, borderRadius: 8, border: '1px solid #334155', background: '#020617', color: '#f8fafc', marginTop: 6 },
  row: { display: 'flex', gap: 10, marginTop: 10, flexWrap: 'wrap' },
  btn: { padding: '10px 12px', border: 0, borderRadius: 8, color: '#fff', fontWeight: 600, cursor: 'pointer' },
};

const parseHashRoute = () => {
  const raw = (window.location.hash || '#/login').replace(/^#\/?/, '').trim();
  return ['login', 'dashboard', 'chat', 'models', 'admin'].includes(raw) ? raw : 'login';
};
const setRoute = (route) => { window.location.hash = `#/${route}`; };

async function authFetch(path, options = {}) {
  const token = localStorage.getItem('ampai_token') || '';
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  return fetch(path, { ...options, headers });
}

async function decodeResponse(res) {
  const raw = await res.text();
  try { return JSON.parse(raw); } catch { return { detail: raw }; }
}

function App() {
  const [route, setLocalRoute] = useState(parseHashRoute());
  const [username, setUsername] = useState(localStorage.getItem('ampai_username') || '');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [ok, setOk] = useState('');
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [me, setMe] = useState(null);
  const [adminUsers, setAdminUsers] = useState([]);
  const [newUser, setNewUser] = useState({ username: '', password: '', role: 'user' });
  const [modelOptions, setModelOptions] = useState({ providers: [], models: {} });

  const loggedIn = !!localStorage.getItem('ampai_token');
  const role = localStorage.getItem('ampai_role') || 'user';
  const sessionId = useMemo(() => {
    const existing = localStorage.getItem('ampai_session_id');
    if (existing) return existing;
    const generated = `sess_${Date.now()}`;
    localStorage.setItem('ampai_session_id', generated);
    return generated;
  }, []);

  useEffect(() => {
    const onHash = () => setLocalRoute(parseHashRoute());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  useEffect(() => {
    (async () => {
      if (!loggedIn) return;
      const who = await authFetch('/api/auth/whoami');
      if (who.ok) {
        const info = await decodeResponse(who);
        setMe(info);
        localStorage.setItem('ampai_username', info.username || '');
        localStorage.setItem('ampai_role', info.role || 'user');
      }
    })();
  }, [loggedIn]);

  useEffect(() => {
    if (loggedIn && route === 'login') setRoute('chat');
    if (!loggedIn && route !== 'login') setRoute('login');
  }, [loggedIn, route]);

  useEffect(() => {
    if (!loggedIn) return;
    if (route === 'admin' && role === 'admin') loadAdminUsers();
    if (route === 'models') loadModels();
  }, [loggedIn, route, role]);

  async function callAuth(path, body) {
    const res = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const data = await decodeResponse(res);
    if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
    return data;
  }

  async function onLogin() {
    setBusy(true); setError(''); setOk('');
    try {
      const data = await callAuth('/api/auth/login', { username: username.trim(), password });
      localStorage.setItem('ampai_token', data.token || '');
      localStorage.setItem('ampai_role', data.role || 'user');
      localStorage.setItem('ampai_username', data.username || username.trim());
      setPassword(''); setOk('Login successful. Redirecting to chat...'); setRoute('chat'); setLocalRoute('chat');
    } catch (e) { setError(e.message || 'Login failed'); }
    finally { setBusy(false); }
  }

  async function onRegister() {
    setBusy(true); setError(''); setOk('');
    try { await callAuth('/api/auth/register', { username: username.trim(), password }); setOk('Registration successful. You can login now.'); }
    catch (e) { setError(e.message || 'Registration failed'); }
    finally { setBusy(false); }
  }

  async function sendChat() {
    const message = chatInput.trim();
    if (!message) return;
    setChatInput('');
    setChatMessages((prev) => [...prev, { role: 'user', text: message }]);
    const res = await authFetch('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message, model_type: 'ollama', memory_mode: 'full', use_web_search: false, attachments: [] }),
    });
    const data = await decodeResponse(res);
    if (!res.ok) {
      setChatMessages((prev) => [...prev, { role: 'assistant', text: `Error: ${data.detail || 'chat failed'}` }]);
      return;
    }
    setChatMessages((prev) => [...prev, { role: 'assistant', text: String(data.response || data.reply || data.message || 'No response') }]);
  }

  async function loadAdminUsers() {
    const res = await authFetch('/api/admin/users');
    const data = await decodeResponse(res);
    if (res.ok) setAdminUsers(data.users || []);
    else setError(data.detail || 'Failed to load users');
  }

  async function createAdminUser() {
    const res = await authFetch('/api/admin/users', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newUser),
    });
    const data = await decodeResponse(res);
    if (!res.ok) return setError(data.detail || 'Failed creating user');
    setOk(`Created user ${newUser.username}.`);
    setNewUser({ username: '', password: '', role: 'user' });
    loadAdminUsers();
  }

  async function loadModels() {
    const res = await authFetch('/api/models/options');
    const data = await decodeResponse(res);
    if (res.ok) setModelOptions(data);
  }

  function logout() {
    localStorage.removeItem('ampai_token'); localStorage.removeItem('ampai_role'); localStorage.removeItem('ampai_username');
    setMe(null); setRoute('login'); setLocalRoute('login'); setOk('Logged out.');
  }

  const nav = React.createElement('div', { style: { ...styles.card, position: 'sticky', top: 10, zIndex: 2 } },
    React.createElement('div', { style: styles.row },
      React.createElement('button', { style: { ...styles.btn, background: '#334155' }, onClick: () => setRoute('dashboard') }, 'Dashboard'),
      React.createElement('button', { style: { ...styles.btn, background: '#4f46e5' }, onClick: () => setRoute('chat') }, 'Chat'),
      React.createElement('button', { style: { ...styles.btn, background: '#334155' }, onClick: () => setRoute('models') }, 'AI Model Connection'),
      role === 'admin' ? React.createElement('button', { style: { ...styles.btn, background: '#059669' }, onClick: () => setRoute('admin') }, 'Admin Panel') : null,
      React.createElement('button', { style: { ...styles.btn, background: '#334155', marginLeft: 'auto' }, onClick: logout }, 'Logout'),
    )
  );

  if (!loggedIn || route === 'login') {
    return React.createElement('div', { style: styles.root }, React.createElement('div', { style: styles.container },
      React.createElement('div', { style: styles.card },
        React.createElement('h1', null, 'AmpAI Login'),
        React.createElement('p', null, 'Default admin: ', React.createElement('code', null, 'admin'), ' / ', React.createElement('code', null, 'P@ssw0rd'), '.'),
        React.createElement('label', null, 'Username'),
        React.createElement('input', { style: styles.input, value: username, onChange: (e) => setUsername(e.target.value), autoComplete: 'username' }),
        React.createElement('label', { style: { marginTop: 8, display: 'block' } }, 'Password'),
        React.createElement('input', { style: styles.input, type: 'password', value: password, onChange: (e) => setPassword(e.target.value), autoComplete: 'current-password' }),
        React.createElement('div', { style: styles.row },
          React.createElement('button', { style: { ...styles.btn, background: '#4f46e5' }, onClick: onLogin, disabled: busy }, busy ? 'Working...' : 'Login'),
          React.createElement('button', { style: { ...styles.btn, background: '#059669' }, onClick: onRegister, disabled: busy }, busy ? 'Working...' : 'Register'),
        ),
        error ? React.createElement('p', { style: { color: '#fda4af' } }, error) : null,
        ok ? React.createElement('p', { style: { color: '#86efac' } }, ok) : null,
      )
    ));
  }

  let page = null;
  if (route === 'dashboard') {
    page = React.createElement('div', { style: styles.card },
      React.createElement('h2', null, 'Dashboard'),
      React.createElement('p', null, `Welcome, ${(me?.username || localStorage.getItem('ampai_username') || 'user')} (${role}).`),
      React.createElement('ul', null,
        React.createElement('li', null, 'Chat route active: ', React.createElement('code', null, '#/chat')),
        React.createElement('li', null, 'AI model connection page: ', React.createElement('code', null, '#/models')),
        React.createElement('li', null, 'Admin panel: ', React.createElement('code', null, '#/admin'), ' (admin only)')),
    );
  } else if (route === 'chat') {
    page = React.createElement('div', { style: styles.card },
      React.createElement('h2', null, 'AmpAI Chat'),
      React.createElement('p', null, 'Your login is valid and chat route is active.'),
      React.createElement('div', { style: { maxHeight: 280, overflowY: 'auto', border: '1px solid #334155', borderRadius: 8, padding: 10, marginBottom: 10 } },
        chatMessages.length === 0 ? React.createElement('p', { style: { margin: 0 } }, 'Start chatting with your assistant.') : null,
        ...chatMessages.map((m, i) => React.createElement('p', { key: i }, React.createElement('strong', null, m.role === 'user' ? 'You' : 'AI', ':'), ' ', m.text)),
      ),
      React.createElement('input', { style: styles.input, placeholder: 'Type a message...', value: chatInput, onChange: (e) => setChatInput(e.target.value), onKeyDown: (e) => e.key === 'Enter' && sendChat() }),
      React.createElement('div', { style: styles.row }, React.createElement('button', { style: { ...styles.btn, background: '#4f46e5' }, onClick: sendChat }, 'Send')),
    );
  } else if (route === 'models') {
    page = React.createElement('div', { style: styles.card },
      React.createElement('h2', null, 'AI Model Connection'),
      React.createElement('p', null, 'Connected providers and model options from backend.'),
      React.createElement('ul', null,
        ...(modelOptions.providers || []).map((p) => React.createElement('li', { key: p.value },
          React.createElement('strong', null, p.label), ': ', ((modelOptions.models && modelOptions.models[p.value]) || []).join(', ') || 'No models configured'))),
    );
  } else if (route === 'admin') {
    page = React.createElement('div', { style: styles.card },
      React.createElement('h2', null, 'Admin Panel'),
      role !== 'admin' ? React.createElement('p', { style: { color: '#fda4af' } }, 'Admin access required.') : React.createElement(React.Fragment, null,
        React.createElement('p', null, 'Create admin/user accounts and review users.'),
        React.createElement('div', { style: styles.row },
          React.createElement('input', { style: styles.input, placeholder: 'username', value: newUser.username, onChange: (e) => setNewUser((v) => ({ ...v, username: e.target.value })) }),
          React.createElement('input', { style: styles.input, type: 'password', placeholder: 'password', value: newUser.password, onChange: (e) => setNewUser((v) => ({ ...v, password: e.target.value })) }),
          React.createElement('select', { style: styles.input, value: newUser.role, onChange: (e) => setNewUser((v) => ({ ...v, role: e.target.value })) },
            React.createElement('option', { value: 'user' }, 'user'), React.createElement('option', { value: 'admin' }, 'admin')),
          React.createElement('button', { style: { ...styles.btn, background: '#059669' }, onClick: createAdminUser }, 'Create User')
        ),
        React.createElement('table', { style: { width: '100%', marginTop: 12 } },
          React.createElement('thead', null, React.createElement('tr', null, React.createElement('th', { align: 'left' }, 'Username'), React.createElement('th', { align: 'left' }, 'Role'))),
          React.createElement('tbody', null, ...adminUsers.map((u) => React.createElement('tr', { key: u.username }, React.createElement('td', null, u.username), React.createElement('td', null, u.role))))
        )
      )
    );
  }

  return React.createElement('div', { style: styles.root }, React.createElement('div', { style: styles.container }, nav, page,
    error ? React.createElement('div', { style: styles.card }, React.createElement('p', { style: { color: '#fda4af', margin: 0 } }, error)) : null,
    ok ? React.createElement('div', { style: styles.card }, React.createElement('p', { style: { color: '#86efac', margin: 0 } }, ok)) : null,
  ));
}

const rootEl = document.getElementById('root');
if (rootEl) createRoot(rootEl).render(React.createElement(App));
