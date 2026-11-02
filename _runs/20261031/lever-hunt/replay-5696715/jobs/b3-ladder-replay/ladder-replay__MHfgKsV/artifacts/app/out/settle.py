#!/usr/bin/env python3
"""Quarterly arena-ladder season settlement (stages S1..S9).

Usage: python3 settle.py DATA_DIR OUT_DIR

Every rule, schema and constant is read from DATA_DIR; nothing about a
particular corpus is embedded here.
"""
import csv
import datetime
import hashlib
import json
import math
import os
import re
import sys
import zipfile
import zlib
from fractions import Fraction
from xml.etree import ElementTree as ET

SSNS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RELNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
WNS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

ORE_GAIN_LABEL = "ore_to_ledger_gain"
PARAM_LABELS = ("a_s", "b_s", "tau_s", "recovery_s")


# ---------------------------------------------------------------- numerics
def frac(x):
    """Exact Fraction from Fraction/int/float/decimal-string."""
    if isinstance(x, Fraction):
        return x
    if isinstance(x, int):
        return Fraction(x)
    if isinstance(x, float):
        return Fraction(x)
    return Fraction(str(x).strip())


def round_half_even(value, dp=0):
    """Exact half-to-even rounding to dp decimals, returned as a Fraction."""
    scaled = frac(value) * 10 ** dp
    floor = scaled.numerator // scaled.denominator
    rem = scaled - floor
    if rem > Fraction(1, 2) or (rem == Fraction(1, 2) and floor % 2 != 0):
        floor += 1
    return Fraction(floor, 10 ** dp)


def to_int(value):
    return int(round_half_even(value, 0))


def fmt(value, dp):
    units = int(round_half_even(value, dp) * 10 ** dp)
    sign = "-" if units < 0 else ""
    units = abs(units)
    if dp == 0:
        return sign + str(units)
    whole, part = divmod(units, 10 ** dp)
    return "%s%d.%0*d" % (sign, whole, dp, part)


def logit(p):
    return math.log(p / (1.0 - p))


def sigmoid(x):
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def safe_div(num, den):
    return Fraction(0) if frac(den) == 0 else frac(num) / frac(den)


def wilson(p, n, z):
    if n <= 0:
        return 0.0, 0.0
    p = float(p)
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = (z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))) / denom
    return center - half, center + half


# ------------------------------------------------------------ input readers
def read_rows(path, delim):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=delim))


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read_lines(path):
    with open(path, encoding="utf-8") as fh:
        return [ln.rstrip("\n") for ln in fh]


def cell_col(ref):
    return "".join(ch for ch in ref if ch.isalpha())


def cell_row(ref):
    return int("".join(ch for ch in ref if ch.isdigit()))


def load_workbook(path):
    """Return [(sheet_name, {(row, col_letter): text}), ...] in workbook order."""
    zf = zipfile.ZipFile(path)
    names = zf.namelist()
    shared = []
    for cand in names:
        if cand.lower() == "xl/sharedstrings.xml":
            root = ET.fromstring(zf.read(cand))
            for si in root.iter(SSNS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(SSNS + "t")))
            break
    relmap = {}
    if "xl/_rels/workbook.xml.rels" in names:
        for rel in ET.fromstring(zf.read("xl/_rels/workbook.xml.rels")):
            relmap[rel.get("Id")] = rel.get("Target")
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    sheets = []
    for sh in wb.iter(SSNS + "sheet"):
        target = relmap.get(sh.get(RELNS + "id"))
        if target is None:
            continue
        target = target.lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        if target in names:
            sheets.append((sh.get("name"), target))
    out = []
    for name, target in sheets:
        grid = {}
        for cell in ET.fromstring(zf.read(target)).iter(SSNS + "c"):
            ref = cell.get("r")
            if not ref:
                continue
            ctype = cell.get("t")
            vnode = cell.find(SSNS + "v")
            if ctype == "s" and vnode is not None:
                text = shared[int(vnode.text)]
            elif ctype in (None, "n") and vnode is not None:
                text = vnode.text or ""
            else:
                text = "".join(t.text or "" for t in cell.iter(SSNS + "t"))
            grid[(cell_row(ref), cell_col(ref))] = text.strip()
        out.append((name, grid))
    return out


