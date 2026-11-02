#!/usr/bin/env python3
"""apportion_berth.py - berth-hour apportionment for the four-terminal port.

Reads --data <dir>, writes the nine contract documents into --out <dir>.
Standard library only, no network, byte-identical across reruns.
"""
from __future__ import annotations

import argparse
import configparser
import csv
import datetime as dt
import json
import pathlib
import re
import sys
from collections import defaultdict

TERMINALS = ["Alpha", "Bravo", "Charlie", "Delta"]
CYCLES = ["H%02d" % i for i in range(1, 27)]
CYCLE_IDX = {c: i for i, c in enumerate(CYCLES)}
WEATHER_CANDIDATES = ["SHEX", "SHINC", "WWD"]
REQUIRED_FILES = [
    "corpus_index.md", "source_manifest.md", "output_contract.md", "reason_codes.json",
    "unit_declarations.ini", "source_declarations.properties", "derivation_policy.ini",
    "vessel_master.csv", "charterer_master.csv", "charterer_alias_map.csv",
    "authority_roles.csv", "retraction_notices.csv", "terminal_capacity_declarations.csv",
    "substitution_factors.csv", "tide_tables.csv", "pilotage_windows.csv",
    "terminal_clock_marks.csv", "priority_register.csv", "commitment_agreements.csv",
    "commitment_exceptions.csv", "ceiling_register.csv",
    "fixed_width_intake_q1.txt", "fixed_width_intake_q2.txt",
    "registry_q1.tsv", "registry_q2.tsv", "registry_q3.tsv", "registry_q4.tsv",
    "state_events_p1.jsonl", "state_events_p2.jsonl", "state_events_p3.jsonl",
    "state_events_p4.jsonl", "state_events_p5.jsonl",
    "port_circulars_p1.jsonl", "port_circulars_p2.jsonl", "port_circulars_p3.jsonl",
    "approval_audit.log", "approval_audit.log.1", "approval_audit.log.2",
    "laytime_observations.log", "demurrage_settlement.log",
    "laytime_rules.md", "demurrage_rules.md", "priority_rules.md", "substitution_rules.md",
    "amendment_rules.md", "errata_2032-04.md", "legacy_terminal_handbook.md",
]
AUDIT_FILES = ["approval_audit.log", "approval_audit.log.1", "approval_audit.log.2"]
AUDIT_MARKERS = {
    "log_continuations": "log_continuation_marker",
    "header_gaps": "header_gap_marker",
    "null_forms": "null_form_marker",
    "duplicate_identical": "duplicate_identical_marker",
    "duplicate_conflicting": "duplicate_conflicting_marker",
    "cross_source_collapsed": "cross_source_collapsed_marker",
    "fold_disambiguated": "fold_disambiguated_marker",
    "gap_shifted": "gap_shifted_marker",
    "unknown_charterer_rows": "unknown_charterer_marker",
    "out_of_horizon_rows": "out_of_horizon_marker",
    "block_unit_rows": "block_unit_marker",
    "paren_negatives": "paren_negative_marker",
    "restatement_gaps": "restatement_gap_marker",
    "late_recorded": "late_recorded_marker",
    "late_dropped": "late_dropped_marker",
    "epoch_reassignments": "epoch_reassignment_marker",
    "substitution_hops": "substitution_hop_marker",
    "substitution_cycles": "substitution_cycle_marker",
    "no_qualified_berth": "no_qualified_berth_marker",
    "resets": "reset_marker",
}
STATE_MARKERS = {
    "stale_events": "stale_event_marker",
    "duplicate_version_events": "duplicate_version_marker",
    "illegal_transitions": "illegal_transition_marker",
}
CIRCULAR_MARKERS = {
    "circulars_applied": "circular_applied_marker",
    "circulars_unendorsed": "circular_unendorsed_marker",
    "circulars_early": "circular_early_marker",
    "circulars_retracted": "circular_retracted_marker",
    "circular_chains_unresolvable": "circular_chain_unresolvable_marker",
}
EXCEPTION_MARKERS = {
    "exceptions_applied": "exception_applied_marker",
    "exceptions_unendorsed": "exception_unendorsed_marker",
    "exceptions_retracted": "exception_retracted_marker",
}
DATA_QUALITY_TALLIES = [
    "header_gaps", "late_recorded", "null_forms", "duplicate_identical",
    "duplicate_conflicting", "cross_source_collapsed", "fold_disambiguated", "gap_shifted",
    "log_continuations", "unknown_charterer_rows", "out_of_horizon_rows", "block_unit_rows",
    "paren_negatives", "restatement_gaps",
]
POLICY_MARKER_TALLIES = [
    "substitution_hops", "substitution_cycles", "no_qualified_berth", "resets",
    "epoch_reassignments", "exceptions_applied", "exceptions_unendorsed",
    "exceptions_retracted", "illegal_transitions", "stale_events", "duplicate_version_events",
    "circulars_applied", "circulars_early", "circulars_unendorsed", "circulars_retracted",
    "circular_chains_unresolvable",
]


