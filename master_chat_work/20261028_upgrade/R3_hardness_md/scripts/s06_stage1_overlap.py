import sys, hashlib
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import *

fd = {p.name: p for p in FD.iterdir() if p.is_dir()}
st = {p.name: p for p in STAGE1.iterdir() if p.is_dir()}
both = sorted(set(fd) & set(st))
print(f"Final_Delivery dirs {len(fd)}, anubis-stage-1 dirs {len(st)}, overlap {len(both)}, "
      f"FD only {sorted(k[:8] for k in set(fd) - set(st))}, stage-1 only {sorted(k[:8] for k in set(st) - set(fd))}")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


same = diff = miss = 0
rows = []
for k in both:
    for rel in (REL, REL55):
        a, b = fd[k] / rel / "report.json", st[k] / rel / "report.json"
        if a.exists() or b.exists():
            if not (a.exists() and b.exists()):
                miss += 1; rows.append((k[:8], str(rel), "missing in " + ("stage-1" if a.exists() else "FD")))
            elif sha(a) == sha(b):
                same += 1
            else:
                diff += 1
                ra, rb = json.loads(a.read_text()), json.loads(b.read_text())
                rows.append((k[:8], str(rel), "DIFF", ra["final_reward"], rb["final_reward"]))
print(f"report.json byte-identical {same}, differ {diff}, one side missing {miss}")
for r in rows:
    print("  ", r)
files = ("instruction.md", "tests/test_output.py", "tests/judge.toml", "task.toml")
for f in files:
    eq = sum(sha(fd[k] / f) == sha(st[k] / f) for k in both)
    print(f"{f}: identical in {eq} of {len(both)}")
