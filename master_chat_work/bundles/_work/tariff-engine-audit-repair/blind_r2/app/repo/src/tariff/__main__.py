"""Command line entry: python -m tariff DATA_DIR"""
import sys

from .report import MissingInputError, build_invoices, render


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        sys.stderr.write("usage: python -m tariff DATA_DIR\n")
        return 2
    try:
        text = render(build_invoices(args[0]))
    except MissingInputError as error:
        sys.stderr.write(f"missing input: {error.name}\n")
        return 2
    sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
