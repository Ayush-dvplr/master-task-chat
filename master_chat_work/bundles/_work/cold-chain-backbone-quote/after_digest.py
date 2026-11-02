"""Digest every hidden book, its expected documents, the shipped book docs and case outcomes with one template; compare to a before log."""
import hashlib, json, sys, time
from pathlib import Path
from book_digests import digest, load
tt = load(sys.argv[1]); CI = Path(sys.argv[2])
dd = lambda docs: {d: hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()[:16] for d, v in sorted(docs.items())}
table = {}
for name in ["fresh_1", "fresh_2", "fresh_3", "rescaled", "relocated", "missing", "rejections", "ties", "wide_1", "wide_2", "wide_3"]:
    t = time.time(); book = tt._book(name); tb = time.time() - t
    t = time.time(); exp = {} if name == "missing" else tt._expected(name); te = time.time() - t
    table[name] = {"book": digest(book)[:16], "docs": dd(exp)}
    print(name, table[name], "build %.1fs expected %.1fs" % (tb, te), flush=True)
t = time.time()
table["shipped"] = {"book": digest(CI)[:16], "docs": dd(tt._expected_documents(CI))}
print("shipped", table["shipped"], "%.1fs" % (time.time() - t), flush=True)
t = time.time()
table["cases"] = {json.loads(l)["case"]: tt._case_outcome(json.loads(l)) for l in (CI / "regression_cases.jsonl").read_text().splitlines()}
print("cases %.1fs" % (time.time() - t))
before = json.loads(Path(sys.argv[3]).read_text()[Path(sys.argv[3]).read_text().index("\n{") + 1:].split("\nALL_DONE")[0].rsplit("\nEXIT", 1)[0])["table"]
for k in table:
    b = before[k]
    same = (b == table[k]) if k == "cases" else (b["book"] == table[k]["book"] and b["docs"] == table[k]["docs"])
    print("COMPARE", k, "identical" if same else "DIFFERENT")
