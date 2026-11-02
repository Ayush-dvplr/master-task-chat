"""targeted.py: a2 vs reference on hidden renders mutated toward branches a2's own fuzz never varied.
Usage: targeted.py <mutator|all> <first_seed> <n> <jobs>
Every mutation stays inside what charging_rules.md allows (see MUTATORS docstrings).
"""
import json, os, random, re, shutil, subprocess, sys, tempfile, time
from datetime import datetime, timedelta, date
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import fuzz_local as F  # noqa: E402
import gen_core  # noqa: E402  (path inserted by fuzz_local)

REF = "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/depot-charge-plan/solution/solve.py"
A2 = "/Users/mac/Desktop/Terminal Bench/master_chat_work/20261102_depot-charge-plan/a2_score/a2_out/derive_report.py"
ST = "%Y-%m-%dT%H:%M"
DEP = ["North", "South", "West", "East"]


def rd(d, n):
    return open(os.path.join(d, n)).read()


def wr(d, n, t):
    open(os.path.join(d, n), "w").write(t)


def plan(d):
    t = rd(d, "grid.ini")
    pd = re.search(r"plan_date = (\S+)", t).group(1)
    first = datetime.strptime(re.search(r"first_slot = (\S+)", t).group(1), ST)
    return pd, first, first + timedelta(minutes=15 * 96)


def csv_rows(d, n):
    lines = rd(d, n).splitlines()
    return lines[0], [l.split(",") for l in lines[1:]]


def csv_write(d, n, head, rows):
    wr(d, n, head + "\n" + "".join(",".join(r) + "\n" for r in rows))


def add_notice(d, section, lines):
    t = rd(d, "disruption_notice.md").splitlines()
    i = next(j for j, l in enumerate(t) if l.strip() == section)
    j = i + 1
    while j < len(t) and not t[j].startswith("## "):
        j += 1
    while j > i + 1 and not t[j - 1].strip():
        j -= 1
    t[j:j] = lines
    wr(d, "disruption_notice.md", "\n".join(t) + "\n")


def tm(x):
    return x.strftime(ST)


# ---------------------------------------------------------------- mutators (rule refs = charging_rules.md line)

def m_roster_depot(d, rng):
    """R5 :14 depot = roster depot, not register home_depot."""
    pd, *_ = plan(d)
    h, rows = csv_rows(d, "roster.csv")
    for r in rows:
        if r[0] == pd and rng.random() < 0.4:
            r[2] = rng.choice([x for x in DEP if x != r[2]])
    csv_write(d, "roster.csv", h, rows)


def m_offgrid(d, rng):
    """R5 :14 window = slots starting >= arrive and < depart, off-grid times; R13 :28 off-grid slot_start is not in window."""
    pd, first, end = plan(d)
    h, rows = csv_rows(d, "roster.csv")
    for r in rows:
        if r[0] == pd and rng.random() < 0.5:
            a = datetime.strptime(r[3], ST) + timedelta(minutes=rng.randint(-14, 14))
            e = datetime.strptime(r[4], ST) + timedelta(minutes=rng.randint(-14, 14))
            r[3], r[4] = tm(a), tm(e)
    csv_write(d, "roster.csv", h, rows)
    h, rows = csv_rows(d, "published_plan.csv")
    for r in rows:
        if r[0] == pd and rng.random() < 0.05:
            r[2] = tm(datetime.strptime(r[2], ST) + timedelta(minutes=rng.choice([1, 5, 7, 14])))
    csv_write(d, "published_plan.csv", h, rows)


def m_bad_window_edges(d, rng):
    """R4 :13 bad_window boundaries: arrive == first slot ok, depart == end ok, one minute past -> bad, arrive == depart bad."""
    pd, first, end = plan(d)
    h, rows = csv_rows(d, "roster.csv")
    cand = [r for r in rows if r[0] == pd]
    rng.shuffle(cand)
    kinds = ["a_first", "d_end", "a_first_m1", "d_end_p1", "eq", "both", "d_before_first_plus"]
    for i, r in enumerate(cand[:14]):
        k = kinds[i % len(kinds)]
        if k == "a_first":
            r[3] = tm(first)
        elif k == "d_end":
            r[4] = tm(end)
        elif k == "a_first_m1":
            r[3] = tm(first - timedelta(minutes=1))
        elif k == "d_end_p1":
            r[4] = tm(end + timedelta(minutes=1))
        elif k == "eq":
            r[4] = r[3]
        elif k == "both":
            r[3], r[4] = tm(first), tm(end)
        else:
            r[3], r[4] = tm(first + timedelta(minutes=3)), tm(first + timedelta(minutes=14))  # empty window, accepted
    csv_write(d, "roster.csv", h, rows)


