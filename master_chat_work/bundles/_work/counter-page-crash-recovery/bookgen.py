"""Crash-book generator and reference recovery, shared by datagen.py and the verifier text.

Everything below the BODY marker is pasted verbatim into tests/test_output.py.
"""
# BODY
import hashlib
import json
import struct
import zlib

_M64 = (1 << 64) - 1


class Rng:
    """xorshift64* stream; identical on every Python build."""

    def __init__(self, seed: int):
        self.s = ((seed * 0x9E3779B97F4A7C15) ^ 0x632BE59BD9B4E019) & _M64 or 1

    def next64(self) -> int:
        x = self.s
        x ^= x >> 12
        x ^= (x << 25) & _M64
        x ^= x >> 27
        self.s = x
        return (x * 0x2545F4914F6CDD1D) & _M64

    def below(self, n: int) -> int:
        return self.next64() % n

    def randint(self, lo: int, hi: int) -> int:
        return lo + self.below(hi - lo + 1)

    def random(self) -> float:
        return (self.next64() >> 11) / float(1 << 53)

    def choice(self, seq):
        return seq[self.below(len(seq))]

    def shuffle(self, items: list) -> None:
        for i in range(len(items) - 1, 0, -1):
            j = self.below(i + 1)
            items[i], items[j] = items[j], items[i]

    def sample(self, seq, k: int) -> list:
        pool = list(seq)
        self.shuffle(pool)
        return pool[:k]


GEN_PROFILES = {
    "light": dict(recs=(450, 1000), pages=(8, 20), slots=(4, 8), active=(3, 6), p_flush=0.08,
                  p_sp=0.03, p_rb=0.03, p_abort=0.03, ckpts=(1, 3), p_lag=0.3, restarts=(0, 1),
                  hop=0.0, res_k=30, p_hot=0.3, p_multi=0.15, p_same=0.0, p_end=0.3),
    "dense": dict(recs=(800, 1120), pages=(16, 24), slots=(6, 8), active=(6, 10), p_flush=0.12,
                  p_sp=0.07, p_rb=0.07, p_abort=0.05, ckpts=(2, 4), p_lag=0.4, restarts=(2, 3),
                  hop=0.9, res_k=14, p_hot=0.6, p_multi=0.35, p_same=0.4, p_end=0.05),
    "restart": dict(recs=(500, 1080), pages=(8, 24), slots=(4, 8), active=(6, 10), p_flush=0.10,
                    p_sp=0.08, p_rb=0.08, p_abort=0.06, ckpts=(1, 3), p_lag=0.5, restarts=(2, 4),
                    hop=0.9, res_k=10, p_hot=0.6, p_multi=0.35, p_same=0.4, p_end=0.06),
    "max": dict(recs=(1100, 1150), pages=(24, 24), slots=(8, 8), active=(8, 12), p_flush=0.12,
                p_sp=0.07, p_rb=0.07, p_abort=0.05, ckpts=(2, 4), p_lag=0.4, restarts=(2, 3),
                hop=0.9, res_k=14, p_hot=0.6, p_multi=0.35, p_same=0.4, p_end=0.05),
}
LIMIT_RECORDS = 1200
LIMIT_PAGES = 24
SLOT_RANGE = (4, 8)
_ALNUM = "abcdefghijklmnopqrstuvwxyz0123456789"
_MIXED = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TXN_KINDS = ("begin", "update", "clr", "commit", "abort", "end")


def _fresh_id(rng, used, alphabet, n, first_alpha=True):
    while True:
        s = "".join(rng.choice(alphabet) for _ in range(n))
        if first_alpha and not s[0].isalpha():
            continue
        if s.lower() not in used:
            used.add(s.lower())
            return s


# ---------------------------------------------------------------- reference recovery

def undo_point(R, lsn, hops=None):
    via_next = False
    while lsn is not None:
        r = R[lsn]
        if r["type"] == "update":
            return r
        if r["type"] == "clr":
            if via_next and hops is not None:
                hops[0] += 1
            lsn = r["undo_next"]
            via_next = True
        else:
            lsn = r["prev"]
            via_next = False
    return None


