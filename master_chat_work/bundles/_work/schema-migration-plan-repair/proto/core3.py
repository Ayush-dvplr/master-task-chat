"""Scratch (gate v3.6 harden f0331ad): prototype of the added large-graph worlds.

Same generator family as world_29..36 (`_g_core` in test_output.src.py), own RNG stream (BASE + number),
zone out-degree DEGREE, plus one extra guard: skip a draw whose edge count passes the 6,000 limit.

    python3 -B core3.py gen OUT FIRST LAST BASE DEGREE   # writes OUT/world_NN/{contract files, case.json}
    python3 -B core3.py seeds COUNT BASE DEGREE          # shape assert over COUNT draws
"""

from __future__ import annotations

import inspect
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core2  # noqa: E402

T = core2.T


def variant(base: int, degree: int):
    src = inspect.getsource(T._g_core)
    src = src.replace("def _g_core(w: _World, number: int)", "def _g_core_v(w, number)")
    src = src.replace("rng = _rng(5000 + number)", f"rng = _rng({base} + number)")
    src = src.replace("            for _ in range(4):\n", f"            for _ in range({degree}):\n")
    src = src.replace("        rng.shuffle(edges)\n", "        if len(edges) > 6000:\n            continue\n        rng.shuffle(edges)\n")
    assert src.count(f"range({degree})") >= 1 and "6000:\n            continue" in src
    ns = dict(vars(T))
    exec(compile(src, "g_core_v", "exec"), ns)
    return ns["_g_core_v"]


def world(index: int, base: int, degree: int):
    w = T._World(100 + index - 1, ("CORE",))
    variant(base, degree)(w, index)
    return w.finish()


def main() -> None:
    mode = sys.argv[1]
    if mode == "gen":
        out, first, last, base, degree = Path(sys.argv[2]), *map(int, sys.argv[3:7])
        for index in range(first, last + 1):
            spec, lines, *_ = world(index, base, degree)
            folder = out / f"world_{index:02d}"
            folder.mkdir(parents=True, exist_ok=True)
            root = spec.write()
            for f in root.iterdir():
                (folder / f.name).write_text(f.read_text())
            rows = []
            for doc in lines:
                t = time.time()
                plan = core2._bounded_plan(spec, doc["schema"], doc["payload"])
                rows.append({"start": doc["schema"], "payload": doc["payload"], "plan": plan, "ref_s": round(time.time() - t, 3)})
            (folder / "case.json").write_text(json.dumps({"index": index, "base": base, "degree": degree, "rows": rows}))
            print(folder.name, "schemas", len(spec.schemas), "edges", len(spec.edges),
                  "ref_s", [r["ref_s"] for r in rows], "plan_len", [len(r["plan"] or []) for r in rows], flush=True)
    elif mode == "one":
        name, folder = sys.argv[2], Path(sys.argv[3])
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (4 << 30, 4 << 30))
        case = json.loads((folder / "case.json").read_text())
        spec, *_ = world(case["index"], case["base"], case["degree"])
        fn = core2.SOLVERS[name] if name in core2.SOLVERS else getattr(core2._load_core(), name + "_plan")
        row = case["rows"][0]
        t = time.time()
        try:
            verdict = "exact" if fn(spec, row["start"], row["payload"]) == row["plan"] else "WRONG"
        except MemoryError:
            verdict = "MEMORY"
        print(folder.name, name, verdict, round(time.time() - t, 2), flush=True)
    elif mode == "seeds":
        count, base, degree = map(int, sys.argv[2:5])
        t0, worst, emax = time.time(), 0.0, 0
        for index in range(1, count + 1):
            t = time.time()
            spec, *_ = world(index, base, degree)
            worst = max(worst, time.time() - t)
            emax = max(emax, len(spec.edges))
        print("seeds ok", count, "worst_build_s", round(worst, 2), "max_edges", emax, "total_s", round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
