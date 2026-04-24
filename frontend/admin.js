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
        'openrouter_model_list': document.getElementById('config-openrouter-model-list'),
        'imap_host': document.getElementById('config-imap-host'),
        'imap_username': document.getElementById('config-imap-username'),
        'imap_password': document.getElementById('config-imap-password'),
        'anythingllm_base_url': document.getElementById('config-anythingllm-url'),
        'anythingllm_api_key': document.getElementById('config-anythingllm-key'),
        'anythingllm_workspace': document.getElementById('config-anythingllm-workspace'),
        'anythingllm_workspace_list': document.getElementById('config-anythingllm-workspace-list'),
        'ollama_model_list': document.getElementById('config-ollama-model-list'),
        'generic_model_list': document.getElementById('config-generic-model-list'),
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
        'email_digest_timezone': document.getElementById('config-email-digest-timezone'),
        'chat_agent_name': document.getElementById('config-chat-agent-name'),
        'chat_agent_avatar_url': document.getElementById('config-chat-agent-avatar-url'),
        'backup_mode': document.getElementById('config-backup-mode'),
        'backup_local_path': document.getElementById('config-backup-local-path'),
        'backup_ftp_host': document.getElementById('config-backup-ftp-host'),
        'backup_ftp_user': document.getElementById('config-backup-ftp-user'),
        'backup_ftp_password': document.getElementById('config-backup-ftp-password'),
        'backup_ftp_path': document.getElementById('config-backup-ftp-path'),
        'backup_smb_host': document.getElementById('config-backup-smb-host'),
        'backup_smb_share': document.getElementById('config-backup-smb-share'),
        'backup_smb_path': document.getElementById('config-backup-smb-path'),
        'backup_smb_user': document.getElementById('config-backup-smb-user'),
        'backup_smb_password': document.getElementById('config-backup-smb-password'),
        'backup_smb_domain': document.getElementById('config-backup-smb-domain'),
        'backup_schedule_enabled': document.getElementById('config-backup-schedule-enabled'),
        'backup_schedule_hour': document.getElementById('config-backup-schedule-hour'),
        'backup_schedule_minute': document.getElementById('config-backup-schedule-minute'),
        'backup_schedule_cron': document.getElementById('config-backup-schedule-cron'),
        'resend_api_key': document.getElementById('config-resend-api-key'),
        'resend_from_email': document.getElementById('config-resend-from-email'),
        'notification_email_to': document.getElementById('config-notification-email-to'),
        'chat_reply_email_notifications': document.getElementById('config-chat-reply-email-notifications'),
        'notification_default_browser_notify_on_away_replies': document.getElementById('config-notification-default-browser-notify-on-away-replies'),
        'notification_default_email_notify_on_away_replies': document.getElementById('config-notification-default-email-notify-on-away-replies'),
        'notification_default_minimum_notify_interval_seconds': document.getElementById('config-notification-default-minimum-notify-interval-seconds'),
        'notification_default_digest_mode': document.getElementById('config-notification-default-digest-mode'),
        'notification_default_digest_interval_minutes': document.getElementById('config-notification-default-digest-interval-minutes'),
        'pii_redaction_enabled': document.getElementById('config-pii-redaction-enabled'),
        'retention_max_age_days': document.getElementById('config-retention-max-age-days')
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
        'integration_email_gmail_credentials',
        'backup_ftp_password',
        'backup_smb_password',
        'resend_api_key'
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
    const usersTbody = document.getElementById('users-tbody');
    const newUserUsername = document.getElementById('new-user-username');
    const newUserPassword = document.getElementById('new-user-password');
    const newUserRole = document.getElementById('new-user-role');
    const createUserBtn = document.getElementById('create-user-btn');
    const userStatus = document.getElementById('user-status');
    const mediaTbody = document.getElementById('media-tbody');
    const runBackupBtn = document.getElementById('run-backup-btn');
    const backupStatus = document.getElementById('backup-status');
    const backupHistoryTbody = document.getElementById('backup-history-tbody');
    const testFtpConnectionBtn = document.getElementById('test-ftp-connection-btn');
    const testSmbConnectionBtn = document.getElementById('test-smb-connection-btn');
    const backupRestoreBtn = document.getElementById('backup-restore-btn');
    const backupRestoreJson = document.getElementById('backup-restore-json');
    const backupRestoreDryRun = document.getElementById('backup-restore-dry-run');
    const runRetentionBtn = document.getElementById('run-retention-btn');
    const retentionStatus = document.getElementById('retention-status');
    const groupNameInput = document.getElementById('group-name');
    const groupMembersInput = document.getElementById('group-members');
    const groupSelector = document.getElementById('group-selector');
    const groupSessionSelector = document.getElementById('group-session-selector');
    const createGroupBtn = document.getElementById('create-group-btn');
    const shareGroupSessionBtn = document.getElementById('share-group-session-btn');
    const groupsList = document.getElementById('groups-list');
    const groupStatus = document.getElementById('group-status');
    const groupMembersList = document.getElementById('group-members-list');
    const groupSharedSessionsList = document.getElementById('group-shared-sessions-list');
    let selectedGroupId = null;

    const initializeAdmin = async () => {
        const user = await enforceAuth({ requiredRole: 'admin' });
        if (!user) return;
        loadAdminSessions();
        loadConfigs();
        loadCoreMemories();
        loadSystemHealth();
        loadUsers();
        loadMediaAssets();
        loadGroups();
        setupConfigChangeTracking();
        setupClearKeyButtons();
        refreshHealthBtn.addEventListener('click', loadSystemHealth);
        if (runBackupBtn) {
            runBackupBtn.addEventListener('click', runBackupNow);
        }
        if (testFtpConnectionBtn) {
            testFtpConnectionBtn.addEventListener('click', () => testBackupConnection('ftp'));
        }
        if (testSmbConnectionBtn) {
            testSmbConnectionBtn.addEventListener('click', () => testBackupConnection('smb'));
        }
        if (backupRestoreBtn) {
            backupRestoreBtn.addEventListener('click', restoreBackup);
        }
        if (runRetentionBtn) {
            runRetentionBtn.addEventListener('click', runRetentionNow);
        }
        loadBackupHistory();
        if (createGroupBtn) {
            createGroupBtn.addEventListener('click', createGroup);
        }
        if (shareGroupSessionBtn) {
            shareGroupSessionBtn.addEventListener('click', shareSessionToGroup);
        }
        if (groupSelector) {
            groupSelector.addEventListener('change', async () => {
                selectedGroupId = Number(groupSelector.value) || null;
                await loadGroupDetails();
            });
        }
        loadSessionOptions();
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

    async function runRetentionNow() {
        if (!runRetentionBtn) return;
        runRetentionBtn.disabled = true;
        retentionStatus.textContent = 'Running...';
        try {
            const maxAge = Number(document.getElementById('config-retention-max-age-days')?.value || 365);
            const res = await apiFetch('/api/admin/retention/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ max_age_days: maxAge, archive_only: true }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Retention run failed');
            retentionStatus.textContent = `Archived: ${data.archived || 0}, Deleted: ${data.deleted || 0}`;
            retentionStatus.style.color = '#10b981';
        } catch (error) {
            retentionStatus.textContent = error.message;
            retentionStatus.style.color = '#ef4444';
        } finally {
            runRetentionBtn.disabled = false;
        }
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
                const currentValue = input.type === 'checkbox' ? String(!!input.checked) : input.value;
                if (currentValue !== (initialConfigValues[key] ?? '')) {
                    dirtyConfigKeys.add(key);
                } else {
                    dirtyConfigKeys.delete(key);
                }
            });
            if (input.type === 'checkbox') {
                input.addEventListener('change', () => input.dispatchEvent(new Event('input')));
            }
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
                if (input.type === 'checkbox') {
                    const checked = String(data[key] || '').toLowerCase() === 'true';
                    input.checked = checked;
                    initialConfigValues[key] = String(checked);
                } else {
                    if (data[key]) {
                        input.value = data[key];
                    } else {
                        input.value = '';
                    }
                    initialConfigValues[key] = input.value;
                }
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
            const value = input.type === 'checkbox' ? String(!!input.checked) : input.value.trim();
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


    async function loadUsers() {
        if (!usersTbody) return;
        try {
            const res = await apiFetch('/api/admin/users');
            const data = await res.json();
            const users = data.users || [];
            usersTbody.innerHTML = users.map(u => `
                <tr>
                    <td>${u.id}</td>
                    <td>${u.username}</td>
                    <td>
                        <select data-role-user-id="${u.id}" class="modern-input" style="padding:4px 8px; font-size:0.8rem; width:100px;">
                            <option value="user" ${u.role === 'user' ? 'selected' : ''}>user</option>
                            <option value="admin" ${u.role === 'admin' ? 'selected' : ''}>admin</option>
                        </select>
                    </td>
                    <td><button data-del-user-id="${u.id}" class="btn" style="width:auto; padding:6px 10px;">Delete</button></td>
                </tr>
            `).join('') || '<tr><td colspan="4" style="text-align:center;">No users</td></tr>';
        } catch (e) {
            console.error('Failed to load users', e);
        }
    }

    if (createUserBtn) {
        createUserBtn.addEventListener('click', async () => {
            const username = document.getElementById('new-username')?.value?.trim();
            const password = document.getElementById('new-password')?.value || '';
            const role = document.getElementById('new-role')?.value || 'user';
            if (!username || !password) return alert('Username and password required');
            const res = await apiFetch('/api/admin/users', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password, role })
            });
            const data = await res.json();
            if (!res.ok) return alert(data.detail || 'Create failed');
            document.getElementById('new-username').value = '';
            document.getElementById('new-password').value = '';
            loadUsers();
        });
    }

    document.addEventListener('change', async (e) => {
        const userId = e.target?.getAttribute?.('data-role-user-id');
        if (!userId) return;
        await apiFetch(`/api/admin/users/${userId}/role`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role: e.target.value })
        });
        loadUsers();
    });

    document.addEventListener('click', async (e) => {
        const userId = e.target?.getAttribute?.('data-del-user-id');
        if (!userId) return;
        if (!confirm('Delete this user?')) return;
        await apiFetch(`/api/admin/users/${userId}`, { method: 'DELETE' });
        loadUsers();
    });

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

    async function loadUsers() {
        try {
            const response = await fetch('/api/admin/users');
            const data = await response.json();
            usersTbody.innerHTML = '';
            const users = data.users || [];
            if (!users.length) {
                usersTbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">No users</td></tr>';
                return;
            }

            users.forEach((user) => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${user.username}</td>
                    <td>
                        <select class="modern-input user-role-select" data-username="${user.username}" style="max-width:120px;">
                            <option value="user" ${user.role === 'user' ? 'selected' : ''}>user</option>
                            <option value="admin" ${user.role === 'admin' ? 'selected' : ''}>admin</option>
                        </select>
                    </td>
                    <td><input type="password" class="modern-input user-password-input" data-username="${user.username}" placeholder="New password" style="max-width:200px;"></td>
                    <td>
                        <button class="btn user-save-btn" data-username="${user.username}" style="width:auto; padding:6px 10px;">Save</button>
                        <button class="btn user-delete-btn" data-username="${user.username}" style="width:auto; padding:6px 10px; background:rgba(239,68,68,0.15); color:#ef4444; border:1px solid rgba(239,68,68,0.35);">Delete</button>
                    </td>
                `;
                usersTbody.appendChild(tr);
            });

            usersTbody.querySelectorAll('.user-save-btn').forEach((btn) => {
                btn.addEventListener('click', async () => {
                    const username = btn.dataset.username;
                    const roleSelect = usersTbody.querySelector(`.user-role-select[data-username="${username}"]`);
                    const passwordInput = usersTbody.querySelector(`.user-password-input[data-username="${username}"]`);
                    const payload = { role: roleSelect.value };
                    if (passwordInput.value.trim()) payload.password = passwordInput.value.trim();
                    await updateUser(username, payload);
                });
            });

            usersTbody.querySelectorAll('.user-delete-btn').forEach((btn) => {
                btn.addEventListener('click', async () => {
                    const username = btn.dataset.username;
                    if (!confirm(`Delete user "${username}"?`)) return;
                    await deleteUser(username);
                });
            });
        } catch (error) {
            userStatus.textContent = `Failed to load users: ${error.message}`;
            userStatus.style.color = '#ef4444';
        }
    }

    async function createUser() {
        const username = newUserUsername.value.trim();
        const password = newUserPassword.value;
        const role = newUserRole.value;
        if (!username || !password) {
            userStatus.textContent = 'Username and password are required.';
            userStatus.style.color = '#ef4444';
            return;
        }
        try {
            const response = await fetch('/api/admin/users', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password, role }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Failed to create user');
            newUserUsername.value = '';
            newUserPassword.value = '';
            newUserRole.value = 'user';
            userStatus.textContent = 'User created.';
            userStatus.style.color = '#10b981';
            loadUsers();
        } catch (error) {
            userStatus.textContent = error.message;
            userStatus.style.color = '#ef4444';
        }
    }

    async function updateUser(username, payload) {
        try {
            const response = await fetch(`/api/admin/users/${encodeURIComponent(username)}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Failed to update user');
            userStatus.textContent = `Updated ${username}.`;
            userStatus.style.color = '#10b981';
            loadUsers();
        } catch (error) {
            userStatus.textContent = error.message;
            userStatus.style.color = '#ef4444';
        }
    }

    async function deleteUser(username) {
        try {
            const response = await fetch(`/api/admin/users/${encodeURIComponent(username)}`, {
                method: 'DELETE',
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Failed to delete user');
            userStatus.textContent = `Deleted ${username}.`;
            userStatus.style.color = '#10b981';
            loadUsers();
        } catch (error) {
            userStatus.textContent = error.message;
            userStatus.style.color = '#ef4444';
        }
    }

    if (createUserBtn) {
        createUserBtn.addEventListener('click', createUser);
    }

    async function runBackupNow() {
        backupStatus.textContent = 'Running backup...';
        backupStatus.style.color = 'var(--text-secondary)';
        try {
            const response = await fetch('/api/admin/backup/run', { method: 'POST' });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Backup failed');
            backupStatus.textContent = data.path || data.file || 'Backup completed';
            backupStatus.style.color = '#10b981';
            loadBackupHistory();
        } catch (error) {
            backupStatus.textContent = error.message;
            backupStatus.style.color = '#ef4444';
        }
    }

    async function loadBackupHistory() {
        if (!backupHistoryTbody) return;
        try {
            const response = await apiFetch('/api/admin/backup/status-history');
            const data = await response.json();
            const history = data.history || [];
            backupHistoryTbody.innerHTML = history.map((row) => `
                <tr>
                    <td>${row.timestamp || ''}</td>
                    <td>${row.trigger || ''}</td>
                    <td>${row.status || ''}</td>
                    <td>${row.mode || ''}</td>
                    <td>${row.error || row.target || ''}</td>
                </tr>
            `).join('') || '<tr><td colspan="5" style="text-align:center;">No backup runs yet</td></tr>';
        } catch (error) {
            backupHistoryTbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:#ef4444;">${error.message}</td></tr>`;
        }
    }

    async function testBackupConnection(mode) {
        backupStatus.textContent = `Testing ${mode.toUpperCase()} connection...`;
        backupStatus.style.color = 'var(--text-secondary)';
        const payload = mode === 'ftp'
            ? {
                mode: 'ftp',
                host: configInputs.backup_ftp_host.value.trim(),
                user: configInputs.backup_ftp_user.value.trim(),
                password: configInputs.backup_ftp_password.value,
                path: configInputs.backup_ftp_path.value.trim() || '/',
            }
            : {
                mode: 'smb',
                host: configInputs.backup_smb_host.value.trim(),
                share: configInputs.backup_smb_share.value.trim(),
                path: configInputs.backup_smb_path.value.trim() || '/',
                user: configInputs.backup_smb_user.value.trim(),
                password: configInputs.backup_smb_password.value,
                domain: configInputs.backup_smb_domain.value.trim(),
            };
        try {
            const response = await apiFetch('/api/admin/backup/test-connection', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Connection test failed');
            backupStatus.textContent = data.detail || 'Connection successful';
            backupStatus.style.color = '#10b981';
        } catch (error) {
            backupStatus.textContent = error.message;
            backupStatus.style.color = '#ef4444';
        }
    }

    async function restoreBackup() {
        const backupJson = backupRestoreJson?.value || '';
        if (!backupJson.trim()) {
            backupStatus.textContent = 'Paste backup JSON first.';
            backupStatus.style.color = '#ef4444';
            return;
        }
        backupStatus.textContent = 'Validating restore payload...';
        backupStatus.style.color = 'var(--text-secondary)';
        try {
            const response = await apiFetch('/api/admin/backup/restore', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    backup_json: backupJson,
                    dry_run: !!backupRestoreDryRun?.checked,
                }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Restore failed');
            const s = data.summary || {};
            backupStatus.textContent = `Restore ${data.dry_run ? 'dry-run' : 'completed'}: sessions=${s.session_count || 0}, messages=${s.message_count || 0}, invalid=${s.invalid_sessions || 0}`;
            backupStatus.style.color = '#10b981';
            loadBackupHistory();
        } catch (error) {
            backupStatus.textContent = error.message;
            backupStatus.style.color = '#ef4444';
        }
    }

    async function loadGroups() {
        try {
            const response = await fetch('/api/memory-groups');
            const data = await response.json();
            const groups = data.groups || [];
            groupsList.innerHTML = '';
            if (groupSelector) {
                groupSelector.innerHTML = '';
            }
            if (groups.length && !selectedGroupId) {
                selectedGroupId = groups[0].id;
            }
            groups.forEach((g) => {
                const li = document.createElement('li');
                li.textContent = `#${g.id} ${g.name} (${g.created_by})`;
                groupsList.appendChild(li);
                if (groupSelector) {
                    const option = document.createElement('option');
                    option.value = String(g.id);
                    option.textContent = `#${g.id} ${g.name}`;
                    groupSelector.appendChild(option);
                }
            });
            if (groupSelector && groups.length) {
                groupSelector.value = String(selectedGroupId || groups[0].id);
                selectedGroupId = Number(groupSelector.value);
            }
            if (groupSelector && !groups.length) {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = 'No groups available';
                groupSelector.appendChild(option);
                selectedGroupId = null;
            }
            await loadGroupDetails();
        } catch (error) {
            groupStatus.textContent = error.message;
            groupStatus.style.color = '#ef4444';
        }
    }

    async function createGroup() {
        const name = groupNameInput.value.trim();
        const members = groupMembersInput.value.split(',').map(s => s.trim()).filter(Boolean);
        if (!name) {
            groupStatus.textContent = 'Group name is required';
            groupStatus.style.color = '#ef4444';
            return;
        }
        try {
            const response = await fetch('/api/admin/memory-groups', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, members, description: '' }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Failed to create group');
            selectedGroupId = data.group_id;
            groupStatus.textContent = `Created group #${selectedGroupId}`;
            groupStatus.style.color = '#10b981';
            loadGroups();
        } catch (error) {
            groupStatus.textContent = error.message;
            groupStatus.style.color = '#ef4444';
        }
    }

    async function shareSessionToGroup() {
        const sessionId = groupSessionSelector?.value?.trim();
        if (!selectedGroupId || !sessionId) {
            groupStatus.textContent = 'Select a group and a session';
            groupStatus.style.color = '#ef4444';
            return;
        }
        try {
            const response = await fetch(`/api/admin/memory-groups/${selectedGroupId}/share`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Failed to share session');
            groupStatus.textContent = `Shared ${sessionId} to group #${selectedGroupId}`;
            groupStatus.style.color = '#10b981';
            await loadGroupDetails();
        } catch (error) {
            groupStatus.textContent = error.message;
            groupStatus.style.color = '#ef4444';
        }
    }

    async function loadSessionOptions() {
        if (!groupSessionSelector) return;
        try {
            const response = await fetch('/api/sessions');
            const data = await response.json();
            const sessions = data.sessions || [];
            groupSessionSelector.innerHTML = '';
            if (!sessions.length) {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = 'No sessions available';
                groupSessionSelector.appendChild(option);
                return;
            }
            sessions.forEach((s) => {
                const option = document.createElement('option');
                option.value = s.session_id;
                option.textContent = s.session_id;
                groupSessionSelector.appendChild(option);
            });
        } catch (error) {
            groupStatus.textContent = error.message;
            groupStatus.style.color = '#ef4444';
        }
    }

    async function loadGroupDetails() {
        if (!selectedGroupId) {
            if (groupMembersList) groupMembersList.innerHTML = '<li>No group selected</li>';
            if (groupSharedSessionsList) groupSharedSessionsList.innerHTML = '<li>No group selected</li>';
            return;
        }
        try {
            const [membersRes, sessionsRes] = await Promise.all([
                fetch(`/api/admin/memory-groups/${selectedGroupId}/members`),
                fetch(`/api/admin/memory-groups/${selectedGroupId}/sessions`),
            ]);
            const membersData = await membersRes.json();
            const sessionsData = await sessionsRes.json();
            if (!membersRes.ok) throw new Error(membersData.detail || 'Failed to load group members');
            if (!sessionsRes.ok) throw new Error(sessionsData.detail || 'Failed to load group sessions');

            renderGroupMembers(membersData.members || []);
            renderGroupSessions(sessionsData.sessions || []);
        } catch (error) {
            groupStatus.textContent = error.message;
            groupStatus.style.color = '#ef4444';
        }
    }

    function renderGroupMembers(members) {
        if (!groupMembersList) return;
        groupMembersList.innerHTML = '';
        if (!members.length) {
            groupMembersList.innerHTML = '<li>No members</li>';
            return;
        }
        members.forEach((username) => {
            const li = document.createElement('li');
            const button = document.createElement('button');
            button.className = 'btn';
            button.style.width = 'auto';
            button.style.marginLeft = '8px';
            button.textContent = 'Remove';
            button.onclick = () => removeMember(username);
            li.textContent = username;
            li.appendChild(button);
            groupMembersList.appendChild(li);
        });
    }

    function renderGroupSessions(sessions) {
        if (!groupSharedSessionsList) return;
        groupSharedSessionsList.innerHTML = '';
        if (!sessions.length) {
            groupSharedSessionsList.innerHTML = '<li>No shared sessions</li>';
            return;
        }
        sessions.forEach((sessionId) => {
            const li = document.createElement('li');
            const button = document.createElement('button');
            button.className = 'btn';
            button.style.width = 'auto';
            button.style.marginLeft = '8px';
            button.textContent = 'Unshare';
            button.onclick = () => unshareSession(sessionId);
            li.textContent = sessionId;
            li.appendChild(button);
            groupSharedSessionsList.appendChild(li);
        });
    }

    async function removeMember(username) {
        if (!selectedGroupId) return;
        try {
            const response = await fetch(`/api/admin/memory-groups/${selectedGroupId}/members/${encodeURIComponent(username)}`, {
                method: 'DELETE',
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Failed to remove member');
            groupStatus.textContent = `Removed ${username}`;
            groupStatus.style.color = '#10b981';
            await loadGroupDetails();
        } catch (error) {
            groupStatus.textContent = error.message;
            groupStatus.style.color = '#ef4444';
        }
    }

    async function unshareSession(sessionId) {
        if (!selectedGroupId) return;
        try {
            const response = await fetch(`/api/admin/memory-groups/${selectedGroupId}/sessions/${encodeURIComponent(sessionId)}`, {
                method: 'DELETE',
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || 'Failed to unshare session');
            groupStatus.textContent = `Unshared ${sessionId}`;
            groupStatus.style.color = '#10b981';
            await loadGroupDetails();
        } catch (error) {
            groupStatus.textContent = error.message;
            groupStatus.style.color = '#ef4444';
        }
    }

    async function loadMediaAssets() {
        try {
            const response = await fetch('/api/media');
            const data = await response.json();
            const media = data.media || [];
            mediaTbody.innerHTML = '';
            if (!media.length) {
                mediaTbody.innerHTML = '<tr><td colspan="4" style="text-align:center;">No uploaded media found</td></tr>';
                return;
            }
            media.forEach((m) => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${m.username || ''}</td>
                    <td>${m.session_id || ''}</td>
                    <td><a href="${m.url}" target="_blank" rel="noopener noreferrer">${m.filename || ''}</a></td>
                    <td>${m.mime_type || ''}</td>
                `;
                mediaTbody.appendChild(tr);
            });
        } catch (error) {
            mediaTbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:#ef4444;">${error.message}</td></tr>`;
        }
    }

    // --- Reports search/export (admin) ---
    let latestAdminReportMatches = [];

    function toCsv(rows) {
        if (!rows?.length) return '';
        const headers = Object.keys(rows[0]);
        const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
        return [headers.join(','), ...rows.map((r) => headers.map((h) => esc(r[h])).join(','))].join('\n');
    }

    function downloadBlob(filename, content, type) {
        const blob = new Blob([content], { type });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }

    async function runAdminReportSearch() {
        const status = document.getElementById('admin-report-status');
        const params = new URLSearchParams();
        const read = (id) => document.getElementById(id)?.value?.trim();
        const q = read('admin-report-q');
        const sid = read('admin-report-session-id');
        const from = read('admin-report-date-from');
        const to = read('admin-report-date-to');
        const category = read('admin-report-category');
        const sharedOnly = !!document.getElementById('admin-report-shared-only')?.checked;
        if (q) params.set('q', q);
        if (sid) params.set('session_id', sid);
        if (from) params.set('date_from', from);
        if (to) params.set('date_to', to);
        if (category) params.set('category', category);
        if (sharedOnly) params.set('shared_only', 'true');

        status.textContent = 'Searching…';
        const response = await apiFetch(`/api/reports/find?${params.toString()}`);
        const data = await response.json();
        if (!response.ok) {
            status.textContent = data.detail || 'Search failed';
            status.style.color = '#ef4444';
            latestAdminReportMatches = [];
            return;
        }
        latestAdminReportMatches = data.matches || [];
        status.textContent = `Found ${latestAdminReportMatches.length} matches`;
        status.style.color = '#10b981';
    }

    document.getElementById('admin-report-search-btn')?.addEventListener('click', runAdminReportSearch);
    document.getElementById('admin-report-export-json-btn')?.addEventListener('click', () => {
        if (!latestAdminReportMatches.length) return;
        downloadBlob('admin-report-results.json', JSON.stringify(latestAdminReportMatches, null, 2), 'application/json');
    });
    document.getElementById('admin-report-export-csv-btn')?.addEventListener('click', () => {
        if (!latestAdminReportMatches.length) return;
        downloadBlob('admin-report-results.csv', toCsv(latestAdminReportMatches), 'text/csv');
    });

});
