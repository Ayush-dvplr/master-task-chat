"""E5 differential fuzz on the FINAL hidden generator (WORK/test_output.src.py): per seed and kind (H1, H2) build the
extract exactly as hidden_root does, then compare the reference with each wrong reading and with the saved agent
programs, per owned-row family. usage: python3 -B fuzz_final.py N FIRST"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path

WORK = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/district-heat-flex-procurement")
HERE = Path(__file__).resolve().parent
AGENTS = {"blind": HERE.parent / "agent_program" / "blind" / "derive_report.py",
          "harness": HERE.parent / "agent_program" / "harness" / "derive_report.py"}
FLAGS = ("REENTRY", "DROPLEFT", "NODROP", "NOCARRY", "CHAIN0", "CHAIN1", "RELIEF")
T = None


def _load():
    global T
    if T is None:
        sys.path.insert(0, str(WORK / "stub"))
        spec = importlib.util.spec_from_file_location("tsrc", WORK / "test_output.src.py")
        T = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(T)
    return T


def _fails(got, want, kind):
    t = _load()
    return sorted(f for f in t.FAMILIES if t.HIDDEN_OF[f] == kind
                  and (got is None or t._project(f, got) != t._project(f, want)))


def one(seed: int) -> dict:
    t = _load()
    row = {"seed": seed}
    for kind in ("H1", "H2"):
        spec = t._hidden_spec(kind, seed)
        if not t.within_contract(spec):
            row[kind] = "out_of_contract"
            continue
        planted = t._plant_grants(spec, seed, f"{kind}-{seed}")
        t._assert_bounds(spec)
        folder = Path(tempfile.mkdtemp(prefix="dhfp-ff-")) / "x"
        t.write_extract(folder, spec)
        ref = t.reference(folder)
        res = {"planted": planted}
        for flag in FLAGS:
            res[flag] = _fails(t.reference(folder, frozenset({flag})), ref, kind)
        for name, prog in AGENTS.items():
            out = folder.parent / f"out-{name}"
            p = subprocess.run([sys.executable, "-B", str(prog), str(folder), str(out)], capture_output=True,
                               timeout=120)
            got = None
            if p.returncode == 0:
                got = {q.name: json.loads(q.read_text()) for q in out.glob("*.json")}
            res[name] = _fails(got, ref, kind)
        row[kind] = res
        shutil.rmtree(folder.parent, ignore_errors=True)
        t._CACHE.clear()
        t._SEARCH_MEMO.clear()
    return row


def main() -> None:
    n, first = int(sys.argv[1]), int(sys.argv[2])
    rows = []
    with Pool(6, maxtasksperchild=5) as pool:
        for r in pool.imap_unordered(one, range(first, first + n)):
            rows.append(r)
            if len(rows) % 25 == 0:
                print(f"progress {len(rows)}/{n}", flush=True)
    rows.sort(key=lambda r: r["seed"])
    (HERE / f"fuzz_final_{first}_{n}.json").write_text(json.dumps(rows, indent=1))
    for kind in ("H1", "H2"):
        ok = [r[kind] for r in rows if isinstance(r[kind], dict)]
        full = sum(1 for r in ok if r["planted"] == 4)
        print(f"{kind}: corpora {len(ok)} (out of contract {n - len(ok)}), all 4 regions planted {full}")
        for key in FLAGS + tuple(AGENTS):
            diff = sum(1 for r in ok if r[key])
            mean = sum(len(r[key]) for r in ok) / max(1, len(ok))
            print(f"  {key:9s} differing {diff:4d}/{len(ok)} ({100 * diff / max(1, len(ok)):5.1f}%)  "
                  f"mean families {mean:4.1f}")


if __name__ == "__main__":
    main()
