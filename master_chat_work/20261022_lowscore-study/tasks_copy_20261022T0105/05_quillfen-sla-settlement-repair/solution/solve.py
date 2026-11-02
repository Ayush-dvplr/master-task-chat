#!/usr/bin/env python3
"""Reference repair: restore the settlement engine to its contract and deliver the repair records."""
from __future__ import annotations

import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

DATA = Path(os.environ.get("QF_DATA", "/app/data")).resolve()
OUT = Path(os.environ.get("QF_OUT", "/app/out")).resolve()

# (package, clause, function, file, shipped text, repaired text)
REPAIRS = [
    ("quillfen.parsers", "2.4", "scheduler.syslog_year", "src/quillfen/parsers/scheduler.py",
     "def syslog_year(corpus: Corpus, month: int, day: int, hour: int, minute: int, second: int) -> int:\n    \"\"\"Syslog stamps carry no year: a legacy export only covers its own settlement year.\"\"\"\n    year = time_year(corpus.period_start)\n    instant(year, month, day, hour, minute, second)\n    return year\n",
     "def syslog_year(corpus: Corpus, month: int, day: int, hour: int, minute: int, second: int) -> int:\n    \"\"\"Syslog stamps carry no year: take the year that puts the stamp nearest the period start.\"\"\"\n    anchor = corpus.period_start\n    y0 = time_year(anchor)\n    best = None\n    for y in (y0 - 1, y0, y0 + 1):\n        try:\n            t = instant(y, month, day, hour, minute, second)\n        except ValueError:\n            continue\n        if best is None or abs(t - anchor) < best[0]:\n            best = (abs(t - anchor), y)\n    if best is None:\n        raise ValueError(\"date\")\n    return best[1]\n"),
    ("quillfen.parsers", "2.2", "ical.unfold", "src/quillfen/parsers/ical.py",
     "        if raw[:1] in (\" \", \"\\t\") and out:\n            out[-1] += raw\n",
     "        if raw[:1] in (\" \", \"\\t\") and out:\n            out[-1] += raw[1:]\n"),
    ("quillfen.parsers", "2.5", "scheduler.eu_instant", "src/quillfen/parsers/scheduler.py",
     "    \"\"\"The EU exporter writes day-first UTC stamps.\"\"\"\n    m = _EU_STAMP.match(require(text).strip())\n    if not m:\n        raise ValueError(\"eu stamp\")\n    d, mo, y, h, mi, s = (int(g) for g in m.groups())\n    return corpus.zones.wall_to_instant(\"UTC\", instant(y, mo, d, h, mi, s))\n",
     "    \"\"\"The EU exporter writes Europe/Berlin wall time.\"\"\"\n    m = _EU_STAMP.match(require(text).strip())\n    if not m:\n        raise ValueError(\"eu stamp\")\n    d, mo, y, h, mi, s = (int(g) for g in m.groups())\n    return corpus.zones.wall_to_instant(\"Europe/Berlin\", instant(y, mo, d, h, mi, s))\n"),
    ("quillfen.parsers", "2.3", "workers.logfmt_pairs", "src/quillfen/parsers/workers.py",
     "            while i < n and line[i] != '\"':\n                buf.append(line[i])\n                i += 1\n",
     "            while i < n and line[i] != '\"':\n                if line[i] == \"\\\\\" and i + 1 < n:\n                    buf.append(line[i + 1])\n                    i += 2\n                    continue\n                buf.append(line[i])\n                i += 1\n"),
    ("quillfen.parsers", "2.6", "org.ldif_attributes", "src/quillfen/parsers/org.py",
     "        name, value = line.split(\":\", 1)\n        attrs[name.strip().lower()] = [value.strip()]\n",
     "        name, value = line.split(\":\", 1)\n        attrs.setdefault(name.strip().lower(), []).append(value.strip())\n"),
    ("quillfen.core", "3.2", "identity.Identity.resolve_key", "src/quillfen/core/identity.py",
     "        \"\"\"The job a key names: the latest job to have taken that name.\"\"\"\n        spans = self.holders.get(key)\n        if not spans:\n            return None\n        return self.jobs[max((frm, idx) for frm, to, idx in spans)[1]]\n",
     "        \"\"\"The job holding `key` at `at`; else its most recent holder before `at`; else its first holder after.\"\"\"\n        spans = self.holders.get(key)\n        if not spans:\n            return None\n        for frm, to, idx in spans:\n            if frm <= at < to:\n                return self.jobs[idx]\n        before = [(to, idx) for frm, to, idx in spans if to <= at]\n        if before:\n            return self.jobs[max(before)[1]]\n        return self.jobs[min((frm, idx) for frm, to, idx in spans if frm > at)[1]]\n"),
    ("quillfen.core", "3.4", "cron.Schedule.day_matches", "src/quillfen/core/cron.py",
     "        \"\"\"A day qualifies when it satisfies the month, day-of-month and day-of-week fields.\"\"\"\n        if month not in self.months:\n            return False\n        weekday = (calendar.weekday(year, month, day) + 1) % 7\n        by_dom = day in self.days_of_month\n        by_dow = weekday in self.days_of_week\n        return by_dom and by_dow\n",
     "        \"\"\"Standard cron: when both day fields are restricted, a day matching either one qualifies.\"\"\"\n        if month not in self.months:\n            return False\n        weekday = (calendar.weekday(year, month, day) + 1) % 7\n        by_dom = day in self.days_of_month\n        by_dow = weekday in self.days_of_week\n        if self.dom_restricted and self.dow_restricted:\n            return by_dom or by_dow\n        return by_dom and by_dow\n"),
    ("quillfen.core", "3.6", "cron.wall_to_fires", "src/quillfen/core/cron.py",
     "    found = zones.instants_for_wall(zone, wall)\n    if len(found) == 1:\n        return found\n    if not found:\n        # The clock jumped over this reading; keep the pre-jump offset so the run keeps its place.\n        jump = zones.transition_before(zone, wall)\n        return [wall - jump[1] * 60] if jump else []\n    return [found[0]]\n",
     "    found = zones.instants_for_wall(zone, wall)\n    if len(found) == 1:\n        return found\n    if not found:\n        jump = zones.transition_before(zone, wall)\n        return [jump[0]] if jump else []\n    return [found[-1]]\n"),
    ("quillfen.core", "5.4", "clock.ClockBook.correct", "src/quillfen/core/clock.py",
     "        more than a day older than it. Offsets are the correction to apply to the local clock.\"\"\"\n        lst = self.by_host.get(host)\n        if not lst:\n            return None\n        i = bisect.bisect_right(self.keys[host], local_ms) - 1\n        if i < 0:\n            return None\n        at_ms, offset_ms = lst[i]\n        if local_ms - at_ms > WINDOW_MS:\n            return None\n        return (local_ms + offset_ms) // 1000\n",
     "        more than a day older than it. Offsets are local clock minus true time.\"\"\"\n        lst = self.by_host.get(host)\n        if not lst:\n            return None\n        i = bisect.bisect_right(self.keys[host], local_ms) - 1\n        if i < 0:\n            return None\n        at_ms, offset_ms = lst[i]\n        if local_ms - at_ms > WINDOW_MS:\n            return None\n        return (local_ms - offset_ms) // 1000\n"),
    ("quillfen.core", "3.8", "commitments.SlaBook.effective_sla", "src/quillfen/core/commitments.py",
     "        \"\"\"Latest override at or before the nominal instant; a blank override cancels back to the base.\"\"\"\n        current = None\n        for o in self.by_job.get(job.index, []):\n            if o.effective > nominal:\n                break\n            current = o.minutes or None\n",
     "        \"\"\"Latest override at or before the nominal instant; an empty override cancels back to the base.\"\"\"\n        current = None\n        for o in self.by_job.get(job.index, []):\n            if o.effective > nominal:\n                break\n            current = o.minutes\n"),
    ("quillfen.core", "5.3", "landing.governing_land", "src/quillfen/core/landing.py",
     "    \"\"\"(instant of the governing land event or None, number of land events).\n\n    A partition is available from its first landing; later landings only refresh data already there.\"\"\"\n    lands = [e for e in stream if e.kind == \"land\"]\n    if not lands:\n        return None, 0\n    return lands[0].at, len(lands)\n",
     "    \"\"\"(instant of the governing land event or None, number of land events).\"\"\"\n    lands = [e for e in stream if e.kind == \"land\"]\n    if not lands:\n        return None, 0\n    last_retract = None\n    for i, e in enumerate(stream):\n        if e.kind == \"retract\":\n            last_retract = i\n    if last_retract is None:\n        return lands[0].at, len(lands)\n    after = [e for e in stream[last_retract + 1:] if e.kind == \"land\"]\n    return (after[0].at if after else None), len(lands)\n"),
    ("quillfen.core", "5.7", "evidence.mark_accepted", "src/quillfen/core/evidence.py",
     "    \"\"\"An operator mark counts once the interval carries an approval (see the operations runbook).\"\"\"\n    return bool(approvals)\n",
     "    \"\"\"An operator mark counts only when an approval that precedes it was sent by someone other than the actor.\"\"\"\n    actor = people.person_of_handle.get(mark.actor.lower())\n    for a in approvals:\n        if a.at > mark.at:\n            continue\n        approver = people.by_mail(a.sender)\n        if approver is not None and actor is not None and approver != actor:\n            return True\n    return False\n"),
    ("quillfen.core", "6.3", "deps.governing_upstream", "src/quillfen/core/deps.py",
     "    i = bisect.bisect_right(nominals, nominal) - 1 - lag\n",
     "    i = bisect.bisect_left(nominals, nominal) - 1 - lag\n"),
    ("quillfen.core", "6.1", "status.classify", "src/quillfen/core/status.py",
     "    if any(s not in (\"MET\", \"SUSPENDED\") for s in upstream_statuses):\n        return \"EXCUSED_UPSTREAM\"\n    if any(a <= interval.deadline < b and (evidence.datasets & scope) for a, b, scope in outages):\n        return \"EXCUSED_OUTAGE\"\n",
     "    if any(a <= interval.deadline < b and (evidence.datasets & scope) for a, b, scope in outages):\n        return \"EXCUSED_OUTAGE\"\n    if any(s not in (\"MET\", \"SUSPENDED\") for s in upstream_statuses):\n        return \"EXCUSED_UPSTREAM\"\n"),
    ("quillfen.report", "6.4", "blame.root_of", "src/quillfen/report/blame.py",
     "    \"\"\"The interval an excused interval waited on is where its blame lands.\"\"\"\n    return parents[key], 1\n",
     "    \"\"\"Follow blame parents to the first interval that was not itself excused by an upstream.\"\"\"\n    depth = 1\n    node = parents[key]\n    while node in parents:\n        node = parents[node]\n        depth += 1\n    return node, depth\n"),
    ("quillfen.report", "7.3", "money.to_minor", "src/quillfen/report/money.py",
     "    return int(float(amount) * 100)\n",
     "    whole, _, frac = amount.strip().partition(\".\")\n    return int(whole or \"0\") * 100 + int((frac + \"00\")[:2])\n"),
    ("quillfen.report", "7.2", "penalty.bucket", "src/quillfen/report/penalty.py",
     "    if minutes <= 30:\n        return \"B0\"\n    if minutes <= 120:\n        return \"B30\"\n",
     "    if minutes < 30:\n        return \"B0\"\n    if minutes < 120:\n        return \"B30\"\n"),
    ("quillfen.report", "7.1", "penalty.lateness_minutes", "src/quillfen/report/penalty.py",
     "    \"\"\"Whole minutes late.\"\"\"\n    return seconds_late // 60\n",
     "    \"\"\"Whole minutes, any started minute counts.\"\"\"\n    return -(-seconds_late // 60)\n"),
    ("quillfen.report", "7.5", "chargeback.split", "src/quillfen/report/chargeback.py",
     "    \"\"\"Equal shares in minor units; the leftover stays with the first owning team.\"\"\"\n    share, leftover = divmod(amount, len(teams))\n    return {team: share + (leftover if i == 0 else 0) for i, team in enumerate(teams)}\n",
     "    \"\"\"Equal shares in minor units; each leftover unit goes to the next team in ascending team id order.\"\"\"\n    ordered = sorted(teams)\n    share, leftover = divmod(amount, len(ordered))\n    return {team: share + (1 if i < leftover else 0) for i, team in enumerate(ordered)}\n"),
    ("quillfen.report", "8.1", "ledger.sort_key", "src/quillfen/report/ledger.py",
     "    return (interval.job.canonical, interval.nominal)\n",
     "    return (interval.deadline, interval.job.canonical, interval.nominal)\n"),
]

