#!/usr/bin/env python3
"""Year-end 2032 reserving run.

Reads the flat corpus handed to it on --data and writes the nine documents
fixed by ``output_contract.md`` into --out.  Every rule, bound, factor and
vocabulary is loaded from the corpus at run time; nothing is hardcoded.
"""

import argparse
import configparser
import csv
import glob
import json
import os
import re
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN, getcontext

getcontext().prec = 40

ONE = Decimal(1)


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def half_up(value):
    return int(Decimal(value).quantize(ONE, rounding=ROUND_HALF_UP))


def half_even(value):
    return int(Decimal(value).quantize(ONE, rounding=ROUND_HALF_EVEN))


def q6(value):
    return Decimal(value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


class Corpus:
    """Read-only access to the data directory with fail-fast on absence."""

    def __init__(self, data_dir):
        self.dir = data_dir
        if not os.path.isdir(data_dir):
            raise FileNotFoundError("data directory not found: %s" % data_dir)

    def path(self, name):
        p = os.path.join(self.dir, name)
        if not os.path.isfile(p):
            raise FileNotFoundError("required source file missing: %s" % name)
        return p

    def text(self, name):
        with open(self.path(name), "r", encoding="utf-8") as fh:
            return fh.read()

    def lines(self, name, encoding="utf-8"):
        with open(self.path(name), "r", encoding=encoding) as fh:
            return fh.read().split("\n")

    def rows(self, name, delimiter=",", encoding="utf-8"):
        """Positional rows: header list plus a list of data row lists."""
        with open(self.path(name), "r", encoding=encoding, newline="") as fh:
            parsed = list(csv.reader(fh, delimiter=delimiter))
        parsed = [r for r in parsed if r and any(c.strip() for c in r)]
        if not parsed:
            return [], []
        return parsed[0], parsed[1:]

    def table(self, name, delimiter=","):
        """Header-keyed rows honouring the leftmost-occurrence rule."""
        header, data = self.rows(name, delimiter=delimiter)
        first = {}
        for idx, col in enumerate(header):
            first.setdefault(col.strip(), idx)
        out = []
        for row in data:
            out.append({k: (row[i] if i < len(row) else "")
                        for k, i in first.items()})
        return out

    def glob(self, pattern):
        found = sorted(os.path.basename(p)
                       for p in glob.glob(os.path.join(self.dir, pattern)))
        if not found:
            raise FileNotFoundError("no source file matches %s" % pattern)
        return found

    def exists(self, name):
        return os.path.isfile(os.path.join(self.dir, name))


# --------------------------------------------------------------------------
# declarations and rule documents
# --------------------------------------------------------------------------

def load_declarations(cx):
    policy = configparser.ConfigParser()
    policy.read_string(cx.text("derivation_policy.ini"))
    units = configparser.ConfigParser()
    units.read_string(cx.text("unit_declarations.ini"))

    props = {}
    for line in cx.lines("source_declarations.properties"):
        if "=" in line and not line.strip().startswith("#"):
            key, val = line.split("=", 1)
            props[key.strip()] = val.strip()

    codes = json.loads(cx.text("reason_codes.json"))

    dec = {
        "valuation_instant": policy.get("horizon", "valuation_instant").strip(),
        "cutover_instant": policy.get("horizon", "cutover_instant").strip(),
        "pre_cutover": [s.strip() for s in
                        policy.get("precedence", "pre_cutover").split(",")],
        "post_cutover": [s.strip() for s in
                         policy.get("precedence", "post_cutover").split(",")],
        "dollar_scale": int(units.get("dollars", "scale")),
        "negatives": units.get("dollars", "negatives").strip(),
        "fw_width": int(props["fixed_width_intake.width"]),
        "fw_offsets": {},
        "codes": codes,
    }
    for spec in props["fixed_width_intake.offsets"].split(","):
        field, start, end = spec.split(":")
        dec["fw_offsets"][field.strip()] = (int(start), int(end))
    return dec


def load_rule_parameters(cx):
    """Pull every governing constant out of the rule documents."""
    rules = {}

    alae_doc = cx.text("alae_rules.md")
    cands = re.findall(r"candidate readings `([a-z0-9_]+)` and `([a-z0-9_]+)`",
                       alae_doc)
    if not cands:
        raise ValueError("alae_rules.md: candidate readings not declared")
    rules["alae_candidates"] = list(cands[0])

    disc_doc = cx.text("discounting_rules.md")
    cands = re.findall(r"candidate readings `([a-z0-9_]+)` and `([a-z0-9_]+)`",
                       disc_doc)
    if not cands:
        raise ValueError("discounting_rules.md: candidate readings not declared")
    rules["discount_candidates"] = list(cands[0])
    cl_doc = cx.text("chain_ladder_rules.md")
    m = re.search(r"clipped to the interval `\[\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\]`",
                  cl_doc)
    if not m:
        raise ValueError("chain_ladder_rules.md: clipping interval not declared")
    rules["clip_low"] = Decimal(m.group(1))
    rules["clip_high"] = Decimal(m.group(2))
    rules["factors_bounded"] = "[%s, %s]" % (m.group(1), m.group(2))
    m = re.search(r"rounded to (\w+) decimal places", cl_doc)
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
             "six": 6, "seven": 7, "eight": 8}
    rules["factor_decimals"] = words.get(m.group(1), 6) if m else 6

    att_doc = cx.text("attachment_rules.md")
    m = re.search(r"Clash cover \(per `([^`]+)`\)", att_doc)
    if not m:
        raise ValueError("attachment_rules.md: clash authority not declared")
    rules["attachment_authority"] = m.group(1)
    errata = cx.text(rules["attachment_authority"])
    m = re.search(r"identifier of this rule is\s*`([^`]+)`", errata)
    if not m:
        raise ValueError("%s: rule identifier not declared"
                         % rules["attachment_authority"])
    rules["attachment_rule"] = m.group(1)
    m = re.search(r"walked through the ceded path in exactly this order: (.+?)\.",
                  att_doc)
    rules["layer_path"] = (re.findall(r"`([a-z_]+)`", m.group(1)) if m
                           else ["retention", "working_excess", "cat_excess",
                                 "retro"])

    amend = cx.text("amendment_rules.md")
    m = re.search(r"lifts ALAE by `([0-9.]+)`", amend)
    if not m:
        raise ValueError("amendment_rules.md: cede_cap_raise ratio missing")
    rules["cede_cap_raise"] = Decimal(m.group(1))
    m = re.search(r"signed off iff its `(\w+)` appears in an `(\w+)` line", amend)
    rules["audit_verb"] = m.group(2) if m else "ENDORSE"

    cf = cx.text("counterfactual_parameters.md")
    m = re.search(r"added tenor is `([0-9]+)` years", cf)
    if not m:
        raise ValueError("counterfactual_parameters.md: added tenor missing")
    rules["cf_added_tenor"] = int(m.group(1))
    m = re.search(r"fixed increment of `([0-9.]+)` percentage points", cf)
    if not m:
        raise ValueError("counterfactual_parameters.md: increment missing")
    rules["cf_increment"] = Decimal(m.group(1))
    m = re.search(r"its `want` is multiplied by `([0-9.]+)`", cf)
    if not m:
        raise ValueError("counterfactual_parameters.md: retro multiplier missing")
    rules["cf_retro_multiplier"] = Decimal(m.group(1))
    m = re.search(r"records `layer=([a-z_]+)`", cf)
    rules["cf_retro_layer"] = m.group(1) if m else "cat_excess"
    m = re.search(r"A cycle `Hnn` sits `nn / ([0-9]+)` years out", cf)
    rules["cf_cycle_divisor"] = int(m.group(1)) if m else 2

    dq_doc = cx.text("data_quality_counting.md")
    m = re.search(r"positive whole multiple of one (\w+) dollars", dq_doc)
    blocks = {"thousand": 1000, "hundred": 100, "million": 1000000}
    rules["block_unit"] = blocks.get(m.group(1), 1000) if m else 1000
    return rules


