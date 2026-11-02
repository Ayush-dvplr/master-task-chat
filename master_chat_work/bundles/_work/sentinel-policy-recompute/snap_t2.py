"""Snapshot reference documents and corpus bytes of every existing corpus (t2 regression guard)."""
import hashlib, importlib.util, json, sys
tests = sys.argv[1]; out = sys.argv[2]
spec = importlib.util.spec_from_file_location("t", tests); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
names = sys.argv[3].split(",") if len(sys.argv) > 3 else list(m.VARIANTS)
snap = {}
for name in names:
    files, rows, stored = m.build_variant(name)
    docs = m.evaluate(files, rows, stored)[0]
    snap[name] = {"docs": json.loads(json.dumps(docs, sort_keys=True)),
                  "files": {k: hashlib.sha256(v).hexdigest() for k, v in sorted(files.items())},
                  "rows": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()}
json.dump(snap, open(out, "w"), indent=1, sort_keys=True)
print(len(snap), "corpora")
