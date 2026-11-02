"""diffout.py <ref_dir> <got_dir>: compare every json report whole, print first differing path."""
import json, sys
from pathlib import Path


def first_diff(a, b, p=""):
    if type(a) != type(b):
        return p or "/"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return f"{p}/{k}"
            d = first_diff(a[k], b[k], f"{p}/{k}")
            if d:
                return d
        return None
    if isinstance(a, list):
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, f"{p}/{i}")
            if d:
                return d
        return f"{p}/len" if len(a) != len(b) else None
    return None if a == b else (p or "/")


ref, got = Path(sys.argv[1]), Path(sys.argv[2])
ok = 0
names = sorted(x.name for x in ref.glob("*.json"))
for n in names:
    g = got / n
    if not g.exists():
        print(f"  {n}: MISSING")
        continue
    ra, ga = ref.joinpath(n).read_bytes(), g.read_bytes()
    if ra == ga:
        ok += 1
        continue
    d = first_diff(json.loads(ra), json.loads(ga))
    print(f"  {n}: DIFF {d if d else '(bytes only)'}")
print(f"DIFF {got} exact {ok}/{len(names)}")
