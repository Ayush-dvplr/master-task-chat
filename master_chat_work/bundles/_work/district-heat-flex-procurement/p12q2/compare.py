"""Host experiment: run the test reference with bounded and with an exact method side by side.

usage: python3 -B compare.py EXACT_SNIPPET [roots...]   roots from: shipped H1 H2 wide0 wide1 wide2 wide3
"""
import importlib.util
import sys
import time
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
BUNDLE = WORK.parent.parent / "district-heat-flex-procurement"
sys.path.insert(0, str(WORK / "stub"))
snippet = Path(sys.argv[1]).read_text()
src = (BUNDLE / "tests" / "test_output.py").read_text()
anchor = "    sites_of: dict[tuple[str, str], list[dict[str, Any]]] = {}\n"
assert src.count(anchor) == 1
src = src.replace(anchor, snippet + "\n" + anchor)
old = "                solver = search if lazy & SEARCH_FLAGS else bounded\n"
assert src.count(old) == 1
src = src.replace(old, "                solver = search if lazy & SEARCH_FLAGS else _DUAL(bounded, exact, eid, region, root)\n")
src = src.replace("_SEARCH_MEMO: ", "STATS = []\n_SEARCH_MEMO: ", 1)
src += '''

def _DUAL(first, second, eid, region, root):
    def run(*args):
        t0 = time.perf_counter()
        a = first(*args)
        t1 = time.perf_counter()
        b = second(*args)
        t2 = time.perf_counter()
        STATS.append((str(root).rsplit("/", 1)[-1], eid, region, len(args[0]), t1 - t0, t2 - t1, a == b, a, b))
        return a
    return run
'''
path = WORK / "p12q2" / "_patched.py"
path.write_text(src)
spec = importlib.util.spec_from_file_location("tp", path)
tp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tp)
pick = sys.argv[2:] or ["shipped", "H1", "H2", "wide0", "wide1", "wide2", "wide3"]
for name in pick:
    t0 = time.perf_counter()
    start = len(tp.STATS)
    if name == "shipped":
        tp.expected(tp.visible_root())
    elif name in ("H1", "H2"):
        tp.expected(tp.hidden_root(name))
    else:
        tp.expected(tp.wide_root(int(name[-1]))[0])
    rows = tp.STATS[start:]
    bad = [r for r in rows if not r[6]]
    slow = sorted(rows, key=lambda r: -r[5])[:3]
    print(f"{name}: calls {len(rows)} mismatches {len(bad)} bounded {sum(r[4] for r in rows):.1f}s "
          f"exact {sum(r[5] for r in rows):.1f}s wall {time.perf_counter() - t0:.1f}s", flush=True)
    for r in bad[:5]:
        print("  MISMATCH", r[:4], r[7], r[8], flush=True)
    for r in slow:
        print(f"  slow {r[1]} {r[2]} n={r[3]} bounded {r[4]:.2f}s exact {r[5]:.2f}s", flush=True)
