/* =====================================================
   AmpAI — Memory, Admin, Models, Settings Logic
   ===================================================== */

// ── Memory Explorer ────────────────────────────────
const MX = { offset: 0, limit: 50, total: 0 };

async function memoryLoad() {
  await mxFetch();
  if (window._mxBound) return;
  window._mxBound = true;
  document.getElementById('memory-refresh-btn')?.addEventListener('click', () => { MX.offset = 0; mxFetch(); });
  document.getElementById('mx-apply')?.addEventListener('click',           () => { MX.offset = 0; mxFetch(); });
  document.getElementById('mx-prev')?.addEventListener('click',             () => { MX.offset = Math.max(0, MX.offset - MX.limit); mxFetch(); });
  document.getElementById('mx-next')?.addEventListener('click',             () => { MX.offset += MX.limit; mxFetch(); });
}

async function mxFetch() {
  const body = {
    query: document.getElementById('mx-query')?.value.trim() || '',
    category: document.getElementById('mx-category')?.value || '',
    owner_scope: document.getElementById('mx-scope')?.value || 'mine',
    date_from: document.getElementById('mx-date-from')?.value ? document.getElementById('mx-date-from').value + 'T00:00:00Z' : '',
    date_to: document.getElementById('mx-date-to')?.value ? document.getElementById('mx-date-to').value + 'T23:59:59Z' : '',
    limit: MX.limit,
    offset: MX.offset,
  };
  const tbody = document.getElementById('mx-body');
  if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:32px;color:var(--muted)">Loading…</td></tr>';
  const { ok, data } = await apiJSON('/api/memory/explorer', { method: 'POST', body: JSON.stringify(body) });
  if (!ok) { if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="color:var(--red);text-align:center;padding:24px">Failed to load</td></tr>'; return; }
  MX.total = Number(data.total || 0);

  // Populate category dropdown
  const cats = Object.keys(data.categories || {}).sort();
  const catEl = document.getElementById('mx-category');
  if (catEl) {
    const sel = catEl.value;
    catEl.innerHTML = '<option value="">All categories</option>' + cats.map(c => `<option value="${c}">${c} (${data.categories[c]})</option>`).join('');
    catEl.value = sel;
  }

  const rows = data.sessions || [];
  if (tbody) {
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:32px;color:var(--muted)">No memories found</td></tr>';
    } else {
      tbody.innerHTML = rows.map(s => `
        <tr>
          <td><code style="font-size:0.78rem">${s.session_id}</code></td>
          <td><span class="badge badge-blue">${s.category || '-'}</span></td>
          <td>${s.owner || '-'}</td>
          <td style="font-size:0.78rem;color:var(--muted)">${(s.insight?.tags || '').split(',').filter(Boolean).slice(0,4).join(', ') || '-'}</td>
          <td class="truncate" style="max-width:200px;font-size:0.82rem">${(s.insight?.summary || '-').slice(0,100)}</td>
          <td class="text-xs text-muted">${fmtDate(s.updated_at)}</td>
          <td><button class="btn btn-secondary btn-sm" onclick="viewChatLog('${s.session_id}')">View</button></td>
        </tr>`).join('');
    }
  }

  const start = MX.total ? MX.offset + 1 : 0;
  const end = Math.min(MX.offset + MX.limit, MX.total);
  const pageEl = document.getElementById('mx-page');
  if (pageEl) pageEl.textContent = `${start}–${end} of ${MX.total}`;
  const prevBtn = document.getElementById('mx-prev');
  const nextBtn = document.getElementById('mx-next');
  if (prevBtn) prevBtn.disabled = MX.offset <= 0;
  if (nextBtn) nextBtn.disabled = (MX.offset + MX.limit) >= MX.total;
}

async function viewChatLog(sessionId) {
  document.getElementById('modal-session-id-label').textContent = sessionId;
  const body = document.getElementById('modal-chat-body');
  const sugEl = document.getElementById('modal-task-suggestions');
  body.innerHTML = '<div style="text-align:center;padding:32px;color:var(--muted)">Loading…</div>';
  if (sugEl) sugEl.innerHTML = '';
  openModal('modal-chat-log');

  const { ok, data } = await apiJSON(`/api/history/${sessionId}`);
  if (!ok) { body.innerHTML = '<div style="color:var(--red);text-align:center">Failed to load.</div>'; return; }
  const msgs = data.messages || [];
  body.innerHTML = msgs.length ? msgs.map(m => `
    <div style="padding:10px 14px;border-radius:8px;font-size:0.85rem;
      ${m.type==='human'
        ? 'background:rgba(99,102,241,0.15);text-align:right'
        : 'background:var(--bg-3);border:1px solid var(--border)'}">
      <strong style="font-size:0.72rem;color:var(--muted)">${m.type==='human'?'User':'AI'}</strong><br>
      ${m.content.replace(/</g,'&lt;').replace(/\n/g,'<br>')}
    </div>`).join('')
    : '<div style="text-align:center;color:var(--muted)">No messages found</div>';

  const sug = await apiJSON(`/api/sessions/${encodeURIComponent(sessionId)}/task-suggestions`);
  if (sug.ok && (sug.data.suggestions || []).length) {
    const pending = (sug.data.suggestions || []).filter(s => s.status === 'pending').slice(0, 8);
    if (pending.length) {
      body.innerHTML += `<div style="margin-top:12px;padding:10px;border:1px solid var(--border);border-radius:8px;background:var(--bg-2)">
        <div style="font-size:.78rem;font-weight:700;margin-bottom:8px">Suggested Tasks</div>
        ${pending.map(s => `<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
          <div style="flex:1;font-size:.82rem">${s.title || 'Suggested task'}</div>
          <button class="btn btn-secondary btn-sm" onclick="convertTaskSuggestion('${s.id}','${sessionId}')">Create Task</button>
        </div>`).join('')}
      </div>`;
    }
  }

  document.getElementById('modal-export-btn').onclick = () => exportSession(sessionId);
}

async function convertTaskSuggestion(id, sessionId) {
  const { ok } = await apiJSON(`/api/tasks/from-suggestion/${encodeURIComponent(id)}`, { method: 'POST' });
  toast(ok ? 'Task created' : 'Failed to create task', ok ? 'success' : 'error');
  if (ok) viewChatLog(sessionId);
}

