"""Command line entry: python -m tariff DATA_DIR"""
import sys
from pathlib import Path

from .report import INPUTS, build_invoices, render


def main(argv=None):
    """Print the invoice document of a data directory, or report a missing input."""
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0])
    for name in INPUTS:
        if not (root / name).is_file():
            print(f"missing input: {name}", file=sys.stderr)
            return 2
    print(render(build_invoices(args[0])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
