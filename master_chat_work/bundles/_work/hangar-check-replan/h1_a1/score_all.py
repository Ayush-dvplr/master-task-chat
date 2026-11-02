"""Score programs against the built tests module (Docker only, as root, /tests = BUNDLE tests).

usage: python3 -B score_all.py OUTLOG PROG.py [PROG.py ...]
Builds every held-out folder once (expected outputs from the reference), then for each program:
copies it to /app/out/derive_report.py, runs it on the shipped data into /app/out, reruns it on
every held-out and changed folder, and evaluates every registered criterion. One JSON line per
program, then ALL_DONE <n>. Optional env WITNESS=<dir>: save the FORMS folders there.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "/tests")
import test_output as T  # noqa: E402

SRC = Path("/tests/test_output.py").read_text(encoding="utf-8")
REGS = re.findall(r"def (\w+)\(workspace: Path\) -> bool:\n    return _holds\((.*)\)\n", SRC)
WEIGHTS = {n: int(w) for n, w in re.findall(r"criteria\.(\w+)\(weight=(-?\d+)\)", SRC)}
assert len(REGS) == len(WEIGHTS), (len(REGS), len(WEIGHTS))
NAMES = list(T.HIDDEN) + list(T.FORMS) + ["m1", "m2"]
POS = sum(w for w in WEIGHTS.values() if w > 0)


def install(prog):
    shutil.rmtree("/app/out", ignore_errors=True)
    os.makedirs("/app/out")
    shutil.copy(prog, "/app/out/derive_report.py")
    raw = Path(prog).parent.parent / "progs_raw"
    if raw.is_dir():
        shutil.rmtree("/app/progs_raw", ignore_errors=True)
        shutil.copytree(raw, "/app/progs_raw")
    os.system("chmod -R a+rX /app")


def rerun(name):
    case = T._CASES[name]
    if "want" not in case:
        return None
    root = case["data"].parent
    work = Path(tempfile.mkdtemp(prefix="hangar-run-"))
    case["stray"] = []
    case.pop("error", None)
    case.pop("got", None)
    t0 = time.time()
    with T._RUN_LOCK:
        root.chmod(0o755)
        try:
            case["got"] = T._run_program(case["data"], work, case["stray"])
        except Exception as exc:
            case["error"] = "%s: %s" % (type(exc).__name__, exc)
        finally:
            root.chmod(0o700)
            shutil.rmtree(work, ignore_errors=True)
    return round(time.time() - t0, 1)


def main():
    log, progs = sys.argv[1], sys.argv[2:]
    built = {}
    shipped = T._shipped_case()
    with open(log, "a") as fh:
        for prog in progs:
            install(prog)
            t0 = time.time()
            deliver = dict(x.split("=", 1) for x in os.environ.get("DELIVER", "").split(",") if x)
            if os.path.basename(prog) in deliver:  # outputs as the agent delivered them; no root run of a forking program
                for name in T.ARTIFACT_NAMES:
                    shutil.copy(os.path.join(deliver[os.path.basename(prog)], name), "/app/out/" + name)
                r = subprocess.CompletedProcess([], 0)
            else:
                r = subprocess.run(["python3", "/app/out/derive_report.py", str(shipped["data"]), "/app/out"],
                                   cwd="/app", capture_output=True, text=True, timeout=120)
            secs = {"shipped": round(time.time() - t0, 1)}
            for name in NAMES:
                if name not in T._CASES:
                    t1 = time.time()
                    T._build_case(name)
                    built[name] = round(time.time() - t1, 1)
                    secs[name] = None
                else:
                    secs[name] = rerun(name)
            verdict, pos, neg = {}, 0, []
            for crit, expr in REGS:
                ok = eval("_holds(%s)" % expr, T.__dict__)
                w = WEIGHTS[crit]
                verdict[crit] = "E" if ok else "W"
                m = re.search(r'"(h\d+|m\d)"', expr)
                if not ok and m and "error" in T._CASES.get(m.group(1), {}):
                    verdict[crit] = "C"
                if ok and w > 0:
                    pos += w
                if ok and w < 0:
                    neg.append(crit)
            errors = {n: T._CASES[n].get("error", "")[:160] for n in NAMES if "error" in T._CASES[n]}
            rec = {"prog": Path(prog).stem, "pos": pos, "of": POS, "pct": round(100.0 * pos / POS, 1),
                   "neg": neg, "shipped_rc": r.returncode, "secs": secs, "verdict": verdict, "errors": errors,
                   "build_secs": built}
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            print(rec["prog"], pos, POS, rec["pct"], neg, flush=True)
        wit = os.environ.get("WITNESS")
        if wit:
            for name in T.FORMS:
                dest = Path(wit) / name
                shutil.rmtree(dest, ignore_errors=True)
                shutil.copytree(T._CASES[name]["data"], dest / "data")
                (dest / "want.json").write_text(json.dumps(T._CASES[name]["want"], indent=1, sort_keys=True))
        fh.write("ALL_DONE %d\n" % len(progs))


main()
