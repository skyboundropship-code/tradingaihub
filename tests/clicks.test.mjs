// npm run test:functions — scripts/clicks.mjs aggregation (no wrangler, no network).
import test from "node:test";
import assert from "node:assert/strict";
import { aggregate, lastDays } from "../scripts/clicks.mjs";

test("aggregate sums counters by kind/tool/host/page/locale/day and skips junk", () => {
  const a = aggregate([
    { name: "click:2026-10-29:openbb:plain", value: JSON.stringify({ n: 3, hosts: { "github.com": 3 }, pages: { "/tools/openbb/": 3 }, locales: { en: 2, he: 1 } }) },
    { name: "click:2026-10-30:-:partner", value: { n: 2, hosts: { "tradingview.com": 2 }, pages: { "/": 2 }, locales: { en: 2 } } },
    { name: "click:2026-10-30:-:affiliate", value: "not json" },
    { name: "crl:abc", value: JSON.stringify({ n: 9, seen: [] }) },
    { name: "sub:a@b.c", value: "{}" },
  ]);
  assert.equal(a.total, 5);
  assert.deepEqual(a.byKind, { plain: 3, partner: 2 });
  assert.deepEqual(a.byDay, { "2026-10-29": 3, "2026-10-30": 2 });
  assert.deepEqual(a.byLocale, { en: 4, he: 1 });
  assert.equal(a.byTool["openbb (plain)"], 3);
});

test("lastDays returns N UTC dates ending today", () => {
  const s = lastDays(3, new Date("2026-10-30T01:00:00Z"));
  assert.deepEqual([...s], ["2026-10-30", "2026-10-29", "2026-10-28"]);
});
