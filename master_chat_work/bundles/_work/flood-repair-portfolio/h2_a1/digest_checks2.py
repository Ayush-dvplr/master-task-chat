"""sha256 of tests/test_output.py without the _BOOKS literal, the launcher helpers
(_launch, _stop_untrusted) and the two imports they use: python3 -B digest_checks2.py FILE"""
import hashlib
import sys

lines = open(sys.argv[1], encoding="utf-8").read().split("\n")
out, skip = [], False
for ln in lines:
    if ln in ("import signal", "import time"):
        continue
    if ln.startswith("_BOOKS:") or ln.startswith("def _launch(") or ln.startswith("def _stop_untrusted("):
        skip = True
        continue
    if skip and ln != "" and not ln.startswith(" "):
        skip = False
    if not skip:
        out.append(ln)
print(hashlib.sha256("\n".join(out).encode()).hexdigest(), len(out))
