import sys, importlib.util, tempfile, zipfile
from pathlib import Path
spec = importlib.util.spec_from_file_location("s", sys.argv[1]); s = importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
out = Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(sys.argv[2]) as z: z.extractall(out)
s.TOOL = out
print(len(s.repair()), "repairs")
