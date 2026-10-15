import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import { accountHasQuota, incrementAccountCount, markAccountExhausted, isQuotaLikeError, nextAccount } from '../flow-accounts.mjs';

const source = fs.readFileSync(new URL('../run-images.mjs', import.meta.url), 'utf8');
const fn = source.slice(source.indexOf('async function runJob('), source.indexOf('\nasync function main()'));

function runner({ adopt = false, downloadFails = false, quotaFails = false, generationFails = false, closed = false, sceneCount = 1 } = {}) {
  const accounts = [{ id:'a', max_images:115 }, { id:'b', max_images:115 }];
  const state = { current_id:'a', counts:{} };
  const page = { isClosed:()=>closed, url:()=> 'https://flow.google.com/project/test', evaluate:async()=>[], locator:()=>({ count:async()=>0 }) };
  const session = { page, account:accounts[0] };
  let claims = 0, generated = 0, switches = 0, configurations = 0;
  const statuses = [], saved = [];
  const sandbox = {
    console:{ log(){}, error(){} }, process:{ exitCode:0 }, ROOT:'/fake', LOCAL:'/fake', path,
    accountHasQuota, incrementAccountCount, markAccountExhausted, isQuotaLikeError,
    saveAccountState(){}, configureFlow:async()=>{ configurations++; }, monitorWrite(){}, sleep:async()=>{},
    findExistingTileUrl:async()=>adopt ? 'existing' : null, fillPrompt:async()=>{},
    failureSnapshot:async()=>({}), clickGenerate:async()=>{ generated++; },
    waitForNewImage:async()=>{ if (quotaFails) throw new Error('Daily limit reached'); if (generationFails && claims === 1) throw new Error('No confirmed new image within timeout (needs review).'); return ['new']; },
    download2K:async()=>{ if (downloadFails && claims === 1) throw new Error('menu missing'); return '/tmp/image.jpg'; },
    switchFlowAccount:async()=>{
      const next = nextAccount(accounts, state, { requireSignedIn:false });
      if (!next) throw new Error('all profiles exhausted');
      switches++; session.account = next; state.current_id = next.id;
    },
    helperFetch:async(_h,_t,url,{body})=>{
      if (url.endsWith('claim-next')) return ++claims <= sceneCount ? { scene:{ scene:46+claims, text:`Scene ${46+claims}` } } : { reason:'done', summary:{failed:statuses.filter(s=>s.status==='failed').length} };
      if (url.endsWith('/save')) { saved.push(46+claims); return { saved:{ path:'image', width:2752, height:1536 } }; }
      statuses.push(body);
      return {};
    },
  };
  vm.createContext(sandbox); vm.runInContext(fn, sandbox);
  return { state, statuses, saved, sandbox, counts:()=>({ generated, switches, configurations }), run:()=>sandbox.runJob(session, { helperUrl:'',token:'',jobId:'test',delaySec:0,regenerate:false,imagesDir:'/tmp',accounts,state }) };
}

test('settings configure once across multiple scenes in the same project',async()=>{
  const r = runner({sceneCount:2});
  await r.run();
  assert.equal(r.counts().configurations,1);
  assert.deepEqual(r.saved,[47,48]);
});

test('generated image counts even when download fails', async()=>{
  const r = runner({ downloadFails:true });
  await r.run();
  assert.equal(r.state.counts.a, 1);
});

for (const failure of ['generationFails', 'downloadFails']) {
  test(`${failure}: mark scene failed and save next scene without pausing queue`, async()=>{
    const r = runner({ [failure]:true, sceneCount:2 });
    await r.run();
    assert(r.statuses.some(s=>s.status==='failed'));
    assert(!r.statuses.some(s=>s.status==='needs_review'));
    assert.deepEqual(r.saved, [48]);
    assert.equal(r.sandbox.process.exitCode, 1);
  });
}

test('closed browser stops rather than skipping every remaining scene', async()=>{
  const r = runner({ downloadFails:true, closed:true, sceneCount:2 });
  await assert.rejects(r.run(), /menu missing/);
  assert(r.statuses.some(s=>s.status==='needs_review'));
  assert.deepEqual(r.saved, []);
});

for (const step of ['fillPrompt','clickGenerate']) {
  test(`${step} failure pauses the job before claiming another scene`,async()=>{
    const r=runner({sceneCount:3});
    let calls=0;
    r.sandbox[step]=async()=>{calls++; throw new Error('UI timeout');};
    await assert.rejects(r.run(),/UI timeout/);
    assert.equal(calls,1);
    assert(r.statuses.some(s=>s.status==='needs_review' && s.error_category==='ui_blocked'));
    assert.deepEqual(r.saved,[]);
  });
}

test('adopting gallery result does not charge generation twice', async()=>{
  const r = runner({ adopt:true }); await r.run();
  assert.equal(r.state.counts.a || 0, 0);
  assert.equal(r.counts().generated, 0);
});

test('quota rotation skips exhausted accounts and terminates rather than circles', async()=>{
  const r = runner({ quotaFails:true });
  await assert.rejects(r.run(), /all profiles exhausted/);
  assert.equal(r.counts().switches, 1);
  assert.equal(r.counts().generated, 2);
  assert.equal(r.state.exhausted.a, true);
  assert.equal(r.state.exhausted.b, true);
});
