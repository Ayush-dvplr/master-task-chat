"""Append the new repairs of oracle_repairs.py to solution/solve.py in its own
_block style. Usage: python3 -B render_repairs.py <solve.py>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from oracle_repairs import REPAIRS  # noqa: E402

CLOSE = '     _block(\'    source = params["header"]["register_in_force"]\')),\n)\n'


def render(text, indent):
    if text.endswith("\n"):
        lines = text[:-1].split("\n")
        parts = [repr(line) for line in lines]
        head = "_block("
        pad = " " * (indent + len(head))
        return head + (",\n" + pad).join(parts) + ")"
    lines = text.split("\n")
    parts = [repr(line + "\n") for line in lines[:-1]] + [repr(lines[-1])]
    pad = " " * indent
    return ("\n" + pad).join(parts)


def main():
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    if text.count(CLOSE) != 1:
        raise SystemExit("close anchor matches " + str(text.count(CLOSE)))
    rows = []
    for code, relative, old, new in REPAIRS:
        rows.append("    (" + repr(code) + ", " + repr(relative) + ",\n"
                    + "     " + render(old, 5) + ",\n"
                    + "     " + render(new, 5) + "),\n")
    text = text.replace(CLOSE, CLOSE[:-2] + "".join(rows) + ")\n")
    path.write_text(text, encoding="utf-8")
    print("rendered", len(rows))


if __name__ == "__main__":
    main()
