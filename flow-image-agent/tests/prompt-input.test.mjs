import test from 'node:test';
import assert from 'node:assert/strict';
import { enterPrompt, submitPrompt } from '../prompt-input.mjs';

function fixture({ contenteditable = false, count = 1, corrupt = false, neverReady = false, overlays = 0, stuck = false } = {}) {
  const actions = [];
  const element = contenteditable ? { innerText:'' } : { value:'' };
  const buttonElement = { isConnected:true, disabled:true, getAttribute:()=>null };
  const editor = {
    first(){ return this; }, waitFor:async()=>{}, count:async()=>count,
    click:async()=>{ throw new Error('Editor click must not block prompt entry'); },
    fill:async text=>{ actions.push('fill'); element[contenteditable?'innerText':'value'] = corrupt ? text.slice(0,-1) : text; },
    evaluate:async fn=>fn(element),
  };
  const button = {
    focus:async()=>{}, isVisible:async()=>true, isEnabled:async()=>!buttonElement.disabled,
    getAttribute:async()=>null,
    waitFor:async()=>{}, elementHandle:async()=>({ element:buttonElement, dispose:async()=>{} }),
    click:async()=>{ throw new Error('Pointer stability must not block submission'); },
    press:async key=>{ assert.equal(key,'Space'); assert.equal(buttonElement.disabled,false); actions.push('submit'); },
  };
  const page = {
    bringToFront:async()=>{ actions.push('foreground'); },
    keyboard:{press:async key=>{ assert.equal(key,'Escape'); actions.push('escape'); if (!stuck) overlays=Math.max(0,overlays-1); }},
    locator:selector=>selector.includes('cdk-overlay-backdrop') ? {
      count:async()=>overlays, first(){return this;},
      waitFor:async()=>{if(overlays) {const error=new Error('still visible'); error.name='TimeoutError'; throw error;}},
    } : editor, getByRole:()=>button,
    waitForFunction:async(fn,handle)=>{
      actions.push('wait enabled');
      assert.equal(fn(handle.element),false);
      if (neverReady) throw new Error('Generate readiness timeout');
      buttonElement.disabled=false;
      assert.equal(fn(handle.element),true);
    },
  };
  return { page, element, actions };
}

for (const contenteditable of [false,true]) {
  test(`verified entry and enabled submission (${contenteditable?'contenteditable':'textarea'})`, async()=>{
    const f=fixture({contenteditable});
    await enterPrompt(f.page,'Scene 1. Landscape.');
    await submitPrompt(f.page,'Scene 1. Landscape.');
    assert.deepEqual(f.actions,['foreground','fill','foreground','wait enabled','submit']);
  });
}

test('truncated input is rejected before submission',async()=>{
  const f=fixture({corrupt:true});
  await assert.rejects(enterPrompt(f.page,'Scene 1. Landscape.'),/verify/);
  assert(!f.actions.includes('submit'));
});

test('nested download menus close before prompt entry', async()=>{
  const f=fixture({overlays:2});
  await enterPrompt(f.page,'Original');
  await submitPrompt(f.page,'Original');
  assert.deepEqual(f.actions,['foreground','escape','escape','fill','foreground','wait enabled','submit']);
});

test('submission dismisses an overlay that appeared after entry', async()=>{
  const f=fixture({overlays:1});
  f.element.value='Original';
  await submitPrompt(f.page,'Original');
  assert.deepEqual(f.actions,['foreground','escape','wait enabled','submit']);
});

test('stuck backdrop stops before filling or submitting', async()=>{
  for (const operation of [enterPrompt,submitPrompt]) {
    const f=fixture({overlays:1,stuck:true});
    await assert.rejects(operation(f.page,'Original'),error=>error.category==='ui_blocked');
    assert.deepEqual(f.actions,['foreground','escape','escape','escape']);
  }
});
test('text changed after entry is rejected before submission',async()=>{
  const f=fixture(); await enterPrompt(f.page,'Original'); f.element.value='Changed';
  await assert.rejects(submitPrompt(f.page,'Original'),/verify/);
  assert(!f.actions.includes('submit'));
});
test('disabled Generate is never clicked',async()=>{
  const f=fixture({neverReady:true}); await enterPrompt(f.page,'Original');
  await assert.rejects(submitPrompt(f.page,'Original'),/readiness timeout/);
  assert(!f.actions.includes('submit'));
});
test('ambiguous prompt editors are never filled',async()=>{
  const f=fixture({count:2});
  await assert.rejects(enterPrompt(f.page,'Original'),/unambiguously/);
  assert.deepEqual(f.actions,['foreground']);
});

test('submission activation failure is propagated without a duplicate activation', async()=>{
  const f=fixture();
  let clicks=0;
  const button=f.page.getByRole();
  button.press=async()=>{ clicks++; throw new Error('locator.press: Timeout'); };
  await enterPrompt(f.page,'Original');
  await assert.rejects(submitPrompt(f.page,'Original'),/locator.press: Timeout/);
  assert.equal(clicks,1);
});

test('button disabled after focus is never activated',async()=>{
  const f=fixture();
  await enterPrompt(f.page,'Original');
  f.page.getByRole().isEnabled=async()=>false;
  await assert.rejects(submitPrompt(f.page,'Original'),/became unavailable/);
  assert(!f.actions.includes('submit'));
});
