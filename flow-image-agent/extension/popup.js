const $ = (id) => document.getElementById(id);
let tabId = null;
let pollTimer = null;

function status(value, isError = false) {
  const el = $('status');
  el.textContent = value;
  el.classList.toggle('err', isError);
}

function diag(value) {
  $('diag').textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}

async function saveSettings() {
  await chrome.storage.local.set({
    helperUrl: $('helperUrl').value.trim(),
    token: $('token').value.trim(),
    storyKey: $('story').value,
    sceneFrom: Number($('sceneFrom').value),
    sceneTo: Number($('sceneTo').value),
    firstTwo: $('firstTwo').checked,
    regenerate: $('regenerate').checked,
  });
}

async function helper(path, options = {}) {
  await saveSettings();
  const result = await chrome.runtime.sendMessage({
    type: 'helperFetch',
    helperUrl: $('helperUrl').value.trim(),
    token: $('token').value.trim(),
    path,
    method: options.method || 'GET',
    body: options.body,
  });
  if (!result?.ok && result?.error) throw new Error(result.error);
  if (!result?.data?.ok) {
    throw new Error(result?.data?.error || `Helper HTTP ${result?.status}`);
  }
  return result.data;
}

async function ensureFlowTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.url) throw new Error('No active tab.');
  const host = new URL(tab.url).hostname;
  if (!['flow.google.com', 'labs.google'].includes(host) ||
      !(tab.url.includes('/project/') || tab.url.includes('/tools/flow'))) {
    throw new Error('Open a signed-in Google Flow project tab first.');
  }
  tabId = tab.id;
  await chrome.scripting.executeScript({ target: { tabId }, files: ['runner.js'] });
  return tab;
}

async function sendRunner(message) {
  if (!tabId) await ensureFlowTab();
  return chrome.tabs.sendMessage(tabId, message);
}

async function refreshStories() {
  status('Loading stories…');
  const data = await helper('/stories');
  const select = $('story');
  const previous = select.value;
  select.innerHTML = '';
  for (const story of data.stories) {
    const opt = document.createElement('option');
    opt.value = story.key;
    opt.textContent = `[${story.category}] ${story.story_id} · ${story.title} · ${story.completed_images}/${story.prompt_count} images`;
    select.appendChild(opt);
  }
  if (!data.stories.length) {
    select.innerHTML = '<option value="">No stories with image-prompts found</option>';
  } else if (previous) {
    select.value = previous;
  }
  status(`Loaded ${data.stories.length} stories.`);
}

async function runPreview() {
  const storyKey = $('story').value;
  if (!storyKey) throw new Error('Select a story.');
  const firstTwo = $('firstTwo').checked;
  const qs = firstTwo
    ? 'first_two=1'
    : `from=${encodeURIComponent($('sceneFrom').value)}&to=${encodeURIComponent($('sceneTo').value)}`;
  const data = await helper(`/stories/${encodeURIComponent(storyKey)}/preview?${qs}`);
  const lines = [
    `Story: ${data.story.title} (${data.story.category}/${data.story.story_id})`,
    `Format: ${data.format}`,
    `Detected scenes: ${data.detected_scenes.length}`,
    `Selected: ${data.selected_scenes.join(', ')}`,
    `Output: ${data.images_dir}`,
    `Expected: ${data.expected_filenames.join(', ')}`,
    `Already completed: ${data.completed_count}`,
    `Model: ${data.settings.model} · ${data.settings.aspect_ratio} · ${data.settings.download_variant}`,
  ];
  $('previewBox').textContent = lines.join('\n');
  diag(data.existing_job ? { existing_job: data.existing_job.job_id, control: data.existing_job.control } : 'No existing job manifest');
  return data;
}

