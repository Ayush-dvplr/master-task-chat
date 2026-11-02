#!/usr/bin/env python3
"""Derive the aa314fee-a873-5778-9d55-e8892e6d7cda artifacts from a flat evidence corpus."""

from __future__ import annotations

import argparse
import bisect
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

SITES = ["North", "South", "West", "East"]
SEGMENTS = ["commercial", "public"]
OUTCOMES = ["FULL", "PARTIAL", "ZERO", "EXCLUDED"]
CYCLE_IDS = ["C%02d" % k for k in range(1, 25)]
SOURCE_OF_PREFIX = {"OBK": "order_book", "REG": "contract_registry", "LGI": "legacy_intake"}
SOURCE_RANK = {"order_book": 0, "contract_registry": 1, "legacy_intake": 2}


def half_up(numerator: int, denominator: int) -> int:
    # Single rounding stage for the whole walk, as the errata requires.
    return (2 * numerator + denominator) // (2 * denominator)


def parse_instant(text):
    raw = (text or "").strip()
    if not raw or raw in {"\\N", "-"}:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1]
    elif raw.endswith("+00:00"):
        raw = raw[:-6]
    return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S")


def parse_local(text):
    raw = (text or "").strip()
    if not raw:
        return None
    return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S")


def parse_compact(text):
    raw = (text or "").strip()
    if not raw:
        return None
    return datetime.strptime(raw, "%Y%m%d%H%M%S")


def parse_declared_value(text) -> int:
    raw = (text or "").strip()
    if raw.startswith("(") and raw.endswith(")"):
        return -int(raw[1:-1])
    return int(raw)


def canonical_id(code):
    raw = (code or "").strip()
    if not raw:
        return None
    body = raw.split("-", 1)
    if len(body) != 2 or not body[1].isdigit():
        return None
    return "CUS-%04d" % int(body[1])


class Counters:
    def __init__(self) -> None:
        self.declared = {}
        self.parsed = {}
        self.admitted = {}
        self.late = {}
        self.header_gaps = {}
        self.tally = {}

    def count(self, key: str, amount: int = 1) -> None:
        self.tally[key] = self.tally.get(key, 0) + amount

    def file_rows(self, source, name, declared, parsed, admitted, late) -> None:
        self.declared[source] = self.declared.get(source, 0) + (parsed if declared is None else declared)
        self.parsed[source] = self.parsed.get(source, 0) + parsed
        self.admitted[source] = self.admitted.get(source, 0) + admitted
        self.late[source] = self.late.get(source, 0) + late
        if declared is not None and declared != parsed:
            self.header_gaps[name] = declared - parsed


class Policy:
    """Configuration read from the shipped declarations rather than assumed."""

    def __init__(self, data: Path) -> None:
        self.sections = self._read_ini(data / "derivation_policy.ini")
        self.units = self._read_ini(data / "unit_declarations.ini")
        self.properties = self._read_properties(data / "source_declarations.properties")
        self.vocabulary = json.loads((data / "reason_codes.json").read_text())
        base = self.sections["defaults"]
        self.as_of_text = base["as_of_instant"]
        self.as_of = parse_instant(self.as_of_text)
        self.collapse = timedelta(minutes=int(base["collapse_window_minutes"]))
        self.max_hops = int(base["max_substitution_hops"])
        self.unranked_rank = int(base["unranked_commitment_rank"])
        self.cutover_cycle = self.properties["precedence.cutover_cycle"]
        self.skew = {site: int(self._site_value(site, "recorder_skew_seconds")) for site in SITES}
        self.lot_wafers = int(self.units["order_book"]["lot_size_wafers"])
        self.lot_equiv = int(self.units["capacity"]["lot_equivalent_wafers"])
        self.factor_scale = 100 if self.units["substitution"]["factor_scale"] == "per_100" else 1
        self.intake_scale = 100 if self.units["intake"]["quantity_scale"] == "hundredths" else 1
        self.reason_order = list(self.vocabulary["reason_precedence"])
        self.files = {}
        for key, value in self.properties.items():
            if key.startswith("source.") and (key.endswith(".files") or key.endswith(".audit")):
                code = key.split(".")[1]
                self.files.setdefault(code, [])
                for name in [part.strip() for part in value.replace(",", " ").split()]:
                    if name and name not in self.files[code]:
                        self.files[code].append(name)
        self.source_codes = sorted(self.files)

    @staticmethod
    def _read_ini(path: Path):
        sections = {}
        current = None
        for line in path.read_text().splitlines():
            text = line.strip()
            if not text or text.startswith("#") or text.startswith(";"):
                continue
            if text.startswith("[") and text.endswith("]"):
                current = text[1:-1].strip()
                sections.setdefault(current, {})
                continue
            if "=" in text and current is not None:
                key, _, value = text.partition("=")
                sections[current][key.strip()] = value.strip()
        return sections

    @staticmethod
    def _read_properties(path: Path):
        values = {}
        pending = ""
        for line in path.read_text().splitlines():
            text = line.strip()
            if not text or text.startswith("#") or text.startswith("!"):
                continue
            if pending:
                text = pending + " " + text
                pending = ""
            if text.endswith("\\"):
                pending = text[:-1].strip()
                continue
            cut = len(text)
            for mark in ("=", ":"):
                found = text.find(mark)
                if found != -1:
                    cut = min(cut, found)
            if cut == len(text):
                continue
            values[text[:cut].strip()] = text[cut + 1:].strip()
        return values

    def _site_value(self, site, key):
        name = "site:" + site
        seen = set()
        while name and name not in seen:
            seen.add(name)
            section = self.sections.get(name, {})
            if key in section:
                return section[key]
            name = section.get("inherits", "").strip()
        return self.sections["defaults"][key]

    def governing_source(self, field, before, settled):
        key = "precedence.%s.%s" % ("before_cutover" if before else "from_cutover", field)
        if key in self.properties:
            return self.properties[key]
        return settled


class Clock:
    """Site local time from the shipped marks, with repeated and missing windows."""

    def __init__(self, data: Path, counters: Counters) -> None:
        self.marks = {site: {} for site in SITES}
        parsed = 0
        with (data / "site_clock_marks.csv").open() as handle:
            for row in csv.DictReader(handle):
                parsed += 1
                entry = (row["from_local_time"], int(row["utc_offset_minutes"]))
                self.marks[row["site"]].setdefault(row["local_date"], []).append(entry)
        counters.file_rows("CLK", "site_clock_marks.csv", None, parsed, parsed, 0)
        self.starts = {}
        for site in SITES:
            points = []
            for index in range(1, 26):
                if index == 25:
                    local = datetime(2032, 1, 1, 6, 0, 0)
                else:
                    day = 1 if index % 2 == 1 else 16
                    local = datetime(2031, (index + 1) // 2, day, 6, 0, 0)
                points.append(self.to_utc(site, local, 0)[0])
            self.starts[site] = points

    def to_utc(self, site, local, fold):
        rows = self.marks[site][local.strftime("%Y-%m-%d")]
        if len(rows) == 1:
            return local - timedelta(minutes=rows[0][1]), ""
        before = rows[0][1]
        after = rows[1][1]
        hour, minute, second = (int(part) for part in rows[1][0].split(":"))
        edge = local.replace(hour=hour, minute=minute, second=second, microsecond=0)
        if after < before:
            gap = timedelta(minutes=before - after)
            if edge - gap <= local < edge:
                return local - timedelta(minutes=before if fold == 0 else after), "ambiguous"
            return local - timedelta(minutes=before if local < edge else after), ""
        gap = timedelta(minutes=after - before)
        if edge <= local < edge + gap:
            return (local + gap) - timedelta(minutes=after), "shifted"
        return local - timedelta(minutes=before if local < edge else after), ""

    def start(self, site, index):
        return self.starts[site][index - 1]

    def cycle_of(self, site, instant):
        points = self.starts[site]
        if instant < points[0] or instant >= points[24]:
            return None
        return bisect.bisect_right(points, instant)


class Ledgered:
    """A request assembled from one or more source rows."""

    __slots__ = (
        "rows", "site", "identity", "customer_id", "epoch", "segment", "ref", "cycle",
        "effective", "quantity_wafers", "node", "served", "hops", "numerator",
        "denominator", "walk_error", "state", "reason", "quantity_equiv", "ceiling_equiv",
        "ceiling_wafers", "carried_in", "claim", "floor_equiv", "granted", "granted_wafers",
        "deficit", "carried_out", "granted_to_date", "deficit_to_date", "outcome",
        "before_cutover",
    )

    def __init__(self) -> None:
        self.rows = []
        self.floor_equiv = 0
        self.carried_in = 0
        self.claim = 0
        self.granted = 0
        self.granted_wafers = 0
        self.deficit = 0
        self.carried_out = 0
        self.granted_to_date = 0
        self.deficit_to_date = 0
        self.reason = "NONE"
        self.state = "approved"
        self.hops = 0
        self.served = ""
        self.outcome = "EXCLUDED"


def write_json(path: Path, payload) -> None:
    with path.open("w") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)


