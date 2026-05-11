import "./styles.css";

// ── Types ──────────────────────────────────────────────────────────────────
type Health  = { ok: boolean; status: string; detail: string };
type Auth    = { username: string; role: string; token: string };
type Msg     = { role: "user"|"assistant"|"system"; content: string; time: string };
type Session = { session_id: string; category: string; updated_at: string; pinned?: boolean };
type CoreMem = { id: number; fact: string };
type User    = { username: string; role: string };
type Attach  = { filename: string; url: string; type: string; extracted_text: string|null };

// ── Constants ──────────────────────────────────────────────────────────────
const GITHUB  = "pranto48/ampai";
const SK      = "ampai.serverUrl";
const AK      = "ampai.auth";
const SESSK   = "ampai.sessionId";
const DEF_URL = (["tauri.localhost","localhost","127.0.0.1"].includes(window.location.hostname)
  || window.location.protocol.startsWith("tauri"))
  ? "http://127.0.0.1:8001" : window.location.origin;

// ── State ──────────────────────────────────────────────────────────────────
const S = {
  serverUrl: norm(localStorage.getItem(SK) || DEF_URL),
  health: { ok:false, status:"offline", detail:"Not checked" } as Health,
  auth: readAuth(),
  sessionId: localStorage.getItem(SESSK) || newSid(),
  msgs: [] as Msg[],
  tab: "server",
  sessions: [] as Session[],
  sessionSearch: "",
  memories: [] as CoreMem[],
  users: [] as User[],
  updateVersion: null as any,
  updateStatus: null as any,
  updateLog: [] as string[],
  backups: [] as any[],
  tgStatus: null as any,
  configs: {} as Record<string,string>,
  providers: [] as Array<{value:string;label:string}>,
  // chat options
  modelType: "ollama",
  memoryMode: "full",
  useWebSearch: false,
  attachments: [] as Attach[],
  busy: false,
};