def claim_tx_layout(cx):
    """Positional column layout of the claim transaction logs, as declared."""
    text = cx.text("source_manifest.md")
    layout = {}
    for idx, name in re.findall(r"^- column (\d+): `([A-Za-z_]+)`", text, re.M):
        layout.setdefault(name, int(idx))
    for needed in ("claim_ref", "reinsurer_id", "lob", "accident_year",
                   "paid_to_date", "incurred", "recorded_instant"):
        if needed not in layout:
            raise ValueError("source_manifest.md: column %s not declared" % needed)
    return layout


def required_files(cx):
    """Every file the corpus index declares, plus the index itself."""
    index_name = "corpus_index.md"
    names = re.findall(r"^- `([^`]+)`", cx.text(index_name), re.M)
    out = [index_name]
    for n in names:
        if n not in out:
            out.append(n)
    return out


# --------------------------------------------------------------------------
# dollar parsing
# --------------------------------------------------------------------------

PAREN_AMOUNT = re.compile(r"\((\d[\d,]*)\)")


def parse_dollars(raw, dec):
    text = (raw or "").strip().replace("$", "")
    if text == "":
        return 0
    negative = False
    m = PAREN_AMOUNT.fullmatch(text)
    if m and dec["negatives"] == "paren":
        negative = True
        text = m.group(1)
    elif text.startswith("-"):
        negative = True
        text = text[1:]
    text = text.replace(",", "")
    value = int(Decimal(text) * dec["dollar_scale"])
    return -value if negative else value


# --------------------------------------------------------------------------
# source ingestion
# --------------------------------------------------------------------------

def first_index(header, name):
    for idx, col in enumerate(header):
        if col.strip() == name:
            return idx
    raise ValueError("column %s absent from header" % name)


def load_sources(cx, dec, layout):
    """Return all source rows plus the raw-file tallies."""
    valuation = dec["valuation_instant"]
    rows = []
    late_rows = []
    restatement_gaps = 0
    tx_late_rows = []

    tx_files = cx.glob("claim_tx_H*.csv")
    enc_tx = "utf-8"
    for order, name in enumerate(tx_files):
        header, data = cx.rows(name, encoding=enc_tx)
        i_ref = layout["claim_ref"]
        i_rid = layout["reinsurer_id"]
        i_lob = layout["lob"]
        i_ay = layout["accident_year"]
        i_paid = layout["paid_to_date"]
        i_inc = layout["incurred"]
        i_inst = layout["recorded_instant"]
        i_rest = layout.get("paid_to_date_restated", -1)
        for pos, row in enumerate(data):
            paid = parse_dollars(row[i_paid], dec)
            if 0 <= i_rest < len(row) and row[i_rest].strip() != "":
                if parse_dollars(row[i_rest], dec) != paid:
                    restatement_gaps += 1
            rec = {
                "source": "claim_tx",
                "file": name,
                "order": (order, pos),
                "claim_ref": row[i_ref].strip(),
                "reinsurer_id": row[i_rid].strip(),
                "lob": row[i_lob].strip(),
                "accident_year": row[i_ay].strip(),
                "paid_to_date": paid,
                "incurred": parse_dollars(row[i_inc], dec),
                "recorded_instant": row[i_inst].strip(),
            }
            if rec["recorded_instant"] > valuation:
                late_rows.append(rec)
                tx_late_rows.append(rec)
            else:
                rows.append(rec)

    for order, name in enumerate(cx.glob("cession_q*.tsv")):
        header, data = cx.rows(name, delimiter="\t")
        i_ref = first_index(header, "claim_ref")
        i_rid = first_index(header, "reinsurer_id")
        i_lob = first_index(header, "lob")
        i_ced = first_index(header, "ceded_dollars")
        i_inst = first_index(header, "recorded_instant")
        for pos, row in enumerate(data):
            rec = {
                "source": "cession",
                "file": name,
                "order": (order, pos),
                "claim_ref": row[i_ref].strip(),
                "reinsurer_id": row[i_rid].strip(),
                "lob": row[i_lob].strip(),
                "accident_year": "",
                "paid_to_date": parse_dollars(row[i_ced], dec),
                "incurred": None,
                "recorded_instant": row[i_inst].strip(),
            }
            if rec["recorded_instant"] > valuation:
                late_rows.append(rec)
            else:
                rows.append(rec)

    off = dec["fw_offsets"]
    block_unit_rows = 0
    for order, name in enumerate(cx.glob("fixed_width_intake_h*.txt")):
        for pos, line in enumerate(cx.lines(name)):
            if not line.strip():
                continue

            def field(key):
                start, end = off[key]
                return line[start:end].strip()

            paid = parse_dollars(field("paid_to_date"), dec)
            if paid > 0 and paid % 1000 == 0:
                block_unit_rows += 1
            rec = {
                "source": "fixed_width_intake",
                "file": name,
                "order": (order, pos),
                "claim_ref": field("claim_ref"),
                "reinsurer_id": field("reinsurer_id"),
                "lob": field("lob"),
                "accident_year": field("accident_year"),
                "paid_to_date": paid,
                "incurred": None,
                "recorded_instant": field("recorded_instant"),
            }
            if rec["recorded_instant"] > valuation:
                late_rows.append(rec)
            else:
                rows.append(rec)

    return {
        "rows": rows,
        "late_rows": late_rows,
        "tx_late_rows": tx_late_rows,
        "restatement_gaps": restatement_gaps,
        "block_unit_rows": block_unit_rows,
    }


