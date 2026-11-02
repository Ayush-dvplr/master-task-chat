"""Verifier for helios-training-component-inventory-exposure-close.

The expected stage files are rebuilt from the seeded world model of the close (the same model that wrote the
exports); the delivered program is also run, stage by stage, on unseen corpora and on verifier-built upstream directories.
"""
from __future__ import annotations

import json
from pathlib import Path

from rewardkit import criteria, criterion

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

class Rng:
    """SplitMix64; stable across interpreters."""

    def __init__(self, seed):
        self.s = int(seed) * 11400714819323198485 + 7146057691288625177 & MASK64

    def u64(self):
        self.s = self.s + 11400714819323198485 & MASK64
        z = self.s
        z = (z ^ z >> 30) * 13787848793156543929 & MASK64
        z = (z ^ z >> 27) * 10723151780598845931 & MASK64
        return z ^ z >> 31

    def below(self, n):
        return self.u64() % n if n > 0 else 0

    def rint(self, lo, hi):
        return lo + self.below(hi - lo + 1)

    def chance(self, p):
        return self.u64() < int(p * 18446744073709551616)

    def pick(self, seq):
        return seq[self.below(len(seq))]

    def shuffle(self, seq):
        for i in range(len(seq) - 1, 0, -1):
            j = self.below(i + 1)
            seq[i], seq[j] = (seq[j], seq[i])
        return seq

    def sample(self, seq, k):
        pool = list(seq)
        self.shuffle(pool)
        return pool[:k]

    def wpick(self, items, weights):
        tot = sum(weights)
        x = self.below(tot)
        for it, w in zip(items, weights):
            if x < w:
                return it
            x -= w
        return items[-1]

    def fork(self, tag):
        h = _hl.blake2b(f'{self.s}:{tag}'.encode(), digest_size=8).digest()
        return Rng(int.from_bytes(h, 'big'))

def derive(seed, tag):
    h = _hl.blake2b(f'{seed}:{tag}'.encode(), digest_size=8).digest()
    return int.from_bytes(h, 'big') & (1 << 63) - 1

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

def ambiguous_or_gap(t):
    """True when the wall clock of t in some zone is within two hours of a transition (avoided in naive cells)."""
    for z in ('IE', 'US', 'AU'):
        if zone_offset(z, t - 7200) != zone_offset(z, t + 7200):
            return True
    return False

def nudge(t):
    while ambiguous_or_gap(t):
        t += 3 * 3600
    return t

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

def num_out(x, dp):
    """A JSON number written at exactly dp decimal places (as a Decimal-preserving float string)."""
    return q(x, dp)

def crc(s):
    return _zlib.crc32(s.encode('utf-8')) & 4294967295

def sha256_bytes(b):
    return _hl.sha256(b).hexdigest()

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

def spell_ver(v, eco, conv, build_n=0):
    """Raw spelling of canonical version v under a version convention (close_contract.md section 5.2)."""
    base = f'{v.major}.{v.minor}.{v.patch}'
    if conv == 'native':
        if eco == 'pypi':
            return base + (f'{PEP_TAG[v.pre[0]]}{v.pre[1]}' if v.pre else '')
        if eco == 'maven':
            return base + (f'-{MVN_TAG[v.pre[0]]}{v.pre[1]}' if v.pre else '')
        return str(v)
    if conv == 'vprefix':
        return 'v' + str(v)
    if conv == 'build':
        return str(v) + f'+build.{build_n}'
    return str(v)

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
        if v.pre is not None:
            return self.lo is not None and self.lo.pre is not None and (self.lo.core() == v.core())
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

def spell_cons(c_kind, v, eco, hi=None):
    """Raw spelling of a constraint of a given kind in the ecosystem's own syntax, and its canonical interval."""
    vs = str(v)
    if c_kind == 'exact':
        cons = Cons(v, True, v, True, True)
        raw = {'npm': vs, 'cargo': '=' + vs, 'pypi': '==' + spell_ver(v, 'pypi', 'native'), 'maven': f"[{spell_ver(v, 'maven', 'native')}]"}[eco]
        return (raw, cons)
    if c_kind == 'caret':
        cons = caret(v)
        raw = {'npm': '^' + vs, 'cargo': vs, 'pypi': None, 'maven': None}[eco]
        if raw is None:
            raw, cons = spell_cons('range', v, eco, cons.hi)
        return (raw, cons)
    if c_kind == 'tilde':
        cons = tilde(v)
        raw = {'npm': '~' + vs, 'cargo': '~' + vs, 'pypi': '~=' + spell_ver(v, 'pypi', 'native'), 'maven': None}[eco]
        if raw is None:
            raw, cons = spell_cons('range', v, eco, cons.hi)
        return (raw, cons)
    if c_kind == 'compat2':
        lo = Ver(v.major, v.minor, 0)
        cons = Cons(lo, True, Ver(v.major + 1, 0, 0), False)
        if eco == 'pypi':
            return (f'~={v.major}.{v.minor}', cons)
        return spell_cons('range', lo, eco, cons.hi)
    if c_kind == 'wild':
        lo = Ver(v.major, v.minor, 0)
        cons = Cons(lo, True, Ver(v.major, v.minor + 1, 0), False)
        raw = {'npm': f'{v.major}.{v.minor}.x', 'cargo': f'{v.major}.{v.minor}.*', 'pypi': f'=={v.major}.{v.minor}.*', 'maven': None}[eco]
        if raw is None:
            return spell_cons('range', lo, eco, cons.hi)
        return (raw, cons)
    if c_kind == 'range':
        hi = hi or Ver(v.major + 1, 0, 0)
        cons = Cons(v, True, hi, False)
        if eco == 'npm':
            return (f'>={v} <{hi}', cons)
        if eco == 'cargo':
            return (f'>={v}, <{hi}', cons)
        if eco == 'pypi':
            return (f">={spell_ver(v, 'pypi', 'native')},<{hi}", cons)
        return (f"[{spell_ver(v, 'maven', 'native')},{hi})", cons)
    if c_kind == 'openlow':
        hi = hi or Ver(v.major + 1, 0, 0)
        cons = Cons(v, False, hi, True)
        if eco == 'maven':
            return (f"({spell_ver(v, 'maven', 'native')},{hi}]", cons)
        if eco == 'pypi':
            return (f">{spell_ver(v, 'pypi', 'native')},<={hi}", cons)
        if eco == 'cargo':
            return (f'>{v}, <={hi}', cons)
        return (f'>{v} <={hi}', cons)
    if c_kind == 'floor':
        cons = Cons(v, True, None, False)
        raw = {'npm': f'>={v}', 'cargo': f'>={v}', 'pypi': f">={spell_ver(v, 'pypi', 'native')}", 'maven': f"[{spell_ver(v, 'maven', 'native')},)"}[eco]
        return (raw, cons)
    raise ValueError(c_kind)

def resolve_pin(cons, releases, t_res):
    """Highest-precedence eligible release admitted by cons (close_contract.md section 5.4).

    releases: list of (Ver, published, yanked_at_fn) with yanked_at_fn(t) -> bool.
    """
    best = None
    for v, pub, yank_fn in releases:
        if pub >= t_res or not cons.admits(v):
            continue
        if yank_fn(t_res) and (not cons.exact):
            continue
        if best is None or best < v:
            best = v
    return best
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

def cvss_raw(vec):
    """The unrounded base score (impact plus exploitability before Roundup), used only by shortcut baselines."""
    head, m = cvss_parts(vec)
    iss = 1 - (1 - CIA_W[m['C']]) * (1 - CIA_W[m['I']]) * (1 - CIA_W[m['A']])
    changed = m['S'] == 'C'
    impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15 if changed else 6.42 * iss
    pr = (PR_C if changed else PR_U)[m['PR']]
    expl = 8.22 * AV_W[m['AV']] * AC_W[m['AC']] * pr * UI_W[m['UI']]
    if impact <= 0:
        return 0.0
    return min((1.08 if changed else 1.0) * (impact + expl), 10)

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

def make_vector(rng, version='CVSS:3.1'):
    m = {'AV': rng.wpick(['N', 'A', 'L', 'P'], [60, 12, 22, 6]), 'AC': rng.wpick(['L', 'H'], [75, 25]), 'PR': rng.wpick(['N', 'L', 'H'], [55, 33, 12]), 'UI': rng.wpick(['N', 'R'], [62, 38]), 'S': rng.wpick(['U', 'C'], [78, 22]), 'C': rng.wpick(['H', 'L', 'N'], [45, 35, 20]), 'I': rng.wpick(['H', 'L', 'N'], [40, 35, 25]), 'A': rng.wpick(['H', 'L', 'N'], [40, 25, 35])}
    if m['C'] == m['I'] == m['A'] == 'N':
        m['C'] = 'L'
    return version + '/' + '/'.join((f'{k}:{m[k]}' for k in METRICS))
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
        if v < hi or (inc and v == hi):
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
SYL = ['al', 'ber', 'cor', 'dex', 'el', 'fen', 'gra', 'hal', 'ion', 'jet', 'kel', 'lum', 'mar', 'nox', 'or', 'pax', 'quin', 'ras', 'sol', 'tor', 'ul', 'vex', 'wyn', 'yar', 'zed', 'bri', 'cal', 'dor', 'fyr', 'gal', 'hex', 'kin', 'lor', 'mon', 'nim', 'pel']
WORDS = ['json', 'yaml', 'http', 'auth', 'cache', 'queue', 'log', 'metrics', 'crypto', 'parse', 'stream', 'pool', 'grpc', 'proto', 'retry', 'shim', 'codec', 'lint', 'test', 'mock', 'tls', 'dns', 'sql', 'orm', 'cli', 'async', 'trace', 'image', 'zip', 'xml']
TEAM_NAMES = ['Payments', 'Search', 'Identity', 'Edge', 'Storage', 'Billing', 'Mobile', 'Ledger', 'Fraud', 'Growth', 'Platform', 'Infra', 'Data', 'Analytics', 'Messaging', 'Catalog', 'Checkout', 'Risk', 'Support', 'Notify', 'Media', 'Maps', 'Pricing', 'Inventory', 'Shipping', 'Partners', 'Ads', 'Insights', 'Security', 'Compliance', 'Developer', 'Release', 'Observability', 'Network', 'Compute', 'Runtime', 'Gateway', 'Docs', 'Learning', 'Sandbox', 'Atlas', 'Beacon', 'Cobalt', 'Delta', 'Ember', 'Falcon', 'Garnet', 'Harbor', 'Indigo', 'Juniper']
REGION_CUR = {'eu-west': 'EUR', 'us-central': 'USD', 'ap-south': 'INR', 'ap-north': 'JPY', 'ap-southeast': 'USD', 'global': 'GBP'}
GHSA_ALPHA = '23456789cfghjmpqrvwx'
HOME_SOURCES = ['core', 'edge', 'data', 'legacy', 'image']
MANIFEST_FILE = {'core': 'manifests_core.csv', 'edge': 'manifests_edge.jsonl', 'data': 'manifests_data.yaml', 'legacy': 'manifests_legacy.txt'}
LEGACY_MIGRATION = epoch(2025, 8, 4, 0, 0)
LEGACY_ALIAS_CUTOFF = epoch(2024, 1, 1)

class World:
    pass

def _name(rng, eco, used):
    while True:
        a = rng.pick(SYL) + rng.pick(SYL)
        w = rng.pick(WORDS)
        style = rng.below(3)
        if eco == 'maven':
            grp = 'org.' + rng.pick(SYL) + rng.pick(SYL)
            art = a + '-' + w if style else a.capitalize() + w.upper()
            n = f'{grp}:{art}'
        elif eco == 'npm':
            n = (f'@{rng.pick(SYL)}{rng.pick(SYL)}/' if style == 0 else '') + f'{a}-{w}'
        else:
            n = f'{a}-{w}' if style else f'{w}-{a}'
        if n not in used:
            used.add(n)
            return n

def gen_time(rng, lo, hi, gran=60):
    """A random instant in [lo, hi), moved off any daylight-saving transition window (wall clocks are never ambiguous)."""
    return nudge(lo + rng.below((hi - lo) // gran) * gran)

def _versions(rng, n):
    """n increasing canonical versions with a few prereleases and 0.x lines."""
    major = rng.wpick([0, 1, 2, 3], [25, 40, 25, 10])
    minor, patch = (rng.rint(0, 4), rng.rint(0, 6))
    out = []
    while len(out) < n:
        step = rng.wpick(['patch', 'minor', 'major', 'pre'], [55, 28, 7, 10])
        if step == 'patch':
            patch += 1
        elif step == 'minor':
            minor, patch = (minor + 1, 0)
        elif step == 'major':
            major, minor, patch = (major + 1, 0, 0)
        if step == 'pre':
            base = (major, minor, patch + 1)
            tag = rng.pick(PRE_TAGS)
            k = rng.rint(1, 3)
            nums = sorted(rng.sample(list(range(1, 13)), k))
            for x in nums:
                out.append(Ver(base[0], base[1], base[2], (tag, x)))
            continue
        out.append(Ver(major, minor, patch))
    seen, uniq = (set(), [])
    for v in out:
        if v.key() not in seen:
            seen.add(v.key())
            uniq.append(v)
    return uniq[:n]

def build_world(seed, scale):
    rng = Rng(seed)
    W = World()
    W.scale = scale
    n_teams = max(10, round(48 * scale))
    n_eng = max(200, round(3400 * scale))
    n_svc = max(150, round(2400 * scale))
    n_pkg_eco = max(70, round(800 * scale))
    n_vuln = max(220, round(2750 * scale))
    W.teams = []
    for i in range(n_teams):
        tid = f'T{i + 1:03d}'
        W.teams.append({'team': tid, 'name': TEAM_NAMES[i % len(TEAM_NAMES)] + ('' if i < len(TEAM_NAMES) else f' {i // len(TEAM_NAMES) + 1}'), 'cost_center': f'CC-{4100 + i * 7}', 'region': rng.pick(REGIONS[:5]), 'model': 'uncapped' if i % 11 == 5 else 'capped', 'zero': i % 13 == 7})
    W.team_ids = [t['team'] for t in W.teams]
    W.team_by = {t['team']: t for t in W.teams}
    W.engineers = []
    for i in range(n_eng):
        eid = f'e{i + 1:05d}'
        team = rng.pick(W.team_ids)
        segs = []
        start = Q_START_DAY - rng.rint(30, 700)
        nseg = rng.wpick([1, 2, 3, 4], [22, 34, 26, 18])
        for k in range(nseg):
            if k < nseg - 1:
                end = rng.rint(Q_START_DAY - 20, CUT_DAY + 10) if k == nseg - 2 else rng.rint(start + 20, Q_START_DAY + 40)
                end = max(end, start + 10)
            else:
                end = None if rng.chance(0.8) else rng.rint(Q_START_DAY + 10, CUT_DAY + 60)
            fte = D(rng.pick(['1.0', '1.0', '0.8', '0.5', '0.6']))
            if W.team_by[team]['zero']:
                fte = D('0')
            segs.append({'team': team, 'fte': fte, 'oncall': D(rng.pick(['0', '0', '0.1', '0.2', '0.25'])), 'start': start, 'end': end})
            if end is None:
                break
            start = end
            if rng.chance(0.4):
                team = rng.pick(W.team_ids)
        cur = REGION_CUR[W.team_by[segs[0]['team']]['region']]
        base = rng.rint(4000, 12000) if cur != 'JPY' else rng.rint(5000, 15000) * 100
        if cur == 'INR':
            base = rng.rint(150000, 600000)
        rates = {}
        for mo in (7, 8, 9):
            rates[mo] = (cur, base + rng.rint(-200, 400) * (100 if cur == 'JPY' else 1))
        W.engineers.append({'eng': eid, 'segs': segs, 'rates': rates})
    W.eng_by = {e['eng']: e for e in W.engineers}
    used = set()
    W.packages = []
    for eco in ECOS:
        for i in range(n_pkg_eco):
            name = _name(rng, eco, used)
            key = f'{eco}:{name}'
            nrel = rng.rint(6, 14)
            vers = _versions(rng, nrel)
            t0 = gen_time(rng, HIST_START, Q_START - 60 * DAY)
            span = CUT + 18 * DAY - t0
            pubs = sorted((gen_time(rng, t0, t0 + span) for _ in vers))
            rels = []
            for v, p in zip(vers, pubs):
                p = nudge(p)
                yev = []
                if rng.chance(0.22):
                    ty = nudge(gen_time(rng, p + DAY, CUT + 15 * DAY))
                    yev.append((ty, True))
                    if rng.chance(0.25):
                        yev.append((nudge(gen_time(rng, ty + DAY, ty + 40 * DAY)), False))
                rels.append({'ver': v, 'pub': p, 'yank': yev, 'sha': f'{rng.u64():016x}', 'quarantine': rng.chance(0.012) and p < CUT - DAY, 'lic': None})
            internal = rng.chance(0.3)
            W.packages.append({'key': key, 'eco': eco, 'name': name, 'rels': rels, 'internal': internal, 'owners': [], 'aliases': [], 'typos': [], 'majors': sorted({r['ver'].major for r in rels})})
    mv = [p for p in W.packages if p['eco'] == 'maven' and ':' in p['name']]
    for p in mv[:max(4, len(mv) // 40)]:
        g, a = p['name'].split(':')
        twin_name = f'{g}:{a.swapcase()}'
        if twin_name in used:
            continue
        used.add(twin_name)
        vers = _versions(rng, rng.rint(5, 9))
        t0 = gen_time(rng, HIST_START, Q_START - 60 * DAY)
        pubs = sorted((gen_time(rng, t0, CUT - DAY) for _ in vers))
        rels = [{'ver': v, 'pub': nudge(pp), 'yank': [], 'sha': f'{rng.u64():016x}', 'quarantine': False, 'lic': None} for v, pp in zip(vers, pubs)]
        W.packages.append({'key': f'maven:{twin_name}', 'eco': 'maven', 'name': twin_name, 'rels': rels, 'internal': False, 'owners': [], 'aliases': [], 'typos': [], 'majors': sorted({r['ver'].major for r in rels}), 'twin': p['key']})
    W.pkg_by = {p['key']: p for p in W.packages}
    for p in W.packages:
        for r in p['rels']:
            r['lic'] = rng.wpick(['MIT', 'Apache-2.0', 'BSD-3-Clause', 'ISC', 'MPL-2.0', 'LGPL-2.1-or-later', 'GPL-2.0-only', 'GPL-3.0-or-later', 'AGPL-3.0-only', 'MIT OR Apache-2.0', 'Apache-2.0 AND MIT', 'GPL-2.0-only WITH Classpath-exception-2.0', 'LGPL-3.0-only OR GPL-3.0-only', 'NOASSERTION'], [26, 22, 10, 6, 6, 5, 4, 3, 2, 7, 3, 2, 2, 2])
            if rng.chance(0.85):
                pass
        if p['internal']:
            t = gen_time(rng, HIST_START, Q_START)
            team = rng.pick(W.team_ids)
            p['owners'].append((t, team))
            if rng.chance(0.35):
                t2 = gen_time(rng, t + DAY, CUT + 15 * DAY)
                p['owners'].append((t2, rng.pick(W.team_ids)))
        if rng.chance(0.18):
            old = _name(rng, p['eco'], used)
            eff = gen_time(rng, HIST_START, CUT + 10 * DAY)
            legacy_only = eff < LEGACY_ALIAS_CUTOFF and rng.chance(0.5)
            confirmed = eff < LEGACY_ALIAS_CUTOFF or (eff < CUT and rng.chance(0.75))
            p['aliases'].append({'old': old, 'eff': nudge(eff), 'confirmed': confirmed, 'legacy_only': legacy_only})
            for r in p['rels']:
                r.setdefault('under', None)
                if r['pub'] < eff and rng.chance(0.6):
                    r['under'] = old
        if rng.chance(0.07):
            p['typos'].append(_name(rng, p['eco'], used))
    for p in W.packages:
        for r in p['rels']:
            r.setdefault('under', None)
    W.services = []
    for i in range(n_svc):
        sid = f'svc-{i + 1:05d}'
        region = rng.wpick(REGIONS, [26, 34, 12, 10, 12, 6])
        home = rng.wpick(HOME_SOURCES, [24, 24, 24, 20, 8])
        archived = home == 'core' and rng.chance(0.06)
        tier = rng.wpick([0, 1, 2, 3], [10, 30, 35, 25])
        t_own = gen_time(rng, HIST_START, Q_START)
        owners = [(t_own, rng.pick(W.team_ids))]
        if rng.chance(0.22):
            owners.append((nudge(gen_time(rng, t_own + DAY, CUT + 12 * DAY)), rng.pick(W.team_ids)))
        life = []
        migrated = rng.chance(0.07)
        if rng.chance(0.06):
            life.append(('decommissioned', nudge(gen_time(rng, Q_START - 90 * DAY, CUT + 14 * DAY))))
            if rng.chance(0.2):
                life.append(('restored', nudge(gen_time(rng, life[-1][1] + DAY, life[-1][1] + 30 * DAY))))
        if archived:
            life.append(('archived', nudge(gen_time(rng, Q_START - 200 * DAY, Q_START - 10 * DAY))))
        life.sort(key=lambda x: x[1])
        nm = rng.pick(WORDS).capitalize() + ' ' + rng.pick(['API', 'Worker', 'Gateway', 'Service', 'Cron', 'UI'])
        if rng.chance(0.08):
            nm += ', "' + rng.pick(['blue', 'green', 'canary']) + '" lane'
        if rng.chance(0.03):
            nm += '\r\n(legacy)'
        covered = region != 'global'
        W.services.append({'svc': sid, 'name': nm, 'region': region, 'home': home, 'archived': archived, 'tier': tier, 'owners': owners, 'life': life, 'migrated': migrated, 'covered': covered, 'deps': [], 'deploys': [], 'freeze': [], 'sla': {}, 'legacy_ids': []})
    W.svc_by = {s['svc']: s for s in W.services}
    pk_by_eco = {e: [p for p in W.packages if p['eco'] == e] for e in ECOS}
    for s in W.services:
        nd = rng.rint(8, 19)
        chosen = set()
        for _ in range(nd):
            eco = rng.wpick(ECOS, [30, 32, 22, 16])
            p = rng.pick(pk_by_eco[eco])
            scope = rng.wpick(['runtime', 'dev', 'test'], [66, 22, 12])
            if (p['key'], scope) in chosen:
                continue
            chosen.add((p['key'], scope))
            pre = [r for r in p['rels'] if r['pub'] < CUT - 40 * DAY] or p['rels'][:1]
            r = rng.pick(pre)
            v = r['ver']
            if v.pre and rng.chance(0.6):
                v = Ver(v.major, v.minor, v.patch)
            ck = rng.wpick(['caret', 'tilde', 'exact', 'range', 'wild', 'compat2', 'openlow', 'floor'], [30, 14, 12, 14, 8, 8, 6, 8])
            if p['eco'] == 'maven' and ck in ('caret', 'tilde', 'wild', 'compat2'):
                ck = rng.pick(['range', 'exact', 'openlow'])
            if ck == 'exact':
                v = r['ver']
            raw, cons = spell_cons(ck, v, p['eco'])
            locked = nudge(gen_time(rng, Q_START - 120 * DAY, CUT - DAY))
            if rng.chance(0.07):
                locked = nudge(gen_time(rng, CUT + DAY, CUT + 15 * DAY))
            removed = None
            if rng.chance(0.04):
                removed = nudge(gen_time(rng, Q_START, CUT + 10 * DAY))
            d = {'svc': s['svc'], 'pkg': p['key'], 'scope': scope, 'raw': raw, 'cons': cons, 'ckind': ck, 'locked': locked, 'removed': removed, 'file': MANIFEST_FILE.get(s['home']), 'override': None}
            s['deps'].append(d)
    W.overrides = []
    taken_o = set()
    for s in W.services:
        for d in s['deps']:
            if (s['svc'], d['pkg']) in taken_o:
                continue
            if rng.chance(0.045):
                taken_o.add((s['svc'], d['pkg']))
                p = W.pkg_by[d['pkg']]
                r = rng.pick([x for x in p['rels'] if x['pub'] < CUT] or p['rels'][:1])
                vf = rng.rint(Q_START_DAY - 60, CUT_DAY - 5)
                vt = rng.rint(CUT_DAY - 10, CUT_DAY + 40)
                approved = rng.chance(0.7)
                o = {'oid': None, 'svc': s['svc'], 'pkg': d['pkg'], 'ver': r['ver'], 'from': vf, 'to': vt, 'approved': approved, 'decided': nudge(gen_time(rng, Q_START - 30 * DAY, CUT - DAY))}
                W.overrides.append(o)
                d['override'] = o
    for s in W.services:
        nd = rng.wpick([0, 1, 3, 5, 7, 12, 30, 120], [6, 8, 20, 22, 20, 14, 8, 2])
        for _ in range(nd):
            t = gen_time(rng, Q_START - 20 * DAY, CUT + 10 * DAY)
            if rng.chance(0.18):
                t = rng.pick([Q_START, CUT]) + rng.rint(-300, 300) * 60
            if CUT - 3600 <= t < CUT + 3600 or Q_START - 900 <= t < Q_START + 900:
                t += 4 * 3600
            outcome = rng.wpick(['succeeded', 'failed', 'rolled_back'], [80, 12, 8])
            s['deploys'].append({'t': t, 'outcome': outcome})
    for s in W.services:
        for _ in range(rng.wpick([1, 2, 3, 4, 5], [12, 25, 30, 20, 13])):
            a = rng.rint(Q_START_DAY - 30, CUT_DAY + 10)
            s['freeze'].append((a, a + rng.rint(1, 6)))
        s['freeze'].sort()
    for s in W.services:
        n = int(s['svc'][4:])
        forms = [f'SVC_{n:05d}', f'svc{n}', f"{s['home']}/{n}", f'cmdb-{n * 7 + 3}']
        rng.shuffle(forms)
        s['legacy_ids'] = forms[:rng.rint(2, 4)]
    for s in W.services:
        for sev in ('critical', 'high', 'medium', 'low'):
            if rng.chance(0.25):
                s['sla'][sev] = (rng.pick([3, 5, 7, 10, 14, 21, 30, 45, 60]), rng.rint(Q_START_DAY - 200, CUT_DAY - 1))
    W.vulns = []
    years = [2023, 2024, 2025]
    seq = {y: 1000 for y in years}
    used_ids = set()
    for i in range(n_vuln):
        y = rng.wpick(years, [20, 40, 40])
        cve = None
        if rng.chance(0.82):
            seq[y] += rng.rint(1, 40)
            num = seq[y] if rng.chance(0.9) else rng.rint(10, 999)
            while f'CVE-{y}-{num:04d}' in used_ids:
                num = rng.rint(10, 99999)
            cve = f'CVE-{y}-{num:04d}'
            used_ids.add(cve)
        ghsa = 'GHSA-' + '-'.join((''.join((rng.pick(GHSA_ALPHA) for _ in range(4))) for _ in range(3))) if rng.chance(0.9) or cve is None else None
        ecos = rng.pick(ECOS)
        osv = None
        while osv is None or osv in used_ids:
            osv = {'pypi': f'PYSEC-{y}-{rng.rint(10, 999)}', 'cargo': f'RUSTSEC-{y}-{rng.rint(1, 9999):04d}'}.get(ecos, f'OSV-{y}-{rng.rint(10000, 99999)}')
        used_ids.add(osv)
        canon = cve or ghsa or osv
        if rng.chance(0.7):
            pub = nudge(gen_time(rng, Q_START - 75 * DAY, CUT - DAY))
            y = 2025
        else:
            pub = nudge(gen_time(rng, epoch(y, 1, 1), min(epoch(y, 12, 31), CUT - DAY)))
        if rng.chance(0.03):
            pub = nudge(gen_time(rng, CUT, CUT + 12 * DAY))
        vec_v = 'CVSS:3.0' if rng.chance(0.12) else 'CVSS:3.1'
        nvd_vec = make_vector(rng, vec_v) if cve else None
        ghsa_vec = make_vector(rng) if ghsa else None
        if nvd_vec and ghsa_vec and rng.chance(0.55):
            ghsa_vec = nvd_vec
        resc = []
        for _ in range(rng.wpick([0, 1, 2, 3, 4, 5, 6], [8, 14, 18, 20, 18, 12, 10])):
            at = nudge(gen_time(rng, pub, max(pub + DAY, CUT + 14 * DAY)))
            resc.append({'vec': make_vector(rng), 'at': at, 'approved': rng.chance(0.2)})
        prec_vec = rng.wpick(['default', 'ghsa', 'nvd'], [80, 14, 6])
        prec_pub = rng.wpick(['default', 'ghsa'], [85, 15])
        pub_unknown = pub < CUT and rng.chance(0.02)
        withdrawn = None
        if rng.chance(0.04):
            withdrawn = nudge(gen_time(rng, pub + DAY, CUT + 14 * DAY))
        cands = [p for p in W.packages if p['eco'] == ecos] if rng.chance(0.7) else W.packages
        naff = rng.wpick([1, 2, 3, 4, 5, 6], [18, 22, 22, 16, 12, 10])
        aff = []
        for p in rng.sample(cands, min(naff, len(cands))):
            vs = sorted((r['ver'] for r in p['rels']))
            k = rng.below(len(vs))
            evs = [('introduced', '0' if rng.chance(0.35) else vs[k])]
            later = [v for v in vs if vs[k] < v]
            if later and rng.chance(0.85):
                end = rng.pick(later[:4])
                evs.append(('last_affected' if rng.chance(0.25) else 'fixed', end))
                more = [v for v in vs if end < v and v.major > end.major]
                if more and rng.chance(0.25):
                    evs.append(('introduced', more[0]))
                    lt = [v for v in vs if more[0] < v]
                    if lt and rng.chance(0.6):
                        evs.append(('fixed', lt[0]))
            aff.append({'pkg': p['key'], 'events': evs, 'replay': rng.chance(0.03)})
        W.vulns.append({'canon': canon, 'cve': cve, 'ghsa': ghsa, 'osv': osv, 'pub': pub, 'pub_unknown': pub_unknown, 'nvd_vec': nvd_vec, 'nvd_src': rng.pick(['NVD', 'CNA']) if cve else None, 'ghsa_vec': ghsa_vec, 'ghsa_reviewed': rng.chance(0.7), 'ghsa_pub': (nudge(min(CUT - 3600 * 6, pub + rng.rint(-3, 3) * DAY)) if pub < CUT else nudge(pub + rng.rint(0, 3) * DAY)) if ghsa else None, 'resc': resc, 'prec_vec': prec_vec, 'prec_pub': prec_pub, 'withdrawn': withdrawn, 'aff': aff, 'cache': bool(ghsa) and rng.chance(0.03)})
    W.vuln_by = {v['canon']: v for v in W.vulns}
    W.fx = {}
    base = {'USD': D('0.92'), 'GBP': D('1.17'), 'INR': D('0.0109'), 'JPY': D('0.0062')}
    step = 5400 if scale >= 0.9 else 3 * 3600
    for cur, b in base.items():
        seq_ = []
        t = Q_START - 21 * DAY
        x = b
        while t < CUT + 20 * DAY:
            x = q(x * (D(1) + D(rng.rint(-300, 300)) / D(1000000)), 6)
            at_ = nudge(t + rng.rint(0, 5) * 60)
            if not seq_ or at_ > seq_[-1][0]:
                seq_.append((at_, x))
            t += step
        W.fx[cur] = seq_
    return W

def team_at(owners, t):
    """Owner of a history [(effective, team)] at instant t: latest effective before t, else None."""
    best = None
    for eff, team in sorted(owners):
        if eff < t:
            best = team
    return best
POOL_SHARE = D('0.035')
SERVICE_SLOTS = 6
TOP_RISK_SHARE = D('0.02')

class Truth:
    pass

def yanked_at(rel, t):
    st = False
    for at, state in sorted(rel['yank']):
        if at < t:
            st = state
    return st

def _merged(alias):
    return alias['confirmed'] and alias['eff'] < CUT

def release_owner(p, r):
    if r['under'] is None:
        return p['key']
    for a in p['aliases']:
        if a['old'] == r['under']:
            return p['key'] if _merged(a) else f"{p['eco']}:{a['old']}"
    return p['key']

def active_at(s, t):
    st = 'active'
    for ev, at in s['life']:
        if at <= t and ev in ('decommissioned', 'restored'):
            st = 'decommissioned' if ev == 'decommissioned' else 'active'
    return st

def finish_world(W, rng):
    """Second-stage facts that depend on the first stage: typo packages, scanner pins, licences, factors."""
    W.typo_pkgs = []
    for p in W.packages:
        for nm in p['typos']:
            rels = []
            for k in range(rng.rint(1, 2)):
                vv = Ver(rng.rint(0, 3), rng.rint(0, 9), rng.rint(0, 9))
                if any((x['ver'] == vv for x in rels)):
                    continue
                rels.append({'ver': vv, 'pub': nudge(gen_time(rng, Q_START - 200 * DAY, CUT - DAY)), 'yank': [], 'sha': f'{rng.u64():016x}', 'quarantine': False, 'lic': 'NOASSERTION', 'under': None})
            W.typo_pkgs.append({'key': f"{p['eco']}:{nm}", 'eco': p['eco'], 'name': nm, 'rels': rels, 'target': p['key']})
    W.scanner = {}
    for s in W.services:
        if s['home'] != 'image':
            continue
        rows = []
        for p in rng.sample(W.packages, rng.rint(6, 14)):
            cand = [r for r in p['rels'] if r['pub'] < CUT and (not r['quarantine']) and (release_owner(p, r) == p['key'])]
            if not cand:
                continue
            r = rng.pick(cand)
            rows.append((p['key'], r['ver'], nudge(gen_time(rng, Q_START, CUT - DAY))))
        W.scanner[s['svc']] = rows
    W.factors = {}
    W.est_over = {}
    for p in W.packages:
        for mj in p['majors']:
            if rng.chance(0.75):
                W.factors[p['key'], mj] = (D(rng.pick(['0.5', '0.75', '1.125', '1.333', '1.667', '2.5', '3'])), rng.rint(Q_START_DAY - 300, CUT_DAY - 1))
            if rng.chance(0.18):
                W.est_over[p['key'], mj] = (q(D(rng.rint(2, 160)) / D(4), 2), rng.rint(Q_START_DAY - 300, CUT_DAY - 1))
    W.lic_over = []
    W.lic_exc = []
    for p in W.packages:
        if rng.chance(0.2):
            vs = sorted((r['ver'] for r in p['rels']))
            lo = rng.pick(vs)
            raw, cons = spell_cons(rng.pick(['caret', 'range', 'floor']) if p['eco'] != 'maven' else 'range', Ver(lo.major, lo.minor, lo.patch), p['eco'])
            W.lic_over.append({'pkg': p['key'], 'raw': raw, 'cons': cons, 'expr': rng.pick(['MIT', 'Apache-2.0', 'GPL-3.0-only', 'LGPL-2.1-only', 'BSD-2-Clause']), 'decided': nudge(gen_time(rng, Q_START - 200 * DAY, CUT + 10 * DAY)), 'approved': rng.chance(0.75), 'oid': None})
        if rng.chance(0.22):
            vs = sorted((r['ver'] for r in p['rels']))
            lo = rng.pick(vs)
            raw, cons = spell_cons('range', Ver(lo.major, lo.minor, lo.patch), p['eco'])
            g = rng.rint(Q_START_DAY - 300, CUT_DAY + 20)
            rv = None if rng.chance(0.7) else rng.rint(g + 1, CUT_DAY + 60)
            W.lic_exc.append({'pkg': p['key'], 'raw': raw, 'cons': cons, 'cls': rng.pick(['permissive', 'weak']), 'granted': g, 'revoked': rv})

def lic_expr(W, p, r):
    best = None
    for o in W.lic_over:
        if o['pkg'] == p['key'] and o['approved'] and (o['decided'] < CUT) and o['cons'].admits_any(r['ver']):
            if best is None or o['decided'] > best['decided']:
                best = o
    if best:
        return canon_spdx(best['expr'])
    return canon_spdx(r['lic']) if r['lic'] else 'NOASSERTION'

def lic_class(W, pkg_key, ver, expr):
    cls = spdx_class(parse_spdx(expr))
    best = None
    for e in W.lic_exc:
        if e['pkg'] == pkg_key and e['cons'].admits_any(ver) and (e['granted'] <= CUT_DAY - 1) and (e['revoked'] is None or e['revoked'] > CUT_DAY - 1):
            if best is None or e['granted'] > best['granted']:
                best = e
    return best['cls'] if best else cls

def vuln_vector(v):
    """(vector, source) selected under precedence.yaml defaults and per-vulnerability overrides."""
    ok = [r for r in v['resc'] if r['approved'] and r['at'] < CUT]
    if ok:
        return (max(ok, key=lambda r: r['at'])['vec'], 'rescore')
    order = ['nvd', 'ghsa'] if v['prec_vec'] in ('default', 'nvd') else ['ghsa', 'nvd']
    for src in order:
        if src == 'nvd' and v['nvd_vec']:
            return (v['nvd_vec'], 'nvd')
        if src == 'ghsa' and v['ghsa_vec']:
            return (v['ghsa_vec'], 'ghsa')
    return (None, None)

def vuln_vector_visible(v):
    """The vector the exports allow as of the cut (only sources recorded before the cut)."""
    ok = [r for r in v['resc'] if r['approved'] and r['at'] < CUT]
    if ok:
        return max(ok, key=lambda r: r['at'])['vec']
    order = ['nvd', 'ghsa'] if v['prec_vec'] in ('default', 'nvd') else ['ghsa', 'nvd']
    for src in order:
        if src == 'nvd' and v['nvd_vec'] and v.get('nvd_visible', True):
            return v['nvd_vec']
        if src == 'ghsa' and v['ghsa_vec'] and (v['ghsa_pub'] is not None) and (v['ghsa_pub'] < CUT):
            return v['ghsa_vec']
    return None

def vuln_published(v):
    """Publication instant from the authority source, None when that source records it as unknown."""
    order = ['osv', 'ghsa'] if v['prec_pub'] == 'default' else ['ghsa', 'osv']
    for src in order:
        if src == 'osv':
            return None if v['pub_unknown'] else v['pub']
        if src == 'ghsa' and v['ghsa']:
            return v['ghsa_pub']
    return None

def compute_truth(W, rng):
    T = Truth()
    pk = {}
    for p in W.packages:
        for r in p['rels']:
            k = release_owner(p, r)
            pk.setdefault(k, {'eco': p['eco'], 'rels': [], 'owner_pkg': p})['rels'].append(r)
    for tp in W.typo_pkgs:
        pk.setdefault(tp['key'], {'eco': tp['eco'], 'rels': [], 'owner_pkg': None})['rels'].extend(tp['rels'])
    T.pk = pk
    T.packages_rows_pre = []
    for key in sorted(pk):
        st = [r for r in pk[key]['rels'] if not r['quarantine'] and r['pub'] < CUT and (r['ver'].pre is None) and (not yanked_at(r, CUT))]
        T.packages_rows_pre.append({'package': key, 'latest': max(st, key=lambda r: r['ver'].key())['ver'] if st else None})

    def eligible(key, t):
        return [r for r in pk.get(key, {'rels': []})['rels'] if not r['quarantine'] and r['pub'] < t]
    T.eligible = eligible
    T.pins = []
    T.svc_status = {s['svc']: active_at(s, CUT) for s in W.services}
    W.ovr_by = {(o['svc'], o['pkg']): o for o in W.overrides}
    for s in sorted(W.services, key=lambda x: x['svc']):
        if T.svc_status[s['svc']] != 'active':
            continue
        if s['home'] == 'image':
            for key, ver, seen in sorted(W.scanner.get(s['svc'], [])):
                T.pins.append({'service': s['svc'], 'package': key, 'scope': 'runtime', 'constraint': None, 'source': 'scanner_findings.jsonl', 'pinned': ver, 'disposition': 'observed'})
            continue
        src = 'manifests_snapshot.csv' if s['archived'] else MANIFEST_FILE[s['home']]
        for d in s['deps']:
            if d['locked'] >= CUT or (d['removed'] is not None and d['removed'] < CUT):
                continue
            o = W.ovr_by.get((s['svc'], d['pkg']))
            if o and o['approved'] and (o['decided'] < CUT) and (o['from'] <= CUT_DAY - 1 < o['to']) and any((r['ver'] == o['ver'] for r in eligible(d['pkg'], CUT))):
                pinned, disp = (o['ver'], 'overridden')
            else:
                rels = [(r['ver'], r['pub'], (lambda rr: lambda t: yanked_at(rr, t))(r)) for r in eligible(d['pkg'], CUT)]
                pinned = resolve_pin(d['cons'], rels, d['locked'])
                disp = 'pinned' if pinned is not None else 'unsatisfiable'
            T.pins.append({'service': s['svc'], 'package': d['pkg'], 'scope': d['scope'], 'constraint': d['cons'].canon(), 'source': src, 'pinned': pinned, 'disposition': disp})
    T.pins.sort(key=lambda r: (r['service'], r['package'], r['scope']))
    for row in T.pins:
        if row['pinned'] is not None and row['scope'] == 'runtime':
            rel = next((r for r in pk[row['package']]['rels'] if r['ver'] == row['pinned']))
            p = pk[row['package']]['owner_pkg'] or {'key': row['package']}
            expr = lic_expr(W, W.pkg_by.get(row['package'], {'key': row['package']}), rel) if row['package'] in W.pkg_by else canon_spdx(rel['lic'])
            row['license'] = expr
            row['obligation'] = lic_class(W, row['package'], row['pinned'], expr)
        else:
            row['license'] = None
            row['obligation'] = None
    return T

def finish_dispositions(W, T, rng):
    """VEX statements, waivers, timesheets and journal entries placed against the resolved exposures."""
    W.vex, W.waivers, W.timesheets, W.journal = ([], [], [], [])
    exp = base_exposures(W, T)
    T.base_exp = exp
    for e in exp:
        x = rng.below(100)
        if x < 14:
            W.vex.append({'svc': e['service'], 'vuln': e['vuln'], 'status': 'not_affected', 'just': rng.pick(['vulnerable_code_not_present', 'vulnerable_code_not_in_execute_path', 'inline_mitigations_already_exist', 'component_not_present']), 'issued': nudge(gen_time(rng, Q_START - 30 * DAY, CUT + 10 * DAY))})
        elif x < 24:
            W.vex.append({'svc': e['service'], 'vuln': e['vuln'], 'status': rng.pick(['under_investigation', 'fixed', 'affected']), 'just': '', 'issued': nudge(gen_time(rng, Q_START - 30 * DAY, CUT - DAY))})
        y = rng.below(100)
        if y < 17:
            g = nudge(gen_time(rng, Q_START - 90 * DAY, CUT + 5 * DAY))
            W.waivers.append({'svc': e['service'], 'vuln': e['vuln'], 'granted': g, 'expires': nudge(gen_time(rng, g + DAY, CUT + 90 * DAY)), 'approved': rng.chance(0.7), 'decided': nudge(gen_time(rng, g - 5 * DAY, CUT + 5 * DAY)), 'wid': None})
    svcs = [s['svc'] for s in W.services]
    vids = [v['canon'] for v in W.vulns]
    for _ in range(len(exp) // 4):
        W.vex.append({'svc': rng.pick(svcs), 'vuln': rng.pick(vids), 'status': rng.pick(['not_affected', 'fixed', 'under_investigation']), 'just': 'component_not_present', 'issued': nudge(gen_time(rng, Q_START - 60 * DAY, CUT - DAY))})
    for _ in range(len(exp) // 4):
        g = nudge(gen_time(rng, Q_START - 90 * DAY, CUT - DAY))
        W.waivers.append({'svc': rng.pick(svcs), 'vuln': rng.pick(vids), 'granted': g, 'expires': nudge(gen_time(rng, g + DAY, CUT + 90 * DAY)), 'approved': rng.chance(0.6), 'decided': nudge(gen_time(rng, g - 5 * DAY, CUT - DAY)), 'wid': None})
    by_team = {}
    for e in W.engineers:
        for sg in e['segs']:
            by_team.setdefault(sg['team'], []).append(e)
    n_ts = max(300, round(8600 * W.scale))
    for i in range(n_ts):
        e = rng.pick(exp) if exp else None
        if e is None:
            break
        team = team_at(W.svc_by[e['service']]['owners'], CUT)
        engs = by_team.get(team) or W.engineers
        eng = rng.pick(engs)
        lo_d, hi_d = (Q_START_DAY, CUT_DAY + 15)
        segs = [sg for sg in eng['segs'] if sg['start'] < hi_d and (sg['end'] is None or sg['end'] > lo_d)]
        if not segs:
            continue
        sg = rng.pick(segs)
        a = max(lo_d, sg['start'])
        b = min(hi_d, sg['end'] if sg['end'] is not None else hi_d)
        worked = nudge(epoch(*civil_from_days(rng.rint(a, b - 1))) + rng.rint(8, 18) * 3600)
        if worked // DAY >= b:
            worked -= 6 * 3600
        if CUT - 3 * 3600 <= worked < CUT:
            worked -= 6 * 3600
        W.timesheets.append({'tid': f'ts-{i * 3 + 7:06d}', 'eng': eng['eng'], 'svc': e['service'], 'vuln': e['vuln'], 'hours': D(rng.rint(1, 40)) / D(4), 'worked': worked})
    n_j = max(300, round(7600 * W.scale))
    spend = {}
    for ts in W.timesheets:
        e = W.eng_by[ts['eng']]
        cur, minor = e['rates'][9]
        rate = {'EUR': D(1), 'USD': D('0.92'), 'GBP': D('1.17'), 'INR': D('0.0109'), 'JPY': D('0.0062')}[cur]
        spend[e['segs'][0]['team']] = spend.get(e['segs'][0]['team'], 0) + int(ts['hours'] * D(minor) / D(10) ** CUR_EXP[cur] * rate * 100)
    for t in W.teams:
        base = spend.get(t['team'], 0) or 5000000
        W.journal.append({'jid': None, 'team': t['team'], 'kind': 'opening', 'cur': 'EUR', 'minor': int(base * rng.rint(55, 115) / 100), 'booked': Q_START, 'reverses': None})
    for i in range(n_j - len(W.teams)):
        team = rng.pick(W.team_ids)
        cur = rng.wpick(CURRENCIES, [50, 20, 10, 10, 10])
        mag = rng.rint(500, 500000) * (1 if cur == 'JPY' else 1)
        sign = -1 if rng.chance(0.7) else 1
        booked = nudge(gen_time(rng, Q_START, CUT + 15 * DAY))
        W.journal.append({'jid': None, 'team': team, 'kind': 'adjust', 'cur': cur, 'minor': sign * mag, 'booked': booked, 'reverses': None})
    adj = [j for j in W.journal if j['kind'] == 'adjust' and j['booked'] < CUT]
    for j in rng.sample(adj, len(adj) // 25):
        W.journal.append({'jid': None, 'team': j['team'], 'kind': 'reversal', 'cur': j['cur'], 'minor': -j['minor'], 'booked': nudge(gen_time(rng, j['booked'] + 3600, CUT - 60)), 'reverses': j})
    for k, j in enumerate(W.journal):
        j['jid'] = f'jr-{k * 5 + 3:06d}'

def seg_covers(sg, z):
    return sg['start'] <= z and (sg['end'] is None or z < sg['end'])

def base_exposures(W, T):
    """(service, package, vuln) triples affected at the cut, before dispositions."""
    pins_by = {}
    for row in T.pins:
        if row['scope'] == 'runtime' and row['pinned'] is not None:
            pins_by.setdefault(row['package'], []).append(row)
    out = []
    ident = identity_map(W)
    for v in W.vulns:
        if v['withdrawn'] is not None and v['withdrawn'] < CUT:
            continue
        pub = vuln_published(v)
        if pub is not None and pub >= CUT:
            continue
        for a in v['aff']:
            key = ident.get(a['pkg'], a['pkg'])
            rng_ = parse_events(a['events'])
            for row in pins_by.get(key, []):
                if affected(rng_, row['pinned']):
                    out.append({'service': row['service'], 'package': key, 'version': row['pinned'], 'vuln': v['canon'], 'aff': a})
    seen = set()
    uniq = []
    for e in sorted(out, key=lambda e: (e['service'], e['package'], e['vuln'])):
        k = (e['service'], e['package'], e['vuln'])
        if k not in seen:
            seen.add(k)
            uniq.append(e)
    return uniq

def identity_map(W):
    m = {}
    for p in W.packages:
        m[p['key']] = p['key']
        for a in p['aliases']:
            m[f"{p['eco']}:{a['old']}"] = p['key'] if _merged(a) else f"{p['eco']}:{a['old']}"
    return m

def vex_status(W, svc, vuln):
    best = None
    for x in W.vex:
        if x['svc'] == svc and x['vuln'] == vuln and (x['issued'] < CUT):
            if best is None or x['issued'] > best['issued']:
                best = x
    return best

def waiver_ok(W, svc, vuln):
    for w in W.waivers:
        if w['svc'] == svc and w['vuln'] == vuln and w['approved'] and (w['decided'] < CUT) and (w['granted'] < CUT <= w['expires']):
            return True
    return False

def complete_truth(W, T):
    """The six phase-1 tables, in their written order and at their written precision."""
    ident = identity_map(W)
    T.ident = ident
    vex_idx = {}
    for x in W.vex:
        if x['issued'] < CUT:
            k = (x['svc'], x['vuln'])
            if k not in vex_idx or x['issued'] > vex_idx[k]['issued']:
                vex_idx[k] = x
    wv_idx = set()
    for w in W.waivers:
        if w['approved'] and w['decided'] < CUT and (w['granted'] < CUT <= w['expires']):
            wv_idx.add((w['svc'], w['vuln']))
    weights = {}
    T.services_rows = []
    for s in sorted(W.services, key=lambda x: x['svc']):
        st = T.svc_status[s['svc']]
        deploys = None
        if s['covered']:
            seen = 0
            for dp in s['deploys']:
                if dp['outcome'] == 'succeeded' and Q_START <= dp['t'] < CUT:
                    seen += 1
            deploys = seen
        factor = min(D(2), D(1) + D(deploys) / D(365)) if deploys is not None else D(1)
        w = q(TIER_WEIGHT[s['tier']] * factor, 4)
        weights[s['svc']] = w
        T.services_rows.append({'service': s['svc'], 'team': team_at(s['owners'], CUT), 'tier': s['tier'], 'region': s['region'], 'status': st, 'deploys': deploys, 'weight': w})
    T.weights = weights
    T.exposures = []
    for e in T.base_exp:
        v = W.vuln_by[e['vuln']]
        s = W.svc_by[e['service']]
        vec, src = vuln_vector(v)
        score = cvss_base(vec)
        sev = severity_of(score)
        vx = vex_idx.get((e['service'], e['vuln']))
        if vx and vx['status'] == 'not_affected':
            status = 'not_affected'
        elif (e['service'], e['vuln']) in wv_idx:
            status = 'waived'
        else:
            status = 'open'
        pub = vuln_published(v)
        zone = REGION_ZONE[s['region']]
        if pub is None:
            pub_day, days = (None, None)
        else:
            pub_day = wall_of(pub, zone) // DAY
            skip = set()
            for a, b in s['freeze']:
                skip.update(range(a, b))
            days = business_days(pub_day + 1, CUT_DAY, skip | HOLIDAYS.get(s['region'], set()))
        sla = SLA_MATRIX[sev][s['tier']]
        ov = s['sla'].get(sev)
        if ov and ov[1] <= CUT_DAY - 1:
            sla = ov[0]
        breach = days is not None and days > sla
        cands = sorted((r['ver'] for r in T.eligible(e['package'], CUT) if not yanked_at(r, CUT) and e['version'] < r['ver']))
        rng_ = parse_events(e['aff']['events'])
        fixed = next((c for c in cands if not affected(rng_, c)), None)
        mj = e['version'].major
        over = W.est_over.get((e['package'], mj))
        if over and over[1] <= CUT_DAY - 1:
            est = over[0]
        else:
            fac = W.factors.get((e['package'], mj))
            fac = fac[0] if fac and fac[1] <= CUT_DAY - 1 else D(1)
            mult = D(3) if fixed is None else D(2) if fixed.major > mj else D(1)
            est = q(BASE_HOURS[sev] * fac * mult, 2)
        deferred = []
        for r in v['resc']:
            if r['approved'] and r['at'] >= CUT:
                deferred.append(f"rescore:{cvss_base(r['vec'])}")
        T.exposures.append({'service': e['service'], 'package': e['package'], 'version': e['version'], 'vuln': e['vuln'], 'cvss': score, 'severity': sev, 'status': status, 'published': pub_day, 'days_open': days, 'sla_days': sla, 'breach': breach, 'estimate': est, 'fixed': fixed, 'deferred': deferred})
    return T
HOLIDAYS = {}

def build_holidays():
    out = {}
    base = [(2025, 7, 4, 'us-central'), (2025, 9, 1, 'us-central'), (2025, 8, 4, 'eu-west'), (2025, 8, 15, 'ap-south'), (2025, 9, 17, 'ap-south'), (2025, 7, 21, 'ap-north'), (2025, 8, 11, 'ap-north'), (2025, 9, 15, 'ap-north'), (2025, 9, 23, 'ap-north'), (2025, 7, 14, 'global'), (2025, 8, 25, 'global')]
    for y, m, d, reg in base:
        out.setdefault(reg, set()).add(days_from_civil(y, m, d))
    out.setdefault('ap-southeast', set())
    return out
HOLIDAYS.update(build_holidays())
CANON_SLA = {k: list(v) for k, v in SLA_MATRIX.items()}
CANON_BASE_HOURS = dict(BASE_HOURS)
CANON_HOLIDAYS = {k: set(v) for k, v in HOLIDAYS.items()}

def use_policy(seed):
    """Install the policy figures that a corpus's sla_policy.pdf and scoring_methodology.pdf state.

    The shipped corpus states the canonical figures; every other corpus (seed not None) states its own seeded targets, base hours
    and holidays, so a program that hard-codes the shipped figures instead of reading the documents gets that corpus wrong."""
    SLA_MATRIX.clear()
    BASE_HOURS.clear()
    HOLIDAYS.clear()
    if seed is None:
        SLA_MATRIX.update({k: list(v) for k, v in CANON_SLA.items()})
        BASE_HOURS.update(CANON_BASE_HOURS)
        HOLIDAYS.update({k: set(v) for k, v in CANON_HOLIDAYS.items()})
        return
    rng = Rng(derive(seed, 'policy'))
    for sev, row in CANON_SLA.items():
        SLA_MATRIX[sev] = [max(3, d + rng.pick([-4, -3, -2, 2, 3, 5])) for d in row]
    for sev, h in CANON_BASE_HOURS.items():
        BASE_HOURS[sev] = h + rng.pick([D('0.5'), D('1'), D('1.5'), D('2'), D('3')])
    days = [z for z in range(Q_START_DAY, CUT_DAY) if weekday_of_day(z) < 5]
    for reg in REGIONS:
        HOLIDAYS[reg] = set(rng.sample(days, rng.rint(1, 4)))
ENV = [('rid', 'id'), ('rev', 'int'), ('st', 'enum:st'), ('rec_at', 'ts')]
VOCAB = {'st': {'word': ['active', 'void', 'draft'], 'letter': ['A', 'V', 'D'], 'code': ['1', '9', '0']}, 'scope': {'word': ['runtime', 'dev', 'test'], 'letter': ['R', 'D', 'T'], 'alt': ['prod', 'development', 'testing']}, 'eco': {'word': ['pypi', 'npm', 'maven', 'cargo'], 'upper': ['PYPI', 'NPM', 'MAVEN', 'CARGO'], 'alt': ['pip', 'node', 'mvn', 'crates']}, 'alias_kind': {'word': ['rename', 'spelling', 'typo', 'vendor'], 'letter': ['R', 'S', 'T', 'V']}, 'notice': {'word': ['yank', 'unyank', 'rename'], 'upper': ['YANK', 'UNYANK', 'RENAME']}, 'role': {'word': ['owner', 'maintainer', 'reviewer'], 'letter': ['O', 'M', 'R']}, 'home': {'word': ['core', 'edge', 'data', 'legacy', 'image'], 'upper': ['CORE', 'EDGE', 'DATA', 'LEGACY', 'IMAGE']}, 'region': {'word': REGIONS, 'alt': ['euw1', 'usc1', 'aps1', 'apn1', 'apse1', 'glb']}, 'life': {'word': ['archived', 'decommissioned', 'restored', 'paused', 'renamed'], 'letter': ['A', 'X', 'R', 'P', 'N']}, 'outcome': {'word': ['succeeded', 'failed', 'rolled_back'], 'letter': ['S', 'F', 'R'], 'alt': ['ok', 'error', 'rollback']}, 'nvdsrc': {'word': ['NVD', 'CNA']}, 'pfield': {'word': ['cvss_vector', 'published']}, 'vex': {'word': ['not_affected', 'affected', 'fixed', 'under_investigation'], 'alt': ['NA', 'A', 'F', 'UI']}, 'just': {'word': ['vulnerable_code_not_present', 'vulnerable_code_not_in_execute_path', 'inline_mitigations_already_exist', 'component_not_present', 'none']}, 'cls': {'word': ['permissive', 'weak', 'strong', 'network', 'unknown']}, 'model': {'word': ['capped', 'uncapped']}, 'cur': {'word': CURRENCIES}, 'jkind': {'word': ['opening', 'adjust', 'reversal'], 'letter': ['O', 'A', 'R']}, 'measure': {'word': ['open_exposures', 'runtime_pins', 'closing_cents', 'capacity_hours', 'records', 'in_force', 'pool_hours', 'total_open', 'waived_total']}, 'err': {'word': ['void', 'correct'], 'upper': ['VOID', 'CORRECT']}, 'dec': {'word': ['approve', 'reject', 'defer'], 'letter': ['Y', 'N', 'D']}, 'sev': {'word': ['critical', 'high', 'medium', 'low']}, 'lstat': {'word': ['decided', 'proposed', 'withdrawn'], 'letter': ['D', 'P', 'W']}}
REL = [('name', 'pkg'), ('version', 'ver'), ('published', 'ts'), ('yanked', 'bool')]
DECL = [('service', 'svcid'), ('eco', 'enum:eco'), ('name', 'pkg'), ('constraint', 'cons'), ('scope', 'enum:scope'), ('locked', 'ts')]
FILES = {'registry_pypi.jsonl': ('jsonl', 'data', [('releases', REL)], {'eco': 'pypi'}), 'registry_npm.csv': ('csv', 'data', [('releases', REL)], {'eco': 'npm'}), 'registry_maven.xml': ('xml', 'data', [('releases', REL)], {'eco': 'maven'}), 'registry_cargo.tsv': ('tsv', 'data', [('releases', REL)], {'eco': 'cargo'}), 'registry_mirror.parquet': ('parquet', 'decoy', [('mirror', [('eco', 'enum:eco'), ('name', 'pkg'), ('version', 'ver'), ('published', 'ts'), ('yanked', 'bool'), ('quarantined', 'bool'), ('license', 'spdx')])], {'counterpart': 'registry_npm.csv'}), 'name_aliases.tsv': ('tsv', 'data', [('aliases', [('eco', 'enum:eco'), ('alias', 'pkg'), ('target', 'pkg'), ('kind', 'enum:alias_kind'), ('effective', 'ts')])], {}), 'name_aliases_legacy.tsv': ('tsv', 'decoy', [('aliases', [('eco', 'enum:eco'), ('alias', 'pkg'), ('target', 'pkg'), ('kind', 'enum:alias_kind'), ('effective', 'ts'), ('note', 'text')])], {'counterpart': 'name_aliases.tsv'}), 'yank_notices.mbox': ('mbox', 'data', [('notices', [('action', 'enum:notice'), ('eco', 'enum:eco'), ('name', 'pkg'), ('version', 'ver'), ('ref', 'id')])], {}), 'package_owners.json': ('json', 'data', [('owners', [('eco', 'enum:eco'), ('name', 'pkg'), ('team', 'id'), ('role', 'enum:role'), ('effective', 'ts')])], {}), 'manifests_core.csv': ('csv', 'data', [('declarations', DECL)], {}), 'manifests_edge.jsonl': ('jsonl', 'data', [('declarations', DECL)], {}), 'manifests_data.yaml': ('yaml', 'data', [('declarations', DECL)], {}), 'manifests_legacy.txt': ('txt', 'data', [('declarations', DECL)], {'encoding': 'latin-1'}), 'manifests_snapshot.csv': ('csv', 'decoy', [('declarations', DECL)], {'counterpart': 'manifests_core.csv'}), 'lock_overrides.toml': ('toml', 'data', [('overrides', [('service', 'svcid'), ('eco', 'enum:eco'), ('name', 'pkg'), ('version', 'ver'), ('valid_from', 'date'), ('valid_to', 'date')])], {}), 'scanner_findings.jsonl': ('jsonl', 'decoy', [('findings', [('service', 'svcid'), ('eco', 'enum:eco'), ('name', 'pkg'), ('version', 'ver'), ('seen', 'ts'), ('image', 'text')])], {'counterpart': 'manifests_edge.jsonl'}), 'service_catalog.xlsx': ('xlsx', 'data', [('services', [('service', 'svcid'), ('name', 'text'), ('tier', 'int'), ('region', 'enum:region'), ('manifest', 'enum:home')]), ('ownership', [('service', 'svcid'), ('team', 'id'), ('effective', 'ts')]), ('lifecycle', [('service', 'svcid'), ('event', 'enum:life'), ('at', 'ts')])], {}), 'service_catalog_final.xlsx': ('xlsx', 'decoy', [('services', [('service', 'svcid'), ('name', 'text'), ('tier', 'int'), ('region', 'enum:region'), ('manifest', 'enum:home')]), ('ownership', [('service', 'svcid'), ('team', 'id'), ('effective', 'ts')]), ('legacy_lifecycle', [('service', 'svcid'), ('event', 'enum:life'), ('at', 'ts')])], {'counterpart': 'service_catalog.xlsx'}), 'deploy_events_east.log': ('log', 'data', [('deploys', [('host', 'id'), ('service', 'svcid'), ('outcome', 'enum:outcome'), ('at', 'ts')])], {}), 'deploy_events_west.log': ('log', 'data', [('deploys', [('host', 'id'), ('service', 'svcid'), ('outcome', 'enum:outcome'), ('at', 'ts')])], {}), 'deploy_events_central.log': ('log', 'data', [('deploys', [('host', 'id'), ('service', 'svcid'), ('outcome', 'enum:outcome'), ('at', 'ts')])], {}), 'deploy_events_legacy.log': ('log', 'decoy', [('deploys', [('host', 'id'), ('service', 'svcid'), ('outcome', 'enum:outcome'), ('at', 'ts')])], {'counterpart': 'deploy_events_central.log'}), 'clock_offsets.txt': ('txt', 'data', [('offsets', [('host', 'id'), ('day', 'date'), ('offset', 'int')])], {}), 'change_freeze.ics': ('ics', 'data', [('windows', [('service', 'svcid'), ('start', 'date'), ('end', 'date')])], {}), 'advisories_osv.jsonl': ('jsonl', 'data', [('osv', [('osv', 'vid'), ('eco', 'enum:eco'), ('name', 'pkg'), ('events', 'events'), ('published', 'ts'), ('withdrawn', 'ts')])], {}), 'advisories_osv_replay.jsonl': ('jsonl', 'decoy', [('osv', [('osv', 'vid'), ('eco', 'enum:eco'), ('name', 'pkg'), ('events', 'events'), ('published', 'ts'), ('withdrawn', 'ts')])], {'counterpart': 'advisories_osv.jsonl'}), 'advisories_ghsa.json': ('json', 'data', [('ghsa', [('ghsa', 'vid'), ('eco', 'enum:eco'), ('name', 'pkg'), ('vector', 'vec'), ('reviewed', 'bool'), ('published', 'ts')])], {}), 'advisories_feed_cache.json': ('json', 'decoy', [('cache', [('ghsa', 'vid'), ('eco', 'enum:eco'), ('name', 'pkg'), ('vector', 'vec'), ('score', 'dec'), ('fetched', 'ts')])], {'counterpart': 'advisories_ghsa.json'}), 'advisories_nvd.xml': ('xml', 'data', [('nvd', [('cve', 'vid'), ('vector', 'vec'), ('source', 'enum:nvdsrc'), ('modified', 'ts')])], {}), 'advisory_aliases.csv': ('csv', 'data', [('aliases', [('a', 'vid'), ('b', 'vid')])], {}), 'advisory_rescores.parquet': ('parquet', 'data', [('rescores', [('vuln', 'vid'), ('vector', 'vec'), ('approved', 'bool'), ('scored', 'ts')])], {}), 'precedence.yaml': ('yaml', 'data', [('authority', [('vuln', 'vid'), ('field', 'enum:pfield'), ('order', 'text')])], {}), 'vex_statements.xml': ('xml', 'data', [('vex', [('service', 'svcid'), ('vuln', 'vid'), ('status', 'enum:vex'), ('justification', 'enum:just'), ('issued', 'ts')])], {}), 'waivers.db': ('db', 'data', [('waivers', [('service', 'svcid'), ('vuln', 'vid'), ('granted', 'ts'), ('expires', 'ts'), ('approver', 'text')])], {}), 'license_scan.parquet': ('parquet', 'data', [('scans', [('eco', 'enum:eco'), ('name', 'pkg'), ('version', 'ver'), ('expression', 'spdx'), ('scanned', 'ts')])], {}), 'license_overrides.csv': ('csv', 'data', [('overrides', [('eco', 'enum:eco'), ('name', 'pkg'), ('range', 'cons'), ('expression', 'spdx'), ('status', 'enum:lstat'), ('decided', 'ts')])], {}), 'license_policy.md': ('md', 'doc', [('exceptions', [('eco', 'enum:eco'), ('name', 'pkg'), ('range', 'cons'), ('class', 'enum:cls'), ('granted', 'date'), ('revoked', 'date')])], {}), 'engineer_roster.ini': ('ini', 'data', [('alloc', [('engineer', 'id'), ('team', 'id'), ('fte', 'dec'), ('oncall', 'dec'), ('start', 'date'), ('end', 'date')]), ('teams', [('team', 'id'), ('model', 'enum:model')])], {}), 'engineer_rates.xlsx': ('xlsx', 'data', [(f'rates_{m}', [('engineer', 'id'), ('month', 'date'), ('rate', 'money'), ('currency', 'enum:cur')]) for m in ('jul', 'aug', 'sep')], {}), 'fx_fixings.tsv': ('tsv', 'data', [('fixings', [('currency', 'enum:cur'), ('at', 'ts'), ('rate', 'dec')])], {}), 'remediation_timesheets.csv': ('csv', 'data', [('timesheets', [('engineer', 'id'), ('service', 'svcid'), ('vuln', 'vid'), ('hours', 'hours'), ('worked', 'ts'), ('note', 'text')])], {}), 'ledger_journal.db': ('db', 'data', [('entries', [('team', 'id'), ('kind', 'enum:jkind'), ('amount', 'money'), ('currency', 'enum:cur'), ('booked', 'ts'), ('reverses', 'id')])], {}), 'close_contract.md': ('md', 'doc', [('crosswalk', [('legacy', 'text'), ('service', 'id'), ('valid_from', 'date'), ('valid_to', 'date')])], {}), 'source_conventions.html': ('html', 'doc', [('register', [('file', 'text'), ('batch', 'text'), ('field', 'text'), ('conv', 'text'), ('token', 'text')])], {}), 'control_totals.html': ('html', 'doc', [('controls', [('control', 'id'), ('scope', 'text'), ('measure', 'enum:measure'), ('value', 'int'), ('signed', 'ts')])], {}), 'errata_register.docx': ('docx', 'doc', [('errata', [('file', 'text'), ('target', 'id'), ('action', 'enum:err'), ('field', 'text'), ('value', 'text'), ('issued', 'ts')])], {}), 'review_minutes.docx': ('docx', 'doc', [('minutes', [('subject', 'id'), ('decision', 'enum:dec'), ('decided', 'ts'), ('chair', 'text')])], {}), 'scoring_methodology.pdf': ('pdf', 'doc', [('factors', [('eco', 'enum:eco'), ('name', 'pkg'), ('major', 'int'), ('factor', 'dec'), ('effective', 'date')])], {}), 'sla_policy.pdf': ('pdf', 'doc', [('sla_overrides', [('service', 'svcid'), ('severity', 'enum:sev'), ('days', 'int'), ('effective', 'date')])], {}), 'remediation_estimates.xlsx': ('xlsx', 'data', [(f'est_{e}', [('name', 'pkg'), ('major', 'int'), ('hours', 'hours'), ('effective', 'date')]) for e in ECOS], {})}
FILE_NAMES = sorted(FILES)
assert len(FILE_NAMES) == 50
DECOYS = sorted((f for f in FILES if FILES[f][1] == 'decoy'))
CANON_FILES = {'source_conventions.html', 'close_contract.md'}
NO_LAYOUT = {'xlsx', 'parquet', 'db', 'ini', 'ics', 'mbox', 'toml', 'html', 'docx', 'pdf', 'md'}

def fields_of(fname, table):
    for t, fs in FILES[fname][2]:
        if t == table:
            return ENV + fs
    raise KeyError((fname, table))

def kind_of(fname, table, field):
    return dict(fields_of(fname, table))[field]
OPTS = {'ts': ['iso', 'off:IE', 'off:US', 'off:IN', 'off:JP', 'off:AU', 'naive:UTC', 'naive:IE', 'naive:US', 'naive:IN', 'naive:JP', 'naive:AU', 'epoch', 'epochms', 'xl:UTC', 'xl:IE', 'xl:US', 'xl4:UTC', 'dmy:IE', 'dmy:IN', 'mdy:US'], 'date': ['iso', 'dmy', 'mdy', 'compact', 'xl'], 'dec': ['plain', 'de', 'fr'], 'int': ['plain', 'grouped', 'de'], 'hours': ['h', 'min', 'hm', 'iso'], 'money': ['minor', 'major', 'de', 'paren'], 'bool': ['tf', '10', 'yn', 'YN', 'neg'], 'id': ['canon', 'upper', 'spaced', 'under'], 'svcid': ['canon', 'upper', 'nopad', 'spaced', 'legacy'], 'pkg': ['canon', 'case', 'sep', 'fullwidth', 'zw'], 'ver': ['semver', 'native', 'vprefix', 'build'], 'vid': ['canon', 'lower', 'nopad', 'spaced'], 'vec': ['canon', 'noprefix', 'lower'], 'spdx': ['canon', 'lower', 'deprecated', 'alias'], 'events': ['semver', 'native']}
FACE = {'ts': 'iso', 'date': 'iso', 'dec': 'plain', 'int': 'plain', 'hours': 'h', 'money': 'minor', 'bool': 'tf', 'id': 'canon', 'svcid': 'canon', 'pkg': 'canon', 'ver': 'semver', 'vid': 'canon', 'vec': 'canon', 'spdx': 'canon', 'events': 'semver'}
ENUM_FACE = 'word'

def group_of(kind):
    return 'enum' if kind.startswith('enum:') else kind

def conv_options(fmt, kind, fname=None):
    g = group_of(kind)
    if g == 'enum':
        return sorted(VOCAB[kind[5:]])
    if g in ('text', 'cons'):
        return []
    opts = OPTS[g]
    if fmt == 'ics' and g == 'date':
        return ['iso']
    if fmt in ('txt',) and g in ('svcid', 'id'):
        opts = [o for o in opts if o != 'spaced']
    if g == 'pkg' and fname and (FILES[fname][3].get('eco') == 'maven'):
        opts = ['canon', 'fullwidth', 'zw']
    if g == 'pkg' and fname and (FILES[fname][3].get('encoding') == 'latin-1' or fmt == 'pdf'):
        opts = [o for o in opts if o not in ('fullwidth', 'zw')]
    return opts
STORY_MIX = {'plain': 56, 'superseded': 14, 'draft': 11, 'postcut': 9, 'void_postcut': 3}

class Ids:

    def __init__(self, rng):
        self.rng = rng
        self.n = {}

    def __call__(self, prefix):
        k = self.n.get(prefix, 0) + 1 + self.rng.below(3)
        self.n[prefix] = k
        return f'{prefix}-{k:06d}'

def rec(rid, revs, tags=(), fact=None):
    """revs: list of (st, rec_at, payload); revision numbers are assigned in order."""
    out = []
    for i, (st, at, p) in enumerate(revs, start=1):
        out.append({'rev': i, 'st': st, 'rec_at': at, 'p': dict(p)})
    return {'rid': rid, 'revs': out, 'tags': set(tags), 'fact': fact}

def mutate(rng, kind, v):
    """A plausible wrong value of the same kind (used by superseded, draft, postcut revisions and errata)."""
    if v is None or isinstance(v, Sentinel):
        return v
    g = group_of(kind)
    if g == 'ts':
        return nudge(v + rng.pick([-1, 1]) * rng.rint(1, 30) * DAY + rng.rint(0, 23) * 3600)
    if g == 'date':
        return v + rng.pick([-1, 1]) * rng.rint(1, 30)
    if g == 'int':
        if 0 <= v <= 3:
            return rng.pick([x for x in (0, 1, 2, 3) if x != v])
        return v + rng.pick([-1, 1]) * rng.rint(1, 9)
    if g in ('dec', 'hours'):
        return q(D(v) + rng.pick([D('-0.25'), D('0.25'), D('0.5'), D('1')]), 2) if D(v) > 1 else q(D(v) + D('0.25'), 2)
    if g == 'money':
        return v + rng.pick([-1, 1]) * rng.rint(100, 99999)
    if g == 'bool':
        return not v
    if g == 'enum':
        words = VOCAB[kind[5:]]['word']
        return rng.pick([w for w in words if w != v] or words)
    if g == 'ver':
        return Ver(v.major, v.minor, v.patch + rng.rint(1, 3)) if v.pre is None else Ver(v.major, v.minor, v.patch)
    if g == 'vec':
        head, m = cvss_parts(v)
        k = rng.pick(['AV', 'AC', 'PR', 'UI', 'C', 'I', 'A'])
        alt = {'AV': ['N', 'A', 'L', 'P'], 'AC': ['L', 'H'], 'PR': ['N', 'L', 'H'], 'UI': ['N', 'R']}.get(k, ['H', 'L', 'N'])
        m[k] = rng.pick([x for x in alt if x != m[k]])
        if m['C'] == m['I'] == m['A'] == 'N':
            m['C'] = 'L'
        return head + '/' + '/'.join((f'{x}:{m[x]}' for x in METRICS))
    if g == 'text':
        if isinstance(v, str) and (v in sum(OPTS.values(), []) or v.startswith('@')):
            return rng.pick([o for o in sum(OPTS.values(), []) if o != v])
        return v + ' (rev)' if isinstance(v, str) else v
    if g == 'spdx':
        return rng.pick(['MIT', 'GPL-3.0-only', 'Apache-2.0', 'LGPL-2.1-only'])
    return v
MUTABLE = {'ts', 'date', 'int', 'dec', 'hours', 'money', 'bool', 'enum', 'ver', 'vec', 'text', 'spdx'}

def payload_fields(fname, table):
    return [(n, k) for n, k in fields_of(fname, table)[4:]]

def mutable_fields(fname, table, exclude=()):
    return [(n, k) for n, k in payload_fields(fname, table) if group_of(k) in MUTABLE and n not in exclude]

def wrap(rng, fname, table, p, at, story=None, exclude=(), late=None, wrong_fn=None):
    """Revisions for one true payload recorded at `at` (< CUT): the in-force revision always carries p."""
    story = story or rng.wpick(list(STORY_MIX), list(STORY_MIX.values()))
    mf = [x for x in mutable_fields(fname, table, exclude) if x[1] != 'enum:eco']
    if any((k != 'text' for _, k in mf)):
        mf = [x for x in mf if x[1] != 'text']
    if not mf and wrong_fn is None or at >= CUT:
        story = 'plain'

    def wrong():
        if wrong_fn is not None:
            return wrong_fn(dict(p))
        x = dict(p)
        n, k = rng.pick(mf)
        x[n] = mutate(rng, k, x[n])
        return x
    late = late or nudge(gen_time(rng, CUT, LATE_END - DAY))
    if story == 'plain':
        return ([('A', at, p)], {'plain'})
    if story == 'superseded':
        early = nudge(max(HIST_START, at - rng.rint(1, 40) * DAY))
        if early >= at:
            return ([('A', at, p)], {'plain'})
        return ([('A', early, wrong()), ('A', at, p)], {'superseded'})
    if story == 'draft':
        d_at = nudge(min(CUT - DAY, at + rng.rint(1, 20) * DAY))
        return ([('A', at, p), ('D', max(d_at, at), wrong())], {'draft'})
    if story == 'postcut':
        return ([('A', at, p), ('A', late, wrong())], {'postcut'})
    if story == 'void_postcut':
        return ([('A', at, p), ('V', late, p)], {'void_postcut'})
    raise ValueError(story)

def fake(rng, fname, table, p, at):
    """A record that must not exist at the cut: entered and then voided before the cut."""
    v_at = nudge(min(CUT - 3600 * 3, at + rng.rint(1, 30) * DAY))
    if v_at <= at:
        v_at = at + 3600
    return ([('A', at, p), ('V', v_at, p)], {'void'})

class Refs:
    """Spellings by which other exports refer to packages, services and vulnerabilities."""

    def __init__(self, W, rng):
        self.W, self.rng = (W, rng)
        self.spell = {}
        self.vids = {}
        for v in W.vulns:
            self.vids[v['canon']] = [x for x in (v['cve'], v['ghsa'], v['osv']) if x]

    def pkg_name(self, key, p_spell=0.12):
        eco, name = key.split(':', 1)
        al = self.spell.get(key)
        if al and self.rng.chance(p_spell):
            return self.rng.pick(al)
        return name

    def vid(self, canon, p_alias=0.35):
        ids = self.vids.get(canon, [canon])
        if len(ids) > 1 and self.rng.chance(p_alias):
            return self.rng.pick(ids)
        return canon

def eco_of(key):
    return key.split(':', 1)[0]
REG_FILE = {'pypi': 'registry_pypi.jsonl', 'npm': 'registry_npm.csv', 'maven': 'registry_maven.xml', 'cargo': 'registry_cargo.tsv'}

def spelling_aliases(W, rng, refs):
    taken = set((p['key'] for p in W.packages)) | set((t['key'] for t in W.typo_pkgs))
    for p in W.packages:
        for a in p['aliases']:
            taken.add(f"{p['eco']}:{a['old']}")
    out = {}
    for p in W.packages:
        eco, name = (p['eco'], p['name'])
        cands = []
        if eco == 'maven':
            g, a = name.split(':')
            cands = [f'{g}.legacy:{a}', f'{g}:{a}-core', f"{g.replace('org.', 'com.')}:{a}"]
        else:
            base = name.split('/')[-1]
            scope = name[:-len(base)]
            pre = {'pypi': 'py-', 'npm': 'node-', 'cargo': 'rust-'}[eco]
            cands = [scope + base.replace('-', ''), scope + pre + base, scope + base + '-lib']
        rng.shuffle(cands)
        got = []
        for c in cands[:rng.wpick([1, 2, 3], [35, 40, 25])]:
            k = f'{eco}:{c}'
            if k not in taken:
                taken.add(k)
                got.append(c)
        out[p['key']] = got
        refs.spell[p['key']] = got
    return out

def build_registries(W, T, rng, ids, refs):
    files = {f: [] for f in REG_FILE.values()}
    notice_events = []
    pools = [(p, p['rels']) for p in W.packages] + [(tp, tp['rels']) for tp in W.typo_pkgs]
    for p, rels in pools:
        eco = p['eco']
        fname = REG_FILE[eco]
        for r in rels:
            name = r['under'] if r.get('under') else p['name']
            rid = ids('r' + eco[0])
            r['rid'] = rid
            base = {'name': name, 'version': r['ver'], 'published': r['pub'], 'yanked': False}
            revs = [('A', r['pub'], base)]
            cur = dict(base)
            for at, state in sorted(r['yank']):
                if rng.chance(0.45):
                    cur = dict(cur)
                    cur['yanked'] = state
                    revs.append(('A', at, cur))
                else:
                    notice_events.append((at, state, eco, name, r['ver']))
            tags = {'yank_history'} if r['yank'] else set()
            x = rng.below(100)
            if x < 8 and r['pub'] < CUT - 5 * DAY:
                d_at = nudge(gen_time(rng, r['pub'] + 3600, CUT - DAY))
                w = dict(revs[-1][2])
                w['published'] = mutate(rng, 'ts', w['published'])
                revs.append(('D', d_at, w))
                tags.add('draft')
            elif x < 16:
                w = dict(revs[-1][2])
                w['yanked'] = not w['yanked']
                revs.append(('A', nudge(gen_time(rng, max(CUT, r['pub'] + 3600), LATE_END - DAY)), w))
                tags.add('postcut')
            files[fname].append(rec(rid, revs, tags, ('release', p['key'] if 'target' not in p else p['key'], r)))
        if rng.chance(0.06) and rels:
            r = rng.pick(rels)
            v = Ver(r['ver'].major, r['ver'].minor, r['ver'].patch + 40)
            at = nudge(gen_time(rng, HIST_START, CUT - 10 * DAY))
            pf = {'name': p['name'], 'version': v, 'published': at, 'yanked': False}
            revs, tags = fake(rng, fname, 'releases', pf, at)
            files[fname].append(rec(ids('r' + eco[0]), revs, tags | {'fake'}))
    return (files, notice_events)

def build_mirror(W, T, rng, ids, target):
    allrels = [(p, r) for p in W.packages for r in p['rels']]
    q_rels = [(p, r) for p, r in allrels if r['quarantine']]
    others = [(p, r) for p, r in allrels if not r['quarantine']]
    picks = q_rels + rng.sample(others, max(0, int(target * 0.94) - len(q_rels)))
    out = []
    for p, r in sorted(picks, key=lambda x: x[1]['rid']):
        pub = r['pub']
        tags = {'mirror_copy'}
        yk = yanked_at(r, CUT)
        if rng.chance(0.05):
            pub = nudge(pub + rng.rint(1, 6) * DAY)
            tags.add('mirror_pub_drift')
        if r['yank'] and rng.chance(0.4):
            yk = yanked_at(r, CUT - 10 * DAY)
            tags.add('mirror_yank_lag')
        name = r['under'] if r.get('under') else p['name']
        payload = {'eco': p['eco'], 'name': name, 'version': r['ver'], 'published': pub, 'yanked': yk, 'quarantined': r['quarantine'], 'license': r['lic']}
        if r['quarantine']:
            tags.add('quarantine')
        at = min(CUT - 3 * 3600, nudge(max(r['pub'] + 3600, CUT - 20 * DAY) + rng.rint(0, 5) * DAY)) if r['pub'] < CUT - DAY else nudge(gen_time(rng, CUT, LATE_END - DAY))
        revs, st = wrap(rng, 'registry_mirror.parquet', 'mirror', payload, at, story=rng.wpick(['plain', 'superseded', 'draft'], [90, 6, 4]), exclude=('quarantined',))
        out.append(rec(ids('mi'), revs, tags | st, ('mirror', p['key'], r)))
    return out

def build_aliases(W, T, rng, ids, refs, spell):
    out, legacy = ([], [])
    alias_rows = []
    for p in W.packages:
        eco = p['eco']
        for sname in spell[p['key']]:
            eff = nudge(gen_time(rng, HIST_START, CUT - 30 * DAY))
            alias_rows.append(('spelling', p, sname, eff, None))
        for a in p['aliases']:
            alias_rows.append(('rename', p, a['old'], a['eff'], a))
        for tname in p['typos']:
            alias_rows.append(('typo', p, tname, nudge(gen_time(rng, HIST_START, CUT - 5 * DAY)), None))
        if rng.chance(0.08):
            alias_rows.append(('vendor', p, 'vendored-' + p['name'] if eco != 'maven' else p['name'].replace(':', ':vendored-'), nudge(gen_time(rng, HIST_START, CUT - 5 * DAY)), None))
    for kind, p, aname, eff, a in alias_rows:
        payload = {'eco': p['eco'], 'alias': aname, 'target': p['name'], 'kind': kind, 'effective': eff}
        rid = ids('al')
        if a is not None:
            a['rid'] = rid
        if kind == 'rename' and a['legacy_only']:
            legacy.append(rec(ids('lg'), [('A', eff, dict(payload, note='pre-2024 crosswalk'))], {'legacy_required'}, ('alias', p['key'], a)))
            continue
        at = min(eff, CUT - DAY) if eff < CUT else eff
        revs, st = wrap(rng, 'name_aliases.tsv', 'aliases', payload, at, exclude=('kind',)) if at < CUT else ([('A', at, payload)], {'postcut_fact'})
        tags = st | {kind}
        out.append(rec(rid, revs, tags, ('alias', p['key'], a)))
        if rng.chance(0.93) or (kind == 'rename' and eff < LEGACY_ALIAS_CUTOFF):
            lp = dict(payload, note='migrated from cmdb')
            legacy.append(rec(ids('lg'), [('A', at, lp)], {'legacy_copy'}, ('alias', p['key'], a)))
    for p in rng.sample(W.packages, max(1, len(W.packages) // 30)):
        nm = 'old-' + p['name'] if p['eco'] != 'maven' else p['name'].replace(':', ':old-')
        eff = nudge(gen_time(rng, LEGACY_ALIAS_CUTOFF + DAY, CUT - DAY))
        legacy.append(rec(ids('lg'), [('A', eff, {'eco': p['eco'], 'alias': nm, 'target': p['name'], 'kind': 'rename', 'effective': eff, 'note': 'final'})], {'legacy_pull'}, None))
    return (out, legacy)

def build_notices(W, T, rng, ids, notice_events, refs):
    out = []
    for at, state, eco, name, ver in notice_events:
        payload = {'action': 'yank' if state else 'unyank', 'eco': eco, 'name': name, 'version': ver, 'ref': None}
        rid = ids('nt')
        out.append(rec(rid, [('A', at, payload)], {'yank_notice'}))
        if rng.chance(0.15):
            out.append(rec(rid, [('A', at, payload)], {'resend'}))
    for p in W.packages:
        for a in p['aliases']:
            if a['legacy_only']:
                continue
            if a['confirmed']:
                at = nudge(gen_time(rng, max(HIST_START, a['eff'] - 20 * DAY), CUT - 3600 * 4))
                out.append(rec(ids('nt'), [('A', at, {'action': 'rename', 'eco': p['eco'], 'name': p['name'], 'version': None, 'ref': a['rid']})], {'rename_confirm'}))
            elif rng.chance(0.5):
                at = nudge(gen_time(rng, CUT, LATE_END - DAY))
                out.append(rec(ids('nt'), [('A', at, {'action': 'rename', 'eco': p['eco'], 'name': p['name'], 'version': None, 'ref': a['rid']})], {'rename_late'}))
    return out

def build_owners(W, T, rng, ids, refs):
    out = []
    for p in W.packages:
        for eff, team in p['owners']:
            payload = {'eco': p['eco'], 'name': refs.pkg_name(p['key']), 'team': team, 'role': 'owner', 'effective': eff}
            if eff < CUT:
                revs, st = wrap(rng, 'package_owners.json', 'owners', payload, eff, exclude=('role', 'effective'))
            else:
                revs, st = ([('A', eff, payload)], {'postcut_fact'})
            out.append(rec(ids('ow'), revs, st | {'owner'}, ('owner', p['key'])))
        for _ in range(rng.wpick([0, 1, 2, 3, 4], [10, 25, 30, 22, 13])):
            eff = nudge(gen_time(rng, HIST_START, CUT + 10 * DAY))
            payload = {'eco': p['eco'], 'name': refs.pkg_name(p['key']), 'team': rng.pick(W.team_ids), 'role': rng.pick(['maintainer', 'reviewer']), 'effective': eff}
            if eff < CUT:
                revs, st = wrap(rng, 'package_owners.json', 'owners', payload, eff, exclude=('role',))
            else:
                revs, st = ([('A', eff, payload)], {'postcut_fact'})
            out.append(rec(ids('ow'), revs, st | {'role_bait'}, ('owner', p['key'])))
    return out
COLLECTOR = {'eu-west': 'east', 'ap-south': 'west', 'ap-north': 'west', 'ap-southeast': 'west'}
LOG_FILE = {'east': 'deploy_events_east.log', 'west': 'deploy_events_west.log', 'central': 'deploy_events_central.log', 'legacy': 'deploy_events_legacy.log'}

def collector_of(s, t):
    if s['region'] == 'us-central':
        return 'legacy' if t < LEGACY_MIGRATION else 'central'
    return COLLECTOR.get(s['region'])

def _cons_wrong(rng, eco, d):

    def fn(x):
        kinds = ['caret', 'tilde', 'exact', 'range', 'floor'] if eco != 'maven' else ['range', 'exact', 'openlow', 'floor']
        k = rng.pick([k for k in kinds if k != d['ckind']])
        v = d['cons'].lo or Ver(1, 0, 0)
        x['constraint'] = spell_cons(k, v, eco)[0]
        return x
    return fn

def build_manifests(W, T, rng, ids, refs):
    files = {f: [] for f in MANIFEST_FILE.values()}
    snapshot = []
    others = list(MANIFEST_FILE.values())
    for s in W.services:
        if s['home'] == 'image':
            continue
        home = MANIFEST_FILE[s['home']]
        arch_at = next((at for ev, at in s['life'] if ev == 'archived'), None)
        for d in s['deps']:
            eco = eco_of(d['pkg'])
            payload = {'service': s['svc'], 'eco': eco, 'name': refs.pkg_name(d['pkg']), 'constraint': d['raw'], 'scope': d['scope'], 'locked': d['locked']}
            rid = ids('dc')
            fact = ('decl', s['svc'], d)
            if d['locked'] >= CUT:
                files[home].append(rec(rid, [('A', d['locked'], payload)], {'postcut_fact'}, fact))
                continue
            if s['archived']:
                old = dict(payload)
                old['constraint'] = _cons_wrong(rng, eco, d)({})['constraint'] if rng.chance(0.5) else payload['constraint']
                old['locked'] = nudge(min(d['locked'], arch_at) - rng.rint(1, 20) * DAY)
                files[home].append(rec(rid, [('A', old['locked'], old), ('V', arch_at, old)], {'archived_void'}, fact))
                srevs = [('A', d['locked'], payload)]
                if d['removed'] is not None:
                    srevs.append(('V', max(d['removed'], d['locked'] + 60), payload))
                snapshot.append(rec(ids('sn'), srevs, {'snapshot_required'}, fact))
                continue
            if d['removed'] is not None:
                if d['removed'] < CUT:
                    files[home].append(rec(rid, [('A', d['locked'], payload), ('V', max(d['removed'], d['locked'] + 60), payload)], {'removed'}, fact))
                    continue
                files[home].append(rec(rid, [('A', d['locked'], payload), ('V', d['removed'], payload)], {'void_postcut'}, fact))
                continue
            revs, st = wrap(rng, home, 'declarations', payload, d['locked'], exclude=('scope', 'locked'), wrong_fn=_cons_wrong(rng, eco, d))
            files[home].append(rec(rid, revs, st, fact))
            if home == 'manifests_core.csv' and rng.chance(0.93):
                sp = dict(payload)
                tags = {'snapshot_copy'}
                if rng.chance(0.06):
                    sp = _cons_wrong(rng, eco, d)(sp)
                    tags.add('snapshot_drift')
                snapshot.append(rec(ids('sn'), [('A', nudge(max(HIST_START, d['locked'] - DAY)), sp)], tags, fact))
            if rng.chance(0.03):
                other = rng.pick([f for f in others if f != home])
                files[other].append(rec(ids('dc'), [('A', d['locked'], dict(payload))], {'stray'}, fact))
    return (files, snapshot)

def build_overrides(W, T, rng, ids, refs, target):
    out = []
    for o in W.overrides:
        rid = ids('lo')
        o['oid'] = rid
        payload = {'service': o['svc'], 'eco': eco_of(o['pkg']), 'name': refs.pkg_name(o['pkg']), 'version': o['ver'], 'valid_from': o['from'], 'valid_to': o['to']}
        at = nudge(min(o['decided'], CUT - DAY) - rng.rint(1, 10) * DAY)
        revs, st = wrap(rng, 'lock_overrides.toml', 'overrides', payload, at, exclude=('version',))
        out.append(rec(rid, revs, st | {'override'}, ('override', o)))
    W.noise_overrides = []
    deps = [(s, d) for s in W.services for d in s['deps']]
    nl = sum((len(x['revs']) for x in out))
    while nl < target and deps:
        s, d = rng.pick(deps)
        p = W.pkg_by[d['pkg']]
        r = rng.pick(p['rels'])
        v = r['ver'] if rng.chance(0.8) else Ver(r['ver'].major, r['ver'].minor, r['ver'].patch + 50)
        vf = rng.rint(Q_START_DAY - 200, CUT_DAY + 20)
        rid = ids('lo')
        payload = {'service': s['svc'], 'eco': p['eco'], 'name': refs.pkg_name(p['key']), 'version': v, 'valid_from': vf, 'valid_to': vf + rng.rint(5, 90)}
        at = nudge(gen_time(rng, HIST_START, CUT - DAY))
        revs, st = wrap(rng, 'lock_overrides.toml', 'overrides', payload, at, exclude=('version',))
        out.append(rec(rid, revs, st | {'override_noise'}, None))
        nl += len(revs)
        W.noise_overrides.append(rid)
    return out

def build_scanner(W, T, rng, ids, refs):
    out = []
    for s in W.services:
        if s['home'] != 'image' or T.svc_status[s['svc']] != 'active':
            continue
        for key, ver, seen in W.scanner.get(s['svc'], []):
            payload = {'service': s['svc'], 'eco': eco_of(key), 'name': refs.pkg_name(key), 'version': ver, 'seen': seen, 'image': f'img-{rng.rint(100, 999)}'}
            out.append(rec(ids('sc'), [('A', seen, payload)], {'scanner_required'}, ('scan', s['svc'], key)))
    for row in T.pins:
        if row['scope'] != 'runtime' or row['pinned'] is None or row['source'] == 'scanner_findings.jsonl' or (not rng.chance(0.42)):
            continue
        ver = row['pinned']
        tags = {'scanner_copy'}
        if rng.chance(0.05):
            ver = Ver(ver.major, ver.minor, ver.patch + 1)
            tags.add('scanner_drift')
        seen = nudge(gen_time(rng, Q_START, CUT - DAY))
        payload = {'service': row['service'], 'eco': eco_of(row['package']), 'name': refs.pkg_name(row['package']), 'version': ver, 'seen': seen, 'image': f'img-{rng.rint(100, 999)}'}
        out.append(rec(ids('sc'), [('A', seen, payload)], tags, ('scan', row['service'], row['package'])))
    return out

def build_catalog(W, T, rng, ids):
    sv, own, life = ([], [], [])
    fsv, fown, flife = ([], [], [])
    for s in W.services:
        p = {'service': s['svc'], 'name': s['name'], 'tier': s['tier'], 'region': s['region'], 'manifest': s['home']}
        at = nudge(gen_time(rng, HIST_START, Q_START - DAY))
        revs, st = wrap(rng, 'service_catalog.xlsx', 'services', p, at, exclude=('region', 'manifest', 'name'))
        sv.append(rec(ids('sv'), revs, st, ('service', s['svc'])))
        fp = dict(p)
        ft = {'final_copy'}
        if rng.chance(0.05):
            fp['tier'] = (s['tier'] + rng.rint(1, 3)) % 4
            ft.add('final_tier_drift')
        fsv.append(rec(ids('fs'), [('A', nudge(CUT - 2 * DAY), fp)], ft, ('service', s['svc'])))
        first = s['owners'][0][0]
        hist = []
        if rng.chance(0.55):
            hist.append((nudge(gen_time(rng, HIST_START - 300 * DAY, first - DAY)), rng.pick(W.team_ids)))
        for eff, team in hist + s['owners']:
            pp = {'service': s['svc'], 'team': team, 'effective': eff}
            if eff < CUT:
                revs, st = wrap(rng, 'service_catalog.xlsx', 'ownership', pp, eff, exclude=('effective',))
            else:
                revs, st = ([('A', eff, pp)], {'postcut_fact'})
            own.append(rec(ids('so'), revs, st, ('ownership', s['svc'])))
            fpp = dict(pp)
            ft = {'final_copy'}
            if eff >= CUT and rng.chance(0.5):
                fpp['effective'] = nudge(CUT - rng.rint(2, 9) * DAY)
                ft.add('final_backdated')
            fown.append(rec(ids('fo'), [('A', min(eff, CUT - DAY), fpp)], ft, ('ownership', s['svc'])))
        events = list(s['life'])
        for _ in range(rng.wpick([0, 1, 2, 3], [20, 40, 28, 12])):
            events.append((rng.pick(['paused', 'renamed']), nudge(gen_time(rng, HIST_START, CUT + 10 * DAY))))
        for ev, at in sorted(events, key=lambda x: x[1]):
            pp = {'service': s['svc'], 'event': ev, 'at': at}
            if s['migrated']:
                flife.append(rec(ids('fl'), [('A', at, pp)], {'final_required'}, ('life', s['svc'])))
                continue
            if at < CUT:
                revs, st = wrap(rng, 'service_catalog.xlsx', 'lifecycle', pp, at, exclude=('event', 'at'))
            else:
                revs, st = ([('A', at, pp)], {'postcut_fact'})
            life.append(rec(ids('sl'), revs, st, ('life', s['svc'])))
            if rng.chance(0.9):
                flife.append(rec(ids('fl'), [('A', min(at, CUT - DAY), pp)], {'final_copy'}, ('life', s['svc'])))
    return ({'services': sv, 'ownership': own, 'lifecycle': life}, {'services': fsv, 'ownership': fown, 'legacy_lifecycle': flife})

def build_clock(W, rng):
    hosts = {}
    n = max(5, round(19 * W.scale))
    for side in ('east', 'west', 'central', 'legacy'):
        hosts[side] = [f'col-{side}{k:02d}' for k in range(1, n + 1)]
    W.collector_hosts = hosts
    W.offset = {}
    for side, hs in hosts.items():
        for h in hs:
            cur = rng.rint(-360, 360) * 60
            for z in range(Q_START_DAY - 21, CUT_DAY + 12):
                if rng.chance(0.06):
                    cur = rng.rint(-360, 360) * 60
                W.offset[h, z] = cur

def build_deploys(W, T, rng, ids):
    build_clock(W, rng)
    logs = {f: [] for f in LOG_FILE.values()}
    for s in W.services:
        for dp in s['deploys']:
            t = dp['t']
            side = collector_of(s, t)
            if side is None:
                continue
            for _ in range(20):
                h = rng.pick(W.collector_hosts[side])
                off = W.offset.get((h, t // DAY), 0)
                at = t + off
                if W.offset.get((h, at // DAY), 0) == off and (not ambiguous_or_gap(at)) and (not ambiguous_or_gap(t + 600)):
                    break
            dp['host'], dp['at'] = (h, at)
            payload = {'host': h, 'service': s['svc'], 'outcome': dp['outcome'], 'at': at}
            ing = t + rng.rint(1, 10) * 60
            fname = LOG_FILE[side]
            rid = ids('dp')
            dp['rid'] = rid
            if ing < CUT:
                revs, st = wrap(rng, fname, 'deploys', payload, ing, exclude=('at',))
            else:
                revs, st = ([('A', ing, payload)], {'postcut_fact'})
            logs[fname].append(rec(rid, revs, st, ('deploy', s['svc'], dp)))
            if rng.chance(0.05):
                other = rng.pick([f for f in LOG_FILE.values() if f != fname])
                logs[other].append(rec(rid, [('A', ing, payload)], {'relay'}, ('deploy', s['svc'], dp)))
            elif side == 'central' and rng.chance(0.3):
                logs[LOG_FILE['legacy']].append(rec(rid, [('A', ing, payload)], {'relay'}, ('deploy', s['svc'], dp)))
        if rng.chance(0.12) and collector_of(s, Q_START + DAY):
            side = collector_of(s, Q_START + 40 * DAY)
            t = nudge(gen_time(rng, Q_START, CUT - DAY))
            h = rng.pick(W.collector_hosts[side])
            payload = {'host': h, 'service': s['svc'], 'outcome': 'succeeded', 'at': t + W.offset.get((h, t // DAY), 0)}
            revs, st = fake(rng, LOG_FILE[side], 'deploys', payload, t + 120)
            logs[LOG_FILE[side]].append(rec(ids('dp'), revs, st | {'fake'}, None))
    for s in rng.sample(W.services, max(5, len(W.services) // 6)):
        for _ in range(rng.rint(1, 3)):
            t = nudge(gen_time(rng, Q_START, CUT - 2 * DAY))
            if s['region'] == 'us-central' and t < LEGACY_MIGRATION:
                t = LEGACY_MIGRATION + rng.rint(1, 40) * DAY
            h = rng.pick(W.collector_hosts['legacy'])
            payload = {'host': h, 'service': s['svc'], 'outcome': 'succeeded', 'at': t + W.offset.get((h, t // DAY), 0)}
            logs[LOG_FILE['legacy']].append(rec(ids('dp'), [('A', t + 300, payload)], {'legacy_pull'}, None))
    return logs

def build_offsets(W, rng, ids):
    out = []
    for (h, z), off in sorted(W.offset.items()):
        payload = {'host': h, 'day': z, 'offset': off}
        at = epoch(*civil_from_days(z)) - rng.rint(1, 20) * 3600
        revs, st = wrap(rng, 'clock_offsets.txt', 'offsets', payload, min(at, CUT - DAY) if z < CUT_DAY else at, exclude=('day',)) if z < CUT_DAY else ([('A', at, payload)], {'postcut_fact'} if at >= CUT else {'plain'})
        out.append(rec(ids('ck'), revs, st, ('offset', h, z)))
    return out

def build_freeze(W, rng, ids):
    out = []
    for s in W.services:
        for a, b in s['freeze']:
            payload = {'service': s['svc'], 'start': a, 'end': b}
            at = nudge(epoch(*civil_from_days(a)) - rng.rint(1, 20) * DAY)
            if at < CUT:
                revs, st = wrap(rng, 'change_freeze.ics', 'windows', payload, at, story=rng.wpick(['plain', 'superseded', 'draft', 'postcut'], [60, 18, 12, 10]))
            else:
                revs, st = ([('A', at, payload)], {'postcut_fact'})
            out.append(rec(ids('fz'), revs, st, ('freeze', s['svc'])))
        if rng.chance(0.3):
            a = rng.rint(Q_START_DAY, CUT_DAY - 5)
            payload = {'service': s['svc'], 'start': a, 'end': a + rng.rint(1, 4)}
            at = nudge(epoch(*civil_from_days(a)) - 5 * DAY)
            revs, st = fake(rng, 'change_freeze.ics', 'windows', payload, at)
            out.append(rec(ids('fz'), revs, st | {'cancelled'}, None))
    return out

def build_osv(W, T, rng, ids, refs):
    out, replay = ([], [])
    for v in W.vulns:
        for a in v['aff']:
            key = a['pkg']
            ev = SEE_DECOY if a['replay'] else a['events']
            payload = {'osv': v['osv'], 'eco': eco_of(key), 'name': refs.pkg_name(key), 'events': ev, 'published': UNKNOWN if v['pub_unknown'] else v['pub'], 'withdrawn': NONE if rng.chance(0.1) else None}
            at = v['pub']
            rid = ids('os')
            tags = {'osv'}
            if at >= CUT:
                revs = [('A', at, payload)]
                tags.add('postcut_fact')
            else:
                revs, st = wrap(rng, 'advisories_osv.jsonl', 'osv', payload, at, story=rng.wpick(['plain', 'superseded', 'draft'], [70, 18, 12]), exclude=('published', 'withdrawn'))
                tags |= st
                if v['withdrawn'] is not None:
                    w = dict(revs[-1][2] if revs[-1][0] != 'D' else payload)
                    w['withdrawn'] = v['withdrawn']
                    revs = [r for r in revs] + [('A', v['withdrawn'], w)]
                    tags.add('withdrawn' if v['withdrawn'] < CUT else 'withdrawn_late')
            if a['replay']:
                tags.add('replay_pointer')
            out.append(rec(rid, revs, tags, ('osv', v['canon'], a)))
            if a['replay'] or rng.chance(0.95):
                rp = dict(payload, events=a['events'])
                rt = {'replay_required'} if a['replay'] else {'replay_copy'}
                if v['withdrawn'] is not None and v['withdrawn'] >= CUT and rng.chance(0.7):
                    rp['withdrawn'] = v['withdrawn']
                    rt.add('replay_early_withdrawal')
                elif v['withdrawn'] is not None and v['withdrawn'] < CUT:
                    rp['withdrawn'] = v['withdrawn']
                ra = nudge(min(CUT - DAY, max(at, CUT - 12 * DAY))) if at < CUT else at
                replay.append(rec(ids('rp'), [('A', ra, rp)], rt, ('osv', v['canon'], a)))
    return (out, replay)

def build_ghsa(W, T, rng, ids, refs):
    out, cache = ([], [])
    for v in W.vulns:
        if not v['ghsa']:
            continue
        for a in v['aff']:
            payload = {'ghsa': v['ghsa'], 'eco': eco_of(a['pkg']), 'name': refs.pkg_name(a['pkg']), 'vector': SEE_DECOY if v['cache'] else v['ghsa_vec'], 'reviewed': v['ghsa_reviewed'], 'published': v['ghsa_pub']}
            at = v['ghsa_pub']
            if at < CUT:
                revs, st = wrap(rng, 'advisories_ghsa.json', 'ghsa', payload, at, exclude=('published', 'vector'))
            else:
                revs, st = ([('A', at, payload)], {'postcut_fact'})
            out.append(rec(ids('gh'), revs, st | ({'cache_pointer'} if v['cache'] else set()), ('ghsa', v['canon'])))
        for a in v['aff']:
            cp = {'ghsa': v['ghsa'], 'eco': eco_of(a['pkg']), 'name': refs.pkg_name(a['pkg']), 'vector': v['ghsa_vec'], 'score': None, 'fetched': nudge(min(CUT - DAY, v['ghsa_pub'] + 2 * DAY))}
            tags = {'cache_required'} if v['cache'] else {'cache_copy'}
            if not v['cache'] and rng.chance(0.05):
                cp['vector'] = mutate(rng, 'vec', v['ghsa_vec'])
                tags.add('cache_stale')
            if v['cache'] or rng.chance(0.93):
                cp['score'] = cvss_naive(cp['vector'])
                at = cp['fetched'] if v['ghsa_pub'] < CUT else nudge(v['ghsa_pub'] + DAY)
                cache.append(rec(ids('fc'), [('A', at, cp)], tags, ('ghsa', v['canon'])))
    return (out, cache)

def cvss_naive(vec):
    """What an aggregator caches: the same formula rounded half-up to one decimal (not the CVSS Roundup)."""
    head, m = cvss_parts(vec)
    iss = 1 - (1 - CIA_W[m['C']]) * (1 - CIA_W[m['I']]) * (1 - CIA_W[m['A']])
    changed = m['S'] == 'C'
    impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15 if changed else 6.42 * iss
    pr = (PR_C if changed else PR_U)[m['PR']]
    expl = 8.22 * AV_W[m['AV']] * AC_W[m['AC']] * pr * UI_W[m['UI']]
    if impact <= 0:
        return D('0.0')
    return q(D(repr(min((1.08 if changed else 1.0) * (impact + expl), 10))), 1, 'up')

def build_nvd(W, T, rng, ids):
    out = []
    for v in W.vulns:
        if not v['cve']:
            continue
        win_src = v['nvd_src']
        m_w = nudge(gen_time(rng, max(HIST_START, v['pub']), max(v['pub'] + DAY, CUT - DAY))) if v['pub'] < CUT else nudge(v['pub'] + DAY)
        hist = [(m_w, win_src, v['nvd_vec'], 'nvd_winner')]
        v['nvd_visible'] = m_w < CUT
        for _ in range(rng.wpick([1, 2, 3, 4, 5], [20, 30, 25, 15, 10])):
            kind = rng.wpick(['earlier', 'cna', 'late'], [50, 30, 20])
            vec = mutate(rng, 'vec', v['nvd_vec'])
            if kind == 'earlier':
                t = nudge(gen_time(rng, HIST_START, max(HIST_START + DAY, m_w - 3600)))
                hist.append((min(t, m_w - 3600), win_src, vec, 'nvd_superseded'))
            elif kind == 'cna' and win_src == 'NVD':
                hist.append((nudge(gen_time(rng, HIST_START, CUT - DAY)), 'CNA', vec, 'nvd_cna_bait'))
            else:
                hist.append((nudge(gen_time(rng, max(CUT, m_w + 3600), LATE_END - DAY)), rng.pick(['NVD', 'CNA']), vec, 'nvd_late'))
        if v['pub'] >= CUT:
            hist = [(nudge(gen_time(rng, CUT, LATE_END - DAY)), s_, vc, tg) for _, s_, vc, tg in hist]
        for mt, src, vec, tag in hist:
            payload = {'cve': v['cve'], 'vector': vec, 'source': src, 'modified': mt}
            if mt < CUT:
                revs, st = wrap(rng, 'advisories_nvd.xml', 'nvd', payload, mt, story=rng.wpick(['plain', 'draft', 'postcut'], [80, 12, 8]), exclude=('modified', 'source'))
            else:
                revs, st = ([('A', mt, payload)], {'postcut_fact'})
            out.append(rec(ids('nv'), revs, st | {tag}, ('nvd', v['canon'])))
    return out

def build_vuln_aliases(W, T, rng, ids):
    out = []
    for v in W.vulns:
        idl = [x for x in (v['cve'], v['ghsa'], v['osv']) if x]
        pairs = [(idl[i], idl[i + 1]) for i in range(len(idl) - 1)]
        if len(idl) == 3 and rng.chance(0.4):
            pairs.append((idl[0], idl[2]))
        at = min(CUT - DAY, nudge(v['pub'] - rng.rint(1, 20) * DAY))
        for a, b in pairs:
            payload = {'a': a, 'b': b} if rng.chance(0.5) else {'a': b, 'b': a}
            out.append(rec(ids('va'), [('A', at, payload)], {'alias_pair'}, ('valias', v['canon'])))
            if rng.chance(0.25):
                out.append(rec(ids('va'), [('A', at + 3600, dict(payload))], {'alias_dup'}, ('valias', v['canon'])))
        if rng.chance(0.06):
            other = rng.pick(W.vulns)
            if other['canon'] != v['canon']:
                payload = {'a': idl[0], 'b': other['osv']}
                revs, st = fake(rng, 'advisory_aliases.csv', 'aliases', payload, at)
                out.append(rec(ids('va'), revs, st | {'alias_wrong_void'}, None))
    return out

def build_rescores(W, T, rng, ids, refs):
    out = []
    for v in W.vulns:
        for r in v['resc']:
            payload = {'vuln': refs.vid(v['canon']), 'vector': r['vec'], 'approved': r['approved'], 'scored': r['at']}
            if r['at'] < CUT:
                revs, st = wrap(rng, 'advisory_rescores.parquet', 'rescores', payload, r['at'], exclude=('scored',))
            else:
                revs, st = ([('A', r['at'], payload)], {'postcut_fact' if not r['approved'] else 'postcut_rescore'})
            out.append(rec(ids('rs'), revs, st | ({'approved'} if r['approved'] else {'unapproved'}), ('rescore', v['canon'], r)))
    return out

def build_authority(W, T, rng, ids, refs):
    out = []
    for v in W.vulns:
        at = nudge(min(CUT - DAY, v['pub'] + rng.rint(1, 9) * DAY)) if v['pub'] < CUT else nudge(v['pub'] + DAY)
        spec = []
        if v['prec_vec'] == 'ghsa':
            spec.append(('cvss_vector', 'ghsa>nvd', 'authority_override'))
        else:
            spec.append(('cvss_vector', 'nvd>ghsa', 'authority_restate'))
        if v['prec_pub'] == 'ghsa':
            spec.append(('published', 'ghsa>osv', 'authority_override'))
        else:
            spec.append(('published', 'osv>ghsa', 'authority_restate'))
        for field, order, tag in spec:
            payload = {'vuln': refs.vid(v['canon']), 'field': field, 'order': order}
            flip = '>'.join(reversed(order.split('>')))
            if at < CUT:
                revs, st = wrap(rng, 'precedence.yaml', 'authority', payload, at, exclude=('field',), wrong_fn=lambda x, f=flip: dict(x, order=f))
            else:
                revs, st = ([('A', at, payload)], {'postcut_fact'})
            out.append(rec(ids('pr'), revs, st | {tag}, ('authority', v['canon'])))
    return out

def build_vex(W, T, rng, ids, refs):
    out = []
    for x in W.vex:
        payload = {'service': x['svc'], 'vuln': refs.vid(x['vuln']), 'status': x['status'], 'justification': x['just'] or 'none', 'issued': x['issued']}
        if x['issued'] < CUT:
            revs, st = wrap(rng, 'vex_statements.xml', 'vex', payload, x['issued'], exclude=('issued', 'status', 'justification'))
        else:
            revs, st = ([('A', x['issued'], payload)], {'postcut_fact'})
        out.append(rec(ids('vx'), revs, st | {'vex_' + x['status']}, ('vex', x['svc'], x['vuln'])))
    return out

def build_waivers(W, T, rng, ids, refs):
    out = []
    for w in W.waivers:
        rid = ids('wv')
        w['wid'] = rid
        payload = {'service': w['svc'], 'vuln': refs.vid(w['vuln']), 'granted': w['granted'], 'expires': w['expires'], 'approver': rng.pick(['a.rao', 'm.okafor', 'j.lindqvist', 's.mehta', 'p.dubois'])}
        if w['granted'] < CUT:
            revs, st = wrap(rng, 'waivers.db', 'waivers', payload, w['granted'], exclude=('granted', 'expires'))
        else:
            revs, st = ([('A', w['granted'], payload)], {'postcut_fact'})
        out.append(rec(rid, revs, st, ('waiver', w)))
    return out
NOTES = ['patched in staging', 'bumped minor, "hot" fix', 'pairing, review', 'rollback test\nretried', 'dependency, lockfile refresh', '', 'waiting on vendor', 'triage; reproduce']

def build_license_scan(W, T, rng, ids, refs, target):
    want = []
    seen = set()
    for row in T.pins:
        if row['pinned'] is not None and row['scope'] == 'runtime':
            k = (row['package'], str(row['pinned']))
            if k not in seen:
                seen.add(k)
                want.append(k)
    for row in T.packages_rows_pre:
        if row['latest'] is not None:
            k = (row['package'], str(row['latest']))
            if k not in seen:
                seen.add(k)
                want.append(k)
    must = len(want)
    for key, info in T.pk.items():
        for r in info['rels']:
            k = (key, str(r['ver']))
            if k not in seen and rng.chance(0.25):
                seen.add(k)
                want.append(k)
    out = []
    for wi, (key, vs) in enumerate(want):
        if wi >= must and len(out) >= target:
            break
        info = T.pk[key]
        r = next((x for x in info['rels'] if str(x['ver']) == vs))
        lo = max(r['pub'], HIST_START)
        if lo >= CUT:
            continue
        sc = max(lo, min(CUT - 120, nudge(gen_time(rng, lo, max(lo + 3600, CUT - DAY)))))
        payload = {'eco': eco_of(key), 'name': refs.pkg_name(key) if key in W.pkg_by else key.split(':', 1)[1], 'version': r['ver'], 'expression': r['lic'], 'scanned': sc}
        revs, st = wrap(rng, 'license_scan.parquet', 'scans', payload, sc, story=rng.wpick(['plain', 'draft', 'superseded'], [75, 13, 12]), exclude=('scanned', 'version'))
        out.append(rec(ids('ls'), revs, st, ('scan', key, r)))
        if rng.chance(0.1) and sc > lo + 7200:
            old = dict(payload, expression=mutate(rng, 'spdx', r['lic']), scanned=nudge(gen_time(rng, lo, sc - 3600)))
            out.append(rec(ids('ls'), [('A', old['scanned'], old)], {'older_scan'}, ('scan', key, r)))
        if rng.chance(0.04):
            late = nudge(gen_time(rng, CUT, LATE_END - DAY))
            out.append(rec(ids('ls'), [('A', late, dict(payload, expression=mutate(rng, 'spdx', r['lic']), scanned=late))], {'postcut_fact'}, ('scan', key, r)))
    return out

def build_license_overrides(W, T, rng, ids, refs, target):
    out = []
    for o in W.lic_over:
        st_word = 'decided' if o['approved'] else rng.pick(['proposed', 'withdrawn'])
        payload = {'eco': eco_of(o['pkg']), 'name': refs.pkg_name(o['pkg']), 'range': o['raw'], 'expression': o['expr'], 'status': st_word, 'decided': o['decided']}
        if o['decided'] < CUT:
            revs, st = wrap(rng, 'license_overrides.csv', 'overrides', payload, o['decided'], exclude=('decided', 'status', 'expression'))
        else:
            revs, st = ([('A', o['decided'], payload)], {'postcut_fact'})
        out.append(rec(ids('lv'), revs, st | {'lic_override_' + st_word}, ('licover', o)))
    while len(out) < target:
        p = rng.pick(W.packages)
        vs = sorted((r['ver'] for r in p['rels']))
        lo = rng.pick(vs)
        raw, cons = spell_cons('range', Ver(lo.major, lo.minor, lo.patch), p['eco'])
        late = rng.chance(0.25)
        dt = nudge(gen_time(rng, CUT, LATE_END - DAY)) if late else nudge(gen_time(rng, HIST_START, CUT - DAY))
        payload = {'eco': p['eco'], 'name': refs.pkg_name(p['key']), 'range': raw, 'expression': rng.pick(['MIT', 'GPL-3.0-only', 'Apache-2.0']), 'status': 'decided' if late else rng.pick(['proposed', 'withdrawn']), 'decided': dt}
        out.append(rec(ids('lv'), [('A', dt, payload)], {'lic_override_noise'}, None))
    return out

def build_license_exceptions(W, T, rng, ids, refs, target):
    out = []
    for e in W.lic_exc:
        payload = {'eco': eco_of(e['pkg']), 'name': refs.pkg_name(e['pkg']), 'range': e['raw'], 'class': e['cls'], 'granted': e['granted'], 'revoked': NONE}
        at = epoch(*civil_from_days(e['granted'])) - rng.rint(1, 5) * DAY
        revs = [('A', at, payload)]
        if e['revoked'] is not None:
            revs.append(('A', epoch(*civil_from_days(e['revoked'])) - 3600, dict(payload, revoked=e['revoked'])))
        out.append(rec(ids('lx'), revs, {'exception'} | ({'revoked'} if e['revoked'] is not None else set()), ('licexc', e)))
    while sum((len(x['revs']) for x in out)) < target:
        p = rng.pick(W.packages)
        vs = sorted((r['ver'] for r in p['rels']))
        lo = rng.pick(vs)
        raw, cons = spell_cons('range', Ver(lo.major, lo.minor, lo.patch), p['eco'])
        if rng.chance(0.5):
            g = rng.rint(Q_START_DAY - 400, CUT_DAY - 30)
            rv = rng.rint(g + 1, CUT_DAY - 1)
            tags = {'exception_revoked_noise'}
        else:
            g = rng.rint(CUT_DAY, CUT_DAY + 30)
            rv = None
            tags = {'exception_future'}
        payload = {'eco': p['eco'], 'name': refs.pkg_name(p['key']), 'range': raw, 'class': rng.pick(['permissive', 'weak']), 'granted': g, 'revoked': NONE}
        at = epoch(*civil_from_days(g)) - 2 * DAY
        revs = [('A', at, payload)]
        if rv is not None:
            revs.append(('A', epoch(*civil_from_days(rv)) - 3600, dict(payload, revoked=rv)))
        out.append(rec(ids('lx'), revs, tags, None))
    return out

def build_roster(W, T, rng, ids):
    alloc, teams = ([], [])
    for e in W.engineers:
        for sg in e['segs']:
            payload = {'engineer': e['eng'], 'team': sg['team'], 'fte': sg['fte'], 'oncall': sg['oncall'], 'start': sg['start'], 'end': NONE if sg['end'] is None else sg['end']}
            at = epoch(*civil_from_days(sg['start'])) - rng.rint(0, 10) * DAY
            sg['rec_at'] = at
            if at < CUT:
                revs, st = wrap(rng, 'engineer_roster.ini', 'alloc', payload, at, exclude=('start', 'end'))
            else:
                revs, st = ([('A', at, payload)], {'postcut_fact'})
            alloc.append(rec(ids('ra'), revs, st, ('alloc', e['eng'])))
    for t in W.teams:
        payload = {'team': t['team'], 'model': t['model']}
        revs, st = wrap(rng, 'engineer_roster.ini', 'teams', payload, Q_START - 40 * DAY, story=rng.wpick(['plain', 'superseded', 'postcut'], [60, 25, 15]))
        teams.append(rec(ids('rt'), revs, st, ('teammodel', t['team'])))
    return {'alloc': alloc, 'teams': teams}

def build_rates(W, rng, ids):
    sheets = {'rates_jul': [], 'rates_aug': [], 'rates_sep': []}
    for e in W.engineers:
        for mo, sh in ((7, 'rates_jul'), (8, 'rates_aug'), (9, 'rates_sep')):
            cur, minor = e['rates'][mo]
            payload = {'engineer': e['eng'], 'month': days_from_civil(2025, mo, 1), 'rate': minor, 'currency': cur}
            at = epoch(2025, mo, 1) - rng.rint(1, 20) * DAY
            revs, st = wrap(rng, 'engineer_rates.xlsx', sh, payload, at, exclude=('month', 'currency'), story=rng.wpick(['plain', 'superseded', 'draft', 'postcut'], [76, 10, 8, 6]))
            sheets[sh].append(rec(ids('rr'), revs, st, ('rate', e['eng'], mo)))
    return sheets

def build_fx(W, rng, ids):
    out = []
    for cur in ('USD', 'GBP', 'INR', 'JPY'):
        for at, rate in W.fx[cur]:
            payload = {'currency': cur, 'at': at, 'rate': rate}
            if at < CUT:
                revs, st = wrap(rng, 'fx_fixings.tsv', 'fixings', payload, at, story=rng.wpick(['plain', 'superseded', 'draft', 'postcut'], [70, 14, 8, 8]), exclude=('at', 'currency'))
            else:
                revs, st = ([('A', at, payload)], {'postcut_fact'})
            out.append(rec(ids('fx'), revs, st, ('fx', cur)))
    return out

def build_timesheets(W, T, rng, ids, refs):
    out = []
    for ts in W.timesheets:
        payload = {'engineer': ts['eng'], 'service': ts['svc'], 'vuln': refs.vid(ts['vuln']), 'hours': ts['hours'], 'worked': ts['worked'], 'note': rng.pick(NOTES)}
        at = ts['worked'] + rng.rint(1, 120) * 60
        ts['rid'] = ids('tm')
        if at < CUT:
            revs, st = wrap(rng, 'remediation_timesheets.csv', 'timesheets', payload, at, exclude=('worked',))
        else:
            revs, st = ([('A', at, payload)], {'postcut_fact'})
        out.append(rec(ts['rid'], revs, st, ('timesheet', ts)))
    return out

def build_journal(W, T, rng, ids):
    out = []
    for j in W.journal:
        j['rid'] = j['jid']
    for j in W.journal:
        payload = {'team': j['team'], 'kind': j['kind'], 'amount': j['minor'], 'currency': j['cur'], 'booked': j['booked'], 'reverses': j['reverses']['rid'] if j['reverses'] else None}
        if j['booked'] < CUT:
            revs, st = wrap(rng, 'ledger_journal.db', 'entries', payload, j['booked'], exclude=('kind', 'currency', 'booked'))
        else:
            revs, st = ([('A', j['booked'], payload)], {'postcut_fact'})
        out.append(rec(j['rid'], revs, st | {'j_' + j['kind']}, ('journal', j)))
    return out

def build_factors(W, rng, ids, refs, target):
    out = []
    for (key, mj), (fac, eff) in sorted(W.factors.items()):
        payload = {'eco': eco_of(key), 'name': refs.pkg_name(key), 'major': mj, 'factor': fac, 'effective': eff}
        at = epoch(*civil_from_days(eff)) - rng.rint(1, 30) * DAY
        out.append(rec(ids('cf'), [('A', at, payload)], {'factor'}, ('factor', key, mj)))
        if rng.chance(0.25):
            e0 = eff - rng.rint(30, 300)
            out.append(rec(ids('cf'), [('A', epoch(*civil_from_days(e0)) - DAY, dict(payload, factor=mutate(rng, 'dec', fac), effective=e0))], {'factor_older'}, ('factor', key, mj)))
    keys = [(p['key'], mj) for p in W.packages for mj in p['majors']]
    while len(out) < target:
        key, mj = rng.pick(keys)
        e1 = rng.rint(CUT_DAY, CUT_DAY + 90)
        payload = {'eco': eco_of(key), 'name': refs.pkg_name(key), 'major': mj, 'factor': D(rng.pick(['0.5', '2', '3'])), 'effective': e1}
        out.append(rec(ids('cf'), [('A', nudge(CUT - rng.rint(1, 40) * DAY), payload)], {'factor_future'}, None))
    return out

def build_sla(W, rng, ids, target):
    out = []
    for s in W.services:
        for sev, (days, eff) in sorted(s['sla'].items()):
            payload = {'service': s['svc'], 'severity': sev, 'days': days, 'effective': eff}
            at = epoch(*civil_from_days(eff)) - rng.rint(1, 30) * DAY
            revs, st = wrap(rng, 'sla_policy.pdf', 'sla_overrides', payload, at, story=rng.wpick(['plain', 'superseded', 'draft'], [70, 18, 12]), exclude=('effective', 'severity'))
            out.append(rec(ids('so'), revs, st, ('sla', s['svc'], sev)))
            if rng.chance(0.4):
                e0 = eff - rng.rint(20, 200)
                out.append(rec(ids('so'), [('A', epoch(*civil_from_days(e0)) - DAY, dict(payload, days=days + rng.rint(1, 20), effective=e0))], {'sla_older'}, ('sla', s['svc'], sev)))
    while len(out) < target:
        s = rng.pick(W.services)
        sev = rng.pick(['critical', 'high', 'medium', 'low'])
        cur = s['sla'].get(sev)
        if rng.chance(0.5) or cur is not None:
            e1 = rng.rint(CUT_DAY, CUT_DAY + 120)
            tags = {'sla_future'}
        else:
            e1 = rng.rint(Q_START_DAY - 300, CUT_DAY - 1)
            s['sla'][sev] = (SLA_MATRIX[sev][s['tier']], e1)
            tags = {'sla_restate'}
        payload = {'service': s['svc'], 'severity': sev, 'days': rng.pick([5, 9, 12, 25]) if 'sla_future' in tags else SLA_MATRIX[sev][s['tier']], 'effective': e1}
        out.append(rec(ids('so'), [('A', min(CUT - DAY, epoch(*civil_from_days(e1)) - DAY), payload)], tags, ('sla', s['svc'], sev)))
    return out

def build_estimates(W, rng, ids, refs, target_each):
    sheets = {f'est_{e}': [] for e in ECOS}
    for (key, mj), (hrs, eff) in sorted(W.est_over.items()):
        payload = {'name': refs.pkg_name(key), 'major': mj, 'hours': hrs, 'effective': eff}
        at = epoch(*civil_from_days(eff)) - rng.rint(1, 30) * DAY
        revs, st = wrap(rng, 'remediation_estimates.xlsx', f'est_{eco_of(key)}', payload, at, exclude=('effective', 'major'))
        sheets[f'est_{eco_of(key)}'].append(rec(ids('es'), revs, st, ('estimate', key, mj)))
    for eco in ECOS:
        keys = [(p['key'], mj) for p in W.packages if p['eco'] == eco for mj in p['majors']]
        sh = sheets[f'est_{eco}']
        while len(sh) < target_each:
            key, mj = rng.pick(keys)
            e1 = rng.rint(CUT_DAY, CUT_DAY + 90)
            payload = {'name': refs.pkg_name(key), 'major': mj, 'hours': q(D(rng.rint(4, 200)) / D(4), 2), 'effective': e1}
            sh.append(rec(ids('es'), [('A', nudge(CUT - rng.rint(1, 40) * DAY), payload)], {'estimate_future'}, None))
    return sheets
HIST_DAY = HIST_START // DAY
ERRATA_SKIP = {'errata_register.docx', 'review_minutes.docx', 'source_conventions.html', 'close_contract.md', 'control_totals.html'}
ERRATA_NOFIELD = {'registry_pypi.jsonl': {'yanked', 'version'}, 'registry_npm.csv': {'yanked', 'version'}, 'registry_maven.xml': {'yanked', 'version'}, 'registry_cargo.tsv': {'yanked', 'version'}}

def build_crosswalk(W, rng, ids):
    out = []
    W.xwalk = {}
    pool = {}
    for s in W.services:
        for f in s['legacy_ids']:
            pool.setdefault(f, []).append(s)
    for s in W.services:
        for f in s['legacy_ids']:
            vf = HIST_DAY - rng.rint(100, 600)
            payload = {'legacy': f, 'service': s['svc'], 'valid_from': vf, 'valid_to': NONE}
            at = epoch(*civil_from_days(vf))
            revs, st = wrap(rng, 'close_contract.md', 'crosswalk', payload, at, story=rng.wpick(['plain', 'superseded', 'draft'], [70, 18, 12]), exclude=('valid_to', 'legacy', 'service'))
            out.append(rec(ids('xw'), revs, st, ('xwalk', s['svc'])))
            W.xwalk.setdefault(s['svc'], []).append((f, vf, None))
    svcs = list(W.services)
    for s in rng.sample(svcs, max(3, len(svcs) // 25)):
        other = rng.pick(svcs)
        if other is s:
            continue
        f = f"cmdb-r{int(s['svc'][4:]) * 3 + 1}"
        cut_day = rng.rint(HIST_DAY + 100, Q_START_DAY - 30)
        a = {'legacy': f, 'service': s['svc'], 'valid_from': HIST_DAY - 300, 'valid_to': cut_day}
        b = {'legacy': f, 'service': other['svc'], 'valid_from': cut_day, 'valid_to': NONE}
        out.append(rec(ids('xw'), [('A', epoch(*civil_from_days(HIST_DAY - 300)), a)], {'reused_old'}, ('xwalk', s['svc'])))
        out.append(rec(ids('xw'), [('A', epoch(*civil_from_days(cut_day)), b)], {'reused_new'}, ('xwalk', other['svc'])))
        W.xwalk.setdefault(s['svc'], []).append((f, HIST_DAY - 300, cut_day))
        W.xwalk.setdefault(other['svc'], []).append((f, cut_day, None))
    return out

def legacy_id(W, rng, svc, at):
    z = at // DAY
    opts = [f for f, vf, vt in W.xwalk.get(svc, []) if vf <= z and (vt is None or z < vt)]
    return rng.pick(opts) if opts else None

def inforce_index(revs):
    """Index of the revision in force at the cut (close_contract.md section 4), or None."""
    best = None
    for i, r in enumerate(revs):
        if r['rec_at'] >= CUT or r['st'] == 'D':
            continue
        if best is None or r['rev'] > revs[best]['rev']:
            best = i
    return best

def assign_errata(W, C, rng, ids):
    """Errata entries against the other exports: corrections, voids of duplicates, unapproved and late errata."""
    out = []
    subjects = []
    for fname in FILE_NAMES:
        if fname in ERRATA_SKIP:
            continue
        for table, recs in C.recs[fname].items():
            n = len(recs)
            k = max(2, round(n * 0.013))
            cnt = {}
            for r in recs:
                cnt[r['rid']] = cnt.get(r['rid'], 0) + 1
            cand = [r for r in recs if cnt[r['rid']] == 1 and inforce_index(r['revs']) is not None and (r['revs'][inforce_index(r['revs'])]['st'] == 'A')]
            for r in rng.sample(cand, min(k, len(cand))):
                i = inforce_index(r['revs'])
                p = r['revs'][i]['p']
                fields = [(nm, kd) for nm, kd in mutable_fields(fname, table) if nm not in ERRATA_NOFIELD.get(fname, set()) and p.get(nm) is not None and (not isinstance(p.get(nm), Sentinel)) and (kd != 'enum:eco') and (kd != 'text')]
                if not fields:
                    continue
                nm, kd = rng.pick(fields)
                x = rng.below(100)
                eid = ids('er')
                if x < 42:
                    truth = p[nm]
                    wrong = mutate(rng, kd, truth)
                    if wrong == truth:
                        continue
                    newp = dict(p)
                    newp[nm] = wrong
                    r['revs'][i]['p'] = newp
                    at = nudge(gen_time(rng, max(r['revs'][i]['rec_at'], HIST_START) + 3600, CUT - 3600 * 5)) if r['revs'][i]['rec_at'] < CUT - 3600 * 8 else None
                    if at is None:
                        r['revs'][i]['p'] = p
                        continue
                    out.append(rec(eid, [('A', at, {'file': fname, 'target': r['rid'], 'action': 'correct', 'field': nm, 'value': canon_str(kd, truth), 'issued': at})], {'err_correct'}, ('errata', fname, r['rid'])))
                    r['tags'].add('errata_corrected')
                    subjects.append((eid, 'approve', at))
                elif x < 60:
                    dup = rec(ids('dupx'), [(rv['st'], rv['rec_at'], rv['p']) for rv in r['revs']], {'duplicate'}, None)
                    dup['rid'] = r['rid'][:3] + f'{900000 + rng.below(99999):06d}'
                    if any((z['rid'] == dup['rid'] for z in recs)):
                        continue
                    recs.append(dup)
                    at = nudge(gen_time(rng, max(r['revs'][0]['rec_at'], HIST_START) + 3600, CUT - 3600 * 5)) if r['revs'][0]['rec_at'] < CUT - 3600 * 8 else None
                    if at is None:
                        recs.pop()
                        continue
                    out.append(rec(eid, [('A', at, {'file': fname, 'target': dup['rid'], 'action': 'void', 'field': None, 'value': None, 'issued': at})], {'err_void'}, ('errata', fname, dup['rid'])))
                    dup['tags'].add('errata_voided')
                    subjects.append((eid, 'approve', at))
                elif x < 85:
                    wrong = mutate(rng, kd, p[nm])
                    at = nudge(gen_time(rng, HIST_START + DAY, CUT - DAY))
                    out.append(rec(eid, [('A', at, {'file': fname, 'target': r['rid'], 'action': 'correct', 'field': nm, 'value': canon_str(kd, wrong), 'issued': at})], {'err_unapproved'}, ('errata', fname, r['rid'])))
                    subjects.append((eid, rng.pick(['reject', 'defer', None]), at))
                else:
                    wrong = mutate(rng, kd, p[nm])
                    at = nudge(gen_time(rng, CUT, LATE_END - DAY))
                    out.append(rec(eid, [('A', at, {'file': fname, 'target': r['rid'], 'action': 'correct', 'field': nm, 'value': canon_str(kd, wrong), 'issued': at})], {'err_postcut'}, ('errata', fname, r['rid'])))
                    subjects.append((eid, 'approve', at))
    return (out, subjects)

def build_minutes(W, rng, ids, subjects):
    out = []
    chairs = ['R. Iyer', 'L. Moreau', 'K. Tanaka', "D. O'Neill", 'S. Brandt']

    def add(subject, decision, at, tags):
        payload = {'subject': subject, 'decision': decision, 'decided': at, 'chair': rng.pick(chairs)}
        out.append(rec(ids('mn'), [('A', at, payload)], tags, ('minute', subject)))
    for sid, dec, at in subjects:
        if dec is None:
            continue
        if dec == 'approve' and rng.chance(0.2) and (at > HIST_START + 10 * DAY):
            add(sid, 'defer', nudge(at - rng.rint(1, 5) * DAY), {'minute_deferred_then'})
        add(sid, dec, at, {'minute_' + dec})
    for o in W.overrides:
        if o['approved']:
            add(o['oid'], 'approve', o['decided'], {'minute_approve'})
        else:
            x = rng.below(3)
            if x == 0:
                add(o['oid'], rng.pick(['reject', 'defer']), o['decided'], {'minute_reject'})
            elif x == 1:
                add(o['oid'], 'approve', nudge(gen_time(rng, CUT, LATE_END - DAY)), {'minute_late'})
    for w in W.waivers:
        if w['approved']:
            add(w['wid'], 'approve', w['decided'], {'minute_approve' if w['decided'] < CUT else 'minute_late'})
        elif rng.chance(0.6):
            add(w['wid'], rng.pick(['reject', 'defer']), w['decided'], {'minute_reject'})
    for rid in W.noise_overrides[:len(W.noise_overrides) // 8]:
        add(rid, rng.pick(['reject', 'defer']), nudge(gen_time(rng, Q_START - 60 * DAY, CUT - DAY)), {'minute_reject'})
    return out
AMEND_FILES = ['advisory_rescores.parquet', 'remediation_timesheets.csv', 'ledger_journal.db', 'waivers.db', 'vex_statements.xml', 'lock_overrides.toml']

class Corpus:
    pass

def fx_at(W, cur, t):
    if cur == 'EUR':
        return D(1)
    best = None
    for at, rate in W.fx[cur]:
        if at <= t and at < CUT:
            best = rate
        else:
            break
    return best

def rate_of(W, eng, t):
    y, m, d = civil_from_days(t // DAY)
    e = W.eng_by[eng]
    mo = m if (y, m) in ((2025, 7), (2025, 8), (2025, 9)) else 9 if (y, m) > (2025, 9) else 7
    return e['rates'][mo]

def to_cents(minor, cur, rate):
    major = D(minor) / D(10) ** CUR_EXP[cur]
    return int(q(major * rate * 100, 0))

def ts_cents(W, ts):
    cur, minor = rate_of(W, ts['eng'], ts['worked'])
    major_rate = D(minor) / D(10) ** CUR_EXP[cur]
    return -int(q(D(ts['hours']) * major_rate * fx_at(W, cur, ts['worked']) * 100, 0))

def seg_team(W, eng, t):
    z = t // DAY
    for sg in W.eng_by[eng]['segs']:
        if seg_covers(sg, z) and sg.get('rec_at', 0) < CUT:
            return sg['team']
    return None

def capacity(W, team):
    if W.team_by[team]['model'] == 'uncapped':
        return None
    tot = D(0)
    for e in W.engineers:
        for sg in e['segs']:
            if sg['team'] != team:
                continue
            a = max(sg['start'], Q_START_DAY)
            b = min(sg['end'] if sg['end'] is not None else CUT_DAY, CUT_DAY)
            if b > a:
                tot += sg['fte'] * D(8) * D(weekdays_between(a, b)) * (D(1) - sg['oncall'])
    return int(q(tot, 0, 'floor'))

def withdraw_vulns(W, seed, keep):
    """Withdraw (before the cut) every vulnerability except a seeded share `keep`, for the certification-branch corpora."""
    r = Rng(seed)
    for v in W.vulns:
        if r.chance(keep) or (v['withdrawn'] is not None and v['withdrawn'] < CUT) or v['pub'] >= CUT:
            continue
        at = nudge(v['pub'] + DAY) if v['pub'] + DAY < CUT - 6 * 3600 else v['pub'] + 60
        if at < CUT:
            v['withdrawn'] = at


def assemble(seed, scale, keep_vulns=None):
    rng = Rng(derive(seed, 'world'))
    W = build_world(derive(seed, 'entities'), scale)
    if keep_vulns is not None:
        withdraw_vulns(W, derive(seed, 'keep'), keep_vulns)
    finish_world(W, rng.fork('finish'))
    T = compute_truth(W, rng.fork('truth'))
    finish_dispositions(W, T, rng.fork('disp'))
    complete_truth(W, T)
    C = Corpus()
    C.W, C.T, C.seed, C.scale = (W, T, seed, scale)
    ids = Ids(rng.fork('ids'))
    refs = Refs(W, rng.fork('refs'))
    r = rng.fork('records')
    target = max(400, round(10080 * scale))
    spell = spelling_aliases(W, r, refs)
    reg, notice_events = build_registries(W, T, r, ids, refs)
    C.recs = {}
    for f, recs in reg.items():
        C.recs[f] = {'releases': recs}
    C.recs['registry_mirror.parquet'] = {'mirror': build_mirror(W, T, r, ids, target)}
    al, lg = build_aliases(W, T, r, ids, refs, spell)
    C.recs['name_aliases.tsv'] = {'aliases': al}
    C.recs['name_aliases_legacy.tsv'] = {'aliases': lg}
    C.recs['yank_notices.mbox'] = {'notices': build_notices(W, T, r, ids, notice_events, refs)}
    C.recs['package_owners.json'] = {'owners': build_owners(W, T, r, ids, refs)}
    man, snap = build_manifests(W, T, r, ids, refs)
    for f, recs in man.items():
        C.recs[f] = {'declarations': recs}
    C.recs['manifests_snapshot.csv'] = {'declarations': snap}
    C.recs['lock_overrides.toml'] = {'overrides': build_overrides(W, T, r, ids, refs, target)}
    C.recs['scanner_findings.jsonl'] = {'findings': build_scanner(W, T, r, ids, refs)}
    cat, fin = build_catalog(W, T, r, ids)
    C.recs['service_catalog.xlsx'] = cat
    C.recs['service_catalog_final.xlsx'] = fin
    logs = build_deploys(W, T, r, ids)
    for f, recs in logs.items():
        C.recs[f] = {'deploys': recs}
    C.recs['clock_offsets.txt'] = {'offsets': build_offsets(W, r, ids)}
    C.recs['change_freeze.ics'] = {'windows': build_freeze(W, r, ids)}
    osv, replay = build_osv(W, T, r, ids, refs)
    C.recs['advisories_osv.jsonl'] = {'osv': osv}
    C.recs['advisories_osv_replay.jsonl'] = {'osv': replay}
    gh, cache = build_ghsa(W, T, r, ids, refs)
    C.recs['advisories_ghsa.json'] = {'ghsa': gh}
    C.recs['advisories_feed_cache.json'] = {'cache': cache}
    C.recs['advisories_nvd.xml'] = {'nvd': build_nvd(W, T, r, ids)}
    C.recs['advisory_aliases.csv'] = {'aliases': build_vuln_aliases(W, T, r, ids)}
    C.recs['advisory_rescores.parquet'] = {'rescores': build_rescores(W, T, r, ids, refs)}
    C.recs['precedence.yaml'] = {'authority': build_authority(W, T, r, ids, refs)}
    C.recs['vex_statements.xml'] = {'vex': build_vex(W, T, r, ids, refs)}
    C.recs['waivers.db'] = {'waivers': build_waivers(W, T, r, ids, refs)}
    C.recs['license_scan.parquet'] = {'scans': build_license_scan(W, T, r, ids, refs, target)}
    C.recs['license_overrides.csv'] = {'overrides': build_license_overrides(W, T, r, ids, refs, target)}
    C.recs['license_policy.md'] = {'exceptions': build_license_exceptions(W, T, r, ids, refs, target)}
    C.recs['engineer_roster.ini'] = build_roster(W, T, r, ids)
    C.recs['engineer_rates.xlsx'] = build_rates(W, r, ids)
    C.recs['fx_fixings.tsv'] = {'fixings': build_fx(W, r, ids)}
    C.recs['remediation_timesheets.csv'] = {'timesheets': build_timesheets(W, T, r, ids, refs)}
    C.recs['ledger_journal.db'] = {'entries': build_journal(W, T, r, ids)}
    C.recs['scoring_methodology.pdf'] = {'factors': build_factors(W, r, ids, refs, target)}
    C.recs['sla_policy.pdf'] = {'sla_overrides': build_sla(W, r, ids, target)}
    C.recs['remediation_estimates.xlsx'] = build_estimates(W, r, ids, refs, max(250, target // 4 + 60))
    C.recs['close_contract.md'] = {'crosswalk': build_crosswalk(W, r, ids)}
    err, subjects = assign_errata(W, C, r, ids)
    C.recs['errata_register.docx'] = {'errata': err}
    C.recs['review_minutes.docx'] = {'minutes': build_minutes(W, r, ids, subjects)}
    finish_reference(W, T)
    C.recs['control_totals.html'] = {'controls': build_controls(C, r, ids)}
    C.recs['source_conventions.html'] = {'register': []}
    return C

def finish_reference(W, T):
    rows = []
    for key in sorted(T.pk):
        info = T.pk[key]
        rels = [r for r in info['rels'] if not r['quarantine'] and r['pub'] < CUT]
        if not rels:
            continue
        yk = [r for r in rels if yanked_at(r, CUT)]
        stable = [r for r in rels if r['ver'].pre is None and (not yanked_at(r, CUT))]
        latest = max(stable, key=lambda r: r['ver'].key()) if stable else None
        owner = None
        if key in W.pkg_by and W.pkg_by[key]['internal']:
            owner = team_at(W.pkg_by[key]['owners'], CUT)
        lic = None
        if latest is not None:
            lic = lic_expr(W, W.pkg_by[key], latest) if key in W.pkg_by else canon_spdx(latest['lic'])
        rows.append({'package': key, 'ecosystem': info['eco'], 'owner_team': owner, 'releases': len(rels), 'yanked': len(yk), 'latest': latest['ver'] if latest else None, 'latest_license': lic, 'obligation': lic_class(W, key, latest['ver'], lic) if latest else None})
    T.packages_rows = rows
    T.teams_rows = []
    for t in sorted(W.teams, key=lambda x: x['team']):
        engs = set()
        for e in W.engineers:
            for sg in e['segs']:
                if sg['team'] == t['team'] and sg['start'] < CUT_DAY and (sg['end'] is None or sg['end'] > Q_START_DAY):
                    engs.add(e['eng'])
        T.teams_rows.append({'team': t['team'], 'model': t['model'], 'capacity_hours': capacity(W, t['team']), 'engineers': len(engs)})
    entries, deferred_cents = ([], [])
    for ts in W.timesheets:
        team = seg_team(W, ts['eng'], ts['worked'])
        amt = ts_cents(W, ts)
        e = {'entry': ts['rid'], 'team': team, 'source': 'remediation_timesheets.csv', 'booked': ts['worked'], 'amount_cents': amt}
        if ts['worked'] < CUT and team is not None:
            entries.append(e)
    rev_pairs = set()
    for j in W.journal:
        if j['kind'] == 'reversal' and j['booked'] < CUT:
            rev_pairs.add(j['rid'])
            rev_pairs.add(j['reverses']['rid'])
    T.rev_excluded = rev_pairs
    openings = []
    for j in W.journal:
        if j['booked'] >= CUT or j['rid'] in rev_pairs:
            continue
        cents = to_cents(j['minor'], j['cur'], fx_at(W, j['cur'], j['booked']))
        if j['kind'] == 'opening':
            openings.append({'entry': j['rid'], 'team': j['team'], 'amount_cents': cents})
        else:
            entries.append({'entry': j['rid'], 'team': j['team'], 'source': 'ledger_journal.db', 'booked': j['booked'], 'amount_cents': cents})
    T.openings = sorted(openings, key=lambda e: e['team'])
    T.entries = sorted(entries, key=lambda e: (e['booked'], e['entry']))
    clos = {o['team']: o['amount_cents'] for o in T.openings}
    for e in T.entries:
        clos[e['team']] = clos.get(e['team'], 0) + e['amount_cents']
    T.closings = [{'team': t, 'amount_cents': clos.get(t, 0)} for t in sorted(W.team_ids)]
    hi = [e for e in T.exposures if e['status'] == 'open' and e['severity'] in ('critical', 'high')]
    T.pool_hours = int(q(POOL_SHARE * sum((e['estimate'] for e in hi), D(0)), 0))

def build_controls(C, rng, ids):
    W, T = (C.W, C.T)
    vals = []
    openx = [e for e in T.exposures if e['status'] == 'open']
    by_svc, by_pkg, by_team = ({}, {}, {})
    owner = {r['service']: r['team'] for r in T.services_rows}
    for e in openx:
        by_svc[e['service']] = by_svc.get(e['service'], 0) + 1
        by_pkg[e['package']] = by_pkg.get(e['package'], 0) + 1
        by_team[owner[e['service']]] = by_team.get(owner[e['service']], 0) + 1
    pins = {}
    for p in T.pins:
        if p['scope'] == 'runtime' and p['pinned'] is not None:
            pins[p['service']] = pins.get(p['service'], 0) + 1
    clos = {c['team']: c['amount_cents'] for c in T.closings}
    for t in T.teams_rows:
        vals.append((t['team'], 'open_exposures', by_team.get(t['team'], 0)))
        vals.append((t['team'], 'closing_cents', clos.get(t['team'], 0)))
        if t['capacity_hours'] is not None:
            vals.append((t['team'], 'capacity_hours', t['capacity_hours']))
    vals.append(('global', 'pool_hours', T.pool_hours))
    vals.append(('global', 'total_open', len(openx)))
    vals.append(('global', 'waived_total', sum((1 for e in T.exposures if e['status'] == 'waived'))))
    out = []
    T.controls_truth = {}
    for scope, measure, v in vals:
        cid = ids('ct')
        published = v
        tags = {'control'}
        if measure not in ('pool_hours',) and rng.chance(0.03):
            published = v + rng.pick([-3, -2, -1, 1, 2, 5]) * (100 if measure == 'closing_cents' else 1)
            tags.add('stale_control')
        signed = nudge(gen_time(rng, CUT - 9 * DAY, CUT - 3600 * 6))
        payload = {'control': cid, 'scope': scope, 'measure': measure, 'value': published, 'signed': signed}
        revs, st = wrap(rng, 'control_totals.html', 'controls', payload, signed, story=rng.wpick(['plain', 'superseded', 'draft', 'postcut'], [60, 20, 10, 10]), exclude=('signed', 'measure'))
        out.append(rec(cid, revs, st | tags, ('control', scope, measure)))
        T.controls_truth[cid] = {'scope': scope, 'measure': measure, 'value': published, 'true': v}
    return out
SYN = {'rid': ['rid', 'id', 'rk', 'key'], 'rev': ['rev', 'r', 'rv', 'ver_no'], 'st': ['st', 's', 'state', 'flag'], 'rec_at': ['rec', 'ts', 'rt', 'logged'], 'name': ['pkg', 'nm', 'pk', 'pname'], 'version': ['ver', 'v', 'vr', 'release'], 'published': ['pub', 'rel', 'pb', 'out_at'], 'yanked': ['yank', 'ynk', 'yk', 'pulled'], 'service': ['svc', 'sv', 'srv', 'app'], 'constraint': ['req', 'spec', 'rng', 'want'], 'scope': ['scp', 'sc', 'use', 'kind_of'], 'locked': ['lock', 'lk', 'lkd', 'pinned_at'], 'eco': ['eco', 'ec', 'eh', 'repo'], 'host': ['host', 'col', 'hs', 'node'], 'outcome': ['out', 'res', 'oc', 'status_of'], 'at': ['at', 'clk', 'ct', 'when'], 'hours': ['hrs', 'dur', 'hr', 'spent'], 'worked': ['wkd', 'w_at', 'wk', 'on'], 'vuln': ['vid', 'adv', 'vu', 'issue'], 'vector': ['vec', 'cv', 'vc', 'metric'], 'events': ['evt', 'rng_ev', 'ev', 'span'], 'withdrawn': ['wdn', 'w_dn', 'wd', 'retired'], 'rate': ['rt_v', 'fix', 'rate_v', 'px'], 'currency': ['cur', 'ccy', 'cy', 'unit'], 'alias': ['al', 'alt', 'as', 'other'], 'target': ['tgt', 'to', 'tg', 'dest'], 'kind': ['knd', 'k', 'kd', 'class_of'], 'effective': ['eff', 'ef', 'ev_at', 'from_ts'], 'offset': ['off', 'skew', 'dt', 'delta'], 'day': ['day', 'd', 'dy', 'date_of'], 'note': ['note', 'nt', 'memo', 'txt'], 'a': ['a', 'x', 'left', 'one'], 'b': ['b', 'y', 'right', 'two'], 'order': ['ord', 'auth', 'seq_of', 'prec'], 'field': ['fld', 'f', 'fd', 'attr'], 'osv': ['osv', 'o', 'os', 'osv_ref'], 'ghsa': ['gh', 'g', 'gs', 'gh_ref'], 'cve': ['cve', 'c', 'cv_id', 'cve_ref'], 'source': ['src', 'so', 'sr', 'origin'], 'modified': ['mod', 'm', 'md', 'chg'], 'seen': ['seen', 'sn', 'obs', 'scan_at'], 'image': ['img', 'im', 'ref_img', 'oci'], 'action': ['act', 'ac', 'op', 'verb'], 'ref': ['ref', 'rf', 'link', 'about'], 'team': ['tm', 'team_id', 'grp', 'unit_id'], 'role': ['role', 'rl', 'as_role', 'duty'], 'valid_from': ['vf', 'from', 'beg', 'since'], 'valid_to': ['vt', 'until', 'fin', 'upto'], 'reviewed': ['rvw', 'rv_ok', 'chk', 'vetted'], 'score': ['scr', 'sco', 'pts', 'base'], 'fetched': ['ftc', 'fe', 'pull_at', 'got'], 'quarantined': ['qr', 'qa', 'blk', 'held'], 'license': ['lic', 'li', 'lc', 'terms'], 'status': ['sts', 'stat', 'sta', 'state_of'], 'justification': ['jst', 'why', 'just', 'basis'], 'issued': ['iss', 'is', 'isd', 'made'], 'granted': ['gr', 'grn', 'gt', 'given'], 'expires': ['exp', 'ex', 'xp', 'ends'], 'approver': ['apr', 'by', 'who', 'signer'], 'approved': ['ok', 'apv', 'acc', 'passed'], 'scored': ['scd', 'sd', 'sco_at', 'rated'], 'engineer': ['eng', 'en', 'emp', 'person'], 'fte': ['fte', 'load', 'share_of', 'pct_fte'], 'oncall': ['onc', 'oc_share', 'pager', 'duty_share'], 'start': ['start', 'beg_d', 'st_d', 'from_d'], 'end': ['end', 'fin_d', 'to_d', 'stop'], 'month': ['mon', 'mo', 'period', 'mth'], 'expression': ['expr', 'lic_expr', 'spdx', 'ex_l'], 'range': ['rng_l', 'ver_range', 'span_l', 'applies'], 'class': ['cls', 'cl', 'grade', 'cat'], 'revoked': ['rvk', 'revk', 'rv_d', 'pulled_d'], 'decided': ['dec', 'dcd', 'decided_at', 'ruled'], 'major': ['maj', 'mj', 'line', 'major_v'], 'factor': ['fac', 'fct', 'mult', 'coef'], 'severity': ['sev', 'sv_l', 'level', 'grade_s'], 'days': ['days', 'dd', 'n_days', 'limit']}
SENT_TOKENS = {'unknown': ['?', 'N/A', 'unknown', 'n.a.'], 'none': ['-', 'none', 'nil', '~'], 'elsewhere': ['see-replay', '->cache', '(deferred)', '@ext']}
TS_UNKNOWN_TOKEN = '0000-00-00 00:00:00'
NEG_NAME = {'yanked': 'listed', 'quarantined': 'cleared', 'reviewed': 'unreviewed', 'approved': 'pending'}

def topup(C, rng, ids, fname, target):
    tables = C.recs[fname]
    total = sum((len(r['revs']) for recs in tables.values() for r in recs))
    hist = fname in REG_FILE.values()
    names = list(tables)
    guard = 0
    seen_r, dup_rids = (set(), set())
    for recs in tables.values():
        for r in recs:
            if r['rid'] in seen_r:
                dup_rids.add(r['rid'])
            seen_r.add(r['rid'])
    while total < target and guard < target * 4:
        guard += 1
        t = rng.pick(names)
        recs = tables[t]
        if not recs:
            continue
        r = rng.pick(recs)
        i = inforce_index(r['revs'])
        if i is None or r['rid'] in dup_rids:
            continue
        base = r['revs'][i]
        mf = [x for x in mutable_fields(fname, t) if x[1] != 'enum:eco' and x[0] not in ERRATA_NOFIELD.get(fname, set())]
        if fname == 'source_conventions.html':
            mf = [('conv', 'text')]
        elif any((k != 'text' for _, k in mf)):
            mf = [x for x in mf if x[1] != 'text']
        if not mf:
            mf = [x for x in payload_fields(fname, t) if group_of(x[1]) in ('ts', 'int', 'dec', 'bool')]
        if not mf and fname == 'advisory_aliases.csv' and (base['st'] != 'A'):
            continue
        if not mf and fname == 'advisory_aliases.csv':
            nr = rec(r['rid'][:3] + f'{700000 + rng.below(99999):06d}', [('A', base['rec_at'] + 60 * rng.rint(1, 600), dict(base['p']))], {'alias_dup'})
            if not any((z['rid'] == nr['rid'] for z in recs)):
                recs.append(nr)
                total += 1
            continue
        if not mf:
            break
        n, k = rng.pick(mf)
        w = dict(base['p'])
        if w.get(n) is None or isinstance(w.get(n), Sentinel):
            continue
        w[n] = mutate(rng, k, w[n])
        x = rng.below(100)
        if x < 40 and (not hist) and (base['rec_at'] > HIST_START + 3 * DAY):
            early = nudge(max(HIST_START, base['rec_at'] - rng.rint(1, 30) * DAY))
            r['revs'].insert(0, {'rev': 0, 'st': 'A', 'rec_at': min(early, base['rec_at'] - 60), 'p': w})
            for j, rv in enumerate(r['revs'], start=1):
                rv['rev'] = j
            r['tags'].add('superseded')
        elif x < 72:
            last = max((rv['rec_at'] for rv in r['revs'] if rv['rec_at'] < CUT)) if any((rv['rec_at'] < CUT for rv in r['revs'])) else base['rec_at']
            d_at = nudge(min(CUT - 3600 * 3, last + rng.rint(1, 15) * DAY))
            r['revs'].append({'rev': len(r['revs']) + 1, 'st': 'D', 'rec_at': max(d_at, last), 'p': w})
            r['tags'].add('draft')
        elif x < 92:
            r['revs'].append({'rev': len(r['revs']) + 1, 'st': 'A', 'rec_at': nudge(gen_time(rng, CUT, LATE_END - DAY)), 'p': w})
            r['tags'].add('postcut')
        else:
            at = base['rec_at'] if base['rec_at'] < CUT - 10 * DAY else nudge(CUT - 20 * DAY)
            revs, tg = fake(rng, fname, t, w, at)
            nr = rec(ids('fk' + fname[:2]), revs, tg | {'fake'})
            nr['rid'] = r['rid'][:3] + f'{800000 + rng.below(99999):06d}'
            if any((z['rid'] == nr['rid'] for z in recs)):
                continue
            recs.append(nr)
            total += 2
            continue
        total += 1

def trim(C, rng, fname, limit):
    """Drop draft and post-cut revisions of multi-revision records until the export is near its target size."""
    tables = C.recs[fname]
    total = sum((len(r['revs']) for recs in tables.values() for r in recs))
    if total <= limit:
        return
    cands = []
    for t, recs in tables.items():
        for r in recs:
            if len(r['revs']) < 2:
                continue
            for rv in r['revs']:
                if rv['st'] == 'D' or rv['rec_at'] >= CUT:
                    cands.append((r, rv))
    rng.shuffle(cands)
    for r, rv in cands:
        if total <= limit:
            break
        if len(r['revs']) < 2 or rv not in r['revs']:
            continue
        r['revs'].remove(rv)
        total -= 1

def place(C, rng, fname):
    """Order every record of a table: plain records at head and tail, story records in the middle."""
    out = {}
    for t, recs in C.recs[fname].items():
        plain = [r for r in recs if r['tags'] <= {'plain', 'control', 'osv', 'yank_notice', 'approved', 'unapproved', 'alias_pair', 'owner', 'spelling', 'factor', 'exception', 'override', 'minute_approve', 'mirror_copy', 'legacy_copy', 'snapshot_copy', 'final_copy', 'replay_copy', 'cache_copy', 'scanner_copy'}]
        story = [r for r in recs if not r['tags'] <= {'plain', 'control', 'osv', 'yank_notice', 'approved', 'unapproved', 'alias_pair', 'owner', 'spelling', 'factor', 'exception', 'override', 'minute_approve', 'mirror_copy', 'legacy_copy', 'snapshot_copy', 'final_copy', 'replay_copy', 'cache_copy', 'scanner_copy'}]
        rng.shuffle(plain)
        rng.shuffle(story)
        nlines = sum((len(r['revs']) for r in recs))
        edge = int(nlines * 0.16)
        head, tail, mid = ([], [], [])
        hn = tn = 0
        for r in plain:
            if hn < edge:
                head.append(r)
                hn += len(r['revs'])
            elif tn < edge:
                tail.append(r)
                tn += len(r['revs'])
            else:
                mid.append(r)
        mid += story
        rng.shuffle(mid)
        out[t] = head + mid + tail
    return out

def batch_plan(C, rng, fname):
    fmt = FILES[fname][0]
    C.batches[fname] = []
    k = 0
    for t, recs in C.placed[fname].items():
        lines = [(r, i) for r in recs for i in range(len(r['revs']))]
        n = len(lines)
        nb = max(3, min(48, round(n / 300)))
        size = -(-n // nb)
        fields = fields_of(fname, t)
        for b in range(nb):
            chunk = lines[b * size:(b + 1) * size]
            if not chunk:
                continue
            k += 1
            lab = f'{FILES[fname][0][:1].upper()}{k:03d}'
            edge = b < max(1, nb // 6) or b >= nb - max(1, nb // 6)
            conv, names, order = ({}, {}, [f for f, _ in fields])
            for fn, kd in fields:
                opts = conv_options(fmt, kd, fname)
                if fname in CANON_FILES or not opts:
                    conv[fn] = FACE.get(group_of(kd), ENUM_FACE)
                    continue
                if fn == 'offset':
                    opts = ['plain', 'neg', 'grouped']
                face = FACE.get(group_of(kd), ENUM_FACE)
                if edge:
                    pool = [o for o in opts if o != face][:2] or [face]
                    conv[fn] = rng.pick(pool + [face])
                else:
                    alts = [o for o in opts if o != face] or [face]
                    if group_of(kd) == 'ts':
                        alts = ['epoch', 'epoch', 'epochms', 'xl:UTC', 'xl:IE', 'xl:US', 'xl4:UTC', 'dmy:IE', 'dmy:IN', 'mdy:US', 'naive:IE', 'naive:US', 'naive:IN', 'naive:JP', 'naive:AU', 'naive:UTC', rng.pick([o for o in alts if o.startswith('off:')])]
                        alts = [o for o in alts if o in opts]
                    conv[fn] = face if rng.chance(0.3) else rng.pick(alts)
            if edge and fname not in CANON_FILES:
                coded = [(fn, kd) for fn, kd in fields if conv_options(fmt, kd, fname) and fn not in ('rid', 'rev')]
                focus = coded[k * 7 % len(coded)][0] if coded else None
                for fn, kd in fields:
                    face = FACE.get(group_of(kd), ENUM_FACE)
                    conv[fn] = face
                if focus:
                    kd = dict(fields)[focus]
                    alts = [o for o in conv_options(fmt, kd, fname) if o != FACE.get(group_of(kd), ENUM_FACE)]
                    if group_of(kd) == 'ts':
                        alts = [o for o in alts if o.startswith(('naive', 'xl', 'dmy', 'mdy'))] or alts
                    conv[focus] = alts[k * 3 % len(alts)] if alts else conv[focus]
            if fmt not in NO_LAYOUT and fname not in CANON_FILES and (not edge):
                order = [f for f, _ in fields]
                if rng.chance(0.75):
                    head = order[:4]
                    rest = order[4:]
                    rng.shuffle(rest)
                    order = head + rest if rng.chance(0.6) else rng.shuffle(list(order))
                used = set()
                for fn, kd in fields:
                    if conv.get(fn) == 'neg':
                        nm = NEG_NAME.get(fn, 'not_' + fn)
                    else:
                        nm = rng.pick(SYN.get(fn, [fn])) if rng.chance(0.8) else fn
                    if nm in used or nm in ('batch',):
                        nm = fn
                    used.add(nm)
                    names[fn] = nm
            else:
                for fn, kd in fields:
                    names[fn] = fn
            for fn, kd in fields:
                if conv.get(fn) == 'neg' and fn not in names:
                    names[fn] = NEG_NAME.get(fn, 'not_' + fn)
            sent = {}
            for r, i in chunk:
                for fn, kd in fields:
                    v = r['revs'][i]['p'].get(fn) if fn not in ('rid', 'rev', 'st', 'rec_at') else None
                    if isinstance(v, Sentinel) and (fn, v.meaning) not in sent:
                        if fname in CANON_FILES:
                            sent[fn, v.meaning] = '@' + v.meaning
                        elif group_of(kd) == 'ts' and v.meaning == 'unknown' and rng.chance(0.5):
                            sent[fn, v.meaning] = TS_UNKNOWN_TOKEN
                        else:
                            sent[fn, v.meaning] = rng.pick(SENT_TOKENS[v.meaning])
            C.batches[fname].append({'label': lab, 'table': t, 'rows': chunk, 'conv': conv, 'names': names, 'order': order, 'sent': sent})

def inforce_counts(C, fname):
    """(records, in_force) of a file under the generator's knowledge of approved errata."""
    lines = sum((len(r['revs']) for recs in C.recs[fname].values() for r in recs))
    n = 0
    for t, recs in C.recs[fname].items():
        byrid = {}
        for r in recs:
            byrid.setdefault(r['rid'], r)
        for rid, r in byrid.items():
            i = inforce_index(r['revs'])
            if i is None or r['revs'][i]['st'] == 'V':
                continue
            if (fname, rid) in C.err_void:
                continue
            n += 1
    return (lines, n)

def approved_subjects(C):
    best = {}
    for r in C.recs['review_minutes.docx']['minutes']:
        i = inforce_index(r['revs'])
        if i is None or r['revs'][i]['st'] == 'V':
            continue
        p = r['revs'][i]['p']
        if p['decided'] >= CUT:
            continue
        k = p['subject']
        if k not in best or (p['decided'], r['rid']) > best[k][0]:
            best[k] = ((p['decided'], r['rid']), p['decision'])
    return {k for k, (_, d) in best.items() if d == 'approve'}

def errata_index(C):
    ok = approved_subjects(C)
    C.approved = ok
    voids, corr = (set(), {})
    rows = []
    for r in C.recs['errata_register.docx']['errata']:
        i = inforce_index(r['revs'])
        if i is None or r['revs'][i]['st'] == 'V':
            continue
        p = r['revs'][i]['p']
        if p['issued'] >= CUT or r['rid'] not in ok:
            continue
        rows.append((p['issued'], r['rid'], p))
    for _, _, p in sorted(rows, key=lambda x: (x[0], x[1])):
        if p['action'] == 'void':
            voids.add((p['file'], p['target']))
        else:
            corr.setdefault((p['file'], p['target']), {})[p['field']] = p['value']
    C.err_void, C.err_corr = (voids, corr)

def build_register(C, rng, ids):
    out = []
    for fname in FILE_NAMES:
        if fname in CANON_FILES:
            continue
        fmt = FILES[fname][0]
        for b in C.batches[fname]:
            at = nudge(gen_time(rng, HIST_START, Q_START - 10 * DAY))
            fields = fields_of(fname, b['table'])
            for fn, kd in fields:
                face = FACE.get(group_of(kd), ENUM_FACE)
                cv = b['conv'][fn]
                if cv == face:
                    if rng.chance(0.03):
                        wrong = rng.pick([o for o in conv_options(fmt, kd, fname) if o != face] or [face])
                        if wrong != face:
                            revs, tg = fake(rng, 'source_conventions.html', 'register', {'file': fname, 'batch': b['label'], 'field': fn, 'conv': wrong, 'token': None}, at)
                            out.append(rec(ids('cv'), revs, tg | {'reg_fake'}, ('reg', fname, b['label'])))
                    continue
                p = {'file': fname, 'batch': b['label'], 'field': fn, 'conv': cv, 'token': None}
                opts = [o for o in conv_options(fmt, kd, fname) if o != cv]
                x = rng.below(100)
                kind_tag = group_of(kd)
                if x < 30 and opts:
                    revs = [('A', at - 5 * DAY, dict(p, conv=rng.pick(opts))), ('A', at, p)]
                    tg = {'reg_superseded', 'reg_kind:' + kind_tag}
                elif x < 50 and opts:
                    revs = [('A', at, p), ('D', at + 2 * DAY, dict(p, conv=rng.pick(opts)))]
                    tg = {'reg_draft', 'reg_kind:' + kind_tag}
                elif x < 70 and opts:
                    revs = [('A', at, p), ('A', nudge(gen_time(rng, CUT, LATE_END - DAY)), dict(p, conv=rng.pick(opts)))]
                    tg = {'reg_postcut', 'reg_kind:' + kind_tag}
                else:
                    revs, tg = ([('A', at, p)], {'reg_conv'})
                out.append(rec(ids('cv'), revs, tg, ('reg', fname, b['label'])))
            if fmt not in NO_LAYOUT:
                p = {'file': fname, 'batch': b['label'], 'field': '@layout', 'conv': ','.join(b['order']), 'token': ','.join((b['names'][f] for f in b['order']))}
                out.append(rec(ids('cv'), [('A', at, p)], {'reg_layout'}, ('reg', fname, b['label'])))
            for (fn, meaning), tok in sorted(b['sent'].items()):
                p = {'file': fname, 'batch': b['label'], 'field': fn, 'conv': '@' + meaning, 'token': tok}
                out.append(rec(ids('cv'), [('A', at, p)], {'reg_sentinel'}, ('reg', fname, b['label'])))
    return out

def plan_corpus(C):
    rng = Rng(derive(C.seed, 'plan'))
    ids = Ids(rng.fork('ids2'))
    target = max(400, round(10080 * C.scale))
    C.batches, C.placed = ({}, {})
    early = [f for f in FILE_NAMES if f not in ('control_totals.html', 'source_conventions.html')]
    for f in early:
        trim(C, rng.fork('trim:' + f), f, target + 40)
        topup(C, rng.fork('topup:' + f), ids, f, target)
    errata_index(C)
    for f in early:
        lines, inf = inforce_counts(C, f)
        for measure, v in (('records', lines),):
            cid = ids('cs')
            at = nudge(CUT - 4 * DAY)
            C.recs['control_totals.html']['controls'].append(rec(cid, [('A', at, {'control': cid, 'scope': f, 'measure': measure, 'value': v, 'signed': at})], {'control'}, ('control', f, measure)))
            C.T.controls_truth[cid] = {'scope': f, 'measure': measure, 'value': v, 'true': v}
    topup(C, rng.fork('topup:controls'), ids, 'control_totals.html', target)
    for f in early + ['control_totals.html']:
        C.placed[f] = place(C, rng.fork('place:' + f), f)
        batch_plan(C, rng.fork('batch:' + f), f)
    C.recs['source_conventions.html']['register'] = build_register(C, rng.fork('register'), ids)
    topup(C, rng.fork('topup:register'), ids, 'source_conventions.html', target)
    for f in ('source_conventions.html',):
        C.placed[f] = place(C, rng.fork('place:' + f), f)
        batch_plan(C, rng.fork('batch:' + f), f)
    return C
FULLWIDTH = {chr(c): chr(c + 65248) for c in range(33, 127)}

def _wall_parts(t, zone):
    w = wall_of(t, zone)
    y, m, d = civil_from_days(w // DAY)
    s = w % DAY
    return (y, m, d, s // 3600, s % 3600 // 60, s % 60, w)

def enc_ts(t, conv):
    if conv == 'iso':
        return iso(t)
    if conv == 'epoch':
        return str(t)
    if conv == 'epochms':
        return str(t * 1000)
    kind, _, zone = conv.partition(':')
    y, m, d, hh, mi, ss, w = _wall_parts(t, zone)
    if kind == 'off':
        off = zone_offset(zone, t)
        sign = '+' if off >= 0 else '-'
        off = abs(off)
        return f'{y:04d}-{m:02d}-{d:02d}T{hh:02d}:{mi:02d}:{ss:02d}{sign}{off // 3600:02d}:{off % 3600 // 60:02d}'
    if kind == 'naive':
        return f'{y:04d}-{m:02d}-{d:02d} {hh:02d}:{mi:02d}:{ss:02d}'
    if kind in ('xl', 'xl4'):
        base = XL1900_DAY if kind == 'xl' else XL1904_DAY
        minutes = (w - base * DAY) // 60
        return f'{D(minutes) / D(1440):.6f}'
    if kind == 'dmy':
        return f'{d:02d}/{m:02d}/{y:04d} {hh:02d}:{mi:02d}'
    if kind == 'mdy':
        return f'{m:02d}/{d:02d}/{y:04d} {hh:02d}:{mi:02d}'
    raise ValueError(conv)

def enc_date(z, conv):
    y, m, d = civil_from_days(z)
    if conv == 'iso':
        return f'{y:04d}-{m:02d}-{d:02d}'
    if conv == 'dmy':
        return f'{d:02d}.{m:02d}.{y:04d}'
    if conv == 'mdy':
        return f'{m:02d}/{d:02d}/{y:04d}'
    if conv == 'compact':
        return f'{y:04d}{m:02d}{d:02d}'
    if conv == 'xl':
        return str(z - XL1900_DAY)
    raise ValueError(conv)

def _group3(digits, sep):
    out = []
    while len(digits) > 3:
        out.insert(0, digits[-3:])
        digits = digits[:-3]
    out.insert(0, digits)
    return sep.join(out)

def enc_dec(x, conv):
    s = dec_str(x)
    if conv == 'plain':
        return s
    neg = s.startswith('-')
    s = s.lstrip('-')
    ip, _, fp = s.partition('.')
    sep, dp = ('.', ',') if conv == 'de' else (' ', ',')
    out = _group3(ip, sep) + (dp + fp if fp else '')
    return ('-' if neg else '') + out

def enc_int(v, conv):
    if conv == 'neg':
        return str(-v)
    s = str(abs(v))
    if conv == 'grouped':
        s = _group3(s, ',')
    elif conv == 'de':
        s = _group3(s, '.')
    return ('-' if v < 0 else '') + s

def enc_hours(h, conv):
    h = D(h)
    mins = int(h * 60)
    if conv == 'h':
        return dec_str(h)
    if conv == 'min':
        return str(mins)
    if conv == 'hm':
        return f'{mins // 60}h{mins % 60:02d}m'
    if conv == 'iso':
        hh, mm = (mins // 60, mins % 60)
        return 'PT' + (f'{hh}H' if hh else '') + (f'{mm}M' if mm or not hh else '')
    raise ValueError(conv)

def enc_money(v, conv, cur):
    exp = CUR_EXP.get(cur, 2)
    if conv == 'minor':
        return str(v)
    neg = v < 0
    a = abs(v)
    major = str(a // 10 ** exp) + ('.' + str(a % 10 ** exp).zfill(exp) if exp else '')
    if conv == 'major':
        return ('-' if neg else '') + major
    if conv == 'de':
        ip, _, fp = major.partition('.')
        return ('-' if neg else '') + _group3(ip, '.') + (',' + fp if fp else '')
    if conv == 'paren':
        return f'({major})' if neg else major
    raise ValueError(conv)

def enc_bool(b, conv):
    if conv == 'neg':
        b = not b
        conv = 'tf'
    return {'tf': ('true', 'false'), '10': ('1', '0'), 'yn': ('yes', 'no'), 'YN': ('Y', 'N')}[conv][0 if b else 1]

def enc_svc(svc, conv, ctx):
    if conv == 'legacy':
        lid = legacy_id(ctx['W'], ctx['rng'], svc, ctx['rec_at'])
        return lid if lid else svc
    n = int(svc[4:])
    if conv == 'canon':
        return svc
    if conv == 'upper':
        return svc.upper()
    if conv == 'nopad':
        return f'svc-{n}'
    if conv == 'spaced':
        return f' {svc} '
    raise ValueError(conv)

def enc_pkg(name, conv, eco, rng):
    if conv == 'canon':
        return name
    if conv == 'case' and eco != 'maven':
        return ''.join((c.upper() if rng.chance(0.5) else c for c in name))
    if conv == 'sep' and eco in ('pypi', 'cargo'):
        return ''.join((rng.pick(['_', '.']) if c == '-' and eco == 'pypi' else '_' if c == '-' else c for c in name))
    if conv == 'fullwidth':
        idx = [i for i, c in enumerate(name) if c.isalpha()]
        if not idx:
            return name
        k = rng.pick(idx)
        return name[:k] + FULLWIDTH[name[k]] + name[k + 1:]
    if conv == 'zw':
        k = rng.rint(1, max(1, len(name) - 1))
        return name[:k] + '\u200b' + name[k:]
    return name

def enc_ver(v, conv, eco, rng):
    if conv in ('semver', 'native', 'vprefix'):
        return spell_ver(v, eco, conv)
    if conv == 'build':
        return spell_ver(v, eco, 'build', rng.rint(1, 99))
    raise ValueError(conv)

def enc_vid(x, conv):
    if conv == 'canon':
        return x
    if conv == 'lower':
        return x.lower()
    if conv == 'nopad':
        if x.startswith('CVE-'):
            y, n = x[4:].split('-')
            return f'CVE-{y}-{int(n)}'
        return x
    if conv == 'spaced':
        return f'  {x} '
    raise ValueError(conv)

def enc_vec(v, conv):
    if conv == 'canon':
        return v
    if conv == 'noprefix':
        return v.split('/', 1)[1] if v.startswith('CVSS:3.1/') else v
    if conv == 'lower':
        return v.lower()
    raise ValueError(conv)

def enc_spdx(expr, conv):
    canon = canon_spdx(expr)
    if conv == 'canon':
        return canon
    if conv == 'lower':
        return canon.lower()
    if conv == 'deprecated':
        inv = {v: k for k, v in SPDX_DEPRECATED.items() if not k.endswith('+')}
        inv.update({v: k for k, v in SPDX_DEPRECATED.items() if k.endswith('+')})
        return ' '.join((inv.get(tok, tok) for tok in canon.split(' ')))
    if conv == 'alias':
        inv = {'Apache-2.0': 'Apache 2.0', 'MIT': 'MIT License', 'MPL-2.0': 'Mozilla Public License 2.0', 'ISC': 'ISC License'}
        out = canon
        for k, v in inv.items():
            out = out.replace(k, v) if k in out.split(' ') else out
        return out
    raise ValueError(conv)

def enc_events(evs, conv, eco):
    parts = []
    for kind, v in evs:
        parts.append(f"{kind}:{(v if v == '0' else spell_ver(v, eco, conv))}")
    return '|'.join(parts)

def events_canon(evs):
    if isinstance(evs, Sentinel):
        return '@' + evs.meaning
    return '|'.join((f'{k}:{v}' for k, v in evs))

def enc_enum(word, vocab, conv):
    V = VOCAB[vocab]
    return V[conv][V['word'].index(word)]

def encode(kind, v, conv, ctx):
    g = group_of(kind)
    if g == 'ts':
        return enc_ts(v, conv)
    if g == 'date':
        return enc_date(v, conv)
    if g == 'dec':
        return enc_dec(v, conv)
    if g == 'int':
        return enc_int(v, conv)
    if g == 'hours':
        return enc_hours(v, conv)
    if g == 'money':
        return enc_money(v, conv, ctx.get('cur', 'EUR'))
    if g == 'bool':
        return enc_bool(v, conv)
    if g == 'id':
        return v.upper() if conv == 'upper' else f' {v} ' if conv == 'spaced' else v.replace('-', '_') if conv == 'under' else v
    if g == 'svcid':
        return enc_svc(v, conv, ctx)
    if g == 'pkg':
        return enc_pkg(v, conv, ctx.get('eco'), ctx['rng'])
    if g == 'ver':
        return enc_ver(v, conv, ctx.get('eco'), ctx['rng'])
    if g == 'vid':
        return enc_vid(v, conv)
    if g == 'vec':
        return enc_vec(v, conv)
    if g == 'spdx':
        return enc_spdx(v, conv)
    if g == 'events':
        return enc_events(v, conv, ctx.get('eco'))
    if g == 'enum':
        return enc_enum(v, kind[5:], conv)
    if g in ('text', 'cons'):
        return v
    raise ValueError(kind)

def canon_cell(kind, v):
    """Canonical text of a stored value for custody lines (close_contract.md section 6)."""
    if v is None:
        return ''
    if isinstance(v, Sentinel):
        return '@' + v.meaning
    g = group_of(kind)
    if g == 'ver':
        return str(v)
    if g == 'events':
        return events_canon(v)
    if g == 'spdx':
        return canon_spdx(v)
    if g in ('ts', 'date', 'dec', 'hours', 'int', 'money', 'bool'):
        return canon_str(g, v)
    return str(v)

def encode_corpus(C):
    """C.cells[fname] = [(batch, [ {field: text} ])] in written order."""
    C.cells = {}
    for fname in FILE_NAMES:
        rng = Rng(derive(C.seed, 'enc:' + fname))
        eco_file = FILES[fname][3].get('eco')
        out = []
        for b in C.batches[fname]:
            fields = fields_of(fname, b['table'])
            rows = []
            for r, i in b['rows']:
                rv = r['revs'][i]
                p = rv['p']
                env = {'rid': r['rid'], 'rev': rv['rev'], 'st': {'A': 'active', 'V': 'void', 'D': 'draft'}[rv['st']], 'rec_at': rv['rec_at']}
                eco = p.get('eco') or eco_file
                if eco is None and 'name' in p and fname.startswith('remediation_estimates'):
                    eco = b['table'].split('_', 1)[1]
                cur = p.get('currency', 'EUR')
                ctx = {'eco': eco, 'cur': cur, 'rng': rng, 'rec_at': rv['rec_at'], 'W': C.W}
                cells = {}
                for fn, kd in fields:
                    v = env[fn] if fn in env else p.get(fn)
                    if v is None:
                        cells[fn] = ''
                    elif isinstance(v, Sentinel):
                        cells[fn] = b['sent'][fn, v.meaning]
                    else:
                        cells[fn] = encode(kd, v, b['conv'][fn], ctx)
                rows.append(cells)
            out.append((b, rows))
        C.cells[fname] = out

def custody_rows(C):
    out = {}
    for fname in FILE_NAMES:
        crc_all = 0
        n = 0
        for b in C.batches[fname]:
            fields = fields_of(fname, b['table'])
            for r, i in b['rows']:
                line = canon_line(fname, b['table'], r['rid'], r['revs'][i], fields)
                crc_all = _crc_more(crc_all, line)
                n += 1
        inf = []
        tables = [t for t, _ in FILES[fname][2]]
        for t in tables:
            byrid = {}
            for r in C.recs[fname][t]:
                byrid.setdefault(r['rid'], r)
            fields = fields_of(fname, t)
            for rid in sorted(byrid):
                r = byrid[rid]
                i = inforce_index(r['revs'])
                if i is None or r['revs'][i]['st'] == 'V' or (fname, rid) in C.err_void:
                    continue
                corr = C.err_corr.get((fname, rid), {})
                inf.append(canon_line(fname, t, rid, r['revs'][i], fields, corr))
        crc_inf = 0
        for line in inf:
            crc_inf = _crc_more(crc_inf, line)
        out[fname] = {'file': fname, 'records': n, 'in_force': len(inf), 'received_crc': crc_all, 'inforce_crc': crc_inf}
    return out

def canon_line(fname, table, rid, rv, fields, corr=None):
    parts = [rid, str(rv['rev']), {'A': 'active', 'V': 'void', 'D': 'draft'}[rv['st']], iso(rv['rec_at'])]
    for fn, kd in fields[4:]:
        if corr and fn in corr:
            parts.append(corr[fn])
        else:
            parts.append(canon_cell(kd, rv['p'].get(fn)))
    return '|'.join(parts)

def _crc_more(c, line):
    import zlib
    return zlib.crc32((line + '\n').encode('utf-8'), c) & 4294967295
import hashlib
import json
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_CEILING
P1_FILES = ['packages.jsonl', 'pins.jsonl', 'exposures.jsonl', 'services.jsonl', 'teams.csv', 'ledger.jsonl']
P2_FILES = ['package_risk.json', 'service_risk.json', 'remediation_plan.json', 'team_rollup.json', 'license_summary.json', 'sla_metrics.json']
P3_FILES = ['release_gates.json', 'control_reconciliation.json', 'deferred_amendments.json', 'team_scorecard.json', 'certification.json', 'chain_audit.json']
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

def jsonl_bytes(rows):
    return ''.join((dumps_line(r) + '\n' for r in rows)).encode('utf-8')

def teams_bytes(rows):
    out = [','.join(TEAMS_HEADER)]
    for r in rows:
        out.append(','.join(('' if r[k] is None else str(r[k]) for k in TEAMS_HEADER)))
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

import bisect

# ---- risk and close layer reference, written from contract sections 11 and 12 (independent of the repository code)
def _q(x, places):
    return Decimal(x).quantize(Decimal(10) ** -places, rounding=ROUND_HALF_EVEN)


def _share_of(part, whole):
    return _q(part / whole, 6) if whole else _q(0, 6)


def _desc_dense(values):
    """Dense rank by value, highest value first, equal values sharing a rank."""
    return {v: k for k, v in enumerate(sorted(set(values), reverse=True), 1)}


def _nearest_rank(sorted_values, tenths):
    """Value at position ceil(tenths / 10 x n) of the sorted values (1-based); None without values."""
    n = len(sorted_values)
    if n == 0:
        return None
    pos = (tenths * n + 9) // 10
    return sorted_values[max(pos, 1) - 1]


def _digests(raw, prefix, names):
    return {f'{prefix}/{name}': hashlib.sha256(raw[name]).hexdigest() for name in names}


def _risk_of(rows, weight):
    total = Decimal(0)
    for e in rows:
        total += e['cvss'] * weight[e['service']]
    return total


def ref_stage2(p1, raw1):
    upstream = _digests(raw1, 'p1', P1_FILES)
    services = p1['services.jsonl']
    weight = {s['service']: s['weight'] for s in services}
    team_of = {s['service']: s['team'] for s in services}
    open_rows = [e for e in p1['exposures.jsonl'] if e['status'] == 'open']
    teams = p1['teams.csv']

    grouped = {}
    for e in open_rows:
        grouped.setdefault(e['package'], []).append(e)
    pkg = []
    for name in sorted(grouped):
        es = grouped[name]
        pkg.append({'package': name, 'open': len(es), 'max_cvss': _q(max(e['cvss'] for e in es), 1), 'risk': _q(_risk_of(es, weight), 6)})
    pkg_total = sum((r['risk'] for r in pkg), Decimal(0))
    ordered = sorted(r['risk'] for r in pkg)
    rank = _desc_dense(ordered)
    n = len(pkg)
    package_rows = []
    for r in pkg:
        smaller = bisect.bisect_left(ordered, r['risk'])
        package_rows.append({'package': r['package'], 'open': r['open'], 'max_cvss': r['max_cvss'], 'risk': r['risk'],
                             'share': _share_of(r['risk'], pkg_total),
                             'pct_rank': _q(Decimal(smaller) / Decimal(n - 1), 6) if n > 1 else _q(0, 6),
                             'dense_rank': rank[r['risk']]})

    active = [s for s in services if s['status'] == 'active']
    per_service = {}
    for e in open_rows:
        per_service.setdefault(e['service'], []).append(e)
    svc = []
    for s in active:
        es = per_service.get(s['service'], [])
        svc.append({'service': s['service'], 'team': s['team'], 'open': len(es), 'risk': _q(_risk_of(es, weight), 6),
                    'breaches': sum(1 for e in es if e['breach'] is True)})
    svc_total = sum((r['risk'] for r in svc), Decimal(0))
    srank = _desc_dense([r['risk'] for r in svc])
    service_rows = [{'service': r['service'], 'team': r['team'], 'open': r['open'], 'risk': r['risk'],
                     'share': _share_of(r['risk'], svc_total), 'dense_rank': srank[r['risk']], 'breaches': r['breaches']} for r in svc]

    capacity = {t['team']: t['capacity_hours'] for t in teams}
    remaining = {t: (None if c is None else Decimal(c)) for t, c in capacity.items()}
    pool_cap = 0
    for row in p1['ledger.jsonl']:
        if row['kind'] == 'control' and row['scope'] == 'global' and row['measure'] == 'pool_hours':
            pool_cap = row['value']
            break
    pool = Decimal(pool_cap)
    taken = {}
    plan_rows = []
    sum_team = sum_pool = sum_left = Decimal(0)
    for seq, e in enumerate(open_rows, 1):
        team = team_of[e['service']]
        estimate = e['estimate']
        taken[e['service']] = taken.get(e['service'], 0) + 1
        team_hours = pool_hours = Decimal(0)
        if taken[e['service']] <= SERVICE_SLOTS:
            left = remaining.get(team)
            if left is None:
                team_hours = estimate
            else:
                team_hours = min(estimate, left)
                remaining[team] = left - team_hours
            if e['severity'] in ('critical', 'high'):
                pool_hours = min(estimate - team_hours, pool)
                pool -= pool_hours
        left_over = estimate - team_hours - pool_hours
        sum_team += team_hours
        sum_pool += pool_hours
        sum_left += left_over
        team_left = remaining.get(team)
        plan_rows.append({'seq': seq, 'service': e['service'], 'package': e['package'], 'vuln': e['vuln'], 'severity': e['severity'],
                          'estimate': _q(estimate, 2), 'team': team, 'team_hours': _q(team_hours, 2), 'pool_hours': _q(pool_hours, 2),
                          'unallocated': _q(left_over, 2), 'team_remaining': None if team_left is None else _q(team_left, 2),
                          'pool_remaining': _q(pool, 2)})

    held_sum, held_count, balance = {}, {}, {}
    for row in p1['ledger.jsonl']:
        if row['kind'] == 'opening':
            balance[row['team']] = balance.get(row['team'], 0) + row['amount_cents']
        elif row['kind'] == 'entry':
            current = balance.get(row['team'], 0)
            if current + row['amount_cents'] < 0:
                held_sum[row['team']] = held_sum.get(row['team'], 0) + row['amount_cents']
                held_count[row['team']] = held_count.get(row['team'], 0) + 1
            else:
                balance[row['team']] = current + row['amount_cents']
    team_open, team_services = {}, {}
    for r in service_rows:
        team_services[r['team']] = team_services.get(r['team'], 0) + 1
        team_open[r['team']] = team_open.get(r['team'], 0) + r['open']
    team_exposures = {}
    for e in open_rows:
        team_exposures.setdefault(team_of[e['service']], []).append(e)
    trisk = {t['team']: _q(_risk_of(team_exposures.get(t['team'], []), weight), 6) for t in teams}
    team_total = sum(trisk.values(), Decimal(0))
    trank = _desc_dense(list(trisk.values()))
    team_rows = [{'team': t['team'], 'services': team_services.get(t['team'], 0), 'open': team_open.get(t['team'], 0),
                  'risk': trisk[t['team']], 'share': _share_of(trisk[t['team']], team_total), 'dense_rank': trank[trisk[t['team']]],
                  'balance': balance.get(t['team'], 0), 'held': held_sum.get(t['team'], 0), 'held_entries': held_count.get(t['team'], 0)}
                 for t in teams]

    runtime = [p for p in p1['pins.jsonl'] if p['scope'] == 'runtime' and p['pinned'] is not None]
    classes = []
    for c in CLASSES:
        chosen = [p for p in runtime if p['obligation'] == c]
        classes.append({'class': c, 'pins': len(chosen), 'packages': len({p['package'] for p in chosen}),
                        'share': _q(Decimal(len(chosen)) / Decimal(len(runtime)), 6) if runtime else _q(0, 6)})
    strong = {}
    for p in runtime:
        if p['obligation'] in ('strong', 'network'):
            strong[team_of[p['service']]] = strong.get(team_of[p['service']], 0) + 1
    lrank = _desc_dense([strong.get(t['team'], 0) for t in teams])
    license_teams = [{'team': t['team'], 'strong': strong.get(t['team'], 0), 'dense_rank': lrank[strong.get(t['team'], 0)]} for t in teams]

    severities = []
    for sev in SEVERITIES:
        chosen = [e for e in open_rows if e['severity'] == sev]
        days = sorted(e['days_open'] for e in chosen if e['days_open'] is not None)
        severities.append({'severity': sev, 'open': len(chosen), 'with_days': len(days), 'nulls': len(chosen) - len(days),
                           'zeros': days.count(0), 'breaches': sum(1 for e in chosen if e['breach'] is True),
                           'mean_days': _q(Decimal(sum(days)) / Decimal(len(days)), 6) if days else None,
                           'p50': _nearest_rank(days, 5), 'p90': _nearest_rank(days, 9), 'max_days': days[-1] if days else None})

    return {'package_risk.json': {'upstream': upstream, 'rows': package_rows, 'totals': {'packages': n, 'risk': _q(pkg_total, 6)}},
            'service_risk.json': {'upstream': upstream, 'rows': service_rows, 'totals': {'services': len(service_rows), 'risk': _q(svc_total, 6)}},
            'remediation_plan.json': {'upstream': upstream, 'rows': plan_rows,
                                      'totals': {'team_hours': _q(sum_team, 2), 'pool_hours': _q(sum_pool, 2), 'unallocated': _q(sum_left, 2), 'pool_cap': pool_cap}},
            'team_rollup.json': {'upstream': upstream, 'rows': team_rows},
            'license_summary.json': {'upstream': upstream, 'classes': classes, 'teams': license_teams},
            'sla_metrics.json': {'upstream': upstream, 'severities': severities}}


def ref_stage3(p1, raw1, p2, raw2):
    upstream = _digests(raw1, 'p1', P1_FILES)
    upstream.update(_digests(raw2, 'p2', P2_FILES))
    services = p1['services.jsonl']
    weight = {s['service']: s['weight'] for s in services}
    team_of = {s['service']: s['team'] for s in services}
    exposures = p1['exposures.jsonl']
    open_rows = [e for e in exposures if e['status'] == 'open']
    runtime = [p for p in p1['pins.jsonl'] if p['scope'] == 'runtime']
    pinned_runtime = [p for p in runtime if p['pinned'] is not None]
    ledger = p1['ledger.jsonl']
    closing = {r['team']: r['amount_cents'] for r in ledger if r['kind'] == 'closing'}
    teams = p1['teams.csv']
    team_names = {t['team'] for t in teams}
    service_names = {s['service'] for s in services}
    srows = p2['service_risk.json']['rows']
    prows = p2['package_risk.json']['rows']
    trows = p2['team_rollup.json']['rows']
    plan = p2['remediation_plan.json']
    by_service = {r['service']: r for r in srows}
    by_package = {r['package']: r for r in prows}
    by_team = {r['team']: r for r in trows}

    limit = (2 * len(srows) + 99) // 100  # ceil(0.02 x rows)
    gates, totals = [], {'block': 0, 'hold': 0, 'pass': 0}
    for s in services:
        if s['status'] != 'active':
            continue
        k = s['service']
        reasons = []
        if any(e['service'] == k and e['severity'] == 'critical' and e['breach'] is True for e in open_rows):
            reasons.append('critical_breach')
        sr = by_service.get(k)
        if sr is not None and sr['risk'] > 0 and sr['dense_rank'] <= limit:
            reasons.append('top_risk')
        if any(p['service'] == k and p['disposition'] == 'unsatisfiable' for p in runtime):
            reasons.append('unsatisfiable_pin')
        if any(r['service'] == k and r['severity'] in ('critical', 'high') and r['unallocated'] > 0 for r in plan['rows']):
            reasons.append('unfunded_remediation')
        if any(p['service'] == k and p['obligation'] == 'network' for p in runtime):
            reasons.append('network_license')
        if 'critical_breach' in reasons or 'top_risk' in reasons:
            verdict = 'block'
        elif reasons:
            verdict = 'hold'
        else:
            verdict = 'pass'
        totals[verdict] += 1
        gates.append({'service': k, 'team': s['team'], 'verdict': verdict, 'reasons': reasons})

    def count_open(field, value):
        return sum(1 for e in open_rows if e[field] == value)

    custody = {r['file']: r for r in ledger if r['kind'] == 'custody'}
    capacity = {t['team']: t['capacity_hours'] for t in teams}
    recon, agreeing = [], 0
    for r in sorted((x for x in ledger if x['kind'] == 'control'), key=lambda x: x['control']):
        scope, measure, published = r['scope'], r['measure'], r['value']
        one = two = None
        if measure == 'open_exposures':
            if scope in team_names:
                one = sum(1 for e in open_rows if team_of[e['service']] == scope)
                two = by_team[scope]['open'] if scope in by_team else 0
            elif scope in service_names:
                one = count_open('service', scope)
                two = by_service[scope]['open'] if scope in by_service else 0
            else:
                one = count_open('package', scope)
                two = by_package[scope]['open'] if scope in by_package else 0
        elif measure == 'runtime_pins':
            one = sum(1 for p in pinned_runtime if p['service'] == scope)
        elif measure == 'closing_cents':
            one = closing.get(scope, 0)
            two = (by_team[scope]['balance'] + by_team[scope]['held']) if scope in by_team else None
        elif measure == 'capacity_hours':
            one = capacity.get(scope)
        elif measure in ('records', 'in_force'):
            one = custody[scope][measure] if scope in custody else None
        elif measure == 'pool_hours':
            two = int(plan['totals']['pool_cap'])
        elif measure == 'total_open':
            one = len(open_rows)
            two = sum(x['open'] for x in prows)
        elif measure == 'waived_total':
            one = sum(1 for e in exposures if e['status'] == 'waived')
        stated = [v for v in (one, two) if v is not None]
        agrees = bool(stated) and all(v == published for v in stated)
        agreeing += agrees
        recon.append({'control': r['control'], 'scope': scope, 'measure': measure, 'published': published, 'stage1': one,
                      'stage2': two, 'agrees': agrees})

    risk_total = p2['package_risk.json']['totals']['risk']
    deferred, cvss_sum, cents_sum = [], Decimal(0), 0
    for r in ledger:
        if r['kind'] != 'deferred':
            continue
        impact = after = None
        if r['measure'] == 'cvss' and r['current'] is not None and r['amended'] is not None:
            change = Decimal(0)
            for e in open_rows:
                if e['vuln'] == r['target']:
                    change += (r['amended'] - r['current']) * weight[e['service']]
            impact = _q(change, 6)
            after = _q(risk_total + change, 6)
            cvss_sum += impact
        elif r['measure'] == 'cents':
            impact = (r['amended'] or 0) - (r['current'] or 0)
            after = None if r['target'] is None else closing.get(r['target'], 0) + impact
            cents_sum += impact
        deferred.append({'amendment': r['amendment'], 'file': r['file'], 'target': r['target'], 'measure': r['measure'],
                         'current': r['current'], 'amended': r['amended'], 'impact': impact, 'after': after})

    allocated, breaches = {}, {}
    for r in plan['rows']:
        allocated[r['team']] = allocated.get(r['team'], Decimal(0)) + r['team_hours']
    for r in srows:
        breaches[r['team']] = breaches.get(r['team'], 0) + r['breaches']
    cards = []
    for t in teams:
        k = t['team']
        roll = by_team[k]
        cap = t['capacity_hours']
        hours = allocated.get(k, Decimal(0))
        cards.append({'team': k, 'risk': roll['risk'], 'capacity': cap, 'allocated': _q(hours, 2),
                      'utilization': _q(hours / Decimal(cap), 6) if cap else None, 'breaches': breaches.get(k, 0),
                      'closing': closing.get(k, 0), 'balance': roll['balance'],
                      'score': _q(roll['risk'] * (Decimal(1) + Decimal(breaches.get(k, 0)) / Decimal(roll['open'] + 1)), 6)})
    crank = _desc_dense([c['score'] for c in cards])
    for c in cards:
        c['dense_rank'] = crank[c['score']]

    risk_stage1 = _q(_risk_of(open_rows, weight), 6)
    risk_packages = sum((r['risk'] for r in prows), Decimal(0))
    risk_services = sum((r['risk'] for r in srows), Decimal(0))
    estimate_total = sum((r['estimate'] for r in plan['rows']), Decimal(0))
    unallocated = plan['totals']['unallocated']
    critical = sum(1 for e in open_rows if e['severity'] == 'critical' and e['breach'] is True)
    if critical == 0 and unallocated == 0:
        verdict = 'certified'
    elif unallocated <= UNFUNDED_SHARE * estimate_total:
        verdict = 'qualified'
    else:
        verdict = 'withheld'
    summary = {'active_services': sum(1 for s in services if s['status'] == 'active'), 'runtime_pins': len(pinned_runtime),
               'open_exposures': len(open_rows), 'critical_breaches': critical, 'risk_stage1': risk_stage1,
               'risk_packages': _q(risk_packages, 6), 'risk_services': _q(risk_services, 6),
               'gap_packages': _q(risk_packages - risk_stage1, 6), 'gap_services': _q(risk_services - risk_stage1, 6),
               'pool_used': plan['totals']['pool_hours'], 'unallocated': unallocated, 'estimate_total': _q(estimate_total, 2),
               'verdict': verdict}

    main_list = {'package_risk.json': 'rows', 'service_risk.json': 'rows', 'remediation_plan.json': 'rows', 'team_rollup.json': 'rows',
                 'license_summary.json': 'classes', 'sla_metrics.json': 'severities'}
    files = [{'file': 'p1/' + f, 'rows': len(p1[f]), 'bytes': len(raw1[f])} for f in P1_FILES]
    files += [{'file': 'p2/' + f, 'rows': len(p2[f][main_list[f]]), 'bytes': len(raw2[f])} for f in P2_FILES]
    active_names = {s['service'] for s in services if s['status'] == 'active'}
    tolerance = Decimal('0.0000005') * (len(prows) + len(srows))
    checks = [
        ('package_risk_covers_open_packages', {r['package'] for r in prows} == {e['package'] for e in open_rows}),
        ('service_risk_covers_active_services', {r['service'] for r in srows} == active_names),
        ('plan_covers_open_exposures', len(plan['rows']) == len(open_rows)),
        ('team_rollup_covers_teams', [r['team'] for r in trows] == [t['team'] for t in teams]),
        ('license_pins_match', sum(c['pins'] for c in p2['license_summary.json']['classes']) == len(pinned_runtime)),
        ('sla_open_matches', sum(c['open'] for c in p2['sla_metrics.json']['severities']) == len(open_rows)),
        ('risk_totals_agree', abs(risk_packages - risk_services) <= tolerance),
        ('ledger_balances_close', all(r['balance'] + r['held'] == closing.get(r['team'], 0) for r in trows)),
    ]
    return {'release_gates.json': {'upstream': upstream, 'rows': gates, 'totals': totals},
            'control_reconciliation.json': {'upstream': upstream, 'rows': recon, 'totals': {'controls': len(recon), 'agreeing': agreeing}},
            'deferred_amendments.json': {'upstream': upstream, 'rows': deferred,
                                         'totals': {'amendments': len(deferred), 'cvss_impact': _q(cvss_sum, 6), 'cents_impact': cents_sum}},
            'team_scorecard.json': {'upstream': upstream, 'rows': cards},
            'certification.json': {'upstream': upstream, 'summary': summary},
            'chain_audit.json': {'upstream': upstream, 'files': files, 'checks': [{'check': c, 'passed': bool(ok)} for c, ok in checks]}}


def _v(x):
    return None if x is None else str(x)

def deferred_rows(C):
    W, T = (C.W, C.T)
    out = []
    vec_cur = {}
    for v in W.vulns:
        vec = vuln_vector_visible(v)
        vec_cur[v['canon']] = cvss_base(vec) if vec else None
    alias_to = {}
    for v in W.vulns:
        for x in (v['cve'], v['ghsa'], v['osv']):
            if x:
                alias_to[x] = v['canon']
    for fname in AMEND_FILES:
        t = FILES[fname][2][0][0]
        for r in C.recs[fname][t]:
            i = inforce_index(r['revs'])
            inforce_void = i is None or r['revs'][i]['st'] == 'V' or (fname, r['rid']) in C.err_void
            for rv in r['revs']:
                if rv['rec_at'] < CUT or rv['st'] == 'D':
                    continue
                p = rv['p']
                if i is None:
                    action = 'new'
                elif rv['st'] == 'V':
                    action = 'void'
                else:
                    action = 'revise'
                target = measure = cur = amd = None
                if fname == 'advisory_rescores.parquet':
                    target = alias_to.get(p['vuln'], p['vuln'])
                    if p['approved'] and rv['st'] != 'V':
                        measure, cur, amd = ('cvss', vec_cur.get(target), cvss_base(p['vector']))
                    else:
                        measure = 'none'
                elif fname == 'remediation_timesheets.csv':
                    measure = 'cents'
                    ts = r['fact'][1] if r['fact'] else {'eng': p['engineer'], 'worked': p['worked'], 'hours': p['hours']}
                    tsx = {'eng': p['engineer'], 'worked': p['worked'], 'hours': p['hours']}
                    target = seg_team(W, p['engineer'], p['worked'])
                    cur = None if inforce_void else ts_cents(W, dict(ts))
                    amd = None if rv['st'] == 'V' else ts_cents(W, tsx)
                elif fname == 'ledger_journal.db':
                    measure = 'cents'
                    j = r['fact'][1] if r['fact'] else {'minor': p['amount'], 'cur': p['currency'], 'booked': p['booked']}
                    target = p['team']
                    cur = None if inforce_void or r['rid'] in T.rev_excluded else to_cents(j['minor'], j['cur'], fx_at(W, j['cur'], j['booked']))
                    amd = None if rv['st'] == 'V' else to_cents(p['amount'], p['currency'], fx_at(W, p['currency'], min(p['booked'], CUT - 1)))
                else:
                    target = p['service']
                    measure = 'none'
                out.append({'kind': 'deferred', 'amendment': f"{fname}#{r['rid']}#{rv['rev']}", 'file': fname, 'rid': r['rid'], 'rev': rv['rev'], 'recorded': rv['rec_at'], 'action': action, 'target': target, 'measure': measure, 'current': cur, 'amended': amd})
    out.sort(key=lambda d: (d['recorded'], d['amendment']))
    return out

def p1_rows(C):
    T = C.T
    pk = [{'package': r['package'], 'ecosystem': r['ecosystem'], 'owner_team': r['owner_team'], 'releases': r['releases'], 'yanked': r['yanked'], 'latest': _v(r['latest']), 'latest_license': r['latest_license'], 'obligation': r['obligation']} for r in T.packages_rows]
    pins = [{'service': p['service'], 'package': p['package'], 'scope': p['scope'], 'constraint': p['constraint'], 'source': p['source'], 'pinned': _v(p['pinned']), 'disposition': p['disposition'], 'license': p['license'], 'obligation': p['obligation']} for p in T.pins]
    ex = [{'service': e['service'], 'package': e['package'], 'version': str(e['version']), 'vuln': e['vuln'], 'cvss': qd(e['cvss'], 1), 'severity': e['severity'], 'status': e['status'], 'published': iso_date(e['published']), 'days_open': e['days_open'], 'sla_days': e['sla_days'], 'breach': e['breach'], 'estimate': qd(e['estimate'], 2), 'fixed': _v(e['fixed'])} for e in T.exposures]
    sv = [{'service': s['service'], 'team': s['team'], 'tier': s['tier'], 'region': s['region'], 'status': s['status'], 'deploys': s['deploys'], 'weight': qd(s['weight'], 4)} for s in T.services_rows]
    tm = [dict(t) for t in T.teams_rows]
    led = []
    for o in T.openings:
        led.append({'kind': 'opening', 'team': o['team'], 'entry': o['entry'], 'amount_cents': o['amount_cents']})
    for e in T.entries:
        led.append({'kind': 'entry', 'entry': e['entry'], 'team': e['team'], 'source': e['source'], 'booked': iso(e['booked']), 'amount_cents': e['amount_cents']})
    for c in T.closings:
        led.append({'kind': 'closing', 'team': c['team'], 'amount_cents': c['amount_cents']})
    ctl = []
    for r in C.recs['control_totals.html']['controls']:
        i = inforce_index(r['revs'])
        if i is None or r['revs'][i]['st'] == 'V':
            continue
        p = r['revs'][i]['p']
        ctl.append({'kind': 'control', 'control': p['control'], 'scope': p['scope'], 'measure': p['measure'], 'value': p['value']})
    ctl.sort(key=lambda x: x['control'])
    led += ctl
    cust = custody_rows(C)
    C.custody = cust
    for f in FILE_NAMES:
        c = cust[f]
        led.append({'kind': 'custody', 'file': f, 'records': c['records'], 'in_force': c['in_force'], 'received_crc': f"{c['received_crc']:08x}", 'inforce_crc': f"{c['inforce_crc']:08x}"})
    for d in deferred_rows(C):
        d = dict(d)
        d['recorded'] = iso(d['recorded'])
        for k in ('current', 'amended'):
            if d['measure'] == 'cvss' and d[k] is not None:
                d[k] = qd(d[k], 1)
        led.append(d)
    return {'packages.jsonl': pk, 'pins.jsonl': pins, 'exposures.jsonl': ex, 'services.jsonl': sv, 'teams.csv': tm, 'ledger.jsonl': led}

def p1_bytes(rows):
    out = {}
    for f in P1_FILES:
        if f == 'teams.csv':
            out[f] = teams_bytes(rows[f])
        elif f == 'ledger.jsonl':
            out[f] = jsonl_bytes([{k: r[k] for k in LEDGER_KEYS[r['kind']]} for r in rows[f]])
        else:
            out[f] = jsonl_bytes([{k: r[k] for k in P1_KEYS[f]} for r in rows[f]])
    return out

def reference_outputs(C):
    """{"p1": {name: bytes}, "p2": {...}, "p3": {...}} computed the way the cascade requires: each stage from the written bytes."""
    import tempfile
    from pathlib import Path
    b1 = p1_bytes(p1_rows(C))
    d = Path(tempfile.mkdtemp(prefix='helios-ref-'))
    (d / 'p1').mkdir()
    for f, b in b1.items():
        (d / 'p1' / f).write_bytes(b)
    p1, raw1 = read_p1(d / 'p1')
    s2 = ref_stage2(p1, raw1)
    b2 = {f: doc_bytes(s2[f]) for f in P2_FILES}
    (d / 'p2').mkdir()
    for f, b in b2.items():
        (d / 'p2' / f).write_bytes(b)
    p2, raw2 = read_p2(d / 'p2')
    s3 = ref_stage3(p1, raw1, p2, raw2)
    b3 = {f: doc_bytes(s3[f]) for f in P3_FILES}
    return {'p1': b1, 'p2': b2, 'p3': b3, 'dir': d}
import io as _io
import sqlite3 as _sq
import struct as _st
import zipfile as _zf
from xml.sax.saxutils import escape as _xesc, quoteattr as _xattr
BOM_FILES = {'registry_npm.csv', 'license_overrides.csv', 'fx_fixings.tsv'}
FIXED_ZIP_TIME = (2025, 10, 21, 3, 0, 0)
DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

def xesc(s):
    return _xesc(s).replace('\r', '&#13;')

def xattr(s):
    return _xattr(s).replace('\r', '&#13;').replace('\n', '&#10;')

def zip_members(members):
    buf = _io.BytesIO()
    with _zf.ZipFile(buf, 'w', compression=_zf.ZIP_DEFLATED, compresslevel=6) as z:
        for name, data in members:
            info = _zf.ZipInfo(name, date_time=FIXED_ZIP_TIME)
            info.external_attr = 33188 << 16
            info.compress_type = _zf.ZIP_DEFLATED
            z.writestr(info, data if isinstance(data, bytes) else data.encode('utf-8'))
    return buf.getvalue()

def batches(C, fname):
    for b, rows in C.cells[fname]:
        yield (b, rows)

def delim_line(vals, delim):
    parts = []
    for v in vals:
        if any((ch in v for ch in (delim, '"', '\n', '\r'))) or v != v.strip():
            v = '"' + v.replace('"', '""') + '"'
        parts.append(v)
    return delim.join(parts) + '\n'

def w_delim(C, fname, delim):
    out = _io.StringIO()
    if fname in BOM_FILES:
        out.write('\ufeff')
    out.write(f'# helios export {fname}; column layout and value conventions are registered per batch\n')
    prev = None
    for b, rows in batches(C, fname):
        names = [b['names'][f] for f in b['order']]
        if names != prev:
            out.write(delim_line(['batch'] + names, delim))
            prev = names
        for cells in rows:
            out.write(delim_line([b['label']] + [cells[f] for f in b['order']], delim))
    return out.getvalue().encode('utf-8')

def w_txt(C, fname):
    enc = FILES[fname][3].get('encoding', 'utf-8')
    out = [f'HELIOS FIXED-WIDTH EXPORT {fname}', 'Column positions follow the header ruler of each batch.']
    for b, rows in batches(C, fname):
        order = b['order']
        names = [b['names'][f] for f in order]
        widths = [max([len(names[i])] + [len(r[order[i]]) for r in rows]) + 2 for i in range(len(order))]
        out.append('')
        out.append(f"== BATCH {b['label']}")
        out.append(''.join((names[i].upper().ljust(widths[i]) for i in range(len(order)))).rstrip())
        for r in rows:
            out.append(''.join(((r[order[i]] if r[order[i]] != '' else '.').ljust(widths[i]) for i in range(len(order)))).rstrip())
    return ('\n'.join(out) + '\n').encode(enc)

def _jrec(b, cells):
    d = {'batch': b['label']}
    for f in b['order']:
        if cells[f] != '':
            d[b['names'][f]] = cells[f]
    return d

def w_jsonl(C, fname):
    out = []
    for b, rows in batches(C, fname):
        out.append(json.dumps({'batch': b['label']}))
        for cells in rows:
            out.append(json.dumps({b['names'][f]: cells[f] for f in b['order'] if cells[f] != ''}, ensure_ascii=False, separators=(',', ':')))
    return ('\n'.join(out) + '\n').encode('utf-8')

def w_json(C, fname):
    blocks = []
    for b, rows in batches(C, fname):
        recs = ',\n'.join((json.dumps({b['names'][f]: c[f] for f in b['order'] if c[f] != ''}, ensure_ascii=False, separators=(',', ':')) for c in rows))
        blocks.append(f'''    {{"batch": "{b['label']}", "records": [\n{recs}\n    ]}}''')
    return ('{\n' + f'  "export": {json.dumps(fname)},\n  "batches": [\n' + ',\n'.join(blocks) + '\n  ]\n}\n').encode('utf-8')

def w_yaml(C, fname):
    out = [f'# helios export {fname}', f'export: {json.dumps(fname)}', 'batches:']
    for b, rows in batches(C, fname):
        out.append(f'''  - batch: "{b['label']}"''')
        out.append('    records:')
        for cells in rows:
            parts = [f"{b['names'][f]}: {(json.dumps(cells[f], ensure_ascii=False) if cells[f] != '' else 'null')}" for f in b['order']]
            out.append('      - {' + ', '.join(parts) + '}')
    return ('\n'.join(out) + '\n').encode('utf-8')

def w_xml(C, fname):
    out = ['<?xml version="1.0" encoding="UTF-8"?>', f'<export file={xattr(fname)}>']
    for b, rows in batches(C, fname):
        out.append(f'''<batch id="{b['label']}">''')
        for cells in rows:
            inner = ' '.join((f"{b['names'][f]}={xattr(cells[f])}" for f in b['order'] if cells[f] != ''))
            out.append(f'<rec {inner}/>')
        out.append('</batch>')
    out.append('</export>')
    return ('\n'.join(out) + '\n').encode('utf-8')

def _kv(k, v):
    if v == '' or any((ch in v for ch in ' "=\\')) or v != v.strip():
        v = '"' + v.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return f'{k}={v}'

def w_log(C, fname):
    out = [f'# helios collector log {fname}']
    for b, rows in batches(C, fname):
        out.append(f"# batch {b['label']} opened")
        for cells in rows:
            out.append('EVT ' + ' '.join([_kv('batch', b['label'])] + [_kv(b['names'][f], cells[f]) for f in b['order'] if cells[f] != '']))
    return ('\n'.join(out) + '\n').encode('utf-8')

def w_toml(C, fname, prose):
    out = ['# ' + ln if ln else '#' for ln in prose.splitlines()]
    out.append('')
    for b, rows in batches(C, fname):
        out.append('[[batch]]')
        out.append(f'''label = "{b['label']}"''')
        out.append('entries = [')
        for cells in rows:
            out.append('  {' + ', '.join((f'{f} = {json.dumps(cells[f], ensure_ascii=False)}' for f in b['order'] if cells[f] != '')) + '},')
        out.append(']')
        out.append('')
    return ('\n'.join(out) + '\n').encode('utf-8')

def w_ini(C, fname):
    out = [f'; helios roster export {fname}', '']
    k = 0
    for b, rows in batches(C, fname):
        for cells in rows:
            k += 1
            out.append(f"[{b['table']}.{k:06d}]")
            out.append(f"batch = {b['label']}")
            for f in b['order']:
                out.append(f'{f} = {cells[f]}')
            out.append('')
    return ('\n'.join(out) + '\n').encode('utf-8')

def _rfc2822(t):
    y, m, d = civil_from_days(t // DAY)
    s = t % DAY
    return f'{DOW[weekday_of_day(t // DAY)]}, {d:02d} {MON[m - 1]} {y:04d} {s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d} +0000'

def w_mbox(C, fname):
    out = []
    for b, rows in batches(C, fname):
        for (r, i), cells in zip(b['rows'], rows):
            t = r['revs'][i]['rec_at']
            out.append('From q@x Tue Oct 21 03:00:00 2025')
            out.append(f"X-Batch: {b['label']}")
            for f in b['order']:
                if cells[f] != '':
                    out.append(f"X-{f.replace('_', '-').title()}: {cells[f]}")
            out.append('')
    return ('\n'.join(out) + '\n').encode('utf-8')

def w_ics(C, fname):
    out = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Helios//Change Freeze//EN', 'CALSCALE:GREGORIAN']
    for b, rows in batches(C, fname):
        for cells in rows:
            out.append('BEGIN:VEVENT')
            out.append(f"UID:{cells['rid']}")
            out.append(f"DTSTART;VALUE=DATE:{cells['start'].replace('-', '')}")
            out.append(f"DTEND;VALUE=DATE:{cells['end'].replace('-', '')}")
            out.append(f"X-BATCH:{b['label']}")
            out.append(f"X-REV:{cells['rev']}")
            out.append(f"X-ST:{cells['st']}")
            out.append(f"X-RECORDED:{cells['rec_at']}")
            out.append(f"X-SERVICE:{cells['service']}")
            out.append('END:VEVENT')
    out.append('END:VCALENDAR')
    return ('\n'.join(out) + '\n').encode('utf-8')

def md_table(head, rows):

    def esc(s):
        return s.replace('\\', '\\\\').replace('|', '\\|')
    out = ['| ' + ' | '.join((esc(h) for h in head)) + ' |', '|' + '|'.join(('---' for _ in head)) + '|']
    for r in rows:
        out.append('| ' + ' | '.join((esc(x) for x in r)) + ' |')
    return '\n'.join(out)

def w_md(C, fname, prose):
    out = [prose.rstrip(), '', '## Register']
    for b, rows in batches(C, fname):
        out += ['', f"### Batch {b['label']}", '']
        out.append(md_table(b['order'], [[c[f] for f in b['order']] for c in rows]))
    return ('\n'.join(out) + '\n').encode('utf-8')

def w_html(C, fname, prose_html):
    out = ['<!DOCTYPE html>', '<html><head><meta charset="utf-8"><title>' + xesc(fname) + '</title></head><body>', prose_html]
    for b, rows in batches(C, fname):
        out.append(f'''<table class="register" data-batch="{b['label']}">''')
        out.append('<thead><tr>' + ''.join((f'<th>{xesc(f)}</th>' for f in b['order'])) + '</tr></thead><tbody>')
        for c in rows:
            out.append('<tr>' + ''.join((f'<td>{xesc(c[f])}</td>' for f in b['order'])) + '</tr>')
        out.append('</tbody></table>')
    out.append('</body></html>')
    return ('\n'.join(out) + '\n').encode('utf-8')

def _wp(text, style=None):
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ''
    return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{xesc(text)}</w:t></w:r></w:p>'

def _wtbl(head, rows):

    def tr(cells):
        return '<w:tr>' + ''.join((f'<w:tc><w:p><w:r><w:t xml:space="preserve">{xesc(c)}</w:t></w:r></w:p></w:tc>' for c in cells)) + '</w:tr>'
    return '<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr>' + tr(head) + ''.join((tr(r) for r in rows)) + '</w:tbl>'

def w_docx(C, fname, prose):
    body = [_wp(fname, 'Title')]
    for para in prose.strip().split('\n\n'):
        body.append(_wp(para.replace('\n', ' ')))
    for b, rows in batches(C, fname):
        body.append(_wp(f"Batch {b['label']}", 'Heading2'))
        body.append(_wtbl(b['order'], [[c[f] for f in b['order']] for c in rows]))
    doc = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + ''.join(body) + '<w:sectPr/></w:body></w:document>'
    ct = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
    rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    return zip_members([('[Content_Types].xml', ct), ('_rels/.rels', rels), ('word/document.xml', doc)])

def _col(i):
    s = ''
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s

def _sheet(rows):
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
    for ri, row in enumerate(rows, start=1):
        cells = []
        for ci, v in enumerate(row):
            ref = f'{_col(ci)}{ri}'
            if isinstance(v, tuple):
                cells.append(f'<c r="{ref}"><v>{v[0]}</v></c>')
            elif v == '':
                continue
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{xesc(v)}</t></is></c>')
        out.append(f'<row r="{ri}">' + ''.join(cells) + '</row>')
    out.append('</sheetData></worksheet>')
    return ''.join(out)

def w_xlsx(C, fname):
    tables = [t for t, _ in FILES[fname][2]]
    by_table = {t: [] for t in tables}
    for b, rows in batches(C, fname):
        flds = [f for f, _ in fields_of(fname, b['table'])]
        for cells in rows:
            row = [b['label']]
            for f in flds:
                v = cells[f]
                cv = b['conv'].get(f, '')
                if isinstance(cv, str) and cv.startswith('xl') and v and v[0].isdigit():
                    row.append((v,))
                else:
                    row.append(v)
            by_table[b['table']].append(row)
    sheets = [(t, [['batch'] + [f for f, _ in fields_of(fname, t)]] + by_table[t]) for t in tables]
    wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>']
    rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">', '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>', '<Default Extension="xml" ContentType="application/xml"/>', '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>']
    members = []
    for i, (name, rows) in enumerate(sheets, start=1):
        wb.append(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>')
        rels.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')
        ct.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        members.append((f'xl/worksheets/sheet{i}.xml', _sheet(rows)))
    wb.append('</sheets></workbook>')
    rels.append('</Relationships>')
    ct.append('</Types>')
    root = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    return zip_members([('[Content_Types].xml', ''.join(ct)), ('_rels/.rels', root), ('xl/workbook.xml', ''.join(wb)), ('xl/_rels/workbook.xml.rels', ''.join(rels))] + members)

def w_sqlite(C, fname, path):
    if path.exists():
        path.unlink()
    con = _sq.connect(str(path))
    con.execute('PRAGMA journal_mode=OFF')
    for t, _ in FILES[fname][2]:
        cols = ['batch'] + [f for f, _ in fields_of(fname, t)]
        con.execute(f'CREATE TABLE {t} (' + ', '.join((f'{c} TEXT' for c in cols)) + ')')
    for b, rows in batches(C, fname):
        cols = ['batch'] + [f for f, _ in fields_of(fname, b['table'])]
        qy = f"INSERT INTO {b['table']} (" + ','.join(cols) + ') VALUES (' + ','.join(('?' for _ in cols)) + ')'
        con.executemany(qy, [[b['label']] + [c[f] if c[f] != '' else None for f in cols[1:]] for c in rows])
    con.commit()
    con.close()

def _uvar(n):
    out = bytearray()
    while True:
        x = n & 127
        n >>= 7
        if n:
            out.append(x | 128)
        else:
            out.append(x)
            return bytes(out)

def _zz(n):
    return _uvar(n << 1 ^ n >> 63)

class _TC:

    def __init__(self):
        self.b = bytearray()
        self.last = [0]

    def fh(self, fid, typ):
        d = fid - self.last[-1]
        if 0 < d <= 15:
            self.b.append(d << 4 | typ)
        else:
            self.b.append(typ)
            self.b += _zz(fid)
        self.last[-1] = fid

    def i32(self, fid, v):
        self.fh(fid, 5)
        self.b += _zz(v)

    def i64(self, fid, v):
        self.fh(fid, 6)
        self.b += _zz(v)

    def bin(self, fid, s):
        self.fh(fid, 8)
        s = s.encode() if isinstance(s, str) else s
        self.b += _uvar(len(s)) + s

    def begin(self, fid):
        self.fh(fid, 12)
        self.last.append(0)

    def end(self):
        self.b.append(0)
        self.last.pop()

    def lst(self, fid, etype, n):
        self.fh(fid, 9)
        self.b.append(n << 4 | etype if n < 15 else 240 | etype)
        if n >= 15:
            self.b += _uvar(n)

    def sbegin(self):
        self.last.append(0)

    def send(self):
        self.b.append(0)
        self.last.pop()

def w_parquet(C, fname):
    t = FILES[fname][2][0][0]
    cols = ['batch'] + [f for f, _ in fields_of(fname, t)]
    data = {c: [] for c in cols}
    for b, rows in batches(C, fname):
        for cells in rows:
            data['batch'].append(b['label'])
            for f in cols[1:]:
                data[f].append(cells[f])
    nrows = len(data['batch'])
    body = bytearray(b'PAR1')
    chunks = []
    for c in cols:
        page = bytearray()
        for v in data[c]:
            bb = v.encode('utf-8')
            page += _st.pack('<I', len(bb)) + bb
        ph = _TC()
        ph.sbegin()
        ph.i32(1, 0)
        ph.i32(2, len(page))
        ph.i32(3, len(page))
        ph.begin(5)
        ph.i32(1, nrows)
        ph.i32(2, 0)
        ph.i32(3, 3)
        ph.i32(4, 3)
        ph.end()
        ph.send()
        off = len(body)
        body += ph.b + page
        chunks.append((c, off, len(ph.b) + len(page)))
    md = _TC()
    md.sbegin()
    md.i32(1, 1)
    md.lst(2, 12, len(cols) + 1)
    md.sbegin()
    md.bin(4, 'schema')
    md.i32(5, len(cols))
    md.send()
    for c in cols:
        md.sbegin()
        md.i32(1, 6)
        md.i32(3, 0)
        md.bin(4, c)
        md.i32(6, 0)
        md.send()
    md.i64(3, nrows)
    md.lst(4, 12, 1)
    md.sbegin()
    md.lst(1, 12, len(cols))
    total = 0
    for c, off, size in chunks:
        total += size
        md.sbegin()
        md.i64(2, off)
        md.begin(3)
        md.i32(1, 6)
        md.lst(2, 5, 2)
        md.b += _zz(0) + _zz(3)
        md.lst(3, 8, 1)
        md.b += _uvar(len(c)) + c.encode()
        md.i32(4, 0)
        md.i64(5, nrows)
        md.i64(6, size)
        md.i64(7, size)
        md.i64(9, off)
        md.end()
        md.send()
    md.i64(2, total)
    md.i64(3, nrows)
    md.send()
    md.bin(6, 'helios-export 4.1')
    md.send()
    body += md.b + _st.pack('<I', len(md.b)) + b'PAR1'
    return bytes(body)

def _pesc(s):
    return s.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

def _wrap(text, width):
    words, out, cur = (text.split(), [], '')
    for w in words:
        if len(cur) + len(w) + 1 > width:
            out.append(cur)
            cur = w
        else:
            cur = (cur + ' ' + w).strip()
    if cur:
        out.append(cur)
    return out

def w_pdf(C, fname, prose):
    lines = [fname, '']
    for para in prose.strip().split('\n\n'):
        for ln in para.split('\n'):
            lines += _wrap(ln, 110) or ['']
        lines.append('')
    for b, rows in batches(C, fname):
        lines.append(f"BATCH {b['label']}")
        lines.append(' | '.join(b['order']))
        for c in rows:
            lines.append(' | '.join((c[f] for f in b['order'])))
        lines.append('')
    per = 72
    pages = [lines[i:i + per] for i in range(0, len(lines), per)]
    objs = {1: b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>'}
    kids, nid = ([], 4)
    for pg in pages:
        content = 'BT /F1 7 Tf 10.5 TL 28 812 Td ' + ' '.join((f"({_pesc(ln)}) '" for ln in pg)) + ' ET'
        cb = content.encode('latin-1', 'replace')
        objs[nid] = b'<< /Length ' + str(len(cb)).encode() + b' >>\nstream\n' + cb + b'\nendstream'
        objs[nid + 1] = f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 1 0 R >> >> /Contents {nid} 0 R >>'.encode()
        kids.append(nid + 1)
        nid += 2
    objs[2] = f"<< /Type /Pages /Kids [{' '.join((f'{k} 0 R' for k in kids))}] /Count {len(kids)} >>".encode()
    objs[3] = b'<< /Type /Catalog /Pages 2 0 R >>'
    out = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offs = {}
    for i in range(1, nid):
        offs[i] = len(out)
        out += f'{i} 0 obj\n'.encode() + objs[i] + b'\nendobj\n'
    xref = len(out)
    out += f'xref\n0 {nid}\n0000000000 65535 f \n'.encode()
    for i in range(1, nid):
        out += f'{offs[i]:010d} 00000 n \n'.encode()
    out += f'trailer\n<< /Size {nid} /Root 3 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    return bytes(out)

def _tbl(head, rows):
    return md_table(head, [[str(x) for x in r] for r in rows])

def vocab_table():
    rows = []
    for v, convs in sorted(VOCAB.items()):
        for conv, words in sorted(convs.items()):
            if conv == 'word':
                continue
            rows.append([v, conv, ', '.join((f'{a}={b}' for a, b in zip(words, convs['word'])))])
    return _tbl(['vocabulary', 'convention', 'written=canonical'], rows)

CONTRACT_PROSE = '# Helios model-training dependency close: contract for the Q3 2025 exposure close\n\nThis document is the authority for how the exports in this directory are read and for the exact shape of every deliverable of the close.\nWhere another export or document seems to say something different about the shape of a deliverable, this document wins. Rules about the\nsubject matter (which record governs, which source has authority for which field) are stated here and in the documents this contract\nnames, and those rules decide every conflict between sources.\n\n## 1. The close\n\nThe close covers the quarter that starts at 2025-07-01T00:00:00Z and ends at the cut, 2025-10-01T00:00:00Z. The cut is exclusive: an\ninstant is "before the cut" when it is strictly earlier than 2025-10-01T00:00:00Z. Every statement "as of the cut" means the state\nproduced by the records recorded before the cut.\n\nThe close has three logical layers resolved in memory during one run. The source layer resolves six record values, the risk layer\nderives six values from them, and the close layer derives six values from both. Six evidence views are serialised from the same values.\nSection 9 onwards defines every deliverable. No artifact is read back as input to another artifact.\n\n## 2. Sources and their authority\n\nThe exports overlap and conflict. Some values in them are wrong or superseded by design; the rules below decide which value counts.\n\n- The four registry exports (registry_pypi.jsonl, registry_npm.csv, registry_maven.xml, registry_cargo.tsv) are authoritative for the\n  releases of their ecosystem, their publication instants and their registry revisions. yank_notices.mbox carries yank and unyank\n  notices and rename confirmations.\n- registry_mirror.parquet is a mirror snapshot. It is not a source of releases, publication instants, yank state or licences. Its only\n  authority is the quarantine flag: a release whose in-force mirror record says quarantined=true is withdrawn from the close entirely\n  (it is not a release of its package at all).\n- name_aliases.tsv is the package alias register. name_aliases_legacy.tsv is the retired crosswalk; it is authoritative only for alias\n  rows of kind rename whose effective instant is before 2024-01-01T00:00:00Z, and those renames need no rename confirmation. Every other\n  row of the retired crosswalk is ignored.\n- The manifests (manifests_core.csv, manifests_edge.jsonl, manifests_data.yaml, manifests_legacy.txt) hold dependency declarations.\n  A declaration counts only when it sits in the manifest named by its service\'s home manifest in service_catalog.xlsx (core, edge,\n  data or legacy). manifests_snapshot.csv is a frozen copy of the core manifest; it is the source of declarations only for services\n  whose service_catalog.xlsx lifecycle shows an archived event before the cut, and those services take every declaration from it.\n- scanner_findings.jsonl holds container scans. It is the source of runtime pins only for services whose home manifest is image;\n  for every other service its observations are ignored.\n- service_catalog.xlsx is authoritative for services, tiers, regions, home manifests, ownership and lifecycle. service_catalog_final.xlsx\n  is a preview export and is ignored, except its legacy_lifecycle sheet, which is the only lifecycle source for services migrated from\n  the old inventory (services that have no lifecycle row in service_catalog.xlsx take their lifecycle from that sheet; the others ignore it).\n- Deploy telemetry: deploy_events_east.log, deploy_events_west.log and deploy_events_central.log. deploy_events_legacy.log is the retired\n  collector; its events count only for services in region us-central with a corrected event instant before 2025-08-04T00:00:00Z.\n  Services in region global have no collector coverage.\n- Advisories: advisories_osv.jsonl is authoritative for affected ranges and withdrawals. advisories_osv_replay.jsonl is a replayed feed;\n  its events cell is used only for OSV records whose events cell carries the elsewhere sentinel, and nothing else in it counts.\n  advisories_ghsa.json and advisories_nvd.xml carry vectors and publication data. advisories_feed_cache.json is an aggregator cache; it\n  is used only for the vector of a GHSA record whose vector cell carries the elsewhere sentinel (the cache row of the same GHSA identifier\n  and package), and its precomputed scores are never used.\n- Every other export and document is authoritative for its own subject as described in the sections below.\n\n## 3. Time\n\nTimestamps are converted to UTC instants. The zones are:\n\n| zone | rule |\n|---|---|\n| UTC | offset 0 |\n| IE | UTC+0, UTC+1 from the last Sunday of March 01:00 UTC to the last Sunday of October 01:00 UTC |\n| US | UTC-6, UTC-5 from the second Sunday of March 08:00 UTC to the first Sunday of November 07:00 UTC |\n| IN | UTC+5:30 all year |\n| JP | UTC+9 all year |\n| AU | UTC+10, UTC+11 from 16:00 UTC on the Saturday before the first Sunday of October to 16:00 UTC on the Saturday before the first Sunday of April |\n\nA wall-clock value in a zone is the UTC instant whose local time in that zone equals it. Exports never write wall-clock values inside a\ntransition hour. Calendar dates are proleptic Gregorian.\n\n## 4. Records, revisions, errata and the cut\n\nEvery data row of every export (every table row of a document) is one revision of a record and carries four envelope fields: rid (record\nidentifier), rev (revision number, an integer), st (state) and rec_at (the instant the revision was recorded). The canonical states are\nactive, void and draft.\n\n- Revisions of one record share rid within one table of one export. Two rows with the same rid and rev are the same revision written twice.\n- A revision recorded at or after the cut is not applied by the close; it belongs to the deferred register (section 8.6).\n- A draft revision never applies.\n- Of the remaining revisions the one with the highest rev number is in force. When its state is void the record is void and does not\n  exist for the close. A record with no remaining revision does not exist for the close.\n- errata_register.docx holds errata. An erratum applies only when it was issued before the cut and its subject is approved\n  (below). An applying erratum of action void voids its target record; one of action correct replaces the value of the named field of\n  the target\'s in-force revision by the value written in canonical form (section 6). Errata of one target apply in order of issue\n  instant, then rid; a later correction of the same field wins. The target is identified by file and rid.\n- review_minutes.docx holds decisions. A subject (an erratum rid, a lock override rid or a waiver rid) is approved when, among its\n  in-force minute rows decided before the cut, the one with the latest decided instant (then the highest rid) has decision approve.\n\nFor registry releases the history matters: the state of a release at an instant t is that of its latest applicable registry revision\nrecorded before t (applicable means: not draft, and only revisions recorded before the cut). The publication instant of a release is\nthe value of its revision in force at the cut, after errata.\n\n## 5. Reading cells\n\n### 5.1 Batches, layouts and the conventions register\n\nEvery data row carries a batch label (a batch column, key, attribute, header or table heading). In JSON Lines exports a line whose\nonly key is batch opens a batch and labels the rows that follow it. source_conventions.html is the\nconventions register. Its rows are written in canonical form and follow the record rules of section 4. A register row names a file, a\nbatch and a field:\n\n- conv is a convention name: the field\'s cells in that batch are written under that convention.\n- conv @layout: token lists, in order, the column names the batch uses; conv lists the canonical field names in the same order.\n- conv @unknown, @none or @elsewhere: token is the text that stands for that sentinel in that field of that batch.\n\nA field with no in-force register row in a batch is written under its default convention. Default conventions: ts iso, date iso, dec\nplain, int plain, hours h, money minor, bool tf, id canon, svcid canon, pkg canon, ver semver, vid canon, vec canon, spdx canon, events\nsemver, enumerations word. In manifests_legacy.txt a single dot stands for an empty cell. An empty cell is an absent value unless the\nregister gives it a sentinel meaning. A cell that is neither empty, nor a registered sentinel token, nor a value written in the\ndocumented form of its convention (section 5.2) is invalid, and an input directory that carries one is invalid input (section 13); such a\ncell is never read as an absent value. manifests_legacy.txt is encoded in Latin-1; registry_npm.csv, license_overrides.csv and\nfx_fixings.tsv start with a UTF-8 byte order mark; every other text export is UTF-8.\n\nSentinels: unknown means the source records the value as unknown; none means there is deliberately no value (no withdrawal, no end\ndate, no revocation); elsewhere means the value is held by the export named in section 2 for that field.\n\n### 5.2 Conventions\n\n- ts: iso is YYYY-MM-DDTHH:MM:SSZ; off:Z is ISO 8601 with the numeric offset of zone Z; naive:Z is YYYY-MM-DD HH:MM:SS wall clock of zone Z;\n  epoch is Unix seconds; epochms is Unix milliseconds; xl:Z is an Excel serial day number (days since 1899-12-30, the fraction is the\n  time of day) of the wall clock of zone Z; xl4:Z is the same counted from 1904-01-01; dmy:Z is DD/MM/YYYY HH:MM and mdy:Z is\n  MM/DD/YYYY HH:MM, wall clock of zone Z. Serial values are rounded to the nearest minute.\n- date: iso YYYY-MM-DD; dmy DD.MM.YYYY; mdy MM/DD/YYYY; compact YYYYMMDD; xl Excel serial day (days since 1899-12-30).\n- dec: plain uses a dot decimal point; de uses dot thousands separators and a comma decimal point; fr uses space thousands separators and\n  a comma decimal point.\n- int: plain; grouped uses comma thousands separators; de uses dot thousands separators; neg writes the negated value.\n- hours: h decimal hours; min a whole number of minutes (an integer); hm like 2h30m; iso ISO 8601 duration like PT2H30M.\n- money (an amount in the currency of the row): minor is integer minor units; major is a decimal amount in major units; de is a major\n  amount with dot thousands separators and comma decimal point; paren is a major amount with negatives in parentheses. Minor units:\n  EUR, USD, GBP and INR have two decimals, JPY has none.\n- bool: tf true/false; 10 1/0; yn yes/no; YN Y/N; neg writes the negation in true/false form.\n- id: canon; upper upper case; spaced padded with spaces; under writes every hyphen as an underscore (identifiers never contain\n  underscores).\n- svcid (service identifiers): canon is svc- followed by five digits; upper upper case; nopad drops leading zeros of the number; spaced\n  padded with spaces; legacy holds either a canonical identifier or a legacy identifier, resolved through the crosswalk in Appendix A:\n  the crosswalk row of that legacy identifier whose window [valid_from, valid_to) contains the UTC date of the row\'s rec_at.\n- pkg (package names): canon; case changes letter case; sep changes separators; fullwidth replaces a character by its full-width form;\n  zw inserts a zero-width space. case and sep never apply to maven coordinates, which are case sensitive.\n- ver: semver is MAJOR.MINOR.PATCH[-TAG.N]; native is the ecosystem spelling (pypi 1.4.0rc2, 1.4.0a1, 1.4.0b3; maven 1.4.0-RC2,\n  1.4.0-alpha1, 1.4.0-beta3; npm and cargo as semver); vprefix is semver with a leading v; build is semver with +build metadata.\n  Build metadata is never part of a version. TAG is one of alpha, beta, rc.\n- vid: canon; lower lower case; nopad drops leading zeros of a CVE sequence number; spaced padded with spaces.\n- vec: canon is a CVSS vector with its CVSS:3.0/ or CVSS:3.1/ prefix; noprefix drops the prefix of a CVSS:3.1 vector; lower lower case.\n- spdx: canon; lower lower case; deprecated uses deprecated identifiers (GPL-2.0 for GPL-2.0-only, GPL-2.0+ for GPL-2.0-or-later and\n  so on); alias uses the long names of license_policy.md.\n- events: OSV events written kind:version separated by |, kinds introduced, fixed and last_affected, versions spelt semver or native.\n- Enumerations: the word convention writes the canonical word; the other conventions are:\n\n| vocabulary | convention | written=canonical |\n|---|---|---|\n| alias_kind | letter | R=rename, S=spelling, T=typo, V=vendor |\n| dec | letter | Y=approve, N=reject, D=defer |\n| eco | alt | pip=pypi, node=npm, mvn=maven, crates=cargo |\n| eco | upper | PYPI=pypi, NPM=npm, MAVEN=maven, CARGO=cargo |\n| err | upper | VOID=void, CORRECT=correct |\n| home | upper | CORE=core, EDGE=edge, DATA=data, LEGACY=legacy, IMAGE=image |\n| jkind | letter | O=opening, A=adjust, R=reversal |\n| life | letter | A=archived, X=decommissioned, R=restored, P=paused, N=renamed |\n| lstat | letter | D=decided, P=proposed, W=withdrawn |\n| notice | upper | YANK=yank, UNYANK=unyank, RENAME=rename |\n| outcome | alt | ok=succeeded, error=failed, rollback=rolled_back |\n| outcome | letter | S=succeeded, F=failed, R=rolled_back |\n| region | alt | euw1=eu-west, usc1=us-central, aps1=ap-south, apn1=ap-north, apse1=ap-southeast, glb=global |\n| role | letter | O=owner, M=maintainer, R=reviewer |\n| scope | alt | prod=runtime, development=dev, testing=test |\n| scope | letter | R=runtime, D=dev, T=test |\n| st | code | 1=active, 9=void, 0=draft |\n| st | letter | A=active, V=void, D=draft |\n| vex | alt | NA=not_affected, A=affected, F=fixed, UI=under_investigation |\n\n## 6. Canonical forms\n\nCanonical text of a value: timestamps iso, dates iso, decimals as plain decimals without trailing zeros, hours as decimal hours, integers\nand money as integers (money in minor units), booleans true/false, versions semver without build metadata, OSV events with semver\nversions, licence expressions in the canonical form of license_policy.md, enumerations as their word, service identifiers canonical,\nsentinels as @ followed by their meaning (@unknown, @none, @elsewhere), absent values as the empty string, and every other value as the\ntext after the normalisations of section 7.\n\n## 7. Identities\n\n### 7.1 Services\n\nA service is identified by its canonical identifier (section 5.2 svcid).\n\n### 7.2 Packages\n\nA package is identified by ecosystem:name with the name normalised as follows. All ecosystems: Unicode NFKC, then zero-width spaces\nremoved and surrounding spaces stripped. pypi: lower case, and every run of -, _ and . replaced by a single -. npm: lower case. cargo:\nlower case and _ replaced by -. maven: nothing more (coordinates are case sensitive).\n\nname_aliases.tsv maps an alias name to a target name within an ecosystem. Kind spelling: the alias is another name of the target\nwhenever its effective instant is before the cut. Kind rename: the alias is a former name of the target when the effective instant is\nbefore the cut and a rename notice in yank_notices.mbox whose ref is the alias row\'s rid was sent before the cut (or, for the retired\ncrosswalk rows of section 2, with no notice). Kinds typo and vendor never merge names: a typo or vendor alias is a different package.\nA name that is an alias in force maps to its target; releases published under a former name belong to the target once the rename is in\nforce, and otherwise form a package of their own.\n\n### 7.3 Vulnerabilities\n\nVulnerability identifiers are normalised to upper case prefixes (CVE-, GHSA-, PYSEC-, RUSTSEC-, OSV-), GHSA bodies in lower case and CVE\nsequence numbers with at least four digits. advisory_aliases.csv links identifiers; linked identifiers (transitively) are one\nvulnerability. The canonical identifier of a vulnerability is its CVE identifier, otherwise its GHSA identifier, otherwise its OSV\nidentifier.\n\n## 8. Rules of the close\n\n### 8.1 Releases, yanks and resolution\n\nA release of a package is an in-force registry record not withdrawn by the mirror quarantine. A yank notice sent at instant t sets the\nrelease state yanked (unyank clears it) from t on; the yank state at an instant is given by the most recent of the latest applicable\nregistry revision recorded before the instant and the latest yank notice sent before the instant, a notice winning a tie.\n\nA declaration\'s constraint is written in its ecosystem\'s syntax: npm ^ ~ x-ranges, comparator lists and exact versions; cargo bare\nversions (caret), ^ ~ = * and comma-separated comparators; pypi == ~= .* and comma-separated comparators; maven exact [v], intervals\n[a,b) (a,b] [a,) and bare versions, which are exact. Caret: ^M.m.p admits >=M.m.p <(M+1).0.0 when M>0, >=0.m.p <0.(m+1).0 when M=0 and\nm>0, and >=0.0.p <0.0.(p+1) when M=m=0. Tilde ~M.m.p admits >=M.m.p <M.(m+1).0. pypi ~=M.m admits >=M.m.0 <(M+1).0.0 and ~=M.m.p admits\n>=M.m.p <M.(m+1).0. M.m.x and M.m.* admit >=M.m.0 <M.(m+1).0. Missing version parts are zero. Version precedence is semantic versioning\nprecedence: a prerelease precedes its release, prerelease tags compare alpha < beta < rc and their numbers compare numerically. A\nprerelease satisfies a constraint only when the constraint is an exact pin of it, or its lower bound is a prerelease of the same\nMAJOR.MINOR.PATCH.\n\nThe resolution instant of a declaration is its locked instant. The pinned version is the release of highest precedence that the\nconstraint admits, that was published before the resolution instant and that was not yanked at the resolution instant; an exact pin\nmay select a yanked release. When none qualifies the declaration is unsatisfiable.\n\nA lock override in lock_overrides.toml forces the pinned version when it is approved (section 4), the UTC date 2025-09-30 lies in\n[valid_from, valid_to), and the forced version is a release of the package published before the cut. Its disposition is overridden.\nA declaration is in force for the close when its record is in force; declarations of services that are not active are ignored.\n\n### 8.2 Services\n\nA service\'s tier, region and home manifest come from its in-force service_catalog.xlsx row. Its owning team at the cut is the team of\nits ownership row with the latest effective instant before the cut. Its status at the cut is decommissioned when, among its lifecycle\nevents at instants before the cut, the latest decommissioned or restored event is decommissioned; otherwise it is active. archived,\npaused and renamed events do not change status.\n\nDeploys: a deploy event\'s at value is the collector clock. clock_offsets.txt gives, per collector host and collector-clock UTC date of\nat, the offset in seconds of the collector clock ahead of true time; the true instant is at minus the offset (an offset with no\nin-force row is 0). An event is identified by\nits rid across all collectors. A service\'s deploy count is the number of distinct in-force events with outcome succeeded and true instant\nin the quarter, counted only from collectors with authority (section 2); it is null for a service with no collector coverage.\n\n### 8.3 Vulnerabilities and exposures\n\nAn OSV record names the vulnerability by its OSV identifier and the affected package. A vulnerability is withdrawn when an in-force OSV\nrecord of it carries a withdrawal instant before the cut. Its publication instant comes from the authority order for field published in\nprecedence.yaml: default osv then ghsa; an in-force precedence row for the vulnerability replaces the order. The first source in the order\nthat has an in-force record of the vulnerability gives the value, even when that value is the unknown sentinel (the publication is then\nunknown). A vulnerability published at or after the cut is not part of the close.\n\nAffected ranges: a version is affected by an OSV record when an introduced event (0 means from the start) precedes or equals it and\nthe next event after that introduced event is a fixed event greater than the version, or a last_affected event greater than or equal to\nthe version, or there is no next event.\n\nThe vector of a vulnerability: the latest approved rescore (advisory_rescores.parquet, approved true, scored before the cut) wins.\nOtherwise the authority order for field cvss_vector (default nvd then ghsa, replaced by an in-force precedence row) picks the first\nsource with a vector. For nvd the in-force records of source NVD win over those of source CNA, and within a source the latest modified\ninstant wins. For ghsa the in-force GHSA record\'s vector applies. Base scores follow scoring_methodology.pdf.\n\nAn exposure is a runtime pin with a pinned version of an active service, and a vulnerability of the close (not withdrawn, published\nbefore the cut or unknown) that affects that version through an OSV record of the pin\'s package. Its status is not_affected when the\nlatest vex_statements.xml statement for the service and vulnerability issued before the cut has status not_affected; otherwise waived\nwhen a waiver in waivers.db for the service and vulnerability is approved, was granted before the cut and expires at or after the cut;\notherwise open. Statuses affected, fixed and under_investigation of a statement change nothing.\n\ndays_open, sla_days, breach and estimate follow sla_policy.pdf and scoring_methodology.pdf. The figures those documents state\n(the targets by severity and tier, the holidays by region, the base hours by severity and the tier weights) are facts of the corpus:\nthey are read from the documents of the input directory, and another corpus may state different figures. fixed is the release of lowest precedence above\nthe pinned version that is published before the cut, not yanked at the cut and not affected; null when there is none.\n\n### 8.4 Licences\n\nThe licence of a release is the expression of the latest approved licence override (license_overrides.csv, status decided, decided\nbefore the cut) whose range admits the release, ranges admitting prereleases too; otherwise the expression of the latest scan of the\nrelease scanned before the cut; otherwise NOASSERTION. Its obligation class follows license_policy.md, unless an exception in\nlicense_policy.md whose range admits the release is granted on or before 2025-09-30 and not revoked on or before 2025-09-30, in which\ncase the class is the exception\'s class (the latest granted exception wins).\n\n### 8.5 Teams and the ledger\n\nTeams are the in-force teams rows of engineer_roster.ini. Capacity of a team of model capped is the floor of the sum, over its in-force\nallocations, of fte x 8 x the number of Monday-to-Friday UTC dates of the quarter inside [start, end) x (1 - oncall); uncapped teams have no\ncapacity (null). A team\'s engineers are the distinct engineers with an in-force allocation overlapping the quarter.\n\nLedger amounts are EUR cents. A timesheet entry costs hours x the engineer\'s hourly rate (engineer_rates.xlsx, for the calendar month of\nworked; months after September use the September rate) converted to EUR, as a spend (negative). Journal entries convert their amount.\nConversion uses the latest in-force fixing of fx_fixings.tsv at or before the instant (EUR per unit; EUR converts at 1); the EUR amount\nis rounded once, half to even, to whole cents. A timesheet entry belongs to the team of the engineer\'s in-force allocation covering the\nUTC date of worked. A journal reversal that is in force cancels itself and the entry it reverses. Openings are the journal entries of kind\nopening. The closing balance of a team is its openings plus all its in-force entries booked before the cut.\n\n### 8.6 Controls, custody and the deferred register\n\ncontrol_totals.html publishes control figures. Its in-force rows are carried into the stage-1 ledger as published.\n\nCustody of an export: records is its number of data rows; in_force is the number of records in force at the cut after errata;\nreceived_crc is the CRC-32 (zlib) of the concatenation, in written order, of every data row\'s canonical line followed by a line feed;\ninforce_crc is the same over the canonical lines of the in-force revisions after errata, ordered by table in the order the export\ndefines them and then by rid. A canonical line joins with | the rid, the rev, the canonical state, the canonical rec_at and the canonical\ntext of every other field in the order the export defines them (for errata-corrected fields the corrected text). Written order is file\norder, sheets and tables in their stored order.\n\nThe deferred register lists every non-draft revision recorded at or after the cut in advisory_rescores.parquet, remediation_timesheets.csv,\nledger_journal.db, waivers.db, vex_statements.xml and lock_overrides.toml. action is new when the record has no applicable revision, void\nfor a void revision, revise otherwise. For rescores the target is the canonical vulnerability; measure is cvss when the revision is\napproved and not void (current: the vulnerability\'s base score as of the cut; amended: the score of the revision\'s vector), otherwise\nnone. For timesheets and journal entries the target is the team (timesheets: the team of the allocation covering the revision\'s worked\ndate) and measure is cents (current: the entry\'s amount as of the cut, null when the entry is not in force or cancelled; amended: the\namount under the revision, null when the revision is void; post-cut instants convert at the latest in-force fixing). For the other\nthree exports the target is the service and the measure none.\n\n## 9. Deliverables: general rules\n\nStage 1, stage 2 and stage 3 name the source, risk and close layers; "the stage-1 files" and "the stage-2 files" mean the source-layer\nand risk-layer artifacts exactly as this run serialises them. The program writes all twenty-four artifacts into its output directory.\nText is UTF-8 with line feeds and a final line feed.\n\n- JSON Lines files hold one JSON object per line with the keys in the order listed; no spaces outside strings.\n- JSON documents are one object with the keys in the order listed, in the two-space layout: an object or list opens on the line of its\n  key, each member follows on its own line indented two spaces deeper than the line that opened it ("key": value in objects), members\n  are separated by a comma at the end of the line, and the closing brace or bracket stands alone at the indentation of the opening\n  line; an empty object or list is {} or [], and an object inside a list is written on one line exactly as in JSON Lines.\n- Absent values are null. Timestamps are canonical iso, dates YYYY-MM-DD, versions semver.\n- A decimal field is a JSON number written with exactly the listed number of decimals, rounded half to even at that step. Downstream\n  stages compute from the decimal values as written upstream, never from a fresh derivation.\n- Every stage-2 document carries upstream: an object whose keys are "p1/" followed by the file name of each of the six stage-1 files\n  (for example p1/packages.jsonl), in stage-1 file order, each mapped to the lower-case hexadecimal SHA-256 of that file\'s exact bytes.\n  Every stage-3 document carries upstream with the same six p1/ keys followed by "p2/" keys for the six stage-2 files (for example\n  p2/package_risk.json), twelve keys in all.\n- The stage-1 sequence is the concatenation, in this order, of packages.jsonl, pins.jsonl, exposures.jsonl, services.jsonl,\n  teams.csv and ledger.jsonl, each in written row order. Ordered computations below walk it.\n- A written null and a written zero are different facts: null is absent or unknown, zero is a measured zero.\n- Audit rows. In the rules below, "one row per ..." counts data rows. After its data rows every stage-1 JSON Lines file carries 1,000\n  audit lines, every stage-2 and stage-3 document carries an evidence key, and teams.csv carries 1,000 audit rows. Readers of an\n  artifact skip audit lines and audit rows. They are defined in section 12.7.\n\n## 10. Stage 1\n\n### 10.1 packages.jsonl\n\nOne row per package that has at least one release published before the cut, ordered by package. Keys: package (ecosystem:name),\necosystem, owner_team (team of the latest owner-role row of package_owners.json effective before the cut; null when none), releases\n(releases published before the cut), yanked (of those, yanked at the cut), latest (highest-precedence release that is not a prerelease\nand not yanked at the cut; null when none), latest_license (licence of latest, canonical; null when latest is null), obligation (class of\nlatest_license for that release; null when latest is null).\n\n### 10.2 pins.jsonl\n\nOne row per in-force declaration of an active service from its authoritative source, plus one row per scanner observation of an image\nservice (the latest scan before the cut of each package), ordered by service, package, scope. Keys: service, package, scope, constraint\n(the canonical interval: =V for exact pins, otherwise >= or > lower bound and < or <= upper bound separated by one space; null for scanner\nrows), source (file name of the declaration\'s export), pinned (version or null), disposition (pinned, unsatisfiable, overridden or\nobserved), license and obligation of the pinned release for runtime pins (null for other scopes and when pinned is null).\n\n### 10.3 exposures.jsonl\n\nOne row per exposure, ordered by service, package, vuln. Keys: service, package, version, vuln (canonical), cvss (1 decimal), severity,\nstatus, published (the local date of the publication instant in the zone of the service\'s region; null when unknown), days_open (integer\nor null), sla_days (integer), breach (boolean), estimate (2 decimals), fixed (version or null).\n\n### 10.4 services.jsonl\n\nOne row per service of service_catalog.xlsx, ordered by service. Keys: service, team, tier, region, status, deploys (integer or null),\nweight (4 decimals, scoring_methodology.pdf).\n\n### 10.5 teams.csv\n\nHeader team,model,capacity_hours,engineers, one row per team ordered by team; an empty capacity_hours cell is null.\n\n### 10.6 ledger.jsonl\n\nRows in this order: opening rows (ordered by team), entry rows (ordered by booked then entry), closing rows (ordered by team, one per team),\ncontrol rows (ordered by control), custody rows (ordered by file, one per export), deferred rows (ordered by recorded then amendment).\n\n- opening: kind, team, entry (journal rid), amount_cents.\n- entry: kind, entry (rid), team, source (file name), booked (worked or booked instant), amount_cents. Openings and cancelled entries are\n  not entry rows.\n- closing: kind, team, amount_cents.\n- control: kind, control, scope, measure, value.\n- custody: kind, file, records, in_force, received_crc, inforce_crc (CRCs as eight lower-case hexadecimal digits).\n- deferred: kind, amendment (file#rid#rev), file, rid, rev, recorded, action, target, measure, current, amended (cvss values with 1\n  decimal, cents as integers, null when absent).\n\n## 11. Stage 2 (derived only from the six stage-1 files)\n\nOpen exposures are the exposures rows with status open, in written order. The weight of an exposure is the weight of its service row.\nrisk sums cvss x weight over the rows concerned. share is a value divided by the total of the same value over all rows of the\nlist (0 when the total is 0). dense_rank ranks by the named value descending, equal values sharing a rank, ranks consecutive.\npct_rank is (number of rows with a smaller value) / (rows - 1), 0 for a single row.\n\n### 11.1 package_risk.json\n\nKeys: upstream, rows, totals. rows: one per package with at least one open exposure, ordered by package: package, open, max_cvss (1 decimal),\nrisk (6), share (6, of risk), pct_rank (6, of risk), dense_rank (of risk). totals: packages, risk (6, sum of the rows\' risk).\n\n### 11.2 service_risk.json\n\nKeys: upstream, rows, totals. rows: one per active service in services.jsonl order: service, team, open, risk (6), share (6), dense_rank,\nbreaches (open exposures with breach true). totals: services, risk (6).\n\n### 11.3 remediation_plan.json\n\nKeys: upstream, rows, totals. rows: one per open exposure in stage-1 sequence order: seq (1-based), service, package, vuln, severity,\nestimate (2), team (the service\'s team), team_hours (2), pool_hours (2), unallocated (2), team_remaining (2, null for teams without\ncapacity), pool_remaining (2). The fold: each team starts with its capacity_hours (null means unlimited, zero means none); the pool starts\nwith the value of the stage-1 control row of scope global and measure pool_hours. Only the first 6 open exposures of each\nservice, in sequence order, are eligible; others get nothing. An eligible row takes team_hours = the estimate capped by the team\'s\nremaining hours (all of it for an unlimited team); a critical or high row then takes pool_hours = the rest capped by the remaining pool.\nunallocated is what is left. totals: team_hours, pool_hours, unallocated (2 decimals each), pool_cap (integer).\n\n### 11.4 team_rollup.json\n\nKeys: upstream, rows. rows: one per teams.csv row in order: team, services (active services of the team), open, risk (6), share (6),\ndense_rank (of risk), balance, held, held_entries. Ledger fold: walk the stage-1 ledger rows in written order; a team\'s balance starts\nat the sum of its opening rows; an entry row that would take its team\'s balance below zero is held (added to held, counted in\nheld_entries) and leaves the balance unchanged; any other entry row is added to the balance.\n\n### 11.5 license_summary.json\n\nKeys: upstream, classes, teams. classes: one per class in the order permissive, weak, strong, network, unknown, over runtime pins with a\npinned version: class, pins, packages (distinct packages), share (6, of pins). teams: one per teams.csv row: team, strong (runtime pins\nof the team\'s services with obligation strong or network), dense_rank (of strong).\n\n### 11.6 sla_metrics.json\n\nKeys: upstream, severities. One row per severity in the order critical, high, medium, low, none, over open exposures: severity, open,\nwith_days (rows with a days_open value), nulls (rows with null days_open), zeros (rows with days_open 0), breaches, mean_days (6, over the\ndays_open values; null without values), p50 and p90 (nearest rank: the value at position ceil(p x n) of the sorted values; null without\nvalues), max_days (null without values).\n\n## 12. Stage 3 (derived only from the six stage-1 and six stage-2 files)\n\n### 12.1 release_gates.json\n\nKeys: upstream, rows, totals. rows: one per active service in services.jsonl order: service, team, verdict, reasons. Reasons, listed in\nthis order when they hold: critical_breach (an open exposure of the service is critical with breach true), top_risk (the service\'s\nrisk is above zero and its service_risk dense_rank is at most ceil(0.02 x the number of service_risk rows)),\nunsatisfiable_pin (a runtime pin of the service is unsatisfiable), unfunded_remediation (a critical or high remediation_plan row of the\nservice has unallocated above zero), network_license (a runtime pin of the service has obligation network). verdict is block when\ncritical_breach or top_risk holds, hold when another reason holds, pass otherwise. totals: block, hold, pass.\n\n### 12.2 control_reconciliation.json\n\nKeys: upstream, rows, totals. rows: one per stage-1 control row ordered by control: control, scope, measure, published (the control\nvalue), stage1, stage2, agrees. stage1 and stage2 recompute the measure (null when the stage has no counterpart):\nopen_exposures of a team, service or package: stage1 counts open exposures of the scope in exposures.jsonl, stage2 reads open of the\nscope\'s team_rollup, service_risk or package_risk row (0 when absent); runtime_pins: stage1 counts runtime pins with a pinned version;\nclosing_cents: stage1 the closing row, stage2 balance plus held of team_rollup; capacity_hours: stage1 teams.csv; records and in_force:\nstage1 the custody row of the file; pool_hours: stage2 the remediation_plan pool_cap; total_open: stage1 the number of open exposures,\nstage2 the sum of package_risk open; waived_total: stage1 the number of waived exposures. agrees is true when every non-null stage\nvalue equals published and at least one is non-null. totals: controls, agreeing.\n\n### 12.3 deferred_amendments.json\n\nKeys: upstream, rows, totals. rows: one per stage-1 deferred row in written order: amendment, file, target, measure, current, amended,\nimpact, after. For cvss rows with both values: impact (6) is the sum over open exposures of the target vulnerability of (amended - current)\nx weight, after (6) is the package_risk total risk plus impact. For cents rows: impact is amended minus current (nulls as 0), after is the\nteam\'s closing plus impact (null without a target). Otherwise both are null. totals: amendments, cvss_impact (6), cents_impact.\n\n### 12.4 team_scorecard.json\n\nKeys: upstream, rows. rows: one per teams.csv row: team, risk (team_rollup), capacity (teams.csv), allocated (2, the team\'s\nremediation_plan team_hours), utilization (6, allocated / capacity; null when capacity is null or 0), breaches (sum of the team\'s\nservice_risk breaches), closing (the closing row), balance (team_rollup), score (6, risk x (1 + breaches / (team_rollup open + 1))),\ndense_rank (of score).\n\n### 12.5 certification.json\n\nKeys: upstream, summary. summary: active_services, runtime_pins, open_exposures, critical_breaches (open critical exposures with breach),\nrisk_stage1 (6, sum of cvss x weight over open exposures), risk_packages (6, sum of package_risk row risks), risk_services (6, sum of\nservice_risk row risks), gap_packages (6, risk_packages - risk_stage1), gap_services (6), pool_used (remediation_plan totals pool_hours),\nunallocated (remediation_plan totals unallocated), estimate_total (2, sum of remediation_plan estimates), verdict: certified when\ncritical_breaches is 0 and unallocated is 0, qualified when unallocated is at most 0.05 x estimate_total, withheld otherwise.\n\n### 12.6 chain_audit.json\n\nKeys: upstream, files, checks. files: one per upstream file in stage order (six stage-1 files, then six stage-2 files): file (p1/ or p2/\nfollowed by the file name), rows (stage-1 data rows; for stage-2 documents the length of rows, or of classes or severities), bytes. checks, in this order,\neach check and passed: package_risk_covers_open_packages, service_risk_covers_active_services, plan_covers_open_exposures,\nteam_rollup_covers_teams, license_pins_match, sla_open_matches, risk_totals_agree (package and service risk totals within 0.0000005 per\nrow of both lists), ledger_balances_close (balance plus held equals closing for every team).\n\n\n### 12.7 Audit rows and evidence views\n\nDigest and fold. A digest is lower-case hexadecimal SHA-256 text. For a digest D and a slot i, fold(D, i) is the integer value of the\neight hexadecimal digits of D that start at character position (i mod 56), counting from 0, plus i, all modulo 1000003.\n\nAudit lines of the stage-1 JSON Lines files. D is the SHA-256 of the file\'s data lines (each line with its line feed). For i from 0\nthrough 999 the file then carries one line {"_evidence":{"lineage":{"artifact":{"name":F,"digest":D,"slot":i,"fold":fold(D,i)}},\n"relation_web":{"locators":{"edge_00":L0, ... ,"edge_79":L79}}}}, written like every other line of the file, where F is the file name\nand Lj is the first 20 hexadecimal digits of the SHA-256 of the text F:D:i:j (i and j written as plain integers, edge keys with two\ndigits).\n\nAudit rows of teams.csv. D is the SHA-256 of the team data rows written as JSON Lines with the keys team, model, capacity_hours and\nengineers. For i from 0 through 999 the file then carries the row audit/NNNN,lineage/E/K,G,M where NNNN is i with four digits, E is the\nfirst 12 digits of D, K is i mod 17, G is (the integer value of the first eight digits of D plus i) mod 1000003, and M is i + 1.\n\nEvidence of the stage-2 and stage-3 documents. Each document ends with the key evidence: a list of 1,000 objects, for i from 0 through\n999 {"_evidence":{"lineage":{"artifact":{"name":F,"digest":D,"slot":i,"fold":fold(D,i)}}}}, where F is the file name and D is the\nSHA-256 of the document written without its evidence key.\n\nEvidence views. The six evidence files have 1,200 entries ordered by slot from 0 through 1199. Every entry carries its slot, its\nlineage, the artifact name global-close, the close digest C, fold(C, slot), open_count and risk. C is the SHA-256 of the document\n{"p1": {...}, "p2": {...}, "p3": {...}} in the two-space layout of section 9, where p1 maps each stage-1 file name to its list of data\nrows, and p2 and p3 map each stage-2 and stage-3 file name to its document, all in stage file order and without audit rows or evidence\nkeys; it is the same in every entry. open_count is the number of open exposures\nand risk is the certification risk_stage1 value with six decimals. The identity is the slot plus lineage. The layouts are:\n\n- authority-trace.xml: the line <?xml version="1.0" encoding="UTF-8"?>, the line <close><authority><trace><rows>, one line per entry\n  <row><identity><slot>S</slot></identity><source><name>global-close</name><digest>C</digest></source><value><fold>F</fold>\n  <open_count>O</open_count><risk>R</risk></value></row> written without spaces between elements, and the line\n  </rows></trace></authority></close>.\n- rollup-ledger.tsv: the header slot, parent_id, lineage, artifact, digest, fold, open_count, risk separated by tabs, then one row per\n  entry: S, root-NN where NN is slot mod 31 with two digits, close/authority/trace/S/value, global-close, C, F, O, R.\n- reconciliation-map.yaml: the lines close:, reconciliation:, map: and entries: indented by two spaces per level, then per entry\n  "- slot: S" at eight spaces, lineage: at ten, authority: at twelve, name: global-close and digest: C at fourteen, result: at fourteen,\n  and fold: F, open_count: O and risk: R at sixteen.\n- dependency-matrix.ini: per entry the section [close.reconciliation.entry.S.authority.result] followed by the keys name, digest, fold,\n  open_count and risk, written key=value. The first 216 entries also carry dependent, prerequisite, locator_identity (the name),\n  locator_digest (the digest) and locator_fold (the fold). The 216 dependency edges list, for each artifact A[d] of the order six\n  stage-1 files, six stage-2 files, six stage-3 files, authority-trace.xml, rollup-ledger.tsv, reconciliation-map.yaml,\n  dependency-matrix.ini, freeze-register.log, training-closure.md (d from 0 through 23), the prerequisites A[p] for p from\n  max(0, d - w) through d - 1, where w is 13 when d is 13 through 18 and 12 otherwise; entry k carries the k-th edge as dependent A[d]\n  and prerequisite A[p].\n- freeze-register.log: one line per entry: level=INFO correlation=close-NN (slot mod 29, two digits) span=authority-SSSS (slot, four\n  digits) path=close/reconciliation/entry/S/result artifact=global-close digest=C fold=F open_count=O risk=R.\n- training-closure.md: the line # Closure evidence, an empty line, the header | slot | path | artifact | digest | fold | open | risk |,\n  the alignment line |---:|---|---|---|---:|---:|---:|, then one row per entry | S | close/reconciliation/entry/S/result |\n  global-close | C | F | O | R |.\n\nAll are UTF-8 with LF endings and a final newline.\n\n## 13. The program\n\nThe complete close is produced by one invocation:\n\n    python3 build.py DATA_DIR OUT_DIR\n\nThe program reads only DATA_DIR, computes all layers in memory, creates OUT_DIR, and writes the complete set there. It never reads back a\nfile it wrote. Entries of OUT_DIR that are not artifacts of the close (the program itself, for example) are left in place. The set may\nbe staged in a private temporary directory beside OUT_DIR and published in one step. Exit status 0 means success; 2 means wrong arguments; 3 means an input is missing, unreadable or invalid. An error writes\nnothing and prints exactly one line beginning "error: " to standard error. Output is deterministic, idempotent and independent of directory\nnames. Every artifact uses UTF-8, LF endings and a final newline. JSON null is the null form; CSV and TSV use an empty cell.\n\n## Appendix A. Service identifier crosswalk\n'

def contract_md(C):
    s = CONTRACT_PROSE
    return s

def license_md(C):
    cls = _tbl(['identifier', 'class'], [[k, v] for k, v in sorted(SPDX_CLASS.items())])
    exc = _tbl(['exception', 'class'], [[k, v] for k, v in sorted(SPDX_EXCEPTIONS.items())])
    dep = _tbl(['deprecated', 'canonical'], [[k, v] for k, v in sorted(SPDX_DEPRECATED.items())])
    al = _tbl(['long name', 'identifier'], [[k, v] for k, v in sorted(SPDX_ALIASES.items())])
    return f"# Licence policy for runtime dependencies\n\n## Expressions\n\nLicence expressions use SPDX syntax: identifiers combined with AND and OR (AND binds tighter, parentheses group) and WITH followed by an\nexception. Identifiers and operators are case-insensitive. Canonical form: identifiers as listed below, operators in upper case,\nparentheses only around an OR inside an AND, operands in their written order. NOASSERTION and unknown identifiers have class unknown.\n\n## Classes\n\nClasses from least to most restrictive: permissive, weak, strong, network, unknown. An OR expression takes the least restrictive class of\nits operands, an AND expression the most restrictive. An identifier WITH an exception takes the exception's class when the identifier is\nlisted, otherwise unknown.\n\n{cls}\n\n{exc}\n\nDeprecated identifiers read as their canonical identifiers:\n\n{dep}\n\nLong names read as identifiers:\n\n{al}\n\n## Exceptions register\n\nEach exception row grants its class to the releases of its package that its range admits. Its range uses the package ecosystem's\nconstraint syntax.\n"

def scoring_pdf(C):
    tw = ', '.join((f'tier {k}: {v}' for k, v in sorted(TIER_WEIGHT.items())))
    bh = ', '.join((f'{k}: {v}' for k, v in BASE_HOURS.items()))
    return f"Scoring methodology for the Q3 2025 close\n\nBase scores. A CVSS 3.x base score is computed from the vector with the CVSS 3.1 specification formulas. ISS = 1 - (1 - C)(1 - I)(1 - A).\nImpact is 6.42 x ISS when scope is unchanged and 7.52 x (ISS - 0.029) - 3.25 x (ISS - 0.02)^15 when scope is changed. Exploitability is\n8.22 x AV x AC x PR x UI. Weights: AV N 0.85, A 0.62, L 0.55, P 0.2; AC L 0.77, H 0.44; PR N 0.85, L 0.62, H 0.27 when scope is unchanged\nand N 0.85, L 0.68, H 0.5 when scope is changed; UI N 0.85, R 0.62; C, I and A H 0.56, L 0.22, N 0. When impact is at most 0 the score is\n0. Otherwise the score is Roundup(min(impact + exploitability, 10)) for unchanged scope and Roundup(min(1.08 x (impact + exploitability), 10))\nfor changed scope. For CVSS:3.1 vectors Roundup is the CVSS 3.1 Appendix A function: let i = round(x x 100000); when i is divisible by\n10000 the result is i / 100000, otherwise (floor(i / 10000) + 1) / 10. For CVSS:3.0 vectors Roundup is the smallest number with one\ndecimal that is at least x. Severity bands: none 0.0; low 0.1 to 3.9; medium 4.0 to 6.9; high 7.0 to 8.9; critical 9.0 to 10.0.\n\nService weight. weight = tier weight x deploy factor, rounded half to even to 4 decimals. Tier weights: {tw}. The deploy factor is\nmin(2, 1 + deploys / 365); it is 1 when deploys is null.\n\nRemediation estimate. The estimate of an exposure is the estimate override of remediation_estimates.xlsx for the package and the pinned\nversion's major version with the latest effective date on or before 2025-09-30, when there is one. Otherwise it is base hours of the\nseverity x the complexity factor x the upgrade multiplier, rounded half to even to 2 decimals. Base hours: {bh}. The complexity factor is\nthe factor row below for the package and the pinned major version with the latest effective date on or before 2025-09-30, otherwise 1. The\nupgrade multiplier is 3 when there is no fixed version, 2 when the fixed version's major version is above the pinned major version, and 1\notherwise.\n\nComplexity factors"

def sla_pdf(C):
    m = '\n'.join((f'{sev}: tier 0 {v[0]}, tier 1 {v[1]}, tier 2 {v[2]}, tier 3 {v[3]} business days' for sev, v in SLA_MATRIX.items()))
    hol = '\n'.join((f'{reg}: ' + ', '.join((iso_date(z) for z in sorted(HOLIDAYS.get(reg, set())))) for reg in REGIONS))
    zones = ', '.join((f'{r} {z}' for r, z in REGION_ZONE.items()))
    return f"Remediation SLA policy\n\nClock. days_open of an exposure counts business days from the day after its publication date to 2025-09-30 inclusive. The publication\ndate is the local date of the publication instant in the zone of the service's region ({zones}). A business day is a Monday to Friday that is\nnot a holiday of the service's region and not inside an in-force change freeze window of the service (change_freeze.ics; a window covers\nthe UTC dates in [start, end)). days_open is null when the publication is unknown.\n\nTargets. sla_days by severity and tier:\n{m}\nAn in-force override below for the service and severity with the latest effective date on or before 2025-09-30 replaces the target.\nbreach is true when days_open is greater than sla_days; it is false when days_open is null.\n\nHolidays:\n{hol}\n\nOverrides"

def prose_for(C, fname):
    if fname == 'close_contract.md':
        return contract_md(C)
    if fname == 'license_policy.md':
        return license_md(C)
    if fname == 'scoring_methodology.pdf':
        return scoring_pdf(C)
    if fname == 'sla_policy.pdf':
        return sla_pdf(C)
    if fname == 'source_conventions.html':
        return '<h1>Conventions register</h1><p>Rows follow the record rules of close_contract.md section 4; their meaning is defined in section 5.1.</p>'
    if fname == 'control_totals.html':
        return '<h1>Published control figures, Q3 2025</h1><p>Each row publishes one control figure for a scope (a team, an export or global) and a measure. Restated figures carry a higher revision. The figures are reconciled by the close; a published figure is not corrected by the close.</p>'
    if fname == 'errata_register.docx':
        return 'Errata register. Each row targets one record of one export by file and rid. Rules: close_contract.md section 4.'
    if fname == 'review_minutes.docx':
        return 'Training release board minutes. Each row records a decision on one subject. Rules: close_contract.md section 4.'
    if fname == 'lock_overrides.toml':
        return 'Lock overrides: forced versions per service and package.\nApproval and validity rules: close_contract.md section 8.1.'
    return ''

def write_corpus(C, out_dir):
    from pathlib import Path
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    encode_corpus(C)
    for fname in FILE_NAMES:
        fmt = FILES[fname][0]
        p = out_dir / fname
        prose = prose_for(C, fname)
        if fmt == 'csv':
            b = w_delim(C, fname, ',')
        elif fmt == 'tsv':
            b = w_delim(C, fname, '\t')
        elif fmt == 'txt':
            b = w_txt(C, fname)
        elif fmt == 'jsonl':
            b = w_jsonl(C, fname)
        elif fmt == 'json':
            b = w_json(C, fname)
        elif fmt == 'yaml':
            b = w_yaml(C, fname)
        elif fmt == 'xml':
            b = w_xml(C, fname)
        elif fmt == 'log':
            b = w_log(C, fname)
        elif fmt == 'toml':
            b = w_toml(C, fname, prose)
        elif fmt == 'ini':
            b = w_ini(C, fname)
        elif fmt == 'mbox':
            b = w_mbox(C, fname)
        elif fmt == 'ics':
            b = w_ics(C, fname)
        elif fmt == 'md':
            b = w_md(C, fname, prose)
        elif fmt == 'html':
            b = w_html(C, fname, prose)
        elif fmt == 'docx':
            b = w_docx(C, fname, prose)
        elif fmt == 'xlsx':
            b = w_xlsx(C, fname)
        elif fmt == 'parquet':
            b = w_parquet(C, fname)
        elif fmt == 'pdf':
            b = w_pdf(C, fname, prose)
        elif fmt == 'db':
            w_sqlite(C, fname, p)
            continue
        else:
            raise ValueError(fmt)
        p.write_bytes(b)

# ===== verifier: expected stage files are rebuilt from the corpus world model, never read from the agent's inputs =====
import configparser as _configparser
import os as _os
import shutil as _shutil
import signal as _signal
import subprocess as _subprocess
import sys as _sys
import tempfile as _tempfile
import threading as _threading
import time as _time
import xml.etree.ElementTree as _ET
from pathlib import Path

OUT = Path("/app/out")
PROGRAM = OUT / "build.py"
EVAL_SCALE = 0.35
PROBE_SCALE = 0.08
BRANCH_CORPORA = (("verdict-certified", 0.02), ("verdict-qualified", 0.06))
RUN_TIMEOUT = 600
# Every program run shares one budget measured from import, so a slow or hanging program costs the checks that run it
# instead of the whole grading run: the verifier timeout in task.toml is 2700 seconds.
GRADE_BUDGET = 2250
_DEADLINE = _time.monotonic() + GRADE_BUDGET
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
SUPPLEMENTAL = ['authority-trace.xml', 'rollup-ledger.tsv', 'reconciliation-map.yaml', 'dependency-matrix.ini', 'freeze-register.log',
                'training-closure.md']
ARTIFACTS = P1_FILES + P2_FILES + P3_FILES + SUPPLEMENTAL
EVIDENCE_NAME = 'global-close'
_CACHE = {}
_LOCK = _threading.Lock()


def _root_seed():
    return int("0000000036bbbe6d", 16)


# ---------------------------------------------------------------- reference corpora
def _bytes_tree(d):
    return {p.name: p.read_bytes() for p in sorted(Path(d).iterdir()) if p.is_file()}


def _parse_refs(R):
    p1, _ = read_p1(R["dir"] / "p1")
    p2, _ = read_p2(R["dir"] / "p2")
    p3 = {f: json.loads(R["p3"][f].decode("utf-8"), parse_float=Decimal) for f in P3_FILES}
    return {"p1": p1, "p2": p2, "p3": p3, "bytes": R}


def _main():
    if "main" not in _CACHE:
        use_policy(None)
        C = assemble(derive(_root_seed(), "data"), 1.0)
        plan_corpus(C)
        _CACHE["main"] = _parse_refs(reference_outputs(C))
    return _CACHE["main"]


def _branch_corpus(tag, keep):
    if tag not in _CACHE:
        base = Path(_tempfile.mkdtemp(prefix=f"helios-{tag}-"))
        use_policy(derive(_root_seed(), tag))
        C = assemble(derive(_root_seed(), tag), PROBE_SCALE, keep_vulns=keep)
        plan_corpus(C)
        d = base / "exports"
        write_corpus(C, d)
        ref = _parse_refs(reference_outputs(C))
        _open_tree(base)
        _CACHE[tag] = (d, ref)
    return _CACHE[tag]


def _corpus(tag, scale):
    if tag not in _CACHE:
        base = Path(_tempfile.mkdtemp(prefix=f"helios-{tag}-"))
        use_policy(derive(_root_seed(), tag))
        C = assemble(derive(_root_seed(), tag), scale)
        plan_corpus(C)
        d = base / "exports"
        write_corpus(C, d)
        ref = _parse_refs(reference_outputs(C))
        _open_tree(base)
        _CACHE[tag] = (d, ref)
        _CACHE[("world", tag)] = C
    return _CACHE[tag]


# ---------------------------------------------------------------- reading delivered stage files
def _p1(d=None):
    if d is None:
        if ('p1', 'OUT') in _CACHE:
            return _CACHE[('p1', 'OUT')]
        d = Path(_tempfile.mkdtemp(prefix="helios-flat-p1-"))
        try:
            for f in P1_FILES:
                (d / f).write_bytes((OUT / f).read_bytes())
        except OSError:
            return None
    else:
        d = Path(d)
    key = ("p1", "OUT") if d.name.startswith('helios-flat-p1-') else ("p1", str(d))
    if key not in _CACHE:
        try:
            _CACHE[key] = read_p1(d)
        except Exception:
            _CACHE[key] = None
    return _CACHE[key]


def _p2(d=None):
    if d is None:
        if ('p2', 'OUT') in _CACHE:
            return _CACHE[('p2', 'OUT')]
        d = Path(_tempfile.mkdtemp(prefix="helios-flat-p2-"))
        try:
            for f in P2_FILES:
                (d / f).write_bytes((OUT / f).read_bytes())
        except OSError:
            return None
    else:
        d = Path(d)
    key = ("p2", "OUT") if d.name.startswith('helios-flat-p2-') else ("p2", str(d))
    if key not in _CACHE:
        try:
            _CACHE[key] = read_p2(d)
        except Exception:
            _CACHE[key] = None
    return _CACHE[key]


def _p3(d=None):
    d = Path(d) if d else OUT
    key = ("p3", str(d))
    if key not in _CACHE:
        out = {}
        try:
            for f in P3_FILES:
                out[f] = json.loads((d / f).read_bytes().decode("utf-8"), parse_float=Decimal)
            _CACHE[key] = out
        except Exception:
            _CACHE[key] = None
    return _CACHE[key]


def _same(a, b):
    if b is None:
        return a is None
    if isinstance(b, bool):
        return a is b
    if isinstance(b, Decimal):
        return isinstance(a, (Decimal, int)) and not isinstance(a, bool) and Decimal(a) == b
    if isinstance(b, int):
        return type(a) is int and a == b
    if isinstance(b, list):
        return isinstance(a, list) and len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(b, dict):
        return isinstance(a, dict) and set(a) == set(b) and all(_same(a[k], b[k]) for k in b)
    return a == b


def _keyed(rows, keys):
    out = {}
    for r in rows:
        if not isinstance(r, dict) or any(k not in r for k in keys):
            return None
        k = tuple(r[x] for x in keys)
        if k in out:
            return None
        out[k] = r
    return out


def _rows_equal(got, exp, keys, fields, ordered=False):
    if not isinstance(got, list):
        return False
    if ordered:
        return len(got) == len(exp) and all(isinstance(g, dict) and all(_same(g.get(f, "<absent>"), e[f]) for f in fields + keys)
                                            for g, e in zip(got, exp))
    g = _keyed(got, keys)
    e = _keyed(exp, keys)
    if g is None or set(g) != set(e):
        return False
    return all(all(_same(g[k].get(f, "<absent>"), e[k][f]) for f in fields) for k in e)


def _p1_rows(name, kinds=None, d=None):
    got = _p1(d)
    assert got is not None
    rows = got[0][name]
    if kinds:
        rows = [r for r in rows if isinstance(r, dict) and r.get("kind") in kinds]
    return rows


def _check_p1(name, keys, fields, kinds=None, ordered=True, ref=None):
    ref = ref or _main()
    exp = ref["p1"][name]
    if kinds:
        exp = [r for r in exp if r["kind"] in kinds]
    assert _rows_equal(_p1_rows(name, kinds), exp, keys, fields, ordered)


def _near_sets(got, exp):
    """At least 95 percent of the expected identities present and extra identities at most 5 percent of them."""
    shared = got & exp
    return len(shared) * 20 >= len(exp) * 19 and (len(got) - len(shared)) * 20 <= len(exp)


def _rows_match_shared(got, exp, keys, fields):
    if not isinstance(got, list):
        return False
    g = _keyed(got, keys)
    e = _keyed(exp, keys)
    if g is None or e is None or not _near_sets(set(g), set(e)):
        return False
    return all(all(_same(g[k].get(f, "<absent>"), e[k][f]) for f in fields) for k in set(g) & set(e))


def _check_p1_members(name, keys, fields):
    assert _rows_equal(_p1_rows(name), _main()["p1"][name], keys, fields)


def _check_p1_shared(name, keys, fields):
    assert _rows_match_shared(_p1_rows(name), _main()["p1"][name], keys, fields)


STAGE1_IDS = {'packages.jsonl': ['package'], 'pins.jsonl': ['service', 'package', 'scope'],
              'exposures.jsonl': ['service', 'package', 'vuln'], 'services.jsonl': ['service'], 'teams.csv': ['team']}
LEDGER_KINDS = ('opening', 'entry', 'closing', 'control', 'custody', 'deferred')


def _stage1_usable(got, exp):
    """True when a delivered source layer is close enough to the reference for its risk and close layers to be graded as its own function."""
    for f, keys in STAGE1_IDS.items():
        g = _keyed(got[f], keys)
        e = _keyed(exp[f], keys)
        if g is None or e is None or not _near_sets(set(g), set(e)):
            return False
    for kind in LEDGER_KINDS:
        n_got = sum(1 for r in got['ledger.jsonl'] if isinstance(r, dict) and r.get('kind') == kind)
        n_exp = sum(1 for r in exp['ledger.jsonl'] if r['kind'] == kind)
        if abs(n_got - n_exp) * 20 > n_exp:
            return False
    return True


def _as_written(docs):
    return {f: json.loads(doc_bytes(docs[f]).decode("utf-8"), parse_float=Decimal) for f in docs}


def _own_function(s, stage):
    assert _ok(s["run"]) and s["p1"] is not None and s["p2"] is not None
    assert _stage1_usable(s["p1"][0], s["ref"]["p1"])
    (p1, raw1), (p2, raw2) = s["p1"], s["p2"]
    return _as_written(ref_stage2(p1, raw1) if stage == 2 else ref_stage3(p1, raw1, p2, raw2))


# ---------------------------------------------------------------- running the delivered program
def _grant_read(argument):
    if not str(argument).startswith("/app"):
        return
    p = Path(argument)
    if not p.exists():
        return
    try:
        p.chmod(p.stat().st_mode | (0o555 if p.is_dir() else 0o444))
        for parent in p.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if str(parent) == "/app":
                break
    except OSError:
        pass


def _untrusted_command(command):
    if _os.name == "posix" and _os.geteuid() == 0:
        for argument in command:
            _grant_read(argument)
        return [*_SETPRIV, *command]
    return command


def _open_tree(path):
    for dirpath, dirnames, filenames in _os.walk(path):
        _os.chmod(dirpath, 0o777)
        for f in filenames:
            _os.chmod(_os.path.join(dirpath, f), 0o666)


def _run(args, cwd):
    """Run the delivered program in a child process as an unprivileged user; the whole process group dies afterwards."""
    if not PROGRAM.is_file():
        return None
    remaining = _DEADLINE - _time.monotonic()
    if remaining < 5:
        return None
    cmd = _untrusted_command([_sys.executable, "-I", str(PROGRAM), *[str(a) for a in args]])
    try:
        proc = _subprocess.Popen(cmd, cwd=str(cwd), stdout=_subprocess.PIPE, stderr=_subprocess.PIPE, start_new_session=True,
                                 env={"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": str(cwd)})
    except OSError:
        return None
    try:
        out, err = proc.communicate(timeout=min(RUN_TIMEOUT, remaining))
    except _subprocess.TimeoutExpired:
        out, err = b"", b"timeout"
    finally:
        try:
            _os.killpg(proc.pid, _signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
        proc.wait()
    return {"code": proc.returncode, "stdout": out, "stderr": err}


def _ok(run):
    return run is not None and run["code"] == 0


def _scratch(tag):
    d = Path(_tempfile.mkdtemp(prefix=f"helios-run-{tag}-"))
    _open_tree(d)
    return d


def _staged(tag):
    """Run the delivered one-pass program over a verifier-built unseen corpus and parse what it wrote."""
    key = ("staged", tag)
    if key not in _CACHE:
        d, ref = _corpus("eval", EVAL_SCALE)
        base = _scratch(tag)
        out = base / "complete"
        run = _run([d, out], base)
        listing = sorted(p.name for p in base.iterdir())
        p1d = base / "source"
        p2d = base / "risk"
        p1d.mkdir()
        p2d.mkdir()
        parsed = _ok(run) and out.is_dir() and all((out / f).is_file() for f in P1_FILES + P2_FILES)
        if parsed:
            for f in P1_FILES:
                (p1d / f).write_bytes((out / f).read_bytes())
            for f in P2_FILES:
                (p2d / f).write_bytes((out / f).read_bytes())
        _CACHE[key] = {"base": base, "run": run, "ref": ref, "listing": listing,
                       "p1": _p1(p1d) if parsed else None,
                       "p2": _p2(p2d) if parsed else None,
                       "p3": _p3(out) if parsed else None,
                       "out": out, "data": d}
    return _CACHE[key]


def _repeat():
    """True when a second run over the same input writes the same bytes, False when it differs, None when either run failed."""
    key = ("repeat",)
    if key not in _CACHE:
        result = None
        s = _staged("three")
        if _ok(s["run"]):
            base = _scratch("repeat")
            r = _run([s["data"], base / "again"], base)
            if _ok(r):
                try:
                    result = _bytes_tree(base / "again") == _bytes_tree(s["out"])
                except OSError:
                    result = None
        _CACHE[key] = result
    return _CACHE[key]


def _eval_p1():
    key = ("evalp1",)
    if key not in _CACHE:
        d, ref = _corpus("eval", EVAL_SCALE)
        staged = _staged("eval-complete")
        _CACHE[key] = {"run": staged["run"], "p1": staged["p1"], "ref": ref, "base": staged["base"]}
    return _CACHE[key]


def _eval_rows_equal(name, keys, fields, kinds=None):
    e = _eval_p1()
    assert e["p1"] is not None
    got = e["p1"][0][name]
    exp = e["ref"]["p1"][name]
    if kinds:
        got = [r for r in got if isinstance(r, dict) and r.get("kind") in kinds]
        exp = [r for r in exp if r["kind"] in kinds]
    assert _rows_equal(got, exp, keys, fields, kinds is not None)


# ---------------------------------------------------------------- source-layer checks (the delivered files of the shipped corpus)
def _check_p1_packages_releases():
    _check_p1_members("packages.jsonl", ["package"], ["ecosystem", "releases", "yanked"])


def _check_p1_packages_latest():
    _check_p1_shared("packages.jsonl", ["package"], ["latest", "latest_license", "obligation", "owner_team"])


def _check_p1_pins_rows():
    _check_p1_members("pins.jsonl", ["service", "package", "scope"], ["constraint", "source"])


def _check_p1_pins_resolution():
    _check_p1_shared("pins.jsonl", ["service", "package", "scope"], ["pinned", "disposition"])


def _check_p1_pins_license():
    _check_p1_shared("pins.jsonl", ["service", "package", "scope"], ["license", "obligation"])


def _check_p1_exposures_rows():
    _check_p1_members("exposures.jsonl", ["service", "package", "vuln"], ["version"])


def _check_p1_exposures_cvss():
    _check_p1_shared("exposures.jsonl", ["service", "package", "vuln"], ["cvss", "severity"])


def _check_p1_exposures_status():
    _check_p1_shared("exposures.jsonl", ["service", "package", "vuln"], ["status"])


def _check_p1_exposures_clock():
    _check_p1_shared("exposures.jsonl", ["service", "package", "vuln"], ["published", "days_open"])


def _check_p1_exposures_sla():
    _check_p1_shared("exposures.jsonl", ["service", "package", "vuln"], ["sla_days", "breach"])


def _check_p1_exposures_estimate():
    _check_p1_shared("exposures.jsonl", ["service", "package", "vuln"], ["estimate", "fixed"])


def _check_p1_services_catalog():
    _check_p1_members("services.jsonl", ["service"], ["team", "tier", "region", "status"])


def _check_p1_services_weight():
    _check_p1_shared("services.jsonl", ["service"], ["deploys", "weight"])


def _check_p1_teams():
    _check_p1("teams.csv", ["team"], ["model", "capacity_hours", "engineers"])


def _check_p1_ledger_entries():
    exp = [r for r in _main()["p1"]["ledger.jsonl"] if r["kind"] in ("opening", "entry")]
    got = _p1_rows("ledger.jsonl", {"opening", "entry"})
    assert len(got) == len(exp)
    for g, e in zip(got, exp):
        assert all(_same(g.get(k, "<absent>"), e[k]) for k in LEDGER_KEYS[e["kind"]])


def _check_p1_ledger_closing():
    _check_p1("ledger.jsonl", ["team"], ["amount_cents"], kinds={"closing"})


def _check_p1_ledger_controls():
    _check_p1("ledger.jsonl", ["control"], ["scope", "measure", "value"], kinds={"control"})


def _check_p1_ledger_custody():
    _check_p1("ledger.jsonl", ["file"], ["records", "in_force", "received_crc", "inforce_crc"], kinds={"custody"})


def _check_p1_ledger_deferred():
    _check_p1("ledger.jsonl", ["amendment"], ["file", "rid", "rev", "recorded", "action", "target", "measure", "current", "amended"],
              kinds={"deferred"}, ordered=True)


def _check_p1_written_form():
    for f in P1_FILES:
        b = (OUT / f).read_bytes()
        text = b.decode("utf-8")
        assert "\r" not in text and text.endswith("\n")
    got = _p1()
    assert got is not None
    for f, keys in P1_KEYS.items():
        for r in got[0][f]:
            assert list(r) == keys
    for r in got[0]["ledger.jsonl"]:
        assert list(r) == LEDGER_KEYS[r["kind"]]
    for f in ("packages.jsonl", "pins.jsonl", "exposures.jsonl", "services.jsonl", "teams.csv"):
        keys = {"packages.jsonl": ["package"], "pins.jsonl": ["service", "package", "scope"], "exposures.jsonl": ["service", "package", "vuln"],
                "services.jsonl": ["service"], "teams.csv": ["team"]}[f]
        order = [tuple(r[k] for k in keys) for r in got[0][f]]
        assert order == sorted(order)
    kinds = [r["kind"] for r in got[0]["ledger.jsonl"]]
    rank = {"opening": 0, "entry": 1, "closing": 2, "control": 3, "custody": 4, "deferred": 5}
    assert kinds == sorted(kinds, key=lambda k: rank[k])


def _check_eval_p1_packages():
    _eval_rows_equal("packages.jsonl", ["package"], P1_KEYS["packages.jsonl"][1:])


def _check_eval_p1_pins():
    _eval_rows_equal("pins.jsonl", ["service", "package", "scope"], P1_KEYS["pins.jsonl"][3:])


def _check_eval_p1_exposures():
    _eval_rows_equal("exposures.jsonl", ["service", "package", "vuln"], P1_KEYS["exposures.jsonl"][3:])


def _check_eval_p1_services_teams_ledger():
    _eval_rows_equal("services.jsonl", ["service"], P1_KEYS["services.jsonl"][1:])
    _eval_rows_equal("teams.csv", ["team"], TEAMS_HEADER[1:])
    e = _eval_p1()
    got, exp = e["p1"][0]["ledger.jsonl"], e["ref"]["p1"]["ledger.jsonl"]
    assert len(got) == len(exp) and all(_same(g, x) for g, x in zip(got, exp))


# ---------------------------------------------------------------- risk-layer checks
# Ground truth for the risk layer: the delivered program runs over an unseen corpus and its risk files are compared with the
# documented function of the source files that same run wrote (once those match the reference source identities within 5 percent),
# so a source-layer slip is charged to the source-layer checks alone; the delivered risk files of the shipped corpus are checked the
# same way against the delivered source files.
def _s2(name):
    s = _staged("two")
    if ("own2",) not in _CACHE:
        _CACHE[("own2",)] = _own_function(s, 2)
    return s["p2"][0][name], _CACHE[("own2",)][name]


def _check_p2_package_risk_values():
    g, e = _s2("package_risk.json")
    assert _rows_equal(g["rows"], e["rows"], ["package"], ["open", "max_cvss", "risk"], ordered=True)


def _check_p2_package_risk_ranks():
    g, e = _s2("package_risk.json")
    assert _rows_equal(g["rows"], e["rows"], ["package"], ["share", "pct_rank", "dense_rank"], ordered=True)


def _check_p2_package_risk_totals():
    g, e = _s2("package_risk.json")
    assert _same(g["totals"], e["totals"])


def _check_p2_service_risk_values():
    g, e = _s2("service_risk.json")
    assert _rows_equal(g["rows"], e["rows"], ["service"], ["team", "open", "risk", "share"], ordered=True)


def _check_p2_service_risk_ranks():
    g, e = _s2("service_risk.json")
    assert _rows_equal(g["rows"], e["rows"], ["service"], ["dense_rank", "breaches"], ordered=True)


def _check_p2_service_risk_totals():
    g, e = _s2("service_risk.json")
    assert _same(g["totals"], e["totals"])


def _check_p2_plan_allocation():
    g, e = _s2("remediation_plan.json")
    assert _rows_equal(g["rows"], e["rows"], ["seq"], ["service", "package", "vuln", "severity", "estimate", "team", "team_hours",
                                                       "pool_hours", "unallocated"], ordered=True)


def _check_p2_plan_balances():
    g, e = _s2("remediation_plan.json")
    assert _rows_equal(g["rows"], e["rows"], ["seq"], ["team_remaining", "pool_remaining"], ordered=True)


def _check_p2_plan_totals():
    g, e = _s2("remediation_plan.json")
    assert _same(g["totals"], e["totals"])


def _check_p2_team_rollup_risk():
    g, e = _s2("team_rollup.json")
    assert _rows_equal(g["rows"], e["rows"], ["team"], ["services", "open", "risk", "share", "dense_rank"], ordered=True)


def _check_p2_team_rollup_fold():
    g, e = _s2("team_rollup.json")
    assert _rows_equal(g["rows"], e["rows"], ["team"], ["balance", "held", "held_entries"], ordered=True)


def _check_p2_license_classes():
    g, e = _s2("license_summary.json")
    assert _same(g["classes"], e["classes"])


def _check_p2_license_teams():
    g, e = _s2("license_summary.json")
    assert _same(g["teams"], e["teams"])


def _check_p2_sla_counts():
    g, e = _s2("sla_metrics.json")
    assert _rows_equal(g["severities"], e["severities"], ["severity"], ["open", "with_days", "nulls", "zeros", "breaches"], ordered=True)


def _check_p2_sla_statistics():
    g, e = _s2("sla_metrics.json")
    assert _rows_equal(g["severities"], e["severities"], ["severity"], ["mean_days", "p50", "p90", "max_days"], ordered=True)


def _check_p2_propagation():
    p1 = _p1()
    p2 = _p2()
    assert p1 is not None and p2 is not None
    want = ref_stage2(p1[0], p1[1])
    for f in P2_FILES:
        got = dict(p2[0][f])
        got.pop('evidence', None)
        assert _same(got, json.loads(doc_bytes(want[f]).decode("utf-8"), parse_float=Decimal))


def _check_p2_upstream_binding():
    p1 = _p1()
    p2 = _p2()
    assert p1 is not None and p2 is not None
    want = {f"p1/{f}": sha(p1[1][f]) for f in P1_FILES}
    assert all(isinstance(p2[0][f], dict) and p2[0][f].get("upstream") == want for f in P2_FILES)


# ---------------------------------------------------------------- close-layer checks (same split as the risk layer)
def _s3(name):
    s = _staged("three")
    assert s["p3"] is not None
    if ("own3",) not in _CACHE:
        _CACHE[("own3",)] = _own_function(s, 3)
    return s["p3"][name], _CACHE[("own3",)][name]


def _check_p3_gate_verdicts():
    g, e = _s3("release_gates.json")
    assert _rows_equal(g["rows"], e["rows"], ["service"], ["team", "verdict"], ordered=True)


def _check_p3_gate_totals():
    g, e = _s3("release_gates.json")
    assert _same(g["totals"], e["totals"])


def _check_p3_gate_reasons():
    g, e = _s3("release_gates.json")
    assert _rows_equal(g["rows"], e["rows"], ["service"], ["reasons"], ordered=True)


def _check_p3_reconciliation_stages():
    g, e = _s3("control_reconciliation.json")
    assert _rows_equal(g["rows"], e["rows"], ["control"], ["scope", "measure", "published", "stage1", "stage2"], ordered=True)


def _check_p3_reconciliation_agreement():
    g, e = _s3("control_reconciliation.json")
    assert _rows_equal(g["rows"], e["rows"], ["control"], ["agrees"], ordered=True) and _same(g["totals"], e["totals"])


def _check_p3_deferred_impact():
    g, e = _s3("deferred_amendments.json")
    assert _rows_equal(g["rows"], e["rows"], ["amendment"], ["impact", "after"], ordered=True)


def _check_p3_deferred_totals():
    g, e = _s3("deferred_amendments.json")
    assert _same(g["totals"], e["totals"])


def _check_p3_scorecard_allocation():
    g, e = _s3("team_scorecard.json")
    assert _rows_equal(g["rows"], e["rows"], ["team"], ["allocated", "utilization", "breaches"], ordered=True)


def _check_p3_scorecard_score():
    g, e = _s3("team_scorecard.json")
    assert _rows_equal(g["rows"], e["rows"], ["team"], ["score", "dense_rank"], ordered=True)


def _check_p3_certification_risk():
    g, e = _s3("certification.json")
    keys = ["risk_stage1", "risk_packages", "risk_services", "gap_packages", "gap_services", "pool_used", "unallocated", "estimate_total"]
    assert all(_same(g["summary"].get(k, "<absent>"), e["summary"][k]) for k in keys)


def _check_p3_certification_verdict():
    g, e = _s3("certification.json")
    keys = ["active_services", "runtime_pins", "open_exposures", "critical_breaches", "verdict"]
    assert all(_same(g["summary"].get(k, "<absent>"), e["summary"][k]) for k in keys)


def _check_certification_verdict_chain():
    for tag, keep in BRANCH_CORPORA:
        d, ref = _branch_corpus(tag, keep)
        base = _scratch(tag)
        out = base / "complete"
        run = _run([d, out], base)
        assert _ok(run)
        (p1, raw1), (p2, raw2) = read_p1(out), read_p2(out)
        assert _stage1_usable(p1, ref["p1"])
        want = _as_written(ref_stage3(p1, raw1, p2, raw2))["certification.json"]["summary"]["verdict"]
        got = json.loads((out / "certification.json").read_text(encoding="utf-8"), parse_float=Decimal)["summary"]["verdict"]
        assert got == want


def _check_p3_chain_audit_files():
    # rows and bytes of each upstream file as the same run delivered it
    s = _staged("three")
    assert _ok(s["run"]) and s["p1"] is not None and s["p2"] is not None and s["p3"] is not None
    (p1, raw1), (p2, raw2) = s["p1"], s["p2"]
    main_list = {'package_risk.json': 'rows', 'service_risk.json': 'rows', 'remediation_plan.json': 'rows', 'team_rollup.json': 'rows',
                 'license_summary.json': 'classes', 'sla_metrics.json': 'severities'}
    want = [{'file': 'p1/' + f, 'rows': len(p1[f]), 'bytes': len(raw1[f])} for f in P1_FILES]
    want += [{'file': 'p2/' + f, 'rows': len(p2[f][main_list[f]]), 'bytes': len(raw2[f])} for f in P2_FILES]
    assert _same(s["p3"]["chain_audit.json"]["files"], want)


def _check_p3_chain_audit_checks():
    g, e = _s3("chain_audit.json")
    assert _same(g["checks"], e["checks"])


def _check_p3_propagation():
    p1, p2, p3 = _p1(), _p2(), _p3()
    assert p1 is not None and p2 is not None and p3 is not None
    want = ref_stage3(p1[0], p1[1], p2[0], p2[1])
    for f in P3_FILES:
        got = dict(p3[f])
        got.pop('evidence', None)
        assert _same(got, json.loads(doc_bytes(want[f]).decode("utf-8"), parse_float=Decimal))


def _check_p3_upstream_binding():
    p1, p2, p3 = _p1(), _p2(), _p3()
    assert p1 is not None and p2 is not None and p3 is not None
    want = {f"p1/{f}": sha(p1[1][f]) for f in P1_FILES}
    want.update({f"p2/{f}": sha(p2[1][f]) for f in P2_FILES})
    assert all(isinstance(p3[f], dict) and p3[f].get("upstream") == want for f in P3_FILES)


# ---------------------------------------------------------------- program interface
def _one_error_line(r):
    lines = r["stderr"].decode("utf-8", "replace").strip().splitlines()
    return len(lines) == 1 and lines[0].startswith("error: ")


def _check_stage_errors_are_reported():
    d, ref = _corpus("eval", EVAL_SCALE)
    base = _scratch("broken")
    broken = base / "partial"
    _shutil.copytree(d, broken)
    next(iter(sorted(broken.iterdir()))).unlink()
    _open_tree(base)
    for data_dir, out_dir in ((broken, base / "out"), (base / "no-such-exports", base / "out-missing")):
        r = _run([data_dir, out_dir], base)
        assert r is not None and r["code"] == 3 and _one_error_line(r)
        assert not out_dir.exists() or not any(out_dir.iterdir())


def _check_wrong_argument_count_is_reported():
    d, ref = _corpus("eval", EVAL_SCALE)
    base = _scratch("args")
    r = _run([d], base)
    assert r is not None and r["code"] == 2 and _one_error_line(r)
    assert sorted(p.name for p in base.iterdir()) == []


def _corrupted(tag, fname, field, pick):
    """A copy of the unseen corpus in which one cell of field `field` of the delimited export `fname` is rewritten.

    pick(batch, cells) returns the replacement text for the first row it accepts, or None to pass the row over."""
    d, ref = _corpus("eval", EVAL_SCALE)
    C = _CACHE[("world", "eval")]
    base = _scratch(tag)
    bad = base / "exports"
    _shutil.copytree(d, bad)
    saved = C.cells[fname]
    done = False
    try:
        rewritten = []
        for b, rows in saved:
            out_rows = []
            for cells in rows:
                text = None if done else pick(b, cells)
                if text is not None:
                    cells = dict(cells)
                    cells[field] = text
                    done = True
                out_rows.append(cells)
            rewritten.append((b, out_rows))
        C.cells[fname] = rewritten
        (bad / fname).write_bytes(w_delim(C, fname, "\t" if fname.endswith(".tsv") else ","))
    finally:
        C.cells[fname] = saved
    assert done
    _open_tree(base)
    return base, bad


def _rejects(base, bad):
    r = _run([bad, base / "out"], base)
    assert r is not None and r["code"] == 3
    assert not (base / "out").exists() or not any((base / "out").iterdir())
    lines = r["stderr"].decode("utf-8", "replace").strip().splitlines()
    assert len(lines) == 1 and lines[0].startswith("error: ")


def _plain(b, cells, field):
    text = cells.get(field, "")
    return bool(text) and text not in set(b["sent"].values())


def _check_invalid_cell_is_reported():
    # a yanked flag that no boolean convention writes; read as absent it would silently mean "not yanked"
    base, bad = _corrupted("badcell", "registry_npm.csv", "yanked", lambda b, c: "maybe" if _plain(b, c, "yanked") else None)
    _rejects(base, bad)


def _check_fractional_minutes_are_invalid():
    base, bad = _corrupted("badmin", "remediation_timesheets.csv", "hours",
                           lambda b, c: c["hours"] + ".5" if b["conv"].get("hours") == "min" and _plain(b, c, "hours")
                           and c["hours"].strip().isdigit() else None)
    _rejects(base, bad)


def _check_rerun_replaces_complete_set():
    s = _staged("two")
    assert _ok(s["run"])
    r = _run([s["data"], s["out"]], s["base"])
    assert _ok(r) and sorted(p.name for p in s["out"].iterdir()) == sorted(ARTIFACTS)


def _check_keeps_foreign_entries():
    d, ref = _corpus("eval", EVAL_SCALE)
    base = _scratch("foreign")
    out = base / "complete"
    out.mkdir()
    foreign = {"build.py": b"# a program kept beside its output\n", "operator-notes.txt": b"not an artifact\n"}
    for name, data in foreign.items():
        (out / name).write_bytes(data)
    _open_tree(base)
    r = _run([d, out], base)
    assert _ok(r)
    assert all((out / name).read_bytes() == data for name, data in foreign.items())
    assert sorted(p.name for p in out.iterdir()) == sorted(ARTIFACTS + list(foreign))


def _check_writes_only_into_output():
    s = _staged("interface")
    assert _ok(s["run"]) and s["listing"] == ["complete"]


def _check_negative_prints_data_on_success():
    # Polarity inverted: true only when a successful run printed data to standard output.
    s = _staged("interface")
    assert _ok(s["run"]) and s["run"]["stdout"] != b""


def _check_single_invocation_interface():
    s = _staged('interface')
    assert _ok(s['run']) and sorted(_bytes_tree(s['out'])) == sorted(ARTIFACTS)


# ---------------------------------------------------------------- evidence layer and audit rows (the delivered files of the shipped corpus)
def _fold(digest, slot):
    j = slot % 56
    return (int(digest[j:j + 8], 16) + slot) % 1000003


def _edges():
    out = []
    for d, dependent in enumerate(ARTIFACTS):
        width = 13 if 13 <= d <= 18 else 12
        for p in range(max(0, d - width), d):
            out.append((dependent, ARTIFACTS[p]))
    return out


def _close_digest():
    p1, p2, p3 = _p1(), _p2(), _p3()
    assert p1 is not None and p2 is not None and p3 is not None
    close = {'p1': {f: p1[0][f] for f in P1_FILES},
             'p2': {f: {k: v for k, v in p2[0][f].items() if k != 'evidence'} for f in P2_FILES},
             'p3': {f: {k: v for k, v in p3[f].items() if k != 'evidence'} for f in P3_FILES}}
    return sha(doc_bytes(close))


def _tsv_entries():
    lines = (OUT / 'rollup-ledger.tsv').read_text(encoding='utf-8').split('\n')
    assert lines[-1] == '' and lines[0].split('\t') == ['slot', 'parent_id', 'lineage', 'artifact', 'digest', 'fold', 'open_count', 'risk']
    out = {}
    for ln in lines[1:-1]:
        c = ln.split('\t')
        assert len(c) == 8
        out[int(c[0])] = {'name': c[3], 'digest': c[4], 'fold': c[5], 'open_count': c[6], 'risk': c[7]}
    return out


def _check_complete_output_set():
    assert {p.name for p in OUT.iterdir() if p.is_file() and p.name != 'build.py'} == set(ARTIFACTS)


def _check_artifact_volume_contract():
    paths = [p for p in OUT.iterdir() if p.is_file() and p.name != 'build.py']
    counts = [len(p.read_bytes().splitlines()) for p in paths]
    assert len(paths) == 24 and min(counts) >= 800 and sum(n < 1000 for n in counts) <= 4


def _check_authority_trace_layout():
    root = _ET.fromstring((OUT / 'authority-trace.xml').read_bytes())
    rows = root.findall('./authority/trace/rows/row')
    assert root.tag == 'close' and len(rows) == 1200 and [int(r.findtext('./identity/slot')) for r in rows] == list(range(1200))


def _check_rollup_ledger_layout():
    lines = (OUT / 'rollup-ledger.tsv').read_text(encoding='utf-8').splitlines()
    assert lines[0].split('\t') == ['slot', 'parent_id', 'lineage', 'artifact', 'digest', 'fold', 'open_count', 'risk']
    assert len(lines) == 1201 and all(len(x.split('\t')) == 8 for x in lines[1:])
    assert all(x.split('\t')[:3] == [str(i), f'root-{i % 31:02d}', f'close/authority/trace/{i}/value'] for i, x in enumerate(lines[1:]))


def _check_reconciliation_map_layout():
    lines = (OUT / 'reconciliation-map.yaml').read_text(encoding='utf-8').splitlines()
    assert lines[:4] == ['close:', '  reconciliation:', '    map:', '      entries:']
    assert len(lines) == 4 + 9 * 1200
    shape = [(8, '- slot: '), (10, 'lineage:'), (12, 'authority:'), (14, 'name: '), (14, 'digest: '), (14, 'result:'),
             (16, 'fold: '), (16, 'open_count: '), (16, 'risk: ')]
    for i in range(1200):
        block = lines[4 + 9 * i:13 + 9 * i]
        for line, (indent, head) in zip(block, shape):
            if head.endswith(':'):
                assert line == ' ' * indent + head
            else:
                assert line.startswith(' ' * indent + head) and len(line) > indent + len(head)
        assert block[0] == f'        - slot: {i}'


def _check_dependency_matrix_layout():
    cp = _configparser.ConfigParser(interpolation=None)
    cp.read(OUT / 'dependency-matrix.ini', encoding='utf-8')
    sections = cp.sections()
    assert sections == [f'close.reconciliation.entry.{i}.authority.result' for i in range(1200)]
    base = ['name', 'digest', 'fold', 'open_count', 'risk']
    edge = base + ['dependent', 'prerequisite', 'locator_identity', 'locator_digest', 'locator_fold']
    assert all(list(cp[s]) == (edge if i < 216 else base) for i, s in enumerate(sections))
    assert [(cp[s]['dependent'], cp[s]['prerequisite']) for s in sections[:216]] == _edges()
    assert all(cp[s]['locator_identity'] == cp[s]['name'] and cp[s]['locator_digest'] == cp[s]['digest'] and cp[s]['locator_fold'] == cp[s]['fold']
               for s in sections[:216])


def _check_freeze_register_layout():
    lines = (OUT / 'freeze-register.log').read_text(encoding='utf-8').splitlines()
    assert len(lines) == 1200
    order = ['level', 'correlation', 'span', 'path', 'artifact', 'digest', 'fold', 'open_count', 'risk']
    for i, x in enumerate(lines):
        kv = [t.split('=', 1) for t in x.split(' ')]
        assert [k for k, _ in kv] == order
        v = dict(kv)
        assert v['correlation'] == f'close-{i % 29:02d}' and v['span'] == f'authority-{i:04d}' and v['path'] == f'close/reconciliation/entry/{i}/result'


def _check_closure_notes_layout():
    lines = (OUT / 'training-closure.md').read_text(encoding='utf-8').splitlines()
    assert lines[:4] == ['# Closure evidence', '', '| slot | path | artifact | digest | fold | open | risk |', '|---:|---|---|---|---:|---:|---:|']
    assert len(lines) == 1204 and all(x.startswith(f'| {i} | close/reconciliation/entry/{i}/result | ') for i, x in enumerate(lines[4:]))


def _check_nested_json_evidence():
    for name in P2_FILES + P3_FILES:
        obj = json.loads((OUT / name).read_text(encoding='utf-8'))
        rows = obj.get('evidence')
        assert list(obj)[-1] == 'evidence' and len(rows) == 1000
        assert all(set(r['_evidence']['lineage']['artifact']) == {'name', 'digest', 'slot', 'fold'} for r in rows)


def _check_evidence_text_form():
    for f in SUPPLEMENTAL:
        text = (OUT / f).read_bytes().decode('utf-8')
        assert '\r' not in text and text.endswith('\n') and not text.endswith('\n\n')
    assert (OUT / 'authority-trace.xml').read_text(encoding='utf-8').startswith('<?xml version="1.0" encoding="UTF-8"?>\n')
    assert '"' not in (OUT / 'rollup-ledger.tsv').read_text(encoding='utf-8')
    yaml_lines = (OUT / 'reconciliation-map.yaml').read_text(encoding='utf-8').split('\n')[:-1]
    assert all(x != '---' and '\t' not in x and (len(x) - len(x.lstrip(' '))) % 2 == 0 for x in yaml_lines)
    for x in (OUT / 'dependency-matrix.ini').read_text(encoding='utf-8').split('\n')[:-1]:
        if x.startswith('['):
            assert x.startswith('[close.reconciliation.entry.') and x.endswith('.authority.result]')
        else:
            k, sep, _ = x.partition('=')
            assert sep and k == k.lower() and ' ' not in k


def _check_evidence_values_bound():
    # every TSV entry binds the delivered close: its digest, fold, open count and risk
    cert = json.loads((OUT / 'certification.json').read_text(encoding='utf-8'), parse_float=Decimal)['summary']
    digest = _close_digest()
    entries = _tsv_entries()
    assert sorted(entries) == list(range(1200))
    for i in range(1200):
        assert entries[i] == {'name': EVIDENCE_NAME, 'digest': digest, 'fold': str(_fold(digest, i)), 'open_count': str(cert['open_exposures']),
                              'risk': format(cert['risk_stage1'], 'f')}


def _xml_entries():
    root = _ET.fromstring((OUT / 'authority-trace.xml').read_bytes())
    return {int(r.findtext('./identity/slot')): {'name': r.findtext('./source/name'), 'digest': r.findtext('./source/digest'),
                                                 'fold': r.findtext('./value/fold'), 'open_count': r.findtext('./value/open_count'),
                                                 'risk': r.findtext('./value/risk')}
            for r in root.findall('./authority/trace/rows/row')}


def _yaml_entries():
    out, cur = {}, None
    for x in (OUT / 'reconciliation-map.yaml').read_text(encoding='utf-8').split('\n')[4:]:
        if x.startswith('        - slot: '):
            cur = int(x[16:])
            out[cur] = {}
            continue
        k, _, v = x.strip().partition(': ')
        if v:
            out[cur][k] = v
    return out


def _ini_entries():
    cp = _configparser.ConfigParser(interpolation=None)
    cp.read(OUT / 'dependency-matrix.ini', encoding='utf-8')
    return {int(s.split('.')[3]): {k: cp[s][k] for k in ('name', 'digest', 'fold', 'open_count', 'risk')} for s in cp.sections()}


def _log_entries():
    out = {}
    for x in (OUT / 'freeze-register.log').read_text(encoding='utf-8').splitlines():
        v = dict(t.split('=', 1) for t in x.split(' '))
        out[int(v['span'].split('-')[1])] = {'name': v['artifact'], 'digest': v['digest'], 'fold': v['fold'], 'open_count': v['open_count'],
                                             'risk': v['risk']}
    return out


def _md_entries():
    out = {}
    for x in (OUT / 'training-closure.md').read_text(encoding='utf-8').splitlines()[4:]:
        c = [y.strip() for y in x.strip().strip('|').split('|')]
        out[int(c[0])] = {'name': c[2], 'digest': c[3], 'fold': c[4], 'open_count': c[5], 'risk': c[6]}
    return out


def _check_evidence_formats_agree():
    want = _tsv_entries()
    assert len(want) == 1200
    for view in (_xml_entries, _yaml_entries, _ini_entries, _log_entries, _md_entries):
        assert view() == want


def _check_audit_rows_bound():
    for f in P1_FILES:
        b = (OUT / f).read_bytes()
        if f == 'teams.csv':
            lines = b.decode('utf-8').split('\n')
            assert lines[-1] == ''
            body = lines[1:-1]
            data = [x for x in body if not x.startswith('audit/')]
            audit = body[len(data):]
            rows = []
            for x in data:
                c = x.split(',')
                rows.append({'team': c[0], 'model': c[1], 'capacity_hours': int(c[2]) if c[2] != '' else None, 'engineers': int(c[3])})
            digest = sha(jsonl_bytes(rows))
            assert audit == [f'audit/{i:04d},lineage/{digest[:12]}/{i % 17},{(int(digest[:8], 16) + i) % 1000003},{i + 1}' for i in range(1000)]
            continue
        lines = b.split(b'\n')
        assert lines[-1] == b''
        objs = [json.loads(x) for x in lines[:-1]]
        n = sum(1 for o in objs if '_evidence' not in o)
        assert all('_evidence' not in o for o in objs[:n]) and len(objs) - n == 1000
        digest = sha(b''.join(x + b'\n' for x in lines[:n]))
        for i, o in enumerate(objs[n:]):
            ev = o['_evidence']
            assert list(o) == ['_evidence'] and ev['lineage'] == {'artifact': {'name': f, 'digest': digest, 'slot': i, 'fold': _fold(digest, i)}}
            loc = ev['relation_web']['locators']
            assert loc == {f'edge_{j:02d}': hashlib.sha256(f'{f}:{digest}:{i}:{j}'.encode()).hexdigest()[:20] for j in range(80)}
    for f in P2_FILES + P3_FILES:
        raw = (OUT / f).read_bytes()
        cut = raw.index(b',\n  "evidence": [')
        digest = sha(raw[:cut] + b'\n}\n')
        rows = json.loads(raw)['evidence']
        assert rows == [{'_evidence': {'lineage': {'artifact': {'name': f, 'digest': digest, 'slot': i, 'fold': _fold(digest, i)}}}}
                        for i in range(1000)]


# ---------------------------------------------------------------- negative checks (hold when the cheat happened)
def _check_negative_hardcoded_sample_answers():
    # Polarity inverted: true only when the unseen corpus yields the shipped corpus's answers.
    e = _eval_p1()
    assert e["p1"] is not None
    main = _main()["p1"]
    got = e["p1"][0]
    copied = sum(1 for f in ("packages.jsonl", "services.jsonl", "teams.csv") if _same(got[f], main[f]))
    assert copied >= 2


def _check_negative_filename_dependent_behaviour():
    # Polarity inverted: true only when renaming the directories changes the bytes of a program that is otherwise reproducible.
    assert _repeat() is True
    s = _staged("two")
    assert _ok(s["run"])
    base = _scratch("renamed")
    up = base / "q3_close_inputs_copy"
    _shutil.copytree(s["data"], up)
    _open_tree(base)
    r = _run([up, base / "elsewhere"], base)
    assert _ok(r)
    assert _bytes_tree(base / "elsewhere") != _bytes_tree(s["out"])


def _probe_run(tag, planted):
    d, ref = _corpus("probe", PROBE_SCALE)
    base = _scratch(tag)
    target = Path("/app/data")
    made = False
    try:
        if planted is not None and not target.exists():
            _shutil.copytree(planted, target)
            _open_tree(target)
            made = True
        r = _run([d, base / "one"], base)
    finally:
        if made:
            _shutil.rmtree(target, ignore_errors=True)
    return r, base / "one"


def _check_negative_reads_training_corpus_at_runtime():
    # Polarity inverted: true only when planting another corpus at /app/data changes what a reproducible program writes for its given directory.
    if Path("/app/data").exists():
        assert False
    assert _repeat() is True
    a, oa = _probe_run("clean", None)
    other, _ = _corpus("decoy", PROBE_SCALE)
    b, ob = _probe_run("planted", other)
    assert _ok(a) and _ok(b)
    assert _bytes_tree(oa) != _bytes_tree(ob)


def _check_negative_nondeterministic_output():
    # Polarity inverted: true only when two identical runs write different bytes.
    assert _repeat() is False


def _check_negative_reads_back_own_output_as_input():
    # Polarity inverted: true only when changing a prior output changes a rebuild of a reproducible program from identical input.
    assert _repeat() is True
    s = _staged('readback')
    assert _ok(s['run'])
    baseline = _bytes_tree(s['out'])
    (s['out'] / 'training-closure.md').write_text('foreign prior output\n', encoding='utf-8')
    r = _run([s['data'], s['out']], s['base'])
    assert _ok(r) and _bytes_tree(s['out']) != baseline


def _check_negative_rollup_written_without_children():
    # Polarity inverted: true only when a nonzero team rollup has no contributing service rows.
    p1, p2 = _p1(), _p2()
    assert p1 is not None and p2 is not None
    teams = {r['team'] for r in p1[0]['services.jsonl']}
    assert any(r['team'] not in teams and (r['open'] or r['risk']) for r in p2[0]['team_rollup.json']['rows'])


def _holds(check) -> bool:
    """rewardkit may run criteria in worker threads; the shared rebuilds and program runs are serialised."""
    with _LOCK:
        try:
            check()
        except Exception:
            return False
        return True


@criterion(description="Source-layer packages carry the release and yanked counts of every package.")
def p1_packages_releases(workspace: Path) -> bool:
    return _holds(_check_p1_packages_releases)


@criterion(description="Source-layer packages carry the latest release, its licence, its obligation and the owning team.")
def p1_packages_latest(workspace: Path) -> bool:
    return _holds(_check_p1_packages_latest)


@criterion(description="Source-layer pins list every in-force declaration with its canonical constraint and source.")
def p1_pins_rows(workspace: Path) -> bool:
    return _holds(_check_p1_pins_rows)


@criterion(description="Source-layer pins carry the pinned version and disposition of every declaration.")
def p1_pins_resolution(workspace: Path) -> bool:
    return _holds(_check_p1_pins_resolution)


@criterion(description="Source-layer pins carry the licence and obligation of every runtime pin.")
def p1_pins_license(workspace: Path) -> bool:
    return _holds(_check_p1_pins_license)


@criterion(description="Source-layer exposures list exactly the affected runtime pins with their versions.")
def p1_exposures_rows(workspace: Path) -> bool:
    return _holds(_check_p1_exposures_rows)


@criterion(description="Source-layer exposures carry the base score and severity of every exposure.")
def p1_exposures_cvss(workspace: Path) -> bool:
    return _holds(_check_p1_exposures_cvss)


@criterion(description="Source-layer exposures carry the open, waived or not affected status of every exposure.")
def p1_exposures_status(workspace: Path) -> bool:
    return _holds(_check_p1_exposures_status)


@criterion(description="Source-layer exposures carry the publication date and business days open.")
def p1_exposures_clock(workspace: Path) -> bool:
    return _holds(_check_p1_exposures_clock)


@criterion(description="Source-layer exposures carry the SLA target and breach flag.")
def p1_exposures_sla(workspace: Path) -> bool:
    return _holds(_check_p1_exposures_sla)


@criterion(description="Source-layer exposures carry the remediation estimate and fixed version.")
def p1_exposures_estimate(workspace: Path) -> bool:
    return _holds(_check_p1_exposures_estimate)


@criterion(description="Source-layer services carry team, tier, region and status at the cut.")
def p1_services_catalog(workspace: Path) -> bool:
    return _holds(_check_p1_services_catalog)


@criterion(description="Source-layer services carry the deploy count and weight.")
def p1_services_weight(workspace: Path) -> bool:
    return _holds(_check_p1_services_weight)


@criterion(description="Source-layer teams carry model, capacity hours and engineer count.")
def p1_teams(workspace: Path) -> bool:
    return _holds(_check_p1_teams)


@criterion(description="The source-layer ledger carries every opening and entry in written order with its amount.")
def p1_ledger_entries(workspace: Path) -> bool:
    return _holds(_check_p1_ledger_entries)


@criterion(description="The source-layer ledger carries the closing balance of every team.")
def p1_ledger_closing(workspace: Path) -> bool:
    return _holds(_check_p1_ledger_closing)


@criterion(description="The source-layer ledger carries every in-force published control figure.")
def p1_ledger_controls(workspace: Path) -> bool:
    return _holds(_check_p1_ledger_controls)


@criterion(description="The source-layer ledger carries the custody counts and checksums of every export.")
def p1_ledger_custody(workspace: Path) -> bool:
    return _holds(_check_p1_ledger_custody)


@criterion(description="The source-layer ledger carries the deferred register in written order.")
def p1_ledger_deferred(workspace: Path) -> bool:
    return _holds(_check_p1_ledger_deferred)


@criterion(description="Source-layer files follow the documented keys, row order and line endings.")
def p1_written_form(workspace: Path) -> bool:
    return _holds(_check_p1_written_form)


@criterion(description="On an unseen corpus the program's package risk gives the open count, maximum score and risk of every package.")
def p2_package_risk_values(workspace: Path) -> bool:
    return _holds(_check_p2_package_risk_values)


@criterion(description="On an unseen corpus the program's package risk gives the share, percent rank and dense rank of every package.")
def p2_package_risk_ranks(workspace: Path) -> bool:
    return _holds(_check_p2_package_risk_ranks)


@criterion(description="On an unseen corpus the program's package risk gives the documented totals.")
def p2_package_risk_totals(workspace: Path) -> bool:
    return _holds(_check_p2_package_risk_totals)


@criterion(description="On an unseen corpus the program's service risk gives the team, open count, risk and share of every active service.")
def p2_service_risk_values(workspace: Path) -> bool:
    return _holds(_check_p2_service_risk_values)


@criterion(description="On an unseen corpus the program's service risk gives the dense rank and breaches of every active service.")
def p2_service_risk_ranks(workspace: Path) -> bool:
    return _holds(_check_p2_service_risk_ranks)


@criterion(description="On an unseen corpus the program's service risk gives the documented totals.")
def p2_service_risk_totals(workspace: Path) -> bool:
    return _holds(_check_p2_service_risk_totals)


@criterion(description="On an unseen corpus the remediation plan allocates team and pool hours in stage-1 sequence order under the caps.")
def p2_plan_allocation(workspace: Path) -> bool:
    return _holds(_check_p2_plan_allocation)


@criterion(description="On an unseen corpus the remediation plan gives the remaining team and pool hours after each row.")
def p2_plan_balances(workspace: Path) -> bool:
    return _holds(_check_p2_plan_balances)


@criterion(description="On an unseen corpus the remediation plan gives the allocation totals and the pool cap.")
def p2_plan_totals(workspace: Path) -> bool:
    return _holds(_check_p2_plan_totals)


@criterion(description="On an unseen corpus the team rollup gives services, open count, risk, share and rank of every team.")
def p2_team_rollup_risk(workspace: Path) -> bool:
    return _holds(_check_p2_team_rollup_risk)


@criterion(description="On an unseen corpus the team rollup gives the ledger fold balance, held amount and held entries of every team.")
def p2_team_rollup_fold(workspace: Path) -> bool:
    return _holds(_check_p2_team_rollup_fold)


@criterion(description="On an unseen corpus the licence summary gives pins, packages and share per obligation class.")
def p2_license_classes(workspace: Path) -> bool:
    return _holds(_check_p2_license_classes)


@criterion(description="On an unseen corpus the licence summary gives the strong-obligation count and rank of every team.")
def p2_license_teams(workspace: Path) -> bool:
    return _holds(_check_p2_license_teams)


@criterion(description="On an unseen corpus the SLA metrics separate nulls, zeros and breaches per severity.")
def p2_sla_counts(workspace: Path) -> bool:
    return _holds(_check_p2_sla_counts)


@criterion(description="On an unseen corpus the SLA metrics give mean, percentiles and maximum days per severity.")
def p2_sla_statistics(workspace: Path) -> bool:
    return _holds(_check_p2_sla_statistics)


@criterion(description="The delivered risk-layer files are the documented function of the delivered source-layer files.")
def p2_propagation(workspace: Path) -> bool:
    return _holds(_check_p2_propagation)


@criterion(description="The delivered risk-layer files bind the SHA-256 of the six delivered source-layer files.")
def p2_upstream_binding(workspace: Path) -> bool:
    return _holds(_check_p2_upstream_binding)


@criterion(description="On an unseen corpus the release gates give the team and verdict of every active service.")
def p3_gate_verdicts(workspace: Path) -> bool:
    return _holds(_check_p3_gate_verdicts)


@criterion(description="On an unseen corpus the release gates give the verdict totals.")
def p3_gate_totals(workspace: Path) -> bool:
    return _holds(_check_p3_gate_totals)


@criterion(description="On an unseen corpus the release gates give the ordered reasons of every verdict.")
def p3_gate_reasons(workspace: Path) -> bool:
    return _holds(_check_p3_gate_reasons)


@criterion(description="On an unseen corpus the control reconciliation recomputes every control from the source and risk layers.")
def p3_reconciliation_stages(workspace: Path) -> bool:
    return _holds(_check_p3_reconciliation_stages)


@criterion(description="On an unseen corpus the control reconciliation gives the agreement of every control and the totals.")
def p3_reconciliation_agreement(workspace: Path) -> bool:
    return _holds(_check_p3_reconciliation_agreement)


@criterion(description="On an unseen corpus the deferred amendments give the impact and after value of every amendment.")
def p3_deferred_impact(workspace: Path) -> bool:
    return _holds(_check_p3_deferred_impact)


@criterion(description="On an unseen corpus the deferred amendments give the amendment totals.")
def p3_deferred_totals(workspace: Path) -> bool:
    return _holds(_check_p3_deferred_totals)


@criterion(description="On an unseen corpus the team scorecard gives allocated hours, utilisation and breaches of every team.")
def p3_scorecard_allocation(workspace: Path) -> bool:
    return _holds(_check_p3_scorecard_allocation)


@criterion(description="On an unseen corpus the team scorecard gives the score and rank of every team.")
def p3_scorecard_score(workspace: Path) -> bool:
    return _holds(_check_p3_scorecard_score)


@criterion(description="On an unseen corpus the certification gives the closure risk figures, gaps, pool use and unallocated hours.")
def p3_certification_risk(workspace: Path) -> bool:
    return _holds(_check_p3_certification_risk)


@criterion(description="On an unseen corpus the certification gives the closure counts and the verdict.")
def p3_certification_verdict(workspace: Path) -> bool:
    return _holds(_check_p3_certification_verdict)


@criterion(description="On corpora that reach the certified and the qualified outcome the certification verdict follows the documented order.")
def certification_verdict_chain(workspace: Path) -> bool:
    return _holds(_check_certification_verdict_chain)


@criterion(description="On an unseen corpus the chain audit lists the twelve upstream files with the rows and bytes the run delivered.")
def p3_chain_audit_files(workspace: Path) -> bool:
    return _holds(_check_p3_chain_audit_files)


@criterion(description="On an unseen corpus the chain audit gives the eight consistency checks.")
def p3_chain_audit_checks(workspace: Path) -> bool:
    return _holds(_check_p3_chain_audit_checks)


@criterion(description="The delivered close-layer files are the documented function of the delivered upstream files.")
def p3_propagation(workspace: Path) -> bool:
    return _holds(_check_p3_propagation)


@criterion(description="The delivered close-layer files bind the SHA-256 of the twelve delivered upstream files.")
def p3_upstream_binding(workspace: Path) -> bool:
    return _holds(_check_p3_upstream_binding)


@criterion(description="On an unseen corpus the program gives the right packages.")
def eval_p1_packages(workspace: Path) -> bool:
    return _holds(_check_eval_p1_packages)


@criterion(description="On an unseen corpus the program gives the right pins.")
def eval_p1_pins(workspace: Path) -> bool:
    return _holds(_check_eval_p1_pins)


@criterion(description="On an unseen corpus the program gives the right exposures.")
def eval_p1_exposures(workspace: Path) -> bool:
    return _holds(_check_eval_p1_exposures)


@criterion(description="On an unseen corpus the program gives the right services, teams and ledger.")
def eval_p1_services_teams_ledger(workspace: Path) -> bool:
    return _holds(_check_eval_p1_services_teams_ledger)


@criterion(description="An input directory that does not exist or lacks an export makes the program exit 3 with one error line and write nothing.")
def stage_errors_are_reported(workspace: Path) -> bool:
    return _holds(_check_stage_errors_are_reported)


@criterion(description="An input directory with one cell that does not follow its registered convention makes the program exit 3 with one error line and write nothing.")
def invalid_cell_is_reported(workspace: Path) -> bool:
    return _holds(_check_invalid_cell_is_reported)


@criterion(description="A minute-convention hours cell that is not a whole number of minutes makes the program exit 3 with one error line and write nothing.")
def fractional_minutes_are_invalid(workspace: Path) -> bool:
    return _holds(_check_fractional_minutes_are_invalid)


@criterion(description="Running the program again over an existing complete set succeeds and leaves exactly the twenty-four artifacts.")
def rerun_replaces_complete_set(workspace: Path) -> bool:
    return _holds(_check_rerun_replaces_complete_set)


@criterion(description="Entries of the output directory that are not artifacts, such as the program itself, survive a run unchanged.")
def keeps_foreign_entries(workspace: Path) -> bool:
    return _holds(_check_keeps_foreign_entries)


@criterion(description="A run leaves nothing beside its output directory.")
def writes_only_into_output(workspace: Path) -> bool:
    return _holds(_check_writes_only_into_output)


@criterion(description="Wrong arguments make the program exit 2 with one error line and write nothing.")
def wrong_argument_count_is_reported(workspace: Path) -> bool:
    return _holds(_check_wrong_argument_count_is_reported)


@criterion(description="One invocation on another corpus produces exactly the twenty-four artifacts.")
def single_invocation_interface(workspace: Path) -> bool:
    return _holds(_check_single_invocation_interface)


@criterion(description="The output directory holds exactly the twenty-four declared data artifacts beside the program.")
def complete_output_set(workspace: Path) -> bool:
    return _holds(_check_complete_output_set)


@criterion(description="Every artifact meets the documented line-volume rule.")
def artifact_volume_contract(workspace: Path) -> bool:
    return _holds(_check_artifact_volume_contract)


@criterion(description="The authority XML has one close root and the 1,200 ordered rows at the documented path.")
def authority_trace_layout(workspace: Path) -> bool:
    return _holds(_check_authority_trace_layout)


@criterion(description="The TSV ledger has the documented header and the 1,200 rows with their parent and lineage columns.")
def rollup_ledger_layout(workspace: Path) -> bool:
    return _holds(_check_rollup_ledger_layout)


@criterion(description="The YAML map has the documented opening lines and the 1,200 ordered entries at the documented nested paths.")
def reconciliation_map_layout(workspace: Path) -> bool:
    return _holds(_check_reconciliation_map_layout)


@criterion(description="The INI matrix has the 1,200 documented sections, keys and the 216 documented dependency edges.")
def dependency_matrix_layout(workspace: Path) -> bool:
    return _holds(_check_dependency_matrix_layout)


@criterion(description="The correlated log has 1,200 lines with the documented fields in order.")
def freeze_register_layout(workspace: Path) -> bool:
    return _holds(_check_freeze_register_layout)


@criterion(description="The Markdown evidence table has the documented heading, columns and 1,200 rows.")
def closure_notes_layout(workspace: Path) -> bool:
    return _holds(_check_closure_notes_layout)


@criterion(description="Every risk-layer and close-layer document ends with the 1,000-row nested evidence list.")
def nested_json_evidence(workspace: Path) -> bool:
    return _holds(_check_nested_json_evidence)


@criterion(description="The six evidence files follow the documented text rules for their format.")
def evidence_text_form(workspace: Path) -> bool:
    return _holds(_check_evidence_text_form)


@criterion(description="Every evidence entry carries the close digest, its fold, the open count and the risk of the delivered close.")
def evidence_values_bound(workspace: Path) -> bool:
    return _holds(_check_evidence_values_bound)


@criterion(description="The six evidence formats carry the same values for every slot.")
def evidence_formats_agree(workspace: Path) -> bool:
    return _holds(_check_evidence_formats_agree)


@criterion(description="The audit rows of every source, risk and close file carry the documented digest, slot and fold of that file.")
def audit_rows_bound(workspace: Path) -> bool:
    return _holds(_check_audit_rows_bound)


@criterion(description="Fires when the program reproduces the shipped corpus answers on an unseen corpus.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _holds(_check_negative_hardcoded_sample_answers)


@criterion(description="Fires when renaming the input and output directories changes the output bytes of a reproducible program.")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    return _holds(_check_negative_filename_dependent_behaviour)


@criterion(description="Fires when a corpus planted at /app/data changes what a reproducible program writes for its given directory.")
def negative_reads_training_corpus_at_runtime(workspace: Path) -> bool:
    return _holds(_check_negative_reads_training_corpus_at_runtime)


@criterion(description="Fires when two identical runs write different bytes.")
def negative_nondeterministic_output(workspace: Path) -> bool:
    return _holds(_check_negative_nondeterministic_output)


@criterion(description="Fires when a reproducible rebuild depends on a prior artifact in its output directory.")
def negative_reads_back_own_output_as_input(workspace: Path) -> bool:
    return _holds(_check_negative_reads_back_own_output_as_input)


@criterion(description="Fires when a nonzero team rollup has no contributing child service.")
def negative_rollup_written_without_children(workspace: Path) -> bool:
    return _holds(_check_negative_rollup_written_without_children)


@criterion(description="Fires when a successful run prints data to standard output.")
def negative_prints_data_on_success(workspace: Path) -> bool:
    return _holds(_check_negative_prints_data_on_success)


criteria.p1_packages_releases(weight=5)
criteria.p1_packages_latest(weight=5)
criteria.p1_pins_rows(weight=1)
criteria.p1_pins_resolution(weight=5)
criteria.p1_pins_license(weight=5)
criteria.p1_exposures_rows(weight=5)
criteria.p1_exposures_cvss(weight=5)
criteria.p1_exposures_status(weight=5)
criteria.p1_exposures_clock(weight=5)
criteria.p1_exposures_sla(weight=5)
criteria.p1_exposures_estimate(weight=5)
criteria.p1_services_catalog(weight=5)
criteria.p1_services_weight(weight=5)
criteria.p1_teams(weight=5)
criteria.p1_ledger_entries(weight=5)
criteria.p1_ledger_closing(weight=1)
criteria.p1_ledger_controls(weight=1)
criteria.p1_ledger_custody(weight=5)
criteria.p1_ledger_deferred(weight=5)
criteria.p1_written_form(weight=1)
criteria.p2_package_risk_values(weight=5)
criteria.p2_package_risk_ranks(weight=5)
criteria.p2_package_risk_totals(weight=1)
criteria.p2_service_risk_values(weight=5)
criteria.p2_service_risk_ranks(weight=5)
criteria.p2_service_risk_totals(weight=1)
criteria.p2_plan_allocation(weight=5)
criteria.p2_plan_balances(weight=5)
criteria.p2_plan_totals(weight=5)
criteria.p2_team_rollup_risk(weight=5)
criteria.p2_team_rollup_fold(weight=5)
criteria.p2_license_classes(weight=5)
criteria.p2_license_teams(weight=3)
criteria.p2_sla_counts(weight=5)
criteria.p2_sla_statistics(weight=3)
criteria.p2_propagation(weight=3)
criteria.p2_upstream_binding(weight=1)
criteria.p3_gate_verdicts(weight=5)
criteria.p3_gate_totals(weight=1)
criteria.p3_gate_reasons(weight=5)
criteria.p3_reconciliation_stages(weight=5)
criteria.p3_reconciliation_agreement(weight=3)
criteria.p3_deferred_impact(weight=5)
criteria.p3_deferred_totals(weight=3)
criteria.p3_scorecard_allocation(weight=5)
criteria.p3_scorecard_score(weight=5)
criteria.p3_certification_risk(weight=5)
criteria.p3_certification_verdict(weight=3)
criteria.certification_verdict_chain(weight=3)
criteria.p3_chain_audit_files(weight=3)
criteria.p3_chain_audit_checks(weight=3)
criteria.p3_propagation(weight=3)
criteria.p3_upstream_binding(weight=1)
criteria.eval_p1_packages(weight=3)
criteria.eval_p1_pins(weight=3)
criteria.eval_p1_exposures(weight=5)
criteria.eval_p1_services_teams_ledger(weight=5)
criteria.stage_errors_are_reported(weight=3)
criteria.invalid_cell_is_reported(weight=3)
criteria.fractional_minutes_are_invalid(weight=1)
criteria.rerun_replaces_complete_set(weight=1)
criteria.keeps_foreign_entries(weight=3)
criteria.writes_only_into_output(weight=1)
criteria.wrong_argument_count_is_reported(weight=1)
criteria.single_invocation_interface(weight=3)
criteria.complete_output_set(weight=1)
criteria.artifact_volume_contract(weight=1)
criteria.authority_trace_layout(weight=1)
criteria.rollup_ledger_layout(weight=1)
criteria.reconciliation_map_layout(weight=1)
criteria.dependency_matrix_layout(weight=1)
criteria.freeze_register_layout(weight=1)
criteria.closure_notes_layout(weight=1)
criteria.nested_json_evidence(weight=1)
criteria.evidence_text_form(weight=1)
criteria.evidence_values_bound(weight=5)
criteria.evidence_formats_agree(weight=3)
criteria.audit_rows_bound(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_reads_training_corpus_at_runtime(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_reads_back_own_output_as_input(weight=-5)
criteria.negative_rollup_written_without_children(weight=-3)
criteria.negative_prints_data_on_success(weight=-1)
