import { activeCaption, clamp, ease, routePoint } from "./util.js";

function plane(ctx, x, y, scale = 1) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(0.18);
  ctx.scale(scale, scale);
  ctx.fillStyle = "#f7f0dc";
  ctx.beginPath();
  const pts = [
    [25, 0],
    [-10, -7],
    [-18, -23],
    [-23, -23],
    [-18, -3],
    [-29, -9],
    [-30, -3],
    [-25, 0],
    [-30, 3],
    [-29, 9],
    [-18, 3],
    [-23, 23],
    [-18, 23],
    [-10, 7],
  ];
  pts.forEach((p, i) => (i ? ctx.lineTo(...p) : ctx.moveTo(...p)));
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

function drawText(ctx, text, x, y, {
  font,
  fill = "#ffffff",
  stroke = "rgba(8,16,28,0.85)",
  strokeWidth = 4,
  align = "left",
  baseline = "alphabetic",
  shadow = true,
} = {}) {
  ctx.save();
  ctx.font = font;
  ctx.textAlign = align;
  ctx.textBaseline = baseline;
  if (shadow) {
    ctx.shadowColor = "rgba(0,0,0,0.55)";
    ctx.shadowBlur = Math.max(2, strokeWidth * 1.4);
    ctx.shadowOffsetX = 0;
    ctx.shadowOffsetY = Math.max(1, strokeWidth * 0.35);
  }
  if (strokeWidth > 0) {
    ctx.lineWidth = strokeWidth;
    ctx.strokeStyle = stroke;
    ctx.lineJoin = "round";
    ctx.strokeText(text, x, y);
  }
  ctx.fillStyle = fill;
  ctx.fillText(text, x, y);
  ctx.restore();
}

function labelOpacity(label, t, zoomU) {
  let o = 1;
  if (label.visible_from != null && t < label.visible_from) {
    o *= ease((t - (label.visible_from - 0.35)) / 0.35);
  }
  if (label.visible_until != null && t > label.visible_until - 0.45) {
    o *= 1 - ease((t - (label.visible_until - 0.45)) / 0.45);
  }
  // Slight size/opacity response as the camera closes in.
  o *= clamp(1.05 - zoomU * 0.12);
  return clamp(o);
}