class Corpus:
    """Reference tables and the governing lookups built over them."""

    def __init__(self, data: Path, policy: Policy, clock: Clock, counters: Counters) -> None:
        self.data = data
        self.policy = policy
        self.clock = clock
        self.counters = counters
        self._group_cache = {}
        self._edge_cache = {}
        self._walk_cache = {}
        self._ceiling_cache = {}
        self._endorse_cache = {}
        self._load_customers()
        self._load_aliases()
        self._load_capacity()
        self._load_substitution()
        self._load_ceilings()
        self._load_commitments()
        self._load_authority()
        self._load_audit()
        self._load_retractions()

    def local(self, site, text, fold):
        instant, flag = self.clock.to_utc(site, parse_local(text), int(fold or 0))
        if flag == "ambiguous":
            self.counters.count("fold_disambiguated")
        elif flag == "shifted":
            self.counters.count("gap_shifted")
        return instant

    def table(self, name, source, delimiter=","):
        """Rows of one delimited file, with the declared count kept for the data quality report."""
        declared = None
        rows = []
        with (self.data / name).open(newline="") as handle:
            lines = handle.read().splitlines()
        start = 0
        if lines and lines[0].startswith("#"):
            start = 1
            for part in lines[0].lstrip("#").split():
                if part.startswith("declared_rows="):
                    declared = int(part.split("=", 1)[1])
        reader = csv.reader(lines[start:], delimiter=delimiter)
        header = next(reader)
        for fields in reader:
            if not fields:
                continue
            row = {}
            for index, title in enumerate(header):
                row[title] = fields[index] if index < len(fields) else None
            row["_fields"] = fields
            rows.append(row)
        admitted = []
        late = 0
        for row in rows:
            stamp = parse_instant(row.get("recorded_utc"))
            if stamp is not None and stamp > self.policy.as_of:
                late += 1
                continue
            admitted.append(row)
        self.counters.file_rows(source, name, declared, len(rows), len(admitted), late)
        return admitted

    def _load_customers(self):
        self.epochs = {}
        for row in self.table("customer_master.csv", "MST"):
            key = (row["customer_id"], int(row["epoch_seq"]))
            record = self.epochs.get(key)
            if record is None:
                record = {
                    "id": row["customer_id"],
                    "seq": int(row["epoch_seq"]),
                    "from": parse_instant(row["epoch_from_utc"]),
                    "to": parse_instant(row["epoch_to_utc"]),
                    "segment": row["segment"],
                    "home": row["home_site"],
                    "status_rows": [],
                }
                self.epochs[key] = record
            record["status_rows"].append(
                (parse_instant(row["effective_utc"]), int(row["revision_seq"]), row["status"])
            )
        self.by_customer = {}
        for (cid, seq), record in self.epochs.items():
            record["status_rows"].sort(key=lambda item: (item[0], item[1]))
            self.by_customer.setdefault(cid, []).append(record)
        for cid in self.by_customer:
            self.by_customer[cid].sort(key=lambda record: record["seq"])

    def epoch_at(self, customer_id, instant):
        records = self.by_customer.get(customer_id)
        if not records:
            return None
        for record in records:
            upper = record["to"]
            if record["from"] <= instant and (upper is None or instant < upper):
                return record
        last = records[-1]
        if last["to"] is not None and instant >= last["to"]:
            return last
        return records[0]

    @staticmethod
    def status_at(record, instant):
        state = "active"
        for effective, _revision, value in record["status_rows"]:
            if effective <= instant:
                state = value
        return state

    def _load_aliases(self):
        self.aliases = {}
        for row in self.table("customer_alias_map.csv", "ALS"):
            self.aliases.setdefault(row["alias_code"], []).append(
                (
                    parse_instant(row["effective_utc"]),
                    int(row["revision_seq"]),
                    parse_instant(row["expires_utc"]),
                    row["target_code"],
                )
            )
        for code in self.aliases:
            self.aliases[code].sort(key=lambda item: (item[0], item[1]))

    def resolve_code(self, code, instant):
        current = (code or "").strip()
        for _hop in range(4):
            if current.startswith("CUS-"):
                return current
            options = [
                item
                for item in self.aliases.get(current, [])
                if item[0] <= instant and (item[2] is None or instant < item[2])
            ]
            if not options:
                return None
            current = options[-1][3]
        return None

    def _load_capacity(self):
        self.capacity_rows = {}
        for row in self.table("site_capacity_declarations.csv", "CAP"):
            raw = row["value"]
            if raw.strip().startswith("("):
                self.counters.count("paren_negatives")
            if row["unit"] == "lot_equivalents":
                self.counters.count("lot_unit_rows")
            entry = {
                "group": row["tool_group"],
                "basis": row["basis"],
                "value": parse_declared_value(raw) * (self.policy.lot_equiv if row["unit"] == "lot_equivalents" else 1),
                "status": row["status"],
                "nodes": [part for part in row["nodes"].split("|") if part],
                "eff": self.local(row["site"], row["effective_local"], row["fold"]),
                "rev": int(row["revision_seq"]),
            }
            self.capacity_rows.setdefault((row["site"], row["cycle"]), []).append(entry)

    def groups(self, site, cycle):
        key = (site, cycle)
        found = self._group_cache.get(key)
        if found is not None:
            return found
        start = self.clock.start(site, int(cycle[1:]))
        held = {}
        for entry in self.capacity_rows.get(key, []):
            held.setdefault(entry["group"], []).append(entry)
        result = {}
        for group, entries in held.items():
            heads = [item for item in entries if item["basis"] == "absolute" and item["eff"] <= start]
            if not heads:
                continue
            head = max(heads, key=lambda item: (item["eff"], item["rev"]))
            value = head["value"]
            deltas = [
                item
                for item in entries
                if item["basis"] == "delta" and head["eff"] <= item["eff"] <= start
            ]
            for item in sorted(deltas, key=lambda row: (row["eff"], row["rev"])):
                value += item["value"]
            result[group] = (max(0, value), head["status"], head["nodes"])
        capacity = sum(value for value, status, _nodes in result.values() if status == "online")
        qualified = set()
        for value, status, nodes in result.values():
            if status == "online":
                qualified.update(nodes)
        self._group_cache[key] = (capacity, qualified)
        return self._group_cache[key]

    def _load_substitution(self):
        self.edge_rows = {}
        for row in self.table("node_substitution_factors.csv", "SUB"):
            entry = {
                "from": row["from_node"],
                "to": row["to_node"],
                "factor": int(row["factor_per_100"]),
                "status": row["status"],
                "eff": self.local(row["site"], row["effective_local"], row["fold"]),
                "rev": int(row["revision_seq"]),
            }
            self.edge_rows.setdefault((row["site"], row["cycle"]), []).append(entry)

    def edges(self, site, cycle):
        key = (site, cycle)
        found = self._edge_cache.get(key)
        if found is not None:
            return found
        start = self.clock.start(site, int(cycle[1:]))
        best = {}
        for entry in self.edge_rows.get(key, []):
            if entry["eff"] > start:
                continue
            pair = (entry["from"], entry["to"])
            current = best.get(pair)
            if current is None or (entry["eff"], entry["rev"]) > (current["eff"], current["rev"]):
                best[pair] = entry
        adjacency = {}
        for (origin, target), entry in best.items():
            if entry["status"] != "in_force":
                continue
            adjacency.setdefault(origin, []).append((entry["factor"], target))
        for origin in adjacency:
            adjacency[origin].sort()
        self._edge_cache[key] = adjacency
        return adjacency

    def walk(self, site, cycle, node):
        key = (site, cycle, node)
        found = self._walk_cache.get(key)
        if found is not None:
            return found
        _capacity, qualified = self.groups(site, cycle)
        adjacency = self.edges(site, cycle)
        seen = [node]
        current = node
        numerator = 1
        denominator = 1
        hops = 0
        while True:
            if current in qualified:
                result = (current, hops, numerator, denominator, "")
                break
            if hops >= self.policy.max_hops or current not in adjacency:
                result = (None, hops, numerator, denominator, "NO_QUALIFIED_NODE")
                break
            factor, target = adjacency[current][0]
            numerator *= factor
            denominator *= self.policy.factor_scale
            hops += 1
            if target in seen:
                result = (None, hops, numerator, denominator, "UNRESOLVABLE_SUB_CYCLE")
                break
            seen.append(target)
            current = target
        self._walk_cache[key] = result
        return result

    def _load_ceilings(self):
        self.ceiling_rows = {}
        for index in (1, 2, 3):
            name = "entitlement_ceilings_p%d.csv" % index
            for row in self.table(name, "CEIL"):
                if row["unit"] == "lots":
                    self.counters.count("lot_unit_rows")
                entry = {
                    "value": int(row["ceiling"]) * (self.policy.lot_wafers if row["unit"] == "lots" else 1),
                    "eff": self.local(row["declaring_site"], row["effective_local"], row["fold"]),
                    "rev": int(row["revision_seq"]),
                }
                self.ceiling_rows.setdefault((row["customer_id"], int(row["epoch_seq"])), []).append(entry)

    def ceiling(self, customer_id, epoch_seq, site, cycle):
        key = (customer_id, epoch_seq, site, cycle)
        if key in self._ceiling_cache:
            return self._ceiling_cache[key]
        start = self.clock.start(site, int(cycle[1:]))
        options = [
            entry for entry in self.ceiling_rows.get((customer_id, epoch_seq), []) if entry["eff"] <= start
        ]
        value = None
        if options:
            value = max(options, key=lambda entry: (entry["eff"], entry["rev"]))["value"]
        self._ceiling_cache[key] = value
        return value

    def _load_commitments(self):
        self.agreement_rows = {}
        self.agreement_meta = {}
        for row in self.table("commitment_agreements.csv", "AGR"):
            if row["unit"] == "lots":
                self.counters.count("lot_unit_rows")
            agreement = row["agreement_id"]
            self.agreement_meta[agreement] = {
                "customer": row["customer_id"],
                "site": row["site"],
                "recurrence": row["recurrence"],
                "first": int(row["first_cycle"][1:]),
                "until": int(row["until_cycle"][1:]),
            }
            self.agreement_rows.setdefault(agreement, []).append(
                {
                    "value": int(row["floor"]) * (self.policy.lot_wafers if row["unit"] == "lots" else 1),
                    "local": row["effective_local"],
                    "rev": int(row["revision_seq"]),
                }
            )
        self.rank_rows = {}
        for row in self.table("priority_register.csv", "PRI"):
            self.rank_rows.setdefault(row["agreement_id"], []).append(
                {
                    "rank": int(row["priority_rank"]),
                    "local": row["effective_local"],
                    "rev": int(row["revision_seq"]),
                }
            )
        self.exceptions = {}
        for row in self.table("commitment_exceptions.csv", "EXC"):
            self.exceptions.setdefault((row["agreement_id"], row["cycle"]), []).append(
                {
                    "id": row["exception_id"],
                    "action": row["action"],
                    "target": (row["target_cycle"] or "").strip(),
                    "approval": row["approval_ref"],
                    "recorded": parse_instant(row["recorded_utc"]),
                }
            )
        for agreement, rows in self.agreement_rows.items():
            site = self.agreement_meta[agreement]["site"]
            for entry in rows:
                entry["eff"] = self.local(site, entry["local"], 0)
            rows.sort(key=lambda entry: (entry["eff"], entry["rev"]))
        for agreement, rows in self.rank_rows.items():
            meta = self.agreement_meta.get(agreement)
            site = meta["site"] if meta else SITES[0]
            for entry in rows:
                entry["eff"] = self.local(site, entry["local"], 0)
            rows.sort(key=lambda entry: (entry["eff"], entry["rev"]))

    def due(self, agreement, index):
        meta = self.agreement_meta[agreement]
        if index < meta["first"] or index > meta["until"]:
            return False
        recurrence = meta["recurrence"]
        if recurrence == "every_cycle":
            return True
        if recurrence == "alternate_from_first":
            return (index - meta["first"]) % 2 == 0
        return index % 2 == 1

    def floor_wafers(self, agreement, site, cycle):
        start = self.clock.start(site, int(cycle[1:]))
        options = [entry for entry in self.agreement_rows.get(agreement, []) if entry["eff"] <= start]
        if not options:
            return None
        return options[-1]["value"]

    def rank_of(self, agreement, site, cycle):
        start = self.clock.start(site, int(cycle[1:]))
        options = [entry for entry in self.rank_rows.get(agreement, []) if entry["eff"] <= start]
        if not options:
            return self.policy.unranked_rank
        return options[-1]["rank"]

    def _load_authority(self):
        self.authority = {}
        for row in self.table("authority_roles.csv", "AUT"):
            key = (row["approver_id"], row["role"], row["scope"])
            entry = {
                "from": parse_instant(row["effective_utc"]),
                "to": parse_instant(row["expires_utc"]),
                "rev": int(row["revision_seq"]),
                "scope": row["scope"],
            }
            current = self.authority.get(key)
            if current is None or (entry["from"], entry["rev"]) > (current["from"], current["rev"]):
                self.authority[key] = entry
        self.by_approver = {}
        for (approver, _role, _scope), entry in self.authority.items():
            self.by_approver.setdefault(approver, []).append(entry)

    def holds(self, approver, scope, instant):
        for entry in self.by_approver.get(approver, []):
            if entry["scope"] not in (scope, "any"):
                continue
            if entry["from"] <= instant and (entry["to"] is None or instant < entry["to"]):
                return True
        return False

    def _load_audit(self):
        self.audit = {}
        parsed = 0
        admitted = 0
        late = 0
        for name in ("approval_audit.log", "approval_audit.log.1", "approval_audit.log.2"):
            for line in (self.data / name).read_text().splitlines():
                if not line.strip():
                    continue
                if line.startswith("  "):
                    self.counters.count("log_continuations")
                    continue
                parsed += 1
                head, _, rest = line.partition(" ")
                fields = {}
                for part in rest.split():
                    key, _, value = part.partition("=")
                    fields[key] = value
                site = fields.get("site")
                stamp = parse_local(head)
                if stamp is None or site not in self.clock.marks:
                    continue
                instant = self.clock.to_utc(site, stamp - timedelta(seconds=self.policy.skew[site]), 0)[0]
                if instant > self.policy.as_of:
                    late += 1
                    continue
                admitted += 1
                self.audit.setdefault(fields.get("ref", ""), []).append(
                    {
                        "instant": instant,
                        "approver": fields.get("approver"),
                        "scope": fields.get("scope"),
                        "action": fields.get("action"),
                        "approval": fields.get("apl"),
                    }
                )
        self.counters.file_rows("AUT", "approval_audit.log", None, parsed, admitted, late)

    def endorsed(self, reference, scope):
        key = (reference, scope)
        if key in self._endorse_cache:
            return self._endorse_cache[key]
        verdict = False
        for entry in self.audit.get(reference, []):
            if entry["action"] != "endorse" or entry["approval"] in (None, "none"):
                continue
            if entry["scope"] not in (scope, "any"):
                continue
            if self.holds(entry["approver"], scope, entry["instant"]):
                verdict = True
                break
        self._endorse_cache[key] = verdict
        return verdict

    def _load_retractions(self):
        self.retractions = {}
        rows = self.table("retraction_notices.csv", "RTR")
        for row in rows:
            self.retractions.setdefault(row["target_id"], []).append(row["retraction_id"])

    def retracted(self, target):
        # A retraction that has itself been retracted leaves its target standing.
        for identifier in self.retractions.get(target, []):
            if identifier not in self.retractions:
                return True
        return False


