export function documentaryPresentation(theme) {
  const mode = theme?.capabilities?.presentation;
  if (mode) return mode === "documentary";
  return theme?.id === "documentary_relief_bold";
}

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
  };
}

export function waitFrame() {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}

export function withTimeout(promise, ms, label) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
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

export function highlightOpacity(hl, t, duration) {
  if (t < hl.from || t > hl.to) return 0;
  let o = hl.fill_opacity ?? 0.5;
  const fadeIn = 0.35;
  const fadeOut = hl.fade_out ?? 0.4;
  if (t < hl.from + fadeIn) o *= ease((t - hl.from) / fadeIn);
  const holdThroughEnd = duration != null && hl.to >= duration - 0.05;
  if (!holdThroughEnd && fadeOut > 0 && t > hl.to - fadeOut) o *= 1 - ease((t - (hl.to - fadeOut)) / fadeOut);
  return clamp(o);
}
