/* =====================================================
   AmpAI — NEW PAGES: Tasks, Notes, Analytics, Network
   ===================================================== */

// ── Tasks Page ─────────────────────────────────────
function buildTasksPage() {
  return `
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
  <h2 style="font-size:1.15rem;font-weight:700">✅ Task Manager</h2>
  <div style="display:flex;gap:8px">
    <select id="task-filter" style="padding:6px 10px;border-radius:8px;background:rgba(0,0,0,.25);
      border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:.82rem;outline:none">
      <option value="all">All Tasks</option>
      <option value="todo">Todo</option>
      <option value="in_progress">In Progress</option>
      <option value="done">Done</option>
    </select>
    <button id="new-task-btn" class="btn btn-primary btn-sm">＋ New Task</button>
  </div>
</div>

<!-- Kanban Board -->
<div id="task-board" style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;min-height:400px">
  <!-- Todo Column -->
  <div style="background:rgba(15,23,42,.6);border:1px solid var(--border);border-radius:12px;padding:14px">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
      <div style="width:8px;height:8px;border-radius:50%;background:var(--muted)"></div>
      <span style="font-weight:600;font-size:.85rem;color:var(--muted)">TODO</span>
      <span id="count-todo" style="margin-left:auto;background:var(--bg-3);border:1px solid var(--border);
        border-radius:999px;padding:2px 8px;font-size:.72rem;color:var(--muted)">0</span>
    </div>
    <div id="col-todo" class="task-col" data-status="todo" style="display:flex;flex-direction:column;gap:8px;min-height:80px"></div>
  </div>
  <!-- In Progress Column -->
  <div style="background:rgba(15,23,42,.6);border:1px solid rgba(245,158,11,.15);border-radius:12px;padding:14px">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
      <div style="width:8px;height:8px;border-radius:50%;background:var(--yellow)"></div>
      <span style="font-weight:600;font-size:.85rem;color:var(--yellow)">IN PROGRESS</span>
      <span id="count-in_progress" style="margin-left:auto;background:rgba(245,158,11,.1);border:1px solid rgba(245,158,11,.25);
        border-radius:999px;padding:2px 8px;font-size:.72rem;color:var(--yellow)">0</span>
    </div>
    <div id="col-in_progress" class="task-col" data-status="in_progress" style="display:flex;flex-direction:column;gap:8px;min-height:80px"></div>
  </div>
  <!-- Done Column -->
  <div style="background:rgba(15,23,42,.6);border:1px solid rgba(16,185,129,.15);border-radius:12px;padding:14px">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">
      <div style="width:8px;height:8px;border-radius:50%;background:var(--green)"></div>
      <span style="font-weight:600;font-size:.85rem;color:var(--green)">DONE</span>
      <span id="count-done" style="margin-left:auto;background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.25);
        border-radius:999px;padding:2px 8px;font-size:.72rem;color:var(--green)">0</span>
    </div>
    <div id="col-done" class="task-col" data-status="done" style="display:flex;flex-direction:column;gap:8px;min-height:80px"></div>
  </div>
</div>

<!-- New Task Modal -->
<div id="modal-task" class="modal-overlay">
  <div class="modal-box" style="max-width:480px">
    <div class="modal-header">
      <div class="modal-title" id="task-modal-title">New Task</div>
      <button class="modal-close" data-close-modal="modal-task">✕</button>
    </div>
    <input type="hidden" id="task-edit-id"/>
    <div class="fg">
      <label class="lbl">Title *</label>
      <input id="task-title-inp" class="input" placeholder="Task title"/>
    </div>
    <div class="fg">
      <label class="lbl">Description</label>
      <textarea id="task-desc-inp" class="input" rows="3" placeholder="Details…" style="resize:vertical"></textarea>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div class="fg">
        <label class="lbl">Priority</label>
        <select id="task-priority-inp" class="input">
          <option value="low">🟢 Low</option>
          <option value="medium" selected>🟡 Medium</option>
          <option value="high">🔴 High</option>
        </select>
      </div>
      <div class="fg">
        <label class="lbl">Status</label>
        <select id="task-status-inp" class="input">
          <option value="todo">Todo</option>
          <option value="in_progress">In Progress</option>
          <option value="done">Done</option>
        </select>
      </div>
    </div>
    <div class="fg">
      <label class="lbl">Due Date</label>
      <input id="task-due-inp" type="datetime-local" class="input"/>
    </div>
    <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:4px">
      <button class="btn btn-ghost btn-sm" data-close-modal="modal-task">Cancel</button>
      <button id="save-task-btn" class="btn btn-primary btn-sm">Save Task</button>
    </div>
  </div>
</div>`;
}