// ── Utilities ──────────────────────────────────────────────────────────────
function norm(v:string):string{
  const t=(v||"").trim(); if(!t) return DEF_URL;
  const s=/^https?:\/\//i.test(t)?t:`http://${t}`;
  try{return new URL(s).origin;}catch{return DEF_URL;}
}
function newSid():string{
  const id=(globalThis.crypto?.randomUUID?.()||`d-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  localStorage.setItem(SESSK,id); return id;
}
function readAuth():Auth|null{
  const r=localStorage.getItem(AK); if(!r) return null;
  try{const p=JSON.parse(r)as Auth;return p?.token&&p?.username?p:null;}
  catch{localStorage.removeItem(AK);return null;}
}
function setAuth(a:Auth|null){
  S.auth=a; a?localStorage.setItem(AK,JSON.stringify(a)):localStorage.removeItem(AK);
}
function hdrs(extra?:HeadersInit):Headers{
  const h=new Headers(extra);
  if(!h.has("Content-Type")) h.set("Content-Type","application/json");
  if(S.auth?.token) h.set("Authorization",`Bearer ${S.auth.token}`);
  return h;
}
async function api<T>(path:string,init:RequestInit={}):Promise<T>{
  const ac=new AbortController();
  const t=setTimeout(()=>ac.abort(),25000);
  try{
    const r=await fetch(`${S.serverUrl}${path}`,{...init,headers:hdrs(init.headers),signal:ac.signal});
    const txt=await r.text();
    const d=txt?JSON.parse(txt):{};
    if(!r.ok) throw new Error(d?.detail||d?.message||r.statusText);
    return d as T;
  }finally{clearTimeout(t);}
}
function esc(s:string):string{
  return(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
// simple markdown: code blocks, bold, line breaks
function md(s:string):string{
  return esc(s)
    .replace(/```([\s\S]*?)```/g,"<pre><code>$1</code></pre>")
    .replace(/\*\*(.*?)\*\*/g,"<strong>$1</strong>")
    .replace(/\n/g,"<br />");
}
function toast(msg:string,type:"ok"|"err"|"info"="info"){
  const c=document.getElementById("toast-container");
  if(!c) return;
  const el=document.createElement("div");
  el.className=`toast toast-${type}`;
  el.textContent=msg;
  c.appendChild(el);
  setTimeout(()=>el.remove(),3500);
}
async function checkServer(){
  const cands=Array.from(new Set([S.serverUrl,"http://127.0.0.1:8001","http://127.0.0.1:8000","http://192.168.20.5:8000"]));
  for(const c of cands){
    try{
      const r=await fetch(`${c}/healthz`,{signal:AbortSignal.timeout(5000),headers:{Accept:"application/json"}});
      if(!r.ok) continue;
      const d=await r.json();
      S.serverUrl=c; localStorage.setItem(SK,c);
      S.health={ok:d.status==="ok",status:d.status||"ok",detail:`Connected: ${c}`};
      render(); return;
    }catch{}
  }
  S.health={ok:false,status:"offline",detail:"Cannot reach server"}; render();
}
function pushMsg(role:Msg["role"],content:string){
  S.msgs.push({role,content,time:new Date().toLocaleTimeString()});
}
function switchTab(t:string){S.tab=t;render();void loadTabData(t);}
async function loadTabData(t:string){
  if(!S.auth) return;
  if(t==="history"){try{const d=await api<any>("/api/sessions?limit=60");S.sessions=d.sessions||[];render();}catch{}}
  if(t==="memory"){try{const d=await api<any>("/api/core-memories");S.memories=d.core_memories||[];render();}catch{}}
  if(t==="admin"&&S.auth?.role==="admin"){try{const d=await api<any>("/api/admin/users");S.users=d.users||[];render();}catch{}}
  if(t==="update"&&S.auth?.role==="admin"){try{S.updateVersion=await api<any>("/api/admin/update/version");render();}catch{}}
  if(t==="settings"&&S.auth?.role==="admin"){
    try{
      const[cfg,tg,mo]=await Promise.all([api<any>("/api/admin/configs"),api<any>("/api/admin/integrations/telegram/status"),api<any>("/api/models/options")]);
      S.configs=cfg;S.tgStatus=tg;S.providers=mo.providers||[];
      if(S.configs.default_model_provider) S.modelType=S.configs.default_model_provider;
      render();
    }catch{}
  }
}

// ── Render ─────────────────────────────────────────────────────────────────
function render(){
  const app=document.getElementById("app"); if(!app) return;
  const isAdmin=S.auth?.role==="admin";
  app.innerHTML=`
<div class="app-shell">
  <div class="sidebar">
    <div class="sidebar-brand">
      <div class="brand-icon">&#x1F916;</div>
      <div>
        <div>AmpAI</div>
        <div class="brand-sub">Desktop Client</div>
      </div>
    </div>
    <div class="tab-bar">
      ${tb("server","&#x1F5A5;","Server")}
      ${tb("account","&#x1F464;","Account")}
      ${S.auth?tb("history","&#x1F4AC;","History"):""}
      ${S.auth?tb("settings","&#x2699;","Settings"):""}
      ${S.auth?tb("memory","&#x1F9E0;","Memory"):""}
      ${isAdmin?tb("admin","&#x1F6E1;","Admin"):""}
      ${isAdmin?tb("update","&#x1F504;","Update"):""}
    </div>
    <div class="tab-panels">
      ${tp("server",serverTab())}
      ${tp("account",accountTab())}
      ${S.auth?tp("history",historyTab()):""}
      ${S.auth?tp("settings",settingsTab()):""}
      ${S.auth?tp("memory",memoryTab()):""}
      ${isAdmin?tp("admin",adminTab()):""}
      ${isAdmin?tp("update",updateTab()):""}
    </div>
  </div>
  <div class="chat-shell">
    ${chatTopbar()}
    <div class="chat-messages" id="msgs">${renderMsgs()}</div>
    <div class="chat-input-bar">
      <div class="attach-pills" id="attach-pills">${renderAttachPills()}</div>
      <div class="input-box">
        <textarea id="chat-textarea" class="chat-textarea" rows="1"
          placeholder="${S.auth?"Message AmpAI\u2026 (Enter to send, Shift+Enter for newline)":"Login to chat"}"
          ${S.auth?"":"disabled"}></textarea>
        <label class="attach-btn" title="Attach file" style="cursor:pointer">
          &#x1F4CE;
          <input type="file" id="file-input" multiple style="display:none" />
        </label>
        <button class="chat-send-btn" id="btn-send" ${S.auth&&!S.busy?"":"disabled"}>
          ${S.busy?"&#x23F3;":"Send"}
        </button>
      </div>
    </div>
  </div>
</div>
<div id="toast-container"></div>`;
  document.getElementById("msgs")!.scrollTop=999999;
  bind();
}

function tb(id:string,icon:string,label:string){
  return `<button class="tab-btn${S.tab===id?" active":""}" data-tab="${id}">${icon} ${label}</button>`;
}
function tp(id:string,content:string){
  return `<div class="tab-panel${S.tab===id?" active":""}">${content}</div>`;
}

function chatTopbar():string{
  const provList=S.providers.length?S.providers:[
    {value:"ollama",label:"&#x1F999; Ollama"},
    {value:"openrouter",label:"&#x1F500; OpenRouter"},
    {value:"openai",label:"&#x2728; OpenAI"},
    {value:"gemini",label:"&#x1F31F; Gemini"},
    {value:"anthropic",label:"&#x1F534; Anthropic"},
    {value:"generic",label:"&#x1F3E0; LM Studio"},
    {value:"anythingllm",label:"&#x1F4DA; AnythingLLM"},
  ];
  return `<div class="chat-topbar">
  <div class="chat-topbar-info">
    <div class="chat-topbar-title">
      ${S.sessions.find(s=>s.session_id===S.sessionId)?.category||"AmpAI Chat"}
    </div>
    <div class="chat-topbar-sub">${esc(S.sessionId.slice(0,18))}&hellip;</div>
  </div>
  <select class="chat-topbar-select" id="sel-model">
    ${provList.map(p=>`<option value="${esc(p.value)}"${S.modelType===p.value?" selected":""}>${p.label}</option>`).join("")}
  </select>
  <select class="chat-topbar-select" id="sel-memory">
    <option value="full"${S.memoryMode==="full"?" selected":""}>&#x1F9E0; Full Memory</option>
    <option value="indexed"${S.memoryMode==="indexed"?" selected":""}>&#x26A1; Indexed</option>
    <option value="context_only"${S.memoryMode==="context_only"?" selected":""}>&#x1F4AC; Context Only</option>
    <option value="none"${S.memoryMode==="none"?" selected":""}>&#x26D4; No Memory</option>
  </select>
  <label class="chat-topbar-check">
    <input type="checkbox" id="chk-websearch" ${S.useWebSearch?"checked":""} />
    &#x1F310; Web
  </label>
  <button class="sm" id="btn-new-session">&#x2795; New</button>
</div>`;
}

function renderAttachPills():string{
  return S.attachments.map((a,i)=>`
<div class="attach-pill">
  &#x1F4CE; <span title="${esc(a.filename)}">${esc(a.filename.slice(0,22))}</span>
  <button class="attach-del" data-del-attach="${i}">&#x2715;</button>
</div>`).join("");
}

function renderMsgs():string{
  if(!S.msgs.length) return `
<div class="chat-empty">
  <div class="msg-avatar" style="background:linear-gradient(135deg,#10b981,#3b82f6)">AI</div>
  <div class="chat-empty-bubble">
    <strong>Hello! I'm AmpAI.</strong><br/>
    I remember your conversations and use that memory to give you personalised answers.<br/><br/>
    <span style="color:var(--muted);font-size:.85rem">Start chatting &mdash; every message is saved and indexed for future recall.</span>
  </div>
</div>`;
  const rows=S.msgs.map(m=>{
    const isUser=m.role==="user";
    const initial=S.auth?.username?.[0]?.toUpperCase()||"U";
    return `<div class="msg-row ${m.role}">
  <div class="msg-avatar">${isUser?initial:m.role==="system"?"&#x2139;":"AI"}</div>
  <div>
    ${m.time?`<div class="msg-meta">${m.role} &middot; ${m.time}</div>`:""}
    <div class="msg-bubble" ${isUser?"":`innerHTML="${md(m.content)}"`}>
      ${isUser?esc(m.content):`<span data-md="${esc(m.content)}"></span>`}
    </div>
  </div>
</div>`;
  });
  if(S.busy) rows.push(`<div class="msg-row assistant">
  <div class="msg-avatar">AI</div>
  <div class="msg-bubble"><div class="typing-dots"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div></div>
</div>`);
  return rows.join("");
}

// ── Sidebar tab panels ─────────────────────────────────────────────────────

function serverTab():string{
  const h=S.health;
  return `
<div class="panel">
  <div class="panel-title">Server Connection</div>
  <div class="status-row">
    <span class="badge ${h.ok?"ok":"bad"}">${h.ok?"&#x25CF; Online":"&#x25CF; Offline"}</span>
    <div class="status-detail"><strong>${esc(h.status)}</strong><span>${esc(h.detail)}</span></div>
  </div>
  <form class="stack" id="server-form">
    <label class="field">Server URL<input name="url" value="${esc(S.serverUrl)}" placeholder="http://127.0.0.1:8001"/></label>
    <div class="row">
      <button class="primary" type="submit">Save &amp; Connect</button>
      <button type="button" id="btn-test-server">Test</button>
    </div>
  </form>
  <div class="divider"></div>
  <div class="panel-title">Quick Connect</div>
  <button class="quick-url" data-url="http://127.0.0.1:8001" style="width:100%;margin-bottom:5px">&#x1F4BB; Local (127.0.0.1:8001)</button>
  <button class="quick-url" data-url="http://192.168.20.5:8000" style="width:100%">&#x1F5A7; Docker Server (192.168.20.5:8000)</button>
  <div class="divider"></div>
  <div class="panel-title">Docker Start</div>
  <code>docker compose up --build</code>
</div>`;
}

function accountTab():string{
  if(S.auth) return `
<div class="panel">
  <div class="panel-title">Signed In</div>
  <div class="account-card">
    <div class="account-avatar">${S.auth.username[0].toUpperCase()}</div>
    <div><div class="account-name">${esc(S.auth.username)}</div><div class="account-role">${esc(S.auth.role)}</div></div>
  </div>
  <button id="btn-logout" style="width:100%;margin-top:10px">Logout</button>
</div>`;
  return `
<div class="panel">
  <div class="panel-title">Login</div>
  <form class="stack" id="login-form">
    <label class="field">Username<input name="username" value="admin" autocomplete="username"/></label>
    <label class="field">Password<input name="password" type="password" value="P@ssw0rd" autocomplete="current-password"/></label>
    <button class="primary" type="submit"${S.busy?" disabled":""}>Login</button>
  </form>
</div>`;
}

function historyTab():string{
  const filtered=S.sessions.filter(s=>
    !S.sessionSearch||
    s.session_id.includes(S.sessionSearch)||
    (s.category||"").toLowerCase().includes(S.sessionSearch.toLowerCase())
  );
  return `
<div class="panel" style="padding-bottom:8px">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    Chat History <button id="btn-reload-sessions" class="sm">&#x1F504;</button>
  </div>
  <input id="session-search" placeholder="Search sessions&#x2026;" value="${esc(S.sessionSearch)}" style="margin-top:0"/>
</div>
<div class="sessions-list">
${filtered.length?filtered.map(s=>`
<div class="session-item${S.sessionId===s.session_id?" active":""}" data-sid="${esc(s.session_id)}">
  <div class="session-item-info">
    <div class="session-item-id">${esc(s.category||"Untitled Chat")}</div>
    <div class="session-item-meta">${esc(s.session_id.slice(0,14))} &middot; ${(s.updated_at||"").slice(0,10)}</div>
  </div>
  <button class="session-item-delete sm" data-del-sid="${esc(s.session_id)}" title="Delete">&#x2715;</button>
</div>`).join(""):`<div class="section-empty">${S.sessions.length?"No matches.":"No sessions yet. Start chatting!"}</div>`}
</div>`;
}

function settingsTab():string{
  if(S.auth?.role!=="admin") return `<div class="section-empty">&#x1F6E1; Admin access required.</div>`;
  const cfg=S.configs;const tg=S.tgStatus;
  const provList=S.providers.length?S.providers:[
    {value:"ollama",label:"Ollama (Local)"},
    {value:"openrouter",label:"OpenRouter"},
    {value:"openai",label:"OpenAI"},
    {value:"gemini",label:"Google Gemini"},
    {value:"anthropic",label:"Anthropic"},
    {value:"generic",label:"LM Studio / Generic"},
  ];
  return `
<div class="panel">
  <div class="panel-title">AI Provider &amp; Model</div>
  <form class="stack" id="cfg-model-form">
    <label class="field">Default Provider
      <select name="default_model_provider">
        ${provList.map(p=>`<option value="${esc(p.value)}"${cfg.default_model_provider===p.value?" selected":""}>${esc(p.label)}</option>`).join("")}
      </select>
    </label>
    <label class="field">Default Model<input name="default_model" value="${esc(cfg.default_model||"")}" placeholder="e.g. llama3.2, gpt-4o"/></label>
    <label class="field">Ollama Base URL<input name="ollama_base_url" value="${esc(cfg.ollama_base_url||"")}" placeholder="http://host.docker.internal:11434"/></label>
    <div class="divider"></div>
    <div class="panel-title">API Keys</div>
    <label class="field">OpenRouter Key<input name="openrouter_api_key" value="${esc(cfg.openrouter_api_key||"")}" type="password" placeholder="sk-or-..."/></label>
    <label class="field">OpenAI Key<input name="openai_api_key" value="${esc(cfg.openai_api_key||"")}" type="password" placeholder="sk-..."/></label>
    <label class="field">Gemini Key<input name="gemini_api_key" value="${esc(cfg.gemini_api_key||"")}" type="password"/></label>
    <label class="field">Anthropic Key<input name="anthropic_api_key" value="${esc(cfg.anthropic_api_key||"")}" type="password"/></label>
    <label class="field">LM Studio / Generic URL<input name="generic_base_url" value="${esc(cfg.generic_base_url||"")}" placeholder="http://localhost:1234"/></label>
    <label class="field">Generic API Key<input name="generic_api_key" value="${esc(cfg.generic_api_key||"")}" type="password"/></label>
    <div class="divider"></div>
    <div class="panel-title">Memory Defaults</div>
    <label class="field">Memory Mode<select name="memory_mode">
      ${["full","indexed","context_only","none"].map(m=>`<option${cfg.memory_mode===m?" selected":""}>${m}</option>`).join("")}
    </select></label>
    <label class="field">Memory Top-K<input name="memory_top_k" value="${esc(cfg.memory_top_k||"5")}" type="number" min="1" max="30"/></label>
    <label class="field">SerpAPI Key (Web Search)<input name="serpapi_api_key" value="${esc(cfg.serpapi_api_key||"")}" type="password"/></label>
    <button class="primary" type="submit">&#x1F4BE; Save AI Settings</button>
  </form>
</div>
<div class="panel">
  <div class="panel-title">Telegram Bot ${tg?`<span class="badge ${tg.enabled?"ok":"bad"}" style="float:right;font-size:.69rem">${tg.enabled?"Enabled":"Disabled"}</span>`:""}</div>
  ${tg?`<div class="hint" style="margin-bottom:8px">Token: ${esc(tg.token_masked||"not set")} &nbsp;|&nbsp; Polling: ${tg.polling_enabled?"On":"Off"}</div>`:""}
  <form class="stack" id="tg-form">
    <label class="field">Bot Token<input name="telegram_bot_token" value="${esc(cfg.telegram_bot_token||"")}" type="password" placeholder="123456:ABC-..."/></label>
    <label class="field">Webhook URL<input name="telegram_webhook_url" value="${esc(cfg.telegram_webhook_url||tg?.webhook_url||"")}" placeholder="https://yourdomain.com/webhook"/></label>
    <div class="row">
      <button class="primary" type="submit">&#x1F4BE; Save</button>
      <button type="button" id="btn-tg-test">&#x1F916; Test</button>
    </div>
    <div class="row">
      <button type="button" id="btn-tg-connect">&#x1F517; Set Webhook</button>
      <button type="button" id="btn-tg-disconnect">&#x274C; Remove</button>
    </div>
    <div class="row">
      <button type="button" id="btn-tg-polling-on" class="success">&#x25B6; Enable Polling</button>
      <button type="button" id="btn-tg-polling-off" class="danger">&#x23F9; Disable Polling</button>
    </div>
  </form>
</div>
<div class="panel">
  <div class="panel-title">Settings Backup</div>
  <div class="row">
    <button id="btn-settings-export">&#x1F4E5; Export JSON</button>
    <label style="flex:1;cursor:pointer">
      <button type="button" onclick="this.parentElement.querySelector('input').click()" style="width:100%">&#x1F4E4; Import JSON</button>
      <input type="file" id="settings-import-file" accept=".json" style="display:none"/>
    </label>
  </div>
</div>`;
}

function memoryTab():string{
  return `
<div class="panel">
  <div class="panel-title">Core Memories (${S.memories.length})</div>
  <form class="stack" id="mem-add-form">
    <label class="field">New fact<textarea name="fact" rows="2" placeholder="e.g. User prefers dark mode and concise answers"></textarea></label>
    <button class="primary" type="submit">&#x2795; Add Memory</button>
  </form>
</div>
<div class="panel">
  <div class="panel-title">Recall Search</div>
  <form class="stack" id="recall-form">
    <label class="field">Search past memories &amp; sessions<input name="q" placeholder="e.g. Docker setup..."/></label>
    <button class="primary" type="submit">&#x1F50D; Search</button>
  </form>
  <div id="recall-results" style="margin-top:8px;font-size:.82rem;color:var(--muted)"></div>
</div>
<div class="memory-list">
  ${S.memories.length
    ?S.memories.map(m=>`
<div class="memory-item">
  <div class="memory-item-text">${esc(m.fact)}</div>
  <button class="sm danger" data-del-mem="${m.id}" title="Delete" style="flex-shrink:0;height:24px;padding:0 8px">&#x2715;</button>
</div>`).join("")
    :`<div class="section-empty">No core memories yet.<br/>Add facts the AI should always remember.</div>`}
</div>
<div style="padding-top:10px"><button id="btn-reload-memory" style="width:100%">&#x1F504; Refresh</button></div>`;
}

function adminTab():string{
  return `
<div class="panel">
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
${S.users.map(u=>`
<div class="user-item">
  <div class="user-item-info">
    <div class="user-item-name">${esc(u.username)}</div>
    <div class="user-item-role">${esc(u.role)}</div>
  </div>
  ${u.username!==S.auth?.username
    ?`<button class="danger sm" data-del-user="${esc(u.username)}">&#x1F5D1; Delete</button>`
    :`<span class="badge ok" style="font-size:.69rem">You</span>`}
</div>`).join("")}
</div>`;
}

function updateTab():string{
  const v=S.updateVersion;const st=S.updateStatus;
  return `
<div class="panel">
  <div class="panel-title">Docker Code Update</div>
  ${v?`<div class="status-row" style="margin-bottom:10px">
    <span class="badge ${v.up_to_date?"ok":"warn"}">${v.up_to_date?"&#x2714; Up to date":"&#x26A0; Update available"}</span>
    <div class="status-detail">
      <strong>Current: ${esc(v.current_commit||"unknown")}</strong>
      <span>Latest: ${esc(v.latest_commit||"unknown")}</span>
    </div>
  </div>`:""}
  <div class="row">
    <button id="btn-check-version">&#x1F50D; Check</button>
    <button class="primary" id="btn-trigger-update">&#x2B07; Pull Update</button>
    <button id="btn-poll-update-status" class="sm">&#x1F504; Status</button>
  </div>
  ${st?`<div class="status-row" style="margin-top:10px">
    <span class="badge ${st.state==="success"?"ok":st.state==="running"?"warn":"bad"}">${esc(st.state)}</span>
    <div class="status-detail"><strong>Update ${esc(st.state)}</strong><span>${esc(st.finished_at||st.started_at||"")}</span></div>
  </div>`:""}
  ${S.updateLog.length?`<div class="update-log">${esc(S.updateLog.join("\n"))}</div>`:""}
</div>
<div class="panel">
  <div class="panel-title">Code Backups</div>
  <button id="btn-load-backups" style="width:100%;margin-bottom:8px">&#x1F4C2; Load Backups</button>
  <div>
    ${S.backups.map(b=>`
<div class="backup-item">
  <div class="backup-item-info">
    <div class="backup-item-name">${esc(b.name)}</div>
    <div class="backup-item-meta">Commit: ${esc(b.commit)} &middot; ${Math.round((b.size_bytes||0)/1024)} KB</div>
  </div>
  <button class="danger sm" data-del-backup="${esc(b.name)}">&#x2715;</button>
</div>`).join("")}
  </div>
</div>`;
}

// ── Event Binding ──────────────────────────────────────────────────────────
function bind(){
  // Tabs
  document.querySelectorAll<HTMLButtonElement>(".tab-btn[data-tab]").forEach(b=>{
    b.addEventListener("click",()=>switchTab(b.dataset.tab!));
  });
  // Quick server buttons
  document.querySelectorAll<HTMLButtonElement>(".quick-url[data-url]").forEach(b=>{
    b.addEventListener("click",()=>{S.serverUrl=norm(b.dataset.url!);localStorage.setItem(SK,S.serverUrl);void checkServer();});
  });
  // Server form
  document.getElementById("server-form")?.addEventListener("submit",async e=>{
    e.preventDefault();
    const f=new FormData(e.currentTarget as HTMLFormElement);
    S.serverUrl=norm(f.get("url") as string);localStorage.setItem(SK,S.serverUrl);
    await checkServer();
  });
  document.getElementById("btn-test-server")?.addEventListener("click",()=>void checkServer());

  // Login
  document.getElementById("login-form")?.addEventListener("submit",async e=>{
    e.preventDefault();
    const f=new FormData(e.currentTarget as HTMLFormElement);
    S.busy=true;render();
    try{
      const r=await api<Auth>("/api/auth/login",{method:"POST",body:JSON.stringify({username:f.get("username"),password:f.get("password"),remember_me:true})});
      setAuth(r);pushMsg("system",`Signed in as ${r.username} (${r.role})`);
      S.tab="history";
    }catch(err:any){pushMsg("system",err.message||"Login failed");}
    S.busy=false;render();
    if(S.auth) void loadTabData(S.tab);
  });
  // Logout
  document.getElementById("btn-logout")?.addEventListener("click",()=>{
    setAuth(null);S.tab="account";S.sessions=[];S.memories=[];S.users=[];render();
  });

  // Chat topbar selectors
  document.getElementById("sel-model")?.addEventListener("change",e=>{
    S.modelType=(e.currentTarget as HTMLSelectElement).value;
  });
  document.getElementById("sel-memory")?.addEventListener("change",e=>{
    S.memoryMode=(e.currentTarget as HTMLSelectElement).value;
  });
  document.getElementById("chk-websearch")?.addEventListener("change",e=>{
    S.useWebSearch=(e.currentTarget as HTMLInputElement).checked;
  });

  // New session
  document.getElementById("btn-new-session")?.addEventListener("click",()=>{
    S.sessionId=newSid();S.msgs=[];S.attachments=[];render();
  });

  // File attachment
  document.getElementById("file-input")?.addEventListener("change",async(e)=>{
    const files=Array.from((e.currentTarget as HTMLInputElement).files||[]);
    if(!files.length) return;
    for(const file of files){
      const formData=new FormData();formData.append("file",file);
      try{
        const r=await fetch(`${S.serverUrl}/api/upload?session_id=${encodeURIComponent(S.sessionId)}`,
          {method:"POST",headers:{Authorization:`Bearer ${S.auth?.token||""}`},body:formData});
        if(r.ok){const d=await r.json();S.attachments.push(d);toast(`Attached: ${file.name}`,"ok");}
        else toast(`Upload failed: ${file.name}`,"err");
      }catch(err:any){toast(err.message,"err");}
    }
    // re-render attach pills only
    const ap=document.getElementById("attach-pills");
    if(ap) ap.innerHTML=renderAttachPills();
    bindAttachDels();
    (e.currentTarget as HTMLInputElement).value="";
  });

  bindAttachDels();

  // Chat send
  const ta=document.getElementById("chat-textarea") as HTMLTextAreaElement|null;
  ta?.addEventListener("keydown",(e:KeyboardEvent)=>{
    if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();void doSend();}
  });
  ta?.addEventListener("input",()=>{
    if(ta){ta.style.height="auto";ta.style.height=Math.min(ta.scrollHeight,130)+"px";}
  });
  document.getElementById("btn-send")?.addEventListener("click",()=>void doSend());

  // Session search
  document.getElementById("session-search")?.addEventListener("input",e=>{
    S.sessionSearch=(e.currentTarget as HTMLInputElement).value;
    // re-render just the list
    const sl=document.querySelector(".sessions-list");
    if(sl){
      const filtered=S.sessions.filter(s=>
        !S.sessionSearch||
        s.session_id.includes(S.sessionSearch)||
        (s.category||"").toLowerCase().includes(S.sessionSearch.toLowerCase())
      );
      sl.innerHTML=filtered.length?filtered.map(s=>`
<div class="session-item${S.sessionId===s.session_id?" active":""}" data-sid="${esc(s.session_id)}">
  <div class="session-item-info">
    <div class="session-item-id">${esc(s.category||"Untitled Chat")}</div>
    <div class="session-item-meta">${esc(s.session_id.slice(0,14))} &middot; ${(s.updated_at||"").slice(0,10)}</div>
  </div>
  <button class="session-item-delete sm" data-del-sid="${esc(s.session_id)}" title="Delete">&#x2715;</button>
</div>`).join(""):`<div class="section-empty">No matches.</div>`;
      bindSessionItems();
    }
  });

  // History - reload
  document.getElementById("btn-reload-sessions")?.addEventListener("click",()=>void loadTabData("history"));
  bindSessionItems();

  // Settings - AI config save
  document.getElementById("cfg-model-form")?.addEventListener("submit",async e=>{
    e.preventDefault();
    const f=new FormData(e.currentTarget as HTMLFormElement);
    const configs:Record<string,string>={};
    for(const[k,v] of f.entries()) if(v) configs[k]=v as string;
    try{
      await api("/api/admin/configs",{method:"POST",body:JSON.stringify({configs})});
      S.configs={...S.configs,...configs};
      if(configs.default_model_provider) S.modelType=configs.default_model_provider;
      toast("AI settings saved.","ok");
    }catch(err:any){toast("Save failed: "+err.message,"err");}
    render();
  });

  // Telegram
  document.getElementById("tg-form")?.addEventListener("submit",async e=>{
    e.preventDefault();
    const f=new FormData(e.currentTarget as HTMLFormElement);
    const token=f.get("telegram_bot_token") as string;
    const webhookUrl=f.get("telegram_webhook_url") as string;
    try{
      await api("/api/admin/integrations/telegram/save",{method:"POST",body:JSON.stringify({bot_token:token,webhook_url:webhookUrl,enabled:true})});
      const cfgs:Record<string,string>={};
      if(token) cfgs.telegram_bot_token=token;
      if(webhookUrl) cfgs.telegram_webhook_url=webhookUrl;
      if(Object.keys(cfgs).length) await api("/api/admin/configs",{method:"POST",body:JSON.stringify({configs:cfgs})});
      S.tgStatus=await api<any>("/api/admin/integrations/telegram/status");
      toast("Telegram settings saved.","ok");
    }catch(err:any){toast("Telegram save failed: "+err.message,"err");}
    render();
  });
  document.getElementById("btn-tg-test")?.addEventListener("click",async()=>{
    try{const r=await api<any>("/api/admin/integrations/telegram/test",{method:"POST"});toast(`Bot OK: @${r.bot_username}`,"ok");}
    catch(err:any){toast("Telegram test failed: "+err.message,"err");}
  });
  document.getElementById("btn-tg-connect")?.addEventListener("click",async()=>{
    try{const r=await api<any>("/api/admin/integrations/telegram/connect",{method:"POST"});toast(r.description||"Webhook connected.","ok");}
    catch(err:any){toast(err.message,"err");}
  });
  document.getElementById("btn-tg-disconnect")?.addEventListener("click",async()=>{
    try{const r=await api<any>("/api/admin/integrations/telegram/disconnect",{method:"POST"});toast(r.description||"Webhook removed.","info");}
    catch(err:any){toast(err.message,"err");}
  });
  document.getElementById("btn-tg-polling-on")?.addEventListener("click",async()=>{
    try{await api("/api/admin/integrations/telegram/enable-polling",{method:"POST"});S.tgStatus=await api<any>("/api/admin/integrations/telegram/status");toast("Polling enabled.","ok");}
    catch(err:any){toast(err.message,"err");}
    render();
  });
  document.getElementById("btn-tg-polling-off")?.addEventListener("click",async()=>{
    try{await api("/api/admin/integrations/telegram/disable-polling",{method:"POST"});S.tgStatus=await api<any>("/api/admin/integrations/telegram/status");toast("Polling disabled.","info");}
    catch(err:any){toast(err.message,"err");}
    render();
  });

  // Settings export/import
  document.getElementById("btn-settings-export")?.addEventListener("click",async()=>{
    try{
      const r=await api<any>("/api/admin/settings/export?include_secrets=false");
      const blob=new Blob([JSON.stringify(r,null,2)],{type:"application/json"});
      const a=document.createElement("a");a.href=URL.createObjectURL(blob);
      a.download=`ampai-settings-${new Date().toISOString().slice(0,10)}.json`;a.click();
      toast(`Exported ${r.meta?.exported_key_count||"?"} keys.`,"ok");
    }catch(err:any){toast("Export failed: "+err.message,"err");}
  });
  document.getElementById("settings-import-file")?.addEventListener("change",async e=>{
    const file=(e.currentTarget as HTMLInputElement).files?.[0];if(!file) return;
    try{
      const payload=JSON.parse(await file.text());
      const r=await api<any>("/api/admin/settings/import",{method:"POST",body:JSON.stringify({configs:payload.configs||payload,dry_run:false,conflict_strategy:"overwrite"})});
      toast(`Import complete: ${(r.results||[]).length} keys.`,"ok");
    }catch(err:any){toast("Import failed: "+err.message,"err");}
  });

  // Memory add
  document.getElementById("mem-add-form")?.addEventListener("submit",async e=>{
    e.preventDefault();
    const f=new FormData(e.currentTarget as HTMLFormElement);
    const fact=(f.get("fact") as string||"").trim();if(!fact) return;
    try{
      await api("/api/core-memories",{method:"POST",body:JSON.stringify({fact})});
      toast("Memory added.","ok");
      (e.currentTarget as HTMLFormElement).reset();
      const d=await api<any>("/api/core-memories");S.memories=d.core_memories||[];
    }catch(err:any){toast("Add memory failed: "+err.message,"err");}
    render();
  });
  document.getElementById("btn-reload-memory")?.addEventListener("click",()=>void loadTabData("memory"));
  document.querySelectorAll<HTMLButtonElement>("[data-del-mem]").forEach(b=>{
    b.addEventListener("click",async()=>{
      const id=b.dataset.delMem!;if(!confirm("Delete this memory?")) return;
      try{await api(`/api/admin/core-memories/${id}`,{method:"DELETE"});S.memories=S.memories.filter(m=>String(m.id)!==id);toast("Memory deleted.","info");}
      catch(err:any){toast(err.message,"err");}
      render();
    });
  });

  // Recall search
  document.getElementById("recall-form")?.addEventListener("submit",async e=>{
    e.preventDefault();
    const f=new FormData(e.currentTarget as HTMLFormElement);
    const q=(f.get("q") as string||"").trim();if(!q) return;
    const el=document.getElementById("recall-results");
    if(el) el.textContent="Searching…";
    try{
      const r=await api<any>("/api/recall/search",{method:"POST",body:JSON.stringify({q,session_id:"",limit:10})});
      if(el) el.innerHTML=r.summary?`<div style="white-space:pre-wrap">${esc(r.summary)}</div>`:`<div style="color:var(--muted)">No results found.</div>`;
    }catch(err:any){if(el) el.textContent="Recall search failed: "+err.message;}
  });

  // Admin add user
  document.getElementById("add-user-form")?.addEventListener("submit",async e=>{
    e.preventDefault();
    const f=new FormData(e.currentTarget as HTMLFormElement);
    try{
      await api("/api/admin/users",{method:"POST",body:JSON.stringify({username:f.get("username"),password:f.get("password"),role:f.get("role")})});
      toast(`User "${f.get("username")}" created.`,"ok");
      (e.currentTarget as HTMLFormElement).reset();
      const d=await api<any>("/api/admin/users");S.users=d.users||[];
    }catch(err:any){toast("Create user failed: "+err.message,"err");}
    render();
  });
  document.querySelectorAll<HTMLButtonElement>("[data-del-user]").forEach(b=>{
    b.addEventListener("click",async()=>{
      const uname=b.dataset.delUser!;if(!confirm(`Delete user "${uname}"?`)) return;
      try{await api(`/api/admin/users/${uname}`,{method:"DELETE"});S.users=S.users.filter(u=>u.username!==uname);toast(`User "${uname}" deleted.`,"info");}
      catch(err:any){toast(err.message,"err");}
      render();
    });
  });

  // Update
  document.getElementById("btn-check-version")?.addEventListener("click",async()=>{
    try{S.updateVersion=await api<any>("/api/admin/update/version");toast("Version info loaded.","info");}
    catch(err:any){toast(err.message,"err");}
    render();
  });
  document.getElementById("btn-trigger-update")?.addEventListener("click",async()=>{
    if(!confirm("Pull latest code from GitHub and restart?")) return;
    try{const r=await api<any>("/api/admin/update/trigger",{method:"POST"});toast(r.message||"Update started.","ok");}
    catch(err:any){toast(err.message,"err");}
    render();
  });
  document.getElementById("btn-poll-update-status")?.addEventListener("click",async()=>{
    try{const r=await api<any>("/api/admin/update/status");S.updateStatus=r;S.updateLog=r.log_lines||[];toast("Status refreshed.","info");}
    catch(err:any){toast(err.message,"err");}
    render();
  });
  document.getElementById("btn-load-backups")?.addEventListener("click",async()=>{
    try{const r=await api<any>("/api/admin/update/backups");S.backups=r.backups||[];toast(`${S.backups.length} backup(s) loaded.`,"info");}
    catch(err:any){toast(err.message,"err");}
    render();
  });
  document.querySelectorAll<HTMLButtonElement>("[data-del-backup]").forEach(b=>{
    b.addEventListener("click",async()=>{
      const name=b.dataset.delBackup!;if(!confirm(`Delete backup "${name}"?`)) return;
      try{await api(`/api/admin/update/backups/${name}`,{method:"DELETE"});S.backups=S.backups.filter(bk=>bk.name!==name);toast(`Backup "${name}" deleted.`,"info");}
      catch(err:any){toast(err.message,"err");}
      render();
    });
  });

  // apply md to AI messages
  document.querySelectorAll<HTMLElement>("[data-md]").forEach(el=>{
    const raw=el.dataset.md||"";
    el.outerHTML=`<div>${md(raw)}</div>`;
  });
}

