#!/usr/bin/env python3
"""Derive the assessment statements of a billing batch under the Vellmouth
Consolidated Municipal Utility Tariff Code 2026.

Usage: python3 derive_report.py <DATA_DIR> <OUT_DIR>

Every rate, allowance, factor, limit, priority, period, designation, date and
method is read out of <DATA_DIR>/tariff_code.md: the original provisions read
with the corrections of Division 15-2, the provisions outside Part 15 that
displace printed values, the amendments of Division 15-1 in the order of the
days on which they were made, and the Binding Rulings of Part 16 (section
1-006).  No figure of the Code is written into this program.
"""

import csv
import json
import os
import re
import sys
from datetime import date, timedelta
from fractions import Fraction

# --------------------------------------------------------------------------
# Division 1-2: rules of computation
# --------------------------------------------------------------------------

DAY = timedelta(days=1)
OPEN = date(9999, 12, 31)


def r_even(x):
    """Round a Fraction of cents to the nearest cent, ties to even (1-081(1))."""
    f = x.numerator // x.denominator
    rem = x - f
    if rem * 2 < 1:
        return f
    if rem * 2 > 1:
        return f + 1
    return f if f % 2 == 0 else f + 1


def r_up(x):
    """Round a Fraction of cents half up (1-081(2))."""
    f = x.numerator // x.denominator
    rem = x - f
    return f + 1 if rem * 2 >= 1 else f


MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}

WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
         "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
         "eleven": 11, "twelve": 12, "fourteen": 14, "twenty-one": 21,
         "twenty-eight": 28, "thirty": 30, "forty-two": 42, "sixty": 60,
         "ninety": 90}

ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4}

DATE_RE = re.compile(r"^(\d{1,2}) (" + "|".join(MONTHS) + r") (\d{4})$")
DATE_IN = re.compile(r"\b(\d{1,2}) (" + "|".join(MONTHS) + r") (\d{4})\b")


def parse_date(text):
    m = DATE_RE.match(text.strip())
    return date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))


def dollars(lit):
    """A money literal such as '$2.3070' as an exact Fraction of dollars."""
    return Fraction(lit.replace("$", "").replace(",", ""))


def rate_units(lit):
    """A rate stated in dollars to four decimal places, in units of $0.0001."""
    return int(dollars(lit) * 10000)


def cents(lit):
    return int(dollars(lit) * 100)


def ppm(lit):
    """A percentage written to four decimal places, in parts per million."""
    return int(Fraction(lit) * 10000)


# --------------------------------------------------------------------------
# Reading the Code
# --------------------------------------------------------------------------

ROMANS = {"i", "ii", "iii", "iv"}
LABEL_RE = re.compile(r"^\(([0-9]+|[a-z]+)\)\s")


class Section:
    def __init__(self, number, heading, division):
        self.number = number
        self.heading = heading
        self.division = division
        self.blocks = {}
        self.order = []
        self.lines = []

    def text(self, path):
        return self.blocks.get(path)


def _sortkey(num):
    a, b = num.split("-")
    return (int(a), int(b))


class Code:
    """The consolidated text, addressable by section and paragraph."""

    def __init__(self, raw):
        self.sections = {}
        division = None
        cur = None
        state = {"num": None, "alpha": None, "last": None}
        for line in raw.split("\n"):
            s = line.strip()
            m = re.match(r"^#### Division (\S+)\.", s)
            if m:
                division = m.group(1)
                cur = None
                continue
            if s.startswith("## Part "):
                cur = None
                continue
            m = re.match(r"^### Section (\S+)\. (.*)$", s)
            if m:
                cur = Section(m.group(1), m.group(2), division)
                self.sections[cur.number] = cur
                state = {"num": None, "alpha": None, "last": None}
                continue
            if cur is None or not s:
                continue
            cur.lines.append(s)
            m = LABEL_RE.match(s)
            if not m:
                continue
            lab = m.group(1)
            if lab.isdigit():
                kind = "num"
            elif lab in ROMANS and (lab != "i" or state["last"] == "alpha"):
                kind = "roman"
            elif len(lab) == 1 and lab.isalpha():
                kind = "alpha"
            else:
                continue
            if kind == "num":
                state["num"], state["alpha"] = lab, None
                path = (lab,)
            elif kind == "alpha":
                state["alpha"] = lab
                path = (state["num"], lab) if state["num"] else (lab,)
            else:
                base = (state["num"], state["alpha"]) if state["num"] \
                    else (state["alpha"],)
                path = base + (lab,)
            state["last"] = kind
            cur.blocks[path] = s
            cur.order.append(path)

    def division(self, name):
        return [self.sections[n] for n in sorted(self.sections, key=_sortkey)
                if self.sections[n].division == name]

    def part(self, p):
        return [self.sections[n] for n in sorted(self.sections, key=_sortkey)
                if n.split("-")[0] == p]


REF_RE = re.compile(r"^(\d+-\d+)((?:\([0-9a-z]+\))*)$")


def parse_ref(token):
    token = token.rstrip(".,;")
    m = REF_RE.match(token)
    if not m:
        return None
    return m.group(1), tuple(re.findall(r"\(([0-9a-z]+)\)", m.group(2)))


# --------------------------------------------------------------------------
# Division 15-2: corrections, read into the text they correct (1-006(2))
# --------------------------------------------------------------------------

CORR_RE = re.compile(r"^\(\d+\) In section (\S+?), for '(.*?)' read '(.*?)'\.$")
CORR_HEAD_RE = re.compile(r"^\(\d+\) In the heading to section ")


def apply_corrections(code):
    """Rewrite each corrected paragraph and note which section corrects it."""
    corr = {}
    for sec in code.division("15-2"):
        for path in sec.order:
            line = sec.blocks[path]
            if CORR_HEAD_RE.match(line):
                continue
            m = CORR_RE.match(line)
            if not m:
                continue
            ref = parse_ref(m.group(1))
            old, new = m.group(2), m.group(3)
            target = code.sections[ref[0]]
            text = target.blocks[ref[1]]
            if old not in text:
                raise ValueError("correction %s does not match %s"
                                 % (sec.number, m.group(1)))
            target.blocks[ref[1]] = text.replace(old, new, 1)
            if not DATE_RE.match(new):
                corr[(ref[0], ref[1], new)] = sec.number
    return corr


# --------------------------------------------------------------------------
# Timelines of values
# --------------------------------------------------------------------------

