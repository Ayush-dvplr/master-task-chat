import sys, re, statistics, collections
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import *

SET = sys.argv[1] if len(sys.argv) > 1 else "doc85"
T = load_doc85() if SET == "doc85" else load_all()
N = len(T)
print(f"=== set {SET}: n={N}")
HELD = re.compile(r"hidden|heldout|held_out|unseen|challenge|corpus|generalis|extract|reseed|fresh", re.I)
SHIP = re.compile(r"shipped|visible|sample|given|public|untrapped", re.I)
HOLES = {"3f39299a", "b625f36e", "8d3e20fb", "80877080", "7c2e77a1", "6d12f970", "b42c61b9", "c55a1967"}
share5 = lambda d: sum(t["weight"] for t in d["pos_t"] if t["weight"] == 5) / d["tw"]
hshare = lambda d: sum(t["weight"] for t in d["pos_t"] if HELD.search(t["name"])) / d["tw"]
h5share = lambda d: sum(t["weight"] for t in d["pos_t"] if HELD.search(t["name"]) and t["weight"] == 5) / d["tw"]

# doc line 417 formula omits fired test negatives
for d in T:
    if d["tpen"]:
        print(f"F1 {d['id'][:8]} stored tests {d['tests_pct']}; doc-417 formula {100*d['tearn']/d['tw']:.2f}; with penalty {100*(d['tearn']+d['tpen'])/d['tw']:.2f}")

# ---------- confounds ----------
by_a = collections.defaultdict(list)
for d in T:
    by_a[d.get("author") or "?"].append(d)
print("C1 authors:", len(by_a))
for a, g in sorted(by_a.items(), key=lambda x: -len(x[1])):
    print(f"C1 {a}: n {len(g)} final {statistics.mean(d['final'] for d in g):.1f} tests {statistics.mean(d['tests_pct'] for d in g):.1f} "
          f"judge {statistics.mean(d['judge_pct'] for d in g):.1f} heavy {statistics.mean(share5(d) for d in g):.2f} "
          f"held {statistics.mean(hshare(d) for d in g):.2f} checks {statistics.mean(len(d['tests']) for d in g):.0f} <40 {sum(d['final']<40 for d in g)}")
# share of variance in final explained by author (eta^2)
def eta2(groups, key):
    allv = [key(d) for g in groups for d in g]; m = statistics.mean(allv)
    sst = sum((v - m) ** 2 for v in allv)
    ssb = sum(len(g) * (statistics.mean(key(d) for d in g) - m) ** 2 for g in groups)
    return ssb / sst
big = [g for g in by_a.values() if len(g) >= 3]
print(f"C2 eta^2 by author (authors with >=3 tasks, {sum(map(len, big))} tasks): final {eta2(big, lambda d: d['final']):.2f} "
      f"tests {eta2(big, lambda d: d['tests_pct']):.2f} heavy_share {eta2(big, share5):.2f} held_share {eta2(big, hshare):.2f}")
# within-author correlation: demean by author
def within(fx, fy, groups):
    xs, ys = [], []
    for g in groups:
        mx = statistics.mean(fx(d) for d in g); my = statistics.mean(fy(d) for d in g)
        xs += [fx(d) - mx for d in g]; ys += [fy(d) - my for d in g]
    return pearson(xs, ys)
for nm, fx in (("heavy_share", share5), ("held_share", hshare), ("held5_share", h5share), ("n_checks", lambda d: len(d["tests"])),
               ("in_lines", lambda d: d["in_lines"]), ("instr_len", lambda d: d["instr_len"])):
    print(f"C3 {nm}: pooled r_tests {pearson([fx(d) for d in T], [d['tests_pct'] for d in T]):+.2f} "
          f"within-author r_tests {within(fx, lambda d: d['tests_pct'], big):+.2f} within-author r_final {within(fx, lambda d: d['final'], big):+.2f}")
print(f"C3 tests vs judge: pooled r {pearson([d['tests_pct'] for d in T], [d['judge_pct'] for d in T]):+.2f} "
      f"within-author r {within(lambda d: d['tests_pct'], lambda d: d['judge_pct'], big):+.2f}")
cat = collections.defaultdict(list)
for d in T:
    cat[d.get("category") or "?"].append(d)
print("C4 categories:", {k: (len(v), round(statistics.mean(d["final"] for d in v), 1)) for k, v in sorted(cat.items(), key=lambda x: -len(x[1]))})
bigc = [g for g in cat.values() if len(g) >= 3]
print(f"C4 eta^2 by category: final {eta2(bigc, lambda d: d['final']):.2f}")

# ---------- within-task: shipped vs held-out ----------
pairs = []
for d in T:
    s = [t for t in d["pos_t"] if SHIP.search(t["name"]) and not HELD.search(t["name"])]
    h = [t for t in d["pos_t"] if HELD.search(t["name"])]
    if s and h:
        pairs.append((d["id"][:8], round(100 * sum(t["passed"] for t in s) / len(s)), round(100 * sum(t["passed"] for t in h) / len(h)), len(s), len(h)))
