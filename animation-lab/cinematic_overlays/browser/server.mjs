import http from "node:http";
import { existsSync, readFileSync, statSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL(".", import.meta.url));

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".woff2": "font/woff2",
};

function inside(folder, candidate) {
  const base = normalize(folder);
  const file = normalize(candidate);
  return file === base || file.startsWith(`${base}/`);
}

export function createServer({ planFile, fontDir }) {
  return http.createServer((req, res) => {
    const url = new URL(req.url || "/", "http://127.0.0.1");
    const pathname = decodeURIComponent(url.pathname);
    let file = null;
    if (pathname === "/" || pathname === "/index.html") file = join(root, "index.html");
    else if (pathname === "/stage.js") file = join(root, "stage.js");
    else if (pathname === "/plan.json") file = planFile;
    else if (pathname.startsWith("/fonts/")) {
      const candidate = join(fontDir, pathname.slice("/fonts/".length));
      file = inside(fontDir, candidate) ? candidate : null;
    }
    if (!file || !existsSync(file) || statSync(file).isDirectory()) {
      res.writeHead(404);
      res.end("not found");
      return;
    }
    res.writeHead(200, {
      "Content-Type": MIME[extname(file).toLowerCase()] || "application/octet-stream",
      "Cache-Control": "no-store",
    });
    res.end(readFileSync(file));
  });
}

export function listen(server) {
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => resolve(server.address().port));
  });
}
