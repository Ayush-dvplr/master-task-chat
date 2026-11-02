"""sha256 of gen_month output for the seeds the bundle uses (P2.1 byte-identical proof)."""
import hashlib
import random
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
from ref_core import ref_compute  # noqa: E402
from gen_core import gen_month  # noqa: E402

HIDDEN = 58213


def month(seed):
    rng = random.Random(seed)
    return "%04d-%02d" % (rng.choice((2027, 2028, 2029)), rng.randint(1, 12))


def digest(files):
    h = hashlib.sha256()
    for name in sorted(files):
        h.update(name.encode() + b"\0" + files[name] + b"\0")
    return h.hexdigest()


cases = [("shipped 461927", (461927, "2026-09", 3200, 2400, False)),
         ("hidden 58213", (HIDDEN, month(HIDDEN), 1600, 1200, True))]
for label, args in cases:
    print(label, digest(gen_month(*args, ref_compute)))
