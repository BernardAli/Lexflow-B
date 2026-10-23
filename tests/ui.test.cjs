const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const {JSDOM} = require('jsdom');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'static/features.js'), 'utf8')+'\n'+fs.readFileSync(path.join(root, 'static/app.js'), 'utf8');

async function browser(t,hash='') {
  const dom = new JSDOM(fs.readFileSync(path.join(root, 'static/index.html'), 'utf8'), {
    url:'http://localhost:8000/'+hash, runScripts:'outside-only'
  });
  t.after(() => dom.window.close());
  dom.window.fetch = async () => ({ok:false, status:401, json:async()=>({detail:'Sign in'})});
  dom.window.eval(source + `
    globalThis.uiTest = {showModal,closeModal,reviewModal,fieldCard,exportModal,showLogin,
      showForgotPassword,showResetPassword,render,workflowsPage,tabGroup,
      intakePage,settingsPage,pilotPage,integrationsPage,showMfaGate,showRecoveryCodes,mfaSettingsPanel,
      setState(value){Object.assign(S,value);},
      setMatterPage(fn){matterPage=fn;}
    };
  `);
  await new Promise(resolve=>setImmediate(resolve));
  dom.window.uiTest.setState({user:{role:'reviewer',name:'Demo Reviewer',workspace:'Demo'},csrf:'test-token'});
  return {window:dom.window, document:dom.window.document, ui:dom.window.uiTest};
}

function field(overrides={}) {
  return {key:'buyer_name',label:'Buyer',value:'Manually Corrected Name',status:'confirmed',required:true,
    reviewed_at:'2026-10-22T12:00:00+00:00',review_candidate_id:null,review_note:'Verified correction',confidence:1,
    candidates:[
      {id:'first',value:'First Candidate',confidence:.98,document_name:'first.txt',origin:'local_rules',evidence:'First source'},
      {id:'chosen',value:'Chosen Candidate',confidence:.92,document_name:'chosen.txt',origin:'local_rules',evidence:'Chosen source'}
    ],...overrides};
}

test('Close, Cancel, backdrop and dialog interior have the correct behavior',async t=>{
  const {document,ui}=await browser(t);
  for(const label of ['Close','Cancel']) {
    ui.showModal(`<button type="button" data-action="close-modal">${label}</button>`);
    document.querySelector('.modal-dialog').click();
    assert.ok(document.querySelector('.modal-dialog'),'Clicking the dialog interior keeps it open');
    document.querySelector('[data-action=close-modal]').click();
    assert.equal(document.querySelector('.modal-dialog'),null);
  }
  ui.showModal('<p>Source content</p>');
  document.querySelector('.modal-backdrop').click();
  assert.equal(document.querySelector('.modal-dialog'),null);
});

test('password sign-in opens the factor challenge and failed proof stays outside the workspace',async t=>{
  const {window,document,ui}=await browser(t);
  ui.showLogin();
  const requests=[];
  window.fetch=async(url,options={})=>{
    requests.push({url,body:options.body});
    if(url==='/api/auth/login')return {ok:true,status:200,json:async()=>({mfa_required:true,challenge:'private-challenge'})};
    return {ok:false,status:401,json:async()=>({detail:'The code is invalid or already used'})};
  };
  document.querySelector('#login-form').dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(window.location.hash,'#/two-factor');
  assert.equal(document.querySelector('.app-shell'),null);
  assert.ok(!document.body.textContent.includes('private-challenge'));
  const form=document.querySelector('#mfa-login-form');
  form.elements.code.value='123456';
  form.dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(requests[1].url,'/api/auth/mfa/verify');
  assert.deepEqual(JSON.parse(requests[1].body),{challenge:'private-challenge',code:'123456'});
  assert.equal(form.querySelector('[role=alert]').hidden,false);
  assert.ok(form.querySelector('[role=alert]').textContent.includes('invalid'));
  assert.equal(document.querySelector('.app-shell'),null);
  assert.equal(window.localStorage.length,0);
});

