import importlib.util, json, sys, tempfile
spec = importlib.util.spec_from_file_location("solve", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
orig = m.compute_counterfactuals
box = {}
def wrap(*a, **k):
    box["cf"] = orig(*a, **k); return box["cf"]
m.compute_counterfactuals = wrap
out = tempfile.mkdtemp()
sys.argv = ["solve", "--data", sys.argv[2], "--out", out]
m.main()
print(json.dumps(box["cf"], indent=1, sort_keys=True))
