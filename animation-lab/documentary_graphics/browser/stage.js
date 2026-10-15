const stage = document.querySelector("#stage");
const svgNS = "http://www.w3.org/2000/svg";
let plan = null;

function smooth(value) {
  const clamped = Math.max(0, Math.min(1, value));
  return clamped * clamped * (3 - 2 * clamped);
}

function interpolate(keys, seconds) {
  if (seconds <= keys[0].t) return keys[0];
  if (seconds >= keys[keys.length - 1].t) return keys[keys.length - 1];
  for (let index = 0; index < keys.length - 1; index += 1) {
    const earlier = keys[index];
    const later = keys[index + 1];
    if (seconds >= earlier.t && seconds <= later.t) {
      const weight = smooth((seconds - earlier.t) / (later.t - earlier.t));
      return {
        x: earlier.x + (later.x - earlier.x) * weight,
        y: earlier.y + (later.y - earlier.y) * weight,
      };
    }
  }
  return keys[keys.length - 1];
}

function phase(graphic, seconds) {
  const start = graphic.start;
  const reveal = graphic.reveal;
  const fade = graphic.label_fade || 0;
  const holdEnd = start + reveal + fade + graphic.hold;
  const end = holdEnd + graphic.exit;
  if (seconds < start || seconds >= end) return { line: 0, label: 0, opacity: 0, appear: 0 };
  let line = 1;
  let label = 1;
  if (seconds < start + reveal) {
    line = reveal ? smooth((seconds - start) / reveal) : 1;
    label = 0;
  } else if (fade && seconds < start + reveal + fade) {
    label = smooth((seconds - start - reveal) / fade);
  }
  const opacity = seconds < holdEnd ? 1 : 1 - smooth((seconds - holdEnd) / graphic.exit);
  return { line, label, opacity, appear: fade ? label : line };
}

function el(name, attrs) {
  const node = document.createElementNS(svgNS, name);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
  return node;
}

function build() {
  const { width, height, tokens } = plan;
  document.documentElement.style.width = `${width}px`;
  document.documentElement.style.height = `${height}px`;
  stage.style.width = `${width}px`;
  stage.style.height = `${height}px`;
  const face = document.createElement("style");
  face.textContent = `
    @font-face { font-family: "Doc Devanagari"; src: url("/fonts/NotoSansDevanagari-Regular.woff2") format("woff2"); font-display: block; }
    @font-face { font-family: "Doc Latin"; src: url("/fonts/NotoSans-Regular.woff2") format("woff2"); font-display: block; }
  `;
  document.head.appendChild(face);
  stage.style.setProperty("--ink", tokens.ink);
  stage.style.setProperty("--accent", tokens.accent);
  stage.style.setProperty("--emphasis", tokens.emphasis);
  stage.style.setProperty("--backing", tokens.backing);
  stage.style.setProperty("--shadow", tokens.shadow);
  stage.style.setProperty("--radius", `${tokens.radius}px`);
  stage.style.setProperty("--kicker", `${tokens.kicker}px`);
  stage.style.setProperty("--pad-x", `${tokens.pad_x}px`);
  stage.style.setProperty("--pad-y", `${tokens.pad_y}px`);
  const svg = el("svg", { class: "geometry", viewBox: `0 0 ${width} ${height}`, width, height });
  svg.classList.add("geometry");
  plan.graphics.forEach((graphic) => {
    const group = el("g", { id: `geo_${graphic.id}`, opacity: 0 });
    if (graphic.dim && graphic.rect) {
      const mask = el("mask", { id: `mask_${graphic.id}` });
      mask.appendChild(el("rect", { x: 0, y: 0, width, height, fill: "white" }));
      mask.appendChild(el("rect", {
        x: graphic.rect.x * width,
        y: graphic.rect.y * height,
        width: graphic.rect.width * width,
        height: graphic.rect.height * height,
        fill: "black",
      }));
      svg.appendChild(mask);
      group.appendChild(el("rect", { x: 0, y: 0, width, height, fill: "black", opacity: 0.34, mask: `url(#mask_${graphic.id})` }));
    }
    if (graphic.treatment === "detail_spotlight" || graphic.treatment === "detail_highlight") {
      const shape = graphic.template === "ring"
        ? el("ellipse", { class: "mark", fill: "none", stroke: tokens.line, "stroke-width": tokens.line_width })
        : el("rect", { class: "mark", fill: "none", stroke: tokens.line, "stroke-width": tokens.line_width, rx: graphic.template === "focus_rect" ? 8 : 0 });
      group.appendChild(shape);
    }
    if (graphic.anchor || graphic.anchor_keyframes) {
      group.appendChild(el("polyline", { class: "leader", fill: "none", stroke: tokens.line, "stroke-width": tokens.line_width, "stroke-linecap": "round", "stroke-linejoin": "round" }));
      group.appendChild(el("circle", { class: "dot", r: 4.5, fill: tokens.ink }));
    }
    if (graphic.points && graphic.treatment !== "measurement") {
      group.appendChild(el("polyline", { class: "route", fill: "none", stroke: tokens.line, "stroke-width": tokens.line_width, "stroke-linecap": "round", "stroke-linejoin": "round" }));
      if (graphic.arrow) group.appendChild(el("polygon", { class: "arrow", fill: tokens.line }));
    }
    if (graphic.treatment === "measurement") {
      group.appendChild(el("line", { class: "bracket", stroke: tokens.line, "stroke-width": tokens.line_width, "stroke-linecap": "round" }));
      group.appendChild(el("line", { class: "tick a", stroke: tokens.line, "stroke-width": tokens.line_width }));
      group.appendChild(el("line", { class: "tick b", stroke: tokens.line, "stroke-width": tokens.line_width }));
    }
    svg.appendChild(group);
    if (graphic.primary || graphic.kicker || graphic.runs || graphic.image || graphic.badge) {
      stage.appendChild(cardFor(graphic, tokens));
    }
  });
  stage.appendChild(svg);
}