async function exportSession(sessionId) {
  const { ok, data } = await apiJSON(`/api/export/${sessionId}`);
  if (!ok) { toast('Export failed', 'error'); return; }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `ampai_session_${sessionId}.json`;
  a.click();
}

// ── Memory Inbox ───────────────────────────────────
const MI = { limit: 100, offset: 0, rows: [] };

async function memoryInboxLoad() {
  await miFetch();
  if (window._miBound) return;
  window._miBound = true;
  document.getElementById('mi-refresh-btn')?.addEventListener('click', () => miFetch());
  document.getElementById('mi-apply')?.addEventListener('click', () => miFetch());
}

function _miFilters() {
  const params = new URLSearchParams();
  params.set('status', document.getElementById('mi-status')?.value || 'pending');
  params.set('limit', String(MI.limit));
  params.set('offset', String(MI.offset));
  const session = document.getElementById('mi-session')?.value.trim();
  if (session) params.set('session_id', session);
  const dateFrom = document.getElementById('mi-date-from')?.value;
  const dateTo = document.getElementById('mi-date-to')?.value;
  if (dateFrom) params.set('date_from', `${dateFrom}T00:00:00Z`);
  if (dateTo) params.set('date_to', `${dateTo}T23:59:59Z`);
  return params;
}

function miRenderRows() {
  const tbody = document.getElementById('mi-body');
  if (!tbody) return;
  if (!MI.rows.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:28px;color:var(--muted)">No memory candidates found</td></tr>';
    return;
  }
  tbody.innerHTML = MI.rows.map(r => `
    <tr id="mi-row-${r.id}">
      <td><code>${r.id}</code></td>
      <td style="font-size:.78rem">${r.session_id || '-'}</td>
      <td style="max-width:360px">${(r.candidate_text || '').replace(/</g, '&lt;')}</td>
      <td>${r.confidence || '-'}</td>
      <td><span class="badge badge-blue">${r.status || 'pending'}</span></td>
      <td class="text-xs text-muted">${fmtDate(r.created_at)}</td>
      <td style="display:flex;gap:6px;flex-wrap:wrap">
        <button class="btn btn-primary btn-sm" onclick="memoryInboxApprove(${r.id})">Approve</button>
        <button class="btn btn-danger btn-sm" onclick="memoryInboxReject(${r.id})">Reject</button>
        <button class="btn btn-secondary btn-sm" onclick="memoryInboxEditApprove(${r.id})">Edit + Approve</button>
      </td>
    </tr>
  `).join('');
}

async function miFetch() {
  const tbody = document.getElementById('mi-body');
  if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:32px;color:var(--muted)">Loading…</td></tr>';
  const { ok, data } = await apiJSON(`/api/memory/inbox?${_miFilters().toString()}`);
  if (!ok) {
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:28px;color:var(--red)">Failed to load inbox</td></tr>';
    return;
  }
  MI.rows = data.candidates || [];
  miRenderRows();
}

function _miOptimisticUpdate(id, patch) {
  MI.rows = MI.rows.map(row => row.id === id ? { ...row, ...patch } : row);
  miRenderRows();
}

