"""Differential fuzz driver for data-product-config-compiler; runs inside the verifier image.
usage: python3 fz_cf.py <cases.jsonl> <results.jsonl> <workers> | python3 fz_cf.py --one '<case json>'
Case: {"id","profile","seed","size","hidden","date","muts":[...],"struct":...}
Reference = T.ref_compute on the mutated files (RefError -> expected error line and code).
"""
import datetime as dt
import json, os, random, re, shutil, subprocess, sys, tempfile, time, zipfile
from multiprocessing import Pool
from pathlib import Path
sys.path.insert(0, "/tests")
import test_output as T

PROGS = {"agent": "/progs/agent/tool.zip", "oracle": "/fz/oracle_cf/tool.zip"}
_ROOTS = {}


def diffs(p, w, path="$", out=None):
    out = [] if out is None else out
    if isinstance(w, dict) and isinstance(p, dict):
        for k in list(w) + [k for k in p if k not in w]:
            if k not in p or k not in w:
                out.append((path + "." + str(k), "only-one"))
            else:
                diffs(p[k], w[k], path + "." + str(k), out)
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


def root(who):
    if who not in _ROOTS:
        r = Path(tempfile.mkdtemp(prefix="tool-%s-" % who))
        with zipfile.ZipFile(PROGS[who]) as zf:
            zf.extractall(r)
        T._set_modes(r, 0o755, 0o644)
        _ROOTS[who] = r
    return _ROOTS[who]


def txt(f, n):
    return f[n].decode("utf-8")


def put(f, n, s):
    f[n] = s.encode("utf-8")


def day_of(f):
    return dt.date.fromisoformat(json.loads(f["release_manifest.json"])["compile_date"])


# ---------------------------------------------------------------- mutations (all contract-valid by construction)
def m_dates(f, rng, D):
    """owner rows starting or ending exactly on D, ending the day before; events dated on D late and D+1 early."""
    lines = txt(f, "owners.csv").split("\n")
    head, body = lines[0], [l for l in lines[1:] if l]
    Ds = D.isoformat()
    idx = [i for i, l in enumerate(body) if l.split(",")[2] <= Ds and (l.split(",")[3] == "" or l.split(",")[3] >= Ds)]
    rng.shuffle(idx)
    for k, i in enumerate(idx[:12]):
        o, t, a, b = body[i].split(",")
        if k % 3 == 0:
            a = Ds
        elif k % 3 == 1:
            b = Ds
        elif a <= (D - dt.timedelta(days=1)).isoformat():
            b = (D - dt.timedelta(days=1)).isoformat()
        body[i] = ",".join((o, t, a, b))
    put(f, "owners.csv", "\n".join([head] + body) + "\n")
    cat = json.loads(f["release_manifest.json"])["catalog"]
    owners = sorted({l.split(",")[0] for l in body})
    ev = []
    for pid in rng.sample(cat, 3):
        ev.append("%sT23:59:59Z RETIRE product=%s ticket=DEP-1" % (Ds, pid))
    for pid in rng.sample(cat, 3):
        ev.append("%sT00:00:00Z RETIRE product=%s ticket=DEP-2" % ((D + dt.timedelta(days=1)).isoformat(), pid))
    for o in rng.sample(owners, 3):
        ev.append("%sT23:59:59Z RETIRE owner=%s ticket=DEP-3" % (Ds, o))
    for o in rng.sample(owners, 3):
        ev.append("%sT00:00:00Z RETIRE owner=%s ticket=DEP-4" % ((D + dt.timedelta(days=1)).isoformat(), o))
    log = txt(f, "deprecation.log").split("\n")
    for e in ev:
        log.insert(rng.randrange(len(log)), e)
    put(f, "deprecation.log", "\n".join(l for l in log if l) + "\n")


def m_ids(f, rng, D):
    """every product id written in some other legal spelling: catalog, ini headers, log, overrides."""
    man = json.loads(f["release_manifest.json"])
    man["catalog"] = [T._gmangle(rng, p) if rng.random() < 0.5 else p for p in man["catalog"]]
    rng.shuffle(man["catalog"])
    put(f, "release_manifest.json", json.dumps(man, indent=2) + "\n")
    ini = re.sub(r"^\[product (\S+)\]$", lambda m: "[product %s]" % (T._gmangle(rng, T.ref_canon(m.group(1)))
                                                                     if rng.random() < 0.5 else m.group(1)),
                 txt(f, "products.ini"), flags=re.M)
    put(f, "products.ini", ini)
    log = re.sub(r"RETIRE product=(\S+)", lambda m: "RETIRE product=%s" % (T._gmangle(rng, T.ref_canon(m.group(1)))
                 if rng.random() < 0.5 and re.fullmatch(r"DP\d{5}", T.ref_canon(m.group(1))) else m.group(1)),
                 txt(f, "deprecation.log"))
    put(f, "deprecation.log", log)


