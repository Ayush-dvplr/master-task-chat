"""Seeded capture log for the format-recovery archetype.

The spec documents are templates. This writes `<FORMAT_TAG>-capture-log.jsonl`,
20,000 field captures (about 9% damaged), by running the verifier's own
generator (`capture_log()` in tests/test_output.py), so the shipped file and
the grader's ground truth cannot drift apart. The format report and error
analysis artifacts summarise this log.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path


def _verifier_namespace(tests_py: Path) -> dict:
    stub = types.ModuleType("rewardkit")
    setattr(stub, "criterion", lambda **_: (lambda fn: fn))

    class _Registry:
        def __getattr__(self, _name):
            return lambda **_: None

    setattr(stub, "criteria", _Registry())
    module = types.ModuleType("format_recovery_verifier")
    saved = sys.modules.get("rewardkit")
    sys.modules["rewardkit"] = stub
    sys.modules[module.__name__] = module
    try:
        exec(compile(tests_py.read_text(encoding="utf-8"), str(tests_py), "exec"), module.__dict__)
    finally:
        sys.modules.pop(module.__name__, None)
        if saved is None:
            sys.modules.pop("rewardkit", None)
        else:
            sys.modules["rewardkit"] = saved
    return module.__dict__


def generate(data_dir: Path, seed: int, subs: dict[str, str]) -> None:
    tests_py = data_dir.parent.parent / "tests" / "test_output.py"
    rows = _verifier_namespace(tests_py)["capture_log"]()
    lines = [json.dumps({"capture_id": row["capture_id"], "hex": row["hex"]}, separators=(",", ":")) for row in rows]
    name = f"{subs['{{FORMAT_TAG}}']}-capture-log.jsonl"
    (data_dir / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
