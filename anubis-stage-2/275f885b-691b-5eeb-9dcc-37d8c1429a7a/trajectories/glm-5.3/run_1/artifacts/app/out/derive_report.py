#!/usr/bin/env python3
"""Campaign dose ration settlement.

Reads a campaign corpus folder and writes the nine settlement documents.
Every rule applied comes from the corpus itself; nothing is hard coded.
"""

import argparse
import configparser
import datetime as dt
import json
import os
import re
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

TS_FMT = "%Y-%m-%d %H:%M:%S"
UTC_FMT = "%Y-%m-%dT%H:%M:%SZ"


def parse_local(text):
    return dt.datetime.strptime(text, TS_FMT)


def parse_utc(text):
    return dt.datetime.strptime(text, UTC_FMT)


def parse_date(text):
    parts = text.strip().split("-")
    return dt.date(int(parts[0]), int(parts[1]), int(parts[2]))


def to_int(text):
    """Whole number from a plain or parenthesised decimal field."""
    text = text.strip()
    if text.startswith("(") and text.endswith(")"):
        return -int(text[1:-1])
    return int(text)


class RecordFile(object):
    """A delimited or json record file with its `# rows=` declaration."""

    def __init__(self, path, declared, rows, header):
        self.path = path
        self.declared = declared
        self.rows = rows
        self.header = header


def load_record_file(path, kind):
    """kind: csv | tsv | jsonl | fixed"""
    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    declared = None
    start = 0
    if lines and lines[0].startswith("# rows="):
        declared = int(lines[0].split("=", 1)[1].strip())
        start = 1
    body = [ln for ln in lines[start:] if ln.strip()]
    header = None
    if kind in ("csv", "tsv"):
        sep = "," if kind == "csv" else "\t"
        head = start
        header = body[0].split(sep) if body else []
        rows = []
        for ln in body[1:]:
            rows.append(ln.split(sep))
        return RecordFile(path, declared, rows, header)
    if kind == "jsonl":
        rows = [json.loads(ln) for ln in body]
        return RecordFile(path, declared, rows, None)
    # fixed width assay file: one record per line
    return RecordFile(path, declared, body, None)


# --------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------

class Corpus(object):
    def __init__(self, folder):
        self.folder = folder
        self.source_rows = defaultdict(int)
        self.header_gaps = 0
        self.files = {}
        self._load_all()

    # -- generic loaders ---------------------------------------------------

    def _record(self, logical, name, kind):
        path = os.path.join(self.folder, name)
        rf = load_record_file(path, kind)
        self.source_rows[logical] += len(rf.rows)
        if rf.declared is not None and rf.declared != len(rf.rows):
            self.header_gaps += 1
        self.files[name] = rf
        return rf

    def _load_all(self):
        # inventory from the manifest: every file must be present
        manifest_path = os.path.join(self.folder, "source_manifest.md")
        text = open(manifest_path, "r", encoding="utf-8").read()
        self.manifest_sources = {}
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("- ") and ":" in line:
                head, rest = line[2:].split(":", 1)
                self.manifest_sources[head.strip()] = rest.split()
        for src, names in self.manifest_sources.items():
            for name in names:
                if not os.path.exists(os.path.join(self.folder, name)):
                    raise SystemExit("incomplete export: missing %s" % name)

        for src, names in self.manifest_sources.items():
            for name in names:
                path = os.path.join(self.folder, name)
                if not os.path.isfile(path):
                    continue
                if name.endswith(".csv"):
                    self._record(src, name, "csv")
                elif name.endswith(".tsv"):
                    self._record(src, name, "tsv")
                elif name.endswith(".jsonl"):
                    self._record(src, name, "jsonl")
                elif name.endswith(".txt"):
                    self._record(src, name, "fixed")

        # configuration
        self.props = self._load_properties(os.path.join(self.folder, "source_declarations.properties"))
        self.units = self._load_units(os.path.join(self.folder, "unit_declarations.ini"))
        self.reason_codes = json.load(open(os.path.join(self.folder, "reason_codes.json"), "r", encoding="utf-8"))
        self.authority = json.load(open(os.path.join(self.folder, "authority_scopes.json"), "r", encoding="utf-8"))

        # observation logs
        self.governance = self._load_log(os.path.join(self.folder, "governance_observations.log"))
        self.clearance = self._load_log(os.path.join(self.folder, "clearance_observations.log"))
        self._read_contract()

    @staticmethod
    def _load_properties(path):
        raw = open(path, "r", encoding="utf-8").read().splitlines()
        values = {}
        key = None
        buf = []
        for line in raw:
            if line.strip().startswith("#") or not line.strip():
                if key is not None:
                    values[key] = " ".join(buf)
                    key, buf = None, []
                continue
            if key is not None and line.startswith((" ", "\t")):
                buf.append(line.strip())
                if not line.rstrip().endswith("\\"):
                    values[key] = " ".join(buf)
                    key, buf = None, []
                continue
            if key is not None:
                values[key] = " ".join(buf)
                key, buf = None, []
            if "=" in line:
                k, v = line.split("=", 1)
                key = k.strip()
                buf = [v.strip()]
                if line.rstrip().endswith("\\"):
                    buf[0] = buf[0].rstrip("\\").strip()
                else:
                    values[key] = buf[0]
                    key, buf = None, []
        if key is not None:
            values[key] = " ".join(buf)
        out = {}
        for k, v in values.items():
            out[k] = " ".join(v.split())
        return out

    @staticmethod
    def _load_units(path):
        cp = configparser.ConfigParser()
        cp.optionxform = str
        cp.read(path)
        out = {}
        for section in cp.sections():
            out[section] = dict(cp[section])
        return out

    @staticmethod
    def _load_log(path):
        entries = []
        for line in open(path, "r", encoding="utf-8").read().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            fields = {"stamp": line.split()[0]}
            for token in line.split()[1:]:
                if "=" in token:
                    key, value = token.split("=", 1)
                    fields[key] = value
            entries.append(fields)
        return entries

    def _read_contract(self):
        path = os.path.join(self.folder, "output_contract.md")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as handle:
                self.contract = handle.read()
        else:
            self.contract = ""

    # -- accessors ----------------------------------------------------------
    def contract_order(self, label):
        """The fixed order a list is held in, as the output contract states it."""
        found = []
        if self.contract:
            pattern = re.compile(r"`%s` is a list in the order ([^\n.]+)" % label)
            match = pattern.search(self.contract)
            if match:
                for item in match.group(1).split(","):
                    item = item.strip().strip("`")
                    if not item or " " in item:
                        break
                    found.append(item)
        if not found and self.contract:
            alt = re.findall(r"%s_([A-Za-z0-9_-]+)\.json" % label[:-1], self.contract)
            for item in alt:
                if item not in found:
                    found.append(item)
        return found

    def regions(self):
        order = [x for x in self.contract_order("regions") if x in self._depot_names()]
        names = self._depot_names()
        for name in names:
            if name not in order:
                order.append(name)
        return order

    def segments(self):
        known = []
        for row in self.files["block_master.csv"].rows:
            if row[4] not in known:
                known.append(row[4])
        order = [x for x in self.contract_order("segments") if x in known]
        for name in known:
            if name not in order:
                order.append(name)
        return order

    def _depot_names(self):
        return [region for region, _ in self._depot_map()]

    def names_of(self, logical):
        """Record file names of one logical source, in manifest order."""
        return [n for n in self.manifest_sources.get(logical, [])
                if os.path.isfile(os.path.join(self.folder, n))]

    def assay_name(self):
        for name in self.names_of("assay"):
            return name
        return None

    def assay_decimals(self):
        section = self.units.get("potency_assays.doses_per_unit", {})
        return int(section.get("implied_decimals", "3"))

    def props_int(self, key):
        return int(self.props[key])

    def props_time(self, key):
        text = self.props[key]
        parts = [int(x) for x in text.split(":")]
        while len(parts) < 3:
            parts.append(0)
        return dt.time(parts[0], parts[1], parts[2])

    def _depot_map(self):
        pairs = []
        for token in re.split(r"[,;]", self.props.get("depot.map", "")):
            token = token.strip()
            if ":" in token:
                region, depot = token.split(":", 1)
                pairs.append((region.strip(), depot.strip()))
        return pairs

    def depot_of(self, region):
        for name, depot in self._depot_map():
            if name == region:
                return depot
        return None

    def region_of(self, depot):
        for name, value in self._depot_map():
            if value == depot:
                return name
        return None

    def reference_tier_sources(self):
        """Logical sources whose rows count under `reference`."""
        sources = []
        for name in self.manifest_sources.get("reference", []):
            sources.append("reference")
            break
        for logical in ("ceilings", "configuration"):
            if logical in self.manifest_sources:
                sources.append(logical)
        return sources


