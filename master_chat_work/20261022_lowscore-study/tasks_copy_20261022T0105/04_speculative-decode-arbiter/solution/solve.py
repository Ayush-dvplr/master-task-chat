#!/usr/bin/env python3
"""SDA arbiter replay.

Written from the shipped specification and its appendices, independently of the
grader. Run as the replay driver:

    python3 arbiter_driver.py --data <corpus directory> --out <output directory>

reads a recorded corpus, writes every declared replay artifact into the output
directory and exits 0. It holds no figure from any particular recording, so
pointed at a different corpus it produces that corpus's numbers.

With --oracle it additionally extracts and drives the control plane service
over both of its channels and prints the closing summary.

Standard library only. Deterministic: the same corpus always yields the same
bytes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from decimal import Decimal, ROUND_HALF_EVEN

# --------------------------------------------------------------------------
# Constants quoted from SPEC-SDA.md.
# --------------------------------------------------------------------------

SLOT_REGISTRY = ["S%02d" % i for i in range(16)]
TENANT_REGISTRY = ["T%02d" % i for i in range(1, 11)]
RANK_OF_LANE = {"bulk": 1, "standard": 2, "interactive": 3, "realtime": 4}

WIDTH_FLOOR = 1
WIDTH_CEILING = 8
EMA_SPAN = 25
EMA_WEIGHT = 2.0 / (EMA_SPAN + 1)
EMA_START = 0.5
RAISE_ABOVE = 0.85
RESET_BELOW = 0.30
PASS_LIMIT = 6

NULL_TOKEN = "TKFF"
NULL_CLASS = "CZZ"
REPAIR_ORDER = ["R01", "R02", "R03", "R04", "R05", "R06"]
CLASS_ORDER = ["accepted", "rejected", "expired", "reclaimed", "voided"]

UNIT_COST = {
    "draft": 3, "verify": 7, "emit": 2, "reclaim": 5,
    "expire": 4, "void": 11, "inversion": 13,
}

DELIVERABLES = [
    "stream_registry.csv", "token_classes.json", "window_index.tsv",
    "lease_grants.psv", "cancel_timeline.jsonl", "k_schedule.tsv",
    "acceptance_ledger.csv", "lease_conflicts.tsv", "reclaim_ledger.csv",
    "malformed_repairs.jsonl", "window_disposition.csv",
    "token_accounting.tsv", "stream_metrics.json", "tenant_cost.csv",
    "inversion_report.tsv", "nonconvergence_report.jsonl",
    "slot_occupancy.tsv", "conservation_ledger.json", "reconciliation.tsv",
    "arbiter_driver.py", "run_manifest.json",
]

CORPUS_DEFAULT = "/app/data"
OUTPUT_DEFAULT = "/app/out"
SERVICE_FILE = "arbiter_service.py"
SERVICE = {"entry": None}
LISTEN_PORT = 8713


# --------------------------------------------------------------------------
# Small helpers.
# --------------------------------------------------------------------------

def slurp(path):
    with io.open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def delimited(path, delimiter, skip_header=True):
    """Parse a delimited file with the csv module and no quoting surprises."""
    text = slurp(path)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter,
                        quoting=csv.QUOTE_NONE)
    records = [row for row in reader if row]
    if skip_header and records:
        records = records[1:]
    return records


def keyvalue_lines(path):
    """Logfmt: unquoted key=value pairs separated by single spaces."""
    result = []
    for raw in slurp(path).split("\n"):
        if not raw.strip():
            continue
        pairs = {}
        for token in raw.split(" "):
            head, sep, tail = token.partition("=")
            if sep:
                pairs[head] = tail
        result.append(pairs)
    return result


def properties_map(path):
    mapping = {}
    for raw in slurp(path).split("\n"):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        head, sep, tail = stripped.partition("=")
        if sep:
            mapping[head.strip()] = tail.strip()
    return mapping


def family(directory, pattern):
    matcher = re.compile(pattern)
    return sorted(os.path.join(directory, entry)
                  for entry in os.listdir(directory) if matcher.match(entry))


def canonical(reference):
    """Upper case, underscores become hyphens. SPEC section 2."""
    return reference.strip().upper().replace("_", "-")


def window_key(stream, sequence):
    """Canonical stream, '#', sequence zero padded to four. SPEC section 2."""
    return "%s#%04d" % (stream, sequence)


def ratio_text(value):
    """Four decimal places, half to even, applied only here. SPEC section 14."""
    return str(Decimal(value).quantize(Decimal("0.0001"),
                                       rounding=ROUND_HALF_EVEN))


def compact_json(payload):
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def joined(rows):
    return "".join(row + "\n" for row in rows)


def truth_word(flag):
    return "true" if flag else "false"


# --------------------------------------------------------------------------
# Reading the recording.
# --------------------------------------------------------------------------

def read_recording(directory):
    """Assemble the recorded run from the shipped families of files."""
    book = {}

    book["classes"] = {row[0]: row[1]
                       for row in delimited(os.path.join(directory, "token-alias.tsv"), "\t")
                       if len(row) >= 2}

    owner = {row[0]: row[1]
             for row in delimited(os.path.join(directory, "streams-tenant.tsv"), "\t")
             if len(row) >= 2}
    lane = properties_map(os.path.join(directory, "streams-priority.properties"))
    condition = {}
    for pairs in keyvalue_lines(os.path.join(directory, "streams-status.logfmt")):
        condition[pairs.get("stream", "")] = pairs.get("status", "active")

    streams = []
    for row in delimited(os.path.join(directory, "streams-master.csv"), ","):
        if len(row) < 6:
            continue
        reference, advisory, declared_lane, seed, opens, closes = row[:6]
        chosen_lane = lane.get(reference, declared_lane)
        streams.append({
            "id": canonical(reference),
            "ref": reference,
            "tenant": owner.get(reference, advisory),
            "lane": chosen_lane,
            "rank": RANK_OF_LANE.get(chosen_lane, 0),
            "seed": int(seed),
            "opens": int(opens),
            "closes": int(closes),
            "status": condition.get(reference, "active"),
        })
    book["streams"] = streams
    identity = {item["ref"]: item["id"] for item in streams}

    book["allowance"] = {
        identity[row[0]]: int(row[1])
        for row in delimited(os.path.join(directory, "stream-budget-allocation.csv"), ",")
        if len(row) >= 2 and row[0] in identity
    }

    proposals = {}
    for path in family(directory, r"windows-draft-\d+\.jsonl$"):
        for raw in slurp(path).split("\n"):
            if not raw.strip():
                continue
            record = json.loads(raw)
            proposals[(record["stream_ref"], int(record["seq"]))] = (
                int(record["k_requested"]), list(record["draft"]))

    opinions = {}
    for path in family(directory, r"windows-verdict-\d+\.psv$"):
        for row in delimited(path, "|"):
            if len(row) >= 3:
                opinions[(row[0], int(row[1]))] = [t for t in row[2].split(";") if t]

    followups = {}
    for path in family(directory, r"windows-correction-\d+\.ssv$"):
        for row in delimited(path, " "):
            if len(row) >= 3:
                followups[(row[0], int(row[1]))] = row[2]

    holdings = {}
    for path in family(directory, r"leases-grant-\d+\.logfmt$"):
        for pairs in keyvalue_lines(path):
            holdings[(pairs["stream"], int(pairs["seq"]))] = (
                pairs["slot"], int(pairs["grant"]), int(pairs["expiry"]))

    windows = []
    for handle, (asked, proposed) in proposals.items():
        reference, sequence = handle
        if reference not in identity or handle not in holdings:
            continue
        slot, granted, expires = holdings[handle]
        owner_id = identity[reference]
        windows.append({
            "key": window_key(owner_id, sequence),
            "stream": owner_id,
            "seq": sequence,
            "asked": asked,
            "proposed": proposed,
            "opinion": opinions.get(handle, []),
            "followup": followups.get(handle, ""),
            "slot": slot,
            "granted": granted,
            "expires": expires,
        })
    windows.sort(key=lambda item: (item["stream"], item["seq"]))
    book["windows"] = windows

    stops = []
    marker = re.compile(
        r'STREAM_CANCEL \[sda stream="([^"]+)" tick="(\d+)" origin="([^"]+)"\]')
    for raw in slurp(os.path.join(directory, "cancel-events.rfc5424")).split("\n"):
        found = marker.search(raw)
        if found and found.group(1) in identity:
            stops.append({"stream": identity[found.group(1)],
                          "tick": int(found.group(2)),
                          "origin": found.group(3)})
    stops.sort(key=lambda item: item["stream"])
    book["stops"] = stops

    challenges = []
    for row in delimited(os.path.join(directory, "leases-revoke.csv"), ","):
        if len(row) < 5:
            continue
        slot, tick, challenger, holder, sequence = row[:5]
        if challenger not in identity or holder not in identity:
            continue
        challenges.append({
            "slot": slot,
            "tick": int(tick),
            "challenger": identity[challenger],
            "holder": identity[holder],
            "window": window_key(identity[holder], int(sequence)),
        })
    book["challenges"] = challenges
    return book


# --------------------------------------------------------------------------
# Repairs. SPEC section 4.
# --------------------------------------------------------------------------

def apply_repairs(book):
    mended = []
    for window in book["windows"]:
        codes = []

        width = window["asked"]
        if width < WIDTH_FLOOR:
            width = WIDTH_FLOOR
            codes.append("R01")
        elif width > WIDTH_CEILING:
            width = WIDTH_CEILING
            codes.append("R02")

        proposed = list(window["proposed"])
        if len(proposed) > width:
            proposed = proposed[:width]
            codes.append("R03")

        opinion = list(window["opinion"])
        answered = min(len(opinion), len(proposed))
        if len(opinion) < len(proposed):
            opinion.extend([NULL_TOKEN] * (len(proposed) - len(opinion)))
            codes.append("R04")
        elif len(opinion) > len(proposed):
            opinion = opinion[:len(proposed)]

        dead = window["expires"] <= window["granted"]
        if dead:
            codes.append("R05")

        if any(token not in book["classes"] for token in proposed):
            codes.append("R06")

        mended.append(dict(window, width=width, proposed=proposed,
                           opinion=opinion, answered=answered,
                           codes=codes, dead=dead))
    return mended


# --------------------------------------------------------------------------
# Leases. SPEC section 8.
# --------------------------------------------------------------------------

def settle_leases(book, windows):
    """Return the surviving expiry per window, who moved it, and the ignored
    revocations."""
    rank_of = {item["id"]: item["rank"] for item in book["streams"]}
    grouped = {}
    for challenge in book["challenges"]:
        grouped.setdefault(challenge["window"], []).append(challenge)

    surviving = {}
    mover = {}
    ignored = []
    for window in windows:
        expiry = window["expires"]
        holder_rank = rank_of.get(window["stream"], 0)
        winner = None
        for challenge in sorted(grouped.get(window["key"], []),
                                key=lambda c: (c["tick"], c["challenger"])):
            if rank_of.get(challenge["challenger"], 0) > holder_rank:
                if challenge["tick"] < expiry:
                    expiry = challenge["tick"]
                    winner = challenge
            else:
                ignored.append(dict(challenge, holder_rank=holder_rank,
                                    challenger_rank=rank_of.get(challenge["challenger"], 0)))
        surviving[window["key"]] = expiry
        mover[window["key"]] = winner
    ignored.sort(key=lambda c: (c["window"], c["challenger"], c["tick"]))
    return surviving, mover, ignored


# --------------------------------------------------------------------------
# Acceptance. SPEC sections 5, 6 and 10.
# --------------------------------------------------------------------------

def agreement_length(classes, proposed, opinion):
    """Longest leading run sharing a class. The null class matches nothing."""
    reach = 0
    for index in range(min(len(proposed), len(opinion))):
        left = classes.get(proposed[index], NULL_CLASS)
        right = classes.get(opinion[index], NULL_CLASS)
        if left == NULL_CLASS or right == NULL_CLASS or left != right:
            break
        reach += 1
    return reach


def classify(book, window, width, expiry, stop_tick):
    """Split one window's drafted tokens across the five terminal classes."""
    proposed = window["proposed"][:width]
    opinion = window["opinion"][:width]
    drafted = len(proposed)
    tally = dict((name, 0) for name in CLASS_ORDER)

    if window["dead"]:
        tally["voided"] = drafted
        return tally, 0, drafted

    if stop_tick is not None and window["granted"] >= stop_tick:
        tally["reclaimed"] = drafted
        return tally, 0, drafted

    horizon = expiry
    if stop_tick is not None and stop_tick < horizon:
        horizon = stop_tick
    room = horizon - window["granted"]
    if room < 0:
        room = 0

    reach = agreement_length(book["classes"], proposed, opinion)
    landed = reach if reach <= room else room
    unanswered = drafted - min(window["answered"], drafted)

    tally["accepted"] = landed
    tally["expired"] = reach - landed
    tally["voided"] = unanswered
    tally["rejected"] = drafted - reach - unanswered
    return tally, reach, drafted