class TL:
    def __init__(self, start, end, value, auth):
        self.segs = [(start, end, value, auth)]

    def set(self, s, e, value, auth):
        out = []
        for (a, b, v, au) in self.segs:
            if b < s or a > e:
                out.append((a, b, v, au))
                continue
            if a < s:
                out.append((a, s - DAY, v, au))
            if b > e:
                out.append((e + DAY, b, v, au))
        out.append((s, e, value, auth))
        out.sort(key=lambda t: t[0])
        self.segs = out

    def at(self, d):
        for (a, b, v, au) in self.segs:
            if a <= d <= b:
                return v
        raise KeyError(d)

    def merged(self):
        out = []
        for (a, b, v, au) in sorted(self.segs, key=lambda t: t[0]):
            if out and out[-1][2] == v and out[-1][3] == au and \
                    out[-1][1] + DAY == a:
                out[-1] = (out[-1][0], b, v, au)
            else:
                out.append((a, b, v, au))
        return out

    def periods(self, key):
        return [{"from": a.isoformat(),
                 "to": None if b == OPEN else b.isoformat(),
                 key: v,
                 "authority": au} for (a, b, v, au) in self.merged()]

    def const(self):
        m = self.merged()
        if len(m) != 1:
            raise ValueError("value is not constant for the tariff year")
        return m[0][2], m[0][3]


class Slot:
    """A value printed in a provision, with its timeline and its text."""

    def __init__(self, code, corr, sec, path, parser, start, end,
                 repealed=None):
        self.sec = sec
        self.path = path
        self.parser = parser
        self.end = end
        self.repealed = repealed
        self.text = code.sections[sec].text(path)
        if self.text is None:
            value, lit = repealed, None
        else:
            value, lit = parser(self.text)
        auth = corr.get((sec, path, lit), sec) if lit else sec
        self.tl = TL(start, end, value, auth)


# --------------------------------------------------------------------------
# Parsers for the printed values
# --------------------------------------------------------------------------

MONEY = re.compile(r"\$[\d,]+\.\d+")
PCT = re.compile(r"([\d.]+) per cent")


def p_rate(text):
    lit = MONEY.search(text).group(0)
    return rate_units(lit), lit


def p_cents(text):
    lit = MONEY.search(text).group(0)
    return cents(lit), lit


def p_pct_int(text):
    m = PCT.search(text)
    return int(m.group(1)), m.group(0)


def p_ppm(text):
    m = PCT.search(text)
    return ppm(m.group(1)), m.group(0)


def p_band(text):
    m = re.search(r"Band ([ABC])", text)
    return m.group(1), m.group(0)


def p_exempt(text):
    return "not exempt" not in text, None


def p_drought(text):
    return "not designated" not in text, None


def p_region(text):
    m = re.search(r"part of the (North|South|West|East) region", text)
    return m.group(1), m.group(0)


def p_litres(which):
    def f(text):
        hits = re.findall(r"([\d,]+) litres", text)
        lit = hits[which]
        return int(lit.replace(",", "")), lit + " litres"
    return f


def p_priority(text):
    m = re.search(r"priority (\d+)", text)
    return int(m.group(1)), m.group(0)


def p_days_word(text):
    m = re.search(r"is (\w+(?:-\w+)?) days", text)
    return WORDS[m.group(1)], m.group(1) + " days"


def p_carry(text):
    if "may not be carried forward" in text:
        return 0, None
    m = re.search(r"carried forward for (\w+(?:-\w+)?) tariff years", text)
    return WORDS[m.group(1)], m.group(1) + " tariff years"


CAP_BASES = {"Volumetric Charges": "volumetric",
             "Water Supply Charges": "water",
             "Service Charges": "service",
             "Supply Total": "supply",
             "Gross Charge": "gross"}


def p_cap(text):
    m = re.search(r"exceed \$([\d,]+\.\d\d)", text)
    if m:
        lit = "$" + m.group(1)
        return ("fixed", cents(lit)), lit
    m = re.search(r"exceed (\d+) per cent of the account's ([A-Za-z ]+?)\.",
                  text)
    return (CAP_BASES[m.group(2)], int(m.group(1))), m.group(1) + " per cent"


def p_excluded(text):
    if "No holder form is excluded" in text:
        return [], None
    return re.findall(r"holder form of the account is (\w+)", text), None


AMOUNT_BASES = [("of the expenditure claimed", "expenditure"),
                ("of the leak value of each accepted leak claim", "leak"),
                ("of the daily service charges of the account's Large Meters",
                 "large_meters"),
                ("of the account's Service Charges", "service"),
                ("of the account's Water Supply Charges", "water"),
                ("of the account's Volumetric Charges", "volumetric"),
                ("of the account's Supply Total", "supply"),
                ("of the account's Gross Charge", "gross")]


def p_amount(text):
    m = PCT.search(text)
    for needle, name in AMOUNT_BASES:
        if needle in text:
            return (int(m.group(1)), name), m.group(0)
    raise ValueError("unknown rebate base: " + text)


CARDS = [("a pensioner concession card", "pensioner"),
         ("a health care card", "health"),
         ("a veteran concession card", "veteran")]


def p_eligibility(text):
    classes = [c for c in ("residential", "commercial", "public")
               if c + " account" in text]
    found = []
    for needle, name in CARDS:
        pos = text.find(needle)
        if pos >= 0:
            found.append((pos, name))
    rule = {"classes": classes,
            "cards": [n for _, n in sorted(found)],
            "community": "community organisation" in text,
            "drought": "drought property" in text,
            "large_meter": "Large Meter" in text}
    return rule, None


# --------------------------------------------------------------------------
# The Code as a set of values in force
# --------------------------------------------------------------------------

