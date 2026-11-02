"""W1c: reproduce the doc's 85-bundle set from git history (read-only: git ls-tree / git show).
Commit 95f8fb386 (2026-10-27 18:23 IST) is "Update Final Delivery difficulty report and leaderboard for 85 tasks".
Headline figures are computed for (a) 83 opus-5 reports, (b) 83 opus-5 + 2 opus-5-5 reports = 85."""
import sys, json, subprocess, statistics
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import ROOT

REPO = ROOT / "Anubis_Tasks_Samples"
COMMIT = sys.argv[1] if len(sys.argv) > 1 else "95f8fb386"


def git(*a):
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True, check=True).stdout


def load(commit=COMMIT):
    names = git("ls-tree", "-r", "--name-only", commit, "Final_Delivery").splitlines()
    reps = [n for n in names if n.endswith("/run_1/report.json") and "/trajectories/" in n]
    by = {}
    for n in reps:
        tid, model = n.split("/")[1], n.split("/")[3]
        by.setdefault(tid, {})[model] = json.loads(git("show", f"{commit}:{n}"))
    return by


def head(rs, label):
    f = sorted(r["final_reward"] for r in rs)
    nt = sum(len(r["pytest"]["tests"]) for r in rs)
    nj = sum(len(r["rubric"]) for r in rs)
    tw = sum(t["weight"] for r in rs for t in r["pytest"]["tests"] if t["weight"] > 0)
    te = sum(t["weight"] for r in rs for t in r["pytest"]["tests"] if t["weight"] > 0 and t["passed"])
    jw = sum(c["score"] for r in rs for c in r["rubric"] if c["is_positive"])
    je = sum(c["score"] for r in rs for c in r["rubric"] if c["is_positive"] and c["passed"])
    tp = [r["test_weights_percentage"] for r in rs]; jp = [r["rubric_weights_percentage"] for r in rs]
    print(f"[{label}] n={len(rs)} mean={statistics.mean(f):.2f} median={statistics.median(f):.2f} min={f[0]} max={f[-1]} "
          f">=60:{sum(x>=60 for x in f)} <40:{sum(x<40 for x in f)} <25:{sum(x<25 for x in f)} | checks={nt} criteria={nj} "
          f"| test pos weight={tw} earned={te} | judge pos weight={jw} earned={je} | mean tests%={statistics.mean(tp):.2f} "
          f"mean judge%={statistics.mean(jp):.2f} tests<judge in {sum(a<b for a,b in zip(tp,jp))} "
          f"tests<=judge/2 in {sum(a<=b/2 for a,b in zip(tp,jp))}")


if __name__ == "__main__":
    by = load()
    print("commit", COMMIT, "task dirs with any report:", len(by), "models:",
          sorted({m for v in by.values() for m in v}))
    o5 = [v["claude-opus-5"] for v in by.values() if "claude-opus-5" in v]
    head(o5, "opus-5 only")
    mix = [v.get("claude-opus-5") or v.get("claude-opus-5-5") for v in by.values()]
    head(mix, "opus-5 + opus-5-5 fallback")
    print("tasks with only opus-5-5:", [k[:8] for k, v in by.items() if "claude-opus-5" not in v])
