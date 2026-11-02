#!/usr/bin/env python3
"""Detector-array flux reconciliation.

Reads a reconciliation extract from DATA_DIR and writes the full corrected
report set into OUT_DIR, recomputing every figure from the reference tables
named authoritative by the extract's file role index.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import csv
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from fractions import Fraction

REPORT_ID = "detector-flux-reconciliation"
PHOTOMETRIC_BANDS = ["u", "g", "r", "i", "z"]
DIGEST_MODULUS = 1000003
MAD_MULTIPLIER = 6
ANOMALY_MULTIPLIER = 3
NEAR_SATURATION_PERCENT = 98


# --------------------------------------------------------------------------
# numeric helpers
# --------------------------------------------------------------------------

def round_half_even(value):
    """Banker's rounding of an exact Fraction/int to an int."""
    fr = Fraction(value)
    q, rem = divmod(fr.numerator, fr.denominator)
    twice = 2 * rem
    if twice > fr.denominator:
        return q + 1
    if twice < fr.denominator:
        return q
    return q if q % 2 == 0 else q + 1


def floor_div(numerator, denominator):
    """Floor division toward negative infinity."""
    return numerator // denominator


# --------------------------------------------------------------------------
# minimal readers for the extract's file formats
# --------------------------------------------------------------------------

def read_delimited(path, delimiter):
    with open(path, newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter=delimiter)]


def authoritative_rows(rows):
    """Keep only `authoritative` rows when the table publishes a row_kind."""
    if rows and "row_kind" in rows[0]:
        kept = [r for r in rows if r.get("row_kind") == "authoritative"]
        if kept:
            return kept
    return rows


def _yaml_scalar(text):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def parse_yaml(text):
    """Parse the indentation-based YAML subset used by this extract."""
    lines = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append((len(raw) - len(raw.lstrip(" ")), stripped))
    cursor = [0]

    def is_item(content):
        return content == "-" or content.startswith("- ")

    def parse_block(indent):
        if is_item(lines[cursor[0]][1]):
            out = []
            while cursor[0] < len(lines):
                ind, content = lines[cursor[0]]
                if ind != indent or not is_item(content):
                    break
                cursor[0] += 1
                rest = content[1:].strip()
                if not rest:
                    if cursor[0] < len(lines) and lines[cursor[0]][0] > indent:
                        out.append(parse_block(lines[cursor[0]][0]))
                    else:
                        out.append(None)
                elif ":" in rest:
                    item = {}
                    key, _, value = rest.partition(":")
                    item[key.strip()] = _yaml_scalar(value)
                    while cursor[0] < len(lines) and lines[cursor[0]][0] > indent:
                        _, inner = lines[cursor[0]]
                        cursor[0] += 1
                        key, _, value = inner.partition(":")
                        item[key.strip()] = _yaml_scalar(value)
                    out.append(item)
                else:
                    out.append(_yaml_scalar(rest))
            return out
        out = {}
        while cursor[0] < len(lines):
            ind, content = lines[cursor[0]]
            if ind != indent or is_item(content):
                break
            cursor[0] += 1
            key, _, value = content.partition(":")
            key = key.strip()
            if value.strip():
                out[key] = _yaml_scalar(value)
            elif cursor[0] < len(lines) and (
                lines[cursor[0]][0] > indent
                or (lines[cursor[0]][0] == indent and is_item(lines[cursor[0]][1]))
            ):
                out[key] = parse_block(lines[cursor[0]][0])
            else:
                out[key] = None
        return out

    if not lines:
        return {}
    return parse_block(lines[0][0])


def read_yaml(path):
    with open(path, encoding="utf-8") as handle:
        return parse_yaml(handle.read())


def read_xlsx(path):
    """Return `[(sheet_name, rows)]` of a workbook, rows keyed by header row."""
    ns_main = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    ns_rel = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    sheets = []
    with zipfile.ZipFile(path) as archive:
        book = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target_by_rid = {node.get("Id"): node.get("Target") for node in rels}

        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            sst = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in sst.iter(ns_main + "si"):
                shared.append("".join(t.text or "" for t in item.iter(ns_main + "t")))

        for node in book.iter(ns_main + "sheet"):
            target = target_by_rid[node.get(ns_rel + "id")]
            if not target.startswith("xl/"):
                target = "xl/" + target.lstrip("/")
            sheet = ET.fromstring(archive.read(target))
            table = []
            for row in sheet.iter(ns_main + "row"):
                values = []
                for cell in row.iter(ns_main + "c"):
                    kind = cell.get("t")
                    if kind == "inlineStr":
                        text = "".join(t.text or "" for t in cell.iter(ns_main + "t"))
                    elif kind == "s":
                        value = cell.find(ns_main + "v")
                        text = shared[int(value.text)] if value is not None else ""
                    else:
                        value = cell.find(ns_main + "v")
                        text = value.text if value is not None and value.text else ""
                    values.append(text)
                table.append(values)
            rows = []
            if table:
                header = table[0]
                rows = [
                    {header[i]: row[i] for i in range(min(len(header), len(row)))}
                    for row in table[1:]
                ]
            sheets.append((node.get("name"), rows))
    return sheets