async function _miPatch(id, status, edited_text = null) {
  _miOptimisticUpdate(id, { status, candidate_text: edited_text || MI.rows.find(r => r.id === id)?.candidate_text });
  const { ok, data } = await apiJSON(`/api/memory/inbox/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ status, edited_text }),
  });
  if (!ok) {
    toast(data.detail || 'Memory review failed', 'error');
    miFetch();
    return;
  }
  toast(`Candidate ${status}`, 'success');
  _miOptimisticUpdate(id, data.candidate || {});
}

async function memoryInboxApprove(id) {
  await _miPatch(id, 'approved');
}

async function memoryInboxReject(id) {
  await _miPatch(id, 'rejected');
}

async function memoryInboxEditApprove(id) {
  const row = MI.rows.find(r => r.id === id);
  const edited = prompt('Edit memory before approving', row?.candidate_text || '');
  if (edited === null) return;
  await _miPatch(id, 'approved', edited);
}

// ── Admin ──────────────────────────────────────────
async function adminInit() {
  if (State.role !== 'admin') { toast('Admin access required', 'error'); navigate('chat'); return; }
  loadAdminStats();
  loadHealthPanel();
  adminTabHandlers();
  document.getElementById('refresh-health-btn')?.addEventListener('click', loadHealthPanel);
  document.getElementById('create-user-btn')?.addEventListener('click', createUser);
  document.getElementById('run-backup-btn')?.addEventListener('click', runBackup);
  document.getElementById('backup-preflight-btn')?.addEventListener('click', runRestorePreflight);
  document.getElementById('restore-backup-btn')?.addEventListener('click', restoreBackup);
  document.getElementById('backup-restore-file')?.addEventListener('change', loadRestoreFile);
  document.getElementById('backup-profile-save-btn')?.addEventListener('click', saveBackupProfile);
  document.getElementById('backup-profile-reset-btn')?.addEventListener('click', resetBackupProfileForm);
  document.getElementById('backup-monitor-refresh-btn')?.addEventListener('click', () => loadBackupJobs(true));
}

let restorePreflightId = null;
let restorePollTimer = null;

function adminTabHandlers() {
  if (window._adminTabsBound) return;
  window._adminTabsBound = true;
  const ALL_TABS = ['health','users','sessions','memories','backup','audit'];
  document.querySelectorAll('#admin-tabs .tab').forEach(tab => {
    tab.addEventListener('click', () => {
      // Toggle active state
      document.querySelectorAll('#admin-tabs .tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const name = tab.dataset.tab;
      // Show/hide panels by ID (no .tab-panel class)
      ALL_TABS.forEach(t => {
        const panel = document.getElementById('tab-' + t);
        if (panel) panel.classList.toggle('hidden', t !== name);
      });
      // Load data for the panel
      if (name === 'users')    loadAdminUsers();
      if (name === 'sessions') loadAdminSessions();
      if (name === 'memories') loadCoreMemories();
      if (name === 'backup') { loadBackupHistory(); loadBackupProfiles(); loadBackupJobs(); loadBackupKpis(); }
      if (name === 'audit')    loadAuditLog();
    });
  });
}

async function loadAdminStats() {
  const { ok: ok1, data: d1 } = await apiJSON('/api/sessions?limit=1');
  const { ok: ok2, data: d2 } = await apiJSON('/api/admin/users');
  const { ok: ok3, data: d3 } = await apiJSON('/api/admin/core-memories');
  const { ok: ok4, data: d4 } = await apiJSON('/api/tasks?status=pending');
  if (ok1) document.getElementById('stat-sessions').textContent = d1.total ?? (d1.sessions?.length ?? '—');
  if (ok2) document.getElementById('stat-users').textContent = (d2.users?.length ?? '—');
  if (ok3) document.getElementById('stat-memories').textContent = (d3.core_memories?.length ?? '—');
  if (ok4) document.getElementById('stat-tasks').textContent = (d4.tasks?.length ?? '—');
}

async function loadHealthPanel() {
  const grid = document.getElementById('health-grid');
  if (grid) grid.innerHTML = '<div class="text-muted text-sm">Loading…</div>';
  const { ok, data } = await apiJSON('/api/health');
  if (!ok || !data.checks) return;
  const checks = data.checks;
  const tiles = [
    ['Database', checks.db],
    ['Redis', checks.redis],
    ['Model Provider', checks.model_provider],
    ['Search Provider', checks.search_provider],
  ];
  if (grid) {
    grid.innerHTML = tiles.map(([name, c]) => `
      <div class="health-tile ${c?.ok ? 'health-ok' : 'health-fail'}">
        <div class="health-name">${name}</div>
        <div class="health-status">${c?.ok ? '● Healthy' : '● Unhealthy'}</div>
        ${c?.details || c?.provider ? `<div class="text-xs text-muted" style="margin-top:4px">${c.details||c.provider||''}</div>` : ''}
      </div>`).join('');
  }
  const sch = checks.scheduler || {};
  const diagEl = document.getElementById('scheduler-diag');
  if (diagEl) diagEl.textContent = `Running: ${sch.running ? 'Yes' : 'No'}\nLast sweep: ${sch.last_run?.network_sweep || 'N/A'}\nJobs: ${(sch.jobs||[]).join(', ')||'none'}`;
}

async function loadAdminUsers() {
  const tbody = document.getElementById('users-tbody');
  if (!tbody) return;
  const { ok, data } = await apiJSON('/api/admin/users');
  if (!ok) { tbody.innerHTML = '<tr><td colspan="4" style="color:var(--red);text-align:center">Failed</td></tr>'; return; }
  const users = data.users || [];
  tbody.innerHTML = users.map(u => `
    <tr>
      <td><strong>${u.username}</strong></td>
      <td>
        <select class="input" data-uname="${u.username}" style="width:110px;padding:5px 8px;font-size:0.8rem" onchange="updateUserRole('${u.username}',this.value)">
          <option value="user" ${u.role==='user'?'selected':''}>user</option>
          <option value="admin" ${u.role==='admin'?'selected':''}>admin</option>
        </select>
      </td>
      <td><input type="password" class="input" id="upw-${u.username}" placeholder="New password" style="max-width:180px;padding:6px 10px;font-size:0.82rem"/></td>
      <td style="display:flex;gap:6px">
        <button class="btn btn-secondary btn-sm" onclick="saveUserPw('${u.username}')">Save</button>
        ${u.username !== 'admin' ? `<button class="btn btn-danger btn-sm" onclick="deleteUser('${u.username}')">Delete</button>` : ''}
      </td>
    </tr>`).join('');
}

async function createUser() {
  const u = document.getElementById('new-user-name')?.value.trim();
  const p = document.getElementById('new-user-pass')?.value;
  const r = document.getElementById('new-user-role')?.value || 'user';
  const st = document.getElementById('user-status');
  if (!u || !p) { if(st){st.textContent='Username and password required.';st.style.color='var(--red)';} return; }
  const { ok, data } = await apiJSON('/api/admin/users', { method:'POST', body: JSON.stringify({username:u,password:p,role:r}) });
  if (st) { st.textContent = ok ? 'User created.' : (data.detail||'Failed.'); st.style.color = ok?'var(--green)':'var(--red)'; }
  if (ok) { document.getElementById('new-user-name').value=''; document.getElementById('new-user-pass').value=''; loadAdminUsers(); }
}

async function updateUserRole(username, role) {
  await apiJSON(`/api/admin/users/${encodeURIComponent(username)}`, { method:'PATCH', body: JSON.stringify({role}) });
  toast('Role updated', 'success');
}

async function saveUserPw(username) {
  const pw = document.getElementById('upw-' + username)?.value.trim();
  if (!pw) { toast('Enter a new password', 'error'); return; }
  const { ok, data } = await apiJSON(`/api/admin/users/${encodeURIComponent(username)}`, { method:'PATCH', body: JSON.stringify({password:pw}) });
  toast(ok ? 'Password updated' : (data.detail||'Failed'), ok ? 'success' : 'error');
}

async function deleteUser(username) {
  if (!confirm(`Delete user "${username}"? This cannot be undone.`)) return;
  const { ok } = await apiJSON(`/api/admin/users/${encodeURIComponent(username)}`, { method:'DELETE' });
  toast(ok ? 'User deleted' : 'Failed', ok ? 'success' : 'error');
  if (ok) loadAdminUsers();
}

async function loadAdminSessions() {
  const tbody = document.getElementById('admin-sessions-tbody');
  if (!tbody) return;
  const { ok, data } = await apiJSON('/api/sessions?limit=100');
  if (!ok) return;
  const sessions = data.sessions || [];
  tbody.innerHTML = sessions.map(s => `
    <tr>
      <td><code class="text-xs">${s.session_id}</code></td>
      <td><span class="badge badge-blue">${s.category||'-'}</span></td>
      <td>${s.owner||'-'}</td>
      <td>${s.pinned?'📌 Yes':'—'}</td>
      <td style="display:flex;gap:6px">
        <button class="btn btn-secondary btn-sm" onclick="viewChatLog('${s.session_id}')">View</button>
        <button class="btn btn-secondary btn-sm" onclick="exportSession('${s.session_id}')">Export</button>
      </td>
    </tr>`).join('') || '<tr><td colspan="5" style="text-align:center;color:var(--muted)">No sessions</td></tr>';
}

async function loadCoreMemories() {
  const el = document.getElementById('core-memories-list');
  if (!el) return;
  const { ok, data } = await apiJSON('/api/admin/core-memories');
  if (!ok) { el.innerHTML = '<span class="text-muted text-sm">Failed to load</span>'; return; }
  const mems = data.core_memories || [];
  el.innerHTML = mems.length ? mems.map(m => `
    <div class="memory-pill">
      ${m.fact}
      <button class="del" onclick="deleteCoreMemory(${m.id},this)">✕</button>
    </div>`).join('')
    : '<span class="text-muted text-sm">No core memories yet.</span>';
}

async function deleteCoreMemory(id, btn) {
  btn.disabled = true;
  const { ok } = await apiJSON(`/api/admin/core-memories/${id}`, { method:'DELETE' });
  if (ok) { btn.closest('.memory-pill')?.remove(); toast('Memory deleted', 'success'); }
  else { btn.disabled = false; toast('Failed to delete', 'error'); }
}

async function runBackup() {
  const btn = document.getElementById('run-backup-btn');
  const st = document.getElementById('backup-status');
  btn.disabled = true; if(st) { st.textContent = 'Queued…'; st.style.color='var(--muted)'; }
  const { ok, data } = await apiJSON('/api/admin/backup', { method:'POST' });
  btn.disabled = false;
  if (st) { st.textContent = ok ? `✓ Job queued: #${data.job_id}` : '✕ '+( data.detail||'Failed'); st.style.color = ok?'var(--green)':'var(--red)'; }
  if (ok) { loadBackupHistory(); loadBackupJobs(); }
}

function resetBackupProfileForm() {
  window._editingBackupProfileId = null;
  const ids = [
    'backup-profile-name', 'backup-profile-path', 'backup-profile-host', 'backup-profile-port',
    'backup-profile-username', 'backup-profile-credential', 'backup-profile-cron',
    'backup-profile-interval', 'backup-profile-retention-count', 'backup-profile-retention-days'
  ];
  ids.forEach((id) => { const el = document.getElementById(id); if (el) el.value = ''; });
  const typeEl = document.getElementById('backup-profile-type');
  if (typeEl) typeEl.value = 'local';
  const checks = {
    'backup-profile-enabled': true,
    'backup-profile-include-db': true,
    'backup-profile-include-uploads': false,
    'backup-profile-include-configs': false,
    'backup-profile-include-logs': false,
  };
  Object.entries(checks).forEach(([id, val]) => { const el = document.getElementById(id); if (el) el.checked = val; });
}

function backupProfilePayloadFromForm() {
  return {
    name: document.getElementById('backup-profile-name')?.value.trim() || '',
    enabled: !!document.getElementById('backup-profile-enabled')?.checked,
    include_database: !!document.getElementById('backup-profile-include-db')?.checked,
    include_uploads: !!document.getElementById('backup-profile-include-uploads')?.checked,
    include_configs: !!document.getElementById('backup-profile-include-configs')?.checked,
    include_logs: !!document.getElementById('backup-profile-include-logs')?.checked,
    destination: {
      type: document.getElementById('backup-profile-type')?.value || 'local',
      path: document.getElementById('backup-profile-path')?.value.trim() || '',
      host: document.getElementById('backup-profile-host')?.value.trim() || '',
      port: Number(document.getElementById('backup-profile-port')?.value || 0) || null,
      username: document.getElementById('backup-profile-username')?.value.trim() || '',
      credential: document.getElementById('backup-profile-credential')?.value || '',
    },
    schedule: {
      cron: document.getElementById('backup-profile-cron')?.value.trim() || '',
      interval_minutes: Number(document.getElementById('backup-profile-interval')?.value || 0) || null,
    },
    retention_count: Number(document.getElementById('backup-profile-retention-count')?.value || 0) || null,
    retention_days: Number(document.getElementById('backup-profile-retention-days')?.value || 0) || null,
  };
}

async function saveBackupProfile() {
  const status = document.getElementById('backup-profile-status');
  const payload = backupProfilePayloadFromForm();
  if (!payload.name) {
    if (status) { status.textContent = 'Profile name is required.'; status.style.color = 'var(--red)'; }
    return;
  }
  const editingId = window._editingBackupProfileId;
  const url = editingId ? `/api/backups/profiles/${editingId}` : '/api/backups/profiles';
  const method = editingId ? 'PATCH' : 'POST';
  const { ok, data } = await apiJSON(url, { method, body: JSON.stringify(payload) });
  if (!ok) {
    if (status) { status.textContent = data.detail || 'Failed to save profile.'; status.style.color = 'var(--red)'; }
    return;
  }
  if (status) { status.textContent = editingId ? 'Profile updated.' : 'Profile created.'; status.style.color = 'var(--green)'; }
  resetBackupProfileForm();
  await loadBackupProfiles();
}

function fillBackupProfileForm(profile) {
  window._editingBackupProfileId = profile.id;
  const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v ?? ''; };
  const setChk = (id, v) => { const el = document.getElementById(id); if (el) el.checked = !!v; };
  setVal('backup-profile-name', profile.name || '');
  setVal('backup-profile-type', profile.destination?.type || 'local');
  setVal('backup-profile-path', profile.destination?.path || '');
  setVal('backup-profile-host', profile.destination?.host || '');
  setVal('backup-profile-port', profile.destination?.port || '');
  setVal('backup-profile-username', profile.destination?.username || '');
  setVal('backup-profile-credential', '');
  setVal('backup-profile-cron', profile.schedule?.cron || '');
  setVal('backup-profile-interval', profile.schedule?.interval_minutes || '');
  setVal('backup-profile-retention-count', profile.retention_count || '');
  setVal('backup-profile-retention-days', profile.retention_days || '');
  setChk('backup-profile-enabled', profile.enabled);
  setChk('backup-profile-include-db', profile.include_database);
  setChk('backup-profile-include-uploads', profile.include_uploads);
  setChk('backup-profile-include-configs', profile.include_configs);
  setChk('backup-profile-include-logs', profile.include_logs);
}

