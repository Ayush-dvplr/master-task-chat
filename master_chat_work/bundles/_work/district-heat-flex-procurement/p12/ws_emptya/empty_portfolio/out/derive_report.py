import json
import runpy
import sys
from pathlib import Path

sys.dont_write_bytecode = True
out = Path(sys.argv[2])
sys.argv = ["solve.py", sys.argv[1], sys.argv[2]]
try:
    runpy.run_path("/b/solution/solve.py", run_name="__main__")
except SystemExit:
    pass
for f in sorted(out.glob("region_*.json")):
    doc = json.loads(f.read_text())
    for row in doc.get("events", []):
        row["selected_offer_ids"] = []
    f.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
