import test from 'node:test';
import assert from 'node:assert/strict';
import { connectFlowBrowser } from '../connect-flow-browser.mjs';

test('existing context connects without overrides and enables browser download events', async()=>{
  const context = {}, calls = [];
  const browser = { contexts:()=>[context], newBrowserCDPSession:async()=>({
    send:async(method,params)=>{calls.push({method,params});}, detach:async()=>{calls.push('detach');},
  }) };
  const chromium = { connectOverCDP:async(endpoint,options)=>{
    assert.equal(endpoint,'http://localhost:9222');
    assert.deepEqual(options,{noDefaults:true,artifactsDir:'/tmp/downloads'});
    return browser;
  } };
  const result = await connectFlowBrowser(chromium,'http://localhost:9222','/tmp/downloads');
  assert.equal(result.browser, browser);
  assert.equal(result.context, context);
  assert(result.downloadSession);
  assert.deepEqual(calls,[{method:'Browser.setDownloadBehavior',params:{behavior:'allowAndName',downloadPath:'/tmp/downloads',eventsEnabled:true}}]);
});

test('unsupported download management is reported instead of silently waiting for downloads',async()=>{
  let detached=false;
  const chromium={connectOverCDP:async()=>({contexts:()=>[{}],newBrowserCDPSession:async()=>({
    send:async()=>{throw new Error('unsupported');},detach:async()=>{detached=true;},
  })})};
  await assert.rejects(connectFlowBrowser(chromium,'endpoint','/tmp/downloads'),/download setup failed before submission/);
  assert(detached);
});