def recount_block_units(cx, dec, rules):
    unit = rules["block_unit"]
    off = dec["fw_offsets"]
    start, end = off["paid_to_date"]
    total = 0
    for name in cx.glob("fixed_width_intake_h*.txt"):
        for line in cx.lines(name):
            if not line.strip():
                continue
            paid = parse_dollars(line[start:end], dec)
            if paid > 0 and paid % unit == 0:
                total += 1
    return total


def count_paren_negatives(cx):
    total = 0
    names = sorted(os.path.basename(p) for p in
                   glob.glob(os.path.join(cx.dir, "*.csv"))
                   + glob.glob(os.path.join(cx.dir, "*.tsv")))
    for name in names:
        for line in cx.lines(name):
            if PAREN_AMOUNT.search(line):
                total += 1
    return total


# --------------------------------------------------------------------------
# reinsurer resolution
# --------------------------------------------------------------------------

class ReinsurerBook:
    def __init__(self, cx):
        self.alias = {}
        for row in cx.table("reinsurer_alias_map.csv"):
            self.alias[row["alias"].strip().lower()] = row["canonical_id"].strip()
        self.boundaries = {}
        self.ids = []
        seen = {}
        for row in cx.table("reinsurer_master.csv"):
            rid = row["reinsurer_id"].strip()
            bound = row["epoch_boundary"].strip()
            seen.setdefault(rid, []).append(bound)
            if rid not in self.ids:
                self.ids.append(rid)
        for rid, bounds in seen.items():
            nonempty = sorted({b for b in bounds if b})
            if len(bounds) > 1 and nonempty:
                self.boundaries[rid] = nonempty[0]

    def base(self, raw):
        if raw is None:
            return None
        text = raw.strip()
        if text == "":
            return None
        if text in self.ids:
            return text
        key = text.lower()
        if key in self.alias and self.alias[key] in self.ids:
            return self.alias[key]
        collapsed = " ".join(key.split())
        if collapsed in self.alias and self.alias[collapsed] in self.ids:
            return self.alias[collapsed]
        return None

    def canonical(self, raw, instant):
        base = self.base(raw)
        if base is None:
            return None
        bound = self.boundaries.get(base)
        if bound and instant >= bound:
            return "%s#2" % base
        return "%s#1" % base


def strip_epoch(canonical):
    return canonical.split("#", 1)[0] if canonical else canonical


# --------------------------------------------------------------------------
# collapse stage
# --------------------------------------------------------------------------

def source_rank(source, instant, dec):
    order = (dec["pre_cutover"] if instant < dec["cutover_instant"]
             else dec["post_cutover"])
    name = source
    if name in order:
        return order.index(name)
    return len(order)


def collapse(rows, dec):
    by_claim = {}
    for rec in rows:
        by_claim.setdefault(rec["claim_ref"], []).append(rec)
    governing = {}
    stats = {"duplicate_identical": 0, "duplicate_conflicting": 0,
             "cross_source_collapsed": 0, "fold_disambiguated": 0}
    for ref in sorted(by_claim):
        group = by_claim[ref]
        if len(group) > 1:
            stats["cross_source_collapsed"] += 1
            paid_values = {r["paid_to_date"] for r in group}
            if len(paid_values) == 1:
                stats["duplicate_identical"] += 1
            else:
                stats["duplicate_conflicting"] += 1
                stats["fold_disambiguated"] += 1
        best = None
        best_key = None
        for rec in group:
            rank = source_rank(rec["source"], rec["recorded_instant"], dec)
            key = (rank, _desc(rec["recorded_instant"]), rec["source"],
                   rec["order"])
            if best_key is None or key < best_key:
                best_key = key
                best = rec
        governing[ref] = best
    return governing, stats


class _Desc:
    """Reverse-ordering wrapper so the later instant wins a tie."""

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        return self.value > other.value

    def __eq__(self, other):
        return self.value == other.value


def _desc(value):
    return _Desc(value)


# --------------------------------------------------------------------------
# cycle placement
# --------------------------------------------------------------------------

class CycleClock:
    def __init__(self, cx):
        self.cycles = []
        for row in cx.table("cycle_marks.csv"):
            self.cycles.append((row["cycle"].strip(),
                                row["start_instant"].strip(),
                                row["end_instant"].strip()))
        self.cycles.sort(key=lambda c: (c[1], c[0]))
        self.codes = [c[0] for c in self.cycles]

    def place(self, instant):
        """Return (cycle, shifted) for an instant."""
        for code, start, end in self.cycles:
            if start <= instant <= end:
                return code, False
        for code, start, end in self.cycles:
            if start > instant:
                return code, True
        return self.cycles[-1][0], True


# --------------------------------------------------------------------------
# observation-log settlements
# --------------------------------------------------------------------------

