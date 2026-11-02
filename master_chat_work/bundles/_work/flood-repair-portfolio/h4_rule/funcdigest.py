"""Per top-level block sha256 of a python file: python3 -B funcdigest.py FILE -> 'name sha12' lines."""
import hashlib, sys, re
lines = open(sys.argv[1], encoding="utf-8").read().split("\n")
blocks, name, buf = [], "<head>", []
for ln in lines:
    m = re.match(r"(def|class) (\w+)|(\w+)\s*(:[^=]*)?=", ln)
    if ln and not ln[0].isspace() and m and not ln.startswith(("@",)):
        blocks.append((name, buf)); name = m.group(2) or m.group(3); buf = []
    buf.append(ln)
blocks.append((name, buf))
seen = {}
for n, b in blocks:
    seen[n] = seen.get(n, 0) + 1
    key = n if seen[n] == 1 else "%s#%d" % (n, seen[n])
    print(key, hashlib.sha256("\n".join(b).strip().encode()).hexdigest()[:12])
