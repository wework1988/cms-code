#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer, listen } from "./server.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));

const r = spawnSync(process.execPath, [join(__dirname, "build.mjs")], {
  cwd: __dirname,
  stdio: "inherit",
});
if (r.status !== 0) process.exit(r.status ?? 1);

const server = createServer();
const baseUrl = await listen(server, 4173);
const engines = ["maplibre", "openlayers", "cesium"];

console.log("\nMap comparison preview server");
console.log(`  ${baseUrl}/?engine=maplibre`);
for (const e of engines) console.log(`  ${baseUrl}/?engine=${e}`);
console.log("\nOpen a URL above. Ctrl+C to stop.\n");

// Optional live scrubber via query ?t=3.5 after load — page exposes renderSample.
process.on("SIGINT", () => {
  server.close(() => process.exit(0));
});