# --------------------------------------------------------------------------
# The schedule and its fixed point. SPEC sections 6 and 7.
# --------------------------------------------------------------------------

def sweep(book, windows, seed, surviving, stops):
    """One pass over a stream at a given seed width."""
    plan = []
    detail = []
    average = EMA_START
    width = seed
    for window in windows:
        width = max(WIDTH_FLOOR, min(WIDTH_CEILING, width))
        plan.append(width)
        tally, reach, drafted = classify(
            book, window, width, surviving[window["key"]],
            stops.get(window["stream"]))
        share = (float(reach) / drafted) if drafted else 0.0
        average = (1.0 - EMA_WEIGHT) * average + EMA_WEIGHT * share
        detail.append({"key": window["key"], "width": width, "reach": reach,
                       "drafted": drafted, "average": average, "tally": tally})
        if average > RAISE_ABOVE:
            width = min(WIDTH_CEILING, width + 1)
        elif average < RESET_BELOW:
            width = WIDTH_FLOOR
    return plan, detail, average


def pooled(detail):
    top = sum(row["reach"] for row in detail)
    bottom = sum(row["drafted"] for row in detail)
    return (float(top) / bottom) if bottom else 0.0


def settle_stream(book, stream, windows, surviving, stops):
    """Recalibrate the seed until the plan stops moving, capped at PASS_LIMIT."""
    seed = stream["seed"]
    earlier = None
    count = 0
    plan, detail, average = [], [], EMA_START
    settled = False
    while count < PASS_LIMIT:
        count += 1
        plan, detail, average = sweep(book, windows, seed, surviving, stops)
        if earlier is not None and plan == earlier:
            settled = True
            break
        earlier = plan
        rate = pooled(detail)
        if rate > RAISE_ABOVE:
            seed = min(WIDTH_CEILING, seed + 1)
        elif rate < RESET_BELOW:
            seed = WIDTH_FLOOR
        else:
            plan, detail, average = sweep(book, windows, seed, surviving, stops)
            settled = True
            break
    return {"seed": seed, "plan": plan, "detail": detail,
            "average": average, "passes": count, "settled": settled}


