#!/usr/bin/env python3
"""Write the program as one self-contained file: python3 tools/amalgamate.py OUT_FILE

The modules of src/helios_close are concatenated in dependency order with their relative imports removed.
"""
import re
import sys
from pathlib import Path

ORDER = ["domain", "formats", "records", "cascade", "rules", "ledger", "cli"]


def main():
    if len(sys.argv) != 2:
        print("usage: amalgamate.py OUT_FILE", file=sys.stderr)
        return 2
    root = Path(__file__).resolve().parents[1] / "src" / "helios_close"
    parts = ["#!/usr/bin/env python3", '"""Helios Q3 close program (amalgamated from src/helios_close)."""', "from __future__ import annotations", ""]
    for name in ORDER:
        text = (root / f"{name}.py").read_text(encoding="utf-8")
        lines = [ln for ln in text.splitlines() if not re.match(r"^from \.\w* import ", ln) and ln != "from __future__ import annotations"]
        if lines and lines[0].startswith('"""'):
            lines = lines[1:]
        parts.append(f"# ---- {name}")
        parts.extend(lines)
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
