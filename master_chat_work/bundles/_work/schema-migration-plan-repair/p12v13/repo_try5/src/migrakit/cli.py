"""Command line: ``python -m migrakit run ...``."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_pipeline


def _resolve(value: str) -> Path:
    """Resolve a command-line path against the caller's working directory."""
    return Path(value).expanduser().resolve()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="migrakit", description="Migrate partner records to canonical schemas.")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="process a feed and write records.jsonl and run_summary.json")
    run.add_argument("--contracts", required=True, help="folder holding the seven contract files")
    run.add_argument("--feed", required=True, help="partner feed, one JSON object per line")
    run.add_argument("--corrections", required=True, help="correction log")
    run.add_argument("--manifest", required=True, help="replay manifest CSV")
    run.add_argument("--out", required=True, help="output folder")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    records, summary = run_pipeline(
        _resolve(args.contracts), _resolve(args.feed), _resolve(args.corrections), _resolve(args.manifest)
    )
    out = _resolve(args.out)
    out.mkdir(parents=True, exist_ok=True)
    lines = "".join(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n" for record in records)
    (out / "records.jsonl").write_text(lines, encoding="utf-8")
    (out / "run_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0
