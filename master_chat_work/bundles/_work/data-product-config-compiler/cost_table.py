"""G10 cost table: each lever's wrong reading alone, one fact wrong, and all levers but one wrong."""
from __future__ import annotations

import json
import sys

from score import BACKGROUND, LEVERS, SCRATCH, WORK, score

RUBRIC = 0.90


def overall(row: dict) -> float:
    return round(100 * (0.5 * row["got"] / row["pos"] + 0.5 * RUBRIC), 1)


def main() -> None:
    rows = {"oracle": score("oracle", [])}
    names = list(LEVERS)
    for name in names:
        full, one = LEVERS[name]
        rows["alone " + name] = score("alone-" + name, full)
        rows["one-fact " + name] = score("one-" + name, one)
        others = [edit for other in names if other != name for edit in LEVERS[other][0]]
        rows["only-right " + name] = score("onlyright-" + name, others)
    for name, (full, _one) in BACKGROUND.items():
        rows["background " + name] = score("bg-" + name, full)
    rows["all wrong"] = score("allwrong", [edit for name in names for edit in LEVERS[name][0]])
    for label, row in rows.items():
        lost = 100 - row["pct"]
        print("%-22s tests %5.1f%%  lost %5.1f%%  overall@90 %5.1f  failed %s" % (
            label, row["pct"], lost, overall(row), ",".join(row["failed"])))
    (SCRATCH / "cost_table.json").write_text(json.dumps(rows, indent=2))
    (WORK / "cost_table.json").write_text(json.dumps(rows, indent=2))


if __name__ == "__main__":
    sys.exit(main())
