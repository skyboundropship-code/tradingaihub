#!/usr/bin/env python3
"""Static security scanner for listed tools.

Never executes, installs, or imports third-party tool code. Reads files only via
the GitHub API / raw contents, npm and PyPI registry JSON, and the OSV.dev API.

Statuses are informational only: this script does not hide or un-list tools.

Run:  python3 scripts/security_scan.py
      python3 scripts/security_scan.py --only=id1,id2
      python3 scripts/security_scan.py --only=id1,id2 --out-dir=/tmp/sec --dry-run
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
import tomllib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urlparse, urlsplit, urlunparse

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "TradingAIHubSecurityScan/0.1 (static review; read-only)"}
TOKEN = os.environ.get("GITHUB_TOKEN")
NOW = dt.datetime.now(dt.timezone.utc)
S = requests.Session()
S.headers.update(UA)

CACHE_DIR = os.environ.get("SECURITY_SCAN_CACHE") or os.path.join(ROOT, ".cache", "security-scan")
DEFAULT_OUT = os.path.join(ROOT, "data", "security")
MAX_FILE_BYTES = 256 * 1024
MAX_FILES_DEFAULT = 150
TOOL_DEADLINE = 180.0
GET_DEADLINE = 25.0

# --- popular package names used only for typo-distance checks (static list; not fetched) -----
POPULAR_NPM = frozenset("""
react react-dom vue angular lodash underscore express axios webpack typescript
next jquery moment request chalk commander debug glob mkdirp cross-env dotenv
ws mocha jest eslint prettier electron nx prisma zod tailwindcss postcss sass
redux rxjs core-js classnames uuid yargs inquirer ora rimraf fs-extra minimist
semver colors node-fetch form-data body-parser cors helmet jsonwebtoken passport
mongoose mongodb redis ioredis graphql vite esbuild rollup parcel nodemon pm2
husky lint-staged styled-components three d3 ccxt web3 ethers viem bignumber.js
decimal.js date-fns dayjs luxon ramda immutable bluebird async npm yarn pnpm
lerna turbo ts-node webpack-dev-server webpack-cli mocha chai sinon nyc
@babel/core @types/node @types/react @apollo/client @solana/web3.js
bitcoinjs-lib bitcore-lib wagmi left-pad event-stream node-ipc
""".split())

POPULAR_PYPI = frozenset("""
pip setuptools wheel requests urllib3 certifi charset-normalizer idna chardet
numpy pandas scipy matplotlib pillow cryptography pyyaml click flask django
fastapi pydantic starlette uvicorn gunicorn sqlalchemy alembic psycopg2
psycopg2-binary redis celery boto3 botocore s3transfer google-auth grpcio
protobuf tensorflow torch scikit-learn lxml beautifulsoup4 bs4 httpx aiohttp
httpcore h11 sniffio anyio attrs packaging tomli typing-extensions
importlib-metadata zipp six pytz python-dateutil tzdata openpyxl xlrd tabulate
rich typer tqdm colorama pygments jinja2 markupsafe werkzeug itsdangerous
blinker pytest pytest-cov coverage mypy ruff black flake8 pylint isort ccxt
web3 eth-account eth-utils bitcoinlib python-bitcoinlib alpaca-py
alpaca-trade-api yfinance polygon-api-client fredapi pandas-datareader
backtrader vectorbt ib-insync python-binance pybit openai anthropic langchain
tiktoken pyopenssl paramiko fabric ansible tox nox hatch poetry twine build
virtualenv pipenv httpie scrapy notebook jupyterlab ipython sympy networkx
statsmodels seaborn plotly dash streamlit gradio
""".split())

# Registries / CDNs / local that are expected network destinations (not "hard-coded exfil").
REGISTRY_HOSTS = frozenset("""
github.com www.github.com api.github.com raw.githubusercontent.com
objects.githubusercontent.com ghcr.io npmjs.org registry.npmjs.org
www.npmjs.com registry.npmjs.com pypi.org files.pythonhosted.org
pypi.python.org test.pypi.org nodejs.org deb.nodesource.com
get.docker.com sh.rustup.rs static.rust-lang.org dl.google.com
packages.microsoft.com aka.ms repo.maven.apache.org
pypi.ngc.nvidia.com registry.yarnpkg.com cr.l5d.io quay.io
gcr.io registry.k8s.io docker.io registry-1.docker.io
cdn.jsdelivr.net unpkg.com cdnjs.cloudflare.com
localhost 127.0.0.1 0.0.0.0 ::1
""".split())

SKIP_DIR = frozenset("""
node_modules dist vendor vendors third_party third-party .git coverage
__pycache__ .venv venv site-packages bower_components .next out min umd
bundles generated .cache .tox .mypy_cache .pytest_cache build
""".split())

SKIP_SUFFIX = (
    ".min.js", ".min.css", ".map", ".lock", ".bin", ".wasm", ".png", ".jpg",
    ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".woff", ".woff2", ".ttf", ".eot",
    ".mp4", ".zip", ".gz", ".tgz", ".whl", ".egg", ".so", ".dylib", ".dll",
    ".exe", ".pyc", ".pyo", ".class", ".jar", ".o", ".a", ".rs.bk",
)
SKIP_NAMES = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json",
    "poetry.lock", "cargo.lock", "go.sum", "composer.lock", "uv.lock",
})
ALWAYS_NAMES = frozenset({
    "package.json", "pyproject.toml", "setup.py", "setup.cfg", "setup.cfg.toml",
    "dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml",
    "compose.yaml", "install.sh", "install.bash", "install.ps1", "bootstrap.sh",
    "makefile", "server.json", "smithery.yaml", "smithery.yml", "mcp.json",
    ".mcp.json", "requirements.txt",
})
SOURCE_EXT = frozenset({
    ".py", ".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx", ".sh", ".bash", ".zsh",
    ".ps1", ".go", ".rs", ".rb", ".php", ".json", ".toml", ".yml", ".yaml",
    ".cfg", ".ini",
})
INSTALL_HOOKS = (
    "preinstall", "install", "postinstall", "prepare", "prepublish",
    "prepublishOnly", "prepack", "postpack",
)
# prepare/husky and similar hooks that only run local tooling are expected.
BENIGN_HOOK = re.compile(
    r"^\s*(husky(?:\s+install)?|npm\s+run\s+build|tsc|echo\b.*|true|exit\s+0|"
    r"node-gyp\s+rebuild|prebuild-install|only-allow|simple-git-hooks|"
    r"npm\s+run\s+prepare|patch-package(?:\s+--error-on-fail)?)\s*$",
    re.I,
)

CURL_PIPE = re.compile(
    r"(curl|wget|invoke-webrequest|\biwr\b)\b[^\n|]{0,220}\|\s*(?:sudo\s+)?"
    r"(?:bash|sh|zsh|fish|python3?|pwsh|powershell|cmd|iex)\b",
    re.I,
)
BASH_FROM_CURL = re.compile(
    r"(?:bash|sh)\s+<\(\s*(curl|wget)\b|(?:bash|sh)\s+-c\s+[\"']?\$\(?(curl|wget)\b",
    re.I,
)
BINARY_DL = re.compile(
    r"(curl|wget|requests\.get|urllib\.request|fetch\(|httpx\.|aiohttp\.)"
    r"[^\n]{0,220}(\.exe\b|\.dmg\b|\.apk\b|\.msi\b|\.appimage\b|\.bat\b)",
    re.I,
)
EVAL_DECODE = re.compile(
    r"(?:eval|exec|Function|setTimeout|setInterval)\s*\(\s*"
    r"(?:atob|Buffer\.from|base64\.b64decode|codecs\.decode|unhexlify|"
    r"fromhex|base64decode|b64decode)",
    re.I,
)
EVAL_BUFFER = re.compile(r"(?:eval|exec|Function)\s*\(\s*Buffer\.from", re.I)
LONG_B64 = re.compile(r"[\"'][A-Za-z0-9+/]{200,}={0,2}[\"']")
LONG_HEX = re.compile(r"[\"'](?:0x)?[0-9a-fA-F]{400,}[\"']")
SECRET_PATHS = re.compile(
    r"(?:~/?\.ssh|(?:^|[\"'/])id_rsa(?:\b|\.)|id_ed25519|\.gnupg|"
    r"\.aws/credentials|wallet\.dat|login\.keychain|"
    r"Application Support/(?:Google/Chrome|Firefox)|"
    r"AppData\\(?:Roaming|Local)\\(?:Google\\Chrome|Mozilla)|"
    r"Cookies/Cookies|(?:Chrome|Chromium|Google)/[^\"'\\n]*Login Data|Keychain\.accts|"
    r"electrum/wallets|Solana/id\.json|\.bitcoin/wallet|"
    r"metamask|IndexedDB/nkbihfbeogae)",
    re.I,
)
SEED_ASK = re.compile(
    r"(enter|paste|provide|input|prompt(?:\s+for)?|type(?:\s+in)?|supply|"
    r"ask(?:ing)?\s+for)\b.{0,60}\b(seed\s*phrase|mnemonic(?:\s+phrase)?|"
    r"recovery\s+phrase|wallet\s+private\s+key|private\s+key(?:\s+wif)?|"
    r"12[- ]word|24[- ]word|xprv|secret\s+recovery)",
    re.I,
)
HARDCODED_IP = re.compile(r"\b(?:https?://)?(\d{1,3}(?:\.\d{1,3}){3})(?::\d+)?\b")
HTTP_URL = re.compile(
    r"""(?:fetch|axios(?:\.\w+)?|requests\.(?:get|post|put|patch|delete|request)|"""
    r"""httpx\.(?:get|post|request)|urllib\.request|urlopen|ClientSession|"""
    r"""wget|curl)\s*\(\s*[Rr]?[fF]?[\"'](https?://[^\"']+)""",
    re.I,
)
PLAIN_URL = re.compile(r"https?://([A-Za-z0-9.-]+)(?::\d+)?", re.I)
TRADE_WORDS = re.compile(
    r"\b(place_order|submit_order|create_order|market_order|limit_order|"
    r"send_order|placeorder|submitorder|send_transaction|transfer_funds|"
    r"withdraw(?:al|s|_to)?|wire_transfer|send_crypto|broadcast_transaction|"
    r"sign_and_send|liquidate|close_all_positions|sendtransaction)\b",
    re.I,
)
WITHDRAW_WORDS = re.compile(
    r"\b(withdraw(?:al|s|_to)?|wire_transfer|send_crypto|transfer_funds|"
    r"send_transaction|broadcast_transaction|sign_and_send)\b",
    re.I,
)
CONFIRM_WORDS = re.compile(
    r"\b(confirm(?:ation)?|dry_run|dry-run|paper(?:_trading|_mode)?|"
    r"require_confirm|preview_only|user_approval|need_approval|"
    r"idempotency|require_otp|mfa|step_up|human_in_the_loop)\b",
    re.I,
)
OAUTH_BROAD = re.compile(
    r"\b(?:scope|scopes)\s*[=:]\s*[\"']([^\"']+)[\"']",
    re.I,
)
BROAD_SCOPE_TOKEN = re.compile(
    r"(^|[,\s])(\*|admin|full[_-]?access|full[_-]?control|write[_-]?all|"
    r"account:write|wallet:.*:send|repo\s*$|https://www\.googleapis\.com/auth/cloud-platform)"
    r"([,\s]|$)",
    re.I,
)
SETUP_CMDCLASS = re.compile(r"\bcmdclass\s*=", re.I)
SETUP_CUSTOM_INSTALL = re.compile(
    r"class\s+\w+\s*\([^)]*\binstall\b[^)]*\)|"
    r"from\s+setuptools\.command\.install\s+import|"
    r"from\s+distutils\.command\.install\s+import",
    re.I,
)

PRIV_NET_PREFIXES = (
    "10.", "192.168.", "127.", "0.", "255.", "169.254.",
)


def _bounded(fn, deadline):
    box = {}

    def run():
        try:
            box["v"] = fn()
        except BaseException as e:  # noqa: BLE001 — isolate one tool
            box["v"] = e

    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(max(deadline, 0))
    return ("v" in box), box.get("v")


def get(url, **kw):
    try:
        return S.get(url, timeout=20, allow_redirects=True, **kw)
    except requests.RequestException as e:
        return e


# ------------------------------- cache + API accounting ---------------------------------------
_C_LOCK = threading.Lock()
API_CALLS = Counter()


def _cache_path(key):
    h = hashlib.sha256(key.encode()).hexdigest()
    return os.path.join(CACHE_DIR, h[:2], h + ".cache")


def cache_get(key):
    p = _cache_path(key)
    try:
        with open(p) as f:
            wrap = json.load(f)
        return wrap.get("value")
    except (OSError, ValueError):
        return None


def cache_set(key, value):
    p = _cache_path(key)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"value": value}, f)
    os.replace(tmp, p)


