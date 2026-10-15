export function clamp(v, a = 0, b = 1) {
  return Math.max(a, Math.min(b, v));
}

export function ease(v) {
  v = clamp(v);
  return v * v * (3 - 2 * v);
}

export function lerp(a, b, u) {
  return a + (b - a) * u;
}

export function lerp2(a, b, u) {
  return [lerp(a[0], b[0], u), lerp(a[1], b[1], u)];
}

/** Piecewise ease between camera keyframes keyed by time `t`. */
export function sampleCamera(keyframes, t) {
  if (!keyframes?.length) throw new Error("camera.keyframes required");
  if (t <= keyframes[0].t) return { ...keyframes[0], u: 0 };
  if (t >= keyframes[keyframes.length - 1].t) {
    return { ...keyframes[keyframes.length - 1], u: 1 };
  }
  let i = 0;
  while (i < keyframes.length - 1 && keyframes[i + 1].t < t) i += 1;
  const a = keyframes[i];
  const b = keyframes[i + 1];
  const u = ease((t - a.t) / (b.t - a.t));
  return {
    t,
    u,
    center: lerp2(a.center, b.center, u),
    zoom: lerp(a.zoom, b.zoom, u),
    pitch: lerp(a.pitch ?? 0, b.pitch ?? 0, u),
    bearing: lerp(a.bearing ?? 0, b.bearing ?? 0, u),
    altitude_m: lerp(a.altitude_m ?? 0, b.altitude_m ?? 0, u),
    heading_deg: lerp(a.heading_deg ?? 0, b.heading_deg ?? 0, u),
    pitch_deg: lerp(a.pitch_deg ?? -90, b.pitch_deg ?? -90, u),
  };
}

export function activeCaption(captions, t) {
  for (const c of captions) {
    if (t >= c.start && t < c.end) return c.text;
  }
  const last = captions[captions.length - 1];
  if (last && t >= last.start) return last.text;
  return "";
}

export function routePoint(route, u) {
  if (!route?.length) return null;
  if (u <= 0) return route[0];
  if (u >= 1) return route[route.length - 1];
  const scaled = u * (route.length - 1);
  const i = Math.floor(scaled);
  const f = scaled - i;
  return lerp2(route[i], route[i + 1] || route[i], f);
}

export function waitFrame() {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}

export function waitIdle(ms = 0) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function withTimeout(promise, ms, label) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

/** Smooth 0–1 emphasis for Bangladesh after bangladesh_from. */
export function bangladeshEmphasis(story, t) {
  const from = story.highlights.bangladesh_from ?? 4;
  const fade = story.highlights.bangladesh_fade ?? 0.85;
  return ease((t - from) / fade);
}

export function preloadImage(url, timeoutMs = 30000) {
  return withTimeout(
    new Promise((resolve, reject) => {
      const img = new Image();
      img.decoding = "async";
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error(`Failed to load image: ${url}`));
      img.src = url;
    }),
    timeoutMs,
    `Image load ${url}`,
  );
}
