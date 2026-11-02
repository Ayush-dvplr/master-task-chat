import os, sys, traceback, importlib
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, sys.argv[2])
os.environ["SEASON_OUT_DIR"] = sys.argv[1]
import test_output as T
names = [n for n in dir(T) if n.startswith("test_generalisation") or n.startswith("test_determinism")]
for n in sorted(names):
    try:
        getattr(T, n)(); print("PASS", n)
    except Exception as e:
        print("FAIL", n, "::", str(e)[:500].replace("\n"," | "))