def counted(kind):
    with _C_LOCK:
        API_CALLS[kind] += 1


def github_headers():
    h = dict(UA)
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
        h["Accept"] = "application/vnd.github+json"
        h["X-GitHub-Api-Version"] = "2022-11-28"
    return h


def _maybe_sleep_rate(resp):
    if resp is None or isinstance(resp, Exception):
        return
    rem = resp.headers.get("X-RateLimit-Remaining")
    if rem is not None and rem.isdigit() and int(rem) <= 20:
        reset = resp.headers.get("X-RateLimit-Reset")
        if reset and reset.isdigit():
            wait = min(max(int(reset) - int(time.time()) + 1, 0), 90)
            if wait:
                time.sleep(wait)
    if resp.status_code == 429:
        ra = resp.headers.get("Retry-After")
        wait = int(ra) if ra and ra.isdigit() else 15
        time.sleep(min(wait, 60))


def gh_api(path, raw=False):
    """GitHub REST GET. Uses GITHUB_TOKEN, else the logged-in `gh` CLI. Cached."""
    key = f"gh:{path}:raw={raw}"
    hit = cache_get(key)
    if hit is not None:
        return hit
    url = f"https://api.github.com/{path.lstrip('/')}"
    if TOKEN:
        counted("github")
        r = get(url, headers=github_headers())
        _maybe_sleep_rate(r if not isinstance(r, Exception) else None)
        if isinstance(r, Exception) or r.status_code != 200:
            cache_set(key, None)
            return None
        val = r.content.decode("utf-8", "replace") if raw else r.json()
        cache_set(key, val)
        return val
    if shutil.which("gh"):
        counted("github")
        args = ["gh", "api", path]
        if raw:
            args += ["-H", "Accept: application/vnd.github.raw"]
        try:
            p = shutil.which("gh") and __import__("subprocess").run(
                args, capture_output=True, text=True, timeout=45
            )
        except Exception:
            cache_set(key, None)
            return None
        if p.returncode != 0:
            cache_set(key, None)
            return None
        val = p.stdout if raw else json.loads(p.stdout) if p.stdout else None
        cache_set(key, val)
        return val
    return None


