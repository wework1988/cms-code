import assert from 'node:assert/strict';
import { isQuotaLikeError, nextAccount, accountHasQuota, markAccountExhausted, assertAccountEmail, refreshAccountDay } from '../flow-accounts.mjs';

assert.equal(isQuotaLikeError('Flow did not start a new generation (needs review).'), false);
assert.equal(isQuotaLikeError('daily limit reached'), true);
assert.equal(isQuotaLikeError('policy rejection'), false);

const accounts = [
  { id: 'a', profile_dir: '/tmp/a', max_images: 115 },
  { id: 'b', profile_dir: '/tmp/b', max_images: 115 },
];
const state = { current_id: 'a', counts: { a: 115, b: 0 } };
assert.equal(accountHasQuota(accounts[0], state), false);
assert.equal(accountHasQuota(accounts[1], state), true);
assert.equal(nextAccount(accounts, state, { requireSignedIn: false })?.id, 'b');
state.counts.a = 0;
markAccountExhausted(state, 'a');
state.current_id = 'b';
assert.equal(nextAccount(accounts, state, { requireSignedIn: false }), null);
markAccountExhausted(state, 'b');
assert.equal(accountHasQuota(accounts[1], state), false);
refreshAccountDay(state, new Date('2099-01-01T00:00:00Z'));
assert.deepEqual(state.counts, {});
assert.deepEqual(state.exhausted, {});
assertAccountEmail({ id:'a',email:'first@example.com' }, 'Google Account: First (FIRST@example.com)');
assert.throws(() => assertAccountEmail({ id:'a',email:'first@example.com' }, 'Google Account: Second (second@example.com)'), /does not match/);
assert.throws(() => assertAccountEmail({ id:'a',email:'first@example.com' }, ''), /does not match/);
console.log('flow-accounts tests ok');
