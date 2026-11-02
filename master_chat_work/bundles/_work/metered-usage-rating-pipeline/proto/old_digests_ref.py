"""Scratch: the work reference must give byte-identical documents on shipped and hidden corpora."""
import importlib.util, json, os, sys
sys.dont_write_bytecode = True
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here); sys.path.insert(1, os.path.dirname(here))
import ref_core as R
spec = importlib.util.spec_from_file_location("T", "/b/tests/test_output.py")
T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)
for key, fn in (("shipped", T._shipped_files), ("hidden", T._hidden_files), ("scaled", T._tier_scaled_files),
                ("small", T._small_commitment_files), ("near", T._near_base_files)):
    f = fn(); a = T.ref_compute(f); b = R.ref_compute(f)
    print(key, json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str), flush=True)
