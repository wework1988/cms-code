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
    regenerate: false,
    headed: true,
    delaySec: 5,
    helperUrl: 'http://127.0.0.1:8765',
    projectUrl: process.env.FLOW_PROJECT_URL || null,
  };
  const positional = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--first-two' || a === '--first_two') args.firstTwo = true;
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
  if (!args.firstTwo && args.from == null && args.to == null) {
    args.firstTwo = true; // safe default for one-command runs
  }
  return args;
}

function usage() {
  console.log(`Usage:
  ./scripts/run_images.sh <story> [--first-two] [--from N --to M] [--regenerate]
  [--project-url URL] [--helper http://127.0.0.1:8765]

Examples:
  ./scripts/run_images.sh 164-how-captain-saved-video-done --first-two
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

function ensureChromeWithLogin() {
  console.log('Opening Chrome with your Google login (Flow agent profile clone)…');
  console.log(`Source profile: ${REAL_CHROME_PROFILE}`);
  console.log(`Debug profile:  ${FLOW_CHROME_PROFILE}`);
  const result = spawnSync('bash', [START_CHROME_SCRIPT], {
    cwd: ROOT,
    env: {
      ...process.env,
      CHROME_USER_DATA_DIR: REAL_CHROME_PROFILE,
      CHROME_FLOW_USER_DATA_DIR: FLOW_CHROME_PROFILE,
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

async function openBrowserContext() {
  if (!(await cdpAlive())) {
    ensureChromeWithLogin();
  }
  if (!(await cdpAlive())) {
    throw new Error(`Chrome debugging not available at ${DEFAULT_CDP}`);
  }

  console.log(`Connecting to signed-in Chrome via ${DEFAULT_CDP}`);
  const browser = await chromium.connectOverCDP(DEFAULT_CDP);
  const context = browser.contexts()[0] || await browser.newContext({ acceptDownloads: true });
  const page = await context.newPage();
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

function loadSavedProjectUrl() {
  if (fs.existsSync(PROJECT_URL_FILE)) {
    const url = fs.readFileSync(PROJECT_URL_FILE, 'utf8').trim();
    if (url) return url;
  }
  return null;
}

function saveProjectUrl(url) {
  fs.mkdirSync(LOCAL, { recursive: true });
  fs.writeFileSync(PROJECT_URL_FILE, `${url}\n`, 'utf8');
}

function isFlowHost(url) {
  try {
    const host = new URL(url).hostname;
    return host === 'flow.google.com' || host === 'labs.google' || host.endsWith('.google.com');
  } catch {
    return false;
  }
}

function isInFlowProject(url) {
  try {
    const u = new URL(url);
    if (!['flow.google.com', 'labs.google'].includes(u.hostname)) return false;
    // Real project workspace — not the marketing/home gallery.
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
    'Download': ['Download'],
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

  const has169 = await page.evaluate(() => window.__flowAgent.controls().some((el) => window.__flowAgent.matches(el, '16:9')));
  if (!has169) {
    const opened = await clickNamedControl(page, 'Settings trigger', { selectOnlyIfNeeded: false, optional: true });
    if (!opened) {
      // Try clicking any tune/settings icon by material text.
      await page.evaluate(() => {
        const el = window.__flowAgent.controls().find((c) => /^(tune|settings)$/i.test(window.__flowAgent.label(c)));
        if (el) el.click();
      });
    }
    await sleep(700);
  }

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
  await ensurePageHelpers(page);
  const ok = await page.evaluate((value) => {
    const boxes = [...document.querySelectorAll('textarea,[contenteditable="true"],[role="textbox"]')]
      .filter((el) => window.__flowAgent.visible(el));
    if (boxes.length !== 1) throw new Error('Could not identify the Flow prompt box');
    const el = boxes[0];
    el.focus();
    if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) {
      const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    } else {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(el);
      selection.removeAllRanges();
      selection.addRange(range);
      if (!document.execCommand('insertText', false, value)) {
        throw new Error('Flow did not accept the prompt');
      }
    }
    const current = (el.value ?? el.textContent) || '';
    return current.trim() === value.trim();
  }, text);
  if (!ok) throw new Error('Could not verify the complete prompt text in the editor');
}

async function clickGenerate(page) {
  await ensurePageHelpers(page);
  const btn = await page.evaluateHandle(() => window.__flowAgent.findControl('Start generation'));
  const disabled = await btn.evaluate((el) => el.disabled || el.getAttribute('aria-disabled') === 'true');
  if (disabled) {
    await btn.dispose();
    throw new Error('Generate is unavailable. Check model, credits, and prompt in Flow.');
  }
  await nativeClick(page, btn);
  await btn.dispose();
}

async function waitForNewImage(page, beforeUrls, beforeBatches, timeoutMs = 180000) {
  const start = Date.now();
  let submitOk = false;
  while (Date.now() - start < 12000) {
    const batches = await page.locator('button[aria-label="Download batch"]').count();
    if (batches > beforeBatches) {
      submitOk = true;
      break;
    }
    await sleep(250);
  }
  if (!submitOk) {
    const maybe = await page.evaluate((prev) => {
      const urls = [...document.querySelectorAll('flow-image-tile img, img')]
        .filter((el) => el.complete && el.naturalWidth >= 256)
        .map((el) => el.currentSrc || el.src);
      return urls.some((u) => !prev.includes(u));
    }, beforeUrls);
    if (!maybe) throw new Error('Flow did not start a new generation (needs review).');
  }

  let fresh = [];
  let prevSig = '';
  let stableSince = 0;
  while (Date.now() - start < timeoutMs) {
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
  const menu = await page.evaluateHandle((url) => {
    const image = [...document.querySelectorAll('flow-image-tile img')]
      .find((el) => (el.currentSrc || el.src) === url);
    const tile = image?.closest('flow-image-tile');
    const btn = tile?.querySelector('button[aria-label="More options"]');
    if (!btn) throw new Error('More options menu not found for result image');
    return btn;
  }, imageUrl);
  await nativeClick(page, menu);
  await menu.dispose();
  await sleep(350);
  await clickNamedControl(page, 'Download', { selectOnlyIfNeeded: false });
  await sleep(350);

  const downloadPromise = page.waitForEvent('download', { timeout: 180000 });
  await clickNamedControl(page, '2K Upscaled', { selectOnlyIfNeeded: false });
  const download = await downloadPromise;
  const suggested = download.suggestedFilename() || `flow-2k-${Date.now()}.jpg`;
  const dest = path.join(DOWNLOADS, suggested);
  await download.saveAs(dest);
  await page.keyboard.press('Escape').catch(() => {});
  return dest;
}

async function ensureFlowProject(page, preferredUrl) {
  let url = preferredUrl || loadSavedProjectUrl();
  let newProjectAttempts = 0;
  let lastClickAt = 0;

  if (url && isInFlowProject(url)) {
    console.log(`Opening Flow project: ${url}`);
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120000 });
  } else {
    const home = 'https://flow.google.com/';
    console.log(`No saved project URL. Opening ${home}`);
    await page.goto(home, { waitUntil: 'domcontentloaded', timeout: 120000 });
    await sleep(2500);
  }

  const deadline = Date.now() + 5 * 60 * 1000;
  while (Date.now() < deadline) {
    const current = page.url();

    if (isInFlowProject(current) || (isFlowHost(current) && await hasFlowEditor(page))) {
      if (isInFlowProject(current)) saveProjectUrl(current);
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

async function runJob(page, { helperUrl, token, jobId, delaySec, regenerate }) {
  const creds = { helperUrl, token, jobId, regenerate };
  await configureFlow(page);

  while (true) {
    const claimed = await helperFetch(helperUrl, token, `/jobs/${jobId}/claim-next`, {
      method: 'POST',
      body: {
        owner: 'cli-playwright',
        flow_project_url: page.url(),
      },
    });
    if (!claimed.scene) {
      console.log(claimed.reason === 'done' ? 'Queue complete.' : `Stopped: ${claimed.reason}`);
      return claimed;
    }
    const scene = claimed.scene;
    console.log(`\n=== Scene ${scene.scene} ===`);
    try {
      await configureFlow(page);
      const beforeUrls = await page.evaluate(() =>
        [...document.querySelectorAll('flow-image-tile img, img')]
          .filter((el) => el.complete && el.naturalWidth >= 256)
          .map((el) => el.currentSrc || el.src)
          .filter(Boolean),
      );
      const beforeBatches = await page.locator('button[aria-label="Download batch"]').count();

      await helperFetch(helperUrl, token, `/jobs/${jobId}/scenes/${scene.scene}/status`, {
        method: 'POST',
        body: { status: 'submitting' },
      });
      await fillPrompt(page, scene.text);
      await sleep(500);
      await clickGenerate(page);
      console.log(`Scene ${scene.scene}: generating…`);
      await helperFetch(helperUrl, token, `/jobs/${jobId}/scenes/${scene.scene}/status`, {
        method: 'POST',
        body: { status: 'generating' },
      });
      const fresh = await waitForNewImage(page, beforeUrls, beforeBatches);
      console.log(`Scene ${scene.scene}: upscaling 2K…`);
      await helperFetch(helperUrl, token, `/jobs/${jobId}/scenes/${scene.scene}/status`, {
        method: 'POST',
        body: { status: 'upscaling' },
      });
      const downloadPath = await download2K(page, fresh[0]);
      console.log(`Scene ${scene.scene}: saving ${downloadPath}`);
      const saved = await helperFetch(helperUrl, token, `/jobs/${jobId}/scenes/${scene.scene}/save`, {
        method: 'POST',
        body: {
          download_path: downloadPath,
          regenerate,
        },
      });
      console.log(
        `Scene ${scene.scene}: saved → ${saved.saved.path} (${saved.saved.width}x${saved.saved.height})`,
      );
    } catch (err) {
      const message = err?.message || String(err);
      console.error(`Scene ${scene.scene} failed: ${message}`);
      const needsReview = /needs review|did not start|timeout/i.test(message);
      await helperFetch(helperUrl, token, `/jobs/${jobId}/scenes/${scene.scene}/status`, {
        method: 'POST',
        body: {
          status: needsReview ? 'needs_review' : 'failed',
          error_category: needsReview ? 'needs_review' : 'unknown',
          error_message: message,
        },
      }).catch(() => {});
      throw err;
    }
    await sleep(delaySec * 1000);
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
  else {
    body.scene_from = args.from;
    body.scene_to = args.to;
  }
  const job = await helperFetch(args.helperUrl, token, '/jobs', { method: 'POST', body });
  console.log(`Job ${job.job.job_id} · ${JSON.stringify(job.summary)}`);

  if (job.summary.remaining === 0 && !args.regenerate) {
    console.log('Nothing to do — selected scenes already completed.');
    console.log(`Images dir: ${job.job.images_dir}`);
    return;
  }

  const { page, mode } = await openBrowserContext();

  try {
    const projectUrl = await ensureFlowProject(page, args.projectUrl);
    await runJob(page, {
      helperUrl: args.helperUrl,
      token,
      jobId: job.job.job_id,
      delaySec: args.delaySec,
      regenerate: args.regenerate,
    });
    console.log('\nDone.');
    console.log(`Project: ${projectUrl}`);
    console.log(`Images:  ${job.job.images_dir}`);
  } finally {
    // Keep your real Chrome open; only close the automation tab.
    await sleep(1000);
    if (mode === 'cdp') {
      await page.close().catch(() => {});
    }
  }
}

main().catch((err) => {
  console.error('\nERROR:', err.message || err);
  process.exit(1);
});
