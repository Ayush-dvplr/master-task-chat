import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests_src"))
import hgen
for arg in sys.argv[1:]:
    name, seed = arg.split("=")
    out = os.path.join(os.path.dirname(__file__), "hidden", name)
    os.makedirs(out, exist_ok=True)
    for fn, text in hgen.build(int(seed)).items():
        with open(os.path.join(out, fn), "w") as fh:
            fh.write(text)
    print("wrote", out)
