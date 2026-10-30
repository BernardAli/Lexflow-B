/* Structured case preparation; vendor mapping lives on the server. */
'use strict';

const CASE_CATEGORIES = {
 property_transaction:'Property transaction / Grundstücksgeschäft',
 company_agreement:'Company agreement / Gesellschaftsvertrag',
 power_of_attorney:'Power of attorney / Vorsorgevollmacht', will:'Will / Testament',
 bulk_certification:'Bulk certification / Massenbeglaubigung', other:'Other / Sonstige Akten'
};
const CASE_ROLES = {
 buyer:'Buyer', seller:'Seller', founder:'Founder', shareholder:'Shareholder', director:'Director',
 representative:'Representative', deceased:'Deceased', heir:'Heir', principal:'Principal',
 agent:'Agent', client:'Client', other:'Other'
};
const CASE_PERSON_FIELDS = [
 ['birth_name','Birth name / Geburtsname'],['birth_date','Date of birth','date'],
 ['citizenship','Citizenship'],['marital_status','Marital status',{ '':'Not recorded',single:'Single',married:'Married',divorced:'Divorced',widowed:'Widowed',other:'Other'}],
 ['matrimonial_regime','Matrimonial property regime / Güterstand']
];
const CASE_COMPANY_FIELDS = [
 ['legal_form','Legal form / Rechtsform'],['registered_seat','Registered seat / Sitz'],
 ['register_court','Register court / Registergericht'],['register_number','Register number'],['vat_id','VAT ID']
];
const CASE_PROPERTY_FIELDS = [
 ['land_register','Land register / Grundbuch'],['sheet','Sheet / Blatt'],['volume','Volume / Band'],
 ['inventory_number','Inventory number / Lfd. Nr. BV'],['district','District / Gemarkung'],
 ['section','Section / Flur'],['parcel','Parcel / Flurstück'],['area_sqm','Area in m² (decimal point)'],
 ['ownership_share','Ownership share (e.g. 1/2)'],
 ['property_type','Property type',{'':'Not recorded',built:'Built',unbuilt:'Unbuilt',residential:'Residential',condominium:'Condominium',agricultural:'Agricultural',other:'Other'}],
 ['encumbered','Encumbered / Belastet',{'':'Not recorded',true:'Yes',false:'No'}]
];
const CASE_ADDRESS_FIELDS = [['street','Street and number'],['postal_code','Postal code'],['city','City'],['country','Country']];
const CASE_TASK_STATUS = {pending:'Pending / Noch nicht veranlasst',initiated:'Initiated / Veranlasst',completed:'Completed / Erledigt'};

function caseInput(name,label,value='',type='text',required=false) {
 const control = typeof type==='object'
  ? `<select class="form-control" name="${esc(name)}">${Object.entries(type).map(([key,text])=>`<option value="${esc(key)}" ${String(value??'')===key?'selected':''}>${esc(text)}</option>`).join('')}</select>`
  : `<input class="form-control" name="${esc(name)}" value="${esc(value??'')}" type="${esc(type)}" maxlength="300" ${required?'required':''} />`;
 return `<label class="form-label">${esc(label)}${control}</label>`;
}

function caseInputGroup(fields,item,prefix='') {
 return fields.map(([key,label,type])=>caseInput(prefix+key,label,item?.[key],type||'text')).join('');
}

function caseFacts(item,fields) {
 return fields.filter(([key])=>item[key]!==''&&item[key]!=null).map(([key,label,type])=>
  `<div><dt>${esc(label)}</dt><dd>${esc(typeof type==='object'?(type[String(item[key])]||item[key]):item[key])}</dd></div>`).join('');
}

function caseSource(item) {
 const docs=S.matter?.documents||[];
 return `<p class="feature-caption">${item.source_document_ids.map(id=>{
  const doc=docs.find(d=>d.id===id);
  return `<button type="button" class="text-link bare-btn" data-action="view-doc" data-id="${esc(id)}">${esc(doc?.name||'Source document')}</button>`;
 }).join(' · ')}${item.source_note?` · ${esc(item.source_note)}`:''}</p>`;
}

