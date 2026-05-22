(function(){const a=document.createElement("link").relList;if(a&&a.supports&&a.supports("modulepreload"))return;for(const i of document.querySelectorAll('link[rel="modulepreload"]'))n(i);new MutationObserver(i=>{for(const l of i)if(l.type==="childList")for(const r of l.addedNodes)r.tagName==="LINK"&&r.rel==="modulepreload"&&n(r)}).observe(document,{childList:!0,subtree:!0});function s(i){const l={};return i.integrity&&(l.integrity=i.integrity),i.referrerPolicy&&(l.referrerPolicy=i.referrerPolicy),i.crossOrigin==="use-credentials"?l.credentials="include":i.crossOrigin==="anonymous"?l.credentials="omit":l.credentials="same-origin",l}function n(i){if(i.ep)return;i.ep=!0;const l=s(i);fetch(i.href,l)}})();const z="pranto48/ampai",R="0.1.5",E="ampai.serverUrl",I="ampai.auth",x="ampai.sessionId",q="ampai.accent",L=["tauri.localhost","localhost","127.0.0.1"].includes(window.location.hostname)||window.location.protocol.startsWith("tauri")?"http://127.0.0.1:8001":window.location.origin,K=[{name:"Indigo",value:"#6366f1"},{name:"Purple",value:"#8b5cf6"},{name:"Blue",value:"#3b82f6"},{name:"Cyan",value:"#06b6d4"},{name:"Teal",value:"#14b8a6"},{name:"Green",value:"#10b981"},{name:"Amber",value:"#f59e0b"},{name:"Rose",value:"#f43f5e"}],k=[{value:"ollama",label:"🦙 Ollama",local:!0,urlField:"ollama_base_url",keyField:""},{value:"openrouter",label:"🔀 OpenRouter",local:!1,urlField:"",keyField:"openrouter_api_key"},{value:"openai",label:"✨ OpenAI",local:!1,urlField:"",keyField:"openai_api_key"},{value:"gemini",label:"🌟 Gemini",local:!1,urlField:"",keyField:"gemini_api_key"},{value:"anthropic",label:"🔴 Anthropic",local:!1,urlField:"",keyField:"anthropic_api_key"},{value:"groq",label:"⚡ Groq",local:!1,urlField:"",keyField:"groq_api_key"},{value:"mistral",label:"🌪️ Mistral",local:!1,urlField:"",keyField:"mistral_api_key"},{value:"cohere",label:"🔵 Cohere",local:!1,urlField:"",keyField:"cohere_api_key"},{value:"generic",label:"🏠 LM Studio",local:!0,urlField:"generic_base_url",keyField:"generic_api_key"},{value:"anythingllm",label:"📚 AnythingLLM",local:!0,urlField:"anythingllm_base_url",keyField:"anythingllm_api_key"}];function W(t){const a=(t||"").trim();if(!a)return L;const s=/^https?:\/\//i.test(a)?a:`http://${a}`;try{return new URL(s).origin}catch{return L}}function V(){const t=globalThis.crypto?.randomUUID?.()||`d-${Date.now()}-${Math.random().toString(16).slice(2)}`;return localStorage.setItem(x,t),t}function G(){const t=localStorage.getItem(I);if(!t)return null;try{const a=JSON.parse(t);return a?.token&&a?.username?a:null}catch{return localStorage.removeItem(I),null}}const e={serverUrl:W(localStorage.getItem(E)||L),health:{ok:!1,status:"offline",detail:"Not checked"},auth:G(),sessionId:localStorage.getItem(x)||V(),msgs:[],tab:"server",sessions:[],sessionSearch:"",sessionCategoryFilter:"",sessionPage:1,sessionHasMore:!0,sessionLoadingMore:!1,sessionError:"",renamingSessionId:null,renamingSessionTitle:"",assigningCategorySessionId:null,assigningCategoryValue:"",memories:[],memSubTab:"core",memoryInbox:[],inboxStatusFilter:"pending",memoryAnalytics:null,editingMemId:null,editingMemFact:"",users:[],updateVersion:null,updateStatus:null,updateLog:[],backups:[],tgStatus:null,configs:{},providers:[],personas:[],editingPersona:null,personaModal:!1,adminSubTab:"dashboard",settingsSubTab:"provider",adminStats:null,desktopUpdate:null,themeAccent:localStorage.getItem(q)||"#6366f1",sidebarCollapsed:localStorage.getItem("ampai.sidebarCollapsed")==="1",ollamaModels:[],providerModels:{},modal:null,modelType:"ollama",modelName:"",memoryMode:"full",useWebSearch:!1,enableBrowserTools:!1,enableTerminalTools:!1,attachments:[],busy:!1,fetchingModels:!1,browserState:{enabled:!1,allowlist:[],jobs:[],currentScreenshot:null,confirmationPending:null},terminalState:{enabled:!1,policy:{enabled:!1,require_confirmation:!0,allowed_folders:[],command_allowlist:[],command_denylist:[],timeout:30,max_output:1e4},logs:[],confirmationPending:null},taskState:{tasks:[],filter:{}}};function o(t){return(t||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}function Y(t){return o(t).replace(/```([\s\S]*?)```/g,"<pre><code>$1</code></pre>").replace(/\*\*(.*?)\*\*/g,"<strong>$1</strong>").replace(/\n/g,"<br/>")}function w(t){if(!t)return"-";const a=new Date(t),s=Date.now()-a.getTime(),n=Math.floor(s/6e4);if(n<1)return"just now";if(n<60)return`${n}m ago`;const i=Math.floor(n/60);return i<24?`${i}h ago`:`${Math.floor(i/24)}d ago`}function Q(){return e.auth?`<div class="panel">
  <div class="panel-title">Signed In</div>
  <div class="account-card">
    <div class="account-avatar">${e.auth.username[0].toUpperCase()}</div>
    <div><div class="account-name">${o(e.auth.username)}</div><div class="account-role">${o(e.auth.role)}</div></div>
  </div>
  <button id="btn-logout" style="width:100%;margin-top:10px">Logout</button>
</div>`:`<div class="panel">
  <div class="panel-title">Login</div>
  <form class="stack" id="login-form">
    <label class="field">Username<input name="username" value="admin" autocomplete="username"/></label>
    <label class="field">Password<input name="password" type="password" value="P@ssw0rd" autocomplete="current-password"/></label>
    <button class="primary" type="submit">Login</button>
  </form>
</div>`}function X(){const t=[...new Set(e.sessions.map(l=>l.category||"Uncategorized"))],a=e.sessionSearch.toLowerCase(),n=[...e.sessions.filter(l=>{const r=(l.title||l.category||"").toLowerCase(),u=(l.category||"").toLowerCase(),v=l.session_id.toLowerCase(),g=!a||r.includes(a)||u.includes(a)||v.includes(a),y=!e.sessionCategoryFilter||l.category===e.sessionCategoryFilter;return g&&y})].sort((l,r)=>l.pinned&&!r.pinned?-1:!l.pinned&&r.pinned?1:(r.updated_at||"").localeCompare(l.updated_at||"")),i=e.sessionError?`<div class="session-error-banner">${o(e.sessionError)}</div>`:"";return`<div class="panel" style="padding-bottom:8px">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    Chat History
    <div style="display:flex;gap:4px">
      <button id="btn-new-chat-sidebar" class="sm primary" title="New Chat">+ New</button>
      <button id="btn-reload-sessions" class="sm" title="Refresh">↻</button>
    </div>
  </div>
  <input id="session-search" placeholder="Search sessions…" value="${o(e.sessionSearch)}" style="margin-bottom:6px"/>
  <div class="cat-filter">
    <span class="cat-chip${e.sessionCategoryFilter?"":" active"}" data-cat="">All</span>
    ${t.map(l=>`<span class="cat-chip${e.sessionCategoryFilter===l?" active":""}" data-cat="${o(l)}">${o(l)}</span>`).join("")}
  </div>
  ${i}
</div>
<div class="sessions-list" id="sessions-list-scroll">
  ${n.length?n.map(l=>{const r=l.title||l.category||"Untitled Chat",u=e.sessionId===l.session_id,v=l.pinned,g=e.renamingSessionId===l.session_id,y=e.assigningCategorySessionId===l.session_id;return g?`<div class="session-item active" data-sid="${o(l.session_id)}">
    <div class="session-rename-form">
      <input id="rename-input-${o(l.session_id)}" class="session-rename-input" maxlength="100" value="${o(e.renamingSessionTitle)}" placeholder="Session title (max 100 chars)"/>
      <div class="session-rename-actions">
        <button class="sm primary" data-rename-save="${o(l.session_id)}" title="Save">✓</button>
        <button class="sm" data-rename-cancel="${o(l.session_id)}" title="Cancel">✕</button>
      </div>
    </div>
  </div>`:y?`<div class="session-item active" data-sid="${o(l.session_id)}">
    <div class="session-rename-form">
      <input id="category-input-${o(l.session_id)}" class="session-rename-input" value="${o(e.assigningCategoryValue)}" placeholder="Category name"/>
      <div class="session-rename-actions">
        <button class="sm primary" data-category-save="${o(l.session_id)}" title="Save">✓</button>
        <button class="sm" data-category-cancel="${o(l.session_id)}" title="Cancel">✕</button>
      </div>
    </div>
  </div>`:`<div class="session-item${u?" active":""}${v?" pinned":""}" data-sid="${o(l.session_id)}">
    <div class="session-item-info">
      <div class="session-item-id">${v?'<span class="pin-icon" title="Pinned">📌</span> ':""}${o(r)}</div>
      <div class="session-item-meta">${o(l.category||"Uncategorized")} · ${w(l.updated_at)}</div>
    </div>
    <div class="session-item-actions">
      <button class="sm" data-rename-sid="${o(l.session_id)}" title="Rename">✏️</button>
      <button class="sm" data-pin-sid="${o(l.session_id)}" title="${v?"Unpin":"Pin"}">${v?"📌":"📍"}</button>
      <button class="sm" data-archive-sid="${o(l.session_id)}" title="Archive">📦</button>
      <button class="sm" data-assign-cat-sid="${o(l.session_id)}" title="Assign Category">🏷️</button>
      <button class="sm danger" data-del-sid="${o(l.session_id)}" title="Delete">🗑️</button>
    </div>
  </div>`}).join(""):`<div class="section-empty">${e.sessions.length?"No matching sessions.":"No sessions yet."}</div>`}
  ${e.sessionHasMore&&n.length>=40?`<div class="session-load-more" id="session-load-more"><button class="sm" id="btn-load-more-sessions">${e.sessionLoadingMore?"Loading…":"Load more"}</button></div>`:""}
</div>`}function Z(){const t=["core","inbox","analytics"].map(s=>`<button class="sub-tab-btn${e.memSubTab===s?" active":""}" data-mem-sub="${s}">${s==="core"?"🧠 Core":s==="inbox"?"📬 Inbox":"📊 Analytics"}</button>`).join("");let a="";if(e.memSubTab==="core")a=`<div class="panel">
  <div class="panel-title">Core Memories (${e.memories.length})</div>
  <form class="stack" id="mem-add-form">
    <label class="field">New fact<textarea name="fact" rows="2" placeholder="e.g. User prefers dark mode">${e.editingMemId!=null?o(e.editingMemFact):""}</textarea></label>
    <button class="primary" type="submit">➕ Add Memory</button>
  </form>
</div>
<div class="memory-list">
${e.memories.length?e.memories.map(s=>`<div class="memory-item${e.editingMemId===s.id?" editing":""}">
  ${e.editingMemId===s.id?`<div style="flex:1"><textarea id="mem-edit-${s.id}" rows="2" style="width:100%;font-size:.82rem">${o(s.fact)}</textarea>
       <div style="display:flex;gap:5px;margin-top:5px">
         <button class="success sm" data-save-mem="${s.id}">💾 Save</button>
         <button class="sm" data-cancel-edit-mem="1">Cancel</button>
       </div></div>`:`<div class="memory-item-text">${o(s.fact)}</div>
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
</div>`;else if(e.memSubTab==="inbox"){const s=e.memoryInbox;a=`<div class="panel">
  <div class="panel-title">Memory Inbox — AI Candidates</div>
  <div class="row" style="margin-bottom:8px">
    <select id="inbox-status-filter">
      <option value="pending"${e.inboxStatusFilter==="pending"?" selected":""}>Pending</option>
      <option value="approved"${e.inboxStatusFilter==="approved"?" selected":""}>Approved</option>
      <option value="rejected"${e.inboxStatusFilter==="rejected"?" selected":""}>Rejected</option>
    </select>
    <button id="btn-reload-inbox" class="sm">🔄</button>
  </div>
</div>
<div>
${s.length?s.map(n=>`<div class="inbox-item">
  <div class="inbox-item-meta">
    <span class="badge ${n.status==="approved"?"ok":n.status==="rejected"?"bad":"warn"}">${n.status}</span>
    <span>Confidence: ${(n.confidence||0).toFixed(2)}</span>
    <span>${w(n.created_at)}</span>
  </div>
  <div class="inbox-item-text">${o(n.edited_text||n.candidate_text)}</div>
  <div class="inbox-item-actions">
    <button class="success sm" data-inbox-approve="${n.id}">✓ Approve</button>
    <button class="danger sm" data-inbox-reject="${n.id}">✕ Reject</button>
    <button class="sm" data-inbox-edit="${n.id}">✏️ Edit</button>
    <button class="danger sm" data-inbox-del="${n.id}">🗑</button>
  </div>
</div>`).join(""):`<div class="section-empty">No ${e.inboxStatusFilter} candidates.</div>`}
</div>`}else{const s=e.memoryAnalytics,n=s?.kpis||{},i=s?.memory_writes_per_day||[],l=i.length?Math.max(...i.map(r=>r.count||0),1):1;a=`<div class="kpi-grid">
  <div class="kpi-card"><div class="kpi-value">${n.memory_writes_total??0}</div><div class="kpi-label">Memory Writes</div></div>
  <div class="kpi-card"><div class="kpi-value">${n.retrieval_hits_total??0}</div><div class="kpi-label">Retrieval Hits</div></div>
  <div class="kpi-card"><div class="kpi-value">${n.stale_memories_count??0}</div><div class="kpi-label">Stale Memories</div></div>
  <div class="kpi-card"><div class="kpi-value" style="font-size:1rem">${s?.top_categories?.[0]?.category||"—"}</div><div class="kpi-label">Top Category</div></div>
</div>
<div class="panel">
  <div class="panel-title">Writes per Day</div>
  ${i.slice(-10).map(r=>`<div class="trend-bar-row">
    <div class="trend-bar-label">${(r.day||"").slice(5)}</div>
    <div class="trend-bar-track"><div class="trend-bar-fill" style="width:${Math.round((r.count||0)/l*100)}%"></div></div>
    <div class="trend-bar-val">${r.count||0}</div>
  </div>`).join("")||'<div class="section-empty">No data.</div>'}
</div>
<button id="btn-reload-analytics" style="width:100%">🔄 Refresh Analytics</button>`}return`<div class="sub-tabs">${t}</div>${a}`}function ee(){return`<div class="panel">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    AI Personas <button class="sm primary" id="btn-new-persona">➕ New</button>
  </div>
  <div class="hint" style="margin-bottom:8px">Personas define AI personality &amp; system prompts. Set one as default.</div>
</div>
<div>
${e.personas.length?e.personas.map(t=>`<div class="persona-card">
  <div class="persona-card-header">
    <div class="persona-card-name">${o(t.name)}</div>
    ${t.is_default?'<span class="badge ok">Default</span>':""}
  </div>
  ${t.tags?.length?`<div style="margin-bottom:4px">${t.tags.map(a=>`<span class="badge info" style="margin-right:3px;font-size:.65rem">${o(a)}</span>`).join("")}</div>`:""}
  <div class="persona-card-prompt">${o((t.system_prompt||"").slice(0,200))}</div>
  <div class="persona-card-actions">
    <button class="sm" data-edit-persona="${o(t.id)}">✏️ Edit</button>
    <button class="sm success" data-default-persona="${o(t.id)}">⭐ Set Default</button>
    <button class="sm danger" data-del-persona="${o(t.id)}">🗑 Delete</button>
  </div>
</div>`).join(""):'<div class="section-empty">No personas yet.<br/>Create one to customize AI behaviour.</div>'}
</div>
${e.personaModal?te():""}`}function te(){const t=e.editingPersona;return`<div class="modal-overlay" id="persona-modal-overlay">
  <div class="modal-box">
    <div class="modal-title">${t?"Edit Persona":"New Persona"}<button class="modal-close" id="btn-persona-modal-close">✕</button></div>
    <div class="stack">
      <label class="field">Name<input id="persona-name" value="${o(t?.name||"")}" placeholder="e.g. Helpful Assistant"/></label>
      <label class="field">Tags (comma-separated)<input id="persona-tags" value="${o((t?.tags||[]).join(", "))}" placeholder="helpful, concise"/></label>
      <label class="field">System Prompt<textarea id="persona-prompt" rows="5" placeholder="You are a helpful assistant…">${o(t?.system_prompt||"")}</textarea></label>
      <label class="field" style="flex-direction:row;align-items:center;gap:8px">
        <input type="checkbox" id="persona-default" style="width:auto" ${t?.is_default?"checked":""}/> Set as default
      </label>
      <input type="hidden" id="persona-edit-id" value="${o(t?.id||"")}"/>
      <div class="row">
        <button class="primary" id="btn-save-persona">💾 Save</button>
        <button id="btn-persona-modal-close2">Cancel</button>
      </div>
    </div>
  </div>
</div>`}function ae(){if(e.auth?.role!=="admin")return'<div class="section-empty">🛡️ Admin access required.</div>';const t=e.configs,a=k.map(n=>({value:n.value,label:n.label}));return`<div class="sub-tabs">${[{id:"provider",label:"🤖 AI Provider"},{id:"api",label:"🔑 API Credentials"},{id:"memory",label:"🧠 Memory Defaults"},{id:"backup",label:"💾 Backup & Import"}].map(n=>`<button type="button" class="sub-tab-btn${e.settingsSubTab===n.id?" active":""}" data-settings-sub="${n.id}">${n.label}</button>`).join("")}</div>
  <form class="stack" id="cfg-model-form" style="margin-top: 10px;">
    <!-- 1. AI Provider -->
    <div class="settings-sub-group" data-group="provider" style="display: ${e.settingsSubTab==="provider"?"flex":"none"}; flex-direction: column; gap: 14px;">
      <div class="panel">
        <div class="panel-title">Default Provider & Agent</div>
        <div class="form-grid">
          <label class="field">Default Provider
            <select name="default_model_provider">
              ${a.map(n=>`<option value="${o(n.value)}"${t.default_model_provider===n.value?" selected":""}>${o(n.label)}</option>`).join("")}
            </select>
          </label>
          <label class="field">Default Model
            <input name="default_model" value="${o(t.default_model||"")}" placeholder="e.g. llama3.2, gpt-4o"/>
          </label>
          <label class="field">AI Agent Name
            <input name="chat_agent_name" value="${o(t.chat_agent_name||"AmpAI")}" placeholder="AmpAI"/>
          </label>
          <label class="field">Ollama URL
            <input name="ollama_base_url" value="${o(t.ollama_base_url||"")}" placeholder="http://host.docker.internal:11434"/>
          </label>
        </div>
        <div style="margin-top:12px; display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
          <button type="button" id="btn-fetch-ollama-models" class="sm">🔍 Fetch Ollama Models</button>
          ${e.ollamaModels.length?`<div style="font-size:.75rem;color:var(--muted);flex:1">Ollama models: ${e.ollamaModels.slice(0,6).join(", ")}</div>`:""}
        </div>
      </div>
    </div>

    <!-- 2. API Credentials -->
    <div class="settings-sub-group" data-group="api" style="display: ${e.settingsSubTab==="api"?"flex":"none"}; flex-direction: column; gap: 14px;">
      <div class="panel">
        <div class="panel-title">API Keys & Endpoints</div>
        <div class="form-grid">
          <label class="field">OpenRouter Key
            <input name="openrouter_api_key" value="${o(t.openrouter_api_key||"")}" type="password" placeholder="sk-or-…"/>
          </label>
          <label class="field">OpenAI Key
            <input name="openai_api_key" value="${o(t.openai_api_key||"")}" type="password" placeholder="sk-…"/>
          </label>
          <label class="field">Gemini Key
            <input name="gemini_api_key" value="${o(t.gemini_api_key||"")}" type="password" placeholder="AIzaSy…"/>
          </label>
          <label class="field">Anthropic Key
            <input name="anthropic_api_key" value="${o(t.anthropic_api_key||"")}" type="password" placeholder="sk-ant-…"/>
          </label>
          <label class="field">Groq Key
            <input name="groq_api_key" value="${o(t.groq_api_key||"")}" type="password" placeholder="gsk_…"/>
          </label>
          <label class="field">Mistral Key
            <input name="mistral_api_key" value="${o(t.mistral_api_key||"")}" type="password" placeholder="Mistral Key"/>
          </label>
          <label class="field">Cohere Key
            <input name="cohere_api_key" value="${o(t.cohere_api_key||"")}" type="password" placeholder="Cohere Key"/>
          </label>
          <label class="field">LM Studio / Generic URL
            <input name="generic_base_url" value="${o(t.generic_base_url||"")}" placeholder="http://localhost:1234"/>
          </label>
          <label class="field">Generic API Key
            <input name="generic_api_key" value="${o(t.generic_api_key||"")}" type="password" placeholder="Generic Key"/>
          </label>
          <label class="field">AnythingLLM URL
            <input name="anythingllm_base_url" value="${o(t.anythingllm_base_url||"")}" placeholder="http://localhost:3001"/>
          </label>
          <label class="field">AnythingLLM Key
            <input name="anythingllm_api_key" value="${o(t.anythingllm_api_key||"")}" type="password" placeholder="AnythingLLM Key"/>
          </label>
          <label class="field">AnythingLLM Workspace
            <input name="anythingllm_workspace" value="${o(t.anythingllm_workspace||"")}" placeholder="my-workspace"/>
          </label>
        </div>
      </div>
    </div>

    <!-- 3. Memory Defaults -->
    <div class="settings-sub-group" data-group="memory" style="display: ${e.settingsSubTab==="memory"?"flex":"none"}; flex-direction: column; gap: 14px;">
      <div class="panel">
        <div class="panel-title">Memory & Web Search</div>
        <div class="form-grid">
          <label class="field">Memory Mode
            <select name="memory_mode">
              ${["full","indexed","context_only","none"].map(n=>`<option${t.memory_mode===n?" selected":""}>${n}</option>`).join("")}
            </select>
          </label>
          <label class="field">Memory Top-K
            <input name="memory_top_k" value="${o(t.memory_top_k||"5")}" type="number" min="1" max="30"/>
          </label>
          <label class="field">SerpAPI Key (Web Search)
            <input name="serpapi_api_key" value="${o(t.serpapi_api_key||"")}" type="password" placeholder="SerpAPI Key"/>
          </label>
        </div>
      </div>
    </div>

    <!-- Save button (shown for provider, api, memory) -->
    <button class="primary" type="submit" id="btn-save-settings" style="display: ${e.settingsSubTab!=="backup"?"block":"none"}; width: 100%; margin-top: 10px;">💾 Save AI Settings</button>
  </form>

  <!-- 4. Backup & Import -->
  <div class="settings-sub-group" data-group="backup" style="display: ${e.settingsSubTab==="backup"?"block":"none"}; margin-top: 10px;">
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
  </div>`}function se(){return`<div class="panel">
  <div class="panel-title">🎨 Theme Colour</div>
  <div class="hint" style="margin-bottom:10px">Choose accent colour — persisted locally.</div>
  <div class="theme-swatches">
    ${K.map(t=>`<div class="theme-swatch${e.themeAccent===t.value?" active":""}" data-accent="${t.value}" style="background:${t.value}" title="${t.name}"></div>`).join("")}
  </div>
  <label class="field" style="margin-top:8px">Custom hex colour
    <div style="display:flex;gap:8px;align-items:center">
      <input type="color" id="colour-picker" value="${o(e.themeAccent)}" style="width:44px;height:32px;padding:2px;cursor:pointer"/>
      <input id="colour-hex" value="${o(e.themeAccent)}" placeholder="#6366f1" style="flex:1"/>
    </div>
  </label>
  <button class="primary" id="btn-apply-colour" style="margin-top:8px;width:100%">Apply Colour</button>
</div>
<div class="panel">
  <div class="panel-title">🤖 AI Display Name</div>
  <div class="hint" style="margin-bottom:8px">Changes agent name shown in chat. Admin config persisted server-side.</div>
  <div class="hint">Current: <strong>${o(e.configs.chat_agent_name||"AmpAI")}</strong></div>
</div>
<div class="panel">
  <div class="panel-title">📐 Layout</div>
  <div class="row">
    <button id="btn-toggle-sidebar">
      ${e.sidebarCollapsed?"⇥ Expand Sidebar":"⇤ Collapse Sidebar"}
    </button>
  </div>
</div>`}function ne(){const t=["dashboard","users","agent","backup","retention"].map(s=>`<button class="sub-tab-btn${e.adminSubTab===s?" active":""}" data-admin-sub="${s}">${{dashboard:"📊 Dashboard",users:"👥 Users",agent:"🤖 Agent",backup:"💾 Backup",retention:"🗑 Retention"}[s]}</button>`).join("");let a="";if(e.adminSubTab==="dashboard"){const s=e.adminStats||{};a=`<div class="dash-stats">
  <div class="dash-stat"><div class="dash-stat-val">${s.session_count??"—"}</div><div class="dash-stat-lbl">Sessions</div></div>
  <div class="dash-stat"><div class="dash-stat-val">${s.memory_count??"—"}</div><div class="dash-stat-lbl">Memories</div></div>
  <div class="dash-stat"><div class="dash-stat-val">${s.user_count??"—"}</div><div class="dash-stat-lbl">Users</div></div>
  <div class="dash-stat"><div class="dash-stat-val" style="font-size:1rem">${o(s.uptime||"—")}</div><div class="dash-stat-lbl">Uptime</div></div>
</div>
<button id="btn-reload-admin-stats" style="width:100%;margin-bottom:8px">🔄 Refresh Stats</button>
<div class="panel">
  <div class="panel-title">System Health</div>
  <div id="admin-health-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
    <div class="hint">Click Refresh Stats to load health.</div>
  </div>
</div>`}else if(e.adminSubTab==="users")a=`<div class="panel">
  <div class="panel-title">User Management (${e.users.length})</div>
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
${e.users.map(s=>`<div class="user-item">
  <div class="user-item-info"><div class="user-item-name">${o(s.username)}</div><div class="user-item-role">${o(s.role)}</div></div>
  ${s.username!==e.auth?.username?`<button class="danger sm" data-del-user="${o(s.username)}">🗑 Delete</button>`:'<span class="badge ok" style="font-size:.69rem">You</span>'}
</div>`).join("")}
</div>`;else if(e.adminSubTab==="agent"){const s=e.configs;a=`<div class="panel">
  <div class="panel-title">AI Agent Settings</div>
  <form class="stack" id="agent-settings-form">
    <label class="field">Agent Display Name<input name="chat_agent_name" value="${o(s.chat_agent_name||"AmpAI")}" placeholder="AmpAI"/></label>
    <label class="field">Avatar URL (optional)<input name="chat_agent_avatar_url" value="${o(s.chat_agent_avatar_url||"")}" placeholder="https://…"/></label>
    <button class="primary" type="submit">💾 Save Agent Settings</button>
  </form>
</div>
<div class="panel">
  <div class="panel-title">AI Personas</div>
  <div class="hint">Manage personas from the Personas tab in the sidebar.</div>
</div>`}else if(e.adminSubTab==="backup"){const s=e.configs;a=`<div class="panel">
  <div class="panel-title">Backup Configuration</div>
  <form class="stack" id="backup-cfg-form">
    <label class="field">Backup Mode<select name="backup_mode">
      ${["local","ftp","smb"].map(n=>`<option${s.backup_mode===n?" selected":""}>${n}</option>`).join("")}
    </select></label>
    <label class="field">Local Path<input name="backup_local_path" value="${o(s.backup_local_path||"")}" placeholder="/backups"/></label>
    <div class="divider"></div>
    <div class="panel-title">FTP Settings</div>
    <label class="field">FTP Host<input name="backup_ftp_host" value="${o(s.backup_ftp_host||"")}"/></label>
    <label class="field">FTP User<input name="backup_ftp_user" value="${o(s.backup_ftp_user||"")}"/></label>
    <label class="field">FTP Password<input name="backup_ftp_password" value="${o(s.backup_ftp_password||"")}" type="password"/></label>
    <label class="field">FTP Path<input name="backup_ftp_path" value="${o(s.backup_ftp_path||"")}"/></label>
    <div class="divider"></div>
    <div class="panel-title">SMB Settings</div>
    <label class="field">SMB Host<input name="backup_smb_host" value="${o(s.backup_smb_host||"")}"/></label>
    <label class="field">SMB Share<input name="backup_smb_share" value="${o(s.backup_smb_share||"")}"/></label>
    <label class="field">SMB Path<input name="backup_smb_path" value="${o(s.backup_smb_path||"")}"/></label>
    <label class="field">SMB User<input name="backup_smb_user" value="${o(s.backup_smb_user||"")}"/></label>
    <label class="field">SMB Password<input name="backup_smb_password" value="${o(s.backup_smb_password||"")}" type="password"/></label>
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
    ${e.backups.map(n=>`<div class="backup-item">
  <div class="backup-item-info"><div class="backup-item-name">${o(n.name)}</div><div class="backup-item-meta">Commit: ${o(n.commit||"")} · ${Math.round((n.size_bytes||0)/1024)} KB</div></div>
  <button class="danger sm" data-del-backup="${o(n.name)}">✕</button>
</div>`).join("")}
  </div>
</div>`}else{const s=e.configs;a=`<div class="panel">
  <div class="panel-title">Data Retention</div>
  <form class="stack" id="retention-form">
    <label class="field">Chat History (days)<input name="retention_chat_days" value="${o(s.retention_max_age_days||"365")}" type="number" min="1"/></label>
    <label class="field">Recall Index (days)<input name="recall_index_days" value="${o(s.recall_index_days||"365")}" type="number" min="1"/></label>
    <label class="field">Logs (days)<input name="logs_days" value="${o(s.logs_days||"30")}" type="number" min="1"/></label>
    <div class="row">
      <button class="primary" type="submit">💾 Save Retention</button>
      <button type="button" id="btn-retention-dry-run">🔍 Dry Run</button>
    </div>
  </form>
  <div id="retention-status" style="margin-top:8px;font-size:.8rem;color:var(--muted)"></div>
</div>`}return`<div class="sub-tabs">${t}</div>${a}`}function ie(){const t=e.updateVersion,a=e.updateStatus;return`<div class="panel">
  <div class="panel-title">🖥️ Desktop App</div>
  ${e.desktopUpdate?`<div style="padding:10px;background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.3);border-radius:8px;margin-bottom:10px;font-size:.85rem">
    🎉 New version <strong>${o(e.desktopUpdate.version)}</strong> available!
    <a href="${o(e.desktopUpdate.url)}" target="_blank" style="color:#fcd34d;margin-left:8px;font-weight:700">Download →</a>
  </div>`:`<div class="hint" style="margin-bottom:8px">Current version: <strong>v${R}</strong> — Up to date ✓</div>`}
</div>
<div class="panel">
  <div class="panel-title">🐳 Docker Code Update</div>
  ${t?`<div class="status-row" style="margin-bottom:10px">
    <span class="badge ${t.up_to_date?"ok":"warn"}">${t.up_to_date?"✔ Up to date":"⚠ Update available"}</span>
    <div class="status-detail"><strong>Current: ${o(t.current_commit||"unknown")}</strong><span>Latest: ${o(t.latest_commit||"unknown")}</span></div>
  </div>`:""}
  <div class="row">
    <button id="btn-check-version">🔍 Check</button>
    <button class="primary" id="btn-trigger-update">⬇ Pull Update</button>
    <button id="btn-poll-update-status" class="sm">🔄 Status</button>
  </div>
  ${a?`<div class="status-row" style="margin-top:10px">
    <span class="badge ${a.state==="success"?"ok":a.state==="running"?"warn":"bad"}">${o(a.state)}</span>
    <div class="status-detail"><strong>Update ${o(a.state)}</strong><span>${o(a.finished_at||a.started_at||"")}</span></div>
  </div>`:""}
  ${e.updateLog.length?`<div class="update-log">${o(e.updateLog.join(`
`))}</div>`:""}
</div>`}function oe(){const t=e.configs,a=e.modelType||t.default_model_provider||"ollama",s=e.modelName||t.default_model||"",n=k.map(u=>{const v=a===u.value,g=u.keyField?!!(t[u.keyField]||"").trim():!0,A=(e.providerModels[u.value]||[]).length,J=u.local?'<span class="badge ok" style="font-size:.65rem">Local</span>':g?'<span class="badge ok" style="font-size:.65rem">Key Set</span>':'<span class="badge bad" style="font-size:.65rem">No Key</span>';return`<div class="provider-card${v?" active":""}" data-select-provider="${o(u.value)}">
  <div class="provider-card-header">
    <span class="provider-card-label">${o(u.label)}</span>
    ${J}
  </div>
  <div class="provider-card-models">
    ${A?`<span style="font-size:.72rem;color:var(--muted)">${A} model${A>1?"s":""}</span>`:`<button class="sm" data-fetch-models="${o(u.value)}" style="font-size:.72rem">🔍 Fetch Models</button>`}
  </div>
</div>`}).join(""),i=e.providerModels[a]||[],l=i.length?i.map(u=>{const v=s===u.id,g=u.free?'<span class="badge ok" style="font-size:.6rem;margin-left:4px">FREE</span>':"",y=u.context_length?`<span style="font-size:.68rem;color:var(--muted);margin-left:6px">${Math.round(u.context_length/1e3)}K ctx</span>`:"";return`<div class="model-item${v?" selected":""}" data-select-model="${o(u.id)}">
  <span class="model-item-name">${o(u.name||u.id)}</span>${g}${y}
</div>`}).join(""):`<div class="section-empty" style="padding:12px">
        <button class="primary" data-fetch-models="${o(a)}" style="width:100%">🔍 Fetch Available Models</button>
        <div class="hint" style="margin-top:8px">Click to load models from ${o(a)}</div>
      </div>`;return`<div class="panel">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    🤖 AI Model Selection
    <button class="sm" id="btn-refresh-all-models">🔄 Refresh All</button>
  </div>
  ${s?`<div class="ai-current-selection">
        <span class="hint">Active:</span>
        <strong>${o(a)}</strong> / <code>${o(s)}</code>
      </div>`:`<div class="ai-current-selection">
        <span class="hint">No model selected. Choose a provider and model below.</span>
      </div>`}
</div>

<div class="panel">
  <div class="panel-title">Providers</div>
  <div class="provider-grid">${n}</div>
</div>

<div class="panel">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    Models — ${o(k.find(u=>u.value===a)?.label||a)}
    <button class="sm" data-fetch-models="${o(a)}">🔍 Refresh</button>
  </div>
  <div class="model-list">${l}</div>
</div>

<div class="panel">
  <div class="panel-title">Custom Model Name</div>
  <div class="hint" style="margin-bottom:8px">Type a model ID directly if not listed above (e.g., openai/gpt-oss-120b:free)</div>
  <form id="custom-model-form" class="row" style="gap:8px">
    <input id="custom-model-input" value="${o(s)}" placeholder="provider/model-name" style="flex:1"/>
    <button class="primary" type="submit">Set Model</button>
  </form>
</div>`}function le(){const t=e.taskState.tasks,a=t.filter(r=>r.status==="todo"),s=t.filter(r=>r.status==="in_progress"),n=t.filter(r=>r.status==="done");function i(r){return`<span class="badge ${{urgent:"bad",high:"warn",medium:"info",low:"ok"}[r]||"info"}">${o(r)}</span>`}function l(r){return`<div class="task-card">
  <div class="task-card-header">
    <div class="task-card-title">${o(r.title)}</div>
    ${i(r.priority)}
  </div>
  ${r.description?`<div class="task-card-desc">${o(r.description.slice(0,120))}</div>`:""}
  <div class="task-card-meta">
    ${r.due_at?`<span>Due: ${o(r.due_at.slice(0,10))}</span>`:""}
    <span>${w(r.updated_at)}</span>
  </div>
  <div class="task-card-actions">
    ${r.status!=="todo"?`<button class="sm" data-task-id="${r.id}" data-task-status="todo">← Todo</button>`:""}
    ${r.status!=="in_progress"?`<button class="sm" data-task-id="${r.id}" data-task-status="in_progress">▶ In Progress</button>`:""}
    ${r.status!=="done"?`<button class="sm success" data-task-id="${r.id}" data-task-status="done">✓ Done</button>`:""}
    <button class="sm danger" data-del-task="${r.id}">🗑</button>
  </div>
</div>`}return`<div class="panel" style="padding-bottom:8px">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    📋 Tasks (${t.length}) <button id="btn-reload-tasks" class="sm">🔄 Refresh</button>
  </div>
</div>
<div class="task-columns">
  <div class="task-column">
    <div class="task-column-header">Todo (${a.length})</div>
    ${a.length?a.map(l).join(""):'<div class="section-empty">No tasks</div>'}
  </div>
  <div class="task-column">
    <div class="task-column-header">In Progress (${s.length})</div>
    ${s.length?s.map(l).join(""):'<div class="section-empty">No tasks</div>'}
  </div>
  <div class="task-column">
    <div class="task-column-header">Done (${n.length})</div>
    ${n.length?n.map(l).join(""):'<div class="section-empty">No tasks</div>'}
  </div>
</div>`}function re(t){return`<span class="badge ${t==="completed"?"ok":t==="running"?"warn":t==="failed"?"bad":""}" style="font-size:.69rem">${o(t)}</span>`}function de(){const t=e.browserState,a=t.allowlist.length?t.allowlist.map(i=>`<div class="allowlist-item"><code>${o(i)}</code></div>`).join(""):'<div class="hint">No domains configured. All navigation is blocked.</div>',s=t.jobs.slice(0,200),n=s.length?s.map(i=>`<div class="browser-job-item">
  <div class="browser-job-info">
    <div class="browser-job-type">${o(i.job_type)} ${re(i.status)}</div>
    <div class="browser-job-meta">${w(i.created_at)}${i.request?.url?` · ${o(String(i.request.url))}`:""}</div>
  </div>
</div>`).join(""):'<div class="section-empty">No browser actions recorded yet.</div>';return`<div class="panel">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    Browser Automation ${t.enabled?'<span class="badge ok">Enabled</span>':'<span class="badge bad">Disabled</span>'}
  </div>
  <div class="hint" style="margin-bottom:10px">
    ${t.enabled?"Browser automation is active. Actions require confirmation before execution.":"Browser automation is disabled. An admin must enable it via BROWSER_AUTOMATION_ENABLED."}
  </div>
  <button id="btn-reload-browser" class="sm" style="margin-bottom:12px">🔄 Refresh</button>
</div>
<div class="panel">
  <div class="panel-title">Domain Allowlist</div>
  <div class="hint" style="margin-bottom:8px">Only these domains can be navigated to. Empty list blocks all navigation.</div>
  <div class="allowlist-list" style="margin-bottom:8px">${a}</div>
  <form class="stack" id="browser-allowlist-form">
    <label class="field">Add domain<input name="domain" placeholder="example.com"/></label>
    <div class="row">
      <button class="primary" type="submit">Add Domain</button>
    </div>
  </form>
</div>
<div class="panel">
  <div class="panel-title">Action History <span style="font-size:.75rem;color:var(--muted)">(${s.length} entries)</span></div>
  <div class="browser-jobs-list" style="max-height:400px;overflow-y:auto">${n}</div>
</div>`}function ce(){const t=e.terminalState,a=t.enabled?'<span class="badge ok">Enabled</span>':'<span class="badge bad">Disabled</span>',s=t.policy,n=`<div class="terminal-policy-grid">
  <div class="terminal-policy-item"><strong>Require Confirmation:</strong> ${s.require_confirmation?"Yes":"No"}</div>
  <div class="terminal-policy-item"><strong>Timeout:</strong> ${s.timeout}s</div>
  <div class="terminal-policy-item"><strong>Max Output:</strong> ${s.max_output} chars</div>
  <div class="terminal-policy-item"><strong>Allowed Folders:</strong> ${s.allowed_folders.length?s.allowed_folders.map(l=>o(l)).join(", "):"None configured"}</div>
</div>`,i=t.logs.length?t.logs.slice(0,200).map(l=>{const r=l.blocked?"bad":l.exit_code===0?"ok":"warn",u=l.blocked?"Blocked":l.exit_code===0?"OK":`Exit ${l.exit_code}`;return`<div class="terminal-log-item">
  <div class="terminal-log-header">
    <span class="badge ${r}">${o(u)}</span>
    <code class="terminal-log-cmd">${o(l.command.slice(0,80))}</code>
    <span class="terminal-log-time">${w(l.created_at)}</span>
  </div>
  ${l.output_summary?`<div class="terminal-log-output">${o(l.output_summary.slice(0,200))}</div>`:""}
</div>`}).join(""):'<div class="section-empty">No terminal commands executed yet.</div>';return`<div class="panel">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    ⌨️ Terminal Tools ${a}
  </div>
  <div class="hint" style="margin-bottom:10px">Terminal tools allow AmpAI to execute shell commands within security boundaries.</div>
</div>
<div class="panel">
  <div class="panel-title">Policy</div>
  ${n}
</div>
<div class="panel">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    Command History <button id="btn-reload-terminal" class="sm">🔄 Refresh</button>
  </div>
  <div class="terminal-logs-list">${i}</div>
</div>`}function B(t){const a=(t||"").trim();if(!a)return e.serverUrl;const s=/^https?:\/\//i.test(a)?a:`http://${a}`;try{return new URL(s).origin}catch{return e.serverUrl}}function D(t){e.auth=t,t?localStorage.setItem(I,JSON.stringify(t)):localStorage.removeItem(I)}function b(){return e.auth?.role==="admin"}function me(t){const a=new Headers(t);return a.has("Content-Type")||a.set("Content-Type","application/json"),e.auth?.token&&a.set("Authorization",`Bearer ${e.auth.token}`),a}async function c(t,a={}){const s=new AbortController,n=a.timeout!==void 0?a.timeout:t.includes("/chat")?18e4:3e4,i=n>0?setTimeout(()=>s.abort(),n):void 0;try{const{timeout:l,...r}=a,u=await fetch(`${e.serverUrl}${t}`,{...r,headers:me(r.headers),signal:s.signal}),v=await u.text(),g=v?JSON.parse(v):{};if(!u.ok)throw new Error(g?.detail||g?.message||u.statusText);return g}finally{i&&clearTimeout(i)}}function M(t){const a=document.documentElement;a.style.setProperty("--accent",t),a.style.setProperty("--accent-2",t),e.themeAccent=t,localStorage.setItem(q,t)}function d(t,a="info"){const s=document.getElementById("toast-container");if(!s)return;const n=document.createElement("div");n.className=`toast toast-${a}`,n.textContent=t,s.appendChild(n),setTimeout(()=>n.remove(),3500)}function h(t,a){e.msgs.push({role:t,content:a,time:new Date().toLocaleTimeString()})}function P(){const t=globalThis.crypto?.randomUUID?.()||`d-${Date.now()}-${Math.random().toString(16).slice(2)}`;return e.sessionId=t,localStorage.setItem(x,t),t}function ue(){return e.attachments.map((t,a)=>`
<div class="attach-pill">
  <span title="${o(t.filename)}">${o(t.filename.slice(0,22))}</span>
  <button class="attach-del" data-del-attach="${a}">×</button>
</div>`).join("")}function pe(){if(!e.msgs.length)return`
<div class="chat-empty">
  <div class="msg-avatar" style="background:linear-gradient(135deg,#10b981,#3b82f6)">AI</div>
  <div class="chat-empty-bubble">
    <strong>Hello! I'm AmpAI.</strong><br/>
    I remember your conversations and can reuse them in future chats.<br/><br/>
    <span style="color:var(--muted);font-size:.85rem">Chat history, memory, admin settings, and integrations are shared between the web app and the Windows app.</span>
  </div>
</div>`;const t=e.msgs.map(a=>{const s=e.auth?.username?.[0]?.toUpperCase()||"U",n=a.role==="user"?s:a.role==="system"?"i":"AI",i=a.role==="user"?o(a.content):`<div>${Y(a.content)}</div>`;return`
<div class="msg-row ${a.role}">
  <div class="msg-avatar">${n}</div>
  <div>
    <div class="msg-meta">${o(a.role)} · ${o(a.time)}</div>
    <div class="msg-bubble">${i}</div>
  </div>
</div>`});return e.busy&&t.push(`
<div class="msg-row assistant">
  <div class="msg-avatar">AI</div>
  <div class="msg-bubble">
    <div class="typing-dots"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>
  </div>
</div>`),t.join("")}function m(){const t=document.getElementById("app");if(!t)return;const a=e.tab!=="server"&&e.tab!=="more",s=`
<div class="chat-fullscreen">
  ${ye()}
  <div class="chat-messages" id="msgs">${pe()}</div>
  <div class="chat-input-bar">
    <div class="attach-pills" id="attach-pills">${ue()}</div>
    <div class="input-box">
      <textarea id="chat-textarea" class="chat-textarea" rows="1" placeholder="${e.auth?"Message AmpAI…":"Login to chat"}" ${e.auth?"":"disabled"}></textarea>
      <label class="attach-btn" title="Attach file">
        📎
        <input type="file" id="file-input" multiple style="display:none"/>
      </label>
      <button class="chat-send-btn" id="btn-send" ${e.auth&&!e.busy?"":"disabled"}>${e.busy?"…":"Send"}</button>
    </div>
  </div>
  <nav class="nav-bar">
    ${f("server","💬","Chat")}
    ${f("history","📜","History")}
    ${f("memory","🧠","Memory")}
    ${f("ai","🤖","AI")}
    ${f("tasks","📋","Tasks")}
    ${f("more","☰","More")}
  </nav>
  ${e.tab==="more"?ve():""}
</div>`;if(a){const i=be(e.tab);t.innerHTML=`
${s}
<div class="page-overlay">
  <div class="page-header">
    <button class="page-back-btn" id="btn-back-to-chat">← Back to Chat</button>
    <span class="page-title">${o(ge(e.tab))}</span>
  </div>
  <div class="page-body">${i}</div>
</div>
<div id="toast-container"></div>`}else t.innerHTML=`
${s}
<div id="toast-container"></div>`;const n=document.getElementById("msgs");n&&(n.scrollTop=n.scrollHeight),ke()}function f(t,a,s){return`<button class="nav-item${e.tab===t?" active":""}" data-nav="${t}"><span class="nav-icon">${a}</span><span class="nav-label">${s}</span></button>`}function ve(){return`<div class="more-menu-overlay" id="more-menu">
  <div class="more-menu">
    ${[{id:"account",icon:"👤",label:"Account"},{id:"browser",icon:"🌐",label:"Browser"},{id:"terminal",icon:"⌨️",label:"Terminal"},{id:"personas",icon:"🎭",label:"AI Personas"},{id:"settings",icon:"⚙️",label:"Settings"},{id:"personalise",icon:"🎨",label:"Personalise"},...b()?[{id:"telegram",icon:"📱",label:"Telegram"},{id:"admin",icon:"🛡️",label:"Admin"},{id:"update",icon:"🔄",label:"Update"}]:[]].map(a=>`<button class="more-menu-item" data-nav="${a.id}"><span>${a.icon}</span> ${o(a.label)}</button>`).join("")}
  </div>
</div>`}function ge(t){return{account:"👤 Account",history:"📜 Chat History",memory:"🧠 Memory",ai:"🤖 AI Models & Providers",tasks:"📋 Tasks",browser:"🌐 Browser Automation",terminal:"⌨️ Terminal Tools",personas:"🎭 AI Personas",settings:"⚙️ Settings",personalise:"🎨 Personalise",telegram:"📱 Telegram",admin:"🛡️ Admin",update:"🔄 Update"}[t]||t}function be(t){switch(t){case"account":return Q();case"history":return X();case"memory":return Z();case"ai":return oe();case"tasks":return le();case"browser":return de();case"terminal":return ce();case"personas":return ee();case"settings":return ae();case"personalise":return se();case"telegram":return fe();case"admin":return ne();case"update":return ie();default:return'<div class="section-empty">Page not found</div>'}}function ye(){const t=k.map(i=>({value:i.value,label:i.label})),a=e.sessions.find(i=>i.session_id===e.sessionId),s=e.providerModels[e.modelType]||[];let n;return e.fetchingModels?n='<option value="" disabled selected>Loading models…</option>':s.length?n=s.map(i=>`<option value="${o(i.id)}"${e.modelName===i.id?" selected":""}>${o(i.name||i.id)}${i.free?" ✦":""}</option>`).join(""):n=`<option value="${o(e.modelName)}">${o(e.modelName||"default")}</option>`,`
<div class="chat-topbar">
  <div class="chat-topbar-info">
    <div class="chat-topbar-title">${o(a?.category||"AmpAI Chat")}</div>
    <div class="chat-topbar-sub">${o(e.sessionId.slice(0,20))}…</div>
  </div>
  <span class="ai-name-badge">${o(e.configs.chat_agent_name||"AmpAI")}</span>
  <select class="chat-topbar-select" id="sel-provider">
    ${t.map(i=>`<option value="${o(i.value)}"${e.modelType===i.value?" selected":""}>${o(i.label)}</option>`).join("")}
  </select>
  <select class="chat-topbar-select" id="sel-model" style="max-width:180px">
    ${n}
  </select>
  <select class="chat-topbar-select" id="sel-memory">
    ${["full","indexed","context_only","none"].map(i=>`<option value="${i}"${e.memoryMode===i?" selected":""}>${o(i)}</option>`).join("")}
  </select>
  <label class="chat-topbar-check"><input type="checkbox" id="chk-websearch" ${e.useWebSearch?"checked":""}/> Web</label>
  <button class="sm" id="btn-new-session">New</button>
</div>`}function fe(){const t=e.configs,a=e.tgStatus;return`<div class="panel">
  <div class="panel-title">📱 Telegram Bot ${a?`<span class="badge ${a.enabled?"ok":"bad"}" style="float:right;font-size:.69rem">${a.enabled?"Enabled":"Disabled"}</span>`:""}</div>
  ${a?`<div class="hint" style="margin-bottom:8px">Token: ${o(a.token_masked||"not set")} | Polling: ${a.polling_enabled?"On":"Off"}</div>`:""}
  <form class="stack" id="tg-form">
    <label class="field">Bot Token<input name="telegram_bot_token" value="${o(t.telegram_bot_token||"")}" type="password" placeholder="123456:ABC-…"/></label>
    <label class="field">Webhook URL<input name="telegram_webhook_url" value="${o(t.telegram_webhook_url||a?.webhook_url||"")}" placeholder="https://yourdomain.com/webhook"/></label>
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
</div>`}async function _(){const t=Array.from(new Set([e.serverUrl,"http://127.0.0.1:8001","http://127.0.0.1:8000","http://192.168.20.5:8001","http://192.168.20.5:8000"]));for(const a of t)try{const s=await fetch(`${a}/healthz`,{signal:AbortSignal.timeout(5e3),headers:{Accept:"application/json"}});if(!s.ok)continue;const n=await s.json();e.serverUrl=a,localStorage.setItem(E,a),e.health={ok:n.status==="ok",status:n.status||"ok",detail:`Connected: ${a}`},m();return}catch{continue}e.health={ok:!1,status:"offline",detail:"Cannot reach server"},m()}function N(t){return t.replace(/^v/i,"").split(".").map(a=>Number.parseInt(a,10)||0)}function he(t,a){const s=N(t),n=N(a),i=Math.max(s.length,n.length);for(let l=0;l<i;l+=1){const r=s[l]||0,u=n[l]||0;if(r>u)return!0;if(r<u)return!1}return!1}async function C(){try{const t=await fetch(`https://api.github.com/repos/${z}/releases/latest`,{headers:{Accept:"application/vnd.github+json"}});if(!t.ok)return;const a=await t.json(),s=String(a.tag_name||a.name||"").replace(/^v/i,"");if(!s||!he(s,R)){e.desktopUpdate=null;return}const n=Array.isArray(a.assets)?a.assets.find(i=>String(i.name||"").match(/\.(msi|exe)$/i)):null;e.desktopUpdate={version:s,url:n?.browser_download_url||a.html_url}}catch{e.desktopUpdate=null}}async function p(t){if(e.auth)try{if(t==="history"){e.sessionPage=1,e.sessionHasMore=!0,e.sessionError="";const a=await c("/api/sessions?limit=40&archived=false");e.sessions=a.sessions||[],e.sessions.length<40&&(e.sessionHasMore=!1)}if(t==="memory"){const a=await c("/api/core-memories");if(e.memories=a.core_memories||[],e.memSubTab==="inbox"){const s=await c(`/api/memory/inbox?status=${encodeURIComponent(e.inboxStatusFilter)}`);e.memoryInbox=s.items||s.candidates||[]}e.memSubTab==="analytics"&&(e.memoryAnalytics=await c("/api/memory/analytics?days=30"))}if(t==="tasks"){const a=await c("/api/tasks");e.taskState.tasks=a.tasks||[]}if(t==="ai"){try{const a=await c("/api/models/options");e.providers=a.providers||[];const s=a.models||{};for(const[n,i]of Object.entries(s))Array.isArray(i)&&i.length&&!e.providerModels[n]?.length&&(e.providerModels[n]=i.map(l=>({id:l,name:l,free:l.includes(":free"),local:n==="ollama"||n==="generic"})))}catch{}try{const a=e.modelType||e.configs.default_model_provider||"ollama",s=await c(`/api/models/fetch/${a}`);s.models?.length&&(e.providerModels[a]=s.models)}catch{}}if(t==="browser")try{const a=await c("/api/browser/jobs?limit=200");if(e.browserState.jobs=a.jobs||[],b()){const s=await c("/api/browser/allowlist");e.browserState.allowlist=s.domains||s.allowlist||[]}}catch{}if(t==="terminal")try{const a=await c("/api/terminal/logs?limit=200");if(e.terminalState.logs=a.logs||[],b()){const s=await c("/api/terminal/policy");e.terminalState.policy=s,e.terminalState.enabled=s.enabled??!1}}catch{}if(t==="personas"){const a=await c("/api/personas");e.personas=a.personas||[]}if(t==="settings"&&b()){const[a,s]=await Promise.all([c("/api/admin/configs"),c("/api/models/options")]);e.configs=a||{},e.providers=s.providers||[],e.modelType=e.configs.default_model_provider||e.modelType}if(t==="telegram"&&b()){const[a,s]=await Promise.all([c("/api/admin/configs"),c("/api/admin/integrations/telegram/status")]);e.configs=a||{},e.tgStatus=s}if(t==="admin"&&b()){const[a,s,n,i]=await Promise.all([c("/api/admin/users"),c("/api/analytics/summary"),c("/api/admin/settings/health"),c("/api/health")]);e.users=a.users||[],e.adminStats={session_count:s.total_sessions,memory_count:s.total_memories,user_count:a.users?.length||0,uptime:i?.checks?.app?.detail||i?.status||"ok",health_checks:n.checks||[]}}if(t==="browser")try{const[a,s]=await Promise.all([c("/api/browser/allowlist").catch(()=>({domains:[]})),c("/api/browser/jobs?limit=200").catch(()=>({jobs:[]}))]);e.browserState.allowlist=a.domains||a.allowlist||[],e.browserState.jobs=s.jobs||[],e.browserState.enabled=a.enabled??e.browserState.enabled}catch{}if(t==="update"&&b()){e.updateVersion=await c("/api/admin/update/version");const a=await c("/api/admin/update/status");e.updateStatus=a,e.updateLog=a.log_lines||[],await C()}}catch(a){d(a.message||`Failed to load ${t}`,"err")}finally{m()}}function $e(t){e.tab=t,m(),p(t)}function ke(){document.querySelectorAll("[data-nav]").forEach(a=>{a.addEventListener("click",()=>{const s=a.dataset.nav||"server";if(s==="more"){e.tab==="more"?e.tab="server":e.tab="more",m();return}$e(s)})}),document.getElementById("btn-back-to-chat")?.addEventListener("click",()=>{e.tab="server",m()}),document.querySelector(".more-menu-overlay")?.addEventListener("click",a=>{a.target.classList.contains("more-menu-overlay")&&(e.tab="server",m())}),document.querySelectorAll(".quick-url[data-url]").forEach(a=>{a.addEventListener("click",()=>{e.serverUrl=B(a.dataset.url||""),localStorage.setItem(E,e.serverUrl),_()})}),document.getElementById("server-form")?.addEventListener("submit",async a=>{a.preventDefault();const s=new FormData(a.currentTarget);e.serverUrl=B(String(s.get("url")||"")),localStorage.setItem(E,e.serverUrl),await _()}),document.getElementById("btn-test-server")?.addEventListener("click",()=>{_()}),document.getElementById("login-form")?.addEventListener("submit",async a=>{a.preventDefault();const s=new FormData(a.currentTarget);e.busy=!0,m();try{const n=await c("/api/auth/login",{method:"POST",body:JSON.stringify({username:s.get("username"),password:s.get("password"),remember_me:!0})});D(n),h("system",`Signed in as ${n.username} (${n.role})`),e.tab="history"}catch(n){h("system",n.message||"Login failed")}finally{e.busy=!1,m(),e.auth&&p(e.tab)}}),document.getElementById("btn-logout")?.addEventListener("click",()=>{D(null),e.sessions=[],e.memories=[],e.memoryInbox=[],e.personas=[],e.users=[],e.tab="account",m()}),document.getElementById("sel-provider")?.addEventListener("change",a=>{e.modelType=a.currentTarget.value,e.modelName="",e.fetchingModels=!0,m(),(async()=>{try{const s=await c(`/api/models/fetch/${e.modelType}`);e.providerModels[e.modelType]=s.models||[]}catch(s){d(s.message||`Failed to fetch models for ${e.modelType}`,"err")}finally{e.fetchingModels=!1,m()}})()}),document.getElementById("sel-model")?.addEventListener("change",a=>{e.modelName=a.currentTarget.value}),document.getElementById("sel-memory")?.addEventListener("change",a=>{e.memoryMode=a.currentTarget.value}),document.getElementById("chk-websearch")?.addEventListener("change",a=>{e.useWebSearch=a.currentTarget.checked}),document.getElementById("btn-new-session")?.addEventListener("click",()=>{P(),e.msgs=[],e.attachments=[],m()});const t=document.getElementById("chat-textarea");t?.addEventListener("keydown",a=>{a.key==="Enter"&&!a.shiftKey&&(a.preventDefault(),F())}),t?.addEventListener("input",()=>{t.style.height="auto",t.style.height=`${Math.min(t.scrollHeight,130)}px`}),document.getElementById("btn-send")?.addEventListener("click",()=>{F()}),document.getElementById("file-input")?.addEventListener("change",async a=>{const s=Array.from(a.currentTarget.files||[]);if(s.length){for(const n of s){const i=new FormData;i.append("file",n);try{const l=await fetch(`${e.serverUrl}/api/upload?session_id=${encodeURIComponent(e.sessionId)}`,{method:"POST",headers:e.auth?.token?{Authorization:`Bearer ${e.auth.token}`}:void 0,body:i});if(!l.ok)throw new Error(n.name);const r=await l.json();e.attachments.push(r),d(`Attached: ${n.name}`,"ok")}catch{d(`Upload failed: ${n.name}`,"err")}}a.currentTarget.value="",m()}}),we(),_e(),Se(),Ee(),Ie(),xe(),Ae(),Te(),Le(),Me(),Pe(),H(),Ce()}function we(){document.querySelectorAll("[data-del-attach]").forEach(t=>{t.addEventListener("click",()=>{const a=Number.parseInt(t.dataset.delAttach||"-1",10);a>=0&&(e.attachments.splice(a,1),m())})})}function _e(){document.getElementById("btn-reload-sessions")?.addEventListener("click",()=>{e.sessionPage=1,e.sessionHasMore=!0,p("history")}),document.getElementById("btn-new-chat-sidebar")?.addEventListener("click",()=>{P(),e.msgs=[],e.attachments=[],e.tab="server",m()});let t=null;document.getElementById("session-search")?.addEventListener("input",s=>{const n=s.currentTarget.value;t&&clearTimeout(t),t=setTimeout(()=>{e.sessionSearch=n,m()},300)}),document.querySelectorAll("[data-cat]").forEach(s=>{s.addEventListener("click",()=>{e.sessionCategoryFilter=s.dataset.cat||"",m()})});const a=document.getElementById("sessions-list-scroll");a?.addEventListener("scroll",()=>{if(e.sessionLoadingMore||!e.sessionHasMore)return;const{scrollTop:s,scrollHeight:n,clientHeight:i}=a;s+i>=n-50&&U()}),document.getElementById("btn-load-more-sessions")?.addEventListener("click",()=>{U()}),document.querySelectorAll(".session-item[data-sid]").forEach(s=>{s.addEventListener("click",async n=>{const i=n.target;if(i.closest("[data-del-sid]")||i.closest("[data-rename-sid]")||i.closest("[data-pin-sid]")||i.closest("[data-archive-sid]")||i.closest("[data-assign-cat-sid]")||i.closest("[data-rename-save]")||i.closest("[data-rename-cancel]")||i.closest("[data-category-save]")||i.closest("[data-category-cancel]")||i.closest("input"))return;const l=s.dataset.sid||"";if(l){e.sessionId=l,localStorage.setItem(x,l);try{const r=await c(`/api/history/${encodeURIComponent(l)}`);e.msgs=(r.messages||[]).map(u=>({role:u.type==="human"?"user":"assistant",content:u.content||"",time:""})),e.tab="server"}catch(r){h("system",`Failed to load history: ${r.message}`)}m()}})}),document.querySelectorAll("[data-del-sid]").forEach(s=>{s.addEventListener("click",async n=>{n.stopPropagation();const i=s.dataset.delSid||"";if(!(!i||!confirm("Delete this chat session?"))){e.sessionError="";try{await c(`/api/sessions/${encodeURIComponent(i)}`,{method:"DELETE"}),e.sessions=e.sessions.filter(l=>l.session_id!==i),e.sessionId===i&&(P(),e.msgs=[]),d("Session deleted.","info"),m()}catch(l){e.sessionError=`Delete failed: ${l.message||"Unknown error"}`,d(l.message||"Failed to delete session","err"),m()}}})}),document.querySelectorAll("[data-pin-sid]").forEach(s=>{s.addEventListener("click",async n=>{n.stopPropagation();const i=s.dataset.pinSid||"";if(!i)return;const l=e.sessions.find(u=>u.session_id===i);if(!l)return;const r=!l.pinned;try{await c(`/api/sessions/${encodeURIComponent(i)}`,{method:"PATCH",body:JSON.stringify({pinned:r})}),l.pinned=r,d(r?"Session pinned.":"Session unpinned.","ok"),m()}catch(u){d(u.message||"Failed to update pin","err")}})}),document.querySelectorAll("[data-archive-sid]").forEach(s=>{s.addEventListener("click",async n=>{n.stopPropagation();const i=s.dataset.archiveSid||"";if(i){e.sessionError="";try{await c(`/api/sessions/${encodeURIComponent(i)}`,{method:"PATCH",body:JSON.stringify({archived:!0})}),e.sessions=e.sessions.filter(l=>l.session_id!==i),d("Session archived.","ok"),m()}catch(l){e.sessionError=`Archive failed: ${l.message||"Unknown error"}`,d(l.message||"Failed to archive session","err"),m()}}})}),document.querySelectorAll("[data-rename-sid]").forEach(s=>{s.addEventListener("click",n=>{n.stopPropagation();const i=s.dataset.renameSid||"";if(!i)return;const l=e.sessions.find(r=>r.session_id===i);e.renamingSessionId=i,e.renamingSessionTitle=l?.title||l?.category||"",m(),setTimeout(()=>{const r=document.getElementById(`rename-input-${i}`);r&&(r.focus(),r.select())},50)})}),document.querySelectorAll("[data-rename-save]").forEach(s=>{s.addEventListener("click",async n=>{n.stopPropagation();const i=s.dataset.renameSave||"";if(!i)return;const r=(document.getElementById(`rename-input-${i}`)?.value||"").trim().slice(0,100);if(!r){d("Title cannot be empty.","err");return}try{await c(`/api/sessions/${encodeURIComponent(i)}`,{method:"PATCH",body:JSON.stringify({title:r})});const u=e.sessions.find(v=>v.session_id===i);u&&(u.title=r),e.renamingSessionId=null,e.renamingSessionTitle="",d("Session renamed.","ok"),m()}catch(u){d(u.message||"Failed to rename session","err")}})}),document.querySelectorAll("[data-rename-cancel]").forEach(s=>{s.addEventListener("click",n=>{n.stopPropagation(),e.renamingSessionId=null,e.renamingSessionTitle="",m()})}),document.querySelectorAll(".session-rename-input").forEach(s=>{s.addEventListener("keydown",n=>{n.key==="Enter"&&(n.preventDefault(),s.parentElement?.parentElement?.querySelector("[data-rename-save],[data-category-save]")?.click()),n.key==="Escape"&&(n.preventDefault(),s.parentElement?.parentElement?.querySelector("[data-rename-cancel],[data-category-cancel]")?.click())})}),document.querySelectorAll("[data-assign-cat-sid]").forEach(s=>{s.addEventListener("click",n=>{n.stopPropagation();const i=s.dataset.assignCatSid||"";if(!i)return;const l=e.sessions.find(r=>r.session_id===i);e.assigningCategorySessionId=i,e.assigningCategoryValue=l?.category||"",m(),setTimeout(()=>{const r=document.getElementById(`category-input-${i}`);r&&(r.focus(),r.select())},50)})}),document.querySelectorAll("[data-category-save]").forEach(s=>{s.addEventListener("click",async n=>{n.stopPropagation();const i=s.dataset.categorySave||"";if(!i)return;const r=(document.getElementById(`category-input-${i}`)?.value||"").trim()||"Uncategorized";try{await c(`/api/sessions/${encodeURIComponent(i)}`,{method:"PATCH",body:JSON.stringify({category:r})});const u=e.sessions.find(v=>v.session_id===i);u&&(u.category=r),e.assigningCategorySessionId=null,e.assigningCategoryValue="",d("Category updated.","ok"),m()}catch(u){d(u.message||"Failed to assign category","err")}})}),document.querySelectorAll("[data-category-cancel]").forEach(s=>{s.addEventListener("click",n=>{n.stopPropagation(),e.assigningCategorySessionId=null,e.assigningCategoryValue="",m()})})}async function U(){if(!(e.sessionLoadingMore||!e.sessionHasMore)){e.sessionLoadingMore=!0,m();try{const t=e.sessionPage+1,a=(t-1)*40,n=(await c(`/api/sessions?limit=40&offset=${a}&archived=false`)).sessions||[];n.length<40&&(e.sessionHasMore=!1);const i=new Set(e.sessions.map(l=>l.session_id));for(const l of n)i.has(l.session_id)||e.sessions.push(l);e.sessionPage=t}catch(t){d(t.message||"Failed to load more sessions","err")}finally{e.sessionLoadingMore=!1,m()}}}function Se(){document.querySelectorAll("[data-mem-sub]").forEach(t=>{t.addEventListener("click",()=>{e.memSubTab=t.dataset.memSub||"core",p("memory")})}),document.getElementById("mem-add-form")?.addEventListener("submit",async t=>{t.preventDefault();const a=new FormData(t.currentTarget),s=String(a.get("fact")||"").trim();if(s)try{e.editingMemId!=null?(await c(`/api/admin/core-memories/${e.editingMemId}`,{method:"PATCH",body:JSON.stringify({fact:s})}),e.editingMemId=null,e.editingMemFact="",d("Memory updated.","ok")):(await c("/api/core-memories",{method:"POST",body:JSON.stringify({fact:s})}),d("Memory added.","ok")),await p("memory")}catch(n){d(n.message,"err")}}),document.getElementById("btn-reload-memory")?.addEventListener("click",()=>{p("memory")}),document.querySelectorAll("[data-edit-mem]").forEach(t=>{t.addEventListener("click",()=>{const a=Number.parseInt(t.dataset.editMem||"",10),s=e.memories.find(n=>n.id===a);s&&(e.editingMemId=a,e.editingMemFact=s.fact,m())})}),document.querySelectorAll("[data-cancel-edit-mem]").forEach(t=>{t.addEventListener("click",()=>{e.editingMemId=null,e.editingMemFact="",m()})}),document.querySelectorAll("[data-save-mem]").forEach(t=>{t.addEventListener("click",async()=>{const a=Number.parseInt(t.dataset.saveMem||"",10),n=document.getElementById(`mem-edit-${a}`)?.value.trim()||"";if(n)try{await c(`/api/admin/core-memories/${a}`,{method:"PATCH",body:JSON.stringify({fact:n})}),e.editingMemId=null,e.editingMemFact="",d("Memory updated.","ok"),await p("memory")}catch(i){d(i.message,"err")}})}),document.querySelectorAll("[data-del-mem]").forEach(t=>{t.addEventListener("click",async()=>{const a=t.dataset.delMem||"";if(!(!a||!confirm("Delete this memory?")))try{await c(`/api/admin/core-memories/${a}`,{method:"DELETE"}),d("Memory deleted.","info"),await p("memory")}catch(s){d(s.message,"err")}})}),document.getElementById("recall-form")?.addEventListener("submit",async t=>{t.preventDefault();const a=new FormData(t.currentTarget),s=String(a.get("q")||"").trim(),n=document.getElementById("recall-results");if(!(!s||!n)){n.textContent="Searching…";try{const i=await c("/api/recall/search",{method:"POST",body:JSON.stringify({q:s,session_id:"",limit:10})});n.innerHTML=i.summary?`<div style="white-space:pre-wrap">${o(i.summary)}</div>`:'<div class="hint">No results found.</div>'}catch(i){n.textContent=i.message}}}),document.getElementById("btn-reload-inbox")?.addEventListener("click",()=>{p("memory")}),document.getElementById("inbox-status-filter")?.addEventListener("change",t=>{e.inboxStatusFilter=t.currentTarget.value,p("memory")}),document.querySelectorAll("[data-inbox-approve]").forEach(t=>{t.addEventListener("click",()=>{O(t.dataset.inboxApprove||"","approved")})}),document.querySelectorAll("[data-inbox-reject]").forEach(t=>{t.addEventListener("click",()=>{O(t.dataset.inboxReject||"","rejected")})}),document.querySelectorAll("[data-inbox-del]").forEach(t=>{t.addEventListener("click",async()=>{const a=t.dataset.inboxDel||"";if(!(!a||!confirm("Delete this inbox item?")))try{await c(`/api/memory/inbox/${encodeURIComponent(a)}`,{method:"DELETE"}),await p("memory")}catch(s){d(s.message,"err")}})}),document.querySelectorAll("[data-inbox-edit]").forEach(t=>{t.addEventListener("click",async()=>{const a=t.dataset.inboxEdit||"",s=e.memoryInbox.find(i=>String(i.id)===a);if(!s)return;const n=prompt("Edit memory candidate",s.edited_text||s.candidate_text);if(n!=null)try{await c(`/api/memory/inbox/${encodeURIComponent(a)}`,{method:"PATCH",body:JSON.stringify({edited_text:n,status:s.status})}),await p("memory")}catch(i){d(i.message,"err")}})}),document.getElementById("btn-reload-analytics")?.addEventListener("click",()=>{p("memory")})}async function O(t,a){if(t)try{await c(`/api/memory/inbox/${encodeURIComponent(t)}`,{method:"PATCH",body:JSON.stringify({status:a})}),d(`Memory candidate ${a}.`,"ok"),await p("memory")}catch(s){d(s.message,"err")}}function Ee(){document.getElementById("btn-new-persona")?.addEventListener("click",()=>{e.editingPersona=null,e.personaModal=!0,m()}),document.querySelectorAll("[data-edit-persona]").forEach(t=>{t.addEventListener("click",()=>{const a=Number.parseInt(t.dataset.editPersona||"",10),s=e.personas.find(n=>Number(n.id)===a);s&&(e.editingPersona=s,e.personaModal=!0,m())})}),document.querySelectorAll("[data-default-persona]").forEach(t=>{t.addEventListener("click",async()=>{const a=t.dataset.defaultPersona||"";try{await c(`/api/personas/${encodeURIComponent(a)}`,{method:"PATCH",body:JSON.stringify({is_default:!0})}),await p("personas")}catch(s){d(s.message,"err")}})}),document.querySelectorAll("[data-del-persona]").forEach(t=>{t.addEventListener("click",async()=>{const a=t.dataset.delPersona||"";if(!(!a||!confirm("Delete this persona?")))try{await c(`/api/personas/${encodeURIComponent(a)}`,{method:"DELETE"}),d("Persona deleted.","info"),await p("personas")}catch(s){d(s.message,"err")}})}),document.querySelectorAll("#btn-persona-modal-close,#btn-persona-modal-close2").forEach(t=>{t.addEventListener("click",()=>{e.personaModal=!1,e.editingPersona=null,m()})}),document.getElementById("btn-save-persona")?.addEventListener("click",async()=>{const t=document.getElementById("persona-edit-id")?.value,a=document.getElementById("persona-name")?.value.trim()||"",s=document.getElementById("persona-tags")?.value||"",n=document.getElementById("persona-prompt")?.value.trim()||"",i=!!document.getElementById("persona-default")?.checked;if(!a||!n){d("Name and system prompt are required.","err");return}const l={name:a,system_prompt:n,tags:s.split(",").map(r=>r.trim()).filter(Boolean),is_default:i};try{t?await c(`/api/personas/${encodeURIComponent(t)}`,{method:"PATCH",body:JSON.stringify(l)}):await c("/api/personas",{method:"POST",body:JSON.stringify(l)}),e.personaModal=!1,e.editingPersona=null,await p("personas")}catch(r){d(r.message,"err")}})}function Ie(){document.querySelectorAll("[data-settings-sub]").forEach(t=>{t.addEventListener("click",()=>{e.settingsSubTab=t.dataset.settingsSub||"provider",m()})}),document.getElementById("cfg-model-form")?.addEventListener("submit",async t=>{t.preventDefault();const a=new FormData(t.currentTarget),s={};for(const[n,i]of a.entries())s[n]=String(i||"");try{await c("/api/admin/configs",{method:"POST",body:JSON.stringify({configs:s})}),Object.assign(e.configs,s),e.modelType=s.default_model_provider||e.modelType,d("Settings saved.","ok"),m()}catch(n){d(n.message,"err")}}),document.getElementById("btn-fetch-ollama-models")?.addEventListener("click",async()=>{try{const a=await(await fetch(`${e.configs.ollama_base_url||"http://127.0.0.1:11434"}/api/tags`)).json();e.ollamaModels=(a.models||[]).map(s=>s.name).filter(Boolean),d(`Loaded ${e.ollamaModels.length} Ollama models.`,"ok"),m()}catch(t){d(t.message||"Failed to fetch Ollama models.","err")}}),document.getElementById("btn-settings-export")?.addEventListener("click",async()=>{try{const t=await c("/api/admin/settings/export?include_secrets=false"),a=new Blob([JSON.stringify(t,null,2)],{type:"application/json"}),s=document.createElement("a");s.href=URL.createObjectURL(a),s.download=`ampai-settings-${new Date().toISOString().slice(0,10)}.json`,s.click(),d(`Exported ${t.meta?.exported_key_count||0} keys.`,"ok")}catch(t){d(t.message,"err")}}),document.getElementById("settings-import-file")?.addEventListener("change",async t=>{const a=t.currentTarget.files?.[0];if(a)try{const s=JSON.parse(await a.text()),n=await c("/api/admin/settings/import",{method:"POST",body:JSON.stringify({configs:s.configs||s,dry_run:!1,conflict_strategy:"overwrite"})});d(`Imported ${(n.results||[]).length} settings.`,"ok")}catch(s){d(s.message,"err")}})}function $(t,a,s){document.getElementById(t)?.addEventListener("click",async()=>{try{const n=await c(a,{method:"POST"});d(n?.description||n?.message||s,"ok"),e.tab==="settings"&&await p("settings")}catch(n){d(n.message,"err")}})}function xe(){document.querySelectorAll("[data-accent]").forEach(t=>{t.addEventListener("click",()=>{const a=t.dataset.accent||e.themeAccent;M(a),m()})}),document.getElementById("btn-apply-colour")?.addEventListener("click",()=>{const t=document.getElementById("colour-hex")?.value.trim()||e.themeAccent;if(!/^#[0-9a-f]{6}$/i.test(t)){d("Enter a valid hex colour like #2563eb","err");return}M(t),m()})}function Ae(){document.getElementById("tg-form")?.addEventListener("submit",async t=>{t.preventDefault();const a=new FormData(t.currentTarget);try{await c("/api/admin/integrations/telegram/save",{method:"POST",body:JSON.stringify({bot_token:a.get("telegram_bot_token"),webhook_url:a.get("telegram_webhook_url"),enabled:!0})}),await p("telegram"),d("Telegram settings saved.","ok")}catch(s){d(s.message,"err")}}),$("btn-tg-test","/api/admin/integrations/telegram/test","Telegram test ok."),$("btn-tg-connect","/api/admin/integrations/telegram/connect","Telegram webhook connected."),$("btn-tg-disconnect","/api/admin/integrations/telegram/disconnect","Telegram webhook removed."),$("btn-tg-polling-on","/api/admin/integrations/telegram/enable-polling","Telegram polling enabled."),$("btn-tg-polling-off","/api/admin/integrations/telegram/disable-polling","Telegram polling disabled.")}function Te(){document.querySelectorAll("[data-fetch-models]").forEach(t=>{t.addEventListener("click",async a=>{a.preventDefault();const s=t.dataset.fetchModels||"";if(s){t.textContent="⏳ Loading...",t.disabled=!0;try{const n=await c(`/api/models/fetch/${encodeURIComponent(s)}`);n.models?.length?(e.providerModels[s]=n.models,d(`Loaded ${n.count} models from ${s}`,"ok")):d(`No models found for ${s}`,"info")}catch(n){d(n.message||`Failed to fetch models from ${s}`,"err")}finally{m()}}})}),document.querySelectorAll("[data-select-provider]").forEach(t=>{t.addEventListener("click",()=>{const a=t.dataset.selectProvider||"";a&&(e.modelType=a,e.providerModels[a]?.length||(async()=>{try{const s=await c(`/api/models/fetch/${encodeURIComponent(a)}`);s.models?.length?(e.providerModels[a]=s.models,d(`Loaded ${s.count||s.models.length} models from ${a}`,"ok")):d(`No models found for ${a}`,"info")}catch(s){d(s.message||`Failed to fetch models from ${a}`,"err")}finally{m()}})(),m())})}),document.querySelectorAll("[data-select-model]").forEach(t=>{t.addEventListener("click",()=>{const a=t.dataset.selectModel||"";a&&(e.modelName=a,d(`Model set: ${a}`,"ok"),m())})}),document.getElementById("custom-model-form")?.addEventListener("submit",t=>{t.preventDefault();const s=(document.getElementById("custom-model-input")?.value||"").trim();s&&(e.modelName=s,d(`Model set: ${s}`,"ok"),m())}),document.getElementById("btn-refresh-all-models")?.addEventListener("click",async()=>{d("Fetching models from all configured providers...","info");for(const t of k)if(!(!t.local&&t.keyField&&!e.configs[t.keyField]))try{const a=await c(`/api/models/fetch/${encodeURIComponent(t.value)}`);a.models?.length&&(e.providerModels[t.value]=a.models)}catch{}d("Model refresh complete","ok"),m()})}function Le(){document.getElementById("btn-reload-tasks")?.addEventListener("click",()=>{p("tasks")}),document.querySelectorAll("[data-task-status]").forEach(t=>{t.addEventListener("click",async()=>{const a=t.dataset.taskId||"",s=t.dataset.taskStatus||"";if(!(!a||!s))try{await c(`/api/tasks/${encodeURIComponent(a)}`,{method:"PATCH",body:JSON.stringify({status:s})}),await p("tasks")}catch(n){d(n.message,"err")}})}),document.querySelectorAll("[data-del-task]").forEach(t=>{t.addEventListener("click",async()=>{const a=t.dataset.delTask||"";if(!(!a||!confirm("Delete this task?")))try{await c(`/api/tasks/${encodeURIComponent(a)}`,{method:"DELETE"}),d("Task deleted.","info"),await p("tasks")}catch(s){d(s.message,"err")}})})}function Me(){document.getElementById("btn-reload-browser")?.addEventListener("click",()=>{p("browser")}),document.getElementById("browser-allowlist-form")?.addEventListener("submit",async t=>{t.preventDefault();const a=new FormData(t.currentTarget),s=String(a.get("domain")||"").trim();if(s)try{const n=[...e.browserState.allowlist,s];await c("/api/browser/allowlist",{method:"POST",body:JSON.stringify({domains:n})}),e.browserState.allowlist=n,d(`Domain "${s}" added to allowlist.`,"ok"),m()}catch(n){d(n.message||"Failed to update allowlist","err")}})}function Pe(){document.getElementById("btn-reload-terminal")?.addEventListener("click",()=>{p("terminal")})}function H(){document.querySelectorAll("[data-admin-sub]").forEach(a=>{a.addEventListener("click",()=>{e.adminSubTab=a.dataset.adminSub||"dashboard",m(),H()})}),document.getElementById("btn-reload-admin-stats")?.addEventListener("click",()=>{p("admin")});const t=document.getElementById("admin-health-grid");t&&Array.isArray(e.adminStats?.health_checks)&&(t.innerHTML=e.adminStats.health_checks.map(a=>`
<div class="panel" style="margin:0;padding:10px">
  <div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start">
    <strong style="font-size:.8rem">${o(a.key||"check")}</strong>
    <span class="badge ${a.status==="ok"?"ok":a.status==="warn"?"warn":"bad"}">${o(a.status||"unknown")}</span>
  </div>
  <div class="hint" style="margin-top:6px">${o(a.message||"")}</div>
  ${a.fix_hint?`<div class="hint" style="margin-top:4px;color:var(--yellow)">${o(a.fix_hint)}</div>`:""}
</div>`).join("")),document.getElementById("add-user-form")?.addEventListener("submit",async a=>{a.preventDefault();const s=new FormData(a.currentTarget);try{await c("/api/admin/users",{method:"POST",body:JSON.stringify({username:s.get("username"),password:s.get("password"),role:s.get("role")})}),await p("admin"),d("User created.","ok")}catch(n){d(n.message,"err")}}),document.querySelectorAll("[data-del-user]").forEach(a=>{a.addEventListener("click",async()=>{const s=a.dataset.delUser||"";if(!(!s||!confirm(`Delete user "${s}"?`)))try{await c(`/api/admin/users/${encodeURIComponent(s)}`,{method:"DELETE"}),await p("admin"),d("User deleted.","info")}catch(n){d(n.message,"err")}})}),document.getElementById("agent-settings-form")?.addEventListener("submit",async a=>{a.preventDefault();const s=new FormData(a.currentTarget),n={chat_agent_name:String(s.get("chat_agent_name")||""),chat_agent_avatar_url:String(s.get("chat_agent_avatar_url")||"")};try{await c("/api/admin/configs",{method:"POST",body:JSON.stringify({configs:n})}),Object.assign(e.configs,n),d("Agent settings saved.","ok"),m()}catch(i){d(i.message,"err")}}),document.getElementById("backup-cfg-form")?.addEventListener("submit",async a=>{a.preventDefault();const s=new FormData(a.currentTarget),n={};for(const[i,l]of s.entries())n[i]=String(l||"");try{await c("/api/admin/configs",{method:"POST",body:JSON.stringify({configs:n})}),Object.assign(e.configs,n),d("Backup settings saved.","ok")}catch(i){d(i.message,"err")}}),document.getElementById("btn-run-backup")?.addEventListener("click",async()=>{try{const a=await c("/api/admin/backup",{method:"POST"}),s=document.getElementById("backup-status");s&&(s.textContent=a.message||"Backup started."),d(a.message||"Backup started.","ok")}catch(a){d(a.message,"err")}}),document.getElementById("btn-load-backups")?.addEventListener("click",async()=>{try{const a=await c("/api/admin/update/backups");e.backups=a.backups||[],m()}catch(a){d(a.message,"err")}}),document.getElementById("retention-form")?.addEventListener("submit",async a=>{a.preventDefault();const s=new FormData(a.currentTarget);try{const n={retention_max_age_days:String(s.get("retention_chat_days")||"365"),recall_index_days:String(s.get("recall_index_days")||"365"),logs_days:String(s.get("logs_days")||"30")};await c("/api/admin/configs",{method:"POST",body:JSON.stringify({configs:n})}),Object.assign(e.configs,n);const i=document.getElementById("retention-status");i&&(i.textContent="Retention settings saved."),d("Retention settings saved.","ok")}catch(n){d(n.message,"err")}}),document.getElementById("btn-retention-dry-run")?.addEventListener("click",async()=>{const a=document.getElementById("retention-form");if(!a)return;const s=new FormData(a);try{const n=await c("/api/admin/retention/dry-run",{method:"POST",body:JSON.stringify({max_age_days:Number(s.get("retention_chat_days")||365),archive_only:!0})}),i=document.getElementById("retention-status");i&&(i.textContent=JSON.stringify(n))}catch(n){d(n.message,"err")}})}let S=null;function T(){S!==null&&(clearInterval(S),S=null)}function j(){T(),S=setInterval(async()=>{try{const t=await c("/api/admin/update/status");if(e.updateStatus=t,e.updateLog=t.log_lines||[],m(),t.state==="success"||t.state==="error"){T();const a=document.getElementById("btn-trigger-update");a&&(a.disabled=!1),t.state==="success"?d("Update completed successfully!","ok"):t.state==="error"&&d(t.error||"Update failed.","err")}}catch(t){d(t.message||"Failed to poll update status","err"),T();const a=document.getElementById("btn-trigger-update");a&&(a.disabled=!1)}},3e3)}function Ce(){if(document.getElementById("btn-check-version")?.addEventListener("click",async()=>{try{e.updateVersion=await c("/api/admin/update/version"),await C(),m()}catch(t){d(t.message,"err")}}),document.getElementById("btn-trigger-update")?.addEventListener("click",async()=>{if(!confirm("Pull latest code from GitHub and restart the server?"))return;const t=document.getElementById("btn-trigger-update");try{t&&(t.disabled=!0);const a=await c("/api/admin/update/trigger",{method:"POST"});d(a.message||"Update started.","ok"),e.updateStatus={state:"running",started_at:new Date().toISOString(),finished_at:null,error:null,log_lines:[]},e.updateLog=[],m(),j()}catch(a){d(a.message,"err"),t&&(t.disabled=!1)}}),document.getElementById("btn-poll-update-status")?.addEventListener("click",async()=>{try{const t=await c("/api/admin/update/status");e.updateStatus=t,e.updateLog=t.log_lines||[],m()}catch(t){d(t.message,"err")}}),e.updateStatus?.state==="running"){const t=document.getElementById("btn-trigger-update");t&&(t.disabled=!0),j()}}async function F(){const t=document.getElementById("chat-textarea");if(!t||!e.auth||e.busy)return;const a=t.value.trim();if(!(!a&&!e.attachments.length)){t.value="",t.style.height="auto",h("user",a||"(attachment)"),e.busy=!0,m();try{const s=await c("/api/chat",{method:"POST",body:JSON.stringify({session_id:e.sessionId,message:a||"Please review the attached file.",model_type:e.modelType,model_name:e.modelName||void 0,memory_mode:e.memoryMode,use_web_search:e.useWebSearch,enable_browser_tools:e.enableBrowserTools,enable_terminal_tools:e.enableTerminalTools,attachments:e.attachments})});h("assistant",s.response||s.message||"No response."),e.attachments=[],p("history")}catch(s){h("assistant",`Error: ${s.message||"Chat request failed"}`),setTimeout(()=>{e.busy=!1,m()},Math.min(1e3,500));return}finally{e.busy=!1,m()}}}M(e.themeAccent);m();_();C();e.auth&&p(e.tab);
