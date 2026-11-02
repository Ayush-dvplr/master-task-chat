import hashlib, os, sys
root = sys.argv[1]
ps = sorted(os.path.relpath(os.path.join(d, f), root) for d, _, fs in os.walk(root) for f in fs)
h = hashlib.sha256()
for p in ps:
    h.update((hashlib.sha256(open(os.path.join(root, p), 'rb').read()).hexdigest() + "  ./" + p + "\n").encode())
print(h.hexdigest()[:12])