function buildMemoryInboxPage() {
  return `
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
  <h2 style="font-size:1.15rem;font-weight:700">📥 Memory Inbox</h2>
  <div style="display:flex;gap:8px">
    <input id="mi-search" class="input" placeholder="Search memories..." style="min-width:220px"/>
    <select id="mi-status-filter" class="input" style="width:auto;padding:6px 10px">
      <option value="pending">Pending</option>
      <option value="approved">Approved</option>
      <option value="rejected">Rejected</option>
      <option value="all">All</option>
    </select>
    <button id="mi-refresh-btn" class="btn btn-secondary btn-sm">↻ Refresh</button>
  </div>
</div>
<div class="card" style="margin-bottom:14px">
  <label class="lbl">Capture candidate memory manually</label>
  <div style="display:flex;gap:8px">
    <input id="mi-capture-text" class="input" placeholder="e.g., I prefer short bullet-point answers."/>
    <button id="mi-capture-btn" class="btn btn-primary btn-sm">Add</button>
  </div>
</div>
<div class="card" style="overflow-x:auto">
  <table class="tbl">
    <thead>
      <tr><th>Candidate</th><th>Session</th><th>Confidence</th><th>Status</th><th>Created</th><th>Action</th></tr>
    </thead>
    <tbody id="mi-body">
      <tr><td colspan="6" style="text-align:center;color:var(--muted);padding:24px">Loading…</td></tr>
    </tbody>
  </table>
</div>`;
}

function buildPersonasPage() {
  return `
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
  <h2 style="font-size:1.15rem;font-weight:700">🎭 Persona Library</h2>
  <button id="persona-new-btn" class="btn btn-primary btn-sm">＋ New Persona</button>
</div>
<div class="card" style="margin-bottom:14px">
  <div style="font-size:.82rem;color:var(--muted)">Select a persona from chat topbar. Personas prepend reusable instructions to your request.</div>
</div>
<div id="persona-list" class="grid-2" style="gap:12px"></div>

<div id="modal-persona" class="modal-overlay">
  <div class="modal-box" style="max-width:680px">
    <div class="modal-header">
      <div class="modal-title" id="persona-modal-title">New Persona</div>
      <button class="modal-close" data-close-modal="modal-persona">✕</button>
    </div>
    <input id="persona-edit-id" type="hidden"/>
    <div class="fg"><label class="lbl">Name</label><input id="persona-name" class="input"/></div>
    <div class="fg"><label class="lbl">Tags (comma-separated)</label><input id="persona-tags" class="input" placeholder="coding, research"/></div>
    <div class="fg"><label class="lbl">System Prompt</label><textarea id="persona-prompt" class="input" rows="8" style="resize:vertical"></textarea></div>
    <label style="display:flex;align-items:center;gap:8px;margin-bottom:8px"><input id="persona-default" type="checkbox" style="accent-color:var(--accent)"/> Set as default</label>
    <div style="display:flex;justify-content:flex-end;gap:8px">
      <button class="btn btn-ghost btn-sm" data-close-modal="modal-persona">Cancel</button>
      <button id="persona-save-btn" class="btn btn-primary btn-sm">Save Persona</button>
    </div>
  </div>
</div>`;
}

