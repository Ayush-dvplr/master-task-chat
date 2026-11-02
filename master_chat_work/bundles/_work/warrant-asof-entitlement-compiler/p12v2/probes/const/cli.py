"""Probe: a tool that ignores --data and writes the same documents for every corpus."""
import json, sys
from pathlib import Path

DOCS = {
    "resolve-config": {"policy": "fixed"},
    "compile": {"u0001|grp-fixed": "member"},
    "audit": {k: [] for k in ("rejects", "unresolved", "held_grants", "unattested", "sod", "self_check")},
    "summarize": {"profiles": {}, "eligibility": {}, "grants": {}, "audit_counts": {}, "inputs": []},
}
argv = sys.argv[1:]
out = Path(argv[argv.index("--out") + 1])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(DOCS[argv[0]], indent=2, sort_keys=True) + "\n")
