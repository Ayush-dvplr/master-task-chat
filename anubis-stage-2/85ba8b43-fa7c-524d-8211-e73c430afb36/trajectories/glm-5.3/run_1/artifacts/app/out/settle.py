#!/usr/bin/env python3
"""Quarterly arena-ladder season settlement (stages S1..S9).

Usage: python3 settle.py DATA_DIR OUT_DIR

Reads the complete written contract and corpus from DATA_DIR and writes the
twenty-nine settlement artifacts into OUT_DIR. Standard library only.
"""

import csv
import datetime
import hashlib
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_EVEN
from fractions import Fraction

# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------

NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_DOC = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
NS_ODR = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

STREAM_RE = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.S)
TJ_RE = re.compile(rb"\(((?:\\.|[^\\()])*)\)\s*Tj")
NUM_RE = r"([0-9]*\.?[0-9]+)"


def rhe(num, den):
    """Exact round-half-even of the rational num/den to an integer."""
    if den == 0:
        return 0
    sign = -1 if (num < 0) != (den < 0) else 1
    n, d = abs(num), abs(den)
    q, r = divmod(n, d)
    if 2 * r > d or (2 * r == d and q % 2 == 1):
        q += 1
    return sign * q


def fmt_units(units, dp):
    """Format an integer scaled by 10**-dp as a fixed-point decimal string."""
    sign = "-" if units < 0 else ""
    ip, fp = divmod(abs(units), 10 ** dp)
    return "%s%d.%0*d" % (sign, ip, dp, fp)


def fmt_frac(fr, dp):
    return fmt_units(rhe(fr.numerator * 10 ** dp, fr.denominator), dp)


def fmt_float(x, dp):
    d = Decimal(repr(float(x))).quantize(Decimal(1).scaleb(-dp),
                                          rounding=ROUND_HALF_EVEN)
    if d == 0:
        d = abs(d)
    return format(d, "f")


def read_delimited(path, delim):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=delim))


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def parse_date(s):
    return datetime.date.fromisoformat(s.strip())


# ---------------------------------------------------------------------------
# binary input readers
# ---------------------------------------------------------------------------


def _cell_text(cell, shared):
    t = cell.get("t")
    if t == "inlineStr":
        return "".join(e.text or "" for e in cell.iter(NS_MAIN + "t"))
    if t == "s":
        v = "".join(e.text or "" for e in cell.iter(NS_MAIN + "v"))
        try:
            return shared[int(v)]
        except (ValueError, IndexError):
            return ""
    return "".join(e.text or "" for e in cell.iter(NS_MAIN + "v"))


def _sheet_cells(zf, member, shared):
    root = ET.fromstring(zf.read(member))
    cells = {}
    for row in root.iter(NS_MAIN + "row"):
        r = int(row.get("r"))
        for cell in row:
            col = re.match(r"([A-Z]+)", cell.get("r")).group(1)
            cells[(r, col)] = _cell_text(cell, shared)
    return cells


def read_workbook(path, wanted_tag):
    """Return the {cell: text} map of the sheet whose B1 equals wanted_tag."""
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            sroot = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sroot.iter(NS_MAIN + "si"):
                shared.append("".join(t.text or "" for t in si.iter(NS_MAIN + "t")))
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        target = {rel.get("Id"): rel.get("Target") for rel in rels}
        for sheet in wb.iter(NS_MAIN + "sheet"):
            member = target.get(sheet.get(NS_ODR + "id"), "")
            if not member.startswith("xl/"):
                member = "xl/" + member.lstrip("/")
            cells = _sheet_cells(zf, member, shared)
            if cells.get((1, "B"), "").strip() == wanted_tag:
                return cells
    raise SystemExit("no workbook sheet tagged %r" % wanted_tag)


def read_pdf_text(path):
    raw = open(path, "rb").read()
    lines = []
    for m in STREAM_RE.finditer(raw):
        body = m.group(1)
        try:
            body = zlib.decompress(body)
        except zlib.error:
            pass
        for t in TJ_RE.finditer(body):
            s = t.group(1)
            s = s.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
            lines.append(s.decode("latin-1"))
    return "\n".join(lines)


