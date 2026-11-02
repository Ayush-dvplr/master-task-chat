"""Per-project solve times on the non-lever books and the shipped book (Law-1 fix 25c745d).

Run inside the verifier image only:
  python -B /w/time_projects.py <tests/test_output.py> <package src dir> <mode> <label>
mode "pkg" times task.core.best_network of the package; mode "dw" times the kill-test
Dreyfus-Wagner solver (proto/solvers.dw_global) on the package's parsed projects.
Each project is capped at CAP seconds; after two caps the rest of that book is skipped.
Prints one JSON line per project: label, book, pid, cold rooms, sites, links, seconds.
"""
import importlib.util
import json
import os
import signal
import sys
import time
from pathlib import Path

CAP = int(os.environ.get("CAP", "12"))
BOOKS = tuple(os.environ.get("BOOKS", "shipped,fresh_1,fresh_2,fresh_3,rescaled,relocated").split(","))


class Cap(Exception):
    pass


def _alarm(_sig, _frm):
    raise Cap()


def main() -> None:
    tests, src, mode, label = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    spec = importlib.util.spec_from_file_location("tt", tests)
    tt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tt)
    sys.path.insert(0, src)
    from task import core, parser  # noqa: E402
    solve = core.best_network
    if mode == "dw":
        sys.path.insert(0, str(Path(__file__).resolve().parent / "proto"))
        import solvers  # noqa: E402

        def solve(project):
            proj = {"n": project.size, "charge": list(project.charges), "cold": set(project.cold),
                    "links": list(project.links)}
            return solvers.dw_global(proj)
    signal.signal(signal.SIGALRM, _alarm)
    for name in BOOKS:
        root = Path(sys.argv[5]) if name == "shipped" else tt._book(name)
        book = parser.load_book(root)
        caps = 0
        total = 0.0
        for pid, project in sorted(book["projects"].items()):
            row = {"label": label, "book": name, "pid": pid, "cold": len(project.cold),
                   "sites": project.size + 1, "links": len(project.links)}
            if caps >= int(os.environ.get("MAXCAPS", "2")):
                row["sec"] = "skip"
            else:
                signal.alarm(CAP)
                t0 = time.perf_counter()
                try:
                    solve(project)
                    row["sec"] = round(time.perf_counter() - t0, 3)
                    total += row["sec"]
                except Cap:
                    row["sec"] = ">%d" % CAP
                    caps += 1
                finally:
                    signal.alarm(0)
            print(json.dumps(row), flush=True)
        print(json.dumps({"label": label, "book": name, "projects": len(book["projects"]),
                          "budget": 4 * len(book["projects"]) + 10, "sum_sec": round(total, 2),
                          "caps": caps}), flush=True)
    print("ALL_DONE", label, flush=True)


if __name__ == "__main__":
    main()
