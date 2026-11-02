import sys, time, zipfile
from pathlib import Path
zipfile.ZipFile("/o/tool.zip").extractall("/app/tool")
src = Path("/solution/solve.py").read_text()
a = src.index("def self_check"); b = src.index('    witness = "no member reaches one group')
g = {"__name__": "r3dbg"}
exec(compile(src[:b], "r3dbg", "exec"), g)
t = time.time()
g["self_check"]({"hr": "site", "start": "decided", "window": "half"})
print(f"elapsed {time.time() - t:.1f}s", flush=True)