JVALS = {
    "integer": ["0", "-0", "-1", "1", "1e0", "1E2", "5.0", "10e-1", "\"5\"", "\" 5\"", "true", "false", "null", "[5]",
                "100000000000000000000", "-100000000000000000000", "{\"v\": 5}", "3", "7", "1440", "3650", "256", "4"],
    "boolean": ["true", "false", "\"true\"", "\"False\"", "0", "1", "null", "[true]", "1.0"],
    "enum": ["\"kms\"", "\"hsm\"", "\"none\"", "\"KMS\"", "\" kms\"", "\"kms \"", "null", "[\"kms\"]", "1", "true", "\"\""],
    "list": ["[]", "[\"a\"]", "[\" a \", \"b\"]", "[\"a\", 1]", "\"a,b\"", "null", "[[\"a\"]]", "[\"\"]", "[null]", "{}"],
    "string": ["\"\"", "\" CC-1 \"", "\"CC-9\"", "null", "5", "true", "[\"CC\"]", "\"\\u00e9t\\u00e9\""],
}
SCHEMA = T.GEN_SCHEMA


def m_jtypes(f, rng, D):
    """JSON-layer values at every type and bound edge, in both JSON layers."""
    cat = json.loads(f["release_manifest.json"])["catalog"]
    lines = [l for l in txt(f, "product_overrides.jsonl").split("\n") if l.strip()]
    top = max(json.loads(l)["seq"] for l in lines)
    new = []
    keys = list(SCHEMA) + ["retention", "Weight", ""]
    for i in range(60):
        key = rng.choice(keys)
        kind = SCHEMA[key]["type"] if key in SCHEMA else rng.choice(list(JVALS))
        val = rng.choice(JVALS[kind])
        pid = rng.choice(cat)
        new.append('{"seq": %d, "product": "%s", "key": "%s", "value": %s, "ticket": "CHG-F%d"}' % (top + 1 + i, pid, key, val, i))
    for l in new:
        lines.insert(rng.randrange(len(lines) + 1), l)
    put(f, "product_overrides.jsonl", "\n".join(lines) + "\n")
    teams = json.loads(f["team_overrides.json"])
    parts = []
    for t in teams:
        ent = ['"%s": %s' % (k, json.dumps(v)) for k, v in teams[t].items()]
        for _ in range(rng.randint(0, 3)):
            key = rng.choice(keys)
            if any(e.startswith('"%s":' % key) for e in ent):
                continue
            kind = SCHEMA[key]["type"] if key in SCHEMA else "integer"
            ent.append('"%s": %s' % (key, rng.choice(JVALS[kind])))
        parts.append('"%s": {%s}' % (t, ", ".join(ent)))
    parts.append('"no-such-team": {"weight": 9, "replicas": "x"}')
    put(f, "team_overrides.json", "{\n" + ",\n".join(parts) + "\n}\n")


def m_seq(f, rng, D):
    """same product+key overridden many times, seqs out of file order, seq 0 and negative seqs."""
    cat = json.loads(f["release_manifest.json"])["catalog"]
    lines = [l for l in txt(f, "product_overrides.jsonl").split("\n") if l.strip()]
    used = {json.loads(l)["seq"] for l in lines}
    free = [s for s in range(-40, 1)] + [s for s in range(1, 100) if s not in used]
    rng.shuffle(free)
    for pid in rng.sample(cat, 6):
        key = rng.choice(["retention_days", "replicas", "weight", "notify", "cost_center"])
        for _ in range(4):
            s = free.pop()
            v = json.dumps(T._gvalue(rng, key)) if not (key == "cost_center" and rng.random() < 0.3) else "null"
            lines.insert(rng.randrange(len(lines) + 1), '{"seq": %d, "product": "%s", "key": "%s", "value": %s, "ticket": "CHG-S"}' % (s, pid, key, v))
    put(f, "product_overrides.jsonl", "\n".join(lines) + "\n")