function editBackupProfile(profileId) {
  const profile = (window._backupProfilesById || {})[profileId];
  if (!profile) return;
  fillBackupProfileForm(profile);
}

async function runBackupProfile(profileId) {
  const st = document.getElementById('backup-status');
  if (st) { st.textContent = 'Queueing profile backup…'; st.style.color = 'var(--muted)'; }
  const { ok, data } = await apiJSON(`/api/backups/profiles/${profileId}/run`, { method: 'POST' });
  if (st) { st.textContent = ok ? `✓ Job queued: #${data.job_id}` : `✕ ${data.detail || 'Failed'}`; st.style.color = ok ? 'var(--green)' : 'var(--red)'; }
  if (ok) { loadBackupHistory(); loadBackupJobs(); }
}

function backupStatusBadge(status) {
  if (status === 'success') return '<span class="badge badge-green">success</span>';
  if (status === 'failed') return '<span class="badge badge-red">failed</span>';
  if (status === 'running') return '<span class="badge" style="background:#3b82f61f;color:#60a5fa;border:1px solid #3b82f633">running</span>';
  return '<span class="badge" style="background:#f59e0b1f;color:#fbbf24;border:1px solid #f59e0b33">queued</span>';
}

function backupDurationSeconds(job) {
  if (!job?.started_at) return '-';
  const start = new Date(job.started_at).getTime();
  const end = job.finished_at ? new Date(job.finished_at).getTime() : Date.now();
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return '-';
  return `${Math.round((end - start) / 1000)}s`;
}

