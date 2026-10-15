import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

test('fresh project opens settings and waits for Image radio before configuring', async () => {
  const source = fs.readFileSync(new URL('../run-images.mjs', import.meta.url), 'utf8');
  const fn = source.slice(source.indexOf('async function configureFlow('), source.indexOf('\nasync function fillPrompt('));
  const actions = [];
  let visible = false;
  const page = {
    getByRole(role, options) {
      if (role === 'radio') return {
        isVisible: async () => visible,
        waitFor: async () => { assert(visible); actions.push('panel ready'); },
      };
      assert.equal(options.name, 'Settings trigger');
      return { click: async () => { visible = true; actions.push('open settings'); } };
    },
    evaluate: async fn => String(fn).includes('listLabels') ? ['Settings trigger'] : true,
  };
  const sandbox = { console:{log(){}}, sleep:async()=>{}, ensurePageHelpers:async()=>{}, waitForFlowWorkspace:async()=>{},
    clickNamedControl:async(_page,name)=>{ actions.push(name); } };
  vm.createContext(sandbox); vm.runInContext(fn, sandbox);
  await sandbox.configureFlow(page);
  assert.deepEqual(actions, ['open settings','panel ready','Image','16:9','x1','Settings trigger']);
});
