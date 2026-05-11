(function(){const t=document.createElement("link").relList;if(t&&t.supports&&t.supports("modulepreload"))return;for(const o of document.querySelectorAll('link[rel="modulepreload"]'))n(o);new MutationObserver(o=>{for(const d of o)if(d.type==="childList")for(const u of d.addedNodes)u.tagName==="LINK"&&u.rel==="modulepreload"&&n(u)}).observe(document,{childList:!0,subtree:!0});function s(o){const d={};return o.integrity&&(d.integrity=o.integrity),o.referrerPolicy&&(d.referrerPolicy=o.referrerPolicy),o.crossOrigin==="use-credentials"?d.credentials="include":o.crossOrigin==="anonymous"?d.credentials="omit":d.credentials="same-origin",d}function n(o){if(o.ep)return;o.ep=!0;const d=s(o);fetch(o.href,d)}})();const O="pranto48/ampai",C="0.1.4",f="ampai.serverUrl",_="ampai.auth",k="ampai.sessionId",M="ampai.accent",$=["tauri.localhost","localhost","127.0.0.1"].includes(window.location.hostname)||window.location.protocol.startsWith("tauri")?"http://127.0.0.1:8001":window.location.origin,U=[{name:"Indigo",value:"#6366f1"},{name:"Purple",value:"#8b5cf6"},{name:"Blue",value:"#3b82f6"},{name:"Cyan",value:"#06b6d4"},{name:"Teal",value:"#14b8a6"},{name:"Green",value:"#10b981"},{name:"Amber",value:"#f59e0b"},{name:"Rose",value:"#f43f5e"}],D=[{value:"ollama",label:"🦙 Ollama",local:!0,urlField:"ollama_base_url",keyField:""},{value:"openrouter",label:"🔀 OpenRouter",local:!1,urlField:"",keyField:"openrouter_api_key"},{value:"openai",label:"✨ OpenAI",local:!1,urlField:"",keyField:"openai_api_key"},{value:"gemini",label:"🌟 Gemini",local:!1,urlField:"",keyField:"gemini_api_key"},{value:"anthropic",label:"🔴 Anthropic",local:!1,urlField:"",keyField:"anthropic_api_key"},{value:"groq",label:"⚡ Groq",local:!1,urlField:"",keyField:"groq_api_key"},{value:"mistral",label:"🌪️ Mistral",local:!1,urlField:"",keyField:"mistral_api_key"},{value:"cohere",label:"🔵 Cohere",local:!1,urlField:"",keyField:"cohere_api_key"},{value:"generic",label:"🏠 LM Studio",local:!0,urlField:"generic_base_url",keyField:"generic_api_key"},{value:"anythingllm",label:"📚 AnythingLLM",local:!0,urlField:"anythingllm_base_url",keyField:"anythingllm_api_key"}];function F(e){const t=(e||"").trim();if(!t)return $;const s=/^https?:\/\//i.test(t)?t:`http://${t}`;try{return new URL(s).origin}catch{return $}}function N(){const e=globalThis.crypto?.randomUUID?.()||`d-${Date.now()}-${Math.random().toString(16).slice(2)}`;return localStorage.setItem(k,e),e}function R(){const e=localStorage.getItem(_);if(!e)return null;try{const t=JSON.parse(e);return t?.token&&t?.username?t:null}catch{return localStorage.removeItem(_),null}}const a={serverUrl:F(localStorage.getItem(f)||$),health:{ok:!1,status:"offline",detail:"Not checked"},auth:R(),sessionId:localStorage.getItem(k)||N(),msgs:[],tab:"server",sessions:[],sessionSearch:"",sessionCategoryFilter:"",memories:[],memSubTab:"core",memoryInbox:[],inboxStatusFilter:"pending",memoryAnalytics:null,editingMemId:null,editingMemFact:"",users:[],updateVersion:null,updateStatus:null,updateLog:[],backups:[],tgStatus:null,configs:{},providers:[],personas:[],editingPersona:null,personaModal:!1,adminSubTab:"dashboard",adminStats:null,desktopUpdate:null,themeAccent:localStorage.getItem(M)||"#6366f1",sidebarCollapsed:localStorage.getItem("ampai.sidebarCollapsed")==="1",ollamaModels:[],modal:null,modelType:"ollama",modelName:"",memoryMode:"full",useWebSearch:!1,attachments:[],busy:!1};function i(e){return(e||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}function j(e){return i(e).replace(/```([\s\S]*?)```/g,"<pre><code>$1</code></pre>").replace(/\*\*(.*?)\*\*/g,"<strong>$1</strong>").replace(/\n/g,"<br/>")}function q(e){if(!e)return"-";const t=new Date(e),s=Date.now()-t.getTime(),n=Math.floor(s/6e4);if(n<1)return"just now";if(n<60)return`${n}m ago`;const o=Math.floor(n/60);return o<24?`${o}h ago`:`${Math.floor(o/24)}d ago`}function J(){const e=a.health;return`<div class="panel">
  <div class="panel-title">Server Connection</div>
  <div class="status-row">
    <span class="badge ${e.ok?"ok":"bad"}">${e.ok?"Online":"Offline"}</span>
    <div class="status-detail"><strong>${i(e.status)}</strong><span>${i(e.detail)}</span></div>
  </div>
  <form class="stack" id="server-form">
    <label class="field">Server URL<input name="url" value="${i(a.serverUrl)}" placeholder="http://127.0.0.1:8001"/></label>
    <div class="row">
      <button class="primary" type="submit">Save and Connect</button>
      <button type="button" id="btn-test-server">Test</button>
    </div>
  </form>
  <div class="divider"></div>
  <div class="panel-title">Quick Connect</div>
  <button class="quick-url" data-url="http://127.0.0.1:8001" style="width:100%;margin-bottom:5px">Local 127.0.0.1:8001</button>
  <button class="quick-url" data-url="http://192.168.20.5:8001" style="width:100%">Docker 192.168.20.5:8001</button>
  <div class="divider"></div>
  <div class="panel-title">Docker Start</div>
  <code>docker compose up --build</code>
</div>`}function H(){return a.auth?`<div class="panel">
  <div class="panel-title">Signed In</div>
  <div class="account-card">
    <div class="account-avatar">${a.auth.username[0].toUpperCase()}</div>
    <div><div class="account-name">${i(a.auth.username)}</div><div class="account-role">${i(a.auth.role)}</div></div>
  </div>
  <button id="btn-logout" style="width:100%;margin-top:10px">Logout</button>
</div>`:`<div class="panel">
  <div class="panel-title">Login</div>
  <form class="stack" id="login-form">
    <label class="field">Username<input name="username" value="admin" autocomplete="username"/></label>
    <label class="field">Password<input name="password" type="password" value="P@ssw0rd" autocomplete="current-password"/></label>
    <button class="primary" type="submit">Login</button>
  </form>
</div>`}function z(){const e=[...new Set(a.sessions.map(s=>s.category||"Uncategorized"))],t=a.sessions.filter(s=>{const n=a.sessionSearch.toLowerCase(),o=!n||s.session_id.toLowerCase().includes(n)||(s.category||"").toLowerCase().includes(n),d=!a.sessionCategoryFilter||s.category===a.sessionCategoryFilter;return o&&d});return`<div class="panel" style="padding-bottom:8px">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    Chat History <button id="btn-reload-sessions" class="sm">Refresh</button>
  </div>
  <input id="session-search" placeholder="Search sessions" value="${i(a.sessionSearch)}" style="margin-bottom:6px"/>
  <div class="cat-filter">
    <span class="cat-chip${a.sessionCategoryFilter?"":" active"}" data-cat="">All</span>
    ${e.map(s=>`<span class="cat-chip${a.sessionCategoryFilter===s?" active":""}" data-cat="${i(s)}">${i(s)}</span>`).join("")}
  </div>
</div>
<div class="sessions-list">
  ${t.length?t.map(s=>`<div class="session-item${a.sessionId===s.session_id?" active":""}" data-sid="${i(s.session_id)}">
    <div class="session-item-info">
      <div class="session-item-id">${i(s.category||"Untitled Chat")}</div>
      <div class="session-item-meta">${i(s.session_id.slice(0,14))} · ${(s.updated_at||"").slice(0,10)}</div>
    </div>
    <div class="session-item-actions">
      <button class="sm danger" data-del-sid="${i(s.session_id)}" title="Delete">Delete</button>
    </div>
  </div>`).join(""):`<div class="section-empty">${a.sessions.length?"No matching sessions.":"No sessions yet."}</div>`}
</div>`}function K(){const e=["core","inbox","analytics"].map(s=>`<button class="sub-tab-btn${a.memSubTab===s?" active":""}" data-mem-sub="${s}">${s==="core"?"🧠 Core":s==="inbox"?"📬 Inbox":"📊 Analytics"}</button>`).join("");let t="";if(a.memSubTab==="core")t=`<div class="panel">
  <div class="panel-title">Core Memories (${a.memories.length})</div>
  <form class="stack" id="mem-add-form">
    <label class="field">New fact<textarea name="fact" rows="2" placeholder="e.g. User prefers dark mode">${a.editingMemId!=null?i(a.editingMemFact):""}</textarea></label>
    <button class="primary" type="submit">➕ Add Memory</button>
  </form>
</div>
<div class="memory-list">
${a.memories.length?a.memories.map(s=>`<div class="memory-item${a.editingMemId===s.id?" editing":""}">
  ${a.editingMemId===s.id?`<div style="flex:1"><textarea id="mem-edit-${s.id}" rows="2" style="width:100%;font-size:.82rem">${i(s.fact)}</textarea>
       <div style="display:flex;gap:5px;margin-top:5px">
         <button class="success sm" data-save-mem="${s.id}">💾 Save</button>
         <button class="sm" data-cancel-edit-mem="1">Cancel</button>
       </div></div>`:`<div class="memory-item-text">${i(s.fact)}</div>
     <div class="memory-item-actions">
       <button class="sm" data-edit-mem="${s.id}" title="Edit">✏️</button>
       <button class="sm danger" data-del-mem="${s.id}" title="Delete">✕</button>
     </div>`}
</div>`).join(""):'<div class="section-empty">No core memories yet.<br/>Add facts the AI should always remember.</div>'}
</div>
<div style="padding:8px 0">
  <button id="btn-reload-memory" style="width:100%">🔄 Refresh</button>
</div>
<div class="panel">
  <div class="panel-title">Recall Search</div>
  <form class="stack" id="recall-form">
    <label class="field">Search past memories &amp; sessions<input name="q" placeholder="e.g. Docker setup…"/></label>
    <button class="primary" type="submit">🔍 Search</button>
  </form>
  <div id="recall-results" style="margin-top:8px;font-size:.82rem;color:var(--muted)"></div>
</div>`;else if(a.memSubTab==="inbox"){const s=a.memoryInbox;t=`<div class="panel">
  <div class="panel-title">Memory Inbox — AI Candidates</div>
  <div class="row" style="margin-bottom:8px">
    <select id="inbox-status-filter">
      <option value="pending"${a.inboxStatusFilter==="pending"?" selected":""}>Pending</option>
      <option value="approved"${a.inboxStatusFilter==="approved"?" selected":""}>Approved</option>
      <option value="rejected"${a.inboxStatusFilter==="rejected"?" selected":""}>Rejected</option>
    </select>
    <button id="btn-reload-inbox" class="sm">🔄</button>
  </div>
</div>
<div>
${s.length?s.map(n=>`<div class="inbox-item">
  <div class="inbox-item-meta">
    <span class="badge ${n.status==="approved"?"ok":n.status==="rejected"?"bad":"warn"}">${n.status}</span>
    <span>Confidence: ${(n.confidence||0).toFixed(2)}</span>
    <span>${q(n.created_at)}</span>
  </div>
  <div class="inbox-item-text">${i(n.edited_text||n.candidate_text)}</div>
  <div class="inbox-item-actions">
    <button class="success sm" data-inbox-approve="${n.id}">✓ Approve</button>
    <button class="danger sm" data-inbox-reject="${n.id}">✕ Reject</button>
    <button class="sm" data-inbox-edit="${n.id}">✏️ Edit</button>
    <button class="danger sm" data-inbox-del="${n.id}">🗑</button>
  </div>
</div>`).join(""):`<div class="section-empty">No ${a.inboxStatusFilter} candidates.</div>`}
</div>`}else{const s=a.memoryAnalytics,n=s?.kpis||{},o=s?.memory_writes_per_day||[],d=o.length?Math.max(...o.map(u=>u.count||0),1):1;t=`<div class="kpi-grid">
  <div class="kpi-card"><div class="kpi-value">${n.memory_writes_total??0}</div><div class="kpi-label">Memory Writes</div></div>
  <div class="kpi-card"><div class="kpi-value">${n.retrieval_hits_total??0}</div><div class="kpi-label">Retrieval Hits</div></div>
  <div class="kpi-card"><div class="kpi-value">${n.stale_memories_count??0}</div><div class="kpi-label">Stale Memories</div></div>
  <div class="kpi-card"><div class="kpi-value" style="font-size:1rem">${s?.top_categories?.[0]?.category||"—"}</div><div class="kpi-label">Top Category</div></div>
</div>
<div class="panel">
  <div class="panel-title">Writes per Day</div>
  ${o.slice(-10).map(u=>`<div class="trend-bar-row">
    <div class="trend-bar-label">${(u.day||"").slice(5)}</div>
    <div class="trend-bar-track"><div class="trend-bar-fill" style="width:${Math.round((u.count||0)/d*100)}%"></div></div>
    <div class="trend-bar-val">${u.count||0}</div>
  </div>`).join("")||'<div class="section-empty">No data.</div>'}
</div>
<button id="btn-reload-analytics" style="width:100%">🔄 Refresh Analytics</button>`}return`<div class="sub-tabs">${e}</div>${t}`}function W(){return`<div class="panel">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    AI Personas <button class="sm primary" id="btn-new-persona">➕ New</button>
  </div>
  <div class="hint" style="margin-bottom:8px">Personas define AI personality &amp; system prompts. Set one as default.</div>
</div>
<div>
${a.personas.length?a.personas.map(e=>`<div class="persona-card">
  <div class="persona-card-header">
    <div class="persona-card-name">${i(e.name)}</div>
    ${e.is_default?'<span class="badge ok">Default</span>':""}
  </div>
  ${e.tags?.length?`<div style="margin-bottom:4px">${e.tags.map(t=>`<span class="badge info" style="margin-right:3px;font-size:.65rem">${i(t)}</span>`).join("")}</div>`:""}
  <div class="persona-card-prompt">${i((e.system_prompt||"").slice(0,200))}</div>
  <div class="persona-card-actions">
    <button class="sm" data-edit-persona="${i(e.id)}">✏️ Edit</button>
    <button class="sm success" data-default-persona="${i(e.id)}">⭐ Set Default</button>
    <button class="sm danger" data-del-persona="${i(e.id)}">🗑 Delete</button>
  </div>
</div>`).join(""):'<div class="section-empty">No personas yet.<br/>Create one to customize AI behaviour.</div>'}
</div>
${a.personaModal?G():""}`}function G(){const e=a.editingPersona;return`<div class="modal-overlay" id="persona-modal-overlay">
  <div class="modal-box">
    <div class="modal-title">${e?"Edit Persona":"New Persona"}<button class="modal-close" id="btn-persona-modal-close">✕</button></div>
    <div class="stack">
      <label class="field">Name<input id="persona-name" value="${i(e?.name||"")}" placeholder="e.g. Helpful Assistant"/></label>
      <label class="field">Tags (comma-separated)<input id="persona-tags" value="${i((e?.tags||[]).join(", "))}" placeholder="helpful, concise"/></label>
      <label class="field">System Prompt<textarea id="persona-prompt" rows="5" placeholder="You are a helpful assistant…">${i(e?.system_prompt||"")}</textarea></label>
      <label class="field" style="flex-direction:row;align-items:center;gap:8px">
        <input type="checkbox" id="persona-default" style="width:auto" ${e?.is_default?"checked":""}/> Set as default
      </label>
      <input type="hidden" id="persona-edit-id" value="${i(e?.id||"")}"/>
      <div class="row">
        <button class="primary" id="btn-save-persona">💾 Save</button>
        <button id="btn-persona-modal-close2">Cancel</button>
      </div>
    </div>
  </div>
</div>`}function V(){if(a.auth?.role!=="admin")return'<div class="section-empty">🛡️ Admin access required.</div>';const e=a.configs,t=a.tgStatus;return`<div class="panel">
  <div class="panel-title">AI Provider &amp; Model</div>
  <form class="stack" id="cfg-model-form">
    <label class="field">Default Provider
      <select name="default_model_provider">
        ${(a.providers.length?a.providers:D.map(n=>({value:n.value,label:n.label}))).map(n=>`<option value="${i(n.value)}"${e.default_model_provider===n.value?" selected":""}>${i(n.label)}</option>`).join("")}
      </select>
    </label>
    <label class="field">Default Model<input name="default_model" value="${i(e.default_model||"")}" placeholder="e.g. llama3.2, gpt-4o"/></label>
    <label class="field">AI Agent Name<input name="chat_agent_name" value="${i(e.chat_agent_name||"AmpAI")}" placeholder="AmpAI"/></label>
    <div class="divider"></div>
    <div class="panel-title">API Keys &amp; Endpoints</div>
    <label class="field">Ollama URL<input name="ollama_base_url" value="${i(e.ollama_base_url||"")}" placeholder="http://host.docker.internal:11434"/>
    </label>
    ${a.ollamaModels.length?`<div style="font-size:.75rem;color:var(--muted)">Ollama models: ${a.ollamaModels.slice(0,6).join(", ")}</div>`:""}
    <button type="button" id="btn-fetch-ollama-models" class="sm">🔍 Fetch Ollama Models</button>
    <label class="field">OpenRouter Key<input name="openrouter_api_key" value="${i(e.openrouter_api_key||"")}" type="password" placeholder="sk-or-…"/></label>
    <label class="field">OpenAI Key<input name="openai_api_key" value="${i(e.openai_api_key||"")}" type="password" placeholder="sk-…"/></label>
    <label class="field">Gemini Key<input name="gemini_api_key" value="${i(e.gemini_api_key||"")}" type="password"/></label>
    <label class="field">Anthropic Key<input name="anthropic_api_key" value="${i(e.anthropic_api_key||"")}" type="password"/></label>
    <label class="field">Groq Key<input name="groq_api_key" value="${i(e.groq_api_key||"")}" type="password" placeholder="gsk_…"/></label>
    <label class="field">Mistral Key<input name="mistral_api_key" value="${i(e.mistral_api_key||"")}" type="password"/></label>
    <label class="field">Cohere Key<input name="cohere_api_key" value="${i(e.cohere_api_key||"")}" type="password"/></label>
    <label class="field">LM Studio / Generic URL<input name="generic_base_url" value="${i(e.generic_base_url||"")}" placeholder="http://localhost:1234"/></label>
    <label class="field">Generic API Key<input name="generic_api_key" value="${i(e.generic_api_key||"")}" type="password"/></label>
    <label class="field">AnythingLLM URL<input name="anythingllm_base_url" value="${i(e.anythingllm_base_url||"")}" placeholder="http://localhost:3001"/></label>
    <label class="field">AnythingLLM Key<input name="anythingllm_api_key" value="${i(e.anythingllm_api_key||"")}" type="password"/></label>
    <label class="field">AnythingLLM Workspace<input name="anythingllm_workspace" value="${i(e.anythingllm_workspace||"")}" placeholder="my-workspace"/></label>
    <div class="divider"></div>
    <div class="panel-title">Memory Defaults</div>
    <label class="field">Memory Mode<select name="memory_mode">
      ${["full","indexed","context_only","none"].map(n=>`<option${e.memory_mode===n?" selected":""}>${n}</option>`).join("")}
    </select></label>
    <label class="field">Memory Top-K<input name="memory_top_k" value="${i(e.memory_top_k||"5")}" type="number" min="1" max="30"/></label>
    <label class="field">SerpAPI Key (Web Search)<input name="serpapi_api_key" value="${i(e.serpapi_api_key||"")}" type="password"/></label>
    <button class="primary" type="submit">💾 Save AI Settings</button>
  </form>
</div>
<div class="panel">
  <div class="panel-title">Telegram Bot ${t?`<span class="badge ${t.enabled?"ok":"bad"}" style="float:right;font-size:.69rem">${t.enabled?"Enabled":"Disabled"}</span>`:""}</div>
  ${t?`<div class="hint" style="margin-bottom:8px">Token: ${i(t.token_masked||"not set")} | Polling: ${t.polling_enabled?"On":"Off"}</div>`:""}
  <form class="stack" id="tg-form">
    <label class="field">Bot Token<input name="telegram_bot_token" value="${i(e.telegram_bot_token||"")}" type="password" placeholder="123456:ABC-…"/></label>
    <label class="field">Webhook URL<input name="telegram_webhook_url" value="${i(e.telegram_webhook_url||t?.webhook_url||"")}" placeholder="https://yourdomain.com/webhook"/></label>
    <div class="row">
      <button class="primary" type="submit">💾 Save</button>
      <button type="button" id="btn-tg-test">🤖 Test</button>
    </div>
    <div class="row">
      <button type="button" id="btn-tg-connect">🔗 Set Webhook</button>
      <button type="button" id="btn-tg-disconnect">❌ Remove</button>
    </div>
    <div class="row">
      <button type="button" id="btn-tg-polling-on" class="success">▶ Enable Polling</button>
      <button type="button" id="btn-tg-polling-off" class="danger">⏹ Disable Polling</button>
    </div>
  </form>
</div>
<div class="panel">
  <div class="panel-title">Settings Backup</div>
  <div class="row">
    <button id="btn-settings-export">📥 Export JSON</button>
    <label style="flex:1;cursor:pointer">
      <button type="button" onclick="this.parentElement.querySelector('input').click()" style="width:100%">📤 Import JSON</button>
      <input type="file" id="settings-import-file" accept=".json" style="display:none"/>
    </label>
  </div>
</div>`}function Q(){return`<div class="panel">
  <div class="panel-title">🎨 Theme Colour</div>
  <div class="hint" style="margin-bottom:10px">Choose accent colour — persisted locally.</div>
  <div class="theme-swatches">
    ${U.map(e=>`<div class="theme-swatch${a.themeAccent===e.value?" active":""}" data-accent="${e.value}" style="background:${e.value}" title="${e.name}"></div>`).join("")}
  </div>
  <label class="field" style="margin-top:8px">Custom hex colour
    <div style="display:flex;gap:8px;align-items:center">
      <input type="color" id="colour-picker" value="${i(a.themeAccent)}" style="width:44px;height:32px;padding:2px;cursor:pointer"/>
      <input id="colour-hex" value="${i(a.themeAccent)}" placeholder="#6366f1" style="flex:1"/>
    </div>
  </label>
  <button class="primary" id="btn-apply-colour" style="margin-top:8px;width:100%">Apply Colour</button>
</div>
<div class="panel">
  <div class="panel-title">🤖 AI Display Name</div>
  <div class="hint" style="margin-bottom:8px">Changes agent name shown in chat. Admin config persisted server-side.</div>
  <div class="hint">Current: <strong>${i(a.configs.chat_agent_name||"AmpAI")}</strong></div>
</div>
<div class="panel">
  <div class="panel-title">📐 Layout</div>
  <div class="row">
    <button id="btn-toggle-sidebar">
      ${a.sidebarCollapsed?"⇥ Expand Sidebar":"⇤ Collapse Sidebar"}
    </button>
  </div>
</div>`}function Y(){const e=["dashboard","users","agent","backup","retention"].map(s=>`<button class="sub-tab-btn${a.adminSubTab===s?" active":""}" data-admin-sub="${s}">${{dashboard:"📊 Dashboard",users:"👥 Users",agent:"🤖 Agent",backup:"💾 Backup",retention:"🗑 Retention"}[s]}</button>`).join("");let t="";if(a.adminSubTab==="dashboard"){const s=a.adminStats||{};t=`<div class="dash-stats">
  <div class="dash-stat"><div class="dash-stat-val">${s.session_count??"—"}</div><div class="dash-stat-lbl">Sessions</div></div>
  <div class="dash-stat"><div class="dash-stat-val">${s.memory_count??"—"}</div><div class="dash-stat-lbl">Memories</div></div>
  <div class="dash-stat"><div class="dash-stat-val">${s.user_count??"—"}</div><div class="dash-stat-lbl">Users</div></div>
  <div class="dash-stat"><div class="dash-stat-val" style="font-size:1rem">${i(s.uptime||"—")}</div><div class="dash-stat-lbl">Uptime</div></div>
</div>
<button id="btn-reload-admin-stats" style="width:100%;margin-bottom:8px">🔄 Refresh Stats</button>
<div class="panel">
  <div class="panel-title">System Health</div>
  <div id="admin-health-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
    <div class="hint">Click Refresh Stats to load health.</div>
  </div>
</div>`}else if(a.adminSubTab==="users")t=`<div class="panel">
  <div class="panel-title">User Management (${a.users.length})</div>
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
${a.users.map(s=>`<div class="user-item">
  <div class="user-item-info"><div class="user-item-name">${i(s.username)}</div><div class="user-item-role">${i(s.role)}</div></div>
  ${s.username!==a.auth?.username?`<button class="danger sm" data-del-user="${i(s.username)}">🗑 Delete</button>`:'<span class="badge ok" style="font-size:.69rem">You</span>'}
</div>`).join("")}
</div>`;else if(a.adminSubTab==="agent"){const s=a.configs;t=`<div class="panel">
  <div class="panel-title">AI Agent Settings</div>
  <form class="stack" id="agent-settings-form">
    <label class="field">Agent Display Name<input name="chat_agent_name" value="${i(s.chat_agent_name||"AmpAI")}" placeholder="AmpAI"/></label>
    <label class="field">Avatar URL (optional)<input name="chat_agent_avatar_url" value="${i(s.chat_agent_avatar_url||"")}" placeholder="https://…"/></label>
    <button class="primary" type="submit">💾 Save Agent Settings</button>
  </form>
</div>
<div class="panel">
  <div class="panel-title">AI Personas</div>
  <div class="hint">Manage personas from the Personas tab in the sidebar.</div>
</div>`}else if(a.adminSubTab==="backup"){const s=a.configs;t=`<div class="panel">
  <div class="panel-title">Backup Configuration</div>
  <form class="stack" id="backup-cfg-form">
    <label class="field">Backup Mode<select name="backup_mode">
      ${["local","ftp","smb"].map(n=>`<option${s.backup_mode===n?" selected":""}>${n}</option>`).join("")}
    </select></label>
    <label class="field">Local Path<input name="backup_local_path" value="${i(s.backup_local_path||"")}" placeholder="/backups"/></label>
    <div class="divider"></div>
    <div class="panel-title">FTP Settings</div>
    <label class="field">FTP Host<input name="backup_ftp_host" value="${i(s.backup_ftp_host||"")}"/></label>
    <label class="field">FTP User<input name="backup_ftp_user" value="${i(s.backup_ftp_user||"")}"/></label>
    <label class="field">FTP Password<input name="backup_ftp_password" value="${i(s.backup_ftp_password||"")}" type="password"/></label>
    <label class="field">FTP Path<input name="backup_ftp_path" value="${i(s.backup_ftp_path||"")}"/></label>
    <div class="divider"></div>
    <div class="panel-title">SMB Settings</div>
    <label class="field">SMB Host<input name="backup_smb_host" value="${i(s.backup_smb_host||"")}"/></label>
    <label class="field">SMB Share<input name="backup_smb_share" value="${i(s.backup_smb_share||"")}"/></label>
    <label class="field">SMB Path<input name="backup_smb_path" value="${i(s.backup_smb_path||"")}"/></label>
    <label class="field">SMB User<input name="backup_smb_user" value="${i(s.backup_smb_user||"")}"/></label>
    <label class="field">SMB Password<input name="backup_smb_password" value="${i(s.backup_smb_password||"")}" type="password"/></label>
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
    ${a.backups.map(n=>`<div class="backup-item">
  <div class="backup-item-info"><div class="backup-item-name">${i(n.name)}</div><div class="backup-item-meta">Commit: ${i(n.commit||"")} · ${Math.round((n.size_bytes||0)/1024)} KB</div></div>
  <button class="danger sm" data-del-backup="${i(n.name)}">✕</button>
</div>`).join("")}
  </div>
</div>`}else{const s=a.configs;t=`<div class="panel">
  <div class="panel-title">Data Retention</div>
  <form class="stack" id="retention-form">
    <label class="field">Chat History (days)<input name="retention_chat_days" value="${i(s.retention_max_age_days||"365")}" type="number" min="1"/></label>
    <label class="field">Recall Index (days)<input name="recall_index_days" value="${i(s.recall_index_days||"365")}" type="number" min="1"/></label>
    <label class="field">Logs (days)<input name="logs_days" value="${i(s.logs_days||"30")}" type="number" min="1"/></label>
    <div class="row">
      <button class="primary" type="submit">💾 Save Retention</button>
      <button type="button" id="btn-retention-dry-run">🔍 Dry Run</button>
    </div>
  </form>
  <div id="retention-status" style="margin-top:8px;font-size:.8rem;color:var(--muted)"></div>
</div>`}return`<div class="sub-tabs">${e}</div>${t}`}function X(){const e=a.updateVersion,t=a.updateStatus;return`<div class="panel">
  <div class="panel-title">🖥️ Desktop App</div>
  ${a.desktopUpdate?`<div style="padding:10px;background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);border-radius:8px;margin-bottom:10px;font-size:.85rem">
    🎉 New version <strong>${i(a.desktopUpdate.version)}</strong> available!
    <a href="${i(a.desktopUpdate.url)}" target="_blank" style="color:#fcd34d;margin-left:8px;font-weight:700">Download →</a>
  </div>`:`<div class="hint" style="margin-bottom:8px">Current version: <strong>v${C}</strong> — Up to date ✓</div>`}
</div>
<div class="panel">
  <div class="panel-title">🐳 Docker Code Update</div>
  ${e?`<div class="status-row" style="margin-bottom:10px">
    <span class="badge ${e.up_to_date?"ok":"warn"}">${e.up_to_date?"✔ Up to date":"⚠ Update available"}</span>
    <div class="status-detail"><strong>Current: ${i(e.current_commit||"unknown")}</strong><span>Latest: ${i(e.latest_commit||"unknown")}</span></div>
  </div>`:""}
  <div class="row">
    <button id="btn-check-version">🔍 Check</button>
    <button class="primary" id="btn-trigger-update">⬇ Pull Update</button>
    <button id="btn-poll-update-status" class="sm">🔄 Status</button>
  </div>
  ${t?`<div class="status-row" style="margin-top:10px">
    <span class="badge ${t.state==="success"?"ok":t.state==="running"?"warn":"bad"}">${i(t.state)}</span>
    <div class="status-detail"><strong>Update ${i(t.state)}</strong><span>${i(t.finished_at||t.started_at||"")}</span></div>
  </div>`:""}
  ${a.updateLog.length?`<div class="update-log">${i(a.updateLog.join(`
`))}</div>`:""}
</div>`}function I(e){const t=(e||"").trim();if(!t)return a.serverUrl;const s=/^https?:\/\//i.test(t)?t:`http://${t}`;try{return new URL(s).origin}catch{return a.serverUrl}}function x(e){a.auth=e,e?localStorage.setItem(_,JSON.stringify(e)):localStorage.removeItem(_)}function b(){return a.auth?.role==="admin"}function Z(e){const t=new Headers(e);return t.has("Content-Type")||t.set("Content-Type","application/json"),a.auth?.token&&t.set("Authorization",`Bearer ${a.auth.token}`),t}async function r(e,t={}){const s=new AbortController,n=setTimeout(()=>s.abort(),25e3);try{const o=await fetch(`${a.serverUrl}${e}`,{...t,headers:Z(t.headers),signal:s.signal}),d=await o.text(),u=d?JSON.parse(d):{};if(!o.ok)throw new Error(u?.detail||u?.message||o.statusText);return u}finally{clearTimeout(n)}}function w(e){const t=document.documentElement;t.style.setProperty("--accent",e),t.style.setProperty("--accent-2",e),a.themeAccent=e,localStorage.setItem(M,e)}function ee(){const e=document.querySelector(".sidebar");e&&e.classList.toggle("collapsed",!!a.sidebarCollapsed)}function l(e,t="info"){const s=document.getElementById("toast-container");if(!s)return;const n=document.createElement("div");n.className=`toast toast-${t}`,n.textContent=e,s.appendChild(n),setTimeout(()=>n.remove(),3500)}function g(e,t){a.msgs.push({role:e,content:t,time:new Date().toLocaleTimeString()})}function B(){const e=globalThis.crypto?.randomUUID?.()||`d-${Date.now()}-${Math.random().toString(16).slice(2)}`;return a.sessionId=e,localStorage.setItem(k,e),e}function te(){return a.attachments.map((e,t)=>`
<div class="attach-pill">
  <span title="${i(e.filename)}">${i(e.filename.slice(0,22))}</span>
  <button class="attach-del" data-del-attach="${t}">×</button>
</div>`).join("")}function ae(){if(!a.msgs.length)return`
<div class="chat-empty">
  <div class="msg-avatar" style="background:linear-gradient(135deg,#10b981,#3b82f6)">AI</div>
  <div class="chat-empty-bubble">
    <strong>Hello! I'm AmpAI.</strong><br/>
    I remember your conversations and can reuse them in future chats.<br/><br/>
    <span style="color:var(--muted);font-size:.85rem">Chat history, memory, admin settings, and integrations are shared between the web app and the Windows app.</span>
  </div>
</div>`;const e=a.msgs.map(t=>{const s=a.auth?.username?.[0]?.toUpperCase()||"U",n=t.role==="user"?s:t.role==="system"?"i":"AI",o=t.role==="user"?i(t.content):`<div>${j(t.content)}</div>`;return`
<div class="msg-row ${t.role}">
  <div class="msg-avatar">${n}</div>
  <div>
    <div class="msg-meta">${i(t.role)} · ${i(t.time)}</div>
    <div class="msg-bubble">${o}</div>
  </div>
</div>`});return a.busy&&e.push(`
<div class="msg-row assistant">
  <div class="msg-avatar">AI</div>
  <div class="msg-bubble">
    <div class="typing-dots"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>
  </div>
</div>`),e.join("")}function c(){const e=document.getElementById("app");if(!e)return;e.innerHTML=`
<div class="app-shell">
  <aside class="sidebar${a.sidebarCollapsed?" collapsed":""}">
    <div class="sidebar-header">
      <div class="sidebar-brand">
        <div class="brand-icon">AI</div>
        <div>
          <div class="brand-name">AmpAI</div>
          <div class="brand-sub">Shared Desktop + Web</div>
        </div>
      </div>
      <button class="collapse-btn" id="btn-sidebar-collapse">${a.sidebarCollapsed?"»":"«"}</button>
    </div>
    <div class="tab-bar">
      ${p("server","Server")}
      ${p("account","Account")}
      ${a.auth?p("history","History"):""}
      ${a.auth?p("memory","Memory"):""}
      ${a.auth?p("personas","AI Personas"):""}
      ${a.auth?p("settings","Settings"):""}
      ${a.auth?p("personalise","Personalise"):""}
      ${b()?p("admin","Admin"):""}
      ${b()?p("update","Update"):""}
    </div>
    <div class="tab-panels">
      ${v("server",J())}
      ${v("account",H())}
      ${a.auth?v("history",z()):""}
      ${a.auth?v("memory",K()):""}
      ${a.auth?v("personas",W()):""}
      ${a.auth?v("settings",V()):""}
      ${a.auth?v("personalise",Q()):""}
      ${b()?v("admin",Y()):""}
      ${b()?v("update",X()):""}
    </div>
  </aside>
  <main class="chat-shell">
    ${se()}
    <div class="chat-messages" id="msgs">${ae()}</div>
    <div class="chat-input-bar">
      <div class="attach-pills" id="attach-pills">${te()}</div>
      <div class="input-box">
        <textarea id="chat-textarea" class="chat-textarea" rows="1" placeholder="${a.auth?"Message AmpAI…":"Login to chat"}" ${a.auth?"":"disabled"}></textarea>
        <label class="attach-btn" title="Attach file">
          📎
          <input type="file" id="file-input" multiple style="display:none"/>
        </label>
        <button class="chat-send-btn" id="btn-send" ${a.auth&&!a.busy?"":"disabled"}>${a.busy?"…":"Send"}</button>
      </div>
    </div>
  </main>
</div>
<div id="toast-container"></div>`;const t=document.getElementById("msgs");t&&(t.scrollTop=t.scrollHeight),ee(),oe()}function p(e,t){return`<button class="tab-btn${a.tab===e?" active":""}" data-tab="${e}">${i(t)}</button>`}function v(e,t){return`<div class="tab-panel${a.tab===e?" active":""}">${t}</div>`}function se(){const e=a.providers.length?a.providers:[{value:"ollama",label:"Ollama"},{value:"generic",label:"LM Studio"},{value:"anythingllm",label:"AnythingLLM"},{value:"openrouter",label:"OpenRouter"},{value:"openai",label:"OpenAI"},{value:"gemini",label:"Gemini"},{value:"anthropic",label:"Anthropic"}],t=a.sessions.find(s=>s.session_id===a.sessionId);return`
<div class="chat-topbar">
  <div class="chat-topbar-info">
    <div class="chat-topbar-title">${i(t?.category||"AmpAI Chat")}</div>
    <div class="chat-topbar-sub">${i(a.sessionId.slice(0,20))}…</div>
  </div>
  <span class="ai-name-badge">${i(a.configs.chat_agent_name||"AmpAI")}</span>
  <select class="chat-topbar-select" id="sel-model">
    ${e.map(s=>`<option value="${i(s.value)}"${a.modelType===s.value?" selected":""}>${i(s.label)}</option>`).join("")}
  </select>
  <select class="chat-topbar-select" id="sel-memory">
    ${["full","indexed","context_only","none"].map(s=>`<option value="${s}"${a.memoryMode===s?" selected":""}>${i(s)}</option>`).join("")}
  </select>
  <label class="chat-topbar-check"><input type="checkbox" id="chk-websearch" ${a.useWebSearch?"checked":""}/> Web</label>
  <button class="sm" id="btn-new-session">New</button>
</div>`}async function h(){const e=Array.from(new Set([a.serverUrl,"http://127.0.0.1:8001","http://127.0.0.1:8000","http://192.168.20.5:8001","http://192.168.20.5:8000"]));for(const t of e)try{const s=await fetch(`${t}/healthz`,{signal:AbortSignal.timeout(5e3),headers:{Accept:"application/json"}});if(!s.ok)continue;const n=await s.json();a.serverUrl=t,localStorage.setItem(f,t),a.health={ok:n.status==="ok",status:n.status||"ok",detail:`Connected: ${t}`},c();return}catch{continue}a.health={ok:!1,status:"offline",detail:"Cannot reach server"},c()}function A(e){return e.replace(/^v/i,"").split(".").map(t=>Number.parseInt(t,10)||0)}function ne(e,t){const s=A(e),n=A(t),o=Math.max(s.length,n.length);for(let d=0;d<o;d+=1){const u=s[d]||0,E=n[d]||0;if(u>E)return!0;if(u<E)return!1}return!1}async function S(){try{const e=await fetch(`https://api.github.com/repos/${O}/releases/latest`,{headers:{Accept:"application/vnd.github+json"}});if(!e.ok)return;const t=await e.json(),s=String(t.tag_name||t.name||"").replace(/^v/i,"");if(!s||!ne(s,C)){a.desktopUpdate=null;return}const n=Array.isArray(t.assets)?t.assets.find(o=>String(o.name||"").match(/\.(msi|exe)$/i)):null;a.desktopUpdate={version:s,url:n?.browser_download_url||t.html_url}}catch{a.desktopUpdate=null}}async function m(e){if(a.auth)try{if(e==="history"){const t=await r("/api/sessions?limit=100&archived=false");a.sessions=t.sessions||[]}if(e==="memory"){const t=await r("/api/core-memories");if(a.memories=t.core_memories||[],a.memSubTab==="inbox"){const s=await r(`/api/memory/inbox?status=${encodeURIComponent(a.inboxStatusFilter)}`);a.memoryInbox=s.items||s.candidates||[]}a.memSubTab==="analytics"&&(a.memoryAnalytics=await r("/api/memory/analytics?days=30"))}if(e==="personas"){const t=await r("/api/personas");a.personas=t.personas||[]}if(e==="settings"&&b()){const[t,s,n]=await Promise.all([r("/api/admin/configs"),b()?r("/api/admin/integrations/telegram/status"):Promise.resolve(null),r("/api/models/options")]);a.configs=t||{},a.tgStatus=s,a.providers=n.providers||[],a.modelType=a.configs.default_model_provider||a.modelType}if(e==="admin"&&b()){const[t,s,n,o]=await Promise.all([r("/api/admin/users"),r("/api/analytics/summary"),r("/api/admin/settings/health"),r("/api/health")]);a.users=t.users||[],a.adminStats={session_count:s.total_sessions,memory_count:s.total_memories,user_count:t.users?.length||0,uptime:o?.checks?.app?.detail||o?.status||"ok",health_checks:n.checks||[]}}if(e==="update"&&b()){a.updateVersion=await r("/api/admin/update/version");const t=await r("/api/admin/update/status");a.updateStatus=t,a.updateLog=t.log_lines||[],await S()}}catch(t){l(t.message||`Failed to load ${e}`,"err")}finally{c()}}function ie(e){a.tab=e,c(),m(e)}function oe(){document.querySelectorAll(".tab-btn[data-tab]").forEach(t=>{t.addEventListener("click",()=>ie(t.dataset.tab||"server"))}),document.getElementById("btn-sidebar-collapse")?.addEventListener("click",()=>{a.sidebarCollapsed=!a.sidebarCollapsed,localStorage.setItem("ampai.sidebarCollapsed",a.sidebarCollapsed?"1":"0"),c()}),document.querySelectorAll(".quick-url[data-url]").forEach(t=>{t.addEventListener("click",()=>{a.serverUrl=I(t.dataset.url||""),localStorage.setItem(f,a.serverUrl),h()})}),document.getElementById("server-form")?.addEventListener("submit",async t=>{t.preventDefault();const s=new FormData(t.currentTarget);a.serverUrl=I(String(s.get("url")||"")),localStorage.setItem(f,a.serverUrl),await h()}),document.getElementById("btn-test-server")?.addEventListener("click",()=>{h()}),document.getElementById("login-form")?.addEventListener("submit",async t=>{t.preventDefault();const s=new FormData(t.currentTarget);a.busy=!0,c();try{const n=await r("/api/auth/login",{method:"POST",body:JSON.stringify({username:s.get("username"),password:s.get("password"),remember_me:!0})});x(n),g("system",`Signed in as ${n.username} (${n.role})`),a.tab="history"}catch(n){g("system",n.message||"Login failed")}finally{a.busy=!1,c(),a.auth&&m(a.tab)}}),document.getElementById("btn-logout")?.addEventListener("click",()=>{x(null),a.sessions=[],a.memories=[],a.memoryInbox=[],a.personas=[],a.users=[],a.tab="account",c()}),document.getElementById("sel-model")?.addEventListener("change",t=>{a.modelType=t.currentTarget.value}),document.getElementById("sel-memory")?.addEventListener("change",t=>{a.memoryMode=t.currentTarget.value}),document.getElementById("chk-websearch")?.addEventListener("change",t=>{a.useWebSearch=t.currentTarget.checked}),document.getElementById("btn-new-session")?.addEventListener("click",()=>{B(),a.msgs=[],a.attachments=[],c()});const e=document.getElementById("chat-textarea");e?.addEventListener("keydown",t=>{t.key==="Enter"&&!t.shiftKey&&(t.preventDefault(),T())}),e?.addEventListener("input",()=>{e.style.height="auto",e.style.height=`${Math.min(e.scrollHeight,130)}px`}),document.getElementById("btn-send")?.addEventListener("click",()=>{T()}),document.getElementById("file-input")?.addEventListener("change",async t=>{const s=Array.from(t.currentTarget.files||[]);if(s.length){for(const n of s){const o=new FormData;o.append("file",n);try{const d=await fetch(`${a.serverUrl}/api/upload?session_id=${encodeURIComponent(a.sessionId)}`,{method:"POST",headers:a.auth?.token?{Authorization:`Bearer ${a.auth.token}`}:void 0,body:o});if(!d.ok)throw new Error(n.name);const u=await d.json();a.attachments.push(u),l(`Attached: ${n.name}`,"ok")}catch{l(`Upload failed: ${n.name}`,"err")}}t.currentTarget.value="",c()}}),le(),re(),de(),ce(),me(),ue(),P(),pe()}function le(){document.querySelectorAll("[data-del-attach]").forEach(e=>{e.addEventListener("click",()=>{const t=Number.parseInt(e.dataset.delAttach||"-1",10);t>=0&&(a.attachments.splice(t,1),c())})})}function re(){document.getElementById("btn-reload-sessions")?.addEventListener("click",()=>{m("history")}),document.getElementById("session-search")?.addEventListener("input",e=>{a.sessionSearch=e.currentTarget.value,c()}),document.querySelectorAll("[data-cat]").forEach(e=>{e.addEventListener("click",()=>{a.sessionCategoryFilter=e.dataset.cat||"",c()})}),document.querySelectorAll(".session-item[data-sid]").forEach(e=>{e.addEventListener("click",async t=>{if(t.target.closest("[data-del-sid]"))return;const n=e.dataset.sid||"";if(n){a.sessionId=n,localStorage.setItem(k,n);try{const o=await r(`/api/history/${encodeURIComponent(n)}`);a.msgs=(o.messages||[]).map(d=>({role:d.type==="human"?"user":"assistant",content:d.content||"",time:""})),a.tab="server"}catch(o){g("system",`Failed to load history: ${o.message}`)}c()}})}),document.querySelectorAll("[data-del-sid]").forEach(e=>{e.addEventListener("click",async t=>{t.stopPropagation();const s=e.dataset.delSid||"";if(!(!s||!confirm("Delete this chat session?")))try{await r(`/api/sessions/${encodeURIComponent(s)}`,{method:"DELETE"}),a.sessions=a.sessions.filter(n=>n.session_id!==s),a.sessionId===s&&(B(),a.msgs=[]),l("Session deleted.","info"),c()}catch(n){l(n.message,"err")}})})}function de(){document.querySelectorAll("[data-mem-sub]").forEach(e=>{e.addEventListener("click",()=>{a.memSubTab=e.dataset.memSub||"core",m("memory")})}),document.getElementById("mem-add-form")?.addEventListener("submit",async e=>{e.preventDefault();const t=new FormData(e.currentTarget),s=String(t.get("fact")||"").trim();if(s)try{a.editingMemId!=null?(await r(`/api/admin/core-memories/${a.editingMemId}`,{method:"PATCH",body:JSON.stringify({fact:s})}),a.editingMemId=null,a.editingMemFact="",l("Memory updated.","ok")):(await r("/api/core-memories",{method:"POST",body:JSON.stringify({fact:s})}),l("Memory added.","ok")),await m("memory")}catch(n){l(n.message,"err")}}),document.getElementById("btn-reload-memory")?.addEventListener("click",()=>{m("memory")}),document.querySelectorAll("[data-edit-mem]").forEach(e=>{e.addEventListener("click",()=>{const t=Number.parseInt(e.dataset.editMem||"",10),s=a.memories.find(n=>n.id===t);s&&(a.editingMemId=t,a.editingMemFact=s.fact,c())})}),document.querySelectorAll("[data-cancel-edit-mem]").forEach(e=>{e.addEventListener("click",()=>{a.editingMemId=null,a.editingMemFact="",c()})}),document.querySelectorAll("[data-save-mem]").forEach(e=>{e.addEventListener("click",async()=>{const t=Number.parseInt(e.dataset.saveMem||"",10),n=document.getElementById(`mem-edit-${t}`)?.value.trim()||"";if(n)try{await r(`/api/admin/core-memories/${t}`,{method:"PATCH",body:JSON.stringify({fact:n})}),a.editingMemId=null,a.editingMemFact="",l("Memory updated.","ok"),await m("memory")}catch(o){l(o.message,"err")}})}),document.querySelectorAll("[data-del-mem]").forEach(e=>{e.addEventListener("click",async()=>{const t=e.dataset.delMem||"";if(!(!t||!confirm("Delete this memory?")))try{await r(`/api/admin/core-memories/${t}`,{method:"DELETE"}),l("Memory deleted.","info"),await m("memory")}catch(s){l(s.message,"err")}})}),document.getElementById("recall-form")?.addEventListener("submit",async e=>{e.preventDefault();const t=new FormData(e.currentTarget),s=String(t.get("q")||"").trim(),n=document.getElementById("recall-results");if(!(!s||!n)){n.textContent="Searching…";try{const o=await r("/api/recall/search",{method:"POST",body:JSON.stringify({q:s,session_id:"",limit:10})});n.innerHTML=o.summary?`<div style="white-space:pre-wrap">${i(o.summary)}</div>`:'<div class="hint">No results found.</div>'}catch(o){n.textContent=o.message}}}),document.getElementById("btn-reload-inbox")?.addEventListener("click",()=>{m("memory")}),document.getElementById("inbox-status-filter")?.addEventListener("change",e=>{a.inboxStatusFilter=e.currentTarget.value,m("memory")}),document.querySelectorAll("[data-inbox-approve]").forEach(e=>{e.addEventListener("click",()=>{L(e.dataset.inboxApprove||"","approved")})}),document.querySelectorAll("[data-inbox-reject]").forEach(e=>{e.addEventListener("click",()=>{L(e.dataset.inboxReject||"","rejected")})}),document.querySelectorAll("[data-inbox-del]").forEach(e=>{e.addEventListener("click",async()=>{const t=e.dataset.inboxDel||"";if(!(!t||!confirm("Delete this inbox item?")))try{await r(`/api/memory/inbox/${encodeURIComponent(t)}`,{method:"DELETE"}),await m("memory")}catch(s){l(s.message,"err")}})}),document.querySelectorAll("[data-inbox-edit]").forEach(e=>{e.addEventListener("click",async()=>{const t=e.dataset.inboxEdit||"",s=a.memoryInbox.find(o=>String(o.id)===t);if(!s)return;const n=prompt("Edit memory candidate",s.edited_text||s.candidate_text);if(n!=null)try{await r(`/api/memory/inbox/${encodeURIComponent(t)}`,{method:"PATCH",body:JSON.stringify({edited_text:n,status:s.status})}),await m("memory")}catch(o){l(o.message,"err")}})}),document.getElementById("btn-reload-analytics")?.addEventListener("click",()=>{m("memory")})}async function L(e,t){if(e)try{await r(`/api/memory/inbox/${encodeURIComponent(e)}`,{method:"PATCH",body:JSON.stringify({status:t})}),l(`Memory candidate ${t}.`,"ok"),await m("memory")}catch(s){l(s.message,"err")}}function ce(){document.getElementById("btn-new-persona")?.addEventListener("click",()=>{a.editingPersona=null,a.personaModal=!0,c()}),document.querySelectorAll("[data-edit-persona]").forEach(e=>{e.addEventListener("click",()=>{const t=Number.parseInt(e.dataset.editPersona||"",10),s=a.personas.find(n=>Number(n.id)===t);s&&(a.editingPersona=s,a.personaModal=!0,c())})}),document.querySelectorAll("[data-default-persona]").forEach(e=>{e.addEventListener("click",async()=>{const t=e.dataset.defaultPersona||"";try{await r(`/api/personas/${encodeURIComponent(t)}`,{method:"PATCH",body:JSON.stringify({is_default:!0})}),await m("personas")}catch(s){l(s.message,"err")}})}),document.querySelectorAll("[data-del-persona]").forEach(e=>{e.addEventListener("click",async()=>{const t=e.dataset.delPersona||"";if(!(!t||!confirm("Delete this persona?")))try{await r(`/api/personas/${encodeURIComponent(t)}`,{method:"DELETE"}),l("Persona deleted.","info"),await m("personas")}catch(s){l(s.message,"err")}})}),document.querySelectorAll("#btn-persona-modal-close,#btn-persona-modal-close2").forEach(e=>{e.addEventListener("click",()=>{a.personaModal=!1,a.editingPersona=null,c()})}),document.getElementById("btn-save-persona")?.addEventListener("click",async()=>{const e=document.getElementById("persona-edit-id")?.value,t=document.getElementById("persona-name")?.value.trim()||"",s=document.getElementById("persona-tags")?.value||"",n=document.getElementById("persona-prompt")?.value.trim()||"",o=!!document.getElementById("persona-default")?.checked;if(!t||!n){l("Name and system prompt are required.","err");return}const d={name:t,system_prompt:n,tags:s.split(",").map(u=>u.trim()).filter(Boolean),is_default:o};try{e?await r(`/api/personas/${encodeURIComponent(e)}`,{method:"PATCH",body:JSON.stringify(d)}):await r("/api/personas",{method:"POST",body:JSON.stringify(d)}),a.personaModal=!1,a.editingPersona=null,await m("personas")}catch(u){l(u.message,"err")}})}function me(){document.getElementById("cfg-model-form")?.addEventListener("submit",async e=>{e.preventDefault();const t=new FormData(e.currentTarget),s={};for(const[n,o]of t.entries())s[n]=String(o||"");try{await r("/api/admin/configs",{method:"POST",body:JSON.stringify({configs:s})}),Object.assign(a.configs,s),a.modelType=s.default_model_provider||a.modelType,l("Settings saved.","ok"),c()}catch(n){l(n.message,"err")}}),document.getElementById("btn-fetch-ollama-models")?.addEventListener("click",async()=>{try{const t=await(await fetch(`${a.configs.ollama_base_url||"http://127.0.0.1:11434"}/api/tags`)).json();a.ollamaModels=(t.models||[]).map(s=>s.name).filter(Boolean),l(`Loaded ${a.ollamaModels.length} Ollama models.`,"ok"),c()}catch(e){l(e.message||"Failed to fetch Ollama models.","err")}}),document.getElementById("tg-form")?.addEventListener("submit",async e=>{e.preventDefault();const t=new FormData(e.currentTarget);try{await r("/api/admin/integrations/telegram/save",{method:"POST",body:JSON.stringify({bot_token:t.get("telegram_bot_token"),webhook_url:t.get("telegram_webhook_url"),enabled:!0})}),await m("settings"),l("Telegram settings saved.","ok")}catch(s){l(s.message,"err")}}),y("btn-tg-test","/api/admin/integrations/telegram/test","Telegram test ok."),y("btn-tg-connect","/api/admin/integrations/telegram/connect","Telegram webhook connected."),y("btn-tg-disconnect","/api/admin/integrations/telegram/disconnect","Telegram webhook removed."),y("btn-tg-polling-on","/api/admin/integrations/telegram/enable-polling","Telegram polling enabled."),y("btn-tg-polling-off","/api/admin/integrations/telegram/disable-polling","Telegram polling disabled."),document.getElementById("btn-settings-export")?.addEventListener("click",async()=>{try{const e=await r("/api/admin/settings/export?include_secrets=false"),t=new Blob([JSON.stringify(e,null,2)],{type:"application/json"}),s=document.createElement("a");s.href=URL.createObjectURL(t),s.download=`ampai-settings-${new Date().toISOString().slice(0,10)}.json`,s.click(),l(`Exported ${e.meta?.exported_key_count||0} keys.`,"ok")}catch(e){l(e.message,"err")}}),document.getElementById("settings-import-file")?.addEventListener("change",async e=>{const t=e.currentTarget.files?.[0];if(t)try{const s=JSON.parse(await t.text()),n=await r("/api/admin/settings/import",{method:"POST",body:JSON.stringify({configs:s.configs||s,dry_run:!1,conflict_strategy:"overwrite"})});l(`Imported ${(n.results||[]).length} settings.`,"ok")}catch(s){l(s.message,"err")}})}function y(e,t,s){document.getElementById(e)?.addEventListener("click",async()=>{try{const n=await r(t,{method:"POST"});l(n?.description||n?.message||s,"ok"),a.tab==="settings"&&await m("settings")}catch(n){l(n.message,"err")}})}function ue(){document.querySelectorAll("[data-accent]").forEach(e=>{e.addEventListener("click",()=>{const t=e.dataset.accent||a.themeAccent;w(t),c()})}),document.getElementById("btn-apply-colour")?.addEventListener("click",()=>{const e=document.getElementById("colour-hex")?.value.trim()||a.themeAccent;if(!/^#[0-9a-f]{6}$/i.test(e)){l("Enter a valid hex colour like #2563eb","err");return}w(e),c()}),document.getElementById("btn-toggle-sidebar")?.addEventListener("click",()=>{a.sidebarCollapsed=!a.sidebarCollapsed,localStorage.setItem("ampai.sidebarCollapsed",a.sidebarCollapsed?"1":"0"),c()})}function P(){document.querySelectorAll("[data-admin-sub]").forEach(t=>{t.addEventListener("click",()=>{a.adminSubTab=t.dataset.adminSub||"dashboard",c(),P()})}),document.getElementById("btn-reload-admin-stats")?.addEventListener("click",()=>{m("admin")});const e=document.getElementById("admin-health-grid");e&&Array.isArray(a.adminStats?.health_checks)&&(e.innerHTML=a.adminStats.health_checks.map(t=>`
<div class="panel" style="margin:0;padding:10px">
  <div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start">
    <strong style="font-size:.8rem">${i(t.key||"check")}</strong>
    <span class="badge ${t.status==="ok"?"ok":t.status==="warn"?"warn":"bad"}">${i(t.status||"unknown")}</span>
  </div>
  <div class="hint" style="margin-top:6px">${i(t.message||"")}</div>
  ${t.fix_hint?`<div class="hint" style="margin-top:4px;color:var(--yellow)">${i(t.fix_hint)}</div>`:""}
</div>`).join("")),document.getElementById("add-user-form")?.addEventListener("submit",async t=>{t.preventDefault();const s=new FormData(t.currentTarget);try{await r("/api/admin/users",{method:"POST",body:JSON.stringify({username:s.get("username"),password:s.get("password"),role:s.get("role")})}),await m("admin"),l("User created.","ok")}catch(n){l(n.message,"err")}}),document.querySelectorAll("[data-del-user]").forEach(t=>{t.addEventListener("click",async()=>{const s=t.dataset.delUser||"";if(!(!s||!confirm(`Delete user "${s}"?`)))try{await r(`/api/admin/users/${encodeURIComponent(s)}`,{method:"DELETE"}),await m("admin"),l("User deleted.","info")}catch(n){l(n.message,"err")}})}),document.getElementById("agent-settings-form")?.addEventListener("submit",async t=>{t.preventDefault();const s=new FormData(t.currentTarget),n={chat_agent_name:String(s.get("chat_agent_name")||""),chat_agent_avatar_url:String(s.get("chat_agent_avatar_url")||"")};try{await r("/api/admin/configs",{method:"POST",body:JSON.stringify({configs:n})}),Object.assign(a.configs,n),l("Agent settings saved.","ok"),c()}catch(o){l(o.message,"err")}}),document.getElementById("backup-cfg-form")?.addEventListener("submit",async t=>{t.preventDefault();const s=new FormData(t.currentTarget),n={};for(const[o,d]of s.entries())n[o]=String(d||"");try{await r("/api/admin/configs",{method:"POST",body:JSON.stringify({configs:n})}),Object.assign(a.configs,n),l("Backup settings saved.","ok")}catch(o){l(o.message,"err")}}),document.getElementById("btn-run-backup")?.addEventListener("click",async()=>{try{const t=await r("/api/admin/backup",{method:"POST"}),s=document.getElementById("backup-status");s&&(s.textContent=t.message||"Backup started."),l(t.message||"Backup started.","ok")}catch(t){l(t.message,"err")}}),document.getElementById("btn-load-backups")?.addEventListener("click",async()=>{try{const t=await r("/api/admin/update/backups");a.backups=t.backups||[],c()}catch(t){l(t.message,"err")}}),document.getElementById("retention-form")?.addEventListener("submit",async t=>{t.preventDefault();const s=new FormData(t.currentTarget);try{const n={retention_max_age_days:String(s.get("retention_chat_days")||"365"),recall_index_days:String(s.get("recall_index_days")||"365"),logs_days:String(s.get("logs_days")||"30")};await r("/api/admin/configs",{method:"POST",body:JSON.stringify({configs:n})}),Object.assign(a.configs,n);const o=document.getElementById("retention-status");o&&(o.textContent="Retention settings saved."),l("Retention settings saved.","ok")}catch(n){l(n.message,"err")}}),document.getElementById("btn-retention-dry-run")?.addEventListener("click",async()=>{const t=document.getElementById("retention-form");if(!t)return;const s=new FormData(t);try{const n=await r("/api/admin/retention/dry-run",{method:"POST",body:JSON.stringify({max_age_days:Number(s.get("retention_chat_days")||365),archive_only:!0})}),o=document.getElementById("retention-status");o&&(o.textContent=JSON.stringify(n))}catch(n){l(n.message,"err")}})}function pe(){document.getElementById("btn-check-version")?.addEventListener("click",async()=>{try{a.updateVersion=await r("/api/admin/update/version"),await S(),c()}catch(e){l(e.message,"err")}}),document.getElementById("btn-trigger-update")?.addEventListener("click",async()=>{if(confirm("Pull latest code from GitHub and restart the server?"))try{const e=await r("/api/admin/update/trigger",{method:"POST"});l(e.message||"Update started.","ok")}catch(e){l(e.message,"err")}}),document.getElementById("btn-poll-update-status")?.addEventListener("click",async()=>{try{const e=await r("/api/admin/update/status");a.updateStatus=e,a.updateLog=e.log_lines||[],c()}catch(e){l(e.message,"err")}})}async function T(){const e=document.getElementById("chat-textarea");if(!e||!a.auth||a.busy)return;const t=e.value.trim();if(!(!t&&!a.attachments.length)){e.value="",e.style.height="auto",g("user",t||"(attachment)"),a.busy=!0,c();try{const s=await r("/api/chat",{method:"POST",body:JSON.stringify({session_id:a.sessionId,message:t||"Please review the attached file.",model_type:a.modelType,memory_mode:a.memoryMode,use_web_search:a.useWebSearch,attachments:a.attachments})});g("assistant",s.response||s.message||"No response."),a.attachments=[],m("history")}catch(s){g("assistant",`Error: ${s.message||"Chat failed"}`)}finally{a.busy=!1,c()}}}w(a.themeAccent);c();h();S();a.auth&&m(a.tab);
