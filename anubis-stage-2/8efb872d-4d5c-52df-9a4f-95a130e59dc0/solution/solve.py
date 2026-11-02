#!/usr/bin/env python3
"""Edge cache placement optimizer, rebuilt against capacity standard revision 7.

    python3 build.py phase1 <DATA_DIR> <P1_DIR>
    python3 build.py phase2 <P1_DIR> <P2_DIR>
    python3 build.py phase3 <P1_DIR> <P2_DIR> <P3_DIR>
"""

from __future__ import annotations

import base64
import configparser
import csv
import hashlib
import io
import json
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

SECONDS_PER_DAY = 86400
WINDOW_RANK = {"hourly": 0, "daily": 1, "weekly": 2}
WINDOW_MULT = {"hourly": Fraction(1, 24), "daily": Fraction(1), "weekly": Fraction(7)}
LEVEL_DEFAULT = {"gzip": 6, "zstd": 3, "br": 4}
CODEC_NAME = {"gzip": "gzip", "zstd": "zstd", "zst": "zstd", "br": "br", "brotli": "br"}
UNIT_BYTES = {"": 1, "b": 1, "kib": 1 << 10, "mib": 1 << 20, "gib": 1 << 30, "tib": 1 << 40,
              "kb": 10 ** 3, "mb": 10 ** 6, "gb": 10 ** 9, "tb": 10 ** 12}
MEM_BYTES = {"": 1, "b": 1, "k": 1 << 10, "kb": 1 << 10, "kib": 1 << 10, "m": 1 << 20, "mb": 1 << 20,
             "mib": 1 << 20, "g": 1 << 30, "gb": 1 << 30, "gib": 1 << 30, "t": 1 << 40, "tb": 1 << 40, "tib": 1 << 40}
HUMAN_UNIT = {"K": 1 << 10, "M": 1 << 20, "G": 1 << 30, "T": 1 << 40}
CACHE_MOUNT = "/var/cache/edge"
SWEEPER = "cache-sweep"
SWEEP_CONF = "/etc/edgecache/edgecache.conf"
COUNTER_NAMES = ("edge_tx_bytes_total", "cache_served_bytes_total")

P1_NAMES = ("nodes.csv", "properties.csv", "policies.csv", "footprints.csv", "pending.json", "pops.json")
P2_NAMES = ("pop_rollup.csv", "class_rollup.csv", "shield_alloc.csv", "pin_plan.csv", "risk_rank.csv", "manifest.json")
P3_NAMES = ("projection.csv", "pop_outlook.csv", "spill_alloc.csv", "tickets.csv", "class_drift.csv", "manifest.json")
COLUMNS = {
    "nodes.csv": ["node_id", "pop", "class", "tier", "media", "usable_bytes", "base_used_bytes",
                  "post_cut_used_bytes", "prior_peak_kib", "sweep_interval", "ram_bytes"],
    "properties.csv": ["node_id", "property", "instance", "samples", "daily_bytes"],
    "policies.csv": ["node_id", "property", "versions", "refresh", "effective_refresh", "store_compressed",
                     "hot_raw", "codec", "ratio"],
    "footprints.csv": ["node_id", "property", "cycle_bytes", "hot_kib", "stale_kib", "peak_kib"],
    "pop_rollup.csv": ["pop", "nodes", "measured_pairs", "null_pairs", "compressed_pairs", "peak_mib", "usable_mib",
                       "headroom_mib", "pending_nodes", "shield_mib"],
    "class_rollup.csv": ["class", "nodes", "pops", "daily_mib", "mean_ratio", "peak_mib", "pending_pairs",
                         "shield_share_mib"],
    "shield_alloc.csv": ["node_id", "pop", "demand_kib", "granted_kib", "cumulative_kib", "state"],
    "pin_plan.csv": ["node_id", "property", "density", "hot_kib", "cumulative_kib", "pinned"],
    "risk_rank.csv": ["node_id", "pop", "headroom_kib", "daily_kib", "days_to_full", "full_date_local",
                      "pin_share", "pending", "rank"],
    "projection.csv": ["node_id", "pop", "class", "peak_now_kib", "peak_after_kib", "prior_gap_kib", "headroom_after_kib",
                       "days_after", "rank_before", "flag", "pop_share", "class_peak_share", "full_date_after",
                       "running_kib", "running_min_kib"],
    "pop_outlook.csv": ["pop", "headroom_mib_now", "headroom_mib_after", "at_risk_nodes", "shield_left_mib",
                        "spill_left_mib", "pending_applied", "mean_days_after", "worst_class"],
    "spill_alloc.csv": ["node_id", "pop", "deficit_kib", "daily_kib", "granted_kib", "remaining_kib", "state"],
    "tickets.csv": ["ticket", "pop", "node_id", "flag", "days_after", "rank_before"],
    "class_drift.csv": ["class", "peak_mib_now", "peak_mib_after", "drift_mib", "prior_gap_mib", "at_risk_nodes", "mean_pop_share",
                        "shield_share_after_mib"],
}


class UsageError(Exception):
    pass


class UpstreamError(Exception):
    pass


# ------------------------------------------------------------ arithmetic ----
def half_even(x) -> int:
    x = Fraction(x)
    q, r = divmod(x.numerator, x.denominator)
    if 2 * r > x.denominator or (2 * r == x.denominator and q % 2 == 1):
        q += 1
    return q


def decimal_text(x, places: int) -> str:
    n = half_even(Fraction(x) * 10 ** places)
    sign = "-" if n < 0 else ""
    digits = str(abs(n)).rjust(places + 1, "0")
    return sign + (digits if places == 0 else digits[:-places] + "." + digits[-places:])


def kib(n) -> int:
    return half_even(Fraction(n, 1024))


def ceil_fraction(a: Fraction) -> int:
    return -((-a.numerator) // a.denominator)


def whole_number(text: str) -> int:
    d = Decimal(str(text).strip())
    if d != d.to_integral_value():
        raise ValueError(f"non-integral counter value {text!r}")
    return int(d)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------- instants ---
def to_epoch(dt: datetime) -> int:
    return int(dt.timestamp())


def instant(value, local_offset_min=None) -> int:
    """Seconds since the epoch for any instant form the standard allows."""
    if isinstance(value, int):
        return value // 1000 if value >= 10 ** 12 else value
    if isinstance(value, datetime):
        return to_epoch(value if value.tzinfo else value.replace(tzinfo=timezone.utc))
    if isinstance(value, date):
        return to_epoch(datetime(value.year, value.month, value.day, tzinfo=timezone.utc))
    s = str(value).strip()
    m = re.fullmatch(r"(\d+)(?:\.(\d+))?", s)
    if m:
        if (m[2] or "").strip("0"):
            raise ValueError(f"sub-second instant {s!r}")
        n = int(m[1])
        return n // 1000 if len(m[1]) >= 13 else n
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return to_epoch(datetime(int(m[1]), int(m[2]), int(m[3]), tzinfo=timezone.utc))
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.0+)?(Z|[+-]\d{2}(?::?\d{2})?)?", s)
    if not m:
        raise ValueError(f"unrecognised instant {s!r}")
    naive = to_epoch(datetime.fromisoformat(f"{m[1]}T{m[2]}").replace(tzinfo=timezone.utc))
    zone = m[3]
    if zone is None:
        if local_offset_min is None:
            raise ValueError(f"wall time without a PoP: {s!r}")
        return naive - local_offset_min * 60
    if zone == "Z":
        return naive
    digits = zone[1:].replace(":", "")
    minutes = int(digits[:2]) * 60 + (int(digits[2:4]) if len(digits) > 2 else 0)
    return naive - (minutes if zone[0] == "+" else -minutes) * 60


def offset_minutes(text: str) -> int:
    s = str(text).strip().upper().removeprefix("UTC")
    m = re.fullmatch(r"([+-])(\d{2}):?(\d{2})?", s)
    if not m:
        raise ValueError(f"bad offset {text!r}")
    minutes = int(m[2]) * 60 + int(m[3] or 0)
    return minutes if m[1] == "+" else -minutes


