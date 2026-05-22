import{S,ALL_PROVIDERS,ACCENT_COLORS,APP_VERSION,GITHUB}from"./state";
import{esc}from"./tabs-a";

export function settingsTab():string{
  if(S.auth?.role!=="admin")return`<div class="section-empty">🛡️ Admin access required.</div>`;
  const cfg=S.configs;
  const provList=ALL_PROVIDERS.map(p=>({value:p.value,label:p.label}));

  const subBtns = [
    { id: "provider", label: "🤖 AI Provider" },
    { id: "api", label: "🔑 API Credentials" },
    { id: "memory", label: "🧠 Memory Defaults" },
    { id: "backup", label: "💾 Backup & Import" }
  ].map(t => `<button type="button" class="sub-tab-btn${S.settingsSubTab === t.id ? " active" : ""}" data-settings-sub="${t.id}">${t.label}</button>`).join("");

  return `<div class="sub-tabs">${subBtns}</div>
  <form class="stack" id="cfg-model-form" style="margin-top: 10px;">
    <!-- 1. AI Provider -->
    <div class="settings-sub-group" data-group="provider" style="display: ${S.settingsSubTab === "provider" ? "flex" : "none"}; flex-direction: column; gap: 14px;">
      <div class="panel">
        <div class="panel-title">Default Provider & Agent</div>
        <div class="form-grid">
          <label class="field">Default Provider
            <select name="default_model_provider">
              ${provList.map(p=>`<option value="${esc(p.value)}"${cfg.default_model_provider===p.value?" selected":""}>${esc(p.label)}</option>`).join("")}
            </select>
          </label>
          <label class="field">Default Model
            <input name="default_model" value="${esc(cfg.default_model||"")}" placeholder="e.g. llama3.2, gpt-4o"/>
          </label>
          <label class="field">AI Agent Name
            <input name="chat_agent_name" value="${esc(cfg.chat_agent_name||"AmpAI")}" placeholder="AmpAI"/>
          </label>
          <label class="field">Ollama URL
            <input name="ollama_base_url" value="${esc(cfg.ollama_base_url||"")}" placeholder="http://host.docker.internal:11434"/>
          </label>
        </div>
        <div style="margin-top:12px; display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
          <button type="button" id="btn-fetch-ollama-models" class="sm">🔍 Fetch Ollama Models</button>
          ${S.ollamaModels.length?`<div style="font-size:.75rem;color:var(--muted);flex:1">Ollama models: ${S.ollamaModels.slice(0,6).join(", ")}</div>`:""}
        </div>
      </div>
    </div>

    <!-- 2. API Credentials -->
    <div class="settings-sub-group" data-group="api" style="display: ${S.settingsSubTab === "api" ? "flex" : "none"}; flex-direction: column; gap: 14px;">
      <div class="panel">
        <div class="panel-title">API Keys & Endpoints</div>
        <div class="form-grid">
          <label class="field">OpenRouter Key
            <input name="openrouter_api_key" value="${esc(cfg.openrouter_api_key||"")}" type="password" placeholder="sk-or-…"/>
          </label>
          <label class="field">OpenAI Key
            <input name="openai_api_key" value="${esc(cfg.openai_api_key||"")}" type="password" placeholder="sk-…"/>
          </label>
          <label class="field">Gemini Key
            <input name="gemini_api_key" value="${esc(cfg.gemini_api_key||"")}" type="password" placeholder="AIzaSy…"/>
          </label>
          <label class="field">Anthropic Key
            <input name="anthropic_api_key" value="${esc(cfg.anthropic_api_key||"")}" type="password" placeholder="sk-ant-…"/>
          </label>
          <label class="field">Groq Key
            <input name="groq_api_key" value="${esc(cfg.groq_api_key||"")}" type="password" placeholder="gsk_…"/>
          </label>
          <label class="field">Mistral Key
            <input name="mistral_api_key" value="${esc(cfg.mistral_api_key||"")}" type="password" placeholder="Mistral Key"/>
          </label>
          <label class="field">Cohere Key
            <input name="cohere_api_key" value="${esc(cfg.cohere_api_key||"")}" type="password" placeholder="Cohere Key"/>
          </label>
          <label class="field">LM Studio / Generic URL
            <input name="generic_base_url" value="${esc(cfg.generic_base_url||"")}" placeholder="http://localhost:1234"/>
          </label>
          <label class="field">Generic API Key
            <input name="generic_api_key" value="${esc(cfg.generic_api_key||"")}" type="password" placeholder="Generic Key"/>
          </label>
          <label class="field">AnythingLLM URL
            <input name="anythingllm_base_url" value="${esc(cfg.anythingllm_base_url||"")}" placeholder="http://localhost:3001"/>
          </label>
          <label class="field">AnythingLLM Key
            <input name="anythingllm_api_key" value="${esc(cfg.anythingllm_api_key||"")}" type="password" placeholder="AnythingLLM Key"/>
          </label>
          <label class="field">AnythingLLM Workspace
            <input name="anythingllm_workspace" value="${esc(cfg.anythingllm_workspace||"")}" placeholder="my-workspace"/>
          </label>
        </div>
      </div>
    </div>

    <!-- 3. Memory Defaults -->
    <div class="settings-sub-group" data-group="memory" style="display: ${S.settingsSubTab === "memory" ? "flex" : "none"}; flex-direction: column; gap: 14px;">
      <div class="panel">
        <div class="panel-title">Memory & Web Search</div>
        <div class="form-grid">
          <label class="field">Memory Mode
            <select name="memory_mode">
              ${["full","indexed","context_only","none"].map(m=>`<option${cfg.memory_mode===m?" selected":""}>${m}</option>`).join("")}
            </select>
          </label>
          <label class="field">Memory Top-K
            <input name="memory_top_k" value="${esc(cfg.memory_top_k||"5")}" type="number" min="1" max="30"/>
          </label>
          <label class="field">SerpAPI Key (Web Search)
            <input name="serpapi_api_key" value="${esc(cfg.serpapi_api_key||"")}" type="password" placeholder="SerpAPI Key"/>
          </label>
        </div>
      </div>
    </div>

    <!-- Save button (shown for provider, api, memory) -->
    <button class="primary" type="submit" id="btn-save-settings" style="display: ${S.settingsSubTab !== "backup" ? "block" : "none"}; width: 100%; margin-top: 10px;">💾 Save AI Settings</button>
  </form>

  <!-- 4. Backup & Import -->
  <div class="settings-sub-group" data-group="backup" style="display: ${S.settingsSubTab === "backup" ? "block" : "none"}; margin-top: 10px;">
    <div class="panel">
      <div class="panel-title">Settings Backup</div>
      <div class="row">
        <button id="btn-settings-export">📥 Export JSON</button>
        <label style="flex:1;cursor:pointer">
          <button type="button" onclick="this.parentElement.querySelector('input').click()" style="width:100%">📤 Import JSON</button>
          <input type="file" id="settings-import-file" accept=".json" style="display:none"/>
        </label>
      </div>
    </div>
  </div>`;
}

