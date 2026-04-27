/* =====================================================
   AmpAI SPA — Core Application (Fixed)
   ===================================================== */

// ── State ──────────────────────────────────────────
const State = {
  token:     localStorage.getItem('ampai_token')    || '',
  role:      localStorage.getItem('ampai_role')     || 'user',
  user:      localStorage.getItem('ampai_username') || '',
  sessionId: localStorage.getItem('ampai_session_id') || _newSessionId(),
  currentPage: 'login',
};

function _newSessionId() {
  const id = 'sess_' + Math.random().toString(36).slice(2, 9);
  localStorage.setItem('ampai_session_id', id);
  return id;
}

// ── API ────────────────────────────────────────────
async function apiJSON(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (State.token) headers['Authorization'] = 'Bearer ' + State.token;
  try {
    const res = await fetch(path, { ...opts, headers });
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, data };
  } catch (e) {
    return { ok: false, status: 0, data: { detail: e.message } };
  }
}

// ── Toast ──────────────────────────────────────────
function toast(msg, type = 'info') {
  const c = document.getElementById('toast-container');
  if (!c) return;
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `<span>${type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}</span> ${msg}`;
  c.appendChild(el);
  setTimeout(() => el.remove(), 3800);
}

// ── Modal ──────────────────────────────────────────
function openModal(id)  { document.getElementById(id)?.classList.add('open');    }
function closeModal(id) { document.getElementById(id)?.classList.remove('open'); }

// ── Navigation ─────────────────────────────────────
// Two top-level pages: #page-login and #page-shell.
// Sub-pages live inside #page-shell as .subpage divs.
const SUBPAGES = ['chat','memory','tasks','notes','analytics','network','models','settings','admin'];
const PAGE_TITLES = {
  chat:'Chat', memory:'Memory Explorer', tasks:'Task Manager',
  notes:'Notes', analytics:'Analytics', network:'Network Monitor',
  models:'AI Models', settings:'Settings', admin:'Admin Panel'
};

function navigate(page) {
  // Guard: unauthenticated → login
  if (!State.token && page !== 'login') { navigate('login'); return; }
  // Guard: authenticated → skip login page
  if (State.token  && page === 'login') { page = 'chat'; }
  // Guard: non-admin on admin page
  if (page === 'admin' && State.role !== 'admin') { navigate('chat'); return; }

  State.currentPage = page;
  history.replaceState(null, '', '#/' + page);

  if (page === 'login') {
    _showEl('page-login');
    _hideEl('page-shell');
    return;
  }

  // Authenticated pages live inside the shell
  _hideEl('page-login');
  _showEl('page-shell');

  // Activate correct subpage
  document.querySelectorAll('.subpage').forEach(p => p.classList.add('hidden'));
  const spEl = document.getElementById('sp-' + page);
  if (spEl) spEl.classList.remove('hidden');

  // Highlight sidebar nav
  document.querySelectorAll('.nav-item[data-page]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.page === page);
  });

  // Update topbar title
  const titleEl = document.getElementById('topbar-title');
  if (titleEl) titleEl.textContent = PAGE_TITLES[page] || page;

  // Trigger page logic
  _onPageEnter(page);
}

function _showEl(id) {
  const el = document.getElementById(id);
  if (el) { el.style.display = ''; el.classList.add('active'); }
}
function _hideEl(id) {
  const el = document.getElementById(id);
  if (el) { el.style.display = 'none'; el.classList.remove('active'); }
}

function _onPageEnter(page) {
  if (page === 'chat')      chatInit();
  if (page === 'memory')    memoryLoad();
  if (page === 'tasks')     tasksLoad();
  if (page === 'notes')     notesLoad();
  if (page === 'analytics') analyticsLoad();
  if (page === 'network')   networkLoad();
  if (page === 'admin')     adminInit();
  if (page === 'models')    modelsLoad();
  if (page === 'settings')  settingsLoad();
}

