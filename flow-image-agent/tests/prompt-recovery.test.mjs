import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
import {classifyFailure,newFailure,loadHistory,revise} from '../prompt-recovery.mjs';
import {isQuotaLikeError} from '../flow-accounts.mjs';

test('only policy errors qualify, historical cards do not',()=>{
 assert.equal(classifyFailure('This generation might violate our policies.'),'policy_rejection');
 assert.equal(classifyFailure('Daily limit reached'),'rate_limit');
 assert.equal(classifyFailure('Timeout waiting for generation'),'unknown');
 assert.equal(newFailure({'might violate our policies':1},{'might violate our policies':1}),null);
 assert.equal(newFailure({'might violate our policies':1},{'might violate our policies':2}),'might violate our policies');
});
test('revision budget survives restart; originals retained',async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'flow-repair-'));
 try {
  let calls=0; const api=async()=>{calls++;return {action:'rewrite',prompt:'Scene 1. A calm mountain landscape, hand drawn, 16:9.',reason:'Simplified'};};
  for(let i=0;i<3;i++)await revise(loadHistory(dir,1,'Scene 1. Original'),'', 'policy',api);
  assert.equal(calls,2);const data=loadHistory(dir,1,'Scene 1. Original').data;
  assert.equal(data.original_prompt,'Scene 1. Original');assert.equal(data.revisions.length,2);
  assert.throws(()=>loadHistory(dir,1,'Different scene'),/changed/);
 }finally{fs.rmSync(dir,{recursive:true});}
});
test('service failure is saved and does not loop',async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'flow-repair-'));
 try {
 const history=loadHistory(dir,1,'Original');
 assert.equal(await revise(history,'','policy',async()=>{throw new Error('offline')}),null);
 assert.equal(loadHistory(dir,1,'Original').data.revisions[0].status,'needs_review');
 }finally{fs.rmSync(dir,{recursive:true});}
});
for (const failure of ['policy_rejection', 'timeout', 'generation_failed']) {
test(`${failure}: two revisions then mark scene failed and save next scene`,async()=>{
 const source=fs.readFileSync(fileURLToPath(new URL('../run-images.mjs',import.meta.url)),'utf8');
 const fn=source.slice(source.indexOf('async function runJob('),source.indexOf('\nasync function main()',source.indexOf('async function runJob(')));
 let claimed=0, current=0, revisions=0;const submissions=[],saved=[],statuses=[];
 const sandbox={console:{log(){},error(){}},process:{exitCode:0},ROOT:'/fake',path,isQuotaLikeError,
 configureFlow:async()=>{},recordOutcome(){},monitorWrite(){},sleep:async()=>{},findExistingTileUrl:async()=>null,
 failureSnapshot:async()=>({}),fillPrompt:async()=>{},clickGenerate:async()=>{submissions.push(current)},
 waitForNewImage:async()=>{if(current===1){const e=new Error(failure==='timeout'?'No confirmed new image within timeout (needs review).':'Generation failed');if(failure!=='timeout')e.category=failure;throw e;}return ['image'];},
 download2K:async()=>'/tmp/image.jpg',
 loadHistory:()=>({data:{revisions:[]}}),revise:async(h)=>{if(revisions===2)return null;revisions++;h.data.revisions.push({});return `Revision ${revisions}`;},
 helperFetch:async(_h,_t,url,{body})=>{
 if(url.endsWith('claim-next')) {claimed++;current=claimed;return claimed<=2?{scene:{scene:claimed,text:`Scene ${claimed}. Landscape`}}:{reason:'done',summary:{failed:1}};}
 if(url.endsWith('/save')){saved.push(current);return {saved:{path:'image',width:2752,height:1536}};}
 statuses.push(body);return {};
 }};
 vm.createContext(sandbox);vm.runInContext(fn,sandbox);
 await sandbox.runJob({page:{url:()=> 'https://flow.google.com/project/test',evaluate:async()=>[],locator:()=>({count:async()=>0})}},{helperUrl:'',token:'',jobId:'test',delaySec:0,regenerate:false,imagesDir:'/tmp'});
 assert.deepEqual(submissions,[1,1,1,2]);assert.deepEqual(saved,[2]);
 assert(statuses.some(s=>s.status==='failed'&&s.error_category===(failure==='timeout'?'generation_failed':failure)));
 assert.equal(sandbox.process.exitCode,1);
});
}
