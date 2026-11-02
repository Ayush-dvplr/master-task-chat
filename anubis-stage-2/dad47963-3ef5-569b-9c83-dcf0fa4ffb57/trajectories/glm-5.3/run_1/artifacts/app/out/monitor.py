#!/usr/bin/env python3
"""PD-RETAIL v4 retail scorecard monitoring engine.

Usage:  python3 monitor.py ESTATE_DIR OUT_DIR
"""
import sys, os, re, io, json, csv, sqlite3, datetime, logging, warnings
from decimal import Decimal, getcontext, ROUND_HALF_EVEN, ROUND_HALF_UP
from collections import defaultdict, Counter

getcontext().prec = 60
logging.getLogger('pdfminer').setLevel(logging.ERROR)
warnings.filterwarnings('ignore')

import tomli
import yaml
from lxml import etree
from openpyxl import load_workbook
from pypdf import PdfReader
from docx import Document as _Docx
from docx.table import Table as _Table
from docx.text.paragraph import Paragraph as _Para
from docx.oxml.ns import qn as _qn

SEGMENTS = ['CARD', 'PLOAN', 'AUTO', 'MORT', 'OVDR', 'BNPL']
COHORT_FIRST = datetime.date(2025, 1, 1)
COHORT_LAST = datetime.date(2025, 7, 1)

# ------------------------------------------------------------------ utilities

def read_bytes(p):
    with open(p, 'rb') as f:
        return f.read()

def decode_bytes(b, enc='utf-8'):
    if enc == 'iso-8859-1':
        return b.decode('iso-8859-1')
    if b[:3] == b'\xef\xbb\xbf':
        b = b[3:]
    try:
        return b.decode('utf-8')
    except UnicodeDecodeError:
        return b.decode('utf-8', 'replace')

def read_text(path, enc='utf-8'):
    return decode_bytes(read_bytes(path), enc)

_WS = re.compile(r'[\s\u00a0\u200b\ufeff]+')

def norm_key(s, prefix):
    if s is None:
        return None
    s = _WS.sub('', str(s))
    s = s.upper().replace('\u0410', 'A').replace('\u0421', 'C').replace('-', '')
    d = re.sub(r'\D', '', s)
    if not d:
        return None
    return '%s%07d' % (prefix, int(d))

def norm_acct(s):
    return norm_key(s, 'AC')

def norm_cust(s):
    return norm_key(s, 'CU')

def norm_id(s):
    if s is None:
        return ''
    return _WS.sub('', str(s)).upper()

def norm_tok(s):
    if s is None:
        return ''
    return str(s).strip().upper()

def digits_int(s):
    if s is None:
        return 0
    if not isinstance(s, str):
        s = str(s)
    d = re.sub(r'\D', '', s)
    return int(d) if d else 0

_DATE_FMTS = ['%Y-%m-%d', '%d.%m.%Y', '%m/%d/%Y', '%Y%m%d', '%d/%m/%Y', '%m-%d-%Y']

def parse_date(s):
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
        return datetime.date(int(s[:4]), int(s[5:7]), int(s[8:10]))
    for f in _DATE_FMTS:
        try:
            return datetime.datetime.strptime(s, f).date()
        except ValueError:
            continue
    return None

def parse_month(s):
    if s is None:
        return None
    s = str(s).strip()
    m = re.fullmatch(r'(\d{4})[-/](\d{1,2})', s)
    if m:
        return '%04d-%02d' % (int(m.group(1)), int(m.group(2)))
    m = re.fullmatch(r'(\d{1,2})[-/](\d{4})', s)
    if m:
        return '%04d-%02d' % (int(m.group(2)), int(m.group(1)))
    return None

def parse_amount(s):
    """Money/number value; thousands separators are commas inside quoted values (4.6)."""
    if s is None:
        return None
    if isinstance(s, Decimal):
        return s
    if isinstance(s, int):
        return Decimal(s)
    if isinstance(s, float):
        return Decimal(repr(s))
    s = str(s).strip()
    if s == '':
        return None
    neg = False
    if s.startswith('(') and s.endswith(')'):
        neg = True
        s = s[1:-1].strip()
    s = _WS.sub('', s)
    if s[:1] in '+-':
        if s[0] == '-':
            neg = True
        s = s[1:]
    if ',' in s and '.' in s:
        s = s.replace(',', '')
    elif ',' in s:
        head, sep, tail = s.rpartition(',')
        if re.fullmatch(r'\d{1,3}(,\d{3})+', s):
            s = s.replace(',', '')
        else:
            s = head.replace(',', '') + '.' + tail
    if not re.fullmatch(r'[\d.]*', s) or s == '':
        return None
    d = Decimal(s) if s else Decimal(0)
    return -d if neg else d

def round_cents(d):
    return d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def round6(d):
    return d.quantize(Decimal('0.000001'), rounding=ROUND_HALF_EVEN)

def f6(d):
    return format(round6(d), 'f')

def f2(d):
    return format(d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), 'f')

def exceldate(serial):
    return datetime.date(1899, 12, 30) + datetime.timedelta(days=int(serial))

def excel_to_dt(v):
    if isinstance(v, datetime.datetime):
        return v
    if isinstance(v, datetime.date):
        return datetime.datetime(v.year, v.month, v.day)
    d = Decimal(str(v))
    days = int(d)
    frac = d - days
    secs = int((frac * 86400).to_integral_value(rounding=ROUND_HALF_UP))
    base = datetime.datetime(1899, 12, 30) + datetime.timedelta(days=days)
    return base + datetime.timedelta(seconds=secs)

def last_sunday(year, month):
    if month == 12:
        d = datetime.date(year, 12, 31)
    else:
        d = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
    return d - datetime.timedelta(days=(d.weekday() + 1) % 7)

_DST = {}

def dst_bounds(year):
    if year not in _DST:
        _DST[year] = (datetime.datetime.combine(last_sunday(year, 3), datetime.time(1, 0)),
                      datetime.datetime.combine(last_sunday(year, 10), datetime.time(1, 0)))
    return _DST[year]

def std_offset(market):
    return 0 if market == 'GB' else 1

def is_dst_utc(dt):
    s, e = dst_bounds(dt.year)
    return s <= dt < e

def utc_to_local(dt, market):
    return dt + datetime.timedelta(hours=std_offset(market) + (1 if is_dst_utc(dt) else 0))

def local_to_utc(dt, market):
    std = std_offset(market)
    u = dt - datetime.timedelta(hours=std)
    if is_dst_utc(u):
        s, _ = dst_bounds(dt.year)
        if s <= u < s + datetime.timedelta(hours=1):
            return u          # local time inside the spring gap keeps the standard offset
        return dt - datetime.timedelta(hours=std + 1)
    return u

