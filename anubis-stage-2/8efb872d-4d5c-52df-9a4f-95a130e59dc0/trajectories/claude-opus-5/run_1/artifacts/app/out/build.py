#!/usr/bin/env python3
"""Cache placement optimizer for the CDN edge fleet.

Three stages, driven from the command line:

    build.py phase1 <DATA_DIR> <P1_DIR>
    build.py phase2 <P1_DIR> <P2_DIR>
    build.py phase3 <P1_DIR> <P2_DIR> <P3_DIR>

Phase 1 reduces the input corpus to frozen per-node and per-pair figures
following ``edge_capacity_standard_r7.md``.  Phase 2 rolls those up, and
phase 3 projects the pending amendments on top.  Phases 2 and 3 read only
their upstream directories.
"""

import base64
import csv
import hashlib
import json
import os
import re
import sys
import tomllib
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction

# ---------------------------------------------------------------------------
# constants fixed by the standard and the output contract
# ---------------------------------------------------------------------------

CUT = datetime(2024, 10, 1, 18, 0, 0, tzinfo=timezone.utc)
WINDOW_START = CUT - timedelta(days=7)
CACHE_MOUNT = "/var/cache/edge"
SWEEP_BINARY = "/usr/local/sbin/cache-sweep"
SWEEP_CONF = "/etc/edgecache/edgecache.conf"
NVME_DEFAULT_RESERVE_PCT = 7
BENCH_CORPUS = "edge24"
ACTIVE_STATUSES = frozenset({"active", "serving", "maintenance"})
CODEC_DEFAULT_LEVEL = {"gzip": 6, "zstd": 3, "br": 4}
REFRESH_RANK = {"hourly": 0, "daily": 1, "weekly": 2}
CYCLE_FACTOR = {"hourly": Fraction(1, 24), "daily": Fraction(1), "weekly": Fraction(7)}

COUNTER_FILES = (
    "amer_node_dump.csv",
    "apj_export_0928.jsonl",
    "bulkpull_0929.csv",
    "busfeed_edge.ndjson",
    "colld-fra1.log",
    "colld-misc.log",
    "colld-sin3.log",
    "edgetap_0927.prom",
    "edgetap_0929.prom",
    "lb_poll_east.tsv",
    "lbpop_counters.prom",
    "legacy_poller.tsv",
    "legacy_poller_b.tsv",
    "node_tail_west.csv",
    "pdump-fra-w39.prom",
    "pushgw_dump.xml",
    "pushgw_dump_2.xml",
    "rwtail_w39.jsonl",
    "scr_k22_export.prom",
    "scrape_audit.html",
    "tsarch_part1.sql",
    "tsarch_part2.sql",
)

USAGE_FILES = ("ducollect_a.log", "ducollect_b.log", "ducollect_late.log")

BASE_INPUT_FILES = (
    "asset_status_hist.csv",
    "blkdev_audit.tsv",
    "cab_minutes.md",
    "codec_bench.csv",
    "cr_export.jsonl",
    "decom_cal.ics",
    "edgecache_2023.conf",
    "edgecache_main.conf",
    "hwclass_ledger.sql",
    "ident_overrides.properties",
    "labnodes.tsv",
    "mirror_twins.json",
    "nodedir_export.ldif",
    "optplan_prev.csv",
    "pathmap.ini",
    "pop_registry.toml",
    "prop_changes.csv",
    "replay_inject_q3.prom",
    "scrape_targets.toml",
    "stg_jobs.toml",
    "sweeper.crontab",
    "tier_assign.xml",
    "tuning_drafts.jsonl",
)

P1_FILES = (
    "footprints.csv",
    "nodes.csv",
    "pending.json",
    "policies.csv",
    "pops.json",
    "properties.csv",
)

P2_FILES = (
    "class_rollup.csv",
    "manifest.json",
    "pin_plan.csv",
    "pop_rollup.csv",
    "risk_rank.csv",
    "shield_alloc.csv",
)

HEADERS = {
    "nodes.csv": "node_id,pop,class,tier,media,usable_bytes,base_used_bytes,"
                 "post_cut_used_bytes,prior_peak_kib,sweep_interval,ram_bytes",
    "properties.csv": "node_id,property,instance,samples,daily_bytes",
    "policies.csv": "node_id,property,versions,refresh,effective_refresh,"
                    "store_compressed,hot_raw,codec,ratio",
    "footprints.csv": "node_id,property,cycle_bytes,hot_kib,stale_kib,peak_kib",
    "pop_rollup.csv": "pop,nodes,measured_pairs,null_pairs,compressed_pairs,peak_mib,"
                      "usable_mib,headroom_mib,pending_nodes,shield_mib",
    "class_rollup.csv": "class,nodes,pops,daily_mib,mean_ratio,peak_mib,pending_pairs,"
                        "shield_share_mib",
    "shield_alloc.csv": "node_id,pop,demand_kib,granted_kib,cumulative_kib,state",
    "pin_plan.csv": "node_id,property,density,hot_kib,cumulative_kib,pinned",
    "risk_rank.csv": "node_id,pop,headroom_kib,daily_kib,days_to_full,full_date_local,"
                     "pin_share,pending,rank",
    "projection.csv": "node_id,pop,class,peak_now_kib,peak_after_kib,prior_gap_kib,"
                      "headroom_after_kib,days_after,rank_before,flag,pop_share,"
                      "class_peak_share,full_date_after,running_kib,running_min_kib",
    "pop_outlook.csv": "pop,headroom_mib_now,headroom_mib_after,at_risk_nodes,"
                       "shield_left_mib,spill_left_mib,pending_applied,mean_days_after,"
                       "worst_class",
    "spill_alloc.csv": "node_id,pop,deficit_kib,daily_kib,granted_kib,remaining_kib,state",
    "tickets.csv": "ticket,pop,node_id,flag,days_after,rank_before",
    "class_drift.csv": "class,peak_mib_now,peak_mib_after,drift_mib,prior_gap_mib,"
                       "at_risk_nodes,mean_pop_share,shield_share_after_mib",
}


class UsageError(Exception):
    """Wrong subcommand or wrong number of arguments."""


class UpstreamError(Exception):
    """Missing, unreadable or inconsistent input/upstream directory."""


# ---------------------------------------------------------------------------
# small numeric and text helpers
# ---------------------------------------------------------------------------

def to_fraction(text):
    """Parse a decimal or exponential literal exactly."""
    s = str(text).strip()
    m = re.fullmatch(r"([+-]?)(\d*)(?:\.(\d*))?(?:[eE]([+-]?\d+))?", s)
    if not m or (not m.group(2) and not m.group(3)):
        raise ValueError("not a number: %r" % (text,))
    sign = -1 if m.group(1) == "-" else 1
    whole = m.group(2) or "0"
    frac = m.group(3) or ""
    exp = int(m.group(4) or 0)
    value = Fraction(int(whole + frac) if frac else int(whole), 10 ** len(frac))
    return sign * value * Fraction(10) ** exp


def half_even(value):
    """Round a Fraction (or int) to the nearest integer, halves to even."""
    return round(Fraction(value))


def floor_div(value):
    """Floor of a Fraction."""
    f = Fraction(value)
    return f.numerator // f.denominator


def ceil_frac(value):
    f = Fraction(value)
    return -((-f.numerator) // f.denominator)


def fmt_dec(value, places):
    """Format a Fraction with a fixed number of places, halves to even."""
    scaled = half_even(Fraction(value) * 10 ** places)
    sign = "-" if scaled < 0 else ""
    digits = str(abs(scaled)).rjust(places + 1, "0")
    if places == 0:
        return sign + digits
    return "%s%s.%s" % (sign, digits[:-places], digits[-places:])


def fmt_int(value):
    return "" if value is None else str(int(value))


def normalise_name(text):
    return text.strip().lower()


# ---------------------------------------------------------------------------
# instant parsing
# ---------------------------------------------------------------------------

_DT_RE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?\s*"
    r"(Z|z|[+-]\d{2}:\d{2}|[+-]\d{4}|[+-]\d{2})?"
)
_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_NUM_RE = re.compile(r"[+-]?\d+(?:\.\d+)?")


def _tz_from_text(text):
    if text is None:
        return None
    if text in ("Z", "z"):
        return timezone.utc
    sign = 1 if text[0] == "+" else -1
    body = text[1:].replace(":", "")
    hours = int(body[:2])
    minutes = int(body[2:4]) if len(body) > 2 else 0
    return timezone(sign * timedelta(hours=hours, minutes=minutes))


def parse_instant(value, local_offset_minutes=None):
    """Parse one of the corpus instant spellings into an aware UTC datetime.

    ``local_offset_minutes`` supplies the zone for bare wall-clock readings.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return _from_epoch(to_fraction(repr(value)))
    text = str(value).strip()
    if not text:
        raise ValueError("empty instant")
    if _NUM_RE.fullmatch(text):
        return _from_epoch(to_fraction(text))
    m = _DT_RE.fullmatch(text)
    if m:
        micro = 0
        if m.group(7):
            micro = int((m.group(7) + "000000")[:6])
        tz = _tz_from_text(m.group(8))
        if tz is None:
            offset = 0 if local_offset_minutes is None else local_offset_minutes
            tz = timezone(timedelta(minutes=offset))
        naive = datetime(
            int(m.group(1)), int(m.group(2)), int(m.group(3)),
            int(m.group(4)), int(m.group(5)), int(m.group(6)), micro, tzinfo=tz,
        )
        return naive.astimezone(timezone.utc)
    m = _DATE_RE.fullmatch(text)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                        tzinfo=timezone.utc)
    raise ValueError("unrecognised instant: %r" % (value,))


def _from_epoch(frac):
    seconds = frac / 1000 if abs(frac) >= 10 ** 11 else frac
    whole = floor_div(seconds)
    micro = half_even((seconds - whole) * 1000000)
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
        seconds=whole, microseconds=micro)


def fmt_instant(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# size parsing
# ---------------------------------------------------------------------------

_CAP_RE = re.compile(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([KMGTP]i?B|B)?\s*$")
_BINARY_RE = re.compile(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([KMGTP]?)(?:i?B)?\s*$", re.I)


def parse_capacity(text):
    """Capacity with the standard's suffix rules, in bytes (exact)."""
    m = _CAP_RE.fullmatch(str(text))
    if not m:
        raise ValueError("bad capacity: %r" % (text,))
    number = to_fraction(m.group(1))
    suffix = m.group(2) or ""
    if suffix in ("", "B"):
        return number
    power = "KMGTP".index(suffix[0]) + 1
    base = 1024 if "i" in suffix else 1000
    return number * base ** power


