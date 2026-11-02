import runpy
import sys
sys.dont_write_bytecode = True
sys.argv = ["run_prog.py", "greedy"] + sys.argv[1:3] + ["/b/solution/solve.py"]
runpy.run_path("/k/proto/run_prog.py", run_name="__main__")
