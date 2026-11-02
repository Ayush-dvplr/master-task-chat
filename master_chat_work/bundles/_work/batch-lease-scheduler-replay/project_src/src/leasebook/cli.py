"""Command line entry: leasebook DATA_DIR OUT_DIR."""
import json
import os
import sys

from .book import BookError, load_book
from .replay import SetReplay
from .report import build_documents


def replay_book(book):
    """Replay every set of a loaded book; returns set id -> SetReplay."""
    return {
        set_id: SetReplay(spec, book.lease, book.delay, book.pools).run()
        for set_id, spec in book.sets.items()
    }


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print("usage: leasebook DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data_dir, out_dir = args
    try:
        book = load_book(data_dir)
    except BookError as exc:
        print(exc.message())
        return 2
    documents = build_documents(replay_book(book))
    os.makedirs(out_dir, exist_ok=True)
    for name, document in documents.items():
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=1, sort_keys=True)
            handle.write("\n")
    return 0
