"""Render an abstract instance (absgen.make) to the full data layout. Usage: render.py mode seed n empty(0|1) outdir"""
import datetime as dt
import json
import os
import random
import string
import sys

from absgen import BASES, CLASSES, TYPES, make
import docx

D0 = dt.date(2025, 1, 1)
D1 = dt.date(2029, 12, 31)
SEASONS = [("2025A", dt.date(2025, 3, 1)), ("2025B", dt.date(2025, 9, 1)), ("2026A", dt.date(2026, 3, 1)),
           ("2026B", dt.date(2026, 9, 1)), ("2027A", dt.date(2027, 3, 1)), ("2027B", dt.date(2027, 9, 1)),
           ("2028A", dt.date(2028, 3, 1))]


def iso(d):
    return d.isoformat()


def render(inst, outdir, seed, traps=()):
    rng = random.Random(seed * 31 + 5)
    meta = inst["meta"]
    hidden = meta["mode"] == "hidden"
    season, sstart = SEASONS[4] if not hidden else rng.choice(SEASONS[2:])
    S = inst["S"]
    day = lambda d: sstart + dt.timedelta(days=d - 1)
    os.makedirs(outdir, exist_ok=True)
    # tails
    used = set()

    def new_tail():
        while True:
            t = "VT-" + "".join(rng.choice(string.ascii_uppercase) for _ in range(3))
            if t not in used:
                used.add(t)
                return t
    register = []
    for _ in range(2600):
        register.append([new_tail(), rng.choices(list(CLASSES), weights=[2, 3, 3])[0],
                         rng.choice(["IndiGo Air", "Vistara Regional", "Coastal Link", "Deccan Wings"]), "ACTIVE"])
    for row in rng.sample(register, 120):
        row[3] = "RETIRED"
    tail_of = {}
    for ch in inst["checks"]:
        t = new_tail()
        tail_of[ch["id"]] = t
        register.append([t, ch["cls"], rng.choice(["IndiGo Air", "Vistara Regional", "Coastal Link"]), "ACTIVE"])
    retired = [r[0] for r in register if r[3] == "RETIRED"]
    rng.shuffle(register)
    # requests
    hdr = "request_id,season,tail,check_type,base,available_from,due_date,duration_days,status"
    rows = []
    pub = []
    rid_pool = iter(rng.sample(range(100000, 999999), 9000))
    planned_tails = set(tail_of.values())
    active = [r for r in register if r[3] == "ACTIVE" and r[0] not in planned_tails]
    for sn, s0 in SEASONS:
        if sn == season:
            continue
        for _ in range(900):
            rid = "R%06d" % next(rid_pool)
            ty = rng.choice("ACD")
            p = rng.randint(*TYPES[ty]["p"])
            a = s0 + dt.timedelta(days=rng.randint(0, 150))
            rows.append([rid, sn, rng.choice(active)[0], ty, rng.choice(BASES), iso(a),
                         iso(a + dt.timedelta(days=p + rng.randint(0, 9))), str(p), rng.choice(["DONE", "DONE", "CANCELLED"])])
            pub.append([rid, iso(a + dt.timedelta(days=rng.randint(0, 3)))])
    notice_avail = []
    plan_rows = []
    for ch in inst["checks"]:
        a = day(ch["r"])
        if hidden and ch["r"] < ch["ps"] and rng.random() < 0.5:
            notice_avail.append((tail_of[ch["id"]], iso(a)))
            a = day(ch["ps"] + rng.randint(1, 5))
        elif not hidden and rng.random() < 0.15:
            notice_avail.append((tail_of[ch["id"]], iso(a)))
            a = day(max(1, ch["r"] - rng.randint(1, 5)))
        plan_rows.append([ch["id"], season, tail_of[ch["id"]], ch["type"], ch["base"], iso(a), iso(day(ch["due"])),
                          str(ch["p"]), "OPEN"])
        pub.append([ch["id"], iso(day(ch["ps"]))])
    # planned-season noise: cancelled rows and one reject of each kind (+ empty base rejects)
    extra = []

    def base_row(b=None):
        rid = "Q%05d" % rng.randint(10000, 99999)
        while any(r[0] == rid for r in plan_rows + extra):
            rid = "Q%05d" % rng.randint(10000, 99999)
        ty = rng.choice("ACD")
        p = rng.randint(*TYPES[ty]["p"])
        a = rng.randint(1, S - 30)
        return [rid, season, rng.choice(active)[0], ty, b or rng.choice(BASES), iso(day(a)),
                iso(day(a + p + 3)), str(p), "OPEN"]
    for _ in range(25):
        r = base_row()
        r[8] = "CANCELLED"
        extra.append(r)
        pub.append([r[0], r[5]])
    kinds = ["unknown_tail", "retired_tail", "bad_date", "bad_duration", "unknown_base", "unknown_check_type",
             "no_published_start"]
    eb = meta["empty_base"]
    plan = list(kinds) + (["retired_tail", "bad_date", "bad_duration"] if eb else [])
    for j, kd in enumerate(plan):
        r = base_row(eb if j >= len(kinds) else None)
        if kd == "unknown_tail":
            r[2] = "VT-" + "".join(rng.choice("0123456789") for _ in range(3))
        elif kd == "retired_tail":
            r[2] = rng.choice(retired)
        elif kd == "bad_date":
            r[6] = rng.choice(["2027-02-30", r[6].replace("-", "/"), "31-12-2027"])
        elif kd == "bad_duration":
            r[7] = rng.choice(["0", "-4", "7.5", "ten"])
        elif kd == "unknown_base":
            r[4] = rng.choice(["Central", "north", "Hub"])
        elif kd == "unknown_check_type":
            r[3] = rng.choice(["B", "E", "a"])
        if kd != "no_published_start":
            pub.append([r[0], r[5]])
        extra.append(r)
    if eb:
        for _ in range(2):
            r = base_row(eb)
            r[8] = "CANCELLED"
            extra.append(r)
            pub.append([r[0], r[5]])
    dup = list(rng.choice(plan_rows))
    dup[6] = iso(dt.date.fromisoformat(dup[6]) + dt.timedelta(days=7))
    allrows = rows + plan_rows + extra
    rng.shuffle(allrows)
    pos = rng.randint(len(allrows) // 2, len(allrows))
    first = next(i for i, r in enumerate(allrows) if r[0] == dup[0])
    allrows.insert(max(pos, first + 1), dup)
    with open(os.path.join(outdir, "check_requests.csv"), "w") as f:
        f.write(hdr + "\n")
        for r in allrows:
            f.write(",".join(r) + "\n")
    rng.shuffle(pub)
    with open(os.path.join(outdir, "published_plan.csv"), "w") as f:
        f.write("request_id,published_start\n")
        for r in pub:
            f.write(",".join(r) + "\n")
    with open(os.path.join(outdir, "fleet_register.csv"), "w") as f:
        f.write("tail,aircraft_class,operator,status\n")
        for r in register:
            f.write(",".join(r) + "\n")
    # calendar + notice closures
    notice_closed = []
    cal_closed = {b: set() for b in BASES}
    for b in BASES:
        cl = sorted(inst["closed"].get(b, []))
        runs = []
        for d in cl:
            if runs and d == runs[-1][1] + 1:
                runs[-1][1] = d
            else:
                runs.append([d, d])
        for a, z in runs:
            # hidden: every closure that ends inside the season is in the notice (more plan-changing cells)
            if z == S or (not hidden and b != meta.get("tight") and rng.random() < 0.4):
                cal_closed[b].update(range(a, z + 1))
            else:
                notice_closed.append((b, iso(day(a)), iso(day(z))))
    with open(os.path.join(outdir, "base_calendar.jsonl"), "w") as f:
        for b in BASES:
            ns = set(inst["nostart"][b])
            d = D0
            while d <= D1:
                k = (d - sstart).days + 1
                if 1 <= k <= S:
                    st = "CLOSED" if k in cal_closed[b] else ("NO_START" if k in ns else "OPEN")
                else:
                    x = rng.random()
                    st = "CLOSED" if x < 0.02 else ("NO_START" if x < 0.06 else "OPEN")
                f.write(json.dumps({"base": b, "date": iso(d), "status": st}) + "\n")
                d += dt.timedelta(days=1)
    for _ in range(3):
        t = rng.choice(active)[0]
        notice_avail.append((t, iso(day(rng.randint(1, S)))))
    rng.shuffle(notice_avail)
    closures = sorted(notice_closed, key=lambda x: (x[1], x[0]))
    write_office(outdir, inst, season, sstart, S, closures, notice_avail, set(traps), random.Random(seed * 104729 + 3))
    with open(os.path.join(outdir, "check_types.json"), "w") as f:
        json.dump({k: {"max_compress_days": v["c"], "overtime_shifts_per_day": v["h"]} for k, v in inst["types"].items()},
                  f, indent=2)
        f.write("\n")
    with open(os.path.join(outdir, "fleet_limits.toml"), "w") as f:
        f.write('season = "%s"\nseason_start = "%s"\nseason_end = "%s"\n' % (season, iso(sstart), iso(sstart + dt.timedelta(days=S - 1))))


def _len(a, z):
    return str((dt.date.fromisoformat(z) - dt.date.fromisoformat(a)).days + 1)


def _move_ok(v):
    return len(v) >= 2 and v[-1] != "0" and v[-1] + v[:-1] != v


def write_office(outdir, inst, season, sstart, S, closures, avail, traps, tr):
    """traps: subset of F1 relmain, F2 alt, F3 move, F4 delins. Targets: K (pool), tight closure days, rates, a date."""
    K, sc = str(inst["K"]), str(inst["shift_cost"])
    tight = inst["meta"].get("tight")
    cl = [[b, a, _len(a, z)] for b, a, z in closures]
    ti = max((i for i, c in enumerate(cl) if c[0] == tight), key=lambda i: int(cl[i][2]), default=None)
    pool = [["item", "value"], ["overtime_pool_shifts", K], ["shift_cost", sc]]
    rates = [["class", "revenue_per_day", "overdue_weight", "deferral_penalty"]] + [
        [c, str(v["rev"]), str(v["w"]), str(v["pen"])] for c, v in inst["classes"].items()]
    av = [["tail", "available_from"]] + [[t, a] for t, a in avail]
    # one trap per family; cell targets in fixed preference order, each cell used once
    # plan-changing cells first: pool limit, tight-base closure, other closures (longest first); shift cost last
    rest = sorted((i for i in range(len(cl)) if i != ti), key=lambda i: -int(cl[i][2]))
    # enlarging slips (F3, F4) bite on the pool and on ordinary closures; shrinking slips (F2) on the tight closure
    tc = [("cl", ti, 2)] if ti is not None else []
    grow = [("pool", 1, 1)] + [("cl", i, 2) for i in rest] + tc + [("pool", 2, 1)]
    shrink = [("pool", 1, 1)] + tc + [("cl", i, 2) for i in rest] + [("pool", 2, 1)]
    used = set()

    def pick(ok, targets=grow, need=True):
        for t in targets:
            if t in used:
                continue
            tab = {"pool": pool, "rates": rates, "cl": cl}[t[0]]
            if ok(tab[t[1]][t[2]]):
                used.add(t)
                return tab, t[1], t[2]
        if need:
            raise SystemExit("no trap target")
        return None
    def f3(need):
        got = pick(_move_ok, grow, need)
        if not got:
            return
        tab, i, j = got
        tab[i][j] = ("move", tab[i][j])

    def f4(need):
        got = pick(lambda v: isinstance(v, str) and len(v) >= 2 and int(v) >= 10, grow, need)
        if not got:
            return
        tab, i, j = got
        v = tab[i][j]
        old = tr.choice([d for d in "123456789" if d != v[-1]])
        tab[i][j] = ("delins", v[:-1], old, v[-1])

    def f2(need):
        # alternatives cover the leading digits; the last digit is a plain run after the element
        got = pick(lambda v: isinstance(v, str) and v.isdigit() and int(v) >= 10, shrink, need)
        if not got:
            return
        tab, i, j = got
        v = int(tab[i][j])
        lead, last = v // 10, str(v % 10)
        s3 = str(lead // 3) if lead // 3 else ""
        s2 = str(lead // 2) if lead // 2 else ""
        tab[i][j] = ("alt", s3, str(lead), s2, last)
    # each in-text family takes two cells; which family reaches the pool cell first is drawn per corpus
    fams = [f for f in ("F3", "F4", "F2") if f in traps]
    tr.shuffle(fams)
    for rnd in range(2):
        for f in fams:
            {"F3": f3, "F4": f4, "F2": f2}[f](rnd == 0)
    head = [("p", "Disruption notice for season %s" % season), ("p", "Issued by Maintenance Control after the published plan."),
            ("p", "Base closures")]
    nb = head + [("tbl", [["base", "from", "days"]] + cl), ("p", "Revised availability"), ("tbl", av)]
    lb = [("p", "Planning limits for season %s" % season), ("p", "Overtime pool"), ("tbl", pool), ("p", "Class rates"),
          ("tbl", rates)]
    pv = lambda rows: [[docx.plain(c) for c in r] for r in rows]
    if "F1" in traps:
        # notice when a tight closure exists and the limits doc is not already carrying F3/F4 on K; else limits
        st_pool = [r[:] for r in pv(pool)]
        st_pool[1][1] = str(int(st_pool[1][1]) * 2 + 7)
        st_rates = [r[:] for r in pv(rates)]
        for r in st_rates[1:]:
            r[1] = str(int(r[1]) + 10)
        stale_l = [("p", "Planning limits (draft)"), ("tbl", st_pool), ("tbl", st_rates)]
        st_cl = [r for r in pv(cl) if r[0] != tight] or pv(cl)[:1]
        stale_n = head + [("tbl", [["base", "from", "days"]] + st_cl), ("tbl", pv(av))]
        docx.write(os.path.join(outdir, "planning_limits.docx"), lb, stale=stale_l)
        docx.write(os.path.join(outdir, "disruption_notice.docx"), nb, stale=stale_n)
    else:
        docx.write(os.path.join(outdir, "planning_limits.docx"), lb)
        docx.write(os.path.join(outdir, "disruption_notice.docx"), nb)

if __name__ == "__main__":
    mode, seed, n, empty, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4] == "1", sys.argv[5]
    inst = make(mode, seed, n, empty)
    render(inst, out, seed, sys.argv[6].split(",") if len(sys.argv) > 6 else ())
    json.dump(inst, open(os.path.join(os.path.dirname(out.rstrip("/")) or ".", "abstract_%s_%d.json" % (mode, seed)), "w"))
