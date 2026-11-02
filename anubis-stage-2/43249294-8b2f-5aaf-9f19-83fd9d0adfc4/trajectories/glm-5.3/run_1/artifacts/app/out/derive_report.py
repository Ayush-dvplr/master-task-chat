#!/usr/bin/env python3
"""Derive the assessment statements of a Vellmouth 2026 billing batch.

Usage: python3 derive_report.py <DATA_DIR> <OUT_DIR>

Every rate, allowance, factor, limit, priority, period, designation, date and
method is read out of the Code in <DATA_DIR>/tariff_code.md and applied in the
order fixed by section 1-006 of the Code.  All money and volume arithmetic uses
integers and fractions.Fraction only.
"""

import csv
import json
import os
import re
import sys
from datetime import date, timedelta
from fractions import Fraction

# ---------------------------------------------------------------------------
# exact arithmetic helpers
# ---------------------------------------------------------------------------


def half_even(f):
    """Round a Fraction to the nearest whole number, ties to even."""
    n, d = f.numerator, f.denominator
    q, r = divmod(n, d)
    r2 = r * 2
    if r2 < d:
        return q
    if r2 > d:
        return q + 1
    return q if q % 2 == 0 else q + 1


def half_up(f):
    """Round a Fraction to the nearest whole number, ties up."""
    n, d = f.numerator, f.denominator
    return (2 * n + d) // (2 * d)


# ---------------------------------------------------------------------------
# number words
# ---------------------------------------------------------------------------

_NUMWORDS = {
    'no': 0, 'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
    'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14,
    'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
    'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
    'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90,
}


def word_to_int(word):
    word = word.strip().lower()
    if word in _NUMWORDS:
        return _NUMWORDS[word]
    if '-' in word:
        total = 0
        for part in word.split('-'):
            total += _NUMWORDS[part]
        return total
    m = re.match(r'^(\d+)$', word)
    if m:
        return int(m.group(1))
    raise ValueError('unknown number word %r' % word)


# ---------------------------------------------------------------------------
# Code parsing
# ---------------------------------------------------------------------------

MONTHS = {
    'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5,
    'June': 6, 'July': 7, 'August': 8, 'September': 9, 'October': 10,
    'November': 11, 'December': 12,
}

RE_SEC = re.compile(r'^### Section (\d+-\d+)\. (.*)$')
RE_UNIT_N = re.compile(r'^\((\d+)\)\s+(.*)$')
RE_UNIT_P = re.compile(r'^\(([a-z]+)\)\s+(.*)$')

def parse_date(s):
    """'11 August 2026' or '2026-08-11' -> date."""
    s = s.strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    parts = s.split()
    return date(int(parts[2]), MONTHS[parts[1]], int(parts[0]))


class Code(object):
    """The text of the Code, split into addressable units."""

    def __init__(self, text):
        self.units = {}          # '2-113(d)(iii)' -> text (None if repealed)
        self.unit_section = {}   # unit -> '2-113'
        self.headings = {}       # section -> heading text
        self.section_text = {}   # section -> whole body text
        self.section_extra = {}
        self.order = []
        self._parse(text)

    def _parse(self, text):
        """Read the Code into addressable units.

        A unit is a subsection such as '9-120(3)', a paragraph such as
        '2-113(d)', a paragraph of a subsection such as '6-020(2)(c)' or a
        sub-paragraph such as '2-113(d)(iii)'.
        """
        bodies = {}
        heads = []
        cur = None
        acc = []
        for raw in text.split('\n'):
            if raw.startswith('#'):
                if cur is not None:
                    bodies[cur] = acc
                m = RE_SEC.match(raw)
                cur = m.group(1) if m else None
                if cur is not None:
                    self.headings[cur] = m.group(2)
                    self.order.append(cur)
                acc = []
                continue
            if cur is None:
                continue
            acc.append(raw)
        if cur is not None:
            bodies[cur] = acc

        for sec in self.order:
            lines = []
            for raw in bodies[sec]:
                t = raw.strip()
                if not t or t.startswith('Note:'):
                    continue
                if t.startswith('Designation:'):
                    self.section_extra[sec] = t
                    continue
                lines.append(t)
            self.section_text[sec] = '\n'.join(lines)
            toks = []
            for t in lines:
                m = RE_UNIT_N.match(t)
                if m:
                    toks.append(['num', m.group(1), m.group(2)])
                    continue
                m = RE_UNIT_P.match(t)
                if m:
                    toks.append(['tok', m.group(1), m.group(2)])
                    continue
                toks.append(['cont', None, t])
            self._classify(toks)
            num = let = rom = None
            for kind, tok, body in toks:
                if kind == 'num':
                    num, let, rom = tok, None, None
                    self._put(sec, '%s(%s)' % (sec, num), body)
                elif kind == 'sub':
                    rom = tok
                    base = self._base(sec, num, let)
                    self._put(sec, '%s(%s)' % (base, rom), body)
                elif kind == 'tok':
                    let, rom = tok, None
                    self._put(sec, self._base(sec, num, let), body)
                else:
                    if rom is not None:
                        base = self._base(sec, num, let)
                        ref = '%s(%s)' % (base, rom)
                    elif let is not None:
                        ref = self._base(sec, num, let)
                    elif num is not None:
                        ref = '%s(%s)' % (sec, num)
                    else:
                        ref = None
                    if ref is not None and ref in self.units:
                        self.units[ref] += ' ' + body

    @staticmethod
    def _classify(toks):
        """Mark roman-numeral tokens that are sub-paragraphs, not paragraphs."""
        subs = set()
        for i, item in enumerate(toks):
            if item[0] != 'tok' or item[1] not in ROMAN_TOKENS:
                continue
            prev = toks[i - 1] if i else None
            chained = prev is not None and prev[0] == 'sub'
            colon = prev is not None and prev[0] == 'tok' and \
                prev[2].rstrip().endswith(':')
            later = any(t[0] == 'tok' and len(t[1]) == 1 and t[1] < item[1]
                        for t in toks[i + 1:])
            if chained or colon or later:
                subs.add(i)
        for i in subs:
            toks[i][0] = 'sub'

    @staticmethod
    def _base(sec, num, let):
        if num is not None and let is not None:
            return '%s(%s)(%s)' % (sec, num, let)
        if let is not None:
            return '%s(%s)' % (sec, let)
        return sec

    def _put(self, section, ref, text):
        self.units[ref] = text
        self.unit_section[ref] = section

    def replace(self, ref, old, new):
        t = self.units.get(ref)
        if t is None or old not in t:
            return False
        self.units[ref] = t.replace(old, new, 1)
        return True

    def omit(self, ref, old):
        t = self.units.get(ref)
        if t is None or old not in t:
            return False
        self.units[ref] = t.replace(old, '', 1)
        return True

    def insert_after(self, ref, anchor, new):
        t = self.units.get(ref)
        if t is None or anchor not in t:
            return False
        self.units[ref] = t.replace(anchor, anchor + new, 1)
        return True

    def repeal(self, ref):
        self.units[ref] = None


# ---------------------------------------------------------------------------
# figure parsing
# ---------------------------------------------------------------------------


def money_units(s):
    """'$2.3070' or '2.3070' -> 23070 (units of $0.0001)."""
    m = re.search(r'([0-9][0-9,]*)\.([0-9]+)', s)
    if not m:
        raise ValueError('no money figure in %r' % s)
    frac = m.group(2)
    if len(frac) < 4:
        frac = frac + '0' * (4 - len(frac))
    return int(m.group(1).replace(',', '') + frac[:4])


def cents_of(s):
    """'$260.00' -> 26000 cents."""
    m = re.search(r'([0-9][0-9,]*)\.([0-9]{2})(?![0-9])', s)
    return int(m.group(1).replace(',', '')) * 100 + int(m.group(2))


def ppm_of(s):
    """'4.2500 per cent' or '4.2500' -> 42500 parts per million."""
    m = re.search(r'([0-9]+)\.([0-9]{4})', s)
    return int(m.group(1) + m.group(2))


def percent_of(s):
    """'40 per cent' or '40' -> 40."""
    m = re.search(r'([0-9]+)', s)
    return int(m.group(1))


def litres_of(s):
    """'450' or '450 litres' -> 450."""
    m = re.search(r'([0-9][0-9,]*)', s)
    return int(m.group(1).replace(',', ''))


# ---------------------------------------------------------------------------
# value keys
#
#   ('block', class, n)        water supply block rate of a class
#   ('band', class)            band of a class
#   ('discharge', class)       discharge factor (per cent) of a class
#   ('catch', class)           catchment levy exemption (bool) of a class
#   ('drought', zone)          Drought Zone designation (bool) of a zone
#   ('ww', zone)               wastewater charge rate of a zone
#   ('sw', zone)               stormwater charge rate of a zone
#   ('region', zone)           region of a zone
#   ('allow', band, part)      daily allowance of a band ('b1' or 'b2')
#   ('svc', size)              daily service charge of a meter size
#   ('surcharge', region)      regional surcharge rate (ppm)
#   ('droughtsup',)            drought supplement (ppm)
#   ('catchlevy',)             catchment levy (ppm)
#   ('twvol',) ('twload',)     trade waste volume / load charge
#   ('globalcap',)             overall limit on rebates (per cent)
#   ('minimum', aclass)        minimum annual charge (cents)
#   ('grace',)                 period of grace (days)
#   ('interest',)              interest rate (ppm)
#   ('rebate', code, attr)     rebate attribute
# ---------------------------------------------------------------------------