function backupVerifiedBadge(job) {
  if (job.status !== 'success') return '<span class="badge" style="background:#f59e0b1f;color:#fbbf24;border:1px solid #f59e0b33">pending</span>';
  if (job.verified) return '<span class="badge badge-green">verified</span>';
  return '<span class="badge badge-red">failed</span>';
}

async function loadBackupKpis() {
  const ids = {
    lastBackup: document.getElementById('kpi-last-successful-backup'),
    lastRestore: document.getElementById('kpi-last-successful-restore-test'),
    rate7d: document.getElementById('kpi-backup-success-rate-7d'),
    rate30d: document.getElementById('kpi-backup-success-rate-30d'),
  };
  if (!ids.lastBackup || !ids.lastRestore || !ids.rate7d || !ids.rate30d) return;
  const { ok, data } = await apiJSON('/api/backups/kpis');
  if (!ok) return;
  const k = data.kpis || {};
  ids.lastBackup.textContent = k.last_successful_backup ? fmtDate(k.last_successful_backup) : '—';
  ids.lastRestore.textContent = k.last_successful_restore_test ? fmtDate(k.last_successful_restore_test) : '—';
  ids.rate7d.textContent = `${Number(k.backup_success_rate_7d || 0).toFixed(2)}%`;
  ids.rate30d.textContent = `${Number(k.backup_success_rate_30d || 0).toFixed(2)}%`;
}

async function loadBackupJobs(showToast = false) {
  const tbody = document.getElementById('backup-jobs-tbody');
  if (!tbody) return;
  const { ok, data } = await apiJSON('/api/backups/jobs?limit=25&offset=0');
  if (!ok) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--red)">Failed to load jobs</td></tr>';
    if (showToast) toast(data.detail || 'Failed to refresh jobs', 'error');
    return;
  }
  const jobs = data.jobs || [];
  tbody.innerHTML = jobs.length ? jobs.map((j) => `
    <tr>
      <td>#${j.id}</td>
      <td>${backupStatusBadge(j.status)}</td>
      <td>${backupVerifiedBadge(j)}</td>
      <td>${j.profile_id ?? '-'}</td>
      <td class="text-xs">${j.started_at ? fmtDate(j.started_at) : '-'}</td>
      <td class="text-xs">${backupDurationSeconds(j)}</td>
      <td class="text-xs">${j.bytes_written || 0}</td>
      <td class="text-xs">${j.artifact_path || '-'}</td>
      <td class="text-xs">${(j.error_message || j.verification_error) ? `<details><summary>View</summary>${j.error_message || j.verification_error}</details>` : '-'}</td>
    </tr>`).join('')
    : '<tr><td colspan="9" style="text-align:center;color:var(--muted);padding:20px">No backup jobs yet</td></tr>';
  await loadBackupKpis();
  if (showToast) toast('Backup jobs refreshed', 'success');
}

async function deleteBackupProfile(profileId) {
  if (!confirm('Delete this backup profile?')) return;
  const { ok, data } = await apiJSON(`/api/backups/profiles/${profileId}`, { method: 'DELETE' });
  if (!ok) { toast(data.detail || 'Failed to delete profile', 'error'); return; }
  toast('Profile deleted', 'success');
  loadBackupProfiles();
}

async function loadBackupProfiles() {
  const tbody = document.getElementById('backup-profiles-tbody');
  if (!tbody) return;
  const { ok, data } = await apiJSON('/api/backups/profiles');
  if (!ok) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--red)">Failed to load profiles</td></tr>';
    return;
  }
  const profiles = data.profiles || [];
  window._backupProfilesById = Object.fromEntries(profiles.map((p) => [p.id, p]));
  tbody.innerHTML = profiles.length ? profiles.map((p) => `
    <tr>
      <td><strong>${p.name}</strong><div class="text-xs text-muted">${p.enabled ? 'enabled' : 'disabled'}</div></td>
      <td>${p.destination?.type || 'local'} ${p.destination?.host ? `@ ${p.destination.host}` : ''}<div class="text-xs text-muted">${p.destination?.path || '-'}</div></td>
      <td class="text-xs">${p.schedule?.cron || (p.schedule?.interval_minutes ? `every ${p.schedule.interval_minutes}m` : '-')}</td>
      <td class="text-xs">count=${p.retention_count ?? '-'}, days=${p.retention_days ?? '-'}</td>
      <td style="display:flex;gap:6px;flex-wrap:wrap">
        <button class="btn btn-secondary btn-sm" onclick="editBackupProfile(${p.id})">Edit</button>
        <button class="btn btn-primary btn-sm" onclick="runBackupProfile(${p.id})">Run now</button>
        <button class="btn btn-danger btn-sm" onclick="deleteBackupProfile(${p.id})">Delete</button>
      </td>
    </tr>
  `).join('') : '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:20px">No profiles</td></tr>';
}

async function loadRestoreFile(event) {
  const file = event?.target?.files?.[0];
  if (!file) return;
  const txt = await file.text();
  const box = document.getElementById('backup-restore-json');
  if (box) box.value = txt;
}

async function runRestorePreflight() {
  const json = document.getElementById('backup-restore-json')?.value.trim();
  const st = document.getElementById('restore-status');
  const progress = document.getElementById('restore-progress');
  if (!json) { if(st){st.textContent='Paste backup JSON first.';st.style.color='var(--red)';} return; }
  const { ok, data } = await apiJSON('/api/restores/preflight', { method:'POST', body: JSON.stringify({backup_json:json}) });
  if (!ok) {
    if (st) { st.textContent = data.detail || 'Preflight failed'; st.style.color = 'var(--red)'; }
    return;
  }
  restorePreflightId = data.preflight_id;
  const checks = data.report?.checks || [];
  const failing = checks.filter((c) => !c.ok).map((c) => c.name);
  if (st) {
    st.textContent = failing.length ? `Preflight failed: ${failing.join(', ')}` : 'Preflight passed. You can confirm restore.';
    st.style.color = failing.length ? 'var(--red)' : 'var(--green)';
  }
  if (progress) progress.textContent = `Preflight ID: ${restorePreflightId}`;
}

