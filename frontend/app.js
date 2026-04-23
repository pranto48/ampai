document.addEventListener('DOMContentLoaded', () => {
    const chatMessages = document.getElementById('chat-messages');
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-btn');
    const chatForm = document.getElementById('chat-form');
    const modelSelect = document.getElementById('model-select');
    const apiKeyInput = document.getElementById('api-key');
    const apiKeyLabel = document.getElementById('api-key-label');
    const newChatBtn = document.getElementById('new-chat-btn');
    const sessionsList = document.getElementById('sessions-list');
    const sessionSearchInput = document.getElementById('session-search');
    const showArchivedToggle = document.getElementById('show-archived-toggle');
    const currentSessionTitle = document.getElementById('current-session-title');
    const currentSessionIdDisplay = document.getElementById('current-session-id');
    const sessionCategorySelect = document.getElementById('session-category');
    const deleteSessionBtn = document.getElementById('delete-session-btn');
    const fullscreenChatBtn = document.getElementById('fullscreen-chat-btn');
    const attachBtn = document.getElementById('attach-btn');
    const fileInput = document.getElementById('file-input');
    const attachmentPreview = document.getElementById('attachment-preview');
    const webSearchToggle = document.getElementById('web-search-toggle');
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.querySelector('.sidebar');
    const sidebarMinimizeBtn = document.getElementById('sidebar-minimize-btn');
    const agentDisplayName = document.getElementById('agent-display-name');
    const tasksViewBtn = document.getElementById('tasks-view-btn');
    const taskQuickAddInput = document.getElementById('task-quick-add-input');
    const taskQuickAddBtn = document.getElementById('task-quick-add-btn');
    const summarizeEmailBtn = document.getElementById('summarize-email-btn');

    let currentSessionId = generateSessionId();
    let currentSessionCategory = "Uncategorized";
    let currentView = 'chat';
    let sessionFilters = { query: '', archived: false };
    let sessionsById = {};
    currentSessionIdDisplay.textContent = currentSessionId;

    let globalConfigs = {};
    let isUserAway = false;

    function toggleFullscreenChat() {
        const container = document.querySelector('.app-container');
        if (!container) return;
        container.classList.toggle('chat-fullscreen');
        localStorage.setItem('chat_fullscreen', container.classList.contains('chat-fullscreen') ? '1' : '0');
    }

    function setSidebarMinimized(minimized) {
        if (!sidebar) return;
        sidebar.classList.toggle('minimized', !!minimized);
        localStorage.setItem('sidebar_minimized', minimized ? '1' : '0');
    }

    async function checkGlobalConfigs() {
        try {
            const res = await fetch('/api/configs/status');
            globalConfigs = await res.json();
            if (globalConfigs.default_model && !sessionStorage.getItem('model_set')) {
                modelSelect.value = globalConfigs.default_model;
                sessionStorage.setItem('model_set', 'true');
            }
            if (agentDisplayName) {
                agentDisplayName.textContent = globalConfigs.chat_agent_name || 'AI Agent';
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

    const initializeApp = async () => {
        const user = await enforceAuth();
        if (!user) return;
        loadSessions();
        checkGlobalConfigs();
    };
    initializeApp();

    if (sidebar) {
        const savedMinimized = localStorage.getItem('sidebar_minimized');
        const shouldAutoMinimize = window.innerWidth < 1200;
        setSidebarMinimized(savedMinimized ? savedMinimized === '1' : shouldAutoMinimize);
    }

    const appContainer = document.querySelector('.app-container');
    if (appContainer && localStorage.getItem('chat_fullscreen') === '1') {
        appContainer.classList.add('chat-fullscreen');
    }

    if (sidebarMinimizeBtn) {
        sidebarMinimizeBtn.addEventListener('click', () => {
            setSidebarMinimized(!sidebar.classList.contains('minimized'));
        });
    }

    if (fullscreenChatBtn) {
        fullscreenChatBtn.addEventListener('click', toggleFullscreenChat);
    }

    window.addEventListener('blur', () => { isUserAway = true; });
    window.addEventListener('focus', () => { isUserAway = false; });
    document.addEventListener('visibilitychange', () => { isUserAway = document.hidden; });

    if (sessionSearchInput) {
        sessionSearchInput.addEventListener('input', () => {
            sessionFilters.query = sessionSearchInput.value.trim();
            loadSessions();
        });
    }

    if (showArchivedToggle) {
        showArchivedToggle.addEventListener('change', () => {
            sessionFilters.archived = showArchivedToggle.checked;
            loadSessions();
        });
    }

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

    if (tasksViewBtn) {
        tasksViewBtn.addEventListener('click', async () => {
            currentView = 'tasks';
            await renderTasksView();
        });
    }

    if (taskQuickAddBtn && taskQuickAddInput) {
        taskQuickAddBtn.addEventListener('click', async () => {
            const title = taskQuickAddInput.value.trim();
            if (!title) return;
            const created = await createTask({ title, session_id: currentSessionId });
            if (created) {
                taskQuickAddInput.value = '';
                if (currentView === 'tasks') await renderTasksView();
            }
        });
    }

    if (summarizeEmailBtn) {
        summarizeEmailBtn.addEventListener('click', async () => {
            appendMessage('ai', 'Generating today’s email summary...');
            summarizeEmailBtn.disabled = true;
            try {
                const response = await fetch('/api/integrations/email/summary-today', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        provider: 'outlook',
                        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
                        session_id: currentSessionId,
                        model_type: modelSelect.value,
                        api_key: apiKeyInput.value || null,
                    }),
                });
                const data = await response.json();
                if (!response.ok) {
                    appendMessage('ai', `Email summary error: ${data.detail || 'Failed to summarize inbox.'}`);
                    return;
                }
                appendMessage('ai', data.summary || 'No summary generated.');
                loadSessions();
            } catch (error) {
                appendMessage('ai', `Email summary failed: ${error.message}`);
            } finally {
                summarizeEmailBtn.disabled = false;
            }
        });
    }

    // Event Listeners
    sessionCategorySelect.addEventListener('change', async (e) => {
        const newCategory = e.target.value;
        currentSessionCategory = newCategory;
        try {
            await fetch(`/api/sessions/${currentSessionId}/category`, {
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
                const response = await fetch(`/api/sessions/${currentSessionId}`, { method: 'DELETE' });
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
                    const response = await fetch(`/api/upload?session_id=${encodeURIComponent(currentSessionId)}`, {
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

    newChatBtn.addEventListener('click', () => {
        currentView = 'chat';
        currentSessionId = generateSessionId();
        currentSessionCategory = "Uncategorized";
        sessionCategorySelect.value = "Uncategorized";
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
        currentView = 'chat';

        if (message.toLowerCase().startsWith('/task ')) {
            const quickTitle = message.substring(6).trim();
            if (quickTitle) {
                const created = await createTask({ title: quickTitle, session_id: currentSessionId });
                if (created) {
                    appendMessage('ai', `✅ Task created: #${created.id} ${created.title}`);
                } else {
                    appendMessage('ai', 'Failed to create task.');
                }
            }
            messageInput.value = '';
            sendBtn.setAttribute('disabled', 'true');
            return;
        }

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
            const response = await fetch('/api/chat', {
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
                appendMessage('ai', data.response, false, data.web_search_status);
                // Refresh sessions list in case this was a new session
                loadSessions();
                if (isUserAway) {
                    if ('Notification' in window) {
                        if (Notification.permission === 'granted') {
                            new Notification('AmpAI Reply Ready', { body: data.response?.slice(0, 120) || 'New AI reply received.' });
                        } else if (Notification.permission !== 'denied') {
                            Notification.requestPermission();
                        }
                    }
                    fetch('/api/notifications/chat-reply', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            session_id: currentSessionId,
                            reply_preview: data.response || '',
                        }),
                    }).catch(() => {});
                }
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

    async function createTask(payload) {
        try {
            const response = await fetch('/api/tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!response.ok) return null;
            const data = await response.json();
            return data.task;
        } catch (error) {
            console.error('Failed to create task', error);
            return null;
        }
    }

    function appendMessage(role, content, isPreFormatted = false, webSearchStatus = null) {
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

        if (role === 'ai' && webSearchStatus) {
            const statusBadge = document.createElement('div');
            statusBadge.style.marginTop = '8px';
            statusBadge.style.display = 'inline-block';
            statusBadge.style.fontSize = '0.75rem';
            statusBadge.style.padding = '3px 8px';
            statusBadge.style.borderRadius = '999px';

            if (webSearchStatus.ok) {
                statusBadge.style.background = 'rgba(16, 185, 129, 0.15)';
                statusBadge.style.border = '1px solid rgba(16, 185, 129, 0.35)';
                statusBadge.style.color = '#10b981';
                statusBadge.textContent = `Web: ${webSearchStatus.provider || 'available'}`;
            } else {
                statusBadge.style.background = 'rgba(239, 68, 68, 0.12)';
                statusBadge.style.border = '1px solid rgba(239, 68, 68, 0.35)';
                statusBadge.style.color = '#ef4444';
                statusBadge.textContent = 'Web unavailable';
                statusBadge.title = webSearchStatus.error || 'Web search failed';
            }

            bubble.appendChild(statusBadge);
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
            const params = new URLSearchParams();
            if (sessionFilters.query) params.set('query', sessionFilters.query);
            params.set('archived', String(sessionFilters.archived));
            const response = await fetch(`/api/sessions?${params.toString()}`);
            const data = await response.json();

            sessionsList.innerHTML = '';
            if (data.sessions && data.sessions.length > 0) {
                data.sessions.sort((a, b) => {
                    if ((b.pinned ? 1 : 0) !== (a.pinned ? 1 : 0)) return (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0);
                    return new Date(b.updated_at || 0) - new Date(a.updated_at || 0);
                });
                sessionsById = {};
                const groups = {};
                data.sessions.forEach(s => {
                    sessionsById[s.session_id] = s;
                    if (!groups[s.category]) groups[s.category] = [];
                    groups[s.category].push(s);
                });

                for (const [category, ids] of Object.entries(groups)) {
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

                    ids.forEach((session) => {
                        const sessionId = session.session_id;
                        const li = document.createElement('li');
                        li.className = 'session-item';
                        li.dataset.sessionId = sessionId;
                        li.style.display = 'flex';
                        li.style.justifyContent = 'space-between';
                        li.style.alignItems = 'center';
                        if (sessionId === currentSessionId) {
                            li.classList.add('active');
                            sessionCategorySelect.value = category; // Update dropdown for active
                        }

                        const label = document.createElement('span');
                        label.textContent = `${session.pinned ? '📌 ' : ''}${sessionId}`;
                        label.style.flex = '1';
                        label.style.overflow = 'hidden';
                        label.style.textOverflow = 'ellipsis';
                        label.style.whiteSpace = 'nowrap';
                        label.onclick = () => {
                            sessionCategorySelect.value = session.category;
                            loadSessionHistory(sessionId);
                        };

                        const controls = document.createElement('span');
                        controls.style.display = 'flex';
                        controls.style.gap = '6px';

                        const pinBtn = document.createElement('button');
                        pinBtn.className = 'btn icon-btn';
                        pinBtn.style.width = 'auto';
                        pinBtn.style.padding = '2px 6px';
                        pinBtn.textContent = session.pinned ? '📌' : '📍';
                        pinBtn.title = session.pinned ? 'Unpin session' : 'Pin session';
                        pinBtn.onclick = async (event) => {
                            event.stopPropagation();
                            await fetch(`/api/sessions/${sessionId}/pin`, {
                                method: 'PATCH',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ value: !session.pinned }),
                            });
                            loadSessions();
                        };

                        const archiveBtn = document.createElement('button');
                        archiveBtn.className = 'btn icon-btn';
                        archiveBtn.style.width = 'auto';
                        archiveBtn.style.padding = '2px 6px';
                        archiveBtn.textContent = session.archived ? '♻️' : '🗄️';
                        archiveBtn.title = session.archived ? 'Unarchive session' : 'Archive session';
                        archiveBtn.onclick = async (event) => {
                            event.stopPropagation();
                            await fetch(`/api/sessions/${sessionId}/archive`, {
                                method: 'PATCH',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ value: !session.archived }),
                            });
                            loadSessions();
                        };

                        controls.appendChild(pinBtn);
                        controls.appendChild(archiveBtn);
                        li.appendChild(label);
                        li.appendChild(controls);
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
        currentView = 'chat';
        currentSessionId = sessionId;
        currentSessionIdDisplay.textContent = sessionId;
        
        // Update UI active state
        document.querySelectorAll('.session-item').forEach(el => {
            if (el.dataset.sessionId === sessionId) el.classList.add('active');
            else el.classList.remove('active');
        });
        if (sessionsById[sessionId]?.category) {
            sessionCategorySelect.value = sessionsById[sessionId].category;
            currentSessionCategory = sessionsById[sessionId].category;
        }

        try {
            chatMessages.innerHTML = '<div style="text-align:center; color:var(--text-secondary); margin-top:20px;">Loading memory...</div>';
            
            const response = await fetch(`/api/history/${sessionId}`);
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

    async function fetchTasks(filters = {}) {
        const query = new URLSearchParams(filters).toString();
        const res = await fetch(`/api/tasks${query ? `?${query}` : ''}`);
        if (!res.ok) return [];
        const data = await res.json();
        return data.tasks || [];
    }

    async function patchTask(taskId, payload) {
        const res = await fetch(`/api/tasks/${taskId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        return res.ok;
    }

    async function removeTask(taskId) {
        const res = await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
        return res.ok;
    }

    async function renderTasksView() {
        const tasks = await fetchTasks();
        const now = new Date();
        const groups = {
            overdue: [],
            active: [],
            complete: [],
        };

        tasks.forEach((task) => {
            const status = (task.status || '').toLowerCase();
            const dueDate = task.due_at ? new Date(task.due_at) : null;
            if (status === 'done' || status === 'completed') groups.complete.push(task);
            else if (dueDate && dueDate < now) groups.overdue.push(task);
            else groups.active.push(task);
        });

        const renderGroup = (title, list) => {
            const items = list.map((task) => {
                const due = task.due_at ? new Date(task.due_at).toLocaleString() : 'No due date';
                return `
                    <div class="message ai-message" style="margin-bottom:8px;">
                        <div class="avatar">T</div>
                        <div class="bubble" style="width:100%;">
                            <div style="display:flex; justify-content:space-between; gap:8px; align-items:center;">
                                <strong>#${task.id} ${task.title}</strong>
                                <span class="badge">${task.priority || 'medium'}</span>
                            </div>
                            <div style="font-size:0.85rem; color:var(--text-secondary); margin:6px 0;">${task.description || ''}</div>
                            <div style="font-size:0.8rem; color:var(--text-secondary); margin-bottom:8px;">Due: ${due} | Status: ${task.status}</div>
                            <div style="display:flex; gap:6px; flex-wrap:wrap;">
                                <button class="btn task-complete-btn" data-task-id="${task.id}" style="width:auto; padding:4px 8px;">Complete</button>
                                <button class="btn task-edit-btn" data-task-id="${task.id}" style="width:auto; padding:4px 8px;">Edit</button>
                                <button class="btn task-delete-btn" data-task-id="${task.id}" style="width:auto; padding:4px 8px; color:#ef4444;">Delete</button>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
            return `<h3 style="margin: 12px 0 8px;">${title} (${list.length})</h3>${items || '<div style="color:var(--text-secondary);">None</div>'}`;
        };

        chatMessages.innerHTML = `
            <div class="message ai-message welcome-message">
                <div class="avatar">AI</div>
                <div class="bubble">
                    <p><strong>Tasks Dashboard</strong> — grouped by overdue, active, and completed.</p>
                </div>
            </div>
            ${renderGroup('Overdue', groups.overdue)}
            ${renderGroup('Active', groups.active)}
            ${renderGroup('Completed', groups.complete)}
        `;

        document.querySelectorAll('.task-complete-btn').forEach((btn) => {
            btn.addEventListener('click', async () => {
                await patchTask(btn.dataset.taskId, { status: 'done' });
                await renderTasksView();
            });
        });
        document.querySelectorAll('.task-delete-btn').forEach((btn) => {
            btn.addEventListener('click', async () => {
                await removeTask(btn.dataset.taskId);
                await renderTasksView();
            });
        });
        document.querySelectorAll('.task-edit-btn').forEach((btn) => {
            btn.addEventListener('click', async () => {
                const newTitle = prompt('New task title:');
                if (!newTitle) return;
                await patchTask(btn.dataset.taskId, { title: newTitle });
                await renderTasksView();
            });
        });
    }

    // --- Update Checker Logic ---
    const updateBanner = document.getElementById('update-banner');
    const syncCodeBtn = document.getElementById('sync-code-btn');
    let initialMtime = null;

    async function checkUpdates() {
        try {
            const response = await fetch('/api/status');
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
                    const res = await fetch('/api/status');
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
});
