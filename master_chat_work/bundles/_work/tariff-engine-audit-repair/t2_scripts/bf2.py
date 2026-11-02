import sys, json, importlib.util, collections
W="/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/tariff-engine-audit-repair"
sys.path.insert(0, W+"/rewardkit_stub")
spec = importlib.util.spec_from_file_location("t", "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/tariff-engine-audit-repair/tests/test_output.py")
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
FLAGS = {"U1": ["U1"], "U1first": ["U1first"], "U1nofit": ["U1nofit"], "D1": ["D1"], "D1zero": ["D1zero"], "D2": ["D2"], "D2row": ["D2row"], "D2file": ["D2file"], "D2any": ["D2any"]}
def changed(a, b):
    out = set(); x = collections.defaultdict(list); y = collections.defaultdict(list)
    for i in a["invoices"]: x[i["account"]].append(i)
    for i in b["invoices"]: y[i["account"]].append(i)
    for k in set(x) | set(y):
        if json.dumps(x[k], sort_keys=True) != json.dumps(y[k], sort_keys=True): out.add(k)
    ea = {(e["read_id"], e["reason"]) for e in a["exceptions"]}; eb = {(e["read_id"], e["reason"]) for e in b["exceptions"]}
    rid = {e["read_id"]: e["account"] for e in a["exceptions"] + b["exceptions"]}
    for r, _ in ea ^ eb: out.add(rid[r])
    return out
def fires(texts):
    full = t._Ledger(texts).document()
    return {k: len(changed(full, t._Ledger(texts, frozenset(v)).document())) for k, v in FLAGS.items()}
res = {"shipped": fires(t._shipped_texts())}
st = t._shipped_texts()
res["shipped_keys"] = {"cumulative": st["meter_reads.jsonl"].count('"cumulative"'), "revisions": st["rate_card.json"].count("revisions"), "payments.csv": "payments.csv" in st}
for c in ("fresh", "rescaled", "relocated", "rotated", "api", "recoded", "renamed"):
    res[c] = fires(t._corpus_texts(c))
    res[c]["labels"] = dict(collections.Counter("+".join(sorted(v)) for v in t._owned(c).values()))
    res[c]["payment_rows"] = t._corpus_texts(c).get("payments.csv", "").count("\n") - 1
print(json.dumps(res, indent=1))
