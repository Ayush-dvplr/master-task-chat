import sys, time
sys.path.insert(0, '.')
from load import load
import vouch
m = load()
exec(open('stmt_block.py').read(), m.__dict__)
for corpus in sys.argv[1:] or ["fresh","rescaled","relocated","rotated","api","recoded","renamed"]:
    t=time.time(); texts = m._statement_texts(corpus); tg=time.time()-t
    t=time.time(); doc = m._statements(texts); tr=time.time()-t
    rows = m._voucher_rows(texts); bal = m._balances(texts)
    big = [a for a in rows if bal.get(a,0) > 50000]
    gbad = sum(vouch.greedy(bal.get(a,0), rows[a]) != s["redeemed"] for a,s in zip(sorted(rows), doc["statements"]))
    print(corpus, "gen %.1fs ref %.2fs" % (tg, tr), "stmts", len(doc["statements"]), "big", [(bal[a], len(rows[a])) for a in big], "greedy wrong", gbad)
