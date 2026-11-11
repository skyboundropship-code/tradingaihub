#!/usr/bin/env python3
"""Regenerate data/security-scan.json from a scanner results directory.

The public file lists only tools whose latest scan status is "clean". Each
entry has status, date, scanner_commit, rules_version, and an optional VirusTotal
file SHA-256 (`vt`) when one was recorded. Findings and non-clean statuses are
never written, so a later concerns result simply drops the tool (and its badge).

Wire this into the weekly job after the security-scanner PR (#38) merges.

Usage:
  python3 scripts/build_security_json.py /path/to/results-dir
  python3 scripts/build_security_json.py /path/to/results-dir -o data/security-scan.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "security-scan.json"
TOOLS_JSON = ROOT / "data" / "tools.json"
SHA256 = __import__("re").compile(r"^[a-fA-F0-9]{64}$")


def load_results(results_dir: Path) -> tuple[dict, dict]:
    summary = {}
    tools = {}
    for path in sorted(results_dir.glob("*.json")):
        data = json.loads(path.read_text())
        if path.name == "summary.json" or not isinstance(data, dict):
            if path.name == "summary.json":
                summary = data
            continue
        tid = data.get("id")
        if not tid or not data.get("status"):
            continue
        tools[tid] = data
    return summary, tools


def vt_of(entry: dict) -> str | None:
    for key in ("vt", "vt_sha256", "sha256", "file_sha256"):
        val = entry.get(key)
        if isinstance(val, str) and SHA256.match(val.strip()):
            return val.strip().lower()
    return None


def build(results_dir: Path, listed_ids: set[str]) -> dict:
    summary, raw = load_results(results_dir)
    top_commit = summary.get("scanner_commit") or next(
        (r.get("scanner_commit") for r in raw.values() if r.get("scanner_commit")), None
    )
    top_rules = summary.get("rules_version")
    if top_rules is None:
        top_rules = next((r.get("rules_version") for r in raw.values() if r.get("rules_version") is not None), None)
    if top_rules is not None:
        top_rules = str(top_rules)
    tools = {}
    for tid in sorted(raw):
        if tid not in listed_ids:
            continue
        entry = raw[tid]
        if entry.get("status") != "clean":
            continue
        date = entry.get("date")
        if not date or not isinstance(date, str):
            raise SystemExit(f"missing date for clean tool {tid}")
        commit = entry.get("scanner_commit") or top_commit
        rules = entry.get("rules_version")
        rules = str(rules) if rules is not None else top_rules
        if not commit or rules is None:
            raise SystemExit(f"missing scanner_commit or rules_version for {tid}")
        rec = {
            "status": "clean",
            "date": date,
            "scanner_commit": commit,
            "rules_version": str(rules),
        }
        vt = vt_of(entry)
        if vt:
            rec["vt"] = vt
        tools[tid] = rec
    out = {
        "scanner_commit": top_commit,
        "rules_version": top_rules,
        "tools": tools,
    }
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("results_dir", type=Path, help="Directory of per-tool scanner JSON plus summary.json")
    p.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT, help="Output path (default: data/security-scan.json)")
    args = p.parse_args(argv)
    results_dir = args.results_dir
    if not results_dir.is_dir():
        print(f"results dir not found: {results_dir}", file=sys.stderr)
        return 2
    listed = {t["id"] for t in json.loads(TOOLS_JSON.read_text())}
    data = build(results_dir, listed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    n = len(data["tools"])
    print(f"wrote {args.output} ({n} clean tools, scanner {data['scanner_commit']}, rules {data['rules_version']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
