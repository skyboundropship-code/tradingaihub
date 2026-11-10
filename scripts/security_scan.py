#!/usr/bin/env python3
"""Static security scanner for listed tools.

Never executes, installs, or imports third-party tool code. Reads files only via
the GitHub API / raw contents, npm and PyPI registry JSON, and the OSV.dev API.

Statuses are informational only: this script does not hide or un-list tools.

Run:  python3 scripts/security_scan.py
      python3 scripts/security_scan.py --only=id1,id2
      python3 scripts/security_scan.py --only=id1,id2 --out-dir=/tmp/sec --dry-run
      python3 scripts/security_scan.py --only=id1 --timeout=600 --max-files=2500
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import threading
import time
import tomllib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urlsplit

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "TradingAIHubSecurityScan/0.1 (static review; read-only)"}
TOKEN = os.environ.get("GITHUB_TOKEN")
NOW = dt.datetime.now(dt.timezone.utc)
S = requests.Session()
S.headers.update(UA)

CACHE_DIR = os.environ.get("SECURITY_SCAN_CACHE") or os.path.join(ROOT, ".cache", "security-scan")
DEFAULT_OUT = os.path.join(ROOT, "data", "security")
RULES_VERSION = "6"

def _scanner_commit():
    try:
        proc = subprocess.run(
            ["git", "-C", ROOT, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        sha = (proc.stdout or "").strip()
        if proc.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", sha):
            return sha
    except Exception:
        pass
    return None

SCANNER_COMMIT = _scanner_commit()

def stamp_result(out):
    if isinstance(out, dict):
        out["scanner_commit"] = SCANNER_COMMIT
        out["rules_version"] = RULES_VERSION
    return out

MAX_FILE_BYTES = 256 * 1024
MAX_MANIFEST_BYTES = 5 * 1024 * 1024
MAX_FILES_DEFAULT = 400
TOOL_DEADLINE = 180.0
GET_DEADLINE = 25.0
# Stop starting new GitHub REST work when fewer than this many calls remain.
RATE_FLOOR = 500
RATE_REMAINING = None
RATE_STOP = False
RATE_LOCK = threading.Lock()

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
react-hook-form eslint-config-prettier eslint-plugin-prettier
@tanstack/react-router @tanstack/router-core @tanstack/router-devtools
@tanstack/router-vite-plugin @tanstack/react-query
""".split())

