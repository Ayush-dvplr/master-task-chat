"""Checks for the repaired pagerecover package and the recovery documents it writes.

The package is taken from /app/out/package.zip, unpacked into a scratch directory and run
as an unprivileged user from a foreign working directory on books generated here.
"""
import ast
import base64
import copy
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
import zipfile
import zlib
from pathlib import Path

from rewardkit import criteria, criterion

BOOK_SEED = int("5113927")
SHIPPED_SEED = int("806610")
PACKAGE = "pagerecover"
APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
OUT_DIR = APP_ROOT / "out"
ARCHIVE = OUT_DIR / "package.zip"
DOCUMENTS = ("module_core.json", "module_metrics.json", "dependency_resolution.json", "summary.json")
BOOK_FILES = ("journal.jsonl", "disk_pages.bin", "page_map.ini", "checkpoint.toml",
              "txn_catalog.csv", "audit_queries.json")
CATEGORIES = {"packaging", "dependency", "decoding", "config", "validation", "recovery", "reporting", "cli"}
RUN_TIMEOUT = 300
TIME_LIMIT = 60.0
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_RUNNER = ("import runpy, sys; sys.path.insert(0, sys.argv[1]); sys.argv = [sys.argv[2]] + sys.argv[3:]; "
           "runpy.run_module(sys.argv[0], run_name='__main__', alter_sys=True)")
_VERSION_PROBE = "import sys; sys.path.insert(0, sys.argv[1]); import pagerecover; print(pagerecover.__version__)"
_SHIPPED_DATA = {
    'ci_config.yaml': [
        'eNplkL1SAzEMhHs/hSaNoTjfAN3xMB7jU4iI/yLpjglPjw1NII2K3W9WWvFWlDIu0K56quXFPT2bgvpZ+bzAShLeEq4m1pxD',
        'WWUxABPYXxamDFshVRQdaKw7MkwCQxCYdvuXjnCg3CortPCOjD/8KzSmog83kvO+T6FavH883IVYe5/iYiJr7f/r+tmNEoaU',
        'YLqAcLQmsNIxRPWtJorXUShwPNHeXzCH1ua66dxCPPdw90Wt+4xj3Y0tmI6jo/uQWjqwoiJnKiRK0Q9xAeUNzTdRm3e5',
    ],
    'compiler_flags.json': [
        'eNpNjEEOwiAQAO+8gnC2BqiatO/onVTYpBulS9j1UI1/V+zF68xkXkprUzZZaDWjNv3ReXNo7LoJREoQ4gLx9nVSH/AzyHSf',
        'BVLAXKjKv3piCZFyqcCM+5GFKqT9mUCgZlyRBWNosWAGljkXbq23buhs37nTZIfRX8azN+qtPnK9MqE=',
    ],
    'dependency_manifest.json': [
        'eNpFjtEOwiAMRd/3FQvPurjpk79izMKgbo2MIjCVGP/dwrL41pOe295PVdfCSXWXI4hzHkfwoOgJXuzKLsWJbO8XG3EuyrFp',
        'u3UnjaEX6F6DA6vBqtQ7MqhS1kLUBoc9WZNW+0Z+QM3aduyfQwgcubDFXqTZYIkweHgsEGLYeIrRvTeQSJkF07W8yDZ6bsT1',
        'A5LNPbrm1BxE9a1+T0ZH4Q==',
    ],
    'expected_targets.json': [
        'eNp9kMFOAyEQhu/7FJs9N+zdm4k9evFqDKEwVVqGIczQZDW+u+Ba08SVC5D/+/ID8zGM42SyffMX0Ah4gMzT3fhc4wrSkjKd',
        'wIoSwjDt1vRpf//wuFforgFnOyfzChksXSDPWvvoRWuVlv8VND52FRt8hwYyDnJHaGfu8J996SqJstyWCLDw3FbNSGdoqJKX',
        '3TpG8Udj5WaAs0lppiK11p5rs3r36dr1yxjCsVWqE1P8Qw/FB6fXp2wbSK4E0JYydAUEyd7ytuMgQXQQ7VLvYgpFPMVtlQui',
        'qYP7hu33w+fwBSVFua4=',
    ],
    'project.zip': [
        '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',
        '/ju/hIAe/Pc/YJo//RDv/g+PzPcx',
    ],
}
_SHIPPED_SHA = {
    'audit_queries.json': 'a67a7f6205b83b9df4f42dcb3886841310b458bc590b1f1f1a5ee2af6a121b29',
    'checkpoint.toml': 'e05e7b0e25a4b8f07e674d4ceec5a51e7709ee8a6d0304efb927c7ac6b36ce1c',
    'disk_pages.bin': 'e6f82822c7913ff89e3461f1d251315b9dfac4ce478436935a0c015210c0a570',
    'journal.jsonl': '2809c762d757988c48e9aa844ae64cc3a394eba70b48c0245a2e5e9127f26d25',
    'page_map.ini': '14b869671416a570a3fe92f53644e91b26fd056f35fa4a5784e1eca5cc90baea',
    'txn_catalog.csv': 'a6b67d2841f80be7d921819e5a6f4f5cc1ee19335a183afb62a1d2ba18832689',
}
_CACHE = {}


