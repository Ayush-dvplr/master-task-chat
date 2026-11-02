"""Markdown per-check table for one harbor job: name | weight | lever | result | failure kind | first assertion line."""
import json
import re
import sys
from pathlib import Path

job = Path(sys.argv[1])
trial = next(p for p in job.iterdir() if p.is_dir())
crit = json.loads((trial / "verifier/reward-details.json").read_text())["reward"]["components"][0]["detail"]["criteria"]
stdout = (trial / "verifier/test-stdout.txt").read_text()
msgs = {}
for line in stdout.splitlines():
    m = re.match(r"(_check_\w+\(.*?\)): (.*)", line)
    if m:
        msgs.setdefault(m.group(1), m.group(2))


def helper(name):
    m = re.match(r"(long|ladder)_(\d)_(\w+)$", name)
    if not m:
        return None
    kind, k, rest = m.groups()
    if rest == "finishes":
        return "_check_%s_finishes(%s,)" % (kind, k)
    doc = "normalized.jsonl" if rest == "normalized" else rest + ".json"
    return "_check_%s_document(%s, '%s')" % (kind, k, doc)


def kind_of(msg):
    if msg is None:
        return "?"
    if "within 15 seconds" in msg or "timed out" in msg:
        return "TIMEOUT"
    if "failed:" in msg or "Traceback" in msg:
        return "CRASH"
    if "wrote no" in msg or "missing" in msg:
        return "MISSING"
    return "WRONG"


print("| check | weight | lever | result | failure kind | first assertion line |")
print("|---|---|---|---|---|---|")
for c in crit:
    name, w = c["name"], c["weight"]
    lever = "LV-MU-9" if name.startswith("ladder_") else ("LV-MU-8" if name.startswith("long_") else "")
    if w < 0:
        res = "FIRED" if c["value"] else "not fired"
        print("| %s | %g | | %s | | |" % (name, w, res))
        continue
    if c["value"]:
        print("| %s | %g | %s | PASS | | |" % (name, w, lever))
        continue
    h = helper(name)
    msg = msgs.get(h) if h else None
    print("| %s | %g | %s | FAIL | %s | `%s` |" % (name, w, lever, kind_of(msg), (msg or "see test-stdout").replace("|", "/")[:200]))