def parse_binary_size(text):
    """Memory and df -h sizes: binary whatever the suffix."""
    m = _BINARY_RE.fullmatch(str(text))
    if not m:
        raise ValueError("bad size: %r" % (text,))
    number = to_fraction(m.group(1))
    letter = m.group(2).upper()
    if not letter:
        return number
    return number * 1024 ** ("KMGTP".index(letter) + 1)


# ---------------------------------------------------------------------------
# node identity
# ---------------------------------------------------------------------------

class Identity:
    """Resolves every reference spelling in the corpus to a canonical node id."""

    def __init__(self, directory, aliases, renames):
        self.directory = directory
        self.aliases = aliases
        self.renames = renames
        self._cache = {}

    def _follow(self, name):
        seen = set()
        current = name
        while True:
            nxt = self.renames.get(current)
            if nxt is None or nxt == current or nxt in seen:
                return current
            seen.add(current)
            current = nxt

    def resolve(self, ref, pop=None):
        key = (normalise_name(str(ref)), normalise_name(str(pop)) if pop else None)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        text = key[0]
        candidates = []
        if "@" in text:
            candidates.append(("legacy", text))
        else:
            if text.endswith(".edge.lan"):
                candidates.append(("fqdn", text))
            if text.startswith("ca-"):
                candidates.append(("asset", text))
            if text.startswith("sn"):
                candidates.append(("serial", text))
            if key[1]:
                candidates.append(("legacy", "%s@%s" % (text, key[1])))
            candidates.append((None, text))
        result = None
        for cand in candidates:
            if cand in self.aliases:
                result = self.aliases[cand]
                break
        if result is None:
            for cand in candidates:
                if cand in self.directory:
                    result = self.directory[cand]
                    break
        if result is None:
            result = text
        result = self._follow(result)
        self._cache[key] = result
        return result


def load_ldif(path):
    """Unfolded LDIF entries as dicts of attribute -> list of values."""
    entries = []
    current = None
    lines = []
    for raw in read_text(path).split("\n"):
        if raw.startswith(" ") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    for line in lines:
        if not line.strip():
            continue
        if line.startswith("#"):
            continue
        if ":" not in line:
            continue
        attr, _, rest = line.partition(":")
        if rest.startswith(":"):
            value = base64.b64decode(rest[1:].strip()).decode("utf-8")
        else:
            value = rest.strip()
        if attr == "dn":
            current = {}
            entries.append(current)
        if current is None:
            continue
        current.setdefault(attr, []).append(value)
    return entries


def load_identity(data_dir, pop_canon):
    directory = {}
    for entry in load_ldif(os.path.join(data_dir, "nodedir_export.ldif")):
        cns = entry.get("cn")
        if not cns:
            continue
        canonical = normalise_name(cns[-1])
        directory[(None, canonical)] = canonical
        for attr, kind in (("assetTag", "asset"), ("dNSName", "fqdn"),
                           ("serialNumber", "serial")):
            for value in entry.get(attr, []):
                directory[(kind, normalise_name(value))] = canonical
        for value in entry.get("legacyName", []):
            short, _, pop = normalise_name(value).partition("@")
            directory[("legacy", "%s@%s" % (short, pop_canon.get(pop, pop)))] = canonical

    alias_best = {}
    rename_best = {}
    pattern = re.compile(
        r"^(alias\.(?P<kind>[a-z]+)\.(?P<value>.+?)|rename\.(?P<old>.+?))"
        r"\s*[:=]\s*(?P<target>[^;]+?)\s*;\s*rev\s*=\s*(?P<rev>\d+)\s*$")
    for line in read_text(os.path.join(data_dir, "ident_overrides.properties")).split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        m = pattern.match(line)
        if not m:
            continue
        rev = int(m.group("rev"))
        target = normalise_name(m.group("target"))
        if m.group("old") is not None:
            key = normalise_name(m.group("old"))
            if key not in rename_best or rev >= rename_best[key][0]:
                rename_best[key] = (rev, target)
        else:
            kind = m.group("kind")
            value = normalise_name(m.group("value"))
            if kind == "legacy":
                short, _, pop = value.partition("@")
                value = "%s@%s" % (short, pop_canon.get(pop, pop))
            key = (kind, value)
            if key not in alias_best or rev >= alias_best[key][0]:
                alias_best[key] = (rev, target)
    aliases = {k: v[1] for k, v in alias_best.items()}
    renames = {k: v[1] for k, v in rename_best.items()}
    return Identity(directory, aliases, renames)


# ---------------------------------------------------------------------------
# generic readers
# ---------------------------------------------------------------------------

def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        raise UpstreamError(path) from exc


def read_lines(path):
    return read_text(path).split("\n")


def read_csv_rows(path):
    text = read_text(path)
    return list(csv.DictReader(text.splitlines()))


def require_dir(path):
    if not os.path.isdir(path) or not os.access(path, os.R_OK | os.X_OK):
        raise UpstreamError(path)


def require_files(directory, names):
    require_dir(directory)
    for name in names:
        full = os.path.join(directory, name)
        if not os.path.isfile(full) or not os.access(full, os.R_OK):
            raise UpstreamError(full)


# ---------------------------------------------------------------------------
# PoP registry
# ---------------------------------------------------------------------------

def parse_offset_minutes(text):
    body = str(text).strip()
    if body.upper().startswith("UTC"):
        body = body[3:]
    m = re.fullmatch(r"([+-])(\d{2}):?(\d{2})", body)
    if not m:
        raise ValueError("bad offset: %r" % (text,))
    sign = 1 if m.group(1) == "+" else -1
    return sign * (int(m.group(2)) * 60 + int(m.group(3)))


def parse_pct(text):
    return int(str(text).strip().rstrip("%").strip())


def load_pops(data_dir):
    with open(os.path.join(data_dir, "pop_registry.toml"), "rb") as handle:
        doc = tomllib.load(handle)
    pops = {}
    canon = {}
    for code, body in doc.get("pops", {}).items():
        key = normalise_name(code)
        pops[key] = {
            "pop": key,
            "utc_offset_minutes": parse_offset_minutes(body["utc_offset"]),
            "shield_pool_bytes": parse_capacity(body["shield_pool"]),
            "ticket_quota": int(body["ticket_quota"]),
            "spill_budget_bytes": parse_capacity(body["spill_budget"]),
            "ram_pin_pct": parse_pct(body["ram_pin_pct"]),
            "scope": normalise_name(body["scope"]),
        }
        canon[key] = key
        for alias in body.get("aliases", []):
            canon[normalise_name(alias)] = key
    placements = []
    for pid, body in sorted(doc.get("placement", {}).items()):
        placements.append({
            "id": pid,
            "node_ref": body["node"],
            "pop": canon.get(normalise_name(body["pop"]), normalise_name(body["pop"])),
            "since": parse_instant(body["since"]),
            "state": normalise_name(body["state"]),
        })
    return pops, canon, placements


# ---------------------------------------------------------------------------
# node attribute histories
# ---------------------------------------------------------------------------

def latest_at_cut(records):
    """Latest (instant, order, payload) record at or before the cut."""
    best = None
    for moment, order, payload in records:
        if moment > CUT:
            continue
        if best is None or (moment, order) >= (best[0], best[1]):
            best = (moment, order, payload)
    return None if best is None else best[2]


def load_asset_status(data_dir, ident):
    history = {}
    for index, row in enumerate(read_csv_rows(os.path.join(data_dir, "asset_status_hist.csv"))):
        node = ident.resolve(row["node_ref"], row.get("pop_hint"))
        moment = parse_instant(row["recorded_at"])
        history.setdefault(node, []).append(
            (moment, index, (normalise_name(row["status"]), row["mem"])))
    return {node: latest_at_cut(recs) for node, recs in history.items()}


_SQL_CLASS_RE = re.compile(
    r"VALUES\s*\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*(\d+)\s*,\s*'([^']*)'\s*\)")


def load_classes(data_dir, ident):
    history = {}
    for index, line in enumerate(read_lines(os.path.join(data_dir, "hwclass_ledger.sql"))):
        m = _SQL_CLASS_RE.search(line)
        if not m:
            continue
        if int(m.group(4)):
            continue
        node = ident.resolve(m.group(1))
        history.setdefault(node, []).append(
            (parse_instant(m.group(3)), index, normalise_name(m.group(2))))
    return {node: latest_at_cut(recs) for node, recs in history.items()}


def load_tiers(data_dir, ident):
    text = read_text(os.path.join(data_dir, "tier_assign.xml"))
    class_default = {}
    for m in re.finditer(r'<class\s+name="([^"]*)"\s+tier="([^"]*)"\s*/>', text):
        class_default[normalise_name(m.group(1))] = normalise_name(m.group(2))
    node_tier = {}
    index = 0
    for m in re.finditer(r'<node\s+ref="([^"]*)"\s*>(.*?)</node>', text, re.S):
        node = ident.resolve(m.group(1))
        records = []
        for entry in re.finditer(r'<tier\s+since="([^"]*)"\s*>(.*?)</tier>', m.group(2), re.S):
            index += 1
            records.append((parse_instant(entry.group(1)), index,
                            normalise_name(entry.group(2))))
        value = latest_at_cut(records)
        if value is not None:
            node_tier[node] = value
    return class_default, node_tier


def load_decommissions(data_dir, ident):
    confirmed = set()
    block = {}
    for line in read_lines(os.path.join(data_dir, "decom_cal.ics")):
        line = line.strip()
        if line == "BEGIN:VEVENT":
            block = {}
            continue
        if line == "END:VEVENT":
            status = normalise_name(block.get("STATUS", ""))
            ref = block.get("X-NODE")
            start = block.get("DTSTART")
            if status == "confirmed" and ref and start is not None:
                if start <= CUT:
                    confirmed.add(ident.resolve(ref))
            block = {}
            continue
        if ":" not in line:
            continue
        name, _, value = line.partition(":")
        parts = name.split(";")
        key = parts[0].upper()
        if key == "DTSTART":
            params = dict(p.split("=", 1) for p in parts[1:] if "=" in p)
            block["DTSTART"] = _parse_ics_instant(value, params)
        elif key == "X-NODE":
            block["X-NODE"] = value.strip()
        elif key == "STATUS":
            block["STATUS"] = value.strip()
    return confirmed


def _etc_gmt_offset(zone):
    m = re.fullmatch(r"Etc/GMT([+-])(\d{1,2})", zone)
    if not m:
        raise ValueError("unsupported zone: %r" % (zone,))
    hours = int(m.group(2))
    return timezone(timedelta(hours=-hours if m.group(1) == "+" else hours))


