"""Unit tests for auto.py (stdlib unittest; temp dirs and a temp sqlite db, no network, no opencode)."""
from __future__ import annotations

import json
import os
import sqlite3
import stat
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import auto  # noqa: E402

IST = auto.IST
NOW_MS = 1_800_000_000_000
MIN = 60_000

REAL_ERRORS = {
    "limit": {"name": "APIError", "data": {"message": "Third-party apps now draw from your extra usage, "
                                                      "not your plan limits. Add more at claude.ai/settings"}},
    "network": {"name": "APIError", "data": {"message": "Cannot connect to API: Unable to connect to API (ECONNREFUSED)"}},
    "aborted": {"name": "MessageAbortedError", "data": {"message": "Aborted"}},
    "other_unknown": {"name": "UnknownError", "data": {"message": "Internal error"}},
    "other_oauth": {"name": "APIError", "data": {"message": "OAuth access token has been revoked."}},
    "other_model": {"name": "APIError", "data": {"message": "Claude Code 2.1.220 does not support this model. "
                                                           "Run claude update."}},
}


def make_db(path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(path)
    c.executescript("""
        create table session(id text primary key, parent_id text, title text, time_updated integer);
        create table message(id text primary key, session_id text, time_created integer, time_updated integer, data text);
        create table part(id text primary key, message_id text, session_id text, time_created integer, data text);
    """)
    return c


def add_session(c, sid, title="t", parent=None, updated=NOW_MS):
    c.execute("insert into session values (?,?,?,?)", (sid, parent, title, updated))


def add_msg(c, sid, mid, created, data, texts=()):
    c.execute("insert into message values (?,?,?,?,?)", (mid, sid, created, created, json.dumps(data)))
    for i, t in enumerate(texts):
        c.execute("insert into part values (?,?,?,?,?)",
                  (f"{mid}_p{i}", mid, sid, created + i, json.dumps({"type": "text", "text": t})))
    c.execute("insert into part values (?,?,?,?,?)",
              (f"{mid}_tool", mid, sid, created + 99, json.dumps({"type": "tool", "text": "IGNORED"})))
    c.commit()


class DbCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.db_path = self.dir / "oc.db"
        self.c = make_db(self.db_path)
        self.addCleanup(self.c.close)
        p = mock.patch.object(auto, "DB_PATH", self.db_path)
        p.start()
        self.addCleanup(p.stop)


class TestDbState(DbCase):
    def test_busy_when_last_is_recent_user_message(self) -> None:
        add_session(self.c, "s1")
        add_msg(self.c, "s1", "m1", NOW_MS - 2 * MIN, {"role": "user"})
        self.assertEqual(auto.db_state("s1", NOW_MS).state, "busy")

    def test_interrupted_when_last_is_old_user_message(self) -> None:
        add_session(self.c, "s1")
        add_msg(self.c, "s1", "m1", NOW_MS - 30 * MIN, {"role": "user"})
        self.assertEqual(auto.db_state("s1", NOW_MS).state, "interrupted")

    def test_error_when_assistant_has_error(self) -> None:
        add_session(self.c, "s1")
        add_msg(self.c, "s1", "m1", NOW_MS - MIN, {"role": "assistant", "error": REAL_ERRORS["limit"],
                                                  "time": {"created": NOW_MS}})
        d = auto.db_state("s1", NOW_MS)
        self.assertEqual((d.state, d.error, d.msg_id), ("error", REAL_ERRORS["limit"], "m1"))

    def test_busy_when_assistant_not_completed_and_session_fresh(self) -> None:
        add_session(self.c, "s1", updated=NOW_MS - MIN)
        add_msg(self.c, "s1", "m1", NOW_MS - 20 * MIN, {"role": "assistant", "time": {"created": 1}})
        self.assertEqual(auto.db_state("s1", NOW_MS).state, "busy")

    def test_interrupted_when_assistant_not_completed_and_session_stale(self) -> None:
        add_session(self.c, "s1", updated=NOW_MS - 30 * MIN)
        add_msg(self.c, "s1", "m1", NOW_MS - 31 * MIN, {"role": "assistant", "time": {"created": 1}})
        self.assertEqual(auto.db_state("s1", NOW_MS).state, "interrupted")

    def test_tool_calls_finish_is_busy_then_interrupted(self) -> None:
        data = {"role": "assistant", "finish": "tool-calls", "time": {"created": 1, "completed": 2}}
        add_session(self.c, "fresh", updated=NOW_MS - MIN)
        add_msg(self.c, "fresh", "m1", NOW_MS - MIN, data)
        add_session(self.c, "stale", updated=NOW_MS - 30 * MIN)
        add_msg(self.c, "stale", "m2", NOW_MS - 30 * MIN, data)
        self.assertEqual(auto.db_state("fresh", NOW_MS).state, "busy")
        self.assertEqual(auto.db_state("stale", NOW_MS).state, "interrupted")

    def test_done_for_stop_length_and_null_finish_with_completed(self) -> None:
        for i, finish in enumerate(("stop", "length", None)):
            sid = f"s{i}"
            add_session(self.c, sid)
            add_msg(self.c, sid, f"m{i}", NOW_MS - MIN,
                    {"role": "assistant", "finish": finish, "time": {"created": 1, "completed": 2}}, ["part one", "part two"])
            d = auto.db_state(sid, NOW_MS)
            self.assertEqual(d.state, "done", finish)
            self.assertEqual(d.tail, "part one\npart two")

    def test_last_message_wins_by_time_created(self) -> None:
        add_session(self.c, "s1")
        add_msg(self.c, "s1", "m1", NOW_MS - 20 * MIN,
                {"role": "assistant", "finish": "stop", "time": {"completed": 2}})
        add_msg(self.c, "s1", "m2", NOW_MS - MIN, {"role": "user"})
        self.assertEqual(auto.db_state("s1", NOW_MS).state, "busy")

    def test_unknown_for_missing_session_or_db(self) -> None:
        self.assertEqual(auto.db_state("nope", NOW_MS).state, "unknown")
        with mock.patch.object(auto, "DB_PATH", self.dir / "missing.db"):
            self.assertEqual(auto.db_state("s1", NOW_MS).state, "unknown")

    def test_connection_is_read_only(self) -> None:
        with closing(auto.db_connect()) as c, self.assertRaises(sqlite3.OperationalError):
            c.execute("insert into session values ('x', null, 't', 1)")


class TestAdoptLookup(DbCase):
    def test_find_session_picks_newest_root_session_with_title(self) -> None:
        add_session(self.c, "old", "abc1234", updated=NOW_MS - 5 * MIN)
        add_session(self.c, "new", "abc1234", updated=NOW_MS)
        add_session(self.c, "child", "abc1234", parent="new", updated=NOW_MS + 5 * MIN)
        add_session(self.c, "other", "zzz")
        self.c.commit()
        self.assertEqual(auto.find_session("abc1234"), "new")
        self.assertIsNone(auto.find_session("missing"))

    def test_adopt_one_marks_not_owned_and_copies_board_prompt(self) -> None:
        add_session(self.c, "sess1", "abc1234")
        self.c.commit()
        board = self.dir / "board.json"
        board.write_text(json.dumps({"rows": [{"sha": "abc1234", "status": "running", "prompt": "prompts/x.md"}]}))
        auto.use_run(self.dir / "run")
        st = {"workers": {}}
        with mock.patch.object(auto, "BOARD", board):
            self.assertTrue(auto.adopt_one(st, "abc1234", None))
            self.assertFalse(auto.adopt_one(st, "nosuch", None))
            self.assertFalse(auto.adopt_one(st, "abc1234", "ses_missing"))
        w = st["workers"]["abc1234"]
        self.assertEqual((w["session"], w["adopted"], w["owned"], w["prompt"], w["reported_msg"]),
                         ("sess1", True, False, "prompts/x.md", None))
        self.assertTrue(auto.is_passive(w))
        self.assertFalse(w["build"])


class TestClassify(unittest.TestCase):
    def test_real_errors(self) -> None:
        got = {k: auto.classify(v) for k, v in REAL_ERRORS.items()}
        self.assertEqual(got, {"limit": "limit", "network": "network", "aborted": "aborted",
                               "other_unknown": "other", "other_oauth": "other", "other_model": "other"})

    def test_other_limit_and_network_phrases(self) -> None:
        self.assertEqual(auto.classify({"name": "APIError", "data": {"message": "429 rate limit"}}), "limit")
        self.assertEqual(auto.classify({"name": "APIError", "data": {"message": "request timed out"}}), "network")
        self.assertEqual(auto.classify(None), "other")


class TestReset(unittest.TestCase):
    base = datetime(2026, 10, 26, 14, 0, tzinfo=IST)

    def test_reset_at_clock_time_today_or_tomorrow(self) -> None:
        self.assertEqual(auto.parse_reset("limit resets at 3:30pm", self.base),
                         datetime(2026, 10, 26, 15, 30, tzinfo=IST))
        self.assertEqual(auto.parse_reset("resets 9:05am", self.base), datetime(2026, 10, 27, 9, 5, tzinfo=IST))
        self.assertEqual(auto.parse_reset("resets 16:45", self.base), datetime(2026, 10, 26, 16, 45, tzinfo=IST))
        self.assertEqual(auto.parse_reset("resets 12am", self.base), datetime(2026, 10, 27, 0, 0, tzinfo=IST))

    def test_try_again_in(self) -> None:
        self.assertEqual(auto.parse_reset("try again in 15 minutes", self.base), self.base + timedelta(minutes=15))
        self.assertEqual(auto.parse_reset("Try again in 2 hours.", self.base), self.base + timedelta(hours=2))

    def test_default_when_nothing_parses(self) -> None:
        self.assertEqual(auto.parse_reset("Third-party apps draw from extra usage", self.base),
                         self.base + timedelta(minutes=30))
        self.assertEqual(auto.parse_reset("resets 5 times", self.base, 60), self.base + timedelta(minutes=60))


class TestPlan(unittest.TestCase):
    def test_timed_lines_parse_with_next_occurrence(self) -> None:
        start = datetime(2026, 10, 26, 22, 0, tzinfo=IST)
        text = ("intro line\n- At 03:00: run harness on X\n  * at 7:30 - wrap up\nat 21:00\u2013evening thing\n"
                "not at 04:00: inline\n- at 25:99: bad time\nat 22:00: same minute\n")
        got = auto.parse_plan(text, start)
        self.assertEqual([(g["at"], g["text"], g["sent"]) for g in got], [
            ("2026-10-27T03:00+05:30", "run harness on X", False),
            ("2026-10-27T07:30+05:30", "wrap up", False),
            ("2026-10-27T21:00+05:30", "evening thing", False),
            ("2026-10-27T22:00+05:30", "same minute", False),
        ])


class TestReportInsert(unittest.TestCase):
    def test_template_section_order(self) -> None:
        heads = [l for l in auto.REPORT_TEMPLATE.splitlines() if l.startswith("#")]
        self.assertEqual(heads, ["# AUTO report ({label}: {started} -> {until})", "## In short", "## Needs Ayush",
                                 "## Results", "## Decisions and overrides", "## Interrupted or unfinished",
                                 "## Still running at stop", "## Proposed changes (not applied)"])

    def test_lines_go_under_interrupted_section_in_order(self) -> None:
        text = auto.REPORT_TEMPLATE.format(label="x", started="a", until="b")
        text = auto.insert_report_line(text, "- WATCHER 01:00: first")
        text = auto.insert_report_line(text, "- WATCHER 01:05: second")
        lines = text.split("\n")
        i = lines.index("## Interrupted or unfinished")
        j = lines.index("## Still running at stop")
        self.assertEqual([l for l in lines[i:j] if l], ["## Interrupted or unfinished",
                                                        "- WATCHER 01:00: first", "- WATCHER 01:05: second"])
        self.assertEqual(lines[j - 1], "")

    def test_existing_hand_written_lines_are_kept_and_section_last(self) -> None:
        text = "## Interrupted or unfinished\n- by master\n"
        out = auto.insert_report_line(text, "- WATCHER 02:00: x")
        self.assertEqual(out.split("\n")[:3], ["## Interrupted or unfinished", "- by master", "- WATCHER 02:00: x"])

    def test_missing_header_appends_at_end(self) -> None:
        out = auto.insert_report_line("# T\n\n## Results\n", "- WATCHER 03:00: y")
        self.assertTrue(out.endswith("## Results\n- WATCHER 03:00: y\n"))


class TestResumeRefusal(unittest.TestCase):
    def test_rules(self) -> None:
        self.assertIn("no previous run", auto.resume_refusal({}))
        self.assertIn("still running", auto.resume_refusal({"watcher_pid": os.getpid()}))
        self.assertEqual(auto.resume_refusal({"watcher_pid": 2 ** 22 + 1, "ended": "x", "final_sent": True}),
                         "last run finished normally; use start")
        self.assertIsNone(auto.resume_refusal({"watcher_pid": 2 ** 22 + 1}))
        self.assertIsNone(auto.resume_refusal({"watcher_pid": 2 ** 22 + 1, "ended": "x"}))  # ended without FINAL


class RunCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        auto.use_run(self.dir / "run").dir.mkdir()
        auto.cur().report.write_text(auto.REPORT_TEMPLATE.format(label="x", started="a", until="b"))
        self.notes: list[str] = []
        p = mock.patch.object(auto, "notify", side_effect=self.notes.append)  # never osascript in tests
        p.start()
        self.addCleanup(p.stop)


class TestRetries(RunCase):
    def state(self) -> dict:
        return {"workers": {"abc": auto.new_worker("ses1", "")}, "retries": {}, "events": []}

    def test_limit_error_pauses_once_then_gives_up_after_four_retries(self) -> None:
        st = self.state()
        ev: list[str] = []
        err = REAL_ERRORS["limit"]
        auto.handle_result(st, ev, "abc", auto.DbState("error", "m1", "", err))
        auto.handle_result(st, ev, "abc", auto.DbState("error", "m1", "", err))  # same message: ignored
        self.assertEqual(len(ev), 1)
        self.assertTrue(ev[0].startswith("PAUSED abc: limit: Third-party apps"))
        for n in range(1, auto.MAX_RETRIES + 1):
            st["retries"]["abc"]["count"] = n
            st["retries"]["abc"]["at"] = None
            auto.handle_result(st, ev, "abc", auto.DbState("error", f"m{n + 1}", "", err))
        self.assertEqual(ev[-1], "GAVE UP abc after 4 retries")
        self.assertTrue(st["retries"]["abc"]["gave_up"])
        self.assertEqual(sum(e.startswith("GAVE UP") for e in ev), 1)

    def test_aborted_and_other_errors_are_reported_without_retry(self) -> None:
        st = self.state()
        ev: list[str] = []
        auto.handle_result(st, ev, "abc", auto.DbState("error", "m1", "", REAL_ERRORS["aborted"]))
        self.assertTrue(ev[0].startswith("ERROR abc: aborted"))
        self.assertEqual(st["retries"], {})

    def test_done_clears_pause_and_tags_adopted_sessions(self) -> None:
        st = self.state()
        st["workers"]["abc"].update(adopted=True, owned=False)
        st["retries"]["abc"] = {"count": 2}
        ev: list[str] = []
        auto.handle_result(st, ev, "abc", auto.DbState("done", "m9", "ALL GOOD"))
        self.assertTrue(ev[0].startswith("done : abc (adopted session ses1)"))
        self.assertIn("ALL GOOD", ev[0])
        self.assertEqual(st["retries"], {})

    def test_retry_is_scheduled_at_parsed_reset_time(self) -> None:
        st = self.state()
        auto.schedule_retry(st, "abc", "limit", "limit reached, try again in 90 minutes", "m1")
        at = datetime.fromisoformat(st["retries"]["abc"]["at"])
        delta = at - auto.now()
        self.assertLess(abs(delta - timedelta(minutes=90)), timedelta(seconds=5))


class TestPassivePoll(RunCase):
    def test_interrupted_reported_once_and_done_reported_once(self) -> None:
        st = {"workers": {"abc": auto.new_worker("ses1", "", adopted=True)}, "retries": {}, "events": [],
              "worker_url": "http://x"}
        ev: list[str] = []
        with mock.patch.object(auto, "busy_ids", return_value=set()), \
                mock.patch.object(auto, "http", return_value=[]), \
                mock.patch.object(auto, "db_state", return_value=auto.DbState("interrupted", "m1")):
            auto.poll_workers(st, ev)
            auto.poll_workers(st, ev)
        self.assertEqual(ev, ["INTERRUPTED abc: session stopped mid-step (its window may have been closed); "
                              "not resumed automatically"])
        ev.clear()
        with mock.patch.object(auto, "busy_ids", return_value=set()), \
                mock.patch.object(auto, "http", return_value=[]), \
                mock.patch.object(auto, "db_state", return_value=auto.DbState("done", "m2", "fin")):
            auto.poll_workers(st, ev)
            auto.poll_workers(st, ev)
        self.assertEqual(len(ev), 1)
        self.assertTrue(ev[0].startswith("done : abc (adopted session ses1)"))

    def test_busy_workers_counts_passive_busy_sessions(self) -> None:
        st = {"workers": {"p": auto.new_worker("s_p", "", adopted=True), "o": auto.new_worker("s_o", "")},
              "worker_url": "http://x"}
        with mock.patch.object(auto, "healthy", return_value=True), \
                mock.patch.object(auto, "busy_ids", return_value={"s_o"}), \
                mock.patch.object(auto, "db_state", return_value=auto.DbState("busy", "m")):
            self.assertEqual(sorted(auto.busy_workers(st)), ["o", "p"])


class TestReportAndHarness(RunCase):
    def test_gap_adds_event_and_report_line(self) -> None:
        st = {"last_poll": (auto.now() - timedelta(minutes=45)).isoformat(timespec="seconds")}
        ev: list[str] = []
        auto.check_gap(st, ev)
        self.assertTrue(ev[0].startswith("GAP: watcher did not run from "))
        self.assertIn("- WATCHER", auto.cur().report.read_text())
        ev.clear()
        auto.check_gap(st, ev)
        self.assertEqual(ev, [])

    def test_network_down_then_back(self) -> None:
        st: dict = {"net_down_since": (auto.now() - timedelta(minutes=7)).isoformat(timespec="seconds")}
        ev: list[str] = []
        with mock.patch.object(auto, "net_up", return_value=False):
            self.assertFalse(auto.check_net(st, ev))
            auto.check_net(st, ev)
        self.assertEqual(auto.cur().report.read_text().count("network down since"), 1)
        with mock.patch.object(auto, "net_up", return_value=True):
            self.assertTrue(auto.check_net(st, ev))
        self.assertTrue(ev[0].startswith("NETWORK BACK after 7 min (down since "))
        self.assertIsNone(st["net_down_since"])

    def fake_harness(self, state: dict) -> None:
        h = self.dir / "harness"
        (h / ".master-queue").mkdir(parents=True)
        (h / ".venv/bin").mkdir(parents=True)
        (h / "scripts").mkdir()
        (h / ".master-queue/state.json").write_text(json.dumps(state))
        py = h / ".venv/bin/python"
        py.write_text(f"#!/bin/sh\necho \"fake master_queue $@\" >> {h}/calls.txt\necho resumed-ok\n")
        py.chmod(py.stat().st_mode | stat.S_IXUSR)
        self.harness = h

    def test_limit_pause_is_resumed_at_reset_max_three_times_and_startup_never(self) -> None:
        reason = "usage limit reached, try again in 1 minutes"
        self.fake_harness({"runs": [], "queue": [], "paused": True, "pause_reason": reason})
        st: dict = {"harness_resume": {}}
        ev: list[str] = []
        with mock.patch.object(auto, "HARNESS", self.harness):
            auto.harness_auto_resume(st, ev)
            self.assertEqual(ev, [])  # not yet due
            for _ in range(5):
                st["harness_resume"][reason]["at"] = "2020-01-01T00:00:00+05:30"
                auto.harness_auto_resume(st, ev)
            calls = (self.harness / "calls.txt").read_text().splitlines()
            self.assertEqual(calls, ["fake master_queue scripts/master_queue.py resume"] * 3)
            self.assertEqual(sum("GAVE UP" in e for e in ev), 1)
            (self.harness / ".master-queue/state.json").write_text(json.dumps(
                {"paused": True, "pause_reason": "startup failure: usage limit while starting"}))
            auto.harness_auto_resume(st, ev)
            self.assertEqual(len((self.harness / "calls.txt").read_text().splitlines()), 3)


class TestMisc(unittest.TestCase):
    def test_worker_permission_denies_auto_and_night(self) -> None:
        bash = auto.WORKER_PERMISSION["bash"]
        self.assertEqual((bash["*auto.py*"], bash["*night.py*"], bash["*master_queue.py*"]), ("deny",) * 3)

    def test_require_not_worker(self) -> None:
        with mock.patch.dict(os.environ, {"OC_AUTO_WORKER": "1"}), self.assertRaises(auto.AutoError):
            auto.require_not_worker()

    def test_message_prefix_and_footer_text(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            auto.use_run(Path(t) / "run")
            st = {"master": "m", "master_url": "http://m", "master_session": "s", "until": "2026-10-26T07:30+05:30",
                  "events": ["EVT"], "master_idle_polls": 5, "retries": {}}
            sent: list[str] = []
            with mock.patch.object(auto, "REGISTRY", Path(t)), mock.patch.object(auto, "healthy", return_value=True), \
                    mock.patch.object(auto, "busy_ids", return_value=set()), \
                    mock.patch.object(auto, "last_message", return_value=None), \
                    mock.patch.object(auto, "master_identity", return_value=(None, None, None)), \
                    mock.patch.object(auto, "prompt", side_effect=lambda u, s, text, **k: sent.append(text)):
                auto.deliver(st)
            self.assertRegex(sent[0], r"^\[AUTO WATCHER\] \d\d:\d\d IST \(auto mode until 07:30; Ayush is away\)\n\nEVT")
            self.assertIn("AUTO_POLICY.md", sent[0])
            self.assertEqual(st["events"], [])

    def test_master_limit_error_holds_delivery_and_retries_continue(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            auto.use_run(Path(t) / "run").dir.mkdir()
            auto.cur().report.write_text(auto.REPORT_TEMPLATE.format(label="x", started="a", until="b"))
            st = {"retries": {}}
            msg = {"info": {"id": "mm1", "role": "assistant", "error": REAL_ERRORS["limit"]}}
            sent: list[str] = []
            with mock.patch.object(auto, "last_message", return_value=msg), \
                    mock.patch.object(auto, "master_identity", return_value=(None, None, None)), \
                    mock.patch.object(auto, "prompt", side_effect=lambda u, s, text, **k: sent.append(text)):
                self.assertTrue(auto.master_gate(st, "u", "s"))
                self.assertEqual(sent, [])
                st["retries"][auto.MASTER_KEY]["at"] = "2020-01-01T00:00:00+05:30"
                self.assertTrue(auto.master_gate(st, "u", "s"))
                self.assertEqual(sent, ["continue"])
            with mock.patch.object(auto, "last_message", return_value={"info": {"id": "mm2", "role": "assistant"}}):
                self.assertFalse(auto.master_gate(st, "u", "s"))
            self.assertEqual(st["retries"], {})


class TestSchedule(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        for name, val in (("AUTO_DIR", self.d), ("SCHED_RETRY_S", 0), ("SCHED_POLL_S", 0)):
            p = mock.patch.object(auto, name, val)
            p.start()
            self.addCleanup(p.stop)
        self.now = datetime(2026, 10, 27, 1, 0, tzinfo=IST)
        p = mock.patch.object(auto, "now", side_effect=lambda: self.now)
        p.start()
        self.addCleanup(p.stop)

    def args(self, *extra: str):
        return auto.build_parser().parse_args(["start", "--until", "08:30", *extra])

    def write_sched(self, at: str, until: str, argv=None) -> None:
        auto.sched_file().write_text(json.dumps({"id": "X", "at": at, "until": until,
                                                 "argv": argv or ["start", "--until", "08:30"]}))

    def test_schedule_checks_then_writes_file_with_times_and_argv(self) -> None:
        plan = self.d / "plan.md"
        plan.write_text("p")
        pops = iter([mock.Mock(pid=111), mock.Mock(pid=222)])
        with mock.patch.object(auto, "master_url", return_value="u") as mu, \
                mock.patch.object(auto.subprocess, "Popen", side_effect=lambda *a, **k: next(pops)):
            self.assertEqual(auto.cmd_start(self.args("--at", "02:00", "--plan", str(plan), "--harness", "2")), 0)
        mu.assert_called_once()
        sch = auto.load_schedule()
        self.assertEqual((sch["at"], sch["until"]), ("2026-10-27T02:00+05:30", "2026-10-27T08:30+05:30"))
        self.assertEqual((sch["waiter_pid"], sch["caffeinate_pid"]), (111, 222))
        self.assertIn("--plan", sch["argv"])
        self.assertNotIn("--at", sch["argv"])
        self.assertEqual(sch["argv"][sch["argv"].index("--harness") + 1], "2")

    def test_schedule_refuses_when_master_down_or_plan_missing_and_writes_nothing(self) -> None:
        with mock.patch.object(auto, "master_url", side_effect=auto.AutoError("down")):
            with self.assertRaises(auto.AutoError):
                auto.cmd_start(self.args("--at", "02:00"))
        with mock.patch.object(auto, "master_url", return_value="u"):
            with self.assertRaises(OSError):
                auto.cmd_start(self.args("--at", "02:00", "--plan", str(self.d / "missing.md")))
        self.assertFalse(auto.sched_file().exists())

    def test_existing_schedule_blocks_new_schedule_and_plain_start(self) -> None:
        self.write_sched("2026-10-27T02:00+05:30", "2026-10-27T08:30+05:30")
        with self.assertRaisesRegex(auto.AutoError, "cancel"):
            auto.cmd_start(self.args("--at", "03:00"))
        with self.assertRaisesRegex(auto.AutoError, "cancel"):
            auto.cmd_start(self.args())

    def test_waiter_starts_once_due_and_removes_file(self) -> None:
        self.write_sched("2026-10-27T01:00+05:30", "2026-10-27T08:30+05:30")
        seen = []
        with mock.patch.object(auto, "cmd_start", side_effect=lambda a: seen.append(a) or 0):
            self.assertEqual(auto.cmd_scheduled(mock.Mock(id="X")), 0)
        self.assertTrue(seen[0].from_schedule)
        self.assertIsNone(getattr(seen[0], "schedule_note", None))
        self.assertFalse(auto.sched_file().exists())

    def test_late_wake_starts_with_note_and_after_until_skips(self) -> None:
        self.write_sched("2026-10-27T00:30+05:30", "2026-10-27T08:30+05:30")
        seen = []
        with mock.patch.object(auto, "cmd_start", side_effect=lambda a: seen.append(a) or 0):
            auto.cmd_scheduled(mock.Mock(id="X"))
        self.assertIn("began late at 01:00", seen[0].schedule_note)
        self.write_sched("2026-10-26T23:00+05:30", "2026-10-27T00:30+05:30")
        with mock.patch.object(auto, "cmd_start") as cs:
            auto.cmd_scheduled(mock.Mock(id="X"))
        cs.assert_not_called()
        self.assertIn("SKIPPED", (self.d / "SCHEDULED.log").read_text())

    def test_waiter_retries_then_gives_up(self) -> None:
        self.write_sched("2026-10-27T01:00+05:30", "2026-10-27T08:30+05:30")
        with mock.patch.object(auto, "SCHED_RETRY_N", 3), \
                mock.patch.object(auto, "cmd_start", side_effect=auto.AutoError("master chat port u not answering")) as cs:
            self.assertEqual(auto.cmd_scheduled(mock.Mock(id="X")), 1)
        self.assertEqual(cs.call_count, 3)
        log = (self.d / "SCHEDULED.log").read_text()
        self.assertIn("GAVE UP after 3 tries", log)
        self.assertFalse(auto.sched_file().exists())

    def test_waiter_succeeds_on_second_try(self) -> None:
        self.write_sched("2026-10-27T01:00+05:30", "2026-10-27T08:30+05:30")
        calls = iter([auto.AutoError("master chat not registered"), 0])

        def fake(a):
            r = next(calls)
            if isinstance(r, Exception):
                raise r
            return r
        with mock.patch.object(auto, "cmd_start", side_effect=fake):
            self.assertEqual(auto.cmd_scheduled(mock.Mock(id="X")), 0)
        self.assertIn("STARTED at 01:00 (scheduled 01:00, try 2)", (self.d / "SCHEDULED.log").read_text())

    def test_other_start_error_is_logged_once_without_retry(self) -> None:
        self.write_sched("2026-10-27T01:00+05:30", "2026-10-27T08:30+05:30")
        with mock.patch.object(auto, "cmd_start", side_effect=AttributeError("boom")) as cs:
            self.assertEqual(auto.cmd_scheduled(mock.Mock(id="X")), 1)
        self.assertEqual(cs.call_count, 1)
        log = (self.d / "SCHEDULED.log").read_text()
        self.assertIn("AttributeError: boom", log)
        self.assertIn("no retry", log)
        self.assertFalse(auto.sched_file().exists())

    def test_cancelled_waiter_does_nothing(self) -> None:
        self.write_sched("2026-10-27T05:00+05:30", "2026-10-27T08:30+05:30")
        with mock.patch.object(auto, "cmd_start") as cs:
            self.assertEqual(auto.cmd_scheduled(mock.Mock(id="OTHER")), 0)
            self.assertEqual(auto.cmd_cancel(None), 0)
        cs.assert_not_called()
        self.assertFalse(auto.sched_file().exists())
        self.assertIn("CANCELLED", (self.d / "SCHEDULED.log").read_text())

    def test_status_reports_stale_schedule(self) -> None:
        self.write_sched("2026-10-27T02:00+05:30", "2026-10-27T08:30+05:30")
        self.assertIn("STALE", auto.schedule_status())
        auto.sched_file().unlink()
        self.assertTrue(auto.schedule_status().startswith("schedule: none"))


# ---------------------------------------------------------------- E1: limit detection and budget
class FakeOpencode:
    """Minimal opencode server in a thread: /global/health, /session/status, /session, prompt_async."""

    def __init__(self) -> None:
        import http.server
        import threading
        self.status: dict = {}
        self.posts: list[str] = []
        fake = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a) -> None:  # quiet
                pass

            def reply(self, body) -> None:
                raw = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:
                path = self.path.split("?")[0]
                if path == "/global/health":
                    self.reply({"healthy": True})
                elif path == "/session/status":
                    self.reply(fake.status)
                elif path.endswith("/message"):
                    self.reply([])
                else:
                    self.reply([])

            def do_POST(self) -> None:
                n = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(n)
                fake.posts.append(self.path)
                self.reply({"id": "ses_new"} if self.path == "/session" else {})

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        self.srv.shutdown()
        self.srv.server_close()


RETRY_LIMIT = {"type": "retry", "attempt": 2, "message": "This request would exceed your account's rate limit. "
               "Please try again in 5 minutes.", "next": None}
RETRY_401 = {"type": "retry", "attempt": 1, "message": "401 Unauthorized: invalid x-api-key", "next": None}


class LimitCase(RunCase):
    def setUp(self) -> None:
        super().setUp()
        self.oc = FakeOpencode()
        self.addCleanup(self.oc.close)
        sec = self.dir / "secret"
        sec.write_text("x\n")
        for name, val in (("SECRET", sec), ("HARNESS", self.make_harness())):
            p = mock.patch.object(auto, name, val)
            p.start()
            self.addCleanup(p.stop)
        self.st = {"workers": {"w1": auto.new_worker("ses_w1", ""), "w2": auto.new_worker("ses_w2", "")},
                   "retries": {}, "events": [], "worker_url": self.oc.url, "harness_seen": []}

    def make_harness(self, state: dict | None = None) -> Path:
        h = self.dir / "harness"
        (h / ".master-queue").mkdir(parents=True, exist_ok=True)
        (h / ".venv/bin").mkdir(parents=True, exist_ok=True)
        (h / "scripts").mkdir(exist_ok=True)
        self.set_mq(state or {"runs": [], "queue": [], "paused": False, "pause_reason": ""}, h)
        py = h / ".venv/bin/python"
        py.write_text(f"#!/bin/sh\necho \"$@\" >> {h}/calls.txt\necho ok\n")
        py.chmod(py.stat().st_mode | stat.S_IXUSR)
        self.harness = h
        return h

    def set_mq(self, state: dict, h: Path | None = None) -> None:
        ((h or self.harness) / ".master-queue/state.json").write_text(json.dumps(state))

    def calls(self) -> list[str]:
        f = self.harness / "calls.txt"
        return f.read_text().splitlines() if f.exists() else []

    def poll(self) -> list[str]:
        ev: list[str] = []
        auto.poll_workers(self.st, ev)
        auto.poll_harness(self.st, ev)
        auto.check_limit(self.st, ev)
        return ev


class TestLimit(LimitCase):
    def test_retry_is_not_busy(self) -> None:
        self.oc.status = {"ses_w1": RETRY_LIMIT, "ses_w2": {"type": "busy"}, "ses_x": {"type": "idle"}}
        self.assertEqual(auto.busy_ids(self.oc.url), {"ses_w2"})
        self.assertEqual(set(auto.retry_ids(self.oc.url)), {"ses_w1"})
        self.assertEqual(auto.busy_ids(self.oc.url, include_retry=True), {"ses_w1", "ses_w2"})
        self.assertEqual(auto.busy_workers(self.st), ["w2"])

    def test_retry_gives_limit_within_two_polls_then_cleared_after_two_clean_polls(self) -> None:
        self.oc.status = {"ses_w1": RETRY_LIMIT}
        ev = self.poll() + self.poll()
        limit = [e for e in ev if e.startswith("LIMIT:")]
        self.assertEqual(len(limit), 1, ev)
        self.assertIn("w1", limit[0])
        self.assertTrue(self.st["limit_since"])
        reset = datetime.fromisoformat(self.st["limit_reset"]) - datetime.fromisoformat(self.st["limit_since"])
        self.assertEqual(reset, timedelta(minutes=5))
        self.assertEqual(len(self.notes), 1)
        self.assertEqual(auto.cur().report.read_text().count("LIMIT:"), 1)
        self.assertEqual(len(self.calls()), 1)
        self.assertTrue(self.calls()[0].startswith("scripts/master_queue.py pause auto.py LIMIT since"))
        self.assertFalse(auto.LIMIT_RE.search(self.calls()[0].split(" pause ", 1)[1]))  # our hold is no limit text
        self.assertEqual(self.st["workers"]["w1"]["idle_polls"], 0)  # retry is never read as a finished step
        # the queue now shows our pause; the worker recovers
        self.set_mq({"runs": [], "queue": [], "paused": True,
                     "pause_reason": "auto.py LIMIT since 10:00: no new paid run starts until it clears"})
        self.oc.status = {"ses_w1": {"type": "busy"}}
        ev = self.poll()
        self.assertFalse(any(e.startswith("LIMIT") for e in ev))
        self.assertTrue(self.st.get("limit_since"))  # 1 clean poll is not enough
        self.oc.status = {"ses_w1": RETRY_LIMIT}  # dirty again resets the count
        self.poll()
        self.assertEqual(self.st["limit_clean"], 0)
        self.oc.status = {}
        ev = self.poll() + self.poll()
        self.assertEqual(sum(e.startswith("LIMIT CLEARED") for e in ev), 1, ev)
        self.assertNotIn("limit_since", self.st)
        self.assertEqual(self.calls()[-1], "scripts/master_queue.py resume")
        self.assertEqual(len(self.notes), 1)

    def test_mq_usage_limit_pause_is_limit_and_mq_not_paused_again(self) -> None:
        self.set_mq({"runs": [], "queue": [], "paused": True, "pause_task": "t1", "pause_reason":
                     "subscription usage limit reached during t1 (requeued at the front). Resume once the "
                     "limit resets.; soonest reset in 4698s"})
        self.oc.status = {}
        ev = self.poll()
        self.assertTrue(any(e.startswith("LIMIT: harness") for e in ev), ev)
        self.assertEqual(self.calls(), [])  # already paused by MQ
        reset = datetime.fromisoformat(self.st["limit_reset"]) - datetime.fromisoformat(self.st["limit_since"])
        self.assertEqual(reset, timedelta(seconds=4698))

    def test_401_is_auth_not_limit(self) -> None:
        self.oc.status = {"ses_w1": RETRY_401}
        ev = self.poll() + self.poll()
        self.assertEqual(sum(e.startswith("AUTH w1") for e in ev), 1, ev)
        self.assertFalse(any(e.startswith("LIMIT") for e in ev))
        self.assertNotIn("limit_since", self.st)
        reason = "AUTH: login rejected during t1 (requeued at the front). Run scripts/anubis-auth setup, then " \
                 "master_queue.py resume."
        self.set_mq({"runs": [], "queue": [], "paused": True, "pause_task": "t1", "pause_reason": reason})
        self.oc.status = {}
        ev = self.poll()
        self.assertTrue(ev and ev[0].startswith("AUTH: harness paused on a login fault"), ev)
        self.assertNotIn("limit_since", self.st)
        st = {"harness_resume": {}}
        auto.harness_auto_resume(st, ev)
        self.assertEqual((st["harness_resume"], self.calls()), ({}, []))  # no auto-resume
        # the old MQ text for a 401 preflight also matched LIMIT words: still AUTH here
        self.assertTrue(auto.is_auth_pause("EXHAUSTED http 401 from the usage probe"))
        self.assertFalse(auto.is_limit_pause("EXHAUSTED http 401 accounts exhausted"))

    def test_exhausted_line_during_paid_run_is_logged_not_killed(self) -> None:
        log = self.dir / "run.log"
        log.write_text("req 1 ok\nall 1 accounts exhausted; soonest reset in 4698s\nreq 2 ok\n")
        self.set_mq({"runs": [{"task": "t1", "attempt": 1, "status": "RUNNING", "log": str(log)}],
                     "queue": [], "paused": False})
        self.oc.status = {}
        ev = self.poll() + self.poll()
        self.assertEqual(sum(e.startswith("harness LOG: t1 attempt 1 still RUNNING") for e in ev), 1, ev)
        self.assertIn("(not killed)", ev[0])
        self.assertFalse(any(e.startswith("LIMIT") for e in ev))
        self.assertEqual(self.calls(), [])
        self.assertEqual(auto.cur().report.read_text().count("accounts exhausted"), 1)

    def test_hold_file_written_for_limit_and_busy(self) -> None:
        hold = self.harness / ".master-queue" / auto.HOLD_FILE
        self.oc.status = {}
        auto.write_hold(self.st)
        self.assertFalse(json.loads(hold.read_text())["hold"])
        self.st["workers"]["w3"] = auto.new_worker("ses_w3", "")
        self.oc.status = {f"ses_w{i}": {"type": "busy"} for i in (1, 2, 3)}
        auto.write_hold(self.st)
        h = json.loads(hold.read_text())
        self.assertEqual((h["hold"], h["busy"]), (True, 3))
        self.oc.status = {}
        self.st["limit_since"] = auto.ts()
        auto.write_hold(self.st)
        self.assertTrue(json.loads(hold.read_text())["reason"].startswith("LIMIT since"))


class TestBudgetRefusals(LimitCase):
    def setUp(self) -> None:
        super().setUp()
        p = mock.patch.object(auto, "latest_run", side_effect=auto.cur)
        p.start()
        self.addCleanup(p.stop)
        self.bundle = self.dir / "bundle"
        self.bundle.mkdir()
        (self.bundle / "task.toml").write_text("")
        self.prompt_file = self.dir / "p.md"
        self.prompt_file.write_text("board id `abc1234`\n")
        self.st.update(max_workers=5, max_harness=2, stopping=False)
        self.no_sh = mock.patch.object(auto, "sh", side_effect=AssertionError("must refuse before any check"))

    def spawn(self) -> None:
        auto.save_state(self.st)
        auto.cmd_spawn(mock.Mock(sha="abc1234", prompt=str(self.prompt_file), build=False))

    def run_harness(self) -> None:
        auto.save_state(self.st)
        auto.cmd_harness(mock.Mock(bundle=str(self.bundle)))

    def test_spawn_and_harness_refused_during_limit(self) -> None:
        self.st["limit_since"] = auto.ts()
        with self.assertRaisesRegex(auto.AutoError, "^LIMIT since .*no spawn until LIMIT CLEARED"):
            self.spawn()
        with self.no_sh, self.assertRaisesRegex(auto.AutoError, "^LIMIT since .*no harness until LIMIT CLEARED"):
            self.run_harness()
        self.assertEqual(self.oc.posts, [])
        with mock.patch.object(sys, "argv", ["auto.py", "spawn", "abc1234", str(self.prompt_file)]), \
                mock.patch("sys.stderr") as err:
            self.assertEqual(auto.main(), 2)  # non-zero exit with the message
        self.assertIn("no spawn until LIMIT CLEARED", "".join(c.args[0] for c in err.write.call_args_list))

    def test_harness_refused_with_three_busy_workers(self) -> None:
        self.st["workers"]["w3"] = auto.new_worker("ses_w3", "")
        self.oc.status = {f"ses_w{i}": {"type": "busy"} for i in (1, 2, 3)}
        with self.no_sh, self.assertRaisesRegex(auto.AutoError, "3 workers busy; a paid run starts only with <= 2"):
            self.run_harness()
        self.oc.status = {"ses_w1": {"type": "busy"}, "ses_w2": {"type": "busy"}, "ses_w3": RETRY_LIMIT}
        with self.no_sh, self.assertRaisesRegex(AssertionError, "must refuse before any check"):
            self.run_harness()  # 2 busy + 1 in retry: passes the budget, reaches the docker/pypi checks

    def test_fourth_spawn_held_while_paid_run_running(self) -> None:
        self.st["workers"]["w3"] = auto.new_worker("ses_w3", "")
        self.oc.status = {f"ses_w{i}": {"type": "busy"} for i in (1, 2, 3)}
        self.set_mq({"runs": [{"task": "t1", "attempt": 1, "status": "RUNNING"}], "queue": [], "paused": False})
        with self.assertRaisesRegex(auto.AutoError, "^held: 3 workers busy while paid run t1 is RUNNING"):
            self.spawn()
        self.assertEqual(self.oc.posts, [])
        self.set_mq({"runs": [{"task": "t1", "attempt": 1, "status": "DONE"}], "queue": [], "paused": False})
        self.spawn()  # no paid run: MAX_BUSY_WORKERS 5 as before
        self.assertEqual(self.oc.posts[0], "/session")
        self.assertIn("abc1234", auto.load_state()["workers"])


class TestResetAndResumeKey(RunCase):
    base = datetime(2026, 10, 28, 17, 54, 49, tzinfo=IST)

    def test_reset_in_seconds(self) -> None:
        line = "all 1 accounts exhausted; soonest reset in 4698s"
        self.assertEqual(auto.parse_reset(line, self.base, 60), self.base + timedelta(seconds=4698))
        self.assertEqual(f"{auto.parse_reset(line, self.base, 60):%H:%M:%S}", "19:13:07")
        for text, delta in (("reset in 30 sec", timedelta(seconds=30)), ("try again in 2 seconds", timedelta(seconds=2)),
                            ("try again in 5 minutes", timedelta(minutes=5)), ("try again in 2 hours", timedelta(hours=2)),
                            ("try again in 3hrs", timedelta(hours=3))):
            self.assertEqual(auto.parse_reset(text, self.base) - self.base, delta, text)
        self.assertIsNone(auto.reset_in_text("no reset words", self.base))

    def test_resume_keyed_by_task_with_five_minute_pad(self) -> None:
        h = self.dir / "harness"
        (h / ".master-queue").mkdir(parents=True)
        (h / ".venv/bin").mkdir(parents=True)
        py = h / ".venv/bin/python"
        py.write_text(f"#!/bin/sh\necho \"$@\" >> {h}/calls.txt\n")
        py.chmod(py.stat().st_mode | stat.S_IXUSR)
        r1 = "subscription usage limit reached during t1 (requeued at the front). Resume once the limit resets."
        (h / ".master-queue/state.json").write_text(json.dumps(
            {"paused": True, "pause_task": "t1", "pause_reason": r1 + "; soonest reset in 600s"}))
        st: dict = {"harness_resume": {}}
        ev: list[str] = []
        with mock.patch.object(auto, "HARNESS", h):
            auto.harness_auto_resume(st, ev)
            self.assertEqual(list(st["harness_resume"]), ["t1"])
            at = datetime.fromisoformat(st["harness_resume"]["t1"]["at"]) - auto.now()
            self.assertLess(abs(at - timedelta(minutes=15)), timedelta(seconds=5))  # 600 s + 5 min pad
            for reset in ("120s", "300s", "60s", "30s"):  # same task, new reason text each time
                (h / ".master-queue/state.json").write_text(json.dumps(
                    {"paused": True, "pause_task": "t1", "pause_reason": f"{r1}; soonest reset in {reset}"}))
                st["harness_resume"]["t1"]["at"] = "2020-01-01T00:00:00+05:30"
                auto.harness_auto_resume(st, ev)
            self.assertEqual(list(st["harness_resume"]), ["t1"])
            self.assertEqual(len((h / "calls.txt").read_text().splitlines()), 3)
            self.assertEqual(sum("GAVE UP" in e for e in ev), 1)
            # no pause_task (old MQ state): key comes from "during <task>"
            (h / ".master-queue/state.json").write_text(json.dumps({"paused": True, "pause_reason": r1.replace("t1", "t2")}))
            auto.harness_auto_resume(st, ev)
            self.assertEqual(sorted(st["harness_resume"]), ["t1", "t2"])


if __name__ == "__main__":
    unittest.main()
