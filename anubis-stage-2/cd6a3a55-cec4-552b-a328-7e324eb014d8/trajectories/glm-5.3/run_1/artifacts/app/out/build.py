#!/usr/bin/env python3
"""Helios Q3 close program (amalgamated from src/helios_close)."""
from __future__ import annotations

# ---- domain

import hashlib as _hl
import json as _json
import zlib as _zlib
from decimal import Decimal as _D, ROUND_HALF_UP as _HU, ROUND_HALF_EVEN as _HE, ROUND_FLOOR as _FL
MASK64 = (1 << 64) - 1
Q_START = 1751328000
CUT = 1759276800
LATE_END = 1761004800
HIST_START = 1672531200
DAY = 86400

def days_from_civil(y, m, d):
    y -= m <= 2
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468

def civil_from_days(z):
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    return (y + (m <= 2), m, d)

def epoch(y, m, d, hh=0, mm=0, ss=0):
    return days_from_civil(y, m, d) * DAY + hh * 3600 + mm * 60 + ss

def weekday_of_day(z):
    return (z + 3) % 7

def nth_sunday(y, m, n):
    first = next((d for d in range(1, 8) if weekday_of_day(days_from_civil(y, m, d)) == 6))
    return first + 7 * (n - 1)

def last_sunday(y, m):
    dim = [31, 29 if y % 4 == 0 and (y % 100 or y % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return max((d for d in range(dim - 6, dim + 1) if weekday_of_day(days_from_civil(y, m, d)) == 6))
ZONES = ['UTC', 'IE', 'US', 'IN', 'JP', 'AU']

def zone_offset(zone, t):
    """Offset east of UTC (seconds) in force at UTC instant t (close_contract.md section 3)."""
    if zone == 'UTC':
        return 0
    if zone == 'IN':
        return 19800
    if zone == 'JP':
        return 32400
    y = civil_from_days(t // DAY)[0]
    if zone == 'IE':
        on = epoch(y, 3, last_sunday(y, 3), 1)
        off = epoch(y, 10, last_sunday(y, 10), 1)
        return 3600 if on <= t < off else 0
    if zone == 'US':
        on = epoch(y, 3, nth_sunday(y, 3, 2), 8)
        off = epoch(y, 11, nth_sunday(y, 11, 1), 7)
        return -18000 if on <= t < off else -21600
    if zone == 'AU':
        on = epoch(y, 10, nth_sunday(y, 10, 1), 0) - 8 * 3600
        off = epoch(y, 4, nth_sunday(y, 4, 1), 0) - 8 * 3600
        return 39600 if t >= on or t < off else 36000
    raise ValueError(zone)

def wall_of(t, zone):
    return t + zone_offset(zone, t)

def iso(t):
    if t is None:
        return None
    y, m, d = civil_from_days(t // DAY)
    s = t % DAY
    return f'{y:04d}-{m:02d}-{d:02d}T{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}Z'

def iso_date(z):
    if z is None:
        return None
    y, m, d = civil_from_days(z)
    return f'{y:04d}-{m:02d}-{d:02d}'

def day_of(t):
    return t // DAY
CUT_DAY = CUT // DAY
Q_START_DAY = Q_START // DAY
XL1900_DAY = days_from_civil(1899, 12, 30)
XL1904_DAY = days_from_civil(1904, 1, 1)

def D(x):
    return x if isinstance(x, _D) else _D(str(x))

def q(x, dp, mode='even'):
    rounding = {'even': _HE, 'up': _HU, 'floor': _FL}[mode]
    return D(x).quantize(_D(1).scaleb(-dp), rounding=rounding)

def dec_str(x):
    s = format(D(x).normalize(), 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s

class Sentinel:
    __slots__ = ('meaning',)

    def __init__(self, meaning):
        self.meaning = meaning

    def __repr__(self):
        return f'@{self.meaning}'
UNKNOWN = Sentinel('unknown')
NONE = Sentinel('none')
SEE_DECOY = Sentinel('elsewhere')
SENT_BY = {'unknown': UNKNOWN, 'none': NONE, 'elsewhere': SEE_DECOY}
CURRENCIES = ['EUR', 'USD', 'GBP', 'INR', 'JPY']
CUR_EXP = {'EUR': 2, 'USD': 2, 'GBP': 2, 'INR': 2, 'JPY': 0}

def canon_str(kind, v):
    """Canonical text of a value of a given kind (custody checksums, close_contract.md section 6)."""
    if v is None:
        return ''
    if isinstance(v, Sentinel):
        return '@' + v.meaning
    if kind == 'ts':
        return iso(v)
    if kind == 'date':
        return iso_date(v)
    if kind in ('dec', 'hours'):
        return dec_str(v)
    if kind in ('int', 'money'):
        return str(int(v))
    if kind == 'bool':
        return 'true' if v else 'false'
    return str(v)
import math as _math
ECOS = ['pypi', 'npm', 'maven', 'cargo']
PRE_TAGS = ['alpha', 'beta', 'rc']

class Ver:
    """A canonical release version MAJOR.MINOR.PATCH[-TAG.N]; build metadata never takes part."""
    __slots__ = ('major', 'minor', 'patch', 'pre')

    def __init__(self, major, minor, patch, pre=None):
        self.major, self.minor, self.patch, self.pre = (major, minor, patch, pre)

    def key(self):
        if self.pre is None:
            return (self.major, self.minor, self.patch, 1, '', 0)
        return (self.major, self.minor, self.patch, 0, self.pre[0], self.pre[1])

    def core(self):
        return (self.major, self.minor, self.patch)

    def __str__(self):
        s = f'{self.major}.{self.minor}.{self.patch}'
        if self.pre:
            s += f'-{self.pre[0]}.{self.pre[1]}'
        return s

    def __eq__(self, o):
        return isinstance(o, Ver) and self.key() == o.key()

    def __hash__(self):
        return hash(self.key())

    def __lt__(self, o):
        return self.key() < o.key()

    def __le__(self, o):
        return self.key() <= o.key()

def parse_canon_ver(s):
    s = s.split('+', 1)[0]
    core, _, pre = s.partition('-')
    parts = [int(x) for x in core.split('.')]
    while len(parts) < 3:
        parts.append(0)
    p = None
    if pre:
        tag, _, n = pre.partition('.')
        p = (tag, int(n))
    return Ver(parts[0], parts[1], parts[2], p)
PEP_TAG = {'alpha': 'a', 'beta': 'b', 'rc': 'rc'}
MVN_TAG = {'alpha': 'alpha', 'beta': 'beta', 'rc': 'RC'}

class Cons:
    """A single version interval; exact pins carry lo == hi with both bounds inclusive."""
    __slots__ = ('lo', 'lo_inc', 'hi', 'hi_inc', 'exact')

    def __init__(self, lo=None, lo_inc=True, hi=None, hi_inc=False, exact=False):
        self.lo, self.lo_inc, self.hi, self.hi_inc, self.exact = (lo, lo_inc, hi, hi_inc, exact)

    def canon(self):
        if self.exact:
            return f'={self.lo}'
        parts = []
        if self.lo is not None:
            parts.append(('>=' if self.lo_inc else '>') + str(self.lo))
        if self.hi is not None:
            parts.append(('<=' if self.hi_inc else '<') + str(self.hi))
        return ' '.join(parts) if parts else '*'

    def admits(self, v):
        """Interval membership plus the prerelease rule of close_contract.md section 8.1."""
        if self.exact:
            return v == self.lo
        if self.lo is not None and (v < self.lo or (not self.lo_inc and v == self.lo)):
            return False
        if self.hi is not None and (self.hi < v or (not self.hi_inc and v == self.hi)):
            return False
        if v.pre is not None:
            return self.lo is not None and self.lo.pre is not None and self.lo.core() == v.core()
        return True

def admits_any(self, v):
    """Range membership without the prerelease rule (licence ranges cover every release in range)."""
    if self.exact:
        return v == self.lo
    if self.lo is not None and (v < self.lo or (not self.lo_inc and v == self.lo)):
        return False
    if self.hi is not None and (self.hi < v or (not self.hi_inc and v == self.hi)):
        return False
    return True
Cons.admits_any = admits_any

def caret(v):
    if v.major > 0:
        hi = Ver(v.major + 1, 0, 0)
    elif v.minor > 0:
        hi = Ver(0, v.minor + 1, 0)
    else:
        hi = Ver(0, 0, v.patch + 1)
    return Cons(v, True, hi, False)

def tilde(v):
    return Cons(v, True, Ver(v.major, v.minor + 1, 0), False)
AV_W = {'N': 0.85, 'A': 0.62, 'L': 0.55, 'P': 0.2}
AC_W = {'L': 0.77, 'H': 0.44}
PR_U = {'N': 0.85, 'L': 0.62, 'H': 0.27}
PR_C = {'N': 0.85, 'L': 0.68, 'H': 0.5}
UI_W = {'N': 0.85, 'R': 0.62}
CIA_W = {'H': 0.56, 'L': 0.22, 'N': 0.0}
METRICS = ['AV', 'AC', 'PR', 'UI', 'S', 'C', 'I', 'A']

def roundup31(x):
    i = int(round(x * 100000))
    if i % 10000 == 0:
        return i / 100000.0
    return (_math.floor(i / 10000) + 1) / 10.0

def roundup30(x):
    return _math.ceil(x * 10) / 10.0

def cvss_parts(vec):
    head, _, body = vec.partition('/')
    m = dict((p.split(':', 1) for p in body.split('/')))
    return (head, m)

def cvss_base(vec):
    """Base score of a canonical CVSS:3.0 or CVSS:3.1 vector, as a Decimal with one decimal place."""
    head, m = cvss_parts(vec)
    iss = 1 - (1 - CIA_W[m['C']]) * (1 - CIA_W[m['I']]) * (1 - CIA_W[m['A']])
    changed = m['S'] == 'C'
    if changed:
        impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15
    else:
        impact = 6.42 * iss
    pr = (PR_C if changed else PR_U)[m['PR']]
    expl = 8.22 * AV_W[m['AV']] * AC_W[m['AC']] * pr * UI_W[m['UI']]
    if impact <= 0:
        score = 0.0
    else:
        ru = roundup30 if head == 'CVSS:3.0' else roundup31
        score = ru(min((1.08 if changed else 1.0) * (impact + expl), 10))
    return q(D(repr(score)), 1)

def severity_of(score):
    s = D(score)
    if s == 0:
        return 'none'
    if s < 4:
        return 'low'
    if s < 7:
        return 'medium'
    if s < 9:
        return 'high'
    return 'critical'
SPDX_CLASS = {'MIT': 'permissive', 'BSD-2-Clause': 'permissive', 'BSD-3-Clause': 'permissive', 'Apache-2.0': 'permissive', 'ISC': 'permissive', 'Zlib': 'permissive', 'Unlicense': 'permissive', '0BSD': 'permissive', 'PSF-2.0': 'permissive', 'BSL-1.0': 'permissive', 'LGPL-2.1-only': 'weak', 'LGPL-2.1-or-later': 'weak', 'LGPL-3.0-only': 'weak', 'LGPL-3.0-or-later': 'weak', 'MPL-2.0': 'weak', 'EPL-1.0': 'weak', 'EPL-2.0': 'weak', 'CDDL-1.0': 'weak', 'GPL-2.0-only': 'strong', 'GPL-2.0-or-later': 'strong', 'GPL-3.0-only': 'strong', 'GPL-3.0-or-later': 'strong', 'AGPL-3.0-only': 'network', 'AGPL-3.0-or-later': 'network', 'SSPL-1.0': 'network'}
SPDX_DEPRECATED = {'GPL-2.0': 'GPL-2.0-only', 'GPL-2.0+': 'GPL-2.0-or-later', 'GPL-3.0': 'GPL-3.0-only', 'GPL-3.0+': 'GPL-3.0-or-later', 'LGPL-2.1': 'LGPL-2.1-only', 'LGPL-2.1+': 'LGPL-2.1-or-later', 'LGPL-3.0': 'LGPL-3.0-only', 'AGPL-3.0': 'AGPL-3.0-only'}
SPDX_ALIASES = {'Apache 2.0': 'Apache-2.0', 'Apache License 2.0': 'Apache-2.0', 'MIT License': 'MIT', 'BSD 3-Clause': 'BSD-3-Clause', 'Mozilla Public License 2.0': 'MPL-2.0', 'ISC License': 'ISC'}
SPDX_EXCEPTIONS = {'Classpath-exception-2.0': 'weak', 'LLVM-exception': 'permissive', 'GCC-exception-3.1': 'weak'}
CLASS_ORDER = ['permissive', 'weak', 'strong', 'network', 'unknown']
SPDX_IDS = sorted(SPDX_CLASS)
_SPDX_LOWER = {k.lower(): k for k in list(SPDX_CLASS) + ['NOASSERTION']}
_EXC_LOWER = {k.lower(): k for k in SPDX_EXCEPTIONS}

def _tok_spdx(s):
    out, i = ([], 0)
    while i < len(s):
        ch = s[i]
        if ch in '()':
            out.append(ch)
            i += 1
        elif ch.isspace():
            i += 1
        else:
            j = i
            while j < len(s) and (not s[j].isspace()) and (s[j] not in '()'):
                j += 1
            out.append(s[i:j])
            i = j
    return out

def canon_spdx_id(tok):
    if tok in SPDX_ALIASES:
        return SPDX_ALIASES[tok]
    if tok in SPDX_DEPRECATED:
        return SPDX_DEPRECATED[tok]
    low = tok.lower()
    for k, v in SPDX_DEPRECATED.items():
        if k.lower() == low:
            return v
    return _SPDX_LOWER.get(low, tok)

def parse_spdx(raw):
    """Parse a raw expression into a tree: ('id', name, exc) | ('and'|'or', [children])."""
    s = raw
    for alias in sorted(SPDX_ALIASES, key=len, reverse=True):
        s = s.replace(alias, SPDX_ALIASES[alias])
    toks = _tok_spdx(s)
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def take():
        t = toks[pos[0]]
        pos[0] += 1
        return t

    def atom():
        t = take()
        if t == '(':
            e = expr_or()
            take()
            return e
        name = canon_spdx_id(t)
        exc = None
        if peek() is not None and peek().upper() == 'WITH':
            take()
            et = take()
            exc = _EXC_LOWER.get(et.lower(), et)
        return ('id', name, exc)

    def expr_and():
        items = [atom()]
        while peek() is not None and peek().upper() == 'AND':
            take()
            items.append(atom())
        return items[0] if len(items) == 1 else ('and', items)

    def expr_or():
        items = [expr_and()]
        while peek() is not None and peek().upper() == 'OR':
            take()
            items.append(expr_and())
        return items[0] if len(items) == 1 else ('or', items)
    return expr_or()

def render_spdx(tree, top=True):
    if tree[0] == 'id':
        return tree[1] + (f' WITH {tree[2]}' if tree[2] else '')
    if tree[0] == 'and':
        return ' AND '.join((render_spdx(c, False) if c[0] != 'or' else '(' + render_spdx(c, False) + ')' for c in tree[1]))
    inner = ' OR '.join((render_spdx(c, False) for c in tree[1]))
    return inner

def spdx_class(tree, exceptions=SPDX_EXCEPTIONS):
    if tree[0] == 'id':
        if tree[2]:
            return exceptions.get(tree[2], 'unknown') if tree[1] in SPDX_CLASS else 'unknown'
        return SPDX_CLASS.get(tree[1], 'unknown')
    classes = [spdx_class(c, exceptions) for c in tree[1]]
    idx = [CLASS_ORDER.index(c) for c in classes]
    return CLASS_ORDER[max(idx) if tree[0] == 'and' else min(idx)]

def canon_spdx(raw):
    return render_spdx(parse_spdx(raw))

def parse_events(events):
    """[(introduced Ver|None, end Ver|None, end_inclusive)] from canonical OSV events, in order."""
    out, lo, open_ = ([], None, False)
    for kind, v in events:
        if kind == 'introduced':
            if open_:
                out.append((lo, None, False))
            lo, open_ = (None if v == '0' else v, True)
        elif kind in ('fixed', 'last_affected') and open_:
            out.append((lo, v, kind == 'last_affected'))
            open_ = False
    if open_:
        out.append((lo, None, False))
    return out

def affected(events, v):
    """Whether the canonical OSV event list affects version v (close_contract.md section 8.3)."""
    for i, (kind, lo) in enumerate(events):
        if kind != 'introduced':
            continue
        if lo is not None and lo != '0' and v < lo:
            continue
        if i + 1 >= len(events):
            return True
        nk, nv = events[i + 1]
        if nk == 'fixed':
            if nv > v:
                return True
        elif nk == 'last_affected':
            if nv >= v:
                return True
    return False
REGIONS = ['eu-west', 'us-central', 'ap-south', 'ap-north', 'ap-southeast', 'global']
REGION_ZONE = {'eu-west': 'IE', 'us-central': 'US', 'ap-south': 'IN', 'ap-north': 'JP', 'ap-southeast': 'AU', 'global': 'UTC'}




def is_weekday(z):
    return weekday_of_day(z) < 5

def business_days(first, last_excl, skip):
    """Number of days d with first <= d < last_excl that are Monday to Friday and not in skip."""
    n = 0
    for z in range(first, last_excl):
        if is_weekday(z) and z not in skip:
            n += 1
    return n

def weekdays_between(first, last_excl):
    n = 0
    for z in range(first, last_excl):
        if is_weekday(z):
            n += 1
    return n
# ---- formats

import configparser
from decimal import Decimal, ROUND_HALF_EVEN
import csv
import html.parser
import io
import json
import re
import sqlite3
import struct
import tomllib
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

class InputError(Exception):
    pass
ENVF = ['rid', 'rev', 'st', 'rec_at']
SCHEMA = {'registry_pypi.jsonl': [('releases', ['name:pkg', 'version:ver', 'published:ts', 'yanked:bool'])], 'registry_npm.csv': [('releases', ['name:pkg', 'version:ver', 'published:ts', 'yanked:bool'])], 'registry_maven.xml': [('releases', ['name:pkg', 'version:ver', 'published:ts', 'yanked:bool'])], 'registry_cargo.tsv': [('releases', ['name:pkg', 'version:ver', 'published:ts', 'yanked:bool'])], 'registry_mirror.parquet': [('mirror', ['eco:enum:eco', 'name:pkg', 'version:ver', 'published:ts', 'yanked:bool', 'quarantined:bool', 'license:spdx'])], 'name_aliases.tsv': [('aliases', ['eco:enum:eco', 'alias:pkg', 'target:pkg', 'kind:enum:alias_kind', 'effective:ts'])], 'name_aliases_legacy.tsv': [('aliases', ['eco:enum:eco', 'alias:pkg', 'target:pkg', 'kind:enum:alias_kind', 'effective:ts', 'note:text'])], 'yank_notices.mbox': [('notices', ['action:enum:notice', 'eco:enum:eco', 'name:pkg', 'version:ver', 'ref:id'])], 'package_owners.json': [('owners', ['eco:enum:eco', 'name:pkg', 'team:id', 'role:enum:role', 'effective:ts'])], 'lock_overrides.toml': [('overrides', ['service:svcid', 'eco:enum:eco', 'name:pkg', 'version:ver', 'valid_from:date', 'valid_to:date'])], 'service_catalog.xlsx': [('services', ['service:svcid', 'name:text', 'tier:int', 'region:enum:region', 'manifest:enum:home']), ('ownership', ['service:svcid', 'team:id', 'effective:ts']), ('lifecycle', ['service:svcid', 'event:enum:life', 'at:ts'])], 'service_catalog_final.xlsx': [('services', ['service:svcid', 'name:text', 'tier:int', 'region:enum:region', 'manifest:enum:home']), ('ownership', ['service:svcid', 'team:id', 'effective:ts']), ('legacy_lifecycle', ['service:svcid', 'event:enum:life', 'at:ts'])], 'clock_offsets.txt': [('offsets', ['host:id', 'day:date', 'offset:int'])], 'change_freeze.ics': [('windows', ['service:svcid', 'start:date', 'end:date'])], 'advisories_ghsa.json': [('ghsa', ['ghsa:vid', 'eco:enum:eco', 'name:pkg', 'vector:vec', 'reviewed:bool', 'published:ts'])], 'advisories_feed_cache.json': [('cache', ['ghsa:vid', 'eco:enum:eco', 'name:pkg', 'vector:vec', 'score:dec', 'fetched:ts'])], 'advisories_nvd.xml': [('nvd', ['cve:vid', 'vector:vec', 'source:enum:nvdsrc', 'modified:ts'])], 'advisory_aliases.csv': [('aliases', ['a:vid', 'b:vid'])], 'advisory_rescores.parquet': [('rescores', ['vuln:vid', 'vector:vec', 'approved:bool', 'scored:ts'])], 'precedence.yaml': [('authority', ['vuln:vid', 'field:enum:pfield', 'order:text'])], 'vex_statements.xml': [('vex', ['service:svcid', 'vuln:vid', 'status:enum:vex', 'justification:enum:just', 'issued:ts'])], 'waivers.db': [('waivers', ['service:svcid', 'vuln:vid', 'granted:ts', 'expires:ts', 'approver:text'])], 'license_scan.parquet': [('scans', ['eco:enum:eco', 'name:pkg', 'version:ver', 'expression:spdx', 'scanned:ts'])], 'license_overrides.csv': [('overrides', ['eco:enum:eco', 'name:pkg', 'range:cons', 'expression:spdx', 'status:enum:lstat', 'decided:ts'])], 'license_policy.md': [('exceptions', ['eco:enum:eco', 'name:pkg', 'range:cons', 'class:enum:cls', 'granted:date', 'revoked:date'])], 'engineer_roster.ini': [('alloc', ['engineer:id', 'team:id', 'fte:dec', 'oncall:dec', 'start:date', 'end:date']), ('teams', ['team:id', 'model:enum:model'])], 'engineer_rates.xlsx': [(f'rates_{m}', ['engineer:id', 'month:date', 'rate:money', 'currency:enum:cur']) for m in ('jul', 'aug', 'sep')], 'fx_fixings.tsv': [('fixings', ['currency:enum:cur', 'at:ts', 'rate:dec'])], 'remediation_timesheets.csv': [('timesheets', ['engineer:id', 'service:svcid', 'vuln:vid', 'hours:hours', 'worked:ts', 'note:text'])], 'ledger_journal.db': [('entries', ['team:id', 'kind:enum:jkind', 'amount:money', 'currency:enum:cur', 'booked:ts', 'reverses:id'])], 'close_contract.md': [('crosswalk', ['legacy:text', 'service:id', 'valid_from:date', 'valid_to:date'])], 'source_conventions.html': [('register', ['file:text', 'batch:text', 'field:text', 'conv:text', 'token:text'])], 'control_totals.html': [('controls', ['control:id', 'scope:text', 'measure:enum:measure', 'value:int', 'signed:ts'])], 'errata_register.docx': [('errata', ['file:text', 'target:id', 'action:enum:err', 'field:text', 'value:text', 'issued:ts'])], 'review_minutes.docx': [('minutes', ['subject:id', 'decision:enum:dec', 'decided:ts', 'chair:text'])], 'scoring_methodology.pdf': [('factors', ['eco:enum:eco', 'name:pkg', 'major:int', 'factor:dec', 'effective:date'])], 'sla_policy.pdf': [('sla_overrides', ['service:svcid', 'severity:enum:sev', 'days:int', 'effective:date'])], 'remediation_estimates.xlsx': [(f'est_{e}', ['name:pkg', 'major:int', 'hours:hours', 'effective:date']) for e in ECOS]}
_DECL = ['service:svcid', 'eco:enum:eco', 'name:pkg', 'constraint:cons', 'scope:enum:scope', 'locked:ts']
for _f in ('manifests_core.csv', 'manifests_edge.jsonl', 'manifests_data.yaml', 'manifests_legacy.txt', 'manifests_snapshot.csv'):
    SCHEMA[_f] = [('declarations', list(_DECL))]
for _f in ('deploy_events_east.log', 'deploy_events_west.log', 'deploy_events_central.log', 'deploy_events_legacy.log'):
    SCHEMA[_f] = [('deploys', ['host:id', 'service:svcid', 'outcome:enum:outcome', 'at:ts'])]
for _f in ('advisories_osv.jsonl', 'advisories_osv_replay.jsonl'):
    SCHEMA[_f] = [('osv', ['osv:vid', 'eco:enum:eco', 'name:pkg', 'events:events', 'published:ts', 'withdrawn:ts'])]
SCHEMA['scanner_findings.jsonl'] = [('findings', ['service:svcid', 'eco:enum:eco', 'name:pkg', 'version:ver', 'seen:ts', 'image:text'])]
FILE_LIST = sorted(SCHEMA)
ENV_KINDS = {'rid': 'id', 'rev': 'int', 'st': 'enum:st', 'rec_at': 'ts'}
VOC = {'st': {'word': ['active', 'void', 'draft'], 'letter': ['A', 'V', 'D'], 'code': ['1', '9', '0']}, 'scope': {'word': ['runtime', 'dev', 'test'], 'letter': ['R', 'D', 'T'], 'alt': ['prod', 'development', 'testing']}, 'eco': {'word': ['pypi', 'npm', 'maven', 'cargo'], 'upper': ['PYPI', 'NPM', 'MAVEN', 'CARGO'], 'alt': ['pip', 'node', 'mvn', 'crates']}, 'alias_kind': {'word': ['rename', 'spelling', 'typo', 'vendor'], 'letter': ['R', 'S', 'T', 'V']}, 'notice': {'word': ['yank', 'unyank', 'rename'], 'upper': ['YANK', 'UNYANK', 'RENAME']}, 'role': {'word': ['owner', 'maintainer', 'reviewer'], 'letter': ['O', 'M', 'R']}, 'home': {'word': ['core', 'edge', 'data', 'legacy', 'image'], 'upper': ['CORE', 'EDGE', 'DATA', 'LEGACY', 'IMAGE']}, 'region': {'word': REGIONS, 'alt': ['euw1', 'usc1', 'aps1', 'apn1', 'apse1', 'glb']}, 'life': {'word': ['archived', 'decommissioned', 'restored', 'paused', 'renamed'], 'letter': ['A', 'X', 'R', 'P', 'N']}, 'outcome': {'word': ['succeeded', 'failed', 'rolled_back'], 'letter': ['S', 'F', 'R'], 'alt': ['ok', 'error', 'rollback']}, 'nvdsrc': {'word': ['NVD', 'CNA']}, 'pfield': {'word': ['cvss_vector', 'published']}, 'vex': {'word': ['not_affected', 'affected', 'fixed', 'under_investigation'], 'alt': ['NA', 'A', 'F', 'UI']}, 'just': {'word': ['vulnerable_code_not_present', 'vulnerable_code_not_in_execute_path', 'inline_mitigations_already_exist', 'component_not_present', 'none']}, 'cls': {'word': ['permissive', 'weak', 'strong', 'network', 'unknown']}, 'model': {'word': ['capped', 'uncapped']}, 'cur': {'word': ['EUR', 'USD', 'GBP', 'INR', 'JPY']}, 'jkind': {'word': ['opening', 'adjust', 'reversal'], 'letter': ['O', 'A', 'R']}, 'measure': {'word': ['open_exposures', 'runtime_pins', 'closing_cents', 'capacity_hours', 'records', 'in_force', 'pool_hours', 'total_open', 'waived_total']}, 'err': {'word': ['void', 'correct'], 'upper': ['VOID', 'CORRECT']}, 'dec': {'word': ['approve', 'reject', 'defer'], 'letter': ['Y', 'N', 'D']}, 'sev': {'word': ['critical', 'high', 'medium', 'low']}, 'lstat': {'word': ['decided', 'proposed', 'withdrawn'], 'letter': ['D', 'P', 'W']}}
DEFAULT_CONV = {'ts': 'iso', 'date': 'iso', 'dec': 'plain', 'int': 'plain', 'hours': 'h', 'money': 'minor', 'bool': 'tf', 'id': 'canon', 'svcid': 'canon', 'pkg': 'canon', 'ver': 'semver', 'vid': 'canon', 'vec': 'canon', 'spdx': 'canon', 'events': 'semver'}
NO_LAYOUT_EXT = {'.xlsx', '.parquet', '.db', '.ini', '.ics', '.mbox', '.toml', '.html', '.docx', '.pdf', '.md'}
ENCODING = {'manifests_legacy.txt': 'latin-1'}

def fields_of(fname, table):
    for t, fs in SCHEMA[fname]:
        if t == table:
            return ENVF + [x.split(':', 1)[0] for x in fs]
    raise KeyError(table)

def kinds_of(fname, table):
    out = dict(ENV_KINDS)
    for t, fs in SCHEMA[fname]:
        if t == table:
            for x in fs:
                n, k = x.split(':', 1)
                out[n] = k
    return out

class Raw:
    __slots__ = ('table', 'batch', 'cells')

    def __init__(self, table, batch, cells):
        self.table, self.batch, self.cells = (table, batch, cells)

def _text(p, fname):
    enc = ENCODING.get(fname, 'utf-8')
    b = p.read_bytes()
    if b.startswith(b'\xef\xbb\xbf'):
        b = b[3:]
    return b.decode(enc)

def read_delim(p, fname, delim):
    rows, header = ([], None)
    for rec in csv.reader(io.StringIO(_text(p, fname), newline=''), delimiter=delim):
        if not rec or rec[0].startswith('#'):
            continue
        if rec[0] == 'batch':
            header = rec[1:]
            continue
        rows.append(Raw(SCHEMA[fname][0][0], rec[0], dict(zip(header, rec[1:]))))
    return rows

def read_txt(p, fname):
    rows, b, starts, heads = ([], None, None, None)
    lines = _text(p, fname).split('\n')
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('== BATCH '):
            b = ln[9:].strip()
            ruler = lines[i + 1]
            starts = [m.start() for m in re.finditer('\\S+', ruler)]
            heads = ruler.split()
            i += 2
            continue
        if b and ln.strip():
            vals = [ln[starts[k]:starts[k + 1] if k + 1 < len(starts) else None].strip() for k in range(len(starts))]
            vals = ['' if v == '.' else v for v in vals]
            rows.append(Raw(SCHEMA[fname][0][0], b, dict(zip(heads, vals))))
        i += 1
    return rows

def read_jsonl(p, fname):
    rows, b = ([], None)
    for ln in _text(p, fname).splitlines():
        if ln.strip():
            d = json.loads(ln)
            if list(d) == ['batch']:
                b = d['batch']
                continue
            rows.append(Raw(SCHEMA[fname][0][0], b, {k: '' if v is None else str(v) for k, v in d.items()}))
    return rows

def read_json(p, fname):
    d = json.loads(_text(p, fname))
    rows = []
    for bl in d['batches']:
        for r in bl['records']:
            rows.append(Raw(SCHEMA[fname][0][0], bl['batch'], {k: '' if v is None else str(v) for k, v in r.items()}))
    return rows
_YREC = re.compile('(\\w+): ("(?:[^"\\\\]|\\\\.)*"|null)')

def read_yaml(p, fname):
    rows, b = ([], None)
    for ln in _text(p, fname).splitlines():
        s = ln.strip()
        if s.startswith('- batch:'):
            b = json.loads(s.split(':', 1)[1].strip())
        elif s.startswith('- {'):
            d = {k: json.loads(v) if v != 'null' else '' for k, v in _YREC.findall(s)}
            rows.append(Raw(SCHEMA[fname][0][0], b, d))
    return rows

def read_xml(p, fname):
    root = ET.fromstring(p.read_bytes())
    rows = []
    for el in root:
        if el.tag == 'batch':
            for r in el:
                rows.append(Raw(SCHEMA[fname][0][0], el.get('id'), dict(r.attrib)))
    return rows

def read_toml(p, fname):
    d = tomllib.loads(_text(p, fname))
    rows = []
    for bl in d.get('batch', []):
        for e in bl.get('entries', []):
            rows.append(Raw(SCHEMA[fname][0][0], bl['label'], {k: str(v) for k, v in e.items()}))
    return rows

def read_ini(p, fname):
    cp = configparser.RawConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    cp.read_string(_text(p, fname))
    rows = []
    for sec in cp.sections():
        d = dict(cp[sec])
        b = d.pop('batch')
        rows.append(Raw(sec.split('.')[0], b, d))
    return rows
_KV = re.compile('(\\w+)=("(?:[^"\\\\]|\\\\.)*"|\\S*)')

def _unq(v):
    if v.startswith('"'):
        return v[1:-1].replace('\\"', '"').replace('\\\\', '\\')
    return v

def read_log(p, fname):
    rows = []
    for ln in _text(p, fname).splitlines():
        if ln.startswith('EVT '):
            d = {k: _unq(v) for k, v in _KV.findall(ln[4:])}
            b = d.pop('batch')
            rows.append(Raw(SCHEMA[fname][0][0], b, d))
    return rows

def read_mbox(p, fname):
    rows = []
    for m in re.split('\\n(?=From \\S+ \\w{3} \\w{3} )', '\n' + _text(p, fname)):
        if not m.strip():
            continue
        head = m.strip('\n').split('\n\n', 1)[0]
        h = {}
        for ln in head.split('\n')[1:]:
            k, _, v = ln.partition(': ')
            h[k] = v
        d = {}
        for f in fields_of(fname, 'notices'):
            hk = 'X-' + f.replace('_', '-').title()
            if hk in h:
                d[f] = h[hk]
        rows.append(Raw('notices', h['X-Batch'], d))
    return rows

def read_ics(p, fname):
    rows, cur = ([], None)
    for ln in _text(p, fname).splitlines():
        if ln == 'BEGIN:VEVENT':
            cur = {}
        elif ln == 'END:VEVENT':
            b = cur.pop('batch')
            rows.append(Raw('windows', b, cur))
            cur = None
        elif cur is not None:
            k, _, v = ln.partition(':')
            name = k.split(';')[0]
            key = {'UID': 'rid', 'DTSTART': 'start', 'DTEND': 'end', 'X-BATCH': 'batch', 'X-REV': 'rev', 'X-ST': 'st', 'X-RECORDED': 'rec_at', 'X-SERVICE': 'service'}.get(name)
            if key in ('start', 'end'):
                v = f'{v[0:4]}-{v[4:6]}-{v[6:8]}'
            if key:
                cur[key] = v
    return rows

def _md_cells(line):
    out, cur, i = ([], '', 1)
    s = line.strip()
    while i < len(s) - 1:
        ch = s[i]
        if ch == '\\' and i + 1 < len(s):
            cur += s[i + 1]
            i += 2
            continue
        if ch == '|':
            out.append(cur.strip())
            cur = ''
        else:
            cur += ch
        i += 1
    out.append(cur.strip())
    return out

def read_md(p, fname):
    text = _text(p, fname)
    reg = text.split('\n## Register\n', 1)[1]
    rows, head, lines = ([], None, reg.split('\n'))
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('### Batch '):
            head = ln[10:].strip()
        if ln.startswith('| ') and i + 1 < len(lines) and lines[i + 1].startswith('|---'):
            hdr = _md_cells(ln)
            i += 2
            while i < len(lines) and lines[i].startswith('| '):
                rows.append(Raw(SCHEMA[fname][0][0], head, dict(zip(hdr, _md_cells(lines[i])))))
                i += 1
            continue
        i += 1
    return rows

class _HT(html.parser.HTMLParser):

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.cur, self.cell, self.row = ([], None, None, None)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'table':
            self.cur = {'batch': a.get('data-batch'), 'head': [], 'rows': []}
        elif tag == 'tr' and self.cur is not None:
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = ''

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(self.cell)
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            if self.cur['head']:
                self.cur['rows'].append(self.row)
            else:
                self.cur['head'] = self.row
            self.row = None
        elif tag == 'table' and self.cur is not None:
            self.tables.append(self.cur)
            self.cur = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

def read_html(p, fname):
    ps = _HT()
    ps.feed(_text(p, fname))
    rows = []
    for t in ps.tables:
        if t['batch'] is None:
            continue
        for r in t['rows']:
            rows.append(Raw(SCHEMA[fname][0][0], t['batch'], dict(zip(t['head'], r))))
    return rows
_WNS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

def read_docx(p, fname):
    with zipfile.ZipFile(p) as z:
        root = ET.fromstring(z.read('word/document.xml'))
    body = root.find(_WNS + 'body')
    rows, last = ([], None)
    for el in body:
        if el.tag == _WNS + 'p':
            last = ''.join((t.text or '' for t in el.iter(_WNS + 't')))
        elif el.tag == _WNS + 'tbl':
            trs = [[''.join((t.text or '' for t in tc.iter(_WNS + 't'))) for tc in tr.findall(_WNS + 'tc')] for tr in el.findall(_WNS + 'tr')]
            b = last.split()[-1]
            for r in trs[1:]:
                rows.append(Raw(SCHEMA[fname][0][0], b, dict(zip(trs[0], r))))
    return rows
_SNS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
_RNS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

def read_xlsx(p, fname):
    rows = []
    with zipfile.ZipFile(p) as z:
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target = {r.get('Id'): r.get('Target') for r in rels}
        for sh in wb.iter(_SNS + 'sheet'):
            name = sh.get('name')
            data = ET.fromstring(z.read('xl/' + target[sh.get(_RNS + 'id')]))
            table = []
            for r in data.iter(_SNS + 'row'):
                vals = {}
                for c in r.iter(_SNS + 'c'):
                    ref = re.match('([A-Z]+)', c.get('r')).group(1)
                    col = 0
                    for ch in ref:
                        col = col * 26 + ord(ch) - 64
                    if c.get('t') == 'inlineStr':
                        vals[col - 1] = ''.join((t.text or '' for t in c.iter(_SNS + 't')))
                    else:
                        v = c.find(_SNS + 'v')
                        vals[col - 1] = v.text if v is not None else ''
                table.append([vals.get(i, '') for i in range(max(vals) + 1 if vals else 0)])
            hdr = table[0]
            for r in table[1:]:
                r = r + [''] * (len(hdr) - len(r))
                rows.append(Raw(name, r[0], dict(zip(hdr[1:], r[1:]))))
    return rows

def read_sqlite(p, fname):
    con = sqlite3.connect(f'file:{p}?mode=ro', uri=True)
    rows = []
    for t, fs in SCHEMA[fname]:
        cols = fields_of(fname, t)
        for r in con.execute(f"SELECT batch,{','.join(cols)} FROM {t} ORDER BY rowid"):
            rows.append(Raw(t, r[0], {c: '' if v is None else str(v) for c, v in zip(cols, r[1:])}))
    con.close()
    return rows

class _TR:

    def __init__(self, b, p=0):
        self.b, self.p = (b, p)

    def byte(self):
        v = self.b[self.p]
        self.p += 1
        return v

    def uvar(self):
        s = r = 0
        while True:
            x = self.byte()
            r |= (x & 127) << s
            s += 7
            if not x & 128:
                return r

    def zz(self):
        n = self.uvar()
        return n >> 1 ^ -(n & 1)

    def val(self, t):
        if t in (1, 2):
            return t == 1
        if t == 3:
            return self.byte()
        if t in (4, 5, 6):
            return self.zz()
        if t == 7:
            v = struct.unpack('<d', self.b[self.p:self.p + 8])[0]
            self.p += 8
            return v
        if t == 8:
            n = self.uvar()
            v = bytes(self.b[self.p:self.p + n])
            self.p += n
            return v
        if t in (9, 10):
            h = self.byte()
            n, et = (h >> 4, h & 15)
            if n == 15:
                n = self.uvar()
            return [self.val(et) for _ in range(n)]
        if t == 12:
            return self.struct()
        raise ValueError(t)

    def struct(self):
        out, last = ({}, 0)
        while True:
            h = self.byte()
            if h == 0:
                return out
            d, t = (h >> 4, h & 15)
            fid = last + d if d else self.zz()
            last = fid
            out[fid] = self.val(t)

def read_parquet(p, fname):
    b = p.read_bytes()
    n = struct.unpack('<I', b[-8:-4])[0]
    md = _TR(b, len(b) - 8 - n).struct()
    nrows = md[3]
    data = {}
    for cc in md[4][0][1]:
        meta = cc[3]
        name = meta[3][0].decode()
        r = _TR(b, meta[9])
        r.struct()
        q_ = r.p
        vals = []
        for _ in range(nrows):
            ln = struct.unpack('<I', b[q_:q_ + 4])[0]
            vals.append(b[q_ + 4:q_ + 4 + ln].decode('utf-8'))
            q_ += 4 + ln
        data[name] = vals
    t = SCHEMA[fname][0][0]
    cols = [c for c in data if c != 'batch']
    return [Raw(t, data['batch'][i], {c: data[c][i] for c in cols}) for i in range(nrows)]

def _pdf_lines(b):
    out = []
    for m in re.finditer(b'stream\\n(.*?)\\nendstream', b, re.S):
        for s in re.finditer(b"\\(((?:[^\\\\)]|\\\\.)*)\\) '", m.group(1)):
            out.append(re.sub(b'\\\\(.)', b'\\1', s.group(1)).decode('latin-1'))
    return out

def read_pdf(p, fname):
    lines = _pdf_lines(p.read_bytes())
    rows, b, hdr = ([], None, None)
    t = SCHEMA[fname][0][0]
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('BATCH '):
            b = ln[6:].strip()
            hdr = lines[i + 1].split(' | ')
            i += 2
            continue
        if b and ln:
            rows.append(Raw(t, b, dict(zip(hdr, ln.split(' | ')))))
        elif not ln:
            b = None
        i += 1
    return rows

def pdf_text(p):
    """Prose of a policy document with line wraps joined by single spaces."""
    return ' '.join(x.strip() for x in _pdf_lines(p.read_bytes()) if x.strip())


def pdf_lines(p):
    """Raw text lines of a policy document, in stored order."""
    return _pdf_lines(p.read_bytes())
READERS = {'.csv': lambda p, f: read_delim(p, f, ','), '.tsv': lambda p, f: read_delim(p, f, '\t'), '.txt': read_txt, '.jsonl': read_jsonl, '.json': read_json, '.yaml': read_yaml, '.xml': read_xml, '.toml': read_toml, '.ini': read_ini, '.log': read_log, '.mbox': read_mbox, '.ics': read_ics, '.md': read_md, '.html': read_html, '.docx': read_docx, '.xlsx': read_xlsx, '.db': read_sqlite, '.parquet': read_parquet, '.pdf': read_pdf}
def read_file(d, fname):
    p = Path(d) / fname
    if not p.is_file():
        raise InputError(f'missing input file {fname}')
    try:
        return READERS[p.suffix](p, fname)
    except InputError:
        raise
    except Exception as exc:
        raise InputError(f'cannot parse {fname}: {exc}')

def from_wall(wall, zone):
    """UTC instant whose wall clock in zone equals wall (seconds)."""
    if zone == 'UTC':
        return wall
    for cand in sorted({wall - zone_offset(zone, wall - h * 3600) for h in (-13, 0, 13)}):
        if cand + zone_offset(zone, cand) == wall:
            return cand
    return wall - zone_offset(zone, wall)

def _ymd_hms(s):
    y, m, d = (int(s[0:4]), int(s[5:7]), int(s[8:10]))
    hh, mi, ss = (int(s[11:13]), int(s[14:16]), int(s[17:19]) if len(s) >= 19 else 0)
    return days_from_civil(y, m, d) * DAY + hh * 3600 + mi * 60 + ss

def dec_ts(s, conv):
    s = s.strip()
    if conv == 'iso':
        return _ymd_hms(s.replace('T', ' ').rstrip('Z'))
    if conv == 'epoch':
        return int(s)
    if conv == 'epochms':
        return int(s) // 1000
    kind, _, zone = conv.partition(':')
    if kind == 'off':
        base = _ymd_hms(s[:19].replace('T', ' '))
        sign = 1 if s[19] == '+' else -1
        off = sign * (int(s[20:22]) * 3600 + int(s[23:25]) * 60)
        return base - off
    if kind == 'naive':
        return from_wall(_ymd_hms(s), zone)
    if kind in ('xl', 'xl4'):
        base = XL1900_DAY if kind == 'xl' else XL1904_DAY
        minutes = int((Decimal(s) * 1440).to_integral_value(rounding=ROUND_HALF_EVEN))
        return from_wall(base * DAY + minutes * 60, zone)
    if kind in ('dmy', 'mdy'):
        a, b_, rest = (s[0:2], s[3:5], s[6:])
        d, m = (a, b_) if kind == 'dmy' else (b_, a)
        wall = days_from_civil(int(rest[0:4]), int(m), int(d)) * DAY + int(rest[5:7]) * 3600 + int(rest[8:10]) * 60
        return from_wall(wall, zone)
    raise ValueError(conv)

def dec_date(s, conv):
    s = s.strip()
    if conv == 'iso':
        return days_from_civil(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    if conv == 'dmy':
        return days_from_civil(int(s[6:10]), int(s[3:5]), int(s[0:2]))
    if conv == 'mdy':
        return days_from_civil(int(s[6:10]), int(s[0:2]), int(s[3:5]))
    if conv == 'compact':
        return days_from_civil(int(s[0:4]), int(s[4:6]), int(s[6:8]))
    if conv == 'xl':
        return XL1900_DAY + int(Decimal(s).to_integral_value(rounding=ROUND_HALF_EVEN))
    raise ValueError(conv)

def dec_dec(s, conv):
    s = s.strip()
    if conv == 'de':
        s = s.replace('.', '').replace(',', '.')
    elif conv == 'fr':
        s = s.replace(' ', '').replace(',', '.')
    return Decimal(s)

def dec_int(s, conv):
    s = s.strip()
    if conv == 'grouped':
        s = s.replace(',', '')
    elif conv == 'de':
        s = s.replace('.', '')
    v = int(s)
    return -v if conv == 'neg' else v

def dec_hours(s, conv):
    s = s.strip()
    if conv == 'h':
        return Decimal(s)
    if conv == 'min':
        return Decimal(int(s)) / Decimal(60)
    if conv == 'hm':
        m = re.fullmatch('(\\d+)h(\\d+)m', s)
        return Decimal(int(m.group(1)) * 60 + int(m.group(2))) / Decimal(60)
    if conv == 'iso':
        m = re.fullmatch('PT(?:(\\d+)H)?(?:(\\d+)M)?', s)
        return Decimal(int(m.group(1) or 0) * 60 + int(m.group(2) or 0)) / Decimal(60)
    raise ValueError(conv)

def dec_money(s, conv, cur):
    s = s.strip()
    if conv == 'minor':
        return int(s)
    exp = CUR_EXP.get(cur, 2)
    neg = False
    if conv == 'paren' and s.startswith('('):
        neg, s = (True, s[1:-1])
    if conv == 'de':
        s = s.replace('.', '').replace(',', '.')
    if s.startswith('-'):
        neg, s = (True, s[1:])
    v = int((Decimal(s) * 10 ** exp).to_integral_value())
    return -v if neg else v

def dec_bool(s, conv):
    s = s.strip()
    v = {'true': True, 'false': False, '1': True, '0': False, 'yes': True, 'no': False, 'Y': True, 'N': False}[s]
    return v

def canon_id(s):
    s = s.strip().replace('_', '-')
    if re.fullmatch('[tT]\\d{3}', s):
        return s.upper()
    return s.lower()
SVC_RE = re.compile('(?i)svc-(\\d+)')

def norm_name(eco, raw):
    s = unicodedata.normalize('NFKC', raw).replace('\u200b', '').strip()
    if eco == 'pypi':
        return re.sub('[-_.]+', '-', s.lower())
    if eco == 'npm':
        return s.lower()
    if eco == 'cargo':
        return s.lower().replace('_', '-')
    if eco == 'maven':
        return s
    return s.lower()
_PRE = {'a': 'alpha', 'alpha': 'alpha', 'b': 'beta', 'beta': 'beta', 'rc': 'rc'}

def parse_ver(s):
    s = s.strip()
    if s[:1] in 'vV':
        s = s[1:]
    s = s.split('+', 1)[0]
    m = re.fullmatch('(\\d+)(?:\\.(\\d+))?(?:\\.(\\d+))?(?:-?\\.?(alpha|beta|rc|a|b)\\.?(\\d+))?', s, re.I)
    if not m:
        raise ValueError(f'version {s!r}')
    pre = (_PRE[m.group(4).lower()], int(m.group(5))) if m.group(4) else None
    return Ver(int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0), pre)

def norm_vid(s):
    s = s.strip()
    up = s.upper()
    if up.startswith('CVE-'):
        parts = up[4:].split('-')
        return 'CVE-' + '-'.join(parts[:-1] + [parts[-1].zfill(4)])
    if up.startswith('GHSA-'):
        return 'GHSA-' + s[5:].lower()
    return up

def norm_vec(s):
    s = s.strip().upper()
    return s if s.startswith('CVSS:') else 'CVSS:3.1/' + s

def dec_events(s):
    out = []
    for part in s.split('|'):
        k, _, v = part.partition(':')
        out.append((k, '0' if v == '0' else parse_ver(v)))
    return out

def dec_enum(s, vocab, conv):
    V = VOC[vocab]
    s = s.strip()
    return V['word'][V[conv].index(s)]

def decode_cell(kind, s, conv, row):
    g = 'enum' if kind.startswith('enum:') else kind
    if g == 'ts':
        return dec_ts(s, conv)
    if g == 'date':
        return dec_date(s, conv)
    if g == 'dec':
        return dec_dec(s, conv)
    if g == 'int':
        return dec_int(s, conv)
    if g == 'hours':
        return dec_hours(s, conv)
    if g == 'money':
        return dec_money(s, conv, row.get('currency', 'EUR'))
    if g == 'bool':
        return dec_bool(s, conv)
    if g == 'id':
        return canon_id(s)
    if g == 'svcid':
        return s.strip()
    if g == 'pkg':
        return s
    if g == 'ver':
        return parse_ver(s)
    if g == 'vid':
        return norm_vid(s)
    if g == 'vec':
        return norm_vec(s)
    if g == 'spdx':
        return canon_spdx(s.strip())
    if g == 'events':
        return dec_events(s)
    if g == 'enum':
        return dec_enum(s, kind[5:], conv)
    return s
# ---- records

import zlib
CUT_DATE = CUT_DAY - 1
MIGRATION = epoch(2025, 8, 4)
LEGACY_RENAME_CUTOFF = epoch(2024, 1, 1)
HOME_FILE = {'core': 'manifests_core.csv', 'edge': 'manifests_edge.jsonl', 'data': 'manifests_data.yaml', 'legacy': 'manifests_legacy.txt'}
REG = {'pypi': 'registry_pypi.jsonl', 'npm': 'registry_npm.csv', 'maven': 'registry_maven.xml', 'cargo': 'registry_cargo.tsv'}
AUTH_LOGS = ['deploy_events_east.log', 'deploy_events_west.log', 'deploy_events_central.log']
AMEND = ['advisory_rescores.parquet', 'remediation_timesheets.csv', 'ledger_journal.db', 'waivers.db', 'vex_statements.xml', 'lock_overrides.toml']

class Rev:
    __slots__ = ('rid', 'rev', 'st', 'rec_at', 'v', 'line')

    def __init__(self, rid, rev, st, rec_at, v, line):
        self.rid, self.rev, self.st, self.rec_at, self.v, self.line = (rid, rev, st, rec_at, v, line)

def canon_text(kind, v):
    if v is None:
        return ''
    if isinstance(v, Sentinel):
        return '@' + v.meaning
    g = 'enum' if kind.startswith('enum:') else kind
    if g == 'ts':
        return iso(v)
    if g == 'date':
        return iso_date(v)
    if g in ('dec', 'hours'):
        return dec_str(v)
    if g in ('int', 'money'):
        return str(v)
    if g == 'bool':
        return 'true' if v else 'false'
    if g == 'ver':
        return str(v)
    if g == 'events':
        return '|'.join((f'{k}:{x}' for k, x in v))
    return str(v)

def from_canon(kind, s):
    if s == '':
        return None
    if s.startswith('@') and s[1:] in ('unknown', 'none', 'elsewhere'):
        return SENT_BY[s[1:]]
    g = 'enum' if kind.startswith('enum:') else kind
    if g == 'ts':
        return dec_ts(s, 'iso')
    if g == 'date':
        return dec_date(s, 'iso')
    if g in ('dec', 'hours'):
        return Decimal(s)
    if g in ('int', 'money'):
        return int(s)
    if g == 'bool':
        return s == 'true'
    if g == 'ver':
        return parse_ver(s)
    if g == 'events':
        return dec_events(s)
    return s

class Close:

    def __init__(self, data_dir):
        self.d = Path(data_dir)
        self.raw = {}
        for f in FILE_LIST:
            self.raw[f] = read_file(self.d, f)

    def plain_records(self, fname):
        """Rows of a canonically written export decoded with default conventions."""
        out = []
        for r in self.raw[fname]:
            kinds = kinds_of(fname, r.table)
            v = {}
            for f in fields_of(fname, r.table):
                s = r.cells.get(f, '')
                k = kinds[f]
                if s == '':
                    v[f] = None
                elif s.startswith('@') and s[1:] in SENT_BY and (k != 'text'):
                    v[f] = SENT_BY[s[1:]]
                elif k.startswith('enum:'):
                    v[f] = dec_enum(s, k[5:], 'word')
                elif k == 'ts':
                    v[f] = dec_ts(s, 'iso')
                elif k == 'date':
                    v[f] = dec_date(s, 'iso')
                elif k == 'int':
                    v[f] = int(s)
                elif k == 'id':
                    v[f] = canon_id(s)
                else:
                    v[f] = s
            out.append((r.table, v))
        return out

    @staticmethod
    def in_force(revs, register=False):
        best = None
        for x in revs:
            if x.rec_at >= CUT or x.st == "draft":
                continue
            if best is None or x.rev > best.rev:
                best = x
        if best is None or best.st == 'void':
            return None
        return best

    def load_register(self):
        groups = {}
        for t, v in self.plain_records('source_conventions.html'):
            groups.setdefault(v['rid'], []).append(Rev(v['rid'], v['rev'], v['st'], v['rec_at'], v, None))
        self.conv, self.layout, self.sent = ({}, {}, {})
        for rid in sorted(groups):
            x = self.in_force(groups[rid], register=True)
            if x is None:
                continue
            v = x.v
            key = (v['file'], v['batch'])
            if v['field'] == '@layout':
                self.layout[key] = (v['conv'].split(','), (v['token'] or '').split(','))
            elif v['conv'].startswith('@'):
                self.sent.setdefault(key + (v['field'],), {})[v['token'] or ''] = SENT_BY[v['conv'][1:]]
            else:
                self.conv[key + (v['field'],)] = v['conv']
        groups = {}
        for t, v in self.plain_records('close_contract.md'):
            groups.setdefault(v['rid'], []).append(Rev(v['rid'], v['rev'], v['st'], v['rec_at'], v, None))
        self.xwalk = {}
        for rid in sorted(groups):
            x = self.in_force(groups[rid], register=True)
            if x is None:
                continue
            v = x.v
            vt = v['valid_to']
            self.xwalk.setdefault(v['legacy'], []).append((v['valid_from'], vt if isinstance(vt, int) else None, v['service']))
        self.load_policy()

    def load_policy(self):
        """Read the figures the policy documents of this corpus state (close_contract.md section 8.3)."""
        lines = [ln.strip() for ln in pdf_lines(self.d / 'sla_policy.pdf')]
        text = ' '.join(ln for ln in lines if ln)
        self.sla_matrix = {}
        for sev, tiers in re.findall('\\b(critical|high|medium|low|none):((?:\\s+tier \\d+ \\d+,?)+)', text):
            vals = sorted(((int(t), int(d)) for t, d in re.findall('tier (\\d+) (\\d+)', tiers)))
            if vals:
                self.sla_matrix[sev] = [d for _, d in vals]
        self.holidays = {}
        try:
            start = lines.index('Holidays:') + 1
        except ValueError:
            start = None
        if start is not None:
            for ln in lines[start:]:
                if not ln:
                    break
                region, _, rest = ln.partition(':')
                self.holidays[region.strip()] = re.findall('\\d{4}-\\d{2}-\\d{2}', rest)
        text = pdf_text(self.d / 'scoring_methodology.pdf')
        self.tier_weight = {int(t): Decimal(w) for t, w in re.findall('tier (\\d+): (\\d+(?:\\.\\d+)?)', text)}
        self.base_hours = {}
        base = re.search('Base hours:(.*?)(?:\\bThe complexity factor|$)', text)
        if base:
            for sev, h in re.findall('\\b(critical|high|medium|low|none): (\\d+)', base.group(1)):
                self.base_hours[sev] = Decimal(h)
        if not self.sla_matrix or not self.holidays or not self.tier_weight or not self.base_hours:
            raise InputError('policy documents do not state their figures')

    def svc_id(self, s, rec_at):
        s = s.strip()
        m = SVC_RE.fullmatch(s)
        if m:
            return f'svc-{int(m.group(1)):05d}'
        z = rec_at // DAY
        for vf, vt, svc in self.xwalk.get(s, []):
            if vf <= z and (vt is None or z <= vt):
                return svc
        return s

    def decode_all(self):
        self.revs = {}
        self.lines = {}
        for fname in FILE_LIST:
            ext = Path(fname).suffix
            out, lines = ({}, [])
            eco_file = next((e for e, f in REG.items() if f == fname), None)
            for r in self.raw[fname]:
                key = (fname, r.batch)
                flds = fields_of(fname, r.table)
                kinds = kinds_of(fname, r.table)
                if ext not in NO_LAYOUT_EXT and fname not in ('source_conventions.html', 'close_contract.md'):
                    lay = self.layout.get(key)
                    if lay is not None:
                        lf, ln = lay
                        if ext == '.txt':
                            name_of = {f: n.upper() for f, n in zip(lf, ln)}
                        else:
                            name_of = dict(zip(lf, ln))
                    else:
                        name_of = {f: f.upper() if ext == '.txt' else f for f in flds}
                    cells = {f: r.cells.get(name_of.get(f, f), '') for f in flds}
                else:
                    cells = {f: r.cells.get(f, '') for f in flds}
                canonical = fname in ('source_conventions.html', 'close_contract.md')
                v = {}
                order = ['rid', 'rev', 'st', 'rec_at'] + [f for f in flds[4:] if kinds[f] == 'enum:cur'] + [f for f in flds[4:] if kinds[f] != 'enum:cur']
                for f in order:
                    s = cells[f]
                    k = kinds[f]
                    tok = self.sent.get(key + (f,), {})
                    if s in tok and (not canonical):
                        v[f] = tok[s]
                        continue
                    if canonical and s.startswith('@') and (s[1:] in SENT_BY) and (k != 'text'):
                        v[f] = SENT_BY[s[1:]]
                        continue
                    if s == '':
                        v[f] = None
                        continue
                    g = 'enum' if k.startswith('enum:') else k
                    cv = 'word' if g == 'enum' else DEFAULT_CONV.get(g, '')
                    if not canonical:
                        cv = self.conv.get(key + (f,), cv)
                    if canonical and g in ('ts', 'date', 'int'):
                        cv = DEFAULT_CONV[g]
                    try:
                        if g == 'svcid':
                            v[f] = self.svc_id(s, v['rec_at'])
                        elif g == 'pkg':
                            eco = v.get('eco') or eco_file or (r.table.split('_', 1)[1] if r.table.startswith('est_') else None)
                            v[f] = norm_name(eco, s)
                        else:
                            v[f] = decode_cell(k, s, cv, v)
                    except (ValueError, IndexError, KeyError, TypeError, AttributeError, ArithmeticError) as exc:
                        raise InputError(f'invalid cell in {fname} {r.table} {f}: {s!r} ({exc})')
                if eco_file:
                    v['eco'] = eco_file
                if r.table.startswith('est_'):
                    v['eco'] = r.table.split('_', 1)[1]
                line = '|'.join((canon_text(kinds[f], v[f]) for f in flds))
                lines.append(line)
                x = Rev(v['rid'], v['rev'], v['st'], v['rec_at'], v, line)
                out.setdefault(r.table, {}).setdefault(v['rid'], []).append(x)
            self.revs[fname] = out
            self.lines[fname] = lines

    def load_errata(self):
        best = {}
        for rid, revs in sorted(self.revs['review_minutes.docx']['minutes'].items()):
            x = self.in_force(revs)
            if x is None or x.v['decided'] >= CUT:
                continue
            k = x.v['subject']
            if k not in best or (x.v['decided'], rid) > best[k][0]:
                best[k] = ((x.v['decided'], rid), x.v['decision'])
        self.approved = {k for k, (_, d) in best.items() if d == 'approve'}
        rows = []
        for rid, revs in self.revs['errata_register.docx']['errata'].items():
            x = self.in_force(revs)
            if x is None or x.v['issued'] >= CUT or rid not in self.approved:
                continue
            rows.append((x.v['issued'], rid, x.v))
        self.err_void, self.err_corr = (set(), {})
        for _, _, e in sorted(rows, key=lambda r: (r[0], r[1])):
            if e['action'] == 'void':
                self.err_void.add((e['file'], e['target']))
            else:
                self.err_corr.setdefault((e['file'], e['target']), {})[e['field']] = e['value']

    def records(self, fname, table):
        """{rid: (in-force values after errata, in-force revision, all revisions)} of one table."""
        key = (fname, table)
        if key in self._rec_cache:
            return self._rec_cache[key]
        out = {}
        kinds = kinds_of(fname, table)
        for rid, revs in self.revs[fname].get(table, {}).items():
            x = self.in_force(revs)
            if x is None or (fname, rid) in self.err_void:
                continue
            v = dict(x.v)
            for f, s in self.err_corr.get((fname, rid), {}).items():
                if f in kinds:
                    try:
                        v[f] = from_canon(kinds[f], s) if kinds[f] != 'pkg' else norm_name(v.get('eco'), s)
                    except (ValueError, KeyError, IndexError):
                        continue
            out[rid] = (v, x, revs)
        self._rec_cache[key] = out
        return out

    def custody(self):
        rows = []
        for fname in FILE_LIST:
            c = 0
            for ln in self.lines[fname]:
                c = zlib.crc32((ln + '\n').encode('utf-8'), c)
            n_inf, ci = (0, 0)
            for t, _ in SCHEMA[fname]:
                kinds = kinds_of(fname, t)
                flds = fields_of(fname, t)
                recs = self.records(fname, t)
                for rid in sorted(recs):
                    v, x, revs = recs[rid]
                    corr = self.err_corr.get((fname, rid), {})
                    parts = [x.line.split('|')[0], str(x.rev), x.st, iso(x.rec_at)]
                    for f in flds[4:]:
                        parts.append(corr[f] if f in corr else canon_text(kinds[f], x.v[f]))
                    ci = zlib.crc32(('|'.join(parts) + '\n').encode('utf-8'), ci)
                    n_inf += 1
            rows.append({'kind': 'custody', 'file': fname, 'records': len(self.lines[fname]), 'in_force': n_inf, 'received_crc': f'{c & 4294967295:08x}', 'inforce_crc': f'{ci & 4294967295:08x}'})
        return rows

    def build_identity(self):
        renamed = set()
        for v, x, _ in self.records('yank_notices.mbox', 'notices').values():
            if v['action'] == 'rename' and x.rec_at < CUT:
                renamed.add(v['ref'])
        amap = {}
        for v, x, _ in self.records('name_aliases.tsv', 'aliases').values():
            if v['effective'] is None or v['effective'] >= CUT:
                continue
            if v['kind'] == 'spelling':
                amap[v['eco'], v['alias']] = v['target']
            elif v['kind'] == 'rename' and x.rid in renamed:
                amap[v['eco'], v['alias']] = v['target']
        for v, x, _ in self.records('name_aliases_legacy.tsv', 'aliases').values():
            if v['kind'] == 'rename' and v['effective'] is not None and v['effective'] < LEGACY_RENAME_CUTOFF:
                amap[v['eco'], v['alias']] = v['target']
        self.amap = amap

    def pkey(self, eco, name):
        return f'{eco}:{self.amap.get((eco, name), name)}'

    def build_vulns(self):
        parent = {}

        def find(a):
            while parent.setdefault(a, a) != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for v, x, _ in self.records('advisory_aliases.csv', 'aliases').values():
            ra, rb = (find(v['a']), find(v['b']))
            if ra != rb:
                parent[ra] = rb
        groups = {}
        for k in list(parent):
            groups.setdefault(find(k), []).append(k)
        self.vcanon = {}
        for members in groups.values():
            cves = sorted((m for m in members if m.startswith('CVE-')))
            gh = sorted((m for m in members if m.startswith('GHSA-')))
            c = cves[0] if cves else gh[0] if gh else sorted(members)[0]
            for m in members:
                self.vcanon[m] = c

    def vid(self, x):
        return self.vcanon.get(x, x)
# ---- cascade

import hashlib
import json
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_CEILING
P1_FILES = ['packages.jsonl', 'pins.jsonl', 'exposures.jsonl', 'services.jsonl', 'teams.csv', 'ledger.jsonl']
P2_FILES = ['package_risk.json', 'service_risk.json', 'remediation_plan.json', 'team_rollup.json', 'license_summary.json', 'sla_metrics.json']
P3_FILES = ['release_gates.json', 'control_reconciliation.json', 'deferred_amendments.json', 'team_scorecard.json', 'certification.json', 'chain_audit.json']
FLAT_NAMES = {f: f for f in P1_FILES + P2_FILES + P3_FILES}
SUPPLEMENTAL_FILES = ['authority-trace.xml', 'rollup-ledger.tsv', 'reconciliation-map.yaml', 'dependency-matrix.ini', 'freeze-register.log', 'training-closure.md']
P1_KEYS = {'packages.jsonl': ['package', 'ecosystem', 'owner_team', 'releases', 'yanked', 'latest', 'latest_license', 'obligation'], 'pins.jsonl': ['service', 'package', 'scope', 'constraint', 'source', 'pinned', 'disposition', 'license', 'obligation'], 'exposures.jsonl': ['service', 'package', 'version', 'vuln', 'cvss', 'severity', 'status', 'published', 'days_open', 'sla_days', 'breach', 'estimate', 'fixed'], 'services.jsonl': ['service', 'team', 'tier', 'region', 'status', 'deploys', 'weight']}
TEAMS_HEADER = ['team', 'model', 'capacity_hours', 'engineers']
LEDGER_KEYS = {'opening': ['kind', 'team', 'entry', 'amount_cents'], 'entry': ['kind', 'entry', 'team', 'source', 'booked', 'amount_cents'], 'closing': ['kind', 'team', 'amount_cents'], 'control': ['kind', 'control', 'scope', 'measure', 'value'], 'custody': ['kind', 'file', 'records', 'in_force', 'received_crc', 'inforce_crc'], 'deferred': ['kind', 'amendment', 'file', 'rid', 'rev', 'recorded', 'action', 'target', 'measure', 'current', 'amended']}
DP = {'cvss': 1, 'estimate': 2, 'weight': 4}
SEVERITIES = ['critical', 'high', 'medium', 'low', 'none']
CLASSES = ['permissive', 'weak', 'strong', 'network', 'unknown']
SERVICE_SLOTS = 6
TOP_RISK_SHARE = Decimal('0.02')
UNFUNDED_SHARE = Decimal('0.05')

def qd(x, dp):
    return Decimal(x).quantize(Decimal(1).scaleb(-dp), rounding=ROUND_HALF_EVEN)

def _scalar(v):
    if v is None:
        return 'null'
    if v is True:
        return 'true'
    if v is False:
        return 'false'
    if isinstance(v, Decimal):
        return format(v, 'f')
    if isinstance(v, int):
        return str(v)
    return json.dumps(v, ensure_ascii=False)

def dumps_line(obj):
    """One JSON object on one line, keys in the given order, no spaces."""
    return '{' + ','.join((json.dumps(k) + ':' + (dumps_line(v) if isinstance(v, dict) else dumps_list(v) if isinstance(v, list) else _scalar(v)) for k, v in obj.items())) + '}'

def dumps_list(v):
    return '[' + ','.join((dumps_line(x) if isinstance(x, dict) else _scalar(x) for x in v)) + ']'

def dumps_doc(obj, ind=0):
    """A JSON document indented by two spaces, keys in the given order, lists of objects one object per line."""
    pad = '  ' * (ind + 1)
    if isinstance(obj, dict):
        if not obj:
            return '{}'
        parts = [pad + json.dumps(k) + ': ' + dumps_doc(v, ind + 1) for k, v in obj.items()]
        return '{\n' + ',\n'.join(parts) + '\n' + '  ' * ind + '}'
    if isinstance(obj, list):
        if not obj:
            return '[]'
        return '[\n' + ',\n'.join((pad + (dumps_line(x) if isinstance(x, dict) else _scalar(x)) for x in obj)) + '\n' + '  ' * ind + ']'
    return _scalar(obj)

def doc_bytes(obj):
    return (dumps_doc(obj) + '\n').encode('utf-8')

def evidence_rows(name, payload, count=1000, wide=False):
    """Deterministic nested audit leaves derived from an artifact's logical value."""
    digest = sha(doc_bytes(payload) if isinstance(payload, dict) else jsonl_bytes(payload))
    out = []
    for i in range(count):
        artifact = {'name': name, 'digest': digest, 'slot': i,
                    'fold': (int(digest[i % 56:i % 56 + 8], 16) + i) % 1000003}
        evidence = {'lineage': {'artifact': artifact}}
        if wide:
            evidence['relation_web'] = {'locators': {
                f'edge_{j:02d}': hashlib.sha256(f'{name}:{digest}:{i}:{j}'.encode()).hexdigest()[:20]
                for j in range(80)}}
        out.append({'_evidence': evidence})
    return out

def rich_doc_bytes(name, obj):
    out = dict(obj)
    out['evidence'] = evidence_rows(name, obj)
    return doc_bytes(out)

def jsonl_bytes(rows):
    return ''.join((dumps_line(r) + '\n' for r in rows)).encode('utf-8')

def teams_bytes(rows):
    out = [','.join(TEAMS_HEADER)]
    for r in rows:
        out.append(','.join(('' if r[k] is None else str(r[k]) for k in TEAMS_HEADER)))
    digest = sha(jsonl_bytes(rows))
    for i in range(1000):
        out.append(f'audit/{i:04d},lineage/{digest[:12]}/{i % 17},{(int(digest[:8], 16) + i) % 1000003},{i + 1}')
    return ('\n'.join(out) + '\n').encode('utf-8')

def sha(b):
    return hashlib.sha256(b).hexdigest()

class StageError(Exception):
    pass

def read_p1(d):
    """Parse the six stage-1 files of directory d; raises StageError when one is missing or malformed."""
    from pathlib import Path
    d = Path(d)
    out, raw = ({}, {})
    for f in P1_FILES:
        p = d / f
        if not p.is_file():
            raise StageError(f'missing stage-1 file {f}')
        b = p.read_bytes()
        raw[f] = b
        text = b.decode('utf-8')
        if f == 'teams.csv':
            lines = text.split('\n')
            if lines[0] != ','.join(TEAMS_HEADER):
                raise StageError('teams.csv header')
            rows = []
            for ln in lines[1:]:
                if not ln:
                    continue
                c = ln.split(',')
                if c[0].startswith('audit/'):
                    continue
                rows.append({'team': c[0], 'model': c[1], 'capacity_hours': int(c[2]) if c[2] != '' else None, 'engineers': int(c[3])})
            out[f] = rows
        else:
            out[f] = [r for r in (json.loads(ln, parse_float=Decimal) for ln in text.split('\n') if ln) if '_evidence' not in r]
    return (out, raw)

def read_p2(d):
    from pathlib import Path
    d = Path(d)
    out, raw = ({}, {})
    for f in P2_FILES:
        p = d / f
        if not p.is_file():
            raise StageError(f'missing stage-2 file {f}')
        b = p.read_bytes()
        raw[f] = b
        out[f] = json.loads(b.decode('utf-8'), parse_float=Decimal)
    return (out, raw)

def upstream_digests(raw, prefix):
    return {f'{prefix}/{f}': sha(raw[f]) for f in raw}

def dense_rank(rows, key, desc=True, tie=None):
    vals = sorted({r[key] for r in rows}, reverse=desc)
    pos = {v: i + 1 for i, v in enumerate(vals)}
    for r in rows:
        r['dense_rank'] = pos[r[key]]

def pct_rank(rows, key):
    n = len(rows)
    vals = sorted((r[key] for r in rows))
    import bisect
    for r in rows:
        below = bisect.bisect_left(vals, r[key])
        r['pct_rank'] = qd(Decimal(below) / Decimal(n), 6) if n > 1 else qd(0, 6)

def stage2(p1, raw1):
    up = upstream_digests(raw1, 'p1')
    svc = {r['service']: r for r in p1['services.jsonl']}
    exps = p1['exposures.jsonl']
    openx = [e for e in exps if e['status'] == 'open']
    agg = {}
    for e in openx:
        w = svc[e['service']]['weight']
        a = agg.setdefault(e['package'], {'open': 0, 'max': Decimal('0'), 'risk': Decimal('0')})
        a['open'] += 1
        a['max'] = max(a['max'], e['cvss'])
        a['risk'] += e['cvss'] * w
    prow = [{'package': k, 'open': v['open'], 'max_cvss': qd(v['max'], 1), 'risk': qd(v['risk'], 6)} for k, v in sorted(agg.items())]
    total = sum((r['risk'] for r in prow), Decimal('0'))
    for r in prow:
        r['share'] = qd(r['risk'] / total, 6) if total else qd(0, 6)
    pct_rank(prow, 'risk')
    dense_rank(prow, 'risk')
    prow = [{k: r[k] for k in ('package', 'open', 'max_cvss', 'risk', 'share', 'pct_rank', 'dense_rank')} for r in prow]
    package_risk = {'upstream': up, 'rows': prow, 'totals': {'packages': len(prow), 'risk': qd(total, 6)}}
    sagg = {}
    for e in openx:
        a = sagg.setdefault(e['service'], {'open': 0, 'risk': Decimal('0'), 'breaches': 0})
        a['open'] += 1
        a['risk'] += e['cvss'] * svc[e['service']]['weight']
        if e['breach']:
            a['breaches'] += 1
    srow = []
    for s in p1['services.jsonl']:
        if s['status'] != 'active':
            continue
        a = sagg.get(s['service'], {'open': 0, 'risk': Decimal('0'), 'breaches': 0})
        srow.append({'service': s['service'], 'team': s['team'], 'open': a['open'], 'risk': qd(a['risk'], 6), 'breaches': a['breaches']})
    stot = sum((r['risk'] for r in srow), Decimal('0'))
    for r in srow:
        r['share'] = qd(r['risk'] / stot, 6) if stot else qd(0, 6)
    dense_rank(srow, 'risk')
    srow = [{k: r[k] for k in ('service', 'team', 'open', 'risk', 'share', 'dense_rank', 'breaches')} for r in srow]
    service_risk = {'upstream': up, 'rows': srow, 'totals': {'services': len(srow), 'risk': qd(stot, 6)}}
    cap = {t['team']: t['capacity_hours'] for t in p1['teams.csv']}
    pool_cap = next((r['value'] for r in p1['ledger.jsonl'] if r['kind'] == 'control' and r['scope'] == 'global' and (r['measure'] == 'pool_hours')), 0)
    team_left = {t: Decimal(c) if c is not None else Decimal(0) for t, c in cap.items()}
    pool_left = Decimal(pool_cap)
    slots = {}
    plan = []
    tt = tp = tu = Decimal('0')
    for seq, e in enumerate(openx, start=1):
        team = svc[e['service']]['team']
        need = e['estimate']
        th = ph = Decimal('0')
        slots[e['service']] = slots.get(e['service'], 0) + 1
        if slots[e['service']] < SERVICE_SLOTS:
            left = team_left.get(team)
            if left is None:
                th = need
            else:
                th = min(need, left)
                team_left[team] = left - th
            if e['severity'] in ('critical', 'high'):
                ph = min(need - th, pool_left)
                pool_left -= ph
        un = need - th - ph
        tt += th
        tp += ph
        tu += un
        tl = team_left.get(team)
        plan.append({'seq': seq, 'service': e['service'], 'package': e['package'], 'vuln': e['vuln'], 'severity': e['severity'], 'estimate': qd(need, 2), 'team': team, 'team_hours': qd(th, 2), 'pool_hours': qd(ph, 2), 'unallocated': qd(un, 2), 'team_remaining': qd(tl, 2) if tl is not None else None, 'pool_remaining': qd(pool_left, 2)})
    remediation_plan = {'upstream': up, 'rows': plan, 'totals': {'team_hours': qd(tt, 2), 'pool_hours': qd(tp, 2), 'unallocated': qd(tu, 2), 'pool_cap': pool_cap}}
    tagg = {}
    for s in p1['services.jsonl']:
        a = tagg.setdefault(s['team'], {'services': 0, 'open': 0})
        a['services'] += 1
        a['open'] += sagg.get(s['service'], {'open': 0})['open']
    trisk = {}
    for e in openx:
        t = svc[e['service']]['team']
        trisk[t] = trisk.get(t, Decimal('0')) + e['cvss'] * svc[e['service']]['weight']
    bal, held, hcount = ({}, {}, {})
    for row in p1['ledger.jsonl']:
        if row['kind'] == 'opening':
            bal[row['team']] = bal.get(row['team'], 0) + row['amount_cents']
        elif row['kind'] == 'entry':
            t = row['team']
            b = bal.get(t, 0)
            if b < 0:
                held[t] = held.get(t, 0) + row['amount_cents']
                hcount[t] = hcount.get(t, 0) + 1
            else:
                bal[t] = b + row['amount_cents']
    trow = []
    for t in p1['teams.csv']:
        k = t['team']
        a = tagg.get(k, {'services': 0, 'open': 0})
        trow.append({'team': k, 'services': a['services'], 'open': a['open'], 'risk': qd(trisk.get(k, 0), 6), 'balance': bal.get(k, 0), 'held': held.get(k, 0), 'held_entries': hcount.get(k, 0)})
    ttot = sum((r['risk'] for r in trow), Decimal('0'))
    for r in trow:
        r['share'] = qd(r['risk'] / ttot, 6) if ttot else qd(0, 6)
    dense_rank(trow, 'risk')
    trow = [{k: r[k] for k in ('team', 'services', 'open', 'risk', 'share', 'dense_rank', 'balance', 'held', 'held_entries')} for r in trow]
    team_rollup = {'upstream': up, 'rows': trow}
    rp = [p for p in p1['pins.jsonl'] if p['pinned'] is not None]
    cls = []
    for c in CLASSES:
        sel = [p for p in rp if p['obligation'] == c]
        cls.append({'class': c, 'pins': len(sel), 'packages': len({p['package'] for p in sel}), 'share': qd(Decimal(len(sel)) / Decimal(len(rp)), 6) if rp else qd(0, 6)})
    strong = {}
    for p in rp:
        if p['obligation'] in ('strong', 'network'):
            t = svc[p['service']]['team']
            strong[t] = strong.get(t, 0) + 1
    lteams = [{'team': t['team'], 'strong': strong.get(t['team'], 0)} for t in p1['teams.csv']]
    dense_rank(lteams, 'strong')
    license_summary = {'upstream': up, 'classes': cls, 'teams': lteams}
    sev_rows = []
    for sv in SEVERITIES:
        sel = [e for e in openx if e['severity'] == sv]
        days = sorted(e['days_open'] or 0 for e in sel)
        n = len(days)

        def nearest(pq):
            if not n:
                return None
            k = int((Decimal(pq) * n).to_integral_value(rounding=ROUND_HALF_EVEN))
            return days[max(1, k) - 1]
        sev_rows.append({'severity': sv, 'open': len(sel), 'with_days': n, 'nulls': len(sel) - n, 'zeros': sum((1 for x in days if x == 0)), 'breaches': sum((1 for e in sel if e['breach'])), 'mean_days': qd(Decimal(sum(days)) / Decimal(n), 6) if n else None, 'p50': nearest('0.5'), 'p90': nearest('0.9'), 'max_days': days[-1] if n else None})
    sla_metrics = {'upstream': up, 'severities': sev_rows}
    return {'package_risk.json': package_risk, 'service_risk.json': service_risk, 'remediation_plan.json': remediation_plan, 'team_rollup.json': team_rollup, 'license_summary.json': license_summary, 'sla_metrics.json': sla_metrics}

def _ceil(x):
    return int(Decimal(x).to_integral_value(rounding=ROUND_CEILING))

def stage3(p1, raw1, p2, raw2):
    up = dict(upstream_digests(raw1, 'p1'))
    up.update(upstream_digests(raw2, 'p2'))
    svc = {r['service']: r for r in p1['services.jsonl']}
    exps = p1['exposures.jsonl']
    openx = [e for e in exps if e['status'] == 'open']
    srisk = {r['service']: r for r in p2['service_risk.json']['rows']}
    n_rank = int(TOP_RISK_SHARE * len(p2['service_risk.json']['rows']))
    crit = {e['service'] for e in openx if e['severity'] == 'critical' and e['breach']}
    unsat = {p['service'] for p in p1['pins.jsonl'] if p['disposition'] == 'unsatisfiable'}
    netl = {p['service'] for p in p1['pins.jsonl'] if p['scope'] == 'runtime' and p['obligation'] == 'network'}
    unfunded = {r['service'] for r in p2['remediation_plan.json']['rows'] if r['severity'] in ('critical', 'high') and r['unallocated'] > 0}
    gates = []
    tot = {'block': 0, 'hold': 0, 'pass': 0}
    for s in p1['services.jsonl']:
        if s['status'] != 'active':
            continue
        k = s['service']
        sr = srisk.get(k)
        reasons = []
        if k in crit:
            reasons.append('critical_breach')
        if sr is not None and sr['risk'] > 0 and (sr['dense_rank'] <= n_rank):
            reasons.append('top_risk')
        if k in unsat:
            reasons.append('unsatisfiable_pin')
        if k in unfunded:
            reasons.append('unfunded_remediation')
        if k in netl:
            reasons.append('network_license')
        verdict = 'block' if {'critical_breach', 'top_risk'} & set(reasons) else 'hold' if reasons else 'pass'
        tot[verdict] += 1
        gates.append({'service': k, 'team': s['team'], 'verdict': verdict, 'reasons': reasons})
    release_gates = {'upstream': up, 'rows': gates, 'totals': tot}
    by_svc, by_pkg, by_team = ({}, {}, {})
    for e in openx:
        by_svc[e['service']] = by_svc.get(e['service'], 0) + 1
        by_pkg[e['package']] = by_pkg.get(e['package'], 0) + 1
        t = svc[e['service']]['team']
        by_team[t] = by_team.get(t, 0) + 1
    pins = {}
    for p in p1['pins.jsonl']:
        if p['scope'] == 'runtime' and p['pinned'] is not None:
            pins[p['service']] = pins.get(p['service'], 0) + 1
    led = p1['ledger.jsonl']
    closing = {r['team']: r['amount_cents'] for r in led if r['kind'] == 'closing'}
    custody = {r['file']: r for r in led if r['kind'] == 'custody'}
    cap = {t['team']: t['capacity_hours'] for t in p1['teams.csv']}
    teams = set(cap)
    s2svc = {r['service']: r for r in p2['service_risk.json']['rows']}
    s2pkg = {r['package']: r for r in p2['package_risk.json']['rows']}
    s2team = {r['team']: r for r in p2['team_rollup.json']['rows']}
    plan_t = p2['remediation_plan.json']['totals']
    rec = []
    agree = 0
    for r in sorted((x for x in led if x['kind'] == 'control'), key=lambda x: x['control']):
        sc, m, pub = (r['scope'], r['measure'], r['value'])
        s1 = s2 = None
        if m == 'open_exposures':
            if sc in teams:
                s1, s2 = (by_team.get(sc, 0), s2team[sc]['open'] if sc in s2team else 0)
            elif sc in svc:
                s1, s2 = (by_svc.get(sc, 0), s2svc[sc]['open'] if sc in s2svc else 0)
            else:
                s1, s2 = (by_pkg.get(sc, 0), s2pkg[sc]['open'] if sc in s2pkg else 0)
        elif m == 'runtime_pins':
            s1 = pins.get(sc, 0)
        elif m == 'closing_cents':
            s1 = closing.get(sc, 0)
            s2 = s2team[sc]['balance'] + s2team[sc]['held'] if sc in s2team else None
        elif m == 'capacity_hours':
            s1 = cap.get(sc)
        elif m in ('records', 'in_force'):
            s1 = custody[sc][m] if sc in custody else None
        elif m == 'pool_hours':
            s2 = int(plan_t['pool_cap'])
        elif m == 'total_open':
            s1 = len(openx)
            s2 = sum((x['open'] for x in p2['package_risk.json']['rows']))
        elif m == 'waived_total':
            s1 = sum((1 for e in exps if e['status'] == 'waived'))
        ok = (s1 is None or s1 == pub) and (s2 is None or s2 == pub) and (not (s1 is None and s2 is None))
        agree += ok
        rec.append({'control': r['control'], 'scope': sc, 'measure': m, 'published': pub, 'stage1': s1, 'stage2': s2, 'agrees': ok})
    control_reconciliation = {'upstream': up, 'rows': rec, 'totals': {'controls': len(rec), 'agreeing': agree}}
    ptot = p2['package_risk.json']['totals']['risk']
    drows = []
    cv_sum = Decimal('0')
    ct_sum = 0
    for r in led:
        if r['kind'] != 'deferred':
            continue
        imp = after = None
        if r['measure'] == 'cvss' and r['current'] is not None and (r['amended'] is not None):
            delta = r['amended'] - r['current']
            s = sum((delta * svc[e['service']]['weight'] for e in exps if e['vuln'] == r['target']), Decimal('0'))
            imp = qd(s, 6)
            after = qd(ptot + s, 6)
            cv_sum += imp
        elif r['measure'] == 'cents':
            imp = (r['amended'] or 0) - (r['current'] or 0)
            after = s2team[r['target']]['balance'] + imp if r['target'] in s2team else None
            ct_sum += imp
        drows.append({'amendment': r['amendment'], 'file': r['file'], 'target': r['target'], 'measure': r['measure'], 'current': r['current'], 'amended': r['amended'], 'impact': imp, 'after': after})
    deferred_amendments = {'upstream': up, 'rows': drows, 'totals': {'amendments': len(drows), 'cvss_impact': qd(cv_sum, 6), 'cents_impact': ct_sum}}
    alloc = {}
    for r in p2['remediation_plan.json']['rows']:
        alloc[r['team']] = alloc.get(r['team'], Decimal('0')) + r['team_hours']
    br = {}
    for r in p2['service_risk.json']['rows']:
        br[r['team']] = br.get(r['team'], 0) + r['breaches']
    sc_rows = []
    for t in p1['teams.csv']:
        k = t['team']
        tr = s2team[k]
        a = alloc.get(k, Decimal('0'))
        c = t['capacity_hours']
        util = qd(a / Decimal(c), 6) if c else qd(0, 6) if c == 0 else None
        score = qd(tr['risk'] * (Decimal(1) + Decimal(br.get(k, 0)) / Decimal(max(tr['open'], 1))), 6)
        sc_rows.append({'team': k, 'risk': tr['risk'], 'capacity': c, 'allocated': qd(a, 2), 'utilization': util, 'breaches': br.get(k, 0), 'closing': closing.get(k, 0), 'balance': tr['balance'], 'score': score})
    dense_rank(sc_rows, 'score')
    team_scorecard = {'upstream': up, 'rows': sc_rows}
    risk1 = qd(sum((e['cvss'] * svc[e['service']]['weight'] for e in openx), Decimal('0')), 6)
    rp_ = sum((r['risk'] for r in p2['package_risk.json']['rows']), Decimal('0'))
    rs_ = sum((r['risk'] for r in p2['service_risk.json']['rows']), Decimal('0'))
    est = sum((r['estimate'] for r in p2['remediation_plan.json']['rows']), Decimal('0'))
    un = plan_t['unallocated']
    crit_n = sum((1 for e in openx if e['severity'] == 'critical' and e['breach']))
    if crit_n == 0 and un == 0:
        verdict = 'certified'
    elif un <= UNFUNDED_SHARE * est:
        verdict = 'qualified'
    else:
        verdict = 'withheld'
    certification = {'upstream': up, 'summary': {'active_services': sum((1 for s in p1['services.jsonl'] if s['status'] == 'active')), 'runtime_pins': sum(pins.values()), 'open_exposures': len(openx), 'critical_breaches': crit_n, 'risk_stage1': risk1, 'risk_packages': qd(rp_, 6), 'risk_services': qd(rs_, 6), 'gap_packages': qd(rp_ - risk1, 6), 'gap_services': qd(rs_ - risk1, 6), 'pool_used': plan_t['pool_hours'], 'unallocated': un, 'estimate_total': qd(est, 2), 'verdict': verdict}}
    files = []
    for f in P1_FILES:
        n = len(p1[f])
        files.append({'file': 'p1/' + f, 'rows': n, 'bytes': len(raw1[f])})
    main_list = {'package_risk.json': 'rows', 'service_risk.json': 'rows', 'remediation_plan.json': 'rows', 'team_rollup.json': 'rows', 'license_summary.json': 'classes', 'sla_metrics.json': 'severities'}
    for f in P2_FILES:
        files.append({'file': 'p2/' + f, 'rows': len(p2[f][main_list[f]]), 'bytes': len(raw2[f])})
    active = {s['service'] for s in p1['services.jsonl'] if s['status'] == 'active'}
    rp = [p for p in p1['pins.jsonl'] if p['scope'] == 'runtime' and p['pinned'] is not None]
    checks = [('package_risk_covers_open_packages', {r['package'] for r in p2['package_risk.json']['rows']} == {e['package'] for e in openx}), ('service_risk_covers_active_services', {r['service'] for r in p2['service_risk.json']['rows']} == active), ('plan_covers_open_exposures', len(p2['remediation_plan.json']['rows']) == len(openx)), ('team_rollup_covers_teams', [r['team'] for r in p2['team_rollup.json']['rows']] == [t['team'] for t in p1['teams.csv']]), ('license_pins_match', sum((c['pins'] for c in p2['license_summary.json']['classes'])) == len(rp)), ('sla_open_matches', sum((c['open'] for c in p2['sla_metrics.json']['severities'])) == len(openx)), ('risk_totals_agree', abs(rp_ - rs_) <= Decimal('0.0000005') * (len(p2['package_risk.json']['rows']) + len(p2['service_risk.json']['rows']))), ('ledger_balances_close', all((s2team[t]['balance'] + s2team[t]['held'] == closing.get(t, 0) for t in s2team)))]
    chain_audit = {'upstream': up, 'files': files, 'checks': [{'check': c, 'passed': bool(ok)} for c, ok in checks]}
    return {'release_gates.json': release_gates, 'control_reconciliation.json': control_reconciliation, 'deferred_amendments.json': deferred_amendments, 'team_scorecard.json': team_scorecard, 'certification.json': certification, 'chain_audit.json': chain_audit}

def supplemental_bytes(p1, p2, p3):
    """Six format-distinct views, all derived from the in-memory close."""
    rows = evidence_rows('global-close', {'p1': p1, 'p2': p2, 'p3': p3}, 1200)
    vals = [r['_evidence']['lineage']['artifact'] for r in rows]
    open_count = len([x for x in p1['exposures.jsonl'] if x['status'] == 'open'])
    risk = p3['certification.json']['summary']['risk_stage1']
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<close><authority><trace><rows>']
    xml += [f'<row><identity><slot>{r["slot"]}</slot></identity><source><name>{r["name"]}</name><digest>{r["digest"]}</digest></source><value><fold>{r["fold"]}</fold><open_count>{open_count}</open_count><risk>{risk}</risk></value></row>' for r in vals]
    xml += ['</rows></trace></authority></close>']
    tsv = ['slot\tparent_id\tlineage\tartifact\tdigest\tfold\topen_count\trisk']
    tsv += [f'{r["slot"]}\troot-{r["slot"] % 31:02d}\tclose/authority/trace/{r["slot"]}/value\t{r["name"]}\t{r["digest"]}\t{r["fold"]}\t{open_count}\t{risk}' for r in vals]
    yaml = ['close:', '  reconciliation:', '    map:', '      entries:']
    for r in vals:
        yaml += [f'        - slot: {r["slot"]}', '          lineage:', '            authority:', f'              name: {r["name"]}', f'              digest: {r["digest"]}', '              result:', f'                fold: {r["fold"]}',
                 f'                open_count: {open_count}', f'                risk: {risk}']
    ordered_artifacts = P1_FILES + P2_FILES + P3_FILES + SUPPLEMENTAL_FILES
    graph_edges = []
    for dependent_index, dependent in enumerate(ordered_artifacts):
        width = 13 if 13 <= dependent_index <= 18 else 12
        for prerequisite_index in range(max(0, dependent_index - width), dependent_index):
            graph_edges.append((dependent, ordered_artifacts[prerequisite_index]))
    assert len(graph_edges) == 216
    ini = []
    for i, r in enumerate(vals):
        ini += [f'[close.reconciliation.entry.{r["slot"]}.authority.result]', f'name={r["name"]}', f'digest={r["digest"]}', f'fold={r["fold"]}', f'open_count={open_count}', f'risk={risk}']
        if i < len(graph_edges):
            dependent, prerequisite = graph_edges[i]
            ini += [f'dependent={dependent}', f'prerequisite={prerequisite}', f'locator_identity={r["name"]}', f'locator_digest={r["digest"]}', f'locator_fold={r["fold"]}']
    log = [f'level=INFO correlation=close-{r["slot"] % 29:02d} span=authority-{r["slot"]:04d} path=close/reconciliation/entry/{r["slot"]}/result artifact={r["name"]} digest={r["digest"]} fold={r["fold"]} open_count={open_count} risk={risk}' for r in vals]
    md = ['# Closure evidence', '', '| slot | path | artifact | digest | fold | open | risk |', '|---:|---|---|---|---:|---:|---:|']
    md += [f'| {r["slot"]} | close/reconciliation/entry/{r["slot"]}/result | {r["name"]} | {r["digest"]} | {r["fold"]} | {open_count} | {risk} |' for r in vals]
    return {
        'authority-trace.xml': ('\n'.join(xml) + '\n').encode(),
        'rollup-ledger.tsv': ('\n'.join(tsv) + '\n').encode(),
        'reconciliation-map.yaml': ('\n'.join(yaml) + '\n').encode(),
        'dependency-matrix.ini': ('\n'.join(ini) + '\n').encode(),
        'freeze-register.log': ('\n'.join(log) + '\n').encode(),
        'training-closure.md': ('\n'.join(md) + '\n').encode(),
    }
# ---- rules


def parse_cmp(tok):
    for op in ('>=', '<=', '>', '<', '='):
        if tok.startswith(op):
            return (op, parse_ver(tok[len(op):].strip()))
    return ('', parse_ver(tok))

def cons_from_cmps(cmps):
    c = Cons(None, True, None, False)
    for op, v in cmps:
        if op in ('>=', '>'):
            c.lo, c.lo_inc = (v, op == '>=')
        elif op in ('<', '<='):
            c.hi, c.hi_inc = (v, op == '<=')
        elif op == '=':
            return Cons(v, True, v, True, True)
    return c

def _wild(body):
    parts = body.split('.')
    if len(parts) == 2 or parts[1] in ('x', '*'):
        M = int(parts[0])
        if len(parts) >= 2 and parts[1] not in ('x', '*'):
            m = int(parts[1])
            return Cons(Ver(M, m, 0), True, Ver(M, m + 1, 0), False)
        return Cons(Ver(M, 0, 0), True, Ver(M + 1, 0, 0), False)
    M, m = (int(parts[0]), int(parts[1]))
    return Cons(Ver(M, m, 0), True, Ver(M, m + 1, 0), False)

def parse_cons(eco, raw):
    s = raw.strip()
    if eco == 'maven':
        if s[0] in '[(':
            inner = s[1:-1]
            if ',' not in inner:
                v = parse_ver(inner)
                return Cons(v, True, v, True, True)
            a, b = inner.split(',', 1)
            return Cons(parse_ver(a) if a.strip() else None, s[0] == '[', parse_ver(b) if b.strip() else None, s[-1] == ']')
        v = parse_ver(s)
        return Cons(v, True, v, True, True)
    if eco == 'pypi':
        parts = [p.strip() for p in s.split(',')]
        if len(parts) == 1 and parts[0].startswith('=='):
            body = parts[0][2:]
            if body.endswith('.*'):
                return _wild(body[:-2] + '.x')
            v = parse_ver(body)
            return Cons(v, True, v, True, True)
        if len(parts) == 1 and parts[0].startswith('~='):
            body = parts[0][2:]
            v = parse_ver(body)
            if body.count('.') == 1:
                return Cons(Ver(v.major, v.minor, 0), True, Ver(v.major + 1, 0, 0), False)
            return tilde(v)
        return cons_from_cmps([parse_cmp(p) for p in parts])
    if eco == 'cargo':
        parts = [p.strip() for p in s.split(',')]
        if len(parts) == 1:
            p = parts[0]
            if p.startswith('^'):
                return caret(parse_ver(p[1:]))
            if p.startswith('~'):
                return tilde(parse_ver(p[1:]))
            if p.startswith('='):
                v = parse_ver(p[1:])
                return Cons(v, True, v, True, True)
            if p.endswith('.*'):
                return _wild(p[:-2] + '.x')
            if p[0].isdigit():
                return caret(parse_ver(p))
        return cons_from_cmps([parse_cmp(p) for p in parts])
    if s.startswith('^'):
        return caret(parse_ver(s[1:]))
    if s.startswith('~'):
        return tilde(parse_ver(s[1:]))
    if s.endswith('.x') or s.endswith('.*'):
        return _wild(s[:-2] + '.x')
    toks = s.split()
    if len(toks) == 1 and toks[0][0].isdigit():
        v = parse_ver(toks[0])
        return Cons(v, True, v, True, True)
    return cons_from_cmps([parse_cmp(t) for t in toks])

def stage1(self):
    self._rec_cache = {}
    self.load_register()
    self.decode_all()
    self.load_errata()
    self.build_identity()
    self.build_vulns()
    self.build_releases()
    self.build_services()
    self.build_pins()
    self.build_exposures()
    self.build_ledger()
    return self.p1_rows()

def build_releases(self):
    quar = set()
    for v, x, _ in self.records('registry_mirror.parquet', 'mirror').values():
        if v['quarantined'] is True:
            quar.add((self.pkey(v['eco'], v['name']), str(v['version'])))
    self.rel = {}
    for eco, f in REG.items():
        for rid, (v, x, revs) in self.records(f, 'releases').items():
            key = self.pkey(eco, v['name'])
            vs = str(v['version'])
            if (key, vs) in quar:
                continue
            hist = sorted(((r.rev, r.rec_at, r.v['yanked']) for r in revs if r.st != 'draft' and r.rec_at < CUT))
            self.rel.setdefault(key, {})[vs] = {'ver': v['version'], 'pub': v['published'], 'hist': hist}
    self.notes = {}
    self.renamed = set()
    for v, x, _ in self.records('yank_notices.mbox', 'notices').values():
        if v['action'] == 'rename':
            if x.rec_at < CUT:
                self.renamed.add(v['ref'])
            continue
        if v['action'] in ('yank', 'unyank') and v.get('version') is not None:
            k = (self.pkey(v['eco'], v['name']), str(v['version']))
            self.notes.setdefault(k, []).append((x.rec_at, v['action'] == 'yank'))
    self.lic_over = {}
    for v, x, _ in self.records('license_overrides.csv', 'overrides').values():
        if v['status'] == 'decided' and v['decided'] is not None and (v['decided'] < CUT):
            key = self.pkey(v['eco'], v['name'])
            self.lic_over.setdefault(key, []).append((v['decided'], parse_cons(v['eco'], v['range']), v['expression']))
    self.scans = {}
    for v, x, _ in self.records('license_scan.parquet', 'scans').values():
        if v['scanned'] is not None and v['scanned'] < CUT:
            k = (self.pkey(v['eco'], v['name']), str(v['version']))
            if k not in self.scans or v['scanned'] > self.scans[k][0]:
                self.scans[k] = (v['scanned'], v['expression'])
    self.lic_exc = {}
    for v, x, _ in self.records('license_policy.md', 'exceptions').values():
        rv = v['revoked']
        if v['granted'] is not None and v['granted'] <= CUT_DATE and (not isinstance(rv, int) or rv > CUT_DATE):
            key = self.pkey(v['eco'], v['name'])
            self.lic_exc.setdefault(key, []).append((v['granted'], parse_cons(v['eco'], v['range']), v['class']))

def yanked_at(self, key, vs, t):
    r = self.rel[key][vs]
    best = None
    for rev, at, y in r['hist']:
        if at < t and (best is None or rev > best[0]):
            best = (rev, at, y)
    note = None
    for at, y in sorted(self.notes.get((key, vs), [])):
        if at < t:
            note = (at, y)
    if note is not None and (best is None or note[0] >= best[1]):
        return note[1]
    return bool(best[2]) if best else False

def license_of(self, key, ver):
    best = None
    for dt, cons, expr in self.lic_over.get(key, []):
        if cons.admits_any(ver) and (best is None or dt > best[0]):
            best = (dt, expr)
    if best:
        expr = best[1]
    else:
        sc = self.scans.get((key, str(ver)))
        expr = sc[1] if sc else 'NOASSERTION'
    cls = spdx_class(parse_spdx(expr))
    exc = None
    for g, cons, c in self.lic_exc.get(key, []):
        if cons.admits_any(ver) and (exc is None or g > exc[0]):
            exc = (g, c)
    return (expr, exc[1] if exc else cls)

def build_services(self):
    self.svc = {}
    for v, x, _ in self.records('service_catalog.xlsx', 'services').values():
        self.svc[v['service']] = {'tier': v['tier'], 'region': v['region'], 'home': v['manifest'], 'team': None, 'status': 'active', 'archived': False}
    own = {}
    for v, x, _ in self.records('service_catalog.xlsx', 'ownership').values():
        if v['effective'] < CUT:
            k = v['service']
            if k not in own or (v['effective'], x.rid) > own[k][0]:
                own[k] = ((v['effective'], x.rid), v['team'])
    for k, (_, t) in own.items():
        if k in self.svc:
            self.svc[k]['team'] = t
    has_life = {x.v['service'] for revs in self.revs['service_catalog.xlsx'].get('lifecycle', {}).values() for x in revs}
    events = []
    for v, x, _ in self.records('service_catalog.xlsx', 'lifecycle').values():
        events.append(v)
    for v, x, _ in self.records('service_catalog_final.xlsx', 'legacy_lifecycle').values():
        if v['service'] not in has_life:
            events.append(v)
    for v in sorted(events, key=lambda e: (e['at'], e['rid'])):
        s = self.svc.get(v['service'])
        if s is None or v['at'] >= CUT:
            continue
        if v['event'] == 'decommissioned':
            s['status'] = 'decommissioned'
        elif v['event'] == 'restored':
            s['status'] = 'active'
        elif v['event'] == 'archived':
            s['archived'] = True
    offs = {}
    for v, x, _ in self.records('clock_offsets.txt', 'offsets').values():
        offs[v['host'], v['day']] = v['offset']
    seen = {}
    for f in AUTH_LOGS + ['deploy_events_legacy.log']:
        for rid, (v, x, _) in self.records(f, 'deploys').items():
            s = self.svc.get(v['service'])
            t = v['at'] - offs.get((v['host'], v['at'] // DAY), 0)
            if f == 'deploy_events_legacy.log':
                if not (s and s['region'] == 'us-central') or t >= MIGRATION:
                    continue
                if rid in seen:
                    continue
            if rid not in seen:
                seen[rid] = (v['service'], v['outcome'], t)
    cnt = {}
    for rid, (svc, outcome, t) in seen.items():
        if outcome == 'succeeded' and Q_START <= t < CUT:
            cnt[svc] = cnt.get(svc, 0) + 1
    for k, s in self.svc.items():
        s['deploys'] = cnt.get(k, 0) if s['region'] != 'global' else None
        factor = min(Decimal(2), Decimal(1) + Decimal(s['deploys']) / Decimal(365)) if s['deploys'] is not None else Decimal(1)
        s['weight'] = qd(self.tier_weight[s['tier']] * factor, 4)

def build_pins(self):
    ovr = {}
    for v, x, _ in self.records('lock_overrides.toml', 'overrides').values():
        if x.rid in self.approved and v['valid_from'] <= CUT_DATE <= v['valid_to']:
            key = self.pkey(v['eco'], v['name'])
            r = self.rel.get(key, {}).get(str(v['version']))
            if r is not None and r['pub'] < CUT:
                ovr[v['service'], key] = v['version']
    decl = {}
    for f in list(HOME_FILE.values()) + ['manifests_snapshot.csv']:
        for v, x, _ in self.records(f, 'declarations').values():
            decl.setdefault((f, v['service']), []).append(v)
    scans = {}
    for v, x, _ in self.records('scanner_findings.jsonl', 'findings').values():
        if v['seen'] < CUT:
            k = (v['service'], self.pkey(v['eco'], v['name']))
            if k not in scans or v['seen'] > scans[k][0]:
                scans[k] = (v['seen'], v['version'])
    self.pins = []
    for k in sorted(self.svc):
        s = self.svc[k]
        if s['status'] != 'active':
            continue
        if s['home'] == 'image':
            for (svc, key), (_, ver) in sorted(scans.items()):
                if svc == k:
                    self.pins.append({'service': k, 'package': key, 'scope': 'runtime', 'constraint': None, 'source': 'scanner_findings.jsonl', 'pinned': ver, 'disposition': 'observed'})
            continue
        src = 'manifests_snapshot.csv' if s['archived'] else HOME_FILE[s['home']]
        for v in decl.get((src, k), []):
            key = self.pkey(v['eco'], v['name'])
            cons = parse_cons(v['eco'], v['constraint'])
            if (k, key) in ovr:
                pinned, disp = (ovr[k, key], 'overridden')
            else:
                best = None
                for vs, r in self.rel.get(key, {}).items():
                    if r['pub'] >= v['locked'] or not cons.admits(r['ver']):
                        continue
                    if not cons.exact and self.yanked_at(key, vs, v['locked']):
                        continue
                    if best is None or best < r['ver']:
                        best = r['ver']
                pinned = best
                disp = 'pinned' if best is not None else 'unsatisfiable'
            self.pins.append({'service': k, 'package': key, 'scope': v['scope'], 'constraint': cons.canon(), 'source': src, 'pinned': pinned, 'disposition': disp})
    self.pins.sort(key=lambda r: (r['service'], r['package'], r['scope']))
    for p in self.pins:
        if p['pinned'] is not None and p['scope'] == 'runtime':
            p['license'], p['obligation'] = self.license_of(p['package'], p['pinned'])
        else:
            p['license'], p['obligation'] = (None, None)

def vuln_vector(self, c):
    best = None
    for v, x, _ in self.records('advisory_rescores.parquet', 'rescores').values():
        if self.vid(v['vuln']) == c and v['approved'] is True and (v['scored'] < CUT):
            if best is None or v['scored'] > best[0]:
                best = (v['scored'], v['vector'])
    if best:
        return best[1]
    for src in self.authority.get((c, 'cvss_vector'), ['nvd', 'ghsa']):
        if src == 'nvd':
            for source in ('NVD', 'CNA'):
                cands = [r for r in self.nvd.get(c, []) if r[0] == source]
                if cands:
                    return max(cands, key=lambda r: (r[1], r[3]))[2]
        elif src == 'ghsa':
            for rid, vec, gid, key in sorted(self.ghsa_vec.get(c, [])):
                if isinstance(vec, Sentinel):
                    vec = self.cache_vec.get((gid, key))
                if vec:
                    return vec
    return None

def build_exposures(self):
    self.authority = {}
    for v, x, _ in self.records('precedence.yaml', 'authority').values():
        self.authority[self.vid(v['vuln']), v['field']] = v['order'].split('>')
    self.nvd = {}
    for v, x, _ in self.records('advisories_nvd.xml', 'nvd').values():
        self.nvd.setdefault(self.vid(v['cve']), []).append((v['source'], v['modified'], v['vector'], x.rid))
    self.cache_vec = {}
    for v, x, _ in self.records('advisories_feed_cache.json', 'cache').values():
        self.cache_vec[v['ghsa'], self.pkey(v['eco'], v['name'])] = v['vector']
    self.ghsa_vec, ghsa_pub = ({}, {})
    for v, x, _ in self.records('advisories_ghsa.json', 'ghsa').values():
        c = self.vid(v['ghsa'])
        self.ghsa_vec.setdefault(c, []).append((x.rid, v['vector'], v['ghsa'], self.pkey(v['eco'], v['name'])))
        ghsa_pub.setdefault(c, []).append((x.rid, v['published']))
    replay = {}
    for v, x, _ in self.records('advisories_osv_replay.jsonl', 'osv').values():
        replay[(v['osv'], self.pkey(v['eco'], v['name']))] = v['events']
    osv = []
    osv_pub, withdrawn = ({}, set())
    for v, x, _ in self.records('advisories_osv.jsonl', 'osv').values():
        c = self.vid(v['osv'])
        key = self.pkey(v['eco'], v['name'])
        ev = v['events']
        if isinstance(ev, Sentinel):
            ev = replay.get((v['osv'], key))
        if isinstance(v['withdrawn'], int) and v['withdrawn'] < CUT:
            withdrawn.add(c)
        osv_pub.setdefault(c, []).append((x.rid, v['published']))
        osv.append((c, key, ev, x.rid))
    pubs = {}
    for c in set(osv_pub) | set(ghsa_pub):
        val = 'absent'
        for src in self.authority.get((c, 'published'), ['osv', 'ghsa']):
            lst = osv_pub.get(c) if src == 'osv' else ghsa_pub.get(c)
            if lst:
                val = sorted(lst)[0][1]
                break
        pubs[c] = None if val == 'absent' else val
    self.vpub = pubs
    pins_by = {}
    for p in self.pins:
        if p['scope'] == 'runtime' and p['pinned'] is not None:
            pins_by.setdefault(p['package'], []).append(p)
    vex = {}
    for v, x, _ in self.records('vex_statements.xml', 'vex').values():
        if v['issued'] < CUT:
            k = (v['service'], self.vid(v['vuln']))
            if k not in vex or (v['issued'], x.rid) > vex[k][0]:
                vex[k] = ((v['issued'], x.rid), v['status'])
    waived = set()
    for v, x, _ in self.records('waivers.db', 'waivers').values():
        if x.rid in self.approved and v['granted'] < CUT <= v['expires']:
            waived.add((v['service'], self.vid(v['vuln'])))
    freeze = {}
    for v, x, _ in self.records('change_freeze.ics', 'windows').values():
        freeze.setdefault(v['service'], set()).update(range(v['start'], v['end']))
    holi = {r: {days_from_civil(int(d[0:4]), int(d[5:7]), int(d[8:10])) for d in ds} for r, ds in self.holidays.items()}
    sla_over = {}
    for v, x, _ in self.records('sla_policy.pdf', 'sla_overrides').values():
        if v['effective'] < CUT_DATE:
            k = (v['service'], v['severity'])
            if k not in sla_over or (v['effective'], x.rid) > sla_over[k][0]:
                sla_over[k] = ((v['effective'], x.rid), v['days'])
    factors, est = ({}, {})
    for v, x, _ in self.records('scoring_methodology.pdf', 'factors').values():
        if v['effective'] <= CUT_DATE:
            k = (self.pkey(v['eco'], v['name']), v['major'])
            if k not in factors or (v['effective'], x.rid) > factors[k][0]:
                factors[k] = ((v['effective'], x.rid), v['factor'])
    for t, _ in SCHEMA['remediation_estimates.xlsx']:
        for v, x, _ in self.records('remediation_estimates.xlsx', t).values():
            if v['effective'] <= CUT_DATE:
                k = (self.pkey(v['eco'], v['name']), v['major'])
                if k not in est or (v['effective'], x.rid) > est[k][0]:
                    est[k] = ((v['effective'], x.rid), v['hours'])
    vec_cache = {}
    seen = set()
    out = []
    for c, key, ev, rid in osv:
        if c in withdrawn or ev is None:
            continue
        pub = pubs.get(c)
        if isinstance(pub, int) and pub >= CUT:
            continue
        pub = pub if isinstance(pub, int) else None
        for p in pins_by.get(key, []):
            if not affected(ev, p['pinned']):
                continue
            k3 = (p['service'], key, c)
            if k3 in seen:
                continue
            seen.add(k3)
            if c not in vec_cache:
                vec_cache[c] = self.vuln_vector(c)
            score = cvss_base(vec_cache[c]) if vec_cache[c] else Decimal('0.0')
            sev = severity_of(score)
            s = self.svc[p['service']]
            st = vex.get((p['service'], c))
            if st and st[1] == 'not_affected':
                status = 'not_affected'
            elif (p['service'], c) in waived:
                status = 'waived'
            else:
                status = 'open'
            if pub is None:
                pday, days = (None, None)
            else:
                pday = pub // DAY
                days = business_days(pday + 1, CUT_DAY, freeze.get(p['service'], set()) | holi.get(s['region'], set()))
            sla = self.sla_matrix[sev][s['tier']]
            so = sla_over.get((p['service'], sev))
            if so:
                sla = so[1]
            breach = days is not None and days > sla
            ver = p['pinned']
            cands = sorted((r['ver'] for vs, r in self.rel.get(key, {}).items() if r['pub'] < CUT and ver < r['ver'] and not self.yanked_at(key, vs, CUT)))
            fixed = next((x for x in cands if not affected(ev, x)), None)
            e_o = est.get((key, ver.major))
            if e_o:
                estimate = qd(e_o[1], 2)
            else:
                fo = factors.get((key, ver.major))
                fac = fo[1] if fo else Decimal(1)
                mult = Decimal(3) if fixed is None else Decimal(2) if fixed.major > ver.major else Decimal(1)
                estimate = qd(self.base_hours[sev] * fac * mult, 2)
            out.append({'service': p['service'], 'package': key, 'version': str(ver), 'vuln': c, 'cvss': qd(score, 1), 'severity': sev, 'status': status, 'published': iso_date(pday) if pday is not None else None, 'days_open': days, 'sla_days': sla, 'breach': breach, 'estimate': estimate, 'fixed': str(fixed) if fixed else None})
    out.sort(key=lambda e: (e['service'], e['package'], e['vuln']))
    self.exposures = out
    self.vec_cache = vec_cache
Close.stage1 = stage1
Close.build_releases = build_releases
Close.yanked_at = yanked_at
Close.license_of = license_of
Close.build_services = build_services
Close.build_pins = build_pins
Close.vuln_vector = vuln_vector
Close.build_exposures = build_exposures
# ---- ledger

from decimal import ROUND_FLOOR

def build_ledger(self):
    self.teams = {}
    for v, x, _ in self.records('engineer_roster.ini', 'teams').values():
        self.teams[v['team']] = {'model': v['model'], 'cap': Decimal(0), 'engs': set()}
    self.allocs = []
    for v, x, _ in self.records('engineer_roster.ini', 'alloc').values():
        end = v['end'] if isinstance(v['end'], int) else None
        self.allocs.append((v['engineer'], v['team'], v['fte'], v['oncall'], v['start'], end))
        t = self.teams.get(v['team'])
        if t is None:
            continue
        a = max(v['start'], Q_START_DAY)
        b = min(end if end is not None else CUT_DAY, CUT_DAY)
        if b > a:
            t['cap'] += v['fte'] * Decimal(8) * Decimal(weekdays_between(a, b)) * (Decimal(1) - v['oncall'])
        if v['start'] < CUT_DAY and (end is None or end > Q_START_DAY):
            t['engs'].add(v['engineer'])
    self.fx = {}
    for v, x, _ in self.records('fx_fixings.tsv', 'fixings').values():
        self.fx.setdefault(v['currency'], []).append((v['at'], v['rate']))
    for k in self.fx:
        self.fx[k].sort()
    self.rates = {}
    for t, _ in SCHEMA['engineer_rates.xlsx']:
        for v, x, _ in self.records('engineer_rates.xlsx', t).values():
            self.rates[v['engineer'], civil_from_days(v['month'])[1]] = (v['rate'], v['currency'])
    entries, openings = ([], [])
    for rid, (v, x, _) in self.records('remediation_timesheets.csv', 'timesheets').items():
        if v['worked'] >= CUT:
            continue
        team = self.team_on(v['engineer'], v['worked'])
        if team is None:
            continue
        entries.append({'kind': 'entry', 'entry': rid, 'team': team, 'source': 'remediation_timesheets.csv', 'booked': v['worked'], 'amount_cents': self.ts_cents(v)})
    jr = self.records('ledger_journal.db', 'entries')
    cancelled = set()
    for rid, (v, x, _) in jr.items():
        if v['kind'] == 'reversal' and v['booked'] < CUT:
            cancelled.add(rid)
            if v['reverses']:
                cancelled.add(v['reverses'])
    self.cancelled = cancelled
    for rid, (v, x, _) in jr.items():
        if rid in cancelled or v['booked'] >= CUT:
            continue
        cents = self.to_cents(v['amount'], v['currency'], v['booked'])
        if v['kind'] == 'opening':
            openings.append({'kind': 'opening', 'team': v['team'], 'entry': rid, 'amount_cents': cents})
        else:
            entries.append({'kind': 'entry', 'entry': rid, 'team': v['team'], 'source': 'ledger_journal.db', 'booked': v['booked'], 'amount_cents': cents})
    openings.sort(key=lambda r: (r['team'], r['entry']))
    entries.sort(key=lambda r: (r['booked'], r['entry']))
    clos = {}
    for r in openings + entries:
        clos[r['team']] = clos.get(r['team'], 0) + r['amount_cents']
    self.openings, self.entries = (openings, entries)
    self.closings = [{'kind': 'closing', 'team': t, 'amount_cents': clos.get(t, 0)} for t in sorted(self.teams)]

def fx_at(self, cur, t):
    if cur == 'EUR':
        return Decimal(1)
    best = None
    for at, rate in self.fx.get(cur, []):
        if at <= t:
            best = rate
        else:
            break
    if best is None:
        best = self.fx[cur][0][1] if self.fx.get(cur) else Decimal(1)
    return best

def to_cents(self, minor, cur, t):
    """Minor units of the row's currency converted to EUR cents, rounded once half to even."""
    major = Decimal(minor) / Decimal(10) ** CUR_EXP[cur]
    return int(qd(major * self.fx_at(cur, t), 2).scaleb(2))

def rate_major(self, eng, t):
    y, m, d = civil_from_days(t // DAY)
    mo = m if (y, m) in ((2025, 7), (2025, 8), (2025, 9)) else 7
    minor, cur = self.rates.get((eng, mo), (0, 'EUR'))
    return (Decimal(minor) / Decimal(10) ** CUR_EXP[cur], cur)

def ts_cents(self, v):
    rate, cur = self.rate_major(v['engineer'], v['worked'])
    return -int(qd(v['hours'] * rate * self.fx_at(cur, v['worked']), 2).scaleb(2))

def team_on(self, eng, t):
    z = t // DAY
    for e, team, fte, oncall, start, end in self.allocs:
        if e == eng and start <= z and (end is None or z <= end):
            return team
    return None

def deferred(self):
    out = []
    for fname in AMEND:
        t = SCHEMA[fname][0][0]
        recs = self.records(fname, t)
        for rid, revs in sorted(self.revs[fname][t].items()):
            applicable = [r for r in revs if r.st != 'draft' and r.rec_at < CUT]
            for r in revs:
                if r.rec_at < CUT or r.st == 'draft':
                    continue
                v = r.v
                action = 'new' if not applicable else 'void' if r.st == 'void' else 'revise'
                target = measure = cur = amd = None
                if fname == 'advisory_rescores.parquet':
                    target = self.vid(v['vuln'])
                    if v['approved'] is True and r.st != 'void':
                        measure = 'cvss'
                        if target not in self.vec_cache:
                            self.vec_cache[target] = self.vuln_vector(target)
                        cv = self.vec_cache[target]
                        cur = cvss_base(cv) if cv else None
                        amd = cvss_base(v['vector'])
                    else:
                        measure = 'none'
                elif fname == 'remediation_timesheets.csv':
                    measure = 'cents'
                    target = self.team_on(v['engineer'], v['worked'])
                    cur = self.ts_cents(recs[rid][0]) if rid in recs else None
                    amd = None if r.st == 'void' else self.ts_cents(v)
                elif fname == 'ledger_journal.db':
                    measure = 'cents'
                    target = v['team']
                    if rid in recs and rid not in self.cancelled:
                        iv = recs[rid][0]
                        cur = self.to_cents(iv['amount'], iv['currency'], iv['booked'])
                    amd = None if r.st == 'void' else self.to_cents(v['amount'], v['currency'], v['booked'])
                else:
                    target = v['service']
                    measure = 'none'
                if measure == 'cvss':
                    cur = qd(cur, 1) if cur is not None else None
                    amd = qd(amd, 1)
                out.append({'kind': 'deferred', 'amendment': f'{fname}#{rid}#{r.rev}', 'file': fname, 'rid': rid, 'rev': r.rev, 'recorded': iso(r.rec_at), 'action': action, 'target': target, 'measure': measure, 'current': cur, 'amended': amd})
    out.sort(key=lambda d: (d['recorded'], d['amendment']))
    return out

def p1_rows(self):
    pk = []
    owners = {}
    for v, x, _ in self.records('package_owners.json', 'owners').values():
        if v['role'] != 'reviewer' and v['effective'] < CUT:
            k = self.pkey(v['eco'], v['name'])
            if k not in owners or (v['effective'], x.rid) > owners[k][0]:
                owners[k] = ((v['effective'], x.rid), v['team'])
    for key in sorted(self.rel):
        rels = {vs: r for vs, r in self.rel[key].items() if r['pub'] < CUT}
        if not rels:
            continue
        yk = [vs for vs in rels if self.yanked_at(key, vs, CUT)]
        stable = [r['ver'] for vs, r in rels.items() if r['ver'].pre is None]
        latest = max(stable) if stable else None
        lic = obl = None
        if latest is not None:
            lic, obl = self.license_of(key, latest)
        pk.append({'package': key, 'ecosystem': key.split(':', 1)[0], 'owner_team': owners[key][1] if key in owners else None, 'releases': len(rels), 'yanked': len(yk), 'latest': str(latest) if latest else None, 'latest_license': lic, 'obligation': obl})
    pins = [{'service': p['service'], 'package': p['package'], 'scope': p['scope'], 'constraint': p['constraint'], 'source': p['source'], 'pinned': str(p['pinned']) if p['pinned'] is not None else None, 'disposition': p['disposition'], 'license': p['license'], 'obligation': p['obligation']} for p in self.pins]
    sv = [{'service': k, 'team': s['team'], 'tier': s['tier'], 'region': s['region'], 'status': s['status'], 'deploys': s['deploys'], 'weight': s['weight']} for k, s in sorted(self.svc.items())]
    tm = []
    for k in sorted(self.teams):
        t = self.teams[k]
        cap = None if t['model'] == 'uncapped' else int(t['cap'].to_integral_value(rounding=ROUND_FLOOR))
        tm.append({'team': k, 'model': t['model'], 'capacity_hours': cap, 'engineers': len(t['engs'])})
    led = list(self.openings)
    led += [dict(e, booked=iso(e['booked'])) for e in self.entries]
    led += self.closings
    ctl = []
    for rid, (v, x, _) in self.records('control_totals.html', 'controls').items():
        ctl.append({'kind': 'control', 'control': v['control'], 'scope': v['scope'], 'measure': v['measure'], 'value': v['value']})
    led += sorted(ctl, key=lambda r: r['control'])
    led += self.custody()
    led += self.deferred()
    return {'packages.jsonl': pk, 'pins.jsonl': pins, 'exposures.jsonl': self.exposures, 'services.jsonl': sv, 'teams.csv': tm, 'ledger.jsonl': led}
Close.build_ledger = build_ledger
Close.fx_at = fx_at
Close.to_cents = to_cents
Close.rate_major = rate_major
Close.ts_cents = ts_cents
Close.team_on = team_on
Close.deferred = deferred
Close.p1_rows = p1_rows
# ---- cli

import os
import shutil
import sys
import tempfile


def stage1_files(rows):
    files = {}
    for name in P1_FILES:
        if name == 'teams.csv':
            files[name] = teams_bytes(rows[name])
            continue
        if name == 'ledger.jsonl':
            clean = [{k: r[k] for k in LEDGER_KEYS[r['kind']]} for r in rows[name]]
        else:
            clean = [{k: r[k] for k in P1_KEYS[name]} for r in rows[name]]
        files[name] = jsonl_bytes(clean + evidence_rows(name, clean, wide=True))
    return files


def complete_files(data_dir):
    """Compute all shared values in memory and serialise each artifact once."""
    close = Close(data_dir)
    p1 = close.stage1()
    raw1 = stage1_files(p1)
    p2 = stage2(p1, raw1)
    raw2 = {name: rich_doc_bytes(name, p2[name]) for name in P2_FILES}
    p3 = stage3(p1, raw1, p2, raw2)
    raw3 = {name: rich_doc_bytes(name, p3[name]) for name in P3_FILES}
    files = dict(raw1)
    files.update(raw2)
    files.update(raw3)
    files.update(supplemental_bytes(p1, p2, p3))
    return files


def write_complete(out_dir, files):
    """Publish a complete directory only after every byte is ready.

    Entries of an existing output directory that are not artifacts of the close (the program itself, for
    example) are carried over unchanged; the earlier artifacts are replaced as one set.
    """
    out = Path(out_dir)
    parent = out.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix='.helios-complete-', dir=str(parent)))
    try:
        for name in sorted(files):
            (tmp / name).write_bytes(files[name])
        if not out.exists():
            os.replace(tmp, out)
            return
        old = Path(tempfile.mkdtemp(prefix='.helios-old-', dir=str(parent)))
        old.rmdir()
        os.replace(out, old)
        kept = []
        try:
            for entry in sorted(old.iterdir()):
                if entry.name not in files:
                    os.replace(entry, tmp / entry.name)
                    kept.append(entry.name)
            os.replace(tmp, out)
        except OSError:
            for name in kept:
                if (tmp / name).exists():
                    os.replace(tmp / name, old / name)
            os.replace(old, out)
            raise
        shutil.rmtree(old)
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)


USAGE = 'usage: build.py DATA_DIR OUT_DIR'


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print('error: ' + USAGE, file=sys.stderr)
        return 2
    data_dir, out_dir = map(Path, argv)
    if not data_dir.is_dir() or not os.access(data_dir, os.R_OK):
        print(f'error: unreadable input directory {data_dir}', file=sys.stderr)
        return 3
    try:
        files = complete_files(data_dir)
        write_complete(out_dir, files)
    except (InputError, StageError, OSError, ValueError, KeyError, UnicodeDecodeError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
