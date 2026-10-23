'use strict';
const desk={user:null,csrf:'',cases:[],selected:null,tab:'details',query:''};
const deskApp=document.querySelector('#notary-app');
const safe=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stageName=value=>({received:'Received',in_preparation:'In preparation',ready_for_review:'Ready for review'})[value]||value;
const date=value=>new Date(value).toLocaleString('en-GB',{dateStyle:'medium',timeStyle:'short'});
const fieldNames={'Beteiligter.Kaeufer.Name':'Buyer','Beteiligter.Verkaufer.Name':'Seller','Vorgang.KaufpreisEUR':'Purchase price (EUR)','Immobilie.Anschrift':'Property address','Grundbuch.Blatt':'Land register','Beteiligter.Kaeufer.Email':'Buyer email','Vorgang.Termin':'Appointment','Immobilie.Flurstueck':'Parcel reference'};
async function request(url,options={}){
 const response=await fetch(url,{credentials:'same-origin',...options,headers:{'Content-Type':'application/json',...(options.method?{'X-CSRF-Token':desk.csrf}:{})}});
 const data=await response.json();
 if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'The destination request could not be completed.');
 return data;
}
function announce(message){const target=document.querySelector('#notary-feedback');target.textContent=message;setTimeout(()=>{if(target.textContent===message)target.textContent='';},6500);}
function renderList(){
 const filtered=desk.cases.filter(record=>(record.matter.reference+' '+record.matter.title).toLowerCase().includes(desk.query.toLowerCase()));
 document.querySelector('#notary-case-list').innerHTML=filtered.length?filtered.map(record=>`<button type="button" class="notary-case" data-case="${safe(record.id)}" aria-current="${record.id===desk.selected}"><small>${safe(record.matter.reference)}</small><strong>${safe(record.matter.title)}</strong><span class="badge badge-${record.stage==='ready_for_review'?'confirmed':'optional'}">${safe(stageName(record.stage))}</span></button>`).join(''):'<p class="notary-empty">No matching destination cases. Send an approved matter from LexFlow to NotaryDesk Demo to begin.</p>';
}
function renderDetail(){
 const record=desk.cases.find(item=>item.id===desk.selected);
 const target=document.querySelector('#notary-detail');
 if(!record){target.innerHTML='<div class="notary-empty"><h2>Your next case starts with an approved handoff.</h2><p>This destination stores the mapped values it receives and keeps an acceptance receipt.</p><a class="btn btn-primary" href="/#/integrations">Open LexFlow integrations</a></div>';return;}
 target.innerHTML=`<div class="notary-detail-head"><p class="eyebrow">${safe(record.matter.reference)}</p><h2>${safe(record.matter.title)}</h2><p>Received ${safe(date(record.received_at))} · <b>${safe(stageName(record.stage))}</b></p></div><div class="notary-detail-body"><div class="tab-list" role="tablist" aria-label="Destination case sections">${[['details','Case details'],['evidence','Delivery evidence']].map(([id,label])=>`<button type="button" class="tab-button" role="tab" id="desk-tab-${id}" aria-controls="desk-panel-${id}" aria-selected="${desk.tab===id}" tabindex="${desk.tab===id?0:-1}" data-desk-tab="${id}">${label}</button>`).join('')}</div>
 <section role="tabpanel" id="desk-panel-details" aria-labelledby="desk-tab-details" tabindex="0" ${desk.tab==='details'?'':'hidden'}><dl class="notary-fields">${Object.entries(record.fields).map(([key,value])=>`<div class="notary-field"><dt>${safe(fieldNames[key]||key)}</dt><dd>${safe(value)}</dd></div>`).join('')}</dl><form class="notary-stage" id="notary-stage-form"><p class="eyebrow">DESTINATION WORKFLOW</p><p>Change the preparation stage in this fictional case-management workspace. The approved source values stay read-only.</p><div class="feature-form-grid"><label class="form-label">Case stage<select class="form-control" name="stage" ${desk.user.role==='analyst'?'disabled':''}>${['received','in_preparation','ready_for_review'].map(stage=>`<option value="${stage}" ${record.stage===stage?'selected':''}>${stageName(stage)}</option>`).join('')}</select></label><button class="btn btn-primary" type="submit" ${desk.user.role==='analyst'?'disabled':''}>Save case stage</button></div><p id="notary-stage-error" role="alert" hidden></p></form></section>
 <section role="tabpanel" id="desk-panel-evidence" aria-labelledby="desk-tab-evidence" tabindex="0" ${desk.tab==='evidence'?'':'hidden'}><dl class="notary-evidence"><div><dt>Destination receipt</dt><dd>${safe(record.receipt_id)}</dd></div><div><dt>Source approval</dt><dd>${safe(date(record.matter.approved_at))}</dd></div><div><dt>Received payload SHA-256</dt><dd><code>${safe(record.payload_sha256)}</code></dd></div><div><dt>Handoff</dt><dd>Signed request · Verified TLS certificate · Signed acceptance receipt · Duplicate protection</dd></div></dl><p class="feature-caption">This receipt belongs to a fictional demonstration destination. It does not establish acceptance by a real notary vendor.</p><p><a class="text-link" href="/#/matter/${encodeURIComponent(record.source_matter_id)}">Open the source matter in LexFlow →</a></p></section></div>`;
}
function selectTab(button,focus=false){
 desk.tab=button.dataset.deskTab;
 document.querySelectorAll('[data-desk-tab]').forEach(tab=>{const selected=tab===button;tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;document.getElementById(tab.getAttribute('aria-controls')).hidden=!selected;});
 if(focus){button.focus({preventScroll:true});button.scrollIntoView({block:'nearest',inline:'nearest'});}
}
function render(){
 deskApp.innerHTML=`<div class="notary-heading"><div><p class="eyebrow">${safe(desk.user.workspace)}</p><h1>A clear desk for the next step.</h1><p>Approved matters received from LexFlow, ready for preparation.</p></div><div class="notary-trust"><b>Independent destination</b><span>Signed HTTPS handoffs · Encrypted case storage</span></div></div><div class="notary-metrics">${[['Received cases',desk.cases.length],['In preparation',desk.cases.filter(c=>c.stage==='in_preparation').length],['Ready for review',desk.cases.filter(c=>c.stage==='ready_for_review').length]].map(([label,value])=>`<div class="notary-metric"><span>${label}</span><b>${value}</b></div>`).join('')}</div><div class="notary-workspace"><aside class="panel"><div class="panel-heading"><div><p class="eyebrow">DESTINATION CASES</p><h3>Case register</h3></div><button class="btn btn-secondary btn-small" type="button" data-desk-action="refresh">Refresh</button></div><div class="notary-search"><label class="form-label">Find a case<input id="notary-search" class="form-control" type="search" placeholder="Title or reference…" value="${safe(desk.query)}" /></label></div><div id="notary-case-list" class="notary-case-list"></div></aside><section id="notary-detail" class="panel"></section></div>`;
 renderList();renderDetail();
 document.querySelector('#notary-search').addEventListener('input',event=>{desk.query=event.target.value;renderList();});
}
async function refresh(){const data=await request('/api/demo-notary/cases');desk.cases=data.cases;if(!desk.cases.some(record=>record.id===desk.selected))desk.selected=desk.cases[0]?.id||null;render();}
document.addEventListener('click',async event=>{
 const tab=event.target.closest('[data-desk-tab]');if(tab){selectTab(tab);return;}
 const item=event.target.closest('[data-case]');if(item){desk.selected=item.dataset.case;desk.tab='details';renderList();renderDetail();return;}
 if(event.target.closest('[data-desk-action=refresh]')){try{await refresh();announce('Destination cases refreshed.');}catch(error){announce(error.message);}}
});
document.addEventListener('keydown',event=>{
 const tab=event.target.closest('[data-desk-tab]');if(!tab||!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
 const tabs=[...document.querySelectorAll('[data-desk-tab]')];const index=event.key==='Home'?0:event.key==='End'?tabs.length-1:(tabs.indexOf(tab)+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;event.preventDefault();selectTab(tabs[index],true);
});
document.addEventListener('submit',async event=>{
 if(event.target.id!=='notary-stage-form')return;event.preventDefault();
 const form=event.target,button=form.querySelector('[type=submit]'),record=desk.cases.find(item=>item.id===desk.selected);
 button.disabled=true;
 try{const data=await request('/api/demo-notary/cases/'+encodeURIComponent(record.id)+'/stage',{method:'POST',body:JSON.stringify({stage:form.elements.stage.value,expected_revision:record.revision})});desk.cases=desk.cases.map(item=>item.id===record.id?data.case:item);render();announce('Destination case stage saved.');}
 catch(error){const feedback=form.querySelector('[role=alert]');feedback.hidden=false;feedback.textContent=error.message;}
 finally{if(button.isConnected)button.disabled=false;}
});
(async()=>{try{const auth=await request('/api/auth/me');desk.user=auth.user;desk.csrf=auth.csrf;await refresh();}catch(error){deskApp.innerHTML=`<section class="panel notary-loading"><h1>Open the LexFlow workspace first.</h1><p>${safe(error.message)}</p><a class="btn btn-primary" href="/">Return to LexFlow</a></section>`;}})();
