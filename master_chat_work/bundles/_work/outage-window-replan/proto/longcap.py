"""Long-cap run of the strongest B&B (components + heuristic order): does it finish inside the per-run limit?
usage: python3 longcap.py <cap_s> <seed>..."""
import sys
import time
from lanegen import gen_lane
from lane import Lane, reference
from lanekill import label
from lanekill2 import comp_bb

cap = float(sys.argv[1])
for sd in [int(x) for x in sys.argv[2:]]:
    d = gen_lane(sd, "hidden")
    L = Lane(d)
    ref = reference(L)
    t0 = time.time()
    p, c = comp_bb(d, L, cap, True)
    print("seed=%d comp_heur=%s%s(%.1f)" % (sd, label(L, p, ref), "/capped" if c else "", time.time() - t0), flush=True)