LEGAL_MOVES = {
    "approved": {"hold": "held", "withdraw": "withdrawn", "reject": "rejected"},
    "held": {"release": "approved", "withdraw": "withdrawn"},
    "withdrawn": {"reinstate": "approved"},
    "rejected": {},
}
STATE_REASON = {"held": "ON_HOLD", "withdrawn": "WITHDRAWN", "rejected": "REJECTED"}
FIELD_SCOPE = {"quantity": "quantity", "node": "node", "effective": "effective"}


def settle_quantity_governor(data: Path, counters: Counters):
    """Enumerate the candidate readings and keep the one that fits every observation."""
    lines = []
    for line in (data / "governance_observations.log").read_text().splitlines():
        if not line.strip():
            continue
        fields = {}
        for part in line.split()[1:]:
            key, _, value = part.partition("=")
            fields[key] = value
        lines.append(fields)
    counters.file_rows("OBS", "governance_observations.log", None, len(lines), len(lines), 0)
    survivors = []
    for candidate in ("order_book", "contract_registry", "later_recorded"):
        fits = True
        for fields in lines:
            predicted = fields["later_recorded"] if candidate == "later_recorded" else candidate
            if predicted != fields["governed_by"]:
                fits = False
                break
        if fits:
            survivors.append(candidate)
    if len(survivors) != 1:
        raise SystemExit("governance observations do not settle a single reading")
    return survivors[0]


