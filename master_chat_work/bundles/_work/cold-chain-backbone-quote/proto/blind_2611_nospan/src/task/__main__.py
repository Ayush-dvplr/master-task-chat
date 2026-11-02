"""python -m task --book DIR --out DIR"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .parser import MissingBookFile, load_book
from .report import build


def main(argv=None) -> int:
    options = argparse.ArgumentParser(prog="task")
    options.add_argument("--book", required=True, type=Path)
    options.add_argument("--out", required=True, type=Path)
    args = options.parse_args(argv)
    try:
        book = load_book(args.book)
    except MissingBookFile as exc:
        print(f"E_MISSING_FILE {exc.name}", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    for name, document in build(book).items():
        (args.out / name).write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
