"""Digest every hidden book and its expected documents with one template; dump JSON. python3 -B v2_digest.py <template> <ci> <out.json>"""
import hashlib, json, sys, time
from pathlib import Path
from book_digests import digest, load
tt = load(sys.argv[1]); CI = Path(sys.argv[2])
dd = lambda docs: {d: hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest() for d, v in sorted(docs.items())}
table = {}
for name in ["fresh_1", "fresh_2", "fresh_3", "rescaled", "relocated", "missing", "rejections", "ties", "wide_1", "wide_2", "wide_3"]:
    book = tt._book(name)
    table[name] = {"book": digest(book), "docs": {} if name == "missing" else dd(tt._expected(name))}
    print(name, table[name]["book"][:16], flush=True)
table["shipped"] = {"book": digest(CI), "docs": dd(tt._expected_documents(CI))}
table["cases"] = {json.loads(l)["case"]: tt._case_outcome(json.loads(l)) for l in (CI / "regression_cases.jsonl").read_text().splitlines()}
Path(sys.argv[3]).write_text(json.dumps(table, indent=1, sort_keys=True))
print("ALL_DONE")
