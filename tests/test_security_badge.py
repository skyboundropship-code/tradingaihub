"""Every public security badge is for a clean, listed tool; no non-clean id is badged.

Source results default to /workspace/security-scan/results-full-r6 (override with
SECURITY_SCAN_RESULTS). After a build, the test also checks dist HTML when present.

Run: python3 -m unittest tests.test_security_badge
"""
from __future__ import annotations

import json
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "data" / "security-scan.json"
TOOLS = ROOT / "data" / "tools.json"
DEFAULT_RESULTS = Path(os.environ.get("SECURITY_SCAN_RESULTS", "/workspace/security-scan/results-full-r6"))
LANGS = ["en", "he", "es", "pt", "de", "fr", "ja", "ko", "zh", "hi", "tr", "ar", "ru"]
BADGE_MARK = "sec-badge"
CARD_MARK = "sec-card"
VT_HOST = "virustotal.com/gui/file/"


def _load(path: Path):
    return json.loads(path.read_text())


def _source_statuses(results_dir: Path) -> dict[str, str]:
    out = {}
    for path in results_dir.glob("*.json"):
        if path.name == "summary.json":
            continue
        data = json.loads(path.read_text())
        tid, status = data.get("id"), data.get("status")
        if tid and status:
            out[tid] = status
    return out


class SecurityBadgeData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public = _load(PUBLIC)
        cls.tools = {t["id"] for t in _load(TOOLS)}
        cls.badged = cls.public.get("tools") or {}

    def test_public_file_has_only_clean_listed_tools(self):
        self.assertTrue(self.badged, "security-scan.json has no tools")
        for tid, rec in self.badged.items():
            with self.subTest(tid=tid):
                self.assertIn(tid, self.tools, f"{tid} is badged but missing from tools.json")
                self.assertEqual(rec.get("status"), "clean")
                self.assertRegex(rec.get("date") or "", r"^\d{4}-\d{2}-\d{2}$")
                self.assertTrue(rec.get("scanner_commit"))
                self.assertIsNotNone(rec.get("rules_version"))
                self.assertNotIn("findings", rec)
                self.assertNotIn("notes", rec)
                if "vt" in rec:
                    self.assertRegex(rec["vt"], r"^[a-f0-9]{64}$")

    def test_matches_source_results(self):
        self.assertTrue(DEFAULT_RESULTS.is_dir(), f"source results not found: {DEFAULT_RESULTS}")
        statuses = _source_statuses(DEFAULT_RESULTS)
        self.assertTrue(statuses, "no per-tool results in the source directory")
        clean = {tid for tid, st in statuses.items() if st == "clean" and tid in self.tools}
        not_clean = {tid for tid, st in statuses.items() if st != "clean"}
        self.assertEqual(set(self.badged), clean)
        for tid in not_clean:
            self.assertNotIn(tid, self.badged, f"non-clean {tid} ({statuses[tid]}) is badged")
        self.assertNotIn("claude-code-trading-terminal", self.badged)
        self.assertEqual(len(self.badged), 79)

    def test_top_level_stamp(self):
        self.assertTrue(str(self.public.get("scanner_commit", "")).startswith("bce7a11"))
        self.assertEqual(str(self.public.get("rules_version")), "6")

    def test_api_status_values_unchanged(self):
        # Display copy changed; the API still exposes status=unconfirmed and status_label="Needs review".
        src = (ROOT / "src" / "lib" / "data.ts").read_text()
        self.assertIn('unconfirmed: { label: "Needs review", tone: "warn"', src)
        api = (ROOT / "src" / "lib" / "publicApi.ts").read_text()
        self.assertIn("status_label: STATUS[v.status]?.label ?? v.status", api)


