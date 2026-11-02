#!/usr/bin/env python3
"""Append one decision row to decisions.jsonl (the one writer, R5-23).

  decide.py --by BY --what TEXT [--slug SLUG] [--words VERBATIM] [--file PATH]

Row: {"ist": "YYYY-MM-DD HH:MM", "by": ..., "slug": ..., "what": ..., "words": ...}
(ist is set here in IST; slug/words only when given). BY is one of: ayush, master,
master (auto), worker <7-hex sha>. Empty --what or a bad --by -> exit 2, nothing written.
File: --file, else $DECIDE_FILE, else master_chat_tasks/decisions.jsonl. Old rows
(who/decision/verbatim) are never rewritten.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
DEFAULT_FILE = Path(__file__).resolve().parent.parent / "decisions.jsonl"
BY_RE = re.compile(r"ayush|master|master \(auto\)|worker [0-9a-f]{7}")


def row(by: str, what: str, slug: str = "", words: str = "", at: datetime | None = None) -> dict[str, str]:
    """A validated row; ValueError names the bad field."""
    by, what = by.strip(), what.strip()
    if not BY_RE.fullmatch(by):
        raise ValueError(f"--by {by!r}: want ayush, master, 'master (auto)' or 'worker <7-hex sha>'")
    if not what:
        raise ValueError("--what is empty")
    out = {"ist": (at or datetime.now(IST)).astimezone(IST).strftime("%Y-%m-%d %H:%M"), "by": by}
    if slug.strip():
        out["slug"] = slug.strip()
    out["what"] = what
    if words:
        out["words"] = words
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--by", required=True, help="ayush | master | 'master (auto)' | 'worker <sha>'")
    ap.add_argument("--what", required=True, help="the decision, one line")
    ap.add_argument("--slug", default="", help="task slug (optional)")
    ap.add_argument("--words", default="", help="the words it rests on, verbatim (optional)")
    ap.add_argument("--file", type=Path, help="decisions file (default: $DECIDE_FILE or decisions.jsonl)")
    a = ap.parse_args(argv)
    try:
        r = row(a.by, a.what, a.slug, a.words)
    except ValueError as e:
        print(f"decide.py: {e}", file=sys.stderr)
        return 2
    path = a.file or Path(os.environ.get("DECIDE_FILE") or DEFAULT_FILE)
    line = json.dumps(r, ensure_ascii=False)
    lead = ""
    if path.is_file() and path.stat().st_size:
        with path.open("rb") as f:
            f.seek(-1, os.SEEK_END)
            lead = "" if f.read(1) == b"\n" else "\n"
    with path.open("a") as f:
        f.write(lead + line + "\n")
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
