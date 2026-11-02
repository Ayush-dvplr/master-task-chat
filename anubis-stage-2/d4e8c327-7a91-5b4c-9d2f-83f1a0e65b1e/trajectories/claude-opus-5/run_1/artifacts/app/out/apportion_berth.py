#!/usr/bin/env python3
"""Berth-hour apportionment for the four-terminal container port Alpha/Bravo/Charlie/Delta.

Every rule is read from the corpus at run time: the contract documents
(``*.md``, ``derivation_policy.ini``, ``unit_declarations.ini``,
``source_declarations.properties``, ``reason_codes.json``) are the single
source of truth and the two settlement logs settle the withheld rules by
enumeration.
"""

import argparse
import configparser
import csv
import glob
import json
import os
import re
from datetime import datetime, timedelta

TERMINAL_ORDER_FALLBACK = ["Alpha", "Bravo", "Charlie", "Delta"]

# words a tally name may carry that a marker token leaves implicit
FILLER_WORDS = {"event", "row"}


def _stem(word):
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _stems(name):
    return [_stem(w) for w in name.split("_") if w]


def marker_matches(token, tally):
    """True when ``token`` is the marker named after the tally ``tally``.

    Marker tokens drop the plural and sometimes the trailing category word, so
    ``exception_applied_marker`` answers to ``exceptions_applied`` and
    ``duplicate_version_marker`` answers to ``duplicate_version_events``.
    """
    if not token.endswith("_marker"):
        return False
    base = _stems(token[: -len("_marker")])
    want = _stems(tally)
    if base == want:
        return True
    if len(want) > len(base) and want[: len(base)] == base:
        return all(w in FILLER_WORDS for w in want[len(base):])
    return False


# --------------------------------------------------------------------------
# primitive readers (every one of them raises if the file cannot be read)
# --------------------------------------------------------------------------

def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def read_lines(path):
    return [ln.rstrip("\n") for ln in read_text(path).split("\n")]


def read_csv_rows(path, delimiter=","):
    """Return (header, list-of-lists). Raises on a missing file."""
    text = read_text(path)
    rows = list(csv.reader(text.splitlines(), delimiter=delimiter))
    rows = [r for r in rows if r and any(c.strip() for c in r)]
    if not rows:
        return [], []
    return rows[0], rows[1:]


def read_csv_dicts(path, delimiter=","):
    header, rows = read_csv_rows(path, delimiter)
    out = []
    for r in rows:
        d = {}
        for i, h in enumerate(header):
            d[h] = r[i] if i < len(r) else ""
        d["__row__"] = r
        out.append(d)
    return header, out


def family(data_dir, pattern):
    return sorted(glob.glob(os.path.join(data_dir, pattern)))


def require_family(data_dir, pattern):
    files = family(data_dir, pattern)
    if not files:
        raise FileNotFoundError(
            "no corpus file matches %s in %s" % (pattern, data_dir))
    return files


def parse_instant(text):
    if text is None:
        return None
    t = text.strip()
    if not t:
        return None
    t = t.replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(t, fmt)
        except ValueError:
            continue
    raise ValueError("uninterpretable instant %r" % (text,))


NUM_RE = re.compile(r"^-?\d+$")


def parse_int(text):
    """Integer reader honouring parenthesised negatives and block units."""
    if text is None:
        return None
    t = text.strip().replace(",", "").replace("_", "")
    if not t:
        return None
    neg = False
    if t.startswith("(") and t.endswith(")"):
        neg = True
        t = t[1:-1].strip()
    if t.startswith("+"):
        t = t[1:]
    if NUM_RE.match(t):
        v = int(t)
        return -v if neg else v
    try:
        v = float(t)
    except ValueError:
        return None
    v = int(v) if float(v).is_integer() else int(v)
    return -v if neg else v


# --------------------------------------------------------------------------
# contract readers
# --------------------------------------------------------------------------

def read_ini(path):
    cp = configparser.ConfigParser()
    cp.read_string(read_text(path))
    return cp


def read_properties(path):
    props = {}
    for ln in read_text(path).splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or ln.startswith("!"):
            continue
        if "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        props[k.strip()] = v.strip()
    return props


def source_declarations(path):
    """source name -> declared row count."""
    out = {}
    for k, v in read_properties(path).items():
        if k.endswith(".declared"):
            out[k[: -len(".declared")]] = parse_int(v) or 0
    return out


# --------------------------------------------------------------------------
# withheld rules, settled by enumeration over the settlement logs
# --------------------------------------------------------------------------

CYCLE_ORDINAL_RE = re.compile(r"(\d+)\s*$")


def cycle_gap(first, second, cycle_index):
    """Cycles between two cycle labels, by horizon position where both labels
    sit in the horizon and by label ordinal otherwise."""
    if first in cycle_index and second in cycle_index:
        return cycle_index[second] - cycle_index[first]
    a = CYCLE_ORDINAL_RE.search(first or "")
    b = CYCLE_ORDINAL_RE.search(second or "")
    if a is None or b is None:
        return None
    return int(b.group(1)) - int(a.group(1))


def settle_survival_cycles(path, cycle_index):
    """Largest carried age that every observation still reports as surviving."""
    carried, expired = set(), set()
    for ln in read_text(path).splitlines():
        ln = ln.strip()
        if not ln:
            continue
        fields = {}
        for tok in ln.split():
            if "=" in tok:
                k, v = tok.split("=", 1)
                fields[k] = v
        raised = fields.get("lot_raised")
        opening = fields.get("opening")
        outcome = (fields.get("outcome") or "").upper()
        if raised is None or opening is None:
            continue
        age = cycle_gap(raised, opening, cycle_index)
        if age is None:
            continue
        if outcome == "CARRIED":
            carried.add(age)
        elif outcome == "EXPIRED":
            expired.add(age)
    candidates = []
    hi = max(list(carried) + list(expired) + [0])
    for n in range(0, hi + 1):
        if all(a <= n for a in carried) and all(a > n for a in expired):
            candidates.append(n)
    if not candidates:
        raise ValueError("demurrage settlement log admits no survival age")
    return candidates[0]


