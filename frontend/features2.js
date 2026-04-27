/* =====================================================
   AmpAI — Logic for Tasks, Notes, Analytics, Network
   ===================================================== */

// ═══════════════════════════════════════════════════
// TASKS
// ═══════════════════════════════════════════════════
let _tasksBound = false;

async function tasksLoad() {
  await _fetchTasks();
  if (_tasksBound) return;
  _tasksBound = true;

  document.getElementById('new-task-btn')?.addEventListener('click', () => _openTaskModal());
  document.getElementById('save-task-btn')?.addEventListener('click', _saveTask);
  document.getElementById('task-filter')?.addEventListener('change', _fetchTasks);
}

async function _fetchTasks() {
  const filter = document.getElementById('task-filter')?.value || 'all';
  const url = filter === 'all' ? '/api/tasks' : `/api/tasks?status=${filter}`;
  const { ok, data } = await apiJSON(url);
  if (!ok) return;
  const tasks = data.tasks || [];
  _renderKanban(tasks);
}

function _renderKanban(tasks) {
  const cols = { todo: [], in_progress: [], done: [] };
  tasks.forEach(t => {
    const s = t.status === 'in_progress' ? 'in_progress' : (t.status || 'todo');
    if (cols[s]) cols[s].push(t);
  });
  ['todo', 'in_progress', 'done'].forEach(status => {
    const col = document.getElementById('col-' + status);
    const count = document.getElementById('count-' + status);
    if (count) count.textContent = cols[status].length;
    if (!col) return;
    col.innerHTML = cols[status].length
      ? cols[status].map(t => _taskCard(t)).join('')
      : `<div style="text-align:center;padding:24px;color:var(--muted);font-size:.8rem;border:1px dashed var(--border);border-radius:8px">Empty</div>`;
  });
}

function _taskCard(t) {
  const priColor = { high: '#ef4444', medium: '#f59e0b', low: '#10b981' }[t.priority] || '#94a3b8';
  const due = t.due_at ? new Date(t.due_at).toLocaleDateString() : '';
  const overdue = t.due_at && new Date(t.due_at) < new Date() && t.status !== 'done';
  return `
<div style="background:var(--bg-3);border:1px solid var(--border);border-radius:10px;padding:12px 14px;
  cursor:pointer;transition:all .18s;border-left:3px solid ${priColor}"
  onmouseenter="this.style.borderColor='rgba(99,102,241,.5)'"
  onmouseleave="this.style.borderColor='var(--border)'"
  onclick="_openTaskModal(${JSON.stringify(t).replace(/"/g,'&quot;')})">
  <div style="font-weight:600;font-size:.875rem;margin-bottom:6px;line-height:1.4">${_esc(t.title)}</div>
  ${t.description ? `<div style="font-size:.78rem;color:var(--muted);margin-bottom:8px;line-height:1.4">${_esc(t.description).slice(0,80)}${t.description.length>80?'…':''}</div>` : ''}
  <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
    <span style="font-size:.7rem;font-weight:600;padding:2px 7px;border-radius:999px;
      background:${priColor}22;color:${priColor};border:1px solid ${priColor}44">${t.priority||'medium'}</span>
    ${due ? `<span style="font-size:.72rem;color:${overdue?'var(--red)':'var(--muted)'}">${overdue?'⚠️ ':''} ${due}</span>` : ''}
    <button onclick="event.stopPropagation();_deleteTask(${t.id})" style="margin-left:auto;background:none;border:none;
      cursor:pointer;color:var(--muted);font-size:.85rem;padding:2px 4px" title="Delete">🗑</button>
  </div>
</div>`;
}

