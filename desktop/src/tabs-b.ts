import{S}from"./state";
import{esc,fmtRel}from"./tabs-a";

export function memoryTab():string{
  const subBtns=["core","inbox","analytics"].map(t=>`<button class="sub-tab-btn${S.memSubTab===t?" active":""}" data-mem-sub="${t}">${t==="core"?"🧠 Core":t==="inbox"?"📬 Inbox":"📊 Analytics"}</button>`).join("");
  let content="";
  if(S.memSubTab==="core"){
    content=`<div class="panel">
  <div class="panel-title">Core Memories (${S.memories.length})</div>
  <form class="stack" id="mem-add-form">
    <label class="field">New fact<textarea name="fact" rows="2" placeholder="e.g. User prefers dark mode">${S.editingMemId!=null?esc(S.editingMemFact):""}</textarea></label>
    <button class="primary" type="submit">➕ Add Memory</button>
  </form>
</div>
<div class="memory-list">
${S.memories.length?S.memories.map(m=>`<div class="memory-item${S.editingMemId===m.id?" editing":""}">
  ${S.editingMemId===m.id
    ?`<div style="flex:1"><textarea id="mem-edit-${m.id}" rows="2" style="width:100%;font-size:.82rem">${esc(m.fact)}</textarea>
       <div style="display:flex;gap:5px;margin-top:5px">
         <button class="success sm" data-save-mem="${m.id}">💾 Save</button>
         <button class="sm" data-cancel-edit-mem="1">Cancel</button>
       </div></div>`
    :`<div class="memory-item-text">${esc(m.fact)}</div>
     <div class="memory-item-actions">
       <button class="sm" data-edit-mem="${m.id}" title="Edit">✏️</button>
       <button class="sm danger" data-del-mem="${m.id}" title="Delete">✕</button>
     </div>`}
</div>`).join(""):`<div class="section-empty">No core memories yet.<br/>Add facts the AI should always remember.</div>`}
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
</div>`;
  }
  else if(S.memSubTab==="inbox"){
    const items=S.memoryInbox;
    content=`<div class="panel">
  <div class="panel-title">Memory Inbox — AI Candidates</div>
  <div class="row" style="margin-bottom:8px">
    <select id="inbox-status-filter">
      <option value="pending"${S.inboxStatusFilter==="pending"?" selected":""}>Pending</option>
      <option value="approved"${S.inboxStatusFilter==="approved"?" selected":""}>Approved</option>
      <option value="rejected"${S.inboxStatusFilter==="rejected"?" selected":""}>Rejected</option>
    </select>
    <button id="btn-reload-inbox" class="sm">🔄</button>
  </div>
</div>
<div>
${items.length?items.map(i=>`<div class="inbox-item">
  <div class="inbox-item-meta">
    <span class="badge ${i.status==="approved"?"ok":i.status==="rejected"?"bad":"warn"}">${i.status}</span>
    <span>Confidence: ${(i.confidence||0).toFixed(2)}</span>
    <span>${fmtRel(i.created_at)}</span>
  </div>
  <div class="inbox-item-text">${esc(i.edited_text||i.candidate_text)}</div>
  <div class="inbox-item-actions">
    <button class="success sm" data-inbox-approve="${i.id}">✓ Approve</button>
    <button class="danger sm" data-inbox-reject="${i.id}">✕ Reject</button>
    <button class="sm" data-inbox-edit="${i.id}">✏️ Edit</button>
    <button class="danger sm" data-inbox-del="${i.id}">🗑</button>
  </div>
</div>`).join(""):`<div class="section-empty">No ${S.inboxStatusFilter} candidates.</div>`}
</div>`;
  }
  else{
    const a=S.memoryAnalytics;
    const kpis=a?.kpis||{};
    const writes=a?.memory_writes_per_day||[];
    const maxW=writes.length?Math.max(...writes.map((r:any)=>r.count||0),1):1;
    content=`<div class="kpi-grid">
  <div class="kpi-card"><div class="kpi-value">${kpis.memory_writes_total??0}</div><div class="kpi-label">Memory Writes</div></div>
  <div class="kpi-card"><div class="kpi-value">${kpis.retrieval_hits_total??0}</div><div class="kpi-label">Retrieval Hits</div></div>
  <div class="kpi-card"><div class="kpi-value">${kpis.stale_memories_count??0}</div><div class="kpi-label">Stale Memories</div></div>
  <div class="kpi-card"><div class="kpi-value" style="font-size:1rem">${a?.top_categories?.[0]?.category||"—"}</div><div class="kpi-label">Top Category</div></div>
</div>
<div class="panel">
  <div class="panel-title">Writes per Day</div>
  ${writes.slice(-10).map((r:any)=>`<div class="trend-bar-row">
    <div class="trend-bar-label">${(r.day||"").slice(5)}</div>
    <div class="trend-bar-track"><div class="trend-bar-fill" style="width:${Math.round(((r.count||0)/maxW)*100)}%"></div></div>
    <div class="trend-bar-val">${r.count||0}</div>
  </div>`).join("")||`<div class="section-empty">No data.</div>`}
</div>
<button id="btn-reload-analytics" style="width:100%">🔄 Refresh Analytics</button>`;
  }
  return`<div class="sub-tabs">${subBtns}</div>${content}`;
}

