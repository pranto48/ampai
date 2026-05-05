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
    <button id="fb-restore-preview-btn" class="btn btn-secondary"
      style="padding:10px 22px;font-size:.9rem;font-weight:600">
      🔎 Preview Restore
    </button>
    <button id="fb-restore-btn" class="btn btn-danger"
      style="padding:10px 22px;font-size:.9rem;font-weight:600">
      ♻️ Restore Selected
    </button>
    <label style="font-size:.82rem;color:var(--muted);display:flex;align-items:center;gap:6px">
      <input type="checkbox" id="fb-r-dry-run"> Dry run (no writes)
    </label>
    <span id="fb-restore-status" style="font-size:.84rem;color:var(--muted)"></span>
  </div>
  <div id="fb-restore-result" style="display:none;margin-top:14px;background:var(--bg-3);border:1px solid var(--border);border-radius:10px;padding:14px;font-size:.82rem"></div>
</div>`;
}

// ── Agent Memory Vault Page ────────────────────────────────────────────────
function buildAgentMemoryViewerPage() {
  return `
<div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:14px;margin-bottom:24px">
  <div>
    <h2 style="font-size:1.18rem;font-weight:800;display:flex;align-items:center;gap:10px">
      🔐 Agent Memory Vault
      <span id="amv-pb-badge" style="padding:3px 11px;border-radius:999px;font-size:.72rem;font-weight:600;
        background:rgba(99,102,241,.15);color:#818cf8;border:1px solid rgba(99,102,241,.3);display:none">
        — files
      </span>
    </h2>
    <p style="font-size:.82rem;color:var(--muted);margin-top:4px">
      View every memory saved by Antigravity (AI assistant) and AmpAI's own core memory store.
    </p>
  </div>
  <button id="amv-refresh-btn" class="btn btn-secondary btn-sm">↻ Refresh</button>
</div>

<!-- Stats strip -->
<div id="amv-stats-strip" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:22px">
  <div class="stat-card"><div id="amv-stat-pb-files" class="stat-value">—</div><div class="stat-label">PB Files</div></div>
  <div class="stat-card"><div id="amv-stat-pb-readable" class="stat-value">—</div><div class="stat-label">Decoded</div></div>
  <div class="stat-card"><div id="amv-stat-pb-strings" class="stat-value">—</div><div class="stat-label">Memory Strings</div></div>
  <div class="stat-card"><div id="amv-stat-core" class="stat-value">—</div><div class="stat-label">Core Memories</div></div>
</div>

<!-- Tabs -->
<div style="display:flex;gap:4px;margin-bottom:18px;background:var(--bg-2);padding:4px;border-radius:10px;width:fit-content">
  <button id="amv-tab-pb"   class="btn btn-primary  btn-sm amv-tab" data-tab="pb"   style="border-radius:7px">🤖 Antigravity (.pb)</button>
  <button id="amv-tab-core" class="btn btn-ghost btn-sm amv-tab" data-tab="core" style="border-radius:7px">🧠 AmpAI Core</button>
</div>

<!-- Search bar -->
<div style="display:flex;gap:8px;margin-bottom:16px">
  <input id="amv-search" class="input" placeholder="Search memories…" style="flex:1;max-width:400px"/>
  <button id="amv-search-btn" class="btn btn-secondary btn-sm">Search</button>
</div>

<!-- Antigravity PB panel -->
<div id="amv-panel-pb">
  <div id="amv-pb-permission-note" style="display:none;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.3);
    border-radius:10px;padding:14px 18px;font-size:.84rem;color:#fbbf24;margin-bottom:16px">
    ⚠️ <strong>Permission Denied</strong> — macOS TCC is blocking access to <code>~/.gemini/antigravity/implicit/</code>.<br>
    Grant full-disk access to your terminal/Python in <em>System Preferences → Privacy & Security → Full Disk Access</em>.
  </div>
  <div id="amv-pb-list" style="display:flex;flex-direction:column;gap:14px">
    <div class="card" style="text-align:center;color:var(--muted);padding:32px">
      <div style="font-size:2rem;margin-bottom:8px">⏳</div>Loading Antigravity memories…
    </div>
  </div>
</div>