function _openTaskModal(task = null) {
  document.getElementById('task-modal-title').textContent = task ? 'Edit Task' : 'New Task';
  document.getElementById('task-edit-id').value = task?.id || '';
  document.getElementById('task-title-inp').value = task?.title || '';
  document.getElementById('task-desc-inp').value = task?.description || '';
  document.getElementById('task-priority-inp').value = task?.priority || 'medium';
  document.getElementById('task-status-inp').value = task?.status || 'todo';
  if (task?.due_at) {
    try { document.getElementById('task-due-inp').value = new Date(task.due_at).toISOString().slice(0,16); } catch {}
  } else {
    document.getElementById('task-due-inp').value = '';
  }
  openModal('modal-task');
  setTimeout(() => document.getElementById('task-title-inp')?.focus(), 100);
}

async function _saveTask() {
  const id    = document.getElementById('task-edit-id').value;
  const title = document.getElementById('task-title-inp').value.trim();
  if (!title) { toast('Title is required', 'error'); return; }
  const payload = {
    title,
    description: document.getElementById('task-desc-inp').value.trim(),
    priority:    document.getElementById('task-priority-inp').value,
    status:      document.getElementById('task-status-inp').value,
    due_at:      document.getElementById('task-due-inp').value || null,
  };
  const url    = id ? `/api/tasks/${id}` : '/api/tasks';
  const method = id ? 'PATCH' : 'POST';
  const { ok } = await apiJSON(url, { method, body: JSON.stringify(payload) });
  if (ok) { toast(id ? 'Task updated' : 'Task created', 'success'); closeModal('modal-task'); _fetchTasks(); }
  else toast('Failed to save task', 'error');
}

async function _deleteTask(id) {
  if (!confirm('Delete this task?')) return;
  const { ok } = await apiJSON(`/api/tasks/${id}`, { method: 'DELETE' });
  if (ok) { toast('Task deleted', 'success'); _fetchTasks(); }
  else toast('Failed to delete', 'error');
}

// ═══════════════════════════════════════════════════
// NOTES
// ═══════════════════════════════════════════════════
let _notesBound = false;
let _currentNoteId = null;
let _noteAutoSave = null;

async function notesLoad() {
  await _fetchNotes();
  if (_notesBound) return;
  _notesBound = true;

  document.getElementById('new-note-btn')?.addEventListener('click', _newNote);
  document.getElementById('note-save-btn')?.addEventListener('click', _saveNote);
  document.getElementById('note-delete-btn')?.addEventListener('click', _deleteNote);
  document.getElementById('note-ai-btn')?.addEventListener('click', _noteAISummary);
  document.getElementById('note-pin-btn')?.addEventListener('click', _toggleNotePin);

  document.getElementById('note-search')?.addEventListener('input', e => _fetchNotes(e.target.value));

  // Word count
  document.getElementById('note-body-inp')?.addEventListener('input', () => {
    const words = (document.getElementById('note-body-inp').value.trim().match(/\S+/g)||[]).length;
    const wc = document.getElementById('note-words');
    if (wc) wc.textContent = `${words} word${words!==1?'s':''}`;
    _setNoteStatus('Unsaved');
    clearTimeout(_noteAutoSave);
    _noteAutoSave = setTimeout(_saveNote, 3000);
  });
}

async function _fetchNotes(query = '') {
  const url = query ? `/api/notes?q=${encodeURIComponent(query)}` : '/api/notes';
  const { ok, data } = await apiJSON(url);
  const list = document.getElementById('notes-list');
  if (!list) return;
  if (!ok) { list.innerHTML = '<div style="padding:12px;color:var(--red);font-size:.8rem">Failed to load notes</div>'; return; }
  const notes = data.notes || [];
  if (!notes.length) {
    list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--muted);font-size:.82rem">No notes yet.<br>Create your first note!</div>';
    return;
  }
  list.innerHTML = notes.map(n => `
    <div class="note-item ${n.id === _currentNoteId ? 'note-active' : ''}" data-nid="${n.id}"
      style="padding:10px 12px;border-radius:8px;cursor:pointer;margin-bottom:2px;transition:all .15s;
      border-left:2px solid ${n.id===_currentNoteId?'var(--accent)':'transparent'}"
      onmouseenter="if(this.dataset.nid!='${_currentNoteId}')this.style.background='var(--bg-3)'"
      onmouseleave="if(this.dataset.nid!='${_currentNoteId}')this.style.background=''"
      onclick="_loadNote(${n.id})">
      <div style="font-size:.85rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
        ${n.pinned?'📌 ':''} ${_esc(n.title)||'Untitled'}
      </div>
      <div style="font-size:.72rem;color:var(--muted);margin-top:3px;display:flex;align-items:center;gap:6px">
        ${n.tag ? `<span style="background:rgba(99,102,241,.15);color:#818cf8;border:1px solid rgba(99,102,241,.25);padding:1px 6px;border-radius:999px;font-size:.68rem">${n.tag}</span>` : ''}
        <span>${_fmtRelative(n.updated_at)}</span>
      </div>
    </div>`).join('');
}