class Tariff:
    def __init__(self, raw):
        self.code = Code(raw)
        self.corr = apply_corrections(self.code)
        self.year_start, self.year_end = self._tariff_year()
        self.quarters = self._quarters()
        self.holidays = self._holidays()
        self.slots = {}
        self.by_ref = {}
        self._build_classes()
        self._build_zones()
        self._build_general()
        self._build_rebates()
        self._displacements()
        self._amendments()
        self.rulings = self._rulings()
        self.instalment_dates = self._instalment_dates()

    # -- helpers ---------------------------------------------------------
    def _slot(self, key, sec, path, parser, end=None, repealed=None):
        s = Slot(self.code, self.corr, sec, path, parser,
                 self.year_start, end or self.year_end, repealed)
        self.slots[key] = s
        self.by_ref[(sec, path)] = s
        return s

    def _tariff_year(self):
        d = DATE_IN.findall(self.code.sections["1-224"].text(("1",)))
        return (date(int(d[0][2]), MONTHS[d[0][1]], int(d[0][0])),
                date(int(d[1][2]), MONTHS[d[1][1]], int(d[1][0])))

    def _quarters(self):
        t = self.code.sections["1-092"].text(("1",))
        out = {}
        y = self.year_start.year
        for ordn, m1, m2 in re.findall(
                r"(first|second|third|fourth) quarter (?:of the tariff year )?"
                r"is (\w+) to (\w+)", t):
            em = MONTHS[m2]
            end = date(y + 1, 1, 1) - DAY if em == 12 else date(y, em + 1, 1) - DAY
            out[ORDINALS[ordn]] = (date(y, MONTHS[m1], 1), end)
        return out

    def _holidays(self):
        t = self.code.sections["1-090"].text(("1",))
        return {date(int(y), MONTHS[m], int(d))
                for d, m, y in DATE_IN.findall(t)}

    def is_business_day(self, d):
        return d.weekday() < 5 and d not in self.holidays

    def next_business_day(self, d):
        while not self.is_business_day(d):
            d += DAY
        return d

    # -- Schedule 2 ------------------------------------------------------
    def _build_classes(self):
        self.classes = []
        for sec in self.code.part("2"):
            m = re.match(r"Class (TC-\d+):", sec.heading)
            if not m or sec.division != "2-2":
                continue
            tc = m.group(1)
            self.classes.append(tc)
            for i, r in enumerate(("i", "ii", "iii"), start=1):
                self._slot(("class", tc, "block", i), sec.number, ("d", r),
                           p_rate)
            self._slot(("class", tc, "exempt"), sec.number, ("e",), p_exempt,
                       repealed=False)
            self._slot(("class", tc, "band"), sec.number, ("f",), p_band)
            self._slot(("class", tc, "df"), sec.number, ("g",), p_pct_int)

    # -- Schedule 3 ------------------------------------------------------
    def _build_zones(self):
        self.zones = []
        for sec in self.code.part("3"):
            m = re.match(r"Zone (Z-\d+):", sec.heading)
            if not m or sec.division != "3-2":
                continue
            z = m.group(1)
            self.zones.append(z)
            self._slot(("zone", z, "region"), sec.number, ("b",), p_region)
            self._slot(("zone", z, "drought"), sec.number, ("c",), p_drought)
            self._slot(("zone", z, "ww"), sec.number, ("d",), p_rate)
            self._slot(("zone", z, "sw"), sec.number, ("e",), p_rate)

    # -- Parts 4 to 12 ---------------------------------------------------
    def _build_general(self):
        for band, para in (("A", "a"), ("B", "b"), ("C", "c")):
            self._slot(("band", band, "b1"), "4-020", ("2", para), p_litres(0))
            self._slot(("band", band, "b2u"), "4-020", ("2", para), p_litres(1))
        self.sizes = []
        sec = self.code.sections["6-020"]
        for path in sec.order:
            m = re.match(r"\([a-z]\) for a meter of (\d+) mm, \$",
                         sec.blocks[path])
            if m and path[0] == "2":
                size = int(m.group(1))
                self.sizes.append(size)
                self._slot(("svc", size), "6-020", path, p_rate)
        self.regions = []
        sec = self.code.sections["7-010"]
        for path in sec.order:
            m = re.match(r"\([a-z]\) for the (\w+) region, ",
                         sec.blocks[path])
            if m and path[0] == "1":
                self.regions.append(m.group(1))
                self._slot(("surcharge", m.group(1)), "7-010", path, p_ppm)
        self._slot(("drought_supp",), "7-020", ("1",), p_ppm)
        self._slot(("levy",), "5-210", ("2",), p_ppm)
        self._slot(("tw", "volume"), "5-110", ("2", "a"), p_rate)
        self._slot(("tw", "load"), "5-110", ("2", "b"), p_rate)
        self._slot(("global_cap",), "9-002", ("1",), p_pct_int)
        sec = self.code.sections["11-010"]
        for path in sec.order:
            m = re.match(r"\([a-z]\) for a (\w+) account, \$",
                         sec.blocks[path])
            if m and path[0] == "1":
                self._slot(("minimum", m.group(1)), "11-010", path, p_cents)
        self._slot(("grace",), "12-030", ("2",), p_days_word)
        self._slot(("interest",), "12-040", ("1",), p_ppm, end=OPEN)

    # -- Part 9 and Division 15-3 ----------------------------------------
    def _build_rebates(self):
        self.rebates = {}
        for num in sorted(self.code.sections, key=_sortkey):
            sec = self.code.sections[num]
            t = sec.text(("1",))
            if not t:
                continue
            m = re.search(r"identified by rebate code (RB-\d+)", t)
            if not m:
                continue
            code = m.group(1)
            self.rebates[code] = {"section": num}
            self._slot(("rebate", code, "priority"), num, ("2",), p_priority)
            self._slot(("rebate", code, "eligibility"), num, ("3",),
                       p_eligibility)
            self._slot(("rebate", code, "amount"), num, ("4",), p_amount)
            self._slot(("rebate", code, "cap"), num, ("5",), p_cap,
                       repealed=(None, None))
            self._slot(("rebate", code, "carry"), num, ("6",), p_carry)
            self._slot(("rebate", code, "excluded"), num, ("7",), p_excluded,
                       repealed=[])

    # -- 1-006(3): provisions outside Part 15 that displace a value -------
    DISPLACERS = [
        (re.compile(r"the percentage stated in section (\S+?) is taken to be "
                    r"([\d.]+) per cent for the tariff year"), "pct"),
        (re.compile(r"the daily service charge stated in section (\S+?) for a "
                    r"meter of \d+ mm has effect for the tariff year \d+ as if "
                    r"it were (\$[\d,]+\.\d+)"), "rate"),
        (re.compile(r"section (4-020), for the tariff year \d+ the block (\d) "
                    r"allowance for Band ([ABC]) is ([\d,]+) litres per day"),
         "allowance"),
    ]

    def _displacements(self):
        for num in sorted(self.code.sections, key=_sortkey):
            sec = self.code.sections[num]
            if num.split("-")[0] in ("15", "16"):
                continue
            for path in sec.order:
                line = sec.blocks[path]
                for rx, kind in self.DISPLACERS:
                    m = rx.search(line)
                    if not m:
                        continue
                    if kind == "pct":
                        slot = self.by_ref[parse_ref(m.group(1))]
                        lit = m.group(2) + " per cent"
                        value = ppm(m.group(2))
                    elif kind == "rate":
                        slot = self.by_ref[parse_ref(m.group(1))]
                        lit = m.group(2)
                        value = rate_units(lit)
                    else:
                        slot = self.slots[("band", m.group(3),
                                           "b1" if m.group(2) == "1"
                                           else "b2u")]
                        lit = m.group(4) + " litres"
                        value = int(m.group(4).replace(",", ""))
                    slot.tl.set(self.year_start, slot.end, value,
                                self.corr.get((num, path, lit), num))

    # -- Division 15-1: amendments ---------------------------------------
    SUBST = re.compile(r"[Ii]n section (\S+?), for '(.*?)' substitute '(.*?)'\.")
    OMIT = re.compile(r"In section (\S+?), omit '(.*?)'\.")
    INSERT = re.compile(r"In section (\S+?), after '(.*?)' insert '(.*?)'\.")
    REPEAL = re.compile(r"(?:Paragraph|Subsection) \(([0-9a-z]+)\) of section "
                        r"(\d+-\d+) is repealed\.")
    DIRECT = re.compile(r"under section ([\d-]+(?:\([0-9a-z]+\))*)")
    SUBSTANTIVE = re.compile(r"(\$[\d,]+\.\d+|[\d.]+ per cent|Band [ABC]|"
                             r"priority \d+|tariff years|litres|is repealed|"
                             r"exempt|concession card|'not '|' not')")

    def _period(self, text, slot):
        end = slot.end
        m = re.search(r"for the period beginning on (" + DATE_IN.pattern + ")",
                      text)
        if m:
            return parse_date(m.group(1)), end
        m = re.search(r"For the period from (" + DATE_IN.pattern + r") to ("
                      + DATE_IN.pattern + r")", text)
        if m:
            return parse_date(m.group(1)), parse_date(m.group(5))
        m = re.search(r"For the (first|second|third|fourth) quarter of the "
                      r"tariff year only", text)
        if m:
            return self.quarters[ORDINALS[m.group(1)]]
        m = re.search(r"For the (first|second|third|fourth) and later quarters "
                      r"of the tariff year", text)
        if m:
            return self.quarters[ORDINALS[m.group(1)]][0], end
        m = re.search(r"With effect from (" + DATE_IN.pattern + r"),", text)
        if m:
            return parse_date(m.group(1)), end
        return self.year_start, end

    def _amendments(self):
        events = []
        for sec in self.code.division("15-1"):
            made = parse_date(re.search(r"made on (" + DATE_IN.pattern + r")\.",
                                        sec.text(("1",))).group(1))
            for path in sec.order:
                if path == ("1",):
                    continue
                events.append((made, _sortkey(sec.number), int(path[0]),
                               sec, path))
        for made, _k, _s, sec, path in sorted(events, key=lambda e: e[:3]):
            self._apply_amendment(sec, path)

    def _apply_amendment(self, sec, path):
        text = sec.blocks[path]
        num = sec.number

        def unaffected():
            """A provision this Part amends that fixes no value in a statement."""
            if self.SUBSTANTIVE.search(text):
                raise ValueError("unhandled amendment %s%s: %s"
                                 % (num, path, text))

        m = self.REPEAL.search(text)
        if m:
            slot = self.by_ref.get((m.group(2), (m.group(1),)))
            if slot is None:
                return unaffected()
            slot.text = None
            s, e = self._period(text, slot)
            slot.tl.set(s, e, slot.repealed, num)
            return

        m = self.SUBST.search(text)
        if m:
            slot = self.by_ref.get(parse_ref(m.group(1)))
            if slot is None:
                return unaffected()
            old, new = m.group(2), m.group(3)
            if old not in slot.text:
                raise ValueError("amendment %s%s does not match %s"
                                 % (num, path, m.group(1)))
            slot.text = slot.text.replace(old, new, 1)
            value, _lit = slot.parser(slot.text)
            s, e = self._period(text, slot)
            slot.tl.set(s, e, value, self.corr.get((num, path, new), num))
            return

        for rx in (self.OMIT, self.INSERT):
            m = rx.search(text)
            if not m:
                continue
            slot = self.by_ref.get(parse_ref(m.group(1)))
            if slot is None:
                return unaffected()
            if rx is self.OMIT:
                if m.group(2) not in slot.text:
                    raise ValueError("omission %s%s does not match" % (num, path))
                slot.text = slot.text.replace(m.group(2), "", 1)
            else:
                anchor = m.group(2)
                if anchor not in slot.text:
                    raise ValueError("insertion %s%s does not match" % (num, path))
                slot.text = slot.text.replace(anchor, anchor + m.group(3), 1)
            value, _lit = slot.parser(slot.text)
            s, e = self._period(text, slot)
            slot.tl.set(s, e, value, num)
            return

        m = self.DIRECT.search(text)
        if m:
            slot = self.by_ref.get(parse_ref(m.group(1)))
            if slot is not None:
                mv = MONEY.search(text)
                if mv:
                    lit = mv.group(0)
                    value = rate_units(lit) if slot.parser is p_rate \
                        else cents(lit)
                else:
                    mp = PCT.search(text)
                    lit = mp.group(0)
                    value = ppm(mp.group(1))
                s, e = self._period(text, slot)
                slot.tl.set(s, e, value, self.corr.get((num, path, lit), num))
                return

        unaffected()

    # -- Part 16: only a Binding Ruling has legal effect (1-004(4)) -------
    def _rulings(self):
        """The Binding Rulings, taken from the designation each document
        states in its first line, the headings having no legal effect."""
        out = {}
        for num in sorted(self.code.sections, key=_sortkey):
            sec = self.code.sections[num]
            for line in sec.lines:
                m = re.match(r"Designation: (.+?)\.$", line)
                if m:
                    if m.group(1) == "Binding Ruling":
                        out[num] = " ".join(sec.blocks[p] for p in sec.order)
                    break
        return out

    # -- Part 12 ---------------------------------------------------------
    def _instalment_dates(self):
        t = self.code.sections["12-010"].text(("3",))
        days = [date(int(y), MONTHS[m], int(d))
                for d, m, y in DATE_IN.findall(t)]
        move = "moved to the next business day" in t
        return {"Q%d" % i: (self.next_business_day(d) if move else d)
                for i, d in enumerate(days, start=1)}

    # -- accessors -------------------------------------------------------
    def v(self, key, day):
        return self.slots[key].tl.at(day)

    def c(self, key):
        return self.slots[key].tl.const()


