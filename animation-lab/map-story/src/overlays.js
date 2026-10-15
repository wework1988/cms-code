import { pinBounds, pinMetrics, tracePin } from "./pin.js";
import { clamp, documentaryPresentation, ease } from "./util.js";

function drawText(ctx, text, x, y, {
  font,
  fill = "#ffffff",
  stroke = "rgba(8,16,28,0.85)",
  strokeWidth = 4,
  align = "left",
  baseline = "alphabetic",
  shadow = true,
  shadowColor = "rgba(0,0,0,0.55)",
  shadowBlur = null,
  shadowOffsetX = 0,
  shadowOffsetY = null,
  letterSpacing = "0px",
} = {}) {
  ctx.save();
  ctx.font = font;
  ctx.textAlign = align;
  ctx.textBaseline = baseline;
  ctx.letterSpacing = letterSpacing;
  if (shadow) {
    ctx.shadowColor = shadowColor;
    ctx.shadowBlur = shadowBlur == null ? Math.max(2, strokeWidth * 1.4) : shadowBlur;
    ctx.shadowOffsetX = shadowOffsetX;
    ctx.shadowOffsetY = shadowOffsetY == null ? Math.max(1, strokeWidth * 0.35) : shadowOffsetY;
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

function hasDevanagari(text) {
  return /[\u0900-\u097F]/.test(text || "");
}

function overlaps(a, b) {
  return !(
    a.x + a.w <= b.x
    || b.x + b.w <= a.x
    || a.y + a.h <= b.y
    || b.y + b.h <= a.y
  );
}

function wrapTextLines(ctx, text, maxWidth, maxLines = 3) {
  const words = String(text || "").trim().split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const lines = [];
  let current = words[0];
  for (let i = 1; i < words.length; i += 1) {
    const attempt = `${current} ${words[i]}`;
    if (ctx.measureText(attempt).width <= maxWidth || current.length <= 1) {
      current = attempt;
      continue;
    }
    lines.push(current);
    current = words[i];
    if (lines.length >= maxLines - 1) break;
  }
  if (lines.length < maxLines) {
    const start = lines.join(" ").split(/\s+/).filter(Boolean).length;
    const rest = words.slice(start).join(" ").trim();
    if (rest) lines.push(rest);
  }
  return lines.slice(0, maxLines);
}

function currentStage(plan, t) {
  const stages = plan.composition?.stages || [];
  return stages.find((stage) => t >= stage.interval?.[0] && t <= stage.interval?.[1] + 0.001) || null;
}

function stageLabelSpec(stage, label) {
  if (!stage?.labels?.length) return null;
  return stage.labels.find((item) => item.place === label.place && item.text === label.text) || null;
}

function candidateCenters(anchor, box, placement) {
  const [ax, ay] = anchor;
  const right = [ax + box.w * 0.6 + 24, ay];
  const left = [ax - box.w * 0.6 - 24, ay];
  const top = [ax, ay - box.h * 0.8 - 16];
  const bottom = [ax, ay + box.h * 0.8 + 16];
  const internal = [ax, ay];
  const order = {
    internal_center: [internal, top, right, left, bottom],
    external_right: [right, top, bottom, left, internal],
    external_left: [left, top, bottom, right, internal],
    external_bottom: [bottom, right, left, top, internal],
    external_top: [top, right, left, bottom, internal],
  };
  return order[placement] || [top, right, left, bottom, internal];
}

function brushBanner(ctx, x, y, w, h) {
  const top = y + h * 0.22;
  const bot = y + h * 0.78;
  const mid = y + h * 0.5;
  const bodyL = x + w * 0.16;
  const bodyR = x + w * 0.84;
  ctx.beginPath();
  ctx.moveTo(bodyL, top);
  ctx.lineTo(bodyR, top + h * 0.02);
  ctx.lineTo(x + w * 0.9, top + h * 0.01);
  ctx.lineTo(x + w * 0.95, top + h * 0.1);
  ctx.lineTo(x + w * 0.985, mid - h * 0.06);
  ctx.lineTo(x + w * 0.94, mid + h * 0.02);
  ctx.lineTo(x + w * 0.975, mid + h * 0.1);
  ctx.lineTo(x + w * 0.9, bot - h * 0.06);
  ctx.lineTo(bodyR, bot);
  ctx.lineTo(bodyL, bot + h * 0.01);
  ctx.lineTo(x + w * 0.1, bot - h * 0.02);
  ctx.lineTo(x + w * 0.045, mid + h * 0.08);
  ctx.lineTo(x + w * 0.09, mid);
  ctx.lineTo(x + w * 0.03, mid - h * 0.07);
  ctx.lineTo(x + w * 0.11, top + h * 0.08);
  ctx.closePath();
}

function drawDateBanner(ctx, plan, t, s) {
  const banner = plan.date_banner;
  if (!banner?.text) return;
  const theme = plan.theme?.date_banner || {};
  const from = banner.from ?? 0;
  const until = banner.until ?? plan.duration ?? 999;
  if (t < from || t > until) return;
  const enter = ease(clamp((t - from) / 0.45));
  const exit = t > until - 0.45 ? 1 - ease((t - (until - 0.45)) / 0.45) : 1;
  const alpha = enter * exit;
  if (alpha <= 0.02) return;
  const w = plan.width;
  const h = plan.height;
  const size = Math.round((banner.text_size || theme.text_size || 92) * s);
  const font = `${size}px "${theme.font || "Story Condensed"}", "Arial Narrow", sans-serif`;
  ctx.save();
  ctx.font = font;
  ctx.letterSpacing = "0.04em";
  const text = String(banner.text).toUpperCase();
  const textWidth = ctx.measureText(text).width;
  const bh = (banner.height || theme.height || 146) * s;
  const bw = Math.min(w * 0.86, Math.max(textWidth + 160 * s, 520 * s));
  const x = (w - bw) / 2;
  const y = h - bh - 42 * s;
  ctx.globalAlpha = alpha;
  ctx.translate(w / 2, y + bh / 2);
  ctx.scale(0.35 + 0.65 * enter, 1);
  ctx.translate(-w / 2, -(y + bh / 2));
  ctx.fillStyle = theme.fill || "#17160F";
  brushBanner(ctx, x, y, bw, bh);
  ctx.fill();
  drawText(ctx, text, w / 2, y + bh * 0.54, {
    font,
    fill: theme.text || "#FFFDF5",
    strokeWidth: 0,
    align: "center",
    baseline: "middle",
    shadowColor: "rgba(0,0,0,0.55)",
    shadowBlur: 2 * s,
    shadowOffsetY: 2 * s,
    letterSpacing: "0.04em",
  });
  ctx.restore();
  if (banner.demo) {
    ctx.save();
    ctx.globalAlpha = alpha;
    drawText(ctx, "STYLE DEMONSTRATION — NOT A STORY DATE", w / 2, y - 18 * s, {
      font: `${Math.round(22 * s)}px "Story Condensed", sans-serif`,
      fill: "#FFFDF5",
      strokeWidth: 0,
      align: "center",
      baseline: "bottom",
      shadowColor: "rgba(0,0,0,0.8)",
      shadowBlur: 6 * s,
      shadowOffsetY: 2 * s,
      letterSpacing: "0.08em",
    });
    ctx.restore();
  }
}

function drawLayeredMarker(ctx, x, y, color, size, alpha, bloom) {
  ctx.save();
  ctx.globalAlpha = alpha * 0.55;
  ctx.fillStyle = color;
  ctx.shadowColor = color;
  ctx.shadowBlur = size * 2.4;
  ctx.beginPath();
  ctx.arc(x, y, size * bloom * 1.55, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = size * 0.8;
  ctx.globalAlpha = alpha * 0.9;
  ctx.beginPath();
  ctx.arc(x, y, size * 0.85, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.globalAlpha = alpha;
  ctx.fillStyle = "#FFFDF5";
  ctx.beginPath();
  ctx.arc(x, y, Math.max(2.2, size * 0.34), 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawPin(ctx, x, y, spec, scale, alpha) {
  const height = Math.max(28, Math.min(72, spec.height || 54)) * scale;
  const metrics = pinMetrics(height);
  ctx.save();
  ctx.translate(x, y);
  ctx.globalAlpha = alpha;
  const shadow = spec.shadow || "#00000055";
  ctx.save();
  ctx.translate(1.5 * scale, 2.5 * scale);
  ctx.fillStyle = shadow;
  ctx.globalAlpha = alpha * (spec.shadow_strength ?? 0.4);
  tracePin(ctx, height);
  ctx.fill();
  ctx.restore();
  ctx.fillStyle = spec.fill || "#E60023";
  tracePin(ctx, height);
  ctx.fill();
  const hole = spec.hole || "transparent";
  if (hole === "transparent") {
    ctx.globalCompositeOperation = "destination-out";
    ctx.globalAlpha = 1;
    ctx.beginPath();
    ctx.arc(0, metrics.centerY, metrics.holeRadius, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalCompositeOperation = "source-over";
  }
  else {
    ctx.fillStyle = spec.hole_color || spec.holeColor || "#FFFFFF";
    ctx.beginPath();
    ctx.arc(0, metrics.centerY, metrics.holeRadius, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = spec.outline || "#FFFFFF";
  ctx.lineWidth = Math.max(1, (spec.outline_width || 2.25) * scale);
  tracePin(ctx, height);
  ctx.stroke();
  ctx.restore();
  return pinBounds(height);
}

function labelOpacity(label, t, duration) {
  let o = 1;
  if (label.visible_from != null && t < label.visible_from) {
    o *= ease((t - (label.visible_from - 0.35)) / 0.35);
  }
  const holdThroughEnd = duration != null && label.visible_until != null && label.visible_until >= duration - 0.05;
  if (label.focus_until != null && label.rest_opacity != null && t > label.focus_until) {
    const u = ease(clamp((t - label.focus_until) / 0.55));
    o *= (1 - u) + label.rest_opacity * u;
  } else if (!holdThroughEnd && label.visible_until != null && t > label.visible_until - 0.4) {
    o *= 1 - ease((t - (label.visible_until - 0.4)) / 0.4);
  }
  return clamp(o);
}

export function drawOverlays(ctx, plan, _engine, project, t) {
  const w = plan.width;
  const h = plan.height;
  const theme = plan.theme;
  const s = w / 1920;
  ctx.clearRect(0, 0, w, h);

  const documentary = documentaryPresentation(theme);
  const stage = currentStage(plan, t);
  const occupied = [];
  if (!documentary) {
    const vignette = ctx.createRadialGradient(w / 2, h * 0.48, h * 0.36, w / 2, h * 0.5, w * 0.72);
    vignette.addColorStop(0, "#00000000");
    vignette.addColorStop(1, theme.vignette || "#03091740");
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, w, h);
  }

  for (const marker of plan.markers || []) {
    if (t < marker.from || t > marker.to) continue;
    const point = project(marker.anchor);
    if (!point) continue;
    if (documentary) {
      const arrival = theme.marker?.arrival_seconds ?? 0;
      const age = t - marker.from;
      let alpha = 1;
      let bloom = 1;
      if (!marker.pulse && arrival > 0 && age < arrival) {
        const u = ease(clamp(age / arrival));
        alpha = u;
        bloom = 1.4 - 0.4 * u;
      }
      const shape = theme.marker?.shape || theme.capabilities?.marker_shape || "glow_dot";
      if (shape === "ring") {
        const radius = Math.max(10, (theme.marker?.height || 36) * 0.34) * s * bloom;
        const hole = Math.max(4, radius * 0.46);
        ctx.save();
        ctx.translate(point[0], point[1]);
        ctx.globalAlpha = alpha;
        ctx.fillStyle = marker.color || theme.marker?.fill || "#E60023";
        ctx.beginPath();
        ctx.arc(0, 0, radius, 0, Math.PI * 2);
        ctx.arc(0, 0, hole, 0, Math.PI * 2, true);
        ctx.fill("evenodd");
        ctx.strokeStyle = theme.marker?.outline || "#FFFFFF";
        ctx.lineWidth = Math.max(1, (theme.marker?.outline_width || 2.25) * s);
        ctx.beginPath();
        ctx.arc(0, 0, radius, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
        occupied.push({
          x: point[0] - radius,
          y: point[1] - radius,
          w: radius * 2,
          h: radius * 2,
        });
      }
      else if (shape === "pin") {
        const pinScale = marker.pulse ? 1 + 0.04 * Math.sin(t * 5) : bloom;
        ctx.save();
        ctx.translate(point[0], point[1]);
        ctx.scale(pinScale, pinScale);
        const bounds = drawPin(ctx, 0, 0, {
          ...theme.marker,
          fill: marker.color || theme.marker?.fill || "#E60023",
        }, s, alpha);
        ctx.restore();
        occupied.push({
          x: point[0] + bounds.x * pinScale,
          y: point[1] + bounds.y * pinScale,
          w: bounds.w * pinScale,
          h: bounds.h * pinScale,
        });
      }
      else {
        const radius = (marker.size || 8) * s * (marker.pulse ? 1 + 0.08 * Math.sin(t * 5) : 1);
        drawLayeredMarker(ctx, point[0], point[1], marker.color || theme.palette?.marker_yellow || "#FFF400", radius, alpha, bloom);
      }
      continue;
    }
    const pulse = marker.pulse ? 1 + 0.08 * Math.sin(t * 5) : 1;
    const radius = (marker.size || 11) * s * pulse;
    ctx.beginPath();
    ctx.arc(point[0], point[1], radius + 3 * s, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(255,248,236,0.92)";
    ctx.fill();
    ctx.beginPath();
    ctx.arc(point[0], point[1], radius, 0, Math.PI * 2);
    ctx.fillStyle = marker.color || "#E6D545";
    ctx.fill();
  }

  for (const label of plan.labels || []) {
    if (label.visible_from != null && t < label.visible_from - 0.35) continue;
    if (label.visible_until != null && t > label.visible_until) continue;
    if (plan.callout && t >= plan.callout.reveal && label.text === plan.callout.text) continue;
    const q = project(label.anchor);
    if (!q) continue;
    if (q[0] < 60 * s || q[0] > w - 60 * s || q[1] < 80 * s || q[1] > h - 120 * s) continue;
    const opacity = labelOpacity(label, t, plan.duration);
    if (opacity <= 0.02) continue;
    const y = q[1] + (label.offset_y || 0) * s;
    ctx.globalAlpha = opacity;
    if (documentary) {
      const labelTheme = theme.label || {};
      const stageSpec = stageLabelSpec(stage, label);
      const devanagari = hasDevanagari(label.text);
      const family = devanagari
        ? (labelTheme.font_devanagari || "Story Devanagari Bold")
        : (labelTheme.font_latin || "Story Condensed");
      let text = label.text;
      if (!devanagari && labelTheme.uppercase_latin) text = String(text).toUpperCase();
      const minSize = Math.round((labelTheme.min_size || 28) * s);
      const maxSize = Math.round((labelTheme.max_size || 96) * s);
      let size = Math.round(((stageSpec?.font_size || label.size || 48) * s));
      size = Math.max(minSize, Math.min(maxSize, size));
      const fontOf = (px) => `${px}px "${family}", sans-serif`;
      ctx.font = fontOf(size);
      ctx.letterSpacing = devanagari ? "0px" : "0.03em";
      while (size > minSize && ctx.measureText(text).width > w * 0.72) {
        size -= 2;
        ctx.font = fontOf(size);
      }
      const maxWidth = Math.min(w * 0.72, Math.max(200 * s, w * 0.36));
      const lines = wrapTextLines(ctx, text, maxWidth, 3);
      const lineHeight = size * 1.2;
      const lineWidths = lines.map((line) => ctx.measureText(line).width);
      const textWidth = lineWidths.length ? Math.max(...lineWidths) : ctx.measureText(text).width;
      const textHeight = Math.max(lineHeight, lines.length * lineHeight);
      const placement = stageSpec?.placement || "internal_center";
      const centers = candidateCenters([q[0], y], { w: textWidth, h: textHeight }, placement);
      const safePad = 36 * s;
      let chosen = null;
      for (const center of centers) {
        const box = {
          x: center[0] - textWidth / 2,
          y: center[1] - textHeight / 2,
          w: textWidth,
          h: textHeight,
        };
        const inside = (
          box.x >= safePad
          && box.y >= safePad
          && box.x + box.w <= w - safePad
          && box.y + box.h <= h - safePad
        );
        if (!inside) continue;
        if (occupied.some((other) => overlaps(other, box))) continue;
        chosen = { center, box };
        break;
      }
      if (!chosen) continue;
      occupied.push(chosen.box);
      const startY = chosen.center[1] - ((lines.length - 1) * lineHeight) / 2;
      for (let i = 0; i < lines.length; i += 1) {
        drawText(ctx, lines[i], chosen.center[0], startY + i * lineHeight, {
          font: fontOf(size),
          fill: labelTheme.color || theme.ink,
          stroke: "rgba(0,0,0,0.55)",
          strokeWidth: (labelTheme.stroke_width ?? 1.2) * s,
          align: "center",
          baseline: "middle",
          shadowColor: labelTheme.shadow || "rgba(0,0,0,0.82)",
          shadowBlur: (labelTheme.shadow_blur ?? 9) * s,
          shadowOffsetY: (labelTheme.shadow_offset_y ?? 5) * s,
          letterSpacing: devanagari ? "0px" : "0.03em",
        });
      }
    } else {
      drawText(ctx, label.text, q[0], q[1], {
        font: `${Math.round((label.size || 48) * s)}px "Story Devanagari", "Devanagari Sangam MN", sans-serif`,
        fill: theme.ink,
        strokeWidth: Math.max(4, 6 * s),
        align: "center",
        baseline: "middle",
      });
    }
    ctx.globalAlpha = 1;
  }

  if (documentary) drawDateBanner(ctx, plan, t, s);

  if (plan.callout && t >= plan.callout.reveal) {
    const reveal = ease((t - plan.callout.reveal) / 0.65);
    const anchor = project(plan.callout.anchor);
    if (anchor && reveal > 0) {
      const sx = plan.callout.screen[0] * w;
      const sy = plan.callout.screen[1] * h;
      const boxW = 220 * s;
      const boxH = 72 * s;
      const boxX = sx - boxW / 2;
      const boxY = sy - boxH / 2;

      ctx.globalAlpha = reveal;
      ctx.fillStyle = theme.callout_box || "rgba(18,28,48,0.92)";
      ctx.strokeStyle = theme.callout_border || theme.gold;
      ctx.lineWidth = Math.max(1.5, 2 * s);
      const r = 10 * s;
      ctx.beginPath();
      ctx.moveTo(boxX + r, boxY);
      ctx.arcTo(boxX + boxW, boxY, boxX + boxW, boxY + boxH, r);
      ctx.arcTo(boxX + boxW, boxY + boxH, boxX, boxY + boxH, r);
      ctx.arcTo(boxX, boxY + boxH, boxX, boxY, r);
      ctx.arcTo(boxX, boxY, boxX + boxW, boxY, r);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      drawText(ctx, plan.callout.text, sx, sy + 2 * s, {
        font: `${Math.round(40 * s)}px "Story Devanagari", "Devanagari Sangam MN", sans-serif`,
        fill: theme.callout_text || theme.ink,
        strokeWidth: Math.max(3, 4 * s),
        align: "center",
        baseline: "middle",
      });

      const showArrow = plan.callout.presentation !== "label_only";
      const startX = sx < anchor[0] ? boxX + boxW : boxX;
      const startY = sy;
      const cx = (startX + anchor[0]) / 2;
      const cy = Math.min(startY, anchor[1]) - 50 * s;
      const pts = [];
      if (showArrow) {
      for (let i = 0; i <= 56; i += 1) {
        const v = reveal * (i / 56);
        const inv = 1 - v;
        pts.push([
          inv * inv * startX + 2 * inv * v * cx + v * v * anchor[0],
          inv * inv * startY + 2 * inv * v * cy + v * v * anchor[1],
        ]);
      }
      ctx.beginPath();
      ctx.strokeStyle = theme.gold;
      ctx.lineWidth = Math.max(2, 2.4 * s);
      pts.forEach((p, i) => (i ? ctx.lineTo(...p) : ctx.moveTo(...p)));
      ctx.stroke();
      if (reveal > 0.92) {
        const a = Math.atan2(
          anchor[1] - pts[pts.length - 2][1],
          anchor[0] - pts[pts.length - 2][0],
        );
        const len = 16 * s;
        ctx.fillStyle = theme.gold;
        ctx.beginPath();
        ctx.moveTo(...anchor);
        ctx.lineTo(anchor[0] - len * Math.cos(a - 0.4), anchor[1] - len * Math.sin(a - 0.4));
        ctx.lineTo(anchor[0] - len * Math.cos(a + 0.4), anchor[1] - len * Math.sin(a + 0.4));
        ctx.closePath();
        ctx.fill();
      }
      }
      ctx.globalAlpha = 1;
    }
  }

  drawText(ctx, plan.attribution || "", 40 * s, h - 24 * s, {
    font: `${Math.round(11 * s)}px "Story Latin", Arial, sans-serif`,
    fill: theme.muted,
    strokeWidth: 0,
    shadow: false,
  });

  if (window.__mapDebugOverlay && stage?.labels?.length) {
    ctx.save();
    ctx.globalAlpha = 0.9;
    ctx.strokeStyle = "rgba(120,255,220,0.7)";
    ctx.setLineDash([8, 6]);
    const safe = plan.composition?.safe_area;
    if (safe) {
      ctx.strokeRect(safe.left, safe.top, safe.right - safe.left, safe.bottom - safe.top);
    }
    ctx.setLineDash([]);
    ctx.strokeStyle = "rgba(255,180,0,0.75)";
    for (const item of stage.labels) {
      const box = item.box;
      if (!box) continue;
      ctx.strokeRect(box.x, box.y, box.w, box.h);
      ctx.beginPath();
      ctx.arc(item.anchor[0], item.anchor[1], 4, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();
  }
}