print(f"W1 tasks with shipped-named AND held-out-named checks: {len(pairs)}; held-out pass < shipped pass in "
      f"{sum(b < a for _, a, b, _, _ in pairs)}, equal {sum(a == b for _, a, b, _, _ in pairs)}, higher {sum(b > a for _, a, b, _, _ in pairs)}; "
      f"mean shipped {statistics.mean(a for _, a, _, _, _ in pairs):.0f}% mean held {statistics.mean(b for _, _, b, _, _ in pairs):.0f}%")
print("W1 pairs (id, shipped pass%, held pass%, n_ship, n_held):", pairs)
# same-weight control: weight-5 held-out vs weight-5 non-held-out in the same task
wp = []
for d in T:
    a = [t for t in d["pos_t"] if t["weight"] == 5 and HELD.search(t["name"])]
    b = [t for t in d["pos_t"] if t["weight"] == 5 and not HELD.search(t["name"])]
    if a and b:
        wp.append((sum(t["passed"] for t in b) / len(b), sum(t["passed"] for t in a) / len(a)))
print(f"W2 tasks with weight-5 held-out AND weight-5 non-held-out: {len(wp)}; held lower in {sum(h < s for s, h in wp)}, "
      f"equal {sum(h == s for s, h in wp)}; mean non-held {100*statistics.mean(s for s, _ in wp):.0f}% held {100*statistics.mean(h for _, h in wp):.0f}%")

# ---------- recipe (section 8) ----------
def recipe(d):
    npos = len(d["pos_t"])
    held5 = [t for t in d["pos_t"] if t["weight"] == 5 and HELD.search(t["name"])]
    return dict(r1=0.6 <= share5(d) <= 0.8, r1b=10 <= len(d["tests"]) <= 35, r3=len(held5) >= 6, r6=len(d["pos_j"]) > 0)
for k in ("r1", "r1b", "r3"):
    g = [d for d in T if recipe(d)[k]]
    print(f"R {k}: n {len(g)} final mean {statistics.mean(d['final'] for d in g):.1f} <40 {sum(d['final']<40 for d in g)}")
g = [d for d in T if recipe(d)["r1"] and recipe(d)["r3"]]
print(f"R r1+r3 (heavy 60-80% and >=6 weight-5 held-out checks): n {len(g)}", [(d["id"][:8], d["final"], d["tests_pct"], d["judge_pct"]) for d in g])
g = [d for d in T if recipe(d)["r1"] and recipe(d)["r1b"] and recipe(d)["r3"]]
print(f"R r1+r1b+r3 (also 10-35 checks): n {len(g)}", [(d["id"][:8], d["final"]) for d in g])
g = [d for d in T if h5share(d) >= 0.5]
print(f"R held-out weight-5 share >= 50%: n {len(g)} final mean {statistics.mean(d['final'] for d in g):.1f} <40 {sum(d['final']<40 for d in g)}",
      sorted((d["final"], d["id"][:8], d["tests_pct"], d["judge_pct"]) for d in g))

# ---------- tasks under 40 ----------
low = sorted((d for d in T if d["final"] < 40), key=lambda d: d["final"])
print(f"L tasks final<40: {len(low)}")
for d in low:
    print(f"L {d['id'][:8]} final {d['final']} tests {d['tests_pct']} judge {d['judge_pct']} heavy {share5(d):.2f} held {hshare(d):.2f} held5 {h5share(d):.2f} "
          f"checks {len(d['tests'])} crit {len(d['rubric'])} author {d.get('author')} hole {d['id'][:8] in HOLES} model {d.get('model', 'opus-5')}")
lt25 = [d for d in low if d["final"] < 25]
print(f"L <25 profile tests in [5,25]: {sum(5 <= d['tests_pct'] <= 25 for d in lt25)}/{len(lt25)}; judge in [25,45]: "
      f"{sum(25 <= d['judge_pct'] <= 45 for d in lt25)}/{len(lt25)}; final in [15,35]: {sum(15 <= d['final'] <= 35 for d in lt25)}/{len(lt25)}")
print("L <40: tests<85 & judge<85:", sum(d["tests_pct"] < 85 and d["judge_pct"] < 85 for d in low), "of", len(low),
      "| tests summary", summary([d["tests_pct"] for d in low]), "judge summary", summary([d["judge_pct"] for d in low]))
print("L <40 excluding section-8 hole tasks:", sum(d["id"][:8] not in HOLES for d in low))
ok = [d for d in T if d["final"] < 50]
print(f"G final<50 n {len(ok)}; of them tests<85&judge<85 {sum(d['tests_pct'] < 85 and d['judge_pct'] < 85 for d in ok)}")
print("G tasks with tests<85 & judge<85:", sum(d["tests_pct"] < 85 and d["judge_pct"] < 85 for d in T), "of", N,
      "; of those final<40:", sum(d["tests_pct"] < 85 and d["judge_pct"] < 85 and d["final"] < 40 for d in T))
# what judge% did <40 need given tests
print("G <40 tasks with judge >= 60:", [(d["id"][:8], d["tests_pct"], d["judge_pct"]) for d in low if d["judge_pct"] >= 60])
print("G judge<0 (negatives exceed earned):", [(d["id"][:8], d["judge_pct"]) for d in T if d["judge_pct"] < 0])
