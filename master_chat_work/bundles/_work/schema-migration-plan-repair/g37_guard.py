from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

WORK = Path(__file__).resolve().parent
BUNDLE = WORK.parent.parent / "schema-migration-plan-repair"
BEFORE = WORK / "before_g37"


def source(path: Path) -> str:
    text = path.read_text()
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.AnnAssign)
                and isinstance(n.target, ast.Name) and n.target.id == "_SHIPPED_DATA")
    lines = text.splitlines(keepends=True)
    return "".join(lines[:node.lineno - 1]) + "_SHIPPED_DATA: dict[str, str] = {}\n" + "".join(lines[node.end_lineno:])


def checks(text: str) -> dict[str, str]:
    lines = text.splitlines(keepends=True)
    names = set(re.findall(r"^criteria\.(\w+)\(weight=-?\d+\)$", text, re.M))
    found = {}
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            start = min([node.lineno, *(d.lineno for d in node.decorator_list)])
            found[node.name] = hashlib.sha256("".join(lines[start - 1:node.end_lineno]).encode()).hexdigest()
    assert names == found.keys()
    return found


def main() -> None:
    frozen = source(BEFORE / "tests/test_output.py")
    baseline = WORK / "g37_frozen.src.py"
    if baseline.exists():
        assert baseline.read_text() == frozen
    else:
        baseline.write_text(frozen)
    current = (WORK / "test_output.src.py").read_text()
    assert source(BUNDLE / "tests/test_output.py") == current, "PAUSED: generated tests differ from source"
    old, new = checks(frozen), checks(current)
    assert len(old) == 81
    assert all(new[name] == digest for name, digest in old.items()), "PAUSED: old check changed"
    old_regs = re.findall(r"^criteria\.\w+\(weight=-?\d+\)$", frozen, re.M)
    new_regs = re.findall(r"^criteria\.\w+\(weight=-?\d+\)$", current, re.M)
    assert all(row in new_regs for row in old_regs)
    immutable = [p for p in BEFORE.rglob("*") if p.is_file()
                 and (p.relative_to(BEFORE).parts[0] == "environment" or p.name == "instruction.md")]
    assert all((BUNDLE / p.relative_to(BEFORE)).read_bytes() == p.read_bytes() for p in immutable)
    result = {"old_checks": len(old), "current_checks": len(new), "immutable_files": len(immutable),
              "check_digest": hashlib.sha256(json.dumps(old, sort_keys=True).encode()).hexdigest(),
              "old_check_changes": 0, "immutable_changes": 0}
    (WORK / "g37_guard.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