def _restyle(rng, key, raw):
    v = raw.strip()
    q = len(v) >= 2 and v[0] == '"' and v[-1] == '"'
    inner = v[1:-1] if q else v
    kind = SCHEMA[key]["type"]
    if kind == "boolean":
        inner = "".join(c.upper() if rng.random() < 0.5 else c.lower() for c in inner)
    elif kind == "integer":
        inner = "0" * rng.randint(0, 2) + inner
    elif kind == "list" and inner:
        inner = rng.choice([" , ", ",", ",  ", " ,"]).join(x.strip() for x in inner.split(","))
        if rng.random() < 0.3:
            inner = " " + inner + " "
    if rng.random() < 0.4:
        return '"' + inner + '"'
    return inner


def m_text(f, rng, D):
    """text layers: quoting, letter case, leading zeros, list spacing, extra spaces round separators, comments."""
    out = []
    for l in txt(f, "base_layer.yaml").split("\n"):
        if l and not l.startswith("#") and ":" in l:
            k, _, r = l.partition(":")
            l = "%s%s:%s%s" % (" " * rng.randint(0, 1), k.strip(), " " * rng.randint(0, 3), _restyle(rng, k.strip(), r))
        out.append(l)
        if rng.random() < 0.2:
            out.append(rng.choice(["", "# note", "   "]))
    put(f, "base_layer.yaml", "\n".join(out))
    for name in ("products.ini", "env_dev.toml", "env_prod.toml"):
        out = []
        for l in txt(f, name).split("\n"):
            s = l.strip()
            if s and not s.startswith("#") and not s.startswith("[") and "=" in s:
                k, _, r = s.partition("=")
                k = k.strip()
                if k in SCHEMA:
                    l = "%s%s%s=%s%s" % (" " * rng.randint(0, 2), k, " " * rng.randint(0, 2), " " * rng.randint(0, 2), _restyle(rng, k, r))
            out.append(l)
            if rng.random() < 0.1:
                out.append(rng.choice(["# c", "", "  # indented comment"]))
        put(f, name, "\n".join(out))
    out = []
    for l in txt(f, "selectors.rules").split("\n"):
        m = re.match(r"match (team|tier|label):(\S+) set (\S+) ?(.*)$", l)
        if m:
            l = "match %s:%s set %s %s" % (m.group(1), m.group(2), m.group(3), _restyle(rng, m.group(3), m.group(4)))
        out.append(l)
    put(f, "selectors.rules", "\n".join(out))


def m_quota(f, rng, D):
    """quotas at the edges: zero, smaller than the number of active products, huge."""
    q = json.loads(f["cluster_quota.json"])
    for k in q:
        q[k] = rng.choice([0, 1, 2, 7, 10 ** 15 + rng.randint(0, 99), q[k]])
    put(f, "cluster_quota.json", json.dumps(q, indent=2) + "\n")


def m_weights(f, rng, D):
    """weights equal everywhere, or one product with the maximum, to force long remainder ties."""
    put(f, "selectors.rules", txt(f, "selectors.rules").rstrip("\n") + "\nmatch tier:%s set weight %d\n" % (rng.choice(["bronze", "silver", "gold"]), rng.choice([1, 100])))


def m_nulls(f, rng, D):
    """null removal and later re-set through every layer that may carry a null."""
    cat = json.loads(f["release_manifest.json"])["catalog"]
    lines = [l for l in txt(f, "product_overrides.jsonl").split("\n") if l.strip()]
    top = max(json.loads(l)["seq"] for l in lines)
    for i, pid in enumerate(rng.sample(cat, 10)):
        lines.append('{"seq": %d, "product": "%s", "key": "cost_center", "value": null, "ticket": "N"}' % (top + 1 + 2 * i, pid))
        if i % 2:
            lines.append('{"seq": %d, "product": "%s", "key": "cost_center", "value": "CC-0001", "ticket": "N"}' % (top + 2 + 2 * i, pid))
    rng.shuffle(lines)
    put(f, "product_overrides.jsonl", "\n".join(lines) + "\n")
    teams = json.loads(f["team_overrides.json"])
    for t in rng.sample(sorted(teams), 4):
        teams[t]["cost_center"] = None
    put(f, "team_overrides.json", json.dumps(teams, indent=2) + "\n")


