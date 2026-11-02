"""Differential fuzz driver for metered-usage-rating-pipeline; runs inside the verifier image.
usage: python3 fz_mu.py <cases.jsonl> <results.jsonl> <workers>
case: {"id","profile","seed","month","rows","accts","hidden","muts":[..],"struct":"none|shuffle|renamed|nested|cwdroot|readonly|tierscale|poolhalf"}
Corpus = T.gen_month(...) then text-level mutations (each contract-valid), controls recounted,
expected = T.ref_compute(files). Agent and oracle run as nobody with sys.executable -I.
"""
import datetime as dt, json, os, random, re, shutil, subprocess, sys, tempfile, time, configparser
from multiprocessing import Pool
from pathlib import Path
sys.path.insert(0, "/tests")
import test_output as T


# harden r2: the shipped generator is bounded (1000 tries); no patch here.

AGENT = "/progs/agent/transform.py"
ORACLE = "/progs/oracle/solve.py"
MUTANTS = {m: "/progs/%s/transform.py" % m for m in ("mut_mu6", "mut_mu5", "mut_mu7")}
UTC = dt.timezone.utc
FILES = T.GEN_FILES
PREFIX = T.GEN_PREFIX


def diffs(p, w, path="$", out=None):
    out = [] if out is None else out
    if isinstance(w, dict) and isinstance(p, dict):
        for k in list(w) + [k for k in p if k not in w]:
            if k not in p or k not in w:
                out.append((path + "." + k, "only-one"))
            else:
                diffs(p[k], w[k], path + "." + k, out)
        return out
    if isinstance(w, list) and isinstance(p, list):
        for i, (a, b) in enumerate(zip(p, w)):
            diffs(a, b, "%s[%d]" % (path, i), out)
        if len(p) != len(w):
            out.append((path, "len %d vs %d" % (len(p), len(w))))
        return out
    if p != w or type(p) is not type(w):
        out.append((path, "%r vs %r" % (p, w)))
    return out


def keyed(p, w):
    """normalized.jsonl compared by (region, record_id) field by field, plus order."""
    out = []
    pk = {(r.get("region"), r.get("record_id")): r for r in p if isinstance(r, dict)}
    wk = {(r["region"], r["record_id"]): r for r in w}
    for k, r in wk.items():
        if k not in pk:
            out.append(("%s/%s" % k, "missing"))
            continue
        for f, v in r.items():
            if pk[k].get(f) != v or type(pk[k].get(f)) is not type(v):
                out.append(("%s/%s.%s" % (k[0], k[1], f), "%r vs %r" % (pk[k].get(f), v)))
    for k in pk:
        if k not in wk:
            out.append(("%s/%s" % k, "extra"))
    po = [(r.get("region"), r.get("record_id")) for r in p if isinstance(r, dict)]
    wo = [(r["region"], r["record_id"]) for r in w]
    if [x for x in po if x in wk] != [x for x in wo if x in pk]:
        out.append(("$order", "rating order differs"))
    return out


# ---------- corpus helpers ----------
def month_bounds(month):
    y, m = int(month[:4]), int(month[5:7])
    s = dt.datetime(y, m, 1, tzinfo=UTC)
    e = dt.datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=UTC)
    return s, e


def render_line(region, rid, ts, acct, pname, u, offset=0, site="Zürich"):
    if region == "central":
        return ",".join((rid, ts.strftime("%Y-%m-%d %H:%M:%S"), acct, pname, u))
    if region == "east":
        return "\t".join((rid, str(int(ts.timestamp())), acct, pname, u))
    if region == "north":
        return '{"id": "%s", "at": "%s", "acct": "%s", "sku": "%s", "units": %s}' % (
            rid, ts.strftime("%Y-%m-%dT%H:%M:%SZ"), acct, pname, u)
    if region == "south":
        line = rid.ljust(10) + ts.strftime("%Y%m%d%H%M%S") + acct.ljust(10) + pname.ljust(12) + u.rjust(6) + site.ljust(20)
        assert len(line) == 72, line
        return line
    off = dt.timezone(dt.timedelta(minutes=offset))
    return "%s rec=%s acct=%s product=%s qty=%s" % (ts.astimezone(off).isoformat(), rid, acct, pname, u)