def parse_kv_log(lines):
    out = []
    for line in lines:
        if not line.strip():
            continue
        parts = line.split()
        fields = {}
        plain = []
        for token in parts:
            if "=" in token:
                key, val = token.split("=", 1)
                fields[key] = val
            else:
                plain.append(token)
        out.append((plain, fields))
    return out


def load_adjustments(cx, dec):
    """claim_ref -> list of adjustment observations in file order."""
    records = []
    for plain, fields in parse_kv_log(cx.lines("claim_adjustment_log.log")):
        if "alae" not in fields or "settled" not in fields:
            continue
        ref = None
        for token in plain[1:] if len(plain) > 1 else plain:
            if token.startswith("CLM-"):
                ref = token
        if ref is None:
            continue
        records.append({
            "instant": plain[0] if plain else "",
            "claim_ref": ref,
            "gross": parse_dollars(fields.get("gross", "0"), dec),
            "alae": parse_dollars(fields["alae"], dec),
            "settled": parse_dollars(fields["settled"], dec),
            "layer": fields.get("layer", "").strip(),
        })
    by_claim = {}
    for rec in records:
        by_claim.setdefault(rec["claim_ref"], []).append(rec)
    return records, by_claim


def fit_alae_fraction(records):
    ratios = []
    for rec in records:
        if rec["settled"] > 0:
            ratios.append(Decimal(rec["alae"]) / Decimal(rec["settled"]))
    if not ratios:
        raise ValueError("claim_adjustment_log.log carries no settled rows")
    for places in range(1, 9):
        step = Decimal(1).scaleb(-places)
        candidates = sorted({r.quantize(step, rounding=ROUND_HALF_UP)
                             for r in ratios})
        fits = []
        for cand in candidates:
            ok = True
            for rec in records:
                if rec["settled"] <= 0:
                    continue
                predicted = half_up(cand * Decimal(rec["settled"]))
                if abs(predicted - rec["alae"]) > 1:
                    ok = False
                    break
            if ok:
                fits.append(cand)
        if fits:
            return fits[0]
    raise ValueError("no ALAE fraction fits every observation")


def settle_alae_convention(records, candidates, fraction):
    """Enumerate the declared candidate readings against every observation."""
    survivors = []
    for name in candidates:
        ok = True
        for rec in records:
            if name == "pro_rata":
                predicted = half_up(fraction * Decimal(rec["settled"]))
                if abs(predicted - rec["alae"]) > 1:
                    ok = False
            elif name == "excess_only":
                if rec["layer"] == "retention":
                    if rec["alae"] != 0:
                        ok = False
                else:
                    if rec["alae"] <= 0:
                        ok = False
            else:
                ok = False
            if not ok:
                break
        if ok:
            survivors.append(name)
    if len(survivors) != 1:
        raise ValueError("ALAE convention not settled uniquely: %r" % survivors)
    return survivors[0]


def load_curve(cx):
    curve = {}
    for row in cx.table("curve_marks.csv"):
        curve[int(row["tenor_years"])] = Decimal(row["yield_pct"].strip())
    if not curve:
        raise ValueError("curve_marks.csv carries no marks")
    return curve


def curve_rate(curve, years):
    tenors = sorted(curve)
    years = Decimal(years)
    if years <= tenors[0]:
        return curve[tenors[0]]
    if years >= tenors[-1]:
        return curve[tenors[-1]]
    for lo, hi in zip(tenors, tenors[1:]):
        if lo <= years <= hi:
            if years == lo:
                return curve[lo]
            span = Decimal(hi - lo)
            weight = (years - Decimal(lo)) / span
            return curve[lo] + (curve[hi] - curve[lo]) * weight
    return curve[tenors[-1]]


def pv_factor(rate, years):
    base = ONE + Decimal(rate) / Decimal(100)
    return q6(ONE / (base ** Decimal(years)) if years else ONE)


def settle_discount_curve(cx, curve, candidates):
    observations = []
    for plain, fields in parse_kv_log(cx.lines("treasury_curve_observations.log")):
        if "tenor" not in fields or "pv_factor" not in fields:
            continue
        observations.append((
            Decimal(re.sub(r"[^0-9.]", "", fields["tenor"])),
            Decimal(fields["observed"]),
            Decimal(fields["pv_factor"]),
        ))
    if not observations:
        raise ValueError("treasury_curve_observations.log carries no marks")
    tolerance = Decimal("0.0001")
    scores = {}
    for name in candidates:
        misses = 0
        for tenor, observed, shown in observations:
            if name == "flat_10y":
                anchor = max(curve)
                rate = curve[anchor]
            elif name == "duration_matched":
                rate = observed
            else:
                misses = len(observations)
                break
            predicted = ONE / ((ONE + rate / Decimal(100)) ** tenor)
            if abs(predicted - shown) > tolerance:
                misses += 1
        scores[name] = misses
    survivors = [n for n in candidates if scores.get(n, 1) == 0]
    if len(survivors) != 1:
        raise ValueError("discount curve not settled uniquely: %r" % survivors)
    return survivors[0]


# --------------------------------------------------------------------------
# endorsement circulars
# --------------------------------------------------------------------------

def load_endorsements(cx, rules, valuation):
    circulars = []
    for name in cx.glob("endorsement_circulars_p*.jsonl"):
        for line in cx.lines(name):
            if not line.strip():
                continue
            circ = json.loads(line)
            if circ.get("recorded_instant", "") > valuation:
                continue
            circulars.append(circ)

    audit_files = [n for n in cx.glob("endorsement_audit.log*")]
    base = "endorsement_audit.log"
    continuations = len([n for n in audit_files if n != base])
    signed = set()
    audit_entries = 0
    for name in sorted(audit_files):
        for line in cx.lines(name):
            if not line.strip():
                continue
            tokens = line.split()
            if tokens and tokens[0] > valuation and tokens[0][:2].isdigit():
                continue
            audit_entries += 1
            if rules["audit_verb"] not in tokens:
                continue
            for token in tokens:
                if token.startswith("claim="):
                    signed.add(token.split("=", 1)[1])

    authority = set()
    for row in cx.table("authority_roles.csv"):
        authority.add((row["underwriter_id"].strip(), row["lob"].strip()))

    counted, dropped = [], []
    for circ in circulars:
        ok_sign = circ.get("claim_ref") in signed
        ok_auth = (circ.get("underwriter", "").strip(),
                   circ.get("lob", "").strip()) in authority
        (counted if (ok_sign and ok_auth) else dropped).append(circ)
    return {
        "circulars": circulars,
        "counted": counted,
        "dropped": dropped,
        "audit_entries": audit_entries,
        "log_continuations": continuations,
    }