function buildDailyBriefPage() {
  return `
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
  <h2 style="font-size:1.15rem;font-weight:700">📰 Daily Brief</h2>
  <div style="display:flex;gap:8px">
    <button id="pull-email-context-btn" class="btn btn-secondary btn-sm">📧 Pull Email Context</button>
    <button id="pull-calendar-context-btn" class="btn btn-secondary btn-sm">📅 Pull Calendar Context</button>
    <button id="brief-refresh-btn" class="btn btn-primary btn-sm">↻ Refresh</button>
  </div>
</div>
<div class="grid-2" style="gap:16px">
  <div class="card"><div class="card-title">Open Tasks</div><div id="brief-open-tasks"></div></div>
  <div class="card"><div class="card-title">Pending Replies</div><div id="brief-pending-replies"></div></div>
  <div class="card"><div class="card-title">Recent Important Memories</div><div id="brief-memories"></div></div>
  <div class="card"><div class="card-title">Pending Memory Candidates</div><div id="brief-candidates"></div></div>
</div>`;
}

function buildWorkspacePage() {
  return `
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
  <h2 style="font-size:1.15rem;font-weight:700">👥 Team Workspaces</h2>
  <button id="workspace-new-btn" class="btn btn-primary btn-sm">＋ New Workspace</button>
</div>
<div id="workspace-list" class="grid-2" style="gap:12px"></div>

<div id="modal-workspace" class="modal-overlay">
  <div class="modal-box" style="max-width:620px">
    <div class="modal-header">
      <div class="modal-title">New Workspace</div>
      <button class="modal-close" data-close-modal="modal-workspace">✕</button>
    </div>
    <div class="fg"><label class="lbl">Name</label><input id="workspace-name" class="input"/></div>
    <div class="fg"><label class="lbl">Description</label><input id="workspace-description" class="input"/></div>
    <div class="fg"><label class="lbl">Members (username:role, comma separated)</label><input id="workspace-members" class="input" placeholder="alice:editor, bob:viewer"/></div>
    <div style="display:flex;justify-content:flex-end;gap:8px">
      <button class="btn btn-ghost btn-sm" data-close-modal="modal-workspace">Cancel</button>
      <button id="workspace-save-btn" class="btn btn-primary btn-sm">Create</button>
    </div>
  </div>
</div>`;
}

