import importlib.util, json, subprocess, sys, tempfile, os
spec = importlib.util.spec_from_file_location("t", "/b/tests/test_output.py"); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
for key in sys.argv[2:]:
    seed, kind = t._FRESH[key]
    data = t._fresh_tree(seed, kind)
    exp = t._expected(data)
    out = tempfile.mkdtemp()
    r = subprocess.run(["python3", sys.argv[1], "--data", str(data), "--out", out], capture_output=True, text=True, timeout=300)
    print("==", key, "rc", r.returncode, r.stderr[-200:])
    for name in ("data_quality.json", "summary.json"):
        got = json.load(open(os.path.join(out, name)))
        want = json.loads(exp[name]) if isinstance(exp[name], str) else exp[name]
        if got != want:
            if name == "summary.json":
                print(name, {k: (got.get(k), want.get(k)) for k in want if got.get(k) != want.get(k)})
            else:
                g = got["rejected"] if isinstance(got, dict) else got; w = want["rejected"] if isinstance(want, dict) else want
                print(name, "extra", [x for x in g if x not in w], "missing", [x for x in w if x not in g])
