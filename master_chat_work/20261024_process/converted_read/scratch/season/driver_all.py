import os, sys
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, sys.argv[2])
os.environ["SEASON_OUT_DIR"] = sys.argv[1]
import test_output as T
for n in sorted(n for n in dir(T) if n.startswith("test_")):
    try: getattr(T, n)(); print("PASS", n)
    except Exception as e: print("FAIL", n, "::", str(e)[:200].replace("\n"," | "))