def settle_carry_age(data: Path, counters: Counters):
    lines = []
    for line in (data / "deficit_observations.log").read_text().splitlines():
        if not line.strip():
            continue
        fields = {}
        for part in line.split()[1:]:
            key, _, value = part.partition("=")
            fields[key] = value
        lines.append(fields)
    counters.file_rows("OBS", "deficit_observations.log", None, len(lines), len(lines), 0)
    survivors = []
    for candidate in (1, 2, 3, "unbounded"):
        fits = True
        for fields in lines:
            age = int(fields["lot_age"])
            carried = candidate == "unbounded" or age <= candidate
            if carried != (fields["deficit_state"] == "carried"):
                fits = False
                break
        if fits:
            survivors.append(candidate)
    if len(survivors) != 1:
        raise SystemExit("deficit observations do not settle a single age")
    return survivors[0]


def prescan(path: Path, kind: str, counters: Counters) -> None:
    """Shape tallies that the admitted rows alone would miss."""
    lines = path.read_text().splitlines()
    start = 1 if lines and lines[0].startswith("#") else 0
    header = lines[start].split("\t" if kind == "registry" else ",")
    for line in lines[start + 1:]:
        if not line:
            continue
        if kind == "registry":
            fields = line.split("\t")
            if len(fields) < len(header):
                counters.count("row_truncated")
            node = fields[3] if len(fields) > 3 else ""
            if node == "":
                counters.count("node_empty")
            elif node == "\\N":
                counters.count("node_backslash_n")
        else:
            fields = next(csv.reader([line]))
            if len(fields) > 5 and fields[4] != fields[5]:
                counters.count("restatement_gaps")


