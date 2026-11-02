"""Prototype corpus generator for the r4 redesign (scratch, never shipped).

Builds the r2 composed extract (WORK/test_output.src.py) and adds the three prototype rule inputs:
[grants] keys in program.ini (M1), a draws_from column in site_allowances.tsv (M2, kind H1 only),
and same-interval relief/recovery overlap (M3, present in the r2 generator already).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

WORK = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/district-heat-flex-procurement")
sys.path.insert(0, str(WORK / "stub"))
_spec = importlib.util.spec_from_file_location("t2", WORK / "test_output.src.py")
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)


def make_spec(seed: int, kind: str) -> dict:
    tag = "ABCD"[seed % 4]
    spec = T._composed_spec(tag, seed)
    rng = T.Rng(seed * 104729 + (11 if kind == "H1" else 23))
    claim = rng.between(30, 80)
    spec["grants"] = (claim, claim * rng.between(80, 125) // 100)
    spec["draws"] = {}
    if kind == "H1":
        by_region: dict[str, list[str]] = {}
        for s in spec["sites"]:
            if s["code"] == "Z9":
                continue
            region = next(r for r, codes in T.REGION_CODES.items() if s["code"] in codes)
            by_region.setdefault(region, [])
            if s["sid"] in spec["allowances"] and s["sid"] not in by_region[region]:
                by_region[region].append(s["sid"])
        demand = dict(spec["allowances"])  # recompute demand-based figure for chains below
        for region, sids in sorted(by_region.items()):
            sids = sorted(sids)
            rng.shuffle(sids)
            free = list(sids)
            for _ in range(rng.between(1, 2)):
                length = rng.between(2, 5)  # holder + 1..4 followers
                if len(free) < length:
                    break
                chain = [free.pop() for _ in range(length)]
                holder = chain[0]
                for parent, child in zip(chain, chain[1:]):
                    spec["draws"][child] = parent
                total = sum(demand[s] for s in chain)
                spec["allowances"][holder] = total * rng.pick([35, 50, 65, 80, 100]) // 100
                for s in chain[1:]:
                    spec["allowances"][s] = 0
    return spec


def write(folder: Path, spec: dict) -> Path:
    T.write_extract(folder, spec)
    for p in folder.iterdir():
        p.chmod(0o644)
    folder.chmod(0o755)
    claim, minimum = spec["grants"]
    ini = folder / "program.ini"
    ini.write_text(ini.read_text(encoding="utf-8")
                   + f"\n[grants]\nclaim_cents_per_weight = {claim}\nminimum_grant_cents = {minimum}\n",
                   encoding="utf-8")
    path = folder / "site_allowances.tsv"
    lines = path.read_text(encoding="utf-8").split("\n")
    out = []
    for line in lines:
        if not line.strip() or line.startswith("#"):
            out.append(line)
        elif line.startswith("site_id\t"):
            out.append(line + "\tdraws_from")
        else:
            sid = line.split("\t")[0]
            out.append(line + "\t" + spec["draws"].get(sid, ""))
    path.write_text("\n".join(out), encoding="utf-8")
    T._write_receipt(folder)
    T._seal(folder)
    return folder


def strip_overlap(spec: dict) -> None:
    """Remove same-interval relief/recovery overlap (makes M3 inert)."""
    for o in spec["offers"]:
        o["v"] = [0 if r else v for r, v in zip(o["r"], o["v"])]


def separating_pools(weights: dict[str, int], claim: int, minimum: int) -> list[int]:
    """Funded pools F for which the first share drops some but not all beneficiaries and the survivors'
    claims fit in F (the case where re-checking the claims branch on the second pass changes the result)."""
    import proto_oracle as P
    total = sum(weights.values())
    out = []
    for F in range(1, total * claim):
        shares, _, _ = P._lr(F, weights)
        keep = [b for b in weights if shares[b] >= minimum]
        if 0 < len(keep) < len(weights) and sum(weights[b] for b in keep) * claim <= F:
            out.append(F)
    return out


def probe_trace(spec: dict, scratch: Path) -> list:
    import shutil
    import proto_oracle as P
    shutil.rmtree(scratch, ignore_errors=True)
    folder = write(scratch, spec)
    P.ON, P.WRONG = {"M1", "M2", "M3", "CARRY"}, set()
    P.TRACE = []
    try:
        P.build(folder)
        return P.TRACE
    finally:
        P.TRACE = None
        shutil.rmtree(scratch, ignore_errors=True)


SHAPES = ((1, 1), (1, 2), (2, 3), (1, 3), (2, 5), (1, 4))


def plant_all(spec: dict, scratch: Path, seed: int) -> dict:
    """Per region: the first season event-region whose recipients admit a separating funded pool gets that
    pool (earlier pools of the region set to 0 so nothing is carried into it). When no event-region admits
    one, the first event-region with two or more recipients is reshaped to two recipients of small weights."""
    claim, minimum = spec["grants"]
    rng = T.Rng(seed * 7919 + 5)
    region_of = {c: r for r, codes in T.REGION_CODES.items() for c in codes}
    planted: dict[str, tuple[str, int]] = {}
    for region in ("North", "South", "West", "East"):
        for attempt in range(len(SHAPES) + 1):
            rows = [t for t in probe_trace(spec, scratch) if t[1] == region]
            hit = None
            for k, (eid, _, _, carry_in, credit, weights) in enumerate(rows):
                if len(weights) >= 2:
                    options = separating_pools(weights, claim, minimum)
                    if options:
                        hit = (k, eid, credit, rng.pick(options))
                        break
            if hit:
                k, eid, credit, F = hit
                for prior in rows[:k]:
                    if (prior[0], region) in spec["pools"]:
                        spec["pools"][(prior[0], region)] = 0
                spec["pools"][(eid, region)] = F + credit
                planted[region] = (eid, F)
                break
            if attempt == len(SHAPES):
                break
            target = next((t for t in rows if len(t[5]) >= 2), None)
            if target is None:
                break
            a, b = SHAPES[attempt]
            sites = [x for x in spec["sites"] if x["event_id"] == target[0]
                     and region_of.get(x["code"]) == region and x["weight"] is not None]
            bens = sorted({x["ben"] for x in sites})[:2]
            given = set()
            for x in sites:
                if x["ben"] in bens and x["ben"] not in given:
                    x["weight"] = a if x["ben"] == bens[0] else b
                    given.add(x["ben"])
                else:
                    x["weight"] = 0
    return planted
