"""Master point 2: per-night and per-book optimiser time (run inside python:3.12-slim).

usage: python3 -B timing.py <program.py> <label> [cap_seconds]
Writes the hidden books with bookgen, imports the program as a module and times best_plan on every
accepted night (each night capped by SIGALRM at cap_seconds, default 60), then the whole program
run per book. Prints one line per night and per book, then ALL_DONE.
"""
import importlib.util
import json
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bookgen  # noqa: E402

SIZES = {"H1": (400, 300, 61), "H2": (500, 350, 200), "H3": (450, 320, 400), "M": (300, 250, 30)}


class Cap(Exception):
    pass


def _alarm(signum, frame):
    raise Cap()


def main():
    program, label = sys.argv[1], sys.argv[2]
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    spec = importlib.util.spec_from_file_location("prog", program)
    prog = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prog)
    meta = json.loads((HERE / "hidden_meta.json").read_text())
    signal.signal(signal.SIGALRM, _alarm)
    for name in ("H1", "H2", "H3"):
        m = meta[name]
        clients, sites, start = SIZES[name]
        files = bookgen.make_book(m["seed"], m["specs"], m["attempts"], clients, sites, tuple(m["thresholds"]), start)
        with tempfile.TemporaryDirectory() as td:
            data = Path(td) / "data"
            data.mkdir()
            for fn, text in files.items():
                (data / fn).write_text(text)
            book = prog.Book(data)
            rows_of = {}
            for r in book.job_rows:
                rows_of.setdefault(r["night_id"], []).append(r)
            holding = {b["bay_id"]: b["initial_family"] for b in book.bays}
            worst = 0.0
            for night in book.nights:
                nid = night["id"]
                rows = rows_of.get(nid, [])
                if prog.rejection(book, nid, rows):
                    continue
                jobs = []
                for r in rows:
                    s, e = book.windows[r["window_id"]]
                    jobs.append({"job_id": r["job_id"], "start": s, "end": e, "family": r["family"],
                                 "value": int(r["value"]), "client_id": r["client_id"]})
                t0 = time.perf_counter()
                signal.alarm(cap)
                try:
                    plan = prog.best_plan(book, nid, jobs, holding)
                    signal.alarm(0)
                    dt = time.perf_counter() - t0
                    status = "ok"
                except Cap:
                    dt, status, plan = float(cap), "capped", None
                worst = max(worst, dt)
                print("%s %s night %s jobs %d %.2fs %s" % (label, name, nid, len(jobs), dt, status), flush=True)
                if plan is None:
                    break
                fam = dict(holding)
                for j in sorted((j for j in jobs if j["job_id"] in plan), key=lambda j: (j["start"], j["job_id"])):
                    fam[plan[j["job_id"]]] = j["family"]
                holding = fam
            t0 = time.perf_counter()
            try:
                proc = subprocess.run([sys.executable, "-B", program, str(data), str(Path(td) / "out")],
                                      capture_output=True, timeout=cap * len(book.nights))
                whole = "%.2fs exit %d" % (time.perf_counter() - t0, proc.returncode)
            except subprocess.TimeoutExpired:
                whole = "over %ds" % (cap * len(book.nights))
            print("%s %s book nights %d worst_night %.2fs whole_run %s" % (label, name, len(book.nights), worst, whole),
                  flush=True)
    print("ALL_DONE")


if __name__ == "__main__":
    main()
