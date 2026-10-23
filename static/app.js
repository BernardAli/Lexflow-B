/* LexFlow AI prototype — zero external JavaScript dependencies. */
'use strict';
const app = document.querySelector('#app');
const modalRoot = document.querySelector('#modal-root');
const toastRoot = document.querySelector('#toast-root');
let S = { user: null, csrf: '', config: null, route: '/dashboard', matter: null,
          search: '', statusFilter: '', mobileNav: false, renderKey: 0, auditEvents: [] };
const SAMPLE = `VERTRAULICH? NEIN — SYNTHETISCHE TESTDATEN\nKaufvertragsvorbereitung\nKäufer: Clara Hoffmann\nVerkäufer: Daniel Richter\nKaufpreis: 695.000,00 €\nObjektadresse: Rosenstraße 20, 80331 München\nGrundbuch: München Blatt 9912\nKäufer E-Mail: clara.hoffmann@example.test\nBeurkundungstermin: 22.12.2026`;

function esc(v) { return String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c])); }
function trim(v,n=180) { const x=String(v??'');return x.length>n?x.slice(0,n-1)+'…':x; }
function documentLabel(name) {return String(name||'Document').replace(/^\d+_/, '').replace(/_/g, ' ');}
function prettyDate(value) { if (!value) return '—'; try {return new Date(value).toLocaleString('en-GB',{dateStyle:'medium',timeStyle:'short'});} catch {return value;} }
function humanStatus(st) {return ({new:'New',in_review:'In review',approved:'Approved',exported:'Exported',confirmed:'Confirmed',conflict:'Conflict',invalid:'Invalid value',needs_review:'Needs review',missing:'Missing',optional:'Optional'})[st] || st;}
function statusBadge(st) {return `<span class="badge badge-${esc(st)}"><i class="badge-dot"></i>${esc(humanStatus(st))}</span>`;}
function initials(name) {return String(name||'LX').split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase();}
function svg(name,size=20) {
 const paths={
 grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
 files:'<path d="M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M8 3v5h5"/><path d="M8 13h8M8 17h8"/>',
 inbox:'<path d="M4 4h16v11l-3 5H7l-3-5z"/><path d="M4 14h5l2 3h2l2-3h5"/>',
 check:'<path d="m5 12 5 5L20 6"/>',
 clipboard:'<rect x="4" y="5" width="16" height="17" rx="2"/><path d="M9 5V3h6v2M8 11h8M8 15h8"/>',
 transfer:'<path d="M4 7h15m-5-4 5 4-5 4M20 17H5m5-4-5 4 5 4"/>',
 activity:'<path d="M3 12h4l3-8 4 16 3-8h4"/>',
 settings:'<circle cx="12" cy="12" r="3"/><path d="M20 12a8 8 0 0 0-.4-2.5l1.5-1.2-2-3.4-1.9.7a8 8 0 0 0-4.4-2.5L12 1l-.8 2.1a8 8 0 0 0-4.4 2.5l-1.9-.7-2 3.4 1.5 1.2a8 8 0 0 0 0 5l-1.5 1.2 2 3.4 1.9-.7a8 8 0 0 0 4.4 2.5L12 23l.8-2.1a8 8 0 0 0 4.4-2.5l1.9.7 2-3.4-1.5-1.2A8 8 0 0 0 20 12z"/>',
 plus:'<path d="M12 5v14M5 12h14"/>',
 arrow:'<path d="M5 12h14m-6-6 6 6-6 6"/>',
 chevron:'<path d="m9 18 6-6-6-6"/>',
 down:'<path d="m6 9 6 6 6-6"/>',
 search:'<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
 upload:'<path d="M12 17V3m-5 5 5-5 5 5"/><path d="M4 17v3h16v-3"/>',
 download:'<path d="M12 3v14m-5-5 5 5 5-5M4 20h16"/>',
 eye:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
 shield:'<path d="m12 2 9 4v5c0 5-3 9-9 11-6-2-9-6-9-11V6z"/><path d="m8 12 3 3 5-6"/>',
 alert:'<path d="M12 3 2 21h20zM12 9v5M12 17h.01"/>',
 lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
 book:'<path d="M4 4a2 2 0 0 1 2-2h14v19H6a2 2 0 0 0-2 2zM4 4v17a2 2 0 0 1 2-2h14"/>',
 clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/>',
 close:'<path d="M6 6 18 18M18 6 6 18"/>',
 user:'<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
 logout:'<path d="M10 5H5v14h5M14 7l5 5-5 5M19 12H9"/>',
 more:'<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
 bolt:'<path d="m13 2-9 11h7l-1 9 10-12h-7z"/>',
 edit:'<path d="m3 21 4-1 13-13-3-3L4 17zM15 6l3 3"/>',
 server:'<rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M7 6h.01M7 17h.01"/>',
 table:'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 10h18M10 3v18"/>',
 menu:'<path d="M4 7h16M4 12h16M4 17h16"/>',
 info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>'
 };
 return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]||paths.grid}</svg>`;
}
function toast(message,type='success') {
 const id=crypto.randomUUID();
 while(toastRoot.children.length>=3)toastRoot.firstElementChild.remove();
 toastRoot.insertAdjacentHTML('beforeend',`<div data-toast="${id}" class="toast toast-${type}"><div class="toast-symbol">${svg(type==='error'?'alert':'check',18)}</div><span>${esc(message)}</span><button class="bare-btn" data-action="dismiss-toast" data-id="${id}" aria-label="Dismiss">${svg('close',15)}</button></div>`);
 setTimeout(()=>document.querySelector(`[data-toast="${id}"]`)?.remove(),6100);
}
async function api(url,options={}) {
 const opts={credentials:'same-origin',...options,headers:{...(options.headers||{})}};
 if (options.json !== undefined) {opts.method=opts.method||'POST';opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(options.json);}
 if (S.csrf && opts.method && opts.method !== 'GET') opts.headers['X-CSRF-Token']=S.csrf;
 let res;
 try {res=await fetch(url,opts);}catch(err){throw new Error('Cannot reach the local server. Check that LexFlow is running.');}
 let payload;
 try {payload=await res.json();}catch{payload={detail:'Unexpected server response'};}
 if (!res.ok) {
   if (res.status===401 && !url.endsWith('/login')) { S.user=null;S.csrf='';showLogin(); }
   throw new Error(typeof payload.detail==='string'?payload.detail:JSON.stringify(payload.detail||'Request failed'));
 }
 return payload;
}
function navLink(to,icon,label,tag='') {let active=S.route===to||(to==='/matters'&&S.route.startsWith('/matter/'));return `<a href="#${to}" class="nav-item ${active?'active':''}">${svg(icon,19)}<span>${label}</span>${tag?`<em>${tag}</em>`:''}</a>`;}
function headerTitle() {
 if (S.route==='/dashboard')return ['Overview','Your workflow, in one place'];
 if (S.route==='/matters')return ['Matters','All workspaces and case records'];
 if (S.route.startsWith('/matter/'))return ['Matter workspace','Source-to-approval review'];
 if (S.route.startsWith('/intake'))return ['Document intake','Bring your documents into LexFlow'];
 if (S.route==='/queue')return ['Review queue','Verify exceptions and missing information'];
 if (S.route==='/exports')return ['Transfers & exports','Approved data, controlled handoff'];
 if (S.route==='/audit')return ['Audit trail','Every action, accountable'];
 if (S.route==='/workflows')return ['Workflow studio','Reusable document rules'];
 if (S.route==='/integrations')return ['Integrations','Approved delivery and receipts'];
 if (S.route==='/pilot')return ['Pilot measurement','Measure the workflow'];
 if (S.route==='/security')return ['Security','Controls, sessions and audit integrity'];
 if (S.route==='/settings')return ['Workspace settings','Integration mappings and access'];
 return ['LexFlow',''];
}
function shell(content) {
 const [title,subtitle]=headerTitle();
 app.innerHTML=`<div class="app-shell">
 <aside class="sidebar ${S.mobileNav?'mobile-open':''}">
  <div class="side-top"><a href="#/dashboard" class="logo" aria-label="LexFlow home"><span class="logo-mark">L<span>≡</span></span><span class="logo-copy">LEX<span>FLOW</span><small>AI</small><em>Legal workspace</em></span></a><button class="sidebar-close" data-action="toggle-nav" aria-label="Close navigation">${svg('close')}</button></div>
  <div class="workspace-switch"><span class="ws-icon">${svg('shield',19)}</span><div><strong>${esc(S.user.workspace)}</strong><span>Protected workspace</span></div>${svg('down',15)}</div>
  <p class="side-section">WORKSPACE</p>
  <nav class="side-nav">${navLink('/dashboard','grid','Overview')}${navLink('/matters','files','Matters')}${navLink('/intake','inbox','Document intake')}${navLink('/queue','clipboard','Review queue')}</nav>
  <p class="side-section">MANAGEMENT</p>
  <nav class="side-nav">${navLink('/workflows','bolt','Workflow studio')}${navLink('/integrations','server','Integrations')}${navLink('/pilot','activity','Pilot measurement')}${navLink('/security','shield','Security')}${navLink('/exports','transfer','Transfers & exports')}${navLink('/audit','activity','Audit trail')}${navLink('/settings','settings','Settings')}</nav>
  <div class="sidebar-bottom"><div class="environment-card"><span class="env-eyebrow"><span class="pulse-dot"></span> SANDBOX ENVIRONMENT</span><strong>Human-in-the-loop</strong><span>Approval required before any export. Approval-gated exports and integration receipts.</span></div><div class="side-profile"><span class="avatar">${esc(initials(S.user.name))}</span><div><b>${esc(S.user.name)}</b><small>${esc(S.user.role.toUpperCase())}</small></div><button title="Sign out" aria-label="Sign out" data-action="logout" class="icon-button light">${svg('logout',18)}</button></div></div>
 </aside>
 <div class="main-area"><header class="topbar"><div class="topbar-title"><button class="mobile-toggle" data-action="toggle-nav" aria-label="Open navigation">${svg('menu',22)}</button><span class="breadcrumb">Workspace <span> / </span> <strong>${esc(title)}</strong></span><small>${esc(subtitle)}</small></div><div class="topbar-right">${typeof F!=='undefined'&&F.timer?`<button class="btn btn-secondary btn-small" data-action="pilot-timer">${svg('clock',15)} Stop work timer</button>`:''}<span class="topbar-chip">${svg('lock',14)} ${S.profile==='hardened'?'Hardened profile':'Local demo'}</span><a href="#/intake" class="topbar-add">${svg('plus',17)} New intake</a><span class="header-avatar">${esc(initials(S.user.name))}</span></div></header><main class="page-content">${content}</main><footer class="app-footer"><span>© 2026 LexFlow AI • Allgift Technologies Ltd • <b>Functional prototype v0.10.0</b></span><span>${S.demoMode===false?'Operational review required':'Demo data only'} • Not production-certified</span></footer></div></div>`;
}
function pageRenderer(route){
 const hash=location.hash||'#/dashboard';
 if(hash.split('?')[0]!=='#'+route)throw new DOMException('Page navigation superseded this request','AbortError');
 S.route=hash.slice(1);
 return content=>{if((location.hash||'#/dashboard')!==hash)throw new DOMException('Page navigation superseded this request','AbortError');shell(content);};
}
function sectionHeading(kicker,title,description,actions='') {return `<div class="page-heading"><div><p class="eyebrow">${esc(kicker)}</p><h1>${esc(title)}</h1><p class="muted">${esc(description)}</p></div>${actions?`<div class="heading-actions">${actions}</div>`:''}</div>`;}
function emptyState(title,desc,btn='') {return `<div class="empty-state"><span class="empty-ico">${svg('files',30)}</span><h3>${esc(title)}</h3><p>${esc(desc)}</p>${btn}</div>`;}
function matterRows(matters) {
 if(!matters.length) return `<tr><td colspan="6">${emptyState('No matching matters','Create a matter or adjust your filters.',`<button class="btn btn-primary" data-action="new-matter">${svg('plus',16)} New matter</button>`)}</td></tr>`;
 return matters.map(m=>`<tr class="clickable-row" data-go="/matter/${esc(m.id)}"><td><span class="ref-cell"><span class="file-mini">${svg('files',17)}</span><b>${esc(m.reference)}</b></span></td><td><div class="td-main">${esc(m.title)}<small>${esc(S.config.schemas[m.matter_type]?.label||m.matter_type)}</small></div></td><td>${statusBadge(m.status)}</td><td><span class="inline-metric ${m.conflict_count?'warn':''}">${m.conflict_count?svg('alert',15):svg('check',15)} ${m.conflict_count?m.conflict_count+' conflict'+(m.conflict_count>1?'s':''):m.document_count+' files'}</span></td><td>${esc(prettyDate(m.updated_at))}</td><td class="row-chevron">${svg('chevron',18)}</td></tr>`).join('');
}
async function dashboard() {
 const shell=pageRenderer('/dashboard');
 const data=await api('/api/dashboard');
 const total=data.total_matters||1;
 shell(`${sectionHeading('CONTROL CENTER',`Good ${new Date().getHours()<12?'morning':new Date().getHours()<18?'afternoon':'evening'}, ${S.user.name.split(' ')[0]}.`,'Review incoming information, resolve uncertainty and move approved data forward.',`${S.config.demo_mode?`<button class="btn btn-secondary" data-action="start-demo">${svg('bolt',18)} Start guided demo</button>`:''}<button class="btn btn-primary" data-action="new-matter">${svg('plus',18)} New matter</button>`)}
 <section class="hero-banner"><div class="hero-info"><div class="hero-kicker">${svg('bolt',15)} INTELLIGENT DOCUMENT OPERATIONS</div><h2>Keep your systems.<br/><em>Remove the repetitive work.</em></h2><p>From incoming document to verified, approved structured data — with people in control at every stage.</p><a href="#/intake" class="hero-button">Process a document ${svg('arrow',17)}</a></div><div class="hero-visual" aria-label="From source documents to human approval"><div class="preview-document"><div class="preview-document-head"><span>${svg('files',17)} A clearer workflow</span>${svg('book',19)}</div><div class="preview-document-row"><span>01</span><b>Source documents</b>${svg('check',16)}</div><div class="preview-document-row"><span>02</span><b>Structured information</b>${svg('check',16)}</div><div class="preview-document-row"><span>03</span><b>Human approval</b>${svg('shield',16)}</div><div class="preview-document-foot">Thoughtfully connected. Always reviewed.</div></div></div></section>
 <div class="metrics-grid"><div class="metric-card"><div class="metric-top">Active matters <span class="metric-icon blue">${svg('files',20)}</span></div><strong>${data.total_matters}</strong><p>Total in current workspace</p></div><div class="metric-card"><div class="metric-top">Awaiting review <span class="metric-icon purple">${svg('clipboard',20)}</span></div><strong>${data.review_queue}</strong><p>Require verification or approval</p></div><div class="metric-card"><div class="metric-top">Data conflicts <span class="metric-icon amber">${svg('alert',20)}</span></div><strong>${data.conflicts}</strong><p>Unresolved cross-document mismatches</p></div><div class="metric-card"><div class="metric-top">Approved exports <span class="metric-icon green">${svg('transfer',20)}</span></div><strong>${data.exports}</strong><p>Files generated, no live transmission</p></div></div>
 <div class="two-panel"><section class="panel"><div class="panel-heading"><div><p class="eyebrow">OPERATIONS</p><h3>Recent matters</h3></div><a href="#/matters" class="text-link">View all ${svg('arrow',16)}</a></div><div class="table-scroll"><table><thead><tr><th>Reference</th><th>Matter</th><th>Status</th><th>Attention</th><th>Updated</th><th></th></tr></thead><tbody>${matterRows(data.recent_matters)}</tbody></table></div></section>
 <aside class="panel pulse-panel"><div class="panel-heading"><div><p class="eyebrow">WORKFLOW STATUS</p><h3>Pipeline snapshot</h3></div>${svg('activity',20)}</div><div class="pipeline-visual">${Object.entries({new:'New',in_review:'In review',approved:'Approved',exported:'Exported'}).map(([key,label])=>`<div class="pipeline-row"><div class="pipeline-lab"><span>${label}</span><b>${data.status_counts[key]||0}</b></div><div class="pipeline-bar"><span class="fill-${key}" style="width:${Math.max(data.status_counts[key]/total*100,0)}%"></span></div></div>`).join('')}</div><div class="pipeline-tip">${svg('shield',19)}<div><b>Human oversight remains essential.</b><span>Automated extraction never bypasses the explicit approval gate.</span></div></div></aside></div>
 <section class="panel activity-panel"><div class="panel-heading"><div><p class="eyebrow">TRACEABILITY</p><h3>Recent activity</h3></div><a href="#/audit" class="text-link">Full audit trail ${svg('arrow',16)}</a></div><div class="activity-list">${data.recent_activity.map(a=>`<div class="activity-item"><span class="activity-mark">${svg(a.action.includes('approved')?'check':a.action.includes('document')?'upload':'activity',17)}</span><div><strong>${esc(a.action.replaceAll('_',' '))}</strong><span>${esc(a.reference||'Workspace')} • ${esc(a.actor||'System')}</span></div><time>${esc(prettyDate(a.created_at))}</time></div>`).join('')}</div></section>`);
}
async function mattersPage() {
 const shell=pageRenderer('/matters');
 const data=await api('/api/matters?'+new URLSearchParams({q:S.search,status:S.statusFilter}));
 shell(`${sectionHeading('CASE MANAGEMENT','All matters','Browse records, open a review workbench or start a new matter.',`<button class="btn btn-primary" data-action="new-matter">${svg('plus',18)} New matter</button>`)}
 <section class="panel list-panel"><div class="list-toolbar"><div class="search-box">${svg('search',18)}<input id="matter-search" placeholder="Search title or reference…" value="${esc(S.search)}" autocomplete="off" /></div><div class="filter-pills">${[['','All'],['new','New'],['in_review','In review'],['approved','Approved'],['exported','Exported']].map(([value,label])=>`<button data-action="filter-status" data-status="${value}" class="filter-pill ${S.statusFilter===value?'selected':''}">${label}</button>`).join('')}</div></div><div class="table-scroll"><table><thead><tr><th>Reference</th><th>Matter</th><th>Status</th><th>Documents / issues</th><th>Last updated</th><th></th></tr></thead><tbody>${matterRows(data.matters)}</tbody></table></div><div class="table-footer">${data.matters.length} matter${data.matters.length===1?'':'s'} shown <span>Tenant-scoped records</span></div></section>`);
 const search=document.querySelector('#matter-search');if(search){search.focus();search.setSelectionRange(search.value.length,search.value.length);}
}
async function queuePage() {
 const shell=pageRenderer('/queue');
 const d=await api('/api/matters');
 const pending=d.matters.filter(m=>m.status==='new'||m.status==='in_review');
 pending.sort((a,b)=>(b.conflict_count-a.conflict_count)||(b.unreviewed_count-a.unreviewed_count));
 shell(`${sectionHeading('HUMAN APPROVAL','Review queue','Work through documents requiring verification, correction or sign-off.',`<a class="btn btn-secondary" href="#/matters">View all matters ${svg('arrow',16)}</a>`)}
 <div class="review-callout">${svg('shield',24)}<div><strong>Designed to escalate uncertainty — never silently guess.</strong><p>Conflicting values, missing required fields and unverified suggestions block final approval until a reviewer confirms them.</p></div></div>
 <section class="panel"><div class="panel-heading"><div><p class="eyebrow">ACTION REQUIRED</p><h3>${pending.length} open matter${pending.length!==1?'s':''}</h3></div></div>${pending.length?`<div class="queue-list">${pending.map(m=>`<a href="#/matter/${esc(m.id)}" class="queue-card"><span class="queue-icon ${m.conflict_count?'danger':''}">${svg(m.conflict_count?'alert':'clipboard',22)}</span><div><small>${esc(m.reference)} • ${esc(S.config.schemas[m.matter_type]?.label||m.matter_type)}</small><strong>${esc(m.title)}</strong><span>${m.conflict_count?m.conflict_count+' source conflict(s) • ':''}${m.unreviewed_count} required field(s) need approval</span></div>${statusBadge(m.status)}${svg('chevron',20)}</a>`).join('')}</div>`:emptyState('Review queue is clear','No matters currently require human review.')}</section>`);
}
function fieldCard(field){
 const interesting=field.candidates.length;
 const reviewed=Boolean(field.reviewed_at);
 const source=reviewed?field.candidates.find(c=>c.id===field.review_candidate_id):field.candidates[0];
 const sourceText=reviewed?(source?documentLabel(source.document_name)+' • human verified':'Manual correction • human verified'):(source?documentLabel(source.document_name)+' • '+Math.round(field.confidence*100)+'% confidence':'Manual entry available');
 const icon=field.status==='confirmed'?'check':['conflict','invalid'].includes(field.status)?'alert':field.status==='missing'?'close':'files';
 return `<div class="field-card ${field.status==='conflict'?'field-conflict':''}" id="field-${esc(field.key)}"><div class="field-top"><div class="field-title"><span class="field-status-icon field-is-${esc(field.status)}">${svg(icon,17)}</span><div><strong>${esc(field.label)}</strong><small>${field.required?'REQUIRED':'OPTIONAL'} • ${field.candidates.length} source suggestion${interesting===1?'':'s'}</small></div></div>${statusBadge(field.status)}</div>
 <div class="field-value">${field.value?esc(field.value):'<span class="field-empty">No value detected</span>'}</div>
 <div class="field-bottom"><span class="source-hint">${svg(source?'files':'info',14)} ${esc(sourceText)}</span>${S.user.role!=='analyst'?`<button class="field-action" data-action="review-field" data-field="${esc(field.key)}">${svg('edit',15)} ${reviewed?'Edit review':'Review field'}</button>`:'<span class="readonly-tag">Read only</span>'}</div>
 ${field.validation_error?`<div class="conflict-strip">${svg('alert',16)} ${esc(field.validation_error)}</div>`:''}
 ${field.status==='conflict'?`<div class="conflict-strip">${svg('alert',16)} ${interesting} suggestions contain different values — choose the correct source.</div>`:''}</div>`;
}
async function matterPage(id){
 const shell=pageRenderer('/matter/'+id);
 const d=await api('/api/matters/'+encodeURIComponent(id));S.matter=d;
 const m=d.matter, pct=Math.round((d.required_confirmed/Math.max(1,d.required_total))*100);
 const already=m.status==='approved'||m.status==='exported';
 const pilotTimerButton=`<button class="btn btn-secondary" data-action="pilot-timer" data-matter="${esc(m.id)}">${svg('clock',17)} ${typeof F!=='undefined'&&F.timer?'Stop work timer':'Start work timer'}</button>`;
 shell(`<div class="back-line"><a href="#/matters">${svg('arrow',16)} All matters</a><span> / </span><strong>${esc(m.reference)}</strong></div>
 <div class="matter-page-head"><div><div class="case-ref">${svg('files',17)} ${esc(m.reference)} ${statusBadge(m.status)}</div><h1>${esc(m.title)}</h1><p>${esc(S.config.schemas[m.matter_type]?.label||m.matter_type)} • Created ${esc(prettyDate(m.created_at))}</p></div><div class="matter-actions"><a href="#/intake?matter=${encodeURIComponent(id)}" class="btn btn-secondary">${svg('plus',17)} Add documents</a>${already?`<button class="btn btn-secondary" data-action="reopen-matter">${svg('edit',16)} Reopen</button><button class="btn btn-primary" data-action="export-matter">${svg('download',17)} Export approved data</button>`:`<button class="btn btn-primary" data-action="approve-matter" ${!d.ready_for_approval?'disabled title="Confirm required fields and resolve every conflict or invalid value"':''}>${svg('check',17)} Approve matter</button>`}</div></div>
 <div class="status-progress"><div class="progress-copy"><div><span class="progress-circle">${svg('check',18)}</span><strong>Review completeness</strong><span>${d.required_confirmed} of ${d.required_total} required fields confirmed</span></div><b>${pct}%</b></div><div class="progress-track"><span style="width:${pct}%"></span></div></div>
 ${pct===100&&!d.ready_for_approval?`<div class="audit-alert">${svg('alert',18)} Resolve remaining conflicts or invalid values: ${esc((d.approval_blockers||[]).join(', '))}</div>`:''}
 <div class="feature-toolbar">${pilotTimerButton}<a class="text-link" href="#/integrations">Integrations & receipts ${svg('arrow',16)}</a><a class="text-link" href="#/pilot">Pilot evidence ${svg('activity',16)}</a></div><div class="workbench-grid"><aside class="side-stack"><section class="panel workbench-panel"><div class="panel-heading"><div><p class="eyebrow">SOURCES</p><h3>Documents <span class="count-pill">${d.documents.length}</span></h3></div><a href="#/intake?matter=${encodeURIComponent(id)}" class="small-square" title="Add source">${svg('plus',18)}</a></div>${d.documents.length?`<div class="doc-list">${d.documents.map(doc=>`<button class="doc-list-item" title="${esc(doc.name)}" data-action="view-doc" data-id="${esc(doc.id)}"><span class="doc-file-icon">${svg('files',19)}</span><span><b>${esc(documentLabel(doc.name))}</b><small>${Math.max(1,Math.round(doc.byte_size/1024))} KB • ${esc(prettyDate(doc.created_at))}</small></span>${svg('eye',16)}</button>`).join('')}</div>`:emptyState('No source files','Use document intake to upload a file or paste some text.')}</section>
 <section class="panel insight-panel"><div class="panel-heading"><div><p class="eyebrow">WORKFLOW</p><h3>Approval controls</h3></div></div><div class="check-list"><p>${svg('check',16)} Explicit reviewer confirmations</p><p>${svg('check',16)} Source evidence per suggestion</p><p>${svg('check',16)} Conflict-aware field verification</p><p>${svg('check',16)} Audit events for all decisions</p></div></section></aside>
 <section class="panel extraction-panel"><div class="panel-heading"><div><p class="eyebrow">STRUCTURED INFORMATION</p><h3>Extracted fields</h3><p class="panel-sub">Review values against the originating documents. Suggestions are not considered approved.</p></div><span class="field-count">${d.fields.length} fields</span></div><div class="field-grid">${d.fields.map(fieldCard).join('')}</div></section>
 <aside class="side-stack"><section class="panel risk-panel"><div class="panel-heading"><div><p class="eyebrow">INTELLIGENCE SIGNALS</p><h3>Review insights</h3></div>${svg('activity',20)}</div><div class="insight-stat"><span class="insight-dot danger"></span><div><b>${d.fields.filter(f=>f.status==='conflict').length} conflicts</b><small>Different source values</small></div></div><div class="insight-stat"><span class="insight-dot warning"></span><div><b>${d.fields.filter(f=>f.status==='missing').length} missing</b><small>Required information absent</small></div></div><div class="insight-stat"><span class="insight-dot good"></span><div><b>${d.fields.filter(f=>f.status==='confirmed').length} verified</b><small>Human-confirmed fields</small></div></div><div class="soft-note">${svg('info',17)} Field confidences are extraction heuristics, not calibrated legal reliability scores.</div></section>
 <section class="panel process-panel"><div class="panel-heading"><div><p class="eyebrow">SEVEN-STAGE FLOW</p><h3>Processing path</h3></div></div><div class="step-list">${[['Receive',d.documents.length>0],['Choose matter type',true],['Extract',d.fields.some(f=>f.candidates.length)],['Validate',d.ready_for_approval],['Review',d.ready_for_approval],['Approve',already],['Export file',m.status==='exported']].map(([step,done],i)=>`<div class="step ${done?'done':''}"><span>${done?svg('check',14):i+1}</span><b>${step}</b>${done?'<small>Complete</small>':''}</div>`).join('')}</div></section></aside></div>
 ${d.exports.length?`<section class="panel existing-exports"><div class="panel-heading"><div><p class="eyebrow">OUTPUTS</p><h3>Generated approved exports</h3></div></div>${d.exports.map(e=>`<div class="export-inline">${svg('download',18)}<b>${esc(e.filename)}</b><span>${esc(prettyDate(e.created_at))}</span>${e.invalidated_at?`<span title="${esc(e.invalidation_reason)}">Superseded — approve and export again</span>`:`<a href="/api/exports/${encodeURIComponent(e.id)}/download">Download ${svg('arrow',16)}</a>`}</div>`).join('')}</section>`:''}`);
}
async function intakePage() {
 const shell=pageRenderer('/intake');
 const data=await api('/api/matters');
 const params=new URLSearchParams((S.route.split('?')[1]||''));
 const preselected=params.get('matter')||data.matters[0]?.id||'';
 shell(`${sectionHeading('SMART INTAKE','Document processing','Import files or pasted text, extract suggestions and route them to a human reviewer.',`<button class="btn btn-secondary" data-action="new-matter">${svg('plus',17)} New matter</button>`)}
 <div class="intake-grid"><section class="panel intake-main"><div class="panel-heading"><div><p class="eyebrow">STEP 01</p><h3>Choose destination matter</h3><p class="panel-sub">Inputs stay inside the chosen workspace and matter.</p></div></div><div class="form-pad"><label class="form-label">Matter<select id="intake-matter" class="form-control">${data.matters.map(m=>`<option value="${esc(m.id)}" ${m.id===preselected?'selected':''}>${esc(m.reference+' — '+m.title)}</option>`).join('')}</select></label>
 <div class="intake-switch"><button data-action="intake-tab" data-tab="file" id="tab-file" class="intake-tab selected">${svg('upload',17)} File upload</button><button data-action="intake-tab" data-tab="paste" id="tab-paste" class="intake-tab">${svg('files',17)} Paste document text</button></div>
 <div id="pane-file"><form id="upload-form"><label class="drop-area" id="drop-area"><span class="drop-bubble">${svg('upload',26)}</span><strong>Drop documents here, or choose files</strong><p>PDF, DOCX, EML, TXT, PNG, JPG, TIFF</p><small>Up to ${S.config.max_upload_mb} MB per file · 6 files per batch</small><input type="file" multiple id="intake-files" accept=".pdf,.docx,.eml,.txt,.png,.jpg,.jpeg,.tif,.tiff" hidden /></label><div id="file-summary" class="file-summary"></div><div class="intake-footer">${externalAIControl()}<button type="submit" class="btn btn-primary" id="upload-submit">${svg('bolt',17)} Process selected files</button></div></form></div>
 <div id="pane-paste" hidden><form id="paste-form"><label class="form-label">Document label<input class="form-control" id="paste-name" value="pasted_correspondence.txt" maxlength="128"/></label><label class="form-label">Document text<textarea id="paste-text" class="form-control paste-input" placeholder="Paste an email, questionnaire or text extracted from a legal document…" required></textarea></label><button type="button" class="btn btn-ghost" data-action="load-sample">${svg('files',16)} Insert synthetic example</button><div class="intake-footer">${externalAIControl('paste-ai')}<button type="submit" class="btn btn-primary">${svg('bolt',17)} Extract structured fields</button></div></form></div></div></section>
 <aside class="intake-right"><section class="panel how-panel"><p class="eyebrow">WHAT HAPPENS NEXT</p><h3>One secure processing pipeline</h3>${[['Classify','A matter-specific field schema defines what can be extracted.'],['Extract','Local document rules identify explicitly labeled values.'],['Reconcile','Different source values are flagged for review.'],['Approve','Reviewers confirm values before generating a file export.']].map(([t,d],i)=>`<div class="how-step"><span>0${i+1}</span><div><b>${t}</b><p>${d}</p></div></div>`).join('')}</section><section class="blue-info">${svg('shield',24)}<b>Privacy by default</b><p>Offline rules run locally. External AI is disabled unless the server administrator configures it and the user explicitly opts in for this intake.</p><span>Prototype only · Do not upload real confidential records</span></section></aside></div>`);
 document.querySelector('#intake-files')?.addEventListener('change',()=>updateFileSummary());
 const dz=document.querySelector('#drop-area');if(dz){['dragenter','dragover'].forEach(e=>dz.addEventListener(e,ev=>{ev.preventDefault();dz.classList.add('dragging');}));['dragleave','drop'].forEach(e=>dz.addEventListener(e,ev=>{ev.preventDefault();dz.classList.remove('dragging');}));dz.addEventListener('drop',ev=>{const input=document.querySelector('#intake-files');input.files=ev.dataTransfer.files;updateFileSummary();});}
}
function externalAIControl(id='upload-ai') {return `<label class="ai-opt"><input type="checkbox" id="${id}" ${S.config.external_ai_enabled?'':'disabled'}/><span><b>Use external AI enhancement</b><small>${S.config.external_ai_enabled?'Opt-in sends this document to the configured AI provider.':'Disabled on server; local extraction runs by default.'}</small></span></label>`;}
function updateFileSummary(){const files=[...(document.querySelector('#intake-files')?.files||[])];document.querySelector('#file-summary').innerHTML=files.length?files.map(f=>`<span>${svg('files',15)} ${esc(f.name)} <small>${Math.round(f.size/1024)} KB</small></span>`).join(''):'';}
async function exportsPage(){
 const shell=pageRenderer('/exports');
 const d=await api('/api/exports');
 shell(`${sectionHeading('APPROVED DATA TRANSFER','Exports & connectors','Browse approved outputs and view exactly what data leaves the review process.',`<a href="#/settings" class="btn btn-secondary">${svg('settings',16)} Configure mappings</a>`)}
 <div class="connector-grid"><div class="connector-card"><span class="connector-symbol">${svg('files',24)}</span><div><h3>Approved structured export</h3><p>CSV and JSON files mapped to destination field names.</p><span class="connector-state"><i></i> Ready for download</span></div></div><div class="connector-card"><span class="connector-symbol lavender">${svg('transfer',24)}</span><div><h3>Notary connector simulator</h3><p>Demonstrates a mapped data handoff without writing to a live system.</p><span class="connector-state muted-state"><i></i> Sandbox only</span></div></div><div class="connector-card"><span class="connector-symbol beige">${svg('lock',24)}</span><div><h3>BNotK / XNP integrations</h3><p>Production integrations require authorized interfaces, vendor agreements and verification.</p><span class="connector-state offline-state"><i></i> Not connected</span></div></div></div>
 <section class="panel"><div class="panel-heading"><div><p class="eyebrow">EXPORT HISTORY</p><h3>${d.exports.length} approved output${d.exports.length!==1?'s':''}</h3></div></div><div class="table-scroll"><table><thead><tr><th>File name</th><th>Linked matter</th><th>Profile</th><th>Created by</th><th>Date</th><th>Download</th></tr></thead><tbody>${d.exports.length?d.exports.map(e=>`<tr><td><span class="ref-cell"><span class="file-mini">${svg('download',17)}</span><b>${esc(e.filename)}</b></span></td><td><a class="table-link" href="#/matter/${esc(e.matter_id)}">${esc(e.reference)}</a></td><td>${esc(e.connector==='notary_demo'?'Notary simulator':'Approved export')} <small class="ext-tag">${esc(e.format.toUpperCase())}</small></td><td>${esc(e.actor)}</td><td>${esc(prettyDate(e.created_at))}</td><td>${e.invalidated_at?`<span title="${esc(e.invalidation_reason)}">Superseded</span>`:`<a href="/api/exports/${encodeURIComponent(e.id)}/download" class="text-link">${svg('download',16)} Download</a>`}</td></tr>`).join(''):`<tr><td colspan="6">${emptyState('No exports yet','Confirm all required fields, approve a matter and then export its structured data.')}</td></tr>`}</tbody></table></div></section>`);
}
async function auditPage(){
 const shell=pageRenderer('/audit');
 const d=await api('/api/audit?limit=200');S.auditEvents=d.events;
 shell(`${sectionHeading('TRANSPARENCY & CONTROL','Audit trail','A chronological history of intake, human decisions and generated outputs.')}
 <div class="audit-alert">${svg('info',19)} <span>Events are protected by workspace HMAC chains. Verify the chain and download a checkpoint in Security. External checkpoint storage and retention remain operator responsibilities.</span></div>
 <section class="panel"><div class="panel-heading"><div><p class="eyebrow">RECENT EVENTS</p><h3>${d.events.length} logged activities</h3></div></div><div class="table-scroll"><table><thead><tr><th>Event</th><th>Matter</th><th>Actor</th><th>Details</th><th>Timestamp (UTC)</th></tr></thead><tbody>${d.events.map(e=>`<tr><td><div class="ref-cell"><span class="file-mini">${svg(e.action.includes('approved')?'check':e.action.includes('document')?'upload':'activity',17)}</span><b>${esc(e.action.replaceAll('_',' '))}</b></div></td><td>${e.matter_id?`<a class="table-link" href="#/matter/${esc(e.matter_id)}">${esc(e.reference)}</a>`:'Workspace'}</td><td>${esc(e.actor||'System')}</td><td class="audit-details"><button class="text-link bare-btn" data-action="audit-details" data-id="${esc(e.id)}">View decision details</button></td><td>${esc(prettyDate(e.created_at))}</td></tr>`).join('')}</tbody></table></div></section>`);
}
async function settingsPage(){
 const shell=pageRenderer('/settings');
 const [mappings,members,security]=await Promise.all([api('/api/settings/mappings'),S.user.role==='admin'?api('/api/settings/users'):Promise.resolve({users:[]}),api('/api/security/status')]);
 const users=members.users;
 shell(`${sectionHeading('WORKSPACE CONFIGURATION','Settings','Review deployment boundaries, field mappings and team permissions.')}
 <div class="settings-grid"><section class="panel settings-panel"><div class="panel-heading"><div><p class="eyebrow">DATA TRANSFER</p><h3>Connector field mappings</h3><p class="panel-sub">Each destination must be unique. Mapping changes require affected matters to be approved again.</p></div></div><form id="mappings-form"><div class="mapping-list">${Object.entries(mappings.mappings).map(([key,target])=>`<div class="mapping-row"><label><span>${esc(S.config.field_meta[key]?.label||key)}</span><small>${esc(key)}</small></label><span class="mapping-arrow">${svg('arrow',16)}</span><input class="form-control mapping-input" data-field="${esc(key)}" value="${esc(target)}" ${S.user.role!=='admin'?'disabled':''} required /></div>`).join('')}</div>${S.user.role==='admin'?`<div class="settings-actions"><button class="btn btn-primary" type="submit">${svg('check',17)} Save mappings</button></div>`:''}</form></section>
 <div class="settings-right"><section class="panel info-settings"><div class="panel-heading"><div><p class="eyebrow">DEPLOYMENT PROFILE</p><h3>${security.profile==='hardened'?'Hardened configuration':'Local sandbox'}</h3></div><span class="badge badge-confirmed"><i class="badge-dot"></i> Active</span></div><div class="setting-fact"><span>Processing</span><strong>Local rules</strong></div><div class="setting-fact"><span>External AI</span><strong>${S.config.external_ai_enabled?'Configured (opt-in)':'Disabled'}</strong></div><div class="setting-fact"><span>Database</span><strong>Local SQLite</strong></div><div class="setting-fact"><span>Remote notary connectors</span><strong>Not connected</strong></div><div class="setting-fact"><span>New artifact encryption</span><strong>${security.storage_encryption?'Enabled':'Not configured'}</strong></div><div class="settings-disclaimer">${svg('alert',19)} A production notarial deployment requires a dedicated security and regulatory review.</div></section>
 <section class="panel info-settings"><div class="panel-heading"><div><p class="eyebrow">ACCESS CONTROL</p><h3>Workspace members</h3></div></div>${users.length?users.map(u=>`<div class="member-row"><span class="avatar small-avatar">${esc(initials(u.name))}</span><div><b>${esc(u.name)}</b><span>${esc(u.email)}</span></div><strong>${esc(u.role)}</strong></div>`).join(''):`<p class="muted" style="padding:0 24px 20px">Only admins can view team membership.</p>`}</section>
 <section class="panel info-settings"><div class="panel-heading"><div><p class="eyebrow">ACCOUNT SECURITY</p><h3>Change password</h3></div></div><form id="password-form" class="small-form"><label>Current password<input class="form-control" type="password" name="current_password" autocomplete="current-password" required/></label><label>New password (12+ characters)<input class="form-control" type="password" name="new_password" minlength="12" maxlength="128" autocomplete="new-password" required /></label><button class="btn btn-secondary" type="submit">${svg('lock',17)} Update password</button></form></section></div></div>`);
}
function showAuthPage(content,label='Sign in'){
 S.user=null;S.csrf='';S.config=null;
 S.matter=null;S.auditEvents=[];closeModal();if(typeof resetFeatures==='function')resetFeatures();
 app.innerHTML=`<div class="login-page">
  <section class="login-story" aria-label="About LexFlow">
   <div class="login-wordmark"><span class="logo-mark" aria-hidden="true">L<span>≡</span></span>LEX<span>FLOW</span><small>AI</small></div>
   <div class="story-center">
    <span class="story-eyebrow">INTELLIGENCE FOR LEGAL WORK</span>
    <h1>Complex documents.<br/><em>Clear decisions.</em></h1>
    <p>A considered workspace for document intake, human verification and the confident movement of approved information.</p>
    <div class="story-features">
     <div class="story-feature"><span>${svg('files',18)}</span><div><b>Every detail, connected.</b><p>Keep extracted information linked to its source.</p></div></div>
     <div class="story-feature"><span>${svg('shield',18)}</span><div><b>Your judgement stays central.</b><p>Review uncertainty and approve with intention.</p></div></div>
     <div class="story-feature"><span>${svg('activity',18)}</span><div><b>A clear record of the work.</b><p>Follow decisions from first intake to final export.</p></div></div>
    </div>
   </div>
   <div class="login-story-bottom">BUILT FOR LEGAL PROFESSIONALS<span>Allgift Technologies Ltd</span></div>
  </section>
  <section class="login-form-side" aria-label="${esc(label)}">
   <div class="login-form-wrap">
    <div class="login-overline"><span class="pulse-dot"></span>YOUR LEGAL WORKSPACE</div>
    ${content}
    <p class="login-disclaimer">LexFlow AI · ${S.demoMode===false?'Legal workspace':'Demonstration workspace'}</p>
   </div>
  </section>
 </div>`;
}
function showLogin(resetComplete=false){
 showAuthPage(`
    <h2>Welcome back.</h2>
    <p class="login-desc">A little less administration.<br/>A little more room for the work that matters.</p>
    ${resetComplete?`<div class="auth-notice" role="status">${svg('check',20)}<div><b>Password updated.</b><p>Sign in with your new password. Your previous sessions have been signed out.</p></div></div>`:''}
    <form id="login-form">
     <label>Email address<span class="input-with-icon">${svg('user',18)}<input class="form-control" type="email" name="email" required value="admin@keller.demo" autocomplete="username" /></span></label>
     <label>Password<span class="input-with-icon">${svg('lock',18)}<input class="form-control" type="password" name="password" required value="LexFlowDemo2026!" autocomplete="current-password" /></span></label>
     <div class="auth-help"><a class="text-link" href="#/forgot-password">Forgot password?</a></div>
     <div class="auth-feedback" role="alert" tabindex="-1" hidden></div>
     <button class="btn btn-primary login-button" type="submit">Enter your workspace ${svg('arrow',18)}</button>
    </form>
    <p class="login-security">${svg('lock',13)} A private workspace. A human decision.</p>
    <div class="demo-credentials">
     <div>${svg('info',17)}<b>Explore the demonstration</b></div>
     <div class="demo-account-options" aria-label="Choose a demo role">
      <button type="button" data-action="choose-login" data-email="admin@keller.demo" aria-pressed="true">Admin</button>
      <button type="button" data-action="choose-login" data-email="reviewer@keller.demo" aria-pressed="false">Reviewer</button>
      <button type="button" data-action="choose-login" data-email="assistant@keller.demo" aria-pressed="false">Analyst</button>
      <button type="button" data-action="choose-login" data-email="admin@weber.demo" aria-pressed="false">Other office</button>
     </div>
     <small>Sample password: <code>LexFlowDemo2026!</code><br/>Synthetic examples only. Keep confidential records out of this demo.</small>
    </div>
 `);
 if(S.demoMode===false){document.querySelector('.demo-credentials')?.remove();document.querySelector('#login-form [name=email]').value='';document.querySelector('#login-form [name=password]').value='';}
 if(resetComplete){document.querySelector('#login-form [name=password]').value='';document.querySelector('#login-form [name=email]').value='';document.querySelectorAll('[data-action=choose-login]').forEach(button=>button.setAttribute('aria-pressed','false'));}
}
function showForgotPassword(){
 showAuthPage(`
  <a class="auth-back text-link" href="#/login">${svg('chevron',15)} Back to sign in</a>
  <div class="auth-emblem">${svg('lock',25)}</div>
  <h2>Let’s get you back in.</h2>
  <p class="login-desc">Enter your account email to request a link and create a new password.</p>
  <form id="reset-request-form">
   <label>Email address<span class="input-with-icon">${svg('user',18)}<input class="form-control" type="email" name="email" required maxlength="254" placeholder="you@your-practice.com" autocomplete="username" /></span></label>
   <div class="auth-feedback" role="alert" tabindex="-1" hidden></div>
   <button class="btn btn-primary login-button" type="submit">Request reset link ${svg('arrow',18)}</button>
  </form>
  <div id="reset-request-result" class="auth-result" role="status" tabindex="-1" hidden></div>
  <p class="login-security">${svg('clock',14)} Reset links expire after 30 minutes.</p>
 `,'Reset password');
}
function showResetPassword(token){
 showAuthPage(`
  <a class="auth-back text-link" href="#/login">${svg('chevron',15)} Back to sign in</a>
  <div class="auth-emblem">${svg('shield',25)}</div>
  <h2>A fresh start.</h2>
  <p class="login-desc">Choose a password with 12–128 characters. Resetting it signs out your existing sessions.</p>
  ${token?`<form id="reset-password-form">
   <label>New password<span class="input-with-icon">${svg('lock',18)}<input class="form-control" type="password" name="new_password" required minlength="12" maxlength="128" autocomplete="new-password" aria-describedby="password-guidance" /></span></label>
   <p class="auth-guidance" id="password-guidance">Use a long, unique password you haven’t used elsewhere.</p>
   <label>Confirm new password<span class="input-with-icon">${svg('lock',18)}<input class="form-control" type="password" name="confirm_password" required minlength="12" maxlength="128" autocomplete="new-password" /></span></label>
   <div class="auth-feedback" role="alert" tabindex="-1" hidden></div>
   <button class="btn btn-primary login-button" type="submit">Save new password ${svg('arrow',18)}</button>
  </form>`:`<div class="auth-feedback" role="alert">This reset link is incomplete. Request a new link to continue.</div>`}
  <p class="auth-retry">Need another link? <a class="text-link" href="#/forgot-password">Request a new one</a></p>
 `,'Create a new password');
 const form=document.querySelector('#reset-password-form');if(form)form.resetToken=token;
}

async function render(){
 const publicPath=location.hash.slice(1).split('?')[0];
 if(publicPath==='/forgot-password'){showForgotPassword();return;}
 if(publicPath==='/reset-password'){showResetPassword(new URLSearchParams(location.hash.split('?')[1]||'').get('token')||'');return;}
 if(publicPath==='/login'){showLogin(new URLSearchParams(location.hash.split('?')[1]||'').get('reset')==='success');return;}
 if(!S.user){showLogin();return;}
 const key=++S.renderKey;
 const hash=decodeURI(location.hash.slice(1)||'/dashboard');
 const path=hash.split('?')[0];
 S.route=hash;
 // Redirect invalid paths to overview.
 try {
  if(path==='/dashboard') await dashboard();
  else if(path==='/matters') await mattersPage();
  else if(path==='/queue') await queuePage();
  else if(path==='/intake') await intakePage();
  else if(path==='/exports') await exportsPage();
  else if(path==='/audit') await auditPage();
  else if(path==='/workflows') await workflowsPage();
  else if(path==='/integrations') await integrationsPage();
  else if(path==='/pilot') await pilotPage();
  else if(path==='/security') await securityPage();
  else if(path==='/settings') await settingsPage();
  else if(path.startsWith('/matter/')) await matterPage(path.split('/')[2]);
  else {location.hash='#/dashboard';return;}
  S.mobileNav=false;
 }catch(err){ if(err.name==='AbortError'||key!==S.renderKey)return;console.error(err); if(S.user){shell(emptyState('Could not load this page',err.message,`<a class="btn btn-primary" href="#/dashboard">Return to overview</a>`));} }
}
async function start(){
 try{const options=await api('/api/auth/options');S.demoMode=options.demo_mode;S.profile=options.security_profile;}catch{S.demoMode=false;}
 if(['/login','/forgot-password','/reset-password'].includes(location.hash.slice(1).split('?')[0])){await render();return;}
 try {const d=await api('/api/auth/me');S.user=d.user;S.csrf=d.csrf;S.config=await api('/api/config');if(!location.hash)location.hash='#/dashboard';await render();}
 catch{await render();}
}
function showModal(html,size='medium') {modalRoot.innerHTML=`<div class="modal-backdrop"><div class="modal-dialog modal-${size}" role="dialog" aria-modal="true">${html}</div></div>`;document.body.classList.add('modal-open');}
function closeModal(){modalRoot.innerHTML='';document.body.classList.remove('modal-open');}
function modalTop(kicker,title,desc=''){return `<div class="modal-heading"><div><span class="eyebrow">${esc(kicker)}</span><h2>${esc(title)}</h2>${desc?`<p>${esc(desc)}</p>`:''}</div><button type="button" data-action="close-modal" class="icon-button" aria-label="Close dialog">${svg('close',20)}</button></div>`;}
function newMatterModal(){showModal(`${modalTop('NEW WORKFLOW','Create a matter','Choose a matter schema. You can attach documents immediately afterward.')}<form id="new-matter-form" class="modal-body"><label class="form-label">Matter title<input class="form-control" name="title" placeholder="e.g. Property purchase — Example Street 4" maxlength="160" minlength="3" required autofocus/></label><label class="form-label">Matter type<select name="matter_type" class="form-control">${Object.entries(S.config.schemas).map(([key,obj])=>`<option value="${esc(key)}">${esc(obj.label)}</option>`).join('')}</select></label><div class="modal-tip">${svg('info',18)} You can process PDF, Word, email, scans (optional OCR) and text documents.</div><div class="modal-buttons"><button type="button" class="btn btn-secondary" data-action="close-modal">Cancel</button><button type="submit" class="btn btn-primary">Create matter ${svg('arrow',17)}</button></div></form>`);}
function reviewModal(key){
 const field=S.matter?.fields.find(f=>f.key===key);if(!field)return;
 const canEdit=S.matter.matter.status!=='approved'&&S.matter.matter.status!=='exported';
 const reviewed=Boolean(field.reviewed_at);
 const manual=reviewed&&!field.review_candidate_id;
 const selected=reviewed?field.review_candidate_id:(field.status==='conflict'?null:field.candidates[0]?.id);
 showModal(`${modalTop('SOURCE VERIFICATION',field.label,'Select the correct extracted value or enter a manually verified correction.')}<form id="review-field-form" class="modal-body" data-field="${esc(key)}">
 <div class="review-modal-label">Source suggestions <span>${field.candidates.length}</span></div><div class="candidate-options">${field.candidates.length?field.candidates.map((c,i)=>`<label class="candidate-option"><input type="radio" name="candidate" value="${esc(c.id)}" ${c.id===selected?'checked':''}/><div><div class="candidate-primary"><b>${esc(c.value)}</b><span>${Math.round(c.confidence*100)}% confidence</span></div><p>${esc(documentLabel(c.document_name))} · ${esc(c.origin.replaceAll('_',' '))}</p><blockquote>${esc(trim(c.evidence,240))}</blockquote></div></label>`).join(''):`<p class="candidate-empty">No suggestions. Enter an appropriately verified manual value below.</p>`}</div>
 <label class="form-label">Manual override <small>(optional; takes precedence over selected suggestion)</small><input id="review-manual" class="form-control" value="${esc(manual?field.value:'')}" placeholder="Enter verified value from document…" maxlength="300"/></label><label class="form-label">Review note <small>(optional)</small><textarea id="review-note" class="form-control note-input" placeholder="e.g. Confirmed correct land register number from revised attachment…" maxlength="500">${esc(field.review_note||'')}</textarea></label>
 ${field.status==='conflict'?`<div class="modal-warning">${svg('alert',18)} Conflicting source values detected. Your explicit selection resolves this field's conflict for approval.</div>`:''}
 <div class="modal-buttons">${field.status==='confirmed'&&canEdit?`<button type="button" class="btn btn-ghost" data-action="clear-field" data-field="${esc(key)}">Clear review</button>`:''}<button type="button" class="btn btn-secondary" data-action="close-modal">Cancel</button><button type="submit" class="btn btn-primary" ${canEdit?'':'disabled'}>${svg('check',17)} Confirm value</button></div></form>`, 'large');
 modalRoot.querySelectorAll('[name=candidate]').forEach(input=>input.addEventListener('change',()=>{document.querySelector('#review-manual').value='';}));
}
async function docModal(id){
 const doc=await api('/api/documents/'+encodeURIComponent(id));
 showModal(`${modalTop('SOURCE DOCUMENT',doc.name,'Inspect extracted text and source-file metadata.')}<div class="modal-body"><div class="doc-details"><span>${svg('files',17)} ${Math.round(doc.byte_size/1024)} KB</span><span>SHA-256: ${esc(doc.sha256.slice(0,17))}…</span></div>${(doc.warnings||[]).map(w=>`<div class="audit-alert">${svg('alert',17)} ${esc(w)}</div>`).join('')}<pre class="doc-preview">${esc(doc.raw_text||'[No extractable text. For scanned images, install optional local OCR or paste text.]')}</pre><div class="modal-buttons">${S.user.role!=='analyst'?`<button class="btn btn-secondary" data-action="teach-source">${svg('bolt',17)} Teach a field</button>`:''}<button class="btn btn-secondary" data-action="close-modal">Close</button><a href="/api/documents/${encodeURIComponent(doc.id)}/download" class="btn btn-primary">${svg('download',16)} Download original</a></div></div>`, 'large');
}
async function exportModal(){
 const id=S.matter?.matter?.id;if(!id)return;
 let d=await api(`/api/matters/${id}/export/preview?fmt=json`);
 showModal(`${modalTop('CONTROLLED HANDOFF','Generate approved export','Local file generation only — no data is sent to any external notarial system.')}<form class="modal-body" id="export-form"><div class="export-options"><label class="form-label">File format<select class="form-control" id="export-format"><option value="json">JSON — structured payload</option><option value="csv">CSV — mapped key-value rows</option></select></label><label class="form-label">Connector profile<select class="form-control" id="export-connector"><option value="approved_export">Approved export</option><option value="notary_demo">Notary software simulator</option></select></label></div><p class="review-modal-label">Payload preview</p><pre class="doc-preview export-preview" id="export-preview">${esc(d.preview)}</pre><div class="modal-buttons"><button type="button" data-action="close-modal" class="btn btn-secondary">Cancel</button><button type="submit" class="btn btn-primary">${svg('download',17)} Generate export</button></div></form>`, 'large');
 const form=document.querySelector('#export-form'),preview=document.querySelector('#export-preview');
 let previewVersion=0;
 const refresh=async()=>{const version=++previewVersion,button=form.querySelector('[type=submit]');button.disabled=true;try{const query=new URLSearchParams({fmt:form.querySelector('#export-format').value,connector:form.querySelector('#export-connector').value});const r=await api(`/api/matters/${id}/export/preview?${query}`);if(version===previewVersion&&form.isConnected){preview.textContent=r.preview;button.disabled=false;}}catch(e){if(version===previewVersion&&form.isConnected){preview.textContent='Preview unavailable. Choose the format again to retry.';toast(e.message,'error');}}};
 form.querySelector('#export-format').addEventListener('change',refresh);
 form.querySelector('#export-connector').addEventListener('change',refresh);
}
async function actionClick(ev){
 const t=ev.target.closest('[data-action]');
 if(!t)return;
 const act=t.dataset.action;
 try {
  if(typeof featureActions==='function'&&['new-rule','teach-source','preview-rule','toggle-rule','rule-history','preview-transfer','receiver-detail','retry-transfer','revoke-sessions','pilot-timer'].includes(act)){await featureActions(act,t);return;}
  if(act==='logout'){await api('/api/auth/logout',{method:'POST'});S.user=null;S.csrf='';showLogin();return;}
  if(act==='toggle-nav'){S.mobileNav=!S.mobileNav;document.querySelector('.sidebar')?.classList.toggle('mobile-open',S.mobileNav);return;}
  if(act==='dismiss-toast'){document.querySelector(`[data-toast="${t.dataset.id}"]`)?.remove();return;}
  if(act==='choose-login'){document.querySelector('#login-form [name=email]').value=t.dataset.email;document.querySelector('#login-form [name=password]').value='LexFlowDemo2026!';document.querySelectorAll('[data-action=choose-login]').forEach(button=>button.setAttribute('aria-pressed',String(button===t)));return;}
  if(act==='start-demo'){t.disabled=true;try{const d=await api('/api/demo/start',{method:'POST'});location.hash='#/matter/'+d.id;await render();toast('Demo ready: review the five required fields and resolve the land register conflict.');}finally{t.disabled=false;}return;}
  if(act==='audit-details'){const event=S.auditEvents.find(e=>e.id===t.dataset.id);if(event)showModal(`${modalTop('DECISION HISTORY',event.action.replaceAll('_',' '),event.actor+' • '+prettyDate(event.created_at))}<div class="modal-body"><pre class="doc-preview">${esc(JSON.stringify(JSON.parse(event.details_json),null,2))}</pre><div class="modal-buttons"><button type="button" class="btn btn-secondary" data-action="close-modal">Close</button></div></div>`,'large');return;}
  if(act==='new-matter'){newMatterModal();return;}
  if(act==='close-modal'){closeModal();return;}
  if(act==='filter-status'){S.statusFilter=t.dataset.status;await mattersPage();return;}
  if(act==='review-field'){reviewModal(t.dataset.field);return;}
  if(act==='view-doc'){await docModal(t.dataset.id);return;}
  if(act==='load-sample'){document.querySelector('#paste-text').value=SAMPLE;document.querySelector('#paste-name').value='synthetic_purchase_example.txt';toast('Synthetic sample loaded. Choose a property purchase matter to extract fields.');return;}
  if(act==='intake-tab'){let isFile=t.dataset.tab==='file';document.querySelector('#pane-file').hidden=!isFile;document.querySelector('#pane-paste').hidden=isFile;document.querySelector('#tab-file').classList.toggle('selected',isFile);document.querySelector('#tab-paste').classList.toggle('selected',!isFile);return;}
  if(act==='clear-field'){if(!confirm('Clear the human confirmation for this field?'))return;let id=S.matter.matter.id;await api(`/api/matters/${id}/fields/${t.dataset.field}/clear`,{method:'POST'});closeModal();await matterPage(id);toast('Field confirmation cleared.');return;}
  if(act==='approve-matter'){let id=S.matter?.matter?.id;if(!confirm('Approve this matter? All required field values will be locked for controlled export.'))return;await api(`/api/matters/${id}/approve`,{method:'POST'});toast('Matter approved. It can now be exported.');await matterPage(id);return;}
  if(act==='reopen-matter'){let id=S.matter?.matter?.id;if(!confirm('Reopen this approved matter for editing? This invalidates its current approval.'))return;await api(`/api/matters/${id}/reopen`,{method:'POST'});toast('Matter reopened for review.');await matterPage(id);return;}
  if(act==='export-matter'){await exportModal();return;}
 }catch(err){if(err.name!=='AbortError')toast(err.message,'error');}
}
async function submitForms(ev){
 const f=ev.target;
 if(!f?.id)return;
 ev.preventDefault();
 const submit=f.querySelector('[type=submit]');if(submit){submit.disabled=true;submit.classList.add('busy');}
 const feedback=f.querySelector('.auth-feedback');if(feedback)feedback.hidden=true;
 try{
  if(typeof submitFeatureForm==='function'&&await submitFeatureForm(f))return;
  if(f.id==='login-form') {const fd=new FormData(f);const d=await api('/api/auth/login',{json:{email:fd.get('email'),password:fd.get('password')}});S.user=d.user;S.csrf=d.csrf;S.config=await api('/api/config');location.hash='#/dashboard';await render();toast('Welcome to your workspace.');}
  if(f.id==='reset-request-form'){
   const fd=new FormData(f);const d=await api('/api/auth/forgot-password',{json:{email:fd.get('email').trim()}});
   const result=document.querySelector('#reset-request-result');if(!result||!f.isConnected)return;
   result.innerHTML=`<div class="auth-result-heading">${svg('check',19)}<b>Request received</b></div><p>${esc(d.message)}</p>${d.delivery==='demo'?`<div class="auth-demo-note"><b>Local demonstration</b><p>No email is sent. Reset links are displayed here for the four seeded demo accounts.</p>${d.demo_reset_path?`<a id="demo-reset-link" class="btn btn-secondary" href="${esc(d.demo_reset_path)}">Create a new password ${svg('arrow',16)}</a><small>This single-use link expires in ${esc(d.expires_in_minutes)} minutes. A new request replaces it.</small>`:'<p>Use a sample account such as <strong>admin@keller.demo</strong> to try this flow.</p>'}</div>`:'<p>If the email matches an account, check your inbox and spam folder for the link.</p>'}`;
   result.hidden=false;result.focus();submit.innerHTML=`Request another link ${svg('arrow',18)}`;
  }
  if(f.id==='reset-password-form'){
   const fd=new FormData(f);if(fd.get('new_password')!==fd.get('confirm_password'))throw new Error('Passwords do not match. Enter the same password in both fields.');
   await api('/api/auth/reset-password',{json:{token:f.resetToken,new_password:fd.get('new_password'),confirm_password:fd.get('confirm_password')}});
   f.reset();f.resetToken='';history.replaceState(null,'',location.pathname+location.search+'#/login?reset=success');showLogin(true);
  }
  if(f.id==='new-matter-form'){const fd=new FormData(f);const d=await api('/api/matters',{json:{title:fd.get('title'),matter_type:fd.get('matter_type')}});closeModal();location.hash='#/matter/'+d.id;await render();toast('Matter created. Add source documents to begin.');}
  if(f.id==='paste-form'){const id=document.querySelector('#intake-matter').value;const txt=document.querySelector('#paste-text').value;if(!id)throw new Error('Create or select a matter first.');const data=await api('/api/intake/text',{json:{matter_id:id,filename:document.querySelector('#paste-name').value,text:txt,use_external_ai:document.querySelector('#paste-ai').checked}});toast(`Document processed: ${data.suggestions} field suggestions.`);if(data.warnings.length)toast(data.warnings.join(' '),'error');location.hash='#/matter/'+id;await render();}
  if(f.id==='upload-form'){const id=document.querySelector('#intake-matter').value;const files=document.querySelector('#intake-files').files;if(!id||!files.length)throw new Error('Select a matter and at least one file.');const fd=new FormData();fd.append('matter_id',id);fd.append('use_external_ai',String(document.querySelector('#upload-ai').checked));for(const file of files)fd.append('files',file);let d=await api('/api/intake/upload',{method:'POST',body:fd});const num=d.results.reduce((sum,r)=>sum+r.suggestions,0);toast(`${d.results.length} document(s) ingested: ${num} suggestions.`);const warns=d.results.flatMap(x=>x.warnings);if(warns.length)toast(warns.join(' '),'error');location.hash='#/matter/'+id;await render();}
  if(f.id==='review-field-form'){const id=S.matter.matter.id,key=f.dataset.field,manual=document.querySelector('#review-manual').value.trim();const picked=f.querySelector('[name=candidate]:checked')?.value;const d=await api(`/api/matters/${id}/fields/${key}/confirm`,{json:{candidate_id:manual?null:picked||null,value:manual||null,note:document.querySelector('#review-note').value}});closeModal();await matterPage(id);toast(`${S.config.field_meta[key].label} confirmed by reviewer.`);}
  if(f.id==='export-form'){const id=S.matter.matter.id;const d=await api(`/api/matters/${id}/exports`,{json:{format:document.querySelector('#export-format').value,connector:document.querySelector('#export-connector').value}});closeModal();await matterPage(id);toast('Approved file created. Download is available below.');window.location.href=d.download_url;}
  if(f.id==='mappings-form'){const mappings={};f.querySelectorAll('.mapping-input').forEach(i=>{mappings[i.dataset.field]=i.value.trim();});await api('/api/settings/mappings',{method:'PUT',json:{mappings}});toast('Mappings saved. Affected matters require approval again.');}
  if(f.id==='password-form'){const fd=new FormData(f);await api('/api/auth/change-password',{json:Object.fromEntries(fd)});f.reset();toast('Password updated. Other sessions were closed.');}
 }catch(err){if(err.name==='AbortError')return;if(feedback&&f.isConnected){feedback.textContent=err.message;feedback.hidden=false;feedback.focus();}else toast(err.message,'error');}
 finally{if(submit){submit.disabled=false;submit.classList.remove('busy');}}
}
app.addEventListener('click',ev=>{const row=ev.target.closest('[data-go]');if(row&&!ev.target.closest('a,button')){location.hash='#'+row.dataset.go;return;}actionClick(ev);});
modalRoot.addEventListener('click',ev=>{if(ev.target.classList.contains('modal-backdrop'))closeModal();else actionClick(ev);});
toastRoot.addEventListener('click',actionClick);
document.addEventListener('submit',submitForms);
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});
let searchTimer;
document.addEventListener('input',ev=>{if(ev.target.id==='matter-search'){S.search=ev.target.value;clearTimeout(searchTimer);searchTimer=setTimeout(()=>{if(location.hash.split('?')[0]==='#/matters') mattersPage();},350);}});
window.addEventListener('hashchange',render);
start();