def pdf_text_lines(path):
    """Extract the parenthesised text-show operands of an uncompressed PDF."""
    with open(path, "rb") as handle:
        blob = handle.read().decode("latin-1")
    lines = []
    for match in re.finditer(r"\((?:\\.|[^()\\])*\)\s*Tj", blob):
        body = match.group(0)
        body = body[1:body.rindex(")")]
        body = body.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
        lines.append(body)
    return lines


# --------------------------------------------------------------------------
# extract loading
# --------------------------------------------------------------------------

class Extract(object):
    """The authoritative reference tables of one reconciliation extract."""

    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.observations = self._load_observations()
        self.full_well = self._load_full_well()
        self.exposure_weight = self._load_exposure_weight()
        self.dark_current = self._load_dark_current()
        self.coefficients = self._load_coefficients()
        self.gain_micro = self._load_gain()
        self.fold = self._load_fold()
        self.scale_micro = self._load_scale()
        self.drift_ppm = self._load_drift()
        self.epoch_windows = self._load_epoch_windows()
        self.disputed = self._load_disputed()
        self.masked, self.relay_targets = self._load_relay()
        self.exposure = self._load_exposure_ledger()
        self.bands = self._load_bands()
        self.instruments = sorted(self.exposure_weight)
        self.epochs = sorted(self.epoch_windows)
        self.input_file_count = sum(
            1 for name in os.listdir(data_dir)
            if os.path.isfile(os.path.join(data_dir, name))
        )

    def path(self, name):
        return os.path.join(self.data_dir, name)

    def _load_observations(self):
        rows = read_delimited(self.path("obs_capture_index.csv"), ",")
        out = []
        for row in rows:
            out.append({
                "obs_id": row["obs_id"],
                "instrument": row.get("instrument") or row.get("instr"),
                "band": row["band"],
                "mjd": int(row["mjd"]),
                "gain_label": row.get("gain_label") or row.get("written_label"),
                "raw_counts": int(row.get("raw_counts") or row.get("adu")),
                "pixel": row["pixel"],
                "quality_flag": row.get("quality_flag") or row.get("csv_quality"),
            })
        out.sort(key=lambda o: o["obs_id"])
        return out

    def _load_full_well(self):
        rows = authoritative_rows(read_delimited(self.path("full_well_capacity.tsv"), "\t"))
        return {r["instrument"]: int(r["full_well_counts"]) for r in rows}

    def _load_exposure_weight(self):
        rows = authoritative_rows(read_delimited(self.path("exposure_weight_micro.tsv"), "\t"))
        return {r["instrument"]: int(r["weight_micro"]) for r in rows}

    def _load_dark_current(self):
        table = {}
        backup = self.path("baseline_pedestal_grid.tsv")
        if os.path.isfile(backup):
            for r in authoritative_rows(read_delimited(backup, "\t")):
                table[(r["instrument"], r["band"], r["epoch"])] = int(
                    r["dark_current_counts"]
                )
        rows = authoritative_rows(read_delimited(self.path("pedestal_authoritative.csv"), ","))
        for r in rows:
            table[(r["instrument"], r["band"], r["epoch"])] = int(r["dark_current_counts"])
        return table

    def _load_coefficients(self):
        table = {}
        backup = self.path("instrument_capability_matrix.xml")
        if os.path.isfile(backup):
            root = ET.parse(backup).getroot()
            for node in root.iter("instrument"):
                degrees = sorted(
                    (
                        (int(k[len("nonlin_a"):]), int(v))
                        for k, v in node.attrib.items() if k.startswith("nonlin_a")
                    ),
                    reverse=True,
                )
                if degrees:
                    table[node.get("instrument")] = [c for _, c in degrees]
        doc = read_yaml(self.path("response_curve_horner.yaml"))
        for instrument, coeffs in doc["coefficients"].items():
            table[instrument] = [int(c) for c in coeffs]
        return table

    def _load_gain(self):
        table = {}
        backup = self.path("yield_channel_values.psv")
        if os.path.isfile(backup):
            for r in read_delimited(backup, "|"):
                table[r["channel"]] = int(r["micro_e_per_count"])
        with open(self.path("quantum_yield_micro.json"), encoding="utf-8") as handle:
            doc = json.load(handle)
        for channel, value in doc["channels"].items():
            table[channel] = int(value)
        return table

    def _load_fold(self):
        rows = read_delimited(self.path("channel_lineage_fold.psv"), "|")
        by_label_mjd = {}
        by_label_epoch = {}
        for row in rows:
            label = row["written_label"]
            resolved = row["resolved_channel"]
            by_label_mjd[(label, int(row["mjd"]))] = resolved
            by_label_epoch[(label, row["epoch"])] = resolved
        return by_label_mjd, by_label_epoch

    def _load_scale(self):
        sheets = read_xlsx(self.path("gain_scale_workbook.xlsx"))
        candidates = [
            (name, rows) for name, rows in sheets
            if rows and "instrument" in rows[0] and "factor_micro" in rows[0]
        ]
        chosen = None
        for name, rows in candidates:
            if "authoritative" in name:
                chosen = rows
                break
        if chosen is None and candidates:
            chosen = candidates[0][1]
        chosen = authoritative_rows(chosen or [])
        return {
            r["instrument"]: int(r["factor_micro"])
            for r in chosen if r.get("instrument")
        }

    def _load_drift(self):
        table = {}
        backup = self.path("drift_ppm_matrix.tsv")
        if os.path.isfile(backup):
            for r in authoritative_rows(read_delimited(backup, "\t")):
                table[(r["instrument"], r["epoch"])] = int(r["drift_ppm"])
        doc = read_yaml(self.path("thermal_drift_ppm.yml"))
        for entry in doc["table"]:
            table[(entry["instrument"], entry["epoch"])] = int(entry["drift_ppm"])
        return table

    def _load_epoch_windows(self):
        with open(self.path("epoch_window_bounds.json"), encoding="utf-8") as handle:
            doc = json.load(handle)
        return {
            epoch: (int(win["mjd_start"]), int(win["mjd_end"]))
            for epoch, win in doc["epochs"].items()
        }

    def _load_disputed(self):
        lines = pdf_text_lines(self.path("adjudication_dossier.pdf"))
        header = None
        disputed = set()
        for line in lines:
            if "|" not in line:
                continue
            fields = [f.strip() for f in line.split("|")]
            if "obs_id" in fields:
                header = fields
                continue
            if header is None or len(fields) < 2:
                continue
            record = dict(zip(header, fields))
            obs_id = record.get("obs_id")
            if obs_id and any(v == "disputed" for v in record.values()):
                disputed.add(obs_id)
        return disputed

    def _load_relay(self):
        targets = {}
        root = ET.parse(self.path("occlusion_relay_graph.xml")).getroot()
        for node in root.iter("node"):
            raw = (node.get("targets") or "").strip()
            if not raw:
                continue
            pixel = node.get("pixel")
            targets[pixel] = [t for t in re.split(r"[;,]", raw) if t]
        edge_path = self.path("relay_edges.jsonl")
        if os.path.isfile(edge_path):
            with open(edge_path, encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    if record.get("targets"):
                        targets.setdefault(record["pixel"], list(record["targets"]))
        return sorted(targets), targets

    def _load_exposure_ledger(self):
        rows = read_delimited(self.path("exposure_ledger.csv"), ",")
        return {
            r["obs_id"]: (int(r["exposure_ms"]), r["shutter_state"])
            for r in rows
        }

    def _load_bands(self):
        path = self.path("band_index_map.xml")
        if os.path.isfile(path):
            root = ET.parse(path).getroot()
            entries = [
                (int(node.get("index")), node.get("band"))
                for node in root.iter("band")
            ]
            if entries:
                return [band for _, band in sorted(entries)]
        return list(PHOTOMETRIC_BANDS)

    # resolution helpers -----------------------------------------------

    def epoch_of(self, mjd):
        for epoch in sorted(self.epoch_windows):
            start, end = self.epoch_windows[epoch]
            if start <= mjd < end:
                return epoch
        return None

    def resolve_channel(self, label, mjd, epoch):
        by_label_mjd, by_label_epoch = self.fold
        if (label, mjd) in by_label_mjd:
            return by_label_mjd[(label, mjd)]
        if (label, epoch) in by_label_epoch:
            return by_label_epoch[(label, epoch)]
        return label


# --------------------------------------------------------------------------
# reconciliation pipeline
# --------------------------------------------------------------------------

def horner(coeffs, net):
    """Evaluate the micro-scaled polynomial, highest degree first."""
    acc = 0
    for coeff in coeffs:
        acc = acc * net + coeff
    return acc


def reconcile(extract):
    """Run the seven correction stages over every observation."""
    records = []
    for obs in extract.observations:
        instrument = obs["instrument"]
        epoch = extract.epoch_of(obs["mjd"])
        full_well = extract.full_well[instrument]
        raw = obs["raw_counts"]
        saturated = raw > full_well
        effective = full_well if saturated else raw
        dark = extract.dark_current[(instrument, obs["band"], epoch)]
        net = effective - dark
        linearized = round_half_even(
            Fraction(horner(extract.coefficients[instrument], net), 1000000)
        )
        channel = extract.resolve_channel(obs["gain_label"], obs["mjd"], epoch)
        gained = Fraction(linearized * extract.gain_micro[channel], 1000000)
        scaled = gained * Fraction(extract.scale_micro[instrument], 1000000)
        drift_ppm = extract.drift_ppm[(instrument, epoch)]
        drift_correction = round_half_even(scaled * Fraction(drift_ppm, 1000000))
        flux = round_half_even(scaled - drift_correction)
        records.append({
            "obs_id": obs["obs_id"],
            "instrument": instrument,
            "band": obs["band"],
            "epoch": epoch,
            "resolved_channel": channel,
            "effective_counts": effective,
            "saturated": saturated,
            "net_counts": net,
            "linearized": linearized,
            "drift_ppm": drift_ppm,
            "drift_correction": drift_correction,
            "calibrated_flux_ujy": flux,
            "raw_counts": raw,
            "full_well_counts": full_well,
            "pixel": obs["pixel"],
            "quality_flag": obs["quality_flag"],
        })
    records.sort(key=lambda r: r["obs_id"])
    return records


def band_median(values):
    """Median of the eligible band sample, banker's-rounded to an integer."""
    sample = sorted(values)
    size = len(sample)
    if size == 0:
        return None
    if size % 2:
        return sample[size // 2]
    return round_half_even(Fraction(sample[size // 2 - 1] + sample[size // 2], 2))


def lower_median(values):
    """Settlement-layer median: even samples take the lower middle value."""
    sample = sorted(values)
    size = len(sample)
    if size == 0:
        return None
    if size % 2:
        return sample[size // 2]
    return sample[size // 2 - 1]


def largest_remainder(pool, weights):
    """Apportion `pool` across `weights` so the integer parts sum exactly."""
    total_weight = sum(weights.values())
    keys = sorted(weights)
    exact = {k: Fraction(pool * weights[k], total_weight) for k in keys}
    base = {}
    for key in keys:
        value = exact[key]
        base[key] = value.numerator // value.denominator
    leftover = pool - sum(base.values())
    order = sorted(keys, key=lambda k: (-(exact[k] - base[k]), k))
    recipients = order[:leftover] if leftover > 0 else []
    attributed = dict(base)
    for key in recipients:
        attributed[key] += 1
    return attributed, sorted(recipients)


def close_deadpixels(extract, live_records):
    """Least-fixed-point redistribution of masked-pixel flux, with audit."""
    base = {}
    for record in live_records:
        base[record["pixel"]] = base.get(record["pixel"], 0) + record["calibrated_flux_ujy"]

    masked = set(extract.masked)
    pixels = set(base) | masked
    for pixel in masked:
        pixels.update(extract.relay_targets.get(pixel, []))

    resolved = {pixel: base.get(pixel, 0) for pixel in sorted(pixels)}
    relayed = {pixel: 0 for pixel in sorted(masked)}
    per_target = {pixel: {} for pixel in sorted(masked)}

    for _ in range(len(masked) + 1):
        moved = False
        for pixel in sorted(masked):
            amount = resolved[pixel]
            if amount == 0:
                continue
            moved = True
            resolved[pixel] = 0
            relayed[pixel] += amount
            targets = sorted(extract.relay_targets.get(pixel, []))
            if not targets:
                continue
            share = floor_div(amount, len(targets))
            leftover = amount - share * len(targets)
            for index, target in enumerate(targets):
                sent = share + (leftover if index == 0 else 0)
                resolved[target] = resolved.get(target, 0) + sent
                per_target[pixel][target] = per_target[pixel].get(target, 0) + sent
        if not moved:
            break

    def terminals(pixel):
        found = set()
        seen = set()
        stack = list(extract.relay_targets.get(pixel, []))
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            if node in masked:
                stack.extend(extract.relay_targets.get(node, []))
            else:
                found.add(node)
        return sorted(found)

    relays = []
    for pixel in sorted(masked):
        targets = sorted(extract.relay_targets.get(pixel, []))
        amounts = {t: per_target[pixel].get(t, 0) for t in targets}
        if targets and relayed[pixel] == 0:
            amounts = {t: 0 for t in targets}
        relays.append({
            "pixel": pixel,
            "relayed_ujy": relayed[pixel],
            "targets": targets,
            "per_target_ujy": amounts,
            "terminal_pixels": terminals(pixel),
        })
    return resolved, relays


# --------------------------------------------------------------------------
# settlement layer
# --------------------------------------------------------------------------

def settle(extract, live_records):
    """Contract sections S1..S8 on top of the reconciled flux."""
    band_rank = {band: i for i, band in enumerate(extract.bands)}
    zero_exposure = []
    settled = []
    near_saturated = []

    for record in live_records:
        if (
            record["raw_counts"] * 100 >= record["full_well_counts"] * NEAR_SATURATION_PERCENT
            and record["raw_counts"] <= record["full_well_counts"]
        ):
            near_saturated.append(record)
        exposure_ms, shutter_state = extract.exposure[record["obs_id"]]
        if shutter_state == "aborted" or exposure_ms == 0:
            zero_exposure.append({
                "obs_id": record["obs_id"],
                "shutter_state": shutter_state,
            })
            continue
        rate = floor_div(record["calibrated_flux_ujy"] * 1000000, exposure_ms)
        settled.append({
            "obs_id": record["obs_id"],
            "instrument": record["instrument"],
            "band": record["band"],
            "exposure_ms": exposure_ms,
            "calibrated_flux_ujy": record["calibrated_flux_ujy"],
            "rate_ujy_per_ks": rate,
        })

    near_ids = {r["obs_id"] for r in near_saturated}

    groups = {}
    for entry in settled:
        groups.setdefault((entry["instrument"], entry["band"]), []).append(entry)

    rejects = []
    rejected_ids = set()
    for key in sorted(groups):
        members = groups[key]
        if len(members) < 4:
            continue
        rates = [m["rate_ujy_per_ks"] for m in members]
        med = lower_median(rates)
        mad = lower_median([abs(rate - med) for rate in rates])
        threshold = med + MAD_MULTIPLIER * mad
        for member in members:
            if member["obs_id"] in near_ids:
                continue
            if member["rate_ujy_per_ks"] > threshold:
                rejected_ids.add(member["obs_id"])
                rejects.append({
                    "obs_id": member["obs_id"],
                    "instrument": member["instrument"],
                    "band": member["band"],
                    "rate_ujy_per_ks": member["rate_ujy_per_ks"],
                    "group_median": med,
                    "group_mad": mad,
                    "threshold": threshold,
                })

    survivors = [e for e in settled if e["obs_id"] not in rejected_ids]
    pool = sum(e["rate_ujy_per_ks"] for e in survivors)

    ranked = sorted(
        survivors,
        key=lambda e: (-e["rate_ujy_per_ks"], band_rank.get(e["band"], 0), e["obs_id"]),
    )
    digest = 0
    order = []
    for position, entry in enumerate(ranked, start=1):
        digest += position * entry["rate_ujy_per_ks"]
        order.append({
            "position": position,
            "obs_id": entry["obs_id"],
            "rate_ujy_per_ks": entry["rate_ujy_per_ks"],
        })
    digest %= DIGEST_MODULUS

    return {
        "zero_exposure": sorted(zero_exposure, key=lambda e: e["obs_id"]),
        "settled": sorted(settled, key=lambda e: e["obs_id"]),
        "rejects": sorted(rejects, key=lambda e: e["obs_id"]),
        "near_saturated": sorted(near_saturated, key=lambda r: r["obs_id"]),
        "survivors": survivors,
        "pool": pool,
        "order": order,
        "digest": digest,
    }


# --------------------------------------------------------------------------
# writers
# --------------------------------------------------------------------------

def write_json(out_dir, name, payload):
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2, sort_keys=True))
        handle.write("\n")


def write_text(out_dir, name, text):
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def write_rows(out_dir, name, header, rows, delimiter):
    lines = [delimiter.join(header)]
    for row in rows:
        lines.append(delimiter.join(str(cell) for cell in row))
    write_text(out_dir, name, "\n".join(lines) + "\n")


def sum_by(records, key):
    totals = {}
    counts = {}
    for record in records:
        value = record[key]
        totals[value] = totals.get(value, 0) + record["calibrated_flux_ujy"]
        counts[value] = counts.get(value, 0) + 1
    return totals, counts


def build(data_dir, out_dir):
    extract = Extract(data_dir)
    records = reconcile(extract)
    by_id = {r["obs_id"]: r for r in records}

    dropped_ids = sorted(oid for oid in extract.disputed if oid in by_id)
    dropped_set = set(dropped_ids)
    live = [r for r in records if r["obs_id"] not in dropped_set]

    band_flux, band_counts = sum_by(live, "band")
    epoch_flux, epoch_counts = sum_by(live, "epoch")
    instrument_flux, instrument_counts = sum_by(live, "instrument")

    channel_usage = {}
    for record in live:
        channel_usage[record["resolved_channel"]] = (
            channel_usage.get(record["resolved_channel"], 0) + 1
        )

    eligible = {}
    for record in live:
        if not record["saturated"]:
            eligible.setdefault(record["band"], []).append(record["calibrated_flux_ujy"])
    medians = {}
    for band, values in eligible.items():
        median = band_median(values)
        if median is not None:
            medians[band] = median

    resolved_pixels, relays = close_deadpixels(extract, live)
    total = sum(resolved_pixels.values())

    anomalies = []
    for record in live:
        if record["saturated"]:
            continue
        median = medians.get(record["band"])
        if median is None:
            continue
        if record["calibrated_flux_ujy"] > ANOMALY_MULTIPLIER * median:
            anomalies.append({
                "obs_id": record["obs_id"],
                "band": record["band"],
                "calibrated_flux_ujy": record["calibrated_flux_ujy"],
                "band_median": median,
            })
    anomalies.sort(key=lambda a: a["obs_id"])

    saturated_ids = sorted(r["obs_id"] for r in live if r["saturated"])
    suspect_clear = sorted(
        r["obs_id"] for r in live if r["quality_flag"] == "suspect"
    )

    attributed, recipients = largest_remainder(total, extract.exposure_weight)
    settlement = settle(extract, live)
    settled_attributed, _ = largest_remainder(
        settlement["pool"], extract.exposure_weight
    )

    os.makedirs(out_dir, exist_ok=True)

    # --- whole-corpus report -------------------------------------------
    write_json(out_dir, "summary.json", {
        "report_id": REPORT_ID,
        "observation_count": len(records),
        "live_count": len(live),
        "dropped_count": len(dropped_ids),
        "total_reconciled_flux_ujy": total,
        "band_flux_ujy": band_flux,
        "epoch_flux_ujy": epoch_flux,
        "instrument_flux_ujy": instrument_flux,
        "channel_usage": channel_usage,
        "band_median_ujy": medians,
    })

    write_json(out_dir, "reconciled_flux.json", {
        "report_id": REPORT_ID,
        "observations": [
            {
                "obs_id": r["obs_id"],
                "instrument": r["instrument"],
                "band": r["band"],
                "epoch": r["epoch"],
                "resolved_channel": r["resolved_channel"],
                "effective_counts": r["effective_counts"],
                "saturated": r["saturated"],
                "net_counts": r["net_counts"],
                "linearized": r["linearized"],
                "drift_ppm": r["drift_ppm"],
                "drift_correction": r["drift_correction"],
                "calibrated_flux_ujy": r["calibrated_flux_ujy"],
            }
            for r in records
        ],
    })

    live_instruments = set(instrument_flux)
    live_epochs = set(epoch_flux)
    live_channels = set(channel_usage)
    folds = set()
    _, fold_by_epoch = extract.fold
    for (label, epoch), resolved in fold_by_epoch.items():
        if resolved != label:
            folds.add("%s:%s->%s" % (label, epoch, resolved))

    write_json(out_dir, "calibration_audit.json", {
        "report_id": REPORT_ID,
        "scale_factor_micro": {
            k: v for k, v in extract.scale_micro.items() if k in live_instruments
        },
        "gain_micro_e_per_count": {
            k: v for k, v in extract.gain_micro.items() if k in live_channels
        },
        "drift_ppm": {
            "%s:%s" % (instrument, epoch): ppm
            for (instrument, epoch), ppm in extract.drift_ppm.items()
        },
        "nonlinearity_coeffs": {
            k: v for k, v in extract.coefficients.items() if k in live_instruments
        },
        "epoch_windows": {
            epoch: [bounds[0], bounds[1]]
            for epoch, bounds in extract.epoch_windows.items()
            if epoch in live_epochs
        },
        "fold_applied": sorted(folds),
    })

    write_json(out_dir, "data_quality.json", {
        "report_id": REPORT_ID,
        "input_file_count": extract.input_file_count,
        "observation_count": len(records),
        "disputed_count": len(dropped_ids),
        "masked_pixel_count": len(extract.masked),
        "distinct_pixels": len(resolved_pixels),
        "suspect_but_not_disputed": suspect_clear,
        "saturated_count": len(saturated_ids),
        "saturated_obs_ids": saturated_ids,
    })

    for instrument in extract.instruments:
        subset = [r for r in live if r["instrument"] == instrument]
        bflux, _ = sum_by(subset, "band")
        eflux, _ = sum_by(subset, "epoch")
        write_json(out_dir, "instrument_%s.json" % instrument, {
            "instrument": instrument,
            "observation_count": len(subset),
            "flux_ujy": sum(r["calibrated_flux_ujy"] for r in subset),
            "band_flux_ujy": bflux,
            "epoch_flux_ujy": eflux,
        })

    write_json(out_dir, "epoch_totals.json", {
        "report_id": REPORT_ID,
        "epoch_flux_ujy": epoch_flux,
        "epoch_observation_count": epoch_counts,
    })

    write_json(out_dir, "deadpixel_closure.json", {
        "report_id": REPORT_ID,
        "masked_pixel_count": len(extract.masked),
        "resolved_pixel_flux_ujy": resolved_pixels,
        "total_after_closure_ujy": total,
    })

    write_json(out_dir, "anomaly_ledger.json", {
        "report_id": REPORT_ID,
        "rule": "flux > 3 * band median (live, non-saturated only)",
        "anomalies": anomalies,
    })

    ranked = sorted(live, key=lambda r: (-r["calibrated_flux_ujy"], r["obs_id"]))
    write_json(out_dir, "ordered_flux_index.json", {
        "report_id": REPORT_ID,
        "order": "calibrated_flux_ujy desc, obs_id asc",
        "index": [
            {
                "rank": position,
                "obs_id": r["obs_id"],
                "calibrated_flux_ujy": r["calibrated_flux_ujy"],
            }
            for position, r in enumerate(ranked, start=1)
        ],
    })

    write_json(out_dir, "dropped_observations.json", {
        "report_id": REPORT_ID,
        "source": "adjudication_dossier.pdf",
        "dropped_obs_ids": dropped_ids,
    })

    write_json(out_dir, "provenance_manifest.json", {
        "report_id": REPORT_ID,
        "scale_factor_source": "gain_scale_workbook.xlsx",
        "disputed_source": "adjudication_dossier.pdf",
        "raw_counts_source": "obs_capture_index.csv",
        "full_well_source": "full_well_capacity.tsv",
        "exposure_weight_source": "exposure_weight_micro.tsv",
        "attribution_method": "largest_remainder",
        "pipeline_order": [
            "clip", "dark", "nonlinearity", "gain", "scale", "drift", "quantize",
        ],
        "rounding": "half_even",
        "drift_operation": "subtract",
        "deadpixel_resolution": "least_fixed_point",
        "source_precedence": ["adjudication_dossier.pdf", "csv_quality_flag"],
        "total_reconciled_flux_ujy": total,
    })

    write_json(out_dir, "flux_attribution.json", {
        "report_id": REPORT_ID,
        "pool_ujy": total,
        "exposure_weight_micro": dict(extract.exposure_weight),
        "attributed_ujy": attributed,
        "remainder_recipients": recipients,
    })

    write_json(out_dir, "relay_audit.json", {
        "report_id": REPORT_ID,
        "masked_pixel_count": len(extract.masked),
        "relays": relays,
    })

    # --- delimited rollups ---------------------------------------------
    write_rows(
        out_dir, "band_rollup.csv",
        ["band", "flux_ujy", "observation_count"],
        [[b, band_flux.get(b, 0), band_counts.get(b, 0)] for b in extract.bands],
        ",",
    )
    write_rows(
        out_dir, "epoch_rollup.tsv",
        ["epoch", "flux_ujy", "observation_count"],
        [[e, epoch_flux.get(e, 0), epoch_counts.get(e, 0)] for e in extract.epochs],
        "\t",
    )
    write_rows(
        out_dir, "instrument_rollup.psv",
        ["instrument", "flux_ujy", "observation_count"],
        [
            [g, instrument_flux.get(g, 0), instrument_counts.get(g, 0)]
            for g in extract.instruments
        ],
        "|",
    )

    # --- remaining whole-corpus artifacts ------------------------------
    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<flagged_observations>"]
    for anomaly in anomalies:
        xml_lines.append(
            '  <observation obs_id="%s" band="%s" calibrated_flux_ujy="%d" '
            'band_median="%d"/>' % (
                anomaly["obs_id"], anomaly["band"],
                anomaly["calibrated_flux_ujy"], anomaly["band_median"],
            )
        )
    xml_lines.append("</flagged_observations>")
    write_text(out_dir, "flagged_observations.xml", "\n".join(xml_lines) + "\n")

    yaml_lines = ["anomaly_count: %d" % len(anomalies), "band_flux_ujy:"]
    for band in sorted(band_flux):
        yaml_lines.append("  %s: %d" % (band, band_flux[band]))
    yaml_lines.append("dropped_count: %d" % len(dropped_ids))
    yaml_lines.append("live_count: %d" % len(live))
    yaml_lines.append("report_id: %s" % REPORT_ID)
    yaml_lines.append("total_reconciled_flux_ujy: %d" % total)
    write_text(out_dir, "objective_summary.yaml", "\n".join(yaml_lines) + "\n")

    md = [
        "# Detector Flux Reconciliation Report",
        "",
        "- report_id: %s" % REPORT_ID,
        "- observation_count: %d" % len(records),
        "- live_count: %d" % len(live),
        "- dropped_count: %d" % len(dropped_ids),
        "- masked_pixel_count: %d" % len(extract.masked),
        "- anomaly_count: %d" % len(anomalies),
        "- total_reconciled_flux_ujy: %d" % total,
        "",
        "## Flux by band",
        "",
        "| band | flux_ujy | observation_count |",
        "|------|----------|-------------------|",
    ]
    for band in extract.bands:
        md.append("| %s | %d | %d |" % (
            band, band_flux.get(band, 0), band_counts.get(band, 0)
        ))
    md += [
        "",
        "## Flux by epoch",
        "",
        "| epoch | flux_ujy | observation_count |",
        "|-------|----------|-------------------|",
    ]
    for epoch in extract.epochs:
        md.append("| %s | %d | %d |" % (
            epoch, epoch_flux.get(epoch, 0), epoch_counts.get(epoch, 0)
        ))
    md.append("")
    write_text(out_dir, "reconciliation_report.md", "\n".join(md) + "\n")

    write_text(out_dir, "run_status.txt", "".join([
        "status: ok\n",
        "observations: %d\n" % len(records),
        "live: %d\n" % len(live),
        "dropped: %d\n" % len(dropped_ids),
        "total_reconciled_flux_ujy: %d\n" % total,
    ]))

    # --- settlement artifacts ------------------------------------------
    survivors = settlement["survivors"]
    write_json(out_dir, "settlement_summary.json", {
        "report_id": REPORT_ID,
        "settled_pool_ujy": settlement["pool"],
        "settlement_digest": settlement["digest"],
        "settled_count": len(survivors),
        "rejected_count": len(settlement["rejects"]),
        "zero_exposure_count": len(settlement["zero_exposure"]),
        "near_saturated_count": len(settlement["near_saturated"]),
    })

    write_json(out_dir, "settled_rates.json", {
        "report_id": REPORT_ID,
        "rates": [
            {
                "obs_id": e["obs_id"],
                "instrument": e["instrument"],
                "band": e["band"],
                "exposure_ms": e["exposure_ms"],
                "calibrated_flux_ujy": e["calibrated_flux_ujy"],
                "rate_ujy_per_ks": e["rate_ujy_per_ks"],
            }
            for e in settlement["settled"]
        ],
    })

    write_json(out_dir, "zero_exposure.json", {
        "report_id": REPORT_ID,
        "observations": settlement["zero_exposure"],
    })

    write_json(out_dir, "cosmic_ray_rejects.json", {
        "report_id": REPORT_ID,
        "rejects": settlement["rejects"],
    })

    write_json(out_dir, "near_saturation.json", {
        "report_id": REPORT_ID,
        "observations": [
            {
                "obs_id": r["obs_id"],
                "instrument": r["instrument"],
                "raw_counts": r["raw_counts"],
                "full_well_counts": r["full_well_counts"],
            }
            for r in settlement["near_saturated"]
        ],
    })

    write_json(out_dir, "settled_attribution.json", {
        "report_id": REPORT_ID,
        "settled_pool_ujy": settlement["pool"],
        "attributed_ujy": settled_attributed,
    })

    settled_band_count = {}
    settled_band_pool = {}
    for entry in survivors:
        band = entry["band"]
        settled_band_count[band] = settled_band_count.get(band, 0) + 1
        settled_band_pool[band] = (
            settled_band_pool.get(band, 0) + entry["rate_ujy_per_ks"]
        )
    write_rows(
        out_dir, "band_settlement.csv",
        ["band", "settled_count", "settled_pool_ujy"],
        [
            [b, settled_band_count.get(b, 0), settled_band_pool.get(b, 0)]
            for b in extract.bands
        ],
        ",",
    )

    write_json(out_dir, "settlement_order.json", {
        "report_id": REPORT_ID,
        "order": settlement["order"],
    })

    # --- per-dimension rollups -----------------------------------------
    for instrument in extract.instruments:
        for band in extract.bands:
            cell = [
                r for r in live
                if r["instrument"] == instrument and r["band"] == band
            ]
            write_json(out_dir, "cell_%s_%s.json" % (instrument, band), {
                "instrument": instrument,
                "band": band,
                "observation_count": len(cell),
                "flux_ujy": sum(r["calibrated_flux_ujy"] for r in cell),
                "saturated_count": sum(1 for r in cell if r["saturated"]),
                "obs_ids": sorted(r["obs_id"] for r in cell),
            })

    for epoch in extract.epochs:
        for band in extract.bands:
            rows = []
            for instrument in extract.instruments:
                cell = [
                    r for r in live
                    if r["epoch"] == epoch
                    and r["band"] == band
                    and r["instrument"] == instrument
                ]
                rows.append([
                    instrument,
                    sum(r["calibrated_flux_ujy"] for r in cell),
                    len(cell),
                ])
            write_rows(
                out_dir, "grid_%s_%s.psv" % (epoch, band),
                ["instrument", "flux_ujy", "observation_count"], rows, "|",
            )

    for instrument in extract.instruments:
        for epoch in extract.epochs:
            rows = []
            for band in extract.bands:
                cell = [
                    r for r in live
                    if r["instrument"] == instrument
                    and r["epoch"] == epoch
                    and r["band"] == band
                ]
                rows.append([
                    band,
                    sum(r["calibrated_flux_ujy"] for r in cell),
                    len(cell),
                ])
            write_rows(
                out_dir, "span_%s_%s.tsv" % (instrument, epoch),
                ["band", "flux_ujy", "observation_count"], rows, "\t",
            )


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    build(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
