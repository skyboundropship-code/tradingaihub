#!/usr/bin/env python3
"""Mutation suite for scripts/verify.py (PR #18). Each mutation is applied to a TEMP COPY of verify.py and the unit
tests are run against it via VERIFY_PY (the repo is never modified). A mutation is "killed" when the tests fail.
Run: npm run test:mutate            (or: python3 scripts/tests/mutate_verify.py [name ...])
Exit status 0 only if every non-equivalent mutation is killed and every mutation applied."""
import os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "scripts", "verify.py")

# name: (exact text in verify.py, replacement)
M = {
    # --- QA round 1 survivors
    "metadata_follows_redirects": ('allow_redirects=False, headers={"Accept": "application/json"}', 'allow_redirects=True, headers={"Accept": "application/json"}'),
    "bearer_check_removed": ('if not wa.lower().startswith("bearer"): return False, "no Bearer challenge"', 'pass'),
    "403_accepted": ('    if r.status_code == 401:\n        ok, info', '    if r.status_code in (401, 403):\n        ok, info'),
    "cross_org_note_removed": ('if g and g.get("cross_org_redirect"):\n        v["issues"]', 'if False:\n        v["issues"]'),
    # --- QA round 2 survivors / gaps
    "b_no_retry": ('for attempt in (1, 2):', 'for attempt in (1,):'),
    "b_retry_4xx_too": ('r.status_code < 500: return _Meta', 'r.status_code < 400: return _Meta'),
    "max_body_off": ('MAX_BODY = 64 * 1024', 'MAX_BODY = 1 << 30'),
    "jsonrpc_result_ignored": ('and ("result" in j or "error" in j)', ''),
    "recheck_off": ('    recheck_demotions(todo, fresh, current)\n', ''),
    "slowhdr_unbounded": ('    done, r = _bounded(work, deadline)\n', '    done, r = True, (lambda: (lambda x: x)(work()))() if True else None\n'),
    "loop_deadline_off": ('if stop.is_set() or time.monotonic() - t0 > deadline: raise', 'if False: raise'),
    # --- round 2 blocker 1: URL parser differential
    "backslash_allowed": ('if "\\\\" in u or "@" in u or', 'if "@" in u or'),
    "at_allowed": ('if "\\\\" in u or "@" in u or', 'if "\\\\" in u or'),
    "pct_encoded_allowed": (' or re.search(r"%(5c|40)", u, re.I)', ''),
    "userinfo_allowed": ('    if p.username is not None or p.password is not None: return "URL contains userinfo"\n', ''),
    "md_url_problem_skipped": ('    bad = url_problem(md_url)\n    if bad: return False', '    bad = None\n    if bad: return False'),
    "resource_url_problem_skipped": ('    bad = url_problem(res)\n    if bad: return False', '    bad = None\n    if bad: return False'),
    "endpoint_url_problem_skipped": ('    bad = url_problem(url)\n    if bad: return link(', '    bad = None\n    if bad: return link('),
    "req_url_problem_skipped": ('    bad = url_problem(url)\n    if bad: return UnsafeURL(bad), b""', '    bad = None\n    if bad: return UnsafeURL(bad), b""'),
    "prepared_target_unchecked": ('if _target(prep.url) != _validated(url): return UnsafeURL', 'if False: return UnsafeURL'),
    # --- round 1 rules
    "cross_org_status_ignored": ('(gated or cross) else status', 'gated else status'),
    "cross_org_link_rewritten": ('and not g.get("cross_org_redirect"): t["repo"]', ': t["repo"]'),
    "exact_host_dropped": ('if md_host != ep_host and md_host not in', 'if False and md_host not in'),
    "two_label_host": ('ep_host = _host(endpoint)', 'ep_host = ".".join(_host(endpoint).split(".")[-2:]); md_host = ".".join(md_host.split(".")[-2:])'),
    "https_check_removed": ('if mp.scheme != "https" or not md_host', 'if not md_host'),
    "non200_accepted": ('if r.status_code != 200: return False, f"metadata answered', 'if r.status_code >= 400: return False, f"metadata answered'),
    "naive_startswith": ('return ep == rp or ep.startswith(rp + "/")', 'return ep.startswith(rp)'),
    "origin_ignored": ('same = _origin(res) == _origin(endpoint) and', 'same = '),
    "resource_valueerror_uncaught": ('    except ValueError: return False, f"metadata resource', '    except ZeroDivisionError: return False, f"metadata resource'),
    "as_check_removed": ('if not isinstance(au, list) or not any(', 'if False and not any('),
    "blank_as_ok": ('any(isinstance(x, str) and x.strip() for x in au)', 'len(au) > 0'),
    "post_2xx_any_body_ok": ('if done(r, body) and not _challenge(r): return', 'if True: return'),
    "post_challenge_ok": ('if done(r, body) and not _challenge(r): return', 'if done(r, body): return'),
    "post_redirect_ok": ('        return link(url, r.status_code, "gated", method="POST", why=f"redirects to', '        return link(url, r.status_code, "ok", method="POST", why=f"redirects to'),
    "post_follows_redirects": ('    allow = kw.pop("allow_redirects", False)', '    allow = kw.pop("allow_redirects", True)'),
    "get_any_ctype_ok": ('if "text/event-stream" in gct and sse_ok(g, gb) and not _challenge(g):', 'if True:'),
    "alive_retry_challenge_ok": ('            if _challenge(r2):\n', '            if False:\n'),
    "no_shared_budget": ('    end = time.monotonic() + DEADLINE  # one budget', '    end = time.monotonic() + 10 * DEADLINE  # one budget'),
    "timeout_is_error": ('if isinstance(r, Timeout): return link(url, "Timeout", "gated"', 'if isinstance(r, Timeout): return link(url, "Timeout", "error"'),
    "timeout_note_misleading": ('"Timeout": "timeout", ', ''),
    "get_unbounded": ('done, r = _bounded(lambda: S.get(url, timeout=20, allow_redirects=True, **kw), GET_DEADLINE)', 'done, r = True, S.get(url, timeout=20, allow_redirects=True, **kw)'),
    "safe_verify_reraises": ('    if done and not isinstance(v, BaseException): return v\n', '    if done and isinstance(v, BaseException): raise v\n    if done: return v\n'),
    "safe_verify_uncapped": ('done, v = _bounded(lambda: verify(t), TOOL_DEADLINE)', 'done, v = _bounded(lambda: verify(t), 10**6)'),
    "no_recheck": ('if again:\n        with', 'if False:\n        with'),
    "jsonrpc_id_ignored": ('j.get("id") == 1 and', ''),
    # --- QA #18 nits (follow-up PR)
    "tls_timeout_is_error": ('    if isinstance(r, requests.exceptions.Timeout): return Timeout(', '    if False: return Timeout('),
    "deadline_unrounded": ('return f"{round(max(x, 0), 1):g}s"', 'return f"{x}s"'),
    "whitespace_check_after_at": ('    if any(ord(c) <= 0x20 or ord(c) == 0x7f for c in u): return "URL contains whitespace or control characters"\n    if "\\\\" in u or "@" in u or re.search(r"%(5c|40)", u, re.I): return "URL contains a backslash or \'@\' (userinfo is not allowed)"\n',
                                  '    if "\\\\" in u or "@" in u or re.search(r"%(5c|40)", u, re.I): return "URL contains a backslash or \'@\' (userinfo is not allowed)"\n    if any(ord(c) <= 0x20 or ord(c) == 0x7f for c in u): return "URL contains whitespace or control characters"\n'),
}
# Mutations no test can kill because another guard already enforces the same behaviour (documented, not counted).
EQUIVALENT = {
    "loop_deadline_off": "the worker join (_bounded) already enforces the wall-clock deadline for the body loop",
    "userinfo_allowed": "userinfo always needs an '@' in the authority, which url_problem already refuses anywhere in the URL",
    "resource_valueerror_uncaught": "url_problem(res) runs first and already refuses every URL urlsplit/.port reject (belt and braces)",
}

