import json, sys, os
ref, got = sys.argv[1], sys.argv[2]
def first(a, b, p=""):
    if type(a) != type(b): return p or "/"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b: return p + "/" + k
            d = first(a[k], b[k], p + "/" + k)
            if d: return d
        return None
    if isinstance(a, list):
        for i, (x, y) in enumerate(zip(a, b)):
            d = first(x, y, "%s[%d]" % (p, i))
            if d: return d
        return None if len(a) == len(b) else p + "/len"
    return None if a == b else (p or "/")
kept = 0; out = []
names = sorted(os.listdir(ref))
for n in names:
    try:
        b = json.load(open(os.path.join(got, n)))
    except Exception as e:
        out.append("%s MISSING" % n); continue
    d = first(json.load(open(os.path.join(ref, n))), b)
    if d is None: kept += 1
    else: out.append("%s %s" % (n, d))
print("kept %d/%d" % (kept, len(names)), "; ".join(out)[:600])
