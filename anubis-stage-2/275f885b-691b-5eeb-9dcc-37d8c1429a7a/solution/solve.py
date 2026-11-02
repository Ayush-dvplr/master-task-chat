#!/usr/bin/env python3
"""Settle the campaign dose rationing ladder for one corpus of export files.

Usage: derive_report.py --data <corpus directory> --out <output directory>
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path

REGIONS = ["North", "South", "West", "East"]
SEGMENTS = ["commercial", "public"]
REJECT_ORDER = [
    "RC_UNKNOWN_BLOCK",
    "RC_WINDOW",
    "RC_LATE_RECORD",
    "RC_WITHDRAWN_BLOCK",
    "RC_EPOCH_GAP",
    "RC_EVENT_CONFLICT",
    "RC_NO_HEADCOUNT",
]
SOURCE_ORDER = [
    "field_intake",
    "dispatch_stream",
    "registry",
    "visit_events",
    "amendment_notices",
    "lot_register",
    "release_certificates",
    "assay",
    "reference",
]

COUNTED = [
    "RC_DUPLICATE_COLLAPSED",
    "RC_STALE_REVISION",
    "RC_AMENDMENT_STALE",
    "RC_AMENDMENT_UNAUTHORISED",
    "RC_LOT_CYCLE",
    "RC_ILLEGAL_TRANSITION",
    "RC_NO_SUBSTITUTE",
    "RC_UNIT_UNDECLARED",
    "RC_HEADER_GAP",
]
TRANSITIONS = {
    ("quarantine", "released"),
    ("quarantine", "condemned"),
    ("released", "condemned"),
    ("condemned", "reinstated"),
}
SCOPES = ["fully_awarded_only", "none", "region_wide", "tier1_only"]
SOURCES = ["dispatch_stream", "field_intake"]


def parse_day(text):
    return date(int(text[0:4]), int(text[5:7]), int(text[8:10]))


def parse_stamp(text):
    return datetime(
        int(text[0:4]), int(text[5:7]), int(text[8:10]), int(text[11:13]), int(text[14:16]), int(text[17:19])
    )


def half_up(numerator, denominator):
    return (numerator * 2 + denominator) // (denominator * 2)


def scaled(text):
    body = text.strip()
    if "." in body:
        whole, rest = body.split(".", 1)
        rest = (rest + "000")[:3]
        return int(whole) * 1000 + int(rest)
    return int(body) * 1000


class Corpus:
    """Raw export files, parsed once."""

    def __init__(self, root: Path):
        self.root = root
        self.header_gaps = 0
        self.source_rows = {}
        self.manifest = self.read_manifest()

    def path(self, name):
        target = self.root / name
        if not target.is_file():
            raise SystemExit("missing export file: %s" % name)
        return target

    def body(self, name):
        declared = None
        rows = []
        for line in self.path(name).read_text().split("\n"):
            if line == "":
                continue
            if line.startswith("#"):
                if declared is None and "rows=" in line:
                    declared = int(line.split("rows=")[1].strip())
                continue
            rows.append(line)
        return declared, rows

    def note_gap(self, declared, count):
        if declared is not None and declared != count:
            self.header_gaps += 1

    def table(self, name, sep=","):
        declared, rows = self.body(name)
        header = rows[0].split(sep)
        out = []
        for line in rows[1:]:
            parts = line.split(sep)
            record = {}
            for index, key in enumerate(header):
                record[key] = parts[index] if index < len(parts) else None
            out.append(record)
        self.note_gap(declared, len(out))
        return out

    def records(self, name):
        declared, rows = self.body(name)
        out = [json.loads(line) for line in rows]
        self.note_gap(declared, len(out))
        return out

    def flat(self, name):
        declared, rows = self.body(name)
        self.note_gap(declared, len(rows))
        return rows

    def read_manifest(self):
        groups = {}
        for line in self.path("source_manifest.md").read_text().split("\n"):
            text = line.strip()
            if not text.startswith("- ") or ":" not in text:
                continue
            label, rest = text[2:].split(":", 1)
            names = [item for item in rest.replace(",", " ").split() if item]
            groups[label.strip()] = names
        for names in groups.values():
            for name in names:
                self.path(name)
        return groups

    def group(self, label):
        return sorted(self.manifest.get(label, []))

    def properties(self):
        values = {}
        pending = None
        for raw in self.path("source_declarations.properties").read_text().split("\n"):
            line = raw.strip()
            if pending is not None:
                joined = pending + " " + line
                if joined.endswith("\\"):
                    pending = joined[:-1].rstrip()
                    continue
                key, rest = joined.split("=", 1)
                values[key.strip()] = rest.strip()
                pending = None
                continue
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.endswith("\\"):
                pending = line[:-1].rstrip()
                continue
            key, rest = line.split("=", 1)
            values[key.strip()] = rest.strip()
        return values

    def ini(self):
        sections = {}
        current = None
        for raw in self.path("unit_declarations.ini").read_text().split("\n"):
            line = raw.strip()
            if not line or line.startswith(";") or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current = line[1:-1]
                sections[current] = {}
                continue
            if current is None or "=" not in line:
                continue
            key, value = line.split("=", 1)
            sections[current][key.strip()] = value.strip()
        return sections


class Settlement:
    def __init__(self, root: Path):
        self.corpus = Corpus(root)
        self.props = self.corpus.properties()
        self.units = self.corpus.ini()
        self.reasons = json.loads(self.corpus.path("reason_codes.json").read_text())
        self.scopes = json.loads(self.corpus.path("authority_scopes.json").read_text())
        self.depot_of = {}
        for item in self.props["depot.map"].replace(",", " ").split():
            region, depot = item.split(":")
            self.depot_of[region] = depot
        self.region_of = {depot: region for region, depot in self.depot_of.items()}
        self.cutover = parse_day(self.props["cutover.date"])
        self.anchor = parse_day(self.props["campaign.anchor.date"])
        self.round_total = int(self.props["campaign.rounds"])
        self.collapse_hours = int(self.props["collapse.window.hours"])
        self.cap_multiple = int(self.props["carry.cap.multiple"])
        self.max_alias_hops = int(self.props["alias.max_hops"])
        self.max_sub_hops = int(self.props["substitution.max_hops"])
        self.tier_count = int(self.props["tier.count"])
        self.day_start = int(self.props["day.start.local"][0:2])
        self.window_days = int(self.props["window.length.days"])
        self.counted = {code: 0 for code in COUNTED}
        self.rejects = {code: 0 for code in REJECT_ORDER}
        self.cache_state = {}
        self.cache_sub = {}
        self.cache_target = {}
        self.cache_master = {}
        self.cache_tier = {}
        self.cache_elig = {}
        self.audit = {
            "alias_hops": {"1": 0, "2": 0, "3": 0},
            "epoch_identities": 0,
            "collapsed_duplicates": 0,
            "stale_revisions": 0,
            "attribute_overrides": 0,
            "amendments_applied": 0,
            "amendments_stale": 0,
            "amendments_unauthorised": 0,
            "ceiling_clamped": 0,
            "exact_half_entitlements": 0,
            "substituted_lots": {"1": 0, "2": 0},
            "lots_unresolved_cycle": 0,
            "lots_without_substitute": 0,
            "illegal_transitions": 0,
            "reinstated_lots": 0,
            "unit_undeclared_lots": 0,
            "extinguished_no_show": 0,
            "extinguished_epoch": 0,
        }

    # ---------- calendar ----------
    def load_calendar(self):
        rows = self.corpus.table("calendar_exceptions.csv")
        self.bump("reference", len(rows))
        codes = ["R%02d" % (index + 1) for index in range(self.round_total)]
        nominal = {code: self.anchor + timedelta(days=14 * index) for index, code in enumerate(codes)}
        best = {}
        for row in rows:
            if row["region"] != "ALL":
                continue
            code = row["round_code"]
            key = (parse_stamp(row["issued_at"]), row["notice_ref"])
            if code not in best or key > best[code][0]:
                best[code] = (key, row)
        start = {}
        skipped = set()
        for code in codes:
            chosen = best.get(code)
            if chosen is None or chosen[1]["action"] == "confirm":
                start[code] = nominal[code]
            elif chosen[1]["action"] == "skip":
                start[code] = nominal[code]
                skipped.add(code)
            else:
                start[code] = parse_day(chosen[1]["new_start_date"])
        self.codes = codes
        self.start = start
        self.skipped = skipped
        self.live = sorted([code for code in codes if code not in skipped], key=lambda code: (start[code], code))
        self.position = {code: index for index, code in enumerate(self.live)}
        self.settles_in = {}
        for code in codes:
            if code not in skipped:
                self.settles_in[code] = code
                continue
            later = [item for item in self.live if start[item] > start[code]]
            self.settles_in[code] = later[0] if later else None
        self.rolls_into = {}
        for code, target in self.settles_in.items():
            if target is not None and target != code:
                self.rolls_into.setdefault(target, []).append(code)

    def bump(self, label, count):
        self.corpus.source_rows[label] = self.corpus.source_rows.get(label, 0) + count

    def load_offsets(self):
        rows = self.corpus.table("depot_clock_offsets.csv")
        self.bump("reference", len(rows))
        table = {}
        for row in rows:
            key = (row["depot"], parse_day(row["calendar_date"]))
            stamp = parse_stamp(row["issued_at"])
            if key not in table or stamp > table[key][0]:
                table[key] = (stamp, int(row["utc_offset_minutes"]))
        self.offsets = {key: value[1] for key, value in table.items()}

    def offset(self, depot, day):
        if (depot, day) in self.offsets:
            return self.offsets[(depot, day)]
        raise SystemExit("no declared clock offset for %s on %s" % (depot, day))

    def window(self, code):
        begin = datetime.combine(self.start[code], datetime.min.time()) + timedelta(hours=self.day_start)
        return begin, begin + timedelta(days=self.window_days)

    def to_utc(self, depot, moment):
        return moment - timedelta(minutes=self.offset(depot, moment.date()))

    # ---------- reference data ----------
    def load_blocks(self):
        rows = self.corpus.table("block_master.csv")
        self.bump("reference", len(rows))
        versions = {}
        for row in rows:
            versions.setdefault(row["block_ref"], []).append(row)
        for ref in versions:
            versions[ref].sort(key=lambda item: (parse_day(item["valid_from"]), item["record_id"]))
        self.master = versions

        alias_rows = self.corpus.table("block_alias_map.csv")
        self.bump("reference", len(alias_rows))
        aliases = {}
        for row in alias_rows:
            aliases.setdefault(row["alias_key"], []).append(row)
        self.aliases = aliases

        tiers = self.corpus.table("priority_register.csv")
        self.bump("reference", len(tiers))
        register = {}
        for row in tiers:
            register.setdefault(row["block_ref"], []).append(row)
        for ref in register:
            register[ref].sort(
                key=lambda item: (parse_day(item["effective_from"]), parse_stamp(item["issued_at"]), item["entry_ref"])
            )
        self.priority = register

        ceilings = {}
        for name in self.corpus.group("ceilings"):
            rows = self.corpus.table(name)
            self.bump("reference", len(rows))
            for row in rows:
                key = (row["block_ref"], row["round_code"])
                stamp = (parse_stamp(row["issued_at"]), row["entry_ref"])
                if key not in ceilings or stamp > ceilings[key][0]:
                    ceilings[key] = (stamp, int(row["handling_ceiling"]))
        self.ceilings = {key: value[1] for key, value in ceilings.items()}
        self.ceiling_stamp = {key: value[0][0] for key, value in ceilings.items()}

        factors = {}
        rows = self.corpus.table("dose_factors.csv")
        self.bump("reference", len(rows))
        for row in rows:
            key = (row["region"], row["species"], row["age_class"])
            factors.setdefault(key, []).append(
                (
                    parse_day(row["effective_from"]),
                    parse_stamp(row["issued_at"]),
                    row["factor_ref"],
                    scaled(row["doses_per_100_head"]) // 10,
                )
            )
        for key in factors:
            factors[key].sort()
        self.factors = factors

        potency = {}
        rows = self.corpus.table("potency_factors.csv")
        self.bump("reference", len(rows))
        for row in rows:
            key = (row["depot"], row["serotype"], row["unit"])
            potency.setdefault(key, []).append(
                (
                    parse_day(row["effective_from"]),
                    parse_stamp(row["issued_at"]),
                    row["factor_ref"],
                    scaled(row["doses_per_unit"]),
                )
            )
        for key in potency:
            potency[key].sort()
        self.potency = potency

        edges = {}
        rows = self.corpus.table("substitution_graph.csv")
        self.bump("reference", len(rows))
        for row in rows:
            edges.setdefault(row["from_serotype"], []).append(
                (
                    parse_day(row["effective_from"]),
                    parse_day(row["effective_to"]) if row["effective_to"] else None,
                    row["to_serotype"],
                    int(row["potency_percent"]),
                    row["edge_ref"],
                )
            )
        self.edges = edges

        phases = {}
        rows = self.corpus.table("campaign_phases.csv")
        self.bump("reference", len(rows))
        for row in rows:
            key = (row["region"], row["round_code"])
            phases.setdefault(key, []).append((parse_stamp(row["issued_at"]), row["revision_ref"], row["target_serotype"]))
        for key in phases:
            phases[key].sort()
        self.phases = phases

    def target_serotype(self, region, code):
        key = (region, code)
        if key in self.cache_target:
            return self.cache_target[key]
        begin, _ = self.window(code)
        cut = self.to_utc(self.depot_of[region], begin)
        live = [item for item in self.phases.get(key, []) if item[0] <= cut]
        if not live:
            raise SystemExit("no campaign phase in force for %s %s" % (region, code))
        self.cache_target[key] = live[-1][2]
        return self.cache_target[key]

    def resolve_key(self, raw):
        text = raw.strip().upper()
        if "/" in text:
            text = text.split("/")[0]
        digits = "".join(ch for ch in text if ch.isdigit())
        if not digits:
            return None
        return "BLK-%04d" % int(digits)

    def resolve_block(self, key, day):
        seen = set()
        current = key
        hops = 0
        while hops <= self.max_alias_hops:
            if current in self.master:
                return current, hops
            if current in seen:
                return None, hops
            seen.add(current)
            options = [
                row
                for row in self.aliases.get(current, [])
                if parse_day(row["effective_from"]) <= day
                and (not row["effective_to"] or day < parse_day(row["effective_to"]))
            ]
            if not options:
                return None, hops
            options.sort(key=lambda row: (parse_day(row["effective_from"]), parse_stamp(row["issued_at"])))
            current = options[-1]["canonical_ref"]
            hops += 1
        return None, hops

    def master_version(self, ref, day):
        key = (ref, day)
        if key in self.cache_master:
            return self.cache_master[key]
        chosen = None
        for row in self.master.get(ref, []):
            if parse_day(row["valid_from"]) <= day:
                chosen = row
        self.cache_master[key] = chosen
        return chosen

    def tier_for(self, ref, day):
        key = (ref, day)
        if key in self.cache_tier:
            return self.cache_tier[key]
        chosen = None
        for row in self.priority.get(ref, []):
            if parse_day(row["effective_from"]) <= day:
                chosen = row
        value = self.tier_count if chosen is None else int(chosen["tier"])
        self.cache_tier[key] = value
        return value

    def factor_for(self, region, species, age, day):
        options = [item for item in self.factors.get((region, species, age), []) if item[0] <= day]
        if not options:
            raise SystemExit("no dose factor in force for %s %s %s" % (region, species, age))
        return options[-1][3]

    # ---------- event streams ----------
    def load_events(self):
        groups = {}
        total = 0
        for name in self.corpus.group("visit_events"):
            for row in self.corpus.records(name):
                total += 1
                groups.setdefault(row["event_id"], []).append(row)
        self.bump("visit_events", total)
        conflicts = set()
        restocks = {}
        no_shows = {}
        for key in sorted(groups):
            rows = groups[key]
            bodies = set(json.dumps(row, sort_keys=True) for row in rows)
            if len(bodies) > 1:
                for row in rows:
                    conflicts.add((row["block_ref"], row["round_code"]))
                continue
            row = rows[0]
            if row["event"] == "restock":
                restocks.setdefault(row["block_ref"], []).append(parse_stamp(row["occurred_at"]))
            elif row["event"] == "no_show":
                no_shows.setdefault((row["block_ref"], row["round_code"]), []).append(parse_stamp(row["occurred_at"]))
        for ref in restocks:
            restocks[ref].sort()
        self.restocks = restocks
        self.no_shows = no_shows
        self.event_conflicts = conflicts

    def epoch(self, ref, moment_utc):
        return 1 + sum(1 for item in self.restocks.get(ref, []) if item < moment_utc)

    def load_dispatch(self):
        stream = {}
        total = 0
        for name in self.corpus.group("dispatch_stream"):
            for row in self.corpus.records(name):
                total += 1
                stream.setdefault((row["block_ref"], row["round_code"]), []).append(row)
        self.bump("dispatch_stream", total)
        self.dispatch = stream

    def dispatch_value(self, ref, codes, limit_utc):
        best = None
        for code in codes:
            rows = [row for row in self.dispatch.get((ref, code), []) if parse_stamp(row["recorded_at"]) <= limit_utc]
            if not rows:
                continue
            top = max(int(row["version"]) for row in rows)
            latest = [row for row in rows if int(row["version"]) == top]
            latest.sort(key=lambda row: (parse_stamp(row["recorded_at"]), row["op"]))
            chosen = latest[-1]
            if chosen["op"] == "delete":
                continue
            stamp = parse_stamp(chosen["recorded_at"])
            if best is None or stamp > best[0]:
                best = (stamp, int(chosen["head_count"]))
        return best

    def load_registry(self):
        table = {}
        total = 0
        for name in self.corpus.group("registry"):
            for row in self.corpus.table(name, sep="\t"):
                total += 1
                table.setdefault(row["block_ref"], []).append(row)
        self.bump("registry", total)
        for ref in table:
            table[ref].sort(key=lambda row: (parse_day(row["observed_at"]), row["record_id"]))
        self.registry = table

    def registry_value(self, ref, day):
        value = None
        for row in self.registry.get(ref, []):
            if parse_day(row["observed_at"]) > day:
                break
            raw = row.get("head_on_hand")
            if raw is None or raw == "":
                continue
            if raw == "\\N":
                value = None
                continue
            value = int(raw)
        return value

    def load_amendments(self):
        table = {}
        total = 0
        for name in self.corpus.group("amendments"):
            for row in self.corpus.records(name):
                total += 1
                table.setdefault((row["block_ref"], row["round_code"]), []).append(row)
        self.bump("amendment_notices", total)
        self.amendments = table

    def adjust(self, text):
        body = text.strip()
        if body.startswith("(") and body.endswith(")"):
            return -int(body[1:-1])
        return int(body)

    def apply_amendments(self, ref, codes, region, target, base, since_utc, limit_utc):
        notices = []
        for code in codes:
            for row in self.amendments.get((ref, code), []):
                if row["target"] == target:
                    notices.append(row)
        notices.sort(key=lambda row: (parse_stamp(row["recorded_at"]), row["notice_ref"]))
        value = base
        for row in notices:
            rule = self.scopes.get(row["signed_by"])
            if rule is None or not rule["can_amend"] or region not in rule["regions"]:
                self.counted["RC_AMENDMENT_UNAUTHORISED"] += 1
                self.audit["amendments_unauthorised"] += 1
                continue
            stamp = parse_stamp(row["recorded_at"])
            if stamp <= since_utc or stamp >= limit_utc:
                self.counted["RC_AMENDMENT_STALE"] += 1
                self.audit["amendments_stale"] += 1
                continue
            value = value + self.adjust(row["adjustment"])
            self.audit["amendments_applied"] += 1
        return max(0, value)

    # ---------- claims ----------
    def load_requisitions(self):
        rows = []
        total = 0
        for name in self.corpus.group("field_intake"):
            for row in self.corpus.table(name):
                total += 1
                rows.append(row)
        self.bump("field_intake", total)
        self.requisitions = rows

    def admit(self):
        groups = {}
        for row in self.requisitions:
            code = row["round_code"]
            settle = self.settles_in.get(code)
            if code not in self.start or settle is None:
                self.rejects["RC_UNKNOWN_BLOCK"] += 1
                continue
            begin, end = self.window(code)
            key = self.resolve_key(row["holding_key"])
            ref, hops = (None, 0) if key is None else self.resolve_block(key, begin.date())
            if ref is None:
                self.rejects["RC_UNKNOWN_BLOCK"] += 1
                continue
            if hops:
                self.audit["alias_hops"][str(hops)] += 1
            effective = parse_stamp(row["effective_at"])
            recorded = parse_stamp(row["recorded_at"])
            if effective < begin or effective >= end:
                self.rejects["RC_WINDOW"] += 1
                continue
            if recorded >= end:
                self.rejects["RC_LATE_RECORD"] += 1
                continue
            version = self.master_version(ref, begin.date())
            if version is None:
                self.rejects["RC_UNKNOWN_BLOCK"] += 1
                continue
            region = version["region"]
            depot = self.depot_of[region]
            withdrawn = version["withdrawn_from"]
            if withdrawn and parse_day(withdrawn) <= begin.date():
                self.rejects["RC_WITHDRAWN_BLOCK"] += 1
                continue
            begin_utc = self.to_utc(depot, begin)
            end_utc = self.to_utc(depot, end)
            if any(begin_utc <= item < end_utc for item in self.restocks.get(ref, [])):
                self.rejects["RC_EPOCH_GAP"] += 1
                continue
            if (ref, code) in self.event_conflicts:
                self.rejects["RC_EVENT_CONFLICT"] += 1
                continue
            groups.setdefault((ref, settle), []).append((row, code, recorded, version, region, depot))
        self.groups = groups

    def collapse(self):
        claims = {}
        for key in sorted(self.groups):
            members = sorted(self.groups[key], key=lambda item: (item[2], item[0]["req_ref"]))
            limit = members[0][2] + timedelta(hours=self.collapse_hours)
            inside = [item for item in members if item[2] <= limit]
            outside = len(members) - len(inside)
            self.counted["RC_STALE_REVISION"] += outside
            self.audit["stale_revisions"] += outside
            self.counted["RC_DUPLICATE_COLLAPSED"] += len(inside) - 1
            self.audit["collapsed_duplicates"] += len(inside) - 1
            claims[key] = (inside[-1], sorted({item[1] for item in members}))
        self.claim_rows = claims

    def build_head_facts(self):
        facts = {}
        for (ref, settle), (survivor, codes) in self.claim_rows.items():
            row, named, recorded, version, region, depot = survivor
            begin, end = self.window(settle)
            named_end = self.window(named)[1]
            begin_utc = self.to_utc(depot, begin)
            limit_utc = self.to_utc(depot, named_end)
            identity = "%s#%d" % (ref, self.epoch(ref, begin_utc))
            lookup = sorted(set(codes) | set(self.rolls_into.get(settle, [])) | {settle})
            dispatched = self.dispatch_value(ref, lookup, limit_utc)
            if row["species"] != version["species"] or row["age_class"] != version["age_class"]:
                self.audit["attribute_overrides"] += 1
            facts[(identity, settle)] = {
                "ref": ref,
                "settle": settle,
                "named": named,
                "codes": lookup,
                "region": region,
                "depot": depot,
                "segment": version["segment"],
                "species": version["species"],
                "age": version["age_class"],
                "begin": begin,
                "end": end,
                "limit_utc": limit_utc,
                "recorded_local": recorded,
                "identity": identity,
                "field_intake": None if not row["head_count"] else int(row["head_count"]),
                "dispatch_stream": None if dispatched is None else dispatched[1],
                "dispatch_stamp": None if dispatched is None else dispatched[0],
                "registry": self.registry_value(ref, begin.date()),
            }
        self.head_facts = facts

    def governing_source(self, identity, code, before, later):
        facts = self.head_facts.get((identity, code))
        if facts is None:
            return "unknown"
        primary = before if facts["begin"].date() < self.cutover else later
        other = "dispatch_stream" if primary == "field_intake" else "field_intake"
        if facts[primary] is not None:
            return primary
        if facts[other] is not None:
            return other
        if facts["registry"] is not None:
            return "registry"
        return "none"

    def settle_governance(self):
        observed = []
        for name in self.corpus.group("observations"):
            if "governance" not in name:
                continue
            for line in self.corpus.flat(name):
                fields = {}
                for token in line.split():
                    if "=" in token:
                        label, value = token.split("=", 1)
                        fields[label] = value
                if fields.get("obs") == "head_count":
                    observed.append((fields["block"], fields["round"], fields["governed_by"]))
        self.governance_observations = observed
        picks = []
        for before in SOURCES:
            for later in SOURCES:
                if all(
                    self.governing_source(block, code, before, later) == recorded
                    for block, code, recorded in observed
                ):
                    picks.append((before, later))
        if len(picks) != 1:
            raise SystemExit("settlement evidence does not single out one governing order")
        self.governs_before, self.governs_from = picks[0]

    def build_entitlements(self):
        claims = {}
        for key in sorted(self.head_facts):
            identity, settle = key
            facts = self.head_facts[key]
            source = self.governing_source(identity, settle, self.governs_before, self.governs_from)
            if source == "none":
                self.rejects["RC_NO_HEADCOUNT"] += 1
                continue
            head = facts[source]
            depot = facts["depot"]
            begin = facts["begin"]
            limit_utc = facts["limit_utc"]
            if source == "field_intake":
                since = self.to_utc(depot, facts["recorded_local"])
            elif source == "dispatch_stream":
                since = facts["dispatch_stamp"]
            else:
                since = self.to_utc(depot, datetime.combine(begin.date(), datetime.min.time()))
            head = self.apply_amendments(
                facts["ref"], facts["codes"], facts["region"], "head_count", head, since, limit_utc
            )
            factor = self.factor_for(facts["region"], facts["species"], facts["age"], begin.date())
            numerator = head * factor
            if numerator % 10000 == 5000:
                self.audit["exact_half_entitlements"] += 1
            entitlement = half_up(numerator, 10000)
            ceiling = self.ceilings.get((facts["ref"], settle))
            if ceiling is not None:
                ceiling = self.apply_amendments(
                    facts["ref"],
                    facts["codes"],
                    facts["region"],
                    "handling_ceiling",
                    ceiling,
                    self.ceiling_stamp[(facts["ref"], settle)],
                    limit_utc,
                )
                if ceiling < entitlement:
                    self.audit["ceiling_clamped"] += 1
                    entitlement = ceiling
            claims[(facts["region"], settle, identity)] = {
                "identity": identity,
                "ref": facts["ref"],
                "segment": facts["segment"],
                "tier": self.tier_for(facts["ref"], begin.date()),
                "entitlement": entitlement,
            }
        self.claims = claims
        self.audit["epoch_identities"] = len(
            {value["identity"] for value in claims.values() if int(value["identity"].split("#")[1]) > 1}
        )

    # ---------- supply ----------
    def load_lots(self):
        lots = []
        total = 0
        for name in self.corpus.group("lot_register"):
            for row in self.corpus.table(name):
                total += 1
                lots.append(row)
        self.bump("lot_register", total)
        certs = {}
        cert_total = 0
        for name in self.corpus.group("release_certificates"):
            for row in self.corpus.table(name):
                cert_total += 1
                certs.setdefault((row["lot_ref"], row["production_year"]), []).append(row)
        self.bump("release_certificates", cert_total)
        assays = {}
        for name in self.corpus.group("assay"):
            for line in self.corpus.flat(name):
                padded = line + " " * 46
                assays[(padded[0:9].strip(), padded[9:13].strip())] = int(padded[33:41])
        self.bump("assay", len(assays))
        self.lots = sorted(lots, key=lambda row: (row["lot_ref"], row["production_year"]))
        self.certs = certs
        self.assays = assays

    def lot_content(self, row):
        depot = row["depot"]
        year = row["production_year"]
        declared = self.units.get("lot_register.quantity", {}).get("%s.%s" % (depot, year))
        if declared is None:
            self.counted["RC_UNIT_UNDECLARED"] += 1
            self.audit["unit_undeclared_lots"] += 1
            return None
        key = (row["lot_ref"], year)
        if key in self.assays:
            per_unit = self.assays[key]
        else:
            options = [
                item
                for item in self.potency.get((depot, row["serotype"], declared), [])
                if item[0] <= parse_day(row["consign_date"])
            ]
            if not options:
                raise SystemExit("no potency factor for %s %s %s" % (depot, row["serotype"], declared))
            per_unit = options[-1][3]
        return (scaled(row["quantity"]) * per_unit) // 1000000

    def lot_state_at(self, key, moment_utc):
        memo = (key, moment_utc)
        if memo in self.cache_state:
            return self.cache_state[memo]
        rows = [row for row in self.certs.get(key, []) if parse_stamp(row["issued_at"]) <= moment_utc]
        if not rows:
            answer = ("quarantine", 0, False)
            self.cache_state[memo] = answer
            return answer
        present = {row["cert_ref"] for row in rows}
        edges = {row["cert_ref"]: row["supersedes"] for row in rows if row["supersedes"] in present}
        looped = False
        for node in sorted(edges):
            path = set()
            step = node
            while step in edges:
                if step in path:
                    looped = True
                    break
                path.add(step)
                step = edges[step]
            if looped:
                break
        if looped:
            answer = ("cycle", 0, False)
            self.cache_state[memo] = answer
            return answer
        superseded = set(edges.values())
        live = [row for row in rows if row["cert_ref"] not in superseded]
        if not live:
            answer = ("cycle", 0, False)
            self.cache_state[memo] = answer
            return answer
        live.sort(key=lambda row: (parse_stamp(row["issued_at"]), row["cert_ref"]))
        state = "quarantine"
        illegal = 0
        reinstated = False
        for row in live:
            target = row["state"]
            if target == state:
                continue
            if (state, target) not in TRANSITIONS:
                illegal += 1
                continue
            if target == "reinstated":
                rule = self.scopes.get(row["signed_by"])
                if rule is None or not rule["can_reinstate"]:
                    illegal += 1
                    continue
                state = "released"
                reinstated = True
                continue
            state = target
        answer = (state, illegal, reinstated)
        self.cache_state[memo] = answer
        return answer

    def substitute(self, serotype, target, day):
        memo = (serotype, target, day)
        if memo in self.cache_sub:
            return self.cache_sub[memo]
        answer = self.search_path(serotype, target, day)
        self.cache_sub[memo] = answer
        return answer

    def search_path(self, serotype, target, day):
        if serotype == target:
            return (0, 100)
        direct = [
            edge
            for edge in self.edges.get(serotype, [])
            if edge[0] <= day and (edge[1] is None or day < edge[1]) and edge[2] == target
        ]
        if direct:
            direct.sort(key=lambda edge: (-edge[3], edge[4]))
            return (1, direct[0][3])
        if self.max_sub_hops < 2:
            return None
        best = None
        for first in self.edges.get(serotype, []):
            if not (first[0] <= day and (first[1] is None or day < first[1])):
                continue
            for second in self.edges.get(first[2], []):
                if not (second[0] <= day and (second[1] is None or day < second[1])):
                    continue
                if second[2] != target:
                    continue
                mark = (-(first[3] * second[3]), first[4], second[4])
                if best is None or mark < best[0]:
                    best = (mark, first[3] * second[3])
        if best is None:
            return None
        return (2, best[1])

    def build_supply(self):
        self.pool = {region: [] for region in REGIONS}
        seen_cycle = set()
        counted_illegal = set()
        counted_missing = set()
        for row in self.lots:
            depot = row["depot"]
            region = self.region_of[depot]
            key = (row["lot_ref"], row["production_year"])
            settle = self.settles_in.get(row["consign_round"])
            if settle is None:
                continue
            content = self.lot_content(row)
            if content is None:
                continue
            expiry = parse_stamp(row["expiry_at"])
            entry = None
            hops = 0
            percent = 100
            for code in self.live[self.position[settle] :]:
                begin, _ = self.window(code)
                if expiry <= begin:
                    break
                state, illegal, reinstated = self.lot_state_at(key, self.to_utc(depot, begin))
                if state == "cycle":
                    if key not in seen_cycle:
                        seen_cycle.add(key)
                        self.counted["RC_LOT_CYCLE"] += 1
                        self.audit["lots_unresolved_cycle"] += 1
                    break
                if illegal and key not in counted_illegal:
                    counted_illegal.add(key)
                    self.counted["RC_ILLEGAL_TRANSITION"] += illegal
                    self.audit["illegal_transitions"] += illegal
                if state != "released":
                    continue
                path = self.substitute(row["serotype"], self.target_serotype(region, code), begin.date())
                if path is None:
                    if key not in counted_missing:
                        counted_missing.add(key)
                        self.counted["RC_NO_SUBSTITUTE"] += 1
                        self.audit["lots_without_substitute"] += 1
                    continue
                entry = code
                hops, percent = path
                if reinstated:
                    self.audit["reinstated_lots"] += 1
                break
            if entry is None:
                continue
            usable = content if hops == 0 else (content * percent) // (100 ** hops)
            if hops:
                self.audit["substituted_lots"][str(hops)] += 1
            self.pool[region].append(
                {
                    "key": "%s@%s" % (row["lot_ref"], row["production_year"]),
                    "ref": row["lot_ref"],
                    "year": row["production_year"],
                    "entry": entry,
                    "expiry": expiry,
                    "serotype": row["serotype"],
                    "content": usable,
                    "hops": hops,
                    "depot": depot,
                }
            )
        for region in self.pool:
            self.pool[region].sort(key=lambda item: (item["expiry"], item["ref"], item["year"]))

    def eligible(self, region, code, lot):
        memo = (code, lot["key"])
        if memo in self.cache_elig:
            return self.cache_elig[memo]
        begin, _ = self.window(code)
        answer = True
        if self.position[lot["entry"]] > self.position[code]:
            answer = False
        elif lot["expiry"] <= begin:
            answer = False
        elif self.lot_state_at((lot["ref"], lot["year"]), self.to_utc(lot["depot"], begin))[0] != "released":
            answer = False
        elif self.substitute(lot["serotype"], self.target_serotype(region, code), begin.date()) is None:
            answer = False
        self.cache_elig[memo] = answer
        return answer

    def build_members(self):
        self.members = {}
        for code in self.live:
            begin, _ = self.window(code)
            table = {region: [] for region in REGIONS}
            for block_ref in sorted(self.master):
                version = self.master_version(block_ref, begin.date())
                if version is None:
                    continue
                region = version["region"]
                if region not in table:
                    continue
                depot = self.depot_of[region]
                identity = "%s#%d" % (block_ref, self.epoch(block_ref, self.to_utc(depot, begin)))
                table[region].append((block_ref, identity))
            self.members[code] = table

    # ---------- ladder ----------
    def run_ladder(self, scope, collect=None):
        remaining = {}
        for region in REGIONS:
            for lot in self.pool[region]:
                remaining[lot["key"]] = lot["content"]
        balances = {}
        awarded_total = {}
        deferred_total = {}
        ledger = {region: [] for region in REGIONS}
        cells = {region: [] for region in REGIONS}
        written = {region: 0 for region in REGIONS}
        clearing_rounds = {region: [] for region in REGIONS}
        extinguished = {"no_show": 0, "epoch": 0}
        identity_now = {}
        for code in self.live:
            begin, _ = self.window(code)
            for region in REGIONS:
                members = self.members[code][region]
                for block_ref, identity in members:
                    previous = identity_now.get(block_ref)
                    if previous is not None and previous != identity and balances.get(previous):
                        extinguished["epoch"] += 1
                        balances[previous] = 0
                    identity_now[block_ref] = identity
                write_now = 0
                for lot in self.pool[region]:
                    if lot["expiry"] <= begin and remaining.get(lot["key"]):
                        write_now += remaining[lot["key"]]
                        remaining[lot["key"]] = 0
                written[region] += write_now
                available = 0
                usable_lots = []
                for lot in self.pool[region]:
                    if remaining.get(lot["key"], 0) <= 0 or not self.eligible(region, code, lot):
                        continue
                    usable_lots.append(lot)
                    available += remaining[lot["key"]]
                cell_claims = []
                for block_ref, identity in members:
                    claim = self.claims.get((region, code, identity))
                    if claim is None:
                        continue
                    balance = balances.get(identity, 0)
                    cell_claims.append(
                        {
                            "identity": identity,
                            "ref": block_ref,
                            "tier": claim["tier"],
                            "entitlement": claim["entitlement"],
                            "carried": balance,
                            "claimable": claim["entitlement"] + balance,
                            "segment": claim["segment"],
                        }
                    )
                cell_claims.sort(key=lambda item: (item["tier"], item["identity"]))
                total_claimable = sum(item["claimable"] for item in cell_claims)
                pot = available
                waterline = -1
                binding = 0
                awards = {}
                for tier in range(1, self.tier_count + 1):
                    tier_claims = [item for item in cell_claims if item["tier"] == tier and item["claimable"] > 0]
                    if not tier_claims:
                        continue
                    demand = sum(item["claimable"] for item in tier_claims)
                    if demand <= pot:
                        for item in tier_claims:
                            awards[item["identity"]] = item["claimable"]
                        pot -= demand
                        continue
                    low = 0
                    high = max(item["claimable"] for item in tier_claims)
                    level = 0
                    while low <= high:
                        mid = (low + high) // 2
                        if sum(min(item["claimable"], mid) for item in tier_claims) <= pot:
                            level = mid
                            low = mid + 1
                        else:
                            high = mid - 1
                    for item in tier_claims:
                        awards[item["identity"]] = min(item["claimable"], level)
                    spare = pot - sum(awards[item["identity"]] for item in tier_claims)
                    for item in tier_claims:
                        if spare <= 0:
                            break
                        if item["claimable"] > awards[item["identity"]]:
                            awards[item["identity"]] += 1
                            spare -= 1
                    waterline = level
                    binding = tier
                    pot = 0
                    break
                for item in cell_claims:
                    awards.setdefault(item["identity"], 0)
                    item["full"] = awards[item["identity"]] == item["claimable"] and item["claimable"] > 0
                served = {}
                cursor = 0
                for item in cell_claims:
                    need = awards[item["identity"]]
                    while need > 0 and cursor < len(usable_lots):
                        lot = usable_lots[cursor]
                        free = remaining.get(lot["key"], 0)
                        if free <= 0:
                            cursor += 1
                            continue
                        if item["identity"] not in served:
                            served[item["identity"]] = (lot["key"], lot["hops"])
                        take = min(free, need)
                        remaining[lot["key"]] = free - take
                        need -= take
                clearing = total_claimable < available
                if clearing:
                    clearing_rounds[region].append(code)
                cleared_here = 0
                for item in cell_claims:
                    award = awards[item["identity"]]
                    deferred = item["claimable"] - award
                    carry = min(deferred, self.cap_multiple * item["entitlement"])
                    if self.no_shows.get((item["ref"], code)):
                        if carry:
                            extinguished["no_show"] += 1
                        carry = 0
                    if self.covers(scope, clearing, item, True):
                        if carry:
                            cleared_here += 1
                        carry = 0
                    awarded_total[item["identity"]] = awarded_total.get(item["identity"], 0) + award
                    deferred_total[item["identity"]] = deferred_total.get(item["identity"], 0) + deferred
                    balances[item["identity"]] = carry
                    if item["claimable"] == 0:
                        outcome, reason = "declined", "CEILING_ZERO"
                    elif award == item["claimable"]:
                        outcome, reason = "full", "AWARD_FULL"
                    elif award == 0:
                        outcome, reason = "zero", "SUPPLY_EXHAUSTED"
                    else:
                        outcome, reason = "partial", "LEVEL_BOUND"
                    lot_key, lot_hops = served.get(item["identity"], ("", 0))
                    ledger[region].append(
                        {
                            "block": item["identity"],
                            "round": code,
                            "tier": item["tier"],
                            "entitlement_doses": item["entitlement"],
                            "carried_claim_doses": item["carried"],
                            "claimable_doses": item["claimable"],
                            "awarded_doses": award,
                            "deferred_doses": deferred,
                            "awarded_to_date": awarded_total[item["identity"]],
                            "deferred_to_date": deferred_total[item["identity"]],
                            "carry_forward_doses": carry,
                            "served_lot": lot_key,
                            "substitution_hops": lot_hops,
                            "outcome": outcome,
                            "reason": reason,
                            "segment": item["segment"],
                        }
                    )
                    if collect is not None:
                        collect.append((region, code, item["identity"], self.covers(scope, clearing, item, True)))
                claimed = {item["identity"] for item in cell_claims}
                for block_ref, identity in members:
                    if identity in claimed:
                        continue
                    silent = {"identity": identity, "ref": block_ref, "tier": None, "full": False}
                    if self.covers(scope, clearing, silent, False):
                        if balances.get(identity):
                            cleared_here += 1
                        balances[identity] = 0
                    if collect is not None:
                        collect.append((region, code, identity, self.covers(scope, clearing, silent, False)))
                awarded_here = sum(awards[item["identity"]] for item in cell_claims)
                cells[region].append(
                    {
                        "round": code,
                        "available_doses": available,
                        "claimable_doses": total_claimable,
                        "awarded_doses": awarded_here,
                        "waterline": waterline,
                        "binding_tier": binding,
                        "surplus_doses": available - awarded_here,
                        "cleared_balances": cleared_here,
                        "written_off_doses": write_now,
                    }
                )
        return {
            "ledger": ledger,
            "cells": cells,
            "written": written,
            "clearing": clearing_rounds,
            "extinguished": extinguished,
        }

    def covers(self, scope, clearing, item, has_claim):
        if not clearing or scope == "none":
            return False
        if scope == "region_wide":
            return True
        if scope == "fully_awarded_only":
            return bool(has_claim and item["full"])
        if scope == "tier1_only":
            return bool(has_claim and item["tier"] == 1)
        return False

    def settle_clearance(self):
        observed = []
        for name in self.corpus.group("observations"):
            if "clearance" not in name:
                continue
            for line in self.corpus.flat(name):
                fields = {}
                for token in line.split():
                    if "=" in token:
                        label, value = token.split("=", 1)
                        fields[label] = value
                if fields.get("obs") == "carry":
                    observed.append((fields["region"], fields["round"], fields["block"], fields["balance_cleared"]))
        self.clearance_observations = observed
        wanted = {(region, code, block): flag for region, code, block, flag in observed}
        picks = []
        for scope in SCOPES:
            collected = []
            self.run_ladder(scope, collect=collected)
            table = {}
            for region, code, identity, flag in collected:
                table[(region, code, identity)] = "yes" if flag else "no"
            if all(table.get(key) == value for key, value in wanted.items()):
                picks.append(scope)
        if len(picks) != 1:
            raise SystemExit("clearance evidence does not single out one scope")
        self.clearance_scope = picks[0]

    # ---------- emit ----------
    def emit(self, out: Path):
        result = self.final
        out.mkdir(parents=True, exist_ok=True)
        totals = {"claimable": 0, "awarded": 0, "deferred": 0, "carry": 0, "available": 0, "surplus": 0, "written": 0}
        rollup = {}
        for segment in SEGMENTS:
            rollup[segment] = {
                "regions": {
                    region: {
                        "claims": 0,
                        "awarded_doses": 0,
                        "claimable_doses": 0,
                        "deferred_doses": 0,
                        "carry_forward_doses": 0,
                        "full": 0,
                        "partial": 0,
                        "zero": 0,
                        "declined": 0,
                    }
                    for region in REGIONS
                },
                "rounds": {code: {"claims": 0, "awarded_doses": 0, "deferred_doses": 0} for code in self.live},
            }
        region_totals = {}
        for region in REGIONS:
            rows = result["ledger"][region]
            document = {
                "region": region,
                "rounds": list(self.live),
                "ledger": [{key: row[key] for key in row if key != "segment"} for row in rows],
                "cells": result["cells"][region],
            }
            (out / ("region_%s.json" % region)).write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
            awarded = sum(row["awarded_doses"] for row in rows)
            deferred = sum(row["deferred_doses"] for row in rows)
            region_totals[region] = {
                "region": region,
                "claims": len(rows),
                "awarded_doses": awarded,
                "deferred_doses": deferred,
            }
            totals["awarded"] += awarded
            totals["deferred"] += deferred
            totals["claimable"] += sum(row["claimable_doses"] for row in rows)
            totals["carry"] += sum(row["carry_forward_doses"] for row in rows)
            totals["available"] += sum(cell["available_doses"] for cell in result["cells"][region])
            totals["surplus"] += sum(cell["surplus_doses"] for cell in result["cells"][region])
            totals["written"] += result["written"][region]
            for row in rows:
                bucket = rollup[row["segment"]]["regions"][region]
                bucket["claims"] += 1
                bucket["awarded_doses"] += row["awarded_doses"]
                bucket["claimable_doses"] += row["claimable_doses"]
                bucket["deferred_doses"] += row["deferred_doses"]
                bucket["carry_forward_doses"] += row["carry_forward_doses"]
                bucket[row["outcome"]] += 1
                slot = rollup[row["segment"]]["rounds"][row["round"]]
                slot["claims"] += 1
                slot["awarded_doses"] += row["awarded_doses"]
                slot["deferred_doses"] += row["deferred_doses"]
        for segment in SEGMENTS:
            document = {
                "segment": segment,
                "regions": [dict(region=region, **rollup[segment]["regions"][region]) for region in REGIONS],
                "rounds": [dict(round=code, **rollup[segment]["rounds"][code]) for code in self.live],
            }
            (out / ("segment_%s.json" % segment)).write_text(json.dumps(document, indent=1, sort_keys=True) + "\n")
        summary = {
            "live_rounds": list(self.live),
            "skipped_rounds": sorted(self.skipped),
            "claims_settled": sum(len(result["ledger"][region]) for region in REGIONS),
            "claims_rejected": sum(self.rejects.values()),
            "blocks_settled": len({row["block"] for region in REGIONS for row in result["ledger"][region]}),
            "claimable_doses": totals["claimable"],
            "awarded_doses": totals["awarded"],
            "deferred_doses": totals["deferred"],
            "carry_forward_doses": totals["carry"],
            "available_doses": totals["available"],
            "surplus_doses": totals["surplus"],
            "written_off_doses": totals["written"],
            "regions": [region_totals[region] for region in REGIONS],
            "segments": [
                {
                    "segment": segment,
                    "claims": sum(rollup[segment]["regions"][region]["claims"] for region in REGIONS),
                    "awarded_doses": sum(rollup[segment]["regions"][region]["awarded_doses"] for region in REGIONS),
                }
                for segment in SEGMENTS
            ],
        }
        (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
        audit = dict(self.audit)
        audit["governing_source"] = {"before_cutover": self.governs_before, "from_cutover": self.governs_from}
        audit["balance_clearance_scope"] = self.clearance_scope
        audit["binding_tiers"] = {str(index): 0 for index in range(0, self.tier_count + 1)}
        for region in REGIONS:
            for cell in result["cells"][region]:
                audit["binding_tiers"][str(cell["binding_tier"])] += 1
        audit["clearing_rounds"] = [{"region": region, "rounds": result["clearing"][region]} for region in REGIONS]
        audit["extinguished_no_show"] = result["extinguished"]["no_show"]
        audit["extinguished_epoch"] = result["extinguished"]["epoch"]
        (out / "policy_audit.json").write_text(json.dumps(audit, indent=1, sort_keys=True) + "\n")
        self.counted["RC_HEADER_GAP"] = self.corpus.header_gaps
        quality = {
            "rejects": {code: self.rejects[code] for code in self.reasons["reject_codes"]},
            "counted": {code: self.counted[code] for code in self.reasons["counted_codes"]},
            "source_rows": {label: self.corpus.source_rows.get(label, 0) for label in SOURCE_ORDER},
        }
        (out / "data_quality.json").write_text(json.dumps(quality, indent=1, sort_keys=False) + "\n")

    def run(self, out: Path):
        self.load_calendar()
        self.load_offsets()
        self.load_blocks()
        self.load_events()
        self.load_dispatch()
        self.load_registry()
        self.load_amendments()
        self.load_requisitions()
        self.load_lots()
        self.admit()
        self.collapse()
        self.build_head_facts()
        self.settle_governance()
        self.build_entitlements()
        self.build_supply()
        self.build_members()
        self.settle_clearance()
        self.final = self.run_ladder(self.clearance_scope)
        self.emit(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    Settlement(Path(args.data)).run(Path(args.out))


if __name__ == "__main__":
    main()