# ---------------------------------------------------------------- book generator (same one that wrote /app/data)

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


# ---------------------------------------------------------------- sandbox helpers

def _memo(key, build):
    if key not in _CACHE:
        try:
            _CACHE[key] = (True, build())
        except Exception as exc:  # cached so every dependent check reports the same cause
            _CACHE[key] = (False, exc)
    ok, value = _CACHE[key]
    if not ok:
        raise value
    return value


def _scratch(prefix):
    path = Path(tempfile.mkdtemp(prefix=prefix))
    path.chmod(0o777)
    return path


def _open_tree(root):
    for dirpath, dirnames, filenames in os.walk(root):
        os.chmod(dirpath, 0o777)
        for name in filenames:
            os.chmod(os.path.join(dirpath, name), 0o644)


def _shipped_file(name):
    return zlib.decompress(base64.b64decode("".join(_SHIPPED_DATA[name])))


def _shipped_json(name):
    return json.loads(_shipped_file(name).decode("utf-8"))


def _root_only_tests_present():
    try:
        info = os.stat("/tests")
    except OSError:
        return False
    return info.st_uid == 0 and stat.S_IMODE(info.st_mode) & 0o077 == 0


def _grant_read(argument):
    """Agent editors can leave 0600 files; the unprivileged run needs to read what the agent built."""
    path = Path(str(argument))
    try:
        if not path.is_absolute() or APP_ROOT not in (path, *path.parents) or not path.exists():
            return
        for parent in [path, *path.parents]:
            mode = parent.stat().st_mode
            extra = stat.S_IROTH | (stat.S_IXOTH if stat.S_ISDIR(mode) else 0)
            parent.chmod(stat.S_IMODE(mode) | extra)
            if parent == APP_ROOT:
                break
    except OSError:
        pass


def _untrusted_command(command):
    if os.name != "posix":
        raise RuntimeError("checks need a POSIX host")
    if os.geteuid() != 0:
        if _root_only_tests_present():
            raise RuntimeError("checks must start as root to drop privileges")
        return list(command)
    for argument in command:
        _grant_read(argument)
    return _SETPRIV + list(command)


def _env(home):
    return {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(home), "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"}


def _run(command, cwd, timeout=RUN_TIMEOUT, extra_env=None):
    env = _env(cwd)
    env.update(extra_env or {})
    started = time.monotonic()
    try:
        done = subprocess.run(_untrusted_command(command), text=True, capture_output=True, env=env,
                              cwd=str(cwd), timeout=timeout)
    except subprocess.TimeoutExpired:
        done = subprocess.CompletedProcess(command, -9, "", "timed out after %d s" % timeout)
    return done, time.monotonic() - started


def _artifact(name):
    path = OUT_DIR / name
    _grant_read(path)
    return path


def _json_artifact(name):
    path = _artifact(name)
    assert path.is_file(), "%s is missing" % path
    return json.loads(path.read_text(encoding="utf-8"))


def _archive_members():
    def build():
        path = _artifact("package.zip")
        assert path.is_file(), "%s is missing" % path
        with zipfile.ZipFile(path) as zf:
            return [(info, zf.read(info)) for info in zf.infolist()]
    return _memo("members", build)


