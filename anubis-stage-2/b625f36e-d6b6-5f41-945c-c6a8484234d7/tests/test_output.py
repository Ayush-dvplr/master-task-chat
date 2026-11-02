"""Deterministic checker for the Marrowgate interval restatement task.

The verifier container does not carry the agent's corpus, so this module owns
the corpus builder and an implementation of the settlement rules and recomputes
every expected value from a seed. Two corpora are built: the one the agent was
given, and one it has never seen, which the delivered program is run against.
"""

from __future__ import annotations

import ast
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import unicodedata
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

from rewardkit import criteria, criterion

DAYS = ["20310308", "20310309", "20310310", "20310311",
        "20310312", "20310313", "20310314", "20310315"]
ZONES = ["EAST", "NORTH", "SOUTH", "WEST"]
# A zone the network carried at the time of the publication and has retired
# since. The baseline states cells for it and this run computes none.
RETIRED_ZONE = "CENTRAL"

CLASS_RANK = {"ORIGINAL": 0, "AMENDMENT": 1, "CORRECTION": 2,
              "REVERSAL": 3, "RESTATEMENT": 4}

FIELDS = ["event_key", "revision_no", "revision_class", "site_ref", "meter_id",
          "occurred_at", "ingested_at", "quantity", "delta_flag",
          "supersedes_revision"]

FIXED_COLS = [("event_key", 12), ("revision_no", 4), ("revision_class", 12),
              ("site_ref", 16), ("meter_id", 10), ("occurred_at", 22),
              ("ingested_at", 22), ("quantity", 14), ("delta_flag", 2),
              ("supersedes_revision", 4)]

PSV_ORDER = ["site_ref", "meter_id", "event_key", "revision_no",
             "revision_class", "occurred_at", "ingested_at",
             "quantity", "supersedes_revision", "delta_flag"]

BATCHES = (
    [("readings_desk_%02d.csv" % i, "csv") for i in range(1, 13)]
    + [("readings_import_%02d.jsonl" % i, "jsonl") for i in range(1, 10)]
    + [("readings_relay_%02d.tsv" % i, "tsv") for i in range(1, 7)]
    + [("readings_partner_%02d.psv" % i, "psv") for i in range(1, 5)]
    + [("readings_legacy_%02d.fixed" % i, "fixed") for i in range(1, 3)]
    + [("adjustments_%02d.jsonl" % i, "adj") for i in range(1, 4)]
    # One relay batch is redelivered under a fresh identity. It is registered
    # last, so every row it repeats is seen second and only the one revision
    # it adds has never been delivered before.
    + [("readings_relay_07.tsv", "tsv")]
)
BATCH_KIND = dict(BATCHES)
FAMILY = {"csv": "desk", "jsonl": "import", "tsv": "relay",
          "psv": "partner", "fixed": "legacy", "adj": "adjustment"}
BATCH_FAMILY = dict((n, FAMILY[k]) for n, k in BATCHES)

# The manifest registers the desk family out of alphabetical order, so reading
# the directory by file name and reading it in batch_seq order are different
# orders inside one family, and the first row read for a delivery identity
# differs between them.
_DESK_SEQ = [3, 7, 1, 9, 2, 11, 5, 12, 4, 8, 6, 10]
BATCH_SEQ = dict((n, i) for i, (n, _k) in enumerate(BATCHES, 1))
for _i, _s in enumerate(_DESK_SEQ, 1):
    BATCH_SEQ["readings_desk_%02d.csv" % _i] = _s

WITHDRAWN_BATCHES = ("readings_desk_09.csv", "readings_import_07.jsonl",
                     "readings_relay_05.tsv")
GHOST_BATCH = "readings_desk_13.csv"
UNLISTED_BATCH = "readings_desk_90.csv"
REPLAY_BATCH = "readings_relay_07.tsv"
REPLAY_SOURCE = "readings_relay_03.tsv"

# A batch that was withdrawn and later reinstated carries more than one
# manifest row for the one filename. Membership is decided row by row, so a
# retired registration sits beside the live one and neither cancels it.
REINSTATED_LOW = "readings_import_02.jsonl"
REINSTATED_HIGH = "readings_desk_04.csv"

# The partner system stamps its readings in the local offset its operator
# keeps, so those instants have to be carried to UTC before anything is read
# off them.
PARTNER_OFFSET = "+05:30"

REASON_CODES = ("BAD_QUANTITY", "BAD_TIMESTAMP", "MALFORMED_ROW",
                "METER_SITE_MISMATCH", "OUT_OF_CALENDAR", "UNKNOWN_METER",
                "UNKNOWN_SITE")

DAY_OPEN = "T06:00:00Z"

# Written instants that have the shape of the Z form and name a day the
# Gregorian calendar does not have. 2031 is not a leap year.
BAD_DATES = ("2031-02-29T10:00:00Z", "2031-02-30T12:00:00Z",
             "2031-04-31T09:30:00Z", "2031-06-31T08:00:00Z")

# Producing systems that wrote a byte order mark ahead of the first line, and
# one that ends every line with a carriage return before the line feed.
BOM_BATCHES = ("readings_desk_05.csv", "readings_import_04.jsonl")
CRLF_BATCHES = ("readings_relay_02.tsv",)


# --------------------------------------------------------------------------
# instants
# --------------------------------------------------------------------------

def _iso(day_idx: int, hour: int, minute: int, second: int = 0) -> str:
    """An instant inside settlement day ``day_idx``; hours run 0..23 from 06:00Z."""
    base = 8 + day_idx
    h = 6 + hour
    if h >= 24:
        h -= 24
        base += 1
    return "2031-03-%02dT%02d:%02d:%02dZ" % (base, h, minute, second)


def _month_length(y, mo):
    """Days in a Gregorian month, so a date the calendar never had does not
    parse as an instant at all."""
    if mo == 2:
        leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
        return 29 if leap else 28
    return 30 if mo in (4, 6, 9, 11) else 31


def parse_instant(s):
    """Return a comparable integer for an instant, or None. Two written forms
    are accepted: the Z form, and a fixed offset form carrying a trailing
    +HH:MM or -HH:MM naming the shift that reaches the reading as written from
    UTC."""
    if not isinstance(s, str):
        return None
    offset = 0
    if len(s) == 25 and s[19] in "+-" and s[22] == ":":
        try:
            oh, om = int(s[20:22]), int(s[23:25])
        except ValueError:
            return None
        if oh > 23 or om > 59:
            return None
        offset = (oh * 3600 + om * 60) * (1 if s[19] == "+" else -1)
        s = s[:19] + "Z"
    if len(s) != 20 or s[-1] != "Z" or s[10] != "T":
        return None
    try:
        y, mo, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
        h, mi, sec = int(s[11:13]), int(s[14:16]), int(s[17:19])
    except ValueError:
        return None
    if s[4] != "-" or s[7] != "-" or s[13] != ":" or s[16] != ":":
        return None
    if not (1 <= mo <= 12 and 1 <= d <= _month_length(y, mo)
            and h <= 23 and mi <= 59 and sec <= 59):
        return None
    days = (y * 372) + ((mo - 1) * 31) + (d - 1)
    return ((days * 24 + h) * 60 + mi) * 60 + sec - offset


def _as_offset(text, offset):
    """Re-stamp a Z instant in a fixed offset form. Anything that is not a well
    formed Z instant is handed back exactly as it was delivered."""
    if offset is None or not isinstance(text, str) or len(text) != 20:
        return text
    if text[-1] != "Z" or text[10] != "T":
        return text
    t = parse_instant(text)
    if t is None:
        return text
    sign = 1 if offset[0] == "+" else -1
    t += (int(offset[1:3]) * 3600 + int(offset[4:6]) * 60) * sign
    days, rest = divmod(t, 86400)
    h, rest = divmod(rest, 3600)
    mi, sec = divmod(rest, 60)
    y, rem = divmod(days, 372)
    mo, d = divmod(rem, 31)
    return "%04d-%02d-%02dT%02d:%02d:%02d%s" % (
        y, mo + 1, d + 1, h, mi, sec, offset)


def settlement_day(occurred_at):
    """Settlement day key for an instant, on the half-open window that opens
    at 06:00:00Z. Returns None when the instant falls outside the calendar."""
    t = parse_instant(occurred_at)
    if t is None:
        return None
    shifted = t - 6 * 3600
    for i, key in enumerate(DAYS):
        lo = parse_instant("2031-03-%02dT06:00:00Z" % (8 + i)) - 6 * 3600
        if lo <= shifted < lo + 86400:
            return key
    return None


def normalize_ref(s):
    """Documented join normalization: NFC, casefold, collapse internal runs of
    whitespace and of hyphen padding, strip, upper."""
    if not isinstance(s, str):
        return ""
    t = unicodedata.normalize("NFC", s)
    t = t.replace("\t", " ")
    t = " ".join(t.split())
    t = t.replace(" - ", "-").replace("- ", "-").replace(" -", "-")
    return t.strip().casefold().upper()


# --------------------------------------------------------------------------
# corpus construction
# --------------------------------------------------------------------------

def _mangle(rng, site):
    r = rng.random()
    if r < 0.62:
        return site
    if r < 0.72:
        return "  %s " % site
    if r < 0.80:
        return site.lower()
    if r < 0.86:
        return site.replace("-", " - ")
    if r < 0.92:
        return "\t%s\t" % site.lower()
    return unicodedata.normalize("NFD", site)


