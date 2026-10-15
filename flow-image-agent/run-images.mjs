#!/usr/bin/env node
/**
 * One-command CMS Flow image runner.
 *
 * Starts the local helper (if needed), creates a job, opens Chrome with a
 * persistent Google-signed-in profile, drives Flow (Nano Banana 2.1 / 16:9 / 2K),
 * and saves images into <story>/images/.
 *
 * Usage:
 *   ./scripts/run_images.sh 164-how-captain-saved-video-done --first-two
 *   ./scripts/run_images.sh general/164-how-captain-saved-video-done --from 1 --to 2
 *   FLOW_PROJECT_URL=https://labs.google/.../project/... ./scripts/run_images.sh 164-... --first-two
 */

import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { classifyFailure, failureSnapshot, newFailure, loadHistory, revise, recordOutcome } from './prompt-recovery.mjs';
import { select2KMenu } from './download-menu.mjs';
import { enterPrompt, submitPrompt } from './prompt-input.mjs';
import { connectFlowBrowser } from './connect-flow-browser.mjs';
import { trackPageDownloads, downloadFromPage } from './cdp-download.mjs';
import {
  loadAccountPool,
  loadAccountState,
  saveAccountState,
  currentAccount,
  nextAccount,
  incrementAccountCount,
  markAccountExhausted,
  assertAccountEmail,
  accountHasQuota,
  isQuotaLikeError,
  profileLooksSignedIn,
} from './flow-accounts.mjs';


// Read-only monitoring: telemetry failures never interrupt generation.
let monitorPath = null, monitorPage = null, monitorTimer = null;
let monitorData = {state: 'starting', browser: 'unknown', scenes: {}};
function monitorWrite(state, scene = null) {
  if (state) {
    monitorData.state = state; monitorData.updated_at = Date.now()/1000;
    if (scene !== null) {
      monitorData.scene = scene;
      monitorData.scenes[String(scene)] = {state, updated_at: monitorData.updated_at};
    }
  }
  monitorData.heartbeat_at = Date.now()/1000;
  try { if (monitorPage) {
    const browser = monitorPage.context().browser();
    monitorData.browser = monitorPage.isClosed() || (browser && !browser.isConnected()) ? 'disconnected' : 'connected';
  } } catch (_) { monitorData.browser = 'unknown'; }
  if (!monitorPath) return;
  try {
    fs.mkdirSync(path.dirname(monitorPath), {recursive:true});
    const tmp = `${monitorPath}.${process.pid}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(monitorData)); fs.renameSync(tmp,monitorPath);
  } catch (_) { /* Status remains stale when storage is unavailable. */ }
}
function monitorStart(file) {
  monitorPath = file; monitorWrite('starting');
  monitorTimer = setInterval(() => monitorWrite(), 20000); monitorTimer.unref();
}
process.on('exit', code => {
  clearInterval(monitorTimer);
  monitorWrite(code ? 'failed' : 'exited');
});

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = __dirname;
const LOCAL = path.join(ROOT, '.local');
const DOWNLOADS = path.join(LOCAL, 'downloads');
const PROJECT_URL_FILE = path.join(LOCAL, 'flow-project-url.txt');
const CONFIG_PATH = path.join(ROOT, 'config.json');
const HELPER_SCRIPT = path.join(ROOT, 'scripts', 'run_helper.sh');
const START_CHROME_SCRIPT = path.join(ROOT, 'scripts', 'start_chrome_debug.sh');
const DEFAULT_CDP = process.env.CDP_URL || 'http://127.0.0.1:9222';
const REAL_CHROME_PROFILE = process.env.CHROME_USER_DATA_DIR
  || path.join(os.homedir(), 'Library', 'Application Support', 'Google', 'Chrome');
// Chrome refuses remote debugging on the default profile path; agent uses a clone.
const FLOW_CHROME_PROFILE = process.env.CHROME_FLOW_USER_DATA_DIR
  || path.join(os.homedir(), 'Library', 'Application Support', 'Google', 'Chrome-FlowAgent');

function loadPlaywright() {
  const require = createRequire(import.meta.url);
  const candidates = [
    path.join(ROOT, 'node_modules', 'playwright'),
    path.join(ROOT, '..', 'playright-automation', 'node_modules', 'playwright'),
  ];
  for (const c of candidates) {
    try {
      return require(c);
    } catch {
      /* try next */
    }
  }
  throw new Error('Playwright not found. Run: cd flow-image-agent && npm install');
}

const { chromium } = loadPlaywright();

function parseArgs(argv) {
  const args = {
    story: null,
    from: null,
    to: null,
    firstTwo: false,
    all: false,
    regenerate: false,
    headed: true,
    delaySec: null, // Default: random 10–30 seconds between scenes.
    helperUrl: 'http://127.0.0.1:8765',
    projectUrl: process.env.FLOW_PROJECT_URL || null,
  };
  const positional = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--first-two' || a === '--first_two') args.firstTwo = true;
    else if (a === '--all') args.all = true;
    else if (a === '--regenerate') args.regenerate = true;
    else if (a === '--headless') args.headed = false;
    else if (a === '--from') args.from = Number(argv[++i]);
    else if (a === '--to') args.to = Number(argv[++i]);
    else if (a === '--project-url') args.projectUrl = argv[++i];
    else if (a === '--helper') args.helperUrl = argv[++i];
    else if (a === '--delay') args.delaySec = Number(argv[++i]);
    else if (a === '--help' || a === '-h') args.help = true;
    else if (a.startsWith('-')) throw new Error(`Unknown flag: ${a}`);
    else positional.push(a);
  }
  args.story = positional[0] || null;
  if (args.delaySec !== null && (!Number.isFinite(args.delaySec) || args.delaySec < 0)) {
    throw new Error('--delay must be a non-negative number of seconds.');
  }
  if (args.all && args.firstTwo) {
    throw new Error('Use either --all or --first-two, not both.');
  }
  if (args.all && (args.from != null || args.to != null)) {
    throw new Error('Do not combine --all with --from/--to.');
  }
  // Manual smoke tests default to first two; worker/CMS passes --all explicitly.
  if (!args.all && !args.firstTwo && args.from == null && args.to == null) {
    args.firstTwo = true;
  }
  return args;
}

function usage() {
  console.log(`Usage:
  ./scripts/run_images.sh <story> [--all|--first-two] [--from N --to M] [--regenerate]
  [--project-url URL] [--helper http://127.0.0.1:8765]

Examples:
  ./scripts/run_images.sh 164-how-captain-saved-video-done --first-two
  ./scripts/run_images.sh 165-pakistan-army --all
  ./scripts/run_images.sh 165-pakistan-army --from 1 --to 2

Uses your normal Chrome Google login (restarts Chrome once with remote
debugging if needed). Optional: FLOW_PROJECT_URL, CDP_URL, CHROME_USER_DATA_DIR.`);
}

async function cdpAlive(cdpUrl = DEFAULT_CDP) {
  try {
    const res = await fetch(new URL('/json/version', cdpUrl), { signal: AbortSignal.timeout(1200) });
    return res.ok;
  } catch {
    return false;
  }
}

function ensureChromeWithLogin(account, { forceRestart = false } = {}) {
  const profileDir = account?.profile_dir || FLOW_CHROME_PROFILE;
  console.log('Opening Chrome with your Google login (Flow agent profile)…');
  if (account?.email) console.log(`Flow account: ${account.email} (${account.id})`);
  console.log(`Debug profile:  ${profileDir}`);
  const result = spawnSync('bash', [START_CHROME_SCRIPT], {
    cwd: ROOT,
    env: {
      ...process.env,
      CHROME_USER_DATA_DIR: REAL_CHROME_PROFILE,
      CHROME_FLOW_USER_DATA_DIR: profileDir,
      CHROME_FLOW_SKIP_SYNC: '1',
      CHROME_FLOW_FORCE_RESTART: forceRestart ? '1' : (process.env.CHROME_FLOW_FORCE_RESTART || '0'),
      CHROME_DEBUG_PORT: new URL(DEFAULT_CDP).port || '9222',
    },
    encoding: 'utf8',
  });
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
  if (result.status !== 0) {
    throw new Error(
      'Could not start Chrome with your login profile. '
      + 'Quit Chrome manually, then re-run:\n'
      + '  ./scripts/start_chrome_debug.sh\n'
      + 'If still signed out: CHROME_FLOW_REFRESH_LOGIN=1 ./scripts/start_chrome_debug.sh',
    );
  }
}

async function openBrowserContext(account, { forceRestart = false } = {}) {
  if (forceRestart || !(await cdpAlive())) {
    ensureChromeWithLogin(account, { forceRestart });
  }
  if (!(await cdpAlive())) {
    throw new Error(`Chrome debugging not available at ${DEFAULT_CDP}`);
  }

  console.log(`Connecting to signed-in Chrome via ${DEFAULT_CDP}`);
  const { browser, context, downloadSession } = await connectFlowBrowser(chromium, DEFAULT_CDP, DOWNLOADS);
  const page = await context.newPage();
  await trackPageDownloads(page, context, downloadSession, DOWNLOADS);
  return { browser, context, page, mode: 'cdp' };
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function readToken() {
  const cfg = readJson(CONFIG_PATH);
  let tokenFile = cfg.token_file || '.local/pairing-token';
  if (!path.isAbsolute(tokenFile)) tokenFile = path.join(ROOT, tokenFile);
  if (!fs.existsSync(tokenFile)) {
    throw new Error(`Pairing token missing at ${tokenFile}. Start helper once.`);
  }
  return fs.readFileSync(tokenFile, 'utf8').trim();
}

async function helperFetch(helperUrl, token, pathname, { method = 'GET', body } = {}) {
  const res = await fetch(`${helperUrl.replace(/\/$/, '')}${pathname}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      'X-Flow-Agent-Token': token,
      'Content-Type': 'application/json',
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || `Helper HTTP ${res.status} for ${pathname}`);
  }
  return data;
}

