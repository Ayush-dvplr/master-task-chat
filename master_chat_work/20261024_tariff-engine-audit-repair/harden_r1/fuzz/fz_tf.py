"""Differential fuzz driver for tariff-engine-audit-repair; runs inside the verifier image.
usage: python3 fz_tf.py <cases.jsonl> <results.jsonl> <workers>   |  --one '<case json>'
case: {"id","profile","seed","size","reuse":[..],"muts":[..],"struct":"none|shuffle|rotated|relocated|api|cwdroot|readonly|rescaled|crlf|missing"}
Corpus = T._corpus(seed,size,reuse) (hidden-tier generator), then contract-valid mutations,
expected = T._Ledger(texts).document(). Agent and oracle patched-repo.zip run as nobody like _cli.
"""
import json, os, random, re, shutil, subprocess, sys, tempfile, time, zipfile
from datetime import date, timedelta
from multiprocessing import Pool
from pathlib import Path
sys.path.insert(0, "/tests")
import test_output as T

AGENT = "/progs/agent/patched-repo.zip"
ORACLE = "/fz/oracle_tf/patched-repo.zip"
_Q = re.compile(r'"quantity": (.*)\}$')


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


class C:
    """Structured corpus: reads (dicts with raw quantity text), meters, periods, card."""

    def __init__(self, texts, info):
        self.reads = []
        for ln in texts["meter_reads.jsonl"].splitlines():
            o = json.loads(ln)
            o["quantity"] = _Q.search(ln).group(1)
            self.reads.append(o)
        self.meters = [ln.split(",") for ln in texts["accounts.csv"].splitlines()[1:]]
        self.periods = [ln.split(",") for ln in texts["billing_periods.csv"].splitlines()[1:]]
        self.card = {n: {"standing": T._amount(p["standing"]), "credit": p["credit"],
                         "tiers": [["null" if c is None else str(c), T._rate_text(r)] for c, r in p["tiers"]]}
                     for n, p in info["plans"].items()}
        self.ahead = "account,meter,active_from,active_to"
        self.phead = "account,start,end,plan,commitment"
        self.nl = "\n"
        self.n = 0

    def rid(self):
        self.n += 1
        return "X%05d" % self.n

    def texts(self):
        nl = self.nl
        reads = "".join('{"read_id": %s, "account": %s, "meter": %s, "day": %s, "quantity": %s}%s' % (
            json.dumps(r["read_id"], ensure_ascii=False), json.dumps(r["account"], ensure_ascii=False),
            json.dumps(r["meter"], ensure_ascii=False), json.dumps(r["day"]), r["quantity"], nl) for r in self.reads)
        parts = []
        for name, p in self.card.items():
            tiers = ", ".join('{"up_to": %s, "rate": %s}' % (c, r) for c, r in p["tiers"])
            parts.append('    %s: {"standing_charge": %s, "credit_rate": %s, "tiers": [%s]}' % (
                json.dumps(name), p["standing"], p["credit"], tiers))
        card = '{\n  "currency": "EUR",\n  "plans": {\n' + ",\n".join(parts) + "\n  }\n}\n"
        return {"meter_reads.jsonl": reads,
                "accounts.csv": self.ahead + nl + "".join(",".join(m) + nl for m in self.meters),
                "billing_periods.csv": self.phead + nl + "".join(",".join(p) + nl for p in self.periods),
                "rate_card.json": card}

    def period(self, acct):
        p = next(p for p in self.periods if p[0].strip() == acct)
        return date.fromisoformat(p[1].strip()), date.fromisoformat(p[2].strip())

    def own(self, acct):
        return [m for m in self.meters if m[0].strip() == acct]

    def add(self, acct, meter, day, q):
        r = {"read_id": self.rid(), "account": acct, "meter": meter, "day": day.isoformat(), "quantity": q}
        self.reads.append(r)
        return r


def accts(c):
    return [p[0].strip() for p in c.periods]


