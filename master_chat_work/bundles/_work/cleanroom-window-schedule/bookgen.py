"""Seeded book generator. Pasted verbatim into tests/test_output.py; datagen.py uses it for the shipped book."""
import json

_HORIZON = 1440
_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"


class _Rng:
    """xorshift64*: identical streams on every Python version."""

    def __init__(self, seed):
        self.s = (seed * 0x9E3779B97F4A7C15 + 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF or 1
        for _ in range(4):
            self.next()

    def next(self):
        x = self.s
        x ^= (x >> 12)
        x ^= (x << 25) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 27)
        self.s = x
        return (x * 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def randint(self, lo, hi):
        return lo + self.next() % (hi - lo + 1)

    def choice(self, seq):
        return seq[self.randint(0, len(seq) - 1)]

    def shuffle(self, seq):
        for i in range(len(seq) - 1, 0, -1):
            k = self.randint(0, i)
            seq[i], seq[k] = seq[k], seq[i]

    def sample(self, seq, k):
        pool = list(seq)
        self.shuffle(pool)
        return pool[:k]


def _codes(rng, n, make):
    seen = []
    while len(seen) < n:
        c = make(rng)
        if c not in seen:
            seen.append(c)
    return seen


def book_setup(seed, n_nights, n_clients, n_sites, max_jobs, thresholds, start_day):
    """Book-level identities: families, bays, clients, sites, night ids, dates, job and window ids."""
    assert 1 <= n_nights <= 500
    rng = _Rng(seed)
    fams = _codes(rng, 3, lambda r: "".join(r.choice(_LETTERS) for _ in range(3)))
    ghost_fams = _codes(rng, 6, lambda r: "".join(r.choice(_LETTERS) for _ in range(3)))
    ghost_fams = [g for g in ghost_fams if g not in fams][:2]
    bay_ids = _codes(rng, 3, lambda r: "BAY-%s%d" % (r.choice(_LETTERS), r.randint(10, 99)))
    rates = rng.sample([1, 2, 3, 4], 3)
    while True:
        quals = {}
        for b in bay_ids:
            k = rng.randint(2, 3)
            quals[b] = sorted(rng.sample(fams, k), key=fams.index)
        if all(sum(f in q for q in quals.values()) >= 2 for f in fams):
            break
    bays = [{"bay_id": b, "minute_rate": r, "initial_family": rng.choice(quals[b])}
            for b, r in zip(bay_ids, rates)]
    sites = _codes(rng, n_sites, lambda r: "ST%05d" % r.randint(0, 99999))
    regions = {s: rng.choice(["North", "South", "West", "East"]) for s in sites}
    used_sites = sites[: max(4, n_sites * 3 // 4)]
    allc = _codes(rng, n_clients + 3, lambda r: "CL%06d" % r.randint(0, 999999))
    clients = allc[:n_clients]
    ghost_clients = allc[n_clients:]
    client_site = {c: rng.choice(used_sites) for c in clients}
    segments = {c: rng.choice(["commercial", "public"]) for c in clients}
    night_ids = _codes(rng, n_nights, lambda r: "NT%05d" % r.randint(0, 99999))
    days, d = [], start_day
    for _ in range(n_nights):
        d += rng.randint(1, 3)
        days.append(d)
    job_ids = _codes(rng, max_jobs, lambda r: "JB%06d" % r.randint(0, 999999))
    win_ids = _codes(rng, max_jobs + max_jobs // 8 + 4, lambda r: "WN%06d" % r.randint(0, 999999))
    return {"seed": seed, "fams": fams, "ghost_fams": ghost_fams, "bays": bays, "quals": quals,
            "sites": sites, "regions": regions, "clients": clients, "ghost_clients": ghost_clients,
            "client_site": client_site, "segments": segments, "night_ids": night_ids, "days": days,
            "job_ids": job_ids, "win_ids": win_ids, "thresholds": thresholds,
            "next_job": 0, "next_win": 0}


def _intervals(rng, n_jobs, max_overlap, dur_lo, dur_hi):
    while True:
        iv, tries = [], 0
        while len(iv) < n_jobs and tries < 40000:
            tries += 1
            d = rng.randint(dur_lo, dur_hi)
            s = rng.randint(0, _HORIZON - d)
            e = s + d
            pts = [s] + [a for a, b in iv if s <= a < e]
            if all(sum(1 for a, b in iv + [(s, e)] if a <= p < b) <= max_overlap for p in pts):
                iv.append((s, e))
        if len(iv) == n_jobs:
            return iv


def night_data(ctx, k, spec, attempt):
    """Night k (date order). spec keys: jobs, overlap, mand, crew, fee, defects, values, dur.

    Job and window ids come from book-level pools by position, so redrawing a night
    (new attempt) changes only its content."""
    n_jobs = spec["jobs"]
    assert 0 <= n_jobs <= 72 and 1 <= spec["overlap"] <= 7
    assert 1 <= spec["values"][0] <= spec["values"][1] <= 2000
    assert 1 <= spec["fee"][0] <= spec["fee"][1] <= 500 and 5 <= spec["crew"][0] <= spec["crew"][1] <= 120
    rng = _Rng(ctx["seed"] * 1000003 + k * 7919 + attempt * 104729 + 17)
    ids = ctx["job_ids"][ctx["next_job"]: ctx["next_job"] + n_jobs]
    wids = ctx["win_ids"][ctx["next_win"]: ctx["next_win"] + n_jobs]
    ctx["next_job"] += n_jobs
    ctx["next_win"] += n_jobs
    iv = _intervals(rng, n_jobs, spec["overlap"], spec["dur"][0], spec["dur"][1])
    jobs = []
    for jid, wid, (s, e) in zip(ids, wids, iv):
        jobs.append({"job_id": jid, "window_id": wid, "start": s, "end": e,
                     "family": rng.choice(ctx["fams"]), "client_id": rng.choice(ctx["clients"]),
                     "value": rng.randint(spec["values"][0], spec["values"][1])})
    mand = sorted(rng.sample(ids, min(spec["mand"], n_jobs)))
    fees = []
    for a in ctx["fams"]:
        for b in ctx["fams"]:
            if a != b:
                fees.append([a, b, rng.randint(spec["fee"][0], spec["fee"][1]),
                             rng.randint(spec["crew"][0], spec["crew"][1])])
    rows = [dict(j) for j in jobs]
    windows = [[j["window_id"], j["start"], j["end"]] for j in jobs]
    for kind in spec.get("defects", ()):
        if kind == "dup":
            src = rows[rng.randint(0, len(rows) - 1)]
            extra = dict(src, value=rng.randint(spec["values"][0], spec["values"][1]))
            extra["window_id"] = ctx["win_ids"][ctx["next_win"]]
            ctx["next_win"] += 1
            windows.append([extra["window_id"], src["start"], src["end"]])
            rows.append(extra)
        elif kind == "win_missing":
            r = rows[rng.randint(0, len(rows) - 1)]
            r["window_id"] = ctx["win_ids"][ctx["next_win"]]
            ctx["next_win"] += 1
        elif kind == "win_reversed":
            r = rows[rng.randint(0, len(rows) - 1)]
            for w in windows:
                if w[0] == r["window_id"]:
                    w[1], w[2] = w[2], w[1]
        elif kind == "win_late":
            r = rows[rng.randint(0, len(rows) - 1)]
            for w in windows:
                if w[0] == r["window_id"]:
                    w[2] = _HORIZON + rng.randint(1, 90)
        elif kind == "unk_family":
            rows[rng.randint(0, len(rows) - 1)]["family"] = ctx["ghost_fams"][0]
        elif kind == "unk_client":
            rows[rng.randint(0, len(rows) - 1)]["client_id"] = ctx["ghost_clients"][0]
        elif kind == "fee_missing":
            del fees[rng.randint(0, len(fees) - 1)]
    nid = ctx["night_ids"][k]
    return {"night_id": nid, "day": ctx["days"][k], "jobs": jobs, "rows": rows, "windows": windows,
            "mand": mand, "fees": fees, "defects": list(spec.get("defects", ()))}


def _date(day):
    y, m = 2026, 1
    lens = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    d = day
    while d >= lens[m - 1]:
        d -= lens[m - 1]
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return "%04d-%02d-%02d" % (y, m, d + 1)


def render(ctx, nights):
    """Files of the book as {name: text}."""
    rng = _Rng(ctx["seed"] * 31 + 5)
    rows = [r for n in nights for r in ((r, n["night_id"]) for r in n["rows"])]
    rng.shuffle(rows)
    jobs = "job_id,night_id,window_id,client_id,family,value\n" + "".join(
        "%s,%s,%s,%s,%s,%d\n" % (r["job_id"], nid, r["window_id"], r["client_id"], r["family"], r["value"])
        for r, nid in rows)
    wins = [w for n in nights for w in n["windows"]]
    rng.shuffle(wins)
    windows = "window_id\tstart\tend\n" + "".join("%s\t%d\t%d\n" % tuple(w) for w in wins)
    fees = [[n["night_id"]] + f for n in nights for f in n["fees"]]
    rng.shuffle(fees)
    fee_text = "night_id,from_family,to_family,fee,crew_minutes\n" + "".join(
        "%s,%s,%s,%d,%d\n" % tuple(f) for f in fees)
    bays = json.dumps({"bays": ctx["bays"]}, indent=2) + "\n"
    ini = "[catalog]\nfamilies = %s\n" % ", ".join(ctx["fams"])
    for b in ctx["bays"]:
        ini += "\n[%s]\nfamilies = %s\n" % (b["bay_id"], ", ".join(ctx["quals"][b["bay_id"]]))
    cl = list(ctx["clients"])
    rng.shuffle(cl)
    clients = "".join(json.dumps({"client_id": c, "site": ctx["client_site"][c]}) + "\n" for c in cl)
    st = list(ctx["sites"])
    rng.shuffle(st)
    regions = "site,region\n" + "".join("%s,%s\n" % (s, ctx["regions"][s]) for s in st)
    rng.shuffle(cl)
    segments = "client_id\tsegment\n" + "".join("%s\t%s\n" % (c, ctx["segments"][c]) for c in cl)
    mand = json.dumps({n["night_id"]: n["mand"] for n in nights if n["mand"]}, indent=2, sort_keys=True) + "\n"
    order = list(nights)
    rng.shuffle(order)
    th = ctx["thresholds"]
    audit = "[thresholds]\ncrew_minutes_limit = %d\nmargin_floor = %d\n" % (th[0], th[1])
    for n in order:
        audit += '\n[[night]]\nid = "%s"\ndate = "%s"\n' % (n["night_id"], _date(n["day"]))
    return {"jobs.csv": jobs, "windows.tsv": windows, "bays.json": bays, "qualifications.ini": ini,
            "setup_fees.csv": fee_text, "clients.jsonl": clients, "regions.csv": regions,
            "segments.tsv": segments, "mandatory.json": mand, "audit.toml": audit}


def make_book(seed, specs, attempts, n_clients, n_sites, thresholds, start_day):
    max_jobs = sum(s["jobs"] for s in specs)
    ctx = book_setup(seed, len(specs), n_clients, n_sites, max_jobs, thresholds, start_day)
    nights = [night_data(ctx, k, s, a) for k, (s, a) in enumerate(zip(specs, attempts))]
    return render(ctx, nights)