def _extract_archive():
    def build():
        root = _scratch("package-") / "pkg"
        root.mkdir()
        for info, data in _archive_members():
            name = info.filename
            assert not name.startswith("/") and ".." not in name.split("/"), "unsafe member %s" % name
            assert "\\" not in name and "\x00" not in name, "unsafe member %s" % name
            if name.endswith("/"):
                continue
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        _open_tree(root.parent)
        assert (root / "src" / PACKAGE / "__init__.py").is_file(), "archive has no src/%s/__init__.py" % PACKAGE
        return root
    return _memo("extract", build)


def _shipped_project():
    def build():
        with zipfile.ZipFile(io.BytesIO(_shipped_file("project.zip"))) as zf:
            return {name[len("project/"):]: zf.read(name) for name in zf.namelist() if name.startswith("project/")}
    return _memo("project", build)


# ---------------------------------------------------------------- books

def _scaled(book, factor):
    scaled = copy.deepcopy(book)
    for img in scaled["images"]:
        for d in img["disk"].values():
            d["slots"] = [v * factor for v in d["slots"]]
        for r in img["records"]:
            for ch in r.get("changes", ()):
                ch["delta"] *= factor
    return scaled


def _rejection_book():
    book = build_book(BOOK_SEED + 3, "restart", 11, dense=True, min_restarts=2)
    plan = [("E_BAD_IMAGE",), ("E_BAD_IMAGE",), ("E_UNKNOWN_PAGE",), ("E_DUP_LSN",), ("E_BAD_CHAIN",),
            ("E_BAD_IMAGE", "E_BAD_CHAIN"), ("E_UNKNOWN_PAGE", "E_DUP_LSN"), ("E_DUP_LSN", "E_BAD_CHAIN"),
            ("E_BAD_CHAIN/undo_next",)]
    rng = Rng(BOOK_SEED ^ 0x4E7)
    for img, codes in zip(book["images"], plan):
        pristine = copy.deepcopy(img)
        while True:
            for code in reversed(codes):
                plant_defect(rng, img, code)
            if validate(img) == codes[0].split("/")[0]:
                break
            img.clear()
            img.update(copy.deepcopy(pristine))
    return book


def _book(name):
    def build():
        if name == "shipped":
            book = shipped_book(SHIPPED_SEED)
            files = render_book(book, Rng(SHIPPED_SEED ^ 0xF11E))
            for fname, data in files.items():
                assert hashlib.sha256(data).hexdigest() == _SHIPPED_SHA[fname], "generator drift on %s" % fname
            return book
        if name == "dense":
            book = build_book(BOOK_SEED, "dense", 12, dense=True, min_restarts=2)
        elif name == "restart":
            book = build_book(BOOK_SEED + 1, "restart", 12, dense=True, min_restarts=2)
        elif name == "max":
            book = build_book(BOOK_SEED + 2, "max", 12, dense=True, min_restarts=2)
        elif name == "rejection":
            book = _rejection_book()
        elif name == "relocated":
            book = build_book(BOOK_SEED + 4, "dense", 8, dense=True, min_restarts=2)
        elif name == "scaled":
            book = _scaled(_book("dense"), 3)
        elif name == "missing":
            book = build_book(BOOK_SEED + 5, "light", 3, light=True)
        else:
            raise KeyError(name)
        assert len(book["images"]) <= 40 and all(_fits(img) for img in book["images"]), "book outside limits"
        return book
    return _memo(("book", name), build)


def _book_dir(name):
    def build():
        base = _scratch("book-")
        where = base / ("relocated book" if name == "relocated" else "book") / "inputs"
        where.mkdir(parents=True)
        files = render_book(_book(name), Rng(BOOK_SEED * 7 + len(name)))
        for fname, data in files.items():
            (where / fname).write_bytes(data)
        if name == "missing":
            (where / Rng(BOOK_SEED).choice(sorted(BOOK_FILES))).unlink()
        _open_tree(base)
        return where
    return _memo(("dir", name), build)


def _expected(name):
    return _memo(("expected", name), lambda: documents(_book(name)))