def capacity_bytes(text) -> int:
    if isinstance(text, int):
        return text
    m = re.fullmatch(r"\s*([0-9.]+)\s*([A-Za-z]*)\s*", str(text))
    if not m:
        raise ValueError(f"bad capacity {text!r}")
    return int(Fraction(m[1]) * UNIT_BYTES[m[2].lower()])


def memory_bytes(text) -> int:
    m = re.fullmatch(r"\s*([0-9.]+)\s*([A-Za-z]*)\s*", str(text))
    if not m:
        raise ValueError(f"bad memory size {text!r}")
    return int(Fraction(m[1]) * MEM_BYTES[m[2].lower()])


def utc_text(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------ file access ---
def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise UpstreamError(str(path)) from exc


def need_dir(path: Path) -> Path:
    if not path.is_dir():
        raise UpstreamError(str(path))
    try:
        list(path.iterdir())
    except OSError as exc:
        raise UpstreamError(str(path)) from exc
    return path


def render_csv(name: str, rows) -> str:
    lines = [",".join(COLUMNS[name])]
    lines.extend(",".join("" if v is None else str(v) for v in row) for row in rows)
    return "\n".join(lines) + "\n"


def render_json(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def write_outputs(out_dir: Path, files: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        tmp = out_dir / (name + ".part")
        tmp.write_bytes(text.encode("utf-8"))
        tmp.replace(out_dir / name)


def coarser_window(a: str, b: str) -> str:
    return a if WINDOW_RANK[a] >= WINDOW_RANK[b] else b


def footprint(daily: int, window: str, versions: int, compressed: bool, hot_raw: bool, ratio: str):
    """(cycle, hot, stale, peak) bytes for one pair under the standard's footprint rule."""
    cycle = half_even(Fraction(daily) * WINDOW_MULT[window])
    generation = ceil_fraction(Fraction(cycle) / Fraction(ratio))
    hot = cycle if (not compressed or hot_raw) else generation
    stale = (versions - 1) * (generation if compressed else cycle)
    return cycle, hot, stale, hot + stale + cycle


# ======================================================================
# Phase 1
# ======================================================================
class Corpus:
    """The data directory, located by content rather than by its own name."""

    def __init__(self, root: Path):
        self.root = need_dir(root)
        self.files = sorted(p for p in root.rglob("*") if p.is_file())
        self.named = {p.name: p for p in self.files}
        cut_text = None
        for p in self.files:
            if p.suffix == ".md":
                m = re.search(r"The planning cut is (\S+?)\.\s", read_text(p))
                if m:
                    cut_text = m.group(1)
                    break
        if cut_text is None:
            raise UpstreamError(str(root / "edge_capacity_standard_r7.md"))
        self.cut = instant(cut_text)
        self.window_start = self.cut - 7 * SECONDS_PER_DAY

    def text(self, name: str) -> str:
        if name not in self.named:
            raise UpstreamError(str(self.root / name))
        return read_text(self.named[name])


class Optimizer:
    def __init__(self, corpus: Corpus):
        self.c = corpus
        self.cut = corpus.cut
        self.load_identity()
        self.load_pops()
        self.load_catalogue()
        self.load_nodes()
        self.load_policies()
        self.load_rates()
        self.load_disks()

    # ---- identity ----------------------------------------------------------
    def load_identity(self):
        entries = []
        current = None
        last = None
        for raw in self.c.text("nodedir_export.ldif").split("\n"):
            if raw.startswith(" ") and current is not None and last:
                current[last][-1] += raw[1:]
                continue
            if not raw.strip():
                if current:
                    entries.append(current)
                current, last = None, None
                continue
            if raw.startswith("version:"):
                continue
            key, sep, val = raw.partition(":")
            if not sep:
                continue
            val = base64.b64decode(val[1:].strip()).decode("utf-8") if val.startswith(":") else val.strip()
            if key == "dn":
                current = {}
            if current is None:
                continue
            current.setdefault(key, []).append(val)
            last = key
        if current:
            entries.append(current)
        names = {}
        for e in entries:
            cn = e.get("cn", [""])[0].lower()
            for attr in ("cn", "assetTag", "dNSName", "legacyName", "serialNumber"):
                for v in e.get(attr, []):
                    names[v.lower()] = cn
        alias_rev, rename_rev = {}, {}
        pattern = re.compile(r"^(\S+?)\s*[=:]\s*(\S+)\s*;\s*rev=(\d+)\s*$")
        for raw in self.c.text("ident_overrides.properties").split("\n"):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = pattern.match(line)
            if not m:
                continue
            key, val, rev = m[1], m[2].lower(), int(m[3])
            if key.startswith("rename."):
                old = key[len("rename."):].lower()
                if old not in rename_rev or rev > rename_rev[old][0]:
                    rename_rev[old] = (rev, val)
            elif key.startswith("alias."):
                ref = key.split(".", 2)[2].lower()
                if ref not in alias_rev or rev > alias_rev[ref][0]:
                    alias_rev[ref] = (rev, val)
        for ref, (_rev, val) in alias_rev.items():
            names[ref] = val
        self.names = names
        self.renames = {k: v for k, (_r, v) in rename_rev.items()}

    def node(self, ref, pop=None):
        if ref is None:
            return None
        ref = str(ref).strip()
        if pop:
            ref = f"{ref}@{pop}"
        name = self.names.get(ref.lower(), ref.lower())
        hops = 0
        while name in self.renames and self.renames[name] != name and hops < 64:
            name = self.renames[name]
            hops += 1
        return name if name in self.universe else None

    # ---- points of presence and placements ---------------------------------
    def load_pops(self):
        reg = tomllib.loads(self.c.text("pop_registry.toml"))
        self.pop_info = {}
        self.pop_alias = {}
        for code, p in reg.get("pops", {}).items():
            self.pop_info[code] = {
                "offset": offset_minutes(p["utc_offset"]),
                "shield": capacity_bytes(p["shield_pool"]),
                "quota": int(p["ticket_quota"]),
                "spill": capacity_bytes(p["spill_budget"]),
                "pin": int(str(p["ram_pin_pct"]).strip().rstrip("%")),
                "prod": str(p.get("scope", "")).lower() == "prod",
            }
            self.pop_alias[code.lower()] = code
            for a in p.get("aliases", []):
                self.pop_alias[a.lower()] = code
        latest = {}
        self.universe = set()
        for place in reg.get("placement", {}).values():
            nid = str(place["node"]).lower()
            self.universe.add(nid)
            if str(place.get("state", "")).lower() != "installed":
                continue
            t = instant(place["since"])
            if t <= self.cut and (nid not in latest or t >= latest[nid][0]):
                latest[nid] = (t, self.pop_alias[str(place["pop"]).lower()])
        self.pop_of = {n: v[1] for n, v in latest.items()}

    def local_offset(self, nid):
        pop = self.pop_of.get(nid)
        return self.pop_info[pop]["offset"] if pop else None

    # ---- properties, paths, classes ----------------------------------------
    def load_catalogue(self):
        cp = configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=",))
        cp.optionxform = str
        cp.read_string(self.c.text("pathmap.ini"))
        self.prop_alias = {}
        self.catalog = {}
        self.ctype = {}
        for k, v in cp.items("catalog"):
            self.catalog[k] = v.strip().strip('"')
            self.prop_alias[k.lower()] = k
        for k, v in cp.items("types"):
            self.ctype[k] = v.strip()
        for k, v in cp.items("aliases"):
            self.prop_alias[k.lower()] = v.strip()
        for raw in self.c.text("edgecache_2023.conf").split("\n"):
            m = re.match(r"#\s*renamed\s+(\S+)\s*->\s*(\S+)", raw)
            if m:
                self.prop_alias[m[1].lower()] = m[2]
        self.catalog_path = {v: k for k, v in self.catalog.items()}
        self.node_paths = {}
        self.ini_sections = [(sec, dict(cp.items(sec))) for sec in cp.sections()
                             if sec not in ("aliases", "catalog", "types")]

    def prop(self, ref):
        if ref is None:
            return None
        return self.prop_alias.get(str(ref).strip().lower())

    def prop_by_path(self, nid, path):
        path = path.strip().strip('"')
        return self.node_paths.get(nid, {}).get(path) or self.catalog_path.get(path)

    @staticmethod
    def latest(store, key, t, value, cut):
        if t <= cut and (key not in store or t >= store[key][0]):
            store[key] = (t, value)

    def load_nodes(self):
        for sec, items in self.ini_sections:
            nid = self.node(sec)
            if nid is None:
                continue
            paths = self.node_paths.setdefault(nid, {})
            for k, v in items.items():
                p = self.prop(k)
                if p:
                    paths[v.strip().strip('"')] = p
        cut = self.cut
        status = {}
        for row in csv.DictReader(io.StringIO(self.c.text("asset_status_hist.csv"))):
            nid = self.node(row["node_ref"])
            if nid is not None:
                self.latest(status, nid, instant(row["recorded_at"]), (row["status"].strip().lower(), row["mem"]), cut)
        self.memory = {n: memory_bytes(v[1][1]) for n, v in status.items()}
        klass = {}
        insert = re.compile(r"VALUES \('([^']*)', '([^']*)', '([^']*)', (\d+), '[^']*'\);")
        for raw in self.c.text("hwclass_ledger.sql").split("\n"):
            m = insert.search(raw)
            if not m or m[4] != "0":
                continue
            nid = self.node(m[1])
            if nid is not None:
                self.latest(klass, nid, instant(m[3]), m[2].strip().lower(), cut)
        self.klass = {n: v[1] for n, v in klass.items()}
        root = ET.fromstring(self.c.text("tier_assign.xml"))
        class_tier = {e.get("name").lower(): e.get("tier") for e in root.findall("class")}
        tier = {}
        for e in root.findall("node"):
            nid = self.node(e.get("ref"))
            if nid is None:
                continue
            for t_el in e.findall("tier"):
                self.latest(tier, nid, instant(t_el.get("since")), t_el.text.strip().lower(), cut)
        retired = set()
        for block in re.findall(r"BEGIN:VEVENT\n(.*?)END:VEVENT", self.c.text("decom_cal.ics"), re.S):
            fields = {}
            start = None
            for raw in block.split("\n"):
                if raw.startswith("DTSTART"):
                    start = self.ics_start(raw)
                elif ":" in raw:
                    k, _s, v = raw.partition(":")
                    fields[k] = v.strip()
            if fields.get("STATUS", "").upper() != "CONFIRMED" or start is None or start > cut:
                continue
            nid = self.node(fields.get("X-NODE"))
            if nid:
                retired.add(nid)
        self.templates = {}
        current = None
        depth = 0
        for raw in self.c.text("edgecache_main.conf").split("\n"):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            m = re.match(r"^class\s+(\S+)\s*\{$", line)
            if m and depth == 0:
                current = m[1].lower()
                depth = 1
                continue
            m = re.match(r"^location\s+(\S+)\s*\{$", line)
            if m and current and depth == 1:
                p = self.catalog_path.get(m[1])
                if p:
                    self.templates.setdefault(current, []).append(p)
            depth += line.count("{") - line.count("}")
            if depth <= 0:
                current, depth = None, 0
        change = {}
        for row in csv.DictReader(io.StringIO(self.c.text("prop_changes.csv"))):
            nid = self.node(row["node_ref"])
            p = self.prop(row["property"])
            act = row["action"].strip().lower()
            if nid is None or p is None or act == "confirm":
                continue
            self.latest(change, (nid, p), instant(row["effective"]), act, cut)
        self.props = {nid: set(self.templates.get(cls, [])) for nid, cls in self.klass.items()}
        for (nid, p), (_t, act) in change.items():
            if nid in self.props:
                if act == "add":
                    self.props[nid].add(p)
                elif act == "remove":
                    self.props[nid].discard(p)
        watched = self.production_targets()
        self.scope = []
        self.tier = {}
        for nid in sorted(self.universe):
            st = status.get(nid, (0, ("", "")))[1][0]
            pop = self.pop_of.get(nid)
            cls = self.klass.get(nid)
            if st not in ("active", "serving", "maintenance") or pop is None or not self.pop_info[pop]["prod"]:
                continue
            if nid in retired or cls is None or cls == "retired":
                continue
            if not any((nid, p) in watched for p in self.props.get(nid, ())):
                continue
            tv = tier[nid][1] if nid in tier else class_tier.get(cls)
            if tv == "x":
                continue
            self.tier[nid] = tv
            self.scope.append(nid)
        self.in_scope = set(self.scope)
        self.pairs = sorted((n, p) for n in self.scope for p in self.props[n])

    def production_targets(self):
        """(node, property) pairs with a registered production exporter instance."""
        self.mirrors = {m["mirror_instance"] for m in json.loads(self.c.text("mirror_twins.json"))}
        self.labs = {row["instance"].strip()
                     for row in csv.DictReader(io.StringIO(self.c.text("labnodes.tsv")), delimiter="\t")}
        self.registered = {}
        for t in tomllib.loads(self.c.text("scrape_targets.toml")).get("targets", {}).values():
            key = (self.node(t["node"]), self.prop(t["property"]))
            self.registered.setdefault(key, []).append(t)
        return {key for key, items in self.registered.items()
                if any(t["instance"] not in self.mirrors and t["instance"] not in self.labs for t in items)}

    @staticmethod
    def ics_start(line):
        head, _s, value = line.partition(":")
        value = value.strip()
        if "VALUE=DATE" in head:
            return to_epoch(datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc))
        local = to_epoch(datetime.strptime(value.rstrip("Z"), "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc))
        m = re.search(r"TZID=Etc/GMT([+-])(\d+)", head)
        if m:
            # IANA Etc/GMT-N is N hours east of UTC
            east = int(m[2]) if m[1] == "-" else -int(m[2])
            return local - east * 3600
        return local

    # ---- cache policy ----------------------------------------------------------
    @staticmethod
    def directive(layer, text):
        parts = text.rstrip(";").split()
        if len(parts) < 2:
            return
        word, arg = parts[0], parts[1]
        if word == "versions":
            layer["versions"] = int(arg)
        elif word == "refresh" and arg in WINDOW_RANK:
            layer["refresh"] = arg
        elif word == "store-compressed":
            layer["store_compressed"] = arg == "on"
        elif word == "hot-raw":
            layer["hot_raw"] = arg == "on"
        elif word == "codec":
            layer["codec_name"] = CODEC_NAME[arg.lower()]
            layer.pop("level", None)
        elif word == "codec-level":
            layer["level"] = int(arg)

    @staticmethod
    def apply(state, layer):
        for k in ("versions", "refresh", "store_compressed", "hot_raw"):
            if k in layer:
                state[k] = layer[k]
        if "codec_name" in layer:
            state["codec_name"] = layer["codec_name"]
            state["level"] = layer.get("level", LEVEL_DEFAULT[layer["codec_name"]])
        elif "level" in layer:
            state["level"] = layer["level"]

    def parse_config(self, text):
        """(global layer, class layers, node layers, includes) of one config file."""
        glob, classes, nodes, includes = {}, {}, [], []
        stack = []
        layer = None
        for raw in text.split("\n"):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            m = re.match(r"^(class|node|location)\s+(\S+)\s*\{$", line)
            if m:
                stack.append((m[1], m[2]))
                if m[1] == "location":
                    layer = {}
                continue
            if line == "}":
                if not stack:
                    continue
                kind, name = stack.pop()
                if kind == "location" and stack:
                    owner_kind, owner = stack[-1]
                    if owner_kind == "class":
                        p = self.catalog_path.get(name)
                        if p:
                            classes[(owner.lower(), p)] = layer
                    else:
                        nodes.append((owner, name, layer))
                    layer = None
                continue
            if line.startswith("include "):
                includes.append(line.split(None, 1)[1].rstrip(";").strip())
                continue
            if layer is not None:
                self.directive(layer, line)
            elif not stack:
                self.directive(glob, line)
        return glob, classes, nodes, includes

    def load_policies(self):
        cut = self.cut
        glob, classes, node_main, includes = self.parse_config(self.c.text("edgecache_main.conf"))
        node_layers = {}

        def add_node_layers(blocks):
            for ref, path, layer in blocks:
                nid = self.node(ref)
                if nid is None or nid not in self.in_scope:
                    continue
                p = self.prop_by_path(nid, path)
                if p is None or p not in self.props[nid]:
                    continue
                node_layers.setdefault((nid, p), []).append(layer)

        add_node_layers(node_main)
        for inc in includes:
            add_node_layers(self.parse_config(self.c.text(Path(inc).name))[2])
        drafts = {}
        for raw in self.c.text("tuning_drafts.jsonl").split("\n"):
            if raw.strip():
                rec = json.loads(raw)
                drafts[rec["proposal"]] = rec["value"]
        decisions = {}
        for raw in self.c.text("cab_minutes.md").split("\n"):
            cells = [c.strip() for c in raw.strip().strip("|").split("|")]
            if len(cells) < 3 or not re.fullmatch(r"CR-\d+", cells[1]):
                continue
            word = cells[2].lower()
            verdict = "approved" if word.startswith("approve") else "rejected" if word.startswith("reject") else None
            if verdict is not None:
                self.latest(decisions, cells[1], instant(cells[0]), verdict, cut)
        self.amendments = []
        for raw in self.c.text("cr_export.jsonl").split("\n"):
            if not raw.strip():
                continue
            rec = json.loads(raw)
            status = decisions.get(rec["change"], (None, str(rec["status"]).lower()))[1]
            if status != "approved":
                continue
            field = rec["field"]
            value = self.normalise(field, drafts.get(rec["value_ref"]) if "value_ref" in rec else rec.get("value"))
            target = self.node(rec["target"]) if rec["scope"] == "node" else str(rec["target"]).lower()
            self.amendments.append({"id": rec["change"], "scope": rec["scope"], "target": target,
                                    "property": self.prop(rec["property"]), "field": field, "value": value,
                                    "eff": instant(rec["effective"])})
        self.amendments.sort(key=lambda a: (a["eff"], a["id"]))
        self.sweep = self.sweep_intervals()
        ratios = self.ratios()
        self.policy = {}
        for nid, p in self.pairs:
            state = {}
            self.apply(state, glob)
            cls = self.klass[nid]
            if (cls, p) in classes:
                self.apply(state, classes[(cls, p)])
            for a in self.amendments:
                if a["eff"] <= cut and a["scope"] == "class" and a["target"] == cls and a["property"] == p:
                    self.apply(state, self.amendment_layer(a))
            for layer in node_layers.get((nid, p), []):
                self.apply(state, layer)
            for a in self.amendments:
                if a["eff"] <= cut and a["scope"] == "node" and a["target"] == nid and a["property"] == p:
                    self.apply(state, self.amendment_layer(a))
            state["codec"] = f"{state['codec_name']}:{state['level']}"
            state["ratio"] = ratios[(self.ctype[p], state["codec"])]
            state["effective"] = coarser_window(state["refresh"], self.sweep[nid])
            self.policy[(nid, p)] = state
        self.pending = []
        for a in self.amendments:
            if a["eff"] <= cut:
                continue
            if a["scope"] == "node":
                if a["target"] not in self.in_scope or a["property"] not in self.props[a["target"]]:
                    continue
            elif not any(self.klass[n] == a["target"] and a["property"] in self.props[n] for n in self.scope):
                continue
            self.pending.append(a)

    @staticmethod
    def normalise(field, value):
        if field == "versions":
            return int(value)
        if field in ("store_compressed", "hot_raw"):
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in ("on", "true", "yes", "1")
        return str(value).strip()

    @staticmethod
    def amendment_layer(a):
        if a["field"] == "codec":
            name, level = a["value"].split(":")
            return {"codec_name": CODEC_NAME[name], "level": int(level)}
        return {a["field"]: a["value"]}

    def sweep_intervals(self):
        best = {}
        for raw in self.c.text("sweeper.crontab").split("\n"):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            nid = self.node(parts[0])
            if nid is None:
                continue
            if parts[1].startswith("@"):
                sched, rest = parts[1:2], parts[2:]
            else:
                sched, rest = parts[1:6], parts[6:]
            cmd = rest[1:]
            if not cmd or not cmd[0].endswith("/" + SWEEPER) or "--dry-run" in cmd or SWEEP_CONF not in cmd:
                continue
            if sched[0].startswith("@"):
                kind = {"@hourly": "hourly", "@daily": "daily", "@midnight": "daily", "@weekly": "weekly"}.get(sched[0])
                if kind is None:
                    continue
            else:
                _minute, hour, _dom, _mon, dow = sched
                kind = "hourly" if hour in ("*", "*/1") else "weekly" if dow != "*" else "daily"
            if nid not in best or WINDOW_RANK[kind] < WINDOW_RANK[best[nid]]:
                best[nid] = kind
        return {n: best.get(n, "daily") for n in self.scope}

    def ratios(self):
        acc = {}
        for row in csv.DictReader(io.StringIO(self.c.text("codec_bench.csv"))):
            if row["corpus"].strip().lower() != "edge24" or row["status"].strip().lower() != "ok":
                continue
            name = CODEC_NAME[row["codec"].strip().lower()]
            level = int(row["level"].strip().lower().lstrip("q"))
            acc.setdefault((row["content_type"].strip().lower(), f"{name}:{level}"), []).append(
                Fraction(int(row["in_bytes"]), int(row["out_bytes"])))
        return {k: decimal_text(sum(v, Fraction(0)) / len(v), 2) for k, v in acc.items()}

    # ---- counters ----------------------------------------------------------------
    def load_rates(self):
        unit = {}
        registered = {}
        for key, items in self.registered.items():
            for t in items:
                inst = t["instance"]
                unit[inst] = 1024 if str(t.get("counter_unit", "bytes")).lower() == "kib" else 1
                registered.setdefault(key, []).append(inst)
        mirrors, labs = self.mirrors, self.labs
        staging = {(s["job"], s["instance"]) for s in tomllib.loads(self.c.text("stg_jobs.toml")).get("scrape", {}).values()}
        excluded = mirrors | labs
        injected = set()
        for raw in self.c.text("replay_inject_q3.prom").split("\n"):
            m = PROM_LINE.match(raw.strip())
            if not m:
                continue
            labels = dict(LABEL.findall(m[2]))
            injected.add((self.node(labels.get("node"), labels.get("pop")), self.prop(labels.get("prop")),
                          labels.get("instance"), instant(m[4]), whole_number(m[3])))
        self.instance = {}
        for key in self.pairs:
            insts = [i for i in registered.get(key, []) if i not in excluded]
            self.instance[key] = insts[0] if insts else None
        readings = {}
        for path in self.c.files:
            for rec in counter_readings(path):
                nid = self.node(rec["node"], rec.get("pop"))
                if nid is None or nid not in self.in_scope:
                    continue
                p = self.prop_by_path(nid, rec["path"]) if rec.get("path") is not None else self.prop(rec["prop"])
                if p is None or p not in self.props[nid]:
                    continue
                inst, job = rec["instance"], rec["job"]
                if inst in excluded or (job, inst) in staging:
                    continue
                ts = instant(rec["ts"], self.local_offset(nid))
                raw_value = whole_number(rec["value"])
                if (nid, p, inst, ts, raw_value) in injected:
                    continue
                if ts < self.c.window_start or ts > self.cut:
                    continue
                readings.setdefault((nid, p), {})[(inst, job, ts)] = raw_value * unit.get(inst, 1)
        self.rate = {}
        for key in self.pairs:
            pts = sorted((ts, v) for (_i, _j, ts), v in readings.get(key, {}).items())
            if len(pts) < 2:
                self.rate[key] = (len(pts), None)
                continue
            rise = sum(b - a if b >= a else b for (_t0, a), (_t1, b) in zip(pts, pts[1:]))
            span = pts[-1][0] - pts[0][0]
            self.rate[key] = (len(pts), half_even(Fraction(rise * SECONDS_PER_DAY, span)) if span > 0 else None)

    # ---- disks -------------------------------------------------------------------
    def load_disks(self):
        cut = self.cut
        geometry = {}
        for row in csv.DictReader(io.StringIO(self.c.text("blkdev_audit.tsv")), delimiter="\t"):
            if row["mount"] != CACHE_MOUNT:
                continue
            nid = self.node(row["node"])
            if nid is not None:
                self.latest(geometry, nid, instant(row["audited"]), row, cut)
        self.disk = {}
        for nid in self.scope:
            row = geometry[nid][1]
            bs_text = row["bsize"].strip().lower()
            bs = int(bs_text[:-1]) * 1024 if bs_text.endswith("k") else int(bs_text)
            blocks = int(row["blocks"])
            media = row["media"].strip().lower()
            res = row["reserve"].strip()
            if media == "sata":
                reserved = 0
            elif res.startswith("rb="):
                reserved = int(res[3:])
            elif res.startswith("op="):
                reserved = blocks * int(res[3:]) // 100
            else:
                reserved = blocks * 7 // 100
            self.disk[nid] = (media, (blocks - reserved) * bs)
        before, after = {}, {}
        for path in self.c.files:
            if path.suffix != ".log":
                continue
            text = read_text(path)
            if "=== node=" not in text:
                continue
            for nid, t, used in usage_snapshots(text, self.node):
                if t <= cut:
                    if nid not in before or t >= before[nid][0]:
                        before[nid] = (t, used)
                elif used is not None and (nid not in after or t < after[nid][0]):
                    after[nid] = (t, used)
        self.base = {n: before[n][1] for n in self.scope}
        self.post_cut = {n: after[n][1] if n in after else None for n in self.scope}
        prior = {}
        for row in csv.DictReader(io.StringIO(self.c.text("optplan_prev.csv"))):
            if row["run_id"].strip() != "q2-final":
                continue
            nid = self.node(row["node_ref"])
            if nid is None:
                continue
            number, _sp, suffix = row["peak_kib"].strip().partition(" ")
            prior[nid] = prior.get(nid, 0) + int(number) * (1024 if suffix.strip().lower() == "mib" else 1)
        self.prior = prior

    # ---- output -------------------------------------------------------------------
    def outputs(self) -> dict:
        nodes, props, pols, fps = [], [], [], []
        for nid in self.scope:
            media, usable = self.disk[nid]
            nodes.append([nid, self.pop_of[nid], self.klass[nid], self.tier[nid], media, usable, self.base[nid],
                          self.post_cut[nid], self.prior.get(nid), self.sweep[nid], self.memory[nid]])
        for key in self.pairs:
            nid, p = key
            n, daily = self.rate[key]
            props.append([nid, p, self.instance[key], n, daily])
            pol = self.policy[key]
            pols.append([nid, p, pol["versions"], pol["refresh"], pol["effective"], int(pol["store_compressed"]),
                         int(pol["hot_raw"]), pol["codec"], pol["ratio"]])
            if daily is None:
                fps.append([nid, p, None, None, None, None])
            else:
                cycle, hot, stale, peak = footprint(daily, pol["effective"], pol["versions"], pol["store_compressed"],
                                                    pol["hot_raw"], pol["ratio"])
                fps.append([nid, p, cycle, kib(hot), kib(stale), kib(peak)])
        pend = [{"id": a["id"], "scope": a["scope"],
                 "node_id": a["target"] if a["scope"] == "node" else None,
                 "class": a["target"] if a["scope"] == "class" else None,
                 "property": a["property"], "field": a["field"], "value": a["value"],
                 "effective_utc": utc_text(a["eff"])} for a in self.pending]
        pops = []
        for code in sorted(c for c, info in self.pop_info.items() if info["prod"]):
            info = self.pop_info[code]
            members = [n for n in self.scope if self.pop_of[n] == code]
            pops.append({"pop": code, "utc_offset_minutes": info["offset"], "shield_pool_kib": kib(info["shield"]),
                         "ticket_quota": info["quota"], "spill_budget_kib": kib(info["spill"]),
                         "ram_pin_pct": info["pin"], "nodes": len(members),
                         "pin_budget_kib": sum(self.memory[n] // 1024 * info["pin"] // 100 for n in members)})
        return {"nodes.csv": render_csv("nodes.csv", nodes), "properties.csv": render_csv("properties.csv", props),
                "policies.csv": render_csv("policies.csv", pols), "footprints.csv": render_csv("footprints.csv", fps),
                "pending.json": render_json({"freeze_utc": utc_text(self.cut), "amendments": pend}),
                "pops.json": render_json({"pops": pops})}


PROM_LINE = re.compile(r"^([A-Za-z_:][\w:]*)\{(.*)\}\s+(\S+)\s+(\S+)$")
LABEL = re.compile(r'(\w+)="([^"]*)"')


def counter_readings(path: Path):
    """Yield counter readings from any export format, recognised by content."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    head = text[:4096]
    if path.suffix == ".prom" and any(n + "{" in text for n in COUNTER_NAMES):
        for raw in text.split("\n"):
            m = PROM_LINE.match(raw.strip())
            if m and m[1] in COUNTER_NAMES:
                lab = dict(LABEL.findall(m[2]))
                yield {"node": lab.get("node"), "prop": lab.get("prop"), "instance": lab.get("instance"),
                       "job": lab.get("job"), "pop": lab.get("pop"), "value": m[3], "ts": m[4]}
    elif '"metric":"edge_tx_bytes_total"' in head:
        for raw in text.split("\n"):
            if raw.strip():
                r = json.loads(raw)
                lab = r["labels"]
                yield {"node": lab.get("node"), "prop": lab.get("prop"), "instance": lab.get("instance"),
                       "job": lab.get("job"), "pop": lab.get("pop"), "value": r["value"], "ts": r["ts"]}
    elif '"m":"edge_tx_bytes_total"' in head:
        for raw in text.split("\n"):
            if raw.strip():
                r = json.loads(raw)
                yield {"node": r.get("node"), "prop": r.get("prop"), "instance": r.get("inst"), "job": r.get("job"),
                       "pop": r.get("pop"), "value": str(r["v"]), "ts": r["t"]}
    elif head.startswith("node,property,instance,job,pop,timestamp,value"):
        for r in csv.DictReader(io.StringIO(text)):
            yield {"node": r["node"], "prop": r["property"], "instance": r["instance"], "job": r["job"],
                   "pop": r["pop"] or None, "value": r["value"], "ts": r["timestamp"]}
    elif head.startswith("ts\tnode\tpop\tpath"):
        for r in csv.DictReader(io.StringIO(text), delimiter="\t"):
            yield {"node": r["node"], "path": r["path"], "prop": None, "instance": r["instance"], "job": r["job"],
                   "pop": r["pop"] or None, "value": r["value"], "ts": r["ts"]}
    elif " sample node=" in head:
        for raw in text.split("\n"):
            m = re.match(r"^(.*?) sample (.*)$", raw)
            if not m:
                continue
            kv = dict(tok.split("=", 1) for tok in m[2].split())
            yield {"node": kv.get("node"), "prop": kv.get("prop"), "instance": kv.get("inst"), "job": kv.get("job"),
                   "pop": kv.get("pop"), "value": kv["v"], "ts": m[1]}
    elif "<samples" in head:
        for el in ET.fromstring(text).iter("s"):
            yield {"node": el.get("n"), "prop": el.get("p"), "instance": el.get("i"), "job": el.get("j"),
                   "pop": el.get("pop"), "value": el.get("v"), "ts": el.get("t")}
    elif "INSERT INTO edge_samples" in text[:20000]:
        pat = re.compile(r"VALUES \('([^']*)', '([^']*)', '([^']*)', '([^']*)', (NULL|'[^']*'), '([^']*)', ([^)]*)\);")
        for raw in text.split("\n"):
            m = pat.search(raw)
            if m:
                yield {"node": m[1], "prop": m[2], "instance": m[3], "job": m[4],
                       "pop": None if m[5] == "NULL" else m[5].strip("'"), "value": m[7], "ts": m[6]}
    elif "<table>" in head and "<th>node</th>" in head:
        pat = re.compile(r"<tr>" + r"<td>(.*?)</td>" * 7 + r"</tr>")
        for raw in text.split("\n"):
            m = pat.search(raw)
            if m:
                yield {"node": m[1], "prop": m[2], "instance": m[3], "job": m[4], "pop": m[5] or None,
                       "value": m[7], "ts": m[6]}


def usage_snapshots(text, resolve):
    """Yield (node, instant, cache mount used bytes or None) per usage snapshot."""
    for block in re.split(r"^=== ", text, flags=re.M)[1:]:
        lines = block.split("\n")
        m = re.match(r"node=(\S+) at=(.+?) cmd=df -([kh])\s*$", lines[0])
        if not m:
            continue
        nid = resolve(m[1])
        if nid is None:
            continue
        used = None
        for ln in lines[2:]:
            parts = ln.split()
            if len(parts) >= 6 and parts[-1] == CACHE_MOUNT:
                if m[3] == "k":
                    used = int(parts[2]) * 1024
                else:
                    hm = re.fullmatch(r"([0-9.]+)([KMGT])", parts[2])
                    used = int(Fraction(hm[1]) * HUMAN_UNIT[hm[2]])
        yield nid, instant(m[2]), used


def phase1(data_dir: Path, out_dir: Path) -> None:
    files = Optimizer(Corpus(data_dir)).outputs()
    write_outputs(out_dir, files)


# ======================================================================
# Phases 2 and 3 work from the upstream directories only
# ======================================================================
def load_csv(d: Path, name: str):
    reader = csv.DictReader(io.StringIO(read_text(d / name)))
    if reader.fieldnames != COLUMNS[name]:
        raise UpstreamError(str(d / name))
    return list(reader)


def load_json(d: Path, name: str):
    try:
        return json.loads(read_text(d / name))
    except ValueError as exc:
        raise UpstreamError(str(d / name)) from exc


def opt_int(v):
    return None if v == "" else int(v)


def read_upstream(d: Path, names) -> dict:
    need_dir(d)
    raw = {}
    for n in names:
        if not (d / n).is_file():
            raise UpstreamError(str(d / n))
        try:
            raw[n] = (d / n).read_bytes()
        except OSError as exc:
            raise UpstreamError(str(d / n)) from exc
    return raw


class Stage1:
    """The six phase 1 files and the per-node figures phases 2 and 3 share."""

    def __init__(self, d: Path):
        self.raw = read_upstream(d, P1_NAMES)
        self.nodes = load_csv(d, "nodes.csv")
        pending = load_json(d, "pending.json")
        self.pops = load_json(d, "pops.json")["pops"]
        self.amendments = pending["amendments"]
        self.cut = instant(pending["freeze_utc"])
        self.pop = {p["pop"]: p for p in self.pops}
        self.pair = {}
        for kind, name in (("svc", "properties.csv"), ("pol", "policies.csv"), ("fp", "footprints.csv")):
            for r in load_csv(d, name):
                self.pair.setdefault((r["node_id"], r["property"]), {})[kind] = r
        self.props = {}
        for nid, p in sorted(self.pair):
            self.props.setdefault(nid, []).append(p)
        self.hits = {}
        for a in self.amendments:
            for n in self.nodes:
                nid = n["node_id"]
                if a["scope"] == "node" and a["node_id"] != nid:
                    continue
                if a["scope"] == "class" and a["class"] != n["class"]:
                    continue
                if (nid, a["property"]) in self.pair:
                    self.hits.setdefault((nid, a["property"]), []).append(a)
        self.calc = {}
        for n in self.nodes:
            nid = n["node_id"]
            peak = daily = measured = 0
            for p in self.props.get(nid, []):
                row = self.pair[(nid, p)]
                if row["fp"]["peak_kib"] != "":
                    peak += int(row["fp"]["peak_kib"])
                if row["svc"]["daily_bytes"] != "":
                    daily += int(row["svc"]["daily_bytes"])
                    measured += 1
            usable = kib(int(n["usable_bytes"]))
            base = kib(int(n["base_used_bytes"]))
            self.calc[nid] = {"usable": usable, "base": base, "peak": peak, "measured": measured,
                              "ram": kib(int(n["ram_bytes"])), "daily": kib(daily) if measured else None,
                              "headroom": usable - base - peak,
                              "pending": any((nid, p) in self.hits for p in self.props.get(nid, []))}


def days_of(headroom, daily):
    if daily is None:
        return None
    if daily == 0:
        return "never"
    return Fraction(0) if headroom <= 0 else Fraction(headroom, daily)


def days_text(d):
    if d is None:
        return ""
    return "never" if d == "never" else decimal_text(d, 2)


def days_sort(d):
    if isinstance(d, Fraction):
        return (0, d)
    return (1, Fraction(0)) if d == "never" else (2, Fraction(0))


def local_day(cut, d, offset):
    moment = Fraction(cut) + d * SECONDS_PER_DAY + offset * 60
    whole = moment.numerator // moment.denominator
    return (datetime(1970, 1, 1) + timedelta(days=whole // SECONDS_PER_DAY)).strftime("%Y-%m-%d")


def plan_pins(s1: Stage1):
    """Greedy first-fit RAM pin plan: (rows, pinned KiB per node)."""
    rows = []
    pinned = {}
    for n in s1.nodes:
        nid = n["node_id"]
        budget = s1.calc[nid]["ram"] * int(s1.pop[n["pop"]]["ram_pin_pct"]) // 100
        free, ranked = [], []
        for p in s1.props.get(nid, []):
            row = s1.pair[(nid, p)]
            if row["svc"]["daily_bytes"] == "" or row["pol"]["effective_refresh"] == "hourly" or (nid, p) in s1.hits:
                continue
            hot = int(row["fp"]["hot_kib"])
            if hot == 0:
                free.append((p, hot, None))
            else:
                ranked.append((p, hot, Fraction(int(row["svc"]["daily_bytes"]), hot)))
        ranked.sort(key=lambda c: (-c[2], c[0]))
        used = 0
        for p, hot, dens in sorted(free) + ranked:
            fits = used + hot <= budget
            if fits:
                used += hot
            rows.append([nid, p, None if dens is None else decimal_text(dens, 2), hot, used, int(fits)])
        pinned[nid] = used
    return rows, pinned


def phase2(p1_dir: Path, out_dir: Path) -> None:
    s1 = Stage1(p1_dir)
    files = {}
    rows = []
    for pop in s1.pops:
        code = pop["pop"]
        members = [n["node_id"] for n in s1.nodes if n["pop"] == code]
        pairs = [s1.pair[(m, p)] for m in members for p in s1.props.get(m, [])]
        rows.append([code, len(members),
                     sum(p["svc"]["daily_bytes"] != "" for p in pairs),
                     sum(p["svc"]["daily_bytes"] == "" for p in pairs),
                     sum(p["pol"]["store_compressed"] == "1" for p in pairs),
                     kib(sum(int(p["fp"]["peak_kib"]) for p in pairs if p["fp"]["peak_kib"] != "")),
                     kib(sum(s1.calc[m]["usable"] for m in members)),
                     kib(sum(s1.calc[m]["headroom"] for m in members)),
                     sum(s1.calc[m]["pending"] for m in members),
                     kib(pop["shield_pool_kib"])])
    files["pop_rollup.csv"] = render_csv("pop_rollup.csv", rows)

    pop_total, split = {}, {}
    for n in s1.nodes:
        pk = s1.calc[n["node_id"]]["peak"]
        pop_total[n["pop"]] = pop_total.get(n["pop"], 0) + pk
        split[(n["class"], n["pop"])] = split.get((n["class"], n["pop"]), 0) + pk
    rows = []
    for cls in sorted({n["class"] for n in s1.nodes}):
        members = [n for n in s1.nodes if n["class"] == cls]
        pairs = [s1.pair[(n["node_id"], p)] for n in members for p in s1.props.get(n["node_id"], [])]
        measured = [int(p["svc"]["daily_bytes"]) for p in pairs if p["svc"]["daily_bytes"] != ""]
        comp = [Fraction(p["pol"]["ratio"]) for p in pairs if p["pol"]["store_compressed"] == "1"]
        share = sum((Fraction(pop["shield_pool_kib"] * split.get((cls, pop["pop"]), 0), pop_total[pop["pop"]])
                     for pop in s1.pops if pop_total.get(pop["pop"], 0) > 0), Fraction(0))
        affected = sum(1 for n in members for p in s1.props.get(n["node_id"], []) if (n["node_id"], p) in s1.hits)
        rows.append([cls, len(members), len({n["pop"] for n in members}),
                     half_even(Fraction(sum(measured), 1 << 20)) if measured else None,
                     decimal_text(sum(comp, Fraction(0)) / len(comp), 3) if comp else None,
                     kib(sum(s1.calc[n["node_id"]]["peak"] for n in members)), affected, kib(share)])
    files["class_rollup.csv"] = render_csv("class_rollup.csv", rows)

    written = {n["node_id"]: i for i, n in enumerate(s1.nodes)}
    rows = []
    for pop in s1.pops:
        members = sorted((n for n in s1.nodes if n["pop"] == pop["pop"]),
                         key=lambda n: (int(n["tier"]), s1.calc[n["node_id"]]["pending"], written[n["node_id"]]))
        left = pop["shield_pool_kib"]
        running = 0
        for n in members:
            nid = n["node_id"]
            if s1.calc[nid]["measured"] == 0:
                rows.append([nid, pop["pop"], 0, 0, running, "unmeasured"])
                continue
            want = sum(int(s1.pair[(nid, p)]["fp"]["stale_kib"]) for p in s1.props[nid]
                       if s1.pair[(nid, p)]["pol"]["store_compressed"] == "1" and s1.pair[(nid, p)]["fp"]["stale_kib"] != "")
            give = min(want, left)
            left -= give
            running += give
            state = "zero" if want == 0 else "full" if give == want else "partial" if give else "none"
            rows.append([nid, pop["pop"], want, give, running, state])
    files["shield_alloc.csv"] = render_csv("shield_alloc.csv", rows)

    pin_rows, pinned = plan_pins(s1)
    files["pin_plan.csv"] = render_csv("pin_plan.csv", pin_rows)

    ranked = []
    for n in s1.nodes:
        nid = n["node_id"]
        c = s1.calc[nid]
        d = days_of(c["headroom"], c["daily"])
        hot_total = sum(int(s1.pair[(nid, p)]["fp"]["hot_kib"]) for p in s1.props.get(nid, [])
                        if s1.pair[(nid, p)]["fp"]["hot_kib"] != "")
        ranked.append((days_sort(d) + (nid,), [
            nid, n["pop"], c["headroom"], c["daily"], days_text(d),
            local_day(s1.cut, d, s1.pop[n["pop"]]["utc_offset_minutes"]) if isinstance(d, Fraction) else None,
            decimal_text(Fraction(pinned[nid], hot_total), 4) if hot_total else None, int(c["pending"])]))
    ranked.sort(key=lambda x: x[0])
    files["risk_rank.csv"] = render_csv("risk_rank.csv", [r + [i + 1] for i, (_k, r) in enumerate(ranked)])

    numeric = sorted(k[1] for k, _r in ranked if k[0] == 0)
    if numeric:
        k = len(numeric)
        median_text = decimal_text(numeric[k // 2] if k % 2 else (numeric[k // 2 - 1] + numeric[k // 2]) / 2, 2)
    else:
        median_text = None
    head = sorted(s1.calc[n["node_id"]]["headroom"] for n in s1.nodes)
    rank90 = -(-len(head) * 9 // 10)
    pairs = list(s1.pair.values())
    files["manifest.json"] = render_json({
        "phase": 2,
        "inputs": {n: sha(s1.raw[n]) for n in P1_NAMES},
        "totals": {
            "nodes": len(s1.nodes),
            "pairs_measured": sum(p["svc"]["daily_bytes"] != "" for p in pairs),
            "pairs_null": sum(p["svc"]["daily_bytes"] == "" for p in pairs),
            "pairs_compressed": sum(p["pol"]["store_compressed"] == "1" for p in pairs),
            "peak_kib": sum(int(p["fp"]["peak_kib"]) for p in pairs if p["fp"]["peak_kib"] != ""),
            "daily_kib": kib(sum(int(p["svc"]["daily_bytes"]) for p in pairs if p["svc"]["daily_bytes"] != "")),
            "pending_amendments": len(s1.amendments),
            "shield_kib": sum(p["shield_pool_kib"] for p in s1.pops),
            "pinned_kib": sum(pinned.values()),
        },
        "median_days_to_full": median_text,
        "p90_headroom_kib": head[max(rank90, 1) - 1] if head else None,
    })
    write_outputs(out_dir, files)


def phase3(p1_dir: Path, p2_dir: Path, out_dir: Path) -> None:
    s1 = Stage1(p1_dir)
    raw2 = read_upstream(p2_dir, P2_NAMES)
    pops2 = {r["pop"]: r for r in load_csv(p2_dir, "pop_rollup.csv")}
    class_rows = load_csv(p2_dir, "class_rollup.csv")
    classes2 = {r["class"]: r for r in class_rows}
    shield = {r["node_id"]: int(r["granted_kib"]) for r in load_csv(p2_dir, "shield_alloc.csv")}
    pinned = {}
    for r in load_csv(p2_dir, "pin_plan.csv"):
        if r["pinned"] == "1":
            pinned[r["node_id"]] = pinned.get(r["node_id"], 0) + int(r["hot_kib"])
    risk = {r["node_id"]: r for r in load_csv(p2_dir, "risk_rank.csv")}
    manifest2 = load_json(p2_dir, "manifest.json")
    if manifest2.get("phase") != 2 or manifest2.get("inputs") != {n: sha(s1.raw[n]) for n in P1_NAMES}:
        raise UpstreamError(str(p2_dir / "manifest.json"))
    limit = Fraction(manifest2["median_days_to_full"]) if manifest2["median_days_to_full"] is not None else None
    cap = manifest2["p90_headroom_kib"]

    proj = []
    used_amendments = set()
    for n in s1.nodes:
        nid = n["node_id"]
        now = after = 0
        for p in s1.props.get(nid, []):
            row = s1.pair[(nid, p)]
            old = 0 if row["fp"]["peak_kib"] == "" else int(row["fp"]["peak_kib"])
            now += old
            hits = s1.hits.get((nid, p), [])
            used_amendments.update(a["id"] for a in hits)
            if not hits or row["svc"]["daily_bytes"] == "":
                after += old
                continue
            rule = {"versions": int(row["pol"]["versions"]), "refresh": row["pol"]["refresh"],
                    "store_compressed": row["pol"]["store_compressed"] == "1", "hot_raw": row["pol"]["hot_raw"] == "1"}
            for a in hits:
                rule[a["field"]] = a["value"]
            window = coarser_window(rule["refresh"], n["sweep_interval"])
            *_rest, peak = footprint(int(row["svc"]["daily_bytes"]), window, int(rule["versions"]),
                                     bool(rule["store_compressed"]), bool(rule["hot_raw"]), row["pol"]["ratio"])
            after += kib(peak)
        c = s1.calc[nid]
        observed = kib(int(n["post_cut_used_bytes"])) if n["post_cut_used_bytes"] != "" else c["base"]
        head = c["usable"] - observed - after + shield.get(nid, 0) + pinned.get(nid, 0)
        gap = after - int(n["prior_peak_kib"]) if n["prior_peak_kib"] != "" else None
        d = days_of(head, opt_int(risk[nid]["daily_kib"]))
        if isinstance(d, Fraction) and limit is not None and d < limit:
            flag = "at-risk"
        elif after > now:
            flag = "watch"
        else:
            flag = "ok"
        pop_den = int(pops2[n["pop"]]["headroom_mib"]) * 1024
        class_den = int(classes2[n["class"]]["peak_mib"]) * 1024
        proj.append({
            "nid": nid, "pop": n["pop"], "class": n["class"], "tier": n["tier"], "now": now, "after": after, "gap": gap,
            "head": head, "days": d, "rank": int(risk[nid]["rank"]), "flag": flag, "daily": risk[nid]["daily_kib"],
            "ps": Fraction(head, pop_den) if pop_den > 0 else None,
            "cs": Fraction(after, class_den) if class_den > 0 else None,
            "date": local_day(s1.cut, d, s1.pop[n["pop"]]["utc_offset_minutes"]) if isinstance(d, Fraction) else None,
        })
    four = lambda x: None if x is None else decimal_text(x, 4)
    files = {}
    rows = []
    running = 0
    lowest = None
    for p in proj:
        running += p["head"]
        lowest = running if lowest is None else min(lowest, running)
        rows.append([p["nid"], p["pop"], p["class"], p["now"], p["after"], p["gap"], p["head"], days_text(p["days"]), p["rank"],
                     p["flag"], four(p["ps"]), four(p["cs"]), p["date"], running, lowest])
    files["projection.csv"] = render_csv("projection.csv", rows)

    rows = []
    spill = {}
    for pop in s1.pops:
        short = [p for p in proj if p["pop"] == pop["pop"] and p["head"] < 0]
        short.sort(key=lambda p: (0 if p["cs"] is not None else 1, -(p["cs"] or 0), p["head"], p["nid"]))
        left = pop["spill_budget_kib"]
        healthy_pop = int(pops2[pop["pop"]]["headroom_mib"]) > 0
        for p in short:
            gap = -p["head"]
            if healthy_pop and p["tier"] == "3":
                rows.append([p["nid"], pop["pop"], gap, p["daily"], 0, left, "deferred"])
                continue
            give = min(gap, left)
            if cap is not None and cap > 0:
                give = min(give, cap)
            left -= give
            spill[p["nid"]] = give
            rows.append([p["nid"], pop["pop"], gap, p["daily"], give, left,
                         "full" if give == gap else "partial" if give > 0 else "none"])
    files["spill_alloc.csv"] = render_csv("spill_alloc.csv", rows)

    rows = []
    for pop in s1.pops:
        here = [p for p in proj if p["pop"] == pop["pop"]]
        risky = [p for p in here if p["flag"] == "at-risk"]
        nums = [p["days"] for p in here if isinstance(p["days"], Fraction)]
        members = {p["nid"] for p in here}
        touched = {a["id"] for (nid, _p), hits in s1.hits.items() if nid in members for a in hits}
        worst = None
        if risky:
            load = {}
            for p in risky:
                load[p["class"]] = load.get(p["class"], Fraction(0)) + (p["cs"] or Fraction(0))
            worst = min(load, key=lambda k: (-load[k], k))
        rows.append([pop["pop"], int(pops2[pop["pop"]]["headroom_mib"]), kib(sum(p["head"] for p in here)), len(risky),
                     kib(pop["shield_pool_kib"] - sum(shield.get(p["nid"], 0) for p in here)),
                     kib(pop["spill_budget_kib"] - sum(spill.get(p["nid"], 0) for p in here)),
                     len(touched), decimal_text(sum(nums, Fraction(0)) / len(nums), 2) if nums else None, worst])
    files["pop_outlook.csv"] = render_csv("pop_outlook.csv", rows)

    rows = []
    issued = 0
    order = {"at-risk": 0, "watch": 1}
    for pop in s1.pops:
        cand = [p for p in proj if p["pop"] == pop["pop"] and p["flag"] in order]
        cand.sort(key=lambda p: (order[p["flag"]], days_sort(p["days"]),
                                 0 if p["cs"] is not None else 1, -(p["cs"] or 0),
                                 0 if p["ps"] is not None else 1, -(p["ps"] or 0), p["nid"]))
        quota = pop["ticket_quota"] if int(pops2[pop["pop"]]["headroom_mib"]) > 0 else 2 * pop["ticket_quota"]
        for k, p in enumerate(cand[:quota], start=1):
            rows.append([f"T-{pop['pop']}-{k:02d}", pop["pop"], p["nid"], p["flag"], days_text(p["days"]), p["rank"]])
            issued += 1
    files["tickets.csv"] = render_csv("tickets.csv", rows)

    pop_after, mix = {}, {}
    for p in proj:
        pop_after[p["pop"]] = pop_after.get(p["pop"], 0) + p["after"]
        mix[(p["class"], p["pop"])] = mix.get((p["class"], p["pop"]), 0) + p["after"]
    rows = []
    for r in class_rows:
        cls = r["class"]
        mine = [p for p in proj if p["class"] == cls]
        after = kib(sum(p["after"] for p in mine))
        shares = [p["ps"] for p in mine if p["ps"] is not None]
        pool = sum((Fraction(pop["shield_pool_kib"] * mix.get((cls, pop["pop"]), 0), pop_after[pop["pop"]])
                    for pop in s1.pops if pop_after.get(pop["pop"], 0) > 0), Fraction(0))
        gaps = [p["gap"] for p in mine if p["gap"] is not None]
        rows.append([cls, int(r["peak_mib"]), after, after - int(r["peak_mib"]), kib(sum(gaps)) if gaps else None,
                     sum(p["flag"] == "at-risk" for p in mine),
                     decimal_text(sum(shares, Fraction(0)) / len(shares), 4) if shares else None, kib(pool)])
    files["class_drift.csv"] = render_csv("class_drift.csv", rows)

    chain = "0" * 64
    for line in files["projection.csv"].split("\n")[1:]:
        if line:
            chain = sha((chain + line).encode("utf-8"))
    inputs = {f"p1/{n}": sha(s1.raw[n]) for n in P1_NAMES}
    inputs.update({f"p2/{n}": sha(raw2[n]) for n in P2_NAMES})
    files["manifest.json"] = render_json({
        "phase": 3, "inputs": inputs, "chain": chain,
        "totals": {"nodes": len(proj), "at_risk": sum(p["flag"] == "at-risk" for p in proj),
                   "watch": sum(p["flag"] == "watch" for p in proj),
                   "peak_after_kib": sum(p["after"] for p in proj),
                   "headroom_after_kib": sum(p["head"] for p in proj),
                   "spill_granted_kib": sum(spill.values()),
                   "tickets": issued, "pending_applied": len(used_amendments)},
    })
    write_outputs(out_dir, files)


def main(argv) -> int:
    try:
        if not argv:
            raise UsageError("missing subcommand")
        cmd, rest = argv[0], argv[1:]
        arity = {"phase1": 2, "phase2": 2, "phase3": 3}
        if cmd not in arity:
            raise UsageError(f"unknown subcommand {cmd!r}")
        if len(rest) != arity[cmd]:
            raise UsageError(f"{cmd} takes {arity[cmd]} directories")
        paths = [Path(p) for p in rest]
        if cmd == "phase1":
            phase1(paths[0], paths[1])
        elif cmd == "phase2":
            phase2(paths[0], paths[1])
        else:
            phase3(paths[0], paths[1], paths[2])
    except UsageError as exc:
        print(f"error: usage: {exc}", file=sys.stderr)
        return 2
    except UpstreamError as exc:
        print(f"error: upstream: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
