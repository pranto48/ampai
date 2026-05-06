/* =====================================================
   AmpAI — Chat Feature Logic
   ===================================================== */

let chatAttachments = [];
let _chatHandlersBound = false;
const PERSONA_PREF_KEY = 'ampai_persona_id';
const WEB_SEARCH_PREF_KEY = 'ampai_web_search_enabled';
const SESSIONS_CACHE_KEY = 'ampai_cached_sessions';
const LOCAL_SESSION_INDEX_KEY = 'ampai_local_session_index';
const LOCAL_HISTORY_PREFIX = 'ampai_local_history:';
let chatOutputMode = 'normal';
const RETRIEVAL_PRESETS = {
  balanced: { topK: 6, recencyBias: 0.35, semanticWeight: 0.55, contextBudget: 3200, hybridEnabled: true },
  fast: { topK: 3, recencyBias: 0.2, semanticWeight: 0.45, contextBudget: 1800, hybridEnabled: true },
  deep: { topK: 12, recencyBias: 0.15, semanticWeight: 0.7, contextBudget: 5000, hybridEnabled: true },
};
let currentRetrievalPreset = 'balanced';
let retrievalPresetScope = 'user';

function chatInit() {
  // Only load sessions each time; bind handlers only once
  loadSessions();
  _updateChatSessionDisplay();
  _loadPersonaOptions();
  _loadSessionTaskSuggestions(State.sessionId);
  _restoreLocalPreferences();
  _loadChatPreferences();
  _loadMediaLibrary();
  if (!_chatHandlersBound) {
    _chatHandlersBound = true;
    _bindChatHandlers();
  }
}

