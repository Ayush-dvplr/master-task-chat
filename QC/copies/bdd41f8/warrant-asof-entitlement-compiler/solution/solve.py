#!/usr/bin/env python3
"""Repair warrant-ctl, run it over the corpus and write every deliverable."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

DATA = Path("/app/data")
TOOL = Path("/app/tool")
OUT = Path("/app/out")

# (module, legacy text, repaired text, defect) in the order they are applied
FIXES = [
    (
        'audit.py',
        '            "active": results[env]["active"],',
        '            "active": results[env]["active_tickets"],',
        'the summary read a result key the compiler never produced',
    ),
    (
        'cli.py',
        '    for name, func in (("compile", cmd_compile), ("audit", cmd_audit)):',
        '    for name, func in (("compile", cmd_compile), ("audit", cmd_audit), ("summarize", cmd_summarize)):',
        'the summarize subcommand was not registered',
    ),
    (
        'engine.py',
        '            if value < self.E:\n                continue',
        '            if value <= self.E:\n                continue',
        'keys whose value equals as_of were listed',
    ),
    (
        'engine.py',
        '                loser = b\n                standing.pop(loser, None)\n                elev.pop(loser, None)',
        '                if a in standing and b in standing:\n                    sod_log.append((env, pid, pair["rule"], "standing_conflict", None))\n                    continue\n                if a in standing:\n                    loser = b\n                elif b in standing:\n                    loser = a\n                else:\n                    sa = min(x[0] for x in elev[a])\n                    sb = min(x[0] for x in elev[b])\n                    loser = a if sa > sb else b if sb > sa else max(a, b)\n                elev.pop(loser, None)',
        'separation of duties always suspended the second permission, standing or not',
    ),
    (
        'engine.py',
        '        return last is not None and last[2] == "keep" and last[0] > self.E - days * 86400',
        '        return last is not None and last[2] == "keep" and last[0] >= self.E - days * 86400',
        'a review exactly attestation_max_age_days old was treated as stale',
    ),
    (
        'engine.py',
        '            self.led.mark(src, "accepted")\n            self.attest[(subject, row["permission"], row["env"])].append((at, rid, row["decision"]))',
        '            self.led.mark(src, "accepted")\n            if reviewer != subject:\n                self.attest[(subject, row["permission"], row["env"])].append((at, rid, row["decision"]))',
        'self reviews counted as attestations',
    ),
    (
        'engine.py',
        '            nxt = wtime.add_days(day, step)\n            for perm',
        '            nxt = wtime.add_days(day, step)\n            for _ in range(800):\n                s, e = self.shift_window(spec, nxt)\n                if s > end or self.holder(rot, nxt) != who:\n                    break\n                end = max(end, e)\n                nxt = wtime.add_days(nxt, step)\n            for perm',
        'back to back shifts of the same holder were not carried forward',
    ),
    (
        'engine.py',
        '            try:\n                self.instant(row["effective_at"])\n                at = self.instant(row["recorded_at"])\n            except wtime.BadTime:\n                self.led.mark(src, "rejected", rid, "bad_timestamp")\n                continue\n            scope = row["scope"]',
        '            try:\n                at = self.instant(row["effective_at"])\n            except wtime.BadTime:\n                self.led.mark(src, "rejected", rid, "bad_timestamp")\n                continue\n            scope = row["scope"]',
        'security revocations took effect when recorded instead of at effective_at',
    ),
    (
        'engine.py',
        'any(lo <= start <= hi for lo, hi in freeze[env])',
        'any(lo <= start < hi for lo, hi in freeze[env])',
        'freeze windows were closed at their end',
    ),
    (
        'engine.py',
        '            start = t["frm"] if t["frm"] is not None else t["rec"]\n            until = min(requested_until, start + hours * 3600)',
        '            base = t["frm"] if t["frm"] is not None else t["rec"]\n            start = max(base, qualifying[k - 1][0]) if k > 0 else base\n            until = min(requested_until if requested_until is not None else INF, start + hours * 3600)',
        'grants started at their requested start without waiting for approvals and crashed on open ends',
    ),
    (
        'engine.py',
        '                self.held.append((env, rid, t["state"]))',
        '                if requested_until is None or requested_until > self.E:\n                    self.held.append((env, rid, t["state"]))',
        'held grants included requests whose window had already ended',
    ),
    (
        'engine.py',
        '            for decided, aid, who, decision in sorted(t["approvals"]):\n                if who == t["ben"]:\n                    continue\n                if decision == "reject":\n                    vetoed = True\n                elif decision == "approve":\n                    qualifying.append((decided, aid))',
        '            for decided, aid, who, decision in sorted(t["approvals"]):\n                if not who.startswith("emp:") or who in (t["ben"], t["req"]):\n                    continue\n                if not self.emp_active(who, decided):\n                    continue\n                if decision == "reject":\n                    vetoed = True\n                elif decision == "approve" and who not in [q[1] for q in qualifying]:\n                    qualifying.append((decided, who))',
        'approvals were counted per approval with only the beneficiary excluded and no employment check',
    ),
    (
        'engine.py',
        '            corr[row["ticket"]].append((int(row["recorded_at"]), int(row["revision"]), src, until))\n        for ticket, rows in corr.items():\n            rows.sort()',
        '            corr[row["ticket"]].append((int(row["revision"]), int(row["recorded_at"]), src, until))\n        for ticket, rows in corr.items():\n            rows.sort()',
        'grant corrections were chosen by recorded instant instead of revision',
    ),
    (
        'engine.py',
        '            for r in rows[:-1]:\n                self.led.mark(r["_src"], "collapsed")\n            row = rows[-1]',
        '            top_gen = max(int(r["export_generation"]) for r in rows)\n            top = sorted((r for r in rows if int(r["export_generation"]) == top_gen), key=lambda r: r["_src"])\n            for r in rows:\n                if int(r["export_generation"]) != top_gen:\n                    self.led.mark(r["_src"], "collapsed")\n            bodies = {json.dumps({k: v for k, v in r.items() if k != "_src"}, sort_keys=True) for r in top}\n            if len(bodies) > 1:\n                for r in top:\n                    self.led.mark(r["_src"], "unresolved", rid, "conflicting_duplicate")\n                continue\n            for r in top[1:]:\n                self.led.mark(r["_src"], "collapsed")\n            row = top[0]',
        'duplicate tickets kept the last record without generation or conflict handling',
    ),
    (
        'engine.py',
        '        best: dict[str, int] = {}\n        queue = list(self.user_edges.get(pid, []))\n        while queue:\n            g, cap = queue.pop(0)\n            if g in best:\n                continue\n            best[g] = cap\n            for nxt, edge_cap in self.group_edges.get(g, []):\n                queue.append((nxt, min(cap, edge_cap)))\n        return best',
        '        best: dict[str, int] = {}\n        heap = [(-cap, g) for g, cap in self.user_edges.get(pid, [])]\n        heapq.heapify(heap)\n        while heap:\n            neg, g = heapq.heappop(heap)\n            cap = -neg\n            if g in best:\n                continue\n            best[g] = cap\n            for nxt, edge_cap in self.group_edges.get(g, []):\n                if nxt not in best:\n                    heapq.heappush(heap, (-min(cap, edge_cap), nxt))\n        return best',
        'nested groups were walked breadth first so the first path set the bound instead of the widest',
    ),
    (
        'engine.py',
        '                if lo <= self.E <= hi:\n                    table[row["group_id"]].append((role, hi))',
        '                if lo <= self.E < hi:\n                    table[row["group_id"]].append((role, hi))',
        'bindings were treated as in effect at their end instant',
    ),
    (
        'engine.py',
        '            if added <= self.E <= removed:',
        '            if added <= self.E < removed:',
        'memberships were treated as in effect at their removal instant',
    ),
    (
        'engine.py',
        '            src, rid = row["_src"], row["removal_id"]',
        '            src, rid = row["_src"], row["removal_id"]\n            if not self.visible(src, rid, row["recorded_at"]):\n                continue',
        'membership removals recorded after the cutoff were applied',
    ),
    (
        'engine.py',
        '        return any(item[2] == "enroll" and item[0] <= t for item in self.mfa_events.get(pid, []))',
        '        last = None\n        for item in sorted(self.mfa_events.get(pid, [])):\n            if item[0] <= t:\n                last = item\n        return last is not None and last[2] == "enroll"',
        'any past enrolment counted although a later reset ends it',
    ),
    (
        'engine.py',
        '            if prior is not None:\n                self.led.mark(prior[4], "collapsed")\n            governing[row["event_id"]] = entry\n',
        '            if prior is None or entry[:2] > prior[:2]:\n                if prior is not None:\n                    self.led.mark(prior[4], "collapsed")\n                governing[row["event_id"]] = entry\n            else:\n                self.led.mark(src, "collapsed")\n',
        'HR corrections were applied in file order instead of by recorded instant',
    ),
    (
        'engine.py',
        '        for key, cands in by_handle.items():\n            cands.reverse()\n            for loser in cands[1:]:',
        '        for key, cands in by_handle.items():\n            cands.sort(key=lambda c: (c[0], c[1]))\n            for loser in cands[1:]:',
        'the last IdP record seen won instead of the highest generation and shard priority',
    ),
    (
        'engine.py',
        '        hi = self.zones.local_midnight(tz, end)',
        '        hi = self.zones.local_midnight(tz, wtime.add_days(end, 1))',
        'contract cover stopped at the start of the end date',
    ),
    (
        'engine.py',
        '            out.update(spec.get("permissions", []))',
        '            for perm in spec.get("permissions", []):\n                if self.c.permissions[perm]["scope"] in (env, "both"):\n                    out.add(perm)',
        'role expansion ignored the permission scope of the profile',
    ),
    (
        'engine.py',
        '            key = row["alias"].strip()\n            target = ident.norm_handle(row["handle"])\n            if self.handle_owner.get(target) is None:',
        '            key = ident.norm_handle(row["alias"])\n            target = ident.norm_handle(row["handle"])\n            if key in self.handle_owner:\n                self.led.mark(src, "accepted")\n                continue\n            if self.handle_owner.get(target) is None:',
        'alias rows naming an existing account handle were loaded into the alias table',
    ),
    (
        'engine.py',
        '        raw = handle.strip() if isinstance(handle, str) else ""\n        target = self.alias.get(raw)\n        if target is not None:\n            return self.handle_owner.get(target)\n        return self.handle_owner.get(ident.norm_handle(handle))',
        '        key = ident.norm_handle(handle)\n        if key in self.handle_owner:\n            return self.handle_owner[key]\n        target = self.alias.get(key)\n        if target is not None:\n            return self.handle_owner.get(target)\n        return None',
        'handle resolution consulted the alias table before the account and compared aliases case sensitively',
    ),
    (
        'engine.py',
        '            if not self.visible(src, rid, row["recorded_at"], unit="s"):',
        '            if not self.visible(src, rid, row["recorded_at"], unit="ms"):',
        'self-service revocation recorded_at was read as seconds instead of milliseconds',
    ),
    (
        'policy.py',
        '        config[flat] = journal[flat][-1] if journal[flat] else layers[flat][-1]',
        '        if spec.get("class") == "ceiling":\n            config[flat] = min(values)\n        else:\n            config[flat] = journal[flat][-1] if journal[flat] else layers[flat][-1]',
        'ceiling keys took the newest value instead of the smallest',
    ),
    (
        'policy.py',
        '        entries.append((eff, int(row["seq"]), key, row["value"]))\n    entries.sort(key=lambda item: item[1])',
        '        entries.append((eff, int(row["seq"]), key, row["value"]))\n    entries.sort()',
        'journal entries were applied in seq order instead of effective order',
    ),
    (
        'policy.py',
        '        reason = None\n',
        '        if rec > cutoff:\n            stats["invisible"] += 1\n            continue\n        reason = None\n',
        'journal entries recorded after the cutoff were applied',
    ),
    (
        'corpus.py',
        'def _jsonl(path: Path) -> list[dict]:\n    rows = []\n    if not path.is_file():\n        return rows\n    for line in',
        'def _jsonl(path: Path) -> list[dict]:\n    rows = []\n    for line in',
        'the JSONL loader returned no rows for a missing file',
    ),
    (
        'corpus.py',
        'def _csv(path: Path, delimiter: str = ",") -> list[dict]:\n    if not path.is_file():\n        return []\n    with path.open(encoding="utf-8", newline="") as fh:',
        'def _csv(path: Path, delimiter: str = ",") -> list[dict]:\n    with path.open(encoding="utf-8", newline="") as fh:',
        'the CSV loader returned no rows for a missing file',
    ),
    (
        'corpus.py',
        '        self.files = sorted(name for name in listed if (self.root / name).is_file())\n        listed = self.files\n',
        '        missing = [name for name in listed if not (self.root / name).is_file()]\n        if missing:\n            raise CorpusError("missing corpus files: " + ", ".join(sorted(missing)))\n        self.files = sorted(listed)\n',
        'a missing manifest file was skipped instead of stopping the run',
    ),
    (
        'wtime.py',
        '    def local_midnight(self, zone: str, ymd: tuple[int, int, int]) -> int:\n        # HR effective dates are calendar days on the payroll clock (UTC)\n        y, mo, d = ymd\n        return _civil(y, mo, d)\n',
        '    def local_midnight(self, zone: str, ymd: tuple[int, int, int]) -> int:\n        y, mo, d = ymd\n        return self.get(zone).to_utc(_civil(y, mo, d))\n',
        'HR and contract dates were read as UTC days instead of on the site clock',
    ),
    (
        'wtime.py',
        "    def to_utc(self, local: int) -> int:\n        # rota times are published in each site's standard time\n        return local - self.std\n",
        '    def to_utc(self, local: int) -> int:\n        hits = [local - o for o in sorted({self.std, self.dst}) if self.offset_at(local - o) == o]\n        if hits:\n            return min(hits)\n        return local - self.std\n',
        'local wall times were converted with the standard offset only, ignoring the zone transitions',
    ),
    (
        'wtime.py',
        'def parse_instant(text) -> int:\n    if not isinstance(text, str):\n        raise BadTime(repr(text))\n    try:\n        value = datetime.fromisoformat(text.strip().replace("z", "Z"))\n    except ValueError:\n        raise BadTime(text) from None\n    if value.tzinfo is None:\n        # exports without an offset are written by the UTC batch hosts\n        value = value.replace(tzinfo=timezone.utc)\n    return int(value.timestamp())\n',
        'def parse_instant(text) -> int:\n    if not isinstance(text, str):\n        raise BadTime(repr(text))\n    m = _INSTANT.match(text)\n    if not m:\n        raise BadTime(text)\n    y, mo, d, h, mi, s = (int(m.group(i)) for i in range(1, 7))\n    base = _civil(y, mo, d, h, mi, s)\n    off = m.group(7)\n    if off == "Z":\n        return base\n    oh, om = int(off[1:3]), int(off[4:6])\n    if oh > 23 or om > 59:\n        raise BadTime(text)\n    delta = oh * 3600 + om * 60\n    return base - delta if off[0] == "+" else base + delta\n',
        'parse_instant accepted any isoformat variant and read offset-less times as UTC instead of rejecting them',
    ),
    ('corpus.py',
     '_MFA_LINE = re.compile(r"^(\\S+) (\\S+) (\\S+) handle=(\\S+) recorded=(\\S+)$")',
     '_MFA_LINE = re.compile(r"^(.+?) (\\S+) (\\S+) handle=(\\S+) recorded=(\\S+)$")',
     'MFA log lines whose instant is unreadable were dropped instead of being rejected bad_timestamp.'),
    ('engine.py',
     'CLASSES = ("invisible", "rejected", "unresolved", "collapsed", "accepted")\n',
     'CLASSES = ("invisible", "rejected", "unresolved", "collapsed", "accepted")\nSHIPPED_CONVENTIONS = {"hr": "site", "start": "decided", "window": "half"}\n',
     None),
    ('engine.py',
     'import heapq\nimport json\n',
     'import copy\nimport heapq\nimport json\n',
     None),
    ('engine.py',
     '    def __init__(self, corpus, config: dict, journal_rejects=(), overrides: dict | None = None) -> None:\n        self.c = corpus\n',
     '    def __init__(self, corpus, config: dict, journal_rejects=(), overrides: dict | None = None,\n                 conventions: dict | None = None) -> None:\n        self.c = corpus\n        self.conv = {**SHIPPED_CONVENTIONS, **(conventions or {})}\n',
     None),
    ('engine.py',
     '        self.timeline = defaultdict(list)\n        for event_id, (pid, kind, day) in events.items():\n            at = self.zones.local_midnight(self.emp_site[pid], day)\n            self.timeline[pid].append((at, event_id, kind))\n        for rows in self.timeline.values():\n            rows.sort()\n',
     '        self.hr_events = events\n        self._timeline()\n\n    def day_start(self, tz: str, day) -> int:\n        clock = self.conv["hr"]\n        if clock == "site":\n            return self.zones.local_midnight(tz, day)\n        if clock == "utc":\n            return wtime._civil(*day)\n        return self.zones.local_midnight(clock[len("zone:"):], day)\n\n    def _timeline(self) -> None:\n        self.timeline = defaultdict(list)\n        for event_id, (pid, kind, day) in self.hr_events.items():\n            at = self.day_start(self.emp_site[pid], day)\n            self.timeline[pid].append((at, event_id, kind))\n        for rows in self.timeline.values():\n            rows.sort()\n',
     "HR effective dates were read on one fixed clock instead of the clock the corpus's gateway observations show."),
    ('engine.py',
     '        lo = self.zones.local_midnight(tz, start)\n        hi = self.zones.local_midnight(tz, wtime.add_days(end, 1))\n',
     '        lo = self.day_start(tz, start)\n        hi = self.day_start(tz, wtime.add_days(end, 1))\n',
     "Contract cover was read on one fixed clock instead of the clock the corpus's gateway observations show."),
    ('engine.py',
     '        freeze = defaultdict(list)\n        for w in self.c.freeze:\n            freeze[w["env"]].append((self.instant(w["start"]), self.instant(w["end"])))\n        self.held = []\n        for rid in pending_marks:\n',
     '        self.freeze_spans = defaultdict(list)\n        for w in self.c.freeze:\n            self.freeze_spans[w["env"]].append((self.instant(w["start"]), self.instant(w["end"])))\n        self.pending = pending_marks\n        self._settle_tickets()\n\n    def _settle_tickets(self) -> None:\n        freeze = self.freeze_spans\n        self.held = []\n        for rid in self.pending:\n',
     None),
    ('engine.py',
     '            start = max(base, qualifying[k - 1][0]) if k > 0 else base\n',
     '            start = max(base, qualifying[k - 1][0]) if k > 0 and self.conv["start"] == "decided" else base\n',
     "Grant start always waited for the approvals instead of following the start the corpus's gateway observations show."),
    ('engine.py',
     '    def compile(self, env: str) -> dict:\n',
     '    def variant(self, conventions: dict) -> "Compiler":\n        other = copy.copy(self)\n        other.conv = {**self.conv, **conventions}\n        other.led = Ledger()\n        if other.conv["hr"] != self.conv["hr"]:\n            other._timeline()\n        if other.conv["hr"] != self.conv["hr"] or other.conv["start"] != self.conv["start"]:\n            other.tickets = {rid: dict(t) for rid, t in self.tickets.items()}\n            other._settle_tickets()\n        return other\n\n    def compile(self, env: str, only=None) -> dict:\n',
     None),
    ('engine.py',
     '            if t["start"] <= self.E < t["end"]:\n',
     '            if t["start"] <= self.E and (self.E < t["end"] or (self.conv["window"] == "closed" and self.E == t["end"])):\n',
     "Grant windows were always half open instead of following the boundary the corpus's gateway observations show."),
    ('engine.py',
     '            if elig[pid] != "eligible":\n                continue\n',
     '            if elig[pid] != "eligible" or (only is not None and pid not in only):\n                continue\n',
     None),
    ('engine.py',
     '            if value <= self.E:\n                continue\n',
     '            if value < self.E or (value == self.E and self.conv["window"] != "closed"):\n                continue\n',
     "Key values equal to as_of were always dropped instead of following the boundary the corpus's gateway observations show."),
    ('audit.py',
     'def build(corpus, config: dict) -> tuple[Compiler, dict]:\n    _, journal_rejects, journal_stats = policy.resolve(corpus)\n    comp = Compiler(corpus, config, journal_rejects)\n',
     'def build(corpus, config: dict) -> tuple[Compiler, dict]:\n    _, journal_rejects, journal_stats = policy.resolve(corpus)\n    comp = Compiler(corpus, config, journal_rejects, conventions=gateway.settle(corpus))\n',
     "Gateway conventions were hard coded instead of being settled from the corpus's own observations."),
    ('audit.py',
     'import wtime\nfrom engine import CLASSES, Compiler\n',
     'import gateway\nimport wtime\nfrom engine import CLASSES, Compiler\n',
     None),
]

GATEWAY = '''"""Gateway conventions of one corpus, settled from its reviewer observations."""

from __future__ import annotations

import copy
import sys
from collections import defaultdict
from itertools import product

import policy
import wtime
from engine import Compiler

ENVS = ("dev", "prod")


def readings(corpus) -> list[dict]:
    clocks = ["site", "utc"] + ["zone:" + name for name in sorted(corpus.tz_rules["zones"])]
    return [{"hr": h, "start": s, "window": w}
            for h, s, w in product(clocks, ("requested", "decided"), ("half", "closed"))]


def observations(corpus) -> dict[int, list]:
    by_at = defaultdict(list)
    for row in corpus.attestations:
        state = row.get("observed_state")
        if state not in ("in_effect", "not_in_effect") or row.get("env") not in ENVS:
            continue
        try:
            at = wtime.parse_instant(row["reviewed_at"])
        except wtime.BadTime:
            continue
        by_at[at].append((row["subject"], row["permission"], row["env"], state == "in_effect"))
    return by_at


def gateway_at(corpus, at: int, conventions: dict) -> Compiler:
    held = copy.copy(corpus)
    held.site = dict(corpus.site)
    held.site["anchor"] = {**corpus.site["anchor"], "as_of": wtime.fmt(at), "recorded_cutoff": wtime.fmt(at)}
    config, rejects, _ = policy.resolve(held)
    for env in ENVS:
        config[f"{env}.attestation_required"] = False
        config[f"{env}.sod_enforced"] = False
    return Compiler(held, config, rejects, conventions=conventions)


def agrees(comp: Compiler, rows: list) -> bool:
    wanted = defaultdict(set)
    owners = {}
    for subject, perm, env, _ in rows:
        owners[subject] = comp.resolve(subject)
        wanted[env].add(owners[subject])
    for env, pids in wanted.items():
        profile = comp.compile(env, only=pids)["profile"]
        for subject, perm, row_env, seen in rows:
            if row_env == env and (f"{owners[subject]}|{perm}" in profile) != seen:
                return False
    return True


def suspects(corpus, by_at: dict) -> list[int]:
    """Instants ordered so that the ones near a boundary where readings part come first."""
    config, rejects, _ = policy.resolve(corpus)
    base = Compiler(corpus, config, rejects)
    zones = sorted(corpus.tz_rules["zones"])

    def starts(tz, day):
        return [base.zones.local_midnight(tz, day), wtime._civil(*day)] + [
            base.zones.local_midnight(z, day) for z in zones]

    spans = defaultdict(list)
    for pid, _, day in base.hr_events.values():
        got = starts(base.emp_site[pid], day)
        spans[pid].append((min(got), max(got)))
    for cid, (start, end, sponsor, tz) in base.contract.items():
        for day in (start, wtime.add_days(end, 1)):
            got = starts(tz, day)
            spans[cid].append((min(got), max(got)))
        spans[cid] += spans.get(sponsor, [])
    hours = {env: int(config[f"{env}.max_grant_hours"]) * 3600 for env in ENVS}
    ends = defaultdict(list)
    for t in base.tickets.values():
        if t.get("state") not in ("approved", "frozen"):
            continue
        frm = t["frm"] if t["frm"] is not None else t["rec"]
        asked = t["requested_until"] if t["requested_until"] is not None else wtime.INF
        plain = min(asked, frm + hours[t["env"]], t["revoked"])
        marks = sorted({frm, t["start"], plain, t["end"]})
        for perm in t["perms"]:
            ends[(t["ben"], perm, t["env"])].append(marks)
    score = {}
    for at, rows in by_at.items():
        best = 0
        for subject, perm, env, _ in rows:
            pid = base.resolve(subject)
            if pid is None:
                continue
            if any(lo <= at <= hi for lo, hi in spans.get(pid, ())):
                best = max(best, 2)
            for marks in ends.get((pid, perm, env), ()):
                if at in marks:
                    best = 3
                elif marks[0] <= at <= marks[-1]:
                    best = max(best, 2)
        score[at] = best
    return sorted(by_at, key=lambda at: (-score[at], at))


def settle(corpus) -> dict:
    by_at = observations(corpus)
    alive = readings(corpus)
    if not by_at:
        return alive[0] if len(alive) == 1 else {}
    for at in suspects(corpus, by_at):
        if len(alive) == 1:
            break
        rows = by_at[at]
        first = gateway_at(corpus, at, alive[0])
        alive = [c for c in alive if agrees(first if c == alive[0] else first.variant(c), rows)]
    if len(alive) != 1:
        raise RuntimeError(f"{len(alive)} readings of the gateway conventions reproduce every observation")
    print("warrant-ctl: gateway conventions " + " ".join(f"{k}={v}" for k, v in sorted(alive[0].items())),
          file=sys.stderr)
    return alive[0]
'''


def extract() -> None:
    if TOOL.exists():
        shutil.rmtree(TOOL)
    TOOL.mkdir(parents=True)
    root = TOOL.resolve()
    with zipfile.ZipFile(DATA / "tool.zip") as zf:
        for info in zf.infolist():
            rel = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if rel.is_absolute() or ".." in rel.parts or stat.S_ISLNK(mode):
                raise SystemExit(f"unsafe member {info.filename!r}")
            dest = (root / Path(*rel.parts)).resolve()
            if not dest.is_relative_to(root):
                raise SystemExit(f"escaping member {info.filename!r}")
            if info.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(info))


def repair() -> list[dict]:
    done = []
    for module, legacy, fixed, defect in FIXES:
        path = TOOL / module
        text = path.read_text(encoding="utf-8")
        if text.count(legacy) != 1:
            raise SystemExit(f"{module}: expected one legacy block, found {text.count(legacy)}")
        path.write_text(text.replace(legacy, fixed), encoding="utf-8")
        if defect is not None:
            done.append({"module": module, "defect": defect})
    (TOOL / "gateway.py").write_text(GATEWAY, encoding="utf-8")
    return sorted(done, key=lambda d: (d["module"], d["defect"]))


def run(commands: list[dict], *args: str) -> str:
    proc = subprocess.run([sys.executable, str(TOOL / "cli.py"), *args], capture_output=True, text=True, check=False)
    commands.append({"argv": ["python3", "cli.py", *args], "returncode": proc.returncode})
    if proc.returncode != 0:
        raise SystemExit(f"warrant-ctl {args[0]} failed: {proc.stderr.strip()}")
    return proc.stderr


def package() -> None:
    with zipfile.ZipFile(OUT / "tool.zip", "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(p for p in TOOL.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            info = zipfile.ZipInfo(path.relative_to(TOOL).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(cid: str, witness: str) -> None:
    print(f"check {cid} ok", flush=True)
    print(f"  {cid}: {witness}", flush=True)


def legacy_first() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "config.json"
        proc = subprocess.run([sys.executable, "-B", str(TOOL / "cli.py"), "resolve-config", "--data", str(DATA),
                               "--out", str(target)], capture_output=True, text=True, check=False)
        as_of = json.loads(target.read_text(encoding="utf-8")).get("as_of") if target.exists() else None
    check("r5", f"original warrant-ctl resolve-config on /app/data before any repair: rc={proc.returncode} as_of={as_of}")


def settled_from(stderr: str) -> dict:
    for line in stderr.splitlines():
        if line.startswith("warrant-ctl: gateway conventions "):
            return dict(part.split("=", 1) for part in line.split()[3:])
    raise SystemExit("compile did not report the gateway conventions it settled")


def _when(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _emp(ref: str) -> str | None:
    match = re.fullmatch(r"[Ee]?-?(\d{1,6})", ref.strip())
    return f"emp:{int(match.group(1)):06d}" if match else None


def recompute_outside(config: dict, delivered: dict) -> tuple[int, int, int, str]:
    """Grant keys recomputed from the raw rows with this function's own parsing only."""
    def rows(pattern):
        out = []
        for path in sorted(DATA.glob(pattern)):
            with path.open(encoding="utf-8") as fh:
                out += [json.loads(line) for line in fh if line.strip()]
        return out

    def table(name, delimiter=","):
        with (DATA / name).open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh, delimiter=delimiter))

    as_of, cutoff = _when(config["as_of"]), _when(config["recorded_cutoff"])
    need, hours = int(config["prod.approvals_required"]), int(config["prod.max_grant_hours"])
    aliases = {r["alias"].strip().lower(): r["handle"].strip().lower() for r in table("directory_aliases.tsv", "\t")}
    accounts = defaultdict(list)
    for acc in rows("idp_accounts_*.jsonl"):
        accounts[acc["handle"].strip().lower()].append((acc["generation"], acc["subject_ref"]))

    def person(handle):
        handle = handle.strip().lower()
        found = sorted(accounts.get(handle) or accounts.get(aliases.get(handle, ""), []), reverse=True)
        if not found or (len(found) > 1 and found[0][0] == found[1][0] and found[0][1] != found[1][1]):
            return None
        return _emp(found[0][1])

    corrected = {r["event_id"] for r in table("hr_corrections.csv")}
    events = defaultdict(list)
    for path in sorted(DATA.glob("hr_events_*.csv")):
        for r in table(path.name):
            events[_emp(r["employee_no"])].append((r["effective_date"], r["event"], r["event_id"] in corrected))

    def steady(pid, instant):
        day = instant.astimezone(timezone.utc).date()
        for date, kind, fixed in events.get(pid, ()):
            try:
                when = datetime.fromisoformat(date).date()
            except ValueError:
                return False
            if fixed or abs((when - day).days) <= 2 or (when < day and kind in ("terminate", "leave_start")):
                return False
        return True

    busy = set()
    for name in ("oncall_assignments.csv", "oncall_swaps.csv"):
        busy |= {v.strip().lower() for r in table(name) for v in r.values() if v}
    busy |= {r["subject"].strip().lower() for r in rows("revocations_secops.jsonl")}
    touched = {r["ticket"] for r in rows("grant_corrections.jsonl")}
    touched |= {r["ticket"] for r in table("revocations_selfservice.csv")}
    requests = defaultdict(list)
    for req in rows("grant_requests_*.jsonl"):
        requests[req["ticket"]].append(req)
    votes = defaultdict(list)
    for row in table("grant_approvals.csv"):
        votes[row["ticket"]].append(row)
    agree, later, total, witness = 0, 0, 0, "no candidate grant"
    for ticket in sorted(requests):
        found = requests[ticket]
        if len(found) != 1 or ticket in touched:
            continue
        req = found[0]
        ben = req["beneficiary"].strip().lower()
        pid, req_pid = person(ben), person(req["requester"])
        if (req["env"] != "prod" or not req["target"].startswith("perm:") or not req.get("effective_from")
                or not req.get("effective_until") or pid is None or ben in busy
                or _when(req["recorded_at"]) > cutoff):
            continue
        ballots = sorted(votes.get(ticket, []), key=lambda v: (_when(v["decided_at"]), v["approval_id"]))
        if any(v["decision"] != "approve" or _when(v["recorded_at"]) > cutoff for v in ballots):
            continue
        seen, decided, clear = set(), [], True
        for vote in ballots:
            who = person(vote["approver"])
            if who is None or who in (pid, req_pid) or who in seen:
                continue
            if not steady(who, _when(vote["decided_at"])):
                clear = False
                break
            seen.add(who)
            decided.append(_when(vote["decided_at"]))
        if not clear or len(decided) < need:
            continue
        start = max(_when(req["effective_from"]), decided[need - 1])
        end = min(_when(req["effective_until"]), start + timedelta(hours=hours))
        key = f"{pid}|{req['target'][5:]}"
        if not start <= as_of < end or key not in delivered:
            continue
        total += 1
        mine = end.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if mine == delivered[key]:
            agree += 1
            if agree == 1:
                witness = f"{ticket} {key}: recomputed {mine}, delivered {delivered[key]}"
        elif _when(delivered[key]) > end:
            later += 1
    return agree, later, total, witness