def validate(img):
    pages, disk = img["pages"], img["disk"]
    if set(disk) != set(pages) or img.get("dup_frame"):
        return "E_BAD_IMAGE"
    for p, n in pages.items():
        if disk[p].get("corrupt") or len(disk[p]["slots"]) != n:
            return "E_BAD_IMAGE"
    for r in img["records"]:
        for ch in r.get("changes", ()):
            if ch["page"] not in pages or not 0 <= ch["slot"] < pages[ch["page"]]:
                return "E_UNKNOWN_PAGE"
    lsns = [r["lsn"] for r in img["records"]]
    if len(set(lsns)) != len(lsns):
        return "E_DUP_LSN"
    R = {r["lsn"]: r for r in img["records"]}
    for r in img["records"]:
        if r["type"] not in TXN_KINDS:
            continue
        if (r["prev"] is None) != (r["type"] == "begin"):
            return "E_BAD_CHAIN"
        for key in ("prev", "undo_next"):
            v = r.get(key)
            if v is None:
                continue
            t = R.get(v)
            if t is None or v >= r["lsn"] or t.get("txn") != r["txn"]:
                return "E_BAD_CHAIN"
    return None


def analysis(img):
    R = {r["lsn"]: r for r in img["records"]}
    order = sorted(R)
    master = img["master"]
    T, D = {}, {}
    if master:
        end = [r for r in img["records"] if r["type"] == "checkpoint_end" and r["begin_lsn"] == master][0]
        for t in end["txn_table"]:
            T[t["txn"]] = {"state": t["state"], "last": t["last_lsn"]}
        for d in end["dirty_pages"]:
            D[d["page"]] = d["rec_lsn"]
    for lsn in order:
        if lsn < master:
            continue
        r = R[lsn]
        if r["type"] not in TXN_KINDS:
            continue
        if r["type"] == "end":
            T.pop(r["txn"], None)
            continue
        e = T.setdefault(r["txn"], {"state": "running", "last": lsn})
        e["last"] = lsn
        if r["type"] == "commit":
            e["state"] = "committed"
        elif r["type"] == "abort":
            e["state"] = "aborting"
        for ch in r.get("changes", ()):
            D.setdefault(ch["page"], lsn)
    return R, order, T, D


def redo(R, order, D, pages, stats=None):
    start = min(D.values()) if D else None
    examined = applied = 0
    if start is None:
        return start, examined, applied
    for lsn in order:
        r = R[lsn]
        if lsn < start or r["type"] not in ("update", "clr"):
            continue
        examined += 1
        todo = {ch["page"] for ch in r["changes"]
                if ch["page"] in D and lsn >= D[ch["page"]] and lsn > pages[ch["page"]]["page_lsn"]}
        if stats is not None:
            seen = [ch["page"] for ch in r["changes"] if ch["page"] in todo]
            if len(seen) != len(set(seen)):
                stats["same_page_redo"] += 1
            if any(lsn == pages[ch["page"]]["page_lsn"] for ch in r["changes"]):
                stats["equal_page_lsn"] += 1
        for ch in r["changes"]:
            if ch["page"] in todo:
                pg = pages[ch["page"]]
                pg["slots"][ch["slot"]] += ch["delta"]
                pg["page_lsn"] = lsn
                applied += 1
    return start, examined, applied


