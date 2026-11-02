"""Build solution/solve.sh with the self-check stage embedded as a heredoc."""
from pathlib import Path
W = Path(__file__).resolve().parents[1]
B = W.parent.parent / "depot-charge-plan"
check = (W / "solution_src" / "selfcheck.py").read_text()
assert "SELFCHECK" not in check
text = """#!/bin/bash
# Oracle for depot-charge-plan: install the program, run it on the shipped data, then self-check it.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/derive_report.py
python3 /app/out/derive_report.py --data /app/data --out /app/out

# Self-check stage: each check prints `check <id> ok` and one witness line.
check_dir="$(mktemp -d)"
cat > "$check_dir/selfcheck.py" <<'SELFCHECK'
""" + check + """SELFCHECK
python3 "$check_dir/selfcheck.py" /app/out/derive_report.py /app/data /app/out
rm -rf "$check_dir"
"""
(B / "solution" / "solve.sh").write_text(text)
print("solve.sh", text.count("\n"), "lines")
