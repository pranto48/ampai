/* =====================================================
   AmpAI — Logic for Tasks, Notes, Analytics, Network
   ===================================================== */

let _memoryInboxBound = false;
let _personasBound = false;
let _dailyBriefBound = false;
let _workspaceBound = false;

async function memoryInboxLoad() {
  await _fetchMemoryInbox();
  if (_memoryInboxBound) return;
  _memoryInboxBound = true;
  document.getElementById('mi-refresh-btn')?.addEventListener('click', _fetchMemoryInbox);
  document.getElementById('mi-status-filter')?.addEventListener('change', _fetchMemoryInbox);
  document.getElementById('mi-search')?.addEventListener('input', _fetchMemoryInbox);
  document.getElementById('mi-capture-btn')?.addEventListener('click', _captureMemoryInboxItem);
}

async function _fetchMemoryInbox() {
  const status = document.getElementById('mi-status-filter')?.value || 'pending';
  const q = document.getElementById('mi-search')?.value?.trim() || '';
  const query = new URLSearchParams();
  query.set('status', status);
  if (q) query.set('q', q);
  const { ok, data } = await apiJSON(`/api/memory/inbox?${query.toString()}`);
  const tbody = document.getElementById('mi-body');
  if (!tbody) return;
  if (!ok) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--red);padding:20px">Failed to load inbox</td></tr>';
    return;
  }
  const items = data.items || [];
  window.State = window.State || {};
  window.State.memoryInboxRows = items;
  tbody.innerHTML = items.length ? items.map(i => `
    <tr>
      <td style="max-width:340px;font-size:.82rem">${_esc(i.edited_text || i.candidate_text || '-')}</td>
      <td><code class="text-xs">${_esc(i.session_id||'-')}</code></td>
      <td>${Number(i.confidence||0).toFixed(2)}</td>
      <td><span class="badge ${i.status==='approved'?'badge-green':i.status==='rejected'?'badge-red':'badge-yellow'}">${_esc(i.status||'pending')}</span></td>
      <td class="text-xs text-muted">${_fmtRelative(i.created_at)}</td>
      <td style="display:flex;gap:6px">
        <button class="btn btn-secondary btn-sm" onclick="_reviewMemoryInbox('${i.id}','approved')">Approve</button>
        <button class="btn btn-secondary btn-sm" onclick="_reviewMemoryInbox('${i.id}','rejected')">Reject</button>
        <button class="btn btn-secondary btn-sm" onclick="_editMemoryInbox('${i.id}')">Edit</button>
        <button class="btn btn-danger btn-sm" onclick="_deleteMemoryInbox('${i.id}')">Delete</button>
      </td>
    </tr>
  `).join('') : '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:20px">No candidates</td></tr>';
}

async function _captureMemoryInboxItem() {
  const text = document.getElementById('mi-capture-text')?.value.trim() || '';
  if (!text) return toast('Enter a memory candidate first', 'info');
  const { ok } = await apiJSON('/api/memory/inbox/capture', { method: 'POST', body: JSON.stringify({ text, session_id: State.sessionId }) });
  if (ok) {
    document.getElementById('mi-capture-text').value = '';
    toast('Memory candidate captured', 'success');
    _fetchMemoryInbox();
  } else {
    toast('Failed to capture candidate', 'error');
  }
}

async function _reviewMemoryInbox(id, status) {
  const row = (window.State?.memoryInboxRows || []).find((x) => String(x.id) === String(id));
  const edited = prompt(`Optional edit before marking as ${status}:`, row?.edited_text || row?.candidate_text || '') || '';
  const { ok } = await apiJSON(`/api/memory/inbox/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify({ status, edited_text: edited }),
  });
  if (ok) {
    toast(`Marked ${status}`, 'success');
    _fetchMemoryInbox();
  } else {
    toast('Failed to update candidate', 'error');
  }
}

async function _editMemoryInbox(id) {
  const row = (window.State?.memoryInboxRows || []).find((x) => String(x.id) === String(id));
  const edited = prompt('Edit memory text:', row?.edited_text || row?.candidate_text || '');
  if (edited === null) return;
  const { ok } = await apiJSON(`/api/memory/inbox/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify({ status: row?.status || 'pending', edited_text: edited }),
  });
  if (ok) {
    toast('Memory updated', 'success');
    _fetchMemoryInbox();
  } else {
    toast('Failed to edit candidate', 'error');
  }
}

async function _deleteMemoryInbox(id) {
  if (!confirm('Delete this memory candidate?')) return;
  const { ok } = await apiJSON(`/api/memory/inbox/${encodeURIComponent(id)}`, { method: 'DELETE' });
  if (ok) {
    toast('Memory deleted', 'success');
    _fetchMemoryInbox();
  } else {
    toast('Failed to delete candidate', 'error');
  }
}

async function personasLoad() {
  await _fetchPersonas();
  if (_personasBound) return;
  _personasBound = true;
  document.getElementById('persona-new-btn')?.addEventListener('click', () => _openPersonaModal());
  document.getElementById('persona-save-btn')?.addEventListener('click', _savePersona);
}