<!-- AmpAI Core panel -->
<div id="amv-panel-core" style="display:none">
  <div class="card" style="margin-bottom:16px">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
      <input id="amv-new-fact" class="input" placeholder="Add a core memory fact…" style="flex:1"/>
      <button id="amv-add-fact-btn" class="btn btn-primary btn-sm">＋ Add</button>
    </div>
  </div>
  <div id="amv-core-list" style="display:flex;flex-direction:column;gap:8px">
    <div style="text-align:center;color:var(--muted);padding:24px">Loading…</div>
  </div>
</div>`;
}

// ── Telegram Integration Card (improved wizard) ─────────────────────────────
function buildTelegramIntegrationCard() {
  return `
<div class="card" id="telegram-integration-card" style="margin-top:16px;border:1px solid rgba(99,102,241,.2)">
  <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:14px">
    <div style="display:flex;align-items:center;gap:10px">
      <span style="font-size:1.5rem">✈️</span>
      <div>
        <div class="card-title" style="margin-bottom:2px">Telegram Bot</div>
        <div style="font-size:.75rem;color:var(--muted)">Connect your bot · choose polling or webhook</div>
      </div>
    </div>
    <label style="display:flex;align-items:center;gap:8px;font-size:.82rem;cursor:pointer">
      <input id="tg-enabled" type="checkbox" style="accent-color:var(--accent);width:16px;height:16px"/>
      <span>Enable</span>
    </label>
  </div>

  <!-- Status strip -->
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;background:var(--bg-3);border:1px solid var(--border);border-radius:10px;padding:10px 14px;margin-bottom:16px;font-size:.8rem">
    <div><span style="color:var(--muted)">Integration:</span> <span id="tg-status-enabled" class="badge badge-yellow">Unknown</span></div>
    <div><span style="color:var(--muted)">Token:</span> <span id="tg-status-token" class="badge badge-yellow">Unknown</span></div>
    <div><span style="color:var(--muted)">Mode:</span> <span id="tg-status-mode" class="badge" style="background:rgba(99,102,241,.15);color:#818cf8;border:1px solid rgba(99,102,241,.3)">—</span></div>
    <div><span style="color:var(--muted)">Bot:</span> <span id="tg-status-botname" style="color:var(--text)">—</span></div>
    <div><span style="color:var(--muted)">Last test:</span> <span id="tg-status-last-test">—</span></div>
  </div>

  <!-- Step 1: Token -->
  <div style="margin-bottom:14px;padding:12px 14px;background:var(--bg-2);border:1px solid var(--border);border-radius:10px">
    <div style="font-size:.78rem;font-weight:700;color:var(--muted);margin-bottom:8px">① BOT TOKEN</div>
    <div style="display:grid;grid-template-columns:1fr auto;gap:8px;align-items:end">
      <div>
        <label class="lbl">Bot Token <span style="font-size:.7rem;color:var(--muted)">(from @BotFather)</span></label>
        <input id="tg-bot-token" type="password" class="input" placeholder="123456:ABCDef…" autocomplete="new-password"/>
        <div id="tg-token-hint" style="font-size:.72rem;color:var(--muted);margin-top:4px">Leave blank to keep existing token.</div>
      </div>
      <button id="tg-test-btn" class="btn btn-secondary btn-sm" style="white-space:nowrap">🔍 Verify Token</button>
    </div>
  </div>

  <!-- Step 2: Mode -->
  <div style="margin-bottom:14px;padding:12px 14px;background:var(--bg-2);border:1px solid var(--border);border-radius:10px">
    <div style="font-size:.78rem;font-weight:700;color:var(--muted);margin-bottom:10px">② CONNECTION MODE</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <div id="tg-mode-polling-card" style="border:2px solid rgba(99,102,241,.3);border-radius:10px;padding:12px;cursor:pointer;transition:all .2s"
        onclick="_tgSelectMode('polling')">
        <div style="font-weight:700;font-size:.875rem;margin-bottom:4px">🔄 Long Polling</div>
        <div style="font-size:.72rem;color:var(--muted);line-height:1.5">Best for local / Docker setups. No public URL required. Server pulls updates automatically.</div>
        <button id="tg-enable-polling-btn" class="btn btn-primary btn-sm" style="margin-top:10px;width:100%">Enable Polling</button>
      </div>
      <div id="tg-mode-webhook-card" style="border:2px solid var(--border);border-radius:10px;padding:12px;cursor:pointer;transition:all .2s"
        onclick="_tgSelectMode('webhook')">
        <div style="font-weight:700;font-size:.875rem;margin-bottom:4px">🌐 Webhook</div>
        <div style="font-size:.72rem;color:var(--muted);line-height:1.5">Best for public HTTPS servers. Telegram pushes updates to your URL instantly.</div>
        <div style="margin-top:10px">
          <input id="tg-webhook-url" class="input" placeholder="https://example.com/api/integrations/telegram/webhook" style="font-size:.78rem"/>
          <input id="tg-secret-token" type="password" class="input" placeholder="optional webhook secret" autocomplete="new-password" style="font-size:.78rem;margin-top:6px"/>
        </div>
      </div>
    </div>
  </div>

  <!-- Step 3: Actions -->
  <div style="padding:12px 14px;background:var(--bg-2);border:1px solid var(--border);border-radius:10px;margin-bottom:14px">
    <div style="font-size:.78rem;font-weight:700;color:var(--muted);margin-bottom:10px">③ SAVE & CONNECT</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button id="tg-save-btn" class="btn btn-primary btn-sm">💾 Save Settings</button>
      <button id="tg-register-btn" class="btn btn-secondary btn-sm">🔗 Register Webhook</button>
      <button id="tg-webhook-info-btn" class="btn btn-ghost btn-sm">📡 Webhook Info</button>
      <button id="tg-remove-btn" class="btn btn-danger btn-sm">⛔ Disconnect</button>
    </div>
  </div>

  <!-- Webhook Info Panel (collapsed) -->
  <div id="tg-webhook-info-panel" style="display:none;background:var(--bg-3);border:1px solid var(--border);border-radius:10px;padding:12px 14px;font-size:.8rem">
    <div style="font-weight:700;margin-bottom:8px">📡 Live Webhook Status</div>
    <div id="tg-webhook-info-content" style="color:var(--muted)">Loading…</div>
  </div>
