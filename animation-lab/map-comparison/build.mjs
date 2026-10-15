import * as esbuild from "esbuild";
import { cpSync, mkdirSync, existsSync, writeFileSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const cacheDir = join(__dirname, ".cache");
const cesiumSrc = join(__dirname, "node_modules/cesium/Build/Cesium");
const cesiumDest = join(cacheDir, "cesium");

mkdirSync(cacheDir, { recursive: true });

const depsOnly = process.argv.includes("--deps-only");

function syncCesiumAssets() {
  if (!existsSync(cesiumSrc)) {
    if (depsOnly) return;
    throw new Error("Cesium package missing. Run npm install first.");
  }
  mkdirSync(cesiumDest, { recursive: true });
  for (const part of ["Workers", "Assets", "ThirdParty", "Widgets", "Cesium.js"]) {
    const src = join(cesiumSrc, part);
    const dest = join(cesiumDest, part);
    if (!existsSync(src)) continue;
    cpSync(src, dest, { recursive: true });
  }
  writeFileSync(
    join(cesiumDest, ".stamp"),
    JSON.stringify({ copiedAt: new Date().toISOString() }, null, 2),
  );
}

syncCesiumAssets();
if (depsOnly) {
  console.log("[build] Cesium static assets cached.");
  process.exit(0);
}

const cssInjectPlugin = {
  name: "css-inject",
  setup(build) {
    build.onLoad({ filter: /\.css$/ }, async (args) => {
      const css = readFileSync(args.path, "utf8");
      const code = `
        const css = ${JSON.stringify(css)};
        if (typeof document !== 'undefined') {
          const style = document.createElement('style');
          style.setAttribute('data-src', ${JSON.stringify(args.path)});
          style.textContent = css;
          document.head.appendChild(style);
        }
        export default css;
      `;
      return { contents: code, loader: "js" };
    });
  },
};

await esbuild.build({
  absWorkingDir: __dirname,
  entryPoints: ["main.js"],
  outfile: join(cacheDir, "bundle.js"),
  bundle: true,
  format: "esm",
  platform: "browser",
  target: ["chrome120"],
  sourcemap: true,
  logLevel: "info",
  define: {
    CESIUM_BASE_URL: JSON.stringify("/cesium/"),
  },
  loader: {
    ".png": "dataurl",
    ".jpg": "dataurl",
    ".gif": "dataurl",
    ".webp": "dataurl",
    ".svg": "dataurl",
    ".ttf": "file",
    ".woff": "file",
    ".woff2": "file",
  },
  plugins: [cssInjectPlugin],
});

console.log("[build] Wrote .cache/bundle.js");