def _run_package(name, attempt=1):
    def build():
        root = _extract_archive()
        base = _scratch("run-")
        out = base / "out dir"
        cwd = base / "elsewhere"
        cwd.mkdir()
        _open_tree(base)
        done, elapsed = _run([sys.executable, "-I", "-B", "-c", _RUNNER, str(root / "src"), PACKAGE, "recover",
                              "--data", str(_book_dir(name)), "--out", str(out)], cwd)
        return done, elapsed, out
    return _memo(("run", name, attempt), build)


def _delivered(name, attempt=1):
    def build():
        done, _elapsed, out = _run_package(name, attempt)
        assert done.returncode == 0, "package exited %s on the %s book: %s" % (
            done.returncode, name, done.stderr.strip()[-600:])
        docs = {}
        for doc in DOCUMENTS:
            path = out / doc
            assert path.is_file(), "package wrote no %s for the %s book" % (doc, name)
            docs[doc] = json.loads(path.read_text(encoding="utf-8"))
        return docs
    return _memo(("delivered", name, attempt), build)


def _first_difference(want, got, path="$"):
    if isinstance(want, dict) and isinstance(got, dict):
        for key in sorted(set(want) | set(got), key=str):
            if key not in got:
                return "%s.%s missing" % (path, key)
            if key not in want:
                return "%s.%s unexpected" % (path, key)
            found = _first_difference(want[key], got[key], "%s.%s" % (path, key))
            if found:
                return found
        return None
    if isinstance(want, list) and isinstance(got, list):
        for index, (a, b) in enumerate(zip(want, got)):
            found = _first_difference(a, b, "%s[%d]" % (path, index))
            if found:
                return found
        if len(want) != len(got):
            return "%s: length %d != %d" % (path, len(got), len(want))
        return None
    if type(want) is not type(got) or want != got:
        return "%s: %r != %r" % (path, got, want)
    return None


def _same(label, want, got):
    found = _first_difference(want, got)
    assert found is None, "%s differs first at %s" % (label, found)


# ---------------------------------------------------------------- checks

def _check_artifacts():
    for name in ("package.zip", "selftest.json", "build_report.json") + DOCUMENTS:
        path = _artifact(name)
        assert path.is_file() and path.stat().st_size > 0, "%s is missing or empty" % path
        if name.endswith(".json"):
            json.loads(path.read_text(encoding="utf-8"))


def _check_archive_layout():
    targets = _shipped_json("expected_targets.json")
    flags = _shipped_json("compiler_flags.json")
    stamp = tuple(int(x) for x in re.split(r"[-T:]", flags["deterministic_zip_timestamps"]))
    method = {"stored": zipfile.ZIP_STORED, "deflated": zipfile.ZIP_DEFLATED}[flags["zip_compression"]]
    names = []
    for info, _data in _archive_members():
        if info.filename.endswith("/"):
            continue
        names.append(info.filename)
        assert info.compress_type == method, "%s uses compression %d" % (info.filename, info.compress_type)
        assert info.date_time == stamp, "%s has timestamp %s" % (info.filename, info.date_time)
    assert len(names) == len(set(names)), "archive repeats a member"
    missing = sorted(set(targets["archive_members"]) - set(names))
    assert not missing, "archive lacks %s" % missing
    extra = sorted(n for n in set(names) - set(targets["archive_members"])
                   if not re.fullmatch(r"src/pagerecover/[A-Za-z0-9_]+\.py", n))
    assert not extra, "archive holds unexpected members %s" % extra


def _check_package_metadata():
    root = _extract_archive()
    wanted = _shipped_json("dependency_manifest.json")["required_version"]
    meta = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = meta.get("project", {})
    assert project.get("name") == PACKAGE, "pyproject names %r" % project.get("name")
    assert project.get("version") == wanted, "pyproject version %r != %r" % (project.get("version"), wanted)
    assert project.get("requires-python") in (">=3.12", ">=3.12.0"), "requires-python %r" % project.get(
        "requires-python")
    assert not project.get("dependencies"), "runtime dependencies %r" % project.get("dependencies")
    package_dir = meta.get("tool", {}).get("setuptools", {}).get("package-dir", {})
    assert package_dir.get("") == "src", "package-dir %r" % package_dir
    cwd = _scratch("probe-")
    done, _ = _run([sys.executable, "-I", "-B", "-c", _VERSION_PROBE, str(root / "src")], cwd, timeout=60)
    assert done.returncode == 0, "importing the archived package failed: %s" % done.stderr.strip()[-400:]
    assert done.stdout.strip() == wanted, "__version__ %r != %r" % (done.stdout.strip(), wanted)


