"""Prototype crash-book generator: buffer pool + WAL + fuzzy checkpoints + savepoint rollbacks
+ aborts + interrupted earlier restarts. Truth = genesis + net effect of committed txns."""
import random
import string

import rec as R_

PROFILES = {
    # shipped-like: one restart rarely, no CLR->CLR hops forced
    "shipped": dict(recs=(300, 900), pages=(8, 20), slots=(4, 8), active=(3, 6), p_flush=0.08,
                    p_sp=0.03, p_rb=0.03, p_abort=0.03, ckpts=(1, 3), p_lag=0.3, restarts=(0, 1),
                    p_torn=0.4, hop=0.0, res_k=30, p_hot=0.3, p_multi=0.15, p_same=0.2),
    "dense": dict(recs=(800, 1200), pages=(16, 24), slots=(6, 8), active=(6, 10), p_flush=0.12,
                  p_sp=0.06, p_rb=0.06, p_abort=0.05, ckpts=(2, 4), p_lag=0.4, restarts=(1, 2),
                  p_torn=0.5, hop=0.6, res_k=20, p_hot=0.6, p_multi=0.35, p_same=0.4),
    "restart": dict(recs=(500, 1100), pages=(8, 24), slots=(4, 8), active=(5, 9), p_flush=0.10,
                    p_sp=0.08, p_rb=0.08, p_abort=0.06, ckpts=(1, 3), p_lag=0.5, restarts=(2, 3),
                    p_torn=0.5, hop=0.8, res_k=12, p_hot=0.6, p_multi=0.35, p_same=0.4),
}


def pid(rng, used):
    while True:
        s = "".join(rng.choice(string.ascii_lowercase + string.digits) for _ in range(4))
        if s not in used and not s.isdigit():
            used.add(s)
            return s


