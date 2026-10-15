#!/usr/bin/env node
import { spawn, spawnSync } from "node:child_process";
import {
  mkdirSync,
  existsSync,
  renameSync,
  rmSync,
  writeFileSync,
  readFileSync,
  copyFileSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { createServer, listen } from "./server.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const LAB = join(__dirname, "..");
const OUT_DIR = join(LAB, "output/map-comparison");
const CACHE = join(__dirname, ".cache");

const ENGINES = ["maplibre", "openlayers", "cesium"];

function parseArgs(argv) {
  const args = { engine: "all", frames: null, keepFrames: false };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--engine") args.engine = argv[++i];
    else if (a === "--keep-frames") args.keepFrames = true;
    else if (a === "--help" || a === "-h") args.help = true;
  }
  return args;
}

function ffmpegPath() {
  if (process.env.FFMPEG) return process.env.FFMPEG;
  const candidates = [
    join(
      LAB,
      ".venv/lib/python3.9/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1",
    ),
    join(
      LAB,
      ".venv/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1",
    ),
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
  // Fallback: ask imageio via python.
  const py = join(LAB, ".venv/bin/python");
  if (existsSync(py)) {
    const r = spawnSync(
      py,
      ["-c", "import imageio_ffmpeg as f; print(f.get_ffmpeg_exe())"],
      { encoding: "utf8" },
    );
    if (r.status === 0) return r.stdout.trim();
  }
  throw new Error("FFmpeg not found. Install ffmpeg or keep animation-lab/.venv.");
}

function buildBundle() {
  const r = spawnSync(process.execPath, [join(__dirname, "build.mjs")], {
    cwd: __dirname,
    stdio: "inherit",
  });
  if (r.status !== 0) throw new Error("esbuild bundle failed");
}

function readStory() {
  return JSON.parse(readFileSync(join(__dirname, "story.json"), "utf8"));
}

function packageVersions() {
  const pkg = JSON.parse(readFileSync(join(__dirname, "package.json"), "utf8"));
  const versions = {};
  for (const name of ["maplibre-gl", "ol", "cesium", "playwright", "esbuild"]) {
    try {
      const p = JSON.parse(
        readFileSync(join(__dirname, "node_modules", name, "package.json"), "utf8"),
      );
      versions[name] = p.version;
    } catch {
      versions[name] = pkg.dependencies[name] || "unknown";
    }
  }
  return versions;
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
  const state = await page.evaluate(() => ({
    ready: window.sampleReady === true,
    error: window.sampleError || null,
  }));
  throw new Error(
    `sampleReady timeout after ${timeoutMs}ms` +
      (state.error ? ` (${state.error})` : ""),
  );
}

async function renderEngine({ engine, story, baseUrl, ffmpeg, keepFrames }) {
  const frames = story.duration * story.fps;
  if (frames !== 300 && story.duration === 10 && story.fps === 30) {
    console.warn(`[render] Expected 300 frames; got ${frames}`);
  }
  const tmpDir = join(CACHE, `frames-${engine}`);
  const tmpMp4 = join(OUT_DIR, `.${engine}.partial.mp4`);
  const finalMp4 = join(OUT_DIR, `${engine}.mp4`);
  const previewPng = join(OUT_DIR, `${engine}.png`);
  const qaDir = join(OUT_DIR, "qa");
  const mid = Math.floor(frames / 2);
  const keyFrames = [
    { i: 0, name: "start" },
    { i: mid, name: "middle" },
    { i: frames - 1, name: "final" },
  ];

  if (keepFrames) {
    rmSync(tmpDir, { recursive: true, force: true });
    mkdirSync(tmpDir, { recursive: true });
  }
  mkdirSync(OUT_DIR, { recursive: true });
  mkdirSync(qaDir, { recursive: true });
  if (existsSync(tmpMp4)) rmSync(tmpMp4);

  console.log(`\n[render] ${engine}: ${frames} frames @ ${story.width}x${story.height}`);

  const browser = await chromium.launch({
    headless: true,
    args: [
      "--disable-dev-shm-usage",
      "--ignore-gpu-blocklist",
      "--enable-webgl",
      "--enable-webgl2",
      // Fallback when no GPU is available (Chrome 128+).
      "--enable-unsafe-swiftshader",
    ],
  });

  let page;
  let ff;
  const failedRequests = [];
  try {
    page = await browser.newPage({
      viewport: { width: story.width, height: story.height, deviceScaleFactor: 1 },
      deviceScaleFactor: 1,
    });
    page.on("pageerror", (err) => console.error(`[${engine}] pageerror:`, err.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") console.error(`[${engine}] console:`, msg.text());
    });
    page.on("requestfailed", (req) => {
      const failure = `${req.url()} :: ${req.failure()?.errorText || "unknown"}`;
      failedRequests.push(failure);
      console.error(`[${engine}] requestfailed:`, failure);
    });

    const url = `${baseUrl}/?engine=${engine}`;
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 120000 });
    try {
      await waitForReady(page);
    } catch (err) {
      if (failedRequests.length) {
        throw new Error(`${err.message}\nFailed requests:\n- ${failedRequests.join("\n- ")}`);
      }
      throw err;
    }

    ff = spawn(
      ffmpeg,
      [
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "image2pipe",
        "-framerate",
        String(story.fps),
        "-i",
        "-",
        "-frames:v",
        String(frames),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-movflags",
        "+faststart",
        "-an",
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
      const t = i / story.fps;
      await page.evaluate(async (time) => window.renderSample(time), t);
      const buf = await page.screenshot({ type: "png", caret: "hide", animations: "disabled" });
      if (!ff.stdin.write(buf)) {
        await new Promise((r) => ff.stdin.once("drain", r));
      }
      if (keepFrames) {
        writeFileSync(join(tmpDir, `frame-${String(i).padStart(5, "0")}.png`), buf);
      }
      for (const key of keyFrames) {
        if (key.i === i) {
          writeFileSync(join(qaDir, `${engine}-${key.name}.png`), buf);
          if (key.name === "middle") writeFileSync(previewPng, buf);
        }
      }
      if (i === 0 || i === mid || i === frames - 1 || (i + 1) % 30 === 0) {
        const elapsed = ((Date.now() - started) / 1000).toFixed(1);
        console.log(`[render] ${engine}: frame ${i + 1}/${frames} (t=${t.toFixed(2)}s, ${elapsed}s)`);
      }
    }
    ff.stdin.end();
    await ffDone;
    if (!existsSync(tmpMp4)) throw new Error(`Missing temp MP4 for ${engine}`);
    if (!existsSync(previewPng)) {
      // Fallback preview from first frame if mid write failed.
      await page.evaluate(async () => window.renderSample(story.duration / 2));
      writeFileSync(
        previewPng,
        await page.screenshot({ type: "png", caret: "hide", animations: "disabled" }),
      );
    }

    renameSync(tmpMp4, finalMp4);
    console.log(`[render] ${engine}: wrote ${finalMp4}`);
    ff = null;
  } finally {
    if (ff && !ff.killed) {
      try {
        ff.stdin.end();
      } catch {
        /* ignore */
      }
      ff.kill("SIGTERM");
    }
    await browser.close().catch(() => {});
    if (!keepFrames) rmSync(tmpDir, { recursive: true, force: true });
  }

  return { mp4: finalMp4, png: previewPng, frames };
}