function _readLocalSessionIndex() {
  try {
    const raw = localStorage.getItem(LOCAL_SESSION_INDEX_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function _upsertLocalSessionIndex(sessionId, category = 'Uncategorized') {
  if (!sessionId) return;
  const rows = _readLocalSessionIndex().filter((s) => s && s.session_id && s.session_id !== sessionId);
  rows.unshift({ session_id: sessionId, category, updated_at: new Date().toISOString(), pinned: false, source: 'local' });
  try { localStorage.setItem(LOCAL_SESSION_INDEX_KEY, JSON.stringify(rows.slice(0, 200))); } catch {}
}

function _historyKey(sessionId) {
  return `${LOCAL_HISTORY_PREFIX}${sessionId || ''}`;
}

function _appendLocalHistory(sessionId, type, content) {
  if (!sessionId || !content) return;
  try {
    const raw = localStorage.getItem(_historyKey(sessionId));
    const parsed = raw ? JSON.parse(raw) : [];
    const rows = Array.isArray(parsed) ? parsed : [];
    rows.push({ type, content, created_at: new Date().toISOString() });
    localStorage.setItem(_historyKey(sessionId), JSON.stringify(rows.slice(-500)));
  } catch {}
}

function _readLocalHistory(sessionId) {
  try {
    const raw = localStorage.getItem(_historyKey(sessionId));
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

async function _loadChatPreferences() {
  const { ok, data } = await apiJSON('/api/users/me/chat-preferences');
  if (!ok) return;
  chatOutputMode = (data?.chat_output_mode || 'normal') === 'compact' ? 'compact' : 'normal';
  const preset = (data?.retrieval_default_preset || 'balanced').toLowerCase();
  retrievalPresetScope = (data?.retrieval_scope || 'user').toLowerCase() === 'chat' ? 'chat' : 'user';
  const chatScopedPreset = localStorage.getItem(`ampai_retrieval_preset:${State.sessionId || ''}`);
  const effectivePreset = retrievalPresetScope === 'chat' && chatScopedPreset ? chatScopedPreset : preset;
  if (RETRIEVAL_PRESETS[effectivePreset]) {
    currentRetrievalPreset = effectivePreset;
    _applyRetrievalPreset(effectivePreset);
  }
}

function _applyRetrievalPreset(preset) {
  const topK = document.getElementById('memory-top-k');
  const recency = document.getElementById('memory-recency-bias') || document.getElementById('recency-bias');
  if (!topK || !recency || !RETRIEVAL_PRESETS[preset]) return;
  const cfg = RETRIEVAL_PRESETS[preset];
  topK.value = String(cfg.topK);
  recency.value = String(cfg.recencyBias);
  currentRetrievalPreset = preset;
  if (retrievalPresetScope === 'chat' && State.sessionId) {
    localStorage.setItem(`ampai_retrieval_preset:${State.sessionId}`, preset);
  }
}

async function loadMemoryPolicyBadge() {
  const { ok, data } = await apiJSON('/api/users/me/memory-policy');
  if (!ok) return;
  if (typeof window.updateMemoryPolicyBadge === 'function') {
    window.updateMemoryPolicyBadge(data || {});
  }
}

function _bindChatHandlers() {
  // New chat
  document.getElementById('new-chat-btn')?.addEventListener('click', () => {
    State.sessionId = _newSessionId();
    _upsertLocalSessionIndex(State.sessionId);
    _updateChatSessionDisplay();
    const msgs = document.getElementById('chat-messages');
    if (msgs) msgs.innerHTML = _welcomeMsg();
    chatAttachments = [];
    _renderAttachPreviews();
    document.querySelectorAll('#sessions-list .session-item').forEach(e => e.classList.remove('active'));
    _setSendEnabled(false);
  });

  // Session search
  document.getElementById('session-search')?.addEventListener('input', e => {
    loadSessions(e.target.value.trim());
  });

  // Textarea auto-resize + send enable
  const input = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');

  input?.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 140) + 'px';
    _setSendEnabled(input.value.trim().length > 0 || chatAttachments.length > 0);
  });

  input?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!sendBtn?.disabled) _sendChat();
    }
  });

  sendBtn?.addEventListener('click', _sendChat);
  document.getElementById('persona-select')?.addEventListener('change', (e) => {
    localStorage.setItem(PERSONA_PREF_KEY, e.target.value || '');
  });
  document.getElementById('web-search-toggle')?.addEventListener('change', (e) => {
    localStorage.setItem(WEB_SEARCH_PREF_KEY, e.target.checked ? '1' : '0');
    toast(e.target.checked ? 'Web search enabled' : 'Web search disabled', 'info');
  });
  document.getElementById('model-select')?.addEventListener('change', (e) => {
    localStorage.setItem('ampai_model_type', e.target.value || '');
  });
  document.getElementById('memory-mode-select')?.addEventListener('change', (e) => {
    localStorage.setItem('ampai_memory_mode', e.target.value || '');
  });

  // File attach
  document.getElementById('attach-btn')?.addEventListener('click', () => {
    document.getElementById('file-input')?.click();
  });
  document.getElementById('quick-capture-btn')?.addEventListener('click', _quickCaptureMemory);
  document.getElementById('media-refresh-btn')?.addEventListener('click', _loadMediaLibrary);

  document.getElementById('file-input')?.addEventListener('change', async e => {
    const files = Array.from(e.target.files || []);
    for (const file of files) {
      const fd = new FormData();
      fd.append('file', file);
      try {
        const headers = {};
        if (State.token) headers['Authorization'] = 'Bearer ' + State.token;
        const res = await fetch(`/api/upload?session_id=${encodeURIComponent(State.sessionId)}`, {
          method: 'POST', headers, body: fd,
        });
        if (res.ok) {
          const d = await res.json();
          chatAttachments.push(d);
          _renderAttachPreviews();
          _setSendEnabled(true);
        } else {
          toast('Upload failed', 'error');
        }
      } catch (err) {
        toast('Upload error: ' + err.message, 'error');
      }
    }
    e.target.value = '';
  });

  // Focus input box border
  const inputBox = document.getElementById('input-box');
  document.getElementById('chat-input')?.addEventListener('focus', () => {
    if (inputBox) inputBox.style.borderColor = 'var(--accent)';
  });
  document.getElementById('chat-input')?.addEventListener('blur', () => {
    if (inputBox) inputBox.style.borderColor = 'var(--border)';
  });

  document.getElementById('retrieval-preset-balanced')?.addEventListener('click', () => _applyRetrievalPreset('balanced'));
  document.getElementById('retrieval-preset-fast')?.addEventListener('click', () => _applyRetrievalPreset('fast'));
  document.getElementById('retrieval-preset-deep')?.addEventListener('click', () => _applyRetrievalPreset('deep'));
}

