#!/usr/bin/env python3
"""Points lost per check, per judge criterion and per hidden input from a harness job (plan v1 U16).

  loss.py SLUG_OR_JOB_DIR [--all]     (--all lists every check, not only the ones that lost points)

Reads jobs/<slug>/trajectory/*/Run */verifier/reward-details.json. For a positive item
lost = weight * (1 - value); for a negative item (weight < 0) penalty = weight * value (fired).
Groups lost test points by the hidden-input token in the check name (h1, hidden_h2, seed3, case_x ...),
so one bug billed across many tests shows as one line. Replaces hand P14 attribution.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[2] / "Terminal_2.0_Harbor_Harness"
TOKEN = re.compile(r"(hidden_[a-z0-9]+|h\d+|seed\d+|case_[a-z0-9]+|s\d+|q\d+)", re.I)


def report(path, show_all):
    comps = json.loads(path.read_text())["reward"]["components"]
    print(f"\n== {path.parent.parent.name}  (reward {json.loads(path.read_text())['reward']['score']})")
    for c in comps:
        items = c["detail"].get("criteria", [])
        pos = [i for i in items if i["weight"] > 0]
        neg = [i for i in items if i["weight"] < 0]
        tot = sum(i["weight"] for i in pos)
        got = sum(i["weight"] * i["value"] for i in pos)
        pen = sum(i["weight"] * i["value"] for i in neg)
        pct = 100 * (got + pen) / tot if tot else 0
        print(f"-- {c['name']}: {got + pen:g}/{tot:g} = {pct:.2f}%  (positive lost {tot - got:g}, negatives fired {pen:g})")
        lost = sorted([(i["weight"] * (1 - i["value"]), i) for i in pos if show_all or i["value"] < 1], key=lambda x: -x[0])
        for pts, i in lost:
            why = i.get("reasoning") or i.get("description", "")
            print(f"   -{pts:g}  {i.get('id', '')} {i['name']}: {why[:160]}")
        for i in neg:
            if i["value"]:
                print(f"   {i['weight'] * i['value']:g} FIRED {i.get('id', '')} {i['name']}: {(i.get('reasoning') or i.get('description', ''))[:160]}")
        if c["name"] != "judge" and lost:
            by = defaultdict(float)
            for pts, i in lost:
                m = TOKEN.search(i["name"])
                by[m.group(1).lower() if m else "(no input token)"] += pts
            print("   by hidden input: " + ", ".join(f"{k} -{v:g}" for k, v in sorted(by.items(), key=lambda x: -x[1])))


def main(a):
    if not a:
        sys.exit(__doc__)
    jd = Path(a[0]) if Path(a[0]).is_dir() else HARNESS / "jobs" / a[0]
    files = sorted(jd.glob("trajectory/*/Run */verifier/reward-details.json")) or sorted(
        jd.glob("trajectories/*/run_*/verifier/reward-details.json"))  # delivery layout
    if not files:
        sys.exit(f"no reward-details.json under {jd}")
    print(f"job {jd}  runs {len(files)}")
    for f in files:
        report(f, "--all" in a)


if __name__ == "__main__":
    main(sys.argv[1:])