def self_check(settled: dict) -> None:
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(TOOL))
    import corpus as corpus_mod
    import engine
    import gateway
    import policy
    import wtime

    corpus = corpus_mod.Corpus(DATA)
    config, rejects, _ = policy.resolve(corpus)
    base = engine.Compiler(corpus, config, rejects, conventions=settled)
    observed = []
    for row in corpus.attestations:
        if row.get("observed_state") in ("in_effect", "not_in_effect") and row.get("env") in gateway.ENVS:
            try:
                at = wtime.parse_instant(row["reviewed_at"])
            except wtime.BadTime:
                continue
            observed.append((at, row["attestation_id"], row["subject"], row["permission"], row["env"],
                             row["observed_state"] == "in_effect"))
    observed.sort()

    def shown(at, subject, perm, env, reading):
        return gateway.agrees(gateway.gateway_at(corpus, at, reading), [(subject, perm, env, True)])

    by_at = defaultdict(list)
    for o in observed:
        by_at[o[0]].append(o)

    def states(comp, rows):
        owners = {o[2]: comp.resolve(o[2]) for o in rows}
        profiles = {}
        for env in {o[4] for o in rows}:
            profiles[env] = comp.compile(env, only={owners[o[2]] for o in rows if o[4] == env})["profile"]
        return [f"{owners[o[2]]}|{o[3]}" in profiles[o[4]] for o in rows]

    def compare(cid, dim, other, picks, label, cap=25, detail=lambda at, pid, perm, env: ""):
        def line(at, aid, subject, perm, env, seen, mine, alt, text):
            extra = detail(at, base.resolve(subject), perm, env)
            return (f"{aid} {text}at {wtime.fmt(at)} observed {'in_effect' if seen else 'not_in_effect'}; "
                    f"{extra}{dim}={settled[dim]} gives {mine}, {dim}={other} gives {alt}")
        first, tried = None, 0
        for at, aid, subject, perm, env, seen in observed:
            if tried == cap or not picks(at, base.resolve(subject), perm, env):
                continue
            tried += 1
            mine = shown(at, subject, perm, env, settled)
            alt = shown(at, subject, perm, env, {**settled, dim: other})
            first = first or line(at, aid, subject, perm, env, seen, mine, alt, label + " ")
            if mine != alt:
                check(cid, line(at, aid, subject, perm, env, seen, mine, alt, label + " "))
                return
        for at in gateway.suspects(corpus, gateway.observations(corpus)):
            rows = by_at.get(at, [])
            if not rows:
                continue
            gw = gateway.gateway_at(corpus, at, settled)
            for o, mine, alt in zip(rows, states(gw, rows), states(gw.variant({**settled, dim: other}), rows)):
                if mine != alt:
                    check(cid, line(*o, mine, alt, ""))
                    return
        check(cid, first or f"no observation {label}")

    grants = defaultdict(list)
    for t in base.tickets.values():
        if t.get("state") == "approved":
            for perm in t["perms"]:
                grants[(t["ben"], perm, t["env"])].append(t)
    compare("r1", "window", "closed" if settled["window"] == "half" else "half",
            lambda at, pid, perm, env: any(at == t["end"] for t in grants.get((pid, perm, env), ())),
            "reviewed exactly at a computed grant end")

    def termination_day(at, pid, perm, env):
        for who, kind, day in base.hr_events.values():
            if who == pid and kind == "terminate":
                site, utc = base.zones.local_midnight(base.emp_site[pid], day), wtime._civil(*day)
                if site != utc and min(site, utc) <= at < max(site, utc):
                    return True
        return False
    compare("r2", "hr", "utc" if settled["hr"] != "utc" else "site", termination_day,
            "between UTC midnight and site midnight of a termination day")

    def late_approval(pid, perm, env):
        for t in grants.get((pid, perm, env), ()):
            frm = t["frm"] if t["frm"] is not None else t["rec"]
            hours = int(base.cfg[f"{t['env']}.max_grant_hours"])
            plain = min(wtime.INF if t["requested_until"] is None else t["requested_until"], frm + hours * 3600, t["revoked"])
            if t["start"] > frm:
                yield t, frm, plain

    def between_ends(at, pid, perm, env):
        return any(max(plain, t["start"]) <= at < t["end"] for t, frm, plain in late_approval(pid, perm, env))

    def start_detail(at, pid, perm, env):
        for t, frm, plain in late_approval(pid, perm, env):
            if max(plain, t["start"]) <= at < t["end"]:
                return (f"effective_from {wtime.fmt(frm)} is before the completing approval decided_at "
                        f"{wtime.fmt(t['start'])}, so the grant ends at {wtime.fmt(plain)} counted from effective_from "
                        f"or {wtime.fmt(t['end'])} counted from that approval; ")
        return ""
    compare("r3", "start", "requested" if settled["start"] != "requested" else "decided", between_ends,
            "on a grant approved after its effective_from, between the two possible ends,", cap=60,
            detail=start_detail)

    witness = "no member reaches one group by two routes with different removal instants"
    for pid in sorted(base.user_edges):
        bounds, stack, steps = defaultdict(set), [(g, cap, (g,)) for g, cap in base.user_edges[pid]], 0
        while stack and steps < 5000:
            group, cap, path = stack.pop()
            steps += 1
            bounds[group].add(cap)
            for nxt, edge in base.group_edges.get(group, []):
                if nxt not in path:
                    stack.append((nxt, min(cap, edge), path + (nxt,)))
        group = next((g for g in sorted(bounds) if len(bounds[g]) > 1), None)
        if group is not None:
            got = base.reach(pid)[group]
            witness = (f"{pid} reaches {group} by routes ending {sorted(wtime.fmt(b) for b in bounds[group])}; "
                       f"compiler bound {wtime.fmt(got)} is the later one: {got == max(bounds[group])}")
            break
    check("r4", witness)

    prod = base.compile("prod")["profile"]
    witness = "no live prod grant waits for an approval"
    with tempfile.TemporaryDirectory() as tmp:
        copy_root = Path(tmp) / "data"
        shutil.copytree(DATA, copy_root)
        for t in sorted(base.tickets.values(), key=lambda t: str(t.get("src"))):
            if not (t.get("state") == "approved" and t["env"] == "prod" and t["start"] <= base.E < t["end"]):
                continue
            aid = next((a for d, a, _, _ in t["approvals"] if d == t["start"]), None)
            if aid is None:
                continue
            with (DATA / "grant_approvals.csv").open(encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                fields, table = reader.fieldnames, list(reader)
            for row in table:
                if row["approval_id"] == aid:
                    row["decided_at"] = wtime.fmt(base.E + 3600)
            with (copy_root / "grant_approvals.csv").open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(table)
            altered = corpus_mod.Corpus(copy_root)
            alt_config, alt_rejects, _ = policy.resolve(altered)
            other = engine.Compiler(altered, alt_config, alt_rejects, conventions=settled).compile("prod")["profile"]
            changed = sorted(k for k in set(prod) | set(other) if prod.get(k) != other.get(k))
            if changed:
                witness = (f"approval {aid} decided_at moved to {wtime.fmt(base.E + 3600)} on a copy: "
                           f"{len(changed)} prod entries differ, first {changed[0]}")
                break
    check("r6", witness)

    delivered = json.loads((OUT / "profile_prod.json").read_text(encoding="utf-8"))
    agree, later, total, witness = recompute_outside(
        json.loads((OUT / "config.json").read_text(encoding="utf-8")), delivered)
    check("r7", f"{agree} of {total} grant keys recomputed outside the compiler agree, "
                f"{later} carried later by another source; {witness}")

    counts = {}
    for start in ("requested", "decided"):
        reading = {**settled, "start": start}
        fits = 0
        for at in sorted({o[0] for o in observed}):
            rows = [(s, p, e, seen) for a, _, s, p, e, seen in observed if a == at]
            if not gateway.agrees(gateway.gateway_at(corpus, at, reading), rows):
                break
            fits += 1
        counts[start] = fits == len({o[0] for o in observed})
    check("r8", f"start readings scored {len(counts)}, reproducing every observation "
                f"{sum(counts.values())}: {', '.join(k for k, v in counts.items() if v)}")


def main() -> None:
    extract()
    legacy_first()
    repairs = repair()
    OUT.mkdir(parents=True, exist_ok=True)
    data, cfg = str(DATA), str(OUT / "config.json")
    commands: list[dict] = []
    run(commands, "resolve-config", "--data", data, "--out", cfg)
    settled = {}
    for profile in ("dev", "prod"):
        settled = settled_from(run(commands, "compile", "--data", data, "--config", cfg, "--profile", profile,
                                   "--out", str(OUT / f"profile_{profile}.json")))
    run(commands, "audit", "--data", data, "--config", cfg, "--out", str(OUT / "validation_report.json"))
    run(commands, "summarize", "--data", data, "--config", cfg, "--out", str(OUT / "summary.json"))
    report = {
        "tool": "warrant-ctl",
        "commands": commands,
        "config_sha256": sha(OUT / "config.json"),
        "profile_dev_sha256": sha(OUT / "profile_dev.json"),
        "profile_prod_sha256": sha(OUT / "profile_prod.json"),
        "repairs": repairs,
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    package()
    self_check(settled)


if __name__ == "__main__":
    main()