class Builder:
    """Source rows become requests, then governed records, then priced claims."""

    def __init__(self, data: Path, policy: Policy, clock: Clock, corpus: Corpus, counters: Counters) -> None:
        self.data = data
        self.policy = policy
        self.clock = clock
        self.corpus = corpus
        self.counters = counters
        self.quantity_governor = settle_quantity_governor(data, counters)
        self.carry_age = settle_carry_age(data, counters)
        self.audit_by_approval = {}
        for entries in corpus.audit.values():
            for entry in entries:
                self.audit_by_approval.setdefault(entry["approval"], []).append(entry)
        self.requests = []
        self.out_of_scope = []
        self.by_reference = {}

    def read_rows(self):
        rows = []
        for index in range(1, 7):
            name = "orderbook_c%02d_c%02d.csv" % (index * 4 - 3, index * 4)
            prescan(self.data / name, "orderbook", self.counters)
            for row in self.corpus.table(name, "OBK"):
                fields = row["_fields"]
                if fields[6] == "lots":
                    self.counters.count("lot_unit_rows")
                effective = self.corpus.local(fields[2], fields[7], fields[8])
                rows.append(
                    {
                        "source": "order_book",
                        "ref": fields[0],
                        "code": fields[1],
                        "site": fields[2],
                        "node": fields[3],
                        "wafers": int(fields[4]) * (self.policy.lot_wafers if fields[6] == "lots" else 1),
                        "effective": effective,
                        "recorded": parse_instant(fields[9]),
                    }
                )
        for index in range(1, 5):
            name = "registry_q%d.tsv" % index
            prescan(self.data / name, "registry", self.counters)
            for row in self.corpus.table(name, "REG", delimiter="\t"):
                fields = row["_fields"]
                node = (fields[3] or "").strip()
                if node == "\\N":
                    node = ""
                rows.append(
                    {
                        "source": "contract_registry",
                        "ref": fields[0],
                        "code": fields[1],
                        "site": fields[2],
                        "node": node,
                        "wafers": int(fields[4]),
                        "effective": parse_instant(fields[6]),
                        "recorded": parse_instant(fields[7]),
                    }
                )
        for index in (1, 2):
            name = "fixed_width_intake_h%d.txt" % index
            parsed = 0
            admitted = 0
            late = 0
            for line in (self.data / name).read_text().splitlines():
                if not line.strip():
                    continue
                parsed += 1
                site = line[26:34].strip()
                recorded = parse_compact(line[64:78])
                if recorded > self.policy.as_of:
                    late += 1
                    continue
                admitted += 1
                rows.append(
                    {
                        "source": "legacy_intake",
                        "ref": line[0:12].strip(),
                        "code": line[12:26].strip(),
                        "site": site,
                        "node": line[34:40].strip(),
                        "wafers": int(line[40:50]) // self.policy.intake_scale,
                        "effective": self.intake_instant(site, line[50:64]),
                        "recorded": recorded,
                    }
                )
            self.counters.file_rows("LGI", name, None, parsed, admitted, late)
        return rows

    def intake_instant(self, site, text):
        instant, flag = self.clock.to_utc(site, parse_compact(text), 0)
        if flag == "ambiguous":
            self.counters.count("fold_disambiguated")
        elif flag == "shifted":
            self.counters.count("gap_shifted")
        return instant

    def resolve_rows(self, rows):
        keep = []
        for row in rows:
            code = row["code"]
            if row["source"] == "legacy_intake" and not code.startswith("CUS-"):
                resolved = self.corpus.resolve_code(code, row["effective"])
            else:
                resolved = code
            identity = canonical_id(resolved) if resolved else None
            if identity is None or identity not in self.corpus.by_customer:
                self.counters.count("unknown_customer_rows")
                self.out_of_scope.append(
                    {
                        "request_ref": row["ref"],
                        "customer": row["code"],
                        "site": row["site"],
                        "reason": "UNKNOWN_CUSTOMER",
                    }
                )
                continue
            row["customer_id"] = identity
            keep.append(row)
        return keep

    def dedupe(self, rows):
        grouped = {}
        for row in rows:
            grouped.setdefault((row["source"], row["ref"]), []).append(row)
        keep = []
        for _key, group in sorted(grouped.items()):
            if len(group) == 1:
                keep.append(group[0])
                continue
            shapes = {
                (row["customer_id"], row["site"], row["node"], row["wafers"], row["effective"])
                for row in group
            }
            if len(shapes) == 1:
                self.counters.count("duplicate_identical", len(group) - 1)
            else:
                self.counters.count("duplicate_conflicting", len(group) - 1)
            keep.append(max(group, key=lambda row: (row["recorded"], row["ref"])))
        return keep

    def collapse(self, rows):
        pools = {}
        for row in rows:
            pools.setdefault((row["customer_id"], row["site"]), []).append(row)
        requests = []
        for key in sorted(pools):
            pool = sorted(pools[key], key=lambda row: (row["effective"], SOURCE_RANK[row["source"]], row["ref"]))
            position = 0
            while position < len(pool):
                anchor = pool[position]
                cluster = [anchor]
                position += 1
                while position < len(pool) and pool[position]["effective"] <= anchor["effective"] + self.policy.collapse:
                    cluster.append(pool[position])
                    position += 1
                if len(cluster) > 1:
                    self.counters.count("cross_source_collapsed", len(cluster) - 1)
                requests.append(self.assemble(cluster))
        return requests

    def assemble(self, cluster):
        request = Ledgered()
        request.rows = cluster
        request.site = cluster[0]["site"]
        request.customer_id = cluster[0]["customer_id"]
        by_source = {}
        for row in cluster:
            by_source.setdefault(row["source"], row)
        earliest = min(row["effective"] for row in cluster)
        request.before_cutover = earliest < self.clock.start(request.site, int(self.policy.cutover_cycle[1:]))
        quantity_row = self.pick(by_source, "quantity", request.before_cutover)
        node_row = self.pick(by_source, "node", request.before_cutover)
        effective_row = self.pick(by_source, "effective", request.before_cutover)
        reference_row = self.pick(by_source, "request_ref", request.before_cutover)
        request.quantity_wafers = quantity_row["wafers"]
        request.node = node_row["node"]
        if not request.node:
            for source in ("order_book", "contract_registry", "legacy_intake"):
                row = by_source.get(source)
                if row is not None and row["node"]:
                    request.node = row["node"]
                    break
        request.effective = effective_row["effective"]
        request.ref = reference_row["ref"]
        for row in cluster:
            self.by_reference[row["ref"]] = request
        return request

    def pick(self, by_source, field, before):
        wanted = self.policy.governing_source(field, before, self.quantity_governor)
        row = by_source.get(wanted)
        if row is not None:
            return row
        for source in ("order_book", "contract_registry", "legacy_intake"):
            row = by_source.get(source)
            if row is not None:
                return row
        raise SystemExit("a request carried no source row")

    def amend(self):
        notices = {}
        for index in (1, 2, 3):
            name = "amendment_notices_p%d.jsonl" % index
            parsed = 0
            admitted = 0
            late = 0
            for line in (self.data / name).read_text().splitlines():
                if not line.strip():
                    continue
                parsed += 1
                record = json.loads(line)
                stamp = parse_instant(record["recorded_utc"])
                if stamp > self.policy.as_of:
                    late += 1
                    continue
                admitted += 1
                record["recorded"] = stamp
                notices.setdefault(record["request_ref"], []).append(record)
            self.counters.file_rows("AMD", name, None, parsed, admitted, late)
        for reference, group in sorted(notices.items()):
            request = self.by_reference.get(reference)
            if request is None:
                continue
            # amendment_rules.md condition 2: strictly after the latest recorded
            # instant among the admitted source rows of the request.
            latest = max(row["recorded"] for row in request.rows)
            valid = []
            for record in sorted(group, key=lambda item: (item["recorded"], item["notice_id"])):
                if record["recorded"] <= latest:
                    self.counters.count("amendments_early")
                    continue
                if self.corpus.retracted(record["notice_id"]):
                    self.counters.count("amendments_retracted")
                    continue
                scope = FIELD_SCOPE.get(record["field"], record["field"])
                if not self.corpus.endorsed(record["notice_id"], scope):
                    self.counters.count("amendments_unendorsed")
                    continue
                valid.append(record)
            if not valid:
                continue
            known = {record["notice_id"]: record for record in valid}
            if self.has_cycle(known):
                self.counters.count("amendment_chains_unresolvable")
                request.reason = "UNRESOLVABLE_CHAIN"
                continue
            superseded = {
                record["supersedes"] for record in valid if record["supersedes"] in known
            }
            heads = [record for record in valid if record["notice_id"] not in superseded]
            chosen = {}
            for record in heads:
                field = record["field"]
                current = chosen.get(field)
                if current is None or (record["recorded"], record["notice_id"]) > (
                    current["recorded"],
                    current["notice_id"],
                ):
                    chosen[field] = record
            for field, record in sorted(chosen.items()):
                self.counters.count("amendments_applied")
                if field == "quantity":
                    request.quantity_wafers = int(record["value"])
                elif field == "node":
                    request.node = record["value"]
                elif field == "effective":
                    request.effective = parse_instant(record["value"])

    @staticmethod
    def has_cycle(known):
        for start in known:
            seen = set()
            current = start
            while current in known:
                if current in seen:
                    return True
                seen.add(current)
                current = known[current]["supersedes"]
        return False

    def apply_states(self):
        events = {}
        for index in range(1, 6):
            name = "state_events_p%d.jsonl" % index
            parsed = 0
            admitted = 0
            late = 0
            for line in (self.data / name).read_text().splitlines():
                if not line.strip():
                    continue
                parsed += 1
                record = json.loads(line)
                stamp = parse_instant(record["recorded_utc"])
                if stamp > self.policy.as_of:
                    late += 1
                    continue
                admitted += 1
                record["recorded"] = stamp
                events.setdefault(record["request_ref"], []).append(record)
            self.counters.file_rows("EVT", name, None, parsed, admitted, late)
        pooled = {}
        for reference, group in events.items():
            request = self.by_reference.get(reference)
            if request is None:
                continue
            slot = pooled.setdefault(request.ref, (request, []))
            slot[1].extend(group)
        for key in sorted(pooled):
            request, group = pooled[key]
            state = "approved"
            highest = 0
            used = set()
            for record in sorted(group, key=lambda item: (item["recorded"], item["version"], item["event_id"])):
                version = int(record["version"])
                if version in used:
                    self.counters.count("duplicate_version_events")
                    continue
                if version <= highest:
                    self.counters.count("stale_events")
                    continue
                used.add(version)
                highest = version
                action = record["action"]
                moves = LEGAL_MOVES[state]
                if action not in moves:
                    self.counters.count("illegal_transitions")
                    continue
                if action == "reinstate" and not self.reinstatement_allowed(record):
                    self.counters.count("illegal_transitions")
                    continue
                state = moves[action]
            request.state = state

    def reinstatement_allowed(self, record):
        if "authority_ref" not in record:
            return self.corpus.endorsed(record["event_id"], "state")
        reference = record["authority_ref"]
        if not reference:
            return False
        for entry in self.audit_by_approval.get(reference, []):
            if entry["action"] != "endorse" or entry["scope"] not in ("state", "any"):
                continue
            if self.corpus.holds(entry["approver"], "state", entry["instant"]):
                return True
        return False

    def classify(self):
        kept = []
        for request in self.requests:
            index = self.clock.cycle_of(request.site, request.effective)
            if index is None:
                self.counters.count("out_of_horizon_rows")
                self.out_of_scope.append(
                    {
                        "request_ref": request.ref,
                        "customer": request.customer_id,
                        "site": request.site,
                        "reason": "OUT_OF_HORIZON",
                    }
                )
                continue
            request.cycle = CYCLE_IDS[index - 1]
            epoch = self.corpus.epoch_at(request.customer_id, request.effective)
            request.epoch = epoch["seq"]
            request.segment = epoch["segment"]
            request.identity = "%s#%d" % (request.customer_id, epoch["seq"])
            if epoch["seq"] != self.corpus.by_customer[request.customer_id][0]["seq"]:
                self.counters.count("epoch_reassignments")
            served, hops, numerator, denominator, error = self.corpus.walk(
                request.site, request.cycle, request.node
            )
            request.served = served or ""
            request.hops = hops
            request.numerator = numerator
            request.denominator = denominator
            request.walk_error = error
            request.quantity_equiv = half_up(request.quantity_wafers * numerator, denominator)
            ceiling = self.corpus.ceiling(request.customer_id, request.epoch, request.site, request.cycle)
            request.ceiling_wafers = ceiling
            request.ceiling_equiv = (
                0 if ceiling is None else half_up(ceiling * numerator, denominator)
            )
            flags = []
            if request.reason == "UNRESOLVABLE_CHAIN":
                flags.append("UNRESOLVABLE_CHAIN")
            if not request.node:
                flags.append("NODE_NOT_STATED")
            if error:
                flags.append(error)
            if self.corpus.status_at(epoch, request.effective) == "suspended":
                flags.append("CUSTOMER_SUSPENDED")
            if request.state in STATE_REASON:
                flags.append(STATE_REASON[request.state])
            if ceiling == 0:
                flags.append("CAP_ZERO")
                self.counters.count("ceiling_zero")
            request.reason = "NONE"
            for candidate in self.policy.reason_order:
                if candidate in flags:
                    request.reason = candidate
                    break
            if error == "UNRESOLVABLE_SUB_CYCLE":
                self.counters.count("substitution_cycles")
            elif error == "NO_QUALIFIED_NODE":
                self.counters.count("no_qualified_node")
            kept.append(request)
        self.requests = kept

    def build(self):
        rows = self.resolve_rows(self.read_rows())
        self.requests = self.collapse(self.dedupe(rows))
        self.amend()
        self.apply_states()
        self.classify()
        return self.requests