def m_edge(c, rng):
    for a in rng.sample(accts(c), min(6, len(accts(c)))):
        s, e = c.period(a)
        ms = c.own(a)
        m = rng.choice(ms)
        k = rng.randrange(5)
        if k == 0:
            m[2], m[3] = s.isoformat(), e.isoformat()
        elif k == 1:
            m[2], m[3] = e.isoformat(), ""
        elif k == 2:
            m[2], m[3] = (s - timedelta(days=40)).isoformat(), s.isoformat()
        elif k == 3:
            m[2], m[3] = (s - timedelta(days=40)).isoformat(), (s - timedelta(days=1)).isoformat()
        else:
            m[2], m[3] = (e + timedelta(days=1)).isoformat(), ""
        f = date.fromisoformat(m[2])
        t = date.fromisoformat(m[3]) if m[3] else None
        for d in {s, e, f, f - timedelta(days=1), s - timedelta(days=1), e + timedelta(days=1)} | ({t, t + timedelta(days=1)} if t else set()):
            c.add(a, m[1].strip(), d, str(rng.randrange(1, 400)))


def m_span(c, rng):
    for p in rng.sample(c.periods, min(6, len(c.periods))):
        y = rng.choice([2026, 2027, 2028])
        span = rng.choice([1, 2, 28, 29, 30, 31, 62, 59, 60])
        s = rng.choice([date(y, 1, 31), date(y, 2, 1), date(y, 2, 27), date(y, 12, 15), date(y, 1, 1),
                        date(2028, 2, 28), date(y, 3, 1), date(y, 11, 30)])
        e = s + timedelta(days=span - 1)
        old_s = date.fromisoformat(p[1].strip())
        p[1], p[2] = s.isoformat(), e.isoformat()
        a = p[0].strip()
        for m in c.own(a):  # keep meters plausibly active around the new period
            if rng.random() < 0.7:
                m[2] = (s - timedelta(days=rng.randrange(0, 50))).isoformat()
                if m[3]:
                    m[3] = (s + timedelta(days=rng.randrange(0, span + 3))).isoformat()
        delta = s - old_s
        for r in c.reads:
            if r["account"].strip() == a and rng.random() < 0.8:
                r["day"] = (date.fromisoformat(r["day"].strip()) + delta).isoformat()


def m_qty(c, rng):
    good = ["0", "-0", "1000000000", "999999999999", "1", "007" if False else "70"]
    bad = ["1.0", "0.0", "1e0", "1E+2", "-1", "-0.0", "1.5e-3", '"5"', '" 7 "', "true", "false", "null", "-12", "10E0", "0e0", '""']
    for a in rng.sample(accts(c), min(8, len(accts(c)))):
        s, e = c.period(a)
        ms = c.own(a)
        if not ms:
            continue
        for _ in range(4):
            m = rng.choice(ms)
            q = rng.choice(good + bad)
            c.add(a, m[1].strip(), s + timedelta(days=rng.randrange((e - s).days + 1)), q)


def m_dup(c, rng):
    for a in rng.sample(accts(c), min(8, len(accts(c)))):
        s, e = c.period(a)
        ms = [m for m in c.own(a) if not m[3]]
        if not ms:
            continue
        m = rng.choice(ms)[1].strip()
        d = s + timedelta(days=rng.randrange((e - s).days + 1))
        k = rng.randrange(4)
        if k == 0:  # exception first, then a valid read: second is accepted
            c.add(a, m, d, rng.choice(["null", "2.5", '"9"', "-3"]))
            c.add(a, m, d, str(rng.randrange(1, 90)))
            c.add(a, m, d, str(rng.randrange(1, 90)))
        elif k == 1:  # same key, padded strings
            r = c.add(a, m, d, "11")
            r2 = c.add(a, " %s " % m, d, "12")
            r2["account"] = "%s " % a
        elif k == 2:  # same day other meter is not a duplicate
            for mm in c.own(a):
                c.add(a, mm[1].strip(), d, "5")
        else:  # triple
            for q in ("3", "4", "0"):
                c.add(a, m, d, q)


