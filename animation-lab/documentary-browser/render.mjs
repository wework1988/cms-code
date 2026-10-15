#!/usr/bin/env node
/** Isolated Playwright frame clock. Does not connect to Chrome port 9222. */
import { spawn, spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer, listen } from "./server.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const LAB = join(__dirname, "..");
const requireFromMap = createRequire(join(LAB, "map-story/package.json"));
const { chromium } = requireFromMap("playwright");

function parseArgs(argv) {
  const args = { plan: null, outputDir: null, cacheDir: null };
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--plan") args.plan = resolve(argv[++i]);
    else if (argv[i] === "--output-dir") args.outputDir = resolve(argv[++i]);
    else if (argv[i] === "--cache-dir") args.cacheDir = resolve(argv[++i]);
  }
  if (!args.plan || !args.outputDir) throw new Error("Use --plan and --output-dir");
  return args;
}

function ffmpegPath() {
  const py = join(LAB, ".venv/bin/python");
  const result = spawnSync(py, ["-c", "import imageio_ffmpeg as f; print(f.get_ffmpeg_exe())"], { encoding: "utf8" });
  if (result.status !== 0) throw new Error(result.stderr || "FFmpeg not found");
  return result.stdout.trim();
}

function copyVendors() {
  const vendor = join(__dirname, "vendor");
  mkdirSync(join(vendor, "pdfjs"), { recursive: true });
  const nodeModules = join(__dirname, "node_modules");
  cpSync(join(nodeModules, "animejs/lib/anime.min.js"), join(vendor, "anime.min.js"));
  cpSync(join(nodeModules, "d3/dist/d3.min.js"), join(vendor, "d3.min.js"));
  cpSync(join(nodeModules, "pdfjs-dist/build/pdf.min.mjs"), join(vendor, "pdfjs/pdf.min.mjs"));
  cpSync(join(nodeModules, "pdfjs-dist/build/pdf.worker.min.mjs"), join(vendor, "pdfjs/pdf.worker.min.mjs"));
  const fonts = join(nodeModules, "pdfjs-dist/standard_fonts");
  if (existsSync(fonts)) cpSync(fonts, join(vendor, "pdfjs/standard_fonts"), { recursive: true });
}

function ensureFonts() {
  const dir = join(__dirname, "assets/fonts");
  mkdirSync(dir, { recursive: true });
  const required = ["NotoSansDevanagari-Regular.woff2", "NotoSans-Regular.woff2"];
  const missing = required.filter((name) => !existsSync(join(dir, name)));
  if (missing.length) {
    throw new Error(`Missing OFL fonts in assets/fonts: ${missing.join(", ")}`);
  }
  return dir;
}

function lastFrameCount(text) {
  const matches = [...text.matchAll(/frame=\s*(\d+)/g)];
  return matches.length ? Number(matches[matches.length - 1][1]) : null;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  delete process.env.PLAYWRIGHT_CHROME_CDP;
  copyVendors();
  const fontDir = ensureFonts();
  const plan = JSON.parse(readFileSync(args.plan, "utf8"));
  const frames = Math.round(plan.duration_seconds * plan.fps);
  mkdirSync(args.outputDir, { recursive: true });
  const partial = join(args.outputDir, "documentary.partial.mp4");
  const stillDir = join(args.outputDir, "frames");
  mkdirSync(stillDir, { recursive: true });
  if (existsSync(partial)) rmSync(partial);
  const assetRoots = [LAB, dirname(args.plan)];
  for (const asset of plan.assets || []) {
    if (asset.path) assetRoots.push(dirname(asset.path));
  }
  const server = createServer({ planFile: args.plan, assetRoots, fontDir });
  const port = await listen(server);
  const browser = await chromium.launch({
    headless: true,
    args: ["--disable-dev-shm-usage"],
  });
  const ffmpeg = ffmpegPath();
  let page;
  let ff;
  try {
    page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
    page.on("pageerror", (error) => console.error(error.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") console.error(msg.text());
    });
    await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: "domcontentloaded", timeout: 120000 });
    const started = Date.now();
    while (Date.now() - started < 90000) {
      const state = await page.evaluate(() => ({ ready: window.sampleReady === true, error: window.sampleError || null }));
      if (state.error) throw new Error(state.error);
      if (state.ready) break;
      await new Promise((r) => setTimeout(r, 150));
    }
    const ready = await page.evaluate(() => window.sampleReady === true);
    if (!ready) throw new Error("Renderer did not become ready");
    await page.evaluate(async (time) => window.renderAt(time), 1200);
    const first = await page.screenshot({ type: "jpeg", quality: 85 });
    await page.evaluate(async (time) => window.renderAt(time), 400);
    await page.evaluate(async (time) => window.renderAt(time), 1200);
    const second = await page.screenshot({ type: "jpeg", quality: 85 });
    if (!first.equals(second)) throw new Error("renderAt is not deterministic for the same timestamp");

    ff = spawn(ffmpeg, [
      "-y", "-hide_banner", "-loglevel", "error",
      "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", String(plan.fps), "-i", "-",
      "-frames:v", String(frames),
      "-vf", "scale=in_range=jpeg:out_range=tv,format=yuv420p",
      "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "18",
      "-movflags", "+faststart", "-an", partial,
    ], { stdio: ["pipe", "inherit", "inherit"] });
    const done = new Promise((resolveDone, reject) => {
      ff.on("close", (code) => (code === 0 ? resolveDone() : reject(new Error(`FFmpeg exited ${code}`))));
      ff.on("error", reject);
    });
    const checkpoints = (plan.beats || []).map((beat, index) => ({
      frame: Math.min(frames - 1, Math.round(((beat.start + beat.end) / 2) * plan.fps)),
      name: `beat-${String(index + 1).padStart(2, "0")}`,
    }));
    checkpoints.push({ frame: frames - 1, name: "hold" });
    for (let i = 0; i < frames; i += 1) {
      await page.evaluate(async (time) => window.renderAt(time), (i * 1000) / plan.fps);
      const buf = await page.screenshot({ type: "jpeg", quality: 85, caret: "hide", animations: "disabled" });
      if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once("drain", r));
      for (const point of checkpoints) {
        if (point.frame === i) writeFileSync(join(stillDir, `${point.name}.jpg`), buf);
      }
      if (i === 0 || i + 1 === frames || (i + 1) % 60 === 0) {
        console.log(`[documentary] frame ${i + 1}/${frames}`);
      }
    }
    ff.stdin.end();
    await done;
    if (!existsSync(partial) || statSync(partial).size < 1000) throw new Error("Partial MP4 is missing");
    const probe = spawnSync(ffmpeg, ["-hide_banner", "-i", partial, "-f", "null", "-"], { encoding: "utf8" });
    const text = `${probe.stderr || ""}\n${probe.stdout || ""}`;
    const decoded = lastFrameCount(text);
    if (probe.status !== 0 || decoded !== frames) {
      throw new Error(`Decode check failed (${decoded} vs ${frames})`);
    }
    console.log(JSON.stringify({ partial, frames: decoded }));
  } finally {
    if (ff && ff.stdin && !ff.stdin.destroyed) ff.stdin.destroy();
    if (page) await page.close().catch(() => {});
    await browser.close().catch(() => {});
    server.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
