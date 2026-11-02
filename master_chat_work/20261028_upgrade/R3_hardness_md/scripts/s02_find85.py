"""W1b: which 85 of the 90 opus-5 reports did the doc use? Search 5-task drop sets matching the doc's
headline numbers (2,950 checks, 1,842 criteria, mean 51.95, median 53.99, >=60 36, <40 18, <25 7,
positive test weight 8,429 / earned 3,734, positive judge weight 4,514)."""
import sys, itertools
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import *

T = load_all(with_inputs=False)
N = len(T)
tot = dict(nt=sum(len(d["tests"]) for d in T), nj=sum(len(d["rubric"]) for d in T),
           tw=sum(d["tw"] for d in T), te=sum(d["tearn"] for d in T), jw=sum(d["jw"] for d in T),
           je=sum(d["jearn"] for d in T), fs=sum(d["final"] for d in T))
print("90-set totals:", {k: round(v, 2) for k, v in tot.items()})
doc = dict(nt=2950, nj=1842, tw=8429, te=3734, jw=4514)
print("doc 85 totals:", doc, "=> dropped must sum to", {k: round(tot[k] - doc[k], 2) for k in doc})

def score(S):
    f = sorted(d["final"] for d in S)
    return dict(mean=round(sum(f) / len(f), 2), median=round(statistics.median(f), 2),
                ge60=sum(x >= 60 for x in f), lt40=sum(x < 40 for x in f), lt25=sum(x < 25 for x in f))

best = []
for combo in itertools.combinations(range(N), 5):
    if sum(len(T[i]["tests"]) for i in combo) != tot["nt"] - 2950:
        continue
    if sum(len(T[i]["rubric"]) for i in combo) != tot["nj"] - 1842:
        continue
    S = [T[i] for i in range(N) if i not in combo]
    s = score(S)
    dist = (abs(s["mean"] - 51.95) + abs(s["median"] - 53.99) + abs(s["ge60"] - 36) + abs(s["lt40"] - 18) + abs(s["lt25"] - 7)
            + abs(sum(d["tw"] for d in S) - 8429) / 10 + abs(sum(d["jw"] for d in S) - 4514) / 10)
    best.append((round(dist, 2), [T[i]["id"][:8] for i in combo], s,
                 sum(d["tw"] for d in S), sum(d["tearn"] for d in S), sum(d["jw"] for d in S), sum(d["jearn"] for d in S)))
best.sort(key=lambda x: x[0])
print("drop sets matching check+criterion counts:", len(best))
for b in best[:8]:
    print(b)
exact = [b for b in best if b[0] == 0]
print("exact matches on all doc headline figures:", len(exact))