def appended(R, T, pages, next_lsn, stats=None):
    """Yield the records recovery appends, applying each CLR to pages; mutates R and T."""
    hops = [0] if stats is not None else None
    for tx in sorted(t for t in T if T[t]["state"] == "committed"):
        yield {"lsn": next_lsn, "type": "end", "txn": tx, "prev": T[tx]["last"]}
        next_lsn += 1
        del T[tx]
    up = {tx: undo_point(R, T[tx]["last"], hops) for tx in sorted(T)}
    if stats is not None:
        tops = [u["lsn"] for u in up.values() if u is not None]
        stats["noundo_inside"] += sum(1 for t, u in up.items() if u is None and tops and T[t]["last"] < max(tops))
    for tx in sorted(t for t in up if up[t] is None):
        yield {"lsn": next_lsn, "type": "end", "txn": tx, "prev": T[tx]["last"]}
        next_lsn += 1
        del T[tx], up[tx]
    while up:
        tx = max(up, key=lambda t: (up[t]["lsn"], -t))
        u = up[tx]
        clr = {"lsn": next_lsn, "type": "clr", "txn": tx, "prev": T[tx]["last"],
               "changes": [{"page": c["page"], "slot": c["slot"], "delta": -c["delta"]} for c in u["changes"]],
               "undo_next": u["prev"]}
        next_lsn += 1
        for c in clr["changes"]:
            pages[c["page"]]["slots"][c["slot"]] += c["delta"]
            pages[c["page"]]["page_lsn"] = clr["lsn"]
        T[tx]["last"] = clr["lsn"]
        R[clr["lsn"]] = clr
        yield clr
        up[tx] = undo_point(R, u["prev"], hops)
        if up[tx] is None:
            yield {"lsn": next_lsn, "type": "end", "txn": tx, "prev": T[tx]["last"]}
            next_lsn += 1
            del T[tx], up[tx]
    if stats is not None:
        stats["clr_chain_hops"] += hops[0]


def recover(img, stats=None):
    err = validate(img)
    if err:
        return {"status": "rejected", "error": err}
    R, order, T, D = analysis(img)
    pages = {p: {"page_lsn": d["page_lsn"], "slots": list(d["slots"])} for p, d in img["disk"].items()}
    winners = sorted(t for t, e in T.items() if e["state"] == "committed")
    losers = sorted(t for t, e in T.items() if e["state"] != "committed")
    if stats is not None:
        stats["winners_out_of_order"] += int([t for t in T if T[t]["state"] == "committed"] != winners)
        stats["redo_below_master"] += int(bool(D) and min(D.values()) < img["master"])
    start, examined, applied = redo(R, order, D, pages, stats)
    app = list(appended(R, T, pages, max(order) + 1, stats))
    return {"status": "recovered", "pages": pages, "winners": winners, "losers": losers,
            "redo_start": start, "examined": examined, "applied": applied, "appended": app,
            "next_lsn": max(order) + 1 + len(app)}


def canonical_pages(pages) -> bytes:
    return json.dumps(pages, sort_keys=True, separators=(",", ":")).encode("utf-8")


def documents(book, recover_fn=None):
    out = {"module_core.json": {}, "module_metrics.json": {}, "dependency_resolution.json": {}, "summary.json": {}}
    for img in book["images"]:
        iid = img["id"]
        res = (recover_fn or recover)(img)
        if res["status"] == "rejected":
            for doc in out.values():
                doc[iid] = {"status": "rejected", "error": res["error"]}
            continue
        clrs = [a for a in res["appended"] if a["type"] == "clr"]
        out["module_core.json"][iid] = {"status": "recovered", "pages": res["pages"]}
        out["module_metrics.json"][iid] = {
            "status": "recovered", "winners": len(res["winners"]), "losers": len(res["losers"]),
            "redo_start_lsn": res["redo_start"], "redo_records": res["examined"],
            "redo_changes_applied": res["applied"], "clrs_appended": len(clrs),
            "ends_appended": len(res["appended"]) - len(clrs), "next_lsn": res["next_lsn"]}
        out["dependency_resolution.json"][iid] = {"status": "recovered", "losers": res["losers"],
                                                  "appended": res["appended"]}
        owner = img["catalog"]
        clients = {}
        for tx in res["winners"] + res["losers"]:
            c = clients.setdefault(owner[tx], {"winners": 0, "losers": 0, "compensated": 0})
            c["winners" if tx in res["winners"] else "losers"] += 1
        for a in clrs:
            clients[owner[a["txn"]]]["compensated"] += sum(abs(c["delta"]) for c in a["changes"])
        audits = {}
        for q in img["queries"]:
            total = 0
            for p in q["pages"]:
                sl = res["pages"][p]["slots"]
                total += sum(sl) if q["slot"] == "all" else sl[q["slot"]]
            audits[q["id"]] = total
        out["summary.json"][iid] = {"status": "recovered",
                                    "image_sha256": hashlib.sha256(canonical_pages(res["pages"])).hexdigest(),
                                    "clients": dict(sorted(clients.items())), "audits": audits}
    return {name: {"images": dict(sorted(doc.items()))} for name, doc in out.items()}


