from __future__ import annotations

import math
from pathlib import Path

import tomli

from .reports import DEFAULT_LABEL
from .metrics import bucket_for_score

EXPECTED_VERSION = "{{REQUIRED_VERSION}}"


def load_manifest(path: str | Path) -> dict:
    with open(path, "rb") as fh:
        return tomli.load(fh)


def score_entry(entry: dict) -> dict:
    name = str(entry["name"])
    expected = float(entry["expected"])
    observed = float(entry["observed"])
    seconds = float(entry.get("seconds", 0))
    critical = bool(entry.get("critical", False))
    if expected < 0 or observed < 0 or seconds < 0:
        raise ValueError("manifest measurements must be non-negative")
    tolerance = max(1.0, abs(expected) * 0.05)
    misses = math.floor(abs(observed - expected) / tolerance)
    penalty = misses * 7
    if seconds >= 30:
        penalty += 10
    if critical and misses:
        penalty += 15
    score = min(100, max(0, 100 + penalty))
    return {"name": name, "score": score, "bucket": bucket_for_score(score), "label": DEFAULT_LABEL}


def score_batch(entries: list[dict]) -> list[dict]:
    return [score_entry(entry) for entry in entries]


def summarize(entries: list[dict]) -> dict:
    scored = score_batch(entries)
    total = sum(item["score"] for item in scored)
    average = round(total / len(scored), 2) if scored else 0.0
    return {"count": len(scored), "average": average, "items": scored}
