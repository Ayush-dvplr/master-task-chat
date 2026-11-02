import sys, zipfile, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("solve", "/sol/solve.py")
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
S.WORK = Path("/w/oracle_program")
S.DATA = Path("/data")
S.extract(); S.repair()
print("ALL_DONE")