def month_add(ym, n):
    y, m = int(ym[:4]), int(ym[5:7])
    t = y * 12 + (m - 1) + n
    return '%04d-%02d' % (t // 12, t % 12 + 1)

def month_end(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    if m == 12:
        return datetime.date(y, 12, 31)
    return datetime.date(y, m + 1, 1) - datetime.timedelta(days=1)

def parse_utc(s):
    """ISO-8601 instant with Z or numeric offset -> naive UTC datetime."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:?\d{2})?', s)
    if not m:
        return None
    y, mo, d, h, mi, se = (int(m.group(i)) for i in range(1, 7))
    dt = datetime.datetime(y, mo, d, h, mi, se)
    off = m.group(8)
    if off and off != 'Z':
        off = off.replace(':', '')
        sign = 1 if off[0] == '+' else -1
        oh = int(off[1:3])
        om = int(off[3:5])
        dt -= sign * datetime.timedelta(hours=oh, minutes=om)
    return dt


# ------------------------------------------------------------------ readers

def text_records(path, delim=',', enc='utf-8'):
    """Records of a delimited file (spec 4.2).

    Comments, the header and re-emitted headers are not records.  A re-emitted
    header redefines the column order of the records that follow it.  Returns a
    list of (ordinal, row, header) with the 1-based record ordinal.
    """
    rdr = csv.reader(io.StringIO(read_text(path, enc), newline=''), delimiter=delim)
    out = []
    hdr = None
    ordinal = 0
    for r in rdr:
        if not r or all(x == '' for x in r):
            continue
        if r[0].startswith('#'):
            continue
        cur = [x.strip() for x in r]
        if hdr is None:
            hdr = cur
            continue
        if len(cur) == len(hdr) and set(cur) == set(hdr):
            hdr = cur
            continue
        if len(cur) > len(hdr):
            cur = cur[:len(hdr)]
        ordinal += 1
        out.append((ordinal, cur, hdr))
    return out

def jsonl_records(path):
    """(ordinal, object) for every record line; control and header lines are not records."""
    out = []
    ordinal = 0
    for line in read_text(path).splitlines():
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        if not isinstance(o, dict):
            ordinal += 1
            out.append((ordinal, o))
            continue
        if '_control' in o or '_header' in o:
            continue
        ordinal += 1
        out.append((ordinal, o))
    return out

def pdf_table(path, header):
    """Rows of a pdf text table with the given header; repeated headers are skipped."""
    want = list(header)
    keys = [norm_tok(x) for x in want]
    out = []
    active = False
    for line in pdf_text_lines(path):
        if '|' not in line:
            continue
        parts = [x.strip() for x in line.split('|')]
        if parts and parts[0] == '':
            parts = parts[1:]
        if parts and parts[-1] == '':
            parts = parts[:-1]
        if [norm_tok(x) for x in parts] == keys:
            active = True
            continue
        if not active:
            continue
        if len(parts) != len(want):
            continue
        out.append(parts)
    return out

def pdf_text_lines(path):
    r = PdfReader(path)
    out = []
    for pg in r.pages:
        t = pg.extract_text()
        if t:
            out.extend(t.split('\n'))
    return out

def md_table(path, header):
    """Rows of a markdown table with the given header."""
    want = [norm_tok(x) for x in header]
    out = []
    active = False
    for line in read_text(path).splitlines():
        if not line.startswith('|'):
            active = False
            continue
        parts = [x.strip() for x in line.strip('|').split('|')]
        if all(re.fullmatch(r'-*', x) for x in parts):
            continue
        if [norm_tok(x) for x in parts] == want:
            active = True
            continue
        if not active:
            continue
        if set(parts) == set(want):
            continue
        if len(parts) > len(want):
            parts = parts[:len(want)]
        out.append(parts)
    return out

def docx_tables(path):
    d = _Docx(path)
    res = []
    for child in d.element.body.iterchildren():
        if child.tag == _qn('w:tbl'):
            res.append([[c.text for c in r.cells] for r in _Table(child, d).rows])
    return res

def docx_appendix(path, header):
    """Data rows of every table of the document whose header matches (spec 4.2)."""
    want = [norm_tok(x) for x in header]
    out = []
    for t in docx_tables(path):
        if t and [norm_tok(c) for c in t[0]] == want:
            out.extend(t[1:])
    return out

def docx_custom_props(path):
    return _custom_props(path)

def _custom_props(path):
    import zipfile
    try:
        z = zipfile.ZipFile(path)
        x = z.read('docProps/custom.xml')
    except Exception:
        return {}
    out = {}
    for pr in etree.fromstring(x):
        name = pr.get('name')
        val = ''.join(pr.itertext())
        if name:
            out[name] = val
    return out

def xlsx_sheets(path):
    """{sheet: (header, rows)}; repeated header rows inside a sheet are not records."""
    wb = load_workbook(path, read_only=True, data_only=True)
    out = {}
    for sn in wb.sheetnames:
        ws = wb[sn]
        hdr = None
        rows = []
        for r in ws.iter_rows(values_only=True):
            if r is None or all(v is None for v in r):
                continue
            if hdr is None:
                hdr = r
                continue
            if tuple(str(v) if v is not None else '' for v in r) == \
               tuple(str(v) if v is not None else '' for v in hdr):
                continue
            rows.append(r)
        out[sn] = (hdr, rows)
    return out

def xlsx_custom_props(path):
    return _custom_props(path)

def parquet_rows(path):
    import pyarrow.parquet as pq
    return pq.read_table(path).to_pylist()

def parquet_meta(path):
    import pyarrow.parquet as pq
    md = pq.ParquetFile(path).schema_arrow.metadata or {}
    v = md.get(b'delivery_control')
    if v is None:
        return {}
    if isinstance(v, bytes):
        v = v.decode()
    return json.loads(v)

def sqlite_tables(path):
    con = sqlite3.connect(path)
    names = [r[0] for r in con.execute(
        "select name from sqlite_master where type='table' order by name")]
    out = {}
    for n in names:
        cols = [c[1] for c in con.execute('PRAGMA table_info("%s")' % n)]
        out[n] = [dict(zip(cols, r)) for r in con.execute('select * from "%s"' % n)]
    con.close()
    return out

def sqlite_control(path):
    try:
        con = sqlite3.connect(path)
        cur = con.execute('select * from delivery_control')
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        con.close()
        if row:
            return dict(zip(cols, row))
    except Exception:
        pass
    return {}

def html_register_rows(path, table_id='register'):
    """Rows of an html register table honouring rowspan; returns (cells, is_header)."""
    tree = etree.fromstring(read_bytes(path), etree.HTMLParser(encoding='utf-8', recover=True))
    out = []
    for tbl in tree.iter('table'):
        if table_id and tbl.get('id') != table_id:
            continue
        pending = {}
        for tr in tbl.iter('tr'):
            cells = [c for c in tr if c.tag in ('td', 'th')]
            row = []
            ci = 0
            col = 0
            while True:
                if col in pending:
                    if pending[col][0] > 0:
                        row.append(pending[col][1])
                        pending[col] = (pending[col][0] - 1, pending[col][1])
                        col += 1
                        continue
                    del pending[col]
                    col += 1
                    continue
                if ci >= len(cells):
                    break
                c = cells[ci]
                ci += 1
                txt = ' '.join(''.join(c.itertext()).split())
                row.append(txt)
                span = int(c.get('rowspan', '1') or '1')
                if span > 1:
                    pending[col] = (span - 1, txt)
                col += 1
            for c in [c for c, v in pending.items() if v[0] <= 0]:
                del pending[c]
            is_hdr = bool(cells) and all(c.tag == 'th' for c in cells)
            out.append((row, is_hdr))
    return out

def fixed_width_records(path, rectype='10', enc='iso-8859-1'):
    out = []
    ordinal = 0
    for line in read_text(path, enc).splitlines():
        if line.startswith(rectype):
            ordinal += 1
            out.append((ordinal, line))
    return out

def ini_sections(path):
    """INI without interpolation; keys case-insensitive, inline ; and # are comments."""
    text = read_text(path)
    cur = 'DEFAULT'
    out = {}
    order = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line[0] in ';#':
            continue
        if line.startswith('[') and line.endswith(']'):
            cur = line[1:-1].strip()
            continue
        sep = '=' if '=' in line else (':' if ':' in line else None)
        if sep is None:
            continue
        k, v = line.split(sep, 1)
        k = k.strip()
        v = v.split(';')[0].split('#')[0].strip()
        key = (cur.upper(), k.upper())
        if key in out:
            continue
        out[key] = v
        order.setdefault(cur.upper(), []).append(k.upper())
    return out, order

def yaml_load(path):
    """YAML with every scalar read as a string (spec 4.4)."""
    class L(yaml.SafeLoader):
        pass
    L.add_constructor('tag:yaml.org,2002:bool', lambda l, n: l.construct_scalar(n))
    L.add_constructor('tag:yaml.org,2002:int', lambda l, n: l.construct_scalar(n))
    L.add_constructor('tag:yaml.org,2002:float', lambda l, n: l.construct_scalar(n))
    L.add_constructor('tag:yaml.org,2002:null', lambda l, n: l.construct_scalar(n))
    L.add_constructor('tag:yaml.org,2002:timestamp', lambda l, n: l.construct_scalar(n))
    return yaml.load(read_text(path), Loader=L)

def xml_root(path):
    return etree.fromstring(read_bytes(path))

def xml_elems(root, tag):
    """Child elements with the given local name, ignoring the namespace."""
    return [el for el in root.iter()
            if isinstance(el.tag, str) and etree.QName(el).localname.lower() == tag.lower()]


def xml_text(el, name):
    for c in el:
        if isinstance(c.tag, str) and etree.QName(c).localname.lower() == name.lower():
            return c.text
    return None

def mbox_messages(path):
    """Messages of an mbox file; the control message is one of them."""
    text = read_text(path)
    starts = [m.start() for m in re.finditer(r'^From ', text, re.M)]
    msgs = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(text)
        chunk = text[s:e]
        parts = re.split(r'\r?\n\r?\n', chunk, maxsplit=1)
        head = parts[0]
        body = parts[1] if len(parts) > 1 else ''
        hdrs = {}
        cur = None
        for l in head.splitlines()[1:]:
            if l[:1] in (' ', '\t') and cur:
                hdrs[cur] += ' ' + l.strip()
            elif ':' in l:
                k, v = l.split(':', 1)
                cur = k.strip().lower()
                hdrs[cur] = v.strip()
        if 'quoted-printable' in hdrs.get('content-transfer-encoding', '').lower():
            import quopri
            body = quopri.decodestring(body.encode('utf-8')).decode('utf-8', 'replace')
        msgs.append({'headers': hdrs, 'body': body})
    return msgs

def ics_events(path):
    out = []
    cur = {}
    key = None
    for raw in read_text(path).splitlines():
        line = raw.rstrip('\r')
        if line[:1] == ' ':
            if key:
                cur[key] += line[1:]
            continue
        if line == 'BEGIN:VEVENT':
            cur = {}
            continue
        if line == 'END:VEVENT':
            out.append(cur)
            cur = {}
            continue
        if ':' in line:
            k, v = line.split(':', 1)
            key = k.split(';')[0]
            cur[key] = v
    return out

def parse_control_kv(s):
    out = {}
    for part in re.split(r'[;\s]+', s.strip()):
        if '=' in part:
            k, v = part.split('=', 1)
            out[k.strip()] = v.strip()
    return out

def control_from_comment(text):
    for line in text.splitlines():
        t = line.strip()
        if t.startswith('#') and 'control_id=' in t:
            return parse_control_kv(t.lstrip('#').strip())
    return {}


# ------------------------------------------------------------------ estate

class Estate:

    def __init__(self, root):
        self.root = root
        self.manifest = json.loads(read_text(os.path.join(root, 'delivery_manifest.json')))
        self.cycle = self.manifest['cycle']
        ds = []
        for d in self.manifest['deliveries']:
            if d['cycle'] == self.cycle:
                d = dict(d)
                d['_dt'] = parse_utc(d['delivered_at'])
                ds.append(d)
        ds.sort(key=lambda d: (d['_dt'], d['delivery_id']))
        self.deliveries = ds
        self.by_file = {}
        for i, d in enumerate(ds):
            d['_ord'] = i
            self.by_file.setdefault(d['file'], []).append(d)
        self.certified = self.manifest.get('certified_snapshot_partitions', [])

    def path(self, name):
        return os.path.join(self.root, name)

    def has(self, name):
        return os.path.exists(self.path(name))

    def delivery_of(self, name):
        ds = self.by_file.get(name)
        return ds[0] if ds else None

    def order_of(self, name):
        d = self.delivery_of(name)
        return d['_ord'] if d else -1


def _lower(d):
    return {str(k).strip().lower(): v for k, v in d.items()} if isinstance(d, dict) else {}


def read_control(est, name):
    """The delivery control block of a file (spec 2.1)."""
    p = est.path(name)
    if not os.path.exists(p):
        return None
    low = os.path.basename(name).lower()
    try:
        if low.endswith('.jsonl'):
            for line in read_text(p).splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                if isinstance(o, dict) and '_control' in o:
                    return o['_control']
            return {}
        if low.endswith('.json'):
            o = json.loads(read_text(p))
            if isinstance(o, dict):
                for k in ('control', 'delivery_control'):
                    if k in o:
                        return o[k]
            return {}
        if low.endswith('.yaml') or low.endswith('.yml'):
            d = yaml_load(p)
            if isinstance(d, dict) and 'delivery_control' in d:
                return d['delivery_control']
            return {}
        if low.endswith('.parquet'):
            return parquet_meta(p)
        if low.endswith('.db'):
            return sqlite_control(p)
        if low.endswith(('.xlsx', '.docx')):
            return _custom_props(p)
        if low.endswith('.pdf'):
            for line in reversed(pdf_text_lines(p)):
                if 'control_id=' in line:
                    return parse_control_kv(line.split('Delivery control:')[-1].strip())
            return {}
        if low.endswith('.html'):
            for line in read_text(p).splitlines():
                m = re.search(r'<meta\s+name="delivery-control"\s+content="([^"]*)"', line)
                if m:
                    return parse_control_kv(m.group(1))
            return {}
        if low.endswith('.md'):
            lines = read_text(p).splitlines()
            for i, line in enumerate(lines):
                if line.strip().lower().startswith('## delivery control'):
                    sec = {}
                    for l in lines[i + 1:]:
                        t = l.strip()
                        if t.startswith('#') and not t.lower().startswith('## delivery'):
                            break
                        if t.startswith('|'):
                            parts = [x.strip() for x in t.strip('|').split('|')]
                            if len(parts) >= 2 and parts[0] and not set(parts[0]) <= set('-'):
                                sec[parts[0]] = parts[1]
                    return sec
            return {}
        if low.endswith('.ics'):
            for line in read_text(p).splitlines():
                if line.startswith('X-DELIVERY-CONTROL:'):
                    return parse_control_kv(line.split(':', 1)[1])
            return {}
        if low.endswith('.toml'):
            d = tomli.loads(read_text(p))
            for k in ('delivery_control', 'control'):
                if k in d:
                    return d[k]
            return {}
        if low.endswith('.ini'):
            sec, _ = ini_sections(p)
            return {k[1].lower(): v for k, v in sec.items() if k[0] == 'DELIVERY_CONTROL'}
        if low.endswith('.xml'):
            for el in xml_elems(xml_root(p), 'control'):
                return dict(el.attrib)
            return {}
        if low.endswith('.mbox'):
            for m in mbox_messages(p):
                if norm_tok(m['headers'].get('subject')) == 'DELIVERY CONTROL':
                    return parse_control_kv(m['body'])
            return {}
        if low.endswith('.log'):
            return control_from_comment(read_text(p))
        if low.endswith('.txt'):
            for line in read_text(p, 'iso-8859-1').splitlines():
                if line.startswith('99') and 'control_id=' in line:
                    return parse_control_kv(line[2:])
            return control_from_comment(read_text(p, 'iso-8859-1'))
        return control_from_comment(read_text(p))
    except Exception:
        return None


def as_int(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    s = str(v).strip()
    if s == '':
        return None
    try:
        return int(s)
    except ValueError:
        try:
            return int(Decimal(s))
        except Exception:
            return None


# ------------------------------------------------------------------ engine

SNAP_FILES = {
    'snapshots_2025_02.csv': ('csv', ','),
    'snapshots_2025_03.tsv': ('csv', '\t'),
    'snapshots_2025_06_a.csv': ('csv', ';'),
    'snapshots_2025_06_b.jsonl': ('jsonl', None),
    'snapshots_2025_08_a.csv': ('csv', ','),
    'snapshots_2025_08_b.tsv': ('csv', '\t'),
    'snapshots_2025_10_a.csv': ('csv', ','),
    'snapshots_2025_10_b.tsv': ('csv', '\t'),
    'snapshots_2025_10_b_restated.tsv': ('csv', '\t'),
    'snapshots_2025_11_a.csv': ('csv', ','),
    'snapshots_2025_11_a_rev2.csv': ('csv', ','),
    'snapshots_2026_02_a.csv': ('csv', ','),
    'snapshots_2026_02_b.jsonl': ('jsonl', None),
    'snapshots_2026_06.csv': ('csv', ','),
    'snapshots_2025_04.parquet': ('parquet', None),
    'snapshots_2025_11_b.parquet': ('parquet', None),
    'snapshots_2026_05_a.parquet': ('parquet', None),
    'snapshots_2025_05.xlsx': ('xlsx', None),
    'snapshots_2025_09.xlsx': ('xlsx', None),
    'snapshots_2025_12.xlsx': ('xlsx', None),
    'snapshots_2026_03.xlsx': ('xlsx', None),
    'snapshots_2026_04.txt': ('fixed', None),
    'snapshots_2026_05_b.txt': ('fixed', None),
    'servicing_snapshots_2025q3.db': ('sqlite', None),
    'servicing_snapshots_2026q1.db': ('sqlite', None),
}

WRITTEN_OFF = {'W', 'S', 'CO', 'CLOSED', 'WRITTENOFF', 'WRITTEN-OFF', 'WRITTEN_OFF'}


class Engine:

    def __init__(self, est):
        self.est = est
        self.counts = {}
        self.hashes = {}
        self.controls = {}
        self.files_read = 0
        self.quarantine = defaultdict(set)      # delivery lower -> set of ordinals
        self.d = {}                              # parsed payloads

    # -------------------------------------------------- delivery records
    def scan(self, name):
        """Parse one delivery: record count, hash total and the data the engine needs."""
        p = self.est.path(name)
        if not os.path.exists(p):
            return None
        fn = getattr(self, 'scan_' + re.sub(r'[^0-9a-z]+', '_', name.lower()), None)
        keys = None
        payload = None
        if fn is not None:
            keys, payload = fn(p)
        else:
            keys = generic_hash_keys(p)
        self.counts[self.est.delivery_of(name)['delivery_id']] = len(keys)
        self.hashes[self.est.delivery_of(name)['delivery_id']] = sum(digits_int(k) for k in keys)
        self.files_read += 1
        if payload is not None:
            self.d[name] = payload
        return keys

    # ---- applications
    def scan_applications_2025_01_csv(self, p):
        recs = []
        keys = []
        quar = self.quarantine['applications_2025_01.csv']
        for o, r, h in text_records(p, ','):
            keys.append(r[h.index('account_ref')])
            if o in quar:
                continue
            recs.append((o, r[h.index('app_id')], r[h.index('account_ref')],
                         r[h.index('customer_ref')], r[h.index('branch_code')],
                         r[h.index('product_code')], None,
                         r[h.index('decided_at_local')], True,
                         r[h.index('limit_amount')], r[h.index('revision')],
                         r[h.index('received_at_utc')]))
        return keys, {'records': recs, 'delivered': self.est.order_of('applications_2025_01.csv')}

    def scan_applications_2025_02_tsv(self, p):
        recs = []
        keys = []
        quar = self.quarantine['applications_2025_02.tsv']
        for o, r, h in text_records(p, '\t'):
            keys.append(r[h.index('acct')])
            if o in quar:
                continue
            recs.append((o, r[h.index('app_id')], r[h.index('acct')], r[h.index('cust')],
                         r[h.index('branch')], r[h.index('product')],
                         r[h.index('decision_utc')], None, False,
                         r[h.index('limit')], r[h.index('rev')], r[h.index('received_utc')]))
        return keys, {'records': recs, 'delivered': self.est.order_of('applications_2025_02.tsv')}

    def scan_applications_2025_03_txt(self, p):
        recs = []
        keys = []
        quar = self.quarantine['applications_2025_03.txt']
        for o, line in fixed_width_records(p):
            acct = line[13:25].strip()
            keys.append(acct)
            if o in quar:
                continue
            recs.append((o, line[2:13].strip(), acct, line[25:37].strip(),
                         line[37:43].strip(), line[43:51].strip(), None,
                         line[51:65].strip(), True,
                         Decimal(line[65:78].strip() or '0') / 100,
                         line[78:80].strip(), line[80:94].strip()))
        return keys, {'records': recs, 'delivered': self.est.order_of('applications_2025_03.txt')}

    def scan_applications_2025_04_csv(self, p):
        recs = []
        keys = []
        quar = self.quarantine['applications_2025_04.csv']
        for o, r, h in text_records(p, ';'):
            keys.append(r[h.index('konto')])
            if o in quar:
                continue
            recs.append((o, None, r[h.index('konto')], r[h.index('kunde')],
                         r[h.index('filial')], r[h.index('produkt')],
                         r[h.index('entscheidung')], None, False,
                         r[h.index('limit')], r[h.index('revision')],
                         r[h.index('eingang_utc')]))
        return keys, {'records': recs, 'delivered': self.est.order_of('applications_2025_04.csv')}

    def scan_applications_2025_04_reextract_csv(self, p):
        appid = {}
        keys = []
        for o, r, h in text_records(p, ','):
            acct = r[h.index('account')]
            keys.append(acct)
            a = norm_acct(acct)
            appid[a] = norm_id(r[h.index('app_id')])
        return keys, {'appid': appid}

    def scan_applications_2025_05_xlsx(self, p):
        recs = []
        keys = []
        quar = self.quarantine['applications_2025_05.xlsx']
        hdr, rows = xlsx_sheets(p)['applications']
        names = [str(x) for x in hdr]
        ia = names.index('app_id')
        iac = names.index('account')
        ic = names.index('customer')
        ib = names.index('branch')
        ip = names.index('product_code_current')
        idt = names.index('decided_local')
        il = names.index('limit')
        ir = names.index('revision')
        irc = names.index('received_utc')
        for o, r in enumerate(rows, 1):
            keys.append(r[iac])
            if o in quar:
                continue
            recs.append((o, r[ia], r[iac], r[ic], r[ib], r[ip], None,
                         excel_to_dt(r[idt]), True, r[il], r[ir], r[irc]))
        return keys, {'records': recs, 'delivered': self.est.order_of('applications_2025_05.xlsx')}

    def scan_applications_2025_06_jsonl(self, p):
        recs = []
        keys = []
        quar = self.quarantine['applications_2025_06.jsonl']
        for o, obj in jsonl_records(p):
            keys.append(obj['acct'])
            if o in quar:
                continue
            recs.append((o, obj.get('app'), obj['acct'], obj.get('cust'), obj.get('branch'),
                         obj.get('product'),
                         datetime.datetime(1970, 1, 1) + datetime.timedelta(milliseconds=int(obj['decided_ms'])),
                         None, False, obj.get('limit'), obj.get('rev'),
                         datetime.datetime(1970, 1, 1) + datetime.timedelta(milliseconds=int(obj['received_ms']))))
        return keys, {'records': recs, 'delivered': self.est.order_of('applications_2025_06.jsonl')}

    def scan_applications_master_2025h1_parquet(self, p):
        keys = []
        rev = {}
        for r in parquet_rows(p):
            keys.append(r['account'])
            a = norm_acct(r['account'])
            if a is not None:
                rev[a] = bool(r['withdrawal_reversed'])
        return keys, {'reversed': rev}

    # ---- snapshots
    def snapshot_payload(self, name, rows):
        """rows: iterable of (ordinal, acct, period, dpd_raw, status)."""
        keys = []
        recs = []
        quar = self.quarantine[name.lower()]
        for o, acct, period, dpd, st in rows:
            keys.append(acct)
            if o in quar:
                continue
            recs.append((norm_acct(acct), norm_period(period), dpd, norm_tok(st)))
        return keys, {'records': recs}

    def scan_snapshots_2025_02_csv(self, p):
        return self.snapshot_payload('snapshots_2025_02.csv',
            ((o, r[h.index('account')], r[h.index('period')], r[h.index('dpd')], r[h.index('status')])
             for o, r, h in text_records(p, ',')))

    def scan_snapshots_2025_03_tsv(self, p):
        return self.snapshot_payload('snapshots_2025_03.tsv',
            ((o, r[h.index('acct')], r[h.index('period_yyyymm')], r[h.index('days_past_due')],
              r[h.index('status_cd')]) for o, r, h in text_records(p, '\t')))

    def scan_snapshots_2025_06_a_csv(self, p):
        return self.snapshot_payload('snapshots_2025_06_a.csv',
            ((o, r[h.index('konto')], r[h.index('okres')], r[h.index('dpd')], r[h.index('status')])
             for o, r, h in text_records(p, ';')))

    def scan_snapshots_2025_06_b_jsonl(self, p):
        return self.snapshot_payload('snapshots_2025_06_b.jsonl',
            ((o, obj['a'], obj['p'], obj.get('dpd'), obj.get('s')) for o, obj in jsonl_records(p)))

    def scan_snapshots_2026_02_b_jsonl(self, p):
        return self.snapshot_payload('snapshots_2026_02_b.jsonl',
            ((o, obj['a'], obj['p'], obj.get('dpd'), obj.get('s')) for o, obj in jsonl_records(p)))

    def scan_snapshots_2025_08_a_csv(self, p):
        return self.snapshot_payload('snapshots_2025_08_a.csv',
            ((o, r[0], r[1], r[h.index('dpd')], r[h.index('status')])
             for o, r, h in text_records(p, ',')))

    def scan_snapshots_2025_08_b_tsv(self, p):
        return self.snapshot_payload('snapshots_2025_08_b.tsv',
            ((o, r[h.index('acct')], r[h.index('period_yyyymm')], r[h.index('days_past_due')],
              r[h.index('status_cd')]) for o, r, h in text_records(p, '\t')))

    def scan_snapshots_2025_10_a_csv(self, p):
        return self.snapshot_payload('snapshots_2025_10_a.csv',
            ((o, r[0], r[1], r[h.index('dpd')], r[h.index('status')])
             for o, r, h in text_records(p, ',')))

    def scan_snapshots_2025_10_b_tsv(self, p):
        return self.snapshot_payload('snapshots_2025_10_b.tsv',
            ((o, r[h.index('acct')], r[h.index('period_yyyymm')], r[h.index('days_past_due')],
              r[h.index('status_cd')]) for o, r, h in text_records(p, '\t')))

    def scan_snapshots_2025_10_b_restated_tsv(self, p):
        """Restatement flags: dpd_reason = SYSTEM_ERROR voids the certified DPD (governance 3.12)."""
        recs = []
        keys = []
        quar = self.quarantine['snapshots_2025_10_b_restated.tsv']
        for o, r, h in text_records(p, '\t'):
            keys.append(r[h.index('acct')])
            if o in quar:
                continue
            if norm_tok(r[h.index('dpd_reason')]) != 'SYSTEM_ERROR':
                continue
            recs.append((norm_acct(r[h.index('acct')]), norm_period(r[h.index('period_yyyymm')])))
        return keys, {'system_error': recs}

    def scan_snapshots_2025_11_a_csv(self, p):
        return self.snapshot_payload('snapshots_2025_11_a.csv',
            ((o, r[h.index('account')], r[h.index('period')], r[h.index('dpd')], r[h.index('status')])
             for o, r, h in text_records(p, ',')))

    def scan_snapshots_2025_11_a_rev2_csv(self, p):
        return self.snapshot_payload('snapshots_2025_11_a_rev2.csv',
            ((o, r[h.index('account')], r[h.index('period')], r[h.index('dpd')], r[h.index('status')])
             for o, r, h in text_records(p, ',')))

    def scan_snapshots_2026_02_a_csv(self, p):
        return self.snapshot_payload('snapshots_2026_02_a.csv',
            ((o, r[0], r[1], r[h.index('dpd')], r[h.index('status')])
             for o, r, h in text_records(p, ',')))

    def scan_snapshots_2026_06_csv(self, p):
        return self.snapshot_payload('snapshots_2026_06.csv',
            ((o, r[h.index('account')], r[h.index('period')], r[h.index('dpd')], r[h.index('status')])
             for o, r, h in text_records(p, ',')))

    def scan_snapshots_2025_04_parquet(self, p):
        return self.snapshot_payload('snapshots_2025_04.parquet',
            ((i, r['account'], r['period'], r['dpd'], r['status'])
             for i, r in enumerate(parquet_rows(p), 1)))

    def scan_snapshots_2025_11_b_parquet(self, p):
        return self.snapshot_payload('snapshots_2025_11_b.parquet',
            ((i, r['account'], r['period'], r['dpd'], r['status'])
             for i, r in enumerate(parquet_rows(p), 1)))

    def scan_snapshots_2026_05_a_parquet(self, p):
        return self.snapshot_payload('snapshots_2026_05_a.parquet',
            ((i, r['account'], r['period'], r['dpd'], r['status'])
             for i, r in enumerate(parquet_rows(p), 1)))

    def _xlsx_snap(self, p, name):
        out = []
        ordinal = 0
        for sn, (hdr, rows) in xlsx_sheets(p).items():
            names = [str(x) for x in hdr]
            ia = names.index('account')
            ip = names.index('period')
            idp = names.index('dpd')
            ist = names.index('status')
            for r in rows:
                ordinal += 1
                per = r[ip]
                if isinstance(per, datetime.datetime):
                    period = '%04d-%02d' % (per.year, per.month)
                elif isinstance(per, datetime.date):
                    period = '%04d-%02d' % (per.year, per.month)
                elif isinstance(per, int):
                    period = norm_period(str(per))
                else:
                    period = norm_period(str(per))
                out.append((ordinal, r[ia], period, r[idp], r[ist]))
        return self.snapshot_payload(name, out)

    def scan_snapshots_2025_05_xlsx(self, p):
        return self._xlsx_snap(p, 'snapshots_2025_05.xlsx')

    def scan_snapshots_2025_09_xlsx(self, p):
        return self._xlsx_snap(p, 'snapshots_2025_09.xlsx')

    def scan_snapshots_2025_12_xlsx(self, p):
        return self._xlsx_snap(p, 'snapshots_2025_12.xlsx')

    def scan_snapshots_2026_03_xlsx(self, p):
        return self._xlsx_snap(p, 'snapshots_2026_03.xlsx')

    def scan_snapshots_2026_04_txt(self, p):
        return self.snapshot_payload('snapshots_2026_04.txt',
            ((o, line[2:14].strip(), line[14:20].strip(), line[20:24].strip(), line[24:25].strip())
             for o, line in fixed_width_records(p)))

    def scan_snapshots_2026_05_b_txt(self, p):
        return self.snapshot_payload('snapshots_2026_05_b.txt',
            ((o, line[2:14].strip(), line[14:20].strip(), line[20:24].strip(), line[24:25].strip())
             for o, line in fixed_width_records(p)))

    def scan_servicing_snapshots_2025q3_db(self, p):
        return self._sqlite_snap(p, 'servicing_snapshots_2025q3.db')

    def scan_servicing_snapshots_2026q1_db(self, p):
        return self._sqlite_snap(p, 'servicing_snapshots_2026q1.db')

    def _sqlite_snap(self, p, name):
        tabs = sqlite_tables(p)
        out = []
        ordinal = 0
        for tn in sorted(tabs):
            for r in tabs[tn]:
                ordinal += 1
                out.append((ordinal, r['account'], norm_period(r['period']), r['dpd'], r['status']))
        return self.snapshot_payload(name, out)

    # ---- scores
    def scan_score_events_backfill_csv(self, p):
        keys = []
        quar = self.quarantine['score_events_backfill.csv']
        ev = []
        for o, r, h in text_records(p, ','):
            keys.append(r[h.index('account')])
            if o in quar:
                continue
            ev.append((norm_acct(r[h.index('account')]), norm_id(r[h.index('event_id')]),
                       norm_id(r[h.index('run_id')]), parse_utc(r[h.index('scored_at')]),
                       int(r[h.index('score')])))
        return keys, {'events': ev}

    def scan_score_events_node5_parquet(self, p):
        keys = []
        quar = self.quarantine['score_events_node5.parquet']
        ev = []
        for i, r in enumerate(parquet_rows(p), 1):
            keys.append(r['account'])
            if i in quar:
                continue
            ev.append((norm_acct(r['account']), norm_id(r['event_id']), norm_id(r['run_id']),
                       datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=int(r['scored_at_s'])),
                       int(r['score'])))
        return keys, {'events': ev}

    def scan_score_events_node6_xml(self, p):
        keys = []
        quar = self.quarantine['score_events_node6.xml']
        ev = []
        root = xml_root(p)
        for i, el in enumerate(xml_elems(root, 'event'), 1):
            acct = xml_text(el, 'account')
            keys.append(acct)
            if i in quar:
                continue
            ev.append((norm_acct(acct), norm_id(el.get('id')), norm_id(el.get('run')),
                       parse_utc(xml_text(el, 'scoredAt')), int(xml_text(el, 'score'))))
        return keys, {'events': ev}

    def scan_score_events_node7_tsv(self, p):
        keys = []
        quar = self.quarantine['score_events_node7.tsv']
        ev = []
        for o, r, h in text_records(p, '\t'):
            keys.append(r[h.index('account')])
            if o in quar:
                continue
            serial = Decimal(r[h.index('scored_at_serial_utc')])
            secs = (serial - 25569) * 86400
            ts = datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=int(secs.to_integral_value(rounding=ROUND_HALF_EVEN)))
            ev.append((norm_acct(r[h.index('account')]), norm_id(r[h.index('event_id')]),
                       norm_id(r[h.index('run_id')]), ts, int(r[h.index('score')])))
        return keys, {'events': ev}

    def _jsonl_score(self, p, name):
        keys = []
        quar = self.quarantine[name.lower()]
        ev = []
        for o, obj in jsonl_records(p):
            keys.append(obj['acct'])
            if o in quar:
                continue
            ev.append((norm_acct(obj['acct']), norm_id(obj['event']), norm_id(obj['run']),
                       datetime.datetime(1970, 1, 1) + datetime.timedelta(milliseconds=int(Decimal(str(obj['ts_ms'])))),
                       int(obj['score'])))
        return keys, {'events': ev}

    def scan_score_batches_2025_q1_jsonl(self, p):
        return self._jsonl_score(p, 'score_batches_2025_q1.jsonl')

    def scan_score_batches_2025_q2_a_jsonl(self, p):
        return self._jsonl_score(p, 'score_batches_2025_q2_a.jsonl')

    def scan_score_batches_2025_q2_b_jsonl(self, p):
        return self._jsonl_score(p, 'score_batches_2025_q2_b.jsonl')

    def scan_score_batches_2025_q2_c_jsonl(self, p):
        return self._jsonl_score(p, 'score_batches_2025_q2_c.jsonl')

    def _log_score(self, p, name, node):
        keys = []
        quar = self.quarantine[name.lower()]
        ev = []
        voids = set()
        recs = []
        for line in read_text(p).splitlines():
            if not line or line[:1] == '#':
                continue
            toks = [t for t in line.split(' ') if t]
            if len(toks) >= 4 and toks[3] == 'SCORE':
                recs.append(('SCORE', line[:20], toks))
            elif node == 9 and len(toks) >= 4 and toks[3] == 'VOID':
                recs.append(('VOID', line[:20], toks))
        ordinal = 0
        for kind, ts, toks in recs:
            f = {}
            for t in toks[4:]:
                if '=' in t:
                    k, v = t.split('=', 1)
                    f[k] = v
                else:
                    f.setdefault('_', []).append(t)
            if kind == 'SCORE':
                acct = f.get('acct')
                keys.append(acct)
                ordinal += 1
                if ordinal in quar:
                    continue
                ev.append((norm_acct(acct), norm_id(f.get('event')), norm_id(f.get('run')),
                           parse_utc(ts), int(f.get('score'))))
            else:
                keys.append(f.get('run'))
                voids.add(norm_id(f.get('run')))
        return keys, {'events': ev, 'voids': voids}

    def scan_scoring_engine_node1_log(self, p):
        return self._log_score(p, 'scoring_engine_node1.log', 1)

    def scan_scoring_engine_node2_log(self, p):
        return self._log_score(p, 'scoring_engine_node2.log', 2)

    def scan_scoring_engine_node3_log(self, p):
        return self._log_score(p, 'scoring_engine_node3.log', 3)

    def scan_scoring_engine_node4_log(self, p):
        return self._log_score(p, 'scoring_engine_node4.log', 4)

    def scan_scoring_engine_node9_log(self, p):
        return self._log_score(p, 'scoring_engine_node9.log', 9)

    # ---- registers
    def scan_account_closures_2025_json(self, p):
        o = json.loads(read_text(p))
        keys = [c['account'] for c in o['closures']]
        cl = {}
        for c in o['closures']:
            a = norm_acct(c['account'])
            d = parse_date(c['closed'])
            if a and d:
                if a not in cl or d < cl[a]:
                    cl[a] = d
        return keys, {'closures': cl}

    def scan_account_closures_2026h1_csv(self, p):
        recs = text_records(p, ',')
        keys = [r[h.index('account')] for o, r, h in recs]
        cl = {}
        for o, r, h in recs:
            a = norm_acct(r[h.index('account')])
            d = parse_date(r[h.index('closed_on')])
            if a and d:
                if a not in cl or d < cl[a]:
                    cl[a] = d
        return keys, {'closures': cl}

    def scan_application_withdrawals_json(self, p):
        o = json.loads(read_text(p))
        keys = [w['account'] for w in o['withdrawals']]
        wd = defaultdict(list)
        for w in o['withdrawals']:
            a = norm_acct(w['account'])
            d = parse_date(w['withdrawn_on'])
            if a and d:
                wd[a].append(d)
        return keys, {'withdrawals': wd}

    def scan_status_events_chargeoff_2025_csv(self, p):
        recs = text_records(p, ',')
        keys = [r[h.index('account_ref')] for o, r, h in recs]
        out = []
        for o, r, h in recs:
            out.append((o, norm_id(r[h.index('event_id')]), r[h.index('account_ref')],
                        parse_date(r[h.index('chargeoff_date')])))
        return keys, {'chargeoffs': out}

    def scan_chargeoff_events_2026_parquet(self, p):
        rows = parquet_rows(p)
        keys = [r['account'] for r in rows]
        out = []
        for i, r in enumerate(rows, 1):
            d = r['chargeoff_date']
            if isinstance(d, datetime.datetime):
                d = d.date()
            out.append((i, norm_id(r['event_id']), r['account'], d))
        return keys, {'chargeoffs': out}

    def scan_status_events_consolidated_json(self, p):
        o = json.loads(read_text(p))
        ev = o['events']
        keys = [(e.get('ref') or e.get('subject')) for e in ev]
        rev = {}
        dec = {}
        for e in ev:
            ty = norm_tok(e.get('type'))
            src = norm_tok(e.get('source'))
            if ty == 'CO_REVERSAL':
                r = norm_id(e.get('ref'))
                d = parse_date(e.get('date'))
                if r and d:
                    rev.setdefault(r, []).append(d)
            elif ty == 'DECEASED' and src == 'CIVIL_REGISTRY':
                c = norm_cust(e.get('subject'))
                d = parse_date(e.get('date'))
                if c and d:
                    dec[c] = d if c not in dec else min(dec[c], d)
        return keys, {'reversals': rev, 'deceased': dec}

    def scan_deceased_notifications_feed_xml(self, p):
        els = xml_elems(xml_root(p), 'notification')
        keys = [xml_text(el, 'customer') for el in els]
        dec = {}
        for el in els:
            c = norm_cust(xml_text(el, 'customer'))
            d = parse_date(xml_text(el, 'notified'))
            if c and d:
                dec[c] = d if c not in dec else min(dec[c], d)
        return keys, {'deceased': dec}

    def scan_deceased_notifications_register_pdf(self, p):
        rows = pdf_table(p, ['customer', 'notified'])
        keys = [r[0] for r in rows]
        dec = {}
        for r in rows:
            c = norm_cust(r[0])
            d = parse_date(r[1])
            if c and d:
                dec[c] = d if c not in dec else min(dec[c], d)
        return keys, {'deceased': dec}

    def scan_fraud_alerts_2025_jsonl(self, p):
        recs = jsonl_records(p)
        keys = [o['case'] for o, o in [(x[0], x[1]) for x in recs]]
        alerts = []
        for o, obj in recs:
            alerts.append((norm_id(obj['case']), norm_acct(obj['account']),
                           parse_date(obj['alert_date'])))
        return keys, {'alerts': alerts}

    def scan_fraud_alerts_2026_xml(self, p):
        els = xml_elems(xml_root(p), 'alert')
        keys = [xml_text(el, 'case') for el in els]
        alerts = []
        for el in els:
            alerts.append((norm_id(xml_text(el, 'case')), norm_acct(xml_text(el, 'account')),
                           parse_date(xml_text(el, 'raised'))))
        return keys, {'alerts': alerts}

    def scan_fraud_case_dispositions_json(self, p):
        o = json.loads(read_text(p))
        keys = [c['case_id'] for c in o['cases']]
        disp = {}
        for c in o['cases']:
            disp[norm_id(c['case_id'])] = norm_tok(c['disposition'])
        return keys, {'dispositions': disp}

    def scan_snapshot_corrections_feed_xml(self, p):
        els = xml_elems(xml_root(p), 'correction')
        keys = [xml_text(el, 'account') for el in els]
        corr = {}
        for el in els:
            seq = digits_int(xml_text(el, 'seq'))
            a = norm_acct(xml_text(el, 'account'))
            per = norm_period(xml_text(el, 'period'))
            d = int(xml_text(el, 'dpd')) if xml_text(el, 'dpd') is not None else None
            if a and per:
                k = (a, per)
                if k not in corr or seq > corr[k][0]:
                    corr[k] = (seq, d)
        return keys, {'corrections': {k: v[1] for k, v in corr.items()}}

    def scan_ops_corrections_mbox(self, p):
        msgs = mbox_messages(p)
        keys = []
        corr = {}
        retracted = {}
        items = []
        for i, m in enumerate(msgs):
            subj = norm_tok(m['headers'].get('subject'))
            mid = m['headers'].get('message-id', '')
            if subj == 'DELIVERY CONTROL':
                continue
            keys.append(mid)
            dt = email_date(m['headers'].get('date'))
            if subj == 'RETRACT':
                rt = norm_id(re.search(r'<([^>]*)>', subj).group(1)) if re.search(r'<([^>]*)>', subj) else ''
                retracted.setdefault(rt, []).append(dt)
                items.append(('retract', i, dt, mid))
                continue
            body = m['body']
            acct = period = dpd = None
            for line in body.splitlines():
                if ':' in line:
                    k, v = line.split(':', 1)
                    k = k.strip().lower()
                    v = v.strip()
                    if k == 'account':
                        acct = v
                    elif k == 'period':
                        period = v
                    elif k == 'dpd':
                        dpd = v
            items.append(('corr', i, dt, mid, norm_acct(acct), norm_period(period), dpd))
        # a correction is void when a later message retracts its Message-ID
        for it in items:
            if it[0] != 'corr':
                continue
            mid = it[3]
            if any(d > it[2] for d in retracted.get(norm_id(mid), [])):
                continue
            a, per, dpd = it[4], it[5], it[6]
            if not a or not per or dpd is None:
                continue
            k = (a, per)
            if k not in corr or it[2] > corr[k][0]:
                corr[k] = (it[2], norm_id(mid), int(Decimal(dpd)))
        return keys, {'corrections': {k: v[2] for k, v in corr.items()}}

    def scan_treasury_fixings_2024_2026_xml(self, p):
        els = xml_elems(xml_root(p), 'fixing')
        keys = [el.get('date') for el in els]
        fix = defaultdict(dict)
        for el in els:
            ccy = norm_tok(el.get('ccy'))
            date = parse_date(el.get('date'))
            rev = digits_int(el.get('rev') or '1')
            per = Decimal(el.get('per') or '1')
            val = Decimal(el.text.strip().replace(',', '.'))
            cur = fix[ccy].get(date)
            if cur is None or rev > cur[0]:
                fix[ccy][date] = (rev, val, per)
        return keys, {'fixings': fix}

    def scan_fx_rates_ecb_mirror_xml(self, p):
        root = xml_root(p)
        els = xml_elems(root, 'rate')
        keys = [el.get('date') for el in els]
        iso = {}
        for el in xml_elems(root, 'currency'):
            iso[el.get('numeric')] = norm_tok(el.get('alpha'))
        return keys, {'iso': iso}

    def scan_customer_merges_2026_tsv(self, p):
        recs = text_records(p, '\t')
        keys = [r[h.index('merged_customer')] for o, r, h in recs]
        merges = {}
        for o, r, h in recs:
            if norm_tok(r[h.index('decision')]) != 'APPROVED':
                continue
            m = norm_cust(r[h.index('merged_customer')])
            s = norm_cust(r[h.index('surviving_customer')])
            d = parse_date(r[h.index('decided_on')])
            if m and s:
                if m not in merges or d > merges[m][0]:
                    merges[m] = (d, s)
        return keys, {'merges': {k: v[1] for k, v in merges.items()}}

    def scan_customer_merge_decisions_docx(self, p):
        rows = docx_appendix(p, ['merged_customer', 'surviving_customer', 'decision', 'decided_on'])
        keys = [r[0] for r in rows]
        merges = {}
        for r in rows:
            if norm_tok(r[2]) != 'APPROVED':
                continue
            m = norm_cust(r[0])
            s = norm_cust(r[1])
            d = parse_date(r[3])
            if m and s:
                if m not in merges or d > merges[m][0]:
                    merges[m] = (d, s)
        return keys, {'merges': {k: v[1] for k, v in merges.items()}}

    def scan_customer_master_db(self, p):
        tabs = sqlite_tables(p)
        keys = []
        alias = {}
        for r in tabs['customers']:
            keys.append(r['customer'])
        for r in tabs['customer_alias']:
            keys.append(r['alias'])
            a = norm_cust(r['alias'])
            m = norm_cust(r['master'])
            if a and m:
                alias[a] = m
        return keys, {'alias': alias}

    def scan_merge_candidates_ml_xlsx(self, p):
        data = xlsx_sheets(p)
        keys = []
        legacy = {}
        hdr, rows = data['legacy_refs']
        names = [str(x) for x in hdr]
        il = names.index('legacy_customer')
        ic = names.index('customer')
        for r in rows:
            keys.append(r[il])
            l = norm_key(r[il], 'LCU')
            c = norm_cust(r[ic])
            if l and c:
                legacy[l] = c
        hdr, rows = data['candidates']
        names = [str(x) for x in hdr]
        ia = names.index('customer_a')
        for r in rows:
            keys.append(r[ia])
        return keys, {'legacy_cust': legacy}

    def scan_employee_leavers_tsv(self, p):
        recs = text_records(p, '\t')
        keys = [r[h.index('employee_id')] for o, r, h in recs]
        lv = defaultdict(list)
        for o, r, h in recs:
            e = norm_id(r[h.index('employee_id')])
            d = parse_date(r[h.index('leave_date')])
            if e and d:
                lv[e].append(d)
        return keys, {'leavers': lv}

    def scan_exclusion_policy_docx(self, p):
        rows = docx_appendix(p, ['employee', 'customer', 'start_date'])
        keys = [r[0] for r in rows]
        st = defaultdict(list)
        for r in rows:
            e = norm_id(r[0])
            c = norm_cust(r[1])
            d = parse_date(r[2])
            if e and d:
                st[e].append((d, c))
        return keys, {'starts': st}

    def scan_limit_amendments_2025_xlsx(self, p):
        keys = []
        out = []
        ordinal = 0
        for sn, (hdr, rows) in xlsx_sheets(p).items():
            names = [str(x) for x in hdr]
            ii = names.index('amendment_id')
            ia = names.index('account')
            ie = names.index('effective_serial')
            il = names.index('new_limit')
            for r in rows:
                ordinal += 1
                keys.append(r[ia])
                out.append((ordinal, norm_id(r[ii]), norm_acct(r[ia]),
                            exceldate(r[ie]), r[il]))
        return keys, {'amendments': out}

    def scan_limit_management_policy_docx(self, p):
        rows = docx_appendix(p, ['amendment_id', 'account', 'effective', 'new_limit'])
        keys = [r[1] for r in rows]
        out = []
        for i, r in enumerate(rows, 1):
            out.append((i, norm_id(r[0]), norm_acct(r[1]), parse_date(r[2]), r[3]))
        return keys, {'amendments': out}

    def scan_product_migrations_2025_xlsx(self, p):
        hdr, rows = xlsx_sheets(p)['migrations']
        names = [str(x) for x in hdr]
        im = names.index('migration_id')
        ia = names.index('account')
        ifr = names.index('from_code')
        itc = names.index('to_code')
        ief = names.index('effective')
        keys = [r[ia] for r in rows]
        out = []
        for i, r in enumerate(rows, 1):
            d = r[ief]
            if not isinstance(d, datetime.date):
                d = parse_date(str(d))
            out.append((i, norm_id(r[im]), norm_acct(r[ia]), norm_tok(r[ifr]),
                        norm_tok(r[itc]), d))
        return keys, {'migrations': out}

    def scan_sampling_methodology_docx(self, p):
        rows = docx_appendix(p, ['account', 'inclusion_probability', 'status'])
        keys = [r[0] for r in rows]
        ov = {}
        for r in rows:
            if norm_tok(r[2]) != 'APPROVED':
                continue
            a = norm_acct(r[0])
            if a:
                ov[a] = r[1]
        return keys, {'overrides': ov}

    def scan_sampling_inclusion_gb_pl_se_yaml(self, p):
        return self._sampling(p)

    def scan_sampling_inclusion_cz_hu_ch_yaml(self, p):
        return self._sampling(p)

    def scan_sampling_inclusion_dk_no_yaml(self, p):
        return self._sampling(p)

    def scan_sampling_design_v2_yaml(self, p):
        return self._sampling(p)

    def _sampling(self, p):
        d = yaml_load(p)
        inc = d.get('inclusion') or []
        keys = [e['key'] for e in inc]
        entries = {}
        for e in inc:
            entries[sample_key(e['key'])] = parse_pi(e['pi'])
        return keys, {'entries': entries}

    def scan_bad_definition_standard_docx(self, p):
        rows = docx_appendix(p, ['grant', 'account', 'from_month', 'to_month'])
        keys = [r[0] for r in rows]
        grants = {}
        for r in rows:
            g = norm_id(r[0])
            a = norm_acct(r[1])
            fm = parse_month(r[2])
            tm = parse_month(r[3])
            if g and a and fm:
                grants[g] = (a, fm, tm)
        return keys, {'grants': grants}

    def scan_bad_definition_standard_v5_docx(self, p):
        rows = docx_appendix(p, ['grant', 'revoked_on', 'account', 'status'])
        keys = [r[0] for r in rows]
        revoked = set()
        for r in rows:
            if norm_tok(r[3]) != 'REVOKED':
                continue
            g = norm_id(r[0])
            if g:
                revoked.add(g)
        return keys, {'revoked': revoked}

    def scan_forbearance_extensions_register_pdf(self, p):
        rows = pdf_table(p, ['grant', 'new_to_month'])
        keys = [r[0] for r in rows]
        ext = {}
        for r in rows:
            g = norm_id(r[0])
            m = parse_month(r[1])
            if g and m:
                ext[g] = m if g not in ext else max(ext[g], m)
        return keys, {'extensions': ext}

    def scan_audit_label_confirmations_pdf(self, p):
        rows = pdf_table(p, ['account', 'audited_label'])
        keys = [r[0] for r in rows]
        aud = {}
        for r in rows:
            a = norm_acct(r[0])
            if a:
                aud[a] = norm_tok(r[1])
        return keys, {'audit': aud}

    def scan_consumer_redress_programme_pdf(self, p):
        rows = pdf_table(p, ['account', 'programme'])
        keys = [r[0] for r in rows]
        red = set()
        for r in rows:
            a = norm_acct(r[0])
            if a:
                red.add(a)
        return keys, {'redress': red}

    def scan_regulatory_exclusion_letter_2026_pdf(self, p):
        rows = pdf_table(p, ['account', 'notice_date'])
        keys = [r[0] for r in rows]
        ins = defaultdict(list)
        for r in rows:
            a = norm_acct(r[0])
            d = parse_date(r[1])
            if a and d:
                ins[a].append(d)
        return keys, {'insolvency': ins}

    def scan_model_registry_v4_toml(self, p):
        d = tomli.loads(read_text(p))
        runs = d.get('run', [])
        keys = [r['run_id'] for r in runs]
        return keys, {'runs': runs, 'approvals': d.get('approval', []),
                      'withdrawals': d.get('withdrawal', [])}

    def scan_scoring_runs_2025q2_toml(self, p):
        d = tomli.loads(read_text(p))
        runs = d.get('run', [])
        keys = [r['run_id'] for r in runs]
        return keys, {'runs': runs}

    def scan_model_registry_v4_1_toml(self, p):
        d = tomli.loads(read_text(p))
        pts = d.get('calibration_point', [])
        keys = [str(r['score']) for r in pts]
        return keys, {'points': pts, 'withdrawals': d.get('withdrawal', []),
                      'change_request': norm_id(d.get('change_request', '')),
                      'approvals': d.get('approval', [])}

    def scan_score_clock_skew_corrections_json(self, p):
        d = json.loads(read_text(p))
        runs = d['runs']
        keys = [r['run'] for r in runs]
        off = {}
        for r in runs:
            off[norm_id(r['run'])] = int(Decimal(str(r['offset_seconds'])))
        return keys, {'offsets': off}

    def scan_model_documentation_v4_pdf(self, p):
        rows = pdf_table(p, ['segment', 'score', 'pd'])
        keys = [r[1] for r in rows]
        grid = {}
        cuts = {}
        for r in rows:
            seg = norm_tok(r[0])
            sc = int(digits_int(r[1]))
            grid[(seg, sc)] = Decimal(r[2].replace(',', '.'))
        return keys, {'grid': grid}

    def scan_calibration_reissue_2026_pdf(self, p):
        rows = pdf_table(p, ['segment', 'score', 'pd'])
        keys = [r[1] for r in rows]
        grid = {}
        appb = {}
        for r in rows:
            seg = norm_tok(r[0])
            sc = int(digits_int(r[1]))
            if seg in SEGMENTS:
                appb[(seg, sc)] = Decimal(r[2].replace(',', '.'))
        return keys, {'appendixb': appb}

    def scan_governance_precedence_policy_docx(self, p):
        rows = docx_appendix(p, ['cr', 'subject', 'status', 'decided_on'])
        keys = [r[0] for r in rows]
        latest = {}
        for i, r in enumerate(rows):
            cr = norm_id(r[0])
            st = norm_tok(r[2])
            d = parse_date(r[3]) or datetime.date.min
            if cr not in latest or (d, i) > latest[cr][0]:
                latest[cr] = ((d, i), st)
        return keys, {'cr_status': {k: v[1] for k, v in latest.items()}}

    def scan_errata_register_md(self, p):
        rule = md_table(p, ['erratum', 'document', 'change', 'change request'])
        row = md_table(p, ['erratum', 'account', 'period', 'dpd', 'status', 'raised'])
        keys = [r[0] for r in row]
        return keys, {'rule': rule, 'row': row}

    def scan_monitoring_spec_v4_md(self, p):
        rows = md_table(p, ['segment', 'score', 'dev_count'])
        keys = [r[1] for r in rows]
        dev = defaultdict(dict)
        for r in rows:
            seg = norm_tok(r[0])
            sc = int(digits_int(r[1]))
            dev[seg][sc] = Decimal(r[2].replace(',', '.'))
        return keys, {'dev': dev}

    def scan_branch_directory_html(self, p):
        rows = [(r, h) for r, h in html_register_rows(p) if not h and len(r) >= 4]
        keys = [r[1] for r, h in rows]
        reg = defaultdict(list)
        for r, h in rows:
            market = norm_tok(r[0])
            branch = norm_id(r[1])
            vf = parse_date(r[2]) or datetime.date.min
            vt = parse_date(r[3]) if (r[3] and not r[3].lower().startswith('open')
                                      and not r[3].startswith('9999')) else None
            reg[branch].append((market, vf, vt))
        return keys, {'branches': reg}

    def scan_branch_directory_2026_html(self, p):
        rows = [(r, h) for r, h in html_register_rows(p) if not h and len(r) >= 2]
        keys = [r[0] for r, h in rows]
        recode = {}
        for r, h in rows:
            recode[norm_id(r[0])] = norm_id(r[1])
        return keys, {'recode': recode}

    def scan_litigation_hold_register_html(self, p):
        rows = [(r, h) for r, h in html_register_rows(p) if not h and len(r) >= 4]
        keys = [r[1] for r, h in rows]
        holds = defaultdict(list)
        for r, h in rows:
            a = norm_acct(r[1])
            f = parse_date(r[2]) or datetime.date.min
            t = parse_date(r[3]) if (r[3] and not r[3].lower().startswith('open')) else None
            if a:
                holds[a].append((f, t))
        return keys, {'holds': holds}

    def scan_market_holidays_ics(self, p):
        evs = ics_events(p)
        keys = [e.get('DTSTART', '')[:8] for e in evs]
        hols = defaultdict(set)
        for e in evs:
            m = norm_tok(e.get('X-MARKET', ''))
            cat = norm_tok(e.get('CATEGORIES', ''))
            ds = e.get('DTSTART', '')
            if len(ds) >= 8 and ds[:8].isdigit():
                d = datetime.date(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))
                hols[(m, d)].add(cat)
        return keys, {'holidays': hols}

    def scan_currency_redenomination_ini(self, p):
        sec, order = ini_sections(p)
        keys = list(order.get('REDENOMINATED', []))
        red = {}
        for k in keys:
            v = sec[('REDENOMINATED', k)]
            a = norm_acct(k)
            if a:
                red[a] = norm_tok(v)
        return keys, {'redenominated': red}

    def scan_legacy_account_map_ini(self, p):
        sec, order = ini_sections(p)
        keys = list(order.get('LEGACY_ACCOUNTS', []))
        lmap = {}
        for k in keys:
            v = sec[('LEGACY_ACCOUNTS', k)]
            kk = norm_id(k)
            if kk.startswith('L'):
                lmap[kk] = norm_acct(v)
        return keys, {'legacy': lmap}

    def scan_product_code_crosswalk_ini(self, p):
        sec, order = ini_sections(p)
        keys = []
        cross = {}
        for s in SEGMENTS:
            for k in order.get(s.upper(), []):
                keys.append(k)
                cross[norm_tok(k)] = s
        return keys, {'crosswalk': cross}

    def scan_delivery_manifest_json(self, p):
        o = json.loads(read_text(p))
        keys = [d['delivery_id'] for d in o['deliveries']]
        return keys, {}

    def scan_data_quality_issue_log_md(self, p):
        rows = md_table(p, ['issue', 'delivery', 'record', 'disposition', 'note'])
        keys = [r[0] for r in rows]
        return keys, {}

    def scan_snapshots_servicing_replica_db(self, p):
        tabs = sqlite_tables(p)
        keys = []
        for tn in sorted(tabs):
            for r in tabs[tn]:
                if tn.startswith('snap_'):
                    keys.append(r['account'])
                else:
                    keys.append(str(int(str(r['value'])) % 10000000))
        return keys, {}


