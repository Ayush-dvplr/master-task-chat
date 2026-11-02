"""Authoring-time runner: call every check of the bundle's tests/test_output.py directly.

    python3 run_checks.py APP_ROOT [OUT_JSON] [--only name,name]

Uses a stand-in rewardkit module (STUB) so the checks import without the real
package; the score printed is the tests-channel share, positive total as the
denominator. The final oracle score is taken with the real rewardkit.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

WORK = Path(__file__).resolve().parent
BUNDLE = WORK.parent.parent / "tariff-engine-audit-repair"
STUB = Path(str(Path(__file__).resolve().parent / "rewardkit_stub"))


def main() -> None:
    app = Path(sys.argv[1]).resolve()
    out_json = Path(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
    only = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
    os.environ["APP_ROOT"] = str(app)
    sys.path.insert(0, str(STUB))
    test_file = Path(os.environ.get("TEST_OUTPUT_FILE", str(BUNDLE / "tests" / "test_output.py")))
    spec = importlib.util.spec_from_file_location("bundle_tests", test_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    weights = dict(sys.modules["rewardkit"].REGISTERED)
    results = {}
    earned = 0
    for name, weight in weights.items():
        if only and name not in only:
            continue
        started = time.time()
        value = bool(getattr(module, name)(app))
        results[name] = {"pass": value, "weight": weight, "sec": round(time.time() - started, 2)}
        earned += weight if value else 0
        print(f"{'PASS' if value else 'fail'} {weight:+d} {name} ({results[name]['sec']}s)", flush=True)
    positive = sum(w for w in weights.values() if w > 0)
    score = earned / positive
    print(f"SCORE {score:.4f} ({earned}/{positive})")
    if out_json:
        out_json.write_text(json.dumps({"score": score, "earned": earned, "positive": positive, "checks": results}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
