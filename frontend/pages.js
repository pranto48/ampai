/* =====================================================
   AmpAI — Inner HTML for each subpage
   Called from ampai.js _shellHTML()
   ===================================================== */

// ── Chat inner HTML ────────────────────────────────
function buildChatPage() {
  return `
  <!-- Session sidebar -->
  <div style="width:260px;min-width:260px;background:var(--bg-2);border-right:1px solid var(--border);
    display:flex;flex-direction:column;overflow:hidden">
    <div style="padding:14px;border-bottom:1px solid var(--border);display:flex;flex-direction:column;gap:10px">
      <button id="new-chat-btn" style="width:100%;padding:10px;border-radius:8px;border:none;cursor:pointer;
        background:var(--accent);color:#fff;font-family:inherit;font-size:.875rem;font-weight:600">
        ＋ New Chat
      </button>
      <input id="session-search" placeholder="Search sessions…"
        style="width:100%;padding:8px 10px;border-radius:8px;background:rgba(0,0,0,.2);
        border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:.82rem;outline:none"/>
    </div>
    <div id="sessions-list" style="flex:1;overflow-y:auto;padding:8px"></div>
  </div>

  <!-- Chat main -->
  <div style="flex:1;display:flex;flex-direction:column;min-width:0">
    <!-- Chat topbar -->
    <div style="padding:12px 18px;border-bottom:1px solid var(--border);display:flex;align-items:center;
      gap:12px;background:var(--glass);backdrop-filter:blur(12px)">
      <div style="flex:1">
        <div style="font-weight:600;font-size:.95rem" id="chat-session-name">New Chat</div>
        <div style="font-size:.72rem;color:var(--muted)" id="chat-session-id"></div>
      </div>
      <select id="model-select" style="padding:6px 10px;border-radius:8px;background:rgba(0,0,0,.25);
        border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:.82rem;outline:none">
        <option value="ollama">🦙 Ollama</option>
        <option value="openai">✨ OpenAI</option>
        <option value="gemini">🌟 Gemini</option>
        <option value="anthropic">🔴 Anthropic</option>
        <option value="anythingllm">🏠 AnythingLLM</option>
        <option value="openrouter">🔀 OpenRouter</option>
      </select>
      <select id="persona-select" title="Persona"
        style="padding:6px 10px;border-radius:8px;background:rgba(0,0,0,.25);
        border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:.82rem;outline:none;min-width:170px">
        <option value="">🧩 Default Persona</option>
      </select>
      <select id="memory-mode-select" title="Memory mode"
        style="padding:6px 10px;border-radius:8px;background:rgba(0,0,0,.25);
        border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:.82rem;outline:none">
        <option value="full">🧠 Full Memory</option>
        <option value="context_only">💬 Context Only</option>
        <option value="none">⛔ No Memory</option>
      </select>
      <label title="Enable web search" style="display:flex;align-items:center;gap:5px;
        font-size:.8rem;color:var(--muted);cursor:pointer">
        <input type="checkbox" id="web-search-toggle" style="accent-color:var(--accent)"/> 🌐
      </label>
      <span id="memory-policy-badge" style="font-size:.72rem;color:var(--muted);padding:4px 8px;border:1px solid var(--border);border-radius:999px">
        Memory: Loading…
      </span>
    </div>

    <!-- Messages -->
    <div id="chat-messages" style="flex:1;overflow-y:auto;padding:24px 20px;
      display:flex;flex-direction:column;gap:20px;scroll-behavior:smooth">
      <div style="display:flex;gap:12px;max-width:80%;align-self:flex-start">
        <div style="width:34px;height:34px;border-radius:50%;flex-shrink:0;
          background:linear-gradient(135deg,#10b981,#3b82f6);
          display:flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:700;color:#fff">AI</div>
        <div style="padding:12px 16px;border-radius:12px;border-top-left-radius:3px;
          background:var(--bg-3);border:1px solid var(--border);line-height:1.6;font-size:.9rem">
          <strong>Hello! I'm AmpAI.</strong><br>
          I remember your conversations and use that memory to give you better, personalised answers.<br><br>
          <span style="color:var(--muted);font-size:.85rem">Start chatting — every message is saved and indexed for future recall.</span>
        </div>
      </div>
    </div>

    <!-- Input -->
    <div style="padding:14px 18px;border-top:1px solid var(--border);
      background:linear-gradient(to top,var(--bg) 70%,transparent)">
      <div id="attach-previews" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px"></div>
      <div style="display:flex;align-items:flex-end;gap:8px;background:var(--bg-3);
        border:1px solid var(--border);border-radius:14px;padding:8px 12px;transition:border-color .2s"
        id="input-box">
        <button id="attach-btn" title="Attach file" style="background:none;border:none;cursor:pointer;
          color:var(--muted);padding:6px;font-size:1.1rem;transition:color .15s">📎</button>
        <input type="file" id="file-input" style="display:none" multiple/>
        <textarea id="chat-input" rows="1" placeholder="Message AmpAI…"
          style="flex:1;background:none;border:none;color:var(--text);font-family:inherit;
          font-size:.95rem;resize:none;outline:none;max-height:140px;min-height:24px;
          line-height:1.5;padding:6px 0"></textarea>
        <button id="send-btn" disabled style="padding:8px 16px;border-radius:8px;border:none;cursor:pointer;
          background:var(--accent);color:#fff;font-family:inherit;font-size:.875rem;font-weight:600;
          transition:all .18s;opacity:.6">Send</button>
      </div>
      <div style="display:flex;margin-top:6px;padding:0 2px">
        <span style="font-size:.72rem;color:var(--muted)">Shift+Enter for newline · Enter to send</span>
        <span style="font-size:.72rem;color:var(--muted);margin-left:auto" id="session-cat-badge"></span>
      </div>
    </div>
  </div>`;
}