def _sunday_hours(start, hours):
    n = 0
    for h in range(int(hours)):
        if (start + timedelta(hours=h)).weekday() == 6:
            n += 1
    return n


def counted_hours(convention, start, hours, adverse=None):
    """Laytime hours that count under a weather-stoppage convention."""
    hours = int(hours)
    if hours <= 0:
        return 0
    if convention == "SHINC":
        return hours
    if convention == "SHEX":
        return hours - _sunday_hours(start, hours)
    if convention == "WWD":
        if not adverse:
            return hours
        dropped = 0
        for h in range(hours):
            t = start + timedelta(hours=h)
            if any(a0 <= t < a1 for a0, a1 in adverse):
                dropped += 1
        return hours - dropped
    raise ValueError("unknown weather-stoppage convention %r" % (convention,))


def settle_weather_stoppage(path, rules_text):
    """Pick the one candidate convention that fits every settled observation."""
    cands = []
    for name in ("SHEX", "SHINC", "WWD"):
        if name in rules_text:
            cands.append(name)
    if not cands:
        cands = ["SHEX", "SHINC", "WWD"]
    obs = []
    for ln in read_text(path).splitlines():
        ln = ln.strip()
        if not ln:
            continue
        fields = {}
        for tok in ln.split():
            if "=" in tok:
                k, v = tok.split("=", 1)
                fields[k] = v
        if "window" not in fields or "laytime_counted_hours" not in fields:
            continue
        w0, w1 = fields["window"].split("/")
        start, end = parse_instant(w0), parse_instant(w1)
        adverse = []
        if "adverse" in fields:
            a0, a1 = fields["adverse"].split("/")
            adverse.append((parse_instant(a0), parse_instant(a1)))
        span = int(round((end - start).total_seconds() / 3600.0))
        obs.append((start, span, adverse, parse_int(fields["laytime_counted_hours"])))
    if not obs:
        raise ValueError("laytime observation log carries no observation")
    fits = {}
    for name in cands:
        fits[name] = sum(
            1 for (s, span, adv, want) in obs
            if counted_hours(name, s, span, adv) == want)
    # a reading that fits only some of the observations is the wrong reading
    settled = [n for n in cands if fits[n] == len(obs)]
    if not settled:
        raise ValueError("laytime observations settle no convention")
    rival = [n for n in cands if fits[n] == 0]
    return settled[0], (rival[0] if len(rival) == 1 else None), fits, len(obs)


# --------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------

