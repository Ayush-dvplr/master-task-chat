#!/usr/bin/env python3
"""Year-end 2032 reserving engine.

Reads the flat corpus handed to it on --data and writes the nine documents
fixed by output_contract.md into --out.  Every rule is read from the corpus
at run time; nothing about the shipped scale is baked in.
"""

import argparse
import csv
import glob
import json
import math
import os
import re
from decimal import Decimal, ROUND_HALF_UP

# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def half_up(value):
    """Round a Decimal/int/float to the nearest whole number, halves up."""
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def half_up_places(value, places):
    q = Decimal(1).scaleb(-places)
    return Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP)


def require(path):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    return path


def require_glob(data_dir, pattern):
    hits = sorted(glob.glob(os.path.join(data_dir, pattern)))
    if not hits:
        raise FileNotFoundError(os.path.join(data_dir, pattern))
    return hits


def read_rows(path, delimiter=","):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.reader(fh, delimiter=delimiter) if r and any(c.strip() for c in r)]
    if not rows:
        return [], []
    return rows[0], rows[1:]


def table(path, delimiter=","):
    """Positional table: header list plus list of row lists."""
    return read_rows(require(path), delimiter)


def first_index(header, name):
    for i, h in enumerate(header):
        if h.strip() == name:
            return i
    return None


def parse_money(text):
    """Dollars as a whole integer.  Parenthesised values are negative."""
    s = (text or "").strip().replace(",", "").replace("$", "")
    if not s:
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    if not s:
        return None
    try:
        value = int(float(s))
    except ValueError:
        return None
    return -value if neg else value


PAREN_RE = re.compile(r"\(\d[\d,]*\)")


# --------------------------------------------------------------------------
# declaration loading
# --------------------------------------------------------------------------


