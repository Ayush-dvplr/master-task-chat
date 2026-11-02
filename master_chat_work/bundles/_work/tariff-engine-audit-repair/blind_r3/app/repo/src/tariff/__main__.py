"""Command line entry: python -m tariff [--statements] DATA_DIR"""
import json
import sys
from pathlib import Path

from .report import REQUIRED, build_invoices, build_statements, render


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    statements = False
    if args and args[0] == "--statements":
        statements = True
        args = args[1:]
    if len(args) != 1:
        sys.stderr.write("usage: python -m tariff [--statements] DATA_DIR\n")
        return 2
    root = Path(args[0])
    for name in REQUIRED:
        if not (root / name).is_file():
            sys.stderr.write(f"missing input: {name}\n")
            return 2
    if statements:
        sys.stdout.write(json.dumps(build_statements(root)) + "\n")
    else:
        sys.stdout.write(render(build_invoices(root)) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
