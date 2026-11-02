#!/usr/bin/env python3
"""ttc, the command line entry of the path calendar compiler.

The entry owns the argument handling and nothing else. Every stage lives in the
engine module beside it, which this file imports by putting its own directory
at the front of the import path, so the pair runs from whatever directory it is
installed in.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Keep the pair self contained: importing the engine must not leave a bytecode
# cache beside the two files, which would be a stray file in a directory the
# compile writes its documents into.
sys.dont_write_bytecode = True
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