// ── Notes Page ─────────────────────────────────────
function buildNotesPage() {
  return `
<div style="display:flex;height:100%;gap:0">
  <!-- Notes sidebar -->
  <div style="width:260px;min-width:260px;background:var(--bg-2);border-right:1px solid var(--border);
    display:flex;flex-direction:column">
    <div style="padding:14px;border-bottom:1px solid var(--border)">
      <button id="new-note-btn" style="width:100%;padding:10px;border-radius:8px;border:none;cursor:pointer;
        background:var(--accent);color:#fff;font-family:inherit;font-size:.875rem;font-weight:600">
        ＋ New Note
      </button>
      <input id="note-search" placeholder="Search notes…" style="width:100%;margin-top:8px;
        padding:8px 10px;border-radius:8px;background:rgba(0,0,0,.2);border:1px solid var(--border);
        color:var(--text);font-family:inherit;font-size:.82rem;outline:none"/>
    </div>
    <div id="notes-list" style="flex:1;overflow-y:auto;padding:8px">
      <div style="padding:20px;text-align:center;color:var(--muted);font-size:.85rem">Loading notes…</div>
    </div>
  </div>

  <!-- Note editor -->
  <div style="flex:1;display:flex;flex-direction:column;min-width:0">
    <div id="note-empty" style="flex:1;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:12px;color:var(--muted)">
      <div style="font-size:3rem">📝</div>
      <div style="font-size:.95rem">Select a note or create a new one</div>
      <button onclick="document.getElementById('new-note-btn').click()" class="btn btn-secondary btn-sm">＋ New Note</button>
    </div>
    <div id="note-editor-wrap" style="display:none;flex:1;flex-direction:column">
      <div style="padding:16px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px">
        <input id="note-title-inp" placeholder="Note title…" style="flex:1;background:none;border:none;
          color:var(--text);font-family:inherit;font-size:1.05rem;font-weight:700;outline:none"/>
        <div style="display:flex;gap:6px">
          <button id="note-ai-btn" class="btn btn-secondary btn-sm" title="Ask AI about this note">✨ AI Summary</button>
          <button id="note-pin-btn" class="btn btn-secondary btn-sm" title="Pin note">📌</button>
          <button id="note-save-btn" class="btn btn-primary btn-sm">💾 Save</button>
          <button id="note-delete-btn" class="btn btn-danger btn-sm">🗑</button>
        </div>
      </div>
      <div style="padding:8px;border-bottom:1px solid var(--border);display:flex;gap:4px;flex-wrap:wrap">
        <button onclick="noteFormat('bold')" class="btn btn-ghost btn-sm" style="font-weight:700">B</button>
        <button onclick="noteFormat('italic')" class="btn btn-ghost btn-sm" style="font-style:italic">I</button>
        <button onclick="noteFormat('h1')" class="btn btn-ghost btn-sm">H1</button>
        <button onclick="noteFormat('h2')" class="btn btn-ghost btn-sm">H2</button>
        <button onclick="noteFormat('ul')" class="btn btn-ghost btn-sm">• List</button>
        <button onclick="noteFormat('code')" class="btn btn-ghost btn-sm" style="font-family:monospace">Code</button>
        <button onclick="noteFormat('hr')" class="btn btn-ghost btn-sm">—</button>
        <select id="note-tag-inp" style="margin-left:auto;padding:4px 8px;border-radius:6px;
          background:rgba(0,0,0,.25);border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:.78rem;outline:none">
          <option value="">Tag…</option>
          <option value="work">💼 Work</option>
          <option value="personal">👤 Personal</option>
          <option value="idea">💡 Idea</option>
          <option value="research">🔬 Research</option>
          <option value="meeting">📅 Meeting</option>
        </select>
      </div>
      <textarea id="note-body-inp" placeholder="Start writing… (Markdown supported)" style="flex:1;
        background:none;border:none;color:var(--text);font-family:inherit;font-size:.925rem;
        outline:none;resize:none;padding:20px;line-height:1.8"></textarea>
      <div style="padding:8px 20px;border-top:1px solid var(--border);display:flex;align-items:center;gap:12px">
        <span id="note-status" style="font-size:.75rem;color:var(--muted)">Unsaved</span>
        <span id="note-words" style="font-size:.75rem;color:var(--muted)">0 words</span>
        <input type="hidden" id="note-current-id"/>
      </div>
    </div>
    <!-- AI Summary panel -->
    <div id="note-ai-panel" style="display:none;width:320px;background:var(--bg-2);border-left:1px solid var(--border);
      padding:18px;overflow-y:auto;flex-direction:column;gap:12px">
      <div style="font-weight:700;font-size:.9rem;margin-bottom:8px">✨ AI Insights</div>
      <div id="note-ai-content" style="font-size:.875rem;color:var(--muted);line-height:1.6">
        Click "AI Summary" to analyze this note.
      </div>
    </div>
  </div>
</div>`;
}

