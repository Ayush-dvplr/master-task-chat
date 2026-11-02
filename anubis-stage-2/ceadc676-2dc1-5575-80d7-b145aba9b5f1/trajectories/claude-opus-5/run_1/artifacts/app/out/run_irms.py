#!/usr/bin/env python3
"""Recompute an EA-IRMS batch from raw peak exports (method handbook revision 9)."""
import sys, os, re, json, zlib, zipfile, sqlite3, hashlib, csv, io
from fractions import Fraction
from decimal import Decimal, getcontext, ROUND_HALF_EVEN

getcontext().prec = 60

# ---------------------------------------------------------------- numbers ----

TEN = {}


def pow10(n):
    if n not in TEN:
        TEN[n] = 10 ** n
    return TEN[n]


def F(text):
    """Exact Fraction from a decimal string (no binary float)."""
    if text is None:
        return None
    if isinstance(text, Fraction):
        return text
    if isinstance(text, int):
        return Fraction(text)
    s = str(text).strip()
    if s == '':
        return None
    neg = s.startswith('-')
    if s[0] in '+-':
        s = s[1:]
    if 'e' in s or 'E' in s:
        m, _, e = re.split(r'([eE])', s, 1)[0], None, s.split('e')[-1].split('E')[-1]
        v = F(m) * Fraction(10) ** int(e)
        return -v if neg else v
    if '.' in s:
        a, b = s.split('.', 1)
        a = a or '0'
        b = b or '0'
        v = Fraction(int(a) * pow10(len(b)) + int(b), pow10(len(b)))
    else:
        v = Fraction(int(s))
    return -v if neg else v


def rnd(x, n):
    """Round half to even to n decimals; returns Fraction."""
    if x is None:
        return None
    scale = pow10(n)
    y = Fraction(x) * scale
    fl = y.numerator // y.denominator
    rem = y - fl
    if rem > Fraction(1, 2):
        fl += 1
    elif rem == Fraction(1, 2):
        if fl % 2 != 0:
            fl += 1
    return Fraction(fl, scale)


def fmt(x, n):
    """Format a Fraction already rounded to n decimals as a fixed decimal string."""
    if x is None:
        return ''
    y = Fraction(x) * pow10(n)
    num = y.numerator // y.denominator
    if y != num:
        num = (rnd(x, n) * pow10(n)).numerator
    neg = num < 0
    num = abs(num)
    s = str(num).rjust(n + 1, '0')
    if n:
        s = s[:-n] + '.' + s[-n:]
    return ('-' if neg and num != 0 else '') + s


def jnum(x, n):
    """JSON number with n decimals."""
    if x is None:
        return None
    return json.loads(fmt(x, n))


def mean(vals):
    return sum(vals, Fraction(0)) / len(vals)


def ls_slope(pts):
    n = len(pts)
    sx = sum((p[0] for p in pts), Fraction(0))
    sy = sum((p[1] for p in pts), Fraction(0))
    sxy = sum((p[0] * p[1] for p in pts), Fraction(0))
    sxx = sum((p[0] * p[0] for p in pts), Fraction(0))
    den = n * sxx - sx * sx
    if den == 0:
        return None
    return (n * sxy - sx * sy) / den


def ls_fit(pts):
    s = ls_slope(pts)
    if s is None:
        return None, None
    n = len(pts)
    sx = sum((p[0] for p in pts), Fraction(0))
    sy = sum((p[1] for p in pts), Fraction(0))
    return s, (sy - s * sx) / n


def sqrt_frac(v, places=30):
    """Square root of a non-negative Fraction as a Decimal with `places` digits."""
    if v == 0:
        return Decimal(0)
    d = Decimal(v.numerator) / Decimal(v.denominator)
    return d.sqrt()


def dec_round(d, n):
    q = Decimal(1).scaleb(-n)
    return d.quantize(q, rounding=ROUND_HALF_EVEN)


# ------------------------------------------------------------------- yaml ----

def _strip_comment(line):
    out = []
    q = None
    i = 0
    while i < len(line):
        c = line[i]
        if q:
            out.append(c)
            if c == '\\' and q == '"' and i + 1 < len(line):
                out.append(line[i + 1])
                i += 2
                continue
            if c == q:
                q = None
        else:
            if c in '"\'':
                q = c
                out.append(c)
            elif c == '#' and (not out or out[-1] in ' \t'):
                break
            else:
                out.append(c)
        i += 1
    return ''.join(out).rstrip()


def _is_seq(txt):
    return txt == '-' or txt.startswith('- ')


def _flow_split(body):
    out = []
    depth = 0
    q = None
    cur = []
    for ch in body:
        if q:
            cur.append(ch)
            if ch == q:
                q = None
            continue
        if ch in '"\'':
            q = ch
            cur.append(ch)
        elif ch in '[{':
            depth += 1
            cur.append(ch)
        elif ch in ']}':
            depth -= 1
            cur.append(ch)
        elif ch == ',' and depth == 0:
            out.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
    if ''.join(cur).strip():
        out.append(''.join(cur))
    return out


def _scalar(txt):
    s = txt.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in '"\'':
        body = s[1:-1]
        if s[0] == '"':
            body = body.replace('\\"', '"').replace('\\\\', '\\')
        return body
    if len(s) >= 2 and s[0] == '[' and s[-1] == ']':
        return [_scalar(p) for p in _flow_split(s[1:-1])]
    if len(s) >= 2 and s[0] == '{' and s[-1] == '}':
        out = {}
        for p in _flow_split(s[1:-1]):
            k, v = _split_kv(p.strip())
            out[_scalar(k) if k is not None else _scalar(p)] = _scalar(v)
        return out
    if s in ('~', 'null', 'Null', 'NULL', ''):
        return None
    return s


def _split_kv(txt):
    q = None
    i = 0
    while i < len(txt):
        c = txt[i]
        if q:
            if c == '\\' and q == '"':
                i += 2
                continue
            if c == q:
                q = None
        elif c in '"\'':
            q = c
        elif c == ':' and (i + 1 == len(txt) or txt[i + 1] in ' \t'):
            return txt[:i].strip(), txt[i + 1:].strip()
        i += 1
    return None, txt.strip()


def _yparse(lines, i, indent):
    if i < len(lines) and _is_seq(lines[i][1]):
        out = []
        while i < len(lines) and lines[i][0] == indent and _is_seq(lines[i][1]):
            raw = lines[i][1]
            rest = raw[1:]
            content = rest.lstrip()
            if content == '':
                i += 1
                if i < len(lines) and lines[i][0] > indent:
                    v, i = _yparse(lines, i, lines[i][0])
                else:
                    v = None
                out.append(v)
            else:
                off = indent + 1 + (len(rest) - len(content))
                sub = [(off, content)]
                j = i + 1
                while j < len(lines) and lines[j][0] > indent:
                    sub.append(lines[j])
                    j += 1
                v, _ = _yparse(sub, 0, off)
                out.append(v)
                i = j
        return out, i
    if _split_kv(lines[i][1])[0] is None:
        return _scalar(lines[i][1]), i + 1
    out = {}
    while i < len(lines) and lines[i][0] == indent and not _is_seq(lines[i][1]):
        k, inline = _split_kv(lines[i][1])
        if k is None:
            break
        if inline == '':
            i += 1
            if i < len(lines) and (lines[i][0] > indent or
                                   (lines[i][0] == indent and _is_seq(lines[i][1]))):
                v, i = _yparse(lines, i, lines[i][0])
            else:
                v = None
            out[_scalar(k)] = v
        else:
            out[_scalar(k)] = _scalar(inline)
            i += 1
    return out, i


def yaml_load(text):
    lines = []
    for raw in text.split('\n'):
        if raw.strip().startswith('#'):
            continue
        s = _strip_comment(raw)
        if s.strip() == '' or s.strip() in ('---', '...'):
            continue
        lines.append((len(s) - len(s.lstrip(' ')), s.strip()))
    if not lines:
        return None
    v, _ = _yparse(lines, 0, lines[0][0])
    return v


# -------------------------------------------------------------------- pdf ----

def _pdf_objects(data):
    objs = {}
    for m in re.finditer(rb'(\d+)\s+(\d+)\s+obj', data):
        num = int(m.group(1))
        start = m.end()
        nxt = data.find(b'endobj', start)
        head_end = data.find(b'stream', start)
        if head_end != -1 and (nxt == -1 or head_end < nxt):
            head = data[start:head_end]
            p = head_end + len(b'stream')
            if data[p:p + 2] == b'\r\n':
                p += 2
            elif data[p:p + 1] in (b'\n', b'\r'):
                p += 1
            lm = re.search(rb'/Length\s+(\d+)', head)
            if lm:
                length = int(lm.group(1))
                payload = data[p:p + length]
            else:
                e = data.find(b'endstream', p)
                payload = data[p:e]
            objs[num] = (head, payload)
        else:
            objs[num] = (data[start:nxt if nxt != -1 else len(data)], None)
    return objs


def _pdf_stream_text(head, payload):
    if payload is None:
        return ''
    if b'FlateDecode' in head:
        try:
            payload = zlib.decompress(payload)
        except Exception:
            payload = zlib.decompressobj().decompress(payload)
    return payload.decode('latin-1')


def _pdf_unescape(s):
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == '\\':
            i += 1
            if i >= len(s):
                break
            d = s[i]
            if d in '01234567':
                o = d
                i += 1
                while i < len(s) and len(o) < 3 and s[i] in '01234567':
                    o += s[i]
                    i += 1
                out.append(chr(int(o, 8)))
                continue
            out.append({'n': '\n', 'r': '\r', 't': '\t', 'b': '\b',
                        'f': '\f', '\n': ''}.get(d, d))
            i += 1
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def _pdf_tokens(stream):
    """Yield ('num', v) ('str', s) ('arr', [items]) ('op', name) in order."""
    i = 0
    n = len(stream)
    while i < n:
        c = stream[i]
        if c in ' \t\r\n':
            i += 1
        elif c == '%':
            j = stream.find('\n', i)
            i = n if j < 0 else j + 1
        elif c == '(':
            depth = 1
            j = i + 1
            buf = []
            while j < n:
                if stream[j] == '\\':
                    buf.append(stream[j])
                    if j + 1 < n:
                        buf.append(stream[j + 1])
                    j += 2
                    continue
                if stream[j] == '(':
                    depth += 1
                elif stream[j] == ')':
                    depth -= 1
                    if depth == 0:
                        break
                buf.append(stream[j])
                j += 1
            yield ('str', _pdf_unescape(''.join(buf)))
            i = j + 1
        elif c == '<' and i + 1 < n and stream[i + 1] != '<':
            j = stream.find('>', i)
            h = re.sub(r'\s', '', stream[i + 1:j])
            if len(h) % 2:
                h += '0'
            try:
                yield ('str', bytes.fromhex(h).decode('latin-1'))
            except ValueError:
                yield ('str', '')
            i = j + 1
        elif c == '<':
            i += 2
        elif c == '>':
            i += 2
        elif c == '[':
            yield ('beginarr', None)
            i += 1
        elif c == ']':
            yield ('endarr', None)
            i += 1
        elif c == '/':
            m = re.match(r'/[^\s/\[\]<>(){}%]*', stream[i:])
            yield ('name', m.group(0)[1:])
            i += m.end()
        elif c in '+-.0123456789':
            m = re.match(r'[+-]?[0-9]*\.?[0-9]*', stream[i:])
            tok = m.group(0)
            if tok in ('', '+', '-', '.'):
                i += 1
                continue
            yield ('num', F(tok) if tok not in ('.',) else Fraction(0))
            i += m.end()
        else:
            m = re.match(r"[A-Za-z'\"*][A-Za-z0-9'\"*]*", stream[i:])
            if not m:
                i += 1
                continue
            yield ('op', m.group(0))
            i += m.end()


def pdf_page_rows(stream):
    """Rebuild rows of positioned text from one page content stream."""
    cells = []
    stack = []
    tm = [Fraction(0)] * 6
    tlm = [Fraction(0)] * 6
    leading = Fraction(0)
    arr = None
    for kind, val in _pdf_tokens(stream):
        if kind == 'beginarr':
            arr = []
            continue
        if kind == 'endarr':
            continue
        if kind in ('num', 'str', 'name'):
            if arr is not None:
                arr.append((kind, val))
            else:
                stack.append((kind, val))
            continue
        op = val
        if op == 'BT':
            tm = [Fraction(1), Fraction(0), Fraction(0), Fraction(1),
                  Fraction(0), Fraction(0)]
            tlm = list(tm)
        elif op == 'Tm':
            nums = [v for k, v in stack if k == 'num'][-6:]
            if len(nums) == 6:
                tm = list(nums)
                tlm = list(nums)
        elif op in ('Td', 'TD'):
            nums = [v for k, v in stack if k == 'num'][-2:]
            if len(nums) == 2:
                if op == 'TD':
                    leading = -nums[1]
                tlm[4] += nums[0]
                tlm[5] += nums[1]
                tm = list(tlm)
        elif op == 'TL':
            nums = [v for k, v in stack if k == 'num'][-1:]
            if nums:
                leading = nums[0]
        elif op == 'T*':
            tlm[5] -= leading
            tm = list(tlm)
        elif op == 'Tj' or op == "'" or op == '"':
            if op != 'Tj':
                tlm[5] -= leading
                tm = list(tlm)
            txt = ''.join(v for k, v in stack if k == 'str')
            cells.append((tm[5], tm[4], txt))
        elif op == 'TJ':
            txt = ''.join(v for k, v in (arr or []) if k == 'str')
            cells.append((tm[5], tm[4], txt))
        elif op == 'ET':
            pass
        stack = []
        arr = None
    rows = {}
    for y, x, t in cells:
        rows.setdefault(y, []).append((x, t))
    out = []
    for y in sorted(rows, reverse=True):
        out.append([t for _, t in sorted(rows[y], key=lambda p: p[0])])
    return out


