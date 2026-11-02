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


def read_feed(path: str | Path) -> list[FeedLine]:
    """Return one FeedLine per physical line; a bad line carries its problem."""
    found: list[FeedLine] = []
    for number, raw in enumerate(split_lines(Path(path).read_text(encoding="utf-8")), start=1):
        try:
            document = json.loads(raw)
        except ValueError:
            document = None
            problem = "line is not JSON"
        else:
            problem = _shape_problem(document)
        named = document.get("batch") if isinstance(document, dict) else None
        found.append(FeedLine(number, None if problem else document, problem, named if isinstance(named, str) else None))
    return found
