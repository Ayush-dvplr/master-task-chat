import sys, time, importlib.util, os
from pathlib import Path
here = Path(__file__).parent
sys.path.insert(0, str(here))
spec = importlib.util.spec_from_file_location("t", sys.argv[1]); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
out = Path(sys.argv[2])
for lab in sys.argv[3:]:
    kind, k = lab.rsplit("_", 1); k = int(k)
    t0 = time.perf_counter(); c0 = time.process_time()
    files = (t._long_files if kind == "long" else t._ladder_files)(k)
    d = out / lab; d.mkdir(parents=True, exist_ok=True)
    for n, b in files.items(): (d / n).write_bytes(b)
    print(lab, "gen_wall_s=%.1f gen_cpu_s=%.1f files=%d bytes=%d" % (time.perf_counter()-t0, time.process_time()-c0, len(files), sum(map(len, files.values()))), flush=True)
