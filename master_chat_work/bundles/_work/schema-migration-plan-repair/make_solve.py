"""Render solution/solve.py: the reverse of make_shipped's patches, applied to a copy of /app/repo.

    python3 make_solve.py

Verifies that applying the rendered repairs to repo_shipped/ reproduces
repo_fixed/ byte for byte before writing.
"""

from __future__ import annotations

import filecmp
import shutil
import tempfile
from pathlib import Path

import make_shipped as ms

WORK = Path(__file__).resolve().parent
BUNDLE = WORK.parent.parent / "schema-migration-plan-repair"


def repairs() -> list[tuple[str, str, str]]:
    found = []
    for rel, old, new in ms.PATCHES:
        if old in ms.SPANS:
            fixed_text = (ms.FIXED / rel).read_text(encoding="utf-8")
            start_token, end_token = ms.SPANS[old]
            start = fixed_text.index(start_token)
            end = len(fixed_text) if end_token is None else fixed_text.index(end_token, start)
            shipped_fragment = new + "\n" if old == "ADMIT_FROM_HERE" else new
            found.append((rel, shipped_fragment, fixed_text[start:end]))
        else:
            found.append((rel, new, old))
    return found


def literal(text: str) -> str:
    if "'''" not in text and "\\" not in text and not text.endswith("'"):
        return "'''" + text + "'''"
    return repr(text)


def render(items: list[tuple[str, str, str]]) -> str:
    body = "".join(f"    (\n        {rel!r},\n        {literal(old)},\n        {literal(new)},\n    ),\n" for rel, old, new in items)
    template = (WORK / "solve_template.py").read_text(encoding="utf-8")
    return template.replace("REPAIRS: list[tuple[str, str, str]] = []", "REPAIRS: list[tuple[str, str, str]] = [\n" + body + "]")


def verify(items: list[tuple[str, str, str]]) -> None:
    scratch = Path(tempfile.mkdtemp(prefix="smpr-solve-verify-"))
    tree = scratch / "repo"
    shutil.copytree(ms.SHIPPED, tree)
    for rel, old, new in reversed(items):
        path = tree / rel
        text = path.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise SystemExit(f"repair target not unique in {rel}")
        path.write_text(text.replace(old, new), encoding="utf-8")
    (tree / "src/migrakit/__main__.py").write_text((ms.FIXED / "src/migrakit/__main__.py").read_text(encoding="utf-8"), encoding="utf-8")
    cmp = filecmp.dircmp(tree, ms.FIXED, ignore=["__pycache__"])
    def walk(c):
        bad = c.left_only + c.right_only + c.diff_files
        for sub in c.subdirs.values():
            bad += walk(sub)
        return bad
    problems = walk(cmp)
    shutil.rmtree(scratch)
    if problems:
        raise SystemExit(f"round trip differs: {problems}")


if __name__ == "__main__":
    items = repairs()
    verify(items)
    (BUNDLE / "solution" / "solve.py").write_text(render(items), encoding="utf-8")
    print(f"rendered {len(items)} repairs")
