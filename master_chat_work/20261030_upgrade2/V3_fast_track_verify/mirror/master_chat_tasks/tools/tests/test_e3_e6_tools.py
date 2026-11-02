"""E3-E6 (board 478e1df): decide.py, registry_check.py, master_queue gate runs and cancel, package exit.

Everything runs on temp files; the live decisions.jsonl, registry, queue state and jobs are never touched.
E3_MQ / E3_PRB point the MQ and package tests at another copy (used for the negative run on the backups).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent.parent
MT = TOOLS.parent
H = MT.parent / "Terminal_2.0_Harbor_Harness"
MQ_PATH = Path(os.environ.get("E3_MQ") or H / "scripts/master_queue.py")
PRB_PATH = Path(os.environ.get("E3_PRB") or H / "scripts/package_rfp_bundles.py")


def load_mq():
    spec = importlib.util.spec_from_file_location("mq_under_test", MQ_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses look the module up while the class is built
    spec.loader.exec_module(mod)
    return mod


class Tmp(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="E3-tests-", dir="/Users/mac/Desktop/Terminal Bench/master_chat_work/20261030_upgrade2/V3_fast_track_verify/tmp"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def tool(self, name: str, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(TOOLS / name), *args], capture_output=True, text=True,
                              env={**os.environ, **(env or {})}, cwd=self.tmp)


class E4Decide(Tmp):
    OLD = '{"ist": "2026-10-29 01:57", "who": "master", "decision": "old row", "verbatim": "x"}\n'

    def test_decide_appends_one_valid_row(self) -> None:  # R5-23
        f = self.tmp / "decisions.jsonl"
        f.write_text(self.OLD)
        r = self.tool("decide.py", "--by", "master (auto)", "--slug", "cold-chain", "--what", "freeze tree",
                      "--words", "Target <40 now", "--file", str(f))
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = f.read_text().splitlines()
        self.assertEqual(lines[0] + "\n", self.OLD)  # old row byte-identical
        row = json.loads(lines[1])
        self.assertEqual(list(row), ["ist", "by", "slug", "what", "words"])
        self.assertRegex(row["ist"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")
        self.assertEqual((row["by"], row["slug"], row["what"], row["words"]),
                         ("master (auto)", "cold-chain", "freeze tree", "Target <40 now"))
        self.assertEqual(r.stdout.strip(), lines[1])
        env_file = self.tmp / "env.jsonl"
        env_file.write_text(self.OLD.rstrip("\n"))  # no trailing newline: the new row still gets its own line
        r = self.tool("decide.py", "--by", "worker 478e1df", "--what", "E3 done", env={"DECIDE_FILE": str(env_file)})
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = [json.loads(l) for l in env_file.read_text().splitlines()]
        self.assertEqual(rows[1], {"ist": rows[1]["ist"], "by": "worker 478e1df", "what": "E3 done"})
        for by in ("ayush", "master"):
            self.assertEqual(self.tool("decide.py", "--by", by, "--what", "w", "--file", str(f)).returncode, 0)

    def test_decide_refuses_bad_by_and_empty_what(self) -> None:  # R5-23
        f = self.tmp / "decisions.jsonl"
        f.write_text(self.OLD)
        for args in (["--by", "Ayush", "--what", "x"], ["--by", "master (night)", "--what", "x"],
                     ["--by", "worker xyz", "--what", "x"], ["--by", "ayush", "--what", "   "],
                     ["--by", "ayush"], ["--what", "x"]):
            r = self.tool("decide.py", *args, "--file", str(f))
            self.assertEqual(r.returncode, 2, (args, r.stdout, r.stderr))
        self.assertEqual(f.read_text(), self.OLD)


class E6RegistryCheck(Tmp):
    def tasks(self, rows: list[dict]) -> Path:
        p = self.tmp / "tasks.json"
        p.write_text(json.dumps({"updated_ist": "x", "tasks": rows}))
        return p

    def test_registry_check_reports_drift_exit_1_read_only(self) -> None:  # R5-16
        p = self.tasks([{"slug": "a", "pipeline": {"traj_final": 65.59}, "build": {"oracle": 1.0}, "runs": [{"t": 1}]},
                        {"slug": "b", "pipeline": {"traj_final": "51.45"}, "build": {"oracle": None}, "runs": [{"t": 2}]},
                        {"slug": "c", "pipeline": {"traj_final": None}, "build": {"oracle": "1.0 x3"}, "runs": [{"t": "3"}]}])
        before = hashlib.sha256(p.read_bytes()).hexdigest()
        r = self.tool("registry_check.py", "--file", str(p))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("3 tasks, 3 field(s) with type drift", r.stdout)
        self.assertRegex(r.stdout, r"pipeline\.traj_final: (number x1, string x1|string x1, number x1)")
        self.assertIn('string: b = "51.45"', r.stdout)
        self.assertIn('string: c = "1.0 x3"', r.stdout)
        self.assertIn("runs[].t:", r.stdout)
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), before)

    def test_registry_check_clean_exit_0_and_unreadable_exit_2(self) -> None:  # R5-16
        p = self.tasks([{"slug": "a", "x": 1.5, "n": None}, {"slug": "b", "x": 2, "n": "note"}])
        r = self.tool("registry_check.py", env={"REGISTRY_FILE": str(p)})
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("0 field(s) with type drift", r.stdout)
        self.assertEqual(self.tool("registry_check.py", "--file", str(self.tmp / "missing.json")).returncode, 2)


class E6MasterQueue(Tmp):
    def setUp(self) -> None:
        super().setUp()
        self.mq = load_mq()

    def state(self, **kw) -> dict:
        return {"max_concurrent": 1, "paused": False, "pause_reason": "", "queue": [{"task": "q1"}], "runs": [], **kw}

    def launch_with(self, procs: list[str], budget=(16.0, 16384)) -> list[str]:
        mq = self.mq
        table = [(100 + i, 900 + i, 60, cmd) for i, cmd in enumerate(procs)]
        ctx = mq.Ctx(root=self.tmp)
        with mock.patch.object(mq, "ps_table", return_value=table), \
                mock.patch.object(mq, "docker_budget", return_value=budget), \
                mock.patch.object(mq, "task_resources", return_value=(2.0, 4096)), \
                mock.patch.object(mq, "launch", side_effect=lambda c, s, item: f"launched {item['task']}"):
            return mq.maybe_launch(ctx, self.state())

    def test_mq_gate_runs_do_not_hold_a_slot(self) -> None:  # R5-12
        gates = ["/w/.venv/bin/harbor run --agent oracle -p /Users/mac/Desktop/Terminal Bench/master_chat_work/20261030_upgrade2/V3_fast_track_verify/tmp/qc/task -n 1",
                 "/w/.venv/bin/harbor run -p /Users/mac/Desktop/Terminal Bench/master_chat_work/20261030_upgrade2/V3_fast_track_verify/tmp/qc/task --agent nop", "/w/.venv/bin/harbor run -a oracle -p t"]
        self.assertEqual(self.launch_with(gates), ["launched q1"])
        paid = ["/w/.venv/bin/harbor run -p Tasks_INPUT/other --agent claude-code"]
        self.assertEqual(self.launch_with(paid), [])  # a paid run elsewhere still takes the slot
        self.assertEqual(self.launch_with(gates, budget=(7.0, 16384)), [])  # gate runs still count for Docker

    def test_mq_cancel_clears_pause_when_queue_empty(self) -> None:  # R5-14
        q = self.tmp / ".master-queue"
        q.mkdir()
        q.joinpath("state.json").write_text(json.dumps(self.state(
            paused=True, pause_reason="subscription usage limit reached during q1", pause_task="q1",
            queue=[{"task": "q1"}, {"task": "q2"}])))
        root = ["--root", str(self.tmp)]
        with mock.patch("builtins.print") as out:
            self.assertEqual(self.mq.main([*root, "cancel", "q1"]), 0)
        st = json.loads(q.joinpath("state.json").read_text())
        self.assertTrue(st["paused"])  # q2 still queued: the pause still holds it
        with mock.patch("builtins.print") as out:
            self.assertEqual(self.mq.main([*root, "cancel", "q2"]), 0)
        st = json.loads(q.joinpath("state.json").read_text())
        self.assertEqual((st["paused"], st["pause_reason"], st["pause_task"], st["queue"]), (False, "", "", []))
        self.assertIn("pause cleared (was: subscription usage limit reached during q1)",
                      " ".join(str(c.args[0]) for c in out.call_args_list))


class E6PackageExit(Tmp):
    def test_package_errored_run_exits_3_without_traceback(self) -> None:  # R5-21
        task = self.tmp / "corpus" / "t1"
        task.mkdir(parents=True)
        (task / "task.toml").write_text('name = "x/t1"\n')
        run = self.tmp / "jobs" / "t1__job" / "trajectory" / "kiro-model" / "Run 1"
        run.mkdir(parents=True)
        (run / "config.json").write_text(json.dumps({"task": {"path": str(task)}}))
        (run / "exception.txt").write_text("ApiOverloadedError: InternalServerError\n")
        out = self.tmp / "out"
        r = subprocess.run([sys.executable, str(PRB_PATH), "--jobs", str(self.tmp / "jobs"), "-o", str(out),
                            "--corpus", str(self.tmp / "corpus")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"t1: not packaged: .*missing delivery evidence")
        self.assertFalse((out / "t1").exists())  # nothing half-written


if __name__ == "__main__":
    unittest.main()