</div>`;
}


// ── Telegram Chats Page ──────────────────────────────────────────────────────
function buildTelegramChatsPage() {
  return `
<div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:14px;margin-bottom:24px">
  <div>
    <h2 style="font-size:1.18rem;font-weight:800;display:flex;align-items:center;gap:10px">
      ✈️ Telegram Chats
      <span id="tgc-count-badge" style="padding:3px 10px;border-radius:999px;font-size:.72rem;font-weight:600;
        background:rgba(99,102,241,.15);color:#818cf8;border:1px solid rgba(99,102,241,.3);display:none">0 chats</span>
    </h2>
    <p style="font-size:.82rem;color:var(--muted);margin-top:4px">
      Browse and search all Telegram conversations flowing through your AmpAI bot.
    </p>
  </div>
  <div style="display:flex;gap:8px">
    <button id="tgc-refresh-btn" class="btn btn-secondary btn-sm">↻ Refresh</button>
    <button id="tgc-settings-btn" class="btn btn-ghost btn-sm" onclick="navigate('settings')">⚙️ Bot Settings</button>
  </div>
</div>

<!-- Stats row -->
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:20px">
  <div class="stat-card"><div id="tgc-stat-total" class="stat-value">—</div><div class="stat-label">Total Chats</div></div>
  <div class="stat-card"><div id="tgc-stat-active" class="stat-value">—</div><div class="stat-label">Active (7d)</div></div>
  <div class="stat-card"><div id="tgc-stat-pending" class="stat-value">—</div><div class="stat-label">Pending Updates</div></div>
  <div class="stat-card"><div id="tgc-stat-mode"  class="stat-value" style="font-size:.85rem">—</div><div class="stat-label">Mode</div></div>
</div>

<!-- Telegram connection health bar -->
<div id="tgc-health-bar" style="display:none;margin-bottom:16px;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.25);
  border-radius:10px;padding:10px 14px;font-size:.82rem;color:#fbbf24">
  <strong>⚠️ Webhook Error:</strong> <span id="tgc-health-error"></span>
</div>

<!-- Search + filter -->
<div style="display:flex;gap:8px;margin-bottom:16px">
  <input id="tgc-search" class="input" placeholder="Search by session ID or user…" style="flex:1;max-width:380px"/>