def read_docx_text(path):
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    paras = []
    for p in root.iter(NS_DOC + "p"):
        paras.append("".join(t.text or "" for t in p.iter(NS_DOC + "t")))
    return "\n".join(paras)


def first_number(patterns, text, cast=Fraction, what="constant"):
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return cast(m.group(1))
    raise SystemExit("could not locate %s in document" % what)


# ---------------------------------------------------------------------------
# stage S1 / S2: canonical rows, anchors, verdicts
# ---------------------------------------------------------------------------


def build_population(data_dir, cfg):
    capture = read_delimited(os.path.join(data_dir, "ladder_match_capture_s1.csv"), ",")
    tiers = {}
    for row in read_delimited(os.path.join(data_dir, "account_tier_crosswalk.csv"), ","):
        tiers[row["account_id"]] = row
    draw_reg = {}
    for row in read_delimited(os.path.join(data_dir, "cohort_draw_register.psv"), "|"):
        draw_reg[row["match_key"]] = row

    key_fields = cfg["match_key_fields"]
    groups = defaultdict(list)
    for row in capture:
        groups["|".join(row[f] for f in key_fields)].append(row)

    matches = {}
    for key, rows in groups.items():
        sealed = [r for r in rows if r["seal_status"] == cfg["seal_code"]]
        if not sealed:
            continue  # a key that never sealed is dropped from the population
        canonical = max(sealed, key=lambda r: int(r["checkpoint_no"]))
        first = min(rows, key=lambda r: int(r["checkpoint_no"]))
        acct = canonical["account_id"]
        reg = draw_reg.get(key, {})
        stratum = reg.get("stratum_frozen") or "%s-%s" % (
            tiers[acct]["frozen_tier"], tiers[acct]["frozen_server"])
        matches[key] = {
            "match_key": key,
            "account_id": acct,
            "stratum": stratum,
            "drawn": 1 if str(reg.get("drawn", "0")).strip() == "1" else 0,
            "loot_currency": canonical["loot_currency"],
            "anchor_date": first["match_epoch"],
            "raw_loot": canonical["raw_loot"],
            "p_raw": first["p_raw"],
        }
    return matches


def resolve_verdicts(matches, data_dir, cfg):
    history = defaultdict(list)
    for row in read_delimited(os.path.join(data_dir, "verdict_amendment_history.tsv"), "\t"):
        history[row["match_key"]].append(row)
    window = datetime.timedelta(days=cfg["window_days"])
    for key, m in matches.items():
        anchor = parse_date(m["anchor_date"])
        in_window = [r for r in history.get(key, [])
                     if anchor <= parse_date(r["effective_at"]) <= anchor + window]
        if not in_window:
            m["verdict"] = "excluded"
            continue
        last = sorted(in_window, key=lambda r: int(r["review_seq"]))[-1]
        m["verdict"] = cfg["crosswalk"].get(last["verdict"], "excluded")
    return {k: v for k, v in matches.items() if v["verdict"] in ("positive", "negative")}


# ---------------------------------------------------------------------------
# stage S3: running ladder baseline
# ---------------------------------------------------------------------------


def running_baseline(resolved, cfg):
    p_eff = {}
    for stratum in cfg["strata"]:
        baseline = cfg["base_p"]
        for key in sorted(k for k, v in resolved.items() if v["stratum"] == stratum):
            p_raw = Fraction(resolved[key]["p_raw"])
            lo, hi = cfg["p_raw_bounds"]
            p_raw = max(lo, min(hi, p_raw))
            value = cfg["baseline_w_raw"] * p_raw + cfg["baseline_w_prev"] * baseline
            value = max(Fraction(0), min(Fraction(1), value))
            p_eff[key] = value
            baseline = value
    return p_eff


# ---------------------------------------------------------------------------
# stage S4: reward-unit canonicalization
# ---------------------------------------------------------------------------


