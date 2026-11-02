#!/bin/bash
# Oracle dispatcher for 7c787cba-5282-55f9-99f4-896d5cc0e007. It installs the repaired
# engine and the command line entry beside it, then compiles the shipped
# extract with them.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/pathcal.py

cat > /app/out/ttc.py <<'ENTRY'
#!/usr/bin/env python3
"""ttc, the command line entry of the path calendar compiler."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pathcal

USAGE = "usage: ttc.py compile <DATA_DIR> <OUT_DIR>\n"


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] != "compile":
        sys.stderr.write(USAGE)
        return 2
    pathcal.compile_extract(argv[2], argv[3])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
ENTRY

python3 /app/out/ttc.py compile /app/wtt /app/out
