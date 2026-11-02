import importlib.util, json, sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import run_tests
run_tests.stub()
spec = importlib.util.spec_from_file_location("t", HERE.parent.parent / "flood-repair-portfolio/tests/test_output.py")
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
M = ["greedy_w","greedy_ratio","local_swap","ils","lp_round","lp_round_ls","bnb_colour","bnb_memo_reduce_split","reduce_bnb"]
out = {}
for book, cand in [("H1","h1_4"),("H2","h2_1"),("H3","h3_1"),("M","m_2")]:
    L = t._Ledger(t.book_files(book))
    rows = [json.loads(x) for x in open(HERE/f"logs/base_{cand}.log") if x.startswith("{")]
    for r in rows:
        rd = L.rounds[r["round"]]; info = rd["info"]
        line = {"book":book,"round":r["round"],"n":r["n"],"opt":rd["total"]}
        for m in M:
            v = r[m]; got = sum(info[p]["benefit"] for p in v["ids"])
            line[m] = ("0" if v["exact"] else str(rd["total"]-got)) + ("/TO" if "TO" in str(v.get("note","")) or "timeout" in str(v.get("note","")) else "")
        print(json.dumps(line))
