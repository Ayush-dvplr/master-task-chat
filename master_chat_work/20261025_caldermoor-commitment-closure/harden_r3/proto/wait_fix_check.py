import os, sys, shutil, subprocess, tempfile, json
sys.path.insert(0, "/tests")
import test_output as T
for seed in [int(s) for s in sys.argv[1:]]:
    tmp = tempfile.mkdtemp()
    try:
        data = os.path.join(tmp, "data")
        T._write_corpus(seed, data)
        st = T.compute(data)
        parted = T._wait_months(st)
        ref = os.path.join(tmp, "ref"); os.makedirs(ref); T.write_all(st, ref)
        res = {}
        for lab in ("oracle", "mut_N2"):
            out = os.path.join(tmp, lab); os.makedirs(out)
            p = subprocess.run([sys.executable, "-B", "/proto/%s/reconcile.py" % lab, data, out], capture_output=True)
            res[lab] = [n for n in sorted(os.listdir(ref)) if open(os.path.join(ref, n), "rb").read() != open(os.path.join(out, n), "rb").read()] if p.returncode == 0 else ("rc", p.returncode, p.stderr[-300:])
        added = sum(1 for l in open(os.path.join(data, T.WAIT_EDGE_FEED)) if l.startswith("EDG-9"))
        print(seed, "added", added, "parted", len(parted), json.dumps(res))
    except AssertionError as e:
        print(seed, "ASSERT", e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
