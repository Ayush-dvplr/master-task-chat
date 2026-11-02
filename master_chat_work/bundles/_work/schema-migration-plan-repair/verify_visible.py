"""Round 1: run repo_fixed, repo_shipped and single-defect variants on the visible
inputs and report where each one differs from repo_fixed.

    python3 verify_visible.py <environment dir> <scratch dir>
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import make_shipped as ms

WORK = Path(__file__).resolve().parent
GROUPS = {
    "F1-F4 planner": [0, 1], "F5 from_payload": [2], "F6 decoy null": [3, 17],
    "F6 fill": [4], "F7 parser merge": [5], "F7b tokens_for or": [19],
    "F8 executor": [6, 7], "F9 classify": [8], "F10 admit": [9], "F11 order": [10],
    "F12 identity": [11, 12], "F13 feed": [13], "F14 summary": [14, 15],
    "F16 tokens trimmed": [20], "F17 receipt shipped": [21],
}
DRIVER = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
from migrakit import run_pipeline
ci = sys.argv[2]
records, summary = run_pipeline(ci, ci + "/partner_batches.jsonl",
                                ci + "/correction_log.txt", ci + "/replay_manifest.csv")
json.dump({"records": records, "summary": summary}, open(sys.argv[3], "w"), sort_keys=True)
'''


def tree(dest: Path, indices: list[int] | None) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(ms.FIXED, dest, ignore=shutil.ignore_patterns("__pycache__"))
    for index, (rel, old, new) in enumerate(ms.PATCHES):
        if indices is not None and index not in indices:
            continue
        path = dest / rel
        text = path.read_text(encoding="utf-8")
        text = ms._replace_span(text, old, new) if old in ms.SPANS else text.replace(old, new)
        path.write_text(text, encoding="utf-8")
    return dest


def run(src_tree: Path, ci: Path, out: Path) -> tuple[dict | None, float, str]:
    start = time.time()
    proc = subprocess.run([sys.executable, "-c", DRIVER, str(src_tree / "src"), str(ci), str(out)],
                          capture_output=True, text=True, timeout=1800)
    took = time.time() - start
    if proc.returncode:
        return None, took, proc.stderr.strip().splitlines()[-1]
    return json.loads(out.read_text()), took, ""


def compare(base: dict, other: dict) -> dict:
    fields = {}
    lines = 0
    for a, b in zip(base["records"], other["records"]):
        diff = [k for k in a if a[k] != b.get(k)]
        if diff:
            lines += 1
            for k in diff:
                fields[k] = fields.get(k, 0) + 1
    summary = sorted(k for k in base["summary"] if base["summary"][k] != other["summary"].get(k))
    return {"records_differing": lines, "fields": fields, "summary_keys": summary}


def main() -> None:
    env, scratch = Path(sys.argv[1]), Path(sys.argv[2])
    ci = env / "ci"
    scratch.mkdir(parents=True, exist_ok=True)
    base, took, err = run(tree(scratch / "fixed", []), ci, scratch / "fixed.json")
    report = {"fixed_seconds": round(took, 2)}
    s = base["summary"]
    report["figures"] = {
        "migrated": s["by_status"].get("migrated", 0),
        "rejected": s["by_status"].get("rejected", 0),
        "invalid_corrections": len(s["invalid_corrections"]),
        "completed_steps": sum(r["completed_steps"] for r in base["records"]),
    }
    report["summary"] = {k: s[k] for k in ("records", "attempted", "by_status", "by_code")}
    variants = {"shipped": None, "shipped minus decoy and F5": [i for i in range(20) if i not in (2, 3, 17)]}
    variants.update(GROUPS)
    variants["all but decoy"] = [i for i in range(20) if i not in (3, 17, 18)]
    for name, indices in variants.items():
        if name == "shipped":
            src = ms.SHIPPED
        elif name == "all but decoy":
            continue
        else:
            src = tree(scratch / "variant", indices)
        result, took, err = run(src, ci, scratch / "variant.json")
        report[name] = {"seconds": round(took, 2), "error": err} if result is None else (
            compare(base, result) | {"seconds": round(took, 2)})
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
