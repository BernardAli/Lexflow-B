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
      showForgotPassword,showResetPassword,render,workflowsPage,
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