function bindAttachDels(){
  document.querySelectorAll<HTMLButtonElement>("[data-del-attach]").forEach(b=>{
    b.addEventListener("click",()=>{
      const i=parseInt(b.dataset.delAttach!);
      S.attachments.splice(i,1);
      const ap=document.getElementById("attach-pills");
      if(ap){ap.innerHTML=renderAttachPills();bindAttachDels();}
    });
  });
}

function bindSessionItems(){
  document.querySelectorAll<HTMLElement>(".session-item[data-sid]").forEach(el=>{
    el.addEventListener("click",async ev=>{
      if((ev.target as HTMLElement).closest("[data-del-sid]")) return;
      const sid=el.dataset.sid!;S.sessionId=sid;
      try{
        const r=await api<any>(`/api/history/${sid}`);
        S.msgs=(r.messages||[]).map((m:any)=>({
          role:m.type==="human"?"user":"assistant",content:m.content||"",time:""
        }));
      }catch(err:any){pushMsg("system","Failed to load history: "+err.message);}
      localStorage.setItem(SESSK,sid);
      S.tab="server";render();
    });
  });
  document.querySelectorAll<HTMLButtonElement>("[data-del-sid]").forEach(b=>{
    b.addEventListener("click",async ev=>{
      ev.stopPropagation();
      const sid=b.dataset.delSid!;if(!confirm(`Delete session?`)) return;
      try{
        await api(`/api/sessions/${sid}`,{method:"DELETE"});
        S.sessions=S.sessions.filter(s=>s.session_id!==sid);
        if(S.sessionId===sid){S.sessionId=newSid();S.msgs=[];}
        toast("Session deleted.","info");render();
      }catch(err:any){toast(err.message,"err");}
    });
  });
}

async function doSend(){
  const ta=document.getElementById("chat-textarea") as HTMLTextAreaElement|null;
  if(!ta) return;
  const msg=ta.value.trim();
  if((!msg&&S.attachments.length===0)||!S.auth||S.busy) return;
  ta.value="";ta.style.height="auto";
  pushMsg("user",msg||"(attachment)");
  S.busy=true;render();
  try{
    const payload:any={
      session_id:S.sessionId,message:msg||"Please review the attached file.",
      model_type:S.modelType,memory_mode:S.memoryMode,
      use_web_search:S.useWebSearch,attachments:S.attachments,
    };
    const r=await api<any>("/api/chat",{method:"POST",body:JSON.stringify(payload)});
    pushMsg("assistant",r.response||r.message||"No response.");
    S.attachments=[];
    // refresh sessions in background
    void (async()=>{try{const d=await api<any>("/api/sessions?limit=60");S.sessions=d.sessions||[];}catch{}})();
  }catch(err:any){pushMsg("assistant",`⚠️ ${err.message||"Chat failed"}`);}
  S.busy=false;render();
}

// ── Init ───────────────────────────────────────────────────────────────────
render();
void checkServer();
if(S.auth) void loadTabData(S.tab);
