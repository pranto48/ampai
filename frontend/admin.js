document.addEventListener('DOMContentLoaded', () => {
    async function ensureAuth() {
        const token = localStorage.getItem('ampai_token') || '';
        if (!token) {
            alert('Please login from chat page first.');
            window.location.href = 'index.html';
            return false;
        }
        const res = await apiFetch('/api/auth/whoami', { headers: { 'Authorization': `Bearer ${token}` } });
        if (!res.ok) {
            alert('Authentication expired.');
            localStorage.removeItem('ampai_token');
            window.location.href = 'index.html';
            return false;
        }
        const who = await res.json();
        if (who.role !== 'admin') {
            alert('Admin token required.');
            window.location.href = 'index.html';
            return false;
        }
        return true;
    }

    async function apiFetch(url, options = {}) {
        const token = localStorage.getItem('ampai_token') || '';
        const headers = options.headers || {};
        headers['Authorization'] = `Bearer ${token}`;
        return fetch(url, { ...options, headers });
    }
    const memoriesTbody = document.getElementById('memories-tbody');
    const importFile = document.getElementById('import-file');
    const importBtn = document.getElementById('import-btn');
    const importStatus = document.getElementById('import-status');

    const logModal = document.getElementById('log-modal');
    const closeModalBtn = document.getElementById('close-modal');
    const modalSessionId = document.getElementById('modal-session-id');
    const modalChatBox = document.getElementById('modal-chat-box');

    const saveConfigsBtn = document.getElementById('save-configs-btn');
    const configStatus = document.getElementById('config-status');
    const configInputs = {
        'ollama_base_url': document.getElementById('config-ollama-url'),
        'generic_base_url': document.getElementById('config-generic-url'),
        'generic_api_key': document.getElementById('config-generic-key'),
        'openai_api_key': document.getElementById('config-openai-key'),
        'gemini_api_key': document.getElementById('config-gemini-key'),
        'anthropic_api_key': document.getElementById('config-anthropic-key'),
        'openrouter_api_key': document.getElementById('config-openrouter-key'),
        'openrouter_model': document.getElementById('config-openrouter-model'),
        'imap_host': document.getElementById('config-imap-host'),
        'imap_username': document.getElementById('config-imap-username'),
        'imap_password': document.getElementById('config-imap-password'),
        'anythingllm_base_url': document.getElementById('config-anythingllm-url'),
        'anythingllm_api_key': document.getElementById('config-anythingllm-key'),
        'anythingllm_workspace': document.getElementById('config-anythingllm-workspace'),
        'default_model': document.getElementById('config-default-model'),
        'web_search_secondary_provider': document.getElementById('config-web-search-secondary-provider'),
        'web_fallback_provider': document.getElementById('config-web-fallback-provider'),
        'serpapi_api_key': document.getElementById('config-serpapi-key'),
        'bing_api_key': document.getElementById('config-bing-key'),
        'custom_web_search_url': document.getElementById('config-custom-web-search-url'),
        'custom_web_search_api_key': document.getElementById('config-custom-web-search-api-key'),
        'integration_email_outlook_credentials': document.getElementById('config-outlook-credentials'),
        'integration_email_gmail_credentials': document.getElementById('config-gmail-credentials'),
        'email_digest_provider': document.getElementById('config-email-digest-provider'),
        'email_digest_hour': document.getElementById('config-email-digest-hour'),
        'email_digest_minute': document.getElementById('config-email-digest-minute'),
        'email_digest_timezone': document.getElementById('config-email-digest-timezone')
    };
    const SECRET_CONFIG_KEYS = new Set([
        'generic_api_key',
        'openai_api_key',
        'gemini_api_key',
        'anthropic_api_key',
        'openrouter_api_key',
        'anythingllm_api_key',
        'serpapi_api_key',
        'bing_api_key',
        'custom_web_search_api_key',
        'integration_email_outlook_credentials',
        'integration_email_gmail_credentials'
    ]);
    const CLEAR_VALUE_SENTINEL = "__CLEAR__";
    const initialConfigValues = {};
    const dirtyConfigKeys = new Set();

    const coreMemoriesContainer = document.getElementById('core-memories-container');
    const refreshHealthBtn = document.getElementById('refresh-health-btn');
    const healthStatusGrid = document.getElementById('health-status-grid');
    const schedulerDiagnostics = document.getElementById('scheduler-diagnostics');
    const healthUpdatedAt = document.getElementById('health-updated-at');
    const emailProviderSelect = document.getElementById('email-provider-select');
    const connectEmailProviderBtn = document.getElementById('connect-email-provider-btn');
    const disconnectEmailProviderBtn = document.getElementById('disconnect-email-provider-btn');
    const emailProviderStatus = document.getElementById('email-provider-status');
    const saveEmailScheduleBtn = document.getElementById('save-email-schedule-btn');
    const emailScheduleStatus = document.getElementById('email-schedule-status');

    ensureAuth().then((ok) => { if (!ok) return; loadAdminSessions(); loadConfigs(); loadCoreMemories(); loadHealth(); });

    async function loadCoreMemories() {
        try {
            const res = await apiFetch('/api/admin/core-memories');
            const data = await res.json();
            coreMemoriesContainer.innerHTML = '';
            
            if (data.core_memories && data.core_memories.length > 0) {
                data.core_memories.forEach(mem => {
                    const pill = document.createElement('div');
                    pill.style.background = 'rgba(16, 185, 129, 0.1)';
                    pill.style.border = '1px solid rgba(16, 185, 129, 0.3)';
                    pill.style.color = 'var(--text-color)';
                    pill.style.padding = '8px 14px';
                    pill.style.borderRadius = '20px';
                    pill.style.fontSize = '0.9rem';
                    pill.style.display = 'flex';
                    pill.style.alignItems = 'center';
                    pill.style.gap = '8px';
                    
                    const factSpan = document.createElement('span');
                    factSpan.textContent = mem.fact;
                    
                    const delBtn = document.createElement('button');
                    delBtn.innerHTML = '&times;';
                    delBtn.style.background = 'transparent';
                    delBtn.style.border = 'none';
                    delBtn.style.color = '#ef4444';
                    delBtn.style.cursor = 'pointer';
                    delBtn.style.fontSize = '1.2rem';
                    delBtn.style.lineHeight = '1';
                    delBtn.onclick = async () => {
                        await apiFetch(`/api/admin/core-memories/${mem.id}`, { method: 'DELETE' });
                        loadCoreMemories();
                    };
                    
                    pill.appendChild(factSpan);
                    pill.appendChild(delBtn);
                    coreMemoriesContainer.appendChild(pill);
                });
            } else {
                coreMemoriesContainer.innerHTML = '<span style="color: var(--text-secondary); font-size: 0.9rem;">No core memories learned yet.</span>';
            }
        } catch (e) {
            console.error("Failed to load core memories", e);
        }
    }

    async function loadConfigs() {
        try {
            const res = await apiFetch('/api/admin/configs');
            const data = await res.json();
            for (const [key, input] of Object.entries(configInputs)) {
                if (data[key]) {
                    input.value = data[key];
                } else {
                    input.value = '';
                }
                initialConfigValues[key] = input.value;
                dirtyConfigKeys.delete(key);
            }
        } catch (e) {
            console.error("Failed to load configs", e);
        }
    }

    saveConfigsBtn.addEventListener('click', async () => {
        configStatus.textContent = "Saving...";
        configStatus.style.color = "var(--text-secondary)";
        
        const payload = {};
        for (const key of dirtyConfigKeys) {
            const input = configInputs[key];
            const value = input.value.trim();
            if (SECRET_CONFIG_KEYS.has(key) && value === '') {
                payload[key] = CLEAR_VALUE_SENTINEL;
            } else {
                payload[key] = value;
            }
        }

        if (Object.keys(payload).length === 0) {
            configStatus.textContent = "No config changes to save.";
            configStatus.style.color = "var(--text-secondary)";
            return;
        }

        try {
            const res = await apiFetch('/api/admin/configs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ configs: payload })
            });

            if (res.ok) {
                await fetch('/api/admin/configs/migrate', { method: 'POST' });
                await loadConfigs();
                configStatus.textContent = "Saved successfully!";
                configStatus.style.color = "#10b981";
                setTimeout(() => configStatus.textContent = "", 3000);
            } else {
                throw new Error("Failed to save");
            }
        } catch (e) {
            configStatus.textContent = "Error saving: " + e.message;
            configStatus.style.color = "#ef4444";
        }
    });

    async function loadAdminSessions() {
        try {
            const response = await apiFetch('/api/sessions');
            const data = await response.json();
            
            memoriesTbody.innerHTML = '';
            
            if (data.sessions && data.sessions.length > 0) {
                data.sessions.forEach(session => {
                    const tr = document.createElement('tr');
                    
                    const tdId = document.createElement('td');
                    tdId.textContent = session.session_id;
                    
                    const tdCat = document.createElement('td');
                    const badge = document.createElement('span');
                    badge.className = 'badge';
                    badge.textContent = session.category;
                    tdCat.appendChild(badge);
                    
                    const tdActions = document.createElement('td');
                    const exportBtn = document.createElement('button');
                    exportBtn.className = 'btn';
                    exportBtn.style.padding = '6px 12px';
                    exportBtn.style.fontSize = '0.8rem';
                    exportBtn.style.background = 'var(--accent-color)';
                    exportBtn.style.color = 'white';
                    exportBtn.textContent = 'Export JSON';
                    exportBtn.onclick = () => exportMemory(session.session_id);
                    
                    const viewBtn = document.createElement('button');
                    viewBtn.className = 'btn';
                    viewBtn.style.padding = '6px 12px';
                    viewBtn.style.fontSize = '0.8rem';
                    viewBtn.style.background = 'transparent';
                    viewBtn.style.border = '1px solid var(--border-color)';
                    viewBtn.style.color = 'var(--text-color)';
                    viewBtn.style.marginRight = '8px';
                    viewBtn.textContent = 'View Log';
                    viewBtn.onclick = () => window.viewMemory(session.session_id);
                    
                    tdActions.appendChild(viewBtn);
                    tdActions.appendChild(exportBtn);
                    
                    tr.appendChild(tdId);
                    tr.appendChild(tdCat);
                    tr.appendChild(tdActions);
                    memoriesTbody.appendChild(tr);
                });
            } else {
                memoriesTbody.innerHTML = '<tr><td colspan="3" style="text-align: center;">No memories found</td></tr>';
            }
        } catch (error) {
            console.error('Failed to load admin sessions', error);
        }
    }

    async function exportMemory(sessionId) {
        try {
            const response = await apiFetch(`/api/export/${sessionId}`);
            const data = await response.json();
            
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(data, null, 2));
            const downloadAnchorNode = document.createElement('a');
            downloadAnchorNode.setAttribute("href",     dataStr);
            downloadAnchorNode.setAttribute("download", `ampai_memory_${sessionId}.json`);
            document.body.appendChild(downloadAnchorNode); // required for firefox
            downloadAnchorNode.click();
            downloadAnchorNode.remove();
        } catch (error) {
            alert('Failed to export memory: ' + error.message);
        }
    };

    window.viewMemory = async function(sessionId) {
        modalSessionId.textContent = sessionId;
        modalChatBox.innerHTML = '<div style="color: var(--text-secondary); text-align: center;">Loading...</div>';
        logModal.classList.add('show');

        try {
            const res = await apiFetch(`/api/history/${sessionId}`);
            const data = await res.json();
            
            modalChatBox.innerHTML = ''; // clear loading

            if (data.messages && data.messages.length > 0) {
                data.messages.forEach(msg => {
                    const bubble = document.createElement('div');
                    bubble.style.padding = '12px 16px';
                    bubble.style.borderRadius = '8px';
                    bubble.style.maxWidth = '85%';
                    bubble.style.wordWrap = 'break-word';
                    bubble.style.whiteSpace = 'pre-wrap';
                    bubble.style.fontFamily = 'monospace';
                    
                    if (msg.type === 'human') {
                        bubble.style.backgroundColor = 'rgba(255,255,255,0.1)';
                        bubble.style.color = '#fff';
                        bubble.style.alignSelf = 'flex-end';
                        bubble.textContent = `User: ${msg.content}`;
                    } else {
                        bubble.style.backgroundColor = 'rgba(16, 185, 129, 0.1)';
                        bubble.style.color = 'var(--accent-color)';
                        bubble.style.border = '1px solid rgba(16, 185, 129, 0.2)';
                        bubble.style.alignSelf = 'flex-start';
                        bubble.textContent = `AI: ${msg.content}`;
                    }
                    modalChatBox.appendChild(bubble);
                });
            } else {
                modalChatBox.innerHTML = '<div style="color: var(--text-secondary); text-align: center;">No messages found in this session.</div>';
            }
        } catch (e) {
            modalChatBox.innerHTML = `<div style="color: #ef4444; text-align: center;">Error loading history: ${e.message}</div>`;
        }
    };


    async function loadHealth() {
        try {
            const res = await apiFetch('/api/health');
            if (!res.ok) return;
            const data = await res.json();
            const el = document.createElement('div');
            el.className = 'card';
            el.innerHTML = `<h2>Diagnostics</h2><pre style="white-space:pre-wrap;">${JSON.stringify(data, null, 2)}</pre>`;
            document.querySelector('.admin-container')?.appendChild(el);
        } catch (e) { console.error(e); }
    }

    closeModalBtn.addEventListener('click', () => {
        logModal.classList.remove('show');
    });

    window.addEventListener('click', (event) => {
        if (event.target === logModal) {
            logModal.classList.remove('show');
        }
    });

    importBtn.addEventListener('click', () => {
        const file = importFile.files[0];
        if (!file) {
            importStatus.textContent = "Please select a file first.";
            importStatus.style.color = "#ef4444";
            return;
        }

        const reader = new FileReader();
        reader.onload = async (e) => {
            try {
                const json = JSON.parse(e.target.result);
                if (!json.session_id || !json.messages) {
                    throw new Error("Invalid format");
                }
                
                // Allow importing with a new ID to avoid collisions, or keep the old one
                const newId = json.session_id + "_imported_" + Math.random().toString(36).substring(2, 5);
                json.session_id = newId;

                importStatus.textContent = "Importing...";
                importStatus.style.color = "var(--text-secondary)";

                const response = await apiFetch('/api/import', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: json.session_id,
                        category: json.category || 'Imported',
                        messages: json.messages
                    })
                });

                if (response.ok) {
                    importStatus.textContent = "Successfully imported! You can now use this memory in the chat.";
                    importStatus.style.color = "#10b981";
                    loadAdminSessions();
                } else {
                    const err = await response.json();
                    throw new Error(err.detail || "Server error");
                }

            } catch (err) {
                importStatus.textContent = "Error importing file: " + err.message;
                importStatus.style.color = "#ef4444";
            }
        };
        reader.readAsText(file);
    });
});
