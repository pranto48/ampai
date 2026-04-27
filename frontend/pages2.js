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