class Corpus:
    def __init__(self, files):
        self.f = dict(files)
        ctl = json.loads(self.f["collector_controls.json"])
        self.month = ctl["month"]
        self.ms, self.me = month_bounds(self.month)
        cp = configparser.ConfigParser(interpolation=None)
        cp.optionxform = str
        cp.read_string(self.f["products.ini"].decode())
        self.names = {c: {r: cp[c][r].strip() for r in T.REF_REGIONS} for c in cp.sections()}
        rows = self.f["accounts.csv"].decode().splitlines()[1:]
        self.accts = [r.split(",")[0] for r in rows if r.strip()]
        self.n = 0

    def enc(self, region):
        return "latin-1" if region == "south" else "utf-8"

    def lines(self, region):
        return self.f[FILES[region]].decode(self.enc(region)).split("\n")[:-1]

    def set_lines(self, region, lines):
        self.f[FILES[region]] = ("\n".join(lines) + "\n").encode(self.enc(region))

    def add(self, region, ts, acct=None, code=None, u=None, rid=None, offset=0, pname=None, rng=None):
        self.n += 1
        rng = rng or random
        rid = rid or "%s-9%05d" % (PREFIX[region], self.n)
        acct = acct or rng.choice(self.accts)
        code = code or rng.choice(T.REF_PRODUCTS)
        pname = pname if pname is not None else self.names[code][region]
        u = u if u is not None else str(rng.randint(1, 999))
        ls = self.lines(region)
        ls.append(render_line(region, rid, ts, acct, pname, u, offset))
        self.set_lines(region, ls)
        return rid

    def recount(self):
        ctl = json.loads(self.f["collector_controls.json"])
        for r in T.REF_REGIONS:
            ls = [x for x in self.lines(r) if x.strip()]
            ctl["collectors"][r]["records"] = len(ls) - (1 if r in ("central", "east") else 0)
        self.f["collector_controls.json"] = (json.dumps(ctl, indent=2) + "\n").encode()

    def rand_ts(self, rng):
        return self.ms + dt.timedelta(seconds=rng.randrange(int((self.me - self.ms).total_seconds())))


def variant(rng, a):
    d = a[2:]
    return rng.choice(["ac" + d, "Ac" + d, "AC-" + d, "a-c" + d, "ac-%s-%s" % (d[:3], d[3:]), "-AC" + d, "AC" + d + "-"])


# ---------- mutations ----------
def m_edge(c, rng):
    for r in T.REF_REGIONS:
        for ts in (c.ms, c.me - dt.timedelta(seconds=1), c.me, c.ms - dt.timedelta(seconds=1)):
            offs = (0,) if r != "west" else (0, 330, -420, 840, -720, 345)
            for o in offs:
                c.add(r, ts, offset=o, rng=rng)


def m_acct(c, rng):
    for r in T.REF_REGIONS:
        for _ in range(12):
            a = variant(rng, rng.choice(c.accts))
            if r == "south" and len(a) > 10:
                a = a[:10]
            c.add(r, c.rand_ts(rng), acct=a, rng=rng)
    rows = c.f["accounts.csv"].decode().splitlines()
    for i in range(1, len(rows)):
        if rng.random() < 0.15:
            a, s, p, par = rows[i].split(",")
            rows[i] = ",".join((variant(rng, a), s, p, variant(rng, par) if par.strip() else par))
    c.f["accounts.csv"] = ("\n".join(rows) + "\n").encode()


def m_group(c, rng):
    """harden r2: plant billing groups (parent column) in any profile; parent spelled in variant forms."""
    rows = c.f["accounts.csv"].decode().splitlines()
    canon = lambda x: x.strip().upper().replace("-", "")
    used = set()
    for i in range(1, len(rows)):
        a, s, p, par = rows[i].split(",")
        if par.strip():
            used.add(canon(a)); used.add(canon(par))
    free = [i for i in range(1, len(rows)) if canon(rows[i].split(",")[0]) not in used]
    rng.shuffle(free)
    k = 0
    while k + 3 <= len(free) and k < len(free) * 0.4:
        head = rows[free[k]].split(",")[0]
        chain = [head]
        for j in free[k + 1:k + 1 + rng.randint(1, 3)]:
            a, s, p, par = rows[j].split(",")
            up = chain[-1] if rng.random() < .6 else rng.choice(chain)  # round 2: parent chains
            rows[j] = ",".join((a, s, p, variant(rng, up) if rng.random() < .5 else up))
            chain.append("AC" + canon(a)[2:])  # canonical spelling, so variant() applies to it
        k += 5
    c.f["accounts.csv"] = ("\n".join(rows) + "\n").encode()
    # heavy usage by grouped accounts so counters cross tier bounds
    for _ in range(40):
        c.add(rng.choice(T.REF_REGIONS), c.rand_ts(rng), acct=rows[rng.choice(free[:max(1, k)])].split(",")[0],
              u=str(rng.randint(300, 999)), rng=rng)