TITLE_RE = re.compile(r'^Table\s+(\S+?):\s*(.*?)\s*\[\s*([^\]]*?)\s*\]$')
CONT_RE = re.compile(r'^Table\s+(\S+?)\s*\(continued\)\s*$')


class MemoTable(object):
    def __init__(self, tid, title, status):
        self.id = tid
        self.title = title
        self.status = status
        self.header = None
        self.rows = []

    def dicts(self):
        return [dict(zip(self.header, r)) for r in self.rows]


def read_memo(path):
    data = open(path, 'rb').read()
    objs = _pdf_objects(data)
    cat = None
    for num, (head, _) in objs.items():
        if b'/Catalog' in head:
            cat = num
    pages_ref = int(re.search(rb'/Pages\s+(\d+)\s+0\s+R', objs[cat][0]).group(1))

    def collect(num, acc):
        head = objs[num][0]
        if b'/Pages' in head and b'/Kids' in head:
            kids = re.search(rb'/Kids\s*\[(.*?)\]', head, re.S).group(1)
            for k in re.findall(rb'(\d+)\s+0\s+R', kids):
                collect(int(k), acc)
        else:
            acc.append(num)
        return acc

    pages = collect(pages_ref, [])
    tables = []
    cur = None
    expect_header = False
    for pnum in pages:
        cm = re.search(rb'/Contents\s+(\d+)\s+0\s+R', objs[pnum][0])
        if not cm:
            continue
        stream = _pdf_stream_text(*objs[int(cm.group(1))])
        for row in pdf_page_rows(stream):
            cells = [c.strip() for c in row]
            joined = ' '.join(cells).strip()
            if len(cells) == 1:
                m = TITLE_RE.match(joined)
                if m:
                    cur = MemoTable(m.group(1), m.group(2), m.group(3))
                    tables.append(cur)
                    expect_header = True
                    continue
                m = CONT_RE.match(joined)
                if m:
                    cur = None
                    for t in tables:
                        if t.id == m.group(1):
                            cur = t
                    expect_header = True
                    continue
                if joined.startswith('Table'):
                    cur = None
                    continue
            if cur is None:
                continue
            if expect_header:
                cur.header = cells
                expect_header = False
                continue
            if len(cells) == len(cur.header):
                cur.rows.append(cells)
            else:
                cur = None
    return tables


# ------------------------------------------------------------------- xlsx ----

XNS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
XRNS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


class Workbook(object):
    def __init__(self, path):
        from xml.etree import ElementTree as ET
        self.z = zipfile.ZipFile(path)
        wb = ET.fromstring(self.z.read('xl/workbook.xml'))
        pr = wb.find(XNS + 'workbookPr')
        self.date1904 = False
        if pr is not None:
            v = (pr.get('date1904') or '').strip().lower()
            self.date1904 = v in ('1', 'true')
        rels = {}
        for r in ET.fromstring(self.z.read('xl/_rels/workbook.xml.rels')):
            rels[r.get('Id')] = r.get('Target')
        self.parts = {}
        for s in wb.find(XNS + 'sheets'):
            t = rels[s.get(XRNS + 'id')]
            if t.startswith('/'):
                t = t[1:]
            elif not t.startswith('xl/'):
                t = 'xl/' + t
            self.parts[s.get('name')] = t
        self.sst = []
        if 'xl/sharedStrings.xml' in self.z.namelist():
            st = ET.fromstring(self.z.read('xl/sharedStrings.xml'))
            for si in st:
                self.sst.append(''.join(t.text or '' for t in si.iter(XNS + 't')))
        self._cache = {}

    def raw_rows(self, name):
        from xml.etree import ElementTree as ET
        if name in self._cache:
            return self._cache[name]
        root = ET.fromstring(self.z.read(self.parts[name]))
        out = []
        sd = root.find(XNS + 'sheetData')
        for row in sd.findall(XNS + 'row'):
            cells = {}
            for c in row.findall(XNS + 'c'):
                ref = c.get('r') or ''
                mm = re.match(r'([A-Z]+)', ref)
                if mm:
                    ci = 0
                    for ch in mm.group(1):
                        ci = ci * 26 + ord(ch) - 64
                else:
                    ci = len(cells) + 1
                t = c.get('t')
                v = c.find(XNS + 'v')
                if t == 's':
                    val = self.sst[int(v.text)] if v is not None else ''
                elif t == 'inlineStr':
                    isl = c.find(XNS + 'is')
                    val = ''.join(x.text or '' for x in isl.iter(XNS + 't')) \
                        if isl is not None else ''
                else:
                    val = v.text if v is not None else ''
                cells[ci] = val or ''
            if cells:
                out.append([cells.get(i + 1, '') for i in range(max(cells))])
            else:
                out.append([])
        self._cache[name] = out
        return out

    def table(self, name, key):
        rows = self.raw_rows(name)
        hi = None
        for i, r in enumerate(rows):
            if r and r[0].strip() == key:
                hi = i
                break
        if hi is None:
            return []
        header = [c.strip() for c in rows[hi]]
        out = []
        for r in rows[hi + 1:]:
            if len(r) < 2 or r[1].strip() == '':
                continue
            d = {}
            for j, h in enumerate(header):
                d[h] = (r[j].strip() if j < len(r) else '')
            out.append(d)
        return out

    def serial_to_date(self, serial):
        import datetime
        n = int(Fraction(F(serial)))
        base = datetime.date(1904, 1, 1) if self.date1904 else datetime.date(1899, 12, 30)
        return base + datetime.timedelta(days=n)


# ------------------------------------------------------------------ clock ----

import datetime as _dt

EPOCH = _dt.datetime(1970, 1, 1)


def to_epoch(dtobj):
    return int((dtobj - EPOCH).total_seconds())


def from_epoch(secs):
    return EPOCH + _dt.timedelta(seconds=secs)


def parse_offset(text):
    s = str(text).strip()
    sign = -1 if s.startswith('-') else 1
    s = s.lstrip('+-')
    if ':' in s:
        h, m = s.split(':')[:2]
    else:
        h, m = s[:2], s[2:4] or '0'
    return sign * (int(h) * 3600 + int(m) * 60)


class SiteClock(object):
    def __init__(self, doc):
        self.base = parse_offset(doc['base_offset'])
        tr = []
        for t in (doc.get('transitions') or []):
            tr.append((to_epoch(_dt.datetime.strptime(t['at_utc'], '%Y-%m-%dT%H:%M:%SZ')),
                       parse_offset(t['offset_after'])))
        tr.sort()
        self.tr = tr
        self.offsets = sorted(set([self.base] + [o for _, o in tr]))

    def offset_at(self, u):
        import bisect
        i = bisect.bisect_right([a for a, _ in self.tr], u)
        return self.tr[i - 1][1] if i else self.base

    def to_utc(self, naive_local_epoch):
        """naive_local_epoch: wall-clock seconds read as if UTC."""
        cands = []
        for o in self.offsets:
            u = naive_local_epoch - o
            if self.offset_at(u) == o:
                cands.append(u)
        if cands:
            return min(cands)
        for i, (at, after) in enumerate(self.tr):
            before = self.tr[i - 1][1] if i else self.base
            if after > before and at + before <= naive_local_epoch < at + after:
                return naive_local_epoch - before
        return naive_local_epoch - self.base

    def local(self, u):
        return from_epoch(u + self.offset_at(u))

    def local_date(self, u):
        return self.local(u).date()


# ---------------------------------------------------------------- aliases ----

SESSION_RE = re.compile(r'^(SQ|LN)-\d{4}-\d{2}$')


def norm(tok):
    return ('' if tok is None else str(tok)).strip().upper()


class Aliases(object):
    def __init__(self, db_path, sample_ids, client_map):
        con = sqlite3.connect(db_path)
        self.sess = []
        self.inst = []
        self.mat = []
        try:
            for tok, can, proj in con.execute(
                    'SELECT token, canonical, project FROM session_alias'):
                self.sess.append((norm(tok), norm(can), norm(proj)))
        except sqlite3.Error:
            pass
        try:
            for tok, can in con.execute(
                    'SELECT token, canonical FROM instrument_alias'):
                self.inst.append((norm(tok), norm(can)))
        except sqlite3.Error:
            pass
        try:
            for tok, can, proj, vf in con.execute(
                    'SELECT token, canonical, project, valid_from FROM material_alias'):
                self.mat.append((norm(tok), norm(can), norm(proj), str(vf).strip()))
        except sqlite3.Error:
            pass
        con.close()
        self.sample_ids = set(sample_ids)
        self.client_map = dict(client_map)
        self._sc = {}
        self._ic = {}
        self._mc = {}

    def session(self, token, project):
        key = (norm(token), norm(project))
        if key in self._sc:
            return self._sc[key]
        tok = key[0]
        seen = set()
        while tok and not SESSION_RE.match(tok) and tok not in seen:
            seen.add(tok)
            nxt = None
            for t, c, p in self.sess:
                if t == tok and (p == '*' or p == key[1]):
                    nxt = c
                    break
            if nxt is None:
                break
            tok = nxt
        res = tok if SESSION_RE.match(tok or '') else None
        self._sc[key] = res
        return res

    def instrument(self, token):
        tok = norm(token)
        if tok in self._ic:
            return self._ic[tok]
        cur = tok
        seen = set()
        while cur not in ('K1', 'K2') and cur not in seen:
            seen.add(cur)
            nxt = None
            for t, c in self.inst:
                if t == cur:
                    nxt = c
                    break
            if nxt is None:
                break
            cur = nxt
        res = cur if cur in ('K1', 'K2') else None
        self._ic[tok] = res
        return res

    CANON = ('RM-GLU-L', 'RM-GLU-H', 'RM-CAF', 'QC-SED', 'QC-MUS', 'QC-ALG',
             'ELM-ACT', 'BLK', 'COND')

    def is_canon_material(self, tok):
        return tok in self.CANON or tok in self.sample_ids

    def material(self, token, project, date_str):
        key = (norm(token), norm(project), date_str)
        if key in self._mc:
            return self._mc[key]
        cur = key[0]
        seen = set()
        while not self.is_canon_material(cur) and cur not in seen:
            seen.add(cur)
            best = None
            for t, c, p, vf in self.mat:
                if t != cur:
                    continue
                if not (p == '*' or p == key[1]):
                    continue
                if date_str is not None and vf > date_str:
                    continue
                if best is None or vf >= best[0]:
                    best = (vf, c)
            if best is None:
                if cur in self.client_map:
                    cur = self.client_map[cur]
                break
            cur = best[1]
        res = cur if self.is_canon_material(cur) else None
        self._mc[key] = res
        return res

    def material_class(self, mat):
        if mat in ('RM-GLU-L', 'RM-GLU-H', 'RM-CAF'):
            return 'RM'
        if mat in ('QC-SED', 'QC-MUS', 'QC-ALG'):
            return 'QC'
        if mat == 'ELM-ACT':
            return 'ELM'
        if mat == 'BLK':
            return 'BLK'
        if mat == 'COND':
            return 'COND'
        if mat in self.sample_ids:
            return 'SAMPLE'
        return None


# ---------------------------------------------------------------- layouts ----

EMAP = {
    'E1': {'N2': 'N', 'CO2': 'C'},
    'E2': {'N': 'N', 'C': 'C'},
    'E3': {'15N': 'N', '13C': 'C'},
    'E4': {'28': 'N', '44': 'C'},
    'E5': {'NITROGEN': 'N', 'CARBON': 'C'},
}
PMAP = {
    'P1': {'S': 'A', 'R': 'R'},
    'P2': {'SAMPLE': 'A', 'REF': 'R'},
    'P3': {'1': 'A', '0': 'R'},
    'P3i': {'1': 'A', '0': 'R'},
    'P4': {'ANALYTE': 'A', 'REFERENCE': 'R'},
    'P5': {'PK': 'A', 'RG': 'R'},
}

