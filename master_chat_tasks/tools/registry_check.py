#!/usr/bin/env python3
"""Report type drift in registry/tasks.json (read-only, R5-16).

  registry_check.py [--file PATH]

A field drifts when the same path (list items as []) holds values of more than one
kind across tasks: number, string, bool, list, object (null is ignored), e.g.
pipeline.traj_final 65.59 in one task and "51.45" in another. Prints each drifting
path with its kinds and up to 5 tasks per kind. Exit 0 = no drift,
1 = drift, 2 = unreadable file. The file is never written.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

DEFAULT_FILE = Path(__file__).resolve().parent.parent / "registry" / "tasks.json"


def kind(v: object) -> str | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        return "string"
    return "list" if isinstance(v, list) else "object"


def walk(v: object, path: str, slug: str, seen: dict[str, dict[str, list[tuple[str, object]]]]) -> None:
    k = kind(v)
    if k is None:
        return
    if path:
        seen[path][k].append((slug, v))
    if isinstance(v, dict):
        for key, sub in v.items():
            walk(sub, f"{path}.{key}" if path else key, slug, seen)
    elif isinstance(v, list):
        for sub in v:
            walk(sub, f"{path}[]", slug, seen)


def drift(tasks: list[dict]) -> dict[str, dict[str, list[tuple[str, object]]]]:
    seen: dict[str, dict[str, list[tuple[str, object]]]] = defaultdict(lambda: defaultdict(list))
    for t in tasks:
        walk(t, "", str(t.get("slug", "?")), seen)
    return {p: dict(ks) for p, ks in sorted(seen.items()) if len(ks) > 1}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", type=Path, default=Path(os.environ.get("REGISTRY_FILE") or DEFAULT_FILE))
    a = ap.parse_args(argv)
    try:
        data = json.loads(a.file.read_text())
    except (OSError, ValueError) as e:
        print(f"registry_check.py: cannot read {a.file}: {e}", file=sys.stderr)
        return 2
    tasks = data.get("tasks", []) if isinstance(data, dict) else data
    found = drift(tasks)
    print(f"{a.file}: {len(tasks)} tasks, {len(found)} field(s) with type drift")
    for path, kinds in found.items():
        counts = ", ".join(f"{k} x{len(v)}" for k, v in sorted(kinds.items(), key=lambda kv: -len(kv[1])))
        print(f"  {path}: {counts}")
        for k, vals in sorted(kinds.items(), key=lambda kv: len(kv[1])):
            for slug, v in vals[:5]:
                print(f"    {k}: {slug} = {json.dumps(v, ensure_ascii=False)[:80]}")
            if len(vals) > 5:
                print(f"    {k}: ... {len(vals) - 5} more")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
