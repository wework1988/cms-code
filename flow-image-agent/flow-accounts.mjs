/**
 * Rotate Google Flow Chrome profiles when one Gmail hits the ~120 image cap.
 * Passwords are never stored: each profile must already be signed into Flow.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const DEFAULT_MAX = 115;
const STATE_NAME = 'flow-account-state.json';

export function todayStamp(now = new Date()) {
  return now.toISOString().slice(0, 10);
}

export function expandHome(raw) {
  const text = String(raw || '').trim();
  if (!text) return text;
  if (text.startsWith('~/')) return path.join(os.homedir(), text.slice(2));
  return text;
}

export function isQuotaLikeError(message) {
  return /daily limit|quota exceeded|too many requests|rate limit|try again tomorrow|usage limit|limit reached/i
    .test(String(message || ''));
}

export function loadAccountPool(config, { localDir, defaultProfile, defaultProjectUrl } = {}) {
  const configured = Array.isArray(config?.flow_accounts) ? config.flow_accounts : [];
  const accounts = configured
    .filter((row) => row && row.enabled !== false)
    .map((row, index) => ({
      id: String(row.id || `account-${index + 1}`),
      email: String(row.email || '').trim(),
      profile_dir: expandHome(row.profile_dir || defaultProfile || ''),
      project_url: String(row.project_url || '').trim() || defaultProjectUrl || '',
      max_images: Number(row.max_images) > 0 ? Number(row.max_images) : DEFAULT_MAX,
    }))
    .filter((row) => row.profile_dir);
  if (accounts.length) return accounts;
  if (defaultProfile) {
    return [{
      id: 'default',
      email: '',
      profile_dir: expandHome(defaultProfile),
      project_url: defaultProjectUrl || '',
      max_images: DEFAULT_MAX,
    }];
  }
  return [];
}

export function profileLooksSignedIn(profileDir) {
  const root = path.join(expandHome(profileDir), 'Default');
  return ['Cookies', 'Login Data', 'Network/Cookies'].some((rel) =>
    fs.existsSync(path.join(root, rel)),
  );
}

function statePath(localDir) {
  return path.join(localDir, STATE_NAME);
}

export function loadAccountState(localDir, accounts, now = new Date()) {
  const file = statePath(localDir);
  const day = todayStamp(now);
  let data = { current_id: accounts[0]?.id || null, day, counts: {} };
  try {
    if (fs.existsSync(file)) {
      const loaded = JSON.parse(fs.readFileSync(file, 'utf8'));
      if (loaded && typeof loaded === 'object') data = { ...data, ...loaded };
    }
  } catch {
    /* keep defaults */
  }
  if (data.day !== day) {
    data = { current_id: data.current_id || accounts[0]?.id || null, day, counts: {} };
  }
  if (!accounts.some((a) => a.id === data.current_id)) {
    data.current_id = accounts[0]?.id || null;
  }
  return data;
}

export function saveAccountState(localDir, state) {
  fs.mkdirSync(localDir, { recursive: true });
  const tmp = `${statePath(localDir)}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(state, null, 2));
  fs.renameSync(tmp, statePath(localDir));
}

export function currentAccount(accounts, state) {
  return accounts.find((a) => a.id === state.current_id) || accounts[0] || null;
}

export function refreshAccountDay(state, now = new Date()) {
  const day = todayStamp(now);
  if (state.day && state.day !== day) {
    state.counts = {};
    state.exhausted = {};
  }
  state.day = day;
}

export function accountHasQuota(account, state) {
  refreshAccountDay(state);
  const used = Number(state.counts?.[account.id] || 0);
  return !state.exhausted?.[account.id] && used < account.max_images;
}

export function markAccountExhausted(state, accountId) {
  refreshAccountDay(state);
  state.exhausted ||= {};
  state.exhausted[accountId] = true;
}

export function assertAccountEmail(account, label) {
  if (!account?.email) return;
  const emails = String(label || '').match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi) || [];
  if (!emails.some(email => email.toLowerCase() === account.email.toLowerCase())) {
    throw new Error(`Flow Gmail does not match ${account.id} (${account.email}). Open its dedicated Chrome profile and sign into Flow before retrying.`);
  }
}

export function incrementAccountCount(state, accountId) {
  refreshAccountDay(state);
  state.counts = state.counts || {};
  state.counts[accountId] = Number(state.counts[accountId] || 0) + 1;
}

export function nextAccount(accounts, state, { requireSignedIn = true } = {}) {
  if (accounts.length < 2) return null;
  const start = Math.max(0, accounts.findIndex((a) => a.id === state.current_id));
  for (let i = 1; i <= accounts.length; i++) {
    const candidate = accounts[(start + i) % accounts.length];
    if (!accountHasQuota(candidate, state)) continue;
    if (requireSignedIn && !profileLooksSignedIn(candidate.profile_dir)) continue;
    if (candidate.id === state.current_id && accounts.length > 1) continue;
    return candidate;
  }
  return null;
}
