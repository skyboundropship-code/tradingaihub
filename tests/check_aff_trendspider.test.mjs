// npm run test:functions — scripts/check_aff.mjs TrendSpider gate: requires _go=tradingaihub, fails on any other _go value
// (including the retired referral id). Runs check_aff in a temp copy; the dist-based cases need a prior `npm run build`.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs"; import os from "node:os"; import path from "node:path";
import { spawnSync } from "node:child_process";

const ROOT = path.resolve(import.meta.dirname, "..");
const SCRIPT = path.join(ROOT, "scripts/check_aff.mjs");
const OLD = ["li", "ran", "-13d76f"].join(""); // retired id, assembled so the literal never appears in the repo

function sandbox({ config, page, withDist = false }) {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), "chkaff-"));
  fs.mkdirSync(path.join(d, "src"));
  fs.writeFileSync(path.join(d, "src/config.ts"), config ?? fs.readFileSync(path.join(ROOT, "src/config.ts"), "utf8"));
  fs.symlinkSync(path.join(ROOT, "src/i18n"), path.join(d, "src/i18n"));
  fs.symlinkSync(path.join(ROOT, "data"), path.join(d, "data"));
  if (withDist) {
    fs.cpSync(path.join(ROOT, "dist"), path.join(d, "dist"), { recursive: true, filter: (s) => !/\.(png|jpe?g|webp|svg|ico|xml|txt|json|js|css|woff2?)$/.test(s) });
    if (page) { fs.mkdirSync(path.join(d, "dist/zz-ts-test"), { recursive: true }); fs.writeFileSync(path.join(d, "dist/zz-ts-test/index.html"), page); }
  } else fs.mkdirSync(path.join(d, "dist"));
  const r = spawnSync(process.execPath, [SCRIPT], { cwd: d, encoding: "utf8" });
  fs.rmSync(d, { recursive: true, force: true });
  return r;
}
const hasDist = fs.existsSync(path.join(ROOT, "dist/index.html"));
const link = (go) => `<html lang="en"><body><p id="aff-note">n</p><a href="https://trendspider.com/?_go=${go}" rel="sponsored noopener" aria-describedby="aff-note">TS</a><span class="partner-tag">PARTNER</span></body></html>`;

test("config gate: AFFILIATES.trendspider.id must be tradingaihub (retired or other ids fail)", { skip: !hasDist && "needs npm run build" }, () => {
  const cfg = fs.readFileSync(path.join(ROOT, "src/config.ts"), "utf8");
  assert.match(cfg, /trendspider:\s*\{\s*id:\s*"tradingaihub"/);
  for (const bad of [OLD, "someone"]) {
    const r = sandbox({ withDist: true, config: cfg.replace(/(trendspider:\s*\{\s*id:\s*")[^"]+"/, `$1${bad}"`) });
    assert.equal(r.status, 1); assert.match(r.stderr, /must be "tradingaihub"/);
  }
});

test("href gate: _go=tradingaihub passes, retired id or other _go fails the build", { skip: !hasDist && "needs npm run build" }, () => {
  const label = JSON.parse(fs.readFileSync(path.join(ROOT, "src/i18n/en.json"), "utf8")).partner.label;
  const ok = sandbox({ withDist: true, page: link("tradingaihub").replace("PARTNER", label) });
  assert.equal(ok.status, 0, ok.stderr); assert.match(ok.stdout, /TrendSpider links: \d+ ok .*0 bad/);
  for (const go of [OLD, "someone", "tradingaihub&amp;_go=x"]) {
    const r = sandbox({ withDist: true, page: link(go).replace("PARTNER", label) });
    assert.equal(r.status, 1, go); assert.match(r.stderr, /BAD TrendSpider link/);
  }
});
