"""Per-check table from a harbor job's reward-details.json, plus memory peak for the matching verifier container."""
import json
import re
import sys
from pathlib import Path

job, prefix = Path(sys.argv[1]), sys.argv[2]
trial = next(p for p in job.iterdir() if p.is_dir())
details = json.loads((trial / "verifier/reward-details.json").read_text())
stdout = (trial / "verifier/test-stdout.txt").read_text()
result = json.loads((trial / "result.json").read_text())
crit = details["reward"]["components"][0]["detail"]["criteria"]

# first assertion line per check helper: _holds prints "<helper>(args): <exc>"
fails = {}
for line in stdout.splitlines():
    m = re.match(r"(_check_\w+)(\(.*?\)): (.*)", line)
    if m:
        fails.setdefault(m.group(1) + m.group(2), m.group(3))

pos_total = sum(c["weight"] for c in crit if c["weight"] > 0)
earned = sum(c["weight"] for c in crit if c["weight"] > 0 and c["value"])
neg = sum(-c["weight"] for c in crit if c["weight"] < 0 and c["value"])  # negative fires when its criterion is True
rows = []
for c in crit:
    ok = bool(c["value"])
    rows.append((c["name"], c["weight"], "PASS" if ok else "FAIL"))
v = result["verifier"]
print("criteria", len(crit), "pos_total", pos_total, "earned", earned, "neg_fired", neg,
      "tests_pct %.2f" % (100 * (earned - neg) / pos_total), "reward", result["verifier_result"])
print("verifier", v["started_at"], v["finished_at"], "exception", result.get("exception_info"))
for r in rows:
    if r[2] == "FAIL" or r[1] < 0:
        print("ROW", *r)
print("--- assertion lines")
for k, msg in fails.items():
    print("FAILMSG", k, "::", msg[:300])
peaks = []
for line in Path("/tmp/opencode-logs/mu-79409fb-blind/mem.log").read_text().splitlines():
    parts = line.split("|")
    if parts[1].startswith(prefix + "__") and "__verifier__" in parts[1]:
        m = re.search(r"peak=(\d+)", line)
        if m:
            peaks.append(int(m.group(1)))
        peaks_usage = parts[2]
print("peak_gib %.3f samples %d" % (max(peaks) / 2**30 if peaks else -1, len(peaks)))