def m_quoted(c, rng):
    """harden r2: north units as JSON strings (quoted digits) on heavy lines."""
    for _ in range(30):
        c.add("north", c.ms + dt.timedelta(seconds=rng.randrange(5 * 86400)), u=rng.choice(['"%d"', '" %d"', '"%d "']) % rng.randint(300, 999), rng=rng)


def m_units_ok(c, rng):
    for r in ("central", "east", "south", "west"):
        for tok in ("007", "0999", "000001", "0042"):
            if r == "south" and len(tok) > 6:
                continue
            c.add(r, c.rand_ts(rng), u=tok, rng=rng)
    for r in ("central", "east"):
        for tok in (" 12", "13 ", "  7  "):
            c.add(r, c.rand_ts(rng), u=tok, rng=rng)
    for tok in ("  15", "    9"):
        c.add("south", c.rand_ts(rng), u=tok, rng=rng)


def m_units_bad(c, rng):
    toks = {"central": ["+5", "1_2", "\u0661\u0662", "\uff11\uff12", "12 3", "0x1F", "\u00b2"],
            "east": ["+5", "1_2", "\u0663", "\uff17", "4 4"],
            "west": ["+5", "1_2", "\u0661\u0662", "\uff11\uff12"],
            "south": ["+5", "1_2", "\u00b2", "\u00b3", "\u00b9", "1 2"],
            "north": ["[5]", '{"v": 5}', "5.0", "12E0", "-0.0", "5e0"]}
    for r, ts_ in toks.items():
        for tok in ts_:
            c.add(r, c.rand_ts(rng), u=tok, rng=rng)


def m_dupconf(c, rng):
    for r in T.REF_REGIONS:
        ls = c.lines(r)
        body = 1 if r in ("central", "east") else 0
        for _ in range(4):
            i = rng.randrange(body, len(ls))
            rid = extract_rid(r, ls[i])
            # later record with same id but different content (valid other account/units)
            c.add(r, c.rand_ts(rng), rid=rid, rng=rng)
        # quarantined first, valid duplicate later
        rid = "%s-8%05d" % (PREFIX[r], rng.randrange(99999))
        c.add(r, c.ms - dt.timedelta(hours=3), rid=rid, rng=rng)
        c.add(r, c.rand_ts(rng), rid=rid, rng=rng)
    # same record_id in two different files: not a duplicate
    rid = "XRF-000001"
    for r in T.REF_REGIONS:
        c.add(r, c.rand_ts(rng), rid=rid, rng=rng)


def extract_rid(r, line):
    if r == "central":
        return line.split(",")[0].strip()
    if r == "east":
        return line.split("\t")[0].strip()
    if r == "north":
        return json.loads(line)["id"].strip()
    if r == "south":
        return line[:10].strip()
    return re.search(r"rec=(\S+)", line).group(1)


def m_ties(c, rng):
    ts = c.rand_ts(rng)
    a = rng.choice(c.accts)
    for r in T.REF_REGIONS:
        for rid in ("%s-10" % PREFIX[r], "%s-9" % PREFIX[r], "%s-000002" % PREFIX[r], "%s-1" % PREFIX[r].lower()):
            c.add(r, ts, acct=a, code="CMP", rid=rid, rng=rng)


def m_tier(c, rng):
    card = json.loads(c.f["rate_card.json"].decode(), parse_float=str)
    txt = c.f["rate_card.json"].decode()
    for code in T.REF_PRODUCTS:
        tiers = card["products"][code]["tiers"]
        if rng.random() < 0.5:
            a, b = rng.choice([(1, 2), (1, 999), (999, 1000), (2, 3)])
            txt = replace_from(txt, code, tiers[1]["from"], a)
            txt = replace_from(txt, code, tiers[2]["from"], b)
    c.f["rate_card.json"] = txt.encode()


def replace_from(txt, code, old, new):
    i = txt.index('"%s"' % code)
    j = txt.index('"from": %d,' % old, i)
    return txt[:j] + '"from": %d,' % new + txt[j + len('"from": %d,' % old):]


