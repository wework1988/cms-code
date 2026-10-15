import http from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { extname, join, normalize, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = __dirname;
const LAB = join(__dirname, "..");

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".geojson": "application/geo+json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".ttf": "font/ttf",
  ".ttc": "font/collection",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

function resolvePath(urlPath, planFile) {
  const clean = decodeURIComponent(urlPath.split("?")[0]);
  if (clean === "/" || clean === "/index.html") return join(ROOT, "index.html");
  if (clean === "/bundle.js") return join(ROOT, ".cache/bundle.js");
  if (clean === "/bundle.js.map") return join(ROOT, ".cache/bundle.js.map");
  if (clean === "/plan.json") return planFile;
  if (clean.startsWith("/assets/maps/")) {
    return join(LAB, "assets/maps", clean.slice("/assets/maps/".length));
  }
  if (clean.startsWith("/assets/fonts/")) {
    return join(ROOT, "assets/fonts", clean.slice("/assets/fonts/".length));
  }
  const candidate = join(ROOT, normalize(clean).replace(/^(\.\.(\/|\\|$))+/, ""));
  if (!candidate.startsWith(ROOT)) return null;
  return candidate;
}

export function createServer(options = {}) {
  const planFile = options.planFile || join(ROOT, ".cache/plan.json");
  const server = http.createServer((req, res) => {
    try {
      const filePath = resolvePath(req.url || "/", planFile);
      if (!filePath || !existsSync(filePath) || statSync(filePath).isDirectory()) {
        res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
        res.end(`Not found: ${req.url}`);
        return;
      }
      const body = readFileSync(filePath);
      res.writeHead(200, {
        "Content-Type": MIME[extname(filePath)] || "application/octet-stream",
        "Cache-Control": "no-store",
      });
      res.end(body);
    } catch (err) {
      res.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
      res.end(String(err));
    }
  });
  return server;
}

export function listen(server, preferred = 0) {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(preferred, "127.0.0.1", () => {
      const { port } = server.address();
      resolve(`http://127.0.0.1:${port}`);
    });
  });
}
