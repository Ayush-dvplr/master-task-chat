import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
import test_output as T
jobs, ov, nn, out = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
specs = [{"jobs": jobs, "overlap": ov, "mand": 0, "crew": (25, 60), "fee": (20, 160), "values": (200, 900), "dur": (30, 180)} for _ in range(nn)]
f = T.make_book(880001 + jobs, specs, [0] * nn, 3000, 2600, (75, 1500), 60)
d = Path(out); d.mkdir(parents=True, exist_ok=True)
for k, v in f.items(): (d / k).write_text(v)
