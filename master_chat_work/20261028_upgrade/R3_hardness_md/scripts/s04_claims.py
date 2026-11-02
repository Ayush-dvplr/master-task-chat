import sys, re, statistics, collections
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import *

SET = sys.argv[1] if len(sys.argv) > 1 else "doc85"
T = load_doc85() if SET == "doc85" else load_all()
N = len(T)
print(f"=== set {SET}: n={N}")


def pct(a, b):
    return round(100 * a / b, 1) if b else float("nan")


# ---------- S1 headline + channel split ----------
f = [d["final"] for d in T]
tp = [d["tests_pct"] for d in T]; jp = [d["judge_pct"] for d in T]
print("S1 final", summary(f), ">=60", sum(x >= 60 for x in f), "<40", sum(x < 40 for x in f), "<25", sum(x < 25 for x in f),
      "==0", sum(x == 0 for x in f))
print("S1 tests", summary(tp), "earned", sum(d["tearn"] for d in T), "of", sum(d["tw"] for d in T))
print("S1 judge", summary(jp), "earned", sum(d["jearn"] for d in T), "of", sum(d["jw"] for d in T))
print("S1 tests<judge", sum(a < b for a, b in zip(tp, jp)), "tests>judge", sum(a > b for a, b in zip(tp, jp)))
print("S1 checks", sum(len(d["tests"]) for d in T), "criteria", sum(len(d["rubric"]) for d in T))

# ---------- S2 examples ----------
for tid in ("59417607", "8defd7be", "d49e259f"):
    d = next((x for x in T if x["id"].startswith(tid)), None)
    if not d:
        continue
    ok = [t["name"] for t in d["pos_t"] if t["passed"]]
    bad = [(t["name"], t["weight"]) for t in d["pos_t"] if not t["passed"]]
    print(f"S2 {tid} final {d['final']} tests {d['tests_pct']} passed={ok}")
    print(f"S2 {tid} failed n={len(bad)}: {bad}")

# ---------- S3 themes ----------
THEMES = {
    "heldout": r"hidden|heldout|held_out|unseen|challenge|corpus|generalis|extract|reseed|fresh",
    "xfile": r"resolv|lookup|chain|cross|join",
    "exact": r"exact|byte|identical|equal",
    "edge": r"tie|empty|malformed|boundar|round|trap|edge",
    "determinism": r"determin|idempot|twice|rerun|stable|repeat|reproduc",
    "plumbing": r"exist|runs|parse|cli|deliver",
    "shape": r"shape|key|schema|serial|format",
}
P = [(d, t) for d in T for t in d["pos_t"]]
TW = sum(t["weight"] for _, t in P)
for k, rx in THEMES.items():
    r = re.compile(rx, re.I)
    s = [t for _, t in P if r.search(t["name"])]
    fl = [t for t in s if not t["passed"]]
    wl = sum(t["weight"] for t in fl); wa = sum(t["weight"] for t in s)
    print(f"S3 theme {k}: checks {len(s)} failed {pct(len(fl), len(s))}% weight lost {wl} ({pct(wl, wa)}% of tier, {pct(wl, TW)}% of all)")
rp, rx_ = re.compile(THEMES["plumbing"] + "|" + THEMES["shape"], re.I), re.compile(THEMES["exact"], re.I)
both = sig = 0
for d in T:
    pl = [t for t in d["pos_t"] if rp.search(t["name"])]
    ex = [t for t in d["pos_t"] if rx_.search(t["name"])]
    if pl and ex:
        both += 1
        if pct(sum(t["passed"] for t in pl), len(pl)) >= 75 and pct(sum(t["passed"] for t in ex), len(ex)) <= 50:
            sig += 1
print(f"S3 tasks with plumbing/shape AND exact checks: {both}; plumbing>=75% pass & exact<=50% pass: {sig}")

for w in (1.0, 3.0, 5.0):
    s = [t for _, t in P if t["weight"] == w]
    print(f"S3 weight {w}: failed {sum(not t['passed'] for t in s)} of {len(s)} = {pct(sum(not t['passed'] for t in s), len(s))}%")
lost5 = [d for d in T if any(t["weight"] == 5 for t in d["pos_t"]) and not any(t["weight"] == 5 and t["passed"] for t in d["pos_t"])]
print(f"S3 tasks failing every weight-5 check: {len(lost5)}; their tests%: {summary([d['tests_pct'] for d in lost5])}; "
      f"final: {summary([d['final'] for d in lost5])}; final>=50: {sum(d['final'] >= 50 for d in lost5)}; "
      f"tasks with no weight-5 check: {sum(not any(t['weight'] == 5 for t in d['pos_t']) for d in T)}")
