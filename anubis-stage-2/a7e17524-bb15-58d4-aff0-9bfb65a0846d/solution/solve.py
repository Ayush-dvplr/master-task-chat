#!/usr/bin/env python3
"""Adjudicate cycle RC-2411 of the Hollowbrand package relay, drive the relay
service through the admitted promotions and write the cycle artifacts."""
from __future__ import annotations

import configparser
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

DATA = os.environ.get("RELAY_DATA", "/app/data")
OUT = os.environ.get("RELAY_OUT", "/app/out")
SERVICE = os.environ.get("RELAY_SERVICE", "/app/service")
LADDER = ["edge", "canary", "staging", "stable"]
TIER_RANK = {"tier1": 1, "tier2": 2, "tier3": 3}
WEEKDAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday",
                 "saturday", "sunday"]


def parse_instant(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def show_instant(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


GRAMMAR_FIELDS: List[str] = ["epoch", "major", "minor", "patch", "build"]


def revision_tuple(text: str) -> Tuple[int, ...]:
    epoch, rest = text.split(":", 1)
    core, build = rest.rsplit("-", 1)
    major, minor, patch = core.split(".")
    parts = {"epoch": int(epoch), "major": int(major), "minor": int(minor),
             "patch": int(patch), "build": int(build)}
    return tuple(parts[name] for name in GRAMMAR_FIELDS)


def read_csv(name: str) -> List[Dict[str, str]]:
    with open(os.path.join(DATA, name), "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_tsv(name: str) -> List[Dict[str, str]]:
    with open(os.path.join(DATA, name), "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_jsonl(name: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(os.path.join(DATA, name), "r", encoding="utf-8") as handle:
        for line in handle:
            body = line.strip()
            if body:
                rows.append(json.loads(body))
    return rows


def read_json(name: str) -> Any:
    with open(os.path.join(DATA, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_blocks(name: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    site: Optional[str] = None
    field: Optional[str] = None
    with open(os.path.join(DATA, name), "r", encoding="utf-8") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            indent = len(raw) - len(raw.lstrip())
            body = raw.strip()
            if body.startswith("- "):
                if site is not None and field is not None:
                    out[site].setdefault(field, []).append(body[2:].strip())
            elif indent == 2 and body.endswith(":"):
                site = body[:-1]
                out.setdefault(site, {})
                field = None
            elif indent == 4 and body.endswith(":"):
                field = body[:-1]
            elif indent == 4 and ":" in body and site is not None:
                key, value = body.split(":", 1)
                out[site][key.strip()] = value.strip()
    return out


def read_params(name: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    fenced = False
    with open(os.path.join(DATA, name), "r", encoding="utf-8") as handle:
        for raw in handle:
            body = raw.rstrip("\n")
            if body.startswith("```"):
                fenced = not fenced
                continue
            if not fenced or ":" not in body:
                continue
            key, value = body.split(":", 1)
            if re.match(r"^[a-z][a-z0-9_]*$", key) and value.strip():
                out[key] = value.strip()
    return out


def at_or_before(stamp: str, cut: str, rule: str) -> bool:
    """Apply one declared boundary rule to an instant comparison."""
    return stamp <= cut if rule == "inclusive" else stamp < cut


def governing(rows: Iterable[Dict[str, Any]], ident: str,
              cut: str) -> Optional[Dict[str, Any]]:
    best: Optional[Tuple[Tuple[str, str], Dict[str, Any]]] = None
    for row in rows:
        if str(row["effective_at"]) > cut:
            continue
        mark = (str(row["recorded_at"]), str(row[ident]))
        if best is None or mark > best[0]:
            best = (mark, row)
    return None if best is None else best[1]


class Evidence(object):
    def __init__(self) -> None:
        global GRAMMAR_FIELDS, LADDER
        self.index_params = read_params("data_index_spec.md")
        self.rule_params = read_params("relay_governance_spec.md")
        self.ladder_params = read_params("channel_ladder_spec.md")
        self.identity_params = read_params("unit_identity_spec.md")
        self.time_params = read_params("temporal_rules_spec.md")
        self.dep_params = read_params("dependency_admission_spec.md")
        self.attest_params = read_params("attestation_authority_spec.md")
        self.budget_params = read_params("budget_reservation_spec.md")
        self.metric_params = read_params("metrics_definitions_spec.md")
        self.runbook_params = read_params("operations_runbook_spec.md")
        self.artifact_params = read_params("artifact_contract_spec.md")
        self.scenario_params = read_params("scenario_definitions_spec.md")
        self.notes_params = read_params("operator_notes.md")
        grammar = read_json("revision_grammar.json")
        GRAMMAR_FIELDS = list(grammar["compare_fields"])
        LADDER = self.ladder_params["ladder"].split(",")
        self.ladder = LADDER
        self.registry_sites = read_blocks("site_registry.yaml")
        self.horizon = read_json("horizon_config.json")
        self.policy = read_json("relay_policy_baseline.json")
        codes = read_json("reason_code_registry.json")["codes"]
        self.order = dict((c["code"], c["order"]) for c in codes)
        self.decision_of = dict((c["code"], c["decision"]) for c in codes)
        self.suffixes = read_json("platform_suffixes.json")["suffixes"]
        self.risk = read_json("risk_tier_table.json")
        self.overrides = read_json("site_overrides.json")["overrides"]
        self.bulletins = read_json("release_bulletins.json")["bulletins"]
        self.directives = read_json("quarantine_directives.json")["directives"]
        self.grants = read_json("delegation_grants.json")["grants"]
        self.carry_policy = read_json("carry_forward_policy.json")
        self.overlays = read_json("scenario_overlays.json")["scenarios"]
        ini = configparser.ConfigParser()
        ini.read(os.path.join(DATA, "channel_budgets.ini"))
        self.budgets: Dict[str, Dict[str, int]] = {}
        for channel in LADDER:
            section = ini[channel]
            budget = int(section["budget"])
            first = int(section["reserved_tier1"])
            second = int(section["reserved_tier2"])
            floor = int(self.budget_params["general_pool_floor"])
            if "rollback_reserve_charge" in section:
                hold = int(section["rollback_reserve_charge"])
            elif self.budget_params["rollback_hold_fallback"] == "per_member_doubled":
                hold = 2 * int(self.policy["rollback_reserve_per_member"])
            else:
                hold = int(self.policy["rollback_reserve_per_member"])
            self.budgets[channel] = {"tier1": first, "tier2": second,
                                     "published_tier2": second, "hold": hold,
                                     "general": max(floor, budget - first - second)}
        self.calendar = read_blocks("business_calendar.yaml")
        self.catalog: Dict[str, List[Dict[str, str]]] = {}
        for row in read_csv("unit_catalog.csv"):
            self.catalog.setdefault(row["unit_key"], []).append(row)
        self.alias: Dict[str, List[Dict[str, str]]] = {}
        for row in read_csv("alias_bindings.csv"):
            self.alias.setdefault(row["content_ref"], []).append(row)
        self.attestations: Dict[str, List[Dict[str, Any]]] = {}
        for row in read_jsonl("builder_attestations.jsonl"):
            self.attestations.setdefault(row["content_ref"], []).append(row)
        self.snapshot = read_csv("channel_membership_snapshot.csv")
        self.mirrors = dict((c, read_tsv("mirror_index_%s.tsv" % c)) for c in LADDER)
        self.requests = read_jsonl(self.index_params["request_table"])
        self.withdrawals: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for row in read_jsonl("withdrawal_notices.jsonl"):
            self.withdrawals.setdefault((row["unit_key"], row["revision"]), []).append(row)
        self.embargoes: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        self.embargo_by_id: Dict[str, Dict[str, Any]] = {}
        for row in read_jsonl("embargo_records.jsonl"):
            self.embargoes.setdefault((row["unit_key"], row["revision"]), []).append(row)
            self.embargo_by_id[row["embargo_id"]] = row
        self.chains: Dict[str, List[Dict[str, str]]] = {}
        for row in read_csv("supersession_chains.csv"):
            self.chains.setdefault(row["superseded_embargo_id"], []).append(row)
        self.central: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for row in read_jsonl("integrity_reports_central.jsonl"):
            self.central.setdefault((row["unit_key"], row["revision"]), []).append(row)
        self.site_verdicts: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
        for row in read_csv("qa_verdicts_site.csv"):
            self.site_verdicts.setdefault((row["unit_key"], row["revision"]), []).append(row)
        self.freezes: Dict[Tuple[str, str, str], List[Dict[str, str]]] = {}
        for row in read_csv("site_freeze_windows.csv"):
            self.freezes.setdefault((row["site"], row["channel"], row["family"]), []).append(row)
        self.holds: Dict[Tuple[str, str, str], List[Dict[str, str]]] = {}
        for row in read_csv("recurring_holds.csv"):
            self.holds.setdefault((row["site"], row["channel"], row["family"]), []).append(row)
        self.exceptions: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
        for row in read_csv("hold_exceptions.csv"):
            self.exceptions.setdefault((row["hold_id"], row["occurrence_date"]), []).append(row)
        self.offsets: Dict[str, List[Tuple[str, int]]] = {}
        for row in read_csv("site_clock_offsets.csv"):
            self.offsets.setdefault(row["site"], []).append(
                (row["from_instant"], int(row["utc_offset_minutes"])))
        for site in self.offsets:
            self.offsets[site].sort()
        self.seals: Dict[str, List[Tuple[str, str]]] = {}
        with open(os.path.join(DATA, "relay_audit.log"), "r", encoding="utf-8") as handle:
            for line in handle:
                fields: Dict[str, str] = {}
                for part in line.split():
                    if "=" in part and not part.startswith("detail"):
                        key, value = part.split("=", 1)
                        fields[key] = value
                if fields.get("event") != "SEAL":
                    continue
                self.seals.setdefault(fields.get("channel", ""), []).append(
                    (line.split()[0], fields.get("status", "")))
        self.primary: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
        for row in read_csv("unit_revision_requires.csv"):
            self.primary.setdefault((row["unit_key"], row["revision"]), []).append(row)
        self.legacy: Dict[Tuple[str, str], List[Dict[str, str]]] = {}
        for row in read_tsv("dependency_declarations_legacy.tsv"):
            self.legacy.setdefault((row["unit_key"], row["revision"]), []).append(row)
        self.prior: Dict[Tuple[str, str, str], List[str]] = {}
        for row in read_csv("prior_cycle_decisions.csv"):
            self.prior.setdefault((row["cycle_id"], row["unit_key"],
                                   row["target_channel"]), []).append(row["decision"])
        self.carry: Dict[Tuple[str, str], Dict[str, str]] = {}
        for row in read_csv("carry_forward_state.csv"):
            if row["as_of_cycle"] == self.carry_policy["as_of_cycle"]:
                self.carry[(row["unit_key"], row["target_channel"])] = row
        self.waivers: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
        for row in read_jsonl("waiver_records.jsonl"):
            self.waivers.setdefault((row["site"], row["family"], row["channel"]), []).append(row)
        bounds = read_json("boundary_semantics.json")
        self.bounds: Dict[str, str] = dict(bounds["comparisons"])
        self.census_scope: Dict[str, str] = dict(bounds["census_scope"])
        self.scopes = set(self.policy["requirement_scopes_in_force"])
        self.trusted = set(self.policy["trusted_builders"])
        self.precedence = list(self.policy["builder_precedence"])
        ini_cap = configparser.ConfigParser()
        ini_cap.read(os.path.join(DATA, "channel_budgets.ini"))
        self.batch_limit = int(ini_cap["defaults"]["advisory_cap"]) // len(LADDER)
        self.cooldown = int(self.notes_params["reseal_cooldown_hours"])
        self.inputs_seen = len([n for n in os.listdir(DATA)
                                if os.path.isfile(os.path.join(DATA, n))])

    def offset_at(self, site: str, moment: datetime) -> int:
        stamp = show_instant(moment)
        found = 0
        for from_instant, minutes in self.offsets.get(site, []):
            if from_instant <= stamp:
                found = minutes
        return found

    def local_of(self, site: str, moment: datetime) -> datetime:
        return moment + timedelta(minutes=self.offset_at(site, moment))

    def label_unit(self, label: str) -> Optional[str]:
        body = label
        for suffix in self.suffixes:
            if body.endswith(suffix):
                body = body[: -len(suffix)]
                break
        parts = body.split(self.identity_params["label_separator"])
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return None
        joiner = self.identity_params["unit_separator"]
        return parts[0].lower() + joiner + parts[1].lower()

    def membership(self) -> Dict[str, Dict[str, str]]:
        current = max(int(row["snapshot_seq"]) for row in self.snapshot)
        seating: Dict[str, Dict[str, str]] = dict((c, {}) for c in LADDER)
        for row in self.snapshot:
            if (int(row["snapshot_seq"]) == current
                    and row["state"] == self.ladder_params["membership_state"]):
                seating[row["channel"]][row["unit_key"]] = row["revision"]
        return seating

    def seated(self, cut: str) -> Dict[str, Dict[str, str]]:
        seating = self.membership()
        out: Dict[str, Dict[str, str]] = {}
        for channel in LADDER:
            best: Dict[str, str] = {}
            for row in self.mirrors[channel]:
                if (row["state"] != self.ladder_params["mirror_state"]
                        or row["published_at"] > cut):
                    continue
                unit = self.label_unit(row["label"])
                if unit is None:
                    continue
                held = best.get(unit)
                if held is None or revision_tuple(row["revision"]) > revision_tuple(held):
                    best[unit] = row["revision"]
            out[channel] = dict((u, best.get(u, r)) for u, r in seating[channel].items())
        return out

    def waiver_expiry(self, site: str, effective: str, span: int) -> datetime:
        block = self.calendar.get(self.registry_sites[site]["calendar"], {})
        weekend = set(block.get("weekend_days", []))
        holidays = set(block.get("holidays", []))
        local = self.local_of(site, parse_instant(effective))
        day = local.replace(hour=0, minute=0, second=0, microsecond=0)
        counted = 0
        while True:
            stamp = day.strftime("%Y-%m-%d")
            if WEEKDAY_NAMES[day.weekday()] not in weekend and stamp not in holidays:
                counted += 1
                if counted >= span:
                    break
            day = day + timedelta(days=1)
        closing = day + timedelta(days=1)
        return closing - timedelta(minutes=self.offset_at(site, closing))


class Candidate(object):
    __slots__ = ("request_id", "content_ref", "unit", "family", "revision",
                 "channel", "site", "tier", "owner", "requires", "release",
                 "code", "escalated_from", "pool", "draw")

    def __init__(self, row: Dict[str, Any]) -> None:
        self.request_id = row["request_id"]
        self.content_ref = row["content_ref"]
        self.revision = row["revision"]
        self.channel = row["target_channel"]
        self.site = row["site"]
        self.unit: Optional[str] = None
        self.family: Optional[str] = None
        self.tier: Optional[str] = None
        self.owner: Optional[str] = None
        self.requires: List[Tuple[str, str]] = []
        self.release: Optional[str] = None
        self.code: Optional[str] = None
        self.escalated_from: Optional[str] = None
        self.pool: Optional[str] = None
        self.draw: int = 0


def governing_requests(ev: Evidence) -> List[Dict[str, Any]]:
    field = ev.horizon["horizon_field"]
    best: Dict[str, Tuple[Tuple[str, int], Dict[str, Any]]] = {}
    for row in ev.requests:
        stamp = row[field]
        if not ev.horizon["horizon_start"] <= stamp < ev.horizon["horizon_end"]:
            continue
        mark = (row["recorded_at"], int(row[ev.rule_params["request_priority_field"]]))
        held = best.get(row["request_id"])
        if held is None or mark >= held[0]:
            best[row["request_id"]] = (mark, row)
    return [best[key][1] for key in sorted(best)]


def resolve_unit(ev: Evidence, reference: str, cut: str) -> Optional[str]:
    live = [r for r in ev.alias.get(reference, [])
            if not r["retired_at"] or r["retired_at"] > cut]
    winner = governing(live, "binding_id", cut)
    if winner is not None:
        return winner["unit_key"]
    behind = len(ev.precedence)

    def rank(row: Dict[str, Any]) -> Tuple[str, int, str]:
        standing = (ev.precedence.index(row["builder"])
                    if row["builder"] in ev.precedence else behind)
        return (row["signed_at"], -standing, row["attestation_id"])

    filed = [r for r in ev.attestations.get(reference, [])
             if r["builder"] in ev.trusted]
    for row in sorted(filed, key=rank, reverse=True):
        parts = row["source_name"].split(ev.identity_params["source_name_separator"])
        if len(parts) == 2 and parts[0] and parts[1]:
            return parts[0] + ev.identity_params["unit_separator"] + parts[1]
    return None


def embargo_release(ev: Evidence, unit: str, revision: str, cut: str) -> Optional[str]:
    record = governing(ev.embargoes.get((unit, revision), []), "embargo_id", cut)
    seen: set = set()
    while record is not None and record["embargo_id"] not in seen:
        seen.add(record["embargo_id"])
        chain = governing(ev.chains.get(record["embargo_id"], []), "chain_id", cut)
        if chain is None:
            return record["release_instant"]
        record = ev.embargo_by_id.get(chain["superseding_embargo_id"])
    return None if record is None else record["release_instant"]


def chain_ends_in_void(ev: Evidence, unit: str, revision: str, cut: str) -> bool:
    """True when the chain embargo_release follows names a replacement no record holds."""
    record = governing(ev.embargoes.get((unit, revision), []), "embargo_id", cut)
    seen: set = set()
    while record is not None and record["embargo_id"] not in seen:
        seen.add(record["embargo_id"])
        chain = governing(ev.chains.get(record["embargo_id"], []), "chain_id", cut)
        if chain is None:
            return False
        record = ev.embargo_by_id.get(chain["superseding_embargo_id"])
        if record is None:
            return True
    return False


def attestation_clears(ev: Evidence, cand: Candidate, cut: str,
                       opts: Dict[str, bool]) -> bool:
    filed = [r for r in ev.central.get((cand.unit, cand.revision), []) if r["verdict"]]
    central = governing(filed, "report_id", cut)
    if central is None:
        return False
    verdict = central["verdict"]
    if not opts.get("no_grants"):
        held = [g for g in ev.grants
                if g["site"] == cand.owner and g["family"] == cand.family]
        grant = governing(held, "grant_id", cut)
        if grant is not None and grant["status"] == "active":
            owned = [r for r in ev.site_verdicts.get((cand.unit, cand.revision), [])
                     if r["site"] == cand.owner]
            local = governing(owned, "verdict_id", cut)
            if local is not None and local["effective_at"] > central["effective_at"]:
                verdict = local["verdict"]
    if verdict == "pass":
        return True
    if verdict == "indeterminate" and not opts.get("strict"):
        return cand.channel != ev.attest_params["indeterminate_blocked_channel"]
    return False


def tier_allowed(ev: Evidence, cand: Candidate, cut: str,
                 opts: Dict[str, bool]) -> bool:
    allowed = set(ev.risk["channel_risk_tiers"][cand.channel])
    for rule in ev.overrides:
        if rule["site"] == cand.site and rule["channel"] == cand.channel:
            allowed -= set(rule["deny_risk_tiers"])
    if not opts.get("ignore_bulletins"):
        same = [b for b in ev.bulletins
                if b["action"] == "allow_risk_tier" and b["channel"] == cand.channel
                and b["family"] == cand.family and b["risk_tier"] == cand.tier]
        winner = governing(same, "bulletin_id", cut)
        if winner is not None and winner["status"] == "active":
            allowed.add(cand.tier)
    return cand.tier in allowed


def quarantine_floored(ev: Evidence, cand: Candidate, cut: str) -> bool:
    for scope in ("any", cand.channel):
        same = [d for d in ev.directives
                if d["scope_family"] == cand.family and d["scope_channel"] == scope]
        winner = governing(same, "directive_id", cut)
        if winner is None or winner["status"] != "active":
            continue
        if revision_tuple(cand.revision) < revision_tuple(winner["floor_revision"]):
            return True
    return False


def cooldown_closed(ev: Evidence, channel: str, cut: str) -> bool:
    stamps = [s for s, status in ev.seals.get(channel, [])
              if status != "rolled_back" and s <= cut]
    if not stamps:
        return False
    return parse_instant(cut) - parse_instant(max(stamps)) < timedelta(hours=ev.cooldown)


def waiver_lifts(ev: Evidence, cand: Candidate, cut: str) -> bool:
    winner = governing(ev.waivers.get((cand.site, cand.family, cand.channel), []),
                       "waiver_id", cut)
    if winner is None:
        return False
    expiry = ev.waiver_expiry(cand.site, winner["effective_at"],
                              int(winner["expires_after_business_days"]))
    return parse_instant(cut) < expiry


def freeze_covers(ev: Evidence, cand: Candidate, cut: str) -> bool:
    local = ev.local_of(cand.site, parse_instant(cut))
    flavour = cand.unit.split("/")[1]
    for row in ev.freezes.get((cand.site, cand.channel, cand.family), []):
        if row["status"] != "active" or row["flavour"] not in (flavour, "*"):
            continue
        start = datetime.strptime(row["start_local"], "%Y-%m-%dT%H:%M:%S")
        start = start.replace(tzinfo=timezone.utc)
        span = {ev.time_params["freeze_length_unit"]: int(row["hold_len"])}
        if start <= local < start + timedelta(**span):
            return True
    return False


def hold_covers(ev: Evidence, cand: Candidate, cut: str) -> bool:
    local = ev.local_of(cand.site, parse_instant(cut))
    today = local.strftime("%Y-%m-%d")
    flavour = cand.unit.split("/")[1]
    for row in ev.holds.get((cand.site, cand.channel, cand.family), []):
        if row["flavour"] not in (flavour, "*"):
            continue
        if not row["from_date"] <= today < row["until_date"]:
            continue
        if int(row["weekday"]) != local.weekday():
            continue
        hour, minute, second = (int(p) for p in row["start_local"].split(":"))
        start = local.replace(hour=hour, minute=minute, second=second, microsecond=0)
        dropped = False
        for change in ev.exceptions.get((row["hold_id"], today), []):
            if change["action"] == "cancel":
                dropped = True
            elif change["action"] == "shift":
                start = start + timedelta(minutes=int(change["shift_minutes"]))
        if dropped:
            continue
        span = {ev.time_params["hold_length_unit"]: int(row["hold_len"])}
        if start <= local < start + timedelta(**span):
            return True
    return False


def requirements_of(ev: Evidence, unit: str, revision: str) -> List[Tuple[str, str]]:
    primary = ev.primary.get((unit, revision))
    if primary is not None:
        return [(r["requires_unit_key"], r["min_revision"]) for r in primary
                if r["scope"] in ev.scopes]
    return [(r["requires_unit_key"], r["min_revision"])
            for r in ev.legacy.get((unit, revision), [])]


def met(seating: Dict[str, str], cohort: Dict[str, str], unit: str,
        minimum: str) -> bool:
    for pool in (seating, cohort):
        held = pool.get(unit)
        if held is not None and revision_tuple(held) >= revision_tuple(minimum):
            return True
    return False


def closed_rings(edges: Dict[str, List[str]]) -> set:
    """Every node that sits on a closed ring of the given edges."""
    index: Dict[str, int] = {}
    low: Dict[str, int] = {}
    on_stack: Dict[str, bool] = {}
    stack: List[str] = []
    counter = [0]
    caught: set = set()

    def visit(root: str) -> None:
        work: List[Tuple[str, int]] = [(root, 0)]
        while work:
            node, step = work.pop()
            if step == 0:
                index[node] = low[node] = counter[0]
                counter[0] += 1
                stack.append(node)
                on_stack[node] = True
            moved = False
            for position in range(step, len(edges.get(node, []))):
                nxt = edges[node][position]
                if nxt not in index:
                    work.append((node, position + 1))
                    work.append((nxt, 0))
                    moved = True
                    break
                if on_stack.get(nxt):
                    low[node] = min(low[node], index[nxt])
            if moved:
                continue
            for nxt in edges.get(node, []):
                if nxt in low and index.get(nxt, 0) > index[node]:
                    low[node] = min(low[node], low[nxt])
            if low[node] == index[node]:
                group: List[str] = []
                while True:
                    member = stack.pop()
                    on_stack[member] = False
                    group.append(member)
                    if member == node:
                        break
                if len(group) > 1:
                    caught.update(group)
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])

    for node in sorted(edges):
        if node not in index:
            visit(node)
    return caught


def bound_pairs(cand: Candidate, held: List[Candidate],
                standing: Dict[str, str]) -> set:
    """Unit pairs whose rollback cover this admission completes."""
    found = set()
    for other in held:
        for unit, minimum in cand.requires:
            if (unit == other.unit
                    and revision_tuple(other.revision) >= revision_tuple(minimum)
                    and not met(standing, {}, unit, minimum)):
                found.add(tuple(sorted((cand.unit, other.unit))))
        for unit, minimum in other.requires:
            if (unit == cand.unit
                    and revision_tuple(cand.revision) >= revision_tuple(minimum)
                    and not met(standing, {}, unit, minimum)):
                found.add(tuple(sorted((other.unit, cand.unit))))
    return found


def serves_others(cand: Candidate, pool: List[Candidate]) -> int:
    """Requirement rows held by other admitted requests that this one meets."""
    total = 0
    for other in pool:
        if other is cand or other.channel != cand.channel:
            continue
        for unit, minimum in other.requires:
            if unit == cand.unit and revision_tuple(cand.revision) >= revision_tuple(minimum):
                total += 1
    return total


def adjudicate(ev: Evidence, cut: str, opts: Dict[str, bool]) -> Dict[str, Any]:
    seated = ev.seated(cut)
    horizon_end = ev.horizon["horizon_end"]
    cands: List[Candidate] = []
    for row in governing_requests(ev):
        cand = Candidate(row)
        cand.unit = resolve_unit(ev, cand.content_ref, cut)
        if cand.unit is None:
            cand.code = "alias_unresolved"
            cands.append(cand)
            continue
        cand.family = cand.unit.split("/")[0]
        entry = governing(ev.catalog.get(cand.unit, []), "catalog_row_id", cut)
        cand.tier = entry["risk_tier"] if entry is not None else "tier3"
        cand.owner = entry["owning_site"] if entry is not None else cand.site
        cand.requires = requirements_of(ev, cand.unit, cand.revision)
        cands.append(cand)
    for cand in cands:
        if cand.code is not None:
            continue
        hits: List[str] = []
        head = -1
        for index, channel in enumerate(LADDER):
            if cand.unit in seated[channel]:
                head = index
        here = LADDER.index(cand.channel)
        if head < 0:
            if here != 0:
                hits.append("channel_not_adjacent")
        elif here not in (head, head + 1):
            hits.append("channel_not_adjacent")
        standing = seated[cand.channel].get(cand.unit)
        if standing is not None and revision_tuple(standing) >= revision_tuple(cand.revision):
            hits.append("revision_regression")
        notice = governing(ev.withdrawals.get((cand.unit, cand.revision), []),
                           "notice_id", cut)
        if notice is not None and notice["status"] == "active":
            hits.append("withdrawn_revision")
        if quarantine_floored(ev, cand, cut):
            hits.append("quarantine_floor")
        cand.release = embargo_release(ev, cand.unit, cand.revision, cut)
        if cand.release is not None:
            if cand.release >= horizon_end:
                hits.append("embargo_active")
            elif cand.release > cut:
                hits.append("embargo_pending")
        if not attestation_clears(ev, cand, cut, opts):
            hits.append("attestation_failed")
        if not tier_allowed(ev, cand, cut, opts):
            hits.append("risk_tier_blocked")
        if cooldown_closed(ev, cand.channel, cut):
            hits.append("channel_cooldown")
        lifted = waiver_lifts(ev, cand, cut)
        if freeze_covers(ev, cand, cut) and not lifted:
            hits.append("freeze_window")
        if hold_covers(ev, cand, cut) and not lifted:
            hits.append("recurring_hold")
        if hits:
            cand.code = min(hits, key=lambda code: ev.order[code])
    alive = [c for c in cands if c.code is None]
    supplies: Dict[Tuple[str, str], Candidate] = {}
    for cand in alive:
        supplies[(cand.channel, cand.unit)] = cand
    # A requirement one co-candidate would meet is an edge. Any closed ring of
    # edges, of whatever length, refuses every member.
    edges: Dict[str, List[str]] = dict((c.request_id, []) for c in alive)
    for cand in alive:
        for unit, minimum in cand.requires:
            mate = supplies.get((cand.channel, unit))
            if mate is None or mate.request_id == cand.request_id:
                continue
            if revision_tuple(mate.revision) >= revision_tuple(minimum):
                edges[cand.request_id].append(mate.request_id)
    cycled = closed_rings(edges)
    for cand in alive:
        if cand.request_id in cycled:
            cand.code = "cycle_unresolved"
    alive = [c for c in cands if c.code is None]
    cohort: Dict[str, Dict[str, str]] = dict((c, {}) for c in LADDER)
    for cand in alive:
        held = cohort[cand.channel].get(cand.unit)
        if held is None or revision_tuple(cand.revision) > revision_tuple(held):
            cohort[cand.channel][cand.unit] = cand.revision
    for cand in alive:
        for unit, minimum in cand.requires:
            if not met(seated[cand.channel], cohort[cand.channel], unit, minimum):
                cand.code = "missing_dependency"
                break
    alive = [c for c in cands if c.code is None]
    opening = ev.horizon["horizon_start"]
    holders: List[Candidate] = []
    floor = int(ev.budget_params["reserved_tier2_floor"])
    pairs_by_channel: Dict[str, int] = {}
    holds_by_channel: Dict[str, int] = {}
    settled: Dict[str, Dict[str, int]] = {}
    drawn_by_channel: Dict[str, Dict[str, int]] = {}
    refused_cover: Dict[str, int] = {}
    refused_empty: Dict[str, int] = {}
    for channel in LADDER:
        pools = dict(ev.budgets[channel])
        hold = pools["hold"]
        drawn: Dict[str, int] = {"tier1": 0, "tier2": 0, "general": 0}
        refused_cover[channel] = 0
        refused_empty[channel] = 0
        charged: set = set()
        here: List[Candidate] = []
        ranked = sorted([c for c in alive if c.channel == channel],
                        key=lambda c: (TIER_RANK[c.tier], c.release or opening, c.unit))
        for cand in ranked:
            name = None
            if pools.get(cand.tier, 0) > 0:
                name = cand.tier
            elif pools["general"] > 0:
                name = "general"
            if name is None:
                cand.code = "budget_exhausted"
                refused_empty[channel] += 1
                continue
            fresh = bound_pairs(cand, here, seated[channel]) - charged
            need = len(fresh) * hold
            spare = pools["tier2"] - (1 if name == "tier2" else 0)
            if spare - need < floor:
                cand.code = "budget_exhausted"
                refused_cover[channel] += 1
                continue
            pools[name] -= 1
            pools["tier2"] -= need
            charged |= fresh
            drawn[name] += 1
            cand.pool = name
            cand.draw = drawn[name]
            here.append(cand)
            holders.append(cand)
        pairs_by_channel[channel] = len(charged)
        holds_by_channel[channel] = len(charged) * hold
        drawn_by_channel[channel] = dict(drawn)
        settled[channel] = {"tier1": pools["tier1"], "tier2": pools["tier2"],
                            "general": pools["general"]}
    kept: Dict[str, Dict[str, str]] = dict((c, {}) for c in LADDER)
    for cand in holders:
        held = kept[cand.channel].get(cand.unit)
        if held is None or revision_tuple(cand.revision) > revision_tuple(held):
            kept[cand.channel][cand.unit] = cand.revision
    dropped_in_closure: List[str] = []
    evictions_per_pass: List[int] = []
    evicting_passes = 0
    for _pass in range(int(ev.dep_params["closure_pass_bound"])):
        lost = 0
        for cand in list(holders):
            for unit, minimum in cand.requires:
                if not met(seated[cand.channel], kept[cand.channel], unit, minimum):
                    cand.code = "missing_dependency"
                    holders.remove(cand)
                    dropped_in_closure.append(cand.request_id)
                    lost += 1
                    break
        if not lost:
            break
        evictions_per_pass.append(lost)
        evicting_passes += 1
        kept = dict((c, {}) for c in LADDER)
        for cand in holders:
            held = kept[cand.channel].get(cand.unit)
            if held is None or revision_tuple(cand.revision) > revision_tuple(held):
                kept[cand.channel][cand.unit] = cand.revision
    for cand in holders:
        cand.code = "ok"
    threshold = int(ev.carry_policy["escalation_carry_count"])
    cleared = ev.carry_policy["reset_flag_cleared_value"]
    excluded = ev.carry_policy["excluded_reason_code"]
    rewritten = ev.carry_policy["escalated_reason_code"]
    for cand in cands:
        if ev.decision_of[cand.code] != "deferred" or cand.code == excluded:
            continue
        state = ev.carry.get((cand.unit, cand.channel))
        if state is None:
            continue
        if int(state["carry_count"]) >= threshold and state["reset_flag"] != cleared:
            cand.escalated_from = cand.code
            cand.code = rewritten
    admitted = [c for c in cands if c.code == "ok"]
    order: List[Candidate] = []
    waiting = list(admitted)
    placed: Dict[Tuple[str, str], str] = {}
    while waiting:
        ready: List[Candidate] = []
        for cand in waiting:
            blocked = False
            for unit, minimum in cand.requires:
                if met(seated[cand.channel], {}, unit, minimum):
                    continue
                supplied = placed.get((cand.channel, unit))
                if supplied is not None and revision_tuple(supplied) >= revision_tuple(minimum):
                    continue
                blocked = True
            if not blocked:
                ready.append(cand)
        if not ready:
            ready = list(waiting)
        pick = sorted(ready, key=lambda c: (TIER_RANK[c.tier],
                                            -serves_others(c, admitted), c.unit))[0]
        order.append(pick)
        placed[(pick.channel, pick.unit)] = pick.revision
        waiting.remove(pick)
    return {"cut": cut, "cands": cands, "order": order,
            "closure_losses": dropped_in_closure,
            "closure_passes": evicting_passes,
            "rollback_pairs": pairs_by_channel,
            "rollback_holds": holds_by_channel,
            "settled_pools": settled,
            "drawn_by_channel": drawn_by_channel,
            "refused_cover": refused_cover,
            "refused_empty": refused_empty,
            "evictions_per_pass": evictions_per_pass}


def digest_of(ev: Evidence, order: List[Candidate]) -> str:
    fields = ev.metric_params["digest_fields"].split(",")
    rows = []
    for cand in order:
        carried = {"unit_key": cand.unit, "revision": cand.revision,
                   "target_channel": cand.channel, "pool": cand.pool or "",
                   "draw_index": str(cand.draw)}
        rows.append("|".join(carried[name] for name in fields))
    body = "\n".join(rows)
    width = int(ev.metric_params["digest_chars"])
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:width]


def counts_of(ev: Evidence, cands: List[Candidate]) -> Dict[str, int]:
    tally: Dict[str, int] = {}
    for cand in cands:
        tally[cand.code] = tally.get(cand.code, 0) + 1
    return dict(sorted(tally.items(), key=lambda pair: ev.order[pair[0]]))


def largest_remainder(parts: Dict[str, int], total: int, places: int) -> Dict[str, float]:
    scale = 100 * (10 ** places)
    if total <= 0:
        return dict((key, 0.0) for key in parts)
    raw = dict((k, Decimal(v) * Decimal(scale) / Decimal(total)) for k, v in parts.items())
    floors = dict((k, int(v)) for k, v in raw.items())
    spare = scale - sum(floors.values())
    ranked = sorted(parts, key=lambda k: (-(raw[k] - floors[k]), k))
    for key in ranked[:spare]:
        floors[key] += 1
    return dict((k, float(Decimal(v) / Decimal(10 ** places))) for k, v in floors.items())


def drive_service(ev: Evidence, order: List[Candidate]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    base = ev.horizon["service_base_url"]
    limit = ev.batch_limit
    actor = ev.horizon["actor"]
    process = subprocess.Popen(
        [sys.executable, os.path.join(SERVICE, "relay_service.py"),
         "--host", "127.0.0.1", "--port", base.rsplit(":", 1)[1], "--data", DATA],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(160):
            try:
                urllib.request.urlopen(base + "/health", timeout=2).read()
                break
            except Exception:
                time.sleep(0.25)

        def call(body: Dict[str, Any]) -> Dict[str, Any]:
            request = urllib.request.Request(
                base + "/apply", data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request, timeout=90) as answer:
                return json.loads(answer.read().decode("utf-8"))

        batches: List[List[Dict[str, Any]]] = []
        for index in range(0, len(order), limit):
            batches.append([{"op": "promote", "unit_key": c.unit,
                             "revision": c.revision, "target_channel": c.channel,
                             "requires": [list(pair) for pair in c.requires]}
                            for c in order[index:index + limit]])
        batches.append([{"op": "seal", "channel": channel} for channel in LADDER])
        keys: List[str] = []
        submitted = 0
        accepted = 0
        opener: Optional[Dict[str, Any]] = None
        aborted = 0
        for number, ops in enumerate(batches, start=1):
            key = "rc2411-call-%02d" % number
            body = {"ops": ops, "actor": actor, "idempotency_key": key}
            if opener is None:
                opener = body
            answer = call(body)
            keys.append(key)
            submitted += len(ops)
            accepted += int(answer.get("accepted", 0))
            if answer.get("reason") == "adjudication_error":
                aborted += 1
        replayed = 0
        for _again in range(int(ev.runbook_params["replay_count"])):
            if opener is not None:
                call(opener)
                replayed += 1
        with urllib.request.urlopen(base + "/state", timeout=30) as answer:
            state = json.loads(answer.read().decode("utf-8"))
        summary = {
            "actor": actor,
            "endpoint": base + "/apply",
            "batch_limit": limit,
            "calls": len(batches),
            "replayed_calls": replayed,
            "ops_submitted": submitted,
            "ops_accepted": accepted,
            "ops_rejected": submitted - accepted,
            "seal_ops": len(LADDER),
            "aborted_calls": aborted,
            "final_op_seq": int(state["op_seq"]),
            "idempotency_keys": keys,
        }
        return state, summary
    finally:
        process.terminate()
        process.wait(timeout=20)


def write_artifact(ev: Evidence, name: str, payload: Any) -> None:
    indent = int(ev.artifact_params["json_indent"])
    with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, indent=indent))
        handle.write("\n")


def closing_report(ev: Evidence, cut: str, base: Dict[str, Any]) -> None:
    """Print the ten counts the operator message carries, each with its source."""
    drawn = base["drawn_by_channel"]
    settled = base["settled_pools"]
    cover = base["refused_cover"]
    empty = base["refused_empty"]
    passes = list(base["evictions_per_pass"]) + [0, 0, 0]
    scope = ev.census_scope

    def per_channel(values: Dict[str, int]) -> str:
        return ", ".join("%s %d" % (c, values[c]) for c in LADDER)

    def draws(channel: str) -> str:
        return "tier one %d, tier two %d, general %d" % (
            drawn[channel]["tier1"], drawn[channel]["tier2"], drawn[channel]["general"])

    def offered(channel: str) -> int:
        return sum(drawn[channel].values())

    void = sorted(c.request_id for c in base["cands"]
                  if c.unit is not None and chain_ends_in_void(ev, c.unit, c.revision, cut))
    lines = [
        "[relay-gate] cycle %s closed. Ten counts for the operator:" % ev.policy["cycle_id"],
        "1 edge draws: %s; seats offered before revalidation %d"
        % (draws("edge"), offered("edge")),
        "2 canary draws: %s; seats offered before revalidation %d"
        % (draws("canary"), offered("canary")),
        "3 staging draws: %s; seats offered on stable %d" % (draws("staging"), offered("stable")),
        "4 bound pairs that drew rollback cover (%s): %s"
        % (scope["rollback_pairs"], per_channel(base["rollback_pairs"])),
        "5 size of one rollback hold: %s" % per_channel(dict((c, ev.budgets[c]["hold"])
                                                            for c in LADDER)),
        "6 tier two reserve left: %s" % per_channel(dict((c, settled[c]["tier2"])
                                                        for c in LADDER)),
        "7 general pool left: %s" % per_channel(dict((c, settled[c]["general"])
                                                    for c in LADDER)),
        "8 tier one reserve left: %s" % per_channel(dict((c, settled[c]["tier1"])
                                                        for c in LADDER)),
        "9 refused for want of cover both ways %d, refused at an empty pool %d; "
        "cover refusals in canary %d, in staging %d"
        % (sum(cover.values()), sum(empty.values()), cover["canary"], cover["staging"]),
        "10 holders evicted (%s): first pass %d, second pass %d, third pass %d, "
        "whole cycle %d; passes that evicted somebody (%s) %d"
        % (scope["closure_losses"], passes[0], passes[1], passes[2],
           len(base["closure_losses"]), scope["closure_passes"], base["closure_passes"]),
        "Sources: counts 1 to 3 and 6 to 9 come from the capacity draw run over the pools in "
        "channel_budgets.ini under budget_reservation_spec.md; count 4 pairs requests through "
        "unit_revision_requires.csv against the seating read from "
        "channel_membership_snapshot.csv and the mirror_index files; count 5 is the "
        "rollback_reserve_charge in channel_budgets.ini, or twice rollback_reserve_per_member "
        "in relay_policy_baseline.json where a channel publishes no charge; count 10 comes "
        "from the closure passes of dependency_admission_spec.md. The scopes of counts 4 and "
        "10 are the census_scope entries of boundary_semantics.json.",
        "Derived in full: all ten counts above, by the rules as written.",
        "Settled on balance, kept apart: %d requests reach a supersession_chains.csv row "
        "whose replacement embargo embargo_records.jsonl does not hold (%s). The chain was "
        "followed as written, so those requests carry no embargo; setting the void row aside "
        "instead would leave the original embargo in force and defer them."
        % (len(void), ", ".join(void) if void else "none"),
        "Left unsettled: nothing.",
    ]
    for line in lines:
        print(line)


def main() -> int:
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    ev = Evidence()
    cut = ev.horizon["decision_instant"]
    base = adjudicate(ev, cut, {})
    cands = base["cands"]
    order = base["order"]
    admitted = [c for c in cands if c.code == "ok"]
    deferred = [c for c in cands if ev.decision_of[c.code] == "deferred"]
    rejected = [c for c in cands if ev.decision_of[c.code] == "rejected"]
    withdrawn = [c for c in cands if c.code == "withdrawn_revision"]
    escalated = [c for c in cands if c.escalated_from]
    audit = len(cands)
    divisor = audit - len(withdrawn)
    rate = 0.0
    if divisor > 0:
        places = int(ev.metric_params["rate_places"])
        rate = float((Decimal(len(admitted)) / Decimal(divisor)).quantize(
            Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))
    by_channel = dict((channel, 0) for channel in LADDER)
    for cand in admitted:
        by_channel[cand.channel] += 1
    prior = ev.policy["prior_cycle_id"]
    repeats = set()
    for cand in deferred:
        if "deferred" in ev.prior.get((prior, cand.unit, cand.channel), []):
            repeats.add(cand.unit)
    write_artifact(ev, "report.json", {
        "cycle_id": ev.policy["cycle_id"],
        "decision_instant": cut,
        "audit_count": audit,
        "decisions": [{
            "request_id": c.request_id,
            "unit_key": c.unit or "",
            "revision": c.revision,
            "target_channel": c.channel,
            "site": c.site,
            "risk_tier": c.tier or "",
            "decision": ev.decision_of[c.code],
            "reason_code": c.code,
        } for c in sorted(cands, key=lambda c: c.request_id)],
        "reason_code_counts": counts_of(ev, cands),
        "escalations": [{"unit_key": c.unit, "original_reason_code": c.escalated_from}
                        for c in sorted(escalated, key=lambda c: c.unit)],
        "unresolved": [{"unit_key": c.unit, "revision": c.revision,
                        "reason_code": c.code}
                       for c in sorted([c for c in cands if c.code == "embargo_pending"],
                                       key=lambda c: (c.unit, c.revision))],
        "admission_order": ["%s|%s|%s" % (c.unit, c.revision, c.channel) for c in order],
    })
    write_artifact(ev, "summary.json", {
        "cycle_id": ev.policy["cycle_id"],
        "inputs_seen": ev.inputs_seen,
        "audit_count": audit,
        "admitted_total": len(admitted),
        "deferred_total": len(deferred),
        "rejected_total": len(rejected),
        "withdrawn_excluded": len(withdrawn),
        "escalated_total": len(escalated),
        "admission_rate": rate,
        "admitted_by_channel": by_channel,
        "coverage_share_pct": largest_remainder(
            by_channel, len(admitted), int(ev.metric_params["share_places"])),
        "repeat_deferral_count": len(repeats),
        "closure_passes": base["closure_passes"],
        "rollback_holds": sum(base["rollback_holds"].values()),
        "dependency_digest": digest_of(ev, order),
    })
    state, summary = drive_service(ev, order)
    write_artifact(ev, "final_state.json", state)
    write_artifact(ev, "transcript_summary.json", summary)
    for name in ("alpha", "beta"):
        overlay = [o for o in ev.overlays if o["name"] == name][0]
        moment = overlay["decision_instant"]
        opts = {} if name == "alpha" else {"ignore_bulletins": True, "no_grants": True}
        run = adjudicate(ev, moment, opts)
        rows = run["cands"]
        write_artifact(ev, "scenario_%s.json" % name, {
            "scenario": name,
            "decision_instant": moment,
            "audit_count": len(rows),
            "admitted_total": len([c for c in rows if c.code == "ok"]),
            "deferred_total": len([c for c in rows if ev.decision_of[c.code] == "deferred"]),
            "rejected_total": len([c for c in rows if ev.decision_of[c.code] == "rejected"]),
            "reason_code_counts": counts_of(ev, rows),
            "admitted_digest": digest_of(ev, run["order"]),
        })
    modes: Dict[str, Dict[str, int]] = {}
    mode_names = ev.scenario_params["mode_names"].split(",")
    for name in mode_names:
        opts = {"strict": True} if name == "strict" else {}
        rows = adjudicate(ev, cut, opts)["cands"]
        modes[name] = {
            "admitted_total": len([c for c in rows if c.code == "ok"]),
            "deferred_total": len([c for c in rows if ev.decision_of[c.code] == "deferred"]),
            "attestation_failed": len([c for c in rows if c.code == "attestation_failed"]),
        }
    write_artifact(ev, "scenario_mode.json", {
        "cycle_id": ev.policy["cycle_id"],
        "modes": modes,
        "delta": dict((key, modes[mode_names[0]][key] - modes[mode_names[1]][key])
                      for key in ("admitted_total", "deferred_total",
                                  "attestation_failed")),
    })
    closing_report(ev, cut, base)
    return 0


if __name__ == "__main__":
    sys.exit(main())
