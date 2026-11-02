#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path
from typing import Any


def ts(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def iso(value: int) -> str:
    return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rounded(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def contained(row: dict[str, Any], license_row: dict[str, Any]) -> bool:
    return (
        ts(license_row["start"]) <= ts(row["start"]) < ts(row["end"]) <= ts(license_row["end"])
        and int(license_row["low_khz"]) <= int(row["low_khz"]) < int(row["high_khz"]) <= int(license_row["high_khz"])
        and bool(row.get("cells"))
        and set(row["cells"]) <= set(license_row["cells"])
    )


def resolve(rows: list[dict[str, Any]], group_key: str, conflict_code: str, issues: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row[group_key]].append(row)
    winners: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for group_id in sorted(groups):
        ordered = sorted(groups[group_id], key=lambda row: (int(row["revision"]), ts(row["recorded_at"]), row["record_id"]))
        winner = ordered[-1]
        peers = [row for row in ordered if int(row["revision"]) == int(winner["revision"]) and row["recorded_at"] == winner["recorded_at"]]
        payloads = set()
        for row in peers:
            payload = {key: value for key, value in row.items() if key != "record_id"}
            if isinstance(payload.get("cells"), list):
                payload["cells"] = sorted(payload["cells"])
            payloads.add(canonical(payload))
        if len(payloads) > 1:
            issues.append({"code": conflict_code, "record_id": group_id})
        decisions.append({group_key: group_id, "winner_record_id": winner["record_id"], "discarded_record_ids": sorted(row["record_id"] for row in ordered if row is not winner)})
        if winner["status"] == "active":
            winners.append(winner)
    return winners, decisions


def allocate_signed(amount: int, weights: list[tuple[str, int]], owner: str) -> dict[str, int]:
    if not weights:
        return {owner: amount}
    result = {party: 0 for party, _ in weights}
    if amount == 0:
        return result
    denominator = sum(weight for _, weight in weights)
    sign, magnitude = (1 if amount > 0 else -1), abs(amount)
    residues: list[tuple[Decimal, str]] = []
    spent = 0
    for party, weight in weights:
        exact = Decimal(magnitude * weight) / Decimal(denominator)
        floor = int(exact.to_integral_value(rounding=ROUND_FLOOR))
        result[party] = sign * floor
        residues.append((exact - floor, party))
        spent += floor
    for _, party in sorted(residues, key=lambda item: (-item[0], item[1]))[: magnitude - spent]:
        result[party] += sign
    return result


def derive(data: Path) -> dict[str, Any]:
    policy = read_json(data / "policy.json")
    parties_list = read_json(data / "parties.json")
    party_ids = {row["party_id"] for row in parties_list}
    raw_licenses = read_jsonl(data / "licenses.jsonl")
    raw_grants = read_jsonl(data / "grant_revisions.jsonl")
    raw_activations = read_jsonl(data / "activation_events.jsonl")
    raw_exclusions = read_jsonl(data / "exclusions.jsonl")
    raw_guards = read_jsonl(data / "guard_bands.jsonl")
    raw_auctions = read_jsonl(data / "auction_results.jsonl")
    raw_corrections = read_jsonl(data / "corrections.jsonl")
    issues: list[dict[str, Any]] = []

    licenses: dict[str, dict[str, Any]] = {}
    for row in raw_licenses:
        try:
            valid = row["owner_party_id"] in party_ids and bool(row["cells"]) and ts(row["start"]) < ts(row["end"]) and int(row["low_khz"]) < int(row["high_khz"])
        except (KeyError, TypeError, ValueError):
            valid = False
        if not valid or row["license_id"] in licenses:
            issues.append({"code": "INVALID_LICENSE", "record_id": row.get("license_id", "?")})
        else:
            licenses[row["license_id"]] = row

    grant_winners, grant_decisions = resolve(raw_grants, "grant_id", "REVISION_TIE_CONFLICT", issues)
    grants: list[dict[str, Any]] = []
    for row in grant_winners:
        license_id = row.get("license_id")
        license_row = licenses.get(license_id) if isinstance(license_id, str) else None
        try:
            valid = license_row is not None and row["party_id"] in party_ids and 0 <= int(row["share_bps"]) <= 10000 and contained(row, license_row)
        except (KeyError, TypeError, ValueError):
            valid = False
        if valid:
            grants.append(row)
        else:
            issues.append({"code": "INVALID_GRANT", "record_id": row.get("grant_id", "?")})
    grants.sort(key=lambda row: (row["license_id"], row["party_id"], ts(row["start"]), int(row["low_khz"]), row["grant_id"]))

    activations: list[dict[str, Any]] = []
    for row in raw_activations:
        try:
            valid = row["license_id"] in licenses and contained(row, licenses[row["license_id"]])
        except (KeyError, TypeError, ValueError):
            valid = False
        if valid:
            activations.append(row)
        else:
            issues.append({"code": "INVALID_ACTIVATION", "record_id": row.get("activation_id", "?")})

    exclusions: list[dict[str, Any]] = []
    for row in raw_exclusions:
        try:
            valid = row["license_id"] in licenses and (row["party_id"] == "*" or row["party_id"] in party_ids) and contained(row, licenses[row["license_id"]])
        except (KeyError, TypeError, ValueError):
            valid = False
        if valid:
            exclusions.append(row)
        else:
            issues.append({"code": "INVALID_EXCLUSION", "record_id": row.get("exclusion_id", "?")})

    guards: dict[str, int] = {}
    guard_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in raw_guards:
        guard_rows[row.get("license_id", "?")].append(row)
    for license_id, rows in sorted(guard_rows.items()):
        valid_rows = [row for row in rows if license_id in licenses and isinstance(row.get("guard_khz"), int) and int(row["guard_khz"]) >= 0]
        if len(rows) != 1 or len(valid_rows) != len(rows):
            issues.append({"code": "INVALID_GUARD_BAND", "record_id": license_id})
        if valid_rows:
            chosen = min(valid_rows, key=lambda row: row["guard_id"])
            guards[license_id] = int(chosen["guard_khz"])

    auction_winners, _ = resolve(raw_auctions, "auction_id", "AUCTION_TIE_CONFLICT", issues)
    auctions: list[dict[str, Any]] = []
    for row in auction_winners:
        license_id = row.get("license_id")
        license_row = licenses.get(license_id) if isinstance(license_id, str) else None
        try:
            valid = license_row is not None and ts(license_row["start"]) <= ts(row["start"]) < ts(row["end"]) <= ts(license_row["end"]) and int(row["rate_cents_per_mhz_hour"]) >= 0
        except (KeyError, TypeError, ValueError):
            valid = False
        if valid:
            auctions.append(row)
        else:
            issues.append({"code": "INVALID_AUCTION", "record_id": row.get("auction_id", "?")})
    auctions.sort(key=lambda row: (row["license_id"], ts(row["start"]), row["auction_id"]))

    correction_totals: dict[str, int] = defaultdict(int)
    for row in raw_corrections:
        try:
            valid = row["license_id"] in licenses
            amount = int(row["amount_cents"])
        except (KeyError, TypeError, ValueError):
            valid, amount = False, 0
        if valid:
            correction_totals[row["license_id"]] += amount
        else:
            issues.append({"code": "INVALID_CORRECTION", "record_id": row.get("correction_id", "?")})

    grants_by_license: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in grants:
        grants_by_license[row["license_id"]].append(row)
    activation_by_license: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in activations:
        activation_by_license[row["license_id"]].append(row)
    activation_ids = {row["activation_id"] for row in activations}
    exclusion_by_license: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in exclusions:
        exclusion_by_license[row["license_id"]].append(row)
    auctions_by_license: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in auctions:
        auctions_by_license[row["license_id"]].append(row)

    slices: list[dict[str, Any]] = []
    preemptions: list[dict[str, Any]] = []
    gross: dict[tuple[str, str], int] = defaultdict(int)
    won_counts: dict[str, int] = defaultdict(int)
    preempted_counts: dict[str, int] = defaultdict(int)
    grant_party = {row["grant_id"]: row["party_id"] for row in grants}

    for license_id, license_row in sorted(licenses.items()):
        owner = license_row["owner_party_id"]
        relevant_grants = grants_by_license[license_id]
        relevant_acts = activation_by_license[license_id]
        relevant_exclusions = exclusion_by_license[license_id]
        relevant_auctions = auctions_by_license[license_id]
        for cell in sorted(set(license_row["cells"])):
            time_cuts = {ts(license_row["start"]), ts(license_row["end"])}
            freq_cuts = {int(license_row["low_khz"]), int(license_row["high_khz"])}
            for row in relevant_grants:
                if cell in row["cells"]:
                    left = int(row["low_khz"]) + guards.get(license_id, 0)
                    right = int(row["high_khz"]) - guards.get(license_id, 0)
                    time_cuts.update((ts(row["start"]), ts(row["end"])))
                    if left < right:
                        freq_cuts.update((left, right))
            for row in relevant_acts + relevant_exclusions:
                if cell in row["cells"]:
                    time_cuts.update((ts(row["start"]), ts(row["end"])))
                    freq_cuts.update((int(row["low_khz"]), int(row["high_khz"])))
            for row in relevant_auctions:
                time_cuts.update((ts(row["start"]), ts(row["end"])))
            times, freqs = sorted(time_cuts), sorted(freq_cuts)
            for start, end in zip(times, times[1:]):
                for low, high in zip(freqs, freqs[1:]):
                    if start >= end or low >= high:
                        continue
                    covering_acts = [row for row in relevant_acts if cell in row["cells"] and ts(row["start"]) <= start and end <= ts(row["end"]) and int(row["low_khz"]) <= low and high <= int(row["high_khz"])]
                    owner_source = min((row["activation_id"] for row in covering_acts), default=f"OWNER:{license_id}")
                    owner_priority = int(policy["primary_priority"] if covering_acts else policy["dormant_owner_priority"])
                    candidates: list[dict[str, Any]] = [{"party": owner, "source": owner_source, "priority": owner_priority, "share": 10000, "grant": False}]
                    for row in relevant_grants:
                        usable_low = int(row["low_khz"]) + guards.get(license_id, 0)
                        usable_high = int(row["high_khz"]) - guards.get(license_id, 0)
                        if cell in row["cells"] and ts(row["start"]) <= start and end <= ts(row["end"]) and usable_low <= low and high <= usable_high:
                            candidates.append({"party": row["party_id"], "source": row["grant_id"], "priority": int(row["priority"]), "share": int(row["share_bps"]), "grant": True})
                    kept = []
                    for candidate in candidates:
                        blocked = any(cell in row["cells"] and ts(row["start"]) <= start and end <= ts(row["end"]) and int(row["low_khz"]) <= low and high <= int(row["high_khz"]) and row["party_id"] in ("*", candidate["party"]) for row in relevant_exclusions)
                        if not blocked:
                            kept.append(candidate)
                    winner = min(kept, key=lambda row: (row["priority"], row["source"], row["party"])) if kept else None
                    preempted = sorted(row["source"] for row in kept if row is not winner)
                    matching_auctions = [row for row in relevant_auctions if ts(row["start"]) <= start and end <= ts(row["end"])]
                    auction = max(matching_auctions, key=lambda row: (ts(row["start"]), row["auction_id"])) if matching_auctions else None
                    auction_id = auction["auction_id"] if auction else "default"
                    rate = int(auction["rate_cents_per_mhz_hour"] if auction else policy["default_rate_cents_per_mhz_hour"])
                    duration, width = end - start, high - low
                    slice_gross = rounded(Decimal(duration * width * rate) / Decimal(3600 * 1000)) if winner else 0
                    winner_cents = rounded(Decimal(slice_gross * winner["share"]) / Decimal(10000)) if winner else 0
                    owner_cents = slice_gross - winner_cents if winner and winner["grant"] else 0
                    result = {"license_id": license_id, "cell_id": cell, "start": iso(start), "end": iso(end), "low_khz": low, "high_khz": high, "duration_seconds": duration, "width_khz": width, "winner_party_id": winner["party"] if winner else None, "winner_source_id": winner["source"] if winner else None, "winner_priority": winner["priority"] if winner else None, "preempted_source_ids": preempted, "auction_id": auction_id, "rate_cents_per_mhz_hour": rate, "gross_cents": slice_gross, "winner_cents": winner_cents, "owner_cents": owner_cents}
                    slices.append(result)
                    if winner:
                        gross[(license_id, winner["party"])] += winner_cents
                        won_counts[winner["party"]] += 1
                        if winner["grant"]:
                            gross[(license_id, owner)] += owner_cents
                    for party in {grant_party[source] for source in preempted if source in grant_party}:
                        preempted_counts[party] += 1
                    if preempted or (winner and winner["source"] in activation_ids):
                        preemptions.append({key: result[key] for key in ("license_id", "cell_id", "start", "end", "low_khz", "high_khz", "winner_party_id", "winner_source_id", "winner_priority", "preempted_source_ids")})

    slices.sort(key=lambda row: (row["license_id"], row["cell_id"], row["start"], row["low_khz"], row["end"], row["high_khz"]))
    preemptions.sort(key=lambda row: (row["license_id"], row["cell_id"], row["start"], row["low_khz"], row["end"], row["high_khz"]))
    allocations: list[dict[str, Any]] = []
    correction_by_party: dict[str, int] = defaultdict(int)
    for license_id, license_row in sorted(licenses.items()):
        weights = sorted((party, amount) for (lid, party), amount in gross.items() if lid == license_id and amount > 0)
        allocated = allocate_signed(correction_totals.get(license_id, 0), weights, license_row["owner_party_id"])
        for party in sorted(allocated):
            before = gross.get((license_id, party), 0)
            correction = allocated[party]
            allocations.append({"license_id": license_id, "party_id": party, "gross_cents": before, "correction_cents": correction, "net_cents": before + correction})
            correction_by_party[party] += correction

    settlement_parties = sorted({party for _, party in gross} | set(correction_by_party))
    settlements: list[dict[str, Any]] = []
    for party in settlement_parties:
        license_ids = sorted({license_id for (license_id, item_party), amount in gross.items() if item_party == party and amount != 0} | {row["license_id"] for row in allocations if row["party_id"] == party and row["correction_cents"] != 0})
        before = sum(amount for (license_id, item_party), amount in gross.items() if item_party == party)
        correction = correction_by_party[party]
        settlements.append({"party_id": party, "license_ids": license_ids, "gross_cents": before, "correction_cents": correction, "net_cents": before + correction, "won_slice_count": won_counts[party], "preempted_slice_count": preempted_counts[party]})

    issues.sort(key=lambda row: (row["code"], row["record_id"]))
    exceptions: list[dict[str, Any]] = [dict(row) for row in issues]
    for row in settlements:
        if abs(row["net_cents"]) >= int(policy["material_cents"]):
            exceptions.append({"code": "MATERIAL_SETTLEMENT", "record_id": row["party_id"], "net_cents": row["net_cents"]})
    exceptions.sort(key=lambda row: (row["code"], row["record_id"]))
    previous = "0" * 64
    trace = []
    for row in settlements:
        entry = hashlib.sha256((previous + canonical(row)).encode()).hexdigest()
        trace.append({"party_id": row["party_id"], "previous_hash": previous, "entry_hash": entry})
        previous = entry
    files = sorted(path for path in data.iterdir() if path.is_file())
    record_counts = {"licenses": len(raw_licenses), "grant_revisions": len(raw_grants), "activations": len(raw_activations), "exclusions": len(raw_exclusions), "guard_bands": len(raw_guards), "auction_revisions": len(raw_auctions), "corrections": len(raw_corrections)}
    return {
        "manifest.json": {"engine_version": policy["engine_version"], "input_files": [{"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size} for path in files], "valid_license_count": len(licenses), "effective_grant_count": len(grants), "slice_count": len(slices)},
        "data_quality.json": {"input_file_count": len(files), "record_counts": record_counts, "issue_count": len(issues), "issues": issues},
        "grant_ledger.json": {"effective_grants": grants, "revision_decisions": grant_decisions},
        "spectrum_slice_ledger.json": {"slices": slices},
        "preemption_ledger.json": {"preemptions": preemptions},
        "party_settlements.json": {"parties": settlements},
        "auction_adjustments.json": {"allocations": allocations},
        "exception_register.json": {"exceptions": exceptions},
        "audit_trace.json": {"entries": trace, "final_hash": previous},
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: clear_spectrum.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    data, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for name, value in derive(data).items():
        write_json(out / name, value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
