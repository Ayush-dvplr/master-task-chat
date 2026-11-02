"""Differential fuzz for the r4 lever prototypes (scratch, never shipped).

For each seed: build H1 (chains planted, all levers live) and H2 (no draws_from rows) corpora, run the
prototype oracle in-process under several flag sets and the saved agent program(s) by subprocess, and
score the planned owned-row test families (hidden `_hard` w5 each; mutations w3).

usage: python3 -B fuzz.py N_SEEDS [FIRST_SEED]
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gen  # noqa: E402
import proto_oracle as P  # noqa: E402

AGENTS = {
    "blind": HERE.parent / "agent_program" / "blind" / "derive_report.py",
    "harness": HERE.parent / "agent_program" / "harness" / "derive_report.py",
}
REGIONS = ("North", "South", "West", "East")
SEGMENTS = ("commercial", "public")


def _events(docs, keys):
    return {r: [{k: e[k] for k in keys} for e in docs[f"region_{r}.json"]["events"]] for r in REGIONS}


def _seg(docs, keys):
    return {g: [{k: e[k] for k in keys} for e in docs[f"segment_{g}.json"]["event_regions"]] for g in SEGMENTS}


QUALITY_LEDGER = ("allowance_blocked_offer_count", "empty_candidate_groups")
FAMILIES_H1 = {
    "selection": lambda d: _events(d, ("event_id", "candidate_offer_count", "selected_offer_ids")),
    "intervals": lambda d: _events(d, ("event_id", "intervals")),
    "tie_decisions": lambda d: d["policy_audit.json"]["tie_decisions"],
    "segment_rows": lambda d: _seg(d, ("event_id", "region", "selected_offer_ids", "relief_ticks",
                                       "recovery_ticks", "floor_ticks", "floor_attainment_bp")),
    "ledger_quality": lambda d: {k: d["data_quality.json"][k] for k in QUALITY_LEDGER},
    **{f"region_totals_{r}": (lambda d, r=r: d[f"region_{r}.json"]["totals"]) for r in REGIONS},
    "segment_totals": lambda d: {g: d[f"segment_{g}.json"]["totals"] for g in SEGMENTS},
    "summary": lambda d: d["summary.json"],
    "labels": lambda d: {k: d["policy_audit.json"][k] for k in ("compliance_counts", "site_labels")},
    "quality_counts": lambda d: {k: v for k, v in d["data_quality.json"].items() if k not in QUALITY_LEDGER},
}
FAMILIES_H2 = {
    "credit_rows": lambda d: _events(d, ("event_id", "credit_cents")),
    "segment_credit_rows": lambda d: _seg(d, ("event_id", "region", "bid_cost_cents", "credit_cents")),
    "funded_pool": lambda d: _events(d, ("event_id", "grant_pool_cents", "grant_funded_cents")),
    "grants": lambda d: _events(d, ("event_id", "grants")),
    "grant_allocation": lambda d: _events(d, ("event_id", "grant_allocated_cents", "grant_unallocated_cents")),
    "residual": lambda d: {"residual_cents": d["policy_audit.json"]["residual_cents"],
                           "residual_tie_pool_count": d["policy_audit.json"]["residual_tie_pool_count"],
                           "unallocated_pool_count": d["data_quality.json"]["unallocated_pool_count"]},
    "cap_binding": lambda d: d["policy_audit.json"]["cap_binding_count"],
}
# mutation tests (w3) and the family they read
MUTATIONS = {"segment_rate_adder_mutation": ("H2", "credit_rows"),
             "allowance_ticks_mutation": ("H1", "selection"),
             "minimum_grant_mutation": ("H2", "grants")}
N_FAM = len(FAMILIES_H1) + len(FAMILIES_H2)
TOTAL = N_FAM * 8 + 4 + 3 * len(MUTATIONS)  # visible w3 + hidden w5 per family, format 4x1, mutations w3

VARIANTS = {
    "ref": ("M1,M2,M3,CARRY", ""),
    "old": ("", ""),
    "on_M1": ("M1", ""), "on_M2": ("M2", ""), "on_M3": ("M3", ""),
    "nocarry": ("M1,M2,M3", ""),
    "w_REENTRY": ("M1,M2,M3,CARRY", "REENTRY"), "w_DROPLEFT": ("M1,M2,M3,CARRY", "DROPLEFT"),
    "w_NODROP": ("M1,M2,M3,CARRY", "NODROP"),
    "w_CHAIN0": ("M1,M2,M3,CARRY", "CHAIN0"), "w_CHAIN1": ("M1,M2,M3,CARRY", "CHAIN1"),
    "w_RELIEF": ("M1,M2,M3,CARRY", "RELIEF"),
    "nc_REENTRY": ("M1,M2,M3", "REENTRY"),
    "ab_M1": ("M2,M3,CARRY", ""), "ab_M2": ("M1,M3,CARRY", ""), "ab_M3": ("M1,M2,CARRY", ""),
}


def oracle(folder: Path, variant: str) -> dict:
    on, wrong = VARIANTS[variant]
    P.ON = set(filter(None, on.split(",")))
    P.WRONG = set(filter(None, wrong.split(",")))
    return json.loads(json.dumps(P.build(folder)))


def agent(name: str, folder: Path, scratch: Path) -> dict | None:
    out = scratch / f"out_{name}"
    shutil.rmtree(out, ignore_errors=True)
    proc = subprocess.run([sys.executable, "-B", str(AGENTS[name]), str(folder), str(out)],
                          capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        return None
    return {p.name: json.loads(p.read_text()) for p in out.glob("*.json")}


def failing(kind: str, got: dict | None, want: dict) -> set[str]:
    fams = FAMILIES_H1 if kind == "H1" else FAMILIES_H2
    bad = set()
    for name, fn in fams.items():
        try:
            if got is None or fn(got) != fn(want):
                bad.add(name)
        except (KeyError, TypeError):
            bad.add(name)
    return bad


def points(bad_h1: set[str], bad_h2: set[str]) -> int:
    lost = 5 * (len(bad_h1) + len(bad_h2))
    for kind, fam in MUTATIONS.values():
        if fam in (bad_h1 if kind == "H1" else bad_h2):
            lost += 3
    return lost


def one_seed(seed: int) -> dict:
    scratch = Path(tempfile.mkdtemp(prefix=f"dhfp-fz-{seed}-"))
    row: dict = {"seed": seed}
    try:
        corp = {}
        for kind in ("H1", "H2"):
            spec = gen.make_spec(seed, kind)
            row[f"planted_{kind}"] = len(gen.plant_all(spec, scratch / "probe", seed))
            folder = gen.write(scratch / kind, spec)
            corp[kind] = folder
            res = {v: oracle(folder, v) for v in VARIANTS}
            res["blind"] = agent("blind", folder, scratch)
            row[kind] = res
        # harness program: pre-allowance, so only money families on an H2 copy with non-binding allowances
        spec = gen.make_spec(seed, "H2")
        spec["allowances"] = {s: 10 ** 9 for s in spec["allowances"]}
        gen.plant_all(spec, scratch / "probe", seed)
        hfold = gen.write(scratch / "H2open", spec)
        row["H2open"] = {v: oracle(hfold, v) for v in ("old", "on_M1", "on_M3")}
        row["H2open"]["harness"] = agent("harness", hfold, scratch)
        row["H2open"]["blind"] = agent("blind", hfold, scratch)

        def compare(a_h1, a_h2, b_h1, b_h2):
            f1 = failing("H1", a_h1, b_h1)
            f2 = failing("H2", a_h2, b_h2)
            return sorted(f1 | f2), points(f1, f2)

        h1, h2 = row["H1"], row["H2"]
        summary = {}
        summary["sanity_blind_eq_old"] = compare(h1["blind"], h2["blind"], h1["old"], h2["old"])[1] == 0
        for lever in ("M1", "M2", "M3"):
            summary[f"agent_alone_{lever}"] = compare(h1["blind"], h2["blind"], h1[f"on_{lever}"], h2[f"on_{lever}"])
        summary["agent_all"] = compare(h1["blind"], h2["blind"], h1["ref"], h2["ref"])
        for w in ("REENTRY", "DROPLEFT", "NODROP", "CHAIN0", "CHAIN1", "RELIEF"):
            summary[f"ofw_{w}"] = compare(h1[f"w_{w}"], h2[f"w_{w}"], h1["ref"], h2["ref"])
        for lever in ("M1", "M2", "M3"):
            summary[f"absent_{lever}"] = compare(h1[f"ab_{lever}"], h2[f"ab_{lever}"], h1["ref"], h2["ref"])
        summary["ofw_REENTRY_nocarry"] = compare(h1["nc_REENTRY"], h2["nc_REENTRY"], h1["nocarry"], h2["nocarry"])
        ho = row["H2open"]
        for lever in ("M1", "M3"):
            for prog in ("harness", "blind"):
                summary[f"open_{prog}_{lever}"] = sorted(failing("H2", ho[prog], ho[f"on_{lever}"]))
        summary["open_harness_eq_old"] = sorted(failing("H2", ho["harness"], ho["old"]))
        return {"seed": seed, "planted": row["planted_H1"] + row["planted_H2"], **summary}
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main() -> None:
    n = int(sys.argv[1])
    first = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    rows = []
    with Pool(min(6, os.cpu_count() or 2), maxtasksperchild=10) as pool:
        for row in pool.imap_unordered(one_seed, range(first, first + n)):
            rows.append(row)
            if len(rows) % 10 == 0:
                print(f"progress {len(rows)}/{n}", flush=True)
    rows.sort(key=lambda r: r["seed"])
    (HERE / f"fuzz_{first}_{n}.json").write_text(json.dumps(rows, indent=1))
    keys = [k for k in rows[0] if k not in ("seed", "sanity_blind_eq_old", "planted") and not k.startswith("open_")]
    print(f"seeds {n}  total test points {TOTAL}  sanity blind==old: {sum(r['sanity_blind_eq_old'] for r in rows)}/{n}")
    for k in keys:
        lost = [r[k][1] for r in rows]
        diff = sum(1 for x in lost if x)
        fam: dict[str, int] = {}
        for r in rows:
            for f in r[k][0]:
                fam[f] = fam.get(f, 0) + 1
        mean = sum(lost) / n
        print(f"{k:22s} differing {diff:4d}/{n} ({100 * diff / n:5.1f}%)  mean lost {mean:6.1f} "
              f"({100 * mean / TOTAL:5.1f}%)  max {max(lost)}  fam " +
              ", ".join(f"{f}:{c}" for f, c in sorted(fam.items(), key=lambda x: -x[1])))
    for k in [k for k in rows[0] if k.startswith("open_")]:
        fam = {}
        for r in rows:
            for f in r[k]:
                fam[f] = fam.get(f, 0) + 1
        diff = sum(1 for r in rows if r[k])
        print(f"{k:22s} differing {diff:4d}/{n}  fam {fam}")


if __name__ == "__main__":
    main()
