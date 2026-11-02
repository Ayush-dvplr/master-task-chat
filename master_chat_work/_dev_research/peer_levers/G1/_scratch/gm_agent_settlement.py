#!/usr/bin/env python3
"""Quarterly arena-ladder season settlement (2026S2).

Recomputes the corrected settlement from /Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/peer_levers/G1/_scratch/gm_corpus per the written contract
(00_pipeline_contract_overview.md and spec_stage_s1..s9), stdlib only.
"""
import csv
import datetime
import hashlib
import json
import math
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_EVEN, getcontext

getcontext().prec = 60

DATA = "/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/peer_levers/G1/_scratch/gm_corpus"
OUT = "/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/peer_levers/G1/_scratch/gm_agent_out"

STRATA = [
    "BRONZE-NA", "BRONZE-EU", "BRONZE-APAC",
    "SILVER-NA", "SILVER-EU", "SILVER-APAC",
    "GOLD-NA", "GOLD-EU", "GOLD-APAC",
]
SLUGS = {
    "BRONZE-NA": "metrics_bro_na.json", "BRONZE-EU": "metrics_bro_eu.json",
    "BRONZE-APAC": "metrics_bro_ap.json", "SILVER-NA": "metrics_sil_na.json",
    "SILVER-EU": "metrics_sil_eu.json", "SILVER-APAC": "metrics_sil_ap.json",
    "GOLD-NA": "metrics_gld_na.json", "GOLD-EU": "metrics_gld_eu.json",
    "GOLD-APAC": "metrics_gld_ap.json",
}
Q6 = Decimal("0.000001")
Q8 = Decimal("0.00000001")
XLNS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
WNS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def d(path):
    return os.path.join(DATA, path)


def rhe(x):
    """Round half-to-even to an integer."""
    return int(Decimal(x).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))


def q6(x):
    return Decimal(x).quantize(Q6, rounding=ROUND_HALF_EVEN)


def q8(x):
    return Decimal(x).quantize(Q8, rounding=ROUND_HALF_EVEN)


def s6(x):
    return str(q6(x))


def s8(x):
    return str(q8(x))


def iso(x):
    return datetime.date.fromisoformat(x)


# ---------------------------------------------------------------- constants
def live_sheet_params():
    """a_s/b_s/tau_s/recovery_s and the ore gain from the LIVE workbook sheet."""
    season = json.load(open(d("season_profile.json")))
    want = season["calibration_version"]
    z = zipfile.ZipFile(d("ladder_tuning_grid.xlsx"))
    sheets = sorted(n for n in z.namelist()
                    if n.startswith("xl/worksheets/sheet"))
    for name in sheets:
        grid = {}
        for row in ET.fromstring(z.read(name)).iter(XLNS + "row"):
            for c in row.iter(XLNS + "c"):
                grid[c.get("r")] = "".join(t.text or "" for t in c.iter(XLNS + "t"))
        if grid.get("B1") != want:
            continue
        cols = {}
        for col in "BCDEFGHIJ":
            cols[grid[col + "6"]] = col
        params = {}
        for st in STRATA:
            col = cols[st]
            params[st] = {
                "a": float(grid[col + "7"]),
                "b": float(grid[col + "8"]),
                "tau": float(grid[col + "9"]),
                "recovery": Decimal(grid[col + "10"]),
            }
        return params, Decimal(grid["B4"]), want
    raise SystemExit("live sheet not found")


def policy_constants():
    """Review unit cost, F-beta beta and CI z from the policy PDF only."""
    import zlib
    raw = open(d("payout_cost_policy.pdf"), "rb").read()
    text = []
    for body in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.S):
        try:
            body = zlib.decompress(body)
        except Exception:
            pass
        for m in re.findall(rb"\(((?:\\.|[^\\()])*)\)\s*Tj", body):
            text.append(m.decode("latin-1"))
    blob = "\n".join(text)
    cost = int(re.search(r"unit cost is (\d+) credits", blob).group(1))
    beta = Decimal(re.search(r"beta = ([0-9.]+)", blob).group(1))
    zval = float(re.search(r"z = ([0-9]+\.[0-9]+)", blob).group(1))
    return cost, beta, zval


