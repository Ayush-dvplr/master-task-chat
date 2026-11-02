"""Differential fuzz driver for caldermoor-commitment-closure (runs inside the verifier image).

case: {"id","profile","seed","fix":[prec|env|ident|env2|prec_all],"struct":none|reverse|renamed|cwdroot|readonly}
expected = T.write_all(T.compute(data)) like T._reference. Agent /progs/agent/reconcile.py and oracle
/progs/oracle/solve.py run as nobody like T._invoke_program. Every graded artifact compared byte for byte;
differing artifacts get a line level summary (count, first differing line pair, sample keys).
"""
import json, os, shutil, signal, subprocess, sys, tempfile, time
from multiprocessing import Pool

sys.path.insert(0, "/tests")
import test_output as T

GRADED = [a for a in T.ARTIFACTS if a != "reconcile.py"]


def fixtures(files, fix, seed):
    for f in fix:
        if f == "prec":
            T._add_precedence_row(files)
        elif f == "env":
            T._add_small_envelopes(files)
        elif f == "ident":
            T._add_identity_fixtures(files)
        elif f == "env2":
            # every second envelope at the reserve-sized minimum of the fixture's spirit (5..40 minutes)
            taken = {tuple(l.split("|")[:2]) for l in files["budget_overrides.psv"].split("\n")[1:] if l}
            pairs = sorted(tuple(l.split(",")[:2]) for l in files["attention_budget.csv"].split("\n")[1:] if l)
            extra = ["%s|%s|%d" % (a, m, 5 + (i * 7) % 36) for i, (a, m) in enumerate(pairs[::2]) if (a, m) not in taken]
            files["budget_overrides.psv"] = files["budget_overrides.psv"].rstrip("\n") + "\n" + "\n".join(extra) + "\n"


def _table(text, sep):
    lines = [l for l in text.split("\n") if l]
    return lines[0].split(sep), [l.split(sep) for l in lines[1:]]


def governing(files):
    head, rows = _table(files["cadence_register.csv"], ",")
    best = {}
    for r in rows:
        d = dict(zip(head, r))
        if d["cadence_id"] not in best or int(d["revision"]) > int(best[d["cadence_id"]]["revision"]):
            best[d["cadence_id"]] = d
    return best


def elapsed(d):
    a = T.parse_instant(d["anchor_at"])
    n = 0
    while a + n * int(d["period_days"]) * 1440 < T.WINDOW_END:
        n += 1
    return n


def m_waivers(files, rng):
    """dense waivers: shared owners, period ties, duplicates across files, non-elapsed, undeclared cadence."""
    gov = governing(files)
    cads = sorted(gov)
    add_d, add_p, k = [], [], 0
    for _ in range(rng.randint(40, 120)):
        c = rng.choice(cads)
        n = elapsed(gov[c])
        roll = rng.random()
        if roll < .08:
            idx = n + rng.randint(0, 3)          # not elapsed
        elif roll < .12:
            c, idx = "CAD-%03d" % rng.randint(900, 999), rng.randint(0, 5)   # undeclared
        elif roll < .25:
            idx = n - 1                          # last, cut short period
        else:
            idx = rng.randrange(max(n, 1))
        k += 1
        row = ["WVR-9%04d" % k, c, str(idx), rng.choice(["AGREED", "AWAY", "SUPERSEDED"]),
               T.fmt_instant(rng.randrange(T.WINDOW_START, T.WINDOW_END))]
        (add_d if rng.random() < .5 else add_p).append(row)
        if rng.random() < .15:                   # the same cadence and period again, other file
            k += 1
            dup = ["WVR-9%04d" % k] + row[1:]
            (add_p if rng.random() < .5 else add_d).append(dup)
    files["waivers_desk.csv"] = files["waivers_desk.csv"].rstrip("\n") + "\n" + "".join(",".join(r) + "\n" for r in add_d)
    files["waivers_partner.psv"] = files["waivers_partner.psv"].rstrip("\n") + "\n" + "".join("|".join(r) + "\n" for r in add_p)


def m_revision(files, rng):
    """a higher revision for some cadences with another period length and anchor; the lower revision keeps its values."""
    gov = governing(files)
    head, _rows = _table(files["cadence_register.csv"], ",")
    add = []
    for c in rng.sample(sorted(gov), min(8, len(gov))):
        d = dict(gov[c])
        d["revision"] = str(int(d["revision"]) + rng.randint(1, 3))
        d["period_days"] = str(rng.choice([1, 2, 7, 14, 30, 91, 300]))
        d["anchor_at"] = T.fmt_instant(rng.choice([T.WINDOW_START, T.WINDOW_START - 1440 * rng.randint(1, 40),
                                                   T.WINDOW_END - 1, T.mk(2032, rng.randint(3, 11), rng.randint(1, 28))]))
        add.append(",".join(d[h] for h in head))
    files["cadence_register.csv"] = files["cadence_register.csv"].rstrip("\n") + "\n" + "\n".join(add) + "\n"


