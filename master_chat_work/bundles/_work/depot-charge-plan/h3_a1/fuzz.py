"""fuzz.py: a1 program vs reference solve.py on generated folders.

Docker only. Mounts: /w = WORK (gen_core.py), /s = BUNDLE/solution, /a = a1 out dir (derive_report.py), /r = run dir.
Usage: fuzz.py <branch> <first_seed> <n> <jobs>
branch: shipped | hidden | large | hidden_reorder | any kind gen_core.render knows
Prints one JSON line per seed: {branch, seed, verdict MATCH|DIFF|REF_FAIL|A1_FAIL, first, ref_s, a1_s}
"""
import json, os, random, shutil, subprocess, sys, tempfile, time
from multiprocessing import Pool

sys.path.insert(0, "/w")
sys.dont_write_bytecode = True
import gen_core  # noqa: E402
sys.path.insert(0, "/w/h3_a1/proto")
import gen_core_up  # noqa: E402

DOCS = ["policy_audit.json", "region_North.json", "region_South.json", "region_West.json",
        "region_East.json", "segment_commercial.json", "segment_public.json", "summary.json",
        "data_quality.json"]


def reorder(data, seed):
    rng = random.Random(seed * 31 + 7)
    for name in ("roster.csv", "published_plan.csv", "settlements.csv", "fleet_register.csv", "trips.jsonl"):
        p = os.path.join(data, name)
        lines = open(p).read().splitlines(keepends=True)
        skip = 0 if name.endswith(".jsonl") else 1
        body = lines[skip:]
        rng.shuffle(body)
        open(p, "w").write("".join(lines[:skip] + body))
    p = os.path.join(data, "service_classes.ini")
    text = open(p).read()
    open(p, "w").write(text.replace("[public]\nweight = 4", "[public]\nweight = 6"))


def first_diff(a, b, path=""):
    if type(a) is not type(b):
        return path or "/"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return path + "/" + k
            d = first_diff(a[k], b[k], path + "/" + k)
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return path + "[len]"
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, "%s[%d]" % (path, i))
            if d:
                return d
        return None
    return None if a == b else path


def same_bytes(data, h, added, plain):
    """True when the uplift folder minus its inserted lines equals the plain hidden render of h."""
    gen_core.render(h, "hidden", plain)
    if sorted(os.listdir(data)) != sorted(os.listdir(plain)):
        return False
    for name in os.listdir(plain):
        a = open(os.path.join(data, name), "rb").read()
        b = open(os.path.join(plain, name), "rb").read()
        if name not in added:
            if a != b:
                return False
            continue
        lines = a.decode().splitlines()
        for row in added[name]:
            lines.remove(row)
        if "\n".join(lines) + "\n" != b.decode():
            return False
    return True


def run(cmd, out):
    os.makedirs(out, exist_ok=True)
    t = time.time()
    p = subprocess.run(cmd + ["--out", out], capture_output=True, text=True, timeout=300)
    return p.returncode, time.time() - t, p.stderr[-300:]


def one(args):
    branch, seed = args
    tmp = tempfile.mkdtemp(dir="/tmp")
    try:
        data = os.path.join(tmp, "data")
        kind = "hidden" if branch == "hidden_reorder" else branch
        extra = {}
        try:
            if kind == "uplift2":
                h, added = gen_core.uplift(seed, data)
                extra = {"h": h, "bytes": same_bytes(data, h, added, os.path.join(tmp, "plain"))}
            else:
                (gen_core_up if kind == "uplift" else gen_core).render(seed, kind, data)
        except Exception as e:
            return {"branch": branch, "seed": seed, "verdict": "GEN_FAIL", "first": repr(e)[:200]}
        if branch == "hidden_reorder":
            reorder(data, seed)
        rr, rs, re_ = run(["python3", "-B", "/s/solve.py", "--data", data], os.path.join(tmp, "ref"))
        ar, as_, ae = run(["python3", "-B", "/a/derive_report.py", "--data", data], os.path.join(tmp, "a1"))
        rec = {"branch": branch, "seed": seed, "ref_s": round(rs, 2), "a1_s": round(as_, 2), **extra}
        if rr == 0:
            base = int(open(os.path.join(data, "grid.ini")).read().split("feeder_kwh_per_slot =")[1].split()[0])
            reg = json.load(open(os.path.join(tmp, "ref", "region_North.json")))
            rec["above_base"] = sum(1 for x in reg["slots"] if x["feeder_kwh"] > base)
        if rr != 0:
            rec.update(verdict="REF_FAIL", first=re_)
        elif ar != 0:
            rec.update(verdict="A1_FAIL", first=ae)
        else:
            rec["verdict"] = "MATCH"
            rec["same"] = []
            for d in DOCS:
                x = json.load(open(os.path.join(tmp, "ref", d)))
                y = json.load(open(os.path.join(tmp, "a1", d)))
                f = first_diff(x, y)
                if f:
                    if rec["verdict"] == "MATCH":
                        rec.update(verdict="DIFF", first=d + f)
                else:
                    rec["same"].append(d)
        return rec
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    branch, s0, n, jobs = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    with Pool(jobs) as pool:
        for rec in pool.imap_unordered(one, [(branch, s) for s in range(s0, s0 + n)]):
            print(json.dumps(rec), flush=True)
    print("ALL_DONE", branch, flush=True)
