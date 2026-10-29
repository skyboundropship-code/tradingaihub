// Build gate: every OG card that pages reference via og:image / twitter:image must exist (non-empty) in public/og and dist/og:
// home, weekly, every category, every comparison (from src/lib/data.ts) and every tool (from data/tools.json).
// scripts/og.mjs runs as the first step of `npm run build`; if this still fails, check its output.
import fs from "node:fs";
const tools = JSON.parse(fs.readFileSync("data/tools.json", "utf8"));
const lib = fs.readFileSync("src/lib/data.ts", "utf8");
const cats = [...lib.matchAll(/slug: "([^"]+)", name: "([^"]+)", short: "[^"]+", icon: "([^"]+)"/g)].map((m) => m[1]);
const comps = [...lib.matchAll(/slug: "([^"]+)", title: "([^"]+)"/g)].map((m) => m[1]);
if (!cats.length || !comps.length) { console.error(`check_og: could not parse categories (${cats.length}) or comparisons (${comps.length}) from src/lib/data.ts`); process.exit(1); }
const names = ["home", "weekly", ...cats.map((c) => `category-${c}`), ...comps.map((c) => `compare-${c}`), ...tools.map((t) => `tool-${t.id}`)];
const ok = (p) => fs.existsSync(p) && fs.statSync(p).size > 0;
const missing = names.filter((n) => !ok(`public/og/${n}.png`));
const notInDist = fs.existsSync("dist/og") ? names.filter((n) => !ok(`dist/og/${n}.png`)) : [];
if (missing.length || notInDist.length) {
  if (missing.length) console.error(`OG images missing in public/og (${missing.length}): ${missing.join(", ")}\nRun: node scripts/og.mjs`);
  if (notInDist.length) console.error(`OG images missing in dist/og (${notInDist.length}): ${notInDist.join(", ")}`);
  process.exit(1);
}
console.log(`OG images: ${tools.length}/${tools.length} tools ok; all ${names.length} cards ok (home, weekly, ${cats.length} categories, ${comps.length} comparisons, ${tools.length} tools)`);
