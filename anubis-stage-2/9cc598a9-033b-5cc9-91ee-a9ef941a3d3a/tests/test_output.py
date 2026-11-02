"""Verifier for 9cc598a9-033b-5cc9-91ee-a9ef941a3d3a.

The first half is the deterministic feed generator (writer side): it regenerates the hidden-tier feed from the eval_seed of the embedded metadata at grade time with the rules the feed documents. The second half holds the rewardkit checks and the embedded expectations.
"""

# ------------------------------------------------------------ restore feed generator (writer side)
# Deterministic generator of a backup-restore feed: a seeded file-share history, the backup sets taken of it,
# the catalog entries those sets recorded and every register, log, notice and document the feed carries.
# Everything a reader needs to undo the renderings below is written into the feed's own documents.

import base64 as _b64
import datetime as dt
import hashlib
import io
import json
import math
import sqlite3
import unicodedata
import zipfile
import zlib
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from xml.sax.saxutils import escape as _xesc
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc


class Rng:
    """xorshift64* - stable across Python versions and platforms."""

    __slots__ = ("state",)

    def __init__(self, seed: int) -> None:
        self.state = (seed & 0xFFFFFFFFFFFFFFFF) or 0x9E3779B97F4A7C15
        for _ in range(4):
            self.next()

    def next(self) -> int:
        x = self.state
        x ^= x >> 12
        x ^= (x << 25) & 0xFFFFFFFFFFFFFFFF
        x ^= x >> 27
        self.state = x
        return (x * 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def randint(self, lo: int, hi: int) -> int:
        return lo + self.next() % (hi - lo + 1)

    def random(self) -> float:
        return (self.next() >> 11) / float(1 << 53)

    def chance(self, p: float) -> bool:
        return self.random() < p

    def choice(self, seq):
        return seq[self.next() % len(seq)]

    def shuffle(self, items: list) -> None:
        for i in range(len(items) - 1, 0, -1):
            j = self.next() % (i + 1)
            items[i], items[j] = items[j], items[i]

    def sample(self, seq, k: int) -> list:
        pool = list(seq)
        self.shuffle(pool)
        return pool[:k]

    def hexstr(self, n: int) -> str:
        out = ""
        while len(out) < n:
            out += f"{self.next():016x}"
        return out[:n]

    def fork(self, tag: str) -> "Rng":
        h = 1469598103934665603
        for ch in tag.encode():
            h = ((h ^ ch) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
        return Rng(self.next() ^ h)


def iso_z(t: dt.datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def floor_s(t: dt.datetime) -> dt.datetime:
    return t.replace(microsecond=0)


def local_wall(t: dt.datetime, tz: str) -> dt.datetime:
    return t.astimezone(ZoneInfo(tz)).replace(tzinfo=None)


def from_wall(wall: dt.datetime, tz: str, fold: int = 0) -> dt.datetime:
    return wall.replace(tzinfo=ZoneInfo(tz), fold=fold).astimezone(UTC)


def dst_end(year: int, tz: str) -> dt.date:
    """Local date on which the zone falls back from summer time in that year."""
    z = ZoneInfo(tz)
    d = dt.date(year, 9, 1)
    prev = dt.datetime(d.year, d.month, d.day, 12, tzinfo=z).utcoffset()
    while d.year == year:
        d += dt.timedelta(days=1)
        off = dt.datetime(d.year, d.month, d.day, 12, tzinfo=z).utcoffset()
        if off < prev:
            return d
        prev = off
    raise ValueError(tz)


# --------------------------------------------------------------------------- parameters
# Two tiers share every rule; they differ in share, site, dates, people and the random draws.

TIER_BASE = {
    "visible": {"share": "FS-02", "host": "FS02", "unc": "corp-fs02", "site_tz": "Europe/Berlin",
                "array": "ARR-FRA-02", "year": 2026, "scale": 1.0, "noise": 1.0, "doc_rows": 5000,
                "srv_old": ("BKP-NYC02", "America/New_York"), "srv_new": ("BKP-BER01", "Europe/Berlin"),
                "srv_other": ("BKP-BOM03", "Asia/Kolkata"), "feed_no": 412},
    "eval": {"share": "FS-07", "host": "FS07", "unc": "corp-fs07", "site_tz": "America/New_York",
             "array": "ARR-EWR-05", "year": 2026, "scale": 0.075, "noise": 0.06, "doc_rows": 260,
             "srv_old": ("BKP-BER01", "Europe/Berlin"), "srv_new": ("BKP-NYC02", "America/New_York"),
             "srv_other": ("BKP-SIN04", "Asia/Singapore"), "feed_no": 588},
}

TOP_DIRS = ["Engineering", "Design", "Shared", "Finance", "Scratch", "Marketing", "Legal"]
SUB_DIRS = {
    "Engineering": ["Projects", "Specs", "Builds", "Firmware", "Test Reports", "Tools"],
    "Design": ["Concepts", "Renders", "Assets", "Brand", "Archive"],
    "Shared": ["Contracts", "Templates", "Minutes", "Handover", "Inbox"],
    "Finance": ["Ledgers", "Budgets", "Invoices"],
    "Scratch": ["tmp", "dumps", "exports"],
    "Marketing": ["Campaigns", "Press", "Events"],
    "Legal": ["Matters", "Disclosures"],
}
WORDS = ["alpha", "pump", "valve", "gearbox", "rotor", "chassis", "housing", "bracket", "sensor", "harness",
         "budget", "review", "summary", "minutes", "draft", "final", "offer", "invoice", "plan", "layout",
         "render", "sketch", "logo", "poster", "banner", "spec", "manual", "report", "notes", "export",
         "Müller", "Café", "Señal", "Größe", "naïve", "Ørsted", "Zürich", "Ångström", "设计", "試験", "Δelta",
         "O'Brien", "R&D", "Q3, 2026", "v2 (copy)", "50% scale", "#12", "[old]", "A+B", "rev.B"]
EXTS = [".docx", ".xlsx", ".pdf", ".dwg", ".step", ".png", ".jpg", ".txt", ".csv", ".zip", ".pptx", ".md",
        ".bin", ".hex", ".log", ".json"]
JUNK_NAMES = ["~$report.docx", "Thumbs.db", ".DS_Store", "build.tmp", "autosave.bak", "~$minutes.docx",
              "desktop.ini", "core.dump"]


def make_params(seed: int, tier: str) -> dict:
    b = dict(TIER_BASE[tier])
    rng = Rng(seed).fork("params-" + tier)
    tz = b["site_tz"]
    year = b["year"]
    fb = dst_end(year, tz)
    w0 = fb - dt.timedelta(days=24 + rng.randint(0, 2))
    share = b["share"]
    num = share.split("-")[1]
    clients = [
        {"code": f"C{rng.randint(1000, 1999)}", "host": b["host"], "os": "windows", "tz": tz, "fs": "NTFS",
         "roots": [f"D:\\Shares\\Projects{num}", f"\\\\?\\D:\\Shares\\Projects{num}", f"\\\\{b['unc']}\\projects"]},
        {"code": f"C{rng.randint(2000, 2999)}", "host": b["host"] + "-REP", "os": "linux", "tz": "UTC", "fs": "ext4",
         "roots": [f"/srv/samba/projects{num}"]},
        {"code": f"C{rng.randint(3000, 3999)}", "host": "MACSTAGE" + num, "os": "macos", "tz": tz, "fs": "APFS",
         "roots": [f"/Volumes/Projects{num}"]},
        {"code": f"C{rng.randint(4000, 4999)}", "host": "INGEST" + num, "os": "windows",
         "tz": rng.choice(["America/Chicago", "Asia/Kolkata", "America/Denver"]), "fs": "FAT32",
         "roots": [f"F:\\Projects{num}"]},
    ]
    includes = ["/Design", "/Shared/Contracts", "/Shared/Templates", "/Shared/Handover", "/Marketing/Press"]
    rng.shuffle(includes)
    includes = sorted(["/Engineering"] + includes[:3])
    p = {
        "tier": tier, "seed": seed, "share": share, "share_num": num, "site_tz": tz, "array": b["array"],
        "unc": b["unc"], "year": year, "fallback": fb.isoformat(), "w0": w0.isoformat(),
        "scale": b["scale"], "noise": b["noise"], "doc_rows": b["doc_rows"], "feed_no": b["feed_no"],
        "srv_old": list(b["srv_old"]), "srv_new": list(b["srv_new"]), "srv_other": list(b["srv_other"]),
        "clients": clients, "includes": includes,
        "job_old": f"PRJ-{share.replace('-', '')}-DAILY", "job_new": f"{b['srv_new'][0][4:7]}-PRJ{num}-NIGHTLY",
        "feed_id": f"RR-{year}-{b['feed_no']:04d}",
        "target_volume": f"VOL-{rng.randint(100, 899)}-{share.replace('-', '')}N",
        "cluster_small": rng.choice([4096, 8192]), "cluster_large": rng.choice([65536, 131072]),
        "large_threshold": rng.choice([1048576, 4194304]), "resident_max": rng.choice([700, 640, 720]),
        "lto_bad_gen": "LTO-6",
        "account_prefix": rng.choice(["ext", "con", "svc"]),
    }
    return p


# --------------------------------------------------------------------------- the file-share simulation


class Share:
    """Case-insensitive, case-preserving tree of one share. Keys are casefolded NFC paths."""

    def __init__(self) -> None:
        self.dirs: dict[str, str] = {"": ""}        # key -> display path ("" is the root)
        self.objs: dict[str, dict] = {}             # key -> {"path", "kind": file|link, "inode" | "target"}
        self.inodes: dict[int, dict] = {}           # inode -> version dict (shared by hard links)

    @staticmethod
    def key(path: str) -> str:
        return unicodedata.normalize("NFC", path).casefold()

    def parent(self, path: str) -> str:
        return path.rsplit("/", 1)[0]

    def members(self, inode: int) -> list[str]:
        return sorted(k for k, o in self.objs.items() if o["kind"] == "file" and o["inode"] == inode)

    def under(self, dkey: str) -> tuple[list[str], list[str]]:
        pre = dkey + "/"
        return ([k for k in self.dirs if k.startswith(pre)], [k for k in self.objs if k.startswith(pre)])

    def snapshot(self) -> dict:
        out = {}
        for k, o in self.objs.items():
            if o["kind"] == "file":
                out[k] = {"path": o["path"], "kind": "file", "inode": o["inode"], **self.inodes[o["inode"]]}
            else:
                out[k] = {"path": o["path"], "kind": "link", "target": o["target"], **o["meta"]}
        return {"objs": out, "dirs": dict(self.dirs)}


def _name(rng: Rng, ext: str | None = None) -> str:
    n = rng.randint(1, 3)
    parts = [rng.choice(WORDS) for _ in range(n)]
    sep = rng.choice([" ", "_", "-", " "])
    base = sep.join(parts)
    if rng.chance(0.35):
        base += f"{sep}{rng.randint(1, 240):03d}"
    return base + (ext if ext is not None else rng.choice(EXTS))


class World:
    """Ground truth: share history, backup sets and the canonical catalog entries."""

    def __init__(self, p: dict, rng: Rng) -> None:
        self.p = p
        self.rng = rng
        self.share = Share()
        self.inode_seq = 1000
        self.version_seq = 0
        self.container_seq = 0
        self.entry_seq = 0
        self.sets: list[dict] = []
        self.entries: dict[str, list[dict]] = {}     # sid -> canonical entries in seq order
        self.pending: list[dict] = []                 # events since the last set the software counts as base
        self.snapshots: dict[str, dict] = {}          # sid -> share snapshot at its capture
        self.versions: dict[str, dict] = {}           # version id -> version
        self.containers: dict[str, dict] = {}         # container id -> {"size", "created", "sid"}
        self.junk_paths = 0
        self.vid_container: dict[str, str] = {}

    # ---- versions -------------------------------------------------------------------------
    def new_version(self, when: dt.datetime, client: dict, kind: str = "edit") -> dict:
        r = self.rng
        self.version_seq += 1
        size = int(math.exp(6.5 + r.random() * 8.2))
        if r.chance(0.004):
            size = r.randint(30, 90) * 1_073_741_824 + r.randint(0, 999_999)
        if r.chance(0.03):
            size = r.randint(0, 760)
        age = dt.timedelta(seconds=r.randint(5, 4 * 3600)) if kind == "edit" else dt.timedelta(days=r.randint(30, 2000))
        mtime = when - age
        if r.chance(0.01):
            mtime = when + dt.timedelta(minutes=r.randint(1, 50))         # client clock ahead: still valid
        if client["fs"] == "FAT32":
            mtime = mtime.replace(microsecond=0)
            mtime -= dt.timedelta(seconds=local_wall(mtime, client["tz"]).second % 2)
        else:
            mtime = mtime.replace(microsecond=r.randint(0, 999_999))
        if client["os"] == "windows":
            mode = None
            attrs = r.choice(["A", "A", "A", "RA", "R", "AH", ""])
            owner = f"S-1-5-21-{self.p['dom']}-{r.choice(self.p['rids'])}"
        else:
            mode = r.choice([0o644, 0o644, 0o664, 0o600, 0o640, 0o755, 0o750, 0o4755, 0o2775, 0o1777, 0o6750])
            attrs = None
            owner = f"uid:{r.choice(self.p['uids'])}"
        if r.chance(0.01):
            owner = f"S-1-5-21-{self.p['legacy_dom']}-{r.choice(self.p['legacy_rids'])}"
        v = {"vid": f"V{self.version_seq:07d}", "sha": r.hexstr(64), "size": size, "mtime": mtime, "mode": mode,
             "attrs": attrs, "owner": owner, "client": client["code"], "container": None}
        self.versions[v["vid"]] = v
        return v

    # ---- events ---------------------------------------------------------------------------
    def ev(self, evk: str, when: dt.datetime, client: dict, **kw) -> None:
        self.pending.append({"ev": evk, "when": when, "client": client["code"], **kw})

    def mkdirs(self, path: str, when: dt.datetime, client: dict) -> None:
        parts = path.strip("/").split("/")
        cur = ""
        for comp in parts:
            cur = cur + "/" + comp
            k = Share.key(cur)
            if k not in self.share.dirs:
                self.share.dirs[k] = cur
                self.ev("mkdir", when, client, path=cur)
            else:
                cur = self.share.dirs[k]

    def create_file(self, path: str, when: dt.datetime, client: dict, kind: str = "edit") -> str | None:
        k = Share.key(path)
        if k in self.share.objs or k in self.share.dirs:
            return None
        self.mkdirs(self.share.parent(path), when, client)
        path = self.share.dirs[Share.key(self.share.parent(path))] + "/" + path.rsplit("/", 1)[1]
        self.inode_seq += self.rng.randint(1, 9)
        v = self.new_version(when, client, kind)
        v["file_id"] = self.inode_seq
        self.share.inodes[self.inode_seq] = v
        self.share.objs[k] = {"path": path, "kind": "file", "inode": self.inode_seq}
        self.ev("put", when, client, path=path, vid=v["vid"], create=True)
        return k

    def modify(self, k: str, when: dt.datetime, client: dict) -> None:
        o = self.share.objs[k]
        old = self.share.inodes[o["inode"]]
        v = self.new_version(when, client)
        v["file_id"] = old["file_id"]
        self.share.inodes[o["inode"]] = v
        for m in self.share.members(o["inode"]):
            self.ev("put", when, client, path=self.share.objs[m]["path"], vid=v["vid"], create=False)

    def delete(self, k: str, when: dt.datetime, client: dict) -> None:
        o = self.share.objs.pop(k)
        self.ev("del", when, client, path=o["path"], kind=o["kind"])

    def rmdir(self, dk: str, when: dt.datetime, client: dict) -> None:
        path = self.share.dirs[dk]
        sub_d, sub_o = self.share.under(dk)
        for k in sub_o:
            self.share.objs.pop(k)
        for k in sub_d:
            self.share.dirs.pop(k)
        self.share.dirs.pop(dk)
        self.ev("del", when, client, path=path, kind="dir")

    def rename(self, k: str, new_path: str, when: dt.datetime, client: dict) -> bool:
        nk = Share.key(new_path)
        if (nk in self.share.objs or nk in self.share.dirs) and nk != k:
            return False
        o = self.share.objs.pop(k)
        self.mkdirs(self.share.parent(new_path), when, client)
        new_path = self.share.dirs[Share.key(self.share.parent(new_path))] + "/" + new_path.rsplit("/", 1)[1]
        old = o["path"]
        o["path"] = new_path
        self.share.objs[nk] = o
        self.ev("ren", when, client, path=old, new=new_path, kind=o["kind"])
        return True

    def rename_dir(self, dk: str, new_path: str, when: dt.datetime, client: dict) -> bool:
        nk = Share.key(new_path)
        if nk in self.share.dirs or nk in self.share.objs or nk.startswith(dk + "/"):
            return False
        if Share.key(self.share.parent(new_path)) not in self.share.dirs:
            return False
        new_path = self.share.dirs[Share.key(self.share.parent(new_path))] + "/" + new_path.rsplit("/", 1)[1]
        old = self.share.dirs[dk]
        sub_d, sub_o = self.share.under(dk)
        moves_d = {k: new_path + self.share.dirs[k][len(old):] for k in sub_d}
        moves_o = {k: new_path + self.share.objs[k]["path"][len(old):] for k in sub_o}
        for k in sub_d:
            self.share.dirs.pop(k)
        self.share.dirs.pop(dk)
        self.share.dirs[nk] = new_path
        for p_ in moves_d.values():
            self.share.dirs[Share.key(p_)] = p_
        objs = {k: self.share.objs.pop(k) for k in sub_o}
        for k, o in objs.items():
            o["path"] = moves_o[k]
            self.share.objs[Share.key(o["path"])] = o
        self.ev("ren", when, client, path=old, new=new_path, kind="dir")
        return True

    def hardlink(self, k: str, new_path: str, when: dt.datetime, client: dict) -> None:
        nk = Share.key(new_path)
        if nk in self.share.objs or nk in self.share.dirs:
            return
        o = self.share.objs[k]
        if o["kind"] != "file":
            return
        self.mkdirs(self.share.parent(new_path), when, client)
        new_path = self.share.dirs[Share.key(self.share.parent(new_path))] + "/" + new_path.rsplit("/", 1)[1]
        self.share.objs[nk] = {"path": new_path, "kind": "file", "inode": o["inode"]}
        self.ev("link", when, client, path=new_path, target=o["path"])

    def symlink(self, path: str, target: str, when: dt.datetime, client: dict) -> None:
        nk = Share.key(path)
        if nk in self.share.objs or nk in self.share.dirs:
            return
        self.mkdirs(self.share.parent(path), when, client)
        path = self.share.dirs[Share.key(self.share.parent(path))] + "/" + path.rsplit("/", 1)[1]
        meta = self.new_version(when, client)
        meta = {"mtime": meta["mtime"], "mode": meta["mode"] and 0o777, "attrs": meta["attrs"],
                "owner": meta["owner"], "client": client["code"]}
        self.share.objs[nk] = {"path": path, "kind": "link", "target": target, "meta": meta}
        self.ev("sym", when, client, path=path, target=target, meta=meta)


# --------------------------------------------------------------------------- timeline of backup sets


def build_timeline(p: dict, rng: Rng) -> list[dict]:
    """The share's backup sets in capture order. Each spec: day, type, job status and the facts other
    sources carry about it (status override, maintenance window, log gap, ambiguous wall time)."""
    fb = dt.date.fromisoformat(p["fallback"])
    w0 = dt.date.fromisoformat(p["w0"])
    specs: list[dict] = []

    def add(day, typ, status="COMPLETED", **kw):
        specs.append({"day": day, "type": typ, "job_status": status, **kw})

    d = w0
    add(d, "FULL")
    k1 = rng.randint(6, 7)
    fail_at, cancel_at = rng.sample(range(1, k1), 2)
    for i in range(k1):
        d += dt.timedelta(days=1)
        add(d, "INCR", "FAILED" if i == fail_at else "CANCELLED" if i == cancel_at else "COMPLETED")
    d += dt.timedelta(days=1)
    add(d, "DIFF")
    k2 = rng.randint(5, 6)
    part_at = rng.randint(1, k2 - 2)
    for i in range(k2):
        d += dt.timedelta(days=1)
        add(d, "INCR", override="PARTIAL" if i == part_at else None)
    consolidated = len(specs) - 1
    d += dt.timedelta(days=1)
    add(d, "SYNTH", consolidates=consolidated, synth_hour=3, era=2)
    add(d, "INCR", era=2)
    seg2 = []
    while d < fb - dt.timedelta(days=2):
        d += dt.timedelta(days=1)
        add(d, "INCR", era=2)
        seg2.append(len(specs) - 1)
    crash_old = rng.choice(seg2[:-1])
    specs[crash_old]["crash"] = "planned"
    specs[rng.choice([i for i in seg2 if i != crash_old])]["log_gap"] = True
    add(fb - dt.timedelta(days=1), "DIFF", era=2)
    add(fb, "INCR", era=2, ambiguous=True)
    crash_off = rng.choice([1, 2])
    for off in range(1, 6):
        day = fb + dt.timedelta(days=off)
        if off == crash_off:
            add(day, "INCR", era=2, crash="actual")
        elif off == crash_off + 1:
            add(day, "INCR", "FAILED", era=2)
        elif off == 5:
            add(day, "INCR", era=2, at_rp=True)
        else:
            add(day, "INCR", era=2)
    add(fb + dt.timedelta(days=5), "INCR", era=2, late=True)
    add(fb + dt.timedelta(days=6), "FULL", era=2)
    for s in specs:
        s.setdefault("era", 1)
        s.setdefault("override", None)
        s.setdefault("crash", None)
    return specs


def snapshot_wall(p: dict, spec: dict, rng: Rng) -> tuple[dt.datetime, int]:
    """Local wall time (site tz) of a set's snapshot and the fold that pins it."""
    day = spec["day"]
    if spec.get("ambiguous"):
        z = ZoneInfo(p["site_tz"])
        for h in range(0, 5):
            wall = dt.datetime(day.year, day.month, day.day, h, 30)
            a = wall.replace(tzinfo=z, fold=0).utcoffset()
            b = wall.replace(tzinfo=z, fold=1).utcoffset()
            if a != b:
                return wall.replace(minute=rng.randint(5, 55), second=rng.randint(0, 59)), 0
        raise ValueError("no repeated hour")
    if spec["type"] == "SYNTH":
        return dt.datetime(day.year, day.month, day.day, 3, rng.randint(0, 30), rng.randint(0, 59)), 0
    if spec.get("at_rp"):
        return dt.datetime(day.year, day.month, day.day, 1, 30, 0), 0
    if spec.get("late"):
        return dt.datetime(day.year, day.month, day.day, 23, rng.randint(0, 40), rng.randint(0, 59)), 0
    if spec.get("log_gap"):
        return dt.datetime(day.year, day.month, day.day, 22, rng.randint(0, 59), 0), 0
    return dt.datetime(day.year, day.month, day.day, rng.randint(21, 23), rng.randint(0, 59), rng.randint(0, 59)), 0


# --------------------------------------------------------------------------- catalog entries


def vary_case(rng: Rng, path: str, keep_last: bool) -> str:
    if not rng.chance(0.18):
        return path
    comps = path.split("/")
    idx = list(range(1, len(comps) - (1 if keep_last else 0)))
    if not idx:
        return path
    i = rng.choice(idx)
    c = comps[i]
    comps[i] = rng.choice([c.upper(), c.lower(), c.swapcase()])
    out = "/".join(comps)
    return out if Share.key(out) == Share.key(path) else path


def _depth(path: str) -> int:
    return path.count("/")


class EntryBuilder:
    def __init__(self, world: "World", sid: str, client: dict) -> None:
        self.w = world
        self.sid = sid
        self.client = client
        self.out: list[dict] = []

    def add(self, etype: str, **kw) -> dict:
        self.w.entry_seq += self.w.rng.randint(1, 3)
        e = {"eid": f"E-{self.w.entry_seq:07d}", "sid": self.sid, "seq": len(self.out) + 1, "etype": etype,
             "client": kw.pop("client", self.client["code"]), "committed": "Y", **kw}
        self.out.append(e)
        return e


def events_to_entries(w: "World", b: EntryBuilder, events: list[dict]) -> None:
    r = w.rng
    for ev in events:
        k = ev["ev"]
        cl = ev["client"]
        if k == "mkdir":
            b.add("D", path=ev["path"], client=cl)
        elif k == "put":
            path = vary_case(r, ev["path"], keep_last=ev["create"])
            e = b.add("F", path=path, vid=ev["vid"], client=w.versions[ev["vid"]]["client"], mod=not ev["create"])
            e["_ev"] = ev
        elif k == "del":
            b.add("W", path=vary_case(r, ev["path"], keep_last=False), kind=ev["kind"], client=cl)
        elif k == "ren":
            b.add("R", path=vary_case(r, ev["path"], keep_last=False), new=vary_case(r, ev["new"], keep_last=True),
                  kind=ev["kind"], client=cl)
        elif k == "link":
            b.add("H", path=vary_case(r, ev["path"], keep_last=True), target=vary_case(r, ev["target"], False), client=cl)
        elif k == "sym":
            b.add("L", path=vary_case(r, ev["path"], keep_last=True), target=ev["target"], meta=ev["meta"],
                  client=ev["meta"]["client"])


def diff_entries(w: "World", b: EntryBuilder, base: dict, cur: dict) -> None:
    r = w.rng
    bd, bo = base.get("dirs", {}), base.get("objs", {})
    cd, co = cur["dirs"], cur["objs"]
    removed_dirs = sorted((k for k, v in bd.items() if k and cd.get(k) != v), key=lambda k: (_depth(k), k))
    top_removed: list[str] = []
    for k in removed_dirs:
        if not any(k.startswith(t + "/") for t in top_removed):
            top_removed.append(k)

    def wiped(k: str) -> bool:
        return any(k.startswith(t + "/") or k == t for t in top_removed)

    for k in top_removed:
        b.add("W", path=vary_case(r, bd[k], False), kind="dir")
    for k in sorted(bo):
        o = bo[k]
        if wiped(k):
            continue
        c = co.get(k)
        if c is None or c["path"] != o["path"] or c["kind"] != o["kind"]:
            b.add("W", path=vary_case(r, o["path"], False), kind=o["kind"])
    for k in sorted((k for k in cd if k and (bd.get(k) != cd[k] or wiped(k))), key=lambda k: (_depth(k), k)):
        b.add("D", path=cd[k])
    emitted: dict[int, str] = {}
    by_inode: dict[int, list[str]] = {}
    for mk in sorted(bo):
        if bo[mk]["kind"] == "file":
            by_inode.setdefault(bo[mk]["inode"], []).append(mk)
    for k in sorted(co):
        c = co[k]
        o = bo.get(k)
        fresh = o is None or wiped(k) or o["path"] != c["path"] or o["kind"] != c["kind"]
        if c["kind"] == "link":
            if fresh or o.get("target") != c["target"]:
                b.add("L", path=c["path"], target=c["target"],
                      meta={x: c[x] for x in ("mtime", "mode", "attrs", "owner", "client")}, client=c["client"])
            continue
        if not fresh and o["vid"] == c["vid"]:
            continue
        ino = c["inode"]
        if ino in emitted:
            b.add("H", path=vary_case(r, c["path"], True), target=vary_case(r, emitted[ino], False))
            continue
        anchor = None
        for mk in by_inode.get(ino, []):
            mo = bo[mk]
            if (mo["vid"] == c["vid"] and not wiped(mk)
                    and co.get(mk, {}).get("path") == mo["path"] and co[mk].get("vid") == c["vid"]):
                anchor = mo["path"]
                break
        if anchor is not None and anchor != c["path"]:
            b.add("H", path=vary_case(r, c["path"], True), target=vary_case(r, anchor, False))
        else:
            path = c["path"] if fresh else vary_case(r, c["path"], False)
            b.add("F", path=path, vid=c["vid"], client=w.versions[c["vid"]]["client"], mod=not fresh)
        emitted[ino] = c["path"]



def _rand_dir(w: "World") -> str:
    keys = [k for k in w.share.dirs if k]
    return w.share.dirs[w.rng.choice(keys)]


def _rel(from_dir: str, to_path: str) -> str:
    a = [c for c in from_dir.split("/") if c]
    b = [c for c in to_path.split("/") if c]
    i = 0
    while i < len(a) and i < len(b) - 1 and Share.key(a[i]) == Share.key(b[i]):
        i += 1
    return "/".join([".."] * (len(a) - i) + b[i:])


def world_people(p: dict, rng: Rng) -> None:
    p["dom"] = f"{rng.randint(1000000000, 3999999999)}-{rng.randint(1000000000, 3999999999)}-{rng.randint(100000000, 999999999)}"
    p["legacy_dom"] = f"{rng.randint(1000000000, 3999999999)}-{rng.randint(1000000000, 3999999999)}-{rng.randint(100000000, 999999999)}"
    p["rids"] = sorted(rng.sample(range(1100, 2400), 70))
    p["legacy_rids"] = sorted(rng.sample(range(500, 1100), 8))
    p["uids"] = sorted(rng.sample(range(1001, 1400), 40))


def run_world(p: dict, seed: int) -> World:
    rng = Rng(seed).fork("world-" + p["tier"])
    world_people(p, rng)
    w = World(p, rng)
    cl = p["clients"]
    scale = p["scale"]
    specs = build_timeline(p, rng.fork("timeline"))
    tz = p["site_tz"]

    # job wall times and snapshot instants
    for s in specs:
        wall, fold = snapshot_wall(p, s, rng)
        s["job_wall"] = wall
        s["job_at"] = from_wall(wall, tz, fold)
    for s in specs:
        if s["type"] == "SYNTH":
            s["snap"] = specs[s["consolidates"]]["job_at"]
            s["queued"] = s["job_at"] - dt.timedelta(minutes=rng.randint(1, 4))
            s["ended"] = s["job_at"] + dt.timedelta(minutes=rng.randint(90, 200))
        else:
            s["snap"] = s["job_at"]
            s["queued"] = s["snap"] - dt.timedelta(minutes=rng.randint(2, 9), seconds=rng.randint(0, 59))
            dur = {"FULL": (180, 360), "DIFF": (60, 140), "INCR": (8, 70)}[s["type"]]
            s["ended"] = s["snap"] + dt.timedelta(minutes=rng.randint(*dur), seconds=rng.randint(0, 59))
        s["server"] = p["srv_old"][0] if s["era"] == 1 else p["srv_new"][0]
        s["job_name"] = p["job_old"] if s["era"] == 1 else p["job_new"]
    rp = next(s for s in specs if s.get("at_rp"))["snap"]
    p["rp_utc"] = iso_z(rp)
    p["request_date"] = (local_wall(rp, tz).date() + dt.timedelta(days=4)).isoformat()
    w.specs = specs
    w.rp = rp

    # initial share population, before the first set (not part of any pending history)
    t0 = from_wall(dt.datetime.combine(dt.date.fromisoformat(p["w0"]), dt.time(8, 0)), tz) - dt.timedelta(days=3)
    for top in TOP_DIRS:
        for sub in SUB_DIRS[top]:
            w.mkdirs(f"/{top}/{sub}", t0, cl[0])
    n0 = max(120, int(4300 * scale))
    proj = [f"/Engineering/Projects/P-{rng.randint(1000, 9999)} {rng.choice(WORDS)}" for _ in range(max(6, int(40 * scale)))]
    for pr in proj:
        for sub in ["CAD", "Docs", "Build", "Review"]:
            w.mkdirs(f"{pr}/{sub}", t0, cl[0])
    while len(w.share.objs) < n0:
        d = _rand_dir(w)
        c = cl[0] if not rng.chance(0.06) else rng.choice(cl[1:])
        name = _name(rng) if not rng.chance(0.03) else rng.choice(JUNK_NAMES)
        w.create_file(f"{d}/{name}", t0, c, kind="import")
    for _ in range(max(3, int(30 * scale))):
        keys = [k for k, o in w.share.objs.items() if o["kind"] == "file"]
        k = rng.choice(keys)
        w.hardlink(k, f"{_rand_dir(w)}/{_name(rng)}", t0, cl[0])
    w.pending.clear()

    w0 = dt.date.fromisoformat(p["w0"])
    p["set_base"] = 41000 + rng.randint(0, 900) if p["tier"] == "visible" else 20000 + rng.randint(0, 900)
    used: set[int] = set()
    for s in sorted(specs, key=lambda s: s["queued"]):
        di = (local_wall(s["queued"], tz).date() - w0).days + 3
        while True:
            n = p["set_base"] + di * 900 + rng.randint(0, 899)
            if n not in used and all(n > u for u in used if u < p["set_base"] + di * 900 + 900):
                break
        used.add(n)
        s["sid"] = f"BS-{n:05d}"
    last = t0
    order = sorted(range(len(specs)), key=lambda i: (specs[i]["job_at"], i))
    base_sid = None
    for i in order:
        s = specs[i]
        if s["type"] != "SYNTH":
            simulate(w, last, s["snap"], s["era"])
            last = s["snap"]
        take_set(w, s, specs, base_sid)
        if s["type"] in ("FULL", "SYNTH") and s["job_status"] == "COMPLETED":
            base_sid = s["sid"]
    return w


def _pick_client(w: World, era: int) -> dict:
    cl = w.p["clients"]
    x = w.rng.random()
    if era == 1:
        return cl[0] if x < 0.84 else cl[2] if x < 0.95 else cl[3]
    return cl[1] if x < 0.78 else cl[2] if x < 0.9 else cl[0] if x < 0.96 else cl[3]


def simulate(w: World, t_from: dt.datetime, t_to: dt.datetime, era: int) -> None:
    r = w.rng
    hours = max(1.0, (t_to - t_from).total_seconds() / 3600)
    n = int(r.randint(140, 200) * w.p["scale"] * hours / 24) + 3
    times = sorted(t_from + dt.timedelta(seconds=r.randint(1, int((t_to - t_from).total_seconds()) - 1)) for _ in range(n))
    for when in times:
        c = _pick_client(w, era)
        files = [k for k, o in w.share.objs.items() if o["kind"] == "file"]
        x = r.random()
        if x < 0.44 and files:
            w.modify(r.choice(files), when, c)
        elif x < 0.66:
            name = _name(r) if not r.chance(0.12) else r.choice(JUNK_NAMES).replace(".", f"{r.randint(1, 99)}.", 1)
            d = _rand_dir(w)
            if r.chance(0.08):
                d = f"{d}/{r.choice(WORDS)} {r.randint(1, 99)}"
            w.create_file(f"{d}/{name}", when, c)
        elif x < 0.73 and files:
            w.delete(r.choice(files), when, c)
        elif x < 0.79 and files:
            k = r.choice(files)
            path = w.share.objs[k]["path"]
            last = path.rsplit("/", 1)[1]
            if r.chance(0.4):
                new_last = last.upper() if last != last.upper() else last.lower()
            else:
                stem, dot, ext = last.rpartition(".")
                new_last = (stem or last) + f" ({r.choice(['old', 'v2', 'final', 'copy'])})" + (dot + ext if stem else "")
            w.rename(k, path.rsplit("/", 1)[0] + "/" + new_last, when, c)
        elif x < 0.83 and files:
            k = r.choice(files)
            w.rename(k, _rand_dir(w) + "/" + w.share.objs[k]["path"].rsplit("/", 1)[1], when, c)
        elif x < 0.845:
            dks = [k for k in w.share.dirs if k.count("/") >= 3]
            if dks:
                dk = r.choice(dks)
                path = w.share.dirs[dk]
                w.rename_dir(dk, path.rsplit("/", 1)[0] + "/" + r.choice(WORDS) + f" {r.randint(1, 50)}", when, c)
        elif x < 0.852:
            dks = [k for k in w.share.dirs if k.count("/") >= 4]
            if dks:
                w.rmdir(r.choice(dks), when, c)
        elif x < 0.87 and files:
            w.hardlink(r.choice(files), f"{_rand_dir(w)}/{_name(r)}", when, c)
        elif x < 0.885 and files:
            d = _rand_dir(w)
            tgt = w.share.objs[r.choice(files)]["path"]
            form = r.random()
            if form < 0.55:
                raw = _rel(d, tgt)
            elif form < 0.75:
                raw = "/".join([".."] * (d.count("/") + r.randint(1, 3))) + "/etc/" + r.choice(["passwd", "shadow", "hosts"])
            else:
                raw = "@ROOT@" + tgt
            if c["os"] == "windows":
                raw = raw.replace("/", "\\")
            w.symlink(f"{d}/{r.choice(WORDS)} link{r.randint(1, 99)}", raw, when, c)
        elif files:
            w.modify(r.choice(files), when, c)


def _idx(items: list, obj) -> int:
    return next(i for i, x in enumerate(items) if x is obj)


def take_set(w: World, s: dict, specs: list[dict], base_sid: str | None) -> None:
    r = w.rng
    typ, sid = s["type"], s["sid"]
    primary = w.p["clients"][0] if s["era"] == 1 else w.p["clients"][1]
    b = EntryBuilder(w, sid, primary)
    cur = w.share.snapshot()
    if typ == "FULL":
        diff_entries(w, b, {}, cur)
    elif typ == "SYNTH":
        cur = w.snapshots[specs[s["consolidates"]]["sid"]]
        diff_entries(w, b, {}, cur)
    elif typ == "DIFF":
        diff_entries(w, b, w.snapshots[base_sid], cur)
    else:
        events_to_entries(w, b, w.pending)
    entries = b.out
    status = s["job_status"]
    if status in ("FAILED", "CANCELLED"):
        entries = entries[: max(1, int(len(entries) * (0.35 + r.random() * 0.5)))]
    else:
        carry: list[dict] = []
        if s["override"] == "PARTIAL":
            last_touch: dict[str, int] = {}
            for i, e in enumerate(entries):
                for pth in (e.get("path"), e.get("new"), e.get("target")):
                    if pth and e["etype"] != "L":
                        last_touch[Share.key(pth)] = i
            cands = [i for i, e in enumerate(entries) if e["etype"] == "F" and e.get("mod")
                     and last_touch.get(Share.key(e["path"])) == i]
            for i in sorted(r.sample(cands, min(len(cands), max(2, len(cands) // 9)))):
                entries[i]["committed"] = "N"
                carry.append(entries[i]["_ev"])
        w.pending = carry
    # junk entries later voided by the catalog consistency job, and rejected paths
    if typ in ("INCR", "DIFF"):
        junk = []
        for _ in range(r.randint(1, 4) if typ == "INCR" else r.randint(3, 6)):
            d = _rand_dir(w) if w.share.dirs else ""
            v = w.new_version(s["snap"], primary)
            v["file_id"] = r.randint(900000, 999999)
            junk.append({"etype": "F", "path": f"{d}/~${r.hexstr(6)}.tmp", "vid": v["vid"], "client": primary["code"],
                         "junk": True})
        mods = [e for e in entries if e["etype"] == "F" and e.get("mod")]
        for e in r.sample(mods, min(len(mods), r.randint(0, 2))):
            v = dict(w.versions[e["vid"]])
            w.version_seq += 1
            v["vid"] = f"V{w.version_seq:07d}"
            v["sha"] = r.hexstr(64)
            v["size"] = v["size"] + r.randint(1, 4096)
            w.versions[v["vid"]] = v
            junk.append({"etype": "F", "path": e["path"], "vid": v["vid"], "client": e["client"], "junk": True,
                         "after": e})
        for j in junk:
            pos = _idx(entries, j.pop("after")) + 1 if "after" in j else r.randint(0, len(entries))
            j.update({"eid": None, "sid": sid, "committed": "Y"})
            entries.insert(pos, j)
        for j in junk:
            entries.insert(r.randint(_idx(entries, j) + 1, len(entries)), {"eid": None, "sid": sid, "etype": "X",
                                                                           "client": primary["code"], "committed": "Y", "voids": j})
        if typ == "INCR" and r.chance(0.45):
            for _ in range(r.randint(1, 2)):
                kind = r.choice(["unsafe", "outside"])
                entries.insert(r.randint(0, len(entries)), {"eid": None, "sid": sid, "etype": "F", "committed": "Y",
                                                             "client": primary["code"], "reject": kind,
                                                             "vid": w.new_version(s["snap"], primary)["vid"],
                                                             "path": "/" + r.choice(["Windows/System32", "etc", "Finance/Payroll", "Users/Public"]) + "/" + _name(r)})
    for i, e in enumerate(entries):
        e["seq"] = i + 1
        if e["eid"] is None:
            w.entry_seq += r.randint(1, 3)
            e["eid"] = f"E-{w.entry_seq:07d}"
    for e in entries:
        if e["etype"] == "X":
            e["voids"] = e["voids"]["eid"]
    # containers: synthetic fulls reference the containers their versions already live in
    chunk = None
    left = 0
    for e in entries:
        if e["etype"] != "F" or e.get("reject"):
            continue
        if typ == "SYNTH" and e["vid"] in w.vid_container:
            e["container"] = w.vid_container[e["vid"]]
            continue
        if left <= 0:
            w.container_seq += r.randint(1, 5)
            chunk = f"CT-{w.container_seq:07d}"
            w.containers[chunk] = {"sid": sid, "created": s["ended"], "size": 0, "members": 0}
            left = r.randint(25, 60)
        left -= 1
        e["container"] = chunk
        w.containers[chunk]["size"] += w.versions[e["vid"]]["size"]
        w.containers[chunk]["members"] += 1
    if status == "COMPLETED":
        for e in entries:
            if e["etype"] == "F" and e["committed"] == "Y" and not e.get("junk") and not e.get("reject"):
                w.vid_container[e["vid"]] = e["container"]
    for e in entries:
        e.pop("_ev", None)
        e.pop("mod", None)
    w.entries[sid] = entries
    w.snapshots[sid] = cur


# --------------------------------------------------------------------------- registers around the catalog

ARRAYS = ["ARR-FRA-01", "ARR-FRA-02", "ARR-FRA-03", "ARR-EWR-04", "ARR-EWR-05", "ARR-BOM-06", "ARR-SIN-07",
          "ARR-LHR-08", "ARR-DUB-09", "ARR-NRT-10"]
SITE_TZ = ["Europe/Berlin", "America/New_York", "Asia/Kolkata", "Asia/Singapore", "Europe/London",
           "America/Chicago", "Asia/Tokyo", "Europe/Dublin"]
VENDORS = ["Kestrel AV", "Norrland Security", "Tamarind Labs", "Bluefin Defense", "Corvid Systems"]


def target_rows(p: dict, rng: Rng, base: int = 5000) -> int:
    if p["tier"] == "visible":
        return base + rng.randint(40, 700)
    return rng.randint(110, 260)


def doc_rows(p: dict, rng: Rng) -> int:
    if p["tier"] == "visible":
        return p["doc_rows"] + rng.randint(20, 400)
    return p["doc_rows"] + rng.randint(0, 60)


def build_registers(w: World) -> dict:
    p = w.p
    r = w.rng.fork("registers")
    R: dict = {}
    tz = p["site_tz"]
    specs = w.specs
    rp = w.rp
    req = dt.date.fromisoformat(p["request_date"])
    req_end = from_wall(dt.datetime.combine(req, dt.time(23, 59, 59)), tz)
    R["req_end"] = req_end
    w0 = dt.date.fromisoformat(p["w0"])

    # ---- other shares, servers and their sets (noise that every share-scoped rule must filter out)
    shares = [p["share"]]
    while len(shares) < 260:
        s = f"{r.choice(['FS', 'NAS', 'FS', 'CIFS'])}-{r.randint(1, 98):02d}"
        if s not in shares:
            shares.append(s)
    R["shares"] = shares
    servers = [p["srv_old"], p["srv_new"], p["srv_other"]]
    other_jobs = []
    for s in shares[1:]:
        for kind in ("NIGHTLY", "WEEKLY"):
            other_jobs.append({"job": f"{s.replace('-', '')}-{kind}", "share": s, "server": r.choice(servers)[0]})
    R["other_jobs"] = other_jobs
    n_noise = int(15400 * p["noise"]) + 40
    used = {int(s["sid"][3:]) for s in specs}
    noise_sets = []
    days = (dt.date.fromisoformat(p["fallback"]) - w0).days + 9
    for _ in range(n_noise):
        j = r.choice(other_jobs)
        di = r.randint(0, days)
        while True:
            n = p["set_base"] + (di + 3) * 900 + r.randint(0, 899)
            if n not in used:
                break
        used.add(n)
        q = from_wall(dt.datetime.combine(w0 + dt.timedelta(days=di), dt.time(r.randint(0, 23), r.randint(0, 59), r.randint(0, 59))), tz)
        typ = r.choice(["INCR", "INCR", "INCR", "DIFF", "FULL"])
        st = r.choice(["COMPLETED"] * 12 + ["FAILED", "CANCELLED", "PARTIAL"])
        noise_sets.append({"sid": f"BS-{n:05d}", "job_name": j["job"], "type": typ, "job_status": st,
                           "server": j["server"], "queued": q, "snap": q + dt.timedelta(minutes=r.randint(2, 9)),
                           "ended": q + dt.timedelta(minutes=r.randint(15, 300)), "share": j["share"]})
    noise_sets.sort(key=lambda s: s["sid"])
    R["noise_sets"] = noise_sets

    # ---- job definitions and the job rename crosswalk
    synth = next(s for s in specs if s["type"] == "SYNTH")
    rename_eff = local_wall(synth["queued"], tz).date()
    R["rename_eff"] = rename_eff.isoformat()
    jobdefs = [{"job": p["job_new"], "share": p["share"], "server": p["srv_new"][0], "status": "ACTIVE"},
               {"job": p["job_old"], "share": "", "server": p["srv_old"][0], "status": "RETIRED"}]
    for j in other_jobs:
        jobdefs.append({"job": j["job"], "share": j["share"], "server": j["server"], "status": "ACTIVE"})
    while len(jobdefs) < target_rows(p, r):
        s = r.choice(shares[1:])
        jobdefs.append({"job": f"{s.replace('-', '')}-{r.choice(['ARCHIVE', 'MONTHLY', 'ADHOC', 'COPY', 'VERIFY'])}{r.randint(1, 999):03d}",
                        "share": s, "server": r.choice(servers)[0], "status": r.choice(["ACTIVE", "ACTIVE", "RETIRED"])})
    R["jobdefs"] = jobdefs
    xwalk = [{"old": p["job_old"], "new": p["job_new"], "effective": rename_eff.isoformat()},
             {"old": p["job_old"] + "-TEST", "new": p["job_new"], "effective": (rename_eff + dt.timedelta(days=40)).isoformat()}]
    for j in other_jobs[: len(other_jobs) // 2]:
        xwalk.append({"old": j["job"].replace("NIGHTLY", "DAILY").replace("WEEKLY", "WKLY"), "new": j["job"],
                      "effective": (w0 - dt.timedelta(days=r.randint(30, 900))).isoformat()})
    while len(xwalk) < doc_rows(p, r):
        xwalk.append({"old": f"LEG-{r.randint(1000, 9999)}-{r.choice(['D', 'W', 'M'])}", "new": r.choice(jobdefs)["job"],
                      "effective": (w0 - dt.timedelta(days=r.randint(1, 1500))).isoformat()})
    R["xwalk"] = xwalk

    # ---- maintenance calendar (planned windows) and the array's own record of actual windows
    events = []
    arr = p["array"]
    for s in specs:
        if s["crash"] == "planned":
            st = s["snap"] - dt.timedelta(minutes=r.randint(10, 50))
            events.append({"uid": f"MW-{r.hexstr(10)}@ops", "array": arr, "start": st, "end": st + dt.timedelta(hours=2),
                           "impact": "SNAPSHOT-CONSISTENCY", "status": "CONFIRMED", "actual": None, "set": s["sid"]})
        if s["crash"] == "actual":
            st = s["snap"] + dt.timedelta(minutes=r.randint(5, 30))
            a0 = s["snap"] - dt.timedelta(minutes=r.randint(5, 25))
            events.append({"uid": f"MW-{r.hexstr(10)}@ops", "array": arr, "start": st, "end": st + dt.timedelta(hours=2),
                           "impact": "SNAPSHOT-CONSISTENCY", "status": "CONFIRMED", "actual": (a0, a0 + dt.timedelta(minutes=95)),
                           "set": s["sid"]})
    applied = [s for s in specs if s["type"] == "INCR" and s["job_status"] == "COMPLETED" and not s["crash"]]
    for s, how in zip(r.sample(applied, 3), ["CANCELLED", "OTHER", "NONE"]):
        st = s["snap"] - dt.timedelta(minutes=30)
        events.append({"uid": f"MW-{r.hexstr(10)}@ops", "array": arr if how != "OTHER" else r.choice([a for a in ARRAYS if a != arr]),
                       "start": st, "end": st + dt.timedelta(hours=1),
                       "impact": "NONE" if how == "NONE" else "SNAPSHOT-CONSISTENCY",
                       "status": "CANCELLED" if how == "CANCELLED" else "CONFIRMED", "actual": None, "set": None})
    for s in specs:
        if s.get("at_rp"):
            events.append({"uid": f"MW-{r.hexstr(10)}@ops", "array": arr, "start": s["snap"] - dt.timedelta(hours=1),
                           "end": s["snap"], "impact": "SNAPSHOT-CONSISTENCY",
                           "status": "CONFIRMED", "actual": None, "set": None, "edge": True})
    while len(events) < target_rows(p, r):
        st = from_wall(dt.datetime.combine(w0 + dt.timedelta(days=r.randint(-20, 40)), dt.time(r.randint(0, 23), r.choice([0, 15, 30, 45]))), tz)
        a = r.choice([x for x in ARRAYS if x != arr])
        events.append({"uid": f"MW-{r.hexstr(10)}@ops", "array": a, "start": st,
                       "end": st + dt.timedelta(minutes=r.choice([30, 60, 90, 120, 240])),
                       "impact": r.choice(["SNAPSHOT-CONSISTENCY", "NONE", "LATENCY"]),
                       "status": r.choice(["CONFIRMED", "CONFIRMED", "TENTATIVE", "CANCELLED"]),
                       "actual": None, "set": None})
    R["events"] = events

    # ---- hosts, client codes, roots, servers
    cl = p["clients"]
    hosts = []
    for c in cl:
        hosts.append({"host": c["host"], "os": c["os"], "tz": c["tz"], "fs": c["fs"]})
    oses = ["windows", "linux", "macos"]
    while len(hosts) < target_rows(p, r):
        o = r.choice(oses)
        hosts.append({"host": f"{r.choice(['WS', 'SRV', 'LT', 'NAS', 'VM'])}{r.randint(10000, 99999)}", "os": o,
                      "tz": r.choice(SITE_TZ), "fs": r.choice(["NTFS", "ext4", "APFS", "XFS", "FAT32", "exFAT"])})
    R["hosts"] = hosts
    cmdb_tz = {cl[3]["host"]: "UTC", cl[0]["host"]: tz}
    R["cmdb_tz"] = cmdb_tz
    clientx = [{"code": c["code"], "host": c["host"], "from": "2024-01-01", "to": ""} for c in cl]
    clientx.append({"code": cl[3]["code"], "host": "INGEST-LEGACY" + p["share_num"], "from": "2021-03-01", "to": "2023-12-31"})
    while len(clientx) < doc_rows(p, r):
        h = r.choice(hosts[4:])
        clientx.append({"code": f"C{r.randint(5000, 99999)}", "host": h["host"],
                        "from": (w0 - dt.timedelta(days=r.randint(30, 2000))).isoformat(), "to": ""})
    R["clientx"] = clientx
    roots = []
    for c in cl:
        for i, rt in enumerate(c["roots"]):
            roots.append({"host": c["host"], "share": p["share"], "slot": i, "root": rt})
    while len(roots) < target_rows(p, r):
        h = r.choice(hosts[4:])
        s = r.choice(shares[1:])
        rt = (f"{r.choice('DEFGH')}:\\Shares\\{s}" if h["os"] == "windows" else f"/srv/{s.lower()}")
        roots.append({"host": h["host"], "share": s, "slot": 0, "root": rt})
    R["roots"] = roots
    srv = []
    for name, stz in servers:
        srv.append({"server": name, "tz": stz, "site": name[4:7]})
    upgrade = from_wall(dt.datetime.combine(dt.date.fromisoformat(p["fallback"]) + dt.timedelta(days=3), dt.time(12, 0)), p["srv_new"][1])
    builds = [{"server": p["srv_new"][0], "build": "7.0.4", "installed": from_wall(dt.datetime(p["year"], 3, 2, 10), p["srv_new"][1]), "stamp": "local"},
              {"server": p["srv_new"][0], "build": "7.2.1", "installed": upgrade, "stamp": "offset"},
              {"server": p["srv_old"][0], "build": "8.1.0", "installed": from_wall(dt.datetime(p["year"], 1, 12, 10), p["srv_old"][1]), "stamp": "offset"},
              {"server": p["srv_other"][0], "build": "7.0.9", "installed": from_wall(dt.datetime(p["year"], 2, 2, 10), p["srv_other"][1]), "stamp": "local"}]
    R["servers"] = srv
    R["builds"] = builds
    R["upgrade"] = upgrade
    share_reg = [{"share": p["share"], "aliases": [f"\\\\{p['unc']}\\projects"], "array": arr, "tz": tz,
                  "case": "insensitive-preserving"}]
    for s in shares[1:]:
        share_reg.append({"share": s, "aliases": [f"\\\\{s.lower()}\\data"], "array": r.choice(ARRAYS), "tz": r.choice(SITE_TZ),
                          "case": r.choice(["insensitive-preserving", "sensitive"])})
    while len(share_reg) < target_rows(p, r):
        s = f"ARC-{r.randint(1000, 99999)}"
        share_reg.append({"share": s, "aliases": [f"\\\\{s.lower()}\\vault"], "array": r.choice(ARRAYS), "tz": r.choice(SITE_TZ),
                          "case": "sensitive"})
    R["share_reg"] = share_reg
    build_media(w, R, r)
    build_av(w, R, r)
    build_identity(w, R, r)
    build_scope(w, R, r)
    return R


VAULTS = ["VLT-ONS1", "VLT-OFF1", "VLT-OFF2", "VLT-OFF3", "VLT-DR1", "VLT-CLD1"]


def build_media(w: World, R: dict, r: Rng) -> None:
    p = w.p
    req_end = R["req_end"]
    w0 = dt.date.fromisoformat(p["w0"])
    tz = p["site_tz"]
    share_cts = sorted(w.containers)
    n_lto = max(12, len(share_cts) // 14)
    mseq = [r.randint(10000, 12000)]

    def mid() -> str:
        mseq[0] += r.randint(1, 7)
        return f"MD-{mseq[0]:05d}"

    lto = [{"media": mid(), "kind": "LTO", "gen": r.choice(["LTO-7", "LTO-8", "LTO-8", "LTO-9"]),
            "home": r.choice(["VLT-OFF1", "VLT-OFF2", "VLT-ONS1"]), "status": "ACTIVE", "status_date": "2026-01-15"}
           for _ in range(n_lto)]
    disk = [{"media": mid(), "kind": r.choice(["DISK", "CLOUD"]), "gen": "-", "home": r.choice(["VLT-DR1", "VLT-CLD1"]),
             "status": "ACTIVE", "status_date": "2026-02-01"} for _ in range(max(3, n_lto // 3))]
    cloud = [{"media": mid(), "kind": "CLOUD", "gen": "-", "home": "VLT-CLD1", "status": "ACTIVE",
              "status_date": "2026-02-01"} for _ in range(max(2, n_lto // 6))]
    for m in disk + cloud:
        m["barcode"] = f"BC{r.randint(100000, 999999)}"
    # copies of every share container
    copies: dict[str, list[dict]] = {}
    for c in share_cts:
        ct = w.containers[c]
        size = ct["size"] * r.randint(55, 98) // 100 + r.randint(512, 9000)
        ct["stored"] = size
        rows = [{"container": c, "copy": 1, "media": r.choice(lto)["media"], "size": size, "created": ct["created"]}]
        rows.append({"container": c, "copy": 2, "media": r.choice(disk)["media"], "size": size, "created": ct["created"]})
        if r.chance(0.45):
            rows.append({"container": c, "copy": 3, "media": r.choice(cloud)["media"], "size": size, "created": ct["created"]})
        copies[c] = rows
    flags = r.sample(range(n_lto), 9)
    damaged = [lto[i]["media"] for i in flags[0:2]]
    rejected = lto[flags[2]]["media"]
    lto[flags[3]]["gen"] = "LTO-6"
    lto[flags[4]]["status"] = "EXPIRED"
    lto[flags[4]]["status_date"] = (w0 + dt.timedelta(days=5)).isoformat()
    draft_bad = lto[flags[5]]["media"]
    corrected_to = lto[flags[6]]["media"]
    typo = "MD-" + str(int(corrected_to[3:]) + 1000).zfill(5)
    late_destroyed = lto[flags[7]]["media"]
    early_destroyed = lto[flags[8]]["media"]
    disk[0]["status"] = "EXPIRED"
    disk[0]["status_date"] = (w0 + dt.timedelta(days=9)).isoformat()
    media = lto + disk + cloud
    R["media_share"] = [m["media"] for m in media]
    merr = [{"id": f"ME-{r.randint(1000, 9999)}", "media": m, "defect": "DAMAGED", "effective": (w0 + dt.timedelta(days=r.randint(2, 20))).isoformat(),
             "status": "APPROVED", "rev": "A"} for m in damaged]
    merr.append({"id": f"ME-{r.randint(1000, 9999)}", "media": rejected, "defect": "UNREADABLE",
                 "effective": (w0 + dt.timedelta(days=4)).isoformat(), "status": "REJECTED", "rev": "A"})
    typo_id = f"ME-{r.randint(1000, 9999)}"
    merr.append({"id": typo_id, "media": typo, "defect": "DAMAGED", "effective": (w0 + dt.timedelta(days=8)).isoformat(),
                 "status": "APPROVED", "rev": "A"})
    merr_b = [{"id": f"ME-{r.randint(1000, 9999)}", "media": draft_bad, "defect": "DAMAGED",
               "effective": (w0 + dt.timedelta(days=12)).isoformat(), "status": "PROPOSED", "rev": "B"}]
    corrections = [{"errata": typo_id, "field": "media", "was": typo, "now": corrected_to,
                    "cab": f"CAB-{r.randint(2000, 2999)}"}]
    R["merr"], R["merr_b"], R["merr_corr"] = merr, merr_b, corrections
    R["destroy"] = [{"media": late_destroyed, "date": (req_end + dt.timedelta(days=1)).astimezone(UTC)},
                    {"media": early_destroyed, "date": req_end - dt.timedelta(days=2)}]
    # checksum audit, rerun and the ticket that scopes the rerun
    sample_c = r.sample(share_cts, min(len(share_cts), 9))
    mism = sample_c[:5]
    ticketed = sample_c[:2]
    rerun_extra_ok = sample_c[2]
    rerun_extra_bad = sample_c[5]
    chk = []
    for c in share_cts:
        for row in copies[c]:
            if row["copy"] == 1 or r.chance(0.3):
                exp = r.hexstr(32)
                bad = (c in mism and row["copy"] == 1)
                chk.append({"container": c, "copy": row["copy"], "expected": exp, "observed": r.hexstr(32) if bad else exp,
                            "result": "MISMATCH" if bad else "MATCH",
                            "at": req_end - dt.timedelta(days=r.randint(3, 9), minutes=r.randint(0, 900))})
    rerun = []
    for c in ticketed + [rerun_extra_ok]:
        rerun.append({"container": c, "copy": 1, "result": "MATCH", "at": req_end - dt.timedelta(hours=r.randint(10, 40))})
    rerun.append({"container": rerun_extra_bad, "copy": 1, "result": "MISMATCH", "at": req_end - dt.timedelta(hours=12)})
    R["chk_share"], R["rerun_share"], R["ticketed"] = chk, rerun, ticketed
    # copy jobs (copies 2 and 3 only count once their copy job completed)
    copyjobs = []
    for c in share_cts:
        for row in copies[c]:
            if row["copy"] == 1:
                continue
            st, at = "COMPLETED", row["created"] + dt.timedelta(hours=r.randint(4, 30))
            x = r.random()
            if x < 0.02:
                st = "FAILED"
            elif x < 0.035:
                at = req_end + dt.timedelta(hours=r.randint(2, 50))
            copyjobs.append({"job": f"CJ-{r.randint(100000, 999999)}", "container": c, "copy": row["copy"],
                             "status": st, "at": at})
    R["copyjobs_share"] = copyjobs
    # repack of a few containers into new RC- containers that the v1 map does not know
    repack = []
    for c in r.sample(share_cts, max(2, len(share_cts) // 30)):
        new = f"RC-{r.randint(1000000, 9999999)}"
        at = req_end - dt.timedelta(days=r.randint(1, 6))
        if r.chance(0.2):
            at = req_end + dt.timedelta(days=2)
        repack.append({"old": c, "new": new, "at": at})
        if at <= req_end:
            size = copies[c][0]["size"] + r.randint(-400, 400)
            copies[new] = [{"container": new, "copy": 1, "media": r.choice(lto)["media"], "size": size, "created": at},
                           {"container": new, "copy": 2, "media": r.choice(disk)["media"], "size": size, "created": at}]
            copyjobs.append({"job": f"CJ-{r.randint(100000, 999999)}", "container": new, "copy": 2, "status": "COMPLETED",
                             "at": at + dt.timedelta(hours=3)})
    R["repack"] = repack
    R["copies"] = copies
    # vault location: slot register as of window start, then transfers and recalls up to the request date
    slots = {}
    for m in media:
        if m["home"] != "VLT-OFF3":
            slots[m["media"]] = m["home"]
    off3 = r.sample([m for m in lto if m["media"] not in damaged], 3)
    for m in off3:
        m["home"] = "VLT-OFF3"
        slots.pop(m["media"], None)
    xfers, recalls = [], []
    for m in r.sample(lto, max(3, n_lto // 4)):
        dest = r.choice([v for v in VAULTS[:5] if v != m["home"]])
        shipped = req_end - dt.timedelta(days=r.randint(3, 20))
        recv = shipped + dt.timedelta(days=r.randint(1, 3))
        if r.chance(0.25):
            recv = req_end + dt.timedelta(days=1)
        xfers.append({"media": m["media"], "from": m["home"], "to": dest, "shipped": shipped, "received": recv})
    for m in r.sample(lto, max(2, n_lto // 6)):
        recalls.append({"media": m["media"], "to": "VLT-ONS1", "at": req_end - dt.timedelta(hours=r.randint(6, 60))})
    R["media"], R["slots"], R["xfers"], R["recalls"], R["off3"] = media, slots, xfers, recalls, [m["media"] for m in off3]
    R["dash_after"] = [{"media": m["media"], "vault": r.choice(VAULTS[:5])} for m in r.sample([m for m in lto if m["media"] not in R["off3"]], 4)]
    # vault service calendar: priority per vault and weekday
    prio = {}
    reqd = dt.date.fromisoformat(p["request_date"])
    span = 420 if p["tier"] == "visible" else 20
    for k in range(-span, span):
        day = (reqd + dt.timedelta(days=k)).isoformat()
        order = VAULTS[:]
        r.shuffle(order)
        for i, v in enumerate(order):
            prio[(v, day)] = i + 1
    R["vault_cal"] = prio


def effective_sid(w: World) -> str:
    specs = sorted(w.specs, key=lambda s: (s["snap"], s["sid"]))
    d2 = max(i for i, s in enumerate(specs) if s["type"] == "DIFF" and s["snap"] <= w.rp)
    last = specs[d2]["sid"]
    for s in specs[d2 + 1:]:
        if s["snap"] > w.rp or s["crash"]:
            break
        if s["type"] == "INCR" and s["job_status"] == "COMPLETED":
            last = s["sid"]
    return last


def version_history(w: World) -> dict[str, list[tuple[dt.datetime, str]]]:
    """identity key -> [(snapshot, vid)] over every F entry of every set, capture order."""
    hist: dict[str, list] = {}
    for s in sorted(w.specs, key=lambda s: (s["snap"], s["sid"])):
        for e in w.entries[s["sid"]]:
            if e["etype"] == "F" and not e.get("junk") and not e.get("reject"):
                hist.setdefault(Share.key(e["path"]), []).append((s["snap"], e["vid"], e["container"]))
    return hist


SIGS = ["Trojan.Win32.Agent", "Ransom.Lockbit", "Exploit.Office.CVE", "Backdoor.Cobalt", "Worm.Autorun",
        "Adware.Bundler", "Riskware.Miner", "Heur.Macro.Downloader"]


def build_av(w: World, R: dict, r: Rng) -> None:
    p = w.p
    req_end = R["req_end"]
    eff = effective_sid(w)
    R["effective_sid"] = eff
    state = w.snapshots[eff]["objs"]
    hist = version_history(w)
    cut = from_wall(dt.datetime.combine(dt.date.fromisoformat(p["fallback"]) - dt.timedelta(days=8), dt.time(0, 0)), p["site_tz"])
    R["av_cutover"] = cut
    engines = [{"code": f"E{r.randint(10, 99)}", "vendor": v, "product": f"{v.split()[0]} Engine {r.randint(3, 9)}"} for v in VENDORS]
    R["engines"] = engines
    final_engine, prelim_engine = engines[0], engines[1]
    findings, prelim = [], []

    def ct_created(c: str) -> dt.datetime:
        return w.containers[c]["created"]

    def flag(vid: str, verdict: str, sig: str, rev: int, engine: dict) -> None:
        sha = w.versions[vid]["sha"]
        cts = sorted({c for vs in hist.values() for (_, v, c) in vs if v == vid})
        for c in cts:
            row = {"sha": sha, "container": c, "verdict": verdict, "sig": sig, "rev": rev, "engine": engine["code"],
                   "at": req_end - dt.timedelta(days=r.randint(0, 3), minutes=r.randint(0, 1400))}
            if ct_created(c) >= cut:
                findings.append(row)
            else:
                prelim.append(dict(row, engine=prelim_engine["code"]))

    files = sorted(k for k, o in state.items() if o["kind"] == "file"
                   and any(k == Share.key(i) or k.startswith(Share.key(i) + "/") for i in p["includes"])
                   and not any(x in k for x in ("~$", ".tmp", "thumbs.db", ".ds_store", "desktop.ini", "core.dump", ".bak", ".hex", "/build/", "/tmp/")))
    multi = [k for k in files if len({v for _, v, _ in hist.get(k, [])}) >= 2]
    single = [k for k in files if len({v for _, v, _ in hist.get(k, [])}) == 1]
    picks = r.sample(multi, min(len(multi), 22))
    withdrawn_sig = ("Heur.Macro.Downloader", 41, 44)
    R["withdrawals"] = [{"vendor": final_engine["vendor"], "sig": withdrawn_sig[0], "rev_from": withdrawn_sig[1],
                         "rev_to": withdrawn_sig[2], "at": req_end - dt.timedelta(days=1)},
                        {"vendor": final_engine["vendor"], "sig": "Ransom.Lockbit", "rev_from": 10, "rev_to": 12,
                         "at": req_end + dt.timedelta(days=3)},
                        {"vendor": prelim_engine["vendor"], "sig": "Worm.Autorun", "rev_from": 1, "rev_to": 3,
                         "at": req_end - dt.timedelta(days=2)}]
    R["av_cases"] = {}
    for i, k in enumerate(picks):
        vid = state[k]["vid"]
        if i < 12:
            flag(vid, "INFECTED", r.choice(SIGS[:5]), r.randint(10, 30), final_engine)
            if i % 4 == 0:
                vs = [v for _, v, _ in hist[k] if v != vid]
                if vs:
                    flag(vs[-1], "INFECTED", r.choice(SIGS[:5]), r.randint(10, 30), final_engine)
            R["av_cases"][k] = "infected"
        elif i < 17:
            flag(vid, "INFECTED", withdrawn_sig[0], r.randint(withdrawn_sig[1], withdrawn_sig[2]), final_engine)
            R["av_cases"][k] = "withdrawn"
        else:
            flag(vid, "PUA", "Adware.Bundler", r.randint(1, 9), final_engine)
            R["av_cases"][k] = "pua"
    for k in r.sample(single, min(len(single), 6)):
        flag(state[k]["vid"], "INFECTED", r.choice(SIGS[:5]), r.randint(10, 30), final_engine)
        R["av_cases"][k] = "infected-new"
    # preliminary scan: detections the final scan later cleared (content captured after the cutover)
    clear = r.sample([k for k in files if k not in R["av_cases"]], 8)
    for k in clear:
        vid = state[k]["vid"]
        for c in sorted({c for (_, v, c) in hist[k] if v == vid}):
            if ct_created(c) >= cut:
                prelim.append({"sha": w.versions[vid]["sha"], "container": c, "verdict": "INFECTED", "sig": r.choice(SIGS[:5]),
                               "rev": r.randint(5, 9), "engine": prelim_engine["code"], "at": cut - dt.timedelta(hours=r.randint(2, 30))})
                findings.append({"sha": w.versions[vid]["sha"], "container": c, "verdict": "CLEAN", "sig": "", "rev": 0,
                                 "engine": final_engine["code"], "at": req_end - dt.timedelta(days=1)})
    R["av_final_share"], R["av_prelim_share"] = findings, prelim


def build_identity(w: World, R: dict, r: Rng) -> None:
    p = w.p
    rp = w.rp
    first = ["anna", "ben", "chen", "dev", "elif", "farah", "goran", "hana", "ivan", "jun", "kofi", "lena", "mia",
             "nils", "omar", "priya", "quinn", "ravi", "sara", "tomas", "uma", "vik", "wen", "yusuf", "zoe"]
    last = ["meyer", "okafor", "lindqvist", "tanaka", "rossi", "nair", "kowalski", "silva", "haddad", "becker"]

    def acct() -> str:
        return f"{r.choice(first)}.{r.choice(last)}{r.randint(1, 99)}"

    idmap, changes = [], []
    cur = {}
    for rid in p["rids"]:
        sid = f"S-1-5-21-{p['dom']}-{rid}"
        a = acct()
        if r.chance(0.15):
            old = acct()
            cut = rp - dt.timedelta(days=r.randint(1, 20))
            if r.chance(0.3):
                cut = rp
            idmap.append({"principal": sid, "account": old, "from": rp - dt.timedelta(days=900), "to": cut})
            idmap.append({"principal": sid, "account": a, "from": cut, "to": None})
        else:
            idmap.append({"principal": sid, "account": a, "from": rp - dt.timedelta(days=900), "to": None})
        cur[sid] = a
    for rid in r.sample(p["rids"], 14):
        sid = f"S-1-5-21-{p['dom']}-{rid}"
        new = acct()
        x = r.random()
        if x < 0.45:
            changes.append({"principal": sid, "account": new, "at": rp - dt.timedelta(days=r.randint(1, 9)), "status": "APPROVED"})
        elif x < 0.7:
            changes.append({"principal": sid, "account": new, "at": rp + dt.timedelta(days=r.randint(1, 9)), "status": "APPROVED"})
        else:
            changes.append({"principal": sid, "account": new, "at": rp - dt.timedelta(days=r.randint(1, 9)), "status": "PENDING"})
    R["idmap_share"], R["idchanges_share"] = idmap, changes
    legacy = {f"S-1-5-21-{p['legacy_dom']}-{rid}": f"legacy\\{acct()}" for rid in p["legacy_rids"]}
    R["legacy_accounts"] = legacy
    local = {}
    for c in p["clients"]:
        if c["os"] != "windows":
            local[c["host"]] = {u: acct() for u in p["uids"] if r.chance(0.9)}
    R["local_accounts"] = local
    R["ad_names"] = {sid: acct() for sid in cur}


def build_scope(w: World, R: dict, r: Rng) -> None:
    p = w.p
    rp = w.rp
    eff = R["effective_sid"]
    dirs = sorted(v for k, v in w.snapshots[eff]["dirs"].items() if k.count("/") >= 3
                  and any(Share.key(v).startswith(Share.key(i) + "/") for i in p["includes"]))
    picks = r.sample(dirs, 3)
    R["dispositions_share"] = [
        {"hold": f"RM-{r.randint(10000, 99999)}", "prefix": picks[0], "action": "DESTROY", "effective": (rp - dt.timedelta(days=r.randint(2, 30))).date().isoformat()},
        {"hold": f"RM-{r.randint(10000, 99999)}", "prefix": picks[1], "action": "DESTROY", "effective": (rp + dt.timedelta(days=r.randint(2, 30))).date().isoformat()},
        {"hold": f"RM-{r.randint(10000, 99999)}", "prefix": picks[2], "action": "RETAIN", "effective": (rp - dt.timedelta(days=60)).date().isoformat()},
    ]
    eff_date = (rp - dt.timedelta(days=400)).date().isoformat()
    pats = [
        ("~$*", "ALL", eff_date, ""), ("*.tmp", "ALL", eff_date, ""), ("Thumbs.db", "ALL", eff_date, ""),
        (".DS_Store", "ALL", eff_date, ""), ("desktop.ini", "ALL", eff_date, ""), ("*.bak", "ALL", eff_date,
                                                                                    (rp - dt.timedelta(days=12)).date().isoformat()),
        ("core.dump", p["share"], eff_date, ""), ("/Engineering/Projects/*/Build/", p["share"], eff_date, ""),
        ("*.log", p["share"], (rp + dt.timedelta(days=3)).date().isoformat(), ""),
        ("**/tmp/**", "ALL", eff_date, ""), ("/Design/Archive/**/*.zip", p["share"], eff_date, ""),
        ("*.hex", p["share"], eff_date, ""), ("[Rr]ender*.png", p["share"], eff_date, ""),
        ("*.TXT", p["share"], (rp - dt.timedelta(days=2)).date().isoformat(), ""),
    ]
    R["patterns_share"] = [{"id": f"EX-{1000 + i * 7 + r.randint(0, 6)}", "pattern": a, "scope": b, "from": c, "to": d}
                           for i, (a, b, c, d) in enumerate(pats)]
    hexp = next(x for x in R["patterns_share"] if x["pattern"] == "*.hex")
    R["withdraw_v9"] = [{"id": hexp["id"], "effective": (rp - dt.timedelta(days=5)).date().isoformat(), "cab": f"CAB-{r.randint(3000, 3999)}"},
                        {"id": R["patterns_share"][1]["id"], "effective": (rp + dt.timedelta(days=9)).date().isoformat(), "cab": f"CAB-{r.randint(3000, 3999)}"}]
    R["patterns_v9_new"] = [{"id": f"EX-{r.randint(5000, 5999)}", "pattern": "*.json", "scope": p["share"],
                             "from": (rp + dt.timedelta(days=4)).date().isoformat(), "to": ""}]


# --------------------------------------------------------------------------- world-level render flags


def mark_entry_flags(w: World, R: dict) -> None:
    """Entries whose rendered values need a documented repair: sentinels and catalog errata targets."""
    r = w.rng.fork("flags")
    share_f = [e for sid in sorted(w.entries) for e in w.entries[sid] if e["etype"] == "F" and not e.get("reject")]
    for e in r.sample(share_f, max(4, len(share_f) // 260)):
        e["sent_mtime"] = True
    for e in r.sample(share_f, max(4, len(share_f) // 300)):
        e["sent_owner"] = True
    errata = []
    fields = ["sha256", "size", "mtime", "container"]
    for e in r.sample(share_f, max(12, len(share_f) // 160)):
        if e.get("sent_mtime"):
            continue
        f = r.choice(fields)
        e["corrupt"] = f
        mode = r.random()
        v = w.versions[e["vid"]]
        good = {"sha256": v["sha"], "size": str(v["size"]), "mtime": iso_z(v["mtime"]), "container": e["container"]}[f]
        if mode < 0.7:
            errata.append({"entry": e["eid"], "field": f, "value": good, "rev": 1, "status": "APPROVED"})
        else:
            errata.append({"entry": e["eid"], "field": f, "value": _bogus(r, f, good), "rev": 1, "status": "APPROVED"})
            errata.append({"entry": e["eid"], "field": f, "value": good, "rev": 2, "status": "APPROVED"})
    for e in r.sample(share_f, max(6, len(share_f) // 400)):
        if e.get("corrupt"):
            continue
        f = r.choice(fields)
        v = w.versions[e["vid"]]
        good = {"sha256": v["sha"], "size": str(v["size"]), "mtime": iso_z(v["mtime"]), "container": e["container"]}[f]
        errata.append({"entry": e["eid"], "field": f, "value": _bogus(r, f, good), "rev": r.choice([1, 2]),
                       "status": r.choice(["REJECTED", "PENDING"])})
    R["errata_share"] = errata


def _bogus(r: Rng, f: str, good: str) -> str:
    if f == "sha256":
        return r.hexstr(64)
    if f == "size":
        return str(int(good) + r.randint(1, 50000))
    if f == "mtime":
        return iso_z(dt.datetime.fromisoformat(good.replace("Z", "+00:00")) + dt.timedelta(hours=r.randint(1, 30)))
    return f"CT-{r.randint(1, 9999999):07d}"


def corrupt_value(r: Rng, f: str, v: dict, e: dict) -> dict:
    if f == "sha256":
        return {"sha": "0" * 64 if r.chance(0.4) else r.hexstr(64)}
    if f == "size":
        return {"size": v["size"] + r.randint(1, 900000)}
    if f == "mtime":
        return {"mtime": v["mtime"] + dt.timedelta(days=r.randint(1, 400))}
    return {"container": f"CT-{r.randint(1, 9999999):07d}"}


# --------------------------------------------------------------------------- value renderings

EPOCH = dt.datetime(1970, 1, 1, tzinfo=UTC)
FT_EPOCH = dt.datetime(1601, 1, 1, tzinfo=UTC)
CONFUSABLE = {"B": "\u0412", "C": "\u0421", "E": "\u0415", "M": "\u041c", "T": "\u0422", "S": "\u0405", "D": "D"}
NNBSP = "\u202f"


def group_int(n: int, locale: str) -> str:
    s = f"{n:,}"
    if locale == "de_DE":
        return s.replace(",", ".")
    if locale == "fr_FR":
        return s.replace(",", NNBSP)
    if locale == "en_US":
        return s
    return str(n)


def dec_text(d: Decimal, locale: str) -> str:
    s = format(d.normalize(), "f") if d != d.to_integral() else str(int(d))
    return s.replace(".", ",") if locale in ("de_DE", "fr_FR") else s


def ts_text(t: dt.datetime, kind: str, tz: str, frac: bool = False) -> str | int:
    if kind == "utc":
        return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S") + (f".{t.microsecond:06d}" if frac and t.microsecond else "") + "Z"
    if kind == "iso":
        lt = t.astimezone(ZoneInfo(tz))
        return lt.strftime("%Y-%m-%dT%H:%M:%S") + (f".{t.microsecond:06d}" if frac and t.microsecond else "") + lt.strftime("%z")[:3] + ":" + lt.strftime("%z")[3:]
    if kind == "epoch":
        return (t - EPOCH) // dt.timedelta(seconds=1)
    if kind == "ms":
        return (t - EPOCH) // dt.timedelta(milliseconds=1)
    if kind == "ft":
        return (t - FT_EPOCH) // dt.timedelta(microseconds=1) * 10 + (0 if not frac else 0)
    if kind == "local":
        return local_wall(t, tz).strftime("%Y-%m-%d %H:%M:%S")
    raise ValueError(kind)


def xl_serial(t: dt.datetime, date1904: bool) -> float:
    base = dt.datetime(1904, 1, 1, tzinfo=UTC) if date1904 else dt.datetime(1899, 12, 30, tzinfo=UTC)
    secs = (floor_s(t) - base) // dt.timedelta(seconds=1)
    return secs / 86400


def mode_text(mode: int, kind: str, is_link: bool = False) -> str:
    if kind == "oct":
        return f"{mode:04o}"
    if kind == "oct3":
        return f"{mode:o}"
    if kind == "dec":
        return str(mode)
    if kind == "st":
        return f"{(0o120000 if is_link else 0o100000) | mode:o}"
    chars = ["l" if is_link else "-"]
    for shift, special, sc in ((6, 0o4000, "s"), (3, 0o2000, "s"), (0, 0o1000, "t")):
        bits = (mode >> shift) & 7
        x = "x" if bits & 1 else "-"
        if mode & special:
            x = sc if bits & 1 else sc.upper()
        chars.append(("r" if bits & 4 else "-") + ("w" if bits & 2 else "-") + x)
    return "".join(chars)


def id_variant(r: Rng, ident: str) -> str:
    pre, _, num = ident.partition("-")
    x = r.randint(0, 5)
    if x == 0:
        return ident.lower()
    if x == 1:
        return f"{pre}-{int(num)}"
    if x == 2:
        return f"  {ident} "
    if x == 3:
        return f"{pre}_{num}"
    if x == 4:
        return "".join(CONFUSABLE.get(c, c) if i < len(pre) else c for i, c in enumerate(ident))
    return f"{pre}{num}"


def raw_path(r: Rng, path: str, client: dict, variants: bool) -> str:
    comps = [c for c in path.split("/") if c]
    root = client["roots"][0]
    if client["os"] == "windows":
        if variants and len(client["roots"]) > 1 and r.chance(0.3):
            root = r.choice(client["roots"][1:])
        if variants and r.chance(0.05) and len(comps) > 2:
            i = r.randint(0, len(comps) - 2)
            comps[i] = comps[i] + r.choice([".", " ", ". "])
        if variants and r.chance(0.04) and len(comps) > 2:
            i = r.randint(1, len(comps) - 1)
            comps = comps[:i] + [r.choice(SUB_DIRS["Shared"]), ".."] + comps[i:]
        sep = "\\" if not (variants and r.chance(0.03)) else "/"
        if variants and r.chance(0.03):
            root = root.lower() if r.chance(0.5) else root.upper()
        return root + sep + sep.join(comps)
    if client["os"] == "macos":
        comps = [unicodedata.normalize("NFD", c) for c in comps]
    if variants and r.chance(0.04) and len(comps) > 1:
        comps.insert(r.randint(0, len(comps) - 1), ".")
    return root + "/" + "/".join(comps)


def reject_path(r: Rng, path: str, client: dict, kind: str) -> str:
    comps = [c for c in path.split("/") if c]
    if client["os"] == "windows":
        if kind == "unsafe":
            return client["roots"][0] + "\\" + "\\".join([".."] * r.randint(2, 4) + comps)
        return r.choice(["D:\\Shares\\Finance", "C:\\Users\\Public", "\\\\corp-fs09\\scans"]) + "\\" + "\\".join(comps)
    if kind == "unsafe":
        return client["roots"][0] + "/" + "/".join(comps[:1] + [".."] * r.randint(2, 4) + comps[1:])
    return r.choice(["/srv/samba/finance", "/mnt/shared", "/mnt/usb0"]) + "/" + "/".join(comps)


# --------------------------------------------------------------------------- file plan

CAT_FORMATS = (["csv"] * 10 + ["tsv"] * 5 + ["jsonl"] * 4 + ["json"] * 6 + ["txt"] * 3 + ["xml"] * 5 + ["parquet"] * 2
               + ["xlsx"] * 4)
CAT_ALIASES = {
    "set": ["set_id", "backup_set", "bset"], "seq": ["seq", "sequence"], "entry": ["entry_id", "eid"],
    "type": ["etype", "entry_type", "op"], "path": ["path", "src_path", "object"], "new_path": ["new_path", "rename_to"],
    "target": ["target", "link_target"], "kind": ["kind", "obj_kind"], "size": ["size", "size_bytes", "bytes", "size_kib"],
    "mtime": ["mtime", "modified"], "mode": ["mode_oct", "mode_sym", "mode_dec", "st_mode"], "attrs": ["attrs", "win_attrs"],
    "owner": ["owner", "principal"], "sha256": ["sha256", "content_hash", "digest"], "container": ["container", "ct_id"],
    "file_id": ["file_id", "inode"], "client": ["client", "agent_client"], "committed": ["committed", "commit_flag"],
    "voids": ["voids", "void_target"],
}
CAT_FIELDS = list(CAT_ALIASES)
TS_KINDS = ["utc", "iso", "epoch", "ms", "ft", "local"]
FIXED_LAYOUTS = {
    "A": [("set", 14), ("seq", 8), ("entry", 14), ("type", 2), ("client", 7), ("kind", 5), ("size", 16),
          ("mtime_ft", 20), ("mode_oct", 6), ("attrs", 5), ("owner", 50), ("sha256", 72), ("container", 15),
          ("file_id", 12), ("committed", 6), ("voids", 14), ("path", 260), ("new_path", 260), ("target", 260)],
    "B": [("entry", 14), ("set", 14), ("seq", 8), ("type", 2), ("client", 7), ("kind", 5), ("size", 16),
          ("mtime_epoch", 12), ("mode_dec", 6), ("attrs", 5), ("owner", 50), ("sha256", 72), ("container", 15),
          ("file_id", 12), ("committed", 6), ("voids", 14), ("path", 260), ("new_path", 260), ("target", 260)],
}


# The registered deterministic checks that settle a restore plan: visible_plan_exact for the shipped
# feed, and eval_plan_exact, extra_plan_7199369_exact, extra_plan_42133777_exact and
# extra_plan_121212121_exact for the four feeds the verifier generates. Every rule a trap plants is
# settled by the plan equality of the feed the trap lands in, so a trap's "test" field carries one of
# these five names. The trap list is author-side bookkeeping: nothing reads it at grade time, and
# build_feed stamps every trap with the check that grades the feed it has just built.
VISIBLE_PLAN_CHECK = "visible_plan_exact"
EVAL_PLAN_CHECK = "eval_plan_exact"
EXTRA_PLAN_CHECKS = {7199369: "extra_plan_7199369_exact",
                     42133777: "extra_plan_42133777_exact",
                     121212121: "extra_plan_121212121_exact"}
PLAN_CHECK = VISIBLE_PLAN_CHECK


def plan_check(seed: int, tier: str) -> str:
    """The registered check that grades the plan of the feed this seed and tier build."""
    if tier != "eval":
        return VISIBLE_PLAN_CHECK
    return EXTRA_PLAN_CHECKS.get(seed, EVAL_PLAN_CHECK)


class FileOut:
    def __init__(self, name: str, fmt: str, stream: str, part: str, status: str = "ORIGINAL", decoy: bool = False):
        self.name, self.fmt, self.stream, self.part, self.status, self.decoy = name, fmt, stream, part, status, decoy
        self.control: dict = {}
        self.tables: list[dict] = []      # {"name", "segments": [(columns, rows)]}
        self.doc: list = []               # documents: ("h", text) | ("p", text) | ("table", name, columns, rows)
        self.traps: list[dict] = []
        self.opts: dict = {}
        self.records = 0

    def trap(self, row, family: str, rule: str, test: str, direction: str = "") -> None:
        self.traps.append({"file": self.name, "row": row, "family": family, "decoy": self.decoy,
                           "direction": direction, "rule": rule, "test": test})


def cat_dialect(r: Rng, fmt: str) -> dict:
    d = {f: r.choice(a) for f, a in CAT_ALIASES.items()}
    d["ts"] = r.choice(TS_KINDS) if fmt != "xlsx" else r.choice(["xl", "xl", "utc", "local"])
    if fmt == "parquet":
        d["ts"] = r.choice(["pq", "ms", "ft", "epoch"])
    d["locale"] = r.choice(["plain", "plain", "en_US", "de_DE", "fr_FR"]) if fmt in ("csv", "tsv", "txt", "xlsx", "xml") else "plain"
    if d["size"] == "size_kib" and fmt in ("txt",):
        d["size"] = "size"
    d["frac"] = r.chance(0.5)
    return d


def cat_columns(d: dict) -> list[str]:
    cols = []
    for f in CAT_FIELDS:
        a = d[f]
        if f == "mtime":
            a = f"{a}_{d['ts']}"
        cols.append(a)
    return cols


def cat_cells(w: World, e: dict, d: dict, fmt: str, r: Rng, plant: str | None, clients: dict) -> list:
    typed = fmt in ("xlsx", "parquet", "json", "jsonl")
    cl = clients.get(e["client"]) or {"os": "windows", "roots": ["E:\\Data"], "fs": "NTFS", "tz": "UTC"}
    v = w.versions.get(e.get("vid")) if e["etype"] == "F" else None
    meta = e.get("meta") if e["etype"] == "L" else None
    if e.get("noise"):
        v = e.get("v")
    vals: dict = {f: "" for f in CAT_FIELDS}
    vals["set"] = e["sid"] if plant != "T1" else id_variant(r, e["sid"])
    vals["seq"] = e["seq"]
    vals["entry"] = e["eid"]
    vals["type"] = e["etype"]
    if e["etype"] == "X":
        pass
    elif e.get("reject"):
        vals["path"] = reject_path(r, e["path"], cl, e["reject"])
    elif e.get("noise"):
        vals["path"] = e["path"]
    else:
        vals["path"] = raw_path(r, e["path"], cl, variants=plant in ("T9", None) and e["etype"] != "D")
    if e["etype"] == "R":
        vals["new_path"] = e["new"] if e.get("noise") else raw_path(r, e["new"], cl, variants=False)
    if e["etype"] == "H":
        vals["target"] = raw_path(r, e["target"], cl, variants=False)
    if e["etype"] == "L":
        t = e["target"].replace("@ROOT@", cl["roots"][0])
        vals["target"] = t
    if e["etype"] in ("W", "R"):
        vals["kind"] = e["kind"]
    vals["client"] = e["client"]
    vals["committed"] = {"Y": d.get("yes", "Y"), "N": d.get("no", "N")}[e["committed"]]
    if e["etype"] == "X":
        vals["voids"] = e["voids"] if plant != "T1" else id_variant(r, e["voids"])
    src = v or meta
    if src is not None:
        size = src.get("size")
        mtime = src["mtime"]
        sha = src.get("sha")
        container = e.get("container")
        if e.get("corrupt"):
            c = corrupt_value(r, e["corrupt"], v, e)
            size, mtime, sha, container = c.get("size", size), c.get("mtime", mtime), c.get("sha", sha), c.get("container", container)
        if size is not None:
            if d["size"] == "size_kib":
                kib = Decimal(size) / 1024
                vals["size"] = float(kib) if typed else dec_text(kib, d["locale"])
            else:
                vals["size"] = size if typed else group_int(size, d["locale"])
        if cl.get("fs") == "FAT32":
            mtime = local_wall(mtime, cl["tz"]).replace(tzinfo=UTC)
        if e.get("sent_mtime"):
            vals["mtime"] = {"utc": "0000-00-00T00:00:00Z", "iso": "0000-00-00T00:00:00+00:00", "local": "0000-00-00 00:00:00",
                             "epoch": 0, "ms": -1, "ft": 0, "xl": 0, "pq": None}[d["ts"]]
        elif d["ts"] == "xl":
            vals["mtime"] = xl_serial(mtime, d.get("date1904", False))
        elif d["ts"] == "pq":
            vals["mtime"] = mtime
        else:
            tzname = cl.get("tz", "UTC") if d["ts"] in ("local", "iso") else "UTC"
            if cl.get("fs") == "FAT32" and d["ts"] in ("local", "iso"):
                tzname = "UTC"
            vals["mtime"] = ts_text(mtime, d["ts"], tzname, frac=d["frac"])
            if not typed and not isinstance(vals["mtime"], str):
                vals["mtime"] = str(vals["mtime"])
        mode = src.get("mode")
        if mode is not None:
            mk = d["mode"]
            vals["mode"] = mode_text(mode, {"mode_oct": d.get("octk", "oct"), "mode_sym": "sym", "mode_dec": "dec",
                                            "st_mode": "st"}[mk], is_link=e["etype"] == "L")
            if typed and mk == "mode_dec":
                vals["mode"] = mode
        else:
            vals["attrs"] = src.get("attrs") or ""
        own = src.get("owner")
        vals["owner"] = r.choice(["N/A", "-", "null"]) if e.get("sent_owner") else own
        if sha:
            if d["sha256"] == "digest":
                vals["sha256"] = "sha256:" + sha
            elif d["sha256"] == "content_hash":
                vals["sha256"] = sha.upper()
            else:
                vals["sha256"] = sha
        if container:
            vals["container"] = container if plant != "T13" else id_variant(r, container)
        if v is not None and "file_id" in v:
            vals["file_id"] = v["file_id"] if typed else str(v["file_id"])
    return [vals[f] for f in CAT_FIELDS]


NOISE_ROOTS = ["E:\\Data\\{s}", "/srv/{s}", "\\\\nas01\\{s}", "/Volumes/{s}"]


def noise_cat_entry(w: World, R: dict, r: Rng) -> dict:
    s = r.choice(R["noise_sets"])
    w.entry_seq_noise = getattr(w, "entry_seq_noise", 5_000_000) + r.randint(1, 3)
    root = r.choice(NOISE_ROOTS).format(s=s["share"].lower())
    sep = "\\" if root[1] == ":" or root.startswith("\\") else "/"
    path = root + sep + sep.join(_name(r, "").replace("/", "-") for _ in range(r.randint(1, 3))) + r.choice(EXTS)
    et = r.choice("FFFFFFDWR")
    v = {"size": int(math.exp(6 + r.random() * 9)), "mtime": s["snap"] - dt.timedelta(minutes=r.randint(1, 90000)),
         "sha": r.hexstr(64), "mode": r.choice([None, 0o644, 0o755]), "attrs": "A", "owner": f"S-1-5-21-{r.randint(10**9, 4 * 10**9)}-{r.randint(1000, 9999)}",
         "file_id": r.randint(10000, 9999999)}
    if v["mode"] is not None:
        v["owner"] = f"uid:{r.randint(1000, 1999)}"
    e = {"sid": s["sid"], "seq": r.randint(1, 4000), "eid": f"E-{w.entry_seq_noise:07d}", "etype": et, "path": path,
         "client": f"C{r.randint(5000, 99999)}", "committed": "Y", "noise": True, "v": v if et == "F" else None,
         "container": f"CT-{r.randint(8000000, 9999999)}" if et == "F" else None}
    if et in ("W", "R"):
        e["kind"] = "file"
    if et == "R":
        e["new"] = path + ".old"
    return e


def plan_slots(r: Rng, n: int, decoy: bool, fixed: int = 0) -> list[int]:
    bands = max(1, math.ceil(n / 500))
    k = r.randint(26, 30) if decoy else r.randint(12, 17)
    k = max(k - fixed, bands)
    slots = [min(n - 1, b * 500 + r.randint(0, 499)) for b in range(bands)]
    while len(slots) < k:
        slots.append(r.randint(0, n - 1))
    return sorted(set(slots))


ROW_FAMILIES = {
    "T1": "identifier normalisation (FMTGUIDE section 4)",
    "T9": "raw path canonicalisation (PATHCONV sections 2-3)",
    "T13": "container identifier normalisation and repack chain (MEDIAPROC section 3)",
}


def build_cat_files(w: World, R: dict, plan: list[tuple]) -> list[FileOut]:
    r = w.rng.fork("cat-files")
    p = w.p
    clients = {c["code"]: c for c in p["clients"]}
    share = [e for s in sorted(w.specs, key=lambda s: (s["snap"], s["sid"])) for e in w.entries[s["sid"]]]
    nparts = len(plan)
    chunks = [share[i * len(share) // nparts:(i + 1) * len(share) // nparts] for i in range(nparts)]
    outs = []
    for idx, (name, fmt) in enumerate(plan):
        part = f"{idx + 1:02d}"
        fo = FileOut(name, fmt, "CAT", part)
        d = cat_dialect(r, fmt)
        if fmt == "txt":
            d.update({f: f for f in CAT_FIELDS})
            d.update({"ts": "ft", "mode": "mode_oct", "size": "size", "locale": "plain"})
        d["octk"] = r.choice(["oct", "oct3"])
        d["yes"], d["no"] = r.choice([("Y", "N"), ("1", "0"), ("true", "false")])
        d["date1904"] = fmt == "xlsx" and r.chance(0.5)
        mine = list(chunks[idx])
        n = target_rows(p, r)
        rows = [("s", e) for e in mine] + [("n", noise_cat_entry(w, R, r)) for _ in range(max(0, n - len(mine)))]
        r.shuffle(rows)
        if part == "18":
            fo.opts["truncate"] = True
        fixed = 6
        slots = set(plan_slots(r, len(rows), False, fixed))
        drift_at = r.randint(len(rows) // 3, 2 * len(rows) // 3) if fmt not in ("json", "jsonl", "parquet") else None
        d2 = dict(d)
        if drift_at is not None and fmt == "txt":
            d2.update({"ts": "epoch", "mode": "mode_dec"})
        elif drift_at is not None:
            for f in r.sample(CAT_FIELDS, 4):
                d2[f] = r.choice(CAT_ALIASES[f])
            if fmt != "xlsx":
                d2["ts"] = r.choice([k for k in TS_KINDS if k != d["ts"]])
            fo.trap("header", "T8", "schema restatement lines restate the column set (FMTGUIDE section 2)", PLAN_CHECK)
        segs: list = []
        cur_cols = cat_columns(d)
        cur_rows: list = []
        layout = "A"
        for i, (kind, e) in enumerate(rows):
            if drift_at is not None and i == drift_at:
                segs.append((cur_cols, cur_rows))
                cur_cols, cur_rows = cat_columns(d2), []
                layout = "B"
            dd = d2 if (drift_at is not None and i >= drift_at) else d
            plant = None
            if i in slots and kind == "s":
                plant = r.choice(["T1", "T1", "T9", "T13"]) if e["etype"] == "F" else "T1"
                fo.trap(i, plant, ROW_FAMILIES[plant], PLAN_CHECK)
            elif i in slots:
                plant = "T1"
                fo.trap(i, "T1", ROW_FAMILIES["T1"], PLAN_CHECK)
            cur_rows.append(cat_cells(w, e, dd, fmt, r, plant, clients))
        segs.append((cur_cols, cur_rows))
        if fmt == "txt":
            fo.opts["layouts"] = ["A", "B"] if drift_at is not None else ["A"]
        fo.tables.append({"name": "entries", "segments": segs})
        fo.opts["dialect"] = d
        sem = {"T5": [], "T6": [], "T7": [], "T15": []}
        for i, (kind, e) in enumerate(rows):
            if kind != "s":
                continue
            if e.get("sent_mtime") or e.get("sent_owner"):
                sem["T5"].append(i)
            if e["etype"] == "X":
                sem["T6"].append(i)
            if e.get("corrupt") or e["committed"] == "N":
                sem["T7"].append(i)
            v = w.versions.get(e.get("vid")) if e["etype"] == "F" else None
            if v and (v["size"] > 20 * 1073741824 or v["mtime"] > w.rp):
                sem["T15"].append(i)
        rules = {"T5": "sentinel values (FMTGUIDE section 5)", "T6": "void entries (RESTORE-SPEC section 6.3)",
                 "T7": "catalog errata and uncommitted entries (RESTORE-SPEC sections 6.4 and 6.5)",
                 "T15": "outliers that are valid (RESTORE-SPEC section 12)"}
        for fam, idxs in sem.items():
            for i in idxs[:1]:
                fo.trap(i, fam, rules[fam], PLAN_CHECK)
        fo.records = sum(len(s[1]) for s in segs)
        enc = r.choice(["utf8", "bom", "latin1", "latin1"]) if fmt in ("csv", "tsv", "txt") else "utf8"
        fo.opts["encoding"] = enc
        if enc != "utf8":
            fo.trap("file", "T10", "encoding markers, byte order mark and line endings (FMTGUIDE section 3)", PLAN_CHECK)
        if d["locale"] != "plain":
            fo.trap("file", "T4", "locale digit grouping declared in the control block (FMTGUIDE section 6)", PLAN_CHECK)
        if d["ts"] in ("local", "iso", "ft", "ms", "xl"):
            fo.trap("file", "T3", "timestamp column kinds (FMTGUIDE section 7)", PLAN_CHECK)
        if d["size"] == "size_kib":
            fo.trap("file", "T2", "size_kib columns carry KiB (FMTGUIDE section 6)", PLAN_CHECK)
        fo.control["locale"] = d["locale"]
        fo.share_rows = [e for k, e in rows if k == "s"]
        outs.append(fo)
    return outs


# --------------------------------------------------------------------------- jobs, logs, calendar, mail


def _srv_tz(R: dict, name: str) -> str:
    return next(s["tz"] for s in R["servers"] if s["server"] == name)


def all_sets(w: World, R: dict) -> list[dict]:
    out = []
    for s in w.specs:
        out.append({"sid": s["sid"], "job_name": s["job_name"], "type": s["type"], "job_status": s["job_status"],
                    "server": s["server"], "queued": s["queued"], "snap": s["snap"], "ended": s["ended"],
                    "consolidates": w.specs[s["consolidates"]]["sid"] if s["type"] == "SYNTH" else "",
                    "client": (w.p["clients"][0] if s["era"] == 1 else w.p["clients"][1])["host"], "share": True,
                    "spec": s})
    for s in R["noise_sets"]:
        out.append({**s, "consolidates": "", "client": "", "share": False, "spec": None})
    return sorted(out, key=lambda s: (s["queued"], s["sid"]))


def build_job_files(w: World, R: dict, names: list[str]) -> list[FileOut]:
    r = w.rng.fork("jobs")
    sets = all_sets(w, R)
    n = len(sets)
    cuts = [0, n // 3, 2 * n // 3, n]
    kinds = [("local", "csv"), ("iso", "tsv"), ("utc", "tsv")]
    outs = []
    for i in range(3):
        fo = FileOut(names[i], kinds[i][1], "JOB", f"{i + 1:02d}")
        k = kinds[i][0]
        cols = ["set_id", "job_name", "set_type", f"queued_{k}", f"ended_{k}", "status", "server", "consolidates", "client_host"]
        rows = []
        chunk = sets[cuts[i]:cuts[i + 1]]
        slots = set(plan_slots(r, len(chunk), False, 3))
        for j, s in enumerate(chunk):
            tzn = _srv_tz(R, s["server"]) if k != "utc" else "UTC"
            sid, job = s["sid"], s["job_name"]
            if j in slots:
                if s["share"] or r.chance(0.5):
                    if r.chance(0.5):
                        sid = id_variant(r, sid)
                        fo.trap(j, "T1", "set identifier normalisation (FMTGUIDE section 4)", PLAN_CHECK)
                    else:
                        job = job.lower() if r.chance(0.5) else f" {job}"
                        fo.trap(j, "T1", "job names compare case-insensitively after trimming (RESTORE-SPEC section 5.1)", PLAN_CHECK)
                else:
                    fo.trap(j, "T11", "queued and ended times never decide the restore point (RESTORE-SPEC section 5.2)", PLAN_CHECK)
            rows.append([sid, job, s["type"], ts_text(s["queued"], k, tzn), ts_text(s["ended"], k, tzn), s["job_status"],
                         s["server"], s["consolidates"], s["client"]])
        fo.tables.append({"name": "jobs", "segments": [(cols, rows)]})
        fo.records = len(rows)
        fo.opts["encoding"] = ["bom", "latin1", "utf8"][i]
        fo.trap("file", "T3", "server-local job times (FMTGUIDE section 7)", PLAN_CHECK)
        fo.trap("file", "T10", "byte order mark and line endings (FMTGUIDE section 3)", PLAN_CHECK)
        outs.append(fo)
    # reporting copy (decoy): snapshot_time is the job end time; catalog_entries is the per-set control total
    fo = FileOut(names[3], "xlsx", "JOB", "00", status="REPORTING", decoy=True)
    fo.tables.append({"name": "About", "segments": [(["key", "value"], [
        ["report", "Backup job summary (BI warehouse extract)"],
        ["system_of_record", "no - reporting copy, see the source authority matrix"],
        ["snapshot_time", "reporting convention: the job end time, stored as an Excel serial in UTC"],
        ["catalog_entries", "number of catalog entries the catalog server recorded for the set, all parts and resends included"],
        ["status", "final job status as reported by the job engine"]])]})
    rows = []
    for j, s in enumerate(sets):
        rows.append([s["sid"], s["job_name"], s["type"], xl_serial(s["ended"], False), s["job_status"],
                     len(w.entries[s["sid"]]) if s["share"] else r.randint(5, 40), s["server"]])
    fo.tables.append({"name": "Sets", "segments": [(["set_id", "job_name", "set_type", "snapshot_time", "status",
                                                      "catalog_entries", "server"], rows)]})
    fo.records = len(rows) + 5
    share_rows = [j for j, s in enumerate(sets) if s["share"]]
    for j in share_rows[:8]:
        fo.trap(j, "T16", "reporting rows agree with the job history on set, type and status", PLAN_CHECK, "pull")
    for j in share_rows[8:14]:
        fo.trap(j, "T11", "snapshot_time here is the job end time (About sheet; AUTH row set.snapshot)", PLAN_CHECK, "pull")
    for j in share_rows[14:18]:
        fo.trap(j, "T7", "status here ignores catalog-check overrides from the server log", PLAN_CHECK, "pull")
    for j in share_rows[18:22]:
        fo.trap(j, "T6", "failed and cancelled sets still listed with their catalog totals", PLAN_CHECK, "push")
    for j in share_rows[22:25]:
        fo.trap(j, "T13", "job names are the original names: renamed jobs need the crosswalk", PLAN_CHECK, "push")
    fo.trap("About", "T14", "About sheet declares the copy non-authoritative", PLAN_CHECK, "push")
    fo.trap("Sets", "T3", "Excel serial date system of this workbook", PLAN_CHECK, "push")
    fo.trap("Sets", "T5", "catalog_entries is the only per-set control total", PLAN_CHECK, "push")
    outs.append(fo)
    return outs


def log_ts(t: dt.datetime, server: str, R: dict, mirror: bool = False) -> str:
    if mirror:
        return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%MZ")
    tzn = _srv_tz(R, server)
    stamp = "local"
    for b in sorted((b for b in R["builds"] if b["server"] == server), key=lambda b: b["installed"]):
        if b["installed"] <= t:
            stamp = b["stamp"]
    lt = t.astimezone(ZoneInfo(tzn))
    if stamp == "local":
        return lt.strftime("%Y-%m-%d %H:%M:%S")
    off = lt.strftime("%z")
    return lt.strftime("%Y-%m-%dT%H:%M:%S") + off[:3] + ":" + off[3:]


def log_events(w: World, R: dict, server: str) -> list[tuple[dt.datetime, str, str, str]]:
    r = w.rng.fork("log-" + server)
    out = []
    for s in all_sets(w, R):
        if s["server"] != server or (not s["share"] and r.chance(0.72)):
            continue
        out.append((s["queued"], "INFO", "jobmgr", f"job {s['job_name']} queued set={s['sid']} type={s['type']}"))
        if s["type"] == "SYNTH":
            out.append((s["queued"] + dt.timedelta(seconds=40), "INFO", "synth", f"synthetic full set={s['sid']} consolidates={s['consolidates']} started"))
        elif s["share"] or s["job_status"] != "CANCELLED" or r.chance(0.5):
            out.append((s["snap"], "INFO", "vss", f"snapshot {{{r.hexstr(8)}-{r.hexstr(4)}}} created set={s['sid']}"))
        out.append((s["ended"], "INFO" if s["job_status"] == "COMPLETED" else "ERROR", "jobmgr",
                    f"set={s['sid']} finished status={s['job_status']}"))
        sp = s["spec"]
        if sp is not None and sp["override"] == "PARTIAL":
            out.append((s["ended"] + dt.timedelta(minutes=r.randint(3, 40)), "WARN", "catalog-check",
                        f"set={s['sid']} status changed COMPLETED -> PARTIAL ({r.randint(3, 40)} objects not committed)"))
        if sp is None and s["job_status"] == "COMPLETED" and r.chance(0.04):
            out.append((s["ended"] + dt.timedelta(minutes=5), "WARN", "catalog-check",
                        f"set={s['sid']} status changed COMPLETED -> PARTIAL ({r.randint(3, 40)} objects not committed)"))
    return out


def build_log_files(w: World, R: dict, names: list[str]) -> list[FileOut]:
    r = w.rng.fork("logs")
    p = w.p
    old, new = p["srv_old"][0], p["srv_new"][0]
    gap_set = next(s for s in w.specs if s.get("log_gap"))
    gap_day = local_wall(gap_set["snap"], _srv_tz(R, new)).date()
    g0 = from_wall(dt.datetime.combine(gap_day, dt.time(0, 0)), _srv_tz(R, new))
    g1 = g0 + dt.timedelta(days=1)
    R["log_gap"] = (g0, g1)

    def filler(t0, t1, server, n):
        out = []
        span = int((t1 - t0).total_seconds())
        for _ in range(n):
            t = t0 + dt.timedelta(seconds=r.randint(0, span))
            out.append((t, "DEBUG", r.choice(["heartbeat", "scheduler", "mediamgr", "dedup"]),
                        r.choice([f"queue depth {r.randint(0, 90)}", f"drive {r.randint(1, 8)} idle",
                                  f"dedup ratio {r.randint(110, 690) / 100}", f"mount request MD-{r.randint(20000, 29999)} ok"])))
        return out

    w0 = from_wall(dt.datetime.combine(dt.date.fromisoformat(p["w0"]), dt.time(0, 0)), p["site_tz"]) - dt.timedelta(days=2)
    w1 = w.rp + dt.timedelta(days=4)
    outs = []
    ev_old = log_events(w, R, old)
    ev_new = log_events(w, R, new)
    plans = [(names[0], old, ev_old, None, None), (names[1], new, [e for e in ev_new if e[0] < g0], None, "rotated"),
             (names[2], new, [e for e in ev_new if e[0] >= g1], None, None)]
    for idx, (name, server, evs, _, role) in enumerate(plans):
        fo = FileOut(name, "log", "LOG", f"{idx + 1:02d}")
        lo = min(e[0] for e in evs) if evs else w0
        hi = max(e[0] for e in evs) if evs else w1
        need = max(0, target_rows(p, r) - len(evs) - 1)
        lines = sorted(evs + filler(lo, hi, server, need), key=lambda e: e[0])
        text = [f"{log_ts(t, server, R)} {server} {lvl} [{comp}] {msg}" for t, lvl, comp, msg in lines]
        if role == "rotated":
            text.append(f"{log_ts(g1 - dt.timedelta(seconds=1), server, R)} {server} WARN [logrotate] lines from "
                        f"{iso_z(g0)} to {iso_z(g1)} were not retained; the console mirror holds that window")
            fo.trap(len(text) - 1, "T14", "rotation footer declares the gap window (AUTH row set.snapshot)", PLAN_CHECK)
        fo.tables.append({"name": "lines", "segments": [([], [[x] for x in text])]})
        fo.records = len(text)
        fo.opts["encoding"] = "utf8"
        slots = plan_slots(r, len(text), False, 2)
        for s_ in slots:
            fo.trap(s_, r.choice(["T3", "T11", "T15"]), "server log timestamps: build-dependent notation, server time zone, repeated hour resolves to the first occurrence (FMTGUIDE section 7)", PLAN_CHECK)
        fo.trap("file", "T5", "snapshot lines are the snapshot time of record (AUTH row set.snapshot)", PLAN_CHECK)
        outs.append(fo)
    # console mirror (decoy): UTC, minute precision, whole range of the new server
    fo = FileOut(names[3], "log", "LOG", "00", status="MIRROR", decoy=True)
    lines = sorted(ev_new + filler(min(e[0] for e in ev_new), max(e[0] for e in ev_new), new, max(0, target_rows(p, r) - len(ev_new))),
                   key=lambda e: e[0])
    text = [f"{log_ts(t, new, R, mirror=True)} {new} {lvl} [{comp}] {msg}" for t, lvl, comp, msg in lines]
    fo.tables.append({"name": "lines", "segments": [([], [[x] for x in text])]})
    fo.records = len(text)
    vss = [i for i, x in enumerate(text) if "snapshot {" in x]
    for i in vss[:10]:
        fo.trap(i, "T16", "mirror lines agree with the server log apart from minute truncation", PLAN_CHECK, "pull")
    for i in vss[10:16]:
        fo.trap(i, "T3", "mirror times are UTC truncated to the minute", PLAN_CHECK, "push")
    over = [i for i, x in enumerate(text) if "status changed" in x]
    for i in over[:3]:
        fo.trap(i, "T7", "overrides repeated from the server log", PLAN_CHECK, "pull")
    for i in r.sample(range(len(text)), 4):
        fo.trap(i, "T6", "cancelled jobs without snapshot lines", PLAN_CHECK, "push")
    for i in r.sample(range(len(text)), 3):
        fo.trap(i, "T13", "set identifiers without job names", PLAN_CHECK, "push")
    outs.append(fo)
    # storage array event log: actual maintenance windows by calendar UID
    fo = FileOut(names[4], "log", "LOG", "04")
    evs = []
    for ev in R["events"]:
        if ev["actual"]:
            a, b = ev["actual"]
            evs.append((a, f"{ev['array']} maintenance uid={ev['uid']} actual-start"))
            evs.append((b, f"{ev['array']} maintenance uid={ev['uid']} actual-end"))
    for ev in r.sample([e for e in R["events"] if e["array"] != p["array"] and e["status"] == "CONFIRMED"], min(400, len(R["events"]) // 10)):
        a = ev["start"] + dt.timedelta(minutes=r.randint(-20, 20))
        evs.append((a, f"{ev['array']} maintenance uid={ev['uid']} actual-start"))
        evs.append((a + dt.timedelta(minutes=r.randint(20, 200)), f"{ev['array']} maintenance uid={ev['uid']} actual-end"))
    while len(evs) < target_rows(p, r):
        t = w0 + dt.timedelta(seconds=r.randint(0, int((w1 - w0).total_seconds())))
        evs.append((t, f"{r.choice(ARRAYS)} snapshot-group SG-{r.randint(100, 999)} {r.choice(['consistent', 'replicated', 'pruned'])}"))
    evs.sort(key=lambda e: e[0])
    text = [f"{t.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]}Z {msg}" for t, msg in evs]
    fo.tables.append({"name": "lines", "segments": [([], [[x] for x in text])]})
    fo.records = len(text)
    for s_ in plan_slots(r, len(text), False, 1):
        fo.trap(s_, r.choice(["T11", "T13", "T3"]), "actual windows override the planned calendar window for the same UID (RESTORE-SPEC section 5.4)", PLAN_CHECK)
    fo.trap("file", "T14", "array log is the record of actual windows", PLAN_CHECK)
    outs.append(fo)
    return outs


def build_cal_mail_jobdef(w: World, R: dict, names: list[str]) -> list[FileOut]:
    r = w.rng.fork("calmail")
    p = w.p
    outs = []
    fo = FileOut(names[0], "ics", "CAL", "01")
    evs = []
    for i, ev in enumerate(R["events"]):
        evs.append(ev)
    r.shuffle(evs)
    fo.tables.append({"name": "events", "segments": [([], evs)]})
    fo.records = len(evs)
    fo.opts["tz"] = p["site_tz"]
    for i, ev in enumerate(evs):
        if ev["array"] == p["array"]:
            fam = "T11" if ev.get("edge") else "T6" if ev["status"] == "CANCELLED" else "T3"
            fo.trap(i, fam, "maintenance windows are half-open and only CONFIRMED SNAPSHOT-CONSISTENCY events count (RESTORE-SPEC section 5.4)", PLAN_CHECK)
    for s_ in plan_slots(r, len(evs), False, len(fo.traps))[: max(0, 14 - len(fo.traps))]:
        fo.trap(s_, r.choice(["T13", "T1"]), "events name arrays; the share's array comes from the share registry", PLAN_CHECK)
    outs.append(fo)
    # vault notifications
    fo = FileOut(names[1], "mbox", "MAIL", "01")
    req_end = R["req_end"]
    msgs = []
    for x in R["recalls"]:
        msgs.append({"date": x["at"], "subject": f"Recall completed: {x['media']}", "kind": "recall", "media": x["media"],
                     "body": f"Media {x['media']} was recalled and checked in at {x['to']}.\nCourier ref {r.randint(100000, 999999)}."})
    for x in R["destroy"]:
        msgs.append({"date": x["date"], "subject": f"Destruction notice: {x['media']}", "kind": "destroy", "media": x["media"],
                     "body": f"Media {x['media']} was destroyed under certificate DC-{r.randint(1000, 9999)}.\nThe media is no longer readable."})
    msgs.append({"date": req_end - dt.timedelta(days=2), "subject": "Checksum rerun request CHK-RERUN-" + str(r.randint(100, 999)),
                 "kind": "rerun", "body": "Please rerun the checksum audit for the following container copies:\n"
                 + "\n".join(f"{c} copy 1" for c in R["ticketed"]) + "\nResults of the rerun replace the first audit for these copies only."})
    while len(msgs) < target_rows(p, r):
        t = req_end - dt.timedelta(days=r.randint(0, 50), minutes=r.randint(0, 1440))
        m = f"MD-{r.randint(20000, 39999)}"
        k = r.choice(["recall", "report", "report", "destroy", "ticket"])
        if k == "recall":
            msgs.append({"date": t, "subject": f"Recall completed: {m}", "kind": k, "media": m,
                         "body": f"Media {m} was recalled and checked in at {r.choice(VAULTS)}."})
        elif k == "destroy":
            msgs.append({"date": t, "subject": f"Destruction notice: {m}", "kind": k, "media": m,
                         "body": f"Media {m} was destroyed under certificate DC-{r.randint(1000, 9999)}."})
        elif k == "ticket":
            msgs.append({"date": t, "subject": f"Checksum rerun request CHK-RERUN-{r.randint(100, 999)}", "kind": "rerun",
                         "body": f"Please rerun the checksum audit for the following container copies:\nCT-{r.randint(8000000, 9999999)} copy {r.randint(1, 3)}"})
        else:
            msgs.append({"date": t, "subject": f"Daily vault report {r.choice(VAULTS)}", "kind": k,
                         "body": f"{r.randint(10, 900)} media on site, {r.randint(0, 20)} in transit."})
    r.shuffle(msgs)
    fo.tables.append({"name": "messages", "segments": [([], msgs)]})
    fo.records = len(msgs)
    for i, m in enumerate(msgs):
        if m.get("media") in R["media_share"] or (m["kind"] == "rerun" and any(c in m["body"] for c in R["ticketed"])):
            fo.trap(i, "T11" if m["kind"] == "destroy" else "T14", "notices take effect at their Date header, only up to the end of the request date (MEDIAPROC section 4)", PLAN_CHECK)
    for s_ in plan_slots(r, len(msgs), False, len(fo.traps))[: max(0, 15 - len(fo.traps))]:
        fo.trap(s_, "T3", "RFC 2822 dates carry their own offsets", PLAN_CHECK)
    outs.append(fo)
    # job definitions
    fo = FileOut(names[2], "xml", "JOBDEF", "01")
    rows = [[j["job"], j["share"], j["server"], j["status"]] for j in R["jobdefs"]]
    r.shuffle(rows)
    fo.tables.append({"name": "jobs", "segments": [(["name", "share", "server", "status"], rows)]})
    fo.records = len(rows)
    for i, row in enumerate(rows):
        if row[0] in (p["job_new"], p["job_old"]):
            fo.trap(i, "T13", "retired jobs carry no share; renamed jobs resolve through the crosswalk (RESTORE-SPEC section 5.1)", PLAN_CHECK)
    for s_ in plan_slots(r, len(rows), False, 2)[:13]:
        fo.trap(s_, "T1", "job and share identifiers compare case-insensitively", PLAN_CHECK)
    outs.append(fo)
    return outs


def _fill_traps(fo: FileOut, r: Rng, n: int, fams: list[str], rule: str, test: str, want: int | None = None) -> None:
    want = want if want is not None else (r.randint(26, 29) if fo.decoy else r.randint(11, 15))
    for s_ in plan_slots(r, n, fo.decoy, 0):
        if len(fo.traps) >= want:
            break
        fo.trap(s_, r.choice(fams), rule, test, r.choice(["pull", "push"]) if fo.decoy else "")


def build_registers_files(w: World, R: dict, names: dict) -> list[FileOut]:
    r = w.rng.fork("regfiles")
    p = w.p
    outs = []
    # host register (yaml): OS and time zone of record
    fo = FileOut(names["host"], "yaml", "HOST", "01")
    rows = [{"host": h["host"], "os": h["os"], "tz": h["tz"]} for h in R["hosts"]]
    r.shuffle(rows)
    for x in rows:
        if x["host"] in {c["host"] for c in p["clients"]} and r.chance(0.5):
            x["host"] = x["host"].lower()
    fo.tables.append({"name": "hosts", "segments": [([], rows)]})
    fo.records = len(rows)
    _fill_traps(fo, r, len(rows), ["T1", "T3"], "host names compare case-insensitively; tz is the IANA zone of record (AUTH row host.tz)", PLAN_CHECK)
    outs.append(fo)
    # CMDB export (decoy): stale time zones, but the only file-system type of record
    fo = FileOut(names["cmdb"], "yaml", "HOST", "00", status="CMDB-EXPORT", decoy=True)
    rows = []
    for h in R["hosts"]:
        rows.append({"hostname": h["host"].upper(), "platform": {"windows": "Windows Server", "linux": "Linux", "macos": "macOS"}[h["os"]],
                     "timezone": R["cmdb_tz"].get(h["host"], h["tz"] if r.chance(0.97) else r.choice(SITE_TZ)), "filesystem": h["fs"]})
    r.shuffle(rows)
    fo.tables.append({"name": "hosts", "segments": [([], rows)]})
    fo.records = len(rows)
    for i, x in enumerate(rows):
        if x["hostname"] in {c["host"].upper() for c in p["clients"]}:
            fo.trap(i, "T16" if x["timezone"] == next(c["tz"] for c in p["clients"] if c["host"].upper() == x["hostname"]) else "T3",
                    "CMDB time zones are not of record; filesystem is (AUTH rows host.tz and host.fs)", PLAN_CHECK, "pull")
    _fill_traps(fo, r, len(rows), ["T16", "T6", "T7", "T13", "T1"], "CMDB export rows agree with the host register on most hosts", PLAN_CHECK)
    outs.append(fo)
    # backup servers and agent builds (yaml)
    fo = FileOut(names["servers"], "yaml", "SRV", "01")
    rows = []
    for s in R["servers"]:
        rows.append({"name": s["server"], "role": "backup-server", "tz": s["tz"], "site": s["site"],
                     "builds": [{"build": b["build"], "installed": iso_z(b["installed"]), "log_timestamps": b["stamp"]}
                                for b in R["builds"] if b["server"] == s["server"]]})
    while len(rows) < target_rows(p, r):
        rows.append({"name": f"PRX-{r.randint(1000, 9999)}", "role": "proxy", "tz": r.choice(SITE_TZ), "site": r.choice(["FRA", "EWR", "BOM", "SIN"]),
                     "builds": [{"build": f"7.{r.randint(0, 3)}.{r.randint(0, 9)}", "installed": iso_z(R["req_end"] - dt.timedelta(days=r.randint(10, 400))),
                                 "log_timestamps": r.choice(["local", "offset"])}]})
    r.shuffle(rows)
    fo.tables.append({"name": "servers", "segments": [([], rows)]})
    fo.records = len(rows)
    fo.trap("servers", "T11", "a build applies from its installed instant onwards (FMTGUIDE section 7)", PLAN_CHECK)
    _fill_traps(fo, r, len(rows), ["T3", "T1"], "server time zone and log timestamp notation by build", PLAN_CHECK)
    outs.append(fo)
    # share registry (yaml)
    fo = FileOut(names["sharereg"], "yaml", "SHARE", "01")
    rows = [{"share": s["share"], "aliases": s["aliases"], "array": s["array"], "site_tz": s["tz"], "case_policy": s["case"]}
            for s in R["share_reg"]]
    r.shuffle(rows)
    fo.tables.append({"name": "shares", "segments": [([], rows)]})
    fo.records = len(rows)
    _fill_traps(fo, r, len(rows), ["T1", "T13", "T3"], "share id, array and site zone of record", PLAN_CHECK)
    outs.append(fo)
    # share roots (ini)
    fo = FileOut(names["roots"], "ini", "ROOT", "01")
    rows = [[f"root.{i + 1:05d}", x["host"], x["share"], x["root"]] for i, x in enumerate(R["roots"])]
    r.shuffle(rows)
    fo.tables.append({"name": "roots", "segments": [(["section", "host", "share", "path"], rows)]})
    fo.records = len(rows)
    _fill_traps(fo, r, len(rows), ["T1", "T9"], "roots compare case-insensitively on Windows hosts (PATHCONV section 2)", PLAN_CHECK)
    outs.append(fo)
    # vault slots (ini): vault of record as of the window start
    fo = FileOut(names["slots"], "ini", "SLOT", "01")
    rows = [[f"slot.{i + 1:05d}", m, v] for i, (m, v) in enumerate(sorted(R["slots"].items()))]
    while len(rows) < target_rows(p, r):
        rows.append([f"slot.{len(rows) + 1:05d}", f"MD-{r.randint(20000, 39999)}", r.choice(VAULTS)])
    r.shuffle(rows)
    fo.tables.append({"name": "slots", "segments": [(["section", "media", "vault"], rows)]})
    fo.records = len(rows)
    _fill_traps(fo, r, len(rows), ["T7", "T1", "T11"], "slot vault is the baseline; transfers and recalls move media later (MEDIAPROC section 4)", PLAN_CHECK)
    outs.append(fo)
    # local accounts (ini)
    fo = FileOut(names["lacct"], "ini", "LACCT", "01")
    rows = []
    for host, accts in sorted(R["local_accounts"].items()):
        for uid, a in sorted(accts.items()):
            rows.append([f"host:{host}", str(uid), a])
    seen_acct = {(a, b) for a, b, _ in rows}
    while len(rows) < target_rows(p, r):
        k = (f"host:{r.choice(R['hosts'][4:])['host']}", str(r.randint(1000, 1999)))
        if k in seen_acct:
            continue
        seen_acct.add(k)
        rows.append([k[0], k[1], f"user{r.randint(100, 999)}"])
    fo.tables.append({"name": "accounts", "segments": [(["section", "uid", "account"], rows)]})
    fo.records = len(rows)
    _fill_traps(fo, r, len(rows), ["T1", "T13"], "uids are host-scoped (RESTORE-SPEC section 9.3)", PLAN_CHECK)
    outs.append(fo)
    # restore targets (toml)
    fo = FileOut(names["vol"], "toml", "VOL", "01")
    rows = [{"id": p["target_volume"], "small_cluster": p["cluster_small"], "large_cluster": p["cluster_large"],
             "large_threshold": p["large_threshold"], "resident_max": p["resident_max"]}]
    while len(rows) < target_rows(p, r):
        rows.append({"id": f"VOL-{r.randint(100, 999)}-{r.choice(R['shares'][1:]).replace('-', '')}{r.choice('NOX')}",
                     "small_cluster": r.choice([4096, 8192, 16384]), "large_cluster": r.choice([65536, 131072, 262144]),
                     "large_threshold": r.choice([1048576, 4194304, 16777216]), "resident_max": r.choice([0, 640, 700, 720])})
    r.shuffle(rows)
    fo.tables.append({"name": "volume", "segments": [([], rows)]})
    fo.records = len(rows)
    _fill_traps(fo, r, len(rows), ["T12", "T2", "T1"], "allocation rounds up to whole clusters (RESTORE-SPEC section 10)", PLAN_CHECK)
    outs.append(fo)
    # exclusion catalogue r8 (toml) and r9 (decoy toml)
    rp_date = local_wall(w.rp, p["site_tz"]).date()
    pats = list(R["patterns_share"])
    while len(pats) < target_rows(p, r):
        pats.append({"id": f"EX-{r.randint(6000, 99999)}", "pattern": r.choice(["*.iso", "*.vhd", "/Archive/**", "*.mp4", "~*", "*.part", "cache/"]),
                     "scope": r.choice(R["shares"][1:]), "from": (rp_date - dt.timedelta(days=r.randint(1, 900))).isoformat(), "to": ""})
    r.shuffle(pats)
    fo = FileOut(names["excl8"], "toml", "EXCL", "08")
    fo.control["revision"] = "8"
    fo.tables.append({"name": "pattern", "segments": [([], pats)]})
    fo.records = len(pats)
    for i, x in enumerate(pats):
        if x in R["patterns_share"]:
            fo.trap(i, r.choice(["T11", "T14", "T9"]), "patterns in force at the restore point date, section 7 dialect", PLAN_CHECK)
    outs.append(fo)
    fo = FileOut(names["excl9"], "toml", "EXCL", "09", decoy=True)
    fo.control["revision"] = "9"
    fo.control["effective_from"] = (rp_date + dt.timedelta(days=3)).isoformat()
    p9 = [dict(x) for x in pats]
    for x in r.sample(p9, max(3, len(p9) // 50)):
        x["pattern"] = x["pattern"] + "*"
    p9 += R["patterns_v9_new"]
    fo.tables.append({"name": "pattern", "segments": [([], p9)]})
    wd = list(R["withdraw_v9"])
    while len(wd) < 30:
        wd.append({"id": f"EX-{r.randint(6000, 99999)}", "effective": (rp_date - dt.timedelta(days=r.randint(1, 60))).isoformat(), "cab": f"CAB-{r.randint(3000, 3999)}"})
    fo.tables.append({"name": "withdrawal", "segments": [([], wd)]})
    fo.records = len(p9) + len(wd)
    fo.trap("catalogue", "T11", "revision 9 is in force only from its effective date (RESTORE-SPEC section 7.4)", PLAN_CHECK, "push")
    for i in range(2):
        fo.trap(f"withdrawal:{i}", "T6", "withdrawals take effect on their own effective date (RESTORE-SPEC section 7.4)", PLAN_CHECK, "push")
    fo.trap("pattern:new", "T7", "new revision-9 patterns are not yet in force", PLAN_CHECK, "pull")
    _fill_traps(fo, r, len(p9), ["T16", "T7", "T13", "T6", "T1", "T11"], "revision 9 agrees with revision 8 on most patterns", PLAN_CHECK)
    outs.append(fo)
    return outs


def build_media_files(w: World, R: dict, names: dict) -> list[FileOut]:
    r = w.rng.fork("mediafiles")
    p = w.p
    req_end = R["req_end"]
    outs = []
    lto = [m for m in R["media"] if m["kind"] == "LTO"]
    other = [m for m in R["media"] if m["kind"] != "LTO"]

    def noise_media(kind):
        return {"media": f"MD-{r.randint(20000, 39999)}", "kind": kind, "gen": r.choice(["LTO-6", "LTO-7", "LTO-8", "LTO-9"]) if kind == "LTO" else "-",
                "home": r.choice(VAULTS), "status": r.choice(["ACTIVE"] * 8 + ["EXPIRED", "SCRATCH"]), "status_date": "2026-03-01",
                "barcode": f"BC{r.randint(100000, 999999)}"}

    inv1 = lto + [noise_media("LTO") for _ in range(max(0, target_rows(p, r) - len(lto)))]
    inv2 = other + [noise_media(r.choice(["DISK", "CLOUD"])) for _ in range(max(0, target_rows(p, r) - len(other)))]
    for name, rows, sheets in ((names["inv1"], inv1, ["LTO"]), (names["inv2"], inv2, ["DISK", "CLOUD"])):
        fo = FileOut(name, "xlsx", "MEDIA", "01" if sheets == ["LTO"] else "02")
        r.shuffle(rows)
        for sh in sheets:
            sel = [m for m in rows if (m["kind"] == sh)]
            cols = ["media_id", "generation", "home_vault", "status", "status_date"] if sh == "LTO" else ["media_id", "kind", "home_vault", "status", "status_date"]
            data = [[m["media"], m["gen"] if sh == "LTO" else m["kind"], m["home"], m["status"],
                     xl_serial(dt.datetime.fromisoformat(m["status_date"]).replace(tzinfo=UTC), False)] for m in sel]
            fo.tables.append({"name": sh, "segments": [(cols, data)]})
        fo.records = sum(len(t["segments"][0][1]) for t in fo.tables)
        fo.trap(sheets[0], "T8", "sheet headers differ between media kinds", PLAN_CHECK)
        _fill_traps(fo, r, fo.records, ["T1", "T5", "T14", "T3"], "status EXPIRED and generation LTO-6 make a copy unusable (MEDIAPROC sections 2 and 5)", PLAN_CHECK)
        outs.append(fo)
    # planning preview (decoy): stale statuses, but the only barcode crosswalk
    fo = FileOut(names["preview"], "xlsx", "MEDIA", "00", status="PREVIEW", decoy=True)
    fo.tables.append({"name": "About", "segments": [(["key", "value"], [["extract", "media planning preview"],
                      ["status_columns", "planning snapshot only; statuses and vaults are not of record"],
                      ["barcode", "label printed on the cartridge or volume; container maps reference copy-2 media by this label"]])]})
    rows = []
    allm = inv1 + inv2
    for m in allm:
        st = m["status"] if r.chance(0.96) else r.choice(["ACTIVE", "EXPIRED"])
        if m["media"] in R["media_share"] and m["status"] == "EXPIRED":
            st = "ACTIVE"
        rows.append([m["media"], m.get("barcode", ""), m["home"] if r.chance(0.9) else r.choice(VAULTS), st])
    r.shuffle(rows)
    fo.tables.append({"name": "Media", "segments": [(["media_id", "barcode", "vault", "status"], rows)]})
    fo.records = len(rows) + 3
    for i, row in enumerate(rows):
        if row[0] in R["media_share"] and len(fo.traps) < 12:
            fo.trap(i, r.choice(["T16", "T7"]), "preview statuses are not of record (AUTH row media.status)", PLAN_CHECK, "pull")
    fo.trap("About", "T14", "About sheet declares the planning status", PLAN_CHECK, "push")
    _fill_traps(fo, r, len(rows), ["T13", "T6", "T1", "T16", "T7"], "barcode crosswalk for copy-2 media (MEDIAPROC section 3)", PLAN_CHECK, 28)
    outs.append(fo)
    # container maps
    share_rows = []
    bc = {m["media"]: m.get("barcode") for m in R["media"]}
    for c, rows_ in sorted(R["copies"].items()):
        if c.startswith("RC-"):
            continue
        for x in rows_:
            share_rows.append({"container": c, "copy": x["copy"], "media_ref": bc[x["media"]] if x["copy"] == 2 else x["media"],
                               "size": x["size"], "created": x["created"]})
    n_each = len(share_rows) // 3 + 1
    for i in range(3):
        mine = share_rows[i * n_each:(i + 1) * n_each]
        while len(mine) < target_rows(p, r):
            mine.append({"container": f"CT-{r.randint(8000000, 9999999)}", "copy": r.randint(1, 3), "media_ref": f"MD-{r.randint(20000, 39999)}",
                         "size": r.randint(10**6, 10**11), "created": req_end - dt.timedelta(days=r.randint(1, 80))})
        r.shuffle(mine)
        fo = FileOut(names[f"cmap{i + 1}"], "parquet", "CMAP", f"{i + 1:02d}")
        fo.opts["cmap_kind"] = i
        fo.control["locale"] = "de_DE" if i == 2 else "plain"
        fo.tables.append({"name": "containers", "segments": [([], mine)]})
        fo.records = len(mine)
        if i == 2:
            fo.trap("size_text", "T4", "size_text uses the control-block locale (FMTGUIDE section 6)", PLAN_CHECK)
        _fill_traps(fo, r, len(mine), ["T1", "T13", "T2", "T12"], "container sizes and copy media references (MEDIAPROC section 3)", PLAN_CHECK)
        outs.append(fo)
    fo = FileOut(names["cmap_v2"], "parquet", "CMAP", "00", status="FINAL", decoy=True)
    fo.opts["cmap_kind"] = 9
    v2 = []
    for x in share_rows:
        y = dict(x)
        if r.chance(0.04):
            y["size"] = x["size"] + r.randint(-9000, 9000)
        v2.append(y)
    for c, rows_ in R["copies"].items():
        if c.startswith("RC-"):
            for x in rows_:
                v2.append({"container": c, "copy": x["copy"], "media_ref": bc[x["media"]] if x["copy"] == 2 else x["media"],
                           "size": x["size"], "created": x["created"]})
    while len(v2) < target_rows(p, r):
        v2.append({"container": f"CT-{r.randint(8000000, 9999999)}", "copy": 1, "media_ref": f"MD-{r.randint(20000, 39999)}",
                   "size": r.randint(10**6, 10**11), "created": req_end - dt.timedelta(days=r.randint(1, 80))})
    r.shuffle(v2)
    fo.control["note"] = "migration test export; only RC- containers written by the repack job are recorded here alone"
    fo.tables.append({"name": "containers", "segments": [([], v2)]})
    fo.records = len(v2)
    for i, x in enumerate(v2):
        if x["container"].startswith("RC-") and len(fo.traps) < 6:
            fo.trap(i, "T13", "repacked containers exist only in this export (AUTH row container.size)", PLAN_CHECK, "push")
    _fill_traps(fo, r, len(v2), ["T16", "T7", "T6", "T12", "T2", "T1"], "v2 sizes are not of record for CT- containers", PLAN_CHECK, 28)
    outs.append(fo)
    # repack journal (sqlite)
    fo = FileOut(names["repack"], "sqlite", "REPACK", "01")
    rows = [[x["old"], x["new"], iso_z(x["at"])] for x in R["repack"]]
    while len(rows) < target_rows(p, r):
        rows.append([f"CT-{r.randint(8000000, 9999999)}", f"RC-{r.randint(1000000, 9999999)}", iso_z(req_end - dt.timedelta(days=r.randint(0, 60)))])
    r.shuffle(rows)
    fo.tables.append({"name": "repack", "segments": [(["old_container", "new_container", "repacked_at"], rows)]})
    fo.records = len(rows)
    _fill_traps(fo, r, len(rows), ["T11", "T13", "T1"], "a repack counts only when repacked_at is at or before the end of the request date", PLAN_CHECK)
    outs.append(fo)
    # checksum audit and rerun
    fo = FileOut(names["chk"], "csv", "CHK", "01")
    rows = [[c["container"], str(c["copy"]), c["expected"], c["observed"], c["result"], iso_z(c["at"])] for c in R["chk_share"]]
    while len(rows) < target_rows(p, r):
        h = r.hexstr(32)
        rows.append([f"CT-{r.randint(8000000, 9999999)}", str(r.randint(1, 3)), h, h, "MATCH", iso_z(req_end - dt.timedelta(days=r.randint(1, 20)))])
    r.shuffle(rows)
    fo.tables.append({"name": "audit", "segments": [(["container", "copy", "expected_md5", "observed_md5", "result", "audited_utc"], rows)]})
    fo.records = len(rows)
    fo.opts["encoding"] = "bom"
    _fill_traps(fo, r, len(rows), ["T1", "T5", "T10", "T13"], "MISMATCH makes that copy unusable (MEDIAPROC section 2)", PLAN_CHECK)
    outs.append(fo)
    fo = FileOut(names["rerun"], "tsv", "CHK", "00", status="RERUN", decoy=True)
    rows = [[c["container"], str(c["copy"]), c["result"], iso_z(c["at"])] for c in R["rerun_share"]]
    while len(rows) < target_rows(p, r):
        rows.append([f"CT-{r.randint(8000000, 9999999)}", str(r.randint(1, 3)), r.choice(["MATCH", "MISMATCH"]), iso_z(req_end - dt.timedelta(hours=r.randint(1, 80)))])
    r.shuffle(rows)
    fo.tables.append({"name": "rerun", "segments": [(["container", "copy", "result", "audited_utc"], rows)]})
    fo.records = len(rows)
    for i, row in enumerate(rows):
        if row[0] in w.containers:
            fo.trap(i, "T7" if row[0] in R["ticketed"] else "T16", "rerun results count only for copies named in a rerun request (MEDIAPROC section 2)", PLAN_CHECK, "pull")
    _fill_traps(fo, r, len(rows), ["T6", "T13", "T1", "T16", "T7", "T10"], "rerun rows outside the ticket are not of record", PLAN_CHECK, 28)
    outs.append(fo)
    return outs


def build_av_id_files(w: World, R: dict, names: dict) -> list[FileOut]:
    r = w.rng.fork("avfiles")
    p = w.p
    req_end = R["req_end"]
    outs = []
    eng = R["engines"]
    final = list(R["av_final_share"])
    sql_part = [f for f in final if r.chance(0.3)]
    for f in sql_part:
        f["engine"] = eng[2]["code"]
    rest = [f for f in final if f not in sql_part]

    def noise_find(code):
        return {"sha": r.hexstr(64), "container": f"CT-{r.randint(8000000, 9999999)}", "verdict": r.choice(["CLEAN"] * 6 + ["INFECTED", "PUA"]),
                "sig": r.choice(SIGS), "rev": r.randint(1, 60), "engine": code, "at": req_end - dt.timedelta(days=r.randint(0, 9), minutes=r.randint(0, 1400))}

    halves = [rest[: len(rest) // 2], rest[len(rest) // 2:]]
    fid = [r.randint(100000, 200000)]

    def rows_of(lst):
        out = []
        for f in lst:
            fid[0] += r.randint(1, 4)
            out.append({"finding_id": f"F-{fid[0]}", "sha256": f["sha"] if r.chance(0.8) else f["sha"].upper(), "container": f["container"],
                        "verdict": f["verdict"], "signature": f["sig"] if f["verdict"] != "CLEAN" else "", "sig_rev": f["rev"],
                        "engine": f["engine"], "scanned_utc": iso_z(f["at"])})
        return out

    for i in range(2):
        lst = halves[i] + [noise_find(eng[0]["code"]) for _ in range(max(0, target_rows(p, r) - len(halves[i])))]
        r.shuffle(lst)
        fo = FileOut(names[f"av{i + 1}"], "jsonl", "AV", f"{i + 1:02d}")
        fo.tables.append({"name": "findings", "segments": [([], rows_of(lst))]})
        fo.records = len(lst)
        _fill_traps(fo, r, len(lst), ["T1", "T6", "T15", "T11"], "infected unless withdrawn; PUA is not quarantined (QPROC sections 2-3)", PLAN_CHECK)
        outs.append(fo)
    lst = sql_part + [noise_find(eng[2]["code"]) for _ in range(max(0, target_rows(p, r) - len(sql_part)))]
    r.shuffle(lst)
    fo = FileOut(names["av3"], "sqlite", "AV", "03")
    rows = rows_of(lst)
    fo.tables.append({"name": "findings", "segments": [(list(rows[0]), [list(x.values()) for x in rows])]})
    fo.records = len(rows)
    _fill_traps(fo, r, len(rows), ["T1", "T13", "T6"], "engine codes map to vendors through the engine registry (QPROC appendix A)", PLAN_CHECK)
    outs.append(fo)
    lst = list(R["av_prelim_share"]) + [noise_find(eng[1]["code"]) for _ in range(max(0, target_rows(p, r) - len(R["av_prelim_share"])))]
    r.shuffle(lst)
    fo = FileOut(names["avpre"], "jsonl", "AV", "00", status="PRELIMINARY", decoy=True)
    fo.tables.append({"name": "findings", "segments": [([], rows_of(lst))]})
    fo.records = len(lst)
    for i, f in enumerate(lst):
        if f in R["av_prelim_share"] and len(fo.traps) < 14:
            fo.trap(i, "T7" if w.containers[f["container"]]["created"] >= R["av_cutover"] else "T13",
                    "the preliminary scan is of record only for containers created before the engine cutover (QPROC section 2)", PLAN_CHECK,
                    "pull" if w.containers[f["container"]]["created"] >= R["av_cutover"] else "push")
    _fill_traps(fo, r, len(lst), ["T16", "T6", "T7", "T13", "T11", "T1"], "preliminary detections later cleared", PLAN_CHECK, 28)
    outs.append(fo)
    # identity map (sqlite) and AD export (decoy sqlite)
    fo = FileOut(names["idmap"], "sqlite", "IDMAP", "01")
    rows = [[x["principal"], x["account"], iso_z(x["from"]), iso_z(x["to"]) if x["to"] else None] for x in R["idmap_share"]]
    while len(rows) < target_rows(p, r):
        rows.append([f"S-1-5-21-{r.randint(10**9, 4 * 10**9)}-{r.randint(10**9, 4 * 10**9)}-{r.randint(10**8, 10**9)}-{r.randint(1000, 9999)}",
                     f"user{r.randint(1000, 9999)}", "2024-01-01T00:00:00Z", None])
    r.shuffle(rows)
    fo.tables.append({"name": "accounts", "segments": [(["principal", "account", "valid_from", "valid_to"], rows)]})
    fo.records = len(rows)
    _fill_traps(fo, r, len(rows), ["T11", "T7", "T1"], "validity is half-open [valid_from, valid_to) at the restore point (RESTORE-SPEC section 9.3)", PLAN_CHECK)
    outs.append(fo)
    fo = FileOut(names["ad"], "sqlite", "IDMAP", "00", status="EXPORT", decoy=True)
    rows = [[sid, f"corp\\{a}", iso_z(req_end + dt.timedelta(days=2))] for sid, a in sorted(R["ad_names"].items())]
    rows += [[sid, a, iso_z(req_end + dt.timedelta(days=2))] for sid, a in sorted(R["legacy_accounts"].items())]
    while len(rows) < target_rows(p, r):
        rows.append([f"S-1-5-21-{r.randint(10**9, 4 * 10**9)}-{r.randint(1000, 9999)}", f"corp\\user{r.randint(1000, 9999)}", iso_z(req_end + dt.timedelta(days=2))])
    r.shuffle(rows)
    fo.tables.append({"name": "ad_users", "segments": [(["sid", "account", "exported_utc"], rows)]})
    fo.tables.append({"name": "export_info", "segments": [(["key", "value"], [["purpose", "helpdesk directory export, current names"],
                      ["authority", "of record only for the LEGACY domain, which the identity map does not carry"]])]})
    fo.records = len(rows) + 2
    for i, row in enumerate(rows):
        if row[0] in R["legacy_accounts"] and len(fo.traps) < 8:
            fo.trap(i, "T13", "legacy-domain SIDs resolve only here (AUTH row owner.account)", PLAN_CHECK, "push")
    _fill_traps(fo, r, len(rows), ["T16", "T7", "T11", "T6", "T1"], "current names, not names at the restore point", PLAN_CHECK, 28)
    outs.append(fo)
    return outs


# --------------------------------------------------------------------------- byte writers
import csv as _csvmod


def control_line(fo: FileOut) -> str:
    c = {"feed": fo.control["feed"], "stream": fo.stream, "part": fo.part, "of": fo.control["of"], "status": fo.status,
         "records": str(fo.control["records"]), "custody": fo.control["custody"]}
    for k, v in fo.control.items():
        if k not in c and k not in ("feed", "of", "records", "custody"):
            c[k] = str(v)
    return " ".join(f"{k}={v.replace(' ', '_') if k != 'note' else v.replace(' ', '_')}" for k, v in c.items())


def control_dict(fo: FileOut) -> dict:
    return dict(item.split("=", 1) for item in control_line(fo).split(" "))


def _cell_text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return repr(v)
    return str(v)


def tsv_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def write_delimited(fo: FileOut, delim: str, r: Rng) -> bytes:
    enc = fo.opts.get("encoding", "utf8")
    nl = "\r\n" if enc == "crlf" else "\n"

    def line(cells) -> str:
        cells = [_cell_text(c) for c in cells]
        if delim == "\t":
            return "\t".join(tsv_escape(c) for c in cells)
        buf = io.StringIO()
        _csvmod.writer(buf, lineterminator="").writerow(cells)
        return buf.getvalue()

    chunks: list[tuple[str, str]] = [("utf-8", "#control " + control_line(fo))]
    first = True
    for t in fo.tables:
        for cols, rows in t["segments"]:
            if first:
                chunks.append(("utf-8", line(cols)))
                first = False
            else:
                chunks.append(("utf-8", "#schema " + line(cols)))
            body = [line(row) + ("," if delim == "," and r.chance(0.01) else "") for row in rows]
            if enc == "latin1" and len(body) > 200:
                a = r.randint(len(body) // 4, len(body) // 2)
                b = a + len(body) // 5
                block = [x for x in body[a:b] if _latin1_ok(x)]
                spill = [x for x in body[a:b] if not _latin1_ok(x)]
                body = body[:a] + ["#encoding latin-1"] + block + ["#encoding utf-8"] + spill + body[b:]
            enc_now = "utf-8"
            for x in body:
                if x == "#encoding latin-1":
                    chunks.append(("utf-8", x))
                    enc_now = "latin-1"
                    continue
                if x == "#encoding utf-8":
                    enc_now = "utf-8"
                chunks.append((enc_now, x))
    out = bytearray(b"\xef\xbb\xbf" if enc == "bom" else b"")
    for e, x in chunks:
        out += (x + nl).encode(e)
    return bytes(out)


def _latin1_ok(s: str) -> bool:
    try:
        s.encode("latin-1")
        return True
    except UnicodeEncodeError:
        return False


def write_txt(fo: FileOut) -> bytes:
    lines = ["#control " + control_line(fo)]
    names = fo.opts.get("layouts", ["A"])
    for (cols, rows), lay in zip(fo.tables[0]["segments"], names):
        lines.append(f"#layout {lay}")
        spec = FIXED_LAYOUTS[lay]
        idx = {c: i for i, c in enumerate(cols)}
        for row in rows:
            out = ""
            for name, width in spec:
                key = name
                if name.startswith("mtime"):
                    key = next(c for c in cols if c.startswith("mtime"))
                if name.startswith("mode"):
                    key = next(c for c in cols if c.startswith("mode"))
                val = _cell_text(row[idx[key]])
                if len(val) > width - 1:
                    raise ValueError(f"fixed-width overflow {name}: {val!r}")
                out += val.ljust(width)
            lines.append(out.rstrip())
    return ("\n".join(lines) + "\n").encode("utf-8")


def write_jsonl(fo: FileOut) -> bytes:
    lines = [json.dumps({"control": control_dict(fo)}, ensure_ascii=False)]
    for t in fo.tables:
        for cols, rows in t["segments"]:
            for row in rows:
                obj = row if isinstance(row, dict) else {c: v for c, v in zip(cols, row) if v not in ("", None)}
                lines.append(json.dumps(obj, ensure_ascii=False, default=str))
    return ("\n".join(lines) + "\n").encode("utf-8")


def write_json(fo: FileOut) -> bytes:
    doc = {"control": control_dict(fo)}
    for t in fo.tables:
        items = []
        for cols, rows in t["segments"]:
            for row in rows:
                items.append(row if isinstance(row, dict) else {c: v for c, v in zip(cols, row) if v not in ("", None)})
        doc[t["name"]] = items
    return (json.dumps(doc, ensure_ascii=False, indent=1, default=str) + "\n").encode("utf-8")


def write_xml(fo: FileOut) -> bytes:
    root = fo.tables[0]["name"]
    out = ['<?xml version="1.0" encoding="UTF-8"?>', f"<{root}>",
           "  <control " + " ".join(f'{k}="{_xesc(v, {chr(34): "&quot;"})}"' for k, v in control_dict(fo).items()) + "/>"]
    item = {"entries": "entry", "jobs": "job"}.get(root, "row")
    for cols, rows in fo.tables[0]["segments"]:
        for row in rows:
            if item == "job":
                out.append("  <job " + " ".join(f'{c}="{_xesc(_cell_text(v), {chr(34): "&quot;"})}"' for c, v in zip(cols, row)) + "/>")
                continue
            parts = [f"<{c}>{_xesc(_cell_text(v))}</{c}>" for c, v in zip(cols, row) if v not in ("", None)]
            out.append(f"  <{item}>" + "".join(parts) + f"</{item}>")
    out.append(f"</{root}>")
    return ("\n".join(out) + "\n").encode("utf-8")


def write_parquet(fo: FileOut) -> bytes:
    import pyarrow as pa
    import pyarrow.parquet as pq
    t = fo.tables[0]
    if fo.stream == "CMAP":
        rows = t["segments"][0][1]
        kind = fo.opts.get("cmap_kind", 0)
        cols = {"container": pa.array([x["container"] for x in rows], pa.string()),
                "copy": pa.array([x["copy"] for x in rows], pa.int8() if kind != 1 else pa.int64()),
                "media_ref": pa.array([x["media_ref"] for x in rows], pa.string())}
        if kind == 2:
            cols["size_text"] = pa.array([group_int(x["size"], "de_DE") for x in rows], pa.string())
        else:
            cols["size_bytes"] = pa.array([x["size"] for x in rows], pa.int64())
        if kind == 1:
            cols["created_ms"] = pa.array([(x["created"] - EPOCH) // dt.timedelta(milliseconds=1) for x in rows], pa.int64())
        else:
            cols["created"] = pa.array([x["created"].astimezone(UTC) for x in rows], pa.timestamp("us", tz="UTC"))
        table = pa.table(cols)
    else:
        cols, rows = t["segments"][0]
        arrays = {}
        for i, c in enumerate(cols):
            vals = [row[i] for row in rows]
            vals = [None if v == "" else v for v in vals]
            nn = [v for v in vals if v is not None]
            if nn and all(isinstance(v, dt.datetime) for v in nn):
                arrays[c] = pa.array(vals, pa.timestamp("us", tz="UTC"))
            elif nn and all(isinstance(v, bool) is False and isinstance(v, int) for v in nn):
                arrays[c] = pa.array(vals, pa.int64())
            elif nn and all(isinstance(v, (int, float)) for v in nn):
                arrays[c] = pa.array([None if v is None else float(v) for v in vals], pa.float64())
            else:
                arrays[c] = pa.array([None if v is None else str(v) for v in vals], pa.string())
        table = pa.table(arrays)
    md = {b"restore-control": control_line(fo).encode()}
    table = table.replace_schema_metadata(md)
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="snappy", use_dictionary=False, write_statistics=False)
    return buf.getvalue()


def write_sqlite(fo: FileOut, path: Path) -> None:
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE _control (key TEXT PRIMARY KEY, value TEXT)")
    con.executemany("INSERT INTO _control VALUES (?, ?)", list(control_dict(fo).items()))
    for t in fo.tables:
        cols, rows = t["segments"][0]
        con.execute(f"CREATE TABLE {t['name']} (" + ", ".join(f'"{c}"' for c in cols) + ")")
        con.executemany(f"INSERT INTO {t['name']} VALUES (" + ",".join("?" * len(cols)) + ")", rows)
    con.commit()
    con.execute("VACUUM")
    con.close()


def write_log(fo: FileOut) -> bytes:
    nl = "\r\n" if fo.opts.get("encoding") == "crlf" else "\n"
    lines = ["#control " + control_line(fo)] + [row[0] for row in fo.tables[0]["segments"][0][1]]
    return (nl.join(lines) + nl).encode("utf-8")


def write_yaml(fo: FileOut) -> bytes:
    import yaml
    doc = {"control": control_dict(fo)}
    for t in fo.tables:
        doc[t["name"]] = t["segments"][0][1]
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=200).encode("utf-8")


def _toml_val(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    return json.dumps(str(v), ensure_ascii=False)


def write_toml(fo: FileOut) -> bytes:
    lines = ["[control]"] + [f"{k} = {_toml_val(v)}" for k, v in control_dict(fo).items()] + [""]
    for t in fo.tables:
        for row in t["segments"][0][1]:
            lines.append(f"[[{t['name']}]]")
            for k, v in row.items():
                lines.append(f"{k} = {_toml_val(v)}")
            lines.append("")
    return "\n".join(lines).encode("utf-8")


def write_ini(fo: FileOut) -> bytes:
    lines = ["[control]"] + [f"{k} = {v}" for k, v in control_dict(fo).items()] + [""]
    cols, rows = fo.tables[0]["segments"][0]
    if fo.stream == "LACCT":
        cur = None
        for sec, uid, acct in sorted(rows, key=lambda x: (x[0], int(x[1]))):
            if sec != cur:
                lines += ["", f"[{sec}]"]
                cur = sec
            lines.append(f"{uid} = {acct}")
    else:
        for row in rows:
            lines.append(f"[{row[0]}]")
            for c, v in zip(cols[1:], row[1:]):
                lines.append(f"{c} = {v}")
            lines.append("")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _ics_fold(line: str) -> str:
    b = line.encode("utf-8")
    if len(b) <= 75:
        return line
    out, cur = [], ""
    for ch in line:
        if len((cur + ch).encode("utf-8")) > (75 if not out else 74):
            out.append(cur)
            cur = ch
        else:
            cur += ch
    out.append(cur)
    return "\n ".join(out)


def write_ics(fo: FileOut, r: Rng) -> bytes:
    tz = fo.opts["tz"]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//corp//storage-ops//EN", "X-RESTORE-CONTROL:" + control_line(fo)]
    for ev in fo.tables[0]["segments"][0][1]:
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{ev['uid']}")
        lines.append("DTSTAMP:" + ev["start"].astimezone(UTC).strftime("%Y%m%dT%H%M%SZ"))
        if r.chance(0.5):
            lines.append(f"DTSTART;TZID={tz}:" + local_wall(ev["start"], tz).strftime("%Y%m%dT%H%M%S"))
            lines.append(f"DTEND;TZID={tz}:" + local_wall(ev["end"], tz).strftime("%Y%m%dT%H%M%S"))
        else:
            lines.append("DTSTART:" + ev["start"].astimezone(UTC).strftime("%Y%m%dT%H%M%SZ"))
            lines.append("DTEND:" + ev["end"].astimezone(UTC).strftime("%Y%m%dT%H%M%SZ"))
        lines.append(f"SUMMARY:Maintenance window {ev['array']} - firmware and controller work")
        lines.append(f"STATUS:{ev['status']}")
        lines.append(f"X-ARRAY:{ev['array']}")
        lines.append(f"X-IMPACT:{ev['impact']}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return ("\n".join(_ics_fold(x) for x in lines) + "\n").encode("utf-8")


def write_mbox(fo: FileOut) -> bytes:
    import email.utils as eu
    out = []

    def msg(date: dt.datetime, subject: str, body: str, extra: str = "") -> None:
        out.append("From vault-ops@corp.example " + date.astimezone(UTC).strftime("%a %b %d %H:%M:%S %Y"))
        lt = date.astimezone(ZoneInfo("Europe/London" if date.minute % 2 else "America/New_York"))
        out.append("From: Vault Operations <vault-ops@corp.example>")
        out.append("To: storage-restore@corp.example")
        out.append("Date: " + eu.format_datetime(lt))
        out.append("Subject: " + subject)
        if extra:
            out.append(extra)
        out.append("")
        for ln in body.split("\n"):
            out.append((">" + ln) if ln.startswith("From ") else ln)
        out.append("")

    msg(dt.datetime(2026, 1, 1, tzinfo=UTC), "feed control", "control message for this mailbox export",
        "X-Restore-Control: " + control_line(fo))
    for m in fo.tables[0]["segments"][0][1]:
        msg(m["date"], m["subject"], m["body"])
    return ("\n".join(out) + "\n").encode("utf-8")


# ---- xlsx (raw OOXML: inline strings, typed numbers)


def _col(n: int) -> str:
    s = ""
    n += 1
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def _xml_text(s: str) -> str:
    s = "".join(ch for ch in s if ch in "\t\n\r" or ord(ch) >= 32)
    return _xesc(s)


def write_xlsx(fo: FileOut, date1904: bool) -> bytes:
    sheets = [("_control", [["key", "value"]] + [[k, v] for k, v in control_dict(fo).items()])]
    for t in fo.tables:
        for i, (cols, rows) in enumerate(t["segments"]):
            sheets.append((t["name"] if i == 0 else f"{t['name']}_{i + 1}", [cols] + rows))
    buf = io.BytesIO()
    z = zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED)

    def put(name: str, data: str) -> None:
        zi = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, data)

    put("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + "".join(f'<Override PartName="/xl/worksheets/sheet{i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                  for i in range(len(sheets))) + "</Types>")
    put("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>")
    put("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        + (f'<workbookPr date1904="1"/>' if date1904 else "<workbookPr/>") + "<sheets>"
        + "".join(f'<sheet name="{_xesc(n)}" sheetId="{i + 1}" r:id="rId{i + 1}"/>' for i, (n, _) in enumerate(sheets))
        + "</sheets></workbook>")
    put("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i + 1}.xml"/>'
                  for i in range(len(sheets))) + "</Relationships>")
    for si, (_, rows) in enumerate(sheets):
        parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
        for ri, row in enumerate(rows):
            cells = []
            for ci, v in enumerate(row):
                ref = f"{_col(ci)}{ri + 1}"
                if v is None or v == "":
                    continue
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    cells.append(f'<c r="{ref}"><v>{repr(v) if isinstance(v, float) else v}</v></c>')
                else:
                    cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{_xml_text(str(v))}</t></is></c>')
            parts.append(f'<row r="{ri + 1}">' + "".join(cells) + "</row>")
        parts.append("</sheetData></worksheet>")
        put(f"xl/worksheets/sheet{si + 1}.xml", "".join(parts))
    z.close()
    return buf.getvalue()


# ---- documents


def doc_records(fo: FileOut) -> int:
    return sum(len(b[3]) for b in fo.doc if b[0] == "table")


def write_md(fo: FileOut) -> bytes:
    out = [f"<!-- restore-control: {control_line(fo)} -->", ""]
    for b in fo.doc:
        if b[0] == "h":
            out += ["#" * b[1] + " " + b[2], ""]
        elif b[0] == "p":
            out += [b[1], ""]
        else:
            _, cap, cols, rows = b
            out += [f"**Table: {cap}**", "", "| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
            out += ["| " + " | ".join(_cell_text(c).replace("|", "\\|") for c in row) + " |" for row in rows]
            out.append("")
    return ("\n".join(out)).encode("utf-8")


def write_html(fo: FileOut) -> bytes:
    title = next((b[2] for b in fo.doc if b[0] == "h"), fo.name)
    out = ["<!DOCTYPE html>", "<html lang=\"en\"><head><meta charset=\"utf-8\">",
           f'<meta name="restore-control" content="{_xesc(control_line(fo))}">', f"<title>{_xesc(title)}</title></head><body>"]
    for b in fo.doc:
        if b[0] == "h":
            out.append(f"<h{b[1]}>{_xesc(b[2])}</h{b[1]}>")
        elif b[0] == "p":
            out.append(f"<p>{_xesc(b[1])}</p>")
        else:
            _, cap, cols, rows = b
            out.append(f"<table><caption>{_xesc(cap)}</caption><thead><tr>" + "".join(f"<th>{_xesc(c)}</th>" for c in cols) + "</tr></thead><tbody>")
            for row in rows:
                out.append("<tr>" + "".join(f"<td>{_xesc(_cell_text(c))}</td>" for c in row) + "</tr>")
            out.append("</tbody></table>")
    out.append("</body></html>")
    return ("\n".join(out) + "\n").encode("utf-8")


W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _w_par(text: str, style: str | None = None) -> str:
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{_xml_text(text)}</w:t></w:r></w:p>'


def write_docx(fo: FileOut) -> bytes:
    body = [_w_par("CONTROL " + control_line(fo))]
    for b in fo.doc:
        if b[0] == "h":
            body.append(_w_par(b[2], f"Heading{b[1]}"))
        elif b[0] == "p":
            body.append(_w_par(b[1]))
        else:
            _, cap, cols, rows = b
            body.append(_w_par(f"Table: {cap}", "Caption"))
            t = ['<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/></w:tblPr>']
            for row in [cols] + rows:
                t.append("<w:tr>" + "".join(f'<w:tc><w:p><w:r><w:t xml:space="preserve">{_xml_text(_cell_text(c))}</w:t></w:r></w:p></w:tc>'
                                            for c in row) + "</w:tr>")
            t.append("</w:tbl>")
            body.append("".join(t))
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W_NS}><w:body>' + "".join(body)
           + "<w:sectPr/></w:body></w:document>")
    styles = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {W_NS}>'
              + "".join(f'<w:style w:type="paragraph" w:styleId="{s}"><w:name w:val="{n}"/></w:style>'
                        for s, n in (("Heading1", "heading 1"), ("Heading2", "heading 2"), ("Heading3", "heading 3"), ("Caption", "caption")))
              + '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/></w:style></w:styles>')
    buf = io.BytesIO()
    z = zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED)

    def put(name, data):
        zi = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(zi, data)

    put("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        "</Types>")
    put("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>")
    put("word/_rels/document.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        "</Relationships>")
    put("word/document.xml", doc)
    put("word/styles.xml", styles)
    z.close()
    return buf.getvalue()


def _pdf_esc(s: str) -> str:
    s = s.encode("ascii", "replace").decode("ascii")
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(text: str, width: int = 140) -> list[str]:
    words, out, cur = text.split(" "), [], ""
    for wd in words:
        if len(cur) + len(wd) + 1 > width and cur:
            out.append(cur)
            cur = wd
        else:
            cur = (cur + " " + wd) if cur else wd
    if cur:
        out.append(cur)
    return out


def pdf_lines(fo: FileOut) -> list[list[str]]:
    per = 90
    pages: list[list[str]] = []
    cur: list[str] = ["CONTROL " + control_line(fo)]
    header: str | None = None

    def push(line: str) -> None:
        nonlocal cur
        if len(cur) >= per:
            pages.append(cur)
            cur = []
            if header is not None:
                cur.append(header + " (continued)")
        cur.append(line)

    for b in fo.doc:
        if b[0] == "h":
            header = None
            push("")
            push(b[2].upper() if b[1] == 1 else b[2])
        elif b[0] == "p":
            header = None
            for ln in _wrap(b[1]):
                push(ln)
        else:
            _, cap, cols, rows = b
            push(f"TABLE {cap}")
            header = " | ".join(cols)
            push(header)
            for row in rows:
                push(" | ".join(_cell_text(c) or "-" for c in row))
            header = None
            push("END TABLE")
    pages.append(cur)
    return pages


def write_pdf(fo: FileOut) -> bytes:
    pages = pdf_lines(fo)
    n = len(pages)
    objs: list[bytes] = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n))
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
    for i, lines in enumerate(pages):
        lines = lines + [f"Page {i + 1} of {n}"]
        y = 820
        ops = []
        for ln in lines:
            ops.append(f"BT /F1 6 Tf 20 {y} Td ({_pdf_esc(ln)}) Tj ET")
            y -= 8.6
        stream = zlib.compress("\n".join(ops).encode("latin-1"), 9)
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>".encode())
        objs.append(f"<< /Length {len(stream)} /Filter /FlateDecode >>\nstream\n".encode() + stream + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offs = []
    for i, o in enumerate(objs):
        offs.append(len(out))
        out += f"{i + 1} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for o in offs:
        out += f"{o:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


# --------------------------------------------------------------------------- documents: rule text

SPEC42 = [
    ("h", 1, "Point-in-time Restore Specification - revision 4.2"),
    ("h", 2, "1. Status and authority"),
    ("p", "This revision is approved; the document control register is the only authority on which revision of any document is in force, never revision numbers, file dates or file names. A restore feed is governed by this specification together with the documents it incorporates: the feed readme (stream README), the catalog format guide (stream FMTGUIDE), the path conventions (stream PATHCONV), the media handling procedure (stream MEDIAPROC), the quarantine procedure (stream QPROC), the source authority matrix (stream AUTH) and the restore request (stream RRQ)."),
    ("p", "Sections 7.1 to 7.3 (pattern dialect) and section 9.2 (timestamp conversion) of revision 4.1 are carried forward unchanged and are not restated here. Every other part of revision 4.1 is superseded."),
    ("p", "Where two sources state the same fact, the source authority matrix decides which one is of record. A source the matrix does not rank for a fact is never used for that fact, even when it is the newest or the most complete file in the feed."),
    ("h", 2, "2. The restore"),
    ("p", "The restore request names the feed, the share, the restore point and the request date. The restore point is a wall-clock time in the site time zone of the share (share registry, site_tz); when that wall time occurs twice, the first occurrence is meant. The end of the request date is 23:59:59 wall-clock time in the site time zone on the request date. The restore point date is the local site date of the restore point."),
    ("h", 2, "5. Backup set chain"),
    ("p", "5.1 Sets of the share. A set belongs to the share when its job name, trimmed of surrounding white space and compared case-insensitively, is a job that the job definitions assign to the share. A retired job definition carries no share. A set run under an old job name belongs to the share when the job rename crosswalk maps that old name to a job of the share and the set was queued before the crosswalk row's effective date (local site date)."),
    ("p", "5.2 Snapshot time. The snapshot time of a set is the instant of the snapshot line for that set in the log of the backup server that ran it (a line of the form 'snapshot {guid} created set=<set>'). Job queued and ended times are never snapshot times. A synthetic full (set type SYNTH) has no snapshot of its own: its snapshot time is the snapshot time of the set named in its consolidates column. The backup server register gives each server's time zone and, per agent build, the time notation its log uses from the build's installed instant onwards."),
    ("p", "5.3 Status. The status of a set is its job history status, replaced by the latest catalog-check status change recorded for the set in the server log."),
    ("p", "5.4 Crash-inconsistent snapshots. A set is crash-inconsistent when its snapshot instant lies inside a maintenance window of the share's array (share registry) whose STATUS is CONFIRMED and whose X-IMPACT is SNAPSHOT-CONSISTENCY. A window includes its start and excludes its end. When the storage array event log records actual-start and actual-end for the event's UID, that actual window replaces the calendar window."),
    ("p", "5.5 Chain selection. Sets are ordered by snapshot time, ties by set identifier. A set is eligible when its snapshot time is at or before the restore point, its status is COMPLETED or PARTIAL and it is not crash-inconsistent. The base is the latest eligible FULL or SYNTH set. The differential is the latest eligible DIFF set whose snapshot is after the base, if any. The anchor is the differential, or the base when there is none. Every eligible INCR set after the anchor is applied in order, until a crash-inconsistent set after the anchor breaks the chain: no set after a break is applied. FAILED and CANCELLED sets never break the chain, because the next incremental is taken relative to the last set that completed. The effective point is the snapshot time of the last applied set."),
    ("p", "5.6 Skipped sets. Every set of the share that is not applied is skipped with exactly one reason, the first that holds in this order: AFTER_RP (snapshot after the restore point), FAILED, CANCELLED, CRASH_INCONSISTENT, BEFORE_BASE (snapshot at or before the base snapshot), SUPERSEDED_BY_DIFF (snapshot at or before the anchor snapshot), CHAIN_BROKEN."),
    ("h", 2, "6. Catalog replay"),
    ("p", "6.1 Order. Entries of the applied sets are applied set by set in chain order and, within a set, in ascending seq. Entries are gathered from every catalog part of the feed; a set's entries may be spread over several parts, and parts list entries in no particular order."),
    ("p", "6.2 Entry types. Identity of objects and the spelling rule are those of PATHCONV section 6. D creates a directory when it is absent and changes nothing otherwise. F replaces the version of an existing file and keeps its spelling; on an absent path it creates the file. H creates a file at path that shares the current version of the file at target. L creates a symbolic link at path whose raw target is target. W removes the object at path; with kind dir it removes the directory and everything under it. R moves the object at path to new_path; with kind dir it moves the directory and everything under it. X voids another entry of the same set (section 6.3)."),
    ("p", "6.3 Voids. An X entry names in its voids column the entry identifier it voids. A voided entry is not applied. The X entry and the entry it voids may be recorded in different parts."),
    ("p", "6.4 Catalog errata. A correction in a catalog errata document replaces one field (sha256, size, mtime or container) of one entry before replay. Only corrections with status APPROVED in an errata revision in force apply; when several apply to the same entry and field, the one from the highest errata revision wins. Corrected values are written as lowercase hexadecimal, a byte count, an ISO 8601 UTC time and a canonical container identifier; a correction whose value is not written in that form is malformed and never applies, whatever its status or revision."),
    ("p", "6.5 Uncommitted entries. An entry whose committed flag is false was not committed by its set and is not applied."),
    ("p", "6.6 Rejected entries. An entry whose raw path is not under one of the client's roots for the share, or whose path climbs above the share root, is rejected and not applied (PATHCONV section 3)."),
    ("h", 2, "7. Exclusion patterns"),
    ("p", "7.4 Catalogue revision. The exclusion catalogue in force is the revision with the highest number whose effective_from is on or before the restore point date. Its patterns apply when their scope is ALL or the share, their effective_from is on or before the restore point date and their retired_from is empty or after it. A pattern listed in the withdrawal register of any catalogue revision stops applying from the withdrawal's effective date, whichever revision is in force."),
    ("h", 2, "8. Scope and exclusions"),
    ("p", "Every file and symbolic link that exists at the effective point is either restored or excluded, never both. The first reason that holds, in this order, excludes it: OUT_OF_SCOPE (the path is not at or under one of the include prefixes of the share's restore profile in Appendix B; prefixes match whole components, case-insensitively), DISPOSED (the path is at or under the prefix of a records disposition with action DESTROY whose effective date is on or before the restore point date; detail is the lowest such hold identifier), EXCLUDED_PATTERN (a pattern in force matches the display path; detail is the matching pattern with the lowest identifier number), SYMLINK_ESCAPE (a link whose target leaves the share, PATHCONV section 5), QUARANTINED (QPROC section 4; detail is the sha256 of the version at the effective point), UNRECOVERABLE (no usable copy, MEDIAPROC section 2; detail is the container identifier after repack). Directories are neither restored nor excluded."),
    ("h", 2, "9. Version metadata"),
    ("p", "9.1 Mode. The restored mode is the permission bits of the restored entry with the set-user-ID and set-group-ID bits cleared and the sticky bit kept, written as four octal digits. Entries from Windows clients carry attributes instead of a mode: 0444 when the attributes contain R, 0644 otherwise."),
    ("p", "9.3 Owner. A principal of the form uid:<n> is resolved in the local account register under the section of the host of the restored entry's client. Any other principal is resolved through the latest approved identity change effective at or before the restore point, otherwise through the identity map row valid at the restore point (valid_from included, valid_to excluded). A principal that nothing resolves, or an owner sentinel, gives UNMAPPED."),
    ("h", 2, "10. Allocation"),
    ("p", "Allocation is computed for the restore target volume named in the restore request (restore target register). A file of size at most resident_max allocates 0 bytes. Otherwise the size is rounded up to a whole number of clusters, using large_cluster when the size is at least large_threshold and small_cluster otherwise. Within a hard-link group only the first member in output order allocates; the others allocate 0. Symbolic links allocate 0."),
    ("h", 2, "11. Deliverables"),
    ("p", "11.1 CSV files are UTF-8 without a byte order mark, with LF line endings, a header row and RFC 4180 quoting (a field is quoted only when it contains a comma, a double quote, CR or LF; embedded quotes are doubled). The last line of each CSV file is a trailer '#custody=<digest> rows=<n>' where digest is the feed custody digest (README section 6) and n the number of data rows. Rows of the manifest and of the exclusions are ordered by the Unicode code points of the case-folded NFC display path, ties by the display path itself."),
    ("p", "11.2 restore_manifest.csv has the columns path, kind, size, allocated, sha256, mode, mtime_utc, owner, source_set, container, media, copy, hardlink_group, link_target. path is the display path at the effective point; kind is file or symlink; size is in bytes; sha256 is lowercase hexadecimal; mtime_utc is YYYY-MM-DDTHH:MM:SSZ; source_set is the set of the entry whose version is restored; container is the container after repack; media and copy are the media and copy number chosen; hardlink_group is HL- followed by four digits, numbered from 0001 in output order of each group's first member, for files whose restored versions share client and file_id with at least one other restored file; link_target is the resolved target of a symbolic link. Fields that do not apply to a symbolic link (sha256, container, media, hardlink_group) are empty, its size, allocated and copy are 0. Fields that do not apply to a file (link_target) are empty."),
    ("p", "11.3 exclusions.csv has the columns path, kind, reason, detail; detail is empty for OUT_OF_SCOPE and SYMLINK_ESCAPE. 11.4 media_pull_list.csv has the columns media_id, vault, copy, containers, read_bytes, read_gib: one row per media holding a chosen copy, containers counted once each, read_bytes the sum of their sizes, read_gib that sum divided by 1073741824 rounded half to even to three decimals, written with exactly three decimals. Rows are ordered by the vault priority of MEDIAPROC Appendix E on the request date, then media_id."),
    ("p", "11.5 Both JSON files are UTF-8 objects whose keys appear exactly in the order listed here, at every level. restore_chain.json has the keys share, restore_point_utc, effective_point_utc, chain (applied sets in order, each an object with the keys set, type, snapshot_utc and role, role being base, diff or incremental), skipped (each skipped set as an object with the keys set, type, snapshot_utc and reason, ordered by snapshot then set) and custody_digest. 11.6 reconciliation.json has the keys sets (one object per applied set in chain order with the keys set, expected, entries, applied, voided, uncommitted and rejected), objects_at_effective_point, restored, excluded (an object whose keys are the six reasons in the order of section 8, zero included), rolled_back (files restored from an earlier entry under QPROC section 4), bytes_restored (sum of restored sizes), bytes_allocated (sum of allocations), hardlink_groups, media, containers and read_bytes (the pull list's row count, container total and byte total) and custody_digest. expected is the set's catalog entry control total of record (source authority matrix, set.entry_total); entries counts every catalog entry of the set in the feed; applied counts the entries actually applied; voided counts entries voided by an X entry; uncommitted and rejected count those entries. An X entry is counted in entries only: it is never counted as applied, voided, uncommitted or rejected. Counts and byte sums are JSON integers."),
    ("h", 2, "12. Values that look wrong but are valid"),
    ("p", "Files of tens of gibibytes, modification times after the snapshot (client clocks running ahead) and modification times decades old are valid and are restored as recorded. Quarantine follows QPROC and media selection follows MEDIAPROC."),
]

SPEC41_KEEP = [
    ("h", 2, "7. Pattern dialect"),
    ("p", "7.1 Matching. Patterns are matched against the display path of an object, case-insensitively after Unicode NFC normalisation. A pattern ending in '/' is a directory pattern: it matches an object when it matches any directory that contains the object, at any depth. A pattern that contains no '/' (after removing a trailing '/') is matched against the last component only (for a directory pattern: against the last component of each containing directory). A pattern that contains a '/' is anchored at the share root; a leading '/' is optional."),
    ("p", "7.2 Syntax. '*' matches any run of characters within one component, never '/'. '?' matches exactly one character other than '/'. '[abc]' matches one listed character and '[!abc]' one character that is not listed. A component that is exactly '**' matches zero or more whole components. Every other character matches itself."),
    ("p", "7.3 Examples. '*.tmp' matches /a/b/x.tmp. '/Design/*.png' matches /Design/a.png but not /Design/sub/a.png. 'Build/' matches /x/Build/y.bin. '**/tmp/**' matches /a/tmp/b and /tmp/b."),
    ("h", 2, "9.2 Timestamp conversion"),
    ("p", "Column kinds and notations are defined in the catalog format guide. Fractions of a second are dropped (truncated towards the earlier second). Wall-clock values are converted with the IANA time zone of the host of record; a wall time that occurs twice resolves to its first occurrence. Excel serial values are rounded to the nearest second."),
    ("p", "Clients whose host file system is FAT32 or exFAT record the local wall-clock time of the client instead of an instant, whatever the column kind says: read the value's calendar digits as a wall-clock time in the client host's time zone and convert that to UTC. An offset written in such a value is meaningless and is ignored."),
    ("p", "A modification time sentinel (catalog format guide section 5) means the agent could not read the time: the restored mtime_utc is then the snapshot time of the set whose entry is restored."),
]

SPEC41_OLD = [
    ("h", 2, "5. Backup set chain (superseded)"),
    ("p", "5.2 The snapshot time of a set is the time its job ended. 5.5 The base is the latest FULL set; synthetic fulls are not used. A FAILED set breaks the chain. Partial sets are skipped."),
    ("h", 2, "6. Catalog replay (superseded)"),
    ("p", "6.2 The display spelling of a path is the spelling of the latest entry applied to it. 6.4 Corrections from the newest errata document apply whatever their status."),
    ("h", 2, "10. Allocation (superseded)"),
    ("p", "A file allocates its size rounded up to whole 4096-byte clusters; hard links allocate like any other file."),
]

SPEC43_RULES = [
    ("h", 1, "Point-in-time Restore Specification - revision 4.3 (working draft)"),
    ("p", "WORKING DRAFT - NOT APPROVED. This draft is circulated for review and is not in force. Appendix J (job rename crosswalk) was approved on its own under a separate change record; see the document control register."),
    ("h", 2, "5. Backup set chain (proposed)"),
    ("p", "5.2 The snapshot time of a set is the job end time reported by the job history; server logs are no longer consulted. 5.5 FAILED and CANCELLED sets break the chain. A set whose snapshot equals the restore point is after it."),
    ("h", 2, "6. Catalog replay (proposed)"),
    ("p", "6.2 The display spelling of a path follows the latest entry applied to it. 6.3 Void entries are ignored when they sit in a different part than the entry they void."),
    ("h", 2, "7. Exclusion patterns (proposed)"),
    ("p", "'*' matches any run of characters including '/'. Patterns are case-sensitive. The newest catalogue revision applies from its publication."),
    ("h", 2, "10. Allocation (proposed)"),
    ("p", "Sizes round to the nearest cluster; hard links and resident files allocate like any other file."),
]

README_TEXT = [
    ("h", 1, "Restore feed readme"),
    ("h", 2, "1. What a feed is"),
    ("p", "A restore feed is the set of files in one directory whose control block names the feed identifier of the restore request. Files are identified only by their content: the format by its leading bytes and structure, the role by the stream, part and status of its control block. File names and extensions carry no meaning and must never decide anything, because feeds are re-delivered under different names."),
    ("h", 2, "2. Control blocks"),
    ("p", "Every feed file except the project archive carries one control block: space-separated key=value pairs whose values never contain spaces. Keys always present: feed, stream, part, of, status, records, custody. Other keys (locale, revision, effective_from, source_custody, note) appear where a stream needs them. Locations: the first line '#control ...' of delimited, fixed-width and log files; the 'control' object of JSON documents and of the first JSONL line; the control element of XML; the 'restore-control' key of the Parquet schema metadata; the _control sheet of workbooks and the _control table of SQLite databases (key, value rows); the control mapping, table or section of YAML, TOML and INI files; the X-RESTORE-CONTROL property of the calendar; the X-Restore-Control header of the first message of the mailbox (a control message that is not a record); the first line 'CONTROL ...' of PDF and Word documents; the restore-control comment of Markdown and the restore-control meta element of HTML."),
    ("h", 2, "3. Records"),
    ("p", "records states the number of data records of the file: data rows of tables and sheets (headers, schema lines, comments and control rows excluded), objects of JSON arrays and JSONL lines, record elements of XML, log lines after the control line, calendar events, mailbox messages after the control message, items of YAML and TOML lists, sections of INI files (for the local account register: account lines), and rows of all tables of a document."),
    ("h", 2, "4. Parts, truncation and resends"),
    ("p", "of states how many ORIGINAL parts the stream has; the feed registry below repeats the part counts of each feed. A part that holds fewer records than its control block states lost its tail in transfer; the lost tail is re-published as a RESEND part with the same stream and part. A RESEND part is of record only for entries whose entry identifier does not occur in the ORIGINAL part; for every other entry the ORIGINAL part wins."),
    ("h", 2, "5. Corrected copies"),
    ("p", "A CORRECTED copy of a part is produced by a help-desk script and is never a catalog source. When the custody value of an ORIGINAL part is N/A, the custody digest uses the source_custody value of the CORRECTED copy of that part instead."),
    ("h", 2, "6. Custody digest"),
    ("p", "For every file of the feed, whatever its status, form the line stream|part|status|records|custody from its control block (values as written, custody replaced as in section 5). Sort the lines by Unicode code points, terminate each with a line feed, and take the SHA-256 of the UTF-8 bytes. The lowercase hexadecimal digest is the custody digest every deliverable carries."),
]

AUTH_ROWS = [
    ("set.membership", "JOBDEF ORIGINAL", "with the job rename crosswalk of SPEC 4.3 Appendix J", "1"),
    ("set.snapshot", "LOG ORIGINAL", "snapshot line of the server that ran the set", "1"),
    ("set.snapshot", "LOG MIRROR", "only inside a window a rotated log declares as not retained", "2"),
    ("set.snapshot", "JOB ORIGINAL", "never - queued and ended are not snapshot times", "-"),
    ("set.snapshot", "JOB REPORTING", "never", "-"),
    ("set.status", "LOG ORIGINAL", "catalog-check status change lines", "1"),
    ("set.status", "JOB ORIGINAL", "", "2"),
    ("set.status", "JOB REPORTING", "never", "-"),
    ("set.consolidates", "JOB ORIGINAL", "", "1"),
    ("set.entry_total", "JOB REPORTING", "catalog_entries: the only per-set control total of catalog entries", "1"),
    ("entry.*", "CAT ORIGINAL", "", "1"),
    ("entry.*", "CAT RESEND", "only entries whose identifier is absent from the ORIGINAL part", "2"),
    ("entry.*", "CAT CORRECTED", "never", "-"),
    ("entry.correction", "ERR ORIGINAL", "approved corrections of revisions in force", "1"),
    ("client.host", "FMTGUIDE Appendix D", "row valid on the local site date of the entry's set snapshot", "1"),
    ("host.tz", "HOST ORIGINAL", "", "1"),
    ("host.tz", "HOST CMDB-EXPORT", "never", "-"),
    ("host.fs", "HOST CMDB-EXPORT", "the only file-system type of record", "1"),
    ("share.*", "SHARE ORIGINAL", "", "1"),
    ("share.root", "ROOT ORIGINAL", "", "1"),
    ("server.*", "SRV ORIGINAL", "", "1"),
    ("media.status", "MEDIA ORIGINAL", "", "1"),
    ("media.status", "MEDIA PREVIEW", "never", "-"),
    ("media.status", "DASH ORIGINAL", "never", "-"),
    ("media.barcode", "MEDIA PREVIEW", "the only barcode to media crosswalk", "1"),
    ("media.vault", "SLOT ORIGINAL", "baseline, then XFER and MAIL as MEDIAPROC section 4", "1"),
    ("media.vault", "DASH ORIGINAL", "only for media of vault VLT-OFF3 that the slot register does not list", "1"),
    ("media.defect", "MERR ORIGINAL", "approved entries of revisions and sections in force", "1"),
    ("container.copies", "CMAP ORIGINAL", "containers CT-", "1"),
    ("container.copies", "CMAP FINAL", "only containers RC- written by the repack job", "1"),
    ("container.check", "CHK ORIGINAL", "", "1"),
    ("container.check", "CHK RERUN", "only copies named in a rerun request message", "1"),
    ("container.repack", "REPACK ORIGINAL", "", "1"),
    ("copy.job", "COPY ORIGINAL", "", "1"),
    ("av.finding", "AV ORIGINAL", "containers created on or after the engine cutover", "1"),
    ("av.finding", "AV PRELIMINARY", "containers created before the engine cutover", "1"),
    ("av.withdrawal", "ADV ORIGINAL", "", "1"),
    ("owner.account", "IDMAP ORIGINAL", "with IDCHG approved changes", "1"),
    ("owner.account", "IDMAP EXPORT", "only principals of a domain with no rows in the identity map", "1"),
    ("owner.uid", "LACCT ORIGINAL", "", "1"),
    ("scope.include", "SPEC Appendix B", "revision in force", "1"),
    ("scope.disposition", "RRQ ORIGINAL", "", "1"),
    ("scope.pattern", "EXCL ORIGINAL", "revision in force, withdrawals of any revision", "1"),
    ("target.volume", "VOL ORIGINAL", "", "1"),
    ("calendar.window", "CAL ORIGINAL", "planned windows", "2"),
    ("calendar.window", "LOG ORIGINAL", "storage array actual-start and actual-end lines", "1"),
]

PATHCONV_TEXT = [
    ("h", 1, "Path conventions for restore catalogs"),
    ("h", 2, "1. Canonical form"),
    ("p", "A canonical share path starts with '/', separates components with '/', is in Unicode NFC, and has no empty, '.' or '..' components. The share root itself is '/'."),
    ("h", 2, "2. Roots"),
    ("p", "A raw catalog path starts with one of the roots the share root register lists for the share and the host of the entry's client (client crosswalk, catalog format guide Appendix D). On Windows hosts the root comparison is case-insensitive and the separators '\\' and '/' are equivalent; on other hosts the comparison is exact. A root matches only when it is followed by a separator or by the end of the path. The rest of the path, split at separators, gives the components."),
    ("h", 2, "3. Components"),
    ("p", "On Windows hosts trailing dots and spaces are removed from every component. On every host, empty components and '.' are dropped and '..' removes the preceding component. A '..' with no preceding component climbs above the share root and makes the entry unsafe. A path under none of the client's roots is outside the share. Unsafe and outside entries are rejected (restore specification section 6.6). Components are then normalised to NFC; macOS clients record NFD."),
    ("h", 2, "4. Identifiers"),
    ("p", "Identifiers are normalised as the catalog format guide section 4 says; the confusable fold table in Appendix C is applied to identifiers only, never to paths."),
    ("h", 2, "5. Link targets"),
    ("p", "A link target that starts with one of the client's roots is taken relative to the share root. Any other absolute target (a leading '/', a drive letter, or '\\\\' on Windows) leaves the share. A relative target is resolved against the directory that contains the link, with '.' and '..' as in section 3; climbing above the share root leaves the share. On Windows hosts '\\' separates components of targets. The resolved target is written in canonical form; its spelling is not changed by the spelling rule."),
    ("h", 2, "6. Identity and spelling"),
    ("p", "Two paths name the same object when their canonical forms are equal after full Unicode case folding (the share registry lists the share as insensitive-preserving). Each component of a display path keeps the spelling under which that file or directory was created or last renamed: a component that already exists keeps its spelling whatever spelling a later entry uses, a newly created or renamed component takes the spelling of the entry that created or renamed it, and missing directories that an entry implies are created with that entry's spelling."),
]

FMTGUIDE_TEXT = [
    ("h", 1, "Catalog and register format guide"),
    ("h", 2, "2. Delimited files"),
    ("p", "Comma files follow RFC 4180; tab files escape tab, line feed, carriage return and backslash as \\t, \\n, \\r and \\\\. Line 1 is the control line, line 2 the header. A line '#schema <header>' restates the header from that point on: columns may be renamed, reordered or change kind. A row may carry one trailing empty field, which is ignored. Other lines starting with '#' are comments."),
    ("h", 2, "3. Encodings"),
    ("p", "Text files are UTF-8 and may start with a byte order mark. In delimited files a line '#encoding latin-1' switches the following lines to ISO-8859-1 until a line '#encoding utf-8'."),
    ("h", 2, "4. Identifiers"),
    ("p", "Set (BS, 5 digits), entry (E, 7 digits), container (CT and RC, 7 digits) and media (MD, 5 digits) identifiers are normalised by removing surrounding white space, folding confusable letters with the identifier rows of PATHCONV Appendix C, upper-casing, reading '_' as '-', inserting the missing '-' after the prefix, and zero-padding the number to the width given. Hashes are hexadecimal in any case and may carry the prefix 'sha256:'; job names compare case-insensitively after trimming."),
    ("h", 2, "5. Sentinels"),
    ("p", "A modification time of 0000-00-00 in text kinds, 0 in epoch, filetime and Excel serial kinds, or -1 in the millisecond kind, or a null Parquet timestamp, is a sentinel: the time was not read (restore specification revision 4.1 section 9.2). An owner of N/A, '-' or null is a sentinel: the owner is UNMAPPED. A sha256 of 64 zeros is a placeholder that a catalog errata correction replaces."),
    ("h", 2, "6. Numbers and sizes"),
    ("p", "size, size_bytes and bytes are byte counts; size_kib is a count of KiB (multiply by 1024; the result is an exact integer). In text cells numbers use the digit grouping of the control-block locale: plain none, en_US ',', de_DE '.', fr_FR U+202F; decimal fractions use ',' for de_DE and fr_FR and '.' otherwise. Workbook and Parquet number cells are typed. Container maps give size_bytes or size_text; size_text is grouped by the control-block locale."),
    ("h", 2, "7. Timestamps"),
    ("p", "A timestamp column is named <name>_<kind>. utc: ISO 8601 ending in Z. iso: ISO 8601 with a UTC offset. epoch: seconds since 1970-01-01T00:00:00Z. ms: milliseconds since then. ft: Windows FILETIME, 100-nanosecond intervals since 1601-01-01T00:00:00Z. local: 'YYYY-MM-DD HH:MM:SS' wall-clock time of the client host (catalog) or of the server named in the row (job history). xl: an Excel serial day number in the workbook's date system (date1904 in the workbook properties), counting UTC. Parquet timestamps are UTC. Job history and mailbox times carry their own notation; calendar times use TZID or a trailing Z. Server log lines start with the server's notation of section 5.2 of the restore specification; console mirror lines are UTC truncated to the minute; storage array event lines are UTC."),
    ("h", 2, "8. Catalog columns"),
    ("p", "Catalog columns appear under the aliases of the table below; the canonical name is listed first. Committed flags are Y/N, 1/0 or true/false. Mode columns: mode_oct (octal, with or without a leading zero), mode_sym (ls notation, with s, S, t and T), mode_dec (decimal) and st_mode (octal including the file-type bits). Windows clients give attributes instead of a mode."),
    ("h", 2, "9. Fixed-width catalog parts"),
    ("p", "Fixed-width parts start with the control line and switch layouts with '#layout <name>' lines. Columns follow each other without separators at the widths of the layout table; widths count characters, values are left-aligned and padded with spaces, and trailing spaces at the end of a line are removed. In layout A the time column is a FILETIME and the mode is octal; in layout B the time is in epoch seconds and the mode is decimal."),
    ("h", 2, "10. Other formats"),
    ("p", "XML catalog parts hold one element per entry with one child element per non-empty column. JSON catalog parts hold the entries array; JSONL parts hold one entry object per line after the control line. Workbooks hold one sheet per header segment (entries, entries_2) besides _control. INI files are read without value interpolation. The calendar folds long lines as RFC 5545 says (a continuation line starts with one space). PDF tables print one row per line with cells separated by ' | ', an empty cell as '-', repeat the header with '(continued)' at the top of a new page, and end with 'END TABLE'."),
]

MEDIAPROC_TEXT = [
    ("h", 1, "Media handling procedure for restores"),
    ("h", 2, "2. Copy usability"),
    ("p", "Every container has copy 1 and may have copies 2 and 3. A copy is usable unless one of these holds: its media has status EXPIRED in the media inventory; its media is of generation LTO-6 (section 5); its media is damaged or unreadable in an approved media errata entry of a revision and section in force (with approved corrections applied to the entry first); its media was destroyed by a destruction notice whose Date is at or before the end of the request date; the checksum audit result for that container copy is MISMATCH (a rerun result replaces the first audit for copies named in a rerun request message); or, for copies 2 and 3, no copy job for that container copy completed at or before the end of the request date. The restore reads the usable copy with the lowest number. A file whose container has no usable copy is UNRECOVERABLE."),
    ("h", 2, "3. Container references"),
    ("p", "The container of a restored entry is the catalog value after errata corrections. When the repack journal moved that container to a new RC- container at or before the end of the request date, the new container is read instead; its copies are listed only in the repack export of the container map. Copy-2 rows reference media by barcode, which the media planning preview maps to media identifiers. Copy-1 and copy-3 rows reference media identifiers."),
    ("h", 2, "4. Vault location"),
    ("p", "The vault of a media at the request date starts from the slot register; transfers whose received time is at or before the end of the request date and recall notices whose Date is at or before it then move the media, in time order, the latest winning. Media of vault VLT-OFF3 are not in the slot register; the vault status dashboard is of record for them."),
    ("h", 2, "5. Restrictions"),
    ("p", "The restore library has no LTO-6 drive: copies on LTO-6 media are not usable, whatever their status."),
    ("h", 2, "6. Pull list order"),
    ("p", "The pull list is ordered by the vault priority that Appendix E gives for the vault on the request date (1 first), then by media identifier."),
]

QPROC_TEXT = [
    ("h", 1, "Quarantine procedure for restores"),
    ("h", 2, "2. Scan of record"),
    ("p", "Findings name a sha256 and the container that was scanned. For a container created at or after the engine cutover the final scan (AV streams with status ORIGINAL) is of record; for a container created before it the preliminary scan (AV status PRELIMINARY) is of record. The container's created time comes from the container map. The engine cutover is {cutover}."),
    ("h", 2, "3. Verdicts"),
    ("p", "A finding of record with verdict INFECTED counts unless it is withdrawn. A finding is withdrawn when the vendor advisory lists the vendor of the finding's engine (Appendix A), the finding's signature, a revision range that includes its sig_rev, and a withdrawal time at or before the end of the request date. PUA and CLEAN verdicts never quarantine. A catalog entry is infected when a counting finding of record matches its sha256 and its container (the catalog value after errata corrections, before repack)."),
    ("h", 2, "4. Rollback"),
    ("p", "When the entry that gives a file its version at the effective point is infected, the file is restored from the latest clean earlier entry of the same identity instead: candidates are F entries that would be applied (not voided, committed, not rejected) of applied sets and of sets skipped as BEFORE_BASE or SUPERSEDED_BY_DIFF, whose path has the same identity, ordered by set snapshot time, set identifier and seq; only entries before the entry at the effective point count. The restored row takes size, sha256, mode, mtime, owner, container and source_set from that entry and keeps the display path. When no candidate is clean the file is QUARANTINED."),
]


def confusable_rows(n: int, r: Rng) -> list[list[str]]:
    ident = [("0412", "B"), ("0421", "C"), ("0415", "E"), ("041C", "M"), ("0422", "T"), ("0405", "S"), ("0392", "B"),
             ("0395", "E"), ("039C", "M"), ("03A4", "T"), ("0421", "C"), ("041D", "H"), ("0420", "P"), ("0425", "X")]
    rows, seen = [], set()
    for cp, fold in ident:
        if cp in seen:
            continue
        seen.add(cp)
        rows.append([f"U+{cp}", unicodedata.name(chr(int(cp, 16)), "?"), fold, "identifier"])
    for c in list(range(0xFF10, 0xFF1A)) + list(range(0xFF21, 0xFF3B)):
        rows.append([f"U+{c:04X}", unicodedata.name(chr(c)), unicodedata.normalize("NFKC", chr(c)), "identifier"])
        seen.add(f"{c:04X}")
    extra = []
    for c in range(0xA0, 0x2FFFF):
        if f"{c:04X}" in seen or len(extra) > n:
            continue
        ch = chr(c)
        base = "".join(x for x in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(x))
        if len(base) == 1 and base.isascii() and base.isalnum() and base != ch:
            extra.append([f"U+{c:04X}", unicodedata.name(ch, "?"), base, "display"])
    if len(rows) + len(extra) < n:
        for c in range(0x0100, 0x2FFFF):
            if len(rows) + len(extra) >= n:
                break
            ch = chr(c)
            if f"{c:04X}" in seen or not unicodedata.category(ch).startswith("L"):
                continue
            base = "".join(x for x in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(x))
            if base.isascii():
                continue
            extra.append([f"U+{c:04X}", unicodedata.name(ch, "?"), "", "display"])
    r.shuffle(extra)
    keep = rows + extra[: max(0, n - len(rows))]
    keep.sort(key=lambda x: int(x[0][2:], 16))
    return keep


def _doc(fo: FileOut, blocks: list) -> FileOut:
    fo.doc = blocks
    fo.records = doc_records(fo)
    return fo


def build_docs(w: World, R: dict, names: dict) -> list[FileOut]:
    r = w.rng.fork("docs")
    p = w.p
    tz = p["site_tz"]
    rp = w.rp
    req_end = R["req_end"]
    rp_wall = local_wall(rp, tz)
    outs = []
    N = lambda: doc_rows(p, r)  # noqa: E731
    shares = R["shares"]

    def profiles(changed: bool, old: bool) -> list[list[str]]:
        rows = []
        mine = list(p["includes"])
        if changed:
            mine = mine[1:] + ["/Shared/Inbox"]
        if old:
            mine = ["/Engineering", "/Design", "/Shared"]
        rows.append([p["share"], "; ".join(mine), p["target_volume"]])
        for s in shares[1:]:
            rows.append([s, "; ".join(sorted(r.sample(["/Data", "/Projects", "/Home", "/Scans", "/Exports", "/Archive"], 2))),
                         f"VOL-{r.randint(100, 999)}-{s.replace('-', '')}N"])
        while len(rows) < N():
            s = f"ARC-{r.randint(1000, 99999)}"
            rows.append([s, "/Vault", f"VOL-{r.randint(100, 999)}-{s.replace('-', '')}N"])
        return rows

    # SPEC 4.2 (md)
    fo = FileOut(names["spec42"], "md", "SPEC", "42", status="ISSUED")
    fo.control["revision"] = "4.2"
    blocks = list(SPEC42) + [("h", 2, "Appendix B - Share restore profiles"),
                             ("p", "include_prefixes lists the include prefixes of each share, separated by '; '."),
                             ("table", "Share restore profiles", ["share", "include_prefixes", "default_target"], profiles(False, False))]
    outs.append(_doc(fo, blocks))
    fo.trap("Appendix B", "T14", "include prefixes of record (section 8)", PLAN_CHECK)
    _fill_traps(fo, r, fo.records, ["T14", "T11", "T12", "T1"], "rules of the approved revision", PLAN_CHECK)
    # SPEC 4.3 draft (md, decoy)
    fo = FileOut(names["spec43"], "md", "SPEC", "43", status="ISSUED", decoy=True)
    fo.control["revision"] = "4.3"
    xw = [[x["old"], x["new"], x["effective"]] for x in R["xwalk"]]
    r.shuffle(xw)
    blocks = list(SPEC43_RULES) + [("h", 2, "Appendix B - Share restore profiles (proposed)"),
                                   ("table", "Share restore profiles", ["share", "include_prefixes", "default_target"], profiles(True, False)),
                                   ("h", 2, "Appendix J - Job rename crosswalk"),
                                   ("p", "Each row maps an old job name to the job that replaced it; sets queued under the old name before the effective date belong to the new job's share."),
                                   ("table", "Job rename crosswalk", ["old_name", "new_name", "effective"], xw)]
    outs.append(_doc(fo, blocks))
    fo.trap("header", "T14", "draft declared in its own header; register confirms (DOCREG)", PLAN_CHECK, "push")
    fo.trap("5.2", "T11", "draft uses job end times", PLAN_CHECK, "pull")
    fo.trap("5.5", "T6", "draft breaks chains on failed sets", PLAN_CHECK, "pull")
    fo.trap("6.2", "T7", "draft spelling follows the latest entry", PLAN_CHECK, "pull")
    fo.trap("7", "T9", "draft star crosses separators", PLAN_CHECK, "pull")
    fo.trap("10", "T12", "draft rounds allocation to nearest", PLAN_CHECK, "pull")
    fo.trap("Appendix B", "T16", "proposed profiles differ for one share", PLAN_CHECK, "pull")
    fo.trap("Appendix J", "T13", "the only job rename crosswalk", PLAN_CHECK, "push")
    _fill_traps(fo, r, fo.records, ["T16", "T13", "T6", "T7", "T1"], "draft content", PLAN_CHECK, 27)
    # SPEC 4.1 (docx, decoy: superseded except sections 7.1-7.3 and 9.2)
    fo = FileOut(names["spec41"], "docx", "SPEC", "41", status="ISSUED", decoy=True)
    fo.control["revision"] = "4.1"
    blocks = [("h", 1, "Point-in-time Restore Specification - revision 4.1"),
              ("p", "Revision block: 4.1 issued. Superseded by revision 4.2 except where 4.2 carries sections forward."),
              ] + SPEC41_OLD + SPEC41_KEEP + [("h", 2, "Appendix B - Share restore profiles"),
                                             ("table", "Share restore profiles", ["share", "include_prefixes", "default_target"], profiles(False, True))]
    outs.append(_doc(fo, blocks))
    for sec, fam, d_ in (("7.1", "T9", "push"), ("7.2", "T9", "push"), ("9.2", "T3", "push"), ("9.2 FAT", "T3", "push"),
                         ("9.2 sentinel", "T5", "push"), ("5.2", "T11", "pull"), ("5.5", "T6", "pull"), ("6.2", "T7", "pull"),
                         ("10", "T12", "pull"), ("Appendix B", "T16", "pull"), ("Appendix B", "T13", "pull")):
        fo.trap(sec, fam, "superseded except sections carried forward by 4.2 (DOCREG, SPEC 4.2 section 1)", PLAN_CHECK, d_)
    _fill_traps(fo, r, fo.records, ["T16", "T7", "T6", "T13", "T14"], "superseded profile rows", PLAN_CHECK, 27)
    # README (md) with the feed registry
    fo = FileOut(names["readme"], "md", "README", "01", status="ISSUED")
    reg = [[p["feed_id"], p["share"], R["rrq_id"], R["part_counts"], "OPEN"]]
    while len(reg) < N():
        reg.append([f"RR-{r.randint(2019, 2026)}-{r.randint(1, 9999):04d}", r.choice(shares[1:]), f"RQ-{r.randint(10000, 99999)}",
                    f"CAT:{r.randint(3, 40)} JOB:{r.randint(1, 3)} LOG:{r.randint(1, 4)}", r.choice(["CLOSED", "CLOSED", "CANCELLED"])])
    r.shuffle(reg)
    outs.append(_doc(fo, list(README_TEXT) + [("h", 2, "Feed registry"), ("p", "parts lists, per stream, how many ORIGINAL parts the feed delivers."),
                                              ("table", "Feed registry", ["feed", "share", "request", "parts", "state"], reg)]))
    _fill_traps(fo, r, fo.records, ["T14", "T6", "T13"], "feed rules and part counts", PLAN_CHECK)
    # restore request (docx)
    fo = FileOut(names["rrq"], "docx", "RRQ", "01", status="ISSUED")
    params = [["request_id", R["rrq_id"]], ["feed", p["feed_id"]], ["share", p["share"]],
              ["restore_point_local", rp_wall.strftime("%Y-%m-%d %H:%M:%S")], ["request_date", p["request_date"]],
              ["target_volume", p["target_volume"]], ["requested_by", "storage-restore@corp.example"]]
    disp = [[h["hold"], p["share"], h["prefix"], h["action"], h["effective"]] for h in R["dispositions_share"]]
    while len(disp) < N():
        disp.append([f"RM-{r.randint(10000, 99999)}", r.choice(shares[1:]), f"/{r.choice(['Data', 'Projects', 'Home'])}/{r.choice(WORDS)}",
                     r.choice(["DESTROY", "RETAIN"]), (rp_wall.date() - dt.timedelta(days=r.randint(-30, 300))).isoformat()])
    r.shuffle(disp)
    outs.append(_doc(fo, [("h", 1, f"Restore request {R['rrq_id']}"), ("p", "Restore the share to the restore point below. The restore point is a wall-clock time in the site time zone of the share."),
                          ("table", "Request parameters", ["key", "value"], params),
                          ("h", 2, "Appendix - Records disposition holds"),
                          ("p", "Holds with action DESTROY take effect on their effective date; RETAIN holds never exclude anything."),
                          ("table", "Records disposition holds", ["hold", "share", "prefix", "action", "effective"], disp)]))
    _fill_traps(fo, r, fo.records, ["T11", "T14", "T1", "T9"], "disposition effective dates and prefixes (SPEC 4.2 section 8)", PLAN_CHECK)
    # authority matrix (docx)
    fo = FileOut(names["auth"], "docx", "AUTH", "01", status="ISSUED")
    rows = [list(x) for x in AUTH_ROWS]
    while len(rows) < N():
        rows.append([f"{r.choice(['hr', 'fin', 'crm', 'erp', 'ops'])}.{r.choice(['employee', 'invoice', 'asset', 'ticket'])}.{r.choice(['grade', 'amount', 'owner', 'state'])}{r.randint(1, 99)}",
                     f"{r.choice(['SAP', 'WORKDAY', 'SNOW', 'CRM'])} {r.choice(['ORIGINAL', 'EXPORT'])}", "", str(r.randint(1, 3))])
    r.shuffle(rows)
    outs.append(_doc(fo, [("h", 1, "Source authority matrix"), ("p", "For each fact the matrix names the stream and control status of record and its rank; '-' means never. A fact is taken from the best-ranked source that has it, under the stated condition."),
                          ("table", "Source authority", ["fact", "source", "condition", "rank"], rows)]))
    _fill_traps(fo, r, fo.records, ["T14", "T16", "T13", "T7"], "authority rows decide every conflict", PLAN_CHECK)
    # path conventions (docx)
    fo = FileOut(names["pathconv"], "docx", "PATHCONV", "01", status="ISSUED")
    outs.append(_doc(fo, list(PATHCONV_TEXT) + [("h", 2, "Appendix C - Confusable fold table"),
                                                ("p", "Rows with scope identifier fold the character for identifiers; rows with scope display are listed for completeness and are never applied."),
                                                ("table", "Confusable fold table", ["codepoint", "name", "fold", "scope"], confusable_rows(N(), r))]))
    _fill_traps(fo, r, fo.records, ["T1", "T9", "T14"], "identifier rows only", PLAN_CHECK)
    # media handling (docx)
    fo = FileOut(names["mediaproc"], "docx", "MEDIAPROC", "01", status="ISSUED")
    cal = [[v, d, str(pr)] for (v, d), pr in sorted(R["vault_cal"].items(), key=lambda x: (x[0][1], x[0][0]))]
    outs.append(_doc(fo, list(MEDIAPROC_TEXT) + [("h", 2, "Appendix E - Vault service calendar"),
                                                 ("table", "Vault service calendar", ["vault", "date", "priority"], cal)]))
    _fill_traps(fo, r, fo.records, ["T14", "T11", "T12"], "priority on the request date", PLAN_CHECK)
    # quarantine (docx)
    fo = FileOut(names["qproc"], "docx", "QPROC", "01", status="ISSUED")
    eng = [[e["code"], e["vendor"], e["product"], "ACTIVE"] for e in R["engines"]]
    used = {e["code"] for e in R["engines"]}
    while len(eng) < N():
        c = f"E{r.randint(100, 99999)}"
        if c in used:
            continue
        used.add(c)
        eng.append([c, r.choice(VENDORS + ["Generic AV", "Legacy Scan"]), f"Engine {r.randint(1, 9)}", r.choice(["ACTIVE", "RETIRED"])])
    r.shuffle(eng)
    q = [("p", b[1].replace("{cutover}", iso_z(R["av_cutover"]))) if b[0] == "p" else b for b in QPROC_TEXT]
    outs.append(_doc(fo, q + [("h", 2, "Appendix A - Engine registry"), ("table", "Engine registry", ["engine", "vendor", "product", "status"], eng)]))
    _fill_traps(fo, r, fo.records, ["T13", "T11", "T14"], "engine to vendor mapping and cutover", PLAN_CHECK)
    # format guide (docx)
    fo = FileOut(names["fmtguide"], "docx", "FMTGUIDE", "01", status="ISSUED")
    alias = [[f, ", ".join(a)] for f, a in CAT_ALIASES.items()]
    lay = [[name, col, str(width)] for name, cols in FIXED_LAYOUTS.items() for col, width in cols]
    cx = [[x["code"], x["host"], x["from"], x["to"]] for x in R["clientx"]]
    r.shuffle(cx)
    outs.append(_doc(fo, list(FMTGUIDE_TEXT) + [("table", "Catalog column aliases", ["column", "aliases"], alias),
                                                ("table", "Fixed-width layouts", ["layout", "column", "width"], lay),
                                                ("h", 2, "Appendix D - Client crosswalk"),
                                                ("p", "valid_to empty means the row is still valid; both dates are inclusive local site dates."),
                                                ("table", "Client crosswalk", ["client", "host", "valid_from", "valid_to"], cx)]))
    _fill_traps(fo, r, fo.records, ["T1", "T5", "T8", "T10", "T2", "T4"], "format rules", PLAN_CHECK)
    return outs


def build_data_docs(w: World, R: dict, names: dict) -> list[FileOut]:
    r = w.rng.fork("datadocs")
    p = w.p
    rp = w.rp
    req_end = R["req_end"]
    N = lambda: doc_rows(p, r)  # noqa: E731
    outs = []
    # catalog errata r1 and r2
    eid = [r.randint(10000, 20000)]
    for rev in (1, 2):
        fo = FileOut(names[f"err{rev}"], "pdf", "ERR", f"{rev:02d}", status="ISSUED")
        fo.control["revision"] = str(rev)
        rows = []
        for x in R["errata_share"]:
            if x["rev"] == rev:
                eid[0] += r.randint(1, 5)
                rows.append([f"ERR-{eid[0]}", x["entry"], x["field"], x["value"], x["status"]])
        while len(rows) < N():
            eid[0] += r.randint(1, 5)
            f = r.choice(["sha256", "size", "mtime", "container"])
            val = {"sha256": r.hexstr(64), "size": str(r.randint(1, 10**9)), "mtime": iso_z(rp - dt.timedelta(days=r.randint(1, 90))),
                   "container": f"CT-{r.randint(8000000, 9999999)}"}[f]
            rows.append([f"ERR-{eid[0]}", f"E-{r.randint(5000000, 9999999):07d}", f, val, r.choice(["APPROVED", "APPROVED", "REJECTED", "PENDING"])])
        r.shuffle(rows)
        outs.append(_doc(fo, [("h", 1, f"Catalog errata - revision {rev}"),
                              ("p", "Each row corrects one field of one catalog entry. Status APPROVED rows apply; REJECTED and PENDING rows never do."),
                              ("table", "Catalog errata", ["errata", "entry", "field", "value", "status"], rows)]))
        for i, row in enumerate(rows):
            if row[1] in {x["entry"] for x in R["errata_share"]} and len(fo.traps) < 9:
                fo.trap(i, "T7" if row[4] == "APPROVED" else "T6", "approved corrections, highest revision wins (SPEC 4.2 section 6.4)", PLAN_CHECK)
        _fill_traps(fo, r, fo.records, ["T7", "T6", "T13", "T5"], "errata rows", PLAN_CHECK)
    # media errata revision A (in force) and B (draft except section 2)
    fo = FileOut(names["merrA"], "pdf", "MERR", "01", status="ISSUED")
    fo.control["revision"] = "A"
    rows = [[x["id"], x["media"], x["defect"], x["effective"], x["status"]] for x in R["merr"]]
    while len(rows) < N():
        rows.append([f"ME-{r.randint(10000, 99999)}", f"MD-{r.randint(20000, 39999)}", r.choice(["DAMAGED", "UNREADABLE", "MISLABELED"]),
                     (rp.date() - dt.timedelta(days=r.randint(1, 300))).isoformat(), r.choice(["APPROVED", "REJECTED"])])
    r.shuffle(rows)
    outs.append(_doc(fo, [("h", 1, "Media errata - revision A"), ("p", "APPROVED DAMAGED and UNREADABLE entries make every copy on the media unusable; MISLABELED entries never do."),
                          ("table", "Media errata", ["errata", "media", "defect", "effective", "status"], rows)]))
    _fill_traps(fo, r, fo.records, ["T7", "T6", "T1", "T13"], "approved defects only (MEDIAPROC section 2)", PLAN_CHECK)
    fo = FileOut(names["merrB"], "pdf", "MERR", "02", status="ISSUED", decoy=True)
    fo.control["revision"] = "B"
    rows = [[x["id"], x["media"], x["defect"], x["effective"], x["status"]] for x in R["merr_b"]]
    rows += [[x["id"], x["media"], x["defect"], x["effective"], x["status"]] for x in R["merr"]]
    while len(rows) < N():
        rows.append([f"ME-{r.randint(10000, 99999)}", f"MD-{r.randint(20000, 39999)}", r.choice(["DAMAGED", "UNREADABLE"]),
                     (rp.date() - dt.timedelta(days=r.randint(1, 300))).isoformat(), "PROPOSED"])
    r.shuffle(rows)
    corr = [[c["errata"], c["field"], c["was"], c["now"], c["cab"]] for c in R["merr_corr"]]
    outs.append(_doc(fo, [("h", 1, "Media errata - revision B (draft)"),
                          ("p", "Section 1 lists proposed entries for review. Section 2 corrects entries of revision A; section 2 was approved on its own."),
                          ("h", 2, "Section 1 - Proposed entries"), ("table", "Proposed media errata", ["errata", "media", "defect", "effective", "status"], rows),
                          ("h", 2, "Section 2 - Corrections to revision A"),
                          ("table", "Corrections to revision A", ["errata", "field", "was", "now", "change"], corr)]))
    fo.trap("Section 2", "T7", "the only correction of a revision-A entry (DOCREG)", PLAN_CHECK, "push")
    fo.trap("Section 1", "T6", "proposed entries are not in force", PLAN_CHECK, "pull")
    _fill_traps(fo, r, fo.records, ["T16", "T7", "T6", "T13", "T1", "T11"], "draft entries", PLAN_CHECK, 27)
    # document control register
    fo = FileOut(names["docreg"], "pdf", "DOCREG", "01", status="ISSUED")
    rpd = rp.date()
    rows = [["SPEC", "4.1", "ALL", "Point-in-time Restore Specification", "SUPERSEDED", (rpd - dt.timedelta(days=500)).isoformat()],
            ["SPEC", "4.1", "7.1-7.3", "Pattern dialect", "IN FORCE", (rpd - dt.timedelta(days=500)).isoformat()],
            ["SPEC", "4.1", "9.2", "Timestamp conversion", "IN FORCE", (rpd - dt.timedelta(days=500)).isoformat()],
            ["SPEC", "4.2", "ALL", "Point-in-time Restore Specification", "APPROVED", (rpd - dt.timedelta(days=120)).isoformat()],
            ["SPEC", "4.3", "ALL", "Point-in-time Restore Specification", "DRAFT", ""],
            ["SPEC", "4.3", "Appendix J", "Job rename crosswalk", "APPROVED", (rpd - dt.timedelta(days=60)).isoformat()],
            ["ERR", "1", "ALL", "Catalog errata", "APPROVED", (rpd - dt.timedelta(days=10)).isoformat()],
            ["ERR", "2", "ALL", "Catalog errata", "APPROVED", (rpd - dt.timedelta(days=3)).isoformat()],
            ["MERR", "A", "ALL", "Media errata", "APPROVED", (rpd - dt.timedelta(days=20)).isoformat()],
            ["MERR", "B", "ALL", "Media errata", "DRAFT", ""],
            ["MERR", "B", "Section 2", "Corrections to revision A", "APPROVED", (rpd - dt.timedelta(days=5)).isoformat()],
            ["EXCL", "8", "ALL", "Exclusion catalogue", "APPROVED", (rpd - dt.timedelta(days=200)).isoformat()],
            ["EXCL", "9", "ALL", "Exclusion catalogue", "APPROVED", (rpd + dt.timedelta(days=3)).isoformat()],
            ["ERR", "3", "ALL", "Catalog errata", "DRAFT", ""]]
    for s in ("README", "FMTGUIDE", "PATHCONV", "MEDIAPROC", "QPROC", "AUTH", "RRQ", "IDCHG", "XFER", "ADV", "COPY"):
        rows.append([s, "1", "ALL", s.title(), "APPROVED", (rpd - dt.timedelta(days=r.randint(30, 400))).isoformat()])
    while len(rows) < N():
        rows.append([r.choice(["HRPOL", "FINPOL", "SECSTD", "OPSRUN", "NETSTD"]) + str(r.randint(1, 99)), f"{r.randint(1, 9)}.{r.randint(0, 9)}", "ALL",
                     "Enterprise document", r.choice(["APPROVED", "SUPERSEDED", "DRAFT", "WITHDRAWN"]), (rpd - dt.timedelta(days=r.randint(1, 900))).isoformat()])
    r.shuffle(rows)
    outs.append(_doc(fo, [("h", 1, "Document control register"),
                          ("p", "A document revision, or the listed section of it, is in force when its status is APPROVED or IN FORCE and its effective date is on or before the restore point date. SUPERSEDED, DRAFT and WITHDRAWN rows are never in force. A row for a section overrides the row for ALL of the same revision."),
                          ("table", "Document control register", ["stream", "revision", "section", "title", "status", "effective"], rows)]))
    _fill_traps(fo, r, fo.records, ["T14", "T7", "T11"], "revision in force decides every document conflict", PLAN_CHECK)
    # identity change register
    fo = FileOut(names["idchg"], "pdf", "IDCHG", "01", status="ISSUED")
    rows = [[f"IC-{r.randint(10000, 99999)}", x["principal"], x["account"], iso_z(x["at"]), x["status"]] for x in R["idchanges_share"]]
    while len(rows) < N():
        rows.append([f"IC-{r.randint(10000, 99999)}", f"S-1-5-21-{r.randint(10**9, 4 * 10**9)}-{r.randint(1000, 9999)}", f"user{r.randint(100, 999)}",
                     iso_z(rp - dt.timedelta(days=r.randint(-30, 300))), r.choice(["APPROVED", "PENDING", "REJECTED"])])
    r.shuffle(rows)
    outs.append(_doc(fo, [("h", 1, "Identity change register"), ("p", "Approved changes rename the account of a principal from their effective time onwards."),
                          ("table", "Identity changes", ["change", "principal", "account", "effective_utc", "status"], rows)]))
    _fill_traps(fo, r, fo.records, ["T11", "T7", "T6"], "changes effective at or before the restore point (SPEC 4.2 section 9.3)", PLAN_CHECK)
    # vault transfer manifests
    fo = FileOut(names["xfer"], "pdf", "XFER", "01", status="ISSUED")
    rows = [[f"TM-{r.randint(10000, 99999)}", x["media"], x["from"], x["to"], iso_z(x["shipped"]), iso_z(x["received"])] for x in R["xfers"]]
    while len(rows) < N():
        t0 = req_end - dt.timedelta(days=r.randint(1, 120))
        rows.append([f"TM-{r.randint(10000, 99999)}", f"MD-{r.randint(20000, 39999)}", r.choice(VAULTS), r.choice(VAULTS), iso_z(t0), iso_z(t0 + dt.timedelta(days=2))])
    r.shuffle(rows)
    outs.append(_doc(fo, [("h", 1, "Vault transfer manifests"), ("p", "A transfer moves the media when it is received."),
                          ("table", "Transfers", ["manifest", "media", "from_vault", "to_vault", "shipped_utc", "received_utc"], rows)]))
    _fill_traps(fo, r, fo.records, ["T11", "T1", "T3"], "received at or before the end of the request date", PLAN_CHECK)
    # vendor advisory (html)
    fo = FileOut(names["adv"], "html", "ADV", "01", status="ISSUED")
    rows = [[f"ADV-{r.randint(1000, 9999)}", x["vendor"], x["sig"], f"{x['rev_from']}-{x['rev_to']}", iso_z(x["at"])] for x in R["withdrawals"]]
    while len(rows) < N():
        a = r.randint(1, 50)
        rows.append([f"ADV-{r.randint(1000, 9999)}", r.choice(VENDORS), f"Gen.Variant.{r.choice(['Kryptik', 'Razy', 'Zusy', 'Mikey'])}.{r.randint(100, 999)}",
                     f"{a}-{a + r.randint(0, 5)}", iso_z(req_end - dt.timedelta(days=r.randint(-10, 200)))])
    r.shuffle(rows)
    outs.append(_doc(fo, [("h", 1, "Signature withdrawal advisories"), ("p", "Each row withdraws detections of a signature, for the listed signature revisions inclusive, from the withdrawal time onwards."),
                          ("table", "Withdrawn signatures", ["advisory", "vendor", "signature", "revisions", "withdrawn_utc"], rows)]))
    _fill_traps(fo, r, fo.records, ["T11", "T13", "T6"], "withdrawals by vendor, signature and revision range (QPROC section 3)", PLAN_CHECK)
    # copy job report (html)
    fo = FileOut(names["copy"], "html", "COPY", "01", status="ISSUED")
    rows = [[x["job"], x["container"], str(x["copy"]), x["status"], iso_z(x["at"])] for x in R["copyjobs_share"]]
    while len(rows) < N():
        rows.append([f"CJ-{r.randint(100000, 999999)}", f"CT-{r.randint(8000000, 9999999)}", str(r.randint(2, 3)), r.choice(["COMPLETED", "FAILED", "RUNNING"]),
                     iso_z(req_end - dt.timedelta(days=r.randint(-3, 60)))])
    r.shuffle(rows)
    outs.append(_doc(fo, [("h", 1, "Copy job report"), ("table", "Copy jobs", ["copy_job", "container", "copy", "status", "completed_utc"], rows)]))
    _fill_traps(fo, r, fo.records, ["T11", "T6", "T1"], "completed at or before the end of the request date (MEDIAPROC section 2)", PLAN_CHECK)
    # vault status dashboard (html, decoy)
    fo = FileOut(names["dash"], "html", "DASH", "01", status="ISSUED", decoy=True)
    after = {x["media"]: x["vault"] for x in R["dash_after"]}
    rows = []
    vault_now = {m["media"]: R["slots"].get(m["media"], m["home"]) for m in R["media"]}
    for m in R["media"]:
        st = "DESTROYED" if m["media"] in {d["media"] for d in R["destroy"]} else m["status"]
        rows.append([m["media"], after.get(m["media"], vault_now[m["media"]]), st, iso_z(req_end + dt.timedelta(days=3))])
    while len(rows) < N():
        rows.append([f"MD-{r.randint(20000, 39999)}", r.choice(VAULTS), r.choice(["ACTIVE", "ACTIVE", "EXPIRED"]), iso_z(req_end + dt.timedelta(days=3))])
    r.shuffle(rows)
    outs.append(_doc(fo, [("h", 1, "Vault status dashboard"), ("p", "Snapshot of the vault inventory system after the restore request; not for audit use. Vault VLT-OFF3 is onboarded here before it reaches the slot register."),
                          ("table", "Media", ["media_id", "vault", "status", "as_of_utc"], rows)]))
    for i, row in enumerate(rows):
        if row[0] in R["off3"]:
            fo.trap(i, "T13", "VLT-OFF3 rows are of record (AUTH row media.vault)", PLAN_CHECK, "push")
        elif row[0] in after or row[2] == "DESTROYED" and row[0] in R["media_share"]:
            fo.trap(i, "T16" if row[0] in after else "T7", "dashboard values after the request date", PLAN_CHECK, "pull")
    fo.trap("banner", "T14", "dashboard declares itself not for audit", PLAN_CHECK, "push")
    fo.trap("as_of", "T11", "as_of after the end of the request date", PLAN_CHECK, "pull")
    _fill_traps(fo, r, fo.records, ["T16", "T6", "T7", "T1", "T13"], "dashboard rows", PLAN_CHECK, 27)
    return outs


# --------------------------------------------------------------------------- precedence fixtures
# Every adjacent pair of the skip-reason order (RESTORE-SPEC 5.6) and of the exclusion order (RESTORE-SPEC 8) that the
# history above cannot produce on its own gets one object or set where both conditions hold. Drawn from a separate
# stream so the rest of the feed is unchanged.

GLOB_META = set("*?[]")


def _fixture_rng(p: dict) -> Rng:
    return Rng(p["seed"]).fork("precedence-fixtures-" + p["tier"])


def _set_id_between(specs: list[dict], queued: dt.datetime, fx: Rng) -> str:
    ids = {int(s["sid"][3:]): s for s in specs}
    before = max(n for n, s in ids.items() if s["queued"] < queued)
    after = min(n for n, s in ids.items() if s["queued"] > queued)
    return f"BS-{before + 1 + fx.randint(0, max(0, min(after - before - 2, 60))):05d}"


def fixture_failed_after_rp(w: "World", fx: Rng) -> None:
    """A FAILED set after the restore point: AFTER_RP must win over FAILED."""
    p = w.p
    late = next(s for s in w.specs if s.get("late"))
    span = int((late["snap"] - w.rp).total_seconds() // 60)
    snap = floor_s(w.rp + dt.timedelta(minutes=fx.randint(span // 4, span // 2), seconds=fx.randint(0, 59)))
    queued = snap - dt.timedelta(minutes=fx.randint(2, 9), seconds=fx.randint(0, 59))
    spec = {"day": local_wall(snap, p["site_tz"]).date(), "type": "INCR", "job_status": "FAILED", "era": 2, "override": None,
            "crash": None, "fixture": "failed-after-rp", "job_wall": local_wall(snap, p["site_tz"]), "job_at": snap, "snap": snap,
            "queued": queued, "ended": snap + dt.timedelta(minutes=fx.randint(3, 15), seconds=fx.randint(0, 59)),
            "server": p["srv_new"][0], "job_name": p["job_new"]}
    spec["sid"] = _set_id_between(w.specs, queued, fx)
    w.specs.append(spec)
    w.entries[spec["sid"]] = []


def _window_over(R: dict, w: "World", s: dict, fx: Rng) -> None:
    start = s["snap"] - dt.timedelta(minutes=fx.randint(10, 40))
    end = start + dt.timedelta(hours=2)
    assert not any(start <= o["snap"] < end for o in w.specs if o is not s)
    R["events"].append({"uid": f"MW-{fx.hexstr(10)}@ops", "array": w.p["array"], "start": start, "end": end,
                        "impact": "SNAPSHOT-CONSISTENCY", "status": "CONFIRMED", "actual": None, "set": s["sid"]})


def fixture_crash_windows(w: "World", R: dict, fx: Rng) -> None:
    """A CANCELLED set and a completed set before the base inside confirmed windows: CANCELLED beats
    CRASH_INCONSISTENT, and CRASH_INCONSISTENT beats BEFORE_BASE."""
    synth = next(s for s in w.specs if s["type"] == "SYNTH")
    base_snap = w.specs[synth["consolidates"]]["snap"]
    cancelled = [s for s in w.specs if s["job_status"] == "CANCELLED" and not s.get("fixture")]
    early = [s for i, s in enumerate(w.specs) if s["type"] == "INCR" and s["job_status"] == "COMPLETED" and s["era"] == 1
             and not s["override"] and not s["crash"] and i != synth["consolidates"] and s["snap"] < base_snap]
    _window_over(R, w, fx.choice(cancelled), fx)
    _window_over(R, w, fx.choice(early), fx)


def _in_scope(p: dict, path: str) -> bool:
    return any(Share.key(path) == Share.key(i) or Share.key(path).startswith(Share.key(i) + "/") for i in p["includes"])


def fixture_hold_out_of_scope(w: "World", R: dict, fx: Rng) -> None:
    """A DESTROY hold in force over an out-of-scope directory: OUT_OF_SCOPE beats DISPOSED."""
    snap = w.snapshots[R["effective_sid"]]
    keys = [k for k, o in snap["objs"].items()]
    dirs = sorted(v for k, v in snap["dirs"].items() if v.count("/") == 2 and not _in_scope(w.p, v)
                  and any(o.startswith(k + "/") for o in keys))
    R["dispositions_share"].append({"hold": f"RM-{fx.randint(10000, 99999)}", "prefix": fx.choice(dirs), "action": "DESTROY",
                                    "effective": (w.rp - dt.timedelta(days=fx.randint(2, 30))).date().isoformat()})


def fixture_pattern_on_escaping_link(w: "World", R: dict, fx: Rng) -> None:
    """A link whose target leaves the share and whose name a pattern in force matches: EXCLUDED_PATTERN beats
    SYMLINK_ESCAPE. The link is created by the last applied set."""
    p = w.p
    eff = R["effective_sid"]
    snap = w.snapshots[eff]
    eff_spec = next(s for s in w.specs if s["sid"] == eff)
    rp_d = w.rp.date().isoformat()
    holds = [h["prefix"] for h in R["dispositions_share"] if h["action"] == "DESTROY" and h["effective"] <= rp_d]
    names = {k.rsplit("/", 1)[1] for k in snap["objs"]}

    def usable(d: str) -> bool:
        comps = [c.casefold() for c in d.split("/") if c]
        return (_in_scope(p, d) and d.count("/") >= 2 and not GLOB_META & set(d) and "tmp" not in comps
                and not (len(comps) >= 4 and comps[:2] == ["engineering", "projects"] and comps[3] == "build")
                and not any(Share.key(d) == Share.key(h) or Share.key(d).startswith(Share.key(h) + "/") for h in holds))

    folder = fx.choice(sorted(v for v in snap["dirs"].values() if usable(v)))
    while True:
        name = f"{fx.choice([x for x in WORDS if x.isalpha()])} link{fx.randint(100, 999)}"
        if Share.key(name) not in names:
            break
    client = p["clients"][1]
    w.entry_seq += fx.randint(1, 3)
    entries = w.entries[eff]
    entries.append({"eid": f"E-{w.entry_seq:07d}", "sid": eff, "seq": len(entries) + 1, "etype": "L", "client": client["code"],
                    "committed": "Y", "path": f"{folder}/{name}",
                    "target": "/".join([".."] * (folder.count("/") + fx.randint(1, 3))) + "/etc/" + fx.choice(["passwd", "shadow"]),
                    "meta": {"mtime": eff_spec["snap"] - dt.timedelta(minutes=fx.randint(5, 600), microseconds=fx.randint(0, 999_999)),
                             "mode": 0o777, "attrs": None, "owner": f"uid:{fx.choice(p['uids'])}", "client": client["code"]}})
    used = {x["id"] for x in R["patterns_share"]}
    while True:
        pid = f"EX-{1100 + fx.randint(0, 80)}"
        if pid not in used:
            break
    R["patterns_share"].append({"id": pid, "pattern": name, "scope": p["share"],
                                "from": (w.rp - dt.timedelta(days=400)).date().isoformat(), "to": ""})


# Hidden-feed fixtures. They run for the hidden tier only, so the generator still reproduces the shipped feed.


def _hidden_fixture_rng(p: dict) -> Rng:
    return Rng(p["seed"]).fork("hidden-fixtures-" + p["tier"])


def _first_occurrence(t: dt.datetime, tzs: tuple) -> bool:
    return all(from_wall(local_wall(t, z), z) == t for z in tzs)


def _free_set_id(w: "World", queued: dt.datetime, fx: Rng) -> str:
    used = {int(s["sid"][3:]) for s in w.specs}
    before = max(int(s["sid"][3:]) for s in w.specs if s["queued"] < queued)
    after = min((int(s["sid"][3:]) for s in w.specs if s["queued"] > queued), default=before + 900)
    free = [n for n in range(before + 1, after) if n not in used]
    assert free, "no free set identifier between the neighbouring sets"
    return f"BS-{fx.choice(free[:60]):05d}"


def fixture_failed_cancelled_after_anchor(w: "World", fx: Rng) -> None:
    """A FAILED and a CANCELLED incremental between the anchor differential and the next applied incremental.
    Neither breaks the chain (RESTORE-SPEC section 5.5): the incremental after them is still applied, and each is
    skipped with its own status as the reason."""
    p = w.p
    order = sorted(w.specs, key=lambda s: (s["snap"], s["sid"]))
    i = max(k for k, s in enumerate(order) if s["type"] == "DIFF" and s["snap"] <= w.rp
            and s["job_status"] == "COMPLETED" and not s["crash"])
    anchor, nxt = order[i], order[i + 1]
    assert nxt["type"] == "INCR" and nxt["job_status"] == "COMPLETED" and not nxt["crash"] and nxt["snap"] <= w.rp
    lo, hi = anchor["snap"], nxt["snap"]
    span = int((hi - lo).total_seconds())
    assert span > 1800
    tzs = (p["site_tz"], p["srv_new"][1])
    for status, a, b in (("FAILED", 0.15, 0.40), ("CANCELLED", 0.55, 0.80)):
        for _ in range(500):
            snap = floor_s(lo + dt.timedelta(seconds=fx.randint(int(span * a), int(span * b))))
            queued = snap - dt.timedelta(minutes=fx.randint(2, 9), seconds=fx.randint(0, 59))
            run = fx.randint(3, 15) if status == "FAILED" else fx.randint(1, 4)
            ended = snap + dt.timedelta(minutes=run, seconds=fx.randint(0, 59))
            if queued > lo and all(_first_occurrence(x, tzs) for x in (snap, queued, ended)):
                break
        else:
            raise AssertionError("no unambiguous snapshot time between the anchor and the next incremental")
        spec = {"day": local_wall(snap, p["site_tz"]).date(), "type": "INCR", "job_status": status, "era": 2, "override": None,
                "crash": None, "fixture": "rebase-" + status.lower(), "job_wall": local_wall(snap, p["site_tz"]), "job_at": snap,
                "snap": snap, "queued": queued, "ended": ended, "server": p["srv_new"][0], "job_name": p["job_new"]}
        spec["sid"] = _free_set_id(w, queued, fx)
        w.specs.append(spec)
        w.entries[spec["sid"]] = []


def fixture_infected_on_unusable_container(w: "World", R: dict, fx: Rng) -> None:
    """A container with no usable copy holds the versions at the effective point of two files whose versions are
    infected. One has no clean earlier version: QUARANTINED, not UNRECOVERABLE (RESTORE-SPEC section 8 order). The
    other rolls back to a clean earlier version held in another container and is restored (QPROC section 4)."""
    p = w.p
    state = w.snapshots[R["effective_sid"]]["objs"]
    order = sorted(w.specs, key=lambda s: (s["snap"], s["sid"]))
    crash = {s["sid"] for s in order if s["crash"]} | {
        e["set"] for e in R["events"] if e.get("set") and e["array"] == p["array"] and e["status"] == "CONFIRMED"
        and e["impact"] == "SNAPSHOT-CONSISTENCY"}
    ok = [s for s in order if s["snap"] <= w.rp and s["job_status"] == "COMPLETED" and s["sid"] not in crash]
    ok_ids = {s["sid"] for s in ok}
    base = [s for s in ok if s["type"] in ("FULL", "SYNTH")][-1]
    diffs = [s for s in ok if s["type"] == "DIFF" and s["snap"] > base["snap"]]
    anchor = diffs[-1] if diffs else base
    applied = {base["sid"], anchor["sid"]}
    for s in order:
        if s["snap"] <= anchor["snap"] or s["snap"] > w.rp:
            continue
        if s["sid"] in crash and s["job_status"] == "COMPLETED":
            break
        if s["sid"] in ok_ids and s["type"] == "INCR":
            applied.add(s["sid"])
    candidates = applied | {s["sid"] for s in ok if s["snap"] <= anchor["snap"]}
    recs: dict[str, list] = {}
    for s in order:
        if s["sid"] in candidates:
            for e in w.entries[s["sid"]]:
                if e["etype"] == "F" and not e.get("junk") and not e.get("reject"):
                    recs.setdefault(Share.key(e["path"]), []).append((s["sid"] in applied, e))
    flagged = {f["sha"] for f in R["av_final_share"] + R["av_prelim_share"]}
    blocked = ({x["old"] for x in R["repack"]} | {x["new"] for x in R["repack"]} | set(R["ticketed"])
               | {x["container"] for x in R["rerun_share"]})
    holds = [Share.key(h["prefix"]) for h in R["dispositions_share"] if h["action"] == "DESTROY"]
    inodes: dict[int, int] = {}
    for o in state.values():
        if o["kind"] == "file":
            inodes[o["inode"]] = inodes.get(o["inode"], 0) + 1

    def eligible(k: str, o: dict) -> bool:
        last = k.rsplit("/", 1)[1]
        return (o["kind"] == "file" and _in_scope(p, o["path"]) and inodes[o["inode"]] == 1
                and not any(k == h or k.startswith(h + "/") for h in holds)
                and not any(x in k for x in ("~$", ".tmp", "thumbs.db", ".ds_store", "desktop.ini", "core.dump", ".bak", ".hex",
                                             "/build/", "/tmp/", "link"))
                and not k.endswith((".txt", ".log", ".json")) and not (k.startswith("/design/archive/") and k.endswith(".zip"))
                and not (last.startswith("render") and last.endswith(".png"))
                and w.versions[o["vid"]]["sha"] not in flagged)

    singles: dict[str, list] = {}
    rollbacks: dict[str, list] = {}
    held: dict[str, int] = {}
    for k in sorted(state):
        o = state[k]
        rs = recs.get(k, [])
        last_applied = max((i for i, (on_chain, _) in enumerate(rs) if on_chain), default=None)
        if o["kind"] != "file" or last_applied is None or last_applied != len(rs) - 1:
            continue
        eff = rs[last_applied][1]
        if eff["vid"] != o["vid"]:
            continue
        c = eff["container"]
        held[c] = held.get(c, 0) + 1
        if not eligible(k, o):
            continue
        earlier = [e for _, e in rs[:last_applied]]
        if not earlier:
            singles.setdefault(c, []).append(k)
        else:
            prev = earlier[-1]
            if (prev["vid"] != o["vid"] and w.versions[prev["vid"]]["sha"] not in flagged and prev["container"] != c
                    and prev["container"] not in blocked):
                rollbacks.setdefault(c, []).append(k)
    cands = sorted((held[c], c) for c in set(singles) & set(rollbacks) if c not in blocked and c in R["copies"])
    if not cands:
        return
    box = cands[0][1]
    q, rb = fx.choice(singles[box]), fx.choice(rollbacks[box])
    rows = [x for x in R["chk_share"] if x["container"] == box and x["copy"] == 1]
    if not rows:
        exp = fx.hexstr(32)
        rows = [{"container": box, "copy": 1, "expected": exp, "observed": exp, "result": "MATCH",
                 "at": R["req_end"] - dt.timedelta(days=fx.randint(3, 9), minutes=fx.randint(0, 900))}]
        R["chk_share"].append(rows[0])
    for x in rows:
        x["observed"] = fx.hexstr(32)
        x["result"] = "MISMATCH"
    for x in R["copyjobs_share"]:
        if x["container"] == box and x["copy"] >= 2:
            x["status"] = "FAILED"
    created = w.containers[box]["created"]
    final = created >= R["av_cutover"]
    engine = R["engines"][0] if final else R["engines"][1]
    for k, case in ((q, "quarantined-unrecoverable"), (rb, "rollback-unrecoverable")):
        row = {"sha": w.versions[state[k]["vid"]]["sha"], "container": box, "verdict": "INFECTED", "sig": fx.choice(SIGS[:5]),
               "rev": fx.randint(13, 30), "engine": engine["code"],
               "at": R["req_end"] - dt.timedelta(days=fx.randint(0, 3), minutes=fx.randint(0, 1400))}
        (R["av_final_share"] if final else R["av_prelim_share"]).append(row)
        R["av_cases"][k] = case


def _tie_fixture_rng(p: dict) -> Rng:
    return Rng(p["seed"]).fork("tie-fixtures-" + p["tier"])


def fixture_snapshot_tie_in_skipped(w: "World", R: dict, fx: Rng) -> None:
    """A CANCELLED incremental whose snapshot falls in the same second as a completed incremental skipped as
    BEFORE_BASE. It was queued later (so its set identifier is higher) and ended earlier: the skipped list orders
    the two by snapshot, then set identifier (RESTORE-SPEC sections 5.5 and 11.5), so the completed set comes first,
    while ordering the tie by status, skip reason or end time puts the cancelled set first."""
    p = w.p
    synth = next(s for s in w.specs if s["type"] == "SYNTH")
    base_snap = w.specs[synth["consolidates"]]["snap"]
    windows = [(e["actual"] or (e["start"], e["end"])) for e in R["events"] if e["array"] == p["array"]]
    tzs = (p["site_tz"], p["srv_old"][1], p["srv_new"][1])
    snaps = [s["snap"] for s in w.specs]
    cands = [s for i, s in enumerate(w.specs) if s["type"] == "INCR" and s["job_status"] == "COMPLETED" and not s["override"]
             and not s["crash"] and not s.get("fixture") and i != synth["consolidates"] and s["snap"] < base_snap
             and snaps.count(s["snap"]) == 1 and not any(a <= s["snap"] < b for a, b in windows)
             and (s["snap"] - s["queued"]).total_seconds() >= 180]
    x = fx.choice(cands)
    span = int((x["snap"] - x["queued"]).total_seconds())
    for _ in range(500):
        queued = x["queued"] + dt.timedelta(seconds=fx.randint(30, span - 90))
        ended = x["snap"] + dt.timedelta(seconds=fx.randint(40, max(41, int((x["ended"] - x["snap"]).total_seconds()) - 30)))
        if ended < x["ended"] and all(_first_occurrence(t, tzs) for t in (queued, ended)):
            break
    else:
        raise AssertionError("no unambiguous queue and end time for the tied set")
    if x["era"] == 1:
        assert local_wall(queued, p["site_tz"]).date().isoformat() < R["rename_eff"]
    used = {int(s["sid"][3:]) for s in w.specs} | {int(s["sid"][3:]) for s in R["noise_sets"]}
    before = max(int(s["sid"][3:]) for s in w.specs if s["queued"] < queued)
    after = min(int(s["sid"][3:]) for s in w.specs if s["queued"] > queued)
    free = [n for n in range(before + 1, after) if n not in used]
    assert free, "no free set identifier for the tied set"
    spec = {"day": local_wall(x["snap"], p["site_tz"]).date(), "type": "INCR", "job_status": "CANCELLED", "era": x["era"],
            "override": None, "crash": None, "fixture": "snapshot-tie", "job_wall": local_wall(x["snap"], p["site_tz"]),
            "job_at": x["snap"], "snap": x["snap"], "queued": queued, "ended": ended, "server": x["server"],
            "job_name": x["job_name"], "sid": f"BS-{fx.choice(free[:60]):05d}"}
    w.specs.append(spec)
    w.entries[spec["sid"]] = []


def fixture_overlapping_holds(w: "World", R: dict, fx: Rng) -> None:
    """A second DESTROY hold in force on one file under an in-force DESTROY hold, with a higher hold identifier. The
    file is at or under both prefixes and its detail is the lowest hold identifier (RESTORE-SPEC section 8), which
    is the broader hold: taking the most specific prefix or the highest identifier gives the other one."""
    p = w.p
    rp_d = local_wall(w.rp, p["site_tz"]).date().isoformat()
    state = w.snapshots[R["effective_sid"]]["objs"]
    special = set(R["av_cases"])

    def covered(k: str, prefix: str) -> bool:
        h = Share.key(prefix)
        return k == h or k.startswith(h + "/")

    holds = sorted((h for h in R["dispositions_share"] if h["action"] == "DESTROY" and h["effective"] <= rp_d
                    and _in_scope(p, h["prefix"])), key=lambda h: h["hold"])
    for h in holds:
        files = sorted(k for k, o in state.items() if o["kind"] == "file" and covered(k, h["prefix"]) and k not in special)
        if files:
            break
    else:
        raise AssertionError("no in-force DESTROY hold over a restorable file")
    target = state[fx.choice(files)]["path"]
    ids = {x["hold"] for x in R["dispositions_share"]}
    while True:
        hid = f"RM-{fx.randint(int(h['hold'][3:]) + 1, 99999)}"
        if hid not in ids:
            break
    R["dispositions_share"].append({"hold": hid, "prefix": target, "action": "DESTROY",
                                    "effective": (w.rp - dt.timedelta(days=fx.randint(2, 30))).date().isoformat()})


# --------------------------------------------------------------------------- assembling a feed


def feed_names(p: dict) -> dict:
    so, sn = p["srv_old"][0].lower(), p["srv_new"][0].lower()
    arr = p["array"].lower()
    n = {
        "jobs": ["job_history_2026_p1.csv", "job_history_2026_p2.tsv", "job_history_2026_p3.tsv", "job_history_summary.xlsx"],
        "logs": [f"{so}.log", f"{sn}.log.1", f"{sn}.log", f"{sn}-console.log", f"{arr}-events.log"],
        "calmail": ["maintenance_calendar.ics", "vault_notifications.mbox", "job_definitions.xml"],
        "reg": {"host": "host_register.yaml", "cmdb": "host_inventory.yaml", "servers": "backup_servers.yaml",
                "sharereg": "share_registry.yaml", "roots": "share_roots.ini", "slots": "vault_slots.ini",
                "lacct": "local_accounts.ini", "vol": "restore_targets.toml", "excl8": "exclusion_catalogue.toml",
                "excl9": "exclusion_catalogue_next.toml"},
        "media": {"inv1": "media_inventory_lto.xlsx", "inv2": "media_inventory_disk.xlsx", "preview": "media_inventory_current.xlsx",
                  "cmap1": "container_map_p1.parquet", "cmap2": "container_map_p2.parquet", "cmap3": "container_map_p3.parquet",
                  "cmap_v2": "container_map.parquet", "repack": "container_repack.db", "chk": "checksum_audit.csv",
                  "rerun": "checksum_audit_latest.tsv"},
        "av": {"av1": "av_findings_p1.jsonl", "av2": "av_findings_p2.jsonl", "av3": "av_findings_engine2.db",
               "avpre": "av_findings.jsonl", "idmap": "identity_map.db", "ad": "identity_directory.db"},
        "docs": {"spec42": "restore_spec.md", "spec43": "restore_spec_latest.md", "spec41": "restore_specification.docx",
                 "readme": "feed_readme.md", "rrq": "restore_request.docx", "auth": "source_authority_matrix.docx",
                 "pathconv": "path_conventions.docx", "mediaproc": "media_handling_procedure.docx",
                 "qproc": "quarantine_procedure.docx", "fmtguide": "catalog_format_guide.docx"},
        "data": {"err1": "catalog_errata_r1.pdf", "err2": "catalog_errata_r2.pdf", "merrA": "media_errata.pdf",
                 "merrB": "media_errata_revised.pdf", "docreg": "document_control_register.pdf",
                 "idchg": "identity_change_register.pdf", "xfer": "vault_transfer_manifests.pdf",
                 "adv": "av_vendor_advisory.html", "copy": "copy_job_report.html", "dash": "vault_status_dashboard.html"},
    }
    ext = {"csv": "csv", "tsv": "tsv", "jsonl": "jsonl", "json": "json", "txt": "txt", "xml": "xml", "parquet": "parquet", "xlsx": "xlsx"}
    rng = Rng(p["seed"]).fork("catplan-" + p["tier"])
    fmts = list(CAT_FORMATS)
    rng.shuffle(fmts)
    fmts = fmts[:39]
    if fmts[17] != "csv":
        j = fmts.index("csv")
        fmts[17], fmts[j] = fmts[j], fmts[17]
    if fmts[6] != "csv":
        j = next(i for i, f in enumerate(fmts) if f == "csv" and i != 17)
        fmts[6], fmts[j] = fmts[j], fmts[6]
    n["cat"] = [(f"catalog_part_{i + 1:02d}.{ext[f]}", f) for i, f in enumerate(fmts)]
    n["cat_resend"] = "catalog_part_18_tail.jsonl"
    n["cat_fixed"] = "catalog_part_07_fixed.csv"
    return n


def build_feed(seed: int, tier: str) -> tuple:
    p = make_params(seed, tier)
    w = run_world(p, seed)
    fx = _fixture_rng(p)
    hx = _hidden_fixture_rng(p)
    fixture_failed_after_rp(w, fx)
    if tier == "eval":
        fixture_failed_cancelled_after_anchor(w, hx)
    R = build_registers(w)
    fixture_crash_windows(w, R, fx)
    fixture_hold_out_of_scope(w, R, fx)
    mark_entry_flags(w, R)
    fixture_pattern_on_escaping_link(w, R, fx)
    if tier == "eval":
        fixture_infected_on_unusable_container(w, R, hx)
        tx = _tie_fixture_rng(p)
        fixture_snapshot_tie_in_skipped(w, R, tx)
        fixture_overlapping_holds(w, R, tx)
    r = w.rng.fork("assemble")
    names = feed_names(p)
    R["rrq_id"] = f"RQ-{r.randint(10000, 99999)}"
    files: list[FileOut] = []
    cats = build_cat_files(w, R, names["cat"])
    files += cats
    # truncated part 18 and its resend; part 07 and its corrected copy
    p18 = cats[17]
    segs = p18.tables[0]["segments"]
    cols, rows = segs[-1]
    k = max(3, len(rows) // 25)
    tail = rows[-k:]
    segs[-1] = (cols, rows[:-k])
    eid_col = next(i for i, c in enumerate(cols) if c in CAT_ALIASES["entry"])
    R["lost_eids"] = {norm_eid(row[eid_col]) for row in tail}
    res = FileOut(names["cat_resend"], "jsonl", "CAT", "18", status="RESEND", decoy=True)
    rsegs = []
    for scols, srows in segs:
        ix = {c: i for i, c in enumerate(scols)}
        ov = []
        for row in srows:
            y = list(row)
            if r.chance(0.05):
                for c in scols:
                    if c in ("sha256", "content_hash", "digest") and y[ix[c]] not in ("", None):
                        y[ix[c]] = ("sha256:" if str(y[ix[c]]).startswith("sha256:") else "") + r.hexstr(64)
            ov.append(y)
        rsegs.append((scols, ov))
    n_ov = sum(len(x[1]) for x in rsegs)
    rsegs[-1] = (cols, rsegs[-1][1] + tail)
    res.tables.append({"name": "entries", "segments": rsegs})
    res.records = n_ov + len(tail)
    ov = range(n_ov)
    res.opts["resend_cols"] = cols
    res.control["locale"] = p18.control.get("locale", "plain")
    for i in range(0, len(ov), max(1, len(ov) // 12)):
        res.trap(i, "T16" if i % 2 else "T7", "overlapping entries: the ORIGINAL part wins (README section 4)", PLAN_CHECK, "pull")
    for i in range(len(ov), len(ov) + len(tail)):
        if len(res.traps) < 26:
            res.trap(i, r.choice(["T6", "T13", "T1"]), "lost tail: the RESEND part is of record (README section 4)", PLAN_CHECK, "push")
    while len(res.traps) < 27:
        res.trap(r.randint(0, res.records - 1), r.choice(["T6", "T7", "T13", "T16"]), "resend rows", PLAN_CHECK, r.choice(["pull", "push"]))
    files.append(res)
    p07 = cats[6]
    fixd = FileOut(names["cat_fixed"], "csv", "CAT", "07", status="CORRECTED", decoy=True)
    fsegs = []
    for cols_, rows_ in p07.tables[0]["segments"]:
        nr = []
        for row in rows_:
            y = list(row)
            if r.chance(0.03):
                ix = {c: i for i, c in enumerate(cols_)}
                for c in cols_:
                    if (c.startswith("sha") or c in ("content_hash", "digest")) and y[ix[c]]:
                        y[ix[c]] = r.hexstr(64)
            nr.append(y)
        fsegs.append((cols_, nr))
    fixd.tables.append({"name": "entries", "segments": fsegs})
    fixd.records = sum(len(x[1]) for x in fsegs)
    fixd.opts["encoding"] = "utf8"
    fixd.control["locale"] = p07.control.get("locale", "plain")
    for fam, d_ in (("T16", "pull"), ("T7", "pull"), ("T6", "push"), ("T13", "push"), ("T1", "pull"), ("T14", "push")):
        for _ in range(4):
            fixd.trap(r.randint(0, fixd.records - 1), fam, "CORRECTED copies are never catalog sources; source_custody stands in for N/A custody (README section 5)",
                      PLAN_CHECK, d_)
    files.append(fixd)
    files += build_job_files(w, R, names["jobs"])
    files += build_log_files(w, R, names["logs"])
    files += build_cal_mail_jobdef(w, R, names["calmail"])
    files += build_registers_files(w, R, names["reg"])
    files += build_media_files(w, R, names["media"])
    files += build_av_id_files(w, R, names["av"])
    counts: dict[str, int] = {}
    for f in files:
        if f.status == "ORIGINAL":
            counts[f.stream] = counts.get(f.stream, 0) + 1
    counts["ERR"] = 2
    R["part_counts"] = " ".join(f"{s}:{counts[s]}" for s in ("CAT", "JOB", "LOG", "AV", "CMAP", "MEDIA", "ERR"))
    files += build_docs(w, R, names["docs"])
    files += build_data_docs(w, R, names["data"])
    relevant = relevant_tokens(p, w, R)
    for f in files:
        finalize_traps(f, r, relevant)
    for f in files:
        f.control["feed"] = p["feed_id"]
        f.control["of"] = f"{counts.get(f.stream, 1):02d}"
        f.control["records"] = f.records + getattr(f, "lost", 0)
        f.control["custody"] = r.hexstr(16)
    p07.control["custody"] = "N/A"
    fixd.control["source_custody"] = [f for f in files if f is not p07][0].control["custody"] if False else r.hexstr(16)
    R["p07_custody"] = fixd.control["source_custody"]
    for i, f in enumerate(files):
        if f.stream == "EXCL" and f.part == "08":
            f.control["effective_from"] = (local_wall(w.rp, p["site_tz"]).date() - dt.timedelta(days=200)).isoformat()
    graded_by = plan_check(seed, tier)
    for f in files:
        for t in f.traps:
            t["test"] = graded_by
    return p, w, R, files


def norm_eid(v) -> str:
    s = str(v).strip().upper().replace("_", "-")
    s = "".join({"\u0415": "E"}.get(c, c) for c in s)
    num = "".join(ch for ch in s if ch.isdigit())
    return f"E-{int(num):07d}"


def write_feed(files: list[FileOut], out_dir: Path, seed: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    r = Rng(seed).fork("write")
    for f in files:
        path = out_dir / f.name
        fmt = f.fmt
        if fmt == "csv":
            data = write_delimited(f, ",", r)
        elif fmt == "tsv":
            data = write_delimited(f, "\t", r)
        elif fmt == "txt":
            data = write_txt(f)
        elif fmt == "jsonl":
            data = write_jsonl(f)
        elif fmt == "json":
            data = write_json(f)
        elif fmt == "xml":
            data = write_xml(f)
        elif fmt == "parquet":
            data = write_parquet(f)
        elif fmt == "xlsx":
            data = write_xlsx(f, f.opts.get("dialect", {}).get("date1904", False))
        elif fmt == "sqlite":
            write_sqlite(f, path)
            continue
        elif fmt == "log":
            data = write_log(f)
        elif fmt == "yaml":
            data = write_yaml(f)
        elif fmt == "toml":
            data = write_toml(f)
        elif fmt == "ini":
            data = write_ini(f)
        elif fmt == "ics":
            data = write_ics(f, r)
        elif fmt == "mbox":
            data = write_mbox(f)
        elif fmt == "md":
            data = write_md(f)
        elif fmt == "html":
            data = write_html(f)
        elif fmt == "docx":
            data = write_docx(f)
        elif fmt == "pdf":
            data = write_pdf(f)
        else:
            raise ValueError(fmt)
        path.write_bytes(data)


# --------------------------------------------------------------------------- trap bookkeeping and band baits

BAIT_RULE = "near-duplicate keys never match: identifiers compare after the documented normalisation only (FMTGUIDE section 4)"
FILE_FAMILIES = {"SPEC": ["T14", "T11", "T12"], "README": ["T14", "T6", "T7"], "RRQ": ["T11", "T14", "T9"],
                 "AUTH": ["T14", "T7", "T16"], "PATHCONV": ["T9", "T14", "T1"], "MEDIAPROC": ["T14", "T12", "T11"],
                 "QPROC": ["T14", "T11", "T13"], "FMTGUIDE": ["T2", "T4", "T8", "T10"], "ERR": ["T7", "T6", "T5"],
                 "MERR": ["T7", "T6", "T11"], "DOCREG": ["T7", "T11", "T14"], "IDCHG": ["T11", "T7", "T6"],
                 "XFER": ["T11", "T3", "T7"], "ADV": ["T11", "T6", "T3"], "COPY": ["T11", "T6", "T3"],
                 "DASH": ["T16", "T11", "T7"], "VOL": ["T12", "T2", "T11"], "CMAP": ["T2", "T12", "T4", "T3"],
                 "MEDIA": ["T5", "T3", "T8"], "CHK": ["T10", "T5", "T7"], "AV": ["T6", "T15", "T11"],
                 "IDMAP": ["T11", "T7", "T5"], "LOG": ["T3", "T11", "T15", "T10"], "JOB": ["T3", "T10", "T11"],
                 "CAL": ["T3", "T11", "T6"], "MAIL": ["T3", "T11", "T14"], "JOBDEF": ["T13", "T7", "T6"],
                 "HOST": ["T3", "T7", "T16"], "SRV": ["T3", "T11", "T7"], "SHARE": ["T3", "T13", "T7"],
                 "ROOT": ["T9", "T13", "T7"], "SLOT": ["T7", "T11", "T13"], "LACCT": ["T13", "T7", "T5"],
                 "EXCL": ["T11", "T9", "T6"], "REPACK": ["T11", "T13", "T7"], "CAT": ["T8", "T10", "T4", "T3"]}


def relevant_tokens(p: dict, w: World, R: dict) -> list[str]:
    toks = [p["share"], p["array"], p["target_volume"], p["job_new"], p["job_old"]]
    toks += [c["host"] for c in p["clients"]] + [c["code"] for c in p["clients"]]
    toks += [s["sid"] for s in w.specs] + R["media_share"][:40] + sorted(w.containers)[:60]
    toks += [e["code"] for e in R["engines"][:3]] + [s["server"] for s in R["servers"]]
    return sorted(set(toks), key=len, reverse=True)


def _bait_value(v, tok: str, suffix: str):
    if isinstance(v, str) and tok in v:
        return v.replace(tok, tok + suffix)
    if isinstance(v, list):
        return [_bait_value(x, tok, suffix) for x in v]
    if isinstance(v, dict):
        return {k: _bait_value(x, tok, suffix) for k, x in v.items()}
    return v


def _rows_ref(fo: FileOut):
    """(list object that holds the file's main records, offset of that list in record numbering)."""
    if fo.doc:
        tabs = [b for b in fo.doc if b[0] == "table"]
        if not tabs:
            return None, 0
        big = max(tabs, key=lambda b: len(b[3]))
        off = 0
        for b in tabs:
            if b is big:
                break
            off += len(b[3])
        return big[3], off
    if not fo.tables:
        return None, 0
    t = max(fo.tables, key=lambda t: sum(len(s[1]) for s in t["segments"]))
    off = 0
    for t2 in fo.tables:
        if t2 is t:
            break
        off += sum(len(s[1]) for s in t2["segments"])
    return t["segments"][0][1], off


def finalize_traps(fo: FileOut, r: Rng, relevant: list[str]) -> None:
    test = PLAN_CHECK
    fams = FILE_FAMILIES.get(fo.stream, ["T1", "T14", "T11"])
    n_before = fo.records
    rows, off = (None, 0) if fo.stream == "CAT" else _rows_ref(fo)
    if rows is not None and rows and not fo.decoy:
        # one bait per 500-record band: a near-duplicate of a relevant record whose key never matches
        templ = []
        for i, row in enumerate(rows):
            text = json.dumps(row, default=str, ensure_ascii=False) if not isinstance(row, str) else row
            hit = next((t for t in relevant if t in text), None)
            if hit:
                templ.append((i, hit))
            if len(templ) > 200:
                break
        if not templ:
            templ = [(r.randint(0, len(rows) - 1), None) for _ in range(12)]
        if templ:
            bands = math.ceil((fo.records + math.ceil(fo.records / 500)) / 500)
            have = {t["row"] // 500 for t in fo.traps if isinstance(t["row"], int)}
            k = 0
            for b in range(bands):
                if b in have:
                    continue
                i, tok = templ[k % len(templ)]
                k += 1
                src_row = rows[i]
                if tok is None:
                    if isinstance(src_row, list):
                        bait = list(src_row)
                        j = len(bait) - 1 if fo.stream == "PATHCONV" else 0
                        bait[j] = "display" if fo.stream == "PATHCONV" else f"{bait[j]}-DR"
                    elif isinstance(src_row, dict):
                        bait = dict(src_row)
                        first = next(iter(bait))
                        bait[first] = f"{bait[first]}-DR"
                    else:
                        continue
                else:
                    suffix = r.choice(["X", "A", "-DR", "-OLD"]) if tok[-1:].isdigit() else r.choice(["-DR", "-OLD", "-2"])
                    bait = _bait_value(src_row, tok, suffix)
                if fo.stream in ("ROOT", "SLOT") and isinstance(bait, list):
                    bait[0] = f"{bait[0]}{k:03d}b"
                if fo.stream == "LACCT" and isinstance(bait, list):
                    bait[1] = str(7000 + k)
                pos = min(len(rows), max(0, b * 500 + r.randint(0, 499) - off))
                rows.insert(pos, bait)
                fo.records += 1
                fo.trap(pos + off, ["T1", "T13", "T16"][k % 3], BAIT_RULE, test)
    # families and counts
    lo, hi = (26, 10 ** 9) if fo.decoy else (16, 20)
    pool = fams + (["T6", "T7", "T13", "T16"] if fo.decoy else [])
    have_f = {t["family"] for t in fo.traps}
    for f in (["T6", "T7", "T13", "T16"] if fo.decoy else []) + fams:
        if f not in have_f:
            fo.trap("file", f, "file-level property of this " + fo.stream + " file", test, r.choice(["pull", "push"]) if fo.decoy else "")
            have_f.add(f)
    if fo.decoy:
        bands = math.ceil(max(1, fo.records) / 500)
        have = {t["row"] // 500 for t in fo.traps if isinstance(t["row"], int)}
        for b in range(bands):
            if b not in have:
                fo.trap(min(fo.records - 1, b * 500 + r.randint(0, 499)), "T16",
                        "every record of a non-authoritative copy agrees or disagrees with its source of record", test, "pull")
    for f in ["T11", "T7", "T13", "T16", "T6"]:
        if len(have_f) >= (6 if fo.decoy else 4):
            break
        if f not in have_f:
            fo.trap("file", f, "file-level property of this " + fo.stream + " file", test, "pull" if fo.decoy else "")
            have_f.add(f)
    while len(fo.traps) < lo:
        fo.trap(r.randint(0, max(0, fo.records - 1)), r.choice(pool), "documented rule of this " + fo.stream + " file", test,
                r.choice(["pull", "push"]) if fo.decoy else "")
    if len(fo.traps) > hi:
        keep, seen_b, seen_f = [], set(), set()
        for t in fo.traps:
            b = t["row"] // 500 if isinstance(t["row"], int) else None
            if (b is not None and b not in seen_b) or t["family"] not in seen_f:
                keep.append(t)
                if b is not None:
                    seen_b.add(b)
                seen_f.add(t["family"])
        for t in fo.traps:
            if len(keep) >= hi:
                break
            if t not in keep:
                keep.append(t)
        fo.traps = keep[:max(hi, len([t for t in keep]))] if len(keep) > hi else keep


# =========================================================================== verifier checks
# Visible tier: the five deliverables under /app/out are compared, exactly, with the restore the rules give for the
# shipped feed (computed at build time, embedded below: the verifier has no /app/data). Hidden tier: a second feed is
# regenerated here by build_feed/write_feed from the embedded eval_seed with the same documented rules but a different share,
# site, people, dates and draws; the delivered package is run on it and compared with the embedded expectation.
# Embedded data is base64 of zlib-compressed JSON and is never executed.

import ast as _ast
import base64 as _base64
import csv as _vcsv
import functools as _functools
import os as _os
import pwd as _pwd
import re as _re
import shutil as _shutil
import signal as _signal
import stat as _stat
import subprocess as _subprocess
import tempfile as _tempfile
import threading as _threading

from rewardkit import criteria, criterion

OUT = Path("/app/out")
PACKAGE = OUT / "package.zip"
DELIVERABLES = {"manifest": "restore_manifest.csv", "exclusions": "exclusions.csv", "pull": "media_pull_list.csv",
                "chain": "restore_chain.json", "recon": "reconciliation.json"}
COLUMNS = {
    "manifest": ["path", "kind", "size", "allocated", "sha256", "mode", "mtime_utc", "owner", "source_set", "container",
                 "media", "copy", "hardlink_group", "link_target"],
    "exclusions": ["path", "kind", "reason", "detail"],
    "pull": ["media_id", "vault", "copy", "containers", "read_bytes", "read_gib"],
}
CHAIN_KEYS = ["share", "restore_point_utc", "effective_point_utc", "chain", "skipped", "custody_digest"]
RECON_KEYS = ["sets", "objects_at_effective_point", "restored", "excluded", "rolled_back", "bytes_restored",
              "bytes_allocated", "hardlink_groups", "media", "containers", "read_bytes", "custody_digest"]
RUN_TIMEOUT = 300
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_RUNNER = r'''
import runpy, sys
sys.path.insert(0, sys.argv[1] + "/src")
sys.argv = ["restorekit"] + sys.argv[2:]
runpy.run_module("restorekit", run_name="__main__")
'''

_EXPECTED_B64 = "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"
_META_B64 = "eNpVks1qXDEMhd/lrieJLUuyNcu+QrtqKRdZltqBdDLMnaQNIe9epxkK2YiDQN/R38viT3q/bu5j2deCnCFBlt2y/TycTj7Wi2+Xbdm/LP/E3boejofLut6enpf94qUnQwRpYdkyikYPtCbC0QUQqjpmR0bpUtAUhURyr42gN6Jld8XG4c/l8ezb3Y/7h77awzEezr/0aH572Z6mUeQoqaKTigghmxSFoeCalRC6ZvLao0MNsYZqkWhIOChrpaH/jd7i+mayvU+ADdQqUMoZadiYHGKM3rGZc5ikYgFRU8u1eiOrXTqUMVvxMkr6CD7p5ecV3FLGHhXAOLxEDaTCHLOyOXoEJdewKJh8GmVLBtwlYSgn1lQ+gueNHv1KnpSUE2IyEmiImAcNLjWNOppbmksHKzINDKGIEkEMGUg6QpVsed0tT4ft0O991eP228/zvt8Wd0rsBBgc0BrOaTHX4vq2EYHCNHobYqSARnVwYHjSZqWTp95nw/N1+CanG+AvAHvkPcHXmf70+YaYgd8lk7R6lZOLV1kbluX7bjE96vn5+pCYG9TCSPn1LxQBxfU="
_EXTRA_EXPECTED_B64 = "eJzsvUtzXVeWJvZXEGq7nRmVoPZa+40ZJVGVilZKapJZrqzqCsR+SkiSAAsgmamqaM/8C+yBZx2eONyTdnhSow5PNPfvKP8Lf/s8gHvPuffcC+ICREZ0plJJPLj3uWvvs9b3rec/f2bJe2n8Zyf//NmbcH5Wy9W7z07+/p8/exve/fTZyWefPzv/8ey8lMuz8x8/j+H8vFw++an8+bPffPbq7DzjF+rZ64Kvrs7+qeArK9njq/D69UUK70r7BUee2y/8FFgbfJ04eh+Sc6mGWARlpiK9djXYkCpFaak6rY0j8iEHm1K0plrKphifZcRaby5y20wYpdpX787elNP37xK+xYLNMYlj4V+yPBHiRJu/w69c/AnPjR+fn72+enLxKtSLS5LtoS7eX6ZyelXwmT/74sWx1MpYfD9dnL8LZ/3f+fLlsWj/Ue0Hb0o+C/jm777CLmSo+923P7ed8cefwmV+fXb+6vTHy4v3b/FNfK/7+l24/LHb47P/+JvNov3i/dnrfPV5vgz13fG/l7856j+JUk/e5G3CbiISdiJu4xyxWxW4UtXZEoUszFUm47IVEG/IJjgtNRuqWSlSWXCJLuMoAqVajS2sOEq5S+D6WMhjwS+Jm8CFWBX428uzn8OT83B26W4pbsEzcSt9I246iLjfvg7nR8p8/m+In8Sz822CZq+MmshZsjVrYjaaCwRJIpcqTPXOaQ4ed9vGqqk4LVSBuLMLVTqtmFgWZRVJr4LjJFbEbLXecq8lvRT2RNEJ21Uxp5/K+ZNXF38Kr69enflNolbSe7NZ1CT0A9zsUdTh9dufwtGL8sv/HV4fXZXzq4vLI5b05G2u28TvWWg5Eb93Uqg18YeaGJdbicLCUxTGC51C8KYWr5t6CSpUQ0EknYVl6JoSoi9ZSVkCmzXxiwXxuxMpcAIz8bdLzuIxiv5f/8v/86//5X9fuuBGeUVTRaK1NKsSLhQ5wVjopMjVbB3HyhCzVQqiDU4oGZQXsSZBpYTETFGxS4kh8OrLmh7ZIGFqEibaqEf+6aJ0At54tz+dGvn67PLNn8Jl+byenYfXp39/8Tr/w6lQ/OTt+Y/bZE1CaeUmwiaIxK9JO2pnJTltKSVyOagooyxSCQsxSypMHmpdx5CVC8Eo5hSiFNnXHNlL2m0mhTomt1XaP4WcA2zz45T3m7Pz9+/K1ZM/v77aikWMNRMpi1UBk3NBeCmr8yVFYYmSVUUZzykLp1JMMhdrVKLK0M9FN/0BYwnzqBJwy4qA1WazSHQs9EYBXysMqx+nfH/3y399/bpcHv1YwmW8+PPR//u/ltfvwpM/vt1+rZ2X01vNStu1S03SiBRkcdDPPnnLRulYIHgLERtSghIUB1lAFFLO4zdtNmSMdcJBjctdMu+UNPFLQSfQ08yrMn9zFp5ADPkfP5xdves126NBf9dyPw+//F8fyvGH8Br/xh1avODkzBT9TcE2zCDws/MGRgiopAB0ZwmjqCHapJwyXKz1GRYvSWeTilbgGLQpJSZX7Soo2ahFcMP9MfuNl/zD2atrTCLV47znPQA5fvv+zdvjq7clLcEQaYU3egoDgQLlmsiNi5U0gEVVtaRqIgCIg7hF0NVoVYNObHDfoUk8kDluuHaxuMZ/XFYx7QG3LcSxUeR/gloZ6M1DGMrfftv+Lu0v99cXP14cdVbyCf649V57pikamamSKqEjMpBerkzAeQZAm6hQ1t6kkKwHrSkZUhc2wDjG4D1r2QA6rnxUe9hHqBKGmDX0yAnpVTGffQjnN7rE3vZuW5qJWtPB7vaouuP7jN88GrnkEXmxdLsNdPNOCKiz5KIEWzBJDsZKBzTtGSY0iFJBMKN0UgZH4DdJhKzJySDaMqzx13baTDNCQOhvdSLdqtB/fn/1vt5InW5rOe9Xg/9wefHHkt5dff70r744kr6nOYv2EvxETLUJWRbr2gRgRCYAPKGjNaIC+3mgkuqMiZA+RSNhUDVsY80p5GpZKldq+4UA/a13kvdrbwkkTidaza55r04sPypiM5V2f9dPL8uHJ18sm0wppqBwajJdQ9kEvV2crJLZRs8Z97kmH6NVzgoJuKiyhhK3IQayhQEXPVi+BLsse0mc5UsWJ9qe0NodL6/P6pM35edy6f2jFviXT7/6vPz57cXlu9Pv/4cvLs/K+SnQyBLtYVi8HZKHPs/Fh6oDaeNETAriTjGAZ0KXSyOdqcY4YHTi7HASKgconWCyhuksdpfkZUPktBmsdJ7Bd+E8vAqPy32ySfI/Xby/ws+u0TkLscg4oa53iL7UKqTX3jkjm1VNUOfOJBfJhMiGdYUmFxR1tdmDiyr8tq1Reiqiupz3uPSAivQScpf2hNfUzPs3YZC83Sh6TZ0/ZlX0z788BvY1zou5JTX3KvqBePYg5mikofkibVc5gGzGzAm/5MkZaClN9cAo2kOBE14Gp7xo3hQRffUZ4pbZBZKqRAtG6pVIJeO4YsW7IVY9WBuNKzXgKDZf/58g/ydXZ68/BL0JzTyu69+TpBHggKs/efv23Vb5a6dnNGkGbCwx2GatJjC5Ytrld9KHTMJ5trYm6TPnjBetelVq0aBMeFNMlVElymFfMws0KQ3+WZX9xZtweU2UNjpcHpf4G1m6ufl/2qp2JE0v/Zr/BaxIFRtCiEVDsVeV8EXNnsBYgzfGB+NlLLX5ZWCDszASh1CDc5xxIHpfLClkw5LrKqf5AmJJr8olPX47e1nOc7k87UJDp1+G+st/XpK6tWIq9lkEThomU3zx0SZX2AgDZRJgaSFoVly8YF9qyACZwRNbEZyJOSfWUPpuD4Qj3LaA0A7X4uOSfOeGOSJLi8DGKDGLwkFmcl3D4J7HHJWTrILKxpGwkaoCPW3udIdFggc3xTe8jal4wxKwJkBONUjw2V3XXR8Lfcyb3Y1X4TL0sJIeV4BiKvSvLtLVEGU++uvLX/7ll/9Ujv7ul/96eZZ+Woo6EzmxC9VHHSqwo6eQo1O45koW8q5WUNkooPN90hHfg9UNmoD2GbhfWu9UAMDf6ZXh7s7LjeKvEP9PN8zV28d/BoN6P226/nSIHy0ZWemgsSdHoIQ3axqfI8wo68KKMlVnnfZSRW+sC6ZSw/dUhdK5JK2q9EXLmBxeDqVF1nXNyG7R+IKO2Wz3uHevgNnkOHhk4n97cfUOrwDUwZKfzFkzTbYgCHEtLEoBcNGDvkLn4jZ7m4EjNZCk5hRTKoD0sAMiVgvFlCuAT/Kl5IQ3QKcS9wH2sLJQO/ZE6xPimdrplf2mZIvHI/PRZTZEOZbQvNRqV4JLc/f6AuAYlC7CREWkIxiVYcjXBuhz0oETdFbVGTYW8AaEypMA6jc2mV0il8fCHPNm8xpxyzsYz4+bxV7UCkjzy/92iXueT4URT/7p7O1WCysAJWmqXvBd78RaCgYlgH0PXd5SXgArlVBWgkFZITLeggi9TtoKRUqUgjNxViU2VLxnb5JZvewLkBJKHhDeTZxlP15chkHDbAzqPR7Zd16ymxwjXNQlP6XSbpp7MQsyJcHVG5IiKAGlYjLMaEjgWDUkl301hUsikW0qQeckFTUlE4SESVZ+p23tPWbqpdAnbE4Uz73C3ZW3j1TJpJ/C1dXZ1dIN18pO84tmWiWqrLQsHIwzxcLeluJVzaBLggPwH+UYnFbQLKwkJMuwmqCzRqQUvdjJULmL5G3OvrhxS946qrRBxPfgoDm/AFg5HtxiSyZTs5wGOWa3ufkWq4Aa0RHfUtZQlUqAmeoKUWsIWhmRs/akQjTkQnUVFzkpCWUjdvLSDiluCZl2roBe0Jsc7o9A0j/A8gg3JG51eXNL7nanHGvngbNnvt/2Ey/JThIEApCJDTpmAz1StG4ZXTrC6LJP1eOOU9ZsSlYxGmMcG8DJdu9dCo7FTtvJjSXRZpje5yoOPuBNboFHJ/4OK/aeyCGTTgi5FOQjPKfgKVfCd3HJ1/1hlUqqtSZZCrlKACcEikTRGoBHBooEtNHkYUyrKqGS1dExIHuxIlW94iLACdttltQ2S0r6RPipP7hX6Lc9BHOvSQNLhxAvQ3pV3h23APcTYJqtmh4WRk3fhRlozwZIhtmmmqOtKnsbGVKVVegSmq8gRrw+XLRTNktwKqgkr30oXpYoaA+Duh1B7vAEP8534HX4+eL9u0WGatTOyB/4j7aVhQ7C2Bg8oAnhOnvFVnhVJO559NkGW/FNR6GGYKQx3gF2muh3phR0DnjgmE1if3VRz/oU0r8Yob8J5+/D69PeG3/ameAn6erDVua0KX1mzT/w3zJnPu4gRvrapVj357Dkr9SzPL1ZINYq8hGilyZQqVVmJYHnOQoXc47OC8q5WpEjTG/L1eMQLQfofgPD4Xc6DXTLPd2SGtlc8/1B8G1z9D7dq3AF3Z9+OhrcNv0RLCU4Aa3PAoJTIyAqXgZlrTamxVhrESmCOHHINTdYGlq9AUPateI9qUoWGAgD2OStlFbvjIbjBICGNnvLdmV+8OAGeVyn8Mv/fP7j1bvLX/7lzWl/Eqe9XTgluUhxsZCfVxgwEzm1pqCcz+TAp6CBbHBCq+YcBhSCavcxhZaX7bwutZiqtG8ISbBTUilpYKfX0le31xg0Dubbkcg1/8Lr8mNIP/+H/9AdTW+fH2kAZcPJ/Ot//j/+v//zfzl6/m+/WkyJop0sOOC+4x1wFuxBtFx4bx2lIluBQSw+KqEYeFSJAH0UjdO5egiqOu2hrOwKOVvApexekmxZf+snEM7PVzKIH2ucfF36Y6bIZWm5OkekaBGdKrwH01CW8qTXw4fASCWG3PJFUoIdyMV7kZV2lQFMi0tCyZR9KYBOplToq1zb77tSAgzKHhzNH7Pd4YnYmCD16KzDkKqgzGikl6pwwLL81DsxMwtWFQYRDqIyJ6UUsQPzhb024GbGyYojIBA2V12Hj7KyhMMhY62X1u1RPgmzwJvrQjqQ+hfEDW6kPySpjWkLR4PBZmkWY+nQPn6qkiw2WC/VScKW7ArVwELpBHSkAsfQwCznoItUCSAK1KI2DVVTyNZ4SRqEVZJSe2YyiOb/lDgSmpLly4urqzN92/fhgfJht53I1fs3b8Llz0d9cPGoC7UvuUjtzrhLgUTBgWNpOclKFK2Cpxi9NbkAzCrY7hoLl0AuRa6yeMhAVyFNKaByYtcxqBZeFJvfjLsmJ3/i12M4jJZAe1b+dCqAl5bcetZDp8yiAsA6604kLWSMoupItkaO7FyyPtbUKlBgkvGKyAR0BDqHF6MkbSgYX3x1PkXYkD0zaUUz1lKdsD+Qqrrf9PydZ/Hyp/dv4pXWT3LcClid7a3CGl71sNTrnmwrLFsjVYiw1QTepgx0kILdKEkmCNVmD8omInBLdppCK8WPLVJWrIk7i39W4jL4R81TTh517Hdd/oCmLTbWUbchyWrJj8pW6pmpliTs2gEQmwRN3/LXuPOQWugjU8AhAgEjMbiEdYb7qDsnE3JLv2UQh64qa+cLoI6Jj+V2h0ZnGDZlmzw6uzCIfyTQ3cuw5ExSLHd588COjVBQMzVEnwpbyBCUughboW69ZgIy9SxDMSU4L4V1LuLidxFM5/Ret1/YVhCup7Uql+HD2SD927aZ+CSWYBD/5cW7izEL4oi0XXoFrGc7iyRYaBheg6sqsUjVKfxb+dLeALwlURpXcQopUadvPRtToXmM0M4J274bNDBSkauvwLa0N7kNrvZGuc/zfFz1nluOoYvMjw7VD3z0q7bbr08FWNvCu0AGmn8W05lVEgmZtDSZbc0WQNWBHhittfU+BzYFjA0mWMjicgiQPHGtLoBtGzLKuA597YBH2+udd1iDR/c+tFLQo+sDOGLm5diCMG5n7RyQUHAE9VJMltA+XnhRvY6NI1RXWzp/5lRCNllXRVEI9j5BMxmcTFyvbhFbnUf8ktSJdidKz7LfHmGDijXxW39drDjG047aOt1xD3K/+vlN+9aN6Kf3fs1ftyKyZW8P9DedqI3+tl6JNNmpfVPFVyR2Iymxl6Q+/6pcnf14/vnzLue7S9k57kE53i7X6ePby7KrkzhuRUJLPulWYDstEyJllV5PY9aA58ab5qpQJnsH+mQl7KuqEkCeY/KueCgYB03C1MgVlHnMGugyKbXe5WbrLbYvm/fNnCizRYuoR5reNpV9yyLv5b/k+JHGz91u0+zZoKjhE/Aob7XGaZEugDO2sGzNcDy+TbLYlmyVUytdaY6i5GRgCSW+u+BZdtHJzZa0eRk6r9sj1t5TsXctWY7J2mUqS95PQzFW2vUOWrHkXCpwoQqltGQr1QiSi1yNzhZKOkvbMiZsDpZqtclmp4BgLOBMsbzm97fbWju1lKDO66xpXQ+dh5vqoNveejMTv7Cf3QuVnYp/6PD0q4vX+deLPmc3M51TJA/NESDaWlvHGygdo4WFuilJQYWQy944mTMYa7LE0D659QMgnKzB79uwB3IRZlth3GJc/hGKvgu3aPHfH12l8Loc9zW6S3417/Qe+SipEVZbpOGgOHZ9WoTwIQoqTtRUraumpZQrKbOH/iET8esOGgvk1+1SPdxAPG0ORXYH0CfuP2KP/+wIBqW/FO2yblapNetyYYASQVUbgfJFa7wIUeNblTxVa3QBEvQuuChzJY6lcjZ4NUoNyhknympKxHLEsdnaE5IL8a5NyFFq47e60eYvwENY3E76Xa3c0dn5h4uzVI5g/Rb5E9PONjpVaB1T9KyEpCpgc62KMoTmM8tZ2AA2lZy3okD5GM0cXCYLPqtDNGE9LXHrMbjWs7JhUT1N6b9uo3Pr0qFPqIX6nmhDa4Y+4LIEgjxY/6xQ1xOu7bpDwQuZueZQshOiRA4hShWydkJxkpHBV61XOkgQ2CycMTrhqBQzvmFj3aWL+mCLa05NDV0k5w6FHoGa2/rVzPwo7is5cXYUfR4EzJw9+lV3LL9eaCvqdhbT1Vqka3heixRMaj1hfNLJF+db07pgvZZZplZsZLJtnbsyG1m1CrFIKfZs4aobHsI/yk9fh84eP67+rVvlP0bgeeS0i+VFjjRtinOtp6GY1n9OZLwByRlI2xq8DSXbCtipSUlXNd6EyIllVa1nIMiAC5mBToGbeD+j4FuzBhZQSDNz3Hk2N7ZQe4S66OYAOrf+UXf/Fw8BTFlPmfDMMnvPTgDnU+VAWkEVeWdqAB4NeDWUgW1gpRhWoOUWRe3wL87O4YUwOced3RrGDOkWXPET9/Jy0PdRn8FuQCqt89M00RkZLhlHhEufgT+yz65Ea1pX0pqVNuxCyKKqBmMjTDPJLIol2O3gfQAwimpfRiaow0V2mqG4DIse9Qn0abtHQ0pW9zYckebF+mrt5w1MpiTBOQeJqwj1k1s3sMBVc0meZAquUDTWSYYJziAFDqzBm6yY8O5o7T2t+ScWPUMkWj8HJWckuc9XNLfOivvUB9JHXYYMlUU/s7V2nkINfsXraYoQK8WcqnSGc6lSRgNIxJFZkAaDSGSbe0glKhocQUhh2Fb2Ce8TzEhYO4mtnahF60Td3KZ+cx71XwpWvTmIoRnkoKL+eHWxPVMLXHcKVWcvhCkgzbpqUUGfTYnVhgL76zM0UpYWNCH6rL3LyucivCa2MBI5tOzdSKu5igvHMLwQZlJD8xepo8Y89i4MNrSJXNBKcndKkNJJs6dUtIIBgI3IIqfW5rRC3BKn0eqKW1MI60KqojrpmspyxNJFwTuBapequCWHekfTjUXHxRyqdh287ln+nSI6HnKBjknaJTPtWM5ijtM3oCZhkmEtYIx9Cye2EmDAoAJEZChnSaZIA5qcWm1Tja41MDQtbY6c1mWPELxw2/If7pIp+mnEfxPwHTjz2ISDnDj61Qf+9WKNPHD/jpeh3X5vU7Y4jQg4G4PzwUoFhmYsU8o1tCbA2ccqfVRQXzm21mK2FXUD3u7CTNTcqFvKa/rq+A6zbgxBLh2HntfXPIQbb0iDGHvsDb0KFmES6NWs5/iGlp5UnOMqbFGCqpGgxjKmHEm3bC1AV89ZCFedNtEW0wqhtJVacswqpN1tDrlrc7hQ3dcdg7l1odmDvRXGiDEQP/QCYh4mo1x7thfPAfbSq1ksU4AIqHW/dmvvSS26E3N2OlRf8Ea0ArPQegLBdrQSHE1CBQ4tPcUI7dnDrBtTfN2pn2RXbby54O/dxZtw1Xsybp1L/WlPoncmHfU+VpjPxaPwPCt3nVHpZKUJtmUpGpVC63FY2OuiVAQ9UDmATbfqp5xkKErCqIgM2x2yNKXGymbXMZiu8eHmyOZ1wxR12wyhh1NLG09hMA59q/hlsCq8mLdPwXftJMxJAD1sPBeooixlTtpncAJRG4KlAsMB8sYp1lYKK1Jr8CxzNS11DiBXrpT9bS2u6ZuAqhMtJxNsRree3xhn+/QtQLcdw1hYsLMvH0njpynTc8AEpmBLLVGAsDkXq87FJSmNCN5mRZHBF6KROqgCnVRN5Wa+waGNggFRu9+E5lTy7QR4Gu65awp7F577dAfRdxQib5bbN3W9yyfHIIWk9SAD7q9ztvlZaw0esBXC1rqCRrTkOVcMlqmia5MVSlBcszAaXK9KQF3tdgYZusTdLW0o/nJNdM/b1tqDLoTdjJ537ZvPHAINSJZKTEbakn0xRsIqGAvzWygpEDfrjasmJJNYyka2tcTb0QxH3N2MZYw0tGbc4oTXvKz/+P7sfHRmbFRLj+4oWt5FQ0gvvnz67bMnv332t1tfA5pnjM4GmlGB3rVOOy+lJxE1XoaqQhVApQHsrArKRhcwaRKikTwRgwqm2sQe8JZ3vQRjpA0vgdInckNbp4VI2+NwX0xk3xmB4x6p3hQjL4TaYBR4NniLpGezpo7A7QrsbNceoRWNQdHkXFoCQSvOD5xaK0UfOenG7Yq1Rgew6iKThvl2e56EbHXHik6knamj/iDotiHPTwKR2kF0xuBo6AqyhI1AABRvHO23PitKt8zd0roommwIWKi2Y7CtW70gAjr1IapWWcNCp1acYzX0T8qKcU/tTnugO3uwufnW3cbofCo1NMT7F7OmZyVM6zKn1vgf1xiIKLURftZTFWADXEhppSw5H6ULQKXNYeprxrH52mIKFoh0p+9OduV8m8nZnsm/j07yQ6u5Iya3mHrkAYJmE3aEcmLtBCRAqFWANRHSyqqhH6VSm6ljsqQicMVb2R5kbXHzQ21VyCAE2ZUMeqz9rhMYRyq2JlDTDt1dxnpve29daP8p1P9AisfJL8e7SiidV9pNY2oeumQ91C+g1aWtvvX4V60jOkibKUQgCXgrdA6tnLJ1mAi+ahtz1MCl0SgBBARgtNYSx2xL+qXNtfY7Qv2PTvHfHMFIyoamaINHe9EQ4O7Om3jPHBVZMLGKUmtfYxXB+UJ4PZxOoUWaZc1tqpowweZ2Gmx0OxCdqq+tyfHKaWwPcQrb0sCkP5GHOo2Hy3zZeBp9/cJiaygpLc0mq0nt1sspfQ3KusptHKNLMbpSszbCZREpNo9cCMSAQz4Jm5KSRpaQCg4sq+r3aIFJC/2huoq+vjegv23m0Sd+G27iCtfe09M+Nw8YZsl5x5D2LDWStfTr/UAcwGEBZmWvuHU0CNIGEOOkYDdStKI5ta3XSdRWkZl0tOSLTiqEqnHEO50WvaHeXFh2l4Hen+RYOmS6OGtayFkkZ6aItHe2TXm1bD3kSxRLq+aGIQigwNqk1ogUkBQ0rAjCy2DYk4zZ62hC2D0ctm+TuTAqZoEQLPaG+hSgqJ+fcXxdBmV3GAKt5FQXdQew3steiwJ9VCIQfpTQPE3bOBCu7FSuzntofGVMED4rvBHGUYLRCG2cvcqFd9YkjL0N2uxBmII1T93HD1V/uNYGq/Lv8lskfT6E0rppm0uxzFatNG+SOYujkaq5pQzjwHypHMEKalUutdZbga1rfjagp+qdKt2MdQGWIKOGfkqexE54yp3e2eyku8MA30/yCoxHMKZYdIM4x37JC1XezotZHG3qtC5SFpLUMrElwGiQ3gaFN0HJoiJVnWGwYaSDTjE4VQ1lLVm24ewEsMrr3omF5Hi8B5omJYFdjUIX5efHmwq5dBBD+5sRsYKZLRVpgtcRz/qY4rt24jFKBGZsdHCtmpg9UKtslKziHCQIAqXYmnfV1rCXiqmBZAgqhwQNlaupe7b+kK1yVokTfdu6kcd7Lt3Ak95iLAYSgFfnQ93mraFgJC1D11TnIGAJ8cc2x023KqqkawEpY/A1m0skHCN4g7eRpI0OvJv9zghzP2R8c2izS0DqGcNfhPPi+gwG2jaU7yy4T72aO0+n2kmzKCW2Ge8Cyj+GZGV2XHUbrGStzsa1ch5bob1Sak30BQx3cdYk2Hc2e8wJFtwNQNnaUfxjDPVjOIAFwSueNaqbdePSvnXwKAnwPzFFHyXEL1UVSSjtUgkwAjVkJZ0unERLBRZtXLCBnQ+763T6xh+byVrLfuy52q1byH4Kufe+0tOVJlxPvlhOx7ZtjtL05mtHYr1YHxQLBEwFBZlC8XMuoabQoKm0sjoGQeCC77ogWgyn5T7q1GpqoxM1rNXpLGSgcvNXKN5YK/WRgzk+hQkYvURLXjvoAyVnpSGGaT2vyJTCbXyesJ6s1NAzBbTPkYkGf711BcS3jSGqTsZUmWQJCvjUq0Kpd4vvbrWyZdZbxu3pW964x5t2uiL2Ln/lenTH0jhJpc2sVF9q5smdt6DALFWUWcHagqRm23wNrmrRyqFMUk7nYlNokRodybuAPzsLE5Et7XQSdXpni5PoDr2raZ7Gcv9Xfhit1/ryHl37ho6AMRdUv1F2NultFrb3qWUttja8kHVQJBrtwlE0FiBD84vCBNdUmn9CcaA2ocmCOrSQZQ1rlGChPIdbHouiyQztPmzf4Z69O7Z8UsXTJ5oe93kUx6310DLy7KM0S7YXFBdkWBdpAseiEgCQry2s3Mrx23BhWQtQkFcyZ/yaU9rCFLSBtqpkvxv9d+4hsTlqcAf983DvgFN09PSvvrhplDCWQ3WNn/AkSx4626rAZ11hZ53PcP2jAciP0Pu62ByjsylzMVxzYw+t8ZOzPjq2MtQSZQJFiEITafyF3SOFucWMF/q1LIzUflyH0I107lrmLyRKCG/9bBAZQIue1MaC11JyLsnS6qtjoiykKjJWy61jTqZQQsKfbIIIPbVGiy3jruU8diGzValvCphdt2rxJ2xPmGae0SFG8Hg1z6rYO2WzBHjI0y5lg3+nDsXHli7aKC30DWnpRNRaC2O5OK9NSZSkbK2pDV6I1pY9W2ilut/o7GFe1rQj1F9Ib4RVkQ+KBiufl6vFBDnLO1tcKh8Sl+pN6wgC2GNYilYUW61vybqx5qKyLBHWJmaOshEyo6KWrCPu/Jrot3reVJcdp0/0TPTbE3Yfldi7Fght+GE3IGUo5Dgitot2lqTcNfgQLCnWZDJMKPtsFCsbbbJV6xqg/lkZaV2bYCt0V/PUgsY26xSshhEoO2vAVZuTsiUMs2OQ9uNS8d0JDP6cUzJyQdNr0dD7RPAaTGo9Qxe4xVqlslVGQJWIpAE4ocopV+gYK4AqcToGEJQUkCj70KIfUPZK4Ke7ZzV1PaG2uHUmmdL+1r3oPs0b0Hz+x31brsWBn2Y2VXh676Vo3bVy9kK2qlXTZpvYkGAxWzMEvDgihQydL1TyQeKMsrbMAn/S7EvgXfe+z4PAvdcngicFxh/diu7hwr1rUm86Z5igPRb07ZgmPze582nyBLTiVCRgUSpet5hrBVlvdd4gWDZmoXTQribRev8Zjk6yVQCaJbRRTrTvCQhqrb3Jz/zKQ8z9tsOBPpHq6Y3ukk9NKzt1qM3a0FWAUAVAmQKsaLBShyqSygChYLlSKdBY562pTb9rQUStTTsWwUsQdVxrcLCd1LqXTK315Tq0vFPrywdXN52maa1LWbrl6OLUlzZjslwpmtZctKX92+atlAHoBYQ2ZBmFU7YN04JqD+1+e9XGowDk+Bp8DGv5bxvvuWzenC2t/3bd88dlYp93WVaff/Pd33z/zZfPjr/9/q+/P37x7LsX3z8HiHBP8PW2U2gNs6YGd+bRUakl+YSi2MtirHBE3mRRACRzSz1sjWI5AdRQlqSrzr511lQ+U1Va0c4WgH0KOr0ExJc0yXdoGdCDW+22gayHV/rDOQxdVtpC6kbwH92+eCFHRLUO9BKW0kzhYd81cd82TSuCuhHQnl2LV4XSpRb0zRtaJPsjZNfXEZE2i9RU0axN0FR7pJIi/mNrilppkFThU2v930qDCnFp1xiQUAd2JUKHt7ahkskmoHqZxX4jAIZeca1f8YHw+cN1ipsKvgUATweCdNpf4eUpDBubla0eQcDNNa7q6lU2qZCOEDPrihNIMJAtxKCgrEm15n1VG+9b+n7gzAaMyrhd7wB34dfNXrCuBcRQQ3TbNJ1PpsCHet6FaYVkteOp3Ln1GVtPlxXRA40LySBERhsFTqq8zcFnAEGgc5kZsMVUk1q+mg1VeiD6HIvCKRS7Tzlvp35a/xk9Gb/T5Ud1wT+5SfKPC64Mkh/98MMoZya1PCtv1jd3TXlXmbqp2SoXbUuD5i7G7FRyusqYA3EtrYZOEtloszJUJG6qc7mlK8edCL3LTtsS/96HoD6uyz/I/qa9w1K3dKZZ8HtWvNhUPwkBFsrelCLavIuUQUyqdVnIFADUtc4WKknJqDmkElOqZCUlqJ59ZgmbbYUTd2jt8GCS1+CMR10y8tiX8rRzBi+gda3dToqUXRJR6liSwZUn4EIVg+dqSAYnkoDichHsSAaTi2jOefYtdT9rJ/PuHvUjLW1d0qe09E51cg+GE1fk3rzBzSvpxVAi0aNFfQC4uNB+gRvEZnOiN2iMUXwb6Y4yqlMkh8KMvwuXuHW9eMrV1TVibvCRpd531sUGgY59n4cW9DCLy45eJ9SGdm6uG9G1KmBXpZLQDcYXEpySEewSyKlu46Kgtfv2GDIlL1vbfy8AfHCNsq5saij7leG2bmLuhNskgNlE5h7L+Fv7e+d90O+nM8PkLIZqxFOcyWlXFL04Us0KOwM107oHB33im1OrqEpOKpVr4aiUi22SV+siZiI3rGmTq8bZDOoLvppKsG2I/D4TBfsOJaLN9FL2Ly3VeHIAfXPP/t89rlwqwlKe9sivcVpK3GnvK7ZJzSYIG2KbyJAilH9SuWV4+MxRJx2pCFiBHJMtIGIh2LVmPdvHGOnWXFLhJdCbHQEb0+4f4xEMNQ+LuZRiVy5lBksybG0Gey1SMo4qgbwmqcFYjUiOdCJAGoVbDnxZEngZqSA8QJAUeSWfbAHJt0Jce9I1wviLC2pPhD4GV5caL1iIdt55wZrJdQ/4PWdUiIm9TMUkDcwagOuNdrj12XMSXgWlRculycl2vdF11olr7QnZbh9Oa2HoWskn326GpugyFDZKXn4ayQ+m93jsorfY6BnPOdX4MxwPURtKIKu+apVCDcLqak0RwJSxcnP71ghzLH10oE3S6JqCKl524fCwOnpnW3FhY1IHTiP+VBZ36Hix5LKROzO3cZOrEzoG1xlTBletPrRmX0Dq1PrvcILWaUFAKPfY2l1UitV5rahKvdPI6q7M9sCDpj6VxFt477jv+zIEmRaUjvfOzzDOrO1CaEXLKRsRyAQBOqpcYdU1NC+KASRFMhC9tiKDbmVjRImayDmFl0LlnVe+K3Neinl8XM3IpzqBv+GjX335/Q9/+PUY7nj+b79a6n3UJLDjDTBGCldhcEtp+cPFKwK6AYNlzbXo1sgZgq5eVgXjC9xUIsB+tfguB7Vb6VxP3aGWvroOM3cVmj9Ge9vf/OvOwWPhzoLub3lhM9gzz/IAqi86ZRWLYUi6At6IAGijc8a3PDAn3o1SUgXEjBKn6E3JyoUoUq54U/ZQRdS10N5W8d/3Ybu1/+wTvAqDC2GsKxwHaDLpxamPuEyzNLO5Skotv8z47NhSBtTpuhuB+2ariwZCUlU2Dt1OJsY2nC3j98DJqsQbA/uw1wvRz1IW0wZUN0VU/tYJxZ/gHAZncvNDDP6HriHM4iFo5WYl511PxzUoBNLrSFLOIMGmxEAhR10yF2cE/qRx4/G+t5Q0kK3acgFdIR2kD81LkVZfho3dR3Trps2bodAf3y9143mkZzBMelnoySm8nSX5ESnj1gSvVEuqAY2teFvw5+SJbIKEW/V/q6KCLQgGzFfhyHRp3UgE+4DbT5lD3W/cUWu/Jk+6kTuHdOV/CsfmIP6+rG0Y5n5EarmymeXU9zCbOkXMlYuqXsQ2846N8V5bYyVAkE/t/zzeD5cC+Zp88trjK1upitaoamdFoRyt8v00BHugFwHo57pxfB+FXxx9x0qqmeuT2U0MQAQHjUVBAyXb2nv5Vs5cdCjFihhqZcWknA4+xRbLFSm22bOlZZuBMeh90i3ltjrmC4CKnhS4W6fhPIzMB/wztmTuxb6gd7SnXYlPrqUzAdk771pKfcurEeC+uOGtZhC8y+Uu49JWg9tt26sQSpQeRNm1DoUrAt/od1gqY3u8TXUGldI3W17qLSuBBKeK3ciWnbem2GOhakl7Fa0hbs1CDKdafIg5WR9lDRG2wIbKsKpBJmoCzqaNeSyV9vRlyobztZ3Ux3bJCT28fFQo/8Xb0saXDjHBlS6mS7NAjDDzoYEGoGb9TuM2S1FTiZwkxRRgfqtNKRoPMEMQP/vW2Tp40dJF2ngvMtnLEJsHWe/RVbn5cjZ3dLxLG9P71SK9wMfk+L4K8BTmcHlostplLU2UAhe4jVKxxguo6RSFMmQKy4BbLFnqEp2RlJqGAcHFuTiptKCavd0ZAG+S7u72QbvjPISou/Sy46Er1JAPv9SnlOSsB85U2C3ZEVfU6DaGvUZcaAF+WhqPSrbLzxawl7p51WA9q/XK22Kyqa5ViawVXG5L9lDbXDaP1GXWy3po5dG3NFhKanLWztqyz3zBMiSbc2EWyYRW42ESJCmLxFtdiLIH9GNmaq2POZbEybKEvCX4UA07c8lM1/BpMwC8S1nrQ8h51TAuMR4367M4CzZBa8jiW44et+40uXUuc4EzGCZ0ijLBOchaG/K6i/lB/LK19LNVOjI7o9xd73verKUXp60v1hU8gIz7HKUeVI8tgpa6dJDaVTqZW1OOZg0hRuk5BddyrEWF0K2K5EIrmM/dgKA2biOC7XAQqQRnlS9uzzm6ndpgNymd7Nxb/Y2+dXb7/YK8l+Xq3dHz0obwjXPUex/K0e7iJSm8mCeHEfF6WyZQeaUqJ8qptc5yigpMZQDGS8xQMQDfIDBOFF+SNA603oPIO0HFsIlmJTVyoTFKK58xHaP3M8H3SMTd1jw+oOCvI3iLzRIF+53NKm1MNajQpr95yB2axVUgPWvxZ6HwXw/TqEzSIVBzsUjjwfNbkLsmqJm1cZTb62ZM60U2q1K9ceK6x+VMX5N1bx6X8B7hgXYOnNTaZwPmIpWTwN64w9okIw1brkWSrZF1NNoDbhsDqymV0iDu0RPhw8lVQW8rllHb2j6s9ut+XJ6RdUl3Ge5dk7ebtrjADIv9HmjWqH4WMgUrL1I41m1UDMF2pmprCMUDl7SEa9/GEEdDUelsRDsImaBalJY6h7AnkTQtKUbISaf0x9to6eXFxeurz/8NQdCwmb9eTsLjnVWntQ0Llj61SBAUh1bVO+tFIePbyM6S8L/c2nuGaHPVkRUofKRkuoEktAZMtrd26LpZaT4hPRfyAABvmwZD866rB+y/3Ut5mF071G4cD03o9eIIzxZ2mMXg7GRGntedN7s4XUQgr9qsQjIaepqgqdv1xjHkUqhwJI+TKbj7CZe/1DbFbcURtZB71EI/qiU9Kj0P/Vw7v83jij0Mgu8HXSz1cZiVs8+KZGxlSkrmNp4ZSAOYr2bLuSgTuxlfxQB/N5ztDYSsoo/Q6VAr7GTydid9VMPYr219BLYXin1CMNJJd+iWMbZH7dvELDm0pXXz5jwEQ6kmwbTgcKtbI1RrZYpC41Jbn33wtrVzdoajZs41lpbYW1SSvvVJclAwDa/vEdFsrRs2c8m71CXxvY67G0u/BnmfdmrkFIx6sU08tNk8kwvf5UkcrTiIsg3QVNrLhjpCAYOXrH3KNRtlS7GOQ4ItNdGDdUKntDsPlcNKhJ2dYvqeDdsmulxPiLe3xSeHl/k0970lvZ8Kp5a0dWt0MdXWytO6i5Wr1LKSjK3hlwW4aGksnNuQBMZNFwUG02UDYF3ayNlsSm3tNkCDqBWy74SAfajSts4M5E/EVht5W11i5rrkjiWP+5QXbHWSOHKzKYEtwYrWm8BDr+QkcG4A3lDRURVhcbGDk7EbmEnalqxB6aW0kSnmxjOZgzUKSl7v119TilZfKoH8+FB5uYcHJDNpDxHIv7785V9++U/l6FddLP7XywUAjmf9AAhaer2tWuiEGEAFIUOrlQKsloGgoXWUBcwmxOKraX0HY65VKxuUa10GS61ZxZ22UjYlwpunJ489j/jTR8WmAr+2kH20/e0F9PglCLxY5O8OenSquLshRGs6RVQw+jaDi6WHDE3yJcZSoJm7nNCWcculzenL3javIaAKmRyjFfhNvWfpv+qmz6kT5aYpuB/ZUfP+Zd5NuhzyrnoquQxNvJjKekbhTfOpFmONFG3mFpRgSAGU0RjXQo5eWgEACIwtPduGu2MrW7TRGE4U8p4V66bLPDST6orORPbqW926fm4+/PWOrWOnwm7Vicc92B4D7cvluW2E7tRcCr+uwD1wXq7FZqucxyWu0RYtXRsG5YOyVG1rHxBhTnUMyeU2e6iqNvivZfyYnaPYqWvUuznKfoc5r3xwa/kCv1/y578N5/niQ7ns2+D3vtdlvxTPwPasEbgTpjhpZJSko0rMzZGtgyFwSlBFfK9l7SgXpQb/MaIadrCQseBTlbV08gVI0rUqkmZCIDsZN42tbyviw08zHkT8srx5+xqiuhom2g9MXfCOqTSG5Qxiz0YxtbQbV52WRFokZ4spvtgUXc5Vy1KChLCjbYOdNPi7avEdl0kWl6w3vGf9reuKs/hE0xz+LYxsXbzR83oVuyJueQBx9wDwurxfWLXokGojx+cZygCAkwEPWqfYcnKKcFZKYJI2BkhqH5MIwHwByrkVPVuhggI+cSA90rnsvSrQIuvDr5bK4Tr3CJmZwh5rdm/bhrEfFn5IjT2TeMfWj/qw2XI/e71lNvq6ss4+p5h81M7bAJZOWgWmovHotY1gKm08q9eUq5UuatsmJ1KbQhPYxrza2nUBbXfFn0pPnKxdYLJ3k9wabN+/oLv4wWkf/F3MZFC+T8lZTjSGLvYwlUoKy4B9orTqEgBApbNuaZU62uScsCYGlwUMbWmDxkyMuSSWdS1PZ7s3u4uOKbtRi3ycN/tAkv6H33xW/pxev786uzi/+uzk728E/1W5Ovvx/PMuAjwU/TBt6SJ6WULT5yefff/7l6fff3364svvf3iG7+eC5349PdJh5ad/tXnww0ct1sdM26frcpxnPQU+7gkv009nH0rn1b/sgipHO3LE7rRNr0LG0QwHFPSwfpewjEOUm9+bO63dYaje6pwOE1UOLp8V2W+KYN1p7SHfYaDwp10jS7K0Gad83E5XeK+7CNHxdTTu2lVwwMPut7lp9t6cQIdfv0/d29yz7C7r9jhxyDEm5568+/O7g27w26fPv3v24sXR82c/fP/85RFJu7Fd4F22GFty9K3dhrkTm0ol77LJ8K6NTuzeFXI4fTrs0rtWTodS202tXD9q9S8uwb0+j+/PXucn794cSE30i3aW6rSPnWwqwbjD0rlcvXp38fbJ2fnZIZcddc7YQWQorT3ww3dtSof43aacuTssPdy9wxmVftnOXB0JmKsDi6JfuMuO2OjDusPSXYV0+XODCoezUf3SXU+TI2HsoY9vMH1jUnafn3MwkX95cZ7KW6iSHkgOl/xwcr9eP11clif5/aG0yfW6B3/rr1ceOnccDfmsYxIabJI5nCK/3m3wknf68WjINGTmjVGKu+00ZJv3prx1Nt3oVPuoPcYQyzBJtK82PZziGSZzdeMSDgdthjDFWBsoxOFu//NO1N3Ah+PeOX8M+nq4Mx3X7+HeiGWOSNHhNMS4x6AabvoiXtcrHPrTDC71ji52CU6HoYvj8oM9PNytHxceaqyHaffcDvpgV399j9PBKAjtN2Yg32mLEREf7C24KbzAC3C4izmkmQ26Zgh6Hcyq9z3KDkDMVnNavmiQ+oaBNMfFdW7z4mv073//9PnT715+892zr1Y38sEq0drm+qpqzCpyMjm2TixF1hhMS9mvIoaiWtSOk1Bt8nUOTkfKSvhdDzpchdbG5LgHHot879nffvnt77969tXpD09fvnz2/LvVR332t8fUkka27fj12eWbP4XLMqrjvlNc65/yMYKJMbItbTxdYO3bHJCck0344Czxf7EIJ0qrGqkSRtYAxUZbZbHepcKZ5e4629ZUQfpeUD14gunYUih3/bRfffPih+9frD/q898de6XsbbccON8iEDngdnspzQPu1w7+oT7beMvHV/GYjFlG8QfcvNfkRz0pORoA1APs3nrlPPnqxemLl98/f3aHV5rt3lt24086r4LlZb/Czl3FLXcdc4AGTH862KJ702arfaVZuHG85tgJp8EYr5Y94bu2J9pDBuvb96LoW+kvW7YtajVLDtX7GLRmEiFpXUkKcla5Er2txvpg2EVD0KapiGw9vitjC9Jkk9VtH7jjKH0rYrEorBd/+N2333z3706fvfjy6Z62eMuWg/lRZgTVRHrROfj7754/+/L7v3n2/OkX367tPIaC+NbX5OYZbnzq175vEm6HGj7YE1l/DU8GbXXTFH0Z2u58dzR/7CMMXUy7FuGnI1ZdBMH3+DAj4e1jQ73PalF33/+z7Hiz7/EBBnp+3I/R7jyaZOUnk8fQfmzZLX6P+w/8pIOwD/4Inaq/dln1XWAeQoutzJIe9Cfz9WzvHib37beXI3db7I+oRQnFloOvVXrYGG9UcUZ6TV7a0nrCaeWCY6cMJ/ykDdihNtxby9Zo7JYfoYGkIZIzNNL5GKvZKFd2raba+kRtEiQMaJKhNeuNKms8aPLOROfIUJsV5kUpxomcs1BRp4966sGHMg6zXyTzW547tAzEXConqQ1YZFJFGx2yrtnIbGH3vY5WypS5SsNG4gYmWQu3NC+R9ru1k+fuVOixcLsyGe7hvg5+G0DG1iR+GJM4ut2F8w+DFlceqJPFkaQep+PP5Z5x+soQlEGjDy7wIdaj7iqDPTXZxofoc4pO29VY9Ajc00MMtq3PtBHsl/Mn7uchhsT66yjNsg69n2cYnHlDEsnDoMDJE2yvcrznnQc7dtonGz3wh++Is/QPQJwnU8IHvdicleO8aiZ6GG04PkefqzEyMrm5OG0ne82cSAVXA9eoClGwtdFoRaxTbv3tFHsKDNCgZahZCAAMIWKrHkxK7zUCZuMItdPOmXnah/h2XJstz24t7ouXxuKRRbJVBYAgLikkDgZGmq2R2hfntPeZjFYm2hiAISSZ2PKnb9c2s7/vQxbRQ6DX2d5DXBfkezGye1/b9+7n1ih0CTXf1+79KzcQqV7bANU8jPWdPcxY4fIgvHK2+/Nnf/PNs//x6LvvXz578eTvvvnh4Z9gsHgs5IO4GWb7j30UrqsF9I7o7n09yOCqHjIV+njQQ1jh2YP02Pyh916ZkdbZYnoYW7z5CQYv7kMY4WmD/U74N0my1632hXDLIZsDcbaV5xlSuZZzQQ6/7eDZGTI6enL0qw/86x2A/CAP0ueZ7eX3vO1+X8PmnacyJOuPyTYD6ThAytO4/hdddlPfjaerWx003D1scZPr23IbBtV1gNT36T6Dwe7GVt49b2K2emsU0F+zvfw5H7XJSC4XBlbdbYMxzDrgmYHGHSBFZrrR0KhlZMn3sUPvHMIFPm0JdIc7jG/6+7pSIDB04T1A2sxsjyHmPCTQ9LG2IY3m7jlds906RN1lkvSpNQe7X9c7DA7/Y4YhOvzqLXf4CDb7PmQzFO6Pw2ruXlQx7vBtwYW9XLlOB8hOnq7de8YPdz/HdQeIc/eqhunCuIMrhWJj6gU5fw8fYjA8pPiA1m2yOCtxD1Ia7uSQinydemu2dOG822ZDjvU1qDxAVuNsixYvbsG4A2QOT9e+MW0dIhxTZZn4Hj7IQMPGLit9qe09fKjBjA50rzcPZOgQibPjVp1O9fT5//Tf9aBAuUNkXK6u3tnoIdvn7kfxbfkxvB6y/VoKStcH9Y7ZyStr4sKoAyjofsWvzq7S64ur95ewL98+/QP+5vEP378AD3zyu68OvkHXNGxEjgc4wvkOHfw9gO2drzyUDjf6evfs4U3Ld3r0pqi0b/u1pc/rx+w2kpxr9/hBSjr6tX8X3r3rKgx659Phznay8ClLf7DTHdceGcDd8dT6un1+1vH2mV53WbzHmWAVdzfpk4Ub1R5EclPNtNAO9y6bNWt7s0lX5HyoU+gENAAGlodgX8O6vaEb/m9oFXIAu9qvPviM+mWPh5jaWF9+AER106OqNW64+5t0s96X4c3bcPbjeeewOeyj3iw9OrcH1+7dgfimTfriusGfP8Ao8uYQHoKt2x1CFW9avHubrfr8YC6tTZsMomqEaRwef08fZ4WPDUiTqPep3vuGQ0nt3enZxm2GiPkgyR46CqEOesOffSjn107IA8CK2cqdX/OQV2xYd6VlyAEs0M3yYyrsIdVgL92xicrwlfCuv6UHsBM3Ww39YcdWMwdVT+NQ3vFiCmsPu8EqOBrNneDlOPott+i7MHZBOGMOG4S72aT3Ut79ZXqRLgOgygEL1a9XhAkY3G8tO+fuEl5feND4Q6F4L467a631PQYPVh9xOlgrlvU9hnT0PkIzpG7d3RWwvseK+Roq5Q6Ak9a3GPBKj2H2iYB/xB6TyMkBTO+m9Q/4Ug0B4LubpvUFe6h7uMs+rhrev7u4Ch+Kdk9ieHXgxTt9yOoAHXumK3caYGh806OlU2Z/8GMcI1KD7ei7RxwAF0x36ZxVB3+DxtUHldZXOdwdgMyW75LCO0J9D8/ejSTqp8oNxOLusHjzJmOs63CaeFy/b5FwfDD2NV1/UGKHe/DuMA93U0aEN7oFB4N0AIQ67tC45yHXG/zzB3zVoQNX20K2P7K0hzTKbYcBpw9vyuHMRVu7qygc6xtPByw2eOsOeKnbVoPGumYERh3ycNsOfdJS5/gescUhDrvvPfvlxfm7y9Byo7787dMXL755cfT1N989/XY5WfTjNmhNrAwfoo3VbOneXhxApU8XHqIyx+uD4Q/gjZ3t1NnVQ4ZwZzsMKQGHuJ3Tpa+rRe/OhWdrD/XcvUJqhQytfugA6mLLPmMc7gAmZdKKvzfdwonDJp5OtxkznluyUFdGLJT6uILRqEw1FKKgaopTJVOOXKIRWmnhY9Ta2iy0TZWyLtXbqr1ILHzVsZLjTY851qON7pm709V+3W/OoeFH1j2MFzvYW7q2+OFezX7ZIe2hJ9p9JJu8OkAAa8MuQ/viUzLugHqg32Fo4DVWPe6s3L79DgdKfRvWHBGeFZ/rPWpEP3bp64ZvY15LizAdzFL9rjdIY7n4mG58uLOdbNATqMFxcPBPMWbljHdomFtyMFU87tOnQxzA77G+bLvyBzNM46J9rHbEsKctK+pwVnaweSPp6WM5BxP39XEO6W99WVibZXoA50e/xXXXqV5x9l6PA7DufvUu3/a6VGMEfwdb/m49/f7hN5+9ff/6dTfXoJuVcHrWFliZAvchvH/dJiH8zbcvj7/89qvJYLjrwQtX+Ibq98yn8Wd8xM/arFMmJ5U00o0/+vEs4gewHOT7XhCzXbtJL9t3ldNdabqrcrJNuV7fUTwRQm/eUE83/Or5rT4lW0ls9XxD3rKhud2GPBNra8DR2j85NRGrfqIHYDfbtJvkvLrp99+9WNmVprvK2cdkKbxhN/+YW3bspm3cZccmVWH9fEfiLSc5vbDff/21XNhxdnXYCukUz6+O3LxhN2drsuHSR5zdHcnK6l5S6ztK0b2csPfQcif/3MaxXLYZKl+/OBb9TbtqUOP07cXZ+bu1YSp0LEwbpiLHEWMFhiq9O/uw5ZflS8FtfpPqBkoOG0IdzCY1vfv5bXuCF3/47uVv8eXVeXh79dPFu+kkF+rWE8PsrcuL1+0vxXBVOhHORrcMq371zddfb1sUD4lF5YnGh1Iri+azWieLtjlNN4t+892Xz5cX1SeST8ivLHp2ni7Lm4JDez1Z26juKu639rpUN62N0716dfb2bRu7sypuhrz9zT5f//7bb7dLW3STzoQeP8Oo8b949vX3z5+dfvH0xbP1T8EQkdrvUwj801Zng+Pce/VuTs+dVv/y6XdfPvv2W9DI9bW1E37vtftb6E+02/PJDXfmbr/Vua2u7YnUez05FPaeNwdryyYVomGc7s3az5+++O0p/i606DcvXj777uVkE9dPJt5vE9VtYk4ErW3y9dNv5k/vvNd7L6y7yXu8942R0HQr93FJDXSjKqEG8I/ce3Vj7d7PbtuzKzO+s7tXJ+d479VduzMCN9LuuTortf99H/WAlnuuLpXa+1RZtGdnNYxB22N1ZeT+q08sxu7VtfF7nypzd9X1Ca9f9Re//+HZ8xfPmo/siz+cdvdufRPDau/DZTl8BCFut4mVfu+XllVnBPGPv+UmXu6t2tpwQXnC9oTk7TbxtL+OY9PpTzUMsb7FJlrvf/B2uLSTa7VrE0VC7S+u7q1md9uDV0y32MR3am9mzHZv4mnvM2mDxWWbmcp8K7ujoGP3BhSyw3Gd1b/dJ1FC7LlJj+tUhyv8TuOGhfdVgyNgJBoGb+4y+wpaan8wqtpFku5E2tuJ35HZE3Fhk/Hl3sPsK7f3u9YzDm5KdvIafPnbp998d/rF8+//3bPv1pfXg3th7+VXCM1+y/v9xWJekmzTxmn96j/9+uWz56fPf5gvvf9dtN1dFCda7LW0d3tCf+oG76omFGW3LN3443vQxPzzaT77EYQRP8Wza1U5FspFKmdSaFGX7EJSkYtIkrMJRReragAXtkaSzMq3f7z1sfEtbJUuelJa3l1t5orlz2/BORu1Uazw5fm7y7NGeLuvwtu3r8+uf/bh4iy3L8RvPnt/ni7evDl79274+rL8cVhFbOSON7uQtyu7dF9d70LO3uyib7HLQCZXdqHVTWhlD3mzg1zagTdSyhVpiVVhidUd9t2C2rlfxK5XyWl4dzqh//jbXl37D9rvaz+MOO3W/ud1b+EJWfz2db/7E/ObeWwROus30/7fJ5DOakTwBJusd0M5cf+xI8avSz6NIb3CX8FOnWPk9ObpnHJWCGmskuMPV8bVdj9tcNDzdJrrVfcIw/xXt+6HYV53w5CSVjnWQnlzT+/MQRcDepDSgtngtN6E87PaLT0fTTvO7uwzVkcH/dDOYlPV3DAZWJHtnKKrg4GVp/Xp4hSKcB6fRetqKwfHWVhWXhnna5GUq3RUcD62hJK5siyJHKvCLilD6bOdk9yFafqTwJpGzT/OBT4/e331JJb0qlyqbgD3dLi40XY6F/j5l4AfLCx1M4hX5gKTEXebwDyR9tgEY3D1H49J1Rtzhq6HXpMVyn42HcbM0tKa1Jlim1ctvCfOWiSqBbchgEho8EVpo2aO1jgIWPqihJEKZIyo2qJkdKtS3zjTXXZeJblR6m/OwjDRXT02mfcxqCEzdogsLs2+VqZT7avCduTXJO0d2Wqd1ZWzj7jGoVTlkzAwC1I4IaA4q1JcWATP3rEPXPCH6ESmbHdKmoH5GuzbJOl+7jU+fv7HD2dX7zoY+ajkPbZbuIlM9xnDwprNcePxnpPSG2e7r0peaHaehAxWRxmKj0aEVKKQshIuN2ubBFRhdqSTLSLmNkbIU8zKQW0ov0vy154qe6IA5u2q5N+/CU/ehfPwKuyrV4ZWXqJDy+syZ31ImY85OWQ3l8lfi1jgdk/VN76rfecgvFHgKmciaaC1JXCIt0HqIn0UFKvNFK12hWSRzBCudEmrbFJyssDkhhLVLgXeXXAWGy/42Ydw3s9136RKGO+XfvCr3Q/07ZOWN4VTB/n2HsVV2a5JtXIxXhYRgjal2BJxcaMWkgFZg4pOhQgR+tBa5cPy+wThExSGl95Y78Muqapj4ube3iTVy/Dh7Ml5OLt09GgURi/VF7//3e+ePv/DEe7bky+++W7r3VWWdqhlVXBHdQlOAAGl4gIQlIZu9ipWKGJKhm1rxSuhvRUnoBaYylwVMIct2sW91DKUwyb5ltdndYAdhh+LhPsZtUt5saNwjaLutVrTC5ZxN9e0rzIi+ZrxT2tbzFoXrqFmU2XFr1bDsbqSkzVCqhQCDsB6pqRzxE2nnXZv9FezPJF6cASNAv7xAh/mycWrUC8ujbulAu7+wrqEu5lFB5LwV8/BrI+gDJ/89tnfbpWxE7p7jjUZO6fIrMpYi+oSgJtUIqjSyAf+oofqNS6FagXbEIsMNVacQ5b4kTUJOiJWHEbs3u5FGasOxZmNl/jD2ate89K+KO7eLVwv4DFNesQWrcYBgII2ZgCO8pY0tXRThSFTwwkcjE0ySaISfdXOB+lEFFkH4mSzA3x24F0OoAP6WAPkatDhYvIqmgDw3iTrhuM2K4wm66aPHw+A60X92+9//+Kb7/56Ux+iQbC2Nz5Lgo0sDRAEQyekpEBfsqzAELDdFiyFjYaMKepqjOYMowcYjdurTVKQLX6829IJ34Jy2wTbK+JHY+l6yQ7k73Q/0sfS7wLD1RRlJRARrm21yhtfYo0pFAbQMFn6VGERY5IR7MOC91nbptpIU30s+N8uVaGPBbWozyYpv708+zkM6pgfmaC7QfKjyhgKrDZk9Q6iZmV36YlsdSKbInO2wlHNwQQQPl+lwxlYgqqGaggqCQ9aWBS0c8pc8C2SFTR7j+vMLefh9nD4E+rkvliCaCy0GlppNeEvOZCksVOWNxV3zTIYz0y1TX3NUMQyVWgL31wVQVqQbBcB26QMkqOpjkwJBVe4jUMCDd8PZoBe6879vkbyXl3Us+Fa+8ci7+vh8L2kj4Xb3KFkvNByKuA1FhItOGCOUgiYNSMoA8dRyLYaXOmGK1yEUjaGorSxBBE0R9A8HyKxUpb30BqqRb03XeaMO9PrZt4Xwt27zriW7lBfvzCrehCwNgDGU52hYcq6MPeNP45DhThcCGxiiqGIKgqD8dVCQQBucBQiiwrFkZ222gNyKKBBEMNkkt8p6J5Eb6Z74fw83DiJpH2kwj4dptQv6AsNjGBmwoa6VWu32npQk1JUJCgMESiQKJGErUHmomO1sgJqexxdqF7hOoO3NGQni9GlcN6lopu/eRtsfrQuub4H3qZ8+0G4bTjfLpShdYVWVVGoCFVsJYiGzsorgh4JNqciSiEokhgz/mp0KYHo2MIeWC+GLHdLdkhSsicQbp+K87hJ31g+ct1Bb2hHt6lwa8Rz3vHUq9wyIteoH9skwJXx4BG4jWWyUuaoyCepdKoaLK8IoaoG0wSEluwCbjA0N34HzGQn9RsT5cieMEyfX5V0DZfhp8GF7x8N0hjb3veetwWVDMs0pdYzp72uOQEmJwpRSx8B1LKrpEHlUrQxglVnz9DSMVhRK1CeL4pULNmnaMyezgv3EpCC6UTzAYJS1kprOnfSRDv4Qwj3eVdZfjVOzxt77t3UCC9oZcN2xq6N1nLtPmdAZYn/wv5VYDNjHJNQ0lZmD7sYnRal1hyDiIlLptIGWqagIQup8KO9JN4SQGzLV9U0M4AD1Hg09GSUeFcfdjPRvquixZ82V9GOrFvscn8moRxQXZHN8Yb7C9ECw0FzwPCxrlHIpKDAAfksNIiLORKoN7Hm5viQO/HGeMEhayWHhJjV2EhHUrqMo097vVcns3Qjia6L3PobftpXcS0Jm7yYekNnLg4wEK5UTEiRktag1LlIKRoOBOEmcBFdIFmtG8RWyccAjaINloYeMmGXtDsYLfx2Z/6riz+F11evzujTg7sNEu/LjfvuZGNh24J9tESz+43bwWuAuqU+gI+w1skU75M1NmkSXmfvcOmrDTHCdAJSS2YoFAksYzIJXbQS4DL7XXAAan9CbkgkX9PgffSP9Cc3j6sCH3u/bxk8PyI9QbtutEo2sTGBa0mytlQUSjWVaFu1fbbacgnJKdhQl3IQFdKVQCkOXKVUI/ZQ19sh9O29HA9zm78+u3zzp3BZun4149jmvhvIxh4p18Eq3Mop3iNllV43kLq2OoFSSrXF5mCtFmCBtkoRkjQpASIyBduGRqZE0NlOKBGZJdmS3KrEbbfdRgPpWmqq4hNaM5DppzY2qsN77nFpkFWZL2tpOb3Sa5RQU2l4zxCrYhjSMzZ4F1XFJwCnAVfBNdXZZg7KaFcBovEbLgqfoLs7oezy2umWtrzpPv/x/fm1glaPVLxjv7uN3e7GZJiWcDH19uNyG7HOvinUIFoyjEpQvSlzy01TyVDWUsmmSkSNLIJwzmVTVKvlDV4nlTQIzU6PnRw9dhtE/Y/vz87Pn1xeXF2dyVuAj4eU9NCPtk0uJymXs2CsNDuJYpIRwCMqGyWbxgpT8lXA4DlA7Ghb2IUYPI6LgMowoDMqQ/z4YdWBwk5DqFt4hTeL+zFlem0U9tAw62ao0pK4jV/0lapogKW18QXKmXKQVK1ISVepM+hMDTrm7LqguKza5uQtdHmMuPIUKO6RUUDcSl42Cbpn5D3kcI9U1kPbqr6PBmw7LwZkySs1Sz4CE3Hrajs7YX2FCpZS5eDY5apEAFmhqH2LAghwR11cdRqAG8CaOWqd8QJInIzdJXPZolqNxixf7k+fO7oq8bFn9vYwFtEse27mAQFms10si3BJSSsIVbJKEVc3Zh+cVZKLUiGnECI+ahIg7jXjbrugeSdBpA7gbZZsM4gdvuPHZQ2vR3cOo7RYd3NUx7FjfvFGS3a7SLkDqGukHM8sQoDCTs01DXrprfclQElY60G/jUnZcQja4RecENblUki4XSCkS4XmzTL/GB/IyFm6mqp7o+VbpH7dt11u7P0z3nSeX/V5oqjKlDwVSNnVJNkqC7njbwKkCM9aaU9ekoJSj8GWoAUATE6EIwEo8TsTReVQnro1BX3gird1Wn8Sufddl2g5n0Zyl26+6IFKRphWfcASbIZqy5GOrlggaotfSTbWWEBuGCgnBS6wn5TAZGSMMRjaqboZ2qUVby4qGNp01TeljX5SkQ+N0sZ+aX7LbLXRvW0FXvUpLLRCrjtcXWp5uqJB6hxA5QsAtija4Rpm6P6QStNCRVqDt4LbzGRuSac1KgCdPeQ/diFg2fon9A03VkO7faDG3vbO369/ZMMBfHWR+gHHC10Cx/CjI54m9c4c3ckHKaE6lG+pjhoMHgyTMziPY0XaSUci4hyUqOBT3iiodp9Y5FwAK+t+jqlWSC5PtBvKrw+QsPDgF3+Uex/PuXaAb+yUNhJQJ2fZZrN6o8KpRtHCvAkMJ0fKuP8ezNO3khfSoaWfRqFSsM7kBPIktFasC4AQXpB9fLG2dfbYngjVZVbfNmz2aeQ/hnvarPo+rrboyRLQETNPFsTk194AXH2AHOG8ge7HX8mVXalZ2mBFJhNgZlkYcKOUY5LBcigxZpW4WEWFd55A78myLXSp1YnW+2v+x3cAXeLU8Rja7FqJAknoxWNQSqqps2v2GkgfMwCk8iyULaa0WlhnWhq8L85TsDIbp42KwVvyoGPQRtKTrIz3wK9hzYVD6PIB/3/23m5JjiNLE3uVstbaasa2i+3ux3/rjgTBae6wSQpAt2akXSvz324sSYALgJzpXdPe6UL3MpleQS+gK931vZ5J3/GIyMrMyIzIqspCFcw0PQaiClXhkcfdz/nO33dUuH9lz6PtQqdCHr4cB3hfA7YsaSG4nGtAvxqpMxtcycqm4FwHzThHepVUyiLXbBX0jtewFK3aBgAE9I8Lkb0fwmlroQJxrJb4fXwXhwiYPLX34NGEz6Xb15IOczTelKXQfjo/CLnb7miFrjlYUavLrWE7uEuSS6tCjllpmy0niSLXsOFCFFOqddpzF4iRcLVOQfiKKWKOK/0xUnBQ68DHUEdE/tHhzotemTl9A59sufRYAWvO/KtZmMa1ZkspwgpXajFsbR00SYgATEk3Q9GHGvBDNeF4W+8Vfrw65tALLdKJ5RTulZJM1EIHQmN3LFY5kHDW9iOIf7S7sGJiqSQL6kHt65o54NHRu4wz7oRNUaiY8AU3jpSQIuTtYWRlI0dwaXOEWws3TMZEqnlvvFlN1fXUxhHv9i0Q8+jdnhpufzRlsyd65lvdVF1wxnQR+cBGruj8HKRORThZrRbRNxzsYqxNXOjCQeJijA9c6VmihmLyusFN8FbalnxOO22SywUuikvjtN1HPcMNOLnk4rG3YZz3MTldCyXMBB9p3wD0rNMO5lQm+JSSUhzrMbI5+L7ws4Kx1HDWKcpKKvZCfG44CSmFZCLXISWVxYm9wBu2QH0ezPlY2n8aGL9Sni+1MLPal3nmmoSrOMtwdIPFQY4qYXOAdJr2WRegThuLczbBB2ZmrhhsxZciKV1Nwz6c4HGFY1wDPaw5eLwn17585KM/crGPdAPXC5PVNsE1txpcaxbOK9ePx1pa1lz+Io0LNgA/BldaFAFCbtD9VRqgSmqN+2G5HCZVfWJXhOl0Sm4vyDDkWAeZn1xM/pFP/FBrNIz7uZxmKSyEkZWcJaP2RQ4/qrpi4SYFWOVWcgrk4eVUEzis3ELOtopKUnDaL3M9qdfwp2BxgXLc6ilXHLw/0rB9976fXuizJ++1uufff8O/K+8g9u8vlSd5UzV6M5Hgwkxpqw2/jNByMYUlBla6XXYCDfC4vSvcsmmTD81qgHkYWVuSUYGqLhQKrGtQtilDxbUSK2xAwpeUZCwc8U900kXgWIPoVpceEfwM26LOvS0jLf8wZW8k/bkQ4Qjz/6SixEAnt705UFt2Z2+SqdlzUW+TLRvopxQBjai5QlrW2KIxhSITA8E/sgE7mSz0FVXvgE/XU4ybiibdO8R3Kpp+rH+O+a//4T8MTQM/1b/Wd0/UG17cnAElXfcgRS8UvuZ+r8XsAO6I2r83SqqwZ0BUc04q70pgojpVmKqDTArBKZFDqIX3DCgqmgj/QspQjY3O6USBG9C39mahkUNyATy2R9D9K1Y/sgVZ2ZY+4Ea6sBQoMs4Fs58vMEzEuEukEASkyll2KDyiIGSBz1yTgyfd2ZpsAoTNLcHQu4C7kYPijmBuQa9mp1tpofAv9EpWfaX8fqRu06tkn1Yt6/Gt6JHTUVON00GXlJUU2nk9j1trv1dK5aoVXANRFbxm3IMivXImOUFV2hKtCwSrAl8wydyq0fDlQo6yiBolfvoUT5qOUZXdpA7CE8Wxh7dhCl2PU5t5LM0SzjLzOs2Z3QiOPI55Cz00VyPcZJgJRUJniZ3QTjhVdTKu+ppNUQEuXuFaClF98OI0T1pa1k3G7PUu3L6i7UlchonzaZoEvji7ceNXuxnAmvnV5Hz1MfgsLdM9+cI6SQvHndtQf83I6IxO3ZwUqy1+roqsfQqAwW29DU3xlThSzLlWOvEE8viz3RjGDg2zjRbugWXXYP8iANrK3SYHASPsS6uyxFZjikEUWAodWw7c3y5yC6Fok1qtwFqcW1C2OGvYiDtlV5M4svscCwVDT9uznkl/Smc6uWWu+an9UI878f6vP/G3bjZj3zLsXIBt69oZvQ6m4x03Qhm1R1PUeaB6KsYckiCAU//+tgS35HYjL3GSvH73h/juh/qBJfQs/vRzfP3nNzdTzkZ436vof/7zHUQ7Ro7GuZ4LMWsVVuvgSlK5WhnhPrsCM4zTG7Iq0iZF8PuE9CLKiuNZhMyRW9d0wKHW2ZuSqZYTjrXh0pS7ZWue4LkehT+6amM94hDduJDCLzVTKa+J9jeE2x92Sf4crKhvPlTfhKo2QfLaxmKN5Y2SyRH3xXpnrbMiy5SNF8IWW3hUp93pPjnoD0imoj5Cl3b7ctCnsh89XZ/exYx7x7MW4Y36FSgKuzmjb51FNQiIkxEO3GwfpGGSQJ9wASJkHnAVki7ZSkcqUnYel6lxVamvKoWc605z28HdoInO/MhuMAylW6fu5wDIbU3VUg+8GWOp/1SsK4/MoZ0M8IxGYpedURjSQPQQbCCvOINmOMQdhZE+h8aRQCpMzgYnGea22miyETVpo7KUO56APQxBhzkBgqlFxY7V+PD2p/j+xis7WEIBp/DYPkg5vxSrIb8z7sMIRRelr6Rdi3AXX5uGii62AumUhhMvucHC1Aj32DltVTEGJz+Q9iHEomKIkksc4RjIcCL/geJ2OCOu1LEyOv9E6xePSX+w8xvCK45QHBohueFfmrnFB/aBB9jFkNgCRHhaLlVKycQMS+1x3EWzthjFac2SBspjE4NMOkTXtrtejrG/Kmb8OG6rB9PwqWijkTihjwi9ENosU/A6Y2atuPjumPG8aT2S3BKttAqqVpGyNplaCpSyBDjKLmv4A9ZUyAOYSXPtnQqdrDdpknm1cUD3xoHD9mCKpHYwu9FK4baxoo+2HxoY4GIwBr24ujf4j11JK5zTZJTZ10v4rt+zzkXikOMeaGBReGRwe0WB5xaKJ6bVw4/jHgDbWjKGAu5HNdlHb5sVxSa7eiUMG4cjVHt3j0882gYMxENLEBUSXm1zbNK44gOOezQAQVFK5glxVGFLmkgiuZoK96IXrjUqKllgLQWt5ESQpdfLrwBU9hkO66FuD4Ycwq0R6mNJfRoLvtFMF0N7wZI+0mqoPVwsN/KhFO+NE65l4KOmlPBRtpCS0jpxtKIKCjGJ4EWFRgq+ERdjOFcazyI4wXlzx2ob71Pf/lgb0XM3vanm+oZNZ1EPaQlEM9NDWjq1yw5cdLZQ8NqVmjw8BMvEtQBKnpp3qWlNwUhY71pzI1JJxmyFC+zd4SfNifm1HieVZ2iOfPSdGPjlLrpBGA20VGIpTGes0TOqrjnfnLTZVBkoK6Isfc052SC9a1EzH7N0OZhqXPBWRY9N40EoNVQoqiRLiKuUoIYx0hHz3Mt975bffKx9GAh4LoftuMTBXqr+0kHNyMj7DmxvgKESLFzmGmvM2QkRanOichYtweSmolq1orkKl44I8MjX1Exk/iPsxbpOMr3897Bx+C9v65az9snAor/9r2/+/P7Du7/93z/dqKVrQWI5ZeDmTa6zlIHjZFiiarkSuxLfBWaUksC0keBe4Mi34KiFUkUrSaUSgnSe+16ZenT1NvRQ0pHNuHuhzKNsRM/dcO/NWpfrOuGXKyo4q0LlNm0RTcZBrkJlrZtxPGAiGujqmIVXxUXl4PpFjhi5AMMhzGoATy8kau4RwHs0qY+x1AEUXaySY0ru1FP7zWdwBOAx7IbucLLhLlsDP0xRE9ryQImMHbGASdzgAWjqqkzQUJzC9zIlDfsc2ENQYtUo0yltr5/QPmx4MweD3KnCLqRdLj+Cdzvbiv2mb290c94nEswIpkOo7Bb4ACxai3BUItBp9ab5JJvSuCgKoEmUXDjVqVezyNQZd1d5UT4JdDSkEq7/O6mupbaLjd8GrzOr/LJC7wYsTLWFlBEFRhiANDc2BjDPOqecDROieOsKqySYY+YUA2aNUF2JItMC2TXhD6Q0h2/BfRqgHkP4myaEIVIhTVgkToG2npV37TvLPNiN08Yuew5QMBly4nanCCVWDA45DK5wOPDRudiIw6a65oL/MznCczjBGPhjLSG7lXdDG2D4JG7BmEGYmN2gI5aquxS8q1lfQt+JXdYgFXH2EzbCWlVkjEk1n4UWIvtihYyiVeddcU7AZBTL5KcCxtmazE71Khe1Xsh1dlq3kWn2tnhIHWBaeZDU2vYO7CSZhyqKsS15KZvgvQsz08wR0D3LXGLTvkUlyMASAIRWeGWATKk46CQLJwHYSEfWUlxAj0sSsmolkmVG5dOb1NQV0V6DzlAzP5iEW2ulj9SkdnArxjsxRrWVXCx4BIoX+21SM92UPDnZmhUKcFX5lqqGORZeNxF01Tk2lbwxcNiYMZXYPfCiSRgPF8nZU4iHzLE6+l5RNLgHn4RG2k2pXXeIdN2bZpWQK/lNM+scnHGoigrQZClK57KFBopOu0yqaQ1ZVy1lNNIXGOTKQexILeM+WCBY+NfhhDqMzq51xEzci819qCt7cBqoPfPQiXGE8cupzeC1388tkyApdtCp1ZUEcJFiErPSSnYBgDTJkkIOMisvmE4OuAr700wUyXAvaDbKZnKFtrtJjqTVpDpGv9Uru3rIiG7dTvIYgn//c82bisYFH40UzQcl9erSXU45HeEEcKd978eEFS6cy+S4BHvMMYQcdXUuJYLQSWlKSdmQ8INS+HUWLrPQK37X6RCPKv+xdkwYtxi31jwF4jcr2YMUVVExEcEACMtFu8ZzqgzHPVJOpjohfXJBGO6jSoEBkfeAqJKKDerEtD5xWl+FK+13kembocLaPv40n2NiV5IuxtTNWOG+yeWPle6LzCDB6f0LMAuWhkKep4x6io2H5joyQkfdWc8Uk+VoCo6b2RJ+ldsNFHsFXpkWrcrrk8Km3kHZeweFO+f5f5yNuEkjDzjochyNvpjFsdbOpiLMp2i6xmR/KlfpoYO8ZvL4CGyqQ4XTHIWzGdoo5oAfgqdmUhIQTxImE/BsXq3w3fRIEbM+74LStTKXpfrqj6eI9jdiGpu+iVqPFwMqVyzOGpMzetdZV23i9tgM+B9kk8nYLICNuNOzetwCaHsuaU++FY/Lgu/hX5ssUpRUlHOrRnmIoR62DKkOZXe3Dt093k4M5mG8DGM6ZymK7WeBixlvju7DCHOIQDkm1ZSsijUXmb3MBW4D1JHmIvfqcFOy9lF7XwIVz6N87YmdH9gAf0XySsh5sVE3D48/0vvULRg5d8fmGwkLvcjmIla7nJ2VxTX4YKV5gKMWrGTGBF9FDM0BGfmmS7LwjHu+DSiW0wtApiFqpe2J9lm/EvJKqb3emzuNkXzcPZiqTR0z2V1PvWgLaQRttZtN2ZoxKjB/nc5JerLCwwJUGAGIPznLWQNYa2OwLQZGgHcB2xojYFKAe8Ac6+uc3sT1XuKwIlqpMFriMgrzLXiQwtMjWzCVvKzzI2s/G86+fxFitlximno/uY+imRqC4sI7ACOZNCy0985oL0VWphTgVR8iRAuFhJ86hVbdHMun8RZM/bH+tq3lj70LXO9yMZLI6mWPgbm9V7bBeq1LZFY6a5WnoqB+SMF/qCrqloyH9gmitMa1LUxPaGKLlKC8kpEprWb2VU8mn4vd/qnswQ2vEemLv/vumy///rNnL/90bBuUXB1wFHgGGgGmOl175R0PF9BZJXwzFJEzJXgSrQWdKrnWUiZteVxEMK6odXqd3gZ4RCHdGRk99i6cVu5FZGjmN+Ob3u3sAHCPCD7wdDQH8JM0vGEOZ8tIJroqpIvB4eRzMRj85lB47AbcOp66CMW1OnlRc9TiSNi0Owp3Gzv8KFswhk2HQi8h3CKnLCS95hYY01yM0ARQ9h6y8jIqHhhKNTYoIYLNbQWfNgOgGofdkDDYtRaAKdH8NiY6OBl+E7NQzG53oIVwsgXu1sD0McU/cPB0SzD+qaS/+Ltf1d8vD6eieav+fm7fmUqqJu+DdOQyoJGyOOpBB+eKMJaUTr6PgDY1wZ2TmsjCcasWdqLEVT+B+kj5wyVGd2f7ehxPbaK9G6JIS6nl4Ge04jPJR8DXFoG2HUVlDQ/PNM5Y3I+gHQwwnGwfyBZrNc9mE763p+EG1UbSmBN41oQ8Zgh4ruDQDn7be/Cokh94W4YKo+X+A7NmhiFySc1pRRB3SsEFk6F8qmrMeQ0c5IWEOQ5cdVThMzemD/HYmVS4ZXOVWbn3gx8prRsSNoP81W1TmI+6AZsSozGvLMTiIA9FYq05TavMjcq2FnxoVTNMcaw+mlBhHEgUG4BbSfMEwpJj8bATydioeP6HjCfBIXesA2Twkoeu8tvGsR91G24qTi+mZM5Ca5rEhq2Oo2452cS5tUAQt8pRexWzV8Go4LSUOqgQG/vPFHn4mOZZ9kkX45uV1W1b5mOF13T2PtnH2YSRsgiaYcEvDmZO774v82yjrMVUb7lB33EdkcnMaiR8qjrYXI1yvmSZcUO8jbAAkccst+QizPIJ1IPCHLMA9yAWfxypD0HR6w6Fxj+Fl0t4lATRrKwIykbtcuwnR1Xz3KCIb5D0PMqaYgYw0s1VilyRRxJeQjHKFjgH1sNpVrlQ4sFCq6n7KYmjZC9mCYcjpbeecvA4gHSr1n1oxBE6LJZbG21mDcqwzntdmSoW7ZPMPSrkC/QMbgbPjcRfckqkfAq286oJ8pbr3YMsAvcphUzNnBCt5grTw6Vddxki/rhXYSpiEWE5KETCrsXmgtSmFWCaViDjBp0Otywr66rGMa/Bwi1QLIDqa7XDECeLny3KxFbXSR97eHSh1v1uav8OTJx3kjrsnJyKGHuS4Gb64XHNz/0Zs2DcvHaiasljhFxT8KdCNdx3nIPgJhupSq0kko9Fcjc+13DlZshHhQ/vVMNNWFU7Ax3U4SM/5I5HRqJbI59Hk/6g9bloaxF0GqDOWTUpe1e7wDO6zE0cVltRcdIpppxq6wSoVCo8X3hh8LSUbpqbP5Sq8NdKNM0Ck6ZThmqpYzQt93C/Hk34XDp0PeYDhvJ255bHCEtu85hNPJBO7qVooHugxgvlVqmkHGBxmf7MRgvcCSsgeOITD3nXMRQdXHIFOj8F4WuBuV6tcNcLBVx3L2R5nJ2YWOnGRH2nzVlqCDdSz9hlD5SxmAhkA/lKIa0RzulQYQmSx7+zJ+Cj4JYO4FCof6V01NKF7B33wma1ypHT5zwpcXADfn39w2h8bx0DepQNmG7ASCfbm2yWNoCMmM1cmfX5cb4Fyp5jmiGkZoqQMAhONzjHTfAUcyDSZGGTRRQkYBzI2gZE2pgRYYeD/DiFLE+zlFeaDqaKj7JlHmJWm+hxhgK+j1DIu7MD4zTLLSQqlFjqe7V+H4DuzjvQwQgB74qHt1blI+BlKEzyjnNpc9C5haSkNzxZyELuMAM+CViE0kpdZwYkNsRHRolyx2uPgJpbh4Ee5fT3ANzF2PA30RMt0iBoPzv9s0LGbGGyjSJqPJyYKBnYAu8zroLjJIzm+fKwGqnknEpyJudcPWwxvGFVVmuFBgesqx/prrTe34C7txx/NB9sZxO647U8bGLGlbyP+2VyvpCjFKnxQDNjDHwpw5WjcMIoZAsICp+L3dzCQdAqWDF5UkIzB/m6wzVoHDi9xl0ZuS/zIRl86NA/PYUzNraOfI1LdXEirMndFpKxZZ6kIn3jqghuHovG5IajrTnbpUVzkofbcNsNXC5sikuwviRhItbOeh9ndoTf4D5zix9H3Yw0E/yUPpr4vrSjy9OA9JU0e3MJ7tL2tSWoGwGdyDt6Lp7iWx/xziNxPRaEXksjFwMLXCuyctAFJZVgJxXcKF/h1/JMPpjOUhm+6FZd1MIUTpRBy6SsCpmgbSShCZ7yTmm0OEbFzhEdmu/aFt+uOUz599RUzP/0t//n3ev8lwszJRcnlq0lyjOjD+R3Z6E12Ewy8F0VAI6okUlfNcHB5Y7JIIoonisTLY8Q8kaG5IF0sGMwvhLYJe8mWA5vxMC/qK+Y3WZnhOjQq7exr/owwHwC/IvLm7F4F4LUyu73hwXpzG6XknDCBRMFcE3w7D5pXYpLusVC3lShE3xZIJyaks+Vp9y4GgO3niWtlFg1uLIXnRxW/GxwF4I9T/k6DGB/Mc6gnXWzqivt4Zru3APgeeeVlIpq0LXF1ITXDvonF6Ni4DEpzIvJY72pOHi60mdlOBfAtVnutPE23KEX+ngbdUQhHSQAf8o7wJPNLsj+rnu641hdHk1wPACqlFvLvutmi7K4BK5qE6UwrQqOfsYYCP6Yr8lEQKOQQpaiBe2FJ11d8pGHfvsT+bYGKnHcBnU7yP+Ut2NIPk7VcMsEyWOr7fKIaQnzG5xqVlfZqoq5QPv4CG+XLAURvCd4wQ0aTTdckeZ0ZP4tghsmSZw4cJSHrEsesm7mbTPH2QCf8j6Mc/9uEgILEen5xJR5t0bVwtVAPGKrteh7BaLJRjkmoROtBMre4ioUX/CzTvts8SPGSFf0iTMXuTbXspHenSHU6+IGjGs/DYfsJvSz6AXLsFqOmIxszSlVI5OwU4P656m7sN7B6RQVhVaMqDK3ErOzHr6Ywc9myZObymoCXvfA5+EEPGe/pmrEg8DoSbhjQUozMAmNoy+XR/+FE9hHLbelZqAh65lIxUZnbNXeWzi8yZBpxOE4RVzk44ENGxPdRJEcnAOptvXNQrTHvJL6iue7mvOE2z5apGdL4Jx1GUczjWNHR1/vQhpaPvku4G7uq/45GXIMMXJ/qvJOyxwjZC9i8kwnBGfN2wacFIVkNurScg2VcFtk1cm1zIw3J6kd3gvPpQ+7UaB7cAs91maU+v6HD29/JvHZ6zevj14CWp1vDC/AWVV1LkCkGkYVAFR4hxOfgw+FiGw1yUPOUnInMfw05ZuNsqSc4Mb95iTf2LFLZsyVCDMo+sRN7r7YOe27FOA3erXwnPlRPA6vYR5pZn8ITObahNGcVMEWCCUcPOAateepHCYY2FcXooQdDnkb/Tt3rPCcg0iGByjuFvlwiovzK7evcn4ELc8Cn0JKI9oZYxG9J3IhHuGDm6XdoYbkzj4w36u2ITL3WYUmCcVyuxEpljO0TFE6h5Zhf73HDYFz3HCfBGwBfla7Ewp9sA8kmDkIjhjNtP/A1XGoEewpnvyX//j81bPfXyhSn/377//h6PG3cqbs5zleleGXyaIpFS56qB73IBnjtDNK4Xo0w/3yRsMZq/CTcUl4qitUfdGW3OpAvqHe+fhUmjvOVH+sK8DVDhdj+Hmg9Fuq9ZRuRtYED2k3ACQttciZxizJptq06vTRvpjOFe7xR2RqDpm4N9gpk0OE7m8G2smRXy04V50h6HCa8V6cWY+2BeM8+4XkutdrgQYFP4n6dCVOqECxAHd6gE/D3NGqRBFMplxwAfBNXA8exAc32AD8RKnLtr453nAEfQPvVusr2pH6X+Kbp55Y3xL5MAl0wJmT6Jeiz6TMOnGoikYESb6S8eR4ok8sGloGCiZSzMIkrrJNXFISoYhCBfiXEEwTcILFKYUlZpkf6KnXuO1vQO9tmQzvEsZXLK49+c/Gf2YnYTfhTwFh4qxC6QcNxRSzTz4zrORws4BL2zygJxVPsM1a8ZAm4etOu92xoLM4NvTwXtPhHk3+NwTeQ4XV9VDrsDInesYFsZOA/P/H3d9yJ3rf+4t/++WUcl/icDXz+VczNSSSrTJqrtqHB1xLjTLJRKpG2GANoFOLMVZYp1urAf+xtrSAvTCJA0Q7bu5xf8vzCDLprpSahTjHyfafAuxk2S8zn4SgZ/kuHHEvdqfdlgo/Kkpo9kreNe7mMkxX5kSBQdCuCtVgfbngpCTvtDcxBQ5E1JIBe3YM71GZG56ooe2VtLPQwg0z1qGT/9TEzlmWaxz563G0zHGw6WYltfuYx/B8GHhVMeAc25yk9D77EDWVYIKA5eCqH9FSzBzLtwCaLspGRUmvWt5JvR+ZuNdFz0RYbk/0g9bfMG58CqLv3LiXI+S5HPIrl0rKob96UfGz2zrjBsV37R6TfSB4soFTWg3HG6om+1wB+5u0PopihUpeJ2bB8k1oWWIVktkrsxfe5B0O7+MoVNErxWS5e2RMzPnQw2wHC1ie2maMDY6btMpwJ9Y9ATNvt9u/Ft42xQC0Rq9UUbopqWDlkqDoQldKPuJ/2jrFnGVwxjjoD32VOBOW/EmbwJ3udGXClXFzB2wT7r+lKbbzjdAPjYa2iR8uN9txOcChS56Uu1RxK9RaDFTACMMH4AIhE+F8VdE77XxiwlDY5ha0hqMGM5y0gh+s8aFN8fCOXVGxnlj0GVhJqf0CxPuQeT/iXgxMQGPd18VQgL44YIDrevbBkRZSi93CCMlUcEw5BsugDAefowQYFZ3yRKsChxlgVBMT0TSmKeB5NNwW7HkGxCodipqKz89NXfyR0gCj9rk4ZRqrW2WFU7pkJrEHkg+w0ZRkaUy5VGrwsUlJ1SfuLK1GVqimZmXi+dEGFkXgVpzQ8zsUgIrAk8b0gVL/7g3YQ3ShT8AY3MzY+/zffbGMQ0kboWbtRQSHYLfRTlfuruBq/sBhzmI0sL8wpkpGrVY2QcaU6nXhIlxhc2FWe1hdC+/YBLd2vjdk9eKK/JX0+5HPuzGcPCxT/VDvuVTDI7Qz+8Kdo3xN0QSlhc7McJoAIjMVF60BLtJFt1x4dKrikFshyQRXvb6NiaxyDP7EBOLAcSivSB6U7RNjs3r5c83vp1yhXEoV+rAWviy65pi4Qi1Ra8lV/J/Jgk2myYW7coMnnvcFhxaIhvVyIuAbR5xC2eaIka7z9B0r0xedQ1J/GlW0g4QnLpIlWMh0Fisibk3hzpPIqQqe+SuN0zoJ44G8padGxtqsWhPOQ2k3SDdJURPB/HmidEL90/GJgw2O6l/G6MCtCQAeNkY2yPim0uayt/4stT17WrV9wHgCB9MKaUPlQVK+csyxZh2a9xVgAhrX2Cgheq4IsclK3ao2cI9yWa3663TxRzhG3sKGL3SdLBI0P6igX9X3Hy5edDD3fuLdXMLWB6Ivs4BXdXBnkgqC4EXWbFsryWSo3VZEwAkXMZvURMvWNRs5EhOIFCWXAbFF2Y4ALARfOjW8cFfKHE72uYN62YkeVz4k6E7Q+WBaY0fQY05vCWAYqSTN8qo8u2ennslXnkKXowWSYzWijAgq45ejtzjirogSAmewfeujAp0oimyKjvt5qj2lj18fY1B4F399PbCH3DrA/qAcvzuiHmYPTROhBt4oqZaHNBpvZki6n/Id9NF8kQ7XPqQcpQV0LqUXS9baoLcLT7GOTcfijcexFsrDtfSmeingxWCD1kTfBwTS4b7l+5XvPaz037798f1UOdZnPl1IQYu1wjjps6lPsxLVzFIDNIbnrFQkgL3Yig7CcdiQRzRCk4vgasv4jguJq2uaStGUZu1pjgtX0HguUVWHYfTtKd0/hqTfxQw8fT2c7Wv4zou81X5428UiyVBSIle4Eh5wpAX4A3BRkjUiCUARX9lxKeSCdTjOFKFpCpNcCwOMGGkVV9N9KJMXbeVHkPdf3v7yHl8tKm9l1Qxcz9Kj1UJfV8BmCvDFtQm6KCYEdzGpnDLBGAaueDRChiYDPMYI1JJjS80Ht048YTrr0MLkoLs2Y55dyC/x87X87vfxTXn7a33HFOwX46yaDcw+Dv2Y0mMV+qVkM3Rwtp67XuEfOrg0zscImXJ5O8/OTY6EEzjk8Gsgc52gUcgl6JQTDrQ+pqq5/q5HwG8bYFLz9jO75YPfAY/sy3nq9hsr25db6R2pWTSPtNzVHKVSrr7UDFEDTFOBmohGtuIZRasWS1M8lgbIGoIWqgptgbw9cyFTFauCHqCf6J01QH9mP9XQC+zMbU+0Ozvy25c05zWvlXLLddMiyP0Sxt3x9CYr2ymCtMyWiumc9oGqLhSKhVvDDRyQumslVlkp4UtKMhbJ1XSnNZFx35LoTWQ082DGTPItxSvmB3l1AuWQy1e3k/J3//0X717XN5fTf2G3Ft1zt0pQVnikNilfsvPJicoDSyT+gCEULqoQNQfwPA8BJZxsxbtim0zMndjUTp7geOGuCr1g1FzJWeHu4MqY26bu5YMf6N6X17H1cqs27ta+1pgVh1KtLhofeWpt0x5G0IrWW11EsqoR/MkkchSA0pZHt9kYAAGJAD00ezenKQ16xRI2ewwcvUJlMITutmGmh5fyQHI41qEsAQ5t56GmGdNJg3x1zgrOBwygCqq5iuMtNayhEiE7uOOGK3GZlljAocmyepE0HPVYA60CDsm92Ees4D36LR7MDr6qP+EYc0vXhDKubwqwRo5PK5asol1U16Fk32fjKWAJIEIbKuOKgiNl4ZPX0JqnXoAYgfakx4EyUUeebBulC6dRe5Ic6eZNmFV/DuFTd9sm0wc71zcCn9KIn/+7L8buokVOPTEbhjdnkoQQExMX1soMbVSgiGWBdtZQKQB2CWqanMQGaCWhZGyGT6M89iVLI08cONV1iOZ2onl6vR/ug0VWi4mWOYXnXWT9H3/7m/qv+Ud4Jm/fvP/N1f98I/ov6/vXf37zu8/f5b+8/rVOIyBHDqUhDnUhnDoYD3lXI2cbr37zx29fPH/23Z+ev/j8i2+e4x9KxQf5cevICLuz39Oi7yGDGw91IWd88kowo4dW+uIdVObv+DT10vlxrN9DfKZhpZGH7XKo3oEdOsiAffqn8ur4WqP6//CvH44v8Pyfnn3zxy+ff3n9/eevXj1/8e32Gs//6bInIo4uMITIpGS/6yBeOo/MNsuMDT5jsdl1r/k7RKR832WfvX2T688fNqx5F1ZsNg6/chCL33fLNmuOYYLr0ce6Fl4vn8f/4Y+fv/j821dff/v8y+3lhC4+ZCIVY1EZyCiEVFPUcFZjMimxEfG1VVm0gVpLqkq4t94nXS1Qq158yREoH4Zw9xV/H28tgz1csnDfp7/oEd33vxtGaQ/98Nf98vfCuXudpyNKZlpyVJ5TN/5iJvBcH/PVX375Kb3/rCdH7qoDpD4a2hoKraaJnF2mlzhFBzNBd/5I2wt+8cvrH8sW8BqQLjN73EuK+7fywJJc2T2Mdjockz7nx3vgXfvq9buf/gXI6neJl/vsw08LZ351HeHW1xks+MVETHSwOvUs8tusOEhQqUUZ3udUbGp/2PgddLHWNLSLPEiqtiigma2nElNytTmhk8YfMgnbtK486dRGrVQhV7yX2XBcHT+6/mpjX5Qy0yTpEVFdiiDOiwvWlh9acQWFh9MMB5btt2nQ9CO0uxgKpe/54Y24/VuMX48ELFwmtmw8H+Qler3+MI5IqBXs/iAv0A3t5MSNAPVjvsUOG37P554VQJ6wevzlw9v38ddqzGcp/vDAuml36a7toa0eTN8fWXfMno9Uj1NOXRKdF/mc8CaMEw6FZdZUdVNW1kReOleJQhAA0jYQkbadYV/XLPGlDDUmilr7Unxlwt/oODZ/q/fsDX1jZmUg6r4eYMe10PRR1Wd/k4m5i8HxeQH5KasPFZ+XMJQf1V6Npeuspe/ln9/yI4/LTpyo5/WuTlt7jByPx48HJvD4zLvcmepziqYVlxp37toivebUfxPRlBKF98FkU5rC18Lm4GIwXJEUgi1a5FtpmfHlHxg2H194i9rr4e3JjFj3xqBBy/XCmTGIMLmaBws7HvilOKbGDPcPf20PLj26GoPeenilOXuHAe6MEasVh/EsGOfIG4ylmZeD0b3s/vpyAOsh3+b//d/rjx/i9fAWD4/7DlNQK/PZly+vX0LP1Y99Kvr6/YpeDi7x5cAStewQH1GwIbQgos/Sl2ZKLEUB2JtC0hShHHfTeqhWA2xSvclK5lKC8IG8Nz45ae76/pNx6M6EJPExYMHhNxlayzpGuuCJbvczmPvRu1u8yHCuL0b3eokA4IHFMil+J8fh15zw6VmqGQn95k1e/vMfvvn623+8fv7y2eff77zK/V4AYHs85Y9yQrbe5PjoiQc+HFNh/CMYwRGZjGGPzk0xhd8eHtIefZshDsRRgPMmvm71FgM798Xfddaav38McDSB7Z7Zunfw+m7v0DfhLsBekc0xKpLWJ6VwOoUtFKoyXlJLKkRlogtctq6L4PK9wDzlQskaUvL6Lht30185TjURJtwt6BqYsb6oJByXeCsjhbNGBE0+c69lTEG4EE1UrQhfpUpZRtmyUbCeuap60tRLacUY5RhxDxemjkmSFVt/Jtwzf4WhLqXXEw6TyBfv34O9xiiFzpMzGW697DQ92Lu8eP6nr5//jxdfvvj8q1cXL7579d2Lz7787tk/fdQ3uUGEN6Tcm8zgBS7ZR7EdszcaMd4F52IvOMOxqCjOZDxnb7HJ8k2VIAtkzufWlrOXGWkVhTwyZObBX2By5j/2gZiqvD8GbNhedzSSrDun48h/F3RkgOdHeJfB+lwOR+FSOH+/e3GHFxkCoh3We3lwuNTJR0FaedLq2zOcx1zW6OdMEJsRzMNn1A6+SoYXH8Rn5Zd75TTuvPxUpTOWB30k4z5/j7PUet159WGe68eIKh1YfCI6GfzdIVUCJbFSNfVw77PBqisA9QHfoOOqESlPLuhHyDbvvcy4FdL1APXLZ59/8/zi99/98eXX3/5Dz3+/+qdXD2/HDr/QA9e9rL/AoM2vp2K/Icl2LcyZ6yhPeampyFGp8ICFTcdWH/gZPv66o0HfIO2hSGSocv44Rv3A2wzFIXdzbD2l5qQlVUvLpSWZM9xuLbQryovmC8+i1doZ67QXlKxgOjkfgguyZoq3fucxNTtEs4eI/scIeO6M1Nkq8Pko6v7A4oPlvRRkPo6+P/AKU0FpL64Bqvs4un7nRbi4YlJmU37gZsjUx/AcZq/z3/7N+JWX94Vl4qRcye4b7ORhRzrm+6m5E73ondfojuNYTzCV54qw4j99+fXL7797uateXvzh0jOb293eYILHi3Ge8y87zlzvBeVT+O1jf/SRsmURHD/AqvjIy2bs/Gt22LkcTT/rovNhj2Nx5d/hnP/9sjE6Ftpu0ssiUs0iex1Nc97bWoWsOlKM2VUTo3KaqJY+DSMWa0zk4jBYXndSdHhvXsRN6cgFrPUy/Dvy1sY7Z1XMxlavHA/eiBp/rT5XmKWiKFilWxQ52ZasDTJq8lGLAFAQmJxx9a3Hfq8eOB4dLeHuWTt5kjp74IqekS5sqEcd+8ymIOP9itSXElSHuLMuhbEPF9nbWZFzAJv525IesLJuZ9kJal9uFUs93MqdcmUDAc4MAL7CPXgDCDwAz2XY990fX11/99X1y2ffLeTWpwd+0Y/eJvx+iLzkfg8e/c4xGTRMKV5UlLda5evhLL/vUbmVmNzdHtxffEqlXQxxp2VUdbd1xhQxF7AtGrS7PX0KZ99kfKaSeIHruAgV7rZghwOLVXB3e+6oMbtduFZKLSP9u62xiaddLjR8322Nbyoe+O79VgGl8O6c93laYGy/4ajX+XZ3evjExiOUOeNhnZ7ercXU7/kAoul3eIRsiy78nZ4+IMLLIfB2uakm1+f8JHy5Lm9O6VS9fb7rNgDr8wlnGpA4eqeXG8ssvDjj+RyDaWdQz9/UP8cffwfAuV63eYvnnU2dDI/78vX7/OPb97+8g84a+0TvL8v5o6eM03CWJ26E+x+2+Uo9NDsVDi9PDL/vUt1D3/RD3/+kz1cY+/4WXeI7PnpkJb+/6p0/ehPZG7K+ktRK/OIW64xNRVOF5pLfeYun/iF++MCKd/P0Xz/7YirfmBzzcymEaa2JF0JIcz7xTA8fQfK9kfjuUycEOPjS0oezb0CHfOe6SdNDB+Kuc530iTZgskfj0891PMYEqFyrXrrFI7eIxbls7f6P/UN8h4vBHuuz+NPP8fWf30yh47HvbmqaFM6eA7McWm/MSk5T2nvJl1xj9rnzatNlHUPC14N9OYOpPLTYJiUxlEfc+xIvrTHWIUzK7gx28tBqIxKfaE5XmXfuvBBPsBqjBdxPdUJM9c5L3VT3Ki3OAGUOrtFrIsZg24VSK3WVd15ndDi61ySwyjkv0fNf65tN9+HleKbPeXHGBUa0MUS3znm6xuePdb/+vEd3fPjYijNy7QipV7Kht1zlH1787f94+fL5WDTMI86fvfzT2Z7eKa3OeQEmnNFtyhmiMzdP/h74dIrHjR390+2S8jD54f2WOol7505Pnvpiznkahyf3Frmhh3/UpUKG5bTJ3dbhEMQU0j+bP7K/ytBGdf5DNOiD6ahOueJzXoMHEMnkmjkzhLA6h9hZV/hv/2b0zZaTF7d86jggeujzHwqZz+E0vczvIkQ8lQafwSxNTxwKjIYJ42NI6QwCmZ7OSYrtAPAYJziDltldYai9mEaCnv3xU7f9/VXY7nMH/e71FOkfVfyE2s/gkeyuN2SYez5/K014f2Oyu8rkgwz9w2O17v2x7e4iE2Pk2DMwhdDvDzt3l+myErRW9HWHJ48eKB+tIQJ9b/dp9/mTUj7fXRggwsTtKNU5oir7z56qA86m36YHj57+tVD0AE+fwMFA2CjsSs/dndaY6PP5SJ7xzk6Pv0lTrHUM3unxY6B7hCGX0p4jF7K/yEiAoeRK8cytHj5Nljnf6/Z28TEHPgEd5gE6o76fDkv3lMf6yDM+/mxh7emBvbh27AHssdUzvmyHjmcEYR9++vl3X3397effXPzt/3zx8tXzLz/DH9/f9+EDF/tEKPD6zQ9a3TzyQP/ZbZ767O2bD0COHwYkM1qesXTyDJpkf5FBiW+x9k9J2zNcof21Js17M4187Hm4P97YX2oKDio/rTqR5D+ADDvw4M6/cwCP/Yff7MxUTc7W/BxXblhpoofiNvR+m89x+3YevYkHT9WFSoizYJ1hla/fYHe3/JapC07YFY7A2y+ySUGItRaH2z97mjdsDg4cvseDx7TdGfT/9lOZ0mYw4ecw39tPHktTpir1+0Pt7Yd3+D6l2SZ/57xLTAVsSp0Fm20/enT67x93Gp+6PjfgNk/7w1iNPrXRTYIYGsqkPTwx9F5LDWhphPLjyIr7B572Fhl8Y7bGQx7gHDGX3RXGIz9ERiYMe65TOS0ybscmx3zTnXs+XTxB2TExM93h8y3AubjJjIhA54MOAwGR8EfGrN7pmTfDeqYrwYdoaBC8f733f/ztb37+5ccf+6iaPv7m+jU/a2uc5K/xlx95uM2fvnl1+d1XXzFG3RoYt5ml8/43w5QcLF+u01/xvvwTilQwfY5P//6fXyd8V3wm5ECVMFuxT5rbWfHbl/JWKzqiIPossr0V7eEV+yzhW6wo91dUgaQ2aragoCMfMcyFurQgzRbU1ipp7GxFdWRFNfuIt12RlO5tjLMV1eEV+1yw7RW/fLG1oFqXqdcUbiHTPqppe71n33y5tKDdX5CUcN6QnK1I4six2f+EkCnd5thobKM8cE6F7pcSIBEuxtV/5cla73gc1lcvL4XrP/2eKzavf377+s2HnblYss9Ntlc0zXyr8Ivyh9e/HvlhyYPbDY3TO8cFoQZm87I+/PVnfoOX//ztq9/jy/dv4s/v//L2w4FB8HRl/JXsQ7nevf2RfynF90MX12zi2fjUL7/+6qtjDx1eUl4puiK39dDyurX9h9rtV/3622cvlh+69cnHh75+k9/Vnyr27Me+A+9/eP3zzzzjbFsk09DjcZ2v/vjNN8clIgK/PIQi+ki4jWL+4vlX3714fv3F5y+f734KpVWfpnbCpxD4/z5wTlwZfeLTDfUJoKc9vY+z02Y8Sic83eK4nPx0xZIx8op2JfPV519/8/zLvQc70RXYaQ8mfm2hx+mSmwc/+/zbZ8+/OfBs68LJz9b8bJJXeveln734/OXvr/G7sBxfv3z1/NtXe4t4o06XjGHJyHBF/kS5Q225+z79mHiCvcWb2y4effJpJxHU1mlfUgR4uhu1C6kTny4pnL61vj89nHzaSSl3+l0K/S7hpp64p0SDeT/p6Urwu0t9pcyJT9c6nHxiVNcD/Pqn7qp2mk5+uuJ3hzIe1fv6042lk+W+b5HWn+6Elyc/XfenQ/R25+kv//j98xcvnzPw/uKfr/up3ltEu5OVvDLjVFGpb7eId/rkm6ts18bYZnm7RYJ2p4urX2Dt9rd6TXtqaInTP4nvp9Xu3+O1T6KlusWhDf2T3HpPtLLqZI1E3bqTu5K3/CSk/OmLdHSFPZHqdovokzd+QFv4JBYHbNXWAxqKE2398GBsgj3RmGmojhMPEp5N/Gzj9gHK6mmFBjlRP2GRrkGwx3SCZByJ00VuRlO8j4J+//nX315/8eK7f3z+7d7jgVFOF7xl4cDN0O7Uxwd/KjiceTGnPf7UQ98fz8OD6Urt6u3Pv3r1/MX1i+/3Hx2kP/nRrgsGe3rKo42w24ZgyZfAo7tm0/L4W7PT+At8w/LX6/L6z/AS8a81J6erMbrFqCRVahGaTvBUcWVtESn4bGNO2rWsjJZSZetkJVtqSiGz54al8tvBE60f3h92EOu//gxHk30lTYQv33x495qd3P5V/PnnH19v/u3Xt68LfyF++5tf3uS3P/30+sOH8et39T+NTxEHHcabVaTZXqV/tVkFsO9mFXebVezeZ5FqexG1tYa9WYGWV8CmvE2deuM6frjec8jx20FvPHpe0YpxfnR/9n/djRPiHeRvbyhf+C1mIT7c+N/uDyC4wm9tM53ApPx2j28Duvl/6Y7wj7Vcp5h/GD5wj1Vc37wfvFPrvfPTv2wNAle4glpLuz8mG6JTm8HafjcoIsNuTETKgNMXPD3QST7rw7AZw/94n36Kb163/uzjE7831BkHUuKb+eohCNaT2xPWsUbYnbEek26m2KR5yKWzWUnjs3ZB10RVVJlKzlYbKkTR48X5B3WIJaQkYxWszqYZ687wcodmrAOvSXgsYkQ5O/Ps+4j17v/MxtkbF8xvDo+zF7Nx9uTFb+4zzn5Pwr1ueJgAAxMoDuU+RkFbI+VvlgfZF0ksxGBUomKzJ5wX2ZzDWUjZmKqtcMGlYkSJoQZSUrhaayhJxNRq2xayOyZkRnmOoyzSbwv519c/fPYmvn7nnpqEe6XFVEdyMIM1CtgE7VcE3JpW0TknSOpgINacjDHZQ8eElpNqthljjSrMvgTNErSqwakEpN6M7AxGk4BtzzDsCRg2M1wK9UrCIZiwxCTgX36Kn/3w9l/ij+9/eN1B4b6U4WcKOixl0YNou1LWe+H0+0l57HnCgTqYpB1FLBXRioiTywb20OL8mpRiSzFli9/LpuUmKFShYrSFooZqgxYRHvYph6iLL5YybYu44/KDisLwGTZAJmpbxH/89g+ff/99J9Z6Gkf4PeOXsZR1mNhwsNBmlC5ZNZyAbfmS9UO+6EYVxyiqSuxbZB8rawxhksxENdZgMv6WWJHYUEi2JkryKhuRSYtkbHNrh9jiBLMzcugQ57/UN5/9VP9a39EhRfEoR/iLd/FN2S7/71nvqVJCenm4MGhj/6RaOdJOasqpJYrWxJpqaSbpoAkmEt+NnoiEKvhaxtCErblknSOOtHKq4ie3BK4PC5wD9xA4g/gr/QlojUHk4wjFsUznUHnadLCllDPdjG+qYLflbLRJRsYYNAQL39M1U3NMTpKDGaQc8C0Rm2HXiwSUc4oqBieKC7KUVtbkrGGh2QE+dLA7xvhLLCWW7ns9ITE/+/yrv/1vl1Lrz37/fD7YZBKxU3r/HGsR7I7mUMGFagQjBqWdxXd5khy0SBOBtMcRdkYRwLaIWRUjbfJMjihIJEXVyhMEHDgmf0jALb6LfxlVh3paAh4aZKby0YNVFJOykD44tw+WlZQ9ALORM2lSqYaYQ4MmDhQg6JiEry5rG5JI1vnmbIIqgevhDRS6qQzqPPRI7QmKRTkrlrMKB+Vcf3zdPks1/1Df9Qz1E5Jzr0jf5soMy6pZwofYh8zS0q6srUk2Qc5BWxWEzALHmpp0XqXia0y+FA3gDHRnHT669MCAjoGe8KRdyuvWcAwkK47faPmU8cYg5pEzY1NILPzimbZByQ4wtsVsgyW1ozuaKjJHHv5bC7x1SbE1G2UR8PVCqoZ8Diqq6rMQycMvNC5WVUugqnRO9TQ5654lD1dqxzd5F399PTqA4WnJeotMZHF8yHSijXL7AG92olWG4gWuyMAhPG1Zl1zhDgrjyEXgi4YzrWOLHlqlpkg+RWdlLRWA2VIyJ0mac5v+Stkx/zJJ+s9v8bEGLd3FdBvt4cRce/jzaY9N8Zw7PBZkOs5k9g/zPp4jHnwn4FNraIyipW5w72SVriQlBBSDjqSa8lDsAb8L5UJFVo1NIFFyKGsC5ij7MfX85vWP7z/7ALDxQ+zpjCehnp+9fZPrzzf9a4v6wnieO7unLoyhHShXnMw6xFpECJCgJ1g7Jxq0cEoyGZWrhqUruVkAEoCR4LKDjIH3mjMlneKjOPYCD4k4wUXhSIZ5MuZvI9+Bs3WKyi2cYngUa7EM70xu2VmjoqxQChAKtLAqwfoCPQF1bVIU2VtojkQq2gwvxRVoigZ9vxMsOihiuhSyR+SW3cCnd4inbpOb/pOhcPV4aI4h1Yq0W6tW8TRm6Vxq0ARWCBi3RiFrOCrWVtV0n9oMTQ2TR7VZEVQODqcdd2EN0g0+YE/OCXtl3La0P7z9Kb4fnZNbY+eugh9CK2/kPbB/DkOwl460EZL2FQcZpcyO5qDsMuSnKoTWRCPAtlK8TPClgaBjUrlVaaAugEMg3wb9LUrFt+CzuOL82rGeKkxk4MwW7eCMn17fONvykPl7FKSxJ+hFHtcJZ4heK7oY1LDaREoeirmmBBdQiwhXhKqssVQLmBw4kpGM1dFab2qB8yNUChI/NyScF+VsOIOoDvuCrKHf/hDb23f+6amPkT1iIWVixb4LuIuUo5SAYjjAOMVFQHEkaAAnfTTFNpKhwvW28E5gAbVouUYoCejxQMr7IE47wcLzCSa1Fy66j5f98JpinO0wUg0NLZRLAVGv5b4VnKHlQsUJ6ytZS/CxbSXTRLWhRXaoHcFLcUYnhe+TYF0CVdEq+9vJVR9X/RI51jAeOsc/1jfxs/evf/w1qicTM+pOtjTmYIPJpIrZUwj7qngWj3ORQxJVZe21hmmzQkeepCxDwmFJGv57atoIjW9FHXMOOZNU0HvRZOe3HRFnjobyPbt8iosv9uOeA0y2h87xoyjiF/3cbrqBt0MZvf90QWUYFt6ewOHP6Z2j7EUrMggdCgCzcDFS007L6rVKMlpRpEtKO8hZa84IJt2UlNrooIOvbdUvmQpDuW5TjvVX2+m/7mHr22pkd0Dc6pzinvp8N9zCSzEjr5zf185BSLkLna2UVVCDK1MA3shx3DknZQiqQ8YcpPHVJ9dy9pTgKgp4LEAfhYeueLGaBpwq8aW8ElPp9r29kwdTz5Oct8Z6L4MLjz23M8XsATpoFzNXqwE74FJXTRbeh24BOr96fDOFAFEXLucsPtlkm3K1ecI/4KcjzrzdSWcf1x+BK7e0vzLhKYfm9oS84IwYheu9HySCY6f9DsqAXx0F1wdoqOhWHeUmS3MUXMBRhQW0gSRcaqUjYLKvAeguBz5HCfdhPZWtLoVl5XzI7g1RInzo8p9/ff3+w8GqjEcxfpOURwx3XMhSibCvj2fQImkXS1O2OB3T4F8nBVxcoIYVpRqhhoNWLvmcqifjooc6SQ2aAz5hEjvn92jNC71SvWHH0Kdwfofg8sHW60m0Ukg7C9tzLN9vCxd/el8N5QgRAjgoXaQuRXKngBBcPgB3mrRT2uJoF5MjYLJVwNC+KG/E2vndJFUN9yvpHWP3n395/ebNmCTxTyaPPYl4JPRbEjE2dT9gMQ8jw1HLnPJXqqVgkxGJIN8CFyNZkYsXJssqoWhLLELBQamFzzmns1xwO4UY9qgjLbhiS9srcSBicaMgnhyEY7aeaynMQZ6NjZun7CyWDOCsxO5BVt6mALE5UxO+R6baTNrmQhmwwpME3IYzSC7EmK0ywQYI3+YQ8mhHT3L3oIUJclazxMgQGApPBk8MyneLK2cz3Mb6g2QeUxROk9k/1UoP1b4baefMSemKo6xxTEwVnuAhVJEldC6cbQ/tDOgcDGBGhmstpY0iA1iHRCqZ05Ijwr2CzsDBljs6+T2c61FrmNuavAeT9siV3AkxFoQrrXCrvnS1JRucymTI6lStcxqnNAJDBFWShFuCrytUSukH2zeADxjCEAEqACnCScKl3jsGwCbDLDHSfWn/+Dm+7TF0fT7vQM97MUw3WAhyOsAA2pez83YPGZMuVEVQwcDj01YVZbSRMpAyFU63DBFnSSvYQR9I+OaaNBnaqFl4fdAbJwlaKjZ+0u4h4/uCt/Of5APSZpKeaeQtvLfFhJRUs3zUrCgRXpuozUqRUoxcgG0qVxRJDacPeCJba2IuWTil4I4YI7JxVfsECxlTkGvyJgj7WMlcwZkZE36PX791QNTjEKKxwHbJ8dNuFo7bF3Q2SkN/5GxKqPDvkpJNCLjZRF4BfsCTtglgWHHYjhzsooJqttaXhvOdtqPKCy5fFzTUM8ljaRL5+GXMh0TNHIELiMN4t++U7AsYNpKgfB2gRZDVq2ShmkvIhqjBzsH1a7WZ6KqUKZNsEX6fxXkXlasH6qqK1nySj2T9emnRcJTV48ftD8l3JFCTWi74fk57rL6vo2Hy7G4RVxDUnI/Sw6vDoYY2TtkXeNOVpIWeSFSVd0S6RtcaHGxlnFBeugY72k7Q0cIcS2HfB2l8TEmPlN5bNM9LeNoqO4vNWUvG7KoQFZPQEncypmYUAW87Pu4y2pi0Fk3gDhgRleYIvzYVysWb2poHJBy6ttby2qb7LQfk/vO713+NN7bxIBJ5PNl/9frdT/8S39XfDWNDLm5mroxe+QL+A7KYR/yVszuujKiwtS3qpgUFo5utwnTHnTL+mgDGZYI9TEG5rDmxnZJWTboEJB5360OP5AS5PvRwAe7TPfIbsU8BUv49uhH0DW3qKOt9n3EnbneaA2I4uyfC2Aq8k28aFPDJdRdbkrmRiDhJIjPm42HS2ZjF25rHsCq5kRt4CcVxU84ainO1liKr1VbD4mlFURUnAzQDfrsGKAqbRJXOEU5oytqb0lLTCj44FMoWuMCPuLnoVa/bOmz7BtTMgXv7+AGjgzLuXK7TEV2YiznKG77cvO8vBGZP25Z5hA20qokYqCVhRUglN+0hZK0BOSK86lY0oHXx0Xrod+hk01sldDVKbYeZj9e9MK2Q7WQQ/lzFiA/rpWyEPuWkxv60i6HJZ8EIkvdmH0TP6vSttUAaXjeyKQqVZctc/QIPBWAu50hZhCiZBA5OOiddDZRwxU2oqtlA2yBvAUWbkcpg4HA5tYLg8UD0RugTH+SxUcxTKhDu84pGqXhp73BoEyCegPxMAnQO8LrhjzuRraMafCNIPJSitSzAdl6UyFlX/OckrCEOV4IOQeguaP341QPbgt5UMh+XrTRhzecuLRDECmRAtiacymJ8jSEnhe9SzC356jq+brERYzyps09cfITjH07rGB6CSeRHWognlz3ZFuv37972rvzf8cC/xSrxoXZiSbgQVQupeeFUhgcSvMQhhfSCg+WTXFxLJUm411AHTACgaoM6Sa64Ymr029mTBbUMDRGYh2m3HDG+2aAQc1tbaOcH9yEkPBD3jvMVN+OMlkSuBFHYd07wXa3UjlcI2+dCdLCBHL5LEH9oUtqMw2N14kJ9RwnKQbfmYHFii/iTKLVYrNBl1f9W7H8faaHaTlvR01IZG8mPowUU8SkfWPLxidxBbuNNaJrCvkmcxf2jgt1LyerSpLJw/myLgpwXuAlRJtvglUhom9YUGa/JlxKb8pGgTby025r6mEkc2H3ElZoIkHbiHkNxzMGiUBukOKJR1LwnwpsbqdPZpf7s8y/HOVUDJ8FJXW2ByOyDbxV02K2aIZOLhRK3tihTcC+gbQTzRDAZrW86UKWQAMJD8bV46bimQ3jywOTV73S1HQuiHq20+5exaubx+R9OkD/jkiV5cx/rvri54ms3F4PXB8ZrQrXoHPe6Gi6METYAG4oI8G4BurPXCpjcKkC/ILLn2iW2AfXEfiviRBfXKNlPIhdzROCjht/M/emjFLHyYqWYAezb34VZHwtgXwhWe0AVbyANCkaoqqsIJQeTnJXCAJiXaHGFdDKZa5tq0jYWk6lsR0SWQYyHqz9ywx7w9g9GRJ7cNkwdh8Oc4YVglLVwyfdE78ipnWBU0QIn31RvoVOACoMpHjKGG5qb8CKZFgIxjwTwOXC6zgYoUzY4SDFmI1a77rulPRIHvNH4w3F4ypL/8m1+P92A0e+/GP8V/vpKJZ+a9QnMLW8MIcZWcDOC1NLnBsxTubKkOvLZelV9MsHGWCRVRkYGVlr7WmGatYhr+zBx6DKpXhiJXD/ZfTjF3AKc6Fn5jtaKdoOxvhkul1QBOj5DuTfNOihpibMNP1QVkShDyTD0UdGEjH0LAPklSFls2g0CHFU9ks+/8VfCfjr+02GZX48DoaQPS1wUktZ7vaxqxQEfWxIBCBP2lWRs2gJeZ/IBvpUxskru1a+J45A+KojcKiWEt6sZCHOTxFzE+AdL056e/Ifo8OUwoGbqTloovbRGeTfv6zfa7VajcJ+RqbVCtsLVkhNpoEqVpeisNgG+Tm/RtRr7Bx9YOWWcSdWUqG1qqwioB2fk4W3otvcmD/RpbMQY/L3uE6t5gPcCkxOTCtl9f9dbT7vJOGB5HHmKBuDHWFheFZupKgE8NW7T8zyVwFYtDCf+izTR4BpA0fek9Dq7wpCMO0yYtVgp//Skv2lPWAqbjS02y2XHhn3dEEpxJhYPlB+B54Ut1VOG1jeeSZ5qcapS0SZE53NxuCa4EIkHcpyUYdKdkdTsdSesxXaentiHIZFjNupiSDRdyLB4+PWM8mkn/A57m8hVyD3BpyoRu6ZjlIKpGAj/BRwnoJ1ovHbSRq7Bt+SkEznWZM2JfTiKEY8wV4JuExV+ehtwk4UeB0svlt1rtcroQgWQX5CVWcgoinMuQ/njb8o5QH3y0gVJyYZgoMMElV7NhdtQZHJD+uoE8ZtxsMJucdx/+mUyvvLTAJzDVOclkO+ll3qm6WEyxW7OiVTMlbsllRadeUdxRWKEu+uaDloC40PsDUYa7lfDjlghpS3WuoZdXaUTmFhHuBjf7Un96eacDoh9nHJ2DXy4xvWi9ysuZmc9qBgpOqtjMDJD5KU2OFFwaat2DYdeMomcKdJFp6KotmUmOMkCiCe13cLERbZE4rMud+L43GL5ScTUhijyiG42Ec2lxuFAswzKvHG4ycg1A+xFKU3M45eZ2kFYgBjvQ23Q8cA1CWpHhAaYr3WkmotmT4tO9Gv1K9UZHdS8kGNQ8k9ezfSa58teurhQTuBcUIeKQ3d0jNSG2Y8BZkoBfmkZOL6pyjVHUngvsmxJMRuaECYb7pmwDdrEFu+thZ5f0zGaWWGOJE9WynCflMhf9A6KzdDW3ly8GMC3q7SsLQknQ8mMXkqsJpRQAeVlY/I/CtnBtwq+kATkwXXAkfZO6Ea+mibyemnXNI5HEk8w2CWV+tScqVH8Uxr8OJwJYd6xwnnA3Tb6CH3hoM9LZoBSmyzRQ31LvgmALdAqWmbjoxKwtKHZmqtyOQLax1Bz22pZOVy2NM1TkYLbCNUOnGRGk4Fp48lr+VHqA5vo5bPY/vZ/XY59nAutcH6VVLvpoiDRnEpyJmRIvUmnja4C7m4IUboUiOBLxdSiT9D90lrcDquU82GHuG6hizNwFycPePD7Luwgfvvkwfwo/6mCbMevWuSE9qtdAVqL2JR0RXsOzeRAIVhvlUzcWSQ8WYBK7KSr5HxV1YsI5KlCJOGxP6flskTvVTZ2r2lrwJafiks7bsLAeT4VLixlsYIXsyzWLJfosybjgVqKN8VXm5pLqaWitTPJy8oVlBZOLTwAFWRVKptCkHxpyaTgt0pxljTQ0GsLj2pG5NEj+PZQxepTFP6mpm+yv2Mx5SLtBMlZ29eMdqJlqB6tbS1ZM6FEgO/KvYpF6epMMRZXycEkyJAKp7mwR5ngGHCraLJ0WtcXz4MJPMnGzMurhxqGJ5/SHffhxb/9cmi428zjFsEuWGNthqO6k1YJcjegSXBcuVghBXhS8GuTUDjmOlfrvfKwCcrjV5yWmi+WNfAJgrPG6AxPeCznOIX6gwun/DgLaRuC9griTwWAbhHcbGbDC1r0vNyss2aXtSKFWJ1ImUoxtRXZXa4iI8mcJP9DMz3YGVTieQDMshBhp2Njlnu9GlpTveDycEz/lOaOp7gLY4fvGNocO2+WaozhS0lNszib8GGvusGahntA3mURRFYG0D+H7I2plZStKWpvKgkjgyPfXA4pUXDOCCa7sH41xa65oP5I+WsnXO81JvZTgabjjIxhP5ainCT3Az+zVgY4wJY0MKaSNWohNByDxEkW7qvhWgj8W/XwGaTJ0gVRC1y2in2F9lK0Wr+pF9j3PqUY501wmdRmFv1kl0ceOR67sxSImycbZ2XgKimeu0NVwEMTIcNTgH+QFXP1KT772SqRSlRWwSN2KulqgZy8jzZnd1rsc8i4qLDHRTI0OWxGPDz5XNfOjkzUXMw3t5BzVyHMiNxnzWfSiGQMDryqrWrrshROFf7sOma4acZrYUvKQrRAzsGpBnxiHeWErKWsxuOoExqt1fuoT+tKDJ2Al70x63L01RY2whk5o5aaRelqM4A6uYYAzzjGBCPsQqihEjRWsbWpFiJAbNEl2iisMLY13JdMKmTVLcxpoSLLQ2Z3a8vfwrZNAYsnb593dmLjNfRI6VIO2Eq1Gpy2XojM9H8CJiERvOZijU3eVQ2bzTyAzVKKzviQyFRgVNwWwoVgdlZapyif2q6kY3YkKecpyGETDpaZP91NGEzz5ViRMuQNhFWLPfd0gG1tn5mRak+yZ/jPVsEfkKbUaFrQSbEX501gQn7VvBK5N8vWRHApNDxAr4rZvhILMSRsh2dag91arMFADNvx9AMYA0a6Zg7BRc4OQ2a1EMKICM1ShG1wyphlm+C9NVk0HATYCBOLKKIKOAzWldR4mgeglGKSFOyDPT0RLJiOZrcN7vWvEHqHp+aJemurhNuKGRdnSJRHH8jd0515tk/sk/Css0KVwm0VQDqQqU0GToCxIrWiOOMoYZ9TM95C1/hga7B553QfTUIqVjYy7KV+2ScewOhT9YoHZdKbvnv7x327vhciaLoPIZZ76ZP/8rYOYYNTdfGWWG7EcWLL90ERfH9pDYUxDjYWHA8xsV54sCrCIabfRdiJWR5QhL2qRos9NsU+r4BlqE4FFeeS4Wp79qrwpqp6vdXcM7a2LfmgYlZ8MPNBpSNbQoBfGVPEdfIRNygEKNICeB1lSV404QKVFrmkW0vL+rdxCatsqyMNOtvDEYKTFR/0CTSy7Yl9ai3h3s2lahu4jEHMGgmVEmT1jrtjoIg5IQidVXnCWpZVu2isqbFJJUp2KYUWqyeSXhi4QoYid12RKjaG03xOaBRAihnZ89PPhe9Jf5h8MFbeXPT+quP9hFqENYcfHiUnv6kW25vWosHZtlBy2JDikxClUIkmKuaqwjbByskcBBOg+ObWWZSGEZqHy1pXE1I4GCSPHX47F//9yLZPEf9YXDnV9y1xOEprZohjv6PEtRgyRKxiy6FGnn9gcwsNojapBEvNVp74ISIwNomWbci2CAqqaTg8JwwHGnjOubUN9nTO4Th4+o9PdL4m+4nPStkB7V320aaXA9rG+RKLjQ4AcXOWWC/2GppNSclaGbzWnqd9ADLCz5QCDr0PXpATredIlCtwPIOvpkjZYF4ElFCVJ1AgSDW2mcyuApPOd4wdnha9x8peTFGvYW7kSNe7sBNMcbWvkWadhkbCrcFNiSkYr001mafbF0mR58wKD/NrcEVIq8SkepIs5cDcNlHzfIbV2ZybAUOByxTM6YmpJ7sN03cH47DFQbZUrEAGZ3pWlkkmeLdjIeBTioxDnrlGobHihQpKPPrCs4rS0eI7Gf6oSLJEl1PWhUSwTguvTDxRR8lunjkGM/f4F4gMn+yWDD1AY65wMSJMak63oMiZ3ZhwdTUKD8xpBPPqARnVSsxfARwSHE8KtoKp4IQM8PpL5b5D2GfSFo6rDKtsv6a3AB0mJOs+wxB2OTh18kluwuLZh9u/yhrenAXgbwVKpzkpjayBhIK5TqEa50JW0VCu3G3FQz5FH04pYLqVi1yDf9q5V1wVy8X3ct8c9KLYT8AcjHGuqfdwOvIL0MgJ78z+kXdSud1anRKAPSFP65wB/HGtZjhKLSUyDJuUtVxMVUuOIgedg8rFikIUa1Hw5k62A+MG3CYNsuiVfRxg+v2lFSFc9OrAgY7uulNuXSsRlsoEwzqxqi01K0qpmoTDLlN0RWqXrHAqcPsbE8QkZpxkNtusyTYTCBYgxtScWsVBU7BRyt5uOwuCjf7YbWldPhKhzo7c2SUYRioupTkAGmcz3+fFsdlbWFNYVUqxCOG55aFmbAPQf/OmpszqvkJV8+QHpkHLJiUdnMnJarNDsOCWIuucado77lvs+bcvBplrnI8i96+//dN3Xz97ftGHwl/83bPvvv/nv//sD18e3QUoGDVPNzkl9sY7K5+zkbGVBrBJ1SsZuRDZqxik0zwjnvBLrQFqVm7MkgFQCPsmJSyCb9tNhwsxYM3HX2Mr/P2ic/fZhd9/w78rz7EZQ0nOZr4BZ/4ulVRLfRJK+zAjulSGwm6ZWsrEhKvCyOSNLly5GZWKrsnss1U5JVFTTRo6qcSEPQi1OV9DSZwYkav5v4Hm+XBlzkrq46lZgU186BrLL4meHWI163kePOKdu6DxPZhXuG011iZMtDADVVZAn6rw3/+vum9NjiNJzrwKrHdWJtkO2OHxDvxjk6CaKzbZItm9M7uSlcWzBxo2SSPA1vTKNHdYM11AF9AJ1vaP/uscOsa6R2YWKjOrMrOAKgA0YzeJAhCR6RHh8fnrc6KaAm2J68hRUSKCVtROWQgdKTjew/67O6dU7C+GvV4JA9FR2DvQd0/6qOG9XM2VBwnNRyUqI9rLhCgeVGHC4G7G60NxXwJ4IinJOpkAxSi8B0A4NMnQ7gXNjfZA7lM01fxmvG8iylojBEqccX2oONQ9iH6T9KVh+ppOOZjviS4j3gq48RN4xTNzuJUj7nsXBeJ/67hFUywj7jfGGqJ/jZlCrjlqkbTs0U3tSgW0xK92A4XzAPyhY9k39SkNCppi2XV8QYVQVBmViswe1beMlBCuoSTlmEcTDGWPcN8EXI5kuUPLxokUjPV4JyeNXy5t1eSo4pmZAVXmHz+Ui41uIF+C3qkL0GQ+TfIKOmmHqH/ki+bK5OhCTkBhADSHY5KOGVZY8Z4ZvFSV9cEyk8E7iwgU4VH2pXiWFE+9FNgJ0Vd2I/ozJtJsDN69s87uS+wdv8uUrgfjhnt+lO0neMSTIbmO0oagqCcZ5TSBj15oKlZBjClDUmj6ltqGgXkXAun6gAAIehk1u3F/1zWrHwOoZu56y++dfXxfoq/pTCu8HafJNGeJeTm3oqDxZKlblodQPEJGq4pJ1GCIWj1pyuxDUVsFXCG6FLikIkiEOQav5jlsCaTqdzjVqrZpCL32plG/L1VfOz9Vz2YXgZzuzYf7esQvgp8aGDh6EMRwxPhKZoO4J4AEvGdj5nQFcwschcEzd4q6LlOTLZu9yVY4tNBCYnsRLrAzpfZMOp6MhI1ZTY/hbhsvxTrJsgmBTbJMiRHH5pgCQIFmWSDIFxzVuopOuyCI0M7YZIynyzhAoFIt1P6FS0pOdto7Oi46bwLOaV8bnHE76OVwi0DkvZ2ETvyr1+c/Pj//H4+evPlx9+Wr5/SQ00E2tOAoYSWNdCWb4kVKSRGbJjmZi9c+Mo2Wmy+SEZk1i0HrIpVfQr6u6QDcxLn/IC+AGv1dtVt/Au473MwjT7OjBjA96JOjT1RfrnTwgosCLBioZMYGihII9nmW1hZqslEsL4xR8jfzlZkWwegyBcS7MLwZ5v906mdrg/cH4O0fL0DTZmfVdtuZZNZEXTOz/YvQBe1WhJKGOKVMIPY0cAZy5rZ6E5SDggaW9oF77qLzknqNJoo/KrYszZ5Xi0vCGfT0/y2Kcu9h87e3bpv90GZiTZb8cKf10OIdQ1BEPkSYVlB7BkeNjCy3kclIrbzAQpaMKSLhTHQDhJCFCppqVLKXWffZSHZz71T9I90Z9FyetfqtjfDuzXh0D0vQZnA2bFNTSSecWTtC/4CASEJP+RTvBNpUylMZKJUf4l2QJd6zAgBXQmQeXXXqANpZXku8poMgj3SyaPP2Iru7/A1mVy+fanetwc8XcPleUwtO8U0xN6q9HSEeg7CoRM7RotKCMudxYWJGtW6ND7pkgbZVSJH4XzJVn3OZDB4QfBYvIIh+IcNEf0YGRG3Xd7Ft1pW4L8Hqass+W07l5ghMVzUIo8f8dsLxfmdBy2xgokRDqYY8U5WbZyUz6t1hqetokpmbIsAaHlRgskSlfMgpG0uutznNz6n4cwfwmQk1PjRfW5+K5wRNqKlaHksbZQQ7qSdjX/fowGJhEHOIaGwhmozKWwRCTHgmJCS0eLlX2iQGACr5Yr0oDvESGgmwkGBTAJG6Awxgf9/y2trW6oEegybG0nGSTPk8BdMj8O+EsLZ//UbqV5WZCih97QozQnopWEp4OJTUxqdChOMFFZBMNgVq2Ev9hESKKsKs8dXQ+25PPx/Yv1/AFdAuQpeB0ra2WRNjcDN1K1un2cgeGLKToHaPOuD2hoB3gEzB6Rg4jxLhpg82FKeNSGQTOGq4LrKWAaErl85mI1OZWw9o+fBuwLf/QLVS45Brl2QFTkydCs2kHrmFNNOc9Vtw2pKslZnuAWEU3sfcEu+vwYVAUacYiwWT0Lx23lJqnDB4eUQDxkqPaGoZKK2Z6ZIPGijflPX9/nQShR1P2kjApDlm1KhH+CgUoAIVeAaXlGehaE9AM6BQVVAk9ZA9mccRNRMXEW00huKMaDMzcgnFeYdc09ppe8ydwr5t2fPezU/v4QBcF93+z3//v58u4h+oJuMEzDTzvkKdMzLL8FMj+/F3onMXMaCyKUIajQpGyaIs0Zoo/JGSKPWKGMVwMQIujBICgZFn3KEh581sCpwix9AOkpibp6TfyzrUfNumCXNbUzaxAKKh/J30yeFtbNE6AKEt8ZNob6i43wdfnPMOheekD6hzDH6uGCUeIkLFPzrh0Uib0HTCPmjCMnJQ6Fxr/2s47AGbxBt1kP7z1YdLT/aw/+MukXM+6vY5FHmEaDTiHZEoszlJvFKJUBlvYaazl4pZaYuNKRjJlNYCtQ1aAtIhGDU88wV+ICZ23buztUhTG74GtvtCFxu9zQ7ohtsQeq3Fqwp/1ZBDtopo2i4D7cZczJxb29M7haGZVfVRQQgaEkrXCAEaKO08eCjFxYRnCLe6TghKvaEMOQRJCX9W93rd7iKnsrvsspkL4MFtflqHSs62YpJPOaOl5JwPZT/udpMMUEMz7lxUaAYXhkfC4/8ysd8Z1PkFuJGkgtC2cEzGyIxn0uI/DHN2IekIf8tqDTrblQfq9rUF7u0QVGfouqC463sAZtJHJLgZrcXIL4rahQcbDQJMkBlVUUYBJCYdXtOGacE8U9JaLmi5RHIWbwGXk9cczTetlmVCU0quqtwjW7oPtzm5DzcRa7AW17VHK0Quk6pIMxBMCq5HDdCa7yg3qBPWweDlq4IV3kTpglRc4Q/ySMaXi14JkAqfJ+INHYWKxBejfJESEUxy/a6LOxNURG3AzeAMDtIG6j7WodcGjYbi10twBKIBqmhEcckzoUaqpBqyi8OKG7K6ltFCpoFniPzex/z1i4wy+HRJlJlddKqyld5IhhvMDjvvU6ZgRN9CTSN6WzegBWUzIE6nvhJ4TyTmK5c7sY6bYCz3CCx9KoKpQi230BpOhVNFvKXWKssUiaxpbUOuTSK+bnCN+CLu041OWiedt5PDZE2LJNg4THCjZsP9PooBBIIUIjl1aKdKZiOaSZIJY1IIWQMrMmm0uGzMDpwXuGKKR63QxNXE6bVoFZip6txsi7RQOrPYN5P8Xu7Vughtlft6FaqlNd1hxWg31Chj8l9FLMzCRFOCEZJ8+wZ4MNX9nFRE9BNE1kZ7lIoLiES8CMAjU5FKXmbdnbLjGNwV8LrRMlR29f4yaHEny9AgmknSZSHHzv4hxwkVS6fotOCO+Vx08YgtEc8bY4PBfyiXOX4aFCcSJJEBMnNUkoS6zKvNJvQT7jRL/VWUHvTSukKD9nKqjPdhKqHWo7OqvoVVewpWwMy0iWX1XIUd5eNm67UkolPuAsmeRS0rulEuoTqShWgf8IAQr5RF4Gmii9xqLzibTTFf03kpyrbam2XzYVTZbaxGzTusHs7qaJ4UvxnVFPUrKyKKHZUJ1U24YCSaUoYlACVystQuuqQc8ZIQQMz8ilFvIbRxBRGiJLeQgB8tWyYp1aHP8DXb0fJhZBpuCL51Liv2X08uo3+XV03o6/F/Q2PX6SnKNW2GYZbeMjDuhRGRRYhWJG2DpUZyDM2qaIOAgIAeOBpfEDm+Z1DZIGgClwyV9nI962BYM2tSpeOZXOrcn9z5arzzj+PVHC9AE19pyGeaNZjKfBZMzN0GkTniZsxG4K2LxhP1nHDC6ZDxiojOUXwLdb9JqiAwDd7GgLhUa7RFg0ezd5n8HRV2kS1lh4H35hCIB0o8s3UNmvqukxaZgrVT2x8MmbajBAhD+T99rl/JoyheB5S91QqvY25RD4ExWWfjKSosIl4IVNrouSV1lY2l6EuwEE2P12HqWgZKfD4TfOhpe9gVduNVWOc9U0+E+Ra7yjE9SzjDERjpBIExwZNilmuE/0pyr1UouCTk1nfAcmEsKF3wn46aJOAFDjoYt8n6ONn/jA4DLoPebp2ZfcNdlV7q+PRvr89fPj1/ffojb2usTzkXj168+uudW18Reclw5ys18OZwVEAMqIGcFwlBTyHqMQUlsOCLtM4UDfi51JKaH6hoUhaFiUz1RxxMz7e205sD4i3nlPQP4zK767KXfRke7sgia9wXJ+AaNFor7NrcqxN850l2ayaGKzC8AdAKDjIkxJ5e5Ix6Xhclo4mJ8RJkxrvZlRjQ/ooioKEcYsDPiovS4J/MF7ZgqZteyUG51yYQ2p9X+W60z0D6HePbZGUvzAUVEwJJ2twxOA8RwFL8SkOAlKSMKGChOfkeEARpVRD7IyIC4oJIwuCvzSaaq1rMvj2eu1Fw9EBzrQYif/fhpw9t37N1y0uwZrLkCKxzdhTfAuqQ3vdBaBaj8wG/MiqgISaU49ISgwnhnOhAlRJsVhGBkZVJZG4YJC4T9UlLm/hzosC67n7UPv3kki+AbGOwEi30maHZkxbMMK1n1HUoGwMloQFsIDtHrYSyYs7gjQsqKGuJ+VBIVyRqI8D/DKDU8Sb2iZvCUz+kMpF2S5T6bqB2buCSfghyb3H/ZLMhzsAIPqrxZVzIPsmhEFkK7U3Ce1Q764XQWeKeVoULhDvacR25ybjUaJxZcgZF1FFEpQ/KBDkL/GvbIdjeW6J2v2xd0Q+02mK4AJ9//rhqSU0m021ney8GHQJ1XWSmFEm3rczRojFQLEOkkQOzuuCtbUPWaBvL4iNoF5T3CDFDEXJO7tRdaBfPKtW4rB0+DzSUOBD8Os9/suMfqpFRx4JxdZeT1EPXEqdVQS1PaiZSMwJHPrgoBYRiC9d4UpgkJOdw75dsQoYskncL2htTr93t/uZ1EtXe5UWwxd9zfJBZY+kzxRVWj8gExhEvyuXnQrGSQgDiyy5cGZNE0Mwyaax3lnmHsB4XoGRbGE/4s3i9Rpa1MGlO6Ioaau1o69TAy6ap9L7o8n7E3tIK/+Uv/K8mjFmuZ7nbonCJemaZLClRKjIrGDmZgw1OKol4E7zMIaEGQgvHAMedr7zjGfd9SHm2oELW1kF2q9hv0VjxfqTeVLI36SNd9iYoN6lzFAc16vJK9A397W9ZcjkUibBFFLztpNfJCSOcDGjocqtisNyhGRUTSECN5Hz02ciAEJTI9Hr4coJEjFnKHOlHW379fPm5XBdWfBlrsdFgsUtd6FCnhKnqdis4jNSRtYMiOw2RWxMVmgK49bmyxXjUNHgUGLGd0OpwiUg+B20NI8qNLApH5M+pyY1dRq4nWG25YM6EHmfyVHUk9k3nvJ/FaCg9J8MsSiPYH3qZlcaT0DsHPnklREpROhEYfpGKFuTwL4D3A6J7SqlSHqjzui/McOIzZIZlnmLUcVllNUUdKeR4Ju3BMqjuXPBNKueaV2PSvT/icxheA0wWtHlRvlFJkTMwX5L3xSRUP0AdpjNj3qP0qZ2lCyYFtMK0xf9wkaxcpn6a7T5q0tKonzbKta+n4c7F3qYLctu0E5m6fceFE6PuiZ5Y/J1GNWN1Nqj7KcGBrFkQ+D9nuHUuC5tFbXNB/DKMcmpDwE0qWJoTu6C0WbHduKrG7ZpIYN/mifco98rZ1sW2GHeTxM3j6O5wDSxzXKBtlQQxYTOq2cUjYJJFW8EDmrIGtY9jGVWMC7jVi7GQIsfDIqxtckKXtZYG6tnHezfvTPHWA12An7L/FD78ieytKRtXA4r2q5lQSjDZeNzoAXzgSbqMF6+XYMltnxhFUaidqGIUaGdBoa6RgXrrGK8Cop9ZmvIuY5biKHZAml3dC43e2TeidY/SJxfDaetdPl1XE03lkZPMh+6GUZ8+as8HyhI/PIsONM9aU0m2sxRydy66iOcgK1lYiU4ZiNkraioqqY4xz168ovOz7aKUafDOg7d6rxei5pd0ZwFfcJJSaZZFEq1dSg2VCTe/jkFkGSJh/lBYpva5ISLEwW/4olAJGbS+8CJGIy0EJUzIs5XVqrJIbrd/v0w1VIlTp3p5I/AepYqPu7gkVD+ueMMppzNpEwQ1TGCIbIrLTBidTCpGQkrMeTxKeEKKVSZlyXLRcTaYW0MssF3wFMylgPqXBHvadgmnbXrbKYPptH0uzFwdV1CBOuJYgeAzeFQoWniBmBM3No/UzzvjPUt5bEaTO87kbBCaAi1XCsXYub2/vgRMzXYe+/hvGFy5x1XouiZMJxaauUZ2lhs0WBN5EYghT3JBjRNMwKu3QFai+CKMwZvA4rroYn1WGQ1jFZhNscQlfBpsV+HuLdrY37ngaz5Vd9VO4E0r9SiYOCSS4RbvTgkxEhcY10ZkyyLj+Bmi/4Q/7QxA0IbI+9EcKFYQNALudfQ5qOU9Qx0BTpBDz34TUNlKHfagZF7bPnIx7dIHO6qmGLk4jUrEfR2I6D1ELYPQxfBgoTjvs3QQiLyZsgUlUAuiggizOOnQAuC858qZI6siagCxI4KlHvwmr0WJp12O1FT0EDHinGbhKRsphQ6os40ytVGaQ4OAFDjliaPeIX3io0wMxZ+1oB47FldJcLBlNmFTUG3ujhaZt6EovA+pU8JCF8BqO3BPdyOyfMQSM67J1QzQfpU4puFQmzFaKksUihswiG4gWzwXXFCtkfGo3p1MufhQONoGwSzj6uGa2qIpuljHCfwVUu6dv3/nK9BmCjb5Uk1Aa7oXwihbbdynUQOVdHo0siwoyoklRC+9LlxD4Ca76CMYBJAILL1EA00kJkAEhvaWVv2a3J3+tNoHgQgibV/n/OTjr3/3dwQuG4rsBx/Taug5qTnplK7nruEBnizBDSlTu5UkCxgqObemcCINYzEgyHeK49/FkmUlG6r4CCIKx0IKnGc1m6YmiSFshx01k6j8oET+H/+S3135VZMsu6Ls5KkgLurw2cawUEtUBNOOCuaY1EZy8AkxZIbKDkN+ZBVzSTYV4iLJLHrqoUxOnjybsCAogDvFSfuwHQjkLOja/f1lpR35q8nNrtWoyd9I4mg1ZS/QZMq6MB6i1EpxDoJ7w6IoTmUF2gDD48CVxd2dIXvqAFWIOn4hC60lFlruBjTY7y/eXXZ5yA9U5M0OPxG26brVUo44PkU6oin1YOS05FwNwE3QUfFK7gWaO5WML4opqykvBAQiy8BzYjInh/Cd4davyctE2Rwk08tykZtwCcgzxkfOmutc5C9B9k0d6ASiEWhizmz24CSQq5hIpQTzzuAWjzpYh8YpngOPh4GhcVS8h8IR42QbFe5zG43VOsdZlgvR1T3s5Hqp+kXv28/yjnK/+wJvGuvWWn7nroV+42L+icBGrRShyjV+W4ltyOlaPgur+XfVg4BibZfhzTLx04b8aaMaZE/5dskfLVaf5A1xIM1wcwsycnqAUaSceJah4K7OXhalvEGsYrPLlM+nmURdj7hfKbRRWYjgM54CHxkURfQhyxbLURRK8YFTYDrn7EFt7usGQm1x+WTmGTeOjT3A3JKW3xS+ZZoHJWOSIjO8eEN0xBkiDOp3LoALbyPapsTejlYtsxArKUOAiOobAec8ZmSwK9eyFpg3F+m+DSzvR/qd37ehTut6CU2wN+IBGN6olHHWQ+3FBpMRHopIFT4icCkNxVoVsaWhhi+xgKOaQ26I9hcv0oL6ntxjOrOc+mHAnT4aRu0kmB4EYW/eQ/HOL9O6AG1pQ9c4d9VYrJMdo+28xQpN1w4DYIhfHE3SpFJiSvqE12sSrHgJipcgnE8gtLEC72ERrcxBZtjM896V9Kp25V/WM9A09HigTGrXS9Amd68YVzNELzCH3zNPxFcHuI8LhVmdtyjUooIUWlrri4w6JQTs+K9kNKSoAFfFFB09mrWzLjJVXWTbG8d9QTq/FvO3nBYTFbSCjzb5iEYBISTwEokb2eDfxIXMeSnOWMdCwe0steDEIeI5lbLZFNCklUL5xFJks3EmRXqeb0/svk3d5l1LvHWIdXQuLX37lOyFmEs0LlQ/SMVQqZaHECedl1ZLnb3NFFhiSjHc7SaYkJR0RF7nKCsZlyf387snoh6GEj0kH5BxVWO1ifGpB2+sbvDzTqIbace1DKPqqaDJBy9ETTNLpqCkUwAWjWAusSw4Ikq0mJJyuOulKJzniJZU4C5TsGPWRQBURQLbraab96S/rw3fyHx3Ig3C9rlsMqOSkCFzaYpzCBEd9whiBBjQAc1XkZ0RKnH8Ds/ZOfLJiwLWA4IkZ/3CpoimBvfcgAFwLXD7QGN7I4G3dtTpp1ztqKn7VKLpMzRXR9ud4YbG9/GZOn8iUtEeRatEFEFTVrFXkQiPkwrcos7XUWllJFANlSrK9FpS7mqNQnVTh+79fOf7vXUDdwq+TWKawpANT+g0R1E0xkUIkYqRISQoeL0G6kyMYMa64lLWArENR+tKswDUI06AdWCNUT2ytMmMeRQ8+cR6YdYbsi3e+bZv9/ujf/i4W8ew2XQZRd2bfdY6C/IwMi4iM4lqY/HzInXMDqE72VO4qZ1AbV8ytSTDy5WU0AaMgd0sjdSJpmm8KneEVh+Yq73CRAVft03eJoq+uSB67qFBRCQUfaYVrSLaOWAccCeVsoEYAgHvz6g5QhfgOXCFaAWxi6lsxyFZE6OPsvjca3E4WYrABSGWflbSQ3bydoLutMZkS9VZWgljUV1nVRwqXEhWm1hQc3Ntc4ipUE2NjIFKkCPiEZVRgwedHYAtMiNQX3hhVpVNHIv6y8jOILKa6wqnySwva5kZk/lZafqJ1hCoiIkbZxyPuNXR4EEVYpXjIahsjfKMM5NL9KpQJY1ArCySjsYFyxRsZgPs6hljpzoDNHFRvu/VyI/KotjyoFdX1rQXV4kxbavQKIp+Yx7cyzHEgAgv4e0G4Cl/DgGIDwbNe5ULKhOVqVVVYc6XDFJLFijtTjjba0810RVV1JSLIfq7Bf44rpDfIKpu2WhmstSHZBCjnKIieeDRpsRYpoQVY4IHhQrCGIgKOOI/7VBbyIR6BIJCkVsQTJmIoKNshph325AAxMXH7JmQu/JEHxb/TyPfmi3XVEBO1SQxxYZSHrkCffbCmlISnn9RtI2OWQhSZlQqDA1JzxC9FUW8t5RCBzpKtB29FqTGrZ6tfxfVTbLdaJwhnbnvXbxmEzN2zZjd5A2R/Cdz5izF5geiH1Hdgszgo+HeyGLRdESYRwgOF8RRgzyjUQ0Z6YuOLEXijBfAfCJAgmZ8GrBNTvjB6Ta0A5q9zfLHvZmfj3sdjoXfam5KGZqKK6OhMUJ64+Cbc064aCX1703SobWuPSFliXoaT6pAUyUX6ueFIicWCLw2Od6OeAhwfYD3UlcmjXZTg2/6QEb7mF/SsCOJ/LSp8D1dEHQzcs5+SUo5nbIQHrVHwBPgIw9OpBSsImbuEEoRPiZGKdAWv417SQfJiq0507OZQg2lzPZQw1xq6H0rmHVBVyPqLht0AmNrPUmcajnx4ymEzEZQsrQxaIg7ow3CExcD8zY5h9s4qmLwN4JAOxFXgJIVmci9zizTXIXqjMMg+3mjY+beLpGjchW+zZdXJ6+r0+ny6/gHj9fNZe3DxakLyG6MUhs7jbC2tqLvhuJa2BRNIFXNElFmGISK1kHyjthQhDBZcReZJ6qTwlCVoH7xLiXAP2XTppkgC2NE5iDVgKrwdtXUR1UpPalvNP6oV+eE1BEkKzbiyMZP9aATjmGow2XgxUOWpJ2J2ISTO8l7GwUxPyQTM48iSoaLo5KMlEnhhWKWhdncT6gxzN3EPQ2Xyb4BteOqlbcfPrxrqPFO2tDlCWOTm9wow0eV60ZDE0S+9rWiSuYmGVtQMZCpnpl22QhuI8rSOQSDBiG4iYrFGKQpMgSXJUdxu+LEEmIwvatg9Oas/Hch7DZWuRuF405ErDGEJRaheS8txXNumEYFLrO0jHrXUQocZwzNII+IOyQpaX9DyaZwNHYyUHfkWKIOOsCyJHJK4FdnCgYOqIb1vbkot7Y3u0c1UoX8Kb9P+VOF3Sftv5mx69TaqfIJ1BJyVD4xIqRCzRAk4L4WJoSQcAt7jlodEHjzJHiE6r7OKuHvoblkAt6oaMPrpCmc5haWaTnimwU38LJ2daHqYWHCTvKV0BpP6JSTVY9gYB+WOMddDokVCIJqOUtwiviMcG8nI4JjxRiTWMi4pXMGrS0V38aIYBF/uJfwM8Xmy+BM6DM+5p1qcAl/WKHJTsC/PPrm5OeL95+v8uXJmkt/Ot3EMmVGmcsI+IhWvIdNnC+SuRS4JVpBQOiC4Do7NNx11I5CCShwXBKvvaRmZlmDs4nU9x7bWpEPRSA8OVwb+7vY2k2qKN7ybLp7ioZRIBhlqns7PDLhJdWKGwkeOBqNRQfc1IwyphziQOLJLNEg/o7aulBwj2uJex9tHiXtrJXTNY4AW+Nh5lAJy8ftG9HYkStczanSfQ5yLnmqcKYz5UBED2ihW4t73WZwgSHiKAUBN+K/TFVvPOBtGcihrYvSlsXgbZltOVxJGnf4s5vLcaI9zSQCGe/jW8r3Df58Tl9/69+nD7/kT+sMzTaqPklLIcf5sYYPuI9FSYCA2Stqaesl6gyfDCXzoH0u8TMRNI/OJI2qRkQ0NUvS0RP9rqCCh2UmJNNkzggzSCT/+OniV38dCdtaoj8lbXFwvDeUdhdEr3RQDR4BZ6YsdiVm2UDAU9/m4kvAu08BlX7jLk64z1m0qLgNMaDlQKaOwHMQtNeO8mIRoXiO52Ap+GC1Zhm2KI+b+gG3sL/eruHGUN4t71mjqqeS0ohDa0bMyZKUVcicjMHiEY3gKyN8FngGrEak5xIK2BvjiKIoS1eo75uPljqhyGXsQ0yRjhbusH2Vjr+xu/KIqeCjYHIuaBNKQasLrRMdDBGK5ljQeLHFCmNV5vS5LMIF4xNHoI2ipVz85B0CbwFi04rZrT3IGcLPuBoEeMkBRTha72smHl+6842pqOf4KKW11rv2cIZQKQsv0DJBBCd9sJIYtBQXEqGGoHaEoVjIOlrtVYoi4E9oxjTiE7y80uImhZQ3LwYhg43ihf17YB/9HvzPf/t///lv/3rSpt+04ZopxWxHRK3DzazJHR1RAyj8WV7r+tBGjEwbJ5LRkjoD4I0YlNfUgsR5vB8ZanFPtHLMybnNLAh17PAw3UbYR9vPb/PPeOWhndKhjpPqanr9F0+nafko8Xpog/e2Nbcx4sVXUnGoi7PleAlSz3DEchRiENFSmXcpCAEzRLx4HGI/6QIg4EN8t5mvMEmIC3Am5ZmyoyDBjSpCbkJ+/u0L+l3YU9xdFUhL+d/GCaZMRA4azdcR5T9oPvR8MDIEtZCAOzamABL1NQtScgWm4IUoUMsYgtSoyUFTxSzeoiHlTK4qPevZk+RGZdsrueeouO95k7eQepLvSjI+VCOjELuCwBFKG41WYUSJGI7WitXchFQSAhGuyT9ibUA9IqWmQC95Wb1QPoAXs4mqXTs7zivw6OG7//0hdxl8+1YiHL6l3UjCtVAenJxMK8N9NUuzlKQqxCeplBIMUZtOLEkbQJsUDfOOEcNtNMmx6IsIwvNSyO3BhaJ/wDIRI7ajS3FwLzb0J80u3jcccPiGmWMZtzwEDflDk8AwlZOK6poN7fHRltYlohLOEbT3iXpE+YzWH72QD/ijCAI5s8UFnT2KWiAGjNHi/5QI0QSzoNSA5L2dy7ZejR2Udvd0Of79b7/Kf4rvPl9efHh/+dXZ/7pegKf58uKn918//hT/cPFLvu6O2eXrXP3paiT6T9mTB+rsq/PfPXnxw9Pzp6vvH799e/76JX4vZXyHd/V7KBG8jDZXu53sG7QuUtcWm9IktuamrGf52x8ev3788u3zlzWJej0BhXgcrlAQCDMdQ/s+GVxD7iGzbH0yEQ+U0hCLZMVQJSbV21NzcnLJFLf7yTrrYpsBN/dUQgeHaBdt4VIcLiCaxI4hWAC0MHixORWImgW0iNEmNiIzNNgMdbGJ1BkxiG1P9eTD+5g/Xl1+jbI6JXkddFE2XWDffL54ly7XLLpNvvJJ4/RFDHz0idvkf7QtjjfVs4tPP/8jap2vWy/2afOWrUsKf1fdwdzrXIoT1OBb3Y1zGy2VmPFGppZSGu8NvH6tEZb8BHgMIConCm4xkILKe0pmxUH2VEloFV7hIc/XBlSv0WlXBwPHXJP1nO2O46JyGTSZVHc6bZtx0aa4dC/Pgd/pU7Q1SH/+TbMpjd6e17R8eibmp2/V3okUzXFsWcdq5dm0hp6dXi14+9H07Qerto5/W0DvyE/Q8cmipb2VRuDI07c8WAz0VgR0tNnp6LW9G2pr2qr/72D/Dx6h2/13vPer96sjYDlt9cHdvn17/FtGmGYbnDJnphHJ0+dvvn/1pn9LvP7ulLwP7ObTb4vRHG3KbtdxuU5h5gDTu/+Iz0DlRNOX8xEnb3o5tSpoWvsd+inIT7bdX3O0KdvQCTPqble7MXNOax/6U6bVjLI59PTr3oB3erIbTktyhE6qtdtN+/0ppYU1XEjthUb2C1hxF2hiy+yB/v/o6ufbwAhYcJdsmfr7H777/tF/f/Pq5V2+Nd2hnY3ThHSOf4ntfADcbKec34UJMXqEN+f//n8ev3j09ndv73rmyuW23SM7Z94ZFb3M1lsmBIQoDU/KCK2j80J7bokHpjipRcIfEiZqDVZLlriBQo3n93zapn1gkwFzAlw27RvvZLGUcK23rz0s11llt5t/4YEZzd/ewSsANn35H+0J2gDKCYCZ2T1He4R1QVP7LLcF4bd+jpq9slF3fDd3yOh5mnzeVW2mXO3jFagZB87RnmWjz2TrKbnzRbprO60/e+Wca+w1BnZ6FX54+fr8yasfz18//ubF+ebcnasd9I2mv/bkdW7ju9aaLai77rc1fTQOIohrsu5mK/4X2N5v7bB7bzhrVzXC2Y4+P8edvtEFp/fz7o1T3tnWclp1OSTbiHKO+yQto2/tfXgHjqrh9E0qzarRQWvmSRDqTkVRdUEt8DhpP2wgFRfmDhTC4Dn+/JsWdt+FSr6euwVOp82KtAW5d/nynXnb1Nx0KKrTy5PbYQcMhyiELUUQe4DVuViXLDMWfJE2WOMVNQeLWgTQLCYRjbZe8qyNKFHKsECTXjMwNdu5K/nsnr6rtQBt7wAPD5+my5xqjxVq2tuacDd5irb2AS2crZlbx528OcdMm0lP6FGm3qTZ2ZJycqzJqw6p6rwrX+uyMgC12bRfcMc5ii5564MJURljk5cC/8ogS6Eu5sRJqKSPzFLbWkFtTxwEJ1U0wmlpwNyAwK+NplEqRCW3GBHNr5/5ze+/e/H85d+szt88efx9DxLdhKhx0IOwQ+ZbilpnQ7yQRUChMc6pl7jg0TjnvAtGgwrS8VB4okISFamyGEWrY5LJac+pC6fb+fQdTVbjn5h0Le94NG28kNly66gvtFVeUGfcwn1MBRFkVvjHe+6pAzpegUl6FUARnR4l4di4B51GqwBXzVa8kRYPUKwM2YictcVNqIwy3mZVfEKVbjnKWUmepAooQPw8c2plzWPwmYmsdx+eXtl4A4AmF3oWexu+bK7O5uLsiFd8U3j27asf3jx/+denr549O399+t3jlz8c2pn2DGHT+5jJiDhtU09a8vbqMpw2Z1798Hb16tnqzZNXE0e3m+GbajHVRJpppHqjUVuN02GvSZf+jSZoU6Za1XKECZoSIbNOAOpaeU7dfDeaqOXI6YJ8bfQHHBxjtVuA2MVBWnsFuJhWfTeaq03s7+Zq8hcnL++9pnneVHRd50kSM0jLfDOleG42yTr9RchpvbvX8C8yiupTm1+0audYpN5vNE0HYcG4A56YbvTW5jnCyBQzWv34+MWP54++e3rgsV//xdNVcyq2FxPfbvQaXrzuGgmWH3BzdpPUtKSD6aVu1I4F94BaqIaWTy5RzeG4h5PDJklNU2dRo/aHu9X+41/OX7x9fNL+xZh79P3TZ7cc+0X+yb/7us3t7mzKRjQnDLHM7fVxM8PTi8v47sPl50/5suud2TBDNF+AnjNjbjhX27Kwia+30b9b6/7xNE1qCDVGnDSHbzh6PVnHWIm3f/j8c7hU7lEKBx+7DV2Sf+IAZ7cZvwH0k67dPUZrnINdSTZYOYPc9xi61rUdRiE2A37nr65IHTb7+QCXcn/YKtjOQp72J91g9A68Nr24gPbbrbVufwayn9E0EQc7fpsDr6pnv8t6PdTu62ZovVlKzQRMbjD0Rjiy2+WTDbtvM1fn9N/ZEfkmg7cVAG1U6ZRO1SkDdzBd2Noh1zU2XczmsBOsAOBgW77LPzzUTu8u/bWHp1oBB7glv/OfUJTktnjif/7oL356f7nOIW0v/7ak6fbS3jZXmy17nMGbhnZtrmKXknx7qLdtqraj0u33z/Xg57/k92gad21utdja5vaWo8cPn/Kj9Hkqu+9mAzcCWa1P7eoY8m/nqv4XMumvswpAsgMouNFMrd+6M1+PMEPrCanmzyEum+sJWjfYMCPo1tjneoY2HdiZgy7y9whU15yuhzC8h0M3sr49ZBiOWxHJaRfZaB0HB13S9TwX+R9Pu015e9h5PUFjMlHkp3IS7w4G7TluxVOrFu80GWEHvQMGDCG33uNv4ieP1jZ5wLt0z5YT9PbS7sauUjgForxsEpIOsFW6sUnDrx3hrSOBVOTt8Ul/hjb+ACAOYab1x67ht84L7dQBlG9//MbOdnB7O7s/7sJEvxuM3MUZbo86+uO2lH7k7mxw5sHOT7MDO+9Se5JaT1bNnb49oh1O1bSCOYDfajhw+/QN0OmKvju22oNJrDOrNm7sw6mcSs1BPsrDif3q54/N6jZbZ9Us7goMHHL/X89S3RWrxud0MKHT8AvqXvYes+utfTjFTqNW/NJwrh945NYCbFxCB1YF11i9KZQ93K7+82++e/7yh7fnbx49ffXkdwcatLPAGeOHwKAtg8uTD++vEKNcrbspHeCIDEfuUuNay6KDibfHu6OZWiC6DmF1RRAH8GON5mrvqJY08vbO0HaCLpGidWo1euUA2nFAZNdaxw2GbKm+VpQsd9C8z+GsjReToLutHa92w/m5mYDxbTM9f4+yo4SUVeelPsCp3hya8HfrD1xXOnN+wA3WTNON3bnxDvwW3Ylkxh0CxW4O3Z6H29tS7ajfNVk560duDMI23nsCaqa4/iZTdZkHXTJIvdhuf+30J2lRG7MHsSP6Y3cMHNcVeYeTUcsR2KbtNyksB9Pk1cJqvCG3d+C0Y7YQAnVC50g+2GFqGR4oK+2m8P7vf/vVx8/v3lVur8oXtrqgATZI2n7xn98RG9iPL96ePnnxdKNjUUOT15KPXeIHopkzrcKvKMKviNXOWRDGMeXW3/vpItTv8Ee8zVocz8v3m1cO5+XcCKUrmdvGnOwR9UrZPqOanFEMZ4TRm1IPJDmekO14xcqhtznh09eDXlC9+fhoPhDC2LpA/QlhxxvK4Ru+evZMTMw4ekNJjYgqW+LgDdX2CSvf3B4TjjYP57QT3PJFNMPtijNOCXX0ioZrqm0ev6LZPqEYyfTlm70mRBhhqGnTeBXZjlW0+804PhlGMSuNHAtVV2WA1xxqp7N/IhLET8Rc+OzNaSVK/JQv8eLLq48fLt5f9SgjoRLd6zPRURjmUnK8uvhlxw8DdecR+kzWH24nRPUzIja8+vUjPcGb3798+y1+efnef7z8w4eraZ7sTx/e0S8Ff9lQlY04bttRnz5/9mzXoM1D1h7W3GwMmi5KGQyqXW0T2Q76/OWT19ODbrx5O+jF+/gp/5xx0d7VFbj848XHj8RHuSkSLqBSOrbzPPvhxYvdEiFma3x40bKzr2+Bb86fvXp9vvrm8Zvz/ltwySuJ7oK3wNEtyRsnALd0dFc7Siwb3VF/G2opaReOrqVePDrUvaLsGe8/+7PHz1+cPx0O7MzygaEOLLtNOP/YpunbdavRnzx++eT8xfjJjZRi8di8dkxgZ1ItGtu6yqy8bGxBG5EzfPSFUnGm0sMvOKO1Q2PdhWds4TYXrIEEy55dVbnIMw4LR0dlvnx0XZUWnMHS0YnUevHopu4XdcaXSkZouXyvW5K7AtS5C0eXTC1WL+BodFSSA8k8ef34zbcr/F288Z6/eXv+8u1gEiXU4lcY3hnzr6D30JC8Hldh2tah69Hf/PD9+es35+RV+Ob3q7q5+5MYphefW17PLSr55s7dYxLrlk8iunYqar9JHDOLtQSv55jblrF++Yo7A4tVKLXvAlxuPBV7vYlkhi0Xl24vL2b3mwQULJ/E0CQcd5fcbxLq/7J4knrGBZyJPcWF+HL5KazNegSqqT3fpKWjXzSJ6I663PNNpFuuzkVzQeOy7HfiCZMunKSBjwgB3JmaBy9SWb5wHbqBERUNtu0OCIDWw1INAtRujB5aDiHA3OGW1smFhxsnkVX8fKhBtkrGcbVc5KpCDN528Lp++m8fP3+5+ub1q785f9kfXhEn/OLhNQlHwpl0S4cH5ZaLpW+WLRpeM7XH8AiPEH8NrrnHz96ev169/n409B4Lakgw1FteLRmaqpyXGUdQzZdqHA1MgOuhyQr+jMZu+nWVLn5Csxe/64EXxp33eBton13yLHOvrU5OCmZtKMwD/gAPLARjrHY28Gy8pHZ6+G18YJwqfmhM63x1ud3izX/6iJYzGX+SS/zy/dWnCzLb61f+48d3F+vv/fLhItEX7LdffX4fP/z888XVVfv1p/wP7ShsqwV8PQuXamOW+tV6Fi7U9Sxqj1lak/h6Frcxh9uYYWN8Pj0+LsmHUAvnV/5qNfAvfHUmrFk7KGgwYG3fgjr2P/Xdn2jroPjWHJVn9MOjaM+Zwk8H9f1n8NteoTi9S78w+0z8czXr3+W0Cj7+8asz+9uvqudldf10moF1iCaNld03N5pQ0HetZKC1HLZouKxP0DZ1cH1HD2d9Pw8wh3MorZWRR9rOBxzsn/8/blNiwg=="

_CACHE: dict = {}
_LOCK = _threading.RLock()


def _locked(fn):
    @_functools.wraps(fn)
    def inner(*args, **kwargs):
        with _LOCK:
            return fn(*args, **kwargs)
    return inner


def _blob(text: str):
    return json.loads(zlib.decompress(_base64.b64decode(text)))


@_locked
def expected() -> dict:
    if "expected" not in _CACHE:
        _CACHE["expected"] = _blob(_EXPECTED_B64)
    return _CACHE["expected"]


@_locked
def meta() -> dict:
    if "meta" not in _CACHE:
        _CACHE["meta"] = _blob(_META_B64)
    return _CACHE["meta"]


@_locked
def extra_expected() -> dict:
    if "extra-expected" not in _CACHE:
        _CACHE["extra-expected"] = _blob(_EXTRA_EXPECTED_B64)
    return _CACHE["extra-expected"]


def strict_equal(a, b) -> bool:
    """Equality that also requires identical JSON types (1 is not 1.0, True is not 1)."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return list(a.keys()) == list(b.keys()) and all(strict_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(strict_equal(x, y) for x, y in zip(a, b))
    return a == b


# ------------------------------------------------------------------ reading deliverables

def parse_csv_bytes(data: bytes, columns: list[str]) -> dict | None:
    """A deliverable CSV: UTF-8, LF, header, rows, trailer. None when it is not one."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if text.startswith("\ufeff") or "\r" in text or not text.endswith("\n"):
        return None
    lines = text[:-1].split("\n")
    if len(lines) < 2:
        return None
    m = _re.fullmatch(r"#custody=([0-9a-f]{64}) rows=(\d+)", lines[-1])
    if not m:
        return None
    rows = list(_vcsv.reader(io.StringIO("\n".join(lines[:-1]) + "\n")))
    if not rows or rows[0] != columns:
        return None
    body = rows[1:]
    if any(len(r) != len(columns) for r in body):
        return None
    return {"rows": [dict(zip(columns, r)) for r in body], "digest": m.group(1), "count": int(m.group(2))}


def parse_json_bytes(data: bytes, keys: list[str]) -> dict | None:
    try:
        obj = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(obj, dict) or list(obj.keys()) != keys:
        return None
    return obj


def load_outputs(folder: Path) -> dict:
    got = {}
    for k, name in DELIVERABLES.items():
        p = folder / name
        try:
            data = p.read_bytes()
        except OSError:
            got[k] = None
            continue
        got[k] = parse_csv_bytes(data, COLUMNS[k]) if k in COLUMNS else parse_json_bytes(data, CHAIN_KEYS if k == "chain" else RECON_KEYS)
    return got


@_locked
def visible() -> dict:
    if "visible" not in _CACHE:
        _CACHE["visible"] = load_outputs(OUT)
    return _CACHE["visible"]


def _as_text(row: dict) -> dict:
    return {k: (str(v) if not isinstance(v, str) else v) for k, v in row.items() if not k.startswith("_")}


def plan_exact(got: dict, exp: dict) -> bool:
    if any(got[k] is None for k in DELIVERABLES):
        return False
    for key in COLUMNS:
        want = [_as_text(row) for row in exp[key]]
        if got[key]["rows"] != want or got[key]["count"] != len(want) or got[key]["digest"] != exp["digest"]:
            return False
    return strict_equal(got["chain"], exp["chain"]) and strict_equal(got["recon"], exp["recon"])


# ------------------------------------------------------------------ the delivered package
# Agent code only ever runs as `nobody`, one invocation at a time. Each invocation gets a fresh private directory as
# its cwd, HOME and TMPDIR; the package and feed trees it reads are root-owned and read-only; its outputs are copied
# into memory as soon as it exits; and every process and file left behind by `nobody` anywhere on the filesystem is
# removed before the next invocation, so no run can see state written by an earlier one.

def _safe_extract(zpath: Path, dest: Path) -> Path | None:
    try:
        with zipfile.ZipFile(zpath) as z:
            for info in z.infolist():
                name = info.filename
                if name.startswith("/") or ".." in Path(name).parts or "\\" in name:
                    return None
            z.extractall(dest)
    except (OSError, zipfile.BadZipFile, ValueError):
        return None
    for cand in [dest] + sorted(p for p in dest.iterdir() if p.is_dir()):
        if (cand / "pyproject.toml").is_file() and (cand / "src" / "restorekit" / "__init__.py").is_file():
            return cand
    return None


def _runner_uid() -> int:
    return _pwd.getpwnam("nobody").pw_uid


def _seal_tree(path: Path) -> None:
    for root, dirs, files in _os.walk(path):
        _os.chmod(root, 0o755)
        for f in files:
            _os.chmod(_os.path.join(root, f), 0o644)


def _kill_runner_processes(uid: int) -> None:
    for pid in _os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            status = Path("/proc", pid, "status").read_text()
        except OSError:
            continue
        uids = next((ln.split()[1:] for ln in status.splitlines() if ln.startswith("Uid:")), [])
        if str(uid) in uids:
            try:
                _os.kill(int(pid), _signal.SIGKILL)
            except OSError:
                pass


def _remove_runner_files(uid: int) -> None:
    pruned = {"/proc", "/sys", "/dev"}
    tops = ["/", "/dev/shm"]
    for top in tops:
        for root, dirs, files in _os.walk(top, topdown=True):
            if top == "/":
                dirs[:] = [d for d in dirs if _os.path.join(root, d) not in pruned]
            for name in files + dirs:
                full = _os.path.join(root, name)
                try:
                    st = _os.lstat(full)
                except OSError:
                    continue
                if st.st_uid != uid:
                    continue
                try:
                    if _stat.S_ISDIR(st.st_mode):
                        _shutil.rmtree(full, ignore_errors=True)
                    else:
                        _os.unlink(full)
                except OSError:
                    pass
            dirs[:] = [d for d in dirs if _os.path.exists(_os.path.join(root, d))]


@_locked
def _scrub() -> None:
    uid = _runner_uid()
    _kill_runner_processes(uid)
    _remove_runner_files(uid)


@_locked
def workdir() -> Path:
    if "work" not in _CACHE:
        w = Path(_tempfile.mkdtemp(prefix="rk-verify-"))
        _os.chmod(w, 0o755)
        _CACHE["work"] = w
    return _CACHE["work"]


@_locked
def sandbox(label: str) -> Path:
    box = workdir() / f"box-{label}"
    if box.exists():
        _shutil.rmtree(box)
    box.mkdir()
    _os.chmod(box, 0o777)
    return box


@_locked
def _run(cmd: list[str], box: Path, timeout: int, cwd: Path | None = None, env_extra: dict | None = None) -> tuple[int, str] | None:
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(box), "TMPDIR": str(box), "LANG": "C.UTF-8",
           "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1"}
    env.update(env_extra or {})
    with _tempfile.TemporaryFile() as log:
        try:
            proc = _subprocess.Popen(_SETPRIV + cmd, cwd=str(cwd or box), env=env, stdout=log, stderr=_subprocess.STDOUT,
                                     start_new_session=True)
        except OSError:
            return None
        try:
            proc.wait(timeout=timeout)
            timed_out = False
        except _subprocess.TimeoutExpired:
            timed_out = True
        try:
            _os.killpg(proc.pid, _signal.SIGKILL)
        except OSError:
            pass
        if timed_out:
            proc.wait()
            return None
        log.seek(0)
        return proc.returncode, log.read().decode("utf-8", "replace")


@_locked
def package_root() -> Path | None:
    if "pkg" not in _CACHE:
        root = None
        if PACKAGE.is_file():
            dest = workdir() / "pkg"
            dest.mkdir(exist_ok=True)
            root = _safe_extract(PACKAGE, dest)
            if root is not None:
                _seal_tree(dest)
        _CACHE["pkg"] = root
    return _CACHE["pkg"]


def _write_sealed_feed(seed: int, dest: Path) -> Path | None:
    try:
        _p, _w, _r, files = build_feed(seed, "eval")
        write_feed(files, dest, seed)
        _seal_tree(dest)
        return dest
    except Exception:
        if dest.exists():
            _shutil.rmtree(dest, ignore_errors=True)
        return None


@_locked
def eval_feed() -> Path | None:
    if "feed" not in _CACHE:
        _CACHE["feed"] = _write_sealed_feed(meta()["eval_seed"], workdir() / "feed")
    return _CACHE["feed"]


@_locked
def extra_feed(seed: int) -> Path | None:
    key = f"extra-feed-{seed}"
    if key not in _CACHE:
        _CACHE[key] = _write_sealed_feed(seed, workdir() / key)
    return _CACHE[key]


@_locked
def renamed_feed() -> Path | None:
    if "renamed" not in _CACHE:
        src = eval_feed()
        if src is None:
            _CACHE["renamed"] = None
        else:
            dst = workdir() / "feed_renamed"
            dst.mkdir(exist_ok=True)
            for i, p in enumerate(sorted(src.iterdir())):
                _shutil.copy(p, dst / f"item_{(i * 37) % 101:03d}.bin")
            _seal_tree(dst)
            _CACHE["renamed"] = dst
    return _CACHE["renamed"]


def _capture(folder: Path) -> dict | None:
    try:
        return {n: (folder / n).read_bytes() for n in DELIVERABLES.values()}
    except OSError:
        return None


@_locked
def run_package(label: str, feed: Path | None) -> dict | None:
    """Bytes of the five deliverables written by one isolated run of the package, or None."""
    key = "run-" + label
    if key not in _CACHE:
        pkg = package_root()
        got = None
        if pkg is not None and feed is not None:
            box = sandbox(label)
            out = box / "out"
            out.mkdir()
            _os.chmod(out, 0o777)
            res = _run(["python3", "-c", _RUNNER, str(pkg), "restore", "--feed", str(feed), "--out", str(out)], box, RUN_TIMEOUT)
            if res is not None and res[0] == 0:
                got = _capture(out)
            _scrub()
        _CACHE[key] = got
    return _CACHE[key]


@_locked
def run_package_with_canary() -> tuple[bool, dict | None]:
    """(canary set up, outputs) of the eval run repeated while /app/data holds a different, valid restore feed."""
    if "run-canary" not in _CACHE:
        ready, got = False, None
        corpus = Path("/app/data")
        if not corpus.exists() and eval_feed() is not None:
            try:
                if _write_sealed_feed(meta()["canary_seed"], corpus) is not None:
                    _os.chmod(corpus.parent, 0o755)
                    ready = True
                    got = run_package("canary", eval_feed())
            finally:
                _shutil.rmtree(corpus, ignore_errors=True)
        _CACHE["run-canary"] = (ready, got)
    return _CACHE["run-canary"]


def parse_outputs(raw: dict | None) -> dict:
    if raw is None:
        return {k: None for k in DELIVERABLES}
    return {k: (parse_csv_bytes(raw[name], COLUMNS[k]) if k in COLUMNS
                else parse_json_bytes(raw[name], CHAIN_KEYS if k == "chain" else RECON_KEYS))
            for k, name in DELIVERABLES.items()}


@_locked
def eval_outputs() -> dict:
    if "eval_out" not in _CACHE:
        _CACHE["eval_out"] = parse_outputs(run_package("eval", eval_feed()))
    return _CACHE["eval_out"]


@_locked
def extra_outputs(seed: int) -> dict:
    key = f"extra-out-{seed}"
    if key not in _CACHE:
        _CACHE[key] = parse_outputs(run_package(f"extra-{seed}", extra_feed(seed)))
    return _CACHE[key]


def deterministic_eval_bytes() -> dict | None:
    """The eval outputs when two isolated runs agree byte for byte, else None."""
    a = run_package("eval", eval_feed())
    if a is None or run_package("eval-again", eval_feed()) != a:
        return None
    return a


def _string_literals(root: Path) -> list[str]:
    out = []
    for p in sorted((root / "src").rglob("*.py")):
        try:
            tree = _ast.parse(p.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        docs = set()
        for node in _ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(body, list) and body and isinstance(body[0], _ast.Expr) and isinstance(body[0].value, _ast.Constant):
                docs.add(id(body[0].value))
        out += [n.value for n in _ast.walk(tree) if isinstance(n, _ast.Constant) and isinstance(n.value, str) and id(n) not in docs]
    return out


def _eval_cmp(fn) -> bool:
    try:
        return bool(fn())
    except Exception:
        return False


# ------------------------------------------------------------------ checks: the package

@criterion(description="package.zip holds an installable src-layout restorekit project that pip installs offline on Python 3.12")
def package_installs(workspace: Path) -> bool:
    try:
        pkg = package_root()
        if pkg is None:
            return False
        box = sandbox("install")
        src = box / "src-copy"
        _shutil.copytree(pkg, src)
        for root, dirs, files in _os.walk(src):
            _os.chmod(root, 0o777)
            for f in files:
                _os.chmod(_os.path.join(root, f), 0o666)
        script = ("python3 -m pip install --no-index --no-build-isolation --no-deps --no-cache-dir --target site ./src-copy"
                  " && PYTHONPATH=site python3 -c 'import restorekit'")
        with _LOCK:
            res = _run(["/bin/sh", "-c", script], box, 300)
            _scrub()
        return res is not None and res[0] == 0
    except Exception:
        return False


@criterion(description="The project test suite in package.zip is the shipped suite unchanged and passes with nothing skipped")
def package_shipped_tests_pass(workspace: Path) -> bool:
    try:
        pkg = package_root()
        if pkg is None:
            return False
        for rel, digest in meta()["shipped_tests"].items():
            p = pkg / rel
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
                return False
        with _LOCK:
            res = _run(["python3", "-m", "unittest", "discover", "-s", "tests", "-t", "."], sandbox("suite"), 300, cwd=pkg,
                       env_extra={"PYTHONPATH": str(pkg / "src")})
            _scrub()
        return res is not None and res[0] == 0 and "\nOK" in res[1] and "skipped" not in res[1]
    except Exception:
        return False


# ------------------------------------------------------------------ checks: the restore plan

@criterion(description="The five restore deliverables for the shipped feed are an exact match for the specification")
def visible_plan_exact(workspace: Path) -> bool:
    try:
        return plan_exact(visible(), expected()["visible"])
    except Exception:
        return False


@criterion(description="The package writes an exact restore plan for the first independently generated feed")
def eval_plan_exact(workspace: Path) -> bool:
    return _eval_cmp(lambda: plan_exact(eval_outputs(), expected()["eval"]))


@criterion(description="The package writes an exact restore plan for the second independently generated feed")
def extra_plan_7199369_exact(workspace: Path) -> bool:
    return _eval_cmp(lambda: plan_exact(extra_outputs(7199369), extra_expected()["7199369"]))


@criterion(description="The package writes an exact restore plan for the third independently generated feed")
def extra_plan_42133777_exact(workspace: Path) -> bool:
    return _eval_cmp(lambda: plan_exact(extra_outputs(42133777), extra_expected()["42133777"]))


@criterion(description="The package writes an exact restore plan for the fourth independently generated feed")
def extra_plan_121212121_exact(workspace: Path) -> bool:
    return _eval_cmp(lambda: plan_exact(extra_outputs(121212121), extra_expected()["121212121"]))


# ------------------------------------------------------------------ negative checks (True when the cheat happened)

@criterion(description="Fires when the package carries answers of the shipped feed or replays them on another feed")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat was seen; the negative weight subtracts.
    try:
        pkg = package_root()
        if pkg is None or not PACKAGE.is_file():
            return False
        lits = _string_literals(pkg)
        tokens = meta()["visible_answers"]
        if any(t in s for s in lits for t in tokens):
            return True
        ev = eval_outputs()
        vis = expected()["visible"]
        return ev["chain"] is not None and ev["chain"].get("custody_digest") == vis["digest"]
    except Exception:
        return False


@criterion(description="Fires when an otherwise deterministic package writes different output once only the feed file names change")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    # Inverted polarity: True means the outputs depend on file names. A nondeterministic package is left to
    # negative_nondeterministic_output so one defect is penalised once.
    try:
        a = deterministic_eval_bytes()
        if a is None:
            return False
        return run_package("renamed", renamed_feed()) != a
    except Exception:
        return False


@criterion(description="Fires when an otherwise deterministic package writes different output once /app/data holds another restore feed")
def negative_reads_training_corpus_at_runtime(workspace: Path) -> bool:
    # Inverted polarity: True means the package read /app/data instead of, or besides, the feed it was given.
    try:
        a = deterministic_eval_bytes()
        if a is None:
            return False
        ready, got = run_package_with_canary()
        return ready and got != a
    except Exception:
        return False


@criterion(description="Fires when two isolated runs of the package on the same feed differ")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # Inverted polarity: True means two identical runs disagree.
    try:
        a = run_package("eval", eval_feed())
        if a is None:
            return False
        return run_package("eval-again", eval_feed()) != a
    except Exception:
        return False


criteria.package_installs(weight=1)
criteria.package_shipped_tests_pass(weight=1)
criteria.visible_plan_exact(weight=5)
criteria.eval_plan_exact(weight=5)
criteria.extra_plan_7199369_exact(weight=5)
criteria.extra_plan_42133777_exact(weight=5)
criteria.extra_plan_121212121_exact(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_reads_training_corpus_at_runtime(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
