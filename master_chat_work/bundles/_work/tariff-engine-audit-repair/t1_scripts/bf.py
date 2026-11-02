import sys, json, importlib.util, collections
sys.path.insert(0, "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/tariff-engine-audit-repair/rewardkit_stub")
spec = importlib.util.spec_from_file_location("t", "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/tariff-engine-audit-repair/tests/test_output.py")
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
def fires(texts):
    full = t._Ledger(texts).document()
    out = {}
    for q in t._QUIET:
        d = t._Ledger(texts, frozenset({q})).document()
        fa = {i["account"] for i in full["invoices"]}
        changed = set()
        bya = collections.defaultdict(list); byb = collections.defaultdict(list)
        for i in full["invoices"]: bya[i["account"]].append(i)
        for i in d["invoices"]: byb[i["account"]].append(i)
        for a in set(bya)|set(byb):
            if json.dumps(bya[a],sort_keys=True)!=json.dumps(byb[a],sort_keys=True): changed.add(a)
        ea = {(e["read_id"],e["reason"]) for e in full["exceptions"]}; eb={(e["read_id"],e["reason"]) for e in d["exceptions"]}
        rid = {e["read_id"]:e["account"] for e in full["exceptions"]+d["exceptions"]}
        for r,_ in ea ^ eb: changed.add(rid[r])
        out[q] = len(changed)
    return out
res = {"shipped": fires(t._shipped_texts())}
for c in t._HIDDEN:
    res[c] = fires(t._corpus_texts(c))
    labels = collections.Counter("+".join(sorted(v)) for v in t._owned(c).values())
    res[c]["labels"] = dict(labels)
# raw evidence of key presence in shipped
st = t._shipped_texts()
res["shipped_keys"] = {"estimated": st["meter_reads.jsonl"].count('"estimated"'), "standing_changes": st["rate_card.json"].count("standing_changes")}
print(json.dumps(res, indent=1))
