import { documentaryPresentation, highlightOpacity } from "./util.js";

function geometryOf(featureData) {
  if (!featureData) return null;
  if (featureData.type === "FeatureCollection") return featureData;
  if (featureData.type === "Feature") return featureData;
  return null;
}

function eachPolygon(geometry, visit) {
  if (!geometry) return;
  if (geometry.type === "FeatureCollection") {
    for (const feature of geometry.features || []) eachPolygon(feature, visit);
    return;
  }
  if (geometry.type === "Feature") {
    eachPolygon(geometry.geometry, visit);
    return;
  }
  if (geometry.type === "Polygon") visit(geometry.coordinates);
  else if (geometry.type === "MultiPolygon") {
    for (const polygon of geometry.coordinates) visit(polygon);
  }
}

function traceRing(ctx, ring, project) {
  if (!ring?.length) return false;
  let moved = false;
  for (const coord of ring) {
    const point = project(coord);
    if (!point) continue;
    if (!moved) {
      ctx.moveTo(point[0], point[1]);
      moved = true;
    } else {
      ctx.lineTo(point[0], point[1]);
    }
  }
  if (moved) ctx.closePath();
  return moved;
}

function activeHighlights(plan, t) {
  const byPlace = new Map();
  for (const hl of plan.highlights || []) {
    const opacity = highlightOpacity(hl, t, plan.duration);
    if (opacity <= 0) continue;
    const prev = byPlace.get(hl.place);
    if (!prev || opacity >= prev.opacity || (hl.role === "primary" && prev.role !== "primary")) {
      byPlace.set(hl.place, { ...hl, opacity });
    }
  }
  return [...byPlace.values()].sort((a, b) => {
    const rank = (hl) => (hl.border_strength === "country" || hl.role === "context" ? 0 : 1);
    return rank(a) - rank(b);
  });
}

function paintPolygon(ctx, geometry, project) {
  ctx.beginPath();
  eachPolygon(geometry, (rings) => {
    for (const ring of rings) traceRing(ctx, ring, project);
  });
}

function darken(hex, amount) {
  const h = hex.replace("#", "");
  const n = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  const mixed = n.map((c) => Math.round(c * (1 - amount)));
  return `rgb(${mixed[0]},${mixed[1]},${mixed[2]})`;
}

function paintHighlights(ctx, highlights, featureData, project, alphaFor, colorFor) {
  for (const hl of highlights) {
    const geometry = geometryOf(featureData[hl.place]);
    if (!geometry) continue;
    ctx.save();
    ctx.globalCompositeOperation = "destination-out";
    ctx.globalAlpha = 1;
    paintPolygon(ctx, geometry, project);
    ctx.fill("evenodd");
    ctx.globalCompositeOperation = "source-over";
    ctx.globalAlpha = Math.max(0, Math.min(1, alphaFor(hl)));
    ctx.fillStyle = colorFor(hl);
    paintPolygon(ctx, geometry, project);
    ctx.fill("evenodd");
    ctx.restore();
  }
}

export function drawMapGrade(canvases, plan, featureData, project, t) {
  const { tint, hue, vignette, glow } = canvases;
  const w = plan.width;
  const h = plan.height;
  const theme = plan.theme || {};
  const documentary = documentaryPresentation(theme);
  for (const canvas of [tint, hue, vignette, glow]) {
    if (!canvas) continue;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, w, h);
  }
  if (!documentary) return;

  const highlights = activeHighlights(plan, t);
  const glowEnabled = theme.capabilities?.border_glow !== false;
  if (theme.fill?.mode === "solid") {
    tint.style.mixBlendMode = "normal";
    paintHighlights(
      tint.getContext("2d"),
      highlights,
      featureData,
      project,
      (hl) => hl.opacity,
      (hl) => hl.color,
    );
  }
  else if (theme.fill?.mode === "terrain_color") {
    const multiplyScale = theme.fill.opacity_scale ?? 1;
    const hueAlpha = theme.fill.hue_opacity ?? 0.56;
    tint.style.mixBlendMode = theme.fill.blend || "multiply";
    paintHighlights(
      tint.getContext("2d"),
      highlights,
      featureData,
      project,
      (hl) => hl.opacity * multiplyScale,
      (hl) => (hl.border_strength === "country" ? (theme.palette?.country_red_deep || darken(hl.color, 0.45)) : darken(hl.color, 0.4)),
    );
    if (hue && theme.fill.hue_blend) {
      hue.style.mixBlendMode = theme.fill.hue_blend;
      paintHighlights(
        hue.getContext("2d"),
        highlights,
        featureData,
        project,
        (hl) => hueAlpha * (hl.fill_opacity ? Math.min(1, hl.opacity / hl.fill_opacity) : 1),
        (hl) => hl.color,
      );
    }
  } else if (tint) {
    tint.style.mixBlendMode = "normal";
  }

  if (theme.capabilities?.vignette !== "none") {
    const vignetteCtx = vignette.getContext("2d");
    const wash = vignetteCtx.createRadialGradient(w / 2, h * 0.46, h * 0.34, w / 2, h * 0.5, w * 0.72);
    wash.addColorStop(0, theme.vignette_inner || "#00000000");
    wash.addColorStop(1, theme.vignette || "#08283166");
    vignetteCtx.fillStyle = wash;
    vignetteCtx.fillRect(0, 0, w, h);
  }

  const glowCtx = glow.getContext("2d");
  const spec = theme.boundary || {};
  const scale = w / 1920;
  for (const hl of highlights) {
    if (hl.border === false) continue;
    const geometry = geometryOf(featureData[hl.place]);
    if (!geometry) continue;
    const country = hl.border_strength === "country";
    const core = (country ? spec.country_core : spec.region_core) ?? 1.6;
    const blur = (country ? spec.country_blur : spec.region_blur) ?? 4;
    const roleScale = hl.role === "context" ? 0.72 : 1;
    eachPolygon(geometry, (rings) => {
      rings.forEach((ring, index) => {
        const exterior = index === 0;
        glowCtx.save();
        glowCtx.beginPath();
        if (!traceRing(glowCtx, ring, project)) {
          glowCtx.restore();
          return;
        }
        glowCtx.lineJoin = "round";
        glowCtx.lineCap = "round";
        const strength = hl.fill_opacity ? Math.min(1, hl.opacity / hl.fill_opacity) : 1;
        glowCtx.shadowColor = theme.border_glow || "#FFD86B";
        glowCtx.shadowBlur = glowEnabled ? (exterior ? blur : blur * 0.4) * scale : 0;
        glowCtx.strokeStyle = theme.border_selected || "#FFF5C5";
        glowCtx.globalAlpha = (country ? 0.92 : 0.48) * roleScale * strength * (exterior ? 1 : 0.7);
        glowCtx.lineWidth = Math.max(1, core * scale * (exterior ? 1 : 0.75));
        glowCtx.stroke();
        glowCtx.restore();
      });
    });
  }
}