def _parse_ics_instant(value, params):
    text = value.strip()
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", text):
        return datetime(int(text[0:4]), int(text[4:6]), int(text[6:8]), tzinfo=timezone.utc)
    m = re.fullmatch(r"(\d{8})T(\d{6})(Z?)", text)
    if not m:
        raise ValueError("bad DTSTART: %r" % (value,))
    day, clock, zulu = m.groups()
    tz = timezone.utc
    if not zulu and "TZID" in params:
        tz = _etc_gmt_offset(params["TZID"])
    naive = datetime(int(day[0:4]), int(day[4:6]), int(day[6:8]),
                     int(clock[0:2]), int(clock[2:4]), int(clock[4:6]), tzinfo=tz)
    return naive.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# property catalogue and path map
# ---------------------------------------------------------------------------

class PropertyCatalog:
    def __init__(self, data_dir, ident):
        text = read_lines(os.path.join(data_dir, "pathmap.ini"))
        sections = []
        current = None
        for line in text:
            stripped = line.strip()
            if not stripped or stripped.startswith(";") or stripped.startswith("#"):
                continue
            m = re.fullmatch(r"\[(.+)\]", stripped)
            if m:
                current = (m.group(1).strip(), [])
                sections.append(current)
                continue
            if current is None or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            current[1].append((key.strip(), value.strip().strip('"')))
        self.alias = {}
        self.catalog = {}
        self.types = {}
        node_sections = []
        for name, items in sections:
            lowered = name.lower()
            if lowered == "aliases":
                for key, value in items:
                    self.alias[normalise_name(key)] = normalise_name(value)
            elif lowered == "catalog":
                for key, value in items:
                    self.catalog[normalise_name(key)] = value
            elif lowered == "types":
                for key, value in items:
                    self.types[normalise_name(key)] = normalise_name(value)
            else:
                node_sections.append((name, items))
        self.renamed = {}
        for line in read_lines(os.path.join(data_dir, "edgecache_2023.conf")):
            m = re.match(r"#\s*renamed\s+(\S+)\s*->\s*(\S+)\s*$", line.strip())
            if m:
                self.renamed[normalise_name(m.group(1))] = normalise_name(m.group(2))
        self.catalog_by_path = {}
        for prop, path in self.catalog.items():
            self.catalog_by_path.setdefault(path, prop)
        self.node_paths = {}
        for name, items in node_sections:
            node = ident.resolve(name)
            table = self.node_paths.setdefault(node, {})
            for key, value in items:
                prop = self.name_of(key)
                if prop is not None:
                    table[prop] = value
        self._ref_cache = {}

    def name_of(self, ref):
        """Resolve a non-path property reference to its catalog name."""
        text = normalise_name(ref)
        if text in self.catalog:
            return text
        if text in self.alias:
            return self.alias[text]
        if text in self.renamed:
            return self.renamed[text]
        return None

    def path_for(self, node, prop):
        return self.node_paths.get(node, {}).get(prop) or self.catalog.get(prop)

    def resolve(self, ref, node=None):
        """Resolve any property reference, including a cache path."""
        key = (normalise_name(str(ref)), node)
        hit = self._ref_cache.get(key)
        if hit is not None:
            return hit
        text = key[0]
        prop = self.name_of(text)
        if prop is None and text.startswith("/"):
            table = self.node_paths.get(node) if node else None
            if table:
                for candidate in sorted(table):
                    if table[candidate] == text:
                        prop = candidate
                        break
            if prop is None:
                prop = self.catalog_by_path.get(text)
        self._ref_cache[key] = prop
        return prop


# ---------------------------------------------------------------------------
# cache configuration
# ---------------------------------------------------------------------------

def _tokenise_directives(body):
    out = []
    for statement in body.split(";"):
        statement = re.sub(r"#.*", "", statement).strip()
        if not statement:
            continue
        parts = statement.split()
        out.append((parts[0], parts[1:]))
    return out


def _strip_comments(text):
    return "\n".join(re.sub(r"#.*", "", line) for line in text.split("\n"))


def _split_blocks(text, keyword):
    """Yield (name, body) for top level ``keyword <name> { ... }`` blocks."""
    pos = 0
    pattern = re.compile(r"\b%s\s+(\S+)\s*\{" % keyword)
    while True:
        m = pattern.search(text, pos)
        if not m:
            return
        depth = 1
        i = m.end()
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        yield m.group(1), text[m.end():i - 1]
        pos = i


def _locations(body):
    out = []
    for name, inner in _split_blocks(body, "location"):
        out.append((name.strip('"'), _tokenise_directives(inner)))
    return out


class CacheConfig:
    def __init__(self, data_dir, ident):
        main_text = read_text(os.path.join(data_dir, "edgecache_main.conf"))
        clean = _strip_comments(main_text)
        first_class = clean.find("class ")
        self.global_directives = _tokenise_directives(
            clean[:first_class] if first_class >= 0 else clean)
        self.class_locations = {}
        for name, body in _split_blocks(clean, "class"):
            self.class_locations[normalise_name(name)] = _locations(body)
        node_blocks = []
        for name, body in _split_blocks(clean, "node"):
            node_blocks.append((ident.resolve(name), _locations(body)))
        includes = [m.group(1) for m in re.finditer(r"include\s+(\S+?)\s*;", clean)]
        seen = set()
        for include in includes:
            if include in seen:
                continue
            seen.add(include)
            inc_clean = _strip_comments(
                read_text(os.path.join(data_dir, include)))
            for name, body in _split_blocks(inc_clean, "node"):
                node_blocks.append((ident.resolve(name), _locations(body)))
        self.node_blocks = {}
        for node, locs in node_blocks:
            self.node_blocks.setdefault(node, []).extend(locs)


def apply_layer(policy, directives):
    """Apply one configuration layer; a later directive inside it wins."""
    pending = {}
    for name, args in directives:
        key = name.lower()
        if key == "versions" and args:
            pending["versions"] = int(args[0])
        elif key == "refresh" and args:
            pending["refresh"] = normalise_name(args[0])
        elif key == "store-compressed" and args:
            pending["store_compressed"] = normalise_name(args[0]) == "on"
        elif key == "hot-raw" and args:
            pending["hot_raw"] = normalise_name(args[0]) == "on"
        elif key == "codec" and args:
            pending["codec"] = canonical_codec(args[0])
        elif key == "codec-level" and args:
            pending["codec_level"] = int(args[0])
    for field in ("versions", "refresh", "store_compressed", "hot_raw"):
        if field in pending:
            policy[field] = pending[field]
    if "codec" in pending:
        policy["codec"] = pending["codec"]
        policy["codec_level"] = pending.get(
            "codec_level", CODEC_DEFAULT_LEVEL[pending["codec"]])
    elif "codec_level" in pending:
        policy["codec_level"] = pending["codec_level"]


def canonical_codec(name):
    text = normalise_name(name)
    if text in ("br", "brotli"):
        return "br"
    if text in ("zstd", "zst"):
        return "zstd"
    return text


def apply_amendment(policy, field, value):
    if field == "versions":
        policy["versions"] = int(value)
    elif field == "refresh":
        policy["refresh"] = normalise_name(value)
    elif field in ("store_compressed", "hot_raw"):
        policy[field] = bool(value)
    elif field == "codec":
        codec, _, level = str(value).partition(":")
        policy["codec"] = canonical_codec(codec)
        policy["codec_level"] = int(level) if level else \
            CODEC_DEFAULT_LEVEL[policy["codec"]]


# ---------------------------------------------------------------------------
# amendments
# ---------------------------------------------------------------------------

def load_amendments(data_dir, ident, catalog):
    drafts = {}
    for line in read_lines(os.path.join(data_dir, "tuning_drafts.jsonl")):
        line = line.strip()
        if not line:
            continue
        doc = json.loads(line)
        drafts[doc["proposal"]] = (doc["field"], doc["value"])

    decisions = {}
    row_re = re.compile(r"^\|(.+)\|\s*$")
    for index, line in enumerate(read_lines(os.path.join(data_dir, "cab_minutes.md"))):
        m = row_re.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if len(cells) < 3 or cells[0].lower() == "decided":
            continue
        if set(cells[0]) <= set("- :"):
            continue
        try:
            moment = parse_instant(cells[0])
        except ValueError:
            continue
        if moment > CUT:
            continue
        verdict = normalise_name(cells[2])
        if verdict.startswith("approv"):
            outcome = "approved"
        elif verdict.startswith("reject"):
            outcome = "rejected"
        else:
            outcome = None
        if outcome is None:
            continue
        change = cells[1].strip()
        previous = decisions.get(change)
        if previous is None or (moment, index) >= previous[0]:
            decisions[change] = ((moment, index), outcome)

    amendments = []
    for line in read_lines(os.path.join(data_dir, "cr_export.jsonl")):
        line = line.strip()
        if not line:
            continue
        doc = json.loads(line)
        change = doc["change"]
        status = normalise_name(doc["status"])
        if change in decisions:
            status = decisions[change][1]
        if status != "approved":
            continue
        field = doc["field"]
        if "value" in doc:
            value = doc["value"]
        else:
            ref = doc["value_ref"]
            if ref not in drafts:
                continue
            field, value = drafts[ref]
        prop = catalog.name_of(doc["property"])
        if prop is None:
            continue
        scope = normalise_name(doc["scope"])
        entry = {
            "id": change,
            "scope": scope,
            "field": field,
            "value": normalise_value(field, value),
            "property": prop,
            "effective": parse_instant(doc["effective"]),
        }
        if scope == "class":
            entry["class"] = normalise_name(doc["target"])
            entry["node_id"] = None
        else:
            entry["class"] = None
            entry["node_id"] = ident.resolve(doc["target"])
        amendments.append(entry)
    amendments.sort(key=lambda a: (a["effective"], a["id"]))
    return amendments


def normalise_value(field, value):
    if field == "versions":
        return int(value)
    if field == "refresh":
        return normalise_name(value)
    if field in ("store_compressed", "hot_raw"):
        if isinstance(value, bool):
            return value
        return normalise_name(value) in ("on", "true", "yes", "1")
    return normalise_name(value)


# ---------------------------------------------------------------------------
# sweeper schedules
# ---------------------------------------------------------------------------

def cron_interval(fields):
    """Classify a cron schedule as hourly, daily or weekly."""
    if fields.startswith("@"):
        token = fields[1:].lower()
        if token == "hourly":
            return "hourly"
        if token in ("daily", "midnight"):
            return "daily"
        return "weekly"
    parts = fields.split()
    if len(parts) != 5:
        return "weekly"
    minute, hour, dom, month, dow = parts
    every = {"*", "*/1"}
    if dom in every and month in every and dow in every:
        if hour in every:
            return "hourly"
        return "daily"
    return "weekly"


