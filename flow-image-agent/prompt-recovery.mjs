import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawn} from 'node:child_process';

export const MAX_REVISIONS = 2;
export function classifyFailure(message) {
  if (/unusual activity/i.test(message)) return 'generation_failed';
  if (/might violate our policies|violates? (?:our |the )?(?:content )?polic(?:y|ies)/i.test(message)) return 'policy_rejection';
  if (/daily limit|quota exceeded|too many requests|rate limit|try again tomorrow/i.test(message)) return 'rate_limit';
  return 'unknown';
}
// Count visible, specific UI messages, excluding historical cards using a pre-submit baseline.
export async function failureSnapshot(page) {
  return page.evaluate(() => {
    const phrases=['might violate our policies','violates our policies','daily limit','quota exceeded','too many requests','rate limit','try again tomorrow','unusual activity'];
    const counts={};
    for(const element of document.querySelectorAll('p,span,div,[role="alert"]')) {
      if (!element.getClientRects().length) continue;
      const text=(element.innerText || '').trim();
      if (text.length>600) continue;
      if ([...element.children].some(child=>phrases.some(phrase=>(child.innerText || '').toLowerCase().includes(phrase)))) continue;
      if (phrases.some(phrase=>text.toLowerCase().includes(phrase))) counts[text]=(counts[text]||0)+1;
    }
    return counts;
  });
}
export function newFailure(before, after) {
  return Object.keys(after).find(text=>after[text]>(before[text]||0)) || null;
}
function save(file,data) {
  fs.mkdirSync(path.dirname(file),{recursive:true});
  const temp=`${file}.${process.pid}.tmp`;fs.writeFileSync(temp,JSON.stringify(data,null,2));fs.renameSync(temp,file);
}
export function loadHistory(dir,scene,original) {
  const file=path.join(dir,'prompt-revisions',`${String(scene).padStart(3,'0')}.json`);
  const hash=crypto.createHash('sha256').update(original).digest('hex');
  const data=fs.existsSync(file)?JSON.parse(fs.readFileSync(file,'utf8')):{scene,original_prompt:original,prompt_hash:hash,revisions:[]};
  if(data.prompt_hash!==hash) throw new Error('Prompt changed since repair history; review required.');
  return {file,data};
}
export function recordOutcome(history, status) {
  const latest=history?.data.revisions.at(-1);
  if (!latest) return;
  latest.status=status;latest.outcome_at=new Date().toISOString();save(history.file,history.data);
}
export async function revise(history, workerRoot, rejection, run=runRepair) {
  if(history.data.revisions.length>=MAX_REVISIONS) return null;
  const revision={number:history.data.revisions.length+1,created_at:new Date().toISOString(),rejection,status:'requested'};
  history.data.revisions.push(revision);save(history.file,history.data); // reserve budget before API call
  try {
    const result=await run(workerRoot,{original_prompt:history.data.original_prompt,
      previous_prompt:history.data.revisions.at(-2)?.prompt || history.data.original_prompt,rejection,revision:revision.number});
    Object.assign(revision,result,{status:result.action==='rewrite'?'ready':'needs_review'});
    save(history.file,history.data);
    return result.action==='rewrite'?result.prompt:null;
  } catch(error) {
    revision.status='needs_review';revision.reason='Repair service failed';save(history.file,history.data);return null;
  }
}
function runRepair(root,data) {
  return new Promise((resolve,reject)=>{
    const proc=spawn(path.join(root,'.venv/bin/python'),[path.join(root,'repair_image_prompt.py')],{cwd:root,stdio:['pipe','pipe','pipe']});
    let output='';const timer=setTimeout(()=>{proc.kill('SIGTERM');reject(new Error('Repair timeout'));},75000);
    proc.stdout.on('data',chunk=>{output+=chunk;if(output.length>100000)proc.kill();});
    proc.stderr.resume();proc.on('error',error=>{clearTimeout(timer);reject(error);});
    proc.on('close',code=>{clearTimeout(timer);try {const result=JSON.parse(output);if(code)reject(new Error('Repair failed'));else resolve(result);}catch(error){reject(error);}});
    proc.stdin.on('error',()=>{});proc.stdin.end(JSON.stringify(data));
  });
}