function cardFor(graphic, tokens) {
  const card = document.createElement("div");
  card.className = "card";
  card.id = `card_${graphic.id}`;
  const role = graphic.size_role || "body";
  const primarySize = (graphic.placement && graphic.placement.font_px) || tokens[role] || tokens.body;
  card.style.setProperty("--primary", `${primarySize}px`);
  card.style.left = `${graphic.placement.x * plan.width}px`;
  card.style.top = `${graphic.placement.y * plan.height}px`;
  card.style.maxWidth = `${graphic.placement.max_width * plan.width}px`;
  if (graphic.placement.align === "center") {
    card.classList.add("center");
    card.style.left = `${(graphic.placement.x + graphic.placement.width / 2) * plan.width}px`;
  }
  const backing = document.createElement("div");
  backing.className = "backing";
  if (graphic.badge) addText(backing, "badge", graphic.badge);
  if (graphic.kicker) addText(backing, "kicker", graphic.kicker);
  if (graphic.image) {
    const image = document.createElement("img");
    image.className = "inset";
    image.src = `/asset?path=${encodeURIComponent(graphic.image)}`;
    backing.appendChild(image);
  }
  const primary = document.createElement("div");
  primary.className = "primary";
  if (graphic.runs) {
    graphic.runs.forEach((run) => {
      const span = document.createElement("span");
      span.textContent = run.text;
      if (run.emphasis) span.className = "em";
      primary.appendChild(span);
    });
  } else if (graphic.primary) {
    primary.textContent = graphic.primary;
  }
  if (primary.childNodes.length) backing.appendChild(primary);
  if (graphic.secondary) addText(backing, "secondary", graphic.secondary);
  if (graphic.underline) {
    const rule = document.createElement("div");
    rule.className = "rule";
    backing.appendChild(rule);
  }
  card.appendChild(backing);
  return card;
}

function addText(parent, className, text) {
  const node = document.createElement("div");
  node.className = className;
  node.textContent = text;
  parent.appendChild(node);
}

function anchorOf(graphic, seconds) {
  if (graphic.anchor_keyframes) return interpolate(graphic.anchor_keyframes, seconds);
  return graphic.anchor;
}