def live_sheet_params(path, calibration_version):
    """Pick the sheet whose B1 equals the calibration version; read its grid."""
    live = None
    for _name, grid in load_workbook(path):
        if grid.get((1, "B"), "") == calibration_version:
            live = grid
            break
    if live is None:
        raise SystemExit("no workbook sheet with B1 == %r" % calibration_version)
    maxrow = max(r for r, _ in live)
    ore_gain = None
    header_row = None
    for r in range(1, maxrow + 1):
        label = live.get((r, "A"), "")
        if label == ORE_GAIN_LABEL:
            ore_gain = frac(live[(r, "B")])
        elif label == "parameter" and header_row is None:
            header_row = r
    if ore_gain is None or header_row is None:
        raise SystemExit("live sheet missing ore gain or parameter header")
    cols = {c: text for (r, c), text in live.items()
            if r == header_row and c != "A" and text}
    params = {}
    for r in range(header_row + 1, maxrow + 1):
        label = live.get((r, "A"), "")
        if label in PARAM_LABELS:
            params[label] = {stratum: frac(live[(r, c)])
                             for c, stratum in cols.items()
                             if live.get((r, c))}
    missing = [p for p in PARAM_LABELS if p not in params]
    if missing:
        raise SystemExit("live sheet missing parameters: %s" % missing)
    return ore_gain, params


def pdf_text(path):
    with open(path, "rb") as fh:
        blob = fh.read()
    chunks = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", blob, re.S):
        body = match.group(1)
        try:
            body = zlib.decompress(body)
        except zlib.error:
            pass
        for show in re.finditer(rb"\(((?:\\.|[^\\()])*)\)\s*Tj", body):
            chunks.append(re.sub(r"\\([()\\])", r"\1",
                                 show.group(1).decode("latin-1")))
    return " ".join(chunks)


def policy_constants(path):
    text = pdf_text(path)
    cost = re.search(r"unit cost is\s+([0-9]+(?:\.[0-9]+)?)\s+credits", text)
    beta = re.search(r"F-beta with beta\s*=\s*([0-9]+(?:\.[0-9]+)?)", text) or \
        re.search(r"\bbeta\s*=\s*([0-9]+(?:\.[0-9]+)?)", text)
    zval = re.search(r"\bz\s*=\s*([0-9]+(?:\.[0-9]+)?)", text)
    if not (cost and beta and zval):
        raise SystemExit("policy document missing review cost / beta / z")
    return frac(cost.group(1)), frac(beta.group(1)), float(zval.group(1))


def docx_text(path):
    root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    return " ".join("".join(t.text or "" for t in p.iter(WNS + "t"))
                    for p in root.iter(WNS + "p"))


def levy_constants(path):
    text = docx_text(path)
    bps = re.search(r"levy of\s+([0-9]+)\s+basis points", text) or \
        re.search(r"([0-9]+)\s+basis points", text)
    floor = re.search(r"floored at\s+([0-9]+)\s+credits", text) or \
        re.search(r"floored at\s+([0-9]+)", text)
    if not (bps and floor):
        raise SystemExit("levy addendum missing levy bps / settlement floor")
    return int(bps.group(1)), int(floor.group(1))


def stratum_slugs(schema_path):
    """Read the documented stratum -> metrics filename mapping."""
    with open(schema_path, encoding="utf-8") as fh:
        text = fh.read()
    return dict(re.findall(r"([A-Z]+-[A-Z]+)\s+to\s+(metrics_[a-z0-9_]+\.json)", text))


