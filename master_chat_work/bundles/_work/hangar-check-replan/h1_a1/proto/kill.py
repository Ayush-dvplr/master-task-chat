"""h1 kill table: every program on every Word-table variant folder, verdict per graded view.

Run inside Docker only:  python3 -B proto/kill.py OUTLOG SEEDS PROG_DIR [variant,...]
PROG_DIR holds <name>.py programs (each: prog DATA_DIR OUT_DIR). Expected = reference on the folder
before restructuring; BRANCH_FIRE = the naive reference reading of the restructured folder differs.
"""
import json
import multiprocessing as mp
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import refgen as R  # noqa: E402
import variants as V  # noqa: E402

PLAN_ROW = ["request_id", "tail", "base", "aircraft_class", "segment", "check_type", "decision", "start_date",
            "finish_date", "compress_days", "overtime_shifts", "overdue_days", "moved", "deferral_reason"]
SETTLE_ROW = ["request_id", "overtime_cost", "allowance_shifts", "paid_shifts", "allowance_credit",
              "settled_overtime_cost"]
SETTLE_GROUP = ["allowance_granted", "overtime_cost", "allowance_used", "allowance_credit", "settled_overtime_cost"]
PLAN_SUMMARY = ["season", "plan_terms", "overtime_pool_shifts", "fleet_overtime_used", "checks_scheduled",
                "checks_deferred", "moved"]
BASES = ["North", "South", "West", "East"]
SEGS = ["commercial", "public"]
M = "<missing>"


def pick(o, ks):
    return {k: o.get(k, M) if isinstance(o, dict) else M for k in ks}


def rows(doc, ks):
    return [pick(r, ks) for r in (doc.get("checks", []) if isinstance(doc, dict) else [])]


def views(doc, want):
    g = lambda n: doc.get(n, {})  # noqa: E731
    v = {"plan_rows": rows(g("policy_audit.json"), PLAN_ROW)}
    pg = {}
    for n in ["region_%s.json" % b for b in BASES] + ["segment_%s.json" % s for s in SEGS]:
        pg[n] = pick(g(n), [k for k in want[n] if k not in SETTLE_GROUP])
    s = g("summary.json")
    pg["summary"] = dict(pick(s, PLAN_SUMMARY),
                         bases=[pick(r, ["base", "checks_scheduled", "checks_deferred", "overtime_shifts"])
                                for r in (s.get("bases", []) if isinstance(s, dict) else [])],
                         segments=[pick(r, ["segment", "checks_scheduled", "checks_deferred"])
                                   for r in (s.get("segments", []) if isinstance(s, dict) else [])])
    v["plan_groups"] = pg
    v["settle_checks"] = rows(g("policy_audit.json"), SETTLE_ROW)
    sg = {"region_%s.json" % b: pick(g("region_%s.json" % b), SETTLE_GROUP) for b in BASES}
    sg.update({"segment_%s.json" % x: pick(g("segment_%s.json" % x), SETTLE_GROUP[1:]) for x in SEGS})
    v["settle_groups"] = sg
    v["settle_summary"] = {"settlement": s.get("settlement", M) if isinstance(s, dict) else M,
                           "bases": [pick(r, ["base", "allowance_granted", "allowance_used",
                                              "settled_overtime_cost"])
                                     for r in (s.get("bases", []) if isinstance(s, dict) else [])]}
    return v


def norm(x):
    return json.loads(json.dumps(x))


def job(args):
    variant, seed, progs = args
    recs = []
    tmp = tempfile.mkdtemp(prefix="kl")
    try:
        data = os.path.join(tmp, "data")
        R.corpus("hidden", seed, 8, False, "bind", False, data)
        t0 = time.time()
        want = norm(R.derive(data))
        ref_s = round(time.time() - t0, 2)
        table, kind = V.VARIANTS[variant]
        touched = V.restructure(data, table, kind)
        try:
            naive = norm(R.derive(data))
            fire = "differs" if naive != want else "SAME"
        except Exception as e:  # noqa: BLE001
            fire = "naive_crash %r" % (str(e)[:60],)
        wv = views(want, want)
        for name, path in progs:
            rec = {"variant": variant, "seed": seed, "prog": name, "rows": touched, "fire": fire, "ref_s": ref_s}
            out = os.path.join(tmp, "o_" + name)
            os.makedirs(out)
            t0 = time.time()
            try:
                p = subprocess.run([sys.executable, "-B", path, data, out], capture_output=True, timeout=60,
                                   cwd=tmp)
                rec["s"] = round(time.time() - t0, 2)
                if p.returncode != 0:
                    rec["verdict"] = {k: "CRASH" for k in wv}
                    rec["why"] = (p.stderr.decode(errors="replace").strip().splitlines() or [""])[-1][:140]
                else:
                    doc = {}
                    for n in want:
                        try:
                            doc[n] = json.load(open(os.path.join(out, n)))
                        except Exception:  # noqa: BLE001
                            doc[n] = {}
                    gv = views(doc, want)
                    rec["verdict"] = {k: ("EXACT" if norm(gv[k]) == wv[k] else "WRONG") for k in wv}
            except subprocess.TimeoutExpired:
                rec["verdict"] = {k: "TIMEOUT" for k in wv}
            except Exception:  # noqa: BLE001
                rec["verdict"] = {k: "HARNESS" for k in wv}
                rec["why"] = traceback.format_exc().strip().splitlines()[-1][:160]
            shutil.rmtree(out, ignore_errors=True)
            recs.append(rec)
        return recs
    except Exception:  # noqa: BLE001
        return [{"variant": variant, "seed": seed, "prog": "-", "verdict": "GENFAIL",
                 "why": traceback.format_exc().strip().splitlines()[-1][:200]}]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    log, n, pdir = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    only = sys.argv[4].split(",") if len(sys.argv) > 4 else list(V.VARIANTS)
    progs = sorted((f[:-3], os.path.join(pdir, f)) for f in os.listdir(pdir) if f.endswith(".py"))
    jobs = [(v, 810000 + 31 * i + 7 * j, progs) for j, v in enumerate(only) for i in range(n)]
    total = 0
    with open(log, "a") as f, mp.Pool(2) as pool:
        for recs in pool.imap_unordered(job, jobs):
            for r in recs:
                f.write(json.dumps(r) + "\n")
                total += 1
            f.flush()
        f.write("ALL_DONE %d\n" % total)


if __name__ == "__main__":
    main()