# --------------------------------------------------------------------------
# reference registers
# --------------------------------------------------------------------------

class Registers(object):
    """Reference tables, primary sources and correction stream, indexed."""

    def __init__(self, corpus):
        self.c = corpus
        f = corpus.files
        self._blocks(f)
        self._aliases(f)
        self._priority(f)
        self._ceilings(f)
        self._dose_factors(f)
        self._potency(f)
        self._substitution(f)
        self._phases(f)
        self._clocks(f)
        self._calendar(f)
        self._lots(f)
        self._events(f)
        self._dispatch(f)
        self._registry(f)
        self._amendments(f)

    # -- blocks ------------------------------------------------------------
    def _blocks(self, f):
        self.master = defaultdict(list)
        for r in f["block_master.csv"].rows:
            self.master[r[1]].append({
                "record_id": r[0], "valid_from": parse_date(r[2]), "region": r[3],
                "segment": r[4], "species": r[5], "age_class": r[6],
                "risk_class": r[7],
                "withdrawn_from": parse_date(r[8]) if r[8] else None,
                "issued_at": r[9],
            })

    def master_version(self, block_ref, start_date):
        """Master version in force for a round window opening on start_date."""
        best = None
        for row in self.master.get(block_ref, ()):
            if row["valid_from"] <= start_date:
                key = (row["valid_from"], row["record_id"])
                if best is None or key > (best["valid_from"], best["record_id"]):
                    best = row
        return best

    # -- aliases -----------------------------------------------------------
    def _aliases(self, f):
        self.alias = defaultdict(list)
        for r in f["block_alias_map.csv"].rows:
            self.alias[r[0]].append({
                "canonical": r[1], "effective_from": parse_date(r[2]),
                "effective_to": parse_date(r[3]) if r[3] else None,
                "issued_at": r[4],
            })

    def alias_step(self, key, start_date):
        """The mapping in force for a key on a round start date, or None."""
        best = None
        for row in self.alias.get(key, ()):
            if row["effective_from"] <= start_date and (
                    row["effective_to"] is None or start_date < row["effective_to"]):
                key_ = (row["effective_from"], row["issued_at"])
                if best is None or key_ > (best["effective_from"], best["issued_at"]):
                    best = row
        return best["canonical"] if best else None

    def resolve_key(self, norm_key, start_date):
        """Resolve a normalised key to a master block and its hop count."""
        if norm_key is None:
            return None, 0
        max_hops = self.c.props_int("alias.max_hops")
        current = norm_key
        visited = {current}
        hops = 0
        while True:
            if current in self.master:
                return current, hops
            if hops >= max_hops:
                return None, hops
            nxt = self.alias_step(current, start_date)
            hops += 1
            if nxt is None or nxt in visited:
                return None, hops
            visited.add(nxt)
            current = nxt

    # -- priority ----------------------------------------------------------
    def _priority(self, f):
        self.priority = defaultdict(list)
        for r in f["priority_register.csv"].rows:
            self.priority[r[1]].append({
                "entry_ref": r[0], "tier": int(r[2]),
                "effective_from": parse_date(r[3]), "issued_at": r[4],
            })

    def tier_of(self, block_ref, start_date):
        best = None
        for row in self.priority.get(block_ref, ()):
            if row["effective_from"] <= start_date:
                key = (row["effective_from"], row["issued_at"], row["entry_ref"])
                if best is None or key > best[0]:
                    best = (key, row)
        return best[1]["tier"] if best else self.c.props_int("tier.count")

    # -- ceilings -----------------------------------------------------------
    def _ceilings(self, f):
        self.ceilings = defaultdict(list)
        for name in self.c.names_of("ceilings"):
            for r in f[name].rows:
                self.ceilings[(r[1], r[2])].append({
                    "entry_ref": r[0], "ceiling": to_int(r[3]), "issued_at": r[4],
                })

    def ceiling_of(self, block_ref, round_code):
        rows = self.ceilings.get((block_ref, round_code))
        if not rows:
            return None, None
        best = max(rows, key=lambda r: (r["issued_at"], r["entry_ref"]))
        return best["ceiling"], best["issued_at"]

    # -- dose factors -------------------------------------------------------
    def _dose_factors(self, f):
        self.dose_factors = defaultdict(list)
        for r in f["dose_factors.csv"].rows:
            self.dose_factors[(r[1], r[2], r[3])].append({
                "factor_ref": r[0], "effective_from": parse_date(r[4]),
                "doses": Decimal(r[5]), "issued_at": r[6],
            })

    def dose_factor(self, region, species, age_class, start_date):
        best = None
        for row in self.dose_factors.get((region, species, age_class), ()):
            if row["effective_from"] <= start_date:
                key = (row["effective_from"], row["issued_at"], row["factor_ref"])
                if best is None or key > best[0]:
                    best = (key, row)
        return best[1]["doses"] if best else None

    # -- potency ------------------------------------------------------------
    def _potency(self, f):
        self.potency = defaultdict(list)
        for r in f["potency_factors.csv"].rows:
            self.potency[(r[1], r[2], r[3])].append({
                "factor_ref": r[0], "effective_from": parse_date(r[4]),
                "doses_per_unit": Decimal(r[5]), "issued_at": r[6],
            })

    def doses_per_unit(self, depot, serotype, unit, consign_date):
        best = None
        for row in self.potency.get((depot, serotype, unit), ()):
            if row["effective_from"] <= consign_date:
                key = (row["effective_from"], row["issued_at"], row["factor_ref"])
                if best is None or key > best[0]:
                    best = (key, row)
        return best[1]["doses_per_unit"] if best else None

    # -- substitution -------------------------------------------------------
    def _substitution(self, f):
        self.sub_edges = defaultdict(list)
        for r in f["substitution_graph.csv"].rows:
            self.sub_edges[(r[1], r[2])].append({
                "edge_ref": r[0], "effective_from": parse_date(r[3]),
                "effective_to": parse_date(r[4]) if r[4] else None,
                "percent": Decimal(r[5]), "issued_at": r[6],
            })
        self.sub_pairs = sorted(self.sub_edges.keys())

    def edge_in_force(self, src, dst, day):
        best = None
        for row in self.sub_edges.get((src, dst), ()):
            if row["effective_from"] <= day and (
                    row["effective_to"] is None or day < row["effective_to"]):
                key = (row["percent"], row["edge_ref"])
                if best is None or key > (best["percent"], best["edge_ref"]):
                    best = row
        return best

    def substitution_path(self, serotype, target, day):
        """(hops, potency fraction) of the path in force, or None."""
        if serotype == target:
            return 0, Decimal(1)
        max_hops = self.c.props_int("substitution.max_hops")
        best = None
        frontier = [(serotype, ())]
        for depth in range(1, max_hops + 1):
            nxt = []
            for node, path in frontier:
                for (src, dst) in self.sub_pairs:
                    if src != node:
                        continue
                    edge = self.edge_in_force(src, dst, day)
                    if edge is None:
                        continue
                    if dst == target:
                        fraction = Decimal(1)
                        for e in list(path) + [edge]:
                            fraction = fraction * e["percent"] / Decimal(100)
                        cand = (depth, fraction)
                        if best is None or depth < best[0] or (depth == best[0]
                                                              and fraction > best[1]):
                            best = cand
                    else:
                        if edge["edge_ref"] in set(e["edge_ref"] for e in path):
                            continue
                        nxt.append((dst, tuple(list(path) + [edge])))
            frontier = nxt
        return best

    # -- phases -------------------------------------------------------------
    def _phases(self, f):
        self.phases = defaultdict(list)
        for r in f["campaign_phases.csv"].rows:
            self.phases[(r[1], r[2])].append({
                "revision_ref": r[0], "target": r[3], "issued_at": r[4],
            })

    def target_serotype(self, region, round_code, open_utc):
        best = None
        for row in self.phases.get((region, round_code), ()):
            if parse_utc(row["issued_at"]) <= open_utc:
                key = (row["issued_at"], row["revision_ref"])
                if best is None or key > (best["issued_at"], best["revision_ref"]):
                    best = row
        return best["target"] if best else None

    # -- depot clocks -------------------------------------------------------
    def _clocks(self, f):
        self.clock = defaultdict(list)
        for r in f["depot_clock_offsets.csv"].rows:
            self.clock[r[0]].append((r[1], int(r[2]), r[3]))
        self.clock_in_force = {}
        for depot, rows in self.clock.items():
            by_date = defaultdict(list)
            for day, off, issued in rows:
                by_date[day].append((issued, off))
            for day, values in by_date.items():
                self.clock_in_force[(depot, day)] = max(values)[1]

    def offset(self, depot, day):
        if not isinstance(day, str):
            day = day.isoformat()
        key = (depot, day)
        if key not in self.clock_in_force:
            raise SystemExit("incomplete export: no clock offset for %s %s" % (depot, day))
        return self.clock_in_force[key]

    def local_to_utc(self, depot, local):
        return local - dt.timedelta(minutes=self.offset(depot, local.date()))

    # -- calendar -----------------------------------------------------------
    def _calendar(self, f):
        rounds = self.c.props_int("campaign.rounds")
        anchor = parse_date(self.c.props["campaign.anchor.date"])
        self.recurrence = {}
        for i in range(rounds):
            self.recurrence["R%02d" % (i + 1)] = anchor + dt.timedelta(days=14 * i)
        notices = defaultdict(list)
        for r in f["calendar_exceptions.csv"].rows:
            notices[r[1]].append({
                "notice_ref": r[0], "region": r[2], "action": r[3],
                "new_start": parse_date(r[4]) if r[4] else None, "issued_at": r[5],
            })
        self.round_action = {}
        for code, rows in notices.items():
            live = [r for r in rows if r["region"] == "ALL"]
            if not live:
                continue
            best = max(live, key=lambda r: (r["issued_at"], r["notice_ref"]))
            if code in self.recurrence:
                self.round_action[code] = best
        self.skipped = set(c for c, r in self.round_action.items() if r["action"] == "skip")
        self.start_date = {}
        for code, start in self.recurrence.items():
            action = self.round_action.get(code)
            if action and action["action"] == "move" and action["new_start"]:
                self.start_date[code] = action["new_start"]
            else:
                self.start_date[code] = start
        self.live = sorted((c for c in self.recurrence if c not in self.skipped),
                           key=lambda c: (self.start_date[c], c))
        # round of settlement for every round code
        self.settlement_round = {}
        for code in self.recurrence:
            if code in self.live:
                self.settlement_round[code] = code
            else:
                later = [c for c in self.live if self.start_date[c] > self.start_date[code]]
                self.settlement_round[code] = (min(later, key=lambda c: (self.start_date[c], c))
                                               if later else None)
        self.day_start = self.c.props_time("day.start.local")
        self.window_days = self.c.props_int("window.length.days")

    def window_local(self, round_code):
        """(open, close) of the claim window of a round, depot local."""
        open_local = dt.datetime.combine(self.start_date[round_code], self.day_start)
        return open_local, open_local + dt.timedelta(days=self.window_days)

    def window_utc(self, round_code, depot):
        open_local, close_local = self.window_local(round_code)
        return self.local_to_utc(depot, open_local), self.local_to_utc(depot, close_local)

    def rounds_in_play(self, settlement_code):
        return set(c for c, s in self.settlement_round.items()
                   if s == settlement_code) | {settlement_code}

    # -- lots ---------------------------------------------------------------
    def _lots(self, f):
        self.lots = {}
        for name in self.c.names_of("lot_register"):
            for r in f[name].rows:
                lot_id = "%s@%s" % (r[0], r[1])
                self.lots[lot_id] = {
                    "lot_id": lot_id, "lot_ref": r[0], "production_year": r[1],
                    "depot": r[2], "serotype": r[3], "quantity": Decimal(r[4]),
                    "consign_round": r[5], "consign_date": parse_date(r[6]),
                    "expiry_local": (parse_local(r[7]) if r[7]
                                     else dt.datetime(9999, 12, 31)),
                }
        self.certs = defaultdict(list)
        for name in self.c.names_of("release_certificates"):
            for r in f[name].rows:
                self.certs["%s@%s" % (r[1], r[2])].append({
                    "cert_ref": r[0], "state": r[3], "issued_at": parse_utc(r[4]),
                    "supersedes": r[5], "signed_by": r[6],
                })
        self.assays = {}
        for line in f[self.c.assay_name()].rows:
            lot_ref = line[0:9].strip()
            year = line[9:13].strip()
            self.assays["%s@%s" % (lot_ref, year)] = (
                Decimal(line[33:41].strip()) / (Decimal(10) ** self.c.assay_decimals()))

    def certs_of(self, lot_id):
        return sorted(self.certs.get(lot_id, ()), key=lambda c: (c["issued_at"], c["cert_ref"]))

    # -- visit events -------------------------------------------------------
    def _events(self, f):
        raw = defaultdict(list)
        for name in self.c.names_of("visit_events"):
            for r in f[name].rows:
                raw[r["event_id"]].append(r)
        self.conflicting_pairs = set()
        self.events = []
        for event_id, rows in raw.items():
            distinct = []
            for row in rows:
                if row not in distinct:
                    distinct.append(row)
            if len(distinct) > 1:
                for row in distinct:
                    self.conflicting_pairs.add((row["block_ref"], row["round_code"]))
            else:
                self.events.extend(rows)
        self.block_events = defaultdict(list)
        for row in self.events:
            self.block_events[(row["block_ref"], row["round_code"])].append(row)
        self.block_restocks = defaultdict(list)
        for row in self.events:
            if row["event"] == "restock":
                self.block_restocks[row["block_ref"]].append(parse_utc(row["occurred_at"]))

    # -- dispatch -----------------------------------------------------------
    def _dispatch(self, f):
        self.dispatch = defaultdict(list)
        for name in self.c.names_of("dispatch_stream"):
            for r in f[name].rows:
                self.dispatch[(r["block_ref"], r["round_code"])].append(r)

    # -- registry -----------------------------------------------------------
    def _registry(self, f):
        self.registry = defaultdict(list)
        for name in self.c.names_of("registry"):
            for r in f[name].rows:
                self.registry[r[1]].append(r)

    # -- amendments ---------------------------------------------------------
    def _amendments(self, f):
        self.amendments = []
        for name in self.c.names_of("amendments"):
            for r in f[name].rows:
                self.amendments.append(r)