# ----------------------------------------------------------------------------- loading

def read_text(path: pathlib.Path) -> str:
    """Read one corpus file; a missing or unreadable file raises."""
    return path.read_text(encoding="utf-8")


def read_table(path: pathlib.Path, delimiter: str = ",") -> list[dict]:
    rows = list(csv.reader(read_text(path).splitlines(), delimiter=delimiter))
    header = rows[0]
    return [dict(zip(header, row)) for row in rows[1:] if row]


def read_ini(path: pathlib.Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    parser.read_string(read_text(path))
    return parser


def read_nor_logs(data: pathlib.Path) -> list[dict]:
    """The governing laytime is the first laytime_hours column, taken by position."""
    nors = []
    for path in sorted(data.glob("nor_log_*.csv")):
        rows = list(csv.reader(read_text(path).splitlines()))
        header = rows[0]
        laytime_col = header.index("laytime_hours")
        for row in rows[1:]:
            if not row:
                continue
            nors.append({
                "nor_ref": row[header.index("nor_ref")],
                "cycle": row[header.index("cycle")],
                "charterer": row[header.index("charterer")],
                "booked_berth": row[header.index("booked_berth")],
                "laytime_hours": int(row[laytime_col]),
                "recorded_instant": row[header.index("recorded_instant")],
            })
    if not nors:
        raise FileNotFoundError("no NOR log in %s" % data)
    return nors


def load_corpus(data: pathlib.Path) -> dict:
    for name in REQUIRED_FILES:
        if not (data / name).is_file():
            raise FileNotFoundError("missing source: %s" % (data / name))
    policy = read_ini(data / "derivation_policy.ini")
    unit = read_ini(data / "unit_declarations.ini")
    declared = {}
    for line in read_text(data / "source_declarations.properties").splitlines():
        if line.strip():
            key, value = line.split("=", 1)
            declared[key.strip().rsplit(".declared", 1)[0]] = int(value)
    ceiling_file = policy["precedence"]["ceiling_source"] + ".csv"
    return {
        "nors": read_nor_logs(data),
        "capacity": {(r["terminal"], r["cycle"]): int(r["capacity_hours"])
                     for r in read_table(data / "terminal_capacity_declarations.csv")},
        "segment": {r["canonical"]: r["segment"] for r in read_table(data / "charterer_master.csv")},
        "minimum": {(r["charterer"], r["terminal"]): int(r["minimum_hours"])
                    for r in read_table(data / "commitment_agreements.csv")},
        "ceiling": {(r["charterer"], r["terminal"]): int(r["ceiling_hours"])
                    for r in read_table(data / ceiling_file)},
        "rank": {r["charterer"]: int(r["rank"]) for r in read_table(data / "priority_register.csv")},
        "cutover": policy["cutover"]["april_2032"],
        "admission": policy["admission"]["instant"],
        "unit": int(unit["unit"]["berth_hours"]),
        "declared": declared,
        "weather": settle_weather(read_text(data / "laytime_observations.log")),
        "survival": settle_survival(read_text(data / "demurrage_settlement.log")),
        "markers": count_markers(data),
        "rows": count_source_rows(data),
    }


# ----------------------------------------------------------------------------- withheld rules

def _instant(text: str) -> dt.datetime:
    return dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")


def _hours(start: dt.datetime, end: dt.datetime, keep) -> int:
    count, hour = 0, start
    while hour < end:
        if keep(hour):
            count += 1
        hour += dt.timedelta(hours=1)
    return count


def counted_hours(convention: str, window: tuple, adverse: tuple) -> int:
    """Laytime hours one candidate convention counts inside an observed window."""
    def in_adverse(hour):
        return adverse[0] <= hour < adverse[1]
    rules = {
        "SHEX": lambda hour: hour.weekday() != 6,
        "SHINC": lambda hour: True,
        "WWD": lambda hour: not in_adverse(hour),
    }
    return _hours(window[0], window[1], rules[convention])


def settle_weather(text: str) -> str:
    pattern = re.compile(r"window=(\S+)/(\S+) adverse=(\S+)/(\S+) laytime_counted_hours=(\d+)")
    observations = []
    for line in text.splitlines():
        if line.strip():
            match = pattern.search(line)
            if match is None:
                raise ValueError("unreadable weather observation: %r" % line)
            w0, w1, a0, a1, counted = match.groups()
            observations.append(((_instant(w0), _instant(w1)), (_instant(a0), _instant(a1)), int(counted)))
    survivors = [c for c in WEATHER_CANDIDATES
                 if all(counted_hours(c, w, a) == n for w, a, n in observations)]
    if len(survivors) != 1:
        raise ValueError("weather-stoppage convention not settled: %r" % survivors)
    return survivors[0]


def settle_survival(text: str) -> int:
    """A lot raised in cycle r still stands at the opening of cycle r + g exactly when g <= N."""
    pattern = re.compile(r"lot_raised=(H\d\d) opening=(H\d\d) outcome=(CARRIED|EXPIRED)")
    carried, expired = [], []
    for line in text.splitlines():
        if line.strip():
            match = pattern.search(line)
            if match is None:
                raise ValueError("unreadable settlement observation: %r" % line)
            gap = int(match.group(2)[1:]) - int(match.group(1)[1:])
            (carried if match.group(3) == "CARRIED" else expired).append(gap)
    low = max(carried, default=0)
    high = min(expired) - 1
    if low != high:
        raise ValueError("survival age not settled: %d..%d" % (low, high))
    return low


# ----------------------------------------------------------------------------- tallies

def count_markers(data: pathlib.Path) -> dict:
    def tally(paths, token):
        return sum(read_text(path).count(token) for path in paths)
    state = sorted(data.glob("state_events_p*.jsonl"))
    circulars = sorted(data.glob("port_circulars_p*.jsonl"))
    audit = [data / name for name in AUDIT_FILES]
    counts = {key: tally(state, token) for key, token in STATE_MARKERS.items()}
    counts.update({key: tally(circulars, token) for key, token in CIRCULAR_MARKERS.items()})
    counts.update({key: tally([data / "commitment_exceptions.csv"], token)
                   for key, token in EXCEPTION_MARKERS.items()})
    counts.update({key: tally(audit, token) for key, token in AUDIT_MARKERS.items()})
    return counts


def count_source_rows(data: pathlib.Path) -> dict:
    def lines(paths, header):
        total = 0
        for path in paths:
            body = [ln for ln in read_text(path).splitlines() if ln.strip() and not ln.startswith("#")]
            total += len(body) - (1 if header and body else 0)
        return total
    return {
        "registry": lines(sorted(data.glob("registry_q*.tsv")), True),
        "fixed_width": lines(sorted(data.glob("fixed_width_intake_q*.txt")), False),
        "state_events": lines(sorted(data.glob("state_events_p*.jsonl")), False),
        "port_circulars": lines(sorted(data.glob("port_circulars_p*.jsonl")), False),
        "approval_audit": lines([data / name for name in AUDIT_FILES], False),
    }


# ----------------------------------------------------------------------------- allocation

def allocate_cell(capacity: int, claims: list[dict]) -> dict:
    """Minimums in register order, then one shared fill level on top of each paid
    minimum, then the indivisible remainder one berth-hour at a time."""
    grant = {c["nor_ref"]: 0 for c in claims}
    left = capacity
    for c in claims:
        pay = min(c["minimum"], c["claim"], left)
        grant[c["nor_ref"]] += pay
        left -= pay
    unmet = {c["nor_ref"]: c["claim"] - grant[c["nor_ref"]] for c in claims}
    level, top = 0, max(unmet.values(), default=0)
    while level < top and sum(min(level + 1, u) for u in unmet.values()) <= left:
        level += 1
    for c in claims:
        extra = min(level, unmet[c["nor_ref"]])
        grant[c["nor_ref"]] += extra
        left -= extra
    order = sorted(claims, key=lambda c: (-(c["claim"] - grant[c["nor_ref"]]), c["recorded_instant"],
                                          c["charterer"], c["nor_ref"]))
    remainder = 0
    for c in order:
        if left == 0:
            break
        if grant[c["nor_ref"]] < c["claim"]:
            grant[c["nor_ref"]] += 1
            left -= 1
            remainder += 1
    return {"grant": grant, "fill_level": level, "residual": left, "remainder": remainder}


def run_ledger(corpus: dict, survival: int, clearing: bool = True, carry: bool = True) -> dict:
    """Walk the horizon cycle by cycle and return ledger rows, cells and lot tallies."""
    in_scope, out_of_scope = defaultdict(list), defaultdict(list)
    for nor in corpus["nors"]:
        if nor["cycle"] in CYCLE_IDX and nor["charterer"] in corpus["segment"]:
            in_scope[(nor["booked_berth"], nor["cycle"])].append(nor)
        else:
            out_of_scope[nor["booked_berth"]].append(
                {"nor_ref": nor["nor_ref"], "charterer": nor["charterer"], "reason": "NONE"})
    lots = defaultdict(list)  # (charterer, terminal) -> [[raised_index, hours], ...] oldest first
    rows, cells = defaultdict(list), defaultdict(list)
    tallies = {"lots_expired": 0, "lots_cleared": 0, "remainder_hours": 0, "cycles_with_remainder": 0}
    for index, cycle in enumerate(CYCLES):
        for terminal in TERMINALS:
            for key in [k for k in lots if k[1] == terminal]:
                standing = []
                for raised, hours in lots[key]:
                    if index - raised > survival:
                        tallies["lots_expired"] += 1
                    else:
                        standing.append([raised, hours])
                lots[key] = standing
            nors = sorted(in_scope.get((terminal, cycle), []),
                          key=lambda n: (corpus["rank"][n["charterer"]], n["recorded_instant"],
                                         n["charterer"], n["nor_ref"]))
            claims = []
            for nor in nors:
                key = (nor["charterer"], terminal)
                carried_in = sum(h for _r, h in lots[key]) if carry else 0
                ceiling = corpus["ceiling"][key]
                excess = max(0, nor["laytime_hours"] + carried_in - ceiling)
                for lot in lots[key]:
                    cut = min(excess, lot[1])
                    lot[1] -= cut
                    excess -= cut
                lots[key] = [lot for lot in lots[key] if lot[1] > 0]
                own = nor["laytime_hours"] - excess
                claims.append({**nor, "key": key, "carried_in": carried_in, "ceiling": ceiling,
                               "own": own, "claim": own + sum(h for _r, h in lots[key]),
                               "minimum": corpus["minimum"].get(key, 0)})
            cap = corpus["capacity"][(terminal, cycle)]
            result = allocate_cell(cap, claims)
            if result["remainder"]:
                tallies["cycles_with_remainder"] += 1
                tallies["remainder_hours"] += result["remainder"]
            for c in claims:
                paid = result["grant"][c["nor_ref"]]
                for lot in lots[c["key"]]:
                    used = min(paid, lot[1])
                    lot[1] -= used
                    paid -= used
                lots[c["key"]] = [lot for lot in lots[c["key"]] if lot[1] > 0]
                if carry and c["own"] - paid > 0:
                    lots[c["key"]].append([index, c["own"] - paid])
                c["carried_out"] = sum(h for _r, h in lots[c["key"]])
                c["granted"] = result["grant"][c["nor_ref"]]
                rows[terminal].append(c)
            if clearing and result["residual"] > 0:
                for key in [k for k in lots if k[1] == terminal]:
                    tallies["lots_cleared"] += len(lots[key])
                    lots[key] = []
            cells[terminal].append({
                "cycle": cycle, "capacity_hours": cap, "fill_level": result["fill_level"],
                "minimum_total_hours": sum(c["minimum"] for c in claims),
                "granted_hours": cap - result["residual"], "residual_hours": result["residual"],
                "nor_count": len(claims), "binding": result["residual"] == 0,
            })
    return {"rows": rows, "cells": cells, "out_of_scope": out_of_scope, "tallies": tallies}


# ----------------------------------------------------------------------------- documents

def ledger_row(c: dict, corpus: dict) -> dict:
    granted = c["granted"]
    outcome = "FULL" if granted == c["claim"] else ("ZERO" if granted == 0 else "PARTIAL")
    return {
        "cycle": c["cycle"], "nor_ref": c["nor_ref"], "charterer": c["charterer"],
        "segment": corpus["segment"][c["charterer"]], "booked_berth": c["booked_berth"],
        "laytime_hours": c["laytime_hours"], "ceiling_hours": c["ceiling"],
        "claim_hours": c["claim"], "carried_in_hours": c["carried_in"],
        "granted_hours": granted, "demurrage_hours": c["claim"] - granted,
        "carried_out_hours": c["carried_out"], "served_berth": c["booked_berth"], "hops": 0,
        "outcome": outcome, "reason": "NONE", "granted_berthhours": granted * corpus["unit"],
        "minimum_hours": c["minimum"],
    }


def build_terminals(corpus: dict, walk: dict) -> dict:
    documents = {}
    for terminal in TERMINALS:
        ledger = sorted((ledger_row(c, corpus) for c in walk["rows"][terminal]),
                        key=lambda r: (CYCLE_IDX[r["cycle"]], r["charterer"], r["nor_ref"]))
        running = defaultdict(lambda: [0, 0])
        for row in ledger:
            state = running[row["charterer"]]
            state[0] += row["granted_hours"]
            state[1] += row["demurrage_hours"]
            row["granted_to_date_hours"], row["demurrage_to_date_hours"] = state
        documents[terminal] = {
            "terminal": terminal, "cycles": walk["cells"][terminal], "ledger": ledger,
            "out_of_scope": sorted(walk["out_of_scope"][terminal], key=lambda r: r["nor_ref"]),
        }
    return documents


def build_summary(corpus: dict, walk: dict, terminals: dict) -> dict:
    ledger = [row for t in TERMINALS for row in terminals[t]["ledger"]]
    cells = [cell for t in TERMINALS for cell in terminals[t]["cycles"]]
    falls, last = 0, {}
    for t in TERMINALS:
        for row in terminals[t]["ledger"]:
            key = (t, row["charterer"])
            falls += int(row["demurrage_to_date_hours"] < last.get(key, 0))
            last[key] = row["demurrage_to_date_hours"]
    return {"totals": {
        "granted_hours": sum(r["granted_hours"] for r in ledger),
        "claim_hours": sum(r["claim_hours"] for r in ledger),
        "demurrage_hours": sum(r["demurrage_hours"] for r in ledger),
        "capacity_hours": sum(c["capacity_hours"] for c in cells),
        "residual_hours": sum(c["residual_hours"] for c in cells),
        "ledger_rows": len(ledger),
        "cycles_with_remainder": walk["tallies"]["cycles_with_remainder"],
        "running_demurrage_max": max((r["demurrage_to_date_hours"] for r in ledger), default=0),
        "out_of_scope_rows": corpus["markers"]["unknown_charterer_rows"] + corpus["markers"]["out_of_horizon_rows"],
        "late_dropped": corpus["markers"]["late_dropped"],
        "identity_checks": {
            "capacity_minus_grant_minus_residual": sum(
                1 for c in cells if c["capacity_hours"] != c["granted_hours"] + c["residual_hours"]),
            "claim_minus_grant_minus_demurrage": sum(
                1 for r in ledger if r["claim_hours"] != r["granted_hours"] + r["demurrage_hours"]),
            "running_demurrage_falls": falls,
        },
    }}


def build_segments(terminals: dict) -> dict:
    documents = {}
    for segment in ("liner", "tramp"):
        rows = {t: [r for r in terminals[t]["ledger"] if r["segment"] == segment] for t in TERMINALS}
        documents[segment] = {
            "segment": segment,
            "totals": {"granted_hours": sum(r["granted_hours"] for t in TERMINALS for r in rows[t]),
                       "claim_hours": sum(r["claim_hours"] for t in TERMINALS for r in rows[t])},
            "by_terminal": {t: sum(r["granted_hours"] for r in rows[t]) for t in TERMINALS},
        }
    return documents


def build_policy_audit(corpus: dict, walk: dict, terminals: dict) -> dict:
    ledger = [(t, row) for t in TERMINALS for row in terminals[t]["ledger"]]
    cells = [cell for t in TERMINALS for cell in terminals[t]["cycles"]]
    matched = {(row["charterer"], t) for t, row in ledger}
    claims = [c for t in TERMINALS for c in walk["rows"][t]]
    audit = {key: corpus["markers"][key] for key in POLICY_MARKER_TALLIES}
    audit.update({
        "lots_expired": walk["tallies"]["lots_expired"],
        "lots_cleared": walk["tallies"]["lots_cleared"],
        "ceiling_binding": sum(1 for c in cells if c["residual_hours"] == 0 and c["capacity_hours"] > 0),
        "ceiling_zero": sum(1 for c in cells if c["capacity_hours"] == 0),
        "minimums_honoured_full": sum(1 for _t, r in ledger
                                      if r["minimum_hours"] > 0 and r["granted_hours"] >= r["minimum_hours"]),
        "minimums_honoured_short": sum(1 for _t, r in ledger
                                       if 0 < r["granted_hours"] < r["minimum_hours"]),
        "minimums_unmatched": sum(1 for key, hours in corpus["minimum"].items()
                                  if hours > 0 and key not in matched),
        "cutover_sides": {
            "before": sum(1 for c in claims if c["recorded_instant"] < corpus["cutover"]),
            "after": sum(1 for c in claims if c["recorded_instant"] >= corpus["cutover"]),
        },
        "withheld": {"weather_stoppage": corpus["weather"], "survival_cycles": corpus["survival"]},
    })
    return audit


def build_data_quality(corpus: dict) -> dict:
    nors = corpus["nors"]
    sources = {"nor_log": {
        "declared": corpus["declared"]["nor_log"], "parsed": len(nors),
        "admitted": sum(1 for n in nors if n["cycle"] in CYCLE_IDX
                        and n["recorded_instant"] <= corpus["admission"])}}
    for name, count in corpus["rows"].items():
        sources[name] = {"declared": corpus["declared"][name], "parsed": count, "admitted": count}
    quality = {"sources": sources}
    quality.update({key: corpus["markers"][key] for key in DATA_QUALITY_TALLIES})
    return quality


def write_documents(out: pathlib.Path, documents: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, document in documents.items():
        (out / name).write_text(json.dumps(document, sort_keys=True, indent=1, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    corpus = load_corpus(pathlib.Path(args.data))
    walk = run_ledger(corpus, corpus["survival"])
    terminals = build_terminals(corpus, walk)
    documents = {"terminal_%s.json" % t: terminals[t] for t in TERMINALS}
    documents.update({"segment_%s.json" % s: d for s, d in build_segments(terminals).items()})
    documents["summary.json"] = build_summary(corpus, walk, terminals)
    documents["policy_audit.json"] = build_policy_audit(corpus, walk, terminals)
    documents["data_quality.json"] = build_data_quality(corpus)
    write_documents(pathlib.Path(args.out), documents)
    return 0


if __name__ == "__main__":
    sys.exit(main())
