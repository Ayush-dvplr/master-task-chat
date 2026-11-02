"""unique_fit.py <corpus_dir>...: per corpus, which settlement readings fit (AL-27 unique-fit check).

Implements the two candidate tests straight from alae_rules.md:3-7 and
discounting_rules.md:3-5 (independent of solve.py) and prints one JSON line per corpus.
"""
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path


def half_up(x: Decimal) -> int:
    return int(x.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def alae_fits(d: Path) -> dict:
    obs = [(int(m.group(1)), int(m.group(2)), m.group(3)) for m in re.finditer(
        r"CLM-\d+\s+gross=\d+\s+alae=(\d+)\s+settled=(\d+)\s+layer=(\S+)",
        (d / "claim_adjustment_log.log").read_text())]
    obs = [(settled, alae, layer) for alae, settled, layer in obs]
    fracs = []
    for places in range(1, 5):
        step = Decimal(1).scaleb(-places)
        for k in range(1, 10 ** places):
            f = step * k
            if all(abs(alae - half_up(f * settled)) <= 1 for settled, alae, _ in obs):
                fracs.append(str(f.normalize()))
        if fracs:
            break
    excess = all((alae == 0) if layer == "retention" else (alae > 0) for _, alae, layer in obs)
    return {"lines": len(obs), "pro_rata": bool(fracs), "fraction": fracs, "excess_only": excess}


def curve_fits(d: Path) -> dict:
    marks = {}
    for ln in (d / "curve_marks.csv").read_text().splitlines()[1:]:
        if ln.strip():
            t, y = ln.split(",")[:2]
            marks[int(t)] = float(y)
    obs = [(int(m.group(1)), float(m.group(2)), float(m.group(3))) for m in re.finditer(
        r"tenor=(\d+)y\s+observed=(\S+)\s+pv_factor=(\S+)",
        (d / "treasury_curve_observations.log").read_text())]
    flat = all(abs(pv - (1 + marks[10] / 100) ** -t) <= 0.005 for t, _, pv in obs)
    dur = all(abs(pv - (1 + o / 100) ** -t) <= 0.005 for t, o, pv in obs)
    worst_flat = max(abs(pv - (1 + marks[10] / 100) ** -t) for t, _, pv in obs)
    worst_dur = max(abs(pv - (1 + o / 100) ** -t) for t, o, pv in obs)
    return {"lines": len(obs), "flat_10y": flat, "duration_matched": dur,
            "max_dev_flat": round(worst_flat, 6), "max_dev_duration": round(worst_dur, 6)}


for arg in sys.argv[1:]:
    p = Path(arg)
    a, c = alae_fits(p), curve_fits(p)
    alae_win = [k for k in ("pro_rata", "excess_only") if a[k]]
    curve_win = [k for k in ("flat_10y", "duration_matched") if c[k]]
    print(json.dumps({"corpus": arg.rstrip("/").split("/")[-1], "alae": a, "curve": c,
                      "alae_unique": alae_win[0] if len(alae_win) == 1 else None,
                      "curve_unique": curve_win[0] if len(curve_win) == 1 else None}))