# layout -> (family, time kind, area unit, amp unit, delta unit, element map,
#            peak map, void-true token, void-false token, decimal comma)
LAYOUTS = {
    'L01': ('csv', 'local_iso', 'Vs', 'mV', 'permil', 'E1', 'P1', 'V', '', False),
    'L02': ('tsv', 'epoch_s', 'mVs', 'V', 'permil', 'E2', 'P2', 'VOID', 'OK', False),
    'L03': ('psv', 'local_dmy', 'Vs', 'mV', 'permil', 'E3', 'P3', 'DEAD', 'LIVE', True),
    'L04': ('jsonl_flat', 'epoch_ms', 'Vs', 'mV', 'milli', 'E3', 'P3i', 'true', 'false', False),
    'L05': ('ndjson_nested', 'iso_off', 'Vs', 'mV', 'permil', 'E2', 'P2', 'Y', 'N', False),
    'L06': ('xml_attr', 'iso_z', 'mVs', 'mV', 'permil', 'E1', 'P1', '1', '0', False),
    'L07': ('sqlite_split', 'local_compact', 'Vs', 'mV', 'milli', 'E1', 'P2', '1', '0', False),
    'L08': ('sqlite_flat', 'epoch_s', 'Vs', 'V', 'permil', 'E2', 'P1', 'VOID', '', False),
    'L09': ('yaml_blocks', 'iso_off', 'Vs', 'mV', 'permil', 'E1', 'P2', 'true', 'false', False),
    'L10': ('yml_grouped', 'local_iso', 'mVs', 'mV', 'permil', 'E5', 'P4', 'void', 'ok', False),
    'L11': ('json_columnar', 'epoch_s', 'mVs', 'mV', 'milli', 'E2', 'P1', '1', '0', False),
    'L12': ('fixed', 'local_compact', 'Vs', 'mV', 'permil', 'E1', 'P5', 'X', '-', False),
    'L13': ('md', 'iso_z', 'Vs', 'V', 'permil', 'E3', 'P2', 'VOID', '', False),
    'L14': ('csv_semi', 'local_dmy_slash', 'Vs', 'mV', 'permil', 'E2', 'P1', 'V', '', True),
    'L15': ('tsv_wide', 'epoch_ms', 'Vs', 'mV', 'permil', None, None, '1', '', False),
    'L16': ('jsonl_nested', 'iso_z', 'Vs', 'mV', 'ratio', 'E1', 'P2', 'true', 'false', False),
    'L17': ('csv_comment', 'iso_off', 'mVs', 'V', 'permil', 'E4', 'P3', '1', '0', False),
    'L18': ('psv', 'epoch_ms', 'mVs', 'mV', 'milli', 'E4', 'P5', 'Y', 'N', False),
    'L19': ('xml_child', 'local_t', 'Vs', 'mV', 'milli', 'E5', 'P4', 'true', 'false', False),
    'L20': ('ndjson_flat', 'basic_z', 'Vs', 'V', 'permil', 'E1', 'P1', 'void', 'ok', False),
    'L21': ('sqlite_runlog', 'iso_off', 'mVs', 'mV', 'permil', 'E1', 'P2', 'VOID', '', False),
    'L22': ('sqlite_eav', 'epoch_s', 'Vs', 'mV', 'permil', 'E2', 'P1', '1', '0', False),
}

FIELDS = {
    'L01': ['proj', 'seq', 'inst', 'pos', 'gas', 'ptype', 'rev', 'void',
            't_local', 'area_vs', 'amp_mv', 'd_permil'],
    'L02': ['Project', 'Sequence', 'Line', 'Counter', 'Species', 'PeakKind',
            'Revision', 'Status', 'EpochS', 'Area_mVs', 'Amp_V', 'dRaw'],
    'L03': ['projekt', 'lauf', 'geraet', 'position', 'isotop', 'peaktyp',
            'revision', 'zustand', 'zeit', 'flaeche_vs', 'amplitude_mv', 'delta'],
    'L04': ['prj', 'run', 'ln', 'slot', 'el', 'pk', 'rv', 'void', 'ts_ms',
            'a', 'amp', 'dm'],
    'L11': ['project', 'sequence', 'instrument', 'counter', 'species', 'peak',
            'revision', 'void', 'epoch_s', 'area_mvs', 'amp_mv', 'd_milli'],
    'L12': [('PROJECT', 1), ('SEQUENCE', 11), ('INST', 27), ('POS', 36),
            ('GAS', 41), ('PT', 46), ('REV', 50), ('VOID', 54), ('TIME', 59),
            ('AREA_VS', 75), ('AMP_MV', 86), ('D_PERMIL', 93)],
    'L13': ['project', 'sequence', 'instrument', 'position', 'isotope', 'peak',
            'rev', 'void', 'time_utc', 'area_vs', 'amp_v', 'delta'],
    'L14': ['Projekt', 'Sequenz', 'Geraet', 'Pos', 'Element', 'Typ', 'Rev',
            'Void', 'Zeit', 'Flaeche', 'Amplitude', 'Delta'],
    'L17': ['project', 'sequence', 'instrument', 'counter', 'mass', 'peak',
            'rev', 'void', 'ts', 'area_mvs', 'amp_v', 'd'],
    'L18': ['PRJ', 'SEQ', 'INST', 'CTR', 'MZ', 'PT', 'REV', 'VD', 'EPOCHMS',
            'AREA_MVS', 'AMP_MV', 'D_MILLI'],
    'L20': ['PROJ', 'SEQ', 'INST', 'POS', 'GAS', 'PT', 'REV', 'STATUS', 'TS',
            'AREA', 'AMP_V', 'DELTA'],
}

ORDER = ('project', 'session', 'instrument', 'counter', 'element', 'peak',
         'rev', 'void', 'time', 'area', 'amp', 'delta')


def _rec(vals):
    return dict(zip(ORDER, vals))


def split_lines(text, sep):
    lines = [l for l in text.split('\n') if l.strip() != '']
    return [r for r in csv.reader(lines, delimiter=sep)]


def _split_rows(text, sep):
    rows = split_lines(text, sep)
    header = [h.strip() for h in rows[0]]
    return [dict(zip(header, r)) for r in rows[1:]]


def read_shard(path, layout):
    """Return the raw records of one shard file, in document order."""
    fam = LAYOUTS[layout][0]
    f = FIELDS.get(layout)
    out = []
    if fam in ('csv', 'tsv', 'psv', 'csv_semi', 'csv_comment'):
        sep = {'csv': ',', 'tsv': '\t', 'psv': '|', 'csv_semi': ';',
               'csv_comment': ','}[fam]
        text = open(path, 'r', encoding='utf-8').read()
        if fam == 'csv_comment':
            text = '\n'.join(l for l in text.split('\n')
                             if not l.lstrip().startswith('#'))
        for row in _split_rows(text, sep):
            out.append(_rec([row.get(k, '') for k in f]))
    elif fam in ('jsonl_flat', 'ndjson_flat'):
        for line in open(path, 'r', encoding='utf-8'):
            if not line.strip():
                continue
            o = json.loads(line)
            out.append(_rec([o.get(k) for k in f]))
    elif fam == 'ndjson_nested':
        for line in open(path, 'r', encoding='utf-8'):
            if not line.strip():
                continue
            o = json.loads(line)
            out.append(_rec([o['meta']['project'], o['meta']['sequence'],
                             o['meta']['instrument'], o['inj']['position'],
                             o['peak']['gas'], o['peak']['type'], o['rev'],
                             o['void'], o['inj']['time'], o['peak']['area'],
                             o['peak']['height_mv'], o['peak']['delta']]))
    elif fam == 'jsonl_nested':
        for line in open(path, 'r', encoding='utf-8'):
            if not line.strip():
                continue
            o = json.loads(line)
            for p in o['peaks']:
                out.append(_rec([o['project'], o['sequence'], o['instrument'],
                                 o['position'], p['gas'], p['type'], p['rev'],
                                 p['void'], o['time'], p['area'], p['amp'],
                                 p['ratio']]))
    elif fam == 'json_columnar':
        doc = json.load(open(path, 'r', encoding='utf-8'))
        cols = doc['export']['columns']
        for row in doc['export']['rows']:
            d = dict(zip(cols, row))
            out.append(_rec([d.get(k) for k in f]))
    elif fam == 'xml_attr':
        from xml.etree import ElementTree as ET
        root = ET.parse(path).getroot()
        for inj in root.iter('inj'):
            for p in inj.findall('peak'):
                out.append(_rec([inj.get('project'), inj.get('seq'),
                                 inj.get('inst'), inj.get('pos'), p.get('el'),
                                 p.get('kind'), p.get('rev'), p.get('void'),
                                 inj.get('t'), p.get('area_mvs'),
                                 p.get('amp_mv'), p.get('d')]))
    elif fam == 'xml_child':
        from xml.etree import ElementTree as ET
        root = ET.parse(path).getroot()
        keys = ['project', 'sequence', 'instrument', 'counter', 'species',
                'kind', 'revision', 'void', 'time', 'area_vs', 'amp_mv',
                'd_milli']
        for rec in list(root):
            d = {c.tag: (c.text or '') for c in rec}
            out.append(_rec([d.get(k, '') for k in keys]))
    elif fam == 'yaml_blocks':
        doc = yaml_load(open(path, 'r', encoding='utf-8').read())
        for b in doc:
            for p in (b.get('peaks') or []):
                out.append(_rec([b['project'], b['sequence'], b['instrument'],
                                 b['position'], p['gas'], p['type'],
                                 p['revision'], p['void'], b['time'],
                                 p['area_vs'], p['amp_mv'], p['delta']]))
    elif fam == 'yml_grouped':
        doc = yaml_load(open(path, 'r', encoding='utf-8').read())
        for g in doc['sequences']:
            for p in (g.get('peaks') or []):
                out.append(_rec([g['project'], g['sequence'], g['instrument'],
                                 p['pos'], p['species'], p['kind'], p['rev'],
                                 p['state'], p['t'], p['area_mvs'],
                                 p['amp_mv'], p['d']]))
    elif fam == 'fixed':
        lines = open(path, 'r', encoding='utf-8').read().split('\n')
        spans = []
        for i, (name, start) in enumerate(f):
            end = f[i + 1][1] - 1 if i + 1 < len(f) else None
            spans.append((start - 1, end))
        for line in lines[2:]:
            if line.strip() == '':
                continue
            vals = [(line[a:b] if b is not None else line[a:]).strip()
                    for a, b in spans]
            out.append(_rec(vals))
    elif fam == 'md':
        for line in open(path, 'r', encoding='utf-8'):
            s = line.strip()
            if not s.startswith('|'):
                continue
            cells = [c.strip() for c in s.strip('|').split('|')]
            if not cells or cells[0] == f[0] or set(cells[0]) <= set('-: '):
                continue
            out.append(_rec(cells[:12]))
    elif fam == 'tsv_wide':
        lines = [l for l in open(path, 'r', encoding='utf-8').read().split('\n')
                 if l.strip() != '']
        header = lines[0].split('\t')
        for line in lines[1:]:
            row = dict(zip(header, line.split('\t')))
            for el in ('N', 'C'):
                rv = (row.get('rev_' + el) or '').strip()
                ar = (row.get('area_' + el) or '').strip()
                if rv == '' and ar == '':
                    continue
                out.append(_rec([row.get('project'), row.get('sequence'),
                                 row.get('instrument'), row.get('counter'),
                                 el, 'A', rv, row.get('void_' + el),
                                 row.get('epoch_ms'), ar,
                                 row.get('amp_' + el), row.get('d_' + el)]))
    elif fam == 'sqlite_flat':
        con = sqlite3.connect(path)
        cols = ['project', 'sequence', 'instrument', 'counter', 'gas',
                'peaktype', 'revision', 'void_flag', 'epoch', 'area',
                'amplitude', 'delta']
        for row in con.execute('SELECT %s FROM export ORDER BY rowid'
                               % ','.join('"%s"' % c for c in cols)):
            out.append(_rec(list(row)))
        con.close()
    elif fam == 'sqlite_split':
        con = sqlite3.connect(path)
        q = ('SELECT i.project, i.seq, i.inst, i.pos, p.el, p.kind, p.rev, '
             'p.voided, i.t_local, p.area_vs, p.amp_mv, p.d_milli '
             'FROM peaks p JOIN injections i ON i.inj_id = p.inj_id '
             'ORDER BY p.peak_id')
        for row in con.execute(q):
            out.append(_rec(list(row)))
        con.close()
    elif fam == 'sqlite_runlog':
        con = sqlite3.connect(path)
        q = ('SELECT r.project, r.sequence, r.instrument, p.counter, p.gas, '
             'p.peak, p.rev, p.flag, p.t, p.area_mvs, p.amp_mv, p.delta '
             'FROM peaktab p JOIN runlog r ON r.run_key = p.run_key '
             'ORDER BY p.row_id')
        for row in con.execute(q):
            out.append(_rec(list(row)))
        con.close()
    elif fam == 'sqlite_eav':
        con = sqlite3.connect(path)
        keys = ['project', 'seq', 'inst', 'pos', 'el', 'type', 'rev', 'void',
                't', 'area', 'amp', 'd']
        cur = {}
        cur_rec = None
        for rec, field, value in con.execute(
                'SELECT rec, field, value FROM kv ORDER BY rec, rowid'):
            if cur_rec is not None and rec != cur_rec:
                out.append(_rec([cur.get(k) for k in keys]))
                cur = {}
            cur_rec = rec
            cur[field] = value
        if cur_rec is not None:
            out.append(_rec([cur.get(k) for k in keys]))
        con.close()
    else:
        raise ValueError('unknown family ' + fam)
    return out


