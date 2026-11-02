"""Docker-only: differential search for documented behaviours a program gets wrong.
Small worlds from the bundle generator, each with document-valid byte rewrites.
Usage: python -B fuzz.py <test_output.py> <program.py> <n_seeds> <json out>"""
import importlib.util, json, random, re, subprocess, sys, tempfile, time
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / "rk"))
tests, prog, nseeds, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
spec = importlib.util.spec_from_file_location("t_out", tests)
T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)


def lines(b):
    return b.decode("utf-8").split("\n")


def shuffle_pc(fs, rng):
    ls = [l for l in lines(fs["plan_changes.log"]) if l.strip()]
    keyof = [(T.ref_canon(re.search(r"account=(\S+)", l).group(1)), l.split()[0]) for l in ls]
    order = list(range(len(ls))); rng.shuffle(order)
    slots = {}
    for pos, i in enumerate(order):
        slots.setdefault(keyof[i], []).append(pos)
    res = [None] * len(ls)
    members = {}
    for i, k in enumerate(keyof):
        members.setdefault(k, []).append(i)
    for k, idxs in members.items():
        for pos, i in zip(sorted(slots[k]), idxs):
            res[pos] = ls[i]
    fs["plan_changes.log"] = ("\n".join(res) + "\n").encode()


def shuffle_acc(fs, rng):
    ls = [l for l in lines(fs["accounts.csv"]) if l.strip()]
    body = ls[1:]; rng.shuffle(body)
    fs["accounts.csv"] = ("\n".join([ls[0]] + body) + "\n").encode()


def noncanon(fs, rng):
    def nc(x):
        x = x.strip()
        if not x:
            return x
        y = x.lower() if rng.random() < 0.5 else x
        k = rng.randint(1, len(y) - 1)
        return y[:k] + "-" + y[k:]
    ls = [l for l in lines(fs["accounts.csv"]) if l.strip()]
    out = [ls[0]]
    for l in ls[1:]:
        c = l.split(",")
        c[0] = nc(c[0]) if rng.random() < 0.3 else c[0]
        c[3] = nc(c[3]) if rng.random() < 0.5 else c[3]
        out.append(",".join(c))
    fs["accounts.csv"] = ("\n".join(out) + "\n").encode()
    pl = []
    for l in lines(fs["plan_changes.log"]):
        if l.strip():
            l = re.sub(r"account=(\S+)", lambda m: "account=" + nc(m.group(1)), l)
        pl.append(l)
    fs["plan_changes.log"] = "\n".join(pl).encode()


def pad(fs, rng):
    ls = [l for l in lines(fs["accounts.csv"]) if l.strip()]
    out = [ls[0]] + [",".join(" " * rng.randint(0, 2) + c + " " * rng.randint(0, 2) for c in l.split(",")) for l in ls[1:]]
    fs["accounts.csv"] = ("\n".join(out) + "\n").encode()
    for name, sep in (("collector_east.tsv", "\t"),):
        ls = lines(fs[name])
        o = [ls[0]] + [sep.join(" " * rng.randint(0, 2) + c + " " * rng.randint(0, 2) for c in l.split(sep)) if l.strip() else l for l in ls[1:]]
        fs[name] = "\n".join(o).encode()


def reverse_tiers(fs, rng):
    d = json.loads(fs["rate_card.json"].decode(), parse_float=lambda s: "@@" + s)
    for p in d["products"].values():
        rng.shuffle(p["tiers"])
    keys = list(d["products"].items()); rng.shuffle(keys); d["products"] = dict(keys)
    fs["rate_card.json"] = re.sub(r'"@@([0-9.eE+-]+)"', r"\1", json.dumps(d, indent=1)).encode()


def ini_shuffle(fs, rng):
    text = fs["products.ini"].decode()
    secs = re.split(r"\n(?=\[)", text.strip("\n"))
    out = []
    for s in secs:
        head, *kv = [x for x in s.split("\n") if x.strip()]
        rng.shuffle(kv)
        out.append("\n".join([head] + kv))
    rng.shuffle(out)
    fs["products.ini"] = ("\n\n".join(out) + "\n").encode()


