import json, os, subprocess, sys, tempfile
sys.path.insert(0, ".")
import bookgen
H = json.load(open("hidden_meta.json"))
SOLVE = "../../flood-repair-portfolio/solution/solve.py"
for name in ("H1", "H2", "H3"):
    spec = dict(H[name]["spec"]); spec["large"] = [tuple(x) for x in spec["large"]]
    files, meta = bookgen.make_book(H[name]["seed"], spec)
    d = tempfile.mkdtemp(); o = tempfile.mkdtemp()
    for f, t in files.items(): open(os.path.join(d, f), "w").write(t)
    subprocess.run([sys.executable, "-I", "-S", SOLVE, d, o], check=True)
    rej = json.load(open(os.path.join(o, "data_quality.json")))["rejected"]
    after = [(r["file"], r["row"], r["code"]) for r in rej if r["file"] in ("proposals.csv", "permits.csv")]
    blanks = {f: files[f].split("\n").index("") for f in ("proposals.csv", "permits.csv")}
    print(name, "blank line idx", blanks, "faults:", sorted(after))
