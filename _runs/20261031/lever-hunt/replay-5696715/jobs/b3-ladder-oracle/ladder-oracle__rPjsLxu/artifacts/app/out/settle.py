#!/usr/bin/env python3
"""Reference oracle for 85ba8b43-fa7c-524d-8211-e73c430afb36.

Independent implementation written from the /app/data written contract (the
00_pipeline_contract_overview.md plus the spec_stage_s1..s9 files, the binary
reading notes, and the xlsx / pdf / docx inputs). Reads the arena-ladder season
export from DATA_DIR (default /app/data), runs the corrected S1..S9 settlement,
and writes each declared artifact to OUT_DIR (default /app/out). Standard library
only; no seeds, no network, no reads outside DATA_DIR and the declared outputs.
"""

from __future__ import annotations

import csv as _csv
import hashlib as _hashlib
import io as _io
import json as _json
import re as _re
import sys as _sys
import zlib as _zlib
import zipfile as _zip
import xml.etree.ElementTree as _xml
from datetime import date as _date
from decimal import Decimal as _Dec, getcontext as _ctx, ROUND_HALF_EVEN as _HE
from pathlib import Path as _Path

_ctx().prec = 50

# ---- domain vocabulary (from tier_server_topology.json / stratum_enumeration) --
_TIER_LIST = ("BRONZE", "SILVER", "GOLD")
_SERVER_LIST = ("NA", "EU", "APAC")
_STRATUM_LIST = tuple(f"{tier}-{srv}" for tier in _TIER_LIST for srv in _SERVER_LIST)
_SCALE_EXP = {"CRD": 0, "TKN": 3, "GLM": 6, "ORE": 0}
_LADDER_WINDOW = 40
_CAP_TEXT = "240"  # reported diagnostic ceiling; inactive for this census
_PARAM_ROWS = ("a_s", "b_s", "tau_s", "recovery_s")
_SLUG_ORDER = ("bro_na", "bro_eu", "bro_ap", "sil_na", "sil_eu",
               "sil_ap", "gld_na", "gld_eu", "gld_ap")
_SLUG_OF = dict(zip(_STRATUM_LIST, _SLUG_ORDER))
_CORE = ("population.csv", "weights.csv", "payout.csv", "metrics.json")

# ---- input file names (discovered by reading each file's contents) ------------
_FILE_MATCHES = "ladder_match_capture_s1.csv"
_FILE_LEDGER = "verdict_amendment_history.tsv"
_FILE_FRAME = "cohort_draw_register.psv"
_FILE_DRIFT = "season_patch_reference.csv"
_FILE_ACCOUNTS = "account_tier_crosswalk.csv"
_FILE_PROFILE = "season_profile.json"
_FILE_GRID = "ladder_tuning_grid.xlsx"
_FILE_POLICY = "payout_cost_policy.pdf"
_FILE_ADDENDUM = "settlement_levy_addendum.docx"


def dec(value) -> _Dec:
    return _Dec(str(value).strip())


def round6(value) -> _Dec:
    return dec(value).quantize(_Dec("0.000001"), rounding=_HE)


def round8(value) -> _Dec:
    return dec(value).quantize(_Dec("0.00000001"), rounding=_HE)


def whole(value) -> int:
    return int(dec(value).quantize(_Dec("1"), rounding=_HE))


def to_logit(prob) -> _Dec:
    prob = dec(prob)
    return (prob / (_Dec(1) - prob)).ln()


def from_logodds(score) -> _Dec:
    return _Dec(1) / (_Dec(1) + (-dec(score)).exp())


def pin_prob(prob: _Dec) -> _Dec:
    floor_p, ceil_p = _Dec("0.000001"), _Dec("0.999999")
    return floor_p if prob < floor_p else (ceil_p if prob > ceil_p else prob)


def load_delimited(path, sep):
    with open(path, encoding="utf-8", newline="") as handle:
        reader = _csv.reader(handle, delimiter=sep)
        columns = next(reader)
        return [dict(zip(columns, record)) for record in reader if record]