class Corpus(object):
    def __init__(self, data_dir):
        d = self.dir = data_dir
        self.policy = read_ini(os.path.join(d, "derivation_policy.ini"))
        self.units = read_ini(os.path.join(d, "unit_declarations.ini"))
        self.declared = source_declarations(
            os.path.join(d, "source_declarations.properties"))
        self.reason_codes = json.loads(
            read_text(os.path.join(d, "reason_codes.json")))["codes"]

        self.laytime_rules = read_text(os.path.join(d, "laytime_rules.md"))
        self.demurrage_rules = read_text(os.path.join(d, "demurrage_rules.md"))
        self.priority_rules = read_text(os.path.join(d, "priority_rules.md"))
        self.substitution_rules = read_text(os.path.join(d, "substitution_rules.md"))
        self.amendment_rules = read_text(os.path.join(d, "amendment_rules.md"))
        read_text(os.path.join(d, "corpus_index.md"))
        read_text(os.path.join(d, "source_manifest.md"))
        read_text(os.path.join(d, "output_contract.md"))

        self.admission = parse_instant(self.policy.get("admission", "instant"))
        self.cutover = parse_instant(self.policy.get("cutover", "april_2032"))
        self.ceiling_source = self.policy.get(
            "precedence", "ceiling_source", fallback="ceiling_register")
        self.berth_hour_unit = parse_int(
            self.units.get("unit", "berth_hours", fallback="1")) or 1

        self.precedence = {}
        for key in self.policy.options("precedence"):
            val = parse_int(self.policy.get("precedence", key))
            if val is not None:
                self.precedence[key] = val

        self._load_reference(d)
        self._load_clock(d)
        self._load_sources(d)
        self._settle(d)

    # -- reference registers -------------------------------------------------
    def _load_reference(self, d):
        _, rows = read_csv_dicts(os.path.join(d, "charterer_master.csv"))
        self.charterers = {}
        self.by_spelling = {}
        for r in rows:
            canon = r["canonical"].strip()
            rec = {
                "canonical": canon,
                "spelling": r.get("spelling", "").strip(),
                "segment": r.get("segment", "").strip(),
                "epoch_start": parse_instant(r.get("epoch_start")),
                "epoch_end": parse_instant(r.get("epoch_end")),
            }
            self.charterers[canon] = rec
            self.by_spelling.setdefault(rec["spelling"], []).append(rec)

        _, rows = read_csv_dicts(os.path.join(d, "charterer_alias_map.csv"))
        self.aliases = {r["alias"].strip(): r["canonical"].strip() for r in rows}

        _, rows = read_csv_dicts(os.path.join(d, "vessel_master.csv"))
        self.vessels = {}
        for r in rows:
            self.vessels[r["vessel_id"].strip()] = {
                "name": r.get("name", "").strip(),
                "draft_m": parse_int(r.get("draft_m")),
                "booked_berth": r.get("booked_berth", "").strip(),
            }

        _, rows = read_csv_dicts(os.path.join(d, "authority_roles.csv"))
        self.authorities = []
        for r in rows:
            self.authorities.append({
                "authority_id": r["authority_id"].strip(),
                "scope": [s for s in r.get("scope", "").split("|") if s],
                "recorded_instant": parse_instant(r.get("recorded_instant")),
            })

        _, rows = read_csv_dicts(os.path.join(d, "retraction_notices.csv"))
        self.suspensions = set()
        for r in rows:
            ch = (r.get("charterer") or "").strip()
            tm = (r.get("terminal") or "").strip()
            if ch:
                self.suspensions.add((ch, tm))

        _, rows = read_csv_dicts(os.path.join(d, "priority_register.csv"))
        self.rank = {}
        for r in rows:
            self.rank[r["charterer"].strip()] = parse_int(r.get("rank")) or 0

        _, rows = read_csv_dicts(os.path.join(d, "commitment_agreements.csv"))
        self.agreements = {}
        for r in rows:
            self.agreements[(r["charterer"].strip(), r["terminal"].strip())] = \
                parse_int(r.get("minimum_hours")) or 0

        _, rows = read_csv_dicts(os.path.join(d, "commitment_exceptions.csv"))
        self.exception_rows = rows
        self.exceptions_waived = set()
        for r in rows:
            status = (r.get("endorsement_status") or "").strip().upper()
            event = (r.get("event") or "").strip()
            if status == "ENDORSED" and "applied" in event:
                self.exceptions_waived.add(
                    (r["charterer"].strip(), r["terminal"].strip()))

        _, rows = read_csv_dicts(os.path.join(d, "ceiling_register.csv"))
        self.ceilings = {}
        for r in rows:
            self.ceilings[(r["charterer"].strip(), r["terminal"].strip())] = \
                parse_int(r.get("ceiling_hours"))

        _, rows = read_csv_dicts(os.path.join(d, "tide_tables.csv"))
        self.spring = {}
        for r in rows:
            self.spring[r["cycle"].strip()] = \
                (r.get("spring", "").strip().lower() == "true")

        _, rows = read_csv_dicts(os.path.join(d, "substitution_factors.csv"))
        self.factors = {}
        for r in rows:
            self.factors[(r["cycle"].strip(), r["terminal_from"].strip(),
                          r["terminal_to"].strip())] = parse_int(r.get("factor"))

        _, rows = read_csv_dicts(os.path.join(d, "pilotage_windows.csv"))
        self.pilotage = {}
        for r in rows:
            self.pilotage[(r["cycle"].strip(), r["terminal_from"].strip(),
                           r["terminal_to"].strip())] = \
                (r.get("open", "").strip().lower() == "true")

    # -- clock and capacity --------------------------------------------------
    def _load_clock(self, d):
        _, rows = read_csv_dicts(os.path.join(d, "terminal_clock_marks.csv"))
        starts = {}
        terms = set()
        for r in rows:
            cyc = r["cycle"].strip()
            terms.add(r["terminal"].strip())
            st = parse_instant(r.get("window_start"))
            en = parse_instant(r.get("window_end"))
            if cyc not in starts:
                starts[cyc] = (st, en)
        self.cycles = sorted(starts, key=lambda c: (starts[c][0], c))
        self.cycle_window = starts
        self.cycle_index = {c: i for i, c in enumerate(self.cycles)}
        self.terminals = sorted(terms) if terms else list(TERMINAL_ORDER_FALLBACK)

        _, rows = read_csv_dicts(
            os.path.join(d, "terminal_capacity_declarations.csv"))
        self.capacity_rows = rows
        cap = {}
        for r in rows:
            inst = parse_instant(r.get("recorded_instant"))
            if inst is not None and self.admission is not None \
                    and inst > self.admission:
                continue
            key = (r["terminal"].strip(), r["cycle"].strip())
            val = parse_int(r.get("capacity_hours"))
            prev = cap.get(key)
            if prev is None or (inst is not None and prev[0] is not None
                                and inst >= prev[0]):
                cap[key] = (inst, val)
        self.capacity = {k: (v[1] or 0) for k, v in cap.items()}

    # -- record sources ------------------------------------------------------
    def _load_sources(self, d):
        self.parsed = {}
        self.admitted = {}

        # nor logs ---------------------------------------------------------
        self.nor_log_rows = []
        parsed = 0
        for path in require_family(d, "nor_log_*.csv"):
            header, rows = read_csv_rows(path)
            pos = [i for i, h in enumerate(header) if h.strip() == "laytime_hours"]
            for r in rows:
                parsed += 1
                get = lambda name: (r[header.index(name)]
                                    if name in header and header.index(name) < len(r)
                                    else "")
                rec = {
                    "nor_ref": get("nor_ref").strip(),
                    "cycle": get("cycle").strip(),
                    "charterer": get("charterer").strip(),
                    "booked_berth": get("booked_berth").strip(),
                    # the first laytime_hours column by position governs
                    "laytime_hours": parse_int(r[pos[0]]) if pos and pos[0] < len(r) else None,
                    "ceiling_hours": parse_int(get("ceiling_hours")),
                    "recorded_instant": parse_instant(get("recorded_instant")),
                    "source": "nor_log",
                }
                self.nor_log_rows.append(rec)
        self.parsed["nor_log"] = parsed

        # registry ---------------------------------------------------------
        self.registry_rows = []
        parsed = 0
        for path in require_family(d, "registry_q*.tsv"):
            header, rows = read_csv_dicts(path, delimiter="\t")
            for r in rows:
                parsed += 1
                self.registry_rows.append({
                    "nor_ref": (r.get("nor_ref") or "").strip(),
                    "cycle": (r.get("cycle") or "").strip(),
                    "charterer": (r.get("charterer") or "").strip(),
                    "booked_berth": (r.get("booked_berth") or "").strip(),
                    "laytime_hours": parse_int(r.get("laytime_hours")),
                    "ceiling_hours": parse_int(r.get("ceiling_hours")),
                    "recorded_instant": parse_instant(r.get("recorded_instant")),
                    "source": "registry",
                })
        self.parsed["registry"] = parsed

        # fixed width intake ------------------------------------------------
        self.fixed_rows = []
        parsed = 0
        for path in require_family(d, "fixed_width_intake_*.txt"):
            names = None
            for ln in read_lines(path):
                if not ln.strip():
                    continue
                if names is None and ln.lstrip().startswith("#"):
                    names = ln.lstrip("# ").split()
                    continue
                toks = ln.split()
                if names is None or len(toks) != len(names):
                    continue
                parsed += 1
                r = dict(zip(names, toks))
                self.fixed_rows.append({
                    "nor_ref": r.get("nor_ref", "").strip(),
                    "cycle": r.get("cycle", "").strip(),
                    "charterer": r.get("charterer", "").strip(),
                    "booked_berth": (r.get("berth") or r.get("booked_berth") or "").strip(),
                    "laytime_hours": parse_int(r.get("laytime") or r.get("laytime_hours")),
                    "ceiling_hours": parse_int(r.get("ceiling_hours")),
                    "recorded_instant": parse_instant(r.get("recorded_instant")),
                    "source": "fixed_width_intake",
                })
        self.parsed["fixed_width"] = parsed

        # state events ------------------------------------------------------
        self.event_rows = []
        self.event_markers = {}
        parsed = 0
        for path in require_family(d, "state_events_p*.jsonl"):
            for ln in read_lines(path):
                ln = ln.strip()
                if not ln:
                    continue
                obj = json.loads(ln)
                parsed += 1
                marker = None
                for key in ("event", "transition"):
                    tok = obj.get(key)
                    if isinstance(tok, str) and tok.endswith("_marker"):
                        marker = tok
                if marker is not None:
                    self.event_markers[marker] = self.event_markers.get(marker, 0) + 1
                    continue
                self.event_rows.append({
                    "nor_ref": (obj.get("nor_ref") or "").strip(),
                    "state": (obj.get("state") or "").strip(),
                    "version": parse_int(str(obj.get("version"))) or 0,
                    "recorded_instant": parse_instant(obj.get("recorded_instant")),
                    "source": "state_events",
                })
        self.parsed["state_events"] = parsed

        # port circulars ----------------------------------------------------
        self.circular_rows = []
        self.circular_markers = {}
        parsed = 0
        for path in require_family(d, "port_circulars_p*.jsonl"):
            for ln in read_lines(path):
                ln = ln.strip()
                if not ln:
                    continue
                obj = json.loads(ln)
                parsed += 1
                tok = obj.get("event")
                if isinstance(tok, str) and tok.endswith("_marker"):
                    self.circular_markers[tok] = self.circular_markers.get(tok, 0) + 1
                self.circular_rows.append(obj)
        self.parsed["port_circulars"] = parsed

        # approval audit ----------------------------------------------------
        self.audit_markers = {}
        self.audit_rows = []
        parsed = 0
        for path in require_family(d, "approval_audit.log*"):
            for ln in read_lines(path):
                ln = ln.strip()
                if not ln:
                    continue
                toks = ln.split()
                parsed += 1
                inst = None
                try:
                    inst = parse_instant(toks[0])
                except ValueError:
                    inst = None
                token = toks[1] if len(toks) > 1 else ""
                self.audit_rows.append({"instant": inst, "token": token,
                                        "line": ln, "path": path})
                if token.endswith("_marker"):
                    self.audit_markers[token] = self.audit_markers.get(token, 0) + 1
        self.parsed["approval_audit"] = parsed

        # the audit instant is the latest endorsement instant on record
        endorsed = [r["instant"] for r in self.audit_rows
                    if r["instant"] is not None and "endorsed" in r["line"]]
        self.audit_instant = max(endorsed) if endorsed else None

    # -- withheld rules ------------------------------------------------------
    def _settle(self, d):
        self.survival_cycles = settle_survival_cycles(
            os.path.join(d, "demurrage_settlement.log"), self.cycle_index)
        (self.weather_stoppage, self.weather_rival,
         self.weather_fits, self.weather_obs) = settle_weather_stoppage(
            os.path.join(d, "laytime_observations.log"), self.laytime_rules)
        read_text(os.path.join(d, "errata_2032-04.md"))
        read_text(os.path.join(d, "legacy_terminal_handbook.md"))

    # -- helpers -------------------------------------------------------------
    def marker_count(self, tally):
        """Audit-log lines whose event token is the marker named after a tally."""
        return self.family_marker_count(self.audit_markers, tally)

    def family_marker_count(self, markers, tally):
        return sum(count for token, count in markers.items()
                   if marker_matches(token, tally))

    def resolve_charterer(self, raw, instant):
        """Canonical identity plus whether an epoch had to be chosen."""
        raw = (raw or "").strip()
        if not raw:
            return None, False
        if raw in self.charterers:
            return raw, False
        if raw in self.aliases and self.aliases[raw] in self.charterers:
            return self.aliases[raw], False
        cands = self.by_spelling.get(raw, [])
        if cands:
            if len(cands) == 1:
                return cands[0]["canonical"], False
            live = [c for c in cands
                    if (c["epoch_start"] is None or instant is None
                        or instant >= c["epoch_start"])
                    and (c["epoch_end"] is None or instant is None
                         or instant <= c["epoch_end"] + timedelta(days=1))]
            pick = (live or cands)[0]
            return pick["canonical"], True
        return None, False