def band_of(rate):
    """SPEC section 12. Both boundaries closed from below."""
    if rate >= RAISE_ABOVE:
        return "high"
    if rate >= RESET_BELOW:
        return "mid"
    return "low"


# --------------------------------------------------------------------------
# Replay.
# --------------------------------------------------------------------------

def replay(book):
    windows = apply_repairs(book)
    surviving, mover, ignored = settle_leases(book, windows)
    stops = dict((item["stream"], item["tick"]) for item in book["stops"])

    grouped = {}
    for window in windows:
        grouped.setdefault(window["stream"], []).append(window)
    for rows in grouped.values():
        rows.sort(key=lambda item: item["seq"])

    outcome = {}
    for stream in book["streams"]:
        outcome[stream["id"]] = settle_stream(
            book, stream, grouped.get(stream["id"], []), surviving, stops)

    per_window = {}
    rate_of = {}
    band_map = {}
    for identifier, solved in outcome.items():
        rate_of[identifier] = pooled(solved["detail"])
        band_map[identifier] = band_of(rate_of[identifier])
        for row in solved["detail"]:
            per_window[row["key"]] = row

    return {
        "windows": windows,
        "by_key": dict((w["key"], w) for w in windows),
        "grouped": grouped,
        "surviving": surviving,
        "mover": mover,
        "ignored": ignored,
        "stops": stops,
        "outcome": outcome,
        "per_window": per_window,
        "rate": rate_of,
        "band": band_map,
        "ordered": sorted(book["streams"], key=lambda s: s["id"]),
    }


