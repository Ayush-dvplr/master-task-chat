"""prof_build.py seed:scale:variant:hr:start ... -> phase seconds of build()."""
import sys, time, cProfile, pstats, io
from pathlib import Path
import load_t
t = load_t.load("/w/proto_ref/test_output.py")
for spec in sys.argv[1:]:
    p = spec.split(":")
    conv = dict(hr=p[3].replace("=", ":"), start=p[4])
    root = Path("/tmp/pb_" + p[0] + p[1]); root.mkdir()
    t0 = time.time(); g = t.generate(root, int(p[0]), float(p[1]), p[2]); t1 = time.time()
    t.attest_from_reference(root, g, int(p[0])); t2 = time.time()
    pr = cProfile.Profile(); pr.enable(); t.observe(root, g, int(p[0]), conv); pr.disable(); t3 = time.time()
    D = t.load(root); cfg, _, _ = t.settle_config(D)
    t4 = time.time(); [t.World(D, cfg, conv) for _ in range(5)]; t5 = time.time()
    print(f"## {spec} generate {t1-t0:.1f}s attest {t2-t1:.1f}s observe {t3-t2:.1f}s world {(t5-t4)/5:.3f}s", flush=True)
    s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(25); print(s.getvalue()[:5000])
