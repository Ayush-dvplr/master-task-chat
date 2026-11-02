#!/usr/bin/env python3
"""Detector flux reconciliation reference implementation.

Reads a reconciliation extract from DATA_DIR (flat files plus a load-bearing
xlsx scale workbook and a pdf adjudication dossier), applies the documented
correction pipeline in its correct application order: clips raw counts at the
per-instrument full well, subtracts dark current from the clipped counts,
resolves the temporal gain-label fold, subtracts thermal drift, quantizes with
banker's rounding, resolves the dead-pixel redistribution as a least fixed point
and audits it hop by hop, drops PDF-adjudicated disputed observations, keeps
saturated observations out of every band median, attributes the reconciled total
across the instruments by largest-remainder apportionment, and writes the
reconciled report set to OUT_DIR.

Standard library only. Reads only DATA_DIR and writes only OUT_DIR.

    python3 derive_report.py DATA_DIR OUT_DIR
"""
from __future__ import annotations

import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from typing import Any

BANDS = ("u", "g", "r", "i", "z")
INSTRUMENTS = ("G1", "G2", "G3", "G4")
EPOCHS = ("E1", "E2", "E3")


def read_delim(path: Path, delim: str) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=delim))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml_simple(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]

    def coerce(v: str) -> Any:
        v = v.strip()
        if v == "true":
            return True
        if v == "false":
            return False
        if re.fullmatch(r"-?\d+", v):
            return int(v)
        return v

    i = 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip():
            i += 1
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        content = raw.strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        if content.startswith("- "):
            item = content[2:].strip()
            if ":" in item:
                d: dict[str, Any] = {}
                k, _, val = item.partition(":")
                d[k.strip()] = coerce(val)
                parent.append(d)
                stack.append((indent, d))
            else:
                parent.append(coerce(item))
        elif content == "-":
            d = {}
            parent.append(d)
            stack.append((indent, d))
        else:
            key, _, val = content.partition(":")
            key = key.strip()
            if val.strip() == "":
                nxt_indent = None
                nxt_dash = False
                j = i + 1
                while j < len(lines):
                    if lines[j].strip():
                        nxt_indent = len(lines[j]) - len(lines[j].lstrip(" "))
                        nxt_dash = lines[j].strip().startswith("-")
                        break
                    j += 1
                child: Any = [] if (nxt_indent is not None and nxt_indent > indent and nxt_dash) else {}
                parent[key] = child
                stack.append((indent, child))
            else:
                parent[key] = coerce(val)
        i += 1
    return root


def read_xml_rows(path: Path, row_tag: str) -> list[dict[str, str]]:
    tree = ET.parse(str(path))
    return [dict(el.attrib) for el in tree.getroot() if el.tag.endswith(row_tag)]


def read_xlsx(path: Path) -> dict[str, list[list[Any]]]:
    M = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    lb, rb = chr(123), chr(125)

    def q(t: str) -> str:
        return lb + M + rb + t

    def col_idx(ref: str) -> int:
        letters = "".join(c for c in ref if c.isalpha())
        n = 0
        for c in letters:
            n = n * 26 + (ord(c) - 64)
        return n - 1

    z = zipfile.ZipFile(str(path))
    shared: list[str] = []
    if "xl/sharedStrings.xml" in z.namelist():
        sroot = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in sroot.findall(q("si")):
            shared.append("".join(t.text or "" for t in si.iter(q("t"))))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels_root = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    R = "http://schemas.openxmlformats.org/package/2006/relationships"
    rid_to_target = {rel.get("Id"): rel.get("Target") for rel in rels_root.findall(lb + R + rb + "Relationship")}
    RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    result: dict[str, list[list[Any]]] = {}
    for sheet in wb.find(q("sheets")).findall(q("sheet")):
        name = sheet.get("name")
        rid = sheet.get(lb + RNS + rb + "id")
        target = rid_to_target.get(rid, "")
        member = target if target.startswith("xl/") else "xl/" + target.lstrip("/")
        if member not in z.namelist():
            member = "xl/" + target
        ws = ET.fromstring(z.read(member))
        rows: list[list[Any]] = []
        data = ws.find(q("sheetData"))
        if data is not None:
            for row in data.findall(q("row")):
                cells: dict[int, Any] = {}
                for c in row.findall(q("c")):
                    ref = c.get("r") or "A1"
                    t = c.get("t") or "n"
                    if t == "s":
                        v = c.find(q("v"))
                        val = shared[int(v.text)] if v is not None else None
                    elif t == "inlineStr":
                        is_ = c.find(q("is"))
                        val = "".join(x.text or "" for x in is_.iter(q("t"))) if is_ is not None else None
                    else:
                        v = c.find(q("v"))
                        val = v.text if v is not None else None
                    cells[col_idx(ref)] = val
                maxc = max(cells) if cells else -1
                rows.append([cells.get(i) for i in range(maxc + 1)])
        result[name] = rows
    return result