# --------------------------------------------------------------------------
# Deliverables. Shapes come from sda-output-formats.md.
# --------------------------------------------------------------------------

def build_stream_registry(book, run):
    rows = ["stream_id,tenant_id,priority_class,priority_rank,k_seed,"
            "admit_open,admit_close,status"]
    for stream in run["ordered"]:
        rows.append(",".join([
            stream["id"], stream["tenant"], stream["lane"], str(stream["rank"]),
            str(stream["seed"]), str(stream["opens"]), str(stream["closes"]),
            stream["status"]]))
    return joined(rows)


def build_token_classes(book, run):
    ordered = sorted(book["classes"].keys(),
                     key=lambda token: int(token[2:], 16))
    return compact_json(dict((t, book["classes"][t]) for t in ordered)) + "\n"


def build_window_index(book, run):
    rows = ["window_id\tstream_id\tseq\tk_requested\tdrafted_recorded\tslot\t"
            "grant_tick\texpiry_tick\trepair_codes\tterminal_band"]
    for window in sorted(run["windows"], key=lambda w: w["key"]):
        rows.append("\t".join([
            window["key"], window["stream"], "%04d" % window["seq"],
            str(window["width"]), str(len(window["proposed"])), window["slot"],
            str(window["granted"]), str(window["expires"]),
            ";".join(window["codes"]), run["band"][window["stream"]]]))
    return joined(rows)


def build_lease_grants(book, run):
    rows = ["window_id|slot|grant_tick|recorded_expiry|effective_expiry|"
            "preempted_by|span"]
    ordered = sorted(run["windows"],
                     key=lambda w: (w["slot"], w["granted"], w["key"]))
    for window in ordered:
        expiry = run["surviving"][window["key"]]
        winner = run["mover"].get(window["key"])
        room = expiry - window["granted"]
        rows.append("|".join([
            window["key"], window["slot"], str(window["granted"]),
            str(window["expires"]), str(expiry),
            winner["challenger"] if winner else "",
            str(room if room > 0 else 0)]))
    return joined(rows)


def build_cancel_timeline(book, run):
    rows = []
    for stop in sorted(book["stops"], key=lambda s: s["stream"]):
        later = 0
        overlapping = 0
        for window in run["grouped"].get(stop["stream"], []):
            if window["granted"] >= stop["tick"]:
                later += 1
            elif run["surviving"][window["key"]] > stop["tick"]:
                overlapping += 1
        rows.append(compact_json({
            "stream_id": stop["stream"], "cancel_tick": stop["tick"],
            "origin": stop["origin"], "windows_after": later,
            "windows_straddling": overlapping}))
    return joined(rows)


def build_k_schedule(book, run):
    rows = ["stream_id\tseed_k_recorded\tseed_k_final\tpasses\tconverged\tschedule"]
    for stream in run["ordered"]:
        solved = run["outcome"][stream["id"]]
        rows.append("\t".join([
            stream["id"], str(stream["seed"]), str(solved["seed"]),
            str(solved["passes"]), truth_word(solved["settled"]),
            ",".join(str(width) for width in solved["plan"])]))
    return joined(rows)


