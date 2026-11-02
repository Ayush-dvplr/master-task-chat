#!/usr/bin/env python3
"""77e8554 M2/W1 proof: run the SOLVER embedded in a solve.py on shipped and H1..H4, save outputs.

usage: byte_proof.py <solve.py> <tests/test_output.py> <dest dir>
"""
import importlib.util
import re
import subprocess
import sys
import tempfile
import types
from pathlib import Path


def main():
    solve, tests, dest = (Path(p).resolve() for p in sys.argv[1:4])
    text = solve.read_text(encoding="utf-8")
    solver = re.search(r"SOLVER = r'''(.*?)'''\n", text, re.S).group(1)
    fake = types.ModuleType("rewardkit")
    fake.criteria = types.SimpleNamespace()
    fake.criterion = lambda **kw: lambda f: f
    sys.modules["rewardkit"] = fake
    spec = importlib.util.spec_from_file_location("t", tests)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except AttributeError:
        pass  # registrations at the bottom need a real registry; helpers are defined above them
    with tempfile.TemporaryDirectory() as tmp:
        prog = Path(tmp) / "solver.py"
        prog.write_text(solver, encoding="utf-8", newline="\n")
        for name in ("shipped", "H1", "H2", "H3", "H4"):
            data = Path(tmp) / name
            mod._write_corpus(name, data)
            out = dest / name
            out.mkdir(parents=True, exist_ok=True)
            subprocess.run([sys.executable, str(prog), str(data), str(out)], check=True)
            print(name, len(list(out.iterdir())), flush=True)
    print("ALL_DONE")


if __name__ == "__main__":
    main()