def _column_number(cell_ref):
    alpha = "".join(ch for ch in cell_ref if ch.isalpha())
    acc = 0
    for ch in alpha:
        acc = acc * 26 + (ord(ch.upper()) - 64)
    return acc - 1


def load_workbook(path):
    archive = _zip.ZipFile(path)
    try:
        pool = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings_root = _xml.fromstring(archive.read("xl/sharedStrings.xml"))
            for entry in strings_root.findall("{*}si"):
                pool.append("".join(node.text or "" for node in entry.findall(".//{*}t")))
        present = archive.namelist()
        book = _xml.fromstring(archive.read("xl/workbook.xml"))
        sheet_names = [tag.get("name") for tag in book.find("{*}sheets")]
        result = {}
        for position, sheet_name in enumerate(sheet_names, start=1):
            part = f"xl/worksheets/sheet{position}.xml"
            if part not in present:
                continue
            grid = []
            sheet_root = _xml.fromstring(archive.read(part))
            for row_node in sheet_root.findall(".//{*}row"):
                bag = {}
                width = -1
                for cell in row_node.findall("{*}c"):
                    idx = _column_number(cell.get("r", ""))
                    kind = cell.get("t", "")
                    if kind == "inlineStr":
                        text = "".join(t.text or "" for t in cell.findall(".//{*}t"))
                    elif kind == "s":
                        holder = cell.find("{*}v")
                        text = pool[int(holder.text)] if holder is not None and holder.text else ""
                    else:
                        holder = cell.find("{*}v")
                        text = holder.text if holder is not None and holder.text is not None else ""
                    bag[idx] = text
                    width = idx if idx > width else width
                grid.append([bag.get(col, "") for col in range(width + 1)])
            result[sheet_name] = grid
        return result
    finally:
        archive.close()


def extract_pdf_lines(path):
    blob = _Path(path).read_bytes()
    collected = []
    for chunk in _re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", blob, _re.S):
        payload = chunk.group(1)
        try:
            payload = _zlib.decompress(payload)
        except _zlib.error:
            pass
        for token in _re.finditer(rb"\(((?:\\.|[^\\()])*)\)\s*Tj", payload):
            literal = token.group(1)
            literal = literal.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
            collected.append(literal.decode("latin-1"))
    return collected


def extract_docx_paragraphs(path):
    archive = _zip.ZipFile(path)
    try:
        body = _xml.fromstring(archive.read("word/document.xml"))
    finally:
        archive.close()
    return ["".join(t.text or "" for t in para.findall(".//{*}t"))
            for para in body.findall(".//{*}p")]