async function startJob() {
  if (!chrome.debugger) {
    throw new Error('Reload the extension so the debugger permission is granted.');
  }
  const tab = await ensureFlowTab();
  await saveSettings();
  const preview = await runPreview();
  const body = {
    story_key: $('story').value,
    regenerate: $('regenerate').checked,
  };
  if ($('firstTwo').checked) body.first_two = true;
  else {
    body.scene_from = Number($('sceneFrom').value);
    body.scene_to = Number($('sceneTo').value);
  }
  const job = await helper('/jobs', { method: 'POST', body });
  status(`Job ${job.job.job_id.slice(0, 8)}… starting on Flow`);
  const result = await sendRunner({
    type: 'startJob',
    jobId: job.job.job_id,
    helperUrl: $('helperUrl').value.trim(),
    token: $('token').value.trim(),
    flowProjectUrl: tab.url,
    settings: preview.settings,
    delaySec: 5,
  });
  status(result.status || 'Running…');
  window.close();
}

async function control(action) {
  const stored = await chrome.storage.local.get(['activeJobId']);
  let jobId = stored.activeJobId;
  if (!jobId) {
    // Ask runner
    try {
      const st = await sendRunner({ type: 'status' });
      jobId = st.jobId;
    } catch { /* ignore */ }
  }
  if (!jobId) throw new Error('No active job id. Start a job first.');
  const data = await helper(`/jobs/${jobId}/${action}`, { method: 'POST', body: {} });
  if (action === 'stop' || action === 'pause') {
    try { await sendRunner({ type: 'stop' }); } catch { /* ignore */ }
  }
  if (action === 'resume' || action === 'retry-failed') {
    await ensureFlowTab();
    const tab = (await chrome.tabs.query({ active: true, currentWindow: true }))[0];
    await sendRunner({
      type: 'startJob',
      jobId,
      helperUrl: $('helperUrl').value.trim(),
      token: $('token').value.trim(),
      flowProjectUrl: tab.url,
      retryFailed: action === 'retry-failed',
      delaySec: 5,
    });
  }
  status(`${action}: ${JSON.stringify(data.summary || data.note || 'ok')}`);
}

async function init() {
  const saved = await chrome.storage.local.get([
    'helperUrl', 'token', 'storyKey', 'sceneFrom', 'sceneTo', 'firstTwo', 'regenerate',
  ]);
  if (saved.helperUrl) $('helperUrl').value = saved.helperUrl;
  if (saved.token) $('token').value = saved.token;
  if (saved.sceneFrom) $('sceneFrom').value = saved.sceneFrom;
  if (saved.sceneTo) $('sceneTo').value = saved.sceneTo;
  if (saved.firstTwo !== undefined) $('firstTwo').checked = saved.firstTwo;
  if (saved.regenerate !== undefined) $('regenerate').checked = saved.regenerate;

  try {
    await ensureFlowTab();
  } catch (e) {
    status(e.message, true);
  }

  try {
    await refreshStories();
    if (saved.storyKey) $('story').value = saved.storyKey;
  } catch (e) {
    status(`Helper: ${e.message}`, true);
    diag(e.message);
  }

  pollTimer = setInterval(async () => {
    try {
      const st = await sendRunner({ type: 'status' });
      if (st?.status) status(st.status);
      if (st?.jobId) await chrome.storage.local.set({ activeJobId: st.jobId });
    } catch { /* popup may outlive runner */ }
  }, 1500);
}

$('refreshStories').onclick = () => refreshStories().catch((e) => status(e.message, true));
$('preview').onclick = () => runPreview().catch((e) => status(e.message, true));
$('start').onclick = () => startJob().catch((e) => status(e.message, true));
$('pause').onclick = () => control('pause').catch((e) => status(e.message, true));
$('resume').onclick = () => control('resume').catch((e) => status(e.message, true));
$('stop').onclick = () => control('stop').catch((e) => status(e.message, true));
$('retryFailed').onclick = () => control('retry-failed').catch((e) => status(e.message, true));
$('firstTwo').onchange = () => {
  const disabled = $('firstTwo').checked;
  $('sceneFrom').disabled = disabled;
  $('sceneTo').disabled = disabled;
};
$('firstTwo').dispatchEvent(new Event('change'));

init().catch((e) => status(e.message, true));