def build_acceptance_ledger(book, run):
    rows = ["window_id,k_policy,drafted,agreed_prefix,accepted,rejected,"
            "expired,reclaimed,voided"]
    for key in sorted(run["per_window"]):
        row = run["per_window"][key]
        tally = row["tally"]
        rows.append(",".join([
            key, str(row["width"]), str(row["drafted"]), str(row["reach"])]
            + [str(tally[name]) for name in CLASS_ORDER]))
    return joined(rows)


def build_lease_conflicts(book, run):
    rank_of = dict((s["id"], s["rank"]) for s in book["streams"])
    rows = ["window_id\tslot\tholder\tholder_rank\tchallenger\t"
            "challenger_rank\trevoke_tick\tdisposition"]
    gathered = []
    for challenge in book["challenges"]:
        window = run["by_key"].get(challenge["window"])
        if window is None:
            continue
        holder_rank = rank_of.get(challenge["holder"], 0)
        challenger_rank = rank_of.get(challenge["challenger"], 0)
        gathered.append((
            challenge["window"], window["slot"], challenge["holder"],
            holder_rank, challenge["challenger"], challenger_rank,
            challenge["tick"],
            "preempted" if challenger_rank > holder_rank else "inverted"))
    gathered.sort(key=lambda item: (item[0], item[4], item[6]))
    for item in gathered:
        rows.append("\t".join(str(field) for field in item))
    return joined(rows)


def build_reclaim_ledger(book, run):
    rows = ["stream_id,cancel_tick,windows_reclaimed,tokens_reclaimed,slots_released"]
    for stop in sorted(book["stops"], key=lambda s: s["stream"]):
        count = 0
        tokens = 0
        slots = set()
        for window in run["grouped"].get(stop["stream"], []):
            row = run["per_window"].get(window["key"])
            if row and row["tally"]["reclaimed"]:
                count += 1
                tokens += row["tally"]["reclaimed"]
                slots.add(window["slot"])
        rows.append(",".join([stop["stream"], str(stop["tick"]), str(count),
                              str(tokens), str(len(slots))]))
    return joined(rows)


def build_malformed_repairs(book, run):
    windows_hit = dict((code, 0) for code in REPAIR_ORDER)
    tokens_hit = dict((code, 0) for code in REPAIR_ORDER)
    for window in run["windows"]:
        row = run["per_window"].get(window["key"])
        drafted = row["drafted"] if row else 0
        for code in window["codes"]:
            if code in windows_hit:
                windows_hit[code] += 1
                tokens_hit[code] += drafted
    rows = []
    for code in REPAIR_ORDER:
        rows.append(compact_json({"repair_code": code,
                                  "windows": windows_hit[code],
                                  "tokens_affected": tokens_hit[code]}))
    return joined(rows)


def dominant(tally):
    best = CLASS_ORDER[0]
    for name in CLASS_ORDER:
        if tally[name] > tally[best]:
            best = name
    return best


def build_window_disposition(book, run):
    rows = ["window_id,stream_id,seq,terminal_band,k_policy,drafted,accepted,"
            "rejected,expired,reclaimed,voided,disposition"]
    for key in sorted(run["per_window"]):
        row = run["per_window"][key]
        window = run["by_key"][key]
        tally = row["tally"]
        rows.append(",".join(
            [key, window["stream"], "%04d" % window["seq"],
             run["band"][window["stream"]], str(row["width"]),
             str(row["drafted"])]
            + [str(tally[name]) for name in CLASS_ORDER]
            + [dominant(tally)]))
    return joined(rows)


def stream_totals(run, identifier):
    tally = dict((name, 0) for name in CLASS_ORDER)
    drafted = 0
    for window in run["grouped"].get(identifier, []):
        row = run["per_window"].get(window["key"])
        if not row:
            continue
        drafted += row["drafted"]
        for name in CLASS_ORDER:
            tally[name] += row["tally"][name]
    return drafted, tally


def build_token_accounting(book, run):
    rows = ["stream_id\tdrafted\taccepted\trejected\texpired\treclaimed\t"
            "voided\tresidual"]
    for stream in run["ordered"]:
        drafted, tally = stream_totals(run, stream["id"])
        gap = drafted - sum(tally[name] for name in CLASS_ORDER)
        rows.append("\t".join([stream["id"], str(drafted)]
                              + [str(tally[name]) for name in CLASS_ORDER]
                              + [str(gap)]))
    return joined(rows)


def build_stream_metrics(book, run):
    payload = {}
    for stream in run["ordered"]:
        solved = run["outcome"][stream["id"]]
        payload[stream["id"]] = {
            "pooled_ratio": ratio_text(run["rate"][stream["id"]]),
            "band": run["band"][stream["id"]],
            "alpha_final": ratio_text(solved["average"]),
            "windows": len(solved["detail"]),
            "passes": solved["passes"],
            "converged": solved["settled"],
        }
    return compact_json(payload) + "\n"