// ── Memory inner HTML ──────────────────────────────
function buildMemoryPage() {
  return `
<div class="section-head" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
  <h2 style="font-size:1.15rem;font-weight:700">🧠 Memory Explorer</h2>
  <button id="memory-refresh-btn" class="btn btn-secondary btn-sm">↻ Refresh</button>
</div>

<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;
  background:var(--bg-2);border:1px solid var(--border);border-radius:12px;padding:16px;margin-bottom:20px">
  <div style="flex:2;min-width:200px">
    <label style="display:block;font-size:.8rem;color:var(--muted);margin-bottom:6px;font-weight:500">Search</label>
    <input id="mx-query" placeholder="Search memories…" class="input"/>
  </div>
  <div style="flex:1;min-width:150px">
    <label style="display:block;font-size:.8rem;color:var(--muted);margin-bottom:6px;font-weight:500">Category</label>
    <select id="mx-category" class="input"><option value="">All categories</option></select>
  </div>
  <div style="flex:1;min-width:130px">
    <label style="display:block;font-size:.8rem;color:var(--muted);margin-bottom:6px;font-weight:500">Scope</label>
    <select id="mx-scope" class="input">
      <option value="mine">Mine</option>
      <option value="shared">Shared</option>
      <option value="all">All</option>
    </select>
  </div>
  <div style="flex:1;min-width:140px">
    <label style="display:block;font-size:.8rem;color:var(--muted);margin-bottom:6px;font-weight:500">From</label>
    <input id="mx-date-from" type="date" class="input"/>
  </div>
  <div style="flex:1;min-width:140px">
    <label style="display:block;font-size:.8rem;color:var(--muted);margin-bottom:6px;font-weight:500">To</label>
    <input id="mx-date-to" type="date" class="input"/>
  </div>
  <button id="mx-apply" class="btn btn-primary" style="align-self:flex-end">Search</button>
</div>

<div class="card" style="overflow-x:auto">
  <table class="tbl">
    <thead>
      <tr>
        <th>Session ID</th><th>Category</th><th>Owner</th>
        <th>Tags</th><th>Summary</th><th>Updated</th><th>Actions</th>
      </tr>
    </thead>
    <tbody id="mx-body">
      <tr><td colspan="7" style="text-align:center;color:var(--muted);padding:32px">Loading…</td></tr>
    </tbody>
  </table>
  <div style="display:flex;align-items:center;justify-content:space-between;margin-top:14px;padding:0 4px">
    <button id="mx-prev" class="btn btn-secondary btn-sm">← Prev</button>
    <span id="mx-page" style="font-size:.75rem;color:var(--muted)">—</span>
    <button id="mx-next" class="btn btn-secondary btn-sm">Next →</button>
  </div>
</div>`;
}