def features(img):
    stats = {"same_page_redo": 0, "equal_page_lsn": 0, "clr_chain_hops": 0, "noundo_inside": 0,
             "winners_out_of_order": 0, "redo_below_master": 0}
    recover(img, stats)
    R = {r["lsn"]: r for r in img["records"]}
    T = analysis(img)[2]
    losers = {t for t, e in T.items() if e["state"] != "committed"}
    winners = {t for t, e in T.items() if e["state"] == "committed"} | {
        r["txn"] for r in img["records"] if r["type"] == "commit"}
    flushed = 0
    for p, d in img["disk"].items():
        top = R.get(d["page_lsn"])
        if top is None or top.get("txn") not in losers:
            continue
        if any(r.get("txn") in winners and r["lsn"] < d["page_lsn"] and any(c["page"] == p for c in r["changes"])
               for r in img["records"] if r["type"] in ("update", "clr")):
            flushed += 1
    stats["loser_over_winner_flush"] = flushed
    tail = 0
    if img["master"]:
        end = [r for r in img["records"] if r["type"] == "checkpoint_end" and r["begin_lsn"] == img["master"]][0]
        tail = sum(1 for r in img["records"] if r["type"] in TXN_KINDS and img["master"] < r["lsn"] < end["lsn"])
    stats["checkpoint_tail"] = tail
    stats["restarts_with_clr"] = img["restarts_with_clr"]
    return stats


DENSE_NEEDS = ("same_page_redo", "equal_page_lsn", "clr_chain_hops", "noundo_inside", "winners_out_of_order",
               "redo_below_master", "loser_over_winner_flush", "checkpoint_tail")


# ---------------------------------------------------------------- generator

