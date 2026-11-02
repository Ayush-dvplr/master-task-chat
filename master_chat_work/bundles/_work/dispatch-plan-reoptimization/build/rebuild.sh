#!/bin/sh
# Author-time rebuild: manifest counts for edited contract files, shipped gold,
# hidden sets, tests/test_output.py. Usage: sh rebuild.sh <bundle> <scratch>
set -e
B="$1"; S="$2"; H="$(cd "$(dirname "$0")" && pwd)"
D="$B/environment/data"
python3 - "$H/oracle.py" "$D" <<'EOF'
import importlib.util, sqlite3, sys
from pathlib import Path
s = importlib.util.spec_from_file_location("o", sys.argv[1]); o = importlib.util.module_from_spec(s); s.loader.exec_module(o)
D = Path(sys.argv[2]); con = sqlite3.connect(D / "xref_manifest.db")
for n, f in [("handbook_ops_v9.md", "md"), ("runbook_params.yaml", "yaml")]:
    con.execute("update sources set record_count=? where name=?", (o.physical_rows(D / n, f), n))
con.commit(); con.close()
EOF
rm -rf "$S/gold" "$S/hidden"; mkdir -p "$S/gold"
python3 "$H/oracle.py" "$D" "$S/gold"
PYTHONDONTWRITEBYTECODE=1 python3 "$H/mkhidden.py" "$D" "$S/hidden" > "$S/cases.log"
for h in H1 H2 H3 H4; do mkdir -p "$S/hidden/out_$h"; python3 "$H/oracle.py" "$S/hidden/$h" "$S/hidden/out_$h"; done
cp "$S/hidden/cases.json" "$H/cases.json"
python3 "$H/mktests.py" "$D" "$S/hidden" "$S/gold" "$B/tests/test_output.py"