# --------------------------------------------------------------------------
# The registers
# --------------------------------------------------------------------------

def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def d_or_none(s):
    return date.fromisoformat(s) if s else None


class Batch:
    def __init__(self, data_dir):
        with open(os.path.join(data_dir, "batch.json"), encoding="utf-8") as fh:
            self.manifest = json.load(fh)
        self.batch_id = self.manifest["batch_id"]
        self.assessment_date = date.fromisoformat(
            self.manifest["assessment_date"])
        self.accounts = read_csv(os.path.join(data_dir, "accounts.csv"))
        self.properties = read_csv(os.path.join(data_dir, "properties.csv"))
        self.meters = read_csv(os.path.join(data_dir, "meters.csv"))
        self.reads = read_csv(os.path.join(data_dir, "meter_reads.csv"))
        self.trade_waste = read_csv(os.path.join(data_dir, "trade_waste.csv"))
        self.claims = read_csv(os.path.join(data_dir, "concession_claims.csv"))
        self.leaks = read_csv(os.path.join(data_dir, "leak_claims.csv"))
        self.carry = read_csv(os.path.join(data_dir, "carryforwards.csv"))
        self.payments = read_csv(os.path.join(data_dir, "payments.csv"))
        self.file_count = sum(1 for n in os.listdir(data_dir)
                              if os.path.isfile(os.path.join(data_dir, n)))


# --------------------------------------------------------------------------
# The assessment
# --------------------------------------------------------------------------

TOTAL_KEYS = ["water_supply_cents", "wastewater_cents", "service_charges_cents",
              "surcharge_cents", "catchment_levy_cents", "trade_waste_cents",
              "gross_charge_cents", "rebates_total_cents",
              "minimum_topup_cents", "net_charge_cents", "payments_cents",
              "interest_cents", "balance_cents"]