export function drawOverlays(ctx, story, _engine, project, t) {
  const w = story.width;
  const h = story.height;
  const theme = story.theme;
  const s = w / 1920;
  ctx.clearRect(0, 0, w, h);

  // Subtle vignette — do not crush coastal detail.
  const vignette = ctx.createRadialGradient(w / 2, h * 0.48, h * 0.34, w / 2, h * 0.5, w * 0.72);
  vignette.addColorStop(0, "#00000000");
  vignette.addColorStop(1, theme.vignette || "#03091755");
  ctx.fillStyle = vignette;
  ctx.fillRect(0, 0, w, h);

  const g = ctx.createLinearGradient(0, h * 0.78, 0, h);
  g.addColorStop(0, "#08121b00");
  g.addColorStop(1, theme.caption_bg);
  ctx.fillStyle = g;
  ctx.fillRect(0, h * 0.78, w, h * 0.22);

  const top = ctx.createLinearGradient(0, 0, 0, h * 0.16);
  top.addColorStop(0, "#08121b99");
  top.addColorStop(1, "#08121b00");
  ctx.fillStyle = top;
  ctx.fillRect(0, 0, w, h * 0.16);

  drawText(ctx, "SOUTH ASIA  /  दक्षिण एशिया", 48 * s, 40 * s, {
    font: `${Math.round(17 * s)}px "Story Latin", "Story Devanagari", sans-serif`,
    fill: theme.gold,
    strokeWidth: 0,
    shadow: false,
  });
  drawText(ctx, story.disclaimer, 48 * s, 74 * s, {
    font: `${Math.round(24 * s)}px "Story Devanagari", "Devanagari Sangam MN", sans-serif`,
    fill: theme.ink,
    strokeWidth: Math.max(3, 4 * s),
  });

  const caption = activeCaption(story.captions, t);
  if (caption) {
    drawText(ctx, caption, 48 * s, h - 72 * s, {
      font: `${Math.round(36 * s)}px "Story Devanagari", "Devanagari Sangam MN", sans-serif`,
      fill: theme.ink,
      strokeWidth: Math.max(4, 6 * s),
    });
  }

  const camSpan = story.camera.keyframes;
  const zoomU = camSpan.length > 1
    ? clamp((t - camSpan[0].t) / (camSpan[camSpan.length - 1].t - camSpan[0].t))
    : 0;

  for (const label of story.labels) {
    if (label.visible_from != null && t < label.visible_from - 0.35) continue;
    if (label.visible_until != null && t > label.visible_until) continue;
    // Avoid stacking with the final callout label.
    if (
      t >= story.callout.reveal &&
      label.text === story.callout.label
    ) {
      continue;
    }
    const q = project(label.anchor);
    if (!q) continue;
    if (q[0] < 70 * s || q[0] > w - 70 * s || q[1] < 90 * s || q[1] > h - 150 * s) continue;
    const opacity = labelOpacity(label, t, zoomU);
    if (opacity <= 0.02) continue;
    ctx.globalAlpha = opacity;
    const size = (label.size || 40) * (1 + zoomU * 0.08);
    drawText(ctx, label.text, q[0], q[1], {
      font: `${Math.round(size * s)}px "Story Devanagari", "Devanagari Sangam MN", sans-serif`,
      fill: theme.ink,
      strokeWidth: Math.max(4, 6 * s),
      align: "center",
      baseline: "middle",
    });
    ctx.globalAlpha = 1;
  }

  const ac = story.aircraft;
  if (t >= ac.start && t <= ac.end + 0.15) {
    const u = ease((t - ac.start) / (ac.end - ac.start));
    const progress = clamp(u);
    const trail = [];
    const steps = 48;
    for (let i = 0; i <= steps; i += 1) {
      const p = routePoint(ac.route, progress * (i / steps));
      const q = project(p);
      if (q) trail.push(q);
    }
    if (trail.length > 1) {
      ctx.beginPath();
      ctx.strokeStyle = theme.gold;
      ctx.globalAlpha = 0.85;
      ctx.lineWidth = Math.max(1.5, 2 * s);
      ctx.setLineDash([7 * s, 6 * s]);
      trail.forEach((q, i) => (i ? ctx.lineTo(...q) : ctx.moveTo(...q)));
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
    }
    const tip = project(routePoint(ac.route, progress));
    if (tip) {
      plane(ctx, tip[0], tip[1], 0.92 * s);
      const ox = ac.formation_offset_px[0] * s;
      const oy = ac.formation_offset_px[1] * s;
      plane(ctx, tip[0] + ox, tip[1] + oy, 0.82 * s);
    }
  }

  if (t >= story.callout.reveal) {
    for (const impact of story.impacts) {
      const age = t - impact.t;
      if (age < 0) continue;
      const q = project(impact.anchor);
      if (!q) continue;
      const cycle = (age % 1.35) / 1.35;
      const r = (9 + cycle * 36) * s;
      ctx.globalAlpha = 0.85 * (1 - cycle);
      ctx.strokeStyle = theme.pulse;
      ctx.lineWidth = Math.max(2, 2.5 * s);
      ctx.beginPath();
      ctx.arc(q[0], q[1], r, 0, Math.PI * 2);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    const reveal = ease((t - story.callout.reveal) / 0.7);
    const anchor = project(story.callout.anchor);
    if (anchor && reveal > 0) {
      const sx = story.callout.screen[0] * w;
      const sy = story.callout.screen[1] * h;
      const cx = (sx + anchor[0]) / 2;
      const cy = Math.min(sy, anchor[1]) - 70 * s;
      const pts = [];
      for (let i = 0; i <= 60; i += 1) {
        const v = reveal * (i / 60);
        const inv = 1 - v;
        pts.push([
          inv * inv * sx + 2 * inv * v * cx + v * v * anchor[0],
          inv * inv * sy + 2 * inv * v * cy + v * v * anchor[1],
        ]);
      }
      ctx.beginPath();
      ctx.strokeStyle = theme.gold;
      ctx.lineWidth = Math.max(2, 2.4 * s);
      pts.forEach((p, i) => (i ? ctx.lineTo(...p) : ctx.moveTo(...p)));
      ctx.stroke();
      if (reveal > 0.95) {
        const a = Math.atan2(
          anchor[1] - pts[pts.length - 2][1],
          anchor[0] - pts[pts.length - 2][0],
        );
        const len = 17 * s;
        ctx.fillStyle = theme.gold;
        ctx.beginPath();
        ctx.moveTo(...anchor);
        ctx.lineTo(anchor[0] - len * Math.cos(a - 0.4), anchor[1] - len * Math.sin(a - 0.4));
        ctx.lineTo(anchor[0] - len * Math.cos(a + 0.4), anchor[1] - len * Math.sin(a + 0.4));
        ctx.closePath();
        ctx.fill();
      }
      drawText(ctx, story.callout.label, sx, sy - 14 * s, {
        font: `${Math.round(34 * s)}px "Story Devanagari", "Devanagari Sangam MN", sans-serif`,
        fill: theme.ink,
        strokeWidth: Math.max(4, 5 * s),
        align: "left",
      });
    }
  }

  drawText(ctx, story.attribution, 48 * s, h - 26 * s, {
    font: `${Math.round(12 * s)}px "Story Latin", Arial, sans-serif`,
    fill: theme.muted,
    strokeWidth: 0,
    shadow: false,
  });
}