async function _loadNote(id) {
  const { ok, data } = await apiJSON(`/api/notes/${id}`);
  if (!ok) { toast('Failed to load note', 'error'); return; }
  _currentNoteId = id;
  document.getElementById('note-current-id').value = id;
  document.getElementById('note-title-inp').value = data.title || '';
  document.getElementById('note-body-inp').value = data.body || '';
  document.getElementById('note-tag-inp').value = data.tag || '';
  document.getElementById('note-pin-btn').textContent = data.pinned ? '📌 Unpin' : '📌 Pin';
  document.getElementById('note-empty').style.display = 'none';
  document.getElementById('note-editor-wrap').style.display = 'flex';
  const words = (data.body||'').trim().split(/\s+/).filter(Boolean).length;
  const wc = document.getElementById('note-words');
  if (wc) wc.textContent = `${words} words`;
  _setNoteStatus('Saved');
  _fetchNotes();
}

function _newNote() {
  _currentNoteId = null;
  document.getElementById('note-current-id').value = '';
  document.getElementById('note-title-inp').value = '';
  document.getElementById('note-body-inp').value = '';
  document.getElementById('note-tag-inp').value = '';
  document.getElementById('note-pin-btn').textContent = '📌 Pin';
  document.getElementById('note-empty').style.display = 'none';
  document.getElementById('note-editor-wrap').style.display = 'flex';
  document.getElementById('note-title-inp')?.focus();
  _setNoteStatus('New');
}

async function _saveNote() {
  const id    = document.getElementById('note-current-id').value;
  const title = document.getElementById('note-title-inp').value.trim() || 'Untitled';
  const body  = document.getElementById('note-body-inp').value;
  const tag   = document.getElementById('note-tag-inp').value;
  const payload = { title, body, tag };
  const url    = id ? `/api/notes/${id}` : '/api/notes';
  const method = id ? 'PUT' : 'POST';
  const { ok, data } = await apiJSON(url, { method, body: JSON.stringify(payload) });
  if (ok) {
    if (!id && data.id) {
      _currentNoteId = data.id;
      document.getElementById('note-current-id').value = data.id;
    }
    _setNoteStatus('Saved ✓');
    _fetchNotes();
  } else {
    _setNoteStatus('Save failed!');
  }
}

async function _deleteNote() {
  const id = document.getElementById('note-current-id').value;
  if (!id) { _newNote(); return; }
  if (!confirm('Delete this note?')) return;
  const { ok } = await apiJSON(`/api/notes/${id}`, { method: 'DELETE' });
  if (ok) {
    _currentNoteId = null;
    document.getElementById('note-empty').style.display = 'flex';
    document.getElementById('note-editor-wrap').style.display = 'none';
    toast('Note deleted', 'success');
    _fetchNotes();
  }
}

async function _toggleNotePin() {
  const id = document.getElementById('note-current-id').value;
  if (!id) return;
  const { ok, data } = await apiJSON(`/api/notes/${id}/pin`, { method: 'POST' });
  if (ok) {
    document.getElementById('note-pin-btn').textContent = data.pinned ? '📌 Unpin' : '📌 Pin';
    _fetchNotes();
  }
}

