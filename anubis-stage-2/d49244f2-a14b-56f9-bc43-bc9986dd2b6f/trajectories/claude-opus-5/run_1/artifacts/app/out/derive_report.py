#!/usr/bin/env python3
"""Derive the assessment statements of a return batch under the Consolidated
Enterprise Levy Code of the Commonwealth of Arvenna (levy year 2026).

Usage:  python3 derive_report.py <DATA_DIR> <OUT_DIR>

The Code shipped in <DATA_DIR>/levy_code.md is parsed; the amendments of
Divisions 7-1 and 7-3, the corrections of Division 7-2 and the Binding Rulings
of Part 14 are applied as section 1-004 directs.  Division 7-9 and the
Explanatory Memoranda and Illustrative Examples of Part 14 have no legal
effect (section 1-004(6) and (7)) and are ignored.

All money arithmetic is exact (int / fractions.Fraction); no float is used.
"""

import csv
import json
import os
import re
import sys
from datetime import date, timedelta
from fractions import Fraction

# ----------------------------------------------------------------------------
# rounding (sections 1-080 and 12-040)
# ----------------------------------------------------------------------------


def rnd_half_even(fr):
    """Section 1-080(1): nearest whole cent, ties to the even cent."""
    n, d = fr.numerator, fr.denominator
    q, r = divmod(n, d)
    t = 2 * r
    if t > d or (t == d and q % 2 != 0):
        q += 1
    return q


def rnd_half_up(fr):
    """Section 12-040(1): nearest whole cent, a half rounded up."""
    n, d = fr.numerator, fr.denominator
    q, r = divmod(n, d)
    if 2 * r >= d:
        q += 1
    return q


# ----------------------------------------------------------------------------
# the Code: sectioning
# ----------------------------------------------------------------------------

SEC_HEAD = re.compile(r"^###\s+Section\s+(\d+-\d+)\.\s*(.*)$")
DIV_HEAD = re.compile(r"^####\s+Division\s+([\d-]+)\.")
PART_HEAD = re.compile(r"^##\s+Part\s+(\d+)\.")
DATE_RE = r"(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})"
MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11,
    "December": 12,
}
PCT = r"(\d+(?:\.\d+)?\s+per cent)"
QUARTERS = ("Q1", "Q2", "Q3", "Q4")
REGIONS = ("North", "South", "West", "East")


def parse_long_date(s):
    d, m, y = s.split()
    return date(int(y), MONTHS[m], int(d))


def sec_key(num):
    a, b = num.split("-")
    return (int(a), int(b))


class Section:
    __slots__ = ("num", "part", "idx", "title", "text", "division", "repl")

    def __init__(self, num, title, part, division):
        self.num = num
        self.part, self.idx = sec_key(num)
        self.title = title
        self.division = division
        self.text = ""
        # (modifying section number, replacement text), in order of application
        self.repl = []

    def key(self):
        return (self.part, self.idx)

    def authority(self, matched):
        """The authority rule: the provision that fixes the value, or, where
        that provision was corrected or amended textually, the provision whose
        words now state it (section 1-004(3) and (4))."""
        found = self.num
        for num, new in self.repl:
            if matched and matched in new:
                found = num
        return found


def load_code(path):
    sections = {}
    order = []
    cur = None
    part = None
    division = None
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            mp = PART_HEAD.match(line)
            if mp:
                part, division, cur = int(mp.group(1)), None, None
                continue
            md = DIV_HEAD.match(line)
            if md:
                division, cur = md.group(1), None
                continue
            ms = SEC_HEAD.match(line)
            if ms:
                cur = Section(ms.group(1), ms.group(2), part, division)
                sections[cur.num] = cur
                order.append(cur.num)
                continue
            if cur is not None:
                cur.text += line + "\n"
    order.sort(key=sec_key)
    return sections, order


# ----------------------------------------------------------------------------
# the Code: corrections and textual amendments
# ----------------------------------------------------------------------------

CORRECTION = re.compile(
    r"In section (\d+-\d+)(?:\([^)]*\))*,\s*(?:in the entry for [^,]+,\s*)?"
    r"for '([^']*)' read '([^']*)'")
SUBSTITUTION = re.compile(
    r"In section (\d+-\d+)(?:\([^)]*\))*,\s*(?:in the entry for [^,]+,\s*)?"
    r"for '([^']*)' substitute '([^']*)'(\s+wherever occurring)?")
PARA_SUB_A = re.compile(
    r"Paragraph \((\w)\) of section (\d+-\d+) is repealed and the following "
    r"paragraph is substituted: '(.*?)'\s*$", re.M)
PARA_SUB_B = re.compile(
    r"For paragraph \((\w)\) of section (\d+-\d+) substitute: '(.*?)'\s*$",
    re.M)


def has_effect(sec):
    """Section 1-004(6): nothing in Division 7-9 has legal effect.
    Section 1-004(7): of Part 14 only a Binding Ruling has."""
    if sec.division == "7-9":
        return False
    if sec.part == 14:
        return "Designation: Binding Ruling." in sec.text
    return True


def apply_text_modifications(sections, order):
    """Section 1-004(4) first - a correction is read as if its words had
    always appeared - then every textual amendment in ascending order of
    section number (section 1-004(3))."""
    corrections = []
    for num in order:
        sec = sections[num]
        if sec.division != "7-2":
            continue
        for m in CORRECTION.finditer(sec.text):
            corrections.append((sec.key(), sec.num, m.group(1), m.group(2),
                                m.group(3)))
    corrections.sort(key=lambda t: t[0])
    for _, cnum, target, old, new in corrections:
        tgt = sections.get(target)
        if tgt is None or old not in tgt.text:
            continue
        tgt.text = tgt.text.replace(old, new, 1)
        tgt.repl.append((cnum, new))

    amendments = []
    for num in order:
        sec = sections[num]
        if sec.division == "7-2" or not has_effect(sec):
            continue
        for m in SUBSTITUTION.finditer(sec.text):
            amendments.append((sec.key(), sec.num, "text", m.group(1),
                               m.group(2), m.group(3), m.group(4)))
        for rx in (PARA_SUB_A, PARA_SUB_B):
            for m in rx.finditer(sec.text):
                amendments.append((sec.key(), sec.num, "para", m.group(2),
                                   m.group(1), m.group(3), None))
    amendments.sort(key=lambda t: t[0])
    for _, anum, kind, target, a, b, every in amendments:
        tgt = sections.get(target)
        if tgt is None:
            continue
        if kind == "text":
            if a not in tgt.text:
                continue
            tgt.text = tgt.text.replace(a, b) if every \
                else tgt.text.replace(a, b, 1)
            tgt.repl.append((anum, b))
        else:
            pat = re.compile(r"^\(%s\)\s.*$" % re.escape(a), re.M)
            if not pat.search(tgt.text):
                continue
            tgt.text = pat.sub(lambda _m: b, tgt.text, count=1)
            tgt.repl.append((anum, b))


