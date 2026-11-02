"""Command line entry: python -m tariff DATA_DIR"""
import sys

from .report import build_invoices, render


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    print(render(build_invoices(args[0])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