async function waitForHelper(helperUrl, timeoutMs = 20000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`${helperUrl.replace(/\/$/, '')}/health`);
      if (res.ok) return true;
    } catch {
      /* retry */
    }
    await sleep(400);
  }
  return false;
}

function ensureHelper(helperUrl) {
  return (async () => {
    if (await waitForHelper(helperUrl, 1500)) {
      console.log('Helper already running.');
      return null;
    }
    console.log('Starting local helper…');
    fs.mkdirSync(LOCAL, { recursive: true });
    const child = spawn('bash', [HELPER_SCRIPT], {
      cwd: ROOT,
      detached: true,
      stdio: ['ignore', 'ignore', 'ignore'],
    });
    child.unref();
    if (!(await waitForHelper(helperUrl, 20000))) {
      throw new Error('Helper did not start on 127.0.0.1:8765');
    }
    console.log('Helper is up.');
    return child;
  })();
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function projectUrlFile(accountId) {
  if (accountId && accountId !== 'default') {
    return path.join(LOCAL, `flow-project-url.${accountId}.txt`);
  }
  return PROJECT_URL_FILE;
}

function loadSavedProjectUrl(accountId) {
  // Never fall back to another Gmail's project URL — that 404s as /404?reason=project.
  const files = accountId
    ? [projectUrlFile(accountId)]
    : [PROJECT_URL_FILE];
  for (const file of files) {
    if (fs.existsSync(file)) {
      const url = fs.readFileSync(file, 'utf8').trim();
      if (url && !isMissingFlowProject(url)) return url;
    }
  }
  return null;
}

function saveProjectUrl(url, accountId) {
  if (!url || isMissingFlowProject(url) || !isInFlowProject(url)) return;
  fs.mkdirSync(LOCAL, { recursive: true });
  fs.writeFileSync(projectUrlFile(accountId), `${url}\n`, 'utf8');
  if (!accountId || accountId === 'default') {
    fs.writeFileSync(PROJECT_URL_FILE, `${url}\n`, 'utf8');
  }
}

function isFlowHost(url) {
  try {
    const host = new URL(url).hostname;
    return host === 'flow.google.com' || host === 'labs.google' || host.endsWith('.google.com');
  } catch {
    return false;
  }
}

function isMissingFlowProject(url) {
  try {
    const u = new URL(url);
    return u.pathname.includes('/404') || u.searchParams.get('reason') === 'project';
  } catch {
    return false;
  }
}

function isInFlowProject(url) {
  try {
    const u = new URL(url);
    if (isMissingFlowProject(url)) return false;
    if (!['flow.google.com', 'labs.google'].includes(u.hostname)) return false;
    // Real project workspace — not the marketing/home gallery or a 404.
    return /\/project\//.test(u.pathname) || /[?&]project[=/]/.test(u.search);
  } catch {
    return false;
  }
}

async function hasFlowEditor(page) {
  return page.evaluate(() => {
    const boxes = [...document.querySelectorAll('textarea,[contenteditable="true"],[role="textbox"]')]
      .filter((el) => {
        const r = el.getBoundingClientRect();
        return r.width > 40 && r.height > 20;
      });
    return boxes.length >= 1;
  });
}

async function clickNewProject(page) {
  console.log('Clicking “New project”…');
  const locators = [
    page.getByRole('button', { name: /^\s*New project\s*$/i }),
    page.getByRole('button', { name: /New project/i }),
    page.locator('button', { hasText: /New project/i }),
    page.locator('[aria-label*="New project" i]'),
    page.locator('a', { hasText: /New project/i }),
  ];
  for (const loc of locators) {
    const target = loc.first();
    try {
      if (await target.count() === 0) continue;
      if (!(await target.isVisible())) continue;
      await nativeClick(page, target);
      return true;
    } catch {
      /* try next */
    }
  }

  // DOM fallback — match visible controls by label text.
  const clicked = await page.evaluate(() => {
    const normalize = (t) => String(t || '').replace(/\s+/g, ' ').trim().toLowerCase();
    const nodes = [...document.querySelectorAll('button,a,[role="button"],div[tabindex]')];
    const matches = nodes.filter((el) => {
      const r = el.getBoundingClientRect();
      if (r.width < 20 || r.height < 20) return false;
      const label = normalize(el.getAttribute('aria-label') || el.textContent);
      return label === 'new project' || label.includes('new project');
    });
    // Prefer the floating bottom-right control if several match.
    matches.sort((a, b) => {
      const ar = a.getBoundingClientRect();
      const br = b.getBoundingClientRect();
      return (br.top + br.left) - (ar.top + ar.left);
    });
    if (!matches.length) return false;
    matches[0].click();
    return true;
  });
  return clicked;
}

async function nativeClick(page, locatorOrHandle) {
  // Playwright Locator has elementHandle(); ElementHandle from evaluateHandle does not.
  let handle = locatorOrHandle;
  if (locatorOrHandle && typeof locatorOrHandle.elementHandle === 'function') {
    handle = await locatorOrHandle.elementHandle();
  }
  if (!handle) throw new Error('Click target missing');
  await handle.evaluate((el) => el.scrollIntoView({ block: 'nearest', inline: 'nearest' }));
  await sleep(80);
  const box = await handle.boundingBox();
  if (!box) throw new Error('Click target has no box');
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
}

async function nativeHover(page, locatorOrHandle) {
  let handle = locatorOrHandle;
  if (locatorOrHandle && typeof locatorOrHandle.elementHandle === 'function') {
    handle = await locatorOrHandle.elementHandle();
  }
  if (!handle) throw new Error('Hover target missing');
  const box = await handle.boundingBox();
  if (!box) throw new Error('Hover target has no box');
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
}

async function scrollHandleToY(page, handle, targetY) {
  const height = () => page.evaluate(() => window.innerHeight);
  for (let i = 0; i < 8; i++) {
    await handle.evaluate((el, y) => {
      el.scrollIntoView({ block: 'center', inline: 'nearest' });
      const r = el.getBoundingClientRect();
      let node = el.parentElement;
      while (node && node !== document.documentElement) {
        const style = getComputedStyle(node);
        const canScroll = node.scrollHeight - node.clientHeight > 20
          && /(auto|scroll|overlay)/.test(style.overflowY);
        if (canScroll) {
          node.scrollTop += r.top - y;
          return;
        }
        node = node.parentElement;
      }
      window.scrollBy(0, r.top - y);
    }, targetY);
    await sleep(120);
    const box = await handle.boundingBox();
    const vh = await height();
    if (box && box.y >= 60 && box.y <= vh - 80) return box;
  }
  return handle.boundingBox();
}

/** Page-side helpers injected via evaluate */
const PAGE_HELPERS = `
(() => {
  const normalize = (text) => String(text || '').replace(/\\s+/g, ' ').trim();
  const ALIASES = {
    'Settings trigger': [
      'Settings trigger', 'Settings', 'Open settings', 'Tune', 'tune',
      'Generation settings', 'Project settings', 'settings', 'Expand',
    ],
    'Select model family': [
      'Select model family', 'Model', 'Models', 'Choose model', 'model family',
    ],
    'Start generation': [
      'Start generation', 'Generate', 'Create', 'Run', 'Submit',
    ],
    'Image': ['Image', 'Images'],
    '16:9': ['16:9', '16 / 9', 'Landscape'],
    'x1': ['x1', '1', '×1'],
    'Download': ['Download', 'Download image', 'Download result'],
    '2K Upscaled': ['2K Upscaled', '2K upscaled', '2K'],
  };
  function visible(el) {
    if (!el?.isConnected) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }
  function label(el) {
    const explicit = el.getAttribute('aria-label');
    if (explicit) return normalize(explicit);
    const titled = el.getAttribute('title');
    if (titled) return normalize(titled);
    const labelled = el.getAttribute('aria-labelledby');
    if (labelled) {
      const text = labelled.split(/\\s+/).map((id) => document.getElementById(id)?.textContent || '').join(' ');
      if (text.trim()) return normalize(text);
    }
    if (el.labels?.length) return normalize([...el.labels].map((l) => l.textContent).join(' '));
    // Strip icon ligatures even when glued directly to the visible label.
    const copy = el.cloneNode(true);
    copy.querySelectorAll('svg,mat-icon,[aria-hidden="true"],.material-icons,.material-symbols-outlined').forEach((icon) => icon.remove());
    return normalize(copy.textContent || '') || normalize(el.textContent || '');
  }
  const controls = () => [...document.querySelectorAll(
    'button,input[type="radio"],[role="button"],[role="radio"],[role="tab"],[role="option"],[role="menuitem"],[role="combobox"],[aria-label]'
  )].filter((el) => visible(el) || (el.type === 'radio' && [...(el.labels || [])].some(visible)));
  const isSelected = (el) => el.checked === true
    || ['aria-checked', 'aria-selected', 'aria-pressed'].some((attr) => el.getAttribute(attr) === 'true')
    || ['checked', 'active', 'on'].includes(el.getAttribute('data-state'));
  function aliasList(name) {
    return ALIASES[name] || [name];
  }
  function matches(el, name) {
    const text = label(el);
    const lower = text.toLowerCase();
    for (const alias of aliasList(name)) {
      const a = alias.toLowerCase();
      if (lower === a) return true;
      // Settings must match a whole label, never a model summary or group.
    }
    const tokens = text.replace(/\\b(?:image|photo|crop_landscape|crop_square|crop_portrait|aspect_ratio|arrow_drop_down|expand_more|videocam)\\b/gi, '').trim().toLowerCase();
    for (const alias of aliasList(name)) {
      if (tokens === alias.toLowerCase()) return true;
    }
    if (name === 'Image') return /^(?:image\\s*){1,2}$/i.test(text);
    if (name === 'Settings trigger') {
      return /^(settings(\\s+trigger)?|tune|generation settings)$/i.test(text);
    }
    if (name === 'Start generation') return /^(start\\s+)?generat(e|ion)$/i.test(text);
    if (name === '2K Upscaled') return /^2k(\\s+upscaled)?$/i.test(text);
    if (name === 'Select model family') {
      return /nano banana|model family|select model/i.test(text);
    }
    return false;
  }
  function findControl(name, { optional = false } = {}) {
    let candidates = controls().filter((el) => matches(el, name));
    const interactive = candidates.filter((el) => el.matches('button,input[type="radio"],[role="button"],[role="radio"],[role="tab"],[role="option"],[role="menuitem"],[role="combobox"]'));
    if (interactive.length) candidates = interactive;
    const radios = candidates.filter((el) => ['radio', 'tab'].includes(el.getAttribute('role')) || el.type === 'radio');
    if (radios.length) candidates = radios;
    candidates = candidates.filter((el) => !candidates.some((other) => other !== el && el.contains(other)));
    if (candidates.length === 1) return candidates[0];
    if (optional && candidates.length === 0) return null;
    // Prefer bottom-bar controls for settings/generate when ambiguous.
    if (candidates.length > 1) {
      candidates.sort((a, b) => b.getBoundingClientRect().top - a.getBoundingClientRect().top);
      if (name === 'Settings trigger' || name === 'Start generation') return candidates[0];
    }
    if (optional) return candidates[0] || null;
    const sample = controls().slice(0, 40).map((el) => label(el)).filter(Boolean).slice(0, 25);
    throw new Error(
      'Could not identify Flow\\'s ' + name + ' control (' + candidates.length + ' matches). '
      + 'Visible labels: ' + JSON.stringify(sample)
    );
  }
  function listLabels() {
    return controls().map((el) => label(el)).filter(Boolean);
  }
  window.__flowAgent = { normalize, visible, label, controls, isSelected, matches, findControl, listLabels, ALIASES };
})();
`;

async function ensurePageHelpers(page) {
  await page.evaluate(PAGE_HELPERS);
}

async function waitForFlowWorkspace(page, timeoutMs = 60000) {
  console.log('Waiting for Flow workspace controls…');
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    await ensurePageHelpers(page);
    const ready = await page.evaluate(() => {
      const hasEditor = [...document.querySelectorAll('textarea,[contenteditable="true"],[role="textbox"]')]
        .some((el) => window.__flowAgent.visible(el));
      const labels = window.__flowAgent.listLabels();
      const hasGenerate = labels.some((l) => /generat/i.test(l));
      const hasSettings = labels.some((l) => /settings|tune/i.test(l));
      return { hasEditor, hasGenerate, hasSettings, labels: labels.slice(0, 40) };
    });
    if (ready.hasEditor || ready.hasGenerate || ready.hasSettings) {
      console.log(`Workspace ready (editor=${ready.hasEditor}, generate=${ready.hasGenerate}, settings=${ready.hasSettings})`);
      return ready;
    }
    await sleep(1000);
  }
  const labels = await page.evaluate(() => {
    try {
      window.__flowAgent && window.__flowAgent.listLabels();
      return (window.__flowAgent && window.__flowAgent.listLabels()) || [];
    } catch {
      return [];
    }
  }).catch(() => []);
  throw new Error(
    'Flow workspace did not become ready. Visible labels: ' + JSON.stringify(labels.slice(0, 40)),
  );
}