def ledger_units(matches, data_dir, cfg):
    drift = defaultdict(list)
    for row in read_delimited(os.path.join(data_dir, "season_patch_reference.csv"), ","):
        drift[row["unit_family"]].append((row["ref_date"], Fraction(row["drift_mult"])))
    for fam in drift:
        drift[fam].sort()
    units = {}
    for key, m in matches.items():
        fam = m["loot_currency"]
        eligible = [v for d, v in drift.get(fam, []) if d <= m["anchor_date"]]
        if not eligible:
            raise SystemExit("no drift reference for %s on/before %s" % (fam, m["anchor_date"]))
        scaled = Fraction(m["raw_loot"])
        if fam == cfg["ore_family"]:
            scaled = scaled * cfg["ore_gain"]
        else:
            scaled = scaled * Fraction(10) ** cfg["scale_exponents"][fam]
        scaled = scaled * eligible[-1]
        units[key] = rhe(scaled.numerator, scaled.denominator)
    return units


# ---------------------------------------------------------------------------
# stage S5: two-level rarity weights
# ---------------------------------------------------------------------------


def two_level_weights(matches, resolved, cfg):
    pop_by_stratum = defaultdict(int)
    sampled_by_stratum = defaultdict(int)
    sampled_by_server = defaultdict(int)
    resolved_by_server = defaultdict(int)
    for m in matches.values():
        pop_by_stratum[m["stratum"]] += 1
        if m["drawn"]:
            # the sampled frame: every drawn match, resolved or not
            sampled_by_stratum[m["stratum"]] += 1
            sampled_by_server[cfg["server_of"](m["stratum"])] += 1
    for m in resolved.values():
        resolved_by_server[cfg["server_of"](m["stratum"])] += 1

    weighted_keys = sorted(k for k, m in resolved.items() if m["drawn"])
    exact = {}
    for key in weighted_keys:
        st = resolved[key]["stratum"]
        srv = cfg["server_of"](st)
        base = Fraction(pop_by_stratum[st], sampled_by_stratum[st])
        nonresp = Fraction(sampled_by_server[srv], resolved_by_server[srv])
        exact[key] = base * nonresp

    dp = cfg["quantize_decimals"]
    scale = 10 ** dp
    quant = {}
    for stratum in cfg["strata"]:
        keys = [k for k in weighted_keys if resolved[k]["stratum"] == stratum]
        if not keys:
            continue
        total = sum((exact[k] for k in keys), Fraction(0))
        target = rhe(total.numerator * scale, total.denominator)
        cells = {k: rhe(exact[k].numerator * scale, exact[k].denominator) for k in keys}
        residue = target - sum(cells.values())
        if residue:
            top = sorted(keys, key=lambda k: (-cells[k], k))[0]
            cells[top] += residue
        quant.update(cells)

    weights = {}
    for key in weighted_keys:
        weights[key] = {
            "stratum": resolved[key]["stratum"],
            "y": 1 if resolved[key]["verdict"] == "positive" else 0,
            "weight_units": quant[key],
        }
    return weights, pop_by_stratum, sampled_by_stratum


# ---------------------------------------------------------------------------
# stage S6: calibration and decision
# ---------------------------------------------------------------------------


def logit(p):
    return math.log(p / (1.0 - p))


def sigmoid(z):
    return 1.0 / (1.0 + math.exp(-z))


def calibrate(resolved, p_eff, cfg):
    p_cal = {}
    yhat = {}
    for key in resolved:
        st = resolved[key]["stratum"]
        p = sigmoid(cfg["a_s"][st] + cfg["b_s"][st] * logit(float(p_eff[key])))
        p_cal[key] = p
        yhat[key] = 1 if p >= cfg["tau_s"][st] else 0
    return p_cal, yhat


# ---------------------------------------------------------------------------
# stage S7: weighted metrics
# ---------------------------------------------------------------------------


def fbeta(precision, recall, beta):
    b2 = beta * beta
    den = b2 * precision + recall
    if den == 0:
        return Fraction(0)
    return (1 + b2) * precision * recall / den