ROMAN = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4}
ROMAN_TOKENS = frozenset(('i', 'ii', 'iii', 'iv', 'v', 'vi'))

REBATE_ATTR_SUB = {2: 'priority', 3: 'eligibility', 4: 'amount',
                   5: 'limit', 6: 'carry', 7: 'exclusion'}

REBATE_SUB_OF_ATTR = {v: k for k, v in REBATE_ATTR_SUB.items()}


class Unknown(Exception):
    pass


class Policy(object):
    """The Code reduced to the values in force."""

    def __init__(self, code):
        self.code = code
        self.tariff_start = None
        self.tariff_end = None
        self.holidays = set()
        self.quarters = {}
        self.due_dates = {}
        self.establishing = {}   # rebate code -> establishing section
        self.values = {}         # key -> (value, authority)
        self.segments = {}       # key -> [(from, to|None, value, authority)]
        self._scan_structural()
        self._scan_schedules()
        self._scan_rebates()
        self._base_values()
        self.corrections = self._collect_corrections()
        self._apply_corrections(self.corrections)
        self._base_values_post()
        self._apply_displacements()
        amendments = self._collect_amendments()
        self._apply_amendments(amendments)
        for key in self.values:
            if key not in self.segments:
                start, end = self.horizon(key)
                self.segments[key] = [(start, end, self.values[key][0],
                                       self.values[key][1])]

    # -- structural provisions -------------------------------------------

    def _scan_structural(self):
        c = self.code
        t = c.units.get('1-224(1)', '')
        m = re.search(r'beginning on (\d+ \w+ \d+) and ending on (\d+ \w+ \d+)', t)
        self.tariff_start = parse_date(m.group(1))
        self.tariff_end = parse_date(m.group(2))
        for d in re.findall(r'(\d+ \w+ \d+)', c.units.get('1-090(1)', '')):
            self.holidays.add(parse_date(d))
        t = c.units.get('1-092(1)', '')
        mm = re.search(r'first quarter of the tariff year is (\w+) to (\w+), '
                      r'the second quarter is (\w+) to (\w+), '
                      r'the third quarter is (\w+) to (\w+) and '
                      r'the fourth quarter is (\w+) to (\w+)', t)
        if mm:
            self.quarters = {}
            for i, q in enumerate(('Q1', 'Q2', 'Q3', 'Q4')):
                self.quarters[q] = (MONTHS[mm.group(1 + 2 * i)],
                                    MONTHS[mm.group(2 + 2 * i)])
        else:
            self.quarters = {'Q1': (1, 3), 'Q2': (4, 6),
                             'Q3': (7, 9), 'Q4': (10, 12)}
        t = c.units.get('12-010(3)', '')
        ds = re.findall(r'(\d+ \w+ \d+)', t)
        for q, d in zip(('Q1', 'Q2', 'Q3', 'Q4'), ds):
            self.due_dates[q] = self.next_business_day(parse_date(d))

    def next_business_day(self, d):
        while not self.is_business_day(d):
            d = d + timedelta(days=1)
        return d

    def is_business_day(self, d):
        return d.weekday() < 5 and d not in self.holidays

    def quarter_bounds(self, q):
        a, b = self.quarters[q]
        y = self.tariff_start.year
        s = date(y, a, 1)
        e = date(y, b, 1)
        if b == 12:
            e = date(y + 1, 1, 1)
        return s, (e - timedelta(days=1))

    # -- rebates ----------------------------------------------------------

    def _scan_schedules(self):
        """Map the class and zone codes of the registers to sections."""
        self.class_section = {}
        self.zone_section = {}
        for s in self.code.order:
            head = self.code.headings.get(s, '')
            m = re.match(r'^Class (TC-\d+):', head)
            if m:
                self.class_section[m.group(1)] = s
            m = re.match(r'^Zone (Z-\d+):', head)
            if m:
                self.zone_section[m.group(1)] = s

    def _scan_rebates(self):
        for s in self.code.order:
            body = self.code.section_text.get(s, '')
            for m in re.finditer(r'[Ee]stablishment\.\s+This section '
                                 r'establishes the ([^,.]+?), identified by '
                                 r'rebate code (RB-\d+)[.,]', body):
                self.establishing[m.group(2)] = s

    # -- the value a unit reference fixes --------------------------------

    def key_of_ref(self, ref):
        """Map a unit reference onto [(key, kind), ...]."""
        m = re.match(r'^(\d+-\d+)((?:\([a-z0-9]+\))*)$', ref)
        if not m:
            return []
        sec = m.group(1)
        labels = re.findall(r'\(([a-z0-9]+)\)', m.group(2))
        part = int(sec.split('-')[0])
        num = sec.split('-')[1]
        keys = []

        def add(key, kind):
            keys.append((key, kind))

        if part == 2 and re.match(r'^\d\d\d$', num) and \
                len(labels) == 2 and labels[1] in ROMAN and \
                labels[0] not in ROMAN:
            add(('block', sec, ROMAN[labels[1]]), 'rate')
        elif part in (2, 3) and re.match(r'^\d\d\d$', num) and \
                len(labels) == 1:
            # an entry of Schedule 2 or Schedule 3
            tag = labels[0]
            if part == 2:
                if tag == 'e':
                    add(('catch', sec), 'boolcatch')
                elif tag == 'f':
                    add(('band', sec), 'band')
                elif tag == 'g':
                    add(('discharge', sec), 'percent')
            else:
                if tag == 'c':
                    add(('drought', sec), 'booldrought')
                elif tag == 'd':
                    add(('ww', sec), 'rate')
                elif tag == 'e':
                    add(('sw', sec), 'rate')
                elif tag == 'b':
                    add(('region', sec), 'region')
        elif sec == '4-020' and labels == ['2', 'a']:
            add(('allow', 'A', 'b1'), 'litres')
            add(('allow', 'A', 'b2'), 'litres_b2')
        elif sec == '4-020' and labels == ['2', 'b']:
            add(('allow', 'B', 'b1'), 'litres')
            add(('allow', 'B', 'b2'), 'litres_b2')
        elif sec == '4-020' and labels == ['2', 'c']:
            add(('allow', 'C', 'b1'), 'litres')
            add(('allow', 'C', 'b2'), 'litres_b2')
        elif sec == '6-020' and len(labels) == 2 and labels[0] == '2':
            ms = re.match(r'^for a meter of (\d+) mm',
                          self.code.units.get(ref, ''))
            add(('svc', int(ms.group(1))), 'rate')
        elif sec == '5-110' and labels == ['2', 'a']:
            add(('twvol',), 'rate')
        elif sec == '5-110' and labels == ['2', 'b']:
            add(('twload',), 'rate')
        elif sec == '7-010' and len(labels) == 2 and labels[0] == '1':
            mr = re.match(r'^for the (North|South|West|East) region',
                          self.code.units.get(ref, ''))
            add(('surcharge', mr.group(1)), 'ppm')
        elif sec == '7-020' and labels == ['1']:
            add(('droughtsup',), 'ppm')
        elif sec == '5-210' and labels == ['2']:
            add(('catchlevy',), 'ppm')
        elif sec == '9-002' and labels == ['1']:
            add(('globalcap',), 'percent')
        elif sec == '11-010' and labels == ['1', 'a']:
            add(('minimum', 'residential'), 'cents')
        elif sec == '11-010' and labels == ['1', 'b']:
            add(('minimum', 'commercial'), 'cents')
        elif sec == '11-010' and labels == ['1', 'c']:
            add(('minimum', 'public'), 'cents')
        elif sec == '12-030' and labels == ['2']:
            add(('grace',), 'days')
        elif sec == '12-040' and labels == ['1']:
            add(('interest',), 'ppm')
        else:
            for code, esec in self.establishing.items():
                if sec == esec and len(labels) == 1:
                    attr = REBATE_ATTR_SUB.get(int(labels[0]))
                    if attr:
                        add(('rebate', code, attr), 'rebate_' + attr)
        return keys

    def horizon(self, key):
        if key == ('interest',):
            return (self.tariff_start, None)
        return (self.tariff_start, self.tariff_end)

    # -- extraction ------------------------------------------------------

    def extract(self, key, kind, text):
        if text is None:
            return None
        if kind == 'rate':
            return money_units(text)
        if kind == 'ppm':
            return ppm_of(text)
        if kind == 'percent':
            return percent_of(text)
        if kind == 'cents':
            return cents_of(text)
        if kind == 'litres':
            m = re.search(r'block 1 is the first ([0-9,]+) litres per day',
                          text)
            return litres_of(m.group(1))
        if kind == 'litres_b2':
            m = re.search(r'up to ([0-9,]+) litres per day', text)
            return litres_of(m.group(1))
        if kind == 'band':
            return re.search(r'assigned to Band ([ABC])', text).group(1)
        if kind == 'boolcatch':
            if re.search(r'are\s+not\s+exempt', text):
                return False
            if re.search(r'are\s+exempt', text):
                return True
            return False
        if kind == 'booldrought':
            if re.search(r'is\s+not\s+designated', text):
                return False
            if re.search(r'is\s+designated', text):
                return True
            return False
        if kind == 'region':
            return re.search(r'forms part of the '
                             r'(North|South|West|East) region',
                             text).group(1)
        if kind == 'days':
            return word_to_int(re.search(r'is ([A-Za-z-]+) days', text).group(1))
        if kind.startswith('rebate_'):
            return self.extract_rebate(key, kind[len('rebate_'):], text)
        raise Unknown('cannot extract kind %r' % kind)

    def extract_rebate(self, key, attr, text):
        code = key[1]
        if attr == 'priority':
            return int(re.search(r'priority (\d+)', text).group(1))
        if attr == 'eligibility':
            return self.parse_eligibility(text)
        if attr == 'amount':
            return self.parse_amount(text)
        if attr == 'limit':
            m = re.search(r'must not exceed \$([0-9][0-9,]*\.[0-9]{2})', text)
            if m:
                return ('fixed', cents_of(m.group(1)))
            m = re.search(r'must not exceed ([0-9]+) per cent of', text)
            if m:
                return (self.limit_basis(text), int(m.group(1)))
            return None
        if attr == 'carry':
            if re.search(r'may not be carried forward', text):
                return 0
            m = re.search(r'carried forward for ([A-Za-z-]+) tariff years?',
                          text)
            return word_to_int(m.group(1))
        if attr == 'exclusion':
            if re.search(r'No holder form is excluded', text):
                return []
            forms = [f for f in ('individual', 'partnership', 'company',
                                 'trust', 'association', 'government_body')
                     if re.search(r'\b%s\b' % f, text)]
            return forms
        raise Unknown('rebate attribute %r' % attr)

    def parse_eligibility(self, text):
        """Reduce an eligibility subsection to a testable condition."""
        cond = {'classes': [], 'cards': [], 'drought': False,
                'large': False, 'community': False, 'any': False}
        if re.search(r'\ban account\b', text) and not cond['classes']:
            cond['any'] = True
        for c in ('residential', 'commercial', 'public'):
            if re.search(r'\ba %s account\b' % c, text):
                cond['classes'].append(c)
        if re.search(r'community organisation', text):
            cond['community'] = True
        for card in ('pensioner', 'health', 'veteran'):
            if re.search(r'\ba %s (?:concession |care )?card\b' % card, text):
                cond['cards'].append(card)
        if re.search(r'drought property', text):
            cond['drought'] = True
        if re.search(r'Large Meter', text):
            cond['large'] = True
        return cond

    def parse_amount(self, text):
        """Classify the Amount subsection of a rebate."""
        rate = percent_of(text)
        if re.search(r'of the expenditure claimed', text):
            return {'basis': 'expenditure', 'rate': rate}
        if re.search(r'leak value', text):
            return {'basis': 'leak', 'rate': rate}
        if re.search(r"of the account's Service Charges", text):
            return {'basis': 'service', 'rate': rate}
        if re.search(r"of the account's Water Supply Charges", text):
            return {'basis': 'water', 'rate': rate}
        if re.search(r"daily service charges of the account's Large Meters", text):
            return {'basis': 'largemeter', 'rate': rate}
        raise Unknown('unparsed Amount subsection: %s' % text)

    def limit_basis(self, text):
        if re.search(r"account's Volumetric Charges", text):
            return 'volumetric'
        if re.search(r"account's Water Supply Charges", text):
            return 'water'
        if re.search(r"account's Service Charges", text):
            return 'service'
        if re.search(r"account's Supply Total", text):
            return 'supply'
        if re.search(r"account's Gross Charge", text):
            return 'gross'
        raise Unknown('unparsed limit: %s' % text)

    def _base_values(self):
        self.pre = {}
        for ref in sorted(self.code.units):
            for key, kind in self.key_of_ref(ref):
                try:
                    val = self.extract(key, kind, self.code.units[ref])
                except (Unknown, AttributeError, ValueError, TypeError, IndexError):
                    continue
                if val is None:
                    continue
                self.pre[key] = (val, self.code.unit_section[ref], ref, kind)

    def _collect_corrections(self):
        out = []
        for s in self.code.order:
            if not re.match(r'^15-4\d\d$', s):
                continue
            for n in range(1, 40):
                ref = '%s(%d)' % (s, n)
                t = self.code.units.get(ref)
                if not t:
                    continue
                m = re.match(r"^In section ([^,]+), for '(.*)' read '(.*)'\.$", t)
                if m:
                    out.append((s, ref, m.group(1), m.group(2), m.group(3)))
                elif t.startswith('In the heading to section'):
                    pass
                else:
                    raise Unknown('unparsed correction %s: %s' % (ref, t))
        return out

    def _apply_corrections(self, corrections):
        self.corrected_by = {}
        for sec, cref, ref, old, new in corrections:
            if ref not in self.code.units:
                raise Unknown('correction %s targets unknown unit %s'
                              % (cref, ref))
            before = self.code.units[ref]
            ok = self.code.replace(ref, old, new)
            if not ok:
                raise Unknown('correction %s cannot find %r in %s'
                              % (cref, old, ref))
            if before != self.code.units[ref]:
                self.corrected_by[ref] = sec

    def _base_values_post(self):
        self.values = {}
        for ref in sorted(self.code.units):
            for key, kind in self.key_of_ref(ref):
                try:
                    val = self.extract(key, kind, self.code.units[ref])
                except (Unknown, AttributeError, ValueError, TypeError, IndexError):
                    continue
                pre = self.pre.get(key)
                if pre is None:
                    continue
                if val is None:
                    continue
                auth = pre[1]
                if val != pre[0]:
                    auth = self.corrected_by.get(ref, auth)
                self.values[key] = (val, auth)

    def _apply_displacements(self):
        """Provisions outside Part 15 that displace a value stated elsewhere.

        Section 1-006(3) makes them part of the original text: each displaces
        the value it names for the whole tariff year.
        """
        found = set()
        for s in self.code.order:
            part = int(s.split('-')[0])
            if part in (15, 16):
                continue
            body = self.code.section_text.get(s, '')
            for m in re.finditer(r'section (5-210\(\d+\))[^.]*?taken to '
                                 r'be ([0-9]+\.[0-9]{4}) per cent', body):
                self.values[('catchlevy',)] = (ppm_of(m.group(2)), s)
                found.add('catchlevy')
            for m in re.finditer(r'section 7-010[^.]*?each regional rate '
                                 r'stated in that section[^.]*?increased by '
                                 r'([0-9]+\.[0-9]{4}) percentage points', body):
                add = ppm_of(m.group(1))
                for reg in ('North', 'South', 'West', 'East'):
                    base = self.values[('surcharge', reg)][0]
                    self.values[('surcharge', reg)] = (base + add, s)
                found.add('surcharge')
            for m in re.finditer(r'section (6-020\(\d\)\([a-z]\))[^.]*?'
                                 r'for a meter of (\d+) mm[^.]*?as if it '
                                 r'were \$([0-9.]+)', body):
                self.values[('svc', int(m.group(2)))] = (
                    money_units(m.group(3)), s)
                found.add('svc')
            for m in re.finditer(r'section 4-020[^.]*?the block 1 allowance '
                                 r'for Band ([ABC]) is ([0-9,]+) litres per '
                                 r'day', body):
                self.values[('allow', m.group(1), 'b1')] = (
                    litres_of(m.group(2)), s)
                found.add('allow')
        for name in ('catchlevy', 'surcharge', 'svc', 'allow'):
            if name not in found:
                raise Unknown('displacement of %s not found in the Code'
                              % name)
        self._check_displacements()

    def _check_displacements(self):
        """Fail loudly if the Code contains a displacement we do not apply."""
        for s in self.code.order:
            part = int(s.split('-')[0])
            if part in (15, 16, 7):
                continue
            body = self.code.section_text.get(s, '')
            for m in re.finditer(r'(taken to be|has effect as if it were|'
                                 r'is increased by|is reduced by)', body):
                span = body[max(0, m.start() - 220):m.end() + 220]
                if not re.search(r'\$[0-9]|[0-9]+\.[0-9]{4} per cent|'
                                 r'[0-9,]+ litres|Band [ABC]|'
                                 r'percentage points', span):
                    continue
                if re.search(r'taken to be given|taken to be lodged|'
                             r'taken to be valid|taken to be served|'
                             r'taken to be made|as if it were lodged|'
                             r'as if it were served|as if it were given|'
                             r'is increased by a further|'
                             r'has effect as if it were lodged', span):
                    continue
                if s in ('8-047', '13-062', '13-118', '14-031'):
                    continue
                raise Unknown('possible displacement in %s: %s'
                              % (s, span[:160]))

    # -- amendments ------------------------------------------------------

    def _collect_amendments(self):
        out = []
        for s in self.code.order:
            m = re.match(r'^15-(\d\d\d)$', s)
            if not m or not (101 <= int(m.group(1)) <= 288):
                continue
            made = None
            for n in range(1, 40):
                ref = '%s(%d)' % (s, n)
                t = self.code.units.get(ref)
                if not t:
                    continue
                mm = re.match(r'^This section was made on (\d+ \w+ \d+)\.$', t)
                if mm:
                    made = parse_date(mm.group(1))
            if made is None:
                raise Unknown('no day of making in %s' % s)
            for n in range(1, 40):
                ref = '%s(%d)' % (s, n)
                t = self.code.units.get(ref)
                if not t:
                    continue
                parsed = self._parse_amendment(ref, t)
                if parsed is not None:
                    parsed['made'] = made
                    parsed['section'] = s
                    parsed['subsection'] = n
                    parsed['ref'] = ref
                    parsed['text'] = t
                    out.append(parsed)
        out.sort(key=lambda a: (a['made'], a['section'], a['subsection']))
        return out

    def _parse_amendment(self, ref, t):
        m = re.match(r"^With effect from (\d+ \w+ \d+), in section ([^,]+), "
                     r"for '(.*)' substitute '(.*)'\.$", t)
        if m:
            return {'kind': 'subst', 'target': m.group(2), 'old': m.group(3),
                    'new': m.group(4), 'period': (parse_date(m.group(1)), None)}
        m = re.match(r"^In section ([^,]+), for '(.*)' substitute '(.*)'\.$", t)
        if m:
            return {'kind': 'subst', 'target': m.group(1), 'old': m.group(2),
                    'new': m.group(3), 'period': None}
        m = re.match(r"^In section ([^,]+), omit '(.*)'\.$", t)
        if m:
            return {'kind': 'omit', 'target': m.group(1), 'old': m.group(2),
                    'period': None}
        m = re.match(r"^In section ([^,]+), after '(.*)' insert '(.*)'\.$", t)
        if m:
            return {'kind': 'insert', 'target': m.group(1),
                    'anchor': m.group(2), 'new': m.group(3), 'period': None}
        m = re.match(r'^(Subsection|Paragraph) \((\w+)\) of section '
                     r'(\d+-\d+) is repealed\.$', t)
        if m:
            return {'kind': 'repeal',
                    'target': '%s(%s)' % (m.group(3), m.group(2)),
                    'period': None}
        m = re.match(r'^For the period from (\d+ \w+ \d+) to (\d+ \w+ \d+), '
                     r'the .*? under section ([^,]+?) is \$([0-9.]+)'
                     r'(?: per kilolitre| per kilogram)?\.$', t)
        if m:
            return {'kind': 'set', 'target': m.group(3),
                    'value': money_units(m.group(4)),
                    'period': (parse_date(m.group(1)), parse_date(m.group(2)))}
        m = re.match(r'^The .*? under section ([^,]+?) is \$([0-9.]+)'
                     r'(?: per kilolitre| per kilogram)? for the period '
                     r'beginning on (\d+ \w+ \d+)\.$', t)
        if m:
            return {'kind': 'set', 'target': m.group(1),
                    'value': money_units(m.group(2)),
                    'period': (parse_date(m.group(3)), None)}
        m = re.match(r'^The .*? under section ([^,]+?) is \$([0-9.]+)'
                     r'(?: per kilolitre| per kilogram)? for the period '
                     r'from (\d+ \w+ \d+) to (\d+ \w+ \d+)\.$', t)
        if m:
            return {'kind': 'set', 'target': m.group(1),
                    'value': money_units(m.group(2)),
                    'period': (parse_date(m.group(3)), parse_date(m.group(4)))}
        m = re.match(r'^For the (first|second|third|fourth)( and later)? '
                     r'quarters? of the tariff year( only)?, the .*? under '
                     r'section ([^,]+?)(?: for a meter of (\d+) mm)? is '
                     r'\$([0-9.]+)(?: per kilolitre| per kilogram)?\.$', t)
        if m:
            q = {'first': 'Q1', 'second': 'Q2', 'third': 'Q3',
                 'fourth': 'Q4'}[m.group(1)]
            qs, qe = self.quarter_bounds(q)
            period = (qs, None) if m.group(2) else (qs, qe)
            return {'kind': 'set', 'target': m.group(4),
                    'value': money_units(m.group(6)), 'period': period}
        m = re.match(r'^The rate of interest under section ([^,]+?) is '
                     r'([0-9]+\.[0-9]{4}) per cent per annum for the period '
                     r'beginning on (\d+ \w+ \d+)\.$', t)
        if m:
            return {'kind': 'set', 'target': m.group(1),
                    'value': ppm_of(m.group(2)),
                    'period': (parse_date(m.group(3)), None)}
        m = re.match(r'^The wastewater charge rate for Zone (Z-\d+) under '
                     r'section ([^,]+?) is \$([0-9.]+) per kilolitre for the '
                     r'period beginning on (\d+ \w+ \d+)\.$', t)
        if m:
            return {'kind': 'set', 'target': m.group(2),
                    'value': money_units(m.group(3)),
                    'period': (parse_date(m.group(4)), None)}
        m = re.match(r'^The wastewater charge rate for Zone (Z-\d+) under '
                     r'section ([^,]+?) is \$([0-9.]+) per kilolitre for the '
                     r'period from (\d+ \w+ \d+) to (\d+ \w+ \d+)\.$', t)
        if m:
            return {'kind': 'set', 'target': m.group(2),
                    'value': money_units(m.group(3)),
                    'period': (parse_date(m.group(4)), parse_date(m.group(5)))}
        return None

    def _apply_amendments(self, amendments):
        self.amend_log = []
        for a in amendments:
            ref = a['target']
            keys = self.key_of_ref(ref)
            if not keys:
                continue
            corrected = self.corrected_by.get(a['ref'])
            if a['kind'] == 'subst':
                ok = self.code.replace(ref, a['old'], a['new'])
            elif a['kind'] == 'omit':
                ok = self.code.omit(ref, a['old'])
            elif a['kind'] == 'insert':
                ok = self.code.insert_after(ref, a['anchor'], a['new'])
            elif a['kind'] == 'repeal':
                self.code.repeal(ref)
                ok = True
            else:
                ok = False
            for key, kind in keys:
                if a['kind'] == 'set':
                    val = a['value']
                elif a['kind'] == 'repeal':
                    val = self.repealed_value(key)
                    if val is None:
                        continue
                elif not ok:
                    # the text operation found nothing to alter: the
                    # amending provision states the figure itself
                    val = self.parse_new(key, kind, a['new'])
                else:
                    try:
                        val = self.extract(key, kind, self.code.units[ref])
                    except (Unknown, AttributeError, ValueError, TypeError,
                            IndexError):
                        val = None
                if val is None:
                    continue
                auth = a['section']
                if corrected and self._figure_correction(a['ref']):
                    auth = corrected
                self._override(key, val, auth, a['period'])
            self.amend_log.append(a)

    def _figure_correction(self, ref):
        """Did the correction to this provision change a figure (not a day)?"""
        if not hasattr(self, '_figcorr'):
            self._figcorr = {}
            for sec, cref, tref, old, new in self.corrections:
                if re.match(r'^\d+ \w+ \d+$', old.strip()):
                    self._figcorr[tref] = False
                elif re.search(r'\$|%|litres|Band|priority', old):
                    self._figcorr[tref] = True
                else:
                    self._figcorr[tref] = True
        return self._figcorr.get(ref, False)

    def parse_new(self, key, kind, new, ref=None):
        if kind == 'rate':
            return money_units(new)
        if kind == 'ppm':
            return ppm_of(new)
        if kind == 'percent':
            return percent_of(new)
        if kind == 'cents':
            return cents_of(new)
        if kind == 'band':
            return re.search(r'Band ([ABC])', new).group(1)
        if kind == 'days':
            return word_to_int(re.search(r'([A-Za-z-]+) days', new).group(1))
        if kind == 'boolcatch':
            return 'not ' not in new
        if kind == 'booldrought':
            return 'not ' not in new
        if kind.startswith('rebate_'):
            attr = kind[len('rebate_'):]
            if attr == 'priority':
                return int(re.search(r'priority (\d+)', new).group(1))
            if attr == 'carry':
                return word_to_int(
                    re.search(r'([A-Za-z-]+) tariff years?', new).group(1))
            if attr == 'amount':
                return self.parse_amount(new)
            if attr == 'limit':
                if '$' in new:
                    return ('fixed', cents_of(new))
                text = self.code.units.get(ref, '')
                return (self.limit_basis(text), percent_of(new))
        raise Unknown('cannot parse new value for kind %r' % kind)

    def repealed_value(self, key):
        if key[0] == 'rebate':
            if key[2] == 'limit':
                return ('repealed', None)
            if key[2] == 'exclusion':
                return []
        if key[0] == 'catch':
            return False
        if key[0] == 'drought':
            return False
        return None

    # -- timelines -------------------------------------------------------

    def _override(self, key, value, auth, period):
        start, end = self.horizon(key)
        if key not in self.segments:
            base = self.values.get(key)
            if base is None:
                return
            self.segments[key] = [(start, end, base[0], base[1])]
        if period is None:
            a, b = start, end
        else:
            a = max(period[0], start)
            b = period[1]
            if b is None or (end is not None and b > end):
                b = end
        if b is not None and a > b:
            return
        out = []
        for (s, e, v, au) in self.segments[key]:
            if e is not None and b is not None and e < a:
                out.append((s, e, v, au))
                continue
            if b is not None and s > b:
                out.append((s, e, v, au))
                continue
            if s < a:
                out.append((s, a - timedelta(days=1), v, au))
            hi = b if (b is None or e is None or b < e) else e
            out.append((a if a > s else s, hi, value, auth))
            if b is not None and (e is None or e > b):
                out.append((b + timedelta(days=1), e, v, au))
        merged = []
        for seg in out:
            if merged:
                ps, pe, pv, pa = merged[-1]
                if pv == seg[2] and pa == seg[3] and (
                        pe is None or pe + timedelta(days=1) == seg[0]):
                    merged[-1] = (ps, seg[1], pv, pa)
                    continue
            merged.append(seg)
        self.segments[key] = merged

    # -- lookups ---------------------------------------------------------

    def single(self, key):
        segs = self.segments.get(key)
        if not segs:
            raise Unknown('no value for %r' % (key,))
        if len(segs) != 1:
            raise Unknown('value for %r is not constant: %r' % (key, segs))
        return segs[0][2], segs[0][3]

    def period_list(self, key, figure):
        out = []
        for (s, e, v, au) in self.segments.get(key, []):
            out.append({'from': s.isoformat(),
                        'to': e.isoformat() if e else None,
                        figure: v, 'authority': au})
        return out