async function clickNamedControl(page, name, { selectOnlyIfNeeded = true, optional = false } = {}) {
  await ensurePageHelpers(page);
  const handle = await page.evaluateHandle(({ controlName, isOptional }) => {
    return window.__flowAgent.findControl(controlName, { optional: isOptional });
  }, { controlName: name, isOptional: optional });
  const isNull = await handle.evaluate((el) => el == null);
  if (isNull) {
    await handle.dispose();
    if (optional) return false;
    throw new Error(`Could not identify Flow's ${name} control`);
  }
  const selected = await handle.evaluate((el) => {
    return el.checked === true
      || ['aria-checked', 'aria-selected', 'aria-pressed'].some((attr) => el.getAttribute(attr) === 'true')
      || ['checked', 'active', 'on'].includes(el.getAttribute('data-state'));
  });
  if (!selectOnlyIfNeeded || !selected) {
    await nativeClick(page, handle);
  }
  await sleep(350);
  await handle.dispose();
  return true;
}

async function configureFlow(page) {
  console.log('Configuring Flow: Image · Nano Banana 2.1 · 16:9 · x1…');
  await waitForFlowWorkspace(page);
  await ensurePageHelpers(page);

  // Dump labels once for troubleshooting.
  const labels = await page.evaluate(() => window.__flowAgent.listLabels());
  console.log('Flow controls:', labels.filter(Boolean).slice(0, 50).join(' | '));

  await page.evaluate(() => {
    const agent = window.__flowAgent.controls().find((el) => /^agent$/i.test(window.__flowAgent.label(el)));
    if (agent && (agent.getAttribute('aria-pressed') === 'true' || agent.getAttribute('aria-checked') === 'true')) {
      agent.click();
    }
  });
  await sleep(350);

  // A fresh project's summary can contain 16:9 while its mode panel is closed.
  // Check the panel's radio rather than an aspect-ratio summary or gallery label.
  const imageMode = page.getByRole('radio', { name: /^Image$/i });
  if (!(await imageMode.isVisible().catch(() => false))) {
    await page.getByRole('button', { name: 'Settings trigger', exact: true }).click({ timeout: 8000 });
  }
  await imageMode.waitFor({ state: 'visible', timeout: 10000 });

  await clickNamedControl(page, 'Image', { optional: false });
  await clickNamedControl(page, '16:9', { optional: false });
  await clickNamedControl(page, 'x1', { optional: true });

  const modelOk = await page.evaluate(() => {
    try {
      const trigger = window.__flowAgent.findControl('Select model family', { optional: true });
      if (!trigger) return false;
      return /Nano Banana 2\.1/i.test(trigger.textContent || window.__flowAgent.label(trigger));
    } catch {
      return false;
    }
  });
  if (!modelOk) {
    await clickNamedControl(page, 'Select model family', { selectOnlyIfNeeded: false, optional: true });
    await sleep(500);
    const picked = await page.evaluate(() => {
      const options = window.__flowAgent.controls().filter((el) =>
        /Nano Banana 2\.1/i.test(window.__flowAgent.label(el)));
      if (!options.length) return false;
      options[0].click();
      return true;
    });
    if (!picked) throw new Error('Nano Banana 2.1 option not found. Labels: ' + JSON.stringify(labels.slice(0, 40)));
    await sleep(500);
  }

  const confirmed = await page.evaluate(() => {
    const selected = window.__flowAgent.findControl('Select model family', { optional: true });
    const modelText = selected ? (selected.textContent || window.__flowAgent.label(selected)) : '';
    if (selected && !/Nano Banana 2\.1/i.test(modelText)) return false;
    for (const name of ['Image', '16:9']) {
      const el = window.__flowAgent.findControl(name, { optional: true });
      if (!el) return false;
      if (!window.__flowAgent.isSelected(el)) return false;
    }
    return true;
  });
  if (!confirmed) {
    throw new Error('Could not confirm Nano Banana 2.1 / Image / 16:9. Labels: ' + JSON.stringify(labels.slice(0, 40)));
  }
  // Close settings panel if open (optional).
  await clickNamedControl(page, 'Settings trigger', { selectOnlyIfNeeded: false, optional: true });
  await sleep(350);
}

