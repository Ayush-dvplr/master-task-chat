"""helios_close.domain: part of the Q3 close program (see README.md)."""
from __future__ import annotations

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
        return (self.major, self.minor, self.patch, 0, self.pre[0], str(self.pre[1]))

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
        """Interval membership plus the prerelease rule of close_contract.md section 5.3."""
        if self.exact:
            return v == self.lo
        if self.lo is not None and (v < self.lo or (not self.lo_inc and v == self.lo)):
            return False
        if self.hi is not None and (self.hi < v or (not self.hi_inc and v == self.hi)):
            return False
        if v.pre is not None and self.lo is not None and self.lo.pre is not None:
            return self.lo.core() == v.core()
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
    if v.major > 0 or v.minor > 0:
        hi = Ver(v.major + 1, 0, 0)
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
        ru = roundup30 if head == 'CVSS:3.0' else lambda x: round(x, 1)
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

def affected(ranges, v):
    for lo, hi, inc in ranges:
        if lo is not None and v < lo:
            continue
        if hi is None:
            return True
        if v < hi:
            return True
    return False
REGIONS = ['eu-west', 'us-central', 'ap-south', 'ap-north', 'ap-southeast', 'global']
REGION_ZONE = {'eu-west': 'IE', 'us-central': 'US', 'ap-south': 'IN', 'ap-north': 'JP', 'ap-southeast': 'AU', 'global': 'UTC'}
TIER_WEIGHT = {0: D('4.0'), 1: D('2.5'), 2: D('1.5'), 3: D('1.0')}
SLA_MATRIX = {'critical': [7, 10, 15, 20], 'high': [15, 20, 30, 45], 'medium': [30, 45, 60, 90], 'low': [60, 90, 120, 180], 'none': [180, 180, 180, 180]}
BASE_HOURS = {'critical': D('16'), 'high': D('8'), 'medium': D('4'), 'low': D('2'), 'none': D('1')}

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