def sample_key(k):
    """Normalise an inclusion register key (account key or application id)."""
    if k is None:
        return None
    t = _WS.sub('', str(k)).upper().replace('\u0410', 'A').replace('\u0421', 'C').replace('-', '')
    if t.startswith('APP'):
        return t
    a = norm_acct(k)
    return a if a else t


def norm_period(s):
    if s is None:
        return None
    if isinstance(s, datetime.datetime):
        return '%04d-%02d' % (s.year, s.month)
    if isinstance(s, datetime.date):
        return '%04d-%02d' % (s.year, s.month)
    t = str(s).strip()
    if re.fullmatch(r'\d{6}', t):
        return '%04d-%02d' % (int(t[:4]), int(t[4:6]))
    return parse_month(t)

def parse_pi(s):
    """Inclusion probability (sampling methodology 2.2)."""
    if s is None:
        return None
    t = str(s).strip()
    if t == '':
        return None
    m = re.fullmatch(r'(\d+(?:\.\d+)?(?:[Ee][+-]\d+)?)\s*/\s*(\d+(?:\.\d+)?)', t)
    if m:
        return Decimal(m.group(1)) / Decimal(m.group(2))
    pct = False
    if t.endswith('%'):
        pct = True
        t = t[:-1].strip()
    m = re.fullmatch(r'([+-]?\d+(?:[.,]\d+)?(?:[Ee][+-]\d+)?)', t)
    if not m:
        return None
    v = Decimal(m.group(1).replace(',', '.'))
    if pct:
        v = v / 100
    return v

