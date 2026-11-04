import test from "node:test";
import assert from "node:assert/strict";
import { findNames, ALLOW } from "../scripts/check_names.mjs";

const N = "\x4ciran", S = "\x53egal";
test("name guard: catches the name in Latin (any case), Hebrew and Arabic", () => {
  assert.equal(findNames(`by ${N} ${S}`).length, 2);
  assert.equal(findNames(`${N.toUpperCase()} / ${N.toLowerCase()}@gmail.com`).length, 2);
  assert.equal(findNames("\u05dc\u05d9\u05e8\u05df \u05e1\u05d2\u05dc").length, 2);
  assert.equal(findNames("\u0644\u064a\u0631\u0627\u0646").length, 1);
});
test("name guard: brand text, Hebrew false positives and allowlisted ids pass", () => {
  assert.deepEqual(findNames("TradingAIHub team · hello@tradingaihub.com"), []);
  assert.deepEqual(findNames("\u05dc\u05d9\u05e8\u05d5\u05e7"), []); // Hebrew 'to green'
  assert.deepEqual(findNames(`https://trendspider.com/?_go=${ALLOW[0]}`), []);
  assert.equal(findNames(`${ALLOW[0]} and ${N}`).length, 1);
});