export function personaliseTab():string{
  return`<div class="panel">
  <div class="panel-title">🎨 Theme Colour</div>
  <div class="hint" style="margin-bottom:10px">Choose accent colour — persisted locally.</div>
  <div class="theme-swatches">
    ${ACCENT_COLORS.map(c=>`<div class="theme-swatch${S.themeAccent===c.value?" active":""}" data-accent="${c.value}" style="background:${c.value}" title="${c.name}"></div>`).join("")}
  </div>
  <label class="field" style="margin-top:8px">Custom hex colour
    <div style="display:flex;gap:8px;align-items:center">
      <input type="color" id="colour-picker" value="${esc(S.themeAccent)}" style="width:44px;height:32px;padding:2px;cursor:pointer"/>
      <input id="colour-hex" value="${esc(S.themeAccent)}" placeholder="#6366f1" style="flex:1"/>
    </div>
  </label>
  <button class="primary" id="btn-apply-colour" style="margin-top:8px;width:100%">Apply Colour</button>
</div>
<div class="panel">
  <div class="panel-title">🤖 AI Display Name</div>
  <div class="hint" style="margin-bottom:8px">Changes agent name shown in chat. Admin config persisted server-side.</div>
  <div class="hint">Current: <strong>${esc(S.configs.chat_agent_name||"AmpAI")}</strong></div>
</div>
<div class="panel">
  <div class="panel-title">📐 Layout</div>
  <div class="row">
    <button id="btn-toggle-sidebar">
      ${S.sidebarCollapsed?"⇥ Expand Sidebar":"⇤ Collapse Sidebar"}
    </button>
  </div>
</div>`;
}