# --------------------------------------------------------------------------
# chain ladder
# --------------------------------------------------------------------------

def accident_year_int(text):
    digits = re.sub(r"[^0-9]", "", text or "")
    return int(digits) if digits else None


def instant_year(instant):
    return int(instant[:4])


def chain_ladder_factors(rows, rules):
    sums = {}
    for rec in rows:
        if rec["source"] != "claim_tx":
            continue
        ay = accident_year_int(rec["accident_year"])
        if ay is None:
            continue
        dev = instant_year(rec["recorded_instant"]) - ay
        if dev < 0:
            dev = 0
        acc = sums.setdefault(dev, [0, 0])
        acc[0] += rec["incurred"] or 0
        acc[1] += rec["paid_to_date"]
    factors = {}
    step = Decimal(1).scaleb(-rules["factor_decimals"])
    for dev, (inc, paid) in sums.items():
        if paid == 0:
            value = ONE
        else:
            value = Decimal(inc) / Decimal(paid)
        if value < rules["clip_low"]:
            value = rules["clip_low"]
        if value > rules["clip_high"]:
            value = rules["clip_high"]
        factors[dev] = value.quantize(step, rounding=ROUND_HALF_UP)
    return factors


def factor_for(factors, dev, rules):
    if dev in factors:
        return factors[dev]
    step = Decimal(1).scaleb(-rules["factor_decimals"])
    return ONE.quantize(step)


# --------------------------------------------------------------------------
# allocation
# --------------------------------------------------------------------------

def allocate_cell(claims, cap, commitments, exceptions, lob, cycle):
    """Three-step allocation; mutates nothing, returns grants and remainder."""
    grants = {ref: 0 for ref in [c["claim_ref"] for c in claims]}
    unmet = {c["claim_ref"]: c["want"] for c in claims}
    remainder = 0
    pool = cap

    ordered = sorted(claims, key=lambda c: (c["claim_ref"],
                                            c["reinsurer_canonical"] or ""))

    for claim in ordered:
        if pool <= 0:
            break
        base = strip_epoch(claim["reinsurer_canonical"])
        minimum = commitments.get((base, lob), 0)
        if (base, lob, cycle) in exceptions:
            minimum = 0
        share = min(minimum, unmet[claim["claim_ref"]], pool)
        if share > 0:
            grants[claim["claim_ref"]] += share
            unmet[claim["claim_ref"]] -= share
            pool -= share

    live = [c for c in ordered if unmet[c["claim_ref"]] > 0]
    if pool > 0 and live:
        level = pool // len(live)
        if level > 0:
            for claim in live:
                ref = claim["claim_ref"]
                give = min(unmet[ref], level)
                if give > 0:
                    grants[ref] += give
                    unmet[ref] -= give
                    pool -= give

    while pool > 0 and any(unmet[c["claim_ref"]] > 0 for c in claims):
        queue = sorted(claims, key=lambda c: (-unmet[c["claim_ref"]],
                                              c["recorded_instant"],
                                              c["reinsurer_canonical"] or "",
                                              c["claim_ref"]))
        progressed = False
        for claim in queue:
            if pool <= 0:
                break
            ref = claim["claim_ref"]
            if unmet[ref] > 0:
                grants[ref] += 1
                unmet[ref] -= 1
                pool -= 1
                remainder += 1
                progressed = True
        if not progressed:
            break

    return grants, unmet, remainder


# --------------------------------------------------------------------------
# main build
# --------------------------------------------------------------------------

