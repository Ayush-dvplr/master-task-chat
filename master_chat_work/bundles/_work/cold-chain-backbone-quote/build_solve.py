"""Write solution/solve.py from the repaired package in WORK/fixed_repo."""
from pathlib import Path

WORK = Path(__file__).resolve().parent
BUNDLE = WORK.parent.parent / "cold-chain-backbone-quote"
FILES = ["pyproject.toml", "src/task/__init__.py", "src/task/parser.py", "src/task/core.py", "src/task/report.py"]

blocks = []
for rel in FILES:
    text = (WORK / "fixed_repo" / rel).read_text(encoding="utf-8")
    assert "'''" not in text
    blocks.append(f'    "{rel}": r\'\'\'{text}\'\'\',\n')

body = (WORK / "solve_body.py").read_text(encoding="utf-8")
out = body.replace("REPAIRED_FILES_HERE\n", "".join(blocks))
(BUNDLE / "solution" / "solve.py").write_text(out, encoding="utf-8")
print("wrote", len(out.splitlines()), "lines")
