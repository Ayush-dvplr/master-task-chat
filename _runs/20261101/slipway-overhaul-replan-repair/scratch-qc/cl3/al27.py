import sys, time
sys.path.insert(0, sys.argv[1])
import importlib.util
spec = importlib.util.spec_from_file_location("t", sys.argv[2] + "/test_output.py")
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
base = t._reference(t.SAMPLE_SEED)
for r in sorted(t.WITHDRAWN_RULES):
    s = time.time()
    w = t._reference(t.SAMPLE_SEED, (r,))
    moved = [k for k in base if base[k] != w.get(k)]
    print(r, len(moved), moved[:6], round(time.time()-s,1), flush=True)