def email_date(s):
    """RFC 2822 date header -> naive UTC datetime."""
    if not s:
        return datetime.datetime.min
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(s)
    except Exception:
        return datetime.datetime.min
    if dt.tzinfo is not None:
        dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return dt


# ------------------------------------------------------------------ pipeline

def load_dq(engine):
    """Quarantined record ordinals per delivery (spec 2.2 and the issue log)."""
    rows = md_table(engine.est.path('data_quality_issue_log.md'),
                    ['issue', 'delivery', 'record', 'disposition', 'note'])
    for r in rows:
        if norm_tok(r[3]) != 'QUARANTINE':
            continue
        name = r[1].strip().lower()
        try:
            ordinal = int(r[2])
        except ValueError:
            continue
        engine.quarantine[name].add(ordinal)


def scan_all(engine):
    load_dq(engine)
    order = [d['file'] for d in engine.est.deliveries]
    for name in order:
        if name == 'delivery_manifest.json':
            engine.scan(name)
            continue
        engine.scan(name)
    # controls
    for d in engine.est.deliveries:
        engine.controls[d['delivery_id']] = _lower(read_control(engine.est, d['file'])) or {}


def reconcile(engine):
    failed = []
    for d in engine.est.deliveries:
        did = d['delivery_id']
        c = engine.controls.get(did) or {}
        ok = True
        ro = c.get('ack_rows_of')
        ho = c.get('ack_hash_of')
        wr = as_int(c.get('ack_rows'))
        wh = as_int(c.get('ack_hash'))
        if ro is None or wr is None or engine.counts.get(ro) != wr:
            ok = False
        if ho is None or wh is None or engine.hashes.get(ho) != wh:
            ok = False
        if not ok:
            failed.append(did)
    missing = [d['file'] for d in engine.est.deliveries
               if not os.path.exists(engine.est.path(d['file']))]
    return {
        'files_checked': engine.files_read,
        'failed_controls': sorted(failed),
        'estate_record_total': sum(engine.counts.values()),
        'estate_hash_total': sum(engine.hashes.values()),
        'reconciled': not failed and not missing and
                      engine.files_read == len(engine.est.deliveries),
    }