def gather(data_dir):
    root = _Path(data_dir)
    raw_matches = load_delimited(root / _FILE_MATCHES, ",")
    revisions = load_delimited(root / _FILE_LEDGER, "\t")
    draw_frame = load_delimited(root / _FILE_FRAME, "|")
    drift_rows = load_delimited(root / _FILE_DRIFT, ",")
    account_rows = load_delimited(root / _FILE_ACCOUNTS, ",")
    profile = _json.loads((root / _FILE_PROFILE).read_text(encoding="utf-8"))

    # --- S4/S6: LIVE workbook sheet selected by B1 == calibration_version --------
    wanted_tag = profile["calibration_version"]
    live_grid = None
    for _sheet, grid in load_workbook(root / _FILE_GRID).items():
        if grid and len(grid[0]) >= 2 and grid[0][1].strip() == wanted_tag:
            live_grid = grid
            break
    if live_grid is None:
        raise ValueError("LIVE tuning sheet not found")

    ore_gain = None
    for line in live_grid:
        if line and line[0].strip() == "ore_to_ledger_gain":
            ore_gain = dec(line[1])
            break

    stratum_header = None
    for offset, line in enumerate(live_grid):
        if any(cell.strip() in _STRATUM_LIST for cell in line):
            stratum_header = offset
            break
    column_for = {}
    for pos, cell in enumerate(live_grid[stratum_header]):
        tag = cell.strip()
        if tag in _STRATUM_LIST or tag == "DEFAULT-ROW":
            column_for[tag] = pos
    gathered = {}
    for line in live_grid[stratum_header + 1:]:
        if not line:
            continue
        label = line[0].strip()
        if label in _PARAM_ROWS:
            for stratum, pos in column_for.items():
                if pos < len(line) and line[pos].strip():
                    gathered.setdefault(stratum, {})[label] = line[pos].strip()
    calibration = {}
    for stratum, values in gathered.items():
        if all(key in values for key in _PARAM_ROWS):
            calibration[stratum] = {
                "a": dec(values["a_s"]), "b": dec(values["b_s"]),
                "tau": dec(values["tau_s"]), "recovery": dec(values["recovery_s"]),
            }

    # --- S8: review cost, F-beta and z come only from the policy PDF -------------
    policy_text = " ".join(extract_pdf_lines(root / _FILE_POLICY))
    review_cost = int(_re.search(r"unit cost is (\d+) credits", policy_text).group(1))
    beta = dec(_re.search(r"beta = (\d+\.\d+)", policy_text).group(1))
    z_value = dec(_re.search(r"z = (\d+\.\d+)", policy_text).group(1))

    # --- S9: smurf levy and settlement floor come only from the DOCX addendum ----
    addendum_text = " ".join(extract_docx_paragraphs(root / _FILE_ADDENDUM))
    levy_bps = int(_re.search(r"smurf levy of (\d+) basis points", addendum_text).group(1))
    floor_credits = int(_re.search(r"floored at (\d+) credits", addendum_text).group(1))

    return {
        "matches": raw_matches, "revisions": revisions, "frame": draw_frame,
        "drift": drift_rows, "accounts": account_rows, "profile": profile,
        "calibration": calibration, "ore_gain": ore_gain, "review_cost": review_cost,
        "beta": beta, "z": z_value, "levy_bps": levy_bps, "floor": floor_credits,
    }


