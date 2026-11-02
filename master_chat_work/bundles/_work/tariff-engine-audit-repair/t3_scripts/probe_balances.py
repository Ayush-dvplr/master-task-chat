import sys, time
from fractions import Fraction
from datetime import date
sys.path.insert(0, __file__.rsplit("/",1)[0])
from load import load
m = load()
for c in ("fresh","rescaled","relocated","rotated","api","recoded","renamed"):
    t=time.time(); texts = m._corpus_texts(c); L = m._Ledger(texts); doc = L.document()
    bal = {}
    for inv in doc["invoices"]:
        a = inv["account"]; p = L.paid.get((a, date.fromisoformat(inv["period"]["start"])), Fraction(0))
        bal[a] = bal.get(a, Fraction(0)) + Fraction(inv["total"]) - p
    vals = sorted(int(v*100) for v in bal.values())
    labels = m._owned(c)
    print(c, len(bal), "files", sorted(texts), "t=%.1fs"%(time.time()-t))
    print("  balances cents min/med/max", vals[0], vals[len(vals)//2], vals[-1], "n<=0", sum(v<=0 for v in vals), "owned", len(labels))
    print("  top", vals[-8:])