// ── Auth ───────────────────────────────────────────
async function doLogin(username, password) {
  const { ok, data } = await apiJSON('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  if (!ok) throw new Error(data.detail || 'Login failed');
  State.token = data.token || '';
  State.role  = data.role  || 'user';
  State.user  = data.username || username;
  localStorage.setItem('ampai_token',    State.token);
  localStorage.setItem('ampai_role',     State.role);
  localStorage.setItem('ampai_username', State.user);
}

async function doLogout() {
  await apiJSON('/api/auth/logout', { method: 'POST' }).catch(() => {});
  State.token = State.role = State.user = '';
  ['ampai_token','ampai_role','ampai_username','ampai_session_id'].forEach(k => localStorage.removeItem(k));
  _syncUserUI();
  navigate('login');
}

async function checkAuth() {
  if (!State.token) return false;
  const { ok } = await apiJSON('/api/auth/whoami');
  if (!ok) { State.token = ''; localStorage.removeItem('ampai_token'); return false; }
  return true;
}

// ── Post-login UI sync ─────────────────────────────
function _syncUserUI() {
  const av  = document.getElementById('user-avatar');
  const nm  = document.getElementById('user-display');
  const ddu = document.getElementById('dd-username');
  const ddr = document.getElementById('dd-role');
  if (av)  av.textContent  = State.user ? State.user[0].toUpperCase() : '?';
  if (nm)  nm.textContent  = State.user;
  if (ddu) ddu.textContent = State.user;
  if (ddr) ddr.textContent = State.role;
  // Show admin nav item only for admins
  document.querySelectorAll('.admin-only').forEach(el => {
    el.classList.toggle('hidden', State.role !== 'admin');
  });
}

// ── Build & Boot ───────────────────────────────────
function buildApp() {
  const app = document.getElementById('app');
  if (!app) return;
  app.innerHTML = _loginHTML() + _shellHTML();
  _attachLoginHandlers();
  _attachShellHandlers();
}

async function init() {
  buildApp();
  const authed = State.token ? await checkAuth() : false;
  if (authed) {
    _syncUserUI();
    const hash = location.hash.replace(/^#\/?/, '');
    navigate(SUBPAGES.includes(hash) ? hash : 'chat');
  } else {
    navigate('login');
  }
  // Restore sidebar collapsed state
  if (localStorage.getItem('sb_collapsed') === '1') {
    document.getElementById('sidebar')?.classList.add('collapsed');
  }
}

document.addEventListener('DOMContentLoaded', init);

// ── Login page HTML ────────────────────────────────
function _loginHTML() {
  return `
<div id="page-login" style="display:flex;align-items:center;justify-content:center;min-height:100vh;
  background:radial-gradient(ellipse 90% 60% at 15% 5%,rgba(99,102,241,.22) 0%,transparent 65%),
  radial-gradient(ellipse 70% 55% at 85% 95%,rgba(139,92,246,.18) 0%,transparent 65%),var(--bg)">
  <div style="width:100%;max-width:420px;padding:24px">
    <div style="text-align:center;margin-bottom:28px">
      <div style="font-size:2.2rem;font-weight:800;background:linear-gradient(90deg,#818cf8,#c084fc,#34d399);
        -webkit-background-clip:text;-webkit-text-fill-color:transparent">⚡ AmpAI</div>
      <p style="color:var(--muted);font-size:.9rem;margin-top:6px">AI-powered memory agent for smarter conversations</p>
    </div>

    <!-- Login card -->
    <div id="login-card" style="background:rgba(15,23,42,.88);border:1px solid var(--border);border-radius:18px;
      padding:32px;backdrop-filter:blur(12px);box-shadow:0 30px 60px rgba(0,0,0,.5)">
      <h2 style="font-size:1.25rem;font-weight:700;margin-bottom:4px">Welcome back</h2>
      <p style="color:var(--muted);font-size:.85rem;margin-bottom:20px">Sign in to your workspace</p>
      <div style="background:rgba(99,102,241,.1);border:1px solid rgba(99,102,241,.25);border-radius:8px;
        padding:10px 12px;font-size:.8rem;color:#a5b4fc;margin-bottom:18px">
        Default admin: <code style="background:rgba(0,0,0,.3);padding:1px 5px;border-radius:4px">admin</code>
        / <code style="background:rgba(0,0,0,.3);padding:1px 5px;border-radius:4px">P@ssw0rd</code>
      </div>
      <div style="margin-bottom:14px">
        <label style="display:block;font-size:.8rem;color:var(--muted);margin-bottom:6px;font-weight:500">Username</label>
        <input id="login-user" type="text" autocomplete="username" placeholder="Enter username"
          style="width:100%;padding:10px 12px;border-radius:8px;background:rgba(0,0,0,.25);
          border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:.9rem;outline:none"/>
      </div>
      <div style="margin-bottom:14px">
        <label style="display:block;font-size:.8rem;color:var(--muted);margin-bottom:6px;font-weight:500">Password</label>
        <input id="login-pass" type="password" autocomplete="current-password" placeholder="Enter password"
          style="width:100%;padding:10px 12px;border-radius:8px;background:rgba(0,0,0,.25);
          border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:.9rem;outline:none"/>
      </div>
      <div id="login-err" style="display:none;color:#fca5a5;font-size:.85rem;margin-bottom:10px"></div>
      <button id="login-btn" style="width:100%;padding:11px;border-radius:8px;border:none;cursor:pointer;
        background:var(--accent);color:#fff;font-family:inherit;font-size:.9rem;font-weight:600;
        transition:all .18s;margin-top:4px">Sign In</button>
      <div style="text-align:center;margin-top:16px;font-size:.82rem;color:var(--muted)">
        No account? <a href="#" id="show-reg" style="color:var(--accent)">Register</a>
      </div>
    </div>

    <!-- Register card -->
    <div id="reg-card" style="display:none;background:rgba(15,23,42,.88);border:1px solid var(--border);
      border-radius:18px;padding:32px;backdrop-filter:blur(12px);box-shadow:0 30px 60px rgba(0,0,0,.5);margin-top:16px">
      <h2 style="font-size:1.25rem;font-weight:700;margin-bottom:4px">Create account</h2>
      <p style="color:var(--muted);font-size:.85rem;margin-bottom:20px">Register a new user</p>
      <div style="margin-bottom:14px">
        <label style="display:block;font-size:.8rem;color:var(--muted);margin-bottom:6px;font-weight:500">Username</label>
        <input id="reg-user" type="text" placeholder="Choose username"
          style="width:100%;padding:10px 12px;border-radius:8px;background:rgba(0,0,0,.25);
          border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:.9rem;outline:none"/>
      </div>
      <div style="margin-bottom:14px">
        <label style="display:block;font-size:.8rem;color:var(--muted);margin-bottom:6px;font-weight:500">Password</label>
        <input id="reg-pass" type="password" placeholder="Min 4 characters"
          style="width:100%;padding:10px 12px;border-radius:8px;background:rgba(0,0,0,.25);
          border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:.9rem;outline:none"/>
      </div>
      <div id="reg-err" style="display:none;color:#fca5a5;font-size:.85rem;margin-bottom:10px"></div>
      <button id="reg-btn" style="width:100%;padding:11px;border-radius:8px;border:none;cursor:pointer;
        background:var(--green);color:#fff;font-family:inherit;font-size:.9rem;font-weight:600">Create Account</button>
      <div style="text-align:center;margin-top:12px;font-size:.82rem;color:var(--muted)">
        <a href="#" id="show-login" style="color:var(--accent)">Back to login</a>
      </div>
    </div>
  </div>
</div>`;
}

// ── Shell HTML (sidebar + main + subpages) ─────────
function _shellHTML() {
  return `
<div id="page-shell" style="display:none;flex:1;height:100vh;overflow:hidden">
  <div class="shell">
    <!-- Sidebar -->
    <aside class="sidebar" id="sidebar">
      <div class="sidebar-logo">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="#818cf8" stroke-width="2"/>
          <path d="M8 12h8M12 8v8" stroke="#c084fc" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <span class="sidebar-label" style="font-weight:800;background:linear-gradient(90deg,#818cf8,#c084fc);
          -webkit-background-clip:text;-webkit-text-fill-color:transparent">AmpAI</span>
      </div>
      <nav class="sidebar-nav">
        <button class="nav-item" data-page="chat">
          <span class="icon">💬</span><span class="sidebar-label">Chat</span>
        </button>
        <button class="nav-item" data-page="memory">
          <span class="icon">🧠</span><span class="sidebar-label">Memory</span>
        </button>
        <button class="nav-item" data-page="tasks">
          <span class="icon">✅</span><span class="sidebar-label">Tasks</span>
        </button>
        <button class="nav-item" data-page="notes">
          <span class="icon">📝</span><span class="sidebar-label">Notes</span>
        </button>
        <button class="nav-item" data-page="analytics">
          <span class="icon">📊</span><span class="sidebar-label">Analytics</span>
        </button>
        <button class="nav-item" data-page="network">
          <span class="icon">🌐</span><span class="sidebar-label">Network</span>
        </button>
        <button class="nav-item" data-page="models">
          <span class="icon">🤖</span><span class="sidebar-label">AI Models</span>
        </button>
        <button class="nav-item" data-page="settings">
          <span class="icon">⚙️</span><span class="sidebar-label">Settings</span>
        </button>
        <button class="nav-item admin-only hidden" data-page="admin">
          <span class="icon">🛡️</span><span class="sidebar-label">Admin Panel</span>
        </button>
      </nav>
      <div class="sidebar-footer">
        <button class="nav-item w-full" id="logout-btn">
          <span class="icon">🚪</span><span class="sidebar-label">Logout</span>
        </button>
      </div>
      <button class="sidebar-toggle" id="sidebar-toggle" title="Toggle sidebar">◀</button>
    </aside>

    <!-- Main -->
    <div class="main">
      <div class="topbar">
        <button class="btn btn-ghost btn-sm" id="mobile-menu-btn" style="display:none">☰</button>
        <div class="topbar-title" id="topbar-title">Chat</div>
        <div style="margin-left:auto;position:relative" id="user-menu-trigger">
          <div style="display:flex;align-items:center;gap:8px;cursor:pointer;padding:4px 8px;border-radius:8px;
            transition:background .15s" onmouseenter="this.style.background='var(--bg-3)'"
            onmouseleave="this.style.background=''">
            <div class="avatar" id="user-avatar">A</div>
            <span id="user-display" style="font-size:.85rem;color:var(--muted)" class="sidebar-label"></span>
            <span style="color:var(--muted);font-size:.8rem">▾</span>
          </div>
          <div id="user-dropdown" class="user-dropdown">
            <div style="padding:10px 14px;border-bottom:1px solid var(--border)">
              <div id="dd-username" style="font-weight:600;color:var(--text);font-size:.9rem"></div>
              <div id="dd-role" style="font-size:.75rem;color:var(--muted)"></div>
            </div>
            <button onclick="navigate('settings')" style="width:100%;padding:9px 14px;font-size:.875rem;
              color:var(--muted);background:none;border:none;cursor:pointer;text-align:left;display:block">
              ⚙️ Settings
            </button>
            <div style="height:1px;background:var(--border);margin:4px 0"></div>
            <button id="dd-logout" style="width:100%;padding:9px 14px;font-size:.875rem;color:var(--red);
              background:none;border:none;cursor:pointer;text-align:left;display:block">
              🚪 Logout
            </button>
          </div>
        </div>
      </div>

      <!-- Subpages -->
      <div id="sp-chat"     class="subpage hidden" style="display:flex;flex:1;min-height:0;flex-direction:row;height:calc(100vh - 57px)">
        ${buildChatPage()}
      </div>
      <div id="sp-memory"   class="subpage hidden page-content">${buildMemoryPage()}</div>
      <div id="sp-tasks"    class="subpage hidden page-content">${buildTasksPage()}</div>
      <div id="sp-notes"    class="subpage hidden" style="display:flex;flex:1;min-height:0;height:calc(100vh - 57px)">${buildNotesPage()}</div>
      <div id="sp-analytics" class="subpage hidden page-content">${buildAnalyticsPage()}</div>
      <div id="sp-network"  class="subpage hidden page-content">${buildNetworkPage()}</div>
      <div id="sp-models"   class="subpage hidden page-content">${buildModelsPage()}</div>
      <div id="sp-settings" class="subpage hidden page-content">${buildSettingsPage()}</div>
      <div id="sp-admin"    class="subpage hidden page-content">${buildAdminPage()}</div>
    </div>
  </div>
</div>
${buildMemoryModal()}`;
}

// ── Attach handlers ────────────────────────────────
function _attachLoginHandlers() {
  const loginBtn = document.getElementById('login-btn');
  const regBtn   = document.getElementById('reg-btn');

  loginBtn?.addEventListener('click', async () => {
    const u = document.getElementById('login-user').value.trim();
    const p = document.getElementById('login-pass').value;
    const errEl = document.getElementById('login-err');
    errEl.style.display = 'none'; errEl.textContent = '';
    loginBtn.disabled = true; loginBtn.textContent = 'Signing in…';
    try {
      await doLogin(u, p);
      _syncUserUI();
      navigate('chat');
    } catch (e) {
      errEl.textContent = e.message;
      errEl.style.display = 'block';
    } finally {
      loginBtn.disabled = false;
      loginBtn.textContent = 'Sign In';
    }
  });

  document.getElementById('login-pass')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') loginBtn?.click();
  });
  document.getElementById('login-user')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('login-pass')?.focus();
  });

  regBtn?.addEventListener('click', async () => {
    const u = document.getElementById('reg-user').value.trim();
    const p = document.getElementById('reg-pass').value;
    const errEl = document.getElementById('reg-err');
    errEl.style.display = 'none'; errEl.textContent = '';
    regBtn.disabled = true; regBtn.textContent = 'Creating…';
    try {
      const { ok, data } = await apiJSON('/api/auth/register', {
        method: 'POST', body: JSON.stringify({ username: u, password: p }),
      });
      if (!ok) throw new Error(data.detail || 'Registration failed');
      toast('Account created! You can now sign in.', 'success');
      document.getElementById('reg-card').style.display = 'none';
      document.getElementById('login-user').value = u;
    } catch (e) {
      errEl.textContent = e.message;
      errEl.style.display = 'block';
    } finally {
      regBtn.disabled = false;
      regBtn.textContent = 'Create Account';
    }
  });

  document.getElementById('show-reg')?.addEventListener('click', e => {
    e.preventDefault();
    document.getElementById('reg-card').style.display = 'block';
  });
  document.getElementById('show-login')?.addEventListener('click', e => {
    e.preventDefault();
    document.getElementById('reg-card').style.display = 'none';
  });
}