def parse_repo(url):
    """https://github.com/o/r[/tree/<branch>/<sub/path>] -> (owner, repo, branch, sub) or None."""
    if not url:
        return None
    m = re.match(
        r"https://github.com/([^/]+)/([^/#?]+)(?:/tree/([^/]+)/([^#?]+?))?/?$",
        url.rstrip("/"),
    )
    if not m:
        return None
    return m.group(1), m.group(2).removesuffix(".git"), m.group(3), m.group(4)


def raw_file(owner, repo, sha, path):
    """Fetch a blob as text. Prefer raw.githubusercontent.com (not REST quota); cache by sha+path."""
    key = f"raw:{owner}/{repo}/{sha}/{path}"
    hit = cache_get(key)
    if hit is not None:
        return hit
    enc = "/".join(quote(p, safe="") for p in path.split("/"))
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{sha}/{enc}"
    counted("raw")
    r = get(url)
    if not isinstance(r, Exception) and r.status_code == 200:
        # reject obviously-binary
        if b"\0" in r.content[:4096]:
            cache_set(key, "")
            return ""
        text = r.content[:MAX_FILE_BYTES].decode("utf-8", "replace")
        cache_set(key, text)
        return text
    # fallback through the API
    api_path = f"repos/{owner}/{repo}/contents/{enc}?ref={sha}"
    body = gh_api(api_path, raw=True)
    if isinstance(body, str):
        cache_set(key, body[:MAX_FILE_BYTES])
        return body[:MAX_FILE_BYTES]
    cache_set(key, "")
    return ""


def npm_registry(name):
    key = f"npm:{name}"
    hit = cache_get(key)
    if hit is not None:
        return hit
    counted("npm")
    r = get(f"https://registry.npmjs.org/{name.replace('/', '%2F')}")
    if isinstance(r, Exception) or r.status_code != 200:
        cache_set(key, None)
        return None
    try:
        j = r.json()
    except ValueError:
        cache_set(key, None)
        return None
    cache_set(key, j)
    return j


def pypi_registry(name):
    key = f"pypi:{name}"
    hit = cache_get(key)
    if hit is not None:
        return hit
    counted("pypi")
    r = get(f"https://pypi.org/pypi/{name}/json")
    if isinstance(r, Exception) or r.status_code != 200:
        cache_set(key, None)
        return None
    try:
        j = r.json()
    except ValueError:
        cache_set(key, None)
        return None
    cache_set(key, j)
    return j


def osv_query(ecosystem, name, version=None):
    key = f"osv:{ecosystem}:{name}:{version or ''}"
    hit = cache_get(key)
    if hit is not None:
        return hit
    body = {"package": {"name": name, "ecosystem": ecosystem}}
    if version:
        body["version"] = version
    counted("osv")
    try:
        r = S.post("https://api.osv.dev/v1/query", json=body, timeout=20)
    except requests.RequestException:
        cache_set(key, [])
        return []
    if r.status_code != 200:
        cache_set(key, [])
        return []
    try:
        vulns = r.json().get("vulns") or []
    except ValueError:
        vulns = []
    cache_set(key, vulns)
    return vulns


# ------------------------------------ helpers -------------------------------------------------
def finding(check, detail, severity, file=None, line=None):
    return {
        "check": check,
        "file": file,
        "line": line,
        "detail": detail,
        "severity": severity,
    }


def line_no(text, idx):
    return text[:idx].count("\n") + 1 if idx is not None else None


def first_match_line(text, regex):
    m = regex.search(text)
    return (m, line_no(text, m.start()) if m else None)


def skip_path(path):
    parts = path.replace("\\", "/").split("/")
    name = parts[-1].lower()
    if name in SKIP_NAMES:
        return True
    if any(p.lower() in SKIP_DIR for p in parts[:-1]):
        return True
    if name.endswith(SKIP_SUFFIX):
        return True
    return False


def is_vendorish(path):
    """Bundles we skip for obfuscation / long-line checks (keep them for install hooks)."""
    p = path.replace("\\", "/").lower()
    parts = p.split("/")
    if any(x in parts for x in ("dist", "vendor", "vendors", "umd", "bundles", "min", "generated")):
        return True
    if p.endswith(".min.js") or p.endswith(".min.css") or ".bundle." in p or ".min." in parts[-1]:
        return True
    return False


def interesting(path, subpath=None):
    if skip_path(path):
        return False
    if subpath and not path.replace("\\", "/").startswith(subpath.rstrip("/") + "/") and path != subpath.rstrip("/"):
        # still allow root packging files
        if os.path.basename(path).lower() not in ALWAYS_NAMES and path.lower() not in (
            "dockerfile", "makefile", "requirements.txt",
        ):
            return False
    base = os.path.basename(path).lower()
    if base in ALWAYS_NAMES or base.startswith("dockerfile") or base.startswith("requirements"):
        return True
    if base in {"readme.md", "readme.rst", "install.md"}:
        return True
    ext = os.path.splitext(base)[1]
    return ext in SOURCE_EXT


def is_test_path(path):
    pth = path.replace("\\", "/").lower()
    parts = pth.split("/")
    if any(x in {"test", "tests", "__tests__", "spec", "specs", "fixtures", "mocks"} for x in parts):
        return True
    name = parts[-1]
    if name.startswith("test_") or name.endswith((".test.js", ".test.ts", ".test.mjs", ".spec.js", ".spec.ts")):
        return True
    if "/tests/record/" in pth or "/record/http/" in pth:
        return True
    return False


def is_example_path(path):
    pth = path.replace("\\", "/").lower()
    return any(x in pth.split("/") for x in ("examples", "example", "templates", "template", "benchmarks", "benchmark", "demos", "demo"))


def file_priority(path):
    base = os.path.basename(path).lower()
    pth = path.replace("\\", "/").lower()
    if is_test_path(pth):
        return 8
    if is_example_path(pth):
        return 6
    if base in ALWAYS_NAMES or base.startswith("dockerfile"):
        return 0
    parts = pth.split("/")
    if any(k in parts for k in ("install", "setup", "wallet", "auth", "mcp")):
        return 1
    if pth.startswith(("src/", "lib/", "server/", "scripts/", "app/")):
        return 2
    return 3