# within-task: pass rate of weight-5 vs weight-1 in the same task
wt = [(pct(sum(t["passed"] for t in d["pos_t"] if t["weight"] == 5), sum(t["weight"] == 5 for t in d["pos_t"])),
       pct(sum(t["passed"] for t in d["pos_t"] if t["weight"] == 1), sum(t["weight"] == 1 for t in d["pos_t"])))
      for d in T if any(t["weight"] == 5 for t in d["pos_t"]) and any(t["weight"] == 1 for t in d["pos_t"])]
print(f"S3 within-task w5 vs w1 pass%: tasks {len(wt)}, w5<w1 in {sum(a < b for a, b in wt)}, equal {sum(a == b for a, b in wt)}, "
      f"mean w5 {statistics.mean(a for a, _ in wt):.1f} mean w1 {statistics.mean(b for _, b in wt):.1f}")

tok = collections.defaultdict(list)
for d, t in P:
    for w in set(t["name"].lower().split("_")):
        tok[w].append(t)
rows = sorted(((pct(sum(not t["passed"] for t in v), len(v)), len(v), w, sum(t["weight"] for t in v if not t["passed"]),
                len({id(x) for x in v}))
               for w, v in tok.items() if len(v) >= 40), reverse=True)
print("S3 tokens n>=40 (fail%, n, token, weight lost):", [(a, b, c, e) for a, b, c, e, _ in rows])
for w in ("delivered", "artifacts", "cli", "artifact", "config", "shipped"):
    v = tok.get(w, [])
    print(f"S3 token {w}: n {len(v)} fail {pct(sum(not t['passed'] for t in v), len(v))}%")
# task concentration of top tokens
for w in ("extract", "bit", "mode", "heldout", "corpus", "generalises"):
    tasks = collections.Counter(d["id"][:8] for d, t in P if w in t["name"].lower().split("_"))
    print(f"S3 token {w} comes from {len(tasks)} tasks: {tasks.most_common(4)}")

fc = collections.Counter()
for d in T:
    for t in d["pos_t"]:
        if not t["passed"]:
            fc[t["name"]] += 1
print("S3 most failed check names (tasks):", fc.most_common(16))
agg = [d for d in T if any(t["name"].startswith("aggregates_") for t in d["pos_t"])]
for d in agg:
    a = [t for t in d["pos_t"] if t["name"].startswith("aggregates_")]
    print(f"S3 aggregates family {d['id'][:8]} author={d.get('author')}: {len(a)} checks, passed {sum(t['passed'] for t in a)}")

# ---------- S4 judge ----------
PJ = [(d, c) for d in T for c in d["pos_j"]]
for key in ("evaluation_target", "importance"):
    cnt = collections.Counter(c[key] for _, c in PJ); fl = collections.Counter(c[key] for _, c in PJ if not c["passed"])
    print(f"S4 positive by {key}:", {k: (v, pct(fl[k], v)) for k, v in cnt.items()})
    cnt_all = collections.Counter(c[key] for d in T for c in d["rubric"])
    print(f"S4 all criteria by {key}:", dict(cnt_all))
JT = {
    "verify": r"verif|re-run|rerun|re-runs|second copy|independent|by hand|compares|cross-check|checks .* against",
    "derive": r"deriv|recompute|works out|computes|calculat|rather than|instead of",
    "cover": r"every|each|all of|covers",
    "honest": r"report|states|claims|honest|mentions|tells|response",
    "order": r"before|after|first|then|until",
    "read": r"opens|reads|inspect|looks at|examin",
}
for k, rx in JT.items():
    r = re.compile(rx, re.I)
    s = [c for _, c in PJ if r.search(c["criterion"])]
    print(f"S4 judge theme {k}: {len(s)} criteria, failed {pct(sum(not c['passed'] for c in s), len(s))}%")
crit = [len(d["rubric"]) for d in T]
print("S4 criteria per task", summary(crit), "positive", sum(len(d["pos_j"]) for d in T), "negative", sum(len(d["neg_j"]) for d in T))
tn = [(d["id"][:8], t["name"], t["weight"]) for d in T for t in d["neg_t"] if t["passed"]]
print("S4 test negatives defined", sum(len(d["neg_t"]) for d in T), "fired", tn)
jn = [(d["id"][:8], c["criterion"][:110], c["score"]) for d in T for c in d["neg_j"] if not c["passed"]]
print("S4 judge negatives defined", sum(len(d["neg_j"]) for d in T), "fired", len(jn), "in tasks", len({x[0] for x in jn}))
HON = re.compile(r"claim|states|reports|gives a figure|says|asserts|describes", re.I)
print("S4 fired judge negatives that are claim/overclaim wording:", sum(bool(HON.search(c)) for _, c, _ in jn), "of", len(jn))
for x in jn:
    print("   S4 fired:", x)
