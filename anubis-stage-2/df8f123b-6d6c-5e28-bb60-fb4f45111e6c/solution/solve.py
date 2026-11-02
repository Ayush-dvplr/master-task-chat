#!/usr/bin/env python3
"""Close the pledge docket for the settlement window and file every artifact."""

import configparser
import csv
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

DATA = "/app/data"
SERVICE = "/app/service"
OUT = "/app/out"
UTC = timezone.utc


# ---------------------------------------------------------------- readers


def read_text(name):
    with open(os.path.join(DATA, name), "r", encoding="utf-8") as fh:
        return fh.read()


def read_rows(name, delim=","):
    with open(os.path.join(DATA, name), "r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=delim))


def read_jsonl(name):
    out = []
    with open(os.path.join(DATA, name), "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def read_log(name):
    with open(os.path.join(DATA, name), "r", encoding="utf-8") as fh:
        return [line.rstrip("\n") for line in fh if line.strip()]


def read_ini(name):
    parser = configparser.ConfigParser()
    parser.read_string(read_text(name))
    return {s: dict(parser.items(s)) for s in parser.sections()}


def md_table(text, first_header):
    """Return the rows of the pipe table whose first header cell matches."""
    rows = []
    header = None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            if header is not None and rows:
                break
            header = None
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if set("".join(cells)) <= set("- "):
            continue
        if header is None:
            if cells[0] == first_header:
                header = cells
            continue
        rows.append(dict(zip(header, cells)))
    if header is None:
        raise SystemExit("no table headed %r" % first_header)
    return rows


def moment(text):
    return datetime.fromisoformat(text)


def iso(value):
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def day(text):
    return date.fromisoformat(text)


def half_up(value):
    whole = int(value)
    if value - whole >= 0.5:
        whole += 1
    return whole


def _invert(text):
    return [-ord(ch) for ch in text]


# ------------------------------------------------------------- spec layer


class Specs:
    """Every rule parameter the desk documents, read from the corpus."""

    def __init__(self):
        self.index = [r["file"] for r in md_table(read_text("corpus_index.md"), "file")]
        for name in self.index:
            if not os.path.exists(os.path.join(DATA, name)):
                raise SystemExit("corpus file missing: %s" % name)

        charter = read_text("settlement_charter.md")
        self.charter = {r["setting"]: r["value"] for r in md_table(charter, "setting")}
        self.window_id = self.charter["window_id"]
        self.cutoff = moment(self.charter["settlement_cutoff"])
        self.boundary_hours = int(self.charter["boundary_notice_hours"])
        self.boundary = timedelta(hours=self.boundary_hours)
        self.home_zone = self.charter["home_zone"]
        self.directive_file = self.charter["directive_source"]

        temporal = read_text("temporal_rules.md")
        self.due_forms = {
            r["expression"]: r["local time of day"]
            for r in md_table(temporal, "expression")
        }
        layers = sorted(
            (int(r["layer"]), r["source"]) for r in md_table(temporal, "layer")
        )
        self.layer_order = [name for _, name in layers]
        if self.layer_order[:3] != [
            "counterparty_closure_overrides.csv",
            "business_day_exceptions.csv",
            "zone_holiday_calendar.csv",
        ]:
            raise SystemExit("unexpected business day layering")

        prov = read_text("provenance_precedence.md")
        self.source_order = {
            r["field class"]: [s.strip() for s in r["source order"].split(",")]
            for r in md_table(prov, "field class")
        }
        for need in ("due_instant", "discharge_evidence", "waiver"):
            if need not in self.source_order:
                raise SystemExit("source order missing for %s" % need)

        self.suffixes = [
            r["legal suffix"]
            for r in md_table(read_text("entity_resolution.md"), "legal suffix")
        ]
        self.reasons = [r["code"] for r in md_table(read_text("reason_codes.md"), "code")]
        self.sources = {
            r["file"]: r["source"]
            for r in md_table(read_text("source_manifest.md"), "file")
        }
        self.mode_layers = {
            int(r["layer"]): r["source"]
            for r in md_table(read_text("mode_selection.md"), "layer")
        }
        self.endpoints = {
            r["endpoint"]: r["verb"]
            for r in md_table(read_text("service_protocol.md"), "endpoint")
        }
        self.contract = self._contract()

        desk = read_ini("desk_policy.ini")
        self.default_mode = desk["desk"]["default_mode"]
        self.host = desk["interface"]["host"]
        self.port = int(desk["interface"]["port"])
        self.channel_header = desk["interface"]["channel_header"]
        if desk["window"]["window_id"] != self.window_id:
            raise SystemExit("window identifier disagreement")
        if int(desk["window"]["boundary_notice_hours"]) != self.boundary_hours:
            raise SystemExit("boundary band disagreement")

        channel = read_ini("channel_policy.ini")
        self.cli_events = [
            e.strip() for e in channel["routing"]["cli_events"].split(",") if e.strip()
        ]
        self.cli_value = channel["channel"]["cli_value"]
        self.api_value = channel["channel"]["api_value"]

        units = read_ini("unit_declarations.ini")
        pair = units["same_name_different_unit"]
        if (
            pair["travel_itinerary.offset_minutes"]
            == pair["zone_offset_table.offset_minutes"]
        ):
            raise SystemExit("offset column units agree unexpectedly")

        if "returns to the desk" not in read_text("grace_allocation.md"):
            raise SystemExit("grace withholding rule missing")
        if "readiness_examples.csv" not in read_text("dependency_rules.md"):
            raise SystemExit("dependency evidence pointer missing")

    def _contract(self):
        """Artifact key lists, taken from the filed contract."""
        text = read_text("output_contract.md")
        out = {}
        for block in re.split(r"\n## ", text)[1:]:
            title, _, body = block.partition("\n")
            name = title.strip().rsplit("/", 1)[-1].replace(".json", "")
            groups = re.findall(
                r"exactly these keys[^:]*:\s*([^.]+)\.", body, re.IGNORECASE
            )
            keys = [
                [
                    token.strip().split(" ")[0]
                    for token in group.replace("\n", " ").split(",")
                    if token.strip()
                ]
                for group in groups
            ]
            if name == "report":
                out["report"] = [r["key"] for r in md_table(body, "key")]
                out["report_pledge"] = keys[0]
                out["report_counts"] = keys[1]
            elif keys:
                out[name] = keys[0]
        for need in (
            "report",
            "report_pledge",
            "report_counts",
            "final_state",
            "transcript_summary",
            "scenario_alpha",
            "scenario_beta",
            "scenario_mode",
            "summary",
        ):
            if need not in out:
                raise SystemExit("contract block missing: %s" % need)
        return out


# ------------------------------------------------- withheld rule learning


def learn_tiebreak():
    """Pick the one ordering that reproduces every filed precedence ruling."""
    groups = {}
    for row in read_rows("precedence_worked_cases.csv"):
        groups.setdefault(row["case_id"], []).append(row)
    alive = {
        "early_log_high_key": lambda c: (c["logged_at"], _invert(c["candidate_record_key"])),
        "early_log_low_key": lambda c: (c["logged_at"], c["candidate_record_key"]),
        "late_log_high_key": lambda c: (_invert(c["logged_at"]), _invert(c["candidate_record_key"])),
        "late_log_low_key": lambda c: (_invert(c["logged_at"]), c["candidate_record_key"]),
    }
    for rows in groups.values():
        picked = [r["candidate_record_key"] for r in rows if r["selected"] == "yes"]
        if len(picked) != 1:
            raise SystemExit("precedence ruling is not unique")
        for label in list(alive):
            if sorted(rows, key=alive[label])[0]["candidate_record_key"] != picked[0]:
                del alive[label]
    if len(alive) != 1:
        raise SystemExit("precedence ordering did not resolve: %s" % sorted(alive))
    return next(iter(alive))


def learn_duplicate_rule():
    """Confirm which of two identical records the desk keeps."""
    high = low = 0
    for row in read_rows("duplicate_record_audit.csv"):
        pair = sorted([row["record_key_a"], row["record_key_b"]])
        if row["retained_record_key"] == pair[-1]:
            high += 1
        elif row["retained_record_key"] == pair[0]:
            low += 1
    if high == 0 or low != 0:
        raise SystemExit("duplicate retention rule unclear")
    return "greatest_key"


def learn_lateness_rule():
    """Confirm how a part minute is handled."""
    alive = {"floor": True, "round": True, "ceil": True}
    for row in read_rows("lateness_rounding_cases.csv"):
        gap = (
            moment(row["effective_instant"]) - moment(row["due_instant"])
        ).total_seconds()
        want = int(row["lateness_minutes"])
        if gap <= 0:
            if want != 0:
                raise SystemExit("early case carries lateness")
            continue
        if alive["floor"] and int(gap // 60) != want:
            alive["floor"] = False
        if alive["round"] and half_up(gap / 60.0) != want:
            alive["round"] = False
        if alive["ceil"] and -int(-gap // 60) != want:
            alive["ceil"] = False
    live = [k for k, v in alive.items() if v]
    if live != ["floor"]:
        raise SystemExit("lateness handling did not resolve: %s" % live)
    return "floor"


def learn_readiness():
    """Learn how prerequisite contributions combine with own evidence."""
    blocked_on_unsettled = True
    uses_own = True
    uses_prereqs = True
    pushed = set()
    lapsed = set()
    unsettled = set()
    for row in read_rows("readiness_examples.csv"):
        parts = [p for p in row["prereq_contributions"].split(";") if p]
        instants = [moment(p) for p in parts if p not in ("unsettled", "lapsed")]
        own = moment(row["own_evidence_instant"]) if row["own_evidence_instant"] else None
        codes = set(c for c in row["reason_codes"].split(";") if c)
        if "unsettled" in parts:
            if row["outcome_state"] != "blocked" or row["effective_instant"]:
                blocked_on_unsettled = False
            unsettled |= codes
            continue
        if row["outcome_state"] != "settled":
            raise SystemExit("unexpected readiness outcome")
        got = moment(row["effective_instant"])
        pool = ([own] if own else []) + instants
        if got != max(pool):
            uses_own = False
        if instants and own and max(instants) > own:
            if got != max(instants):
                uses_prereqs = False
            pushed |= codes
        if "lapsed" in parts:
            lapsed |= codes
    if not (blocked_on_unsettled and uses_own and uses_prereqs):
        raise SystemExit("readiness reading did not resolve")
    if "prereq_unsettled" not in unsettled:
        raise SystemExit("blocked reason code not evidenced")
    if "prereq_pushed" not in pushed:
        raise SystemExit("pushed reason code not evidenced")
    if "prereq_lapsed" not in lapsed:
        raise SystemExit("lapsed reason code not evidenced")
    return {
        "combine": "max_own_and_contributions",
        "unsettled": "blocked",
        "pushed": "prereq_pushed",
        "lapsed": "prereq_lapsed",
        "blocked": "prereq_unsettled",
    }


def share_round(pool, items, redistribute):
    """items are reference, lateness and ceiling triples."""
    total = sum(i[2] for i in items)
    if total <= 0:
        return {i[0]: 0 for i in items}
    raw = {}
    for ref, lateness, ceiling in items:
        raw[ref] = min(pool * ceiling / float(total), float(min(lateness, ceiling)))
    if redistribute:
        for _ in range(6):
            spare = pool - sum(raw.values())
            if spare <= 1e-9:
                break
            room = {}
            for ref, lateness, ceiling in items:
                space = float(min(lateness, ceiling)) - raw[ref]
                if space > 1e-9:
                    room[ref] = space
            open_total = sum(room.values())
            if open_total <= 1e-9:
                break
            for ref, space in room.items():
                raw[ref] += min(space, spare * space / open_total)
    target = int(sum(raw.values()))
    floors = {ref: int(value) for ref, value in raw.items()}
    left = target - sum(floors.values())
    order = sorted(raw, key=lambda ref: (-(raw[ref] - floors[ref]), ref))
    for ref in order[: max(0, left)]:
        floors[ref] += 1
    return floors


def learn_grace_rule():
    """Replay the filed grace rounds and keep the method that reproduces them."""
    rounds = {}
    for row in read_rows("grace_precedent_rounds.csv"):
        rounds.setdefault(row["round_id"], []).append(row)
    alive = {"withhold": True, "redistribute": True}
    for rows in rounds.values():
        pool = int(rows[0]["pool_minutes"])
        items = [
            (r["pledge_ref"], int(r["lateness_minutes"]), int(r["ceiling_minutes"]))
            for r in rows
        ]
        want = {r["pledge_ref"]: int(r["granted_minutes"]) for r in rows}
        for label, flag in (("withhold", False), ("redistribute", True)):
            if alive[label] and share_round(pool, items, flag) != want:
                alive[label] = False
    live = [k for k, v in alive.items() if v]
    if live != ["withhold"]:
        raise SystemExit("grace method did not resolve: %s" % live)
    return False


def learn_exclusions():
    """Read the exclusion sets out of the filed window tallies."""
    states = {}
    classes = {}
    for row in read_rows("audit_tally_history.csv"):
        count = int(row["pledge_count"])
        if count == 0:
            continue
        if int(row["counts_in_audit_total"]) != count:
            raise SystemExit("audit total excludes a filed pledge")
        inside = int(row["counts_in_breach_rate"]) == count
        states.setdefault(row["final_state"], set()).add(inside)
        classes.setdefault(row["pledge_class"], set()).add(inside)
    out_states = set(s for s, v in states.items() if v == {False})
    out_classes = set(c for c, v in classes.items() if v == {False})
    if not out_states or not out_classes:
        raise SystemExit("exclusion sets not evidenced")
    return out_states, out_classes


def learn_cycle_rule():
    rows = read_rows("cycle_findings.csv")
    states = {r["resolution_state"] for r in rows}
    codes = {r["reason_code"] for r in rows}
    if len(states) != 1 or len(codes) != 1:
        raise SystemExit("cycle resolution not uniform")
    return states.pop(), codes.pop()


def learn_period_forms():
    monthly = quarterly = False
    for row in read_jsonl("series_expansion_log.jsonl"):
        label = row["period"]
        if row["instance_id"] != "%s#%s" % (row["series_id"], label):
            raise SystemExit("instance identifier form disagreement")
        if re.fullmatch(r"\d{4}-Q[1-4]", label):
            quarterly = True
        elif re.fullmatch(r"\d{4}-\d{2}", label):
            monthly = True
        else:
            raise SystemExit("unknown period label %s" % label)
    if not (monthly and quarterly):
        raise SystemExit("period label forms not evidenced")
    return True


def learn_boundary_reason():
    seen = set()
    for row in read_jsonl("rejected_call_samples.jsonl"):
        if row["endpoint"] == "/register":
            seen.add(row["reason"])
    if "out_of_window" not in seen:
        raise SystemExit("boundary refusal reason not evidenced")
    return "out_of_window"


def learn_cli_event():
    events = set()
    for line in read_log("desk_transition_log.log"):
        if "channel=cli" not in line:
            continue
        found = re.search(r"event=(\w+)", line)
        if found:
            events.add(found.group(1))
    if len(events) != 1:
        raise SystemExit("client routing not uniform: %s" % sorted(events))
    return events.pop()


def learn_probe_fields():
    shapes = {}
    for line in read_log("service_probe_log.log"):
        found = dict(re.findall(r"(\S+?)=(\S+)", line))
        if "endpoint" not in found:
            continue
        shapes[found["endpoint"]] = [
            f for f in found.get("request_fields", "").split(",") if f and f != "none"
        ]
    for need in ("/window", "/register", "/transition", "/grace"):
        if need not in shapes:
            raise SystemExit("probe log lacks %s" % need)
    return shapes


# ------------------------------------------------------------- entity work


class Holders:
    def __init__(self, spec):
        self.spec = spec
        self.rows = {}
        self.by_name = {}
        for row in read_rows("counterparty_directory.csv"):
            self.rows[row["counterparty_key"]] = row
            self.by_name.setdefault(self.flatten(row["legal_name"]), set()).add(
                row["counterparty_key"]
            )
        self.alias = {}
        self.suffix_only = set()
        for row in read_rows("counterparty_alias_map.csv"):
            flat = self.flatten(row["alias_form"])
            self.alias.setdefault(flat, set()).add(row["counterparty_key"])
            if self.plain(row["alias_form"]) != flat:
                self.suffix_only.add(row["alias_form"])
        self.legacy = {
            row["legacy_code"]: row["counterparty_key"]
            for row in read_rows("legacy_code_crosswalk.tsv", "\t")
        }
        self.handle = {
            row["thread_handle"]: row["counterparty_key"]
            for row in read_rows("inbox_handle_registry.csv")
        }
        self.suffix_hits = set()

    def plain(self, raw):
        text = raw.casefold().replace("&", " and ")
        text = re.sub(r"[^a-z0-9]+", " ", text).strip()
        return re.sub(r"\s+", " ", text)

    def flatten(self, raw):
        text = self.plain(raw)
        changed = True
        while changed:
            changed = False
            for suffix in self.spec.suffixes:
                if text.endswith(" " + suffix):
                    text = text[: -(len(suffix) + 1)].strip()
                    changed = True
        return text

    def resolve(self, raw):
        raw = (raw or "").strip()
        if not raw:
            return None
        if re.fullmatch(r"CP-\d{4}", raw):
            return raw if raw in self.rows else None
        if raw in self.legacy:
            return self.legacy[raw]
        if raw in self.handle:
            return self.handle[raw]
        flat = self.flatten(raw)
        if flat in self.alias and len(self.alias[flat]) == 1:
            found = next(iter(self.alias[flat]))
            if self.plain(raw) != flat:
                self.suffix_hits.add(found)
            return found
        if flat in self.by_name and len(self.by_name[flat]) == 1:
            found = next(iter(self.by_name[flat]))
            if self.plain(raw) != flat:
                self.suffix_hits.add(found)
            return found
        return None

    def zone(self, key):
        return self.rows[key]["business_zone"]

    def status(self, key):
        return self.rows[key]["status"]

    def dissolved(self, key):
        text = self.rows[key]["dissolved_on"]
        return day(text) if text else None


def pledge_ref(raw):
    """Read a raw pledge reference into a canonical identifier."""
    raw = (raw or "").strip()
    if "#" in raw:
        return raw
    flat = re.sub(r"[^A-Za-z0-9]+", " ", raw).strip()
    digits = re.sub(r"\D", "", flat)
    if not digits:
        return None
    return "PL-%05d" % int(digits)


# ----------------------------------------------------------- calendar work


class Clock:
    def __init__(self, holders):
        self.offsets = {}
        for row in read_rows("zone_offset_table.csv"):
            self.offsets.setdefault(row["zone"], []).append(
                (
                    day(row["effective_local_from"]),
                    day(row["effective_local_to"]),
                    int(row["offset_minutes"]),
                )
            )
        for rows in self.offsets.values():
            rows.sort()
        self.holiday = set()
        for row in read_rows("zone_holiday_calendar.csv"):
            if row["observed"] == "yes":
                self.holiday.add((row["zone"], row["local_date"]))
        self.exception = set()
        for row in read_rows("business_day_exceptions.csv"):
            if row["effect"] == "open":
                self.exception.add((row["zone"], row["local_date"]))
        self.closure = {}
        for row in read_rows("counterparty_closure_overrides.csv"):
            key = holders.resolve(row["counterparty_ref"])
            if key is None:
                raise SystemExit(
                    "holder did not resolve for closure override %s" % row["override_id"]
                )
            self.closure[(key, row["local_date"])] = row["effect"]
        self.shift_dates = {}
        for zone, rows in self.offsets.items():
            self.shift_dates[zone] = [r[0] for r in rows[1:]]

    def offset(self, zone, local_day):
        for low, high, value in self.offsets[zone]:
            if low <= local_day < high:
                return value
        raise SystemExit("no offset for %s %s" % (zone, local_day))

    def to_utc(self, zone, naive):
        return (naive - timedelta(minutes=self.offset(zone, naive.date()))).replace(
            tzinfo=UTC
        )

    def to_local(self, zone, value):
        rows = self.offsets[zone]
        chosen = rows[0][2]
        for low, high, minutes in rows:
            opens = datetime(low.year, low.month, low.day, tzinfo=UTC) - timedelta(
                minutes=minutes
            )
            if opens <= value:
                chosen = minutes
            else:
                break
        return (value + timedelta(minutes=chosen)).replace(tzinfo=None)

    def business(self, zone, key, local_day):
        stamp = local_day.isoformat()
        effect = self.closure.get((key, stamp))
        if effect == "closed":
            return False
        if effect == "open":
            return True
        if (zone, stamp) in self.exception:
            return True
        if (zone, stamp) in self.holiday:
            return False
        return local_day.weekday() < 5

    def add_business(self, zone, key, start, count):
        cursor = start
        left = count
        while left > 0:
            cursor += timedelta(days=1)
            if self.business(zone, key, cursor):
                left -= 1
        return cursor

    def last_business(self, zone, key, local_day):
        if local_day.month == 12:
            edge = date(local_day.year + 1, 1, 1)
        else:
            edge = date(local_day.year, local_day.month + 1, 1)
        cursor = edge - timedelta(days=1)
        while not self.business(zone, key, cursor):
            cursor -= timedelta(days=1)
        return cursor

    def nth_business_next(self, zone, key, local_day, index):
        if local_day.month == 12:
            cursor = date(local_day.year + 1, 1, 1)
        else:
            cursor = date(local_day.year, local_day.month + 1, 1)
        seen = 0
        while True:
            if self.business(zone, key, cursor):
                seen += 1
                if seen == index:
                    return cursor
            cursor += timedelta(days=1)

    def resolve_due(self, zone, key, origin, expression):
        local = self.to_local(zone, origin)
        start = local.date()
        if expression.startswith("FIXED:"):
            return self.to_utc(zone, datetime.fromisoformat(expression[6:]))
        if expression.startswith("D+"):
            target = start + timedelta(days=int(expression[2:]))
            clock = (17, 0)
        elif expression.startswith("BD+"):
            target = self.add_business(zone, key, start, int(expression[3:]))
            clock = (17, 0)
        elif expression == "EOM":
            target = self.last_business(zone, key, start)
            clock = (17, 0)
        elif expression.startswith("NBD"):
            target = self.nth_business_next(zone, key, start, int(expression[3:]))
            clock = (12, 0)
        else:
            raise SystemExit("unknown due expression %s" % expression)
        return self.to_utc(
            zone, datetime(target.year, target.month, target.day, clock[0], clock[1])
        )

    def shifted_inside(self, zone, low, high):
        return [s for s in self.shift_dates.get(zone, []) if low.date() <= s < high.date()]


# ------------------------------------------------------------- corpus load


class Corpus:
    def __init__(self, spec, holders, clock, rules):
        self.spec = spec
        self.holders = holders
        self.clock = clock
        self.rules = rules
        self.cutoff = spec.cutoff
        self.dead = self._dead()
        self.directive = self._directive()
        self.window_open = moment(self.directive["window_open"])
        self.window_close = moment(self.directive["window_close"])
        self.pool = int(self.directive["grace_pool_minutes"])
        self.mode, self.authority = self._mode()
        self.catalog = self._catalog()
        self.pledges = {}
        self._registers()
        self.suspended = []
        self.shifted = set()
        self._series()
        self.amendments = self._amendments()
        self.due = {}
        self.authority_of = {}
        self.record_of = {}
        self.expr_of = {}
        self.ack_over_register = set()
        self._govern_due()
        self.evidence = self._evidence()
        self.waivers = self._waivers()
        self.edges = self._edges()

    def _dead(self):
        notices = read_rows("retraction_notices.csv")
        live = {}
        for row in notices:
            if moment(row["occurred_at"]) > self.cutoff:
                continue
            if moment(row["logged_at"]) > self.cutoff:
                continue
            live[row["notice_id"]] = row
        killed = {
            row["target_record_key"]
            for row in live.values()
            if row["target_kind"] == "retraction_notice"
        }
        self.restored = sorted(
            {
                live[n]["target_record_key"]
                for n in killed
                if n in live and live[n]["target_kind"] != "retraction_notice"
            }
        )
        self.retraction_of_retraction = len(killed & set(live))
        return {
            row["target_record_key"]
            for notice, row in live.items()
            if notice not in killed
        }

    def _directive(self):
        best = None
        for row in read_jsonl(self.spec.directive_file):
            if row["window_id"] != self.spec.window_id:
                continue
            if moment(row["issued_at"]) > self.cutoff:
                continue
            if moment(row["logged_at"]) > self.cutoff:
                continue
            if row["directive_id"] in self.dead:
                continue
            if best is None or int(row["revision"]) > int(best["revision"]):
                best = row
        if best is None:
            raise SystemExit("no live directive for the window")
        return best

    def _mode(self):
        wanted = self.directive["mode_directive"]
        needs = str(self.directive["requires_countersignature"]).lower() == "true"
        if not needs:
            return wanted, ""
        signed = {}
        for row in read_rows("countersignature_register.csv"):
            if moment(row["countersigned_at"]) > self.cutoff:
                continue
            if moment(row["logged_at"]) > self.cutoff:
                continue
            if row["countersignature_id"] in self.dead:
                continue
            signed.setdefault(row["order_id"], []).append(row)
        best = None
        for row in read_rows("principal_standing_orders.csv"):
            if row["scope"] != "settlement_mode":
                continue
            if moment(row["issued_at"]) > self.cutoff:
                continue
            if moment(row["logged_at"]) > self.cutoff:
                continue
            if row["order_id"] in self.dead:
                continue
            if row["order_id"] not in signed:
                continue
            if best is None or moment(row["issued_at"]) > moment(best["issued_at"]):
                best = row
        if best is None or best["mode"] != wanted:
            return self.spec.default_mode, ""
        return wanted, best["order_id"]

    def _catalog(self):
        table = {}
        for row in read_rows("pledge_class_catalog.csv"):
            table.setdefault(row["pledge_class"], []).append(row)
        for rows in table.values():
            rows.sort(key=lambda r: r["effective_from"])
        return table

    def facts(self, klass, instant):
        stamp = instant.astimezone(UTC).date().isoformat()
        for row in self.catalog[klass]:
            if row["effective_from"] <= stamp < row["effective_to"]:
                return row
        raise SystemExit("no class facts for %s at %s" % (klass, stamp))

    def _registers(self):
        for year in ("2024", "2025", "2026"):
            for row in read_rows("pledge_register_%s.csv" % year):
                key = self.holders.resolve(row["counterparty_ref"])
                if key is None:
                    raise SystemExit(
                        "holder did not resolve for register record %s" % row["record_key"]
                    )
                self.pledges[row["pledge_id"]] = {
                    "pledge_id": row["pledge_id"],
                    "holder": key,
                    "klass": row["pledge_class"],
                    "origin": moment(row["origin_instant"]),
                    "expression": row["due_expression"],
                    "record": row["record_key"],
                    "series": row["series_id"],
                    "period": row["period"],
                    "shift": False,
                }

    def _series(self):
        overrides = {}
        for row in read_rows("series_instance_overrides.csv"):
            if moment(row["logged_at"]) > self.cutoff:
                continue
            overrides[(row["series_id"], row["period"])] = row
        for row in read_rows("recurring_series_definitions.csv"):
            holder = self.holders.resolve(row["counterparty_ref"])
            if holder is None:
                raise SystemExit("holder did not resolve for series %s" % row["series_id"])
            for label in self._periods(row):
                action = overrides.get((row["series_id"], label))
                klass = row["pledge_class"]
                expression = row["due_expression"]
                shifted = False
                target = holder
                if action is not None:
                    if action["action"] == "suspend":
                        self.suspended.append((row["series_id"], label))
                        continue
                    if action["action"] == "shift":
                        expression = action["value"]
                        shifted = True
                    if action["action"] == "reassign":
                        moved = self.holders.resolve(action["value"])
                        if moved is None:
                            raise SystemExit(
                                "reassignment %s names no holder" % action["override_id"]
                            )
                        target = moved
                identifier = "%s#%s" % (row["series_id"], label)
                origin = self.clock.to_utc(
                    self.holders.zone(target),
                    self._origin(row["cadence"], label, int(row["anchor_day"])),
                )
                if shifted:
                    self.shifted.add(identifier)
                self.pledges[identifier] = {
                    "pledge_id": identifier,
                    "holder": target,
                    "klass": klass,
                    "origin": origin,
                    "expression": expression,
                    "record": "SRX-%s-%s" % (row["series_id"], label),
                    "series": row["series_id"],
                    "period": label,
                    "shift": shifted,
                }

    def _periods(self, row):
        labels = []
        if row["cadence"] == "monthly":
            start = row["first_period"]
            stop = row["last_period"]
            year, month = int(start[:4]), int(start[5:7])
            while "%04d-%02d" % (year, month) <= stop:
                labels.append("%04d-%02d" % (year, month))
                month += 1
                if month > 12:
                    month = 1
                    year += 1
        else:
            year, quarter = int(row["first_period"][:4]), int(row["first_period"][-1])
            while "%04d-Q%d" % (year, quarter) <= row["last_period"]:
                labels.append("%04d-Q%d" % (year, quarter))
                quarter += 1
                if quarter > 4:
                    quarter = 1
                    year += 1
        return labels

    def _origin(self, cadence, label, anchor):
        if cadence == "monthly":
            year, month = int(label[:4]), int(label[5:7])
            span = [31, 29 if year % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
            return datetime(year, month, min(anchor, span[month - 1]), 9, 0)
        year, quarter = int(label[:4]), int(label[-1])
        start = date(year, 3 * (quarter - 1) + 1, 1) + timedelta(days=anchor - 1)
        return datetime(start.year, start.month, start.day, 9, 0)

    def _amendments(self):
        out = {}

        def keep(record, source, pledge, expression, occurred, logged):
            if not expression or not pledge:
                return
            if source == "voice_memo":
                return
            if record in self.dead:
                return
            if moment(occurred) > self.cutoff or moment(logged) > self.cutoff:
                return
            out.setdefault(pledge, []).append(
                {
                    "record": record,
                    "source": source,
                    "expression": expression,
                    "occurred": occurred,
                    "logged": logged,
                }
            )

        for name in ("register_amendments_prior.csv", "register_amendments_window.csv"):
            for row in read_rows(name):
                if row["field_class"] != "due_instant":
                    continue
                keep(
                    row["record_key"],
                    "register",
                    pledge_ref(row["pledge_id"]),
                    row["due_expression"],
                    row["occurred_at"],
                    row["logged_at"],
                )
        for name in (
            "counterparty_ack_feed_prior.jsonl",
            "counterparty_ack_feed_window.jsonl",
        ):
            for row in read_jsonl(name):
                if row["field_class"] != "due_instant":
                    continue
                keep(
                    row["record_key"],
                    "counterparty_ack",
                    pledge_ref(row["pledge_id"]),
                    row["due_expression"],
                    row["occurred_at"],
                    row["logged_at"],
                )
        for row in read_jsonl("inbox_thread_extracts.jsonl"):
            if row["field_class"] != "due_instant":
                continue
            keep(
                row["record_key"],
                "inbox_thread",
                pledge_ref(row["pledge_ref"]),
                row.get("due_expression", ""),
                row["occurred_at"],
                row["logged_at"],
            )
        return out

    def _pick(self, records, order):
        rule = self.rules["tiebreak"]
        early = rule.startswith("early_log")
        high = rule.endswith("high_key")
        for source in order:
            tier = [r for r in records if r["source"] == source]
            if not tier:
                continue
            return sorted(
                tier,
                key=lambda r: (
                    [-ord(c) for c in r["occurred"]],
                    r["logged"] if early else _invert(r["logged"]),
                    _invert(r["record"]) if high else r["record"],
                ),
            )[0]
        return None

    def _govern_due(self):
        order = self.spec.source_order["due_instant"]
        for pid, entry in self.pledges.items():
            records = self.amendments.get(pid, [])
            best = self._pick(records, order)
            if best is None:
                expression = entry["expression"]
                self.authority_of[pid] = "register"
                self.record_of[pid] = entry["record"]
            else:
                expression = best["expression"]
                self.authority_of[pid] = best["source"]
                self.record_of[pid] = best["record"]
                if best["source"] == "counterparty_ack" and any(
                    r["source"] == "register" for r in records
                ):
                    self.ack_over_register.add(pid)
            self.expr_of[pid] = expression
            self.due[pid] = self.clock.resolve_due(
                self.holders.zone(entry["holder"]), entry["holder"], entry["origin"], expression
            )

    def _evidence(self):
        out = {}

        def keep(record, source, pledge, occurred, logged):
            if not pledge or record in self.dead:
                return
            if moment(occurred) > self.cutoff or moment(logged) > self.cutoff:
                return
            out.setdefault(pledge, []).append(
                {
                    "record": record,
                    "source": source,
                    "occurred": occurred,
                    "logged": logged,
                }
            )

        for name in ("discharge_evidence_desk.csv", "discharge_evidence_portal.csv"):
            for row in read_rows(name):
                keep(
                    row["record_key"],
                    "register",
                    pledge_ref(row["pledge_ref"]),
                    row["occurred_at"],
                    row["logged_at"],
                )
        for row in read_rows("counterparty_receipts.tsv", "\t"):
            keep(
                row["record_key"],
                "counterparty_ack",
                pledge_ref(row["pledge_ref"]),
                row["occurred_at"],
                row["logged_at"],
            )
        for row in read_jsonl("inbox_thread_extracts.jsonl"):
            if row["field_class"] != "discharge_evidence":
                continue
            keep(
                row["record_key"],
                "inbox_thread",
                pledge_ref(row["pledge_ref"]),
                row["occurred_at"],
                row["logged_at"],
            )
        return out

    def _waivers(self):
        order = self.spec.source_order["waiver"]
        out = {}
        for row in read_rows("waiver_grants.csv"):
            if row["source"] not in order:
                continue
            if row["record_key"] in self.dead:
                continue
            if moment(row["granted_at"]) > self.cutoff:
                continue
            if moment(row["logged_at"]) > self.cutoff:
                continue
            pid = pledge_ref(row["pledge_ref"])
            if not pid:
                raise SystemExit("waiver %s names no pledge" % row["record_key"])
            out.setdefault(pid, []).append(
                {
                    "record": row["record_key"],
                    "source": row["source"],
                    "occurred": row["granted_at"],
                    "logged": row["logged_at"],
                }
            )
        return out

    def _edges(self):
        out = {}
        self.edge_rows = 0
        for row in read_rows("prereq_edges.tsv", "\t"):
            child = row["pledge_id"]
            parent = row["prereq_pledge_id"]
            if child not in self.pledges or parent not in self.pledges:
                continue
            out.setdefault(child, set()).add(parent)
            self.edge_rows += 1
        return out

    def governing_evidence(self, pid):
        return self._pick(
            self.evidence.get(pid, []), self.spec.source_order["discharge_evidence"]
        )

    def governing_waiver(self, pid):
        return self._pick(self.waivers.get(pid, []), self.spec.source_order["waiver"])


# -------------------------------------------------------------- settlement


def reachable(corpus, seeds):
    seen = set()
    stack = list(seeds)
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(corpus.edges.get(node, ()))
    return seen


def components(corpus, nodes):
    index = {}
    low = {}
    stack = []
    onstack = set()
    groups = []
    counter = [0]
    for root in sorted(nodes):
        if root in index:
            continue
        work = [(root, iter(sorted(corpus.edges.get(root, ()))))]
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        onstack.add(root)
        while work:
            node, kids = work[-1]
            advanced = False
            for kid in kids:
                if kid not in nodes:
                    continue
                if kid not in index:
                    index[kid] = low[kid] = counter[0]
                    counter[0] += 1
                    stack.append(kid)
                    onstack.add(kid)
                    work.append((kid, iter(sorted(corpus.edges.get(kid, ())))))
                    advanced = True
                    break
                if kid in onstack:
                    low[node] = min(low[node], index[kid])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[node])
            if low[node] == index[node]:
                group = set()
                while True:
                    item = stack.pop()
                    onstack.discard(item)
                    group.add(item)
                    if item == node:
                        break
                groups.append(group)
    return groups


def group_order(corpus, groups, nodes):
    owner = {}
    for position, group in enumerate(groups):
        for member in group:
            owner[member] = position
    waits = {position: set() for position in range(len(groups))}
    for child, parents in corpus.edges.items():
        if child not in owner:
            continue
        for parent in parents:
            if parent in owner and owner[parent] != owner[child]:
                waits[owner[child]].add(owner[parent])
    ready = sorted(
        (position for position, need in waits.items() if not need),
        key=lambda position: min(groups[position]),
    )
    done = []
    pending = {position: set(need) for position, need in waits.items()}
    while ready:
        position = ready.pop(0)
        done.append(position)
        for other, need in pending.items():
            if position in need:
                need.discard(position)
                if not need and other not in done and other not in ready:
                    ready.append(other)
        ready.sort(key=lambda item: min(groups[item]))
    if len(done) != len(groups):
        raise SystemExit("dependency order did not resolve")
    return done


def settle(corpus, due, mode, pool, cycle_state, cycle_code, exclude_states, exclude_classes):
    docket = sorted(
        p for p, when in due.items() if corpus.window_open <= when < corpus.window_close
    )
    nodes = reachable(corpus, docket)
    groups = components(corpus, nodes)
    held = set()
    for group in groups:
        if len(group) > 1:
            held |= group
        else:
            only = next(iter(group))
            if only in corpus.edges.get(only, ()):
                held.add(only)
    order = group_order(corpus, groups, nodes)
    state = {}
    effective = {}
    minutes = {}
    reasons = {}
    for position in order:
        for pid in sorted(groups[position]):
            entry = corpus.pledges[pid]
            when = due.get(pid)
            if when is None:
                when = corpus.clock.resolve_due(
                    corpus.holders.zone(entry["holder"]),
                    entry["holder"],
                    entry["origin"],
                    entry["expression"],
                )
            zone = corpus.holders.zone(entry["holder"])
            marks = set()
            if entry["shift"]:
                marks.add("series_shifted")
            if pid in corpus.ack_over_register:
                marks.add("ack_supersedes_register")
            gone = corpus.holders.dissolved(entry["holder"])
            if (
                corpus.holders.status(entry["holder"]) == "dissolved"
                and gone is not None
                and gone <= corpus.clock.to_local(zone, when).date()
            ):
                state[pid] = "lapsed"
                marks.add("counterparty_dissolved")
                effective[pid] = None
                minutes[pid] = 0
            elif pid in held:
                state[pid] = cycle_state
                marks.add(cycle_code)
                effective[pid] = None
                minutes[pid] = 0
            else:
                gifts = []
                stuck = False
                for parent in sorted(corpus.edges.get(pid, ())):
                    if state.get(parent) == "lapsed":
                        marks.add("prereq_lapsed")
                        continue
                    if effective.get(parent) is None:
                        stuck = True
                        continue
                    gifts.append(effective[parent])
                waiver = corpus.governing_waiver(pid)
                proof = corpus.governing_evidence(pid)
                if stuck:
                    state[pid] = "blocked"
                    marks.add("prereq_unsettled")
                    effective[pid] = None
                    minutes[pid] = 0
                elif waiver is not None and (
                    proof is None
                    or moment(waiver["occurred"]) < moment(proof["occurred"])
                ):
                    grant = moment(waiver["occurred"])
                    state[pid] = "waived"
                    effective[pid] = grant
                    minutes[pid] = 0
                    marks.add("waiver_applied")
                    if grant > when:
                        marks.add("waiver_late")
                elif proof is not None:
                    own = moment(proof["occurred"])
                    reached = max([own] + gifts)
                    if gifts and max(gifts) > own:
                        marks.add("prereq_pushed")
                    gap = (reached - when).total_seconds()
                    late = int(gap // 60) if gap > 0 else 0
                    effective[pid] = reached
                    minutes[pid] = late
                    if late > 0:
                        marks.add("late_evidence")
                        state[pid] = "breached"
                    else:
                        state[pid] = "cleared"
                else:
                    gap = (corpus.cutoff - when).total_seconds()
                    state[pid] = "breached"
                    marks.add("no_evidence")
                    effective[pid] = None
                    minutes[pid] = int(gap // 60) if gap > 0 else 0
            reasons[pid] = marks

    granted = {pid: 0 for pid in docket}
    ceiling_cut = 0
    round_size = 0
    if mode == "tempered" and pool > 0:
        items = []
        for pid in docket:
            if state[pid] != "breached" or effective[pid] is None:
                continue
            facts = corpus.facts(corpus.pledges[pid]["klass"], due[pid])
            if facts["grace_eligible"] != "yes":
                continue
            items.append((pid, minutes[pid], int(facts["ceiling_minutes"])))
        round_size = len(items)
        if items:
            total = sum(i[2] for i in items)
            for pid, late, ceiling in items:
                if total > 0 and float(min(late, ceiling)) < pool * ceiling / float(total):
                    reasons[pid].add("class_ceiling_binding")
                    ceiling_cut += 1
            for pid, value in share_round(pool, items, False).items():
                granted[pid] = value
                if value >= minutes[pid]:
                    state[pid] = "tempered_clear"

    rows = []
    for pid in docket:
        entry = corpus.pledges[pid]
        late = minutes[pid]
        give = granted.get(pid, 0)
        rest = late - give if state[pid] == "breached" else 0
        rows.append(
            {
                "pledge_id": pid,
                "counterparty_key": entry["holder"],
                "pledge_class": entry["klass"],
                "governing_due_instant": iso(due[pid]),
                "due_authority": corpus.authority_of[pid],
                "due_record_key": corpus.record_of[pid],
                "effective_discharge_instant": iso(effective[pid])
                if effective[pid]
                else None,
                "lateness_minutes": late,
                "granted_minutes": give,
                "residual_minutes": rest,
                "final_state": state[pid],
                "reason_codes": sorted(reasons[pid]),
            }
        )
    tally = {}
    for name in (
        "breached",
        "cleared",
        "tempered_clear",
        "waived",
        "blocked",
        "held",
        "lapsed",
    ):
        tally[name] = sum(1 for r in rows if r["final_state"] == name)
    denominator = 0
    in_rate_breached = 0
    for row in rows:
        facts = corpus.facts(row["pledge_class"], due[row["pledge_id"]])
        if facts["in_breach_rate"] != "yes":
            continue
        if row["final_state"] in exclude_states:
            continue
        if row["pledge_class"] in exclude_classes:
            continue
        denominator += 1
        if row["final_state"] == "breached":
            in_rate_breached += 1
    return {
        "docket": docket,
        "rows": rows,
        "state": state,
        "effective": effective,
        "minutes": minutes,
        "granted": granted,
        "tally": tally,
        "denominator": denominator,
        "breached_in_rate": in_rate_breached,
        "ceiling_cut": ceiling_cut,
        "round_size": round_size,
        "held": held,
        "total_lateness": sum(r["lateness_minutes"] for r in rows),
        "total_granted": sum(r["granted_minutes"] for r in rows),
    }


# -------------------------------------------------------------- interface


def api(base, endpoint, body, method="POST"):
    data = None
    headers = {"X-Docket-Channel": "api"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    ask = urllib.request.Request(base + endpoint, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(ask, timeout=60) as answer:
            return answer.status, json.loads(answer.read().decode("utf-8"))
    except urllib.error.HTTPError as refused:
        raw = refused.read().decode("utf-8")
        try:
            return refused.code, json.loads(raw)
        except ValueError:
            return refused.code, {"error": raw}


def through_client(base, endpoint, body):
    done = subprocess.run(
        [
            sys.executable,
            os.path.join(SERVICE, "client.py"),
            "--base",
            base,
            "post",
            endpoint,
            "--json",
            json.dumps(body),
        ],
        cwd=SERVICE,
        capture_output=True,
        text=True,
        timeout=120,
    )
    lines = [line for line in done.stdout.splitlines() if line.strip()]
    if not lines:
        raise SystemExit("client returned nothing for %s" % endpoint)
    answer = json.loads(lines[-1])
    return answer["status"], answer["payload"]


def stop_interface(proc):
    for stroke in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, stroke)
        except OSError:
            # the process group is already gone, so there is nothing left to stop
            return
        try:
            proc.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            continue


def start_interface(spec):
    proc = subprocess.Popen(
        [
            sys.executable,
            os.path.join(SERVICE, "simulator.py"),
            "--host",
            spec.host,
            "--port",
            str(spec.port),
        ],
        cwd=SERVICE,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = "http://%s:%s" % (spec.host, spec.port)
    for _ in range(150):
        try:
            status, answer = api(base, "/health", None, "GET")
            if status == 200 and answer.get("ok"):
                return proc, base
        except OSError:
            # the interface is still binding its port; the loop retries and
            # raises below once the attempts run out
            pass
        time.sleep(0.1)
    stop_interface(proc)
    raise SystemExit("interface did not answer on %s" % base)


def file_order(corpus, result):
    docket = set(result["docket"])
    held = result["held"]
    waits = {}
    for pid in docket:
        kin = set()
        for parent in corpus.edges.get(pid, ()):
            if parent in docket and not (pid in held and parent in held):
                kin.add(parent)
        waits[pid] = kin
    ready = sorted(pid for pid, kin in waits.items() if not kin)
    done = []
    seen = set(ready)
    while ready:
        pid = ready.pop(0)
        done.append(pid)
        for other, kin in waits.items():
            if pid in kin:
                kin.discard(pid)
                if not kin and other not in seen:
                    seen.add(other)
                    ready.append(other)
        ready.sort()
    if len(done) != len(docket):
        raise SystemExit("registration order did not resolve")
    return done, waits


def boundary_notices(spec, corpus):
    low = corpus.window_open - spec.boundary
    high = corpus.window_close + spec.boundary
    return sorted(
        pid
        for pid, when in corpus.due.items()
        if (low <= when < corpus.window_open) or (corpus.window_close <= when < high)
    )


def drive(spec, corpus, result, notices, cli_event):
    proc, base = start_interface(spec)
    try:
        status, _ = api(
            base,
            "/window",
            {
                "window_id": spec.window_id,
                "window_open": iso(corpus.window_open),
                "window_close": iso(corpus.window_close),
                "settlement_cutoff": iso(corpus.cutoff),
                "grace_pool_minutes": corpus.pool,
                "mode": corpus.mode,
            },
        )
        if status != 200:
            raise SystemExit("window declaration refused")
        order, waits = file_order(corpus, result)
        docket = set(result["docket"])
        for pid in order:
            outside = []
            for parent in corpus.edges.get(pid, ()):
                if parent in docket:
                    continue
                reached = result["effective"].get(parent)
                if reached is not None:
                    outside.append({"pledge_id": parent, "effective_instant": iso(reached)})
            status, _ = api(
                base,
                "/register",
                {
                    "pledge_id": pid,
                    "counterparty_key": corpus.pledges[pid]["holder"],
                    "pledge_class": corpus.pledges[pid]["klass"],
                    "due_instant": iso(corpus.due[pid]),
                    "prereqs": sorted(waits[pid]),
                    "external_prereqs": outside,
                },
            )
            if status != 200:
                raise SystemExit("registration refused for %s" % pid)
        for pid in notices:
            status, answer = api(
                base,
                "/register",
                {
                    "pledge_id": pid,
                    "counterparty_key": corpus.pledges[pid]["holder"],
                    "pledge_class": corpus.pledges[pid]["klass"],
                    "due_instant": iso(corpus.due[pid]),
                    "boundary": True,
                },
            )
            if answer.get("reason") != "out_of_window":
                raise SystemExit("boundary notice for %s was not refused" % pid)
        for pid in order:
            status, _ = api(base, "/transition", {"pledge_id": pid, "event": "acknowledge"})
            if status != 200:
                raise SystemExit("acknowledgement refused for %s" % pid)
            final = result["state"][pid]
            reached = result["effective"].get(pid)
            late = result["minutes"].get(pid, 0)
            if final == "waived":
                event = "waive"
            elif final in ("cleared", "tempered_clear", "breached"):
                event = "discharge" if reached is not None else "breach"
            elif final == "blocked":
                event = "block"
            elif final == "lapsed":
                event = "lapse"
            else:
                event = "hold"
            body = {"pledge_id": pid, "event": event}
            if event in ("discharge", "waive"):
                body["effective_instant"] = iso(reached)
            if event in ("discharge", "breach", "waive"):
                body["lateness_minutes"] = late
            if event == cli_event:
                status, _ = through_client(base, "/transition", body)
            else:
                status, _ = api(base, "/transition", body)
            if status != 200:
                raise SystemExit("event %s refused for %s" % (event, pid))
        for pid in result["docket"]:
            give = result["granted"].get(pid, 0)
            if give <= 0:
                continue
            status, _ = api(
                base,
                "/grace",
                {
                    "pledge_id": pid,
                    "granted_minutes": give,
                    "lateness_minutes": result["minutes"][pid],
                },
            )
            if status != 200:
                raise SystemExit("grace refused for %s" % pid)
        status, sealed = api(base, "/seal", {})
        if status != 200:
            raise SystemExit("seal refused")
        status, again = api(base, "/seal", {})
        if again.get("reason") != "already_sealed":
            raise SystemExit("seal confirmation was accepted")
        _, snapshot = api(base, "/state", None, "GET")
        _, transcript = api(base, "/transcript", None, "GET")
        return snapshot, transcript
    finally:
        stop_interface(proc)


# -------------------------------------------------------------- artifacts


def legs_table():
    rows = []
    for row in read_rows("travel_itinerary.csv"):
        rows.append((moment(row["depart_instant"]), moment(row["return_instant"]), row["zone"]))
    rows.sort()
    return rows


def zone_at(legs, home, when):
    for start, stop, zone in legs:
        if start <= when < stop:
            return zone
    return home


def presence_due(corpus, legs, home):
    out = {}
    for pid, entry in corpus.pledges.items():
        zone = zone_at(legs, home, entry["origin"])
        out[pid] = corpus.clock.resolve_due(
            zone, entry["holder"], entry["origin"], corpus.expr_of[pid]
        )
    return out


def shaped(spec, name, data):
    want = sorted(spec.contract[name])
    if sorted(data) != want:
        raise SystemExit("artifact %s carries %s" % (name, sorted(data)))
    return data


def put(name, data):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, indent=2, sort_keys=True) + "\n")


def main():
    spec = Specs()
    rules = {
        "tiebreak": learn_tiebreak(),
        "duplicate": learn_duplicate_rule(),
        "lateness": learn_lateness_rule(),
        "readiness": learn_readiness(),
        "redistribute": learn_grace_rule(),
        "exclusions": learn_exclusions(),
        "cycle": learn_cycle_rule(),
        "periods": learn_period_forms(),
        "boundary": learn_boundary_reason(),
        "cli": learn_cli_event(),
        "probes": learn_probe_fields(),
    }
    holders = Holders(spec)
    clock = Clock(holders)
    corpus = Corpus(spec, holders, clock, rules)
    bad_states, bad_classes = rules["exclusions"]
    cycle_state, cycle_code = rules["cycle"]
    filed = settle(
        corpus, corpus.due, corpus.mode, corpus.pool, cycle_state, cycle_code, bad_states, bad_classes
    )
    alpha = settle(
        corpus, corpus.due, "strict", 0, cycle_state, cycle_code, bad_states, bad_classes
    )
    legs = legs_table()
    beta_due = presence_due(corpus, legs, spec.home_zone)
    beta = settle(
        corpus, beta_due, corpus.mode, corpus.pool, cycle_state, cycle_code, bad_states, bad_classes
    )
    notices = boundary_notices(spec, corpus)
    snapshot, transcript = drive(spec, corpus, filed, notices, rules["cli"])

    counts = {
        "audit_total": len(filed["rows"]),
        "breach_rate_denominator": filed["denominator"],
    }
    counts.update(filed["tally"])
    report = shaped(
        spec,
        "report",
        {
            "window_id": spec.window_id,
            "governing_mode": corpus.mode,
            "settlement_cutoff": iso(corpus.cutoff),
            "pledges": filed["rows"],
            "counts": shaped(spec, "report_counts", counts),
        },
    )
    put("report.json", report)

    put("final_state.json", shaped(spec, "final_state", snapshot))

    calls = transcript["calls"]
    reasons = {}
    for call in calls:
        if not call["accepted"] and call["reason"]:
            reasons[call["reason"]] = reasons.get(call["reason"], 0) + 1
    put(
        "transcript_summary.json",
        shaped(
            spec,
            "transcript_summary",
            {
                "total_calls": len(calls),
                "accepted_calls": sum(1 for call in calls if call["accepted"]),
                "rejected_calls": sum(1 for call in calls if not call["accepted"]),
                "calls_by_channel": {
                    "api": sum(1 for call in calls if call["channel"] == "api"),
                    "cli": sum(1 for call in calls if call["channel"] == "cli"),
                },
                "rejections_by_reason": reasons,
                "first_sequence": calls[0]["sequence"],
                "last_sequence": calls[-1]["sequence"],
                "seal_sequence": transcript["seal_sequence"],
            },
        ),
    )

    reverted = sorted(
        row["pledge_id"]
        for row in filed["rows"]
        if row["final_state"] == "tempered_clear"
    )
    put(
        "scenario_alpha.json",
        shaped(
            spec,
            "scenario_alpha",
            {
                "scenario_id": "alpha",
                "basis": "grace_withdrawn",
                "breached": alpha["tally"]["breached"],
                "tempered_clear": alpha["tally"]["tempered_clear"],
                "reverted_pledges": reverted,
                "total_residual_minutes": sum(
                    row["residual_minutes"] for row in alpha["rows"]
                ),
            },
        ),
    )

    moved = sorted(set(beta["docket"]).symmetric_difference(filed["docket"]))
    put(
        "scenario_beta.json",
        shaped(
            spec,
            "scenario_beta",
            {
                "scenario_id": "beta",
                "basis": "presence_zone_resolution",
                "docket_size": len(beta["docket"]),
                "breached": beta["tally"]["breached"],
                "membership_changes": moved,
                "lateness_delta_minutes": beta["total_lateness"] - filed["total_lateness"],
            },
        ),
    )

    put(
        "scenario_mode.json",
        shaped(
            spec,
            "scenario_mode",
            {
                "scenario_id": "mode",
                "governing_mode": corpus.mode,
                "countersignature_authority": corpus.authority,
                "tallies": {
                    "strict": {
                        "breached": alpha["tally"]["breached"],
                        "cleared": alpha["tally"]["cleared"],
                        "tempered_clear": alpha["tally"]["tempered_clear"],
                        "waived": alpha["tally"]["waived"],
                    },
                    "tempered": {
                        "breached": filed["tally"]["breached"],
                        "cleared": filed["tally"]["cleared"],
                        "tempered_clear": filed["tally"]["tempered_clear"],
                        "waived": filed["tally"]["waived"],
                    },
                },
                "grace_pool_minutes": corpus.pool,
                "grace_unused_minutes": corpus.pool - filed["total_granted"],
            },
        ),
    )

    breach_by_holder = {}
    for row in filed["rows"]:
        if row["final_state"] == "breached":
            breach_by_holder[row["counterparty_key"]] = (
                breach_by_holder.get(row["counterparty_key"], 0) + 1
            )
    top = ""
    if breach_by_holder:
        top = sorted(breach_by_holder.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]
    rate = 0
    if filed["denominator"]:
        rate = half_up(1000.0 * filed["breached_in_rate"] / filed["denominator"])
    put(
        "summary.json",
        shaped(
            spec,
            "summary",
            {
                "window_id": spec.window_id,
                "governing_mode": corpus.mode,
                "audit_total": len(filed["rows"]),
                "breach_rate_denominator": filed["denominator"],
                "breached_in_rate": filed["breached_in_rate"],
                "breach_rate_per_mille": rate,
                "granted_minutes_total": filed["total_granted"],
                "unresolved_pledges": sorted(
                    row["pledge_id"]
                    for row in filed["rows"]
                    if row["final_state"] in ("blocked", "held")
                ),
                "settlement_fingerprint": snapshot["settlement_fingerprint"],
                "counterparty_count": len(
                    {row["counterparty_key"] for row in filed["rows"]}
                ),
                "top_breach_counterparty": top,
            },
        ),
    )

    shifts = 0
    for pid in filed["docket"]:
        zone = holders.zone(corpus.pledges[pid]["holder"])
        local = clock.to_local(zone, corpus.due[pid]).date()
        for mark in clock.shift_dates.get(zone, ()):
            if corpus.window_open.date() <= mark < corpus.window_close.date() and local >= mark:
                shifts += 1
                break
    ceilings = 0
    for pid in filed["docket"]:
        rows = list(corpus.catalog.get(corpus.pledges[pid]["klass"], ()))
        for before, after in zip(rows, rows[1:]):
            mark = day(after["effective_from"])
            if (
                corpus.window_open.date() < mark < corpus.window_close.date()
                and before["ceiling_minutes"] != after["ceiling_minutes"]
            ):
                ceilings += 1
                break
    outside_edges = sum(
        1
        for pid in filed["docket"]
        for parent in corpus.edges.get(pid, ())
        if parent not in set(filed["docket"])
    )
    tiers = [
        int(corpus.facts(row["pledge_class"], corpus.due[row["pledge_id"]])["escalation_tier"])
        for row in filed["rows"]
        if row["final_state"] == "breached"
    ]
    peak = max(tiers) if tiers else 0
    before = sum(1 for pid in notices if corpus.due[pid] < corpus.window_open)
    after = len(notices) - before
    print("docket closed for %s under mode %s" % (spec.window_id, corpus.mode))
    print(
        "ack_over_register=%d source=counterparty_ack_feed_prior.jsonl,"
        "counterparty_ack_feed_window.jsonl"
        % len(set(corpus.ack_over_register) & set(filed["docket"]))
    )
    print("ceiling_rows_changed_inside_window=%d source=pledge_class_catalog.csv" % ceilings)
    print(
        "retractions_retracted=%d restored=%s"
        % (corpus.retraction_of_retraction, ",".join(sorted(corpus.restored)))
    )
    print("boundary_before_open=%d boundary_after_close=%d" % (before, after))
    print(
        "grace_round_entrants=%d rule=grace_allocation.md entrant: breached, holding an "
        "effective instant, class grace_eligible yes at the governing due instant"
        % filed["round_size"]
    )
    seats = {corpus.pledges[pid]["holder"] for pid in filed["docket"]}
    print(
        "aliases_needing_suffix_strip=%d source=counterparty_alias_map.csv"
        % len(holders.suffix_hits & seats)
    )
    print("prereq_edges_outside_docket=%d source=prereq_edges.tsv" % outside_edges)
    kin = {pid.split("#")[0] for pid in filed["docket"] if "#" in pid}
    print(
        "series_instances_suspended=%d source=series_instance_overrides.csv"
        % sum(1 for sid, _ in corpus.suspended if sid in kin)
    )
    print("peak_escalation_tier=%d carriers=%d" % (peak, tiers.count(peak) if tiers else 0))
    print("due_instants_after_zone_shift=%d source=zone_offset_table.csv" % shifts)


if __name__ == "__main__":
    main()
