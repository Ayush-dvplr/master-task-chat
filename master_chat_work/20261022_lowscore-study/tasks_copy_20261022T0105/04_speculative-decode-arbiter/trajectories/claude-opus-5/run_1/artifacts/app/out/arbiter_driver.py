#!/usr/bin/env python3
"""Speculative Decode Arbiter replay driver.

Reads a recorded SDA corpus and writes every replay artifact defined by the SDA
output format reference. Standard library only, deterministic, and free of any
figure belonging to a particular corpus.

    python3 arbiter_driver.py --data <corpus directory> --out <output directory>
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil

# ---------------------------------------------------------------- constants

SLOT_REGISTRY = tuple("S%02d" % i for i in range(16))
TENANT_REGISTRY = tuple("T%02d" % i for i in range(1, 11))
RANK_OF_CLASS = {"bulk": 1, "standard": 2, "interactive": 3, "realtime": 4}

EMA_WINDOW = 25
EMA_L = 2.0 / (EMA_WINDOW + 1)
ALPHA_SEED = 0.5
BAND_HIGH = 0.85
BAND_LOW = 0.30
K_MIN = 1
K_MAX = 8
MAX_PASSES = 6

VOID_TOKEN = "TKFF"
VOID_CLASS = "CZZ"

REPAIR_CODES = ("R01", "R02", "R03", "R04", "R05", "R06")
TERMINAL_CLASSES = ("accepted", "rejected", "expired", "reclaimed", "voided")

UNIT_DRAFT = 3
UNIT_VERIFY = 7
UNIT_EMIT = 2
UNIT_RECLAIM = 5
UNIT_EXPIRE = 4
UNIT_VOID = 11
UNIT_INVERSION = 13

ARTIFACT_ORDER = (
    "stream_registry.csv",
    "token_classes.json",
    "window_index.tsv",
    "lease_grants.psv",
    "cancel_timeline.jsonl",
    "k_schedule.tsv",
    "acceptance_ledger.csv",
    "lease_conflicts.tsv",
    "reclaim_ledger.csv",
    "malformed_repairs.jsonl",
    "window_disposition.csv",
    "token_accounting.tsv",
    "stream_metrics.json",
    "tenant_cost.csv",
    "inversion_report.tsv",
    "nonconvergence_report.jsonl",
    "slot_occupancy.tsv",
    "conservation_ledger.json",
    "reconciliation.tsv",
    "arbiter_driver.py",
)

# ------------------------------------------------------------------ parsing


def canon(ref):
    """Canonical stream identifier: upper cased, underscores become hyphens."""
    return ref.strip().upper().replace("_", "-")


def window_id(stream_id, seq):
    return "%s#%s" % (stream_id, seq_code(seq))


def seq_code(seq):
    return "%04d" % int(seq)


def _lines(path):
    with open(path, "r", encoding="utf-8") as fh:
        return [ln for ln in fh.read().split("\n") if ln != ""]


def _table(path, delim, header_first_field):
    """Delimited records. The header line is dropped only when present."""
    rows = [ln.split(delim) for ln in _lines(path)]
    if rows and rows[0] and rows[0][0].strip() == header_first_field:
        rows = rows[1:]
    return rows


def _logfmt(path):
    records = []
    for ln in _lines(path):
        rec = {}
        for part in ln.strip().split(" "):
            if "=" in part:
                key, value = part.split("=", 1)
                rec[key] = value
        records.append(rec)
    return records


def _jsonl(path):
    return [json.loads(ln) for ln in _lines(path)]


_SYSLOG = re.compile(
    r"^<\d+>\d+\s+\S+\s+\S+\s+\S+\s+\S+\s+(?P<msgid>\S+)\s+\[(?P<sd>.*?)\]\s*(?P<msg>.*)$"
)
_SD_PAIR = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)="([^"]*)"')


def _syslog(path):
    records = []
    for ln in _lines(path):
        match = _SYSLOG.match(ln.strip())
        if match is None:
            continue
        fields = dict(_SD_PAIR.findall(match.group("sd")))
        records.append((match.group("msgid"), fields, match.group("msg")))
    return records


def _shards(data_dir, pattern):
    return sorted(glob.glob(os.path.join(data_dir, pattern)))


# ------------------------------------------------------------------ loading


def load_token_classes(data_dir):
    """Return the alias map and the token identifiers in token ordinal order."""
    alias = {}
    for row in _table(os.path.join(data_dir, "token-alias.tsv"), "\t", "token_id"):
        alias[row[0].strip()] = row[1].strip()
    ordered = []
    index_path = os.path.join(data_dir, "token-index.jsonl")
    if os.path.exists(index_path):
        entries = _jsonl(index_path)
        entries.sort(key=lambda rec: (int(rec["ordinal"]), rec["token_id"]))
        for rec in entries:
            token = rec["token_id"]
            if token in alias and token not in ordered:
                ordered.append(token)
    for token in sorted(alias):
        if token not in ordered:
            ordered.append(token)
    return alias, ordered


def load_streams(data_dir):
    streams = {}
    for row in _table(os.path.join(data_dir, "streams-master.csv"), ",", "stream_ref"):
        stream_id = canon(row[0])
        priority_class = row[2].strip()
        streams[stream_id] = {
            "stream_id": stream_id,
            "tenant_id": row[1].strip(),
            "priority_class": priority_class,
            "priority_rank": RANK_OF_CLASS[priority_class],
            "k_seed": int(row[3]),
            "admit_open": int(row[4]),
            "admit_close": int(row[5]),
            "status": "active",
            "allocated_units": 0,
        }

    # The dedicated stream to tenant table is authoritative over the master hint.
    for row in _table(os.path.join(data_dir, "streams-tenant.tsv"), "\t", "stream_ref"):
        stream_id = canon(row[0])
        if stream_id in streams:
            streams[stream_id]["tenant_id"] = row[1].strip()

    for rec in _logfmt(os.path.join(data_dir, "streams-status.logfmt")):
        stream_id = canon(rec["stream"])
        if stream_id in streams:
            streams[stream_id]["status"] = rec["status"]

    budget = os.path.join(data_dir, "stream-budget-allocation.csv")
    for row in _table(budget, ",", "stream_ref"):
        stream_id = canon(row[0])
        if stream_id in streams:
            streams[stream_id]["allocated_units"] = int(row[1])

    return streams


def load_windows(data_dir, alias):
    """Assemble every recorded window and apply the documented repairs."""
    drafts = {}
    for path in _shards(data_dir, "windows-draft-*.jsonl"):
        for rec in _jsonl(path):
            key = (canon(rec["stream_ref"]), int(rec["seq"]))
            drafts[key] = (int(rec["k_requested"]), [str(t) for t in rec["draft"]])

    verdicts = {}
    for path in _shards(data_dir, "windows-verdict-*.psv"):
        for row in _table(path, "|", "stream_ref"):
            key = (canon(row[0]), int(row[1]))
            raw = row[2].strip() if len(row) > 2 else ""
            verdicts[key] = raw.split(";") if raw else []

    leases = {}
    for path in _shards(data_dir, "leases-grant-*.logfmt"):
        for rec in _logfmt(path):
            key = (canon(rec["stream"]), int(rec["seq"]))
            leases[key] = (rec["slot"], int(rec["grant"]), int(rec["expiry"]))

    meta = {}
    for path in _shards(data_dir, "windows-meta-*.tsv"):
        for row in _table(path, "\t", "stream_ref"):
            key = (canon(row[0]), int(row[1]))
            meta[key] = (row[2].strip(), int(row[3]))

    windows = {}
    for key in sorted(set(drafts) | set(leases) | set(meta) | set(verdicts)):
        stream_id, seq = key
        k_raw, draft_raw = drafts.get(key, (K_MIN, []))
        verdict_raw = verdicts.get(key, [])
        if key in leases:
            slot, grant, expiry = leases[key]
        elif key in meta:
            slot, grant = meta[key]
            expiry = grant
        else:
            slot, grant, expiry = "", 0, 0

        codes = []
        k_repaired = k_raw
        if k_raw < K_MIN:
            codes.append("R01")
            k_repaired = K_MIN
        elif k_raw > K_MAX:
            codes.append("R02")
            k_repaired = K_MAX

        draft = list(draft_raw)
        if len(draft) > k_repaired:
            codes.append("R03")
            draft = draft[:k_repaired]

        verdict_len_recorded = len(verdict_raw)
        verdict = list(verdict_raw)
        if verdict_len_recorded < len(draft):
            codes.append("R04")
            verdict.extend([VOID_TOKEN] * (len(draft) - verdict_len_recorded))
        elif verdict_len_recorded > len(draft):
            verdict = verdict[: len(draft)]

        void = expiry <= grant
        if void:
            codes.append("R05")

        # Repairs run in code order, so R06 inspects the vector R03 left behind.
        if any(token not in alias for token in draft):
            codes.append("R06")

        prefix_full = 0
        for position in range(len(draft)):
            draft_class = alias.get(draft[position], VOID_CLASS)
            if draft_class == VOID_CLASS:
                break
            if draft_class != alias.get(verdict[position], VOID_CLASS):
                break
            prefix_full += 1

        windows[key] = {
            "window_id": window_id(stream_id, seq),
            "stream_id": stream_id,
            "seq": seq,
            "k_requested": k_repaired,
            "drafted_recorded": len(draft),
            "slot": slot,
            "grant_tick": grant,
            "expiry_tick": expiry,
            "repair_codes": codes,
            "void": void,
            "verdict_len": verdict_len_recorded,
            "prefix_full": prefix_full,
        }
    return windows


def load_revocations(data_dir):
    revocations = []
    for row in _table(os.path.join(data_dir, "leases-revoke.csv"), ",", "slot"):
        revocations.append(
            {
                "slot": row[0].strip(),
                "revoke_tick": int(row[1]),
                "challenger": canon(row[2]),
                "holder": canon(row[3]),
                "holder_seq": int(row[4]),
            }
        )
    return revocations


def load_cancellations(data_dir):
    """Only STREAM_CANCEL journal records cancel a stream."""
    cancels = {}
    path = os.path.join(data_dir, "cancel-events.rfc5424")
    if not os.path.exists(path):
        return cancels
    for msgid, fields, _message in _syslog(path):
        if msgid != "STREAM_CANCEL":
            continue
        stream_id = canon(fields["stream"])
        entry = (int(fields["tick"]), fields.get("origin", ""))
        if stream_id not in cancels or entry < cancels[stream_id]:
            cancels[stream_id] = entry
    return cancels


# ------------------------------------------------------- schedule fixed point


def drafted_at(window, k_policy):
    return min(k_policy, window["drafted_recorded"])


def prefix_at(window, drafted):
    return min(window["prefix_full"], drafted)


def run_pass(ordered_windows, seed_k):
    """Replay one pass over a stream, returning its schedule, pooled ratio, alpha."""
    k_policy = seed_k
    alpha = ALPHA_SEED
    schedule = []
    total_prefix = 0
    total_drafted = 0
    for window in ordered_windows:
        schedule.append(k_policy)
        drafted = drafted_at(window, k_policy)
        prefix = prefix_at(window, drafted)
        total_prefix += prefix
        total_drafted += drafted
        ratio = (prefix / drafted) if drafted else 0.0
        alpha = (1.0 - EMA_L) * alpha + EMA_L * ratio
        if alpha > BAND_HIGH:
            k_policy = min(K_MAX, k_policy + 1)
        elif alpha < BAND_LOW:
            k_policy = K_MIN
    pooled = (total_prefix / total_drafted) if total_drafted else 0.0
    return schedule, pooled, alpha


def recalibrate(seed_k, pooled):
    if pooled > BAND_HIGH:
        return min(K_MAX, seed_k + 1)
    if pooled < BAND_LOW:
        return K_MIN
    return seed_k


def settle_stream(ordered_windows, seed_recorded):
    """Solve the seed K and its schedule together, stopping at the pass limit."""
    seed_k = seed_recorded
    previous = None
    passes = 0
    while True:
        passes += 1
        schedule, pooled, alpha = run_pass(ordered_windows, seed_k)
        settled = previous is not None and schedule == previous
        next_seed = recalibrate(seed_k, pooled)
        if settled or next_seed == seed_k:
            converged = True
        elif passes >= MAX_PASSES:
            converged = False
        else:
            previous = schedule
            seed_k = next_seed
            continue
        return {
            "schedule": schedule,
            "seed_k_recorded": seed_recorded,
            "seed_k_final": seed_k,
            "passes": passes,
            "converged": converged,
            "pooled_ratio": pooled,
            "alpha_final": alpha,
        }


def band_of(pooled):
    if pooled >= BAND_HIGH:
        return "high"
    if pooled >= BAND_LOW:
        return "mid"
    return "low"


# ------------------------------------------------------------- lease calculus


def resolve_leases(windows, streams, revocations):
    """Apply every revocation, returning the conflict log and per window expiry."""
    by_window = {}
    for event in revocations:
        by_window.setdefault((event["holder"], event["holder_seq"]), []).append(event)

    conflicts = []
    for key, window in windows.items():
        holder_rank = streams[window["stream_id"]]["priority_rank"]
        effective = window["expiry_tick"]
        movers = []
        for event in by_window.get(key, []):
            challenger = streams.get(event["challenger"])
            challenger_rank = challenger["priority_rank"] if challenger else 0
            takes_effect = challenger_rank > holder_rank
            conflicts.append(
                {
                    "window_id": window["window_id"],
                    "slot": window["slot"],
                    "holder": window["stream_id"],
                    "holder_rank": holder_rank,
                    "challenger": event["challenger"],
                    "challenger_rank": challenger_rank,
                    "revoke_tick": event["revoke_tick"],
                    "disposition": "preempted" if takes_effect else "inverted",
                }
            )
            if takes_effect and event["revoke_tick"] < window["expiry_tick"]:
                movers.append((event["revoke_tick"], event["challenger"]))

        preempted_by = ""
        if movers:
            effective, preempted_by = min(movers)
        window["effective_expiry"] = effective
        window["preempted_by"] = preempted_by
        window["span"] = max(0, effective - window["grant_tick"])
        window["granted_span"] = max(0, window["expiry_tick"] - window["grant_tick"])

    conflicts.sort(key=lambda row: (row["window_id"], row["challenger"], row["revoke_tick"]))
    return conflicts


def score_window(window, k_policy, cancel_tick):
    """Terminal classes for one window at its policy K."""
    drafted = drafted_at(window, k_policy)
    prefix = prefix_at(window, drafted)
    counts = dict.fromkeys(TERMINAL_CLASSES, 0)

    # A void window is resolved as void first, so it reaches no other class and
    # the cancellation takes nothing back from it.
    reclaimed = (
        cancel_tick is not None
        and window["grant_tick"] >= cancel_tick
        and not window["void"]
    )
    if window["void"]:
        counts["voided"] = drafted
    elif reclaimed:
        counts["reclaimed"] = drafted
    else:
        scoring_expiry = window["effective_expiry"]
        if cancel_tick is not None and cancel_tick < scoring_expiry:
            scoring_expiry = cancel_tick
        span = max(0, scoring_expiry - window["grant_tick"])
        voided = max(0, drafted - window["verdict_len"])
        accepted = min(prefix, span)
        counts["accepted"] = accepted
        counts["expired"] = prefix - accepted
        counts["voided"] = voided
        counts["rejected"] = drafted - prefix - voided

    return {
        "window_id": window["window_id"],
        "stream_id": window["stream_id"],
        "seq": window["seq"],
        "k_policy": k_policy,
        "drafted": drafted,
        "agreed_prefix": prefix,
        "reclaimed_window": reclaimed,
        "accepted": counts["accepted"],
        "rejected": counts["rejected"],
        "expired": counts["expired"],
        "reclaimed": counts["reclaimed"],
        "voided": counts["voided"],
    }


# ------------------------------------------------------------------ rendering


def ratio4(value):
    """Four decimal places, rounded half to even, applied only at emission."""
    return "%.4f" % value


def boolean(value):
    return "true" if value else "false"


def write_lines(path, lines):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def write_delimited(path, header, rows, delim):
    lines = [delim.join(header)]
    lines.extend(delim.join(str(cell) for cell in row) for row in rows)
    write_lines(path, lines)


def write_jsonl(path, objects):
    write_lines(path, [json.dumps(obj) for obj in objects])


def write_json(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, indent=2) + "\n")


def dominant_class(ledger):
    best_index = None
    best_count = -1
    for index, name in enumerate(TERMINAL_CLASSES):
        if ledger[name] > best_count:
            best_count = ledger[name]
            best_index = index
    return TERMINAL_CLASSES[best_index]


# ----------------------------------------------------------------- the replay


def replay(data_dir, out_dir):
    alias, token_order = load_token_classes(data_dir)
    streams = load_streams(data_dir)
    windows = load_windows(data_dir, alias)
    revocations = load_revocations(data_dir)
    cancels = load_cancellations(data_dir)

    conflicts = resolve_leases(windows, streams, revocations)

    windows_by_stream = {}
    for key in sorted(windows):
        windows_by_stream.setdefault(key[0], []).append(windows[key])

    # Seed recalibration and its fixed point, per stream.
    settled = {}
    for stream_id in sorted(streams):
        ordered = windows_by_stream.get(stream_id, [])
        settled[stream_id] = settle_stream(ordered, streams[stream_id]["k_seed"])
        settled[stream_id]["band"] = band_of(settled[stream_id]["pooled_ratio"])
        settled[stream_id]["windows"] = len(ordered)

    # Per window terminal accounting at the settled schedule.
    ledger = []
    ledger_by_window = {}
    for stream_id in sorted(windows_by_stream):
        schedule = settled[stream_id]["schedule"]
        cancel_tick = cancels[stream_id][0] if stream_id in cancels else None
        for position, window in enumerate(windows_by_stream[stream_id]):
            row = score_window(window, schedule[position], cancel_tick)
            row["terminal_band"] = settled[stream_id]["band"]
            ledger.append(row)
            ledger_by_window[window["window_id"]] = row
    ledger.sort(key=lambda row: row["window_id"])

    inversions_by_stream = {}
    for conflict in conflicts:
        if conflict["disposition"] == "inverted":
            holder = conflict["holder"]
            inversions_by_stream[holder] = inversions_by_stream.get(holder, 0) + 1

    # Per stream accounting, aggregated from the per window ledger.
    accounting = {}
    for stream_id in sorted(streams):
        accounting[stream_id] = dict(
            drafted=0, accepted=0, rejected=0, expired=0, reclaimed=0, voided=0
        )
    for row in ledger:
        totals = accounting[row["stream_id"]]
        totals["drafted"] += row["drafted"]
        for name in TERMINAL_CLASSES:
            totals[name] += row[name]
    for stream_id, totals in accounting.items():
        totals["residual"] = totals["drafted"] - sum(totals[name] for name in TERMINAL_CLASSES)

    paths = {name: os.path.join(out_dir, name) for name in ARTIFACT_ORDER}

    # --- stream_registry.csv
    write_delimited(
        paths["stream_registry.csv"],
        [
            "stream_id",
            "tenant_id",
            "priority_class",
            "priority_rank",
            "k_seed",
            "admit_open",
            "admit_close",
            "status",
        ],
        [
            [
                stream["stream_id"],
                stream["tenant_id"],
                stream["priority_class"],
                stream["priority_rank"],
                stream["k_seed"],
                stream["admit_open"],
                stream["admit_close"],
                stream["status"],
            ]
            for stream in (streams[sid] for sid in sorted(streams))
        ],
        ",",
    )

    # --- token_classes.json
    write_json(
        paths["token_classes.json"],
        {token: alias[token] for token in token_order},
    )

    # --- window_index.tsv
    write_delimited(
        paths["window_index.tsv"],
        [
            "window_id",
            "stream_id",
            "seq",
            "k_requested",
            "drafted_recorded",
            "slot",
            "grant_tick",
            "expiry_tick",
            "repair_codes",
            "terminal_band",
        ],
        [
            [
                window["window_id"],
                window["stream_id"],
                seq_code(window["seq"]),
                window["k_requested"],
                window["drafted_recorded"],
                window["slot"],
                window["grant_tick"],
                window["expiry_tick"],
                ";".join(window["repair_codes"]),
                settled[window["stream_id"]]["band"],
            ]
            for window in (windows[key] for key in sorted(windows))
        ],
        "\t",
    )

    # --- lease_grants.psv, ordered on slot then grant tick then window
    lease_rows = sorted(
        (windows[key] for key in windows),
        key=lambda w: (w["slot"], w["grant_tick"], w["window_id"]),
    )
    write_delimited(
        paths["lease_grants.psv"],
        [
            "window_id",
            "slot",
            "grant_tick",
            "recorded_expiry",
            "effective_expiry",
            "preempted_by",
            "span",
        ],
        [
            [
                window["window_id"],
                window["slot"],
                window["grant_tick"],
                window["expiry_tick"],
                window["effective_expiry"],
                window["preempted_by"],
                window["span"],
            ]
            for window in lease_rows
        ],
        "|",
    )

    # --- cancel_timeline.jsonl
    timeline = []
    for stream_id in sorted(cancels):
        cancel_tick, origin = cancels[stream_id]
        after = 0
        straddling = 0
        for window in windows_by_stream.get(stream_id, []):
            if window["grant_tick"] >= cancel_tick:
                after += 1
            elif window["effective_expiry"] > cancel_tick:
                straddling += 1
        timeline.append(
            {
                "stream_id": stream_id,
                "cancel_tick": cancel_tick,
                "origin": origin,
                "windows_after": after,
                "windows_straddling": straddling,
            }
        )
    write_jsonl(paths["cancel_timeline.jsonl"], timeline)

    # --- k_schedule.tsv
    write_delimited(
        paths["k_schedule.tsv"],
        ["stream_id", "seed_k_recorded", "seed_k_final", "passes", "converged", "schedule"],
        [
            [
                stream_id,
                settled[stream_id]["seed_k_recorded"],
                settled[stream_id]["seed_k_final"],
                settled[stream_id]["passes"],
                boolean(settled[stream_id]["converged"]),
                ",".join(str(k) for k in settled[stream_id]["schedule"]),
            ]
            for stream_id in sorted(settled)
        ],
        "\t",
    )

    # --- acceptance_ledger.csv
    write_delimited(
        paths["acceptance_ledger.csv"],
        [
            "window_id",
            "k_policy",
            "drafted",
            "agreed_prefix",
            "accepted",
            "rejected",
            "expired",
            "reclaimed",
            "voided",
        ],
        [
            [
                row["window_id"],
                row["k_policy"],
                row["drafted"],
                row["agreed_prefix"],
                row["accepted"],
                row["rejected"],
                row["expired"],
                row["reclaimed"],
                row["voided"],
            ]
            for row in ledger
        ],
        ",",
    )

    # --- lease_conflicts.tsv
    write_delimited(
        paths["lease_conflicts.tsv"],
        [
            "window_id",
            "slot",
            "holder",
            "holder_rank",
            "challenger",
            "challenger_rank",
            "revoke_tick",
            "disposition",
        ],
        [
            [
                conflict["window_id"],
                conflict["slot"],
                conflict["holder"],
                conflict["holder_rank"],
                conflict["challenger"],
                conflict["challenger_rank"],
                conflict["revoke_tick"],
                conflict["disposition"],
            ]
            for conflict in conflicts
        ],
        "\t",
    )

    # --- reclaim_ledger.csv
    reclaim_rows = []
    for stream_id in sorted(cancels):
        cancel_tick = cancels[stream_id][0]
        reclaimed_windows = 0
        reclaimed_tokens = 0
        slots = set()
        for window in windows_by_stream.get(stream_id, []):
            row = ledger_by_window[window["window_id"]]
            if row["reclaimed_window"]:
                reclaimed_windows += 1
                reclaimed_tokens += row["drafted"]
                slots.add(window["slot"])
        reclaim_rows.append(
            [stream_id, cancel_tick, reclaimed_windows, reclaimed_tokens, len(slots)]
        )
    write_delimited(
        paths["reclaim_ledger.csv"],
        ["stream_id", "cancel_tick", "windows_reclaimed", "tokens_reclaimed", "slots_released"],
        reclaim_rows,
        ",",
    )

    # --- malformed_repairs.jsonl, every documented code including the unused
    repair_objects = []
    for code in REPAIR_CODES:
        count = 0
        tokens = 0
        for key in sorted(windows):
            window = windows[key]
            if code in window["repair_codes"]:
                count += 1
                tokens += ledger_by_window[window["window_id"]]["drafted"]
        repair_objects.append(
            {"repair_code": code, "windows": count, "tokens_affected": tokens}
        )
    write_jsonl(paths["malformed_repairs.jsonl"], repair_objects)

    # --- window_disposition.csv
    write_delimited(
        paths["window_disposition.csv"],
        [
            "window_id",
            "stream_id",
            "seq",
            "terminal_band",
            "k_policy",
            "drafted",
            "accepted",
            "rejected",
            "expired",
            "reclaimed",
            "voided",
            "disposition",
        ],
        [
            [
                row["window_id"],
                row["stream_id"],
                seq_code(row["seq"]),
                row["terminal_band"],
                row["k_policy"],
                row["drafted"],
                row["accepted"],
                row["rejected"],
                row["expired"],
                row["reclaimed"],
                row["voided"],
                dominant_class(row),
            ]
            for row in ledger
        ],
        ",",
    )

    # --- token_accounting.tsv
    write_delimited(
        paths["token_accounting.tsv"],
        [
            "stream_id",
            "drafted",
            "accepted",
            "rejected",
            "expired",
            "reclaimed",
            "voided",
            "residual",
        ],
        [
            [
                stream_id,
                accounting[stream_id]["drafted"],
                accounting[stream_id]["accepted"],
                accounting[stream_id]["rejected"],
                accounting[stream_id]["expired"],
                accounting[stream_id]["reclaimed"],
                accounting[stream_id]["voided"],
                accounting[stream_id]["residual"],
            ]
            for stream_id in sorted(accounting)
        ],
        "\t",
    )

    # --- stream_metrics.json
    metrics = {}
    for stream_id in sorted(settled):
        state = settled[stream_id]
        metrics[stream_id] = {
            "pooled_ratio": ratio4(state["pooled_ratio"]),
            "band": state["band"],
            "alpha_final": ratio4(state["alpha_final"]),
            "windows": state["windows"],
            "passes": state["passes"],
            "converged": bool(state["converged"]),
        }
    write_json(paths["stream_metrics.json"], metrics)

    # --- tenant_cost.csv, the cap applied after the tenant total is formed
    gross_by_stream = {}
    for stream_id in sorted(streams):
        totals = accounting[stream_id]
        gross_by_stream[stream_id] = (
            UNIT_DRAFT * totals["drafted"]
            + UNIT_VERIFY * settled[stream_id]["windows"]
            + UNIT_EMIT * totals["accepted"]
            + UNIT_RECLAIM * totals["reclaimed"]
            + UNIT_EXPIRE * totals["expired"]
            + UNIT_VOID * totals["voided"]
            + UNIT_INVERSION * inversions_by_stream.get(stream_id, 0)
        )

    tenant_gross = dict.fromkeys(TENANT_REGISTRY, 0)
    tenant_cap = dict.fromkeys(TENANT_REGISTRY, 0)
    for stream_id, stream in streams.items():
        tenant = stream["tenant_id"]
        tenant_gross[tenant] = tenant_gross.get(tenant, 0) + gross_by_stream[stream_id]
        tenant_cap[tenant] = tenant_cap.get(tenant, 0) + stream["allocated_units"]

    tenant_ids = list(TENANT_REGISTRY)
    for tenant in sorted(tenant_gross):
        if tenant not in tenant_ids:
            tenant_ids.append(tenant)

    tenant_rows = []
    for tenant in tenant_ids:
        gross = tenant_gross.get(tenant, 0)
        cap = tenant_cap.get(tenant, 0)
        over = gross > cap
        tenant_rows.append([tenant, gross, cap if over else gross, cap, boolean(over)])
    write_delimited(
        paths["tenant_cost.csv"],
        ["tenant_id", "gross_units", "capped_units", "cap", "over_cap"],
        tenant_rows,
        ",",
    )

    # --- inversion_report.tsv
    write_delimited(
        paths["inversion_report.tsv"],
        ["window_id", "slot", "holder", "challenger", "revoke_tick", "tokens_preserved"],
        [
            [
                conflict["window_id"],
                conflict["slot"],
                conflict["holder"],
                conflict["challenger"],
                conflict["revoke_tick"],
                ledger_by_window[conflict["window_id"]]["accepted"],
            ]
            for conflict in conflicts
            if conflict["disposition"] == "inverted"
        ],
        "\t",
    )

    # --- nonconvergence_report.jsonl
    write_jsonl(
        paths["nonconvergence_report.jsonl"],
        [
            {
                "stream_id": stream_id,
                "passes": settled[stream_id]["passes"],
                "final_schedule": settled[stream_id]["schedule"],
                "pooled_ratio": ratio4(settled[stream_id]["pooled_ratio"]),
            }
            for stream_id in sorted(settled)
            if not settled[stream_id]["converged"]
        ],
    )

    # --- slot_occupancy.tsv
    slot_ids = list(SLOT_REGISTRY)
    for window in windows.values():
        if window["slot"] and window["slot"] not in slot_ids:
            slot_ids.append(window["slot"])
    slot_rows = []
    for slot in slot_ids:
        held = [w for w in windows.values() if w["slot"] == slot]
        granted = sum(w["granted_span"] for w in held)
        effective = sum(w["span"] for w in held)
        events = []
        for window in held:
            if window["span"] > 0:
                events.append((window["grant_tick"], 1))
                events.append((window["effective_expiry"], -1))
        events.sort(key=lambda item: (item[0], item[1]))
        live = 0
        peak = 0
        for _tick, delta in events:
            live += delta
            peak = max(peak, live)
        slot_rows.append([slot, len(held), granted, effective, peak])
    write_delimited(
        paths["slot_occupancy.tsv"],
        ["slot", "windows", "granted_ticks", "effective_ticks", "peak_concurrent"],
        slot_rows,
        "\t",
    )

    # --- conservation_ledger.json, derived from the per window ledger
    from_windows = {"drafted": sum(row["drafted"] for row in ledger)}
    for name in TERMINAL_CLASSES:
        from_windows[name] = sum(row[name] for row in ledger)
    from_windows["residual"] = from_windows["drafted"] - sum(
        from_windows[name] for name in TERMINAL_CLASSES
    )
    write_json(
        paths["conservation_ledger.json"],
        {
            "drafted": from_windows["drafted"],
            "accepted": from_windows["accepted"],
            "rejected": from_windows["rejected"],
            "expired": from_windows["expired"],
            "reclaimed": from_windows["reclaimed"],
            "voided": from_windows["voided"],
            "residual": from_windows["residual"],
        },
    )

    # --- reconciliation.tsv, the second derivation starts at the stream rows
    from_streams = {"drafted": sum(t["drafted"] for t in accounting.values())}
    for name in TERMINAL_CLASSES:
        from_streams[name] = sum(t[name] for t in accounting.values())
    write_delimited(
        paths["reconciliation.tsv"],
        ["class", "from_windows", "from_streams", "delta"],
        [
            [name, from_windows[name], from_streams[name], from_windows[name] - from_streams[name]]
            for name in ("drafted",) + TERMINAL_CLASSES
        ],
        "\t",
    )

    # --- run_manifest.json
    driver_path = paths["arbiter_driver.py"]
    source = os.path.abspath(__file__)
    if os.path.abspath(driver_path) != source and not os.path.exists(driver_path):
        shutil.copyfile(source, driver_path)
    artifacts = []
    for name in ARTIFACT_ORDER:
        path = paths[name]
        with open(path, "rb") as fh:
            payload = fh.read()
        artifacts.append(
            {
                "path": os.path.abspath(path),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
        )
    write_json(os.path.join(out_dir, "run_manifest.json"), {"artifacts": artifacts})


def main(argv=None):
    parser = argparse.ArgumentParser(description="Replay a recorded SDA run.")
    parser.add_argument("--data", default="/app/data")
    parser.add_argument("--out", default="/app/out")
    args = parser.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    replay(args.data, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