# --------------------------------------------------------------------------
# Notice assembly
# --------------------------------------------------------------------------

class Scenario(object):
    """Counterfactual switches; the baseline leaves every one of them off."""

    def __init__(self, ignore_carried=False, weather=None, survival_delta=0,
                 no_clearing=False, lift_admission=False,
                 apply_unendorsed_circulars=False):
        self.ignore_carried = ignore_carried
        self.weather = weather
        self.survival_delta = survival_delta
        self.no_clearing = no_clearing
        self.lift_admission = lift_admission
        self.apply_unendorsed_circulars = apply_unendorsed_circulars


def source_key(name):
    return {"nor_log": "nor_log", "registry": "registry",
            "fixed_width_intake": "fixed_width",
            "state_events": "state_events",
            "port_circulars": "port_circulars"}.get(name, name)


def assemble(corpus, scn):
    """Collapse every source row into one record per Notice of Readiness."""
    admission = None if scn.lift_admission else corpus.admission

    def admissible(row):
        inst = row.get("recorded_instant")
        if inst is None or admission is None:
            return True
        return inst <= admission

    prec = corpus.precedence
    buckets = {}
    admitted_counts = {k: 0 for k in corpus.declared}
    for rows in (corpus.nor_log_rows, corpus.registry_rows, corpus.fixed_rows):
        for row in rows:
            key = source_key(row["source"])
            ok = admissible(row)
            if ok:
                admitted_counts[key] = admitted_counts.get(key, 0) + 1
            buckets.setdefault(row["nor_ref"], []).append((row, ok))

    events = {}
    for row in corpus.event_rows:
        ok = admissible(row)
        if ok:
            admitted_counts["state_events"] = \
                admitted_counts.get("state_events", 0) + 1
        events.setdefault(row["nor_ref"], []).append((row, ok))

    # circulars: endorsed, in scope at the audit instant, recorded after the
    # row they amend. Only those count (amendment_rules.md).
    circ_applied = 0
    for obj in corpus.circular_rows:
        tok = (obj.get("event") or "").strip()
        endorsement = (obj.get("endorsement") or "").strip().upper()
        if marker_matches(tok, "circulars_applied") and endorsement == "ENDORSED":
            circ_applied += 1
        elif scn.apply_unendorsed_circulars and \
                marker_matches(tok, "circulars_unendorsed"):
            circ_applied += 1
    admitted_counts["port_circulars"] = circ_applied
    admitted_counts["approval_audit"] = sum(
        1 for r in corpus.audit_rows
        if r["instant"] is None or admission is None or r["instant"] <= admission)

    notices = []
    for nor_ref in sorted(buckets):
        rows = buckets[nor_ref]
        live = [r for r, ok in rows if ok]
        ev = [r for r, ok in events.get(nor_ref, []) if ok]
        if not live and not ev:
            continue
        ordered = sorted(live, key=lambda r: prec.get(source_key(r["source"]), 99))

        def governing(field):
            for r in ordered:
                v = r.get(field)
                if v is not None and v != "":
                    return v
            return None

        rec = {
            "nor_ref": nor_ref,
            "cycle": governing("cycle"),
            "charterer_raw": governing("charterer"),
            "booked_berth": governing("booked_berth") or "",
            "raw_laytime": governing("laytime_hours"),
            "nor_ceiling": governing("ceiling_hours"),
            "instant": governing("recorded_instant"),
            "all_late": (not live) and bool(ev),
        }
        if rec["instant"] is None and ev:
            rec["instant"] = sorted(
                ev, key=lambda r: r["version"])[-1]["recorded_instant"]
        state = "ACCEPTED"
        if ev:
            state = sorted(ev, key=lambda r: r["version"])[-1]["state"] or "ACCEPTED"
        rec["state"] = state.upper()
        notices.append(rec)
    return notices, admitted_counts


