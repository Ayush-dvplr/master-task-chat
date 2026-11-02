"""G12: run gen_month on 300 fresh seeds (150 hidden-profile 1600/1200, 150 plain random sizes); report loops, asserts, time."""
import json
import multiprocessing
import random
import signal
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
from ref_core import ref_compute  # noqa: E402
from gen_core import gen_month  # noqa: E402


class Loop(Exception):
    pass


def _alarm(*_):
    raise Loop()


def one(case):
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(120)
    t0 = time.time()
    try:
        gen_month(case["seed"], case["month"], case["rows"], case["accts"], case["hidden"], ref_compute)
        status = "ok"
    except Loop:
        status = "LOOP (>120 s)"
    except AssertionError as e:
        status = "assert %s" % str(e)[:60]
    except Exception as e:  # report, do not hide
        status = "%s %s" % (type(e).__name__, str(e)[:60])
    finally:
        signal.alarm(0)
    return dict(case, status=status, secs=round(time.time() - t0, 1))


def main():
    rng = random.Random(25102026)
    cases = []
    for i in range(300):
        hidden = i < 150
        cases.append({"seed": rng.randrange(1, 10 ** 9),
                      "month": "%d-%02d" % (rng.choice((2027, 2028, 2029)), rng.randint(1, 12)),
                      "rows": 1600 if hidden else rng.randint(200, 2000),
                      "accts": 1200 if hidden else rng.randint(100, 1500), "hidden": hidden})
    with multiprocessing.Pool(int(sys.argv[2])) as pool:
        res = pool.map(one, cases)
    with open(sys.argv[3], "w") as fh:
        for r in res:
            fh.write(json.dumps(r) + "\n")
    tally = {}
    for r in res:
        key = ("hidden " if r["hidden"] else "plain ") + r["status"].split(" ")[0]
        tally[key] = tally.get(key, 0) + 1
    print(json.dumps(tally, sort_keys=True))
    print("max secs", max(r["secs"] for r in res))
    for r in res:
        if r["status"] != "ok":
            print(r["seed"], r["hidden"], r["status"])


if __name__ == "__main__":
    main()