def parse_time(kind, raw, clock):
    s = str(raw).strip()
    if kind == 'epoch_s':
        return int(Fraction(F(s)))
    if kind == 'epoch_ms':
        return int(Fraction(F(s)) / 1000)
    if kind == 'iso_z':
        return to_epoch(_dt.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ'))
    if kind == 'basic_z':
        return to_epoch(_dt.datetime.strptime(s, '%Y%m%dT%H%M%SZ'))
    if kind == 'iso_off':
        m = re.match(r'(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})'
                     r'(Z|[+-]\d{2}:?\d{2})$', s)
        base = to_epoch(_dt.datetime.strptime(m.group(1) + ' ' + m.group(2),
                                              '%Y-%m-%d %H:%M:%S'))
        off = 0 if m.group(3) == 'Z' else parse_offset(m.group(3))
        return base - off
    if kind == 'local_iso':
        nv = to_epoch(_dt.datetime.strptime(s, '%Y-%m-%d %H:%M:%S'))
    elif kind == 'local_t':
        nv = to_epoch(_dt.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S'))
    elif kind == 'local_dmy':
        nv = to_epoch(_dt.datetime.strptime(s, '%d.%m.%Y %H:%M:%S'))
    elif kind == 'local_dmy_slash':
        nv = to_epoch(_dt.datetime.strptime(s, '%d/%m/%Y %H:%M:%S'))
    elif kind == 'local_compact':
        nv = to_epoch(_dt.datetime.strptime(s, '%Y%m%d%H%M%S'))
    else:
        raise ValueError('time kind ' + kind)
    return clock.to_utc(nv)


def parse_local_stamp(text, clock):
    """A typed local wall time `YYYY-MM-DD[T ]HH:MM[:SS]` read under H3."""
    s = str(text).strip().replace('T', ' ')
    if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$', s):
        s += ':00'
    return parse_time('local_iso', s, clock)


def decode_record(rec, layout, clock):
    (fam, tkind, aunit, ampunit, dunit, em, pm, vt, vf, comma) = LAYOUTS[layout]

    def txt(v):
        return '' if v is None else str(v).strip()

    def num(v):
        s = txt(v)
        if comma:
            s = s.replace('.', '').replace(',', '.')
        return F(s)

    if em is None:
        element = txt(rec['element']).upper()
    else:
        element = EMAP[em].get(txt(rec['element']).upper())
    if pm is None:
        peak = 'A'
    else:
        pv = txt(rec['peak'])
        if pm == 'P3i' and pv != '':
            pv = str(int(Fraction(F(pv))))
        peak = PMAP[pm].get(pv.upper())
    area = num(rec['area'])
    if aunit == 'mVs':
        area = area / 1000
    amp = num(rec['amp'])
    if ampunit == 'V':
        amp = amp * 1000
    delta = num(rec['delta'])
    if dunit == 'milli':
        delta = delta / 1000
    elif dunit == 'ratio':
        delta = (delta - 1) * 1000
    vv = rec['void']
    if isinstance(vv, bool):
        voided = vv
    else:
        voided = txt(vv).upper() == str(vt).strip().upper()
    return {
        'project': norm(rec['project']),
        'session_tok': norm(rec['session']),
        'instrument_tok': norm(rec['instrument']),
        'counter': int(Fraction(F(txt(rec['counter'])))),
        'element': element,
        'peak': peak,
        'rev': int(Fraction(F(txt(rec['rev'])))) if txt(rec['rev']) != '' else 0,
        'void': voided,
        'utc': parse_time(tkind, rec['time'], clock),
        'area': rnd(area, 4),
        'amp': int(rnd(amp, 0)),
        'delta': rnd(delta, 3),
    }


# ------------------------------------------------------------- input load ----

def read_delimited(path, sep):
    text = open(path, 'r', encoding='utf-8').read()
    rows = split_lines(text, sep)
    if not rows:
        return []
    header = [h.strip() for h in rows[0]]
    return [dict(zip(header, [c.strip() for c in r])) for r in rows[1:]]


def read_jsonl(path):
    out = []
    with open(path, 'r', encoding='utf-8') as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    return out


def section_aw(path):
    masses = {}
    txt = open(path, 'r', encoding='utf-8').read().split('\n')
    i = 0
    while i < len(txt) and not txt[i].strip().startswith('Section AW'):
        i += 1
    i += 1
    while i < len(txt):
        line = txt[i].strip()
        if line == '':
            break
        if '|' in line:
            a, b = [x.strip() for x in line.split('|')[:2]]
            if a != 'element':
                masses[a] = b
        i += 1
    return masses


class Sequence(object):
    def __init__(self, token, project, instrument, kind):
        self.token = token
        self.project = project
        self.instrument_tok = instrument
        self.kind = kind
        self.slots = {}
        self.slot_order = []


def read_sequences(path):
    from xml.etree import ElementTree as ET
    root = ET.parse(path).getroot()
    out = []
    for s in root.iter('sequence'):
        seq = Sequence(norm(s.get('id')), norm(s.get('project')),
                       norm(s.get('instrument')), norm(s.get('kind')))
        for sl in s.findall('slot'):
            tray = int(sl.get('tray'))
            seq.slots[tray] = ((sl.get('token') or '').strip(),
                               norm(sl.get('capsule')))
            seq.slot_order.append(tray)
        out.append(seq)
    return out


def read_autosampler(path):
    out = []
    for line in open(path, 'r', encoding='utf-8'):
        if line.lstrip().startswith('#') or line.strip() == '':
            continue
        p = [x.strip() for x in line.split('|')]
        if len(p) < 7:
            continue
        out.append({'event_id': p[0], 'local_time': p[1], 'instrument': p[2],
                    'session': p[3], 'event': p[4], 'detail': p[5],
                    'state': p[6]})
    return out


class Env(object):
    """Everything read from the input directory."""

    def __init__(self, data_dir):
        self.dir = data_dir
        j = lambda n: os.path.join(data_dir, n)
        self.profile = yaml_load(open(j('analysis_profile.yml'), 'r',
                                      encoding='utf-8').read())
        self.project = norm(self.profile['project'])
        self.elements = list(self.profile['elements'])
        self.clock = SiteClock(yaml_load(open(j('site_clock.yaml'), 'r',
                                             encoding='utf-8').read()))
        self.memo = {}
        for t in read_memo(j('governance_memo.pdf')):
            self.memo.setdefault(t.id, t)
        self.wb = Workbook(j('reference_workbook.xlsx'))
        self.masses = section_aw(j('stat_quick_reference.txt'))
        self.manifest = read_delimited(j('sample_manifest.csv'), ',')
        self.requests = read_delimited(j('client_requests.tsv'), '\t')
        self.sample_ids = [norm(r['sample_id']) for r in self.manifest]
        self.client_map = {}
        for r in self.manifest:
            if r.get('client_id'):
                self.client_map[norm(r['client_id'])] = norm(r['sample_id'])
        self.alias = Aliases(j('alias_register.sqlite'), self.sample_ids,
                             self.client_map)
        self.catalog = json.load(open(j('ingest_catalog.json'), 'r',
                                     encoding='utf-8'))
        self.sequences = read_sequences(j('sequence_tables.xml'))
        self.journal = read_jsonl(j('tray_corrections.ndjson'))
        self.session_events = read_delimited(j('session_events.psv'), '|')
        self.autosampler = read_autosampler(j('autosampler_events.txt'))
        self.capsule_reg = read_delimited(j('rm_capsule_register.psv'), '|')
        self.capsule_flags = read_jsonl(j('capsule_flags.jsonl'))
        self.balance = read_delimited(j('balance_calibration.tsv'), '\t')
        self.published = read_delimited(j('published_results.csv'), ',')
        self.pub_params = json.load(open(j('published_session_params.json'),
                                        'r', encoding='utf-8'))
        self.dashboard = read_delimited(j('qc_dashboard.csv'), ',')
        self.cache = read_jsonl(j('lims_result_cache.jsonl'))
        self.noticeboard = open(j('lab_noticeboard.txt'), 'r',
                                encoding='utf-8').read()
        self.rerun = open(j('rerun_pack.md'), 'r', encoding='utf-8').read()
        self._in_force = {}
        for tid, t in self.memo.items():
            if norm(t.status) == 'IN FORCE':
                self._in_force[tuple(t.header)] = t

    def table_by_header(self, *cols):
        for header, t in self._in_force.items():
            if all(c in header for c in cols):
                return t
        return None


# -------------------------------------------------------------- ingestion ----

class Ingest(object):
    def __init__(self, env):
        self.env = env
        self.replay()
        self.load_audit()
        self.read_files()
        self.select_revisions()

    def replay(self):
        env = self.env
        cat_proj = norm(env.catalog.get('project') or env.project)
        state = {}
        layouts = {}
        first_reg = {}
        for ev in sorted(env.catalog['events'], key=lambda e: e['event']):
            act = norm(ev.get('action'))
            if act == 'VERIFY':
                continue
            sess = env.alias.session(ev.get('session'), cat_proj)
            key = (ev['file'], sess)
            state[key] = act
            if act == 'REGISTER':
                layouts.setdefault(ev['file'], ev.get('layout'))
                if ev['file'] not in first_reg:
                    first_reg[ev['file']] = ev['event']
        self.active = {}
        for (fn, sess), act in state.items():
            if act == 'REGISTER':
                self.active.setdefault(fn, set()).add(sess)
        self.layouts = layouts
        self.file_order = [f for f in sorted(first_reg, key=lambda x: first_reg[x])
                           if f in self.active]

    def load_audit(self):
        env = self.env
        con = sqlite3.connect(os.path.join(env.dir, 'reintegration_audit.db'))
        self.audit = {}
        emap = dict(EMAP['E1'])
        emap.update(EMAP['E2'])
        for (eid, proj, seq, ctr, gas, rev, action, reason, entered) in con.execute(
                'SELECT entry_id, project, sequence, counter, gas, revision, '
                'action, reason_code, entered_utc FROM audit_trail'):
            proj = norm(proj)
            sess = env.alias.session(seq, proj)
            el = emap.get(norm(gas))
            if sess is None or el is None:
                continue
            key = (proj, sess, int(ctr), el, int(rev))
            cand = (str(entered), int(eid), norm(action), norm(reason))
            prev = self.audit.get(key)
            if prev is None or (cand[0], cand[1]) > (prev[0], prev[1]):
                self.audit[key] = cand
        con.close()
        c1 = env.table_by_header('code', 'status')
        self.reason_status = {}
        if c1:
            for r in c1.dicts():
                self.reason_status[norm(r['code'])] = norm(r['status'])

    def read_files(self):
        env = self.env
        self.counts = {'files_read': 0, 'records_read': 0, 'other_project': 0,
                       'reference_peaks': 0, 'inactive_segment': 0,
                       'duplicates': 0}
        self.lineage = []
        self.records = []
        self.alias_seen = set()
        seen = set()
        for fn in self.file_order:
            layout = self.layouts[fn]
            path = os.path.join(env.dir, fn)
            raw = read_shard(path, layout)
            st = {'file': fn, 'layout': layout, 'records': 0,
                  'other_project': 0, 'reference_peaks': 0,
                  'inactive_segment': 0, 'duplicates': 0, 'unique': 0}
            active = self.active.get(fn, set())
            for rr in raw:
                st['records'] += 1
                rec = decode_record(rr, layout, env.clock)
                if rec['project'] != env.project:
                    st['other_project'] += 1
                    continue
                if rec['peak'] != 'A':
                    st['reference_peaks'] += 1
                    continue
                sess = env.alias.session(rec['session_tok'], rec['project'])
                if sess is None or sess not in active:
                    st['inactive_segment'] += 1
                    continue
                self.alias_seen.add(('session', rec['session_tok'], sess))
                self.alias_seen.add(('instrument', rec['instrument_tok'],
                                     env.alias.instrument(rec['instrument_tok'])))
                key = (sess, rec['counter'], rec['element'], rec['rev'])
                if key in seen:
                    st['duplicates'] += 1
                    continue
                seen.add(key)
                st['unique'] += 1
                rec['session'] = sess
                rec['file'] = fn
                self.records.append(rec)
            self.counts['files_read'] += 1
            for k in ('other_project', 'reference_peaks', 'inactive_segment',
                      'duplicates'):
                self.counts[k] += st[k]
            self.counts['records_read'] += st['records']
            self.lineage.append(st)

    def admitted(self, sess, counter, element, rev):
        if rev == 0:
            return True
        entry = self.audit.get((self.env.project, sess, counter, element, rev))
        if entry is None:
            return False
        return entry[2] == 'APPROVE' and \
            self.reason_status.get(entry[3]) == 'ACCEPTED'

    def select_revisions(self):
        groups = {}
        for rec in self.records:
            groups.setdefault((rec['session'], rec['counter'], rec['element']),
                              []).append(rec)
        self.counts.update({'revisions_not_admitted': 0,
                            'revisions_superseded': 0, 'voided': 0, 'kept': 0})
        self.kept = []
        self.inj_time = {}
        self.inj_instrument = {}
        for (sess, ctr, el), recs in groups.items():
            for r in recs:
                self.inj_time.setdefault((sess, ctr), r['utc'])
                self.inj_instrument.setdefault((sess, ctr), r['instrument_tok'])
            ok = []
            for r in recs:
                if self.admitted(sess, ctr, el, r['rev']):
                    ok.append(r)
                else:
                    self.counts['revisions_not_admitted'] += 1
            if not ok:
                continue
            ok.sort(key=lambda r: r['rev'])
            chosen = ok[-1]
            self.counts['revisions_superseded'] += len(ok) - 1
            if chosen['void']:
                self.counts['voided'] += 1
                continue
            self.counts['kept'] += 1
            self.kept.append(chosen)


# ---------------------------------------------------------------- sessions ----

class Session(object):
    pass


def journal_effect(entries):
    """Return the seqs of entries still in effect (REVERSE chains resolved)."""
    by_seq = {e['seq']: e for e in entries}
    reversers = {}
    for e in entries:
        if norm(e.get('action')) == 'REVERSE' and e.get('reverses') is not None:
            reversers.setdefault(e['reverses'], []).append(e['seq'])
    memo = {}

    def live(seq):
        if seq in memo:
            return memo[seq]
        memo[seq] = True
        res = True
        for r in reversers.get(seq, []):
            if r in by_seq and live(r):
                res = False
                break
        memo[seq] = res
        return res

    return set(s for s in by_seq if live(s))


class Batch(object):
    def __init__(self, env, ing):
        self.env = env
        self.ing = ing
        self.build_skips()
        self.build_events()
        self.build_sessions()
        self.build_trays()
        self.build_exclusions()
        self.build_injections()

    # -- autosampler ---------------------------------------------------------
    def build_skips(self):
        env = self.env
        self.skips = {}
        seen = set()
        for ev in env.autosampler:
            if ev['event_id'] in seen:
                continue
            seen.add(ev['event_id'])
            if norm(ev['event']) != 'SKIP' or ev['state'].strip().lower() != 'ok':
                continue
            m = re.search(r'-?\d+', ev['detail'])
            if not m:
                continue
            sess = env.alias.session(ev['session'], env.project)
            if sess is None:
                continue
            self.skips.setdefault(sess, []).append(int(m.group(0)))

    def tray_of(self, sess, counter):
        sk = self.skips.get(sess, [])
        return counter + sum(1 for c in sk if c <= counter)

    # -- session events ------------------------------------------------------
    def build_events(self):
        env = self.env
        self.pauses = {}
        self.leak = {}
        rows = []
        for r in env.session_events:
            sess = env.alias.session(r['session'], norm(r['project']))
            if sess is None:
                continue
            u = parse_local_stamp(r['local_time'], env.clock)
            rows.append((sess, norm(r['event']), u, r['event_id'],
                         (r.get('detail') or '').strip()))
        for sess, evt, u, eid, detail in rows:
            if evt in ('PAUSE', 'RESUME'):
                self.pauses.setdefault(sess, []).append((u, evt))
        for sess in self.pauses:
            self.pauses[sess].sort()
        leak_rows = {}
        for sess, evt, u, eid, detail in rows:
            if evt != 'LEAK_CHECK':
                continue
            cur = leak_rows.get(sess)
            if cur is None or (u, eid) > (cur[0], cur[1]):
                leak_rows[sess] = (u, eid, detail)
        for sess, (u, eid, detail) in leak_rows.items():
            self.leak[sess] = norm(detail) == 'FAIL'

    def pause_intervals(self, sess):
        out = []
        pending = None
        for u, evt in self.pauses.get(sess, []):
            if evt == 'PAUSE':
                if pending is None:
                    pending = u
            else:
                if pending is not None:
                    out.append((pending, u))
                    pending = None
        return out

    def run_minutes(self, sess, start, utc):
        secs = Fraction(utc - start)
        for a, b in self.pause_intervals(sess):
            if a < utc:
                secs -= Fraction(min(b, utc) - a)
        return secs / 60

    # -- sessions ------------------------------------------------------------
    def build_sessions(self):
        env = self.env
        self.sessions = {}
        for seq in env.sequences:
            if seq.project != env.project:
                continue
            sid = env.alias.session(seq.token, seq.project)
            if sid is None:
                continue
            s = Session()
            s.id = sid
            s.seq = seq
            s.kind = seq.kind
            s.instrument = env.alias.instrument(seq.instrument_tok)
            s.counters = sorted(c for (ss, c) in self.ing.inj_time if ss == sid)
            s.start = self.ing.inj_time.get((sid, 1))
            if s.start is None and s.counters:
                s.start = self.ing.inj_time[(sid, s.counters[0])]
            if s.instrument is None and s.counters:
                s.instrument = env.alias.instrument(
                    self.ing.inj_instrument[(sid, s.counters[0])])
            s.date = env.clock.local_date(s.start) if s.start is not None else None
            s.date_str = s.date.isoformat() if s.date else None
            s.leak_fail = self.leak.get(sid, False)
            self.sessions[sid] = s
        self.order = sorted(self.sessions)
        self.analytical = [s for s in self.order
                           if self.sessions[s].kind == 'ANALYTICAL']
        self.linearity = [s for s in self.order
                          if self.sessions[s].kind == 'LINEARITY']

    # -- trays ---------------------------------------------------------------
    def build_trays(self):
        env = self.env
        self.alias_extra = set()
        jr = {}
        for e in env.journal:
            if norm(e.get('project')) != env.project:
                continue
            sess = env.alias.session(e.get('session'), norm(e['project']))
            jr.setdefault(sess, []).append(e)
            if sess is not None:
                self.alias_extra.add(('session', norm(e.get('session')), sess))
        for s in self.sessions.values():
            s.trays = {}
            s.counter_of = {}
            for c in s.counters:
                s.counter_of[self.tray_of(s.id, c)] = c
            entries = [e for e in jr.get(s.id, [])
                       if norm(e.get('status')) == 'POSTED'
                       and str(e.get('field')).strip() == 'token']
            live = journal_effect(entries)
            sets = {}
            for e in entries:
                if norm(e.get('action')) != 'SET' or e['seq'] not in live:
                    continue
                tray = int(e['tray'])
                if tray not in sets or e['seq'] > sets[tray]['seq']:
                    sets[tray] = e
            for e in jr.get(s.id, []):
                if str(e.get('field')).strip() != 'token':
                    continue
                tok = norm(e.get('value'))
                if tok:
                    self.alias_extra.add(
                        ('material', tok,
                         env.alias.material(tok, env.project, s.date_str)))
            for tray in sorted(s.seq.slots):
                tok_raw, capsule = s.seq.slots[tray]
                self.alias_extra.add(
                    ('material', norm(tok_raw),
                     env.alias.material(tok_raw, env.project, s.date_str)))
                jseq = ''
                token = tok_raw.strip()
                if tray in sets:
                    jseq = sets[tray]['seq']
                    token = str(sets[tray].get('value') or '').strip()
                mat = env.alias.material(token, env.project, s.date_str)
                s.trays[tray] = {
                    'tray': tray, 'sequence_token': tok_raw.strip(),
                    'journal_seq': jseq, 'token': token, 'material': mat,
                    'class': env.alias.material_class(mat),
                    'capsule': capsule,
                    'counter': s.counter_of.get(tray),
                }
            self.alias_extra.add(('session', s.seq.token, s.id))

    # -- exclusions ----------------------------------------------------------
    def build_exclusions(self):
        env = self.env
        r1 = env.table_by_header('ruling', 'target')
        self.rulings = [r for r in (r1.dicts() if r1 else [])
                        if norm(r['status']) == 'IN FORCE']
        pos_rulings = {}
        for r in self.rulings:
            if norm(r['action']) != 'EXCLUDE_POSITION':
                continue
            if norm(r['project']) != env.project:
                continue
            target = r['target'].strip()
            if '/' not in target:
                continue
            stok, tray = target.rsplit('/', 1)
            sess = env.alias.session(stok, norm(r['project']))
            if sess is None or not tray.strip().lstrip('-').isdigit():
                continue
            key = (sess, int(tray))
            cur = pos_rulings.get(key)
            if cur is None or (r['date'], r['ruling']) > (cur['date'], cur['ruling']):
                pos_rulings[key] = r
        self.pos_rulings = pos_rulings
        x1 = env.table_by_header('code', 'effect')
        eff = {}
        for r in (x1.dicts() if x1 else []):
            eff[norm(r['code'])] = norm(r['effect'])
        self.flag_exclude = {}
        for fl in env.capsule_flags:
            if eff.get(norm(fl.get('code'))) != 'EXCLUDE':
                continue
            cap = norm(fl.get('capsule'))
            if cap not in self.flag_exclude:
                self.flag_exclude[cap] = norm(fl.get('code'))
        for s in self.sessions.values():
            for tray, info in s.trays.items():
                tag = ''
                r = pos_rulings.get((s.id, tray))
                if r is not None:
                    tag = 'RULING:' + r['ruling'].strip()
                elif info['capsule'] and info['capsule'] in self.flag_exclude:
                    tag = 'FLAG:' + self.flag_exclude[info['capsule']]
                info['excluded'] = tag

    # -- injections ----------------------------------------------------------
    def build_injections(self):
        env = self.env
        self.inj = {}
        for rec in self.ing.kept:
            s = self.sessions.get(rec['session'])
            if s is None:
                continue
            tray = self.tray_of(s.id, rec['counter'])
            info = s.trays.get(tray, {'material': None, 'class': None,
                                      'capsule': '', 'excluded': ''})
            item = {
                'session': s.id, 'instrument': env.alias.instrument(
                    rec['instrument_tok']) or s.instrument,
                'counter': rec['counter'], 'tray': tray,
                'material': info['material'], 'class': info['class'],
                'capsule': info['capsule'], 'element': rec['element'],
                'rev': rec['rev'], 'area': rec['area'], 'amp': rec['amp'],
                'delta': rec['delta'], 'utc': rec['utc'],
                'excluded': info['excluded'],
                'run_min': self.run_minutes(s.id, s.start, rec['utc']),
            }
            self.inj[(s.id, rec['counter'], rec['element'])] = item
        self.by_session = {}
        for k, v in self.inj.items():
            self.by_session.setdefault((v['session'], v['element']), []).append(v)
        for v in self.by_session.values():
            v.sort(key=lambda x: x['tray'])

    def elements_of(self, sess, element):
        return self.by_session.get((sess, element), [])

    def live(self, sess, element):
        return [i for i in self.elements_of(sess, element) if not i['excluded']]


# ------------------------------------------------------------- references ----

RM_COL = {'N': 'd15N_air', 'C': 'd13C_vpdb'}


class Refs(object):
    def __init__(self, env):
        self.env = env
        p = env.profile
        self.lots = {}
        for r in env.capsule_reg:
            self.lots[norm(r['capsule_id'])] = (norm(r['material']),
                                                norm(r['lot']))
        self.certified = {}
        for r in env.wb.table(p['rm_sheet'], 'material'):
            key = (norm(r['material']), norm(r['lot']))
            self.certified[key] = {e: F(r.get(RM_COL[e], '').strip())
                                   for e in env.elements}
        self.assigned = {}
        for r in env.wb.table(p['qc_sheet'], 'material'):
            if norm(r.get('status')) != 'CURRENT':
                continue
            self.assigned[norm(r['material'])] = {
                e: F(r.get(RM_COL[e], '').strip()) for e in env.elements}
        self.elemental = {}
        for r in env.wb.table(p['elemental_sheet'], 'material'):
            if norm(r.get('status')) != 'IN USE':
                continue
            self.elemental[norm(r['lot'])] = {
                e: F(r.get(e + '_pct', '').strip()) for e in env.elements}
        self.bal = []
        for r in env.balance:
            self.bal.append((norm(r['balance']), r['valid_from'].strip(),
                             r['valid_to'].strip(), F(r['factor'])))
        self.mass = {}
        for r in env.wb.table(p['weights_sheet'], 'capsule_id'):
            cap = norm(r['capsule_id'])
            if cap in self.mass:
                continue
            raw = F(r['mass_mg'].strip())
            bal = norm(r['balance'])
            day = env.wb.serial_to_date(r['weighed']).isoformat()
            factor = None
            for b, vf, vt, fa in self.bal:
                if b == bal and vf <= day < vt:
                    factor = fa
                    break
            self.mass[cap] = rnd(raw * factor, 4) if factor is not None else None

    def certified_value(self, capsule, element):
        lot = self.lots.get(capsule)
        if lot is None:
            return None
        row = self.certified.get(lot)
        return None if row is None else row.get(element)

    def pct_standard(self, capsule, element):
        lot = self.lots.get(capsule)
        if lot is None:
            return None
        row = self.elemental.get(lot[1])
        return None if row is None else row.get(element)


# ------------------------------------------------------------ corrections ----

class Corrections(object):
    def __init__(self, env, batch, refs):
        self.env = env
        self.b = batch
        self.refs = refs
        self.params()
        self.linearity()
        self.drift()
        self.blank()
        self.normalization()
        self.elemental()

    def params(self):
        env = self.env
        n2 = env.table_by_header('reference_set')
        self.n2 = n2
        self.ref_set = {}
        self.reject_limit = {}
        self.max_reject = {}
        self.slope_min = None
        self.slope_max = None
        for r in n2.dicts():
            el = norm(r['element'])
            self.ref_set[el] = [norm(x) for x in r['reference_set'].split(';')
                                if x.strip()]
            self.reject_limit[el] = F(r['reject_limit_permil'])
            self.max_reject[el] = int(F(r['max_rejections']))
            self.slope_min = F(r['slope_min'])
            self.slope_max = F(r['slope_max'])
        a1 = env.table_by_header('amplitude_min_mv')
        self.a1 = a1
        self.amp_min = {}
        self.amp_max = {}
        self.blank_max = {}
        for r in a1.dicts():
            el = norm(r['element'])
            self.amp_min[el] = F(r['amplitude_min_mv'])
            self.amp_max[el] = F(r['amplitude_max_mv'])
            self.blank_max[el] = F(r['blank_area_max_vs'])
        l1 = env.table_by_header('threshold_permil_per_vs')
        self.l1 = l1
        self.lin_threshold = {norm(r['element']): F(r['threshold_permil_per_vs'])
                              for r in l1.dicts()}
        q1 = env.table_by_header('tolerance_permil')
        self.q1 = q1
        self.qc_rows = q1.dicts()
        self.a_ref = {e: F(v) for e, v in env.profile['a_ref_vs'].items()}
        self.drift_material = norm(env.profile['drift_material'])
        self.drift_min = int(F(env.profile['drift_min_points']))
        self.lin_min = int(F(env.profile['linearity_min_points']))
        self.lookback = int(F(env.profile['linearity_lookback_days']))
        g1 = env.table_by_header('alpha_' + str(env.profile['grubbs_alpha']))
        self.g1 = g1
        self.grubbs = {}
        col = 'alpha_' + str(env.profile['grubbs_alpha'])
        for r in g1.dicts():
            self.grubbs[int(F(r['n']))] = F(r[col])

    # -- H8 ------------------------------------------------------------------
    def linearity(self):
        b = self.b
        self.lin_fits = {}
        for sid in b.linearity:
            for el in self.env.elements:
                pts = [(i['area'], i['delta']) for i in b.live(sid, el)
                       if i['material'] == 'ELM-ACT']
                pts.sort()
                slope = None
                if len(pts) >= self.lin_min:
                    s = ls_slope(pts)
                    slope = None if s is None else rnd(s, 6)
                self.lin_fits[(sid, el)] = {'n': len(pts), 'slope': slope}
        self.assign = {}
        for sid in b.analytical:
            s = b.sessions[sid]
            for el in self.env.elements:
                cands = []
                for lid in b.linearity:
                    ls = b.sessions[lid]
                    fit = self.lin_fits.get((lid, el))
                    if fit is None or fit['slope'] is None or ls.start is None:
                        continue
                    cands.append((ls, fit['slope']))
                same = [(ls, sl) for ls, sl in cands
                        if ls.date == s.date and ls.start < s.start]
                pick = None
                if same:
                    pick = max(same, key=lambda t: t[0].start)
                else:
                    lo = s.date - _dt.timedelta(days=self.lookback)
                    hi = s.date - _dt.timedelta(days=1)
                    prev = [(ls, sl) for ls, sl in cands
                            if lo <= ls.date <= hi]
                    if prev:
                        pick = max(prev, key=lambda t: t[0].start)
                if pick is None:
                    rec = {'lin_session': None, 'lin_slope': None,
                           'applied': Fraction(0), 'status': 'NONE'}
                else:
                    ls, sl = pick
                    if abs(sl) >= self.lin_threshold[el]:
                        rec = {'lin_session': ls.id, 'lin_slope': sl,
                               'applied': sl, 'status': 'APPLIED'}
                    else:
                        rec = {'lin_session': ls.id, 'lin_slope': sl,
                               'applied': Fraction(0),
                               'status': 'BELOW_THRESHOLD'}
                self.assign[(sid, el)] = rec
        for sid in b.analytical:
            for el in self.env.elements:
                k = self.assign[(sid, el)]['applied']
                aref = self.a_ref[el]
                for i in b.elements_of(sid, el):
                    i['d_lin'] = rnd(i['delta'] - k * (i['area'] - aref), 4)

    # -- H9 ------------------------------------------------------------------
    def drift(self):
        b = self.b
        self.drift_fits = {}
        for sid in b.analytical:
            for el in self.env.elements:
                pts = [(i['run_min'], i['d_lin']) for i in b.live(sid, el)
                       if i['material'] == self.drift_material]
                pts.sort(key=lambda p: p[0])
                n = len(pts)
                if n >= self.drift_min:
                    s = ls_slope(pts)
                    slope = Fraction(0) if s is None else rnd(s, 8)
                    status = 'FITTED'
                else:
                    slope = Fraction(0)
                    status = 'INSUFFICIENT'
                anchor = rnd(mean([p[0] for p in pts]), 4) if pts else Fraction(0)
                self.drift_fits[(sid, el)] = {'n': n, 'slope': slope,
                                              'anchor': anchor,
                                              'status': status}
                for i in b.elements_of(sid, el):
                    i['d_drift'] = rnd(i['d_lin'] - slope *
                                       (i['run_min'] - anchor), 4)

    # -- H10 -----------------------------------------------------------------
    def blank(self):
        b = self.b
        self.blanks = {}
        for sid in b.analytical:
            for el in self.env.elements:
                cand = [i for i in b.live(sid, el) if i['material'] == 'BLK']
                ok = [i for i in cand if i['area'] <= self.blank_max[el]]
                rej = len(cand) - len(ok)
                if ok:
                    ab = rnd(mean([i['area'] for i in ok]), 4)
                    db = rnd(mean([i['delta'] for i in ok]), 3)
                else:
                    ab = Fraction(0)
                    db = Fraction(0)
                self.blanks[(sid, el)] = {'n': len(ok), 'rejected': rej,
                                          'area': ab, 'delta': db}
                for i in b.elements_of(sid, el):
                    den = i['area'] - ab
                    if den == 0:
                        i['d_blank'] = i['d_drift']
                    else:
                        i['d_blank'] = rnd(
                            (i['d_drift'] * i['area'] - db * ab) / den, 4)

    # -- H11 -----------------------------------------------------------------
    def normalization(self):
        b = self.b
        self.norm_fits = {}
        for sid in b.analytical:
            for el in self.env.elements:
                rset = self.ref_set[el]
                pts = []
                for i in b.live(sid, el):
                    if i['class'] != 'RM' or i['material'] not in rset:
                        continue
                    if not (self.amp_min[el] <= i['amp'] <= self.amp_max[el]):
                        continue
                    y = self.refs.certified_value(i['capsule'], el)
                    if y is None:
                        continue
                    pts.append({'tray': i['tray'], 'material': i['material'],
                                'x': i['d_blank'], 'y': y})
                pts.sort(key=lambda p: p['tray'])
                info = {'session': sid, 'element': el, 'reference_set': rset,
                        'removed': [], 'fits': 0, 'slope': None,
                        'intercept': None, 'n_points': 0,
                        'status': 'NO_NORMALIZATION'}
                counts = {m: sum(1 for p in pts if p['material'] == m)
                          for m in rset}
                if any(counts[m] < 2 for m in rset):
                    self.norm_fits[(sid, el)] = info
                    continue
                live = list(pts)
                limit = self.reject_limit[el]
                maxrej = self.max_reject[el]
                status = None
                slope = inter = None
                while True:
                    s, c = ls_fit([(p['x'], p['y']) for p in live])
                    info['fits'] += 1
                    if s is None:
                        slope = inter = None
                        status = 'NO_NORMALIZATION'
                        break
                    slope = rnd(s, 6)
                    inter = rnd(c, 6)
                    res = [p['y'] - (slope * p['x'] + inter) for p in live]
                    worst = max(range(len(live)), key=lambda k: (abs(res[k]), -k))
                    if abs(res[worst]) <= limit:
                        status = 'CONVERGED'
                        break
                    mat = live[worst]['material']
                    if sum(1 for p in live if p['material'] == mat) - 1 < 2:
                        status = 'LIMIT_STOP'
                        break
                    if len(info['removed']) >= maxrej:
                        status = 'MAX_REJECT'
                        break
                    info['removed'].append({'tray_position': live[worst]['tray'],
                                            'material': mat,
                                            'residual': rnd(res[worst], 4)})
                    live.pop(worst)
                info['slope'] = slope
                info['intercept'] = inter
                info['n_points'] = len(live)
                info['status'] = status
                self.norm_fits[(sid, el)] = info
                if slope is not None:
                    for i in b.elements_of(sid, el):
                        if i['class'] in ('RM', 'QC', 'ELM', 'SAMPLE'):
                            i['d_norm'] = rnd(slope * i['d_blank'] + inter, 3)

    # -- H12 -----------------------------------------------------------------
    def elemental(self):
        b = self.b
        self.factors = {}
        for sid in b.analytical:
            for el in self.env.elements:
                ab = self.blanks[(sid, el)]['area']
                vals = []
                for i in b.live(sid, el):
                    if i['material'] != 'ELM-ACT':
                        continue
                    m = self.refs.mass.get(i['capsule'])
                    pct = self.refs.pct_standard(i['capsule'], el)
                    den = i['area'] - ab
                    if m is None or pct is None or den == 0:
                        continue
                    vals.append((m * 1000 * pct / 100) / den)
                factor = rnd(mean(vals), 6) if vals else None
                self.factors[(sid, el)] = {'n': len(vals), 'factor': factor}
                for i in b.elements_of(sid, el):
                    if i['class'] not in ('RM', 'QC', 'SAMPLE'):
                        continue
                    m = self.refs.mass.get(i['capsule'])
                    if factor is None or m is None or m == 0:
                        continue
                    i['pct'] = rnd((i['area'] - ab) * factor /
                                   (m * 1000) * 100, 3)


# ------------------------------------------------------------- acceptance ----

class Acceptance(object):
    def __init__(self, env, batch, refs, corr):
        self.env = env
        self.b = batch
        self.refs = refs
        self.c = corr
        self.qc_materials = {}
        for el in env.elements:
            mats = []
            for r in corr.qc_rows:
                if norm(r['element']) != el:
                    continue
                m = norm(r['material'])
                if m == corr.drift_material or m in mats:
                    continue
                mats.append(m)
            self.qc_materials[el] = mats
        self.tolerance = {}
        for r in corr.qc_rows:
            self.tolerance[(norm(r['material']), norm(r['element']))] = \
                F(r['tolerance_permil'])
        self.session_rulings()
        self.decide()

    def session_rulings(self):
        env = self.env
        self.rulings = {}
        for r in self.b.rulings:
            act = norm(r['action'])
            if act not in ('ACCEPT_SESSION', 'REJECT_SESSION'):
                continue
            if norm(r['project']) != env.project:
                continue
            sess = env.alias.session(r['target'], norm(r['project']))
            if sess is None:
                continue
            el = norm(r['element'])
            els = env.elements if el == 'ALL' else [el]
            for e in els:
                key = (sess, e)
                cur = self.rulings.get(key)
                if cur is None or (r['date'], r['ruling']) > (cur['date'],
                                                              cur['ruling']):
                    self.rulings[key] = r

    def decide(self):
        env = self.env
        self.rows = {}
        self.checks = []
        for sid in self.b.analytical:
            s = self.b.sessions[sid]
            for el in env.elements:
                fit = self.c.norm_fits[(sid, el)]
                reasons = []
                slope = fit['slope']
                slope_ok = False
                if fit['status'] == 'NO_NORMALIZATION' or slope is None:
                    reasons.append('NO_NORMALIZATION')
                else:
                    slope_ok = self.c.slope_min <= slope <= self.c.slope_max
                    if not slope_ok:
                        reasons.append('SLOPE')
                qc_parts = []
                for mat in self.qc_materials[el]:
                    vals = [i['d_norm'] for i in self.b.live(sid, el)
                            if i['material'] == mat and i.get('d_norm') is not None]
                    if not vals:
                        continue
                    m3 = rnd(mean(vals), 3)
                    assigned = self.refs.assigned.get(mat, {}).get(el)
                    tol = self.tolerance.get((mat, el))
                    dev = rnd(m3 - assigned, 3)
                    failed = abs(dev) > tol
                    qc_parts.append('%s:%s:%s' % (mat, fmt(dev, 3),
                                                  'FAIL' if failed else 'PASS'))
                    self.checks.append({'session': sid, 'element': el,
                                        'material': mat, 'n': len(vals),
                                        'mean': m3, 'assigned': assigned,
                                        'deviation': dev, 'tolerance': tol,
                                        'result': 'FAIL' if failed else 'PASS'})
                    if failed:
                        reasons.append('QC:' + mat)
                if s.leak_fail:
                    reasons.append('LEAK')
                computed = 'ACCEPT' if not reasons else 'REJECT'
                ruling = self.rulings.get((sid, el))
                decision = computed
                rid = ''
                if ruling is not None:
                    rid = ruling['ruling'].strip()
                    decision = 'ACCEPT' if norm(ruling['action']) == \
                        'ACCEPT_SESSION' else 'REJECT'
                self.rows[(sid, el)] = {
                    'session': sid, 'element': el, 'instrument': s.instrument,
                    'norm_slope': slope, 'slope_ok': 'Y' if slope_ok else 'N',
                    'qc_checks': ';'.join(qc_parts),
                    'leak': 'Y' if s.leak_fail else 'N', 'computed': computed,
                    'ruling': rid, 'decision': decision,
                    'reasons': ';'.join(reasons)}

    def accepted(self, sid, el):
        row = self.rows.get((sid, el))
        return row is not None and row['decision'] == 'ACCEPT'


# ---------------------------------------------------------------- samples ----

class Samples(object):
    def __init__(self, env, batch, refs, corr, acc):
        self.env = env
        self.b = batch
        self.c = corr
        self.acc = acc
        self.scope = [norm(x) for x in env.profile['samples_in_scope']]
        self.requests()
        self.compute()

    def requests(self):
        env = self.env
        best = {}
        for r in env.requests:
            if norm(r.get('status')) != 'ACTIVE':
                continue
            ref = norm(r['sample_ref'])
            sample = ref if ref in env.alias.sample_ids else \
                env.client_map.get(ref)
            if sample is None:
                sample = env.alias.material(ref, env.project, None)
            if sample is None:
                continue
            key = (r['requested_on'].strip(), r['request_id'].strip())
            if sample not in best or key > best[sample][0]:
                best[sample] = (key, r)
        self.request = {}
        for sample, (_, r) in best.items():
            els = set()
            for part in re.split(r'[^A-Za-z0-9]+', r['elements']):
                p = norm(part)
                if p:
                    els.add(p)
            self.request[sample] = els

    def requested(self, sample, el):
        return el in self.request.get(sample, set())

    def compute(self):
        env = self.env
        b = self.b
        self.values = {}
        self.screen = {}
        self.result = {}
        for sample in self.scope:
            for el in env.elements:
                if not self.requested(sample, el):
                    self.result[(sample, el)] = {'status': 'NOT_REQUESTED'}
                    continue
                items = []
                for sid in b.analytical:
                    if not self.acc.accepted(sid, el):
                        continue
                    start = b.sessions[sid].start
                    for i in b.live(sid, el):
                        if i['material'] == sample and i.get('d_norm') is not None:
                            items.append((start, i['tray'], i))
                items.sort(key=lambda t: (t[0], t[1]))
                vals = [t[2] for t in items]
                initial = len(vals)
                removed = []
                kept = list(vals)
                while len(kept) >= 3:
                    xs = [k['d_norm'] for k in kept]
                    n = len(xs)
                    mu = mean(xs)
                    var = sum(((x - mu) ** 2 for x in xs), Fraction(0)) / (n - 1)
                    if var == 0:
                        break
                    idx = max(range(n), key=lambda k: (abs(xs[k] - mu), -k))
                    dist = abs(xs[idx] - mu)
                    crit = self.c.grubbs.get(n)
                    if crit is None:
                        break
                    if dist * dist > crit * crit * var:
                        g = dec_round(sqrt_frac(dist * dist / var), 4)
                        removed.append({'value': jnum(xs[idx], 3),
                                        'g': json.loads(str(g)),
                                        'g_crit': jnum(crit, 4), 'n': n})
                        kept.pop(idx)
                    else:
                        break
                if initial:
                    self.screen[(sample, el)] = {
                        'sample': sample, 'element': el,
                        'initial_n': initial,
                        'values': [jnum(v['d_norm'], 3) for v in vals],
                        'removed': removed, 'final_n': len(kept)}
                n = len(kept)
                if n == 0:
                    self.result[(sample, el)] = {'status': 'NO_DATA', 'n': 0}
                    continue
                xs = [k['d_norm'] for k in kept]
                mu = mean(xs)
                sd = None
                if n >= 2:
                    var = sum(((x - mu) ** 2 for x in xs), Fraction(0)) / (n - 1)
                    sd = dec_round(sqrt_frac(var), 2)
                pcts = [k['pct'] for k in kept if k.get('pct') is not None]
                self.result[(sample, el)] = {
                    'status': 'REPORTED' if n >= 2 else 'SINGLE',
                    'n': n, 'mean': rnd(mu, 2), 'sd': sd,
                    'pct': rnd(mean(pcts), 2) if pcts else None}
        self.cn = {}
        mc = F(env.masses.get('C'))
        mn = F(env.masses.get('N'))
        for sample in self.scope:
            rn = self.result.get((sample, 'N'), {})
            rc = self.result.get((sample, 'C'), {})
            if rn.get('status') not in ('REPORTED', 'SINGLE'):
                continue
            if rc.get('status') not in ('REPORTED', 'SINGLE'):
                continue
            pn, pc = rn.get('pct'), rc.get('pct')
            if pn is None or pc is None or pn == 0:
                continue
            self.cn[sample] = rnd((pc / mc) / (pn / mn), 2)


# ---------------------------------------------------------------- writers ----

REPORTS = [
    'injection_ledger.csv', 'position_resolution.csv', 'alias_resolution.psv',
    'dedup_report.json', 'source_lineage.json', 'linearity_slopes.json',
    'drift_fits.tsv', 'blank_corrections.psv', 'normalization_fits.json',
    'corrected_injections.jsonl', 'elemental_factors.tsv',
    'session_acceptance.csv', 'qc_results.xml', 'isotope_results.csv',
    'replicate_screening.jsonl', 'parameters_used.yaml',
    'variance_vs_published.csv', 'session_param_diff.json',
    'dashboard_disagreements.csv', 'cache_divergence.jsonl',
    'reconciliation.md',
]


def xesc(v):
    return (str(v).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


class Writer(object):
    def __init__(self, out_dir):
        self.dir = out_dir
        self.written = {}

    def put(self, name, text):
        path = os.path.join(self.dir, name)
        data = text.encode('utf-8')
        with open(path, 'wb') as fh:
            fh.write(data)
        self.written[name] = data

    def table(self, name, header, rows, sep):
        lines = [sep.join(header)]
        for r in rows:
            lines.append(sep.join('' if c is None else str(c) for c in r))
        self.put(name, '\n'.join(lines) + '\n')

    def jsonl(self, name, objs):
        self.put(name, ''.join(json.dumps(o) + '\n' for o in objs))

    def jsondoc(self, name, obj):
        self.put(name, json.dumps(obj, indent=1) + '\n')


class Reporter(object):
    def __init__(self, env, ing, batch, refs, corr, acc, samples, out_dir):
        self.env = env
        self.ing = ing
        self.b = batch
        self.refs = refs
        self.c = corr
        self.acc = acc
        self.s = samples
        self.w = Writer(out_dir)
        self.els = env.elements
        self.sd_col = {e: RM_COL[e].split('_')[0] + '_sd' for e in self.els}

    def eorder(self, el):
        return self.els.index(el)

    # ---------------------------------------------------------------- core --
    def injection_ledger(self):
        rows = []
        for sid in self.b.order:
            for el in self.els:
                for i in self.b.elements_of(sid, el):
                    rows.append((sid, i['counter'], self.eorder(el), i))
        rows.sort(key=lambda t: (t[0], t[1], t[2]))
        out = []
        for sid, ctr, _, i in rows:
            out.append([sid, i['instrument'], ctr, i['tray'], i['material'],
                        i['element'], i['rev'], fmt(i['area'], 4), i['amp'],
                        fmt(i['delta'], 3),
                        from_epoch(i['utc']).strftime('%Y-%m-%dT%H:%M:%SZ'),
                        fmt(rnd(i['run_min'], 4), 4), i['excluded']])
        self.w.table('injection_ledger.csv',
                     ['session', 'instrument', 'counter_position',
                      'tray_position', 'material', 'element', 'revision',
                      'area_vs', 'amplitude_mv', 'delta_raw', 'utc_time',
                      'run_minutes', 'excluded'], out, ',')

    def position_resolution(self):
        out = []
        for sid in self.b.order:
            s = self.b.sessions[sid]
            for tray in sorted(s.trays):
                t = s.trays[tray]
                if t['counter'] is None:
                    status = 'SKIPPED'
                elif t['excluded']:
                    status = 'EXCLUDED'
                else:
                    status = 'MEASURED'
                mass = self.refs.mass.get(t['capsule']) if t['capsule'] else None
                out.append([sid, tray, '' if t['counter'] is None else t['counter'],
                            t['sequence_token'], t['journal_seq'], t['material'],
                            t['class'], t['capsule'],
                            '' if mass is None else fmt(mass, 4), status])
        self.w.table('position_resolution.csv',
                     ['session', 'tray_position', 'counter_position',
                      'sequence_token', 'journal_seq', 'material',
                      'material_class', 'capsule_id', 'mass_mg', 'status'],
                     out, ',')

    def alias_resolution(self):
        seen = set()
        for kind, token, canon in list(self.ing.alias_seen) + \
                list(self.b.alias_extra):
            if canon is None or token is None:
                continue
            tok = norm(token)
            if tok == '' or tok == norm(canon):
                continue
            seen.add((kind, tok, canon))
        rows = sorted(seen, key=lambda r: (r[0], r[1], r[2]))
        self.w.table('alias_resolution.psv', ['kind', 'token', 'canonical'],
                     [list(r) for r in rows], '|')

    def dedup_report(self):
        keys = ['files_read', 'records_read', 'other_project',
                'reference_peaks', 'inactive_segment', 'duplicates',
                'revisions_not_admitted', 'revisions_superseded', 'voided',
                'kept']
        self.w.jsondoc('dedup_report.json',
                       {k: self.ing.counts[k] for k in keys})

    def source_lineage(self):
        files = []
        for st in self.ing.lineage:
            files.append({'file': st['file'], 'layout': st['layout'],
                          'records': st['records'],
                          'other_project': st['other_project'],
                          'reference_peaks': st['reference_peaks'],
                          'inactive_segment': st['inactive_segment'],
                          'duplicates': st['duplicates'],
                          'unique': st['unique']})
        self.w.jsondoc('source_lineage.json', {'files': files})

    def linearity_slopes(self):
        lin = []
        for sid in self.b.linearity:
            s = self.b.sessions[sid]
            for el in self.els:
                f = self.c.lin_fits[(sid, el)]
                lin.append({'session': sid, 'instrument': s.instrument,
                            'local_date': s.date_str, 'element': el,
                            'n_points': f['n'],
                            'slope': jnum(f['slope'], 6)})
        asg = []
        for sid in self.b.analytical:
            for el in self.els:
                a = self.c.assign[(sid, el)]
                asg.append({'session': sid, 'element': el,
                            'lin_session': a['lin_session'],
                            'lin_slope': jnum(a['lin_slope'], 6),
                            'applied_slope': jnum(a['applied'], 6),
                            'status': a['status']})
        self.w.jsondoc('linearity_slopes.json',
                       {'lin_sessions': lin, 'assignments': asg})

    def drift_fits(self):
        out = []
        for sid in self.b.analytical:
            for el in self.els:
                f = self.c.drift_fits[(sid, el)]
                out.append([sid, el, self.c.drift_material, f['n'],
                            fmt(f['slope'], 8), fmt(f['anchor'], 4),
                            f['status']])
        self.w.table('drift_fits.tsv',
                     ['session', 'element', 'drift_material', 'n_points',
                      'slope_per_min', 'anchor_min', 'status'], out, '\t')

    def blank_corrections(self):
        out = []
        for sid in self.b.analytical:
            for el in self.els:
                f = self.c.blanks[(sid, el)]
                out.append([sid, el, f['n'], f['rejected'],
                            fmt(f['area'], 4), fmt(f['delta'], 3)])
        self.w.table('blank_corrections.psv',
                     ['session', 'element', 'n_blanks', 'n_rejected',
                      'mean_area_vs', 'mean_delta'], out, '|')

    def normalization_fits(self):
        fits = []
        for sid in self.b.analytical:
            for el in self.els:
                f = self.c.norm_fits[(sid, el)]
                fits.append({
                    'session': sid, 'element': el,
                    'reference_set': list(f['reference_set']),
                    'n_points': f['n_points'], 'fits': f['fits'],
                    'slope': jnum(f['slope'], 6),
                    'intercept': jnum(f['intercept'], 6),
                    'removed': [{'tray_position': r['tray_position'],
                                 'material': r['material'],
                                 'residual': jnum(r['residual'], 4)}
                                for r in f['removed']],
                    'status': f['status']})
        self.w.jsondoc('normalization_fits.json', {'fits': fits})

    def corrected_injections(self):
        rows = []
        for sid in self.b.analytical:
            for el in self.els:
                for i in self.b.live(sid, el):
                    if i['class'] not in ('RM', 'QC', 'ELM', 'SAMPLE'):
                        continue
                    rows.append((sid, i['tray'], self.eorder(el), i))
        rows.sort(key=lambda t: (t[0], t[1], t[2]))
        objs = []
        for sid, tray, _, i in rows:
            objs.append({'session': sid, 'tray_position': tray,
                         'material': i['material'],
                         'material_class': i['class'], 'element': i['element'],
                         'd_lin': jnum(i['d_lin'], 4),
                         'd_drift': jnum(i['d_drift'], 4),
                         'd_blank': jnum(i['d_blank'], 4),
                         'd_norm': jnum(i.get('d_norm'), 3),
                         'pct': None if i['class'] == 'ELM'
                         else jnum(i.get('pct'), 3)})
        self.w.jsonl('corrected_injections.jsonl', objs)

    def elemental_factors(self):
        out = []
        for sid in self.b.analytical:
            for el in self.els:
                f = self.c.factors[(sid, el)]
                out.append([sid, el, f['n'],
                            '' if f['factor'] is None else fmt(f['factor'], 6)])
        self.w.table('elemental_factors.tsv',
                     ['session', 'element', 'n_standards',
                      'factor_ug_per_vs'], out, '\t')

    def session_acceptance(self):
        out = []
        for sid in self.b.analytical:
            for el in self.els:
                r = self.acc.rows[(sid, el)]
                out.append([sid, el, r['instrument'],
                            '' if r['norm_slope'] is None
                            else fmt(r['norm_slope'], 6), r['slope_ok'],
                            r['qc_checks'], r['leak'], r['computed'],
                            r['ruling'], r['decision'], r['reasons']])
        self.w.table('session_acceptance.csv',
                     ['session', 'element', 'instrument', 'norm_slope',
                      'slope_ok', 'qc_checks', 'leak', 'computed', 'ruling',
                      'decision', 'reasons'], out, ',')

    def qc_results(self):
        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<qc_results project="%s">' % xesc(self.env.project)]
        rows = sorted(self.acc.checks,
                      key=lambda c: (c['session'], self.eorder(c['element']),
                                     self.acc.qc_materials[c['element']]
                                     .index(c['material'])))
        for c in rows:
            lines.append(
                '  <check session="%s" element="%s" material="%s" n="%d" '
                'mean="%s" assigned="%s" deviation="%s" tolerance="%s" '
                'result="%s"/>' % (
                    xesc(c['session']), xesc(c['element']),
                    xesc(c['material']), c['n'], fmt(c['mean'], 3),
                    fmt(c['assigned'], 2), fmt(c['deviation'], 3),
                    fmt(c['tolerance'], 2), c['result']))
        lines.append('</qc_results>')
        self.w.put('qc_results.xml', '\n'.join(lines) + '\n')

    def isotope_results(self):
        header = ['sample_id']
        for e in self.els:
            header += [RM_COL[e], self.sd_col[e], 'n_' + e, 'pct_' + e,
                       'status_' + e]
        header.append('cn_molar')
        out = []
        for sample in sorted(self.s.scope):
            row = [sample]
            for e in self.els:
                r = self.s.result.get((sample, e), {'status': 'NOT_REQUESTED'})
                st = r['status']
                if st == 'NOT_REQUESTED':
                    row += ['', '', '', '', st]
                elif st == 'NO_DATA':
                    row += ['', '', 0, '', st]
                else:
                    row += [fmt(r['mean'], 2),
                            '' if r['sd'] is None else str(r['sd']),
                            r['n'],
                            '' if r['pct'] is None else fmt(r['pct'], 2), st]
            cn = self.s.cn.get(sample)
            row.append('' if cn is None else fmt(cn, 2))
            out.append(row)
        self.w.table('isotope_results.csv', header, out, ',')

    def replicate_screening(self):
        keys = sorted(self.s.screen,
                      key=lambda k: (k[0], self.eorder(k[1])))
        self.w.jsonl('replicate_screening.jsonl',
                     [self.s.screen[k] for k in keys])

    # ------------------------------------------------------------ settings --
    def parameters_used(self):
        env = self.env
        c = self.c
        n2 = {norm(r['element']): r for r in c.n2.dicts()}
        a1 = {norm(r['element']): r for r in c.a1.dicts()}
        l1 = {norm(r['element']): r for r in c.l1.dicts()}
        lines = []
        add = lambda k, v: lines.append('%s: %s' % (k, v))
        add('project', env.project)
        add('rm_sheet', env.profile['rm_sheet'])
        add('normalization_table', c.n2.id)
        for e in self.els:
            add('reference_set_' + e, ','.join(c.ref_set[e]))
        for e in self.els:
            add('reject_limit_' + e, n2[e]['reject_limit_permil'])
        for e in self.els:
            add('max_reject_' + e, n2[e]['max_rejections'])
        for e in self.els:
            add('linearity_threshold_' + e, l1[e]['threshold_permil_per_vs'])
        for e in self.els:
            add('a_ref_' + e, env.profile['a_ref_vs'][e])
        for e in self.els:
            add('amplitude_min_' + e, a1[e]['amplitude_min_mv'])
        for e in self.els:
            add('amplitude_max_' + e, a1[e]['amplitude_max_mv'])
        for e in self.els:
            add('blank_area_max_' + e, a1[e]['blank_area_max_vs'])
        first = n2[self.els[0]]
        add('slope_min', first['slope_min'])
        add('slope_max', first['slope_max'])
        add('linearity_lookback_days', env.profile['linearity_lookback_days'])
        add('drift_material', env.profile['drift_material'])
        add('drift_min_points', env.profile['drift_min_points'])
        add('grubbs_table', c.g1.id)
        add('grubbs_alpha', env.profile['grubbs_alpha'])
        add('molar_mass_C', env.masses.get('C'))
        add('molar_mass_N', env.masses.get('N'))
        add('date_system', '1904' if env.wb.date1904 else '1900')
        add('clock_base_offset',
            yaml_load(open(os.path.join(env.dir, 'site_clock.yaml'), 'r',
                           encoding='utf-8').read())['base_offset'])
        tol = {(norm(r['material']), norm(r['element'])): r['tolerance_permil']
               for r in c.qc_rows}
        done = []
        for r in c.qc_rows:
            m = norm(r['material'])
            if m == c.drift_material or m in done:
                continue
            done.append(m)
        for m in done:
            for e in self.els:
                if (m, e) in tol:
                    add('qc_tolerance_%s_%s' % (m, e), tol[(m, e)])
        self.w.put('parameters_used.yaml', '\n'.join(lines) + '\n')

    # --------------------------------------------------------- comparisons --
    def published_map(self):
        out = {}
        for r in self.env.published:
            sid = norm(r['sample_id'])
            sample = self.env.alias.material(sid, self.env.project, None) or sid
            for e in self.els:
                v = (r.get(RM_COL[e]) or '').strip()
                if v != '':
                    out[(sample, e)] = F(v)
        return out

    def recomputed_value(self, sample, el):
        r = self.s.result.get((sample, el))
        if r is None or r.get('status') not in ('REPORTED', 'SINGLE'):
            return None
        return r['mean']

    def variance_vs_published(self):
        pub = self.published_map()
        keys = set(pub)
        for (sample, el), r in self.s.result.items():
            if r.get('status') in ('REPORTED', 'SINGLE'):
                keys.add((sample, el))
        out = []
        for sample, el in sorted(keys, key=lambda k: (k[0], self.eorder(k[1]))):
            p = pub.get((sample, el))
            rec = self.recomputed_value(sample, el)
            if p is not None and rec is not None:
                diff = rnd(rec - p, 2)
                status = 'MATCH' if abs(diff) <= Fraction(5, 100) else 'DIFF'
                out.append([sample, el, fmt(p, 2), fmt(rec, 2), fmt(diff, 2),
                            status])
            elif p is not None:
                out.append([sample, el, fmt(p, 2), '', '', 'ONLY_PUBLISHED'])
            else:
                out.append([sample, el, '', fmt(rec, 2), '', 'ONLY_RECOMPUTED'])
        self.w.table('variance_vs_published.csv',
                     ['sample_id', 'element', 'published', 'recomputed',
                      'diff', 'status'], out, ',')

    def session_param_diff(self):
        env = self.env
        rows = []
        for p in self.env.pub_params.get('sessions', []):
            sid = env.alias.session(p['session'], env.project) or \
                norm(p['session'])
            el = norm(p['element'])
            fit = self.c.norm_fits.get((sid, el))
            ps = F(str(p['slope']))
            pi = F(str(p['intercept']))
            rs = fit['slope'] if fit else None
            ri = fit['intercept'] if fit else None
            rows.append((sid, self.eorder(el) if el in self.els else 99, {
                'session': sid, 'element': el,
                'published_slope': jnum(ps, 6),
                'recomputed_slope': jnum(rs, 6),
                'published_intercept': jnum(pi, 6),
                'recomputed_intercept': jnum(ri, 6),
                'slope_diff': None if rs is None else jnum(rs - ps, 6),
                'intercept_diff': None if ri is None else jnum(ri - pi, 6),
                'published_points': p.get('rm_points'),
                'recomputed_points': fit['n_points'] if fit else None}))
        rows.sort(key=lambda t: (t[0], t[1]))
        self.w.jsondoc('session_param_diff.json',
                       {'sessions': [r[2] for r in rows]})

    def dashboard_disagreements(self):
        env = self.env
        agg = {}
        for r in env.dashboard:
            sid = env.alias.session(r['session'], env.project)
            if sid is None:
                continue
            el = norm(r['element'])
            key = (sid, el)
            fail = norm(r.get('status')) == 'FAIL'
            agg[key] = agg.get(key, False) or fail
        out = []
        for (sid, el) in sorted(agg, key=lambda k: (k[0], self.eorder(k[1])
                                                    if k[1] in self.els else 99)):
            dash = 'FAIL' if agg[(sid, el)] else 'PASS'
            row = self.acc.rows.get((sid, el))
            dec = row['decision'] if row else ''
            agrees = 'Y' if ((dash == 'PASS' and dec == 'ACCEPT') or
                             (dash == 'FAIL' and dec == 'REJECT')) else 'N'
            out.append([sid, el, dash, dec, agrees])
        self.w.table('dashboard_disagreements.csv',
                     ['session', 'element', 'dashboard_status',
                      'recomputed_decision', 'agrees'], out, ',')

    def cache_divergence(self):
        env = self.env
        objs = []
        for entry in env.cache:
            tok = norm(entry['sample'])
            sample = env.alias.material(tok, env.project, None) or tok
            el = norm(entry['element'])
            cached = F(str(entry['value']))
            rec = self.recomputed_value(sample, el)
            status = 'CURRENT' if (rec is not None and
                                   abs(rnd(rec - cached, 2)) <=
                                   Fraction(5, 100)) else 'STALE'
            objs.append((sample, self.eorder(el) if el in self.els else 99,
                         {'sample': sample, 'element': el,
                          'cached': jnum(cached, 2),
                          'recomputed': jnum(rec, 2), 'status': status}))
        objs.sort(key=lambda t: (t[0], t[1]))
        self.w.jsonl('cache_divergence.jsonl', [o[2] for o in objs])

    # ------------------------------------------------------ reconciliation --
    def rerun_settings(self):
        lines = self.env.rerun.split('\n')
        out = []
        inside = False
        for line in lines:
            if line.strip().lower().startswith('## run settings'):
                inside = True
                continue
            if inside and line.strip().startswith('##'):
                break
            if not inside:
                continue
            s = line.strip()
            if not s.startswith('|'):
                continue
            cells = [c.strip() for c in s.strip('|').split('|')]
            if len(cells) < 2 or cells[0] == 'setting' or \
                    set(cells[0]) <= set('-: '):
                continue
            out.append((cells[0], cells[1]))
        return out

    def in_force_setting(self, name):
        env = self.env
        c = self.c
        n = name.strip()
        if n == 'rm_sheet':
            return env.profile['rm_sheet']
        if n == 'normalization_table':
            return c.n2.id
        if n.startswith('reference_set_'):
            el = n[len('reference_set_'):]
            return ','.join(c.ref_set.get(norm(el), []))
        if n == 'grubbs_table':
            return c.g1.id
        return {'drift_axis': 'run_minutes',
                'linearity_partition': 'instrument_local_day',
                'correction_order': 'linearity,drift,blank,normalization',
                'revision_rule': 'audit_admitted',
                'autosampler_skips': 'applied',
                'session_rulings': 'R-1_in_force',
                'arithmetic': 'exact_decimal_stage_rounding'}.get(n, '')

    def notices(self):
        env = self.env
        pre = {RM_COL[e].split('_')[0]: e for e in self.els}
        pat = re.compile(r'^(\S+)\s*\|\s*(\S+)\s*\|\s*REFERENCE\s*\|\s*'
                         r'(\S+)\s+lot\s+(\S+)\s+(\S+)\s+(-?[0-9.]+)\s+permil')
        out = []
        for line in env.noticeboard.split('\n'):
            m = pat.match(line.strip())
            if not m:
                continue
            material = norm(m.group(3))
            lot = norm(m.group(4))
            el = pre.get(m.group(5))
            if el is None:
                continue
            value = F(m.group(6))
            row = self.refs.certified.get((material, lot))
            cur = row.get(el) if row else None
            if cur is not None and cur == value:
                continue
            out.append([m.group(1), material, lot, el, fmt(value, 2),
                        '' if cur is None else fmt(cur, 2)])
        out.sort(key=lambda r: r[0])
        return out

    def md_table(self, header, rows):
        lines = ['| ' + ' | '.join(header) + ' |',
                 '|' + '|'.join(['---'] * len(header)) + '|']
        for r in rows:
            lines.append('| ' + ' | '.join('' if c is None else str(c)
                                           for c in r) + ' |')
        return lines

    def reconciliation(self):
        pub = self.published_map()
        lines = ['# Reconciliation of batch %s' % self.env.project, '',
                 '## Summary', '']
        rows = []
        for el in self.els:
            recn = sum(1 for (s, e), r in self.s.result.items()
                       if e == el and r.get('status') in ('REPORTED', 'SINGLE'))
            pubn = sum(1 for (s, e) in pub if e == el)
            diffs = []
            for (s, e), p in pub.items():
                if e != el:
                    continue
                rec = self.recomputed_value(s, e)
                if rec is not None:
                    diffs.append(rnd(rec - p, 2))
            dc = sum(1 for d in diffs if abs(d) > Fraction(5, 100))
            shift = fmt(rnd(mean(diffs), 3), 3) if diffs else ''
            rows.append([el, recn, pubn, len(diffs), dc, shift])
        lines += self.md_table(['element', 'recomputed_reported',
                                'published_reported', 'compared',
                                'diff_count', 'mean_shift'], rows)
        lines += ['', '## Session decisions', '']
        rows = []
        for sid in self.b.analytical:
            for el in self.els:
                r = self.acc.rows[(sid, el)]
                if r['computed'] == 'REJECT' or r['decision'] == 'REJECT' or \
                        r['ruling']:
                    rows.append([sid, el, r['computed'], r['ruling'],
                                 r['decision'], r['reasons']])
        lines += self.md_table(['session', 'element', 'computed', 'ruling',
                                'decision', 'reasons'], rows)
        lines += ['', '## Run settings', '']
        rows = [[name, value, self.in_force_setting(name)]
                for name, value in self.rerun_settings()]
        lines += self.md_table(['setting', 'published_run', 'in_force'], rows)
        lines += ['', '## Superseded notices', '']
        lines += self.md_table(['notice', 'material', 'lot', 'element',
                                'notice_value', 'in_force_value'],
                               self.notices())
        self.w.put('reconciliation.md', '\n'.join(lines) + '\n')

    # --------------------------------------------------------------- drive --
    def run(self):
        self.injection_ledger()
        self.position_resolution()
        self.alias_resolution()
        self.dedup_report()
        self.source_lineage()
        self.linearity_slopes()
        self.drift_fits()
        self.blank_corrections()
        self.normalization_fits()
        self.corrected_injections()
        self.elemental_factors()
        self.session_acceptance()
        self.qc_results()
        self.isotope_results()
        self.replicate_screening()
        self.parameters_used()
        self.variance_vs_published()
        self.session_param_diff()
        self.dashboard_disagreements()
        self.cache_divergence()
        self.reconciliation()
        files = []
        for name in REPORTS:
            data = self.w.written[name]
            files.append({'name': name, 'bytes': len(data),
                          'sha256': hashlib.sha256(data).hexdigest()})
        self.w.jsondoc('manifest.json', {'files': files})


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: run_irms.py DATA_DIR OUT_DIR\n')
        return 2
    data_dir, out_dir = argv[1], argv[2]
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    env = Env(data_dir)
    ing = Ingest(env)
    batch = Batch(env, ing)
    refs = Refs(env)
    corr = Corrections(env, batch, refs)
    acc = Acceptance(env, batch, refs, corr)
    samples = Samples(env, batch, refs, corr, acc)
    Reporter(env, ing, batch, refs, corr, acc, samples, out_dir).run()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