// ── Analytics Page ─────────────────────────────────
function buildAnalyticsPage() {
  return `
<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:18px">
  <h2 style="font-size:1.15rem;font-weight:700">📊 Memory Analytics</h2>
  <div style="display:flex;gap:8px;flex-wrap:wrap">
    <button id="analytics-refresh-btn" class="btn btn-secondary btn-sm">↻ Refresh</button>
    <button id="analytics-export-csv-btn" class="btn btn-secondary btn-sm">⬇ Export CSV</button>
  </div>
</div>
<div style="display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;background:var(--bg-2);border:1px solid var(--border);border-radius:12px;padding:14px;margin-bottom:18px">
  <div style="min-width:140px"><label class="lbl">From</label><input id="analytics-date-from" type="date" class="input"/></div>
  <div style="min-width:140px"><label class="lbl">To</label><input id="analytics-date-to" type="date" class="input"/></div>
  <div style="min-width:130px"><label class="lbl">Scope</label><select id="analytics-owner-scope" class="input"><option value="mine">Mine</option><option value="shared">Shared</option><option value="all">All</option></select></div>
  <div style="min-width:120px"><label class="lbl">Stale days</label><input id="analytics-stale-days" type="number" min="1" value="30" class="input"/></div>
  <button id="analytics-apply-btn" class="btn btn-primary">Apply</button>
</div>
<div class="grid-4" style="gap:14px;margin-bottom:18px">
  <div class="stat-card"><div id="kpi-memory-writes" class="stat-value">—</div><div class="stat-label">Memory Writes</div></div>
  <div class="stat-card"><div id="kpi-retrieval-hits" class="stat-value">—</div><div class="stat-label">Retrieval Hits</div></div>
  <div class="stat-card"><div id="kpi-stale-count" class="stat-value">—</div><div class="stat-label">Stale Memories</div></div>
  <div class="stat-card"><div id="kpi-top-category" class="stat-value">—</div><div class="stat-label">Top Category</div></div>
</div>
<div class="grid-2" style="gap:16px;margin-bottom:18px">
  <div class="card"><div class="card-title">Memory Writes per Day</div><div id="analytics-writes-trend"></div></div>
  <div class="card"><div class="card-title">Retrieval Hits per Day</div><div id="analytics-retrieval-trend"></div></div>
</div>
<div class="grid-2" style="gap:16px">
  <div class="card"><div class="card-title">Top Categories</div><div id="analytics-top-categories"></div></div>
  <div class="card" style="overflow:auto">
    <div class="card-title">Stale Memories</div>
    <table class="tbl">
      <thead><tr><th>Session</th><th>Category</th><th>Owner</th><th>Updated</th><th>Last Retrieval</th></tr></thead>
      <tbody id="analytics-stale-body"><tr><td colspan="5" style="text-align:center;color:var(--muted)">Loading…</td></tr></tbody>
    </table>
  </div>
</div>`;
}

// ── Network Monitor Page ────────────────────────────
function buildNetworkPage() {
  return `
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
  <h2 style="font-size:1.15rem;font-weight:700">🌐 Network Monitor</h2>
  <div style="display:flex;gap:8px">
    <button id="run-sweep-btn" class="btn btn-primary btn-sm">▶ Run Sweep Now</button>
    <button id="refresh-network-btn" class="btn btn-secondary btn-sm">↻ Refresh</button>
  </div>
</div>

<!-- Add target form -->
<div class="card" style="margin-bottom:20px">
  <div class="card-title">Add Network Target</div>
  <div style="display:flex;gap:10px;flex-wrap:wrap">
    <input id="net-name-inp" class="input" placeholder="Name (e.g. Home Router)" style="flex:1;min-width:150px"/>
    <input id="net-ip-inp" class="input" placeholder="IP Address (e.g. 192.168.1.1)" style="flex:1;min-width:160px"/>
    <button id="add-target-btn" class="btn btn-primary">Add Target</button>
  </div>
  <div id="net-add-status" style="font-size:.85rem;margin-top:8px"></div>
</div>

<!-- Targets list -->
<div class="card" style="overflow-x:auto">
  <div class="card-title">Monitored Targets</div>
  <table class="tbl">
    <thead>
      <tr><th>Name</th><th>IP Address</th><th>Status</th><th>Latency</th><th>Last Check</th><th>Actions</th></tr>
    </thead>
    <tbody id="network-targets-tbody">
      <tr><td colspan="6" style="text-align:center;color:var(--muted);padding:32px">Loading…</td></tr>
    </tbody>
  </table>
</div>

<!-- Sweep history -->
<div class="card" style="margin-top:16px">
  <div class="card-title">Recent Sweep Reports</div>
  <div id="sweep-history" style="font-size:.875rem;color:var(--muted)">No reports yet.</div>
</div>

<!-- Ping modal -->
<div id="modal-ping" class="modal-overlay">
  <div class="modal-box" style="max-width:400px">
    <div class="modal-header">
      <div class="modal-title">Ping Result — <span id="ping-target-name"></span></div>
      <button class="modal-close" data-close-modal="modal-ping">✕</button>
    </div>
    <pre id="ping-result" style="background:rgba(0,0,0,.4);padding:14px;border-radius:8px;
      font-size:.82rem;white-space:pre-wrap;max-height:300px;overflow-y:auto">Pinging…</pre>
    <div style="text-align:right;margin-top:12px">
      <button class="btn btn-ghost btn-sm" data-close-modal="modal-ping">Close</button>
    </div>
  </div>
</div>`;
}

