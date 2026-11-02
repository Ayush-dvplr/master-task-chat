"""sha256 of tests/test_output.py with the _BOOKS literal removed: python3 -B digest_checks.py FILE"""
import hashlib, sys
lines = open(sys.argv[1], encoding="utf-8").read().split("\n")
out, skip = [], False
for ln in lines:
    if ln.startswith("_BOOKS:"):
        skip = True
        continue
    if skip and (ln == "" or not ln.startswith(" ")):
        skip = False
    if not skip:
        out.append(ln)
print(hashlib.sha256("\n".join(out).encode()).hexdigest(), len(out))