def m_ids(c, rng):
    pool = ["h10", "H9", "H10", "a1", "Z", "H010", "É1", "h-2", "H_3", "H 4", "0001", "~1", "ß", "H10a"]
    rng.shuffle(pool)
    rs = rng.sample(c.reads, min(len(pool), len(c.reads)))
    taken = {r["read_id"].strip() for r in c.reads}
    for r, new in zip(rs, pool):
        if new not in taken:
            r["read_id"] = (" " if rng.random() < 0.3 else "") + new
            taken.add(new)


def m_acctids(c, rng):
    """New accounts whose ids test string ordering and non-ASCII text."""
    for name in ("a0001", "A0001a", "Ä100", "B-77", "0099", "z1"):
        s = date(2027, 3, rng.randrange(2, 20))
        e = s + timedelta(days=rng.choice([27, 31, 40]) - 1)
        plan = rng.choice(list(c.card))
        c.periods.append([name, s.isoformat(), e.isoformat(), plan, rng.choice(["0.00", "10.00", "999999.99"])])
        for j in range(rng.randrange(1, 3)):
            mid = "%sM%d" % (name, j)
            c.meters.append([name, mid, (s - timedelta(days=5)).isoformat(), ""])
            for _ in range(3):
                c.add(name, mid, s + timedelta(days=rng.randrange((e - s).days + 1)), str(rng.randrange(1, 900)))


def m_pad(c, rng):
    for rows in (c.meters, c.periods):
        for row in rows:
            for i in range(len(row)):
                if row[i] and rng.random() < 0.3:
                    row[i] = " " * rng.randrange(1, 3) + row[i] + " " * rng.randrange(0, 3)
    for r in c.reads:
        if rng.random() < 0.2:
            r["day"] = " %s " % r["day"]


def m_padhead(c, rng):
    c.ahead = "account, meter, active_from, active_to"
    c.phead = " account , start , end , plan , commitment "


def m_tiers(c, rng):
    for name, p in c.card.items():
        k = rng.randrange(6)
        if k == 0:
            p["tiers"] = [["null", rng.choice(["0.1234", "1", "0"])]]
        elif k == 1:
            p["tiers"] = [["0", "0.5000"], ["100", "0.2"], ["null", "0.1"]]
        elif k == 2:
            caps = sorted(rng.sample(range(1, 400), 4))
            p["tiers"] = [[str(cp), "%d.%08d" % (0, rng.randrange(10 ** 8))] for cp in caps] + [["null", "0.12345678"]]
        elif k == 3:
            p["tiers"] = [[t[0], t[1] + "0000"] for t in p["tiers"]]
        elif k == 4:
            p["tiers"] = [[t[0], "%s" % rng.choice(["0.105", "0.115", "0.125", "0.135", "0.145", "1", "2"])] for t in p["tiers"]]
        # k == 5 keep
    # quantities landing exactly on caps
    for a in rng.sample(accts(c), min(5, len(accts(c)))):
        plan = next(p[3].strip() for p in c.periods if p[0].strip() == a)
        caps = [int(t[0]) for t in c.card[plan]["tiers"] if t[0] != "null"]
        ms = [m for m in c.own(a) if not m[3]]
        if not caps or not ms:
            continue
        m = rng.choice(ms)[1].strip()
        s, e = c.period(a)
        used = {r["day"].strip() for r in c.reads if r["meter"].strip() == m and r["account"].strip() == a}
        have = None
        free = [s + timedelta(days=i) for i in range((e - s).days + 1) if (s + timedelta(days=i)).isoformat() not in used]
        if free:
            c.add(a, m, rng.choice(free), str(rng.choice(caps)))


def m_card(c, rng):
    for name, p in c.card.items():
        p["standing"] = rng.choice(["45", "0", "12.5", "0.01", "99.99", "1234.56", p["standing"]])
        p["credit"] = rng.choice(["0", "1", "0.5", "1.0", "0.0001", "0.9999", "0.25", p["credit"]])
    for row in c.periods:
        if rng.random() < 0.3:
            row[4] = rng.choice(["0.00", "0.01", "1000000.00"])


