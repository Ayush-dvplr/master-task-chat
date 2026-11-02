import os, sys, time, importlib.util, json
sys.path.insert(0, "rewardkit_stub")
os.environ.setdefault("APP_ROOT", "/tmp/tariff-15b380e/app")
spec = importlib.util.spec_from_file_location("t", "../../tariff-engine-audit-repair/tests/test_output.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
for corpus in sys.argv[1:] or ["fresh"]:
    t = time.time()
    texts, labels = m._quiet_corpus(corpus)
    from collections import Counter
    print(corpus, round(time.time()-t,1), "s", Counter(tuple(sorted(v)) for v in labels.values()))