function buildPersonasPage() {
  return `
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
  <h2 style="font-size:1.15rem;font-weight:700">🧩 Personas</h2>
  <button id="personas-refresh-btn" class="btn btn-secondary btn-sm">↻ Refresh</button>
</div>

<div class="card" style="margin-bottom:16px">
  <div class="card-title">Create Persona</div>
  <div class="grid-2" style="gap:12px">
    <div>
      <label class="lbl">Name</label>
      <input id="persona-name" class="input" placeholder="Helpful Technical Mentor"/>
    </div>
    <div>
      <label class="lbl">Tags (comma separated)</label>
      <input id="persona-tags" class="input" placeholder="coding, concise"/>
    </div>
  </div>
  <div style="margin-top:10px">
    <label class="lbl">System Prompt</label>
    <textarea id="persona-system-prompt" class="input" rows="5" placeholder="You are a concise assistant..."></textarea>
  </div>
  <div style="display:flex;gap:12px;margin-top:10px;align-items:center;flex-wrap:wrap">
    <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
      <input type="checkbox" id="persona-is-default" style="accent-color:var(--accent)"/>
      <span style="font-size:.86rem">Set as default</span>
    </label>
    <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
      <input type="checkbox" id="persona-is-global" style="accent-color:var(--accent)"/>
      <span style="font-size:.86rem">Global (admin only)</span>
    </label>
    <button id="create-persona-btn" class="btn btn-primary btn-sm">Create Persona</button>
    <span id="persona-create-status" style="font-size:.82rem;color:var(--muted)"></span>
  </div>
</div>

<div class="card">
  <div class="card-title">Saved Personas</div>
  <table class="tbl">
    <thead><tr><th>Name</th><th>Scope</th><th>Tags</th><th>Default</th><th>Prompt</th><th>Actions</th></tr></thead>
    <tbody id="personas-body">
      <tr><td colspan="6" style="text-align:center;padding:22px;color:var(--muted)">Loading…</td></tr>
    </tbody>
  </table>
</div>`;
}

// ── AI Models inner HTML ───────────────────────────
function buildModelsPage() {
  return `
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
  <h2 style="font-size:1.15rem;font-weight:700">🤖 AI Model Configuration</h2>
  <button id="save-model-cfg-btn" class="btn btn-primary btn-sm">💾 Save All</button>
</div>
<div id="model-save-status" style="font-size:.85rem;color:var(--green);margin-bottom:12px"></div>

<div class="grid-2" style="gap:16px">
  ${_modelCard('🦙','Ollama','Local LLM','rgba(99,102,241,.15)',[
    ['cfg-ollama-url','text','Base URL','http://localhost:11434'],
    ['cfg-ollama-models','text','Model list (comma-separated)','llama3,mistral,phi3'],
  ])}
  ${_modelCard('✨','OpenAI','GPT-4, GPT-3.5','rgba(16,185,129,.15)',[
    ['cfg-openai-key','password','API Key','sk-…'],
  ])}
  ${_modelCard('🌟','Gemini','Google AI','rgba(245,158,11,.15)',[
    ['cfg-gemini-key','password','API Key','AIza…'],
  ])}
  ${_modelCard('🔴','Anthropic','Claude','rgba(239,68,68,.15)',[
    ['cfg-anthropic-key','password','API Key','sk-ant-…'],
  ])}
  ${_modelCard('🔀','OpenRouter','Multi-provider','rgba(139,92,246,.15)',[
    ['cfg-openrouter-key','password','API Key','sk-or-…'],
    ['cfg-openrouter-model','text','Default Model','openai/gpt-4o'],
  ])}
  ${_modelCard('🏠','AnythingLLM','Self-hosted RAG','rgba(16,185,129,.1)',[
    ['cfg-anythingllm-url','text','Base URL','http://localhost:3001'],
    ['cfg-anythingllm-key','password','API Key',''],
    ['cfg-anythingllm-ws','text','Workspace','my-workspace'],
  ])}
</div>

<div class="card" style="margin-top:16px">
  <div class="card-title">🌐 Web Search</div>
  <div class="grid-2">
    <div style="margin-bottom:14px">
      <label class="lbl">Fallback Provider</label>
      <select id="cfg-search-provider" class="input">
        <option value="duckduckgo">DuckDuckGo (free)</option>
        <option value="serpapi">SerpAPI</option>
        <option value="bing">Bing</option>
      </select>
    </div>
    <div style="margin-bottom:14px">
      <label class="lbl">SerpAPI Key</label>
      <input id="cfg-serpapi-key" type="password" class="input" placeholder="…"/>
    </div>
  </div>
</div>

<div class="card" style="margin-top:16px">
  <div class="card-title">⚙️ Global Default Provider</div>
  <div style="max-width:280px">
    <select id="cfg-default-model" class="input">
      <option value="ollama">Ollama</option>
      <option value="openai">OpenAI</option>
      <option value="gemini">Gemini</option>
      <option value="anthropic">Anthropic</option>
      <option value="anythingllm">AnythingLLM</option>
      <option value="openrouter">OpenRouter</option>
    </select>
  </div>
</div>`;
}

