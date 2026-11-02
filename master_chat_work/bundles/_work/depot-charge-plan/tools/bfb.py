"""Build BRANCH_FIRE: bfb.py <out_root> <bundle_data> kind:seed ...  (renders hidden with gen_core, runs proto2 bf)"""
import os, subprocess, sys
W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, W)
import gen_core  # noqa
root, shipped = sys.argv[1], sys.argv[2]
subprocess.run([sys.executable, "-B", os.path.join(W, "proto2", "bf.py"), shipped, os.path.join(root, "shipped")], check=True)
for spec in sys.argv[3:]:
    kind, seed = spec.split(":")
    d = os.path.join(root, spec.replace(":", "_"), "data")
    os.makedirs(d, exist_ok=True)
    gen_core.render(int(seed), kind, d)
    subprocess.run([sys.executable, "-B", os.path.join(W, "proto2", "bf.py"), d, os.path.dirname(d)], check=True)
print("ALL_DONE", flush=True)