test('required enrollment keeps routes gated and setup secrets disappear at sign-out',async t=>{
  const {window,document,ui}=await browser(t);
  const requests=[];
  window.fetch=async(url,options)=>{requests.push({url,options});return {ok:true,status:200,json:async()=>({secret:'SYNTHETICSETUPKEY',otpauth_uri:'unused'})};};
  ui.showMfaGate({role:'admin',mfa_required:true,mfa_enabled:false},'enrollment-csrf');
  window.history.replaceState(null,'','#/matters');await ui.render();
  assert.equal(requests.length,0);
  assert.equal(document.querySelector('.app-shell'),null);
  const form=document.querySelector('#mfa-enroll-form');
  form.elements.password.value='Test-password-only';
  form.dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(requests[0].url,'/api/auth/mfa/enroll');
  assert.equal(requests[0].options.headers['X-CSRF-Token'],'enrollment-csrf');
  assert.equal(document.querySelector('.mfa-setup-key').textContent,'SYNTHETICSETUPKEY');
  assert.ok(document.querySelector('#mfa-confirm-form'));
  assert.equal(window.localStorage.length,0);
  ui.showLogin();
  assert.ok(!document.body.textContent.includes('SYNTHETICSETUPKEY'));
});

test('recovery codes clear with private dialogs and mandatory MFA has no disable control',async t=>{
  const {document,ui}=await browser(t);
  ui.showRecoveryCodes(['single-use-private-code']);
  assert.ok(document.querySelector('.mfa-recovery-codes').textContent.includes('single-use-private-code'));
  ui.showLogin();
  assert.ok(!document.body.textContent.includes('single-use-private-code'));
  document.querySelector('#app').innerHTML=ui.mfaSettingsPanel({enabled:true,required:true,recovery_codes_remaining:9});
  assert.equal(document.querySelector('[data-action=mfa-disable]'),null);
  assert.ok(document.querySelector('[data-action=mfa-rotate]'));
  assert.ok(document.querySelector('#app').textContent.includes('9 recovery codes'));
});

test('editing retains manual corrections and notes; selecting a source clears the override',async t=>{
  const {window,document,ui}=await browser(t);
  ui.setState({matter:{matter:{id:'test',status:'in_review'},fields:[field()]}});
  ui.reviewModal('buyer_name');
  assert.equal(document.querySelector('#review-manual').value,'Manually Corrected Name');
  assert.equal(document.querySelector('#review-note').value,'Verified correction');
  assert.equal(document.querySelector('[name=candidate]:checked'),null);
  const radio=document.querySelector('[value=chosen]');
  radio.checked=true;
  radio.dispatchEvent(new window.Event('change',{bubbles:true}));
  assert.equal(document.querySelector('#review-manual').value,'');
});

test('candidate reviews retain the selected source and conflicts have no implicit choice',async t=>{
  const {document,ui}=await browser(t);
  const reviewed=field({review_candidate_id:'chosen',value:'Chosen Candidate'});
  ui.setState({matter:{matter:{id:'test',status:'in_review'},fields:[reviewed]}});
  ui.reviewModal('buyer_name');
  assert.equal(document.querySelector('[name=candidate]:checked').value,'chosen');
  document.querySelector('#app').innerHTML=ui.fieldCard(reviewed);
  const hint=document.querySelector('.source-hint').textContent;
  assert.ok(hint.includes('chosen.txt'));
  assert.ok(!hint.includes('first.txt'));
  ui.setState({matter:{matter:{id:'test',status:'in_review'},fields:[field({status:'conflict',reviewed_at:null,review_note:null})]}});
  ui.reviewModal('buyer_name');
  assert.equal(document.querySelector('[name=candidate]:checked'),null);
});

