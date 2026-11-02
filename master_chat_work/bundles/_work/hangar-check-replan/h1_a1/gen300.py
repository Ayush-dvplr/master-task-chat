"""G12 for the held-out Word forms: 300 seeds per form through corpus + _reform (Docker, /tests = BUNDLE tests).

usage: python3 -B gen300.py OUTLOG [N]
_reform asserts: the table has data rows, the form keeps every value (text undo equals the plain part),
the part parses, and the row-by-row reading of the plain package differs. One line per form, then ALL_DONE.
"""
import json
import multiprocessing as mp
import shutil
import sys
import tempfile
import time

sys.path.insert(0, "/tests")
import test_output as T  # noqa: E402


def one(args):
    name, i = args
    seed, table, kind = T.FORMS[name]
    s = 2000000 + 1000 * seed + i
    d = tempfile.mkdtemp(prefix="g300-")
    try:
        T.corpus("hidden", s, 8, False, "bind", False, d)
        T._reform(d, table, kind)
        return name, "ok", ""
    except Exception as exc:
        return name, "fail", "%d %s: %s" % (s, type(exc).__name__, exc)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    log, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 300
    jobs = [(name, i) for name in T.FORMS for i in range(n)]
    t0 = time.time()
    res = {}
    with mp.Pool(2) as pool:
        for name, verdict, why in pool.imap_unordered(one, jobs, chunksize=4):
            r = res.setdefault(name, {"ok": 0, "fail": 0, "why": []})
            r[verdict] += 1
            if why and len(r["why"]) < 3:
                r["why"].append(why)
    with open(log, "w") as fh:
        for name in T.FORMS:
            fh.write(json.dumps(dict(form=name, spec=T.FORMS[name], **res[name])) + "\n")
        fh.write("ALL_DONE %d seconds %.0f\n" % (len(jobs), time.time() - t0))


main()
