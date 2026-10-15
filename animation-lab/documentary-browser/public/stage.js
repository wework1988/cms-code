const stage = document.querySelector("#stage");
let plan = null;
let timeline = null;

function ease(value) {
  const v = Math.max(0, Math.min(1, value));
  return v * v * (3 - 2 * v);
}

function beatProgress(beat, seconds) {
  const span = Math.max(0.001, beat.end - beat.start);
  if (seconds <= beat.start) return 0;
  if (seconds >= beat.end) return 1;
  return ease((seconds - beat.start) / span);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function emphasisHtml(text, phrase) {
  const safe = escapeHtml(text);
  if (!phrase || !text.includes(phrase)) return safe;
  return safe.replace(escapeHtml(phrase), `<span class="mark">${escapeHtml(phrase)}</span>`);
}

function assetUrl(path) {
  return `/asset?path=${encodeURIComponent(path)}`;
}

function applyPreset(name) {
  stage.className = `preset-${name || "cinematic_dark"}`;
}

function addTimeline(target, properties, beat) {
  timeline.add({
    targets: target,
    easing: "cubicBezier(0.4, 0.0, 0.2, 1)",
    duration: Math.max(1, (beat.end - beat.start) * 1000),
    ...properties,
  }, beat.start * 1000);
}

async function loadPdf(path) {
  const pdfjs = await import("/vendor/pdfjs/pdf.min.mjs");
  pdfjs.GlobalWorkerOptions.workerSrc = "/vendor/pdfjs/pdf.worker.min.mjs";
  pdfjs.GlobalWorkerOptions.standardFontDataUrl = "/vendor/pdfjs/standard_fonts/";
  const pdf = await pdfjs.getDocument(assetUrl(path)).promise;
  const page = await pdf.getPage(plan.page || 1);
  const viewport = page.getViewport({ scale: 1.4 });
  const canvas = document.createElement("canvas");
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
  return canvas;
}

function buildText() {
  const root = document.createElement("div");
  root.className = "safe";
  if (plan.template_id === "quote_annotation") {
    root.innerHTML = `<div class="quote-wrap">
      <div class="quote" id="quote">${emphasisHtml(plan.quote, plan.emphasis)}</div>
      <div class="margin-note" id="note">${escapeHtml(plan.margin_note || "")}</div>
    </div>`;
  } else if (plan.template_id === "contrast_reveal") {
    root.innerHTML = `<div class="contrast">${plan.lines.map((line) =>
      `<div class="line ${line.role === "takeaway" ? "takeaway" : ""}" id="${line.id}">${emphasisHtml(line.text, line.emphasis)}</div>`
    ).join("")}</div>`;
  } else {
    root.innerHTML = `<div class="kicker">${escapeHtml(plan.kicker || "Statement")}</div>
      <h1 class="title">${escapeHtml(plan.title || "")}</h1>
      ${plan.lines.map((line) => `<div class="line${line.role === "takeaway" ? " takeaway" : ""}" id="${line.id}">${emphasisHtml(line.text, line.emphasis)}</div>`).join("")}`;
  }
  stage.appendChild(root);
  plan.beats.forEach((beat) => {
    const target = document.getElementById(beat.target);
    if (!target) return;
    if (beat.action === "reveal") addTimeline(target, { opacity: [0, 1], translateY: [18, 0] }, beat);
    if (beat.action === "emphasize") {
      const mark = target.querySelector(".mark");
      if (mark) addTimeline(mark, { backgroundSize: ["0% 0.42em", "100% 0.42em"] }, beat);
    }
    if (beat.action === "dim") addTimeline(target, { opacity: [1, 0.45] }, beat);
  });
}

function buildPhoto() {
  const root = document.createElement("div");
  root.className = plan.template_id === "archival_frame" ? "archival-mat" : "safe";
  const images = plan.images;
  if (plan.template_id === "paired_annotation") {
    root.innerHTML = `<div class="pair">
      <div class="frame-photo"><img id="img_a" src="${assetUrl(images[0].path)}" alt="" style="opacity:0" /></div>
      <div class="bridge" id="bridge">${escapeHtml(plan.bridge || "")}</div>
      <div class="frame-photo"><img id="img_b" src="${assetUrl(images[1].path)}" alt="" style="opacity:0" /></div>
    </div><div class="caption" id="caption" style="position:relative;opacity:0">${escapeHtml(plan.caption || "")}</div>`;
  } else {
    root.innerHTML = `<div class="frame-photo" style="height:${plan.template_id === "archival_frame" ? "760px" : "820px"}">
      <img id="hero" src="${assetUrl(images[0].path)}" alt="" />
      <div class="focus-rect" id="focus"></div>
      <div class="caption" id="caption">${escapeHtml(images[0].caption || "")}</div>
    </div>`;
  }
  stage.appendChild(root);
  if (document.getElementById("bridge")) {
    addTimeline("#img_a", { opacity: [0, 1] }, plan.beats[0]);
    addTimeline("#bridge", { opacity: [0, 1] }, plan.beats[1]);
    addTimeline("#img_b", { opacity: [0, 1] }, plan.beats[2] || plan.beats[1]);
    addTimeline("#caption", { opacity: [0, 1] }, plan.beats[plan.beats.length - 1]);
  }
}

function textFrame(seconds) {
  if (plan.animation_type !== "text_highlighting") return;
  for (const beat of plan.beats) {
    const progress = beatProgress(beat, seconds);
    const element = document.getElementById(beat.target);
    if (!element) continue;
    if (beat.action === "reveal") {
      element.style.opacity = String(progress);
      element.style.transform = `translateY(${(18 * (1 - progress)).toFixed(2)}px)`;
    }
    if (beat.action === "emphasize") {
      const mark = element.querySelector(".mark");
      if (mark) mark.style.backgroundSize = `${(progress * 100).toFixed(2)}% 0.42em`;
    }
    if (beat.action === "dim") element.style.opacity = String(1 - 0.55 * progress);
  }
}

function photoFrame(seconds) {
  const hero = document.getElementById("hero");
  if (!hero || plan.template_id === "paired_annotation") return;
  const beats = plan.beats.filter((beat) => Number.isInteger(beat.image_index));
  let chosen = beats[0];
  for (const beat of beats) {
    if (seconds >= beat.start) chosen = beat;
  }
  if (!chosen) return;
  const image = plan.images[chosen.image_index];
  const url = assetUrl(image.path);
  if (hero.getAttribute("src") !== url) hero.src = url;
  const local = beatProgress(chosen, seconds);
  const drift = chosen.image_index % 2 === 0 ? 1 : -1;
  hero.style.transform = `scale(${(1.04 + 0.03 * local).toFixed(4)}) translateX(${(-0.4 * drift + 0.8 * drift * local).toFixed(2)}%)`;
  const caption = document.getElementById("caption");
  if (caption) {
    caption.textContent = image.caption || "";
    caption.style.opacity = String(Math.min(1, local * 2.2));
  }
  const focus = document.getElementById("focus");
  if (focus && image.focus) {
    focus.style.opacity = String(local > 0.35 ? 1 : 0);
    focus.style.left = `${image.focus.x * 100}%`;
    focus.style.top = `${image.focus.y * 100}%`;
    focus.style.width = `${image.focus.width * 100}%`;
    focus.style.height = `${image.focus.height * 100}%`;
  }
}

function buildCompare() {
  const root = document.createElement("div");
  root.className = "safe";
  const before = plan.before;
  const after = plan.after;
  if (plan.template_id === "split_divider") {
    root.innerHTML = `<div class="split" id="split">
      <img class="layer" src="${assetUrl(before.path)}" alt="" />
      <img class="layer after" id="after" src="${assetUrl(after.path)}" alt="" />
      <div class="divider" id="divider"></div>
    </div><p class="disclosure">${escapeHtml(plan.disclosure || "")}</p>`;
  } else if (plan.template_id === "matched_crossfade") {
    root.innerHTML = `<div class="split"><img class="layer" src="${assetUrl(before.path)}" alt="" />
      <img class="layer" id="after" src="${assetUrl(after.path)}" alt="" style="opacity:0" /></div>
      <p class="disclosure">${escapeHtml(plan.disclosure || "")}</p>`;
  } else {
    root.innerHTML = `<div class="panels">
      <article class="panel-card" id="before_card"><h2>${escapeHtml(before.label)}</h2><div class="panel-photo"><img src="${assetUrl(before.path)}" alt="" /></div></article>
      <article class="panel-card" id="after_card" style="opacity:0"><h2>${escapeHtml(after.label)}</h2><div class="panel-photo"><img src="${assetUrl(after.path)}" alt="" /></div></article>
    </div><p class="disclosure">${escapeHtml(plan.disclosure || "")}</p>`;
  }
  stage.appendChild(root);
  plan.beats.forEach((beat) => {
    if (beat.action === "reveal_after") addTimeline("#after_card, #after", { opacity: [0, 1] }, beat);
    if (beat.action === "divider") addTimeline("#divider", { left: ["8%", "62%"] }, beat);
  });
}

function placeHighlight(box) {
  const region = plan.region;
  if (!region) return;
  box.style.left = `${region.x * 100}%`;
  box.style.top = `${region.y * 100}%`;
  box.style.width = `${region.width * 100}%`;
  box.style.height = `${region.height * 100}%`;
}

async function buildDocument() {
  const root = document.createElement("div");
  const layouts = {
    archival_desk: "safe doc-detail",
    full_frame: "safe doc-full",
    excerpt_panel: "safe doc-detail",
  };
  root.className = layouts[plan.template_id] || "safe doc-detail";
  const frame = document.createElement("div");
  frame.className = "doc-frame";
  const page = document.createElement("div");
  page.className = "doc-page";
  page.id = "doc_page";
  if (plan.asset.kind === "pdf") {
    const canvas = await loadPdf(plan.asset.path);
    page.style.aspectRatio = `${canvas.width} / ${canvas.height}`;
    page.appendChild(canvas);
  } else {
    const img = document.createElement("img");
    img.src = assetUrl(plan.asset.path);
    img.alt = "";
    page.appendChild(img);
  }
  const box = document.createElement("div");
  box.className = "highlight-box";
  box.id = "hl";
  page.appendChild(box);
  placeHighlight(box);
  frame.appendChild(page);
  const side = document.createElement("div");
  side.innerHTML = `<div class="kicker">Page ${plan.page || 1}</div>
    <div class="annotation" id="note">${escapeHtml(plan.annotation || "")}</div>`;
  root.append(frame, side);
  stage.appendChild(root);
  addTimeline("#doc_page", { scale: [1, 1.18] }, plan.beats[1] || plan.beats[0]);
  addTimeline("#hl", { opacity: [0, 1] }, plan.beats[2] || plan.beats[1]);
  addTimeline("#note", { opacity: [0, 1] }, plan.beats[plan.beats.length - 1]);
}

function buildDiagram() {
  const root = document.createElement("div");
  root.className = "safe";
  const svg = window.d3.select(root).append("svg").attr("class", "diagram");
  const nodes = plan.entities;
  const width = 1700;
  const height = 760;
  const positions = new Map();
  if (plan.template_id === "radial") {
    nodes.forEach((node, index) => {
      if (index === 0) positions.set(node.id, [width / 2, height / 2]);
      else {
        const angle = (-Math.PI / 2) + ((index - 1) / (nodes.length - 1)) * Math.PI * 2;
        positions.set(node.id, [width / 2 + Math.cos(angle) * 460, height / 2 + Math.sin(angle) * 250]);
      }
    });
  } else if (plan.template_id === "hierarchy") {
    const levels = new Map();
    nodes.forEach((node) => {
      const level = node.level || 0;
      if (!levels.has(level)) levels.set(level, []);
      levels.get(level).push(node);
    });
    [...levels.keys()].sort().forEach((level) => {
      const row = levels.get(level);
      row.forEach((node, index) => {
        positions.set(node.id, [180 + index * (width - 200) / Math.max(1, row.length - 1 || 1), 120 + level * 240]);
      });
    });
  } else {
    nodes.forEach((node, index) => {
      const span = Math.max(1, nodes.length - 1);
      positions.set(node.id, [280 + index * ((width - 560) / span), height / 2]);
    });
  }
  const edges = svg.append("g");
  plan.edges.forEach((edge, index) => {
    const a = positions.get(edge.from);
    const b = positions.get(edge.to);
    const path = edges.append("line")
      .attr("x1", a[0]).attr("y1", a[1]).attr("x2", a[0]).attr("y2", a[1])
      .attr("stroke", "var(--gold)").attr("stroke-width", 3).attr("id", `edge_${index}`);
    path.datum({ a, b });
    edges.append("text").attr("class", "edge-label").attr("id", `edge_label_${index}`)
      .attr("x", (a[0] + b[0]) / 2).attr("y", (a[1] + b[1]) / 2 - 16)
      .attr("text-anchor", "middle").attr("opacity", 0).text(edge.label);
  });
  nodes.forEach((node) => {
    const [x, y] = positions.get(node.id);
    const g = svg.append("g").attr("id", node.id).attr("opacity", 0);
    g.append("circle").attr("cx", x).attr("cy", y).attr("r", node.id === plan.focus ? 18 : 12).attr("fill", "var(--gold)");
    g.append("text").attr("class", "node-label").attr("x", x).attr("y", y + 48).attr("text-anchor", "middle").text(node.label);
  });
  stage.appendChild(root);
  plan.beats.forEach((beat) => {
    if (beat.action === "reveal_node") addTimeline(`#${beat.target}`, { opacity: [0, 1] }, beat);
    if (beat.action === "draw_edge") addTimeline(`#edge_label_${beat.index}`, { opacity: [0, 1] }, beat);
  });
  window.__edgeProgress = (seconds) => {
    plan.edges.forEach((edge, index) => {
      const beat = plan.beats.find((item) => item.action === "draw_edge" && (item.index === index || (item.indexes || []).includes(index)));
      const line = document.getElementById(`edge_${index}`);
      const label = document.getElementById(`edge_label_${index}`);
      if (!beat || !line) return;
      const p = beatProgress(beat, seconds);
      const a = positions.get(edge.from);
      const b = positions.get(edge.to);
      line.setAttribute("x2", a[0] + (b[0] - a[0]) * p);
      line.setAttribute("y2", a[1] + (b[1] - a[1]) * p);
      if (label) label.setAttribute("opacity", String(p));
    });
  };
}

function buildChart() {
  const root = document.createElement("div");
  root.className = "safe";
  stage.appendChild(root);
  const heading = document.createElement("div");
  heading.className = "kicker";
  heading.textContent = plan.unit || "";
  root.appendChild(heading);
  const width = 1680;
  const height = 760;
  if (plan.template_id === "number_counter") {
    root.innerHTML = `<div class="kicker">${escapeHtml(plan.unit || "")}</div>
      <div class="counter" id="counter">0</div>
      <div class="counter-caption">${escapeHtml(plan.caption || "")}</div>
      <div class="source-label">${escapeHtml(plan.source_label || "")}</div>`;
    return;
  }
  const svg = window.d3.select(root).append("svg").attr("class", "chart");
  const margin = { top: 40, right: 40, bottom: 80, left: 80 };
  const rows = plan.series;
  const d3 = window.d3;
  if (plan.template_id === "line_trend") {
    const x = d3.scalePoint().domain(rows.map((row) => row.label)).range([margin.left, width - margin.right]);
    const y = d3.scaleLinear().domain([0, d3.max(rows, (row) => row.value) * 1.15]).range([height - margin.bottom, margin.top]);
    svg.append("g").attr("transform", `translate(0,${height - margin.bottom})`).call(d3.axisBottom(x));
    svg.append("g").attr("transform", `translate(${margin.left},0)`).call(d3.axisLeft(y).ticks(5));
    const line = d3.line().x((row) => x(row.label)).y((row) => y(row.value));
    svg.append("path").attr("id", "trend").attr("fill", "none").attr("stroke", "var(--gold)").attr("stroke-width", 4)
      .attr("d", line(rows)).attr("stroke-dasharray", function () { return this.getTotalLength(); })
      .attr("stroke-dashoffset", function () { return this.getTotalLength(); });
    rows.forEach((row, index) => {
      svg.append("circle").attr("id", `pt_${index}`).attr("cx", x(row.label)).attr("cy", y(row.value))
        .attr("r", 7).attr("fill", "var(--text)").attr("opacity", 0);
    });
    window.__chartProgress = (seconds) => {
      const path = document.getElementById("trend");
      const length = path.getTotalLength();
      const beat = plan.beats.find((item) => item.action === "draw_series") || plan.beats[1];
      path.setAttribute("stroke-dashoffset", String(length * (1 - beatProgress(beat, seconds))));
      rows.forEach((row, index) => {
        const pointBeat = plan.beats.find((item) => item.action === "reveal_point" && item.index === index) || beat;
        document.getElementById(`pt_${index}`).setAttribute("opacity", String(beatProgress(pointBeat, seconds)));
      });
    };
  } else {
    const x = d3.scaleBand().domain(rows.map((row) => row.label)).range([margin.left, width - margin.right]).padding(0.35);
    const y = d3.scaleLinear().domain([0, d3.max(rows, (row) => row.value) * 1.15]).range([height - margin.bottom, margin.top]);
    svg.append("g").attr("transform", `translate(0,${height - margin.bottom})`).call(d3.axisBottom(x));
    svg.append("g").attr("transform", `translate(${margin.left},0)`).call(d3.axisLeft(y).ticks(5));
    svg.append("line").attr("x1", margin.left).attr("x2", width - margin.right)
      .attr("y1", y(0)).attr("y2", y(0)).attr("stroke", "var(--line)");
    rows.forEach((row, index) => {
      svg.append("rect").attr("id", `bar_${index}`)
        .attr("x", x(row.label)).attr("width", x.bandwidth())
        .attr("y", y(0)).attr("height", 0).attr("fill", index === plan.emphasis_index ? "var(--red)" : "var(--gold)");
    });
    window.__chartProgress = (seconds) => {
      rows.forEach((row, index) => {
        const beat = plan.beats.find((item) => item.action === "reveal_bar" && item.index === index) || plan.beats[1];
        const p = beatProgress(beat, seconds);
        const bar = document.getElementById(`bar_${index}`);
        const full = y(0) - y(row.value);
        bar.setAttribute("height", String(full * p));
        bar.setAttribute("y", String(y(0) - full * p));
      });
    };
  }
  const label = document.createElement("div");
  label.className = "source-label";
  label.textContent = plan.source_label || "";
  stage.appendChild(label);
}

function buildStoryboard() {
  const root = document.createElement("div");
  root.className = "safe";
  if (plan.illustrative !== false) {
    const badge = document.createElement("div");
    badge.className = "rebuild";
    badge.textContent = plan.label || "Illustrative reconstruction";
    stage.appendChild(badge);
  }
  if (plan.template_id === "panel_expand") {
    root.innerHTML = `<div class="story-panels">${plan.images.map((image, index) =>
      `<div class="frame-photo" id="panel_${index}" style="opacity:0"><img src="${assetUrl(image.path)}" alt="" /></div>`
    ).join("")}</div>`;
  } else {
    root.innerHTML = `<div class="story-full frame-photo"><img id="hero" src="${assetUrl(plan.images[0].path)}" alt="" />
      <div class="focus-rect" id="story_focus"></div>
      <div class="caption" id="caption">${escapeHtml(plan.images[0].caption || "")}</div></div>`;
  }
  stage.appendChild(root);
  if (plan.template_id === "panel_expand") {
    plan.images.forEach((image, index) => {
      const beat = plan.beats[index] || plan.beats[plan.beats.length - 1];
      addTimeline(`#panel_${index}`, { opacity: [0, 1], translateY: [20, 0] }, beat);
    });
  } else {
    addTimeline("#hero", { scale: [1.02, 1.05] }, plan.beats[0]);
    addTimeline("#caption", { opacity: [0, 1] }, plan.beats[1] || plan.beats[0]);
  }
}

async function build() {
  applyPreset(plan.style_preset);
  timeline = window.anime.timeline({ autoplay: false, easing: "linear" });
  const builders = {
    text_highlighting: buildText,
    photo_sequences: buildPhoto,
    before_after: buildCompare,
    document_highlighting: buildDocument,
    relationship_diagrams: buildDiagram,
    data_animations: buildChart,
    storyboard_reconstructions: buildStoryboard,
  };
  await builders[plan.animation_type]();
  if (plan.disclosure && !stage.querySelector(".disclosure") && plan.animation_type !== "before_after") {
    const note = document.createElement("div");
    note.className = "source-label";
    note.textContent = plan.disclosure;
    stage.appendChild(note);
  }
  const paths = [];
  for (const image of plan.images || []) if (image.path) paths.push(image.path);
  if (plan.before?.path) paths.push(plan.before.path);
  if (plan.after?.path) paths.push(plan.after.path);
  if (plan.asset?.path && plan.asset.kind !== "pdf") paths.push(plan.asset.path);
  await Promise.all(paths.map(async (path) => {
    const img = new Image();
    img.src = assetUrl(path);
    if (img.decode) await img.decode();
  }));
  const images = [...stage.querySelectorAll("img")];
  await Promise.all(images.map((img) => img.decode?.() || Promise.resolve()));
  if (document.fonts) await document.fonts.ready;
}

function diagramFrame(seconds) {
  if (!plan || plan.animation_type !== "relationship_diagrams") return;
  for (const beat of plan.beats) {
    if (beat.action !== "reveal_node" && beat.action !== "reveal_nodes") continue;
    const ids = beat.targets || [beat.target];
    const progress = beatProgress(beat, seconds);
    for (const id of ids) {
      const element = document.getElementById(id);
      if (element) element.setAttribute("opacity", String(progress));
    }
  }
}

function compareFrame(seconds) {
  if (!plan || plan.animation_type !== "before_after") return;
  for (const beat of plan.beats) {
    if (beat.action !== "reveal_after") continue;
    const progress = String(beatProgress(beat, seconds));
    for (const id of ["after", "after_card"]) {
      const element = document.getElementById(id);
      if (element) element.style.opacity = progress;
    }
  }
}

function documentFrame(seconds) {
  if (!plan || plan.animation_type !== "document_highlighting") return;
  const zoom = plan.beats.find((beat) => beat.action === "zoom");
  const page = document.getElementById("doc_page");
  if (zoom && page) {
    const progress = beatProgress(zoom, seconds);
    const origin = plan.region
      ? `${(plan.region.x + plan.region.width / 2) * 100}% ${(plan.region.y + plan.region.height / 2) * 100}%`
      : "center center";
    page.style.transformOrigin = origin;
    page.style.transform = `scale(${(1 + 0.22 * progress).toFixed(4)})`;
  }
  const sweep = plan.beats.find((beat) => beat.action === "highlight");
  const box = document.getElementById("hl");
  if (sweep && box) box.style.opacity = String(beatProgress(sweep, seconds));
  const noteBeat = plan.beats.find((beat) => beat.action === "annotate");
  const note = document.getElementById("note");
  if (noteBeat && note) note.style.opacity = String(beatProgress(noteBeat, seconds));
}

window.renderAt = (timeMs) => {
  const seconds = timeMs / 1000;
  if (timeline) timeline.seek(timeMs);
  if (plan.template_id === "number_counter") {
    const beat = plan.beats.find((item) => item.action === "count") || plan.beats[1];
    const value = plan.series[0].value * beatProgress(beat, seconds);
    const counter = document.getElementById("counter");
    if (counter) counter.textContent = `${Math.round(value)}${plan.unit === "%" ? "%" : ""}`;
  }
  if (plan.template_id === "split_divider") {
    const beat = plan.beats.find((item) => item.action === "divider");
    const after = document.getElementById("after");
    const divider = document.getElementById("divider");
    if (beat && after && divider) {
      const p = 8 + 54 * beatProgress(beat, seconds);
      after.style.clipPath = `inset(0 0 0 ${p}%)`;
      divider.style.left = `${p}%`;
    }
  }
  if (typeof window.__chartProgress === "function") window.__chartProgress(seconds);
  if (typeof window.__edgeProgress === "function") window.__edgeProgress(seconds);
  if (plan.animation_type === "photo_sequences") photoFrame(seconds);
  textFrame(seconds);
  diagramFrame(seconds);
  compareFrame(seconds);
  documentFrame(seconds);
  if (plan.template_id === "cinematic_sequence" || plan.template_id === "detail_focus") {
    const hero = document.getElementById("hero");
    const caption = document.getElementById("caption");
    const sequenced = plan.beats.filter((beat) => Number.isInteger(beat.image_index));
    let chosenBeat = sequenced[0];
    for (const beat of sequenced) {
      if (seconds >= beat.start) chosenBeat = beat;
    }
    const image = plan.images[chosenBeat ? chosenBeat.image_index : 0];
    if (hero && image && hero.getAttribute("src") !== assetUrl(image.path)) hero.src = assetUrl(image.path);
    if (caption && image) {
      caption.textContent = image.caption || "";
      caption.style.opacity = "1";
    }
    const focus = document.getElementById("story_focus");
    if (focus && image?.focus && chosenBeat) {
      const local = beatProgress(chosenBeat, seconds);
      focus.style.opacity = String(local > 0.4 ? 1 : 0);
      focus.style.left = `${image.focus.x * 100}%`;
      focus.style.top = `${image.focus.y * 100}%`;
      focus.style.width = `${image.focus.width * 100}%`;
      focus.style.height = `${image.focus.height * 100}%`;
    }
  }
};

window.ready = (async () => {
  try {
    plan = await (await fetch("/plan.json")).json();
    await build();
    window.renderAt(0);
    window.sampleReady = true;
  } catch (error) {
    window.sampleError = String(error && error.stack || error);
    throw error;
  }
})();
