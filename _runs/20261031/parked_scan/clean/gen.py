import sys, json, time
from pathlib import Path
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
import test_output as T
def write(d, files):
    d = Path(d); d.mkdir(parents=True, exist_ok=True)
    for k, v in files.items(): (d / k).write_text(v)
t = time.time(); f = T.book_files("SHIPPED"); write(sys.argv[3] + "/ship", f)
print("ship gen %.2fs lines %d" % (time.time() - t, sum(v.count("\n") for v in f.values())))
r = T._Rng(777001); specs = []
for _ in range(340):
    n = r.randint(4, 10); specs.append({"jobs": n, "overlap": min(n, r.randint(3, 5)), "mand": 0, "crew": (15, 60), "fee": (20, 200), "values": (200, 900), "dur": (30, 180)})
for _ in range(100):
    n = r.randint(11, 30); specs.append({"jobs": n, "overlap": r.randint(4, 6), "mand": 0, "crew": (20, 50), "fee": (30, 180), "values": (200, 900), "dur": (30, 180)})
for _ in range(60):
    specs.append({"jobs": 72, "overlap": 7, "mand": 0, "crew": (25, 60), "fee": (20, 160), "values": (200, 900), "dur": (30, 180)})
r.shuffle(specs)
t = time.time(); f = T.make_book(777001, specs, [0] * len(specs), 3000, 2600, (75, 1500), 60); write(sys.argv[3] + "/x4", f)
print("x4 gen %.2fs nights %d jobs %d lines %d" % (time.time() - t, len(specs), sum(s["jobs"] for s in specs), sum(v.count("\n") for v in f.values())))