function caseRecordCard(kind,item,locked) {
 let title,body;
 if(kind==='participants') {
  title=item.name;
  body=`<p>${esc(item.roles.map(role=>CASE_ROLES[role]||role).join(' · '))} · ${esc(item.entity_type)}</p>
   <dl class="case-facts">${caseFacts(item,[['short_name','Short name'],['email','Email'],['phone','Phone'],['tax_id','Tax ID'],...(item.entity_type==='company'?CASE_COMPANY_FIELDS:CASE_PERSON_FIELDS)])}
   ${caseFacts(item.address,CASE_ADDRESS_FIELDS)}</dl>
   ${item.representative_ids.length?`<p>Represented by: ${esc(item.representative_ids.map(id=>S.matter.case_data.data.participants.find(p=>p.id===id)?.name||id).join(', '))}</p>`:''}${caseSource(item)}`;
 } else if(kind==='properties') {
  title=item.address.street||item.land_register||item.parcel;
  body=`<dl class="case-facts">${caseFacts(item,CASE_PROPERTY_FIELDS)}${caseFacts(item.address,CASE_ADDRESS_FIELDS)}</dl>${caseSource(item)}`;
 } else {
  title=item.title;
  body=`<p>${esc(CASE_TASK_STATUS[item.status])}</p>${item.due_date?`<p>Due: ${esc(item.due_date)}</p>`:''}<p>${esc(item.note)}</p>`;
 }
 return `<article class="case-record"><div class="case-record-heading"><h4>${esc(title)}</h4>${!locked?`<div class="feature-actions"><button type="button" class="btn btn-secondary btn-small" data-action="case-edit" data-kind="${kind}" data-id="${esc(item.id)}">Edit</button><button type="button" class="btn btn-ghost btn-small" data-action="case-remove" data-kind="${kind}" data-id="${esc(item.id)}">Remove</button></div>`:''}</div>${body}</article>`;
}

function caseDetailsPanel(detail) {
 const state=detail.case_data;
 if(!state)return '<p>Reload this matter to view structured case details.</p>';
 const data=state.data,locked=['approved','exported'].includes(detail.matter.status);
 const sections=[['participants','Participants / Beteiligte','person'],['properties','Properties / Vertragsobjekte','property'],['tasks','Execution tasks / Vollzug','task']];
 return `<section class="panel case-overview"><div class="panel-heading"><div><p class="eyebrow">CASE PREPARATION</p><h3>Case details</h3><p class="panel-sub">Prepare people, companies and properties for a reviewed handoff. ProNotar32 is not connected.</p></div><span class="badge ${state.reviewed_at?'badge-confirmed':'badge-optional'}">${state.reviewed_at?'Reviewed':state.revision?'Needs review':'Optional preparation'}</span></div>
 <div class="form-pad"><dl class="case-facts"><div><dt>Category</dt><dd>${esc(CASE_CATEGORIES[data.category])}</dd></div><div><dt>Case designation</dt><dd>${esc(data.designation||'Not set')}</dd></div><div><dt>Naming code</dt><dd>${esc(data.naming_code||'Not set')}</dd></div><div><dt>Template reference</dt><dd>${esc(data.template_reference||'Not set')}</dd></div><div><dt>Execution tracking</dt><dd>${data.with_execution?'Included':'Not included'}</dd></div>${data.master_matter_id?`<div><dt>Master case</dt><dd><a class="text-link" href="#/matter/${encodeURIComponent(data.master_matter_id)}">Open master case</a></dd></div>`:''}</dl>
 <p class="feature-caption">${state.revision?`Revision ${state.revision}. ${state.reviewed_at?'Reviewed '+esc(prettyDate(state.reviewed_at))+'.':'A reviewer must verify these details before matter approval.'}`:'Existing field review works as before. Saving case details adds a separate review step.'}</p>
 <div class="feature-actions">${!locked?'<button type="button" class="btn btn-secondary" data-action="case-metadata">Edit case setup</button>':''}${state.revision&&!locked&&S.user.role!=='analyst'?`<button type="button" class="btn btn-primary" data-action="case-review" ${state.reviewed_at?'disabled':''}>Confirm case details</button>`:''}</div>
 ${!locked?'<p class="feature-caption">Check these records against the source documents and the extracted fields. Changes to either require another case review.</p>':'<p class="feature-caption">Reopen the matter to edit these approved records.</p>'}</div></section>
 <div class="case-sections">${sections.map(([kind,label,singular])=>`<section class="panel"><div class="panel-heading"><div><p class="eyebrow">${data[kind].length} RECORD${data[kind].length===1?'':'S'}</p><h3>${label}</h3></div>${!locked?`<button type="button" class="btn btn-secondary btn-small" data-action="case-add" data-kind="${kind}">Add ${singular}</button>`:''}</div><div class="case-records">${data[kind].length?data[kind].map(item=>caseRecordCard(kind,item,locked)).join(''):emptyState('No '+kind+' recorded',kind==='participants'?'Add each person or company separately. Extracted names are not automatically assigned to records.':kind==='properties'?'Add each property and its register details.':'Record pending, initiated or completed tasks. These statuses do not perform external actions.')}</div></section>`).join('')}</div>`;
}

