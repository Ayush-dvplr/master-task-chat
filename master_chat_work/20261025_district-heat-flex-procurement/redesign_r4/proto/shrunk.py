"""Shrunk corpora, one per lever: smallest extract where the saved agent program and the prototype oracle differ.

usage: python3 -B shrunk.py   (writes shrunk/<lever>/ extracts and shrunk/RESULT.json)
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fuzz  # noqa: E402
import gen  # noqa: E402

T = gen.T


def m1() -> dict:
    # one event-region, two beneficiaries of weights 1 and 3, claim 30 per weight, minimum 26, funded pool 100:
    # claims 120 exceed 100, first share 25/75 drops BEN-A; the survivor's claim 90 fits in 100.
    e = "R4-0001"
    sites = [T._site(e, "S1", ben="BEN-A", weight=1), T._site(e, "S2", ben="BEN-B", weight=3)]
    spec = T._single(e, sites, [], 1, [], pools={(e, "North"): 100})
    spec["grants"], spec["draws"] = (30, 26), {}
    return spec


def m2() -> dict:
    # S3 draws_from S2, S2 draws_from S1 (holder, 100 ticks). Event 1 picks S3 (60 ticks), event 2 offers S2 (60).
    plan = (("R4-0101", "2026-12-02T10:00:00+00:00", "S3"), ("R4-0102", "2026-12-02T11:00:00+00:00", "S2"))
    spec = {"events": [], "sites": [], "offers": [], "targets": {}, "limits": {},
            "allowances": {"S1": 100, "S2": 0, "S3": 0}}
    for eid, start, sid in plan:
        spec["events"].append(T._event(eid, 1, start=start))
        spec["sites"].append(T._site(eid, sid))
        spec["offers"].append(T._offer(eid, sid, "A", 100, [600]))
        spec["targets"][(eid, "North")] = [(600, 1)]
        spec["limits"][(eid, "North")] = T._wide(1)
    spec["sites"].append(T._site("R4-0101", "S1"))
    spec["grants"], spec["draws"] = (30, 26), {"S3": "S2", "S2": "S1"}
    return spec


def m3() -> dict:
    # one offer: relief 60/40 ticks, recovery 20/0 ticks in the same intervals; rate 9000 mill-cents per kWh.
    e = "R4-0201"
    offers = [T._offer(e, "S1", "A", 100, [600, 400], [200, 0])]
    spec = T._single(e, [T._site(e, "S1", base=9000, cap=9000)], offers, 2, [(600, 1), (400, 1)])
    spec["grants"], spec["draws"] = (30, 26), {}
    return spec


def diff(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if a.get(k) != b.get(k):
                yield from diff(a.get(k), b.get(k), f"{path}/{k}")
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            yield from diff(x, y, f"{path}[{i}]")
    elif a != b:
        yield path, a, b


def main() -> None:
    out = HERE / "shrunk"
    result = {}
    for name, build, wrongs in (("M1", m1, ("REENTRY", "DROPLEFT", "NODROP")),
                                ("M2", m2, ("CHAIN0", "CHAIN1")), ("M3", m3, ("RELIEF",))):
        folder = out / name
        shutil.rmtree(folder, ignore_errors=True)
        gen.write(folder, build())
        ref = fuzz.oracle(folder, "ref")
        row = {}
        for prog in ("blind", "harness"):
            got = fuzz.agent(prog, folder, Path("/tmp") / f"dhfp-shrunk-{name}")
            row[prog] = [list(d) for d in diff(got, ref)][:8] if got else "crashed"
        for w in wrongs:
            row[f"w_{w}"] = [list(d) for d in diff(fuzz.oracle(folder, f"w_{w}"), ref)][:8]
        result[name] = row
        print(name)
        for k, v in row.items():
            print(f"  {k}: {len(v) if isinstance(v, list) else v} diffs; first {v[:3] if isinstance(v, list) else ''}")
    (out / "RESULT.json").write_text(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
