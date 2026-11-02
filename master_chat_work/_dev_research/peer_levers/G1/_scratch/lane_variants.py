import sys, os, json, subprocess, tempfile
sys.path.insert(0, os.path.abspath("stub"))
T = sys.argv[1]; progs = sys.argv[2:]
sys.path.insert(0, os.path.join(T, "tests"))
import test_output as t
res = {}
for name in t.VARIANTS:
    d, exp = t._materialise(name)
    row = []
    for p in progs:
        o = tempfile.mkdtemp(prefix="lo-")
        r = subprocess.run([sys.executable, p, d, o], capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            row.append("CRASH:" + (r.stderr.strip().splitlines() or [""])[-1][:80]); continue
        bad = []
        for a in t.VALUE_ARTIFACTS:
            try: got = json.load(open(os.path.join(o, a)))
            except Exception: bad.append(a+"(missing)"); continue
            if got != exp[a]: bad.append(a)
        row.append("OK" if not bad else "DIFF(%d)" % len(bad))
    print(name.ljust(24), " | ".join(row), flush=True)
