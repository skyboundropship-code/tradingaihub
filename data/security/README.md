# Static security scan results

`python3 scripts/security_scan.py` writes one JSON file per tool here (plus `summary.json`).

The scanner is read-only. It never installs, imports, or runs third-party tool code. It reads repository files through the GitHub API / raw contents, and package metadata from the npm and PyPI registries and OSV.dev.

Results are informational only. They do not change which tools are listed or built. Per-tool JSON files are gitignored so a review label is not published with the site.

## Schema

```json
{
  "id": "example-mcp",
  "name": "Example MCP",
  "status": "clean",
  "date": "2026-11-10",
  "repo": "https://github.com/example/example-mcp",
  "commit": "<tree sha>",
  "findings": [
    {
      "check": "install-scripts",
      "file": "package.json",
      "line": 12,
      "detail": "short description of what was observed",
      "severity": "info"
    }
  ],
  "files_scanned": 0,
  "packages": {},
  "notes": []
}
```

`status` is `clean`, `concerns`, or `malicious`, derived from the highest finding severity (`malicious` → `malicious`; `high` or `medium` → `concerns`; otherwise `clean`).

Checks: `install-scripts`, `curl-pipe`, `obfuscation`, `secret-exfil`, `typosquat`, `osv`, `repo-mismatch`, `publisher-mismatch`, `permissions`, `repo`.

Run a subset with `--only=id1,id2`. Write somewhere else with `--out-dir=DIR`. `--dry-run` prints a summary and writes nothing.