// ── Docker Update Page ──────────────────────────────
function buildDockerUpdatePage() {
  return `
<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:24px">
  <div>
    <h2 style="font-size:1.15rem;font-weight:700;margin-bottom:4px">🐳 Docker Update Manager</h2>
    <p style="font-size:.82rem;color:var(--muted)">Pull the latest AmpAI code from GitHub and restart — all your data stays safe.</p>
  </div>
  <span id="update-badge" style="padding:5px 14px;border-radius:999px;font-size:.8rem;font-weight:600;
    background:rgba(100,116,139,.15);color:var(--muted);border:1px solid rgba(100,116,139,.3)">Checking…</span>
</div>

<!-- Version card -->
<div class="card" style="margin-bottom:20px">
  <div class="card-title" style="margin-bottom:14px">📦 Version Info</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px">
    <div style="background:var(--bg-3);border:1px solid var(--border);border-radius:10px;padding:14px">
      <div style="font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">Current Commit</div>
      <code id="update-current-commit" style="font-size:.95rem;color:var(--text)">—</code>
    </div>
    <div style="background:var(--bg-3);border:1px solid var(--border);border-radius:10px;padding:14px">
      <div style="font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px">Latest on GitHub</div>
      <code id="update-latest-commit" style="font-size:.95rem;color:var(--text)">—</code>
    </div>
  </div>
  <div id="update-version-status" style="font-size:.84rem;color:var(--muted);margin-bottom:14px">Checking versions…</div>
  <div style="display:flex;gap:10px;flex-wrap:wrap">
    <button id="update-check-btn" class="btn btn-secondary">↻ Check for Updates</button>
    <button id="update-trigger-btn" class="btn btn-primary" disabled
      style="background:linear-gradient(135deg,#6366f1,#8b5cf6);border:none;padding:10px 22px;font-size:.9rem;font-weight:600">
      🚀 Update AmpAI
    </button>
  </div>
</div>

<!-- What's preserved notice -->
<div style="background:rgba(16,185,129,.07);border:1px solid rgba(16,185,129,.2);border-radius:12px;padding:14px 18px;margin-bottom:20px;font-size:.84rem">
  <div style="font-weight:700;color:#10b981;margin-bottom:8px">🔒 What's preserved during update</div>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:6px;color:var(--muted)">
    <span>✓ All chat sessions &amp; history</span>
    <span>✓ Core memories &amp; memory inbox</span>
    <span>✓ Users &amp; authentication</span>
    <span>✓ Tasks &amp; notes</span>
    <span>✓ API keys &amp; settings</span>
    <span>✓ PostgreSQL database</span>
    <span>✓ Redis session data</span>
    <span>✓ Uploaded files</span>
  </div>
</div>

<!-- Live update log -->
<div id="update-log-wrap" style="display:none;margin-bottom:20px">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
    <div style="font-weight:700;font-size:.9rem">📋 Update Log</div>
    <span id="update-state-badge" style="padding:3px 10px;border-radius:999px;font-size:.75rem;font-weight:600;
      background:rgba(99,102,241,.15);color:#818cf8;border:1px solid rgba(99,102,241,.3)">Idle</span>
  </div>
  <pre id="update-log-box" style="background:rgba(0,0,0,.5);border:1px solid var(--border);border-radius:10px;
    padding:16px;font-size:.78rem;font-family:monospace;color:#86efac;min-height:120px;max-height:320px;
    overflow-y:auto;white-space:pre-wrap;word-break:break-all;line-height:1.7"></pre>
</div>

<!-- Code Backups -->
<div class="card">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
    <div class="card-title">🗂 Code Backups</div>
    <button id="update-backups-refresh-btn" class="btn btn-secondary btn-sm">↻ Refresh</button>
  </div>
  <p style="font-size:.8rem;color:var(--muted);margin-bottom:14px">
    A backup of the previous code is created automatically before each update.
    Remove old backups to free disk space.
  </p>
  <div style="overflow-x:auto">
    <table class="tbl">
      <thead>
        <tr>
          <th>Timestamp</th>
          <th>Commit</th>
          <th>Size</th>
          <th>Age</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody id="update-backups-tbody">
        <tr><td colspan="5" style="text-align:center;color:var(--muted);padding:24px">Loading…</td></tr>
      </tbody>
    </table>
  </div>
</div>`;
}