export function personasTab():string{
  return`<div class="panel">
  <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">
    AI Personas <button class="sm primary" id="btn-new-persona">➕ New</button>
  </div>
  <div class="hint" style="margin-bottom:8px">Personas define AI personality &amp; system prompts. Set one as default.</div>
</div>
<div>
${S.personas.length?S.personas.map(p=>`<div class="persona-card">
  <div class="persona-card-header">
    <div class="persona-card-name">${esc(p.name)}</div>
    ${p.is_default?`<span class="badge ok">Default</span>`:""}
  </div>
  ${p.tags?.length?`<div style="margin-bottom:4px">${p.tags.map(t=>`<span class="badge info" style="margin-right:3px;font-size:.65rem">${esc(t)}</span>`).join("")}</div>`:""}
  <div class="persona-card-prompt">${esc((p.system_prompt||"").slice(0,200))}</div>
  <div class="persona-card-actions">
    <button class="sm" data-edit-persona="${esc(p.id)}">✏️ Edit</button>
    <button class="sm success" data-default-persona="${esc(p.id)}">⭐ Set Default</button>
    <button class="sm danger" data-del-persona="${esc(p.id)}">🗑 Delete</button>
  </div>
</div>`).join(""):`<div class="section-empty">No personas yet.<br/>Create one to customize AI behaviour.</div>`}
</div>
${S.personaModal?personaModal():""}`;
}

function personaModal():string{
  const p=S.editingPersona;
  return`<div class="modal-overlay" id="persona-modal-overlay">
  <div class="modal-box">
    <div class="modal-title">${p?"Edit Persona":"New Persona"}<button class="modal-close" id="btn-persona-modal-close">✕</button></div>
    <div class="stack">
      <label class="field">Name<input id="persona-name" value="${esc(p?.name||"")}" placeholder="e.g. Helpful Assistant"/></label>
      <label class="field">Tags (comma-separated)<input id="persona-tags" value="${esc((p?.tags||[]).join(", "))}" placeholder="helpful, concise"/></label>
      <label class="field">System Prompt<textarea id="persona-prompt" rows="5" placeholder="You are a helpful assistant…">${esc(p?.system_prompt||"")}</textarea></label>
      <label class="field" style="flex-direction:row;align-items:center;gap:8px">
        <input type="checkbox" id="persona-default" style="width:auto" ${p?.is_default?"checked":""}/> Set as default
      </label>
      <input type="hidden" id="persona-edit-id" value="${esc(p?.id||"")}"/>
      <div class="row">
        <button class="primary" id="btn-save-persona">💾 Save</button>
        <button id="btn-persona-modal-close2">Cancel</button>
      </div>
    </div>
  </div>
</div>`;
}