function probeVideo(ffmpeg, file) {
  const r = spawnSync(
    ffmpeg,
    ["-hide_banner", "-i", file, "-f", "null", "-"],
    { encoding: "utf8" },
  );
  const text = `${r.stderr || ""}\n${r.stdout || ""}`;
  const dur = /Duration:\s*(\d+):(\d+):(\d+\.\d+)/.exec(text);
  const stream = /Stream #\d+:\d+.*Video: ([^,]+).*?(\d+)x(\d+)/.exec(text);
  const fps = /(\d+(?:\.\d+)?) fps/.exec(text);
  const pix = /yuv420p/.test(text);
  let duration = null;
  if (dur) duration = (+dur[1]) * 3600 + (+dur[2]) * 60 + (+dur[3]);
  return {
    ok: r.status === 0,
    duration,
    codec: stream?.[1],
    width: stream ? +stream[2] : null,
    height: stream ? +stream[3] : null,
    fps: fps ? +fps[1] : null,
    yuv420p: pix,
    raw: text.slice(0, 1200),
  };
}

function countFrames(ffmpeg, file) {
  const r = spawnSync(
    ffmpeg,
    ["-hide_banner", "-i", file, "-f", "null", "-"],
    { encoding: "utf8" },
  );
  const text = `${r.stderr || ""}\n${r.stdout || ""}`;
  // Take the last progress frame= value from a full decode.
  const matches = [...text.matchAll(/frame=\s*(\d+)/g)];
  if (matches.length) return +matches[matches.length - 1][1];
  return null;
}

