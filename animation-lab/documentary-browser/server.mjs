import http from "node:http";
import { existsSync, readFileSync, statSync } from "node:fs";
import { extname, join, normalize, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".pdf": "application/pdf",
  ".ttf": "font/ttf",
  ".otf": "font/otf",
  ".ttc": "font/collection",
  ".woff2": "font/woff2",
};

function inside(root, candidate) {
  const rootResolved = normalize(root);
  const file = normalize(candidate);
  return file === rootResolved || file.startsWith(rootResolved + "/");
}

function safeJoin(root, relative) {
  const file = normalize(join(root, relative));
  return inside(root, file) ? file : null;
}

export function createServer({ planFile, assetRoots, fontDir }) {
  const publicDir = join(__dirname, "public");
  const vendorDir = join(__dirname, "vendor");
  const roots = assetRoots.map((root) => normalize(root));

  const server = http.createServer((req, res) => {
    try {
      const url = new URL(req.url || "/", "http://127.0.0.1");
      const pathname = decodeURIComponent(url.pathname);
      let file = null;
      if (pathname === "/" || pathname === "/index.html") file = join(publicDir, "index.html");
      else if (pathname === "/design.css" || pathname === "/stage.js") file = safeJoin(publicDir, pathname.slice(1));
      else if (pathname === "/plan.json") file = planFile;
      else if (pathname.startsWith("/vendor/")) file = safeJoin(vendorDir, pathname.slice("/vendor/".length));
      else if (pathname.startsWith("/assets/fonts/")) file = safeJoin(fontDir, pathname.slice("/assets/fonts/".length));
      else if (pathname === "/asset") {
        const listed = url.searchParams.get("path") || "";
        if (!listed || !roots.some((root) => inside(root, listed)) || !existsSync(listed)) {
          res.writeHead(404);
          res.end("asset refused");
          return;
        }
        file = listed;
      }
      if (!file || !existsSync(file) || statSync(file).isDirectory()) {
        res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
        res.end("not found");
        return;
      }
      const body = readFileSync(file);
      res.writeHead(200, {
        "Content-Type": MIME[extname(file).toLowerCase()] || "application/octet-stream",
        "Cache-Control": "no-store",
      });
      res.end(body);
    } catch (error) {
      res.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
      res.end(String(error));
    }
  });
  return server;
}

export function listen(server) {
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => resolve(server.address().port));
  });
}
