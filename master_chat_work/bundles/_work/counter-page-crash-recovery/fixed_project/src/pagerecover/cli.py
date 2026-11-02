"""Command line entry point: python -m pagerecover recover --data DIR --out DIR."""
import argparse
import os
import sys

from . import loader, recovery, reports


def main(argv=None):
    parser = argparse.ArgumentParser(prog="pagerecover")
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("recover", help="recover every crash image of a book")
    rec.add_argument("--data", required=True)
    rec.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    try:
        book = loader.load_book(args.data)
    except loader.MissingInput as exc:
        print("pagerecover: missing input %s in %s" % (exc.args[0], args.data), file=sys.stderr)
        return 2
    results = {}
    for image_id, image in book["images"].items():
        results[image_id] = recovery.recover_image(image)
    os.makedirs(args.out, exist_ok=True)
    reports.write_documents(args.out, book, results)
    return 0