test('Clear review reaches the API through the modal event handler',async t=>{
  const {window,document,ui}=await browser(t);
  const requests=[];
  window.confirm=()=>true;
  window.fetch=async(url,options)=>{
    requests.push({url,options});
    return {ok:true,status:200,json:async()=>({ok:true})};
  };
  ui.setMatterPage(async()=>{});
  ui.setState({config:{},matter:{matter:{id:'test',status:'in_review'},fields:[field()]}});
  ui.reviewModal('buyer_name');
  document.querySelector('[data-action=clear-field]').click();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(requests[0].url,'/api/matters/test/fields/buyer_name/clear');
  assert.equal(requests[0].options.method,'POST');
  assert.equal(requests[0].options.headers['X-CSRF-Token'],'test-token');
  assert.equal(document.querySelector('.modal-dialog'),null);
});

test('export preview refreshes for the selected connector',async t=>{
  const {window,document,ui}=await browser(t);
  const requests=[];
  window.fetch=async url=>{
    requests.push(url);
    return {ok:true,status:200,json:async()=>({preview:url})};
  };
  ui.setState({matter:{matter:{id:'test'}}});
  await ui.exportModal();
  document.querySelector('#export-connector').value='notary_demo';
  document.querySelector('#export-connector').dispatchEvent(new window.Event('change',{bubbles:true}));
  await new Promise(resolve=>setImmediate(resolve));
  assert.ok(requests.at(-1).includes('connector=notary_demo'));
  assert.ok(document.querySelector('#export-preview').textContent.includes('connector=notary_demo'));
  assert.equal(document.querySelector('#export-form [type=submit]').disabled,false);
});

test('decision details show complete previous values and login clears private modal content',async t=>{
  const {document,ui}=await browser(t);
  ui.setState({auditEvents:[{id:'event',action:'field_confirmed',actor:'Demo',created_at:'2026-10-22',
    details_json:JSON.stringify({previous:{value:'Previous Name',note:'Full old note'},review:{value:'Current Name'}})}]});
  document.querySelector('#app').innerHTML='<button data-action="audit-details" data-id="event">Details</button>';
  document.querySelector('[data-action=audit-details]').click();
  assert.ok(document.querySelector('.doc-preview').textContent.includes('Full old note'));
  ui.showLogin();
  assert.equal(document.querySelector('.modal-dialog'),null);
  assert.ok(!document.body.textContent.includes('Previous Name'));
});

test('reset links open directly without authentication and missing tokens explain recovery',async t=>{
  const {document,ui}=await browser(t,'#/reset-password?token=direct-link-token');
  assert.equal(document.querySelector('#reset-password-form').resetToken,'direct-link-token');
  assert.equal(document.querySelector('#login-form'),null);
  assert.equal(document.querySelector('[name=new_password]').getAttribute('minlength'),'12');
  assert.equal(document.querySelector('[name=new_password]').getAttribute('maxlength'),'128');
  ui.showResetPassword('');
  assert.equal(document.querySelector('#reset-password-form'),null);
  assert.ok(document.querySelector('[role=alert]').textContent.includes('incomplete'));
  assert.ok(document.querySelector('a[href="#/forgot-password"]'));
});

test('Forgot password submits the account email and displays a clearly labeled demo link',async t=>{
  const {window,document,ui}=await browser(t);
  ui.showLogin();
  assert.ok(document.querySelector('a[href="#/forgot-password"]'));
  ui.showForgotPassword();
  const requests=[];
  window.fetch=async(url,options)=>{
    requests.push({url,options});
    return {ok:true,status:200,json:async()=>({message:'Request received.',delivery:'demo',
      demo_reset_path:'/#/reset-password?token=demo-token',expires_in_minutes:30})};
  };
  document.querySelector('[name=email]').value='reviewer@keller.demo';
  document.querySelector('#reset-request-form').dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(requests[0].url,'/api/auth/forgot-password');
  assert.deepEqual(JSON.parse(requests[0].options.body),{email:'reviewer@keller.demo'});
  assert.equal(requests[0].options.headers['X-CSRF-Token'],undefined);
  const result=document.querySelector('#reset-request-result');
  assert.equal(result.hidden,false);
  assert.ok(result.textContent.includes('No email is sent'));
  assert.equal(document.querySelector('#demo-reset-link').getAttribute('href'),'/#/reset-password?token=demo-token');
});