export function adminTab():string{
  const subBtns=["dashboard","users","agent","backup","retention"].map(t=>`<button class="sub-tab-btn${S.adminSubTab===t?" active":""}" data-admin-sub="${t}">${{dashboard:"📊 Dashboard",users:"👥 Users",agent:"🤖 Agent",backup:"💾 Backup",retention:"🗑 Retention"}[t]}</button>`).join("");
  let content="";
  if(S.adminSubTab==="dashboard"){
    const st=S.adminStats||{};
    content=`<div class="dash-stats">
  <div class="dash-stat"><div class="dash-stat-val">${st.session_count??"—"}</div><div class="dash-stat-lbl">Sessions</div></div>
  <div class="dash-stat"><div class="dash-stat-val">${st.memory_count??"—"}</div><div class="dash-stat-lbl">Memories</div></div>
  <div class="dash-stat"><div class="dash-stat-val">${st.user_count??"—"}</div><div class="dash-stat-lbl">Users</div></div>
  <div class="dash-stat"><div class="dash-stat-val" style="font-size:1rem">${esc(st.uptime||"—")}</div><div class="dash-stat-lbl">Uptime</div></div>
</div>
<button id="btn-reload-admin-stats" style="width:100%;margin-bottom:8px">🔄 Refresh Stats</button>
<div class="panel">
  <div class="panel-title">System Health</div>
  <div id="admin-health-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
    <div class="hint">Click Refresh Stats to load health.</div>
  </div>
</div>`;
  }
  else if(S.adminSubTab==="users"){
    content=`<div class="panel">
  <div class="panel-title">User Management (${S.users.length})</div>
  <form class="stack" id="add-user-form">
    <div class="row">
      <label class="field">Username<input name="username" placeholder="newuser"/></label>
      <label class="field">Password<input name="password" type="password" placeholder="min 8 chars"/></label>
    </div>
    <div class="row">
      <label class="field">Role<select name="role"><option value="user">user</option><option value="admin">admin</option></select></label>
      <button class="primary" type="submit" style="margin-top:auto;height:34px">Add User</button>
    </div>
  </form>
</div>
<div>
${S.users.map(u=>`<div class="user-item">
  <div class="user-item-info"><div class="user-item-name">${esc(u.username)}</div><div class="user-item-role">${esc(u.role)}</div></div>
  ${u.username!==S.auth?.username
    ?`<button class="danger sm" data-del-user="${esc(u.username)}">🗑 Delete</button>`
    :`<span class="badge ok" style="font-size:.69rem">You</span>`}
</div>`).join("")}
</div>`;
  }
  else if(S.adminSubTab==="agent"){
    const cfg=S.configs;
    content=`<div class="panel">
  <div class="panel-title">AI Agent Settings</div>
  <form class="stack" id="agent-settings-form">
    <label class="field">Agent Display Name<input name="chat_agent_name" value="${esc(cfg.chat_agent_name||"AmpAI")}" placeholder="AmpAI"/></label>
    <label class="field">Avatar URL (optional)<input name="chat_agent_avatar_url" value="${esc(cfg.chat_agent_avatar_url||"")}" placeholder="https://…"/></label>
    <button class="primary" type="submit">💾 Save Agent Settings</button>
  </form>
</div>
<div class="panel">
  <div class="panel-title">AI Personas</div>
  <div class="hint">Manage personas from the Personas tab in the sidebar.</div>
</div>`;
  }
  else if(S.adminSubTab==="backup"){
    const cfg=S.configs;
    content=`<div class="panel">
  <div class="panel-title">Backup Configuration</div>
  <form class="stack" id="backup-cfg-form">
    <label class="field">Backup Mode<select name="backup_mode">
      ${["local","ftp","smb"].map(m=>`<option${cfg.backup_mode===m?" selected":""}>${m}</option>`).join("")}
    </select></label>
    <label class="field">Local Path<input name="backup_local_path" value="${esc(cfg.backup_local_path||"")}" placeholder="/backups"/></label>
    <div class="divider"></div>
    <div class="panel-title">FTP Settings</div>
    <label class="field">FTP Host<input name="backup_ftp_host" value="${esc(cfg.backup_ftp_host||"")}"/></label>
    <label class="field">FTP User<input name="backup_ftp_user" value="${esc(cfg.backup_ftp_user||"")}"/></label>
    <label class="field">FTP Password<input name="backup_ftp_password" value="${esc(cfg.backup_ftp_password||"")}" type="password"/></label>
    <label class="field">FTP Path<input name="backup_ftp_path" value="${esc(cfg.backup_ftp_path||"")}"/></label>
    <div class="divider"></div>
    <div class="panel-title">SMB Settings</div>
    <label class="field">SMB Host<input name="backup_smb_host" value="${esc(cfg.backup_smb_host||"")}"/></label>
    <label class="field">SMB Share<input name="backup_smb_share" value="${esc(cfg.backup_smb_share||"")}"/></label>
    <label class="field">SMB Path<input name="backup_smb_path" value="${esc(cfg.backup_smb_path||"")}"/></label>
    <label class="field">SMB User<input name="backup_smb_user" value="${esc(cfg.backup_smb_user||"")}"/></label>
    <label class="field">SMB Password<input name="backup_smb_password" value="${esc(cfg.backup_smb_password||"")}" type="password"/></label>
    <button class="primary" type="submit">💾 Save Backup Config</button>
  </form>
</div>
<div class="panel">
  <div class="panel-title">Run Backup</div>
  <div class="row">
    <button id="btn-run-backup" class="success">▶ Run Backup Now</button>
    <button id="btn-load-backups">📂 Load History</button>
  </div>
  <div id="backup-status" style="margin-top:8px;font-size:.8rem;color:var(--muted)"></div>
  <div style="margin-top:8px">
    ${S.backups.map(b=>`<div class="backup-item">
  <div class="backup-item-info"><div class="backup-item-name">${esc(b.name)}</div><div class="backup-item-meta">Commit: ${esc(b.commit||"")} · ${Math.round((b.size_bytes||0)/1024)} KB</div></div>
  <button class="danger sm" data-del-backup="${esc(b.name)}">✕</button>
</div>`).join("")}
  </div>
</div>`;
  }
  else{
    const cfg=S.configs;
    content=`<div class="panel">
  <div class="panel-title">Data Retention</div>
  <form class="stack" id="retention-form">
    <label class="field">Chat History (days)<input name="retention_chat_days" value="${esc(cfg.retention_max_age_days||"365")}" type="number" min="1"/></label>
    <label class="field">Recall Index (days)<input name="recall_index_days" value="${esc(cfg.recall_index_days||"365")}" type="number" min="1"/></label>
    <label class="field">Logs (days)<input name="logs_days" value="${esc(cfg.logs_days||"30")}" type="number" min="1"/></label>
    <div class="row">
      <button class="primary" type="submit">💾 Save Retention</button>
      <button type="button" id="btn-retention-dry-run">🔍 Dry Run</button>
    </div>
  </form>
  <div id="retention-status" style="margin-top:8px;font-size:.8rem;color:var(--muted)"></div>
</div>`;
  }
  return`<div class="sub-tabs">${subBtns}</div>${content}`;
}