def levy_constants():
    """Levy basis points and settlement floor from the addendum DOCX only."""
    z = zipfile.ZipFile(d("settlement_levy_addendum.docx"))
    paras = ["".join(t.text or "" for t in p.iter(WNS + "t"))
             for p in ET.fromstring(z.read("word/document.xml")).iter(WNS + "p")]
    blob = "\n".join(paras)
    bps = int(re.search(r"levy of (\d+) basis points", blob).group(1))
    floor = int(re.search(r"floored at (\d+) credits", blob).group(1))
    return bps, floor


# ------------------------------------------------------------------ S1 / S2
def load_capture():
    rows = list(csv.DictReader(open(d("ladder_match_capture_s1.csv"))))
    by_key = defaultdict(list)
    for r in rows:
        key = "|".join((r["account_id"], r["hero_handle"], r["seed_hash"],
                        r["ladder_split"]))
        r["match_key"] = key
        r["checkpoint_no"] = int(r["checkpoint_no"])
        by_key[key].append(r)
    return by_key


def load_draw():
    draw = {}
    with open(d("cohort_draw_register.psv")) as fh:
        next(fh)
        for line in fh:
            m = re.match(r'^"(.*)"\|([^|]+)\|(\d+)\s*$', line)
            draw[m.group(1)] = (m.group(2), int(m.group(3)))
    return draw


def load_verdicts():
    vh = defaultdict(list)
    for r in csv.DictReader(open(d("verdict_amendment_history.tsv")),
                            delimiter="\t"):
        vh[r["match_key"]].append(r)
    return vh


def load_drift():
    drift = defaultdict(dict)
    for r in csv.DictReader(open(d("season_patch_reference.csv"))):
        drift[r["unit_family"]][iso(r["ref_date"])] = Decimal(r["drift_mult"])
    return drift


