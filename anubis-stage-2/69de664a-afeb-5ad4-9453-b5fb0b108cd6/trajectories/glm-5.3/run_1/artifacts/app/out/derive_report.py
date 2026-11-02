#!/usr/bin/env python3
"""Detector-array flux reconciliation.

Reads a reconciliation extract from DATA_DIR and writes the full report set
into OUT_DIR, per reconciliation_contract.md and report_schema.md.

Usage:  python3 derive_report.py DATA_DIR OUT_DIR
"""

import collections
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from fractions import Fraction

REPORT_ID = "detector-flux-reconciliation"
BAND_DEFAULT = ["u", "g", "r", "i", "z"]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def read_text(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        return fh.read()


def read_delimited(path, delimiter=","):
    """Parse a delimited file into a list of dicts keyed by stripped headers."""
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        text = fh.read()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    header = [h.strip() for h in lines[0].split(delimiter)]
    rows = []
    for ln in lines[1:]:
        parts = ln.split(delimiter)
        row = {}
        for i, key in enumerate(header):
            row[key] = parts[i].strip() if i < len(parts) else ""
        rows.append(row)
    return rows


def read_jsonl(path):
    if not os.path.isfile(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def as_int(value, default=None):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def round_half_even(value):
    """Banker's rounding of an exact rational (Fraction/int) to an int."""
    if isinstance(value, int):
        return value
    num, den = value.numerator, value.denominator
    quot, rem = divmod(num, den)
    twice = 2 * rem
    if twice < den:
        return quot
    if twice > den:
        return quot + 1
    return quot if quot % 2 == 0 else quot + 1


def floor_div(value):
    """Floor of an exact rational toward negative infinity."""
    if isinstance(value, int):
        return value
    return value.numerator // value.denominator


# --------------------------------------------------------------------------- #
# minimal YAML subset parser (mappings, lists of scalars/maps, scalars)
# --------------------------------------------------------------------------- #

def _yaml_scalar(token):
    token = token.strip()
    if token == "" or token == "~" or token == "null":
        return None
    if (token[0] == token[-1]) and token[0] in "\"'" and len(token) > 1:
        return token[1:-1]
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    if token.lower() in ("true", "false"):
        return token.lower() == "true"
    return token


def _yaml_lines(text):
    out = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        out.append((indent, raw.strip()))
    return out


def _is_seq(line):
    return line == "-" or line.startswith("- ")


def _yaml_block(lines, pos, indent):
    """Parse one block starting at lines[pos] with the given indent.

    Returns (value, next_pos) where value is a list, a dict or a scalar.
    """
    if pos >= len(lines) or lines[pos][0] != indent:
        return None, pos

    if _is_seq(lines[pos][1]):
        seq = []
        while pos < len(lines) and lines[pos][0] == indent and _is_seq(lines[pos][1]):
            body = lines[pos][1][1:].strip()
            pos += 1
            if not body:
                if pos < len(lines) and lines[pos][0] > indent:
                    sub, pos = _yaml_block(lines, pos, lines[pos][0])
                    seq.append(sub)
                else:
                    seq.append(None)
                continue
            if ":" not in body:
                seq.append(_yaml_scalar(body))
                continue
            key, _, rest = body.partition(":")
            item = {key.strip(): (_yaml_scalar(rest) if rest.strip() else None)}
            while pos < len(lines) and lines[pos][0] > indent:
                entry = lines[pos][1]
                if entry == "-" or entry.startswith("- "):
                    sub, pos = _yaml_block(lines, pos, lines[pos][0])
                    item["_items"] = [sub]
                    break
                if ":" not in entry:
                    break
                k, _, v = entry.partition(":")
                if v.strip():
                    item[k.strip()] = _yaml_scalar(v)
                    pos += 1
                elif pos + 1 < len(lines) and lines[pos + 1][0] > lines[pos][0]:
                    sub, pos = _yaml_block(lines, pos + 1, lines[pos + 1][0])
                    item[k.strip()] = sub
                elif pos + 1 < len(lines) and lines[pos + 1][0] == lines[pos][0] \
                        and _is_seq(lines[pos + 1][1]):
                    sub, pos = _yaml_block(lines, pos + 1, lines[pos + 1][0])
                    item[k.strip()] = sub
                else:
                    item[k.strip()] = None
                    pos += 1
            seq.append(item)
        return seq, pos

    mapping = {}
    while pos < len(lines) and lines[pos][0] == indent and not _is_seq(lines[pos][1]):
        line = lines[pos][1]
        if ":" not in line:
            pos += 1
            continue
        key, _, value = line.partition(":")
        key = key.strip().strip("\"'")
        value = value.strip()
        pos += 1
        if value:
            mapping[key] = _yaml_scalar(value)
        elif pos < len(lines) and lines[pos][0] > indent:
            sub, pos = _yaml_block(lines, pos, lines[pos][0])
            mapping[key] = sub
        elif pos < len(lines) and lines[pos][0] == indent and _is_seq(lines[pos][1]):
            sub, pos = _yaml_block(lines, pos, indent)
            mapping[key] = sub
        else:
            mapping[key] = None
    return mapping, pos


def parse_yaml(text):
    lines = _yaml_lines(text)
    if not lines:
        return {}
    obj, _ = _yaml_block(lines, 0, lines[0][0])
    return obj if isinstance(obj, dict) else {}


def load_yaml(data_dir, name):
    path = os.path.join(data_dir, name)
    if not os.path.isfile(path):
        return {}
    try:
        return parse_yaml(read_text(path))
    except Exception:
        return {}


# --------------------------------------------------------------------------- #
# PDF text extraction (adjudication dossier)
# --------------------------------------------------------------------------- #

def pdf_text(path):
    """Collect the literal strings of every content stream in the dossier."""
    with open(path, "rb") as fh:
        data = fh.read()
    chunks = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.S):
        raw = match.group(1)
        for candidate in (raw, raw.rstrip(b"\r\n"), raw.lstrip(b"\r\n")):
            try:
                chunks.append(zlib.decompress(candidate))
                break
            except Exception:
                continue
        else:
            chunks.append(raw)
    text = b"\n".join(chunks).decode("latin-1")
    return re.findall(r"\(([^()]*)\)", text)


_STATUS_WORDS = ("clear", "cleared", "disputed", "ok", "retain", "retained", "valid",
                 "invalid", "dropped", "flagged")


def load_adjudication(data_dir):
    """Return {obs_id: status} from the authoritative PDF dossier."""
    path = os.path.join(data_dir, "adjudication_dossier.pdf")
    verdicts = {}
    if os.path.isfile(path):
        tokens = pdf_text(path)
        rows = [[p.strip() for p in tok.split("|")] for tok in tokens]
        rows = [r for r in rows if len(r) >= 2]
        obs_idx = status_idx = None
        for parts in rows:
            low = [p.lower() for p in parts]
            if "obs_id" in low and any("adjudic" in p or "status" in p for p in low):
                obs_idx = low.index("obs_id")
                status_idx = next(
                    (i for i, p in enumerate(low) if "adjudic" in p or "status" in p), None)
                break
        if obs_idx is None or status_idx is None:
            # no header row: take the column whose values look like verdicts
            best = None
            for i in range(1, max(len(r) for r in rows)):
                hits = sum(1 for r in rows if len(r) > i and r[i].lower() in _STATUS_WORDS)
                if hits and (best is None or hits > best[1]):
                    best = (i, hits)
            if best is not None:
                obs_idx, status_idx = 0, best[0]
        if obs_idx is not None and status_idx is not None:
            for parts in rows:
                if len(parts) > max(obs_idx, status_idx):
                    verdicts[parts[obs_idx]] = parts[status_idx].lower()
    if verdicts:
        return verdicts
    # fallback: the (deliberately incomplete) notice
    for row in read_jsonl(os.path.join(data_dir, "partial_dispute_notice.jsonl")):
        verdicts[str(row.get("obs_id"))] = str(row.get("status", "")).lower()
    return verdicts


# --------------------------------------------------------------------------- #
# xlsx (scale factor workbook)
# --------------------------------------------------------------------------- #

def _xlsx_sheets(path):
    """Return {sheet_name: xml_bytes} for a zip-based workbook."""
    out = {}
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        workbook = zf.read("xl/workbook.xml").decode("utf-8") if "xl/workbook.xml" in names else ""
        rels = {}
        if "xl/_rels/workbook.xml.rels" in names:
            rel_xml = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8")
            for m in re.finditer(r"<Relationship[^>]*Id=\"([^\"]+)\"[^>]*Target=\"([^\"]+)\"", rel_xml):
                rels[m.group(1)] = m.group(2)
            if not rels:
                for m in re.finditer(r"<Relationship[^>]*Target=\"([^\"]+)\"[^>]*Id=\"([^\"]+)\"", rel_xml):
                    rels[m.group(2)] = m.group(1)
        sheet_tags = re.findall(r"<sheet[^>]*/>", workbook)
        for tag in sheet_tags:
            name = re.search(r'name="([^"]+)"', tag)
            rid = re.search(r'r:id="([^"]+)"', tag)
            if not name:
                continue
            target = rels.get(rid.group(1)) if rid else None
            if target is None:
                continue
            part = target if target.startswith("xl/") else "xl/" + target.lstrip("/")
            if part in names:
                out[name.group(1)] = zf.read(part)
        if not out:
            for n in names:
                if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"):
                    out[n] = zf.read(n)
    return out


def _sheet_rows(xml_bytes):
    """Parse a worksheet into a list of dicts keyed by the header row."""
    xml = xml_bytes.decode("utf-8")
    rows = []
    for row_xml in re.findall(r"<row\b.*?</row>|<row\b[^>]*/>", xml, re.S):
        cells = {}
        for m in re.finditer(
                r'<c r="([A-Z]+)\d+"[^>]*?(?:/>|>(.*?)</c>)', row_xml, re.S):
            col, inner = m.group(1), m.group(2) or ""
            value = None
            ism = re.search(r"<t[^>]*>(.*?)</t>", inner, re.S)
            if ism:
                value = ism.group(1)
            else:
                vm = re.search(r"<v>(.*?)</v>", inner, re.S)
                if vm:
                    value = vm.group(1)
            cells[col] = value
        rows.append(cells)
    if not rows:
        return []
    header = {}
    for col, value in rows[0].items():
        if value is not None:
            header[col] = str(value).strip()
    out = []
    for cells in rows[1:]:
        row = {}
        for col, value in cells.items():
            key = header.get(col)
            if key and value is not None:
                row[key] = str(value).strip()
        if row:
            out.append(row)
    return out


def load_scale_factors(data_dir):
    path = os.path.join(data_dir, "gain_scale_workbook.xlsx")
    if not os.path.isfile(path):
        return {}
    sheets = _xlsx_sheets(path)
    chosen = None
    for name in sorted(sheets):
        low = name.lower()
        if "authoritative" in low and "scale" in low:
            chosen = sheets[name]
            break
    if chosen is None:
        for name in sorted(sheets):
            if "scale" in name.lower():
                chosen = sheets[name]
                break
    if chosen is None and sheets:
        chosen = sorted(sheets.items())[0][1]
    if chosen is None:
        return {}
    rows = _sheet_rows(chosen)
    value_key = None
    for candidate in ("factor_micro", "factor", "scale_micro", "scale_factor_micro"):
        for row in rows:
            if candidate in row:
                value_key = candidate
                break
        if value_key:
            break
    if value_key is None:
        for row in rows:
            for key in row:
                if "factor" in key.lower() or "scale" in key.lower():
                    value_key = key
                    break
            if value_key:
                break
    if value_key is None:
        return {}
    out = {}
    for row in rows:
        inst = row.get("instrument")
        val = as_int(row.get(value_key))
        if inst and val is not None:
            out[inst] = val
    return out


# --------------------------------------------------------------------------- #
# reference tables
# --------------------------------------------------------------------------- #

def _authoritative_rows(rows):
    """Prefer rows whose row_kind says authoritative, when the column exists."""
    marked = [r for r in rows if r.get("row_kind")]
    if rows and not marked:
        return rows
    return [r for r in rows if r.get("row_kind") == "authoritative"] or rows


def load_full_well(data_dir):
    out = {}
    for row in _authoritative_rows(
            read_delimited(os.path.join(data_dir, "full_well_capacity.tsv"), "\t")):
        inst = row.get("instrument")
        val = as_int(row.get("full_well_counts"))
        if inst and val is not None and inst not in out:
            out[inst] = val
    return out


def load_dark_current(data_dir):
    """(instrument, band, epoch) -> dark counts, authoritative source first."""
    out = {}
    for row in read_delimited(os.path.join(data_dir, "pedestal_authoritative.csv"), ","):
        inst, band, epoch = row.get("instrument"), row.get("band"), row.get("epoch")
        val = as_int(row.get("dark_current_counts"))
        if inst and band and epoch and val is not None and (inst, band, epoch) not in out:
            out[(inst, band, epoch)] = val
    if out:
        return out
    for row in _authoritative_rows(
            read_delimited(os.path.join(data_dir, "baseline_pedestal_grid.tsv"), "\t")):
        inst, band, epoch = row.get("instrument"), row.get("band"), row.get("epoch")
        val = as_int(row.get("dark_current_counts"))
        if inst and band and epoch and val is not None and (inst, band, epoch) not in out:
            out[(inst, band, epoch)] = val
    return out


def load_gain(data_dir):
    """channel -> micro-e-per-count (quantum_yield_micro.json is authoritative)."""
    out = {}
    path = os.path.join(data_dir, "quantum_yield_micro.json")
    if os.path.isfile(path):
        try:
            doc = json.loads(read_text(path))
        except ValueError:
            doc = {}
        channels = doc.get("channels") if isinstance(doc, dict) else None
        if isinstance(channels, dict):
            for key, value in channels.items():
                val = as_int(value)
                if val is not None:
                    out[key] = val
    if out:
        return out
    for row in read_delimited(os.path.join(data_dir, "yield_channel_values.psv"), "|"):
        channel = row.get("channel")
        val = as_int(row.get("micro_e_per_count"))
        if channel and val is not None and channel not in out:
            out[channel] = val
    return out


def load_nonlinearity(data_dir):
    """instrument -> coefficient list, highest degree first."""
    doc = load_yaml(data_dir, "response_curve_horner.yaml")
    coeffs = doc.get("coefficients") if isinstance(doc, dict) else None
    out = {}
    if isinstance(coeffs, dict):
        for inst, values in coeffs.items():
            if isinstance(values, list):
                nums = [as_int(v) for v in values]
                if all(n is not None for n in nums):
                    out[inst] = nums
    if out:
        return out
    path = os.path.join(data_dir, "instrument_capability_matrix.xml")
    if os.path.isfile(path):
        root = ET.parse(path).getroot()
        for node in root.iter("instrument"):
            inst = node.get("instrument")
            keys = [k for k in node.keys() if k != "instrument"]
            def degree(key):
                m = re.search(r"a(\d+)", key)
                return int(m.group(1)) if m else 0
            pairs = sorted(((degree(k), as_int(node.get(k))) for k in keys),
                           key=lambda p: p[0], reverse=True)
            if inst and all(p[1] is not None for p in pairs):
                out[inst] = [p[1] for p in pairs]
    return out


def load_drift(data_dir):
    """(instrument, epoch) -> ppm."""
    doc = load_yaml(data_dir, "thermal_drift_ppm.yml")
    table = doc.get("table") if isinstance(doc, dict) else None
    out = {}
    if isinstance(table, list):
        for row in table:
            if not isinstance(row, dict):
                continue
            inst, epoch = row.get("instrument"), row.get("epoch")
            val = as_int(row.get("drift_ppm"))
            if inst and epoch and val is not None and (inst, epoch) not in out:
                out[(inst, epoch)] = val
    if out:
        return out
    for row in read_delimited(os.path.join(data_dir, "drift_ppm_matrix.tsv"), "\t"):
        inst, epoch = row.get("instrument"), row.get("epoch")
        val = as_int(row.get("drift_ppm"))
        if inst and epoch and val is not None and (inst, epoch) not in out:
            out[(inst, epoch)] = val
    return out


def load_epoch_windows(data_dir):
    """epoch -> (mjd_start, mjd_end), half-open."""
    path = os.path.join(data_dir, "epoch_window_bounds.json")
    out = {}
    if os.path.isfile(path):
        try:
            doc = json.loads(read_text(path))
        except ValueError:
            doc = {}
        epochs = doc.get("epochs") if isinstance(doc, dict) else None
        if isinstance(epochs, dict):
            for name, spec in epochs.items():
                start = as_int(spec.get("mjd_start"))
                end = as_int(spec.get("mjd_end"))
                if start is not None and end is not None:
                    out[name] = (start, end)
    if out:
        return out
    doc = load_yaml(data_dir, "epoch_capacity_profile.yaml")
    epochs = doc.get("epochs") if isinstance(doc, dict) else None
    if isinstance(epochs, list):
        for row in epochs:
            if not isinstance(row, dict):
                continue
            name = row.get("epoch")
            start, end = as_int(row.get("mjd_start")), as_int(row.get("mjd_end"))
            if name and start is not None and end is not None:
                out[name] = (start, end)
    return out


def load_fold(data_dir):
    """Return (exact mjd-keyed folds, resolver, raw fold rows).

    The contract resolves a written gain label by (written label, mjd); the
    fold table repeats its mapping across the mjds of an epoch, so the resolver
    prefers an exact mjd row, then a (label, epoch) mapping that is constant,
    then the latest row at or before the observation's mjd.
    """
    rows = []
    for row in read_delimited(os.path.join(data_dir, "channel_lineage_fold.psv"), "|"):
        label = row.get("written_label")
        epoch = row.get("epoch")
        mjd = as_int(row.get("mjd"))
        resolved = row.get("resolved_channel")
        if label and epoch and resolved:
            rows.append((label, epoch, mjd, resolved))
    exact = {}
    by_pair = collections.defaultdict(list)
    for label, epoch, mjd, resolved in rows:
        if mjd is not None:
            exact[(label, epoch, mjd)] = resolved
        by_pair[(label, epoch)].append((mjd if mjd is not None else None, resolved))

    def resolve(label, epoch, mjd=None):
        if mjd is not None and (label, epoch, mjd) in exact:
            return exact[(label, epoch, mjd)]
        entries = by_pair.get((label, epoch))
        if not entries:
            return label
        values = {resolved for _, resolved in entries}
        if len(values) == 1:
            return sorted(entries)[0][1]
        dated = sorted((m, resolved) for m, resolved in entries if m is not None)
        if not dated:
            return label
        if mjd is None:
            return dated[0][1]
        chosen = None
        for row_mjd, resolved in dated:
            if row_mjd <= mjd:
                chosen = resolved
        return chosen if chosen is not None else dated[0][1]

    return exact, resolve, rows


def load_relay(data_dir):
    """Return (masked pixels, edges: pixel -> ascending relay targets).

    The occlusion relay graph is authoritative; the jsonl edge list is used
    only when the graph carries no relay edges at all.
    """
    collected = {}

    def add(pixel, targets):
        bucket = collected.setdefault(pixel, set())
        bucket.update(targets)

    path = os.path.join(data_dir, "occlusion_relay_graph.xml")
    if os.path.isfile(path):
        root = ET.parse(path).getroot()
        for node in root.iter("node"):
            pixel = node.get("pixel")
            if not pixel:
                continue
            targets = node.get("targets")
            add(pixel, [t for t in (targets.split(";") if targets else []) if t])
    if not any(collected.values()):
        for row in read_jsonl(os.path.join(data_dir, "relay_edges.jsonl")):
            pixel = row.get("pixel")
            tgts = row.get("targets") or []
            if pixel:
                add(pixel, [str(t) for t in tgts])
    edges = {pixel: sorted(bucket) for pixel, bucket in collected.items()}
    masked = {p for p, tgts in edges.items() if tgts}
    if not masked:
        # last resort: the pixel registry marks masked pixels
        try:
            import sqlite3
            db = os.path.join(data_dir, "pixel_registry.db")
            if os.path.isfile(db):
                con = sqlite3.connect(db)
                try:
                    tables = [r[0] for r in con.execute(
                        "select name from sqlite_master where type='table'")]
                    for table in tables:
                        cols = [r[1] for r in con.execute("PRAGMA table_info(%s)" % table)]
                        if "pixel" in cols:
                            for row in con.execute("select * from %s" % table):
                                rec = dict(zip(cols, row))
                                if str(rec.get("masked", "")).lower() in ("yes", "true", "1"):
                                    masked.add(str(rec["pixel"]))
                finally:
                    con.close()
        except Exception:
            pass
    return masked, edges


def load_exposure(data_dir):
    """obs_id -> (exposure_ms, shutter_state)."""
    out = {}
    for row in read_delimited(os.path.join(data_dir, "exposure_ledger.csv"), ","):
        obs_id = row.get("obs_id")
        if not obs_id:
            continue
        out[obs_id] = (as_int(row.get("exposure_ms"), 0), row.get("shutter_state", ""))
    return out


def load_exposure_weights(data_dir):
    out = {}
    for row in read_delimited(os.path.join(data_dir, "exposure_weight_micro.tsv"), "\t"):
        inst = row.get("instrument")
        val = as_int(row.get("weight_micro"))
        if inst and val is not None:
            out[inst] = val
    return out


def load_band_order(data_dir):
    path = os.path.join(data_dir, "band_index_map.xml")
    if os.path.isfile(path):
        pairs = []
        root = ET.parse(path).getroot()
        for node in root.iter("band"):
            name = node.get("band")
            index = as_int(node.get("index"))
            if name is not None and index is not None:
                pairs.append((index, name))
        if pairs:
            return [name for _, name in sorted(pairs)]
    return list(BAND_DEFAULT)


def load_observations(data_dir):
    """Canonical observation records from the authoritative stream.

    Column aliases (instr, adu, written_label, csv_quality, ...) are resolved
    per the field glossary, and the alternate stream views are only used if
    the authoritative capture index is absent.
    """
    rows = read_delimited(os.path.join(data_dir, "obs_capture_index.csv"), ",")
    if not rows:
        for name in ("capture_alt_view.csv", "frame_intake_stream.ndjson",
                     "arr_run_ledger_delta.jsonl", "raw_capture_mirror.jsonl"):
            candidate = os.path.join(data_dir, name)
            if not os.path.isfile(candidate):
                continue
            if name.endswith((".ndjson", ".jsonl")):
                rows = read_jsonl(candidate)
            else:
                rows = read_delimited(candidate, ",")
            if rows:
                break
    observations = []
    for row in rows:
        obs_id = row.get("obs_id")
        if not obs_id:
            continue
        instrument = row.get("instrument") or row.get("instr")
        band = row.get("band")
        mjd = as_int(row.get("mjd"))
        label = (row.get("gain_label") or row.get("written_label")
                 or row.get("written_gain_label"))
        raw = as_int(row.get("raw_counts") if row.get("raw_counts") is not None
                     else row.get("adu"))
        pixel = row.get("pixel")
        flag = (row.get("quality_flag") or row.get("csv_quality")
                or row.get("csv_quality_flag"))
        if None in (instrument, band, mjd, label, raw, pixel, flag):
            continue
        observations.append({
            "obs_id": obs_id,
            "instrument": instrument,
            "band": band,
            "mjd": mjd,
            "gain_label": label,
            "raw_counts": raw,
            "pixel": pixel,
            "quality_flag": flag,
        })
    observations.sort(key=lambda o: o["obs_id"])
    return observations


# --------------------------------------------------------------------------- #
# pipeline
# --------------------------------------------------------------------------- #

def resolve_epoch(mjd, windows):
    names = sorted(windows, key=lambda e: windows[e][0])
    for name in names:
        start, end = windows[name]
        if start <= mjd < end:
            return name
    if not names:
        return None
    first_start = windows[names[0]][0]
    last_end = windows[names[-1]][1]
    if mjd >= last_end:
        return names[-1]
    return names[0]


def build_records(ctx, observations):
    """Per-observation reconciliation (clip -> dark -> nonlinearity -> gain ->
    scale -> drift -> quantize)."""
    records = []
    windows = ctx["windows"]
    for obs in observations:
        inst, band, mjd = obs["instrument"], obs["band"], obs["mjd"]
        epoch = resolve_epoch(mjd, windows)
        full_well = ctx["full_well"].get(inst)
        raw = obs["raw_counts"]
        saturated = full_well is not None and raw > full_well
        effective = full_well if saturated else raw
        dark = ctx["dark"].get((inst, band, epoch), 0)
        net = effective - dark
        coeffs = ctx["coeffs"].get(inst, [])
        acc = Fraction(0)
        for coeff in coeffs:
            acc = acc * net + coeff
        linearized = round_half_even(acc / 1000000)
        channel = ctx["resolve_channel"](obs["gain_label"], epoch, mjd)
        gain_micro = ctx["gain"].get(channel)
        gain = Fraction(gain_micro, 1000000) if gain_micro is not None else Fraction(1)
        scale_micro = ctx["scale"].get(inst)
        scale = Fraction(scale_micro, 1000000) if scale_micro is not None else Fraction(1)
        scaled = Fraction(linearized) * gain * scale
        drift_ppm = ctx["drift"].get((inst, epoch), 0)
        correction = round_half_even(scaled * drift_ppm / 1000000)
        flux = round_half_even(scaled - correction)
        records.append({
            "obs_id": obs["obs_id"],
            "instrument": inst,
            "band": band,
            "mjd": mjd,
            "epoch": epoch,
            "gain_label": obs["gain_label"],
            "resolved_channel": channel,
            "raw_counts": raw,
            "full_well_counts": full_well,
            "effective_counts": effective,
            "saturated": saturated,
            "near_saturated": (full_well is not None and not saturated
                               and raw * 100 >= full_well * 98),
            "net_counts": net,
            "linearized": linearized,
            "drift_ppm": drift_ppm,
            "drift_correction": correction,
            "calibrated_flux_ujy": flux,
            "pixel": obs["pixel"],
            "quality_flag": obs["quality_flag"],
            "dropped": obs["obs_id"] in ctx["dropped"],
        })
    records.sort(key=lambda r: r["obs_id"])
    return records


def close_pixels(records, masked, edges):
    """Least-fixed-point dead-pixel redistribution.

    Returns (resolved flux per pixel, relayed amount per masked pixel, the
    pixel universe).
    """
    base = collections.defaultdict(int)
    for rec in records:
        if not rec["dropped"]:
            base[rec["pixel"]] += rec["calibrated_flux_ujy"]

    universe = set(base)
    universe |= masked
    reachable = set()
    stack = list(masked)
    while stack:
        pixel = stack.pop()
        for target in edges.get(pixel, []):
            if target not in reachable:
                reachable.add(target)
                stack.append(target)
    universe |= reachable

    pending = {p: base.get(p, 0) for p in masked}
    relayed = {p: 0 for p in masked}
    received = {p: 0 for p in universe}
    # Ascending-order passes until nothing moves. Any relay edge set that is
    # not cyclic terminates on the first pass; the bound only guards a
    # pathological cycle, which has no fixed point.
    for _ in range(4 * len(masked) + 8):
        moved = False
        for pixel in sorted(masked):
            amount = pending.get(pixel, 0)
            if amount <= 0:
                continue
            pending[pixel] = 0
            relayed[pixel] += amount
            targets = edges.get(pixel, [])
            if not targets:
                continue
            count = len(targets)
            share = amount // count
            leftover = amount - share * count
            for index, target in enumerate(targets):
                give = share + (leftover if index == 0 else 0)
                if give <= 0:
                    continue
                if target in masked:
                    pending[target] = pending.get(target, 0) + give
                else:
                    received[target] += give
            moved = True
        if not moved:
            break

    resolved = {}
    for pixel in sorted(universe):
        if pixel in masked:
            resolved[pixel] = 0
        else:
            resolved[pixel] = base.get(pixel, 0) + received.get(pixel, 0)
    return resolved, relayed, sorted(universe)


def terminal_pixels(pixel, masked, edges):
    out = set()
    stack = [pixel]
    seen = set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        for target in edges.get(current, []):
            if target in masked:
                stack.append(target)
            else:
                out.add(target)
    return sorted(out)


def band_median(values):
    """Reconciliation-layer median: banker's rounding of the two middle values."""
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    if n % 2 == 1:
        return ordered[n // 2]
    return round_half_even(Fraction(ordered[n // 2 - 1] + ordered[n // 2], 2))


def settle_median(values):
    """Settlement-layer median: lower of the two middle values for even n."""
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    if n % 2 == 1:
        return ordered[n // 2]
    return ordered[n // 2 - 1]


def largest_remainder(pool, weights):
    """Apportion pool across keys by published weights, largest remainder first."""
    keys = sorted(weights)
    total_weight = sum(weights.values())
    if total_weight == 0 or not keys:
        return {key: 0 for key in keys}, []
    base = {}
    remainders = []
    for key in keys:
        exact = Fraction(pool) * weights[key] / total_weight
        base[key] = floor_div(exact)
        remainders.append((exact - base[key], key))
    leftover = pool - sum(base.values())
    order = sorted(remainders, key=lambda item: (-item[0], item[1]))
    recipients = [key for _, key in order[:leftover]]
    for key in recipients:
        base[key] += 1
    return base, sorted(recipients)


# --------------------------------------------------------------------------- #
# output helpers
# --------------------------------------------------------------------------- #

def dump_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_lines(path, lines):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def render_yaml(obj, indent=0):
    """Deterministic YAML rendering with sorted keys."""
    lines = []
    pad = "  " * indent
    for key in sorted(obj):
        value = obj[key]
        if isinstance(value, dict):
            lines.append("%s%s:" % (pad, key))
            lines.extend(render_yaml(value, indent + 1))
        elif isinstance(value, bool):
            lines.append("%s%s: %s" % (pad, key, "true" if value else "false"))
        elif isinstance(value, int):
            lines.append("%s%s: %d" % (pad, key, value))
        else:
            lines.append("%s%s: %s" % (pad, key, str(value)))
    return lines


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def run(data_dir, out_dir):
    # ---- reference tables ------------------------------------------------- #
    full_well = load_full_well(data_dir)
    dark = load_dark_current(data_dir)
    gain = load_gain(data_dir)
    coeffs = load_nonlinearity(data_dir)
    drift = load_drift(data_dir)
    windows = load_epoch_windows(data_dir)
    fold_exact, fold_resolve, fold_rows = load_fold(data_dir)
    masked, edges = load_relay(data_dir)
    exposure = load_exposure(data_dir)
    weights = load_exposure_weights(data_dir)
    band_order = load_band_order(data_dir)
    scale = load_scale_factors(data_dir)
    verdicts = load_adjudication(data_dir)
    observations = load_observations(data_dir)
    known_ids = {o["obs_id"] for o in observations}

    dropped = {obs_id for obs_id, status in verdicts.items()
               if status == "disputed" and obs_id in known_ids}
    ctx = {
        "full_well": full_well,
        "dark": dark,
        "gain": gain,
        "coeffs": coeffs,
        "drift": drift,
        "windows": windows,
        "resolve_channel": fold_resolve,
        "scale": scale,
        "dropped": dropped,
    }
    records = build_records(ctx, observations)

    live = [r for r in records if not r["dropped"]]
    live.sort(key=lambda r: r["obs_id"])

    instrument_set = set(full_well) | set(coeffs) | set(scale) | set(weights)
    instrument_set |= {r["instrument"] for r in records}
    instruments = sorted(instrument_set)
    epoch_set = set(windows) | {r["epoch"] for r in records if r["epoch"]}
    epochs = sorted(epoch_set)
    bands = [b for b in band_order]
    for rec in records:
        if rec["band"] not in bands:
            bands.append(rec["band"])
    bands = sorted(set(bands), key=lambda b: (band_order.index(b)
                                             if b in band_order else 99, b))

    # ---- rollups --------------------------------------------------------- #
    def tally(keyfn, records_subset):
        flux = collections.defaultdict(int)
        count = collections.defaultdict(int)
        for rec in records_subset:
            key = keyfn(rec)
            flux[key] += rec["calibrated_flux_ujy"]
            count[key] += 1
        return flux, count

    band_flux, band_count = tally(lambda r: r["band"], live)
    epoch_flux, epoch_count = tally(lambda r: r["epoch"], live)
    inst_flux, inst_count = tally(lambda r: r["instrument"], live)

    channel_usage = collections.defaultdict(int)
    for rec in live:
        channel_usage[rec["resolved_channel"]] += 1

    # band medians over live, non-saturated observations
    eligible = collections.defaultdict(list)
    for rec in live:
        if not rec["saturated"]:
            eligible[rec["band"]].append(rec["calibrated_flux_ujy"])
    medians = {}
    for band, values in eligible.items():
        median = band_median(values)
        if median is not None:
            medians[band] = median

    anomalies = []
    for rec in live:
        median = medians.get(rec["band"])
        if median is None or rec["saturated"]:
            continue
        if rec["calibrated_flux_ujy"] > 3 * median:
            anomalies.append({
                "obs_id": rec["obs_id"],
                "band": rec["band"],
                "calibrated_flux_ujy": rec["calibrated_flux_ujy"],
                "band_median": median,
            })
    anomalies.sort(key=lambda a: a["obs_id"])

    # ---- dead-pixel closure ---------------------------------------------- #
    resolved_pixels, relayed, pixel_universe = close_pixels(live, masked, edges)
    total_after_closure = sum(resolved_pixels.values())
    sum_live_flux = sum(r["calibrated_flux_ujy"] for r in live)

    attributed, remainder_recipients = largest_remainder(total_after_closure, weights)

    # ---- ranked index ---------------------------------------------------- #
    ranked = sorted(live, key=lambda r: (-r["calibrated_flux_ujy"], r["obs_id"]))
    ordered_index = [{"rank": i + 1,
                      "obs_id": r["obs_id"],
                      "calibrated_flux_ujy": r["calibrated_flux_ujy"]}
                     for i, r in enumerate(ranked)]

    # ---- settlement layer ------------------------------------------------ #
    settled = []
    zero_exposure = []
    for rec in live:
        exposure_ms, shutter = exposure.get(rec["obs_id"], (None, ""))
        if shutter == "aborted" or exposure_ms is None or exposure_ms <= 0:
            zero_exposure.append({"obs_id": rec["obs_id"], "shutter_state": shutter})
            continue
        rec = dict(rec)
        rec["exposure_ms"] = exposure_ms
        rec["shutter_state"] = shutter
        rec["rate_ujy_per_ks"] = (rec["calibrated_flux_ujy"] * 1000000) // exposure_ms
        settled.append(rec)
    settled.sort(key=lambda r: r["obs_id"])
    zero_exposure.sort(key=lambda r: r["obs_id"])

    groups = collections.defaultdict(list)
    for rec in settled:
        groups[(rec["instrument"], rec["band"])].append(rec)
    group_stats = {}
    for key, members in groups.items():
        rates = [m["rate_ujy_per_ks"] for m in members]
        med = settle_median(rates)
        mad = settle_median([abs(rate - med) for rate in rates])
        group_stats[key] = (med, mad, med + 6 * mad, len(members))

    rejects = []
    surviving = []
    for rec in settled:
        med, mad, threshold, size = group_stats[(rec["instrument"], rec["band"])]
        is_reject = (size >= 4 and not rec["near_saturated"]
                     and rec["rate_ujy_per_ks"] > threshold)
        entry = {
            "obs_id": rec["obs_id"],
            "instrument": rec["instrument"],
            "band": rec["band"],
            "rate_ujy_per_ks": rec["rate_ujy_per_ks"],
            "group_median": med,
            "group_mad": mad,
            "threshold": threshold,
        }
        if is_reject:
            rejects.append(entry)
        else:
            surviving.append(rec)
    rejects.sort(key=lambda r: r["obs_id"])
    surviving.sort(key=lambda r: r["obs_id"])

    settled_pool = sum(r["rate_ujy_per_ks"] for r in surviving)
    settled_attributed, _ = largest_remainder(settled_pool, weights)

    band_position = {band: i for i, band in enumerate(bands)}
    settlement_ranked = sorted(
        surviving,
        key=lambda r: (-r["rate_ujy_per_ks"], band_position.get(r["band"], 99), r["obs_id"]))
    digest = 0
    for position, rec in enumerate(settlement_ranked, start=1):
        digest += position * rec["rate_ujy_per_ks"]
    digest %= 1000003

    band_settled_count = collections.defaultdict(int)
    band_settled_pool = collections.defaultdict(int)
    for rec in surviving:
        band_settled_count[rec["band"]] += 1
        band_settled_pool[rec["band"]] += rec["rate_ujy_per_ks"]

    near_saturated = [r for r in live if r["near_saturated"]]
    near_saturated.sort(key=lambda r: r["obs_id"])

    # ---- write artifacts -------------------------------------------------- #
    os.makedirs(out_dir, exist_ok=True)

    def out_path(name):
        return os.path.join(out_dir, name)

    suspect_not_disputed = sorted(
        r["obs_id"] for r in records
        if r["quality_flag"] and "suspect" in str(r["quality_flag"]).lower()
        and r["obs_id"] not in dropped)
    saturated_live = [r for r in live if r["saturated"]]

    summary = {
        "report_id": REPORT_ID,
        "observation_count": len(records),
        "live_count": len(live),
        "dropped_count": len(dropped),
        "total_reconciled_flux_ujy": total_after_closure,
        "band_flux_ujy": {b: band_flux[b] for b in sorted(band_flux)},
        "epoch_flux_ujy": {e: epoch_flux[e] for e in sorted(epoch_flux)},
        "instrument_flux_ujy": {i: inst_flux[i] for i in sorted(inst_flux)},
        "channel_usage": {c: channel_usage[c] for c in sorted(channel_usage)},
        "band_median_ujy": {b: medians[b] for b in sorted(medians)},
    }
    dump_json(out_path("summary.json"), summary)

    dump_json(out_path("reconciled_flux.json"), {
        "report_id": REPORT_ID,
        "observations": [{
            "obs_id": r["obs_id"],
            "instrument": r["instrument"],
            "band": r["band"],
            "epoch": r["epoch"],
            "resolved_channel": r["resolved_channel"],
            "effective_counts": r["effective_counts"],
            "saturated": bool(r["saturated"]),
            "net_counts": r["net_counts"],
            "linearized": r["linearized"],
            "drift_ppm": r["drift_ppm"],
            "drift_correction": r["drift_correction"],
            "calibrated_flux_ujy": r["calibrated_flux_ujy"],
        } for r in live],
    })

    dump_json(out_path("calibration_audit.json"), {
        "report_id": REPORT_ID,
        "scale_factor_micro": {i: scale[i] for i in sorted(scale)},
        "gain_micro_e_per_count": {c: gain[c] for c in sorted(gain)},
        "drift_ppm": {"%s:%s" % key: drift[key] for key in sorted(drift)},
        "nonlinearity_coeffs": {i: coeffs[i] for i in sorted(coeffs)},
        "epoch_windows": {e: [windows[e][0], windows[e][1]] for e in sorted(windows)},
        "fold_applied": sorted(
            {"%s:%s->%s" % (label, epoch, resolved)
             for label, epoch, resolved in
             {(row[0], row[1], fold_resolve(row[0], row[1], row[2])) for row in fold_rows}
             if resolved != label}),
    })

    dump_json(out_path("data_quality.json"), {
        "report_id": REPORT_ID,
        "input_file_count": len([n for n in os.listdir(data_dir)
                                 if os.path.isfile(os.path.join(data_dir, n))]),
        "observation_count": len(records),
        "disputed_count": len(dropped),
        "masked_pixel_count": len(masked),
        "distinct_pixels": len(pixel_universe),
        "suspect_but_not_disputed": suspect_not_disputed,
        "saturated_count": len(saturated_live),
        "saturated_obs_ids": sorted(r["obs_id"] for r in saturated_live),
    })

    for inst in instruments:
        per_inst = [r for r in live if r["instrument"] == inst]
        i_flux, i_count = tally(lambda r: r["band"], per_inst)
        e_flux, e_count = tally(lambda r: r["epoch"], per_inst)
        dump_json(out_path("instrument_%s.json" % inst), {
            "instrument": inst,
            "observation_count": len(per_inst),
            "flux_ujy": sum(r["calibrated_flux_ujy"] for r in per_inst),
            "band_flux_ujy": {b: i_flux[b] for b in sorted(i_flux)},
            "epoch_flux_ujy": {e: e_flux[e] for e in sorted(e_flux)},
        })

    dump_json(out_path("epoch_totals.json"), {
        "report_id": REPORT_ID,
        "epoch_flux_ujy": {e: epoch_flux[e] for e in sorted(epoch_flux)},
        "epoch_observation_count": {e: epoch_count[e] for e in sorted(epoch_count)},
    })

    dump_json(out_path("deadpixel_closure.json"), {
        "report_id": REPORT_ID,
        "masked_pixel_count": len(masked),
        "resolved_pixel_flux_ujy": {p: resolved_pixels[p] for p in sorted(resolved_pixels)},
        "total_after_closure_ujy": total_after_closure,
    })

    dump_json(out_path("anomaly_ledger.json"), {
        "report_id": REPORT_ID,
        "rule": "flux > 3 * band median (live, non-saturated only)",
        "anomalies": anomalies,
    })

    dump_json(out_path("ordered_flux_index.json"), {
        "report_id": REPORT_ID,
        "order": "calibrated_flux_ujy desc, obs_id asc",
        "index": ordered_index,
    })

    dump_json(out_path("dropped_observations.json"), {
        "report_id": REPORT_ID,
        "source": "adjudication_dossier.pdf",
        "dropped_obs_ids": sorted(dropped),
    })

    dump_json(out_path("provenance_manifest.json"), {
        "report_id": REPORT_ID,
        "scale_factor_source": "gain_scale_workbook.xlsx",
        "disputed_source": "adjudication_dossier.pdf",
        "raw_counts_source": "obs_capture_index.csv",
        "full_well_source": "full_well_capacity.tsv",
        "exposure_weight_source": "exposure_weight_micro.tsv",
        "attribution_method": "largest_remainder",
        "pipeline_order": ["clip", "dark", "nonlinearity", "gain", "scale",
                           "drift", "quantize"],
        "rounding": "half_even",
        "drift_operation": "subtract",
        "deadpixel_resolution": "least_fixed_point",
        "source_precedence": ["adjudication_dossier.pdf", "csv_quality_flag"],
        "total_reconciled_flux_ujy": total_after_closure,
    })

    dump_json(out_path("flux_attribution.json"), {
        "report_id": REPORT_ID,
        "pool_ujy": total_after_closure,
        "exposure_weight_micro": {i: weights[i] for i in sorted(weights)},
        "attributed_ujy": {i: attributed[i] for i in sorted(weights)},
        "remainder_recipients": remainder_recipients,
    })

    relays = []
    for pixel in sorted(masked):
        amount = relayed.get(pixel, 0)
        targets = edges.get(pixel, [])
        per_target = {}
        if targets:
            count = len(targets)
            share = amount // count
            leftover = amount - share * count
            for index, target in enumerate(targets):
                per_target[target] = share + (leftover if index == 0 else 0)
        relays.append({
            "pixel": pixel,
            "relayed_ujy": amount,
            "targets": targets,
            "per_target_ujy": per_target,
            "terminal_pixels": terminal_pixels(pixel, masked, edges),
        })
    dump_json(out_path("relay_audit.json"), {
        "report_id": REPORT_ID,
        "masked_pixel_count": len(masked),
        "relays": relays,
    })

    # ---- delimited rollups ------------------------------------------------- #
    write_lines(out_path("band_rollup.csv"),
                ["band,flux_ujy,observation_count"] +
                ["%s,%d,%d" % (b, band_flux.get(b, 0), band_count.get(b, 0))
                 for b in bands])
    write_lines(out_path("epoch_rollup.tsv"),
                ["epoch\tflux_ujy\tobservation_count"] +
                ["%s\t%d\t%d" % (e, epoch_flux.get(e, 0), epoch_count.get(e, 0))
                 for e in epochs])
    write_lines(out_path("instrument_rollup.psv"),
                ["instrument|flux_ujy|observation_count"] +
                ["%s|%d|%d" % (i, inst_flux.get(i, 0), inst_count.get(i, 0))
                 for i in instruments])

    # ---- xml / yaml / md / txt -------------------------------------------- #
    root = ET.Element("flagged_observations")
    for anomaly in anomalies:
        node = ET.SubElement(root, "observation")
        node.set("obs_id", anomaly["obs_id"])
        node.set("band", anomaly["band"])
        node.set("calibrated_flux_ujy", str(anomaly["calibrated_flux_ujy"]))
        node.set("band_median", str(anomaly["band_median"]))
    xml_bytes = ET.tostring(root, encoding="utf-8")
    with open(out_path("flagged_observations.xml"), "wb") as fh:
        fh.write(b'<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes + b"\n")

    write_lines(out_path("objective_summary.yaml"),
                render_yaml({
                    "report_id": REPORT_ID,
                    "total_reconciled_flux_ujy": total_after_closure,
                    "live_count": len(live),
                    "dropped_count": len(dropped),
                    "anomaly_count": len(anomalies),
                    "band_flux_ujy": {b: band_flux[b] for b in sorted(band_flux)},
                }))

    report_lines = [
        "# Detector array flux reconciliation report",
        "",
        "- report_id: %s" % REPORT_ID,
        "- observation_count: %d" % len(records),
        "- live_count: %d" % len(live),
        "- dropped_count: %d" % len(dropped),
        "- masked_pixel_count: %d" % len(masked),
        "- anomaly_count: %d" % len(anomalies),
        "- total_reconciled_flux_ujy: %d" % total_after_closure,
        "",
        "## Band flux (ujy)",
        "",
    ]
    for band in sorted(band_flux):
        report_lines.append("- %s: %d" % (band, band_flux[band]))
    report_lines += ["", "## Epoch flux (ujy)", ""]
    for epoch in sorted(epoch_flux):
        report_lines.append("- %s: %d" % (epoch, epoch_flux[epoch]))
    report_lines.append("")
    write_lines(out_path("reconciliation_report.md"), report_lines)

    write_lines(out_path("run_status.txt"), [
        "status: ok",
        "observations: %d" % len(records),
        "live: %d" % len(live),
        "dropped: %d" % len(dropped),
        "total_reconciled_flux_ujy: %d" % total_after_closure,
    ])

    # ---- settlement artifacts ---------------------------------------------- #
    dump_json(out_path("settlement_summary.json"), {
        "report_id": REPORT_ID,
        "settled_pool_ujy": settled_pool,
        "settlement_digest": digest,
        "settled_count": len(surviving),
        "rejected_count": len(rejects),
        "zero_exposure_count": len(zero_exposure),
        "near_saturated_count": len(near_saturated),
    })

    dump_json(out_path("settled_rates.json"), {
        "report_id": REPORT_ID,
        "rates": [{
            "obs_id": r["obs_id"],
            "instrument": r["instrument"],
            "band": r["band"],
            "exposure_ms": r["exposure_ms"],
            "calibrated_flux_ujy": r["calibrated_flux_ujy"],
            "rate_ujy_per_ks": r["rate_ujy_per_ks"],
        } for r in settled],
    })

    dump_json(out_path("zero_exposure.json"), {
        "report_id": REPORT_ID,
        "observations": zero_exposure,
    })

    dump_json(out_path("cosmic_ray_rejects.json"), {
        "report_id": REPORT_ID,
        "rejects": rejects,
    })

    dump_json(out_path("near_saturation.json"), {
        "report_id": REPORT_ID,
        "observations": [{
            "obs_id": r["obs_id"],
            "instrument": r["instrument"],
            "raw_counts": r["raw_counts"],
            "full_well_counts": r["full_well_counts"],
        } for r in near_saturated],
    })

    dump_json(out_path("settled_attribution.json"), {
        "report_id": REPORT_ID,
        "settled_pool_ujy": settled_pool,
        "attributed_ujy": {i: settled_attributed[i] for i in sorted(weights)},
    })

    write_lines(out_path("band_settlement.csv"),
                ["band,settled_count,settled_pool_ujy"] +
                ["%s,%d,%d" % (b, band_settled_count.get(b, 0),
                               band_settled_pool.get(b, 0)) for b in bands])

    dump_json(out_path("settlement_order.json"), {
        "report_id": REPORT_ID,
        "order": [{"position": i + 1,
                   "obs_id": r["obs_id"],
                   "rate_ujy_per_ks": r["rate_ujy_per_ks"]}
                  for i, r in enumerate(settlement_ranked)],
    })

    # ---- per-dimension families -------------------------------------------- #
    for inst in instruments:
        for band in bands:
            cell = [r for r in live
                    if r["instrument"] == inst and r["band"] == band]
            dump_json(out_path("cell_%s_%s.json" % (inst, band)), {
                "instrument": inst,
                "band": band,
                "observation_count": len(cell),
                "flux_ujy": sum(r["calibrated_flux_ujy"] for r in cell),
                "saturated_count": sum(1 for r in cell if r["saturated"]),
                "obs_ids": sorted(r["obs_id"] for r in cell),
            })

    for epoch in epochs:
        for band in bands:
            lines = ["instrument|flux_ujy|observation_count"]
            for inst in instruments:
                subset = [r for r in live if r["instrument"] == inst
                          and r["band"] == band and r["epoch"] == epoch]
                lines.append("%s|%d|%d" % (inst,
                                            sum(r["calibrated_flux_ujy"] for r in subset),
                                            len(subset)))
            write_lines(out_path("grid_%s_%s.psv" % (epoch, band)), lines)

    for inst in instruments:
        for epoch in epochs:
            lines = ["band\tflux_ujy\tobservation_count"]
            for band in bands:
                subset = [r for r in live if r["instrument"] == inst
                          and r["band"] == band and r["epoch"] == epoch]
                lines.append("%s\t%d\t%d" % (band,
                                             sum(r["calibrated_flux_ujy"] for r in subset),
                                             len(subset)))
            write_lines(out_path("span_%s_%s.tsv" % (inst, epoch)), lines)

    return {
        "observation_count": len(records),
        "live_count": len(live),
        "dropped_count": len(dropped),
        "total_reconciled_flux_ujy": total_after_closure,
        "conserved": total_after_closure == sum_live_flux,
    }


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir = os.path.abspath(argv[1])
    out_dir = os.path.abspath(argv[2])
    run(data_dir, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))