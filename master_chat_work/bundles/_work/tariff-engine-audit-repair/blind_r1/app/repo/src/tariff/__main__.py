"""Command line entry: python -m tariff DATA_DIR"""
import sys
from pathlib import Path

from .report import INPUT_FILES, build_invoices, render


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("usage: python -m tariff DATA_DIR", file=sys.stderr)
        return 2
    root = Path(args[0])
    for name in INPUT_FILES:
        if not (root / name).is_file():
            print(f"missing input: {name}", file=sys.stderr)
            return 2
    sys.stdout.write(render(build_invoices(root)) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