def write(files, dest, reverse=False):
    os.makedirs(dest, exist_ok=True)
    for name, text in sorted(files.items(), reverse=reverse):
        with open(os.path.join(dest, name), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)


def run(prog, data, out, cwd):
    os.makedirs(out, exist_ok=True)
    T._grant_read(data)
    T._grant_read(os.path.dirname(prog))
    os.chmod(os.path.dirname(out), 0o777)
    os.chmod(out, 0o777)
    cmd = ["/usr/bin/setpriv", "--reuid=nobody", "--regid=nogroup", "--init-groups", "--no-new-privs",
           sys.executable, prog, data, out]
    t0 = time.time()
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd=cwd, start_new_session=True)
    try:
        _, err = p.communicate(timeout=T.RUN_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        return "timeout", "", time.time() - t0
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    return p.returncode, err.decode("utf-8", "replace")[-400:], time.time() - t0


def line_diff(want, got):
    w = want.decode("utf-8", "replace").split("\n")
    g = got.decode("utf-8", "replace").split("\n")
    ws, gs = set(w), set(g)
    only_w = [l for l in w if l not in gs]
    only_g = [l for l in g if l not in ws]
    first = next((i for i in range(max(len(w), len(g))) if (w[i] if i < len(w) else None) != (g[i] if i < len(g) else None)), None)
    return {"lines_w": len(w), "lines_g": len(g), "missing": len(only_w), "extra": len(only_g),
            "first": first, "want_line": (w[first] if first is not None and first < len(w) else None),
            "got_line": (g[first] if first is not None and first < len(g) else None),
            "samples_missing": only_w[:4], "samples_extra": only_g[:4]}


def compare(exp, out):
    d = {}
    for name in GRADED:
        p = os.path.join(out, name)
        if not os.path.isfile(p):
            d[name] = {"absent": True}
            continue
        got = open(p, "rb").read()
        if got != exp[name]:
            d[name] = line_diff(exp[name], got)
    return d


def one(case):
    rec = dict(case)
    tmp = tempfile.mkdtemp(prefix="cmfz")
    try:
        try:
            files, _w = T.build_all(case["seed"])
            fixtures(files, case.get("fix", []), case["seed"])
            rng = __import__("random").Random(case["seed"] * 17 + 3)
            for m in case.get("muts", []):
                {"waivers": m_waivers, "revision": m_revision}[m](files, rng)
        except Exception as e:  # generator refused this seed
            rec["gen_error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
            return rec
        st = case.get("struct", "none")
        dname = "extract (moved) \u00fc" if st == "renamed" else "data"
        data = os.path.join(tmp, "in", dname)
        write(files, data, reverse=(st == "reverse"))
        ref_out = os.path.join(tmp, "ref")
        os.makedirs(ref_out)
        try:
            T.write_all(T.compute(data), ref_out)
        except Exception as e:
            rec["ref_error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
            return rec
        exp = {n: open(os.path.join(ref_out, n), "rb").read() for n in os.listdir(ref_out)}
        rec["ref_missing"] = [n for n in GRADED if n not in exp]
        cwd = "/" if st == "cwdroot" else tmp
        if st == "readonly":
            for here, dirs, fs in os.walk(data):
                for f in fs:
                    os.chmod(os.path.join(here, f), 0o444)
        for who, prog in (("agent", "/progs/agent/reconcile.py"), ("oracle", "/progs/oracle/solve.py")):
            out = os.path.join(tmp, "o_" + who, "out")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            pdir = os.path.join(tmp, "p_" + who)
            os.makedirs(pdir)
            prog = shutil.copy(prog, os.path.join(pdir, "reconcile.py"))
            code, err, secs = run(prog, data, out, cwd)
            if st == "readonly":
                for here, dirs, fs in os.walk(data):
                    os.chmod(here, 0o755)
            r = {"code": code, "secs": round(secs, 2), "err": err if code != 0 else "", "diff": {}}
            if code == 0:
                r["diff"] = compare(exp, out)
            rec[who] = r
        return rec
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    if sys.argv[1] == "--one":
        print(json.dumps(one(json.loads(sys.argv[2])), indent=1, ensure_ascii=False)[:20000])
        return
    cases = [json.loads(l) for l in open(sys.argv[1])]
    done = set()
    if os.path.exists(sys.argv[2]):
        done = {json.loads(l)["id"] for l in open(sys.argv[2])}
    todo = [c for c in cases if c["id"] not in done]
    with Pool(int(sys.argv[3])) as pool, open(sys.argv[2], "a") as fh:
        for rec in pool.imap_unordered(one, todo):
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()


if __name__ == "__main__":
    main()