def levenshtein(a, b, limit=2):
    """Edit distance with early exit when it will exceed `limit`."""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        row_min = i
        for j, cb in enumerate(b, 1):
            ins = cur[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (ca != cb)
            v = min(ins, delete, sub)
            cur.append(v)
            if v < row_min:
                row_min = v
        if row_min > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def typo_of(name, popular):
    """Return (popular_name, distance) if `name` looks like a typo of a popular package."""
    if not name or name in popular:
        return None
    # scoped npm: compare the name part, but @types/XYZ is not a typo of XYZ
    cmp_name = name
    if name.startswith("@") and "/" in name:
        scope, cmp_name = name.split("/", 1)
        if scope in {"@types", "@babel", "@angular", "@testing-library", "@solana", "@apollo"}:
            return None
    low = cmp_name.lower()
    if low in popular:
        return None
    # legitimate suffixes of a popular name (requests-oauthlib, lodash-es already in list)
    # and next-gen renames like httpx2 (pydantic's successor to httpx)
    for pop in popular:
        if low.startswith(pop + "-") or low.startswith(pop + "_") or low.startswith(pop + "."):
            return None
        if pop.startswith(low + "-") or pop.startswith(low + "_"):
            return None
        if re.fullmatch(re.escape(pop) + r"[v._-]?\d+", low):
            return None
    best = None
    for pop in popular:
        limit = 1 if len(pop) < 8 else 2
        if abs(len(low) - len(pop)) > limit:
            continue
        d = levenshtein(low, pop, limit=limit)
        if d == 0:
            return None
        if 0 < d <= limit and len(pop) >= 4:
            if best is None or d < best[1]:
                best = (pop, d)
            if d == 1:
                return best
    return best


def normalize_repo_url(u):
    if not u:
        return ""
    if isinstance(u, dict):
        u = u.get("url") or u.get("web") or ""
    u = str(u).strip()
    u = re.sub(r"^git\+", "", u)
    u = re.sub(r"^git://", "https://", u)
    u = re.sub(r"^ssh://git@", "https://", u)
    u = re.sub(r"^git@github\.com:", "https://github.com/", u)
    u = re.sub(r"\.git$", "", u)
    u = u.rstrip("/")
    p = urlsplit(u)
    if p.netloc.lower() == "github.com":
        parts = [x for x in p.path.split("/") if x]
        if len(parts) >= 2:
            return f"https://github.com/{parts[0]}/{parts[1].removesuffix('.git')}".lower()
    return u.lower()


def host_of(url):
    try:
        h = (urlsplit(url).hostname or "").lower().rstrip(".")
        return h
    except ValueError:
        return ""


def base_domain(host):
    if not host:
        return ""
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net", "gov", "ac"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def allowed_host(host, allow):
    if not host:
        return True
    h = host.lower().rstrip(".")
    if h in REGISTRY_HOSTS or h in allow:
        return True
    # subdomain of an allowed host or of a listed official domain
    for a in list(allow) + list(REGISTRY_HOSTS):
        if not a or re.match(r"^\d+\.\d+\.\d+\.\d+$", a):
            continue
        if h == a or h.endswith("." + a) or base_domain(h) == base_domain(a):
            return True
    return False


def private_or_local_ip(ip):
    if any(ip.startswith(p) for p in PRIV_NET_PREFIXES):
        return True
    if ip.startswith("172."):
        try:
            second = int(ip.split(".")[1])
            return 16 <= second <= 31
        except (ValueError, IndexError):
            return False
    return False


def status_of(findings):
    sev = {f["severity"] for f in findings}
    if "malicious" in sev:
        return "malicious"
    if sev & {"high", "medium"}:
        return "concerns"
    return "clean"


# ------------------------------------ per-file checks ----------------------------------------
def check_package_json(path, text, findings):
    try:
        j = json.loads(text)
    except ValueError:
        return None
    scripts = j.get("scripts") or {}
    if isinstance(scripts, dict):
        for hook in INSTALL_HOOKS:
            cmd = scripts.get(hook)
            if not cmd or not isinstance(cmd, str):
                continue
            if BENIGN_HOOK.match(cmd.strip()):
                continue
            sev = "high"
            detail = f"{hook} script: {cmd[:240]}"
            if CURL_PIPE.search(cmd) or BASH_FROM_CURL.search(cmd):
                sev = "malicious" if re.search(r"\b(\d{1,3}\.){3}\d{1,3}\b|pastebin|bit\.ly|raw\.githubusercontent\.com/.*/(mal|tmp)", cmd, re.I) else "high"
            elif re.search(r"\b(curl|wget|iwr|invoke-webrequest|powershell|chmod\s+\+x)\b", cmd, re.I):
                sev = "high"
            elif re.search(r"\b(eval|Function\(|node\s+-e)\b", cmd):
                sev = "high"
            else:
                # unusual but maybe a local build — medium so a reviewer sees it
                sev = "medium"
            findings.append(finding("install-scripts", detail, sev, file=path))
    return j


def check_setup_py(path, text, findings):
    if SETUP_CMDCLASS.search(text) or SETUP_CUSTOM_INSTALL.search(text):
        m, ln = first_match_line(text, SETUP_CMDCLASS if SETUP_CMDCLASS.search(text) else SETUP_CUSTOM_INSTALL)
        findings.append(finding(
            "install-scripts",
            "setup.py declares cmdclass or a custom install command (review what it runs)",
            "medium", file=path, line=ln,
        ))


def check_shell_and_docker(path, text, findings):
    for rx, label in ((CURL_PIPE, "pipe-to-shell download"), (BASH_FROM_CURL, "shell process substitution from curl/wget")):
        for m in rx.finditer(text):
            snippet = text[m.start():m.start() + 180].splitlines()[0]
            # official installers from known hosts stay medium; unknown/IP go high
            host_m = PLAIN_URL.search(snippet)
            host = (host_m.group(1).lower() if host_m else "")
            sev = "low" if allowed_host(host, set()) else "high"
            findings.append(finding("curl-pipe", f"{label}: {snippet[:180]}", sev, file=path, line=line_no(text, m.start())))
    for m in BINARY_DL.finditer(text):
        snippet = text[m.start():m.start() + 180].splitlines()[0]
        findings.append(finding(
            "curl-pipe", f"download of a binary/executable: {snippet[:180]}",
            "medium", file=path, line=line_no(text, m.start()),
        ))


def check_obfuscation(path, text, findings):
    if is_vendorish(path) or is_test_path(path):
        return
    base = os.path.basename(path).lower()
    # OpenAPI specs, recorded HTTP fixtures and giant JSON blobs are not obfuscated source
    if base.endswith((".yaml", ".yml", ".json", ".csv", ".md")):
        return
    for rx, label, sev in (
        (EVAL_DECODE, "eval/exec of decoded data", "high"),
        (EVAL_BUFFER, "eval/exec of Buffer.from payload", "high"),
    ):
        for m in rx.finditer(text):
            snippet = text[m.start():m.start() + 160].splitlines()[0]
            findings.append(finding("obfuscation", f"{label}: {snippet[:160]}", sev, file=path, line=line_no(text, m.start())))
    # long blobs only if they also sit near a decode, or are extremely long
    for m in LONG_B64.finditer(text):
        blob = m.group(0)
        nearby = text[max(0, m.start() - 80):m.end() + 80]
        if re.search(r"atob|b64decode|base64|Buffer\.from|eval|exec", nearby, re.I) or len(blob) >= 800:
            findings.append(finding(
                "obfuscation", f"long base64 blob ({len(blob)} chars) in source",
                "medium" if len(blob) < 800 else "high",
                file=path, line=line_no(text, m.start()),
            ))
    for m in LONG_HEX.finditer(text):
        findings.append(finding(
            "obfuscation", f"long hex blob ({len(m.group(0))} chars) in source",
            "medium", file=path, line=line_no(text, m.start()),
        ))
    # very long minified-looking lines (not data URIs / single-string JSON)
    for i, line in enumerate(text.splitlines(), 1):
        if len(line) < 500:
            continue
        if line.lstrip().startswith(("//", "#", "*", "/*")):
            continue
        spaces = line.count(" ") + line.count("\t")
        if spaces / max(len(line), 1) < 0.04 and re.search(r"[{;}()]", line):
            findings.append(finding(
                "obfuscation",
                f"very long minified line ({len(line)} chars, little whitespace)",
                "low", file=path, line=i,
            ))
            break  # one per file is enough


def suspicious_host(host):
    """Hosts that are unusual as a hard-coded destination in a finance tool."""
    if not host:
        return False
    h = host.lower().rstrip(".")
    if re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", h) and not private_or_local_ip(h):
        return True
    suffixes = (
        "pastebin.com", "pastebin.pl", "bit.ly", "tinyurl.com", "t.ly", "cutt.ly",
        "discord.com", "discordapp.com", "webhook.site", "ngrok.io", "ngrok.app",
        "trycloudflare.com", "requestbin.com", "pipedream.net",
        "telegram.org", "t.me",
    )
    return any(h == s or h.endswith("." + s) for s in suffixes)


def check_secrets_and_network(path, text, findings, allow_hosts):
    secret_hits = list(SECRET_PATHS.finditer(text))
    for m in secret_hits:
        snippet = text[m.start():m.start() + 140].splitlines()[0]
        findings.append(finding(
            "secret-exfil",
            f"reads a sensitive path or store: {snippet[:140]}",
            "medium", file=path, line=line_no(text, m.start()),
        ))
    for m in SEED_ASK.finditer(text):
        snippet = text[m.start():m.start() + 160].splitlines()[0]
        window = text[max(0, m.start() - 50):m.end() + 50]
        if re.search(r"\b(never|do not|don't|dont|warning|avoid|not\s+ask)\b", window, re.I):
            continue
        findings.append(finding(
            "permissions",
            f"asks for a seed phrase or wallet private key: {snippet[:160]}",
            "high", file=path, line=line_no(text, m.start()),
        ))
    ext_hosts = []
    for m in HTTP_URL.finditer(text):
        url = m.group(1)
        h = host_of(url)
        if not h:
            continue
        if allowed_host(h, allow_hosts):
            continue
        if secret_hits or suspicious_host(h):
            ext_hosts.append((h, url, line_no(text, m.start())))
    for m in HARDCODED_IP.finditer(text):
        ip = m.group(1)
        if private_or_local_ip(ip):
            continue
        start_i = max(0, m.start() - 8)
        ctx = text[start_i:m.end() + 8]
        if "http" not in ctx.lower() and "://" not in ctx and not re.search(r"\b(?:connect|socket|host)\b", ctx, re.I):
            continue
        if secret_hits or suspicious_host(ip):
            ext_hosts.append((ip, m.group(0), line_no(text, m.start())))
    for h, url, ln in ext_hosts:
        if secret_hits:
            sev, detail = "malicious", f"sensitive-path read combined with hard-coded host {h} ({url[:160]})"
        else:
            sev, detail = "high", f"suspicious hard-coded network destination {h} ({url[:160]})"
        findings.append(finding("secret-exfil", detail, sev, file=path, line=ln))




def check_permissions(path, text, findings, official, tool_type=None, category=None):
    # MCP live-trading / withdrawal tools: only look at definitions, and only on
    # MCP servers or broker/crypto tools. Accounting "withdrawal" transaction types are ignored.
    if is_vendorish(path) or is_test_path(path):
        return
    if tool_type != "mcp" and category not in {"trading-brokers", "crypto"}:
        # still flag broad OAuth scopes everywhere
        for m in OAUTH_BROAD.finditer(text):
            scopes = m.group(1)
            if BROAD_SCOPE_TOKEN.search(scopes):
                findings.append(finding(
                    "permissions",
                    f"broad OAuth scope: {scopes[:200]}",
                    "medium", file=path, line=line_no(text, m.start()),
                ))
        return
    confirm_present = bool(CONFIRM_WORDS.search(text))
    # function / exported method / MCP tool name, not an incidental mention
    defn = re.compile(
        r"""(?:async\s+)?(?:def|function)\s+(place_order|submit_order|create_order|market_order|limit_order|"""
        r"""send_order|placeOrder|submitOrder|send_transaction|sendTransaction|transfer_funds|transferFunds|"""
        r"""withdraw(?:_to|_funds)?|wire_transfer|send_crypto|broadcast_transaction|sign_and_send|"""
        r"""liquidate|close_position|close_all_positions)\b"""
        r"""|(?:(?:["']name["']|\bname)\s*[:=]\s*["']|server\.tool\(\s*["']|tool\(\s*["'])"""
        r"""(place_order|submit_order|create_order|market_order|limit_order|send_order|placeOrder|"""
        r"""submitOrder|send_transaction|sendTransaction|transfer_funds|transferFunds|withdraw(?:_to|_funds)?|"""
        r"""wire_transfer|send_crypto|broadcast_transaction|sign_and_send|liquidate|close_position|close_all_positions)["']""",
        re.I,
    )
    hits = list(defn.finditer(text))
    if not hits:
        for m in OAUTH_BROAD.finditer(text):
            scopes = m.group(1)
            if BROAD_SCOPE_TOKEN.search(scopes):
                findings.append(finding(
                    "permissions",
                    f"broad OAuth scope: {scopes[:200]}",
                    "medium", file=path, line=line_no(text, m.start()),
                ))
        return
    names = [(m.group(1) or m.group(2) or "").lower() for m in hits]
    withdrawish = any(re.search(r"withdraw|transfer_funds|send_crypto|send_transaction|sendtransaction|broadcast_transaction|sign_and_send|wire_transfer", n) for n in names)
    snippet = text[hits[0].start():hits[0].start() + 140].splitlines()[0]
    if withdrawish and not confirm_present:
        findings.append(finding(
            "permissions",
            f"enables withdrawal/transfer with no confirm/scope setting visible in this file: {snippet[:140]}",
            "high" if not official else "medium",
            file=path, line=line_no(text, hits[0].start()),
        ))
    elif not confirm_present:
        findings.append(finding(
            "permissions",
            f"enables live trading with no confirm/paper/scope setting visible in this file: {snippet[:140]}",
            "medium" if not official else "low",
            file=path, line=line_no(text, hits[0].start()),
        ))
    for m in OAUTH_BROAD.finditer(text):
        scopes = m.group(1)
        if BROAD_SCOPE_TOKEN.search(scopes):
            findings.append(finding(
                "permissions",
                f"broad OAuth scope: {scopes[:200]}",
                "medium", file=path, line=line_no(text, m.start()),
            ))


# ------------------------------------ package / OSV / typo ------------------------------------
def extract_npm_deps(pkg):
    names = []
    if not isinstance(pkg, dict):
        return names
    if pkg.get("name") and not pkg.get("private"):
        names.append(("self", pkg["name"], (pkg.get("version") if isinstance(pkg.get("version"), str) else None)))
    for field in ("dependencies", "optionalDependencies", "peerDependencies", "devDependencies"):
        block = pkg.get(field) or {}
        if isinstance(block, dict):
            for n, ver in block.items():
                if isinstance(n, str):
                    names.append((field, n, ver if isinstance(ver, str) else None))
    return names


def extract_pypi_deps(text, kind):
    names = []
    if kind == "pyproject":
        try:
            data = tomllib.loads(text)
        except Exception:
            return names
        proj = data.get("project") or {}
        n = proj.get("name")
        if n:
            names.append(("self", n, (proj.get("version") if isinstance(proj.get("version"), str) else None)))
        for dep in proj.get("dependencies") or []:
            if isinstance(dep, str) and dep.strip() and not dep.strip().startswith("#"):
                names.append(("dependencies", re.split(r"[\s<>=!~;\[]", dep.strip(), maxsplit=1)[0], None))
        opt = proj.get("optional-dependencies") or {}
        if isinstance(opt, dict):
            for lst in opt.values():
                for dep in lst or []:
                    if isinstance(dep, str) and dep.strip():
                        names.append(("optional", re.split(r"[\s<>=!~;\[]", dep.strip(), maxsplit=1)[0], None))
        poetry = (data.get("tool") or {}).get("poetry") or {}
        if poetry.get("name"):
            names.append(("self", poetry["name"], poetry.get("version") if isinstance(poetry.get("version"), str) else None))
        deps = poetry.get("dependencies") or {}
        if isinstance(deps, dict):
            for n in deps:
                if n != "python":
                    names.append(("dependencies", n, None))
    elif kind == "requirements":
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("-"):
                continue
            names.append(("requirements", re.split(r"[\s<>=!~;\[\]]", s, maxsplit=1)[0], None))
    return names


def parse_semver(s):
    if not s or str(s).strip() in {"0", "0.0.0"}:
        return (0, 0, 0)
    m = re.match(r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(s).strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0))


