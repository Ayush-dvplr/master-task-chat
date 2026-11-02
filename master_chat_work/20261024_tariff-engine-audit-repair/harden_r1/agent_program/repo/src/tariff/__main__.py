"""Command line entry: python -m tariff DATA_DIR"""
import sys

from .report import build_invoices, missing_input, render


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    data_dir = args[0]
    name = missing_input(data_dir)
    if name is not None:
        print(f"missing input: {name}", file=sys.stderr)
        return 2
    print(render(build_invoices(data_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