class Apportioner:
    """Floors first, then the progressive fill, then the carried shortfall pool."""

    def __init__(self, policy, clock, corpus, counters, carry_age) -> None:
        self.policy = policy
        self.clock = clock
        self.corpus = corpus
        self.counters = counters
        self.carry_age = carry_age
        self.cells = {}

    def survives(self, origin, index):
        if self.carry_age == "unbounded":
            return True
        return origin >= index - self.carry_age

    def obligations(self, site):
        due = {}
        for agreement, meta in self.corpus.agreement_meta.items():
            if meta["site"] != site:
                continue
            due[agreement] = {index for index in range(1, 25) if self.corpus.due(agreement, index)}
        for key in sorted(self.corpus.exceptions):
            agreement, cycle = key
            if agreement not in due:
                continue
            for entry in sorted(self.corpus.exceptions[key], key=lambda item: (item["recorded"], item["id"])):
                if self.corpus.retracted(entry["id"]):
                    self.counters.count("exceptions_retracted")
                    continue
                if not self.corpus.endorsed(entry["id"], "commitment"):
                    self.counters.count("exceptions_unendorsed")
                    continue
                self.counters.count("exceptions_applied")
                due[agreement].discard(int(cycle[1:]))
                if entry["action"] == "move_to" and entry["target"]:
                    due[agreement].add(int(entry["target"][1:]))
        plan = {}
        for agreement, indexes in due.items():
            for index in indexes:
                plan.setdefault(index, []).append(agreement)
        return plan

    def run(self, requests):
        for site in SITES:
            pools = {}
            running = {}
            by_cycle = {}
            for request in requests:
                if request.site == site:
                    by_cycle.setdefault(request.cycle, []).append(request)
            plan = self.obligations(site)
            for index in range(1, 25):
                cycle = CYCLE_IDS[index - 1]
                capacity = self.corpus.groups(site, cycle)[0]
                rows = sorted(by_cycle.get(cycle, []), key=lambda item: (item.identity, item.ref))
                for identity in sorted(pools):
                    kept = []
                    for lot in pools[identity]:
                        if self.survives(lot[0], index):
                            kept.append(lot)
                        else:
                            self.counters.count("lots_expired")
                    pools[identity] = kept
                claiming = [row for row in rows if row.reason == "NONE"]
                carriers = {}
                for request in sorted(claiming, key=lambda item: (item.effective, item.ref)):
                    carriers.setdefault(request.identity, request)
                for request in claiming:
                    carried = 0
                    if carriers.get(request.identity) is request:
                        carried = sum(lot[1] for lot in pools.get(request.identity, []))
                    request.carried_in = carried
                    total = request.quantity_equiv + carried
                    if request.ceiling_wafers is None:
                        request.claim = total
                    else:
                        request.claim = min(total, request.ceiling_equiv)
                        if request.ceiling_equiv < total:
                            self.counters.count("ceiling_binding")
                floors = {request.ref: 0 for request in claiming}
                remaining = capacity
                ordered = sorted(
                    plan.get(index, []),
                    key=lambda agreement: (self.corpus.rank_of(agreement, site, cycle), agreement),
                )
                for agreement in ordered:
                    wafers = self.corpus.floor_wafers(agreement, site, cycle)
                    if wafers is None:
                        continue
                    customer = self.corpus.agreement_meta[agreement]["customer"]
                    covered = None
                    for request in sorted(claiming, key=lambda item: (item.effective, item.ref)):
                        if request.customer_id == customer:
                            covered = request
                            break
                    if covered is None:
                        self.counters.count("floors_unmatched")
                        continue
                    target = half_up(wafers * covered.numerator, covered.denominator)
                    amount = min(target, covered.claim - floors[covered.ref], remaining)
                    amount = max(0, amount)
                    floors[covered.ref] += amount
                    covered.floor_equiv += amount
                    remaining -= amount
                    if amount == target:
                        self.counters.count("floors_honoured_full")
                    else:
                        self.counters.count("floors_honoured_short")
                level = self.fill_level(capacity, claiming, floors)
                grants = {}
                for request in claiming:
                    grants[request.ref] = max(floors[request.ref], min(request.claim, level))
                surplus = capacity - sum(grants.values())
                eligible = [request for request in claiming if request.claim > grants[request.ref]]
                eligible.sort(
                    key=lambda item: (
                        -(item.claim - grants[item.ref]),
                        item.effective,
                        item.identity,
                        item.ref,
                    )
                )
                for request in eligible[: max(0, surplus)]:
                    grants[request.ref] += 1
                granted_total = 0
                for request in claiming:
                    granted = grants[request.ref]
                    request.granted = granted
                    request.granted_wafers = (granted * request.denominator) // request.numerator
                    request.deficit = request.claim - granted
                    granted_total += granted
                    carried_part = min(granted, request.claim - min(request.quantity_equiv, request.claim))
                    pool = pools.setdefault(request.identity, [])
                    left = carried_part
                    while left > 0 and pool:
                        if pool[0][1] <= left:
                            left -= pool[0][1]
                            pool.pop(0)
                        else:
                            pool[0][1] -= left
                            left = 0
                    current_part = min(request.quantity_equiv, request.claim)
                    shortfall = current_part - (granted - carried_part)
                    if shortfall > 0:
                        pool.append([index, shortfall])
                residual = capacity - granted_total
                binding = residual == 0
                if not binding:
                    cleared = 0
                    for identity in sorted(pools):
                        cleared += len(pools[identity])
                        pools[identity] = []
                    if cleared:
                        self.counters.count("lots_cleared", cleared)
                    self.counters.count("resets")
                for request in rows:
                    if request.reason == "NONE":
                        state = running.setdefault(request.identity, [0, 0])
                        state[0] += request.granted
                        state[1] += request.deficit
                        if carriers.get(request.identity) is request:
                            request.carried_out = sum(
                                lot[1] for lot in pools.get(request.identity, []) if self.survives(lot[0], index + 1)
                            )
                        if request.claim == 0:
                            request.outcome = "ZERO"
                        elif request.granted == request.claim:
                            request.outcome = "FULL"
                        elif request.granted == 0:
                            request.outcome = "ZERO"
                        else:
                            request.outcome = "PARTIAL"
                    else:
                        request.outcome = "EXCLUDED"
                        request.claim = 0
                        request.granted = 0
                        request.granted_wafers = 0
                        request.deficit = 0
                        request.carried_in = 0
                        request.floor_equiv = 0
                        request.carried_out = 0
                    state = running.setdefault(request.identity, [0, 0])
                    request.granted_to_date = state[0]
                    request.deficit_to_date = state[1]
                    self.counters.count("hops_%d" % request.hops)
                    self.counters.count("side_before" if request.before_cutover else "side_from")
                self.cells[(site, cycle)] = {
                    "cycle": cycle,
                    "capacity_equiv": capacity,
                    "fill_level": level,
                    "floor_total_equiv": sum(floors.values()),
                    "granted_equiv": granted_total,
                    "residual_equiv": residual,
                    "request_count": len(rows),
                    "binding": binding,
                }

    @staticmethod
    def fill_level(capacity, claiming, floors):
        if not claiming:
            return 0
        pairs = [(floors[request.ref], request.claim) for request in claiming]
        high = max(claim for _floor, claim in pairs)
        low = 0
        best = 0
        while low <= high:
            middle = (low + high) // 2
            total = sum(max(floor, min(claim, middle)) for floor, claim in pairs)
            if total <= capacity:
                best = middle
                low = middle + 1
            else:
                high = middle - 1
        return best