neg_fired_tasks = {x[0] for x in jn}
print("S4 final of tasks with a judge negative fired:", summary([d["final"] for d in T if d["id"][:8] in neg_fired_tasks]),
      "others:", summary([d["final"] for d in T if d["id"][:8] not in neg_fired_tasks]))
print("S4 judge points lost to fired negatives:", sum(-c["score"] for d in T for c in d["neg_j"] if not c["passed"]),
      "vs positive judge weight lost:", sum(c["score"] for d, c in PJ if not c["passed"]))

# ---------- S5 ceiling ----------
print("S5 both halves >=85:", [(d["id"][:8], d["tests_pct"], d["judge_pct"]) for d in T if d["tests_pct"] >= 85 and d["judge_pct"] >= 85])
print("S5 both halves >=70:", [(d["id"][:8], d["tests_pct"], d["judge_pct"]) for d in T if d["tests_pct"] >= 70 and d["judge_pct"] >= 70])
print("S5 tests>=85:", sum(d["tests_pct"] >= 85 for d in T), "judge>=85:", sum(d["judge_pct"] >= 85 for d in T))
print("S5 top5:", sorted(((d["final"], d["id"][:8], d["tests_pct"], d["judge_pct"]) for d in T), reverse=True)[:5])
print("S5 r(tests%, judge%) =", round(pearson(tp, jp), 3))
share5 = lambda d: sum(t["weight"] for t in d["pos_t"] if t["weight"] == 5) / d["tw"]
print("S5 lost5 tasks: tests% cap if all non-5 passed:", summary([round(100 * (1 - share5(d)), 1) for d in lost5]))

# ---------- S6 levers ----------
T.sort(key=share5)
q = [T[i * N // 4:(i + 1) * N // 4] for i in range(4)]
for i, g in enumerate(q):
    print(f"S6 L1 Q{i+1}: n {len(g)} heavy share {statistics.mean(share5(d) for d in g)*100:.0f}% tests {statistics.mean(d['tests_pct'] for d in g):.1f} "
          f"final {statistics.mean(d['final'] for d in g):.1f} judge {statistics.mean(d['judge_pct'] for d in g):.1f}")
H = re.compile(THEMES["heldout"], re.I)
hshare = lambda d: sum(t["weight"] for t in d["pos_t"] if H.search(t["name"])) / d["tw"]
hw = [d for d in T if hshare(d) > 0]
print(f"S6 L2 tasks with any heldout weight {len(hw)} final {statistics.mean(d['final'] for d in hw):.1f}; without {N-len(hw)} "
      f"final {statistics.mean(d['final'] for d in T if hshare(d) == 0):.1f}")
for lo, hi in ((0, 0.0001), (0.0001, 0.25), (0.25, 0.5), (0.5, 1.01)):
    g = [d for d in T if lo <= hshare(d) < hi]
    if g:
        print(f"S6 L2 heldout share [{lo},{hi}): n {len(g)} tests {statistics.mean(d['tests_pct'] for d in g):.1f} final {statistics.mean(d['final'] for d in g):.1f} <40 {sum(d['final']<40 for d in g)}")
print("S6 L3 input files", summary([d["in_files"] for d in T]), "lines", summary([d["in_lines"] for d in T]))
print("S6 L4 shape theme vs exact theme pass: see S3")

# ---------- S7 correlations ----------
feats = {
    "heavy_share": share5, "heldout_share": hshare, "cost": lambda d: d.get("cost"), "tokens": lambda d: d.get("tokens"),
    "pos_test_weight": lambda d: d["tw"], "n_criteria": lambda d: len(d["rubric"]), "in_bytes": lambda d: d["in_bytes"],
    "n_checks": lambda d: len(d["tests"]), "in_lines": lambda d: d["in_lines"], "in_files": lambda d: d["in_files"],
    "instr_len": lambda d: d["instr_len"],
}
for k, fn in feats.items():
    S = [d for d in T if fn(d) is not None]
    x = [fn(d) for d in S]
    print(f"S7 {k}: n {len(S)} r_final {pearson(x, [d['final'] for d in S]):+.2f} r_tests {pearson(x, [d['tests_pct'] for d in S]):+.2f} "
          f"rho_final {spearman(x, [d['final'] for d in S]):+.2f} rho_tests {spearman(x, [d['tests_pct'] for d in S]):+.2f}")
print("S7 medians: instr", statistics.median(d["instr_len"] for d in T), "tokens", statistics.median(d["tokens"] for d in T if d.get("tokens")),
      "cost", statistics.median(d["cost"] for d in T if d.get("cost")))
