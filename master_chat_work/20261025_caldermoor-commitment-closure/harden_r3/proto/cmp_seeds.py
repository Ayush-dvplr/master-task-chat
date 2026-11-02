"""oracle and N2 mutant vs tests reference on given seeds; prints differing artifacts. In verifier image."""
import os, shutil, subprocess, sys, tempfile
sys.path.insert(0, "/tests")
import test_output as T
GR = [a for a in T.ARTIFACTS if a != "reconcile.py"]
for s in sys.argv[1:]:
    tmp = tempfile.mkdtemp()
    data = os.path.join(tmp, "data"); ref = os.path.join(tmp, "ref")
    T._write_corpus(int(s), data) if hasattr(T, "_write_corpus") else None
    os.makedirs(ref); T.write_all(T.compute(data), ref)
    res = {}
    for lab in ("oracle", "mut_N2"):
        o = os.path.join(tmp, lab); os.makedirs(o)
        shutil.copy("/proto/%s/reconcile.py" % lab, os.path.join(tmp, lab + ".py"))
        subprocess.run([sys.executable, "-B", os.path.join(tmp, lab + ".py"), data, o], check=True, capture_output=True)
        res[lab] = [a for a in GR if open(os.path.join(ref, a), "rb").read() != open(os.path.join(o, a), "rb").read()]
    print(s, res, flush=True)
    shutil.rmtree(tmp)