function caseSourceInputs(item={}) {
 return `<fieldset class="case-choice-list"><legend>Source documents</legend>${(S.matter.documents||[]).map(doc=>`<label><input type="checkbox" name="source_document_ids" value="${esc(doc.id)}" ${(item.source_document_ids||[]).includes(doc.id)?'checked':''}/> ${esc(doc.name)}</label>`).join('')||'<p>Add source documents through Document intake.</p>'}</fieldset>${caseInput('source_note','Verification note (required when no source is selected)',item.source_note)}`;
}

function attachCaseContext(form,detail) {
 form.caseContext={matterId:detail.matter.id,revision:detail.case_data.revision,data:JSON.parse(JSON.stringify(detail.case_data.data))};
}

function editCaseRecord(kind,id) {
 const detail=S.matter,data=detail.case_data.data,item=data[kind].find(record=>record.id===id)||{};
 let fields;
 if(kind==='participants') {
  const otherPeople=data.participants.filter(p=>p.entity_type==='person'&&p.id!==id);
  fields=`<div class="feature-form-grid">${caseInput('entity_type','Record type',item.entity_type||'person',{person:'Person',company:'Company'})}${caseInput('name','Full name / Company name',item.name,'text',true)}${caseInput('short_name','Short name for case naming',item.short_name)}</div>
   <fieldset class="case-choice-list"><legend>Roles (choose at least one)</legend>${Object.entries(CASE_ROLES).map(([role,label])=>`<label><input type="checkbox" name="roles" value="${role}" ${(item.roles||[]).includes(role)?'checked':''}/> ${label}</label>`).join('')}</fieldset>
   <div data-entity-fields="person" class="feature-form-grid">${caseInputGroup(CASE_PERSON_FIELDS,item)}</div>
   <div data-entity-fields="company" class="feature-form-grid">${caseInputGroup(CASE_COMPANY_FIELDS,item)}</div>
   <div class="feature-form-grid">${caseInputGroup(CASE_ADDRESS_FIELDS,item.address,'address.')}${caseInput('email','Email',item.email,'email')}${caseInput('phone','Phone',item.phone)}${caseInput('tax_id','Tax ID',item.tax_id)}</div>
   <fieldset class="case-choice-list"><legend>Representatives</legend>${otherPeople.map(p=>`<label><input type="checkbox" name="representative_ids" value="${esc(p.id)}" ${(item.representative_ids||[]).includes(p.id)?'checked':''}/> ${esc(p.name)}</label>`).join('')||'<p>Add a person first to link them as a representative.</p>'}</fieldset>${caseSourceInputs(item)}`;
 } else if(kind==='properties') {
  fields=`<div class="feature-form-grid">${caseInputGroup(CASE_ADDRESS_FIELDS,item.address,'address.')}${caseInputGroup(CASE_PROPERTY_FIELDS,item)}</div>${caseSourceInputs(item)}`;
 } else {
  fields=`${caseInput('title','Task',item.title,'text',true)}<div class="feature-form-grid">${caseInput('status','Status',item.status||'pending',CASE_TASK_STATUS)}${caseInput('due_date','Due date',item.due_date,'date')}</div>${caseInput('note','Note',item.note)}`;
 }
 showModal(`${modalTop('CASE DETAILS',id?'Edit record':'Add record','Enter verified facts. Leave unavailable information blank.')}<form id="case-record-form" class="modal-body" data-kind="${kind}" data-id="${esc(id||'')}">${fields}<div class="auth-feedback" role="alert" tabindex="-1" hidden></div><div class="modal-buttons"><button type="button" class="btn btn-secondary" data-action="close-modal">Cancel</button><button type="submit" class="btn btn-primary">Save record</button></div></form>`,'large');
 const form=document.querySelector('#case-record-form');attachCaseContext(form,detail);
 if(kind==='participants') {
  const toggle=()=>form.querySelectorAll('[data-entity-fields]').forEach(section=>{section.hidden=section.dataset.entityFields!==form.elements.entity_type.value;});
  form.elements.entity_type.addEventListener('change',toggle);toggle();
 }
}

