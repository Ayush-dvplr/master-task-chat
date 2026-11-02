"""Permutation probe: rotate/swap FLAG_* in a copy of the reference; count shipped digests failed.
Usage: probe.py [bitsdir]  (bitsdir holds the single-bit manifests; absent -> 0xfff manifests only)"""
import itertools, json, os, sys
import ref
m = ref.load()
D = ref.B + "/environment/data"
names = ["FLAG_" + n.upper() for n, _ in m.MODE_BITS]
orig = [getattr(m, n) for n in names]
shipped = []  # (prefix, manifest dict)
for prefix in ("", "trial_"):
    shipped.append((prefix, json.load(open(os.path.join(D, prefix + "manifest.json")))))
bdir = sys.argv[1] if len(sys.argv) > 1 else None
if bdir:
    for f in sorted(os.listdir(bdir)):
        shipped.append(("", json.load(open(os.path.join(bdir, f)))))
corp = {p: m.load_corpus(D, p) for p in ("", "trial_")}
def fails(assign):
    for n, v in zip(names, assign): setattr(m, n, v)
    bad = 0
    for prefix, man in shipped:
        c = dict(corp[prefix]); c["mode"] = man["mode"]
        r, p, b = m.resolve(c)
        d = {pl: m.plate_digest(r, p, pl) for pl in c["plates"]}
        bad += sum(d[k] != man["plate_digests"][k] for k in d) + (m.run_digest(r, p, b) != man["run_digest"])
    for n, v in zip(names, orig): setattr(m, n, v)
    return bad
print("identity", fails(orig))
rot = [fails(orig[k:] + orig[:k]) for k in range(1, 12)]
print("rotations failing digests:", rot, "all>0:", all(x > 0 for x in rot))
sw = []
for i, j in itertools.combinations(range(12), 2):
    a = list(orig); a[i], a[j] = a[j], a[i]; sw.append(fails(a))
print("swaps min failing:", min(sw), "zero-count swaps:", sum(x == 0 for x in sw), "of", len(sw))
