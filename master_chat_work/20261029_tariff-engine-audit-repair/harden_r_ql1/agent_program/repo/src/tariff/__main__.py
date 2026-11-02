"""Command line entry: python -m tariff [--statements] DATA_DIR"""
import sys

from .report import build_invoices, build_statements, missing_input, render


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    statements = "--statements" in args
    data_dir = [arg for arg in args if arg != "--statements"][0]
    missing = missing_input(data_dir)
    if missing is not None:
        print(f"missing input: {missing}", file=sys.stderr)
        return 2
    document = build_statements(data_dir) if statements else build_invoices(data_dir)
    print(render(document))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