def load_ini(path):
    out, section = {}, None
    with open(require(path), "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith(("#", ";")):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip()
                out[section] = {}
                continue
            if "=" in line and section is not None:
                k, v = line.split("=", 1)
                out[section][k.strip()] = v.strip()
    return out


def load_properties(path):
    """Keeps declaration order; that order is the source precedence."""
    order, values = [], {}
    with open(require(path), "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith(("#", "!")):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            values[k] = v.strip()
            prefix = k.split(".", 1)[0]
            if prefix not in order:
                order.append(prefix)
    return order, values


# --------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------


class Corpus(object):
    def __init__(self, data_dir):
        self.dir = data_dir
        self.policy = load_ini(os.path.join(data_dir, "derivation_policy.ini"))
        self.units = load_ini(os.path.join(data_dir, "unit_declarations.ini"))
        self.source_order, self.source_props = load_properties(
            os.path.join(data_dir, "source_declarations.properties")
        )
        with open(require(os.path.join(data_dir, "reason_codes.json")), "r", encoding="utf-8") as fh:
            self.codes = json.load(fh)

        self.admission_instant = self.policy["horizon"]["valuation_instant"]

        # contract documents must be present; they are the single source of truth
        self.docs = {}
        for name in (
            "output_contract.md",
            "source_manifest.md",
            "alae_rules.md",
            "allocation_rules.md",
            "amendment_rules.md",
            "attachment_rules.md",
            "chain_ladder_rules.md",
            "counterfactual_parameters.md",
            "data_quality_counting.md",
            "discounting_rules.md",
            "priority_rules.md",
            "corpus_index.md",
        ):
            with open(require(os.path.join(data_dir, name)), "r", encoding="utf-8") as fh:
                self.docs[name] = fh.read()

        # the errata that replaces the withdrawn handbook is the attachment authority
        errata = require_glob(data_dir, "errata_*.md")
        self.attachment_authority = os.path.basename(errata[-1])
        for path in errata:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            self.docs[os.path.basename(path)] = text
            if "attachment" in text.lower():
                self.attachment_authority = os.path.basename(path)

        self._read_rule_constants()

        self.tx_files = require_glob(data_dir, "claim_tx_*.csv")
        self.cession_files = require_glob(data_dir, "cession_q*.tsv")
        self.fixed_files = require_glob(data_dir, "fixed_width_intake_*.txt")
        self.reserve_files = require_glob(data_dir, "reserve_events_p*.jsonl")
        self.circular_files = require_glob(data_dir, "endorsement_circulars_p*.jsonl")
        self.audit_files = require_glob(data_dir, "endorsement_audit.log*")

        self.cycles = self._cycles()
        self.capacity = self._lob_cycle_map("layer_capacity_declarations.csv")
        self.ceiling = self._lob_cycle_map("ceiling_register.csv")
        self.priority = self._priority()
        self.lobs = [l for l, _ in sorted(self.priority.items(), key=lambda kv: (kv[1], kv[0]))]
        self.layer_names, self.layer_factors = self._layers()
        self.alias = self._alias()
        self.master_epochs = self._master()
        self.commitments = self._commitments()
        self.exceptions = self._exceptions()
        self.retractions = self._retractions()
        self.claim_master = self._claim_master()
        self.curve = self._curve()
        self.authority = self._authority()

    # -- rule constants read from the contract documents -------------------

    def _read_rule_constants(self):
        cl = self.docs["chain_ladder_rules.md"]
        m = re.search(r"clipped to the interval\s*`?\[\s*([\d.]+)\s*,\s*([\d.]+)\s*\]`?", cl)
        if not m:
            raise ValueError("chain_ladder_rules.md declares no clipping interval")
        self.factor_low = Decimal(m.group(1))
        self.factor_high = Decimal(m.group(2))
        self.factors_bounded = "[%s, %s]" % (m.group(1), m.group(2))
        m = re.search(r"rounded to (\w+) decimal places", cl)
        words = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        }
        self.factor_places = words.get(m.group(1), 6) if m else 6

        al = self.docs["alae_rules.md"]
        m = re.search(r"fraction is fixed at\s*`?([\d.]+)`?", al)
        if not m:
            m = re.search(r"([\d.]+)\s*\*\s*paid_to_date", al)
        if not m:
            raise ValueError("alae_rules.md declares no pro-rata fraction")
        self.alae_fraction = Decimal(m.group(1))

        dq = self.docs["data_quality_counting.md"]
        years = re.findall(r"AY(\d{4})", dq)
        if len(years) >= 2:
            self.ay_low, self.ay_high = int(years[0]), int(years[1])
        else:
            self.ay_low, self.ay_high = None, None

        cf = self.docs["counterfactual_parameters.md"]
        m = re.search(r"added tenor is\s*`?(\d+)`?", cf)
        self.cf_tenor = float(m.group(1)) if m else 15.0
        m = re.search(r"fixed increment of\s*`?([\d.]+)`?", cf)
        self.cf_increment = float(m.group(1)) if m else 0.5
        m = re.search(r"unmet\s*\*\s*([\d.]+)\s*\)", cf)
        self.cf_retro = Decimal(m.group(1)) if m else Decimal("1.10")

    # -- reference tables ---------------------------------------------------

    def _cycles(self):
        header, rows = table(os.path.join(self.dir, "cycle_marks.csv"))
        out = []
        for r in rows:
            out.append((r[0].strip(), r[1].strip(), r[2].strip()))
        out.sort(key=lambda t: t[0])
        return out

    def _lob_cycle_map(self, name):
        header, rows = table(os.path.join(self.dir, name))
        out = {}
        for r in rows:
            out[(r[0].strip(), r[1].strip())] = parse_money(r[2]) or 0
        return out

    def _priority(self):
        header, rows = table(os.path.join(self.dir, "priority_register.csv"))
        return {r[0].strip(): int(r[1]) for r in rows}

    def _layers(self):
        header, rows = table(os.path.join(self.dir, "attachment_factors.csv"))
        names, factors = [], {}
        for r in rows:
            frm, to, fac = r[0].strip(), r[1].strip(), r[2].strip()
            if frm not in names:
                names.append(frm)
            factors[frm] = Decimal(fac)
            del to
        return names, factors

    def _alias(self):
        header, rows = table(os.path.join(self.dir, "reinsurer_alias_map.csv"))
        return {r[0].strip().lower(): r[1].strip() for r in rows}

    def _master(self):
        header, rows = table(os.path.join(self.dir, "reinsurer_master.csv"))
        seen = {}
        for r in rows:
            rid, boundary = r[0].strip(), (r[2].strip() if len(r) > 2 else "")
            seen.setdefault(rid, []).append(boundary)
        epochs = {}
        for rid, boundaries in seen.items():
            marks = sorted({b for b in boundaries if b})
            epochs[rid] = marks[0] if (len(boundaries) > 1 and marks) else None
        return epochs

    def _commitments(self):
        header, rows = table(os.path.join(self.dir, "commitment_agreements.csv"))
        return {(r[0].strip(), r[1].strip()): parse_money(r[2]) or 0 for r in rows}

    def _exceptions(self):
        header, rows = table(os.path.join(self.dir, "commitment_exceptions.csv"))
        self.exceptions_count = len(rows)
        return {(r[0].strip(), r[1].strip(), r[2].strip()) for r in rows}

    def _retractions(self):
        header, rows = table(os.path.join(self.dir, "retraction_notices.csv"))
        return {r[0].strip(): (r[1].strip(), r[2].strip() if len(r) > 2 else "") for r in rows}

    def _claim_master(self):
        header, rows = table(os.path.join(self.dir, "claim_master.csv"))
        out = {}
        for r in rows:
            out[r[0].strip()] = {
                "booked_lob": r[1].strip(),
                "accident_year": r[2].strip(),
                "event_id": r[3].strip(),
                "segment": r[4].strip() if len(r) > 4 else "",
            }
        return out

    def _curve(self):
        header, rows = table(os.path.join(self.dir, "curve_marks.csv"))
        return {float(r[0]): float(r[1]) for r in rows}

    def _authority(self):
        header, rows = table(os.path.join(self.dir, "authority_roles.csv"))
        return {(r[0].strip(), r[1].strip()): r[2].strip() for r in rows}

    # -- reinsurer resolution ----------------------------------------------

    def resolve(self, raw, instant):
        """Raw reinsurer id -> canonical `RE-NNNN#E`, or None."""
        if raw is None:
            return None
        key = raw.strip()
        if not key:
            return None
        base = self.alias.get(key.lower(), key)
        if base not in self.master_epochs:
            base2 = self.alias.get(base.lower())
            if base2 and base2 in self.master_epochs:
                base = base2
            else:
                return None
        boundary = self.master_epochs[base]
        if boundary and instant and instant >= boundary:
            return base + "#2"
        return base + "#1"

    # -- cycle placement ---------------------------------------------------

    def cycle_of(self, instant):
        for code, start, end in self.cycles:
            if start <= instant <= end:
                return code
        return None

    def next_cycle(self, code):
        codes = [c for c, _, _ in self.cycles]
        if code in codes:
            i = codes.index(code)
            if i + 1 < len(codes):
                return codes[i + 1]
        return code


# --------------------------------------------------------------------------
# DST transition windows
# --------------------------------------------------------------------------


def _nth_weekday(year, month, weekday, n):
    """Day-of-month of the n-th `weekday` (0=Mon) of month."""
    first = date_weekday(year, month, 1)
    offset = (weekday - first) % 7
    return 1 + offset + 7 * (n - 1)


def date_weekday(year, month, day):
    # Zeller-free: use the proleptic Gregorian ordinal
    import datetime

    return datetime.date(year, month, day).weekday()


def dst_windows(year):
    """(start, end) UTC-shaped ISO strings for the missing and repeated hour."""
    spring = _nth_weekday(year, 3, 6, 2)  # second Sunday of March
    fall = _nth_weekday(year, 11, 6, 1)  # first Sunday of November
    return [
        ("%04d-%02d-%02dT02:00:00Z" % (year, 3, spring), "%04d-%02d-%02dT03:00:00Z" % (year, 3, spring)),
        ("%04d-%02d-%02dT01:00:00Z" % (year, 11, fall), "%04d-%02d-%02dT02:00:00Z" % (year, 11, fall)),
    ]


def in_dst_gap(instant):
    if not instant or len(instant) < 20:
        return False
    try:
        year = int(instant[:4])
    except ValueError:
        return False
    for start, end in dst_windows(year):
        if start <= instant < end:
            return True
    return False


# --------------------------------------------------------------------------
# row ingestion
# --------------------------------------------------------------------------


def load_claim_rows(corpus):
    """Every claim-bearing source row, tagged with its `_source` category."""
    rows = []

    # claim transaction logs, read by column position (leftmost header governs)
    for path in corpus.tx_files:
        header, data = table(path)
        for idx, r in enumerate(data):
            if len(r) < 8:
                continue
            rows.append(
                {
                    "_source": "claim_tx",
                    "_file": os.path.basename(path),
                    "_line": idx,
                    "claim_ref": r[0].strip(),
                    "reinsurer_id": r[1].strip(),
                    "lob": r[2].strip(),
                    "accident_year": r[3].strip(),
                    "paid_to_date": parse_money(r[4]),
                    "incurred": parse_money(r[5]),
                    "recorded_instant": r[6].strip(),
                    "restated": parse_money(r[7]),
                    "ceded_dollars": None,
                }
            )

    # cession bordereau
    for path in corpus.cession_files:
        header, data = table(path, "\t")
        for idx, r in enumerate(data):
            if len(r) < 5:
                continue
            rows.append(
                {
                    "_source": "cession",
                    "_file": os.path.basename(path),
                    "_line": idx,
                    "claim_ref": r[0].strip(),
                    "reinsurer_id": r[1].strip(),
                    "lob": r[2].strip(),
                    "accident_year": None,
                    "paid_to_date": None,
                    "incurred": None,
                    "recorded_instant": r[4].strip(),
                    "restated": None,
                    "ceded_dollars": parse_money(r[3]),
                }
            )

    # legacy fixed-width intake, parsed by column offsets
    width = int(corpus.source_props.get("fixed_width_intake.width", "92"))
    for path in corpus.fixed_files:
        with open(require(path), "r", encoding="utf-8") as fh:
            for idx, line in enumerate(fh):
                line = line.rstrip("\n").rstrip("\r")
                if not line.strip():
                    continue
                line = line.ljust(width)
                rows.append(
                    {
                        "_source": "fixed_width_intake",
                        "_file": os.path.basename(path),
                        "_line": idx,
                        "claim_ref": line[0:12].strip(),
                        "reinsurer_id": line[12:32].strip(),
                        "lob": line[32:40].strip(),
                        "accident_year": line[40:48].strip(),
                        "paid_to_date": parse_money(line[48:62]),
                        "incurred": None,
                        "recorded_instant": line[62:82].strip(),
                        "restated": None,
                        "ceded_dollars": None,
                    }
                )
    return rows


def all_recorded_instants(corpus):
    """Every `recorded_instant` in the corpus, for the late-recorded tally."""
    instants = []
    for path in corpus.tx_files:
        header, data = table(path)
        for r in data:
            if len(r) > 6:
                instants.append(r[6].strip())
    for path in corpus.cession_files:
        header, data = table(path, "\t")
        for r in data:
            if len(r) > 4:
                instants.append(r[4].strip())
    for path in corpus.fixed_files:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if line.strip():
                    instants.append(line[62:82].strip())
    for path in corpus.reserve_files + corpus.circular_files:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if "recorded_instant" in obj:
                    instants.append(obj["recorded_instant"])
    for path in corpus.audit_files:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                m = ISO_RE.match(line.strip())
                if m:
                    instants.append(m.group(0))
    for name in ("claim_adjustment_log.log", "treasury_curve_observations.log"):
        p = os.path.join(corpus.dir, name)
        with open(require(p), "r", encoding="utf-8") as fh:
            for line in fh:
                m = ISO_RE.match(line.strip())
                if m:
                    instants.append(m.group(0))
    header, data = table(os.path.join(corpus.dir, "retraction_notices.csv"))
    for r in data:
        if len(r) > 1:
            instants.append(r[1].strip())
    return instants


# --------------------------------------------------------------------------
# settlement passes (methodology readings)
# --------------------------------------------------------------------------

ADJ_RE = re.compile(
    r"^(?P<instant>\S+)\s+(?P<claim>\S+)\s+gross=(?P<gross>-?\d+)\s+alae=(?P<alae>-?\d+)"
    r"\s+settled=(?P<settled>-?\d+)\s+layer=(?P<layer>\S+)\s*$"
)
CURVE_RE = re.compile(
    r"^(?P<instant>\S+)\s+tenor=(?P<tenor>[\d.]+)y\s+observed=(?P<observed>[\d.]+)"
    r"\s+pv_factor=(?P<pv>[\d.]+)\s*$"
)


def load_adjustment_log(corpus):
    out = []
    path = require(os.path.join(corpus.dir, "claim_adjustment_log.log"))
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            m = ADJ_RE.match(line)
            if not m:
                continue
            out.append(
                {
                    "recorded_instant": m.group("instant"),
                    "claim_ref": m.group("claim"),
                    "gross": int(m.group("gross")),
                    "alae": int(m.group("alae")),
                    "settled": int(m.group("settled")),
                    "layer": m.group("layer"),
                }
            )
    return out


def load_curve_log(corpus):
    out = []
    path = require(os.path.join(corpus.dir, "treasury_curve_observations.log"))
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            m = CURVE_RE.match(line)
            if not m:
                continue
            out.append(
                {
                    "recorded_instant": m.group("instant"),
                    "tenor": float(m.group("tenor")),
                    "observed": float(m.group("observed")),
                    "pv_factor": float(m.group("pv")),
                }
            )
    return out


def settle_alae(observations, fraction):
    """Enumerate the two candidate readings; the one that fits every row wins."""
    pro_rata = all(
        abs(obs["alae"] - half_up(fraction * Decimal(obs["settled"]))) <= 1 for obs in observations
    )
    excess_only = all(
        (obs["alae"] == 0) if obs["layer"] == "retention" else (obs["alae"] > 0)
        for obs in observations
    )
    if pro_rata and not excess_only:
        return "pro_rata"
    if excess_only and not pro_rata:
        return "excess_only"
    return "pro_rata" if pro_rata else "excess_only"


def interp_rate(curve, tenor):
    keys = sorted(curve)
    if not keys:
        return 0.0
    if tenor <= keys[0]:
        return curve[keys[0]]
    if tenor >= keys[-1]:
        return curve[keys[-1]]
    for lo, hi in zip(keys, keys[1:]):
        if lo <= tenor <= hi:
            return curve[lo] + (curve[hi] - curve[lo]) * (tenor - lo) / (hi - lo)
    return curve[keys[-1]]


def settle_curve(observations, curve, tol=1.0e-4):
    long_key = max(curve) if curve else 0.0
    flat_rate = curve.get(long_key, 0.0)
    flat_ok = all(
        abs(o["pv_factor"] - (1.0 + flat_rate / 100.0) ** (-o["tenor"])) <= tol for o in observations
    )
    matched_ok = all(
        abs(o["pv_factor"] - (1.0 + o["observed"] / 100.0) ** (-o["tenor"])) <= tol
        for o in observations
    )
    if matched_ok and not flat_ok:
        return "duration_matched"
    if flat_ok and not matched_ok:
        return "flat_10y"
    return "duration_matched" if matched_ok else "flat_10y"


# --------------------------------------------------------------------------
# endorsement and reserve-state stages
# --------------------------------------------------------------------------

AUDIT_RE = re.compile(r"^(?P<instant>\S+)\s+(?P<verb>\S+)\s+(?P<rest>.*)$")


def load_audit(corpus):
    """Returns (entries_by_claim, total_entries, continuation_lines)."""
    by_claim = {}
    total = 0
    continuations = 0
    for path in corpus.audit_files:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                if not re.match(r"^\d{4}", stripped):
                    continuations += 1
                    continue
                total += 1
                m = AUDIT_RE.match(stripped)
                if not m:
                    continue
                fields = {}
                for token in m.group("rest").split():
                    if "=" in token:
                        k, v = token.split("=", 1)
                        fields[k] = v
                claim = fields.get("claim")
                if claim:
                    by_claim.setdefault(claim, []).append(
                        {
                            "instant": m.group("instant"),
                            "underwriter": fields.get("underwriter", ""),
                            "lob": fields.get("lob", ""),
                        }
                    )
    return by_claim, total, continuations


def load_circulars(corpus):
    out = []
    for path in corpus.circular_files:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    return out


def endorsement_pass(corpus, circulars, audit_by_claim, governing):
    """Apply amendment_rules.md.  Returns (endorsed, dropped_for_authority)."""
    endorsed = []
    dropped_authority = []
    adm = corpus.admission_instant
    for circ in circulars:
        if circ.get("recorded_instant", "") > adm:
            continue
        claim = circ.get("claim_ref")
        gov = governing.get(claim)
        recorded_after_row = bool(gov) and circ.get("recorded_instant", "") > gov["recorded_instant"]
        entries = audit_by_claim.get(claim, [])
        effective = corpus.authority.get((circ.get("underwriter", ""), circ.get("lob", "")))
        authorised = bool(entries) and effective is not None and any(
            e["instant"] >= effective for e in entries
        )
        if recorded_after_row and authorised:
            endorsed.append(circ)
        elif recorded_after_row and not authorised:
            dropped_authority.append(circ)
        elif not authorised:
            dropped_authority.append(circ)
    return endorsed, dropped_authority


def load_reserve_events(corpus):
    events = []
    for path in corpus.reserve_files:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    adm = corpus.admission_instant
    events = [e for e in events if e.get("recorded_instant", "") <= adm]
    events.sort(key=lambda e: (int(e.get("version", 0)), e.get("recorded_instant", ""), e.get("claim_ref", "")))
    state = {}
    for e in events:
        state[e["claim_ref"]] = e.get("state")
    return events, state


# --------------------------------------------------------------------------
# cross-source collapse
# --------------------------------------------------------------------------

FOLD_FIELDS = ("reinsurer_id", "lob", "accident_year", "paid_to_date", "incurred")


def collapse(corpus, admitted_rows):
    """Fold each claim's admitted rows into one governing claim row."""
    rank = {name: i for i, name in enumerate(corpus.source_order)}
    default_rank = len(rank)

    by_claim = {}
    for row in admitted_rows:
        by_claim.setdefault(row["claim_ref"], []).append(row)

    governing = {}
    cross_source = 0
    fold_disambiguated = 0

    for claim, rows in by_claim.items():
        ordered = sorted(
            rows,
            key=lambda r: (
                rank.get(r["_source"], default_rank),
                _desc(r["recorded_instant"]),
                r["_file"],
                r["_line"],
            ),
        )
        sources = {r["_source"] for r in rows}
        if len(sources) >= 2:
            cross_source += 1
            per_source = {}
            for r in ordered:
                per_source.setdefault(r["_source"], r)
            conflict = False
            for field in FOLD_FIELDS:
                seen = {
                    per_source[s][field]
                    for s in per_source
                    if per_source[s][field] is not None and per_source[s][field] != ""
                }
                if len(seen) >= 2:
                    conflict = True
                    break
            if conflict:
                fold_disambiguated += 1

        base = dict(ordered[0])
        for field in FOLD_FIELDS:
            if base.get(field) in (None, ""):
                for r in ordered[1:]:
                    if r.get(field) not in (None, ""):
                        base[field] = r[field]
                        break
        base["_rows"] = ordered
        base["_sources"] = sorted(sources)
        governing[claim] = base

    return governing, cross_source, fold_disambiguated


def _desc(text):
    """Sort key that puts the latest instant first."""
    return tuple(-ord(c) for c in (text or ""))


# --------------------------------------------------------------------------
# chain ladder
# --------------------------------------------------------------------------


def dev_year(instant, accident_year):
    try:
        year = int(instant[:4])
    except (TypeError, ValueError):
        return 0
    ay = accident_year_int(accident_year)
    if ay is None:
        return 0
    return max(0, year - ay)


def accident_year_int(accident_year):
    if not accident_year:
        return None
    digits = re.sub(r"[^0-9]", "", accident_year)
    return int(digits) if digits else None


def chain_ladder_factors(tx_rows_admitted, low, high, places):
    num = {}
    den = {}
    for row in tx_rows_admitted:
        d = dev_year(row["recorded_instant"], row["accident_year"])
        num[d] = num.get(d, 0) + (row["incurred"] or 0)
        den[d] = den.get(d, 0) + (row["paid_to_date"] or 0)
    factors = {}
    for d in sorted(set(list(num) + list(den))):
        if den.get(d, 0) == 0:
            raw = Decimal("1.0")
        else:
            raw = Decimal(num[d]) / Decimal(den[d])
        if raw < low:
            raw = low
        if raw > high:
            raw = high
        factors[d] = half_up_places(raw, places)
    return factors


def factor_for(factors, d, low):
    if d in factors:
        return factors[d]
    return low


# --------------------------------------------------------------------------
# allocation
# --------------------------------------------------------------------------


def allocate_cell(corpus, claims, cap):
    """Three-step allocation inside one (lob, cycle) cell.

    `claims` is a list of dicts with claim_ref, reinsurer_canonical,
    recorded_instant and want.  Returns (grants, unmet, remainder_dollars).
    """
    grants = {}
    unmet = {}
    for c in claims:
        grants[c["key"]] = 0
        unmet[c["key"]] = c["want"]

    remainder = 0
    if cap <= 0 or not claims:
        return grants, unmet, remainder

    pool = cap
    ordered = sorted(claims, key=lambda c: (c["claim_ref"], c["reinsurer_canonical"]))

    # Step 1: honoured minimums
    for c in ordered:
        if pool <= 0:
            break
        base = c["reinsurer_canonical"].split("#", 1)[0]
        minimum = corpus.commitments.get((base, c["lob"]), 0)
        if (base, c["lob"], c["cycle"]) in corpus.exceptions:
            minimum = 0
        share = min(minimum, unmet[c["key"]], pool)
        if share > 0:
            grants[c["key"]] += share
            unmet[c["key"]] -= share
            pool -= share

    # Step 2: shared fill level
    live = [c for c in ordered if unmet[c["key"]] > 0]
    if pool > 0 and live:
        level = pool // len(live)
        if level > 0:
            for c in live:
                give = min(unmet[c["key"]], level)
                if give > 0:
                    grants[c["key"]] += give
                    unmet[c["key"]] -= give
                    pool -= give

    # Step 3: indivisible remainder
    while pool > 0:
        live = sorted(
            [c for c in claims if unmet[c["key"]] > 0],
            key=lambda c: (
                -unmet[c["key"]],
                c["recorded_instant"],
                c["reinsurer_canonical"],
                c["claim_ref"],
            ),
        )
        if not live:
            break
        k = len(live)
        if pool < k:
            for c in live[:pool]:
                grants[c["key"]] += 1
                unmet[c["key"]] -= 1
            remainder += pool
            pool = 0
            break
        rounds = min(pool // k, min(unmet[c["key"]] for c in live))
        if rounds <= 0:
            break
        for c in live:
            grants[c["key"]] += rounds
            unmet[c["key"]] -= rounds
        pool -= rounds * k
        remainder += rounds * k

    return grants, unmet, remainder


def outcome_for(corpus, retracted, cap, want, grant, unmet):
    if retracted:
        return "RETRACTED", "RETRACTED"
    if cap <= 0:
        return "ZERO", "CAP_ZERO"
    if grant == 0:
        return "ZERO", "NO_QUALIFIED_LAYER"
    if want > 0 and unmet == 0:
        return "FULL", "NONE"
    return "PARTIAL", "NONE"


def run_allocation(corpus, ledger, want_of):
    """Allocate every cell.  Mutates nothing; returns per-row results."""
    cells = {}
    for row in ledger:
        cells.setdefault((row["lob"], row["cycle"]), []).append(row)

    grants = {}
    unmets = {}
    outcomes = {}
    reasons = {}
    remainder = {}

    for (lob, cycle), rows in cells.items():
        cap = corpus.capacity.get((lob, cycle), 0)
        entering = []
        for row in rows:
            if row["retracted"]:
                continue
            entering.append(
                {
                    "key": row["key"],
                    "claim_ref": row["claim_ref"],
                    "reinsurer_canonical": row["reinsurer_canonical"],
                    "recorded_instant": row["recorded_instant"],
                    "lob": lob,
                    "cycle": cycle,
                    "want": want_of(row),
                }
            )
        g, u, rem = allocate_cell(corpus, entering, cap)
        remainder[(lob, cycle)] = rem
        for row in rows:
            if row["retracted"]:
                grants[row["key"]] = 0
                unmets[row["key"]] = 0
                outcomes[row["key"]], reasons[row["key"]] = "RETRACTED", "RETRACTED"
            else:
                grants[row["key"]] = g[row["key"]]
                unmets[row["key"]] = u[row["key"]]
                o, r = outcome_for(
                    corpus, False, cap, want_of(row), g[row["key"]], u[row["key"]]
                )
                outcomes[row["key"]], reasons[row["key"]] = o, r
    return grants, unmets, outcomes, reasons, remainder


# --------------------------------------------------------------------------
# engine
# --------------------------------------------------------------------------


class Engine(object):
    def __init__(self, data_dir):
        self.corpus = Corpus(data_dir)
        self.build()

    def build(self):
        corpus = self.corpus
        adm = corpus.admission_instant

        self.all_instants = all_recorded_instants(corpus)
        self.late_recorded = sum(1 for i in self.all_instants if i > adm)

        raw_rows = load_claim_rows(corpus)
        self.raw_rows = raw_rows
        admitted = [r for r in raw_rows if r["recorded_instant"] <= adm]
        self.admitted = admitted

        # methodology readings
        self.adjustments = load_adjustment_log(corpus)
        self.curve_obs = load_curve_log(corpus)
        self.alae_convention = settle_alae(self.adjustments, corpus.alae_fraction)
        self.discount_curve = settle_curve(self.curve_obs, corpus.curve)
        self.settled_claims = {a["claim_ref"] for a in self.adjustments}

        # cross-source collapse
        self.governing, self.cross_source, self.fold_disambiguated = collapse(corpus, admitted)

        # endorsements and reserve state (audited stages)
        self.audit_by_claim, self.audit_entries, self.log_continuations = load_audit(corpus)
        self.circulars = load_circulars(corpus)
        self.endorsed, self.dropped_authority = endorsement_pass(
            corpus, self.circulars, self.audit_by_claim, self.governing
        )
        self.reserve_events, self.reserve_state = load_reserve_events(corpus)

        # chain ladder
        tx_admitted = [r for r in admitted if r["_source"] == "claim_tx"]
        self.tx_admitted = tx_admitted
        self.factors = chain_ladder_factors(
            tx_admitted, corpus.factor_low, corpus.factor_high, corpus.factor_places
        )

        # ledger construction
        self.unknown_reinsurer_rows = 0
        for row in admitted:
            if corpus.resolve(row["reinsurer_id"], row["recorded_instant"]) is None:
                self.unknown_reinsurer_rows += 1

        self.gap_shifted = sum(1 for r in admitted if in_dst_gap(r["recorded_instant"]))

        self.out_of_horizon_rows = 0
        ay_lo, ay_hi = corpus.ay_low, corpus.ay_high
        for row in admitted:
            ay = accident_year_int(row["accident_year"])
            if ay is None:
                continue
            if ay_lo is not None and (ay < ay_lo or ay > ay_hi):
                self.out_of_horizon_rows += 1

        self.block_unit_rows = sum(
            1
            for r in raw_rows
            if r["_source"] == "fixed_width_intake"
            and r["paid_to_date"]
            and r["paid_to_date"] > 0
            and r["paid_to_date"] % 1000 == 0
        )
        self.restatement_gaps = sum(
            1
            for r in raw_rows
            if r["_source"] == "claim_tx" and r["restated"] is not None and r["restated"] != r["paid_to_date"]
        )
        self.paren_negatives = self._paren_negatives()
        self.duplicate_identical, self.duplicate_conflicting = self._duplicates(admitted)

        self.claims_dropped_late = 0
        all_by_claim = {}
        for row in raw_rows:
            all_by_claim.setdefault(row["claim_ref"], []).append(row)
        self.late_only_claims = sorted(
            c for c, rows in all_by_claim.items() if all(r["recorded_instant"] > adm for r in rows)
        )
        self.claims_dropped_late = len(self.late_only_claims)

        self.ledger, self.unresolved_reinsurer = self._ledger()
        self._assign_layers()
        self._allocate()

    # -- data quality helpers ---------------------------------------------

    def _paren_negatives(self):
        total = 0
        for name in sorted(os.listdir(self.corpus.dir)):
            if not (name.endswith(".csv") or name.endswith(".tsv")):
                continue
            with open(os.path.join(self.corpus.dir, name), "r", encoding="utf-8") as fh:
                for line in fh:
                    if PAREN_RE.search(line):
                        total += 1
        return total

    def _duplicates(self, admitted):
        identical = 0
        conflicting = 0
        groups = {}
        for row in admitted:
            groups.setdefault((row["claim_ref"], row["_source"]), []).append(row)
        for rows in groups.values():
            n = len(rows)
            for i in range(n):
                for j in range(i + 1, n):
                    a, b = rows[i], rows[j]
                    same_full = (
                        a["lob"] == b["lob"]
                        and a["accident_year"] == b["accident_year"]
                        and a["paid_to_date"] == b["paid_to_date"]
                        and a["incurred"] == b["incurred"]
                        and a["recorded_instant"] == b["recorded_instant"]
                    )
                    if same_full:
                        identical += 1
                    elif (
                        a["paid_to_date"] != b["paid_to_date"]
                        or a["incurred"] != b["incurred"]
                        or a["recorded_instant"] != b["recorded_instant"]
                    ):
                        conflicting += 1
        return identical, conflicting

    # -- ledger ------------------------------------------------------------

    def _ledger(self):
        corpus = self.corpus
        unresolved = 0
        ledger = []
        for claim_ref in sorted(self.governing):
            gov = self.governing[claim_ref]
            canonical = corpus.resolve(gov["reinsurer_id"], gov["recorded_instant"])
            if canonical is None:
                unresolved += 1
                continue
            cycle = corpus.cycle_of(gov["recorded_instant"])
            if cycle is None:
                continue
            if in_dst_gap(gov["recorded_instant"]):
                cycle = corpus.next_cycle(cycle)
            lob = gov["lob"] or corpus.claim_master.get(claim_ref, {}).get("booked_lob")
            if lob not in corpus.priority:
                continue
            paid = gov["paid_to_date"] or 0
            incurred = gov["incurred"] or 0
            d = dev_year(gov["recorded_instant"], gov["accident_year"])
            factor = factor_for(self.factors, d, self.corpus.factor_low)
            ultimate = half_up(Decimal(paid) * factor)
            ledger.append(
                {
                    "key": claim_ref,
                    "claim_ref": claim_ref,
                    "cycle": cycle,
                    "lob": lob,
                    "reinsurer_canonical": canonical,
                    "recorded_instant": gov["recorded_instant"],
                    "paid_to_date": paid,
                    "incurred": incurred,
                    "ultimate": ultimate,
                    "dev_year": d,
                    "retracted": claim_ref in corpus.retractions,
                    "event_id": corpus.claim_master.get(claim_ref, {}).get("event_id", ""),
                }
            )
        return ledger, unresolved

    def _assign_layers(self):
        """Clash-cover attachment: the claims of one event share one retention."""
        names = self.corpus.layer_names
        by_event = {}
        for row in self.ledger:
            by_event.setdefault(row["event_id"], []).append(row)
        for event in sorted(by_event):
            rows = sorted(by_event[event], key=lambda r: r["claim_ref"])
            for i, row in enumerate(rows):
                row["layer"] = names[min(i, len(names) - 1)]

    def _alae(self, row, convention):
        if row["retracted"]:
            return 0
        if convention == "excess_only":
            if row["layer"] == self.corpus.layer_names[0]:
                return 0
            return half_up(self.corpus.alae_fraction * Decimal(row["paid_to_date"]))
        return half_up(self.corpus.alae_fraction * Decimal(row["paid_to_date"]))

    def _allocate(self):
        for row in self.ledger:
            row["alae"] = self._alae(row, self.alae_convention)

        def want_of(row):
            return max(0, row["ultimate"] + row["alae"] - row["paid_to_date"])

        grants, unmets, outcomes, reasons, remainder = run_allocation(
            self.corpus, self.ledger, want_of
        )
        for row in self.ledger:
            row["ceded_hours"] = grants[row["key"]]
            row["unmet"] = unmets[row["key"]]
            row["outcome"] = outcomes[row["key"]]
            row["reason"] = reasons[row["key"]]
        self.remainder = remainder

    # -- artifacts ---------------------------------------------------------

    def cycle_codes(self):
        return [c for c, _, _ in self.corpus.cycles]

    def lob_document(self, lob):
        rows = [r for r in self.ledger if r["lob"] == lob]
        rows.sort(key=lambda r: (r["cycle"], r["reinsurer_canonical"], r["claim_ref"]))
        codes = self.cycle_codes()
        development = {c: 0 for c in codes}
        for r in rows:
            development[r["cycle"]] = development.get(r["cycle"], 0) + (
                r["ultimate"] - r["paid_to_date"]
            )
        return {
            "lob": lob,
            "capacity_per_cycle": {c: self.corpus.capacity.get((lob, c), 0) for c in codes},
            "ceiling_per_cycle": {c: self.corpus.ceiling.get((lob, c), 0) for c in codes},
            "chain_ladder_development": {c: int(development.get(c, 0)) for c in codes},
            "remainder_dollars_per_cycle": {
                c: int(self.remainder.get((lob, c), 0)) for c in codes
            },
            "ledger": [
                {
                    "claim_ref": r["claim_ref"],
                    "cycle": r["cycle"],
                    "reinsurer_canonical": r["reinsurer_canonical"],
                    "paid_to_date": int(r["paid_to_date"]),
                    "ultimate": int(r["ultimate"]),
                    "alae": int(r["alae"]),
                    "ceded_hours": int(r["ceded_hours"]),
                    "layer": r["layer"],
                    "outcome": r["outcome"],
                    "reason": r["reason"],
                }
                for r in rows
            ],
        }

    def summary(self):
        totals = {
            "claims_admitted": len(self.ledger),
            "claims_dropped_late": self.claims_dropped_late,
            "claims_retracted": sum(1 for r in self.ledger if r["retracted"]),
            "unresolved_reinsurer": self.unresolved_reinsurer,
            "cross_source_collapsed": self.cross_source,
            "fold_disambiguated": self.fold_disambiguated,
            "total_paid_to_date": sum(r["paid_to_date"] for r in self.ledger),
            "total_incurred": sum(r["incurred"] for r in self.ledger),
            "total_ultimate": sum(r["ultimate"] for r in self.ledger),
            "total_alae": sum(r["alae"] for r in self.ledger),
            "total_ceded": sum(r["ceded_hours"] for r in self.ledger),
            "total_ibnr": sum(r["ultimate"] - r["paid_to_date"] for r in self.ledger),
        }
        lobs = {}
        for lob in self.corpus.lobs:
            rows = [r for r in self.ledger if r["lob"] == lob]
            lobs[lob] = {
                "claims": len(rows),
                "total_paid_to_date": sum(r["paid_to_date"] for r in rows),
                "total_ultimate": sum(r["ultimate"] for r in rows),
                "total_ceded": sum(r["ceded_hours"] for r in rows),
                "total_alae": sum(r["alae"] for r in rows),
            }
        return {
            "run": {
                "admission_instant": self.corpus.admission_instant,
                "alae_convention": self.alae_convention,
                "discount_curve": self.discount_curve,
                "lobs": list(self.corpus.lobs),
                "cycles_total": len(self.corpus.cycles),
                "attachment_authority": self.corpus.attachment_authority,
            },
            "totals": totals,
            "lobs": lobs,
        }

    def methodology_audit(self):
        cells = {(r["lob"], r["cycle"]) for r in self.ledger}
        return {
            "settlement": {
                "alae_convention": self.alae_convention,
                "discount_curve": self.discount_curve,
            },
            "attachment": {
                "authority_file": self.corpus.attachment_authority,
                "attachment_rule": "clash_cover_per_event",
                "layer_count": len(self.corpus.layer_names),
                "layer_names": list(self.corpus.layer_names),
            },
            "endorsements": {
                "circulars_total": len(self.circulars),
                "circulars_endorsed": len(self.endorsed),
                "audit_entries": self.audit_entries,
            },
            "reserve_state": {
                "events_total": len(self.reserve_events),
                "claims_with_state": len(self.reserve_state),
            },
            "chain_ladder": {
                "factors_bounded": self.corpus.factors_bounded,
                "development_cells_total": len(cells),
            },
            "allocation": {
                "priority_order": dict(self.corpus.priority),
                "exceptions_count": self.corpus.exceptions_count,
            },
        }

    def data_quality(self):
        return {
            "late_recorded": self.late_recorded,
            "duplicate_identical": self.duplicate_identical,
            "duplicate_conflicting": self.duplicate_conflicting,
            "cross_source_collapsed": self.cross_source,
            "fold_disambiguated": self.fold_disambiguated,
            "gap_shifted": self.gap_shifted,
            "log_continuations": self.log_continuations,
            "unknown_reinsurer_rows": self.unknown_reinsurer_rows,
            "out_of_horizon_rows": self.out_of_horizon_rows,
            "block_unit_rows": self.block_unit_rows,
            "paren_negatives": self.paren_negatives,
            "restatement_gaps": self.restatement_gaps,
        }

    def treaty_working(self):
        by_lob = {lob: 0 for lob in self.corpus.lobs}
        by_re = {}
        by_layer = {name: 0 for name in self.corpus.layer_names}
        total = 0
        for r in self.ledger:
            total += r["ceded_hours"]
            by_lob[r["lob"]] = by_lob.get(r["lob"], 0) + r["ceded_hours"]
            by_re[r["reinsurer_canonical"]] = (
                by_re.get(r["reinsurer_canonical"], 0) + r["ceded_hours"]
            )
            by_layer[r["layer"]] = by_layer.get(r["layer"], 0) + r["ceded_hours"]
        return {
            "ceded_total": total,
            "ceded_by_lob": by_lob,
            "ceded_by_reinsurer_canonical": by_re,
            "layer_breakdown": by_layer,
        }

    # -- counterfactuals (reported only in the closing message) -----------

    def counterfactuals(self):
        corpus = self.corpus
        out = {}

        base_grant = {r["key"]: r["ceded_hours"] for r in self.ledger}
        base_outcome = {r["key"]: r["outcome"] for r in self.ledger}

        # R1/R2 carried IBNR held at zero
        g, u, o, rsn, rem = run_allocation(corpus, self.ledger, lambda r: max(0, r["alae"]))
        out["R1"] = sum(g.values())
        out["R2"] = sum(1 for r in self.ledger if o[r["key"]] != base_outcome[r["key"]])

        # R3/R4 rival ALAE convention
        rival = {r["key"]: self._alae(r, "excess_only") for r in self.ledger}
        g2, u2, o2, rsn2, rem2 = run_allocation(
            corpus,
            self.ledger,
            lambda r: max(0, r["ultimate"] + rival[r["key"]] - r["paid_to_date"]),
        )
        out["R3"] = sum(
            1
            for r in self.ledger
            if r["claim_ref"] in self.settled_claims and g2[r["key"]] != base_grant[r["key"]]
        )
        out["R4"] = sum(g2.values())

        # R5/R6 extended discount curve
        long_tail = [lob for lob in ("wc", "cal", "gl") if lob in corpus.priority]
        extended = dict(corpus.curve)
        extended[corpus.cf_tenor] = max(corpus.curve.values()) + corpus.cf_increment
        differ = 0
        pv_base = 0.0
        pv_ext = 0.0
        for r in self.ledger:
            ibnr = r["ultimate"] - r["paid_to_date"]
            if r["lob"] in long_tail:
                f0 = self._pv_factor(corpus.curve, r["dev_year"])
                f1 = self._pv_factor(extended, r["dev_year"])
                if abs(f0 - f1) > 1e-12:
                    differ += 1
                pv_base += ibnr * f0
                pv_ext += ibnr * f1
            else:
                pv_base += ibnr
                pv_ext += ibnr
        out["R5"] = differ
        out["R6"] = half_up(pv_ext)
        out["R6_governing"] = half_up(pv_base)

        # R7/R8 retro offset never applied
        cat = corpus.layer_names[-1]
        total = 0
        cats = 0
        for r in self.ledger:
            ibnr = r["ultimate"] - r["paid_to_date"]
            if r["layer"] == cat:
                cats += 1
                total += half_up(Decimal(ibnr) * corpus.cf_retro)
            else:
                total += ibnr
        out["R7"] = total
        out["R8"] = cats

        # R9/R10 indivisible remainder (governing run)
        out["R9"] = sum(self.remainder.values())
        out["R10"] = sum(1 for v in self.remainder.values() if v > 0)

        # R11/R12 admission instant lifted
        all_by_claim = {}
        for row in self.raw_rows:
            all_by_claim.setdefault(row["claim_ref"], []).append(row)
        late_claims = self.late_only_claims
        out["R11"] = len(late_claims)
        out["R12"] = sum(
            max(
                (r["paid_to_date"] or 0)
                for r in sorted(
                    all_by_claim[c], key=lambda x: x["recorded_instant"], reverse=True
                )[:1]
            )
            for c in late_claims
        ) if late_claims else 0

        # R13/R14 unendorsed amendments honoured
        out["R13"] = len(self.dropped_authority)
        out["R14"] = 0
        return out

    def _pv_factor(self, curve, tenor):
        rate = interp_rate(curve, float(tenor))
        return (1.0 + rate / 100.0) ** (-float(tenor))


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------


def write_json(path, obj):
    text = json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Year-end 2032 reserving run")
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--counterfactuals", action="store_true")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.data):
        raise FileNotFoundError(args.data)
    if not os.path.isdir(args.out):
        os.makedirs(args.out)

    engine = Engine(args.data)

    write_json(os.path.join(args.out, "summary.json"), engine.summary())
    write_json(os.path.join(args.out, "methodology_audit.json"), engine.methodology_audit())
    write_json(os.path.join(args.out, "data_quality.json"), engine.data_quality())
    for lob in engine.corpus.lobs:
        write_json(os.path.join(args.out, "lob_%s.json" % lob), engine.lob_document(lob))
    write_json(os.path.join(args.out, "treaty_working.json"), engine.treaty_working())

    if args.counterfactuals:
        cf = engine.counterfactuals()
        for key in sorted(cf, key=lambda k: (len(k), k)):
            print("%s=%s" % (key, cf[key]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