class Acct:
    __slots__ = ('acct', 'customer', 'rcust', 'branch', 'market', 'segment', 'product',
                 'app_id', 'decision_utc', 'decision_date', 'cohort_month', 'limit',
                 'weight', 'exposure', 'score', 'score_band', 'event_id', 'run_id',
                 'model_version', 'score_ts', 'bad', 'outcome', 'reason', 'window_start',
                 'window_end_month', 'window_end', 'months_observed', 'max_dpd',
                 'bad_month', 'closure_dates')


def build_cohort(engine):
    est = engine.est
    d = engine.d

    # ---- branch directories
    branches = d['branch_directory.html']['branches']
    recode = d['branch_directory_2026.html']['recode']

    def market_of(branch, on_date):
        b = recode.get(branch, branch)
        best = None
        for market, vf, vt in branches.get(b, []):
            if on_date >= vf and (vt is None or on_date <= vt):
                best = market
        return best

    cross = d['product_code_crosswalk.ini']['crosswalk']
    migrations = d['product_migrations_2025.xlsx']['migrations']
    mig_by_acct = defaultdict(list)
    for _o, mid, acct, fcode, tcode, eff in migrations:
        if acct:
            mig_by_acct[acct].append((eff, mid, fcode, tcode))
    for k in mig_by_acct:
        mig_by_acct[k].sort(key=lambda x: (x[0] or datetime.date.min, x[1]))

    # ---- applications
    parts = ['applications_2025_01.csv', 'applications_2025_02.tsv', 'applications_2025_03.txt',
             'applications_2025_04.csv', 'applications_2025_05.xlsx', 'applications_2025_06.jsonl']
    best = {}
    for name in parts:
        payload = d.get(name)
        if not payload:
            continue
        delivered = payload['delivered']
        for rec in payload['records']:
            (ordinal, app_id, acct_raw, cust_raw, branch_raw, prod_raw,
             utc_raw, local_raw, is_local, limit_raw, rev_raw, recv_raw) = rec
            acct = norm_acct(acct_raw)
            if acct is None:
                continue
            rev = int(Decimal(str(rev_raw).strip() or '0'))
            if utc_raw is not None:
                utc = parse_utc(str(utc_raw))
            else:
                utc = None
                if isinstance(local_raw, datetime.datetime):
                    local = local_raw
                else:
                    local = parse_dt_local(str(local_raw))
                if local is None:
                    continue
            if isinstance(recv_raw, datetime.datetime):
                recv = recv_raw
            else:
                recv = parse_utc(str(recv_raw)) or datetime.datetime.min
            limit = parse_amount(limit_raw)
            if limit is None:
                limit = Decimal(0)
            limit = round_cents(limit)
            key = (rev, recv, delivered, ordinal)
            cur = best.get(acct)
            if cur is None or key > cur[0]:
                best[acct] = (key, dict(
                    acct=acct, customer=norm_cust(cust_raw), branch=norm_id(branch_raw),
                    product=norm_tok(prod_raw), app_id=norm_id(app_id) if app_id else None,
                    utc=utc, local=local, is_local=is_local, limit=limit))
    # April application ids come from the re-extract (governance 3.7)
    appid = d.get('applications_2025_04_reextract.csv', {}).get('appid', {})
    for a, v in appid.items():
        if a in best and best[a][1]['app_id'] is None:
            best[a][1]['app_id'] = v

    # withdrawal reversals (governance 3.6)
    reversed_flags = d.get('applications_master_2025h1.parquet', {}).get('reversed', {})

    accounts = {}
    for acct, (key, info) in best.items():
        a = Acct()
        a.acct = acct
        a.customer = info['customer']
        a.branch = info['branch']
        a.product = info['product']
        a.app_id = info['app_id'] or None
        a.limit = info['limit']
        if info['is_local']:
            local = info['local']
            date = local.date()
            mkt = market_of(a.branch, date)
            a.market = mkt
            if mkt is None:
                continue
            a.decision_date = date
            a.decision_utc = local_to_utc(local, mkt)
        else:
            utc = info['utc']
            if utc is None:
                continue
            date = utc.date()
            mkt = market_of(a.branch, date)
            a.market = mkt
            if mkt is None:
                continue
            a.decision_utc = utc
            a.decision_date = utc_to_local(utc, mkt).date()
        if a.decision_date < COHORT_FIRST or a.decision_date >= COHORT_LAST:
            a.reason = 'WINDOW'
        else:
            a.reason = None
        a.cohort_month = '%04d-%02d' % (a.decision_date.year, a.decision_date.month)
        accounts[acct] = a

    # ---- resolved customers
    alias = d.get('customer_master.db', {}).get('alias', {})
    merges = {}
    for src in ('customer_merge_decisions.docx', 'customer_merges_2026.tsv'):
        for k, v in d.get(src, {}).get('merges', {}).items():
            merges[k] = v
    legacy_cust = d.get('merge_candidates_ml.xlsx', {}).get('legacy_cust', {})

    def resolve(cu):
        if cu is None:
            return None
        x = cu
        if x in legacy_cust:
            x = legacy_cust[x]
        seen = set()
        while True:
            if x in alias and x not in seen:
                seen.add(x)
                x = alias[x]
            elif x in merges and x not in seen:
                seen.add(x)
                x = merges[x]
            else:
                return x

    for a in accounts.values():
        a.rcust = resolve(a.customer)

    # ---- product at decision (spec 3.4)
    for a in accounts.values():
        code = a.product
        cands = mig_by_acct.get(a.acct)
        if cands and a.product is not None:
            for eff, mid, fcode, tcode in cands:
                if eff and eff > a.decision_date:
                    code = fcode
                    break
        a.segment = cross.get(norm_tok(code)) if code else None
    return accounts