async function _fetchPersonas() {
  const { ok, data } = await apiJSON('/api/personas');
  const list = document.getElementById('persona-list');
  if (!list) return;
  if (!ok) {
    list.innerHTML = '<div class="card" style="color:var(--red)">Failed to load personas.</div>';
    return;
  }
  const personas = data.personas || [];
  list.innerHTML = personas.length ? personas.map(p => `
    <div class="card">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
        <strong>${_esc(p.name || 'Unnamed')}</strong>
        ${p.is_default ? '<span class="badge badge-green">Default</span>' : ''}
      </div>
      <div style="font-size:.78rem;color:var(--muted);margin-bottom:8px">${_esc((p.tags||[]).join(', ') || 'No tags')}</div>
      <div style="font-size:.82rem;line-height:1.5;max-height:84px;overflow:hidden">${_esc(p.system_prompt || '').slice(0,260)}</div>
      <div style="display:flex;gap:6px;margin-top:10px">
        <button class="btn btn-secondary btn-sm" onclick="_openPersonaModal(${JSON.stringify(p).replace(/\"/g,'&quot;')})">Edit</button>
        <button class="btn btn-danger btn-sm" onclick="_deletePersona('${p.id}')">Delete</button>
      </div>
    </div>
  `).join('') : '<div class="card" style="color:var(--muted)">No personas yet.</div>';
}

function _openPersonaModal(persona = null) {
  document.getElementById('persona-modal-title').textContent = persona ? 'Edit Persona' : 'New Persona';
  document.getElementById('persona-edit-id').value = persona?.id || '';
  document.getElementById('persona-name').value = persona?.name || '';
  document.getElementById('persona-tags').value = (persona?.tags || []).join(', ');
  document.getElementById('persona-prompt').value = persona?.system_prompt || '';
  document.getElementById('persona-default').checked = !!persona?.is_default;
  openModal('modal-persona');
}

async function _savePersona() {
  const id = document.getElementById('persona-edit-id').value;
  const payload = {
    name: document.getElementById('persona-name').value.trim(),
    system_prompt: document.getElementById('persona-prompt').value.trim(),
    tags: (document.getElementById('persona-tags').value || '').split(',').map(s => s.trim()).filter(Boolean),
    is_default: !!document.getElementById('persona-default').checked,
  };
  if (!payload.name || !payload.system_prompt) return toast('Name and prompt are required', 'error');
  const { ok } = await apiJSON(id ? `/api/personas/${encodeURIComponent(id)}` : '/api/personas', {
    method: id ? 'PATCH' : 'POST',
    body: JSON.stringify(payload),
  });
  if (ok) {
    closeModal('modal-persona');
    toast('Persona saved', 'success');
    _fetchPersonas();
    if (typeof chatInit === 'function') chatInit();
  } else {
    toast('Failed to save persona', 'error');
  }
}

async function _deletePersona(id) {
  if (!confirm('Delete this persona?')) return;
  const { ok } = await apiJSON(`/api/personas/${encodeURIComponent(id)}`, { method: 'DELETE' });
  if (ok) {
    toast('Persona deleted', 'success');
    _fetchPersonas();
  } else {
    toast('Failed to delete persona', 'error');
  }
}

async function dailyBriefLoad() {
  await _fetchDailyBrief();
  if (_dailyBriefBound) return;
  _dailyBriefBound = true;
  document.getElementById('brief-refresh-btn')?.addEventListener('click', _fetchDailyBrief);
  document.getElementById('pull-email-context-btn')?.addEventListener('click', () => _pullContext('email'));
  document.getElementById('pull-calendar-context-btn')?.addEventListener('click', () => _pullContext('calendar'));
}

async function _pullContext(provider) {
  const { ok } = await apiJSON('/api/integrations/context/pull', {
    method: 'POST',
    body: JSON.stringify({ provider, session_id: State.sessionId }),
  });
  toast(ok ? `${provider} context pulled to Memory Inbox` : `Failed to pull ${provider} context`, ok ? 'success' : 'error');
  if (ok) _fetchDailyBrief();
}

function _renderBriefList(id, items, renderer) {
  const el = document.getElementById(id);
  if (!el) return;
  if (!items.length) {
    el.innerHTML = '<div style="font-size:.8rem;color:var(--muted)">Nothing to show.</div>';
    return;
  }
  el.innerHTML = items.map(renderer).join('');
}

async function _fetchDailyBrief() {
  const { ok, data } = await apiJSON('/api/daily-brief');
  if (!ok) return;
  _renderBriefList('brief-open-tasks', data.open_tasks || [], t => `<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:.84rem">${_esc(t.title || 'Untitled')} <span style="color:var(--muted);font-size:.74rem">(${_esc(t.priority||'medium')})</span></div>`);
  _renderBriefList('brief-pending-replies', data.pending_replies || [], r => `<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:.84rem">${_esc(r.reply_preview || r.preview || 'Pending reply')}</div>`);
  _renderBriefList('brief-memories', data.recent_memories || [], m => `<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:.84rem">${_esc(m.fact || '')}</div>`);
  _renderBriefList('brief-candidates', data.pending_memory_candidates || [], c => `<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:.84rem">${_esc(c.candidate_text || '')}</div>`);
}

