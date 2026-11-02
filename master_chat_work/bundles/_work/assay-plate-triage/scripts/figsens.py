"""Per figure: how many single alterations, dropped from the full word, move it (M4 weight reasons)."""
import importlib.util, sys, pathlib
B = "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/assay-plate-triage"
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("solve", B + "/solution/solve.py")
s = importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
e = s.load_engine(s.ENGINE)
run = e["read_run"](B + "/environment/data")
names = [c if isinstance(c, str) else c[0] for c in s.CANDIDATES]
def figs(active):
    readings, rows, bench = e["resolve"](run, frozenset(active))
    return s.closing_figures(run, readings, rows)
full = figs(names)
print(full)
for k in full:
    moved = [n for n in names if figs(set(names) - {n})[k] != full[k]]
    print(k, full[k], len(moved), moved)
