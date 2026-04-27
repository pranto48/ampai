/* =====================================================
   AmpAI — Chat Feature Logic
   ===================================================== */

let chatAttachments = [];
let _chatHandlersBound = false;
const PERSONA_PREF_KEY = 'ampai_persona_id';

function chatInit() {
  // Only load sessions each time; bind handlers only once
  loadSessions();
  loadPersonaOptions();
  _updateChatSessionDisplay();
  _loadPersonaOptions();
  _loadSessionTaskSuggestions(State.sessionId);
  if (!_chatHandlersBound) {
    _chatHandlersBound = true;
    _bindChatHandlers();
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

  // File attach
  document.getElementById('attach-btn')?.addEventListener('click', () => {
    document.getElementById('file-input')?.click();
  });

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

  const applyRetrievalPreset = (preset) => {
    const topK = document.getElementById('memory-top-k');
    const recency = document.getElementById('recency-bias');
    const category = document.getElementById('category-filter');
    if (!topK || !recency || !category) return;
    if (preset === 'recent') {
      topK.value = '4';
      recency.value = '0.8';
      category.value = '';
      return;
    }
    if (preset === 'deep') {
      topK.value = '12';
      recency.value = '0.15';
      category.value = '';
      return;
    }
    topK.value = '5';
    recency.value = '0.35';
    category.value = '';
  };

  document.getElementById('retrieval-preset-balanced')?.addEventListener('click', () => applyRetrievalPreset('balanced'));
  document.getElementById('retrieval-preset-recent')?.addEventListener('click', () => applyRetrievalPreset('recent'));
  document.getElementById('retrieval-preset-deep')?.addEventListener('click', () => applyRetrievalPreset('deep'));
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
  const params = new URLSearchParams({ limit: 60, offset: 0 });
  if (query) params.set('q', query);
  const { ok, data } = await apiJSON('/api/sessions?' + params.toString());
  const list = document.getElementById('sessions-list');
  if (!list) return;
  if (!ok) {
    list.innerHTML = '<div style="padding:12px;font-size:.8rem;color:var(--red)">Failed to load sessions</div>';
    return;
  }
  const sessions = data.sessions || [];
  if (!sessions.length) {
    list.innerHTML = '<div style="padding:14px;text-align:center;font-size:.8rem;color:var(--muted)">No sessions yet.<br>Start a new chat!</div>';
    return;
  }
  list.innerHTML = sessions.map(s => `
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
    // Hover style
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
}

async function _loadSessionHistory(sessionId) {
  const msgs = document.getElementById('chat-messages');
  if (!msgs) return;
  msgs.innerHTML = '<div style="text-align:center;padding:48px;color:var(--muted)">Loading history…</div>';
  const { ok, data } = await apiJSON(`/api/history/${sessionId}`);
  if (!ok) {
    msgs.innerHTML = '<div style="text-align:center;padding:48px;color:var(--red)">Failed to load history</div>';
    return;
  }
  msgs.innerHTML = '';
  const messages = data.messages || [];
  _hideSuggestedActions();
  if (!messages.length) {
    msgs.innerHTML = _welcomeMsg();
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
    const recencyBias = parseFloat(document.getElementById('recency-bias')?.value || '0.35');
    const categoryFilter = (document.getElementById('category-filter')?.value || '').trim();
    payload.memory_top_k = Number.isFinite(topK) ? topK : 5;
    payload.recency_bias = Number.isFinite(recencyBias) ? recencyBias : 0.35;
    if (categoryFilter) payload.category_filter = categoryFilter;
  }

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
      persona_id: document.getElementById('persona-select')?.value || null,
      use_web_search: !!(document.getElementById('web-search-toggle')?.checked),
      attachments:  atts,
    }),
  });

  _removeTyping(typId);

  if (ok) {
    _appendMsg('ai', data.response || data.detail || 'No response');
    _renderTaskSuggestions(data.task_suggestions || []);
    loadSessions(); // refresh sidebar
    _loadSessionTaskSuggestions(State.sessionId);
  } else {
    _appendMsg('ai', '⚠️ ' + (data.detail || 'Something went wrong. Check your AI model config.'));
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
