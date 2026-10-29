// Build gate: every tool in data/tools.json must have public/og/tool-<id>.png (used for og:image / twitter:image).
// If this fails, run `node scripts/og.mjs` and commit the new images.
import fs from "node:fs";
const tools = JSON.parse(fs.readFileSync("data/tools.json", "utf8"));
const missing = tools.filter((t) => !fs.existsSync(`public/og/tool-${t.id}.png`) || fs.statSync(`public/og/tool-${t.id}.png`).size === 0).map((t) => t.id);
const notInDist = fs.existsSync("dist/og") ? tools.filter((t) => !fs.existsSync(`dist/og/tool-${t.id}.png`)).map((t) => t.id) : [];
if (missing.length || notInDist.length) {
  if (missing.length) console.error(`OG images missing in public/og for ${missing.length} tool(s): ${missing.join(", ")}\nRun: node scripts/og.mjs`);
  if (notInDist.length) console.error(`OG images missing in dist/og for ${notInDist.length} tool(s): ${notInDist.join(", ")}`);
  process.exit(1);
}
console.log(`OG images: ${tools.length}/${tools.length} tools ok`);
