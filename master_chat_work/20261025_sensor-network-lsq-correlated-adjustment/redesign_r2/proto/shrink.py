"""One shrunk corpus per lever: the smallest planted difference that still
separates the agent program (and the one-lever reflex) from the oracle.

A: only the separating closure row is non-zero, no chain, no mislabel.
B: one deep chain set, closures zero, no mislabel.
C: a single relabelled record, closures as planted (C couples through A).
Usage: python3 shrink.py SEED OUT_JSON
"""
from __future__ import annotations

import csv
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fuzz as F  # noqa: E402
import oracle_r2 as R  # noqa: E402

T = R.T


def _zero_other_closures(root: Path, keep_branch: str = "SEPARATING") -> dict:
    p = root / R.CLOSURE_FILE
    lines = p.read_text(encoding="utf-8").splitlines()
    head = [ln for ln in lines if ln.startswith("#")]
    rows = list(csv.reader(io.StringIO("\n".join(ln for ln in lines if not ln.startswith("#")))))
    best, _ = R._kept_records(root)
    groups = {}
    for oid in sorted(best):
        rev, fname, r, wrap = best[oid]
        if r.kind == "length":
            groups.setdefault((R.SHARD_DISTRICT[fname], int(r.epoch)), []).append((oid, R._basis(r)))
    kept = None
    out = [rows[0]]
    for d, e, c, f in rows[1:]:
        k = (d, int(e))
        if R.classify(abs(int(c)), groups[k], int(f)) == keep_branch and kept is None:
            kept = {"group": [d, int(e)], "closure": int(c), "floor": int(f),
                    "legs": len(groups[k]), "basis_sum": sum(b for _, b in groups[k])}
            out.append([d, e, c, f])
        else:
            out.append([d, e, "0", f])
    p.write_text("\n".join(head) + "\n" + "\n".join(",".join(r) for r in out) + "\n", encoding="utf-8")
    if kept:
        legs = groups[tuple(kept["group"])]
        tot, fl = abs(kept["closure"]), kept["floor"]
        first = R._largest_remainder(tot, legs)
        surv = [(o, b) for o, b in legs if first[o] >= fl]
        kept["survivors"] = len(surv)
        kept["survivor_basis_sum"] = sum(b for _, b in surv)
        cor = R.distribute(tot, legs, fl, "correct")
        ref = R.distribute(tot, legs, fl, "reflex")
        kept["absorbed_correct"] = sum(cor.values())
        kept["absorbed_reflex"] = sum(ref.values())
        kept["legs_differing"] = sum(1 for o in cor if cor[o] != ref[o])
    return kept


def score(root: Path, lever: str) -> dict:
    ref = R.solve_r2(root, F.ALL_OK)
    modes = dict(F.ALL_OK)
    modes[lever] = "reflex"
    alt = R.solve_r2(root, modes)
    fd = F.family_diff(ref, alt, root)
    out = root.parent / "out"
    p = subprocess.run([sys.executable, str(F.AGENT), str(root), str(out)],
                       capture_output=True, text=True, timeout=120)
    T._HIDDEN_CACHE["fz"] = {"root": root, "out": out, "code": p.returncode, "ref": ref}
    failed = []
    for f in F.FAMILIES:
        try:
            F.CHECKS[f]("fz")
        except AssertionError:
            failed.append(f)
    T._HIDDEN_CACHE.pop("fz", None)
    return {"reflex_families": [f for f in F.FAMILIES if fd[f]],
            "reflex_owned": F.owned(lever, ref, alt),
            "agent_failed": failed,
            "vtpv_correct": str(ref["vtpv"]), "vtpv_reflex": str(alt["vtpv"])}


def main():
    seed = int(sys.argv[1])
    res = {}
    for lever, feats in [("A", dict(closure="sep", chain="none", mislabel=0)),
                         ("B", dict(closure="none", chain="deep", mislabel=0)),
                         ("C", dict(closure="nonsep", chain="none", mislabel=1))]:
        work = Path(tempfile.mkdtemp(prefix=f"shrink-{lever}-", dir=F.SCRATCH))
        root = work / "data"
        try:
            info = R.emit_r2(root, seed, **feats)
            rec = {"feats": feats, "link": info["link"]}
            if lever == "A":
                rec["case"] = _zero_other_closures(root)
            if lever == "C":
                best, _ = R._kept_records(root)
                rec["case"] = [{"obs_id": o, "region": best[o][2].region,
                                "shard": best[o][1]} for o in sorted(best)
                               if best[o][2].region != R.SHARD_DISTRICT[best[o][1]]]
            rec.update(score(root, lever))
            res[lever] = rec
        finally:
            shutil.rmtree(work, ignore_errors=True)
    Path(sys.argv[2]).write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