def load_sweep_intervals(data_dir, ident):
    intervals = {}
    for line in read_lines(os.path.join(data_dir, "sweeper.crontab")):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if SWEEP_BINARY not in text:
            continue
        head, _, command = text.partition(SWEEP_BINARY)
        args = command.split()
        if "--dry-run" in args:
            continue
        if SWEEP_CONF not in args:
            continue
        head_parts = head.split()
        if len(head_parts) < 3:
            continue
        node = ident.resolve(head_parts[0])
        schedule = " ".join(head_parts[1:-1])
        interval = cron_interval(schedule)
        current = intervals.get(node)
        if current is None or REFRESH_RANK[interval] < REFRESH_RANK[current]:
            intervals[node] = interval
    return intervals


# ---------------------------------------------------------------------------
# compression ratios
# ---------------------------------------------------------------------------

def load_ratios(data_dir):
    sums = {}
    counts = {}
    for row in read_csv_rows(os.path.join(data_dir, "codec_bench.csv")):
        if normalise_name(row["status"]) != "ok":
            continue
        if normalise_name(row["corpus"]) != BENCH_CORPUS:
            continue
        codec = canonical_codec(row["codec"])
        level = normalise_name(row["level"]).lstrip("q")
        key = (normalise_name(row["content_type"]), codec, int(level))
        ratio = Fraction(int(row["in_bytes"]), int(row["out_bytes"]))
        sums[key] = sums.get(key, Fraction(0)) + ratio
        counts[key] = counts.get(key, 0) + 1
    out = {}
    for key, total in sums.items():
        out[key] = Fraction(half_even(total / counts[key] * 100), 100)
    return out


# ---------------------------------------------------------------------------
# disk geometry and usage
# ---------------------------------------------------------------------------

def load_geometry(data_dir, ident):
    history = {}
    for index, line in enumerate(read_lines(os.path.join(data_dir, "blkdev_audit.tsv"))):
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 7 or parts[0] == "audited":
            continue
        audited, node_ref, mount, media, bsize, blocks, reserve = parts[:7]
        if mount.strip() != CACHE_MOUNT:
            continue
        node = ident.resolve(node_ref)
        history.setdefault(node, []).append(
            (parse_instant(audited), index,
             (normalise_name(media), bsize.strip(), int(blocks), reserve.strip())))
    geometry = {}
    for node, records in history.items():
        row = latest_at_cut(records)
        if row is None:
            continue
        media, bsize_text, blocks, reserve = row
        m = re.fullmatch(r"(\d+)([kK]?)", bsize_text)
        block_size = int(m.group(1)) * (1024 if m.group(2) else 1)
        if media == "sata":
            reserved = 0
        elif reserve == "-":
            reserved = blocks * NVME_DEFAULT_RESERVE_PCT // 100
        elif reserve.startswith("rb="):
            reserved = int(reserve[3:])
        elif reserve.startswith("op="):
            reserved = blocks * int(reserve[3:]) // 100
        else:
            reserved = 0
        geometry[node] = {
            "media": media,
            "usable_bytes": (blocks - reserved) * block_size,
        }
    return geometry


def _df_used_bytes(line, mode):
    parts = line.split()
    if len(parts) < 6 or parts[-1] != CACHE_MOUNT:
        return None
    used = parts[2]
    if mode == "h":
        return floor_div(parse_binary_size(used))
    return int(to_fraction(used)) * 1024


def load_usage(data_dir, ident):
    snapshots = {}
    order = 0
    for name in USAGE_FILES:
        node = None
        moment = None
        mode = None
        used = None
        for line in read_lines(os.path.join(data_dir, name)):
            if line.startswith("=== node="):
                if node is not None and used is not None:
                    snapshots.setdefault(node, []).append((moment, order, used))
                    order += 1
                m = re.match(r"=== node=(\S+)\s+at=(\S+)\s+cmd=df\s+-(\w)", line.strip())
                if not m:
                    node = None
                    continue
                node = ident.resolve(m.group(1))
                moment = parse_instant(m.group(2))
                mode = m.group(3)
                used = None
                continue
            if node is None or line.startswith("#") or line.startswith("---"):
                continue
            value = _df_used_bytes(line, mode)
            if value is not None:
                used = value
        if node is not None and used is not None:
            snapshots.setdefault(node, []).append((moment, order, used))
            order += 1
    base = {}
    post = {}
    for node, records in snapshots.items():
        before = [r for r in records if r[0] <= CUT]
        after = [r for r in records if r[0] > CUT]
        if before:
            base[node] = max(before, key=lambda r: (r[0], r[1]))[2]
        if after:
            post[node] = min(after, key=lambda r: (r[0], r[1]))[2]
    return base, post


def load_prior_peaks(data_dir, ident):
    totals = {}
    for row in read_csv_rows(os.path.join(data_dir, "optplan_prev.csv")):
        if normalise_name(row["run_id"]) != "q2-final":
            continue
        node = ident.resolve(row["node_ref"])
        text = row["peak_kib"].strip()
        m = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*(kib|mib)?", text, re.I)
        if not m:
            continue
        value = to_fraction(m.group(1))
        if m.group(2) and m.group(2).lower() == "mib":
            value *= 1024
        totals[node] = totals.get(node, Fraction(0)) + value
    return {node: half_even(value) for node, value in totals.items()}


# ---------------------------------------------------------------------------
# exporter targets and counter readings
# ---------------------------------------------------------------------------

def load_targets(data_dir, ident, catalog):
    with open(os.path.join(data_dir, "scrape_targets.toml"), "rb") as handle:
        doc = tomllib.load(handle)
    excluded = set()
    for entry in json.loads(read_text(os.path.join(data_dir, "mirror_twins.json"))):
        excluded.add(entry["mirror_instance"].strip())
    for line in read_lines(os.path.join(data_dir, "labnodes.tsv")):
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 3 or parts[0] == "registered":
            continue
        excluded.add(parts[1].strip())
    with open(os.path.join(data_dir, "stg_jobs.toml"), "rb") as handle:
        stg_doc = tomllib.load(handle)
    staging = set()
    for body in stg_doc.get("scrape", {}).values():
        staging.add((body["job"].strip(), body["instance"].strip()))

    targets = {}
    for tid, body in sorted(doc.get("targets", {}).items()):
        instance = body["instance"].strip()
        if instance in excluded:
            continue
        node = ident.resolve(body["node"])
        prop = catalog.name_of(body["property"])
        if prop is None:
            continue
        unit = normalise_name(body.get("counter_unit", "bytes"))
        factor = 1024 if unit == "kib" else 1
        key = (node, prop)
        if key not in targets:
            targets[key] = {"instance": instance, "factor": factor}
    return targets, excluded, staging


_PROM_RE = re.compile(r"^(\w+)\{([^}]*)\}\s+(\S+)\s+(\S+)\s*$")
_LABEL_RE = re.compile(r'(\w+)="([^"]*)"')
_XML_RE = re.compile(r"<s\s+([^/>]*)/>")
_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')
_COLLD_RE = re.compile(r"^(\S+)\s+sample\s+(.*)$")
_SQL_SAMPLE_RE = re.compile(
    r"VALUES\s*\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*"
    r"(NULL|'[^']*')\s*,\s*'([^']*)'\s*,\s*([0-9.eE+-]+)\s*\)")
_TR_RE = re.compile(r"<tr>(.*?)</tr>", re.S)
_TD_RE = re.compile(r"<td>(.*?)</td>", re.S)


def iter_raw_readings(path, name):
    """Yield (node_ref, prop_ref, instance, job, pop, instant_text, value_text)."""
    if name.endswith(".prom"):
        for line in read_lines(path):
            m = _PROM_RE.match(line)
            if not m:
                continue
            labels = dict(_LABEL_RE.findall(m.group(2)))
            yield (labels.get("node", ""), labels.get("prop", ""),
                   labels.get("instance", ""), labels.get("job", ""),
                   labels.get("pop"), m.group(4), m.group(3))
    elif name.endswith(".xml"):
        for m in _XML_RE.finditer(read_text(path)):
            attrs = dict(_ATTR_RE.findall(m.group(1)))
            yield (attrs.get("n", ""), attrs.get("p", ""), attrs.get("i", ""),
                   attrs.get("j", ""), attrs.get("pop"), attrs.get("t", ""),
                   attrs.get("v", ""))
    elif name.endswith(".ndjson"):
        for line in read_lines(path):
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            yield (doc.get("node", ""), doc.get("prop", ""), doc.get("inst", ""),
                   doc.get("job", ""), doc.get("pop"), doc.get("t"), doc.get("v"))
    elif name.endswith(".jsonl"):
        for line in read_lines(path):
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            labels = doc.get("labels", {})
            yield (labels.get("node", ""), labels.get("prop", ""),
                   labels.get("instance", ""), labels.get("job", ""),
                   labels.get("pop"), doc.get("ts"), doc.get("value"))
    elif name.endswith(".log"):
        for line in read_lines(path):
            m = _COLLD_RE.match(line.strip())
            if not m:
                continue
            fields = {}
            for token in m.group(2).split():
                key, _, value = token.partition("=")
                fields[key] = value
            yield (fields.get("node", ""), fields.get("prop", ""),
                   fields.get("inst", ""), fields.get("job", ""),
                   fields.get("pop"), m.group(1), fields.get("v", ""))
    elif name.endswith(".sql"):
        for line in read_lines(path):
            m = _SQL_SAMPLE_RE.search(line)
            if not m:
                continue
            pop = None if m.group(5) == "NULL" else m.group(5).strip("'")
            yield (m.group(1), m.group(2), m.group(3), m.group(4), pop,
                   m.group(6), m.group(7))
    elif name.endswith(".html"):
        for m in _TR_RE.finditer(read_text(path)):
            cells = [c.strip() for c in _TD_RE.findall(m.group(1))]
            if len(cells) < 7:
                continue
            yield (cells[0], cells[1], cells[2], cells[3],
                   cells[4] or None, cells[5], cells[6])
    elif name.endswith(".tsv"):
        rows = read_text(path).splitlines()
        if not rows:
            return
        header = rows[0].split("\t")
        index = {h: i for i, h in enumerate(header)}
        for row in rows[1:]:
            if not row.strip():
                continue
            cells = row.split("\t")
            if len(cells) < len(header):
                continue
            yield (cells[index["node"]], cells[index["path"]],
                   cells[index["instance"]], cells[index["job"]],
                   cells[index["pop"]] or None, cells[index["ts"]],
                   cells[index["value"]])
    elif name.endswith(".csv"):
        for row in read_csv_rows(path):
            yield (row["node"], row["property"], row["instance"], row["job"],
                   row["pop"] or None, row["timestamp"], row["value"])
    else:
        raise ValueError("unknown counter format: %s" % name)