async function restoreBackup() {
  const json = document.getElementById('backup-restore-json')?.value.trim();
  const st = document.getElementById('restore-status');
  const progress = document.getElementById('restore-progress');
  if (!json || !restorePreflightId) {
    if (st) { st.textContent = 'Run preflight first.'; st.style.color = 'var(--red)'; }
    return;
  }
  if (!confirm('This will run a destructive restore. Continue?')) return;
  const { ok, data } = await apiJSON('/api/restores/start', { method:'POST', body: JSON.stringify({backup_json:json, preflight_id:restorePreflightId, confirm_restore:true}) });
  if (!ok) {
    if (st) { st.textContent = data.detail || 'Failed to queue restore'; st.style.color = 'var(--red)'; }
    return;
  }
  const jobId = data.job_id;
  if (st) { st.textContent = `Restore queued (job ${jobId})`; st.style.color = 'var(--green)'; }
  if (progress) progress.textContent = 'Waiting for restore worker…';
  if (restorePollTimer) clearInterval(restorePollTimer);
  restorePollTimer = setInterval(async () => {
    const res = await apiJSON(`/api/restores/jobs/${jobId}`);
    if (!res.ok) return;
    const job = res.data || {};
    if (progress) progress.textContent = `Step: ${job.current_step || '-'} (${job.progress_percent || 0}%)`;
    if (['success', 'failed'].includes(job.status)) {
      clearInterval(restorePollTimer);
      restorePollTimer = null;
      if (st) {
        st.textContent = job.status === 'success' ? 'Restore completed successfully.' : (job.error_message || 'Restore failed');
        st.style.color = job.status === 'success' ? 'var(--green)' : 'var(--red)';
      }
    }
  }, 1500);
}

async function loadBackupHistory() {
  const tbody = document.getElementById('backup-history-tbody');
  if (!tbody) return;
  const { ok, data } = await apiJSON('/api/admin/backup/history');
  if (!ok) return;
  const history = data.history || [];
  tbody.innerHTML = history.length ? history.map(h => `
    <tr>
      <td class="text-xs">${fmtDate(h.timestamp)}</td>
      <td>${h.trigger||'-'}</td>
      <td><span class="badge ${h.status==='success'?'badge-green':'badge-red'}">${h.status}</span></td>
      <td>${h.session_count||0}</td>
      <td>${h.mode||'-'}</td>
    </tr>`).join('')
    : '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:20px">No backup history</td></tr>';
}

async function loadAuditLog() {
  const tbody = document.getElementById('audit-tbody');
  if (!tbody) return;
  const { ok, data } = await apiJSON('/api/admin/audit?limit=50');
  if (!ok) { tbody.innerHTML='<tr><td colspan="5" style="color:var(--red);text-align:center">Failed</td></tr>'; return; }
  const events = data.events || [];
  tbody.innerHTML = events.length ? events.map(e => `
    <tr>
      <td class="text-xs">${fmtDate(e.created_at)}</td>
      <td>${e.username||'-'}</td>
      <td><code class="text-xs">${e.action||'-'}</code></td>
      <td class="text-xs">${e.session_id||'-'}</td>
      <td class="text-xs text-muted">${e.details||''}</td>
    </tr>`).join('')
    : '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:20px">No audit events</td></tr>';
}

// ── AI Models ─────────────────────────────────────
const MODEL_CFG_MAP = {
  'cfg-ollama-url':       'ollama_base_url',
  'cfg-ollama-models':    'ollama_model_list',
  'cfg-openai-key':       'openai_api_key',
  'cfg-gemini-key':       'gemini_api_key',
  'cfg-anthropic-key':    'anthropic_api_key',
  'cfg-openrouter-key':   'openrouter_api_key',
  'cfg-openrouter-model': 'openrouter_model',
  'cfg-anythingllm-url':  'anythingllm_base_url',
  'cfg-anythingllm-key':  'anythingllm_api_key',
  'cfg-anythingllm-ws':   'anythingllm_workspace',
  'cfg-search-provider':  'web_fallback_provider',
  'cfg-serpapi-key':      'serpapi_api_key',
  'cfg-default-model':    'default_model',
};

async function personasLoad() {
  await personasFetch();
  if (window._personasBound) return;
  window._personasBound = true;
  document.getElementById('personas-refresh-btn')?.addEventListener('click', personasFetch);
  document.getElementById('create-persona-btn')?.addEventListener('click', createPersonaPreset);
}

async function personasFetch() {
  const body = document.getElementById('personas-body');
  if (body) body.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:22px;color:var(--muted)">Loading…</td></tr>';
  const { ok, data } = await apiJSON('/api/personas');
  if (!ok) {
    if (body) body.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:22px;color:var(--red)">Failed to load personas.</td></tr>';
    return;
  }
  const personas = data.personas || [];
  if (!personas.length) {
    if (body) body.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:22px;color:var(--muted)">No personas yet.</td></tr>';
    return;
  }
  if (body) {
    body.innerHTML = personas.map(p => `
      <tr>
        <td><input id="persona-name-${p.id}" class="input" value="${(p.name || '').replace(/"/g, '&quot;')}" /></td>
        <td>${p.username ? `👤 ${p.username}` : '🌐 Global'}</td>
        <td><input id="persona-tags-${p.id}" class="input" value="${(p.tags || '').replace(/"/g, '&quot;')}" /></td>
        <td><input type="checkbox" id="persona-default-${p.id}" ${p.is_default ? 'checked' : ''}/></td>
        <td><textarea id="persona-prompt-${p.id}" class="input" rows="3">${(p.system_prompt || '').replace(/</g, '&lt;')}</textarea></td>
        <td style="display:flex;gap:6px;flex-wrap:wrap">
          <button class="btn btn-secondary btn-sm" onclick="savePersonaPreset(${p.id})">Save</button>
          <button class="btn btn-danger btn-sm" onclick="removePersonaPreset(${p.id})">Delete</button>
        </td>
      </tr>
    `).join('');
  }
}

