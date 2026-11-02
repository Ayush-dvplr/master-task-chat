"""Tests for plan v2 A1-A4 (issue.py, intake.py, status.py, repackage_one.py).

Every test runs the tools as subprocesses against a temp copy of master_chat_tasks under /tmp
(tools/, board.json, registry/, pending.db, decisions.jsonl) with MT_ROOT pointing at it.
The harness tree (jobs/, Tasks_INPUT/, Output_RFP/) is only read.
"""
import hashlib
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
H = MT.parent / "Terminal_2.0_Harbor_Harness"
COLD, DISTRICT, SENT = "cold-chain-backbone-quote", "district-heat-flex-procurement", "sentinel-policy-recompute"


def snapshot(*dirs):
    out = {}
    for d in dirs:
        for p in Path(d).rglob("*"):
            if p.is_file():
                st = p.stat()
                out[str(p)] = (st.st_size, st.st_mtime_ns)
    return out


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="E1-tests-", dir="/tmp"))
        shutil.copytree(TOOLS, self.root / "tools", ignore=shutil.ignore_patterns("tests", "__pycache__"))
        (self.root / "registry").mkdir()
        for f in ("tasks.json", "scores.jsonl"):
            shutil.copy2(MT / "registry" / f, self.root / "registry" / f)
        for f in ("board.json", "pending.db", "decisions.jsonl"):
            shutil.copy2(MT / f, self.root / f)
        self.env = {k: v for k, v in os.environ.items() if k != "AUTO_RUN"}
        self.env["MT_ROOT"] = str(self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run_tool(self, tool, *args, env=None, tools=None):
        return subprocess.run([sys.executable, str((tools or self.root / "tools") / tool), *map(str, args)],
                              cwd=self.root, env=env or self.env, capture_output=True, text=True)

    def tasks(self):
        return json.loads((self.root / "registry" / "tasks.json").read_text())

    def set_pipeline(self, slug, **kv):
        t = self.tasks()
        p = next(x for x in t["tasks"] if x["slug"] == slug).setdefault("pipeline", {})
        for k, v in kv.items():
            if v is None:
                p.pop(k, None)
            else:
                p[k] = v
        (self.root / "registry" / "tasks.json").write_text(json.dumps(t, indent=1))

    def add_rows(self, slug, kind, n, issued="2026-10-28 10:00"):
        b = json.loads((self.root / "board.json").read_text())
        for i in range(n):
            b["rows"].append({"sha": f"t{kind[:3]}{i:03d}", "slug": slug, "step": kind, "prompt": "", "result": "",
                              "status": "done", "pending_id": "", "issued": issued, "note": "", "kind": kind, "updated": ""})
        (self.root / "board.json").write_text(json.dumps(b))


class A1Issue(Base):
    SLUG = "e1-test-task"

    def setUp(self):
        super().setUp()
        t = self.tasks()
        t["tasks"].append({"slug": self.SLUG, "pipeline": {"stage": "pushed"}})
        (self.root / "registry" / "tasks.json").write_text(json.dumps(t, indent=1))
        self.draft = self.root / "draft.md"
        self.draft.write_text("Board id: `<SHA>`\npython3 tools/name_session.py <SHA>\n")

    def issue(self, kind, *extra, env=None):
        return self.run_tool("issue.py", self.SLUG, kind, self.draft, "out/<SHA>", *extra, env=env)

    def test_ql_kind_in_help(self):
        self.assertIn("ql", self.run_tool("issue.py", "--help").stdout)

    def test_ql_not_refused_by_time_box(self):
        self.add_rows(self.SLUG, "run", 9)
        r = self.issue("ql", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("DRY RUN ok", r.stdout)
        r = self.issue("run", "--dry-run")  # negative: a counted kind is still boxed
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("time box: 9 sessions", r.stderr)

    def test_ql_sessions_not_counted(self):
        self.add_rows(self.SLUG, "ql", 9)
        self.assertEqual(self.issue("run", "--dry-run").returncode, 0)

    def test_open_ql_round_frees_qc_fix_harden(self):
        self.add_rows(self.SLUG, "run", 9)
        self.set_pipeline(self.SLUG, ql_round="1", ql_last="")
        for k in ("qc", "fix", "harden"):
            r = self.issue(k, "--dry-run")
            self.assertEqual(r.returncode, 0, f"{k}: {r.stderr}")
        self.set_pipeline(self.SLUG, ql_last="closed 10-29 01:00 x")  # closed round: pushed counts as passed
        r = self.issue("qc", "--dry-run")
        self.assertIn("already passed QC (stage pushed)", r.stderr)
        self.assertIn("time box", r.stderr)

    def test_pushed_without_ql_is_passed(self):
        r = self.issue("harden", "--dry-run")
        self.assertIn("no harden after PASS", r.stderr)

    def test_time_box_resets_on_stage_change(self):
        self.add_rows(self.SLUG, "run", 9)
        self.assertNotEqual(self.issue("run", "--dry-run").returncode, 0)
        self.assertEqual(self.run_tool("status.py", "set", self.SLUG, "stage=probe").returncode, 0)
        self.assertIn("stage_since", next(x for x in self.tasks()["tasks"] if x["slug"] == self.SLUG)["pipeline"])
        r = self.issue("run", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)

    def _override_row(self, *extra, env=None):
        self.add_rows(self.SLUG, "run", 9)
        r = self.issue("run", "--override", "ok go", *extra, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads((self.root / "decisions.jsonl").read_text().splitlines()[-1])

    def test_override_row_by_flag(self):
        row = self._override_row("--by", "Ayush (chat)")
        self.assertEqual(row["by"], "Ayush (chat)")
        self.assertNotIn("who", row)

    def test_override_row_by_default_ayush(self):
        self.assertEqual(self._override_row()["by"], "Ayush")

    def test_override_row_by_auto(self):
        self.assertEqual(self._override_row(env={**self.env, "AUTO_RUN": "1"})["by"], "master (auto)")

    def test_same_minute_suffix(self):
        names = []
        for _ in range(3):
            r = self.issue("ql")
            self.assertEqual(r.returncode, 0, r.stderr)
        names = sorted(p.name for p in (self.root / "prompts" / "issued" / self.SLUG).iterdir())
        if len({n[:13] for n in names}) == 1:  # all three in the same minute
            self.assertEqual([n[14:] for n in names], ["ql.md", "ql_2.md", "ql_3.md"])
        self.assertEqual(len(names), 3)


class A2Intake(Base):
    def intake(self, job, *extra):
        return self.run_tool("intake.py", "--job", job, "--harness", H, *extra)

    def test_tree_sha_values(self):
        sys.path.insert(0, str(TOOLS))
        import intake
        # min plan 31 Oct: live bundles change after freeze/push, so compare with the shell method, not pinned shas
        cmd = "find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -c1-12"
        for slug in (COLD, DISTRICT):
            d = H / "Tasks_INPUT" / slug
            sh = subprocess.run(cmd, shell=True, cwd=d, capture_output=True, text=True).stdout.strip()
            self.assertEqual(intake.tree_sha(d), sh, slug)

    def test_tree_sha_matches_shell(self):
        d = self.root / "tree"
        (d / "a b").mkdir(parents=True)
        (d / "a b" / "x.txt").write_text("1")
        (d / "B").write_text("2")
        (d / "_c").write_text("3")
        os.symlink(d / "B", d / "link")
        sh = subprocess.run('find . -type f | LC_ALL=C sort | xargs -I{} shasum -a 256 "{}" | shasum -a 256 | cut -c1-12',
                            shell=True, cwd=d, capture_output=True, text=True).stdout.strip()
        sys.path.insert(0, str(TOOLS))
        import intake
        self.assertEqual(intake.tree_sha(d), sh)

    def test_gate_text_and_not_met(self):
        import re
        for job in (DISTRICT, SENT):
            r = self.intake(job)
            m = re.search(r"scores tests (\S+) rubric (\S+) overall (\S+)", r.stdout)
            t, ru, o = map(float, m.groups())
            want = "MET" if (t < 85 and ru < 85 and o < 40) else "not met"
            self.assertIn(f"gate (tests<85, rubric<85, final<40): {want}", r.stdout, job)
        src = (TOOLS / "intake.py").read_text()
        self.assertNotIn("o < 50", src)
        self.assertNotIn("overall<50", src)
        self.assertEqual(src.count("FINAL_GATE = 40"), 1)

    def test_regrade_valid_false_and_true(self):
        before = (self.root / "registry" / "scores.jsonl").read_bytes()
        r = self.intake(SENT, "--event", "regrade")
        self.assertEqual(r.returncode, 0, r.stderr)
        row = json.loads(r.stdout.split("would append row (no --apply, nothing written): ")[1].splitlines()[0])
        self.assertIs(row["valid"], False)
        self.assertEqual(row["tree_sha"], "583e77e1ae94")
        r = self.intake(SENT, "--event", "regrade", "--ayush-ok", "yes use the regrade")
        row = json.loads(r.stdout.split("nothing written): ")[1].splitlines()[0])
        self.assertIs(row["valid"], True)
        self.assertEqual(row["ayush_ok"], "yes use the regrade")
        self.assertEqual((self.root / "registry" / "scores.jsonl").read_bytes(), before)

    def test_regrade_apply_writes_row(self):
        r = self.intake(SENT, "--event", "regrade", "--apply")
        self.assertEqual(r.returncode, 0, r.stderr)
        row = json.loads((self.root / "registry" / "scores.jsonl").read_text().splitlines()[-1])
        self.assertEqual((row["event"], row["valid"], row["tree_sha"]), ("regrade", False, "583e77e1ae94"))

    def test_ayush_ok_only_for_regrade(self):
        self.assertNotEqual(self.intake(SENT, "--event", "run", "--ayush-ok", "x").returncode, 0)

    def test_gate_run_refused_empty_and_mismatch(self):
        for ev in ("gate_run", "ql_rerun"):
            self.set_pipeline(COLD, tree_sha=None)
            r = self.intake(COLD, "--event", ev)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn(f"registry tree_sha empty: set it at freeze (status.py set {COLD} tree_sha=...)", r.stderr)
            self.set_pipeline(COLD, tree_sha="000000000000")
            r = self.intake(COLD, "--event", ev, "--apply")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("!= registry tree_sha 000000000000", r.stderr)
            sys.path.insert(0, str(TOOLS))
            import intake
            live = intake.tree_sha(H / "Tasks_INPUT" / COLD)
            self.set_pipeline(COLD, tree_sha=live)
            r = self.intake(COLD, "--event", ev)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn(f'"tree_sha": "{live}"', r.stdout)
        self.assertEqual((self.root / "registry" / "scores.jsonl").read_bytes(),
                         (MT / "registry" / "scores.jsonl").read_bytes())


class A3Status(Base):
    def test_bad_field_lists_new_fields(self):
        before = (self.root / "registry" / "tasks.json").read_bytes()
        r = self.run_tool("status.py", "set", COLD, "zz=1")
        self.assertNotEqual(r.returncode, 0)
        for f in ("tree_sha", "ql_round", "ql_last"):
            self.assertIn(f"'{f}'", r.stderr)
        self.assertEqual((self.root / "registry" / "tasks.json").read_bytes(), before)

    def test_set_new_fields(self):
        r = self.run_tool("status.py", "set", COLD, "tree_sha=8ca9c267f59b", "ql_round=1", "ql_last=open")
        self.assertEqual(r.returncode, 0, r.stderr)
        p = next(x for x in self.tasks()["tasks"] if x["slug"] == COLD)["pipeline"]
        self.assertEqual((p["tree_sha"], p["ql_round"], p["ql_last"]), ("8ca9c267f59b", "1", "open"))

    def test_stage_since_only_on_change(self):
        self.run_tool("status.py", "set", COLD, "stage=gate_runs")
        first = next(x for x in self.tasks()["tasks"] if x["slug"] == COLD)["pipeline"]["stage_since"]
        self.set_pipeline(COLD, stage_since="2026-10-01 00:00")
        self.run_tool("status.py", "set", COLD, "stage=gate_runs")
        self.assertEqual(next(x for x in self.tasks()["tasks"] if x["slug"] == COLD)["pipeline"]["stage_since"],
                         "2026-10-01 00:00")
        self.run_tool("status.py", "set", COLD, "stage=pl_ready")
        self.assertNotEqual(next(x for x in self.tasks()["tasks"] if x["slug"] == COLD)["pipeline"]["stage_since"],
                            "2026-10-01 00:00")
        self.assertTrue(first)


class A4Repackage(Base):
    def repack(self, *extra):
        # the real tools/ copy so package_rfp_bundles.py resolves; MT_ROOT points the registry at the temp copy
        return self.run_tool("repackage_one.py", "--slug", SENT, "--run-dir", H / "jobs" / SENT,
                             "--task-dir", H / "Tasks_INPUT" / SENT, *extra, tools=TOOLS)

    def repack_dirs(self):
        return set(Path("/tmp").glob(f"repack-{SENT}-*"))

    def test_refuses_on_mismatch_and_empty(self):
        out = self.root / "out"
        before = self.repack_dirs()
        self.set_pipeline(SENT, tree_sha="000000000000")
        r = self.repack("--output-root", out, "--dry-run")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("!= registry tree_sha 000000000000", r.stderr)
        self.set_pipeline(SENT, tree_sha=None)
        r = self.repack("--output-root", out)
        self.assertIn("registry tree_sha empty", r.stderr)
        self.assertEqual(self.repack_dirs(), before)
        self.assertFalse(out.exists())

    def test_dry_run_writes_nothing_outside_tmp(self):
        self.set_pipeline(SENT, tree_sha="583e77e1ae94")
        out = self.root / "out"
        shutil.copytree(H / "Output_RFP" / SENT, out / SENT)
        watched = [H / "Output_RFP" / SENT, H / "jobs" / SENT, H / "Tasks_INPUT" / SENT, MT / "registry", out]
        snap = snapshot(*watched)
        before = self.repack_dirs()
        r = self.repack("--output-root", out, "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("DRY RUN: nothing copied", r.stdout)
        self.assertEqual(snapshot(*watched), snap)
        new = self.repack_dirs() - before
        self.assertEqual(len(new), 1)
        work = new.pop()
        self.addCleanup(shutil.rmtree, work, True)
        self.assertTrue((work / "staged" / SENT / "task.toml").is_file())
        self.assertFalse((work / "old").exists())
        for p in work.rglob("*"):
            self.assertTrue(str(p.resolve()).startswith(("/tmp/", "/private/tmp/")))

    def test_real_copy_into_fake_root(self):
        self.set_pipeline(SENT, tree_sha="583e77e1ae94")
        out = self.root / "out"
        shutil.copytree(H / "Output_RFP" / SENT, out / SENT)
        old = snapshot(out)
        before = self.repack_dirs()
        r = self.repack("--output-root", out)
        self.assertEqual(r.returncode, 0, r.stderr)
        work = (self.repack_dirs() - before).pop()
        self.addCleanup(shutil.rmtree, work, True)
        self.assertEqual(len(snapshot(work / "old" / SENT)), len(old))
        staged = (work / "staged.sha256").read_text()
        self.assertEqual((work / "after.sha256").read_text(), staged)
        f = out / SENT / "task.toml"
        self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(),
                         hashlib.sha256((H / "Tasks_INPUT" / SENT / "task.toml").read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
