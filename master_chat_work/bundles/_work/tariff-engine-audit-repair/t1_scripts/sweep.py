import sys, importlib.util, time
sys.path.insert(0, "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/tariff-engine-audit-repair/rewardkit_stub")
spec = importlib.util.spec_from_file_location("t", "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/tariff-engine-audit-repair/tests/test_output.py")
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
bases = {c: t._base_texts(c) for c in t._HIDDEN}
ok = fail = 0; t0=time.time()
for i in range(300):
    c = t._HIDDEN[i % 7]
    try:
        t._quiet(bases[c], 1000 + i); ok += 1
    except Exception as e:
        fail += 1; print("FAIL", i, c, repr(e)[:200])
print("sweep", ok, "ok", fail, "fail", round(time.time()-t0,1), "s"); print("ALL_DONE")
