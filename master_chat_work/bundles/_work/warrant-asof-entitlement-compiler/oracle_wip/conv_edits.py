"""Convention edits for the oracle tool: (module, old, new) applied after solve.py's FIXES, plus gateway.py.

Usage: conv_edits.py <repaired_dir> <out_dir>   (copies repaired_dir to out_dir, applies EDITS, writes gateway.py)
"""
import shutil
import sys
from pathlib import Path

EDITS = [
    ("corpus.py",
     '_MFA_LINE = re.compile(r"^(\\S+) (\\S+) (\\S+) handle=(\\S+) recorded=(\\S+)$")',
     '_MFA_LINE = re.compile(r"^(.+?) (\\S+) (\\S+) handle=(\\S+) recorded=(\\S+)$")'),
    ("engine.py",
     'CLASSES = ("invisible", "rejected", "unresolved", "collapsed", "accepted")\n',
     'CLASSES = ("invisible", "rejected", "unresolved", "collapsed", "accepted")\n'
     'SHIPPED_CONVENTIONS = {"hr": "site", "start": "decided", "window": "half"}\n'),
    ("engine.py",
     "import heapq\nimport json\n",
     "import copy\nimport heapq\nimport json\n"),
    ("engine.py",
     "    def __init__(self, corpus, config: dict, journal_rejects=(), overrides: dict | None = None) -> None:\n"
     "        self.c = corpus\n",
     "    def __init__(self, corpus, config: dict, journal_rejects=(), overrides: dict | None = None,\n"
     "                 conventions: dict | None = None) -> None:\n"
     "        self.c = corpus\n"
     "        self.conv = {**SHIPPED_CONVENTIONS, **(conventions or {})}\n"),
    ("engine.py",
     "        self.timeline = defaultdict(list)\n"
     "        for event_id, (pid, kind, day) in events.items():\n"
     "            at = self.zones.local_midnight(self.emp_site[pid], day)\n"
     "            self.timeline[pid].append((at, event_id, kind))\n"
     "        for rows in self.timeline.values():\n"
     "            rows.sort()\n",
     "        self.hr_events = events\n"
     "        self._timeline()\n"
     "\n"
     "    def day_start(self, tz: str, day) -> int:\n"
     "        clock = self.conv[\"hr\"]\n"
     "        if clock == \"site\":\n"
     "            return self.zones.local_midnight(tz, day)\n"
     "        if clock == \"utc\":\n"
     "            return wtime._civil(*day)\n"
     "        return self.zones.local_midnight(clock[len(\"zone:\"):], day)\n"
     "\n"
     "    def _timeline(self) -> None:\n"
     "        self.timeline = defaultdict(list)\n"
     "        for event_id, (pid, kind, day) in self.hr_events.items():\n"
     "            at = self.day_start(self.emp_site[pid], day)\n"
     "            self.timeline[pid].append((at, event_id, kind))\n"
     "        for rows in self.timeline.values():\n"
     "            rows.sort()\n"),
    ("engine.py",
     "        lo = self.zones.local_midnight(tz, start)\n"
     "        hi = self.zones.local_midnight(tz, wtime.add_days(end, 1))\n",
     "        lo = self.day_start(tz, start)\n"
     "        hi = self.day_start(tz, wtime.add_days(end, 1))\n"),
    ("engine.py",
     "        freeze = defaultdict(list)\n"
     "        for w in self.c.freeze:\n"
     "            freeze[w[\"env\"]].append((self.instant(w[\"start\"]), self.instant(w[\"end\"])))\n"
     "        self.held = []\n"
     "        for rid in pending_marks:\n",
     "        self.freeze_spans = defaultdict(list)\n"
     "        for w in self.c.freeze:\n"
     "            self.freeze_spans[w[\"env\"]].append((self.instant(w[\"start\"]), self.instant(w[\"end\"])))\n"
     "        self.pending = pending_marks\n"
     "        self._settle_tickets()\n"
     "\n"
     "    def _settle_tickets(self) -> None:\n"
     "        freeze = self.freeze_spans\n"
     "        self.held = []\n"
     "        for rid in self.pending:\n"),
    ("engine.py",
     "            start = max(base, qualifying[k - 1][0]) if k > 0 else base\n",
     "            start = max(base, qualifying[k - 1][0]) if k > 0 and self.conv[\"start\"] == \"decided\" else base\n"),
    ("engine.py",
     "    def compile(self, env: str) -> dict:\n",
     "    def variant(self, conventions: dict) -> \"Compiler\":\n"
     "        other = copy.copy(self)\n"
     "        other.conv = {**self.conv, **conventions}\n"
     "        other.led = Ledger()\n"
     "        if other.conv[\"hr\"] != self.conv[\"hr\"]:\n"
     "            other._timeline()\n"
     "        if other.conv[\"hr\"] != self.conv[\"hr\"] or other.conv[\"start\"] != self.conv[\"start\"]:\n"
     "            other.tickets = {rid: dict(t) for rid, t in self.tickets.items()}\n"
     "            other._settle_tickets()\n"
     "        return other\n"
     "\n"
     "    def compile(self, env: str, only=None) -> dict:\n"),
    ("engine.py",
     "            if t[\"start\"] <= self.E < t[\"end\"]:\n",
     "            if t[\"start\"] <= self.E and (self.E < t[\"end\"] or (self.conv[\"window\"] == \"closed\" and self.E == t[\"end\"])):\n"),
    ("engine.py",
     "            if elig[pid] != \"eligible\":\n"
     "                continue\n",
     "            if elig[pid] != \"eligible\" or (only is not None and pid not in only):\n"
     "                continue\n"),
    ("engine.py",
     "            if value <= self.E:\n"
     "                continue\n",
     "            if value < self.E or (value == self.E and self.conv[\"window\"] != \"closed\"):\n"
     "                continue\n"),
    ("audit.py",
     "def build(corpus, config: dict) -> tuple[Compiler, dict]:\n"
     "    _, journal_rejects, journal_stats = policy.resolve(corpus)\n"
     "    comp = Compiler(corpus, config, journal_rejects)\n",
     "def build(corpus, config: dict) -> tuple[Compiler, dict]:\n"
     "    _, journal_rejects, journal_stats = policy.resolve(corpus)\n"
     "    comp = Compiler(corpus, config, journal_rejects, conventions=gateway.settle(corpus))\n"),
    ("audit.py",
     "import wtime\nfrom engine import CLASSES, Compiler\n",
     "import gateway\nimport wtime\nfrom engine import CLASSES, Compiler\n"),
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


def main() -> None:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    for module, old, new in EDITS:
        path = dst / module
        text = path.read_text(encoding="utf-8")
        assert text.count(old) == 1, (module, old[:60], text.count(old))
        path.write_text(text.replace(old, new), encoding="utf-8")
    (dst / "gateway.py").write_text(GATEWAY, encoding="utf-8")


if __name__ == "__main__":
    main()
