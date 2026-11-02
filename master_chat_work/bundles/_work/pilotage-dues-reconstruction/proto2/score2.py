"""Score kill outputs against the generator truth. Usage: score2.py CORPUS.json OUT.json"""
import json
import sys
from datetime import date

from core2 import recompute


def expected(doc):
    cals = {k: {date.fromisoformat(d) for d in v} for k, v in doc["calendars"].items()}
    exp = {}
    for st in doc["stations"]:
        tr = st["truth"]
        conv = dict(tr["conv"])
        conv["N"] = tuple(conv["N"])
        tars = [None if a else tuple(t) for t, a in zip(tr["tariffs"], tr["ambiguous"])]
        exp[st["station"]] = {"tariffs": [list(t) if t else "many" for t in tars],
                              "recomputed": recompute(st, cals, conv, tars)}
    return exp


if __name__ == "__main__":
    doc = json.load(open(sys.argv[1]))
    got = json.load(open(sys.argv[2]))
    exp = expected(doc)
    ok = [s for s in exp if exp[s] == {k: got[s][k] for k in ("tariffs", "recomputed")}]
    print(sys.argv[2].rsplit("/", 1)[-1], f"stations exact {len(ok)}/{len(exp)}", ok)
