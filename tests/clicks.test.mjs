// npm run test:functions — scripts/clicks.mjs (no network).
import test from "node:test";
import assert from "node:assert/strict";
import { buildQuery, rowsToMap, explainError, WINDOWS } from "../scripts/clicks.mjs";

test("queries cover 1/7/30 days, exclude bots and QA, and group by affiliate or tool", () => {
  assert.deepEqual(WINDOWS, [1, 7, 30]);
  const q = buildQuery("tah_clicks", "affiliate", 7);
  assert.match(q, /FROM tah_clicks /); assert.match(q, /INTERVAL '7' DAY/); assert.match(q, /blob8 = '0'/); assert.match(q, /SELECT blob2 AS k/);
  assert.match(buildQuery("tah_clicks", "tool", 1), /SELECT blob1 AS k/);
  assert.match(q, /SUM\(_sample_interval\)/);
});

test("buildQuery rejects injection and bad args", () => {
  assert.throws(() => buildQuery("x; DROP", "tool", 1));
  assert.throws(() => buildQuery("tah_clicks", "blob9", 1));
  assert.throws(() => buildQuery("tah_clicks", "tool", 0));
});

test("rowsToMap and auth errors", () => {
  assert.deepEqual(rowsToMap({ data: [{ k: "tradingview", n: "3" }, { k: "eodhd", n: 2 }] }), { tradingview: 3, eodhd: 2 });
  assert.deepEqual(rowsToMap({}), {});
  assert.match(explainError(200, "Authorization error"), /no Analytics Engine read permission/);
  assert.match(explainError(403, ""), /Account Analytics: Read/);
  assert.doesNotMatch(explainError(500, "x"), /Bearer/);
});