async function fillPrompt(page, text) {
  await enterPrompt(page, text);
}

async function clickGenerate(page, expectedText) {
  await submitPrompt(page, expectedText);
}

/** Significant words from "Scene N. Title…" for matching Flow gallery tile labels. */
function promptMatchHints(text) {
  const titleMatch = String(text || '').match(/^Scene\s+\d+\.\s*([^.!?]+)/i);
  const title = (titleMatch ? titleMatch[1] : String(text || '').slice(0, 120)).toLowerCase();
  const stop = new Set([
    'scene', 'create', 'cinematic', 'hand', 'drawn', 'matte', 'painting', 'frame',
    'with', 'from', 'that', 'this', 'into', 'about', 'after', 'before', 'under',
  ]);
  return [...new Set(title.split(/[^a-z0-9]+/).filter((w) => w.length >= 5 && !stop.has(w)))].slice(0, 6);
}

/**
 * Find an existing Flow gallery image that likely matches this prompt
 * (e.g. prior run generated it but download/detection failed).
 */
async function findExistingTileUrl(page, text, excludeUrls = []) {
  const hints = promptMatchHints(text);
  if (!hints.length) return null;
  return page.evaluate(({ hints: hs, exclude }) => {
    const excluded = new Set(exclude);
    const tiles = [...document.querySelectorAll('flow-image-tile')];
    let best = null;
    let bestScore = 0;
    for (const tile of tiles) {
      const label = (
        tile.getAttribute('aria-label')
        || tile.querySelector('[aria-label]')?.getAttribute('aria-label')
        || tile.textContent
        || ''
      ).toLowerCase();
      const img = tile.querySelector('img');
      const url = img ? (img.currentSrc || img.src) : '';
      if (!url || excluded.has(url) || !img?.complete || img.naturalWidth < 256) continue;
      const score = hs.reduce((n, h) => n + (label.includes(h) ? 1 : 0), 0);
      if (score > bestScore) {
        bestScore = score;
        best = url;
      }
    }
    return bestScore > 0 ? best : null;
  }, { hints, exclude: excludeUrls });
}

