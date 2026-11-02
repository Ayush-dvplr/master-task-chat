"""Rescore score_all.py JSON lines with the weights now in BUNDLE tests/test_output.py.

usage: python3 rescore.py TEST_OUTPUT_PY LOG.jsonl...
Prints prog | positive / total | pct | lever (h7..h15) kept | negatives fired | max run seconds.
"""
import json
import re
import sys
from pathlib import Path

src = Path(sys.argv[1]).read_text(encoding="utf-8")
W = {m.group(1): int(m.group(2)) for m in re.finditer(r"criteria\.(\w+)\(weight=(-?\d+)\)", src)}
LEVER = {n for n in W if re.match(r"h(7|8|9|1[0-5])_", n)}
total = sum(w for w in W.values() if w > 0)
lever_total = sum(W[n] for n in LEVER)
print("| program | tests pos | pct | lever kept | negatives | max s |")
print("|---|---|---|---|---|---|")
for log in sys.argv[2:]:
    for line in Path(log).read_text(encoding="utf-8").splitlines():
        if not line.startswith("{"):
            continue
        r = json.loads(line)
        v = r["verdict"]
        pos = sum(W[n] for n, x in v.items() if W.get(n, 0) > 0 and x == "E")
        neg = sum(W[n] for n, x in v.items() if W.get(n, 0) < 0 and x == "E")  # a negative criterion holds when it fires
        kept = sum(W[n] for n in LEVER if v.get(n) == "E")
        secs = [s for s in (r.get("secs") or {}).values() if s is not None]
        pct = 100.0 * max(0, pos + neg) / total
        print("| %s | %d/%d | %.1f | %d/%d (%.0f%%) | %s | %s |" % (
            r["prog"], pos, total, pct, kept, lever_total, 100.0 * kept / lever_total,
            neg or 0, max(secs) if secs else "-"))