test('Unknown accounts retain neutral guidance without an empty reset link',async t=>{
  const {window,document,ui}=await browser(t);
  ui.showForgotPassword();
  window.fetch=async()=>({ok:true,status:200,json:async()=>({message:'If eligible, instructions are available.',delivery:'demo'})});
  document.querySelector('[name=email]').value='unknown@example.test';
  document.querySelector('#reset-request-form').dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(document.querySelector('#demo-reset-link'),null);
  assert.ok(document.querySelector('#reset-request-result').textContent.includes('admin@keller.demo'));
});

test('reset confirmation checks matching passwords and handles expired links inline',async t=>{
  const {window,document,ui}=await browser(t);
  ui.showResetPassword('expired-token');
  const requests=[];
  window.fetch=async(url,options)=>{
    requests.push({url,options});
    return {ok:false,status:400,json:async()=>({detail:'This reset link is invalid or has expired. Request a new link.'})};
  };
  const form=document.querySelector('#reset-password-form');
  form.querySelector('[name=new_password]').value='A-long-new-password!';
  form.querySelector('[name=confirm_password]').value='A-different-password!';
  form.dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(requests.length,0);
  assert.ok(form.querySelector('[role=alert]').textContent.includes('Passwords do not match'));
  form.querySelector('[name=confirm_password]').value='A-long-new-password!';
  form.dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(requests[0].url,'/api/auth/reset-password');
  assert.equal(JSON.parse(requests[0].options.body).token,'expired-token');
  assert.ok(form.querySelector('[role=alert]').textContent.includes('expired'));
  assert.equal(form.querySelector('[type=submit]').disabled,false);
});

test('successful reset removes the token from the address and requests a new sign-in',async t=>{
  const {window,document}=await browser(t,'#/reset-password?token=single-use-token');
  window.fetch=async()=>({ok:true,status:200,json:async()=>({ok:true})});
  const form=document.querySelector('#reset-password-form');
  for(const input of form.querySelectorAll('input'))input.value='A-long-new-password!';
  form.dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(window.location.hash,'#/login?reset=success');
  assert.equal(form.resetToken,'');
  assert.ok(document.querySelector('.auth-notice').textContent.includes('Password updated'));
  assert.equal(document.querySelector('#login-form [name=password]').value,'');
  assert.equal(document.querySelector('.app-shell'),null);
});


test('a late workflow response cannot replace a newer page',async t=>{
  const {window,document,ui}=await browser(t);
  window.history.replaceState(null,'','#/workflows');
  let finish;
  window.fetch=()=>new Promise(resolve=>{finish=resolve;});
  const loading=ui.workflowsPage();
  window.history.replaceState(null,'','#/pilot');
  document.querySelector('#app').innerHTML='<p id="newer-page">Pilot page</p>';
  finish({ok:true,status:200,json:async()=>({rules:[]})});
  await assert.rejects(loading,error=>error.name==='AbortError');
  assert.equal(document.querySelector('#newer-page').textContent,'Pilot page');
});

const demoConfig={schemas:{property_purchase:{label:'Property purchase'}},field_meta:{},max_upload_mb:12,external_ai_enabled:false};
const demoMatter={id:'case-one',reference:'DEMO-1',title:'Synthetic matter',matter_type:'property_purchase',status:'approved'};
const response=body=>({ok:true,status:200,json:async()=>body});

