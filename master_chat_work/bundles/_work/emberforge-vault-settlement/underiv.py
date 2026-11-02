"""Underivability check: does a lever's reflex reading still reproduce the published slice?

For each solver file: run its own recover-style search over the 840 draws against the
published slice records (controls + example report + reference bundle), and report how
many draws survive and whether the true draw is among them. A reflex reading that keeps
exactly the true draw is HIDDEN-ONLY on the labelled visible data; one that loses it is
DERIVABLE (the agent sees zero matches and fixes the rule).

Also reports, per published record, whether the right and reflex readings differ on the
slice under the true draw, and whether they differ on the (unlabelled) season proper.

Usage: python3 underiv.py DATA_DIR solver_id=path ...
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def load(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def published(data: Path) -> dict:
    return {"controls": json.loads((data / "calibration_controls.json").read_text()),
            "example": json.loads((data / "example_workshop_report.json").read_text())}


def matches(got: dict, pub: dict) -> bool:
    flow = got.get("workshop_%s.json" % pub["example"]["workshop_id"], {}).get("reagent_flow", [])
    back = {r["reagent_id"]: r["returned_units"] for r in flow if r["returned_units"]}
    return got["summary.json"] == pub["controls"] and back == pub["example"]["returned_units"]


def main() -> None:
    data = Path(sys.argv[1])
    pub = published(data)
    out = {}
    for arg in sys.argv[2:]:
        sid, path = arg.split("=", 1)
        mod = load(path, sid)
        true = mod.Draw("RS-C", "half-even", "GFS", "opening-plus-acquired")
        sl = mod.Corpus(data, "calibration_")
        survivors = []
        for cand in mod.register_draws():
            try:
                got = mod.settle(sl, cand)
            except (ArithmeticError, ValueError, KeyError):
                continue
            if matches(got, pub):
                survivors.append("/".join(cand))
        try:
            at_true = mod.settle(sl, true)
            slice_diff = [] if matches(at_true, pub) else ["published slice"]
        except (ArithmeticError, ValueError, KeyError) as exc:
            slice_diff = ["raised %s" % type(exc).__name__]
        try:
            season = mod.settle(mod.Corpus(data, ""), true)
            season_json = {k: json.dumps(v, sort_keys=True) for k, v in season.items()}
        except (ArithmeticError, ValueError, KeyError) as exc:
            season_json = {"raised": type(exc).__name__}
        out[sid] = {"survivors": survivors, "slice_records_differing_at_true_draw": slice_diff,
                    "season_json": season_json}
    oracle = out.get("S5", {}).get("season_json", {})
    for sid, row in out.items():
        sj = row.pop("season_json")
        row["season_records_differing_from_oracle"] = sorted(
            k for k in set(sj) | set(oracle) if sj.get(k) != oracle.get(k))
        verdict = "HIDDEN-ONLY" if row["survivors"] == ["RS-C/half-even/GFS/opening-plus-acquired"] else "DERIVABLE"
        row["verdict_on_slice"] = verdict
        print(sid, verdict, "survivors=%d" % len(row["survivors"]), "slice_diff=%s" % row["slice_records_differing_at_true_draw"],
              "season_diff=%s" % row["season_records_differing_from_oracle"])
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