async function createPersonaPreset() {
  const status = document.getElementById('persona-create-status');
  const payload = {
    name: document.getElementById('persona-name')?.value.trim() || '',
    tags: document.getElementById('persona-tags')?.value.trim() || '',
    system_prompt: document.getElementById('persona-system-prompt')?.value.trim() || '',
    is_default: !!document.getElementById('persona-is-default')?.checked,
    is_global: !!document.getElementById('persona-is-global')?.checked,
  };
  if (!payload.name || !payload.system_prompt) {
    if (status) { status.textContent = 'Name and prompt are required.'; status.style.color = 'var(--red)'; }
    return;
  }
  const { ok, data } = await apiJSON('/api/personas', { method: 'POST', body: JSON.stringify(payload) });
  if (!ok) {
    if (status) { status.textContent = data.detail || 'Failed to create persona.'; status.style.color = 'var(--red)'; }
    return;
  }
  if (status) { status.textContent = 'Persona created.'; status.style.color = 'var(--green)'; }
  ['persona-name','persona-tags','persona-system-prompt'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  const isDef = document.getElementById('persona-is-default');
  if (isDef) isDef.checked = false;
  await personasFetch();
}

async function savePersonaPreset(personaId) {
  const payload = {
    name: document.getElementById(`persona-name-${personaId}`)?.value.trim() || '',
    tags: document.getElementById(`persona-tags-${personaId}`)?.value.trim() || '',
    system_prompt: document.getElementById(`persona-prompt-${personaId}`)?.value.trim() || '',
    is_default: !!document.getElementById(`persona-default-${personaId}`)?.checked,
  };
  const { ok, data } = await apiJSON(`/api/personas/${personaId}`, { method: 'PATCH', body: JSON.stringify(payload) });
  toast(ok ? 'Persona updated' : (data.detail || 'Update failed'), ok ? 'success' : 'error');
  if (ok) await personasFetch();
}

async function removePersonaPreset(personaId) {
  if (!confirm('Delete this persona?')) return;
  const { ok, data } = await apiJSON(`/api/personas/${personaId}`, { method: 'DELETE' });
  toast(ok ? 'Persona deleted' : (data.detail || 'Delete failed'), ok ? 'success' : 'error');
  if (ok) await personasFetch();
}

async function modelsLoad() {
  if (State.role !== 'admin') return;
  // Always reload config values on page visit
  const { ok, data } = await apiJSON('/api/admin/configs');
  if (ok) {
    for (const [elId, cfgKey] of Object.entries(MODEL_CFG_MAP)) {
      const el = document.getElementById(elId);
      if (!el) continue;
      const val = data[cfgKey];
      if (val === undefined || val === null) continue;
      // If value is masked (e.g. sk-...r4f2), show placeholder instead so
      // the user knows a key is set but doesn't see it; input stays empty
      // so saving won't overwrite with the masked text.
      if (val.includes('...') || val === '****') {
        el.placeholder = '(key already set — enter new value to change)';
        el.value = '';
      } else {
        el.value = val;
      }
    }
  }
  if (window._modelsBound) return;
  window._modelsBound = true;
  document.getElementById('save-model-cfg-btn')?.addEventListener('click', saveModelCfg);
}

async function saveModelCfg() {
  const configs = {};
  for (const [elId, cfgKey] of Object.entries(MODEL_CFG_MAP)) {
    const el = document.getElementById(elId);
    if (!el) continue;
    const val = el.value.trim();
    // Only include if the user actually typed something (non-empty)
    // Empty fields or fields still showing masked text are skipped
    if (val !== '') configs[cfgKey] = val;
  }
  if (Object.keys(configs).length === 0) {
    toast('No changes to save', 'info');
    return;
  }
  const { ok, data } = await apiJSON('/api/admin/configs', { method: 'POST', body: JSON.stringify({ configs }) });
  const st = document.getElementById('model-save-status');
  if (ok) {
    const saved = data?.saved?.length ?? 0;
    const msg = `✓ Saved ${saved} setting${saved !== 1 ? 's' : ''} successfully!`;
    if (st) { st.textContent = msg; st.style.color = 'var(--green)'; setTimeout(() => st.textContent = '', 4000); }
    toast(msg, 'success');
    // Reload to show updated masked values
    setTimeout(() => { window._modelsBound = false; modelsLoad(); }, 400);
  } else {
    if (st) { st.textContent = '✕ Failed to save'; st.style.color = 'var(--red)'; }
    toast('Save failed', 'error');
  }
}

// ── Settings ──────────────────────────────────────
async function _loadSettingsValues() {
  const { ok, data } = await apiJSON('/api/admin/configs');
  if (ok) {
    const map = {
      'cfg-agent-name':  'chat_agent_name',
      'cfg-agent-avatar':'chat_agent_avatar_url',
      'cfg-resend-key':  'resend_api_key',
      'cfg-resend-from': 'resend_from_email',
      'cfg-notif-to':    'notification_email_to',
    };
    for (const [id, key] of Object.entries(map)) {
      const el = document.getElementById(id);
      if (el && data[key]) el.value = data[key];
    }
  }
  const prefRes = await apiJSON('/api/users/me/notification-preferences');
  if (prefRes.ok) {
    const p = prefRes.data;
    const b    = document.getElementById('notif-browser');   if (b)    b.checked    = !!p.browser_notify_on_away_replies;
    const em   = document.getElementById('notif-email');     if (em)   em.checked   = !!p.email_notify_on_away_replies;
    const intv = document.getElementById('notif-interval');  if (intv) intv.value   = p.minimum_notify_interval_seconds ?? 300;
    const dg   = document.getElementById('notif-digest');    if (dg)   dg.value     = p.digest_mode || 'immediate';
  }
  const mpRes = await apiJSON('/api/users/me/memory-policy');
  if (mpRes.ok) {
    const p = mpRes.data || {};
    const a = document.getElementById('mem-policy-auto'); if (a) a.checked = !!p.auto_capture_enabled;
    const r = document.getElementById('mem-policy-approval'); if (r) r.checked = !!p.require_approval;
    const pii = document.getElementById('mem-policy-pii'); if (pii) pii.checked = !!p.pii_strict_mode;
    const rd = document.getElementById('mem-policy-retention'); if (rd) rd.value = p.retention_days ?? 365;
    const c = document.getElementById('mem-policy-categories'); if (c) c.value = (p.allowed_categories || []).join(', ');
  }
  const chatPrefRes = await apiJSON('/api/users/me/chat-preferences');
  if (chatPrefRes.ok) {
    const pref = chatPrefRes.data || {};
    const compact = document.getElementById('chat-low-token-mode');
    if (compact) compact.checked = !!pref.low_token_mode;
  }
}

async function settingsLoad() {
  if (window._settingsBound) {
    // Re-load values but don't re-bind
    _loadSettingsValues();
    return;
  }
  window._settingsBound = true;
  await _loadSettingsValues();

  document.getElementById('save-agent-settings-btn')?.addEventListener('click', async () => {
    const configs = {
      chat_agent_name: document.getElementById('cfg-agent-name')?.value.trim() || '',
      chat_agent_avatar_url: document.getElementById('cfg-agent-avatar')?.value.trim() || '',
    };
    const { ok } = await apiJSON('/api/admin/configs', { method:'POST', body: JSON.stringify({configs}) });
    toast(ok ? 'Agent settings saved' : 'Failed to save', ok ? 'success' : 'error');
  });

  document.getElementById('change-pw-btn')?.addEventListener('click', async () => {
    const cur = document.getElementById('pw-current')?.value;
    const nw = document.getElementById('pw-new')?.value;
    const st = document.getElementById('pw-status');
    if (!cur || !nw) { if(st){st.textContent='Enter both passwords.';st.style.color='var(--red)';} return; }
    const { ok, data } = await apiJSON('/api/admin/change-password', { method:'POST', body: JSON.stringify({current_password:cur,new_password:nw}) });
    if (st) { st.textContent = ok ? '✓ Password updated.' : ('✕ '+(data.detail||'Failed.')); st.style.color = ok?'var(--green)':'var(--red)'; }
    if (ok) { document.getElementById('pw-current').value=''; document.getElementById('pw-new').value=''; }
  });

  document.getElementById('save-notif-btn')?.addEventListener('click', async () => {
    const payload = {
      browser_notify_on_away_replies: !!document.getElementById('notif-browser')?.checked,
      email_notify_on_away_replies: !!document.getElementById('notif-email')?.checked,
      minimum_notify_interval_seconds: Number(document.getElementById('notif-interval')?.value || 300),
      digest_mode: document.getElementById('notif-digest')?.value || 'immediate',
      digest_interval_minutes: 30,
    };
    const { ok } = await apiJSON('/api/users/me/notification-preferences', { method:'PUT', body: JSON.stringify(payload) });
    toast(ok ? 'Notification preferences saved' : 'Failed', ok ? 'success' : 'error');
  });

  document.getElementById('save-chat-prefs-btn')?.addEventListener('click', async () => {
    const payload = {
      low_token_mode: !!document.getElementById('chat-low-token-mode')?.checked,
    };
    const { ok } = await apiJSON('/api/users/me/chat-preferences', { method: 'PUT', body: JSON.stringify(payload) });
    toast(ok ? 'Chat preferences saved' : 'Failed to save chat preferences', ok ? 'success' : 'error');
  });

  document.getElementById('save-memory-policy-btn')?.addEventListener('click', async () => {
    const payload = {
      auto_capture_enabled: !!document.getElementById('mem-policy-auto')?.checked,
      require_approval: !!document.getElementById('mem-policy-approval')?.checked,
      pii_strict_mode: !!document.getElementById('mem-policy-pii')?.checked,
      retention_days: Number(document.getElementById('mem-policy-retention')?.value || 365),
      allowed_categories: (document.getElementById('mem-policy-categories')?.value || '').split(',').map(s => s.trim()).filter(Boolean),
    };
    const { ok } = await apiJSON('/api/users/me/memory-policy', { method: 'PUT', body: JSON.stringify(payload) });
    toast(ok ? 'Memory policy saved' : 'Failed to save memory policy', ok ? 'success' : 'error');
  });

  document.getElementById('save-email-cfg-btn')?.addEventListener('click', async () => {
    const configs = {
      resend_api_key: document.getElementById('cfg-resend-key')?.value.trim() || '',
      resend_from_email: document.getElementById('cfg-resend-from')?.value.trim() || '',
      notification_email_to: document.getElementById('cfg-notif-to')?.value.trim() || '',
    };
    const { ok } = await apiJSON('/api/admin/configs', { method:'POST', body: JSON.stringify({configs}) });
    toast(ok ? 'Email config saved' : 'Failed', ok ? 'success' : 'error');
  });

  document.getElementById('save-memory-policy-btn')?.addEventListener('click', async () => {
    const retentionDays = Number(document.getElementById('memory-retention-days')?.value || 365);
    if (!Number.isInteger(retentionDays) || retentionDays < 1 || retentionDays > 3650) {
      toast('Retention days must be between 1 and 3650', 'error');
      return;
    }
    const categories = (document.getElementById('memory-allowed-categories')?.value || '')
      .split(',')
      .map(v => v.trim())
      .filter(Boolean);
    const payload = {
      auto_capture_enabled: !!document.getElementById('memory-auto-capture')?.checked,
      require_approval: !!document.getElementById('memory-require-approval')?.checked,
      pii_strict_mode: !!document.getElementById('memory-pii-strict')?.checked,
      retention_days: retentionDays,
      allowed_categories: categories,
    };
    const { ok, data } = await apiJSON('/api/users/me/memory-policy', { method:'PUT', body: JSON.stringify(payload) });
    toast(ok ? 'Memory policy saved' : (data.detail || 'Failed to save memory policy'), ok ? 'success' : 'error');
    if (ok && typeof window.updateMemoryPolicyBadge === 'function') window.updateMemoryPolicyBadge(payload);
  });
}

window.updateMemoryPolicyBadge = function updateMemoryPolicyBadge(policy = {}) {
  const badge = document.getElementById('memory-policy-badge');
  if (!badge) return;
  const autoCapture = !!policy.auto_capture_enabled;
  const requireApproval = !!policy.require_approval;
  const label = !autoCapture ? 'Memory: Off' : (requireApproval ? 'Memory: Manual Approval' : 'Memory: Auto Capture');
  badge.textContent = label;
};

// ── Utility ────────────────────────────────────────
function fmtDate(v) {
  if (!v) return '-';
  const d = new Date(v);
  return isNaN(d) ? v : d.toLocaleString();
}