# ---------------------------------------------------------------------------
# a fast day lookup built from a timeline
# ---------------------------------------------------------------------------

import bisect


class Timeline(object):
    """Value of a figure on each day, from the segments of the Code."""

    __slots__ = ('starts', 'ends', 'values')

    def __init__(self, segments):
        segs = [s for s in segments]
        self.starts = [s[0] for s in segs]
        self.ends = [s[1] for s in segs]
        self.values = [s[2] for s in segs]

    def on(self, day):
        i = bisect.bisect_right(self.starts, day) - 1
        if i < 0:
            raise Unknown('no value in force on %s' % day)
        end = self.ends[i]
        if end is not None and day > end:
            raise Unknown('no value in force on %s' % day)
        return self.values[i]


class Rates(object):
    """Every figure the assessment needs, keyed as the registers key it."""

    def __init__(self, policy):
        p = policy
        self.p = p
        self.block = {}
        self.band = {}
        self.discharge = {}
        self.catchment_exempt = {}
        for code, sec in sorted(p.class_section.items()):
            self.band[code] = p.single(('band', sec))[0]
            self.discharge[code] = p.single(('discharge', sec))[0]
            self.catchment_exempt[code] = p.single(('catch', sec))[0]
            for n in (1, 2, 3):
                self.block[(code, n)] = Timeline(
                    p.segments[('block', sec, n)])
        self.ww = {}
        self.sw = {}
        self.drought = {}
        self.region = {}
        for code, sec in sorted(p.zone_section.items()):
            self.ww[code] = Timeline(p.segments[('ww', sec)])
            self.sw[code] = Timeline(p.segments[('sw', sec)])
            self.drought[code] = p.single(('drought', sec))[0]
            self.region[code] = p.single(('region', sec))[0]
        self.allow = {}
        for band in ('A', 'B', 'C'):
            self.allow[(band, 'b1')] = Timeline(
                p.segments[('allow', band, 'b1')])
            self.allow[(band, 'b2')] = Timeline(
                p.segments[('allow', band, 'b2')])
        self.svc = {}
        for key in p.segments:
            if key[0] == 'svc':
                self.svc[key[1]] = Timeline(p.segments[key])
        self.interest = Timeline(p.segments[('interest',)])
        self.twvol = Timeline(p.segments[('twvol',)])
        self.twload = Timeline(p.segments[('twload',)])

    def block_rate(self, cls, n, day):
        return self.block[(cls, n)].on(day)

    def allowance(self, band, part, day):
        return self.allow[(band, part)].on(day)


