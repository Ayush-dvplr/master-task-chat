#!/usr/bin/env python3
"""fa7c65bd-ff01-50e7-b3ba-34fbd5df860d engine (contract SLSC-1.0).

Usage: python3 clear_spectrum.py DATA_DIR OUT_DIR
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

ZERO_HASH = "0" * 64
SECONDS_PER_HOUR = 3600
KHZ_PER_MHZ = 1000


# ---------------------------------------------------------------- primitives

def round_half_up(value):
    return int(Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def parse_ts(value):
    """Parse an ISO-8601 UTC instant ending in Z into integer epoch seconds."""
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        moment = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return int(moment.timestamp())


def format_ts(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def as_str(row, key):
    value = row.get(key)
    return value if isinstance(value, str) else None


def as_int(row, key):
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def as_cells(row, key="cells"):
    value = row.get(key)
    if not isinstance(value, list) or any(not isinstance(c, str) for c in value):
        return None
    return sorted(set(value))


def read_json(path, fallback):
    if not os.path.isfile(path):
        return fallback
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read().strip()
    if not text:
        return fallback
    return json.loads(text)


def read_jsonl(path):
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_report(out_dir, name, payload):
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2)
        handle.write("\n")


# ------------------------------------------------------------- revisioning

def comparable_fields(row):
    """Row payload used for peer-conflict detection (record_id excluded)."""
    out = {}
    for key, value in row.items():
        if key == "record_id":
            continue
        if key == "cells":
            cells = as_cells(row)
            out[key] = tuple(cells) if cells is not None else ("\x00bad",)
        elif key == "recorded_at":
            out[key] = parse_ts(value)
        else:
            out[key] = json.dumps(value, sort_keys=True)
    return out


def resolve_revisions(rows, group_key, conflict_code, invalid_code, issues):
    """Group revisioned rows and pick the maximum (revision, recorded_at, record_id)."""
    groups = {}
    for row in rows:
        gid = as_str(row, group_key)
        rid = as_str(row, "record_id")
        revision = as_int(row, "revision")
        recorded = parse_ts(row.get("recorded_at"))
        if gid is None:
            issues.append((invalid_code, rid if rid is not None else ""))
            continue
        if rid is None or revision is None or recorded is None:
            groups.setdefault(gid, []).append(
                (None, None, rid if rid is not None else "", row)
            )
            continue
        groups.setdefault(gid, []).append((revision, recorded, rid, row))

    decisions = []
    for gid in sorted(groups):
        entries = groups[gid]
        usable = [e for e in entries if e[0] is not None]
        if not usable:
            issues.append((invalid_code, gid))
            continue
        winner = max(usable, key=lambda e: (e[0], e[1], e[2]))
        peers = [e for e in usable if e[0] == winner[0] and e[1] == winner[1]]
        if len(peers) > 1:
            reference = comparable_fields(winner[3])
            if any(comparable_fields(p[3]) != reference for p in peers):
                issues.append((conflict_code, gid))
        discarded = sorted(e[2] for e in entries if e[2] != winner[2])
        decisions.append(
            {
                "group_id": gid,
                "winner_record_id": winner[2],
                "winner_row": winner[3],
                "discarded_record_ids": discarded,
            }
        )
    return decisions


# ------------------------------------------------------------------ loading

def interval_ok(low, high):
    return low is not None and high is not None and high > low


def contained(inner_low, inner_high, outer_low, outer_high):
    return inner_low >= outer_low and inner_high <= outer_high


def load_licenses(rows, parties, issues):
    licenses = {}
    grouped = {}
    for row in rows:
        lid = as_str(row, "license_id")
        if lid is None:
            continue
        grouped.setdefault(lid, []).append(row)
    for lid in sorted(grouped):
        group = grouped[lid]
        if len(group) > 1:
            issues.append(("INVALID_LICENSE", lid))
            continue
        row = group[0]
        owner = as_str(row, "owner_party_id")
        cells = as_cells(row)
        low = as_int(row, "low_khz")
        high = as_int(row, "high_khz")
        start = parse_ts(row.get("start"))
        end = parse_ts(row.get("end"))
        bad = (
            owner is None
            or owner not in parties
            or not cells
            or not interval_ok(low, high)
            or not interval_ok(start, end)
        )
        if bad:
            issues.append(("INVALID_LICENSE", lid))
            continue
        licenses[lid] = {
            "license_id": lid,
            "owner_party_id": owner,
            "cells": cells,
            "low_khz": low,
            "high_khz": high,
            "start": start,
            "end": end,
        }
    return licenses


def load_guard_bands(rows, issues):
    by_license = {}
    for row in rows:
        gid = as_str(row, "guard_id")
        lid = as_str(row, "license_id")
        guard = as_int(row, "guard_khz")
        by_license.setdefault(lid, []).append((gid, guard))

    guards = {}
    for lid, entries in by_license.items():
        duplicated = len(entries) > 1
        valid = []
        for gid, guard in entries:
            if guard is None or guard < 0 or duplicated:
                issues.append(("INVALID_GUARD_BAND", gid if gid is not None else ""))
            if guard is not None and guard >= 0:
                valid.append((gid if gid is not None else "", guard))
        if valid and lid is not None:
            guards[lid] = min(valid, key=lambda e: e[0])[1]
    return guards


def load_grants(decisions, licenses, parties, issues):
    grants = []
    ledger_decisions = []
    for decision in decisions:
        gid = decision["group_id"]
        row = decision["winner_row"]
        ledger_decisions.append(
            {
                "grant_id": gid,
                "winner_record_id": decision["winner_record_id"],
                "discarded_record_ids": decision["discarded_record_ids"],
            }
        )
        status = as_str(row, "status")
        if status == "cancelled":
            continue
        lid = as_str(row, "license_id")
        party = as_str(row, "party_id")
        cells = as_cells(row)
        low = as_int(row, "low_khz")
        high = as_int(row, "high_khz")
        start = parse_ts(row.get("start"))
        end = parse_ts(row.get("end"))
        priority = as_int(row, "priority")
        share = as_int(row, "share_bps")
        lic = licenses.get(lid)
        bad = (
            status != "active"
            or lic is None
            or party is None
            or party not in parties
            or share is None
            or share < 0
            or share > 10000
            or priority is None
            or not cells
            or not interval_ok(low, high)
            or not interval_ok(start, end)
        )
        if not bad:
            bad = (
                not set(cells).issubset(lic["cells"])
                or not contained(low, high, lic["low_khz"], lic["high_khz"])
                or not contained(start, end, lic["start"], lic["end"])
            )
        if bad:
            issues.append(("INVALID_GRANT", gid))
            continue
        grants.append(
            {
                "grant_id": gid,
                "record_id": decision["winner_record_id"],
                "license_id": lid,
                "party_id": party,
                "cells": cells,
                "low_khz": low,
                "high_khz": high,
                "start": start,
                "end": end,
                "priority": priority,
                "share_bps": share,
            }
        )
    grants.sort(
        key=lambda g: (
            g["license_id"],
            g["party_id"],
            g["start"],
            g["low_khz"],
            g["grant_id"],
        )
    )
    return grants, ledger_decisions


def load_box_rows(rows, licenses, id_key, code, issues, parties=None):
    """Load activation/exclusion style rows that must be contained by a license."""
    loaded = []
    for row in rows:
        rid = as_str(row, id_key)
        if rid is None:
            rid = ""
        lid = as_str(row, "license_id")
        cells = as_cells(row)
        low = as_int(row, "low_khz")
        high = as_int(row, "high_khz")
        start = parse_ts(row.get("start"))
        end = parse_ts(row.get("end"))
        lic = licenses.get(lid)
        bad = (
            lic is None
            or not cells
            or not interval_ok(low, high)
            or not interval_ok(start, end)
        )
        if not bad:
            bad = (
                not set(cells).issubset(lic["cells"])
                or not contained(low, high, lic["low_khz"], lic["high_khz"])
                or not contained(start, end, lic["start"], lic["end"])
            )
        party = None
        if parties is not None and not bad:
            party = as_str(row, "party_id")
            bad = party is None or (party != "*" and party not in parties)
        if bad:
            issues.append((code, rid))
            continue
        entry = {
            "id": rid,
            "license_id": lid,
            "cells": set(cells),
            "low_khz": low,
            "high_khz": high,
            "start": start,
            "end": end,
        }
        if parties is not None:
            entry["party_id"] = party
        loaded.append(entry)
    return loaded


def load_auctions(decisions, licenses, issues):
    auctions = []
    for decision in decisions:
        aid = decision["group_id"]
        row = decision["winner_row"]
        status = as_str(row, "status")
        if status == "cancelled":
            continue
        lid = as_str(row, "license_id")
        start = parse_ts(row.get("start"))
        end = parse_ts(row.get("end"))
        rate = as_int(row, "rate_cents_per_mhz_hour")
        lic = licenses.get(lid)
        bad = (
            status != "active"
            or lic is None
            or rate is None
            or rate < 0
            or not interval_ok(start, end)
        )
        if not bad:
            bad = not contained(start, end, lic["start"], lic["end"])
        if bad:
            issues.append(("INVALID_AUCTION", aid))
            continue
        auctions.append(
            {
                "auction_id": aid,
                "license_id": lid,
                "start": start,
                "end": end,
                "rate_cents_per_mhz_hour": rate,
            }
        )
    auctions.sort(key=lambda a: (a["license_id"], a["start"], a["auction_id"]))
    return auctions


def load_corrections(rows, licenses, issues):
    totals = {}
    for row in rows:
        cid = as_str(row, "correction_id")
        lid = as_str(row, "license_id")
        amount = as_int(row, "amount_cents")
        if lid is None or lid not in licenses or amount is None:
            issues.append(("INVALID_CORRECTION", cid if cid is not None else ""))
            continue
        totals[lid] = totals.get(lid, 0) + amount
    return totals


# ------------------------------------------------------------------- slicing

def usable_band(grant, guards):
    guard = guards.get(grant["license_id"], 0)
    return grant["low_khz"] + guard, grant["high_khz"] - guard


def build_slices(licenses, grants, activations, exclusions, auctions, guards, policy):
    slices = []
    grants_by_license = {}
    for grant in grants:
        low, high = usable_band(grant, guards)
        if high <= low:
            continue
        item = dict(grant)
        item["usable_low"] = low
        item["usable_high"] = high
        grants_by_license.setdefault(grant["license_id"], []).append(item)
    acts_by_license = {}
    for act in activations:
        acts_by_license.setdefault(act["license_id"], []).append(act)
    excl_by_license = {}
    for exc in exclusions:
        excl_by_license.setdefault(exc["license_id"], []).append(exc)
    auc_by_license = {}
    for auc in auctions:
        auc_by_license.setdefault(auc["license_id"], []).append(auc)

    default_rate = policy["default_rate_cents_per_mhz_hour"]
    primary_priority = policy["primary_priority"]
    dormant_priority = policy["dormant_owner_priority"]

    for lid in sorted(licenses):
        lic = licenses[lid]
        owner = lic["owner_party_id"]
        lic_auctions = auc_by_license.get(lid, [])
        for cell in sorted(lic["cells"]):
            cell_grants = [g for g in grants_by_license.get(lid, []) if cell in g["cells"]]
            cell_acts = [a for a in acts_by_license.get(lid, []) if cell in a["cells"]]
            cell_excls = [e for e in excl_by_license.get(lid, []) if cell in e["cells"]]

            time_cuts = {lic["start"], lic["end"]}
            freq_cuts = {lic["low_khz"], lic["high_khz"]}
            for item in cell_grants:
                time_cuts.update((item["start"], item["end"]))
                freq_cuts.update((item["usable_low"], item["usable_high"]))
            for item in cell_acts + cell_excls:
                time_cuts.update((item["start"], item["end"]))
                freq_cuts.update((item["low_khz"], item["high_khz"]))
            for item in lic_auctions:
                time_cuts.update((item["start"], item["end"]))
            time_points = sorted(
                t for t in time_cuts if lic["start"] <= t <= lic["end"]
            )
            freq_points = sorted(
                f for f in freq_cuts if lic["low_khz"] <= f <= lic["high_khz"]
            )

            for t_start, t_end in zip(time_points, time_points[1:]):
                if t_end <= t_start:
                    continue
                time_acts = [
                    a for a in cell_acts if a["start"] <= t_start and a["end"] >= t_end
                ]
                time_auctions = [
                    a for a in lic_auctions if a["start"] <= t_start and a["end"] >= t_end
                ]
                for f_low, f_high in zip(freq_points, freq_points[1:]):
                    if f_high <= f_low:
                        continue
                    slices.append(
                        build_slice(
                            lic,
                            cell,
                            t_start,
                            t_end,
                            f_low,
                            f_high,
                            owner,
                            cell_grants,
                            time_acts,
                            cell_excls,
                            time_auctions,
                            default_rate,
                            primary_priority,
                            dormant_priority,
                        )
                    )
    slices.sort(
        key=lambda s: (
            s["license_id"],
            s["cell_id"],
            s["start"],
            s["low_khz"],
            s["end"],
            s["high_khz"],
        )
    )
    return slices


def build_slice(
    lic,
    cell,
    t_start,
    t_end,
    f_low,
    f_high,
    owner,
    cell_grants,
    time_acts,
    cell_excls,
    time_auctions,
    default_rate,
    primary_priority,
    dormant_priority,
):
    covering_acts = sorted(
        a["id"]
        for a in time_acts
        if a["low_khz"] <= f_low and a["high_khz"] >= f_high
    )
    candidates = []
    owner_source = "OWNER:" + lic["license_id"]
    owner_priority = dormant_priority
    owner_primary = False
    if covering_acts:
        owner_source = covering_acts[0]
        owner_priority = primary_priority
        owner_primary = True
    candidates.append(
        {
            "priority": owner_priority,
            "source_id": owner_source,
            "party_id": owner,
            "grant": None,
            "primary": owner_primary,
        }
    )
    for grant in cell_grants:
        if (
            grant["start"] <= t_start
            and grant["end"] >= t_end
            and grant["usable_low"] <= f_low
            and grant["usable_high"] >= f_high
        ):
            candidates.append(
                {
                    "priority": grant["priority"],
                    "source_id": grant["grant_id"],
                    "party_id": grant["party_id"],
                    "grant": grant,
                    "primary": False,
                }
            )

    applicable = [
        exc
        for exc in cell_excls
        if exc["start"] <= t_start
        and exc["end"] >= t_end
        and exc["low_khz"] <= f_low
        and exc["high_khz"] >= f_high
    ]
    excluded_parties = set()
    exclude_all = False
    for exc in applicable:
        if exc["party_id"] == "*":
            exclude_all = True
        else:
            excluded_parties.add(exc["party_id"])
    if exclude_all:
        candidates = []
    else:
        candidates = [c for c in candidates if c["party_id"] not in excluded_parties]

    duration = t_end - t_start
    width = f_high - f_low

    auction_id = "default"
    rate = default_rate
    if time_auctions:
        best = max(time_auctions, key=lambda a: (a["start"], a["auction_id"]))
        auction_id = best["auction_id"]
        rate = best["rate_cents_per_mhz_hour"]

    record = {
        "license_id": lic["license_id"],
        "cell_id": cell,
        "start": format_ts(t_start),
        "end": format_ts(t_end),
        "low_khz": f_low,
        "high_khz": f_high,
        "duration_seconds": duration,
        "width_khz": width,
        "auction_id": auction_id,
        "rate_cents_per_mhz_hour": rate,
    }

    if not candidates:
        record.update(
            {
                "winner_party_id": None,
                "winner_source_id": None,
                "winner_priority": None,
                "preempted_source_ids": [],
                "gross_cents": 0,
                "winner_cents": 0,
                "owner_cents": 0,
            }
        )
        record["_winner_grant"] = None
        record["_winner_primary"] = False
        return record

    winner = min(
        candidates, key=lambda c: (c["priority"], c["source_id"], c["party_id"])
    )
    preempted = sorted(
        {c["source_id"] for c in candidates if c is not winner}
    )
    gross = round_half_up(
        Decimal(duration * width * rate) / Decimal(SECONDS_PER_HOUR * KHZ_PER_MHZ)
    )
    if winner["grant"] is None:
        winner_cents = gross
        owner_cents = 0
    else:
        winner_cents = round_half_up(
            Decimal(gross * winner["grant"]["share_bps"]) / Decimal(10000)
        )
        owner_cents = gross - winner_cents

    record.update(
        {
            "winner_party_id": winner["party_id"],
            "winner_source_id": winner["source_id"],
            "winner_priority": winner["priority"],
            "preempted_source_ids": preempted,
            "gross_cents": gross,
            "winner_cents": winner_cents,
            "owner_cents": owner_cents,
        }
    )
    record["_winner_grant"] = winner["grant"]
    record["_winner_primary"] = winner["primary"]
    return record


SLICE_FIELDS = (
    "license_id",
    "cell_id",
    "start",
    "end",
    "low_khz",
    "high_khz",
    "duration_seconds",
    "width_khz",
    "winner_party_id",
    "winner_source_id",
    "winner_priority",
    "preempted_source_ids",
    "auction_id",
    "rate_cents_per_mhz_hour",
    "gross_cents",
    "winner_cents",
    "owner_cents",
)

PREEMPTION_FIELDS = (
    "license_id",
    "cell_id",
    "start",
    "end",
    "low_khz",
    "high_khz",
    "winner_party_id",
    "winner_source_id",
    "winner_priority",
    "preempted_source_ids",
)


# -------------------------------------------------------------- settlement

def allocate_correction(total, party_gross):
    """Signed largest-remainder allocation over parties with positive gross."""
    positives = {p: g for p, g in party_gross.items() if g > 0}
    license_gross = sum(positives.values())
    if license_gross <= 0 or total == 0:
        return {}
    magnitude = abs(total)
    sign = 1 if total > 0 else -1
    exact = {}
    floors = {}
    for party, gross in positives.items():
        share = Decimal(magnitude * gross) / Decimal(license_gross)
        floor = int(share)
        floors[party] = floor
        exact[party] = share - floor
    residual = magnitude - sum(floors.values())
    order = sorted(positives, key=lambda p: (-exact[p], p))
    for party in order[:residual]:
        floors[party] += 1
    return {party: sign * amount for party, amount in floors.items()}


def settle(slices, licenses, corrections, grants):
    gross = {}
    won_counts = {}
    for sl in slices:
        if sl["winner_party_id"] is None:
            continue
        lid = sl["license_id"]
        winner = sl["winner_party_id"]
        gross[(lid, winner)] = gross.get((lid, winner), 0) + sl["winner_cents"]
        won_counts[winner] = won_counts.get(winner, 0) + 1
        if sl["_winner_grant"] is not None:
            owner = licenses[lid]["owner_party_id"]
            gross[(lid, owner)] = gross.get((lid, owner), 0) + sl["owner_cents"]

    allocations = []
    correction_by_pair = {}
    for lid in sorted(licenses):
        party_gross = {
            party: amount for (lic, party), amount in gross.items() if lic == lid
        }
        total = corrections.get(lid, 0)
        allocated = allocate_correction(total, party_gross)
        positive_parties = {p for p, g in party_gross.items() if g > 0}
        if not positive_parties and total != 0:
            owner = licenses[lid]["owner_party_id"]
            allocated = {owner: total}
        for party in sorted(positive_parties | set(allocated)):
            amount = allocated.get(party, 0)
            party_total = party_gross.get(party, 0)
            correction_by_pair[(lid, party)] = amount
            allocations.append(
                {
                    "license_id": lid,
                    "party_id": party,
                    "gross_cents": party_total,
                    "correction_cents": amount,
                    "net_cents": party_total + amount,
                }
            )

    party_grants = {}
    for grant in grants:
        party_grants.setdefault(grant["party_id"], set()).add(grant["grant_id"])
    preempt_counts = {}
    for party, sources in party_grants.items():
        count = 0
        for sl in slices:
            if sources.intersection(sl["preempted_source_ids"]):
                count += 1
        preempt_counts[party] = count

    parties_seen = {party for _, party in gross} | {
        party for _, party in correction_by_pair
    }
    settlements = []
    for party in sorted(parties_seen):
        party_licenses = sorted(
            {lid for (lid, p) in gross if p == party}
            | {lid for (lid, p), amt in correction_by_pair.items() if p == party and amt}
        )
        total_gross = sum(amt for (lid, p), amt in gross.items() if p == party)
        total_corr = sum(
            amt for (lid, p), amt in correction_by_pair.items() if p == party
        )
        if total_gross == 0 and total_corr == 0:
            continue
        settlements.append(
            {
                "party_id": party,
                "license_ids": party_licenses,
                "gross_cents": total_gross,
                "correction_cents": total_corr,
                "net_cents": total_gross + total_corr,
                "won_slice_count": won_counts.get(party, 0),
                "preempted_slice_count": preempt_counts.get(party, 0),
            }
        )
    allocations.sort(key=lambda a: (a["license_id"], a["party_id"]))
    return settlements, allocations


def build_audit(settlements):
    previous = ZERO_HASH
    entries = []
    for row in settlements:
        canonical = json.dumps(
            row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        entry_hash = hashlib.sha256(
            (previous + canonical).encode("utf-8")
        ).hexdigest()
        entries.append(
            {
                "party_id": row["party_id"],
                "previous_hash": previous,
                "entry_hash": entry_hash,
            }
        )
        previous = entry_hash
    return {"entries": entries, "final_hash": previous}


# ------------------------------------------------------------------- driver

def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: clear_spectrum.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)

    policy = read_json(os.path.join(data_dir, "policy.json"), {})
    party_rows = read_json(os.path.join(data_dir, "parties.json"), [])
    parties = {}
    for row in party_rows:
        if isinstance(row, dict) and isinstance(row.get("party_id"), str):
            parties[row["party_id"]] = row.get("name")

    license_rows = read_jsonl(os.path.join(data_dir, "licenses.jsonl"))
    grant_rows = read_jsonl(os.path.join(data_dir, "grant_revisions.jsonl"))
    activation_rows = read_jsonl(os.path.join(data_dir, "activation_events.jsonl"))
    exclusion_rows = read_jsonl(os.path.join(data_dir, "exclusions.jsonl"))
    guard_rows = read_jsonl(os.path.join(data_dir, "guard_bands.jsonl"))
    auction_rows = read_jsonl(os.path.join(data_dir, "auction_results.jsonl"))
    correction_rows = read_jsonl(os.path.join(data_dir, "corrections.jsonl"))

    issues = []
    licenses = load_licenses(license_rows, parties, issues)
    guards = load_guard_bands(guard_rows, issues)
    grant_decisions = resolve_revisions(
        grant_rows, "grant_id", "REVISION_TIE_CONFLICT", "INVALID_GRANT", issues
    )
    grants, revision_decisions = load_grants(
        grant_decisions, licenses, parties, issues
    )
    activations = load_box_rows(
        activation_rows, licenses, "activation_id", "INVALID_ACTIVATION", issues
    )
    exclusions = load_box_rows(
        exclusion_rows,
        licenses,
        "exclusion_id",
        "INVALID_EXCLUSION",
        issues,
        parties=parties,
    )
    auction_decisions = resolve_revisions(
        auction_rows, "auction_id", "AUCTION_TIE_CONFLICT", "INVALID_AUCTION", issues
    )
    auctions = load_auctions(auction_decisions, licenses, issues)
    corrections = load_corrections(correction_rows, licenses, issues)

    slices = build_slices(
        licenses, grants, activations, exclusions, auctions, guards, policy
    )
    settlements, allocations = settle(slices, licenses, corrections, grants)

    issue_rows = sorted(
        ({"code": code, "record_id": rid} for code, rid in issues),
        key=lambda i: (i["code"], i["record_id"]),
    )

    input_files = []
    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if os.path.isfile(path):
            input_files.append(
                {
                    "name": name,
                    "sha256": sha256_file(path),
                    "bytes": os.path.getsize(path),
                }
            )

    write_report(
        out_dir,
        "manifest.json",
        {
            "engine_version": policy.get("engine_version"),
            "input_files": input_files,
            "valid_license_count": len(licenses),
            "effective_grant_count": len(grants),
            "slice_count": len(slices),
        },
    )
    write_report(
        out_dir,
        "data_quality.json",
        {
            "input_file_count": len(input_files),
            "record_counts": {
                "licenses": len(license_rows),
                "grant_revisions": len(grant_rows),
                "activations": len(activation_rows),
                "exclusions": len(exclusion_rows),
                "guard_bands": len(guard_rows),
                "auction_revisions": len(auction_rows),
                "corrections": len(correction_rows),
            },
            "issue_count": len(issue_rows),
            "issues": issue_rows,
        },
    )
    write_report(
        out_dir,
        "grant_ledger.json",
        {
            "effective_grants": [
                {
                    "grant_id": g["grant_id"],
                    "record_id": g["record_id"],
                    "license_id": g["license_id"],
                    "party_id": g["party_id"],
                    "cells": g["cells"],
                    "low_khz": g["low_khz"],
                    "high_khz": g["high_khz"],
                    "start": format_ts(g["start"]),
                    "end": format_ts(g["end"]),
                    "priority": g["priority"],
                    "share_bps": g["share_bps"],
                }
                for g in grants
            ],
            "revision_decisions": revision_decisions,
        },
    )
    write_report(
        out_dir,
        "spectrum_slice_ledger.json",
        {"slices": [{k: sl[k] for k in SLICE_FIELDS} for sl in slices]},
    )
    write_report(
        out_dir,
        "preemption_ledger.json",
        {
            "preemptions": [
                {k: sl[k] for k in PREEMPTION_FIELDS}
                for sl in slices
                if sl["preempted_source_ids"] or sl["_winner_primary"]
            ]
        },
    )
    write_report(out_dir, "party_settlements.json", {"parties": settlements})
    write_report(out_dir, "auction_adjustments.json", {"allocations": allocations})

    exceptions = [dict(row) for row in issue_rows]
    material = policy.get("material_cents", 0)
    for row in settlements:
        if abs(row["net_cents"]) >= material:
            exceptions.append(
                {
                    "code": "MATERIAL_SETTLEMENT",
                    "record_id": row["party_id"],
                    "net_cents": row["net_cents"],
                }
            )
    exceptions.sort(key=lambda e: (e["code"], e["record_id"]))
    write_report(out_dir, "exception_register.json", {"exceptions": exceptions})
    write_report(out_dir, "audit_trace.json", build_audit(settlements))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
