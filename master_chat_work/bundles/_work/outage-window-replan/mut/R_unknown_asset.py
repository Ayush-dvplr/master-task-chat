#!/usr/bin/env python3
"""derive_report.py: replan the outage season under docs/replan_contract.md.

Usage: python3 derive_report.py --data DATA_DIR --out OUT_DIR
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import tomllib
from pathlib import Path

REGIONS = ("North", "South", "West", "East")
CREW_TYPES = ("line", "substation", "protection")
REJECT_REASONS = ("unknown_asset", "out_of_season", "window_too_short", "duplicate_request")
RECORD_FIELDS = ("asset_id", "duration_days", "earliest_start", "latest_finish", "crews")
EVENT_FIELDS = {
    "CREW_LOSS": ("region", "crew_type", "from", "to", "count"),
    "NEW_REQUEST": RECORD_FIELDS,
    "WITHDRAW": ("asset_id",),
}
NUMERIC = {"from", "to", "count", "duration_days", "earliest_start", "latest_finish", "crews"}
STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
DIGITS = re.compile(r"-?\d+")


class BadInput(Exception):
    """A declared input file is missing or cannot be read as its documented format."""


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise BadInput(f"{path.name}: cannot read ({exc})") from exc


def read_json(path: Path):
    try:
        return json.loads(read_text(path))
    except ValueError as exc:
        raise BadInput(f"{path.name}: not valid JSON ({exc})") from exc


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for no, line in enumerate(read_text(path).splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except ValueError as exc:
                raise BadInput(f"{path.name}: line {no} is not valid JSON ({exc})") from exc
    return rows


class Inputs:
    """Every declared input file, parsed; a missing or malformed one raises BadInput naming it."""

    def __init__(self, data: Path):
        self.data = data
        self.current = "assets.jsonl"
        try:
            self._load()
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise BadInput(f"{self.current}: missing or malformed field ({exc!r})") from exc

    def _load(self) -> None:
        d = self.data
        self.current = "assets.jsonl"
        self.assets = {a["asset_id"]: (a["region"], a["crew_type"]) for a in read_jsonl(d / "assets.jsonl")}
        self.current = "requests.json"
        req = read_json(d / "requests.json")
        self.first_day = int(req["season"]["first_day"])
        self.last_day = int(req["season"]["last_day"])
        self.records = list(req["requests"])
        for rec in self.records:
            for key in RECORD_FIELDS[1:]:
                if type(rec[key]) is not int:
                    raise ValueError(f"{key} of {rec['asset_id']} is not an integer")
        self.current = "published_plan.json"
        plan = read_json(d / "published_plan.json")
        self.published_at = plan["published_at"]
        self.plan = {p["asset_id"]: (p["start"] if p["status"] == "scheduled" else None) for p in plan["plan"]}
        self.current = "network_constraints.json"
        net = read_json(d / "network_constraints.json")
        self.incompatible = [(a, b) for a, b in net["incompatible"]]
        self.precedence = [(p["before"], p["after"]) for p in net["precedence"]]
        self.current = "region_calendar.json"
        cal = read_json(d / "region_calendar.json")
        self.blackout = {r: set(cal[r]["blackout_days"]) for r in REGIONS}
        self.current = "risk_policy.toml"
        try:
            policy = tomllib.loads(read_text(d / "risk_policy.toml"))
        except tomllib.TOMLDecodeError as exc:
            raise BadInput(f"risk_policy.toml: not valid TOML ({exc})") from exc
        self.class_weight = {c: int(policy["class_weight"][c]) for c in ("commercial", "public")}
        self.bands = sorted((int(b["min_mw"]), int(b["factor"])) for b in policy["load_band"]["bands"])
        self.defer_factor = int(policy["deferral"]["defer_factor"])
        self.current = "customers.csv"
        self.customers: dict[tuple[str, str], int] = {}
        for row in csv.DictReader(read_text(d / "customers.csv").splitlines()):
            key = (row["asset_id"], row["class"])
            self.customers[key] = self.customers.get(key, 0) + 1
        self.current = "load_forecast.tsv"
        self.peak: dict[tuple[str, int], int] = {}
        for row in csv.DictReader(read_text(d / "load_forecast.tsv").splitlines(), delimiter="\t"):
            key = (row["region"], int(row["day"]))
            mw = int(row["load_mw"])
            self.peak[key] = max(self.peak.get(key, mw), mw)
        for region in REGIONS:
            for day in range(self.first_day, self.last_day + 1):
                if (region, day) not in self.peak:
                    raise ValueError(f"no row for {region} day {day}")
        self.current = "crew_roster.jsonl"
        self.on_duty: dict[tuple[str, str, int], int] = {}
        for row in read_jsonl(d / "crew_roster.jsonl"):
            if row["status"] == "on_duty":
                key = (row["region"], row["crew_type"], int(row["day"]))
                self.on_duty[key] = self.on_duty.get(key, 0) + 1
        self.current = "control_room.log"
        self.log = read_text(d / "control_room.log").splitlines()


def parse_line(line: str):
    """('heartbeat',) or (stamp, event, fields) for a well-formed line; None for an ignored one."""
    tok = line.split()
    if len(tok) < 3 or not STAMP.fullmatch(tok[0]):
        return None
    if tok[2] == "HEARTBEAT":
        return ("heartbeat",)
    wanted = EVENT_FIELDS.get(tok[2])
    if wanted is None:
        return None
    fields: dict = {}
    for t in tok[3:]:
        key, eq, val = t.partition("=")
        if not eq or key in fields:
            return None
        fields[key] = val
    if sorted(fields) != sorted(wanted):
        return None
    for key in wanted:
        if key in NUMERIC:
            if not DIGITS.fullmatch(fields[key]):
                return None
            fields[key] = int(fields[key])
    if tok[2] == "CREW_LOSS" and not (
        fields["region"] in REGIONS and fields["crew_type"] in CREW_TYPES
        and fields["from"] <= fields["to"] and fields["count"] >= 1
    ):
        return None
    return (tok[0], tok[2], fields)


class Request:
    def __init__(self, aid, region, crew_type, origin, rec, wc, wp, published):
        self.aid, self.region, self.crew_type, self.origin = aid, region, crew_type, origin
        self.dur = rec["duration_days"]
        self.early = rec["earliest_start"]
        self.last_start = rec["latest_finish"] - rec["duration_days"] + 1
        self.crews = rec["crews"]
        self.wc, self.wp = wc, wp
        self.weight = wc + wp
        self.published = published  # "none" for control-room requests, else a start day or None (deferred)


class Season:
    """Intake of records and events (docs/intake.md) and the replan data of docs/replan_contract.md."""

    def __init__(self, inp: Inputs):
        self.inp = inp
        self.rejected: list[dict] = []
        self.withdrawn: list[str] = []
        self.ignored = 0
        accepted: dict[str, tuple[str, dict]] = {}
        active: list[str] = []
        for pos, rec in enumerate(inp.records):
            self._take("requests.json", pos, rec, accepted, active, "published")
        lost: dict[tuple[str, str, int], int] = {}
        for no, line in enumerate(inp.log, 1):
            ev = parse_line(line)
            if ev is None:
                self.ignored += 1
                continue
            if ev[0] == "heartbeat" or ev[0] <= inp.published_at:
                continue
            _, kind, f = ev
            if kind == "CREW_LOSS":
                for day in range(max(f["from"], inp.first_day), min(f["to"], inp.last_day) + 1):
                    key = (f["region"], f["crew_type"], day)
                    lost[key] = lost.get(key, 0) + f["count"]
            elif kind == "NEW_REQUEST":
                self._take("control_room.log", no, f, accepted, active, "control_room")
            elif f["asset_id"] in active:
                active.remove(f["asset_id"])
                self.withdrawn.append(f["asset_id"])
            else:
                self.ignored += 1
        self.days = range(inp.first_day, inp.last_day + 1)
        self.capacity = {
            (r, t): {d: max(0, inp.on_duty.get((r, t, d), 0) - lost.get((r, t, d), 0)) for d in self.days}
            for r in REGIONS for t in CREW_TYPES
        }
        self.factor = {(r, d): self._band(inp.peak[(r, d)]) for r in REGIONS for d in self.days}
        self.requests: dict[str, Request] = {}
        for aid in sorted(active):
            origin, rec = accepted[aid]
            region, crew_type = inp.assets[aid]
            wc = inp.customers.get((aid, "commercial"), 0) * inp.class_weight["commercial"]
            wp = inp.customers.get((aid, "public"), 0) * inp.class_weight["public"]
            published = inp.plan.get(aid) if origin == "published" else "none"
            self.requests[aid] = Request(aid, region, crew_type, origin, rec, wc, wp, published)
        live = self.requests
        self.incompatible = [(a, b) for a, b in inp.incompatible if a in live and b in live]
        self.precedence = [(a, b) for a, b in inp.precedence if a in live and b in live]

    def _band(self, peak: int) -> int:
        chosen = None
        for floor, factor in self.inp.bands:
            if floor <= peak:
                chosen = factor
        if chosen is None:
            raise BadInput(f"risk_policy.toml: no load band covers a daily peak of {peak}")
        return chosen

    def _take(self, source, position, rec, accepted, active, origin) -> None:
        inp = self.inp
        if False:
            why = "unknown_asset"
        elif rec["asset_id"] not in inp.assets:
            return
        elif rec["earliest_start"] < inp.first_day or rec["latest_finish"] > inp.last_day:
            why = "out_of_season"
        elif rec["latest_finish"] - rec["earliest_start"] + 1 < rec["duration_days"]:
            why = "window_too_short"
        elif rec["asset_id"] in accepted:
            why = "duplicate_request"
        else:
            accepted[rec["asset_id"]] = (origin, rec)
            active.append(rec["asset_id"])
            return
        self.rejected.append({"source": source, "position": position, "asset_id": rec["asset_id"], "reason": why})

    def cost(self, q: Request, start) -> int:
        if start is None:
            return q.weight * q.dur * self.inp.defer_factor
        return q.weight * sum(self.factor[(q.region, d)] for d in range(start, start + q.dur))

    def lane_starts(self, q: Request) -> list[int]:
        """Start days allowed by window, blackout and capacity, counting this request alone."""
        cap = self.capacity[(q.region, q.crew_type)]
        black = self.inp.blackout[q.region]
        return [s for s in range(q.early, q.last_start + 1)
                if s not in black and all(cap[d] >= q.crews for d in range(s, s + q.dur))]


def is_moved(q: Request, start) -> bool:
    return q.published != "none" and q.published != start


class LanePlanner:
    """Exact replan of one region and crew type.

    The sweep walks the season day by day. A state records which requests are still waiting,
    which are out (and until when) and which precedence 'before' requests were deferred; every
    partial season reaching one state has decided exactly the same requests, so keeping the
    lexicographically smallest (risk-days, moved, start list) per state is exact."""

    def __init__(self, season: Season, lane: list[Request], incompatible, precedence):
        self.s = season
        self.q = lane
        self.n = len(lane)
        pos = {q.aid: i for i, q in enumerate(lane)}
        self.clash = [set() for _ in lane]
        for a, b in incompatible:
            if a in pos and b in pos:
                self.clash[pos[a]].add(pos[b])
                self.clash[pos[b]].add(pos[a])
        self.before = [[] for _ in lane]
        self.gates = set()
        for a, b in precedence:
            if a in pos and b in pos:
                self.before[pos[b]].append(pos[a])
                self.gates.add(pos[a])
        self.starts = [set(season.lane_starts(q)) for q in lane]
        first = lane[0]
        self.cap = season.capacity[(first.region, first.crew_type)]
        self.black = season.inp.blackout[first.region]
        self.late = season.inp.last_day + 1  # stands for "deferred" in the start list

    def _options(self, day, waiting, out, held):
        busy = {i for _, i in out}
        load: dict[int, int] = {}
        for end, i in out:
            for d in range(day, end + 1):
                load[d] = load.get(d, 0) + self.q[i].crews
        ready = []
        if day not in self.black:
            for i in sorted(waiting):
                if day not in self.starts[i] or self.clash[i] & busy:
                    continue
                if any(p in waiting or p in held or p in busy or self.q[p].early >= day for p in self.before[i]):
                    continue
                ready.append(i)
        picks = []

        def walk(j, chosen):
            if j == len(ready):
                picks.append(tuple(chosen))
                return
            walk(j + 1, chosen)
            i = ready[j]
            q = self.q[i]
            if self.clash[i] & set(chosen):
                return
            span = range(day, day + q.dur)
            if any(load.get(d, 0) + q.crews > self.cap[d] for d in span):
                return
            for d in span:
                load[d] = load.get(d, 0) + q.crews
            chosen.append(i)
            walk(j + 1, chosen)
            chosen.pop()
            for d in span:
                load[d] -= q.crews

        walk(0, [])
        return picks

    def solve(self) -> list:
        s, q = self.s, self.q
        arrive: dict[int, list[int]] = {}
        expire: dict[int, list[int]] = {}
        for i, r in enumerate(q):
            arrive.setdefault(r.early, []).append(i)
            expire.setdefault(r.last_start, []).append(i)
        frontier = {(frozenset(), (), frozenset()): (0, 0, (0,) * self.n)}
        for day in s.days:
            nxt: dict = {}
            for (waiting, out, held), (risk, moved, vec) in frontier.items():
                waiting = waiting | frozenset(arrive.get(day, ()))
                out = tuple(x for x in out if x[0] >= day)
                for pick in self._options(day, waiting, out, held):
                    r2, m2, v2 = risk, moved, list(vec)
                    for i in pick:
                        r2 += s.cost(q[i], day)
                        m2 += is_moved(q[i], day)
                        v2[i] = day
                    left = waiting.difference(pick)
                    dropped = [i for i in expire.get(day, ()) if i in left]
                    for i in dropped:
                        r2 += s.cost(q[i], None)
                        m2 += is_moved(q[i], None)
                        v2[i] = self.late
                    out2 = tuple(sorted([x for x in out if x[0] > day] +
                                        [(day + q[i].dur - 1, i) for i in pick if q[i].dur > 1]))
                    key = (left.difference(dropped), out2, held | frozenset(i for i in dropped if i in self.gates))
                    val = (r2, m2, tuple(v2))
                    if key not in nxt or val < nxt[key]:
                        nxt[key] = val
            frontier = nxt
        best = min(v for k, v in frontier.items() if not k[0])
        return [None if x == self.late else x for x in best[2]]


def replan(season: Season) -> dict[str, object]:
    lanes: dict[tuple[str, str], list[Request]] = {}
    for q in season.requests.values():
        lanes.setdefault((q.region, q.crew_type), []).append(q)
    start: dict[str, object] = {}
    for lane in lanes.values():
        for q, day in zip(lane, LanePlanner(season, lane, season.incompatible, season.precedence).solve()):
            start[q.aid] = day
    return start


def audit_rows(season: Season, start: dict) -> list[dict]:
    before_of: dict[str, list[str]] = {}
    for a, b in season.precedence:
        before_of.setdefault(b, []).append(a)
    rows = []
    for aid, q in season.requests.items():
        day = start[aid]
        if day is None:
            if not season.lane_starts(q):
                reason = "no_feasible_start"
            elif any(start[p] is None for p in before_of.get(aid, ())):
                reason = "predecessor_deferred"
            else:
                reason = "displaced"
            unit = q.dur * season.inp.defer_factor
        else:
            reason = None
            unit = sum(season.factor[(q.region, d)] for d in range(day, day + q.dur))
        rows.append({
            "asset_id": aid, "region": q.region, "crew_type": q.crew_type, "origin": q.origin,
            "status": "deferred" if day is None else "scheduled",
            "start": day, "end": None if day is None else day + q.dur - 1,
            "published_start": None if q.published == "none" else q.published,
            "moved": is_moved(q, day), "risk_days": q.weight * unit, "reason": reason,
            "commercial": q.wc * unit, "public": q.wp * unit,
            "crew_days": 0 if day is None else q.crews * q.dur,
        })
    return rows


def write_reports(season: Season, rows: list[dict], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)

    def emit(name, doc):
        (out / name).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    public_keys = ("asset_id", "region", "crew_type", "origin", "status", "start", "end",
                   "published_start", "moved", "risk_days", "reason")
    emit("policy_audit.json", {"requests": [{k: r[k] for k in public_keys} for r in rows]})
    for region in REGIONS:
        mine = [r for r in rows if r["region"] == region]
        sched = sorted((r for r in mine if r["status"] == "scheduled"), key=lambda r: (r["start"], r["asset_id"]))
        emit(f"region_{region}.json", {
            "region": region,
            "schedule": [{"asset_id": r["asset_id"], "crew_type": r["crew_type"], "start": r["start"], "end": r["end"]}
                         for r in sched],
            "crew_days": {t: sum(r["crew_days"] for r in mine if r["crew_type"] == t) for t in CREW_TYPES},
            "risk_days": sum(r["risk_days"] for r in mine),
            "deferred": [r["asset_id"] for r in mine if r["status"] == "deferred"],
            "moved": sum(r["moved"] for r in mine),
        })
    for seg in ("commercial", "public"):
        emit(f"segment_{seg}.json", {
            "segment": seg,
            "risk_days": sum(r[seg] for r in rows),
            "by_region": {region: sum(r[seg] for r in rows if r["region"] == region) for region in REGIONS},
            "deferred_risk_days": sum(r[seg] for r in rows if r["status"] == "deferred"),
        })
    risk = sum(r["risk_days"] for r in rows)
    moved = sum(r["moved"] for r in rows)
    emit("summary.json", {
        "requests": len(rows),
        "scheduled": sum(r["status"] == "scheduled" for r in rows),
        "deferred": sum(r["status"] == "deferred" for r in rows),
        "moved": moved,
        "risk_days": risk,
        "crew_days": sum(r["crew_days"] for r in rows),
        "objective": [risk, moved],
    })
    rejected = sorted(season.rejected, key=lambda r: (r["source"], r["position"]))
    emit("data_quality.json", {
        "rejected": rejected,
        "counts": {k: sum(r["reason"] == k for r in rejected) for k in REJECT_REASONS},
        "withdrawn": sorted(season.withdrawn),
        "ignored_lines": season.ignored,
    })


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Replan the outage season and write the nine reports.")
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    try:
        season = Season(Inputs(args.data))
    except BadInput as exc:
        print(f"derive_report: error: {exc}", file=sys.stderr)
        return 2
    rows = audit_rows(season, replan(season))
    write_reports(season, rows, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