class SecurityBadgeDist(unittest.TestCase):
    """If dist/ exists, badges appear only on clean tool pages and never on others."""

    @classmethod
    def setUpClass(cls):
        cls.dist = ROOT / "dist"
        cls.public = _load(PUBLIC)
        cls.tools = [t["id"] for t in _load(TOOLS)]
        cls.badged = set(cls.public.get("tools") or {})

    def test_html_badges_match_clean_set(self):
        if not self.dist.is_dir():
            self.skipTest("dist not built")
        missing_page = []
        extra = []
        absent = []
        vt_invented = []
        for lang in LANGS:
            pre = "" if lang == "en" else f"{lang}/"
            for tid in self.tools:
                page = self.dist / pre / "tools" / tid / "index.html"
                if not page.is_file():
                    missing_page.append(str(page.relative_to(self.dist)))
                    continue
                html = page.read_text()
                has_badge = BADGE_MARK in html
                has_card = CARD_MARK in html  # related-tool cards may appear on a concerns page
                if tid in self.badged:
                    if not has_badge:
                        absent.append(f"{pre}tools/{tid}")
                else:
                    if has_badge:
                        extra.append(f"{pre}tools/{tid}")
                if VT_HOST in html:
                    rec = self.public["tools"].get(tid) or {}
                    if not rec.get("vt"):
                        vt_invented.append(f"{pre}tools/{tid}")
            # methodology page exists and is RTL where required
            sec = self.dist / (f"{lang}/security/index.html" if lang != "en" else "security/index.html")
            self.assertTrue(sec.is_file(), f"missing methodology page for {lang}")
            shtml = sec.read_text()
            self.assertNotRegex(shtml, r'<a[^>]+href="https://www\.virustotal\.com/gui/file/[^"]+"')
            self.assertIn("bce7a11", shtml, f"{lang} /security/ missing scanner commit")
            self.assertIn("2026-11-10", shtml, f"{lang} /security/ missing scan date")
            # rules version 6 appears in the stamp; require it next to the word for "rules" via the full hash nearby
            self.assertRegex(shtml, r"bce7a11c941714db3fd7fd0ef935bcd2ad4bb327")
            if lang in ("he", "ar"):
                self.assertRegex(shtml, r'<html[^>]*dir="rtl"')
        self.assertEqual(missing_page, [], f"missing tool pages: {missing_page[:5]}")
        self.assertEqual(absent, [], f"clean tools missing a page badge: {absent[:5]}")
        self.assertEqual(extra, [], f"non-clean tools have a page badge: {extra[:5]}")
        self.assertEqual(vt_invented, [], f"invented VirusTotal links: {vt_invented[:5]}")

        # Badge title/aria and /security/ stamp include date, short commit and rules version.
        sample = next(iter(self.badged))
        page = (self.dist / "tools" / sample / "index.html").read_text()
        self.assertIn('class="sec-badge"', page)
        self.assertRegex(page, r'title="[^"]*2026-11-10[^"]*bce7a11[^"]*\b6\b')
        self.assertIn("2026-11-10", page)

        # Display-only: unconfirmed chips are muted, have no "!", and do not use the warning tone.
        # API status_label stays "Needs review" (checked in the public-api dump test).
        for tid in ("firefly-iii-api", "openbb", "mercury-mcp"):
            html = (self.dist / "tools" / tid / "index.html").read_text()
            self.assertRegex(html, r'class="badge muted"', f"{tid} missing muted chip")
            self.assertNotRegex(html, r'class="badge warn"[^>]*>!\s', f"{tid} still has a warning bang chip")
            self.assertIn("Link check pending", html)
            self.assertNotRegex(html, r">!\s*Link check pending")

        # Directory cards: a concerns tool must not carry a shield on listing pages
        # (home / tools index). Check the English tools index as a representative crawl.
        index = (self.dist / "tools" / "index.html")
        if index.is_file():
            html = index.read_text()
            # Each card is an <a class="card" href="/tools/{id}/"> ... </a>
            for tid in self.tools:
                m = re.search(rf'<a class="card" href="/tools/{re.escape(tid)}/"[^>]*>(.*?)</a>', html, re.S)
                if not m:
                    continue
                has = CARD_MARK in m.group(1)
                if tid in self.badged:
                    self.assertTrue(has, f"tools index card for clean {tid} has no shield")
                else:
                    self.assertFalse(has, f"tools index card for non-clean {tid} has a shield")


class BuildScriptRoundTrip(unittest.TestCase):
    def test_rebuild_matches_committed_file(self):
        if not DEFAULT_RESULTS.is_dir():
            self.skipTest("source results not found")
        import importlib.util
        spec = importlib.util.spec_from_file_location("build_security_json", ROOT / "scripts" / "build_security_json.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        listed = {t["id"] for t in _load(TOOLS)}
        rebuilt = mod.build(DEFAULT_RESULTS, listed)
        committed = _load(PUBLIC)
        self.assertEqual(rebuilt, committed)


if __name__ == "__main__":
    unittest.main()