async function workspaceLoad() {
  await _fetchWorkspaces();
  if (_workspaceBound) return;
  _workspaceBound = true;
  document.getElementById('workspace-new-btn')?.addEventListener('click', () => openModal('modal-workspace'));
  document.getElementById('workspace-save-btn')?.addEventListener('click', _createWorkspace);
}

async function _fetchWorkspaces() {
  const { ok, data } = await apiJSON('/api/workspaces');
  const list = document.getElementById('workspace-list');
  if (!list) return;
  if (!ok) {
    list.innerHTML = '<div class="card" style="color:var(--red)">Failed to load workspaces.</div>';
    return;
  }
  const rows = data.workspaces || [];
  list.innerHTML = rows.length ? rows.map(w => `
    <div class="card">
      <div style="font-weight:700">${_esc(w.name || 'Untitled')}</div>
      <div style="font-size:.78rem;color:var(--muted);margin:6px 0">${_esc(w.description || '')}</div>
      <div style="font-size:.75rem;color:var(--muted)">Members: ${(w.members||[]).map(m => `${_esc(m.username)} (${_esc(m.role)})`).join(', ') || '-'}</div>
      <div style="font-size:.75rem;color:var(--muted);margin-top:4px">Shared sessions: ${(w.session_ids||[]).length}</div>
      <div style="display:flex;gap:6px;margin-top:10px">
        <button class="btn btn-secondary btn-sm" onclick="_shareCurrentSessionToWorkspace('${w.id}')">Share current session</button>
      </div>
    </div>
  `).join('') : '<div class="card" style="color:var(--muted)">No workspaces yet.</div>';
}

async function _createWorkspace() {
  const name = document.getElementById('workspace-name')?.value.trim() || '';
  if (!name) return toast('Workspace name is required', 'error');
  const description = document.getElementById('workspace-description')?.value.trim() || '';
  const rawMembers = document.getElementById('workspace-members')?.value || '';
  const members = rawMembers.split(',').map(s => s.trim()).filter(Boolean).map(pair => {
    const [username, role] = pair.split(':').map(v => (v || '').trim());
    return { username, role: role || 'viewer' };
  }).filter(m => m.username);
  const { ok } = await apiJSON('/api/workspaces', {
    method: 'POST',
    body: JSON.stringify({ name, description, members }),
  });
  toast(ok ? 'Workspace created' : 'Failed to create workspace', ok ? 'success' : 'error');
  if (ok) {
    closeModal('modal-workspace');
    document.getElementById('workspace-name').value = '';
    document.getElementById('workspace-description').value = '';
    document.getElementById('workspace-members').value = '';
    _fetchWorkspaces();
  }
}

async function _shareCurrentSessionToWorkspace(workspaceId) {
  const { ok } = await apiJSON(`/api/workspaces/${encodeURIComponent(workspaceId)}/share-session`, {
    method: 'POST',
    body: JSON.stringify({ session_id: State.sessionId }),
  });
  toast(ok ? 'Session shared to workspace' : 'Failed to share session', ok ? 'success' : 'error');
  if (ok) _fetchWorkspaces();
}

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
  _initAnalyticsDefaults();
  await _fetchAnalytics();
  if (_analyticsBound) return;
  _analyticsBound = true;
  document.getElementById('analytics-refresh-btn')?.addEventListener('click', _fetchAnalytics);
  document.getElementById('analytics-apply-btn')?.addEventListener('click', _fetchAnalytics);
  document.getElementById('analytics-owner-scope')?.addEventListener('change', _fetchAnalytics);
  document.getElementById('analytics-export-csv-btn')?.addEventListener('click', _exportAnalyticsCsv);
}

async function _fetchAnalytics() {
  const days = Number(document.getElementById('analytics-range')?.value || 30);
  // Sessions & memories
  const [s1, s2, s3, s4] = await Promise.all([
    apiJSON('/api/sessions?limit=200'),
    apiJSON('/api/admin/core-memories').catch(() => ({ ok: false, data: {} })),
    apiJSON('/api/tasks').catch(() => ({ ok: false, data: {} })),
    apiJSON(`/api/memory/analytics?days=${days}`).catch(() => ({ ok: false, data: {} })),
  ]);

  const sessions = s1.data?.sessions || [];
  const memories = s2.data?.core_memories || [];
  const tasks    = s3.data?.tasks || [];
  const summary  = s4.data || {};

  // KPIs
  _setKPI('kpi-messages', summary.memory_candidates_approved ?? sessions.length * 8);
  _setKPI('kpi-sessions', summary.sessions_considered ?? (s1.data?.total ?? sessions.length));
  _setKPI('kpi-memories', summary.memory_candidates_pending ?? memories.length);
  _setKPI('kpi-tasks',    summary.task_suggestions_converted ?? tasks.filter(t => t.status === 'done').length);

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
}

