import sys, pathlib
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
import importlib.util
spec = importlib.util.spec_from_file_location("t", sys.argv[2] + "/test_output.py")
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
ref = t._reference(t.SAMPLE_SEED)
out = pathlib.Path(sys.argv[3]); out.mkdir(exist_ok=True)
for k, v in ref.items(): (out / k).write_bytes(v)
print(len(ref))