def settle(data_dir):
    src = gather(data_dir)
    frame_lookup = {row["match_key"]: row for row in src["frame"]}
    calibration = src["calibration"]

    revisions_by_key = {}
    for row in src["revisions"]:
        revisions_by_key.setdefault(row["match_key"], []).append(row)

    drift_by_family = {}
    for row in src["drift"]:
        drift_by_family.setdefault(row["unit_family"], []).append((row["ref_date"], dec(row["drift_mult"])))
    for family in drift_by_family:
        drift_by_family[family].sort()

    # === S1: canonical row per economic match key; drop never-sealed keys ========
    grouped = {}
    for attempt in src["matches"]:
        key = "|".join((attempt["account_id"], attempt["hero_handle"],
                        attempt["seed_hash"], attempt["ladder_split"]))
        grouped.setdefault(key, []).append(attempt)

    population = []
    for key, attempts in grouped.items():
        sealed = [a for a in attempts if a["seal_status"] == "SEALED"]
        if not sealed:
            continue
        canonical = max(sealed, key=lambda a: int(a["checkpoint_no"]))
        first_attempt = min(attempts, key=lambda a: int(a["checkpoint_no"]))
        record = frame_lookup.get(key)
        population.append({
            "match_key": key,
            "account_id": key.split("|")[0],
            "stratum": record["stratum_frozen"] if record else None,
            "drawn": record["drawn"] if record else "0",
            "raw_loot": canonical["raw_loot"],
            "loot_currency": canonical["loot_currency"],
            "anchor_date": first_attempt["match_epoch"],
            "p_raw": canonical["p_raw"],
        })
    population.sort(key=lambda r: r["match_key"])

    # === S2: verdict within window by review_seq; amended_at is ignored ==========
    def label_of(key, anchor_iso):
        pool = revisions_by_key.get(key, [])
        anchor = _date.fromisoformat(anchor_iso)
        in_window = [r for r in pool
                     if 0 <= (_date.fromisoformat(r["effective_at"]) - anchor).days <= _LADDER_WINDOW]
        if not in_window:
            return None
        final = max(in_window, key=lambda r: int(r["review_seq"]))
        verdict = final["verdict"]
        if verdict == "LADDER_CLEAR":
            return 1
        if verdict == "VOID_SMURF":
            return 0
        return None

    for row in population:
        row["y"] = label_of(row["match_key"], row["anchor_date"])

    resolved = [r for r in population if r["y"] is not None and r["stratum"] is not None]

    # === S3: running ladder baseline folded in ascending match_key order =========
    seed_p = dec(src["profile"]["base_p"])
    carry = {stratum: seed_p for stratum in _STRATUM_LIST}
    for row in sorted(resolved, key=lambda r: (r["stratum"], r["match_key"])):
        previous = carry[row["stratum"]]
        base_prob = pin_prob(dec(row["p_raw"]))
        effective = pin_prob(dec("0.85") * base_prob + dec("0.15") * previous)
        row["p_eff"] = effective
        carry[row["stratum"]] = effective

    # === S4: ledger units via scale exponent + xlsx ore gain + drift/backfill ====
    def drift_factor(family, anchor_iso):
        entries = drift_by_family.get(family, [])
        anchor = _date.fromisoformat(anchor_iso)
        pick = None
        for iso, mult in entries:
            when = _date.fromisoformat(iso)
            if when <= anchor:
                if pick is None or when > pick[0]:
                    pick = (when, mult)
        return pick[1] if pick else None

    for row in resolved:
        currency = row["loot_currency"]
        amount = dec(row["raw_loot"])
        if currency == "ORE":
            converted = amount * src["ore_gain"]
        else:
            converted = amount * (dec(10) ** _SCALE_EXP[currency])
        factor = drift_factor(currency, row["anchor_date"])
        row["units"] = None if factor is None else whole(converted * factor)

    # === S5: two-level rarity weight, inflate then mass-preserving trim ==========
    pop_count = {}
    sampled_count = {}
    sampled_by_server = {}
    resolved_by_server = {}
    for row in population:
        if row["stratum"]:
            pop_count[row["stratum"]] = pop_count.get(row["stratum"], 0) + 1
            if row["drawn"] == "1":
                sampled_count[row["stratum"]] = sampled_count.get(row["stratum"], 0) + 1
                server = row["stratum"].split("-")[1]
                sampled_by_server[server] = sampled_by_server.get(server, 0) + 1
    for row in resolved:
        if row["drawn"] == "1":
            server = row["stratum"].split("-")[1]
            resolved_by_server[server] = resolved_by_server.get(server, 0) + 1

    weighted = [r for r in resolved if r["drawn"] == "1"]
    for row in weighted:
        stratum = row["stratum"]
        server = stratum.split("-")[1]
        base_rate = dec(pop_count[stratum]) / dec(sampled_count[stratum])
        nonresponse = dec(sampled_by_server[server]) / dec(resolved_by_server[server])
        row["w_pre"] = base_rate * nonresponse

    bucket = {}
    for row in weighted:
        bucket.setdefault(row["stratum"], []).append(row)
    for stratum, members in bucket.items():
        subtotal = sum((r["w_pre"] for r in members), _Dec(0))
        rounded_sum = sum((round6(r["w_pre"]) for r in members), _Dec(0))
        leftover = round6(subtotal) - rounded_sum
        for r in members:
            r["w"] = round6(r["w_pre"])
        if leftover != 0 and members:
            top = sorted(members, key=lambda r: (-r["w"], r["match_key"]))[0]
            top["w"] = round6(top["w"] + leftover)

    # === S6: log-odds calibration with LIVE parameters; inclusive threshold ======
    for row in weighted:
        params = calibration[row["stratum"]]
        combined = params["a"] + params["b"] * to_logit(row["p_eff"])
        calibrated = from_logodds(combined)
        row["p_cal"] = calibrated
        row["yhat"] = 1 if calibrated >= params["tau"] else 0

    # === S7: weighted precision / recall / F-beta ================================
    beta_squared = src["beta"] * src["beta"]

    def score_block(members):
        tp = sum((r["w"] for r in members if r["y"] == 1 and r["yhat"] == 1), _Dec(0))
        fp = sum((r["w"] for r in members if r["y"] == 0 and r["yhat"] == 1), _Dec(0))
        fn = sum((r["w"] for r in members if r["y"] == 1 and r["yhat"] == 0), _Dec(0))
        precision = tp / (tp + fp) if (tp + fp) > 0 else _Dec(0)
        recall = tp / (tp + fn) if (tp + fn) > 0 else _Dec(0)
        denom = beta_squared * precision + recall
        fbeta = ((_Dec(1) + beta_squared) * precision * recall / denom) if denom > 0 else _Dec(0)
        return {"tp": tp, "fp": fp, "fn": fn,
                "precision": precision, "recall": recall, "fbeta": fbeta}

    per_stratum_members = {s: [r for r in weighted if r["stratum"] == s] for s in _STRATUM_LIST}
    per_stratum_score = {s: score_block(per_stratum_members[s]) for s in _STRATUM_LIST}
    aggregate = score_block(weighted)
    total_weight = sum((r["w"] for r in weighted), _Dec(0))
    share = {s: sum((r["w"] for r in per_stratum_members[s]), _Dec(0)) for s in _STRATUM_LIST}
    if total_weight > 0:
        macro_precision = sum((per_stratum_score[s]["precision"] * share[s] for s in _STRATUM_LIST), _Dec(0)) / total_weight
        macro_recall = sum((per_stratum_score[s]["recall"] * share[s] for s in _STRATUM_LIST), _Dec(0)) / total_weight
    else:
        macro_precision = macro_recall = _Dec(0)

    # === S8: Wilson intervals on Kish effective N; z from the PDF ================
    def kish_n(members):
        w_sum = sum((r["w"] for r in members), _Dec(0))
        w_sq = sum((r["w"] * r["w"] for r in members), _Dec(0))
        return (w_sum * w_sum / w_sq) if w_sq > 0 else _Dec(0)

    def wilson_bounds(point, n_eff, z):
        if n_eff <= 0:
            return (_Dec(0), _Dec(0))
        z_sq = z * z
        divisor = _Dec(1) + z_sq / n_eff
        centre = (point + z_sq / (_Dec(2) * n_eff)) / divisor
        half = (z * ((point * (_Dec(1) - point) / n_eff + z_sq / (_Dec(4) * n_eff * n_eff)).sqrt())) / divisor
        return (centre - half, centre + half)

    interval_rows = []
    for stratum in _STRATUM_LIST:
        members = per_stratum_members[stratum]
        positives = [r for r in members if r["y"] == 1]
        predicted = [r for r in members if r["yhat"] == 1]
        n_recall = kish_n(positives)
        n_precision = kish_n(predicted)
        recall_lo, recall_hi = wilson_bounds(per_stratum_score[stratum]["recall"], n_recall, src["z"])
        prec_lo, prec_hi = wilson_bounds(per_stratum_score[stratum]["precision"], n_precision, src["z"])
        interval_rows.append({
            "stratum": stratum, "recall_lo": round6(recall_lo), "recall_hi": round6(recall_hi),
            "prec_lo": round6(prec_lo), "prec_hi": round6(prec_hi),
            "n_eff_recall": round6(n_recall), "n_eff_precision": round6(n_precision),
        })

    # === S8/S9: rewarded, review, levy, floor; forfeit share by largest remainder
    levy_bps = dec(src["levy_bps"])
    floor_credits = src["floor"]
    money = []
    forfeit_by_stratum = {}
    forfeit_total = _Dec(0)
    for stratum in _STRATUM_LIST:
        payable = [r for r in per_stratum_members[stratum] if r["units"] is not None]
        rewarded = _Dec(0)
        forfeited = _Dec(0)
        review = _Dec(0)
        recovery = calibration[stratum]["recovery"] if stratum in calibration else dec("0.8")
        for r in payable:
            weighted_units = dec(r["units"]) * r["w"]
            if r["y"] == 1 and r["yhat"] == 1:
                rewarded += whole(weighted_units * recovery)
            if r["y"] == 1 and r["yhat"] == 0:
                forfeited += whole(weighted_units)
            if r["yhat"] == 1:
                review += whole(dec(src["review_cost"]) * r["w"])
        rewarded_i = whole(rewarded)
        forfeited_i = whole(forfeited)
        review_i = whole(review)
        levy_i = whole(dec(rewarded_i) * levy_bps / dec(10000))
        pre_floor = rewarded_i - review_i - levy_i
        net = max(floor_credits, pre_floor)
        money.append({"stratum": stratum, "rewarded_credits": rewarded_i,
                      "forfeited_credits": forfeited_i, "review_credits": review_i,
                      "levy_credits": levy_i, "net_credits": net})
        forfeit_by_stratum[stratum] = forfeited_i
        forfeit_total += forfeited_i

    if forfeit_total > 0:
        exact = {s: (dec(forfeit_by_stratum[s]) * dec(10000) / dec(forfeit_total)) for s in _STRATUM_LIST}
        share_bps = {s: int(exact[s]) for s in _STRATUM_LIST}
        remaining = 10000 - sum(share_bps.values())
        ranking = sorted(_STRATUM_LIST, key=lambda s: (-(exact[s] - int(exact[s])), s))
        for pos in range(remaining):
            share_bps[ranking[pos]] += 1
    else:
        share_bps = {s: 0 for s in _STRATUM_LIST}

    return build_outputs(src, population, resolved, weighted, per_stratum_members,
                         per_stratum_score, aggregate, macro_precision, macro_recall,
                         interval_rows, money, forfeit_by_stratum, share_bps,
                         pop_count, sampled_count)


