"""Write BUNDLE/solution/solve.py: solve_body.py with the repaired files embedded."""
import filecmp
from pathlib import Path

WORK = Path(__file__).resolve().parent
BUNDLE = WORK.parent.parent / "counter-page-crash-recovery"
names = []
for path in sorted((WORK / "fixed_project").rglob("*")):
    if path.is_file() and "__pycache__" not in path.parts:
        rel = path.relative_to(WORK / "fixed_project").as_posix()
        shipped = WORK / "project" / rel
        if not shipped.exists() or not filecmp.cmp(path, shipped, shallow=False):
            names.append(rel)
lines = ["REPAIRED_FILES: dict[str, str] = {"]
for rel in names:
    text = (WORK / "fixed_project" / rel).read_text()
    if "\\" in text or "'''" in text:
        lines.append(f"    {rel!r}: {text!r},")
    else:
        lines.append(f"    {rel!r}: '''" + text + "''',")
lines.append("}")
body = (WORK / "solve_body.py").read_text()
assert body.count("REPAIRED_FILES_LINE") == 1
(BUNDLE / "solution" / "solve.py").write_text(body.replace("REPAIRED_FILES_LINE", "\n".join(lines)))
print("embedded", names)
