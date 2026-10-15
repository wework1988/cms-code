#!/usr/bin/env node
/**
 * Isolated Playwright + FFmpeg renderer for map-story resolved plans.
 * Does not connect to Chrome :9222.
 */
import { spawn, spawnSync } from "node:child_process";
import {
  mkdirSync,
  existsSync,
  renameSync,
  rmSync,
  writeFileSync,
  readFileSync,
  copyFileSync,
  statSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { createServer, listen } from "./server.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const LAB = join(__dirname, "..");
const CACHE = join(__dirname, ".cache");

function parseArgs(argv) {
  const args = {
    engine: "maplibre",
    plan: null,
    outputDir: join(LAB, "output/gorakhpur-map"),
    cacheDir: null,
    keepFrames: false,
    stillsOnly: false,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--engine") args.engine = argv[++i];
    else if (a === "--plan") args.plan = argv[++i];
    else if (a === "--output-dir") args.outputDir = resolve(argv[++i]);
    else if (a === "--cache-dir") args.cacheDir = resolve(argv[++i]);
    else if (a === "--keep-frames") args.keepFrames = true;
    else if (a === "--stills-only") args.stillsOnly = true;
  }
  return args;
}

function ffmpegPath() {
  if (process.env.FFMPEG) return process.env.FFMPEG;
  const candidates = [
    join(LAB, ".venv/lib/python3.9/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"),
    join(LAB, ".venv/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"),
    "ffmpeg",
  ];
  for (const c of candidates) {
    if (c === "ffmpeg") {
      const which = spawnSync("which", ["ffmpeg"], { encoding: "utf8" });
      if (which.status === 0) return which.stdout.trim();
      continue;
    }
    if (existsSync(c)) return c;
  }
  const py = join(LAB, ".venv/bin/python");
  if (existsSync(py)) {
    const r = spawnSync(py, ["-c", "import imageio_ffmpeg as f; print(f.get_ffmpeg_exe())"], {
      encoding: "utf8",
    });
    if (r.status === 0) return r.stdout.trim();
  }
  throw new Error("FFmpeg not found");
}

function buildBundle() {
  const r = spawnSync(process.execPath, [join(__dirname, "build.mjs")], {
    cwd: __dirname,
    stdio: "inherit",
  });
  if (r.status !== 0) throw new Error("esbuild bundle failed");
}

async function waitForReady(page, timeoutMs = 90000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const state = await page.evaluate(() => ({
      ready: window.sampleReady === true,
      error: window.sampleError || null,
    }));
    if (state.error) throw new Error(`Page init failed: ${state.error}`);
    if (state.ready) return;
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error(`sampleReady timeout after ${timeoutMs}ms`);
}

function probeVideo(ffmpeg, file) {
  const r = spawnSync(ffmpeg, ["-hide_banner", "-i", file, "-f", "null", "-"], {
    encoding: "utf8",
  });
  const text = `${r.stderr || ""}\n${r.stdout || ""}`;
  const dur = /Duration:\s*(\d+):(\d+):(\d+\.\d+)/.exec(text);
  const stream = /Stream #\d+:\d+.*Video: ([^,]+).*?(\d+)x(\d+)/.exec(text);
  const fps = /(\d+(?:\.\d+)?) fps/.exec(text);
  const matches = [...text.matchAll(/frame=\s*(\d+)/g)];
  const frameCount = matches.length ? +matches[matches.length - 1][1] : null;
  let duration = null;
  if (dur) duration = (+dur[1]) * 3600 + (+dur[2]) * 60 + (+dur[3]);
  return {
    ok: r.status === 0,
    duration,
    codec: stream?.[1],
    width: stream ? +stream[2] : null,
    height: stream ? +stream[3] : null,
    fps: fps ? +fps[1] : null,
    yuv420p: /yuv420p/.test(text),
    frameCount,
  };
}

function checkpointsFor(plan) {
  if (Array.isArray(plan.qa_frames) && plan.qa_frames.length) {
    return plan.qa_frames.filter((c) => c && c.t < plan.duration && c.name);
  }
  return [
    { t: 1.2, name: "world-india" },
    { t: 4.5, name: "india-up" },
    { t: 8.0, name: "up-district" },
    { t: 12.0, name: "district" },
    { t: 16.0, name: "callout" },
  ].filter((c) => c.t < plan.duration);
}

async function renderEngine({ engine, plan, baseUrl, ffmpeg, outDir, keepFrames, stillsOnly }) {
  const frames = Math.round(plan.duration * plan.fps);
  const tmpMp4 = join(outDir, `.${engine}.partial.mp4`);
  const finalMp4 = join(outDir, `${engine}.mp4`);
  const qaDir = join(outDir, "qa");
  mkdirSync(outDir, { recursive: true });
  mkdirSync(qaDir, { recursive: true });
  if (existsSync(tmpMp4)) rmSync(tmpMp4);

  const checkpoints = checkpointsFor(plan);

  console.log(`\n[map-story] ${engine}: ${frames} frames @ ${plan.width}x${plan.height}`);

  const browser = await chromium.launch({
    headless: true,
    args: [
      "--disable-dev-shm-usage",
      "--ignore-gpu-blocklist",
      "--enable-webgl",
      "--enable-webgl2",
      "--enable-unsafe-swiftshader",
    ],
  });

  let page;
  let ff;
  let probe;
  try {
    page = await browser.newPage({
      viewport: { width: plan.width, height: plan.height, deviceScaleFactor: 1 },
      deviceScaleFactor: 1,
    });
    page.on("pageerror", (err) => console.error(`[${engine}] pageerror:`, err.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") console.error(`[${engine}] console:`, msg.text());
    });

    await page.goto(`${baseUrl}/?engine=${engine}`, {
      waitUntil: "domcontentloaded",
      timeout: 120000,
    });
    await waitForReady(page);

    if (stillsOnly) {
      for (const cp of checkpoints) {
        await page.evaluate(async (time) => window.renderSample(time), cp.t);
        const buf = await page.screenshot({ type: "png", caret: "hide", animations: "disabled" });
        const file = join(qaDir, `${engine}-${cp.name}.png`);
        writeFileSync(file, buf);
        console.log(`[map-story] still ${file}`);
      }
      return { mp4: null, probe: null, frames: checkpoints.length, stillsOnly: true };
    }

    ff = spawn(
      ffmpeg,
      [
        "-y", "-hide_banner", "-loglevel", "error",
        "-f", "image2pipe", "-framerate", String(plan.fps), "-i", "-",
        "-frames:v", String(frames),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "medium", "-crf", "18",
        "-movflags", "+faststart", "-an",
        tmpMp4,
      ],
      { stdio: ["pipe", "inherit", "inherit"] },
    );
    const ffDone = new Promise((resolve, reject) => {
      ff.on("close", (code) => {
        if (code === 0) resolve();
        else reject(new Error(`FFmpeg failed for ${engine} (exit ${code})`));
      });
      ff.on("error", reject);
    });

    const started = Date.now();
    for (let i = 0; i < frames; i += 1) {
      const t = i / plan.fps;
      await page.evaluate(async (time) => window.renderSample(time), t);
      const buf = await page.screenshot({ type: "png", caret: "hide", animations: "disabled" });
      if (!ff.stdin.write(buf)) {
        await new Promise((r) => ff.stdin.once("drain", r));
      }
      for (const cp of checkpoints) {
        if (Math.round(cp.t * plan.fps) === i) {
          writeFileSync(join(qaDir, `${engine}-${cp.name}.png`), buf);
        }
      }
      if (i === 0 || i === frames - 1 || (i + 1) % 30 === 0) {
        const elapsed = ((Date.now() - started) / 1000).toFixed(1);
        console.log(`[map-story] ${engine}: frame ${i + 1}/${frames} (t=${t.toFixed(2)}s, ${elapsed}s)`);
      }
    }
    ff.stdin.end();
    await ffDone;
    if (!existsSync(tmpMp4) || statSync(tmpMp4).size < 1000) {
      throw new Error(`Temporary MP4 missing or too small for ${engine}`);
    }
    probe = probeVideo(ffmpeg, tmpMp4);
    if (!probe.ok) throw new Error(`FFmpeg probe failed for temporary ${engine} video`);
    if (probe.width !== plan.width || probe.height !== plan.height) {
      throw new Error(`Resolution mismatch: ${probe.width}x${probe.height}`);
    }
    if (!probe.yuv420p) throw new Error("Expected yuv420p");
    if (probe.frameCount != null && Math.abs(probe.frameCount - frames) > 1) {
      throw new Error(`Frame count ${probe.frameCount} != expected ${frames}`);
    }
    if (probe.duration != null && Math.abs(probe.duration - plan.duration) > 0.15) {
      throw new Error(`Duration ${probe.duration} != expected ${plan.duration}`);
    }
    renameSync(tmpMp4, finalMp4);
    console.log(`[map-story] ${engine}: wrote ${finalMp4}`);
    ff = null;
  } finally {
    if (ff && !ff.killed) {
      try { ff.stdin.end(); } catch { /* ignore */ }
      ff.kill("SIGTERM");
    }
    await browser.close().catch(() => {});
  }

  return { mp4: finalMp4, probe, frames };
}

async function makeContactSheet(ffmpeg, outDir, engine, plan) {
  const qaDir = join(outDir, "qa");
  const names = checkpointsFor(plan).map((c) => c.name);
  const tiles = names
    .map((n) => ({ name: n, path: join(qaDir, `${engine}-${n}.png`) }))
    .filter((t) => existsSync(t.path));
  if (!tiles.length) return null;
  const out = join(outDir, "contact-sheet.png");
  const args = ["-y", "-hide_banner", "-loglevel", "error"];
  for (const t of tiles) args.push("-i", t.path);
  const labelled = tiles
    .map((t, i) => {
      const label = t.name.replace(/'/g, "");
      return `[${i}:v]scale=384:216:force_original_aspect_ratio=decrease,pad=384:216:(ow-iw)/2:(oh-ih)/2,setsar=1,drawtext=fontfile=/System/Library/Fonts/Supplemental/Arial.ttf:text='${label}':x=10:y=10:fontsize=16:fontcolor=white:borderw=2:bordercolor=black@0.7[v${i}]`;
    })
    .join(";");
  const layout = `${labelled};${tiles.map((_, i) => `[v${i}]`).join("")}hstack=inputs=${tiles.length}[out]`;
  args.push("-filter_complex", layout, "-map", "[out]", out);
  const r = spawnSync(ffmpeg, args, { encoding: "utf8" });
  if (r.status !== 0) {
    console.warn("[map-story] contact sheet failed:", r.stderr?.slice(0, 400));
    return null;
  }
  return out;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.plan || !existsSync(args.plan)) {
    throw new Error(`--plan required (resolved-plan.json). Got: ${args.plan}`);
  }
  if (!["maplibre", "openlayers"].includes(args.engine)) {
    throw new Error(`Unsupported engine: ${args.engine}`);
  }

  const cacheDir = args.cacheDir || CACHE;
  mkdirSync(cacheDir, { recursive: true });
  mkdirSync(args.outputDir, { recursive: true });
  const planFile = join(cacheDir, "plan.json");
  copyFileSync(args.plan, planFile);
  buildBundle();

  const plan = JSON.parse(readFileSync(args.plan, "utf8"));
  const ffmpeg = ffmpegPath();
  const server = createServer({ planFile });
  const baseUrl = await listen(server, 0);
  console.log(`[map-story] local server ${baseUrl}`);

  try {
    const result = await renderEngine({
      engine: args.engine,
      plan,
      baseUrl,
      ffmpeg,
      outDir: args.outputDir,
      keepFrames: args.keepFrames,
      stillsOnly: args.stillsOnly,
    });
    const sheet = await makeContactSheet(ffmpeg, args.outputDir, args.engine, plan);
    const manifestPath = join(args.outputDir, "manifest.json");
    let manifest = {};
    if (existsSync(manifestPath)) {
      try { manifest = JSON.parse(readFileSync(manifestPath, "utf8")); } catch { /* ignore */ }
    }
    manifest.schema_version = "1.0";
    manifest.output_dir = args.outputDir;
    manifest.engines = manifest.engines || {};
    manifest.engines[args.engine] = {
      mp4: result.mp4,
      frames: result.frames,
      probe: result.probe,
      contact_sheet: sheet,
    };
    manifest.updated_at = new Date().toISOString();
    writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
    if (result.probe) {
      console.log(`[map-story] verification ok: ${result.probe.width}x${result.probe.height} `
        + `${result.probe.fps}fps ~${result.probe.duration}s frames=${result.probe.frameCount}`);
    } else {
      console.log(`[map-story] stills written: ${result.frames}`);
    }
  } finally {
    server.close();
  }
}

main().catch((err) => {
  console.error("[map-story] ERROR:", err.message || err);
  process.exit(1);
});