def read_pdf_lines(path: Path) -> list[str]:
    text = path.read_bytes().decode("latin-1")
    stream_pat = "stream" + chr(13) + "?" + chr(10) + "(.*?)" + chr(13) + "?" + chr(10) + "endstream"
    show_pat = "[(]((?:[^()" + "\\" + "\\]|" + "\\" + "\\.)*)[)]" + "\\" + "s*Tj"
    out: list[str] = []
    for m in re.finditer(stream_pat, text, re.S):
        stream = m.group(1)
        for tm in re.finditer(show_pat, stream):
            s = tm.group(1)
            s = s.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
            out.append(s)
    return out


def half_even(v: Decimal) -> int:
    return int(v.quantize(Decimal("1"), ROUND_HALF_EVEN))


def horner(coeffs: list[int], x: int) -> int:
    """Evaluate the micro-scaled polynomial on exact integers, then scale back
    down once with banker's rounding (response_curve_horner.yaml)."""
    acc = 0
    for c in coeffs:
        acc = acc * x + c
    return half_even(Decimal(acc) / Decimal(1_000_000))


def median_half_even(values: list[int]) -> int:
    """rounding_primer.txt: every quantization in this contract uses banker's
    rounding, the band median included."""
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return half_even((Decimal(ordered[mid - 1]) + Decimal(ordered[mid])) / Decimal(2))


def epoch_of_mjd(mjd: int, windows: dict[str, tuple[int, int]]) -> str:
    for ep in EPOCHS:
        lo, hi = windows[ep]
        if lo <= mjd < hi:
            return ep
    return "UNKNOWN"


def load_contract(data: Path) -> dict[str, Any]:
    """Load every reference table from the corpus. The authoritative source of
    each table is named in file_role_index.md."""
    # observation stream: obs_capture_index.csv is authoritative for raw_counts
    obs_rows = read_delim(data / "obs_capture_index.csv", ",")
    obs = []
    for r in obs_rows:
        obs.append({
            "obs_id": r["obs_id"], "instrument": r["instrument"], "band": r["band"],
            "mjd": int(r["mjd"]), "gain_label": r["gain_label"],
            "raw_counts": int(r["raw_counts"]), "pixel": r["pixel"],
            "quality_flag": r["quality_flag"],
        })

    # epoch windows (half-open)
    ew = read_json(data / "epoch_window_bounds.json")["epochs"]
    windows = {e: (int(ew[e]["mjd_start"]), int(ew[e]["mjd_end"])) for e in ew}

    # full well: the clip ceiling, authoritative in its own table only
    full_well: dict[str, int] = {}
    for r in read_delim(data / "full_well_capacity.tsv", "\t"):
        full_well[r["instrument"]] = int(r["full_well_counts"])

    # exposure weight: the attribution ratio, authoritative in its own table only
    exposure_micro: dict[str, int] = {}
    for r in read_delim(data / "exposure_weight_micro.tsv", "\t"):
        exposure_micro[r["instrument"]] = int(r["weight_micro"])

    # dark current: authoritative per (instrument, band, epoch)
    dark: dict[tuple[str, str, str], int] = {}
    for r in read_delim(data / "pedestal_authoritative.csv", ","):
        dark[(r["instrument"], r["band"], r["epoch"])] = int(r["dark_current_counts"])

    # nonlinearity Horner coeffs
    nl = read_yaml_simple(data / "response_curve_horner.yaml")
    nonlin = {k: [int(x) for x in v] for k, v in nl["coefficients"].items()}

    # gain values per resolved channel (micro-e-per-count)
    gy = read_json(data / "quantum_yield_micro.json")
    gain_micro = {k: int(v) for k, v in gy["channels"].items()}

    # gain fold: written label + epoch -> resolved channel
    fold: dict[tuple[str, str], str] = {}
    for r in read_delim(data / "channel_lineage_fold.psv", "|"):
        fold[(r["written_label"], r["epoch"])] = r["resolved_channel"]

    # scale factor: XLSX ONLY (load-bearing xlsx-only value)
    sheets = read_xlsx(data / "gain_scale_workbook.xlsx")
    fs = sheets["scale_factor_authoritative"]
    header = fs[0]
    idx = {h: i for i, h in enumerate(header)}
    factor_micro: dict[str, int] = {}
    for row in fs[1:]:
        factor_micro[row[idx["instrument"]]] = int(row[idx["factor_micro"]])

    # drift ppm per (instrument, epoch)
    dt = read_yaml_simple(data / "thermal_drift_ppm.yml")
    drift: dict[tuple[str, str], int] = {}
    for r in dt["table"]:
        drift[(r["instrument"], r["epoch"])] = int(r["drift_ppm"])

    # dead-pixel relay graph
    masked: dict[str, list[str]] = {}
    for r in read_xml_rows(data / "occlusion_relay_graph.xml", "node"):
        if int(r["target_count"]) > 0:
            masked[r["pixel"]] = [t for t in r["targets"].split(";") if t]

    # disputed observations: PDF ONLY (authoritative source precedence)
    disputed: set[str] = set()
    for line in read_pdf_lines(data / "adjudication_dossier.pdf"):
        parts = line.split("|")
        if len(parts) >= 2 and parts[1] == "disputed":
            disputed.add(parts[0])

    # integration time and shutter state, authoritative in the ledger only
    exposure_ms: dict[str, int] = {}
    shutter_state: dict[str, str] = {}
    for r in read_delim(data / "exposure_ledger.csv", ","):
        exposure_ms[r["obs_id"]] = int(r["exposure_ms"])
        shutter_state[r["obs_id"]] = r["shutter_state"]

    return {
        "obs": obs, "windows": windows, "dark": dark, "nonlin": nonlin,
        "gain_micro": gain_micro, "fold": fold, "factor_micro": factor_micro,
        "drift": drift, "masked": masked, "disputed": disputed,
        "full_well": full_well, "exposure_micro": exposure_micro,
        "exposure_ms": exposure_ms, "shutter_state": shutter_state,
    }