def build(data_dir):
    cx = Corpus(data_dir)
    missing = [n for n in required_files(cx) if not cx.exists(n)]
    if missing:
        raise FileNotFoundError("required source files missing: %s"
                                % ", ".join(sorted(missing)))

    dec = load_declarations(cx)
    rules = load_rule_parameters(cx)
    codes = dec["codes"]

    clock = CycleClock(cx)
    book = ReinsurerBook(cx)

    lob_order = [row["lob"].strip() for row in
                 sorted(cx.table("priority_register.csv"),
                        key=lambda r: (int(r["priority_order"]), r["lob"]))]
    priority = {row["lob"].strip(): int(row["priority_order"])
                for row in cx.table("priority_register.csv")}

    master = {}
    for row in cx.table("claim_master.csv"):
        master[row["claim_id"].strip()] = row

    capacity = {}
    for row in cx.table("layer_capacity_declarations.csv"):
        capacity[(row["lob"].strip(), row["cycle"].strip())] = \
            parse_dollars(row["capacity_dollars"], dec)
    ceiling = {}
    for row in cx.table("ceiling_register.csv"):
        ceiling[(row["lob"].strip(), row["cycle"].strip())] = \
            parse_dollars(row["ceiling_dollars"], dec)

    commitments = {}
    for row in cx.table("commitment_agreements.csv"):
        commitments[(row["reinsurer_id"].strip(), row["lob"].strip())] = \
            parse_dollars(row["minimum_dollars"], dec)
    exceptions = set()
    for row in cx.table("commitment_exceptions.csv"):
        exceptions.add((row["reinsurer_id"].strip(), row["lob"].strip(),
                        row["cycle"].strip()))

    attachment_factors = {}
    header, rows_af = cx.rows("attachment_factors.csv")
    i_from = first_index(header, "from_layer")
    i_to = first_index(header, "to_layer")
    i_fac = first_index(header, "factor")
    for row in rows_af:
        key = (row[i_from].strip(), row[i_to].strip())
        attachment_factors.setdefault(key, Decimal(row[i_fac].strip()))

    retracted = set()
    for row in cx.table("retraction_notices.csv"):
        retracted.add(row["claim_ref"].strip())

    layout = claim_tx_layout(cx)
    sources = load_sources(cx, dec, layout)
    sources["block_unit_rows"] = recount_block_units(cx, dec, rules)

    governing, collapse_stats = collapse(sources["rows"], dec)

    adj_records, adj_by_claim = load_adjustments(cx, dec)
    fraction = fit_alae_fraction(adj_records)
    alae_convention = settle_alae_convention(
        adj_records, rules["alae_candidates"], fraction)
    rival_convention = [c for c in rules["alae_candidates"]
                        if c != alae_convention][0]

    curve = load_curve(cx)
    discount_curve = settle_discount_curve(cx, curve,
                                           rules["discount_candidates"])

    endorsements = load_endorsements(cx, rules, dec["valuation_instant"])

    reserve_events = []
    for name in cx.glob("reserve_events_p*.jsonl"):
        for line in cx.lines(name):
            if line.strip():
                reserve_events.append(json.loads(line))
    reserve_events = [e for e in reserve_events
                      if e.get("recorded_instant", "") <= dec["valuation_instant"]]
    reserve_events.sort(key=lambda e: (e.get("version", 0),
                                       e.get("recorded_instant", ""),
                                       e.get("claim_ref", "")))
    claims_with_state = len({e.get("claim_ref") for e in reserve_events})

    factors = chain_ladder_factors(sources["rows"], rules)

    # ---------------- per-claim ledger seeds ----------------
    gap_shifted = 0
    seeds = []
    for ref in sorted(governing):
        gov = governing[ref]
        info = master.get(ref)
        lob = (info["booked_lob"].strip() if info else gov["lob"])
        ay = (accident_year_int(info["accident_year"]) if info
              else accident_year_int(gov["accident_year"]))
        event_id = (info["event_id"].strip() if info else None) or ("@" + ref)
        cycle, shifted = clock.place(gov["recorded_instant"])
        if shifted:
            gap_shifted += 1
        canonical = book.canonical(gov["reinsurer_id"], gov["recorded_instant"])
        paid = gov["paid_to_date"]
        dev = 0
        if ay is not None:
            dev = instant_year(gov["recorded_instant"]) - ay
            if dev < 0:
                dev = 0
        factor = factor_for(factors, dev, rules)
        ultimate = half_up(Decimal(paid) * factor)

        lines = adj_by_claim.get(ref, [])
        booked_layer = lines[-1]["layer"] if lines else rules["layer_path"][0]
        if booked_layer not in rules["layer_path"][:3]:
            booked_layer = rules["layer_path"][0]

        if lines:
            alae_pro = lines[-1]["alae"]
        else:
            alae_pro = half_up(fraction * Decimal(paid))

        is_retracted = ref in retracted
        is_excluded = canonical is None and not is_retracted

        seeds.append({
            "claim_ref": ref,
            "lob": lob,
            "cycle": cycle,
            "reinsurer_canonical": canonical,
            "recorded_instant": gov["recorded_instant"],
            "paid_to_date": paid,
            "incurred": (gov["incurred"] if gov["incurred"] is not None
                         else paid),
            "ultimate": ultimate,
            "alae_pro_rata": alae_pro,
            "booked_layer": booked_layer,
            "event_id": event_id,
            "retracted": is_retracted,
            "excluded": is_excluded,
            "first_log_layer": lines[0]["layer"] if lines else None,
        })

    # ---------------- clash cover ----------------
    first_layer = rules["layer_path"][0]
    second_layer = rules["layer_path"][1]
    by_event = {}
    for seed in seeds:
        by_event.setdefault(seed["event_id"], []).append(seed)
    for event_id in sorted(by_event):
        members = [s for s in by_event[event_id]
                   if not s["retracted"] and not s["excluded"]
                   and s["booked_layer"] == first_layer]
        members.sort(key=lambda s: (s["claim_ref"],
                                    s["reinsurer_canonical"] or ""))
        for idx, seed in enumerate(members):
            seed["layer"] = first_layer if idx == 0 else second_layer
    for seed in seeds:
        if seed["retracted"] or seed["excluded"]:
            seed["layer"] = first_layer
        elif "layer" not in seed:
            seed["layer"] = seed["booked_layer"]

    # ---------------- alae / want ----------------
    for seed in seeds:
        if seed["retracted"] or seed["excluded"]:
            seed["alae"] = 0
            seed["alae_rival"] = 0
        elif alae_convention == "pro_rata":
            seed["alae"] = seed["alae_pro_rata"]
            seed["alae_rival"] = (0 if seed["layer"] == first_layer
                                  else seed["alae_pro_rata"])
        else:
            seed["alae"] = (0 if seed["layer"] == first_layer
                            else seed["alae_pro_rata"])
            seed["alae_rival"] = seed["alae_pro_rata"]
        seed["want"] = max(0, seed["ultimate"] + seed["alae"]
                           - seed["paid_to_date"])
        seed["want_rival"] = max(0, seed["ultimate"] + seed["alae_rival"]
                                 - seed["paid_to_date"])

    # ---------------- allocation ----------------
    cells = {}
    for seed in seeds:
        cells.setdefault((seed["lob"], seed["cycle"]), []).append(seed)

    remainder_by_cell = {}
    for key in sorted(cells):
        lob, cycle = key
        members = cells[key]
        cap = capacity.get(key, 0)
        active = [s for s in members
                  if not s["retracted"] and not s["excluded"]]
        for seed in members:
            seed["grant"] = 0
            seed["unmet"] = seed["want"]
            seed["cap"] = cap
        remainder = 0
        if cap > 0 and active:
            grants, unmet, remainder = allocate_cell(
                active, cap, commitments, exceptions, lob, cycle)
            for seed in active:
                seed["grant"] = grants[seed["claim_ref"]]
                seed["unmet"] = unmet[seed["claim_ref"]]
        for seed in members:
            if seed["retracted"] or seed["excluded"]:
                seed["grant"] = 0
                seed["unmet"] = 0
        remainder_by_cell[key] = remainder

    # ---------------- outcome / reason ----------------
    for seed in seeds:
        candidates = []
        if seed["retracted"]:
            candidates.append(("RETRACTED", "RETRACTED"))
        if seed["excluded"]:
            candidates.append(("EXCLUDED", "UNRESOLVABLE_CHAIN"))
        if (not seed["retracted"] and not seed["excluded"]
                and seed["cap"] == 0):
            candidates.append(("ZERO", "CAP_ZERO"))
        if not seed["retracted"] and not seed["excluded"] and seed["cap"] > 0:
            if seed["want"] > 0 and seed["unmet"] == 0:
                candidates.append(("FULL", "NONE"))
            if seed["grant"] > 0 and seed["unmet"] > 0:
                candidates.append(("PARTIAL", "NONE"))
            if seed["grant"] == 0:
                candidates.append(("ZERO", "NO_QUALIFIED_LAYER"))
        if not candidates:
            candidates.append(("ACTIVE", "NONE"))
        outcomes = {c[0] for c in candidates}
        reasons = {c[1] for c in candidates}
        seed["outcome"] = next(o for o in codes["outcome_precedence"]
                               if o in outcomes)
        seed["reason"] = next(r for r in codes["reason_precedence"]
                              if r in reasons)
        seed["ceded_hours"] = seed["grant"]
        if seed["outcome"] not in codes["outcomes"]:
            raise ValueError("outcome outside declared vocabulary")
        if seed["reason"] not in codes["reasons"]:
            raise ValueError("reason outside declared vocabulary")

    return {
        "cx": cx, "dec": dec, "rules": rules, "codes": codes, "clock": clock,
        "lob_order": lob_order, "priority": priority, "seeds": seeds,
        "capacity": capacity, "ceiling": ceiling, "cells": cells,
        "remainder_by_cell": remainder_by_cell, "sources": sources,
        "collapse_stats": collapse_stats, "gap_shifted": gap_shifted,
        "alae_convention": alae_convention, "rival_convention": rival_convention,
        "alae_fraction": fraction, "discount_curve": discount_curve,
        "curve": curve, "endorsements": endorsements,
        "reserve_events": reserve_events, "claims_with_state": claims_with_state,
        "factors": factors, "retracted": retracted, "master": master,
        "adj_by_claim": adj_by_claim, "exceptions": exceptions,
        "attachment_factors": attachment_factors,
    }