def build_outputs(src, population, resolved, weighted, per_stratum_members,
                  per_stratum_score, aggregate, macro_precision, macro_recall,
                  interval_rows, money, forfeit_by_stratum, share_bps,
                  pop_count, sampled_count):
    payload = {}

    def as_table(header, records, sep=","):
        sink = _io.StringIO()
        writer = _csv.writer(sink, delimiter=sep, lineterminator="\n")
        writer.writerow(header)
        for record in records:
            writer.writerow(record)
        return sink.getvalue().encode("utf-8")

    def as_json(obj):
        return (_json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")

    ordered_pop = sorted(population, key=lambda r: r["match_key"])
    payload["population.csv"] = as_table(
        ["match_key", "account_id", "stratum", "drawn", "loot_currency", "anchor_date"],
        [[r["match_key"], r["account_id"], r["stratum"] or "", r["drawn"],
          r["loot_currency"], r["anchor_date"]] for r in ordered_pop])

    ordered_weighted = sorted(weighted, key=lambda r: r["match_key"])
    payload["weights.csv"] = as_table(
        ["match_key", "stratum", "y", "yhat", "loot_currency", "ledger_units", "p_eff", "p_cal", "weight"],
        [[r["match_key"], r["stratum"], r["y"], r["yhat"], r["loot_currency"],
          "" if r["units"] is None else str(r["units"]),
          f'{round8(r["p_eff"]):.8f}', f'{round8(r["p_cal"]):.8f}', f'{r["w"]:.6f}']
         for r in ordered_weighted])

    metrics_doc = {
        "overall": {
            "precision": f'{round6(aggregate["precision"]):.6f}',
            "recall": f'{round6(aggregate["recall"]):.6f}',
            "fbeta": f'{round6(aggregate["fbeta"]):.6f}',
            "macro_precision": f'{round6(macro_precision):.6f}',
            "macro_recall": f'{round6(macro_recall):.6f}',
        },
        "strata": {s: {
            "precision": f'{round6(per_stratum_score[s]["precision"]):.6f}',
            "recall": f'{round6(per_stratum_score[s]["recall"]):.6f}',
            "fbeta": f'{round6(per_stratum_score[s]["fbeta"]):.6f}',
        } for s in _STRATUM_LIST},
    }
    payload["metrics.json"] = as_json(metrics_doc)

    for stratum in _STRATUM_LIST:
        payload[f"metrics_{_SLUG_OF[stratum]}.json"] = as_json({
            "stratum": stratum,
            "precision": f'{round6(per_stratum_score[stratum]["precision"]):.6f}',
            "recall": f'{round6(per_stratum_score[stratum]["recall"]):.6f}',
            "fbeta": f'{round6(per_stratum_score[stratum]["fbeta"]):.6f}',
            "tp": f'{round6(per_stratum_score[stratum]["tp"]):.6f}',
            "fp": f'{round6(per_stratum_score[stratum]["fp"]):.6f}',
            "fn": f'{round6(per_stratum_score[stratum]["fn"]):.6f}',
        })

    sum_rewarded = sum(m["rewarded_credits"] for m in money)
    sum_forfeited = sum(m["forfeited_credits"] for m in money)
    sum_review = sum(m["review_credits"] for m in money)
    sum_levy = sum(m["levy_credits"] for m in money)
    sum_net = sum(m["net_credits"] for m in money)
    payload["payout.csv"] = as_table(
        ["stratum", "rewarded_credits", "forfeited_credits", "review_credits", "levy_credits", "net_credits"],
        [[m["stratum"], m["rewarded_credits"], m["forfeited_credits"], m["review_credits"],
          m["levy_credits"], m["net_credits"]] for m in money]
        + [["TOTAL", sum_rewarded, sum_forfeited, sum_review, sum_levy, sum_net]])

    payload["payout_breakdown.tsv"] = as_table(
        ["stratum", "rewarded_credits", "forfeited_credits"],
        [[m["stratum"], m["rewarded_credits"], m["forfeited_credits"]] for m in money], sep="\t")

    payload["payout_ledger.psv"] = as_table(
        ["stratum", "review_credits", "levy_credits", "net_credits"],
        [[m["stratum"], m["review_credits"], m["levy_credits"], m["net_credits"]] for m in money], sep="|")

    payload["forfeited_shares.csv"] = as_table(
        ["stratum", "forfeited_credits", "share_bps"],
        [[s, forfeit_by_stratum[s], share_bps[s]] for s in _STRATUM_LIST])

    payload["confidence_intervals.csv"] = as_table(
        ["stratum", "recall_lo", "recall_hi", "prec_lo", "prec_hi", "n_eff_recall", "n_eff_precision"],
        [[c["stratum"], f'{c["recall_lo"]:.6f}', f'{c["recall_hi"]:.6f}',
          f'{c["prec_lo"]:.6f}', f'{c["prec_hi"]:.6f}',
          f'{c["n_eff_recall"]:.6f}', f'{c["n_eff_precision"]:.6f}'] for c in interval_rows])

    stream_lines = []
    for stratum in _STRATUM_LIST:
        stream_lines.append(_json.dumps({
            "stratum": stratum,
            "precision": f'{round6(per_stratum_score[stratum]["precision"]):.6f}',
            "recall": f'{round6(per_stratum_score[stratum]["recall"]):.6f}',
            "fbeta": f'{round6(per_stratum_score[stratum]["fbeta"]):.6f}',
        }, sort_keys=True))
    payload["stratum_metrics_stream.jsonl"] = ("\n".join(stream_lines) + "\n").encode("utf-8")

    payload["label_distribution.json"] = as_json({
        "positive": sum(1 for r in resolved if r["y"] == 1),
        "negative": sum(1 for r in resolved if r["y"] == 0),
        "resolved_total": len(resolved),
        "population_total": len(population)})
    flagged = sum(1 for r in weighted if r["yhat"] == 1)
    payload["decision_distribution.json"] = as_json({
        "flagged": flagged,
        "cleared": sum(1 for r in weighted if r["yhat"] == 0),
        "weighted_total": len(weighted)})

    payload["frame_counts.json"] = as_json({
        "population_by_stratum": {s: pop_count.get(s, 0) for s in _STRATUM_LIST},
        "sampled_by_stratum": {s: sampled_count.get(s, 0) for s in _STRATUM_LIST},
        "resolved_weighted": {s: len(per_stratum_members[s]) for s in _STRATUM_LIST}})

    payload["weight_diagnostics.json"] = as_json({
        "weight_sum_by_stratum": {s: f'{sum((r["w"] for r in per_stratum_members[s]), _Dec(0)):.6f}' for s in _STRATUM_LIST},
        "cap": _CAP_TEXT,
        "max_weight": f'{max((r["w"] for r in weighted), default=_Dec(0)):.6f}'})

    payload["net_payout_summary.json"] = as_json({
        "total_rewarded_credits": sum_rewarded,
        "total_forfeited_credits": sum_forfeited,
        "total_review_credits": sum_review,
        "total_levy_credits": sum_levy,
        "total_net_credits": sum_net,
        "by_stratum": {m["stratum"]: m["net_credits"] for m in money}})

    payload["levy_summary.json"] = as_json({
        "levy_bps": src["levy_bps"],
        "settlement_floor": src["floor"],
        "total_levy_credits": sum_levy,
        "levy_by_stratum": {m["stratum"]: m["levy_credits"] for m in money},
        "floored_strata": sorted(m["stratum"] for m in money
                                 if (m["rewarded_credits"] - m["review_credits"] - m["levy_credits"]) < src["floor"])})

    payload["audit_summary.json"] = as_json({
        "population": len(population),
        "resolved": len(resolved),
        "weighted": len(weighted),
        "flagged": flagged,
        "overall_fbeta": f'{round6(aggregate["fbeta"]):.6f}',
        "calibration_version": src["profile"]["calibration_version"]})

    overall_md = _io.StringIO()
    overall_md.write("# Overall Settled Metrics\n\n")
    overall_md.write(f'- precision: {round6(aggregate["precision"]):.6f}\n')
    overall_md.write(f'- recall: {round6(aggregate["recall"]):.6f}\n')
    overall_md.write(f'- fbeta: {round6(aggregate["fbeta"]):.6f}\n')
    overall_md.write(f'- macro_precision: {round6(macro_precision):.6f}\n')
    overall_md.write(f'- macro_recall: {round6(macro_recall):.6f}\n')
    payload["overall_metrics.md"] = overall_md.getvalue().encode("utf-8")

    report_md = _io.StringIO()
    report_md.write("# Settlement Reconciliation Report\n\n")
    report_md.write(f"- population: {len(population)}\n")
    report_md.write(f"- resolved: {len(resolved)}\n")
    report_md.write(f"- weighted: {len(weighted)}\n")
    report_md.write(f"- total_net_credits: {sum_net}\n")
    report_md.write(f'- calibration_version: {src["profile"]["calibration_version"]}\n')
    payload["reconciliation_report.md"] = report_md.getvalue().encode("utf-8")

    rollup = _io.StringIO()
    rollup.write('<?xml version="1.0" encoding="UTF-8"?>\n<rollup>\n')
    for stratum in _STRATUM_LIST:
        rollup.write(f'  <stratum id="{stratum}">'
                     f'<precision>{round6(per_stratum_score[stratum]["precision"]):.6f}</precision>'
                     f'<recall>{round6(per_stratum_score[stratum]["recall"]):.6f}</recall>'
                     f'<fbeta>{round6(per_stratum_score[stratum]["fbeta"]):.6f}</fbeta>'
                     f'</stratum>\n')
    rollup.write("</rollup>\n")
    payload["rollup.xml"] = rollup.getvalue().encode("utf-8")

    digest = _hashlib.sha256()
    for name in _CORE:
        digest.update(payload[name])
    payload["manifest.json"] = as_json({"core_order": list(_CORE), "digest_sha256": digest.hexdigest()})

    return payload


def emit(data_dir, out_dir):
    destination = _Path(out_dir)
    destination.mkdir(parents=True, exist_ok=True)
    for name, blob in settle(data_dir).items():
        (destination / name).write_bytes(blob)


def main(argv):
    data_dir = argv[1] if len(argv) > 1 else "/app/data"
    out_dir = argv[2] if len(argv) > 2 else "/app/out"
    emit(data_dir, out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(_sys.argv))