# ----------------------------------------------------------------------------
# the Code: the values in force
# ----------------------------------------------------------------------------


def pct_to_ppm(text):
    """'0.4250 per cent' -> 4250 parts per million."""
    return int(Fraction(re.match(r"(\d+(?:\.\d+)?)", text).group(1)) * 10000)


def dollars_to_cents(text):
    num = re.search(r"([\d,]+(?:\.\d+)?)", text).group(1).replace(",", "")
    return int(Fraction(num) * 100)


def cents_to_millicents(text):
    return int(Fraction(re.match(r"(\d+(?:\.\d+)?)", text).group(1)) * 1000)


DOLLARS = r"(\$\d+(?:,\d{3})*(?:\.\d+)?)"
WORD_NUM = {"no": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
MULT_WORD = {"twice": 2, "double": 2, "three times": 3, "treble": 3}
FUEL_WORDS = (("grid", "grid_electricity"), ("natural gas", "natural_gas"),
              ("diesel", "diesel"), ("biomass", "biomass"),
              ("solar", "solar_onsite"))
FORM_WORDS = (("sole trader", "sole_trader"), ("partnership", "partnership"),
              ("company", "company"), ("trust", "trust"),
              ("cooperative", "cooperative"),
              ("statutory body", "statutory_body"))


def _lookup(desc, table):
    low = desc.lower()
    for word, key in table:
        if word in low:
            return key
    return None


def _in_section_range(num, lo, hi):
    return sec_key(lo) <= sec_key(num) <= sec_key(hi)


class Policy:
    """Every value of the Code that the assessment applies, as in force."""

    def __init__(self, sections, order, year=2026):
        self.sections = sections
        self.order = order
        self.year = year
        self.year_start = date(year, 1, 1)
        self.year_end = date(year, 12, 31)
        self.quarter_start = {"Q1": date(year, 1, 1), "Q2": date(year, 4, 1),
                              "Q3": date(year, 7, 1), "Q4": date(year, 10, 1)}
        self.quarter_end = {"Q1": date(year, 3, 31), "Q2": date(year, 6, 30),
                            "Q3": date(year, 9, 30), "Q4": date(year, 12, 31)}
        self.days_in_year = self._read_year_days()
        self._read_holidays()
        self._read_classes()
        self._read_districts()
        self._read_dated()
        self._read_scalars()
        self._read_rulings()
        self._read_credits()
        self._read_minimum_levy()
        self._read_interest()
        self._read_due_dates()

    # -- helpers -----------------------------------------------------------
    def _search(self, num, pattern, flags=0):
        sec = self.sections[num]
        m = re.search(pattern, sec.text, flags)
        if m is None:
            raise ValueError("section %s: no match for %r" % (num, pattern))
        return sec, m

    def _val(self, num, pattern, conv, flags=0):
        sec, m = self._search(num, pattern, flags)
        raw = m.group(1)
        return {"value": conv(raw), "authority": sec.authority(raw)}

    def _rulings(self):
        for num in self.order:
            sec = self.sections[num]
            if sec.part == 14 and has_effect(sec):
                yield sec

    # -- section 1-002(2): the number of days every proration uses ---------
    def _read_year_days(self):
        _, m = self._search(
            "1-002", r"consists of (\d+) days, and every proration under "
                     r"this Code uses that number of days")
        return int(m.group(1))

    # -- section 1-090: public holidays ------------------------------------
    def _read_holidays(self):
        _, m = self._search(
            "1-090", r"public holidays for the purposes of this Code:(.*?)\.",
            re.S)
        self.holidays = set()
        for part in m.group(1).split(";"):
            mm = re.match(r"^" + DATE_RE + r"$", part.strip())
            if mm:
                self.holidays.add(parse_long_date(mm.group(1)))

    def is_business_day(self, d):
        return d.weekday() < 5 and d not in self.holidays

    def next_business_day(self, d):
        while not self.is_business_day(d):
            d += timedelta(days=1)
        return d

    # -- Schedule 2 and the residual class ---------------------------------
    def _read_classes(self):
        self.classes = {}
        self.class_section = {}
        self.schedule_2 = set()
        self.residual_class = None
        for num in self.order:
            sec = self.sections[num]
            if sec.part != 2:
                continue
            mt = re.match(r"Class (AC-\d+):", sec.title)
            if not mt:
                continue
            code = mt.group(1)
            _, mr = self._search(num, r"\(d\) Scheduled rate\..*?" + PCT)
            _, mb = self._search(num, r"\(f\) Band\..*?Band (I{1,3})\b")
            me = re.search(r"\(e\) Export receipts\.([^\n]*)", sec.text)
            etext = me.group(1)
            excluded = ("are deducted in computing" in etext
                        or "are excluded from assessable receipts" in etext)
            self.classes[code] = {
                "section": num,
                "band": {"value": mb.group(1),
                         "authority": sec.authority(mb.group(1))},
                "export_excluded": {"value": excluded,
                                    "authority": sec.authority(etext.strip())},
                "base_rate": pct_to_ppm(mr.group(1)),
                "base_authority": sec.authority(mr.group(1)),
            }
            self.class_section[num] = code
            self.schedule_2.add(code)
        for num in self.order:
            sec = self.sections[num]
            if not has_effect(sec):
                continue
            mc = re.search(
                r"establishes the residual class, Class (AC-\d+)", sec.text)
            if not mc:
                continue
            code = mc.group(1)
            _, mr = self._search(
                num, r"The scheduled rate of Class AC-\d+ is " + PCT)
            _, mb = self._search(
                num, r"Class AC-\d+ is assigned to Band (I{1,3})\b")
            me = re.search(
                r"Export receipts of a line assessed under Class AC-\d+ "
                r"are (not )?excluded", sec.text)
            self.residual_class = code
            self.classes[code] = {
                "section": num,
                "band": {"value": mb.group(1),
                         "authority": sec.authority(mb.group(1))},
                "export_excluded": {"value": me.group(1) is None,
                                    "authority": sec.authority(me.group(0))},
                "base_rate": pct_to_ppm(mr.group(1)),
                "base_authority": sec.authority(mr.group(1)),
            }
            self.class_section[num] = code

    # -- Schedule 3 --------------------------------------------------------
    def _read_districts(self):
        self.districts = {}
        for num in self.order:
            sec = self.sections[num]
            if sec.part != 3:
                continue
            mt = re.match(r"District (D-\d+):", sec.title)
            if not mt:
                continue
            _, mg = self._search(
                num, r"\(b\) Region\.[^\n]*?(North|South|West|East) region")
            dtext = re.search(r"\(c\) Designations\.([^\n]*)",
                              sec.text).group(1)
            coastal = edz = False
            for clause in dtext.split(" and "):
                negated = " not " in clause
                if "Coastal Zone district" in clause:
                    coastal = not negated
                if "Enterprise Development Zone district" in clause:
                    edz = not negated
            _, mr = self._search(
                num, r"\(d\) Rate\.[^\n]*?(\$[\d,.]+ per square metre)")
            self.districts[mt.group(1)] = {
                "section": num,
                "region": mg.group(1),
                "coastal": coastal,
                "edz": edz,
                "base_rate": dollars_to_cents(mr.group(1)),
                "base_authority": sec.authority(mr.group(1)),
            }

    # -- modifying provisions that take effect from a stated date ----------
    def _read_dated(self):
        class_rate, class_incr = [], []
        district_rate, district_red = [], []
        energy_rate, interest_rate = [], []
        for num in self.order:
            sec = self.sections[num]
            if sec.division == "7-2" or not has_effect(sec):
                continue
            t = sec.text
            for m in re.finditer(
                    r"The scheduled rate for Class (AC-\d+) \(section "
                    r"\d+-\d+\(d\)\) is " + PCT + r", with effect from "
                    + DATE_RE, t):
                class_rate.append((sec.key(), sec.num, m.group(1),
                                   parse_long_date(m.group(3)),
                                   pct_to_ppm(m.group(2)),
                                   sec.authority(m.group(2))))
            for m in re.finditer(
                    r"With effect from " + DATE_RE + r", receipts of lines "
                    r"assessed under Class (AC-\d+) bear activity levy at "
                    r"the scheduled rate of " + PCT, t):
                class_rate.append((sec.key(), sec.num, m.group(2),
                                   parse_long_date(m.group(1)),
                                   pct_to_ppm(m.group(3)),
                                   sec.authority(m.group(3))))
            for m in re.finditer(
                    r"With effect from " + DATE_RE + r", section "
                    r"(\d+-\d+)\(d\) has effect as if the scheduled rate "
                    r"stated in it were " + PCT, t):
                code = self.class_section.get(m.group(2))
                if code:
                    class_rate.append((sec.key(), sec.num, code,
                                       parse_long_date(m.group(1)),
                                       pct_to_ppm(m.group(3)),
                                       sec.authority(m.group(3))))
            for m in re.finditer(
                    r"With effect from " + DATE_RE + r", the scheduled rate "
                    r"of every class whose entry is a section numbered from "
                    r"section (\d+-\d+) to section (\d+-\d+), both "
                    r"inclusive, and which under this Code is assigned to "
                    r"Band (I{1,3}), is increased by (\d+(?:\.\d+)?) "
                    r"percentage points", t):
                class_incr.append((sec.key(), sec.num,
                                   parse_long_date(m.group(1)), m.group(2),
                                   m.group(3), m.group(4),
                                   int(Fraction(m.group(5)) * 10000)))
            for m in re.finditer(
                    r"With effect from " + DATE_RE + r", the establishment "
                    r"levy rate for District (D-\d+) \([^)]*\) under section "
                    r"\d+-\d+\(d\) is (\$[\d,.]+ per square metre) per "
                    r"annum", t):
                district_rate.append((sec.key(), sec.num, m.group(2),
                                      parse_long_date(m.group(1)),
                                      dollars_to_cents(m.group(3)),
                                      sec.authority(m.group(3))))
            for m in re.finditer(
                    r"With effect from " + DATE_RE + r", the establishment "
                    r"levy rate for each district of the "
                    r"(North|South|West|East) region that is designated an "
                    r"Enterprise Development Zone district is reduced by "
                    r"(\$[\d,.]+) per square metre per annum", t):
                district_red.append((sec.key(), sec.num, m.group(2),
                                     parse_long_date(m.group(1)),
                                     dollars_to_cents(m.group(3))))
            for m in re.finditer(
                    r"With effect from " + DATE_RE + r", the rate in section "
                    r"5-010 for ([^,]+?) is (\d+(?:\.\d+)? cents) per "
                    r"kilowatt-hour", t):
                fuel = _lookup(m.group(2), FUEL_WORDS)
                if fuel:
                    energy_rate.append((sec.key(), sec.num, fuel,
                                        parse_long_date(m.group(1)),
                                        cents_to_millicents(m.group(3)),
                                        sec.authority(m.group(3))))
            for m in re.finditer(
                    r"With effect from " + DATE_RE + r", the rate of "
                    r"interest under section 12-020 is " + PCT + r" per "
                    r"annum", t):
                interest_rate.append((sec.key(), sec.num,
                                      parse_long_date(m.group(1)),
                                      pct_to_ppm(m.group(2)),
                                      sec.authority(m.group(2))))
        for lst in (class_rate, class_incr, district_rate, district_red,
                    energy_rate, interest_rate):
            lst.sort(key=lambda t: t[0])
        self._class_rate = class_rate
        self._class_incr = class_incr
        self._district_rate = district_rate
        self._district_red = district_red
        self._energy_rate = energy_rate
        self._interest_rate = interest_rate
        self._build_class_rates()
        self._build_district_rates()
        self._build_energy_rates()

    def _build_class_rates(self):
        self.class_rates = {}
        for code, info in self.classes.items():
            per_q = {}
            for q in QUARTERS:
                qs = self.quarter_start[q]
                ppm, auth = info["base_rate"], info["base_authority"]
                for _, _snum, ccode, frm, val, a in self._class_rate:
                    if ccode == code and frm <= qs:
                        ppm, auth = val, a
                for _, snum, frm, lo, hi, band, delta in self._class_incr:
                    if frm > qs:
                        continue
                    if not _in_section_range(info["section"], lo, hi):
                        continue
                    if info["band"]["value"] != band:
                        continue
                    ppm, auth = ppm + delta, snum
                per_q[q] = {"value": ppm, "authority": auth}
            self.class_rates[code] = per_q

    def _build_district_rates(self):
        self.district_periods = {}
        for code, info in self.districts.items():
            periods = []
            d = self.year_start
            while d <= self.year_end:
                cents, auth = info["base_rate"], info["base_authority"]
                for _, _snum, dcode, frm, val, a in self._district_rate:
                    if dcode == code and frm <= d:
                        cents, auth = val, a
                for _, snum, region, frm, delta in self._district_red:
                    if info["region"] == region and info["edz"] and frm <= d:
                        cents, auth = cents - delta, snum
                if periods and periods[-1][2] == cents \
                        and periods[-1][3] == auth:
                    periods[-1][1] = d
                else:
                    periods.append([d, d, cents, auth])
                d += timedelta(days=1)
            self.district_periods[code] = periods

    def _build_energy_rates(self):
        sec = self.sections["5-010"]
        base = {}
        for m in re.finditer(
                r"for ([a-z][^,;]*), (?:(\d+(?:\.\d+)?) cents per "
                r"kilowatt-hour|(nil))", sec.text):
            fuel = _lookup(m.group(1), FUEL_WORDS)
            if fuel is None:
                continue
            if m.group(3):
                base[fuel] = (0, sec.authority(m.group(3)))
            else:
                base[fuel] = (cents_to_millicents(m.group(2)),
                              sec.authority(m.group(2)))
        self.energy_rates = {}
        for fuel, (mc, auth) in base.items():
            per_q = {}
            for q in QUARTERS:
                qs = self.quarter_start[q]
                v, a = mc, auth
                for _, _snum, f, frm, val, aa in self._energy_rate:
                    if f == fuel and frm <= qs:
                        v, a = val, aa
                per_q[q] = {"value": v, "authority": a}
            self.energy_rates[fuel] = per_q

    # -- the remaining scalar values ---------------------------------------
    def _read_scalars(self):
        sec = self.sections["6-010"]
        self.regional_surcharge_ppm = {}
        for m in re.finditer(
                r"for the (North|South|West|East) region, " + PCT, sec.text):
            self.regional_surcharge_ppm[m.group(1)] = {
                "value": pct_to_ppm(m.group(2)),
                "authority": sec.authority(m.group(2))}
        self.coastal_supplement_ppm = self._val(
            "6-020", r"coastal supplement of " + PCT, pct_to_ppm)
        self.public_floor_factor_percent = self._val(
            "8-020", r"computed at (\d+) per cent of the rate", int)
        self.payroll_rate_ppm = self._val(
            "4-010", r"The rate of payroll levy is " + PCT, pct_to_ppm)
        self.payroll_annual_exemption_cents = self._val(
            "4-020", r"annual exemption of a filer is " + DOLLARS,
            dollars_to_cents)
        self.band_iii_energy_reduction_percent = self._val(
            "5-020", r"reduced by (\d+) per cent of", int)
        self.small_enterprise_threshold_cents = self._val(
            "2-040", r"do not exceed " + DOLLARS, dollars_to_cents)
        self.small_enterprise_rate_factor_percent = self._val(
            "2-040", r"computed at (\d+) per cent of the scheduled rate", int)
        self.global_credit_cap_percent = self._val(
            "9-001", r"must not exceed (\d+) per cent of its Gross Levy", int)

    # -- the Binding Rulings of Part 14 (section 1-004(7)) -----------------
    def _read_rulings(self):
        self.mutual_exemption_multiplier = {"value": 1, "authority": "4-020"}
        self.minimum_levy_prorated = False
        self.carryforward_needs_eligibility = True
        self.principal_district_by_floor_area = False
        for sec in self._rulings():
            m = re.search(
                r"annual exemption of a mutual-class filer is (twice|double|"
                r"three times|treble) the amount stated in section 4-020",
                sec.text)
            if m:
                self.mutual_exemption_multiplier = {
                    "value": MULT_WORD[m.group(1).lower()],
                    "authority": sec.num}
            if re.search(r"minimum levy of every filer is prorated",
                         sec.text):
                self.minimum_levy_prorated = True
            if re.search(r"section 10-006 does not apply", sec.text):
                self.carryforward_needs_eligibility = False
            if re.search(r"the district in which the greatest total floor "
                         r"area of such establishments is located", sec.text):
                self.principal_district_by_floor_area = True

    # -- the credits of the Code -------------------------------------------
    def _read_credits(self):
        creds = []
        for num in self.order:
            sec = self.sections[num]
            if not has_effect(sec):
                continue
            m = re.search(
                r"establishes the (.+?) Credit, identified by credit code "
                r"(K-\d+)", sec.text)
            if not m:
                continue
            _, mr = self._search(
                num, r"Amount\. The current-year amount of the credit is "
                     + PCT + r" of ([^.]*)\.")
            base_text = mr.group(2)
            if "apprentice payroll" in base_text:
                base = "apprentice_payroll"
            elif "export receipts" in base_text:
                base = "export_receipts"
            else:
                base = "qualifying_expenditure"
            limit_text = re.search(
                r"Limit\. The amount of the credit applied (?:for the levy "
                r"year )?must not exceed ([^.]+?)\.", sec.text).group(1)
            mf = re.search(DOLLARS, limit_text)
            if mf:
                cap = {"basis": "fixed",
                       "amount": dollars_to_cents(mf.group(1)),
                       "authority": sec.authority(mf.group(1))}
            else:
                mp = re.search(
                    PCT + r" of the filer's (Primary|Gross) Levy", limit_text)
                if mp:
                    cap = {"basis": mp.group(2).lower() + "_levy",
                           "amount": pct_to_ppm(mp.group(1)),
                           "authority": sec.authority(mp.group(2) + " Levy")}
                else:
                    mq = re.search(r"the filer's (payroll|energy) levy",
                                   limit_text)
                    cap = {"basis": mq.group(1) + "_levy",
                           "amount": 1000000,
                           "authority": sec.authority(mq.group(0))}
            ctext = re.search(r"Carry-forward period\.([^\n]*)",
                              sec.text).group(1)
            if "no carry-forward period" in ctext:
                carry = 0
                cauth = sec.authority("no carry-forward period")
            else:
                mw = re.search(r"carried forward for (\w+) levy years?",
                               ctext)
                carry = WORD_NUM[mw.group(1).lower()]
                cauth = sec.authority(mw.group(1) + " levy years")
            creds.append({
                "credit_code": m.group(2),
                "section": num,
                "rate_ppm": {"value": pct_to_ppm(mr.group(1)),
                             "authority": sec.authority(mr.group(1))},
                "cap": cap,
                "carry_years": {"value": carry, "authority": cauth},
                "_key": sec.key(),
                "_base": base,
                "_on_claim": "arises without a claim" not in sec.text,
            })
        creds.sort(key=lambda c: c["_key"])    # section 1-086(1)
        self.credits = creds
        self.credit_by_code = {c["credit_code"]: c for c in creds}

    # -- Part 11 -----------------------------------------------------------
    def _read_minimum_levy(self):
        sec = self.sections["11-010"]
        self.minimum_levy_cents = {}
        for m in re.finditer(r"for ([^,;]+?), " + DOLLARS, sec.text):
            form = _lookup(m.group(1), FORM_WORDS)
            if form is None:
                continue
            self.minimum_levy_cents[form] = {
                "value": dollars_to_cents(m.group(2)),
                "authority": sec.authority(m.group(2))}

    # -- Part 12 -----------------------------------------------------------
    def _read_interest(self):
        sec, m = self._search("12-020",
                              r"at the rate of " + PCT + r" per annum")
        periods = [{"from": self.year_start, "to": None,
                    "rate_ppm": pct_to_ppm(m.group(1)),
                    "authority": sec.authority(m.group(1))}]
        for _, _snum, frm, ppm, auth in self._interest_rate:
            periods[-1]["to"] = frm - timedelta(days=1)
            periods.append({"from": frm, "to": None, "rate_ppm": ppm,
                            "authority": auth})
        self.interest_periods = periods

    def interest_rate_ppm(self, day):
        chosen = self.interest_periods[0]["rate_ppm"]
        for p in self.interest_periods:
            if day >= p["from"]:
                chosen = p["rate_ppm"]
        return chosen

    def _read_due_dates(self):
        self.instalment_due_dates = {}
        for q in QUARTERS:
            qe = self.quarter_end[q]
            y, m = (qe.year + 1, 1) if qe.month == 12 else (qe.year,
                                                            qe.month + 1)
            last = (date(y + 1, 1, 1) if m == 12
                    else date(y, m + 1, 1)) - timedelta(days=1)
            self.instalment_due_dates[q] = self.next_business_day(last)


# ----------------------------------------------------------------------------
# the registers
# ----------------------------------------------------------------------------


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def pdate(s):
    return date(*(int(x) for x in s.split("-"))) if s else None


class Batch:
    def __init__(self, data_dir):
        with open(os.path.join(data_dir, "batch.json"),
                  encoding="utf-8") as fh:
            man = json.load(fh)
        self.batch_id = man["batch_id"]
        self.assessment_date = pdate(man["assessment_date"])
        self.filers = read_csv(os.path.join(data_dir, "filers.csv"))
        self.establishments = read_csv(
            os.path.join(data_dir, "establishments.csv"))
        self.receipts = read_csv(os.path.join(data_dir, "receipts.csv"))
        self.payroll = read_csv(os.path.join(data_dir, "payroll.csv"))
        self.energy = read_csv(os.path.join(data_dir, "energy.csv"))
        self.claims = read_csv(os.path.join(data_dir, "credit_claims.csv"))
        self.carryforwards = read_csv(
            os.path.join(data_dir, "carryforwards.csv"))
        self.payments = read_csv(os.path.join(data_dir, "payments.csv"))
        self.file_count = sum(
            1 for n in os.listdir(data_dir)
            if os.path.isfile(os.path.join(data_dir, n)))


# ----------------------------------------------------------------------------
# the assessment
# ----------------------------------------------------------------------------

TOTAL_KEYS = ("activity_levy_cents", "floor_levy_cents", "payroll_levy_cents",
              "energy_levy_cents", "surcharge_cents", "primary_levy_cents",
              "gross_levy_cents", "credits_total_cents",
              "minimum_topup_cents", "net_levy_cents", "payments_cents",
              "interest_cents", "balance_cents")


def overlap_days(a_lo, a_hi, b_lo, b_hi):
    lo, hi = max(a_lo, b_lo), min(a_hi, b_hi)
    return max(0, (hi - lo).days + 1)


class Assessor:
    def __init__(self, pol, batch):
        self.pol = pol
        self.batch = batch
        self.issues = []
        b = batch
        self.est_by_filer = {}
        for e in b.establishments:
            self.est_by_filer.setdefault(e["filer_id"], []).append(e)
        self.receipts_by_filer = self._group(b.receipts)
        self.payroll_by_filer = self._group(b.payroll)
        self.energy_by_filer = self._group(b.energy)
        self.claims_by_filer = self._group(b.claims)
        self.cf_by_filer = self._group(b.carryforwards)
        self.pay_by_filer = self._group(b.payments)

    @staticmethod
    def _group(rows):
        out = {}
        for r in rows:
            out.setdefault(r["filer_id"], []).append(r)
        return out

    # -- active days (sections 1-202 and 1-203) ----------------------------
    def spans(self, f):
        pol = self.pol
        lo = max(pol.year_start, pdate(f["commenced_on"]))
        hi = pol.year_end
        ced = pdate(f["ceased_on"])
        if ced is not None and ced < hi:
            hi = ced
        ests = {}
        for e in self.est_by_filer.get(f["filer_id"], []):
            e_lo = max(lo, pdate(e["opened_on"]))
            e_hi = hi
            cl = pdate(e["closed_on"])
            if cl is not None and cl < e_hi:
                e_hi = cl
            ests[e["establishment_id"]] = (e_lo, e_hi)
        return (lo, hi), ests

    # -- one filer ---------------------------------------------------------
    def assess(self, f):
        pol = self.pol
        fid = f["filer_id"]
        (f_lo, f_hi), est_spans = self.spans(f)
        active_days = max(0, (f_hi - f_lo).days + 1)
        ests = self.est_by_filer.get(fid, [])

        # Binding Ruling BR 2026/03 (section 14-010): principal district
        principal = f["registered_district"]
        if pol.principal_district_by_floor_area:
            area = {}
            for e in ests:
                lo, hi = est_spans[e["establishment_id"]]
                if hi >= lo:
                    area[e["district"]] = (area.get(e["district"], 0)
                                           + int(e["floor_area_m2"]))
            if area:
                best = max(area.values())
                principal = min(d for d, a in area.items() if a == best)
        dinfo = pol.districts[principal]

        # sections 2-040 and 2-041: the small enterprise election
        elected = f["small_enterprise_election"] == "Y"
        if elected and f["filer_class"] == "public":
            self.issues.append(
                "%s: small enterprise election by a public-class filer "
                "disregarded" % fid)
            elected = False

        # ---- Part 2 ------------------------------------------------------
        lines = []
        for r in self.receipts_by_filer.get(fid, []):
            code = r["activity_code"]
            # sections 2-003(2) and 7-308(2)
            assessed = (code if code in pol.schedule_2
                        else pol.residual_class)
            if code not in pol.schedule_2:          # section 7-308(6)
                self.issues.append(
                    "%s/%s/%s: unscheduled activity code %s assessed under %s"
                    % (fid, r["establishment_id"], r["quarter"], code,
                       pol.residual_class))
            span = est_spans.get(r["establishment_id"])
            if span is None or overlap_days(
                    pol.quarter_start[r["quarter"]],
                    pol.quarter_end[r["quarter"]], span[0], span[1]) == 0:
                self.issues.append(
                    "%s/%s/%s: receipts reported for an inactive "
                    "establishment" % (fid, r["establishment_id"],
                                       r["quarter"]))
            gross, export = int(r["gross_cents"]), int(r["export_cents"])
            cls = pol.classes[assessed]
            lines.append({
                "establishment_id": r["establishment_id"],
                "reported_code": code,
                "assessed_code": assessed,
                "quarter": r["quarter"],
                "assessable_cents": (gross - export
                                     if cls["export_excluded"]["value"]
                                     else gross),
                "_export": export,
                "_sched": pol.class_rates[assessed][r["quarter"]]["value"],
            })
        total_positive = sum(l["assessable_cents"] for l in lines
                             if l["assessable_cents"] > 0)
        se_applied = bool(
            elected and total_positive
            <= pol.small_enterprise_threshold_cents["value"])
        factor = (Fraction(pol.small_enterprise_rate_factor_percent["value"],
                           100) if se_applied else Fraction(1))
        activity_levy = 0
        for l in lines:
            rate = Fraction(l["_sched"]) * factor
            if rate.denominator != 1:
                raise ValueError("rate not a whole number of ppm")
            l["rate_ppm"] = int(rate)
            l["levy_cents"] = (
                rnd_half_even(Fraction(l["assessable_cents"] * int(rate),
                                       1000000))
                if l["assessable_cents"] > 0 else 0)   # section 1-088
            activity_levy += l["levy_cents"]
        lines.sort(key=lambda l: (l["establishment_id"], l["quarter"],
                                  l["reported_code"]))

        # section 2-045: the predominant class
        totals = {}
        for l in lines:
            if l["assessable_cents"] > 0:
                totals[l["assessed_code"]] = (totals.get(l["assessed_code"], 0)
                                              + l["assessable_cents"])
        if totals:
            best = max(totals.values())
            predominant = min(c for c, v in totals.items() if v == best)
            band = pol.classes[predominant]["band"]["value"]
        else:
            predominant, band = None, None

        # ---- Part 3 with Part 8 ------------------------------------------
        pub_factor = (Fraction(pol.public_floor_factor_percent["value"], 100)
                      if f["filer_class"] == "public" else Fraction(1))
        floor_levy = 0
        for e in sorted(ests, key=lambda x: x["establishment_id"]):
            lo, hi = est_spans[e["establishment_id"]]
            if hi < lo:
                continue
            area = int(e["floor_area_m2"])
            for p_from, p_to, cents, _a in pol.district_periods[e["district"]]:
                days = overlap_days(p_from, p_to, lo, hi)
                if days:
                    floor_levy += rnd_half_even(
                        Fraction(area * cents * days, pol.days_in_year)
                        * pub_factor)

        # ---- Part 4 ------------------------------------------------------
        pay_rows = self.payroll_by_filer.get(fid, [])
        apprentice_total = sum(int(r["apprentice_payroll_cents"])
                               for r in pay_rows)
        payroll_base = (sum(int(r["payroll_cents"]) for r in pay_rows)
                        - apprentice_total)
        exemption = pol.payroll_annual_exemption_cents["value"]
        if f["filer_class"] == "mutual":
            exemption *= pol.mutual_exemption_multiplier["value"]
        prorated = rnd_half_even(
            Fraction(exemption * active_days, pol.days_in_year))
        if f["entity_form"] == "statutory_body":
            payroll_levy = 0                       # section 4-030
        elif payroll_base > prorated:
            payroll_levy = rnd_half_even(
                Fraction((payroll_base - prorated)
                         * pol.payroll_rate_ppm["value"], 1000000))
        else:
            payroll_levy = 0

        # ---- Part 5 ------------------------------------------------------
        energy_gross = 0
        for r in self.energy_by_filer.get(fid, []):
            mc = pol.energy_rates[r["fuel"]][r["quarter"]]["value"]
            energy_gross += rnd_half_even(Fraction(int(r["kwh"]) * mc, 1000))
        energy_levy = energy_gross
        if band == "III":
            energy_levy = energy_gross - rnd_half_even(
                Fraction(energy_gross
                         * pol.band_iii_energy_reduction_percent["value"],
                         100))

        # ---- Part 6 ------------------------------------------------------
        base_levy = activity_levy + floor_levy
        rate_ppm = pol.regional_surcharge_ppm[dinfo["region"]]["value"]
        if dinfo["coastal"]:
            rate_ppm += pol.coastal_supplement_ppm["value"]
        surcharge = rnd_half_even(Fraction(base_levy * rate_ppm, 1000000))

        primary_levy = base_levy + surcharge
        gross_levy = primary_levy + payroll_levy + energy_levy

        # ---- Parts 9 and 10 ----------------------------------------------
        applied, cf_out, credits_total = self._credits(
            f, fid, band, dinfo, ests, est_spans, se_applied,
            apprentice_total, sum(l["_export"] for l in lines),
            primary_levy, gross_levy, payroll_levy, energy_levy)

        # ---- Part 11 -----------------------------------------------------
        min_levy = pol.minimum_levy_cents[f["entity_form"]]["value"]
        if pol.minimum_levy_prorated:            # Binding Ruling BR 2026/05
            min_levy = rnd_half_even(
                Fraction(min_levy * active_days, pol.days_in_year))
        after_credits = gross_levy - credits_total
        topup = min_levy - after_credits if after_credits < min_levy else 0
        net_levy = after_credits + topup

        # ---- Part 12 -----------------------------------------------------
        instalments, payments_total, interest_total, balance = \
            self._instalments(fid, net_levy)

        return {
            "filer_id": fid,
            "filer_class": f["filer_class"],
            "entity_form": f["entity_form"],
            "principal_district": principal,
            "active_days": active_days,
            "predominant_class": predominant,
            "band": band,
            "small_enterprise_applied": se_applied,
            "activity_lines": [
                {"establishment_id": l["establishment_id"],
                 "reported_code": l["reported_code"],
                 "assessed_code": l["assessed_code"],
                 "quarter": l["quarter"],
                 "assessable_cents": l["assessable_cents"],
                 "rate_ppm": l["rate_ppm"],
                 "levy_cents": l["levy_cents"]} for l in lines],
            "activity_levy_cents": activity_levy,
            "floor_levy_cents": floor_levy,
            "payroll_levy_cents": payroll_levy,
            "energy_levy_cents": energy_levy,
            "surcharge_cents": surcharge,
            "primary_levy_cents": primary_levy,
            "gross_levy_cents": gross_levy,
            "credits_applied": applied,
            "credits_total_cents": credits_total,
            "carryforward_out": cf_out,
            "minimum_levy_cents": min_levy,
            "minimum_topup_cents": topup,
            "net_levy_cents": net_levy,
            "instalments": instalments,
            "payments_cents": payments_total,
            "interest_cents": interest_total,
            "balance_cents": balance,
        }, dinfo["region"]

    # -- eligibility for each credit of the Code ---------------------------
    def _eligible(self, code, f, band, dinfo, ests, est_spans, se_applied):
        pol = self.pol
        cls, form = f["filer_class"], f["entity_form"]
        if code == "K-11":      # section 4-060(2)
            return cls in ("commercial", "mutual") and form != "statutory_body"
        if code == "K-03":      # section 5-040(2)
            return band in ("I", "II")
        if code == "K-12":      # section 7-143(2)
            return dinfo["coastal"]
        if code == "K-05":      # section 9-104(b)
            return cls == "public"
        if code == "K-07":      # section 9-109(b)
            return cls == "mutual" or form == "cooperative"
        if code == "K-09":      # section 9-112(b)
            return True
        if code == "K-02":      # section 9-118(b)
            for e in ests:
                lo, hi = est_spans[e["establishment_id"]]
                if hi >= lo and pol.districts[e["district"]]["edz"]:
                    return True
            return False
        if code == "K-06":      # section 9-125(b)
            return True
        if code == "K-04":      # section 9-131(b)
            return cls == "commercial" and form == "company"
        if code == "K-01":      # section 9-140(b)
            return se_applied
        if code == "K-10":      # section 9-147(b)
            return dinfo["edz"] and not dinfo["coastal"]
        if code == "K-08":      # section 9-152(b)
            return band in ("II", "III")
        return False

    def _credits(self, f, fid, band, dinfo, ests, est_spans, se_applied,
                 apprentice_total, export_total, primary_levy, gross_levy,
                 payroll_levy, energy_levy):
        pol = self.pol
        year = pol.year
        eligible = {c["credit_code"]: self._eligible(
            c["credit_code"], f, band, dinfo, ests, est_spans, se_applied)
            for c in pol.credits}

        # claim records: sections 7-346 and 9-006(2)
        claimed = {}
        ineligible = set()
        for cl in sorted(self.claims_by_filer.get(fid, []),
                         key=lambda x: x["claim_id"]):
            code = cl["credit_code"]
            cred = pol.credit_by_code.get(code)
            if cred is None:
                self.issues.append(
                    "%s: claim %s under %s disregarded: no such credit"
                    % (fid, cl["claim_id"], code))
            elif not cred["_on_claim"]:
                self.issues.append(
                    "%s: claim %s under %s disregarded: credit arises "
                    "without claim" % (fid, cl["claim_id"], code))
            elif not eligible[code]:
                ineligible.add(code)
            else:
                claimed[code] = (claimed.get(code, 0)
                                 + int(cl["expenditure_cents"]))
        for code in sorted(ineligible):
            self.issues.append(
                "%s: claim under %s disregarded: filer not eligible"
                % (fid, code))

        # carried-forward amounts: sections 10-003 and 10-004
        carried = {}
        for cf in sorted(self.cf_by_filer.get(fid, []),
                         key=lambda x: (x["credit_code"], x["origin_year"])):
            code, oy = cf["credit_code"], int(cf["origin_year"])
            cred = pol.credit_by_code.get(code)
            if cred is None or cred["carry_years"]["value"] == 0:
                self.issues.append(
                    "%s: carryforward %s/%s disregarded: not permitted"
                    % (fid, code, cf["origin_year"]))
                continue
            if oy + cred["carry_years"]["value"] < year:
                self.issues.append(
                    "%s: carryforward %s/%s disregarded: expired"
                    % (fid, code, cf["origin_year"]))
                continue
            if pol.carryforward_needs_eligibility and not eligible[code]:
                continue
            carried.setdefault(code, {})
            carried[code][oy] = (carried[code].get(oy, 0)
                                 + int(cf["remaining_cents"]))

        basis = {"primary_levy": primary_levy, "gross_levy": gross_levy,
                 "payroll_levy": payroll_levy, "energy_levy": energy_levy}
        global_remaining = rnd_half_even(
            Fraction(gross_levy * pol.global_credit_cap_percent["value"], 100))
        gross_remaining = gross_levy
        applied, cf_out, total = [], [], 0
        for c in pol.credits:
            code, cap = c["credit_code"], c["cap"]
            limit = (cap["amount"] if cap["basis"] == "fixed"
                     else rnd_half_even(Fraction(basis[cap["basis"]]
                                                 * cap["amount"], 1000000)))
            amounts = [(oy, carried[code][oy])
                       for oy in sorted(carried.get(code, {}))]
            cur = 0
            if eligible[code]:
                if c["_on_claim"]:
                    if code in claimed:
                        cur = rnd_half_even(
                            Fraction(claimed[code] * c["rate_ppm"]["value"],
                                     1000000))
                else:
                    base = (apprentice_total
                            if c["_base"] == "apprentice_payroll"
                            else export_total)
                    cur = rnd_half_even(
                        Fraction(base * c["rate_ppm"]["value"], 1000000))
            if cur:
                amounts.append((year, cur))
            for oy, avail in amounts:
                use = max(0, min(avail, limit, gross_remaining,
                                 global_remaining))
                if use:
                    applied.append({"credit_code": code, "origin_year": oy,
                                    "applied_cents": use})
                    limit -= use
                    gross_remaining -= use
                    global_remaining -= use
                    total += use
                left = avail - use
                if left > 0 and oy + c["carry_years"]["value"] >= year + 1:
                    cf_out.append({"credit_code": code, "origin_year": oy,
                                   "remaining_cents": left})
        cf_out.sort(key=lambda x: (x["credit_code"], x["origin_year"]))
        return applied, cf_out, total

    # -- Part 12 -----------------------------------------------------------
    def _instalments(self, fid, net_levy):
        pol = self.pol
        adate = self.batch.assessment_date
        base = (net_levy // 4 if net_levy >= 0
                else -((-net_levy) // 4))          # section 12-001(2)
        amounts = [base, base, base, net_levy - 3 * base]
        inst = [{"quarter": q,
                 "due": pol.instalment_due_dates[q],
                 "amount_cents": amounts[i],
                 "unpaid": amounts[i],
                 "paid_cents": 0,
                 "interest_cents": 0} for i, q in enumerate(QUARTERS)]
        rows = []
        for p in self.pay_by_filer.get(fid, []):
            pd = pdate(p["paid_on"])
            if pd > adate:                         # section 12-010(2)
                self.issues.append(
                    "%s: payment %s dated after the assessment date "
                    "disregarded" % (fid, p["payment_id"]))
                continue
            rows.append((pd, p["payment_id"], int(p["amount_cents"])))
        rows.sort(key=lambda t: (t[0], t[1]))      # section 12-010(1)
        payments_total = sum(r[2] for r in rows)
        for pd, _pid, amount in rows:              # section 12-012
            left = amount
            for it in inst:
                if left <= 0:
                    break
                if it["unpaid"] <= 0:
                    continue
                use = min(left, it["unpaid"])
                it["unpaid"] -= use
                it["paid_cents"] += use
                left -= use
                if pd > it["due"]:                 # section 12-030(1)
                    it["interest_cents"] += self._interest(use, it["due"], pd)
        for it in inst:                            # section 12-030(2)
            if it["unpaid"] > 0 and adate > it["due"]:
                it["interest_cents"] += self._interest(
                    it["unpaid"], it["due"], adate)
        interest_total = sum(it["interest_cents"] for it in inst)
        out = [{"quarter": it["quarter"], "due_date": it["due"].isoformat(),
                "amount_cents": it["amount_cents"],
                "paid_cents": it["paid_cents"],
                "interest_cents": it["interest_cents"]} for it in inst]
        return (out, payments_total, interest_total,
                net_levy + interest_total - payments_total)

    def _interest(self, part, due, upto):
        """Sections 12-030 and 12-040: the interest on each part is a single
        amount, rounded with a half rounded up."""
        pol = self.pol
        total = Fraction(0)
        d = due + timedelta(days=1)
        while d <= upto:
            total += Fraction(part * pol.interest_rate_ppm(d),
                              1000000 * pol.days_in_year)
            d += timedelta(days=1)
        return rnd_half_up(total)


# ----------------------------------------------------------------------------
# the statements
# ----------------------------------------------------------------------------


def totals_of(rows):
    return {k: sum(r[k] for r in rows) for k in TOTAL_KEYS}


def dump(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, indent=2, sort_keys=True))
        fh.write("\n")


def policy_audit(pol, batch):
    return {
        "report_id": batch.batch_id,
        "residual_class": pol.residual_class,
        "activity_classes": {
            code: {"band": pol.classes[code]["band"],
                   "export_excluded": pol.classes[code]["export_excluded"],
                   "rates_ppm": {q: pol.class_rates[code][q]
                                 for q in QUARTERS}}
            for code in pol.classes},
        "districts": {
            code: {"region": info["region"], "coastal": info["coastal"],
                   "edz": info["edz"],
                   "rate_periods": [
                       {"from": p[0].isoformat(), "to": p[1].isoformat(),
                        "rate_cents_per_m2": p[2], "authority": p[3]}
                       for p in pol.district_periods[code]]}
            for code, info in pol.districts.items()},
        "regional_surcharge_ppm": pol.regional_surcharge_ppm,
        "coastal_supplement_ppm": pol.coastal_supplement_ppm,
        "public_floor_factor_percent": pol.public_floor_factor_percent,
        "payroll_rate_ppm": pol.payroll_rate_ppm,
        "payroll_annual_exemption_cents": pol.payroll_annual_exemption_cents,
        "mutual_exemption_multiplier": pol.mutual_exemption_multiplier,
        "band_iii_energy_reduction_percent":
            pol.band_iii_energy_reduction_percent,
        "small_enterprise_threshold_cents":
            pol.small_enterprise_threshold_cents,
        "small_enterprise_rate_factor_percent":
            pol.small_enterprise_rate_factor_percent,
        "global_credit_cap_percent": pol.global_credit_cap_percent,
        "energy_rates_millicents_per_kwh": {
            fuel: {q: pol.energy_rates[fuel][q] for q in QUARTERS}
            for fuel in pol.energy_rates},
        "credits": [{"credit_code": c["credit_code"], "section": c["section"],
                     "rate_ppm": c["rate_ppm"], "cap": c["cap"],
                     "carry_years": c["carry_years"]} for c in pol.credits],
        "minimum_levy_cents": pol.minimum_levy_cents,
        "interest_rate_periods": [
            {"from": p["from"].isoformat(),
             "to": p["to"].isoformat() if p["to"] else None,
             "rate_ppm": p["rate_ppm"], "authority": p["authority"]}
            for p in pol.interest_periods],
        "instalment_due_dates": {q: pol.instalment_due_dates[q].isoformat()
                                 for q in QUARTERS},
    }


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py <DATA_DIR> <OUT_DIR>\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)

    sections, order = load_code(os.path.join(data_dir, "levy_code.md"))
    apply_text_modifications(sections, order)
    pol = Policy(sections, order)
    batch = Batch(data_dir)
    assessor = Assessor(pol, batch)

    assessments, region_of = [], {}
    for f in sorted(batch.filers, key=lambda x: x["filer_id"]):
        a, region = assessor.assess(f)
        assessments.append(a)
        region_of[a["filer_id"]] = region

    class_counts = {c: 0 for c in ("commercial", "mutual", "public")}
    for f in batch.filers:
        class_counts[f["filer_class"]] = class_counts.get(
            f["filer_class"], 0) + 1
    status = {"balance_due": 0, "settled": 0, "credit_balance": 0}
    for a in assessments:
        if a["balance_cents"] > 0:
            status["balance_due"] += 1
        elif a["balance_cents"] == 0:
            status["settled"] += 1
        else:
            status["credit_balance"] += 1
    by_region = {r: [a for a in assessments if region_of[a["filer_id"]] == r]
                 for r in REGIONS}

    dump(os.path.join(out_dir, "summary.json"), {
        "report_id": batch.batch_id,
        "assessment_date": batch.assessment_date.isoformat(),
        "filer_count": len(assessments),
        "totals": totals_of(assessments),
        "region_totals": {r: totals_of(by_region[r]) for r in REGIONS},
        "class_filer_counts": class_counts,
        "balance_status_counts": status,
    })

    for r in REGIONS:
        rows = by_region[r]
        dump(os.path.join(out_dir, "region_%s.json" % r),
             {"region": r, "filer_count": len(rows),
              "totals": totals_of(rows), "filers": rows})

    for seg in ("commercial", "public"):
        rows = [a for a in assessments if a["filer_class"] == seg]
        credit_totals = {}
        for a in rows:
            for c in a["credits_applied"]:
                credit_totals[c["credit_code"]] = (
                    credit_totals.get(c["credit_code"], 0)
                    + c["applied_cents"])
        dump(os.path.join(out_dir, "segment_%s.json" % seg),
             {"segment": seg, "filer_count": len(rows),
              "totals": totals_of(rows), "credit_totals": credit_totals,
              "filer_ids": [a["filer_id"] for a in rows]})

    issues = sorted(assessor.issues)
    dump(os.path.join(out_dir, "data_quality.json"), {
        "input_file_count": batch.file_count,
        "filer_count": len(batch.filers),
        "establishment_count": len(batch.establishments),
        "receipts_line_count": len(batch.receipts),
        "payroll_row_count": len(batch.payroll),
        "energy_row_count": len(batch.energy),
        "claim_count": len(batch.claims),
        "carryforward_count": len(batch.carryforwards),
        "payment_count": len(batch.payments),
        "quality_issue_count": len(issues),
        "quality_issues": issues,
    })

    dump(os.path.join(out_dir, "policy_audit.json"), policy_audit(pol, batch))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