async function waitForNewImage(page, beforeUrls, beforeBatches, failureBaseline, timeoutMs = 180000) {
  async function checkFailure() {
    const message = newFailure(failureBaseline, await failureSnapshot(page));
    if (message) { const error = new Error(message); error.category = classifyFailure(message); throw error; }
  }
  const start = Date.now();
  let submitOk = false;
  // Flow often takes >12s before a new batch/tile appears (esp. after prior failures).
  while (Date.now() - start < 60000) {
    await checkFailure();
    const batches = await page.locator('button[aria-label="Download batch"]').count();
    if (batches > beforeBatches) {
      submitOk = true;
      break;
    }
    const maybe = await page.evaluate((prev) => {
      const urls = [...document.querySelectorAll('flow-image-tile img, img')]
        .filter((el) => el.complete && el.naturalWidth >= 256)
        .map((el) => el.currentSrc || el.src);
      return urls.some((u) => !prev.includes(u));
    }, beforeUrls);
    if (maybe) {
      submitOk = true;
      break;
    }
    // Generating spinner / progress affordances
    const busy = await page.evaluate(() => {
      const text = (document.body?.innerText || '').slice(0, 8000);
      return /generat(ing|e)|upscal|creating|working/i.test(text)
        || !!document.querySelector('[aria-busy="true"], [role="progressbar"]');
    });
    if (busy) {
      submitOk = true;
      break;
    }
    await sleep(500);
  }
  if (!submitOk) {
    throw new Error('Flow did not start a new generation (needs review).');
  }

  let fresh = [];
  let prevSig = '';
  let stableSince = 0;
  while (Date.now() - start < timeoutMs) {
    await checkFailure();
    await sleep(1000);
    fresh = await page.evaluate((prev) => {
      return [...new Set([...document.querySelectorAll('flow-image-tile img, img')]
        .filter((el) => {
          const r = el.getBoundingClientRect();
          return el.complete && el.naturalWidth >= 256 && r.width >= 100 && r.height >= 100;
        })
        .map((el) => el.currentSrc || el.src)
        .filter(Boolean))]
        .filter((url) => !prev.includes(url));
    }, beforeUrls);
    const sig = JSON.stringify(fresh);
    if (fresh.length && sig === prevSig) {
      if (Date.now() - stableSince >= 5000) return fresh;
    } else {
      prevSig = sig;
      stableSince = Date.now();
    }
  }
  throw new Error('No confirmed new image within timeout (needs review).');
}

