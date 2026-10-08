(() => {
  if (window.__cmsFlowImageAgent) return;
  window.__cmsFlowImageAgent = true;

  const state = {
    prompt: null,
    generate: null,
    output: null,
    running: false,
    stopped: false,
    paused: false,
    status: 'Ready · Nano Banana 2.1 · 16:9',
    jobId: null,
    lastError: null,
  };

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  function visible(el) {
    if (!el?.isConnected) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function normalize(text) {
    return String(text || '').replace(/\s+/g, ' ').trim();
  }

  function label(el) {
    const explicit = el.getAttribute('aria-label');
    if (explicit) return normalize(explicit);
    const labelled = el.getAttribute('aria-labelledby');
    if (labelled) {
      const text = labelled.split(/\s+/).map((id) => document.getElementById(id)?.textContent || '').join(' ');
      if (text.trim()) return normalize(text);
    }
    if (el.labels?.length) return normalize([...el.labels].map((l) => l.textContent).join(' '));
    const copy = el.cloneNode(true);
    copy.querySelectorAll('svg,[aria-hidden="true"],.material-icons,.material-symbols-outlined,.material-symbols-rounded,i')
      .forEach((icon) => icon.remove());
    return normalize(copy.textContent || '');
  }

  const controls = () => [...document.querySelectorAll(
    'button,input[type="radio"],[role="button"],[role="radio"],[role="tab"],[role="option"],[role="menuitem"],[role="combobox"]',
  )].filter((el) => visible(el) || (el.type === 'radio' && [...(el.labels || [])].some(visible)));

  const isSelected = (el) => el.checked === true
    || ['aria-checked', 'aria-selected', 'aria-pressed'].some((attr) => el.getAttribute(attr) === 'true')
    || ['checked', 'active', 'on'].includes(el.getAttribute('data-state'));

  function matches(el, name) {
    const text = label(el);
    if (text.toLowerCase() === name.toLowerCase()) return true;
    const tokens = text.replace(/\b(?:image|photo|crop_landscape|crop_square|crop_portrait|aspect_ratio|arrow_drop_down|expand_more|videocam)\b/g, '').trim();
    if (tokens.toLowerCase() === name.toLowerCase()) return true;
    if (name === 'Image') return /^(?:image\s*){1,2}$/i.test(text);
    return false;
  }

  function findControl(name) {
    let candidates = controls().filter((el) => matches(el, name));
    const radios = candidates.filter((el) => ['radio', 'tab'].includes(el.getAttribute('role')) || el.type === 'radio');
    if (radios.length) candidates = radios;
    candidates = candidates.filter((el) => !candidates.some((other) => other !== el && el.contains(other)));
    if (candidates.length !== 1) {
      throw Error(`Could not identify Flow's ${name} control (${candidates.length} matches). No generation was submitted.`);
    }
    return candidates[0];
  }

  async function choose(name) {
    if (state.stopped) throw Error('Stopped.');
    const el = findControl(name);
    if (!isSelected(el)) el.click();
    await sleep(350);
  }

  function detect() {
    const boxes = [...document.querySelectorAll('textarea,[contenteditable="true"],[role="textbox"]')].filter(visible);
    if (boxes.length !== 1) {
      throw Error('Could not identify the Flow prompt box. Open a Flow project and close any dialogs.');
    }
    state.prompt = boxes[0];
    state.generate = findControl('Start generation');
    state.output = document.body;
  }

  function collectResultIds() {
    return [...document.querySelectorAll('flow-image-tile')].map((tile, index) => {
      const img = tile.querySelector('img');
      const src = img?.currentSrc || img?.src || '';
      return {
        index,
        src,
        id: tile.getAttribute('data-id')
          || tile.getAttribute('id')
          || src
          || `tile-${index}`,
      };
    });
  }

  function galleryImageUrls() {
    return [...document.querySelectorAll('flow-image-tile img, img')]
      .filter((el) => {
        const r = el.getBoundingClientRect();
        return el.complete && el.naturalWidth >= 256 && r.width >= 100 && r.height >= 100;
      })
      .map((el) => el.currentSrc || el.src)
      .filter(Boolean);
  }

  async function configure() {
    state.status = 'Setting up Nano Banana 2.1 · 16:9…';
    const agent = controls().find((el) => label(el) === 'Agent');
    if (agent && (agent.getAttribute('aria-pressed') === 'true' || agent.getAttribute('aria-checked') === 'true')) {
      agent.click();
      await sleep(350);
    }
    if (!controls().some((el) => matches(el, '16:9'))) {
      findControl('Settings trigger').click();
      await sleep(500);
    }
    await choose('Image');
    await choose('16:9');
    await choose('x1');
    const trigger = findControl('Select model family');
    if (!/Nano Banana 2\.1/.test(trigger.textContent || '')) {
      trigger.click();
      await sleep(500);
      const options = controls().filter((el) => /(?:^|🍌\s*)Nano Banana 2\.1(?:$|\s)/.test(label(el)) && el !== trigger);
      if (options.length !== 1) {
        throw Error('Nano Banana 2.1 could not be selected in Flow. No generation was submitted.');
      }
      options[0].click();
      await sleep(500);
    }
    const selected = findControl('Select model family');
    if (!/Nano Banana 2\.1/.test(selected.textContent || '')) {
      throw Error('Could not confirm Nano Banana 2.1. No generation was submitted.');
    }
    for (const name of ['Image', '16:9', 'x1']) {
      const el = findControl(name);
      if (!isSelected(el)) throw Error(`Could not confirm ${name}. No generation was submitted.`);
    }
    findControl('Settings trigger').click();
    await sleep(350);
    detect();
  }

  async function nativeClick(el) {
    el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    await sleep(100);
    const r = el.getBoundingClientRect();
    if (!el.isConnected || !r.width || !r.height) throw Error('Flow control changed before clicking.');
    const result = await chrome.runtime.sendMessage({
      type: 'nativeClick',
      x: r.left + r.width / 2,
      y: r.top + r.height / 2,
    });
    if (!result?.ok) throw Error(result?.error || 'Native click was not confirmed.');
  }

  function fill(el, value) {
    el.focus();
    if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) {
      const prototype = el instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(prototype, 'value').set.call(el, value);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    } else {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(el);
      selection.removeAllRanges();
      selection.addRange(range);
      if (!document.execCommand('insertText', false, value)) {
        throw Error('Flow did not accept the prompt. Please reopen the project and try again.');
      }
    }
    const current = (el.value ?? el.textContent) || '';
    if (current.trim() !== value.trim()) {
      throw Error('Could not verify the complete prompt text in the editor. Queue stopped.');
    }
  }

  async function helperFetch(path, options = {}) {
    const result = await chrome.runtime.sendMessage({
      type: 'helperFetch',
      helperUrl: options.helperUrl,
      token: options.token,
      path,
      method: options.method || 'GET',
      body: options.body,
    });
    if (result?.error) throw Error(result.error);
    if (!result?.data?.ok) throw Error(result?.data?.error || `Helper HTTP ${result?.status}`);
    return result.data;
  }

  async function setSceneStatus(jobId, scene, fields, creds) {
    return helperFetch(`/jobs/${jobId}/scenes/${scene}/status`, {
      ...creds,
      method: 'POST',
      body: fields,
    });
  }

  function classifyFailure(message) {
    const m = String(message || '').toLowerCase();
    if (/policy|safety|blocked|violat/.test(m)) return 'policy_rejection';
    if (/credit|quota|billing|insufficient/.test(m)) return 'insufficient_credits';
    if (/rate|too many|429/.test(m)) return 'rate_limit';
    if (/sign in|auth|login|session/.test(m)) return 'authentication_required';
    if (/captcha|challenge|verify you/.test(m)) return 'captcha_challenge';
    if (/network|offline|failed to fetch/.test(m)) return 'network_failure';
    if (/model|nano banana/.test(m) && /unavailable|could not/.test(m)) return 'model_unavailable';
    if (/control|selector|identify|prompt box/.test(m)) return 'ui_selector_failure';
    if (/timeout|within 3 minutes|12 seconds/.test(m)) return 'generation_timeout';
    return 'unknown';
  }

  async function download2K(imageUrl, sceneMeta, creds) {
    state.status = `Scene ${sceneMeta.scene}: opening 2K download…`;
    const image = [...document.querySelectorAll('flow-image-tile img')]
      .find((el) => (el.currentSrc || el.src) === imageUrl);
    const tile = image?.closest('flow-image-tile');
    const menu = tile?.querySelector('button[aria-label="More options"]');
    if (!menu) throw Error('Image generated, but its More options menu could not be found.');
    await setSceneStatus(creds.jobId, sceneMeta.scene, { status: 'upscaling', flow_result_id: sceneMeta.resultId }, creds);
    await nativeClick(menu);
    await sleep(350);
    await nativeClick(findControl('Download'));
    await sleep(350);
    const upscale = findControl('2K Upscaled');
    if (upscale.disabled || upscale.getAttribute('aria-disabled') === 'true') {
      throw Error('Flow has disabled 2K upscaling for this account.');
    }
    const since = new Date().toISOString();
    await setSceneStatus(creds.jobId, sceneMeta.scene, { status: 'downloading' }, creds);
    await nativeClick(upscale);
    const downloadDeadline = Date.now() + 180000;
    let download = null;
    while (Date.now() < downloadDeadline && !state.stopped) {
      await sleep(1500);
      const result = await chrome.runtime.sendMessage({ type: 'downloadStatus', since });
      if (result?.error) throw Error(result.error);
      if (result?.interrupted) throw Error('Chrome interrupted the 2K download. Check Chrome Downloads.');
      if (result?.complete && result.download?.filename) {
        download = result.download;
        break;
      }
    }
    if (state.stopped) return null;
    if (!download) {
      throw Error('2K upscaling was requested, but download completion was not confirmed.');
    }
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
    state.status = `Scene ${sceneMeta.scene}: saving into CMS images/…`;
    const saved = await helperFetch(`/jobs/${creds.jobId}/scenes/${sceneMeta.scene}/save`, {
      ...creds,
      method: 'POST',
      body: {
        download_path: download.filename,
        download_id: String(download.id),
        flow_result_id: sceneMeta.resultId,
        regenerate: Boolean(creds.regenerate),
      },
    });
    return saved;
  }

  async function generateOne(promptText, sceneMeta, creds) {
    detect();
    if (!visible(state.prompt) || !visible(state.generate)) {
      throw Error('Flow controls changed. Reopen the project and try again.');
    }
    const beforeUrls = new Set(galleryImageUrls());
    const beforeIds = new Set(collectResultIds().map((r) => r.id));
    const batchesBefore = document.querySelectorAll('button[aria-label="Download batch"]').length;

    await setSceneStatus(creds.jobId, sceneMeta.scene, { status: 'submitting' }, creds);
    fill(state.prompt, promptText);
    await sleep(500);
    detect();
    if (state.stopped) return;
    if (state.generate.disabled || state.generate.getAttribute('aria-disabled') === 'true') {
      throw Error('Generate is unavailable. Check the model, credits, and prompt in Flow.');
    }
    await nativeClick(state.generate);
    state.status = `Scene ${sceneMeta.scene}: confirming Flow started…`;

    const submitDeadline = Date.now() + 12000;
    while (Date.now() < submitDeadline && !state.stopped
      && document.querySelectorAll('button[aria-label="Download batch"]').length <= batchesBefore) {
      await sleep(250);
    }
    if (state.stopped) return;
    if (document.querySelectorAll('button[aria-label="Download batch"]').length <= batchesBefore) {
      // Uncertain — may still have started without a batch button.
      const maybeNew = collectResultIds().some((r) => !beforeIds.has(r.id));
      if (!maybeNew) {
        await setSceneStatus(creds.jobId, sceneMeta.scene, {
          status: 'needs_review',
          error_category: 'uncertain_submission',
          error_message: 'No new generation batch confirmed after native click. Not retrying automatically.',
        }, creds);
        throw Error(`Scene ${sceneMeta.scene}: needs review — submission not confirmed.`);
      }
    }

    await setSceneStatus(creds.jobId, sceneMeta.scene, { status: 'generating' }, creds);
    state.status = `Scene ${sceneMeta.scene}: generating…`;

    const deadline = Date.now() + 180000;
    let fresh = [];
    let stableSince = 0;
    let previous = '';
    let resultId = null;
    while (Date.now() < deadline && !state.stopped) {
      await sleep(1000);
      // Failure banners
      const bodyText = document.body.innerText || '';
      if (/policy|couldn't generate|can't generate|violat/i.test(bodyText)
        && /blocked|safety|policy|violat/i.test(bodyText.slice(-2000))) {
        // soft check — only if no fresh images
        const urls = [...new Set(galleryImageUrls())].filter((url) => !beforeUrls.has(url));
        if (!urls.length) {
          const err = Error('Flow policy rejection or generation blocked.');
          err.category = 'policy_rejection';
          throw err;
        }
      }
      fresh = [...new Set(galleryImageUrls())].filter((url) => !beforeUrls.has(url));
      const newResults = collectResultIds().filter((r) => !beforeIds.has(r.id));
      if (newResults.length) resultId = newResults[0].id;
      const signature = JSON.stringify(fresh);
      if (fresh.length && signature === previous) {
        if (Date.now() - stableSince >= 5000) break;
      } else {
        previous = signature;
        stableSince = Date.now();
      }
    }
    if (state.stopped) return;
    if (!fresh.length) {
      await setSceneStatus(creds.jobId, sceneMeta.scene, {
        status: 'needs_review',
        error_category: 'generation_timeout',
        error_message: 'No confirmed new image within 3 minutes. Not auto-retrying.',
      }, creds);
      throw Error(`Scene ${sceneMeta.scene}: needs review — no image confirmed.`);
    }

    sceneMeta.resultId = resultId || fresh[0];
    await download2K(fresh[0], sceneMeta, creds);
    state.status = `Scene ${sceneMeta.scene}: completed`;
  }

  async function runJob(options) {
    state.running = true;
    state.stopped = false;
    state.paused = false;
    state.jobId = options.jobId;
    state.lastError = null;
    const creds = {
      jobId: options.jobId,
      helperUrl: options.helperUrl,
      token: options.token,
      regenerate: Boolean(options.regenerate),
    };
    try {
      await configure();
      while (!state.stopped) {
        const claimed = await helperFetch(`/jobs/${options.jobId}/claim-next`, {
          ...creds,
          method: 'POST',
          body: {
            owner: 'extension',
            flow_project_url: options.flowProjectUrl || location.href,
            retry_failed: Boolean(options.retryFailed),
          },
        });
        if (!claimed.scene) {
          state.status = claimed.reason === 'paused'
            ? 'Paused.'
            : claimed.reason === 'stopped'
              ? 'Stopped. An already submitted generation may still finish in Flow.'
              : 'Queue complete.';
          break;
        }
        const scene = claimed.scene;
        state.status = `Scene ${scene.scene}: configuring…`;
        try {
          await configure();
          await generateOne(scene.text, { scene: scene.scene, resultId: null }, creds);
        } catch (error) {
          const category = error.category || classifyFailure(error.message);
          if (/needs review/i.test(error.message) || category === 'uncertain_submission') {
            state.status = error.message;
            state.paused = true;
            break;
          }
          await setSceneStatus(creds.jobId, scene.scene, {
            status: category === 'policy_rejection' ? 'failed' : 'failed',
            error_category: category,
            error_message: error.message,
          }, creds).catch(() => {});
          if (category === 'policy_rejection') {
            state.status = `Scene ${scene.scene} policy rejection — continuing.`;
            continue;
          }
          // Avoid blind retry if submission may have succeeded
          if (category === 'generation_timeout' || category === 'unknown') {
            await setSceneStatus(creds.jobId, scene.scene, {
              status: 'needs_review',
              error_category: category,
              error_message: error.message,
            }, creds).catch(() => {});
            state.status = `Scene ${scene.scene}: ${error.message}`;
            break;
          }
          state.status = `Scene ${scene.scene} failed (${category}): ${error.message}`;
          break;
        }
        const nextAt = Date.now() + (options.delaySec || 5) * 1000;
        while (Date.now() < nextAt && !state.stopped) await sleep(250);
      }
    } catch (error) {
      state.lastError = error.message;
      state.status = error.message;
    } finally {
      state.running = false;
    }
  }

  chrome.runtime.onMessage.addListener((message, _sender, reply) => {
    try {
      if (message.type === 'stop') {
        state.stopped = true;
        reply({ status: state.status, jobId: state.jobId });
        return;
      }
      if (message.type === 'status') {
        reply({ status: state.status, running: state.running, jobId: state.jobId, lastError: state.lastError });
        return;
      }
      if (message.type === 'startJob') {
        if (state.running) throw Error('A queue is already running.');
        if (!message.jobId) throw Error('jobId required');
        void runJob(message);
        reply({ status: 'Starting job…', jobId: message.jobId });
        return;
      }
      reply({ status: state.status, jobId: state.jobId });
    } catch (error) {
      reply({ status: error.message, jobId: state.jobId });
    }
  });
})();