function _attachShellHandlers() {
  // Sidebar collapse
  document.getElementById('sidebar-toggle')?.addEventListener('click', () => {
    const sb = document.getElementById('sidebar');
    sb?.classList.toggle('collapsed');
    localStorage.setItem('sb_collapsed', sb?.classList.contains('collapsed') ? '1' : '0');
    document.getElementById('sidebar-toggle').textContent =
      sb?.classList.contains('collapsed') ? '▶' : '◀';
  });

  // Nav items
  document.querySelectorAll('.nav-item[data-page]').forEach(btn => {
    btn.addEventListener('click', () => navigate(btn.dataset.page));
  });

  // Logout
  document.getElementById('logout-btn')?.addEventListener('click', doLogout);
  document.getElementById('dd-logout')?.addEventListener('click', doLogout);

  // User dropdown toggle
  document.getElementById('user-menu-trigger')?.addEventListener('click', e => {
    e.stopPropagation();
    document.getElementById('user-dropdown')?.classList.toggle('open');
  });
  document.addEventListener('click', () => {
    document.getElementById('user-dropdown')?.classList.remove('open');
  });

  // Mobile menu
  document.getElementById('mobile-menu-btn')?.addEventListener('click', () => {
    document.getElementById('sidebar')?.classList.toggle('mobile-open');
  });

  // Modal close buttons
  document.querySelectorAll('[data-close-modal]').forEach(btn => {
    btn.addEventListener('click', () => closeModal(btn.dataset.closeModal));
  });
}