def m_logs(f, rng, D):
    """log lines with extra fields, repeated events, events for unknown ids and owners, event at the year start."""
    cat = json.loads(f["release_manifest.json"])["catalog"]
    owners = sorted({l.split(",")[0] for l in txt(f, "owners.csv").split("\n")[1:] if l})
    log = [l for l in txt(f, "deprecation.log").split("\n") if l]
    Ds = D.isoformat()
    extra = []
    for pid in rng.sample(cat, 4):
        when = (D - dt.timedelta(days=rng.randint(0, 50))).isoformat()
        extra.append("%sT10:00:00Z RETIRE product=%s ticket=DEP-9 reason=dup note=x" % (when, pid))
        extra.append("%sT11:00:00Z RETIRE product=%s ticket=DEP-9" % (when, pid))
    for o in rng.sample(owners, 3):
        extra.append("%sT01:00:00Z RETIRE owner=%s ticket=DEP-8 by=hr" % ((D - dt.timedelta(days=3)).isoformat(), o + "x"))
        extra.append("%sT01:00:00Z NOTICE owner=%s note=handover" % (Ds, o))
    extra.append("%sT00:00:00Z RETIRE product=DP00000 ticket=DEP-0" % Ds)
    for e in extra:
        log.insert(rng.randrange(len(log) + 1), e)
    put(f, "deprecation.log", "\n".join(log) + "\n")


def m_orphans(f, rng, D):
    """owners with no owners.csv row; products owned by an owner whose rows all ended."""
    ini = txt(f, "products.ini").split("\n")
    idx = [i for i, l in enumerate(ini) if l.startswith("owner = ")]
    for i in rng.sample(idx, min(8, len(idx))):
        ini[i] = "owner = %s" % rng.choice(["z.nobody", "q.ghost", "x.unknown2"])
    put(f, "products.ini", "\n".join(ini))


def m_env(f, rng, D):
    """env sections for a tier nobody has, other keys in env sections, defaults repeated after tiers."""
    for name in ("env_dev.toml", "env_prod.toml"):
        s = txt(f, name).rstrip("\n")
        s += "\n\n[tier.platinum]\nreplicas = 7\n\n[tier.bronze]\nencryption = hsm\nnotify = \"a , b\"\nweight = %d\n" % rng.randint(1, 9)
        put(f, name, s + "\n")


MUTS = {"dates": m_dates, "ids": m_ids, "jtypes": m_jtypes, "seq": m_seq, "text": m_text, "quota": m_quota,
        "weights": m_weights, "nulls": m_nulls, "logs": m_logs, "orphans": m_orphans, "env": m_env}


class GenTimeout(Exception):
    pass


def _alarm(signum, frame):
    raise GenTimeout("generator gen_corpus did not finish in 30 s (fresh_pair loops when too few active products)")


def build(case):
    import signal
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(30)
    try:
        files = T.gen_corpus(case["seed"], case["size"], case["hidden"], case["date"], case["release"], T.ref_compute)
    finally:
        signal.alarm(0)
    rng = random.Random(case["seed"] * 31 + 7)
    D = day_of(files)
    for m in case.get("muts", []):
        MUTS[m](files, rng, D)
    return files


def run(who, files, st, date, case):
    work = Path(tempfile.mkdtemp(prefix="rerun-"))
    source = work / ("input files (moved) ü" if st == "renamed" else "inputs-x")
    source.mkdir()
    for name, blob in files.items():
        (source / name).write_bytes(blob)
    target = work / ("a/b/compiled" if st == "nested" else "compiled-x")
    cwd = work / "elsewhere"
    cwd.mkdir()
    T._set_modes(work, 0o777, 0o666)
    if st == "readonly":
        T._set_modes(source, 0o555, 0o444)
    cmd = [sys.executable, "-B", "-E", "-s", str(root(who) / "cli.py"), "compile", "--data", str(source), "--date", date, "--out", str(target)]
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONHASHSEED": "0", "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    t0 = time.time()
    try:
        p = subprocess.run(T._SETPRIV + cmd, cwd="/" if st == "cwdroot" else str(cwd), env=env, capture_output=True, text=True, timeout=600)
        code, err = p.returncode, p.stderr
    except subprocess.TimeoutExpired:
        code, err = None, "timeout"
    docs = {}
    for d in T.DOCUMENTS:
        pth = target / d
        if pth.exists():
            raw = pth.read_bytes()
            try:
                docs[d] = (json.loads(raw), raw)
            except Exception as e:  # noqa: BLE001 - unreadable document is itself a finding
                docs[d] = ("UNREADABLE %s" % type(e).__name__, raw)
    shutil.rmtree(work, ignore_errors=True)
    return code, err, round(time.time() - t0, 2), docs