def build_tenant_cost(book, run):
    inversions = {}
    for entry in run["ignored"]:
        inversions[entry["holder"]] = inversions.get(entry["holder"], 0) + 1

    gross = dict((tenant, 0) for tenant in TENANT_REGISTRY)
    allowance = dict((tenant, 0) for tenant in TENANT_REGISTRY)
    for stream in book["streams"]:
        drafted, tally = stream_totals(run, stream["id"])
        count = len(run["grouped"].get(stream["id"], []))
        units = (drafted * UNIT_COST["draft"]
                 + count * UNIT_COST["verify"]
                 + tally["accepted"] * UNIT_COST["emit"]
                 + tally["reclaimed"] * UNIT_COST["reclaim"]
                 + tally["expired"] * UNIT_COST["expire"]
                 + tally["voided"] * UNIT_COST["void"]
                 + inversions.get(stream["id"], 0) * UNIT_COST["inversion"])
        gross[stream["tenant"]] = gross.get(stream["tenant"], 0) + units
        allowance[stream["tenant"]] = (allowance.get(stream["tenant"], 0)
                                       + book["allowance"].get(stream["id"], 0))

    rows = ["tenant_id,gross_units,capped_units,cap,over_cap"]
    for tenant in TENANT_REGISTRY:
        total = gross.get(tenant, 0)
        cap = allowance.get(tenant, 0)
        billed = total if total <= cap else cap
        rows.append(",".join([tenant, str(total), str(billed), str(cap),
                              truth_word(total > cap)]))
    return joined(rows)


def build_inversion_report(book, run):
    rows = ["window_id\tslot\tholder\tchallenger\trevoke_tick\ttokens_preserved"]
    for entry in sorted(run["ignored"],
                        key=lambda e: (e["window"], e["challenger"], e["tick"])):
        window = run["by_key"].get(entry["window"])
        row = run["per_window"].get(entry["window"])
        rows.append("\t".join([
            entry["window"], window["slot"] if window else entry["slot"],
            entry["holder"], entry["challenger"], str(entry["tick"]),
            str(row["tally"]["accepted"] if row else 0)]))
    return joined(rows)


def build_nonconvergence_report(book, run):
    rows = []
    for stream in run["ordered"]:
        solved = run["outcome"][stream["id"]]
        if solved["settled"]:
            continue
        rows.append(compact_json({
            "stream_id": stream["id"], "passes": solved["passes"],
            "final_schedule": solved["plan"],
            "pooled_ratio": ratio_text(run["rate"][stream["id"]])}))
    return joined(rows)


def build_slot_occupancy(book, run):
    rows = ["slot\twindows\tgranted_ticks\teffective_ticks\tpeak_concurrent"]
    counts = dict((slot, [0, 0, 0]) for slot in SLOT_REGISTRY)
    live = dict((slot, []) for slot in SLOT_REGISTRY)
    for window in run["windows"]:
        slot = window["slot"]
        if slot not in counts:
            continue
        expiry = run["surviving"][window["key"]]
        recorded = window["expires"] - window["granted"]
        effective = expiry - window["granted"]
        counts[slot][0] += 1
        counts[slot][1] += recorded if recorded > 0 else 0
        counts[slot][2] += effective if effective > 0 else 0
        if effective > 0:
            live[slot].append((window["granted"], expiry))
    for slot in SLOT_REGISTRY:
        marks = []
        for start, finish in live[slot]:
            marks.append((start, 1))
            marks.append((finish, -1))
        marks.sort()
        running = 0
        highest = 0
        for _, step in marks:
            running += step
            if running > highest:
                highest = running
        rows.append("\t".join([slot] + [str(v) for v in counts[slot]]
                              + [str(highest)]))
    return joined(rows)


def grand_totals(run):
    drafted = 0
    tally = dict((name, 0) for name in CLASS_ORDER)
    for row in run["per_window"].values():
        drafted += row["drafted"]
        for name in CLASS_ORDER:
            tally[name] += row["tally"][name]
    return drafted, tally


def build_conservation_ledger(book, run):
    drafted, tally = grand_totals(run)
    payload = {"drafted": drafted}
    for name in CLASS_ORDER:
        payload[name] = tally[name]
    payload["residual"] = drafted - sum(tally[name] for name in CLASS_ORDER)
    return compact_json(payload) + "\n"


def build_reconciliation(book, run):
    from_windows_drafted, from_windows = grand_totals(run)
    from_streams_drafted = 0
    from_streams = dict((name, 0) for name in CLASS_ORDER)
    for stream in book["streams"]:
        drafted, tally = stream_totals(run, stream["id"])
        from_streams_drafted += drafted
        for name in CLASS_ORDER:
            from_streams[name] += tally[name]
    rows = ["class\tfrom_windows\tfrom_streams\tdelta"]
    rows.append("\t".join(["drafted", str(from_windows_drafted),
                           str(from_streams_drafted),
                           str(from_windows_drafted - from_streams_drafted)]))
    for name in CLASS_ORDER:
        rows.append("\t".join([name, str(from_windows[name]),
                               str(from_streams[name]),
                               str(from_windows[name] - from_streams[name])]))
    return joined(rows)


