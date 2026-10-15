const state = {
  studio: null,
  step: 1,
  upload: null,
  previewUrl: "",
  editingId: null,
  pendingLoad: null,
  historyPage: 1,
  poll: null,
};

const $ = (id) => document.getElementById(id);

async function api(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}

function showScreen(name) {
  for (const screen of ["voices", "speak", "history"]) {
    $(`screen-${screen}`).hidden = screen !== name;
  }
  document.querySelectorAll(".nav-button").forEach((button) => {
    if (button.dataset.screen === name) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  api("/api/screen", { method: "POST", body: JSON.stringify({ screen: name }) }).catch(() => {});
  if (name === "history") loadHistory();
  if (name === "speak") loadMiniHistory();
}

async function boot() {
  state.studio = await api("/api/studio");
  fillPresets();
  renderVoices();
  renderEditor();
  showScreen(state.studio.screen || "voices");
  const status = await api("/api/generation");
  if (status.result) showResult(status.result, false);
  if (status.busy) watchGeneration();
}

function fillPresets() {
  const select = $("preset");
  select.innerHTML = "";
  for (const preset of state.studio.presets) {
    const option = document.createElement("option");
    option.value = preset.id;
    option.textContent = preset.label;
    select.appendChild(option);
  }
}

function renderVoices() {
  const query = $("voice-search").value.trim().toLowerCase();
  const voices = state.studio.voices.filter((voice) => {
    if (!query) return true;
    return voice.name.toLowerCase().includes(query) || (voice.description || "").toLowerCase().includes(query);
  });
  const list = $("voice-list");
  list.innerHTML = "";
  if (!state.studio.voices.length) {
    list.innerHTML = `<div class="empty"><p>You haven’t added a voice yet.</p><button type="button" class="primary" id="empty-add">Add your first voice</button></div>`;
    $("empty-add").addEventListener("click", openAdd);
    fillVoiceSelects();
    return;
  }
  if (!voices.length) {
    list.innerHTML = `<div class="empty"><p>No voices match this search.</p></div>`;
    return;
  }
  for (const voice of voices) {
    const row = document.createElement("article");
    row.className = "row";
    row.innerHTML = `
      <span class="avatar" aria-hidden="true">${escapeHtml(voice.initials)}</span>
      <div>
        <div class="name">${escapeHtml(voice.name)} ${voice.selected ? '<span class="badge">Selected</span>' : ""} ${voice.is_default ? '<span class="badge">Default</span>' : ""}</div>
        <div class="meta">${escapeHtml(voice.description || "No description")} · <span class="badge">Hindi</span></div>
      </div>
      <div class="actions">
        <button type="button" data-play="${voice.id}">Play</button>
        <button type="button" class="primary" data-use="${voice.id}">Use voice</button>
        <div class="menu">
          <button type="button" aria-expanded="false" aria-haspopup="menu" data-more="${voice.id}">More</button>
          <div class="menu-panel" hidden role="menu">
            <button type="button" data-rename="${voice.id}">Rename</button>
            <button type="button" data-edit="${voice.id}">Edit details</button>
          </div>
        </div>
      </div>`;
    list.appendChild(row);
  }
  fillVoiceSelects();
}

function fillVoiceSelects() {
  for (const id of ["voice-select", "history-voice"]) {
    const select = $(id);
    const current = select.value;
    const first = id === "history-voice" ? `<option value="">All voices</option>` : `<option value="">Choose a voice</option>`;
    select.innerHTML = first + state.studio.voices.map((voice) =>
      `<option value="${voice.id}">${escapeHtml(voice.name)}</option>`).join("");
    if (id === "voice-select" && state.studio.selected_voice_id) select.value = state.studio.selected_voice_id;
    else if (current) select.value = current;
  }
}

function renderEditor() {
  const voice = state.studio.voices.find((item) => item.id === state.studio.selected_voice_id);
  $("chip-name").textContent = voice ? voice.name : "Choose a voice";
  $("chip-avatar").textContent = voice ? voice.initials : "?";
  $("script").value = state.studio.draft_text || "";
  $("piece-title").value = state.studio.draft_title || "";
  updateCount();
  const hasVoice = Boolean(voice);
  $("generate").disabled = !hasVoice;
  $("no-voice").hidden = hasVoice || state.studio.voices.length > 0;
  applySettings(state.studio.settings);
  $("output-line").textContent = `WAV at ${state.studio.sample_rate} Hz` +
    (state.studio.mp3_available ? ". MP3 is also saved when the encoder is available." : ". MP3 is unavailable on this machine.");
  $("model-line").textContent = `Checkpoint ${state.studio.checkpoint} · chatterbox-tts ${state.studio.package_version} · language ${state.studio.language_id}. A fixed seed reduces variation and does not guarantee identical audio.`;
}

function applySettings(settings) {
  if (!settings) return;
  $("preset").value = settings.preset && [...$("preset").options].some((option) => option.value === settings.preset)
    ? settings.preset : "neutral";
  const preset = state.studio.presets.find((item) => item.id === $("preset").value);
  $("preset-note").textContent = preset ? preset.note : "Experimental tuning, not a guaranteed emotion.";
  $("consistent").checked = settings.consistent !== false;
  $("sentence-pause").value = settings.sentence_pause_ms;
  $("paragraph-pause").value = settings.paragraph_pause_ms;
  $("exaggeration").value = settings.exaggeration;
  $("cfg-weight").value = settings.cfg_weight;
  $("temperature").value = settings.temperature;
  $("repetition").value = settings.repetition_penalty;
  $("min-p").value = settings.min_p;
  $("top-p").value = settings.top_p;
  $("seed").value = settings.seed ?? "";
  $("device").value = settings.device || "auto";
  $("offline").checked = Boolean(settings.offline);
}

function currentSettings() {
  return {
    preset: $("preset").value,
    consistent: $("consistent").checked,
    sentence_pause_ms: Number($("sentence-pause").value),
    paragraph_pause_ms: Number($("paragraph-pause").value),
    exaggeration: Number($("exaggeration").value),
    cfg_weight: Number($("cfg-weight").value),
    temperature: Number($("temperature").value),
    repetition_penalty: Number($("repetition").value),
    min_p: Number($("min-p").value),
    top_p: Number($("top-p").value),
    seed: $("seed").value === "" ? "" : Number($("seed").value),
    device: $("device").value,
    offline: $("offline").checked,
  };
}

function updateCount() {
  $("char-count").textContent = `${$("script").value.length} characters`;
}

let draftTimer;
function scheduleDraft() {
  clearTimeout(draftTimer);
  draftTimer = setTimeout(() => {
    api("/api/draft", {
      method: "PUT",
      body: JSON.stringify({ text: $("script").value, title: $("piece-title").value, screen: "speak" }),
    }).catch(() => {});
  }, 400);
}

async function useVoice(id) {
  const draft = { text: $("script").value, title: $("piece-title").value };
  state.studio = await api(`/api/voices/${id}/use`, { method: "POST" });
  state.studio.draft_text = draft.text;
  state.studio.draft_title = draft.title;
  $("script").value = draft.text;
  $("piece-title").value = draft.title;
  renderVoices();
  renderEditor();
  showScreen("speak");
  scheduleDraft();
}

function openAdd() {
  state.step = 1;
  state.upload = null;
  $("upload-error").textContent = "";
  $("upload-progress").hidden = true;
  showStep();
  $("add-dialog").showModal();
}

function showStep() {
  document.querySelectorAll("[data-step-panel]").forEach((panel) => {
    panel.hidden = Number(panel.dataset.stepPanel) !== state.step;
  });
  document.querySelectorAll("#step-labels li").forEach((item) => {
    item.setAttribute("aria-current", Number(item.dataset.step) === state.step ? "step" : "false");
  });
  $("add-next").textContent = state.step === 3 ? "Save voice" : "Continue";
  $("add-back").hidden = state.step === 1;
}

function uploadFile(file) {
  const body = new FormData();
  body.append("file", file);
  const request = new XMLHttpRequest();
  $("upload-progress").hidden = false;
  $("upload-progress").value = 0;
  $("upload-error").textContent = "";
  request.open("POST", "/api/uploads");
  request.upload.onprogress = (event) => {
    if (event.lengthComputable) $("upload-progress").value = Math.round((event.loaded / event.total) * 100);
  };
  request.onload = () => {
    const data = JSON.parse(request.responseText || "{}");
    if (request.status >= 400) {
      $("upload-error").textContent = data.error || "Upload failed";
      return;
    }
    state.upload = data;
    $("source-audio").src = data.audio_url;
    $("clip-start").value = data.start;
    $("clip-end").value = data.end;
    $("sample-advice").textContent = data.recommendation;
    $("clip-details").textContent = `${data.details.note} Sample rate ${data.details.sample_rate} Hz, ${data.details.channels} channel(s).`;
    state.step = 2;
    showStep();
  };
  request.onerror = () => { $("upload-error").textContent = "Upload failed"; };
  request.send(body);
}

async function previewClip() {
  const data = await api(`/api/uploads/${state.upload.upload_id}/preview`, {
    method: "POST",
    body: JSON.stringify({ start: Number($("clip-start").value), end: Number($("clip-end").value) }),
  });
  state.previewUrl = data.audio_url;
  $("clip-audio").src = data.audio_url;
  $("save-preview").src = data.audio_url;
  $("clip-warnings").textContent = (data.warnings || []).join(" ");
  $("clip-details").textContent = `${data.details.note} Selected sample ${data.duration_sec}s, ${data.details.sample_rate} Hz.`;
}

async function saveVoice() {
  const data = await api("/api/voices", {
    method: "POST",
    body: JSON.stringify({
      upload_id: state.upload.upload_id,
      start: Number($("clip-start").value),
      end: Number($("clip-end").value),
      name: $("voice-name").value,
      description: $("voice-description").value,
      use_now: $("use-now").checked,
    }),
  });
  const draft = { text: $("script").value, title: $("piece-title").value };
  state.studio = data.studio;
  state.studio.draft_text = draft.text;
  state.studio.draft_title = draft.title;
  $("add-dialog").close();
  renderVoices();
  renderEditor();
  if ($("use-now").checked) showScreen("speak");
}

async function generate(newTake) {
  if (!$("script").value.trim() || !$("voice-select").value) return;
  $("generate").disabled = true;
  $("generate-status").textContent = "Starting generation…";
  try {
    await api("/api/generate", {
      method: "POST",
      body: JSON.stringify({
        voice_id: $("voice-select").value,
        text: $("script").value,
        title: $("piece-title").value,
        new_take: Boolean(newTake),
        settings: currentSettings(),
      }),
    });
    watchGeneration();
  } catch (error) {
    $("generate-status").textContent = error.message;
    $("generate").disabled = !$("voice-select").value;
  }
}

function watchGeneration() {
  clearInterval(state.poll);
  state.poll = setInterval(async () => {
    const status = await api("/api/generation");
    if (status.busy) {
      const progress = status.progress || {};
      $("generate-status").textContent = progress.message || "Generating…";
      return;
    }
    clearInterval(state.poll);
    $("generate").disabled = !$("voice-select").value;
    if (status.error) {
      $("generate-status").textContent = status.error;
      return;
    }
    if (status.result) showResult(status.result, false);
    loadMiniHistory();
  }, 800);
}

function showResult(result, autoplay) {
  const notes = (result.notes || []).join(" ");
  $("generate-status").textContent = (result.cache_hit ? "Reused a saved generation. " : "Saved a new generation. ") + notes;
  $("result-audio").src = result.wav_url;
  if (!autoplay) $("result-audio").pause();
  $("download-wav").href = `${result.wav_url}?download=1`;
  $("download-wav").hidden = false;
  $("download-mp3").hidden = !result.mp3_url;
  if (result.mp3_url) $("download-mp3").href = `${result.mp3_url}?download=1`;
}

async function updatePreview() {
  try {
    const data = await api("/api/preview", {
      method: "POST",
      body: JSON.stringify({
        text: $("script").value,
        voice_id: $("voice-select").value,
        use_saved: $("consistent").checked,
        settings: currentSettings(),
      }),
    });
    $("preview-text").textContent = data.preview;
  } catch (error) {
    $("preview-text").textContent = error.message;
  }
}

async function loadHistory() {
  const params = new URLSearchParams({
    q: $("history-search").value,
    voice_id: $("history-voice").value,
    status: $("history-status").value,
    sort: $("history-sort").value,
    page: String(state.historyPage),
    page_size: "12",
  });
  if ($("history-from").value) params.set("from", new Date($("history-from").value + "T00:00:00").toISOString());
  if ($("history-to").value) params.set("to", new Date($("history-to").value + "T23:59:59").toISOString());
  const data = await api(`/api/history?${params}`);
  const list = $("history-list");
  list.innerHTML = "";
  if (!data.total && !filtersActive()) {
    list.innerHTML = `<div class="empty"><p>No generations yet.</p><button type="button" class="primary" id="empty-history">Create your first audio</button></div>`;
    $("empty-history").addEventListener("click", () => showScreen("speak"));
  } else if (!data.total) {
    list.innerHTML = `<div class="empty"><p>No generations match these filters.</p><button type="button" id="empty-clear">Clear filters</button></div>`;
    $("empty-clear").addEventListener("click", clearFilters);
  } else {
    let lastDay = "";
    for (const item of data.items) {
      const day = dayLabel(item.created_at);
      if (day !== lastDay) {
        const heading = document.createElement("h2");
        heading.textContent = day;
        list.appendChild(heading);
        lastDay = day;
      }
      list.appendChild(historyRow(item, false));
    }
  }
  $("page-label").textContent = data.total ? `Page ${data.page} of ${data.pages}` : "";
  $("page-prev").disabled = data.page <= 1;
  $("page-next").disabled = data.page >= data.pages;
}

function filtersActive() {
  return Boolean($("history-search").value || $("history-voice").value || $("history-status").value || $("history-from").value || $("history-to").value);
}

function clearFilters() {
  $("history-search").value = "";
  $("history-voice").value = "";
  $("history-status").value = "";
  $("history-from").value = "";
  $("history-to").value = "";
  $("history-sort").value = "newest";
  state.historyPage = 1;
  loadHistory();
}

async function loadMiniHistory() {
  const data = await api(`/api/history?q=${encodeURIComponent($("mini-search").value)}&page_size=8`);
  const list = $("mini-history");
  const scroll = list.scrollTop;
  list.innerHTML = "";
  let lastDay = "";
  for (const item of data.items) {
    const day = dayLabel(item.created_at);
    if (day !== lastDay) {
      const heading = document.createElement("h2");
      heading.textContent = day;
      list.appendChild(heading);
      lastDay = day;
    }
    list.appendChild(historyRow(item, true));
  }
  list.scrollTop = scroll;
}

function historyRow(item, compact) {
  const row = document.createElement("article");
  row.className = compact ? "mini-row" : "row";
  const duration = item.duration_sec == null ? "" : formatDuration(item.duration_sec);
  const when = item.created_at ? new Date(item.created_at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "Undated";
  row.innerHTML = `
    <span class="avatar" aria-hidden="true">${escapeHtml(initials(item.voice_name))}</span>
    <div>
      <div class="name">${escapeHtml(item.excerpt)}</div>
      <div class="meta">${escapeHtml(item.voice_name)} · ${when}${duration ? ` · ${duration}` : ""} · <span class="badge">${escapeHtml(item.status)}</span></div>
    </div>
    <div class="actions">
      <button type="button" data-hist-play="${item.id}" ${item.audio_available ? "" : "disabled"}>Play</button>
      <a class="button" ${item.audio_available ? `href="/api/history/${item.id}/audio/wav?download=1"` : "hidden"} download>WAV</a>
      <a class="button" ${item.mp3_available ? `href="/api/history/${item.id}/audio/mp3?download=1"` : "hidden"} download>MP3</a>
      <button type="button" data-details="${item.id}">Details</button>
    </div>`;
  if (!item.audio_available) {
    const note = document.createElement("p");
    note.className = "hint";
    note.textContent = "Audio unavailable";
    row.querySelector("div").appendChild(note);
  }
  return row;
}

async function openDetails(id) {
  const item = await api(`/api/history/${id}`);
  state.pendingLoad = item;
  $("detail-title").textContent = item.title || item.excerpt;
  $("detail-meta").textContent = `${item.voice_name} · ${item.created_at || "No stored date"} · ${item.completed_at ? "finished " + item.completed_at : ""}`;
  $("detail-text").textContent = item.text || "";
  $("detail-missing").hidden = item.audio_available;
  $("detail-audio").hidden = !item.audio_available;
  if (item.audio_available) $("detail-audio").src = `/api/history/${item.id}/audio/wav`;
  else $("detail-audio").removeAttribute("src");
  $("detail-wav").hidden = !item.audio_available;
  $("detail-mp3").hidden = !item.mp3_available;
  if (item.audio_available) $("detail-wav").href = `/api/history/${item.id}/audio/wav?download=1`;
  if (item.mp3_available) $("detail-mp3").href = `/api/history/${item.id}/audio/mp3?download=1`;
  $("detail-settings").textContent = item.settings_present
    ? JSON.stringify({ settings: item.settings, seed: item.seed, checkpoint: item.checkpoint, package: item.package_version, device_requested: item.device_requested, device_used: item.device_used, pipeline_version: item.pipeline_version, schema_version: item.schema_version, voice_name_source: item.voice_name_source, duration_source: item.duration_source }, null, 2)
    : "No settings were stored with this generation.";
  $("detail-error").textContent = item.error || "";
  $("detail-dialog").showModal();
}

async function loadIntoEditor() {
  const item = state.pendingLoad;
  if (!item) return;
  const current = $("script").value;
  if (current.trim() && current !== item.text) {
    $("replace-dialog").showModal();
    return;
  }
  await applyLoad(item, false);
}

async function applyLoad(item, restoreSettings) {
  $("script").value = item.text || "";
  $("piece-title").value = item.title || "";
  updateCount();
  scheduleDraft();
  if (item.voice_id && state.studio.voices.some((voice) => voice.id === item.voice_id)) {
    await useVoice(item.voice_id);
  } else {
    showScreen("speak");
  }
  if (restoreSettings && item.settings) {
    applySettings(item.settings);
    if (item.voice_id) {
      await api(`/api/voices/${item.voice_id}/settings`, { method: "PUT", body: JSON.stringify(item.settings) });
    }
  }
  $("detail-dialog").close();
  $("replace-dialog").close();
}

function dayLabel(iso) {
  if (!iso) return "Undated";
  const date = new Date(iso);
  const today = new Date();
  const startToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const startThat = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const diff = Math.round((startToday - startThat) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

function formatDuration(seconds) {
  const total = Math.max(0, Math.round(seconds));
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

function initials(name) {
  const parts = (name || "?").split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, parts[0].charCodeAt(0) < 128 ? 2 : 1);
  return parts.slice(0, 2).map((part) => part[0]).join("");
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}

function insertAtCursor(token) {
  const box = $("script");
  const start = box.selectionStart ?? box.value.length;
  const end = box.selectionEnd ?? start;
  box.value = box.value.slice(0, start) + token + box.value.slice(end);
  box.focus();
  box.selectionStart = box.selectionEnd = start + token.length;
  updateCount();
  scheduleDraft();
}

document.querySelectorAll(".nav-button").forEach((button) => {
  button.addEventListener("click", () => showScreen(button.dataset.screen));
});
$("add-voice").addEventListener("click", openAdd);
$("add-voice-inline").addEventListener("click", openAdd);
$("voice-search").addEventListener("input", renderVoices);
$("voice-list").addEventListener("click", async (event) => {
  const target = event.target.closest("button");
  if (!target) return;
  if (target.dataset.use) useVoice(target.dataset.use);
  if (target.dataset.play) {
    const audio = new Audio(`/api/voices/${target.dataset.play}/reference`);
    audio.play();
  }
  if (target.dataset.more) {
    const panel = target.parentElement.querySelector(".menu-panel");
    panel.hidden = !panel.hidden;
    target.setAttribute("aria-expanded", String(!panel.hidden));
  }
  if (target.dataset.rename || target.dataset.edit) {
    const voice = state.studio.voices.find((item) => item.id === (target.dataset.rename || target.dataset.edit));
    state.editingId = voice.id;
    $("edit-name").value = voice.name;
    $("edit-description").value = voice.description || "";
    $("edit-dialog").showModal();
  }
});
$("edit-save").addEventListener("click", async () => {
  await api(`/api/voices/${state.editingId}`, {
    method: "PATCH",
    body: JSON.stringify({ name: $("edit-name").value, description: $("edit-description").value }),
  });
  state.studio = await api("/api/studio");
  $("edit-dialog").close();
  renderVoices();
  renderEditor();
});
$("edit-cancel").addEventListener("click", () => $("edit-dialog").close());
$("add-cancel").addEventListener("click", () => $("add-dialog").close());
$("add-back").addEventListener("click", () => { state.step = Math.max(1, state.step - 1); showStep(); });
$("add-next").addEventListener("click", async () => {
  try {
    if (state.step === 1) return;
    if (state.step === 2) {
      if (!state.previewUrl) await previewClip();
      state.step = 3;
      showStep();
      return;
    }
    await saveVoice();
  } catch (error) {
    $("upload-error").textContent = error.message;
  }
});
$("upload-file").addEventListener("change", () => {
  if ($("upload-file").files[0]) uploadFile($("upload-file").files[0]);
});
$("drop-zone").addEventListener("dragover", (event) => event.preventDefault());
$("drop-zone").addEventListener("drop", (event) => {
  event.preventDefault();
  if (event.dataTransfer.files[0]) uploadFile(event.dataTransfer.files[0]);
});
$("preview-clip").addEventListener("click", () => previewClip().catch((error) => { $("clip-warnings").textContent = error.message; }));
$("voice-chip").addEventListener("click", () => { $("voice-picker").hidden = !$("voice-picker").hidden; });
$("picker-search").addEventListener("input", () => {
  const query = $("picker-search").value.toLowerCase();
  $("picker-list").innerHTML = state.studio.voices.filter((voice) => voice.name.toLowerCase().includes(query)).map((voice) =>
    `<button type="button" data-pick="${voice.id}">${escapeHtml(voice.name)}</button>`).join("");
});
$("picker-list").addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (button) {
    $("voice-picker").hidden = true;
    useVoice(button.dataset.pick);
  }
});
$("voice-select").addEventListener("change", () => useVoice($("voice-select").value));
$("script").addEventListener("input", () => { updateCount(); scheduleDraft(); });
$("piece-title").addEventListener("input", scheduleDraft);
$("insert-sample").addEventListener("click", () => insertAtCursor(state.studio.sample_text));
$("insert-example").addEventListener("click", () => {
  if ($("script").value.trim() && $("script").value !== state.studio.example_text) {
    if (!window.confirm("Replace the current draft with the narration example?")) return;
  }
  $("script").value = state.studio.example_text;
  updateCount();
  scheduleDraft();
});
$("insert-pause").addEventListener("click", () => insertAtCursor("[pause=300ms] "));
$("generate").addEventListener("click", () => generate(false));
$("new-take").addEventListener("click", () => generate(true));
$("refresh-preview").addEventListener("click", updatePreview);
$("preset").addEventListener("change", () => {
  const preset = state.studio.presets.find((item) => item.id === $("preset").value);
  if (!preset) return;
  $("exaggeration").value = preset.exaggeration;
  $("cfg-weight").value = preset.cfg_weight;
  $("temperature").value = preset.temperature;
  $("repetition").value = preset.repetition_penalty;
  $("min-p").value = preset.min_p;
  $("top-p").value = preset.top_p;
  $("preset-note").textContent = preset.note;
});
$("save-settings").addEventListener("click", async () => {
  const id = $("voice-select").value;
  if (!id) return;
  const saved = await api(`/api/voices/${id}/settings`, { method: "PUT", body: JSON.stringify(currentSettings()) });
  state.studio.settings = saved.settings;
  $("generate-status").textContent = "Saved settings for this voice.";
});
$("reset-settings").addEventListener("click", async () => {
  const id = $("voice-select").value;
  if (!id) return;
  const saved = await api(`/api/voices/${id}/settings/reset`, { method: "POST" });
  state.studio = saved.studio;
  renderEditor();
});
$("tab-settings").addEventListener("click", () => switchTab("settings"));
$("tab-history").addEventListener("click", () => { switchTab("history"); loadMiniHistory(); });
function switchTab(name) {
  $("panel-settings").hidden = name !== "settings";
  $("panel-history").hidden = name !== "history";
  $("tab-settings").setAttribute("aria-selected", String(name === "settings"));
  $("tab-history").setAttribute("aria-selected", String(name === "history"));
}
$("mini-search").addEventListener("input", loadMiniHistory);
$("view-all-history").addEventListener("click", () => showScreen("history"));
$("mini-history").addEventListener("click", onHistoryClick);
$("history-list").addEventListener("click", onHistoryClick);
function onHistoryClick(event) {
  const button = event.target.closest("button");
  if (!button) return;
  if (button.dataset.histPlay) {
    const audio = new Audio(`/api/history/${button.dataset.histPlay}/audio/wav`);
    audio.play();
  }
  if (button.dataset.details) openDetails(button.dataset.details);
}
["history-search", "history-voice", "history-status", "history-sort", "history-from", "history-to"].forEach((id) => {
  $(id).addEventListener("change", () => { state.historyPage = 1; loadHistory(); });
  $(id).addEventListener("input", () => { state.historyPage = 1; loadHistory(); });
});
$("clear-filters").addEventListener("click", clearFilters);
$("page-prev").addEventListener("click", () => { state.historyPage -= 1; loadHistory(); });
$("page-next").addEventListener("click", () => { state.historyPage += 1; loadHistory(); });
$("create-first").addEventListener("click", () => showScreen("speak"));
$("detail-close").addEventListener("click", () => $("detail-dialog").close());
$("load-editor").addEventListener("click", () => loadIntoEditor());
$("replace-yes").addEventListener("click", () => applyLoad(state.pendingLoad, false));
$("replace-no").addEventListener("click", () => $("replace-dialog").close());
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    document.querySelectorAll(".menu-panel").forEach((panel) => { panel.hidden = true; });
    $("voice-picker").hidden = true;
  }
});

boot().catch((error) => {
  document.body.insertAdjacentHTML("afterbegin", `<p class="error">${escapeHtml(error.message)}</p>`);
});