# --------------------------------------------------------------------------
# substitution walk
# --------------------------------------------------------------------------

def berth_walk(corpus, cycle, booked, draft_ok):
    """Served berth and hop count. Draft permitting, the booked berth serves."""
    if draft_ok:
        return booked, 0, None
    frontier = [(booked, 0)]
    seen = {booked}
    while frontier:
        nxt = []
        for node, hops in frontier:
            if hops >= 3:
                continue
            for term in corpus.terminals:
                if term in seen:
                    continue
                if not corpus.pilotage.get((cycle, node, term), False):
                    continue
                seen.add(term)
                nxt.append((term, hops + 1))
        if nxt:
            best = sorted(nxt)[0]
            return best[0], best[1], None
        frontier = nxt
    return None, 0, "NO_QUALIFIED_BERTH"


# --------------------------------------------------------------------------
# allocation
# --------------------------------------------------------------------------

def pick_reason(codes, applicable):
    for code in codes:
        if code == "NONE":
            continue
        if code in applicable:
            return code
    return "NONE"


def allocate(claims, capacity):
    """Honoured minimums in register order, then one shared fill level,
    then the indivisible remainder one berth-hour at a time."""
    remaining = capacity
    paid = {}
    for item in sorted(claims, key=lambda c: (c["rank"], c["charterer"], c["nor_ref"])):
        want = min(item["minimum"], item["claim"], max(remaining, 0))
        paid[item["nor_ref"]] = want
        remaining -= want

    def total_at(level):
        return sum(min(c["claim"], paid[c["nor_ref"]] + level) for c in claims)

    ceiling = max([c["claim"] - paid[c["nor_ref"]] for c in claims] or [0])
    ceiling = max(ceiling, 0)
    level = 0
    if total_at(0) <= capacity:
        lo, hi = 0, ceiling
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if total_at(mid) <= capacity:
                lo = mid
            else:
                hi = mid - 1
        level = lo
    grants = {c["nor_ref"]: min(c["claim"], paid[c["nor_ref"]] + level)
              for c in claims}
    used = sum(grants.values())
    remainder = capacity - used
    handed = 0
    if remainder > 0:
        while remainder > 0:
            pool = [c for c in claims if c["claim"] - grants[c["nor_ref"]] > 0]
            if not pool:
                break
            pool.sort(key=lambda c: (-(c["claim"] - grants[c["nor_ref"]]),
                                     c["instant_key"], c["charterer"], c["nor_ref"]))
            grants[pool[0]["nor_ref"]] += 1
            remainder -= 1
            handed += 1
    return grants, paid, level, handed