async function _fetchAnalytics() {
  const from = document.getElementById('analytics-date-from')?.value || '';
  const to = document.getElementById('analytics-date-to')?.value || '';
  const scope = document.getElementById('analytics-owner-scope')?.value || 'mine';
  const staleDays = document.getElementById('analytics-stale-days')?.value || '30';

  const query = new URLSearchParams({
    date_from: from,
    date_to: to,
    owner_scope: scope,
    stale_days: staleDays,
  });

  const { ok, data } = await apiJSON(`/api/memory/analytics?${query.toString()}`);
  if (!ok) {
    toast(data.detail || 'Failed to load analytics', 'error');
    return;
  }

  _setKPIText('kpi-memory-writes', data?.kpis?.memory_writes_total ?? 0);
  _setKPIText('kpi-retrieval-hits', data?.kpis?.retrieval_hits_total ?? 0);
  _setKPIText('kpi-stale-count', data?.kpis?.stale_memories_count ?? 0);
  _setKPIText('kpi-top-category', (data?.top_categories?.[0]?.category) || '—');

  _renderTrendTable('analytics-writes-trend', data?.memory_writes_per_day || [], 'Writes');
  _renderTrendTable('analytics-retrieval-trend', data?.retrieval_hits_per_day || [], 'Hits');

  const topEl = document.getElementById('analytics-top-categories');
  if (topEl) {
    const rows = data?.top_categories || [];
    topEl.innerHTML = rows.length ? rows.map((r) => `
      <div style="display:flex;justify-content:space-between;border-bottom:1px solid var(--border);padding:7px 0">
        <span>${_esc(r.category || 'Uncategorized')}</span>
        <strong>${Number(r.count || 0)}</strong>
      </div>`).join('') : '<div style="color:var(--muted);font-size:.85rem">No categories in range.</div>';
  }

  const staleBody = document.getElementById('analytics-stale-body');
  if (staleBody) {
    const rows = data?.stale_memories || [];
    staleBody.innerHTML = rows.length ? rows.slice(0, 100).map((r) => `
      <tr>
        <td><code>${_esc(r.session_id || '')}</code></td>
        <td>${_esc(r.category || '')}</td>
        <td>${_esc(r.owner || '')}</td>
        <td>${_fmtDateOnly(r.updated_at)}</td>
        <td>${r.last_retrieval_at ? _fmtDateOnly(r.last_retrieval_at) : 'Never'}</td>
      </tr>`).join('') : '<tr><td colspan="5" style="text-align:center;color:var(--muted)">No stale memories.</td></tr>';
  }
}

function _setKPIText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = String(val ?? '—');
}

function _renderTrendTable(containerId, rows, label) {
  const el = document.getElementById(containerId);
  if (!el) return;
  if (!rows.length) {
    el.innerHTML = '<div style="color:var(--muted);font-size:.85rem">No data for selected range.</div>';
    return;
  }
  el.innerHTML = `<table class="tbl"><thead><tr><th>Date</th><th>${label}</th></tr></thead><tbody>${
    rows.map(r => `<tr><td>${_esc(r.day || '')}</td><td>${Number(r.count || 0)}</td></tr>`).join('')
  }</tbody></table>`;
}

function _fmtDateOnly(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (isNaN(d.getTime())) return _esc(String(value));
  return d.toISOString().slice(0, 10);
}