function _restoreLocalPreferences() {
  const toggle = document.getElementById('web-search-toggle');
  if (toggle) {
    const pref = localStorage.getItem(WEB_SEARCH_PREF_KEY);
    if (pref === '1') toggle.checked = true;
    if (pref === '0') toggle.checked = false;
  }
  const modelSel = document.getElementById('model-select');
  if (modelSel) {
    const m = localStorage.getItem('ampai_model_type');
    if (m) modelSel.value = m;
  }
  const memSel = document.getElementById('memory-mode-select');
  if (memSel) {
    const m = localStorage.getItem('ampai_memory_mode');
    if (m) memSel.value = m;
  }
}

async function _loadMediaLibrary() {
  const listEl = document.getElementById('media-library-list');
  if (!listEl) return;
  listEl.innerHTML = 'Loading uploaded files…';
  const { ok, data } = await apiJSON('/api/media');
  if (!ok) {
    listEl.innerHTML = '<div style="color:var(--red)">Failed to load attached media.</div>';
    return;
  }
  const rows = data.media || [];
  if (!rows.length) {
    listEl.innerHTML = '<div style="color:var(--muted)">No uploaded files yet.</div>';
    return;
  }
  listEl.innerHTML = rows.map((m) => `
    <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;border:1px solid var(--border);border-radius:8px;padding:6px 8px">
      <div style="min-width:0">
        <div style="font-size:.8rem;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${(m.filename || 'file').replace(/</g, '&lt;')}</div>
        <div style="font-size:.72rem;color:var(--muted)">${(m.session_id || '-')} · ${m.created_at ? new Date(m.created_at).toLocaleString() : ''}</div>
      </div>
      <button type="button" class="btn btn-secondary btn-sm" onclick="_attachMediaFromLibrary('${String(m.id)}')">Attach</button>
    </div>
  `).join('');
  window._mediaLibraryRows = rows;
}

function _attachMediaFromLibrary(id) {
  const rows = window._mediaLibraryRows || [];
  const selected = rows.find((r) => String(r.id) === String(id));
  if (!selected) return;
  chatAttachments.push({
    filename: selected.filename,
    url: selected.url,
    type: selected.mime_type || 'application/octet-stream',
    extracted_text: null,
  });
  _renderAttachPreviews();
  _setSendEnabled(true);
  toast('File attached from media library', 'success');
}

function _setSendEnabled(enabled) {
  const btn = document.getElementById('send-btn');
  if (!btn) return;
  btn.disabled = !enabled;
  btn.style.opacity = enabled ? '1' : '0.5';
  btn.style.cursor  = enabled ? 'pointer' : 'not-allowed';
}

function _updateChatSessionDisplay() {
  const idEl   = document.getElementById('chat-session-id');
  const nameEl = document.getElementById('chat-session-name');
  if (idEl)   idEl.textContent   = State.sessionId;
  if (nameEl) nameEl.textContent = 'Session';
}