test('intake tabs preserve drafts and expose the selected panel to assistive technology',async t=>{
  const {window,document,ui}=await browser(t);
  window.history.replaceState(null,'','#/intake');
  ui.setState({config:demoConfig});
  let requests=0;
  window.fetch=async()=>{requests++;return response({matters:[demoMatter]});};
  await ui.intakePage();
  const file=document.querySelector('#intake-method-tab-file');
  const paste=document.querySelector('#intake-method-tab-paste');
  assert.equal(file.getAttribute('aria-selected'),'true');
  assert.equal(paste.tabIndex,-1);
  paste.click();
  const draft=document.querySelector('#paste-text');
  draft.value='Buyer: A synthetic draft';
  document.querySelector('#paste-name').value='keep-this-label.txt';
  const panel=document.getElementById(paste.getAttribute('aria-controls'));
  assert.equal(panel.hidden,false);
  assert.equal(panel.getAttribute('aria-labelledby'),paste.id);
  assert.equal(document.getElementById(file.getAttribute('aria-controls')).hidden,true);
  file.click();paste.click();
  assert.equal(document.querySelector('#paste-text'),draft,'Switching panels keeps the original form mounted');
  assert.equal(draft.value,'Buyer: A synthetic draft');
  assert.equal(document.querySelector('#paste-name').value,'keep-this-label.txt');
  assert.equal(requests,1,'Switching tabs does not reload data or submit forms');
});

test('tab keyboard navigation wraps, supports Home and End, and keeps one tab stop',async t=>{
  const {window,document,ui}=await browser(t);
  document.querySelector('#app').innerHTML=ui.tabGroup('keyboard','Keyboard example',[
    {id:'first',label:'First',content:'First content'},
    {id:'second',label:'Second',content:'Second content'},
    {id:'last',label:'Last',content:'Last content'}
  ]);
  const tabs=[...document.querySelectorAll('[role=tab]')];
  const press=key=>document.activeElement.dispatchEvent(new window.KeyboardEvent('keydown',{key,bubbles:true,cancelable:true}));
  tabs[0].focus();press('ArrowLeft');
  assert.equal(document.activeElement,tabs[2]);
  press('ArrowRight');assert.equal(document.activeElement,tabs[0]);
  press('End');assert.equal(document.activeElement,tabs[2]);
  press('Home');assert.equal(document.activeElement,tabs[0]);
  press('ArrowRight');assert.equal(document.activeElement,tabs[1]);
  assert.equal(tabs.filter(tab=>tab.tabIndex===0).length,1);
  assert.equal(document.querySelectorAll('[role=tabpanel]:not([hidden])').length,1);
  assert.equal(document.querySelector('[role=tabpanel]:not([hidden])').textContent,'Second content');
});

test('tab selection survives a refresh, is scoped to its matter, and clears at sign-out',async t=>{
  const {document,ui}=await browser(t);
  const items=[{id:'review',label:'Review',content:'Fields'},{id:'exports',label:'Exports',content:'Files'}];
  const mount=()=>{document.querySelector('#app').innerHTML=ui.tabGroup('matter','Matter sections',items);};
  ui.setState({route:'/matter/first'});mount();
  document.querySelector('[data-tab=exports]').click();mount();
  assert.equal(document.querySelector('[aria-selected=true]').dataset.tab,'exports');
  ui.setState({route:'/matter/second'});mount();
  assert.equal(document.querySelector('[aria-selected=true]').dataset.tab,'review');
  ui.setState({route:'/matter/first'});mount();
  assert.equal(document.querySelector('[aria-selected=true]').dataset.tab,'exports');
  ui.showLogin();mount();
  assert.equal(document.querySelector('[aria-selected=true]').dataset.tab,'review');
});