def build_state(seed):
    rng = random.Random(seed)
    sites = ["MG-%04d" % i for i in range(1, 421)]
    # A dozen sites carry the district's accented code form. Several producing
    # systems emit them decomposed, so a join that skips NFC composition drops
    # every row those systems delivered for them.
    for idx in range(407, 419):
        sites[idx] = "MG-Å%03d" % (idx + 1)
    meters = {}
    for i, s in enumerate(sites):
        meters[s] = "MTR-%04d" % (2000 + i)

    sites_effective = []
    for s in sites:
        sites_effective.append({
            "site_id": s, "valid_from": "2031-01-01T00:00:00Z",
            "valid_to": "2031-03-11T06:00:00Z",
            "tariff_class": rng.choice(["TC-A", "TC-B", "TC-C"]),
            "zone": rng.choice(ZONES)})
        sites_effective.append({
            "site_id": s, "valid_from": "2031-03-11T06:00:00Z",
            "valid_to": "2032-01-01T00:00:00Z",
            "tariff_class": rng.choice(["TC-A", "TC-B", "TC-C", "TC-D"]),
            "zone": rng.choice(ZONES)})

    merges = []
    merge_map = {}
    pool = sites[110:400]
    for i in range(0, 280, 2):
        a, b = pool[i], pool[i + 1]
        inst = _iso(rng.randrange(1, 7), rng.randrange(0, 22), rng.randrange(0, 60))
        merges.append({"absorbed_site": a, "survivor_site": b, "merge_instant": inst})
        merge_map[a] = (b, inst)
    instant_merges = [(m["absorbed_site"], m["merge_instant"]) for m in merges]
    far = sites[5:125]
    for i in range(0, 120, 2):
        a, b = far[i], far[i + 1]
        merges.append({"absorbed_site": a, "survivor_site": b,
                       "merge_instant": "2031-06-%02dT%02d:00:00Z"
                                        % (1 + (i % 28), rng.randrange(0, 24))})
        merge_map[a] = (b, None)
    # chained hops: a survivor is itself absorbed later
    for i in range(0, 140, 20):
        a2 = sites[400 + (i // 20)]
        surv = pool[i + 1]
        inst2 = _iso(rng.randrange(3, 7), rng.randrange(0, 22), rng.randrange(0, 60))
        merges.append({"absorbed_site": a2, "survivor_site": surv,
                       "merge_instant": inst2})
        merge_map[a2] = (surv, inst2)
    # Deep chains: three sites in a row, both hops dated inside the calendar,
    # so an event late enough in the window resolves through two hops and an
    # event between the two instants stops after the first.
    deep_heads = []
    for k in range(4):
        a, b, c = sites[407 + 3 * k], sites[408 + 3 * k], sites[409 + 3 * k]
        t1 = _iso(0, 1, 5 + k)
        t2 = _iso(1, 3, 11 + k)
        merges.append({"absorbed_site": a, "survivor_site": b,
                       "merge_instant": t1})
        merge_map[a] = (b, t1)
        merges.append({"absorbed_site": b, "survivor_site": c,
                       "merge_instant": t2})
        merge_map[b] = (c, t2)
        deep_heads.append(a)

    # A survivor that is itself absorbed back into the site it absorbed, so the
    # merge history carries a closed loop. The two hops are dated apart, so an
    # event between them resolves exactly one hop, and an event at or after the
    # later hop would walk for ever. The walk stops when it reaches a site it
    # has already left, and the site it has reached stands as the canonical one.
    cycle_heads = []
    for k in range(2):
        a, b = sites[2 * k], sites[2 * k + 1]
        t1 = _iso(k, 2, 0)
        t2 = _iso(4 + k, 2, 0)
        merges.append({"absorbed_site": a, "survivor_site": b,
                       "merge_instant": t1})
        merge_map[a] = (b, t1)
        merges.append({"absorbed_site": b, "survivor_site": a,
                       "merge_instant": t2})
        merge_map[b] = (a, t2)
        cycle_heads.append(a)

    op_state = []
    suspended = set(rng.sample(sites, 38))
    for s in sites:
        if s in suspended:
            cut = _iso(rng.randrange(1, 6), rng.randrange(0, 20), 0)
            op_state.append({"site_id": s, "valid_from": "2031-01-01T00:00:00Z",
                             "valid_to": cut, "state": "ACTIVE"})
            op_state.append({"site_id": s, "valid_from": cut,
                             "valid_to": "2032-01-01T00:00:00Z",
                             "state": "SUSPENDED"})
        else:
            op_state.append({"site_id": s, "valid_from": "2031-01-01T00:00:00Z",
                             "valid_to": "2032-01-01T00:00:00Z", "state": "ACTIVE"})

    # The pulse multiplier a site's meter applies: the whole number of
    # metered units one delivered count stands for. The interval ceiling is
    # proportional to it, so the clamp bites in the same place whatever the
    # multiplier is, and only the arithmetic changes.
    multipliers = {}
    for s in sites:
        multipliers[s] = rng.choices([1, 2, 3, 4], weights=[52, 20, 16, 12])[0]

    def _open(idx):
        """The instant settlement day ``idx`` opens, in the Z form."""
        return "2031-03-%02dT06:00:00Z" % (8 + idx)

    limit_rows = {}
    for s in sites:
        lo = rng.choice([180000, 240000, 300000, 360000]) * multipliers[s]
        limit_rows[s] = [
            {"site_id": s, "valid_from": "2031-01-01T00:00:00Z",
             "valid_to": "2031-03-12T06:00:00Z", "max_interval_wh": lo},
            {"site_id": s, "valid_from": "2031-03-12T06:00:00Z",
             "valid_to": "2032-01-01T00:00:00Z",
             "max_interval_wh": lo + rng.choice([0, 60000, 120000])
                                * multipliers[s]}]

    # Sites whose ceiling file carries a gap: no row at all covers one whole
    # settlement day, so an event whose effective instant lands in the hole
    # has no ceiling and the protocol leaves it unresolvable. A ceiling that
    # is absent is not a ceiling of zero.
    standing = [s for s in sites if s not in merge_map]
    gap_sites = rng.sample(standing, 30)
    ceiling_gap = {}
    for s in gap_sites:
        hole = rng.choice([1, 2, 4, 5, 6])
        ceiling_gap[s] = hole
        rows = limit_rows[s]
        if hole <= 2:
            rows[0]["valid_to"] = _open(hole)
            rows.insert(1, {"site_id": s, "valid_from": _open(hole + 1),
                            "valid_to": "2031-03-12T06:00:00Z",
                            "max_interval_wh": rows[0]["max_interval_wh"]})
        else:
            rows[1]["valid_from"] = _open(hole + 1)
            rows.insert(1, {"site_id": s, "valid_from": "2031-03-12T06:00:00Z",
                            "valid_to": _open(hole),
                            "max_interval_wh": rows[1]["max_interval_wh"]})

    # Four of those holes are closed for half of the day by a narrow row, so
    # the gap is real for part of the settlement day and not for the rest.
    for s in gap_sites[:4]:
        limit_rows[s].append(
            {"site_id": s, "valid_from": _iso(ceiling_gap[s], 6, 0),
             "valid_to": _iso(ceiling_gap[s], 18, 0),
             "max_interval_wh": 120000 * multipliers[s]})

    # A ceiling corrected in place: a narrow row carrying a lower ceiling over
    # a window the long row already covers. Two rows cover those instants and
    # the one whose valid_from is the latest governs, so the correction
    # decides the clamp while it lasts. Half of these corrections are written
    # ahead of the row they correct and half behind it.
    limit_fix = rng.sample([s for s in standing if s not in ceiling_gap], 18)
    for position, s in enumerate(limit_fix):
        day = rng.randrange(0, 7)
        patch = {"site_id": s, "valid_from": _open(day),
                 "valid_to": _open(day + 2),
                 "max_interval_wh": 30000 * multipliers[s]}
        limit_rows[s].insert(0 if position % 2 == 0 else len(limit_rows[s]),
                             patch)

    limits = []
    for s in sites:
        limits.extend(limit_rows[s])

    # An operational state corrected in place, in both directions: a narrow
    # SUSPENDED window inside a standing ACTIVE row, and a narrow ACTIVE
    # window inside a standing SUSPENDED row.
    op_patches = []
    for position, s in enumerate(rng.sample([s for s in sites
                                             if s not in suspended], 14)):
        day = rng.randrange(0, 7)
        op_patches.append((position, {"site_id": s, "valid_from": _open(day),
                                      "valid_to": _open(day + 2),
                                      "state": "SUSPENDED"}))
    for position, s in enumerate(rng.sample(sorted(suspended), 8)):
        op_patches.append((position, {"site_id": s, "valid_from": _open(7),
                                      "valid_to": _open(8),
                                      "state": "ACTIVE"}))
    for position, patch in op_patches:
        if position % 2 == 0:
            op_state.insert(0, patch)
        else:
            op_state.append(patch)

    # A zone and a tariff class corrected in place. A window opening exactly
    # where the standing row opens is decided by the narrower valid_to rather
    # than by the file order or by the valid_from the two rows share.
    eff_index = {}
    for position, row in enumerate(sites_effective):
        eff_index.setdefault(row["site_id"], []).append(position)
    for position, s in enumerate(rng.sample(sites, 26)):
        day = rng.choice([0, 1, 3, 4, 5, 6])
        standing_row = sites_effective[eff_index[s][0 if day < 3 else 1]]
        zone = rng.choice([z for z in ZONES if z != standing_row["zone"]])
        klass = rng.choice([c for c in ["TC-A", "TC-B", "TC-C", "TC-D"]
                            if c != standing_row["tariff_class"]])
        patch = {"site_id": s, "valid_from": _open(day),
                 "valid_to": _open(day + 2), "tariff_class": klass,
                 "zone": zone}
        if position % 2 == 0:
            sites_effective.insert(0, patch)
        else:
            sites_effective.append(patch)

    # A couple of dozen sites swap their meter inside the calendar. The
    # registry keeps the row for the meter that went out as well as the row
    # for the one that came in, so the meter_id of a reading is present in the
    # file whichever side of the swap the reading falls on, and only the window
    # says whether that meter was the site's meter when the reading happened.
    meter_swaps = {}
    for s in rng.sample(sites, 24):
        meter_swaps[s] = _iso(rng.randrange(1, 7), 0, 0)

    def _registration(meter, site, lo, hi, mult):
        return {"meter_id": meter, "site_id": site, "valid_from": lo,
                "valid_to": hi, "pulse_multiplier": mult,
                "model": "MX-" + site[-2:]}

    registry = []
    for s in sites:
        cut = meter_swaps.get(s)
        mult = str(multipliers[s])
        if cut is None:
            registry.append(_registration(meters[s], s,
                                          "2031-01-01T00:00:00Z",
                                          "2032-01-01T00:00:00Z", mult))
        else:
            registry.append(_registration("MTR-7" + meters[s][-3:], s,
                                          "2031-01-01T00:00:00Z", cut, mult))
            registry.append(_registration(meters[s], s, cut,
                                          "2032-01-01T00:00:00Z", mult))

    # Registry corrections. A pulse multiplier moved for a window, a
    # registration that names another site for a window, an unreadable
    # correction over a readable row, and an unreadable row that is the only
    # row covering its window at all.
    unreadable = ("", "0", "-2", "1.5", "\u0663", "1_0", "+3", "3 ")
    plain = [s for s in sites if s not in meter_swaps]
    picked = rng.sample(plain, 42)
    mult_fix = picked[:12]
    site_fix = picked[12:20]
    bad_overlap = picked[20:31]
    bad_hole = picked[31:42]
    registry_patches = []
    for position, s in enumerate(mult_fix + site_fix + bad_overlap):
        day = rng.randrange(0, 7)
        if s in mult_fix:
            named, mult = s, str(multipliers[s] + rng.choice([1, 2, 3]))
        elif s in site_fix:
            named = rng.choice([o for o in plain if o != s])
            mult = str(multipliers[s])
        else:
            named, mult = s, rng.choice(unreadable)
        registry_patches.append(
            (position, _registration(meters[s], named, _open(day),
                                     _open(day + 2), mult)))
    for s in bad_hole:
        day = rng.randrange(0, 7)
        for row in registry:
            if row["meter_id"] == meters[s]:
                row["valid_to"] = _open(day)
                break
        registry.append(_registration(meters[s], s, _open(day + 2),
                                      "2032-01-01T00:00:00Z",
                                      str(multipliers[s])))
        registry_patches.append(
            (1, _registration(meters[s], s, _open(day), _open(day + 2),
                              rng.choice(unreadable))))
    for position, patch in registry_patches:
        if position % 2 == 0:
            registry.insert(0, patch)
        else:
            registry.append(patch)

    return {"rng": rng, "sites": sites, "meters": meters,
            "sites_effective": sites_effective, "merges": merges,
            "merge_map": merge_map, "op_state": op_state, "limits": limits,
            "deep_heads": deep_heads, "cycle_heads": cycle_heads,
            "meter_swaps": meter_swaps, "instant_merges": instant_merges,
            "multipliers": multipliers, "registry": registry,
            "gap_sites": gap_sites, "ceiling_gap": ceiling_gap}


def build_revisions(st):
    rng = st["rng"]
    sites = st["sites"]
    meters = st["meters"]
    merged = sorted(st["merge_map"].keys())
    rows = []

    for n in range(1, 4901):
        key = "EV-%06d" % n
        forced_day = None
        forced_occ = None
        if n % 37 == 0:
            site = st["deep_heads"][(n // 37) % 4]
        elif n % 41 == 0:
            # Half of these sit between the two hops of the closed loop and so
            # resolve exactly one hop. The other half sit at or after the hop
            # that closes the loop, where a walk with no guard never ends.
            site = st["cycle_heads"][(n // 41) % 2]
            forced_day = 2 if (n // 82) % 2 == 0 else 6
        elif n % 97 == 0:
            # An event that occurs exactly at the instant its site is
            # absorbed. A merge applies at or after its own instant, so the
            # hop is taken, and a strict comparison declines it.
            site, forced_occ = st["instant_merges"][(n // 97)
                                                    % len(st["instant_merges"])]
            forced_day = DAYS.index(settlement_day(forced_occ))
        elif n % 43 == 0:
            # An event on a site whose ceiling file carries a hole, dated
            # inside that hole. The protocol leaves it unresolvable, and a
            # reader that treats the absent row as a ceiling of zero settles
            # it at zero instead.
            site = st["gap_sites"][(n // 43) % len(st["gap_sites"])]
            forced_day = st["ceiling_gap"][site]
        elif n % 17 == 0:
            site = merged[n % len(merged)]
        else:
            site = rng.choice(sites)
        meter = meters[site]
        day = forced_day if forced_day is not None else rng.randrange(0, 8)
        if forced_occ is not None:
            occ = forced_occ
        elif n % 53 == 0:
            pick = n % 5
            if pick == 0:
                occ = _iso(day, 0, 0, 0)
            elif pick == 1:
                occ = _iso(day, 23, 59, 59)
            elif pick == 2:
                occ = _iso(day, 24, 0, 0)
            elif pick == 3:
                # Exactly midnight UTC, which falls inside the settlement day
                # that opened eighteen hours earlier, so the date portion of
                # the instant and the settlement day differ by one day.
                occ = _iso(day, 18, 0, 0)
            else:
                occ = _iso(day, 17, 59, 59)
        else:
            occ = _iso(day, rng.randrange(0, 24), rng.randrange(0, 60),
                       rng.randrange(0, 60))

        n_rev = rng.choices([1, 2, 3, 4], weights=[46, 30, 17, 7])[0]
        if n % 31 == 0:
            n_rev = 3 if n % 62 == 0 else 4
        if n % 23 == 0:
            # A quantity that lands exactly on the half once it is carried to
            # the governing decimal place, so the rounding mode decides the
            # figure and a half up reading parts company with a half even one.
            base_kwh = Decimal(rng.randrange(400, 62000) * 10 + 5) / Decimal(1000)
        elif n % 29 == 0:
            # Four decimal places ending in five: the watt-hour value lands
            # exactly on a half, so the conversion's rounding mode decides it.
            # Round half to even keeps an even integer where round half up
            # moves to the odd one above it.
            base_kwh = (Decimal(rng.randrange(40000, 620000) * 10 + 5)
                        / Decimal(10000))
        else:
            base_kwh = Decimal(rng.randrange(400, 62000)) / Decimal(100)
        if n % 89 == 0:
            # A meter that rolled back delivers a negative absolute reading.
            # The first clamp raises it to zero.
            base_kwh = -base_kwh
        rev_nos = rng.sample(range(1, 9), n_rev)
        if n % 79 == 0 and n_rev >= 2:
            # every admitted revision of this event is a restatement, so the
            # event carries no base at all
            classes = ["RESTATEMENT"] * n_rev
        elif n % 31 == 0 and n_rev >= 3:
            # A run of restatements in which each one names the one
            # before it. A restatement that names another restatement of
            # the same event displaces it, so the delta it names never
            # reaches the figure, and a restatement that is itself
            # displaced still displaces the one it names.
            classes = ["ORIGINAL"] + ["RESTATEMENT"] * (n_rev - 1)
        elif n % 61 == 0 and n_rev >= 3:
            # Two reversals of one event. A reversal reverses the event and a
            # second reversal reverses the first, so the pair composes back to
            # nothing and the event settles on its base rather than standing
            # reversed.
            classes = ["ORIGINAL", "REVERSAL", "REVERSAL"]
            for _ in range(n_rev - 3):
                classes.append(rng.choice(["AMENDMENT", "CORRECTION"]))
        else:
            classes = ["ORIGINAL"]
            for _ in range(n_rev - 1):
                classes.append(rng.choices(
                    ["AMENDMENT", "CORRECTION", "REVERSAL", "RESTATEMENT"],
                    weights=[42, 30, 11, 17])[0])

        chain = {}
        if n % 31 == 0:
            stack_idx = [i for i in range(n_rev)
                         if classes[i] == "RESTATEMENT"]
            for _a, _b in zip(stack_idx, stack_idx[1:]):
                chain[_b] = rev_nos[_a]

        for idx in range(n_rev):
            cls = classes[idx]
            rno = rev_nos[idx]
            ing = _iso(min(7, day + rng.randrange(0, 3)),
                       rng.randrange(0, 24), rng.randrange(0, 60))
            sup = ""
            if cls in ("CORRECTION", "RESTATEMENT"):
                others = [r for i, r in enumerate(rev_nos) if i != idx]
                if idx in chain:
                    sup = str(chain[idx])
                elif others and rng.random() > 0.09:
                    sup = str(rng.choice(others))
                else:
                    sup = str(rng.randrange(20, 40))
            if cls == "RESTATEMENT":
                qty = Decimal(rng.randrange(-26000, 34000)) / Decimal(100)
                flag = "1"
            elif cls == "REVERSAL":
                qty = base_kwh
                flag = "0"
            else:
                qty = base_kwh + Decimal(rng.randrange(-300, 300)) / Decimal(100)
                flag = "0"
            null_q = rng.random() < 0.035
            rows.append({
                "event_key": key, "revision_no": rno, "revision_class": cls,
                "site_ref": _mangle(rng, site), "meter_id": meter,
                "occurred_at": occ, "ingested_at": ing,
                "quantity": None if null_q else qty,
                "delta_flag": flag, "supersedes_revision": sup,
                "_kind": "clean",
                "_fam": ("adjustment"
                         if (cls in ("CORRECTION", "RESTATEMENT")
                             and rng.random() < 0.34)
                         else rng.choices(
                             ["desk", "import", "relay", "partner", "legacy"],
                             weights=[12, 9, 6, 4, 2])[0])})

    clean = [r for r in rows if r["_kind"] == "clean"]
    for r in rng.sample(clean, 330):
        d = dict(r)
        d["_kind"] = "duplicate"
        # A redelivery written by a different formatter. The value it carries
        # is the value the original carried, so the payload is the same even
        # though the characters are not.
        if isinstance(d["quantity"], Decimal) and rng.random() < 0.4:
            d["_qtext"] = _alt_numeral(rng, d["quantity"],
                                       d["_fam"] == "adjustment")
        if rng.random() < 0.12:
            d["_rtext"] = "0" + str(d["revision_no"])
            if d["supersedes_revision"]:
                d["_stext"] = "0" + d["supersedes_revision"]
        rows.append(d)
    for r in rng.sample(clean, 175):
        c = dict(r)
        c["_kind"] = "conflict"
        if c["quantity"] is None:
            c["quantity"] = Decimal(rng.randrange(500, 90000)) / Decimal(100)
        else:
            c["quantity"] = c["quantity"] + Decimal(rng.randrange(11, 900)) / Decimal(100)
        rows.append(c)
    # Redeliveries whose reading moved by a tenth of a watt-hour. Carried to
    # whole watt-hours both readings land on the same integer, and they are
    # still two different values, so the later one conflicts.
    fine = [r for r in clean
            if r["_fam"] != "adjustment" and isinstance(r["quantity"], Decimal)
            and r["quantity"].as_tuple().exponent >= -3]
    for r in rng.sample(fine, 48):
        c = dict(r)
        c["_kind"] = "conflict"
        c["quantity"] = r["quantity"] + (Decimal("0.0001")
                                         if r["quantity"] >= 0
                                         else Decimal("-0.0001"))
        rows.append(c)
    all_fams = ["adjustment", "desk", "import", "legacy", "partner", "relay"]
    for r in rng.sample(clean, 260):
        t = dict(r)
        t["_kind"] = "crossfamily"
        others = [f for f in all_fams if f != r["_fam"]]
        t["_fam"] = rng.choice(others)
        if t["quantity"] is None:
            t["quantity"] = Decimal(rng.randrange(500, 90000)) / Decimal(100)
        else:
            t["quantity"] = t["quantity"] + Decimal(rng.randrange(150, 5000)) / Decimal(100)
        rows.append(t)

    # A meter that is registered, whose registration covers the instant,
    # and whose registration names a site other than the one the reading
    # denotes. Such a row clears check seven and falls at check eight.
    swapped = set(st["meter_swaps"])

    def _foreign_meter(rec):
        own = normalize_ref(rec["site_ref"])
        pool = [s for s in sites
                if s not in swapped and normalize_ref(s) != own]
        return meters[rng.choice(pool)]

    bad_specs = [("BAD_TIMESTAMP", 104), ("BAD_QUANTITY", 96),
                 ("UNKNOWN_SITE", 74), ("UNKNOWN_METER", 68),
                 ("METER_SITE_MISMATCH", 72),
                 ("OUT_OF_CALENDAR", 60), ("MALFORMED_ROW", 56)]
    for code, count in bad_specs:
        for _ in range(count):
            src = dict(rng.choice(clean))
            src["_kind"] = "bad"
            src["_fam"] = rng.choices(
                ["adjustment", "desk", "import", "legacy", "partner", "relay"],
                weights=[3, 12, 9, 2, 4, 6])[0]
            src["event_key"] = "EV-%06d" % rng.randrange(700000, 999999)
            if code == "BAD_TIMESTAMP":
                src["occurred_at"] = rng.choice(
                    ["2031-03-09 14:20:00", "31/03/2031T04:00:00Z",
                     "2031-13-40T99:00:00Z", "2031-03-09T14:20Z"])
            elif code == "BAD_QUANTITY":
                src["quantity"] = rng.choice(["1;240.5", "12.5kWh", "--", "1.2.3"])
            elif code == "UNKNOWN_SITE":
                src["site_ref"] = "MG-%04d" % rng.randrange(9000, 9999)
            elif code == "UNKNOWN_METER":
                src["meter_id"] = "MTR-%04d" % rng.randrange(9000, 9999)
            elif code == "METER_SITE_MISMATCH":
                src["meter_id"] = _foreign_meter(src)
            elif code == "OUT_OF_CALENDAR":
                src["occurred_at"] = rng.choice(
                    ["2031-02-27T10:00:00Z", "2031-04-02T09:30:00Z",
                     "2031-03-16T12:00:00Z"])
            else:
                src["revision_class"] = rng.choice(["FIXUP", "", "original"])
            rows.append(src)

    # Values a permissive numeric parser accepts and the documented grammar
    # does not. Each one lands in a family whose unit makes it invalid: an
    # exponent, a special value, a digit group separator or a bare point in
    # a kilowatt hour family, and a fraction or an exponent in the watt hour
    # family.
    lenient = [("kwh", ["1.25E+1", "NaN", "Infinity", "12.", ".75", "1_204.5",
                        "-inf", "4e2"], 64),
               ("wh", ["1200.0", "1.2E3", "+12.5", "350.", "1_200"], 40)]
    for unit, forms, count in lenient:
        for _ in range(count):
            src = dict(rng.choice(clean))
            src["_kind"] = "bad"
            src["_fam"] = ("adjustment" if unit == "wh" else rng.choice(
                ["desk", "import", "legacy", "partner", "relay"]))
            src["event_key"] = "EV-%06d" % rng.randrange(700000, 999999)
            src["quantity"] = rng.choice(forms)
            src["_qtext"] = None
            rows.append(src)

    # revision_no forms that str.isdigit and int() accept and the documented
    # grammar rejects, beside forms that fail any reading.
    for _ in range(46):
        src = dict(rng.choice(clean))
        src["_kind"] = "bad"
        src["_fam"] = rng.choice(["desk", "import", "relay", "partner",
                                  "adjustment"])
        src["event_key"] = "EV-%06d" % rng.randrange(700000, 999999)
        src["_rtext"] = rng.choice(["\u0663", "\uff14", "\u0967", "0", "00",
                                    "+3", "-2", "2.0"])
        rows.append(src)

    # Dates the calendar never had. They are well formed on the page, so a
    # reading that only checks the shape passes them to the calendar test.
    for _ in range(40):
        src = dict(rng.choice(clean))
        src["_kind"] = "bad"
        src["_fam"] = rng.choice(["desk", "import", "relay", "legacy",
                                  "adjustment"])
        src["event_key"] = "EV-%06d" % rng.randrange(700000, 999999)
        src["occurred_at"] = rng.choice(BAD_DATES)
        rows.append(src)

    def _injure(rec, code):
        if code == "BAD_TIMESTAMP":
            rec["occurred_at"] = rng.choice(["2031-03-09 14:20:00",
                                             "2031-03-09T14:20Z"])
        elif code == "BAD_QUANTITY":
            rec["quantity"] = rng.choice(["12.5kWh", "1.2.3"])
        elif code == "UNKNOWN_SITE":
            rec["site_ref"] = "MG-%04d" % rng.randrange(9000, 9999)
        elif code == "UNKNOWN_METER":
            rec["meter_id"] = "MTR-%04d" % rng.randrange(9000, 9999)
        elif code == "METER_SITE_MISMATCH":
            rec["meter_id"] = _foreign_meter(rec)
        elif code == "OUT_OF_CALENDAR":
            rec["occurred_at"] = rng.choice(["2031-02-27T10:00:00Z",
                                             "2031-04-02T09:30:00Z"])
        elif code == "BAD_DATE":
            rec["occurred_at"] = rng.choice(BAD_DATES)
        else:
            rec["revision_class"] = rng.choice(["FIXUP", "", "original"])

    # Rows that fail two checks at once, so the order of the validation
    # precedence decides which code each one carries.
    multi_specs = [(("MALFORMED_ROW", "BAD_TIMESTAMP"), 34),
                   (("MALFORMED_ROW", "UNKNOWN_METER"), 26),
                   (("BAD_TIMESTAMP", "UNKNOWN_SITE"), 30),
                   (("OUT_OF_CALENDAR", "BAD_QUANTITY"), 28),
                   (("BAD_QUANTITY", "UNKNOWN_SITE"), 24),
                   (("UNKNOWN_SITE", "UNKNOWN_METER"), 22),
                   (("METER_SITE_MISMATCH", "UNKNOWN_SITE"), 22),
                   (("METER_SITE_MISMATCH", "BAD_TIMESTAMP"), 20),
                   (("OUT_OF_CALENDAR", "METER_SITE_MISMATCH"), 18),
                   (("BAD_DATE", "UNKNOWN_METER"), 24),
                   (("BAD_DATE", "UNKNOWN_SITE"), 16)]
    for codes, count in multi_specs:
        for _ in range(count):
            src = dict(rng.choice(clean))
            src["_kind"] = "bad"
            src["_fam"] = rng.choices(
                ["adjustment", "desk", "import", "legacy", "partner", "relay"],
                weights=[3, 12, 9, 2, 4, 6])[0]
            src["event_key"] = "EV-%06d" % rng.randrange(700000, 999999)
            for code in codes:
                _injure(src, code)
            rows.append(src)

    rng.shuffle(rows)
    return rows


def _alt_numeral(rng, q, whole):
    """Another way of writing the same number: a leading plus sign, trailing
    zeros on the fraction, or leading zeros on a whole watt-hour count."""
    if whole:
        wh = str(int((Decimal(q) * 1000).to_integral_value(
            rounding=ROUND_HALF_EVEN)))
        if wh.startswith("-"):
            return "-0" + wh[1:]
        return rng.choice(["+" + wh, "0" + wh, "00" + wh])
    text = _qstr(q)
    if text.startswith("-"):
        return text + rng.choice(["0", "00"])
    return rng.choice(["+" + text, text + "0", "+" + text + "00"])


def _qstr(v):
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    # Exact decimal text, never through a binary float, and at least three
    # places so the delivered form matches the producing systems' habit.
    d = Decimal(v)
    if d.as_tuple().exponent > -3:
        d = d.quantize(Decimal("0.001"))
    return format(d, "f")


def _row_text(r, unit, offset=None):
    q = r["quantity"]
    if r.get("_qtext") is not None:
        qs = r["_qtext"]
    elif unit == "wh" and q is not None and not isinstance(q, str):
        qs = str(int((Decimal(q) * 1000).to_integral_value(rounding=ROUND_HALF_EVEN)))
    else:
        qs = _qstr(q)
    return {"event_key": str(r["event_key"]),
            "revision_no": str(r.get("_rtext") or r["revision_no"]),
            "revision_class": str(r["revision_class"]),
            "site_ref": str(r["site_ref"]),
            "meter_id": str(r["meter_id"]),
            "occurred_at": _as_offset(str(r["occurred_at"]), offset),
            "ingested_at": _as_offset(str(r["ingested_at"]), offset),
            "quantity": qs,
            "delta_flag": str(r["delta_flag"]),
            "supersedes_revision": str(r.get("_stext")
                                       or r["supersedes_revision"])}


def deal(st, rows):
    rng = st["rng"]
    by_fam = {}
    for n, _k in BATCHES:
        if n == REPLAY_BATCH:
            continue
        by_fam.setdefault(BATCH_FAMILY[n], []).append(n)
    out = {}
    for n, _k in BATCHES:
        out[n] = []
    for r in rows:
        fam = r.get("_fam", "desk")
        out[rng.choice(by_fam[fam])].append(r)
    for name in sorted(out):
        for r in out[name]:
            if rng.random() < 0.05:
                r["delta_flag"] = "1" if r["delta_flag"] == "0" else "0"
    return out


def write_corpus(seed, outdir, docs):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    st = build_state(seed)
    rows = build_revisions(st)
    dealt = deal(st, rows)
    rng = st["rng"]

    # The delivered history is append only. A batch redelivered under a new
    # identity repeats every row it carried before and adds the one revision
    # that had not been delivered yet, so a reader that dismisses the whole
    # redelivery loses that row and a reader that admits all of it counts the
    # repeats as fresh deliveries.
    replay = [dict(r) for r in dealt[REPLAY_SOURCE]]
    for _r in list(replay):
        if (_r["revision_class"] == "ORIGINAL"
                and isinstance(_r["quantity"], Decimal)
                and str(_r["event_key"]).startswith("EV-0")):
            _fresh = dict(_r)
            _fresh["revision_no"] = 9
            _fresh["revision_class"] = "AMENDMENT"
            _fresh["quantity"] = _r["quantity"] + Decimal("1.250")
            _fresh["supersedes_revision"] = ""
            replay.append(_fresh)
            break
    dealt[REPLAY_BATCH] = replay

    for name in sorted(dealt):
        recs = dealt[name]
        kind = BATCH_KIND[name]
        unit = "wh" if kind == "adj" else "kwh"
        offset = PARTNER_OFFSET if kind == "psv" else None
        texts = [_row_text(r, unit, offset) for r in recs]
        p = outdir / name
        if kind == "csv":
            lines = [",".join(FIELDS)]
            lines += [",".join(t[f].replace(",", ";") for f in FIELDS) for t in texts]
        elif kind == "tsv":
            lines = ["\t".join(FIELDS)]
            lines += ["\t".join(t[f].replace("\t", " ") for f in FIELDS) for t in texts]
        elif kind == "psv":
            lines = ["|".join(PSV_ORDER)]
            lines += ["|".join(t[f].replace("|", "/") for f in PSV_ORDER) for t in texts]
        elif kind == "fixed":
            lines = ["".join(t[f][:w].ljust(w) for f, w in FIXED_COLS) for t in texts]
        else:
            lines = []
            for t in texts:
                obj = dict((f, t[f]) for f in FIELDS)
                lines.append(json.dumps(obj, sort_keys=True, separators=(",", ":")))
        body = "\n".join(lines) + "\n"
        if name in CRLF_BATCHES:
            body = body.replace("\n", "\r\n")
        if name in BOM_BATCHES:
            body = "\ufeff" + body
        p.write_bytes(body.encode("utf-8"))

    ghost_rows = [_row_text(r, "kwh") for r in rows[:240]]
    (outdir / UNLISTED_BATCH).write_text(
        ",".join(FIELDS) + "\n"
        + "\n".join(",".join(t[f].replace(",", ";") for f in FIELDS)
                    for t in ghost_rows) + "\n",
        encoding="utf-8", newline="\n")

    _write_manifest(outdir, dealt, rng)
    _write_reference(outdir, st)
    for fname in sorted(docs):
        (outdir / fname).write_text(docs[fname], encoding="utf-8", newline="\n")
    return st


def _write_manifest(outdir, dealt, rng):
    lines = ["batch_id,filename,batch_seq,status,expected_rows"]
    registered = []
    for name, _k in BATCHES:
        seq = BATCH_SEQ[name]
        status = "WITHDRAWN" if name in WITHDRAWN_BATCHES else "ACTIVE"
        n = len(dealt[name])
        if status == "ACTIVE" and seq in (5, 11, 23, 31):
            n = n + rng.choice([-3, -1, 2, 5])
        registered.append((seq, name, status, n))
    # One filename withdrawn under an earlier registration and reinstated
    # under a later one, and one reinstated under an earlier registration
    # and withdrawn under a later one. Membership is decided row by row,
    # so neither retired row cancels the live one.
    registered.append((0, REINSTATED_LOW, "WITHDRAWN", 0))
    registered.sort()
    for seq, name, status, n in registered:
        lines.append("BATCH-%04d,%s,%d,%s,%d" % (seq, name, seq, status, n))
    seq = len(BATCHES) + 1
    lines.append("BATCH-%04d,%s,%d,ACTIVE,207" % (seq, GHOST_BATCH, seq))
    for i in range(seq + 1, 213):
        lines.append("BATCH-%04d,archive_%04d.csv,%d,WITHDRAWN,0" % (i, i, i))
    lines.append("BATCH-0213,%s,213,WITHDRAWN,%d"
                 % (REINSTATED_HIGH, len(dealt[REINSTATED_HIGH])))
    (outdir / "batch_manifest.csv").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _write_reference(outdir, st):
    def csv(name, keys, recs):
        lines = [",".join(keys)]
        lines += [",".join(str(r[k]) for k in keys) for r in recs]
        (outdir / name).write_text("\n".join(lines) + "\n",
                                   encoding="utf-8", newline="\n")

    csv("sites_effective.csv",
        ["site_id", "valid_from", "valid_to", "tariff_class", "zone"],
        st["sites_effective"])
    csv("site_merges.csv", ["absorbed_site", "survivor_site", "merge_instant"],
        st["merges"])
    csv("operational_state.csv", ["site_id", "valid_from", "valid_to", "state"],
        st["op_state"])
    csv("max_interval_limits.csv",
        ["site_id", "valid_from", "valid_to", "max_interval_wh"], st["limits"])

    csv("meter_registry.csv",
        ["meter_id", "site_id", "valid_from", "valid_to", "pulse_multiplier",
         "model"], st["registry"])

    tar = []
    for tc in ["TC-A", "TC-B", "TC-C", "TC-D"]:
        for i in range(55):
            tar.append({"tariff_class": tc, "band": "B%02d" % i,
                        "threshold_wh": 12000 * (i + 1),
                        "descriptor": "%s band %02d" % (tc, i)})
    csv("tariff_classes.csv",
        ["tariff_class", "band", "threshold_wh", "descriptor"], tar)

    al = ["alias_form\tsite_id"]
    al += ["  %s \t%s" % (s, s) for s in st["sites"][:210]]
    (outdir / "entity_aliases.tsv").write_text("\n".join(al) + "\n",
                                               encoding="utf-8", newline="\n")
    ap = ["legacy_ref|site_id"]
    ap += ["%s|%s" % (s.lower(), s) for s in st["sites"][:205]]
    (outdir / "entity_aliases_partner.psv").write_text("\n".join(ap) + "\n",
                                                       encoding="utf-8", newline="\n")



VALID_CLASSES = ("AMENDMENT", "CORRECTION", "ORIGINAL", "RESTATEMENT", "REVERSAL")


# --------------------------------------------------------------------------
# configuration layering
# --------------------------------------------------------------------------

def _parse_kv(text):
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";") or line.startswith("["):
            continue
        for sep in ("=", ":"):
            if sep in line:
                k, v = line.split(sep, 1)
                out.append((k.strip(), v.strip()))
                break
    return out


def resolve_config(datadir):
    """Three layers. Last wins for every key except the rounding namespace,
    which resolves to the numerically smallest value seen in any layer."""
    layers = ["settlement_defaults.ini", "network_policy.conf",
              "site_overrides.properties"]
    resolved = {}
    winner = {}
    for name in layers:
        p = os.path.join(datadir, name)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fh:
            for k, v in _parse_kv(fh.read()):
                if k.startswith("rounding."):
                    try:
                        iv = int(v)
                    except ValueError:
                        continue
                    if k not in resolved or iv < int(resolved[k]):
                        resolved[k] = str(iv)
                        winner[k] = name
                else:
                    resolved[k] = v
                    winner[k] = name
    return resolved, winner


# --------------------------------------------------------------------------
# reference tables
# --------------------------------------------------------------------------

def _read_csv(path, sep=","):
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    lines = [ln for ln in lines if ln != ""]
    if not lines:
        return []
    head = lines[0].split(sep)
    out = []
    for ln in lines[1:]:
        parts = ln.split(sep)
        if len(parts) != len(head):
            continue
        out.append(dict(zip(head, parts)))
    return out


def load_reference(datadir):
    j = lambda n: os.path.join(datadir, n)
    eff = {}
    for r in _read_csv(j("sites_effective.csv")):
        eff.setdefault(r["site_id"], []).append(
            (parse_instant(r["valid_from"]), parse_instant(r["valid_to"]),
             r["tariff_class"], r["zone"]))
    ops = {}
    for r in _read_csv(j("operational_state.csv")):
        ops.setdefault(r["site_id"], []).append(
            (parse_instant(r["valid_from"]), parse_instant(r["valid_to"]), r["state"]))
    lim = {}
    for r in _read_csv(j("max_interval_limits.csv")):
        lim.setdefault(r["site_id"], []).append(
            (parse_instant(r["valid_from"]), parse_instant(r["valid_to"]),
             int(r["max_interval_wh"])))
    bands = {}
    for r in _read_csv(j("tariff_classes.csv")):
        bands.setdefault(r["tariff_class"], []).append(
            (int(r["threshold_wh"]), r["band"]))
    for tc in bands:
        bands[tc].sort()
    merges = {}
    for r in _read_csv(j("site_merges.csv")):
        merges[r["absorbed_site"]] = (r["survivor_site"],
                                      parse_instant(r["merge_instant"]))
    meters = {}
    known_sites = set()
    bad_registrations = 0
    for r in _read_csv(j("meter_registry.csv")):
        # A row whose pulse_multiplier is not a positive decimal integer in
        # ASCII digits is not a registration at all: it covers no instant and
        # it governs nothing.
        mult = _ascii_int(r.get("pulse_multiplier", ""))
        if mult is None or mult < 1:
            bad_registrations += 1
            continue
        meters.setdefault(r["meter_id"], []).append(
            (parse_instant(r["valid_from"]), parse_instant(r["valid_to"]),
             r["site_id"], mult))
        known_sites.add(r["site_id"])
    for s in eff:
        known_sites.add(s)
    return {"eff": eff, "ops": ops, "lim": lim, "merges": merges,
            "meters": meters, "sites": known_sites, "bands": bands,
            "bad_registrations": bad_registrations}


def tariff_band(ref, tariff_class, quantity_wh):
    """The band whose threshold is the greatest threshold at or below the
    quantity. A quantity below every threshold of its class is UNBANDED."""
    rows = ref["bands"].get(tariff_class, [])
    band = "UNBANDED"
    for threshold, name in rows:
        if threshold <= quantity_wh:
            band = name
        else:
            break
    return band


def _lookup(rows, t):
    """Half-open [valid_from, valid_to) pick at instant t. Where more than one
    row covers t the latest valid_from governs, and on a shared valid_from the
    earliest valid_to does, so file order decides nothing."""
    if t is None:
        return None
    best = None
    for lo, hi, *rest in rows:
        if lo is None or hi is None or not lo <= t < hi:
            continue
        if best is None or (lo, -hi) > (best[0], -best[1]):
            best = (lo, hi, rest)
    return None if best is None else best[2]


def canonical_site(ref, site_id, t):
    """Follow the merge chain, taking each hop only when the effective instant
    is at or after that hop's merge instant."""
    cur = site_id
    seen = set()
    while cur in ref["merges"] and cur not in seen:
        seen.add(cur)
        surv, inst = ref["merges"][cur]
        if inst is None or t is None or t < inst:
            break
        cur = surv
    return cur


# --------------------------------------------------------------------------
# batch ingestion
# --------------------------------------------------------------------------

def read_manifest(datadir):
    rows = _read_csv(os.path.join(datadir, "batch_manifest.csv"))
    out = []
    for r in rows:
        try:
            seq = int(r["batch_seq"])
            exp = int(r["expected_rows"])
        except (ValueError, KeyError):
            continue
        out.append({"batch_id": r["batch_id"], "filename": r["filename"],
                    "batch_seq": seq, "status": r["status"],
                    "expected_rows": exp})
    out.sort(key=lambda r: r["batch_seq"])
    return out


def _parse_batch(path, kind):
    """Body records of one batch. A leading byte order mark belongs to no
    line, and a line ends at LF or at CR LF, so a trailing carriage return is
    never part of the last field."""
    with open(path, "rb") as fh:
        text = fh.read().decode("utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = [ln[:-1] if ln.endswith("\r") else ln for ln in text.split("\n")]
    lines = [ln for ln in lines if ln != ""]
    out = []
    if kind == "fixed":
        for ln in lines:
            rec = {}
            pos = 0
            for f, w in FIXED_COLS:
                rec[f] = ln[pos:pos + w].strip()
                pos += w
            out.append(rec)
        return out
    if kind in ("jsonl", "adj"):
        for ln in lines:
            try:
                obj = json.loads(ln)
            except ValueError:
                out.append({f: "" for f in FIELDS})
                continue
            out.append({f: str(obj.get(f, "")) for f in FIELDS})
        return out
    sep = {"csv": ",", "tsv": "\t", "psv": "|"}[kind]
    head = lines[0].split(sep)
    for ln in lines[1:]:
        parts = ln.split(sep)
        if len(parts) != len(head):
            out.append({f: "" for f in FIELDS})
            continue
        rec = dict(zip(head, parts))
        out.append({f: rec.get(f, "") for f in FIELDS})
    return out


_DIGITS = frozenset("0123456789")


def _ascii_int(text):
    """The value of a run of ASCII digits, or None for anything else. A digit
    from another script is not a decimal digit of this grammar."""
    if not isinstance(text, str) or text == "":
        return None
    for ch in text:
        if ch not in _DIGITS:
            return None
    return int(text)


def _numeral(qty_text, unit):
    """The exact decimal value of a quantity written in the documented
    grammar for its unit, or None. Kilowatt hours: an optional sign, digits,
    and optionally a point followed by digits. Watt hours: an optional sign
    and digits only."""
    if not isinstance(qty_text, str) or qty_text == "":
        return None
    body = qty_text[1:] if qty_text[0] in "+-" else qty_text
    whole, point, frac = body.partition(".")
    if _ascii_int(whole) is None:
        return None
    if point:
        if unit == "wh" or _ascii_int(frac) is None:
            return None
    return Decimal(qty_text)


def _to_wh(qty_text, unit, multiplier=1):
    """kWh decimal text or Wh integer text into integer watt-hours. The pulse
    multiplier reaches the exact decimal value before the conversion, and the
    product is quantized once, ROUND_HALF_EVEN, at this stage and nowhere
    else."""
    d = _numeral(qty_text, unit)
    if d is None:
        return None
    scaled = d * multiplier * (1 if unit == "wh" else 1000)
    return int(scaled.to_integral_value(rounding=ROUND_HALF_EVEN))


def classify_row(rec, ref, unit):
    """Return (reason_code or None). Precedence is fixed and documented."""
    cls = rec.get("revision_class", "")
    if cls not in VALID_CLASSES:
        return "MALFORMED_ROW"
    rno = _ascii_int(rec.get("revision_no", ""))
    if rno is None or rno < 1:
        return "MALFORMED_ROW"
    occ = rec.get("occurred_at", "")
    if parse_instant(occ) is None:
        return "BAD_TIMESTAMP"
    if settlement_day(occ) is None:
        return "OUT_OF_CALENDAR"
    q = rec.get("quantity", "")
    if q != "" and _to_wh(q, unit) is None:
        return "BAD_QUANTITY"
    site = normalize_ref(rec.get("site_ref", ""))
    if site not in ref["sites"]:
        return "UNKNOWN_SITE"
    mtr = rec.get("meter_id", "").strip()
    windows = ref["meters"].get(mtr)
    cover = None if windows is None else _lookup(windows,
                                                 parse_instant(occ))
    if cover is None:
        return "UNKNOWN_METER"
    if cover[0] != site:
        return "METER_SITE_MISMATCH"
    return None


def row_multiplier(rec, ref):
    """The pulse multiplier of the registration covering this row's own
    occurred_at. Every admitted row has exactly one, because check 7 demands a
    covering registration and the overlap rule picks one of them."""
    windows = ref["meters"].get(rec.get("meter_id", "").strip())
    cover = None if windows is None else _lookup(
        windows, parse_instant(rec.get("occurred_at", "")))
    return 1 if cover is None else cover[1]


def ingest(datadir, ref):
    """Walk every ACTIVE manifest batch in batch_seq order and dispose of every
    row exactly once. Returns admitted revisions plus the disposition records."""
    manifest = read_manifest(datadir)
    admitted = []
    rejects = []
    duplicates = []
    conflicts = []
    missing_batches = []
    row_exceptions = []
    seen = {}
    seen_text = {}
    reformatted = []
    total_rows = 0

    for m in manifest:
        if m["status"] != "ACTIVE":
            continue
        path = os.path.join(datadir, m["filename"])
        if not os.path.exists(path):
            missing_batches.append(m)
            continue
        kind = BATCH_KIND.get(m["filename"])
        if kind is None:
            continue
        unit = "wh" if kind == "adj" else "kwh"
        recs = _parse_batch(path, kind)
        if len(recs) != m["expected_rows"]:
            row_exceptions.append({"batch_id": m["batch_id"],
                                   "filename": m["filename"],
                                   "declared_rows": m["expected_rows"],
                                   "observed_rows": len(recs)})
        for line_no, rec in enumerate(recs, 1):
            total_rows += 1
            code = classify_row(rec, ref, unit)
            base = {"batch_id": m["batch_id"], "batch_seq": m["batch_seq"],
                    "filename": m["filename"], "line_no": line_no}
            if code is not None:
                r = dict(base)
                r["event_key"] = rec.get("event_key", "")
                r["reason_code"] = code
                rejects.append(r)
                continue
            fam = BATCH_FAMILY[m["filename"]]
            key = (rec["event_key"], _ascii_int(rec["revision_no"]),
                   rec["revision_class"], fam)
            sup_text = rec["supersedes_revision"].strip()
            sup_no = _ascii_int(sup_text)
            sup_norm = sup_text if sup_no is None else str(sup_no)
            # The payload is compared by value: the instant it names in UTC,
            # the exact decimal value of the quantity in the batch's unit, and
            # the revision number supersedes_revision names.
            payload = (normalize_ref(rec["site_ref"]), rec["meter_id"].strip(),
                       parse_instant(rec["occurred_at"]),
                       _numeral(rec["quantity"], unit), sup_norm)
            if key in seen:
                r = dict(base)
                r["event_key"] = key[0]
                r["revision_no"] = key[1]
                r["revision_class"] = key[2]
                r["family"] = key[3]
                if seen[key] == payload:
                    duplicates.append(r)
                    if seen_text[key] != (rec["quantity"], rec["revision_no"]):
                        reformatted.append(r)
                else:
                    conflicts.append(r)
                continue
            seen[key] = payload
            seen_text[key] = (rec["quantity"], rec["revision_no"])
            wh = None
            if rec["quantity"] != "":
                wh = _to_wh(rec["quantity"], unit, row_multiplier(rec, ref))
            admitted.append({
                "event_key": key[0], "revision_no": key[1],
                "revision_class": key[2],
                "family": fam,
                "site_id": normalize_ref(rec["site_ref"]),
                "meter_id": rec["meter_id"].strip(),
                "occurred_at": rec["occurred_at"],
                "ingested_at": rec["ingested_at"],
                "quantity_wh": wh,
                "supersedes_revision": sup_norm,
                "quantity_text": rec["quantity"],
                "batch_seq": m["batch_seq"], "line_no": line_no,
                "batch_id": m["batch_id"]})

    return {"manifest": manifest, "admitted": admitted, "rejects": rejects,
            "duplicates": duplicates, "conflicts": conflicts,
            "missing_batches": missing_batches,
            "row_exceptions": row_exceptions, "total_rows": total_rows,
            "reformatted": reformatted}


# --------------------------------------------------------------------------
# canonical state
# --------------------------------------------------------------------------

def _pick(revs):
    """Highest class rank, then highest revision_no, then lowest batch_seq."""
    return min(revs, key=lambda r: (-CLASS_RANK[r["revision_class"]],
                                    -r["revision_no"], r["batch_seq"]))


def materialize(datadir):
    ref = load_reference(datadir)
    cfg, winner = resolve_config(datadir)
    ing = ingest(datadir, ref)

    by_event = {}
    for r in ing["admitted"]:
        by_event.setdefault(r["event_key"], []).append(r)

    q_dp = int(cfg.get("rounding.quantity_dp", "3"))
    t_dp = int(cfg.get("rounding.total_dp", "2"))
    include_excluded = cfg.get("settlement.exclusion_policy", "omit") == "include"

    ledger = []
    deferred = []
    unresolvable = []
    demoted = 0
    premerge_kept = 0
    clamp_on_stack_only = 0
    norm_changed = 0
    tie_broken_by_seq = 0
    boundary_shifted = 0
    displaced_revisions = 0

    for key in sorted(by_event):
        revs = by_event[key]
        canon = _pick(revs)
        t = parse_instant(canon["occurred_at"])
        day = settlement_day(canon["occurred_at"])

        top_rno = max(r["revision_no"] for r in revs)
        if canon["revision_no"] < top_rno:
            demoted += 1
        peers = [r for r in revs
                 if r["revision_class"] == canon["revision_class"]
                 and r["revision_no"] == canon["revision_no"]]
        if len(peers) > 1:
            tie_broken_by_seq += 1
        if canon["occurred_at"][:10].replace("-", "") != day:
            boundary_shifted += 1

        raw_site = canon["site_id"]
        csite = canonical_site(ref, raw_site, t)
        if raw_site in ref["merges"] and csite == raw_site:
            premerge_kept += 1

        effrow = _lookup(ref["eff"].get(csite, []), t)
        zone = effrow[1] if effrow else ""
        tariff = effrow[0] if effrow else ""
        oprow = _lookup(ref["ops"].get(csite, []), t)
        state = oprow[0] if oprow else "ACTIVE"
        limrow = _lookup(ref["lim"].get(csite, []), t)
        # No covering row is no ceiling at all, and never a ceiling of zero.
        cap = limrow[0] if limrow else None

        rnos = set(r["revision_no"] for r in revs)
        outcome = None
        reason = ""
        base_revs = [r for r in revs if r["revision_class"] != "RESTATEMENT"]
        full_stack = sorted(
            (r for r in revs if r["revision_class"] == "RESTATEMENT"),
            key=lambda r: (r["revision_no"], r["batch_seq"]))
        stack_nos = set(r["revision_no"] for r in full_stack)
        displaced = set()
        for _r in full_stack:
            _s = _ascii_int(_r["supersedes_revision"])
            if _s is not None and _s in stack_nos:
                displaced.add(_s)
        displaced_revisions += sum(
            1 for r in full_stack if r["revision_no"] in displaced)

        if canon["revision_class"] in ("CORRECTION", "RESTATEMENT"):
            sup = canon["supersedes_revision"]
            if _ascii_int(sup) is None or _ascii_int(sup) not in rnos:
                outcome, reason = "UNRESOLVABLE", "ORPHAN_SUPERSEDE"
        if outcome is None and not base_revs:
            outcome, reason = "UNRESOLVABLE", "MISSING_BASE"
        if outcome is None and cap is None:
            outcome, reason = "UNRESOLVABLE", "MISSING_CEILING"

        qty = 0
        clamp_rec = None
        base_ident = None
        if base_revs:
            _b = _pick(base_revs)
            base_ident = (_b["revision_no"], _b["revision_class"], _b["family"])
        if outcome is None:
            base = _pick(base_revs)
            if base["quantity_wh"] is None:
                outcome = "DEFERRED"
            else:
                base_clamped = max(0, min(cap, base["quantity_wh"]))
                stack = [r for r in full_stack
                         if r["revision_no"] not in displaced]
                total = base_clamped
                for s in stack:
                    if s["quantity_wh"] is not None:
                        total += s["quantity_wh"]
                final = max(0, min(cap, total))
                if final != total and base_clamped == base["quantity_wh"]:
                    clamp_on_stack_only += 1
                stage = ""
                if base_clamped != base["quantity_wh"] and final != total:
                    stage = "BOTH"
                elif base_clamped != base["quantity_wh"]:
                    stage = "BASE"
                elif final != total:
                    stage = "SUM"
                if stage:
                    clamp_rec = {"event_key": key, "canonical_site": csite,
                                 "base_wh": base["quantity_wh"],
                                 "base_clamped_wh": base_clamped,
                                 "stack_delta_wh": total - base_clamped,
                                 "final_wh": final, "clamp_stage": stage,
                                 "max_interval_wh": cap}
                qty = final
                reversals = sum(1 for r in revs
                                if r["revision_class"] == "REVERSAL")
                if (canon["revision_class"] == "REVERSAL"
                        and reversals % 2 == 1):
                    outcome, qty = "VOIDED", 0
                elif state == "SUSPENDED":
                    outcome = "EXCLUDED"
                else:
                    outcome = "SETTLED"

        band = tariff_band(ref, tariff, qty)
        row = {"settlement_day": day, "canonical_site": csite,
               "tariff_band": band,
               "canonical_family": canon["family"],
               "base_identity": base_ident,
               "event_key": key, "outcome": outcome,
               "quantity_wh": qty, "zone": zone, "tariff_class": tariff,
               "source_site": raw_site,
               "revision_no": canon["revision_no"],
               "revision_class": canon["revision_class"],
               "reason_code": reason, "clamp": clamp_rec,
               "stack": full_stack, "displaced": displaced}
        ledger.append(row)
        if outcome == "DEFERRED":
            deferred.append({"event_key": key, "settlement_day": day,
                             "canonical_site": csite,
                             "revision_no": canon["revision_no"]})
        if outcome == "UNRESOLVABLE":
            unresolvable.append({"event_key": key, "reason_code": reason,
                                 "settlement_day": day,
                                 "canonical_site": csite})

    ledger.sort(key=lambda r: (r["settlement_day"], r["canonical_site"], r["event_key"]))

    parts = {}
    for d in DAYS:
        parts[d] = []
    for r in ledger:
        if r["outcome"] == "EXCLUDED" and not include_excluded:
            continue
        parts[r["settlement_day"]].append(r)

    cells = {}
    for r in ledger:
        if r["outcome"] != "SETTLED":
            continue
        ck = (r["settlement_day"], r["zone"])
        c = cells.setdefault(ck, {"settled_wh": 0, "event_count": 0})
        c["settled_wh"] += r["quantity_wh"]
        c["event_count"] += 1

    return {"ref": ref, "cfg": cfg, "winner": winner, "ing": ing,
            "ledger": ledger, "parts": parts, "cells": cells,
            "deferred": deferred, "unresolvable": unresolvable,
            "q_dp": q_dp, "t_dp": t_dp, "include_excluded": include_excluded,
            "counters": {"demoted": demoted, "premerge_kept": premerge_kept,
                         "clamp_on_stack_only": clamp_on_stack_only,
                         "tie_broken_by_seq": tie_broken_by_seq,
                         "boundary_shifted": boundary_shifted,
                         "displaced_revisions": displaced_revisions}}


def kwh_text(wh, dp):
    d = (Decimal(wh) / Decimal(1000)).quantize(Decimal(1).scaleb(-dp),
                                               rounding=ROUND_HALF_EVEN)
    return str(d)



NL = chr(10)

ARTIFACTS = (
    ["/app/out/materialize.py", "/app/out/canonical_ledger.jsonl",
     "/app/out/revision_index.jsonl"]
    + ["/app/out/partition_%s.csv" % d for d in DAYS]
    + ["/app/out/partition_manifest.json", "/app/out/rejects.csv",
       "/app/out/quarantine.jsonl", "/app/out/deferred.jsonl",
       "/app/out/unresolvable.json", "/app/out/dedup_ledger.csv",
       "/app/out/entity_resolution.json", "/app/out/clamp_register.csv",
       "/app/out/stack_register.csv",
       "/app/out/restatement_adjustments.csv", "/app/out/reconciliation.json",
       "/app/out/validation_report.txt", "/app/out/run_manifest.json"]
)


def _wj(path, obj):
    with open(path, "w", encoding="utf-8", newline=NL) as fh:
        fh.write(json.dumps(obj, sort_keys=True, indent=2) + NL)


def make_baseline(datadir, seed):
    """First pass, then publish a prior that differs on all but a couple of
    cells. Written into the corpus directory as published_baseline.json."""
    st = materialize(datadir)
    rng = random.Random(seed ^ 0x5EED)
    cells = []
    for d in DAYS:
        for z in ZONES:
            c = st["cells"].get((d, z), {"settled_wh": 0, "event_count": 0})
            wh, n = c["settled_wh"], c["event_count"]
            if rng.random() < 0.86:
                wh = wh + rng.choice([-1, 1]) * rng.randrange(1200, 900000)
                if wh < 0:
                    wh = abs(wh)
                n = max(0, n + rng.choice([-3, -2, -1, 1, 2, 4]))
            cells.append({"settlement_day": d, "zone": z,
                          "settled_wh": wh, "event_count": n})
    # The publication also states a zone the network has retired since, so
    # this materialization computes nothing for those cells and has to restate
    # each of them to zero rather than leave it out of the adjustment set.
    for d in DAYS[:5]:
        cells.append({"settlement_day": d, "zone": RETIRED_ZONE,
                      "settled_wh": rng.randrange(40000, 2600000),
                      "event_count": rng.randrange(3, 40)})
    _wj(os.path.join(datadir, "published_baseline.json"),
        {"publication_id": "PUB-2031-03-16", "cells": cells})


def read_baseline(datadir):
    p = os.path.join(datadir, "published_baseline.json")
    with open(p, encoding="utf-8") as fh:
        obj = json.load(fh)
    out = {}
    for c in obj.get("cells", []):
        out[(c["settlement_day"], c["zone"])] = (int(c["settled_wh"]),
                                                 int(c["event_count"]))
    return out


def expected_artifacts(datadir):
    """Every deliverable, as the exact bytes a correct run writes."""
    st = materialize(datadir)
    base = read_baseline(datadir)
    ledger = st["ledger"]
    q_dp, t_dp = st["q_dp"], st["t_dp"]
    ing = st["ing"]
    out = {}

    out["canonical_ledger.jsonl"] = "".join(
        json.dumps({"canonical_site": r["canonical_site"],
                    "event_key": r["event_key"], "outcome": r["outcome"],
                    "quantity_kwh": kwh_text(r["quantity_wh"], q_dp),
                    "quantity_wh": r["quantity_wh"],
                    "revision_class": r["revision_class"],
                    "revision_no": r["revision_no"],
                    "settlement_day": r["settlement_day"],
                    "source_site": r["source_site"],
                    "tariff_band": r["tariff_band"],
                    "tariff_class": r["tariff_class"],
                    "zone": r["zone"]},
                   sort_keys=True, separators=(",", ":")) + NL
        for r in ledger)

    canon_of = {}
    base_of = {}
    disp_of = {}
    for r in ledger:
        disp_of[r["event_key"]] = r["displaced"]
        canon_of[r["event_key"]] = (r["revision_no"], r["revision_class"],
                                    r["canonical_family"])
        base_of[r["event_key"]] = r["base_identity"]
    by_event = {}
    for a in ing["admitted"]:
        by_event.setdefault(a["event_key"], []).append(a)
    idx = []
    for k in sorted(by_event):
        for a in sorted(by_event[k], key=lambda x: (x["revision_no"],
                                                    x["revision_class"],
                                                    x["family"])):
            ident = (a["revision_no"], a["revision_class"], a["family"])
            is_c = canon_of.get(k) == ident
            if is_c:
                role = "CANONICAL"
            elif base_of.get(k) == ident:
                role = "BASE"
            elif a["revision_class"] == "RESTATEMENT":
                if a["revision_no"] in disp_of.get(k, ()):
                    role = "DISPLACED"
                else:
                    role = "RESTATEMENT_STACK"
            else:
                role = "SUPERSEDED"
            idx.append({"batch_id": a["batch_id"], "event_key": k,
                        "family": a["family"], "is_canonical": is_c,
                        "quantity_wh": a["quantity_wh"],
                        "revision_class": a["revision_class"],
                        "revision_no": a["revision_no"], "role": role})
    out["revision_index.jsonl"] = "".join(
        json.dumps(o, sort_keys=True, separators=(",", ":")) + NL for o in idx)

    hdr = ["sequence_no", "event_key", "canonical_site", "zone",
           "tariff_band", "outcome", "quantity_wh"]
    pm = []
    for d in DAYS:
        rows = st["parts"][d]
        body = ",".join(hdr) + NL
        for n, r in enumerate(rows, 1):
            body += "%d,%s,%s,%s,%s,%s,%d%s" % (
                n, r["event_key"], r["canonical_site"], r["zone"],
                r["tariff_band"], r["outcome"], r["quantity_wh"], NL)
        out["partition_%s.csv" % d] = body
        s_wh = sum(r["quantity_wh"] for r in rows if r["outcome"] == "SETTLED")
        s_n = sum(1 for r in rows if r["outcome"] == "SETTLED")
        pm.append({"settlement_day": d, "row_count": len(rows),
                   "settled_event_count": s_n, "settled_wh": s_wh,
                   "settled_kwh": kwh_text(s_wh, t_dp)})
    out["partition_manifest.json"] = json.dumps({"partitions": pm},
                                                sort_keys=True, indent=2) + NL

    rej = sorted(ing["rejects"], key=lambda r: (r["batch_id"], r["line_no"]))
    out["rejects.csv"] = ("batch_id,filename,line_no,event_key,reason_code" + NL
                          + "".join("%s,%s,%d,%s,%s%s"
                                    % (r["batch_id"], r["filename"],
                                       r["line_no"], r["event_key"],
                                       r["reason_code"], NL) for r in rej))

    con = sorted(ing["conflicts"], key=lambda r: (r["batch_id"], r["line_no"]))
    out["quarantine.jsonl"] = "".join(
        json.dumps({"batch_id": r["batch_id"], "event_key": r["event_key"],
                    "line_no": r["line_no"],
                    "revision_class": r["revision_class"],
                    "revision_no": r["revision_no"]},
                   sort_keys=True, separators=(",", ":")) + NL for r in con)

    dup = sorted(ing["duplicates"], key=lambda r: (r["batch_id"], r["line_no"]))
    out["dedup_ledger.csv"] = (
        "batch_id,line_no,event_key,revision_no,revision_class" + NL
        + "".join("%s,%d,%s,%d,%s%s" % (r["batch_id"], r["line_no"],
                                        r["event_key"], r["revision_no"],
                                        r["revision_class"], NL) for r in dup))

    out["deferred.jsonl"] = "".join(
        json.dumps(o, sort_keys=True, separators=(",", ":")) + NL
        for o in sorted(st["deferred"], key=lambda x: x["event_key"]))

    mb = sorted(ing["missing_batches"], key=lambda m: m["batch_id"])
    out["unresolvable.json"] = json.dumps({
        "events": sorted(st["unresolvable"], key=lambda x: x["event_key"]),
        "missing_batches": [{"batch_id": m["batch_id"],
                             "filename": m["filename"],
                             "reason_code": "MISSING_BATCH"} for m in mb],
    }, sort_keys=True, indent=2) + NL

    res = []
    for r in ledger:
        if r["source_site"] in st["ref"]["merges"]:
            res.append({"canonical_site": r["canonical_site"],
                        "event_key": r["event_key"],
                        "merge_applied": r["canonical_site"] != r["source_site"],
                        "source_site": r["source_site"]})
    out["entity_resolution.json"] = json.dumps(
        {"resolutions": sorted(res, key=lambda x: x["event_key"])},
        sort_keys=True, indent=2) + NL

    ch = ["event_key", "canonical_site", "max_interval_wh", "base_wh",
          "base_clamped_wh", "stack_delta_wh", "final_wh", "clamp_stage"]
    crows = [r["clamp"] for r in ledger if r.get("clamp")]
    crows.sort(key=lambda c: c["event_key"])
    out["clamp_register.csv"] = ",".join(ch) + NL + "".join(
        ",".join(str(c[k]) for k in ch) + NL for c in crows)

    sh = ["event_key", "revision_no", "family", "delta_wh", "stack_state"]
    srows = []
    for r in ledger:
        held = r["outcome"] in ("DEFERRED", "UNRESOLVABLE")
        for a in r["stack"]:
            if a["revision_no"] in r["displaced"]:
                state = "DISPLACED"
            elif held:
                state = "WITHHELD"
            elif a["quantity_wh"] is None:
                state = "ABSENT"
            else:
                state = "APPLIED"
            srows.append(
                {"event_key": r["event_key"],
                 "revision_no": a["revision_no"],
                 "family": a["family"],
                 "delta_wh": (0 if a["quantity_wh"] is None
                              else a["quantity_wh"]),
                 "stack_state": state})
    srows.sort(key=lambda s: (s["event_key"], s["revision_no"],
                              s["family"]))
    out["stack_register.csv"] = ",".join(sh) + NL + "".join(
        ",".join(str(s[k]) for k in sh) + NL for s in srows)

    adj_rows = []
    tot_base = 0
    tot_delta = 0
    # The cells weighed are the cells the publication states together with the
    # cells this run computes, so a zone the network has retired since the
    # publication is restated to zero rather than left out.
    for cell in sorted(set(base) | set(st["cells"])):
        b_wh, b_n = base.get(cell, (0, 0))
        c = st["cells"].get(cell, {"settled_wh": 0, "event_count": 0})
        dw = c["settled_wh"] - b_wh
        dn = c["event_count"] - b_n
        tot_base += b_wh
        tot_delta += dw
        if dw != 0 or dn != 0:
            kind = ("INCREASE" if dw > 0 else
                    "DECREASE" if dw < 0 else "COUNT_ONLY")
            adj_rows.append({"settlement_day": cell[0], "zone": cell[1],
                             "adjustment_kind": kind,
                             "baseline_settled_wh": b_wh,
                             "restated_settled_wh": c["settled_wh"],
                             "delta_wh": dw,
                             "baseline_event_count": b_n,
                             "restated_event_count": c["event_count"],
                             "delta_events": dn})
    ah = ["settlement_day", "zone", "adjustment_kind", "baseline_settled_wh",
          "restated_settled_wh", "delta_wh", "baseline_event_count",
          "restated_event_count", "delta_events"]
    out["restatement_adjustments.csv"] = ",".join(ah) + NL + "".join(
        ",".join(str(r[h]) for h in ah) + NL for r in adj_rows)

    led_wh = sum(r["quantity_wh"] for r in ledger if r["outcome"] == "SETTLED")
    par_wh = sum(p["settled_wh"] for p in pm)
    n_adm = len(ing["admitted"])
    n_dup = len(ing["duplicates"])
    n_con = len(ing["conflicts"])
    n_rej = len(ing["rejects"])
    recon = {
        "identity_class_partition": {
            "admitted": n_adm, "conflict": n_con, "duplicate": n_dup,
            "rejected": n_rej,
            "residual": n_adm + n_dup + n_con + n_rej - ing["total_rows"],
            "total_rows": ing["total_rows"]},
        "identity_partition_rollup": {
            "ledger_settled_wh": led_wh, "partition_settled_wh": par_wh,
            "residual": par_wh - led_wh},
        "identity_restatement": {
            "adjustment_delta_wh": tot_delta,
            "baseline_settled_wh": tot_base,
            "residual": tot_base + tot_delta - led_wh,
            "restated_settled_wh": led_wh},
    }
    out["reconciliation.json"] = json.dumps(recon, sort_keys=True, indent=2) + NL

    out["validation_report.txt"] = (
        "CLASS_PARTITION residual=%d" + NL
        + "PARTITION_ROLLUP residual=%d" + NL
        + "RESTATEMENT residual=%d" + NL
        + "ROUNDING quantity_dp=%d total_dp=%d" + NL
        + "EXCLUSION policy=%s" + NL
        + "CLAMPED events=%d" + NL
        + "UNRESOLVED events=%d" + NL
        + "DISPLACED revisions=%d" + NL
    ) % (recon["identity_class_partition"]["residual"],
         recon["identity_partition_rollup"]["residual"],
         recon["identity_restatement"]["residual"],
         q_dp, t_dp,
         "include" if st["include_excluded"] else "omit",
         len(crows), len(st["unresolvable"]),
         sum(1 for s in srows if s["stack_state"] == "DISPLACED"))

    ingested = sorted(m["batch_id"] for m in ing["manifest"]
                      if m["status"] == "ACTIVE"
                      and os.path.exists(os.path.join(datadir, m["filename"])))
    withdrawn = sorted(m["batch_id"] for m in ing["manifest"]
                       if m["status"] != "ACTIVE")
    out["run_manifest.json"] = json.dumps({
        "batches_ingested": ingested,
        "batches_withdrawn": withdrawn,
        "config_resolved": st["cfg"],
        "config_winner": st["winner"],
        "row_exceptions": sorted(ing["row_exceptions"],
                                 key=lambda r: r["batch_id"]),
    }, sort_keys=True, indent=2) + NL

    return out, st


def write_artifacts(datadir, outdir):
    os.makedirs(outdir, exist_ok=True)
    files, st = expected_artifacts(datadir)
    for name in sorted(files):
        with open(os.path.join(outdir, name), "w", encoding="utf-8",
                  newline=NL) as fh:
            fh.write(files[name])
    return st


PROTOCOL = """# Marrowgate settlement protocol

This document governs the materialization of the interval ledger for the
Marrowgate district energy network. It is the authority on membership,
disposition, canonical selection, quantity arithmetic and outcome. Where any
other document in this directory appears to say something different about these
subjects, this document governs.

## 1. Batch membership

`batch_manifest.csv` decides which batches belong to a materialization. A batch
is in scope when its manifest row carries `status` exactly `ACTIVE`. A batch
whose row carries any other status is out of scope and none of its rows are read,
whatever the file contains and whether or not the file is present.

A file present in this directory that has no manifest row at all is not part of
the network's registered history. It is not read and it is not an exception.

Membership is decided row by row and never file by file. A batch that was
withdrawn and later reinstated carries more than one manifest row for the one
`filename`, and each row is weighed on its own `status`. A withdrawn row
neither cancels nor confirms an `ACTIVE` row for the same `filename`, whether
the withdrawn row is registered at a lower `batch_seq` or at a higher one, and
a `filename` that carries an `ACTIVE` row is therefore read exactly once
however many withdrawn rows accompany it. Each manifest row is reported under
its own `batch_id`, so one such `filename` is named by an ingested `batch_id`
and by a withdrawn `batch_id` at the same time.

A manifest row that is `ACTIVE` and whose `filename` is absent from this
directory is an unresolvable condition. It is reported under the code
`MISSING_BATCH` and it contributes no rows.

Rows are read in ascending `batch_seq`, and within a batch in file order. The
first line of every delimited batch is a header and is not a row. The
fixed-width batches carry no header and every line is a row.

`expected_rows` states the row count the producing system believed it had
written. A batch whose observed row count differs from `expected_rows` is still
ingested in full, and the disagreement is recorded as a row exception.

## 2. Disposition of a delivered row

Every row read from an in-scope batch receives exactly one disposition:
`ADMITTED`, `DUPLICATE`, `CONFLICT` or `REJECTED`. No row receives two and no
row receives none.

A row is `REJECTED` when it fails validation. Validation applies the following
checks in this order and stops at the first failure, so a row that fails two
checks carries the code of the earlier one:

```
1  revision_class is one of the five defined classes      -> MALFORMED_ROW
2  revision_no is a positive decimal integer              -> MALFORMED_ROW
   written in ASCII digits
3  occurred_at parses as an instant in one of the two      -> BAD_TIMESTAMP
   written forms section 8 defines
4  occurred_at falls inside the settlement calendar       -> OUT_OF_CALENDAR
5  quantity, when present, is a numeral of the grammar   -> BAD_QUANTITY
   record-layouts.md gives for the batch's unit
6  the normalized site reference is a registered site     -> UNKNOWN_SITE
7  meter_id holds a registration covering that instant  -> UNKNOWN_METER
8  that registration names the site the normalized
   reference denotes                           -> METER_SITE_MISMATCH
```

An absent quantity is not a validation failure. Check 5 applies only to a
quantity that is present and non-empty.

Check 2 admits only the ten ASCII digits `0` to `9`. A digit from any other
script is not a decimal digit here, even where a programming language would
read it as one, and a sign, a point or a value of zero fails the check.
Leading zeros are permitted and carry no meaning, so `03` and `3` are the same
revision number wherever a revision number is compared, named or written.

Check 8 compares the `site_id` of the covering meter registration with the
registered site the normalized reference denotes, which is the site the
reference names before any merge is applied. A row whose meter belongs to a
site that merges into the site the row names still fails check 8, because a
row is validated as delivered and the merge chain is walked only once an event
has a canonical revision and therefore an effective instant. A row whose
meter carries no registration covering the instant fails check 7 and never
reaches check 8.

The delivery identity of a row is `event_key`, `revision_no`,
`revision_class` and the batch family the row arrived in, all four together.
Its payload is the normalized site reference, the meter id, `occurred_at`, the
quantity field and `supersedes_revision`, and the payload is compared by value
rather than by characters: `occurred_at` by the UTC instant it names, the
quantity by the exact decimal value its numeral denotes in the batch's unit,
taken before any pulse multiplier is applied, and
`supersedes_revision` by the revision number it names. Two quantities written
differently that denote the same number are the same value. Two quantities
that denote different numbers are different values even where both carry to
the same whole watt-hour. Among rows sharing one
delivery identity, the first one read is `ADMITTED`. A later row with the same
delivery identity is `DUPLICATE` when its payload equals the admitted payload
and `CONFLICT` when it does not. A `CONFLICT` row is quarantined and never
changes the admitted row.

Two rows that share an `event_key` and differ in `revision_no` do not share a
delivery identity. They are the ordinary revision history of one event.

A producing system that loses track of what it has already sent redelivers a
batch under a fresh `batch_id` and a fresh `filename`. The history is append
only, so such a redelivery is in scope on its `status` like any other batch and
every line of it is read. Its repeated rows meet the delivery identities their
originals already hold and fall out as duplicates, and any row in it carrying a
delivery identity no earlier batch held is admitted and settles like any other
revision.

Two rows that agree on `event_key`, `revision_no` and `revision_class` and
arrive in different batch families do not share a delivery identity either.
Both are admitted, and one event therefore carries two admitted revisions of the
same class and number. Section 3 decides which of them governs.

## 3. The canonical revision

The class rank is `ORIGINAL` 0, `AMENDMENT` 1, `CORRECTION` 2, `REVERSAL` 3,
`RESTATEMENT` 4.

Among the admitted revisions of one event the canonical revision is the one with
the highest class rank. Among those, the one with the highest `revision_no`.
Among those, the one whose batch carries the lowest `batch_seq`. Class rank
governs before `revision_no`, so a revision of a higher ranked class is
canonical even when another admitted revision carries a larger `revision_no`,
and the lowest `batch_seq` governs the pair a cross family redelivery creates,
so the earlier registered batch supplies the reading and the later one does
not.

The effective instant of an event is the `occurred_at` of its canonical
revision. Every effective dated lookup in this directory is made at the
effective instant and never at `ingested_at`.

The base revision of an event is the highest ranked admitted revision whose
class is not `RESTATEMENT`, resolved by the same three keys.

## 4. Quantity

All quantity arithmetic is carried in whole watt-hours as integers.

The `quantity` field of a batch is read in that batch's unit, which
`record-layouts.md` states for each family. A quantity expressed in kilowatt
hours is converted to watt-hours by multiplying the decimal value by one
thousand and quantizing the product once to an integer under round half to even.
No later stage re-quantizes a value.

A delivered count is not a reading on its own. The registration that covers a
row's own `occurred_at` for that row's `meter_id` carries a
`pulse_multiplier`, and the quantity the row delivers is the value of its
numeral multiplied by that multiplier. The product is carried to watt-hours by
the single quantization above, so the multiplier is applied to the exact
decimal value before that quantization and never to the integer the
quantization produced: a reading whose watt-hour value lands on a half is
multiplied first and quantized once. Every row that reaches this stage has
cleared check 7 and therefore has exactly one covering registration, by the
rule `entity-model.md` gives for rows that cover one instant together.

`delta_flag` is written by the producing system as a hint. It is advisory and it
is not authoritative. The revision class decides whether a quantity is an
absolute reading or a signed delta.

The quantity of a revision whose class is `RESTATEMENT` is a signed delta in
that batch's unit. The quantity of a revision of any other class is an absolute
reading.

`max_interval_limits.csv` gives the ceiling for a site at an instant. A
canonical site that carries no row covering the effective instant has no
ceiling at all: a ceiling is never assumed, a missing row is never read as a
ceiling of zero, and the event is the unresolvable condition section 5 decides.

Where a ceiling exists, the quantity of the base revision is clamped into the
closed range from zero to that ceiling. The signed deltas of every admitted
`RESTATEMENT` revision of the event are then added to the clamped base, in
ascending `revision_no` and, on a tie, ascending `batch_seq`. The sum is
clamped into the same range a second time. Clamping is applied to a single
event and never to a total.

A `RESTATEMENT` revision whose `supersedes_revision` names the `revision_no`
of an admitted `RESTATEMENT` revision of the same event displaces it. Every
admitted `RESTATEMENT` revision carrying a displaced `revision_no` is withheld
from the stack and its delta is never added to the clamped base. Because the
delivery identity carries the batch family, one `revision_no` can be held by
two admitted `RESTATEMENT` revisions of one event, and naming that number
displaces both of them.

The displacing revision applies its own delta in the ordinary way, and it
applies that delta even when a third revision has displaced it in turn. The
relation is read once over the admitted stack as delivered and is never
followed to a fixed point.

A displaced revision remains an admitted revision. It keeps its place in the
revision index, it counts as a delivered row, and it displaces whatever its
own `supersedes_revision` names. A `RESTATEMENT` naming a `revision_no` that
only a revision of another class carries displaces nothing, and a
`RESTATEMENT` naming a `revision_no` no admitted revision of the event carries
is the orphan condition section 5 decides.

## 4a. Tariff band

`tariff_classes.csv` carries the bands of each tariff class with the watt-hour
threshold at which each band opens. The band of an event is the band of its
tariff class whose threshold is the greatest threshold at or below the event's
final quantity. An event whose final quantity falls below every threshold of its
class carries the literal `UNBANDED`, and so does every event whose final
quantity is zero.

The tariff class is the one the effective dated row selects for the canonical
site at the effective instant, so the band is a consequence of the canonical
revision, the merge chain, the effective dated join, the unit conversion and
both clamps together.

## 5. Outcome

Every event receives exactly one outcome. The following tests are applied in
order and the first one that holds decides:

```
1  the canonical class is CORRECTION or RESTATEMENT and its
   supersedes_revision names a revision_no that no admitted
   revision of the event carries              -> UNRESOLVABLE ORPHAN_SUPERSEDE
2  the event has no admitted non RESTATEMENT
   revision                                   -> UNRESOLVABLE MISSING_BASE
3  no row of max_interval_limits.csv covers the canonical
   site at the effective instant              -> UNRESOLVABLE MISSING_CEILING
4  the base revision carries no quantity      -> DEFERRED
5  the canonical class is REVERSAL and the event
   carries an odd number of admitted REVERSAL
   revisions                                  -> VOIDED
6  the canonical site is SUSPENDED at the
   effective instant                           -> EXCLUDED
7  otherwise                                   -> SETTLED
```

Test 3 is weighed before test 4, so an event whose canonical site has no
ceiling at its effective instant is unresolvable whether or not its base
revision carries a reading, and an event that would otherwise be voided or
excluded is unresolvable for the same reason.

A `VOIDED` event carries a quantity of zero and keeps its place in the ledger
and in every count. An `EXCLUDED` event carries its computed quantity and
keeps its place in the ledger and in every count, and it contributes nothing
to any settled total. A `DEFERRED` or `UNRESOLVABLE` event carries a quantity
of zero.

A reversal reverses the event, and a second reversal reverses the first, so
reversals compose. An event carrying an even number of admitted `REVERSAL`
revisions stands as though none had been delivered and settles on its base,
and an event carrying an odd number is voided.

Only a `SETTLED` event contributes to a settled total or to a settled event
count.

## 6. Zone cells and the published baseline

A zone cell is a settlement day paired with the zone of the canonical site at
the effective instant. `published_baseline.json` carries the settled watt-hours
and the settled event count that a prior publication stated for each zone cell.
The baseline is read and never written.

The restatement of a zone cell is the difference between the value this run
computes and the value the baseline states. A zone cell whose watt-hour
difference and whose event count difference are both zero carries no adjustment
row. Every other zone cell carries exactly one, and the cells weighed are the
cells the baseline states together with the cells this run computes. A cell the
baseline states and this run computes nothing for is restated to zero rather
than left out.

## 7. Configuration

Three layers are read in this order: `settlement_defaults.ini`, then
`network_policy.conf`, then `site_overrides.properties`. For every key outside
the `rounding.` namespace the value from the last layer that sets it governs.
For every key inside the `rounding.` namespace the numerically smallest value
set by any layer governs, whichever layer set it.

`rounding.quantity_dp` is the number of decimal places the per event kilowatt
hour presentation carries. `rounding.total_dp` is the number of decimal places
the per partition kilowatt hour presentation carries. Both presentations are
derived from the integer watt-hour value by dividing by one thousand and
quantizing once under round half to even.

`settlement.exclusion_policy` decides whether an `EXCLUDED` event occupies a row
in its settlement partition. The value `include` places the row and the value
`omit` withholds it. The event remains in the ledger either way.

## 8. Written instants

An instant is delivered in one of two written forms. The first is twenty
characters ending in `Z` and states the instant in UTC directly. The second is
twenty five characters ending in a fixed offset written as a sign, two digits,
a colon and two digits, and states a local reading of the same instant. The
offset is the amount by which that producing system's clock runs ahead of UTC,
so the UTC instant is the written instant with the offset taken off it.

A producing system writes every instant in one form for the whole of a batch.
Which form a batch uses is a property of the producing system, and the form is
visible in the field itself.

Both forms name the same instant and neither is preferred. Every rule in this
document, including calendar membership, the settlement day, the effective
instant and every effective dated read, operates on the UTC instant and never
on the characters as delivered. An instant in neither form fails check 3.

A written instant also has to name a moment that exists. Its date is a date of
the Gregorian calendar, so the day of the month never exceeds the length of
that month and February carries a twenty ninth day only in a leap year, and its
hour runs from `00` to `23`. A field that has the shape of either form and
names a date or a time that does not exist is not an instant at all and fails
check 3. It never reaches check 4.
"""

CALENDAR = """# Settlement calendar

The settlement day is the unit of partitioning. A settlement day opens at
`06:00:00Z` and runs for twenty four hours, and the interval is half open, so
the instant at which a day opens belongs to that day and the instant at which it
closes belongs to the next one.

The settlement day of an event is the day whose half open window contains the
effective instant of that event. The day is keyed by the calendar date on which
its window opens, written as eight digits with no separator.

The calendar for this materialization holds exactly these eight days and no
others:

```
20310308  opens 2031-03-08T06:00:00Z
20310309  opens 2031-03-09T06:00:00Z
20310310  opens 2031-03-10T06:00:00Z
20310311  opens 2031-03-11T06:00:00Z
20310312  opens 2031-03-12T06:00:00Z
20310313  opens 2031-03-13T06:00:00Z
20310314  opens 2031-03-14T06:00:00Z
20310315  opens 2031-03-15T06:00:00Z
```

The window of `20310315` closes at `2031-03-16T06:00:00Z`. An instant that falls
outside the union of these eight windows is outside the calendar.

The date portion of an instant is not the settlement day of that instant, and
the two disagree for every instant between midnight and the day open. An
instant delivered in the fixed offset form has to be carried to UTC before its
date portion or its settlement day means anything at all.
"""

ENTITY = """# Entity model

## Site identity

A batch row carries a site reference as the producing system wrote it. A site
reference joins to a registered site only after normalization. Normalization
applies Unicode NFC composition, replaces tab characters with spaces, collapses
every run of whitespace to one space, removes whitespace that pads a hyphen,
strips the leading and trailing whitespace, and case folds the result to upper
case. Two references that normalize to the same string denote the same site.
Two references that differ before normalization and agree after it are not a
conflict.

`entity_aliases.tsv` and `entity_aliases_partner.psv` record the reference forms
two upstream systems are known to emit. They are a record of observed forms and
they are not a substitute for the normalization above.

## Merges

`site_merges.csv` records that one site was absorbed into another at an instant.
A merge applies to an event only when the effective instant of that event is at
or after the merge instant of that hop. An event whose effective instant
precedes the merge instant keeps the absorbed site as its canonical site.

Merges chain. Where a site was absorbed into a second site that was itself
absorbed into a third, each hop is taken only when the effective instant is at
or after that hop's own merge instant, and the chain stops at the first hop
whose merge instant the effective instant precedes.

The canonical site of an event is the site the chain reaches. The source site is
the registered site the normalized reference denotes before any hop is taken.

## Effective dated reference data

`sites_effective.csv`, `operational_state.csv`, `max_interval_limits.csv` and
`meter_registry.csv` each carry rows bounded by `valid_from` and `valid_to`.
Every such interval is half open, so a row governs an instant that is at or
after `valid_from` and strictly before `valid_to`.

These files are corrected in place rather than rewritten, so for one key more
than one row can cover one instant. Where that happens the row whose
`valid_from` is the latest governs, and where two covering rows carry the same
`valid_from` the one whose `valid_to` is the earliest governs, because the
narrower row is the later correction. The order the rows appear in the file
decides nothing, and a correction sits ahead of the row it corrects as often
as behind it.

A key can also carry no row covering an instant at all. A gap is not a zero
and not a default: what a gap means is decided for each file by the rule that
reads it, and for `max_interval_limits.csv` the protocol makes it an
unresolvable condition.

A meter is the meter of a site only over the interval its registration row
bounds. A site that changes meter inside the calendar keeps the row for the
meter that went out alongside the row for the one that came in, so a meter id
can appear in the file and still hold no registration at the instant a reading
occurred.

Every registration in `meter_registry.csv` carries a `pulse_multiplier`, the
whole number of metered units one delivered count stands for. A row whose
`pulse_multiplier` is absent, or is not a positive decimal integer written in
the ten ASCII digits, is not a registration at all: it covers no instant and it
governs nothing, and a meter holds a registration over that window only if
another row of the file provides one. Such a row is not an exception and it is
reported nowhere.

Every effective dated lookup is made against the canonical site of the event and
at the effective instant of the event. A lookup made against the source site, or
made at the ingestion instant, or made against the row that is current at the
end of the calendar, resolves to a different row for part of the population.
The one lookup that is not made at the effective instant is the pulse
multiplier of a delivered row, which the protocol reads at that row's own
`occurred_at` because a row is read as delivered.
"""

CODES = """# Closed vocabularies

Every code named here is closed. A record carries one code drawn from the set
its field belongs to and no other value ever appears in that field.

## Reason codes, carried by a rejected row

```
BAD_QUANTITY      the quantity field is present and is not a numeral of the
                  grammar record-layouts.md gives for the batch's unit
BAD_TIMESTAMP     occurred_at does not parse as an instant in either of the
                  two written forms the protocol defines, or names a date or
                  a time that does not exist
MALFORMED_ROW     revision_class is outside the five defined classes, or
                  revision_no is not a positive decimal integer written in
                  ASCII digits
METER_SITE_MISMATCH  the meter registration covering the instant names a
                  site other than the one the normalized reference denotes
OUT_OF_CALENDAR   occurred_at parses and falls outside the settlement calendar
UNKNOWN_METER     meter_id holds no registration in meter_registry.csv
                  covering the instant the row occurred at
UNKNOWN_SITE      the normalized site reference is not a registered site
```

## Unresolvable codes

```
MISSING_BASE       every admitted revision of the event is a RESTATEMENT
MISSING_BATCH      an ACTIVE manifest row names a file that is absent
MISSING_CEILING    no row of max_interval_limits.csv covers the canonical
                   site of the event at its effective instant
ORPHAN_SUPERSEDE   the canonical revision supersedes a revision_no that no
                   admitted revision of the event carries
```

## Revision classes

```
AMENDMENT   ORIGINAL   CORRECTION   RESTATEMENT   REVERSAL
```

## Outcomes

```
DEFERRED   EXCLUDED   SETTLED   UNRESOLVABLE   VOIDED
```

## Adjustment kinds

```
COUNT_ONLY   DECREASE   INCREASE
```

## Tariff bands

The band names `tariff_classes.csv` carries for the class, plus the literal
`UNBANDED` for a quantity below every threshold of that class.

## Revision roles

```
BASE                the base revision of its event
CANONICAL           the canonical revision of its event
DISPLACED           an admitted RESTATEMENT another RESTATEMENT of the
                    same event displaced, and which is neither canonical
                    nor base
RESTATEMENT_STACK   any other admitted RESTATEMENT that is not canonical
SUPERSEDED          any other admitted revision
```

A revision that is both canonical and the base of its event carries
`CANONICAL`, because a revision carries exactly one role and `CANONICAL`
governs. A displaced revision that is canonical carries `CANONICAL` and a
displaced revision that is the base carries `BASE`, for the same reason.

## Stack states

```
ABSENT      the revision carries no quantity, so it added nothing
APPLIED     the delta reached the clamped base
DISPLACED   another RESTATEMENT of the event named this revision_no
WITHHELD    the event never reached its quantity chain
```

A stack state is decided in the order `DISPLACED`, then `WITHHELD`, then
`ABSENT`, then `APPLIED`, and the first one that holds governs.
"""

LAYOUTS = """# Record layouts

Six batch families deliver revisions. Every family carries the same ten logical
fields and the families differ in serialization, in field order and in the unit
the quantity field is written in.

```
family      files                      serialization   header   quantity unit
desk        readings_desk_NN.csv       comma           yes      kilowatt hours
import      readings_import_NN.jsonl   json per line   no       kilowatt hours
relay       readings_relay_NN.tsv      tab             yes      kilowatt hours
partner     readings_partner_NN.psv    pipe            yes      kilowatt hours
legacy      readings_legacy_NN.fixed   fixed width     no       kilowatt hours
adjustment  adjustments_NN.jsonl       json per line   no       watt hours
```

The field name `quantity` therefore denotes a decimal count of kilowatt hours in
five families and a whole count of watt hours in the sixth. The unit is a
property of the batch family and never of the row.

The delimited families carry a header line naming their columns. The partner
family writes the same ten columns in a different order from the others, and the
header states that order.

The partner family stamps `occurred_at` and `ingested_at` in the fixed offset
form, and the other five stamp them in the Z form. Both forms are defined in
the protocol, which also states how an offset instant is carried to UTC.

The fixed width family carries no header. Its columns occupy these widths in
this order, and every field is left aligned and padded with spaces:

```
event_key            12
revision_no           4
revision_class       12
site_ref             16
meter_id             10
occurred_at          22
ingested_at          22
quantity             14
delta_flag            2
supersedes_revision   4
```

The json families write every field as a string. A field that carries no value
is written as an empty string in every family.

A quantity is a numeral written in ASCII characters. In the five kilowatt hour
families a numeral is an optional sign `+` or `-`, one or more digits, and
optionally a point followed by one or more digits. In the watt hour family a
numeral is an optional sign followed by one or more digits and nothing else.
No other spelling is a numeral in either unit: not an exponent, not a digit
group separator, not a point with no digit on one side of it, and not a named
value such as `NaN` or `Infinity`. A leading sign, leading zeros and trailing
zeros in the fraction are part of the grammar and do not change the value.
The padding a fixed width column carries is not part of the field.

Every batch is UTF-8 text. A line ends at a line feed, and a carriage return
immediately ahead of the line feed belongs to the line ending rather than to
the last field. A producing system may write a byte order mark ahead of the
first line; it belongs to no line and to no field.

An empty `quantity` denotes an interval that was delivered without a reading. An
empty `supersedes_revision` denotes a revision that supersedes nothing. A
quantity of zero is a delivered reading of zero and is a different thing from an
empty quantity.
"""

CONTRACT = """# Ledger output contract

Twenty four deliverables are written under `/app/out`. Every one of them is
written in UTF-8 with Unix line endings and a trailing newline, and no
deliverable carries a timestamp, a hostname or a path taken from the run.

## Serialization

A file whose name ends `.jsonl` carries one JSON object per line, serialized
with sorted keys and with no space after the separators.

A file whose name ends `.json` carries one JSON document, serialized with sorted
keys and an indent of two spaces.

A file whose name ends `.csv` carries a header line naming its columns in the
order this document gives, then one line per record, comma separated, with no
quoting and no escaping. No value written to a `.csv` deliverable contains a
comma.

Integers are written in decimal with no separators and no sign on a positive
value. A negative integer carries a leading minus. Kilowatt hour presentations
are written as a decimal string with exactly the number of decimal places the
resolved rounding configuration gives.

## The deliverables

```
materialize.py               the reusable program
canonical_ledger.jsonl       one object per event
revision_index.jsonl         one object per admitted revision
partition_20310308.csv       through partition_20310315.csv, one per day
partition_manifest.json      one entry per settlement day
rejects.csv                  one line per rejected row
quarantine.jsonl             one object per conflicting row
dedup_ledger.csv             one line per duplicate row
deferred.jsonl               one object per deferred event
unresolvable.json            events and missing batches
entity_resolution.json       one entry per event whose source site was merged
clamp_register.csv           one line per event a clamp reduced
stack_register.csv           one line per admitted restatement delta
restatement_adjustments.csv  one line per changed zone cell
reconciliation.json          the three identities
validation_report.txt        eight lines
run_manifest.json            the run's resolved decisions
```

## Field orders and orderings

`canonical_ledger.jsonl` carries the keys `canonical_site`, `event_key`,
`outcome`, `quantity_kwh`, `quantity_wh`, `revision_class`, `revision_no`,
`settlement_day`, `source_site`, `tariff_band`, `tariff_class` and `zone`. Lines are ordered by
`settlement_day`, then `canonical_site`, then `event_key`, each ascending as a
string. Every event appears exactly once, whatever its outcome.

`revision_index.jsonl` carries the keys `batch_id`, `event_key`, `family`,
`is_canonical`, `quantity_wh`, `revision_class`, `revision_no` and `role`.
`family` is the batch family the revision arrived in, written as one of
`adjustment`, `desk`, `import`, `legacy`, `partner` or `relay`.
`quantity_wh` is the integer watt-hour value of that revision as delivered,
after its pulse multiplier and the single conversion and before any clamp, and
is null when the revision carries no quantity. Lines are
ordered by `event_key`, then `revision_no`, then `revision_class`, then
`family`, each ascending as a string except `revision_no` which ascends as an
integer. Only admitted revisions appear.

Each `partition_YYYYMMDD.csv` carries the columns `sequence_no`, `event_key`,
`canonical_site`, `zone`, `tariff_band`, `outcome`, `quantity_wh`. Rows hold the
events of that settlement day in the order those events occupy in
`canonical_ledger.jsonl`, and `sequence_no` counts those rows from one within
each partition file.

`partition_manifest.json` carries one key `partitions`, an array of eight
objects in ascending `settlement_day`, each with the keys `settlement_day`,
`row_count`, `settled_event_count`, `settled_wh` and `settled_kwh`. `row_count`
is the number of rows the partition file carries.

`rejects.csv` carries the columns `batch_id`, `filename`, `line_no`,
`event_key`, `reason_code`, ordered by `batch_id` then `line_no`. `line_no`
counts lines of the batch body from one, and a header line is not a body line.

`quarantine.jsonl` carries the keys `batch_id`, `event_key`, `line_no`,
`revision_class` and `revision_no`, ordered by `batch_id` then `line_no`.

`dedup_ledger.csv` carries the columns `batch_id`, `line_no`, `event_key`,
`revision_no`, `revision_class`, ordered by `batch_id` then `line_no`.

`deferred.jsonl` carries the keys `canonical_site`, `event_key`,
`revision_no` and `settlement_day`, ordered by `event_key`.

`unresolvable.json` carries the keys `events` and `missing_batches`. Each entry
of `events` carries `canonical_site`, `event_key`, `reason_code` and
`settlement_day`, ordered by `event_key`. Each entry of `missing_batches`
carries `batch_id`, `filename` and `reason_code`, ordered by `batch_id`.

`entity_resolution.json` carries the key `resolutions`, an array whose entries
carry `canonical_site`, `event_key`, `merge_applied` and `source_site`, ordered
by `event_key`. An event appears here when its source site has a row in
`site_merges.csv`, whether or not the merge applied.

`clamp_register.csv` carries the columns `event_key`, `canonical_site`,
`max_interval_wh`, `base_wh`, `base_clamped_wh`, `stack_delta_wh`, `final_wh`
and `clamp_stage`, ordered by `event_key`. An event appears here when a clamp
changed a value, and only then. A clamp changes a value when it lowers a figure
that sits above the ceiling and equally when it raises a figure that sits below
zero, and both count here. `base_wh` is the base revision's watt-hour value
before any clamp, `base_clamped_wh` is that value after the first clamp,
`stack_delta_wh` is the sum of the restatement deltas that were then added, and
`final_wh` is the value after the second clamp. `clamp_stage` is `BASE` when
only the first clamp changed a value, `SUM` when only the second did, and
`BOTH` when each of them did.

`stack_register.csv` carries the columns `event_key`, `revision_no`,
`family`, `delta_wh` and `stack_state`, ordered by `event_key`, then
`revision_no` ascending as an integer, then `family`. One line appears for
every admitted `RESTATEMENT` revision of every event that carries at least
one, whatever the outcome of that event. `delta_wh` is the signed watt-hour
delta the revision delivered, before any clamp, and is zero when the revision
carries no quantity. `stack_state` is drawn from the stack states
`reason-codes.md` closes.

`restatement_adjustments.csv` carries the columns `settlement_day`, `zone`,
`adjustment_kind`, `baseline_settled_wh`, `restated_settled_wh`, `delta_wh`,
`baseline_event_count`, `restated_event_count`, `delta_events`, ordered by
`settlement_day` then `zone`. `adjustment_kind` is `INCREASE` when the watt-hour
difference is above zero, `DECREASE` when it is below zero, and `COUNT_ONLY`
when the watt-hour difference is zero and the event count difference is not.
The rows are drawn from the union of the zone cells the publication states and
the zone cells this run computes, so a cell the publication states and this
run computes nothing for carries a row whose restated figures are zero.

`reconciliation.json` carries the keys `identity_class_partition`,
`identity_partition_rollup` and `identity_restatement`.
`identity_class_partition` carries `admitted`, `conflict`, `duplicate`,
`rejected`, `residual` and `total_rows`, where `total_rows` is the number of
body lines read from in scope batches and `residual` is the sum of the four
dispositions less `total_rows`. `identity_partition_rollup` carries
`ledger_settled_wh`, `partition_settled_wh` and `residual`, where `residual` is
the partition figure less the ledger figure. `identity_restatement` carries
`adjustment_delta_wh`, `baseline_settled_wh`, `restated_settled_wh` and
`residual`, where the first three are summed over every zone cell and `residual`
is the baseline plus the adjustment less the restated figure.

`validation_report.txt` carries exactly eight lines in this order and this
shape, where the last three state the size of the population the run's own
check covered:

```
CLASS_PARTITION residual=<integer>
PARTITION_ROLLUP residual=<integer>
RESTATEMENT residual=<integer>
ROUNDING quantity_dp=<integer> total_dp=<integer>
EXCLUSION policy=<include or omit>
CLAMPED events=<integer>
UNRESOLVED events=<integer>
DISPLACED revisions=<integer>
```

`CLAMPED events` is the number of lines `clamp_register.csv` carries,
`UNRESOLVED events` is the number of entries the `events` array of
`unresolvable.json` carries, and `DISPLACED revisions` is the number of lines
`stack_register.csv` carries whose `stack_state` is `DISPLACED`.

`run_manifest.json` carries the keys `batches_ingested`, `batches_withdrawn`,
`config_resolved`, `config_winner` and `row_exceptions`. `batches_ingested` is
the sorted array of `batch_id` values that were read. `batches_withdrawn` is
the sorted array of `batch_id` values whose status kept them out of scope. A
`filename` that carries more than one manifest row is named by each of its
`batch_id` values, so the same file can be named in both arrays.
`config_resolved` maps every configuration key to its resolved value as a
string. `config_winner` maps every configuration key to the file name of the
layer whose value governed. `row_exceptions` is an array ordered by `batch_id`
whose entries carry `batch_id`, `declared_rows`, `filename` and
`observed_rows`.

## The program

`materialize.py` accepts `--data` naming a corpus directory and `--out` naming a
destination directory, and writing every deliverable other than itself into the
destination. It reads nothing outside the directory `--data` names, and it uses
only the Python standard library.
"""

GLOSSARY = """# Glossary

**admitted revision** A delivered row that passed validation and was the first
row read carrying its delivery identity.

**base revision** The highest ranked admitted revision of an event whose class
is not `RESTATEMENT`.

**canonical revision** The admitted revision of an event that the class rank,
the revision number and the batch sequence select.

**canonical site** The site an event's merge chain reaches at that event's
effective instant.

**delivery identity** The triple of `event_key`, `revision_no` and
`revision_class`.

**effective instant** The `occurred_at` of an event's canonical revision.

**event** The logical unit an `event_key` names. One event carries one or more
delivered revisions and receives exactly one outcome.

**in scope batch** A batch whose manifest row carries the status `ACTIVE`.

**settlement day** The half open twenty four hour window opening at `06:00:00Z`
that contains an event's effective instant.

**source site** The registered site an event's normalized site reference denotes
before any merge hop is taken.

**zone cell** A settlement day paired with the zone of the canonical site at the
effective instant.
"""

RESTATEMENT = """# Restatement notes

A publication states, for each zone cell, the settled watt-hours and the settled
event count the network published for that cell. A later materialization of the
same calendar can reach a different figure for a cell, because a revision
delivered after the publication changes the canonical revision of an event,
because a merge instant moves an event onto a different canonical site, or
because an effective dated attribute places an event in a different zone.

A restatement is the difference between what this run computes for a zone cell
and what the publication states for it. It is signed. A cell whose figures both
agree with the publication is not restated and no adjustment record is written
for it.

The cells a restatement covers are the cells the publication states together
with the cells this run computes, and never one of the two alone. A zone the
network has retired since the publication is stated by the publication and
computed by nothing here, so this run restates that cell to zero: its restated
watt-hours and its restated event count are both zero and its deltas are the
negatives of the published figures. A cell this run computes that the
publication never stated is restated from zero in the same way.

The publication is an input. It is never rewritten, and the figures it carries
are never substituted for the figures this run computes. A run whose adjustment
record simply repeats the publication's figures has computed nothing.

The publication is granular to the zone cell and never to the partition, so the
figures it carries do not state any partition total and cannot be read as one.
"""

DEFAULTS_INI = """; Marrowgate settlement defaults. Lowest precedence layer.
[rounding]
rounding.quantity_dp = 3
rounding.total_dp = 2

[settlement]
settlement.exclusion_policy = omit
settlement.day_offset_hours = 6
settlement.calendar_days = 8
"""

POLICY_CONF = """# Network policy. Applied after the defaults.
rounding.quantity_dp = 2
settlement.exclusion_policy = include
settlement.calendar_days = 8
"""

OVERRIDES_PROPERTIES = """# Site overrides. Applied last.
rounding.quantity_dp=4
rounding.total_dp=1
settlement.day_offset_hours=6
"""

DOCS = {
    "settlement-protocol.md": PROTOCOL,
    "settlement-calendar.md": CALENDAR,
    "entity-model.md": ENTITY,
    "reason-codes.md": CODES,
    "record-layouts.md": LAYOUTS,
    "ledger-output-contract.md": CONTRACT,
    "glossary.md": GLOSSARY,
    "restatement-notes.md": RESTATEMENT,
    "settlement_defaults.ini": DEFAULTS_INI,
    "network_policy.conf": POLICY_CONF,
    "site_overrides.properties": OVERRIDES_PROPERTIES,
}


# ==========================================================================
# Harness: the verifier owns its own corpus builder and its own engine, so
# every expected value below is recomputed rather than stored. /app/data does
# not exist in this container and is never read.
#
# The agent's program is hostile input. Every execution of it goes through
# _run_program, which drops to an unprivileged user where the image supports
# it, gives the child its own session, and kills that session's whole process
# group once the run returns, so nothing the agent spawned outlives the call.
# ==========================================================================

VISIBLE_SEED = 8143207751
HIDDEN_SEED = 5520914637

_CACHE = {}
_LOCK = threading.RLock()


def _drop_privileges_prefix():
    """The setpriv prefix that runs agent code as nobody, or an empty prefix
    when the image cannot support it. Probed once, so a verifier image without
    setpriv still grades rather than failing every test."""
    if "setpriv" in _CACHE:
        return _CACHE["setpriv"]
    prefix = []
    if os.name == "posix" and getattr(os, "geteuid", None) and os.geteuid() == 0:
        found = shutil.which("setpriv")
        if found:
            candidate = [found, "--reuid=nobody", "--regid=nogroup",
                         "--clear-groups"]
            try:
                probe = subprocess.call(candidate + [sys.executable, "-c", ""],
                                        timeout=60,
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
                if probe == 0:
                    prefix = candidate
            except (OSError, subprocess.SubprocessError):
                prefix = []
    _CACHE["setpriv"] = prefix
    return prefix


def _run_program(program, datadir, outdir, timeout=900):
    """Execute the delivered program once and return its exit status. Returns
    -1 when it could not be started or did not finish."""
    if not os.path.isfile(program):
        return -1
    prefix = _drop_privileges_prefix()
    if prefix:
        # the unprivileged child must be able to read the corpus and write the
        # destination, and must still not be able to read /tests
        for root, dirs, files in os.walk(datadir):
            os.chmod(root, 0o755)
            for name in files:
                try:
                    os.chmod(os.path.join(root, name), 0o644)
                except OSError:
                    pass
        os.chmod(outdir, 0o777)
        # an agent editor writes through a temp file and renames it, so the
        # delivered program can land at mode 0600 and the unprivileged child
        # cannot open it; the verifier is root, so grant read on it first
        try:
            os.chmod(os.path.dirname(program) or ".", 0o755)
            os.chmod(program, 0o644)
        except OSError:
            pass
    command = prefix + [sys.executable, program, "--data", datadir,
                        "--out", outdir]
    environment = dict(os.environ)
    environment["TMPDIR"] = outdir
    child = None
    try:
        child = subprocess.Popen(command, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL,
                                 start_new_session=(os.name == "posix"),
                                 env=environment)
        status = child.wait(timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        status = -1
    finally:
        if child is not None:
            _kill_session(child)
    return status


def _kill_session(child):
    """Take down the child and anything it spawned, so a daemonized helper
    cannot outlive grading and rewrite the reward."""
    try:
        if child.poll() is None:
            child.kill()
    except OSError:
        pass
    if os.name != "posix":
        return
    try:
        os.killpg(os.getpgid(child.pid), signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass


def _build(seed):
    directory = tempfile.mkdtemp(prefix="mg-corpus-")
    write_corpus(seed, directory, DOCS)
    make_baseline(directory, seed)
    return directory


def _out(workspace):
    """The directory the agent's deliverables sit in under the workspace."""
    override = os.environ.get("MG_ARTIFACT_ROOT")
    return override if override else str(Path(workspace) / "out")


def _visible():
    """The corpus the agent was given, rebuilt from its seed, with the exact
    expected bytes of every deliverable and the reference state behind them.
    rewardkit runs checks on worker threads, so the build happens once under
    a lock and every check reads the cached result."""
    with _LOCK:
        if "vis" not in _CACHE:
            directory = _build(VISIBLE_SEED)
            files, state = expected_artifacts(directory)
            _CACHE["vis"] = (directory, files, state)
        return _CACHE["vis"]


def _hidden(out):
    """Regenerate an unseen corpus, run the delivered program against it and
    return the produced directory beside the recomputed expectation."""
    with _LOCK:
        if "hid" not in _CACHE:
            data = _build(HIDDEN_SEED)
            produced = tempfile.mkdtemp(prefix="mg-hidden-out-")
            status = _run_program(os.path.join(out, "materialize.py"), data,
                                  produced)
            _CACHE["hid"] = (data, produced, status,
                             expected_artifacts(data)[0])
        return _CACHE["hid"]


def _read(directory, name):
    path = os.path.join(directory, name)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8", errors="replace", newline="") as handle:
        return handle.read()


def _need(out, name):
    text = _read(out, name)
    if text is None:
        raise AssertionError("required deliverable is absent: " + name)
    return text


def _jsonl(text):
    return [json.loads(ln) for ln in text.split("\n") if ln != ""]


def _rows(text):
    lines = [ln for ln in text.split("\n") if ln != ""]
    head = lines[0].split(",")
    return [dict(zip(head, ln.split(","))) for ln in lines[1:]]


def _holds(probe, *args):
    """Run one probe. Any failed assertion or any error reading the agent's
    output means the property does not hold, so a check never raises."""
    try:
        return bool(probe(*args))
    except Exception:
        return False


def _column(out, name, fields):
    """Assert one column of the ledger across every event the corpus carries.
    Each rule sweep owns its own columns, so no two of them and none of the
    whole artifact tests read the same fact twice."""
    _directory, _files, state = _visible()
    got = {}
    for line in _jsonl(_need(out, "canonical_ledger.jsonl")):
        got[line.get("event_key")] = line
    for event in state["ledger"]:
        line = got.get(event["event_key"])
        if line is None:
            raise AssertionError("event missing from the ledger: "
                                 + event["event_key"])
        for field, expected in fields(event):
            if line.get(field) != expected:
                raise AssertionError((name, event["event_key"], field))
    return True


def _whole(out, names):
    _directory, files, _state = _visible()
    for name in names:
        if _need(out, name) != files[name]:
            raise AssertionError(name)
    return True


def _hidden_whole(out, names):
    _data, produced, status, expected = _hidden(out)
    if status != 0:
        raise AssertionError("the delivered program did not run to completion")
    for name in names:
        if _read(produced, name) != expected[name]:
            raise AssertionError(name)
    return True


PARTITIONS = ["partition_%s.csv" % d for d in DAYS]
EVENT_RECORD_FILES = ["rejects.csv", "quarantine.jsonl", "dedup_ledger.csv",
                      "deferred.jsonl", "unresolvable.json",
                      "clamp_register.csv"]
ALL_DELIVERABLES = [os.path.basename(p) for p in ARTIFACTS]


# ==========================================================================
# The ledger, split by observable. One check per documented rule, each owning
# its own columns, so a solver that broke exactly one rule loses exactly the
# weight of that rule here and no fact is paid for twice.
# ==========================================================================

def _ledger_structure(out):
    text = _need(out, "canonical_ledger.jsonl")
    _directory, _files, state = _visible()
    if not text.endswith("\n") or "\r" in text:
        return False
    keys = ["canonical_site", "event_key", "outcome", "quantity_kwh",
            "quantity_wh", "revision_class", "revision_no", "settlement_day",
            "source_site", "tariff_band", "tariff_class", "zone"]
    seen = []
    for raw in [ln for ln in text.split("\n") if ln != ""]:
        obj = json.loads(raw)
        if sorted(obj) != keys:
            return False
        if raw != json.dumps(obj, sort_keys=True, separators=(",", ":")):
            return False
        seen.append((obj["settlement_day"], obj["canonical_site"],
                     obj["event_key"]))
    if seen != sorted(seen):
        return False
    if len(seen) != len(set(t[2] for t in seen)):
        return False
    return (set(t[2] for t in seen)
            == set(e["event_key"] for e in state["ledger"]))


@criterion(description="canonical_ledger.jsonl holds every event exactly once with the documented keys, serialization and three key ordering")
def canonical_ledger_structure_and_order(workspace: Path) -> bool:
    return _holds(_ledger_structure, _out(workspace))


@criterion(description="every event's revision_no and revision_class are the canonical revision: class rank, then revision number, then lowest batch_seq")
def canonical_revision_selected_by_class_rank(workspace: Path) -> bool:
    return _holds(_column, _out(workspace), "canonical revision",
                  lambda e: [("revision_no", e["revision_no"]),
                             ("revision_class", e["revision_class"])])


@criterion(description="every event's settlement_day is the half open window opening at 06:00:00Z that holds its UTC effective instant")
def settlement_day_window_across_every_event(workspace: Path) -> bool:
    return _holds(_column, _out(workspace), "settlement day",
                  lambda e: [("settlement_day", e["settlement_day"])])


@criterion(description="every event's source_site and canonical_site follow normalization and the merge chain walked at the effective instant")
def site_resolution_across_every_event(workspace: Path) -> bool:
    return _holds(_column, _out(workspace), "site resolution",
                  lambda e: [("source_site", e["source_site"]),
                             ("canonical_site", e["canonical_site"])])


@criterion(description="every event's zone and tariff_class are read for the canonical site at the effective instant")
def effective_dated_attributes_across_every_event(workspace: Path) -> bool:
    return _holds(_column, _out(workspace), "effective dated attributes",
                  lambda e: [("zone", e["zone"]),
                             ("tariff_class", e["tariff_class"])])


def _quantity_chain(out):
    _directory, _files, state = _visible()
    places = state["q_dp"]
    got = {}
    for line in _jsonl(_need(out, "canonical_ledger.jsonl")):
        got[line.get("event_key")] = line
    for event in state["ledger"]:
        line = got.get(event["event_key"])
        if line is None:
            return False
        if line.get("quantity_wh") != event["quantity_wh"]:
            return False
        if line.get("quantity_kwh") != kwh_text(event["quantity_wh"], places):
            return False
    return True


@criterion(description="every event's quantity_wh and quantity_kwh follow the unit, numeral grammar, exact half even conversion, both clamps and the restatement stack")
def quantity_chain_across_every_event(workspace: Path) -> bool:
    return _holds(_quantity_chain, _out(workspace))


@criterion(description="every event's tariff_band is the greatest threshold at or below its final quantity, or UNBANDED")
def tariff_band_floor_across_every_event(workspace: Path) -> bool:
    return _holds(_column, _out(workspace), "tariff band",
                  lambda e: [("tariff_band", e["tariff_band"])])


@criterion(description="every event's outcome follows the documented precedence from the orphan supersede down to SETTLED")
def outcome_precedence_across_every_event(workspace: Path) -> bool:
    return _holds(_column, _out(workspace), "outcome",
                  lambda e: [("outcome", e["outcome"])])


# ==========================================================================
# The other artifacts, whole. Each file is read by exactly one of these.
# ==========================================================================

@criterion(description="revision_index.jsonl matches the recomputed staged index byte for byte")
def revision_index_exact(workspace: Path) -> bool:
    return _holds(_whole, _out(workspace), ["revision_index.jsonl"])


@criterion(description="all eight partition files match the recomputed partitions byte for byte")
def partition_files_exact(workspace: Path) -> bool:
    return _holds(_whole, _out(workspace), PARTITIONS)


def _partitions_agree(out):
    _directory, _files, state = _visible()
    place_excluded = state["include_excluded"]
    ledger = _jsonl(_need(out, "canonical_ledger.jsonl"))
    for day in DAYS:
        wanted = [line["event_key"] for line in ledger
                  if line["settlement_day"] == day
                  and (line["outcome"] != "EXCLUDED" or place_excluded)]
        rows = _rows(_need(out, "partition_%s.csv" % day))
        if [row["event_key"] for row in rows] != wanted:
            return False
        if ([int(row["sequence_no"]) for row in rows]
                != list(range(1, len(rows) + 1))):
            return False
    return True


@criterion(description="the agent's partitions hold its own ledger rows for each day under the resolved exclusion policy, in ledger order, numbered from one")
def partitions_agree_with_the_ledger(workspace: Path) -> bool:
    return _holds(_partitions_agree, _out(workspace))


@criterion(description="rejects, quarantine, dedup ledger, deferred, unresolvable and clamp register match the recomputed files byte for byte")
def event_records_exact(workspace: Path) -> bool:
    return _holds(_whole, _out(workspace), EVENT_RECORD_FILES)


@criterion(description="stack_register.csv matches the recomputed restatement stack byte for byte")
def stack_register_exact(workspace: Path) -> bool:
    return _holds(_whole, _out(workspace), ["stack_register.csv"])


@criterion(description="entity_resolution.json matches the recomputed merge decisions byte for byte")
def entity_resolution_exact(workspace: Path) -> bool:
    return _holds(_whole, _out(workspace), ["entity_resolution.json"])


@criterion(description="partition_manifest.json matches the recomputed per day counts and totals byte for byte")
def partition_manifest_exact(workspace: Path) -> bool:
    return _holds(_whole, _out(workspace), ["partition_manifest.json"])


@criterion(description="restatement_adjustments.csv matches the recomputed signed deltas against the published baseline byte for byte")
def restatement_adjustments_exact(workspace: Path) -> bool:
    return _holds(_whole, _out(workspace), ["restatement_adjustments.csv"])


@criterion(description="reconciliation.json matches the recomputed three identities byte for byte")
def reconciliation_exact(workspace: Path) -> bool:
    return _holds(_whole, _out(workspace), ["reconciliation.json"])


@criterion(description="validation_report.txt and run_manifest.json match the recomputed self check and branch decisions byte for byte")
def run_records_exact(workspace: Path) -> bool:
    return _holds(_whole, _out(workspace),
                  ["validation_report.txt", "run_manifest.json"])


def _identity_triangle(out):
    ledger = _jsonl(_need(out, "canonical_ledger.jsonl"))
    manifest = json.loads(_need(out, "partition_manifest.json"))
    adjust = _rows(_need(out, "restatement_adjustments.csv"))
    recon = json.loads(_need(out, "reconciliation.json"))

    ledger_wh = sum(int(r["quantity_wh"]) for r in ledger
                    if r["outcome"] == "SETTLED")
    ledger_n = sum(1 for r in ledger if r["outcome"] == "SETTLED")
    partition_wh = 0
    partition_rows = 0
    for name in PARTITIONS:
        rows = _rows(_need(out, name))
        partition_rows += len(rows)
        partition_wh += sum(int(r["quantity_wh"]) for r in rows
                            if r["outcome"] == "SETTLED")
    checks = [
        partition_wh == ledger_wh,
        sum(int(p["settled_wh"]) for p in manifest["partitions"]) == ledger_wh,
        sum(int(p["settled_event_count"])
            for p in manifest["partitions"]) == ledger_n,
        sum(int(p["row_count"])
            for p in manifest["partitions"]) == partition_rows,
    ]
    for row in adjust:
        checks.append(int(row["baseline_settled_wh"]) + int(row["delta_wh"])
                      == int(row["restated_settled_wh"]))
        checks.append(int(row["baseline_event_count"])
                      + int(row["delta_events"])
                      == int(row["restated_event_count"]))
    partition = recon["identity_class_partition"]
    rollup = recon["identity_partition_rollup"]
    restatement = recon["identity_restatement"]
    checks += [
        int(partition["admitted"]) + int(partition["duplicate"])
        + int(partition["conflict"]) + int(partition["rejected"])
        == int(partition["total_rows"]),
        int(partition["residual"]) == 0,
        int(rollup["ledger_settled_wh"]) == ledger_wh,
        int(rollup["partition_settled_wh"]) == partition_wh,
        int(rollup["residual"]) == 0,
        int(restatement["restated_settled_wh"]) == ledger_wh,
        int(restatement["baseline_settled_wh"])
        + int(restatement["adjustment_delta_wh"])
        == int(restatement["restated_settled_wh"]),
        int(restatement["residual"]) == 0,
    ]
    return all(checks)


@criterion(description="ledger, partitions, partition manifest, adjustments and reconciliation agree with each other on all three identities")
def identity_triangle_holds(workspace: Path) -> bool:
    return _holds(_identity_triangle, _out(workspace))


# ==========================================================================
# The delivered program against a corpus it has never seen.
# ==========================================================================

@criterion(description="on an unseen corpus the delivered program writes the recomputed ledger and partitions byte for byte")
def unseen_corpus_ledger_and_partitions_exact(workspace: Path) -> bool:
    return _holds(_hidden_whole, _out(workspace),
                  ["canonical_ledger.jsonl"] + PARTITIONS)


@criterion(description="on an unseen corpus the delivered program writes the recomputed staged index, per event records and stack register byte for byte")
def unseen_corpus_event_records_exact(workspace: Path) -> bool:
    return _holds(_hidden_whole, _out(workspace),
                  ["revision_index.jsonl", "stack_register.csv"]
                  + EVENT_RECORD_FILES)


@criterion(description="on an unseen corpus the delivered program writes the recomputed adjustments, reconciliation and run records byte for byte")
def unseen_corpus_adjustments_and_reconciliation_exact(workspace: Path) -> bool:
    return _holds(_hidden_whole, _out(workspace),
                  ["restatement_adjustments.csv", "reconciliation.json",
                   "partition_manifest.json", "entity_resolution.json",
                   "validation_report.txt", "run_manifest.json"])


# ==========================================================================
# Shape. Weight one, and the content checks above cannot pass without it.
# ==========================================================================

@criterion(description="every declared deliverable was written at its declared path")
def all_declared_artifacts_present(workspace: Path) -> bool:
    out = _out(workspace)
    return all(_read(out, name) is not None for name in ALL_DELIVERABLES)


# ==========================================================================
# Negative checks. Each returns True when its shortcut is present, and False
# when the artifact it reads is absent, so a run that produced nothing scores
# zero rather than a negative number. Where a probe could be tripped by an
# unrelated mistake upstream it is restricted to the population that mistake
# cannot reach, so one wrong action draws one penalty.
# ==========================================================================

def _out_of_scope_keys(directory):
    """Event keys delivered only by batches the manifest keeps out of scope,
    the withdrawn rows and the file on disk with no manifest row, and by no
    in scope batch at all, so a key an in scope row also carries never
    counts here whatever the run did with that row."""
    manifest = read_manifest(directory)
    live = set(m["filename"] for m in manifest if m["status"] == "ACTIVE")
    listed = set(m["filename"] for m in manifest)
    outside = set()
    inside = set()
    for name in sorted(os.listdir(directory)):
        kind = "csv" if name == UNLISTED_BATCH else BATCH_KIND.get(name)
        if kind is None or (name not in listed and name != UNLISTED_BATCH):
            continue
        keys = set(rec.get("event_key", "") for rec in
                   _parse_batch(os.path.join(directory, name), kind))
        (inside if name in live else outside).update(keys)
    return outside - inside


def _probe_out_of_scope(out):
    directory, _files, state = _visible()
    text = _read(out, "canonical_ledger.jsonl")
    if text is None:
        return False
    keys = set(r["event_key"] for r in _jsonl(text))
    expected = set(r["event_key"] for r in state["ledger"])
    return len((keys - expected) & _out_of_scope_keys(directory)) > 0


@criterion(description="the ledger carries events that only a batch the manifest keeps out of scope delivers")
def negative_out_of_scope_batch_rows_ingested(workspace: Path) -> bool:
    return _holds(_probe_out_of_scope, _out(workspace))


def _index_by_identity(out):
    text = _read(out, "revision_index.jsonl")
    if text is None:
        return None
    got = {}
    for obj in _jsonl(text):
        got[(obj["event_key"], int(obj["revision_no"]), obj["revision_class"],
             obj.get("family"))] = obj["quantity_wh"]
    return got


def _probe_kwh_units(out):
    _directory, _files, state = _visible()
    got = _index_by_identity(out)
    if got is None:
        return False
    hits = 0
    for revision in state["ing"]["admitted"]:
        if revision["family"] != "adjustment":
            continue
        if revision["quantity_wh"] in (None, 0):
            continue
        key = (revision["event_key"], revision["revision_no"],
               revision["revision_class"], "adjustment")
        if got.get(key) == revision["quantity_wh"] * 1000:
            hits += 1
    return hits > 100


@criterion(description="the staged index shows adjustment family watt-hour quantities multiplied by a thousand")
def negative_adjustment_quantity_read_as_kilowatt_hours(workspace: Path) -> bool:
    return _holds(_probe_kwh_units, _out(workspace))


def _even_halves(state):
    """Admitted kilowatt hour revisions whose exact watt-hour value sits on a
    half above an even integer. Round half to even keeps the even integer;
    round half up, and only round half up, moves to the odd one above it."""
    found = []
    for revision in state["ing"]["admitted"]:
        text = revision.get("quantity_text", "")
        if revision["family"] == "adjustment" or text == "":
            continue
        exact = Decimal(text) * 1000
        floor = int(exact.to_integral_value(rounding="ROUND_FLOOR"))
        if exact - floor == Decimal("0.5") and floor % 2 == 0:
            found.append(((revision["event_key"], revision["revision_no"],
                           revision["revision_class"], revision["family"]),
                          floor))
    return found


def _probe_half_up(out):
    _directory, _files, state = _visible()
    got = _index_by_identity(out)
    if got is None:
        return False
    hits = sum(1 for key, floor in _even_halves(state)
               if got.get(key) == floor + 1)
    return hits >= 10


@criterion(description="the staged index shows kilowatt hour quantities that sit on a half watt-hour rounded half up")
def negative_quantity_rounded_half_up(workspace: Path) -> bool:
    return _holds(_probe_half_up, _out(workspace))


def _probe_reformatted(out):
    _directory, _files, state = _visible()
    text = _read(out, "quarantine.jsonl")
    if text is None:
        return False
    quarantined = set((o["batch_id"], int(o["line_no"])) for o in _jsonl(text))
    hits = sum(1 for r in state["ing"]["reformatted"]
               if (r["batch_id"], r["line_no"]) in quarantined)
    return hits >= 10


@criterion(description="quarantine.jsonl holds redeliveries whose payload differs from the admitted row only in how its numbers are written")
def negative_reformatted_duplicates_quarantined(workspace: Path) -> bool:
    return _holds(_probe_reformatted, _out(workspace))


def _probe_merge_early(out):
    _directory, _files, state = _visible()
    text = _read(out, "canonical_ledger.jsonl")
    if text is None:
        return False
    got = dict((line["event_key"], line) for line in _jsonl(text))
    hits = 0
    for event in state["ledger"]:
        if event["canonical_site"] != event["source_site"]:
            continue
        if event["source_site"] not in state["ref"]["merges"]:
            continue
        line = got.get(event["event_key"])
        if line is None:
            continue
        if line.get("revision_no") != event["revision_no"]:
            continue
        if line.get("revision_class") != event["revision_class"]:
            continue
        if line.get("canonical_site") != event["source_site"]:
            hits += 1
    return hits > 30


@criterion(description="the ledger takes merge hops for events whose effective instant precedes the merge instant")
def negative_merge_applied_before_merge_instant(workspace: Path) -> bool:
    return _holds(_probe_merge_early, _out(workspace))


def _probe_baseline_copied(out):
    text = _read(out, "restatement_adjustments.csv")
    if text is None:
        return False
    rows = _rows(text)
    if not rows:
        return False
    same = sum(1 for r in rows
               if r.get("baseline_settled_wh") == r.get("restated_settled_wh"))
    return same == len(rows)


@criterion(description="every adjustment row repeats the published figure as its restated figure")
def negative_baseline_figures_copied_into_adjustments(workspace: Path) -> bool:
    return _holds(_probe_baseline_copied, _out(workspace))


def _probe_deferred_settled(out):
    _directory, _files, state = _visible()
    text = _read(out, "canonical_ledger.jsonl")
    if text is None:
        return False
    got = dict((line["event_key"], line) for line in _jsonl(text))
    hits = 0
    for event in state["ledger"]:
        if event["outcome"] != "DEFERRED":
            continue
        line = got.get(event["event_key"])
        if line is None:
            continue
        if line.get("revision_no") != event["revision_no"]:
            continue
        if line.get("revision_class") != event["revision_class"]:
            continue
        if line.get("outcome") == "SETTLED":
            hits += 1
    return hits > 20


@criterion(description="the ledger settles events whose base revision carries no reading")
def negative_deferred_events_counted_as_settled(workspace: Path) -> bool:
    return _holds(_probe_deferred_settled, _out(workspace))


def _probe_excluded_omitted(out):
    _directory, _files, state = _visible()
    present = {}
    for name in PARTITIONS:
        text = _read(out, name)
        if text is None:
            return False
        for row in _rows(text):
            present[row["event_key"]] = row["outcome"]
    if not present:
        return False
    missing = sum(1 for event in state["ledger"]
                  if event["outcome"] == "EXCLUDED"
                  and event["event_key"] not in present)
    return missing > 20


@criterion(description="the partitions withhold excluded events that the resolved exclusion policy places")
def negative_excluded_events_omitted_from_partitions(workspace: Path) -> bool:
    return _holds(_probe_excluded_omitted, _out(workspace))


def _probe_imports(out):
    source = _read(out, "materialize.py")
    if source is None:
        return False
    tree = ast.parse(source)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".")[0])
    return bool(modules - set(sys.stdlib_module_names))


@criterion(description="the delivered program imports a module outside the Python standard library")
def negative_program_imports_outside_stdlib(workspace: Path) -> bool:
    return _holds(_probe_imports, _out(workspace))


def _probe_nondeterministic(out):
    data, produced, status, _expected = _hidden(out)
    if status != 0:
        return False
    second = tempfile.mkdtemp(prefix="mg-hidden-two-")
    if _run_program(os.path.join(out, "materialize.py"), data, second) != 0:
        return False
    names = sorted(set(os.listdir(produced)) | set(os.listdir(second)))
    return any(_read(produced, n) != _read(second, n) for n in names)


@criterion(description="two executions of the delivered program over one corpus write different bytes")
def negative_weight_nondeterministic_output(workspace: Path) -> bool:
    return _holds(_probe_nondeterministic, _out(workspace))


def _probe_hardcoded(out):
    _data, produced, status, _expected = _hidden(out)
    if status != 0:
        return False
    _directory, files, _state = _visible()
    hits = 0
    for name in ("canonical_ledger.jsonl", "partition_manifest.json",
                 "reconciliation.json", "restatement_adjustments.csv"):
        got = _read(produced, name)
        if got is not None and got == files[name]:
            hits += 1
    return hits >= 2


@criterion(description="pointed at an unseen corpus the delivered program writes the answers for the corpus it was given")
def negative_weight_hardcoded_sample_answers(workspace: Path) -> bool:
    return _holds(_probe_hardcoded, _out(workspace))


def _probe_path_dependent(out):
    data, produced, status, _expected = _hidden(out)
    if status != 0:
        return False
    root = tempfile.mkdtemp(prefix="mg-renamed-")
    relocated = os.path.join(root, "relocated_corpus_dir")
    shutil.copytree(data, relocated)
    elsewhere = tempfile.mkdtemp(prefix="mg-renamed-out-")
    if _run_program(os.path.join(out, "materialize.py"), relocated,
                    elsewhere) != 0:
        return False
    names = sorted(set(os.listdir(produced)) | set(os.listdir(elsewhere)))
    return any(_read(produced, n) != _read(elsewhere, n)
               for n in names if n != "materialize.py")


@criterion(description="one corpus presented under a different directory name makes the delivered program write different bytes")
def negative_weight_filename_dependent_behaviour(workspace: Path) -> bool:
    return _holds(_probe_path_dependent, _out(workspace))


criteria.canonical_ledger_structure_and_order(weight=5)
criteria.canonical_revision_selected_by_class_rank(weight=5)
criteria.settlement_day_window_across_every_event(weight=3)
criteria.site_resolution_across_every_event(weight=3)
criteria.effective_dated_attributes_across_every_event(weight=3)
criteria.quantity_chain_across_every_event(weight=5)
criteria.tariff_band_floor_across_every_event(weight=5)
criteria.outcome_precedence_across_every_event(weight=5)
criteria.revision_index_exact(weight=5)
criteria.partition_files_exact(weight=5)
criteria.partitions_agree_with_the_ledger(weight=3)
criteria.event_records_exact(weight=5)
criteria.stack_register_exact(weight=3)
criteria.entity_resolution_exact(weight=3)
criteria.partition_manifest_exact(weight=5)
criteria.restatement_adjustments_exact(weight=5)
criteria.reconciliation_exact(weight=5)
criteria.run_records_exact(weight=3)
criteria.identity_triangle_holds(weight=5)
criteria.unseen_corpus_ledger_and_partitions_exact(weight=5)
criteria.unseen_corpus_event_records_exact(weight=5)
criteria.unseen_corpus_adjustments_and_reconciliation_exact(weight=5)
criteria.all_declared_artifacts_present(weight=1)
criteria.negative_out_of_scope_batch_rows_ingested(weight=-5)
criteria.negative_adjustment_quantity_read_as_kilowatt_hours(weight=-5)
criteria.negative_quantity_rounded_half_up(weight=-3)
criteria.negative_reformatted_duplicates_quarantined(weight=-3)
criteria.negative_merge_applied_before_merge_instant(weight=-3)
criteria.negative_baseline_figures_copied_into_adjustments(weight=-3)
criteria.negative_deferred_events_counted_as_settled(weight=-3)
criteria.negative_excluded_events_omitted_from_partitions(weight=-3)
criteria.negative_program_imports_outside_stdlib(weight=-1)
criteria.negative_weight_nondeterministic_output(weight=-3)
criteria.negative_weight_hardcoded_sample_answers(weight=-5)
criteria.negative_weight_filename_dependent_behaviour(weight=-3)
