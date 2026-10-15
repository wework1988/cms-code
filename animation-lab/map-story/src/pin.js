/** Teardrop pin in local pixels. The geographic anchor is the tip at (0, 0). */

export function pinMetrics(height) {
  const radius = height * 0.32;
  const centerY = -(height - radius);
  return {
    height,
    radius,
    centerY,
    holeRadius: radius * 0.46,
    left: -radius,
    right: radius,
    top: centerY - radius,
    bottom: 0,
  };
}

export function tracePin(ctx, height) {
  const { radius, centerY } = pinMetrics(height);
  ctx.beginPath();
  ctx.moveTo(0, 0);
  ctx.quadraticCurveTo(-radius * 0.2, centerY * 0.45, -radius, centerY);
  // Canvas angles increase clockwise because y points down. Clockwise from
  // the left side (PI) to the right side (0) travels over the top of the bulb.
  ctx.arc(0, centerY, radius, Math.PI, 0, false);
  ctx.quadraticCurveTo(radius * 0.2, centerY * 0.45, 0, 0);
  ctx.closePath();
}

export function pinBounds(height) {
  const metrics = pinMetrics(height);
  return {
    x: metrics.left,
    y: metrics.top,
    w: metrics.right - metrics.left,
    h: metrics.bottom - metrics.top,
    tip: [0, 0],
    hole: [0, metrics.centerY, metrics.holeRadius],
  };
}
