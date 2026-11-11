// Name guard: fails if the built dist/ or any git-tracked file contains the owner's personal name.
// Public copy must use "TradingAIHub" / "the TradingAIHub team" / hello@tradingaihub.com.
// Patterns are written as escapes so this file doesn't match itself.
import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const RE = new RegExp(["\x6ciran", "\x73egal", "\u05dc\u05d9\u05e8\u05df", "\u05e1\u05d2\u05dc", "\u0644\u064a\u0631\u0627\u0646"].join("|"), "gi");
// Exact substrings that are allowed (third-party ids we don't control). Remove each entry once it's gone.
export const ALLOW = [];

export function findNames(text) {
  let t = String(text);
  for (const a of ALLOW) t = t.split(a).join("");
  return [...t.matchAll(RE)].map(m => m[0]);
}

function walk(dir, out = []) {
  for (const n of readdirSync(dir)) { const p = join(dir, n); statSync(p).isDirectory() ? walk(p, out) : out.push(p); }
  return out;
}

export function scan(root) {
  const hits = [];
  const check = (abs) => { const h = findNames(readFileSync(abs, "utf8")); if (h.length) hits.push(`${relative(root, abs)}: ${h.length} match(es)`); };
  const tracked = execFileSync("git", ["ls-files", "-z"], { cwd: root, encoding: "utf8" }).split("\0").filter(Boolean);
  for (const f of tracked) { const p = join(root, f); if (existsSync(p) && statSync(p).isFile()) check(p); }
  const dist = join(root, "dist");
  let n = 0;
  if (existsSync(dist)) for (const p of walk(dist)) { check(p); n++; }
  return { hits, tracked: tracked.length, dist: n };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const root = join(fileURLToPath(new URL(".", import.meta.url)), "..");
  const { hits, tracked, dist } = scan(root);
  if (hits.length) { console.error(`Name guard: FAIL\n  ${hits.join("\n  ")}`); process.exit(1); }
  console.log(`Name guard: 0 matches (${tracked} tracked files, ${dist} dist files)`);
}