# --------------------------------------------------------------------------
# artifacts
# --------------------------------------------------------------------------

def ledger_sort_key(seed):
    rc = seed["reinsurer_canonical"]
    return (seed["cycle"], 0 if rc is None else 1, rc or "", seed["claim_ref"])


def write_json(out_dir, name, payload):
    path = os.path.join(out_dir, name)
    text = json.dumps(payload, sort_keys=True, indent=1, ensure_ascii=False)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.write("\n")


def make_artifacts(state):
    seeds = state["seeds"]
    codes = state["codes"]
    clock = state["clock"]
    cycles = clock.codes

    docs = {}
    for lob in state["lob_order"]:
        rows = sorted([s for s in seeds if s["lob"] == lob],
                      key=ledger_sort_key)
        development = {c: 0 for c in cycles}
        for s in rows:
            if s["outcome"] != "EXCLUDED":
                development[s["cycle"]] += s["ultimate"] - s["paid_to_date"]
        docs["lob_%s.json" % lob] = {
            "lob": lob,
            "capacity_per_cycle": {c: state["capacity"].get((lob, c), 0)
                                   for c in cycles},
            "ceiling_per_cycle": {c: state["ceiling"].get((lob, c), 0)
                                  for c in cycles},
            "chain_ladder_development": development,
            "remainder_dollars_per_cycle": {
                c: state["remainder_by_cell"].get((lob, c), 0) for c in cycles},
            "ledger": [{
                "claim_ref": s["claim_ref"],
                "cycle": s["cycle"],
                "reinsurer_canonical": s["reinsurer_canonical"],
                "paid_to_date": s["paid_to_date"],
                "ultimate": s["ultimate"],
                "alae": s["alae"],
                "ceded_hours": s["ceded_hours"],
                "layer": s["layer"],
                "outcome": s["outcome"],
                "reason": s["reason"],
            } for s in rows],
        }

    ceded_total = sum(s["ceded_hours"] for s in seeds)
    ceded_by_lob = {lob: sum(s["ceded_hours"] for s in seeds if s["lob"] == lob)
                    for lob in state["lob_order"]}
    by_reinsurer = {}
    for s in seeds:
        rc = s["reinsurer_canonical"]
        if rc is None:
            continue
        by_reinsurer[rc] = by_reinsurer.get(rc, 0) + s["ceded_hours"]
    layer_breakdown = {}
    for layer in state["rules"]["layer_path"][:3]:
        layer_breakdown[layer] = 0
    for s in seeds:
        layer_breakdown[s["layer"]] = layer_breakdown.get(s["layer"], 0) \
            + s["ceded_hours"]
    docs["treaty_working.json"] = {
        "ceded_total": ceded_total,
        "ceded_by_lob": ceded_by_lob,
        "ceded_by_reinsurer_canonical": by_reinsurer,
        "layer_breakdown": layer_breakdown,
    }

    dq = {
        "late_recorded": len(state["sources"]["late_rows"]),
        "duplicate_identical": state["collapse_stats"]["duplicate_identical"],
        "duplicate_conflicting": state["collapse_stats"]["duplicate_conflicting"],
        "cross_source_collapsed": state["collapse_stats"]["cross_source_collapsed"],
        "fold_disambiguated": state["collapse_stats"]["fold_disambiguated"],
        "gap_shifted": state["gap_shifted"],
        "log_continuations": state["endorsements"]["log_continuations"],
        "unknown_reinsurer_rows": sum(
            1 for s in seeds if s["reinsurer_canonical"] is None),
        "out_of_horizon_rows": len(state["sources"]["late_rows"]),
        "block_unit_rows": state["sources"]["block_unit_rows"],
        "paren_negatives": count_paren_negatives(state["cx"]),
        "restatement_gaps": state["sources"]["restatement_gaps"],
    }
    docs["data_quality.json"] = dq

    cells_with_rows = {(s["lob"], s["cycle"]) for s in seeds}
    docs["methodology_audit.json"] = {
        "settlement": {
            "alae_convention": state["alae_convention"],
            "discount_curve": state["discount_curve"],
        },
        "attachment": {
            "authority_file": state["rules"]["attachment_authority"],
            "attachment_rule": state["rules"]["attachment_rule"],
        },
        "endorsements": {
            "circulars_total": len(state["endorsements"]["circulars"]),
            "circulars_endorsed": len(state["endorsements"]["counted"]),
            "audit_entries": state["endorsements"]["audit_entries"],
        },
        "reserve_state": {
            "events_total": len(state["reserve_events"]),
            "claims_with_state": state["claims_with_state"],
        },
        "chain_ladder": {
            "factors_bounded": state["rules"]["factors_bounded"],
            "development_cells_total": len(cells_with_rows),
        },
        "allocation": {
            "priority_order": dict(state["priority"]),
            "exceptions_count": len(state["exceptions"]),
        },
    }

    totals = {
        "claims_admitted": len(seeds),
        "claims_dropped_late": len(state["sources"]["late_rows"]),
        "claims_retracted": sum(1 for s in seeds
                                if s["outcome"] == "RETRACTED"),
        "unresolved_reinsurer": sum(1 for s in seeds
                                    if s["reinsurer_canonical"] is None),
        "cross_source_collapsed": state["collapse_stats"]["cross_source_collapsed"],
        "fold_disambiguated": state["collapse_stats"]["fold_disambiguated"],
        "total_paid_to_date": sum(s["paid_to_date"] for s in seeds),
        "total_incurred": sum(s["incurred"] for s in seeds),
        "total_ultimate": sum(s["ultimate"] for s in seeds),
        "total_alae": sum(s["alae"] for s in seeds),
        "total_ceded": ceded_total,
        "total_ibnr": sum(s["ultimate"] - s["paid_to_date"] for s in seeds),
    }
    docs["summary.json"] = {
        "run": {
            "admission_instant": state["dec"]["valuation_instant"],
            "alae_convention": state["alae_convention"],
            "discount_curve": state["discount_curve"],
            "lobs": list(state["lob_order"]),
            "cycles_total": len(cycles),
            "attachment_authority": state["rules"]["attachment_authority"],
        },
        "totals": totals,
        "lobs": {
            lob: {
                "claims": sum(1 for s in seeds if s["lob"] == lob),
                "total_paid_to_date": sum(s["paid_to_date"] for s in seeds
                                          if s["lob"] == lob),
                "total_ultimate": sum(s["ultimate"] for s in seeds
                                      if s["lob"] == lob),
                "total_ceded": ceded_by_lob[lob],
                "total_alae": sum(s["alae"] for s in seeds if s["lob"] == lob),
            } for lob in state["lob_order"]
        },
    }
    return docs


