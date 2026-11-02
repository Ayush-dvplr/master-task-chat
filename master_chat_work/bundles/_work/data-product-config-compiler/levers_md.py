"""Write LEVERS.md: one row per check with the levers whose wrong reading fails it (from cost_table.json)."""
from __future__ import annotations

import json
import re

from score import BUNDLE, WORK

FAMILIES = {
    "status_team": "status, owner, tier, team per product",
    "settings_int": "integer settings per product",
    "settings_other": "boolean, enum, list, string settings per product",
    "config_quota": "config.json quota per product",
    "dev_deploy": "profile_dev.json deploy keys",
    "dev_quota": "profile_dev.json quota per product",
    "prod_deploy": "profile_prod.json deploy keys",
    "prod_quota": "profile_prod.json quota per product",
    "rejected_overrides": "validation_report.json",
    "summary": "summary.json",
}


def main() -> None:
    text = (BUNDLE / "tests" / "test_output.py").read_text()
    checks = re.findall(r"^criteria\.(\w+)\(weight=(-?\d+)\)", text, re.M)
    rows = json.loads((WORK / "cost_table.json").read_text())
    levers = ["NL-1", "NL-3", "NL-4"]
    failed = {lever: set(rows["alone " + lever]["failed"]) for lever in levers}
    background = {lever: set(rows["background " + lever]["failed"]) for lever in ("LV-CC-1", "LV-CC-2", "LV-CC-4")}
    totals = {lever: 0 for lever in levers}
    positive = sum(int(w) for _, w in checks if int(w) > 0)
    lines = ["# LEVERS: data-product-config-compiler", "",
             "Lever ids per check come from the measured cost table: a check carries a lever when that "
             "lever's wrong reading alone fails it (`WORK/cost_table.py`).", "",
             "Counted levers (Harden round 1): NL-1 assignment on D (latest active_from), NL-3 quota_cap re-share, "
             "NL-4 text-layer type reading. The build levers LV-CC-1, LV-CC-2, LV-CC-4 stay as background rules "
             "(their giveaway wording removed) and are listed in the last column; they are not counted.", "",
             "| check | weight | levers | graded property | background |", "|---|---|---|---|---|"]
    for name, weight in checks:
        weight = int(weight)
        hit = [lever for lever in levers if name in failed[lever]]
        for lever in hit:
            totals[lever] += weight
        stem = name[:-5] if name.endswith("_hard") else name
        what = FAMILIES.get(stem, name.replace("_", " "))
        if name.endswith("_hard"):
            what += " (hidden release)"
        elif stem in FAMILIES:
            what += " (shipped release)"
        back = [lever for lever in background if name in background[lever]]
        lines.append("| %s | %d | %s | %s | %s |" % (name, weight, ", ".join(hit) or "none (graded work)", what,
                                                   ", ".join(back) or "-"))
    lines += ["", "| lever | positive weight carried | share of P = %d |" % positive, "|---|---|---|"]
    for lever in levers:
        lines.append("| %s | %d | %.1f%% |" % (lever, totals[lever], 100 * totals[lever] / positive))
    lines += ["", "Checks: %d. Positive weight: %d. Negative: %s." % (
        len(checks), positive, ", ".join("%s %s" % (n, w) for n, w in checks if int(w) < 0)), "",
        "## Lessons for the master",
        "- Deriving lever columns from measured failures keeps LEVERS.md and COST_TABLE.md in step | no change: script reads cost_table.json."]
    (WORK / "LEVERS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[-8:]))


if __name__ == "__main__":
    main()
