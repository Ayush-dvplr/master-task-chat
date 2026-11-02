import os, sys, time, importlib.util, random, traceback
sys.path.insert(0, "rewardkit_stub")
os.environ.setdefault("APP_ROOT", "/tmp/tariff-15b380e/app")
spec = importlib.util.spec_from_file_location("t", "../../tariff-engine-audit-repair/tests/test_output.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
fails = {}
orig = m._assert_levers
def wrapped(*a):
    try:
        return orig(*a)
    except AssertionError as e:
        tb = traceback.extract_tb(e.__traceback__)[-1]
        fails[(tb.lineno, str(e)[:60])] = fails.get((tb.lineno, str(e)[:60]), 0) + 1
        raise
m._assert_levers = wrapped
orig_once = m._levers_once
def once(*a):
    try:
        return orig_once(*a)
    except AssertionError as e:
        tb = traceback.extract_tb(e.__traceback__)[-1]
        k = ("once", tb.lineno, str(e)[:60]); fails[k] = fails.get(k, 0) + 1
        raise
m._levers_once = once
mode = sys.argv[1]
if mode == "corpora":
    for c in ["fresh","rescaled","relocated","rotated","api","recoded","renamed"]:
        t=time.time(); m._quiet_corpus(c); print(c, round(time.time()-t,1))
else:
    n = int(sys.argv[2]); ok = bad = 0
    texts, labels = m._quiet(m._base_texts("fresh"), 740213)
    for seed in range(n):
        try:
            m._levers(texts, labels, 10000 + seed); ok += 1
        except Exception as e:
            bad += 1; print("FAIL", seed, type(e).__name__, str(e)[:100])
    print("ok", ok, "bad", bad)
print("assert fails:", sorted(fails.items(), key=lambda x: -x[1])[:15])