def main():
    season = json.load(open(d("season_profile.json")))
    window_days = int(season["window_days"])
    backfill_days = int(season["drift_backfill_days"])
    base_p = Decimal(season["base_p"])
    cap = Decimal(season["weight_cap"])
    exps = json.load(open(d("unit_scale_exponents.json")))["scale_exponents"]
    crosswalk = json.load(open(d("verdict_crosswalk.json")))
    params, ore_gain, calib_version = live_sheet_params()
    review_cost, beta, zval = policy_constants()
    levy_bps, floor = levy_constants()
    max_trim_iter = json.load(open(d("weighting_constants.json")))["max_trim_iterations"]

    by_key = load_capture()
    draw = load_draw()
    vh = load_verdicts()
    drift = load_drift()

    # S1: one canonical row per key, highest checkpoint_no among SEALED rows;
    # keys that never sealed are dropped from the population entirely.
    population = {}
    for key, attempts in by_key.items():
        sealed = [r for r in attempts if r["seal_status"] == "SEALED"]
        if not sealed:
            continue
        canonical = max(sealed, key=lambda r: r["checkpoint_no"])
        first = min(attempts, key=lambda r: r["checkpoint_no"])
        stratum, drawn = draw[key]
        population[key] = {
            "match_key": key,
            "account_id": canonical["account_id"],
            "stratum": stratum,
            "server": stratum.split("-", 1)[1],
            "drawn": drawn,
            "loot_currency": canonical["loot_currency"],
            "raw_loot": Decimal(canonical["raw_loot"]),
            "p_raw": Decimal(canonical["p_raw"]),
            # S2: anchor on the FIRST attempt's epoch, not the canonical row.
            "anchor_date": first["match_epoch"],
        }

    # S2: resolve the adjudicated verdict inside the maturation window by
    # review_seq (amended_at is backfilled); map through the crosswalk.
    resolved = {}
    for key, rec in population.items():
        anchor = iso(rec["anchor_date"])
        cand = [r for r in vh.get(key, [])
                if 0 <= (iso(r["effective_at"]) - anchor).days <= window_days]
        rec["verdict"] = None
        if cand:
            cand.sort(key=lambda r: int(r["review_seq"]))
            rec["verdict"] = cand[-1]["verdict"]
        label = crosswalk.get(rec["verdict"], "excluded") if rec["verdict"] else "excluded"
        rec["label"] = label
        if label in ("positive", "negative"):
            rec["y"] = 1 if label == "positive" else 0
            resolved[key] = rec

    # S3: single running baseline per frozen stratum, ascending match_key.
    lo, hi = Decimal("0.000001"), Decimal("0.999999")
    for stratum in STRATA:
        baseline = base_p
        for key in sorted(k for k, r in resolved.items() if r["stratum"] == stratum):
            rec = resolved[key]
            p_raw = min(max(rec["p_raw"], lo), hi)
            p_eff = min(max(Decimal("0.85") * p_raw + Decimal("0.15") * baseline, lo), hi)
            rec["p_eff"] = p_eff
            baseline = p_eff

    # S4: ledger units (currency exponent, ore gain from the LIVE sheet, then
    # the drift multiplier dated on or before the anchor within the window).
    for rec in population.values():
        cur = rec["loot_currency"]
        if cur == "ORE":
            scaled = rec["raw_loot"] * ore_gain
        else:
            scaled = rec["raw_loot"] * (Decimal(10) ** int(exps[cur]))
        anchor = iso(rec["anchor_date"])
        mult = None
        for back in range(backfill_days + 1):
            mult = drift[cur].get(anchor - datetime.timedelta(days=back))
            if mult is not None:
                break
        rec["drift_gap"] = mult is None
        rec["ledger_units"] = None if mult is None else rhe(scaled * mult)

    # S5: two-level rarity weights on different partitions.
    pop_by_stratum = {s: 0 for s in STRATA}
    sampled_by_stratum = {s: 0 for s in STRATA}
    sampled_by_server = defaultdict(int)
    resolved_by_server = defaultdict(int)
    for rec in population.values():
        pop_by_stratum[rec["stratum"]] += 1
        if rec["drawn"] == 1:
            sampled_by_stratum[rec["stratum"]] += 1
            sampled_by_server[rec["server"]] += 1
    for rec in resolved.values():
        resolved_by_server[rec["server"]] += 1

    weighted = {k: r for k, r in resolved.items() if r["drawn"] == 1}
    raw_w = {}
    for key, rec in weighted.items():
        base_rate = Decimal(pop_by_stratum[rec["stratum"]]) / Decimal(sampled_by_stratum[rec["stratum"]])
        nonresponse = Decimal(sampled_by_server[rec["server"]]) / Decimal(resolved_by_server[rec["server"]])
        raw_w[key] = base_rate * nonresponse

    # inflate first, then trim to the cap by mass-preserving redistribution
    for stratum in STRATA:
        keys = sorted(k for k in raw_w if weighted[k]["stratum"] == stratum)
        if not keys:
            continue
        total = sum(raw_w[k] for k in keys)
        for _ in range(max_trim_iter):
            over = [k for k in keys if raw_w[k] > cap]
            if not over:
                break
            excess = sum(raw_w[k] - cap for k in over)
            for k in over:
                raw_w[k] = cap
            under = [k for k in keys if raw_w[k] < cap]
            pool = sum(raw_w[k] for k in under)
            if not under or pool == 0:
                break
            for k in under:
                raw_w[k] += excess * raw_w[k] / pool
        # quantize to 6 decimals and give the stratum residue to the largest
        # weight, ties broken by smallest match_key
        target = q6(total)
        for k in keys:
            weighted[k]["weight"] = q6(raw_w[k])
        residue = target - sum(weighted[k]["weight"] for k in keys)
        if residue != 0:
            pick = sorted(keys, key=lambda k: (-raw_w[k], k))[0]
            weighted[pick]["weight"] += residue

    # S6: calibrate in log-odds space, decide with an inclusive threshold.
    for rec in weighted.values():
        p = float(rec["p_eff"])
        pr = params[rec["stratum"]]
        logit = math.log(p / (1.0 - p))
        z = pr["a"] + pr["b"] * logit
        p_cal = 1.0 / (1.0 + math.exp(-z))
        rec["p_cal"] = Decimal(repr(p_cal))
        rec["yhat"] = 1 if p_cal >= pr["tau"] else 0
        rec["margin"] = p_cal - pr["tau"]

    # S7: weighted metrics
    def fbeta(p, r):
        b2 = beta * beta
        den = b2 * p + r
        if den == 0:
            return Decimal(0)
        return (1 + b2) * p * r / den

    tp = {s: Decimal(0) for s in STRATA}
    fp = {s: Decimal(0) for s in STRATA}
    fn = {s: Decimal(0) for s in STRATA}
    wsum = {s: Decimal(0) for s in STRATA}
    for rec in weighted.values():
        s, w = rec["stratum"], rec["weight"]
        wsum[s] += w
        if rec["y"] == 1 and rec["yhat"] == 1:
            tp[s] += w
        elif rec["y"] == 0 and rec["yhat"] == 1:
            fp[s] += w
        elif rec["y"] == 1 and rec["yhat"] == 0:
            fn[s] += w

    prec = {}
    rec_ = {}
    fb = {}
    for s in STRATA:
        prec[s] = tp[s] / (tp[s] + fp[s]) if (tp[s] + fp[s]) > 0 else Decimal(0)
        rec_[s] = tp[s] / (tp[s] + fn[s]) if (tp[s] + fn[s]) > 0 else Decimal(0)
        fb[s] = fbeta(prec[s], rec_[s])

    TP, FP, FN = sum(tp.values()), sum(fp.values()), sum(fn.values())
    o_prec = TP / (TP + FP) if (TP + FP) > 0 else Decimal(0)
    o_rec = TP / (TP + FN) if (TP + FN) > 0 else Decimal(0)
    o_fb = fbeta(o_prec, o_rec)
    W = sum(wsum.values())
    macro_prec = sum(wsum[s] / W * prec[s] for s in STRATA) if W > 0 else Decimal(0)
    macro_rec = sum(wsum[s] / W * rec_[s] for s in STRATA) if W > 0 else Decimal(0)

    # S8: Wilson intervals on the Kish effective sample size
    def n_eff(ws):
        tot = sum(ws)
        sq = sum(w * w for w in ws)
        return (tot * tot / sq) if sq > 0 else Decimal(0)

    def wilson(p, n):
        if n <= 0:
            return Decimal(0), Decimal(0)
        pf, nf = float(p), float(n)
        den = 1.0 + zval * zval / nf
        centre = pf + zval * zval / (2 * nf)
        half = zval * math.sqrt(pf * (1 - pf) / nf + zval * zval / (4 * nf * nf))
        return Decimal(repr((centre - half) / den)), Decimal(repr((centre + half) / den))

    ci = {}
    for s in STRATA:
        pos = [r["weight"] for r in weighted.values()
               if r["stratum"] == s and r["y"] == 1]
        pred = [r["weight"] for r in weighted.values()
                if r["stratum"] == s and r["yhat"] == 1]
        nr, np_ = n_eff(pos), n_eff(pred)
        rlo, rhi = wilson(rec_[s], nr)
        plo, phi = wilson(prec[s], np_)
        ci[s] = (rlo, rhi, plo, phi, nr, np_)

    # S8/S9: payout (drift-gap rows leave the payout artifacts only)
    rewarded = {}
    forfeited = {}
    review = {}
    levy = {}
    net_pre = {}
    net = {}
    floored = []
    for s in STRATA:
        rows = [r for r in weighted.values()
                if r["stratum"] == s and not r["drift_gap"]]
        rew = sum(r["weight"] * Decimal(r["ledger_units"])
                  for r in rows if r["y"] == 1 and r["yhat"] == 1)
        rewarded[s] = rhe(rew * params[s]["recovery"])
        forfeited[s] = rhe(sum(r["weight"] * Decimal(r["ledger_units"])
                               for r in rows if r["y"] == 1 and r["yhat"] == 0))
        review[s] = rhe(sum(r["weight"] for r in rows if r["yhat"] == 1)
                        * Decimal(review_cost))
        net_pre[s] = rewarded[s] - review[s]
        levy[s] = rhe(Decimal(rewarded[s]) * Decimal(levy_bps) / Decimal(10000))
        post = net_pre[s] - levy[s]
        if post < floor:
            floored.append(s)
        net[s] = max(post, floor)

    # forfeited-credit basis-point shares, largest remainder to exactly 10000
    total_forf = sum(forfeited.values())
    share_bps = {s: 0 for s in STRATA}
    if total_forf > 0:
        exact = {s: Decimal(forfeited[s]) * 10000 / Decimal(total_forf) for s in STRATA}
        share_bps = {s: int(exact[s]) for s in STRATA}
        left = 10000 - sum(share_bps.values())
        order = sorted(STRATA, key=lambda s: (-(exact[s] - int(exact[s])),
                                              STRATA.index(s)))
        for s in order[:left]:
            share_bps[s] += 1

    # ------------------------------------------------------------- artifacts
    os.makedirs(OUT, exist_ok=True)

    def write(name, text):
        with open(os.path.join(OUT, name), "w", encoding="utf-8",
                  newline="") as fh:
            fh.write(text)

    def write_json(name, obj):
        write(name, json.dumps(obj, indent=2, sort_keys=True) + "\n")

    pop_keys = sorted(population)
    lines = ["match_key,account_id,stratum,drawn,loot_currency,anchor_date"]
    for k in pop_keys:
        r = population[k]
        lines.append(",".join([k, r["account_id"], r["stratum"],
                               str(r["drawn"]), r["loot_currency"],
                               r["anchor_date"]]))
    write("population.csv", "\n".join(lines) + "\n")

    wkeys = sorted(weighted)
    lines = ["match_key,stratum,y,yhat,loot_currency,ledger_units,p_eff,p_cal,weight"]
    for k in wkeys:
        r = weighted[k]
        lines.append(",".join([
            k, r["stratum"], str(r["y"]), str(r["yhat"]), r["loot_currency"],
            "" if r["drift_gap"] else str(r["ledger_units"]),
            s8(r["p_eff"]), s8(r["p_cal"]), s6(r["weight"])]))
    write("weights.csv", "\n".join(lines) + "\n")

    lines = ["stratum,rewarded_credits,forfeited_credits,review_credits,levy_credits,net_credits"]
    for s in STRATA:
        lines.append(",".join([s, str(rewarded[s]), str(forfeited[s]),
                               str(review[s]), str(levy[s]), str(net[s])]))
    lines.append(",".join(["TOTAL", str(sum(rewarded.values())),
                           str(sum(forfeited.values())),
                           str(sum(review.values())), str(sum(levy.values())),
                           str(sum(net.values()))]))
    write("payout.csv", "\n".join(lines) + "\n")

    metrics = {
        "overall": {
            "precision": s6(o_prec), "recall": s6(o_rec), "fbeta": s6(o_fb),
            "macro_precision": s6(macro_prec), "macro_recall": s6(macro_rec),
        },
        "strata": {s: {"precision": s6(prec[s]), "recall": s6(rec_[s]),
                       "fbeta": s6(fb[s])} for s in STRATA},
    }
    write_json("metrics.json", metrics)

    digest = hashlib.sha256()
    for name in ("population.csv", "weights.csv", "payout.csv", "metrics.json"):
        digest.update(open(os.path.join(OUT, name), "rb").read())
    write_json("manifest.json", {
        "core_order": ["population.csv", "weights.csv", "payout.csv",
                       "metrics.json"],
        "digest_sha256": digest.hexdigest(),
    })

    write_json("levy_summary.json", {
        "levy_bps": levy_bps,
        "settlement_floor": floor,
        "total_levy_credits": sum(levy.values()),
        "levy_by_stratum": {s: levy[s] for s in STRATA},
        "floored_strata": sorted(floored),
    })

    for s in STRATA:
        write_json(SLUGS[s], {
            "stratum": s, "precision": s6(prec[s]), "recall": s6(rec_[s]),
            "fbeta": s6(fb[s]), "tp": s6(tp[s]), "fp": s6(fp[s]),
            "fn": s6(fn[s]),
        })

    lines = ["stratum\trewarded_credits\tforfeited_credits"]
    for s in STRATA:
        lines.append("\t".join([s, str(rewarded[s]), str(forfeited[s])]))
    write("payout_breakdown.tsv", "\n".join(lines) + "\n")

    lines = ["stratum|review_credits|levy_credits|net_credits"]
    for s in STRATA:
        lines.append("|".join([s, str(review[s]), str(levy[s]), str(net[s])]))
    write("payout_ledger.psv", "\n".join(lines) + "\n")

    lines = ["stratum,forfeited_credits,share_bps"]
    for s in STRATA:
        lines.append(",".join([s, str(forfeited[s]), str(share_bps[s])]))
    write("forfeited_shares.csv", "\n".join(lines) + "\n")

    lines = ["stratum,recall_lo,recall_hi,prec_lo,prec_hi,n_eff_recall,n_eff_precision"]
    for s in STRATA:
        lines.append(",".join([s] + [s6(v) for v in ci[s]]))
    write("confidence_intervals.csv", "\n".join(lines) + "\n")

    stream = [json.dumps({"stratum": s, "precision": s6(prec[s]),
                          "recall": s6(rec_[s]), "fbeta": s6(fb[s])},
                         sort_keys=True) for s in STRATA]
    write("stratum_metrics_stream.jsonl", "\n".join(stream) + "\n")

    write("overall_metrics.md", "# Overall Settled Metrics\n\n" + "".join(
        "- %s: %s\n" % (n, v) for n, v in [
            ("precision", s6(o_prec)), ("recall", s6(o_rec)),
            ("fbeta", s6(o_fb)), ("macro_precision", s6(macro_prec)),
            ("macro_recall", s6(macro_rec))]))

    write("reconciliation_report.md",
          "# Settlement Reconciliation Report\n\n" + "".join(
              "- %s: %s\n" % (n, v) for n, v in [
                  ("population", len(population)), ("resolved", len(resolved)),
                  ("weighted", len(weighted)),
                  ("total_net_credits", sum(net.values())),
                  ("calibration_version", calib_version)]))

    xml = ['<?xml version="1.0" encoding="UTF-8"?>', "<rollup>"]
    for s in STRATA:
        xml.append('  <stratum id="%s">' % s)
        xml.append("    <precision>%s</precision>" % s6(prec[s]))
        xml.append("    <recall>%s</recall>" % s6(rec_[s]))
        xml.append("    <fbeta>%s</fbeta>" % s6(fb[s]))
        xml.append("  </stratum>")
    xml.append("</rollup>")
    write("rollup.xml", "\n".join(xml) + "\n")

    write_json("label_distribution.json", {
        "positive": sum(1 for r in resolved.values() if r["y"] == 1),
        "negative": sum(1 for r in resolved.values() if r["y"] == 0),
        "resolved_total": len(resolved),
        "population_total": len(population),
    })

    flagged = sum(1 for r in weighted.values() if r["yhat"] == 1)
    write_json("decision_distribution.json", {
        "flagged": flagged,
        "cleared": len(weighted) - flagged,
        "weighted_total": len(weighted),
    })

    write_json("frame_counts.json", {
        "population_by_stratum": {s: pop_by_stratum[s] for s in STRATA},
        "sampled_by_stratum": {s: sampled_by_stratum[s] for s in STRATA},
        "resolved_weighted": {s: sum(1 for r in weighted.values()
                                     if r["stratum"] == s) for s in STRATA},
    })

    write_json("weight_diagnostics.json", {
        "weight_sum_by_stratum": {s: s6(wsum[s]) for s in STRATA},
        "cap": str(int(cap)),
        "max_weight": s6(max((r["weight"] for r in weighted.values()),
                             default=Decimal(0))),
    })

    write_json("net_payout_summary.json", {
        "total_rewarded_credits": sum(rewarded.values()),
        "total_forfeited_credits": sum(forfeited.values()),
        "total_review_credits": sum(review.values()),
        "total_levy_credits": sum(levy.values()),
        "total_net_credits": sum(net.values()),
        "by_stratum": {s: net[s] for s in STRATA},
    })

    write_json("audit_summary.json", {
        "population": len(population),
        "resolved": len(resolved),
        "weighted": len(weighted),
        "flagged": flagged,
        "overall_fbeta": s6(o_fb),
        "calibration_version": calib_version,
    })

    print("population", len(population), "resolved", len(resolved),
          "weighted", len(weighted), "flagged", flagged)
    print("ore_gain", ore_gain, "cost", review_cost, "beta", beta, "z", zval,
          "levy_bps", levy_bps, "floor", floor)
    print("weights", {s: str(wsum[s]) for s in STRATA})
    print("net", {s: net[s] for s in STRATA}, "floored", floored)
    print("overall", metrics["overall"])


if __name__ == "__main__":
    main()
