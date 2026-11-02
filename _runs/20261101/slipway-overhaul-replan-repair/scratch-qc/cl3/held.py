import sys, pathlib, re
sys.path.insert(0, sys.argv[1])
import importlib.util
spec = importlib.util.spec_from_file_location("t", sys.argv[2] + "/test_output.py")
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
for name in [n for n in dir(t) if n.startswith("HELD_")]:
    seed, legacy = getattr(t, name)
    root = t._held_corpus(seed, legacy)
    xw = (root/"identifier_crosswalk.tsv").read_text().splitlines()[1:]
    legs = {l.split("\t")[0] for l in xw}
    hits = {}
    for f in ["exclusive_slot_groups.csv","conditional_charge_rules.jsonl","amendment_journal.jsonl","amendment_supplement.ndjson"]:
        txt = (root/f).read_text()
        hits[f[:12]] = sum(1 for l in legs if l in txt)
    print(name, legacy, hits)
print(xw[:3])