def is_exact_pin(spec):
    if not spec or not isinstance(spec, str):
        return False
    s = spec.strip()
    return bool(re.match(r"^v?\d+\.\d+", s)) and not any(c in s for c in "*^~><=")


def mal_affected(vuln):
    """(exact versions as tuples, ranges as (introduced, fixed|None), has_a_fixed_event)."""
    exact, ranges, has_fixed = [], [], False
    for a in vuln.get("affected") or []:
        for v in a.get("versions") or []:
            pv = parse_semver(v)
            if pv:
                exact.append((v, pv))
        for r in a.get("ranges") or []:
            if r.get("type") not in ("SEMVER", "ECOSYSTEM"):
                continue
            intro, fixed = (0, 0, 0), None
            for ev in r.get("events") or []:
                if "introduced" in ev:
                    intro = parse_semver(ev["introduced"]) or (0, 0, 0)
                if "fixed" in ev:
                    fixed = parse_semver(ev["fixed"])
                    has_fixed = True
            ranges.append((intro, fixed))
    return exact, ranges, has_fixed


def pin_is_affected(pin, exact, ranges):
    if pin is None:
        return False
    if any(pin == ev for _, ev in exact):
        return True
    for intro, fixed in ranges:
        if pin >= intro and (fixed is None or pin < fixed):
            return True
    return False