def parse_dt_local(s):
    s = str(s).strip()
    m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})', s)
    if m:
        return datetime.datetime(*(int(x) for x in m.groups()))
    m = re.fullmatch(r'(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})', s)
    if m:
        return datetime.datetime(*(int(x) for x in m.groups()))
    return None



# ------------------------------------------------------------------ scores

def build_scores(engine, accounts):
    d = engine.d
    runs = {}
    for src in ('model_registry_v4.toml', 'scoring_runs_2025q2.toml'):
        for r in d.get(src, {}).get('runs', []):
            runs[norm_id(r['run_id'])] = (norm_id(str(r.get('node'))),
                                          norm_tok(r.get('model')),
                                          norm_tok(r.get('status')))
    voids = set()
    for name in ('scoring_engine_node1.log', 'scoring_engine_node2.log',
                 'scoring_engine_node3.log', 'scoring_engine_node4.log',
                 'scoring_engine_node9.log'):
        voids |= d.get(name, {}).get('voids', set())
    offsets = d.get('score_clock_skew_corrections.json', {}).get('offsets', {})
    cr_status = d.get('governance_precedence_policy.docx', {}).get('cr_status', {})
    approvals = []
    for a in d.get('model_registry_v4.toml', {}).get('approvals', []):
        eff = a['effective_from'] if isinstance(a['effective_from'], datetime.date) \
            else parse_date(str(a['effective_from']))
        approvals.append((norm_tok(a['model']), {norm_tok(s) for s in a.get('segments', [])}, eff))
    withdrawals = []
    for src in ('model_registry_v4.toml', 'model_registry_v4_1.toml'):
        for w in d.get(src, {}).get('withdrawals', []):
            cr = norm_id(w.get('change_request', ''))
            if cr and cr_status.get(cr) != 'APPROVED':
                continue
            wd = w.get('withdrawn_from')
            if isinstance(wd, datetime.datetime):
                wd = wd.date()
            if not isinstance(wd, datetime.date):
                wd = parse_date(str(wd))
            if wd is None:
                continue
            withdrawals.append((norm_tok(w.get('model')), wd))

    def approved(model, segment, on_date):
        ok = False
        for m, segs, eff in approvals:
            if m == model and segment in segs and eff is not None and on_date >= eff:
                ok = True
        if not ok:
            return False
        for m, wd in withdrawals:
            if m == model and on_date >= wd:
                return False
        return True

    by_acct = defaultdict(list)
    for name in ('score_events_backfill.csv', 'score_events_node5.parquet',
                 'score_events_node6.xml', 'score_events_node7.tsv',
                 'score_batches_2025_q1.jsonl', 'score_batches_2025_q2_a.jsonl',
                 'score_batches_2025_q2_b.jsonl', 'score_batches_2025_q2_c.jsonl',
                 'scoring_engine_node1.log', 'scoring_engine_node2.log',
                 'scoring_engine_node3.log', 'scoring_engine_node4.log'):
        for acct, eid, run, ts, score in d.get(name, {}).get('events', []):
            if ts is None:
                continue
            by_acct[acct].append((eid, run, ts, score))

    for acct, a in accounts.items():
        a.score = None
        a.event_id = a.run_id = a.model_version = a.score_ts = None
        if a.reason not in (None, 'WINDOW'):
            continue
        if a.segment is None:
            continue
        best = None
        for eid, run, ts, score in by_acct.get(acct, []):
            r = runs.get(run)
            if r is None:
                continue                      # 6.1 run not registered
            node, model, status = r
            if status != 'OK':
                continue                      # 6.2 run status not OK
            if run in voids:
                continue                      # 6.2 run voided
            if node == '9':
                continue                      # 6.2 node 9
            if not approved(model, a.segment, a.decision_date):
                continue                      # 6.3 approval and withdrawal
            corrected = ts + datetime.timedelta(seconds=offsets.get(run, 0))
            if corrected > a.decision_utc:
                continue                      # 6.4 point in time
            key = (corrected, digits_int(eid), eid)
            if best is None or key > best[0]:
                best = (key, eid, run, model, corrected, score)
        if best is not None:
            a.score = best[5]
            a.event_id = best[1]
            a.run_id = best[2]
            a.model_version = best[3]
            a.score_ts = best[4]


# ------------------------------------------------------------------ snapshots

DPD_NOT_REPORTED = {'', 'N/A', 'NA', 'NULL', 'NONE', 'NAN', '9999', '-1', 'NR', 'NOT REPORTED'}


def parse_dpd(v):
    if v is None:
        return None
    if isinstance(v, int):
        return None if v in (-1, 9999) else v
    if isinstance(v, float):
        v = repr(v)
    t = str(v).strip().replace('\u00a0', '').replace('+', '')
    if t.upper() in DPD_NOT_REPORTED or t == '':
        return None
    if not re.fullmatch(r'[-+]?\d+', t):
        return None
    n = int(t)
    if n in (-1, 9999):
        return None
    return n


def build_snapshots(engine, accounts):
    """(acct, period) -> (dpd, written_off) from the certified deliveries (spec 5)."""
    est = engine.est
    d = engine.d
    snap = {}
    for part in est.certified:
        name = part['file']
        markets = {norm_tok(m) for m in part.get('markets', [])}
        payload = d.get(name)
        if payload is None:
            continue
        for acct, per, dpd, status in payload.get('records', []):
            if acct is None or per is None:
                continue
            a = accounts.get(acct)
            if a is None or a.market is None or a.market not in markets:
                continue                     # 5.1 outside the certified market scope
            snap[(acct, per)] = (parse_dpd(dpd), norm_tok(status) in ('W', 'S', 'CO'))
    return snap


def build_corrections(engine):
    """DPD corrections with the precedence of the governance policy section 2."""
    d = engine.d
    errata = {}
    for r in d.get('errata_register.md', {}).get('row', []):
        if norm_tok(r[4]) != 'APPLIED':
            continue
        a = norm_acct(r[1])
        per = norm_period(r[2])
        raised = parse_date(r[5]) or datetime.date.min
        dpd = parse_dpd(r[3])
        if a and per:
            k = (a, per)
            cur = errata.get(k)
            if cur is None or (raised, norm_id(r[0])) > cur[0]:
                errata[k] = ((raised, norm_id(r[0])), dpd)
    errata = {k: v[1] for k, v in errata.items()}
    feed = d.get('snapshot_corrections_feed.xml', {}).get('corrections', {})
    mbox = d.get('ops_corrections.mbox', {}).get('corrections', {})
    system_error = set(d.get('snapshots_2025_10_b_restated.tsv', {}).get('system_error', []))
    return errata, feed, mbox, system_error


def month_eff(snap, corr, acct, period, forbear):
    """(effective dpd, written off, valid) for one account month."""
    key = (acct, period)
    if key not in snap:
        return None, False, False
    dpd, wo = snap[key]
    e, feed, mbox, system_error = corr
    if key in e:
        dpd = e[key]
    elif key in feed:
        dpd = feed[key]
    elif key in mbox:
        dpd = mbox[key]
    elif key in system_error:
        dpd = 0
    valid = dpd is not None
    eff = dpd
    if eff == 999:                        # 2.3 written-off sentinel
        eff = 180
        wo = True
    elif eff is not None and forbear:      # 3 forborne month
        eff = 0
    return eff, wo, valid


# ------------------------------------------------------------------ outcomes

