"""Gateway conventions of one corpus, settled from its reviewer observations."""

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