async function _exportAnalyticsCsv() {
  const from = document.getElementById('analytics-date-from')?.value || '';
  const to = document.getElementById('analytics-date-to')?.value || '';
  const scope = document.getElementById('analytics-owner-scope')?.value || 'mine';
  const staleDays = document.getElementById('analytics-stale-days')?.value || '30';
  const query = new URLSearchParams({
    date_from: from,
    date_to: to,
    owner_scope: scope,
    stale_days: staleDays,
    export: 'csv',
  });

  const headers = {};
  if (State.token) headers['Authorization'] = 'Bearer ' + State.token;
  const res = await fetch(`/api/memory/analytics?${query.toString()}`, { headers });
  if (!res.ok) {
    toast('CSV export failed', 'error');
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'memory-analytics.csv';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
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
// DOCKER UPDATE PAGE
// ═══════════════════════════════════════════════════
let _updateBound = false;
let _updatePollTimer = null;

async function dockerUpdateLoad() {
  _fetchUpdateVersion();
  _fetchUpdateBackups();
  if (_updateBound) return;
  _updateBound = true;
  document.getElementById('update-check-btn')?.addEventListener('click', _fetchUpdateVersion);
  document.getElementById('update-trigger-btn')?.addEventListener('click', _triggerUpdate);
  document.getElementById('update-backups-refresh-btn')?.addEventListener('click', _fetchUpdateBackups);
}

async function _fetchUpdateVersion() {
  const statusEl = document.getElementById('update-version-status');
  const currentEl = document.getElementById('update-current-commit');
  const latestEl  = document.getElementById('update-latest-commit');
  const badgeEl   = document.getElementById('update-badge');
  const trigBtn   = document.getElementById('update-trigger-btn');

  if (statusEl) { statusEl.textContent = 'Checking…'; statusEl.style.color = 'var(--muted)'; }

  const { ok, data } = await apiJSON('/api/admin/update/version');
  if (!ok) {
    if (statusEl) { statusEl.textContent = 'Failed to check version.'; statusEl.style.color = 'var(--red)'; }
    return;
  }
  if (currentEl) currentEl.textContent = data.current_commit || 'unknown';
  if (latestEl)  latestEl.textContent  = data.latest_commit  || 'unknown';

  if (data.check_ok === false) {
    if (badgeEl) {
      badgeEl.textContent = '⚠ Check unavailable';
      badgeEl.style.background = 'rgba(239,68,68,.15)';
      badgeEl.style.color = '#ef4444';
      badgeEl.style.border = '1px solid rgba(239,68,68,.3)';
    }
    if (statusEl) { statusEl.textContent = 'Version check unavailable (GitHub API or repo URL issue).'; statusEl.style.color = 'var(--red)'; }
    if (trigBtn) { trigBtn.disabled = false; trigBtn.title = ''; }
    return;
  }

  if (data.up_to_date) {
    if (badgeEl) {
      badgeEl.textContent = '✓ Up to date';
      badgeEl.style.background = 'rgba(16,185,129,.15)';
      badgeEl.style.color = '#10b981';
      badgeEl.style.border = '1px solid rgba(16,185,129,.3)';
    }
    if (statusEl) { statusEl.textContent = 'Your deployment is up to date.'; statusEl.style.color = 'var(--green)'; }
    if (trigBtn) { trigBtn.disabled = true; trigBtn.title = 'Already up to date'; }
  } else {
    if (badgeEl) {
      badgeEl.textContent = '⬆ Update available';
      badgeEl.style.background = 'rgba(245,158,11,.15)';
      badgeEl.style.color = '#f59e0b';
      badgeEl.style.border = '1px solid rgba(245,158,11,.3)';
    }
    if (statusEl) { statusEl.textContent = 'A newer version is available on GitHub.'; statusEl.style.color = 'var(--yellow)'; }
    if (trigBtn) { trigBtn.disabled = false; trigBtn.title = ''; }
  }
}

async function _triggerUpdate() {
  if (!confirm('⚠️ This will:\n1. Backup the current code\n2. Pull latest code from GitHub\n3. Restart the server\n\nAll settings, memories, users and tasks are preserved in Docker volumes.\n\nProceed?')) return;

  const btn = document.getElementById('update-trigger-btn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Starting update…'; }

  const logBox = document.getElementById('update-log-box');
  const logWrap = document.getElementById('update-log-wrap');
  if (logWrap) logWrap.style.display = 'block';
  if (logBox) logBox.textContent = 'Connecting…\n';

  const { ok, data } = await apiJSON('/api/admin/update/trigger', { method: 'POST' });
  if (!ok) {
    toast(data?.detail || 'Failed to start update', 'error');
    if (btn) { btn.disabled = false; btn.textContent = '🚀 Update AmpAI'; }
    return;
  }

  toast('Update started! Watching progress…', 'info');
  _pollUpdateStatus();
}

function _pollUpdateStatus() {
  clearInterval(_updatePollTimer);
  _updatePollTimer = setInterval(async () => {
    const { ok, data } = await apiJSON('/api/admin/update/status');
    if (!ok) return;

    const logBox = document.getElementById('update-log-box');
    if (logBox) {
      logBox.textContent = (data.log_lines || []).join('\n');
      logBox.scrollTop = logBox.scrollHeight;
    }

    const stateEl = document.getElementById('update-state-badge');
    if (stateEl) {
      const stateColors = {
        idle:    { bg:'rgba(100,116,139,.15)', color:'var(--muted)',  border:'1px solid rgba(100,116,139,.3)', label:'Idle' },
        running: { bg:'rgba(99,102,241,.15)',  color:'#818cf8',       border:'1px solid rgba(99,102,241,.3)',  label:'🔄 Running…' },
        success: { bg:'rgba(16,185,129,.15)',  color:'#10b981',       border:'1px solid rgba(16,185,129,.3)', label:'✓ Success' },
        error:   { bg:'rgba(239,68,68,.15)',   color:'var(--red)',    border:'1px solid rgba(239,68,68,.3)',  label:'✕ Error' },
      };
      const s = stateColors[data.state] || stateColors.idle;
      stateEl.textContent = s.label;
      stateEl.style.background = s.bg;
      stateEl.style.color = s.color;
      stateEl.style.border = s.border;
    }

    if (data.state === 'success') {
      clearInterval(_updatePollTimer);
      toast('✓ Update complete! Server restarting…', 'success');
      const btn = document.getElementById('update-trigger-btn');
      if (btn) { btn.textContent = '🚀 Update AmpAI'; }
      _fetchUpdateBackups();
      // Reload page after server restarts
      setTimeout(() => location.reload(), 5000);
    } else if (data.state === 'error') {
      clearInterval(_updatePollTimer);
      toast('Update failed: ' + (data.error || 'Unknown error'), 'error');
      const btn = document.getElementById('update-trigger-btn');
      if (btn) { btn.disabled = false; btn.textContent = '🚀 Update AmpAI'; }
    }
  }, 1500);
}

async function _fetchUpdateBackups() {
  const tbody = document.getElementById('update-backups-tbody');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:16px">Loading…</td></tr>';

  const { ok, data } = await apiJSON('/api/admin/update/backups');
  if (!ok || !data.backups?.length) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:24px">No code backups found.</td></tr>';
    return;
  }

  tbody.innerHTML = data.backups.map(b => {
    const sizeMB = (b.size_bytes / 1048576).toFixed(2);
    return `<tr>
      <td style="font-size:.82rem"><code>${_esc(b.name)}</code></td>
      <td><code style="font-size:.78rem">${_esc(b.commit)}</code></td>
      <td style="font-size:.82rem">${sizeMB} MB</td>
      <td style="font-size:.78rem;color:var(--muted)">${_fmtRelative(b.name)}</td>
      <td>
        <button class="btn btn-danger btn-sm" onclick="_deleteUpdateBackup('${_esc(b.name)}')">🗑 Remove</button>
      </td>
    </tr>`;
  }).join('');
}

async function _deleteUpdateBackup(name) {
  if (!confirm(`Delete backup "${name}"?\nThis cannot be undone.`)) return;
  const { ok } = await apiJSON(`/api/admin/update/backups/${encodeURIComponent(name)}`, { method: 'DELETE' });
  if (ok) {
    toast('Backup deleted', 'success');
    _fetchUpdateBackups();
  } else {
    toast('Failed to delete backup', 'error');
  }
}

// ═══════════════════════════════════════════════════
// FULL BACKUP / RESTORE PAGE
// ═══════════════════════════════════════════════════
let _fbBound = false;

async function fullBackupLoad() {
  _fbLoadCategories();
  _fbLoadList();
  if (_fbBound) return;
  _fbBound = true;
  document.getElementById('fb-cats-refresh-btn')?.addEventListener('click', _fbLoadCategories);
  document.getElementById('fb-create-btn')?.addEventListener('click', _fbCreate);
  document.getElementById('fb-list-refresh-btn')?.addEventListener('click', _fbLoadList);
  document.getElementById('fb-restore-btn')?.addEventListener('click', _fbRestore);
}

async function _fbLoadCategories() {
  const tbody = document.getElementById('fb-cats-tbody');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--muted);padding:16px">Loading…</td></tr>';
  const { ok, data } = await apiJSON('/api/admin/fullbackup/memory-categories');
  if (!ok || !data.categories?.length) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--muted);padding:20px">No categories found.</td></tr>';
    return;
  }
  tbody.innerHTML = data.categories.map(c => `<tr>
    <td><span class="badge badge-blue">${_esc(c.category)}</span></td>
    <td>${c.session_count}</td>
    <td>${c.message_count}</td>
    <td>${c.memory_count}</td>
  </tr>`).join('');
}

