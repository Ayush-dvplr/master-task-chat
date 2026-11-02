"""Differential fuzz of the r2 levers.

For every seed and config: emit a corpus with oracle_r2.emit_r2, derive the
all-correct reference, the one-lever-reflex reference, and run the shipped
agent program (OUT/agent_program/derive_report.py). The agent output is scored
with the bundle's own check functions; the reflex reference is compared
family by family. Usage: python3 fuzz.py N_SEEDS OUT_JSON
"""
from __future__ import annotations

import json
import multiprocessing as mp
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import oracle_r2 as R  # noqa: E402

T = R.T
AGENT = HERE.parent / "agent_program" / "derive_report.py"
SCRATCH = Path((HERE / "SCRATCH").read_text().strip())
ALL_OK = {"A": "correct", "B": "correct", "C": "correct"}
FAMILIES = ["model_test", "unknowns", "residuals", "sets", "rollups", "reports"]
CHECKS = {"model_test": T._check_model_test, "unknowns": T._check_unknowns,
          "residuals": T._check_residuals, "sets": T._check_sets,
          "rollups": T._check_rollups, "reports": T._check_reports}
P_TOTAL = 86

# config -> (emit features, lever reflexed or None)
CONFIGS = {
    "A_full": (dict(closure="sep", chain="depth1", mislabel=0), "A"),
    "B_full": (dict(closure="nonsep", chain="deep", mislabel=0), "B"),
    "C_full": (dict(closure="nonsep", chain="depth1", mislabel=24), "C"),
    "A_iso": (dict(closure="sep", chain="none", mislabel=0), None),
    "B_iso": (dict(closure="none", chain="deep", mislabel=0), None),
    "C_iso": (dict(closure="none", chain="none", mislabel=24), None),
}


def _micro(ref):
    return {o.obs_id: T.frac_to_int_micro(v) for o, v in zip(ref["obs"], ref["residuals"])}


def family_diff(a, b, root) -> dict:
    """Which graded families differ between two references."""
    sf, ec = T.read_frames(root)

    def roll(ref):
        out = {}
        for o, v, f in zip(ref["obs"], ref["residuals"], ref["flags"]):
            for key in (("d", o.region), ("e", o.epoch), ("f", T.rollup_key(o, sf, ec))):
                c = out.setdefault(key, [0, 0, Fraction(0)])
                c[0] += 1
                c[1] += 1 if f else 0
                c[2] += abs(v)
        return {k: (n, d, T.frac_to_int_micro(s)) for k, (n, d, s) in out.items()}

    from fractions import Fraction  # noqa: F401  (closure use)
    globals()["Fraction"] = Fraction
    d = {}
    d["model_test"] = any(T.frac_to_str(a[k], 10) != T.frac_to_str(b[k], 10)
                          for k in ("vtpv", "sigma0_sq")) or a["verdict"] != b["verdict"] \
        or a["dof"] != b["dof"]
    d["unknowns"] = any(T.frac_to_str(x, 10) != T.frac_to_str(y, 10)
                        for x, y in zip(list(a["x"]) + list(a["x_free"]),
                                        list(b["x"]) + list(b["x_free"])))
    d["residuals"] = _micro(a) != _micro(b)
    d["sets"] = (a["removed_ids"] != b["removed_ids"]
                 or [f for f in a["flags"]] != [f for f in b["flags"]]
                 or a["weights_final"] != b["weights_final"])
    d["rollups"] = roll(a) != roll(b)
    d["reports"] = (T.frac_to_str(a["sigma0_sq"], 10) != T.frac_to_str(b["sigma0_sq"], 10)
                    or a["trace"] != b["trace"] or a["verdict"] != b["verdict"]
                    or sum(a["flags"]) != sum(b["flags"]))
    return d


def owned(lever, a, b) -> bool:
    if lever == "A":
        ids = {k for k, v in a["shares"].items() if v} | {k for k, v in b["shares"].items() if v}
        ma, mb = _micro(a), _micro(b)
        return any(ma.get(i) != mb.get(i) for i in ids) or a["shares"] != b["shares"]
    if lever == "B":
        wa = {o.obs_id: w for o, w in zip(a["obs"], a["weights_final"]) if o.kind == "length"}
        wb = {o.obs_id: w for o, w in zip(b["obs"], b["weights_final"]) if o.kind == "length"}
        return wa != wb
    da = {}
    for ref, store in ((a, da), (b, {})):
        pass
    sa = sorted((o.region, T.frac_to_int_micro(v)) for o, v in zip(a["obs"], a["residuals"]))
    sb = sorted((o.region, T.frac_to_int_micro(v)) for o, v in zip(b["obs"], b["residuals"]))
    return sa != sb


def run_one(args):
    cfg, seed = args
    feats, lever = CONFIGS[cfg]
    work = Path(tempfile.mkdtemp(prefix=f"{cfg}-{seed}-", dir=SCRATCH))
    root = work / "data"
    out = work / "out"
    try:
        info = R.emit_r2(root, seed, **feats)
        ref = R.solve_r2(root, ALL_OK)
        rec = {"cfg": cfg, "seed": seed,
               "branches": sorted(set(info["branches"].values()))}
        if lever:
            modes = dict(ALL_OK)
            modes[lever] = "reflex"
            alt = R.solve_r2(root, modes)
            fd = family_diff(ref, alt, root)
            ow = owned(lever, ref, alt)
            rec["reflex_families"] = [f for f in FAMILIES if fd[f]]
            rec["reflex_owned"] = ow
            rec["reflex_points"] = 3 * sum(fd.values()) + (5 if ow else 0)
        p = subprocess.run([sys.executable, str(AGENT), str(root), str(out)],
                           capture_output=True, text=True, timeout=120)
        T._HIDDEN_CACHE["fz"] = {"root": root, "out": out, "code": p.returncode, "ref": ref}
        failed = []
        for f in FAMILIES:
            try:
                CHECKS[f]("fz")
            except AssertionError:
                failed.append(f)
            except Exception as exc:  # noqa: BLE001  artifact unreadable counts as fail
                failed.append(f + ":" + type(exc).__name__)
        rec["agent_failed"] = failed
        rec["agent_points"] = 3 * len(failed)
        return rec
    finally:
        T._HIDDEN_CACHE.pop("fz", None)
        shutil.rmtree(work, ignore_errors=True)


def main():
    n = int(sys.argv[1])
    dest = Path(sys.argv[2])
    cfgs = sys.argv[3].split(",") if len(sys.argv) > 3 else list(CONFIGS)
    jobs = [(c, 10_000_019 + 7919 * i) for c in cfgs for i in range(n)]
    with mp.Pool(9) as pool:
        recs = pool.map(run_one, jobs, chunksize=4)
    dest.write_text(json.dumps(recs, indent=0))
    for c in cfgs:
        rs = [r for r in recs if r["cfg"] == c]
        line = f"{c}: n={len(rs)}"
        ad = sum(1 for r in rs if r["agent_failed"])
        line += f" agent_differ={ad / len(rs):.2%} agent_pts_mean={sum(r['agent_points'] for r in rs) / len(rs):.1f}/18"
        if "reflex_points" in rs[0]:
            rd = sum(1 for r in rs if r["reflex_families"] or r["reflex_owned"])
            pts = sum(r["reflex_points"] for r in rs) / len(rs)
            line += (f" reflex_differ={rd / len(rs):.2%} reflex_pts_mean={pts:.1f}/23"
                     f" ({pts / P_TOTAL:.1%} of {P_TOTAL})")
        print(line)


if __name__ == "__main__":
    main()