async function _noteAISummary() {
  const title = document.getElementById('note-title-inp').value;
  const body  = document.getElementById('note-body-inp').value;
  if (!body.trim()) { toast('Write something first', 'info'); return; }
  const panel = document.getElementById('note-ai-panel');
  const content = document.getElementById('note-ai-content');
  if (panel) { panel.style.display = 'flex'; content.textContent = 'Analyzing…'; }
  const { ok, data } = await apiJSON('/api/chat', {
    method: 'POST',
    body: JSON.stringify({
      session_id: 'notes_ai_' + (_currentNoteId || 'new'),
      message: `Please summarize and extract key insights from this note titled "${title}":\n\n${body.slice(0, 3000)}`,
      model_type: document.getElementById('model-select')?.value || 'ollama',
      memory_mode: 'none',
    }),
  });
  if (content) content.textContent = ok ? (data.response || 'No response') : 'AI unavailable. Check model config.';
}

function noteFormat(type) {
  const ta = document.getElementById('note-body-inp');
  if (!ta) return;
  const sel = ta.value.substring(ta.selectionStart, ta.selectionEnd);
  const map = { bold: `**${sel||'bold text'}**`, italic: `*${sel||'italic text'}*`,
    h1: `\n# ${sel||'Heading 1'}`, h2: `\n## ${sel||'Heading 2'}`,
    ul: `\n- ${sel||'item'}`, code: `\`${sel||'code'}\``, hr: '\n---\n' };
  const ins = map[type] || sel;
  const start = ta.selectionStart;
  ta.value = ta.value.slice(0, start) + ins + ta.value.slice(ta.selectionEnd);
  ta.focus();
  ta.selectionStart = ta.selectionEnd = start + ins.length;
  ta.dispatchEvent(new Event('input'));
}

function _setNoteStatus(s) {
  const el = document.getElementById('note-status');
  if (el) { el.textContent = s; el.style.color = s.includes('fail') ? 'var(--red)' : s.includes('✓') ? 'var(--green)' : 'var(--muted)'; }
}

// ═══════════════════════════════════════════════════
// ANALYTICS
// ═══════════════════════════════════════════════════
let _analyticsBound = false;

async function analyticsLoad() {
  await _fetchAnalytics();
  if (_analyticsBound) return;
  _analyticsBound = true;
  document.getElementById('refresh-analytics-btn')?.addEventListener('click', _fetchAnalytics);
  document.getElementById('analytics-range')?.addEventListener('change', _fetchAnalytics);
}

