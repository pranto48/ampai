import{S,ALL_PROVIDERS,ACCENT_COLORS,APP_VERSION,GITHUB}from"./state";
export function esc(s:string):string{return(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}
export function md(s:string):string{return esc(s).replace(/```([\s\S]*?)```/g,"<pre><code>$1</code></pre>").replace(/\*\*(.*?)\*\*/g,"<strong>$1</strong>").replace(/\n/g,"<br/>");}
export function fmtRel(iso:string):string{if(!iso)return"—";const d=new Date(iso),diff=Date.now()-d.getTime(),m=Math.floor(diff/60000);if(m<1)return"just now";if(m<60)return`${m}m ago`;const h=Math.floor(m/60);if(h<24)return`${h}h ago`;return`${Math.floor(h/24)}d ago`;}

export function serverTab():string{
  const h=S.health;
  return`<div class="panel">
  <div class="panel-title">Server Connection</div>
  <div class="status-row">
    <span class="badge ${h.ok?"ok":"bad"}">${h.ok?"● Online":"● Offline"}</span>
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
  <button class="quick-url" data-url="http://127.0.0.1:8001" style="width:100%;margin-bottom:5px">💻 Local (127.0.0.1:8001)</button>
  <button class="quick-url" data-url="http://192.168.20.5:8000" style="width:100%">🖧 Docker (192.168.20.5:8000)</button>
  <div class="divider"></div>
  <div class="panel-title">Docker Start</div>
  <code>docker compose up --build</code>
</div>`;
}

export function accountTab():string{
  if(S.auth)return`<div class="panel">
  <div class="panel-title">Signed In</div>
  <div class="account-card">
    <div class="account-avatar">${S.auth.username[0].toUpperCase()}</div>
    <div><div class="account-name">${esc(S.auth.username)}</div><div class="account-role">${esc(S.auth.role)}</div></div>
  </div>
  <button id="btn-logout" style="width:100%;margin-top:10px">Logout</button>
</div>`;
  return`<div class="panel">
  <div class="panel-title">Login</div>
  <form class="stack" id="login-form">
    <label class="field">Username<input name="username" value="admin" autocomplete="username"/></label>
    <label class="field">Password<input name="password" type="password" value="P@ssw0rd" autocomplete="current-password"/></label>
    <button class="primary" type="submit"${S.busy?" disabled":""}>Login</button>
  </form>
</div>`;
}

export function historyTab():string{
  const cats=[...new Set(S.sessions.map(s=>s.category||"Uncategorized"))];
  const filtered=S.sessions.filter(s=>{
    const matchQ=!S.sessionSearch||s.session_id.includes(S.sessionSearch)||(s.category||"").toLowerCase().includes(S.sessionSearch.toLowerCase());
    const matchC=!S.sessionCategoryFilter||s.category===S.sessionCategoryFilter;
    return matchQ&&matchC;
  });
  return`<div class="panel" style="padding-bottom:8px">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    Chat History <button id="btn-reload-sessions" class="sm">🔄</button>
  </div>
  <input id="session-search" placeholder="Search sessions…" value="${esc(S.sessionSearch)}" style="margin-bottom:6px"/>
  <div class="cat-filter">
    <span class="cat-chip${!S.sessionCategoryFilter?" active":""}" data-cat="">All</span>
    ${cats.map(c=>`<span class="cat-chip${S.sessionCategoryFilter===c?" active":""}" data-cat="${esc(c)}">${esc(c)}</span>`).join("")}
  </div>
</div>
<div class="sessions-list">
${filtered.length?filtered.map(s=>`<div class="session-item${S.sessionId===s.session_id?" active":""}${s.pinned?" pinned":""}" data-sid="${esc(s.session_id)}">
  <div class="session-item-info">
    <div class="session-item-id">${esc(s.category||"Untitled Chat")}</div>
    <div class="session-item-meta">${esc(s.session_id.slice(0,14))} · ${(s.updated_at||"").slice(0,10)}</div>
  </div>
  <div class="session-item-actions">
    <button class="sm" data-pin-sid="${esc(s.session_id)}" title="${s.pinned?"Unpin":"Pin"}">${s.pinned?"📌":"📍"}</button>
    <button class="sm" data-archive-sid="${esc(s.session_id)}" title="Archive">🗃️</button>
    <button class="sm danger" data-del-sid="${esc(s.session_id)}" title="Delete">✕</button>
  </div>
</div>`).join(""):`<div class="section-empty">${S.sessions.length?"No matches.":"No sessions yet."}</div>`}
</div>`;
}