// ── Full Backup / Restore Page ───────────────────────────
function buildFullBackupPage() {
  return `
<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:24px">
  <div>
    <h2 style="font-size:1.15rem;font-weight:700;margin-bottom:4px">💾 Full Backup &amp; Restore</h2>
    <p style="font-size:.82rem;color:var(--muted)">Category-wise memory backup (5 GB slots) + full system backup with AI configs, users &amp; settings.</p>
  </div>
  <span id="fb-slot-badge" style="padding:5px 14px;border-radius:999px;font-size:.8rem;font-weight:600;
    background:rgba(99,102,241,.15);color:#818cf8;border:1px solid rgba(99,102,241,.3)">Slot: 5 GB max</span>
</div>

<!-- Memory categories overview -->
<div class="card" style="margin-bottom:20px">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
    <div class="card-title">📂 Memory Categories</div>
    <button id="fb-cats-refresh-btn" class="btn btn-secondary btn-sm">↻ Refresh</button>
  </div>
  <div style="overflow-x:auto">
    <table class="tbl">
      <thead><tr><th>Category</th><th>Sessions</th><th>Messages</th><th>Memories</th></tr></thead>
      <tbody id="fb-cats-tbody">
        <tr><td colspan="4" style="text-align:center;color:var(--muted);padding:20px">Loading…</td></tr>
      </tbody>
    </table>
  </div>
</div>

<!-- Create backup -->
<div class="card" style="margin-bottom:20px">
  <div class="card-title" style="margin-bottom:12px">🚀 Create Full Backup</div>
  <div style="font-size:.82rem;color:var(--muted);margin-bottom:14px">
    Backs up: chat history · AI memories · core memories · users · AI model API keys · app settings · personas · tasks.
    Large memory data is split into 5 GB slots automatically.
  </div>
  <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <button id="fb-create-btn" class="btn btn-primary"
      style="background:linear-gradient(135deg,#6366f1,#8b5cf6);border:none;padding:10px 22px;font-size:.9rem;font-weight:600">
      💾 Create Full Backup
    </button>
    <span id="fb-create-status" style="font-size:.84rem;color:var(--muted)"></span>
  </div>
  <div id="fb-manifest-wrap" style="display:none;margin-top:16px;background:var(--bg-3);border:1px solid var(--border);border-radius:10px;padding:14px;font-size:.82rem">
    <div style="font-weight:700;margin-bottom:8px">📋 Backup Manifest</div>
    <div id="fb-manifest-body" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px"></div>
  </div>
</div>

<!-- Saved backups list -->
<div class="card" style="margin-bottom:20px">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px">
    <div class="card-title">🗂 Saved Backups</div>
    <button id="fb-list-refresh-btn" class="btn btn-secondary btn-sm">↻ Refresh</button>
  </div>
  <div style="overflow-x:auto">
    <table class="tbl">
      <thead>
        <tr><th>File</th><th>Created</th><th>Slots</th><th>Sessions</th><th>Memories</th><th>Users</th><th>Size</th><th>Actions</th></tr>
      </thead>
      <tbody id="fb-list-tbody">
        <tr><td colspan="8" style="text-align:center;color:var(--muted);padding:20px">Loading…</td></tr>
      </tbody>
    </table>
  </div>
</div>

<!-- Restore -->
<div class="card">
  <div class="card-title" style="margin-bottom:12px">♻️ Restore from Backup</div>
  <div style="margin-bottom:12px">
    <label style="font-size:.82rem;color:var(--muted);display:block;margin-bottom:6px">Select saved backup file:</label>
    <select id="fb-restore-select" class="input" style="max-width:480px">
      <option value="">— choose a backup —</option>
    </select>
  </div>
  <div style="margin-bottom:12px">
    <label style="font-size:.82rem;color:var(--muted);display:block;margin-bottom:6px">Or upload downloaded backup ZIP:</label>
    <input id="fb-restore-upload" type="file" accept=".zip,application/zip" class="input" style="max-width:480px" />
  </div>
  <div style="font-size:.82rem;font-weight:600;margin-bottom:8px;color:var(--text)">Restore sections:</div>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px;margin-bottom:16px;font-size:.84rem">
    <label><input type="checkbox" id="fb-r-chats" checked> Chat histories</label>
    <label><input type="checkbox" id="fb-r-memories" checked> AI memories</label>
    <label><input type="checkbox" id="fb-r-core" checked> Core memories</label>
    <label><input type="checkbox" id="fb-r-users" checked> Users</label>
    <label><input type="checkbox" id="fb-r-configs" checked> AI keys &amp; settings</label>
    <label><input type="checkbox" id="fb-r-personas" checked> Personas</label>
    <label><input type="checkbox" id="fb-r-tasks" checked> Tasks</label>
  </div>
  <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <button id="fb-restore-btn" class="btn btn-danger"
      style="padding:10px 22px;font-size:.9rem;font-weight:600">
      ♻️ Restore Selected
    </button>
    <span id="fb-restore-status" style="font-size:.84rem;color:var(--muted)"></span>
  </div>
  <div id="fb-restore-result" style="display:none;margin-top:14px;background:var(--bg-3);border:1px solid var(--border);border-radius:10px;padding:14px;font-size:.82rem"></div>
</div>`;
}

