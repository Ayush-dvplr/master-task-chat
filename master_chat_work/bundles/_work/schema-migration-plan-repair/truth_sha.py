"""Rewrite every sha256 in solution/TRUTH.md from the current bundle files (gate v3.6; run last).

    python3 -B truth_sha.py
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

BUNDLE = Path(__file__).resolve().parent.parent.parent / "schema-migration-plan-repair"
TRUTH = BUNDLE / "solution" / "TRUTH.md"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    text = TRUTH.read_text(encoding="utf-8")
    text = re.sub(r"(fix_patch_sha256: )[0-9a-f]{64}", lambda m: m.group(1) + sha(BUNDLE / "solution" / "solve.sh"), text)
    text = re.sub(r"(solve_py_sha256: )[0-9a-f]{64}", lambda m: m.group(1) + sha(BUNDLE / "solution" / "solve.py"), text)
    text = re.sub(r"(- `)([\w./\-]+)(`: `)[0-9a-f]{64}", lambda m: m.group(1) + m.group(2) + m.group(3) + sha(BUNDLE / m.group(2)), text)
    TRUTH.write_text(text, encoding="utf-8")
    print("TRUTH sha256 rewritten")


if __name__ == "__main__":
    main()
