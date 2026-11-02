"""Score a delivered triage.py on the verifier's positive checks, locally (WORK helper).

usage: python3 -B score.py PROGRAM [tests_path]
Prints points per check and the total out of 90.
"""
import os, subprocess, sys, tempfile
import ref

prog = sys.argv[1]
m = ref.load(sys.argv[2]) if len(sys.argv) > 2 else ref.load()

checks = [("reusable_program_is_delivered", None, None, 0, 1),
          ("untrapped_run_alpha", m.BASE_SEEDS[0], 0, 0, 1),
          ("untrapped_run_beta", m.BASE_SEEDS[1], 0, 0, 1)]
for i, (name, flag) in enumerate(m.MODE_BITS):
    checks.append(("mode_bit_" + name, m.BIT_SEEDS[i], flag, 0, 1))
for j, i in enumerate((0, 2, 4, 6, 8, 10)):
    checks.append(("every_bit_except_" + m.MODE_BITS[i][0], m.EXCEPT_SEEDS[j], m.ALL_FLAGS & ~m.MODE_BITS[i][1], 0, 5))
for j, seed in enumerate(m.FULL_SEEDS):
    checks.append(("full_mode_run_" + "abcdefgh"[j], seed, m.ALL_FLAGS, 0, 5))
checks.append(("full_mode_run_with_a_grown_operator_table", m.ALIAS_SEED, m.ALL_FLAGS, getattr(m, "ALIAS_GROWTH", 0), 5))

total = 0
lost = []
for name, seed, mode, grow, weight in checks:
    if seed is None:
        ok = os.path.isfile(prog)
    else:
        root = tempfile.mkdtemp()
        data, out = os.path.join(root, "data"), os.path.join(root, "out")
        os.makedirs(data); os.makedirs(out)
        try:
            m.write_case(data, seed, mode, grow=grow)
        except TypeError:
            m.write_case(data, seed, mode)
        if name.endswith("grown_operator_table"):
            import csv
            with open(os.path.join(data, "operators.csv")) as h:
                count = sum(1 for _ in csv.DictReader(h))
            guard = 8 if getattr(m, "ALIAS_GROWTH", 0) else 5
            if not count > guard:
                ok = False
                print("%s guard failed (%d operators)" % (name, count))
        code = subprocess.run([sys.executable, "-B", prog, data, out], capture_output=True).returncode
        want = m._expected(data)
        ok = code == 0 and all(
            os.path.isfile(os.path.join(out, n)) and open(os.path.join(out, n), encoding="utf-8").read() == want[n]
            for n in m.REPORTS)
    total += weight if ok else 0
    if not ok:
        lost.append(name)
print("TOTAL %d/90" % total)
print("LOST " + ",".join(lost))