</div>

<!-- Chat list -->
<div id="tgc-list" style="display:flex;flex-direction:column;gap:10px">
  <div class="card" style="text-align:center;color:var(--muted);padding:32px">
    <div style="font-size:2.5rem;margin-bottom:10px">✈️</div>
    Loading Telegram chats…
  </div>
</div>

<!-- Chat log modal (shared with admin) -->
<div id="modal-tg-chat" class="modal-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.65);z-index:9999;align-items:center;justify-content:center">
  <div style="background:var(--bg-2);border:1px solid var(--border);border-radius:16px;width:min(96vw,720px);max-height:88vh;display:flex;flex-direction:column">
    <div style="padding:16px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between">
      <div>
        <div style="font-weight:700;font-size:.95rem" id="tgc-modal-title">Telegram Chat</div>
        <div style="font-size:.75rem;color:var(--muted);margin-top:2px" id="tgc-modal-session-id"></div>
      </div>
      <button onclick="document.getElementById('modal-tg-chat').style.display='none'" class="btn btn-ghost btn-sm">✕ Close</button>
    </div>
    <div id="tgc-modal-body" style="flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px">
      <div style="text-align:center;color:var(--muted);padding:24px">Loading…</div>
    </div>
  </div>
</div>`;
}

// ── AmpAI Skills Page ────────────────────────────────────────────────────────
function buildSkillsPage() {
  return `
<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:24px">
  <div>
    <h2 style="font-size:1.15rem;font-weight:700;display:flex;align-items:center;gap:10px">
      🔧 Agent Skills
      <span id="skills-count-badge" style="padding:3px 10px;border-radius:999px;font-size:.72rem;font-weight:600;background:rgba(99,102,241,.15);color:#818cf8;border:1px solid rgba(99,102,241,.3);display:none"></span>
    </h2>
    <p style="font-size:.82rem;color:var(--muted);margin-top:4px">Reusable AI skills. Auto-created from complex tasks and self-improving over time.</p>
  </div>
  <div style="display:flex;gap:8px">
    <input id="skill-search" class="input" placeholder="Search skills…" style="width:200px"/>
    <button id="skill-new-btn" class="btn btn-primary btn-sm">＋ New Skill</button>
  </div>
</div>

<div id="skills-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px">
  <div class="card" style="text-align:center;color:var(--muted);padding:32px">Loading skills…</div>
</div>

<!-- Skill Create/Edit Modal -->
<div id="modal-skill" class="modal-overlay">
  <div class="modal-box" style="max-width:640px">
    <div class="modal-header">
      <div class="modal-title" id="skill-modal-title">New Skill</div>
      <button class="modal-close" data-close-modal="modal-skill">✕</button>
    </div>
    <input type="hidden" id="skill-edit-id"/>
    <div class="fg"><label class="lbl">Skill Name *</label><input id="skill-name-inp" class="input" placeholder="e.g. summarize_email"/></div>
    <div class="fg"><label class="lbl">Description</label><input id="skill-desc-inp" class="input" placeholder="What does this skill do?"/></div>
    <div class="fg"><label class="lbl">Skill Prompt * <span style="font-size:.72rem;color:var(--muted)">(system instructions for this skill)</span></label>
      <textarea id="skill-prompt-inp" class="input" rows="7" style="resize:vertical;font-family:monospace;font-size:.82rem" placeholder="You are an expert at… Your task is to…"></textarea></div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      <div class="fg"><label class="lbl">Trigger Pattern</label><input id="skill-trigger-inp" class="input" placeholder="regex or keyword"/></div>
      <div class="fg"><label class="lbl">Tags</label><input id="skill-tags-inp" class="input" placeholder="coding, analysis…"/></div>
    </div>
    <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:4px">
      <button class="btn btn-ghost btn-sm" data-close-modal="modal-skill">Cancel</button>
      <button id="skill-save-btn" class="btn btn-primary btn-sm">💾 Save Skill</button>
    </div>
  </div>
</div>

