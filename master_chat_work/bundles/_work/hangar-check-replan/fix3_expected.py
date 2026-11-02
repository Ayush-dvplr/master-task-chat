import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, sys.argv[1])
import test_output as T

digests = {}
for name in ["shipped", *T.HIDDEN, *T.FORMS, "m1", "m2"]:
    root = Path(tempfile.mkdtemp(prefix="fix3-expected-"))
    if name == "shipped":
        data = T._shipped_root(root)
        want = T.derive(str(data))
    elif name in T.HIDDEN or name in T.FORMS:
        data = root / "data"
        data.mkdir()
        if name in T.HIDDEN:
            seed, empty, stype, x1 = T.HIDDEN[name]
        else:
            seed, table, kind = T.FORMS[name]
            empty, stype, x1 = False, "bind", False
        _, want = T._planted_corpus(name, seed, empty, stype, x1, data)
        if name in T.FORMS:
            T._reform(data, table, kind)
    else:
        data = T._mutant_data(name, root)
        want = T.derive(str(data))
    blob = json.dumps(want, sort_keys=True, separators=(",", ":")).encode()
    digests[name] = hashlib.sha256(blob).hexdigest()
    print(name, digests[name], flush=True)
    shutil.rmtree(root)
Path(sys.argv[2]).write_text(json.dumps(digests, indent=2) + "\n")
print("EXPECTED_DONE", len(digests), flush=True)