def compute(corpus, scn=None):
    scn = scn or Scenario()
    notices, admitted_counts = assemble(corpus, scn)
    survival = corpus.survival_cycles + scn.survival_delta
    convention = scn.weather or corpus.weather_stoppage

    unknown_charterer, out_of_horizon = [], []
    prepared = []
    epoch_reassigned = 0
    for rec in notices:
        canon, reassigned = corpus.resolve_charterer(rec["charterer_raw"],
                                                     rec["instant"])
        if reassigned:
            epoch_reassigned += 1
        if rec["cycle"] not in corpus.cycle_index:
            out_of_horizon.append((rec, canon))
            continue
        if canon is None:
            unknown_charterer.append((rec, canon))
            continue
        rec["charterer"] = canon
        rec["segment"] = corpus.charterers[canon]["segment"]
        prepared.append(rec)

    # governing laytime: raw hours trimmed by the weather-stoppage convention
    # in force before the April cutover (laytime_rules.md scopes it there).
    for rec in prepared:
        raw = rec["raw_laytime"] or 0
        inst = rec["instant"]
        if inst is not None and corpus.cutover is not None and inst < corpus.cutover:
            rec["laytime"] = counted_hours(convention, inst, raw)
        else:
            rec["laytime"] = raw

    # served berth
    for rec in prepared:
        if not rec["booked_berth"]:
            rec["served"] = None
            rec["hops"] = 0
            rec["berth_reason"] = "BERTH_NOT_STATED"
            continue
        served, hops, why = berth_walk(corpus, rec["cycle"], rec["booked_berth"], True)
        rec["served"] = served
        rec["hops"] = hops
        rec["berth_reason"] = why

    by_cycle_term = {}
    for rec in prepared:
        by_cycle_term.setdefault((rec["cycle"], rec["served"]), []).append(rec)

    lots = {}          # (charterer, terminal) -> list of [raised_index, hours]
    ledger = {t: [] for t in corpus.terminals}
    cycle_stats = {t: {} for t in corpus.terminals}
    audit = {
        "lots_expired": 0, "lots_cleared": 0, "remainder_hours": 0,
        "cycles_with_remainder": 0, "epoch_reassignments": epoch_reassigned,
        "min_full": 0, "min_short": 0, "min_unmatched": 0,
        "no_qualified_berth_rows": 0,
    }
    running_max = 0
    running_end = 0

    for cycle in corpus.cycles:
        cidx = corpus.cycle_index[cycle]
        for term in corpus.terminals:
            # cycle opening: lots older than the settled survival age expire
            for key in list(lots):
                if key[1] != term:
                    continue
                keep = []
                for lot in lots[key]:
                    if cidx - lot[0] > survival:
                        audit["lots_expired"] += 1
                    else:
                        keep.append(lot)
                if keep:
                    lots[key] = keep
                else:
                    lots.pop(key, None)

            capacity = corpus.capacity.get((term, cycle), 0)
            rows = sorted(by_cycle_term.get((cycle, term), []),
                          key=lambda r: (r["charterer"], r["nor_ref"]))
            claims = []
            built = []
            for rec in rows:
                applicable = set()
                st = rec["state"]
                if st == "ON_HOLD":
                    applicable.add("ON_HOLD")
                elif st == "RETRACTED":
                    applicable.add("RETRACTED")
                elif st == "REJECTED":
                    applicable.add("REJECTED")
                if (rec["charterer"], term) in corpus.suspensions \
                        or (rec["charterer"], "") in corpus.suspensions:
                    applicable.add("CHARTERER_SUSPENDED")
                if capacity == 0:
                    applicable.add("CAP_ZERO")
                if rec.get("berth_reason"):
                    applicable.add(rec["berth_reason"])
                excluded = bool(applicable)
                reason = pick_reason(corpus.reason_codes, applicable)

                ceiling = corpus.ceilings.get((rec["charterer"], term))
                if ceiling is None:
                    ceiling = rec["nor_ceiling"]
                if ceiling is None:
                    ceiling = rec["laytime"]
                key = (rec["charterer"], term)
                lot_list = lots.get(key, [])
                carried_in = sum(l[1] for l in lot_list)
                if scn.ignore_carried:
                    carried_in_used = 0
                else:
                    carried_in_used = carried_in
                laytime = max(rec["laytime"], 0)
                lay_eff = min(laytime, ceiling)
                carried_eff = min(carried_in_used, max(ceiling - lay_eff, 0))
                claim = 0 if excluded else lay_eff + carried_eff
                minimum = 0
                if (rec["charterer"], term) not in corpus.exceptions_waived:
                    minimum = corpus.agreements.get((rec["charterer"], term), 0)
                built.append({
                    "rec": rec, "ceiling": ceiling, "carried_in": carried_in,
                    "carried_eff": carried_eff, "lay_eff": lay_eff,
                    "claim": claim, "excluded": excluded, "reason": reason,
                    "minimum": minimum,
                })
                if rec.get("berth_reason") == "NO_QUALIFIED_BERTH":
                    audit["no_qualified_berth_rows"] += 1
                if not excluded and claim > 0:
                    claims.append({
                        "nor_ref": rec["nor_ref"],
                        "charterer": rec["charterer"],
                        "claim": claim,
                        "minimum": minimum,
                        "rank": corpus.rank.get(rec["charterer"], 10 ** 6),
                        "instant_key": rec["instant"] or datetime(1, 1, 1),
                    })

            if claims:
                grants, paid, level, handed = allocate(claims, capacity)
            else:
                grants, paid, level, handed = {}, {}, 0, 0
            audit["remainder_hours"] += handed
            if handed > 0:
                audit["cycles_with_remainder"] += 1

            granted_total = sum(grants.values())
            residual = capacity - granted_total

            for item in built:
                rec = item["rec"]
                granted = grants.get(rec["nor_ref"], 0)
                key = (rec["charterer"], term)
                # the ceiling cuts the lot before the current claim
                if not scn.ignore_carried and item["carried_eff"] < item["carried_in"]:
                    cut = item["carried_in"] - item["carried_eff"]
                    lot_list = lots.get(key, [])
                    for lot in lot_list:
                        if cut <= 0:
                            break
                        take = min(cut, lot[1])
                        lot[1] -= take
                        cut -= take
                    lots[key] = [l for l in lot_list if l[1] > 0]
                    if not lots[key]:
                        lots.pop(key, None)
                # grants discharge the lot oldest first, then the current claim
                left = granted
                if not scn.ignore_carried:
                    lot_list = lots.get(key, [])
                    for lot in lot_list:
                        if left <= 0:
                            break
                        take = min(left, lot[1])
                        lot[1] -= take
                        left -= take
                    lots[key] = [l for l in lot_list if l[1] > 0]
                    if not lots[key]:
                        lots.pop(key, None)
                shortfall = max(item["lay_eff"] - left, 0)
                if shortfall > 0:
                    lots.setdefault(key, []).append([cidx, shortfall])
                demurrage = item["claim"] - granted
                carried_out = demurrage

                if item["excluded"]:
                    outcome = "EXCLUDED"
                elif granted >= item["claim"]:
                    outcome = "FULL"
                elif granted > 0:
                    outcome = "PARTIAL"
                else:
                    outcome = "ZERO"

                register_min = corpus.agreements.get((rec["charterer"], term))
                if register_min is None:
                    audit["min_unmatched"] += 1
                elif granted >= register_min:
                    audit["min_full"] += 1
                else:
                    audit["min_short"] += 1

                ledger[term].append({
                    "cycle": cycle,
                    "nor_ref": rec["nor_ref"],
                    "charterer": rec["charterer"],
                    "segment": rec["segment"],
                    "booked_berth": rec["booked_berth"],
                    "laytime_hours": max(rec["laytime"], 0),
                    "ceiling_hours": item["ceiling"],
                    "claim_hours": item["claim"],
                    "carried_in_hours": item["carried_in"],
                    "granted_hours": granted,
                    "demurrage_hours": demurrage,
                    "carried_out_hours": carried_out,
                    "granted_to_date_hours": 0,
                    "demurrage_to_date_hours": 0,
                    "served_berth": term if term else "",
                    "hops": rec["hops"],
                    "outcome": outcome,
                    "reason": item["reason"],
                    "granted_berthhours": granted * corpus.berth_hour_unit,
                    "minimum_hours": item["minimum"],
                    "_instant": rec["instant"],
                })

            # cycle end: unused capacity clears the lots outright
            if residual > 0 and not scn.no_clearing:
                for key in list(lots):
                    if key[1] == term:
                        audit["lots_cleared"] += len(lots[key])
                        lots.pop(key, None)

            cycle_stats[term][cycle] = {
                "cycle": cycle,
                "capacity_hours": capacity,
                "fill_level": level,
                "minimum_total_hours": sum(c["minimum"] for c in claims),
                "granted_hours": granted_total,
                "residual_hours": residual,
                "nor_count": len(built),
                "binding": bool(residual == 0 and capacity > 0),
            }

        total_open = sum(l[1] for v in lots.values() for l in v)
        running_max = max(running_max, total_open)
        running_end = total_open

    for term in corpus.terminals:
        ledger[term].sort(key=lambda r: (corpus.cycle_index[r["cycle"]],
                                         r["charterer"], r["nor_ref"]))
        gtd, dtd = {}, {}
        for row in ledger[term]:
            ch = row["charterer"]
            gtd[ch] = gtd.get(ch, 0) + row["granted_hours"]
            dtd[ch] = dtd.get(ch, 0) + row["demurrage_hours"]
            row["granted_to_date_hours"] = gtd[ch]
            row["demurrage_to_date_hours"] = dtd[ch]

    return {
        "ledger": ledger,
        "cycle_stats": cycle_stats,
        "audit": audit,
        "admitted": admitted_counts,
        "unknown_charterer": unknown_charterer,
        "out_of_horizon": out_of_horizon,
        "running_demurrage_max": running_max,
        "running_demurrage_end": running_end,
        "survival": survival,
        "convention": convention,
        "notices": prepared,
    }


