import assert from 'node:assert/strict';
import { fillPrompt, normalizePrompt } from './flow_prompt.mjs';

assert.equal(normalizePrompt('A\n B\u00a0 C'), 'A B C');
const makePage = actual => {
  let value;
  const editor = {count: async () => 1, fill: async v => {value = v;},
    evaluate: async () => actual ? actual(value) : value};
  return {locator: () => editor};
};
await fillPrompt(makePage(), 'Scene 1.\nपहला दृश्य\nFull prompt.');
await fillPrompt(makePage(v => v.replaceAll(' ', '\u00a0')), 'One two three');
await assert.rejects(fillPrompt(makePage(() => 'One two'), 'One two three'), /did not match/);
console.log('Prompt-entry regression checks passed');
