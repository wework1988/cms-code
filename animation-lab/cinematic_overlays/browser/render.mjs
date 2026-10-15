#!/usr/bin/env node
/** Transparent overlay frames on an explicit clock. Does not connect to port 9222. */
import { createRequire } from "node:module";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer, listen } from "./server.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const lab = join(here, "..", "..");
const requireFromMap = createRequire(join(lab, "map-story/package.json"));
const { chromium } = requireFromMap("playwright");

function argument(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) throw new Error(`Missing ${name}`);
  return resolve(process.argv[index + 1]);
}

async function main() {
  const planFile = argument("--plan");
  const outputDir = argument("--output-dir");
  const fontDir = join(lab, "documentary-browser/assets/fonts");
  const plan = JSON.parse(readFileSync(planFile, "utf8"));
  mkdirSync(outputDir, { recursive: true });
  delete process.env.PLAYWRIGHT_CHROME_CDP;
  const server = createServer({ planFile, fontDir });
  const port = await listen(server);
  const browser = await chromium.launch({ headless: true, args: ["--disable-dev-shm-usage"] });
  try {
    const page = await browser.newPage({
      viewport: { width: plan.width, height: plan.height },
      deviceScaleFactor: 1,
    });
    page.on("pageerror", (error) => console.error(error.message));
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "domcontentloaded", timeout: 60000 });
    const started = Date.now();
    while (Date.now() - started < 30000) {
      const state = await page.evaluate(() => ({ ready: window.sampleReady === true, error: window.sampleError || null }));
      if (state.error) throw new Error(state.error);
      if (state.ready) break;
      await new Promise((r) => setTimeout(r, 50));
    }
    if (!(await page.evaluate(() => window.sampleReady === true))) throw new Error("Overlay renderer did not become ready");
    const holdMs = (plan.overlays[0].start_time + plan.overlays[0].reveal_duration + plan.overlays[0].hold_duration * 0.5) * 1000;
    await page.evaluate((time) => window.renderAt(time), holdMs);
    const first = await page.screenshot({ type: "png", omitBackground: true });
    await page.evaluate((time) => window.renderAt(time), 0);
    await page.evaluate((time) => window.renderAt(time), holdMs);
    const second = await page.screenshot({ type: "png", omitBackground: true });
    if (!first.equals(second)) throw new Error("renderAt is not deterministic");
    for (let frame = 0; frame < plan.frames; frame += 1) {
      await page.evaluate((time) => window.renderAt(time), (frame * 1000) / plan.fps);
      const png = await page.screenshot({ type: "png", omitBackground: true, animations: "disabled" });
      writeFileSync(join(outputDir, `overlay_${String(frame + 1).padStart(4, "0")}.png`), png);
    }
    console.log(JSON.stringify({ frames: plan.frames, outputDir }));
  } finally {
    await browser.close().catch(() => {});
    server.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
