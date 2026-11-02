"""grade.py <tests_dir> <workspace> [label]: run every check, print JSON summary."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import rk  # noqa: E402

tests_dir, workspace = sys.argv[1], sys.argv[2]
label = sys.argv[3] if len(sys.argv) > 3 else workspace
T = rk.load(tests_dir)
res = {}
for name, fn in rk.REG.items():
    res[name] = bool(fn(Path(workspace)))
pos_total = sum(w for w in rk.W.values() if w > 0)
earned = sum(rk.W[n] for n, v in res.items() if v and rk.W[n] > 0)
neg = sum(rk.W[n] for n, v in res.items() if v and rk.W[n] < 0)
lost = sorted(n for n, v in res.items() if not v and rk.W[n] > 0)
fired = sorted(n for n, v in res.items() if v and rk.W[n] < 0)
print(json.dumps({"label": label, "earned": earned, "neg": neg, "P": pos_total,
                  "score": round(max(0, earned + neg) / pos_total, 4),
                  "lost": lost, "fired": fired}, sort_keys=True))
