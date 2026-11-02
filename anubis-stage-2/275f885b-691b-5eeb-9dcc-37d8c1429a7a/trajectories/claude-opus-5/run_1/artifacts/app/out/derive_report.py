#!/usr/bin/env python3
"""Campaign dose ration settlement.

Reads a campaign export folder named by ``--data`` and writes the nine
settlement documents fixed by ``output_contract.md`` into ``--out``.
Standard library only, offline, deterministic.
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

REGION_ORDER = ["North", "South", "West", "East"]
SEGMENT_ORDER = ["commercial", "public"]

SCOPES = ["region_wide", "fully_awarded_only", "tier1_only", "none"]


class Incomplete(Exception):
    pass


# ---------------------------------------------------------------- utilities


def parse_utc(text):
    t = text.strip()
    if not t:
        return None
    if t.endswith("Z"):
        t = t[:-1]
    return datetime.strptime(t.replace("T", " "), "%Y-%m-%d %H:%M:%S")


def parse_local(text):
    t = text.strip()
    if not t:
        return None
    return datetime.strptime(t.replace("T", " "), "%Y-%m-%d %H:%M:%S")


def parse_date(text):
    t = text.strip()
    if not t:
        return None
    return date.fromisoformat(t)


def scaled_int(text, decimals):
    """Exact fixed point parse: returns the value times 10**decimals."""
    t = text.strip()
    negative = t.startswith("-")
    if negative:
        t = t[1:]
    whole, _, frac = t.partition(".")
    frac = (frac + "0" * decimals)[:decimals]
    value = int(whole or "0") * (10 ** decimals) + int(frac or "0")
    return -value if negative else value


def half_away_from_zero(num, den):
    if num >= 0:
        return (2 * num + den) // (2 * den)
    return -((-2 * num + den) // (2 * den))


# ---------------------------------------------------------------- file layer


class Corpus:
    DELIMITED = (".csv", ".tsv")

    def __init__(self, folder):
        self.folder = folder
        self.row_counts = {}
        self.header_gaps = 0
        self._cache = {}

    def path(self, name):
        return os.path.join(self.folder, name)

    def exists(self, name):
        return os.path.isfile(self.path(name))

    def record_lines(self, name):
        if name in self._cache:
            return self._cache[name]
        with open(self.path(name), "r", encoding="utf-8", newline="") as handle:
            lines = handle.read().split("\n")
        declared = None
        body = lines
        if lines and lines[0].startswith("#"):
            if "rows=" in lines[0]:
                declared = int(lines[0].split("rows=", 1)[1].strip())
            body = lines[1:]
        body = [line for line in body if line.strip() != ""]
        if name.endswith(self.DELIMITED):
            header = body[0] if body else ""
            rows = body[1:]
        else:
            header = None
            rows = body
        self.row_counts[name] = len(rows)
        if declared is not None and declared != len(rows):
            self.header_gaps += 1
        self._cache[name] = (header, rows)
        return header, rows

    def table(self, name):
        delim = "\t" if name.endswith(".tsv") else ","
        header, rows = self.record_lines(name)
        fields = next(csv.reader([header], delimiter=delim))
        return [dict(zip(fields, raw)) for raw in csv.reader(rows, delimiter=delim)]

    def ragged(self, name):
        _header, rows = self.record_lines(name)
        return [next(csv.reader([r], delimiter="\t")) for r in rows]

    def jsonl(self, name):
        _header, rows = self.record_lines(name)
        return [json.loads(r) for r in rows]

    def lines(self, name):
        _header, rows = self.record_lines(name)
        return rows

    def text(self, name):
        with open(self.path(name), "r", encoding="utf-8") as handle:
            return handle.read()


def read_manifest(corpus):
    sources = {}
    for line in corpus.text("source_manifest.md").split("\n"):
        line = line.strip()
        if not line.startswith("- ") or ":" not in line:
            continue
        key, rest = line[2:].split(":", 1)
        sources[key.strip()] = rest.split()
    return sources


def read_properties(corpus, name):
    out = {}
    pending = ""
    for line in corpus.text(name).split("\n"):
        stripped = line.strip()
        if not pending and (not stripped or stripped.startswith("#") or stripped.startswith("!")):
            continue
        if pending:
            stripped = pending + " " + stripped
            pending = ""
        if stripped.endswith("\\"):
            pending = stripped[:-1].strip()
            continue
        if "=" in stripped:
            key, value = stripped.split("=", 1)
            out[key.strip()] = value.strip()
    return out


def read_ini(corpus, name):
    out = {}
    section = None
    for line in corpus.text(name).split("\n"):
        stripped = line.strip()
        if not stripped or stripped[0] in ";#":
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            out.setdefault(section, {})
        elif "=" in stripped and section is not None:
            key, value = stripped.split("=", 1)
            out[section][key.strip()] = value.strip()
    return out


# ---------------------------------------------------------------- settlement


class Settlement:
    ALLOWED_MOVES = {
        ("quarantine", "released"),
        ("quarantine", "condemned"),
        ("released", "condemned"),
        ("condemned", "reinstated"),
    }

    def __init__(self, folder):
        self.corpus = Corpus(folder)
        self.load()

    # -- loading ---------------------------------------------------------

    def load(self):
        corpus = self.corpus
        self.manifest = read_manifest(corpus)
        missing = sorted(
            n for files in self.manifest.values() for n in files if not corpus.exists(n)
        )
        if missing:
            raise Incomplete("missing export files: " + ", ".join(missing))

        props = read_properties(corpus, "source_declarations.properties")
        self.anchor = parse_date(props["campaign.anchor.date"])
        self.round_count = int(props["campaign.rounds"])
        self.cutover = parse_date(props["cutover.date"])
        self.window_days = int(props["window.length.days"])
        self.alias_max_hops = int(props["alias.max_hops"])
        self.sub_max_hops = int(props["substitution.max_hops"])
        self.collapse_hours = int(props["collapse.window.hours"])
        self.carry_cap = int(props["carry.cap.multiple"])
        self.tier_count = int(props["tier.count"])
        hour, minute, second = (int(p) for p in props["day.start.local"].split(":"))
        self.day_start_delta = timedelta(hours=hour, minutes=minute, seconds=second)
        self.region_depot = {}
        for part in props["depot.map"].split(","):
            region, depot = part.split(":")
            self.region_depot[region.strip()] = depot.strip()
        self.depot_region = {v: k for k, v in self.region_depot.items()}

        units = read_ini(corpus, "unit_declarations.ini")
        self.lot_units = units.get("lot_register.quantity", {})
        self.assay_decimals = int(
            units.get("potency_assays.doses_per_unit", {}).get("implied_decimals", "3")
        )
        self.reasons = json.loads(corpus.text("reason_codes.json"))
        self.scopes = json.loads(corpus.text("authority_scopes.json"))

        self.load_offsets()
        self.build_calendar()
        self.load_reference()
        self.load_sources()

    def load_offsets(self):
        best = {}
        for row in self.corpus.table("depot_clock_offsets.csv"):
            key = (row["depot"], row["calendar_date"])
            prev = best.get(key)
            if prev is None or row["issued_at"] > prev[0]:
                best[key] = (row["issued_at"], int(row["utc_offset_minutes"]))
        self.offsets = {k: v[1] for k, v in best.items()}

    def offset(self, depot, day):
        key = (depot, day.isoformat())
        if key not in self.offsets:
            raise Incomplete("no clock offset for %s on %s" % (depot, day))
        return self.offsets[key]

    def to_utc(self, depot, local_dt):
        return local_dt - timedelta(minutes=self.offset(depot, local_dt.date()))

    # -- calendar --------------------------------------------------------

    def build_calendar(self):
        recurrence = {
            "R%02d" % (i + 1): self.anchor + timedelta(days=14 * i)
            for i in range(self.round_count)
        }
        notices = defaultdict(list)
        for row in self.corpus.table("calendar_exceptions.csv"):
            if row["region"].strip() == "ALL":
                notices[row["round_code"]].append(row)

        self.round_start = dict(recurrence)
        self.skipped = set()
        for code in recurrence:
            governing = None
            for row in notices.get(code, []):
                key = (row["issued_at"], row["notice_ref"])
                if governing is None or key > (governing["issued_at"], governing["notice_ref"]):
                    governing = row
            if governing is None:
                continue
            action = governing["action"].strip()
            if action == "move":
                self.round_start[code] = parse_date(governing["new_start_date"])
            elif action == "skip":
                self.skipped.add(code)

        self.all_rounds = sorted(recurrence, key=lambda c: (self.round_start[c], c))
        self.live_rounds = [c for c in self.all_rounds if c not in self.skipped]
        self.round_index = {c: i for i, c in enumerate(self.live_rounds)}

        self.settles_in = {}
        self.feeds = defaultdict(list)
        for code in self.all_rounds:
            if code not in self.skipped:
                self.settles_in[code] = code
                continue
            target = None
            for live in self.live_rounds:
                if self.round_start[live] > self.round_start[code]:
                    target = live
                    break
            self.settles_in[code] = target
            if target is not None:
                self.feeds[target].append(code)

        self.open_local = {}
        self.close_local = {}
        for code in self.all_rounds:
            base = datetime.combine(self.round_start[code], datetime.min.time())
            self.open_local[code] = base + self.day_start_delta
            self.close_local[code] = self.open_local[code] + timedelta(days=self.window_days)

    def depot_open_utc(self, code, depot):
        return self.to_utc(depot, self.open_local[code])

    def depot_close_utc(self, code, depot):
        return self.to_utc(depot, self.close_local[code])

    # -- reference tables -------------------------------------------------

    def load_reference(self):
        corpus = self.corpus
        self.master = defaultdict(list)
        for row in corpus.table("block_master.csv"):
            self.master[row["block_ref"]].append(row)
        for rows in self.master.values():
            rows.sort(key=lambda r: (r["valid_from"], r["record_id"]))

        self.alias = defaultdict(list)
        for row in corpus.table("block_alias_map.csv"):
            self.alias[row["alias_key"]].append(row)

        self.priority = defaultdict(list)
        for row in corpus.table("priority_register.csv"):
            self.priority[row["block_ref"]].append(row)

        self.ceilings = {}
        for name in self.manifest["ceilings"]:
            for row in corpus.table(name):
                key = (row["block_ref"], row["round_code"])
                prev = self.ceilings.get(key)
                if prev is None or (row["issued_at"], row["entry_ref"]) > (
                    prev["issued_at"],
                    prev["entry_ref"],
                ):
                    self.ceilings[key] = row

        self.dose_factors = defaultdict(list)
        for row in corpus.table("dose_factors.csv"):
            self.dose_factors[(row["region"], row["species"], row["age_class"])].append(row)

        self.potency = defaultdict(list)
        for row in corpus.table("potency_factors.csv"):
            self.potency[(row["depot"], row["serotype"], row["unit"])].append(row)

        self.sub_edges = corpus.table("substitution_graph.csv")

        self.phases = defaultdict(list)
        for row in corpus.table("campaign_phases.csv"):
            self.phases[(row["region"], row["round_code"])].append(row)

    def master_version(self, block_ref, when):
        chosen = None
        for row in self.master.get(block_ref, ()):
            if parse_date(row["valid_from"]) <= when:
                chosen = row
            else:
                break
        return chosen

    # -- primary sources --------------------------------------------------

    def load_sources(self):
        corpus = self.corpus
        self.requisitions = []
        for name in self.manifest["field_intake"]:
            self.requisitions.extend(corpus.table(name))

        self.dispatch_index = defaultdict(list)
        for name in self.manifest["dispatch_stream"]:
            for record in corpus.jsonl(name):
                self.dispatch_index[(record["block_ref"], record["round_code"])].append(
                    (int(record["version"]), parse_utc(record["recorded_at"]), record)
                )

        self.registry_index = defaultdict(list)
        for name in self.manifest["registry"]:
            for raw in corpus.ragged(name):
                block = raw[1] if len(raw) > 1 else ""
                observed = raw[2] if len(raw) > 2 else ""
                head = raw[3] if len(raw) > 3 else None
                self.registry_index[block].append((observed, raw[0] if raw else "", head))
        for rows in self.registry_index.values():
            rows.sort(key=lambda r: (r[0], r[1]))

        self.visits = []
        for name in self.manifest["visit_events"]:
            self.visits.extend(corpus.jsonl(name))

        self.amend_index = defaultdict(list)
        for name in self.manifest["amendments"]:
            for notice in corpus.jsonl(name):
                self.amend_index[
                    (notice["block_ref"], notice["round_code"], notice["target"])
                ].append(notice)
        for items in self.amend_index.values():
            items.sort(key=lambda n: (n["recorded_at"], n["notice_ref"]))

        self.lots = []
        for name in self.manifest["lot_register"]:
            self.lots.extend(corpus.table(name))

        self.cert_index = defaultdict(list)
        for name in self.manifest["release_certificates"]:
            for cert in corpus.table(name):
                self.cert_index[(cert["lot_ref"], cert["production_year"])].append(
                    (parse_utc(cert["issued_at"]), cert["cert_ref"], cert)
                )
        for items in self.cert_index.values():
            items.sort(key=lambda c: (c[0], c[1]))

        self.assays = {}
        for name in self.manifest["assay"]:
            for line in corpus.lines(name):
                self.assays[(line[0:9].strip(), line[9:13].strip())] = int(line[33:41])

        self.governance_log = self.parse_observation("governance_observations.log")
        self.clearance_log = self.parse_observation("clearance_observations.log")

        for group in self.manifest.values():
            for name in group:
                if name.endswith((".csv", ".tsv", ".jsonl", ".txt", ".log")):
                    self.corpus.record_lines(name)

        self.build_visit_index()

    def parse_observation(self, name):
        out = []
        for line in self.corpus.lines(name):
            parts = line.split()
            record = {}
            for token in parts[1:]:
                if "=" in token:
                    key, value = token.split("=", 1)
                    record[key] = value
            out.append(record)
        return out

    def build_visit_index(self):
        by_id = defaultdict(list)
        for event in self.visits:
            by_id[event["event_id"]].append(event)
        self.conflict_pairs = set()
        self.no_show = defaultdict(set)
        self.restocks = defaultdict(list)
        for events in by_id.values():
            shapes = {json.dumps(e, sort_keys=True) for e in events}
            if len(shapes) > 1:
                for event in events:
                    self.conflict_pairs.add((event["block_ref"], event["round_code"]))
                continue
            event = events[0]
            if event["event"] == "no_show":
                self.no_show[event["block_ref"]].add(event["round_code"])
            elif event["event"] == "restock":
                self.restocks[event["block_ref"]].append(parse_utc(event["occurred_at"]))
        for stamps in self.restocks.values():
            stamps.sort()

    def registry_head(self, block_ref, on_or_before):
        value = None
        limit = on_or_before.isoformat()
        for observed, _ref, head in self.registry_index.get(block_ref, ()):
            if observed > limit:
                break
            if head is None:
                continue
            text = head.strip()
            if text == "":
                continue
            if text == "\\N":
                value = None
                continue
            value = int(text)
        return value

    # -- identity ---------------------------------------------------------

    @staticmethod
    def normalise_key(raw):
        text = raw.strip().upper().split("/")[0]
        digits = "".join(ch for ch in text if ch.isdigit())
        return "BLK-" + digits.zfill(4) if digits else None

    def resolve_key(self, raw, on_day):
        key = self.normalise_key(raw)
        if key is None:
            return None, 0
        seen = {key}
        hops = 0
        while True:
            if key in self.master:
                return key, hops
            if hops >= self.alias_max_hops:
                return None, hops
            chosen = None
            for row in self.alias.get(key, ()):
                start = parse_date(row["effective_from"])
                end = parse_date(row["effective_to"]) if row["effective_to"].strip() else None
                if on_day < start or (end is not None and on_day >= end):
                    continue
                if chosen is None or (row["effective_from"], row["issued_at"]) > (
                    chosen["effective_from"],
                    chosen["issued_at"],
                ):
                    chosen = row
            if chosen is None:
                return None, hops
            key = chosen["canonical_ref"]
            hops += 1
            if key in seen:
                return None, hops
            seen.add(key)

    def epoch_at(self, block_ref, instant):
        stamps = self.restocks.get(block_ref)
        if not stamps:
            return 1
        return 1 + sum(1 for s in stamps if s < instant)

    # -- admission --------------------------------------------------------

    def admit(self):
        # Reject codes apply in the order errata_notice.md amendment one fixes:
        # unknown block, window, late record, withdrawn block, epoch gap, event
        # conflict, and finally no head count once the surviving row is known.
        self.rejects = defaultdict(int)
        self.alias_hops = defaultdict(int)
        self.window_at_close = 0
        self.window_before_open = 0
        admitted = []
        for row in self.requisitions:
            code = row["round_code"].strip()
            named = code if code in self.round_start else None
            block_ref, hops = (None, 0)
            if named is not None:
                block_ref, hops = self.resolve_key(row["holding_key"], self.round_start[named])
            if named is None or block_ref is None:
                self.rejects["RC_UNKNOWN_BLOCK"] += 1
                continue
            version = self.master_version(block_ref, self.round_start[named])
            if version is None:
                self.rejects["RC_UNKNOWN_BLOCK"] += 1
                continue
            if hops:
                self.alias_hops[hops] += 1

            open_local = self.open_local[named]
            close_local = self.close_local[named]
            effective = parse_local(row["effective_at"])
            recorded = parse_local(row["recorded_at"])
            if effective is None or not (open_local <= effective < close_local):
                self.rejects["RC_WINDOW"] += 1
                if effective is not None:
                    if effective == close_local:
                        self.window_at_close += 1
                    elif effective < open_local:
                        self.window_before_open += 1
                continue
            if recorded is None or recorded >= close_local:
                self.rejects["RC_LATE_RECORD"] += 1
                continue

            region = version["region"]
            depot = self.region_depot[region]
            withdrawn = (
                parse_date(version["withdrawn_from"]) if version["withdrawn_from"].strip() else None
            )
            if withdrawn is not None and withdrawn <= self.round_start[named]:
                self.rejects["RC_WITHDRAWN_BLOCK"] += 1
                continue

            open_utc = self.to_utc(depot, open_local)
            close_utc = self.to_utc(depot, close_local)
            if any(open_utc <= s < close_utc for s in self.restocks.get(block_ref, ())):
                self.rejects["RC_EPOCH_GAP"] += 1
                continue

            settle = self.settles_in[named]
            in_play = [settle] + self.feeds[settle]
            if any((block_ref, rc) in self.conflict_pairs for rc in in_play):
                self.rejects["RC_EVENT_CONFLICT"] += 1
                continue

            epoch = self.epoch_at(block_ref, open_utc)
            admitted.append(
                {
                    "row": row,
                    "block_ref": block_ref,
                    "epoch": epoch,
                    "identity": "%s#%d" % (block_ref, epoch),
                    "named": named,
                    "settle": settle,
                    "region": region,
                    "segment": version["segment"],
                    "version": version,
                    "recorded_local": recorded,
                    "recorded_utc": self.to_utc(depot, recorded),
                    "close_utc": close_utc,
                    "depot": depot,
                }
            )
        return admitted

    def collapse(self, admitted):
        groups = defaultdict(list)
        for item in admitted:
            groups[(item["identity"], item["settle"])].append(item)
        self.collapsed_duplicates = 0
        self.stale_revisions = 0
        span = timedelta(hours=self.collapse_hours)
        survivors = []
        for items in groups.values():
            items.sort(key=lambda i: (i["recorded_local"], i["row"]["req_ref"]))
            limit = items[0]["recorded_local"] + span
            inside = [i for i in items if i["recorded_local"] < limit]
            self.collapsed_duplicates += len(inside) - 1
            self.stale_revisions += len(items) - len(inside)
            survivors.append(inside[-1])
        return survivors

    # -- head counts ------------------------------------------------------

    def dispatch_offer(self, item):
        pool = []
        for rc in [item["settle"]] + self.feeds[item["settle"]]:
            for version, stamp, record in self.dispatch_index.get((item["block_ref"], rc), ()):
                if stamp <= item["close_utc"]:
                    pool.append((version, stamp, record))
        if not pool:
            return None, None
        top = max(p[0] for p in pool)
        best = max(
            (p for p in pool if p[0] == top),
            key=lambda p: (p[1], p[2]["round_code"], p[2]["op"]),
        )
        if best[2]["op"] == "delete":
            return None, None
        return int(best[2]["head_count"]), best[1]

    def field_offer(self, item):
        text = item["row"]["head_count"].strip()
        if text == "":
            return None, None
        return int(text), item["recorded_utc"]

    def registry_offer(self, item):
        value = self.registry_head(item["block_ref"], self.round_start[item["named"]])
        if value is None:
            return None, None
        day = datetime.combine(self.round_start[item["settle"]], datetime.min.time())
        return value, self.to_utc(item["depot"], day)

    def head_count(self, item, governing):
        other = "dispatch_stream" if governing == "field_intake" else "field_intake"
        getters = {
            "field_intake": self.field_offer,
            "dispatch_stream": self.dispatch_offer,
            "registry": self.registry_offer,
        }
        for source in (governing, other, "registry"):
            value, moment = getters[source](item)
            if value is not None:
                return source, value, moment
        return None, None, None

    def governing_for(self, item, sources):
        side = "from_cutover" if self.round_start[item["named"]] >= self.cutover else "before_cutover"
        return sources[side]

    def decide_governing_source(self, survivors):
        observed = {}
        for entry in self.governance_log:
            token = entry.get("governed_by")
            block = entry.get("block")
            rnd = entry.get("round")
            if token and block and rnd:
                observed[(block, rnd)] = token
        candidates = ["field_intake", "dispatch_stream"]
        score = defaultdict(int)
        for item in survivors:
            token = observed.get((item["identity"], item["settle"]))
            if token is None:
                continue
            side = (
                "from_cutover"
                if self.round_start[item["named"]] >= self.cutover
                else "before_cutover"
            )
            for candidate in candidates:
                if self.head_count(item, candidate)[0] == token:
                    score[(side, candidate)] += 1
        return {
            side: max(candidates, key=lambda c: (score[(side, c)], -candidates.index(c)))
            for side in ("before_cutover", "from_cutover")
        }

    # -- amendments -------------------------------------------------------

    def notices_for(self, block_ref, settle, target):
        out = []
        for rc in [settle] + self.feeds[settle]:
            out.extend(self.amend_index.get((block_ref, rc, target), ()))
        out.sort(key=lambda n: (n["recorded_at"], n["notice_ref"]))
        return out

    @staticmethod
    def adjustment_value(text):
        token = text.strip()
        if token.startswith("(") and token.endswith(")"):
            return -int(token[1:-1])
        return int(token)

    def apply_amendments(self, notices, base, region, recorded_moment, close_utc, stats):
        value = base
        for notice in notices:
            role = self.scopes.get(notice["signed_by"])
            if not (role and role.get("can_amend") and region in role.get("regions", [])):
                stats["unauthorised"] += 1
                continue
            stamp = parse_utc(notice["recorded_at"])
            if recorded_moment is None or not (recorded_moment < stamp < close_utc):
                stats["stale"] += 1
                continue
            value = max(0, value + self.adjustment_value(notice["adjustment"]))
            stats["applied"] += 1
        return value

    # -- lot state --------------------------------------------------------

    def chain_state(self, lot_key, instant, cache):
        hit = cache.get(instant)
        if hit is not None:
            return hit
        in_view = [c for c in self.cert_index.get(lot_key, ()) if c[0] <= instant]
        result = self._chain_state(in_view)
        cache[instant] = result
        return result

    def _chain_state(self, in_view):
        if not in_view:
            return ("quarantine", False, 0, False)
        refs = {c[1] for c in in_view}
        graph = {}
        for _stamp, ref, cert in in_view:
            target = cert["supersedes"].strip()
            if target and target in refs:
                graph[ref] = target
        for start in graph:
            seen = set()
            node = start
            while node in graph:
                if node in seen:
                    return (None, True, 0, False)
                seen.add(node)
                node = graph[node]
        superseded = set(graph.values())
        state = "quarantine"
        illegal = 0
        reinstated = False
        for _stamp, ref, cert in in_view:
            if ref in superseded:
                continue
            target = cert["state"].strip()
            normalised = "released" if target == "reinstated" else target
            if normalised == state:
                continue
            if (state, target) in self.ALLOWED_MOVES:
                if target == "reinstated":
                    role = self.scopes.get(cert["signed_by"])
                    if not (role and role.get("can_reinstate")):
                        illegal += 1
                        continue
                    reinstated = True
                state = normalised
                continue
            illegal += 1
        return (state, False, illegal, reinstated)

    # -- substitution ------------------------------------------------------

    def edges_on(self, day):
        key = day.isoformat()
        cached = self._sub_cache.get(key)
        if cached is not None:
            return cached
        best = {}
        for row in self.sub_edges:
            start = parse_date(row["effective_from"])
            end = parse_date(row["effective_to"]) if row["effective_to"].strip() else None
            if day < start or (end is not None and day >= end):
                continue
            pair = (row["from_serotype"], row["to_serotype"])
            potency = int(row["potency_percent"])
            ref = row["edge_ref"]
            prev = best.get(pair)
            if prev is None or potency > prev[0] or (potency == prev[0] and ref < prev[1]):
                best[pair] = (potency, ref)
        adjacency = defaultdict(list)
        nodes = set()
        for (src, dst), (potency, ref) in sorted(best.items()):
            adjacency[src].append((dst, potency, ref))
            nodes.add(src)
            nodes.add(dst)
        paths = {}
        for src in nodes:
            for dst in nodes:
                if src == dst:
                    continue
                chosen = None
                for edge in adjacency.get(src, ()):
                    if edge[0] != dst:
                        continue
                    candidate = (1, edge[1], (edge[2],))
                    if chosen is None or self._better(candidate, chosen):
                        chosen = candidate
                if chosen is None and self.sub_max_hops >= 2:
                    for first in adjacency.get(src, ()):
                        middle = first[0]
                        if middle in (src, dst):
                            continue
                        for second in adjacency.get(middle, ()):
                            if second[0] != dst:
                                continue
                            candidate = (2, first[1] * second[1], (first[2], second[2]))
                            if chosen is None or self._better(candidate, chosen):
                                chosen = candidate
                if chosen is not None:
                    paths[(src, dst)] = chosen
        self._sub_cache[key] = paths
        return paths

    @staticmethod
    def _better(candidate, current):
        if candidate[0] != current[0]:
            return candidate[0] < current[0]
        if candidate[1] != current[1]:
            return candidate[1] > current[1]
        return candidate[2] < current[2]

    def target_serotype(self, region, code, open_utc):
        chosen = None
        for row in self.phases.get((region, code), ()):
            if parse_utc(row["issued_at"]) <= open_utc:
                if chosen is None or (row["issued_at"], row["revision_ref"]) > (
                    chosen["issued_at"],
                    chosen["revision_ref"],
                ):
                    chosen = row
        return chosen["target_serotype"] if chosen else None

    def dose_content(self, lot, unit):
        key = (lot["lot_ref"], lot["production_year"])
        assay = self.assays.get(key)
        if assay is not None:
            per_unit = assay
            from_assay = True
        else:
            from_assay = False
            consign = parse_date(lot["consign_date"])
            chosen = None
            for row in self.potency.get((lot["depot"], lot["serotype"], unit), ()):
                if parse_date(row["effective_from"]) <= consign:
                    key2 = (row["effective_from"], row["issued_at"], row["factor_ref"])
                    if chosen is None or key2 > (
                        chosen["effective_from"],
                        chosen["issued_at"],
                        chosen["factor_ref"],
                    ):
                        chosen = row
            if chosen is None:
                return None, False
            per_unit = scaled_int(chosen["doses_per_unit"], self.assay_decimals)
        quantity = scaled_int(lot["quantity"], 3)
        divisor = 1000 * (10 ** self.assay_decimals)
        return (quantity * per_unit) // divisor, from_assay

    def prepare_lots(self):
        self._sub_cache = {}
        self.pool_entries = defaultdict(list)
        self.write_offs = defaultdict(list)
        self.rc_lot_cycle = 0
        self.rc_illegal = 0
        self.rc_no_substitute = 0
        self.rc_unit_undeclared = 0
        self.reinstated_lots = 0
        self.substituted = defaultdict(int)
        self.pooled_assay = 0
        self.pooled_table = 0
        self.pooled_content = 0
        self.pooled_usable = 0
        self.pooled_lots = 0
        self.unpooled_lots = 0

        opens = {}
        targets = {}
        for code in self.live_rounds:
            for region in REGION_ORDER:
                depot = self.region_depot[region]
                instant = self.depot_open_utc(code, depot)
                opens[(code, depot)] = instant
                targets[(code, region)] = self.target_serotype(region, code, instant)

        for lot in self.lots:
            key = (lot["lot_ref"], lot["production_year"])
            depot = lot["depot"]
            region = self.depot_region.get(depot)
            unit = self.lot_units.get("%s.%s" % (depot, lot["production_year"]))
            if unit is None:
                self.rc_unit_undeclared += 1
                continue
            if region is None:
                self.unpooled_lots += 1
                continue
            content, from_assay = self.dose_content(lot, unit)
            if content is None:
                self.unpooled_lots += 1
                continue
            # Expiry and the window opening are both depot local wall clock
            # readings, so they are ordered against each other directly.
            expiry = parse_local(lot["expiry_at"])
            start_code = self.settles_in.get(lot["consign_round"])
            if start_code is None or start_code not in self.round_index:
                self.unpooled_lots += 1
                continue

            cache = {}
            entered = None
            no_substitute = False
            illegal_done = False
            for index in range(self.round_index[start_code], len(self.live_rounds)):
                code = self.live_rounds[index]
                instant = opens[(code, depot)]
                state, cycle, illegal, reinstated = self.chain_state(key, instant, cache)
                if cycle:
                    self.rc_lot_cycle += 1
                    break
                if illegal and not illegal_done:
                    self.rc_illegal += illegal
                    illegal_done = True
                if expiry <= self.open_local[code]:
                    break
                if state != "released":
                    continue
                target = targets[(code, region)]
                path = None
                if target is not None:
                    if lot["serotype"] == target:
                        path = (0, 1, ())
                    else:
                        path = self.edges_on(self.round_start[code]).get((lot["serotype"], target))
                if path is None:
                    no_substitute = True
                    continue
                hops, product, _refs = path
                usable = content if not hops else (content * product) // (100 ** hops)
                entered = (index, hops, usable, reinstated)
                break
            if no_substitute:
                self.rc_no_substitute += 1
            if entered is None:
                self.unpooled_lots += 1
                continue

            index, hops, usable, reinstated = entered
            self.pooled_lots += 1
            self.pooled_content += content
            self.pooled_usable += usable
            if from_assay:
                self.pooled_assay += 1
            else:
                self.pooled_table += 1
            if hops:
                self.substituted[hops] += 1
            if reinstated:
                self.reinstated_lots += 1

            available = set()
            write_off = None
            for later in range(index, len(self.live_rounds)):
                code = self.live_rounds[later]
                instant = opens[(code, depot)]
                if expiry <= self.open_local[code]:
                    write_off = later
                    break
                state, cycle, _il, _re = self.chain_state(key, instant, cache)
                if cycle:
                    break
                if state != "released":
                    continue
                target = targets[(code, region)]
                if target is None:
                    continue
                if lot["serotype"] != target and (
                    self.edges_on(self.round_start[code]).get((lot["serotype"], target)) is None
                ):
                    continue
                available.add(later)

            record = {
                "key": "%s@%s" % (lot["lot_ref"], lot["production_year"]),
                "lot_ref": lot["lot_ref"],
                "year": lot["production_year"],
                "expiry": expiry,
                "hops": hops,
                "usable": usable,
                "available": available,
            }
            self.pool_entries[(region, index)].append(record)
            if write_off is not None:
                self.write_offs[(region, write_off)].append(record)

        for items in self.pool_entries.values():
            items.sort(key=lambda r: (r["expiry"], r["lot_ref"], r["year"]))
        for items in self.write_offs.values():
            items.sort(key=lambda r: (r["expiry"], r["lot_ref"], r["year"]))

    # -- the ladder --------------------------------------------------------

    @staticmethod
    def level_waterline(values, in_hand):
        if not values:
            return 0
        low, high = 0, max(values)
        while low < high:
            mid = (low + high + 1) // 2
            total = 0
            for value in values:
                total += value if value < mid else mid
                if total > in_hand:
                    break
            if total <= in_hand:
                low = mid
            else:
                high = mid - 1
        return low

    def award_reason(self, awarded, claimable):
        for entry in self.reasons["award_reasons"]:
            code = entry["code"]
            if code == "CEILING_ZERO" and claimable == 0:
                return code
            if code == "AWARD_FULL" and awarded == claimable:
                return code
            if code == "LEVEL_BOUND" and 0 < awarded < claimable:
                return code
            if code == "SUPPLY_EXHAUSTED" and awarded == 0 and claimable > 0:
                return code
        return "SUPPLY_EXHAUSTED"

    def run_campaign(self, claims_by_cell, scope, block_epochs, region_blocks):
        pools = {region: [] for region in REGION_ORDER}
        remaining = {}
        ledger = {region: [] for region in REGION_ORDER}
        cells = {region: [] for region in REGION_ORDER}
        carry = {}
        awarded_total = defaultdict(int)
        deferred_total = defaultdict(int)
        cleared_log = {}
        clearing_rounds = {region: [] for region in REGION_ORDER}
        binding_tiers = defaultdict(int)
        remainder_claims = 0
        remainder_cells = 0
        extinguished_no_show = 0
        extinguished_epoch = 0

        for index, code in enumerate(self.live_rounds):
            for region in REGION_ORDER:
                written_off = 0
                for record in self.write_offs.get((region, index), ()):
                    left = remaining.get(record["key"], 0)
                    if left:
                        written_off += left
                        remaining[record["key"]] = 0
                for record in self.pool_entries.get((region, index), ()):
                    remaining[record["key"]] = record["usable"]
                    pools[region].append(record)

                live_lots = [
                    r for r in pools[region] if index in r["available"] and remaining[r["key"]] > 0
                ]
                live_lots.sort(key=lambda r: (r["expiry"], r["lot_ref"], r["year"]))
                available = sum(remaining[r["key"]] for r in live_lots)

                claims = claims_by_cell.get((region, index), [])
                claims.sort(key=lambda c: (c["tier"], c["identity"]))
                for claim in claims:
                    claim["carried_claim_doses"] = carry.get(claim["identity"], 0)
                    claim["claimable_doses"] = (
                        claim["entitlement_doses"] + claim["carried_claim_doses"]
                    )
                total_claimable = sum(c["claimable_doses"] for c in claims)

                by_tier = defaultdict(list)
                for claim in claims:
                    by_tier[claim["tier"]].append(claim)
                grants = {}
                in_hand = available
                binding = 0
                waterline = -1
                stopped = False
                for tier in sorted(by_tier):
                    members = by_tier[tier]
                    if stopped:
                        for claim in members:
                            grants[claim["identity"]] = 0
                        continue
                    need = sum(c["claimable_doses"] for c in members)
                    if need <= in_hand:
                        for claim in members:
                            grants[claim["identity"]] = claim["claimable_doses"]
                        in_hand -= need
                        continue
                    level = self.level_waterline([c["claimable_doses"] for c in members], in_hand)
                    for claim in members:
                        grants[claim["identity"]] = min(claim["claimable_doses"], level)
                    leftover = in_hand - sum(grants[c["identity"]] for c in members)
                    if leftover > 0:
                        remainder_cells += 1
                        short = sorted(
                            (c for c in members if c["claimable_doses"] > grants[c["identity"]]),
                            key=lambda c: c["identity"],
                        )
                        for claim in short[:leftover]:
                            grants[claim["identity"]] += 1
                            remainder_claims += 1
                    in_hand = 0
                    binding = tier
                    waterline = level
                    stopped = True
                binding_tiers[binding] += 1

                awarded_cell = 0
                for claim in claims:
                    award = grants.get(claim["identity"], 0)
                    claim["awarded_doses"] = award
                    claim["deferred_doses"] = claim["claimable_doses"] - award
                    awarded_cell += award
                    awarded_total[claim["identity"]] += award
                    deferred_total[claim["identity"]] += claim["deferred_doses"]
                    claim["awarded_to_date"] = awarded_total[claim["identity"]]
                    claim["deferred_to_date"] = deferred_total[claim["identity"]]
                    reason = self.award_reason(award, claim["claimable_doses"])
                    claim["reason"] = reason
                    claim["outcome"] = self.reasons["outcomes"][reason]

                cursor = 0
                for claim in claims:
                    need = claim["awarded_doses"]
                    served = ""
                    hops = 0
                    while need > 0 and cursor < len(live_lots):
                        record = live_lots[cursor]
                        left = remaining[record["key"]]
                        if left <= 0:
                            cursor += 1
                            continue
                        if not served:
                            served = record["key"]
                            hops = record["hops"]
                        take = left if left < need else need
                        remaining[record["key"]] = left - take
                        need -= take
                        if remaining[record["key"]] == 0:
                            cursor += 1
                    claim["served_lot"] = served
                    claim["substitution_hops"] = hops if served else 0

                for claim in claims:
                    forward = min(
                        claim["deferred_doses"], self.carry_cap * claim["entitlement_doses"]
                    )
                    if claim["round_no_show"] and forward > 0:
                        forward = 0
                        extinguished_no_show += 1
                    claim["carry_forward_doses"] = forward
                    carry[claim["identity"]] = forward

                is_clearing = available > total_claimable
                if is_clearing:
                    clearing_rounds[region].append(code)
                claimed = {c["identity"]: c for c in claims}
                cleared_balances = 0
                if is_clearing and scope != "none":
                    in_scope = set()
                    if scope == "region_wide":
                        for block_ref in region_blocks[region]:
                            identity = "%s#%d" % (block_ref, block_epochs[(block_ref, index)])
                            in_scope.add(identity)
                        in_scope.update(claimed)
                    elif scope == "fully_awarded_only":
                        in_scope = {i for i, c in claimed.items() if c["outcome"] == "full"}
                    else:
                        in_scope = {i for i, c in claimed.items() if c["tier"] == 1}
                    for identity in in_scope:
                        if carry.get(identity, 0) > 0:
                            carry[identity] = 0
                            cleared_balances += 1
                            if identity in claimed:
                                claimed[identity]["carry_forward_doses"] = 0
                    for identity in in_scope:
                        cleared_log[(identity, code)] = True
                    for identity in claimed:
                        cleared_log.setdefault((identity, code), False)
                else:
                    for identity in claimed:
                        cleared_log[(identity, code)] = False
                    if scope == "region_wide":
                        for block_ref in region_blocks[region]:
                            identity = "%s#%d" % (block_ref, block_epochs[(block_ref, index)])
                            cleared_log.setdefault((identity, code), False)

                if index + 1 < len(self.live_rounds):
                    for block_ref in region_blocks[region]:
                        old = block_epochs[(block_ref, index)]
                        new = block_epochs[(block_ref, index + 1)]
                        if old == new:
                            continue
                        identity = "%s#%d" % (block_ref, old)
                        if carry.get(identity, 0) > 0:
                            carry[identity] = 0
                            extinguished_epoch += 1

                ledger[region].extend(claims)
                cells[region].append(
                    {
                        "round": code,
                        "available_doses": available,
                        "claimable_doses": total_claimable,
                        "awarded_doses": awarded_cell,
                        "waterline": waterline,
                        "binding_tier": binding,
                        "surplus_doses": available - awarded_cell,
                        "cleared_balances": cleared_balances,
                        "written_off_doses": written_off,
                    }
                )

        return {
            "ledger": ledger,
            "cells": cells,
            "cleared_log": cleared_log,
            "clearing_rounds": clearing_rounds,
            "binding_tiers": binding_tiers,
            "remainder_claims": remainder_claims,
            "remainder_cells": remainder_cells,
            "extinguished_no_show": extinguished_no_show,
            "extinguished_epoch": extinguished_epoch,
        }


# ---------------------------------------------------------------- driver


def pick_factor(s, region, version, settle):
    key = (region, version["species"], version["age_class"])
    when = s.round_start[settle]
    chosen = None
    for row in s.dose_factors.get(key, ()):
        if parse_date(row["effective_from"]) <= when:
            candidate = (row["effective_from"], row["issued_at"], row["factor_ref"])
            if chosen is None or candidate > (
                chosen["effective_from"],
                chosen["issued_at"],
                chosen["factor_ref"],
            ):
                chosen = row
    if chosen is None:
        return None
    return scaled_int(chosen["doses_per_100_head"], 2)


def pick_tier(s, block_ref, settle):
    when = s.round_start[settle]
    chosen = None
    for row in s.priority.get(block_ref, ()):
        if parse_date(row["effective_from"]) <= when:
            candidate = (row["effective_from"], row["issued_at"], row["entry_ref"])
            if chosen is None or candidate > (
                chosen["effective_from"],
                chosen["issued_at"],
                chosen["entry_ref"],
            ):
                chosen = row
    return int(chosen["tier"]) if chosen else s.tier_count


def build_claims(s):
    admitted = s.admit()
    survivors = s.collapse(admitted)
    s.governing_source = s.decide_governing_source(survivors)

    s.amend_stats = {"applied": 0, "stale": 0, "unauthorised": 0}
    s.ceiling_clamped = 0
    s.exact_half = 0
    s.attribute_overrides = 0
    s.head_source_counts = defaultdict(int)
    s.registry_blocks = set()
    s.from_skipped = 0

    claims_by_cell = defaultdict(list)
    for item in survivors:
        version = item["version"]
        row = item["row"]
        if row["species"] != version["species"] or row["age_class"] != version["age_class"]:
            s.attribute_overrides += 1

        governing = s.governing_for(item, s.governing_source)
        source, head, moment = s.head_count(item, governing)
        if source is None:
            s.rejects["RC_NO_HEADCOUNT"] += 1
            continue

        settle = item["settle"]
        head = s.apply_amendments(
            s.notices_for(item["block_ref"], settle, "head_count"),
            head,
            item["region"],
            moment,
            item["close_utc"],
            s.amend_stats,
        )

        factor = pick_factor(s, item["region"], version, settle)
        if factor is None:
            entitlement = 0
        else:
            num = head * factor
            if num % 10000 == 5000:
                s.exact_half += 1
            entitlement = half_away_from_zero(num, 10000)

        ceiling_row = s.ceilings.get((item["block_ref"], settle))
        ceiling = int(ceiling_row["handling_ceiling"]) if ceiling_row else None
        notices = s.notices_for(item["block_ref"], settle, "handling_ceiling")
        if notices:
            moment_c = parse_utc(ceiling_row["issued_at"]) if ceiling_row else None
            adjusted = s.apply_amendments(
                notices,
                ceiling if ceiling is not None else 0,
                item["region"],
                moment_c,
                item["close_utc"],
                s.amend_stats,
            )
            if ceiling is not None:
                ceiling = adjusted
        if ceiling is not None and entitlement > ceiling:
            entitlement = ceiling
            s.ceiling_clamped += 1

        s.head_source_counts[source] += 1
        if source == "registry":
            s.registry_blocks.add(item["block_ref"])
        if item["named"] != settle:
            s.from_skipped += 1

        no_show = any(
            rc in s.no_show.get(item["block_ref"], ()) for rc in [settle] + s.feeds[settle]
        )
        claims_by_cell[(item["region"], s.round_index[settle])].append(
            {
                "identity": item["identity"],
                "block_ref": item["block_ref"],
                "epoch": item["epoch"],
                "round": settle,
                "region": item["region"],
                "segment": item["segment"],
                "tier": pick_tier(s, item["block_ref"], settle),
                "entitlement_doses": entitlement,
                "round_no_show": no_show,
                "head_source": source,
            }
        )
    return claims_by_cell


def clone_claims(claims_by_cell):
    return {key: [dict(c) for c in items] for key, items in claims_by_cell.items()}


def block_epoch_table(s):
    table = {}
    region_blocks = {region: [] for region in REGION_ORDER}
    for block_ref in sorted(s.master):
        version = s.master_version(block_ref, s.round_start[s.live_rounds[0]])
        region = version["region"] if version else None
        if region in region_blocks:
            region_blocks[region].append(block_ref)
        depot = s.region_depot.get(region)
        for index, code in enumerate(s.live_rounds):
            instant = s.depot_open_utc(code, depot) if depot else None
            table[(block_ref, index)] = (
                s.epoch_at(block_ref, instant) if instant is not None else 1
            )
    return table, region_blocks


def decide_scope(s, claims_by_cell, block_epochs, region_blocks):
    observations = []
    for entry in s.clearance_log:
        block = entry.get("block")
        rnd = entry.get("round")
        token = entry.get("balance_cleared")
        if block and rnd and token is not None:
            observations.append((block, rnd, token == "yes"))
    best = None
    for scope in SCOPES:
        result = s.run_campaign(clone_claims(claims_by_cell), scope, block_epochs, region_blocks)
        score = 0
        for block, rnd, cleared in observations:
            predicted = result["cleared_log"].get((block, rnd))
            if predicted is not None and predicted == cleared:
                score += 1
        if best is None or score > best[0]:
            best = (score, scope, result)
    return best[1], best[2]


def dump(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def write_documents(s, result, out_dir, scope):
    live = s.live_rounds
    ledger_rows = {}
    for region in REGION_ORDER:
        rows = sorted(
            result["ledger"][region],
            key=lambda c: (s.round_index[c["round"]], c["tier"], c["identity"]),
        )
        ledger_rows[region] = rows
        dump(
            os.path.join(out_dir, "region_%s.json" % region),
            {
                "region": region,
                "rounds": list(live),
                "ledger": [
                    {
                        "block": c["identity"],
                        "round": c["round"],
                        "tier": c["tier"],
                        "entitlement_doses": c["entitlement_doses"],
                        "carried_claim_doses": c["carried_claim_doses"],
                        "claimable_doses": c["claimable_doses"],
                        "awarded_doses": c["awarded_doses"],
                        "deferred_doses": c["deferred_doses"],
                        "awarded_to_date": c["awarded_to_date"],
                        "deferred_to_date": c["deferred_to_date"],
                        "carry_forward_doses": c["carry_forward_doses"],
                        "served_lot": c["served_lot"],
                        "substitution_hops": c["substitution_hops"],
                        "outcome": c["outcome"],
                        "reason": c["reason"],
                    }
                    for c in rows
                ],
                "cells": result["cells"][region],
            },
        )

    all_claims = [c for region in REGION_ORDER for c in ledger_rows[region]]

    for segment in SEGMENT_ORDER:
        members = [c for c in all_claims if c["segment"] == segment]
        regions = []
        for region in REGION_ORDER:
            subset = [c for c in members if c["region"] == region]
            regions.append(
                {
                    "region": region,
                    "claims": len(subset),
                    "awarded_doses": sum(c["awarded_doses"] for c in subset),
                    "claimable_doses": sum(c["claimable_doses"] for c in subset),
                    "deferred_doses": sum(c["deferred_doses"] for c in subset),
                    "carry_forward_doses": sum(c["carry_forward_doses"] for c in subset),
                    "full": sum(1 for c in subset if c["outcome"] == "full"),
                    "partial": sum(1 for c in subset if c["outcome"] == "partial"),
                    "zero": sum(1 for c in subset if c["outcome"] == "zero"),
                    "declined": sum(1 for c in subset if c["outcome"] == "declined"),
                }
            )
        rounds = []
        for code in live:
            subset = [c for c in members if c["round"] == code]
            rounds.append(
                {
                    "round": code,
                    "claims": len(subset),
                    "awarded_doses": sum(c["awarded_doses"] for c in subset),
                    "deferred_doses": sum(c["deferred_doses"] for c in subset),
                }
            )
        dump(
            os.path.join(out_dir, "segment_%s.json" % segment),
            {"segment": segment, "regions": regions, "rounds": rounds},
        )

    cells = [cell for region in REGION_ORDER for cell in result["cells"][region]]
    dump(
        os.path.join(out_dir, "summary.json"),
        {
            "live_rounds": len(live),
            "skipped_rounds": len(s.skipped),
            "claims_settled": len(all_claims),
            "claims_rejected": sum(s.rejects.values()),
            "blocks_settled": len({c["block_ref"] for c in all_claims}),
            "claimable_doses": sum(c["claimable_doses"] for c in all_claims),
            "awarded_doses": sum(c["awarded_doses"] for c in all_claims),
            "deferred_doses": sum(c["deferred_doses"] for c in all_claims),
            "carry_forward_doses": sum(c["carry_forward_doses"] for c in all_claims),
            "available_doses": sum(c["available_doses"] for c in cells),
            "surplus_doses": sum(c["surplus_doses"] for c in cells),
            "written_off_doses": sum(c["written_off_doses"] for c in cells),
            "regions": [
                {
                    "region": region,
                    "claims": len(ledger_rows[region]),
                    "awarded_doses": sum(c["awarded_doses"] for c in ledger_rows[region]),
                    "deferred_doses": sum(c["deferred_doses"] for c in ledger_rows[region]),
                }
                for region in REGION_ORDER
            ],
            "segments": [
                {
                    "segment": segment,
                    "claims": sum(1 for c in all_claims if c["segment"] == segment),
                    "awarded_doses": sum(
                        c["awarded_doses"] for c in all_claims if c["segment"] == segment
                    ),
                }
                for segment in SEGMENT_ORDER
            ],
        },
    )

    dump(
        os.path.join(out_dir, "policy_audit.json"),
        {
            "governing_source": s.governing_source,
            "balance_clearance_scope": scope,
            "alias_hops": {str(n): s.alias_hops.get(n, 0) for n in (1, 2, 3)},
            "epoch_identities": len({c["identity"] for c in all_claims if c["epoch"] > 1}),
            "collapsed_duplicates": s.collapsed_duplicates,
            "stale_revisions": s.stale_revisions,
            "attribute_overrides": s.attribute_overrides,
            "amendments_applied": s.amend_stats["applied"],
            "amendments_stale": s.amend_stats["stale"],
            "amendments_unauthorised": s.amend_stats["unauthorised"],
            "ceiling_clamped": s.ceiling_clamped,
            "exact_half_entitlements": s.exact_half,
            "substituted_lots": {str(n): s.substituted.get(n, 0) for n in (1, 2)},
            "lots_unresolved_cycle": s.rc_lot_cycle,
            "lots_without_substitute": s.rc_no_substitute,
            "illegal_transitions": s.rc_illegal,
            "reinstated_lots": s.reinstated_lots,
            "unit_undeclared_lots": s.rc_unit_undeclared,
            "extinguished_no_show": result["extinguished_no_show"],
            "extinguished_epoch": result["extinguished_epoch"],
            "binding_tiers": {str(n): result["binding_tiers"].get(n, 0) for n in range(5)},
            "clearing_rounds": [
                {"region": region, "rounds": result["clearing_rounds"][region]}
                for region in REGION_ORDER
            ],
        },
    )

    counted = {
        "RC_DUPLICATE_COLLAPSED": s.collapsed_duplicates,
        "RC_STALE_REVISION": s.stale_revisions,
        "RC_AMENDMENT_STALE": s.amend_stats["stale"],
        "RC_AMENDMENT_UNAUTHORISED": s.amend_stats["unauthorised"],
        "RC_LOT_CYCLE": s.rc_lot_cycle,
        "RC_ILLEGAL_TRANSITION": s.rc_illegal,
        "RC_NO_SUBSTITUTE": s.rc_no_substitute,
        "RC_UNIT_UNDECLARED": s.rc_unit_undeclared,
        "RC_HEADER_GAP": s.corpus.header_gaps,
    }
    named = {
        "field_intake": "field_intake",
        "dispatch_stream": "dispatch_stream",
        "registry": "registry",
        "visit_events": "visit_events",
        "amendment_notices": "amendments",
        "lot_register": "lot_register",
        "release_certificates": "release_certificates",
        "assay": "assay",
    }
    source_rows = {}
    for key, logical in named.items():
        source_rows[key] = sum(s.corpus.row_counts.get(n, 0) for n in s.manifest.get(logical, []))
    other = set(named.values()) | {"contract", "legacy", "observations"}
    source_rows["reference"] = sum(
        s.corpus.row_counts.get(n, 0)
        for logical, files in s.manifest.items()
        if logical not in other
        for n in files
    )
    dump(
        os.path.join(out_dir, "data_quality.json"),
        {
            "rejects": {code: s.rejects.get(code, 0) for code in s.reasons["reject_codes"]},
            "counted": {code: counted.get(code, 0) for code in s.reasons["counted_codes"]},
            "source_rows": source_rows,
        },
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Campaign dose ration settlement")
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    try:
        s = Settlement(args.data)
        claims_by_cell = build_claims(s)
        s.prepare_lots()
        block_epochs, region_blocks = block_epoch_table(s)
        scope, result = decide_scope(s, claims_by_cell, block_epochs, region_blocks)
    except Incomplete as exc:
        sys.stderr.write("incomplete export: %s\n" % exc)
        return 1

    os.makedirs(args.out, exist_ok=True)
    write_documents(s, result, args.out, scope)
    return 0


if __name__ == "__main__":
    sys.exit(main())