async function _fetchAnalytics() {
  // Sessions & memories
  const [s1, s2, s3, s4] = await Promise.all([
    apiJSON('/api/sessions?limit=200'),
    apiJSON('/api/admin/core-memories').catch(() => ({ ok: false, data: {} })),
    apiJSON('/api/tasks').catch(() => ({ ok: false, data: {} })),
    apiJSON('/api/analytics/summary').catch(() => ({ ok: false, data: {} })),
  ]);

  const sessions = s1.data?.sessions || [];
  const memories = s2.data?.core_memories || [];
  const tasks    = s3.data?.tasks || [];
  const summary  = s4.data || {};

  // KPIs
  _setKPI('kpi-messages', summary.total_messages ?? sessions.length * 8);
  _setKPI('kpi-sessions', s1.data?.total ?? sessions.length);
  _setKPI('kpi-memories', memories.length);
  _setKPI('kpi-tasks',    tasks.filter(t => t.status === 'done').length);

  // Category chart
  const cats = {};
  sessions.forEach(s => { const c = s.category || 'Uncategorized'; cats[c] = (cats[c]||0) + 1; });
  const total = sessions.length || 1;
  const sorted = Object.entries(cats).sort((a,b) => b[1]-a[1]).slice(0,6);
  const catEl = document.getElementById('category-chart');
  if (catEl) {
    catEl.innerHTML = sorted.length
      ? sorted.map(([cat, n]) => {
          const pct = Math.round((n/total)*100);
          const colors = ['#818cf8','#10b981','#f59e0b','#ef4444','#06b6d4','#c084fc'];
          const ci = sorted.findIndex(x=>x[0]===cat);
          return `<div>
            <div style="display:flex;justify-content:space-between;font-size:.78rem;margin-bottom:4px">
              <span style="color:var(--text)">${_esc(cat)}</span>
              <span style="color:var(--muted)">${n} (${pct}%)</span>
            </div>
            <div style="height:6px;background:var(--bg-4);border-radius:99px;overflow:hidden">
              <div style="height:100%;width:${pct}%;background:${colors[ci%colors.length]};border-radius:99px;transition:width .6s"></div>
            </div>
          </div>`;
        }).join('')
      : '<div style="color:var(--muted);font-size:.8rem">No sessions yet</div>';
  }

  // Activity bar chart (last 7 days)
  const actEl = document.getElementById('activity-chart');
  if (actEl) {
    const days = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date(); d.setDate(d.getDate() - i);
      const key = d.toISOString().slice(0,10);
      const label = d.toLocaleDateString('en',{weekday:'short'});
      const count = sessions.filter(s => (s.updated_at||'').startsWith(key)).length;
      days.push({ label, count });
    }
    const max = Math.max(...days.map(d=>d.count), 1);
    actEl.innerHTML = `<div style="display:flex;align-items:flex-end;gap:4px;height:140px;padding:0 4px;flex:1">
      ${days.map(d => `
        <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px">
          <div style="font-size:.65rem;color:var(--muted)">${d.count||''}</div>
          <div style="width:100%;background:rgba(99,102,241,.7);border-radius:4px 4px 0 0;
            height:${Math.max(4, Math.round((d.count/max)*110))}px;transition:height .4s;
            ${d.count===0?'background:var(--bg-4)':''}"></div>
          <div style="font-size:.67rem;color:var(--muted)">${d.label}</div>
        </div>`).join('')}
    </div>`;
  }

  // Recent memories
  const memEl = document.getElementById('recent-memories-list');
  if (memEl) {
    memEl.innerHTML = memories.length
      ? memories.slice(0,5).map(m => `
          <div style="display:flex;align-items:flex-start;gap:8px;padding:6px 0;border-bottom:1px solid var(--border)">
            <span style="color:#818cf8;flex-shrink:0">🧠</span>
            <span style="font-size:.82rem;color:var(--text);line-height:1.4">${_esc(m.fact)}</span>
          </div>`).join('')
      : '<div style="color:var(--muted);font-size:.8rem">No core memories yet.</div>';
  }

  // Model usage placeholder
  const modEl = document.getElementById('model-usage-list');
  if (modEl) {
    const cfg = (await apiJSON('/api/admin/configs').catch(()=>({ok:false,data:{}}))).data;
    const def = cfg?.default_model || 'ollama';
    modEl.innerHTML = `<div style="display:flex;align-items:center;gap:10px;padding:6px 0">
      <span style="font-size:1rem">🤖</span>
      <div style="flex:1">
        <div style="font-size:.85rem;font-weight:600">${def}</div>
        <div style="font-size:.75rem;color:var(--muted)">Default provider</div>
      </div>
      <span class="badge badge-green">Active</span>
    </div>`;
  }
}

function _setKPI(id, val) {
  const el = document.getElementById(id);
  if (el) { const v = el.querySelector('.stat-value'); if (v) v.textContent = val ?? '—'; }
}

// ═══════════════════════════════════════════════════
// NETWORK MONITOR
// ═══════════════════════════════════════════════════
let _networkBound = false;

async function networkLoad() {
  await _fetchNetworkTargets();
  if (_networkBound) return;
  _networkBound = true;
  document.getElementById('add-target-btn')?.addEventListener('click', _addNetworkTarget);
  document.getElementById('refresh-network-btn')?.addEventListener('click', _fetchNetworkTargets);
  document.getElementById('run-sweep-btn')?.addEventListener('click', _runSweep);
  document.getElementById('net-ip-inp')?.addEventListener('keydown', e => { if (e.key==='Enter') _addNetworkTarget(); });
}

