"""Dump every non-lazy search call (as plain tuples) of the named roots, with bounded's answer, to p12q2/calls_<root>.pkl."""
import importlib.util
import pickle
import sys
import time
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
BUNDLE = WORK.parent.parent / "district-heat-flex-procurement"
sys.path.insert(0, str(WORK / "stub"))
src = (BUNDLE / "tests" / "test_output.py").read_text()
old = "                solver = search if lazy & SEARCH_FLAGS else bounded\n"
src = src.replace(old, "                solver = search if lazy & SEARCH_FLAGS else _REC(bounded, eid, region, root, tk, segment_names)\n")
src = src.replace("_SEARCH_MEMO: ", "CALLS = []\n_SEARCH_MEMO: ", 1)
src += '''

def _REC(fn, eid, region, root, tk, segs):
    def run(cands, goals, caps, floors_here, cw, vw, width):
        t0 = time.perf_counter()
        out = fn(cands, goals, caps, floors_here, cw, vw, width)
        plain = [(o["site"]["sid"], o["id"], o["cost"], tuple(tk(x) for x in o["r"]), tuple(tk(x) for x in o["v"]),
                  o["site"]["segment"]) for o in cands]
        CALLS.append(dict(root=str(root).rsplit("/", 1)[-1], eid=eid, region=region, cands=plain, goals=goals,
                          caps=caps, floors=floors_here, cw=cw, vw=vw, width=width, segs=list(segs), want=out,
                          secs=time.perf_counter() - t0))
        return out
    return run
'''
path = WORK / "p12q2" / "_dump_patched.py"
path.write_text(src)
spec = importlib.util.spec_from_file_location("tq", path)
tq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tq)
for name in sys.argv[1:]:
    start = len(tq.CALLS)
    if name == "shipped":
        tq.expected(tq.visible_root())
    elif name in ("H1", "H2"):
        tq.expected(tq.hidden_root(name))
    else:
        tq.expected(tq.wide_root(int(name[-1]))[0])
    rows = tq.CALLS[start:]
    (WORK / "p12q2" / f"calls_{name}.pkl").write_bytes(pickle.dumps(rows))
    print(name, len(rows), f"{sum(r['secs'] for r in rows):.1f}s", flush=True)