def m_tier_unsorted(c, rng):
    txt = c.f["rate_card.json"].decode().split("\n")
    out, buf = [], []
    for ln in txt:
        if ln.strip().startswith('{"tier"'):
            buf.append(ln.rstrip(","))
            continue
        if buf:
            rng.shuffle(buf)
            out += [b + ("," if k < len(buf) - 1 else "") for k, b in enumerate(buf)]
            buf = []
        out.append(ln)
    c.f["rate_card.json"] = "\n".join(out).encode()


def m_pool(c, rng):
    c.recount()
    docs = T.ref_compute(c.f)
    xml = c.f["commitments.xml"].decode()
    for r in T.REF_REGIONS:
        base = int(docs["region_%s.json" % r]["credit_base"].replace(".", ""))
        pick = rng.choice(["zero", "max", "keep", "one", "over", "equal"])
        if pick == "keep":
            continue
        pool = {"zero": 0, "one": 1, "max": (base - 1) // 2, "over": base + 1, "equal": base}[pick]
        xml = re.sub(r'(<pool region="%s" amount=")[0-9.]+"' % r, lambda m: m.group(1) + '%d.%02d"' % (pool // 100, pool % 100), xml)
    c.f["commitments.xml"] = xml.encode()


def m_plan(c, rng):
    pc = c.f["plan_changes.log"].decode().split("\n")[:-1]
    # changes exactly at usage timestamps, several same-ts changes, variant spellings
    for r in T.REF_REGIONS:
        for _ in range(6):
            ts = c.rand_ts(rng)
            a = rng.choice(c.accts)
            c.add(r, ts, acct=a, rng=rng)
            for k in range(rng.randint(1, 3)):
                f = rng.choice([" plan=%s" % rng.choice(("committed", "payg")), " segment=%s" % rng.choice(T.REF_SEGMENTS),
                                " plan=%s segment=%s" % (rng.choice(("committed", "payg")), rng.choice(T.REF_SEGMENTS))])
                pc.append("%s change account=%s%s" % (ts.strftime("%Y-%m-%dT%H:%M:%SZ"), variant(rng, a) if rng.random() < .5 else a, f))
    pc.sort(key=lambda s: s[:20])  # stable: keeps file order within a timestamp
    c.f["plan_changes.log"] = ("\n".join(pc) + "\n").encode()


def m_pc_unsorted(c, rng):
    pc = c.f["plan_changes.log"].decode().split("\n")[:-1]
    groups = {}
    for ln in pc:
        groups.setdefault(ln[:20], []).append(ln)
    keys = list(groups)
    rng.shuffle(keys)
    c.f["plan_changes.log"] = ("\n".join(l for k in keys for l in groups[k]) + "\n").encode()


def m_offsets(c, rng):
    for _ in range(20):
        c.add("west", c.rand_ts(rng), offset=rng.choice((840, -720, 345, -570, 765, 0)), rng=rng)


def m_pad(c, rng):
    for r in ("central", "east"):
        ls = c.lines(r)
        sep = "," if r == "central" else "\t"
        for i in range(1, len(ls)):
            if rng.random() < 0.3:
                ls[i] = sep.join(" " + x + "  " for x in ls[i].split(sep))
        c.set_lines(r, ls)
    ls = c.lines("north")
    for i in range(len(ls)):
        if rng.random() < 0.3:
            o = json.loads(ls[i])
            ls[i] = '{"id": " %s ", "at": "%s", "acct": "  %s", "sku": " %s ", "units": %s}' % (
                o["id"], o["at"], o["acct"], o["sku"], json.dumps(o["units"]))
    c.set_lines("north", ls)


def m_zero_product(c, rng):
    code = rng.choice(T.REF_PRODUCTS)
    for r in T.REF_REGIONS:
        name = c.names[code][r]
        ls = c.lines(r)
        keep = []
        for i, ln in enumerate(ls):
            if r in ("central", "east") and i == 0:
                keep.append(ln)
                continue
            if product_of(r, ln) == name:
                continue
            keep.append(ln)
        c.set_lines(r, keep)


def product_of(r, line):
    if r == "central":
        return line.split(",")[3].strip()
    if r == "east":
        return line.split("\t")[3].strip()
    if r == "north":
        return json.loads(line)["sku"].strip()
    if r == "south":
        return line[34:46].strip()
    return re.search(r"product=(\S+)", line).group(1)


def counted(c, docs, r):
    canon = lambda x: x.strip().upper().replace("-", "")
    plan = {canon(row.split(",")[0]): row.split(",")[2].strip() for row in c.f["accounts.csv"].decode().splitlines()[1:]}
    return [int(l["charge"].replace(".", "")) for l in docs["normalized.jsonl"] if l["region"] == r and plan.get(l["account_id"]) == "committed"]


def set_attr(c, r, attr, cents):
    xml = c.f["commitments.xml"].decode()
    xml, n = re.subn(r'(<pool region="%s"[^>]*? %s=")[0-9.]+"' % (r, attr), lambda m: m.group(1) + '%d.%02d"' % (cents // 100, cents % 100), xml)
    assert n == 1, (r, attr)
    c.f["commitments.xml"] = xml.encode()


def m_sep(c, rng):
    """round 2 LV-MU-6: pool between the summed charge of the lines that hold 0.50 and the base."""
    c.recount()
    docs = T.ref_compute(c.f)
    for r in rng.sample(list(T.REF_REGIONS), rng.randint(1, 3)):
        ch = counted(c, docs, r)
        base = sum(ch)
        if base < 2:
            continue
        sub0 = sum(x for x in ch if T.ref_cents(T._RF(x * (base - 1), base * 100)) < 50)
        if sub0 < 2:
            continue
        set_attr(c, r, "amount", base - sub0 // 2)


def m_short(c, rng):
    """round 2 LV-MU-7: minimum above the credit base."""
    c.recount()
    docs = T.ref_compute(c.f)
    for r in rng.sample(list(T.REF_REGIONS), rng.randint(1, 3)):
        base = sum(counted(c, docs, r))
        set_attr(c, r, "minimum", base + max(1, int(base * rng.uniform(0.05, 0.8))))


MUTS = {"edge": m_edge, "acct": m_acct, "units_ok": m_units_ok, "units_bad": m_units_bad, "dupconf": m_dupconf,
        "ties": m_ties, "tier": m_tier, "tier_unsorted": m_tier_unsorted, "pool": m_pool, "plan": m_plan,
        "pc_unsorted": m_pc_unsorted, "offsets": m_offsets, "pad": m_pad, "zero_product": m_zero_product,
        "group": m_group, "quoted": m_quoted, "sep": m_sep, "short": m_short}
POST = ("pool", "sep", "short")


def shuffle_rows(c, rng):
    for r in T.REF_REGIONS:
        ls = c.lines(r)
        h = 1 if r in ("central", "east") else 0
        body = ls[h:]
        rng.shuffle(body)
        c.set_lines(r, ls[:h] + body)


def tier_scale(c, rng):
    txt = c.f["rate_card.json"].decode()
    def rep(m):
        v = int(m.group(1))
        return '"from": %d,' % (-(-v * 10375 // 10000) if v > 0 else 0)
    c.f["rate_card.json"] = re.sub(r'"from": (\d+),', rep, txt).encode()


def build(case):
    rng = random.Random(case["seed"] * 7 + 1)
    files = T.gen_month(case["seed"], case["month"], case["rows"], case["accts"], case["hidden"], T.ref_compute)
    c = Corpus(files)
    st = case.get("struct", "none")
    if st == "shuffle":
        shuffle_rows(c, rng)
    if st == "tierscale":
        tier_scale(c, rng)
    muts = case.get("muts", [])
    for m in [m for m in muts if m not in POST]:
        MUTS[m](c, rng)
    c.recount()
    for m in [m for m in POST if m in muts]:
        MUTS[m](c, rng)
    c.recount()
    if st == "poolhalf":
        docs = T.ref_compute(c.f)
        xml = c.f["commitments.xml"].decode()
        for r in T.REF_REGIONS:
            base = int(docs["region_%s.json" % r]["credit_base"].replace(".", ""))
            p = base * 3 // 7
            xml = re.sub(r'(<pool region="%s" amount=")[0-9.]+"' % r, lambda m: m.group(1) + '%d.%02d"' % (p // 100, p % 100), xml)
        c.f["commitments.xml"] = xml.encode()
    return c.f


def fix_pools(c, rng):
    docs = T.ref_compute(c.f)
    xml = c.f["commitments.xml"].decode()
    for r in T.REF_REGIONS:
        base = int(docs["region_%s.json" % r]["credit_base"].replace(".", ""))
        pool = int(re.search(r'region="%s" amount="([0-9.]+)"' % r, xml).group(1).replace(".", ""))
        if pool * 2 >= base:
            p = int(base * rng.uniform(0.2, 0.45))
            xml = re.sub(r'(<pool region="%s" amount=")[0-9.]+"' % r, lambda m: m.group(1) + '%d.%02d"' % (p // 100, p % 100), xml)
    c.f["commitments.xml"] = xml.encode()


def bounds_ok(files, docs):
    return None  # round 2: pools and minimums are free (both credit branches and the true-up are graded)
    xml = files["commitments.xml"].decode()
    for r in T.REF_REGIONS:
        pool = int(re.search(r'region="%s" amount="([0-9.]+)"' % r, xml).group(1).replace(".", ""))
        base = int(docs["region_%s.json" % r]["credit_base"].replace(".", ""))
        if not (pool * 2 < base):
            return "pool %d not < half base %d in %s" % (pool, base, r)
    return None


def run(prog, files, st):
    work = Path(tempfile.mkdtemp(prefix="fz-"))
    src = work / ("in put ünï" if st == "renamed" else "extract")
    src.mkdir()
    for n, b in files.items():
        (src / n).write_bytes(b)
    tgt = work / ("a/b/reports" if st == "nested" else "reports")
    cwd = work / "elsewhere"
    cwd.mkdir()
    T._open_tree(work)
    if st == "readonly":
        for p in src.iterdir():
            p.chmod(0o444)
        src.chmod(0o555)
    if st == "cwdroot":
        cwd = Path("/")
    t0 = time.time()
    try:
        p = subprocess.run([*T._SETPRIV, sys.executable, "-I", prog, "--input", str(src), "--output", str(tgt)],
                           cwd=str(cwd), capture_output=True, text=True, timeout=T.RUN_LIMIT_SEC)
        code, err = p.returncode, p.stderr[-600:]
    except subprocess.TimeoutExpired:
        code, err = None, "timeout"
    secs = round(time.time() - t0, 2)
    docs = {}
    for n in T.DOCUMENTS:
        try:
            docs[n] = T._load(tgt, n)
        except Exception as e:
            docs[n] = "<unreadable %s>" % type(e).__name__
    shutil.rmtree(work, ignore_errors=True)
    return code, err, secs, docs


def compare(docs, want):
    d = {}
    for n in T.DOCUMENTS:
        g = docs[n]
        if isinstance(g, str):
            d[n] = [["$", g]]
            continue
        if n == "normalized.jsonl":
            x = keyed(g, want[n])
        else:
            x = diffs(g, want[n])
        if x:
            d[n] = [list(e) for e in x[:60]] + ([["...", "%d total" % len(x)]] if len(x) > 60 else [])
    return d


def one(case):
    t0 = time.time()
    rec = dict(case)
    try:
        files = build(case)
        want = T.ref_compute(files)
    except (AssertionError, T.RefStop, ValueError, KeyError) as e:
        rec["gen_error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
        return rec
    bad = bounds_ok(files, want)
    if bad:
        rec["gen_error"] = "OOB " + bad
        return rec
    rec["lines"] = len(want["normalized.jsonl"])
    st = case.get("struct", "none")
    for who, prog in (("agent", AGENT), ("oracle", ORACLE)) + tuple(MUTANTS.items()):
        code, err, secs, docs = run(prog, files, st)
        d = compare(docs, want)
        fc = {}
        if isinstance(docs["normalized.jsonl"], list):
            for path, _ in keyed(docs["normalized.jsonl"], want["normalized.jsonl"]):
                f = path.rsplit(".", 1)[-1] if "." in path else path
                fc[f] = fc.get(f, 0) + 1
        if who.startswith("mut_"):
            rec[who] = {"code": code, "secs": secs, "ndocs": len(d), "docs": sorted(d), "fields": fc}
        else:
            rec[who] = {"code": code, "err": err if code else "", "secs": secs, "ndocs": len(d), "docs": sorted(d), "fields": fc}
    rec["wall"] = round(time.time() - t0, 1)
    return rec


def main():
    cases = [json.loads(l) for l in open(sys.argv[1])]
    out = sys.argv[2]
    done = set()
    if os.path.exists(out):
        done = {json.loads(l)["id"] for l in open(out) if l.strip()}
    todo = [c for c in cases if c["id"] not in done]
    with Pool(int(sys.argv[3])) as pool, open(out, "a") as fh:
        for rec in pool.imap_unordered(one, todo):
            fh.write(json.dumps(rec) + "\n")
            fh.flush()


if __name__ == "__main__":
    if sys.argv[1] == "--one":
        print(json.dumps(one(json.loads(sys.argv[2])), indent=1)[:6000])
    else:
        main()