function draw(seconds) {
  const width = plan.width;
  const height = plan.height;
  plan.graphics.forEach((graphic) => {
    const state = phase(graphic, seconds);
    const group = document.getElementById(`geo_${graphic.id}`);
    const card = document.getElementById(`card_${graphic.id}`);
    if (group) group.setAttribute("opacity", String(state.opacity));
    const appear = state.appear;
    if (card) {
      card.style.opacity = String(state.opacity * appear);
      const rise = graphic.entrance === "scale_settle" ? 0 : (1 - appear) * 10;
      const scale = graphic.entrance === "scale_settle" ? 1 + (1 - appear) * 0.04 : 1;
      const shift = graphic.placement && graphic.placement.align === "center" ? "translateX(-50%) " : "";
      card.style.transform = `${shift}translateY(${rise}px) scale(${scale})`;
      card.style.transformOrigin = shift ? "center center" : "left center";
      const rule = card.querySelector(".rule");
      if (rule) rule.style.transform = `scaleX(${appear})`;
      card.style.clipPath = graphic.entrance === "mask_reveal" ? `inset(0 ${(1 - appear) * 100}% 0 0)` : "none";
    }
    if (graphic.rect && group) {
      const mark = group.querySelector(".mark");
      if (mark) {
        const x = graphic.rect.x * width;
        const y = graphic.rect.y * height;
        const w = graphic.rect.width * width;
        const h = graphic.rect.height * height;
        if (graphic.template === "ring") {
          mark.setAttribute("cx", x + w / 2);
          mark.setAttribute("cy", y + h / 2);
          mark.setAttribute("rx", w / 2);
          mark.setAttribute("ry", h / 2);
        } else {
          mark.setAttribute("x", x);
          mark.setAttribute("y", y);
          mark.setAttribute("width", w);
          mark.setAttribute("height", h);
        }
        const length = mark.getTotalLength ? mark.getTotalLength() : 2 * (w + h);
        mark.setAttribute("stroke-dasharray", length);
        mark.setAttribute("stroke-dashoffset", length * (1 - state.line));
      }
    }
    const anchor = anchorOf(graphic, seconds);
    if (anchor && card && group) {
      const box = card.getBoundingClientRect();
      const host = stage.getBoundingClientRect();
      const midY = box.top - host.top + box.height / 2;
      const centerX = box.left - host.left + box.width / 2;
      const ax = anchor.x * width;
      const ay = anchor.y * height;
      const startX = ax >= centerX ? box.right - host.left : box.left - host.left;
      const elbow = graphic.elbow;
      const points = elbow
        ? `${startX},${midY} ${elbow.x * width},${elbow.y * height} ${ax},${ay}`
        : `${startX},${midY} ${ax},${ay}`;
      const line = group.querySelector(".leader");
      line.setAttribute("points", points);
      const length = line.getTotalLength() || 1;
      line.setAttribute("stroke-dasharray", length);
      line.setAttribute("stroke-dashoffset", length * (1 - state.line));
      const dot = group.querySelector(".dot");
      dot.setAttribute("cx", ax);
      dot.setAttribute("cy", ay);
      dot.setAttribute("opacity", String(state.line));
    }
    if (graphic.points && graphic.treatment !== "measurement" && group) {
      const poly = group.querySelector(".route");
      poly.setAttribute("points", graphic.points.map((point) => `${point.x * width},${point.y * height}`).join(" "));
      const length = poly.getTotalLength() || 1;
      poly.setAttribute("stroke-dasharray", length);
      poly.setAttribute("stroke-dashoffset", length * (1 - state.line));
      if (graphic.arrow) {
        const last = graphic.points[graphic.points.length - 1];
        const prev = graphic.points[graphic.points.length - 2];
        const angle = Math.atan2((last.y - prev.y) * height, (last.x - prev.x) * width);
        const tipX = last.x * width;
        const tipY = last.y * height;
        const head = 14;
        const wing = (delta) => [tipX - Math.cos(angle + delta) * head, tipY - Math.sin(angle + delta) * head];
        const left = wing(0.45);
        const right = wing(-0.45);
        const arrow = group.querySelector(".arrow");
        arrow.setAttribute("points", `${tipX},${tipY} ${left[0]},${left[1]} ${right[0]},${right[1]}`);
        arrow.setAttribute("opacity", state.line > 0.92 ? "1" : "0");
      }
    }
    if (graphic.treatment === "measurement" && group) {
      const [a, b] = graphic.points;
      const x1 = a.x * width;
      const y1 = a.y * height;
      const x2 = b.x * width;
      const y2 = b.y * height;
      const bracket = group.querySelector(".bracket");
      bracket.setAttribute("x1", x1);
      bracket.setAttribute("y1", y1);
      bracket.setAttribute("x2", x1 + (x2 - x1) * state.line);
      bracket.setAttribute("y2", y1 + (y2 - y1) * state.line);
      const angle = Math.atan2(y2 - y1, x2 - x1) + Math.PI / 2;
      const tick = (node, x, y) => {
        node.setAttribute("x1", x - Math.cos(angle) * 8);
        node.setAttribute("y1", y - Math.sin(angle) * 8);
        node.setAttribute("x2", x + Math.cos(angle) * 8);
        node.setAttribute("y2", y + Math.sin(angle) * 8);
      };
      tick(group.querySelector(".tick.a"), x1, y1);
      tick(group.querySelector(".tick.b"), x2, y2);
      group.querySelector(".tick.b").setAttribute("opacity", state.line > 0.95 ? "1" : "0");
    }
  });
}

window.renderAt = (timeMs) => draw(timeMs / 1000);

window.audit = () => {
  const host = stage.getBoundingClientRect();
  for (const card of stage.querySelectorAll(".card")) {
    if (Number(card.style.opacity) < 0.9) continue;
    const box = card.getBoundingClientRect();
    if (box.width < 2 || box.height < 2) return `empty ${card.id}`;
    if (box.left < host.left - 1 || box.top < host.top - 1 || box.right > host.right + 1 || box.bottom > host.bottom + 1) {
      return `clipped ${card.id}`;
    }
  }
  return "";
};

window.ready = (async () => {
  try {
    plan = await (await fetch("/plan.json")).json();
    build();
    if (document.fonts) {
      await document.fonts.load("32px Doc Devanagari");
      await document.fonts.ready;
    }
    await Promise.all([...document.images].map((image) => image.decode().catch(() => {})));
    window.renderAt(0);
    window.sampleReady = true;
  } catch (error) {
    window.sampleError = String(error && error.stack || error);
    throw error;
  }
})();