def m_nometer(c, rng):
    for name in ("N0001", "N0002"):
        s = date(2027, 5, 3)
        c.periods.append([name, s.isoformat(), (s + timedelta(days=32)).isoformat(), rng.choice(list(c.card)), "0.00"])
        c.add(name, "NM1", s, "10")


def m_shared(c, rng):
    """A meter id of one account also listed under another account (pairs are the key)."""
    a, b = rng.sample(accts(c), 2)
    ma = rng.choice(c.own(a))
    s, e = c.period(b)
    c.meters.append([b, ma[1].strip(), (s - timedelta(days=10)).isoformat(), ""])
    for _ in range(3):
        c.add(b, ma[1].strip(), s + timedelta(days=rng.randrange((e - s).days + 1)), str(rng.randrange(1, 300)))
    c.add(a, ma[1].strip(), s, "5")


def m_csvquote(c, rng):
    for rows in (c.meters, c.periods):
        for row in rows:
            if rng.random() < 0.3:
                i = rng.randrange(len(row))
                row[i] = '"%s"' % row[i]


def m_blank(c, rng):
    c.reads.insert(rng.randrange(len(c.reads)), None)


MUTS = {f.__name__[2:]: f for f in [m_edge, m_span, m_qty, m_dup, m_ids, m_acctids, m_pad, m_padhead, m_tiers,
                                    m_card, m_nometer, m_shared, m_csvquote, m_blank]}


def contract_ok(texts):
    """Input promises of api_contract.md that a mutation could break."""
    led = T._Ledger(texts)
    for a, (s, e, plan, com) in led.periods.items():
        if not (s <= e and 1 <= (e - s).days + 1 <= 62):
            return "span %s" % a
        if plan not in led.plans:
            return "plan %s" % plan
    ids = [json.loads(l)["read_id"].strip() for l in texts["meter_reads.jsonl"].splitlines() if l.strip()]
    if len(ids) != len(set(ids)):
        return "read ids"
    accts_ = {a for a, _ in led.windows}
    if not accts_ <= set(led.periods):
        return "account without period"
    return ""