async function editCaseMetadata() {
 const detail=S.matter,data=detail.case_data.data;
 const listing=await api('/api/matters');
 if(S.matter!==detail)return;
 const masters={'':'No master case'};
 for(const matter of listing.matters)if(matter.id!==detail.matter.id)masters[matter.id]=matter.reference+' — '+matter.title;
 if(data.master_matter_id&&!masters[data.master_matter_id])masters[data.master_matter_id]='Current master case';
 showModal(`${modalTop('CASE SETUP','Prepare the case structure','These categories describe the handoff. Extraction continues to use the matter’s selected workflow.')}<form id="case-metadata-form" class="modal-body"><div class="feature-form-grid">${caseInput('category','Case category',data.category,CASE_CATEGORIES)}${caseInput('naming_code','Office naming code (e.g. KV, KVV, GS)',data.naming_code)}${caseInput('designation','Case designation for handoff',data.designation)}${caseInput('template_reference','Office template reference',data.template_reference)}${caseInput('master_matter_id','Master case',data.master_matter_id,masters)}${caseInput('with_execution','Include execution tracking',String(data.with_execution),{true:'Yes',false:'No'})}</div><p class="feature-caption">Suggested designation: <span id="case-name-suggestion">${esc(detail.case_data.suggested_designation||'Add participants first')}</span></p><button type="button" class="btn btn-secondary" data-action="case-use-name">Use suggestion</button><div class="auth-feedback" role="alert" tabindex="-1" hidden></div><div class="modal-buttons"><button type="button" class="btn btn-secondary" data-action="close-modal">Cancel</button><button type="submit" class="btn btn-primary">Save case setup</button></div></form>`,'large');
 const form=document.querySelector('#case-metadata-form');attachCaseContext(form,detail);
 form.elements.designation.maxLength=160;form.elements.naming_code.maxLength=16;
 const suggest=()=>{
  const participants=data.participants;
  let names=['seller','buyer'].flatMap(role=>participants.filter(p=>p.roles.includes(role)).map(p=>p.short_name||p.name));
  if(!names.length)names=participants.filter(p=>p.entity_type==='company').map(p=>p.short_name||p.name);
  if(!names.length)names=participants.map(p=>p.short_name||p.name);
  form.caseSuggestion=([...new Set(names)].join('/')+' '+form.elements.naming_code.value.trim()).trim().slice(0,160);
  form.querySelector('#case-name-suggestion').textContent=form.caseSuggestion||'Add participants first';
 };
 form.elements.naming_code.addEventListener('input',suggest);suggest();
}