async function download2K(page, imageUrl) {
  await ensurePageHelpers(page);
  await page.bringToFront();
  let openAttempt = 0;
  const twoK = await select2KMenu(page, async () => {
    openAttempt += 1;
    // Tall More-options menu (~540px) falls off-screen if the tile sits at the
    // top or bottom of the gallery. Shift the trigger on each retry.
    const targetY = [260, 400, 140][Math.min(openAttempt - 1, 2)];
    const tile = await page.evaluateHandle((url) => {
      const image = [...document.querySelectorAll('flow-image-tile img')]
        .find((el) => (el.currentSrc || el.src) === url);
      const found = image?.closest('flow-image-tile');
      if (!found) throw new Error('More options menu not found for result image');
      return found;
    }, imageUrl);
    try {
      await scrollHandleToY(page, tile, targetY);
      await nativeHover(page, tile);
      await sleep(200);
      const menu = await tile.evaluateHandle((el) => {
        const btn = el.querySelector('button[aria-label="More options"]');
        if (!btn) throw new Error('More options menu not found for result image');
        return btn;
      });
      try {
        const box = await menu.boundingBox();
        if (!box) throw new Error('More options menu not found for result image');
        const vh = await page.evaluate(() => window.innerHeight);
        if (box.y < 40 || box.y > vh - 40) await menu.click({ force: true });
        else await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
      } finally { await menu.dispose(); }
    } finally { await tile.dispose(); }
  }, (target) => target.click({ force: true }), sleep);

  const dest = await downloadFromPage(page, async () => {
    // Locator click hits the split "2K / Upscaled" menuitem; coordinate clicks
    // often land on the leftover full-page backdrop instead.
    await twoK.click({ timeout: 8000 }).catch(() => twoK.click({ force: true, timeout: 8000 }));
    console.log('2K clicked; waiting for a confirmed download from this Flow tab…');
  });
  await page.keyboard.press('Escape').catch(() => {});
  await page.keyboard.press('Escape').catch(() => {});
  return dest;
}

async function ensureFlowProject(page, preferredUrl, accountId, account = null) {
  let url = preferredUrl || loadSavedProjectUrl(accountId);
  let newProjectAttempts = 0;
  let lastClickAt = 0;
  if (url && !isInFlowProject(url)) url = null;

  if (url) {
    console.log(`Opening Flow project: ${url}`);
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120000 });
    await sleep(2500);
    const landed = page.url();
    if (!isInFlowProject(landed) || isMissingFlowProject(landed)) {
      console.log(`Project not available on this Gmail (${landed}). Creating a new Flow project…`);
      url = null;
      await page.goto('https://flow.google.com/', { waitUntil: 'domcontentloaded', timeout: 120000 });
      await sleep(2500);
    }
  } else {
    const home = 'https://flow.google.com/';
    console.log(`No saved project URL for this Gmail. Opening ${home}`);
    await page.goto(home, { waitUntil: 'domcontentloaded', timeout: 120000 });
    await sleep(2500);
  }

  const deadline = Date.now() + 5 * 60 * 1000;
  while (Date.now() < deadline) {
    const current = page.url();
    if (isMissingFlowProject(current)) {
      console.log(`Flow returned ${current} — opening home to create a new project…`);
      await page.goto('https://flow.google.com/', { waitUntil: 'domcontentloaded', timeout: 120000 }).catch(() => {});
      await sleep(2000);
      continue;
    }

    if (isInFlowProject(current)) {
      await verifyFlowAccount(page, account);
      saveProjectUrl(current, accountId);
      console.log(`Using Flow project: ${current}`);
      return current;
    }

    // Home / gallery — create a project automatically.
    const shouldClick = newProjectAttempts === 0 || (Date.now() - lastClickAt > 8000 && newProjectAttempts < 8);
    if (shouldClick) {
      const ok = await clickNewProject(page);
      newProjectAttempts += 1;
      lastClickAt = Date.now();
      if (ok) {
        console.log(`“New project” clicked (attempt ${newProjectAttempts}) — waiting for workspace…`);
      } else {
        console.log(`“New project” not found yet (attempt ${newProjectAttempts}) — waiting for page…`);
      }
      await sleep(2500);
      continue;
    }

    await sleep(1500);
  }
  throw new Error(
    'Timed out waiting for a Flow project after trying “New project”. '
    + 'Open a project manually or set FLOW_PROJECT_URL.',
  );
}

async function switchFlowAccount(session, accounts, state, reason) {
  const next = nextAccount(accounts, state);
  if (!next) {
    throw new Error(
      `${reason} Add another signed-in Flow Chrome profile in config.json flow_accounts `
      + '(one Gmail per profile_dir, already logged into Flow).',
    );
  }
  console.log(
    `Switching Flow profile ${state.current_id} → ${next.id}`
    + `${next.email ? ` (${next.email})` : ''} — ${reason}`,
  );
  await session.page.close().catch(() => {});
  const opened = await openBrowserContext(next, { forceRestart: true });
  session.page = opened.page;
  session.browser = opened.browser;
  session.account = next;
  monitorPage = session.page;
  state.current_id = next.id;
  saveAccountState(LOCAL, state);
  const preferred = next.project_url || loadSavedProjectUrl(next.id);
  await ensureFlowProject(session.page, preferred, next.id, next);
  await configureFlow(session.page);
}

