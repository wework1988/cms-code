import assert from "node:assert/strict";
import test from "node:test";
import { pinBounds, pinMetrics, tracePin } from "./src/pin.js";

test("pin tip stays at the origin while the hole sits inside the bulb", () => {
  const bounds = pinBounds(54);
  const metrics = pinMetrics(54);
  assert.deepEqual(bounds.tip, [0, 0]);
  assert.ok(bounds.y < 0);
  assert.equal(bounds.y + bounds.h, 0);
  assert.ok(bounds.hole[1] < 0);
  assert.ok(bounds.hole[1] > bounds.y);
  assert.ok(bounds.hole[1] + bounds.hole[2] < 0);
  assert.ok(metrics.holeRadius < metrics.radius);
});

test("bulb outline travels over the top of the pin", () => {
  let anticlockwise = null;
  tracePin({
    beginPath() {},
    moveTo() {},
    quadraticCurveTo() {},
    arc(_x, _y, _r, _start, _end, flag) { anticlockwise = flag; },
    closePath() {},
  }, 54);
  assert.equal(anticlockwise, false);
});
