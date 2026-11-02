"""Scratch: claim distribution of committed accounts per region on generator months (hidden and shipped)."""
import sys, csv, io
from pathlib import Path
sys.path.insert(0, "/fz")
import fz_mu  # noqa: F401  (patches T._gen_rate)
T = fz_mu.T


def canon(a):
    return a.strip().upper().replace("-", "")


def cents(s):
    return int(s.replace(".", ""))


for label, seed, month, rows, accts, hidden in (("shipped", None, None, None, None, False),
                                               ("hidden", T.HIDDEN_SEED, "2027-08", 1600, 1200, True)):
    if seed is None:
        files = {p.name: p.read_bytes() for p in Path("/data").iterdir()}
    else:
        files = T.gen_month(seed, month, rows, accts, hidden, T.ref_compute)
    docs = T.ref_compute(files)
    text = files["accounts.csv"]
    text = text.decode() if isinstance(text, bytes) else text
    committed = {canon(r["account_id"]) for r in csv.DictReader(io.StringIO(text)) if r["plan"].strip() == "committed"}
    print("==", label, "lines", len(docs["normalized.jsonl"]), "committed accts", len(committed))
    for r in T.REF_REGIONS:
        claims = {}
        for ln in docs["normalized.jsonl"]:
            if ln["region"] == r and ln["account_id"] in committed:
                claims[ln["account_id"]] = claims.get(ln["account_id"], 0) + cents(ln["charge"])
        v = sorted(claims.values())
        doc = docs["region_%s.json" % r]
        tot = sum(v)
        print(r, "n", len(v), "base", doc["credit_base"], "pool", doc["credit_pool"], "min", v[0] / 100, "p10", v[len(v) // 10] / 100,
              "median", v[len(v) // 2] / 100, "max", v[-1] / 100,
              "share<1%", sum(1 for x in v if x * 100 < tot), "sum<1% frac", round(sum(x for x in v if x * 100 < tot) / tot, 3),
              "below2500", sum(1 for x in v if x < 2500), "frac<2500", round(sum(x for x in v if x < 2500) / tot, 3))
