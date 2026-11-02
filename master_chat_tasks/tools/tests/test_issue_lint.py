"""Tests for issue.py prompt lint (min plan A-3, 31 Oct)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
MT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import issue  # noqa: E402

BASE = "Board id: `<SHA>`\npython3 tools/name_session.py <SHA>\n"


class Lint(unittest.TestCase):
    def test_placeholder_is_hard(self):
        hard, _ = issue.lint(BASE + "Copy [[SLUG]] to [[OUT_DIR]].\n")
        self.assertEqual(len(hard), 1)
        self.assertIn("[[OUT_DIR]], [[SLUG]]", hard[0])

    def test_two_oracle_counts_hard_kit_lines_ignored(self):
        hard, _ = issue.lint(BASE + "Run oracle x3, owner, nop.\nLater run oracle-1..oracle-5.\n")
        self.assertEqual(len(hard), 1)
        self.assertIn("x3 at line 3", hard[0])
        self.assertIn("x5 at line 4", hard[0])
        hard, _ = issue.lint(BASE + "Run oracle x3.\nKEEP: Oracle x3 per Ayush; the kit asks oracle x5.\n")
        self.assertEqual(hard, [])
        hard, _ = issue.lint(BASE + "oracle x3 then oracle 1.0x3 on the same tree; oracle-1..oracle-3\n")
        self.assertEqual(hard, [])

    def test_gate_target_needs_decision_row(self):
        _, warn = issue.lint(BASE + "Paid run gate final < 50.\n", "no-such-slug-xyz")
        self.assertEqual(len(warn), 1)
        self.assertIn("final<50 differs from the live gate final<40", warn[0])
        _, warn = issue.lint(BASE + "Paid run gate tests<85, rubric<85, final<40.\n", "no-such-slug-xyz")
        self.assertEqual(warn, [])

    def test_bar_needs_reachable_line(self):
        _, warn = issue.lint(BASE + "Bar: predicted final <= 35.\n")
        self.assertEqual(len(warn), 1)
        self.assertIn("no 'Reachable:' line", warn[0])
        _, warn = issue.lint(BASE + "Bar: predicted final <= 35.\nReachable: judge.toml may change; R1-R4 cut.\n")
        self.assertEqual(warn, [])

    def test_cold_chain_go_is_caught(self):  # the 30 Oct 12:00 contradiction (judge frozen, bar 35)
        f = MT / "prompts" / "issued" / "cold-chain-backbone-quote" / "20261030T1200_go_cap60.md"
        if not f.is_file():
            self.skipTest("prompt not present")
        hard, warn = issue.lint(f.read_text(), "cold-chain-backbone-quote")
        self.assertEqual(hard, [])
        self.assertTrue(any("Reachable" in w for w in warn))


class LintCli(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="lint-tests-", dir="/tmp"))
        shutil.copytree(TOOLS, self.root / "tools", ignore=shutil.ignore_patterns("tests", "__pycache__"))
        (self.root / "registry").mkdir()
        shutil.copy2(MT / "registry" / "tasks.json", self.root / "registry" / "tasks.json")
        for f in ("board.json", "pending.db", "decisions.jsonl"):
            shutil.copy2(MT / f, self.root / f)
        self.env = {k: v for k, v in os.environ.items() if k != "AUTO_RUN"}
        self.env["MT_ROOT"] = str(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_issue(self, *args):
        return subprocess.run([sys.executable, str(self.root / "tools" / "issue.py"), *map(str, args)],
                              cwd=self.root, env=self.env, capture_output=True, text=True)

    def test_lint_mode_exit_codes(self):
        d = self.root / "d.md"
        d.write_text(BASE + "[[SLUG]]\n")
        self.assertEqual(self.run_issue("--lint", d).returncode, 1)
        d.write_text(BASE + "predicted final <= 35\n")
        r = self.run_issue("--lint", d)
        self.assertEqual((r.returncode, r.stdout.startswith("WARN")), (0, True))
        d.write_text(BASE + "plain\n")
        self.assertEqual(self.run_issue("--lint", d).stdout.strip(), "lint clean")

    def test_issue_refuses_then_force_lint_logs(self):
        d = self.root / "d.md"
        d.write_text(BASE + "predicted final <= 35\n")
        out = self.root / "out_<SHA>"
        r = self.run_issue("lint-test-slug", "adhoc", d, out, "--dry-run")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSED (lint warnings)", r.stderr)
        d.write_text(BASE + "[[SLUG]]\n")
        r = self.run_issue("lint-test-slug", "adhoc", d, out, "--dry-run", "--force-lint", "x")
        self.assertIn("REFUSED (lint)", r.stderr)  # hard findings ignore --force-lint
        d.write_text(BASE + "predicted final <= 35\n")
        before = (self.root / "decisions.jsonl").read_text()
        r = self.run_issue("lint-test-slug", "adhoc", d, out, "--dry-run", "--force-lint", "judge may change")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("DRY RUN ok", r.stdout)
        self.assertEqual((self.root / "decisions.jsonl").read_text(), before)  # dry run writes nothing


if __name__ == "__main__":
    unittest.main()
