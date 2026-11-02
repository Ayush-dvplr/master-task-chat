"""Choose each reseeded season's draw so that every observable graded on it moves with the draw.

For every season, walk the uniquely pinned draws (spread order, none reused, consumed
reference only for lv3*) and keep the first under which the grader settles the season
and every graded observable differs from the settlement of the same season under the
visible draw. A program that hardcodes the visible draw then fails every value check.

Usage: python3 select_draws.py <to.py dir> <unique_draws.json> OUT_JSON
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import to  # noqa: E402

OBSERVED = {
    "lv": ["_obs_findings", "_obs_workshop_figures", "_obs_vault", "_obs_reconciliation", "_obs_guilds"],
    "ld": ["_obs_allocation"],
    "cl_priority": ["_obs_allocation"],
    "cl_cap": ["_obs_workshop_figures"],
    "cl_partition": ["_obs_guilds"],
    "cl_temporal": ["_obs_vault"],
    "cl_identity": ["_obs_smith_rows"],
    "cl_quiet": ["_obs_findings"],
}


def observed(name):
    return OBSERVED.get(name) or OBSERVED[name[:2]]


def main():
    unique = [d for d in json.load(open(sys.argv[2])) if d != "RS-C/half-even/GFS/opening-plus-acquired"]
    spread = [unique[(i * 37) % len(unique)] for i in range(len(unique))]
    out = {}
    used = set()
    for name, (seed, _params, mutate) in to.SEASONS.items():
        kind = "consumed" if name.startswith("lv3") else "plain"
        tried = 0
        for draw in spread:
            if draw in used or draw.endswith("/consumed") != (kind == "consumed"):
                continue
            tried += 1
            params = to.Params(*draw.split("/"))
            with tempfile.TemporaryDirectory() as td:
                data = Path(td) / "data"
                try:
                    to._build_corpus_dir(data, params=params, mutate=mutate, main_seed=seed)
                    want = to.settle(to.load(data, ""), params)
                except (ValueError, AssertionError):
                    continue
                try:
                    visible = to.settle(to.load(data, ""), to.TRUE)
                except (ValueError, AssertionError):
                    visible = None
            same = [] if visible is None else [
                o for o in observed(name) if to._same(getattr(to, o)(want), getattr(to, o)(visible))]
            if same:
                continue
            out[name] = {"seed": seed, "draw": draw, "tried": tried,
                         "allocated": want["allocation.json"]["allocated_total"],
                         "counts": want["data_quality.json"]["counts"]}
            used.add(draw)
            print(name, draw, "after", tried, flush=True)
            break
        else:
            print(name, "NO DRAW FOUND", flush=True)
    Path(sys.argv[3]).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