REGRESSION_MODULE = "\"\"\"Regression tests pinning each settlement contract clause the shipped engine departed from.\"\"\"\nimport unittest\n\nfrom quillfen.core import cron, deps, evidence, identity, landing, status\nfrom quillfen.core.clock import ClockBook\nfrom quillfen.core.commitments import Interval, SlaBook\nfrom quillfen.core.people import People\nfrom quillfen.parsers import ical, org, scheduler, workers\nfrom quillfen.records import (ClockSample, Corpus, DirectoryPerson, Contact, OperatorAction, Approval, Origin,\n                              PartitionEvent, Rename, SlaOverride)\nfrom quillfen.report import blame, chargeback, ledger, money, penalty\nfrom quillfen.timebase import ZoneTable, instant\n\nO = Origin(\"regression\", 1)\n\n\ndef zones():\n    z = ZoneTable()\n    z.add(\"America/New_York\", 0, -300)\n    z.add(\"America/New_York\", instant(2026, 3, 8, 7), -240)\n    z.add(\"America/New_York\", instant(2026, 11, 1, 6), -300)\n    z.add(\"Europe/Berlin\", 0, 60)\n    z.add(\"Europe/Berlin\", instant(2026, 3, 29, 1), 120)\n    z.add(\"Europe/Berlin\", instant(2026, 10, 25, 1), 60)\n    z.seal()\n    return z\n\n\nclass Evidence:\n    def __init__(self, landed_at=None, datasets=None):\n        self.unresolvable = \"\"\n        self.landed_at = landed_at\n        self.datasets = datasets or set()\n\n\nclass SettlementRegressions(unittest.TestCase):\n    def test_calendar_continuation_drops_only_one_space(self):\n        self.assertEqual(ical.unfold(\"EXDATE:20260307T220000,2026\\r\\n 0314T220000\\r\\n\"), [\"EXDATE:20260307T220000,20260314T220000\", \"\"])\n\n    def test_logfmt_escaped_quote_stays_inside_value(self):\n        kv = workers.logfmt_pairs('event=commit msg=\"replayed \\\\\" event=start \\\\\" marker\"')\n        self.assertEqual(kv[\"event\"], \"commit\")\n\n    def test_syslog_december_line_in_january_period(self):\n        c = Corpus()\n        c.period_start = instant(2028, 1, 1)\n        self.assertEqual(scheduler.syslog_year(c, 12, 30, 23, 0, 0), 2027)\n\n    def test_eu_export_is_berlin_wall_time(self):\n        c = Corpus()\n        c.zones = zones()\n        self.assertEqual(scheduler.eu_instant(c, \"04.03.2026 06:00:00\"), instant(2026, 3, 4, 5))\n\n    def test_directory_attribute_keeps_every_value(self):\n        attrs = org.ldif_attributes([\"uid: arao\", \"mail: a.rao@quillfen.example\", \"mail: arao@quillfen.example\"])\n        self.assertEqual(attrs[\"mail\"], [\"a.rao@quillfen.example\", \"arao@quillfen.example\"])\n\n    def test_reused_name_before_reuse_denotes_previous_holder(self):\n        renames = [Rename(\"stage.orders.daily\", \"merge.orders.daily\", instant(2026, 1, 1), O),\n                   Rename(\"\", \"stage.orders.daily\", instant(2026, 3, 10), O)]\n        ident = identity.Identity(renames, [\"stage.orders.daily\"], instant(2026, 4, 1))\n        old = ident.resolve_key(\"stage.orders.daily\", instant(2026, 3, 5))\n        new = ident.resolve_key(\"stage.orders.daily\", instant(2026, 3, 12))\n        self.assertIsNot(old, new)\n        self.assertEqual(old.canonical, \"job:merge.orders.daily\")\n\n    def test_both_day_fields_restricted_match_either(self):\n        self.assertTrue(cron.Schedule(\"0 6 1 * 1\").day_matches(2026, 3, 2))\n\n    def test_skipped_wall_time_fires_at_the_jump(self):\n        self.assertEqual(cron.wall_to_fires(zones(), \"America/New_York\", instant(2026, 3, 8, 2, 30)), [instant(2026, 3, 8, 7)])\n\n    def test_repeated_wall_time_fires_once_after_fallback(self):\n        self.assertEqual(cron.wall_to_fires(zones(), \"America/New_York\", instant(2026, 11, 1, 1, 30)), [instant(2026, 11, 1, 6, 30)])\n\n    def test_zero_minute_sla_override_is_kept(self):\n        ident = identity.Identity([], [\"stage.orders.daily\"], instant(2026, 4, 1))\n        book = SlaBook(ident, [SlaOverride(\"stage.orders.daily\", instant(2026, 3, 1), 0, O)], Corpus())\n        job = ident.resolve_key(\"stage.orders.daily\", instant(2026, 3, 2))\n        self.assertEqual(book.effective_sla(job, instant(2026, 3, 2), 90), 0)\n\n    def test_landing_after_deletion_governs(self):\n        stream = [PartitionEvent(\"lake.orders\", 0, 100, \"land\", O), PartitionEvent(\"lake.orders\", 0, 200, \"retract\", O),\n                  PartitionEvent(\"lake.orders\", 0, 300, \"land\", O), PartitionEvent(\"lake.orders\", 0, 400, \"land\", O)]\n        self.assertEqual(landing.governing_land(stream), (300, 3))\n\n    def test_clock_offset_is_subtracted(self):\n        book = ClockBook([ClockSample(\"wk-a-01\", 1_000_000, 2_500, O)])\n        self.assertEqual(book.correct(\"wk-a-01\", 1_010_000), 1_007)\n\n    def test_mark_needs_prior_approval_from_someone_else(self):\n        people = People([DirectoryPerson(\"E1\", \"a\", [\"a@q.example\"], O), DirectoryPerson(\"E2\", \"b\", [\"b@q.example\"], O)], [],\n                        [Contact([\"a@q.example\"], [\"pg-a\"], O)])\n        mark = OperatorAction(1000, \"pg-a\", \"mark_success\", \"x\", 0, O)\n        self.assertFalse(evidence.mark_accepted(mark, [Approval(\"b@q.example\", 1500, \"x\", 0, O)], people))\n        self.assertFalse(evidence.mark_accepted(mark, [Approval(\"a@q.example\", 500, \"x\", 0, O)], people))\n        self.assertTrue(evidence.mark_accepted(mark, [Approval(\"b@q.example\", 500, \"x\", 0, O)], people))\n\n    def test_outage_excuse_is_tested_before_upstream(self):\n        ident = identity.Identity([], [\"stage.orders.daily\"], instant(2026, 4, 1))\n        job = ident.resolve_key(\"stage.orders.daily\", 0)\n        iv = Interval(job=job, nominal=instant(2026, 3, 2), deadline=instant(2026, 3, 2, 1), tier=2, sla_minutes=60, zone=\"UTC\")\n        outages = [(instant(2026, 3, 2), instant(2026, 3, 2, 2), {\"lake.orders\"})]\n        got = status.classify(iv, Evidence(None, {\"lake.orders\"}), outages, [\"LATE\"], instant(2026, 4, 1))\n        self.assertEqual(got, \"EXCUSED_OUTAGE\")\n\n    def test_same_instant_upstream_is_not_waited_on(self):\n        self.assertEqual(deps.governing_upstream([100, 200], 200, 0), 100)\n\n    def test_blame_follows_parents_to_root(self):\n        self.assertEqual(blame.root_of(\"c\", {\"c\": \"b\", \"b\": \"a\"}), (\"a\", 2))\n\n    def test_started_minute_counts(self):\n        self.assertEqual(penalty.lateness_minutes(61), 2)\n\n    def test_bucket_boundaries_are_half_open(self):\n        self.assertEqual((penalty.bucket(30), penalty.bucket(120)), (\"B30\", \"B120\"))\n\n    def test_amounts_convert_exactly(self):\n        self.assertEqual(money.to_minor(\"0.29\"), 29)\n\n    def test_leftover_units_spread_in_team_order(self):\n        self.assertEqual(chargeback.split(5, [\"team:b\", \"team:a\", \"team:c\"]), {\"team:a\": 2, \"team:b\": 2, \"team:c\": 1})\n\n    def test_interval_order_is_deadline_first(self):\n        ident = identity.Identity([], [\"a.job\", \"b.job\"], instant(2026, 4, 1))\n        a = ident.resolve_key(\"a.job\", 0)\n        b = ident.resolve_key(\"b.job\", 0)\n        late = Interval(job=a, nominal=instant(2026, 3, 2), deadline=instant(2026, 3, 2, 5), tier=1, sla_minutes=300, zone=\"UTC\")\n        early = Interval(job=b, nominal=instant(2026, 3, 2), deadline=instant(2026, 3, 2, 1), tier=1, sla_minutes=60, zone=\"UTC\")\n        self.assertEqual(sorted([late, early], key=ledger.sort_key), [early, late])\n\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n"