POPULAR_SCOPES = frozenset("""
@tanstack @babel @types @angular @testing-library @solana @apollo @vue
@mui @emotion @nestjs @aws-sdk @radix-ui @stripe @coinbase @xeroapi
@typescript-eslint @eslint @jest @swc @vitejs @rollup
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
    "preinstall", "install", "postinstall",
    "prepare", "preprepare", "postprepare", "prepack",
)
# prepublish, prepublishOnly and postpack are publish-only and are ignored.
# prepare/husky and similar hooks that only run local tooling are expected.
BENIGN_HOOK = re.compile(
    r"^\s*(husky(?:\s+install)?|"
    r"(?:npm|pnpm|yarn)(?:\s+run)?\s+build(?::\w+)?|"
    r"tsc|true|exit\s+0|"
    r"node-gyp\s+rebuild|prebuild-install|only-allow|simple-git-hooks|"
    r"npm\s+run\s+prepare|patch-package(?:\s+--error-on-fail)?|"
    r"chmod\s+\+x\s+(?:\./)?[\w./+-]+)\s*$",
    re.I,
)

CURL_PIPE = re.compile(
    r"(curl|wget|invoke-webrequest|\biwr\b)\b[^\n|]{0,220}\|\s*"
    r"(?:sudo(?:\s+-\S+)*\s+)?(?:(?:/usr)?/bin/)?(?:bash|sh|zsh|fish|python3?|pwsh|powershell|cmd|iex)\b",
    re.I,
)
BASE64_PIPE = re.compile(
    r"base64\s+(?:-d|--decode)[^|\n]*\|\s*(?:sudo(?:\s+-\S+)*\s+)?(?:(?:/usr)?/bin/)?(?:ba)?sh\b",
    re.I,
)
IEX_DOWNLOAD = re.compile(
    r"\biex\b.{0,80}(?:DownloadString|iwr|Invoke-WebRequest)",
    re.I,
)
BASH_FROM_CURL = re.compile(
    r"(?:bash|sh)\s+<\(\s*(curl|wget)\b"
    r"|(?:bash|sh)\s+-c\s+[\"']?\$\(?(curl|wget)\b"
    r"|\beval\s+[\"']?\$\(\s*(?:curl|wget)\b"
    r"|\beval\s+[\"']?`\s*(?:curl|wget)\b",
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
    r"(?:^|[\"'/\\])\.metamask(?:[\"'/\\]|\b)|metamask[/\\]|IndexedDB/nkbihfbeogae)",
    re.I,
)
SEED_ASK = re.compile(
    r"(enter|paste|provide|input|prompt(?:\s+for)?|type(?:\s+in)?|supply|"
    r"ask(?:ing)?\s+for)\b.{0,60}\b(seed\s*phrase|mnemonic(?:\s+phrase)?|"
    r"recovery\s+phrase|wallet\s+private\s+key|"
    r"(?:wallet|mnemonic|seed|crypto|bitcoin|ethereum)\s+private\s+key|"
    r"private\s+key\s+wif|12[- ]word|24[- ]word|xprv|secret\s+recovery)",
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

# Hosts anyone can publish to: a pipe-to-shell from these is not a trusted installer.
USER_CONTENT_HOSTS = frozenset("""
raw.githubusercontent.com gist.githubusercontent.com gist.github.com
cdn.jsdelivr.net unpkg.com
""".split())

# Exact hosts of well-known official installers (low only in README/docs).
INSTALLER_HOSTS = frozenset("""
deb.nodesource.com sh.rustup.rs get.docker.com static.rust-lang.org
nodejs.org packages.microsoft.com aka.ms dl.google.com
astral.sh claude.ai
""".split())

HOOK_METACHAR = re.compile(r"&&|;|\||\$\(|`")
SETUP_REMOTE_EXEC = re.compile(
    r"(?:exec|eval)\s*\(\s*(?:.*)?(?:urlopen|requests\.get|urllib\.request|fetch)",
    re.I,
)
SETUP_TOPLEVEL_RUN = re.compile(
    r"(?:os\.system|os\.popen|subprocess\.(?:call|run|Popen|check_output|check_call)|"
    r"exec\s*\(|eval\s*\(|(?:urllib\.request\.)?urlopen\s*\()",
)

# Sentinels: never cached.
CACHE_MISS = object()
FETCH_FAILED = object()
OSV_UNAVAILABLE = object()
REGISTRY_ERROR = object()


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
    pth = _cache_path(key)
    try:
        with open(pth) as f:
            wrap = json.load(f)
        return wrap.get("value")
    except (OSError, ValueError):
        return CACHE_MISS


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


def _note_rate(resp):
    """Record GitHub remaining quota; trip RATE_STOP below RATE_FLOOR."""
    global RATE_REMAINING, RATE_STOP
    if resp is None or isinstance(resp, Exception):
        return
    headers = getattr(resp, "headers", None) or {}
    rem = headers.get("X-RateLimit-Remaining")
    if rem is None or not str(rem).isdigit():
        return
    with RATE_LOCK:
        RATE_REMAINING = int(rem)
        if RATE_REMAINING < RATE_FLOOR:
            RATE_STOP = True


def rate_budget_low():
    with RATE_LOCK:
        return RATE_STOP or (RATE_REMAINING is not None and RATE_REMAINING < RATE_FLOOR)


def _retry_headers(resp):
    """True when a response should be retried (429, rate-limited 403, or 5xx with Retry-After)."""
    if resp is None or isinstance(resp, Exception):
        return False
    code = getattr(resp, "status_code", None)
    if code == 429:
        return True
    headers = getattr(resp, "headers", None) or {}
    if code == 403:
        body = ""
        try:
            body = (resp.text or "")[:500].lower()
        except Exception:
            body = ""
        rem = str(headers.get("X-RateLimit-Remaining") or "")
        if rem == "0" or "rate limit" in body or "secondary rate" in body:
            return True
    if code and code >= 500 and headers.get("Retry-After"):
        return True
    return False


def _backoff(resp, attempt):
    headers = getattr(resp, "headers", None) or {}
    ra = headers.get("Retry-After")
    if ra and str(ra).isdigit():
        wait = min(int(ra), 30)
    else:
        wait = min(2 ** attempt, 8)
    time.sleep(wait)


def gh_api(path, raw=False):
    """GitHub REST GET. Uses GITHUB_TOKEN, else the logged-in `gh` CLI. Cached on success only."""
    key = f"gh:{path}:raw={raw}"
    hit = cache_get(key)
    if hit is not CACHE_MISS:
        return hit
    url = f"https://api.github.com/{path.lstrip('/')}"
    if TOKEN:
        r = None
        for attempt in range(4):
            counted("github")
            r = get(url, headers=github_headers())
            _note_rate(r)
            if _retry_headers(r):
                _maybe_sleep_rate(r)
                _backoff(r, attempt)
                continue
            break
        if isinstance(r, Exception) or r is None or r.status_code != 200:
            return None
        val = r.content.decode("utf-8", "replace") if raw else r.json()
        cache_set(key, val)
        return val
    if shutil.which("gh"):
        args = ["gh", "api", path]
        if raw:
            args += ["-H", "Accept: application/vnd.github.raw"]
        last = None
        for attempt in range(4):
            counted("github")
            try:
                last = subprocess.run(args, capture_output=True, text=True, timeout=45)
            except Exception:
                return None
            err = (last.stderr or "") + (last.stdout or "")
            if last.returncode != 0 and attempt < 3 and (
                "429" in err or "rate limit" in err.lower() or "API rate" in err
            ):
                time.sleep(min(2 ** attempt, 8))
                continue
            break
        if last is None or last.returncode != 0:
            return None
        val = last.stdout if raw else json.loads(last.stdout) if last.stdout else None
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


def raw_file(owner, repo, sha, path, max_bytes=None):
    """Fetch a blob as text. Prefer raw.githubusercontent.com (not REST quota); cache by sha+path.
    Returns FETCH_FAILED on a network or HTTP error (never cached). Empty string is a real empty blob.
    Must-scan manifests are read up to MAX_MANIFEST_BYTES (~5 MB); other files up to MAX_FILE_BYTES."""
    limit = max_bytes if max_bytes is not None else (
        MAX_MANIFEST_BYTES if is_must_scan(path) else MAX_FILE_BYTES
    )
    key = f"raw:{owner}/{repo}/{sha}/{path}:{limit}"
    hit = cache_get(key)
    if hit is not CACHE_MISS:
        return hit
    # Legacy entries were keyed without the limit. Reuse them only when the
    # stored blob is not a truncated slice that is smaller than we now need.
    legacy = cache_get(f"raw:{owner}/{repo}/{sha}/{path}")
    if legacy is not CACHE_MISS:
        if not isinstance(legacy, str):
            return legacy
        stored = len(legacy.encode("utf-8"))
        if stored in (MAX_FILE_BYTES, MAX_MANIFEST_BYTES) and stored < limit:
            pass  # likely truncated; refetch at the larger limit
        elif stored <= limit:
            return legacy
        else:
            return legacy.encode("utf-8")[:limit].decode("utf-8", "replace")
    enc = "/".join(quote(p, safe="") for p in path.split("/"))
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{sha}/{enc}"
    r = None
    for attempt in range(4):
        counted("raw")
        r = get(url)
        if _retry_headers(r):
            _maybe_sleep_rate(r)
            _backoff(r, attempt)
            continue
        break
    if not isinstance(r, Exception) and getattr(r, "status_code", None) == 200:
        if b"\0" in r.content[:4096]:
            cache_set(key, "")
            return ""
        text = r.content[:limit].decode("utf-8", "replace")
        cache_set(key, text)
        return text
    # fallback through the API (also uncached on failure). Skip it when the
    # remaining GitHub quota is below RATE_FLOOR, so a raw throttle cannot burn
    # thousands of REST calls.
    if rate_budget_low():
        return FETCH_FAILED
    api_path = f"repos/{owner}/{repo}/contents/{enc}?ref={sha}"
    body = gh_api(api_path, raw=True)
    if isinstance(body, str):
        cache_set(key, body[:limit])
        return body[:limit]
    return FETCH_FAILED

def npm_registry(name):
    key = f"npm:{name}"
    hit = cache_get(key)
    if hit is not CACHE_MISS:
        return hit
    url = f"https://registry.npmjs.org/{name.replace('/', '%2F')}"
    r = None
    for attempt in range(4):
        counted("npm")
        r = get(url)
        if _retry_headers(r):
            _maybe_sleep_rate(r)
            _backoff(r, attempt)
            continue
        break
    if isinstance(r, Exception) or r is None:
        return REGISTRY_ERROR
    if r.status_code == 404:
        cache_set(key, None)
        return None
    if r.status_code != 200:
        return REGISTRY_ERROR
    try:
        j = r.json()
    except ValueError:
        return REGISTRY_ERROR
    cache_set(key, j)
    return j

def pypi_registry(name):
    key = f"pypi:{name}"
    hit = cache_get(key)
    if hit is not CACHE_MISS:
        return hit
    r = None
    for attempt in range(4):
        counted("pypi")
        r = get(f"https://pypi.org/pypi/{name}/json")
        if _retry_headers(r):
            _maybe_sleep_rate(r)
            _backoff(r, attempt)
            continue
        break
    if isinstance(r, Exception) or r is None:
        return REGISTRY_ERROR
    if r.status_code == 404:
        cache_set(key, None)
        return None
    if r.status_code != 200:
        return REGISTRY_ERROR
    try:
        j = r.json()
    except ValueError:
        return REGISTRY_ERROR
    cache_set(key, j)
    return j

def osv_query(ecosystem, name, version=None):
    """Return a list of vulns, or OSV_UNAVAILABLE on a transport/HTTP error (never cached)."""
    key = f"osv:{ecosystem}:{name}:{version or ''}"
    hit = cache_get(key)
    if hit is not CACHE_MISS:
        return hit
    body = {"package": {"name": name, "ecosystem": ecosystem}}
    if version:
        body["version"] = version
    r = None
    for attempt in range(3):
        counted("osv")
        try:
            r = S.post("https://api.osv.dev/v1/query", json=body, timeout=20)
        except requests.RequestException:
            if attempt == 2:
                return OSV_UNAVAILABLE
            _backoff(None, attempt)
            continue
        code = getattr(r, "status_code", None)
        if code == 200:
            break
        # Retry 429, rate-limited 403, and any 5xx (including a bare 500/503).
        if _retry_headers(r) or (isinstance(code, int) and code >= 500):
            _backoff(r, attempt)
            continue
        return OSV_UNAVAILABLE
    if r is None or getattr(r, "status_code", None) != 200:
        return OSV_UNAVAILABLE
    try:
        vulns = r.json().get("vulns") or []
    except ValueError:
        return OSV_UNAVAILABLE
    cache_set(key, vulns)
    return vulns

def finding(check, detail, severity, file=None, line=None, **extra):
    out = {
        "check": check,
        "file": file,
        "line": line,
        "detail": detail,
        "severity": severity,
    }
    out.update(extra)
    return out


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


def is_must_scan(path):
    """Manifests, installers, Dockerfiles, shell, and GitHub workflows are always scanned."""
    rel = path.replace("\\", "/")
    base = rel.split("/")[-1].lower()
    if base in ALWAYS_NAMES or base.startswith("dockerfile") or base.startswith("docker-compose") or base.startswith("compose."):
        return True
    if base.startswith("requirements") and base.endswith(".txt"):
        return True
    if base in {"makefile", "install.sh", "install.bash", "install.ps1", "bootstrap.sh"}:
        return True
    if rel.startswith(".github/workflows/") and base.endswith((".yml", ".yaml")):
        return True
    if base.endswith((".sh", ".bash", ".ps1")):
        return True
    return False


def file_priority(path, primary_dir=None):
    base = os.path.basename(path).lower()
    pth = path.replace("\\", "/").lower()
    if is_must_scan(path):
        return 0
    if is_test_path(pth):
        return 8
    if is_example_path(pth):
        return 6
    if primary_dir:
        pd = primary_dir.replace("\\", "/").rstrip("/").lower()
        if pd and (pth == pd or pth.startswith(pd + "/")):
            return 1
    parts = pth.split("/")
    if any(k in parts for k in ("install", "setup", "wallet", "auth", "mcp", "src", "lib", "server", "scripts", "app")):
        return 2
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


def normalize_pkg_name(name, ecosystem=None):
    """PEP 503-style name normalisation for unscoped packages (typing_extensions == typing-extensions)."""
    if not name:
        return ""
    if name.startswith("@") and "/" in name:
        return name.lower()
    return re.sub(r"[-_.]+", "-", str(name).lower())


def typo_of(name, popular):
    """Return (popular_name, distance) if `name` looks like a typo of a popular package."""
    if not name:
        return None
    scoped = name.startswith("@") and "/" in name
    popular = [p for p in popular if isinstance(p, str)]
    # Exact popular name is never a typo of itself.
    if name in popular or name.lower() in {p.lower() for p in popular}:
        return None

    def typo_scoped_vs_scoped():
        # Never compare a scoped name with an unscoped popular package here
        # (e.g. @modelcontextprotocol/server vs semver, @dotenvx/dotenvx vs dotenv).
        scoped_pops = [p for p in popular if p.startswith("@")]
        if not scoped or not scoped_pops:
            return None
        low = name.lower()
        best = None
        for pop in scoped_pops:
            pl = pop.lower()
            limit = 1 if len(pl) < 8 else 2
            if abs(len(low) - len(pl)) > limit:
                continue
            d = levenshtein(low, pl, limit=limit)
            if d == 0:
                return None
            if 0 < d <= limit and len(pl) >= 4:
                if best is None or d < best[1]:
                    best = (pop, d)
                if d == 1:
                    return best
        return best

    def typo_unscoped_vs_unscoped():
        if scoped:
            return None
        low = normalize_pkg_name(name)
        popular_norm = {}
        for pop in popular:
            if pop.startswith("@"):
                continue
            popular_norm[normalize_pkg_name(pop)] = pop
        if low in popular_norm:
            return None
        for pop_n, pop in popular_norm.items():
            if low.startswith(pop_n + "-") or pop_n.startswith(low + "-"):
                return None
            if re.fullmatch(re.escape(pop_n) + r"[v.-]?\d+", low):
                return None
        best = None
        for pop_n, pop in popular_norm.items():
            limit = 1 if len(pop_n) < 8 else 2
            if abs(len(low) - len(pop_n)) > limit:
                continue
            d = levenshtein(low, pop_n, limit=limit)
            if d == 0:
                return None
            if 0 < d <= limit and len(pop_n) >= 4:
                if best is None or d < best[1]:
                    best = (pop, d)
                if d == 1:
                    return best
        return best

    def typo_scoped_impostor_of_unscoped():
        # @lodash/lodash or @expres/express: name part exactly matches a popular
        # unscoped package, and the scope is the same name or a 1-edit typo of it.
        if not scoped or "/" not in name:
            return None
        scope, _, pkg = name[1:].partition("/")
        if not pkg:
            return None
        unscoped = {normalize_pkg_name(p): p for p in popular if not p.startswith("@")}
        pkg_n = normalize_pkg_name(pkg)
        if pkg_n not in unscoped:
            return None
        scope_l, pkg_l = scope.lower(), pkg.lower()
        if scope_l == pkg_l:
            return (unscoped[pkg_n], 1)
        if 0 < levenshtein(scope_l, pkg_l, limit=1) <= 1:
            return (unscoped[pkg_n], 1)
        return None

    def typo_unscoped_impostor_of_scoped():
        # solana-web3.js / modelcontextprotocol-sdk look-alikes of @scope/name.
        if scoped:
            return None
        low = normalize_pkg_name(name)
        raw = name.lower()
        for pop in popular:
            if not (pop.startswith("@") and "/" in pop):
                continue
            scope, _, pkg = pop[1:].partition("/")
            forms = {
                f"{scope}-{pkg}",
                f"{scope}{pkg}",
                f"{scope}-{pkg.replace('.', '')}",
                f"{scope}{pkg.replace('.', '')}",
                f"{scope}-{pkg.replace('.', '-')}",
            }
            if raw in {f.lower() for f in forms}:
                return (pop, 1)
            if low in {normalize_pkg_name(f) for f in forms}:
                return (pop, 1)
        return None

    return (
        typo_scoped_vs_scoped()
        or typo_unscoped_vs_unscoped()
        or typo_scoped_impostor_of_unscoped()
        or typo_unscoped_impostor_of_scoped()
    )


def normalize_repo_url(u):
    if not u:
        return ""
    if isinstance(u, dict):
        u = u.get("url") or u.get("web") or ""
    u = str(u).strip()
    # package.json shorthands: "github:o/r" and "o/r"
    m = re.match(r"^(?:github:)?([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/?$", u)
    if m and "://" not in u:
        return f"https://github.com/{m.group(1)}/{m.group(2)}".lower()
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
def is_doc_path(path):
    rel = path.replace("\\", "/").lower()
    base = rel.split("/")[-1]
    ext = os.path.splitext(base)[1]
    if ext not in {".md", ".rst", ".txt"}:
        return False
    if base.startswith("readme") or base in {"changelog.md", "changes.md", "history.md"}:
        return True
    parts = rel.split("/")
    return parts and parts[0] in {"docs", "doc", "documentation"}


def is_exact_installer_host(host):
    if not host:
        return False
    h = host.lower().rstrip(".")
    return h in INSTALLER_HOSTS or any(h.endswith("." + x) for x in INSTALLER_HOSTS)


def is_user_content_host(host):
    if not host:
        return False
    h = host.lower().rstrip(".")
    return h in USER_CONTENT_HOSTS or any(h.endswith("." + x) for x in USER_CONTENT_HOSTS)


def is_ci_path(path):
    pth = (path or "").replace("\\", "/").lower()
    base = pth.split("/")[-1]
    if pth.startswith(".github/workflows/") or pth.startswith(".circleci/"):
        return True
    if base in {".gitlab-ci.yml", "azure-pipelines.yml", "azure-pipelines.yaml", "jenkinsfile"}:
        return True
    if "/.github/workflows/" in "/" + pth:
        return True
    return False


def is_vendor_release_url(snippet, owner=None):
    """True when the snippet downloads a GitHub Release of the listed repository owner."""
    if not snippet:
        return False
    owner = (owner or _ctx_owner() or "").strip()
    if not owner:
        return False
    return bool(re.search(
        r"https?://(?:github\.com|objects\.githubusercontent\.com)/"
        + re.escape(owner)
        + r"/[^/\s]+/releases/",
        snippet,
        re.I,
    ))


def strip_shell_comments(text, path=None):
    """Cut comments. `#` is a comment only at line start or after whitespace, `;`, `|` or `&`.
    `//` is stripped only in JS/TS; it is never a shell/Dockerfile comment."""
    if not text:
        return text
    base = os.path.basename((path or "").replace("\\", "/")).lower()
    strip_slash = base.endswith((".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx"))
    out = []
    i, n = 0, len(text)
    in_s = in_d = False
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == "'" and not in_d:
            in_s = not in_s
            out.append(ch); i += 1; continue
        if ch == '"' and not in_s:
            in_d = not in_d
            out.append(ch); i += 1; continue
        if not in_s and not in_d:
            if ch == "#":
                prev = out[-1] if out else None
                if prev is None or prev in " \t\r\n;|&":
                    break
            if strip_slash and ch == "/" and nxt == "/" and not (out and out[-1] == ":"):
                break
        out.append(ch); i += 1
    return "".join(out)


_CURL_FLAG_ARGS = frozenset({
    "-o", "-O", "-C", "-Q", "-d", "-T", "-H", "-e", "-A", "-u", "-U", "-b", "-c",
    "-w", "-m", "-y", "-Y", "-P", "-x", "-X", "-E", "-F", "-K",
    "--output", "--header", "--url", "--user", "--data", "--data-raw",
    "--data-binary", "--referer", "--user-agent", "--connect-timeout",
    "--max-time", "--retry", "--proxy", "--config", "--cacert", "--cert",
    "--key", "--form", "--upload-file", "--output-document",
    "--proto", "--tlsv1", "--resolve", "--connect-to", "--doh-url",
    "--interface", "--max-redirs", "--retry-delay", "--retry-max-time",
    "--cookie", "--cookie-jar", "--dump-header", "--write-out", "--stderr",
})
# Short options whose last letter takes an argument (for clusters like -fsSo).
_CURL_SHORT_ARG = frozenset("oOCQdTeAuUbchwmYyPxXEFK")
_CURL_REDIRECT_FLAGS = frozenset({
    "--url", "-K", "--config", "--resolve", "--connect-to",
    "-x", "--proxy", "--doh-url",
})
_WGET_REDIRECT_FLAGS = frozenset({
    "-i", "--input-file", "-e", "--execute", "--config",
    "-B", "--base",
})
# wget short options that consume an argument (including attached: -i./list.txt).
_WGET_SHORT_ARG = frozenset("oOiIeEBPtTwUuF")


def _shell_tokens(s):
    out, cur, q = [], [], None
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if q:
            if ch == q:
                q = None
            elif ch == "\\" and i + 1 < n:
                cur.append(s[i + 1]); i += 2; continue
            else:
                cur.append(ch)
            i += 1
            continue
        if ch.isspace():
            if cur:
                out.append("".join(cur)); cur = []
            i += 1
            continue
        if ch in ("'", '"'):
            q = ch; i += 1; continue
        cur.append(ch); i += 1
    if cur:
        out.append("".join(cur))
    return out


def curl_pipe_segment(snippet, path=None):
    """The curl/wget text up to the first pipe, comments already stripped."""
    if not snippet:
        return ""
    s = strip_shell_comments(snippet, path=path)
    m = re.search(r"\b(?:curl|wget|invoke-webrequest|\biwr\b)\b", s, re.I)
    if not m:
        return s.strip()
    rest = s[m.start():]
    cut = re.search(r"(?<!\|)\|(?!\|)", rest)
    return (rest[:cut.start()] if cut else rest).strip()


def urls_in_text(s):
    return re.findall(r"https?://[^\s'\"\\]+", s or "", flags=re.I)


def _curl_or_wget_verb(segment):
    """The curl/wget verb in a command segment, ignoring ENV= assignments."""
    for tok in _shell_tokens(segment or ""):
        base = tok.lower().rsplit("/", 1)[-1]
        if base in {"curl", "wget"}:
            return base
    return ""


def _curl_flag_takes_arg(tok, short_arg=None):
    if tok.startswith("--"):
        name = tok.split("=", 1)[0]
        extra = {"--input-file", "--execute", "--base"}
        return (name in _CURL_FLAG_ARGS or name in extra) and "=" not in tok
    return False


def _walk_short_cluster(tok, flags, short_arg):
    """Record each letter of a short cluster; first arg-taking letter consumes the rest.

    Returns True when the next token is the flag's argument (no attached value).
    """
    body = tok[1:]
    i = 0
    while i < len(body):
        ch = body[i]
        flags.add("-" + ch)
        if ch in short_arg:
            # attached argument (possibly empty) is the rest of this token
            return (i + 1) == len(body)
        i += 1
    flags.add(tok)
    return False


def curl_positional_tokens(segment):
    """Non-flag tokens of a curl/wget invocation (arguments already consumed)."""
    tokens = _shell_tokens(segment)
    if not tokens:
        return [], set()
    verb = _curl_or_wget_verb(segment)
    short_arg = _WGET_SHORT_ARG if verb == "wget" else _CURL_SHORT_ARG
    # start after the verb (skip leading ENV= / env)
    start = 0
    for i, tok in enumerate(tokens):
        if tok.lower().rsplit("/", 1)[-1] in {"curl", "wget"}:
            start = i + 1
            break
    skip_next = False
    positionals = []
    flags = set()
    for tok in tokens[start:]:
        if skip_next:
            skip_next = False
            continue
        if tok.startswith("--"):
            name = tok.split("=", 1)[0]
            flags.add(name)
            if _curl_flag_takes_arg(tok):
                skip_next = True
            continue
        if tok.startswith("-") and len(tok) >= 2:
            if _walk_short_cluster(tok, flags, short_arg):
                skip_next = True
            continue
        positionals.append(tok)
    return positionals, flags


def curl_fetch_url(snippet, path=None):
    """URL curl/wget actually fetches: last non-flag token before `|`."""
    segment = curl_pipe_segment(snippet, path=path)
    positionals, _flags = curl_positional_tokens(segment)
    for tok in reversed(positionals):
        if re.match(r"https?://", tok, re.I) or "://" in tok or "." in tok:
            if not re.match(r"https?://", tok, re.I) and "://" not in tok:
                tok = "https://" + tok.lstrip("/")
            return tok
    urls = urls_in_text(segment)
    return urls[-1] if urls else ""


def pipe_url_analysis(snippet, path=None):
    """Return (fetch_url, fetch_host, all_urls) after stripping comments."""
    clean = strip_shell_comments(snippet or "", path=path)
    segment = curl_pipe_segment(clean, path=path)
    fetch = curl_fetch_url(clean, path=path)
    urls = urls_in_text(segment)
    if fetch and fetch not in urls:
        urls = urls + [fetch]
    host = host_of(fetch) if fetch else ""
    return fetch, host, urls


def _raw_text_before_pipe(snippet, path=None):
    s = strip_shell_comments(snippet or "", path=path)
    m = re.search(r"\b(?:curl|wget|invoke-webrequest|\biwr\b)\b", s, re.I)
    rest = s[m.start():] if m else s
    cut = re.search(r"(?<!\|)\|(?!\|)", rest)
    return (rest[:cut.start()] if cut else rest)


def looks_like_pipe_mention(snippet):
    """True when the text talks about curl|bash (a regex, allow-list, or policy) rather than running it."""
    if not snippet:
        return False
    s = snippet.strip()
    # Alternation lists: wget|python-requests|httpx or curl|bash in prose with no URL/flags
    if re.search(r"\b(curl|wget)\s*\|\s*[\w./\\-]+\|", s, re.I):
        return True
    if re.search(r"\b(curl|wget)\s*\|\s*(?:ba)?sh\b", s, re.I) and not re.search(r"https?://|-\w", s):
        return True
    if re.search(r"(RegExp\(|new\s+RegExp|\.test\s*\(|/=\s*/|match\s*\()", s):
        return True
    return False


_SCAN_CTX = threading.local()


def _ctx_owner():
    return getattr(_SCAN_CTX, "owner", None)


def pipe_severity(path, host, snippet, owner=None):
    """Pipe-to-shell severity.

    Official installer hosts are info (low in README/docs so existing QA
    assertions stay green). CI pipes from a non-installer host are low.
    Both info and low leave the tool clean. Hook pipes are handled
    separately and are always high.

    Official downgrade only when the curl/wget segment has exactly one
    positional https URL on an installer (or owner-release) host, none of
    the redirect/config flags, and no `;`, `&&`, `||`, `$(` or backtick
    in the text before the pipe.
    """
    owner = owner if owner is not None else _ctx_owner()
    fetch_url, fetch_host, urls = pipe_url_analysis(snippet, path=path)
    host = fetch_host or (host or "")
    segment = curl_pipe_segment(snippet, path=path)
    positionals, flags = curl_positional_tokens(segment)
    raw_left = _raw_text_before_pipe(snippet, path=path)
    verb = _curl_or_wget_verb(segment)
    redirect = set(_CURL_REDIRECT_FLAGS)
    if verb == "wget":
        redirect |= _WGET_REDIRECT_FLAGS
    has_redirect = any(f in redirect for f in flags)
    # .curlrc / CURL_HOME can inject extra urls or a config (N14).
    # Look at the whole (comment-stripped) snippet so an env prefix
    # before the verb still counts.
    cleaned = strip_shell_comments(snippet or "", path=path)
    if re.search(r"\bCURL_HOME\b|\.curlrc\b", cleaned):
        has_redirect = True
    has_meta = bool(re.search(r";|&&|\|\||\$\(|`", raw_left))
    one_https = (
        len(positionals) == 1
        and bool(re.match(r"https://", positionals[0], re.I))
    )
    pos_url = positionals[0] if one_https else (fetch_url or "")
    official = (
        one_https
        and not has_redirect
        and not has_meta
        and (
            is_exact_installer_host(host_of(pos_url))
            or is_vendor_release_url(pos_url, owner)
        )
    )
    if is_ci_path(path):
        return "info" if official else "low"
    if official:
        if is_doc_path(path):
            return "low"
        return "info"
    return "high"


def _ok_rel_path(path):
    """True for a repo-relative path or glob (word chars, dots, slashes, stars, dashes); no '..', no absolute path."""
    if not path or not isinstance(path, str):
        return False
    p = path.strip()
    if not p or ".." in p:
        return False
    if p.startswith(("/", "~", "\\")) or (len(p) >= 2 and p[1] == ":"):
        return False
    body = p[2:] if p.startswith("./") else p
    if not body or not re.fullmatch(r"[\w./*-]+", body):
        return False
    return True


def _is_modules_or_bin_target(path):
    """True if a hook path plants into node_modules/ or .bin (N15)."""
    if not path or not isinstance(path, str):
        return False
    p = path.replace("\\", "/").strip()
    if p.startswith("./"):
        p = p[2:]
    parts = [x for x in p.split("/") if x and x != "."]
    return any(part in {"node_modules", ".bin"} for part in parts)


# Flag-like tsc arguments only (no bare words, no redirects).
_TSC_PART = re.compile(r"^tsc(?:\s+-{1,2}[\w-]+(?:[ =][\w./-]+)?)*$", re.I)
_CHMOD_PART = re.compile(
    r"^(?:shx\s+)?chmod\s+\+x\s+(?:(?:\./)?[\w./*-]+(?:\s+(?:\./)?[\w./*-]+)*)$",
    re.I,
)
_MKDIR_PART = re.compile(
    r"^mkdir\s+-p\s+(?:(?:\./)?[\w./*-]+(?:\s+(?:\./)?[\w./*-]+)*)$",
    re.I,
)
_CP_PART = re.compile(
    r"^cp\s+-[rR]\s+(?:(?:\./)?[\w./*-]+)(?:\s+(?:\./)?[\w./*-]+)+$",
    re.I,
)

# node -e that only does fs.chmodSync on a fixed relative path with mode 7xx.
_NODE_E_CHMOD = re.compile(
    r"""
    ^\s*node\s+-e\s+
    (?P<outer>["'])
    \s*
    (?:
        require\(\s*(?P<qfs>["'])fs(?P=qfs)\s*\)\s*\.\s*chmodSync
      | \(\s*await\s+import\(\s*(?P<qim>["'])fs(?P=qim)\s*\)\s*\)\s*\.\s*chmodSync
      | import\(\s*(?P<qim2>["'])fs(?P=qim2)\s*\)\s*\.\s*then\(\s*\w+\s*=>\s*\w+\.chmodSync
    )
    \s*\(\s*(?P<qp>["'])(?P<path>[^'"]+)(?P=qp)\s*,\s*(?P<qm>["'])(?P<mode>7[0-7]{2})(?P=qm)\s*\)
    \s*\)?    # optional closer for .then(
    \s*;?\s*
    (?P=outer)
    \s*$
    """,
    re.I | re.X,
)


def _is_benign_hook_part(part):
    """A single &&-separated hook segment. Hostile tokens already rejected by the caller."""
    part = (part or "").strip()
    if not part:
        return False
    if any(ch in part for ch in "&|;<>`$") or "\n" in part or "\r" in part:
        return False
    if _CHMOD_PART.match(part):
        m = re.match(r"^(?:shx\s+)?chmod\s+\+x\s+(.+)$", part, re.I)
        paths = _shell_tokens(m.group(1))
        return bool(paths) and all(_ok_rel_path(p) for p in paths) and not any(
            _is_modules_or_bin_target(p) for p in paths
        )
    if BENIGN_HOOK.match(part):
        return True
    if _TSC_PART.match(part):
        return True
    m = _MKDIR_PART.match(part)
    if m:
        rest = re.match(r"^mkdir\s+-p\s+(.+)$", part, re.I)
        paths = _shell_tokens(rest.group(1))
        return bool(paths) and all(_ok_rel_path(p) for p in paths)
    m = _CP_PART.match(part)
    if m:
        rest = re.match(r"^cp\s+-[rR]\s+(.+)$", part, re.I)
        paths = _shell_tokens(rest.group(1))
        if len(paths) < 2 or not all(_ok_rel_path(p) for p in paths):
            return False
        # N15: destination (last arg) must not be under node_modules/ or .bin.
        return not _is_modules_or_bin_target(paths[-1])
    m = _NODE_E_CHMOD.match(part)
    if m and _ok_rel_path(m.group("path")) and not _is_modules_or_bin_target(m.group("path")):
        return True
    return False


def is_benign_hook(cmd):
    if not cmd or not isinstance(cmd, str):
        return False
    # Always-hostile tokens are never benign, even when chained with tsc/build.
    if re.search(r"\b(curl|wget|iwr|invoke-webrequest)\b", cmd, re.I):
        return False
    if re.search(r"\beval\b|Function\(", cmd, re.I):
        return False
    # After removing every &&, none of & | ; < > ` $ or a newline may remain.
    remainder = cmd.replace("&&", "")
    if any(ch in remainder for ch in "&|;<>`$") or "\n" in remainder or "\r" in remainder:
        return False
    parts = [p.strip() for p in re.split(r"\s*&&\s*", cmd.strip()) if p.strip()]
    if not parts:
        return False
    return all(_is_benign_hook_part(part) for part in parts)


# Package-manager verbs that are not script names when `run` is omitted.
_PM_VERBS = frozenset({
    "install", "ci", "add", "remove", "uninstall", "update", "upgrade", "outdated",
    "audit", "init", "publish", "pack", "link", "unlink", "login", "logout",
    "cache", "config", "help", "version", "why", "exec", "dlx", "node", "global",
    "workspace", "workspaces", "plugin", "set", "up", "info", "dedupe", "explain",
    "rebuild", "run", "create", "dlx", "pkg", "why",
})
_NPM_RUN_RE = re.compile(
    r"\b(?P<pm>npm|pnpm|yarn)(?P<run>\s+run(?:-script)?)?(?:\s+(?P<name>\S+))?",
    re.I,
)


def script_names_in_hook(cmd):
    """Script names a hook reaches via npm/pnpm/yarn run X, or yarn/pnpm X."""
    names = []
    if not cmd or not isinstance(cmd, str):
        return names
    for m in _NPM_RUN_RE.finditer(cmd):
        name = (m.group("name") or "").strip().strip("'\"")
        if not name or name.startswith("-"):
            continue
        pm = (m.group("pm") or "").lower()
        has_run = bool(m.group("run"))
        if not has_run:
            if pm == "npm" and name.lower() not in {"start", "test", "stop", "restart"}:
                continue
            if pm in {"yarn", "pnpm"} and name.lower() in _PM_VERBS:
                continue
        names.append(name)
    return names


def iter_hook_cmds(scripts, cmd, depth=0, seen=None, label=None):
    """Yield (script_name_or_None, command) for a hook and npm-run targets.

    Follows scripts[X], preX and postX. Stops at depth 4 and skips cycles.
    A missing script is omitted (stays benign).
    """
    if seen is None:
        seen = set()
    if not cmd or not isinstance(cmd, str):
        return
    yield label, cmd
    if depth >= 4 or not isinstance(scripts, dict):
        return
    for name in script_names_in_hook(cmd):
        for rel in (name, f"pre{name}", f"post{name}"):
            if rel in seen:
                continue
            seen.add(rel)
            body = scripts.get(rel)
            if not body or not isinstance(body, str):
                continue
            yield from iter_hook_cmds(scripts, body, depth + 1, seen, label=rel)


def _scan_raw_install_hooks(path, text, findings):
    """Best-effort hunt for install hooks in a raw (possibly invalid) manifest."""
    for m in re.finditer(r'"(pre|post)?install"\s*:', text):
        window = text[m.start():m.start() + 400].splitlines()[0]
        if CURL_PIPE.search(window) or BASH_FROM_CURL.search(window) or BASE64_PIPE.search(window) or IEX_DOWNLOAD.search(window):
            findings.append(finding(
                "install-scripts",
                f"install hook in unparseable manifest: {window[:180]}",
                "high", file=path, line=line_no(text, m.start()),
            ))


def check_package_json(path, text, findings):
    try:
        j = json.loads(text)
    except ValueError:
        findings.append(finding(
            "install-scripts",
            "unparseable manifest (invalid or truncated JSON)",
            "medium", file=path,
        ))
        _scan_raw_install_hooks(path, text, findings)
        return None
    scripts = j.get("scripts") or {}
    if isinstance(scripts, dict):
        flagged = set()
        for hook in INSTALL_HOOKS:
            cmd = scripts.get(hook)
            if not cmd or not isinstance(cmd, str):
                continue
            for name, sub in iter_hook_cmds(scripts, cmd, seen={hook}):
                if is_benign_hook(sub):
                    continue
                key = (name or hook, sub)
                if key in flagged:
                    continue
                flagged.add(key)
                label = hook if not name else f"{hook} → {name}"
                detail = f"{label} script: {sub[:240]}"
                if CURL_PIPE.search(sub) or BASH_FROM_CURL.search(sub) or BASE64_PIPE.search(sub) or IEX_DOWNLOAD.search(sub):
                    # A curl|bash inside an install hook is always high, even on an
                    # official installer host or the owner's GitHub releases URL.
                    sev = "high"
                elif re.search(r"\b(curl|wget|iwr|invoke-webrequest|powershell|chmod\s+\+x)\b", sub, re.I):
                    sev = "high"
                elif re.search(r"\b(eval|Function\(|node\s+-e)\b", sub):
                    sev = "high"
                else:
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
    for rx, label in (
        (SETUP_REMOTE_EXEC, "setup.py runs exec/eval of a remote download (needs review)"),
        (SETUP_TOPLEVEL_RUN, "setup.py invokes a process, eval/exec, or urlopen at import (needs review)"),
    ):
        for m in rx.finditer(text):
            snippet = text[m.start():m.start() + 160].splitlines()[0]
            findings.append(finding(
                "install-scripts",
                f"{label}: {snippet[:160]}",
                "high", file=path, line=line_no(text, m.start()),
            ))


def check_shell_and_docker(path, text, findings):
    for rx, label in (
        (CURL_PIPE, "pipe-to-shell download"),
        (BASH_FROM_CURL, "shell process substitution from curl/wget"),
        (BASE64_PIPE, "base64 decode piped to a shell"),
        (IEX_DOWNLOAD, "PowerShell IEX of a remote download"),
    ):
        for m in rx.finditer(text):
            snippet = text[m.start():m.start() + 180].splitlines()[0]
            if looks_like_pipe_mention(snippet):
                continue
            _fetch, host, _urls = pipe_url_analysis(snippet, path=path)
            sev = pipe_severity(path, host, snippet)
            # Env prefixes live before the verb, so also look at the rest of this line.
            if sev in {"info", "low"}:
                line_start = text.rfind("\n", 0, m.start()) + 1
                prefix = text[line_start:m.start()] + snippet
                if re.search(r"\bCURL_HOME\b|\.curlrc\b", prefix):
                    sev = "high"
            findings.append(finding("curl-pipe", f"{label}: {snippet[:180]}", sev, file=path, line=line_no(text, m.start())))
    for m in BINARY_DL.finditer(text):
        snippet = text[m.start():m.start() + 180].splitlines()[0]
        findings.append(finding(
            "curl-pipe", f"download of a binary/executable: {snippet[:180]}",
            "medium", file=path, line=line_no(text, m.start()),
        ))


def check_obfuscation(path, text, findings, reachable=False):
    if is_vendorish(path) and not reachable:
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


def check_secrets_and_network(path, text, findings, allow_hosts, reachable=False):
    # Tests, fixtures, README and docs mention keys and demo IPs; those are not exfil.
    # Seed-phrase prompts are still checked in those paths.
    # Reachable entry points (main/bin/exports/hooks) are always checked.
    skip_exfil = (not reachable) and (is_test_path(path) or is_doc_path(path))
    secret_hits = []
    if not skip_exfil:
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
    if skip_exfil:
        return
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
            sev, detail = "high", f"finding: sensitive-path read combined with hard-coded host {h} ({url[:160]}) needs review"
        else:
            sev, detail = "high", f"finding: suspicious hard-coded network destination {h} ({url[:160]}) needs review"
        findings.append(finding("secret-exfil", detail, sev, file=path, line=ln))




def check_permissions(path, text, findings, official, tool_type=None, category=None, reachable=False):
    # MCP live-trading / withdrawal tools: only look at definitions, and only on
    # MCP servers or broker/crypto tools. Accounting "withdrawal" transaction types are ignored.
    if not reachable and (is_vendorish(path) or is_test_path(path)):
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


def split_req(dep):
    """Split a PEP 508 / requirements token into (name, version_spec_or_None)."""
    s = (dep or "").strip()
    if not s or s.startswith("#") or s.startswith("-"):
        return None, None
    s = re.split(r"\s*;", s, maxsplit=1)[0].strip()
    m = re.match(r"^([A-Za-z0-9_.-]+)\s*(\[[^\]]*\])?\s*(.*)$", s)
    if not m:
        return re.split(r"[\s<>=!~;\[]", s, maxsplit=1)[0], None
    name, _extras, rest = m.group(1), m.group(2), (m.group(3) or "").strip()
    if rest and is_exact_pin(rest):
        rest = strip_pin(rest)
    return name, (rest or None)


def extract_pypi_deps(text, kind, findings=None, path=None):
    names = []
    if kind == "pyproject":
        try:
            data = tomllib.loads(text)
        except Exception:
            if findings is not None:
                findings.append(finding(
                    "install-scripts",
                    "unparseable manifest (invalid or truncated TOML)",
                    "medium", file=path,
                ))
            return names
        proj = data.get("project") or {}
        n = proj.get("name")
        if n:
            names.append(("self", n, (proj.get("version") if isinstance(proj.get("version"), str) else None)))
        for dep in proj.get("dependencies") or []:
            if isinstance(dep, str) and dep.strip() and not dep.strip().startswith("#"):
                name, ver = split_req(dep)
                if name:
                    names.append(("dependencies", name, ver))
        opt = proj.get("optional-dependencies") or {}
        if isinstance(opt, dict):
            for lst in opt.values():
                for dep in lst or []:
                    if isinstance(dep, str) and dep.strip():
                        name, ver = split_req(dep)
                        if name:
                            names.append(("optional", name, ver))
        poetry = (data.get("tool") or {}).get("poetry") or {}
        if poetry.get("name"):
            names.append(("self", poetry["name"], poetry.get("version") if isinstance(poetry.get("version"), str) else None))
        deps = poetry.get("dependencies") or {}
        if isinstance(deps, dict):
            for n, spec in deps.items():
                if n == "python":
                    continue
                ver = None
                if isinstance(spec, str):
                    ver = spec
                elif isinstance(spec, dict) and isinstance(spec.get("version"), str):
                    ver = spec["version"]
                names.append(("dependencies", n, ver))
    elif kind == "requirements":
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("-"):
                continue
            name, ver = split_req(s)
            if name:
                names.append(("requirements", name, ver))
    return names


def _pre_key(part):
    """Numeric identifiers compare as ints; others as lowercase strings (semver)."""
    return (0, int(part)) if str(part).isdigit() else (1, str(part).lower())


class SemVer:
    """Comparable version that orders pre-releases before the matching release."""

    def __init__(self, major, minor=0, patch=0, pre=()):
        self.major, self.minor, self.patch, self.pre = int(major), int(minor), int(patch), tuple(pre)

    def __eq__(self, other):
        return (self.major, self.minor, self.patch, self.pre) == (other.major, other.minor, other.patch, other.pre)

    def __lt__(self, other):
        t = (self.major, self.minor, self.patch)
        o = (other.major, other.minor, other.patch)
        if t != o:
            return t < o
        if not self.pre and not other.pre:
            return False
        if not self.pre:
            return False  # release is after any pre
        if not other.pre:
            return True
        # compare pre identifiers
        a = [_pre_key(x) for x in self.pre]
        b = [_pre_key(x) for x in other.pre]
        return a < b

    def __le__(self, other):
        return self == other or self < other

    def __gt__(self, other):
        return other < self

    def __ge__(self, other):
        return self == other or other < self

    def bump_major(self):
        return SemVer(self.major + 1, 0, 0)

    def bump_minor(self):
        return SemVer(self.major, self.minor + 1, 0)

    def bump_patch(self):
        return SemVer(self.major, self.minor, self.patch + 1)

    def __repr__(self):
        core = f"{self.major}.{self.minor}.{self.patch}"
        return core + (("-" + ".".join(str(x) for x in self.pre)) if self.pre else "")


def parse_semver(s):
    if s is None:
        return None
    raw = str(s).strip()
    if not raw:
        return None
    if raw in {"0", "0.0.0"}:
        return SemVer(0, 0, 0)
    raw = raw.lstrip("v=V").strip()
    # Build metadata (+build) is not a pre-release; strip it first.
    if "+" in raw:
        raw = raw.split("+", 1)[0]
    # PEP 440 pre without treating unknown -tags as metadata: 1.0.0a1 / 1.0.0-rc.1
    m = re.match(
        r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-._]?(a|b|alpha|beta|rc|preview|dev)[.]?(\d*))?$",
        raw,
        re.I,
    )
    if m:
        tag = (m.group(4) or "").lower()
        pre = ()
        if tag:
            num = m.group(5) or "0"
            pre = (tag, int(num) if num.isdigit() else num)
        return SemVer(int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0), pre)
    # Any other -<ids> is a pre-release tuple (next, canary, -0, ...).
    m2 = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([A-Za-z0-9.-]+))?$", raw)
    if not m2:
        return None
    pre = tuple(x for x in (m2.group(4) or "").split(".") if x)
    return SemVer(int(m2.group(1)), int(m2.group(2) or 0), int(m2.group(3) or 0), pre)


def strip_pin(spec):
    if not spec or not isinstance(spec, str):
        return ""
    s = spec.strip()
    s = re.sub(r"^(==|=|v)", "", s).strip()
    return s


def is_exact_pin(spec):
    if not spec or not isinstance(spec, str):
        return False
    s = strip_pin(spec)
    if not s or any(c in s for c in "*^~<>, "):
        return False
    return bool(re.match(r"^\d+\.\d+", s))


def is_unknown_spec(spec):
    if spec is None:
        return True
    s = str(spec).strip()
    return s == "" or s.lower() in {"*", "latest", "x", "any"}


def mal_affected(vuln):
    """(exact list of SemVer, ranges as (introduced, fixed_excl|None, last_affected|None), has_fixed)."""
    exact, ranges, has_fixed = [], [], False
    for a in vuln.get("affected") or []:
        for v in a.get("versions") or []:
            pv = parse_semver(v)
            if pv:
                exact.append((v, pv))
        for r in a.get("ranges") or []:
            if r.get("type") not in ("SEMVER", "ECOSYSTEM"):
                continue
            intro, fixed, last = SemVer(0, 0, 0), None, None
            for ev in r.get("events") or []:
                if "introduced" in ev:
                    intro = parse_semver(ev["introduced"]) or SemVer(0, 0, 0)
                if "fixed" in ev:
                    fixed = parse_semver(ev["fixed"])
                    has_fixed = True
                if "last_affected" in ev:
                    last = parse_semver(ev["last_affected"])
            ranges.append((intro, fixed, last))
    return exact, ranges, has_fixed


def pin_is_affected(pin, exact, ranges):
    if pin is None:
        return False
    if any(pin == ev for _, ev in exact):
        return True
    for intro, fixed, last in ranges:
        if pin >= intro and (fixed is None or pin < fixed) and (last is None or pin <= last):
            return True
    return False


def npm_spec_bounds(spec):
    """(lo inclusive, hi exclusive or None) for a simple npm/PEP specifier. None, None means unknown/unbounded."""
    s = (spec or "").strip()
    if is_unknown_spec(s):
        return SemVer(0, 0, 0), None
    if is_exact_pin(s):
        v = parse_semver(strip_pin(s))
        return (v, v.bump_patch()) if v else (None, None)
    # take the first clause
    s = s.split("||")[0].split(",")[0].strip()
    if s.startswith("^"):
        base = parse_semver(s[1:])
        if not base:
            return None, None
        # ^0.2.3 => >=0.2.3 <0.3.0; ^1.2.3 => >=1.2.3 <2.0.0
        hi = base.bump_minor() if base.major == 0 else base.bump_major()
        return base, hi
    if s.startswith("~"):
        base = parse_semver(s[1:].lstrip("="))
        if not base:
            return None, None
        return base, base.bump_minor()
    m = re.match(r"^(>=|<=|>|<|==|=|~=)\s*(.+)$", s)
    if m:
        op, rest = m.group(1), m.group(2)
        v = parse_semver(rest)
        if not v:
            return None, None
        if op in ("==", "="):
            return v, v.bump_patch() if not v.pre else v  # exclusive end after this exact
        if op == ">=":
            return v, None
        if op == ">":
            return v.bump_patch(), None
        if op == "<=":
            return SemVer(0, 0, 0), v.bump_patch()
        if op == "<":
            return SemVer(0, 0, 0), v
        if op == "~=":  # PEP 440 compatible: ~=1.4.5 => >=1.4.5 <1.5.0; ~=1.4 => >=1.4 <2
            parts = [int(x) for x in re.findall(r"\d+", rest)[:3]]
            if len(parts) <= 2:
                return v, v.bump_major()
            return v, v.bump_minor()
    v = parse_semver(s)
    if v:
        return v, v.bump_patch()
    return None, None


def version_satisfies(spec, ver):
    lo, hi = npm_spec_bounds(spec)
    if ver is None or lo is None:
        return False
    if ver < lo:
        return False
    if hi is not None and not ver < hi:
        return False
    return True


def ranges_overlap(lo, hi, intro, fixed, last):
    """True if [lo, hi) overlaps the affected interval."""
    if lo is None:
        return True
    aff_lo = intro
    # exclusive end
    aff_hi = fixed
    if last is not None:
        # inclusive last: exclusive end is just after last, tightened with fixed
        after_last = last.bump_patch() if not last.pre else last  # pre: treat as <= last only via pin check
        # better: pin <= last is inclusive; use a high bound just above last
        after_last = SemVer(last.major, last.minor, last.patch, last.pre + ("~",) if last.pre else ())
        # simpler inclusive test below
        aff_hi_incl = last
        start = lo if lo >= aff_lo else aff_lo
        if start > aff_hi_incl:
            return False
        if hi is not None and not start < hi:
            return False
        if fixed is not None and not start < fixed:
            return False
        return True
    start = lo if lo >= aff_lo else aff_lo
    # start must be < aff_hi (if any) and < hi (if any)
    if fixed is not None and not start < fixed:
        return False
    if hi is not None and not start < hi:
        return False
    # also lo < fixed and intro < hi
    if hi is not None and not intro < hi:
        # unless lo is inside
        if not (intro < hi):
            return False
    return True


def spec_admits_affected(spec, exact, ranges):
    if is_exact_pin(spec or ""):
        pin = parse_semver(strip_pin(spec))
        return pin_is_affected(pin, exact, ranges)
    if is_unknown_spec(spec):
        return None  # unknown
    # any exact affected version in the spec?
    for _, ev in exact:
        if version_satisfies(spec, ev):
            return True
    lo, hi = npm_spec_bounds(spec)
    if lo is None and hi is None:
        return None
    for intro, fixed, last in ranges:
        if ranges_overlap(lo, hi, intro, fixed, last):
            return True
    return False


def range_is_unbounded(intro, fixed, last):
    """True when a range covers every version (introduced 0, no upper bound)."""
    intro0 = intro is None or intro == SemVer(0, 0, 0)
    return intro0 and fixed is None and last is None


def registry_latest_version(ecosystem, name):
    """Published 'latest' from the registry, or None if lookup fails."""
    try:
        eco = "npm" if (ecosystem or "").lower() == "npm" else "PyPI"
        if eco == "npm":
            reg = npm_registry(name)
            if not reg or reg is REGISTRY_ERROR:
                return None
            latest = (reg.get("dist-tags") or {}).get("latest")
        else:
            reg = pypi_registry(name)
            if not reg or reg is REGISTRY_ERROR:
                return None
            latest = ((reg.get("info") or {}).get("version"))
        return latest if isinstance(latest, str) and latest else None
    except Exception:
        return None


def unknown_spec_is_affected(ecosystem, name, exact, ranges):
    """Unknown pins (* / latest / git / file) still install malware when the
    advisory has no upper bound, or when the registry latest is in range."""
    if any(range_is_unbounded(intro, fixed, last) for intro, fixed, last in ranges):
        return True
    latest = registry_latest_version(ecosystem, name)
    pin = parse_semver(latest) if latest else None
    return pin_is_affected(pin, exact, ranges)


def is_popular_name(name, popular):
    if not name:
        return False
    n = name.lower()
    if n in popular:
        return True
    if name.startswith("@") and "/" in name:
        if n in popular or name.split("/")[0].lower() in POPULAR_SCOPES:
            return True
    return False



LOCK_BASENAMES = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json",
    "poetry.lock", "uv.lock",
})


def in_vendor_dir(path):
    parts = path.replace("\\", "/").split("/")[:-1]
    return any(p.lower() in SKIP_DIR for p in parts)


def _lock_add(versions, name, ver):
    if not name or not ver or not isinstance(ver, str):
        return
    versions.setdefault(name, []).append(ver)
    norm = normalize_pkg_name(name)
    if norm and norm != name:
        versions.setdefault(norm, []).append(ver)


def parse_lockfile(path, text):
    """Return {name: [versions]} or None if the lockfile cannot be parsed."""
    if not text or text is FETCH_FAILED:
        return None
    base = os.path.basename(path or "").lower()
    versions = {}
    try:
        if base in {"package-lock.json", "npm-shrinkwrap.json"}:
            j = json.loads(text)
            for pth, meta in (j.get("packages") or {}).items():
                if not isinstance(meta, dict):
                    continue
                name = meta.get("name")
                if not name and "node_modules/" in (pth or "").replace("\\", "/"):
                    name = pth.replace("\\", "/").split("node_modules/")[-1]
                _lock_add(versions, name, meta.get("version"))
            def walk(deps):
                if not isinstance(deps, dict):
                    return
                for n, meta in deps.items():
                    if isinstance(meta, dict):
                        _lock_add(versions, n, meta.get("version"))
                        walk(meta.get("dependencies"))
            walk(j.get("dependencies"))
        elif base == "yarn.lock":
            header_ok = bool(re.search(r"(?m)^# yarn lockfile v1\b|^__metadata:\s*$", text))
            if not header_ok:
                return None
            current = []
            for line in text.splitlines():
                if line.strip() and not line.startswith((" ", "\t")) and line.rstrip().endswith(":"):
                    header = line.strip()[:-1]
                    current = []
                    for tok in re.split(r",\s*", header):
                        tok = tok.strip().strip("\"'")
                        if not tok:
                            continue
                        if tok.startswith("@"):
                            m = re.match(r"(@[^/]+/[^@]+)@", tok)
                            if m:
                                current.append(m.group(1))
                        elif "@" in tok:
                            current.append(tok.split("@", 1)[0])
                else:
                    m = re.match(r'\s+version:?\s+"?([^"\s]+)"?', line)
                    if m and current:
                        for n in current:
                            _lock_add(versions, n, m.group(1))
                        current = []
        elif base == "pnpm-lock.yaml":
            if not re.search(r"(?m)^lockfileVersion:", text):
                return None
            if not re.search(r"(?m)^(packages|importers):", text):
                return None
            for m in re.finditer(
                r"(?m)^(?:\s*)['\"]?/?((?:@[^/'\"\s]+/)?[^@/'\"\s]+)@v?(\d[^:()'\"]+):",
                text,
            ):
                _lock_add(versions, m.group(1), m.group(2).split("(")[0])
        elif base in {"poetry.lock", "uv.lock"}:
            for m in re.finditer(
                r'(?m)^name\s*=\s*"([^"]+)"\nversion\s*=\s*"([^"]+)"',
                text,
            ):
                _lock_add(versions, m.group(1), m.group(2))
        else:
            return None
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    # Nothing parsed from a present file is not a usable lock: callers fall back
    # to "lockfile not checked" instead of treating it as an empty (safe) pin set.
    return versions or None


def lock_versions_for(manifest_path, locks_by_dir):
    """Walk from the manifest directory up to the repo root looking for a lockfile."""
    if not locks_by_dir:
        return None
    d = (manifest_path or "").replace("\\", "/")
    if d.startswith("npm:") or d.startswith("pypi:"):
        d = ""
    elif "/" in d:
        d = d.rsplit("/", 1)[0]
    else:
        d = ""
    while True:
        if d in locks_by_dir:
            return locks_by_dir[d]
        if d == "":
            return None
        d = d.rsplit("/", 1)[0] if "/" in d else ""


def resolved_lock_versions(lock_versions, name):
    if not lock_versions or not name:
        return []
    out = list(lock_versions.get(name) or [])
    norm = normalize_pkg_name(name)
    if norm != name:
        out.extend(lock_versions.get(norm) or [])
    return out


def check_typos_and_osv(deps, ecosystem, findings, file=None, lock_versions=None):
    popular = POPULAR_NPM if ecosystem == "npm" else POPULAR_PYPI
    seen = set()
    osv_failed = False
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
            vulns = OSV_UNAVAILABLE
        if vulns is OSV_UNAVAILABLE:
            osv_failed = True
            findings.append(finding(
                "osv-unavailable",
                "OSV.dev did not respond; advisory check incomplete",
                "info", file=file,
            ))
            continue
        popular_pkg = is_popular_name(name, popular)
        for v in vulns or []:
            vid = v.get("id") or ""
            summary = (v.get("summary") or v.get("details") or vid)[:200]
            mal = vid.startswith("MAL-") or "malicious" in json.dumps(v.get("database_specific") or {}).lower()
            if not mal:
                continue
            exact, ranges, has_fixed = mal_affected(v)
            typo_mal = typo is not None
            admitted = spec_admits_affected(version, exact, ranges)
            if origin == "self":
                # Name-squat / dependency confusion: a MAL advisory on this
                # manifest's own name is not evidence the repo shipped malware.
                eco = "npm" if ecosystem == "npm" else "PyPI"
                findings.append(finding(
                    "name-squat",
                    f"this repo's example package name is registered on "
                    f"{'npm' if eco == 'npm' else 'PyPI'} by a malicious package ({vid}); "
                    f"the repo code is not affected; mark it `private: true`.",
                    "medium", file=file,
                ))
                continue
            if typo_mal:
                if admitted is False:
                    continue
                findings.append(finding(
                    "osv",
                    f"OSV malicious-package advisory {vid} for {name}: {summary}",
                    "malicious", file=file,
                ))
                continue
            if admitted is False:
                continue
            if admitted is None:
                if unknown_spec_is_affected(ecosystem, name, exact, ranges):
                    admitted = True
                else:
                    findings.append(finding(
                        "osv",
                        f"OSV {vid} for {name}: version unknown, advisory not matched to a pin ({summary})",
                        "low", file=file,
                    ))
                    continue
            if is_exact_pin(version or ""):
                findings.append(finding(
                    "osv",
                    f"OSV {vid} lists this exact pin of {name} ({version}) as a compromised release: {summary}",
                    "high", file=file,
                ))
                continue
            if lock_versions is not None:
                resolved = resolved_lock_versions(lock_versions, name)
                if not resolved:
                    pass  # stale / other-workspace lock: fall through to "not checked"
                elif not any(pin_is_affected(parse_semver(v), exact, ranges) for v in resolved):
                    findings.append(finding(
                        "osv",
                        f"range admits a compromised release of {name} listed in {vid}; "
                        f"repo lockfile pins {', '.join(sorted(set(resolved)))}; npx installs resolve fresh",
                        "low", file=file,
                    ))
                    continue
                else:
                    findings.append(finding(
                        "osv",
                        f"OSV {vid}: lockfile resolves {name} to a compromised release ({', '.join(sorted(set(resolved)))}): {summary}",
                        "high", file=file,
                    ))
                    continue
            if popular_pkg:
                findings.append(finding(
                    "osv",
                    f"range admits a compromised release of {name} listed in {vid}; lockfile not checked",
                    "medium", file=file,
                ))
                continue
            findings.append(finding(
                "osv",
                f"OSV malicious-package advisory {vid} for {name}: {summary}",
                "malicious", file=file,
            ))
    return osv_failed


def _names_from(obj):
    out = []
    if isinstance(obj, dict) and obj.get("name"):
        out.append(obj["name"])
    elif isinstance(obj, str):
        out.append(obj)
    return out


def repo_from_npm(j):
    if not j or j is REGISTRY_ERROR:
        return "", "", []
    latest = (j.get("dist-tags") or {}).get("latest")
    versions = j.get("versions") or {}
    v = versions.get(latest) or {}
    repo = normalize_repo_url(v.get("repository") or j.get("repository"))
    homepage = v.get("homepage") or j.get("homepage") or ""
    publishers = []
    for src in (
        v.get("_npmUser"),
        v.get("maintainers"),
        j.get("maintainers"),
    ):
        if isinstance(src, list):
            for m in src:
                publishers.extend(_names_from(m))
        else:
            publishers.extend(_names_from(src))
    # unique, latest user first
    seen, uniq = set(), []
    for n in publishers:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return repo, homepage, uniq


def repo_from_pypi(j):
    if not j or j is REGISTRY_ERROR:
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
    own_stem = re.sub(r"(hq|inc|io|ai|api|app|org|team|official|finance|dev)$", "", own) or own
    # very short stems ("ai") must not match as a substring of arbitrary names
    min_len = 3
    for p in publishers:
        s = str(p).lower()
        al = _alnum(s)
        if len(own) >= min_len and (own == al or own in al or al == own):
            return True
        if len(own_stem) >= min_len and (own_stem == al or own_stem in al or al == own_stem):
            return True
        m = re.search(r"@([a-z0-9.-]+)", s)
        if m:
            dom = _alnum(m.group(1).split(".")[0])
            if len(dom) >= min_len and (dom in own or own_stem in dom or (len(own_stem) >= min_len and dom in own_stem)):
                return True
    return False


def npm_held_or_deprecated(j):
    """True when the published package is held by npm support or marked unsupported."""
    if not j or j is REGISTRY_ERROR:
        return False
    latest = (j.get("dist-tags") or {}).get("latest")
    v = (j.get("versions") or {}).get(latest) or {}
    names = []
    for src in (v.get("maintainers"), j.get("maintainers")):
        if isinstance(src, list):
            for m in src:
                names.extend(n.lower() for n in _names_from(m))
        elif src:
            names.extend(n.lower() for n in _names_from(src))
    # top-level only npm-support (bitcoin-mcp case): even if old versions list another user
    top = []
    for m in (j.get("maintainers") or []):
        top.extend(n.lower() for n in _names_from(m))
    check = top or names
    if check and all(n.replace(" ", "-") in {"npm-support", "npmsupport"} for n in check):
        return True
    desc = (v.get("description") or j.get("description") or "").lower()
    if "no longer supported" in desc or "package no longer supported" in desc:
        return True
    if v.get("deprecated") or j.get("deprecated"):
        return True
    return False


def check_registry_match(listed_repo, owner, pkg_repo, homepage, publishers, findings, kind, tool=None):
    listed = normalize_repo_url(listed_repo)
    typ = (tool or {}).get("type") if isinstance(tool, dict) else None
    cat = (tool or {}).get("category") if isinstance(tool, dict) else None
    mcpish = typ == "mcp" or cat in {"trading-brokers", "crypto"} or kind in {"npm", "PyPI"}
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
        # Missing VCS URL: medium for npm/PyPI (and for MCP / broker / crypto tools).
        sev = "medium" if mcpish or kind in {"npm", "PyPI"} else "low"
        findings.append(finding(
            "repo-mismatch",
            f"{kind} package does not declare a repository field that matches the listing",
            sev,
        ))
    if owner and publishers:
        if not publisher_matches(owner, publishers):
            findings.append(finding(
                "publisher-mismatch",
                "listed GitHub owner does not match the registry publisher",
                "low",
                publisher_match=False,
            ))
        else:
            # still record the boolean when we bother to check? only on mismatch, as specified
            pass


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


def normalize_repo_rel(rel):
    """Repo-relative path: strip a './' prefix only (not a leading dot), then normpath.

    Returns None for paths that escape the tree (`../` or absolute).
    """
    if not rel or not isinstance(rel, str):
        return None
    rel = rel.replace("\\", "/").strip()
    if rel.startswith("file:"):
        rel = rel.split(":", 1)[-1]
    if rel.startswith("./"):
        rel = rel[2:]
    rel = posixpath.normpath(rel)
    if rel in {".", ""}:
        return ""
    if rel == ".." or rel.startswith("../") or rel.startswith("/"):
        return None
    return rel


def join_repo_rel(rel_dir, rel):
    """Join a repo-relative directory with a (possibly relative) path; drop escapes."""
    if not isinstance(rel, str):
        return None
    rel = rel.replace("\\", "/").strip()
    if rel.startswith("./"):
        rel = rel[2:]
    rel_dir = (rel_dir or "").replace("\\", "/").strip()
    if rel_dir.startswith("./"):
        rel_dir = rel_dir[2:]
    joined = f"{rel_dir}/{rel}" if rel_dir else rel
    return normalize_repo_rel(joined if joined else ".")


def resolve_entry(rel, path_set):
    """Resolve a package main/bin/hook target the way Node does.

    Try the path as written, then common source extensions, then the
    directory's index.*, then a directory package.json (caller may follow
    its main). Returns the first path that exists in path_set, or None.
    """
    if not rel or not path_set:
        return None
    rel = normalize_repo_rel(rel)
    if rel is None:
        return None
    if not rel:
        return "index.js" if "index.js" in path_set else None
    cands = [rel]
    ext = os.path.splitext(rel)[1]
    if not ext:
        for e in (".js", ".mjs", ".cjs", ".ts", ".json", ".node"):
            cands.append(rel + e)
    base = rel.rstrip("/")
    for e in (".js", ".mjs", ".cjs", ".ts"):
        cands.append(f"{base}/index{e}")
    cands.append(f"{base}/package.json")
    seen = set()
    for c in cands:
        if c in seen:
            continue
        seen.add(c)
        if c in path_set:
            return c
    return None


def hook_file_targets(cmd):
    """Files referenced by an install hook (`node dist/setup`, `python -m pkg.mod`, `sh scripts/x.sh`)."""
    out = []
    if not cmd or not isinstance(cmd, str):
        return out
    chunks = re.split(r"\s*(?:&&|;|(?<!\|)\|(?!\|))\s*", cmd)
    for chunk in chunks:
        toks = _shell_tokens(chunk)
        if not toks:
            continue
        i = 0
        while i < len(toks):
            low = toks[i].lower()
            if low in {"python", "python3", "py"}:
                j = i + 1
                while j < len(toks) and toks[j].startswith("-") and toks[j] not in {"-m", "-c", "--module"}:
                    name = toks[j].split("=", 1)[0]
                    if name in {"-W", "-X", "--check-hash-based-pycs"} and "=" not in toks[j]:
                        j += 2
                        continue
                    j += 1
                if j < len(toks) and toks[j] in {"-m", "--module"} and j + 1 < len(toks):
                    path = toks[j + 1].replace(".", "/")
                    out.extend([path + ".py", path + "/__main__.py", path + "/__init__.py"])
                elif j < len(toks) and not toks[j].startswith("-"):
                    out.append(toks[j])
                break
            if low in {"sh", "bash", "zsh", "dash", "ash"}:
                j = i + 1
                while j < len(toks) and toks[j].startswith("-") and toks[j] != "-c":
                    j += 1
                if j < len(toks) and toks[j] != "-c" and not toks[j].startswith("-"):
                    out.append(toks[j])
                break
            if low in {"node", "tsx", "ts-node", "bun", "deno"}:
                j = i + 1
                if low in {"deno", "bun"} and j < len(toks) and toks[j].lower() == "run":
                    j += 1
                while j < len(toks) and toks[j].startswith("-"):
                    name = toks[j].split("=", 1)[0]
                    if name in {"-e", "-p", "-c", "--eval", "--print", "--require", "-r"} and "=" not in toks[j]:
                        j += 2
                        continue
                    j += 1
                if j < len(toks) and not toks[j].startswith("-"):
                    out.append(toks[j])
                break
            i += 1
        for tok in re.findall(r"(?:^|\s)(\S+\.(?:js|mjs|cjs|ts|sh|py|bash))\b", chunk):
            if not tok.startswith("-"):
                norm = normalize_repo_rel(tok)
                if norm:
                    out.append(norm)
    return out


def manifest_entries(path, pkg):
    """Paths named by package.json main / bin / exports / files / hook scripts."""
    rel_dir = path.replace("\\", "/").rsplit("/", 1)[0] if "/" in path.replace("\\", "/") else ""
    out = []

    def add(rel):
        if not isinstance(rel, str) or not rel:
            return
        rel = rel.split(":", 1)[-1] if rel.startswith("file:") else rel
        rel = rel.split("*", 1)[0].rstrip("/")
        joined = join_repo_rel(rel_dir, rel)
        if joined:
            out.append(joined)

    if not isinstance(pkg, dict):
        return out
    if isinstance(pkg.get("main"), str):
        add(pkg["main"])
    else:
        add("index.js")
    if isinstance(pkg.get("module"), str):
        add(pkg["module"])
    bin_ = pkg.get("bin")
    if isinstance(bin_, str):
        add(bin_)
    elif isinstance(bin_, dict):
        for v in bin_.values():
            if isinstance(v, str):
                add(v)
    exports = pkg.get("exports")
    def walk_exports(x):
        if isinstance(x, str):
            add(x)
        elif isinstance(x, dict):
            for v in x.values():
                walk_exports(v)
        elif isinstance(x, list):
            for v in x:
                walk_exports(v)
    walk_exports(exports)
    files = pkg.get("files")
    if isinstance(files, list):
        for v in files:
            if isinstance(v, str) and not any(ch in v for ch in "*?["):
                add(v)
    scripts = pkg.get("scripts") or {}
    if isinstance(scripts, dict):
        for hook, cmd in scripts.items():
            if hook not in INSTALL_HOOKS or not isinstance(cmd, str):
                continue
            for _name, sub in iter_hook_cmds(scripts, cmd, seen={hook}):
                for tok in hook_file_targets(sub):
                    add(tok)
    return out


def list_repo_files(owner, repo, branch=None):
    """Returns (info, sha, entries|None, truncated). entries is None when the tree could not be fetched."""
    info = gh_api(f"repos/{owner}/{repo}")
    if not info or not isinstance(info, dict):
        return None, None, None, False
    sha = (info.get("default_branch") if not branch else branch) or "HEAD"
    ref = gh_api(f"repos/{owner}/{repo}/git/ref/heads/{sha}")
    if isinstance(ref, dict) and ref.get("object", {}).get("sha"):
        sha = ref["object"]["sha"]
    elif isinstance(info.get("default_branch"), str) and not branch:
        sha = info["default_branch"]
    tree = gh_api(f"repos/{owner}/{repo}/git/trees/{sha}?recursive=1")
    if not tree or not isinstance(tree, dict):
        return info, sha, None, False
    entries = []
    for e in tree.get("tree") or []:
        if e.get("type") != "blob":
            continue
        path = e.get("path") or ""
        size = e.get("size") or 0
        entries.append({"path": path, "size": size, "sha": e.get("sha"), "large": size > MAX_FILE_BYTES})
    return info, (tree.get("sha") or sha), entries, bool(tree.get("truncated"))


def finalize_status(out, findings, truncated=False, incomplete=False):
    uniq, seen = [], set()
    for f in findings:
        k = (f["check"], f["file"], f["detail"], f["line"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(f)
    out["findings"] = uniq
    st = status_of(uniq)
    if st == "clean" and (truncated or incomplete):
        # A cap with no medium+ findings is a partial scan, not a concern.
        # Hard failures and a timeout/cap that never read a file stay incomplete.
        details = " ".join((f.get("detail") or "") for f in uniq)
        hard = bool(out.get("fetch_failed")) or any(
            s in details.lower()
            for s in ("not reachable", "could not read", "scan skipped:", "api budget", "github api remaining")
        )
        scanned = int(out.get("files_scanned") or 0)
        # A max-files cap is partial (some files were considered). A timeout
        # or incomplete flag with nothing actually scanned is incomplete.
        if hard or (incomplete and scanned <= 0):
            st = "incomplete"
        else:
            st = "partial"
    out["status"] = st
    out["truncated"] = bool(truncated)
    return stamp_result(out)


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
        "truncated": False,
        "coverage": {"scanned": 0, "matched": 0, "skipped_large": 0},
        "fetch_failed": [],
    }
    parsed = parse_repo(tool.get("repo") or "")
    if not tool.get("repo"):
        findings.append(finding("repo", "No source repository listed; static scan skipped", "info"))
        return finalize_status(out, findings)
    if not parsed:
        findings.append(finding("repo", f"Repository URL is not a GitHub repo we can list: {tool.get('repo')}", "medium"))
        return finalize_status(out, findings)
    owner, repo, branch, sub = parsed
    _SCAN_CTX.owner = owner
    listed = f"https://github.com/{owner}/{repo}"
    info, sha, entries, tree_truncated = list_repo_files(owner, repo, branch)
    if info is None or entries is None:
        findings.append(finding("repo", "Repository not reachable via the GitHub API; scan incomplete", "medium"))
        out["commit"] = sha
        return finalize_status(out, findings, incomplete=True)
    out["commit"] = sha
    if tree_truncated:
        out["notes"].append("GitHub tree was truncated; some paths may not have been listed")
    allow = allow_hosts_for(tool, owner)

    interesting_entries = [
        e for e in entries
        if not skip_path(e["path"]) and (interesting(e["path"], subpath=sub) or is_must_scan(e["path"]))
    ]
    path_set = {e["path"] for e in entries}
    skipped_large = 0

    # Phase 1: always take must-scan files (any size)
    must, rest = [], []
    for e in interesting_entries:
        if is_must_scan(e["path"]):
            must.append(e)
        else:
            rest.append(e)

    # We'll add hook/entry targets after reading manifests
    candidates = list(must)
    official = bool(tool.get("official"))
    npm_pkgs = []
    pypi_deps = []
    extra_targets = set()
    fetch_failed = []
    osv_failed = False
    incomplete = tree_truncated

    def scan_one(path, text, reachable=False):
        nonlocal osv_failed, incomplete
        if text is FETCH_FAILED or text is None:
            fetch_failed.append(path)
            findings.append(finding("repo", f"Could not read {path}", "medium", file=path))
            return
        out["files_scanned"] += 1
        base = os.path.basename(path).lower()
        # A genuine empty blob (e.g. empty requirements.txt) is not a fetch failure.
        # Empty package.json / pyproject.toml is an unparseable manifest, so keep going.
        if text == "" and base not in {"package.json", "pyproject.toml"}:
            return
        if base == "package.json":
            before = len(findings)
            pkg = check_package_json(path, text, findings)
            if any("unparseable manifest" in (f.get("detail") or "") for f in findings[before:]):
                incomplete = True
            if pkg:
                npm_pkgs.append((path, pkg))
                for rel in manifest_entries(path, pkg):
                    extra_targets.add(rel)
        if base == "setup.py":
            check_setup_py(path, text, findings)
            if CURL_PIPE.search(text) or BASH_FROM_CURL.search(text) or BASE64_PIPE.search(text) or BINARY_DL.search(text):
                check_shell_and_docker(path, text, findings)
        if base == "pyproject.toml":
            before = len(findings)
            pypi_deps.extend([(path, d) for d in extract_pypi_deps(text, "pyproject", findings, path)])
            if any("unparseable manifest" in (f.get("detail") or "") for f in findings[before:]):
                incomplete = True
        if base.startswith("requirements") and base.endswith(".txt"):
            pypi_deps.extend([(path, d) for d in extract_pypi_deps(text, "requirements")])
        if (
            base.startswith("dockerfile") or base.startswith("docker-compose") or base.startswith("compose.")
            or base.endswith((".sh", ".ps1", ".bash")) or base == "makefile"
            or path.replace("\\", "/").startswith(".github/workflows/")
        ):
            check_shell_and_docker(path, text, findings)
        else:
            if CURL_PIPE.search(text) or BASH_FROM_CURL.search(text) or BASE64_PIPE.search(text) or IEX_DOWNLOAD.search(text) or BINARY_DL.search(text):
                check_shell_and_docker(path, text, findings)
        check_obfuscation(path, text, findings, reachable=reachable)
        check_secrets_and_network(path, text, findings, allow, reachable=reachable)
        check_permissions(path, text, findings, official, tool.get("type"), tool.get("category"), reachable=reachable)

    scanned_paths = set()
    scanned_reachable = set()
    for e in candidates:
        path = e["path"]
        text = raw_file(owner, repo, sha, path)
        scan_one(path, text)
        scanned_paths.add(path)

    # hook / main / bin targets from manifests, always, any size.
    # Resolve extension-less and directory mains the way Node does.
    resolved_targets = []
    seen_t = set()
    followed_pkg = set()

    def follow_pkg_main(hit):
        """If resolve_entry landed on a package.json, follow its main one level."""
        if posixpath.basename(hit).lower() != "package.json" or hit in followed_pkg:
            return None
        followed_pkg.add(hit)
        text = raw_file(owner, repo, sha, hit)
        if text is FETCH_FAILED or not text:
            return None
        try:
            pkg = json.loads(text)
        except ValueError:
            return None
        rel_dir = posixpath.dirname(hit.replace("\\", "/"))
        main = pkg.get("main") if isinstance(pkg, dict) and isinstance(pkg.get("main"), str) else "index.js"
        joined = join_repo_rel(rel_dir, main)
        if not joined:
            return None
        return resolve_entry(joined, path_set) or (joined if joined in path_set else None)

    for rel in list(extra_targets):
        hit = resolve_entry(rel, path_set) or (rel if rel in path_set else None)
        if not hit:
            continue
        followed = follow_pkg_main(hit)
        for cand in (hit, followed):
            if cand and cand not in seen_t:
                resolved_targets.append(cand)
                seen_t.add(cand)

    by_path = {e["path"]: e for e in entries}
    for rel in resolved_targets:
        if rel in scanned_paths:
            if rel not in scanned_reachable:
                # First pass may have treated a test/doc path as unreachable
                # (e.g. bin → test/run.sh is must-scan). Re-check as reachable.
                text = raw_file(owner, repo, sha, rel)
                if text is not FETCH_FAILED and text is not None:
                    check_obfuscation(rel, text, findings, reachable=True)
                    check_secrets_and_network(rel, text, findings, allow, reachable=True)
                    check_permissions(rel, text, findings, official, tool.get("type"), tool.get("category"), reachable=True)
                scanned_reachable.add(rel)
            continue
        if rel not in path_set:
            continue
        text = raw_file(owner, repo, sha, rel)
        # Manifest main/bin/exports/hook targets are reachable even under
        # skipped dirs (dist/, build/, vendor/, test/, …).
        scan_one(rel, text, reachable=True)
        scanned_paths.add(rel)
        scanned_reachable.add(rel)

    # primary package dir from manifests we already saw
    npm_names = [(path, pkg.get("name")) for path, pkg in npm_pkgs if pkg.get("name") and not pkg.get("private")]
    selfs = [(path, d[1]) for path, d in pypi_deps if d[0] == "self"]
    prim = primary_package(npm_names + selfs, tool, owner, repo)
    primary_dir = None
    if prim:
        pp = prim[0].replace("\\", "/")
        primary_dir = pp.rsplit("/", 1)[0] if "/" in pp else ""

    # Phase 2: remaining source, cap, primary dir first, largest first
    remaining = [e for e in rest if e["path"] not in scanned_paths]
    remaining.sort(key=lambda e: (file_priority(e["path"], primary_dir), -e["size"], e["path"]))
    matched = len(interesting_entries) + sum(1 for r in extra_targets if r in path_set and r not in {e["path"] for e in interesting_entries})
    # unmatched large remaining past the cap
    cap = max(0, max_files)
    if len(remaining) > cap:
        dropped = remaining[cap:]
        skipped_large = sum(1 for e in dropped if e.get("large") or e["size"] > MAX_FILE_BYTES)
        # also count large files we never selected
        remaining = remaining[:cap]
        incomplete = True
        out["notes"].append(f"capped at {max_files} extra files ({len(dropped)} more matching paths not read)")
    else:
        skipped_large += sum(1 for e in remaining if e.get("large") and e["path"] not in scanned_paths and False)
        dropped = []
        skipped_large = sum(1 for e in entries if e.get("large") and e["path"] not in scanned_paths and e not in remaining and not is_must_scan(e["path"]))

    for e in remaining:
        path = e["path"]
        text = raw_file(owner, repo, sha, path)
        scan_one(path, text)
        scanned_paths.add(path)

    # typo / OSV for every package we scanned; registry identity only for the primary package
    # Read lockfiles (not as source) so a range finding can be confirmed or cleared.
    locks_by_dir = {}
    for e in entries:
        base = os.path.basename(e["path"]).lower()
        if base not in LOCK_BASENAMES or in_vendor_dir(e["path"]):
            continue
        text = raw_file(owner, repo, sha, e["path"])
        parsed = parse_lockfile(e["path"], text)
        d = e["path"].replace("\\", "/")
        d = d.rsplit("/", 1)[0] if "/" in d else ""
        if d in locks_by_dir and isinstance(locks_by_dir[d], dict) and parsed:
            for k, vs in parsed.items():
                locks_by_dir[d].setdefault(k, []).extend(vs)
        elif parsed is not None:
            locks_by_dir[d] = parsed
        elif d not in locks_by_dir:
            locks_by_dir[d] = None  # unreadable/unparseable: keep "not checked"

    for path, pkg in npm_pkgs:
        if check_typos_and_osv(extract_npm_deps(pkg), "npm", findings, file=path,
                               lock_versions=lock_versions_for(path, locks_by_dir)):
            osv_failed = True
    prim_npm = primary_package(npm_names, tool, owner, repo)
    if prim_npm:
        path, name = prim_npm
        out["packages"]["npm"] = name
        reg = npm_registry(name)
        if reg is REGISTRY_ERROR:
            incomplete = True
            out["notes"].append(f"npm registry lookup for {name} failed")
        elif reg:
            pkg_repo, home, maintainers = repo_from_npm(reg)
            check_registry_match(listed, owner, pkg_repo, home, maintainers, findings, "npm", tool=tool)
            if npm_held_or_deprecated(reg):
                findings.append(finding(
                    "publisher-mismatch",
                    "npm package appears unmaintained or held by the registry",
                    "medium",
                ))
            latest = (reg.get("dist-tags") or {}).get("latest")
            vers = (reg.get("versions") or {}).get(latest) or {}
            # published latest install hooks (tarball may differ from the repo)
            scripts = vers.get("scripts") if isinstance(vers.get("scripts"), dict) else {}
            if scripts:
                check_package_json(
                    f"npm:{name}@{latest}",
                    json.dumps({"name": name, "scripts": scripts}),
                    findings,
                )
            # OSV against the published latest, not only the repo version
            if latest:
                if check_typos_and_osv([("self", name, latest)], "npm", findings, file=f"npm:{name}@{latest}",
                                       lock_versions=lock_versions_for(path, locks_by_dir)):
                    osv_failed = True
        else:
            out["notes"].append(f"npm package {name} was not found on the registry")

    if pypi_deps:
        by_file = {}
        for path, dep in pypi_deps:
            by_file.setdefault(path, []).append(dep)
        for path, deps in by_file.items():
            if check_typos_and_osv(deps, "PyPI", findings, file=path,
                                   lock_versions=lock_versions_for(path, locks_by_dir)):
                osv_failed = True
        prim_py = primary_package(selfs, tool, owner, repo)
        if prim_py:
            path, name = prim_py
            out["packages"]["pypi"] = name
            reg = pypi_registry(name)
            if reg is REGISTRY_ERROR:
                incomplete = True
                out["notes"].append(f"PyPI registry lookup for {name} failed")
            elif reg:
                pkg_repo, home, authors = repo_from_pypi(reg)
                check_registry_match(listed, owner, pkg_repo, home, authors, findings, "PyPI", tool=tool)
                latest = ((reg.get("info") or {}).get("version"))
                if latest:
                    if check_typos_and_osv([("self", name, latest)], "PyPI", findings, file=f"pypi:{name}@{latest}",
                                           lock_versions=lock_versions_for(path, locks_by_dir)):
                        osv_failed = True
            else:
                out["notes"].append(f"PyPI package {name} was not found on the registry")

    if fetch_failed:
        incomplete = True
        out["fetch_failed"] = fetch_failed
    if osv_failed:
        incomplete = True

    out["coverage"] = {
        "scanned": out["files_scanned"],
        "matched": max(matched, len(interesting_entries)),
        "skipped_large": skipped_large,
    }
    if skipped_large:
        out["notes"].append(f"{skipped_large} blob(s) over {MAX_FILE_BYTES} bytes were not fully read")
    truncated = bool(tree_truncated or (out["notes"] and any("capped at" in n for n in out["notes"])))
    return finalize_status(out, findings, truncated=truncated, incomplete=incomplete)


def safe_scan(tool, max_files, timeout=None):
    deadline = float(timeout if timeout is not None else TOOL_DEADLINE)
    if rate_budget_low():
        return stamp_result({
            "id": tool["id"],
            "name": tool.get("name"),
            "status": "incomplete",
            "date": NOW.strftime("%Y-%m-%d"),
            "repo": tool.get("repo"),
            "commit": None,
            "findings": [finding("repo", "Scan skipped: GitHub API remaining calls are below the floor; retry later", "medium")],
            "files_scanned": 0,
            "packages": {},
            "notes": ["github-rate-floor"],
            "truncated": False,
            "coverage": {"scanned": 0, "matched": 0, "skipped_large": 0},
        })
    done, v = _bounded(lambda: scan_tool(tool, max_files=max_files), deadline)
    if done and not isinstance(v, BaseException):
        return v
    if not done:
        # A timeout that produced no scan result (0 files) is incomplete, not
        # a partial scan: nothing is known yet.
        return stamp_result({
            "id": tool["id"],
            "name": tool.get("name"),
            "status": "incomplete",
            "date": NOW.strftime("%Y-%m-%d"),
            "repo": tool.get("repo"),
            "commit": None,
            "findings": [finding("repo", f"Scan incomplete: scanner timed out after {deadline:g}s", "info")],
            "files_scanned": 0,
            "packages": {},
            "notes": ["scan-timeout"],
            "truncated": True,
            "coverage": {"scanned": 0, "matched": 0, "skipped_large": 0},
        })
    why = f"scanner error ({type(v).__name__}: {v})"
    return stamp_result({
        "id": tool["id"],
        "name": tool.get("name"),
        "status": "incomplete",
        "date": NOW.strftime("%Y-%m-%d"),
        "repo": tool.get("repo"),
        "commit": None,
        "findings": [finding("repo", f"Scan incomplete: {why}", "medium")],
        "files_scanned": 0,
        "packages": {},
        "notes": ["scan-error"],
        "truncated": False,
        "coverage": {"scanned": 0, "matched": 0, "skipped_large": 0},
    })



def parse_args(args, known_ids):
    only, dry, out_dir, jobs, max_files, timeout = None, False, DEFAULT_OUT, 4, MAX_FILES_DEFAULT, TOOL_DEADLINE
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
        elif a.startswith("--timeout="):
            timeout = float(a.split("=", 1)[1])
        elif a in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        else:
            sys.exit(
                f"security_scan.py: unknown argument {a!r} "
                "(usage: security_scan.py [--dry-run] [--only=id1,id2] [--out-dir=DIR] [--jobs=N] [--timeout=SEC])"
            )
        i += 1
    return only, dry, out_dir, max(1, jobs), max_files, timeout


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
    only, dry, out_dir, jobs, max_files, timeout = parse_args(argv if argv is not None else sys.argv[1:], known)
    todo = [t for t in tools if not only or t["id"] in only]
    t0 = time.monotonic()
    os.makedirs(CACHE_DIR, exist_ok=True)
    with ThreadPoolExecutor(jobs) as ex:
        results = list(ex.map(lambda t: safe_scan(t, max_files, timeout=timeout), todo))
    runtime = round(time.monotonic() - t0, 2)
    if not dry:
        for r in results:
            write_result(out_dir, r)
    by = Counter(r["status"] for r in results)
    summary = {
        "checked_at": NOW.isoformat(),
        "scanner_commit": SCANNER_COMMIT,
        "rules_version": RULES_VERSION,
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
