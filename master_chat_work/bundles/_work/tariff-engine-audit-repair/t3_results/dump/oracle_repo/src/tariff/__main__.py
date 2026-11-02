"""Command line entry: python -m tariff [--statements] DATA_DIR"""
import json
import sys
from pathlib import Path

from .report import INPUTS, build_invoices, build_statements, render


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    statements = bool(args) and args[0] == "--statements"
    root = Path(args[1] if statements else args[0])
    for name in INPUTS:
        if not (root / name).is_file():
            print(f"missing input: {name}", file=sys.stderr)
            return 2
    if statements:
        print(json.dumps(build_statements(root), indent=2, sort_keys=True))
    else:
        print(render(build_invoices(root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
