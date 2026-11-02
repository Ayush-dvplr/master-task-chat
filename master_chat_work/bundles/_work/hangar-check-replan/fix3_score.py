import hashlib
import json
import runpy
import sys
from pathlib import Path

runpy.run_path("/work/h1_a1/score_all.py", run_name="__main__")
T = sys.modules["test_output"]
before = json.loads(Path("/results/expected_before.json").read_text())
after = {}
docs = {}
for name in ["shipped", *T.HIDDEN, *T.FORMS, "m1", "m2"]:
    case = T._CASES[name]
    blob = json.dumps(case["want"], sort_keys=True, separators=(",", ":")).encode()
    after[name] = hashlib.sha256(blob).hexdigest()
    docs[name] = {}
    for src in sorted(Path("/source_docs").iterdir()):
        dst = case["data"] / "docs" / src.name
        assert dst.read_bytes() == src.read_bytes(), (name, src.name)
        docs[name][src.name] = hashlib.sha256(dst.read_bytes()).hexdigest()
assert before == after, {n: (before[n], after[n]) for n in before if before[n] != after[n]}
Path("/results/expected_after.json").write_text(json.dumps(after, indent=2) + "\n")
Path("/results/docs_by_corpus.json").write_text(json.dumps(docs, indent=2) + "\n")
print("EXPECTED_IDENTICAL", len(after), "DOCS_IDENTICAL", len(docs) * 6, flush=True)
