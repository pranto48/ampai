document.addEventListener('DOMContentLoaded', () => {
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
        'anythingllm_base_url': document.getElementById('config-anythingllm-url'),
        'anythingllm_api_key': document.getElementById('config-anythingllm-key'),
        'anythingllm_workspace': document.getElementById('config-anythingllm-workspace'),
        'default_model': document.getElementById('config-default-model'),
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
    const adminCurrentPasswordInput = document.getElementById('admin-current-password');
    const adminNewPasswordInput = document.getElementById('admin-new-password');
    const adminChangePasswordBtn = document.getElementById('admin-change-password-btn');
    const adminPasswordStatus = document.getElementById('admin-password-status');

    const initializeAdmin = async () => {
        const user = await enforceAuth({ requiredRole: 'admin' });
        if (!user) return;
        loadAdminSessions();
        loadConfigs();
        loadCoreMemories();
        loadSystemHealth();
        setupConfigChangeTracking();
        setupClearKeyButtons();
        refreshHealthBtn.addEventListener('click', loadSystemHealth);
    };
    initializeAdmin();

    function renderHealthTile(name, ok, details) {
        const tile = document.createElement('div');
        tile.style.background = ok ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)';
        tile.style.border = ok ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(239, 68, 68, 0.35)';
        tile.style.borderRadius = '8px';
        tile.style.padding = '10px';
        tile.innerHTML = `
            <div style="font-weight: 600; margin-bottom: 6px;">${name}</div>
            <div style="font-size: 0.85rem; color: ${ok ? '#10b981' : '#ef4444'};">${ok ? 'Healthy' : 'Unhealthy'}</div>
            ${details ? `<div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px;">${details}</div>` : ''}
        `;
        return tile;
    }

    async function loadSystemHealth() {
        healthUpdatedAt.textContent = 'Loading health...';
        try {
            const response = await fetch('/api/health');
            const data = await response.json();
            const checks = data.checks || {};
            healthStatusGrid.innerHTML = '';
            healthStatusGrid.appendChild(renderHealthTile('Database', !!checks.db?.ok, checks.db?.details || ''));
            healthStatusGrid.appendChild(renderHealthTile('Redis', !!checks.redis?.ok, checks.redis?.details || ''));
            healthStatusGrid.appendChild(renderHealthTile('Model Provider', !!checks.model_provider?.ok, checks.model_provider?.provider || checks.model_provider?.details || ''));
            healthStatusGrid.appendChild(renderHealthTile('Search Provider', !!checks.search_provider?.ok, checks.search_provider?.provider || checks.search_provider?.details || ''));
            const lastRun = checks.scheduler?.last_run || {};
            schedulerDiagnostics.textContent = `Scheduler running: ${checks.scheduler?.running ? 'yes' : 'no'}\nLast network sweep: ${lastRun.network_sweep || 'N/A'}\nLast task reminders: ${lastRun.task_reminders || 'N/A'}\nJobs: ${(checks.scheduler?.jobs || []).join(', ') || 'none'}`;
            healthUpdatedAt.textContent = `Updated at ${new Date().toLocaleString()}`;
        } catch (error) {
            healthStatusGrid.innerHTML = '';
            healthStatusGrid.appendChild(renderHealthTile('System Health', false, error.message));
            schedulerDiagnostics.textContent = 'Unable to load scheduler diagnostics.';
            healthUpdatedAt.textContent = 'Health check failed';
        }
    }

    function setupConfigChangeTracking() {
        for (const [key, input] of Object.entries(configInputs)) {
            input.addEventListener('input', () => {
                if (input.value !== (initialConfigValues[key] ?? '')) {
                    dirtyConfigKeys.add(key);
                } else {
                    dirtyConfigKeys.delete(key);
                }
            });
        }
    }

    function setupClearKeyButtons() {
        for (const [key, input] of Object.entries(configInputs)) {
            if (!SECRET_CONFIG_KEYS.has(key)) continue;

            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn';
            btn.textContent = 'Clear';
            btn.style.marginTop = '6px';
            btn.style.padding = '4px 10px';
            btn.style.fontSize = '0.8rem';
            btn.onclick = () => {
                input.value = '';
                dirtyConfigKeys.add(key);
                configStatus.textContent = `Marked ${key} for clearing. Click Save Configs to apply.`;
                configStatus.style.color = "var(--text-secondary)";
            };
            input.insertAdjacentElement('afterend', btn);
        }
    }

    async function loadCoreMemories() {
        try {
            const res = await fetch('/api/admin/core-memories');
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
                        await fetch(`/api/admin/core-memories/${mem.id}`, { method: 'DELETE' });
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
            const res = await fetch('/api/admin/configs');
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
            const res = await fetch('/api/admin/configs', {
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
            const response = await fetch('/api/sessions');
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
            const response = await fetch(`/api/export/${sessionId}`);
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
            const res = await fetch(`/api/history/${sessionId}`);
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

                const response = await fetch('/api/import', {
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

    if (adminChangePasswordBtn) {
        adminChangePasswordBtn.addEventListener('click', async () => {
            const currentPassword = adminCurrentPasswordInput.value;
            const newPassword = adminNewPasswordInput.value;
            adminPasswordStatus.textContent = '';

            if (!currentPassword || !newPassword) {
                adminPasswordStatus.textContent = 'Enter current and new password.';
                adminPasswordStatus.style.color = '#ef4444';
                return;
            }

            try {
                const response = await fetch('/api/admin/change-password', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        current_password: currentPassword,
                        new_password: newPassword,
                    }),
                });
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.detail || 'Failed to change password');
                }
                adminCurrentPasswordInput.value = '';
                adminNewPasswordInput.value = '';
                adminPasswordStatus.textContent = 'Password updated.';
                adminPasswordStatus.style.color = '#10b981';
            } catch (error) {
                adminPasswordStatus.textContent = error.message;
                adminPasswordStatus.style.color = '#ef4444';
            }
        });
    }
});