// ── Sessions ───────────────────────────────────────
async function loadSessions(query = '') {
  const list = document.getElementById('sessions-list');
  if (!list) return;
  const params = new URLSearchParams({ limit: 60, offset: 0 });
  if (query) params.set('query', query);
  const showSessions = (sessions) => {
    const ordered = [...(sessions || [])].sort((a, b) => {
      const ta = new Date(a.updated_at || 0).getTime();
      const tb = new Date(b.updated_at || 0).getTime();
      return tb - ta;
    });
    if (!ordered.length) {
      list.innerHTML = '<div style="padding:14px;text-align:center;font-size:.8rem;color:var(--muted)">No sessions yet.<br>Start a new chat!</div>';
      return;
    }
    list.innerHTML = ordered.map(s => `
      <div class="session-item ${s.session_id === State.sessionId ? 'active' : ''}"
        data-sid="${s.session_id}" style="padding:10px 12px;border-radius:8px;cursor:pointer;
        margin-bottom:2px;transition:all .15s;border-left:2px solid transparent">
        <div style="font-size:.85rem;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
          ${s.session_id}
        </div>
        <div style="font-size:.72rem;margin-top:3px;display:flex;align-items:center;gap:6px">
          <span style="background:rgba(99,102,241,.15);color:#818cf8;border:1px solid rgba(99,102,241,.25);
            padding:2px 6px;border-radius:999px;font-size:.68rem;font-weight:600">${s.category || 'Uncategorized'}</span>
          ${s.pinned ? '📌' : ''}
        </div>
      </div>
    `).join('');

    list.querySelectorAll('.session-item').forEach(item => {
      item.addEventListener('mouseenter', () => {
        if (!item.classList.contains('active')) item.style.background = 'var(--bg-3)';
      });
      item.addEventListener('mouseleave', () => {
        if (!item.classList.contains('active')) item.style.background = '';
      });
      item.addEventListener('click', () => {
        State.sessionId = item.dataset.sid;
        localStorage.setItem('ampai_session_id', State.sessionId);
        _updateChatSessionDisplay();
        _loadSessionHistory(State.sessionId);
        _loadSessionTaskSuggestions(State.sessionId);
        list.querySelectorAll('.session-item').forEach(i => {
          i.classList.remove('active');
          i.style.background = '';
          i.style.borderLeft = '2px solid transparent';
        });
        item.classList.add('active');
        item.style.background  = 'rgba(99,102,241,.12)';
        item.style.borderLeft  = '2px solid var(--accent)';
      });
    });
  };

  const loadFromCache = () => {
    try {
      const raw = localStorage.getItem(SESSIONS_CACHE_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  };
  const saveCache = (sessions) => {
    try { localStorage.setItem(SESSIONS_CACHE_KEY, JSON.stringify(sessions)); } catch {}
  };

  let response = await apiJSON('/api/sessions?' + params.toString());
  if (!response.ok) {
    await new Promise(r => setTimeout(r, 300));
    response = await apiJSON('/api/sessions?' + params.toString());
  }
  if (!response.ok) {
    const cached = loadFromCache();
    if (cached.length) showSessions(cached);
    else list.innerHTML = '<div style="padding:12px;font-size:.8rem;color:var(--red)">Failed to load sessions</div>';
    toast('Session list may be stale. Failed to refresh sessions.', 'warning');
    if (window.__DEV__) {
      console.warn('Failed to load sessions after retry', {
        status: response.data?.status || response.data?.status_code || 'unknown',
        detail: response.data?.detail || response.data?.error || 'No error detail',
      });
    }
    return;
  }
  const serverSessions = response.data.sessions || [];
  const localSessions = _readLocalSessionIndex();
  const mergedById = {};
  [...localSessions, ...serverSessions].forEach((s) => {
    if (!s?.session_id) return;
    const existing = mergedById[s.session_id];
    if (!existing) mergedById[s.session_id] = s;
    else {
      const tExisting = new Date(existing.updated_at || 0).getTime();
      const tCurrent = new Date(s.updated_at || 0).getTime();
      if (tCurrent >= tExisting) mergedById[s.session_id] = { ...existing, ...s };
    }
  });
  const sessions = Object.values(mergedById).filter((s) =>
    !query || String(s.session_id || '').toLowerCase().includes(String(query).toLowerCase())
  );
  if (response.data?.needs_migration) {
    const cta = State.role === 'admin' ? ' <a href="#admin" style="color:var(--accent)">Open Admin</a>' : '';
    toast('Session migration required.' + cta, 'warning');
  }
  saveCache(sessions);
  showSessions(sessions);
}

async function _loadSessionHistory(sessionId) {
  const msgs = document.getElementById('chat-messages');
  if (!msgs) return;
  msgs.innerHTML = '<div style="text-align:center;padding:48px;color:var(--muted)">Loading history…</div>';
  const { ok, data } = await apiJSON(`/api/history/${sessionId}`);
  if (!ok) {
    const localMessages = _readLocalHistory(sessionId);
    if (localMessages.length) {
      msgs.innerHTML = '';
      localMessages.forEach((m) => _appendMsg(m.type === 'human' ? 'user' : 'ai', m.content));
      _scrollToBottom();
      toast('Showing local cached history (server history unavailable).', 'warning');
      return;
    }
    msgs.innerHTML = `<div style="text-align:center;padding:48px;color:var(--red)">Failed to load history${data?.detail ? ': ' + data.detail : ''}</div>`;
    return;
  }
  msgs.innerHTML = '';
  const messages = data.messages || [];
  const rawRowCount = data.raw_row_count || 0;
  _hideSuggestedActions();
  if (!messages.length) {
    if (rawRowCount > 0) {
      // Messages exist in DB but couldn't be parsed — surface this clearly
      msgs.innerHTML = `<div style="text-align:center;padding:48px;color:var(--yellow)">
        ⚠️ This session has ${rawRowCount} stored message(s) but they could not be decoded.<br>
        <span style="font-size:.8rem;color:var(--muted);margin-top:8px;display:block">
          Try restarting the backend — a message format fix was applied.
        </span>
      </div>`;
    } else {
      msgs.innerHTML = _welcomeMsg();
    }
    return;
  }
  messages.forEach(m => _appendMsg(m.type === 'human' ? 'user' : 'ai', m.content));
  _scrollToBottom();
}


// ── Send ───────────────────────────────────────────
async function _sendChat() {
  const inputEl  = document.getElementById('chat-input');
  const message  = inputEl?.value.trim() || '';
  const atts     = [...chatAttachments];
  if (!message && atts.length === 0) return;

  chatAttachments = [];
  _renderAttachPreviews();
  _appendMsg('user', message || '(attachment)');
  _appendLocalHistory(State.sessionId, 'human', message || '(attachment)');
  if (inputEl) { inputEl.value = ''; inputEl.style.height = 'auto'; }
  _setSendEnabled(false);

  const typId = _showTyping();

  const memoryMode = document.getElementById('memory-mode-select')?.value || 'full';
  const payload = {
    session_id:   State.sessionId,
    message:      message || 'Please review the attached files.',
    model_type:   document.getElementById('model-select')?.value || 'ollama',
    memory_mode:  memoryMode,
    use_web_search: !!(document.getElementById('web-search-toggle')?.checked),
    attachments:  atts,
  };
  if (memoryMode === 'indexed') {
    const topK = parseInt(document.getElementById('memory-top-k')?.value || '5', 10);
    const recencyBias = parseFloat(document.getElementById('memory-recency-bias')?.value || '0.35');
    const categoryFilter = (document.getElementById('memory-category-filter')?.value || '').trim();
    payload.memory_top_k = Number.isFinite(topK) ? topK : 5;
    payload.recency_bias = Number.isFinite(recencyBias) ? recencyBias : 0.35;
    if (categoryFilter) payload.category_filter = categoryFilter;
  }

    try {
    const { ok, data } = await apiJSON('/api/chat', {
      method: 'POST',
      body: JSON.stringify({
        session_id:   State.sessionId,
        message:      message || 'Please review the attached files.',
        model_type:   document.getElementById('model-select')?.value        || 'ollama',
        memory_mode:  document.getElementById('memory-mode-select')?.value  || 'full',
        memory_top_k: Number(document.getElementById('memory-top-k')?.value || 5),
        memory_recency_bias: Number(document.getElementById('memory-recency-bias')?.value || 0),
        memory_category_filter: document.getElementById('memory-category-filter')?.value || '',
        metadata: {
          retrieval_preset: currentRetrievalPreset,
          retrieval_preset_values: RETRIEVAL_PRESETS[currentRetrievalPreset] || RETRIEVAL_PRESETS.balanced,
        },
        persona_id: document.getElementById('persona-select')?.value || null,
        chat_output_mode: chatOutputMode,
        use_web_search: !!(document.getElementById('web-search-toggle')?.checked),
        attachments:  atts,
      }),
    });

    if (ok) {
      const aiText = data.response || data.detail;
      if (!aiText) {
        _appendMsg('ai', '💬 (no text response — check your AI model settings)');
        _appendLocalHistory(State.sessionId, 'ai', '💬 (no text response — check your AI model settings)');
      } else {
        _appendMsg('ai', aiText);
        _appendLocalHistory(State.sessionId, 'ai', aiText);
      }
      // Show memory save feedback
      const memStatus = data.memory_status || {};
      const memAction = (memStatus.memory_action || data.memory_action || '').toLowerCase();
      const memFact   = memStatus.memory_fact   || data.memory_fact   || '';
      const memCat    = memStatus.memory_category || data.memory_category || '';
      if (memAction === 'saved' && memFact) {
        const snippet = memFact.length > 80 ? memFact.slice(0, 80) + '…' : memFact;
        const catLabel = memCat ? ` [${memCat}]` : '';
        toast(`✅ Memory saved${catLabel}: ${snippet}`, 'success');
      } else if (memAction === 'pending_approval' && memFact) {
        toast('📥 Memory captured — awaiting approval', 'info');
      }
      _renderTaskSuggestions(data.task_suggestions || []);
      _upsertLocalSessionIndex(State.sessionId);
      loadSessions(); // refresh sidebar
      _loadSessionTaskSuggestions(State.sessionId);
    } else {
      _appendMsg('ai', '⚠️ ' + (data.detail || 'Something went wrong. Check your AI model config.'));
      _appendLocalHistory(State.sessionId, 'ai', '⚠️ ' + (data.detail || 'Something went wrong. Check your AI model config.'));
    }
  } catch (err) {
    _appendMsg('ai', '⚠️ Failed to send message: ' + (err?.message || 'unknown error'));
    _appendLocalHistory(State.sessionId, 'ai', '⚠️ Failed to send message: ' + (err?.message || 'unknown error'));
  } finally {
    _removeTyping(typId);
  }
}

async function _loadPersonaOptions() {
  const sel = document.getElementById('persona-select');
  if (!sel) return;
  const prev = sel.value;
  const { ok, data } = await apiJSON('/api/personas');
  if (!ok) return;
  const personas = data.personas || [];
  sel.innerHTML = '<option value="">🎭 Persona (None)</option>' + personas.map(p =>
    `<option value="${p.id}">${(p.is_default ? '★ ' : '') + (p.name || 'Unnamed')}</option>`
  ).join('');
  if (prev && [...sel.options].some(o => o.value === prev)) {
    sel.value = prev;
  } else {
    const def = personas.find(p => p.is_default);
    if (def) sel.value = def.id;
  }
}

function _renderTaskSuggestions(suggestions) {
  const panel = document.getElementById('task-suggestions-panel');
  const list = document.getElementById('task-suggestions-list');
  if (!panel || !list) return;
  if (!suggestions.length) {
    panel.style.display = 'none';
    list.innerHTML = '';
    return;
  }
  panel.style.display = 'block';
  list.innerHTML = suggestions.map(s => `
    <div style="display:flex;align-items:center;gap:8px;background:var(--bg-3);border:1px solid var(--border);padding:8px;border-radius:8px">
      <div style="flex:1">
        <div style="font-size:.82rem;font-weight:600">${(s.title || 'Suggested task')}</div>
        <div style="font-size:.75rem;color:var(--muted)">${(s.description || '').slice(0,120)}</div>
      </div>
      <button class="btn btn-primary btn-sm" onclick="_convertTaskSuggestion('${s.id}')">Create Task</button>
    </div>
  `).join('');
}

async function _loadSessionTaskSuggestions(sessionId) {
  const { ok, data } = await apiJSON(`/api/sessions/${encodeURIComponent(sessionId)}/task-suggestions`);
  if (!ok) return;
  const pending = (data.suggestions || []).filter(s => s.status === 'pending');
  _renderTaskSuggestions(pending);
}

async function _convertTaskSuggestion(id) {
  const { ok } = await apiJSON(`/api/tasks/from-suggestion/${encodeURIComponent(id)}`, { method: 'POST' });
  toast(ok ? 'Task created from suggestion' : 'Failed to create task', ok ? 'success' : 'error');
  _loadSessionTaskSuggestions(State.sessionId);
}

async function _quickCaptureMemory() {
  const text = prompt('Quick capture: what should AmpAI remember?') || '';
  const clean = text.trim();
  if (!clean) return;
  const { ok } = await apiJSON('/api/quick-capture', {
    method: 'POST',
    body: JSON.stringify({ text: clean, session_id: State.sessionId }),
  });
  toast(ok ? 'Captured to Memory Inbox' : 'Failed to capture', ok ? 'success' : 'error');
}

// ── DOM helpers ────────────────────────────────────
function _appendMsg(role, content) {
  const msgs = document.getElementById('chat-messages');
  if (!msgs) return;

  const isUser = role === 'user';
  const avLetter = isUser ? (State.user?.[0] || 'U').toUpperCase() : 'AI';
  const avGrad   = isUser
    ? 'linear-gradient(135deg,#6366f1,#a855f7)'
    : 'linear-gradient(135deg,#10b981,#3b82f6)';

  // Simple markdown: code blocks, bold, line breaks
  const html = content
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/```([\s\S]*?)```/g, '<pre style="background:rgba(0,0,0,.4);padding:10px;border-radius:6px;overflow-x:auto;margin-top:8px;font-size:.82rem"><code>$1</code></pre>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');

  const div = document.createElement('div');
  div.style.cssText = `display:flex;gap:12px;max-width:78%;animation:msgIn .25s ease;
    align-self:${isUser ? 'flex-end;flex-direction:row-reverse' : 'flex-start'};`;

  div.innerHTML = `
    <div style="width:34px;height:34px;border-radius:50%;flex-shrink:0;
      background:${avGrad};display:flex;align-items:center;justify-content:center;
      font-size:.75rem;font-weight:700;color:#fff">${avLetter}</div>
    <div style="padding:12px 16px;border-radius:12px;line-height:1.6;font-size:.9rem;
      ${isUser
        ? 'background:var(--accent);color:#fff;border-top-right-radius:3px'
        : 'background:var(--bg-3);border:1px solid var(--border);border-top-left-radius:3px'
      }">${html}</div>`;

  msgs.appendChild(div);
  _scrollToBottom();
}

function _showTyping() {
  const id   = 'typ-' + Date.now();
  const msgs = document.getElementById('chat-messages');
  if (!msgs) return id;
  const div  = document.createElement('div');
  div.id = id;
  div.style.cssText = 'display:flex;gap:12px;max-width:78%;align-self:flex-start;';
  div.innerHTML = `
    <div style="width:34px;height:34px;border-radius:50%;flex-shrink:0;
      background:linear-gradient(135deg,#10b981,#3b82f6);
      display:flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:700;color:#fff">AI</div>
    <div style="padding:12px 16px;border-radius:12px;background:var(--bg-3);border:1px solid var(--border)">
      <div style="display:inline-flex;gap:4px;align-items:center">
        <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
      </div>
    </div>`;
  msgs.appendChild(div);
  _scrollToBottom();
  return id;
}

function _removeTyping(id) { document.getElementById(id)?.remove(); }

function _scrollToBottom() {
  const msgs = document.getElementById('chat-messages');
  if (msgs) msgs.scrollTop = msgs.scrollHeight;
}

function _welcomeMsg() {
  return `<div style="display:flex;gap:12px;max-width:80%;align-self:flex-start">
    <div style="width:34px;height:34px;border-radius:50%;flex-shrink:0;
      background:linear-gradient(135deg,#10b981,#3b82f6);
      display:flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:700;color:#fff">AI</div>
    <div style="padding:14px 18px;border-radius:12px;background:var(--bg-3);border:1px solid var(--border);font-size:.9rem;line-height:1.6">
      <strong>Hello! I'm AmpAI.</strong><br>
      I remember your conversations and use that memory to give you better answers.<br><br>
      <span style="color:var(--muted);font-size:.85rem">Start chatting — every message is saved and indexed for future recall.</span>
    </div>
  </div>`;
}

function _renderAttachPreviews() {
  const el = document.getElementById('attach-previews');
  if (!el) return;
  el.innerHTML = chatAttachments.map((a, i) => `
    <div style="display:inline-flex;align-items:center;gap:6px;
      background:rgba(99,102,241,.12);border:1px solid rgba(99,102,241,.25);
      border-radius:999px;padding:4px 10px;font-size:.78rem">
      📎 <span style="max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${a.filename}</span>
      <button onclick="chatAttachments.splice(${i},1);_renderAttachPreviews();_setSendEnabled(chatAttachments.length>0||document.getElementById('chat-input').value.trim().length>0)"
        style="background:none;border:none;color:var(--red);cursor:pointer;font-size:.9rem;padding:0 2px">✕</button>
    </div>`).join('');
}