<!-- Skill Run Modal -->
<div id="modal-skill-run" class="modal-overlay">
  <div class="modal-box" style="max-width:580px">
    <div class="modal-header">
      <div class="modal-title" id="skill-run-modal-title">Run Skill</div>
      <button class="modal-close" data-close-modal="modal-skill-run">✕</button>
    </div>
    <input type="hidden" id="skill-run-id"/>
    <div class="fg"><label class="lbl">Your Message / Input</label>
      <textarea id="skill-run-message" class="input" rows="4" style="resize:vertical" placeholder="What do you want the skill to process?"></textarea></div>
    <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:4px">
      <button class="btn btn-ghost btn-sm" data-close-modal="modal-skill-run">Cancel</button>
      <button id="skill-run-exec-btn" class="btn btn-primary btn-sm" onclick="_executeSkillRun()">▶ Execute</button>
    </div>
    <div id="skill-run-result-wrap" style="display:none;margin-top:14px">
      <div style="font-size:.78rem;font-weight:700;color:var(--muted);margin-bottom:6px">Result</div>
      <pre id="skill-run-result" style="background:var(--bg-3);border:1px solid var(--border);border-radius:10px;padding:14px;font-size:.82rem;white-space:pre-wrap;max-height:300px;overflow-y:auto;font-family:inherit;line-height:1.6"></pre>
    </div>
  </div>
</div>`;
}

// ── AmpAI Memory Nudges Page ─────────────────────────────────────────────────
function buildNudgesPage() {
  return `
<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:24px">
  <div>
    <h2 style="font-size:1.15rem;font-weight:700;display:flex;align-items:center;gap:10px">
      🧠 Memory Nudges
      <span id="nudge-count-badge" style="padding:3px 10px;border-radius:999px;font-size:.72rem;font-weight:600;background:rgba(239,68,68,.15);color:#f87171;border:1px solid rgba(239,68,68,.3);display:none">0</span>
    </h2>
    <p style="font-size:.82rem;color:var(--muted);margin-top:4px">AmpAI reviews your conversations and suggests facts worth remembering. Accept to save, dismiss to skip.</p>
  </div>
  <div style="display:flex;gap:8px">
    <button id="nudge-refresh-btn" class="btn btn-secondary btn-sm">↻ Refresh</button>
    <button id="nudge-curate-btn" class="btn btn-primary btn-sm">✨ Curate Now</button>
  </div>
</div>

<div style="background:rgba(99,102,241,.07);border:1px solid rgba(99,102,241,.2);border-radius:12px;padding:14px 18px;margin-bottom:20px;font-size:.84rem">
  <strong>How it works:</strong> Every 6 hours, AmpAI uses the local LLM to review recent sessions and extract facts worth remembering.
  Click <strong>Curate Now</strong> to run immediately for your current session.
</div>

<div id="nudge-list" style="display:flex;flex-direction:column;gap:8px">
  <div class="card" style="text-align:center;color:var(--muted);padding:32px">Loading nudges…</div>
</div>`;
}

// ── AmpAI Session Recall Page ─────────────────────────────────────────────────
function buildRecallPage() {
  return `
<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:24px">
  <div>
    <h2 style="font-size:1.15rem;font-weight:700">🔍 Session Recall</h2>
    <p style="font-size:.82rem;color:var(--muted);margin-top:4px">Search across all your past conversations using FTS5 full-text search with LLM summarization.</p>
  </div>
  <button id="recall-reindex-btn" class="btn btn-secondary btn-sm">⚡ Re-index</button>
</div>

<div class="card" style="margin-bottom:20px">
  <div id="recall-stats" style="font-size:.82rem;color:var(--muted);margin-bottom:12px">Loading stats…</div>
  <div style="display:flex;gap:8px">
    <input id="recall-query" class="input" placeholder="Search past conversations… (e.g. Python project, user preferences, meeting notes)" style="flex:1"/>
    <button id="recall-search-btn" class="btn btn-primary">🔍 Search</button>
  </div>
</div>

<div id="recall-results" style="display:flex;flex-direction:column;gap:8px">
  <div style="text-align:center;color:var(--muted);font-size:.85rem;padding:32px">Enter a query to search past conversations.</div>
</div>`;
}

// ── AmpAI Identity / Status Page ─────────────────────────────────────────────
function buildAmpaiStatusPage() {
  return `
