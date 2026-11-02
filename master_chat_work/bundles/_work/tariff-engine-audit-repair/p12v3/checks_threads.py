"""checks_wtc with rewardkit's thread pool, plus a count of statement/ledger children.

    THREADS=8 TESTS=<test_output.py> python3 -B checks_threads.py APP_ROOT OUT_JSON

rewardkit 0.2.1 runs programmatic checks through asyncio.to_thread under a semaphore of 8
(--max-concurrent-programmatic default); THREADS=8 reproduces that pool. Every
`--statements` / `--ledger` child is counted per data path with its wall time.
"""
import importlib.util, json, os, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK / "ql1"))
from checks_wtc import BUNDLE, run_key  # noqa: E402

CHILDREN, LOCK = [], threading.Lock()
_real_run = subprocess.run


def counted(real):
    def run(command, *args, **kwargs):
        return counted_call(real, command, *args, **kwargs)
    return run


def counted_run(command, *args, **kwargs):
    return counted_call(_real_run, command, *args, **kwargs)


def counted_call(real, command, *args, **kwargs):
    flag = next((f for f in ("--statements", "--ledger") if isinstance(command, list) and f in command), None)
    if flag is None:
        return real(command, *args, **kwargs)
    data = Path(command[command.index(flag) + 1])
    # scratch dirs are mkdtemp(prefix=...) + 8 random chars, so one memo key = one prefix
    path = data.parent.name[:-8] if data.name == "data" else str(data)
    started = time.time()
    outcome = "ok"
    try:
        result = real(command, *args, **kwargs)
        outcome = "rc%d" % result.returncode
        return result
    except subprocess.TimeoutExpired:
        outcome = "timeout"
        raise
    finally:
        with LOCK:
            CHILDREN.append({"flag": flag, "path": path, "sec": round(time.time() - started, 2),
                             "outcome": outcome})


def main():
    app, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
    threads = int(os.environ.get("THREADS", "8"))
    tests = Path(os.environ.get("TESTS", BUNDLE / "tests" / "test_output.py"))
    os.environ["APP_ROOT"] = str(app)
    sys.path.insert(0, str(WORK / "rewardkit_stub"))
    subprocess.run = counted_run
    spec = importlib.util.spec_from_file_location("bundle_tests", tests)
    t = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(t)
    if hasattr(t, "_group_run"):  # deb4e4a: agent children start through _group_run (Popen), not subprocess.run
        t._group_run = counted(t._group_run)
    weights = dict(sys.modules["rewardkit"].REGISTERED)

    def one(name):
        started = time.time()
        try:
            value = bool(getattr(t, name)(app))
        except Exception as error:  # a raising check is a verifier error; record it, never hide it
            return name, False, "RAISED %r" % error, round(time.time() - started, 2)
        return name, value, "", round(time.time() - started, 2)

    started = time.time()
    with ThreadPoolExecutor(max_workers=threads) as pool:
        rows = list(pool.map(one, list(weights)))
    wall = round(time.time() - started, 1)
    results, earned = {}, 0
    for name, value, note, sec in rows:
        weight = weights[name]
        cls = note
        if not value and weight > 0 and not note:
            cls = "WRONG"
            key = run_key(name)
            if key:  # memoised: re-raises the remembered failure, starts no child
                kind, corpus = key
                try:
                    if kind == "ledger":
                        t._ledger_run(corpus)
                    elif kind == "statement":
                        t._statement_run(corpus)
                    else:
                        t._statement_run(f"{kind}:{corpus}")
                except AssertionError as error:
                    cls = "TIMEOUT" if "no statements within" in str(error) else "CRASH"
                except Exception:
                    cls = "CRASH"
        results[name] = {"pass": value, "weight": weight, "class": cls, "sec": sec}
        earned += weight if value else 0
    positive = sum(w for w in weights.values() if w > 0)
    split = {c: sum(r["weight"] for r in results.values() if r["class"] == c) for c in ("WRONG", "TIMEOUT", "CRASH")}
    paths = sorted({c["path"] for c in CHILDREN})
    children = {"children": len(CHILDREN), "keys": len(paths),
                "slowest": max((c["sec"] for c in CHILDREN), default=0.0),
                "timeouts": sum(c["outcome"] == "timeout" for c in CHILDREN), "list": CHILDREN}
    out.write_text(json.dumps({"score": earned / positive, "earned": earned, "positive": positive, "split": split,
                               "threads": threads, "tests": str(tests), "wall": wall, "children": children,
                               "checks": results}, indent=1))
    print("SCORE %.4f" % (earned / positive), split, "children", children["children"], "keys", children["keys"],
          "slowest", children["slowest"], "timeouts", children["timeouts"], "wall", wall)


if __name__ == "__main__":
    main()
