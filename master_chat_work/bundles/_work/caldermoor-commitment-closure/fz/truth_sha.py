import hashlib, os, re, sys
B = sys.argv[1]; p = os.path.join(B, "solution/TRUTH.md"); s = open(p).read()
def h(path): return hashlib.sha256(open(os.path.join(B, path), "rb").read()).hexdigest()
def sub(m): return f"{h(m.group(2))}  {m.group(2)}"
s, n = re.subn(r"^([0-9a-f]{64})  (\S+)$", sub, s, flags=re.M)
d = os.path.join(B, "environment/data")
files = sorted((("./" + os.path.relpath(os.path.join(r, f), d)) for r, _, fs in os.walk(d) for f in fs if f != ".DS_Store"), key=lambda x: x.encode())
listing = "".join(f"{hashlib.sha256(open(os.path.join(d, f[2:]), 'rb').read()).hexdigest()}  {f}\n" for f in files)
dh = hashlib.sha256(listing.encode()).hexdigest()
s, m = re.subn(r"`[0-9a-f]{64}`\.\s*$", f"`{dh}`.\n", s)
s = re.sub(r"holds \d+ files", f"holds {len(files)} files", s)
open(p, "w").write(s); print("lines", n, "data", m, len(files), dh)
