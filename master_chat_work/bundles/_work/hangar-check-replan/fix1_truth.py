"""Fix1 (QC v1 DS-22): rewrite TRUTH.md count and probe lines from the shipped tests, then digests (run last)."""
import os
import re
import subprocess
import sys
import tomllib

W = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(os.path.dirname(os.path.dirname(W)), "hangar-check-replan")
src = open(os.path.join(B, "tests", "test_output.py")).read()
weights = [(n, int(w)) for n, w in re.findall(r"criteria\.(\w+)\(weight=(-?\d+)\)", src)]
pos = [(n, w) for n, w in weights if w > 0]
neg = [(n, w) for n, w in weights if w < 0]
crit = tomllib.load(open(os.path.join(B, "tests", "judge.toml"), "rb"))["criterion"]
jpos = [c for c in crit if c["weight"] > 0]
jneg = [c for c in crit if c["weight"] < 0]
probes = sum(c["weight"] for c in jpos if c["annotations"]["type"] == "agent behavior")
P, N = sum(w for _, w in pos), sum(w for _, w in neg)
JP, JN = sum(c["weight"] for c in jpos), sum(c["weight"] for c in jneg)
negs = ", ".join("`%s` (%d)" % (n, w) for n, w in neg)
PROBE = "the probe script `solution/solve.sh` writes to `/tmp/oracle_checks/probes.py`"

t = open(os.path.join(B, "solution", "TRUTH.md")).read()
new_a = ("- Channel A, `tests/test_output.py`: %d checks, positive weight total %d, negatives\n"
         "  %s. The program is run\n" % (len(weights), P, negs))
t, n1 = re.subn(r"- Channel A, `tests/test_output.py`: .*?\n  .*?The program is run\n", new_a, t, flags=re.S)
new_b = ("- Channel B, `tests/judge.toml`: %d positive criteria worth %d (nine process probes the oracle\n"
         "  shows in %s, plus error handling, malformed input, final-reply list, order of work,\n"
         "  final run) and %d negatives worth %d.\n" % (len(jpos), JP, PROBE, len(jneg), JN))
t, n2 = re.subn(r"- Channel B, `tests/judge.toml`: .*?and (four|\d+) negatives worth -?\d+\.\n", new_b, t, flags=re.S)
t, n3 = re.subn(r"weight 0\.5/\d+ on test_output, 0\.5/\d+ on judge\.",
                "weight 0.5/%d on test_output, 0.5/%d on judge." % (P, JP), t)
t, n4 = re.subn(r"runs it on `/app/data`, then runs\n(`solution/probes.py`|the probe script .*?probes.py`), which prints",
                "runs it on `/app/data`, then runs\n%s, which prints" % PROBE, t)
t, n5 = re.subn(r"The test channel carries \d+ positive checks worth \d+ weight and \d+ negative\n"
                r"  checks worth -?\d+ weight\. The judged channel carries \d+ positive criteria\n"
                r"  worth \d+ points and \d+ negatives worth -?\d+\.",
                "The test channel carries %d positive checks worth %d weight and %d negative\n"
                "  checks worth %d weight. The judged channel carries %d positive criteria\n"
                "  worth %d points and %d negatives worth %d." % (len(pos), P, len(neg), N, len(jpos), JP,
                                                                len(jneg), JN), t)
assert (n1, n2, n3, n4, n5) == (1, 1, 1, 1, 1), (n1, n2, n3, n4, n5)
assert probes == 27, probes
open(os.path.join(B, "solution", "TRUTH.md"), "w").write(t)
print("TRUTH counts", len(weights), P, N, len(jpos), JP, JN, "probes", probes)
subprocess.run([sys.executable, "-B", os.path.join(W, "truth_sha.py")], check=True)