async function persistCase(context,data) {
 await api(`/api/matters/${encodeURIComponent(context.matterId)}/case-data`,{method:'PUT',json:{expected_revision:context.revision,data}});
 closeModal();
 if(S.matter?.matter.id===context.matterId)await matterPage(context.matterId);
 toast('Case details saved. Review them before approving the matter.');
}

async function caseAction(action,button) {
 if(action==='case-use-name') {
  const form=document.querySelector('#case-metadata-form');form.elements.designation.value=form.caseSuggestion;return;
 }
 if(action==='case-metadata'){await editCaseMetadata();return;}
 if(action==='case-add'||action==='case-edit'){editCaseRecord(button.dataset.kind,button.dataset.id);return;}
 const detail=S.matter;
 if(action==='case-remove') {
  if(!confirm('Remove this record? The case details will need another review.'))return;
  const data=JSON.parse(JSON.stringify(detail.case_data.data)),kind=button.dataset.kind;
  data[kind]=data[kind].filter(item=>item.id!==button.dataset.id);
  await persistCase({matterId:detail.matter.id,revision:detail.case_data.revision},data);return;
 }
 if(action==='case-review') {
  if(!confirm('Confirm that the case details match the source documents and reviewed fields?'))return;
  await api(`/api/matters/${encodeURIComponent(detail.matter.id)}/case-data/review`,{json:{expected_revision:detail.case_data.revision}});
  await matterPage(detail.matter.id);toast('Case details reviewed. Complete field review and approve the matter.');
 }
}

async function submitCaseForm(form) {
 if(!['case-record-form','case-metadata-form'].includes(form.id))return false;
 const context=form.caseContext, data=JSON.parse(JSON.stringify(context.data)),fd=new FormData(form);
 if(form.id==='case-metadata-form') {
  for(const key of ['category','naming_code','designation','template_reference'])data[key]=fd.get(key).trim();
  data.master_matter_id=fd.get('master_matter_id')||null;data.with_execution=fd.get('with_execution')==='true';
 } else {
  const kind=form.dataset.kind,item={id:form.dataset.id||crypto.randomUUID()};
  const fields=kind==='participants'?[['name'],['short_name'],['email'],['phone'],['tax_id'],...(fd.get('entity_type')==='person'?CASE_PERSON_FIELDS:CASE_COMPANY_FIELDS)]:kind==='properties'?CASE_PROPERTY_FIELDS:[['title'],['status'],['due_date'],['note']];
  for(const [key] of fields)item[key]=(fd.get(key)||'').trim();
  if(kind!=='tasks') {
   item.address=Object.fromEntries(CASE_ADDRESS_FIELDS.map(([key])=>[key,fd.get('address.'+key).trim()]));
   item.source_document_ids=fd.getAll('source_document_ids');item.source_note=fd.get('source_note').trim();
  }
  if(kind==='participants') {
   item.entity_type=fd.get('entity_type');item.roles=fd.getAll('roles');item.representative_ids=fd.getAll('representative_ids');
   if('birth_date' in item)item.birth_date=item.birth_date||null;
  }
  if(kind==='properties')item.encumbered=item.encumbered===''?null:item.encumbered==='true';
  if(kind==='tasks')item.due_date=item.due_date||null;
  const index=data[kind].findIndex(record=>record.id===item.id);
  if(index<0)data[kind].push(item);else data[kind][index]=item;
 }
 await persistCase(context,data);return true;
}