class Emitter:
    def __init__(self, policy, counters, cells, requests, out_of_scope, governor, carry_age) -> None:
        self.policy = policy
        self.counters = counters
        self.cells = cells
        self.requests = requests
        self.out_of_scope = out_of_scope
        self.governor = governor
        self.carry_age = carry_age

    def ledger_row(self, request):
        return {
            "cycle": request.cycle,
            "request_ref": request.ref,
            "customer": request.identity,
            "segment": request.segment,
            "requested_node": request.node,
            "served_node": request.served,
            "hops": request.hops,
            "quantity_equiv": request.quantity_equiv,
            "carried_in_equiv": request.carried_in,
            "ceiling_equiv": request.ceiling_equiv,
            "claim_equiv": request.claim,
            "floor_equiv": request.floor_equiv,
            "granted_equiv": request.granted,
            "granted_wafers": request.granted_wafers,
            "deficit_equiv": request.deficit,
            "carried_out_equiv": request.carried_out,
            "granted_to_date_equiv": request.granted_to_date,
            "deficit_to_date_equiv": request.deficit_to_date,
            "outcome": request.outcome,
            "reason": request.reason,
        }

    def write(self, out: Path):
        order = {cycle: index for index, cycle in enumerate(CYCLE_IDS)}
        regions = {}
        for site in SITES:
            rows = [request for request in self.requests if request.site == site]
            rows.sort(key=lambda item: (order[item.cycle], item.identity, item.ref))
            cycles = [self.cells[(site, cycle)] for cycle in CYCLE_IDS]
            scope = sorted(
                [item for item in self.out_of_scope if item["site"] == site],
                key=lambda item: item["request_ref"],
            )
            document = {
                "site": site,
                "as_of": self.policy.as_of_text,
                "cycles": cycles,
                "ledger": [self.ledger_row(request) for request in rows],
                "out_of_scope": scope,
                "totals": {
                    "ledger_rows": len(rows),
                    "granted_equiv": sum(request.granted for request in rows),
                    "claim_equiv": sum(request.claim for request in rows),
                    "deficit_equiv": sum(request.deficit for request in rows),
                    "capacity_equiv": sum(cell["capacity_equiv"] for cell in cycles),
                    "residual_equiv": sum(cell["residual_equiv"] for cell in cycles),
                },
            }
            regions[site] = document
            write_json(out / ("region_%s.json" % site), document)

        segments = {}
        for segment in SEGMENTS:
            rows = [request for request in self.requests if request.segment == segment]
            sites = []
            for site in SITES:
                part = [request for request in rows if request.site == site]
                sites.append(
                    {
                        "site": site,
                        "granted_equiv": sum(request.granted for request in part),
                        "claim_equiv": sum(request.claim for request in part),
                        "deficit_equiv": sum(request.deficit for request in part),
                        "ledger_rows": len(part),
                    }
                )
            cycles = []
            for cycle in CYCLE_IDS:
                part = [request for request in rows if request.cycle == cycle]
                cycles.append(
                    {
                        "cycle": cycle,
                        "granted_equiv": sum(request.granted for request in part),
                        "claim_equiv": sum(request.claim for request in part),
                        "deficit_equiv": sum(request.deficit for request in part),
                        "ledger_rows": len(part),
                    }
                )
            outcome_counts = {name: 0 for name in OUTCOMES}
            reason_counts = {}
            for request in rows:
                outcome_counts[request.outcome] += 1
                reason_counts[request.reason] = reason_counts.get(request.reason, 0) + 1
            document = {
                "segment": segment,
                "as_of": self.policy.as_of_text,
                "sites": sites,
                "cycles": cycles,
                "outcome_counts": outcome_counts,
                "reason_counts": reason_counts,
                "totals": {
                    "granted_equiv": sum(request.granted for request in rows),
                    "claim_equiv": sum(request.claim for request in rows),
                    "deficit_equiv": sum(request.deficit for request in rows),
                    "ledger_rows": len(rows),
                    "customers": len({request.identity for request in rows}),
                },
            }
            segments[segment] = document
            write_json(out / ("segment_%s.json" % segment), document)

        site_blocks = []
        for site in SITES:
            document = regions[site]
            site_blocks.append(
                {
                    "site": site,
                    "capacity_equiv": document["totals"]["capacity_equiv"],
                    "granted_equiv": document["totals"]["granted_equiv"],
                    "claim_equiv": document["totals"]["claim_equiv"],
                    "deficit_equiv": document["totals"]["deficit_equiv"],
                    "residual_equiv": document["totals"]["residual_equiv"],
                    "ledger_rows": document["totals"]["ledger_rows"],
                }
            )
        cycle_blocks = []
        for cycle in CYCLE_IDS:
            part = [request for request in self.requests if request.cycle == cycle]
            cycle_blocks.append(
                {
                    "cycle": cycle,
                    "capacity_equiv": sum(self.cells[(site, cycle)]["capacity_equiv"] for site in SITES),
                    "granted_equiv": sum(request.granted for request in part),
                    "claim_equiv": sum(request.claim for request in part),
                    "deficit_equiv": sum(request.deficit for request in part),
                    "residual_equiv": sum(self.cells[(site, cycle)]["residual_equiv"] for site in SITES),
                    "ledger_rows": len(part),
                }
            )
        granted = sum(request.granted for request in self.requests)
        claim = sum(request.claim for request in self.requests)
        deficit = sum(request.deficit for request in self.requests)
        capacity = sum(cell["capacity_equiv"] for cell in self.cells.values())
        residual = sum(cell["residual_equiv"] for cell in self.cells.values())
        largest = {"customer": "", "site": "", "value": 0}
        for request in sorted(self.requests, key=lambda item: (item.identity, item.site)):
            if request.deficit_to_date > largest["value"]:
                largest = {
                    "customer": request.identity,
                    "site": request.site,
                    "value": request.deficit_to_date,
                }
        summary = {
            "as_of": self.policy.as_of_text,
            "sites": site_blocks,
            "segments": [
                {
                    "segment": segment,
                    "granted_equiv": segments[segment]["totals"]["granted_equiv"],
                    "claim_equiv": segments[segment]["totals"]["claim_equiv"],
                    "deficit_equiv": segments[segment]["totals"]["deficit_equiv"],
                    "ledger_rows": segments[segment]["totals"]["ledger_rows"],
                }
                for segment in SEGMENTS
            ],
            "cycles": cycle_blocks,
            "totals": {
                "ledger_rows": len(self.requests),
                "granted_equiv": granted,
                "claim_equiv": claim,
                "deficit_equiv": deficit,
                "capacity_equiv": capacity,
                "residual_equiv": residual,
                "out_of_scope_rows": len(self.out_of_scope),
                "customers_served": len({request.identity for request in self.requests}),
                "identity_checks": {
                    "region_minus_segment_granted": granted
                    - sum(segments[segment]["totals"]["granted_equiv"] for segment in SEGMENTS),
                    "capacity_minus_granted_minus_residual": capacity - granted - residual,
                    "claim_minus_granted_minus_deficit": claim - granted - deficit,
                },
                "spine": {
                    "binding_cells": sum(1 for cell in self.cells.values() if cell["binding"]),
                    "non_binding_cells": sum(1 for cell in self.cells.values() if not cell["binding"]),
                    "largest_deficit_to_date": largest,
                },
            },
        }
        write_json(out / "summary.json", summary)

        tally = self.counters.tally
        audit_keys = [
            "floors_honoured_full", "floors_honoured_short", "floors_unmatched",
            "exceptions_applied", "exceptions_unendorsed", "exceptions_retracted",
            "illegal_transitions", "stale_events", "duplicate_version_events",
            "amendments_applied", "amendments_unendorsed", "amendments_early",
            "amendments_retracted", "amendment_chains_unresolvable", "no_qualified_node",
            "substitution_cycles", "resets", "lots_expired", "lots_cleared",
            "ceiling_binding", "ceiling_zero", "epoch_reassignments",
        ]
        audit = {key: tally.get(key, 0) for key in audit_keys}
        audit["substitution_hops"] = {str(index): tally.get("hops_%d" % index, 0) for index in range(4)}
        audit["cutover_sides"] = {
            "before": tally.get("side_before", 0),
            "from": tally.get("side_from", 0),
        }
        audit["withheld"] = {
            "quantity_governed_before_cutover": self.governor,
            "carry_forward_age": self.carry_age,
        }
        write_json(out / "policy_audit.json", audit)

        sources = {}
        for code in self.policy.source_codes:
            sources[code] = {
                "declared_rows": self.counters.declared.get(code, 0),
                "parsed_rows": self.counters.parsed.get(code, 0),
                "admitted_rows": self.counters.admitted.get(code, 0),
            }
        quality = {
            "sources": sources,
            "header_gaps": dict(self.counters.header_gaps),
            "null_forms": {
                "node_empty": tally.get("node_empty", 0),
                "node_backslash_n": tally.get("node_backslash_n", 0),
                "row_truncated": tally.get("row_truncated", 0),
            },
            "late_recorded": {code: self.counters.late.get(code, 0) for code in self.policy.source_codes},
            "duplicate_identical": tally.get("duplicate_identical", 0),
            "duplicate_conflicting": tally.get("duplicate_conflicting", 0),
            "cross_source_collapsed": tally.get("cross_source_collapsed", 0),
            "fold_disambiguated": tally.get("fold_disambiguated", 0),
            "gap_shifted": tally.get("gap_shifted", 0),
            "log_continuations": tally.get("log_continuations", 0),
            "unknown_customer_rows": tally.get("unknown_customer_rows", 0),
            "out_of_horizon_rows": tally.get("out_of_horizon_rows", 0),
            "lot_unit_rows": tally.get("lot_unit_rows", 0),
            "paren_negatives": tally.get("paren_negatives", 0),
            "restatement_gaps": tally.get("restatement_gaps", 0),
        }
        write_json(out / "data_quality.json", quality)


def main() -> None:
    parser = argparse.ArgumentParser(description="Apportion wafer start capacity across sites and cycles.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    arguments = parser.parse_args()
    data = Path(arguments.data)
    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    counters = Counters()
    policy = Policy(data)
    clock = Clock(data, counters)
    corpus = Corpus(data, policy, clock, counters)
    builder = Builder(data, policy, clock, corpus, counters)
    requests = builder.build()
    apportioner = Apportioner(policy, clock, corpus, counters, builder.carry_age)
    apportioner.run(requests)
    emitter = Emitter(
        policy,
        counters,
        apportioner.cells,
        requests,
        builder.out_of_scope,
        builder.quantity_governor,
        builder.carry_age,
    )
    emitter.write(out)


if __name__ == "__main__":
    main()