def _changed_modules():
    shipped = _shipped_project()
    changed = []
    for info, data in _archive_members():
        name = info.filename
        if name.startswith("src/pagerecover/") and not name.endswith("/") and name.count("/") == 2:
            if shipped.get(name) != data:
                changed.append(name.rsplit("/", 1)[1])
    return sorted(changed)


def _check_build_report():
    report = _json_artifact("build_report.json")
    wanted = _shipped_json("dependency_manifest.json")["required_version"]
    assert report.get("ok") is True, "build_report ok is %r" % report.get("ok")
    assert report.get("package") == PACKAGE and report.get("version") == wanted, "build_report names %r %r" % (
        report.get("package"), report.get("version"))
    assert report.get("layout") == "src" and report.get("python") == "3.12", "build_report layout/python wrong"
    assert report.get("fixed_modules") == _changed_modules(), "fixed_modules %r != %r" % (
        report.get("fixed_modules"), _changed_modules())
    cats = report.get("fix_categories")
    assert isinstance(cats, list) and cats and cats == sorted(set(cats)) and set(cats) <= CATEGORIES, (
        "fix_categories %r" % cats)


def _ci_commands():
    commands, inside = [], False
    for line in _shipped_file("ci_config.yaml").decode("utf-8").splitlines():
        if line.startswith("commands:"):
            inside = True
            continue
        if inside and line.startswith("  - "):
            text = line[4:].strip()
            if text.startswith("'") and text.endswith("'"):
                text = text[1:-1].replace("''", "'")
            commands.append(text)
        elif inside and line and not line.startswith(" "):
            inside = False
    return commands


def _archive_unittest():
    def build():
        root = _extract_archive()
        done, _ = _run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"], root,
                       timeout=120, extra_env={"PYTHONPATH": str(root / "src")})
        ran = re.search(r"^Ran (\d+) tests?", done.stderr, re.M)
        assert ran, "archive tests did not run: %s" % done.stderr.strip()[-400:]
        passed = len(re.findall(r" \.\.\. ok$", done.stderr, re.M))
        return int(ran.group(1)), passed
    return _memo("unittest", build)


def _check_selftest():
    report = _json_artifact("selftest.json")
    wanted = _shipped_json("dependency_manifest.json")["required_version"]
    run, passed = _archive_unittest()
    core = _expected("shipped")["module_core.json"]["images"]
    rejected = sum(1 for e in core.values() if e["status"] == "rejected")
    expect = {
        "ok": run == passed and run > 0, "package": PACKAGE, "version": wanted, "archive": "/app/out/package.zip",
        "tests_run": run, "tests_passed": passed, "ci_commands": _ci_commands(),
        "reports": ["/app/out/" + doc for doc in DOCUMENTS], "images_total": len(core),
        "images_recovered": len(core) - rejected, "images_rejected": rejected,
    }
    _same("selftest.json", expect, {key: report.get(key) for key in expect})


def _check_shipped(doc):
    _same("/app/out/" + doc, _expected("shipped")[doc], _json_artifact(doc))


def _check_book(name, doc):
    _same("%s of the %s book" % (doc, name), _expected(name)[doc], _delivered(name)[doc])


def _check_timing():
    done, elapsed, _out = _run_package("max")
    assert done.returncode == 0, "package exited %s on the max book" % done.returncode
    assert elapsed <= TIME_LIMIT, "max book took %.1f s" % elapsed


def _check_missing_input():
    done, _elapsed, out = _run_package("missing")
    gone = Rng(BOOK_SEED).choice(sorted(BOOK_FILES))
    assert done.returncode != 0, "package exited 0 with %s missing" % gone
    assert gone in done.stderr, "stderr does not name %s: %r" % (gone, done.stderr.strip()[-300:])
    written = sorted(p.name for p in out.glob("*.json")) if out.is_dir() else []
    assert not written, "package wrote %s with an input missing" % written


