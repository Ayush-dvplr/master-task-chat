"""F1: write environment/data/bits/0x###_manifest.json: the unprefixed run resolved with one bit set."""
import json, os
import ref
m = ref.load()
D = ref.B + "/environment/data"
base = json.load(open(os.path.join(D, "manifest.json")))
corpus = m.load_corpus(D, "")
out = os.path.join(D, "bits"); os.makedirs(out, exist_ok=True)
for _, flag in sorted(m.MODE_BITS, key=lambda t: t[1]):
    c = dict(corpus); c["mode"] = flag
    r, p, b = m.resolve(c)
    man = {"run": base["run"], "mode": flag, "declared_reads": base["declared_reads"],
           "plate_digests": {pl: m.plate_digest(r, p, pl) for pl in sorted(corpus["plates"])},
           "run_digest": m.run_digest(r, p, b)}
    with open(os.path.join(out, "0x%03x_manifest.json" % flag), "w", encoding="utf-8", newline="") as h:
        h.write(json.dumps(man, sort_keys=True, indent=2) + "\n")
print(sorted(os.listdir(out)))