export function updateTab():string{
  const v=S.updateVersion;const st=S.updateStatus;
  return`<div class="panel">
  <div class="panel-title">🖥️ Desktop App</div>
  ${S.desktopUpdate?`<div style="padding:10px;background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);border-radius:8px;margin-bottom:10px;font-size:.85rem">
    🎉 New version <strong>${esc(S.desktopUpdate.version)}</strong> available!
    <a href="${esc(S.desktopUpdate.url)}" target="_blank" style="color:#fcd34d;margin-left:8px;font-weight:700">Download →</a>
  </div>`:`<div class="hint" style="margin-bottom:8px">Current version: <strong>v${APP_VERSION}</strong> — Up to date ✓</div>`}
</div>
<div class="panel">
  <div class="panel-title">🐳 Docker Code Update</div>
  ${v?`<div class="status-row" style="margin-bottom:10px">
    <span class="badge ${v.up_to_date?"ok":"warn"}">${v.up_to_date?"✔ Up to date":"⚠ Update available"}</span>
    <div class="status-detail"><strong>Current: ${esc(v.current_commit||"unknown")}</strong><span>Latest: ${esc(v.latest_commit||"unknown")}</span></div>
  </div>`:""}
  <div class="row">
    <button id="btn-check-version">🔍 Check</button>
    <button class="primary" id="btn-trigger-update">⬇ Pull Update</button>
    <button id="btn-poll-update-status" class="sm">🔄 Status</button>
  </div>
  ${st?`<div class="status-row" style="margin-top:10px">
    <span class="badge ${st.state==="success"?"ok":st.state==="running"?"warn":"bad"}">${esc(st.state)}</span>
    <div class="status-detail"><strong>Update ${esc(st.state)}</strong><span>${esc(st.finished_at||st.started_at||"")}</span></div>
  </div>`:""}
  ${S.updateLog.length?`<div class="update-log">${esc(S.updateLog.join("\n"))}</div>`:""}
</div>`;
}