def west_order(fs, rng):
    o = []
    for l in lines(fs["collector_west.log"]):
        if l.strip():
            p = l.split(" "); rest = p[1:]; rng.shuffle(rest); l = " ".join([p[0]] + rest)
        o.append(l)
    fs["collector_west.log"] = "\n".join(o).encode()


def north_keys(fs, rng):
    o = []
    for l in lines(fs["collector_north.jsonl"]):
        if l.strip():
            pairs = re.findall(r'("[a-z]+": (?:"[^"]*"|[^,}]+))', l)
            if len(pairs) == 5:
                rng.shuffle(pairs); l = "{" + ", ".join(pairs) + "}"
        o.append(l)
    fs["collector_north.jsonl"] = "\n".join(o).encode()


def xml_order(fs, rng):
    t = fs["commitments.xml"].decode()
    pools = re.findall(r"  <pool [^>]*/>\n", t)
    sh = pools[:]; rng.shuffle(sh)
    rest = t
    for p in pools:
        rest = rest.replace(p, "@@P@@", 1)
    for p in sh:
        rest = rest.replace("@@P@@", p, 1)
    fs["commitments.xml"] = rest.encode()


PERT = [shuffle_pc, shuffle_acc, noncanon, pad, reverse_tiers, ini_shuffle, west_order, north_keys, xml_order]


def run(fs):
    work = Path(tempfile.mkdtemp()); src = work / "in"; src.mkdir(); dst = work / "out"
    for n, b in fs.items():
        (src / n).write_bytes(b)
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-I", prog, "--input", str(src), "--output", str(dst)], capture_output=True, text=True, timeout=30, cwd=str(work))
        rc, err = p.returncode, p.stderr[-200:]
    except subprocess.TimeoutExpired:
        return "TIMEOUT", round(time.time() - t0, 2), None
    if rc != 0:
        return "CRASH", round(time.time() - t0, 2), err
    return "OK", round(time.time() - t0, 2), dst


res = []
for s in range(nseeds):
    rng = random.Random(9000 + s)
    month = "%04d-%02d" % (rng.choice((2027, 2028)), rng.randint(1, 12))
    base = T.gen_month(70000 + s, month, 300, 300, True, T.ref_compute, resellers=40 if s % 2 else 0)
    for pert in [None] + PERT + ["all"]:
        fs = dict(base)
        if pert == "all":
            for f in PERT:
                f(fs, rng)
            name = "all"
        elif pert is not None:
            pert(fs, rng); name = pert.__name__
        else:
            name = "none"
        try:
            want = T.ref_compute(fs)
        except Exception as e:
            res.append({"seed": s, "pert": name, "verdict": "REF_FAIL %r" % e}); print(res[-1], flush=True); continue
        kind, secs, dst = run(fs)
        if kind != "OK":
            v = kind + " " + str(dst)
        else:
            bad = {}
            for doc in T.DOCUMENTS:
                try:
                    d = T._first_diff(want[doc], T._load(dst, doc))
                except Exception as e:
                    d = "LOADERR %s" % e
                if d is not None:
                    bad[doc] = str(d)[:160]
            v = "EXACT" if not bad else "WRONG " + json.dumps(bad)[:400]
        res.append({"seed": s, "pert": name, "secs": secs, "verdict": v})
        if v != "EXACT":
            print(res[-1], flush=True)
    Path(out).write_text(json.dumps(res, indent=0))
    print("seed", s, "done", flush=True)
summ = {}
for r in res:
    summ.setdefault(r["pert"], {}).setdefault(r["verdict"].split(" ")[0], 0)
    summ[r["pert"]][r["verdict"].split(" ")[0]] += 1
print("SUMMARY", json.dumps(summ))
print("ALL_DONE")