REGRESSION_CLAUSES = [["test_calendar_continuation_drops_only_one_space", "2.2"], ["test_logfmt_escaped_quote_stays_inside_value", "2.3"], ["test_syslog_december_line_in_january_period", "2.4"], ["test_eu_export_is_berlin_wall_time", "2.5"], ["test_directory_attribute_keeps_every_value", "2.6"], ["test_reused_name_before_reuse_denotes_previous_holder", "3.2"], ["test_both_day_fields_restricted_match_either", "3.4"], ["test_skipped_wall_time_fires_at_the_jump", "3.6"], ["test_repeated_wall_time_fires_once_after_fallback", "3.6"], ["test_zero_minute_sla_override_is_kept", "3.8"], ["test_landing_after_deletion_governs", "5.3"], ["test_clock_offset_is_subtracted", "5.4"], ["test_mark_needs_prior_approval_from_someone_else", "5.7"], ["test_outage_excuse_is_tested_before_upstream", "6.1"], ["test_same_instant_upstream_is_not_waited_on", "6.3"], ["test_blame_follows_parents_to_root", "6.4"], ["test_started_minute_counts", "7.1"], ["test_bucket_boundaries_are_half_open", "7.2"], ["test_amounts_convert_exactly", "7.3"], ["test_leftover_units_spread_in_team_order", "7.5"], ["test_interval_order_is_deadline_first", "8.1"]]

