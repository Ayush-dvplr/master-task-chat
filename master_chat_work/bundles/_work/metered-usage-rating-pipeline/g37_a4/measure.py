"""Docker-only: time a program on test worlds and compare with ref_compute.
Usage: python -B measure.py <test_output.py> <program.py> <cap_sec> <world,...> <json out>
world names: hidden, long-K, ladder-K"""
import importlib.util, json, subprocess, sys, tempfile, time
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / "rk"))
tests, prog, cap, worlds, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4].split(","), sys.argv[5]
spec = importlib.util.spec_from_file_location("t_out", tests)
T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)
def files(w):
    if w == "hidden": return T._hidden_files()
    if w == "shipped": return T._shipped_files()
    if w.startswith("flat"):  # ladder-K with every parent pointed straight at its root (same groups); probe only
        fs = dict(T._ladder_files(int(w.split("-")[1])))
        rows = fs["accounts.csv"].decode().split("\n")
        cells = [r.split(",") for r in rows[1:] if r.strip()]
        par = {c[0].strip(): c[3].strip() for c in cells}
        root = {}
        for a in par:
            path = []; x = a
            while x not in root and par.get(x):
                path.append(x); x = par[x]
            r = root.get(x, x)
            for y in path: root[y] = r
            root.setdefault(x, r)
        out = [rows[0]]
        for c in cells:
            a = c[0].strip(); r = root[a]
            c[3] = "" if r == a else r
            out.append(",".join(c))
        fs["accounts.csv"] = ("\n".join(out) + "\n").encode()
        return fs
    kind, k = w.rsplit("-", 1)
    return {"long": T._long_files, "ladder": T._ladder_files}[kind](int(k))
res = {}
for w in worlds:
    t0 = time.time(); fs = files(w); tgen = time.time() - t0
    t0 = time.time(); want = T.ref_compute(fs); tref = time.time() - t0
    work = Path(tempfile.mkdtemp()); src = work / "in"; src.mkdir(); dst = work / "out"
    for n, b in fs.items(): (src / n).write_bytes(b)
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-I", prog, "--input", str(src), "--output", str(dst)], capture_output=True, text=True, timeout=cap, cwd=str(work))
        rc, err = p.returncode, p.stderr[-300:]
    except subprocess.TimeoutExpired:
        rc, err = None, "timeout"
    trun = time.time() - t0
    docs = {}
    if rc is None: docs["_"] = "TIMEOUT"
    elif rc != 0: docs["_"] = "CRASH"
    if rc == 0:
        for name in T.DOCUMENTS:
            try: got = T._load(dst, name)
            except Exception as e: docs[name] = "LOADERR %s" % e; continue
            d = T._first_diff(want[name], got)
            docs[name] = "EXACT" if d is None else d[:200]
    nlines = sum(b.count(b"\n") for b in fs.values())
    res[w] = {"gen_s": round(tgen, 2), "ref_s": round(tref, 2), "run_s": round(trun, 2), "rc": rc, "err": err, "docs": docs, "input_bytes": sum(len(b) for b in fs.values()), "input_lines": nlines}
    print(w, json.dumps({k: v for k, v in res[w].items() if k != "docs"}), {k: v for k, v in docs.items() if v != "EXACT"} or "ALL EXACT", flush=True)
    Path(out).write_text(json.dumps(res, indent=1))
print("ALL_DONE")
