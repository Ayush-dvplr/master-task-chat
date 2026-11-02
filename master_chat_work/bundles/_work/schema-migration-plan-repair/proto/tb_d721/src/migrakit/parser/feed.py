"""Partner feed reader (one JSON object per line)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

REQUIRED_TEXT_KEYS = ("batch", "partner", "key", "schema")


@dataclass(frozen=True)
class FeedLine:
    line: int
    record: dict | None
    problem: str
    batch: str | None = None


def _shape_problem(document: object) -> str:
    if not isinstance(document, dict):
        return "line is not a JSON object"
    for key in REQUIRED_TEXT_KEYS:
        if not isinstance(document.get(key), str) or not document[key]:
            return f"missing or empty {key}"
    if not isinstance(document.get("payload"), dict):
        return "payload is not an object"
    return ""


def split_lines(text: str) -> list[str]:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _reject_constant(name: str) -> object:
    raise ValueError(f"{name} is not JSON")


def read_feed(path: str | Path) -> list[FeedLine]:
    """Return one FeedLine per physical line; a bad line carries its problem."""
    found: list[FeedLine] = []
    raw_lines = Path(path).read_bytes().split(b"\n")
    if raw_lines and raw_lines[-1] == b"":
        raw_lines.pop()
    for number, raw in enumerate(raw_lines, start=1):
        try:
            document = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
        except (UnicodeDecodeError, ValueError, RecursionError):
            found.append(FeedLine(number, None, "line is not JSON"))
            continue
        problem = _shape_problem(document)
        named = document.get("batch") if isinstance(document, dict) else None
        found.append(FeedLine(number, None if problem else document, problem, named if isinstance(named, str) else None))
    return found