def one(case):
    rec = dict(case)
    st = case.get("struct", "none")
    try:
        files = build(case)
    except Exception as e:  # noqa: BLE001 - generator rejection
        rec["gen_error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
        return rec
    rnd = random.Random(case["seed"] + 5)
    D = day_of(files)
    date = D.isoformat()
    if st == "shuffle":
        files = T.gen_shuffled(files, case["seed"] + 2)
    elif st == "rescale":
        files = T.gen_rescaled(files, case["seed"] + 1)
    elif st == "shift":
        date = (D + dt.timedelta(days=rnd.choice([45, 1, -1, -400, 900]))).isoformat()
    elif st == "crlf":
        files = {n: b.replace(b"\n", b"\r\n") for n, b in files.items()}
    elif st == "missing":
        gone = rnd.sample(list(T.REF_INPUTS), rnd.choice([1, 1, 2, 3]))
        for g in gone:
            files.pop(g)
        rec["missing"] = gone
    elif st == "baddate":
        date = rnd.choice(["%d-02-29" % (D.year | 1), "%d-13-01" % D.year, "%d-1-05" % D.year, "%d0105" % D.year,
                           "%d-04-31" % D.year, "%s " % date, "\u0662\u0660\u0662\u0667-01-01", "%d-00-10" % D.year])
        if date.endswith("-29") and (D.year | 1) % 4 == 0:
            date = "%d-02-30" % D.year
    elif st == "mismatch":
        man = json.loads(files["release_manifest.json"])
        cat = man["catalog"]
        if rnd.random() < 0.5:
            cat.pop(rnd.randrange(len(cat)))
        else:
            cat.append(rnd.choice(["DP00001", "dp-99999", "DP-0-0002"]))
        files["release_manifest.json"] = (json.dumps(man, indent=2) + "\n").encode()
    rec["date"] = date
    try:
        want, werr = T.ref_compute(files, date), None
        if st == "rescale" or True:
            pass
    except T.RefError as e:
        want, werr = None, (e.code, e.line)
    except Exception as e:  # noqa: BLE001 - reference crash on these inputs
        rec["ref_error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
        want, werr = None, None
    if want is not None:
        cfg = want["config.json"]["products"]
        rec["n"] = {s: sum(1 for p in cfg.values() if p["status"] == s) for s in ("active", "orphaned", "retired")}
        rec["rejected"] = len(want["validation_report.json"]["rejected_overrides"])
        rec["lever_differs"] = {}
        for lever, kw in (("NL-1", {"assign": "first"}), ("NL-3", {"cap": "restart"}), ("NL-4", {"text": "lenient"})):
            try:
                alt = T.ref_compute(files, date, **kw)
                rec["lever_differs"][lever] = sorted(n for n in T.DOCUMENTS if alt[n] != want[n])
            except Exception as e:  # noqa: BLE001 - reflex reading crash
                rec["lever_differs"][lever] = ["crash %s" % type(e).__name__]
    rec["werr"] = werr
    outs = {}
    for who in ("agent", "oracle"):
        code, err, secs, docs = run(who, files, st, date, case)
        r = {"code": code, "secs": secs, "err": err[-300:] if code else ""}
        d = {}
        if werr is not None:
            lines = err.splitlines()
            if not (code == werr[0] and lines == [werr[1]] and not docs):
                d["error"] = [["$", "code %r stderr %r docs %s want %r" % (code, err[-200:], sorted(docs), werr)]]
        elif want is not None:
            for name in T.DOCUMENTS:
                if name not in docs:
                    d[name] = [["$", "missing code %r %s" % (code, err[-200:])]]
                    continue
                got, raw = docs[name]
                dd = diffs(got, want[name])
                if not dd and raw != T.ref_dump(want[name]):
                    dd = [("$bytes", "format differs")]
                if dd:
                    d[name] = [list(x) for x in dd[:40]] + ([["...", "%d total" % len(dd)]] if len(dd) > 40 else [])
        else:
            outs[who] = (code, {n: v[0] for n, v in docs.items()})
        r["diff"] = d
        rec[who] = r
    if want is None and werr is None:
        a, o = outs["agent"], outs["oracle"]
        dd = diffs(a[1], o[1]) + ([("$code", "%r vs %r" % (a[0], o[0]))] if a[0] != o[0] else [])
        rec["agent"]["diff"] = {"vs_oracle": [list(x) for x in dd[:40]]} if dd else {}
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
        print(json.dumps(one(json.loads(sys.argv[2])), indent=1, ensure_ascii=False)[:6000])
    else:
        main()
