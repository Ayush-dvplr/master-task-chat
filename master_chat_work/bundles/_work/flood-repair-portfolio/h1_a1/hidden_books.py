"""python3 -B hidden_books.py OUTROOT: write the current hidden books H1 H2 H3 M (specs and digests
copied from tests/test_output.py:668-718), each checked against its pinned sha256."""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bookgen  # noqa: E402

BASE = {"audit_large": 60, "audit_small": 12, "blank_row": 50, "crews": 700, "faults": 12,
        "order": "shuffle", "permits": 600, "sites": 500, "small": 40, "ties": 8}
BOOKS = {
    "H1": (714301, "c7a56c8f6790f967fc4501c18bea03fc78678974b92a4096c6cd858dcbdf81c1", dict(BASE, large=[(156, 13), (160, 14)])),
    "H2": (721402, "cc365f439f1474685bc21f5351c7334f2aeef8fae00655273c77f84eb4af61c7", dict(BASE, large=[(148, 12), (160, 13)])),
    "H3": (731503, "47de663f0fc8077b862409731b49fd10d9229084205573f743d4bee37e627bac", dict(BASE, large=[(152, 14), (144, 12)])),
    "M": (742604, "d1fe9d3e98842248a27b8f1fc7f9a237e04f8ebe40427f5bde9fd2ea378010b2",
          {"audit_large": 60, "audit_small": 12, "crews": 700, "faults": 10, "large": [(150, 13)],
           "order": "shuffle", "permits": 600, "sites": 500, "small": 30, "ties": 6}),
}

for name, (seed, sha, spec) in BOOKS.items():
    files, _ = bookgen.make_book(seed, spec)
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    assert digest == sha, (name, digest)
    out = os.path.join(sys.argv[1], name)
    os.makedirs(out, exist_ok=True)
    for fname, text in files.items():
        with open(os.path.join(out, fname), "w") as fh:
            fh.write(text)
    print(name, "ok")
