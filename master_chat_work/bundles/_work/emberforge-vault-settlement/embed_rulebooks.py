"""Re-embed every .md document of environment/data into RULEBOOK_TEXTS of a test_output.py.

Usage: python3 embed_rulebooks.py <data_dir> <test_output.py>
Every corpus the grader builds carries these documents byte for byte.
"""
from __future__ import annotations

import sys
from pathlib import Path


def literal(text: str) -> str:
    if '"""' in text or "\\" in text:
        raise SystemExit("document holds a triple quote or a backslash; embed by hand")
    return '"""\\\n' + text + '"""'


def main() -> None:
    data, target = Path(sys.argv[1]), Path(sys.argv[2])
    docs = sorted(p for p in data.glob("*.md"))
    body = "RULEBOOK_TEXTS = {\n" + "".join(
        '    "%s": %s,\n' % (p.name, literal(p.read_text(encoding="utf-8"))) for p in docs
    ) + "}\n"
    src = target.read_text(encoding="utf-8")
    start = src.index("RULEBOOK_TEXTS = {\n")
    end = src.index("\n}\n", start) + 3
    target.write_text(src[:start] + body + src[end:], encoding="utf-8")
    print("embedded", len(docs), "documents")


if __name__ == "__main__":
    main()