# ---------------------------------------------------------------------------
# registers
# ---------------------------------------------------------------------------


def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def iso(s):
    s = s.strip()
    return date(int(s[0:4]), int(s[5:7]), int(s[8:10]))



def days_in(window):
    if window is None:
        return 0
    start, end = window
    if end is None:
        return 366
    return (end - start).days + 1


TOTAL_KEYS = ('water_supply_cents', 'wastewater_cents',
              'service_charges_cents', 'surcharge_cents',
              'catchment_levy_cents', 'trade_waste_cents',
              'gross_charge_cents', 'rebates_total_cents',
              'minimum_topup_cents', 'net_charge_cents',
              'payments_cents', 'interest_cents', 'balance_cents')


def zero_totals():
    return dict((k, 0) for k in TOTAL_KEYS)


class Batch(object):
    """A billing batch, assessed under the Code."""

    def __init__(self, data_dir, policy, rates):
        self.dir = data_dir
        self.p = policy
        self.r = rates
        self.issues = []
        with open(os.path.join(data_dir, 'batch.json'),
                  encoding='utf-8-sig') as fh:
            self.manifest = json.load(fh)
        self.assessment_date = iso(self.manifest['assessment_date'])
        self.batch_id = self.manifest['batch_id']
        self.accounts = read_csv(os.path.join(data_dir, 'accounts.csv'))
        self.properties = read_csv(os.path.join(data_dir, 'properties.csv'))
        self.meters = read_csv(os.path.join(data_dir, 'meters.csv'))
        self.readings = read_csv(os.path.join(data_dir, 'meter_reads.csv'))
        self.trade_waste = read_csv(os.path.join(data_dir, 'trade_waste.csv'))
        self.claims = read_csv(os.path.join(data_dir,
                                            'concession_claims.csv'))
        self.leak_claims = read_csv(os.path.join(data_dir, 'leak_claims.csv'))
        self.carryforwards = read_csv(os.path.join(data_dir,
                                                   'carryforwards.csv'))
        self.payments = read_csv(os.path.join(data_dir, 'payments.csv'))

        self.account_by_id = {}
        for row in self.accounts:
            self.account_by_id[row['account_id']] = row
        self.props_by_account = {}
        for row in self.properties:
            self.props_by_account.setdefault(row['account_id'], []).append(row)
        for acc in self.props_by_account:
            self.props_by_account[acc].sort(key=lambda r: r['property_id'])
        self.prop_by_id = {}
        for row in self.properties:
            self.prop_by_id[row['property_id']] = row
        self.meters_by_prop = {}
        for row in self.meters:
            self.meters_by_prop.setdefault(row['property_id'], []).append(row)
        for prop in self.meters_by_prop:
            self.meters_by_prop[prop].sort(key=lambda r: r['meter_id'])
        self.readings_by_meter = {}
        for row in self.readings:
            self.readings_by_meter.setdefault(row['meter_id'], []).append(row)
        self.trade_by_prop = {}
        for row in self.trade_waste:
            self.trade_by_prop.setdefault(row['property_id'], []).append(row)
        self.claims_by_account = {}
        for row in self.claims:
            self.claims_by_account.setdefault(row['account_id'],
                                               []).append(row)
        self.leaks_by_prop = {}
        for row in self.leak_claims:
            self.leaks_by_prop.setdefault(row['property_id'], []).append(row)
        self.cf_by_account = {}
        for row in self.carryforwards:
            self.cf_by_account.setdefault(row['account_id'], []).append(row)
        self.payments_by_account = {}
        for row in self.payments:
            self.payments_by_account.setdefault(row['account_id'],
                                                []).append(row)

    # -- supply windows -------------------------------------------------

    def account_window(self, acct):
        start = self.p.tariff_start
        if acct['opened_on']:
            d = iso(acct['opened_on'])
            if d > start:
                start = d
        end = self.p.tariff_end
        if acct['closed_on']:
            d = iso(acct['closed_on'])
            if d < end:
                end = d
        if start > end:
            return None
        return (start, end)

    def property_window(self, prop, acct_window):
        if acct_window is None:
            return None
        start, end = acct_window
        d = iso(prop['connected_on'])
        if d > start:
            start = d
        if prop['disconnected_on']:
            d = iso(prop['disconnected_on'])
            if d < end:
                end = d
        if start > end:
            return None
        return (start, end)

    def meter_window(self, meter, prop_window):
        if prop_window is None:
            return None
        start, end = prop_window
        d = iso(meter['installed_on'])
        if d > start:
            start = d
        if meter['removed_on']:
            d = iso(meter['removed_on'])
            if d < end:
                end = d
        if start > end:
            return None
        return (start, end)

    # -- meter intervals -------------------------------------------------

    def intervals_of(self, meter_id, meter, prop, window):
        """The meter intervals of a meter, under sections 4-030 and 1-082."""
        rows = self.readings_by_meter.get(meter_id, [])
        out = []
        if window is None:
            for row in rows:
                self.issues.append(
                    '%s: reading of %s outside the meter\'s supply window '
                    'disregarded' % (meter_id, row['read_on']))
            return out
        start, end = window
        lo = start - timedelta(days=1)
        taken = []
        for row in rows:
            d = iso(row['read_on'])
            if d < lo or d > end:
                self.issues.append(
                    '%s: reading of %s outside the meter\'s supply window '
                    'disregarded' % (meter_id, row['read_on']))
                continue
            taken.append((d, int(row['reading_litres'])))
        taken.sort(key=lambda x: (x[0], x[1]))
        for i in range(1, len(taken)):
            prev_day, prev_val = taken[i - 1]
            day, val = taken[i]
            litres = val - prev_val
            if litres < 0:
                self.issues.append(
                    '%s: reading of %s lower than the preceding reading; '
                    'consumption nil' % (meter_id, day.isoformat()))
                litres = 0
            out.append({'meter_id': meter_id,
                        'property_id': prop['property_id'],
                        'from': (prev_day + timedelta(days=1)).isoformat(),
                        'to': day.isoformat(),
                        'days': (day - prev_day).days,
                        'litres': litres})
        return out

    # -- charges ---------------------------------------------------------

    def water_cents(self, interval, cls, band):
        """Section 4-010: the water supply charge of a meter interval."""
        days = interval['days']
        if days <= 0 or interval['litres'] == 0:
            return 0
        daily = Fraction(interval['litres'], days)
        groups = {}
        day = iso(interval['from'])
        last = iso(interval['to'])
        while day <= last:
            key = (self.r.allowance(band, 'b1', day),
                   self.r.allowance(band, 'b2', day),
                   self.r.block_rate(cls, 1, day),
                   self.r.block_rate(cls, 2, day),
                   self.r.block_rate(cls, 3, day))
            groups[key] = groups.get(key, 0) + 1
            day = day + timedelta(days=1)
        total = Fraction(0)
        for (a1, a2, r1, r2, r3), n in groups.items():
            b1 = daily if daily < a1 else a1
            if daily > a2:
                b2 = a2 - a1
                b3 = daily - a2
            elif daily > a1:
                b2 = daily - a1
                b3 = Fraction(0)
            else:
                b2 = Fraction(0)
                b3 = Fraction(0)
            total = total + (b1 * n * r1 + b2 * n * r2 + b3 * n * r3)
        return half_even(total / 100000)

    def wastewater_cents(self, interval, cls, zone):
        """Section 5-010: the wastewater charge of a meter interval."""
        days = interval['days']
        if days <= 0 or interval['litres'] == 0:
            return 0
        factor = self.r.discharge[cls]
        volume = Fraction(interval['litres'] * factor, 100)
        groups = {}
        day = iso(interval['from'])
        last = iso(interval['to'])
        while day <= last:
            rate = self.r.ww[zone].on(day)
            groups[rate] = groups.get(rate, 0) + 1
            day = day + timedelta(days=1)
        per_day = volume / days
        total = Fraction(0)
        for rate, n in groups.items():
            total = total + per_day * n * rate
        return half_up(total / 100000)

    def service_cents(self, meter, window):
        """Section 6-010: the daily service charges of a meter for the year."""
        if window is None:
            return 0
        size = int(meter['size_mm'])
        tl = self.r.svc[size]
        total = Fraction(0)
        day = window[0]
        end = window[1]
        while day <= end:
            total = total + tl.on(day)
            day = day + timedelta(days=1)
        return half_even(total / 100)

    def stormwater_cents(self, prop, window):
        """Section 6-030: the stormwater charge of a property."""
        if window is None:
            return 0
        area = int(prop['land_area_m2'])
        tl = self.r.sw[prop['zone']]
        rate_total = Fraction(0)
        day = window[0]
        end = window[1]
        while day <= end:
            rate_total = rate_total + tl.on(day)
            day = day + timedelta(days=1)
        return half_up(area * rate_total / 36500)

    def trade_waste_cents(self, row, quarter_first_day):
        """Section 5-110: the trade waste charge of a return."""
        litres = int(row['discharge_litres'])
        bod = int(row['bod_mg_per_l'])
        vol = self.r.twvol.on(quarter_first_day)
        load = self.r.twload.on(quarter_first_day)
        total = (Fraction(litres * vol, 100000) +
                 Fraction(litres * bod * load, 100000000))
        return half_even(total)

    # -- rebates ---------------------------------------------------------

    def rebate_codes_with_basis(self, basis):
        """The rebate codes whose Amount subsection names this basis."""
        out = []
        for code in self.p.establishing:
            amount = self.p.single(('rebate', code, 'amount'))
            if amount[0]['basis'] == basis:
                out.append(code)
        out.sort()
        return out

    def rebate_order(self):
        """Section 1-086: ascending priority, then ascending section."""
        out = []
        for code, sec in self.p.establishing.items():
            priority = self.p.single(('rebate', code, 'priority'))[0]
            part, num = sec.split('-')
            out.append((priority, int(part), int(num), code))
        out.sort()
        return [row[3] for row in out]

    def eligible(self, code, ctx):
        cond = self.p.single(('rebate', code, 'eligibility'))[0]
        excluded = self.p.single(('rebate', code, 'exclusion'))[0]
        if ctx['holder_form'] in excluded:
            return False
        if cond['classes'] and ctx['account_class'] not in cond['classes']:
            return False
        if cond['cards'] and ctx['concession_card'] not in cond['cards']:
            return False
        if cond['community']:
            if not (ctx['account_class'] == 'public' or
                    ctx['holder_form'] == 'association'):
                return False
        if cond['drought'] and not ctx['has_drought_property']:
            return False
        if cond['large'] and not ctx['has_large_meter']:
            return False
        return True

    def limit_of(self, code, ctx):
        """The limit of a rebate, or None where it has been repealed."""
        lim = self.p.single(('rebate', code, 'limit'))[0]
        basis, amount = lim
        if basis == 'repealed':
            return None
        if basis == 'fixed':
            return amount
        figure = ctx['figures'][basis]
        return half_even(Fraction(figure * amount, 100))

    def current_year_amount(self, code, ctx):
        """The current-year amount of a rebate, under section 1-082(h)."""
        amount = self.p.single(('rebate', code, 'amount'))
        basis = amount[0]['basis']
        rate = amount[0]['rate']
        if basis == 'expenditure':
            total = ctx['expenditure'].get(code, 0)
            return half_even(Fraction(total * rate, 100))
        if basis == 'leak':
            total = 0
            for value in ctx['leak_values']:
                total = total + half_even(value * rate / 100)
            return total
        if basis in ('service', 'water', 'gross', 'supply', 'volumetric'):
            return half_even(Fraction(ctx['figures'][basis] * rate, 100))
        if basis == 'largemeter':
            return half_even(Fraction(ctx['large_service'] * rate, 100))
        raise Unknown('rebate amount basis %r' % basis)

    def claims_of(self, account_id, ctx):
        """Section 9-003: sort the claims register of an account."""
        codes = set(self.p.establishing)
        expenditure_based = set()
        for code in self.p.establishing:
            if self.p.single(('rebate', code, 'amount'))[0]['basis'] in (
                    'expenditure',):
                expenditure_based.add(code)
        total = {}
        for row in self.claims_by_account.get(account_id, []):
            code = row['rebate_code']
            claim_id = row['claim_id']
            if code not in codes:
                self.issues.append(
                    '%s: claim %s under %s disregarded: no such rebate'
                    % (account_id, claim_id, code))
                continue
            if code not in expenditure_based:
                self.issues.append(
                    '%s: claim %s under %s disregarded: rebate arises '
                    'without claim' % (account_id, claim_id, code))
                continue
            if not self.eligible(code, ctx):
                self.issues.append(
                    '%s: claim %s under %s disregarded: account not eligible'
                    % (account_id, claim_id, code))
                continue
            total[code] = total.get(code, 0) + int(row['expenditure_cents'])
        return total

    def leak_claims_of(self, account_id, props, acct):
        """Section 9-005: accept the leak claims of an account."""
        accepted = []
        codes = self.rebate_codes_with_basis('leak')
        if not codes:
            return accepted
        code = codes[0]
        cond = self.p.single(('rebate', code, 'eligibility'))[0]
        eligible = (acct['account_class'] in cond['classes'] and
                    acct['holder_form'] not in
                    self.p.single(('rebate', code, 'exclusion'))[0])
        for prop in props:
            for row in self.leaks_by_prop.get(prop['property_id'], []):
                repaired = iso(row['repaired_on'])
                if not (self.p.tariff_start <= repaired <=
                        self.p.tariff_end):
                    self.issues.append(
                        '%s: leak claim %s disregarded: repair date outside '
                        'the tariff year'
                        % (account_id, row['leak_claim_id']))
                    continue
                if not eligible:
                    self.issues.append(
                        '%s: leak claim %s disregarded: account not eligible'
                        % (account_id, row['leak_claim_id']))
                    continue
                rate = self.r.block_rate(prop['tariff_class'], 3, repaired)
                accepted.append(
                    Fraction(int(row['leak_litres']) * rate, 100000))
        return accepted

    # -- one account -----------------------------------------------------

    def assess(self, acct):
        account_id = acct['account_id']
        aclass = acct['account_class']
        acct_window = self.account_window(acct)
        props = self.props_by_account.get(account_id, [])

        prop_objects = []
        meter_objects = []
        interval_objects = []
        water_total = 0
        water_nonexempt = 0
        large_service = 0
        has_large_meter = False
        zone_consumption = {}

        for prop in props:
            pwin = self.property_window(prop, acct_window)
            cls = prop['tariff_class']
            band = self.r.band[cls]
            storm = self.stormwater_cents(prop, pwin)
            tw = 0
            if aclass == 'commercial':
                for row in self.trade_by_prop.get(prop['property_id'], []):
                    q = row['quarter']
                    qstart, _ = self.p.quarter_bounds(q)
                    tw = tw + self.trade_waste_cents(row, qstart)
            else:
                for row in self.trade_by_prop.get(prop['property_id'], []):
                    self.issues.append(
                        '%s: trade waste return for a property of a '
                        'non-commercial account disregarded'
                        % row['return_id'])
            prop_objects.append({
                'property_id': prop['property_id'],
                'zone': prop['zone'],
                'tariff_class': cls,
                'supply_days': days_in(pwin),
                'stormwater_cents': storm,
                'trade_waste_cents': tw})
            for meter in self.meters_by_prop.get(prop['property_id'], []):
                mwin = self.meter_window(meter, pwin)
                svc = self.service_cents(meter, mwin)
                meter_objects.append({
                    'meter_id': meter['meter_id'],
                    'property_id': prop['property_id'],
                    'size_mm': int(meter['size_mm']),
                    'service_days': days_in(mwin),
                    'service_cents': svc})
                if int(meter['size_mm']) >= 80 and days_in(mwin) >= 1:
                    has_large_meter = True
                    large_service = large_service + svc
                for interval in self.intervals_of(meter['meter_id'], meter,
                                                   prop, mwin):
                    interval['water_cents'] = self.water_cents(
                        interval, cls, band)
                    interval['wastewater_cents'] = self.wastewater_cents(
                        interval, cls, prop['zone'])
                    water_total = water_total + interval['water_cents']
                    zone_consumption[prop['zone']] =  \
                        zone_consumption.get(prop['zone'], 0) +  \
                        interval['litres']
                    if not self.r.catchment_exempt[cls]:
                        water_nonexempt = water_nonexempt +  \
                            interval['water_cents']
                    interval_objects.append(interval)

        meter_objects.sort(key=lambda m: (m['property_id'], m['meter_id']))
        interval_objects.sort(key=lambda m: (m['meter_id'], m['to']))

        service_total = sum(m['service_cents'] for m in meter_objects)
        storm_total = sum(p['stormwater_cents'] for p in prop_objects)
        trade_total = sum(p['trade_waste_cents'] for p in prop_objects)
        service_charges = service_total + storm_total
        wastewater_total = sum(i['wastewater_cents'] for i in interval_objects)
        volumetric = water_total + wastewater_total
        base = volumetric + service_charges

        # the billing zone: Binding Ruling BR 2026/1, else section 3-002
        billing_zone = None
        if zone_consumption:
            best = max(zone_consumption.values())
            if best > 0:
                zones = [z for z, v in zone_consumption.items() if v == best]
                zones.sort(key=lambda z: int(z.split('-')[1]))
                billing_zone = zones[0]
        if billing_zone is None:
            live = []
            for prop in props:
                pwin = self.property_window(prop, acct_window)
                if pwin is not None:
                    live.append((iso(prop['connected_on']),
                                 prop['property_id'], prop['zone']))
            if live:
                live.sort()
                billing_zone = live[0][2]

        region = self.r.region[billing_zone] if billing_zone else None
        drought = self.r.drought[billing_zone] if billing_zone else False
        surcharge_ppm = self.p.single(('surcharge', region))[0]
        if drought:
            surcharge_ppm = surcharge_ppm + self.p.single(('droughtsup',))[0]
        surcharge = half_even(Fraction(base * surcharge_ppm, 1000000))
        supply_total = base + surcharge
        levy = half_up(Fraction(water_nonexempt *
                                self.p.single(('catchlevy',))[0], 1000000))
        gross = supply_total + levy + trade_total

        figures = {'service': service_charges, 'water': water_total,
                   'volumetric': volumetric, 'gross': gross,
                   'supply': supply_total}
        ctx = {
            'account_class': aclass,
            'holder_form': acct['holder_form'],
            'concession_card': acct['concession_card'],
            'has_drought_property': any(
                self.r.drought[p['zone']] for p in props),
            'has_large_meter': has_large_meter,
            'figures': figures,
            'large_service': large_service,
            'leak_values': self.leak_claims_of(account_id, props, acct),
            'expenditure': {},
        }
        ctx['expenditure'] = self.claims_of(account_id, ctx)

        # Part 10: amounts carried forward that are taken into account
        cf_taken = []
        for row in self.cf_by_account.get(account_id, []):
            code = row['rebate_code']
            origin = int(row['origin_year'])
            if code not in self.p.establishing:
                self.issues.append(
                    '%s: carryforward %s/%d disregarded: not permitted'
                    % (account_id, code, origin))
                continue
            years = self.p.single(('rebate', code, 'carry'))[0]
            if years <= 0:
                self.issues.append(
                    '%s: carryforward %s/%d disregarded: not permitted'
                    % (account_id, code, origin))
                continue
            if self.p.tariff_start.year > origin + years:
                self.issues.append(
                    '%s: carryforward %s/%d disregarded: expired'
                    % (account_id, code, origin))
                continue
            cf_taken.append((origin, code, int(row['remaining_cents'])))

        # Part 9: apply the rebates in order
        gross_left = gross
        cap_left = half_even(
            Fraction(gross * self.p.single(('globalcap',))[0], 100))
        rebates_applied = []
        rebates_total = 0
        carry_out = []
        for code in self.rebate_order():
            years = self.p.single(('rebate', code, 'carry'))[0]
            amounts = []
            if self.eligible(code, ctx):
                amt = self.current_year_amount(code, ctx)
                if amt > 0:
                    amounts.append((self.p.tariff_start.year, amt))
            for origin, ccode, remaining in cf_taken:
                if ccode == code and remaining > 0:
                    amounts.append((origin, remaining))
            if not amounts:
                continue
            limit = self.limit_of(code, ctx)
            for origin, available in amounts:
                allow = available
                if allow > gross_left:
                    allow = gross_left
                if allow > cap_left:
                    allow = cap_left
                if limit is not None and allow > limit:
                    allow = limit
                if allow < 0:
                    allow = 0
                if allow > 0:
                    rebates_applied.append({'rebate_code': code,
                                            'origin_year': origin,
                                            'applied_cents': allow})
                    rebates_total = rebates_total + allow
                    gross_left = gross_left - allow
                    cap_left = cap_left - allow
                    if limit is not None:
                        limit = limit - allow
                left = available - allow
                if left > 0 and years > 0 and \
                        self.p.tariff_start.year + 1 <= origin + years:
                    carry_out.append((code, origin, left))
        carry_out.sort()

        # Part 11: minimum charge, under Binding Ruling BR 2026/2
        minimum = half_up(
            Fraction(self.p.single(('minimum', aclass))[0] *
                     days_in(acct_window), 365))
        after_rebates = gross - rebates_total
        topup = minimum - after_rebates
        if topup < 0:
            topup = 0
        net = gross - rebates_total + topup

        # Part 12: instalments, payments and interest
        instalments = []
        remaining = net
        for i, q in enumerate(('Q1', 'Q2', 'Q3', 'Q4')):
            if i < 3:
                amount = net // 4
            else:
                amount = remaining
            instalments.append({'quarter': q,
                                'due_date': self.p.due_dates[q],
                                'amount_cents': amount,
                                'paid': 0, 'parts': [], 'unpaid': amount})
            remaining = remaining - amount
        payments = []
        for row in self.payments_by_account.get(account_id, []):
            paid_on = iso(row['paid_on'])
            if paid_on > self.assessment_date:
                self.issues.append(
                    '%s: payment %s dated after the assessment date '
                    'disregarded' % (account_id, row['payment_id']))
                continue
            effective = self.p.next_business_day(paid_on)
            payments.append((effective, row['payment_id'],
                             int(row['amount_cents'])))
        payments.sort()
        payments_total = 0
        for effective, payment_id, amount in payments:
            payments_total = payments_total + amount
            left = amount
            for inst in instalments:
                if left <= 0:
                    break
                if inst['unpaid'] <= 0:
                    continue
                take = left if left < inst['unpaid'] else inst['unpaid']
                inst['unpaid'] = inst['unpaid'] - take
                inst['paid'] = inst['paid'] + take
                inst['parts'].append((take, effective))
                left = left - take
        grace = self.p.single(('grace',))[0]
        interest_total = 0
        for inst in instalments:
            due = inst['due_date']
            inst_interest = 0
            for take, effective in inst['parts']:
                if effective <= due or effective <= due +  \
                        timedelta(days=grace):
                    continue
                inst_interest = inst_interest + self.part_interest(
                    take, due + timedelta(days=1), effective)
            if inst['unpaid'] > 0 and self.assessment_date >  \
                    due + timedelta(days=grace):
                inst_interest = inst_interest + self.part_interest(
                    inst['unpaid'], due + timedelta(days=1),
                    self.assessment_date)
            interest_total = interest_total + inst_interest
            inst['interest'] = inst_interest
        balance = net + interest_total - payments_total

        return {
            'account_id': account_id,
            'account_class': aclass,
            'holder_form': acct['holder_form'],
            'concession_card': acct['concession_card'],
            'active_days': days_in(acct_window),
            'billing_zone': billing_zone,
            'meter_intervals': interval_objects,
            'meters': meter_objects,
            'properties': prop_objects,
            'water_supply_cents': water_total,
            'wastewater_cents': wastewater_total,
            'volumetric_charges_cents': volumetric,
            'service_charges_cents': service_charges,
            'base_charges_cents': base,
            'surcharge_cents': surcharge,
            'supply_total_cents': supply_total,
            'catchment_levy_cents': levy,
            'trade_waste_cents': trade_total,
            'gross_charge_cents': gross,
            'rebates_applied': rebates_applied,
            'rebates_total_cents': rebates_total,
            'carryforward_out': [{'rebate_code': c, 'origin_year': o,
                                  'remaining_cents': r}
                                 for c, o, r in carry_out],
            'minimum_charge_cents': minimum,
            'minimum_topup_cents': topup,
            'net_charge_cents': net,
            'instalments': [{'quarter': i['quarter'],
                             'due_date': i['due_date'].isoformat(),
                             'amount_cents': i['amount_cents'],
                             'paid_cents': i['paid'],
                             'interest_cents': i['interest']}
                            for i in instalments],
            'payments_cents': payments_total,
            'interest_cents': interest_total,
            'balance_cents': balance,
        }

    def part_interest(self, part, first_day, last_day):
        """Section 12-040: interest on a part, rounded half up."""
        total = Fraction(0)
        day = first_day
        while day <= last_day:
            rate = self.r.interest.on(day)
            total = total + part * rate
            day = day + timedelta(days=1)
        return half_up(total / 1000000 / 365)

    # -- statements ------------------------------------------------------

    def run(self, out_dir):
        accounts = [self.account_by_id[k] for k in sorted(self.account_by_id)]
        assessed = [self.assess(a) for a in accounts]

        regions = {}
        for region in ('North', 'South', 'West', 'East'):
            regions[region] = []
        for acc in assessed:
            region = self.r.region[acc['billing_zone']] if \
                acc['billing_zone'] else None
            regions.setdefault(region, []).append(acc)
        region_files = {}
        for region in ('North', 'South', 'West', 'East'):
            region_files[region] = self.region_statement(region,
                                                          regions[region])
        summary = self.summary_statement(assessed, regions, region_files)
        write_json(out_dir, 'summary.json', summary)
        for region in ('North', 'South', 'West', 'East'):
            write_json(out_dir, 'region_%s.json' % region,
                       region_files[region])
        for seg in ('commercial', 'public'):
            write_json(out_dir, 'segment_%s.json' % seg,
                       self.segment_statement(seg, assessed))
        write_json(out_dir, 'policy_audit.json', self.policy_audit())
        write_json(out_dir, 'data_quality.json', self.data_quality(assessed))
        return summary

    def region_statement(self, region, accounts):
        totals = zero_totals()
        for acc in accounts:
            add_totals(totals, acc)
        return {'region': region,
                'account_count': len(accounts),
                'totals': totals,
                'accounts': accounts}

    def summary_statement(self, assessed, regions, region_files):
        totals = zero_totals()
        for acc in assessed:
            add_totals(totals, acc)
        region_totals = {}
        for region in ('North', 'South', 'West', 'East'):
            region_totals[region] = region_files[region]['totals']
        counts = {'residential': 0, 'commercial': 0, 'public': 0}
        status = {'credit_balance': 0, 'settled': 0, 'balance_due': 0}
        for acc in assessed:
            counts[acc['account_class']] = counts[acc['account_class']] + 1
            bal = acc['balance_cents']
            if bal < 0:
                status['credit_balance'] = status['credit_balance'] + 1
            elif bal == 0:
                status['settled'] = status['settled'] + 1
            else:
                status['balance_due'] = status['balance_due'] + 1
        return {'report_id': self.batch_id,
                'assessment_date': self.assessment_date.isoformat(),
                'account_count': len(assessed),
                'totals': totals,
                'region_totals': region_totals,
                'class_account_counts': counts,
                'balance_status_counts': status}

    def segment_statement(self, segment, assessed):
        rows = [a for a in assessed if a['account_class'] == segment]
        totals = zero_totals()
        for acc in rows:
            add_totals(totals, acc)
        rebate_totals = {}
        for acc in rows:
            for row in acc['rebates_applied']:
                code = row['rebate_code']
                rebate_totals[code] = rebate_totals.get(code, 0) +  \
                    row['applied_cents']
        return {'segment': segment,
                'account_count': len(rows),
                'totals': totals,
                'rebate_totals': rebate_totals,
                'account_ids': [a['account_id'] for a in rows]}

    def data_quality(self, assessed):
        issues = sorted(self.issues)
        return {
            'input_file_count': sum(
                1 for name in sorted(os.listdir(self.dir))
                if os.path.isfile(os.path.join(self.dir, name))),
            'account_count': len(self.accounts),
            'property_count': len(self.properties),
            'meter_count': len(self.meters),
            'reading_count': len(self.readings),
            'trade_waste_return_count': len(self.trade_waste),
            'claim_count': len(self.claims),
            'leak_claim_count': len(self.leak_claims),
            'carryforward_count': len(self.carryforwards),
            'payment_count': len(self.payments),
            'quality_issue_count': len(issues),
            'quality_issues': issues,
        }

    def policy_audit(self):
        p = self.p
        classes = {}
        for code in sorted(p.class_section):
            sec = p.class_section[code]
            classes[code] = {
                'band': value_object(p.single(('band', sec))),
                'discharge_factor_percent': value_object(
                    p.single(('discharge', sec))),
                'catchment_exempt': value_object(p.single(('catch', sec))),
                'block_rates': {
                    'block_1': p.period_list(('block', sec, 1), 'rate'),
                    'block_2': p.period_list(('block', sec, 2), 'rate'),
                    'block_3': p.period_list(('block', sec, 3), 'rate'),
                }}
        zones = {}
        for code in sorted(p.zone_section):
            sec = p.zone_section[code]
            zones[code] = {
                'region': value_object(p.single(('region', sec))),
                'drought_zone': value_object(p.single(('drought', sec))),
                'stormwater_rate': value_object(p.single(('sw', sec))),
                'wastewater_rate_periods':
                    p.period_list(('ww', sec), 'rate'),
            }
        allowances = {}
        for band in ('A', 'B', 'C'):
            allowances[band] = {
                'block_1': value_object(p.single(('allow', band, 'b1'))),
                'block_2_upper': value_object(p.single(('allow', band,
                                                        'b2'))),
            }
        service = {}
        for size in sorted(set(k[1] for k in p.segments if k[0] == 'svc')):
            service[str(size)] = p.period_list(('svc', size), 'rate')
        rebates = []
        for code in self.rebate_order():
            sec = p.establishing[code]
            entry = {
                'rebate_code': code,
                'section': sec,
                'priority': value_object(p.single(('rebate', code,
                                                   'priority'))),
                'rate_percent': value_object(
                    (self.p.single(('rebate', code, 'amount'))[0]['rate'],
                     self.p.single(('rebate', code, 'amount'))[1])),
                'cap': self.cap_object(code),
                'carry_years': value_object(p.single(('rebate', code,
                                                      'carry'))),
                'excluded_forms': value_object(p.single(('rebate', code,
                                                        'exclusion'))),
            }
            cond = p.single(('rebate', code, 'eligibility'))
            if cond[0]['cards']:
                entry['concession_cards'] = {
                    'value': cond[0]['cards'], 'authority': cond[1]}
            rebates.append(entry)
        return {
            'report_id': self.batch_id,
            'tariff_classes': classes,
            'zones': zones,
            'band_allowances_litres_per_day': allowances,
            'daily_service_charges': service,
            'regional_surcharge_ppm': dict(
                (r, value_object(p.single(('surcharge', r))))
                for r in ('North', 'South', 'West', 'East')),
            'drought_supplement_ppm': value_object(p.single(('droughtsup',))),
            'catchment_levy_ppm': value_object(p.single(('catchlevy',))),
            'trade_waste_rates': {
                'volume': p.period_list(('twvol',), 'rate'),
                'load': p.period_list(('twload',), 'rate'),
            },
            'rebates_in_application_order': rebates,
            'global_rebate_cap_percent': value_object(
                p.single(('globalcap',))),
            'minimum_charge_cents': dict(
                (c, value_object(p.single(('minimum', c))))
                for c in ('residential', 'commercial', 'public')),
            'interest_grace_days': value_object(p.single(('grace',))),
            'interest_rate_periods': p.period_list(('interest',),
                                                    'rate_ppm'),
            'instalment_due_dates': dict(
                (q, p.due_dates[q].isoformat())
                for q in ('Q1', 'Q2', 'Q3', 'Q4')),
            'binding_rulings_applied': self.binding_rulings(),
        }

    def binding_rulings(self):
        """The Binding Rulings of Part 16, which prevail where inconsistent."""
        out = []
        for sec in self.p.code.order:
            if int(sec.split('-')[0]) != 16:
                continue
            body = self.p.code.section_text.get(sec, '') + \
                self.p.code.section_extra.get(sec, '')
            if 'Designation: Binding Ruling.' in body:
                out.append(sec)
        out.sort()
        return out

    def cap_object(self, code):
        lim = self.p.single(('rebate', code, 'limit'))
        basis, amount = lim[0]
        if basis == 'repealed':
            return {'basis': None, 'amount': None, 'authority': lim[1]}
        if basis == 'fixed':
            return {'basis': 'fixed', 'amount': amount,
                    'authority': lim[1]}
        return {'basis': basis, 'amount': amount, 'authority': lim[1]}


def value_object(pair):
    return {'value': pair[0], 'authority': pair[1]}


def add_totals(totals, acc):
    for key in TOTAL_KEYS:
        totals[key] = totals[key] + acc[key]


def write_json(out_dir, name, obj):
    text = json.dumps(obj, indent=2, sort_keys=True) + '\n'
    with open(os.path.join(out_dir, name), 'w', encoding='utf-8',
              newline='\n') as fh:
        fh.write(text)





def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: derive_report.py <DATA_DIR> <OUT_DIR>\n')
        return 2
    data_dir = argv[1]
    out_dir = argv[2]
    with open(os.path.join(data_dir, 'tariff_code.md'),
              encoding='utf-8-sig') as fh:
        code = Code(fh.read())
    policy = Policy(code)
    rates = Rates(policy)
    batch = Batch(data_dir, policy, rates)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    batch.run(out_dir)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