class Assessment:
    def __init__(self, tariff, batch):
        self.t = tariff
        self.b = batch
        self.issues = []
        self.y0 = tariff.year_start
        self.y1 = tariff.year_end
        self.large_size = self.large_meter_size()
        self._index()
        self._windows()
        self._intervals()
        self._trade_waste()
        self._claims()
        self._leaks()
        self._carry()
        self._payments()
        self.results = [self._account(a) for a in
                        sorted(self.b.accounts, key=lambda a: a["account_id"])]

    # -- indexing --------------------------------------------------------
    def _index(self):
        self.acc = {a["account_id"]: a for a in self.b.accounts}
        self.prop = {p["property_id"]: p for p in self.b.properties}
        self.props_of = {}
        for p in self.b.properties:
            self.props_of.setdefault(p["account_id"], []).append(p)
        for k in self.props_of:
            self.props_of[k].sort(key=lambda p: p["property_id"])
        self.meters_of = {}
        for m in self.b.meters:
            self.meters_of.setdefault(m["property_id"], []).append(m)
        for k in self.meters_of:
            self.meters_of[k].sort(key=lambda m: m["meter_id"])
        self.reads_of = {}
        for r in self.b.reads:
            self.reads_of.setdefault(r["meter_id"], []).append(r)

    # -- 1-230: supply windows -------------------------------------------
    def _windows(self):
        self.win_a, self.win_p, self.win_m = {}, {}, {}
        for a in self.b.accounts:
            s = max(self.y0, date.fromisoformat(a["opened_on"]))
            e = min(self.y1, d_or_none(a["closed_on"]) or self.y1)
            self.win_a[a["account_id"]] = (s, e)
        for p in self.b.properties:
            s0, e0 = self.win_a[p["account_id"]]
            s = max(s0, date.fromisoformat(p["connected_on"]))
            e = min(e0, d_or_none(p["disconnected_on"]) or e0)
            self.win_p[p["property_id"]] = (s, e)
        for m in self.b.meters:
            s0, e0 = self.win_p[m["property_id"]]
            s = max(s0, date.fromisoformat(m["installed_on"]))
            e = min(e0, d_or_none(m["removed_on"]) or e0)
            self.win_m[m["meter_id"]] = (s, e)

    @staticmethod
    def days(win):
        s, e = win
        return (e - s).days + 1 if e >= s else 0

    # -- Part 4 and section 5-010 ----------------------------------------
    def _intervals(self):
        self.intervals_of = {}
        for m in self.b.meters:
            mid = m["meter_id"]
            s, e = self.win_m[mid]
            empty = e < s
            kept = []
            for r in sorted(self.reads_of.get(mid, []),
                            key=lambda r: (r["read_on"], r["reading_litres"])):
                d = date.fromisoformat(r["read_on"])
                if empty or not (s - DAY <= d <= e):
                    self.issues.append(
                        "%s: reading of %s outside the meter's supply window "
                        "disregarded" % (mid, r["read_on"]))
                    continue
                kept.append((d, int(r["reading_litres"])))
            out = []
            for i in range(1, len(kept)):
                d0, v0 = kept[i - 1]
                d1, v1 = kept[i]
                if v1 < v0:
                    self.issues.append(
                        "%s: reading of %s lower than the preceding reading; "
                        "consumption nil" % (mid, d1.isoformat()))
                    litres = 0
                else:
                    litres = v1 - v0
                out.append({"from": d0 + DAY, "to": d1, "litres": litres})
            self.intervals_of[mid] = out

    def interval_charges(self, prop, iv):
        t = self.t
        tc = prop["tariff_class"]
        zone = prop["zone"]
        band = t.c(("class", tc, "band"))[0]
        a1 = t.c(("band", band, "b1"))[0]
        a2 = t.c(("band", band, "b2u"))[0]
        df = t.c(("class", tc, "df"))[0]
        n = (iv["to"] - iv["from"]).days + 1
        per_day = Fraction(iv["litres"], n)
        b1 = min(per_day, Fraction(a1))
        b2 = min(max(per_day - a1, Fraction(0)), Fraction(a2 - a1))
        b3 = max(per_day - a2, Fraction(0))
        ww_day = per_day * df / 100
        water = Fraction(0)
        ww = Fraction(0)
        d = iv["from"]
        while d <= iv["to"]:
            for blk, vol in ((1, b1), (2, b2), (3, b3)):
                if vol:
                    water += vol * t.v(("class", tc, "block", blk), d) / 100000
            if ww_day:
                ww += ww_day * t.v(("zone", zone, "ww"), d) / 100000
            d += DAY
        return r_even(water), r_up(ww)

    # -- section 5-110 ---------------------------------------------------
    def _trade_waste(self):
        self.tw_of = {}
        for ret in sorted(self.b.trade_waste, key=lambda r: r["return_id"]):
            prop = self.prop[ret["property_id"]]
            acct = self.acc[prop["account_id"]]
            if acct["account_class"] != "commercial":
                self.issues.append(
                    "%s: trade waste return for a property of a non-commercial "
                    "account disregarded" % ret["return_id"])
                continue
            day = self.t.quarters[int(ret["quarter"][1])][0]
            vol = int(ret["discharge_litres"])
            bod = int(ret["bod_mg_per_l"])
            charge = Fraction(vol * self.t.v(("tw", "volume"), day), 100000) \
                + Fraction(vol * bod * self.t.v(("tw", "load"), day),
                           100000 * 1000000)
            self.tw_of.setdefault(ret["property_id"], []).append(r_even(charge))

    # -- Part 9 claims ---------------------------------------------------
    def _claims(self):
        self.claims_of = {}
        for cl in sorted(self.b.claims, key=lambda c: c["claim_id"]):
            aid = cl["account_id"]
            code = cl["rebate_code"]
            if code not in self.t.rebates:
                self.issues.append(
                    "%s: claim %s under %s disregarded: no such rebate"
                    % (aid, cl["claim_id"], code))
                continue
            if self.t.c(("rebate", code, "amount"))[0][1] != "expenditure":
                self.issues.append(
                    "%s: claim %s under %s disregarded: rebate arises without "
                    "claim" % (aid, cl["claim_id"], code))
                continue
            if not self.eligible(aid, code):
                self.issues.append(
                    "%s: claim %s under %s disregarded: account not eligible"
                    % (aid, cl["claim_id"], code))
                continue
            self.claims_of.setdefault((aid, code), []).append(
                int(cl["expenditure_cents"]))

    def _leaks(self):
        self.leaks_of = {}
        self.leak_code = None
        for code in sorted(self.t.rebates):
            if self.t.c(("rebate", code, "amount"))[0][1] == "leak":
                self.leak_code = code
        for lk in sorted(self.b.leaks, key=lambda l: l["leak_claim_id"]):
            prop = self.prop[lk["property_id"]]
            aid = prop["account_id"]
            rep = date.fromisoformat(lk["repaired_on"])
            if not (self.y0 <= rep <= self.y1):
                self.issues.append(
                    "%s: leak claim %s disregarded: repair date outside the "
                    "tariff year" % (aid, lk["leak_claim_id"]))
                continue
            if self.leak_code is None or not self.eligible(aid, self.leak_code):
                self.issues.append(
                    "%s: leak claim %s disregarded: account not eligible"
                    % (aid, lk["leak_claim_id"]))
                continue
            self.leaks_of.setdefault(aid, []).append((lk, prop, rep))

    def _carry(self):
        self.carry_of = {}
        for cf in sorted(self.b.carry,
                         key=lambda c: (c["account_id"], c["rebate_code"],
                                        c["origin_year"])):
            aid = cf["account_id"]
            code = cf["rebate_code"]
            known = code in self.t.rebates
            years = self.t.c(("rebate", code, "carry"))[0] if known else 0
            if not known or years == 0:
                self.issues.append(
                    "%s: carryforward %s/%s disregarded: not permitted"
                    % (aid, code, cf["origin_year"]))
                continue
            if self.y0.year - int(cf["origin_year"]) > years:
                self.issues.append(
                    "%s: carryforward %s/%s disregarded: expired"
                    % (aid, code, cf["origin_year"]))
                continue
            self.carry_of.setdefault(aid, []).append(
                (code, int(cf["origin_year"]), int(cf["remaining_cents"])))

    def _payments(self):
        self.pay_of = {}
        for p in self.b.payments:
            paid = date.fromisoformat(p["paid_on"])
            if paid > self.b.assessment_date:
                self.issues.append(
                    "%s: payment %s dated after the assessment date disregarded"
                    % (p["account_id"], p["payment_id"]))
                continue
            self.pay_of.setdefault(p["account_id"], []).append(
                (self.t.next_business_day(paid), p["payment_id"],
                 int(p["amount_cents"])))
        for k in self.pay_of:
            self.pay_of[k].sort()

    # -- eligibility -----------------------------------------------------
    def eligible(self, aid, code):
        acct = self.acc[aid]
        rule = self.t.c(("rebate", code, "eligibility"))[0]
        if acct["holder_form"] in self.t.c(("rebate", code, "excluded"))[0]:
            return False
        if rule["community"]:
            return acct["account_class"] == "public" or \
                acct["holder_form"] == "association"
        if rule["drought"]:
            return any(self.t.c(("zone", p["zone"], "drought"))[0]
                       for p in self.props_of.get(aid, []))
        if rule["large_meter"]:
            return bool(self.large_meters(aid))
        if rule["classes"] and acct["account_class"] not in rule["classes"]:
            return False
        if rule["cards"] and acct["concession_card"] not in rule["cards"]:
            return False
        return True

    def large_meter_size(self):
        """The size at or above which a meter is a Large Meter (1-231)."""
        t = self.t.code.sections["1-231"].text(("1",))
        return int(re.search(r"meter of (\d+) mm or more", t).group(1))

    def large_meters(self, aid):
        size = self.large_size
        out = []
        for p in self.props_of.get(aid, []):
            for m in self.meters_of.get(p["property_id"], []):
                if int(m["size_mm"]) >= size and \
                        self.days(self.win_m[m["meter_id"]]) > 0:
                    out.append(m)
        return out

    # -- 3-002, read with Binding Ruling BR 2026/1 ------------------------
    def billing_zone(self, aid, consumption_by_zone):
        if "16-012" in self.t.rulings and consumption_by_zone:
            best = max(consumption_by_zone.values())
            if best > 0:
                return min(z for z, v in consumption_by_zone.items()
                           if v == best)
        cands = [p for p in self.props_of.get(aid, [])
                 if self.days(self.win_p[p["property_id"]]) > 0]
        if not cands:
            cands = list(self.props_of.get(aid, []))
        cands.sort(key=lambda p: (p["connected_on"], p["property_id"]))
        return cands[0]["zone"]

    # -- one account ------------------------------------------------------
    def _account(self, acct):
        aid = acct["account_id"]
        t = self.t
        active_days = self.days(self.win_a[aid])

        ivs = []
        cons_zone = {}
        water_total = 0
        ww_total = 0
        levy_base = 0
        for p in self.props_of.get(aid, []):
            exempt = t.c(("class", p["tariff_class"], "exempt"))[0]
            for m in self.meters_of.get(p["property_id"], []):
                for iv in self.intervals_of[m["meter_id"]]:
                    w, ww = self.interval_charges(p, iv)
                    ivs.append({"meter_id": m["meter_id"],
                                "property_id": p["property_id"],
                                "from": iv["from"].isoformat(),
                                "to": iv["to"].isoformat(),
                                "days": (iv["to"] - iv["from"]).days + 1,
                                "litres": iv["litres"],
                                "water_cents": w,
                                "wastewater_cents": ww})
                    water_total += w
                    ww_total += ww
                    if not exempt:
                        levy_base += w
                    cons_zone[p["zone"]] = cons_zone.get(p["zone"], 0) + \
                        iv["litres"]
        ivs.sort(key=lambda r: (r["meter_id"], r["to"]))

        meters = []
        service_total = 0
        svc_by_meter = {}
        for p in self.props_of.get(aid, []):
            for m in self.meters_of.get(p["property_id"], []):
                win = self.win_m[m["meter_id"]]
                nd = self.days(win)
                charge = Fraction(0)
                d = win[0]
                for _ in range(nd):
                    charge += Fraction(t.v(("svc", int(m["size_mm"])), d), 100)
                    d += DAY
                c = r_even(charge)
                svc_by_meter[m["meter_id"]] = c
                service_total += c
                meters.append({"meter_id": m["meter_id"],
                               "property_id": p["property_id"],
                               "size_mm": int(m["size_mm"]),
                               "service_days": nd,
                               "service_cents": c})
        meters.sort(key=lambda r: (r["property_id"], r["meter_id"]))

        props = []
        storm_total = 0
        tw_total = 0
        for p in self.props_of.get(aid, []):
            nd = self.days(self.win_p[p["property_id"]])
            rate = t.c(("zone", p["zone"], "sw"))[0]
            storm = r_up(Fraction(int(p["land_area_m2"]) * rate * nd,
                                  100 * 365))
            tw = sum(self.tw_of.get(p["property_id"], []))
            storm_total += storm
            tw_total += tw
            props.append({"property_id": p["property_id"],
                          "zone": p["zone"],
                          "tariff_class": p["tariff_class"],
                          "supply_days": nd,
                          "stormwater_cents": storm,
                          "trade_waste_cents": tw})

        zone = self.billing_zone(aid, cons_zone)
        region = t.c(("zone", zone, "region"))[0]

        volumetric = water_total + ww_total
        service_charges = service_total + storm_total
        base = volumetric + service_charges
        rate_ppm = t.c(("surcharge", region))[0]
        if t.c(("zone", zone, "drought"))[0]:
            rate_ppm += t.c(("drought_supp",))[0]
        surcharge = r_even(Fraction(base * rate_ppm, 1000000))
        supply_total = base + surcharge
        levy = r_up(Fraction(levy_base * t.c(("levy",))[0], 1000000))
        gross = supply_total + levy + tw_total

        applied, carry_out, rebates_total = self._rebates(
            acct, gross, water_total, volumetric, service_charges,
            supply_total, svc_by_meter)

        min_annual = t.c(("minimum", acct["account_class"]))[0]
        if "16-019" in t.rulings:
            min_charge = r_up(Fraction(min_annual * active_days, 365))
        else:
            min_charge = min_annual
        after = gross - rebates_total
        topup = max(0, min_charge - after)
        net = after + topup

        instalments, payments_total, interest_total = \
            self._instalments(aid, net)

        return {
            "account_id": aid,
            "account_class": acct["account_class"],
            "holder_form": acct["holder_form"],
            "concession_card": acct["concession_card"],
            "active_days": active_days,
            "billing_zone": zone,
            "region": region,
            "meter_intervals": ivs,
            "meters": meters,
            "properties": props,
            "water_supply_cents": water_total,
            "wastewater_cents": ww_total,
            "volumetric_charges_cents": volumetric,
            "service_charges_cents": service_charges,
            "base_charges_cents": base,
            "surcharge_cents": surcharge,
            "supply_total_cents": supply_total,
            "catchment_levy_cents": levy,
            "trade_waste_cents": tw_total,
            "gross_charge_cents": gross,
            "rebates_applied": applied,
            "rebates_total_cents": rebates_total,
            "carryforward_out": carry_out,
            "minimum_charge_cents": min_charge,
            "minimum_topup_cents": topup,
            "net_charge_cents": net,
            "instalments": instalments,
            "payments_cents": payments_total,
            "interest_cents": interest_total,
            "balance_cents": net + interest_total - payments_total,
        }

    # -- Parts 9 and 10 ---------------------------------------------------
    def rebate_order(self):
        items = [(self.t.c(("rebate", c, "priority"))[0],
                  _sortkey(self.t.rebates[c]["section"]), c)
                 for c in self.t.rebates]
        items.sort()
        return [c for _p, _s, c in items]

    def _rebates(self, acct, gross, water, volumetric, service_charges,
                 supply_total, svc_by_meter):
        t = self.t
        aid = acct["account_id"]
        bases = {"gross": gross, "water": water, "volumetric": volumetric,
                 "service": service_charges, "supply": supply_total}
        global_left = r_even(Fraction(gross * t.c(("global_cap",))[0], 100))
        gross_left = gross
        applied = []
        carry_out = []
        carried = {}
        for code, origin, amount in self.carry_of.get(aid, []):
            carried.setdefault(code, []).append((origin, amount))
        for code in carried:
            carried[code].sort()
        total = 0
        current_first = "16-034" in t.rulings
        year = t.year_start.year
        for code in self.rebate_order():
            rate, basis = t.c(("rebate", code, "amount"))[0]
            cur = 0
            if self.eligible(aid, code):
                if basis == "expenditure":
                    exp = sum(self.claims_of.get((aid, code), []))
                    cur = r_even(Fraction(exp * rate, 100)) if exp else 0
                elif basis == "leak":
                    acc = 0
                    for lk, prop, rep in self.leaks_of.get(aid, []):
                        r3 = t.v(("class", prop["tariff_class"], "block", 3),
                                 rep)
                        value = Fraction(int(lk["leak_litres"]) * r3, 100000)
                        acc += r_even(value * rate / 100)
                    cur = acc
                elif basis == "large_meters":
                    s = sum(svc_by_meter[m["meter_id"]]
                            for m in self.large_meters(aid))
                    cur = r_even(Fraction(s * rate, 100)) if s else 0
                else:
                    cur = r_even(Fraction(bases[basis] * rate, 100))
            cap_basis, cap_amount = t.c(("rebate", code, "cap"))[0]
            if cap_basis is None:
                limit_left = None
            elif cap_basis == "fixed":
                limit_left = cap_amount
            else:
                limit_left = r_even(Fraction(bases[cap_basis] * cap_amount,
                                             100))
            amounts = carried.get(code, [])
            amounts = [(year, cur)] + amounts if current_first \
                else amounts + [(year, cur)]
            years = t.c(("rebate", code, "carry"))[0]
            for origin, amount in amounts:
                use = amount
                if limit_left is not None:
                    use = min(use, limit_left)
                use = max(min(use, gross_left, global_left), 0)
                if use > 0:
                    applied.append({"rebate_code": code,
                                    "origin_year": origin,
                                    "applied_cents": use})
                    if limit_left is not None:
                        limit_left -= use
                    gross_left -= use
                    global_left -= use
                    total += use
                left = amount - use
                if left > 0 and years > 0 and year + 1 - origin <= years:
                    carry_out.append({"rebate_code": code,
                                      "origin_year": origin,
                                      "remaining_cents": left})
        carry_out.sort(key=lambda r: (r["rebate_code"], r["origin_year"]))
        return applied, carry_out, total

    # -- Part 12 ----------------------------------------------------------
    def _instalments(self, aid, net):
        t = self.t
        quarter = net // 4
        amounts = [quarter, quarter, quarter, net - 3 * quarter]
        insts = [{"quarter": "Q%d" % i,
                  "due": t.instalment_dates["Q%d" % i],
                  "amount": amt, "paid": 0, "parts": []}
                 for i, amt in enumerate(amounts, start=1)]
        for eff, _pid, amount in self.pay_of.get(aid, []):
            rem = amount
            for it in insts:
                if rem <= 0:
                    break
                gap = it["amount"] - it["paid"]
                if gap <= 0:
                    continue
                take = min(gap, rem)
                it["paid"] += take
                it["parts"].append((take, eff))
                rem -= take
        grace = timedelta(days=t.c(("grace",))[0])
        out = []
        interest_total = 0
        for it in insts:
            due = it["due"]
            interest = 0
            for part, eff in it["parts"]:
                if eff > due + grace:
                    interest += self._interest(part, due, eff)
            unpaid = it["amount"] - it["paid"]
            if unpaid > 0 and self.b.assessment_date > due + grace:
                interest += self._interest(unpaid, due, self.b.assessment_date)
            interest_total += interest
            out.append({"quarter": it["quarter"],
                        "due_date": due.isoformat(),
                        "amount_cents": it["amount"],
                        "paid_cents": it["paid"],
                        "interest_cents": interest})
        paid_total = sum(a for _e, _p, a in self.pay_of.get(aid, []))
        return out, paid_total, interest_total

    def _interest(self, part, due, end):
        if end <= due:
            return 0
        acc = Fraction(0)
        d = due + DAY
        while d <= end:
            acc += Fraction(part * self.t.v(("interest",), d), 1000000 * 365)
            d += DAY
        return r_up(acc)