// ── Telegram Integration Card (for admin/settings embedding) ───────────────
function buildTelegramIntegrationCard() {
  return `
<div class="card" id="telegram-integration-card" style="margin-top:16px">
  <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:10px">
    <div class="card-title">📨 Telegram</div>
    <label style="display:flex;align-items:center;gap:8px;font-size:.82rem;color:var(--muted)">
      <input id="tg-enabled" type="checkbox" style="accent-color:var(--accent)"/>
      Enable
    </label>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px">
    <div class="fg" style="margin:0">
      <label class="lbl">Bot token</label>
      <input id="tg-bot-token" type="password" class="input" placeholder="123456:ABCDEF..." autocomplete="off"/>
    </div>
    <div class="fg" style="margin:0">
      <label class="lbl">Webhook URL</label>
      <input id="tg-webhook-url" class="input" placeholder="https://example.com/api/integrations/telegram/webhook"/>
    </div>
    <div class="fg" style="margin:0;grid-column:1 / -1;">
      <label class="lbl">Secret token (optional)</label>
      <input id="tg-secret-token" type="password" class="input" placeholder="optional webhook secret" autocomplete="off"/>
    </div>
  </div>

  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
    <button id="tg-save-btn" class="btn btn-primary btn-sm">Save</button>
    <button id="tg-test-btn" class="btn btn-secondary btn-sm">Test Bot</button>
    <button id="tg-register-btn" class="btn btn-secondary btn-sm">Connect Webhook</button>
    <button id="tg-remove-btn" class="btn btn-danger btn-sm">Disconnect</button>
  </div>

  <div style="display:grid;grid-template-columns:repeat(3,minmax(140px,1fr));gap:8px;background:var(--bg-3);border:1px solid var(--border);border-radius:10px;padding:10px;font-size:.8rem">
    <div><span style="color:var(--muted)">Status:</span> <span id="tg-status-enabled" class="badge badge-yellow">Unknown</span></div>
    <div><span style="color:var(--muted)">Token:</span> <span id="tg-status-token" class="badge badge-yellow">Unknown</span></div>
    <div><span style="color:var(--muted)">Last test:</span> <span id="tg-status-last-test">—</span></div>
  </div>
</div>`;
}