def build_outcomes(engine, accounts):
    d = engine.d
    snap = engine.snap
    corr = engine.corr

    # forbearance grants, extensions and revocations
    grants = d.get('bad_definition_standard.docx', {}).get('grants', {})
    extensions = d.get('forbearance_extensions_register.pdf', {}).get('extensions', {})
    revoked = d.get('bad_definition_standard_v5.docx', {}).get('revoked', set())
    forbear = defaultdict(set)
    for g, (acct, fm, tm) in grants.items():
        if g in revoked:
            continue
        tm = extensions.get(g, tm)
        if tm is None:
            continue
        y1, m1 = int(fm[:4]), int(fm[5:7])
        y2, m2 = int(tm[:4]), int(tm[5:7])
        t = y1 * 12 + m1
        end = y2 * 12 + m2
        while t <= end:
            forbear[acct].add('%04d-%02d' % (t // 12, t % 12 + 1))
            t += 1

    # charge-offs and reversals
    legacy = d.get('legacy_account_map.ini', {}).get('legacy', {})
    co = defaultdict(list)
    for _o, eid, acct_raw, date in d.get('status_events_chargeoff_2025.csv', {}).get('chargeoffs', []):
        a = canonical_acct(acct_raw, legacy)
        if a and date:
            co[a].append((eid, date))
    for _o, eid, acct_raw, date in d.get('chargeoff_events_2026.parquet', {}).get('chargeoffs', []):
        a = canonical_acct(acct_raw, legacy)
        if a and date:
            co[a].append((eid, date))
    reversals = d.get('status_events_consolidated.json', {}).get('reversals', {})

    # DPD thresholds (bad definition 2.1 with the approved errata)
    threshold = {s: 90 for s in SEGMENTS}
    for r in d.get('errata_register.md', {}).get('rule', []):
        cr = norm_id(r[3])
        if d.get('governance_precedence_policy.docx', {}).get('cr_status', {}).get(cr) != 'APPROVED':
            continue
        change = r[2]
        m = re.search(r'the DPD threshold for ([A-Z]+) is (\d+)', change)
        if m:
            threshold[norm_tok(m.group(1))] = int(m.group(2))

    # cut points (model documentation as amended by approved errata)
    cuts = score_cuts(engine)

    for acct, a in accounts.items():
        c = a.cohort_month
        a.window_start = month_add(c, 1)
        a.window_end_month = month_add(c, 12)
        a.window_end = month_end(a.window_end_month)
        a.outcome = None
        a.months_observed = 0
        a.max_dpd = 0
        a.bad_month = None
        a.score_band = None
        if a.reason:
            continue
        thr = threshold.get(a.segment, 90)
        months = [month_add(c, i) for i in range(1, 13)]
        eff = {}
        valid = set()
        woff = set()
        for per in months:
            fb = per in forbear.get(acct, ())
            e, wo, v = month_eff(snap, corr, acct, per, fb)
            if v:
                eff[per] = e if e is not None else 0
                valid.add(per)
            if wo:
                woff.add(per)
        a.months_observed = len(valid)
        a.max_dpd = max([eff[p] for p in valid] or [0])
        # bad months (bad definition 2.2)
        bad_month = None
        for per in months:
            if per not in valid:
                continue
            if per in woff:
                bad_month = per
                break
            if eff[per] >= thr:
                bad_month = per
                break
        chargeoff_bad = False
        for eid, cdate in co.get(acct, []):
            if not (a.decision_date < cdate <= a.window_end):
                continue
            revs = reversals.get(eid, [])
            if any(cdate <= r <= cdate + datetime.timedelta(days=60) for r in revs):
                continue
            chargeoff_bad = True
            break
        if bad_month is not None or chargeoff_bad:
            a.outcome = 'BAD'
            a.bad_month = bad_month
        else:
            a.bad_month = None
        # required months (bad definition 4)
        closures = a.closure_dates or []
        earliest = min(closures) if closures else None
        if earliest is not None:
            req_end = min(months[-1], '%04d-%02d' % (earliest.year, earliest.month))
        else:
            req_end = months[-1]
        required = []
        for per in months:
            if per > req_end:
                break
            required.append(per)
        if a.outcome != 'BAD':
            missing = any(per not in valid for per in required)
            if missing:
                a.outcome = 'CENSORED'
            elif earliest is not None and earliest < month_first(month_add(c, 6)):
                a.outcome = 'INSUFFICIENT'
            elif a.max_dpd >= 30:
                a.outcome = 'INDETERMINATE'
            else:
                a.outcome = 'GOOD'
        a.score_band = band_of(cuts, a.segment, a.score) if a.score is not None else None


def canonical_acct(raw, legacy):
    a = norm_acct(raw)
    if a is not None:
        return a
    k = norm_id(raw)
    if k.startswith('L'):
        return legacy.get(k)
    return None


def month_first(ym):
    return datetime.date(int(ym[:4]), int(ym[5:7]), 1)


def score_cuts(engine):
    """Score band cut points per segment (model documentation with approved errata)."""
    cuts = {}
    rows = []
    p = engine.est.path('model_documentation_v4.pdf')
    want = ['segment', 'c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c8', 'c9']
    keys = [norm_tok(x) for x in want]
    active = False
    for line in pdf_text_lines(p):
        if '|' not in line:
            continue
        parts = [x.strip() for x in line.split('|')]
        if parts and parts[0] == '':
            parts = parts[1:]
        if parts and parts[-1] == '':
            parts = parts[:-1]
        if [norm_tok(x) for x in parts] == keys:
            active = True
            continue
        if not active or len(parts) != len(want):
            continue
        rows.append(parts)
    for r in rows:
        seg = norm_tok(r[0])
        cuts[seg] = [int(x) for x in r[1:]]
    for er in engine.d.get('errata_register.md', {}).get('rule', []):
        cr = norm_id(er[3])
        if engine.d.get('governance_precedence_policy.docx', {}).get('cr_status', {}).get(cr) != 'APPROVED':
            continue
        m = re.search(r'([A-Z]+) cut point c(\d) reads (\d+); the correct value is (\d+)', er[2])
        if m:
            seg = norm_tok(m.group(1))
            idx = int(m.group(2)) - 1
            if seg in cuts:
                cuts[seg][idx] = int(m.group(4))
    return cuts


def band_of(cuts, segment, score):
    c = cuts.get(segment)
    if not c:
        return None
    for i, cut in enumerate(c):
        if score <= cut:
            return i + 1
    return 10


# ------------------------------------------------------------------ exclusions

EXCLUSION_ORDER = ['WINDOW', 'WITHDRAWN', 'DUPLICATE', 'NO_SCORE', 'STAFF', 'LEGAL_HOLD',
                   'INSOLVENCY', 'REDRESS', 'DECEASED', 'FRAUD', 'CENSORED', 'INSUFFICIENT',
                   'INDETERMINATE']


def apply_exclusions(engine, accounts):
    d = engine.d
    # WITHDRAWN (spec 3.5)
    wd = d.get('application_withdrawals.json', {}).get('withdrawals', {})
    reversed_flags = d.get('applications_master_2025h1.parquet', {}).get('reversed', {})
    for acct, a in accounts.items():
        if a.reason:
            continue
        hit = False
        for date in wd.get(acct, ()):
            if 0 <= (date - a.decision_date).days <= 14:
                if reversed_flags.get(acct):
                    continue
                hit = True
                break
        if hit:
            a.reason = 'WITHDRAWN'

    # DUPLICATE (spec 3.6)
    groups = defaultdict(list)
    for acct, a in accounts.items():
        if a.reason or a.reason == 'WINDOW':
            continue
        if a.rcust is None or a.segment is None:
            continue
        groups[(a.rcust, a.segment)].append(a)
    for key, group in groups.items():
        group.sort(key=lambda a: (a.decision_utc, a.acct))
        last = None
        for a in group:
            if last is None:
                last = a
                continue
            if (a.decision_date - last.decision_date).days <= 30:
                a.reason = 'DUPLICATE'
            else:
                last = a

    # NO_SCORE (spec 6.4)
    for acct, a in accounts.items():
        if a.reason:
            continue
        if a.score is None:
            a.reason = 'NO_SCORE'

    # STAFF (exclusion policy 2.1)
    starts = d.get('exclusion_policy.docx', {}).get('starts', {})
    leavers = d.get('employee_leavers.tsv', {}).get('leavers', {})
    employed = defaultdict(list)       # resolved customer -> list of (start, end_exclusive)
    for emp, entries in starts.items():
        leaves = sorted(leavers.get(emp, []))
        entries = sorted(entries, key=lambda x: x[0])
        used = []
        for sdate, cust in entries:
            end = None
            for lv in leaves:
                if lv > sdate and lv not in used:
                    end = lv
                    used.append(lv)
                    break
            rc = engine.resolve(cust)
            if rc:
                employed[rc].append((sdate, end))
    for acct, a in accounts.items():
        if a.reason or a.rcust is None:
            continue
        for sdate, end in employed.get(a.rcust, ()):
            if a.decision_date >= sdate and (end is None or a.decision_date < end):
                a.reason = 'STAFF'
                break

    # LEGAL_HOLD (exclusion policy 2.2, erratum E-011)
    holds = d.get('litigation_hold_register.html', {}).get('holds', {})
    for acct, a in accounts.items():
        if a.reason:
            continue
        for f, t in holds.get(acct, ()):
            if a.decision_date >= f and (t is None or a.decision_date <= t):
                a.reason = 'LEGAL_HOLD'
                break

    # INSOLVENCY (exclusion policy 2.3)
    ins = d.get('regulatory_exclusion_letter_2026.pdf', {}).get('insolvency', {})
    for acct, a in accounts.items():
        if a.reason:
            continue
        for ndate in ins.get(acct, ()):
            if ndate <= a.window_end:
                a.reason = 'INSOLVENCY'
                break

    # REDRESS (exclusion policy 2.4)
    red = d.get('consumer_redress_programme.pdf', {}).get('redress', set())
    for acct, a in accounts.items():
        if a.reason:
            continue
        if acct in red:
            a.reason = 'REDRESS'

    # DECEASED (exclusion policy 2.5)
    dec = {}
    for src in ('deceased_notifications_register.pdf', 'deceased_notifications_feed.xml',
                'status_events_consolidated.json'):
        for c, date in d.get(src, {}).get('deceased', {}).items():
            if c not in dec or date < dec[c]:
                dec[c] = date
    for acct, a in accounts.items():
        if a.reason or a.rcust is None:
            continue
        date = dec.get(a.rcust)
        if date is not None and date <= a.window_end:
            a.reason = 'DECEASED'

    # FRAUD (exclusion policy 2.6)
    disp = d.get('fraud_case_dispositions.json', {}).get('dispositions', {})
    alerts = defaultdict(list)
    for src in ('fraud_alerts_2025.jsonl', 'fraud_alerts_2026.xml'):
        for case, acct, date in d.get(src, {}).get('alerts', []):
            if acct and date:
                alerts[acct].append((case, date))
    for acct, a in accounts.items():
        if a.reason:
            continue
        for case, date in alerts.get(acct, ()):
            if disp.get(case) == 'CONFIRMED' and date <= a.window_end:
                a.reason = 'FRAUD'
                break

    # CENSORED / INSUFFICIENT / INDETERMINATE (bad definition standard 4)
    for acct, a in accounts.items():
        if a.reason:
            continue
        if a.outcome in ('CENSORED', 'INSUFFICIENT', 'INDETERMINATE'):
            a.reason = a.outcome

    # cohort accounts: BAD or GOOD
    for acct, a in accounts.items():
        if not a.reason:
            if a.outcome not in ('BAD', 'GOOD'):
                a.reason = a.outcome
    # final bad flag after audit overrides (bad definition standard 5)
    audit = d.get('audit_label_confirmations.pdf', {}).get('audit', {})
    for acct, a in accounts.items():
        if a.reason:
            a.bad = 0
            continue
        if acct in audit:
            a.bad = 1 if audit[acct] == 'BAD' else 0
        else:
            a.bad = 1 if a.outcome == 'BAD' else 0


# ------------------------------------------------------------------ weights and exposure

MARKET_CURRENCY = {'GB': 'GBP', 'PL': 'PLN', 'SE': 'SEK', 'CZ': 'CZK', 'HU': 'HUF',
                   'CH': 'CHF', 'DK': 'DKK', 'NO': 'NOK'}

MARKET_GROUP = {'GB': 'sampling_inclusion_gb_pl_se.yaml',
                'PL': 'sampling_inclusion_gb_pl_se.yaml',
                'SE': 'sampling_inclusion_gb_pl_se.yaml',
                'CZ': 'sampling_inclusion_cz_hu_ch.yaml',
                'HU': 'sampling_inclusion_cz_hu_ch.yaml',
                'CH': 'sampling_inclusion_cz_hu_ch.yaml',
                'DK': 'sampling_inclusion_dk_no.yaml',
                'NO': 'sampling_inclusion_dk_no.yaml'}


def build_weights(engine, accounts):
    d = engine.d
    overrides = d.get('sampling_methodology.docx', {}).get('overrides', {})
    regs = {}
    for name in MARKET_GROUP.values():
        regs[name] = d.get(name, {}).get('entries', {})
    design_v2 = d.get('sampling_design_v2.yaml', {}).get('entries', {})
    missing = []
    for acct, a in accounts.items():
        pi = None
        if a.cohort_month == '2025-06':
            pi = design_v2.get(sample_key(acct))
        else:
            reg = regs.get(MARKET_GROUP.get(a.market, ''))
            key = sample_key(a.app_id) if a.cohort_month == '2025-04' else sample_key(acct)
            if reg:
                pi = reg.get(key)
        if acct in overrides:
            pi = parse_pi(overrides[acct])
        if pi is None or pi == 0:
            missing.append(acct)
            a.weight = None
        else:
            w = Decimal(1) / pi
            a.weight = int(w.to_integral_value(rounding=ROUND_HALF_UP))
    return missing


def build_exposure(engine, accounts):
    d = engine.d
    amendments = defaultdict(list)
    for src in ('limit_amendments_2025.xlsx', 'limit_management_policy.docx'):
        for _o, aid, acct, eff, new_limit in d.get(src, {}).get('amendments', []):
            if acct is None or eff is None:
                continue
            amendments[acct].append((eff, aid, parse_amount(new_limit)))
    red = d.get('currency_redenomination.ini', {}).get('redenominated', {})
    iso = d.get('fx_rates_ecb_mirror.xml', {}).get('iso', {})
    fixings = d.get('treasury_fixings_2024_2026.xml', {}).get('fixings', {})
    hols = d.get('market_holidays.ics', {}).get('holidays', {})
    for acct, a in accounts.items():
        limit = a.limit
        month_last = month_end(a.cohort_month)
        cands = [x for x in amendments.get(acct, []) if a.decision_date <= x[0] <= month_last]
        if cands:
            cands.sort(key=lambda x: (x[0], x[1]))
            v = cands[-1][2]
            if v is not None:
                limit = v
        if limit is None:
            limit = Decimal(0)
        limit = round_cents(limit)
        ccy = MARKET_CURRENCY.get(a.market)
        num = red.get(acct)
        if num is not None:
            ccy = iso.get(num) or ccy
        if ccy is None:
            a.exposure = round_cents(limit)
            continue
        fdate = last_business_day(engine, a.market, month_last, hols)
        best = None
        table = fixings.get(ccy, {})
        for date in sorted(table):
            if date <= fdate:
                best = table[date]
            else:
                break
        if best is None:
            a.exposure = round_cents(limit)
            continue
        _, val, per = best
        a.exposure = round_cents(limit * val / per)


def last_business_day(engine, market, month_last, hols):
    d = month_last
    while True:
        if d.weekday() >= 5:
            d -= datetime.timedelta(days=1)
            continue
        cats = hols.get((norm_tok(market), d), set())
        if 'PUBLIC-HOLIDAY' in cats or 'BANK-CLOSURE' in cats:
            d -= datetime.timedelta(days=1)
            continue
        return d


# ------------------------------------------------------------------ metrics

def cohort_accounts(accounts):
    return [a for a in accounts.values() if not a.reason]


def population_metrics(cohort):
    segs = {}
    for seg in SEGMENTS + ['ALL']:
        rows = [a for a in cohort if seg == 'ALL' or a.segment == seg]
        accounts_n = len(rows)
        bads = sum(1 for a in rows if a.bad)
        wacc = sum(a.weight for a in rows)
        wbad = sum(a.weight for a in rows if a.bad)
        expo = sum((a.weight * a.exposure for a in rows), Decimal(0))
        expo_bad = sum((a.weight * a.exposure for a in rows if a.bad), Decimal(0))
        segs[seg] = {
            'accounts': accounts_n,
            'bads': bads,
            'weighted_accounts': wacc,
            'weighted_bads': wbad,
            'bad_rate': f6(Decimal(wbad) / Decimal(wacc)) if wacc else f6(Decimal(0)),
            'exposure_eur': f2(expo),
            'exposure_bad_rate': f6(expo_bad / expo) if expo else f6(Decimal(0)),
        }
    return segs


def discrimination(cohort, cuts):
    out = {}
    for seg in SEGMENTS + ['ALL']:
        rows = [a for a in cohort if seg == 'ALL' or a.segment == seg]
        goods = [(a.score, a.weight) for a in rows if not a.bad]
        bads = [(a.score, a.weight) for a in rows if a.bad]
        wg = sum(w for _s, w in goods)
        wb = sum(w for _s, w in bads)
        if not goods or not bads or wg == 0 or wb == 0:
            out[seg] = {'auc': f6(Decimal(0)), 'gini': f6(Decimal(0)),
                        'ks': f6(Decimal(0)), 'ks_score': 0}
            continue
        gs = defaultdict(Decimal)
        bs = defaultdict(Decimal)
        for s, w in goods:
            gs[s] += w
        for s, w in bads:
            bs[s] += w
        scores = sorted(set(gs) | set(bs))
        # auc = sum over bad i, good j of w_i w_j ([s_j > s_i] + 0.5 [s_j = s_i]) / (Wb Wg)
        g_ge = Decimal(0)     # weight of goods with score >= t
        b_lt = Decimal(0)    # weight of bads with score < t
        auc_num = Decimal(0)
        g_gt = sum(gs[s] for s in gs)  # placeholder
        g_gt = Decimal(0)
        for s in scores:
            # contributions where good score equals bad score
            auc_num += Decimal('0.5') * gs[s] * bs[s]
            auc_num += gs[s] * b_lt            # goods at s beat bads below s
            b_lt += bs[s]
        auc = auc_num / (wg * wb)
        gini = 2 * auc - 1
        # ks: weighted cumulative shares at score <= t
        cg = Decimal(0)
        cb = Decimal(0)
        ks_val = Decimal(0)
        ks_score = 0
        for s in scores:
            cg += gs.get(s, Decimal(0))
            cb += bs.get(s, Decimal(0))
            diff = abs(cb / wb - cg / wg)
            if diff > ks_val:
                ks_val = diff
                ks_score = s
        out[seg] = {'auc': f6(auc), 'gini': f6(gini), 'ks': f6(ks_val), 'ks_score': ks_score}
    return out


def psi_metrics(cohort, dev, cuts):
    out = {}
    for seg in SEGMENTS:
        rows = [a for a in cohort if a.segment == seg]
        devseg = dev.get(seg, {})
        total_dev = sum(devseg.values(), Decimal(0))
        exp = []
        for b in range(1, 11):
            exp.append(sum((devseg.get(s, Decimal(0)) for s in devseg if band_of(cuts, seg, s) == b),
                          Decimal(0)))
        wtot = sum(a.weight for a in rows)
        act = [Decimal(0)] * 10
        for a in rows:
            if a.score_band:
                act[a.score_band - 1] += a.weight
        bins = []
        psi = Decimal(0)
        for b in range(10):
            e = exp[b] / total_dev if total_dev else Decimal(0)
            a_ = act[b] / wtot if wtot else Decimal(0)
            ef = max(e, Decimal('0.0001'))
            af = max(a_, Decimal('0.0001'))
            psi += (af - ef) * (af / ef).ln()
            bins.append({'band': b + 1, 'expected': f6(e), 'actual': f6(a_)})
        out[seg] = {'psi': f6(psi), 'bins': bins}
    return out


def calibration_metrics(cohort, grid, appendixb):
    out = []
    for seg in SEGMENTS:
        rows = [a for a in cohort if a.segment == seg]
        for b in range(1, 11):
            sub = [a for a in rows if a.score_band == b]
            accounts_n = len(sub)
            wacc = sum(a.weight for a in sub)
            wbad = sum(a.weight for a in sub if a.bad)
            eb = Decimal(0)
            for a in sub:
                pd = grid.get((seg, a.score))
                if pd is None:
                    pd = Decimal(0)
                eb += a.weight * pd
            if accounts_n == 0:
                out.append({'segment': seg, 'band': b, 'accounts': 0, 'weighted_accounts': 0,
                            'weighted_bads': 0, 'expected_bads': f6(Decimal(0)),
                            'actual_rate': '', 'expected_rate': ''})
            else:
                ar = Decimal(wbad) / Decimal(wacc) if wacc else Decimal(0)
                er = eb / Decimal(wacc) if wacc else Decimal(0)
                out.append({'segment': seg, 'band': b, 'accounts': accounts_n,
                            'weighted_accounts': wacc, 'weighted_bads': wbad,
                            'expected_bads': f6(eb), 'actual_rate': f6(ar),
                            'expected_rate': f6(er)})
    return out


# ------------------------------------------------------------------ writers

def write_csv(path, header, rows):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(','.join(header) + '\n')
        for r in rows:
            f.write(','.join(r) + '\n')


def write_json(path, obj):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write('\n')


def fmt_ts(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def build_outputs(engine, accounts, rec):
    cohort = sorted([a for a in accounts.values() if not a.reason], key=lambda a: a.acct)
    excluded = sorted([a for a in accounts.values() if a.reason], key=lambda a: a.acct)
    score_sel = sorted([a for a in accounts.values()
                        if a.reason not in ('WINDOW', 'WITHDRAWN', 'DUPLICATE')],
                       key=lambda a: a.acct)
    windows = sorted([a for a in accounts.values()
                      if a.reason not in ('WINDOW', 'WITHDRAWN', 'DUPLICATE', 'NO_SCORE',
                                          'STAFF', 'LEGAL_HOLD', 'INSOLVENCY', 'REDRESS',
                                          'DECEASED', 'FRAUD')],
                     key=lambda a: a.acct)

    cohort_rows = []
    for a in cohort:
        cohort_rows.append([a.acct, a.segment or '', a.market or '', a.cohort_month,
                            fmt_ts(a.decision_utc),
                            str(a.score) if a.score is not None else '',
                            str(a.score_band) if a.score_band is not None else '',
                            str(a.bad),
                            str(a.weight) if a.weight is not None else '',
                            f2(a.exposure)])
    excl_rows = [[a.acct, a.reason] for a in excluded]
    sel_rows = []
    for a in score_sel:
        if a.score is None:
            sel_rows.append([a.acct, '', '', '', '', ''])
        else:
            sel_rows.append([a.acct, a.event_id or '', a.run_id or '', a.model_version or '',
                             fmt_ts(a.score_ts), str(a.score)])
    win_rows = []
    for a in windows:
        win_rows.append([a.acct, a.window_start, a.window_end_month,
                         str(a.months_observed), str(a.max_dpd), a.bad_month or '',
                         a.outcome or ''])

    cuts = engine.cuts
    dev = engine.d.get('monitoring_spec_v4.md', {}).get('dev', {})
    grid = engine.d.get('model_documentation_v4.pdf', {}).get('grid', {})
    appendixb = engine.d.get('calibration_reissue_2026.pdf', {}).get('appendixb', {})
    for key, pd in appendixb.items():
        grid[key] = pd

    pop = population_metrics(cohort)
    disc = discrimination(cohort, cuts)
    psi = psi_metrics(cohort, dev, cuts)
    calib = calibration_metrics(cohort, grid, appendixb)

    return {
        'cohort.csv': cohort_rows,
        'exclusions.csv': excl_rows,
        'score_selection.csv': sel_rows,
        'performance_windows.csv': win_rows,
        'population_summary.json': {'status': rec['status'], 'segments': pop},
        'discrimination.json': {'status': rec['status'], 'segments': disc},
        'psi.json': {'status': rec['status'], 'segments': psi},
        'calibration.csv': calib,
    }


def write_outputs(outdir, outputs, rec):
    os.makedirs(outdir, exist_ok=True)
    headers = {
        'cohort.csv': ['acct', 'segment', 'market', 'cohort_month', 'decision_utc', 'score',
                       'score_band', 'bad', 'weight', 'exposure_eur'],
        'exclusions.csv': ['acct', 'reason'],
        'score_selection.csv': ['acct', 'event_id', 'run_id', 'model_version', 'score_ts_utc',
                                'score'],
        'performance_windows.csv': ['acct', 'window_start', 'window_end', 'months_observed',
                                     'max_dpd', 'bad_month', 'outcome'],
        'calibration.csv': ['segment', 'band', 'accounts', 'weighted_accounts', 'weighted_bads',
                            'expected_bads', 'actual_rate', 'expected_rate'],
    }
    for name, rows in outputs.items():
        if name.endswith('.json'):
            write_json(os.path.join(outdir, name), rows)
        else:
            if rows and isinstance(rows[0], dict):
                rows = [[r.get(h, '') for h in headers[name]] for r in rows]
            write_csv(os.path.join(outdir, name), headers[name],
                      [[str(x) for x in r] for r in rows])
    write_json(os.path.join(outdir, 'reconciliation.json'), {
        'status': rec['status'],
        'files_checked': rec['files_checked'],
        'failed_controls': rec['failed_controls'],
        'estate_record_total': rec['estate_record_total'],
        'estate_hash_total': rec['estate_hash_total'],
    })


def empty_outputs(rec):
    return {
        'cohort.csv': [],
        'exclusions.csv': [],
        'score_selection.csv': [],
        'performance_windows.csv': [],
        'calibration.csv': [],
        'population_summary.json': {'segments': {}, 'status': 'UNRECONCILED'},
        'discrimination.json': {'segments': {}, 'status': 'UNRECONCILED'},
        'psi.json': {'segments': {}, 'status': 'UNRECONCILED'},
    }


# ------------------------------------------------------------------ main

def main(estatedir, outdir):
    est = Estate(estatedir)
    engine = Engine(est)
    scan_all(engine)
    rec = reconcile(engine)
    status = 'RECONCILED' if rec['reconciled'] else 'UNRECONCILED'
    rec['status'] = status
    if not rec['reconciled']:
        write_outputs(outdir, empty_outputs(rec), rec)
        return
    engine.resolve = make_resolver(engine)
    accounts = build_cohort(engine)
    build_scores(engine, accounts)
    engine.snap = build_snapshots(engine, accounts)
    engine.corr = build_corrections(engine)
    engine.cuts = score_cuts(engine)
    closures = {}
    for src in ('account_closures_2025.json', 'account_closures_2026h1.csv'):
        for a, dates in engine.d.get(src, {}).get('closures', {}).items():
            closures.setdefault(a, []).append(dates)
    for a in accounts.values():
        a.closure_dates = closures.get(a.acct, [])
    build_outcomes(engine, accounts)
    apply_exclusions(engine, accounts)
    build_weights(engine, accounts)
    build_exposure(engine, accounts)
    outputs = build_outputs(engine, accounts, rec)
    write_outputs(outdir, outputs, rec)


def make_resolver(engine):
    d = engine.d
    alias = d.get('customer_master.db', {}).get('alias', {})
    merges = {}
    for src in ('customer_merge_decisions.docx', 'customer_merges_2026.tsv'):
        for k, v in d.get(src, {}).get('merges', {}).items():
            merges[k] = v
    legacy_cust = d.get('merge_candidates_ml.xlsx', {}).get('legacy_cust', {})

    def resolve(cu):
        if cu is None:
            return None
        x = cu
        if x in legacy_cust:
            x = legacy_cust[x]
        seen = set()
        while x not in seen:
            seen.add(x)
            if x in alias:
                x = alias[x]
            elif x in merges:
                x = merges[x]
            else:
                return x
        return x
    return resolve


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.stderr.write('usage: monitor.py ESTATE_DIR OUT_DIR\n')
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