# --------------------------------------------------------------------------
# documents
# --------------------------------------------------------------------------

LEDGER_FIELDS = [
    "cycle", "nor_ref", "charterer", "segment", "booked_berth", "laytime_hours",
    "ceiling_hours", "claim_hours", "carried_in_hours", "granted_hours",
    "demurrage_hours", "carried_out_hours", "granted_to_date_hours",
    "demurrage_to_date_hours", "served_berth", "hops", "outcome", "reason",
    "granted_berthhours", "minimum_hours",
]

CYCLE_FIELDS = ["cycle", "capacity_hours", "fill_level", "minimum_total_hours",
                "granted_hours", "residual_hours", "nor_count", "binding"]


def dump(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=False)
        fh.write("\n")


def build_documents(corpus, result, out_dir):
    ledger = result["ledger"]
    stats = result["cycle_stats"]
    audit = result["audit"]

    dq_tallies = ["header_gaps", "late_recorded", "null_forms",
                  "duplicate_identical", "duplicate_conflicting",
                  "cross_source_collapsed", "fold_disambiguated", "gap_shifted",
                  "log_continuations", "unknown_charterer_rows",
                  "out_of_horizon_rows", "block_unit_rows", "paren_negatives",
                  "restatement_gaps"]
    sources = {}
    for name in corpus.declared:
        sources[name] = {
            "declared": corpus.declared[name],
            "parsed": corpus.parsed.get(name, 0),
            "admitted": result["admitted"].get(name, 0),
        }
    dq = {}
    for tally in dq_tallies:
        dq[tally] = corpus.marker_count(tally)
    data_quality = {"sources": sources}
    for tally in dq_tallies:
        data_quality[tally] = dq[tally]

    all_rows = [r for t in corpus.terminals for r in ledger[t]]
    all_cycles = [c for t in corpus.terminals for c in stats[t].values()]

    before = sum(1 for r in all_rows
                 if r["_instant"] is not None and corpus.cutover is not None
                 and r["_instant"] < corpus.cutover)
    after = len(all_rows) - before

    policy = {
        "substitution_hops": corpus.marker_count("substitution_hops"),
        "substitution_cycles": corpus.marker_count("substitution_cycles"),
        "no_qualified_berth": corpus.marker_count("no_qualified_berth"),
        "resets": corpus.marker_count("resets"),
        "lots_expired": audit["lots_expired"],
        "lots_cleared": audit["lots_cleared"],
        "ceiling_binding": sum(1 for c in all_cycles
                               if c["residual_hours"] == 0 and c["capacity_hours"] > 0),
        "ceiling_zero": sum(1 for c in all_cycles if c["capacity_hours"] == 0),
        "epoch_reassignments": corpus.marker_count("epoch_reassignments"),
        "exceptions_applied": count_marker_rows(corpus.exception_rows, "exceptions_applied"),
        "exceptions_unendorsed": count_marker_rows(corpus.exception_rows, "exceptions_unendorsed"),
        "exceptions_retracted": count_marker_rows(corpus.exception_rows, "exceptions_retracted"),
        "illegal_transitions": corpus.family_marker_count(corpus.event_markers, "illegal_transitions"),
        "stale_events": corpus.family_marker_count(corpus.event_markers, "stale_events"),
        "duplicate_version_events": corpus.family_marker_count(corpus.event_markers, "duplicate_version_events"),
        "minimums_honoured_full": audit["min_full"],
        "minimums_honoured_short": audit["min_short"],
        "minimums_unmatched": audit["min_unmatched"],
        "circulars_applied": corpus.family_marker_count(corpus.circular_markers, "circulars_applied"),
        "circulars_early": corpus.family_marker_count(corpus.circular_markers, "circulars_early"),
        "circulars_unendorsed": corpus.family_marker_count(corpus.circular_markers, "circulars_unendorsed"),
        "circulars_retracted": corpus.family_marker_count(corpus.circular_markers, "circulars_retracted"),
        "circular_chains_unresolvable": corpus.family_marker_count(
            corpus.circular_markers, "circular_chains_unresolvable"),
        "cutover_sides": {"before": before, "after": after},
        "withheld": {"survival_cycles": result["survival"],
                     "weather_stoppage": result["convention"]},
    }

    id_cap = 0
    id_claim = 0
    id_run = 0
    for term in corpus.terminals:
        for row in ledger[term]:
            cyc = stats[term][row["cycle"]]
            if cyc["capacity_hours"] - cyc["granted_hours"] - cyc["residual_hours"] != 0:
                id_cap += 1
            if row["claim_hours"] - row["granted_hours"] - row["demurrage_hours"] != 0:
                id_claim += 1
            if row["carried_out_hours"] > row["carried_in_hours"] + row["laytime_hours"]:
                id_run += 1

    totals = {
        "granted_hours": sum(r["granted_hours"] for r in all_rows),
        "claim_hours": sum(r["claim_hours"] for r in all_rows),
        "demurrage_hours": sum(r["demurrage_hours"] for r in all_rows),
        "capacity_hours": sum(c["capacity_hours"] for c in all_cycles),
        "residual_hours": sum(c["residual_hours"] for c in all_cycles),
        "ledger_rows": len(all_rows),
        "cycles_with_remainder": audit["cycles_with_remainder"],
        "running_demurrage_max": result["running_demurrage_max"],
        "out_of_scope_rows": dq["unknown_charterer_rows"] + dq["out_of_horizon_rows"],
        "late_dropped": dq["late_recorded"],
        "identity_checks": {
            "capacity_minus_grant_minus_residual": id_cap,
            "claim_minus_grant_minus_demurrage": id_claim,
            "running_demurrage_falls": id_run,
        },
    }

    dump(os.path.join(out_dir, "summary.json"), {"totals": totals})
    dump(os.path.join(out_dir, "policy_audit.json"), policy)
    dump(os.path.join(out_dir, "data_quality.json"), data_quality)

    oos = {t: [] for t in corpus.terminals}
    for rec, canon in result["out_of_horizon"]:
        term = rec["booked_berth"] if rec["booked_berth"] in oos else corpus.terminals[0]
        oos[term].append({"nor_ref": rec["nor_ref"],
                          "charterer": canon or rec["charterer_raw"] or "",
                          "reason": "NONE"})
    for rec, canon in result["unknown_charterer"]:
        term = rec["booked_berth"] if rec["booked_berth"] in oos else corpus.terminals[0]
        oos[term].append({"nor_ref": rec["nor_ref"],
                          "charterer": canon or rec["charterer_raw"] or "",
                          "reason": "NONE"})

    for term in corpus.terminals:
        rows = []
        for row in ledger[term]:
            rows.append({k: row[k] for k in LEDGER_FIELDS})
        cycles = [{k: stats[term][c][k] for k in CYCLE_FIELDS}
                  for c in corpus.cycles]
        doc = {"terminal": term, "cycles": cycles, "ledger": rows,
               "out_of_scope": sorted(oos[term],
                                      key=lambda r: (r["charterer"], r["nor_ref"]))}
        dump(os.path.join(out_dir, "terminal_%s.json" % term), doc)

    segments = sorted({r["segment"] for r in all_rows} |
                      {c["segment"] for c in corpus.charterers.values() if c["segment"]})
    for seg in segments:
        by_term = {}
        granted = claim = 0
        for term in corpus.terminals:
            tot = 0
            for row in ledger[term]:
                if row["segment"] != seg:
                    continue
                tot += row["granted_hours"]
                claim += row["claim_hours"]
            by_term[term] = tot
            granted += tot
        dump(os.path.join(out_dir, "segment_%s.json" % seg),
             {"segment": seg,
              "totals": {"granted_hours": granted, "claim_hours": claim},
              "by_terminal": by_term})


def count_marker_rows(rows, tally):
    return sum(1 for r in rows
               if marker_matches((r.get("event") or "").strip(), tally))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    corpus = Corpus(args.data)
    result = compute(corpus, Scenario())
    if not os.path.isdir(args.out):
        os.makedirs(args.out)
    build_documents(corpus, result, args.out)


if __name__ == "__main__":
    main()
