"""Command line entry point."""
import sys
from pathlib import Path

from . import run


def parse(argv):
    data = None
    out = None
    rest = list(argv)
    while rest:
        head = rest.pop(0)
        if head == "--data" and rest:
            data = rest.pop(0)
        elif head == "--out" and rest:
            out = rest.pop(0)
        else:
            raise SystemExit("usage: python3 -m slwopt --data DIR --out DIR")
    if data is None or out is None:
        raise SystemExit("usage: python3 -m slwopt --data DIR --out DIR")
    return Path(data), Path(out)


def main(argv=None):
    data, out = parse(sys.argv[1:] if argv is None else argv)
    if not data.is_dir():
        raise SystemExit("the paper directory does not exist: " + str(data))
    out.mkdir(parents=True, exist_ok=True)
    run(data, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