def _value_key(text):
    return str(to_fraction(text))


def load_replay_keys(data_dir, ident, catalog):
    keys = set()
    for line in read_lines(os.path.join(data_dir, "replay_inject_q3.prom")):
        m = _PROM_RE.match(line)
        if not m:
            continue
        labels = dict(_LABEL_RE.findall(m.group(2)))
        node = ident.resolve(labels.get("node", ""), labels.get("pop"))
        prop = catalog.resolve(labels.get("prop", ""), node)
        if prop is None:
            continue
        instant = parse_instant(m.group(4))
        keys.add((node, prop, labels.get("instance", ""), instant,
                  _value_key(m.group(3))))
    return keys


def load_counters(data_dir, ident, catalog, targets, pop_of, pops, excluded, staging,
                  replay_keys):
    """Kept in-window readings per (node, property), already in bytes."""
    wanted = {}
    for (node, prop), target in targets.items():
        wanted[(node, prop, target["instance"])] = target["factor"]
    series = {}
    for name in COUNTER_FILES:
        path = os.path.join(data_dir, name)
        for node_ref, prop_ref, instance, job, pop, ts_text, value_text in \
                iter_raw_readings(path, name):
            instance = (instance or "").strip()
            if not instance or instance in excluded:
                continue
            if (job or "").strip() and ((job.strip(), instance) in staging):
                continue
            node = ident.resolve(node_ref, pop)
            prop = catalog.resolve(prop_ref, node)
            if prop is None:
                continue
            key = (node, prop, instance)
            factor = wanted.get(key)
            if factor is None:
                continue
            pop_code = pop_of.get(node)
            offset = pops[pop_code]["utc_offset_minutes"] if pop_code in pops else 0
            instant = parse_instant(ts_text, offset)
            if instant < WINDOW_START or instant > CUT:
                continue
            raw = _value_key(value_text)
            if (node, prop, instance, instant, raw) in replay_keys:
                continue
            series.setdefault((node, prop), {})[
                (instance, (job or "").strip(), instant)] = (
                    int(to_fraction(value_text)) * factor)
    out = {}
    for key, readings in series.items():
        points = sorted((instant, value) for (_, _, instant), value in readings.items())
        out[key] = points
    return out


def daily_bytes_of(points):
    if len(points) < 2:
        return None
    increase = 0
    for (_, previous), (_, current) in zip(points, points[1:]):
        increase += current - previous if current >= previous else current
    span = (points[-1][0] - points[0][0]).total_seconds()
    if span <= 0:
        return None
    return half_even(Fraction(increase) * 86400 / Fraction(span).limit_denominator(10 ** 9))


# ---------------------------------------------------------------------------
# footprints
# ---------------------------------------------------------------------------

def footprint(daily, effective_refresh, ratio, versions, store_compressed, hot_raw):
    cycle = half_even(Fraction(daily) * CYCLE_FACTOR[effective_refresh])
    generation = ceil_frac(Fraction(cycle) / ratio)
    hot = cycle if (not store_compressed or hot_raw) else generation
    stale = (versions - 1) * (generation if store_compressed else cycle)
    peak = hot + stale + cycle
    return {
        "cycle_bytes": cycle,
        "hot_kib": half_even(Fraction(hot, 1024)),
        "stale_kib": half_even(Fraction(stale, 1024)),
        "peak_kib": half_even(Fraction(peak, 1024)),
    }


# ---------------------------------------------------------------------------
# output helpers
# ---------------------------------------------------------------------------

def write_outputs(out_dir, files):
    os.makedirs(out_dir, exist_ok=True)
    for name, payload in sorted(files.items()):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="") as fh:
            fh.write(payload)


def render_csv(name, rows):
    lines = [HEADERS[name]]
    lines.extend(",".join(row) for row in rows)
    return "\n".join(lines) + "\n"


def render_json(obj):
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def sha256_file(path):
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError as exc:
        raise UpstreamError(path) from exc


# ---------------------------------------------------------------------------
# phase 1
# ---------------------------------------------------------------------------

def phase1(data_dir, out_dir):
    require_files(data_dir, BASE_INPUT_FILES + COUNTER_FILES + USAGE_FILES)

    pops, pop_canon, placements = load_pops(data_dir)
    ident = load_identity(data_dir, pop_canon)
    catalog = PropertyCatalog(data_dir, ident)
    config = CacheConfig(data_dir, ident)

    placement_hist = {}
    for entry in placements:
        if entry["state"] != "installed":
            continue
        node = ident.resolve(entry["node_ref"])
        placement_hist.setdefault(node, []).append(
            (entry["since"], entry["id"], entry["pop"]))
    pop_of = {}
    for node, records in placement_hist.items():
        best = None
        for moment, pid, code in records:
            if moment > CUT:
                continue
            if best is None or (moment, pid) >= (best[0], best[1]):
                best = (moment, pid, code)
        if best is not None:
            pop_of[node] = best[2]

    status_of = load_asset_status(data_dir, ident)
    class_of = load_classes(data_dir, ident)
    class_default_tier, node_tier = load_tiers(data_dir, ident)
    decommissioned = load_decommissions(data_dir, ident)
    targets, excluded, staging = load_targets(data_dir, ident, catalog)

    prop_changes = {}
    for index, row in enumerate(read_csv_rows(os.path.join(data_dir, "prop_changes.csv"))):
        node = ident.resolve(row["node_ref"])
        prop = catalog.name_of(row["property"])
        if prop is None:
            continue
        moment = parse_instant(row["effective"])
        prop_changes.setdefault((node, prop), []).append(
            (moment, index, normalise_name(row["action"])))

    served_by = {}
    for key, records in prop_changes.items():
        action = latest_at_cut(records)
        if action is not None:
            served_by[key] = action

    candidates = sorted(set(status_of) | set(class_of) | set(pop_of))
    nodes = []
    for node in candidates:
        if node not in pop_of or pops.get(pop_of[node], {}).get("scope") != "prod":
            continue
        row = status_of.get(node)
        if row is None or row[0] not in ACTIVE_STATUSES:
            continue
        if node in decommissioned:
            continue
        hw_class = class_of.get(node)
        if hw_class is None or hw_class == "retired":
            continue
        tier = node_tier.get(node, class_default_tier.get(hw_class))
        if tier is None or tier == "x":
            continue
        template = []
        for path, _ in config.class_locations.get(hw_class, []):
            prop = catalog.catalog_by_path.get(path)
            if prop is not None and prop not in template:
                template.append(prop)
        properties = set(template)
        for prop in sorted(set(template) | {p for (n, p) in served_by if n == node}):
            action = served_by.get((node, prop))
            if action == "add":
                properties.add(prop)
            elif action == "remove":
                properties.discard(prop)
        properties = sorted(p for p in properties if (node, p) in targets)
        if not properties:
            continue
        nodes.append({
            "node_id": node,
            "pop": pop_of[node],
            "class": hw_class,
            "tier": tier,
            "ram_bytes": floor_div(parse_binary_size(row[1])),
            "properties": properties,
        })

    node_index = {n["node_id"]: n for n in nodes}
    in_scope = set(node_index)

    amendments = load_amendments(data_dir, ident, catalog)
    class_members = {}
    for node in nodes:
        class_members.setdefault(node["class"], []).append(node["node_id"])

    kept_amendments = []
    for entry in amendments:
        if entry["scope"] == "node":
            node = entry["node_id"]
            if node not in in_scope:
                continue
            if entry["property"] not in node_index[node]["properties"]:
                continue
        else:
            members = class_members.get(entry["class"], [])
            if not any(entry["property"] in node_index[m]["properties"] for m in members):
                continue
        kept_amendments.append(entry)

    frozen = [a for a in kept_amendments if a["effective"] <= CUT]
    pending = [a for a in kept_amendments if a["effective"] > CUT]

    class_amendments = {}
    node_amendments = {}
    for entry in frozen:
        if entry["scope"] == "class":
            class_amendments.setdefault((entry["class"], entry["property"]), []).append(entry)
        else:
            node_amendments.setdefault((entry["node_id"], entry["property"]), []).append(entry)

    sweep_of = load_sweep_intervals(data_dir, ident)
    ratios = load_ratios(data_dir)
    geometry = load_geometry(data_dir, ident)
    base_used, post_used = load_usage(data_dir, ident)
    prior_peaks = load_prior_peaks(data_dir, ident)
    replay_keys = load_replay_keys(data_dir, ident, catalog)
    pair_targets = {k: v for k, v in targets.items() if k[0] in in_scope}
    counters = load_counters(data_dir, ident, catalog, pair_targets, pop_of, pops,
                             excluded, staging, replay_keys)

    node_rows = []
    prop_rows = []
    policy_rows = []
    foot_rows = []
    for node in nodes:
        nid = node["node_id"]
        geo = geometry.get(nid, {"media": "", "usable_bytes": 0})
        sweep = sweep_of.get(nid, "daily")
        node["sweep_interval"] = sweep
        node_rows.append([
            nid, node["pop"], node["class"], node["tier"], geo["media"],
            fmt_int(geo["usable_bytes"]), fmt_int(base_used.get(nid, 0)),
            fmt_int(post_used.get(nid)), fmt_int(prior_peaks.get(nid)),
            sweep, fmt_int(node["ram_bytes"]),
        ])
        node_prop_paths = {catalog.path_for(nid, p): p for p in node["properties"]}
        for prop in node["properties"]:
            target = targets[(nid, prop)]
            points = counters.get((nid, prop), [])
            daily = daily_bytes_of(points)
            prop_rows.append([nid, prop, target["instance"], str(len(points)),
                              fmt_int(daily)])

            policy = {"versions": 1, "refresh": "weekly", "store_compressed": False,
                      "hot_raw": False, "codec": "gzip", "codec_level": 6}
            apply_layer(policy, config.global_directives)
            catalog_path = catalog.catalog.get(prop)
            for path, directives in config.class_locations.get(node["class"], []):
                if path == catalog_path:
                    apply_layer(policy, directives)
            for entry in class_amendments.get((node["class"], prop), []):
                apply_amendment(policy, entry["field"], entry["value"])
            node_path = catalog.path_for(nid, prop)
            for path, directives in config.node_blocks.get(nid, []):
                if path == node_path and node_prop_paths.get(path) == prop:
                    apply_layer(policy, directives)
            for entry in node_amendments.get((nid, prop), []):
                apply_amendment(policy, entry["field"], entry["value"])

            effective = policy["refresh"]
            if REFRESH_RANK[sweep] > REFRESH_RANK[effective]:
                effective = sweep
            codec_text = "%s:%d" % (policy["codec"], policy["codec_level"])
            content_type = catalog.types.get(prop, "")
            ratio = ratios.get((content_type, policy["codec"], policy["codec_level"]))
            if ratio is None:
                ratio = Fraction(1)
            policy_rows.append([
                nid, prop, str(policy["versions"]), policy["refresh"], effective,
                "1" if policy["store_compressed"] else "0",
                "1" if policy["hot_raw"] else "0", codec_text, fmt_dec(ratio, 2),
            ])
            if daily is None:
                foot_rows.append([nid, prop, "", "", "", ""])
            else:
                shape = footprint(daily, effective, ratio, policy["versions"],
                                  policy["store_compressed"], policy["hot_raw"])
                foot_rows.append([
                    nid, prop, fmt_int(shape["cycle_bytes"]), fmt_int(shape["hot_kib"]),
                    fmt_int(shape["stale_kib"]), fmt_int(shape["peak_kib"]),
                ])

    pending_json = {
        "freeze_utc": fmt_instant(CUT),
        "amendments": [
            {
                "id": entry["id"],
                "scope": entry["scope"],
                "node_id": entry["node_id"],
                "class": entry["class"],
                "property": entry["property"],
                "field": entry["field"],
                "value": entry["value"],
                "effective_utc": fmt_instant(entry["effective"]),
            }
            for entry in pending
        ],
    }

    pop_entries = []
    for code in sorted(p for p, body in pops.items() if body["scope"] == "prod"):
        body = pops[code]
        members = [n for n in nodes if n["pop"] == code]
        pin_budget = sum(
            floor_div(Fraction(n["ram_bytes"], 1024) * body["ram_pin_pct"] / 100)
            for n in members)
        pop_entries.append({
            "pop": code,
            "utc_offset_minutes": body["utc_offset_minutes"],
            "shield_pool_kib": half_even(body["shield_pool_bytes"] / 1024),
            "ticket_quota": body["ticket_quota"],
            "spill_budget_kib": half_even(body["spill_budget_bytes"] / 1024),
            "ram_pin_pct": body["ram_pin_pct"],
            "pin_budget_kib": pin_budget,
            "nodes": len(members),
        })

    write_outputs(out_dir, {
        "nodes.csv": render_csv("nodes.csv", node_rows),
        "properties.csv": render_csv("properties.csv", prop_rows),
        "policies.csv": render_csv("policies.csv", policy_rows),
        "footprints.csv": render_csv("footprints.csv", foot_rows),
        "pending.json": render_json(pending_json),
        "pops.json": render_json({"pops": pop_entries}),
    })