test('settings tabs retain unsaved mappings and hide membership for a non-admin session',async t=>{
  const {window,document,ui}=await browser(t);
  window.history.replaceState(null,'','#/settings');
  ui.setState({config:demoConfig,user:{role:'admin',name:'Synthetic Admin',workspace:'Demo'}});
  let memberRequests=0;
  window.fetch=async url=>{
    if(url==='/api/settings/users'){memberRequests++;return response({users:[{name:'Demo Member',email:'member@example.test',role:'reviewer'}]});}
    if(url==='/api/settings/mappings')return response({mappings:{buyer_name:'Buyer.Name'}});
    return response({profile:'demo',storage_encryption:false});
  };
  await ui.settingsPage();
  const input=document.querySelector('.mapping-input');input.value='Unsaved.Buyer';
  document.querySelector('[data-tab=account]').click();
  document.querySelector('[data-tab=mappings]').click();
  assert.equal(document.querySelector('.mapping-input').value,'Unsaved.Buyer');
  document.querySelector('[data-tab=members]').click();
  ui.setState({user:{role:'reviewer',name:'Synthetic Reviewer',workspace:'Demo'}});
  await ui.settingsPage();
  assert.equal(memberRequests,1,'Membership is requested only for the admin');
  assert.equal(document.querySelector('[data-tab=members]'),null);
  assert.ok(!document.querySelector('#app').textContent.includes('member@example.test'));
  assert.equal(document.querySelector('[aria-selected=true]').dataset.tab,'mappings');
  assert.equal(document.querySelector('.mapping-input').disabled,true);
});

test('saving a pilot baseline refreshes the values without leaving Record measurements',async t=>{
  const {window,document,ui}=await browser(t);
  window.history.replaceState(null,'','#/pilot');
  ui.setState({config:demoConfig,user:{role:'admin',name:'Synthetic Admin',workspace:'Demo'}});
  const rate={percent:null,numerator:0,denominator:0};
  const data={baseline:null,pilot_minutes:null,time_saved_percent:null,eligible_matters:0,timed_matters:0,
    coverage:rate,corrections:rate,low_confidence:rate,audit_coverage:rate,transfers:[],definitions:{time:'Reported time'}};
  window.fetch=async(url,options={})=>{
    if(url==='/api/matters')return response({matters:[demoMatter]});
    if(options.method==='PUT'){data.baseline=JSON.parse(options.body);return response({ok:true});}
    return response(data);
  };
  await ui.pilotPage();
  document.querySelector('[data-tab=record]').click();
  const form=document.querySelector('#pilot-baseline-form');
  form.elements.minutes.value='20';form.elements.sample_size.value='3';
  form.dispatchEvent(new window.Event('submit',{bubbles:true,cancelable:true}));
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(document.querySelector('[aria-selected=true]').dataset.tab,'record');
  assert.equal(document.querySelector('#pilot-baseline-form').elements.minutes.value,'20');
  assert.equal(document.querySelector('#pilot-baseline-form').closest('[role=tabpanel]').hidden,false);
});

test('integration preview stays ready when inspecting receipts and connector tabs',async t=>{
  const {window,document,ui}=await browser(t);
  window.history.replaceState(null,'','#/integrations');
  ui.setState({config:demoConfig});
  let previews=0;
  window.fetch=async url=>{
    if(url==='/api/matters')return response({matters:[demoMatter]});
    if(url==='/api/integrations/dry-run'){previews++;return response({preview_hash:'approved-fingerprint',payload:{approved:'synthetic payload'}});}
    return response({webhook_configured:false,receiver_records:[],transfers:[]});
  };
  await ui.integrationsPage();
  document.querySelector('[data-action=preview-transfer]').click();
  await new Promise(resolve=>setImmediate(resolve));
  const form=document.querySelector('#integration-form');
  const preview=document.querySelector('#transfer-preview').textContent;
  assert.equal(form.querySelector('[type=submit]').disabled,false);
  document.querySelector('[data-tab=receipts]').click();
  document.querySelector('[data-tab=connectors]').click();
  document.querySelector('[data-tab=delivery]').click();
  assert.equal(document.querySelector('#integration-form'),form);
  assert.equal(document.querySelector('#transfer-preview').textContent,preview);
  assert.equal(form.querySelector('[type=submit]').disabled,false);
  assert.equal(previews,1);
});