class _Sim:
    def __init__(self, rng, prof):
        self.rng, self.p = rng, prof
        used = set()
        n = rng.randint(*prof["pages"])
        self.pages = {_fresh_id(rng, used, _MIXED, 4): rng.randint(*prof["slots"]) for _ in range(n)}
        self.genesis = {p: [rng.randint(-500, 900) for _ in range(k)] for p, k in self.pages.items()}
        self.disk = {p: {"page_lsn": 0, "slots": list(v)} for p, v in self.genesis.items()}
        self.buf = {p: {"page_lsn": 0, "slots": list(v)} for p, v in self.genesis.items()}
        self.dirty = {}
        self.lsn = rng.randint(4_300_000_000, 9_000_000_000)
        self.log, self.R, self.T = [], {}, {}
        self.master = 0
        self.txids = set()
        self.pending = None
        self.amax = rng.randint(*prof["active"])
        self.restarts_with_clr = 0

    def emit(self, **r):
        self.lsn += self.rng.randint(1, 9)
        r["lsn"] = self.lsn
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
        if self.rng.random() < self.p["p_hot"]:
            p = max(self.dirty, key=lambda q: (self.dirty[q], q))
        else:
            p = self.rng.choice(sorted(self.dirty))
        self.disk[p] = {"page_lsn": self.buf[p]["page_lsn"], "slots": list(self.buf[p]["slots"])}
        del self.dirty[p]

    def txid(self):
        while True:
            t = self.rng.randint(100, 999999)
            if t not in self.txids:
                self.txids.add(t)
                return t

    def undo_step(self, tx):
        e = self.T[tx]
        u = undo_point(self.R, e["last"])
        target = e["roll"]
        if u is None or (target is not None and u["lsn"] <= target):
            if target is None and self.rng.random() < 0.5:
                self.emit(type="end", txn=tx, prev=e["last"])
                del self.T[tx]
            elif target is None:
                e["roll"] = "fin"
            else:
                e["roll"] = "no"
            return
        c = self.emit(type="clr", txn=tx, prev=e["last"],
                      changes=[{"page": ch["page"], "slot": ch["slot"], "delta": -ch["delta"]} for ch in u["changes"]],
                      undo_next=u["prev"])
        e["last"] = c["lsn"]
        self.apply(c)

    def snapshot(self):
        txns = [{"txn": t, "state": e["state"], "last_lsn": e["last"]} for t, e in sorted(self.T.items())]
        self.rng.shuffle(txns)
        dirty = [{"page": p, "rec_lsn": v} for p, v in sorted(self.dirty.items())]
        self.rng.shuffle(dirty)
        return txns, dirty

    def run(self, target):
        rng, p = self.rng, self.p
        nck = rng.randint(*p["ckpts"])
        base = len(self.log)
        span = range(base + (target - base) // 6, max(target, base + nck + 1))
        ck_at = sorted(rng.sample(span, min(nck, len(span))))
        while len(self.log) < target:
            if ck_at and len(self.log) >= ck_at[0] and self.pending is None:
                ck_at.pop(0)
                b = self.emit(type="checkpoint_begin")
                self.pending = [b["lsn"], self.snapshot(), rng.randint(1, 12)]
            if self.pending is not None:
                if self.pending[2] <= 0:
                    bl, snap, _ = self.pending
                    self.emit(type="checkpoint_end", begin_lsn=bl, txn_table=snap[0], dirty_pages=snap[1])
                    self.pending = None
                    if rng.random() > p["p_lag"] or not self.master:
                        self.master = bl
                else:
                    self.pending[2] -= 1
            running = sorted(t for t, e in self.T.items() if e["state"] == "running" and e["roll"] == "no")
            rolling = sorted(t for t, e in self.T.items() if e["roll"] is None or isinstance(e["roll"], int))
            committed = sorted(t for t, e in self.T.items() if e["state"] == "committed" or e["roll"] == "fin")
            if rng.random() < p["p_flush"]:
                self.flush()
            elif sum(e["roll"] != "dead" for e in self.T.values()) < self.amax and rng.random() < 0.25:
                t = self.txid()
                b = self.emit(type="begin", txn=t, prev=None)
                self.T[t] = {"state": "running", "last": b["lsn"], "sp": [], "roll": "no"}
            elif rolling and rng.random() < 0.5:
                self.undo_step(rng.choice(rolling))
            elif committed and rng.random() < p["p_end"]:
                t = rng.choice(committed)
                self.emit(type="end", txn=t, prev=self.T[t]["last"])
                del self.T[t]
            elif running:
                t = rng.choice(running)
                e = self.T[t]
                y = rng.random()
                if y < p["p_sp"]:
                    e["sp"].append(e["last"])
                elif y < p["p_sp"] + p["p_rb"] and e["sp"]:
                    e["roll"] = e["sp"].pop()
                elif y < p["p_sp"] + p["p_rb"] + p["p_abort"]:
                    a = self.emit(type="abort", txn=t, prev=e["last"])
                    e.update(last=a["lsn"], state="aborting", roll=None)
                elif y < p["p_sp"] + p["p_rb"] + p["p_abort"] + 0.06:
                    c = self.emit(type="commit", txn=t, prev=e["last"])
                    e.update(last=c["lsn"], state="committed")
                else:
                    k = 1 if rng.random() > p["p_multi"] else rng.randint(2, 3)
                    picks = rng.sample(sorted(self.pages), k)
                    if k > 1 and rng.random() < p["p_same"]:
                        picks[-1] = picks[0]
                    chs = [{"page": pg, "slot": rng.below(self.pages[pg]),
                            "delta": rng.choice([v for v in range(-60, 61) if v])} for pg in picks]
                    u = self.emit(type="update", txn=t, prev=e["last"], changes=chs)
                    e["last"] = u["lsn"]
                    self.apply(u)

    def image_view(self):
        return {"records": self.log, "master": self.master, "pages": self.pages,
                "disk": {p: {"page_lsn": d["page_lsn"], "slots": list(d["slots"])} for p, d in self.disk.items()}}

    def restart(self):
        """Crash, then run a restart that is itself interrupted during undo; False if it would undo too little."""
        rng = self.rng
        R, order, T, D = analysis(self.image_view())
        buf = {p: {"page_lsn": d["page_lsn"], "slots": list(d["slots"])} for p, d in self.disk.items()}
        dirty = {}
        start = min(D.values()) if D else None
        flush_at = set()
        for lsn in order:
            r = R[lsn]
            if start is None or lsn < start or r["type"] not in ("update", "clr"):
                continue
            todo = {ch["page"] for ch in r["changes"]
                    if ch["page"] in D and lsn >= D[ch["page"]] and lsn > buf[ch["page"]]["page_lsn"]}
            for ch in r["changes"]:
                if ch["page"] in todo:
                    buf[ch["page"]]["slots"][ch["slot"]] += ch["delta"]
                    buf[ch["page"]]["page_lsn"] = lsn
                    dirty.setdefault(ch["page"], lsn)
        plan = list(appended(dict(R), {t: dict(e) for t, e in T.items()},
                             {p: {"page_lsn": v["page_lsn"], "slots": list(v["slots"])} for p, v in buf.items()},
                             max(order) + 1))
        Rp = dict(R)
        for r in plan:
            Rp[r["lsn"]] = r
        clr_at = [i for i, r in enumerate(plan) if r["type"] == "clr"]
        if len(clr_at) < 2:
            return False
        stops = [i + 1 for i in clr_at if i + 1 < len(plan) and plan[i]["undo_next"] is not None
                 and Rp[plan[i]["undo_next"]]["type"] == "clr"]
        stops += [i + 1 for i in clr_at if i + 1 < len(plan) and plan[i + 1]["type"] == "end"]
        stop = clr_at[0] + rng.randint(1, self.p["res_k"])
        if stops and rng.random() < self.p["hop"]:
            stop = rng.choice(stops)
        stop = min(stop, clr_at[-1])
        self.pending = None
        self.buf, self.dirty = buf, dirty
        self.T = {t: {"state": e["state"], "last": e["last"], "sp": [], "roll": "dead"} for t, e in T.items()}
        for k, r in enumerate(plan):
            if k >= stop:
                break
            self.log.append(r)
            if r["type"] == "end":
                del self.T[r["txn"]]
                continue
            self.T[r["txn"]]["last"] = r["lsn"]
            for ch in r["changes"]:
                self.apply1(r, ch)
            if rng.random() < 0.15:
                self.flush()
        self.R = {r["lsn"]: r for r in self.log}
        self.lsn = self.log[-1]["lsn"]
        self.restarts_with_clr += 1
        while rng.random() < 0.5:
            self.flush()
        return True


def build_image(rng, profile, iid, clients):
    prof = GEN_PROFILES[profile]
    s = _Sim(rng, prof)
    target = rng.randint(*prof["recs"])
    nres = rng.randint(*prof["restarts"])
    seg = target // (nres + 1)
    s.run(seg)
    for i in range(nres):
        s.restart()
        s.run(min(target, len(s.log) + seg))
    truth = {p: list(v) for p, v in s.genesis.items()}
    winners = {r["txn"] for r in s.log if r["type"] == "commit"}
    for r in s.log:
        if r["type"] in ("update", "clr") and r["txn"] in winners:
            for ch in r["changes"]:
                truth[ch["page"]][ch["slot"]] += ch["delta"]
    records = [dict(r) for r in s.log]
    txns = sorted({r["txn"] for r in records if "txn" in r})
    qused = set()
    queries = []
    for _ in range(rng.randint(2, 5)):
        pg = sorted(rng.sample(sorted(s.pages), rng.randint(1, 4)))
        queries.append({"id": "q" + _fresh_id(rng, qused, _ALNUM, 5, False), "image": iid, "pages": pg,
                        "slot": rng.choice(["all", 0, 1, 2, 3])})
    return {"id": iid, "pages": dict(s.pages), "disk": s.disk, "master": s.master, "records": records,
            "truth": truth, "restarts_with_clr": s.restarts_with_clr,
            "catalog": {t: rng.choice(clients) for t in txns}, "queries": queries}


def _fits(img):
    return (len(img["records"]) <= LIMIT_RECORDS and len(img["pages"]) <= LIMIT_PAGES
            and all(SLOT_RANGE[0] <= n <= SLOT_RANGE[1] for n in img["pages"].values()))


def _light_ok(img):
    if any(len({c["page"] for c in r["changes"]}) != len(r["changes"])
           for r in img["records"] if r["type"] in ("update", "clr")):
        return False
    f = features(img)
    return f["clr_chain_hops"] == 0 and f["same_page_redo"] == 0


def build_book(seed, profile, n_images, dense=False, light=False, min_restarts=0):
    rng = Rng(seed)
    used = set()
    clients = [_fresh_id(rng, set(), "abcdefghijklmnopqrstuvwxyz", 6) for _ in range(9)]
    images = []
    while len(images) < n_images:
        iid = _fresh_id(rng, used, _ALNUM, 6)
        for _attempt in range(400):
            img = build_image(rng, profile, iid, clients)
            if not _fits(img) or img["restarts_with_clr"] < min_restarts:
                continue
            if light and not _light_ok(img):
                continue
            if dense and not all(features(img)[k] > 0 for k in DENSE_NEEDS):
                continue
            break
        else:
            raise AssertionError("generator could not meet the requested profile")
        assert _fits(img)
        images.append(img)
    return {"images": images}


# ---------------------------------------------------------------- defects for rejection books

def plant_defect(rng, img, code):
    recs = img["records"]
    txn_recs = [r for r in recs if r["type"] in TXN_KINDS]
    if code == "E_BAD_IMAGE":
        kind = rng.below(4)
        p = rng.choice(sorted(img["pages"]))
        if kind == 0:
            img["disk"][p]["corrupt"] = True
        elif kind == 1:
            del img["disk"][p]
        elif kind == 2:
            img["disk"][p]["slots"].append(rng.randint(0, 99))
        else:
            img["dup_frame"] = p
    elif code == "E_UNKNOWN_PAGE":
        r = rng.choice([r for r in recs if r["type"] in ("update", "clr")])
        ch = rng.choice(r["changes"])
        if rng.below(2):
            ch["page"] = _fresh_id(rng, {p.lower() for p in img["pages"]}, _MIXED, 4)
        else:
            ch["slot"] = img["pages"][ch["page"]]
    elif code == "E_DUP_LSN":
        a, b = rng.sample(txn_recs, 2)
        dup = dict(a)
        dup["lsn"] = b["lsn"]
        dup["type"] = "commit" if a["type"] != "begin" else "begin"
        dup.pop("changes", None)
        dup.pop("undo_next", None)
        dup["prev"] = None if dup["type"] == "begin" else b["lsn"] - 1
        recs.append(dup)
    elif code == "E_BAD_CHAIN":
        r = rng.choice([r for r in txn_recs if r["prev"] is not None])
        kind = rng.below(3)
        if kind == 0:
            others = [o["lsn"] for o in txn_recs if o["txn"] != r["txn"] and o["lsn"] < r["lsn"]]
            r["prev"] = rng.choice(others) if others else r["lsn"] + 1
        elif kind == 1:
            later = [o["lsn"] for o in txn_recs if o["txn"] == r["txn"] and o["lsn"] > r["lsn"]]
            r["prev"] = rng.choice(later) if later else r["lsn"]
        else:
            r["prev"] = r["prev"] - 1 if r["prev"] - 1 not in {o["lsn"] for o in recs} else r["lsn"] + 7_000_000
    elif code == "E_BAD_CHAIN/undo_next":
        r = rng.choice([r for r in recs if r["type"] == "clr" and r["undo_next"] is not None])
        kind = rng.below(3)
        if kind == 0:
            others = [o["lsn"] for o in txn_recs if o["txn"] != r["txn"] and o["lsn"] < r["lsn"]]
            r["undo_next"] = rng.choice(others) if others else r["lsn"] + 1
        elif kind == 1:
            r["undo_next"] = r["lsn"]
        else:
            taken = {o["lsn"] for o in recs}
            r["undo_next"] = r["undo_next"] - 1 if r["undo_next"] - 1 not in taken else r["lsn"] + 7_000_000
    else:
        raise ValueError(code)


# ---------------------------------------------------------------- file rendering

def render_book(book, rng):
    """Return {file name: bytes} for the six recovery inputs of a book."""
    lines = []
    for img in book["images"]:
        for r in img["records"]:
            row = {"image": img["id"]}
            row.update(r)
            lines.append(json.dumps(row, separators=(",", ":")))
    rng.shuffle(lines)
    frames = []
    for img in book["images"]:
        for p in sorted(img["disk"]):
            d = img["disk"][p]
            body = bytearray()
            for text in (img["id"], p):
                raw = text.encode("ascii")
                body += struct.pack(">H", len(raw)) + raw
            body += struct.pack(">QH", d["page_lsn"], len(d["slots"]))
            body += b"".join(struct.pack(">q", v) for v in d["slots"])
            crc = zlib.crc32(bytes(body))
            if d.get("corrupt"):
                crc ^= 1 << rng.below(32)
            frames.append(bytes(body) + struct.pack(">I", crc))
            if img.get("dup_frame") == p:
                frames.append(frames[-1])
    rng.shuffle(frames)
    ini = []
    for img in book["images"]:
        ini.append("[%s]" % img["id"])
        items = sorted(img["pages"].items())
        rng.shuffle(items)
        ini += ["%s = %d" % kv for kv in items]
        ini.append("")
    toml = ["# master record of every crash image", ""]
    for img in book["images"]:
        toml += ["[images.%s]" % img["id"], "master_lsn = %d" % img["master"], ""]
    rows = [(img["id"], t, c) for img in book["images"] for t, c in img["catalog"].items()]
    rng.shuffle(rows)
    csv_text = "image,txn,client\n" + "".join("%s,%d,%s\n" % row for row in rows)
    queries = [q for img in book["images"] for q in img["queries"]]
    rng.shuffle(queries)
    return {
        "journal.jsonl": ("\n".join(lines) + "\n").encode("utf-8"),
        "disk_pages.bin": b"CPG1" + b"".join(frames),
        "page_map.ini": "\n".join(ini).encode("utf-8"),
        "checkpoint.toml": "\n".join(toml).encode("utf-8"),
        "txn_catalog.csv": csv_text.encode("utf-8"),
        "audit_queries.json": (json.dumps({"queries": queries}, indent=1) + "\n").encode("utf-8"),
    }


# ---------------------------------------------------------------- books

def shipped_book(seed):
    """The book shipped in /app/data: light images plus one E_BAD_CHAIN and one E_BAD_IMAGE image."""
    book = build_book(seed, "light", 36, light=True)
    rng = Rng(seed ^ 0x5EED)
    plant_defect(rng, book["images"][-1], "E_BAD_CHAIN")
    plant_defect(rng, book["images"][-2], "E_BAD_IMAGE")
    return book