# -------------------------------------------------------------- settlement
def settle(data_dir, out_dir):
    D = lambda name: os.path.join(data_dir, name)

    profile = read_json(D("season_profile.json"))
    calib_version = profile["calibration_version"]
    base_p = float(profile["base_p"])
    window_days = int(profile["window_days"])
    weight_cap = str(profile["weight_cap"])

    strata_order = [ln.strip() for ln in read_lines(D("stratum_enumeration.txt"))
                    if ln.strip()]
    rank = {s: i for i, s in enumerate(strata_order)}

    exponents = read_json(D("unit_scale_exponents.json"))["scale_exponents"]
    crosswalk = read_json(D("verdict_crosswalk.json"))
    quant_dp = int(read_json(D("weighting_constants.json"))["quantize_decimals"])
    prob_dp = 8
    for ln in read_lines(D("rounding_and_precision.yml")):
        if ln.startswith("probability_decimals:"):
            prob_dp = int(ln.split(":", 1)[1])
    ore_family = ORE_GAIN_LABEL.split("_", 1)[0].upper()
    slugs = stratum_slugs(D("output_artifact_schemas.md"))
    missing_slugs = [s for s in strata_order if s not in slugs]
    if missing_slugs:
        raise SystemExit("schema has no metrics filename for %s" % missing_slugs)

    ore_gain, params = live_sheet_params(D("ladder_tuning_grid.xlsx"), calib_version)
    review_cost, beta, zval = policy_constants(D("payout_cost_policy.pdf"))
    levy_bps, floor_credits = levy_constants(D("settlement_levy_addendum.docx"))

    accounts = {r["account_id"]: r
                for r in read_rows(D("account_tier_crosswalk.csv"), ",")}
    drawn_flag, drawn_stratum = {}, {}
    for row in read_rows(D("cohort_draw_register.psv"), "|"):
        key = row["match_key"].strip('"')
        drawn_flag[key] = int(row["drawn"])
        drawn_stratum[key] = row["stratum_frozen"]

    drift = {}
    for row in read_rows(D("season_patch_reference.csv"), ","):
        drift.setdefault(row["unit_family"], []).append(
            (row["ref_date"], frac(row["drift_mult"])))
    for fam in drift:
        drift[fam].sort(key=lambda item: item[0])

    # ---- S1 canonicalization: one row per match key, sealed only ---------
    attempts = {}
    for row in read_rows(D("ladder_match_capture_s1.csv"), ","):
        key = "|".join((row["account_id"], row["hero_handle"],
                        row["seed_hash"], row["ladder_split"]))
        attempts.setdefault(key, []).append(row)

    population = {}
    for key, rows in attempts.items():
        sealed = [r for r in rows if r["seal_status"] == "SEALED"]
        if not sealed:
            continue
        canonical = max(sealed, key=lambda r: int(r["checkpoint_no"]))
        anchor = min(rows, key=lambda r: int(r["checkpoint_no"]))
        account = canonical["account_id"]
        stratum = drawn_stratum.get(key)
        if stratum is None:
            acc = accounts[account]
            stratum = acc["frozen_tier"] + "-" + acc["frozen_server"]
        population[key] = {
            "match_key": key,
            "account_id": account,
            "stratum": stratum,
            "server": stratum.split("-", 1)[1],
            "drawn": drawn_flag.get(key, 0),
            "loot_currency": canonical["loot_currency"],
            "raw_loot": canonical["raw_loot"],
            "p_raw": canonical["p_raw"],
            "anchor_date": anchor["match_epoch"],
        }
    pop_keys = sorted(population)

    # ---- S2 anchoring & verdicts ----------------------------------------
    history = {}
    for row in read_rows(D("verdict_amendment_history.tsv"), "\t"):
        history.setdefault(row["match_key"], []).append(row)

    iso = datetime.date.fromisoformat
    for key in pop_keys:
        rec = population[key]
        anchor = iso(rec["anchor_date"])
        in_window = [r for r in history.get(key, [])
                     if 0 <= (iso(r["effective_at"]) - anchor).days <= window_days]
        label = None
        if in_window:
            final = max(in_window, key=lambda r: int(r["review_seq"]))
            mapped = crosswalk.get(final["verdict"], "excluded")
            if mapped == "positive":
                label = 1
            elif mapped == "negative":
                label = 0
        rec["y"] = label

    resolved_keys = [k for k in pop_keys if population[k]["y"] is not None]

    # ---- S3 running ladder baseline per frozen stratum -------------------
    resolved_by_stratum = {}
    for key in resolved_keys:
        resolved_by_stratum.setdefault(population[key]["stratum"], []).append(key)
    for keys in resolved_by_stratum.values():
        baseline = base_p
        for key in sorted(keys):
            p_raw = min(max(float(population[key]["p_raw"]), 1e-6), 0.999999)
            p_eff = min(max(0.85 * p_raw + 0.15 * baseline, 1e-6), 0.999999)
            population[key]["p_eff"] = p_eff
            baseline = p_eff

    # ---- S4 reward-unit canonicalization --------------------------------
    for key in pop_keys:
        rec = population[key]
        family = rec["loot_currency"]
        if family == ore_family or family not in exponents:
            scale = ore_gain
        else:
            scale = Fraction(10) ** int(exponents[family])
        mult = None
        for ref_date, value in drift.get(family, []):
            if ref_date <= rec["anchor_date"]:
                mult = value
            else:
                break
        if mult is None:
            raise SystemExit("no drift reference on or before %s for %s"
                             % (rec["anchor_date"], family))
        rec["ledger_units"] = to_int(frac(rec["raw_loot"]) * scale * mult)

    # ---- S5 two-level rarity weights ------------------------------------
    pop_by_stratum = {s: 0 for s in strata_order}
    sampled_by_stratum = {s: 0 for s in strata_order}
    sampled_by_server, resolved_by_server = {}, {}
    for key in pop_keys:
        rec = population[key]
        pop_by_stratum[rec["stratum"]] = pop_by_stratum.get(rec["stratum"], 0) + 1
        if rec["drawn"] == 1:
            sampled_by_stratum[rec["stratum"]] = sampled_by_stratum.get(rec["stratum"], 0) + 1
            sampled_by_server[rec["server"]] = sampled_by_server.get(rec["server"], 0) + 1
        if rec["y"] is not None:
            resolved_by_server[rec["server"]] = resolved_by_server.get(rec["server"], 0) + 1

    weighted_keys = sorted(k for k in resolved_keys if population[k]["drawn"] == 1)
    weighted_by_stratum = {s: [] for s in strata_order}
    for key in weighted_keys:
        weighted_by_stratum.setdefault(population[key]["stratum"], []).append(key)

    for stratum, keys in weighted_by_stratum.items():
        if not keys:
            continue
        server = stratum.split("-", 1)[1]
        base_rate = safe_div(pop_by_stratum.get(stratum, 0),
                             sampled_by_stratum.get(stratum, 0))
        nonresponse = safe_div(sampled_by_server.get(server, 0),
                               resolved_by_server.get(server, 0))
        exact = base_rate * nonresponse
        quantized = {k: round_half_even(exact, quant_dp) for k in keys}
        residue = round_half_even(exact * len(keys), quant_dp) - sum(quantized.values())
        if residue != 0:
            quantized[sorted(keys, key=lambda k: (-quantized[k], k))[0]] += residue
        for key in keys:
            population[key]["weight"] = quantized[key]

    # ---- S6 calibration & inclusive decision ----------------------------
    for key in weighted_keys:
        rec = population[key]
        stratum = rec["stratum"]
        p_cal = sigmoid(float(params["a_s"][stratum])
                        + float(params["b_s"][stratum]) * logit(rec["p_eff"]))
        rec["p_cal"] = p_cal
        rec["yhat"] = 1 if p_cal >= float(params["tau_s"][stratum]) else 0

    # ---- S7 weighted metrics --------------------------------------------
    tp = {s: Fraction(0) for s in strata_order}
    fp = {s: Fraction(0) for s in strata_order}
    fn = {s: Fraction(0) for s in strata_order}
    wsum = {s: Fraction(0) for s in strata_order}
    for key in weighted_keys:
        rec = population[key]
        s, w = rec["stratum"], rec["weight"]
        wsum[s] += w
        if rec["y"] == 1 and rec["yhat"] == 1:
            tp[s] += w
        elif rec["y"] == 0 and rec["yhat"] == 1:
            fp[s] += w
        elif rec["y"] == 1 and rec["yhat"] == 0:
            fn[s] += w

    beta2 = beta * beta

    def fbeta_of(p, r):
        den = beta2 * p + r
        return Fraction(0) if den == 0 else (1 + beta2) * p * r / den

    precision, recall, fbeta = {}, {}, {}
    for s in strata_order:
        precision[s] = safe_div(tp[s], tp[s] + fp[s])
        recall[s] = safe_div(tp[s], tp[s] + fn[s])
        fbeta[s] = fbeta_of(precision[s], recall[s])

    tp_t, fp_t, fn_t = sum(tp.values()), sum(fp.values()), sum(fn.values())
    w_total = sum(wsum.values())
    overall_p = safe_div(tp_t, tp_t + fp_t)
    overall_r = safe_div(tp_t, tp_t + fn_t)
    overall_f = fbeta_of(overall_p, overall_r)
    macro_p = sum((safe_div(wsum[s], w_total) * precision[s] for s in strata_order),
                  Fraction(0))
    macro_r = sum((safe_div(wsum[s], w_total) * recall[s] for s in strata_order),
                  Fraction(0))

    # ---- S8 Wilson intervals on Kish effective N ------------------------
    def n_eff(weights):
        total = sum(weights, Fraction(0))
        sq = sum((w * w for w in weights), Fraction(0))
        return Fraction(0) if sq == 0 else total * total / sq

    intervals = {}
    for s in strata_order:
        keys = weighted_by_stratum.get(s, [])
        ne_r = n_eff([population[k]["weight"] for k in keys if population[k]["y"] == 1])
        ne_p = n_eff([population[k]["weight"] for k in keys if population[k]["yhat"] == 1])
        r_lo, r_hi = wilson(recall[s], float(ne_r), zval)
        p_lo, p_hi = wilson(precision[s], float(ne_p), zval)
        intervals[s] = (r_lo, r_hi, p_lo, p_hi, ne_r, ne_p)

    # ---- S8/S9 payout, levy, floor --------------------------------------
    rewarded, forfeited, review, levy = {}, {}, {}, {}
    net, floored = {}, []
    for s in strata_order:
        recov = params["recovery_s"].get(s, Fraction(0))
        rew = forf = flagged_w = Fraction(0)
        for key in weighted_by_stratum.get(s, []):
            rec = population[key]
            w, units = rec["weight"], rec["ledger_units"]
            if rec["yhat"] == 1:
                flagged_w += w
            if rec["y"] == 1 and rec["yhat"] == 1:
                rew += w * units * recov
            elif rec["y"] == 1 and rec["yhat"] == 0:
                forf += w * units
        rewarded[s] = to_int(rew)
        forfeited[s] = to_int(forf)
        review[s] = to_int(flagged_w * review_cost)
        levy[s] = to_int(Fraction(rewarded[s] * levy_bps, 10000))
        value = rewarded[s] - review[s] - levy[s]
        if value < floor_credits:
            floored.append(s)
            net[s] = floor_credits
        else:
            net[s] = value

    # ---- forfeited basis-point shares (largest remainder) ----------------
    total_forf = sum(forfeited.values())
    share_bps = {s: 0 for s in strata_order}
    if total_forf > 0:
        exact = {s: Fraction(forfeited[s] * 10000, total_forf) for s in strata_order}
        share_bps = {s: int(exact[s]) for s in strata_order}
        left = 10000 - sum(share_bps.values())
        order = sorted(strata_order,
                       key=lambda s: (-(exact[s] - share_bps[s]), rank[s]))
        for s in order[:left]:
            share_bps[s] += 1

    # ---------------------------------------------------------- artifacts
    os.makedirs(out_dir, exist_ok=True)

    def write_text(name, text):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write(text)

    def write_json(name, obj):
        write_text(name, json.dumps(obj, indent=2, sort_keys=True) + "\n")

    def table(name, header, rows, delim):
        lines = [delim.join(header)]
        lines.extend(delim.join(str(c) for c in row) for row in rows)
        write_text(name, "\n".join(lines) + "\n")

    def q(value):
        return fmt(value, quant_dp)

    table("population.csv",
          ["match_key", "account_id", "stratum", "drawn", "loot_currency",
           "anchor_date"],
          [[population[k]["match_key"], population[k]["account_id"],
            population[k]["stratum"], population[k]["drawn"],
            population[k]["loot_currency"], population[k]["anchor_date"]]
           for k in pop_keys], ",")

    table("weights.csv",
          ["match_key", "stratum", "y", "yhat", "loot_currency", "ledger_units",
           "p_eff", "p_cal", "weight"],
          [[k, population[k]["stratum"], population[k]["y"], population[k]["yhat"],
            population[k]["loot_currency"], population[k]["ledger_units"],
            fmt(population[k]["p_eff"], prob_dp),
            fmt(population[k]["p_cal"], prob_dp),
            q(population[k]["weight"])] for k in weighted_keys], ",")

    payout_rows = [[s, rewarded[s], forfeited[s], review[s], levy[s], net[s]]
                   for s in strata_order]
    payout_rows.append(["TOTAL", sum(rewarded.values()), sum(forfeited.values()),
                        sum(review.values()), sum(levy.values()), sum(net.values())])
    table("payout.csv",
          ["stratum", "rewarded_credits", "forfeited_credits", "review_credits",
           "levy_credits", "net_credits"], payout_rows, ",")

    table("payout_breakdown.tsv",
          ["stratum", "rewarded_credits", "forfeited_credits"],
          [[s, rewarded[s], forfeited[s]] for s in strata_order], "\t")

    table("payout_ledger.psv",
          ["stratum", "review_credits", "levy_credits", "net_credits"],
          [[s, review[s], levy[s], net[s]] for s in strata_order], "|")

    table("forfeited_shares.csv", ["stratum", "forfeited_credits", "share_bps"],
          [[s, forfeited[s], share_bps[s]] for s in strata_order], ",")

    table("confidence_intervals.csv",
          ["stratum", "recall_lo", "recall_hi", "prec_lo", "prec_hi",
           "n_eff_recall", "n_eff_precision"],
          [[s] + [q(v) for v in intervals[s]] for s in strata_order], ",")

    write_json("metrics.json", {
        "overall": {"precision": q(overall_p), "recall": q(overall_r),
                    "fbeta": q(overall_f), "macro_precision": q(macro_p),
                    "macro_recall": q(macro_r)},
        "strata": {s: {"precision": q(precision[s]), "recall": q(recall[s]),
                       "fbeta": q(fbeta[s])} for s in strata_order},
    })

    for s in strata_order:
        write_json(slugs[s], {
            "stratum": s, "precision": q(precision[s]), "recall": q(recall[s]),
            "fbeta": q(fbeta[s]), "tp": q(tp[s]), "fp": q(fp[s]), "fn": q(fn[s]),
        })

    write_text("stratum_metrics_stream.jsonl", "".join(
        json.dumps({"stratum": s, "precision": q(precision[s]),
                    "recall": q(recall[s]), "fbeta": q(fbeta[s])},
                   sort_keys=True) + "\n" for s in strata_order))

    write_text("overall_metrics.md", "# Overall Settled Metrics\n\n" + "".join(
        "- %s: %s\n" % pair for pair in [
            ("precision", q(overall_p)), ("recall", q(overall_r)),
            ("fbeta", q(overall_f)), ("macro_precision", q(macro_p)),
            ("macro_recall", q(macro_r))]))

    write_text("reconciliation_report.md",
               "# Settlement Reconciliation Report\n\n" + "".join(
                   "- %s: %s\n" % pair for pair in [
                       ("population", len(pop_keys)),
                       ("resolved", len(resolved_keys)),
                       ("weighted", len(weighted_keys)),
                       ("total_net_credits", sum(net.values())),
                       ("calibration_version", calib_version)]))

    rollup = ['<?xml version="1.0" encoding="UTF-8"?>', "<rollup>"]
    for s in strata_order:
        rollup.append('  <stratum id="%s">' % s)
        rollup.append("    <precision>%s</precision>" % q(precision[s]))
        rollup.append("    <recall>%s</recall>" % q(recall[s]))
        rollup.append("    <fbeta>%s</fbeta>" % q(fbeta[s]))
        rollup.append("  </stratum>")
    rollup.append("</rollup>")
    write_text("rollup.xml", "\n".join(rollup) + "\n")

    n_pos = sum(1 for k in resolved_keys if population[k]["y"] == 1)
    write_json("label_distribution.json", {
        "positive": n_pos, "negative": len(resolved_keys) - n_pos,
        "resolved_total": len(resolved_keys), "population_total": len(pop_keys)})

    flagged = sum(1 for k in weighted_keys if population[k]["yhat"] == 1)
    write_json("decision_distribution.json", {
        "flagged": flagged, "cleared": len(weighted_keys) - flagged,
        "weighted_total": len(weighted_keys)})

    write_json("frame_counts.json", {
        "population_by_stratum": {s: pop_by_stratum.get(s, 0) for s in strata_order},
        "sampled_by_stratum": {s: sampled_by_stratum.get(s, 0) for s in strata_order},
        "resolved_weighted": {s: len(weighted_by_stratum.get(s, []))
                              for s in strata_order}})

    max_w = max((population[k]["weight"] for k in weighted_keys), default=Fraction(0))
    write_json("weight_diagnostics.json", {
        "weight_sum_by_stratum": {s: q(wsum[s]) for s in strata_order},
        "cap": weight_cap, "max_weight": q(max_w)})

    write_json("net_payout_summary.json", {
        "total_rewarded_credits": sum(rewarded.values()),
        "total_forfeited_credits": sum(forfeited.values()),
        "total_review_credits": sum(review.values()),
        "total_levy_credits": sum(levy.values()),
        "total_net_credits": sum(net.values()),
        "by_stratum": {s: net[s] for s in strata_order}})

    write_json("levy_summary.json", {
        "levy_bps": levy_bps, "settlement_floor": floor_credits,
        "total_levy_credits": sum(levy.values()),
        "levy_by_stratum": {s: levy[s] for s in strata_order},
        "floored_strata": sorted(floored)})

    write_json("audit_summary.json", {
        "population": len(pop_keys), "resolved": len(resolved_keys),
        "weighted": len(weighted_keys), "flagged": flagged,
        "overall_fbeta": q(overall_f), "calibration_version": calib_version})

    core = ["population.csv", "weights.csv", "payout.csv", "metrics.json"]
    digest = hashlib.sha256()
    for name in core:
        with open(os.path.join(out_dir, name), "rb") as fh:
            digest.update(fh.read())
    write_json("manifest.json",
               {"core_order": core, "digest_sha256": digest.hexdigest()})


def main(argv):
    if len(argv) != 3:
        print("usage: settle.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    settle(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