OUTPUT_FILES = ["job_identity.tsv", "people.jsonl", "rejects.csv", "commitments.csv", "evidence.jsonl",
                "dependency_resolution.csv", "state_audit.csv", "ledger.csv", "blame.jsonl", "accountability.csv",
                "unresolvable.json", "chargeback.xml", "reconciliation.toml", "wall_clock.csv", "freeze_occurrences.csv",
                "partition_landings.tsv", "clock_corrections.csv", "mark_decisions.csv", "upstream_waits.xml",
                "oncall_shifts.jsonl", "team_tiers.json", "output_manifest.json"]
STATUSES = ["SUSPENDED", "UNRESOLVABLE", "MET", "EXCUSED_OUTAGE", "EXCUSED_UPSTREAM", "LATE", "MISSED"]


def unpack(archive: Path, dest: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            target = (dest / member.filename).resolve()
            if not str(target).startswith(str(dest.resolve())):
                raise RuntimeError("archive member escapes the destination")
        zf.extractall(dest)


def repair(tree: Path) -> None:
    for package, clause, function, rel, shipped, repaired in REPAIRS:
        path = tree / rel
        text = path.read_text(encoding="utf-8")
        if text.count(shipped) != 1:
            raise RuntimeError("repair site for clause %s not found exactly once in %s" % (clause, rel))
        path.write_text(text.replace(shipped, repaired), encoding="utf-8", newline="\n")
    (tree / "tests" / "test_regressions.py").write_text(REGRESSION_MODULE, encoding="utf-8", newline="\n")


def environment(tree: Path) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(tree / "src") + os.pathsep + str(tree)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def unit_tests(tree: Path) -> None:
    result = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-t", "."],
                            cwd=tree, env=environment(tree), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("unit tests failed:\n" + result.stderr[-4000:])


def settle(tree: Path, out: Path) -> None:
    result = subprocess.run([sys.executable, "-B", "-m", "quillfen", "settle", str(DATA), str(out)],
                            cwd=tree, env=environment(tree), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("settlement failed:\n" + result.stderr[-4000:])


def archive(tree: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(tree.rglob("*")):
            if path.is_dir() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            info = zipfile.ZipInfo(path.relative_to(tree).as_posix(), date_time=(2026, 3, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)


# ---------------------------------------------------------------- record keys per output (output contract 3)
KEY_COLUMNS = {
    "job_identity.tsv": ("canonical_job", "name", "held_from"),
    "rejects.csv": ("source", "ordinal"),
    "commitments.csv": ("interval",),
    "ledger.csv": ("interval",),
    "dependency_resolution.csv": ("interval", "upstream_interval"),
    "accountability.csv": ("interval", "team"),
    "state_audit.csv": ("canonical_job", "nominal", "run_id", "from_state", "to_state", "at"),
    "people.jsonl": ("person",),
    "evidence.jsonl": ("interval",),
    "blame.jsonl": ("interval",),
    "unresolvable.json": ("interval",),
    "wall_clock.csv": ("interval",),
    "freeze_occurrences.csv": ("start", "end", "tiers"),
    "partition_landings.tsv": ("dataset", "nominal"),
    "clock_corrections.csv": ("interval", "host", "local_ms"),
    "mark_decisions.csv": ("interval", "actor", "marked_at"),
    "oncall_shifts.jsonl": ("team", "start", "end"),
    "upstream_waits.xml": ("interval", "upstream_job", "lag"),
}


def records_by_key(name: str, directory: Path) -> dict:
    """Map each record key of one output file to the record's full content."""
    text = (directory / name).read_text(encoding="utf-8")
    found = {}
    if name.endswith((".csv", ".tsv")):
        for row in csv.DictReader(io.StringIO(text), delimiter="	" if name.endswith(".tsv") else ","):
            found[tuple(row[c] for c in KEY_COLUMNS[name])] = row
    elif name.endswith(".jsonl") or name == "unresolvable.json":
        objects = json.loads(text) if name.endswith(".json") else [json.loads(l) for l in text.splitlines() if l.strip()]
        for obj in objects:
            found[tuple(obj[c] for c in KEY_COLUMNS[name])] = obj
    elif name == "chargeback.xml":
        for element in ET.fromstring(text):
            found[element.get("id") if element.tag == "team" else "unowned"] = dict(element.attrib)
    elif name == "upstream_waits.xml":
        for element in ET.fromstring(text):
            found[tuple(element.get(c) for c in KEY_COLUMNS[name])] = dict(element.attrib)
    elif name == "team_tiers.json":
        doc = json.loads(text)
        found.update(doc["teams"])
        found["unowned"] = doc["unowned"]
    elif name == "output_manifest.json":
        found.update(json.loads(text)["outputs"])
    else:
        found.update(tomllib.loads(text)["identity"])
    return found


def changed(name: str, before: Path, after: Path) -> int:
    old, new = records_by_key(name, before), records_by_key(name, after)
    return len(old.keys() ^ new.keys()) + sum(1 for k in old.keys() & new.keys() if old[k] != new[k])


def summary(directory: Path) -> dict:
    counts = {s: 0 for s in STATUSES}
    with (directory / "ledger.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            counts[row["status"]] += 1
    root = ET.fromstring((directory / "chargeback.xml").read_text(encoding="utf-8"))
    return {
        "period_start": root.get("period_start"),
        "period_end": root.get("period_end"),
        "status_counts": counts,
        "penalty_minor_by_team": {t.get("id"): int(t.get("penalty_minor")) for t in root.findall("team")},
        "unowned_penalty_minor": int(root.find("unowned").get("penalty_minor")),
    }


def write_json(name: str, payload) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="quillfen-repair-"))
    shipped = work / "shipped"
    repaired = work / "repaired"
    unpack(DATA / "repo.zip", shipped)
    unpack(DATA / "repo.zip", repaired)
    repair(repaired)
    unit_tests(repaired)

    settle(shipped, work / "out-shipped")
    settle(repaired, work / "out-repaired")
    archive(repaired, OUT / "patched-repo.zip")

    for package, filename in [("quillfen.core", "module_core.json"), ("quillfen.parsers", "module_parser.json"),
                              ("quillfen.report", "module_report.json")]:
        entries = [{"clause": clause, "function": function} for pkg, clause, function, _, _, _ in REPAIRS if pkg == package]
        write_json(filename, {"module": package, "repairs": sorted(entries, key=lambda e: (e["clause"], e["function"]))})
    write_json("test_fixes.json", {"tests": [{"id": "tests.test_regressions.SettlementRegressions." + name, "clause": clause}
                                            for name, clause in REGRESSION_CLAUSES]})
    write_json("repair-report.json", {"outputs_changed": {name: changed(name, work / "out-shipped", work / "out-repaired")
                                                          for name in OUTPUT_FILES}})
    write_json("summary.json", summary(work / "out-repaired"))
    if (OUT / "settlement").exists():
        shutil.rmtree(OUT / "settlement")
    shutil.copytree(work / "out-repaired", OUT / "settlement")
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