async function _fetchNetworkTargets() {
  const { ok, data } = await apiJSON('/api/network/targets');
  const tbody = document.getElementById('network-targets-tbody');
  if (!tbody) return;
  if (!ok || !data.targets?.length) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:32px">No targets configured. Add a host above.</td></tr>';
    return;
  }
  tbody.innerHTML = data.targets.map(t => `
    <tr>
      <td style="font-weight:600">${_esc(t.name)}</td>
      <td><code style="font-size:.82rem">${_esc(t.ip_address)}</code></td>
      <td><span class="badge ${t.status==='Online'?'badge-green':t.status==='Offline'?'badge-red':'badge-yellow'}">${t.status||'Unknown'}</span></td>
      <td style="font-size:.82rem;color:var(--muted)">${t.avg_ping ? t.avg_ping+'ms' : '—'}</td>
      <td style="font-size:.75rem;color:var(--muted)">${_fmtRelative(t.last_checked)}</td>
      <td style="display:flex;gap:6px">
        <button class="btn btn-secondary btn-sm" onclick="_pingTarget(${t.id},'${_esc(t.name)}','${_esc(t.ip_address)}')">Ping</button>
        <button class="btn btn-danger btn-sm" onclick="_deleteTarget(${t.id})">Delete</button>
      </td>
    </tr>`).join('');
}

async function _addNetworkTarget() {
  const name = document.getElementById('net-name-inp')?.value.trim();
  const ip   = document.getElementById('net-ip-inp')?.value.trim();
  const st   = document.getElementById('net-add-status');
  if (!name || !ip) { if (st) { st.textContent='Name and IP are required'; st.style.color='var(--red)'; } return; }
  const { ok } = await apiJSON('/api/network/targets', { method:'POST', body:JSON.stringify({name,ip_address:ip}) });
  if (st) { st.textContent=ok?'Target added!':'Failed to add'; st.style.color=ok?'var(--green)':'var(--red)'; setTimeout(()=>st.textContent='',3000); }
  if (ok) { document.getElementById('net-name-inp').value=''; document.getElementById('net-ip-inp').value=''; _fetchNetworkTargets(); }
}

async function _deleteTarget(id) {
  if (!confirm('Remove this target?')) return;
  const { ok } = await apiJSON(`/api/network/targets/${id}`, { method:'DELETE' });
  if (ok) _fetchNetworkTargets();
}

async function _pingTarget(id, name, ip) {
  document.getElementById('ping-target-name').textContent = name;
  document.getElementById('ping-result').textContent = `Pinging ${ip}…`;
  openModal('modal-ping');
  const { ok, data } = await apiJSON(`/api/network/ping/${id}`);
  document.getElementById('ping-result').textContent = ok
    ? `Host: ${ip}\nStatus: ${data.status}\nLatency: ${data.avg_ping}ms\nDetails: ${data.details}`
    : 'Ping failed or host unreachable.';
}

async function _runSweep() {
  const btn = document.getElementById('run-sweep-btn');
  if (btn) { btn.disabled=true; btn.textContent='Running…'; }
  const { ok } = await apiJSON('/api/network/sweep', { method:'POST' });
  if (btn) { btn.disabled=false; btn.textContent='▶ Run Sweep Now'; }
  toast(ok?'Sweep complete':'Sweep failed', ok?'success':'error');
  _fetchNetworkTargets();
}

// ═══════════════════════════════════════════════════
// SHARED UTILITIES
// ═══════════════════════════════════════════════════
function _esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function _fmtRelative(iso) {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60000)   return 'just now';
  if (diff < 3600000) return Math.floor(diff/60000) + 'm ago';
  if (diff < 86400000) return Math.floor(diff/3600000) + 'h ago';
  return Math.floor(diff/86400000) + 'd ago';
}