function _modelCard(icon, name, sub, bg, fields) {
  return `
<div style="background:var(--bg-2);border:1px solid var(--border);border-radius:12px;padding:18px;
  transition:border-color .2s" onmouseenter="this.style.borderColor='rgba(99,102,241,.4)'"
  onmouseleave="this.style.borderColor='var(--border)'">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
    <div style="width:38px;height:38px;border-radius:10px;background:${bg};
      display:flex;align-items:center;justify-content:center;font-size:1.1rem">${icon}</div>
    <div>
      <div style="font-weight:700">${name}</div>
      <div style="font-size:.75rem;color:var(--muted)">${sub}</div>
    </div>
  </div>
  ${fields.map(([id,type,label,ph]) => `
  <div style="margin-bottom:12px">
    <label style="display:block;font-size:.8rem;color:var(--muted);margin-bottom:6px;font-weight:500">${label}</label>
    <input id="${id}" type="${type}" class="input" placeholder="${ph}"/>
  </div>`).join('')}
</div>`;
}

// ── Settings inner HTML ────────────────────────────
function buildSettingsPage() {
  return `
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
  <h2 style="font-size:1.15rem;font-weight:700">⚙️ Settings</h2>
</div>

<div class="grid-2" style="gap:20px">
  <div>
    <div class="card" style="margin-bottom:16px">
      <div class="card-title">👤 Agent Identity</div>
      <div style="margin-bottom:14px">
        <label class="lbl">Agent Display Name</label>
        <input id="cfg-agent-name" class="input" placeholder="AmpAI"/>
      </div>
      <div style="margin-bottom:14px">
        <label class="lbl">Agent Avatar URL (optional)</label>
        <input id="cfg-agent-avatar" class="input" placeholder="https://…"/>
      </div>
      <button id="save-agent-settings-btn" class="btn btn-primary btn-sm">Save Identity</button>
    </div>

    <div class="card">
      <div class="card-title">🔒 Change Password</div>
      <div style="margin-bottom:14px">
        <label class="lbl">Current Password</label>
        <input id="pw-current" type="password" class="input"/>
      </div>
      <div style="margin-bottom:14px">
        <label class="lbl">New Password</label>
        <input id="pw-new" type="password" class="input"/>
      </div>
      <button id="change-pw-btn" class="btn btn-primary btn-sm">Update Password</button>
      <div id="pw-status" style="font-size:.85rem;margin-top:10px"></div>
    </div>
  </div>

  <div>
    <div class="card" style="margin-bottom:16px">
      <div class="card-title">🔔 Notification Preferences</div>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:12px">
        <input type="checkbox" id="notif-browser" style="accent-color:var(--accent)"/>
        <span style="font-size:.875rem">Browser notifications when away</span>
      </label>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:12px">
        <input type="checkbox" id="notif-email" style="accent-color:var(--accent)"/>
        <span style="font-size:.875rem">Email notifications when away</span>
      </label>
      <div style="margin-bottom:12px">
        <label class="lbl">Min interval between notifications (sec)</label>
        <input id="notif-interval" type="number" value="300" min="0" class="input"/>
      </div>
      <div style="margin-bottom:14px">
        <label class="lbl">Digest mode</label>
        <select id="notif-digest" class="input">
          <option value="immediate">Immediate</option>
          <option value="periodic">Periodic digest</option>
        </select>
      </div>
      <button id="save-notif-btn" class="btn btn-primary btn-sm">Save Notifications</button>
    </div>

    <div class="card" style="margin-bottom:16px">
      <div class="card-title">🧠 Memory Policy</div>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:12px">
        <input type="checkbox" id="memory-auto-capture" style="accent-color:var(--accent)"/>
        <span style="font-size:.875rem">Auto-capture conversation memory</span>
      </label>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:12px">
        <input type="checkbox" id="memory-require-approval" style="accent-color:var(--accent)"/>
        <span style="font-size:.875rem">Require approval before memory writes</span>
      </label>
      <label style="display:flex;align-items:center;gap:10px;cursor:pointer;margin-bottom:12px">
        <input type="checkbox" id="memory-pii-strict" style="accent-color:var(--accent)"/>
        <span style="font-size:.875rem">Strict PII redaction</span>
      </label>
      <div style="margin-bottom:12px">
        <label class="lbl">Retention (days)</label>
        <input id="memory-retention-days" type="number" min="1" max="3650" class="input" value="365"/>
      </div>
      <div style="margin-bottom:14px">
        <label class="lbl">Allowed categories (comma-separated)</label>
        <input id="memory-allowed-categories" class="input" placeholder="preferences,projects,tasks"/>
      </div>
      <button id="save-memory-policy-btn" class="btn btn-primary btn-sm">Save Memory Policy</button>
    </div>

    <div class="card">
      <div class="card-title">📧 Email (Resend)</div>
      <div style="margin-bottom:12px">
        <label class="lbl">Resend API Key</label>
        <input id="cfg-resend-key" type="password" class="input"/>
      </div>
      <div style="margin-bottom:12px">
        <label class="lbl">From email</label>
        <input id="cfg-resend-from" class="input" placeholder="noreply@yourdomain.com"/>
      </div>
      <div style="margin-bottom:14px">
        <label class="lbl">Notification recipient</label>
        <input id="cfg-notif-to" class="input" placeholder="you@yourdomain.com"/>
      </div>
      <button id="save-email-cfg-btn" class="btn btn-primary btn-sm">Save Email Config</button>
    </div>
  </div>
</div>`;
}

