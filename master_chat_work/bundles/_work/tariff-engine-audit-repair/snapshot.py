"""Dump reference documents and corpus text hashes for every corpus: python3 snapshot.py OUT_JSON [TEST_FILE]"""
import hashlib, importlib.util, json, os, sys
from pathlib import Path
WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(WORK / "rewardkit_stub"))
test_file = Path(sys.argv[2]) if len(sys.argv) > 2 else WORK.parent.parent / "tariff-engine-audit-repair" / "tests" / "test_output.py"
spec = importlib.util.spec_from_file_location("bt", test_file); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
out = {}
for corpus in ("shipped", "fresh", "rescaled", "relocated", "rotated", "api", "recoded", "renamed"):
    doc = m._expected(corpus)
    texts = m._shipped_texts() if corpus == "shipped" else m._corpus_texts(corpus)
    out[corpus] = {"doc": doc, "texts": {k: hashlib.sha256(v.encode()).hexdigest() for k, v in sorted(texts.items())}}
Path(sys.argv[1]).write_text(json.dumps(out, sort_keys=True, default=str), encoding="utf-8")
print("snapshot", {k: len(v["doc"]["invoices"]) for k, v in out.items()})