def reconcile_one(o: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    instr, band, mjd = o["instrument"], o["band"], o["mjd"]
    epoch = epoch_of_mjd(mjd, ctx["windows"])
    ceiling = ctx["full_well"][instr]
    saturated = o["raw_counts"] > ceiling
    effective = ceiling if saturated else o["raw_counts"]
    net = effective - ctx["dark"][(instr, band, epoch)]
    lin = horner(ctx["nonlin"][instr], net)
    channel = ctx["fold"][(o["gain_label"], epoch)]
    g = Decimal(lin) * Decimal(ctx["gain_micro"][channel]) / Decimal(1_000_000)
    s = g * Decimal(ctx["factor_micro"][instr]) / Decimal(1_000_000)
    dppm = ctx["drift"][(instr, epoch)]
    drift_corr = half_even(s * Decimal(dppm) / Decimal(1_000_000))
    d = s - Decimal(drift_corr)
    flux = half_even(d)
    return {
        "epoch": epoch, "effective_counts": effective, "saturated": saturated,
        "net": net, "lin": lin, "channel": channel,
        "drift_ppm": dppm, "drift_correction": drift_corr,
        "calibrated_flux_ujy": flux,
    }


def split_to_targets(amount: int, targets: list[str]) -> dict[str, int]:
    """Even split with the leftover to the first target, so the parts always sum
    back to the amount relayed (relay_closure_rule.json)."""
    share, rem = divmod(amount, len(targets))
    return {t: share + (rem if i == 0 else 0) for i, t in enumerate(targets)}


def terminal_pixels(pixel: str, masked: dict[str, list[str]]) -> list[str]:
    """Unmasked pixels the flux finally reaches, following masked hops
    transitively rather than stopping at the first target."""
    seen: set[str] = set()
    terminals: set[str] = set()
    stack = list(masked.get(pixel, ()))
    while stack:
        px = stack.pop()
        if px in seen:
            continue
        seen.add(px)
        if px in masked:
            stack.extend(masked[px])
        else:
            terminals.add(px)
    return sorted(terminals)


def attribute_by_exposure(pool: int, weight_micro: dict[str, int]) -> dict[str, Any]:
    """Largest-remainder apportionment of the pool across the instruments.

    Shares are compared as exact integer remainders over the common denominator
    W, never as floats, so the four parts sum to the pool exactly.
    """
    total_weight = sum(weight_micro[i] for i in INSTRUMENTS)
    base: dict[str, int] = {}
    remainder: dict[str, int] = {}
    for instr in INSTRUMENTS:
        numerator = pool * weight_micro[instr]
        base[instr] = numerator // total_weight
        remainder[instr] = numerator - base[instr] * total_weight
    leftover = pool - sum(base.values())
    order = sorted(INSTRUMENTS, key=lambda i: (-remainder[i], i))
    recipients = order[:leftover]
    attributed = {i: base[i] + (1 if i in recipients else 0) for i in INSTRUMENTS}
    return {"attributed": dict(sorted(attributed.items())),
            "recipients": sorted(recipients)}


def fixpoint_redistribution(base_flux: dict[str, int], masked: dict[str, list[str]]) -> tuple[dict[str, int], dict[str, int]]:
    """Least fixed point of the redistribution, computed as a memoized inflow.

    A masked pixel hands on its FULLY accumulated flux (relay_closure_rule.json),
    so a pixel's value is its own base flux plus the share relayed to it by each
    masked pixel that targets it, and that share needs the source resolved
    first. The walk below resolves each pixel on demand and caches the result,
    carrying its own explicit stack rather than the interpreter's call stack, so
    a relay chain of ANY length reaches the fixed point; a recursive walk would
    instead abort on the interpreter's frame limit once a chain ran past roughly
    a thousand hops. The cycle guard keeps a malformed graph from looping.

    Returns the resolved flux per pixel and, beside it, the fully accumulated
    amount of every pixel, which is what the relay audit reports for a masked
    pixel and what the base flux alone would understate.
    """
    universe = set(base_flux) | set(masked)
    for targets in masked.values():
        universe.update(targets)

    sources_of: dict[str, list[str]] = {}
    for src in sorted(masked):
        for target in masked[src]:
            sources_of.setdefault(target, []).append(src)

    cache: dict[str, int] = {}
    in_progress: set[str] = set()

    def accumulated(px: str) -> int:
        if px in cache:
            return cache[px]
        stack: list[tuple[str, bool]] = [(px, False)]
        while stack:
            node, ready = stack.pop()
            if ready:
                total = base_flux.get(node, 0)
                for src in sources_of.get(node, ()):
                    total += split_to_targets(cache[src], masked[src])[node]
                in_progress.discard(node)
                cache[node] = total
                continue
            if node in cache:
                continue
            if node in in_progress:
                raise ValueError(f"relay graph contains a cycle through {node}")
            in_progress.add(node)
            stack.append((node, True))
            for src in sources_of.get(node, ()):
                if src not in cache:
                    stack.append((src, False))
        return cache[px]

    resolved = {px: 0 if px in masked else accumulated(px) for px in sorted(universe)}
    return resolved, {px: accumulated(px) for px in sorted(universe)}


PHOTOMETRIC_BANDS = ("u", "g", "r", "i", "z")
SETTLEMENT_MODULUS = 1_000_003
COSMIC_RAY_SIGMA = 6
MIN_REJECTION_SAMPLE = 4
NEAR_SATURATION_PERCENT = 98


def median_lower(values: list[int]) -> int:
    """Contract S3: the settlement layer takes the LOWER of the two middle
    values of an even sample, never their mean. This is deliberately not
    median_half_even, which the reconciliation layer above keeps using."""
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return ordered[mid - 1]


def band_rank(band: str) -> int:
    """Contract S4: photometric order, so a settlement ordering never falls back
    on the alphabetical order of the band letters."""
    return PHOTOMETRIC_BANDS.index(band)


def settle(result: dict[str, Any]) -> dict[str, Any]:
    """Contract sections S1 to S8. Runs on top of the reconciliation layer and
    revises nothing in it."""
    ctx = result["ctx"]
    exposure = ctx["exposure_ms"]
    shutter = ctx["shutter_state"]
    full_well = ctx["full_well"]

    # S8: near saturation is an integer test against 98 percent of the ceiling,
    # and a saturated reading is already above the ceiling so it is not near it.
    near_saturated = []
    for row in result["live"]:
        ceiling = full_well[row["instrument"]]
        if row["saturated"]:
            continue
        if row["raw_counts"] * 100 >= ceiling * NEAR_SATURATION_PERCENT:
            near_saturated.append({"obs_id": row["obs_id"],
                                   "instrument": row["instrument"],
                                   "raw_counts": row["raw_counts"],
                                   "full_well_counts": ceiling})
    near_saturated.sort(key=lambda e: e["obs_id"])
    near_ids = {e["obs_id"] for e in near_saturated}

    # S1: floor division, the one stage in the contract that is not banker's
    # rounding. An aborted shutter measured nothing, so it is held out entirely.
    settled_rows = []
    zero_exposure = []
    for row in sorted(result["live"], key=lambda r: r["obs_id"]):
        ms = exposure[row["obs_id"]]
        if ms == 0:
            zero_exposure.append({"obs_id": row["obs_id"],
                                  "shutter_state": shutter[row["obs_id"]]})
            continue
        rate = (row["calibrated_flux_ujy"] * 1_000_000) // ms
        settled_rows.append({"obs_id": row["obs_id"], "instrument": row["instrument"],
                             "band": row["band"], "exposure_ms": ms,
                             "calibrated_flux_ujy": row["calibrated_flux_ujy"],
                             "rate_ujy_per_ks": rate})

    # S2: median absolute deviation, used unscaled, with both exemptions.
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in settled_rows:
        groups.setdefault((row["instrument"], row["band"]), []).append(row)
    rejects = []
    for key in sorted(groups):
        members = groups[key]
        if len(members) < MIN_REJECTION_SAMPLE:
            continue
        rates = [m["rate_ujy_per_ks"] for m in members]
        med = median_lower(rates)
        mad = median_lower([abs(v - med) for v in rates])
        threshold = med + COSMIC_RAY_SIGMA * mad
        for member in members:
            if member["obs_id"] in near_ids:
                continue
            if member["rate_ujy_per_ks"] > threshold:
                rejects.append({"obs_id": member["obs_id"],
                                "instrument": member["instrument"],
                                "band": member["band"],
                                "rate_ujy_per_ks": member["rate_ujy_per_ks"],
                                "group_median": med, "group_mad": mad,
                                "threshold": threshold})
    rejects.sort(key=lambda e: e["obs_id"])
    rejected_ids = {e["obs_id"] for e in rejects}

    surviving = [r for r in settled_rows if r["obs_id"] not in rejected_ids]

    settled_pool = sum(r["rate_ujy_per_ks"] for r in surviving)

    # S7: rate descending, then photometric band, then obs_id ascending.
    ranked = sorted(surviving, key=lambda r: (-r["rate_ujy_per_ks"],
                                              band_rank(r["band"]), r["obs_id"]))
    order = [{"position": i + 1, "obs_id": r["obs_id"],
              "rate_ujy_per_ks": r["rate_ujy_per_ks"]}
             for i, r in enumerate(ranked)]
    digest = sum(e["position"] * e["rate_ujy_per_ks"] for e in order) % SETTLEMENT_MODULUS

    # S6: the same largest-remainder method, applied to the settled pool.
    settled_attribution = attribute_by_exposure(settled_pool, ctx["exposure_micro"])

    band_rows = []
    for band in PHOTOMETRIC_BANDS:
        members = [r for r in surviving if r["band"] == band]
        band_rows.append([band, len(members),
                          sum(r["rate_ujy_per_ks"] for r in members)])

    return {
        "settled_rows": settled_rows, "zero_exposure": zero_exposure,
        "rejects": rejects, "near_saturated": near_saturated,
        "surviving": surviving, "settled_pool": settled_pool,
        "order": order, "digest": digest,
        "settled_attribution": settled_attribution, "band_rows": band_rows,
    }


def derive(data_dir: str | Path) -> dict[str, Any]:
    data = Path(data_dir)
    ctx = load_contract(data)
    obs = ctx["obs"]
    masked = ctx["masked"]
    disputed = ctx["disputed"]

    per_obs = []
    for o in obs:
        r = reconcile_one(o, ctx)
        row = dict(o)
        row.update(r)
        row["disputed"] = o["obs_id"] in disputed
        row["masked"] = o["pixel"] in masked
        per_obs.append(row)

    live = [r for r in per_obs if not r["disputed"]]
    dropped = sorted(r["obs_id"] for r in per_obs if r["disputed"])

    base_flux: dict[str, int] = {}
    for r in live:
        base_flux[r["pixel"]] = base_flux.get(r["pixel"], 0) + r["calibrated_flux_ujy"]
    resolved_pixel, accumulated_pixel = fixpoint_redistribution(base_flux, masked)
    total_flux = sum(resolved_pixel.values())

    relays = []
    for px in sorted(masked):
        targets = sorted(masked[px])
        relayed = accumulated_pixel[px]
        relays.append({"pixel": px, "relayed_ujy": relayed, "targets": targets,
                       "per_target_ujy": dict(sorted(split_to_targets(relayed, targets).items())),
                       "terminal_pixels": terminal_pixels(px, masked)})

    attribution = attribute_by_exposure(total_flux, ctx["exposure_micro"])

    def agg(keyfn):
        flux: dict[str, int] = {}
        cnt: dict[str, int] = {}
        for r in live:
            k = keyfn(r)
            flux[k] = flux.get(k, 0) + r["calibrated_flux_ujy"]
            cnt[k] = cnt.get(k, 0) + 1
        return flux, cnt

    band_flux, band_cnt = agg(lambda r: r["band"])
    epoch_flux, epoch_cnt = agg(lambda r: r["epoch"])
    instr_flux, instr_cnt = agg(lambda r: r["instrument"])

    channel_use: dict[str, int] = {}
    for r in live:
        channel_use[r["channel"]] = channel_use.get(r["channel"], 0) + 1

    eligible = [r for r in live if not r["saturated"]]
    band_median: dict[str, int] = {}
    band_values: dict[str, list[int]] = {}
    for r in eligible:
        band_values.setdefault(r["band"], []).append(r["calibrated_flux_ujy"])
    for b, vals in band_values.items():
        band_median[b] = median_half_even(vals)
    anomalies = []
    for r in sorted(eligible, key=lambda x: x["obs_id"]):
        if r["band"] not in band_median:
            continue
        thr = 3 * band_median[r["band"]]
        if r["calibrated_flux_ujy"] > thr:
            anomalies.append({"obs_id": r["obs_id"], "band": r["band"],
                              "calibrated_flux_ujy": r["calibrated_flux_ujy"],
                              "band_median": band_median[r["band"]]})

    ordered = sorted(live, key=lambda r: (-r["calibrated_flux_ujy"], r["obs_id"]))
    ordered_index = [{"rank": i + 1, "obs_id": r["obs_id"],
                      "calibrated_flux_ujy": r["calibrated_flux_ujy"]}
                     for i, r in enumerate(ordered)]

    result = {
        "ctx": ctx, "per_obs": per_obs, "live": live, "dropped": dropped,
        "masked": masked, "disputed": sorted(disputed),
        "base_flux": base_flux, "resolved_pixel": resolved_pixel,
        "total_flux": total_flux, "relays": relays, "attribution": attribution,
        "saturated": sorted(r["obs_id"] for r in live if r["saturated"]),
        "band_flux": band_flux, "band_cnt": band_cnt,
        "epoch_flux": epoch_flux, "epoch_cnt": epoch_cnt,
        "instr_flux": instr_flux, "instr_cnt": instr_cnt,
        "channel_use": channel_use, "band_median": band_median,
        "anomalies": anomalies, "ordered_index": ordered_index,
    }
    result["settlement"] = settle(result)
    return result


def _wjson(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _wtext(path: Path, text: str) -> None:
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def _wdelim(path: Path, header: list[str], rows: list[list[Any]], delim: str) -> None:
    import io
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delim, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    path.write_text(buf.getvalue(), encoding="utf-8")


def _xesc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _wyaml(path: Path, obj: dict[str, Any]) -> None:
    lines: list[str] = []

    def scalar(v: Any) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v)

    def emit(o: Any, indent: int) -> None:
        pad = "  " * indent
        if isinstance(o, dict):
            for k in sorted(o):
                v = o[k]
                if isinstance(v, (dict, list)):
                    lines.append(f"{pad}{k}:")
                    emit(v, indent + 1)
                else:
                    lines.append(f"{pad}{k}: {scalar(v)}")
        elif isinstance(o, list):
            for v in o:
                if isinstance(v, (dict, list)):
                    lines.append(f"{pad}-")
                    emit(v, indent + 1)
                else:
                    lines.append(f"{pad}- {scalar(v)}")

    emit(obj, 0)
    _wtext(path, "\n".join(lines))


def write_artifacts(data_dir: str | Path, out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    d = derive(data_dir)
    ctx = d["ctx"]

    report_id = "detector-flux-reconciliation"

    summary = {
        "report_id": report_id,
        "observation_count": len(d["per_obs"]),
        "live_count": len(d["live"]),
        "dropped_count": len(d["dropped"]),
        "total_reconciled_flux_ujy": d["total_flux"],
        "band_flux_ujy": dict(sorted(d["band_flux"].items())),
        "epoch_flux_ujy": dict(sorted(d["epoch_flux"].items())),
        "instrument_flux_ujy": dict(sorted(d["instr_flux"].items())),
        "channel_usage": dict(sorted(d["channel_use"].items())),
        "band_median_ujy": dict(sorted(d["band_median"].items())),
    }
    _wjson(out / "summary.json", summary)

    reconciled = {
        "report_id": report_id,
        "observations": [
            {"obs_id": r["obs_id"], "instrument": r["instrument"], "band": r["band"],
             "epoch": r["epoch"], "resolved_channel": r["channel"],
             "effective_counts": r["effective_counts"], "saturated": r["saturated"],
             "net_counts": r["net"], "linearized": r["lin"],
             "drift_ppm": r["drift_ppm"], "drift_correction": r["drift_correction"],
             "calibrated_flux_ujy": r["calibrated_flux_ujy"]}
            for r in sorted(d["live"], key=lambda x: x["obs_id"])
        ],
    }
    _wjson(out / "reconciled_flux.json", reconciled)

    calibration_audit = {
        "report_id": report_id,
        "scale_factor_micro": dict(sorted(ctx["factor_micro"].items())),
        "gain_micro_e_per_count": dict(sorted(ctx["gain_micro"].items())),
        "drift_ppm": {f"{i}:{e}": v for (i, e), v in sorted(ctx["drift"].items())},
        "nonlinearity_coeffs": {k: ctx["nonlin"][k] for k in sorted(ctx["nonlin"])},
        "epoch_windows": {e: list(ctx["windows"][e]) for e in sorted(ctx["windows"])},
        "fold_applied": sorted({f"{w}:{e}->{c}" for (w, e), c in ctx["fold"].items() if w != c}),
    }
    _wjson(out / "calibration_audit.json", calibration_audit)

    data_quality = {
        "report_id": report_id,
        "input_file_count": len([p for p in Path(data_dir).iterdir() if p.is_file()]),
        "observation_count": len(d["per_obs"]),
        "disputed_count": len(d["dropped"]),
        "masked_pixel_count": len(d["masked"]),
        "distinct_pixels": len(d["resolved_pixel"]),
        "suspect_but_not_disputed": sorted(
            r["obs_id"] for r in d["per_obs"]
            if r["quality_flag"] == "suspect" and not r["disputed"]),
        "saturated_count": len(d["saturated"]),
        "saturated_obs_ids": d["saturated"],
    }
    _wjson(out / "data_quality.json", data_quality)

    for instr in INSTRUMENTS:
        rows = [r for r in d["live"] if r["instrument"] == instr]
        bucket = {
            "instrument": instr,
            "observation_count": len(rows),
            "flux_ujy": sum(r["calibrated_flux_ujy"] for r in rows),
            "band_flux_ujy": {},
            "epoch_flux_ujy": {},
        }
        for r in rows:
            bucket["band_flux_ujy"][r["band"]] = bucket["band_flux_ujy"].get(r["band"], 0) + r["calibrated_flux_ujy"]
            bucket["epoch_flux_ujy"][r["epoch"]] = bucket["epoch_flux_ujy"].get(r["epoch"], 0) + r["calibrated_flux_ujy"]
        bucket["band_flux_ujy"] = dict(sorted(bucket["band_flux_ujy"].items()))
        bucket["epoch_flux_ujy"] = dict(sorted(bucket["epoch_flux_ujy"].items()))
        _wjson(out / f"instrument_{instr}.json", bucket)

    epoch_totals = {
        "report_id": report_id,
        "epoch_flux_ujy": dict(sorted(d["epoch_flux"].items())),
        "epoch_observation_count": dict(sorted(d["epoch_cnt"].items())),
    }
    _wjson(out / "epoch_totals.json", epoch_totals)

    deadpixel_closure = {
        "report_id": report_id,
        "masked_pixel_count": len(d["masked"]),
        "resolved_pixel_flux_ujy": dict(sorted(d["resolved_pixel"].items())),
        "total_after_closure_ujy": d["total_flux"],
    }
    _wjson(out / "deadpixel_closure.json", deadpixel_closure)

    _wdelim(out / "band_rollup.csv", ["band", "flux_ujy", "observation_count"],
            [[b, d["band_flux"].get(b, 0), d["band_cnt"].get(b, 0)] for b in BANDS], ",")
    _wdelim(out / "epoch_rollup.tsv", ["epoch", "flux_ujy", "observation_count"],
            [[e, d["epoch_flux"].get(e, 0), d["epoch_cnt"].get(e, 0)] for e in EPOCHS], "\t")
    _wdelim(out / "instrument_rollup.psv", ["instrument", "flux_ujy", "observation_count"],
            [[i, d["instr_flux"].get(i, 0), d["instr_cnt"].get(i, 0)] for i in INSTRUMENTS], "|")

    # Per-dimension rollups, sections D1 to D3 of report_schema.md. Each family
    # carries its own serialisation and its own row order, and every cell counts
    # only live observations, so a dropped observation reaches none of them.
    live_sorted = sorted(d["live"], key=lambda x: x["obs_id"])

    def _cell_rows(instr: str, band: str, epoch: str | None = None) -> list[dict[str, Any]]:
        return [r for r in live_sorted
                if r["instrument"] == instr and r["band"] == band
                and (epoch is None or r["epoch"] == epoch)]

    # D1: one JSON object per instrument and band, 20 files.
    for instr in INSTRUMENTS:
        for band in PHOTOMETRIC_BANDS:
            rows = _cell_rows(instr, band)
            _wjson(out / f"cell_{instr}_{band}.json", {
                "instrument": instr,
                "band": band,
                "observation_count": len(rows),
                "flux_ujy": sum(r["calibrated_flux_ujy"] for r in rows),
                "saturated_count": sum(1 for r in rows if r["saturated"]),
                "obs_ids": [r["obs_id"] for r in rows],
            })

    # D2: one pipe-delimited table per epoch and band, 15 files, rows in
    # instrument order G1 to G4.
    for epoch in EPOCHS:
        for band in PHOTOMETRIC_BANDS:
            _wdelim(out / f"grid_{epoch}_{band}.psv",
                    ["instrument", "flux_ujy", "observation_count"],
                    [[instr,
                      sum(r["calibrated_flux_ujy"] for r in _cell_rows(instr, band, epoch)),
                      len(_cell_rows(instr, band, epoch))]
                     for instr in INSTRUMENTS], "|")

    # D3: one tab-delimited table per instrument and epoch, 12 files, rows in
    # the photometric band order u, g, r, i, z.
    for instr in INSTRUMENTS:
        for epoch in EPOCHS:
            _wdelim(out / f"span_{instr}_{epoch}.tsv",
                    ["band", "flux_ujy", "observation_count"],
                    [[band,
                      sum(r["calibrated_flux_ujy"] for r in _cell_rows(instr, band, epoch)),
                      len(_cell_rows(instr, band, epoch))]
                     for band in PHOTOMETRIC_BANDS], "\t")

    flagged_rows = "".join(
        f'  <observation obs_id="{_xesc(a["obs_id"])}" band="{_xesc(a["band"])}" '
        f'calibrated_flux_ujy="{a["calibrated_flux_ujy"]}" band_median="{a["band_median"]}"/>\n'
        for a in d["anomalies"])
    _wtext(out / "flagged_observations.xml",
           '<?xml version="1.0" encoding="UTF-8"?>\n<flagged_observations>\n'
           + flagged_rows + "</flagged_observations>")

    _wyaml(out / "objective_summary.yaml", {
        "report_id": report_id,
        "total_reconciled_flux_ujy": d["total_flux"],
        "live_count": len(d["live"]),
        "dropped_count": len(d["dropped"]),
        "anomaly_count": len(d["anomalies"]),
        "band_flux_ujy": dict(sorted(d["band_flux"].items())),
    })

    md = ["# Reconciliation Report", "",
          f"- report_id: {report_id}",
          f"- observations: {len(d['per_obs'])}",
          f"- live (non-dropped): {len(d['live'])}",
          f"- dropped (disputed): {len(d['dropped'])}",
          f"- total reconciled flux (uJy): {d['total_flux']}",
          f"- masked pixels: {len(d['masked'])}",
          f"- anomalies: {len(d['anomalies'])}", "",
          "## Band flux (uJy)", ""]
    for b in BANDS:
        md.append(f"- {b}: {d['band_flux'].get(b, 0)}")
    md += ["", "## Epoch flux (uJy)", ""]
    for e in EPOCHS:
        md.append(f"- {e}: {d['epoch_flux'].get(e, 0)}")
    _wtext(out / "reconciliation_report.md", "\n".join(md))

    _wtext(out / "run_status.txt",
           "status: ok\n"
           f"observations: {len(d['per_obs'])}\n"
           f"live: {len(d['live'])}\n"
           f"dropped: {len(d['dropped'])}\n"
           f"total_reconciled_flux_ujy: {d['total_flux']}\n")

    provenance = {
        "report_id": report_id,
        "scale_factor_source": "gain_scale_workbook.xlsx",
        "disputed_source": "adjudication_dossier.pdf",
        "raw_counts_source": "obs_capture_index.csv",
        "full_well_source": "full_well_capacity.tsv",
        "exposure_weight_source": "exposure_weight_micro.tsv",
        "attribution_method": "largest_remainder",
        "pipeline_order": ["clip", "dark", "nonlinearity", "gain", "scale", "drift", "quantize"],
        "rounding": "half_even",
        "drift_operation": "subtract",
        "deadpixel_resolution": "least_fixed_point",
        "source_precedence": ["adjudication_dossier.pdf", "csv_quality_flag"],
        "total_reconciled_flux_ujy": d["total_flux"],
    }
    _wjson(out / "provenance_manifest.json", provenance)

    _wjson(out / "anomaly_ledger.json",
           {"report_id": report_id,
            "rule": "flux > 3 * band median (live, non-saturated only)",
            "anomalies": d["anomalies"]})

    _wjson(out / "flux_attribution.json", {
        "report_id": report_id,
        "pool_ujy": d["total_flux"],
        "exposure_weight_micro": dict(sorted(ctx["exposure_micro"].items())),
        "attributed_ujy": d["attribution"]["attributed"],
        "remainder_recipients": d["attribution"]["recipients"],
    })

    _wjson(out / "relay_audit.json", {
        "report_id": report_id,
        "masked_pixel_count": len(d["masked"]),
        "relays": d["relays"],
    })

    _wjson(out / "ordered_flux_index.json",
           {"report_id": report_id, "order": "calibrated_flux_ujy desc, obs_id asc",
            "index": d["ordered_index"]})

    _wjson(out / "dropped_observations.json",
           {"report_id": report_id, "source": "adjudication_dossier.pdf",
            "dropped_obs_ids": d["dropped"]})

    s = d["settlement"]

    _wjson(out / "settlement_summary.json", {
        "report_id": report_id,
        "settled_pool_ujy": s["settled_pool"],
        "settlement_digest": s["digest"],
        "settled_count": len(s["surviving"]),
        "rejected_count": len(s["rejects"]),
        "zero_exposure_count": len(s["zero_exposure"]),
        "near_saturated_count": len(s["near_saturated"]),
    })

    _wjson(out / "settled_rates.json",
           {"report_id": report_id, "rates": s["settled_rows"]})

    _wjson(out / "zero_exposure.json",
           {"report_id": report_id, "observations": s["zero_exposure"]})

    _wjson(out / "cosmic_ray_rejects.json",
           {"report_id": report_id, "rejects": s["rejects"]})

    _wjson(out / "near_saturation.json",
           {"report_id": report_id, "observations": s["near_saturated"]})

    _wjson(out / "settled_attribution.json", {
        "report_id": report_id,
        "settled_pool_ujy": s["settled_pool"],
        "attributed_ujy": s["settled_attribution"]["attributed"],
    })

    _wdelim(out / "band_settlement.csv",
            ["band", "settled_count", "settled_pool_ujy"], s["band_rows"], ",")

    _wjson(out / "settlement_order.json",
           {"report_id": report_id, "order": s["order"]})


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: derive_report.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    write_artifacts(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
