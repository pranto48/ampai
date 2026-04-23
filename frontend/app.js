document.addEventListener('DOMContentLoaded', () => {
    async function ensureAuth() {
        const existing = localStorage.getItem('ampai_token');
        if (existing) {
            const who = await fetch('/api/auth/whoami', { headers: { Authorization: `Bearer ${existing}` } });
            if (who.ok) return true;
            localStorage.removeItem('ampai_token');
        }

        const doRegister = confirm('No active login. Press OK to Register new user, Cancel to Login.');
        const username = prompt(doRegister ? 'Create username:' : 'Username:') || '';
        const password = prompt(doRegister ? 'Create password:' : 'Password:') || '';
        if (!username || !password) return false;

        try {
            if (doRegister) {
                const reg = await fetch('/api/auth/register', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ username, password })
                });
                if (!reg.ok) {
                    const err = await reg.json();
                    throw new Error(err.detail || 'Registration failed');
                }
            }

            const loginRes = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ username, password })
            });
            if (!loginRes.ok) {
                const err = await loginRes.json();
                throw new Error(err.detail || 'Login failed');
            }
            const data = await loginRes.json();
            localStorage.setItem('ampai_token', data.token);
            localStorage.setItem('ampai_role', data.role);
            localStorage.setItem('ampai_username', data.username || username);
            return true;
        } catch (e) {
            alert('Authentication failed: ' + e.message);
            localStorage.removeItem('ampai_token');
            return false;
        }
    }

    async function apiFetch(url, options = {}) {
        const token = localStorage.getItem('ampai_token') || '';
        const headers = options.headers || {};
        headers['Authorization'] = `Bearer ${token}`;
        return fetch(url, { ...options, headers });
    }
    const chatMessages = document.getElementById('chat-messages');
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-btn');
    const chatForm = document.getElementById('chat-form');
    const modelSelect = document.getElementById('model-select');
    const apiKeyInput = document.getElementById('api-key');
    const apiKeyLabel = document.getElementById('api-key-label');
    const newChatBtn = document.getElementById('new-chat-btn');
    const sessionsList = document.getElementById('sessions-list');
    const currentSessionTitle = document.getElementById('current-session-title');
    const currentSessionIdDisplay = document.getElementById('current-session-id');
    const sessionCategorySelect = document.getElementById('session-category');
    const deleteSessionBtn = document.getElementById('delete-session-btn');
    const attachBtn = document.getElementById('attach-btn');
    const fileInput = document.getElementById('file-input');
    const attachmentPreview = document.getElementById('attachment-preview');
    const webSearchToggle = document.getElementById('web-search-toggle');
    const sessionSearchInput = document.getElementById('session-search');
    const showArchivedToggle = document.getElementById('show-archived');
    const pinSessionBtn = document.getElementById('pin-session-btn');
    const archiveSessionBtn = document.getElementById('archive-session-btn');
    const summarizeEmailBtn = document.getElementById('summarize-email-btn');
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.querySelector('.sidebar');

    let currentSessionId = generateSessionId();
    let currentSessionCategory = "Uncategorized";
    currentSessionIdDisplay.textContent = currentSessionId;

    let globalConfigs = {};

    async function checkGlobalConfigs() {
        try {
            const res = await apiFetch('/api/configs/status');
            globalConfigs = await res.json();
            if (globalConfigs.default_model && !sessionStorage.getItem('model_set')) {
                modelSelect.value = globalConfigs.default_model;
                sessionStorage.setItem('model_set', 'true');
            }
            updateApiKeyVisibility();
        } catch (e) {
            console.error(e);
        }
    }

    function updateApiKeyVisibility() {
        const val = modelSelect.value;
        if (['openai', 'gemini', 'anthropic', 'generic', 'openrouter', 'anythingllm'].includes(val)) {
            if (globalConfigs[val]) {
                apiKeyLabel.style.display = 'block';
                apiKeyLabel.innerHTML = 'API Key <span style="color:#10b981;font-size:0.7rem;">(Global Configured)</span>';
                apiKeyInput.style.display = 'none';
            } else {
                apiKeyLabel.style.display = 'block';
                apiKeyLabel.textContent = 'API Key';
                apiKeyInput.style.display = 'block';
            }
        } else {
            apiKeyLabel.style.display = 'none';
            apiKeyInput.style.display = 'none';
        }
    }

    // Load existing sessions on startup
    ensureAuth().then((ok) => {
        if (!ok) return;
        loadSessions();
        checkGlobalConfigs();
        loadTasks();
    });

    if (mobileMenuBtn && sidebar) {
        mobileMenuBtn.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
        
        document.addEventListener('click', (e) => {
            if (sidebar.classList.contains('open') && !sidebar.contains(e.target) && !mobileMenuBtn.contains(e.target)) {
                sidebar.classList.remove('open');
            }
        });
    }

    // Event Listeners
    sessionCategorySelect.addEventListener('change', async (e) => {
        const newCategory = e.target.value;
        currentSessionCategory = newCategory;
        try {
            await apiFetch(`/api/sessions/${currentSessionId}/category`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category: newCategory })
            });
            loadSessions(); // Refresh sidebar to show new category grouping
        } catch (error) {
            console.error('Failed to update category', error);
        }
    });

    if (deleteSessionBtn) {
        deleteSessionBtn.addEventListener('click', async () => {
            if (!confirm(`Are you sure you want to permanently delete session: ${currentSessionId}?`)) return;
            try {
                const response = await apiFetch(`/api/sessions/${currentSessionId}`, { method: 'DELETE' });
                if (response.ok) {
                    newChatBtn.click();
                    loadSessions();
                } else {
                    alert('Failed to delete session');
                }
            } catch (e) {
                console.error("Error deleting session", e);
            }
        });
    }

    modelSelect.addEventListener('change', () => {
        sessionStorage.setItem('model_set', 'true');
        updateApiKeyVisibility();
    });

    let currentAttachments = [];

    if (attachBtn) {
        attachBtn.addEventListener('click', () => fileInput.click());
    }

    if (fileInput) {
        fileInput.addEventListener('change', async (e) => {
            const files = e.target.files;
            if (!files || files.length === 0) return;
            
            attachBtn.style.opacity = '0.5';
            
            for (let i = 0; i < files.length; i++) {
                const formData = new FormData();
                formData.append('file', files[i]);
                try {
                    const response = await apiFetch('/api/upload', {
                        method: 'POST',
                        body: formData
                    });
                    if (response.ok) {
                        const data = await response.json();
                        currentAttachments.push(data);
                        renderAttachmentPreviews();
                        sendBtn.removeAttribute('disabled');
                    }
                } catch (err) {
                    console.error("Upload failed", err);
                }
            }
            attachBtn.style.opacity = '1';
            fileInput.value = '';
        });
    }

    function renderAttachmentPreviews() {
        if (!attachmentPreview) return;
        attachmentPreview.innerHTML = '';
        currentAttachments.forEach((att, index) => {
            const pill = document.createElement('div');
            pill.style.background = 'rgba(16, 185, 129, 0.1)';
            pill.style.border = '1px solid rgba(16, 185, 129, 0.3)';
            pill.style.padding = '4px 8px';
            pill.style.borderRadius = '4px';
            pill.style.fontSize = '0.8rem';
            pill.style.display = 'flex';
            pill.style.alignItems = 'center';
            pill.style.gap = '6px';
            
            const name = document.createElement('span');
            name.textContent = att.filename;
            name.style.maxWidth = '150px';
            name.style.overflow = 'hidden';
            name.style.textOverflow = 'ellipsis';
            name.style.whiteSpace = 'nowrap';
            
            const del = document.createElement('button');
            del.innerHTML = '&times;';
            del.style.background = 'none';
            del.style.border = 'none';
            del.style.color = '#ef4444';
            del.style.cursor = 'pointer';
            del.onclick = () => {
                currentAttachments.splice(index, 1);
                renderAttachmentPreviews();
                if (currentAttachments.length === 0 && messageInput.value.trim().length === 0) {
                    sendBtn.setAttribute('disabled', 'true');
                }
            };
            
            pill.appendChild(name);
            pill.appendChild(del);
            attachmentPreview.appendChild(pill);
        });
    }

    messageInput.addEventListener('input', () => {
        // Auto-resize textarea
        messageInput.style.height = 'auto';
        messageInput.style.height = (messageInput.scrollHeight) + 'px';
        
        // Enable/disable send button
        if (messageInput.value.trim().length > 0 || currentAttachments.length > 0) {
            sendBtn.removeAttribute('disabled');
        } else {
            sendBtn.setAttribute('disabled', 'true');
        }
    });

    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (messageInput.value.trim().length > 0) {
                chatForm.dispatchEvent(new Event('submit'));
            }
        }
    });


    if (sessionSearchInput) {
        sessionSearchInput.addEventListener('input', () => loadSessions());
    }
    if (showArchivedToggle) {
        showArchivedToggle.addEventListener('change', () => loadSessions());
    }
    if (pinSessionBtn) {
        pinSessionBtn.addEventListener('click', async () => {
            await apiFetch(`/api/sessions/${currentSessionId}/pin`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ value: true })
            });
            loadSessions();
        });
    }
    if (archiveSessionBtn) {
        archiveSessionBtn.addEventListener('click', async () => {
            await apiFetch(`/api/sessions/${currentSessionId}/archive`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ value: true })
            });
            loadSessions();
        });
    }
    if (summarizeEmailBtn) {
        summarizeEmailBtn.addEventListener('click', async () => {
            appendMessage('user', 'Summarize today email report', true);
            const res = await apiFetch('/api/email/summary/today', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_type: modelSelect.value, api_key: apiKeyInput.value || null })
            });
            const data = await res.json();
            appendMessage('ai', data.summary || data.detail || 'No summary available');
        });
    }

    newChatBtn.addEventListener('click', () => {
        currentSessionId = generateSessionId();
        currentSessionIdDisplay.textContent = currentSessionId;
        chatMessages.innerHTML = `
            <div class="message ai-message welcome-message">
                <div class="avatar">AI</div>
                <div class="bubble">
                    <p>New session started. How can I assist you?</p>
                </div>
            </div>
        `;
        document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = messageInput.value.trim();
        if (!message && currentAttachments.length === 0) return;

        const sentAttachments = [...currentAttachments];
        currentAttachments = [];
        renderAttachmentPreviews();

        let displayHtml = message || '';
        if (sentAttachments.length > 0) {
            const attHtml = sentAttachments.map(a => {
                if (a.type.startsWith('image/')) {
                    return `<div style="margin-top: 8px;"><img src="${a.url}" style="max-width: 100%; max-height: 300px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1);"></div>`;
                }
                return `<div style="margin-top: 8px; padding: 6px 10px; background: rgba(255,255,255,0.05); border-radius: 4px; font-size: 0.8rem; border: 1px solid rgba(255,255,255,0.1);">📎 ${a.filename}</div>`;
            }).join('');
            displayHtml += (message ? '<br>' : '') + attHtml;
        }

        // Add user message to UI
        appendMessage('user', displayHtml, true);
        messageInput.value = '';
        messageInput.style.height = 'auto';
        sendBtn.setAttribute('disabled', 'true');

        // Show typing indicator
        const typingId = showTypingIndicator();

        try {
            const response = await apiFetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: currentSessionId,
                    message: message || "Please review the attached files.",
                    model_type: modelSelect.value,
                    api_key: apiKeyInput.value || null,
                    memory_mode: document.getElementById('memory-mode').value,
                    use_web_search: webSearchToggle ? webSearchToggle.checked : false,
                    attachments: sentAttachments
                })
            });

            const data = await response.json();
            removeTypingIndicator(typingId);
            
            if (response.ok) {
                appendMessage('ai', data.response || data.detail || 'No response');
                if (data.web_search && data.web_search.enabled) {
                    appendMessage('ai', `🌐 Web search: ${data.web_search.status} (${data.web_search.provider || 'none'})`);
                }
                // Refresh sessions list in case this was a new session
                loadSessions();
            } else {
                appendMessage('ai', `Error: ${data.detail || 'Something went wrong.'}`);
            }
        } catch (error) {
            removeTypingIndicator(typingId);
            appendMessage('ai', `Connection Error: ${error.message}`);
        }
    });

    // Helper Functions
    function generateSessionId() {
        return 'session_' + Math.random().toString(36).substring(2, 9);
    }

    function appendMessage(role, content, isPreFormatted = false) {
        const div = document.createElement('div');
        div.className = `message ${role}-message`;
        
        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        avatar.textContent = role === 'user' ? 'U' : 'AI';

        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        
        if (isPreFormatted) {
            bubble.innerHTML = content;
        } else {
            // Simple markdown parsing for code blocks and line breaks
            // Also format attachments that were stored as raw text from Postgres
            let formattedContent = content
                .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
                .replace(/\[Attachments: (.*?)\]/g, '<div style="margin-bottom: 8px; padding: 6px 10px; background: rgba(255,255,255,0.05); border-radius: 4px; font-size: 0.8rem; border: 1px solid rgba(255,255,255,0.1); color: var(--text-secondary);">📎 $1</div>')
                .replace(/\n/g, '<br>');
                
            bubble.innerHTML = formattedContent;
        }

        div.appendChild(avatar);
        div.appendChild(bubble);
        chatMessages.appendChild(div);
        
        scrollToBottom();
    }

    function showTypingIndicator() {
        const id = 'typing-' + Date.now();
        const div = document.createElement('div');
        div.className = 'message ai-message';
        div.id = id;
        
        div.innerHTML = `
            <div class="avatar">AI</div>
            <div class="bubble">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        `;
        
        chatMessages.appendChild(div);
        scrollToBottom();
        return id;
    }

    function removeTypingIndicator(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    async function loadSessions() {
        try {
            const query = encodeURIComponent(sessionSearchInput ? sessionSearchInput.value.trim() : '');
            const archived = showArchivedToggle && showArchivedToggle.checked ? 'true' : 'false';
            const response = await apiFetch(`/api/sessions?query=${query}&archived=${archived}`);
            const data = await response.json();
            
            sessionsList.innerHTML = '';
            if (data.sessions && data.sessions.length > 0) {
                // Group sessions by category
                const groups = {};
                data.sessions.forEach(s => {
                    if (!groups[s.category]) groups[s.category] = [];
                    groups[s.category].push(s.session_id);
                });
                
                for (const [category, ids] of Object.entries(groups)) {
                    // Create Category Header
                    const header = document.createElement('div');
                    header.className = 'category-header';
                    header.style.fontSize = '0.75rem';
                    header.style.color = 'var(--text-secondary)';
                    header.style.marginTop = '12px';
                    header.style.marginBottom = '6px';
                    header.style.textTransform = 'uppercase';
                    header.style.fontWeight = 'bold';
                    header.textContent = category;
                    sessionsList.appendChild(header);
                    
                    ids.forEach(sessionId => {
                        const li = document.createElement('li');
                        li.className = 'session-item';
                        if (sessionId === currentSessionId) {
                            li.classList.add('active');
                            sessionCategorySelect.value = category; // Update dropdown for active
                        }
                        li.textContent = sessionId;
                        li.onclick = () => {
                            sessionCategorySelect.value = category;
                            loadSessionHistory(sessionId);
                        }
                        sessionsList.appendChild(li);
                    });
                }
            } else {
                sessionsList.innerHTML = '<li class="session-item">No memories yet</li>';
            }
        } catch (error) {
            console.error('Failed to load sessions', error);
        }
    }

    async function loadSessionHistory(sessionId) {
        currentSessionId = sessionId;
        currentSessionIdDisplay.textContent = sessionId;
        
        // Update UI active state
        document.querySelectorAll('.session-item').forEach(el => {
            if (el.textContent === sessionId) el.classList.add('active');
            else el.classList.remove('active');
        });

        try {
            chatMessages.innerHTML = '<div style="text-align:center; color:var(--text-secondary); margin-top:20px;">Loading memory...</div>';
            
            const response = await apiFetch(`/api/history/${sessionId}`);
            const data = await response.json();
            
            chatMessages.innerHTML = '';
            
            if (data.messages && data.messages.length > 0) {
                data.messages.forEach(msg => {
                    appendMessage(msg.type === 'human' ? 'user' : 'ai', msg.content);
                });
            } else {
                chatMessages.innerHTML = `
                    <div class="message ai-message welcome-message">
                        <div class="avatar">AI</div>
                        <div class="bubble">
                            <p>Memory loaded. Empty session.</p>
                        </div>
                    </div>
                `;
            }
        } catch (error) {
            chatMessages.innerHTML = `<div style="color:red; text-align:center;">Failed to load memory: ${error.message}</div>`;
        }
    }

    // --- Update Checker Logic ---
    const updateBanner = document.getElementById('update-banner');
    const syncCodeBtn = document.getElementById('sync-code-btn');
    let initialMtime = null;

    async function checkUpdates() {
        try {
            const response = await apiFetch('/api/status');
            if (!response.ok) return;
            const data = await response.json();
            
            if (initialMtime === null) {
                initialMtime = data.latest_mtime;
            } else if (data.latest_mtime > initialMtime) {
                updateBanner.style.display = 'flex';
            }
        } catch (e) {
            console.warn('Could not check for updates', e);
        }
    }

    // Poll every 3 seconds
    setInterval(checkUpdates, 3000);

    const syncModal = document.getElementById('sync-modal');
    const syncLogs = document.getElementById('sync-logs');

    function addSyncLog(msg, color = '#10b981') {
        if (!syncLogs) return;
        const div = document.createElement('div');
        div.style.color = color;
        const time = new Date().toLocaleTimeString([], { hour12: false });
        div.textContent = `[${time}] ${msg}`;
        syncLogs.appendChild(div);
        syncLogs.scrollTop = syncLogs.scrollHeight;
    }

    if (syncCodeBtn) {
        syncCodeBtn.addEventListener('click', () => {
            updateBanner.style.display = 'none';
            if (syncModal) syncModal.style.display = 'flex';
            if (syncLogs) syncLogs.innerHTML = '';
            
            addSyncLog("Initiating architecture sync...");
            addSyncLog("Waiting for backend Uvicorn to safely restart...");
            
            let wasOffline = false;
            let attempts = 0;
            
            const pollInterval = setInterval(async () => {
                attempts++;
                try {
                    const res = await apiFetch('/api/status');
                    if (res.ok) {
                        if (wasOffline || attempts > 3) {
                            addSyncLog("Backend is stable and online!", "#3b82f6");
                            addSyncLog("Applying updates and reloading interface...");
                            clearInterval(pollInterval);
                            setTimeout(() => {
                                window.location.reload();
                            }, 1000);
                        } else {
                            addSyncLog("Backend responding. Checking stability...", "#64748b");
                        }
                    } else {
                        wasOffline = true;
                        addSyncLog(`Backend returned ${res.status}. Waiting...`, "#f59e0b");
                    }
                } catch (e) {
                    wasOffline = true;
                    addSyncLog("Backend disconnected. Waiting for recovery...", "#ef4444");
                }
            }, 1000);
        });
    }
    // --- Tasks ---
    const tasksBox = document.createElement('div');
    tasksBox.style.marginTop = '10px';
    tasksBox.innerHTML = `
        <div style="display:flex; gap:8px; align-items:center; margin-bottom:6px;">
            <input id="quick-task-title" class="modern-input" placeholder="Quick task" style="font-size:0.8rem; padding:6px;" />
            <button id="quick-task-add" class="btn" style="width:auto; padding:6px 10px;">+ Task</button>
        </div>
        <div id="task-list" style="max-height:130px; overflow:auto; font-size:0.8rem;"></div>
    `;
    document.querySelector('.sessions-container')?.prepend(tasksBox);

    async function loadTasks() {
        try {
            const res = await apiFetch('/api/tasks');
            if (!res.ok) return;
            const data = await res.json();
            const list = document.getElementById('task-list');
            if (!list) return;
            const tasks = data.tasks || [];
            list.innerHTML = tasks.slice(0, 10).map(t => `<div style="padding:4px 0; border-bottom:1px solid rgba(255,255,255,0.06)">${t.status === 'done' ? '✅' : '📝'} ${t.title}</div>`).join('') || '<div style="color:var(--text-secondary)">No tasks</div>';
        } catch (e) { console.error(e); }
    }

    document.addEventListener('click', async (e) => {
        if (e.target && e.target.id === 'quick-task-add') {
            const input = document.getElementById('quick-task-title');
            const title = input?.value?.trim();
            if (!title) return;
            await apiFetch('/api/tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, session_id: currentSessionId })
            });
            input.value = '';
            loadTasks();
        }
    });

});
