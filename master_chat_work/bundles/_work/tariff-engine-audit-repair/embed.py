"""Render tests/test_output.py from test_output.src.py with environment/ci and environment/repo embedded,
then rewrite tests/reward.toml from the registered weights and judge.toml.

    python3 embed.py
"""

from __future__ import annotations

import base64
import re
import tomllib
import zlib
from pathlib import Path

WORK = Path(__file__).resolve().parent
BUNDLE = WORK.parent.parent / "tariff-engine-audit-repair"
MARKER = "_SHIPPED_DATA: dict[str, str] = {}"


BANNED = re.compile(r"XXX|TODO|FIXME|PLACEHOLDER")


def literal_lines(blob: str, width: int = 96) -> str:
    """The blob as adjacent string literals, split so no literal holds a banned marker word."""
    cuts = set(range(width, len(blob), width))
    for match in BANNED.finditer(blob):
        cuts.add(match.start() + 1)
    bounds = [0, *sorted(cuts), len(blob)]
    parts = [blob[a:b] for a, b in zip(bounds, bounds[1:]) if b > a]
    return "\n".join(f"        {part!r}" for part in parts)


def main() -> None:
    env = BUNDLE / "environment"
    blobs = {}
    for folder in ("ci", "repo"):
        for path in sorted((env / folder).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                rel = f"{folder}/{path.relative_to(env / folder).as_posix()}"
                blobs[rel] = base64.b64encode(zlib.compress(path.read_bytes(), 9)).decode("ascii")
    body = "{\n" + "".join(f"    {name!r}: (\n{literal_lines(blob)}\n    ),\n" for name, blob in blobs.items()) + "}"
    src = (WORK / "test_output.src.py").read_text(encoding="utf-8")
    if src.count(MARKER) != 1:
        raise SystemExit("marker missing")
    (BUNDLE / "tests" / "test_output.py").write_text(src.replace(MARKER, "_SHIPPED_DATA: dict[str, str] = " + body), encoding="utf-8")
    weights = [int(w) for w in re.findall(r"^criteria\.\w+\(weight=(-?\d+)\)$", src, re.M)]
    judge = tomllib.loads((BUNDLE / "tests" / "judge.toml").read_text(encoding="utf-8"))
    judge_pos = sum(c["weight"] for c in judge["criterion"] if c["weight"] > 0)
    test_pos = sum(w for w in weights if w > 0)
    reward = (
        "[[reward]]\n"
        'name = "reward"\n'
        'aggregation = "weighted-sum"\n'
        f"weights = {{ test_output = {0.5 / test_pos!r}, judge = {0.5 / judge_pos!r} }}\n\n"
        "[scoring.test_output]\n"
        'aggregation = "weighted-sum"\n'
    )
    (BUNDLE / "tests" / "reward.toml").write_text(reward, encoding="utf-8")
    print(f"embedded {len(blobs)} files; test positive {test_pos}, negative {-sum(w for w in weights if w < 0)}, judge positive {judge_pos}")


if __name__ == "__main__":
    main()