# --------------------------------------------------------------------------
# requisition admission
# --------------------------------------------------------------------------

def normalise_key(text):
    """A holding key as the field office typed it, normalised."""
    if text is None:
        return None
    trimmed = text.strip().upper()
    trimmed = trimmed.split("/")[0]
    digits = re.sub(r"\D", "", trimmed)
    if not digits:
        return None
    return "BLK-" + digits.zfill(4)


class Requisition(object):
    __slots__ = ("ref", "key", "norm", "named_round", "recorded_local", "effective_local",
                 "head_count", "species", "age_class", "source_tag", "reject", "block",
                 "hops", "identity", "settlement", "row")

    def __init__(self, row):
        self.row = row
        self.ref = row[0]
        self.key = row[1]
        self.norm = normalise_key(row[1])
        self.named_round = row[2]
        self.recorded_local = parse_local(row[3])
        self.effective_local = parse_local(row[4])
        self.head_count = None if row[5] == "" else int(row[5])
        self.species = row[6]
        self.age_class = row[7]
        self.source_tag = row[8] if len(row) > 8 else ""
        self.reject = None
        self.block = None
        self.hops = 0
        self.identity = None
        self.settlement = None


class Claim(object):
    """One settled claim of one block identity for one round."""

    __slots__ = ("block", "identity", "round", "settlement_round", "named_round",
                 "req", "group_rows", "tier", "region", "segment", "species",
                 "age_class", "depot", "head_count", "head_source",
                 "head_recorded_utc", "entitlement_raw", "entitlement", "carried_in",
                 "claimable", "awarded", "deferred", "awarded_to_date",
                 "deferred_to_date", "carry_forward", "served_lot", "hops",
                 "outcome", "reason", "ceiling", "clamped", "half_exact",
                 "remainder_doses")

    def __init__(self):
        self.group_rows = []
        self.remainder_doses = 0
        self.entitlement = None
        self.carry_forward = 0
        self.remainder_doses = 0