def m_outages(d, rng):
    """R10 :22 + R2 :8 overlapping outages at one depot add up, off-grid spans, more than cabinets, spans past the plan day."""
    pd, first, end = plan(d)
    cab = {x["depot"]: x["cabinets"] for x in json.load(open(os.path.join(d, "depots.json")))["depots"]}
    out = []
    for _ in range(rng.randint(3, 7)):
        dep = rng.choice(DEP)
        a = first + timedelta(minutes=rng.randint(-60, 96 * 15))
        b = a + timedelta(minutes=rng.randint(1, 600))
        n = rng.choice([1, 2, 3, cab[dep] // 2, cab[dep], cab[dep] + 5])
        out.append("- %s: %d cabinets out of service from %s to %s" % (dep, n, tm(a), tm(b)))
    add_notice(d, "## Cabinet outages", out)


def m_derates(d, rng):
    """R11 :23 + R2 :8 several derate lines, off-grid spans, limits above base (replaced by), spans past the day.
    Overlapping derate lines are left out (docs do not say which wins)."""
    pd, first, end = plan(d)
    base = int(re.search(r"feeder_kwh_per_slot = (\d+)", rd(d, "grid.ini")).group(1))
    t = rd(d, "disruption_notice.md")
    used = []
    for m in re.finditer(r"^- from (\S+) to (\S+): feeder", t, re.M):
        used.append((datetime.strptime(m.group(1), ST), datetime.strptime(m.group(2), ST)))
    out = []
    for _ in range(rng.randint(2, 5)):
        a = first + timedelta(minutes=rng.randint(-30, 96 * 15))
        b = a + timedelta(minutes=rng.randint(1, 300))
        sa, sb = max(a, first), min(b, end)
        # slot level overlap test (slot start in [a, b))
        def slots(x, y):
            s = set()
            for i in range(96):
                st = first + timedelta(minutes=15 * i)
                if x <= st < y:
                    s.add(i)
            return s
        mine = slots(a, b)
        if any(mine & slots(x, y) for x, y in used):
            continue
        used.append((a, b))
        v = rng.choice([0, 15, base // 10, base // 2, base + rng.randint(1, 3000), 10 * base])
        out.append("- from %s to %s: feeder limit %d kWh per slot" % (tm(a), tm(b), v))
    if out:
        add_notice(d, "## Feeder derating", out)


def m_extras(d, rng):
    """R7 :16 extras only for the day after; buses not on plan, rejected buses, several per bus."""
    pd, first, end = plan(d)
    after = (date.fromisoformat(pd) + timedelta(days=1)).isoformat()
    h, rows = csv_rows(d, "roster.csv")
    on = [r[1] for r in rows if r[0] == pd]
    other = [r[1] for r in rows if r[0] != pd]
    out = []
    for _ in range(rng.randint(4, 10)):
        bus = rng.choice(on + other + ["B9990", "B0001"])
        when = rng.choice([after, after, pd, (date.fromisoformat(pd) + timedelta(days=2)).isoformat()])
        out.append("- %s: extra trip on %s, %d kWh" % (bus, when, rng.randint(1, 120)))
    add_notice(d, "## Extra trips", out)


def m_published(d, rng):
    """R13 :28 rows summed per slot, kWh above max rate, rows for buses not on plan; R14 :29 moved."""
    pd, first, end = plan(d)
    h, rows = csv_rows(d, "published_plan.csv")
    mine = [r for r in rows if r[0] == pd]
    add = []
    for r in rng.sample(mine, min(25, len(mine))):
        add.append([r[0], r[1], r[2], str(rng.randint(0, 80))])
    for r in rng.sample(mine, min(10, len(mine))):
        r[3] = str(int(r[3]) + rng.randint(20, 90))
    rows = rows + add
    rng.shuffle(rows)
    csv_write(d, "published_plan.csv", h, rows)


def m_tariff_switch(d, rng):
    """R12 :27 version in force on the plan date prices every slot, also slots after midnight when a new version starts the day after."""
    pd, first, end = plan(d)
    t = rd(d, "tariff.xml")
    m = re.search(r'<version valid_from="%s" valid_to="(\S+)">' % pd, t)
    nxt = (date.fromisoformat(pd) + timedelta(days=1)).isoformat()
    t = t.replace(m.group(0), '<version valid_from="%s" valid_to="%s">' % (pd, pd))
    bands = ['    <band from="00:00" to="06:00" cents_per_kwh="%d"/>' % rng.randint(1, 9),
             '    <band from="06:00" to="00:00" cents_per_kwh="%d"/>' % rng.randint(40, 90)]
    new = '  <version valid_from="%s" valid_to="%s">\n%s\n  </version>\n' % (nxt, m.group(1), "\n".join(bands))
    t = t.replace("</tariff>", new + "</tariff>")
    wr(d, "tariff.xml", t)


def m_flat_price(d, rng):
    """R15 :33 massive ties: current version one flat price (possibly 0); class weights 0..7. Settlements use older versions only."""
    pd, first, end = plan(d)
    t = rd(d, "tariff.xml")
    i = t.index('<version valid_from="%s"' % pd)
    j = t.index("</version>", i)
    blk = t[i:j]
    p = rng.choice([0, 1, 20])
    blk2 = re.sub(r'cents_per_kwh="\d+"', 'cents_per_kwh="%d"' % p, blk)
    if rng.random() < 0.5:  # one cheap band too
        blk2 = blk2.replace('cents_per_kwh="%d"' % p, 'cents_per_kwh="%d"' % (p + 3), 1)
    wr(d, "tariff.xml", t[:i] + blk2 + t[j:])
    w = rd(d, "service_classes.ini")
    w = re.sub(r"\[public\]\nweight = \d+", "[public]\nweight = %d" % rng.choice([1, 2, 4, 7]), w)
    w = re.sub(r"\[commercial\]\nweight = \d+", "[commercial]\nweight = %d" % rng.choice([0, 1, 1, 3]), w)
    wr(d, "service_classes.ini", w)


def m_contracts(d, rng):
    """R8 :17 blank or unlisted contract -> commercial."""
    pd, *_ = plan(d)
    h, rows = csv_rows(d, "roster.csv")
    for r in rows:
        if r[0] == pd and rng.random() < 0.3:
            r[6] = rng.choice(["", "ZZZ-99", "SCH-99"])
    csv_write(d, "roster.csv", h, rows)


def m_soc(d, rng):
    """R7 :16 need clamp at 0, soc above need; R17 :40 unmet_reason window vs supply with tight windows."""
    pd, first, end = plan(d)
    h, rows = csv_rows(d, "roster.csv")
    for r in rows:
        if r[0] != pd:
            continue
        x = rng.random()
        if x < 0.2:
            r[5] = str(int(r[5]) + rng.randint(50, 500))
        elif x < 0.4:
            a = datetime.strptime(r[3], ST)
            r[4] = tm(a + timedelta(minutes=15 * rng.randint(1, 3)))
        elif x < 0.5:
            r[5] = "0"
    csv_write(d, "roster.csv", h, rows)


def m_first_slot(d, rng):
    """R1 :7 other slots count / first_slot on the 15 min grid (k stays 0..95, prices by time of day)."""
    t = rd(d, "grid.ini")
    pd, first, end = plan(d)
    choice = rng.choice(["fewer", "later"])
    if choice == "fewer":
        t = t.replace("slots = 96", "slots = %d" % rng.randint(60, 90))
    else:
        nf = first + timedelta(minutes=15 * rng.randint(1, 8))
        t = t.replace("first_slot = %s" % tm(first), "first_slot = %s" % tm(nf)).replace("slots = 96", "slots = %d" % rng.randint(80, 88))
    wr(d, "grid.ini", t)


def m_combo(d, rng):
    """All of the above that do not touch grid.ini, stacked."""
    for f in (m_roster_depot, m_offgrid, m_outages, m_derates, m_extras, m_published, m_contracts, m_soc, m_tariff_switch):
        if rng.random() < 0.6:
            f(d, rng)


def m_blank_lines(d, rng):
    """REFBUG probe, R21 :44 line = physical line in file: blank lines inside CSV files."""
    for n in ("roster.csv", "published_plan.csv"):
        lines = rd(d, n).splitlines()
        for _ in range(3):
            lines.insert(rng.randint(1, len(lines)), "")
        wr(d, n, "\n".join(lines) + "\n")


def m_offgrid_first(d, rng):
    """REFBUG probe, R1 :7 + R12 :27: first_slot off the 15 min clock grid (12:05); settlement sessions and
    published slots moved with it; tariff bands stay on HH:MM quarter hours, so a slot's price is the band
    holding its start time (+k slots)."""
    sh = rng.choice([1, 5, 7, 10, 14])
    t = rd(d, "grid.ini")
    pd, first, end = plan(d)
    wr(d, "grid.ini", t.replace("first_slot = %s" % tm(first), "first_slot = %s" % tm(first + timedelta(minutes=sh))))
    mv = lambda s: tm(datetime.strptime(s, ST) + timedelta(minutes=sh))
    h, rows = csv_rows(d, "settlements.csv")
    for r in rows:
        r[3], r[4] = mv(r[3]), mv(r[4])
    csv_write(d, "settlements.csv", h, rows)
    h, rows = csv_rows(d, "published_plan.csv")
    for r in rows:
        r[2] = mv(r[2])
    csv_write(d, "published_plan.csv", h, rows)


MUT = {k[2:]: v for k, v in globals().items() if k.startswith("m_")}


def one(args):
    mut, seed = args
    tmp = tempfile.mkdtemp(dir=os.path.join(HERE, "tmp"))
    try:
        data = os.path.join(tmp, "data")
        rng = random.Random(seed * 1009 + sum(map(ord, mut)))
        try:
            gen_core.render(seed, "large" if mut == "combo" and seed % 5 == 0 else "hidden", data)
            MUT[mut](data, rng)
        except Exception as e:
            return {"mut": mut, "seed": seed, "verdict": "GEN_FAIL", "first": repr(e)[:200]}
        rr, rs, re_ = F.run(["python3", "-B", REF, "--data", data], os.path.join(tmp, "ref"))
        ar, as_, ae = F.run(["python3", "-B", A2, "--data", data], os.path.join(tmp, "a2"))
        rec = {"mut": mut, "seed": seed, "ref_s": round(rs, 2), "a2_s": round(as_, 2)}
        if rr != 0 and ar != 0:
            rec.update(verdict="BOTH_FAIL", first=re_[-120:], a2err=ae[-120:])
        elif rr != 0:
            rec.update(verdict="REF_FAIL", first=re_)
        elif ar != 0:
            rec.update(verdict="A2_FAIL", first=ae)
        else:
            rec["verdict"] = "MATCH"
            rec["same"] = []
            for doc in F.DOCS:
                x = json.load(open(os.path.join(tmp, "ref", doc)))
                y = json.load(open(os.path.join(tmp, "a2", doc)))
                f = F.first_diff(x, y)
                if f:
                    if rec["verdict"] == "MATCH":
                        rec.update(verdict="DIFF", first=doc + f)
                else:
                    rec["same"].append(doc)
        if rec["verdict"] != "MATCH" and os.environ.get("KEEP"):
            keep = os.path.join(HERE, "keep", "%s_%d" % (mut, seed))
            shutil.rmtree(keep, ignore_errors=True)
            shutil.copytree(tmp, keep)
        return rec
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    mut, s0, n, jobs = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    muts = [m for m in MUT if m not in ("blank_lines", "offgrid_first")] if mut == "all" else [mut]
    with Pool(jobs) as pool:
        for rec in pool.imap_unordered(one, [(m, s) for m in muts for s in range(s0, s0 + n)]):
            print(json.dumps(rec), flush=True)
    print("ALL_DONE", mut, flush=True)
