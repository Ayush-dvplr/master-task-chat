"""Time one solver on every problem of a JSON dump, per-problem alarm. Usage: bench.py SOLVER PROBLEMS.json [LIMIT_S]"""
import json
import signal
import sys
import time

sys.dont_write_bytecode = True
import solvers  # noqa: E402


class Late(Exception):
    pass


def _alarm(*_):
    raise Late()


if __name__ == "__main__":
    name, path = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 120
    fn = solvers.SOLVERS[name]
    import os
    TOTAL_MODE = os.environ.get("TOTAL") == "1"
    signal.signal(signal.SIGALRM, _alarm)
    out = []
    total = 0.0
    for p in json.load(open(path)):
        t0 = time.time()
        left = int(limit - total) if TOTAL_MODE else limit
        if left <= 0:
            print("OVER_TOTAL", flush=True)
            break
        signal.alarm(left)
        try:
            key, ways, ids = fn(p)
            res = {"key": list(key) if key else None, "ways": ways, "ids": list(ids)}
        except Late:
            res = {"late": True}
        signal.alarm(0)
        res["s"] = round(time.time() - t0, 3)
        res["er"] = p["er"]
        res["sites"] = len(p["lanes"])
        total += res["s"]
        out.append(res)
        res["nodes"] = solvers.NODES[0]
        solvers.NODES[0] = 0
        print(res["sites"], res["s"], res.get("late"), res.get("ways"), res.get("key"), len(res.get("ids", [])), "nodes", res["nodes"], flush=True)
    print("TOTAL", round(total, 2))
    if len(sys.argv) > 4:
        json.dump(out, open(sys.argv[4], "w"))
