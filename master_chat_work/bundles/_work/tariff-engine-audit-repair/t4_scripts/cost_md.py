"""Append the wave-1 measured cost table (from t4_results/cost_docker.json) to COST_TABLE.md and KILL_TEST.md."""
import json
from pathlib import Path

WORK = Path(__file__).resolve().parents[1]
cost = json.loads((WORK / "t4_results/cost_docker.json").read_text())
lever = [n for n in cost["oracle"]["checks"] if "_ledger_" in n]
lever_pts = sum(cost["oracle"]["checks"][n]["weight"] for n in lever)


def row(name):
    c = cost[name]
    failed = sum(1 for v in c["checks"].values() if v["weight"] > 0 and not v["pass"])
    kept = sum(c["checks"][n]["weight"] for n in lever if c["checks"][n]["pass"])
    return f"{c['score']:.4f}", failed, kept


LABELS = [
    ("oracle", "oracle (split reference)"),
    ("solver:reference", "oracle build, kill-test reference solver"),
    ("blind_r3", "blind round-3 program (397/397 last round)"),
    ("blind_r3+solver:reference", "blind round-3 program with the reference optimum (float check)"),
    ("solver:blind_r3", "blind r3 `_redeem` (cents bitset, suffix masks)"),
    ("solver:bitset", "gcd-reduced cents bitset with id-order rebuild"),
    ("solver:bitset_sum_only", "cents bitset, optimum sum only, greedy ids"),
    ("solver:table", "dict table of sums -> first ids"),
    ("solver:pareto", "Pareto list, dominance pruned"),
    ("solver:mitm", "halves, sorted, raw"),
    ("solver:mitm_dedupe", "halves deduped by sum, id split"),
    ("solver:mitm_dedupe_sorted", "halves deduped by sum, amount split"),
    ("solver:branch_bound", "branch and bound, fractional bound"),
    ("solver:greedy", "largest voucher first"),
    ("solver:naive", "naive combinations"),
    ("Q1_off", "Q1 wrong alone"), ("Q2_off", "Q2 wrong alone"), ("Q3_off", "Q3 wrong alone"),
    ("Q4_off", "Q4 wrong alone"), ("Q5_off", "Q5 wrong alone"), ("U1_off", "U1 wrong alone"),
    ("D1_off", "D1 wrong alone"), ("D2_off", "D2 wrong alone"),
    ("first_write", "first write (Q1-Q5, U1, D1, D2 wrong; exact statements)"),
    ("first_write+solver:bitset", "first write plus cents bitset"),
    ("first_write+solver:greedy", "first write plus greedy"),
]
lines = [
    "",
    "## Wave 1 (d11904c, 27 Oct 2026): measured in Docker on the built bundle, tests share of 488 positive points",
    "",
    "python:3.12-slim, 2 cpus, 4 GB, uid 1000; whole program scored by the real checks (t4_scripts/cost_t4.py,",
    f"cost_docker.sh; t4_results/cost_docker.json). Lever = the 21 ledger checks, {lever_pts} points.",
    "",
    "| program | tests | positive checks failed | lever points kept of 91 |",
    "|---|---|---|---|",
]
for name, label in LABELS:
    if name in cost:
        s, f, k = row(name)
        lines.append(f"| {label} | {s} | {f} | {k} |")
singles = ["Q1_off", "Q2_off", "Q3_off", "Q4_off", "Q5_off", "U1_off", "D1_off", "D2_off", "blind_r3"]
best = max((n for n in singles if n in cost), key=lambda n: cost[n]["earned"])
fired = sorted({k for c in cost.values() for k, v in c["checks"].items() if v["pass"] and v["weight"] < 0})
lines += [
    "",
    f"All-but-one (best single wrong): {best} {cost[best]['score']:.4f} (<= 0.92). Lever alone: blind r3 loses "
    f"{1 - cost['blind_r3']['score']:.1%} (10-30%). Negatives fired: {fired or 'none'}.",
    "",
]
text = "\n".join(lines)
assert "\u2014" not in text and "\u2013" not in text
for f in ("COST_TABLE.md", "KILL_TEST.md"):
    p = WORK / f
    old = p.read_text()
    if "## Wave 1 (d11904c, 27 Oct 2026): measured in Docker on the built bundle" not in old:
        p.write_text(old.rstrip("\n") + "\n" + text)
print(text)
