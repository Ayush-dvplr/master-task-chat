"""Run solution/solve.py on generated months and compare with ref_compute (scratch)."""
import json, pathlib, random, subprocess, sys, tempfile
sys.dont_write_bytecode = True
WORK, SOLVE = sys.argv[1], sys.argv[2]
sys.path.insert(0, WORK)
from ref_core import ref_compute
from gen_core import gen_month

def month(seed):
    rng = random.Random(seed)
    return "%04d-%02d" % (rng.choice((2027, 2028, 2029)), rng.randint(1, 12))

cases = [(461927, "2026-09", 3200, 2400, False), (58213, month(58213), 1600, 1200, True)]
cases += [(s, month(s), 1600, 1200, True) for s in map(int, sys.argv[3:])]
for args in cases:
    files = gen_month(*args, ref_compute)
    exp = ref_compute(files)
    with tempfile.TemporaryDirectory() as d:
        inp, out = pathlib.Path(d, "in"), pathlib.Path(d, "out")
        inp.mkdir()
        for n, b in files.items():
            (inp / n).write_bytes(b)
        rc = subprocess.run([sys.executable, SOLVE, "--input", str(inp), "--output", str(out)]).returncode
        bad = []
        for name, doc in exp.items():
            if name == "normalized.jsonl":
                got = [json.loads(l) for l in (out / name).read_text().splitlines()]
            else:
                got = json.loads((out / name).read_text())
            if got != doc:
                bad.append(name)
    print(args[:2], "rc", rc, "differs", bad)