# --------------------------------------------------------------------------
# The statements
# --------------------------------------------------------------------------

def totals(rows):
    return {k: sum(r[k] for r in rows) for k in TOTAL_KEYS}


def account_object(r):
    out = dict(r)
    del out["region"]
    return out


def policy_audit(t, batch):
    classes = {}
    for tc in t.classes:
        band, band_a = t.c(("class", tc, "band"))
        df, df_a = t.c(("class", tc, "df"))
        ex, ex_a = t.c(("class", tc, "exempt"))
        classes[tc] = {
            "band": {"value": band, "authority": band_a},
            "discharge_factor_percent": {"value": df, "authority": df_a},
            "catchment_exempt": {"value": ex, "authority": ex_a},
            "block_rates": {
                "block_%d" % i:
                    t.slots[("class", tc, "block", i)].tl.periods("rate")
                for i in (1, 2, 3)}}
    zones = {}
    for z in t.zones:
        reg, reg_a = t.c(("zone", z, "region"))
        dr, dr_a = t.c(("zone", z, "drought"))
        sw, sw_a = t.c(("zone", z, "sw"))
        zones[z] = {"region": {"value": reg, "authority": reg_a},
                    "drought_zone": {"value": dr, "authority": dr_a},
                    "stormwater_rate": {"value": sw, "authority": sw_a},
                    "wastewater_rate_periods":
                        t.slots[("zone", z, "ww")].tl.periods("rate")}
    bands = {}
    for b in ("A", "B", "C"):
        v1, a1 = t.c(("band", b, "b1"))
        v2, a2 = t.c(("band", b, "b2u"))
        bands[b] = {"block_1": {"value": v1, "authority": a1},
                    "block_2_upper": {"value": v2, "authority": a2}}
    surch = {}
    for reg in t.regions:
        v, a = t.c(("surcharge", reg))
        surch[reg] = {"value": v, "authority": a}
    ds, ds_a = t.c(("drought_supp",))
    lv, lv_a = t.c(("levy",))
    gc, gc_a = t.c(("global_cap",))
    gr, gr_a = t.c(("grace",))
    order = sorted((t.c(("rebate", c, "priority"))[0],
                    _sortkey(t.rebates[c]["section"]), c) for c in t.rebates)
    rebates = []
    for _p, _s, code in order:
        pr, pr_a = t.c(("rebate", code, "priority"))
        (rate, _basis), rate_a = t.c(("rebate", code, "amount"))
        (cb, ca), cap_a = t.c(("rebate", code, "cap"))
        cy, cy_a = t.c(("rebate", code, "carry"))
        ex, ex_a = t.c(("rebate", code, "excluded"))
        rule, rule_a = t.c(("rebate", code, "eligibility"))
        entry = {"rebate_code": code,
                 "section": t.rebates[code]["section"],
                 "priority": {"value": pr, "authority": pr_a},
                 "rate_percent": {"value": rate, "authority": rate_a},
                 "cap": {"basis": cb, "amount": ca, "authority": cap_a},
                 "carry_years": {"value": cy, "authority": cy_a},
                 "excluded_forms": {"value": ex, "authority": ex_a}}
        if rule["cards"]:
            entry["concession_cards"] = {"value": rule["cards"],
                                         "authority": rule_a}
        rebates.append(entry)
    minimums = {}
    for cl in ("residential", "commercial", "public"):
        v, a = t.c(("minimum", cl))
        minimums[cl] = {"value": v, "authority": a}
    return {
        "report_id": batch.batch_id,
        "tariff_classes": classes,
        "zones": zones,
        "band_allowances_litres_per_day": bands,
        "daily_service_charges": {str(s): t.slots[("svc", s)].tl.periods("rate")
                                  for s in t.sizes},
        "regional_surcharge_ppm": surch,
        "drought_supplement_ppm": {"value": ds, "authority": ds_a},
        "catchment_levy_ppm": {"value": lv, "authority": lv_a},
        "trade_waste_rates": {
            "volume": t.slots[("tw", "volume")].tl.periods("rate"),
            "load": t.slots[("tw", "load")].tl.periods("rate")},
        "rebates_in_application_order": rebates,
        "global_rebate_cap_percent": {"value": gc, "authority": gc_a},
        "minimum_charge_cents": minimums,
        "interest_grace_days": {"value": gr, "authority": gr_a},
        "interest_rate_periods":
            t.slots[("interest",)].tl.periods("rate_ppm"),
        "instalment_due_dates": {q: d.isoformat()
                                 for q, d in t.instalment_dates.items()},
        "binding_rulings_applied": sorted(t.rulings, key=_sortkey),
    }


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, indent=2, sort_keys=True))
        fh.write("\n")


