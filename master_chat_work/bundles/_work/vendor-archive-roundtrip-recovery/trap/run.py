import importlib.util, json, re, sys
sys.path.insert(0, sys.argv[3])
tests, ws = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("test_output", tests)
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
weights = dict((m.group(1), int(m.group(2))) for m in re.finditer(r"^criteria\.(\w+)\(weight=(-?\d+)\)", open(tests).read(), re.M))
res = {n: bool(getattr(mod, n)(ws)) for n in weights}
print(json.dumps({"res": res, "weights": weights}))
