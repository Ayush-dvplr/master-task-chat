"""Render solution/TRUTH.md from TRUTH.src.md with current sha256 values.

    python3 make_truth.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

WORK = Path(__file__).resolve().parent
BUNDLE = WORK.parent.parent / "schema-migration-plan-repair"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    text = (WORK / "TRUTH.src.md").read_text(encoding="utf-8")
    data = BUNDLE / "environment" / "data"
    table = "\n".join(f"- `{p.name}`: `{sha(p)}`" for p in sorted(data.iterdir()) if p.is_file())
    solve_py = BUNDLE / "solution" / "solve.py"
    measured = json.loads((WORK / "n_measure.json").read_text(encoding="utf-8"))
    values = {
        "@@DATA_SHA@@": table,
        "@@SOLVE_SH@@": sha(BUNDLE / "solution" / "solve.sh"),
        "@@SOLVE_PY@@": sha(solve_py),
        "@@SOLVE_LINES@@": str(len(solve_py.read_text(encoding="utf-8").splitlines())),
        "@@SLOWEST@@": f"{measured['slowest_sec']:.2f}",
    }
    for token, value in values.items():
        text = text.replace(token, value)
    if "@@" in text:
        raise SystemExit("unresolved token")
    (BUNDLE / "solution" / "TRUTH.md").write_text(text, encoding="utf-8")
    print("TRUTH.md written", len(text), "chars")


if __name__ == "__main__":
    main()