BUILDERS = [
    ("stream_registry.csv", build_stream_registry),
    ("token_classes.json", build_token_classes),
    ("window_index.tsv", build_window_index),
    ("lease_grants.psv", build_lease_grants),
    ("cancel_timeline.jsonl", build_cancel_timeline),
    ("k_schedule.tsv", build_k_schedule),
    ("acceptance_ledger.csv", build_acceptance_ledger),
    ("lease_conflicts.tsv", build_lease_conflicts),
    ("reclaim_ledger.csv", build_reclaim_ledger),
    ("malformed_repairs.jsonl", build_malformed_repairs),
    ("window_disposition.csv", build_window_disposition),
    ("token_accounting.tsv", build_token_accounting),
    ("stream_metrics.json", build_stream_metrics),
    ("tenant_cost.csv", build_tenant_cost),
    ("inversion_report.tsv", build_inversion_report),
    ("nonconvergence_report.jsonl", build_nonconvergence_report),
    ("slot_occupancy.tsv", build_slot_occupancy),
    ("conservation_ledger.json", build_conservation_ledger),
    ("reconciliation.tsv", build_reconciliation),
]


def emit(directory, book, run, driver_text):
    if not os.path.isdir(directory):
        os.makedirs(directory)
    produced = {}
    for name, builder in BUILDERS:
        produced[name] = builder(book, run)
    produced["arbiter_driver.py"] = driver_text

    listing = []
    for name in DELIVERABLES:
        if name == "run_manifest.json":
            continue
        blob = produced[name].encode("utf-8")
        listing.append({"path": "/app/out/" + name,
                        "sha256": hashlib.sha256(blob).hexdigest(),
                        "bytes": len(blob)})
    produced["run_manifest.json"] = compact_json({"artifacts": listing}) + "\n"

    for name, text in produced.items():
        if name == "arbiter_driver.py":
            continue
        target = os.path.join(directory, name)
        with io.open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    return produced


# --------------------------------------------------------------------------
# Control plane. api_contract.md.
# --------------------------------------------------------------------------

