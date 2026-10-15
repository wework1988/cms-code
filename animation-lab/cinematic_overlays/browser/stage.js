const stage = document.querySelector("#stage");
let plan = null;

function smooth(value) {
  const clamped = Math.max(0, Math.min(1, value));
  return clamped * clamped * (3 - 2 * clamped);
}

function anchorAt(overlay, seconds) {
  if (overlay.anchor_mode === "manual_keyframes") {
    const keys = overlay.anchor_keyframes;
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
  }
  return overlay.anchor;
}

function phase(overlay, seconds) {
  const start = overlay.start_time;
  const reveal = overlay.reveal_duration;
  const fade = overlay.type === "location_callout" ? (overlay.label_fade_duration || 0) : 0;
  const holdEnd = start + reveal + fade + overlay.hold_duration;
  const end = holdEnd + overlay.exit_duration;
  if (seconds < start || seconds >= end) return { line: 0, label: 0, opacity: 0 };
  if (seconds < start + reveal) {
    return { line: smooth((seconds - start) / reveal), label: 0, opacity: 1 };
  }
  if (fade > 0 && seconds < start + reveal + fade) {
    return { line: 1, label: smooth((seconds - start - reveal) / fade), opacity: 1 };
  }
  if (seconds < holdEnd) return { line: 1, label: 1, opacity: 1 };
  return { line: 1, label: 1, opacity: 1 - smooth((seconds - holdEnd) / overlay.exit_duration) };
}

function build() {
  const width = plan.width;
  const height = plan.height;
  document.documentElement.style.width = `${width}px`;
  document.documentElement.style.height = `${height}px`;
  const face = document.createElement("style");
  face.textContent = `
    @font-face {
      font-family: "Doc Devanagari";
      src: url("/fonts/NotoSansDevanagari-Regular.woff2") format("woff2");
      font-display: block;
    }
    @font-face {
      font-family: "Doc Latin";
      src: url("/fonts/NotoSans-Regular.woff2") format("woff2");
      font-display: block;
    }
  `;
  document.head.appendChild(face);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", width);
  svg.setAttribute("height", height);
  plan.overlays.forEach((overlay, index) => {
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.id = `ov_${index}`;
    group.setAttribute("opacity", "0");
    if (overlay.type === "location_callout") {
      group.innerHTML = `
        <line class="leader" stroke="${plan.style.line}" stroke-width="2" fill="none" />
        <circle class="dot" r="5" fill="${plan.style.ink}" />
        <rect class="back" rx="6" fill="${plan.style.backing}" />
        <text class="copy" fill="${plan.style.ink}" font-size="34"></text>
      `;
    } else if (overlay.type === "detail_highlight") {
      group.innerHTML = `<rect class="box" fill="none" stroke="${plan.style.line}" stroke-width="2" />`;
    } else if (overlay.type === "date_label") {
      group.innerHTML = `
        <rect class="back" rx="6" fill="${plan.style.backing}" />
        <text class="copy" fill="${plan.style.ink}" font-size="40"></text>
      `;
    } else if (overlay.type === "route_line") {
      group.innerHTML = `<polyline class="route" fill="none" stroke="${plan.style.line}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" />`;
    }
    svg.appendChild(group);
  });
  stage.replaceChildren(svg);
}

function placeText(group, overlay, width, height) {
  const text = group.querySelector(".copy");
  const back = group.querySelector(".back");
  text.textContent = overlay.text;
  const x = overlay.label.x * width;
  const y = overlay.label.y * height;
  text.setAttribute("x", x);
  text.setAttribute("y", y);
  const box = text.getBBox();
  const padX = 16;
  const padY = 10;
  back.setAttribute("x", box.x - padX);
  back.setAttribute("y", box.y - padY);
  back.setAttribute("width", box.width + padX * 2);
  back.setAttribute("height", box.height + padY * 2);
  return box;
}

function draw(seconds) {
  const width = plan.width;
  const height = plan.height;
  plan.overlays.forEach((overlay, index) => {
    const group = document.getElementById(`ov_${index}`);
    const state = phase(overlay, seconds);
    group.setAttribute("opacity", String(state.opacity));
    if (overlay.type === "location_callout") {
      const box = placeText(group, overlay, width, height);
      const anchor = anchorAt(overlay, seconds);
      const x1 = box.x + box.width + 16;
      const y1 = box.y + box.height / 2;
      const x2 = anchor.x * width;
      const y2 = anchor.y * height;
      const line = group.querySelector(".leader");
      const length = Math.hypot(x2 - x1, y2 - y1) || 1;
      line.setAttribute("x1", x1);
      line.setAttribute("y1", y1);
      line.setAttribute("x2", x2);
      line.setAttribute("y2", y2);
      line.setAttribute("stroke-dasharray", String(length));
      line.setAttribute("stroke-dashoffset", String(length * (1 - state.line)));
      const dot = group.querySelector(".dot");
      dot.setAttribute("cx", x2);
      dot.setAttribute("cy", y2);
      dot.setAttribute("opacity", String(state.line));
      group.querySelector(".copy").setAttribute("opacity", String(state.label));
      group.querySelector(".back").setAttribute("opacity", String(state.label));
    } else if (overlay.type === "detail_highlight") {
      const rect = overlay.rect;
      const box = group.querySelector(".box");
      const x = rect.x * width;
      const y = rect.y * height;
      const w = rect.width * width;
      const h = rect.height * height;
      const length = 2 * (w + h);
      box.setAttribute("x", x);
      box.setAttribute("y", y);
      box.setAttribute("width", w);
      box.setAttribute("height", h);
      box.setAttribute("stroke-dasharray", String(length));
      box.setAttribute("stroke-dashoffset", String(length * (1 - state.line)));
    } else if (overlay.type === "date_label") {
      placeText(group, overlay, width, height);
      const fade = overlay.type === "date_label" ? state.line : state.label;
      group.querySelector(".copy").setAttribute("opacity", String(fade));
      group.querySelector(".back").setAttribute("opacity", String(fade));
    } else if (overlay.type === "route_line") {
      const poly = group.querySelector(".route");
      const points = overlay.points.map((point) => `${point.x * width},${point.y * height}`).join(" ");
      poly.setAttribute("points", points);
      const length = poly.getTotalLength();
      poly.setAttribute("stroke-dasharray", String(length));
      poly.setAttribute("stroke-dashoffset", String(length * (1 - state.line)));
    }
  });
}

window.renderAt = (timeMs) => {
  draw(timeMs / 1000);
};

window.ready = (async () => {
  try {
    plan = await (await fetch("/plan.json")).json();
    build();
    if (document.fonts) {
      await document.fonts.load("34px Doc Devanagari");
      await document.fonts.ready;
    }
    window.renderAt(0);
    window.sampleReady = true;
  } catch (error) {
    window.sampleError = String(error && error.stack || error);
    throw error;
  }
})();
