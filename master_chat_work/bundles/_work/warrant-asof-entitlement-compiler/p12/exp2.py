import sys, importlib.util, tempfile, sys as _s
from pathlib import Path
spec = importlib.util.spec_from_file_location("t", sys.argv[1]); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
ONLY = [None]
orig = t.World.inw
def inw(self, lo, x, hi):
    fn = _s._getframe(1).f_code.co_name
    if ONLY[0] is not None and fn != ONLY[0] and not (fn == "<genexpr>" and ONLY[0] == "freeze"):
        return lo <= x < hi
    return orig(self, lo, x, hi)
t.World.inw = inw
for name in sys.argv[2].split(","):
    conv = t._conv_of(name); seed = [x[1] for x in t.CONV_TIERS if x[0] == name][0]
    root = Path(tempfile.mkdtemp(prefix="exp2-")); t.build(root, seed, 0.05, "conv", conv)
    ONLY[0] = None; half = t.everything(root, dict(conv, window="half"))[1]
    seen = set()
    ONLY[0] = "__probe__"
    for layer in ("standing_of", "directory_layer", "binding_layer", "freeze", "shifts", "profile"):
        ONLY[0] = layer; got = t.everything(root, conv)[1]
        print(name, layer, len(t.json.loads((root / "freeze_windows.json").read_text())["windows"]), {e: len(set(got[e]) ^ set(half[e])) + sum(1 for k in set(got[e]) & set(half[e]) if got[e][k] != half[e][k]) for e in ("dev", "prod")})