def _tree_digest(root):
    digest = hashlib.sha256()
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def _check_rerun_identical():
    before = _tree_digest(_book_dir("restart"))
    first = _delivered("restart")
    second = _delivered("restart", attempt=2)
    for doc in DOCUMENTS:
        _same("second run %s" % doc, first[doc], second[doc])
    assert _tree_digest(_book_dir("restart")) == before, "package changed its input book"


def _holds(check, *args):
    try:
        check(*args)
    except Exception as exc:
        print("%s: %s" % (getattr(check, "__name__", check), exc), file=sys.stderr)
        return False
    return True


def _fires(probe):
    try:
        return bool(probe())
    except Exception as exc:
        print("%s: %s" % (getattr(probe, "__name__", probe), exc), file=sys.stderr)
        return False


def _holds_book_ids():
    shipped_ids = {img["id"] for img in _book("shipped")["images"]}
    root = _extract_archive()
    for path in sorted((root / "src").rglob("*")):
        if path.is_file():
            text = path.read_bytes().decode("utf-8", "replace")
            for iid in shipped_ids:
                if re.search(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(iid), text):
                    return True
    hidden = set(_expected("dense")["module_core.json"]["images"])
    got = set(_delivered("dense")["module_core.json"].get("images", {}))
    return bool(got & shipped_ids) and got != hidden


def _shipped_tests_dropped():
    shipped = ast.parse(_shipped_project()["tests/test_smoke.py"].decode("utf-8"))
    wanted = {n.name for n in ast.walk(shipped) if isinstance(n, ast.FunctionDef) and n.name.startswith("test")}
    members = dict((info.filename, data) for info, data in _archive_members())
    if "tests/test_smoke.py" not in members:
        return True
    text = members["tests/test_smoke.py"].decode("utf-8", "replace")
    tree = ast.parse(text)
    have = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    if wanted - have:
        return True
    return bool(re.search(r"\b(skip|skipIf|skipUnless|skipTest|SkipTest|expectedFailure)\b", text))


# ---------------------------------------------------------------- criteria

@criterion(description="The seven deliverables exist under /app/out and every JSON one parses.")
def artifacts_present(workspace: Path) -> bool:
    return _holds(_check_artifacts)


@criterion(description="package.zip holds exactly the listed members plus added package modules, stored with the stated timestamp.")
def archive_layout(workspace: Path) -> bool:
    return _holds(_check_archive_layout)


@criterion(description="The archived pyproject.toml and pagerecover.__version__ carry the required name, version, Python floor, no dependencies and the src layout.")
def package_metadata(workspace: Path) -> bool:
    return _holds(_check_package_metadata)


@criterion(description="build_report.json carries the stated values and lists exactly the package modules the repair changed or created.")
def build_report_values(workspace: Path) -> bool:
    return _holds(_check_build_report)


@criterion(description="selftest.json reports the archive's real unittest counts, the CI commands unquoted, the report paths and the shipped book's image counts.")
def selftest_truthful(workspace: Path) -> bool:
    return _holds(_check_selftest)


@criterion(description="/app/out/module_core.json equals the recovered page images of the shipped book in full.")
def shipped_core(workspace: Path) -> bool:
    return _holds(_check_shipped, "module_core.json")


@criterion(description="/app/out/module_metrics.json equals the recovery figures of the shipped book in full.")
def shipped_metrics(workspace: Path) -> bool:
    return _holds(_check_shipped, "module_metrics.json")


@criterion(description="/app/out/dependency_resolution.json equals the losers and appended records of the shipped book in full.")
def shipped_appended(workspace: Path) -> bool:
    return _holds(_check_shipped, "dependency_resolution.json")


@criterion(description="/app/out/summary.json equals the digests, client totals and audits of the shipped book in full.")
def shipped_summary(workspace: Path) -> bool:
    return _holds(_check_shipped, "summary.json")


@criterion(description="On a fresh book of dense crash images the archived package writes module_core.json exactly.")
def dense_core(workspace: Path) -> bool:
    return _holds(_check_book, "dense", "module_core.json")


@criterion(description="On a fresh book of dense crash images the archived package writes module_metrics.json exactly.")
def dense_metrics(workspace: Path) -> bool:
    return _holds(_check_book, "dense", "module_metrics.json")