def run(name):
    a, b = M[name]
    src = open(SRC).read()
    if a not in src: return name, "NOT-APPLIED"
    with tempfile.NamedTemporaryFile("w", suffix="_verify.py", delete=False) as f:
        f.write(src.replace(a, b, 1)); path = f.name
    try:
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_verify.py"], cwd=ROOT,
                           env={**os.environ, "VERIFY_PY": path}, capture_output=True, text=True, timeout=240)
        return name, "KILLED" if r.returncode else "SURVIVED"
    except subprocess.TimeoutExpired:
        return name, "KILLED (timeout)"
    finally:
        os.unlink(path)

def main():
    names = sys.argv[1:] or list(M)
    with ThreadPoolExecutor(int(os.environ.get("MUTATE_JOBS", "4"))) as ex: res = dict(ex.map(run, names))
    for n in names:
        tag = f"  (equivalent: {EQUIVALENT[n]})" if n in EQUIVALENT and res[n] == "SURVIVED" else ""
        print(f"{n:30} {res[n]}{tag}")
    killed = sum(v.startswith("KILLED") for v in res.values())
    bad = [n for n, v in res.items() if v == "NOT-APPLIED" or (v == "SURVIVED" and n not in EQUIVALENT)]
    print(f"{killed}/{len(res)} killed; {sum(v == 'SURVIVED' and n in EQUIVALENT for n, v in res.items())} equivalent survivors; "
          f"{len(bad)} real survivors/not applied{': ' + ', '.join(bad) if bad else ''}")
    sys.exit(1 if bad else 0)

if __name__ == "__main__": main()