# ---------------------------------------------------------------------------
# upstream loading for phases 2 and 3
# ---------------------------------------------------------------------------

def load_csv_strict(path, name):
    text = read_text(path)
    lines = text.split("\n")
    if not lines or lines[0] != HEADERS[name]:
        raise UpstreamError(path)
    fields = HEADERS[name].split(",")
    rows = []
    for line in lines[1:]:
        if line == "":
            continue
        cells = line.split(",")
        if len(cells) != len(fields):
            raise UpstreamError(path)
        rows.append(dict(zip(fields, cells)))
    return rows


def opt_int(text):
    return None if text == "" else int(text)


class Phase1Data:
    """The six phase 1 files, parsed back into memory."""

    def __init__(self, p1_dir):
        require_files(p1_dir, P1_FILES)
        self.dir = p1_dir
        self.nodes = load_csv_strict(os.path.join(p1_dir, "nodes.csv"), "nodes.csv")
        self.properties = load_csv_strict(
            os.path.join(p1_dir, "properties.csv"), "properties.csv")
        self.policies = load_csv_strict(
            os.path.join(p1_dir, "policies.csv"), "policies.csv")
        self.footprints = load_csv_strict(
            os.path.join(p1_dir, "footprints.csv"), "footprints.csv")
        try:
            self.pending = json.loads(read_text(os.path.join(p1_dir, "pending.json")))
            self.pops = json.loads(read_text(os.path.join(p1_dir, "pops.json")))["pops"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise UpstreamError(p1_dir) from exc

        self.node_order = [row["node_id"] for row in self.nodes]
        self.node = {row["node_id"]: row for row in self.nodes}
        self.pop = {row["pop"]: row for row in self.pops}
        self.pop_order = [row["pop"] for row in self.pops]

        if len(self.properties) != len(self.policies) or \
                len(self.properties) != len(self.footprints):
            raise UpstreamError(p1_dir)
        self.pairs = []
        for prop, policy, foot in zip(self.properties, self.policies, self.footprints):
            key = (prop["node_id"], prop["property"])
            if key != (policy["node_id"], policy["property"]) or \
                    key != (foot["node_id"], foot["property"]):
                raise UpstreamError(p1_dir)
            self.pairs.append({
                "node_id": key[0],
                "property": key[1],
                "instance": prop["instance"],
                "samples": int(prop["samples"]),
                "daily_bytes": opt_int(prop["daily_bytes"]),
                "versions": int(policy["versions"]),
                "refresh": policy["refresh"],
                "effective_refresh": policy["effective_refresh"],
                "store_compressed": policy["store_compressed"] == "1",
                "hot_raw": policy["hot_raw"] == "1",
                "codec": policy["codec"],
                "ratio": to_fraction(policy["ratio"]),
                "cycle_bytes": opt_int(foot["cycle_bytes"]),
                "hot_kib": opt_int(foot["hot_kib"]),
                "stale_kib": opt_int(foot["stale_kib"]),
                "peak_kib": opt_int(foot["peak_kib"]),
            })
        self.pairs_by_node = {}
        for pair in self.pairs:
            self.pairs_by_node.setdefault(pair["node_id"], []).append(pair)

        self.metrics = {}
        for row in self.nodes:
            nid = row["node_id"]
            pairs = self.pairs_by_node.get(nid, [])
            peak = sum(p["peak_kib"] for p in pairs if p["peak_kib"] is not None)
            measured = [p for p in pairs if p["daily_bytes"] is not None]
            daily_bytes = sum(p["daily_bytes"] for p in measured) if measured else None
            usable_kib = half_even(Fraction(int(row["usable_bytes"]), 1024))
            base_kib = half_even(Fraction(int(row["base_used_bytes"]), 1024))
            ram_kib = half_even(Fraction(int(row["ram_bytes"]), 1024))
            post = opt_int(row["post_cut_used_bytes"])
            self.metrics[nid] = {
                "node_id": nid,
                "pop": row["pop"],
                "class": row["class"],
                "tier": row["tier"],
                "sweep_interval": row["sweep_interval"],
                "usable_kib": usable_kib,
                "base_kib": base_kib,
                "ram_kib": ram_kib,
                "post_cut_kib": None if post is None else half_even(Fraction(post, 1024)),
                "prior_peak_kib": opt_int(row["prior_peak_kib"]),
                "peak": peak,
                "daily_bytes": daily_bytes,
                "daily_kib": None if daily_bytes is None else
                             half_even(Fraction(daily_bytes, 1024)),
                "headroom": usable_kib - base_kib - peak,
            }

        self.affected = set()
        self.amendment_pairs = {}
        for entry in self.pending["amendments"]:
            hits = set()
            for pair in self.pairs:
                node = self.node[pair["node_id"]]
                if pair["property"] != entry["property"]:
                    continue
                if entry["scope"] == "node":
                    if pair["node_id"] == entry["node_id"]:
                        hits.add((pair["node_id"], pair["property"]))
                elif node["class"] == entry["class"]:
                    hits.add((pair["node_id"], pair["property"]))
            self.amendment_pairs[entry["id"]] = hits
            self.affected |= hits
        self.pending_nodes = {nid for nid, _ in self.affected}

    def digests(self):
        return {name: sha256_file(os.path.join(self.dir, name)) for name in P1_FILES}


def days_to_full(headroom, daily_kib):
    """Return (text, exact value or None, kind) following the risk rank rules."""
    if daily_kib is None:
        return "", None, "empty"
    if daily_kib == 0:
        return "never", None, "never"
    if headroom <= 0:
        return "0.00", Fraction(0), "numeric"
    exact = Fraction(headroom, daily_kib)
    return fmt_dec(exact, 2), exact, "numeric"


def local_date(days, offset_minutes):
    seconds = Fraction(int(CUT.timestamp())) + days * 86400 + offset_minutes * 60
    day_number = floor_div(seconds / 86400)
    return (date(1970, 1, 1) + timedelta(days=day_number)).isoformat()


def shield_order_key(data, nid):
    node = data.metrics[nid]
    return (int(node["tier"]), 1 if nid in data.pending_nodes else 0,
            data.node_order.index(nid))


# ---------------------------------------------------------------------------
# phase 2
# ---------------------------------------------------------------------------

def compute_shield_alloc(data):
    rows = []
    grants = {}
    for code in data.pop_order:
        members = [n for n in data.node_order if data.metrics[n]["pop"] == code]
        members.sort(key=lambda nid: shield_order_key(data, nid))
        remaining = data.pop[code]["shield_pool_kib"]
        running = 0
        for nid in members:
            pairs = data.pairs_by_node.get(nid, [])
            measured = [p for p in pairs if p["daily_bytes"] is not None]
            if not measured:
                demand, granted, state = 0, 0, "unmeasured"
            else:
                demand = sum(p["stale_kib"] for p in pairs
                             if p["store_compressed"] and p["stale_kib"] is not None)
                granted = min(demand, remaining)
                if demand == 0:
                    state = "zero"
                elif granted == demand:
                    state = "full"
                elif granted > 0:
                    state = "partial"
                else:
                    state = "none"
            remaining -= granted
            running += granted
            grants[nid] = granted
            rows.append([nid, code, str(demand), str(granted), str(running), state])
    return rows, grants


def compute_pin_plan(data):
    rows = []
    pinned_kib = {}
    for nid in data.node_order:
        node = data.metrics[nid]
        pct = data.pop[node["pop"]]["ram_pin_pct"]
        budget = floor_div(node["ram_kib"] * pct / 100)
        candidates = [
            p for p in data.pairs_by_node.get(nid, [])
            if p["daily_bytes"] is not None
            and p["effective_refresh"] != "hourly"
            and (nid, p["property"]) not in data.affected
        ]
        zero = sorted((p for p in candidates if p["hot_kib"] == 0),
                      key=lambda p: p["property"])
        rest = sorted((p for p in candidates if p["hot_kib"] != 0),
                      key=lambda p: (-Fraction(p["daily_bytes"], p["hot_kib"]),
                                     p["property"]))
        used = 0
        for pair in zero + rest:
            hot = pair["hot_kib"]
            if used + hot <= budget:
                used += hot
                flag = "1"
            else:
                flag = "0"
            density = "" if hot == 0 else fmt_dec(Fraction(pair["daily_bytes"], hot), 2)
            rows.append([nid, pair["property"], density, str(hot), str(used), flag])
        pinned_kib[nid] = used
    return rows, pinned_kib


def compute_risk_rank(data, pinned_kib):
    entries = []
    for nid in data.node_order:
        node = data.metrics[nid]
        text, exact, kind = days_to_full(node["headroom"], node["daily_kib"])
        hot_total = sum(p["hot_kib"] for p in data.pairs_by_node.get(nid, [])
                        if p["hot_kib"] is not None)
        share = "" if hot_total == 0 else \
            fmt_dec(Fraction(pinned_kib.get(nid, 0), hot_total), 4)
        full_date = ""
        if kind == "numeric":
            full_date = local_date(exact, data.pop[node["pop"]]["utc_offset_minutes"])
        entries.append({
            "node_id": nid,
            "pop": node["pop"],
            "headroom": node["headroom"],
            "daily_kib": node["daily_kib"],
            "days_text": text,
            "days_exact": exact,
            "kind": kind,
            "full_date": full_date,
            "pin_share": share,
            "pending": "1" if nid in data.pending_nodes else "0",
        })
    kind_rank = {"numeric": 0, "never": 1, "empty": 2}
    entries.sort(key=lambda e: (kind_rank[e["kind"]],
                                e["days_exact"] if e["kind"] == "numeric" else 0,
                                e["node_id"]))
    rows = []
    for position, entry in enumerate(entries, start=1):
        entry["rank"] = position
        rows.append([
            entry["node_id"], entry["pop"], str(entry["headroom"]),
            fmt_int(entry["daily_kib"]), entry["days_text"], entry["full_date"],
            entry["pin_share"], entry["pending"], str(position),
        ])
    return rows, entries


def compute_pop_rollup(data):
    rows = []
    for code in data.pop_order:
        members = [n for n in data.node_order if data.metrics[n]["pop"] == code]
        pairs = [p for n in members for p in data.pairs_by_node.get(n, [])]
        measured = sum(1 for p in pairs if p["daily_bytes"] is not None)
        peak_kib = sum(p["peak_kib"] for p in pairs if p["peak_kib"] is not None)
        usable = sum(data.metrics[n]["usable_kib"] for n in members)
        headroom = sum(data.metrics[n]["headroom"] for n in members)
        rows.append([
            code, str(len(members)), str(measured), str(len(pairs) - measured),
            str(sum(1 for p in pairs if p["store_compressed"])),
            str(half_even(Fraction(peak_kib, 1024))),
            str(half_even(Fraction(usable, 1024))),
            str(half_even(Fraction(headroom, 1024))),
            str(sum(1 for n in members if n in data.pending_nodes)),
            str(half_even(Fraction(data.pop[code]["shield_pool_kib"], 1024))),
        ])
    return rows


def class_peak_by_pop(data, peak_of):
    totals = {}
    for nid in data.node_order:
        node = data.metrics[nid]
        totals.setdefault(node["pop"], {})
        totals[node["pop"]][node["class"]] = \
            totals[node["pop"]].get(node["class"], 0) + peak_of(nid)
    return totals


def shield_share(data, peak_of, class_name):
    totals = class_peak_by_pop(data, peak_of)
    total = Fraction(0)
    for code in data.pop_order:
        by_class = totals.get(code, {})
        pop_peak = sum(by_class.values())
        if pop_peak <= 0:
            continue
        share = Fraction(by_class.get(class_name, 0), pop_peak)
        total += Fraction(data.pop[code]["shield_pool_kib"]) * share
    return total


def compute_class_rollup(data):
    classes = sorted({data.metrics[n]["class"] for n in data.node_order})
    rows = []
    for name in classes:
        members = [n for n in data.node_order if data.metrics[n]["class"] == name]
        pairs = [p for n in members for p in data.pairs_by_node.get(n, [])]
        measured = [p for p in pairs if p["daily_bytes"] is not None]
        daily = "" if not measured else str(half_even(
            Fraction(sum(p["daily_bytes"] for p in measured), 1048576)))
        compressed = [p for p in pairs if p["store_compressed"]]
        mean_ratio = "" if not compressed else fmt_dec(
            sum(p["ratio"] for p in compressed) / len(compressed), 3)
        peak = sum(data.metrics[n]["peak"] for n in members)
        pending_pairs = sum(1 for p in pairs
                            if (p["node_id"], p["property"]) in data.affected)
        share = shield_share(data, lambda nid: data.metrics[nid]["peak"], name)
        rows.append([
            name, str(len(members)),
            str(len({data.metrics[n]["pop"] for n in members})),
            daily, mean_ratio, str(half_even(Fraction(peak, 1024))),
            str(pending_pairs), str(half_even(share / 1024)),
        ])
    return rows, classes


def phase2(p1_dir, out_dir):
    data = Phase1Data(p1_dir)
    pop_rows = compute_pop_rollup(data)
    class_rows, _ = compute_class_rollup(data)
    shield_rows, _ = compute_shield_alloc(data)
    pin_rows, pinned_kib = compute_pin_plan(data)
    risk_rows, risk_entries = compute_risk_rank(data, pinned_kib)

    numeric = sorted(e["days_exact"] for e in risk_entries if e["kind"] == "numeric")
    if numeric:
        middle = len(numeric) // 2
        median = numeric[middle] if len(numeric) % 2 else \
            (numeric[middle - 1] + numeric[middle]) / 2
        median_text = fmt_dec(median, 2)
    else:
        median_text = None
    headrooms = sorted(data.metrics[n]["headroom"] for n in data.node_order)
    if headrooms:
        position = ceil_frac(Fraction(9, 10) * len(headrooms))
        p90 = headrooms[max(position, 1) - 1]
    else:
        p90 = None

    total_daily = sum(p["daily_bytes"] for p in data.pairs
                      if p["daily_bytes"] is not None)
    manifest = {
        "phase": 2,
        "inputs": data.digests(),
        "totals": {
            "nodes": len(data.node_order),
            "pairs_measured": sum(1 for p in data.pairs if p["daily_bytes"] is not None),
            "pairs_null": sum(1 for p in data.pairs if p["daily_bytes"] is None),
            "pairs_compressed": sum(1 for p in data.pairs if p["store_compressed"]),
            "peak_kib": sum(p["peak_kib"] for p in data.pairs
                            if p["peak_kib"] is not None),
            "daily_kib": half_even(Fraction(total_daily, 1024)),
            "pending_amendments": len(data.pending["amendments"]),
            "shield_kib": sum(p["shield_pool_kib"] for p in data.pops),
            "pinned_kib": sum(pinned_kib.values()),
        },
        "median_days_to_full": median_text,
        "p90_headroom_kib": p90,
    }

    write_outputs(out_dir, {
        "pop_rollup.csv": render_csv("pop_rollup.csv", pop_rows),
        "class_rollup.csv": render_csv("class_rollup.csv", class_rows),
        "shield_alloc.csv": render_csv("shield_alloc.csv", shield_rows),
        "pin_plan.csv": render_csv("pin_plan.csv", pin_rows),
        "risk_rank.csv": render_csv("risk_rank.csv", risk_rows),
        "manifest.json": render_json(manifest),
    })


# ---------------------------------------------------------------------------
# phase 3
# ---------------------------------------------------------------------------

class Phase2Data:
    def __init__(self, p2_dir, p1):
        require_files(p2_dir, P2_FILES)
        self.dir = p2_dir
        manifest_path = os.path.join(p2_dir, "manifest.json")
        try:
            self.manifest = json.loads(read_text(manifest_path))
        except json.JSONDecodeError as exc:
            raise UpstreamError(manifest_path) from exc
        if self.manifest.get("phase") != 2 or \
                self.manifest.get("inputs") != p1.digests():
            raise UpstreamError(manifest_path)
        self.pop_rollup = {r["pop"]: r for r in load_csv_strict(
            os.path.join(p2_dir, "pop_rollup.csv"), "pop_rollup.csv")}
        self.class_rollup = load_csv_strict(
            os.path.join(p2_dir, "class_rollup.csv"), "class_rollup.csv")
        self.shield = load_csv_strict(
            os.path.join(p2_dir, "shield_alloc.csv"), "shield_alloc.csv")
        self.pin_plan = load_csv_strict(
            os.path.join(p2_dir, "pin_plan.csv"), "pin_plan.csv")
        self.risk = {r["node_id"]: r for r in load_csv_strict(
            os.path.join(p2_dir, "risk_rank.csv"), "risk_rank.csv")}
        self.grant = {r["node_id"]: int(r["granted_kib"]) for r in self.shield}
        self.pinned = {}
        for row in self.pin_plan:
            if row["pinned"] == "1":
                self.pinned[row["node_id"]] = \
                    self.pinned.get(row["node_id"], 0) + int(row["hot_kib"])

    def digests(self):
        return {name: sha256_file(os.path.join(self.dir, name)) for name in P2_FILES}


def project_pairs(p1):
    """Peak KiB per node after the pending amendments."""
    policies = {}
    for pair in p1.pairs:
        key = (pair["node_id"], pair["property"])
        if key in p1.affected:
            policies[key] = {
                "versions": pair["versions"],
                "refresh": pair["refresh"],
                "store_compressed": pair["store_compressed"],
                "hot_raw": pair["hot_raw"],
                "codec": pair["codec"].split(":")[0],
                "codec_level": int(pair["codec"].split(":")[1]),
            }
    for entry in p1.pending["amendments"]:
        for key in sorted(p1.amendment_pairs[entry["id"]]):
            if key in policies:
                apply_amendment(policies[key], entry["field"], entry["value"])
    peak_after = {nid: 0 for nid in p1.node_order}
    for pair in p1.pairs:
        key = (pair["node_id"], pair["property"])
        sweep = p1.metrics[pair["node_id"]]["sweep_interval"]
        if key in policies and pair["daily_bytes"] is not None:
            policy = policies[key]
            effective = policy["refresh"]
            if REFRESH_RANK[sweep] > REFRESH_RANK[effective]:
                effective = sweep
            shape = footprint(pair["daily_bytes"], effective, pair["ratio"],
                              policy["versions"], policy["store_compressed"],
                              policy["hot_raw"])
            peak_after[pair["node_id"]] += shape["peak_kib"]
        elif pair["peak_kib"] is not None:
            peak_after[pair["node_id"]] += pair["peak_kib"]
    return peak_after


def phase3(p1_dir, p2_dir, out_dir):
    p1 = Phase1Data(p1_dir)
    p2 = Phase2Data(p2_dir, p1)

    peak_after = project_pairs(p1)
    median_text = p2.manifest.get("median_days_to_full")
    median = None if median_text is None else to_fraction(median_text)
    p90 = p2.manifest.get("p90_headroom_kib")

    class_peak_mib = {r["class"]: int(r["peak_mib"]) for r in p2.class_rollup}
    projection = {}
    for nid in p1.node_order:
        node = p1.metrics[nid]
        observed = node["post_cut_kib"] if node["post_cut_kib"] is not None \
            else node["base_kib"]
        after = peak_after[nid]
        headroom_after = (node["usable_kib"] - observed - after
                          + p2.grant.get(nid, 0) + p2.pinned.get(nid, 0))
        daily_text = p2.risk[nid]["daily_kib"]
        daily_kib = None if daily_text == "" else int(daily_text)
        days_text, days_exact, kind = days_to_full(headroom_after, daily_kib)
        if kind == "numeric" and median is not None and days_exact < median:
            flag = "at-risk"
        elif after > node["peak"]:
            flag = "watch"
        else:
            flag = "ok"
        pop_headroom = int(p2.pop_rollup[node["pop"]]["headroom_mib"]) * 1024
        pop_share = Fraction(headroom_after, pop_headroom) if pop_headroom > 0 else None
        class_peak = class_peak_mib.get(node["class"], 0) * 1024
        class_share = Fraction(after, class_peak) if class_peak > 0 else None
        projection[nid] = {
            "node_id": nid,
            "pop": node["pop"],
            "class": node["class"],
            "tier": node["tier"],
            "peak_now": node["peak"],
            "peak_after": after,
            "prior_gap": None if node["prior_peak_kib"] is None else
                         after - node["prior_peak_kib"],
            "headroom_after": headroom_after,
            "days_text": days_text,
            "days_exact": days_exact,
            "kind": kind,
            "rank_before": int(p2.risk[nid]["rank"]),
            "flag": flag,
            "pop_share": pop_share,
            "class_share": class_share,
            "daily_kib": daily_kib,
            "full_date": "" if kind != "numeric" else
                         local_date(days_exact, p1.pop[node["pop"]]["utc_offset_minutes"]),
        }

    running = 0
    running_min = None
    projection_rows = []
    for nid in p1.node_order:
        item = projection[nid]
        running += item["headroom_after"]
        running_min = running if running_min is None else min(running_min, running)
        projection_rows.append([
            nid, item["pop"], item["class"], str(item["peak_now"]),
            str(item["peak_after"]), fmt_int(item["prior_gap"]),
            str(item["headroom_after"]), item["days_text"], str(item["rank_before"]),
            item["flag"],
            "" if item["pop_share"] is None else fmt_dec(item["pop_share"], 4),
            "" if item["class_share"] is None else fmt_dec(item["class_share"], 4),
            item["full_date"], str(running), str(running_min),
        ])

    spill_rows, spill_grants = compute_spill_alloc(p1, p2, projection, p90)
    ticket_rows = compute_tickets(p1, p2, projection)
    outlook_rows = compute_pop_outlook(p1, p2, projection, spill_grants)
    drift_rows = compute_class_drift(p1, p2, projection, peak_after)

    chain = "0" * 64
    for row in projection_rows:
        line = ",".join(row)
        chain = hashlib.sha256((chain + line).encode("utf-8")).hexdigest()

    inputs = {}
    for name, digest in p1.digests().items():
        inputs["p1/" + name] = digest
    for name, digest in p2.digests().items():
        inputs["p2/" + name] = digest
    applied = sum(1 for entry in p1.pending["amendments"]
                  if p1.amendment_pairs[entry["id"]])
    manifest = {
        "phase": 3,
        "inputs": inputs,
        "totals": {
            "nodes": len(p1.node_order),
            "at_risk": sum(1 for n in p1.node_order if projection[n]["flag"] == "at-risk"),
            "watch": sum(1 for n in p1.node_order if projection[n]["flag"] == "watch"),
            "peak_after_kib": sum(projection[n]["peak_after"] for n in p1.node_order),
            "headroom_after_kib": sum(projection[n]["headroom_after"]
                                      for n in p1.node_order),
            "spill_granted_kib": sum(spill_grants.values()),
            "tickets": len(ticket_rows),
            "pending_applied": applied,
        },
        "chain": chain,
    }

    write_outputs(out_dir, {
        "projection.csv": render_csv("projection.csv", projection_rows),
        "pop_outlook.csv": render_csv("pop_outlook.csv", outlook_rows),
        "spill_alloc.csv": render_csv("spill_alloc.csv", spill_rows),
        "tickets.csv": render_csv("tickets.csv", ticket_rows),
        "class_drift.csv": render_csv("class_drift.csv", drift_rows),
        "manifest.json": render_json(manifest),
    })


def compute_spill_alloc(p1, p2, projection, p90):
    rows = []
    grants = {}
    for code in p1.pop_order:
        members = [n for n in p1.node_order
                   if projection[n]["pop"] == code and projection[n]["headroom_after"] < 0]
        members.sort(key=lambda nid: (
            0 if projection[nid]["class_share"] is not None else 1,
            -(projection[nid]["class_share"] or Fraction(0)),
            projection[nid]["headroom_after"],
            nid,
        ))
        remaining = p1.pop[code]["spill_budget_kib"]
        pop_headroom_now = int(p2.pop_rollup[code]["headroom_mib"])
        for nid in members:
            item = projection[nid]
            deficit = -item["headroom_after"]
            if item["tier"] == "3" and pop_headroom_now > 0:
                granted = 0
                state = "deferred"
            else:
                granted = min(deficit, remaining)
                if p90 is not None and p90 > 0:
                    granted = min(granted, p90)
                granted = max(granted, 0)
                if granted >= deficit:
                    state = "full"
                elif granted > 0:
                    state = "partial"
                else:
                    state = "none"
                remaining -= granted
            grants[nid] = granted
            rows.append([nid, code, str(deficit), fmt_int(item["daily_kib"]),
                         str(granted), str(remaining), state])
    return rows, grants


def _ticket_sort_key(item):
    kind_rank = {"numeric": 0, "never": 1, "empty": 2}
    return (
        0 if item["flag"] == "at-risk" else 1,
        kind_rank[item["kind"]],
        item["days_exact"] if item["kind"] == "numeric" else 0,
        0 if item["class_share"] is not None else 1,
        -(item["class_share"] or Fraction(0)),
        0 if item["pop_share"] is not None else 1,
        -(item["pop_share"] or Fraction(0)),
        item["node_id"],
    )


def compute_tickets(p1, p2, projection):
    rows = []
    for code in p1.pop_order:
        members = [projection[n] for n in p1.node_order
                   if projection[n]["pop"] == code
                   and projection[n]["flag"] in ("at-risk", "watch")]
        members.sort(key=_ticket_sort_key)
        quota = p1.pop[code]["ticket_quota"]
        if int(p2.pop_rollup[code]["headroom_mib"]) <= 0:
            quota *= 2
        for index, item in enumerate(members[:quota], start=1):
            rows.append(["T-%s-%02d" % (code, index), code, item["node_id"],
                         item["flag"], item["days_text"], str(item["rank_before"])])
    return rows


def compute_pop_outlook(p1, p2, projection, spill_grants):
    rows = []
    for code in p1.pop_order:
        members = [n for n in p1.node_order if projection[n]["pop"] == code]
        headroom_after = sum(projection[n]["headroom_after"] for n in members)
        at_risk = [n for n in members if projection[n]["flag"] == "at-risk"]
        shield_left = p1.pop[code]["shield_pool_kib"] - \
            sum(p2.grant.get(n, 0) for n in members)
        spill_left = p1.pop[code]["spill_budget_kib"] - \
            sum(spill_grants.get(n, 0) for n in members)
        pair_set = {(n, p["property"]) for n in members
                    for p in p1.pairs_by_node.get(n, [])}
        applied = sum(1 for entry in p1.pending["amendments"]
                      if p1.amendment_pairs[entry["id"]] & pair_set)
        numeric = [projection[n]["days_exact"] for n in members
                   if projection[n]["kind"] == "numeric"]
        mean_days = "" if not numeric else \
            fmt_dec(sum(numeric) / len(numeric), 2)
        totals = {}
        for nid in at_risk:
            item = projection[nid]
            totals[item["class"]] = totals.get(item["class"], Fraction(0)) + \
                (item["class_share"] or Fraction(0))
        worst = ""
        if totals:
            worst = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        rows.append([
            code, p2.pop_rollup[code]["headroom_mib"],
            str(half_even(Fraction(headroom_after, 1024))), str(len(at_risk)),
            str(half_even(Fraction(shield_left, 1024))),
            str(half_even(Fraction(spill_left, 1024))), str(applied),
            mean_days, worst,
        ])
    return rows


def compute_class_drift(p1, p2, projection, peak_after):
    rows = []
    for row in p2.class_rollup:
        name = row["class"]
        members = [n for n in p1.node_order if projection[n]["class"] == name]
        now_mib = int(row["peak_mib"])
        after_mib = half_even(Fraction(sum(peak_after[n] for n in members), 1024))
        gaps = [projection[n]["prior_gap"] for n in members
                if projection[n]["prior_gap"] is not None]
        prior_gap = "" if not gaps else str(half_even(Fraction(sum(gaps), 1024)))
        shares = [projection[n]["pop_share"] for n in members
                  if projection[n]["pop_share"] is not None]
        mean_share = "" if not shares else fmt_dec(sum(shares) / len(shares), 4)
        share_after = shield_share(p1, lambda nid: peak_after[nid], name)
        rows.append([
            name, str(now_mib), str(after_mib), str(after_mib - now_mib), prior_gap,
            str(sum(1 for n in members if projection[n]["flag"] == "at-risk")),
            mean_share, str(half_even(share_after / 1024)),
        ])
    return rows


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def main(argv):
    if len(argv) < 2:
        raise UsageError("missing subcommand")
    command = argv[1]
    args = argv[2:]
    if command == "phase1":
        if len(args) != 2:
            raise UsageError("phase1 takes 2 arguments")
        phase1(args[0], args[1])
    elif command == "phase2":
        if len(args) != 2:
            raise UsageError("phase2 takes 2 arguments")
        phase2(args[0], args[1])
    elif command == "phase3":
        if len(args) != 3:
            raise UsageError("phase3 takes 3 arguments")
        phase3(args[0], args[1], args[2])
    else:
        raise UsageError("unknown subcommand %r" % (command,))


if __name__ == "__main__":
    try:
        main(sys.argv)
    except UsageError as error:
        sys.stderr.write("error: usage: %s\n" % error)
        sys.exit(2)
    except UpstreamError as error:
        sys.stderr.write("error: upstream: %s\n" % error)
        sys.exit(3)