@criterion(description="On a fresh book of dense crash images the archived package writes dependency_resolution.json exactly.")
def dense_appended(workspace: Path) -> bool:
    return _holds(_check_book, "dense", "dependency_resolution.json")


@criterion(description="On a fresh book of dense crash images the archived package writes summary.json exactly.")
def dense_summary(workspace: Path) -> bool:
    return _holds(_check_book, "dense", "summary.json")


@criterion(description="On a fresh book of images left by interrupted restarts the archived package writes module_core.json exactly.")
def restart_core(workspace: Path) -> bool:
    return _holds(_check_book, "restart", "module_core.json")


@criterion(description="On a fresh book of images left by interrupted restarts the archived package writes module_metrics.json exactly.")
def restart_metrics(workspace: Path) -> bool:
    return _holds(_check_book, "restart", "module_metrics.json")


@criterion(description="On a fresh book of images left by interrupted restarts the archived package writes dependency_resolution.json exactly.")
def restart_appended(workspace: Path) -> bool:
    return _holds(_check_book, "restart", "dependency_resolution.json")


@criterion(description="On a fresh book of images left by interrupted restarts the archived package writes summary.json exactly.")
def restart_summary(workspace: Path) -> bool:
    return _holds(_check_book, "restart", "summary.json")


@criterion(description="On a fresh book of images at the stated size limits the archived package writes module_core.json exactly.")
def max_core(workspace: Path) -> bool:
    return _holds(_check_book, "max", "module_core.json")


@criterion(description="On a fresh book of images at the stated size limits the archived package writes summary.json exactly.")
def max_summary(workspace: Path) -> bool:
    return _holds(_check_book, "max", "summary.json")


@criterion(description="The archived package recovers the book at the stated size limits within 60 seconds.")
def max_within_limit(workspace: Path) -> bool:
    return _holds(_check_timing)


@criterion(description="On a fresh book with defective images, including images with two defects, module_core.json carries the stated rejection codes and the other images exactly.")
def rejection_core(workspace: Path) -> bool:
    return _holds(_check_book, "rejection", "module_core.json")


@criterion(description="On a fresh book under a relocated path with spaces, run from a foreign directory, module_core.json is exact.")
def relocated_core(workspace: Path) -> bool:
    return _holds(_check_book, "relocated", "module_core.json")


@criterion(description="On a copy of the dense book whose page values and deltas were altered, summary.json follows the altered data exactly.")
def scaled_summary(workspace: Path) -> bool:
    return _holds(_check_book, "scaled", "summary.json")


@criterion(description="With one of the six inputs deleted the package exits nonzero, names that file on stderr and writes no document.")
def missing_input_rejected(workspace: Path) -> bool:
    return _holds(_check_missing_input)


@criterion(description="Running the package twice on the same book gives the same documents and leaves the book unchanged.")
def rerun_identical(workspace: Path) -> bool:
    return _holds(_check_rerun_identical)


@criterion(description="The archived package holds an image id of the shipped book or replays shipped figures for another book.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _fires(_holds_book_ids)


@criterion(description="The archive's tests/test_smoke.py drops or skips a test of the shipped one.")
def negative_shipped_tests_dropped(workspace: Path) -> bool:
    return _fires(_shipped_tests_dropped)


criteria.artifacts_present(weight=1)
criteria.archive_layout(weight=3)
criteria.package_metadata(weight=3)
criteria.build_report_values(weight=1)
criteria.selftest_truthful(weight=3)
criteria.shipped_core(weight=3)
criteria.shipped_metrics(weight=3)
criteria.shipped_appended(weight=3)
criteria.shipped_summary(weight=3)
criteria.dense_core(weight=5)
criteria.dense_metrics(weight=5)
criteria.dense_appended(weight=5)
criteria.dense_summary(weight=5)
criteria.restart_core(weight=5)
criteria.restart_metrics(weight=5)
criteria.restart_appended(weight=5)
criteria.restart_summary(weight=5)
criteria.max_core(weight=5)
criteria.max_summary(weight=3)
criteria.max_within_limit(weight=3)
criteria.rejection_core(weight=5)
criteria.relocated_core(weight=5)
criteria.scaled_summary(weight=5)
criteria.missing_input_rejected(weight=3)
criteria.rerun_identical(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_shipped_tests_dropped(weight=-3)