# --------------------------------------------------------------------------
# counterfactuals (reported only in the agent message, never written)
# --------------------------------------------------------------------------

def counterfactuals(state):
    seeds = state["seeds"]
    rules = state["rules"]
    retracted = state["retracted"]
    kept = [s for s in seeds if s["claim_ref"] not in retracted]

    r1 = sum(s["alae"] for s in kept)
    r2 = sum(1 for s in seeds if s["want"] > s["alae"])

    r3 = sum(1 for s in seeds if s["want_rival"] != s["want"])
    r4 = sum(s["want_rival"] for s in seeds)

    curve = state["curve"]
    extended = dict(curve)
    extended[rules["cf_added_tenor"]] = max(curve.values()) + rules["cf_increment"]
    divisor = rules["cf_cycle_divisor"]
    r5 = 0
    for s in kept:
        years = Decimal(int(s["cycle"][1:])) / Decimal(divisor)
        a = pv_factor(curve_rate(curve, years), years)
        b = pv_factor(curve_rate(extended, years), years)
        if a != b:
            r5 += 1
    last_cycle = state["clock"].codes[-1]
    years_last = Decimal(int(last_cycle[1:])) / Decimal(divisor)
    factor_last = pv_factor(curve_rate(curve, years_last), years_last)
    r6 = sum(half_even(Decimal(s["want"]) * factor_last) for s in kept)

    mult = rules["cf_retro_multiplier"]
    target = rules["cf_retro_layer"]
    r7 = 0
    r8 = 0
    for s in kept:
        if s["first_log_layer"] == target:
            r7 += half_up(Decimal(s["want"]) * mult)
            r8 += 1
        else:
            r7 += s["want"]

    r9 = sum(state["remainder_by_cell"].values())
    r10 = sum(1 for v in state["remainder_by_cell"].values() if v > 0)

    late_tx = state["sources"]["tx_late_rows"]
    r11 = len({r["claim_ref"] for r in late_tx})
    r12 = sum(r["paid_to_date"] for r in late_tx)

    by_ref = {s["claim_ref"]: s for s in seeds}
    dropped_refs = {c.get("claim_ref") for c in state["endorsements"]["dropped"]}
    hit = [by_ref[r] for r in sorted(dropped_refs) if r in by_ref]
    r13 = len(hit)
    r14 = len({(s["lob"], s["cycle"]) for s in hit})

    return {
        "R1": r1, "R2": r2, "R3": r3, "R4": r4, "R5": r5, "R6": r6,
        "R7": r7, "R8": r8, "R9": r9, "R10": r10, "R11": r11, "R12": r12,
        "R13": r13, "R14": r14,
    }


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description="Year-end 2032 reserving run")
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--counterfactuals", action="store_true",
                        help="print the counterfactual quantities to stdout")
    args = parser.parse_args(argv)

    state = build(args.data)
    docs = make_artifacts(state)
    os.makedirs(args.out, exist_ok=True)
    for name in sorted(docs):
        write_json(args.out, name, docs[name])

    if args.counterfactuals:
        values = counterfactuals(state)
        for key in sorted(values, key=lambda k: int(k[1:])):
            print("%s=%d" % (key, values[key]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
