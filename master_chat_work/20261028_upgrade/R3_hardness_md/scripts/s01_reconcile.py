"""W1: reconcile Final_Delivery entries (94) vs the doc's 85; recompute final_reward from raw fields."""
import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import *

entries = sorted(FD.iterdir())
print("entries:", len(entries), "dirs:", sum(p.is_dir() for p in entries),
      "files:", [p.name for p in entries if p.is_file()])
nore = []
for p in entries:
    if p.is_dir() and not (p / REL / "report.json").exists():
        alt = [str(x.relative_to(p)) for x in (p / "trajectories").rglob("report.json")] if (p / "trajectories").exists() else []
        nore.append((p.name, alt))
print("dirs without claude-opus-5/run_1/report.json:", nore)

T = load_all(with_inputs=False)
print("tasks with opus-5 report:", len(T))
print("judge models:", {d["judge_model"] for d in T})
print("exceptions:", [d["id"][:8] for d in T if d.get("exception")])

# recompute
bad = []
for d in T:
    t, j, f = recompute(d)
    if abs(t - d["tests_pct"]) > 0.01 or abs(j - d["judge_pct"]) > 0.01 or abs(f - d["final"]) > 0.011:
        bad.append((d["id"][:8], round(t, 2), d["tests_pct"], round(j, 2), d["judge_pct"], f, d["final"]))
print("recompute mismatches (tests/judge/final):", len(bad), bad[:10])
for tid in ("59417607", "8defd7be", "ec7941e5"):
    d = next(x for x in T if x["id"].startswith(tid))
    t, j, f = recompute(d)
    print(f"  sample {tid}: tests {d['tearn']}+{d['tpen']}/{d['tw']}={t:.2f} (stored {d['tests_pct']}); "
          f"judge {d['jearn']}+{d['jpen']}/{d['jw']}={j:.2f} (stored {d['judge_pct']}); final {f} (stored {d['final']})")

# alternative semantic check: does a judge negative with passed True count as fired? (should not reproduce)
alt_bad = 0
for d in T:
    jpen_alt = sum(c["score"] for c in d["neg_j"] if c["passed"])
    j = (d["jearn"] + jpen_alt) / d["jw"] * 100
    if abs(j - d["judge_pct"]) > 0.01:
        alt_bad += 1
print("alt semantics (judge negative passed=True fires) mismatches:", alt_bad)

# timing: which runs existed on 2026-10-27
from collections import Counter
print("run start dates:", sorted(Counter((d.get("started_at") or "?")[:10] for d in T).items()))
late = [d for d in T if (d.get("started_at") or "") >= "2026-10-27T18:30"]  # after 27 Oct IST midnight-ish
print("runs started >= 2026-10-27T18:30Z:", [(d["id"][:8], d["started_at"]) for d in late])

def head(S, label):
    f = [d["final"] for d in S]
    nt = sum(len(d["tests"]) for d in S); nj = sum(len(d["rubric"]) for d in S)
    npt = sum(len(d["pos_t"]) for d in S); npj = sum(len(d["pos_j"]) for d in S)
    print(f"[{label}] n={len(S)} mean={sum(f)/len(f):.2f} median={statistics.median(f):.2f} min={min(f)} max={max(f)} "
          f">=60:{sum(x>=60 for x in f)} <40:{sum(x<40 for x in f)} <25:{sum(x<25 for x in f)} "
          f"tests_all={nt} tests_pos={npt} judge_all={nj} judge_pos={npj}")
head(T, "all90")
# search for a subset of 5 to drop that reproduces doc totals 2950 tests / 1842 criteria / mean 51.95
nt = sum(len(d["tests"]) for d in T); nj = sum(len(d["rubric"]) for d in T)
print("need to drop tests:", nt - 2950, "criteria:", nj - 1842, "final-sum:", round(sum(d['final'] for d in T) - 51.95 * 85, 2))
# try: drop most recent runs
byt = sorted(T, key=lambda d: d.get("started_at") or "")
head(byt[:85], "earliest85")
import itertools
cands = []
for combo in itertools.combinations(range(len(T)), 5):
    s_t = sum(len(T[i]["tests"]) for i in combo)
    if s_t != nt - 2950:
        continue
    s_j = sum(len(T[i]["rubric"]) for i in combo)
    if s_j != nj - 1842:
        continue
    cands.append(combo)
    if len(cands) > 50:
        break
print("5-task drop sets matching both totals (all items):", len(cands))
for c in cands[:5]:
    S = [T[i] for i in range(len(T)) if i not in c]
    head(S, "drop " + ",".join(T[i]["id"][:8] for i in c))