def compromised_release(vuln, exact, ranges, has_fixed):
    """True when the advisory is a short-lived compromise of a real package, not typoquat malware."""
    if has_fixed:
        return True
    if 1 <= len(exact) <= 10 and all(fx is not None for _, fx in ranges):
        return True
    return False


def check_typos_and_osv(deps, ecosystem, findings, file=None):
    popular = POPULAR_NPM if ecosystem == "npm" else POPULAR_PYPI
    seen = set()
    for origin, name, version in deps:
        if not name or name in seen:
            continue
        seen.add(name)
        typo = typo_of(name, popular)
        if typo:
            pop, dist = typo
            sev = "high" if dist == 1 else "medium"
            if origin == "self":
                sev = "medium"
            findings.append(finding(
                "typosquat",
                f"{'package' if origin == 'self' else 'dependency'} {name!r} is {dist} edit(s) from popular {pop!r} ({origin})",
                sev, file=file,
            ))
        try:
            vulns = osv_query("npm" if ecosystem == "npm" else "PyPI", name, None)
        except Exception:
            vulns = []
        pin = parse_semver(version) if is_exact_pin(version or "") else None
        for v in vulns or []:
            vid = v.get("id") or ""
            summary = (v.get("summary") or v.get("details") or vid)[:200]
            mal = vid.startswith("MAL-") or "malicious" in json.dumps(v.get("database_specific") or {}).lower()
            if not mal:
                continue
            exact, ranges, has_fixed = mal_affected(v)
            typo_mal = typo is not None
            if typo_mal or not compromised_release(v, exact, ranges, has_fixed):
                findings.append(finding(
                    "osv",
                    f"OSV malicious-package advisory {vid} for {name}: {summary}",
                    "malicious", file=file,
                ))
                continue
            # Compromised release of a known package: only flag an exact pin that is affected.
            if pin is not None and pin_is_affected(pin, exact, ranges):
                findings.append(finding(
                    "osv",
                    f"OSV {vid} lists this exact pin of {name} ({version}) as a compromised release: {summary}",
                    "high", file=file,
                ))


def repo_from_npm(j):
    if not j:
        return "", "", []
    latest = (j.get("dist-tags") or {}).get("latest")
    versions = j.get("versions") or {}
    v = versions.get(latest) or {}
    repo = normalize_repo_url(v.get("repository") or j.get("repository"))
    homepage = v.get("homepage") or j.get("homepage") or ""
    maintainers = []
    for m in (j.get("maintainers") or v.get("maintainers") or []):
        if isinstance(m, dict) and m.get("name"):
            maintainers.append(m["name"])
        elif isinstance(m, str):
            maintainers.append(m)
    return repo, homepage, maintainers


def repo_from_pypi(j):
    if not j:
        return "", "", []
    info = j.get("info") or {}
    urls = info.get("project_urls") or {}
    candidates = [urls.get(k) for k in ("Source", "Repository", "Homepage", "Code", "source", "GitHub") if urls.get(k)]
    candidates += [info.get("home_page"), info.get("project_url")]
    repo = ""
    for c in candidates:
        n = normalize_repo_url(c)
        if n.startswith("https://github.com/") or n.startswith("https://gitlab.com/") or n.startswith("https://bitbucket.org/"):
            repo = n
            break
    # A pypi.org/project/... page is not a source repository
    authors = []
    for key in ("author", "maintainer"):
        if info.get(key):
            authors.append(str(info[key]))
    if info.get("author_email"):
        authors.append(info["author_email"])
    return repo, info.get("home_page") or "", authors


