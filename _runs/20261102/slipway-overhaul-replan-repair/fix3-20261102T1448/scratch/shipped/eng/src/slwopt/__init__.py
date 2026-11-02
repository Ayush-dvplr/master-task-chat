"""slwopt: the deterministic incremental replan engine.

The package reads one round of working papers, derives the state of the round
in seven layers, solves every precinct exactly against the lexicographic
objective, and then folds in the amendments the desk lodged, visiting only the
derived cells an amendment actually reaches.
"""
from pathlib import Path

from . import publish

__all__ = ["run", "publish"]
VERSION = "5.2.0"


def run(data, out):
    """Replan one round out of the paper directory and publish it."""
    return publish.publish(Path(data), Path(out))