async function _fbCreate() {
  const btn = document.getElementById('fb-create-btn');
  const st  = document.getElementById('fb-create-status');
  const wrap = document.getElementById('fb-manifest-wrap');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Building…'; }
  if (st)  { st.textContent = 'Creating backup — this may take a moment…'; st.style.color = 'var(--muted)'; }
  if (wrap) wrap.style.display = 'none';

  const { ok, data } = await apiJSON('/api/admin/fullbackup/create', { method: 'POST' });
  if (btn) { btn.disabled = false; btn.textContent = '💾 Create Full Backup'; }
  if (!ok) {
    if (st) { st.textContent = '✕ ' + (data?.detail || 'Failed'); st.style.color = 'var(--red)'; }
    return;
  }

  if (st) { st.textContent = `✓ Saved: ${data.filename}`; st.style.color = 'var(--green)'; }
  toast('Full backup created!', 'success');

  // Render manifest
  const m = data.manifest || {};
  const mBody = document.getElementById('fb-manifest-body');
  if (mBody && wrap) {
    const items = [
      ['Slots', m.slot_count],
      ['Sessions', m.total_sessions],
      ['Messages', m.total_messages],
      ['Memories', m.total_memories],
      ['Core Memories', m.total_core_memories],
      ['Users', m.total_users],
      ['Configs', m.total_configs],
      ['Personas', m.total_personas],
      ['Tasks', m.total_tasks],
      ['Created', m.created_at ? new Date(m.created_at).toLocaleString() : '—'],
    ];
    mBody.innerHTML = items.map(([k, v]) =>
      `<div style="background:var(--bg-2);border:1px solid var(--border);border-radius:8px;padding:10px 12px">
        <div style="font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em">${k}</div>
        <div style="font-weight:700;font-size:.95rem">${v ?? '—'}</div>
       </div>`
    ).join('');

    // Slots breakdown
    if ((m.slots || []).length) {
      mBody.innerHTML += `<div style="grid-column:1/-1;margin-top:8px;font-size:.8rem;color:var(--muted)">
        <strong>Slot breakdown:</strong> ${m.slots.map(s =>
          `Slot ${s.slot}: [${(s.categories||[]).join(', ') || 'empty'}] — ${(s.bytes/1048576).toFixed(1)} MB`
        ).join(' | ')}</div>`;
    }
    wrap.style.display = 'block';
  }
  _fbLoadList();
}

