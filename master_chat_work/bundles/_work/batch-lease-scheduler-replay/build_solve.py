"""Embed project_fixed sources into solve_template.py -> BUNDLE/solution/solve.py."""
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent
FIXED = WORK / "project_fixed"
RELS = ["pyproject.toml"] + sorted(
    p.relative_to(FIXED).as_posix() for p in (FIXED / "src" / "leasebook").glob("*.py"))


def main(dest):
    parts = ["SOURCES = {"]
    for rel in RELS:
        text = (FIXED / rel).read_text(encoding="utf-8")
        assert "'''" not in text and not text.endswith("\\")
        parts.append("    %r: r'''%s'''," % (rel, text))
    parts.append("}")
    template = (WORK / "solve_template.py").read_text(encoding="utf-8")
    marker = "SOURCES = {}  # SOURCES-BLOCK"
    assert template.count(marker) == 1
    Path(dest).write_text(template.replace(marker, "\n".join(parts)), encoding="utf-8")
    print("wrote", dest, len(RELS), "sources")


if __name__ == "__main__":
    main(sys.argv[1])