def build(case):
    texts, info = T._corpus(case["seed"], case["size"], tuple(case.get("reuse", ())))
    st = case.get("struct", "none")
    if st == "rescaled":
        texts = T._rescaled(texts, info, case["seed"] + 1)
    muts = case.get("muts", [])
    if muts:
        c = C(texts, info)
        if st == "rescaled":
            first = c.card[info["first_plan"]]["tiers"][0]
            first[1] = T._rate_text(83 * info["scale_step"])
        rng = random.Random(case["seed"] * 7 + 3)
        blank = False
        for m in muts:
            MUTS[m](c, rng)
            if None in c.reads:
                blank = True
                c.reads = [r for r in c.reads if r is not None]
        texts = c.texts()
        if blank:
            ls = texts["meter_reads.jsonl"].split("\n")
            ls.insert(len(ls) // 2, "")
            texts["meter_reads.jsonl"] = "\n".join(ls)
    if st == "shuffle":
        ls = texts["meter_reads.jsonl"].splitlines(keepends=True)
        random.Random(case["seed"]).shuffle(ls)
        texts = {**texts, "meter_reads.jsonl": "".join(ls)}
    if st == "rotated":
        texts = T._rotated(texts, case["seed"] + 1)
    if st == "crlf":
        texts = {k: v.replace("\n", "\r\n") for k, v in texts.items()}
    return texts


def extract(zpath, dest):
    with zipfile.ZipFile(zpath) as zf:
        for info in zf.infolist():
            if info.filename.endswith("/"):
                continue
            t = dest / info.filename
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_bytes(zf.read(info))


def run(zpath, texts, st, missing=None):
    work = Path(tempfile.mkdtemp(prefix="fz-"))
    repo = work / ("checkout" / Path("billing engine") if st == "relocated" else Path("repo"))
    extract(zpath, repo)
    data = work / ("feeds" / Path("cycle inputs ü") if st == "relocated" else Path("data"))
    data.mkdir(parents=True)
    for n, t in texts.items():
        if n != missing:
            (data / n).write_text(t, encoding="utf-8")
    cwd = work / "elsewhere"
    cwd.mkdir()
    T._open_tree(work)
    if st == "readonly":
        for p in data.iterdir():
            p.chmod(0o444)
        data.chmod(0o555)
    if st == "cwdroot":
        cwd = Path("/")
    env = T._env(None)
    if st == "relocated":
        cmd = [sys.executable, "-I", "-B", "-c", T._ISOLATED, str(repo / "src"), str(data)]
    elif st == "api":
        cmd = [sys.executable, "-I", "-B", "-c", T._API, str(repo / "src"), str(data)]
    else:
        env = T._env(repo)
        cmd = [sys.executable, "-B", "-m", "tariff", str(data)]
    t0 = time.time()
    try:
        p = subprocess.run([*T._SETPRIV, *cmd], cwd=str(cwd), env=env, capture_output=True, text=True, timeout=120)
        code, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        code, out, err = None, "", "timeout"
    secs = round(time.time() - t0, 2)
    shutil.rmtree(work, ignore_errors=True)
    return code, out, err, secs


VARS = [(f[:-4], "/progs/var/" + f) for f in sorted(os.listdir("/progs/var"))] if os.path.isdir("/progs/var") else []


def one(case):
    t0 = time.time()
    rec = dict(case)
    try:
        texts = build(case)
        bad = contract_ok(texts)
    except (AssertionError, ValueError, KeyError, StopIteration, IndexError) as e:
        rec["gen_error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
        return rec
    try:
        want = T._Ledger(texts).document()
    except Exception as e:  # reference crash on a contract-valid input: compare agent with oracle instead
        rec["ref_error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
        want = None
    if bad:
        rec["gen_error"] = "OOB " + bad
        return rec
    st = case.get("struct", "none")
    missing = None
    if st == "missing":
        missing = random.Random(case["seed"]).choice(list(T.INPUT_FILES))
        first = next(n for n in T.INPUT_FILES if n == missing)
        rec["missing"] = first
    rec["reads"] = len(texts["meter_reads.jsonl"].splitlines())
    rec["exceptions"] = len(want["exceptions"]) if want else None
    outs = {}
    for who, z in (("agent", AGENT), ("oracle", ORACLE), *VARS):
        code, out, err, secs = run(z, texts, st, missing)
        r = {"code": code, "secs": secs, "err": err[-500:] if code else ""}
        if st == "missing":
            ok = code == 2 and out == "" and err.strip().splitlines()[-1:] == ["missing input: %s" % missing]
            r["diff"] = {} if ok else {"missing": [["$", "code %r out %r err %r" % (code, out[:80], err[-160:])]]}
        else:
            try:
                got = json.loads(out)
                outs[who] = got
                d = [] if want is None else diffs(got, want)
                r["diff"] = {"doc": [list(x) for x in d[:60]] + ([["...", "%d total" % len(d)]] if len(d) > 60 else [])} if d else {}
            except Exception as e:
                r["diff"] = {"doc": [["$", "unreadable %s code %r" % (type(e).__name__, code)]]}
        rec[who] = r
    if want is None and st != "missing":
        for who in ["agent"] + [n for n, _ in VARS]:
            d = diffs(outs.get(who), outs.get("oracle"))
            rec[who]["diff"] = {"doc_vs_oracle": [list(x) for x in d[:60]]} if d else rec[who]["diff"]
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
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()


if __name__ == "__main__":
    if sys.argv[1] == "--one":
        print(json.dumps(one(json.loads(sys.argv[2])), indent=1, ensure_ascii=False)[:8000])
    else:
        main()