def launch_service(corpus):
    entry = os.path.join(corpus, SERVICE_FILE)
    if not os.path.isfile(entry):
        return None
    SERVICE["entry"] = entry
    process = subprocess.Popen(
        [sys.executable, entry, "serve", "--port", str(LISTEN_PORT),
         "--data", corpus],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            with urllib.request.urlopen(
                    "http://127.0.0.1:%d/v1/health" % LISTEN_PORT, timeout=1):
                return process
        except Exception:
            time.sleep(0.25)
    return process


def through_cli(arguments):
    return subprocess.run([sys.executable, SERVICE["entry"]] + arguments,
                          capture_output=True, text=True, timeout=60)


def through_http(route, body):
    request = urllib.request.Request(
        "http://127.0.0.1:%d/v1/%s" % (LISTEN_PORT, route),
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=30) as reply:
        return json.loads(reply.read().decode("utf-8"))


def read_state():
    with urllib.request.urlopen(
            "http://127.0.0.1:%d/v1/state" % LISTEN_PORT, timeout=30) as reply:
        return json.loads(reply.read().decode("utf-8"))


def enact(book, run):
    """Enact the replay's decisions, using both channels.

    Returns one record per state change naming the channel that carried it, so
    the closing summary can say which channel did what.
    """
    ordered = run["ordered"]
    stopped = sorted(run["stops"])
    changes = []
    if not ordered:
        return changes
    through_cli(["admit", "--stream", ordered[0]["id"]])
    changes.append(("command line", "admit", ordered[0]["id"]))
    if len(ordered) > 1:
        through_cli(["admit", "--stream", ordered[1]["id"]])
        changes.append(("command line", "admit", ordered[1]["id"]))
    if stopped:
        through_cli(["cancel", "--stream", stopped[0]])
        changes.append(("command line", "cancel", stopped[0]))
    for stream in ordered[2:6]:
        through_http("admit", {"stream": stream["id"]})
        changes.append(("HTTP", "admit", stream["id"]))
    for identifier in stopped[1:4]:
        through_http("cancel", {"stream": identifier})
        changes.append(("HTTP", "cancel", identifier))
    seen = {}
    for window in run["windows"]:
        seen.setdefault(window["slot"], window["stream"])
    for slot in sorted(seen)[:4]:
        through_http("lease", {"slot": slot, "stream": seen[slot]})
        changes.append(("HTTP", "lease of slot " + slot, seen[slot]))
    through_http("note", {"text": "replay complete, artifacts written"})
    changes.append(("HTTP", "note", "replay complete, artifacts written"))
    return changes


# --------------------------------------------------------------------------
# Closing summary. The figures the instruction asks for by name.
# --------------------------------------------------------------------------

def rows_of(text, delimiter):
    lines = [line for line in text.split("\n") if line]
    header = lines[0].split(delimiter)
    return [dict(zip(header, line.split(delimiter))) for line in lines[1:]]


def closing_figures(produced):
    ledger = rows_of(produced["acceptance_ledger.csv"], ",")
    placed = rows_of(produced["window_disposition.csv"], ",")
    plans = rows_of(produced["k_schedule.tsv"], "\t")
    slots = rows_of(produced["slot_occupancy.tsv"], "\t")
    ignored = rows_of(produced["inversion_report.tsv"], "\t")
    index = rows_of(produced["window_index.tsv"], "\t")
    billing = rows_of(produced["tenant_cost.csv"], ",")
    reclaims = rows_of(produced["reclaim_ledger.csv"], ",")
    accounts = rows_of(produced["token_accounting.tsv"], "\t")
    registry = rows_of(produced["stream_registry.csv"], ",")
    metrics = json.loads(produced["stream_metrics.json"])
    stops = [json.loads(line)
             for line in produced["cancel_timeline.jsonl"].split("\n") if line]

    unsettled = set(json.loads(line)["stream_id"]
                    for line in produced["nonconvergence_report.jsonl"].splitlines()
                    if line)
    capped = set(row["tenant_id"] for row in billing if row["over_cap"] == "true")
    tenant_of = dict((row["stream_id"], row["tenant_id"]) for row in registry)

    widest = -1
    widest_stream = ""
    for row in plans:
        top = max(int(v) for v in row["schedule"].split(",")) if row["schedule"] else 0
        if top > widest or (top == widest and row["stream_id"] < widest_stream):
            widest = top
            widest_stream = row["stream_id"]

    rates = [float(item["pooled_ratio"]) for item in metrics.values()]

    return {
        "windows_at_k8": sum(1 for r in ledger if int(r["k_policy"]) == 8),
        "mean_pooled_ratio": ratio_text(sum(rates) / len(rates) if rates else 0.0),
        "high_band_streams": sum(1 for v in metrics.values() if v["band"] == "high"),
        "low_band_windows": sum(1 for r in placed if r["terminal_band"] == "low"),
        "lease_limited_windows": sum(
            1 for r in ledger if int(r["accepted"]) < int(r["agreed_prefix"])),
        "multi_repair_windows": sum(
            1 for r in index
            if len([c for c in r["repair_codes"].split(";") if c]) >= 2),
        "recalibrated_streams": sum(
            1 for r in plans if r["seed_k_recorded"] != r["seed_k_final"]),
        "max_schedule_stream": widest_stream,
        "distinct_schedules": len(set(r["schedule"] for r in plans)),
        "total_billed_units": sum(int(r["capped_units"]) for r in billing),
        "max_peak_concurrent": max(int(r["peak_concurrent"]) for r in slots),
        "nonconverged_drafted": sum(int(r["drafted"]) for r in accounts
                                    if r["stream_id"] in unsettled),
        "capped_tenant_drafted": sum(int(r["drafted"]) for r in accounts
                                     if tenant_of[r["stream_id"]] in capped),
        "high_band_drafted": sum(int(r["drafted"]) for r in accounts
                                 if metrics[r["stream_id"]]["band"] == "high"),
        "empty_reclaim_streams": sum(
            1 for r in reclaims if int(r["windows_reclaimed"]) == 0),
        "over_cap_tenants": sum(1 for r in billing if r["over_cap"] == "true"),
        "void_disposition_windows": sum(
            1 for r in placed if r["disposition"] == "voided"),
    }


FIGURE_ORDER = [
    "windows_at_k8", "mean_pooled_ratio", "high_band_streams",
    "low_band_windows", "lease_limited_windows", "multi_repair_windows",
    "recalibrated_streams", "max_schedule_stream", "distinct_schedules",
    "total_billed_units", "max_peak_concurrent", "nonconverged_drafted",
    "capped_tenant_drafted", "high_band_drafted", "empty_reclaim_streams",
    "over_cap_tenants", "void_disposition_windows",
]


# --------------------------------------------------------------------------
# Entry point.
# --------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--data", default=CORPUS_DEFAULT)
    parser.add_argument("--out", default=OUTPUT_DEFAULT)
    parser.add_argument("--oracle", action="store_true")
    options, _ = parser.parse_known_args(argv)

    here = os.path.abspath(__file__)
    with io.open(here, "r", encoding="utf-8") as handle:
        own_text = handle.read()

    if options.oracle:
        if not os.path.isdir(options.out):
            os.makedirs(options.out)
        with io.open(os.path.join(options.out, "arbiter_driver.py"), "w",
                     encoding="utf-8", newline="\n") as handle:
            handle.write(own_text)

    book = read_recording(options.data)
    run = replay(book)
    produced = emit(options.out, book, run, own_text)

    if not options.oracle:
        return 0

    process = launch_service(options.data)
    try:
        changes = enact(book, run)
        state = read_state()
    finally:
        if process is not None:
            process.terminate()

    figures = closing_figures(produced)
    report = ["Replay complete. Closing summary."]
    for name in FIGURE_ORDER:
        report.append("%s = %s" % (name, figures[name]))
    report.append("control plane admitted %d streams and cancelled %d"
                  % (len(state.get("admitted", [])), len(state.get("cancelled", []))))
    report.append("Each state change and the service channel that carried it:")
    for channel, operation, target in changes:
        report.append("  %s %s, sent over the %s channel"
                      % (operation, target, channel))
    report.append("artifacts written to %s" % options.out)
    sys.stdout.write("\n".join(report) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