async function _fbLoadList() {
  const tbody = document.getElementById('fb-list-tbody');
  const sel   = document.getElementById('fb-restore-select');
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--muted);padding:16px">Loading…</td></tr>';

  const { ok, data } = await apiJSON('/api/admin/fullbackup/list');
  if (!ok || !data.backups?.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:var(--muted);padding:24px">No full backups yet.</td></tr>';
    if (sel) sel.innerHTML = '<option value="">— no backups found —</option>';
    return;
  }

  // Populate restore dropdown
  if (sel) {
    sel.innerHTML = '<option value="">— choose a backup —</option>' +
      data.backups.map(b => `<option value="${_esc(b.filename)}">${_esc(b.filename)}</option>`).join('');
  }

  tbody.innerHTML = data.backups.map(b => {
    const mb = (b.size_bytes / 1048576).toFixed(2);
    const created = b.created_at ? new Date(b.created_at).toLocaleString() : '—';
    return `<tr>
      <td style="font-size:.8rem"><code>${_esc(b.filename)}</code></td>
      <td style="font-size:.78rem">${created}</td>
      <td>${b.slot_count || '—'}</td>
      <td>${b.total_sessions || 0}</td>
      <td>${b.total_memories || 0}</td>
      <td>${b.total_users || 0}</td>
      <td>${mb} MB</td>
      <td style="display:flex;gap:6px;flex-wrap:wrap">
        <button class="btn btn-secondary btn-sm" onclick="_fbDownload('${_esc(b.filename)}')">⬇ Download</button>
        <button class="btn btn-danger btn-sm"    onclick="_fbDelete('${_esc(b.filename)}')">🗑 Delete</button>
      </td>
    </tr>`;
  }).join('');
}

async function _fbDownload(filename) {
  await _downloadWithAuth(`/api/admin/fullbackup/download/${encodeURIComponent(filename)}`);
}

async function _fbDelete(filename) {
  if (!confirm(`Delete backup "${filename}"?\nThis cannot be undone.`)) return;
  const { ok } = await apiJSON(`/api/admin/fullbackup/${encodeURIComponent(filename)}`, { method: 'DELETE' });
  if (ok) { toast('Backup deleted', 'success'); _fbLoadList(); }
  else toast('Failed to delete backup', 'error');
}

async function _fbRestore() {
  const filename = document.getElementById('fb-restore-select')?.value;
  const uploadFile = document.getElementById('fb-restore-upload')?.files?.[0];
  if (!filename && !uploadFile) { toast('Select a saved backup or upload a ZIP file first', 'error'); return; }

  const sections = [
    ['fb-r-chats',    'restore_chats'],
    ['fb-r-memories', 'restore_memories'],
    ['fb-r-core',     'restore_core_memories'],
    ['fb-r-users',    'restore_users'],
    ['fb-r-configs',  'restore_configs'],
    ['fb-r-personas', 'restore_personas'],
    ['fb-r-tasks',    'restore_tasks'],
  ];
  const payload = filename ? { filename } : {}; 
  sections.forEach(([elId, key]) => {
    payload[key] = !!document.getElementById(elId)?.checked;
  });

  const chosen = sections.filter(([elId]) => document.getElementById(elId)?.checked).map(([, k]) => k);
  if (!chosen.length) { toast('Select at least one section to restore', 'error'); return; }

  if (!confirm(
    `⚠️ Restore from "${filename}"?\n\nSections: ${chosen.join(', ')}\n\nExisting data will NOT be deleted — records are inserted/merged.\n\nProceed?`
  )) return;

  const btn = document.getElementById('fb-restore-btn');
  const st  = document.getElementById('fb-restore-status');
  const res = document.getElementById('fb-restore-result');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Restoring…'; }
  if (st)  { st.textContent = 'Running restore…'; st.style.color = 'var(--muted)'; }
  if (res) res.style.display = 'none';

  let ok = false; let data = {};
  if (uploadFile) {
    const form = new FormData();
    form.append('backup_file', uploadFile);
    sections.forEach(([elId, key]) => form.append(key, String(!!document.getElementById(elId)?.checked)));
    const token = localStorage.getItem('ampai_token') || '';
    const resUp = await fetch('/api/admin/fullbackup/restore-upload', {
      method: 'POST',
      headers: token ? { Authorization: 'Bearer ' + token } : {},
      body: form,
    });
    ok = resUp.ok;
    data = await resUp.json().catch(() => ({}));
  } else {
    const resJson = await apiJSON('/api/admin/fullbackup/restore', {
      method: 'POST', body: JSON.stringify(payload)
    });
    ok = resJson.ok;
    data = resJson.data;
  }
  if (btn) { btn.disabled = false; btn.textContent = '♻️ Restore Selected'; }

  if (!ok) {
    if (st) { st.textContent = '✕ Restore failed'; st.style.color = 'var(--red)'; }
    toast(data?.detail || 'Restore failed', 'error');
    return;
  }

  if (st) { st.textContent = data.ok ? '✓ Restore complete' : '⚠ Restore finished with errors'; st.style.color = data.ok ? 'var(--green)' : 'var(--yellow)'; }
  toast(data.ok ? 'Restore complete!' : 'Restore finished with some errors', data.ok ? 'success' : 'error');

  // Show summary
  if (res) {
    const s = data.summary || {};
    const errs = data.errors || [];
    res.style.display = 'block';
    res.innerHTML = `<div style="font-weight:700;margin-bottom:8px">${data.ok ? '✓ Restore Summary' : '⚠ Restore Summary (with errors)'}</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px;margin-bottom:10px">
        ${Object.entries(s).map(([k, v]) =>
          `<div style="background:var(--bg-2);border:1px solid var(--border);border-radius:8px;padding:8px 10px">
            <div style="font-size:.7rem;color:var(--muted);text-transform:uppercase">${k.replace(/_/g,' ')}</div>
            <div style="font-weight:700">${v}</div>
          </div>`
        ).join('')}
      </div>
      ${errs.length ? `<details style="font-size:.78rem;color:var(--red)"><summary>${errs.length} error(s)</summary><pre style="white-space:pre-wrap">${errs.slice(0,20).join('\n')}</pre></details>` : ''}`;
  }
}


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