async function verifyFlowAccount(page, account) {
  if (!account?.email) return;
  const googleAccount = page.locator('[aria-label*="Google Account:"]').first();
  await googleAccount.waitFor({ state: 'visible', timeout: 15000 });
  assertAccountEmail(account, await googleAccount.getAttribute('aria-label'));
}

async function runJob(session, { helperUrl, token, jobId, delaySec, regenerate, imagesDir, accounts, state, sceneTo = null }) {
  let lastClaimedScene = null;
  const creds = { helperUrl, token, jobId, regenerate };
  async function pauseBetweenScenes() {
    const seconds = delaySec ?? (10 + Math.random() * 20);
    console.log(`Waiting ${seconds.toFixed(1)} seconds before the next scene…`);
    await sleep(seconds * 1000);
  }
  await configureFlow(session.page);

  sceneQueue: while (true) {
    if (sceneTo !== null && lastClaimedScene !== null && lastClaimedScene >= sceneTo) {
      console.log('Selected scene range complete.');
      return;
    }
    if (session.account && !accountHasQuota(session.account, state)) {
      await switchFlowAccount(session, accounts, state, `Reached ${session.account.max_images} images on this Gmail today.`);
    }
    const page = session.page;
    const claimed = await helperFetch(helperUrl, token, `/jobs/${jobId}/claim-next`, {
      method: 'POST',
      body: {
        owner: 'cli-playwright',
        flow_project_url: page.url(),
      },
    });
    if (!claimed.scene) {
      console.log(claimed.reason === 'done' ? 'Queue complete.' : `Stopped: ${claimed.reason}`);
      if ((claimed.summary?.failed || 0) + (claimed.summary?.needs_review || 0) > 0) process.exitCode = 1;
      return claimed;
    }
    const scene = claimed.scene;
    lastClaimedScene = scene.scene;
    monitorWrite("running", scene.scene);
    console.log(`\n=== Scene ${scene.scene} ===`);
    const originalPrompt = scene.text;
    let promptHistory = null;
    while (true) {
    const page = session.page;
    try {
      // runJob configures the project once; switchFlowAccount configures each
      // new profile. Reopening settings per scene creates unnecessary UI races.
      const beforeUrls = await page.evaluate(() =>
        [...document.querySelectorAll('flow-image-tile img, img')]
          .filter((el) => el.complete && el.naturalWidth >= 256)
          .map((el) => el.currentSrc || el.src)
          .filter(Boolean),
      );
      const beforeBatches = await page.locator('button[aria-label="Download batch"]').count();

      // Prefer adopting a prior gallery result when regenerate is off (common after
      // "did not start" false negatives where Flow already produced the image).
      let imageUrl = null;
      if (!regenerate) {
        imageUrl = await findExistingTileUrl(page, scene.text, []);
        if (imageUrl) {
          console.log(`Scene ${scene.scene}: reusing existing Flow gallery result…`);
        }
      }

      if (!imageUrl) {
        await helperFetch(helperUrl, token, `/jobs/${jobId}/scenes/${scene.scene}/status`, {
          method: 'POST',
          body: { status: 'submitting' },
        });
        try {
          await fillPrompt(page, scene.text);
        } catch (error) {
          error.category ||= 'ui_blocked';
          throw error;
        }
        await sleep(500);
        const failureBaseline = await failureSnapshot(page);
        if (promptHistory) recordOutcome(promptHistory, "submitted");
        try {
          await clickGenerate(page, scene.text);
        } catch (error) {
          error.category ||= 'ui_blocked';
          throw error;
        }
        console.log(`Scene ${scene.scene}: generating…`);
        await helperFetch(helperUrl, token, `/jobs/${jobId}/scenes/${scene.scene}/status`, {
          method: 'POST',
          body: { status: 'generating' },
        });
        try {
          const fresh = await waitForNewImage(page, beforeUrls, beforeBatches, failureBaseline);
          imageUrl = fresh[0];
        } catch (waitErr) {
          waitErr.generationFailure = true;
          if (waitErr.category) throw waitErr;
          // Last chance: adopt a gallery tile that matches this prompt title.
          imageUrl = await findExistingTileUrl(page, scene.text, []);
          if (!imageUrl) throw waitErr;
          console.log(`Scene ${scene.scene}: generation unclear; adopting matching gallery tile…`);
        }
        // Count confirmed generation even if upscaling or saving subsequently fails.
        // Reusing an existing gallery image does not consume another generation.
        if (session.account) {
          incrementAccountCount(state, session.account.id);
          saveAccountState(LOCAL, state);
        }
      }

      console.log(`Scene ${scene.scene}: upscaling 2K…`);
      await helperFetch(helperUrl, token, `/jobs/${jobId}/scenes/${scene.scene}/status`, {
        method: 'POST',
        body: { status: 'upscaling' },
      });
      const downloadPath = await download2K(page, imageUrl);
      console.log(`Scene ${scene.scene}: saving ${downloadPath}`);
      const saved = await helperFetch(helperUrl, token, `/jobs/${jobId}/scenes/${scene.scene}/save`, {
        method: 'POST',
        body: {
          download_path: downloadPath,
          regenerate,
        },
      });
      if (promptHistory) recordOutcome(promptHistory, "saved");
      console.log(
        `Scene ${scene.scene}: saved → ${saved.saved.path} (${saved.saved.width}x${saved.saved.height})`,
      );
    } catch (err) {
      const message = err?.message || String(err);
      console.error(`Scene ${scene.scene} failed: ${message}`);
      if (isQuotaLikeError(message)) {
        if (session.account) {
          markAccountExhausted(state, session.account.id);
          saveAccountState(LOCAL, state);
        }
        if (accounts?.length > 1) {
          try {
            await switchFlowAccount(session, accounts, state, message);
          } catch (switchError) {
            await helperFetch(helperUrl, token, `/jobs/${jobId}/scenes/${scene.scene}/status`, {
              method: 'POST', body: { status:'needs_review', error_category:'rate_limit',
                error_message:switchError.message },
            }).catch(() => {});
            throw switchError;
          }
          continue;
        }
      }
      const fatal = err.category === 'ui_blocked' || page.isClosed?.() || isQuotaLikeError(message)
        || /Target page, context or browser has been closed|browser.*disconnected|Flow Gmail does not match/i.test(message);
      const repairable = !fatal && !/unusual activity/i.test(message)
        && (err.generationFailure || err.category === 'policy_rejection');
      if (repairable) {
        try {
          if (promptHistory) recordOutcome(promptHistory, 'failed');
          promptHistory ||= loadHistory(imagesDir, scene.scene, originalPrompt);
          const revised = await revise(promptHistory, path.join(ROOT, '..', 'story-pipeline-worker'), message);
          if (revised) {
            scene.text = revised;
            console.log(`Scene ${scene.scene}: retrying with saved prompt revision ${promptHistory.data.revisions.length}/2`);
            await pauseBetweenScenes();
            continue;
          }
        } catch (_) { /* Unreadable history must never reset the budget. */ }
        await helperFetch(helperUrl, token, `/jobs/${jobId}/scenes/${scene.scene}/status`, {
          method: 'POST', body: {status:'failed', error_category:err.category || 'generation_failed',
            error_message:`${message} Prompt repair exhausted, declined or unavailable. Other scenes will continue.`},
        });
        console.log(`Scene ${scene.scene}: marked for review; continuing remaining scenes.`);
        process.exitCode = 1;
        await pauseBetweenScenes();
        continue sceneQueue;
      }
      const needsReview = /needs review|did not start|timeout/i.test(message);
      await helperFetch(helperUrl, token, `/jobs/${jobId}/scenes/${scene.scene}/status`, {
        method: 'POST',
        body: {
          // needs_review pauses the entire helper queue. Scene failures must stay
          // failed so claim-next can move on without retrying this scene.
          status: fatal ? 'needs_review' : 'failed',
          error_category: err.category || (needsReview ? 'needs_review' : 'unknown'),
          error_message: message,
        },
      });
      if (fatal) throw err;
      process.exitCode = 1;
      console.log(`Scene ${scene.scene}: failed; continuing remaining scenes. Retry this scene in a later run.`);
      await pauseBetweenScenes();
      continue sceneQueue;
    }
    break;
    }
    await pauseBetweenScenes();
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || !args.story) {
    usage();
    process.exit(args.help ? 0 : 1);
  }

  fs.mkdirSync(DOWNLOADS, { recursive: true });

  await ensureHelper(args.helperUrl);
  const token = readToken();

  console.log(`Creating job for story: ${args.story}`);
  const body = {
    story_key: args.story,
    regenerate: args.regenerate,
  };
  if (args.firstTwo) body.first_two = true;
  else if (args.all) {
    // Omit range → helper selects every scene in the prompt file.
    body.all = true;
  } else {
    body.scene_from = args.from;
    body.scene_to = args.to;
  }
  const job = await helperFetch(args.helperUrl, token, '/jobs', { method: 'POST', body });
  monitorStart(path.join(job.job.images_dir, "runner-status.json"));
  console.log(`Job ${job.job.job_id} · ${JSON.stringify(job.summary)}`);

  if (job.summary.remaining === 0 && !args.regenerate) {
    console.log('Nothing to do — selected scenes already completed.');
    console.log(`Images dir: ${job.job.images_dir}`);
    return;
  }

  const cfg = readJson(CONFIG_PATH);
  const accounts = loadAccountPool(cfg, {
    localDir: LOCAL,
    defaultProfile: FLOW_CHROME_PROFILE,
    defaultProjectUrl: args.projectUrl || '',
  });
  const state = loadAccountState(LOCAL, accounts);
  let account = currentAccount(accounts, state);
  let restartForAccount = false;
  if (account && !accountHasQuota(account, state)) {
    const next = nextAccount(accounts, state);
    if (!next) throw new Error('All configured Flow Gmail profiles have reached their local limit or reported quota exhaustion today.');
    account = next;
    restartForAccount = true;
    state.current_id = account.id;
    saveAccountState(LOCAL, state);
  }
  if (account && !profileLooksSignedIn(account.profile_dir)) {
    console.log(
      `Flow profile is not signed in yet: ${account.profile_dir}`
      + (account.email ? ` (${account.email})` : '')
      + '. Chrome will open — sign into Google Flow once, then re-run.',
    );
  }
  if (accounts.length > 1) {
    console.log(
      `Flow account pool: ${accounts.length} Gmail profile(s). `
      + `Using ${account.id}${account.email ? ` / ${account.email}` : ''} `
      + `(${Number(state.counts?.[account.id] || 0)}/${account.max_images} today).`,
    );
  }

  const opened = await openBrowserContext(account, { forceRestart: restartForAccount });
  const session = { page: opened.page, browser: opened.browser, account };
  monitorPage = session.page; monitorWrite("running");

  try {
    const preferred = args.projectUrl || account?.project_url || loadSavedProjectUrl(account?.id);
    const projectUrl = await ensureFlowProject(session.page, preferred, account?.id, account);
    await runJob(session, {
      helperUrl: args.helperUrl,
      token,
      jobId: job.job.job_id,
      imagesDir: job.job.images_dir,
      delaySec: args.delaySec,
      sceneTo: job.job.scene_to,
      regenerate: args.regenerate,
      accounts,
      state,
    });
    console.log('\nDone.');
    console.log(`Project: ${projectUrl}`);
    console.log(`Images:  ${job.job.images_dir}`);
  } finally {
    // Keep your real Chrome open; only close the automation tab.
    await sleep(1000);
    if (opened.mode === 'cdp') {
      await session.page.close().catch(() => {});
      // For connectOverCDP this closes the client transport, leaving the
      // externally launched Chrome open. Otherwise Node can linger after Done.
      await session.browser.close().catch(() => {});
    }
  }
}

main().catch((err) => {
  console.error('\nERROR:', err.message || err);
  process.exit(1);
});