<div style="margin-bottom:24px">
  <h2 style="font-size:1.15rem;font-weight:700">🤖 AmpAI Agent Status</h2>
  <p style="font-size:.82rem;color:var(--muted);margin-top:4px">Local model status, capabilities, and autonomous agent overview.</p>
</div>

<div id="ampai-identity-card" class="card" style="margin-bottom:20px">
  <div style="text-align:center;color:var(--muted);padding:24px">Loading AmpAI identity…</div>
</div>

<div class="grid-2" style="gap:16px">
  <div class="card">
    <div class="card-title">🧠 Memory System</div>
    <div style="font-size:.84rem;line-height:1.8;color:var(--muted)">
      • Core memories persist facts across all sessions<br>
      • Memory nudges suggest important facts every 6h<br>
      • FTS5 cross-session search indexes every chat turn<br>
      • LLM summarizes past context into each prompt
    </div>
    <div style="margin-top:12px;display:flex;gap:8px">
      <button class="btn btn-secondary btn-sm" onclick="navigate('nudges')">View Nudges</button>
      <button class="btn btn-secondary btn-sm" onclick="navigate('recall')">Search Sessions</button>
    </div>
  </div>
  <div class="card">
    <div class="card-title">🔧 Skill System</div>
    <div style="font-size:.84rem;line-height:1.8;color:var(--muted)">
      • Skills are reusable AI prompt templates<br>
      • Auto-created after complex multi-step tasks<br>
      • Self-improving: prompts rewritten when success rate drops<br>
      • Run any skill on-demand with custom inputs
    </div>
    <div style="margin-top:12px">
      <button class="btn btn-secondary btn-sm" onclick="navigate('skills')">Manage Skills</button>
    </div>
  </div>
</div>`;
}

async function ampaiStatusLoad() {
  const card = document.getElementById('ampai-identity-card');
  if (!card) return;
  const { ok, data } = await apiJSON('/api/ampai/identity');
  if (!ok) { card.innerHTML = '<div style="color:var(--red)">Failed to load AmpAI identity</div>'; return; }
  const alive = data.local && data.local.available;
  const models = (data.local && data.local.models) || [];
  const features = data.features || {};
  card.innerHTML = `
<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
  <div style="width:64px;height:64px;border-radius:50%;background:linear-gradient(135deg,#6366f1,#8b5cf6);display:flex;align-items:center;justify-content:center;font-size:2rem">🤖</div>
  <div>
    <div style="font-size:1.25rem;font-weight:800">${_esc(data.name || 'AmpAI')} <span style="font-size:.75rem;color:var(--muted);font-weight:400">v${_esc(data.version || '1.0.0')}</span></div>
    <div style="font-size:.84rem;color:var(--muted);margin-top:2px">${_esc(data.tagline || '')}</div>
    <div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">
      <span class="badge ${alive ? 'badge-green' : 'badge-yellow'}">${alive ? '🟢 Ollama Online' : '🟡 Default Mode'}</span>
      ${alive ? '<span class="badge" style="background:rgba(99,102,241,.15);color:#818cf8;border:1px solid rgba(99,102,241,.3)">' + _esc(data.local.recommended_model||'—') + '</span>' : ''}
    </div>
  </div>
</div>
${alive ? '' : `
<div style="margin-top:16px;background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.25);border-radius:10px;padding:12px 16px;font-size:.84rem;color:#fbbf24">
  ⚠️ <strong>Ollama not detected.</strong> AmpAI is running in <strong>default mode</strong> — using the built-in response engine.
  <a href="https://ollama.ai" target="_blank" style="color:#818cf8;margin-left:8px">Install Ollama →</a>
</div>`}
<div style="margin-top:16px;display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px;font-size:.8rem">
  ${Object.entries(features).map(([k,v]) => `<div style="display:flex;align-items:center;gap:6px"><span style="color:${v?'var(--green)':'var(--red)'}">${v?'✅':'❌'}</span><span style="color:var(--muted)">${_esc(k.replace(/_/g,' '))}</span></div>`).join('')}
</div>
${models.length ? `<div style="margin-top:14px;font-size:.8rem;color:var(--muted)"><strong>Available models:</strong> ${models.map(m=>'<code style="background:var(--bg-3);padding:2px 6px;border-radius:4px">'+_esc(m)+'</code>').join(' ')}</div>` : ''}`;
}