def stratum_stats(weights, yhat, stratum):
    tp = fp = fn = 0
    weight_sum = 0
    for key, w in weights.items():
        if w["stratum"] != stratum:
            continue
        weight_sum += w["weight_units"]
        y, h = w["y"], yhat[key]
        if y == 1 and h == 1:
            tp += w["weight_units"]
        elif y == 0 and h == 1:
            fp += w["weight_units"]
        elif y == 1 and h == 0:
            fn += w["weight_units"]
    precision = Fraction(tp, tp + fp) if (tp + fp) else Fraction(0)
    recall = Fraction(tp, tp + fn) if (tp + fn) else Fraction(0)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall,
            "weight_sum": weight_sum}


# ---------------------------------------------------------------------------
# stage S8: uncertainty and payout
# ---------------------------------------------------------------------------


def wilson(p, n, z):
    if n <= 0:
        return 0.0, 1.0
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))
    return max(0.0, center - half), min(1.0, center + half)


def kish_n_eff(units):
    if not units:
        return 0.0
    sq = sum(u * u for u in units)
    if sq == 0:
        return 0.0
    total = sum(units)
    return (float(total) * float(total)) / float(sq)


def apportion_bps(values, total_bps, order):
    """Largest-remainder apportionment of total_bps proportional to values."""
    total = sum(values[k] for k in order)
    if total <= 0:
        return {k: 0 for k in order}
    exact = {k: Fraction(values[k]) * total_bps / Fraction(total) for k in order}
    cells = {k: exact[k].numerator // exact[k].denominator for k in order}
    left = total_bps - sum(cells.values())
    rank = sorted(order, key=lambda k: (-(exact[k] - cells[k]), k))
    i = 0
    while left > 0:
        cells[rank[i % len(rank)]] += 1
        left -= 1
        i += 1
    return cells


# ---------------------------------------------------------------------------
# artifact writers
# ---------------------------------------------------------------------------


def write_text(out_dir, name, text):
    with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def write_json(out_dir, name, obj):
    write_text(out_dir, name, json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_table(out_dir, name, header, rows, delim):
    lines = [delim.join(header)]
    lines.extend(delim.join(str(c) for c in row) for row in rows)
    write_text(out_dir, name, "\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------

SLUGS = {
    "BRONZE-NA": "metrics_bro_na.json",
    "BRONZE-EU": "metrics_bro_eu.json",
    "BRONZE-APAC": "metrics_bro_ap.json",
    "SILVER-NA": "metrics_sil_na.json",
    "SILVER-EU": "metrics_sil_eu.json",
    "SILVER-APAC": "metrics_sil_ap.json",
    "GOLD-NA": "metrics_gld_na.json",
    "GOLD-EU": "metrics_gld_eu.json",
    "GOLD-APAC": "metrics_gld_ap.json",
}

CORE_ORDER = ["population.csv", "weights.csv", "payout.csv", "metrics.json"]


def load_slugs(data_dir):
    """Per-stratum metrics filename slugs, as declared by the schema document."""
    try:
        text = read_text(os.path.join(data_dir, "output_artifact_schemas.md"))
    except OSError:
        return dict(SLUGS)
    found = re.findall(r"([A-Z]+-[A-Z]+) to (metrics_\w+\.json)", text)
    return dict(found) if found else dict(SLUGS)


def load_config(data_dir):
    cfg = {}
    season = read_json(os.path.join(data_dir, "season_profile.json"))
    cfg["strata"] = read_text(os.path.join(data_dir, "stratum_enumeration.txt")).split()
    cfg["calibration_version"] = season["calibration_version"]
    cfg["window_days"] = int(season["window_days"])
    cfg["base_p"] = Fraction(season["base_p"])

    codes = read_text(os.path.join(data_dir, "seal_status_codes.txt"))
    m = re.search(r"^(\S+)\s*=\s*match committed", codes, re.M)
    cfg["seal_code"] = m.group(1) if m else "SEALED"

    keys_xml = ET.fromstring(read_text(os.path.join(data_dir, "grouping_keys.xml")))
    cfg["match_key_fields"] = [t.strip() for t in keys_xml.find("match_key").text.split("|")]
    cfg["crosswalk"] = {k: (v if v in ("positive", "negative") else "excluded")
                        for k, v in read_json(
                            os.path.join(data_dir, "verdict_crosswalk.json")).items()}

    units_doc = read_json(os.path.join(data_dir, "unit_scale_exponents.json"))
    cfg["scale_exponents"] = {k: int(v) for k, v in units_doc["scale_exponents"].items()}
    # the family whose count-to-ledger gain is published only on the live sheet
    m = re.search(r"([A-Z]+)\s+gain is on the spreadsheet",
                  units_doc.get("note", ""), re.I)
    cfg["ore_family"] = m.group(1).upper() if m else "ORE"

    wconst = read_json(os.path.join(data_dir, "weighting_constants.json"))
    cfg["quantize_decimals"] = int(wconst["quantize_decimals"])
    cfg["weight_cap"] = wconst["cap"]

    rnd = read_text(os.path.join(data_dir, "rounding_and_precision.yml"))
    m = re.search(r"probability_decimals:\s*(\d+)", rnd)
    cfg["prob_decimals"] = int(m.group(1)) if m else 8
    m = re.search(r"quantize_decimals:\s*(\d+)", rnd)
    if m:
        cfg["quantize_decimals"] = int(m.group(1))

    s3 = read_text(os.path.join(data_dir, "spec_stage_s3_running_baseline.md"))
    m = re.search(r"(\d*\.?\d+)\s*\*\s*p_raw\s*\+\s*(\d*\.?\d+)\s*\*\s*previous_baseline", s3)
    cfg["baseline_w_raw"] = Fraction(m.group(1)) if m else Fraction(85, 100)
    cfg["baseline_w_prev"] = Fraction(m.group(2)) if m else Fraction(15, 100)
    m = re.search(r"clamped to \[\s*%s\s*,\s*%s\s*\]" % (NUM_RE, NUM_RE), s3)
    cfg["p_raw_bounds"] = (Fraction(m.group(1)), Fraction(m.group(2))) if m else (
        Fraction(1, 1000000), Fraction(999999, 1000000))

    # the server half of a frozen stratum name is the nonresponse partition
    cfg["server_of"] = lambda st: st.rsplit("-", 1)[1]

    cells = read_workbook(os.path.join(data_dir, "ladder_tuning_grid.xlsx"),
                          cfg["calibration_version"])
    header_row = None
    ore_row = None
    label_rows = {}
    for (r, col), text in cells.items():
        if col == "A":
            label = text.strip()
            if label == "parameter":
                header_row = r
            elif label.startswith("ore_to_ledger_gain"):
                ore_row = r
            elif label in ("a_s", "b_s", "tau_s", "recovery_s"):
                label_rows[label] = r
    col_by_name = {}
    for (r, col), text in cells.items():
        if header_row is not None and r == header_row and col != "A" and text.strip():
            col_by_name[text.strip()] = col
    cfg["ore_gain"] = Fraction(cells.get((ore_row, "B"), "0"))
    for label in ("a_s", "b_s", "tau_s", "recovery_s"):
        row = label_rows.get(label)
        params = {}
        for name, col in col_by_name.items():
            if name == "DEFAULT-ROW":
                continue
            val = cells.get((row, col))
            if val not in (None, ""):
                params[name] = Fraction(val)
        cfg[label] = params

    policy = read_pdf_text(os.path.join(data_dir, "payout_cost_policy.pdf"))
    cfg["review_unit_cost"] = first_number(
        [r"unit cost is\s*%s\s*credits" % NUM_RE,
         r"%s\s*credits per\s*flagged match" % NUM_RE], policy, Fraction, "review unit cost")
    cfg["beta"] = first_number([r"beta\s*=\s*%s" % NUM_RE], policy, Fraction, "F-beta beta")
    cfg["z"] = first_number([r"\bz\s*=\s*%s" % NUM_RE], policy, Fraction, "CI z")

    addendum = read_docx_text(os.path.join(data_dir, "settlement_levy_addendum.docx"))
    cfg["levy_bps"] = int(first_number([r"levy of\s*%s\s*basis points" % NUM_RE,
                                        r"%s\s*basis points" % NUM_RE],
                                       addendum, int, "levy basis points"))
    cfg["settlement_floor"] = int(first_number(
        [r"floored at\s*%s\s*credits" % NUM_RE, r"floor(?:ed)?\s*at\s*%s" % NUM_RE],
        addendum, int, "settlement floor"))
    return cfg


def run(data_dir, out_dir):
    cfg = load_config(data_dir)
    os.makedirs(out_dir, exist_ok=True)
    strata = cfg["strata"]
    qdp = cfg["quantize_decimals"]
    qscale = 10 ** qdp
    pdp = cfg["prob_decimals"]

    matches = build_population(data_dir, cfg)
    resolved = resolve_verdicts(matches, data_dir, cfg)
    p_eff = running_baseline(resolved, cfg)
    units = ledger_units(matches, data_dir, cfg)
    weights, pop_by_stratum, sampled_by_stratum = two_level_weights(matches, resolved, cfg)
    p_cal, yhat = calibrate(resolved, p_eff, cfg)

    stats = {st: stratum_stats(weights, yhat, st) for st in strata}
    tot_tp = sum(stats[st]["tp"] for st in strata)
    tot_fp = sum(stats[st]["fp"] for st in strata)
    tot_fn = sum(stats[st]["fn"] for st in strata)
    tot_w = sum(stats[st]["weight_sum"] for st in strata)
    overall_p = Fraction(tot_tp, tot_tp + tot_fp) if (tot_tp + tot_fp) else Fraction(0)
    overall_r = Fraction(tot_tp, tot_tp + tot_fn) if (tot_tp + tot_fn) else Fraction(0)
    overall_f = fbeta(overall_p, overall_r, cfg["beta"])
    macro_p = (sum((Fraction(stats[st]["weight_sum"], tot_w) * stats[st]["precision"]
                    for st in strata), Fraction(0)) if tot_w else Fraction(0))
    macro_r = (sum((Fraction(stats[st]["weight_sum"], tot_w) * stats[st]["recall"]
                    for st in strata), Fraction(0)) if tot_w else Fraction(0))

    # stage S8 payout basis: the ledger units of the decisive matches
    ledger_tp = {st: 0 for st in strata}
    ledger_fn = {st: 0 for st in strata}
    for key, w in weights.items():
        st = w["stratum"]
        if w["y"] == 1 and yhat[key] == 1:
            ledger_tp[st] += units[key]
        elif w["y"] == 1 and yhat[key] == 0:
            ledger_fn[st] += units[key]

    rewarded = {}
    forfeited = {}
    review = {}
    n_flagged = {st: 0 for st in strata}
    for st in strata:
        rec = cfg["recovery_s"].get(st, cfg["recovery_s"].get("DEFAULT-ROW", Fraction(1)))
        value = Fraction(ledger_tp[st]) * rec
        rewarded[st] = rhe(value.numerator, value.denominator)
        forfeited[st] = ledger_fn[st]
        flagged_units = 0
        for key, w in weights.items():
            if w["stratum"] == st and yhat[key] == 1:
                flagged_units += w["weight_units"]
                n_flagged[st] += 1
        cost = cfg["review_unit_cost"] * Fraction(flagged_units, qscale)
        review[st] = rhe(cost.numerator, cost.denominator)

    levy = {}
    net = {}
    floored = []
    for st in strata:
        value = Fraction(rewarded[st] * cfg["levy_bps"], 10000)
        levy[st] = rhe(value.numerator, value.denominator)
        post = rewarded[st] - review[st] - levy[st]
        if post < cfg["settlement_floor"]:
            floored.append(st)
            post = cfg["settlement_floor"]
        net[st] = post
    floored.sort()
    total_net = sum(net[st] for st in strata)

    z = float(cfg["z"])
    ci = {}
    for st in strata:
        pos_units = [w["weight_units"] for k, w in weights.items()
                     if w["stratum"] == st and w["y"] == 1]
        pred_units = [w["weight_units"] for k, w in weights.items()
                      if w["stratum"] == st and yhat[k] == 1]
        n_r = kish_n_eff(pos_units)
        n_p = kish_n_eff(pred_units)
        rlo, rhi = wilson(float(stats[st]["recall"]), n_r, z)
        plo, phi = wilson(float(stats[st]["precision"]), n_p, z)
        ci[st] = (rlo, rhi, plo, phi, n_r, n_p)

    # ------------------------------------------------------------------
    # artifacts
    # ------------------------------------------------------------------
    pop_rows = [[k, m["account_id"], m["stratum"], m["drawn"], m["loot_currency"],
                 m["anchor_date"]] for k, m in sorted(matches.items())]
    write_table(out_dir, "population.csv",
                ["match_key", "account_id", "stratum", "drawn", "loot_currency",
                 "anchor_date"], pop_rows, ",")

    w_rows = [[k, w["stratum"], w["y"], yhat[k], matches[k]["loot_currency"], units[k],
               fmt_frac(p_eff[k], pdp), fmt_float(p_cal[k], pdp),
               fmt_units(w["weight_units"], qdp)] for k, w in sorted(weights.items())]
    write_table(out_dir, "weights.csv",
                ["match_key", "stratum", "y", "yhat", "loot_currency", "ledger_units",
                 "p_eff", "p_cal", "weight"], w_rows, ",")

    payout_rows = [[st, rewarded[st], forfeited[st], review[st], levy[st], net[st]]
                   for st in strata]
    payout_rows.append(["TOTAL", sum(rewarded[st] for st in strata),
                        sum(forfeited[st] for st in strata),
                        sum(review[st] for st in strata),
                        sum(levy[st] for st in strata), total_net])
    write_table(out_dir, "payout.csv",
                ["stratum", "rewarded_credits", "forfeited_credits", "review_credits",
                 "levy_credits", "net_credits"], payout_rows, ",")

    def f6(fr):
        return fmt_frac(fr, 6)

    write_json(out_dir, "metrics.json", {
        "overall": {"precision": f6(overall_p), "recall": f6(overall_r),
                    "fbeta": f6(overall_f), "macro_precision": f6(macro_p),
                    "macro_recall": f6(macro_r)},
        "strata": {st: {"precision": f6(stats[st]["precision"]),
                        "recall": f6(stats[st]["recall"]),
                        "fbeta": f6(fbeta(stats[st]["precision"], stats[st]["recall"],
                                          cfg["beta"]))} for st in strata}})

    slugs = load_slugs(data_dir)
    for st in strata:
        slug = slugs.get(st)
        if slug is None:
            continue
        write_json(out_dir, slug, {
            "stratum": st,
            "precision": f6(stats[st]["precision"]),
            "recall": f6(stats[st]["recall"]),
            "fbeta": f6(fbeta(stats[st]["precision"], stats[st]["recall"], cfg["beta"])),
            "tp": fmt_units(stats[st]["tp"], qdp),
            "fp": fmt_units(stats[st]["fp"], qdp),
            "fn": fmt_units(stats[st]["fn"], qdp)})

    write_table(out_dir, "payout_breakdown.tsv",
                ["stratum", "rewarded_credits", "forfeited_credits"],
                [[st, rewarded[st], forfeited[st]] for st in strata], "\t")
    write_table(out_dir, "payout_ledger.psv",
                ["stratum", "review_credits", "levy_credits", "net_credits"],
                [[st, review[st], levy[st], net[st]] for st in strata], "|")

    shares = apportion_bps(forfeited, 10000, strata)
    write_table(out_dir, "forfeited_shares.csv",
                ["stratum", "forfeited_credits", "share_bps"],
                [[st, forfeited[st], shares[st]] for st in strata], ",")

    write_table(out_dir, "confidence_intervals.csv",
                ["stratum", "recall_lo", "recall_hi", "prec_lo", "prec_hi",
                 "n_eff_recall", "n_eff_precision"],
                [[st, fmt_float(ci[st][0], 6), fmt_float(ci[st][1], 6),
                  fmt_float(ci[st][2], 6), fmt_float(ci[st][3], 6),
                  fmt_float(ci[st][4], 6), fmt_float(ci[st][5], 6)] for st in strata], ",")

    write_text(out_dir, "stratum_metrics_stream.jsonl", "".join(
        json.dumps({"stratum": st, "precision": f6(stats[st]["precision"]),
                    "recall": f6(stats[st]["recall"]),
                    "fbeta": f6(fbeta(stats[st]["precision"], stats[st]["recall"],
                                      cfg["beta"]))}, sort_keys=True) + "\n"
        for st in strata))

    write_text(out_dir, "overall_metrics.md", "\n".join([
        "# Overall Settled Metrics", "",
        "- precision: %s" % f6(overall_p),
        "- recall: %s" % f6(overall_r),
        "- fbeta: %s" % f6(overall_f),
        "- macro_precision: %s" % f6(macro_p),
        "- macro_recall: %s" % f6(macro_r), ""]))

    write_text(out_dir, "reconciliation_report.md", "\n".join([
        "# Settlement Reconciliation Report", "",
        "- population: %d" % len(matches),
        "- resolved: %d" % len(resolved),
        "- weighted: %d" % len(weights),
        "- total_net_credits: %d" % total_net,
        "- calibration_version: %s" % cfg["calibration_version"], ""]))

    xml = ['<?xml version="1.0" encoding="UTF-8"?>', "<rollup>"]
    for st in strata:
        xml.append('  <stratum id="%s">' % st)
        xml.append("    <precision>%s</precision>" % f6(stats[st]["precision"]))
        xml.append("    <recall>%s</recall>" % f6(stats[st]["recall"]))
        xml.append("    <fbeta>%s</fbeta>"
                   % f6(fbeta(stats[st]["precision"], stats[st]["recall"], cfg["beta"])))
        xml.append("  </stratum>")
    xml.append("</rollup>")
    write_text(out_dir, "rollup.xml", "\n".join(xml) + "\n")

    n_pos = sum(1 for m in matches.values() if m["verdict"] == "positive")
    n_neg = sum(1 for m in matches.values() if m["verdict"] == "negative")
    write_json(out_dir, "label_distribution.json", {
        "positive": n_pos, "negative": n_neg,
        "resolved_total": n_pos + n_neg, "population_total": len(matches)})

    n_flag = sum(n_flagged[st] for st in strata)
    write_json(out_dir, "decision_distribution.json", {
        "flagged": n_flag, "cleared": len(weights) - n_flag,
        "weighted_total": len(weights)})

    write_json(out_dir, "frame_counts.json", {
        "population_by_stratum": {st: pop_by_stratum[st] for st in strata},
        "sampled_by_stratum": {st: sampled_by_stratum[st] for st in strata},
        "resolved_weighted": {st: sum(1 for w in weights.values()
                                      if w["stratum"] == st) for st in strata}})

    write_json(out_dir, "weight_diagnostics.json", {
        "weight_sum_by_stratum": {st: fmt_units(stats[st]["weight_sum"], qdp)
                                  for st in strata},
        "cap": str(cfg["weight_cap"]),
        "max_weight": fmt_units(max((w["weight_units"] for w in weights.values()),
                                    default=0), qdp)})

    write_json(out_dir, "net_payout_summary.json", {
        "total_rewarded_credits": sum(rewarded[st] for st in strata),
        "total_forfeited_credits": sum(forfeited[st] for st in strata),
        "total_review_credits": sum(review[st] for st in strata),
        "total_levy_credits": sum(levy[st] for st in strata),
        "total_net_credits": total_net,
        "by_stratum": {st: net[st] for st in strata}})

    write_json(out_dir, "levy_summary.json", {
        "levy_bps": cfg["levy_bps"],
        "settlement_floor": cfg["settlement_floor"],
        "total_levy_credits": sum(levy[st] for st in strata),
        "levy_by_stratum": {st: levy[st] for st in strata},
        "floored_strata": floored})

    write_json(out_dir, "audit_summary.json", {
        "population": len(matches),
        "resolved": len(resolved),
        "weighted": len(weights),
        "flagged": n_flag,
        "overall_fbeta": f6(overall_f),
        "calibration_version": cfg["calibration_version"]})

    digest = hashlib.sha256()
    for name in CORE_ORDER:
        with open(os.path.join(out_dir, name), "rb") as fh:
            digest.update(fh.read())
    write_json(out_dir, "manifest.json", {
        "core_order": CORE_ORDER,
        "digest_sha256": digest.hexdigest()})


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: settle.py DATA_DIR OUT_DIR\n")
        return 2
    run(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
