"""Offline: compute the wide extracts' optima with _exact, check them against the pickled bounded answers
(p12q2/calls_wide<k>.pkl, the oracle mirror's answers), and write the _WIDE_TRUTH table into test_output.src.py.

Run embed.py first (tests/test_output.py must be the current src). Also checks shipped and H2 against their pickles.
Usage: python3 -B p12q2/gen_wide_truth.py [--write]
"""
import hashlib
import importlib.util
import pickle
import re
import sys
import time
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
BUNDLE = WORK.parent.parent / "district-heat-flex-procurement"
sys.path.insert(0, str(WORK / "stub"))
spec = importlib.util.spec_from_file_location("tq", BUNDLE / "tests" / "test_output.py")
tq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tq)
tq._WIDE_TRUTH.clear()
real = tq._exact
seen: list[tuple[str, tuple, float]] = []


def rec(cands, goals, caps, floors, cw, vw, width):
    digest = hashlib.sha256(repr((cands, goals, caps, floors, cw, vw, width)).encode()).hexdigest()[:24]
    t0 = time.perf_counter()
    out = real(cands, goals, caps, floors, cw, vw, width)
    seen.append((digest, out, time.perf_counter() - t0))
    return out


tq._exact = rec
table: dict[str, tuple[int, str]] = {}
bad = 0
for name in ("shipped", "H2", "wide0", "wide1", "wide2", "wide3"):
    start = len(seen)
    t0 = time.perf_counter()
    if name == "shipped":
        tq.expected(tq.visible_root())
    elif name == "H2":
        tq.expected(tq.hidden_root("H2"))
    else:
        tq.expected(tq.wide_root(int(name[-1]))[0])
    got = seen[start:]
    want = pickle.loads((WORK / "p12q2" / f"calls_{name}.pkl").read_bytes())
    miss = sum(1 for (d, out, s), w in zip(got, want) if (tuple(out[0]), out[1]) != (tuple(w["want"][0]), w["want"][1]))
    miss += abs(len(got) - len(want))
    bad += miss
    worst = max((s for _, _, s in got), default=0.0)
    print(f"{name}: calls {len(got)} (pickle {len(want)}) mismatches {miss} total {time.perf_counter() - t0:.1f}s "
          f"worst call {worst:.1f}s", flush=True)
    if name.startswith("wide"):
        for d, out, _ in got:
            table[d] = (out[1], " ".join(out[0]))
print("table entries", len(table), "mismatches", bad)
if "--write" in sys.argv and bad == 0:
    src_path = WORK / "test_output.src.py"
    src = src_path.read_text()
    body = "".join(f"    {d!r}: ({w}, {ids!r}),\n" for d, (w, ids) in sorted(table.items()))
    new, n = re.subn(r"^_WIDE_TRUTH: dict\[str, tuple\[int, str\]\] = \{.*?^\}\n|^_WIDE_TRUTH: dict\[str, tuple\[int, str\]\] = \{\}\n",
                     lambda m: "_WIDE_TRUTH: dict[str, tuple[int, str]] = {\n" + body + "}\n", src, count=1,
                     flags=re.S | re.M)
    assert n == 1
    src_path.write_text(new)
    print("wrote", len(table), "entries into", src_path)