def main(argv):
    data_dir, out_dir = argv[1], argv[2]
    with open(os.path.join(data_dir, "tariff_code.md"), encoding="utf-8") as fh:
        raw = fh.read()
    t = Tariff(raw)
    batch = Batch(data_dir)
    a = Assessment(t, batch)
    os.makedirs(out_dir, exist_ok=True)
    rows = a.results

    for region in t.regions:
        sel = [r for r in rows if r["region"] == region]
        write_json(os.path.join(out_dir, "region_%s.json" % region),
                   {"region": region,
                    "account_count": len(sel),
                    "totals": totals(sel),
                    "accounts": [account_object(r) for r in sel]})

    for seg in ("commercial", "public"):
        sel = [r for r in rows if r["account_class"] == seg]
        reb = {}
        for r in sel:
            for ap in r["rebates_applied"]:
                reb[ap["rebate_code"]] = reb.get(ap["rebate_code"], 0) \
                    + ap["applied_cents"]
        write_json(os.path.join(out_dir, "segment_%s.json" % seg),
                   {"segment": seg,
                    "account_count": len(sel),
                    "totals": totals(sel),
                    "rebate_totals": reb,
                    "account_ids": [r["account_id"] for r in sel]})

    write_json(os.path.join(out_dir, "summary.json"), {
        "report_id": batch.batch_id,
        "assessment_date": batch.assessment_date.isoformat(),
        "account_count": len(rows),
        "totals": totals(rows),
        "region_totals": {reg: totals([r for r in rows if r["region"] == reg])
                          for reg in t.regions},
        "class_account_counts": {
            cl: sum(1 for r in rows if r["account_class"] == cl)
            for cl in ("residential", "commercial", "public")},
        "balance_status_counts": {
            "credit_balance": sum(1 for r in rows if r["balance_cents"] < 0),
            "settled": sum(1 for r in rows if r["balance_cents"] == 0),
            "balance_due": sum(1 for r in rows if r["balance_cents"] > 0)}})

    write_json(os.path.join(out_dir, "policy_audit.json"),
               policy_audit(t, batch))

    issues = sorted(a.issues)
    write_json(os.path.join(out_dir, "data_quality.json"), {
        "input_file_count": batch.file_count,
        "account_count": len(batch.accounts),
        "property_count": len(batch.properties),
        "meter_count": len(batch.meters),
        "reading_count": len(batch.reads),
        "trade_waste_return_count": len(batch.trade_waste),
        "claim_count": len(batch.claims),
        "leak_claim_count": len(batch.leaks),
        "carryforward_count": len(batch.carry),
        "payment_count": len(batch.payments),
        "quality_issue_count": len(issues),
        "quality_issues": issues})


if __name__ == "__main__":
    main(sys.argv)