class Sim:
    def __init__(self, rng, prof):
        self.rng = rng
        self.p = prof
        used = set()
        npg = rng.randint(*prof["pages"])
        self.pages = {pid(rng, used): rng.randint(*prof["slots"]) for _ in range(npg)}
        self.genesis = {p: [rng.randint(0, 900) for _ in range(n)] for p, n in self.pages.items()}
        self.disk = {p: {"page_lsn": 0, "slots": list(v)} for p, v in self.genesis.items()}
        self.buf = {p: {"page_lsn": 0, "slots": list(v)} for p, v in self.genesis.items()}
        self.dirty = {}
        self.lsn = rng.randint(1000, 90000)
        self.log = []
        self.R = {}
        self.T = {}  # txn -> dict(state,last,sp,roll)
        self.ended = set()
        self.committed = set()
        self.master = 0
        self.txid_used = set()
        self.pending_ckpt = None

    def new_lsn(self):
        self.lsn += self.rng.randint(1, 9)
        return self.lsn

    def emit(self, **r):
        r["lsn"] = self.new_lsn()
        self.log.append(r)
        self.R[r["lsn"]] = r
        return r

    def apply(self, r):
        for ch in r["changes"]:
            self.apply1(r, ch)

    def apply1(self, r, ch):
        b = self.buf[ch["page"]]
        b["slots"][ch["slot"]] += ch["delta"]
        b["page_lsn"] = r["lsn"]
        self.dirty.setdefault(ch["page"], r["lsn"])

    def flush(self):
        if not self.dirty:
            return
        if self.rng.random() < self.p.get("p_hot", 0.0):
            p = max(self.dirty, key=lambda q: (self.dirty[q], q))
        else:
            p = self.rng.choice(sorted(self.dirty))
        self.disk[p] = {"page_lsn": self.buf[p]["page_lsn"], "slots": list(self.buf[p]["slots"])}
        del self.dirty[p]

    def txid(self):
        while True:
            t = self.rng.randint(100, 99999)
            if t not in self.txid_used:
                self.txid_used.add(t)
                return t

    def undo_step(self, tx):
        e = self.T[tx]
        u = R_.undo_point(self.R, e["last"])
        target = e["roll"]
        if u is None or (target is not None and u["lsn"] <= target):
            if target is None:
                self.emit(txn=tx, type="end", prev=e["last"])
                del self.T[tx]
                self.ended.add(tx)
            else:
                e["roll"] = "no"
                e["state"] = "running"
            return
        chs = [{"page": ch["page"], "slot": ch["slot"], "delta": -ch["delta"]} for ch in u["changes"]]
        c = self.emit(txn=tx, type="clr", prev=e["last"], changes=chs, undo_next=u["prev"])
        e["last"] = c["lsn"]
        self.apply(c)

    def snapshot(self):
        txns = [{"txn": t, "state": e["state"], "last": e["last"]} for t, e in sorted(self.T.items())]
        self.rng.shuffle(txns)
        dirty = [{"page": p, "rec": l} for p, l in self.dirty.items()]
        self.rng.shuffle(dirty)
        return txns, dirty

    def run(self, target):
        rng, p = self.rng, self.p
        nck = rng.randint(*p["ckpts"])
        ck_at = sorted(rng.sample(range(target // 6, target), nck))
        while len(self.log) < target:
            if ck_at and len(self.log) >= ck_at[0] and self.pending_ckpt is None:
                ck_at.pop(0)
                b = self.emit(txn=None, type="ckpt_begin")
                self.pending_ckpt = (b["lsn"], self.snapshot(), rng.randint(1, 12))
            if self.pending_ckpt is not None:
                bl, snap, left = self.pending_ckpt
                if left <= 0:
                    self.emit(txn=None, type="ckpt_end", begin=bl, txns=snap[0], dirty=snap[1])
                    self.pending_ckpt = None
                    if rng.random() > p["p_lag"] or not self.master:
                        self.master = bl
                else:
                    self.pending_ckpt = (bl, snap, left - 1)
            running = [t for t, e in self.T.items() if e["state"] == "running" and e["roll"] == "no"]
            rolling = [t for t, e in self.T.items() if e["roll"] != "no"]
            committed = [t for t, e in self.T.items() if e["state"] == "committed"]
            x = rng.random()
            if x < p["p_flush"]:
                self.flush()
            elif len(self.T) < self.amax and rng.random() < 0.25:
                t = self.txid()
                b = self.emit(txn=t, type="begin", prev=None)
                self.T[t] = {"state": "running", "last": b["lsn"], "sp": [], "roll": "no"}
            elif rolling and rng.random() < 0.5:
                self.undo_step(rng.choice(sorted(rolling)))
            elif committed and rng.random() < 0.3:
                t = rng.choice(sorted(committed))
                self.emit(txn=t, type="end", prev=self.T[t]["last"])
                del self.T[t]
                self.ended.add(t)
            elif running:
                t = rng.choice(sorted(running))
                e = self.T[t]
                y = rng.random()
                if y < p["p_sp"]:
                    e["sp"].append(e["last"])
                elif y < p["p_sp"] + p["p_rb"] and e["sp"]:
                    e["roll"] = e["sp"].pop()
                elif y < p["p_sp"] + p["p_rb"] + p["p_abort"]:
                    a = self.emit(txn=t, type="abort", prev=e["last"])
                    e["last"] = a["lsn"]
                    e["state"] = "aborting"
                    e["roll"] = None
                elif y < p["p_sp"] + p["p_rb"] + p["p_abort"] + 0.06:
                    c = self.emit(txn=t, type="commit", prev=e["last"])
                    e["last"] = c["lsn"]
                    e["state"] = "committed"
                    self.committed.add(t)
                else:
                    k = 1 if rng.random() > p["p_multi"] else rng.randint(2, 3)
                    chs = []
                    picks = rng.sample(sorted(self.pages), k)
                    if k > 1 and rng.random() < p["p_same"]:
                        picks[-1] = picks[0]
                    for pg in picks:
                        chs.append({"page": pg, "slot": rng.randrange(self.pages[pg]),
                                    "delta": rng.choice([v for v in range(-60, 61) if v])})
                    u = self.emit(txn=t, type="update", prev=e["last"], changes=chs)
                    e["last"] = u["lsn"]
                    self.apply(u)
        # crash

    def restart(self, rng, last=True):
        img = {"records": self.log, "master": self.master, "pages": self.pages,
               "disk": {p: {"page_lsn": d["page_lsn"], "slots": list(d["slots"])} for p, d in self.disk.items()}}
        Rm, order, master, T, D = R_.analysis(img, {})
        self.buf = {p: {"page_lsn": d["page_lsn"], "slots": list(d["slots"])} for p, d in self.disk.items()}
        self.dirty = {}
        start = min(D.values()) if D else None
        if start is not None:
            for lsn in order:
                if lsn < start:
                    continue
                r = Rm[lsn]
                if r["type"] in ("update", "clr"):
                    todo = {ch["page"] for ch in r["changes"] if ch["page"] in D and lsn >= D[ch["page"]]
                            and lsn > self.buf[ch["page"]]["page_lsn"]}
                    for ch in r["changes"]:
                        if ch["page"] in todo:
                            self.apply1(r, ch)
                    if rng.random() < 0.05:
                        self.flush()
        import copy
        plan = list(R_.appended_sequence(dict(self.R), copy.deepcopy(T), copy.deepcopy(self.buf),
                                         max(order) + 1, {}))
        Rp = dict(self.R)
        for r in plan:
            Rp[r["lsn"]] = r
        hops = [i + 1 for i, r in enumerate(plan) if r["type"] == "clr" and r["undo_next"] is not None
                and Rp[r["undo_next"]]["type"] == "clr" and i + 1 < len(plan)]
        nwin = sum(1 for e in T.values() if e["state"] == "committed")
        stop = nwin + rng.randint(1, self.p["res_k"])
        if hops and last and rng.random() < self.p["hop"]:
            stop = rng.choice(hops)
        Rc = dict(self.R)
        seq = R_.appended_sequence(Rc, T, {p: d for p, d in self.buf.items()}, max(order) + 1, {})
        k = 0
        for r in seq:
            if r["type"] == "clr":
                for ch in r["changes"]:
                    self.dirty.setdefault(ch["page"], r["lsn"])
            self.log.append(r)
            self.R[r["lsn"]] = r
            k += 1
            if rng.random() < 0.15:
                self.flush()
            if k >= stop:
                break
        self.lsn = self.log[-1]["lsn"] if self.log else self.lsn
        while rng.random() < 0.5:
            self.flush()
        # do not write beyond: crash again


def build_image(rng, prof, iid):
    s = Sim(rng, prof)
    s.amax = rng.randint(*prof["active"])
    target = rng.randint(*prof["recs"])
    nres = rng.randint(*prof["restarts"])
    s.run(target - 40 * nres)
    for i in range(nres):
        s.restart(rng, i == nres - 1)
    # winners net effect truth
    truth = {p: list(v) for p, v in s.genesis.items()}
    winners = {r["txn"] for r in s.log if r["type"] == "commit"}
    for r in s.log:
        if r["type"] in ("update", "clr") and r["txn"] in winners:
            for ch in r["changes"]:
                truth[ch["page"]][ch["slot"]] += ch["delta"]
    recs = [dict(r) for r in s.log]
    for r in recs:
        r["image"] = iid
    return {"id": iid, "pages": dict(s.pages), "disk": s.disk, "master": s.master, "records": recs,
            "truth": truth, "nres": nres}


def build_book(seed, profile, n_images):
    rng = random.Random(seed)
    prof = PROFILES[profile]
    used = set()
    images, catalog, queries = [], {}, {}
    clients = ["c" + "".join(rng.choice(string.ascii_lowercase) for _ in range(5)) for _ in range(9)]
    for i in range(n_images):
        iid = "im" + pid(rng, used)
        img = build_image(rng, prof, iid)
        images.append(img)
        txs = sorted({r["txn"] for r in img["records"] if r.get("txn") is not None})
        catalog[iid] = {t: rng.choice(clients) for t in txs}
        qs = []
        for k in range(rng.randint(2, 5)):
            pg = rng.sample(sorted(img["pages"]), rng.randint(1, 4))
            sl = rng.choice([None, 0, 1, 2, 3])
            qs.append({"id": f"q{k}", "pages": pg, "slot": sl})
        queries[iid] = qs
    return {"images": images, "catalog": catalog, "queries": queries}
