"""F1 measurement: per-bit plate moves vs mode 0 on shipped runs; permutation probe."""
import itertools, json, sys, copy
import ref
m = ref.load()
D = ref.B + "/environment/data"
def digests(corpus, mode):
    c = dict(corpus); c["mode"] = mode
    r, p, b = m.resolve(c)
    return {pl: m.plate_digest(r, p, pl) for pl in corpus["plates"]}, m.run_digest(r, p, b)
res = {}
for prefix in ("", "trial_"):
    c = m.load_corpus(D, prefix)
    zero, _ = digests(c, 0)
    full, fr = digests(c, 0xFFF)
    man = json.load(open(D + "/" + prefix + "manifest.json"))
    assert full == man["plate_digests"] and fr == man["run_digest"], prefix
    row = {}
    for name, flag in m.MODE_BITS:
        d, _ = digests(c, flag)
        row[name] = (hex(flag), sum(d[k] != zero[k] for k in d), len(d))
    res[prefix or "unprefixed"] = row
for name, flag in m.MODE_BITS:
    print(name, hex(flag), "unprefixed", res["unprefixed"][name][1], "/", res["unprefixed"][name][2],
          "trial_", res["trial_"][name][1], "/", res["trial_"][name][2])