class Settlement(object):
    def __init__(self, corpus, clearance_scope):
        self.c = corpus
        self.r = Registers(corpus)
        self.scope = clearance_scope
        self.rejects = defaultdict(int)
        self.counted = defaultdict(int)
        self.claims = []
        self.ledger = []
        self.cells = {}
        self.audit = {}
        self._head_cache = {}
        self.illegal_transitions = 0
        self.reinstated_lots = 0

    # ------------------------------------------------------------------
    # requisition admission and collapse
    # ------------------------------------------------------------------
    def admit(self):
        r = self.r
        live = set(r.live)
        self.requisitions = []
        for name in self.c.names_of("field_intake"):
            for row in self.c.files[name].rows:
                self.requisitions.append(Requisition(row))
        groups = defaultdict(list)
        for req in self.requisitions:
            # round of settlement and identity
            if req.named_round not in r.recurrence:
                req.reject = "RC_UNKNOWN_BLOCK"
                self.rejects[req.reject] += 1
                continue
            req.settlement = r.settlement_round[req.named_round]
            if req.settlement is None:
                req.reject = "RC_UNKNOWN_BLOCK"
                self.rejects[req.reject] += 1
                continue
            block, hops = r.resolve_key(req.norm, r.start_date[req.settlement])
            req.block, req.hops = block, hops
            if block is None:
                req.reject = "RC_UNKNOWN_BLOCK"
                self.rejects[req.reject] += 1
                continue
            version = r.master_version(block, r.start_date[req.settlement])
            if version is None:
                req.reject = "RC_UNKNOWN_BLOCK"
                self.rejects[req.reject] += 1
                continue
            depot = self.c.depot_of(version["region"])
            if depot is None:
                req.reject = "RC_UNKNOWN_BLOCK"
                self.rejects[req.reject] += 1
                continue
            open_local, close_local = r.window_local(req.named_round)
            open_utc, close_utc = r.window_utc(req.named_round, depot)
            # RC_WINDOW
            if not (open_local <= req.effective_local < close_local):
                req.reject = "RC_WINDOW"
                self.rejects[req.reject] += 1
                continue
            # RC_LATE_RECORD
            if req.recorded_local >= close_local:
                req.reject = "RC_LATE_RECORD"
                self.rejects[req.reject] += 1
                continue
            # RC_WITHDRAWN_BLOCK
            if version["withdrawn_from"] is not None and version["withdrawn_from"] <= open_local.date():
                req.reject = "RC_WITHDRAWN_BLOCK"
                self.rejects[req.reject] += 1
                continue
            # RC_EPOCH_GAP (before RC_EVENT_CONFLICT: errata amendment one)
            if self._restock_inside(block, open_utc, close_utc):
                req.reject = "RC_EPOCH_GAP"
                self.rejects[req.reject] += 1
                continue
            # RC_EVENT_CONFLICT
            conflict = False
            for code in r.rounds_in_play(req.settlement):
                if (block, code) in r.conflicting_pairs:
                    conflict = True
                    break
            if conflict:
                req.reject = "RC_EVENT_CONFLICT"
                self.rejects[req.reject] += 1
                continue
            epoch = 1 + sum(1 for when in r.block_restocks.get(block, ())
                            if when < open_utc)
            req.identity = "%s#%d" % (block, epoch)
            groups[(req.identity, req.settlement)].append(req)

        # collapse of repeated rows
        self.groups = {}
        for key, rows in groups.items():
            rows.sort(key=lambda q: (q.recorded_local, q.ref))
            span_start = rows[0].recorded_local
            span_end = span_start + dt.timedelta(hours=self.c.props_int("collapse.window.hours"))
            inside = [q for q in rows if q.recorded_local <= span_end]
            after = [q for q in rows if q.recorded_local > span_end]
            self.counted["RC_STALE_REVISION"] += len(after)
            survivor = max(inside, key=lambda q: (q.recorded_local, q.ref))
            self.counted["RC_DUPLICATE_COLLAPSED"] += len(inside) - 1
            self.groups[key] = (survivor, inside, after)
        self.alias_hops = defaultdict(int)
        for req in self.requisitions:
            if req.block is not None:
                self.alias_hops[req.hops] += 1

    def _restock_inside(self, block, open_utc, close_utc):
        for when in self.r.block_restocks.get(block, ()):
            if open_utc <= when < close_utc:
                return True
        return False

    # ------------------------------------------------------------------
    # head count
    # ------------------------------------------------------------------
    def head_count(self, claim):
        """(value, source, recorded moment in utc) of the governing head count."""
        key = (claim.identity, claim.settlement_round, claim.named_round)
        if key in self._head_cache:
            return self._head_cache[key]
        r = self.r
        block_ref = claim.block
        depot = claim.depot
        close_utc = r.window_utc(claim.named_round, depot)[1]
        open_local = r.window_local(claim.named_round)[0]
        settlement_open_local = r.window_local(claim.settlement_round)[0]
        field_value = claim.req.head_count
        # dispatch stream
        dispatch_value = None
        dispatch_at = None
        records = []
        for code in sorted(r.rounds_in_play(claim.settlement_round)):
            for row in r.dispatch.get((block_ref, code), ()):
                if parse_utc(row["recorded_at"]) <= close_utc:
                    records.append(row)
        if records:
            top_version = max(int(row["version"]) for row in records)
            top = [row for row in records if int(row["version"]) == top_version]
            best = max(top, key=lambda row: (row["recorded_at"], row["round_code"]))
            if best["op"] != "delete":
                dispatch_value = int(best["head_count"])
                dispatch_at = parse_utc(best["recorded_at"])
        # registry
        registry_value = None
        for row in sorted(r.registry.get(block_ref, ()), key=lambda x: (x[2], x[0])):
            observed = row[2]
            if len(row) > 2 and observed and observed <= open_local.date().isoformat():
                if len(row) > 3 and row[3] not in ("",):
                    if row[3] == r"\N":
                        registry_value = None
                    else:
                        try:
                            registry_value = int(row[3])
                        except ValueError:
                            pass
        registry_at = self.r.local_to_utc(
            depot, dt.datetime.combine(settlement_open_local.date(), dt.time(0, 0)))
        cutover = parse_date(self.c.props["cutover.date"])
        opens_before = open_local.date() < cutover
        primary = self.governing[0 if opens_before else 1]
        secondary = self.governing[1 if opens_before else 0]
        for source in (primary, secondary):
            if source == "field_intake" and field_value is not None:
                result = (field_value, "field_intake",
                          self.r.local_to_utc(depot, claim.req.recorded_local))
                break
            if source == "dispatch_stream" and dispatch_value is not None:
                result = (dispatch_value, "dispatch_stream", dispatch_at)
                break
        else:
            result = (registry_value, "registry", registry_at)
        self._head_cache[key] = result
        return result

    def set_governing(self, governing):
        self.governing = governing

    # ------------------------------------------------------------------
    # claims of a cell
    # ------------------------------------------------------------------
    def build_claims(self):
        """Group surviving requisitions into claims, one per identity and round."""
        r = self.r
        self.claim_by_key = {}
        for (identity, settlement), (survivor, inside, after) in self.groups.items():
            block_ref = survivor.block
            version = r.master_version(block_ref, r.start_date[settlement])
            claim = Claim()
            claim.block = block_ref
            claim.identity = identity
            claim.settlement_round = settlement
            claim.named_round = survivor.named_round
            claim.round = settlement
            claim.req = survivor
            claim.group_rows = inside
            claim.region = version["region"]
            claim.segment = version["segment"]
            claim.species = version["species"]
            claim.age_class = version["age_class"]
            claim.depot = self.c.depot_of(claim.region)
            claim.tier = r.tier_of(block_ref, r.start_date[settlement])
            self.claim_by_key[(identity, settlement)] = claim

    # ------------------------------------------------------------------
    # amendments
    # ------------------------------------------------------------------
    def amend(self):
        """Apply authorised and timely amendment notices to their targets."""
        r = self.r
        self.amendments_applied = 0
        self.amendments_stale = 0
        self.amendments_unauthorised = 0
        by_target = defaultdict(list)
        for notice in r.amendments:
            role = self.c.authority.get(notice["signed_by"], {})
            block_ref = notice["block_ref"]
            version = r.master_version(block_ref, r.start_date.get(notice["round_code"],
                                                                  dt.date(9999, 12, 31)))
            region = version["region"] if version else None
            authorised = bool(role.get("can_amend")) and region in role.get("regions", ())
            if not authorised:
                self.amendments_unauthorised += 1
                self.counted["RC_AMENDMENT_UNAUTHORISED"] += 1
                continue
            by_target[(block_ref, notice["round_code"])].append(notice)
        self.pending_amendments = by_target
        # timeliness is settled per claim, when the head count and ceiling are known
        self._amend_state = {"applied": 0, "stale": 0}

    def notices_for(self, claim):
        r = self.r
        out = []
        for code in r.rounds_in_play(claim.settlement_round):
            out.extend(self.pending_amendments.get((claim.block, code), ()))
        out.sort(key=lambda n: (n["recorded_at"], n["notice_ref"]))
        return out

    # ------------------------------------------------------------------
    # entitlement of one claim
    # ------------------------------------------------------------------
    def settle_entitlement(self, claim):
        r = self.r
        depot = claim.depot
        close_utc = r.window_utc(claim.named_round, depot)[1]
        head_value, head_source, head_at = self.head_count(claim)
        if head_value is None:
            return None
        ceiling_value, ceiling_at = r.ceiling_of(claim.block, claim.settlement_round)
        # amendment notices that reach this claim
        stale = 0
        applied = []
        for notice in self.notices_for(claim):
            if notice["target"] == "head_count":
                moment = head_at
            elif notice["target"] == "handling_ceiling":
                moment = parse_utc(ceiling_at) if ceiling_at else None
            else:
                moment = None
            if notice["target"] == "handling_ceiling" and ceiling_value is None:
                stale += 1
                continue
            if moment is None or not (moment < parse_utc(notice["recorded_at"]) < close_utc):
                stale += 1
                continue
            applied.append(notice)
        head_value = int(head_value)
        ceiling_value = int(ceiling_value) if ceiling_value is not None else None
        for notice in applied:
            amount = to_int(str(notice["adjustment"]))
            if notice["target"] == "head_count":
                head_value = max(0, head_value + amount)
            else:
                ceiling_value = max(0, (ceiling_value if ceiling_value is not None else 0) + amount)
        claim.head_count = head_value
        claim.head_source = head_source
        claim.head_recorded_utc = head_at
        claim.ceiling = ceiling_value
        self._amend_state["applied"] += len(applied)
        self._amend_state["stale"] += stale
        self.counted["RC_AMENDMENT_STALE"] += stale
        # entitlement
        factor = r.dose_factor(claim.region, claim.species, claim.age_class,
                              r.start_date[claim.settlement_round])
        if factor is None:
            factor = Decimal(0)
        raw = Decimal(head_value) * factor / Decimal(100)
        claim.entitlement_raw = raw
        claim.half_exact = (raw * 2) % 2 == 1
        entitlement = int(raw.quantize(Decimal(1), rounding=ROUND_HALF_UP))
        if claim.half_exact and raw < 0:
            entitlement = -int((-raw).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        claim.clamped = False
        if ceiling_value is not None and entitlement > ceiling_value:
            entitlement = ceiling_value
            claim.clamped = True
        claim.entitlement = entitlement
        return claim

    # ------------------------------------------------------------------
    # lots: state machine, observation, pool entry
    # ------------------------------------------------------------------
    def prepare_lots(self):
        r = self.r
        c = self.c
        units = c.units.get("lot_register.quantity", {})
        self.lot_pool_round = {}
        self.lot_hops = {}
        self.lot_usable = {}
        self.lot_content = {}
        self.lot_content_source = {}
        self.lot_writeoff_round = {}
        self.pooled_lots = []
        self.substituted = defaultdict(int)
        for lot_id, lot in sorted(r.lots.items()):
            basis = units.get("%s.%s" % (lot["depot"], lot["production_year"]))
            if basis is None:
                self.counted["RC_UNIT_UNDECLARED"] += 1
                continue
            if lot_id in r.assays:
                doses_per_unit = r.assays[lot_id]
                source = "assay"
            else:
                doses_per_unit = r.doses_per_unit(lot["depot"], lot["serotype"],
                                                   basis, lot["consign_date"])
                source = "reference"
                if doses_per_unit is None:
                    self.counted["RC_UNIT_UNDECLARED"] += 1
                    continue
            content = int((lot["quantity"] * doses_per_unit).to_integral_value(
                rounding="ROUND_FLOOR"))
            self.lot_content[lot_id] = content
            self.lot_content_source[lot_id] = source
            first_round = r.settlement_round.get(lot["consign_round"])
            if first_round is None:
                continue
            openings = [x for x in r.live if r.start_date[x] >= r.start_date[first_round]]
            region = c.region_of(lot["depot"])
            entered = False
            no_substitute = False
            illegal_counted = False
            for code in openings:
                open_local = r.window_local(code)[0]
                open_utc = r.window_utc(code, lot["depot"])[0]
                if lot["expiry_local"] <= open_local:
                    break
                chain = self.chain_in_force(lot_id, open_utc)
                if chain is None:
                    self.counted["RC_LOT_CYCLE"] += 1
                    break
                if not illegal_counted:
                    moved = self.count_illegal(chain)
                    if moved:
                        self.illegal_transitions += moved
                        illegal_counted = True
                state = self.state_of_chain(chain)
                if state != "released":
                    continue
                target = r.target_serotype(region, code, open_utc)
                path = r.substitution_path(lot["serotype"], target,
                                           open_local.date()) if target else None
                if path is None:
                    no_substitute = True
                    continue
                if entered:
                    continue
                hops, product = path
                self.lot_pool_round[lot_id] = code
                self.lot_hops[lot_id] = hops
                usable = Decimal(content) * product
                self.lot_usable[lot_id] = int(usable.to_integral_value(rounding="ROUND_FLOOR"))
                if self.chain_reinstated(chain):
                    self.reinstated_lots += 1
                if hops:
                    self.substituted[hops] += 1
                entered = True
                break
            if no_substitute:
                self.counted["RC_NO_SUBSTITUTE"] += 1
            if not entered:
                continue
            self.pooled_lots.append(lot_id)
            after_expiry = [x for x in r.live if r.window_local(x)[0] >= lot["expiry_local"]]
            if after_expiry:
                self.lot_writeoff_round[lot_id] = after_expiry[0]

    def chain_in_force(self, lot_id, instant):
        """Certificates in force, or None when they replace each other in a loop."""
        certs = [x for x in self.r.certs_of(lot_id) if x["issued_at"] <= instant]
        if not certs:
            return []
        by_ref = dict((x["cert_ref"], x) for x in certs)
        if self._loops(certs, by_ref):
            return None
        replaced = set(x["supersedes"] for x in certs if x["supersedes"])
        return [x for x in certs if x["cert_ref"] not in replaced]

    @staticmethod
    def _loops(certs, by_ref):
        for cert in certs:
            seen = {cert["cert_ref"]}
            current = cert
            while current["supersedes"] and current["supersedes"] in by_ref:
                nxt = current["supersedes"]
                if nxt in seen:
                    return True
                seen.add(nxt)
                current = by_ref[nxt]
        return False

    ALLOWED = {("quarantine", "released"), ("quarantine", "condemned"),
              ("released", "condemned"), ("condemned", "reinstated")}

    def _can_reinstate(self, cert):
        role = self.c.authority.get(cert["signed_by"], {})
        return bool(role.get("can_reinstate"))

    def state_of_chain(self, chain):
        """The state in force, `reinstated` reading as `released`."""
        state = "quarantine"
        for cert in chain:
            target = cert["state"]
            if target == "reinstated" and not self._can_reinstate(cert):
                continue
            if (state, target) in self.ALLOWED:
                state = "released" if target == "reinstated" else target
        return state

    def chain_reinstated(self, chain):
        """The chain in force holds a reinstatement that applied."""
        state = "quarantine"
        for cert in chain:
            target = cert["state"]
            if target == "reinstated" and not self._can_reinstate(cert):
                continue
            if (state, target) in self.ALLOWED:
                if target == "reinstated":
                    return True
                state = target
        return False

    def count_illegal(self, chain):
        """Certificates of the chain in force that made no move."""
        state = "quarantine"
        illegal = 0
        for cert in chain:
            target = cert["state"]
            if target == "reinstated" and not self._can_reinstate(cert):
                illegal += 1
                continue
            if (state, target) in self.ALLOWED:
                state = "released" if target == "reinstated" else target
            elif state != target:
                illegal += 1
        return illegal

    # ------------------------------------------------------------------
    # one pass over the rounds
    # ------------------------------------------------------------------
    def run(self):
        r = self.r
        c = self.c
        self.admit()
        self.build_claims()
        self.amend()
        self.prepare_lots()
        self.remaining = dict((lot_id, self.lot_usable[lot_id]) for lot_id in self.pooled_lots)
        self.lot_by_region = defaultdict(list)
        for lot_id in self.pooled_lots:
            self.lot_by_region[c.region_of(r.lots[lot_id]["depot"])].append(lot_id)
        self.carry = defaultdict(int)
        self.awarded_to_date = defaultdict(int)
        self.deferred_to_date = defaultdict(int)
        self.cells = {}
        self.cell_claims = {}
        self.ledger = []
        self.clearing = defaultdict(list)
        self.cleared_identities = {}
        self.extinguished_no_show = 0
        self.extinguished_epoch = 0
        self.ceiling_clamped = 0
        self.exact_half = 0
        self.attribute_overrides = 0
        self.head_sources = defaultdict(int)
        self.registry_blocks = set()
        self.remainder_claims = 0
        self.remainder_cells = 0
        self.blocks_settled = set()
        self.epoch_identities = set()
        self.round_claims = defaultdict(list)
        for claim in self.claim_by_key.values():
            self.round_claims[claim.settlement_round].append(claim)
        # identities of every block in every live round, for epoch changes
        self.identities = {}
        previous_code = None
        for code in r.live:
            for block_ref in r.master:
                identity = self.identity_of(block_ref, code)
                self.identities[(block_ref, code)] = identity
                if previous_code is not None:
                    earlier = self.identities.get((block_ref, previous_code))
                    if earlier is not None and earlier != identity:
                        if self.carry.get(earlier, 0) > 0:
                            self.extinguished_epoch += 1
                            self.carry[earlier] = 0
            previous_code = code
            open_local = r.window_local(code)[0]
            for region in c.regions():
                self.settle_cell(code, region, open_local)

        self.counted["RC_ILLEGAL_TRANSITION"] = self.illegal_transitions

        # surviving requisition rows whose stated species or age class differs
        for (identity, settlement), (survivor, inside, after) in self.groups.items():
            version = r.master_version(survivor.block, r.start_date[settlement])
            if version is None:
                continue
            if (survivor.species != version["species"]
                    or survivor.age_class != version["age_class"]):
                self.attribute_overrides += 1

        # amendments that decided nothing
        self.amendments_applied = self._amend_state["applied"]
        notices_seen = set()
        for claim in self.claim_by_key.values():
            if claim.entitlement is None:
                continue
            for notice in self.notices_for(claim):
                notices_seen.add(notice["notice_ref"])
        stale_extra = 0
        for notices in self.pending_amendments.values():
            for notice in notices:
                if notice["notice_ref"] not in notices_seen:
                    stale_extra += 1
        self.amendments_stale = self._amend_state["stale"] + stale_extra
        self.counted["RC_AMENDMENT_STALE"] = self.amendments_stale

    # ------------------------------------------------------------------
    def settle_cell(self, code, region, open_local):
        r = self.r
        c = self.c
        claims = [cl for cl in self.round_claims.get(code, []) if cl.region == region]
        # entitlement and head count
        settled = []
        for claim in claims:
            if self.settle_entitlement(claim) is None:
                self.rejects["RC_NO_HEADCOUNT"] += 1
                continue
            if claim.head_source == "registry":
                self.head_sources["registry"] += 1
                self.registry_blocks.add(claim.block)
            else:
                self.head_sources[claim.head_source] += 1
            if claim.clamped:
                self.ceiling_clamped += 1
            if claim.half_exact:
                self.exact_half += 1
            version = r.master_version(claim.block, r.start_date[code])
            if "#" in claim.identity:
                try:
                    epoch = int(claim.identity.split("#")[1])
                except ValueError:
                    epoch = 1
                if epoch > 1:
                    self.epoch_identities.add(claim.identity)
            self.blocks_settled.add(claim.identity)
            settled.append(claim)
        # carried claim into the round
        for claim in settled:
            claim.carried_in = self.carry.get(claim.identity, 0)
            claim.claimable = claim.entitlement + claim.carried_in
        # available doses of the cell
        depot = c.depot_of(region)
        open_utc = r.window_utc(code, depot)[0]
        available = 0
        available_lots = []
        for lot_id in self.lot_by_region.get(region, ()):
            lot = r.lots[lot_id]
            if self.lot_pool_round.get(lot_id) is None:
                continue
            if r.start_date[self.lot_pool_round[lot_id]] > r.start_date[code]:
                continue
            if lot["expiry_local"] <= open_local:
                continue
            chain = self.chain_in_force(lot_id, open_utc)
            if chain is None:
                continue
            if self.state_of_chain(chain) != "released":
                continue
            target = r.target_serotype(region, code, open_utc)
            path = r.substitution_path(lot["serotype"], target, open_local.date()) \
                if target else None
            if path is None:
                continue
            available += self.remaining[lot_id]
            available_lots.append(lot_id)
        # ladder
        tiers = c.props_int("tier.count")
        in_hand = available
        by_tier = defaultdict(list)
        for claim in settled:
            by_tier[claim.tier].append(claim)
        binding_tier = 0
        waterline = -1
        for tier in range(1, tiers + 1):
            group = sorted(by_tier.get(tier, ()), key=lambda cl: cl.identity)
            if not group:
                continue
            total = sum(cl.claimable for cl in group)
            if total <= in_hand:
                for cl in group:
                    cl.awarded = cl.claimable
                in_hand -= total
                continue
            waterline = 0
            while True:
                if sum(min(cl.claimable, waterline + 1) for cl in group) > in_hand:
                    break
                waterline += 1
            for cl in group:
                cl.awarded = min(cl.claimable, waterline)
            in_hand -= sum(cl.awarded for cl in group)
            short = [cl for cl in group if cl.claimable > cl.awarded]
            if in_hand and short:
                for cl in sorted(short, key=lambda x: x.identity)[:in_hand]:
                    cl.awarded += 1
                    cl.remainder_doses += 1
                    self.remainder_claims += 1
                in_hand = 0
            binding_tier = tier
            break
        if binding_tier == 0:
            waterline = -1
        # ledger order: tier ascending, then identity ascending
        ordered = sorted(settled, key=lambda cl: (cl.tier, cl.identity))
        # drawing
        lots_sorted = sorted(available_lots, key=lambda lot_id: (
            r.lots[lot_id]["expiry_local"], r.lots[lot_id]["lot_ref"],
            r.lots[lot_id]["production_year"]))
        for claim in ordered:
            claim.deferred = claim.claimable - claim.awarded
            need = claim.awarded
            claim.served_lot = ""
            claim.hops = 0
            for lot_id in lots_sorted:
                if need <= 0:
                    break
                have = self.remaining[lot_id]
                if have <= 0:
                    continue
                if claim.served_lot == "":
                    claim.served_lot = lot_id
                    claim.hops = self.lot_hops.get(lot_id, 0)
                drawn = min(have, need)
                self.remaining[lot_id] = have - drawn
                need -= drawn
        # outcome and reason
        for claim in ordered:
            award_reasons = self.c.reason_codes["award_reasons"]
            reason = None
            for entry in award_reasons:
                if self._reason_holds(entry["applies_when"], claim):
                    reason = entry["code"]
                    break
            claim.reason = reason
            claim.outcome = self.c.reason_codes["outcomes"][reason]
            self.awarded_to_date[claim.identity] += claim.awarded
            self.deferred_to_date[claim.identity] += claim.deferred
            claim.awarded_to_date = self.awarded_to_date[claim.identity]
            claim.deferred_to_date = self.deferred_to_date[claim.identity]
        # carried claim of the next round
        cap = c.props_int("carry.cap.multiple")
        for claim in ordered:
            carry = min(claim.deferred, cap * claim.entitlement)
            if carry > 0 and self._no_show(claim):
                carry = 0
                self.extinguished_no_show += 1
            claim.carry_forward = carry
            self.carry[claim.identity] = carry
        # clearing round
        total_claimable = sum(cl.claimable for cl in ordered)
        is_clearing = available > total_claimable
        cleared = 0
        if is_clearing:
            self.clearing[region].append(code)
            for block_ref in self.scope_blocks(region, code, ordered, open_local):
                identity = self.identities.get((block_ref, code))
                if identity is None:
                    continue
                if self.carry.get(identity, 0) > 0:
                    self.carry[identity] = 0
                    self.cleared_identities[(identity, code)] = True
                    cleared += 1
        self.cell_claims[(region, code)] = ordered
        self.cells[(region, code)] = {
            "region": region, "round": code, "available_doses": available,
            "claimable_doses": total_claimable,
            "awarded_doses": sum(cl.awarded for cl in ordered),
            "waterline": waterline, "binding_tier": binding_tier,
            "surplus_doses": available - sum(cl.awarded for cl in ordered),
            "cleared_balances": cleared, "written_off_doses": 0,
        }
        self.ledger.extend(ordered)
        if any(cl.remainder_doses for cl in ordered):
            self.remainder_cells += 1

    def _reason_holds(self, condition, claim):
        if condition.startswith("the claimable quantity for the settled claim is zero"):
            return claim.claimable == 0
        if condition.startswith("the awarded quantity equals the claimable quantity"):
            return claim.awarded == claim.claimable
        if "above zero and below the claimable" in condition:
            return 0 < claim.awarded < claim.claimable
        if "zero while the claimable quantity is above zero" in condition:
            return claim.awarded == 0 and claim.claimable > 0
        return False

    def _no_show(self, claim):
        r = self.r
        for code in r.rounds_in_play(claim.settlement_round):
            for row in r.block_events.get((claim.block, code), ()):
                if row["event"] == "no_show":
                    return True
        return False

    def identity_of(self, block_ref, code):
        """Identity of a block for a round, and the carry it stands on."""
        r = self.r
        version = r.master_version(block_ref, r.start_date[code])
        if version is None:
            return None
        depot = self.c.depot_of(version["region"])
        open_utc = r.window_utc(code, depot)[0]
        epoch = 1 + sum(1 for when in r.block_restocks.get(block_ref, ())
                        if when < open_utc)
        return "%s#%d" % (block_ref, epoch)

    def scope_blocks(self, region, code, ordered, open_local):
        """Blocks whose carried claim a clearing round of this scope reaches."""
        r = self.r
        if self.scope == "none":
            return []
        if self.scope == "fully_awarded_only":
            return set(cl.block for cl in ordered if cl.awarded == cl.claimable)
        if self.scope == "tier1_only":
            return set(cl.block for cl in ordered if cl.tier == 1)
        blocks = []
        for block_ref in r.master:
            version = r.master_version(block_ref, r.start_date[code])
            if version and version["region"] == region:
                blocks.append(block_ref)
        return blocks

    # ------------------------------------------------------------------
    # write offs
    # ------------------------------------------------------------------
    def write_off(self):
        r = self.r
        for lot_id, code in sorted(self.lot_writeoff_round.items()):
            region = self.c.region_of(r.lots[lot_id]["depot"])
            cell = self.cells.get((region, code))
            if cell is None:
                continue
            cell["written_off_doses"] += self.remaining.get(lot_id, 0)
            self.remaining[lot_id] = 0

    # ------------------------------------------------------------------
    # clearance evidence
    # ------------------------------------------------------------------
    def clearance_matches(self):
        """(matching, conflicting) clearance log entries under this reading."""
        r = self.r
        good = 0
        bad = 0
        for entry in self.c.clearance:
            region = entry.get("region")
            code = entry.get("round")
            block = entry.get("block", "")
            cleared = entry.get("balance_cleared")
            if not region or not code or not block.startswith("BLK-"):
                continue
            if code not in r.live:
                continue
            if (region, code) not in self.cells:
                continue
            predicted = self.predicted_cleared(region, code, block.split("#")[0],
                                               self.cell_claims.get((region, code), ()))
            if (cleared == "yes") == predicted:
                good += 1
            else:
                bad += 1
        return good, bad

    def predicted_cleared(self, region, code, block_ref, ordered=None):
        """Did this run reach the carried claim of the block in the round?"""
        r = self.r
        if code not in self.clearing.get(region, ()):
            return False
        version = r.master_version(block_ref, r.start_date[code])
        if version is None or version["region"] != region:
            return False
        if self.scope == "region_wide":
            return True
        if ordered is None:
            ordered = self.cell_claims.get((region, code), ())
        if self.scope == "fully_awarded_only":
            return any(cl.block == block_ref and cl.awarded == cl.claimable
                       for cl in ordered)
        if self.scope == "tier1_only":
            return any(cl.block == block_ref and cl.tier == 1 for cl in ordered)
        return False


def settle_run(corpus, scope, governing):
    settlement = Settlement(corpus, scope)
    settlement.set_governing(governing)
    settlement.run()
    settlement.write_off()
    return settlement


def governing_source(corpus):
    """Which source governs head counts on each side of the cutover."""
    r = Registers(corpus)
    cutover = parse_date(corpus.props["cutover.date"])
    votes = {"before": defaultdict(int), "after": defaultdict(int)}
    for entry in corpus.governance:
        code = entry.get("round")
        source = entry.get("governed_by")
        block = entry.get("block", "")
        if not code or not source or source == "registry" or "#" not in block:
            continue
        if code not in r.start_date:
            continue
        side = "before" if r.start_date[code] < cutover else "after"
        votes[side][source] += 1
    candidates = ["field_intake", "dispatch_stream"]
    out = []
    for side in ("before", "after"):
        tally = votes[side]
        pick = max(sorted(tally), key=lambda k: tally[k]) if tally else candidates[0]
        out.append(pick)
    return (out[0], out[1])


def choose_run(corpus):
    """Settle under each clearance scope the log could settle on."""
    governing = governing_source(corpus)
    best = None
    for scope in ("region_wide", "fully_awarded_only", "tier1_only", "none"):
        settlement = settle_run(corpus, scope, governing)
        good, bad = settlement.clearance_matches()
        if bad == 0:
            return scope, settlement, governing, (good, bad)
        if best is None or bad < best[3][1]:
            best = (scope, settlement, governing, (good, bad))
    return best


class App(object):
    def __init__(self, corpus, out_folder):
        self.c = corpus
        self.out = out_folder

    def build(self):
        self.scope, self.s, governing, evidence = choose_run(self.c)
        self.governing = governing
        self.evidence = evidence
        self.write_documents()

    def write_documents(self):
        s = self.s
        c = self.c
        regions = c.regions()
        segments = c.segments()
        rounds = list(s.r.live)
        position = dict((code, i) for i, code in enumerate(rounds))
        ledger_by_region = defaultdict(list)
        for entry in s.ledger:
            ledger_by_region[entry.region].append(entry)
        for region in regions:
            entries = sorted(ledger_by_region.get(region, []),
                             key=lambda e: (position[e.round], e.tier, e.identity))
            cells = [self.cell_entry(region, code) for code in rounds
                     if (region, code) in s.cells]
            self.dump("region_%s.json" % region, {
                "region": region,
                "rounds": rounds,
                "ledger": [self.ledger_entry(e) for e in entries],
                "cells": cells,
            })
        for segment in segments:
            self.dump("segment_%s.json" % segment,
                      self.segment_doc(segment, regions, rounds))
        self.dump("summary.json", self.summary_doc(regions, segments, rounds))
        self.dump("policy_audit.json", self.audit_doc(regions, rounds))
        self.dump("data_quality.json", self.quality_doc())

    def ledger_entry(self, e):
        return {
            "block": e.identity,
            "round": e.round,
            "tier": e.tier,
            "entitlement_doses": e.entitlement,
            "carried_claim_doses": e.carried_in,
            "claimable_doses": e.claimable,
            "awarded_doses": e.awarded,
            "deferred_doses": e.deferred,
            "awarded_to_date": e.awarded_to_date,
            "deferred_to_date": e.deferred_to_date,
            "carry_forward_doses": e.carry_forward,
            "served_lot": e.served_lot,
            "substitution_hops": e.hops,
            "outcome": e.outcome,
            "reason": e.reason,
        }

    def cell_entry(self, region, code):
        cell = self.s.cells[(region, code)]
        return {
            "round": code,
            "available_doses": cell["available_doses"],
            "claimable_doses": cell["claimable_doses"],
            "awarded_doses": cell["awarded_doses"],
            "waterline": cell["waterline"],
            "binding_tier": cell["binding_tier"],
            "surplus_doses": cell["surplus_doses"],
            "cleared_balances": cell["cleared_balances"],
            "written_off_doses": cell["written_off_doses"],
        }

    def segment_doc(self, segment, regions, rounds):
        s = self.s
        doc = {"segment": segment, "regions": [], "rounds": []}
        for region in regions:
            entries = [e for e in s.ledger if e.region == region and e.segment == segment]
            doc["regions"].append({
                "region": region,
                "claims": len(entries),
                "awarded_doses": sum(e.awarded for e in entries),
                "claimable_doses": sum(e.claimable for e in entries),
                "deferred_doses": sum(e.deferred for e in entries),
                "carry_forward_doses": sum(e.carry_forward for e in entries),
                "full": sum(1 for e in entries if e.outcome == "full"),
                "partial": sum(1 for e in entries if e.outcome == "partial"),
                "zero": sum(1 for e in entries if e.outcome == "zero"),
                "declined": sum(1 for e in entries if e.outcome == "declined"),
            })
        for code in rounds:
            entries = [e for e in s.ledger if e.round == code and e.segment == segment]
            doc["rounds"].append({
                "round": code,
                "claims": len(entries),
                "awarded_doses": sum(e.awarded for e in entries),
                "deferred_doses": sum(e.deferred for e in entries),
            })
        return doc

    def summary_doc(self, regions, segments, rounds):
        s = self.s
        cell_keys = [(reg, code) for reg in regions for code in rounds
                     if (reg, code) in s.cells]
        doc = {
            "live_rounds": len(rounds),
            "skipped_rounds": len(s.r.skipped),
            "claims_settled": len(s.ledger),
            "claims_rejected": sum(s.rejects.values()),
            "blocks_settled": len(s.blocks_settled),
            "claimable_doses": sum(e.claimable for e in s.ledger),
            "awarded_doses": sum(e.awarded for e in s.ledger),
            "deferred_doses": sum(e.deferred for e in s.ledger),
            "carry_forward_doses": sum(e.carry_forward for e in s.ledger),
            "available_doses": sum(s.cells[k]["available_doses"] for k in cell_keys),
            "surplus_doses": sum(s.cells[k]["surplus_doses"] for k in cell_keys),
            "written_off_doses": sum(s.cells[k]["written_off_doses"] for k in cell_keys),
            "regions": [],
            "segments": [],
        }
        for region in regions:
            entries = [e for e in s.ledger if e.region == region]
            doc["regions"].append({
                "region": region,
                "claims": len(entries),
                "awarded_doses": sum(e.awarded for e in entries),
                "deferred_doses": sum(e.deferred for e in entries),
            })
        for segment in segments:
            entries = [e for e in s.ledger if e.segment == segment]
            doc["segments"].append({
                "segment": segment,
                "claims": len(entries),
                "awarded_doses": sum(e.awarded for e in entries),
            })
        return doc

    def audit_doc(self, regions, rounds):
        s = self.s
        c = self.c
        binding = defaultdict(int)
        for region in regions:
            for code in rounds:
                cell = s.cells.get((region, code))
                if cell is not None:
                    binding[str(cell["binding_tier"])] += 1
        binding_tiers = {}
        for key in ["0"] + [str(i) for i in range(1, c.props_int("tier.count") + 1)]:
            binding_tiers[key] = binding.get(key, 0)
        alias_hops = {}
        for i in range(1, c.props_int("alias.max_hops") + 1):
            alias_hops[str(i)] = s.alias_hops.get(i, 0)
        substituted = {}
        for i in range(1, c.props_int("substitution.max_hops") + 1):
            substituted[str(i)] = s.substituted.get(i, 0)
        return {
            "governing_source": {"before_cutover": s.governing[0],
                                 "from_cutover": s.governing[1]},
            "balance_clearance_scope": s.scope,
            "alias_hops": alias_hops,
            "epoch_identities": len(s.epoch_identities),
            "collapsed_duplicates": s.counted.get("RC_DUPLICATE_COLLAPSED", 0),
            "stale_revisions": s.counted.get("RC_STALE_REVISION", 0),
            "attribute_overrides": s.attribute_overrides,
            "amendments_applied": s.amendments_applied,
            "amendments_stale": s.amendments_stale,
            "amendments_unauthorised": s.amendments_unauthorised,
            "ceiling_clamped": s.ceiling_clamped,
            "exact_half_entitlements": s.exact_half,
            "substituted_lots": substituted,
            "lots_unresolved_cycle": s.counted.get("RC_LOT_CYCLE", 0),
            "lots_without_substitute": s.counted.get("RC_NO_SUBSTITUTE", 0),
            "illegal_transitions": s.illegal_transitions,
            "reinstated_lots": s.reinstated_lots,
            "unit_undeclared_lots": s.counted.get("RC_UNIT_UNDECLARED", 0),
            "extinguished_no_show": s.extinguished_no_show,
            "extinguished_epoch": s.extinguished_epoch,
            "binding_tiers": binding_tiers,
            "clearing_rounds": [{"region": region,
                                 "rounds": list(s.clearing.get(region, []))}
                                for region in regions],
        }

    def quality_doc(self):
        s = self.s
        c = self.c
        rejects = dict((code, s.rejects.get(code, 0))
                       for code in c.reason_codes["reject_codes"])
        counted = dict((code, s.counted.get(code, 0))
                       for code in c.reason_codes["counted_codes"])
        counted["RC_HEADER_GAP"] = c.header_gaps
        keys = ["field_intake", "dispatch_stream", "registry", "visit_events",
                "amendment_notices", "lot_register", "release_certificates", "assay",
                "reference"]
        mapping = [("field_intake", "field_intake"),
                   ("dispatch_stream", "dispatch_stream"),
                   ("registry", "registry"),
                   ("visit_events", "visit_events"),
                   ("amendments", "amendment_notices"),
                   ("lot_register", "lot_register"),
                   ("release_certificates", "release_certificates"),
                   ("assay", "assay")]
        rows = {}
        for key in keys:
            total = 0
            if key == "reference":
                for logical in c.reference_tier_sources():
                    total += c.source_rows.get(logical, 0)
            else:
                for logical, target in mapping:
                    if target == key:
                        total += c.source_rows.get(logical, 0)
            rows[key] = total
        return {"rejects": rejects, "counted": counted, "source_rows": rows}

    def dump(self, name, doc):
        path = os.path.join(self.out, name)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(doc, handle, indent=2)
            handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description="Campaign dose ration settlement")
    parser.add_argument("--data", required=True, help="corpus folder")
    parser.add_argument("--out", required=True, help="output folder")
    args = parser.parse_args()
    if not os.path.isdir(args.out):
        os.makedirs(args.out)
    corpus = Corpus(args.data)
    App(corpus, args.out).build()


if __name__ == "__main__":
    main()
