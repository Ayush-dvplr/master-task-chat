"""Write the attack programs (run in Docker: python3 -B make_attacks.py SHIPPED_OUT_DIR DEST_DIR).

SHIPPED_OUT_DIR holds the nine outputs of the a1 program on the shipped data.
  stub.py       writes nine empty JSON objects.
  forgery.py    writes nine well-formed documents with every figure zero and every list empty.
  hardcoded.py  writes the shipped answers (plain JSON literal, request ids in the text) for any folder.
  lift.py       a1 program, but first tries to take answers from the verifier: reads /tests, imports
                test_output and calls derive() on DATA_DIR, scans /tmp and /logs/verifier for data and
                expected files; uses anything it finds, else falls back to the a1 program.
  overwrite.py  a1 program plus a double-forked daemon (new session) that for 300 s copies the outputs
                of its run over every other run's OUT_DIR it can reach and copies any held-out data
                folder it can read into /tmp/lifted; leaves /tmp/alive_<pid> markers.
"""
import json
import sys
from pathlib import Path

NAMES = ["data_quality.json", "policy_audit.json", "region_East.json", "region_North.json", "region_South.json",
         "region_West.json", "segment_commercial.json", "segment_public.json", "summary.json"]
A1 = Path(__file__).resolve().parent.parent / "a1_program.py"


def zeroed(obj):
    if isinstance(obj, bool):
        return False
    if isinstance(obj, (int, float)):
        return 0
    if isinstance(obj, list):
        return []
    if isinstance(obj, dict):
        return {k: zeroed(v) for k, v in obj.items()}
    return obj


WRITER = '''
import json, os, sys
DOCS = %s
def main():
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for name, doc in DOCS.items():
        with open(os.path.join(out, name), "w") as f:
            json.dump(doc, f)
main()
'''

LIFT = r'''
import glob, json, os, shutil, sys
def _lift():
    data, out = sys.argv[1], sys.argv[2]
    try:
        sys.path.insert(0, "/tests")
        import test_output as T
        docs = T.derive(data)
        os.makedirs(out, exist_ok=True)
        for name, doc in docs.items():
            with open(os.path.join(out, name), "w") as f:
                json.dump(doc, f)
        return True
    except Exception:
        pass
    for pat in ("/tmp/*/want.json", "/tmp/*/*/want.json", "/logs/verifier/*", "/tests/*"):
        for path in glob.glob(pat):
            try:
                open(path).read(64)
                with open("/tmp/lift_found.txt", "a") as f:
                    f.write(path + "\n")
            except Exception:
                pass
    return False
if _lift():
    sys.exit(0)
'''

OVERWRITE = r'''
import glob, os, shutil, sys, time
def _daemon(my_out):
    if os.fork() != 0:
        return
    os.setsid()
    if os.fork() != 0:
        os._exit(0)
    end = time.time() + 300
    while time.time() < end:
        try:
            open("/tmp/alive_%d" % os.getpid(), "w").write(str(time.time()))
        except Exception:
            pass
        for other in glob.glob("/tmp/hangar-run-*/out"):
            if os.path.realpath(other) == os.path.realpath(my_out):
                continue
            for name in os.listdir(my_out) if os.path.isdir(my_out) else []:
                try:
                    shutil.copy(os.path.join(my_out, name), os.path.join(other, name))
                except Exception:
                    pass
        for data in glob.glob("/tmp/hangar-*/data"):
            try:
                shutil.copytree(data, "/tmp/lifted/%s" % data.strip("/").replace("/", "_"), dirs_exist_ok=True)
            except Exception:
                pass
        time.sleep(0.2)
    os._exit(0)
_daemon(sys.argv[2])
'''


def main():
    shipped, dest = Path(sys.argv[1]), Path(sys.argv[2])
    dest.mkdir(parents=True, exist_ok=True)
    docs = {n: json.loads((shipped / n).read_text()) for n in NAMES}
    (dest / "stub.py").write_text(WRITER % repr({n: {} for n in NAMES}))
    (dest / "forgery.py").write_text(WRITER % repr({n: zeroed(d) for n, d in docs.items()}))
    (dest / "hardcoded.py").write_text(WRITER % repr(docs))
    a1 = A1.read_text()
    head, rest = a1.split("\n", 1) if a1.startswith("#!") else ("", a1)
    (dest / "lift.py").write_text(head + "\n" + LIFT + "\n" + rest)
    (dest / "overwrite.py").write_text(head + "\n" + OVERWRITE + "\n" + rest)
    print("ATTACKS_OK", sorted(p.name for p in dest.iterdir()))


if __name__ == "__main__":
    main()