// ═══════════════════════════════════════════════════
// TELEGRAM INTEGRATION (admin/settings embedding)
// ═══════════════════════════════════════════════════
let _telegramSettingsBound = false;
let _telegramTokenSaved = false;
let _telegramLastTestResult = '—';

async function telegramSettingsLoad() {
  await _fetchTelegramStatus();
  await _fetchTelegramSettings();
  if (_telegramSettingsBound) return;
  _telegramSettingsBound = true;

  document.getElementById('tg-save-btn')?.addEventListener('click', _saveTelegramSettings);
  document.getElementById('tg-test-btn')?.addEventListener('click', _testTelegramGetMe);
  document.getElementById('tg-register-btn')?.addEventListener('click', _registerTelegramWebhook);
  document.getElementById('tg-remove-btn')?.addEventListener('click', _removeTelegramWebhook);
}

async function _fetchTelegramSettings() {
  const { ok, data } = await apiJSON('/api/integrations/telegram/settings');
  if (!ok) return;
  document.getElementById('tg-enabled') && (document.getElementById('tg-enabled').checked = !!data.enabled);
  document.getElementById('tg-webhook-url') && (document.getElementById('tg-webhook-url').value = data.webhook_url || '');
  _telegramTokenSaved = !!data.bot_token_masked || !!data.token_saved;
  if (data.bot_token_masked) {
    const tokenEl = document.getElementById('tg-bot-token');
    if (tokenEl && !tokenEl.value) tokenEl.placeholder = data.bot_token_masked;
  }
}

async function _saveTelegramSettings() {
  const tokenEl = document.getElementById('tg-bot-token');
  const payload = {
    enabled: !!document.getElementById('tg-enabled')?.checked,
    bot_token: tokenEl?.value?.trim() || undefined,
    webhook_url: document.getElementById('tg-webhook-url')?.value?.trim() || '',
  };
  const { ok, data } = await apiJSON('/api/integrations/telegram/settings', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  toast(ok ? 'Telegram settings saved' : (data?.detail || 'Failed to save Telegram settings'), ok ? 'success' : 'error');
  if (ok) {
    _telegramTokenSaved = _telegramTokenSaved || !!payload.bot_token;
    if (tokenEl) tokenEl.value = '';
    _fetchTelegramSettings();
    _fetchTelegramStatus();
  }
}

async function _testTelegramGetMe() {
  const { ok, data } = await apiJSON('/api/integrations/telegram/test', { method: 'POST' });
  _telegramLastTestResult = ok ? `Passed (${new Date().toLocaleTimeString()})` : `Failed (${new Date().toLocaleTimeString()})`;
  toast(ok ? `Connected as @${data?.username || data?.result?.username || 'bot'}` : (data?.detail || 'Telegram getMe failed'), ok ? 'success' : 'error');
  _fetchTelegramStatus();
}

async function _registerTelegramWebhook() {
  const payload = {
    webhook_url: document.getElementById('tg-webhook-url')?.value?.trim() || '',
  };
  if (!payload.webhook_url) return toast('Webhook URL is required', 'error');
  const { ok, data } = await apiJSON('/api/integrations/telegram/webhook/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  toast(ok ? 'Webhook registered' : (data?.detail || 'Failed to register webhook'), ok ? 'success' : 'error');
  if (ok) _fetchTelegramStatus();
}

async function _removeTelegramWebhook() {
  const { ok, data } = await apiJSON('/api/integrations/telegram/webhook/remove', { method: 'POST' });
  toast(ok ? 'Webhook removed' : (data?.detail || 'Failed to remove webhook'), ok ? 'success' : 'error');
  if (ok) _fetchTelegramStatus();
}

async function _fetchTelegramStatus() {
  const { ok, data } = await apiJSON('/api/integrations/telegram/status');
  const enabledEl = document.getElementById('tg-status-enabled');
  const tokenEl = document.getElementById('tg-status-token');
  const lastTestEl = document.getElementById('tg-status-last-test');
  if (!enabledEl || !tokenEl || !lastTestEl) return;

  if (!ok) {
    enabledEl.textContent = 'Disabled';
    enabledEl.className = 'badge badge-red';
    tokenEl.textContent = _telegramTokenSaved ? 'Saved' : 'Not saved';
    tokenEl.className = _telegramTokenSaved ? 'badge badge-green' : 'badge badge-red';
    lastTestEl.textContent = _telegramLastTestResult;
    return;
  }

  const enabled = !!(data.enabled ?? data.connected ?? data.ok);
  enabledEl.textContent = enabled ? 'Enabled' : 'Disabled';
  enabledEl.className = enabled ? 'badge badge-green' : 'badge badge-red';

  _telegramTokenSaved = _telegramTokenSaved || !!data.bot_token_masked || !!data.token_saved;
  tokenEl.textContent = _telegramTokenSaved ? 'Saved' : 'Not saved';
  tokenEl.className = _telegramTokenSaved ? 'badge badge-green' : 'badge badge-red';

  lastTestEl.textContent = data.last_test_result || _telegramLastTestResult;
}