// ── Admin inner HTML ───────────────────────────────
function buildAdminPage() {
  return `
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
  <h2 style="font-size:1.15rem;font-weight:700">🛡️ Admin Panel</h2>
</div>

<!-- Stats row -->
<div class="grid-4" style="gap:14px;margin-bottom:20px">
  <div class="stat-card"><div class="stat-value" id="stat-sessions">—</div><div class="stat-label">Total Sessions</div></div>
  <div class="stat-card"><div class="stat-value" id="stat-users">—</div><div class="stat-label">Users</div></div>
  <div class="stat-card"><div class="stat-value" id="stat-memories">—</div><div class="stat-label">Core Memories</div></div>
  <div class="stat-card"><div class="stat-value" id="stat-tasks">—</div><div class="stat-label">Active Tasks</div></div>
</div>

<!-- Tabs -->
<div class="tabs" id="admin-tabs">
  <button class="tab active" data-tab="health">🏥 Health</button>
  <button class="tab" data-tab="users">👥 Users</button>
  <button class="tab" data-tab="sessions">💬 Sessions</button>
  <button class="tab" data-tab="memories">🧠 Core Memories</button>
  <button class="tab" data-tab="backup">💾 Backup</button>
  <button class="tab" data-tab="audit">📋 Audit Log</button>
</div>

<!-- Health panel -->
<div id="tab-health">
  <div style="display:flex;justify-content:flex-end;margin-bottom:12px">
    <button id="refresh-health-btn" class="btn btn-secondary btn-sm">↻ Refresh</button>
  </div>
  <div class="grid-4" id="health-grid" style="gap:14px;margin-bottom:16px"></div>
  <div class="card">
    <div class="card-title">Scheduler Diagnostics</div>
    <pre id="scheduler-diag" style="font-size:.8rem;color:var(--muted);white-space:pre-wrap;margin:0">Loading…</pre>
  </div>
</div>

<!-- Users panel -->
<div id="tab-users" class="hidden">
  <div class="card" style="margin-bottom:16px">
    <div class="card-title">Create New User</div>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <input id="new-user-name" class="input" placeholder="Username" style="flex:1;min-width:130px"/>
      <input id="new-user-pass" type="password" class="input" placeholder="Password" style="flex:1;min-width:130px"/>
      <select id="new-user-role" class="input" style="width:110px">
        <option value="user">user</option>
        <option value="admin">admin</option>
      </select>
      <button id="create-user-btn" class="btn btn-primary">Create</button>
    </div>
    <div id="user-status" style="font-size:.85rem;margin-top:8px"></div>
  </div>
  <div class="card" style="overflow-x:auto">
    <table class="tbl">
      <thead><tr><th>Username</th><th>Role</th><th>New Password</th><th>Actions</th></tr></thead>
      <tbody id="users-tbody">
        <tr><td colspan="4" style="text-align:center;padding:24px;color:var(--muted)">Loading…</td></tr>
      </tbody>
    </table>
  </div>
</div>

<!-- Sessions panel -->
<div id="tab-sessions" class="hidden">
  <div class="card" style="overflow-x:auto">
    <table class="tbl">
      <thead><tr><th>Session ID</th><th>Category</th><th>Owner</th><th>Pinned</th><th>Actions</th></tr></thead>
      <tbody id="admin-sessions-tbody">
        <tr><td colspan="5" style="text-align:center;padding:24px;color:var(--muted)">Loading…</td></tr>
      </tbody>
    </table>
  </div>
</div>

<!-- Core memories panel -->
<div id="tab-memories" class="hidden">
  <div class="card">
    <div class="card-title">Distilled Core Memories</div>
    <div id="core-memories-list" style="display:flex;flex-wrap:wrap;gap:8px;min-height:48px">
      <span style="color:var(--muted);font-size:.875rem">Loading…</span>
    </div>
  </div>
</div>

<!-- Backup panel -->
<div id="tab-backup" class="hidden">
  <div class="grid-2" style="gap:16px;margin-bottom:16px">
    <div class="card">
      <div class="card-title">Run Backup Now</div>
      <p style="font-size:.85rem;color:var(--muted);margin-bottom:14px">Exports all sessions to configured destination.</p>
      <button id="run-backup-btn" class="btn btn-primary">▶ Run Backup</button>
      <div id="backup-status" style="font-size:.85rem;margin-top:10px"></div>
    </div>
    <div class="card">
      <div class="card-title">Restore from JSON</div>
      <textarea id="backup-restore-json" class="input" rows="4" placeholder="Paste backup JSON here…"
        style="resize:vertical"></textarea>
      <div style="display:flex;align-items:center;gap:8px;margin-top:8px">
        <input type="checkbox" id="backup-dry-run" checked style="accent-color:var(--accent)"/>
        <label style="font-size:.82rem;color:var(--muted)">Dry run (preview only)</label>
      </div>
      <button id="restore-backup-btn" class="btn btn-secondary" style="margin-top:10px">Restore</button>
      <div id="restore-status" style="font-size:.85rem;margin-top:8px"></div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">Backup History</div>
    <div style="overflow-x:auto">
      <table class="tbl">
        <thead><tr><th>Timestamp</th><th>Trigger</th><th>Status</th><th>Sessions</th><th>Mode</th></tr></thead>
        <tbody id="backup-history-tbody">
          <tr><td colspan="5" style="text-align:center;padding:20px;color:var(--muted)">No history yet</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<!-- Audit Log panel -->
<div id="tab-audit" class="hidden">
  <div class="card" style="overflow-x:auto">
    <table class="tbl">
      <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Session</th><th>Details</th></tr></thead>
      <tbody id="audit-tbody">
        <tr><td colspan="5" style="text-align:center;padding:24px;color:var(--muted)">Loading…</td></tr>
      </tbody>
    </table>
  </div>
</div>`;
}

// ── Chat log modal ─────────────────────────────────
function buildMemoryModal() {
  return `
<div id="modal-chat-log" class="modal-overlay">
  <div class="modal-box" style="max-width:700px;width:95%">
    <div class="modal-header">
      <div class="modal-title">Chat Log — <span id="modal-session-id-label" style="font-size:.85rem;color:var(--muted)"></span></div>
      <button class="modal-close" data-close-modal="modal-chat-log">✕</button>
    </div>
    <div id="modal-chat-body" style="display:flex;flex-direction:column;gap:10px;max-height:60vh;overflow-y:auto"></div>
    <div style="display:flex;gap:8px;margin-top:16px;justify-content:flex-end">
      <button id="modal-export-btn" class="btn btn-secondary btn-sm">⬇ Export JSON</button>
      <button class="btn btn-ghost btn-sm" data-close-modal="modal-chat-log">Close</button>
    </div>
  </div>
</div>`;
}