def _alnum(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def publisher_matches(owner, publishers):
    """True when a publisher name or email obviously belongs to the GitHub owner."""
    own = _alnum(owner)
    if not own:
        return True
    # drop common org suffixes so alpacahq ~ alpaca, OpenBB-finance ~ openbb
    own_stem = re.sub(r"(hq|inc|io|ai|api|app|org|team|official|finance|dev)$", "", own) or own
    for p in publishers:
        s = str(p).lower()
        al = _alnum(s)
        if own in al or al in own or own_stem and (own_stem in al or al in own_stem):
            return True
        # email domain: info@alpaca.markets vs alpacahq
        m = re.search(r"@([a-z0-9.-]+)", s)
        if m:
            dom = _alnum(m.group(1).split(".")[0])
            if dom and (dom in own or own_stem in dom or dom in own_stem):
                return True
    return False


def check_registry_match(listed_repo, owner, pkg_repo, homepage, publishers, findings, kind):
    listed = normalize_repo_url(listed_repo)
    if pkg_repo:
        if listed and pkg_repo != listed and not (
            pkg_repo.startswith(listed + "/") or listed.startswith(pkg_repo + "/")
        ):
            findings.append(finding(
                "repo-mismatch",
                f"{kind} package repository field is {pkg_repo}, listed repo is {listed}",
                "high" if kind in {"npm", "PyPI"} else "medium",
            ))
    else:
        findings.append(finding(
            "repo-mismatch",
            f"{kind} package does not declare a repository field that matches the listing",
            "low",
        ))
    # publisher vs GitHub owner (soft signal)
    if owner and publishers:
        if not publisher_matches(owner, publishers):
            findings.append(finding(
                "publisher-mismatch",
                f"{kind} publishers {publishers[:6]} do not obviously match GitHub owner {owner!r}",
                "low",
            ))


# ------------------------------------ scan one tool ------------------------------------------
def package_belongs(name, path, tool, owner, repo):
    """True when a package.json / pyproject is the listed tool (or a same-repo sibling), not an example app."""
    if not name:
        return False
    if is_example_path(path) or is_test_path(path):
        return False
    tokens = []
    for s in (tool.get("id"), repo, owner):
        if s:
            tokens.extend(x for x in re.split(r"[-_]", s.lower()) if len(x) >= 4)
    n = re.sub(r"[@/]", " ", (name or "").lower())
    n_al = re.sub(r"[^a-z0-9]", "", n)
    for tok in tokens:
        if tok in n.split() or tok in n or re.sub(r"[^a-z0-9]", "", tok) in n_al:
            return True
    # root package of the repo is always in-scope
    rel = path.replace("\\", "/")
    if rel in {"package.json", "pyproject.toml", "setup.py"}:
        return True
    return False


def primary_package(items, tool, owner, repo):
    """Pick the listed tool's main package (exact/repo-name match, then closest to repo root)."""
    belonged = [(path, name) for path, name in items if name and package_belongs(name, path, tool, owner, repo)]
    if not belonged:
        return None
    repo_al = re.sub(r"[^a-z0-9]", "", (repo or "").lower())

    def score(item):
        path, name = item
        n = re.sub(r"[^a-z0-9]", "", (name or "").split("/")[-1].lower())
        exact = 0 if n == repo_al or n.endswith(repo_al) or repo_al.endswith(n) else 1
        depth = path.replace("\\", "/").count("/")
        return (exact, depth, path)

    belonged.sort(key=score)
    return belonged[0]


def allow_hosts_for(tool, owner):
    hosts = set()
    for key in ("homepage", "docs", "repo", "source_url", "remote_mcp_url"):
        h = host_of(tool.get(key) or "")
        if h:
            hosts.add(h)
            bd = base_domain(h)
            if bd:
                hosts.add(bd)
    if owner:
        hosts.add("github.com")
    return hosts


def list_repo_files(owner, repo, branch=None):
    info = gh_api(f"repos/{owner}/{repo}")
    if not info or not isinstance(info, dict):
        return None, None, [], False
    sha = (info.get("default_branch") if not branch else branch) or "HEAD"
    # resolve to a commit sha when possible
    ref = gh_api(f"repos/{owner}/{repo}/git/ref/heads/{sha}")
    if isinstance(ref, dict) and ref.get("object", {}).get("sha"):
        sha = ref["object"]["sha"]
    elif isinstance(info.get("default_branch"), str) and not branch:
        # fall back to the branch name in the trees API
        sha = info["default_branch"]
    tree = gh_api(f"repos/{owner}/{repo}/git/trees/{sha}?recursive=1")
    if not tree or not isinstance(tree, dict):
        return info, sha, []
    entries = []
    for e in tree.get("tree") or []:
        if e.get("type") != "blob":
            continue
        path = e.get("path") or ""
        size = e.get("size") or 0
        if size > MAX_FILE_BYTES:
            continue
        entries.append({"path": path, "size": size, "sha": e.get("sha")})
    if tree.get("truncated"):
        # still return what we got; caller notes the cap
        pass
    return info, (tree.get("sha") or sha), entries, bool(tree.get("truncated"))


def scan_tool(tool, max_files=MAX_FILES_DEFAULT):
    tid = tool["id"]
    findings = []
    out = {
        "id": tid,
        "name": tool.get("name"),
        "status": "clean",
        "date": NOW.strftime("%Y-%m-%d"),
        "repo": tool.get("repo"),
        "commit": None,
        "findings": findings,
        "files_scanned": 0,
        "packages": {},
        "notes": [],
    }
    parsed = parse_repo(tool.get("repo") or "")
    if not tool.get("repo"):
        findings.append(finding("repo", "No source repository listed; static scan skipped", "info"))
        out["status"] = status_of(findings)
        return out
    if not parsed:
        findings.append(finding("repo", f"Repository URL is not a GitHub repo we can list: {tool.get('repo')}", "medium"))
        out["status"] = status_of(findings)
        return out
    owner, repo, branch, sub = parsed
    listed = f"https://github.com/{owner}/{repo}"
    info, sha, entries, truncated = list_repo_files(owner, repo, branch)
    if info is None:
        findings.append(finding("repo", "Repository not reachable via the GitHub API; scan incomplete", "medium"))
        out["status"] = status_of(findings)
        return out
    out["commit"] = sha
    if truncated:
        out["notes"].append("GitHub tree was truncated; some paths may not have been listed")
    allow = allow_hosts_for(tool, owner)
    # homepage domain often equals the vendor API domain
    candidates = [e for e in entries if interesting(e["path"], subpath=sub)]
    candidates.sort(key=lambda e: (file_priority(e["path"]), e["size"], e["path"]))
    if len(candidates) > max_files:
        out["notes"].append(f"capped at {max_files} files ({len(candidates)} matched)")
        candidates = candidates[:max_files]

    npm_pkgs = []
    pypi_deps = []
    official = bool(tool.get("official"))

    for e in candidates:
        path = e["path"]
        text = raw_file(owner, repo, sha, path)
        if not text:
            continue
        out["files_scanned"] += 1
        base = os.path.basename(path).lower()
        if base == "package.json":
            pkg = check_package_json(path, text, findings)
            if pkg:
                npm_pkgs.append((path, pkg))
        if base == "setup.py":
            check_setup_py(path, text, findings)
        if base == "pyproject.toml":
            pypi_deps.extend([(path, d) for d in extract_pypi_deps(text, "pyproject")])
            try:
                n = (tomllib.loads(text).get("project") or {}).get("name") or (
                    (tomllib.loads(text).get("tool") or {}).get("poetry") or {}
                ).get("name")
            except Exception:
                pass
        if base.startswith("requirements") and base.endswith(".txt"):
            pypi_deps.extend([(path, d) for d in extract_pypi_deps(text, "requirements")])
        if base.startswith("dockerfile") or base.startswith("docker-compose") or base.startswith("compose.") or base.endswith(".sh") or base.endswith(".ps1") or base == "makefile":
            check_shell_and_docker(path, text, findings)
        else:
            # still catch curl|bash in source
            if CURL_PIPE.search(text) or BASH_FROM_CURL.search(text) or BINARY_DL.search(text):
                check_shell_and_docker(path, text, findings)
        check_obfuscation(path, text, findings)
        check_secrets_and_network(path, text, findings, allow)
        check_permissions(path, text, findings, official, tool.get("type"), tool.get("category"))

    # typo / OSV for every package we scanned; registry identity only for the primary package
    for path, pkg in npm_pkgs:
        check_typos_and_osv(extract_npm_deps(pkg), "npm", findings, file=path)
    npm_names = [(path, pkg.get("name")) for path, pkg in npm_pkgs if pkg.get("name") and not pkg.get("private")]
    prim = primary_package(npm_names, tool, owner, repo)
    if prim:
        path, name = prim
        out["packages"]["npm"] = name
        reg = npm_registry(name)
        if reg:
            pkg_repo, home, maintainers = repo_from_npm(reg)
            check_registry_match(listed, owner, pkg_repo, home, maintainers, findings, "npm")
        else:
            out["notes"].append(f"npm package {name!r} was not found on the registry")

    # typo / OSV / registry for python
    # collapse deps by file for typo checks
    if pypi_deps:
        # run once per unique file, plus self names
        by_file = {}
        for path, dep in pypi_deps:
            by_file.setdefault(path, []).append(dep)
        for path, deps in by_file.items():
            check_typos_and_osv(deps, "PyPI", findings, file=path)
        selfs = [(path, d[1]) for path, d in pypi_deps if d[0] == "self"]
        prim = primary_package(selfs, tool, owner, repo)
        if prim:
            path, name = prim
            out["packages"]["pypi"] = name
            reg = pypi_registry(name)
            if reg:
                pkg_repo, home, authors = repo_from_pypi(reg)
                check_registry_match(listed, owner, pkg_repo, home, authors, findings, "PyPI")
            else:
                out["notes"].append(f"PyPI package {name!r} was not found on the registry")

    # de-duplicate identical findings (same check/file/detail)
    uniq, seen = [], set()
    for f in findings:
        k = (f["check"], f["file"], f["detail"], f["line"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(f)
    out["findings"] = uniq
    out["status"] = status_of(uniq)
    return out


def safe_scan(tool, max_files):
    done, v = _bounded(lambda: scan_tool(tool, max_files=max_files), TOOL_DEADLINE)
    if done and not isinstance(v, BaseException):
        return v
    why = f"scanner error ({type(v).__name__}: {v})" if done else f"scanner timed out after {TOOL_DEADLINE:g}s"
    return {
        "id": tool["id"],
        "name": tool.get("name"),
        "status": "concerns",
        "date": NOW.strftime("%Y-%m-%d"),
        "repo": tool.get("repo"),
        "commit": None,
        "findings": [finding("repo", f"Scan incomplete: {why}", "medium")],
        "files_scanned": 0,
        "packages": {},
        "notes": [],
    }


# ------------------------------------ CLI ----------------------------------------------------
def parse_args(args, known_ids):
    only, dry, out_dir, jobs, max_files = None, False, DEFAULT_OUT, 4, MAX_FILES_DEFAULT
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--dry-run":
            dry = True
        elif a.startswith("--only="):
            val = a.split("=", 1)[1]
            ids = [x.strip() for x in val.split(",") if x.strip()]
            if not ids:
                sys.exit("security_scan.py: --only needs at least one id")
            unknown = [x for x in ids if x not in known_ids]
            if unknown:
                sys.exit(f"security_scan.py: unknown id(s) for --only: {', '.join(unknown)}")
            only = (only or []) + ids
        elif a == "--only":
            if i + 1 >= len(args) or args[i + 1].startswith("-"):
                sys.exit("security_scan.py: --only needs a comma-separated list of ids")
            i += 1
            ids = [x.strip() for x in args[i].split(",") if x.strip()]
            unknown = [x for x in ids if x not in known_ids]
            if unknown:
                sys.exit(f"security_scan.py: unknown id(s) for --only: {', '.join(unknown)}")
            only = (only or []) + ids
        elif a.startswith("--out-dir="):
            out_dir = a.split("=", 1)[1]
        elif a == "--out-dir":
            i += 1
            if i >= len(args):
                sys.exit("security_scan.py: --out-dir needs a path")
            out_dir = args[i]
        elif a.startswith("--jobs="):
            jobs = int(a.split("=", 1)[1])
        elif a.startswith("--max-files="):
            max_files = int(a.split("=", 1)[1])
        elif a in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        else:
            sys.exit(
                f"security_scan.py: unknown argument {a!r} "
                "(usage: security_scan.py [--dry-run] [--only=id1,id2] [--out-dir=DIR] [--jobs=N])"
            )
        i += 1
    return only, dry, out_dir, max(1, jobs), max_files


def load_tools():
    for name in ("data/tools.json", "data/seed.json"):
        p = os.path.join(ROOT, name)
        if os.path.exists(p):
            return json.load(open(p))
    sys.exit("security_scan.py: no data/tools.json or data/seed.json")


def write_result(out_dir, result):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{result['id']}.json")
    with open(path, "w") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
    return path


def main(argv=None):
    tools = load_tools()
    known = {t["id"] for t in tools}
    only, dry, out_dir, jobs, max_files = parse_args(argv if argv is not None else sys.argv[1:], known)
    todo = [t for t in tools if not only or t["id"] in only]
    t0 = time.monotonic()
    os.makedirs(CACHE_DIR, exist_ok=True)
    with ThreadPoolExecutor(jobs) as ex:
        results = list(ex.map(lambda t: safe_scan(t, max_files), todo))
    runtime = round(time.monotonic() - t0, 2)
    if not dry:
        for r in results:
            write_result(out_dir, r)
    by = Counter(r["status"] for r in results)
    summary = {
        "checked_at": NOW.isoformat(),
        "total": len(results),
        "by_status": dict(by),
        "runtime_seconds": runtime,
        "api_calls": dict(API_CALLS),
        "out_dir": None if dry else out_dir,
        "dry_run": dry,
        "tools": [
            {
                "id": r["id"],
                "status": r["status"],
                "findings": len(r["findings"]),
                "files_scanned": r.get("files_scanned", 0),
                "commit": r.get("commit"),
            }
            for r in results
        ],
    }
    if not dry:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "summary.json"), "w") as f:
            json.dump(summary, f, indent=2)
            f.write("\n")
    print(json.dumps({k: summary[k] for k in ("total", "by_status", "runtime_seconds", "api_calls", "dry_run")}))
    # short per-tool line on stderr for operators
    for r in results:
        top = [f["severity"] for f in r["findings"] if f["severity"] in ("malicious", "high", "medium")]
        print(f"  {r['id']}: {r['status']} ({len(r['findings'])} findings{', ' + ','.join(top[:6]) if top else ''})", file=sys.stderr)
    return summary


if __name__ == "__main__":
    main()
