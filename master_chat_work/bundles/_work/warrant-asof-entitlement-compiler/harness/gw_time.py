"""Time gateway.settle of a tool dir on a corpus: gw_time.py <tool_dir> <data_dir>."""
import sys
import time

sys.path.insert(0, sys.argv[1])
import corpus as corpus_mod  # noqa: E402
import gateway  # noqa: E402

t0 = time.time()
c = corpus_mod.Corpus(__import__("pathlib").Path(sys.argv[2]))
t1 = time.time()
by_at = gateway.observations(c)
order = gateway.suspects(c, by_at)
t2 = time.time()
print(f"load {t1 - t0:.1f}s suspects {t2 - t1:.1f}s instants {len(by_at)}", flush=True)
alive = gateway.readings(c)
n = 0
for at in order:
    if len(alive) == 1:
        break
    n += 1
    a = time.time()
    first = gateway.gateway_at(c, at, alive[0])
    b = time.time()
    before = len(alive)
    alive = [r for r in alive if gateway.agrees(first if r == alive[0] else first.variant(r), by_at[at])]
    print(f"inst {n} at {at} rows {len(by_at[at])} build {b - a:.2f}s eval {time.time() - b:.2f}s alive {before}->{len(alive)}",
          flush=True)
print(f"total {time.time() - t0:.1f}s instants {n} alive {alive}")
