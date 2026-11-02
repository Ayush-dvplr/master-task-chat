import sys, importlib.util, tempfile, json
from pathlib import Path
spec = importlib.util.spec_from_file_location("t", sys.argv[1]); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
for name in sys.argv[2].split(","):
    conv = t._conv_of(name); seed = [x[1] for x in t.CONV_TIERS if x[0] == name][0]
    root = Path(tempfile.mkdtemp(prefix="exp3-")); t.build(root, seed, 0.05, "conv", conv)
    a = t.everything(root, conv); b = t.everything(root, dict(conv, window="half"))
    for i, lab in ((0, "cfg"), (2, "audit"), (3, "summary")):
        print(name, lab, "same" if a[i] == b[i] else "DIFF")
    fa = json.dumps(a[2], sort_keys=True).count("freeze_window"); fb = json.dumps(b[2], sort_keys=True).count("freeze_window")
    print(name, "freeze_window mentions closed", fa, "half", fb)
    print(type(a[2]), list(a[2])[:8] if isinstance(a[2], dict) else len(a[2]))