async function makeContactSheet(ffmpeg, engines) {
  const qaDir = join(OUT_DIR, "qa");
  const tiles = [];
  for (const engine of engines) {
    for (const name of ["start", "middle", "final"]) {
      const p = join(qaDir, `${engine}-${name}.png`);
      if (existsSync(p)) tiles.push({ engine, name, path: p });
    }
  }
  if (!tiles.length) {
    const fallback = engines.map((e) => join(OUT_DIR, `${e}.png`)).filter(existsSync);
    if (!fallback.length) return null;
    const out = join(OUT_DIR, "contact-sheet.png");
    if (fallback.length === 1) {
      copyFileSync(fallback[0], out);
      return out;
    }
  }
  const out = join(OUT_DIR, "contact-sheet.png");
  if (!tiles.length) return null;

  const args = ["-y", "-hide_banner", "-loglevel", "error"];
  for (const t of tiles) args.push("-i", t.path);
  const labelled = tiles
    .map((t, i) => {
      const label = `${t.engine.toUpperCase()} · ${t.name}`;
      return `[${i}:v]scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1,drawtext=fontfile=/System/Library/Fonts/Supplemental/Arial.ttf:text='${label}':x=16:y=16:fontsize=22:fontcolor=white:borderw=2:bordercolor=black@0.7[v${i}]`;
    })
    .join(";");
  // Two rows if both engines present with 3 frames each; else hstack.
  let layout;
  if (tiles.length === 6) {
    layout = `${labelled};[v0][v1][v2]hstack=inputs=3[r0];[v3][v4][v5]hstack=inputs=3[r1];[r0][r1]vstack=inputs=2[out]`;
  } else {
    layout = `${labelled};${tiles.map((_, i) => `[v${i}]`).join("")}hstack=inputs=${tiles.length}[out]`;
  }
  args.push("-filter_complex", layout, "-map", "[out]", out);
  const r = spawnSync(ffmpeg, args, { stdio: "inherit" });
  if (r.status !== 0) throw new Error("contact sheet encode failed");
  return out;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(`Usage: npm run render -- --engine all|maplibre|openlayers|cesium`);
    process.exit(0);
  }

  const selected =
    args.engine === "all"
      ? ENGINES
      : args.engine === "documentary"
        ? ["maplibre", "openlayers"]
        : ENGINES.includes(args.engine)
          ? [args.engine]
          : null;
  if (!selected) {
    console.error(
      `Unknown engine "${args.engine}". Use: all|documentary|${ENGINES.join("|")}`,
    );
    process.exit(2);
  }

  const story = readStory();
  const ffmpeg = ffmpegPath();
  console.log(`[render] ffmpeg=${ffmpeg}`);
  console.log(`[render] story=${story.duration}s ${story.fps}fps ${story.width}x${story.height}`);

  buildBundle();
  mkdirSync(OUT_DIR, { recursive: true });

  const server = createServer();
  const baseUrl = await listen(server, 0);
  console.log(`[render] server ${baseUrl}`);

  const results = {};
  const errors = [];
  try {
    for (const engine of selected) {
      try {
        results[engine] = await renderEngine({
          engine,
          story,
          baseUrl,
          ffmpeg,
          keepFrames: args.keepFrames,
        });
      } catch (err) {
        errors.push({ engine, error: String(err?.stack || err) });
        console.error(`[render] ${engine} FAILED:`, err);
        // Preserve completed outputs from other engines.
      }
    }
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }

  const completed = Object.keys(results);
  let contact = null;
  try {
    contact = await makeContactSheet(ffmpeg, completed.length ? completed : selected);
  } catch (err) {
    console.warn("[render] contact sheet skipped:", err.message);
  }

  const versions = packageVersions();
  const probes = {};
  for (const engine of completed) {
    const file = results[engine].mp4;
    const info = probeVideo(ffmpeg, file);
    const frameCount = countFrames(ffmpeg, file);
    probes[engine] = { ...info, frameCount, file };
  }

  const manifest = {
    generatedAt: new Date().toISOString(),
    storyFile: story.story_file,
    resolution: { width: story.width, height: story.height },
    duration: story.duration,
    fps: story.fps,
    expectedFrames: story.duration * story.fps,
    libraries: versions,
    engines: probes,
    outputs: {
      videos: completed.map((e) => `output/map-comparison/${e}.mp4`),
      previews: completed.map((e) => `output/map-comparison/${e}.png`),
      contactSheet: contact ? "output/map-comparison/contact-sheet.png" : null,
    },
    notes: [
      "Silent H.264 MP4 (yuv420p, faststart) for documentary narration beds.",
      "Deterministic frame stepping via Playwright; not wall-clock flyTo recording.",
      "Terrain: local Natural Earth II shaded relief (Web Mercator JPEG), not satellite/3D.",
      "Routes, pulses and aircraft are illustrative fiction, not real military tracks.",
      "Natural Earth boundaries are generalised de facto outlines.",
      "probeVideo.ok requires FFmpeg exit status 0 (file existence alone is not success).",
    ],
    errors,
  };
  writeFileSync(join(OUT_DIR, "manifest.json"), JSON.stringify(manifest, null, 2));
  console.log(`\n[render] manifest → ${join(OUT_DIR, "manifest.json")}`);

  if (errors.length) {
    console.error(`[render] finished with ${errors.length} failure(s)`);
    process.exit(1);
  }
  console.log("[render] all requested engines completed");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
