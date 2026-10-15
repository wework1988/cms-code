#!/usr/bin/env node
import * as esbuild from "esbuild";
import { mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
mkdirSync(join(__dirname, ".cache"), { recursive: true });

await esbuild.build({
  entryPoints: [join(__dirname, "main.js")],
  bundle: true,
  outfile: join(__dirname, ".cache/bundle.js"),
  format: "esm",
  platform: "browser",
  target: ["chrome120"],
  sourcemap: true,
  loader: { ".css": "css" },
  logLevel: "info",
});
