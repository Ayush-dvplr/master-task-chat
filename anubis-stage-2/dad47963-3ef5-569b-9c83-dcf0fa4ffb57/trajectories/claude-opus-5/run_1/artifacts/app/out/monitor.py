#!/usr/bin/env python3
"""PD-RETAIL v4 performance monitoring engine - cycle 2026-Q2.

Usage: monitor.py ESTATE_DIR OUT_DIR
"""
import sys
import os
import re
import json
import bisect
import zipfile
import sqlite3
import datetime as dt
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN, getcontext
from fractions import Fraction

getcontext().prec = 60

# --------------------------------------------------------------------------
# generic helpers
# --------------------------------------------------------------------------

WS_RE = re.compile(r'[\s\u00a0\u200b\u200c\u200d\ufeff]+')
DIGITS_RE = re.compile(r'\d')


def digits_int(value):
    """Integer formed by the decimal digits of value, read in order."""
    if value is None:
        return 0
    if isinstance(value, (int,)) and not isinstance(value, bool):
        value = str(value)
    elif not isinstance(value, str):
        value = str(value)
    ds = ''.join(DIGITS_RE.findall(value))
    if not ds:
        return 0
    return int(ds)


def strip_ws(s):
    return WS_RE.sub('', s or '')


def canon_key(raw, prefix):
    """Canonical account/customer key: PREFIX + 7 digits."""
    if raw is None:
        return None
    s = strip_ws(str(raw)).upper()
    s = s.replace('\u0410', 'A').replace('\u0421', 'C')
    s = s.replace('-', '')
    if not s:
        return None
    ds = ''.join(DIGITS_RE.findall(s))
    if not ds:
        return None
    return prefix + str(int(ds)).rjust(7, '0')


def canon_acct(raw):
    return canon_key(raw, 'AC')


def canon_cust(raw):
    if raw is None:
        return None
    s = strip_ws(str(raw)).upper().replace('\u0410', 'A').replace('\u0421', 'C').replace('-', '')
    if not s:
        return None
    ds = ''.join(DIGITS_RE.findall(s))
    if not ds:
        return None
    pre = 'LCU' if s.startswith('LCU') else 'CU'
    return pre + str(int(ds)).rjust(7, '0')


def canon_id(raw):
    """Identifiers other than account/customer keys."""
    if raw is None:
        return None
    s = strip_ws(str(raw)).upper()
    return s or None


def canon_register_key(raw):
    """Inclusion register key: an account key or an application id."""
    if raw is None:
        return None
    s = strip_ws(str(raw)).upper()
    s = s.replace('\u0410', 'A').replace('\u0421', 'C')
    if s.startswith('AC'):
        return canon_acct(s)
    return s or None


def ci(raw):
    """case-insensitive trimmed comparison form"""
    if raw is None:
        return ''
    return str(raw).strip().upper()


def parse_date(s):
    """Tolerant date parser -> datetime.date or None."""
    if s is None:
        return None
    if isinstance(s, dt.datetime):
        return s.date()
    if isinstance(s, dt.date):
        return s
    t = str(s).strip()
    if not t:
        return None
    t = t.replace('\u00a0', ' ').strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', t)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r'^(\d{4})/(\d{2})/(\d{2})$', t)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r'^(\d{4})(\d{2})(\d{2})$', t)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r'^(\d{2})[/.](\d{2})[/.](\d{4})$', t)
    if m:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = re.match(r'^(\d{2})-(\d{2})-(\d{4})$', t)
    if m:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return None


def parse_month(s):
    """YYYY-MM / YYYYMM / date -> (year, month) tuple or None."""
    if s is None:
        return None
    if isinstance(s, dt.datetime):
        return (s.year, s.month)
    if isinstance(s, dt.date):
        return (s.year, s.month)
    t = str(s).strip()
    if not t:
        return None
    m = re.match(r'^(\d{4})-(\d{1,2})(?:-\d{1,2})?', t)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = re.match(r'^(\d{4})(\d{2})$', t)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = re.match(r'^(\d{1,2})[/.](\d{4})$', t)
    if m:
        return (int(m.group(2)), int(m.group(1)))
    m = re.match(r'^(\d{4})[/.](\d{1,2})$', t)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return None


def month_key(ym):
    return '%04d-%02d' % ym


def month_add(ym, k):
    y, m = ym
    t = y * 12 + (m - 1) + k
    return (t // 12, t % 12 + 1)


def month_last_day(ym):
    y, m = ym
    if m == 12:
        return dt.date(y, 12, 31)
    return dt.date(y, m + 1, 1) - dt.timedelta(days=1)


def month_first_day(ym):
    return dt.date(ym[0], ym[1], 1)


def parse_iso_instant(s):
    """ISO-8601 instant (Z, offset, or naive=UTC) -> naive UTC datetime."""
    if s is None:
        return None
    if isinstance(s, dt.datetime):
        if s.tzinfo is not None:
            return s.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return s
    t = str(s).strip()
    if not t:
        return None
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})'
                 r'(?:\.\d+)?\s*(Z|z|[+-]\d{2}:?\d{2})?$', t)
    if not m:
        return None
    base = dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                       int(m.group(4)), int(m.group(5)), int(m.group(6)))
    off = m.group(7)
    if off and off not in ('Z', 'z'):
        sign = 1 if off[0] == '+' else -1
        off = off[1:].replace(':', '')
        delta = dt.timedelta(hours=int(off[:2]), minutes=int(off[2:]))
        base = base - sign * delta
    return base


def parse_naive_dt(s):
    """Local wall clock 'YYYY-MM-DD HH:MM:SS' or 'YYYYMMDDHHMMSS'."""
    if s is None:
        return None
    if isinstance(s, dt.datetime):
        return s
    t = str(s).strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})', t)
    if m:
        return dt.datetime(*[int(m.group(i)) for i in range(1, 7)])
    m = re.match(r'^(\d{14})$', t)
    if m:
        return dt.datetime(int(t[0:4]), int(t[4:6]), int(t[6:8]),
                           int(t[8:10]), int(t[10:12]), int(t[12:14]))
    return None


_NUM_CLEAN = re.compile(r'[^0-9+\-.,()]')


def parse_decimal(value, comma_decimal=False):
    """Decimal from a possibly messy numeric string."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    t = str(value).strip()
    if not t:
        return None
    neg = False
    if t.startswith('(') and t.endswith(')'):
        neg = True
        t = t[1:-1].strip()
    t = t.replace('\u00a0', '').replace(' ', '')
    if comma_decimal:
        t = t.replace('.', '')
        t = t.replace(',', '.')
    else:
        if ',' in t and '.' in t:
            t = t.replace(',', '')
        elif ',' in t:
            # ambiguous single comma: treat as decimal separator
            if re.match(r'^[+-]?\d{1,3}(,\d{3})+$', t):
                t = t.replace(',', '')
            else:
                t = t.replace(',', '.')
    if t.startswith('+'):
        t = t[1:]
    if re.match(r'^-?(\d+\.?\d*|\.\d+)[eE][+-]?\d+$', t):
        d = Decimal(t)
        return -d if neg else d
    if not re.match(r'^-?\d*\.?\d*$', t) or t in ('', '-', '.', '-.'):
        return None
    d = Decimal(t)
    return -d if neg else d


CENT = Decimal('0.01')


def to_cents(value, comma_decimal=False):
    """Account money amount read to cents, half up."""
    d = parse_decimal(value, comma_decimal)
    if d is None:
        return None
    return d.quantize(CENT, rounding=ROUND_HALF_UP)


def excel_serial_to_date(v):
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    d = parse_decimal(v)
    if d is None:
        return None
    n = int(d)
    return dt.date(1970, 1, 1) + dt.timedelta(days=n - 25569)


def excel_serial_to_dt(v):
    if isinstance(v, dt.datetime):
        return v
    if isinstance(v, dt.date):
        return dt.datetime(v.year, v.month, v.day)
    d = parse_decimal(v)
    if d is None:
        return None
    secs = (d - Decimal(25569)) * Decimal(86400)
    secs = int(secs.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return dt.datetime(1970, 1, 1) + dt.timedelta(seconds=secs)


# --------------------------------------------------------------------------
# delimited parsing
# --------------------------------------------------------------------------

def read_text(path, encoding='utf-8'):
    with open(path, 'rb') as fh:
        data = fh.read()
    if data.startswith(b'\xef\xbb\xbf'):
        data = data[3:]
    return data.decode(encoding)


def split_records(text, delim):
    """RFC4180 split honouring quotes; '#' lines are comments."""
    rows = []
    comments = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == '#':
            j = text.find('\n', i)
            if j < 0:
                j = n
            comments.append(text[i:j].rstrip('\r'))
            i = j + 1
            continue
        if c == '\n':
            i += 1
            continue
        if c == '\r':
            i += 2 if (i + 1 < n and text[i + 1] == '\n') else 1
            continue
        fields = []
        cur = []
        while i < n:
            c = text[i]
            if c == '"':
                i += 1
                while i < n:
                    if text[i] == '"':
                        if i + 1 < n and text[i + 1] == '"':
                            cur.append('"')
                            i += 2
                        else:
                            i += 1
                            break
                    else:
                        cur.append(text[i])
                        i += 1
            elif c == delim:
                fields.append(''.join(cur))
                cur = []
                i += 1
            elif c == '\r':
                i += 2 if (i + 1 < n and text[i + 1] == '\n') else 1
                break
            elif c == '\n':
                i += 1
                break
            else:
                cur.append(c)
                i += 1
        fields.append(''.join(cur))
        rows.append(fields)
    return rows, comments


def delimited_rows(path, delim, encoding='utf-8'):
    """-> (list of dict, comments)"""
    text = read_text(path, encoding)
    rows, comments = split_records(text, delim)
    if not rows:
        return [], comments
    header = rows[0]
    hsorted = sorted(header)
    cols = header
    out = []
    for r in rows[1:]:
        if len(r) == len(header) and sorted(r) == hsorted:
            cols = r
            continue
        d = {}
        for idx, name in enumerate(cols):
            d[name] = r[idx] if idx < len(r) else ''
        out.append(d)
    return out, comments


CTRL_FIELDS = ('control_id', 'ack_rows_of', 'ack_rows', 'ack_hash_of', 'ack_hash')


def ctrl_from_kv(text):
    d = {}
    for m in re.finditer(r'(control_id|ack_rows_of|ack_rows|ack_hash_of|ack_hash)'
                         r'\s*[=:]\s*([A-Za-z0-9\-]+)', text):
        d[m.group(1)] = m.group(2)
    return normalise_ctrl(d)


def normalise_ctrl(d):
    if not d:
        return None
    out = {}
    out['control_id'] = canon_id(d.get('control_id'))
    out['ack_rows_of'] = canon_id(d.get('ack_rows_of'))
    out['ack_hash_of'] = canon_id(d.get('ack_hash_of'))
    out['ack_rows'] = digits_int(d.get('ack_rows'))
    out['ack_hash'] = digits_int(d.get('ack_hash'))
    return out


def ctrl_from_comments(comments):
    for line in comments:
        if 'control_id' in line:
            return ctrl_from_kv(line)
    return None


# --------------------------------------------------------------------------
# readers: every delivery -> (records, control)
# --------------------------------------------------------------------------

READERS = {}


def _mk(records, hk_field, control):
    for r in records:
        r['_hk'] = digits_int(r.get(hk_field))
    return records, control


def _delim_reader(delim, hk, encoding='utf-8'):
    def fn(path):
        rows, comments = delimited_rows(path, delim, encoding)
        return _mk(rows, hk, ctrl_from_comments(comments))
    return fn


for _name, _delim, _hk, _enc in [
    ('applications_2025_01.csv', ',', 'account_ref', 'utf-8'),
    ('applications_2025_04.csv', ';', 'konto', 'utf-8'),
    ('applications_2025_04_reextract.csv', ',', 'account', 'utf-8'),
    ('snapshots_2025_02.csv', ',', 'account', 'utf-8'),
    ('snapshots_2025_06_a.csv', ';', 'konto', 'utf-8'),
    ('snapshots_2025_08_a.csv', ',', 'account', 'utf-8'),
    ('snapshots_2025_10_a.csv', ',', 'account', 'utf-8'),
    ('snapshots_2025_11_a.csv', ',', 'account', 'utf-8'),
    ('snapshots_2025_11_a_rev2.csv', ',', 'account', 'utf-8'),
    ('snapshots_2026_02_a.csv', ',', 'account', 'utf-8'),
    ('snapshots_2026_06.csv', ',', 'account', 'utf-8'),
    ('status_events_chargeoff_2025.csv', ',', 'account_ref', 'utf-8'),
    ('score_events_backfill.csv', ',', 'account', 'utf-8'),
    ('account_closures_2026h1.csv', ',', 'account', 'utf-8'),
    ('applications_2025_02.tsv', '\t', 'acct', 'utf-8'),
    ('snapshots_2025_03.tsv', '\t', 'acct', 'utf-8'),
    ('snapshots_2025_08_b.tsv', '\t', 'acct', 'utf-8'),
    ('snapshots_2025_10_b.tsv', '\t', 'acct', 'utf-8'),
    ('snapshots_2025_10_b_restated.tsv', '\t', 'acct', 'utf-8'),
    ('score_events_node7.tsv', '\t', 'account', 'utf-8'),
    ('customer_merges_2026.tsv', '\t', 'merged_customer', 'utf-8'),
    ('employee_leavers.tsv', '\t', 'employee_id', 'utf-8'),
]:
    READERS[_name] = _delim_reader(_delim, _hk, _enc)


def _jsonl_reader(hk):
    def fn(path):
        records = []
        control = None
        with open(path, 'rb') as fh:
            data = fh.read()
        if data.startswith(b'\xef\xbb\xbf'):
            data = data[3:]
        for line in data.decode('utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if '_control' in obj:
                control = normalise_ctrl(obj['_control'])
                continue
            if '_header' in obj:
                continue
            records.append(obj)
        return _mk(records, hk, control)
    return fn


for _name, _hk in [
    ('applications_2025_06.jsonl', 'acct'),
    ('snapshots_2025_06_b.jsonl', 'a'),
    ('snapshots_2026_02_b.jsonl', 'a'),
    ('score_batches_2025_q1.jsonl', 'acct'),
    ('score_batches_2025_q2_a.jsonl', 'acct'),
    ('score_batches_2025_q2_b.jsonl', 'acct'),
    ('score_batches_2025_q2_c.jsonl', 'acct'),
    ('fraud_alerts_2025.jsonl', 'case'),
]:
    READERS[_name] = _jsonl_reader(_hk)


def _json_obj_reader(array_key, hk):
    def fn(path):
        with open(path, 'rb') as fh:
            obj = json.loads(fh.read().decode('utf-8'))
        control = normalise_ctrl(obj.get('control'))
        records = list(obj.get(array_key) or [])
        if hk == '_ref_or_subject':
            for r in records:
                ref = (r.get('ref') or '').strip()
                r['_hk'] = digits_int(ref if ref else r.get('subject'))
            return records, control
        return _mk(records, hk, control)
    return fn


for _name, _ak, _hk in [
    ('account_closures_2025.json', 'closures', 'account'),
    ('fraud_case_dispositions.json', 'cases', 'case_id'),
    ('delivery_manifest.json', 'deliveries', 'delivery_id'),
    ('score_clock_skew_corrections.json', 'runs', 'run'),
    ('application_withdrawals.json', 'withdrawals', 'account'),
    ('status_events_consolidated.json', 'events', '_ref_or_subject'),
]:
    READERS[_name] = _json_obj_reader(_ak, _hk)


def _xlsx_control(path):
    with zipfile.ZipFile(path) as z:
        try:
            raw = z.read('docProps/custom.xml').decode('utf-8')
        except KeyError:
            return None
    d = {}
    for m in re.finditer(r'name="([^"]+)"[^>]*>\s*<[^>]*>([^<]*)<', raw):
        d[m.group(1)] = m.group(2)
    return normalise_ctrl({k: v for k, v in d.items() if k in CTRL_FIELDS})


def _sheet_rows(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        header = None
        for row in ws.iter_rows(values_only=True):
            if header is None:
                header = [str(c).strip() if c is not None else '' for c in row]
                continue
            if all(c is None for c in row):
                continue
            d = {}
            for idx, name in enumerate(header):
                d[name] = row[idx] if idx < len(row) else None
            d['_sheet'] = ws.title
            out.append(d)
    wb.close()
    return out


def _xlsx_reader(hk):
    def fn(path):
        rows = _sheet_rows(path)
        if isinstance(hk, dict):
            for r in rows:
                r['_hk'] = digits_int(r.get(hk[r['_sheet']]))
            return rows, _xlsx_control(path)
        return _mk(rows, hk, _xlsx_control(path))
    return fn


for _name, _hk in [
    ('applications_2025_05.xlsx', 'account'),
    ('snapshots_2025_05.xlsx', 'account'),
    ('snapshots_2025_09.xlsx', 'account'),
    ('snapshots_2025_12.xlsx', 'account'),
    ('snapshots_2026_03.xlsx', 'account'),
    ('limit_amendments_2025.xlsx', 'account'),
    ('product_migrations_2025.xlsx', 'account'),
]:
    READERS[_name] = _xlsx_reader(_hk)

READERS['merge_candidates_ml.xlsx'] = _xlsx_reader(
    {'candidates': 'customer_a', 'legacy_refs': 'legacy_customer'})


def _xml_root(path):
    from lxml import etree
    parser = etree.XMLParser(resolve_entities=False, huge_tree=True)
    return etree.parse(path, parser).getroot()


def _lname(el):
    t = el.tag
    if isinstance(t, str) and '}' in t:
        return t.split('}', 1)[1]
    return t


def _xml_reader(rec_tag, hk_fn):
    def fn(path):
        root = _xml_root(path)
        records = []
        control = None
        for el in root.iter():
            if not isinstance(el.tag, str):
                continue
            ln = _lname(el)
            if ln == rec_tag:
                d = dict(el.attrib)
                for ch in el:
                    if isinstance(ch.tag, str):
                        d[_lname(ch)] = (ch.text or '').strip()
                d['_text'] = (el.text or '').strip()
                d['_hk'] = hk_fn(d)
                records.append(d)
            elif ln == 'control':
                control = normalise_ctrl(dict(el.attrib))
        return records, control
    return fn


READERS['treasury_fixings_2024_2026.xml'] = _xml_reader(
    'fixing', lambda d: digits_int(d.get('date')))
READERS['score_events_node6.xml'] = _xml_reader(
    'event', lambda d: digits_int(d.get('account')))
READERS['snapshot_corrections_feed.xml'] = _xml_reader(
    'correction', lambda d: digits_int(d.get('account')))
READERS['deceased_notifications_feed.xml'] = _xml_reader(
    'notification', lambda d: digits_int(d.get('customer')))
READERS['fraud_alerts_2026.xml'] = _xml_reader(
    'alert', lambda d: digits_int(d.get('case')))
READERS['fx_rates_ecb_mirror.xml'] = _xml_reader(
    'rate', lambda d: digits_int(d.get('date')))


def _parquet_reader(hk):
    def fn(path):
        import pyarrow.parquet as pq
        table = pq.read_table(path)
        meta = table.schema.metadata or {}
        control = None
        raw = meta.get(b'delivery_control')
        if raw:
            control = normalise_ctrl(json.loads(raw.decode('utf-8')))
        records = table.to_pylist()
        return _mk(records, hk, control)
    return fn


for _name in ['snapshots_2025_04.parquet', 'snapshots_2025_11_b.parquet',
              'snapshots_2026_05_a.parquet', 'score_events_node5.parquet',
              'chargeoff_events_2026.parquet',
              'applications_master_2025h1.parquet']:
    READERS[_name] = _parquet_reader('account')


def _docx_tables(path):
    from docx import Document
    from docx.table import Table
    doc = Document(path)
    tables = []
    for child in doc.element.body.iterchildren():
        if child.tag.endswith('}tbl'):
            tb = Table(child, doc)
            rows = []
            for r in tb.rows:
                rows.append([c.text.strip() for c in r.cells])
            tables.append(rows)
    return tables


def _docx_reader(hk_index):
    def fn(path):
        tables = _docx_tables(path)
        header = tables[0][0] if tables else None
        out = []
        for rows in tables:
            for r in rows:
                if r == header:
                    continue
                out.append({'_cells': r,
                            '_hk': digits_int(r[hk_index]
                                              if hk_index < len(r) else '')})
        return out, _xlsx_control(path)
    return fn


for _name, _hki in [('governance_precedence_policy.docx', 0),
                    ('exclusion_policy.docx', 0),
                    ('customer_merge_decisions.docx', 0),
                    ('sampling_methodology.docx', 0),
                    ('bad_definition_standard.docx', 0),
                    ('limit_management_policy.docx', 1),
                    ('bad_definition_standard_v5.docx', 0)]:
    READERS[_name] = _docx_reader(_hki)


_PDF_CACHE = {}


def pdf_lines(path):
    key = os.path.realpath(path)
    if key in _PDF_CACHE:
        return _PDF_CACHE[key]
    import logging
    logging.disable(logging.CRITICAL)
    from pdfminer.high_level import extract_text
    text = extract_text(path)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    _PDF_CACHE[key] = lines
    return lines


def _pdf_control(lines):
    for ln in reversed(lines):
        if 'control_id' in ln:
            return ctrl_from_kv(ln)
    return None


def _pdf_reader(ncols, hk_index, numeric_col=None):
    def fn(path):
        lines = pdf_lines(path)
        records = []
        header = None
        for ln in lines:
            if 'control_id' in ln:
                continue
            if '|' not in ln:
                continue
            cells = [c.strip() for c in ln.split('|')]
            if len(cells) != ncols:
                continue
            if numeric_col is not None:
                if not re.match(r'^\d+$', cells[numeric_col].replace(' ', '')):
                    continue
            elif header is None:
                header = cells
                continue
            elif cells == header:
                continue
            records.append({'_cells': cells, '_hk': digits_int(cells[hk_index])})
        return records, _pdf_control(lines)
    return fn


READERS['model_documentation_v4.pdf'] = _pdf_reader(3, 1, 1)
READERS['calibration_reissue_2026.pdf'] = _pdf_reader(3, 1, 1)
READERS['consumer_redress_programme.pdf'] = _pdf_reader(2, 0)
READERS['deceased_notifications_register.pdf'] = _pdf_reader(2, 0)
READERS['audit_label_confirmations.pdf'] = _pdf_reader(2, 0)
READERS['regulatory_exclusion_letter_2026.pdf'] = _pdf_reader(2, 0)
READERS['forbearance_extensions_register.pdf'] = _pdf_reader(2, 0)


def _log_reader(with_void):
    def fn(path):
        records = []
        control = None
        with open(path, 'rb') as fh:
            text = fh.read().decode('utf-8')
        for line in text.splitlines():
            if not line.strip():
                continue
            if line.startswith('#'):
                if 'control_id' in line:
                    control = ctrl_from_kv(line)
                continue
            toks = [t for t in line.split(' ') if t]
            if len(toks) < 4:
                continue
            kind = toks[3]
            if kind == 'SCORE' or (with_void and kind == 'VOID'):
                d = {'_kind': kind, '_ts': toks[0]}
                for t in toks[4:]:
                    if '=' in t:
                        k, v = t.split('=', 1)
                        d[strip_ws(k).lower()] = v
                if kind == 'SCORE':
                    d['_hk'] = digits_int(d.get('acct'))
                else:
                    d['_hk'] = digits_int(d.get('run'))
                records.append(d)
        return records, control
    return fn


for _name in ['scoring_engine_node1.log', 'scoring_engine_node2.log',
              'scoring_engine_node3.log', 'scoring_engine_node4.log']:
    READERS[_name] = _log_reader(False)
READERS['scoring_engine_node9.log'] = _log_reader(True)


def _sqlite_reader(hk_map):
    def fn(path):
        con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
        con.text_factory = str
        cur = con.cursor()
        try:
            row = cur.execute('select * from delivery_control').fetchone()
            names = [d[0] for d in cur.description]
            control = normalise_ctrl(dict(zip(names, row)))
        except sqlite3.Error:
            control = None
        tables = [r[0] for r in cur.execute(
            "select name from sqlite_master where type='table' order by rowid")]
        records = []
        for t in tables:
            rows = cur.execute('select * from "%s"' % t).fetchall()
            names = [d[0] for d in cur.description]
            mode = hk_map(t)
            for r in rows:
                d = dict(zip(names, r))
                d['_table'] = t
                if mode == 'value_mod':
                    d['_hk'] = digits_int(d.get('value')) % 10000000
                else:
                    d['_hk'] = digits_int(d.get(mode))
                records.append(d)
        con.close()
        return records, control
    return fn


READERS['servicing_snapshots_2025q3.db'] = _sqlite_reader(lambda t: 'account')
READERS['servicing_snapshots_2026q1.db'] = _sqlite_reader(lambda t: 'account')
READERS['customer_master.db'] = _sqlite_reader(
    lambda t: 'customer' if t == 'customers' else 'alias')
READERS['snapshots_servicing_replica.db'] = _sqlite_reader(
    lambda t: 'value_mod' if t == 'cycle_controls' else 'account')


def _yaml_reader():
    def fn(path):
        import yaml
        loader = getattr(yaml, 'CBaseLoader', yaml.BaseLoader)
        with open(path, 'rb') as fh:
            doc = yaml.load(fh, Loader=loader)
        control = normalise_ctrl(doc.get('delivery_control'))
        records = list(doc.get('inclusion') or [])
        return _mk(records, 'key', control)
    return fn


for _name in ['sampling_inclusion_gb_pl_se.yaml', 'sampling_inclusion_cz_hu_ch.yaml',
              'sampling_inclusion_dk_no.yaml', 'sampling_design_v2.yaml']:
    READERS[_name] = _yaml_reader()


def _toml_load(path):
    import tomli
    with open(path, 'rb') as fh:
        return tomli.load(fh)


def _toml_reader(array_key, hk):
    def fn(path):
        doc = _toml_load(path)
        control = normalise_ctrl(doc.get('delivery_control'))
        records = list(doc.get(array_key) or [])
        return _mk(records, hk, control)
    return fn


READERS['model_registry_v4.toml'] = _toml_reader('run', 'run_id')
READERS['scoring_runs_2025q2.toml'] = _toml_reader('run', 'run_id')
READERS['model_registry_v4_1.toml'] = _toml_reader('calibration_point', 'score')


def ini_sections(path):
    text = read_text(path, 'utf-8')
    sections = []
    cur = None
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(';') or s.startswith('#'):
            continue
        if s.startswith('[') and s.endswith(']'):
            cur = (s[1:-1].strip(), [])
            sections.append(cur)
            continue
        if cur is None:
            continue
        if '=' in s:
            k, v = s.split('=', 1)
        elif ':' in s:
            k, v = s.split(':', 1)
        else:
            continue
        # inline ';' text is commentary
        v = v.split(';', 1)[0]
        cur[1].append((k.strip().lower(), v.strip()))
    return sections


def _ini_reader(section_filter):
    def fn(path):
        sections = ini_sections(path)
        control = None
        records = []
        for name, items in sections:
            lname = name.strip().lower()
            if lname == 'delivery_control':
                control = normalise_ctrl(dict(items))
                continue
            if lname == 'default':
                continue
            if section_filter and lname not in section_filter:
                continue
            for k, v in items:
                records.append({'_section': name, 'key': k, 'value': v,
                                '_hk': digits_int(k)})
        return records, control
    return fn


READERS['product_code_crosswalk.ini'] = _ini_reader(None)
READERS['legacy_account_map.ini'] = _ini_reader({'legacy_accounts'})
READERS['currency_redenomination.ini'] = _ini_reader({'redenominated'})


def md_tables(path):
    text = read_text(path, 'utf-8')
    out = []
    heading = ''
    rows = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith('#'):
            heading = s.lstrip('#').strip()
            rows = None
            continue
        if s.startswith('|'):
            cells = [c.strip() for c in s.strip('|').split('|')]
            if all(re.match(r'^:?-{2,}:?$', c) for c in cells):
                continue
            if rows is None:
                rows = []
                out.append((heading, rows))
            rows.append(cells)
        else:
            rows = None
    return out


def _md_reader(heading_match, hk_index):
    def fn(path):
        tables = md_tables(path)
        records = []
        control = None
        for heading, rows in tables:
            h = heading.lower()
            if 'delivery control' in h:
                d = {}
                for r in rows:
                    if len(r) >= 2:
                        d[r[0].strip()] = r[1].strip()
                control = normalise_ctrl({k: v for k, v in d.items()
                                          if k in CTRL_FIELDS})
                continue
            if heading_match not in h:
                continue
            for r in rows[1:]:
                records.append({'_cells': r,
                                '_hk': digits_int(r[hk_index]
                                                  if hk_index < len(r) else '')})
        return records, control
    return fn


READERS['monitoring_spec_v4.md'] = _md_reader('appendix a', 1)
READERS['errata_register.md'] = _md_reader('row errata', 0)
READERS['data_quality_issue_log.md'] = _md_reader('data quality issue log', 0)


def html_table_rows(path):
    from lxml import html as lhtml
    with open(path, 'rb') as fh:
        doc = lhtml.fromstring(fh.read())
    control = None
    for meta in doc.iter('meta'):
        if (meta.get('name') or '') == 'delivery-control':
            control = ctrl_from_kv(meta.get('content') or '')
    tables = [t for t in doc.iter('table') if t.get('id') == 'register']
    rows = []
    for t in tables:
        for tr in t.iter('tr'):
            tds = [c for c in tr if c.tag in ('td', 'th')]
            if not tds:
                continue
            is_header = any(c.tag == 'th' for c in tds)
            cells = []
            for c in tds:
                txt = ''.join(c.itertext()).strip()
                span = int(c.get('rowspan') or 1)
                cells.append((txt, span))
            rows.append((is_header, cells))
    return rows, control


def _html_reader(hk_index, expand_rowspan):
    def fn(path):
        rows, control = html_table_rows(path)
        records = []
        carry = []
        for is_header, cells in rows:
            if is_header:
                carry = []
                continue
            if expand_rowspan:
                vals = []
                newcarry = []
                for text, span in carry:
                    vals.append(text)
                    if span > 1:
                        newcarry.append((text, span - 1))
                for text, span in cells:
                    vals.append(text)
                    if span > 1:
                        newcarry.append((text, span - 1))
                carry = newcarry
                cellvals = vals
            else:
                cellvals = [t for t, s in cells]
            records.append({'_cells': cellvals,
                            '_hk': digits_int(cellvals[hk_index]
                                              if hk_index < len(cellvals) else '')})
        return records, control
    return fn


READERS['branch_directory.html'] = _html_reader(1, True)
READERS['branch_directory_2026.html'] = _html_reader(0, False)
READERS['litigation_hold_register.html'] = _html_reader(1, False)


def _fixed_reader(spec, hk):
    def fn(path):
        with open(path, 'rb') as fh:
            text = fh.read().decode('iso-8859-1')
        records = []
        control = None
        for line in text.splitlines():
            if not line.strip():
                continue
            t = line[0:2]
            if t == '99':
                control = ctrl_from_kv(line[2:])
                continue
            if t != '10':
                continue
            d = {}
            for name, a, b in spec:
                d[name] = line[a - 1:b]
            d['_hk'] = digits_int(d.get(hk))
            records.append(d)
        return records, control
    return fn


READERS['applications_2025_03.txt'] = _fixed_reader([
    ('app_id', 3, 13), ('account', 14, 25), ('customer', 26, 37),
    ('branch', 38, 43), ('product', 44, 51), ('decided', 52, 65),
    ('limit', 66, 78), ('revision', 79, 80), ('received', 81, 94),
    ('name', 95, 118)], 'account')

for _name in ['snapshots_2026_04.txt', 'snapshots_2026_05_b.txt']:
    READERS[_name] = _fixed_reader([
        ('account', 3, 14), ('period', 15, 20), ('dpd', 21, 24),
        ('status', 25, 25), ('balance', 26, 40)], 'account')


def _mbox_reader():
    def fn(path):
        with open(path, 'rb') as fh:
            raw = fh.read().decode('utf-8', 'replace')
        chunks = []
        cur = None
        for line in raw.splitlines():
            if line.startswith('From ') and re.match(
                    r'^From \S+@\S+ \w{3} \w{3} \d{2} ', line):
                cur = []
                chunks.append(cur)
                continue
            if cur is not None:
                cur.append(line)
        records = []
        control = None
        for ch in chunks:
            idx = len(ch)
            for i, line in enumerate(ch):
                if line.strip() == '':
                    idx = i
                    break
            headers = {}
            name = None
            for line in ch[:idx]:
                if line[:1] in (' ', '\t') and name:
                    headers[name] += ' ' + line.strip()
                elif ':' in line:
                    name, val = line.split(':', 1)
                    name = name.strip().lower()
                    headers[name] = val.strip()
            body = ch[idx + 1:]
            if ci(headers.get('subject')) == 'DELIVERY CONTROL':
                control = ctrl_from_kv('\n'.join(body))
                continue
            enc = (headers.get('content-transfer-encoding') or '').strip().lower()
            btext = '\n'.join(body)
            if enc == 'quoted-printable':
                import quopri
                btext = quopri.decodestring(
                    btext.encode('utf-8')).decode('utf-8', 'replace')
            records.append({'_headers': headers, '_body': btext,
                            '_hk': digits_int(headers.get('message-id'))})
        return records, control
    return fn


READERS['ops_corrections.mbox'] = _mbox_reader()


def _ics_reader():
    def fn(path):
        with open(path, 'rb') as fh:
            text = fh.read().decode('utf-8')
        lines = []
        for line in text.splitlines():
            if line[:1] in (' ', '\t') and lines:
                lines[-1] += line[1:]
            else:
                lines.append(line)
        records = []
        control = None
        cur = None
        for line in lines:
            s = line.strip()
            if s == 'BEGIN:VEVENT':
                cur = {}
                continue
            if s == 'END:VEVENT':
                datepart = cur.get('DTSTART', '').split('T')[0]
                cur['_hk'] = digits_int(datepart)
                records.append(cur)
                cur = None
                continue
            if s.startswith('X-DELIVERY-CONTROL'):
                control = ctrl_from_kv(s)
                continue
            if ':' not in s:
                continue
            k, v = s.split(':', 1)
            params = k.split(';')
            name = params[0].strip().upper()
            if cur is not None:
                cur[name] = v.strip()
                for p in params[1:]:
                    if '=' in p:
                        pk, pv = p.split('=', 1)
                        cur[name + ';' + pk.strip().upper()] = pv.strip()
        return records, control
    return fn


READERS['market_holidays.ics'] = _ics_reader()


# --------------------------------------------------------------------------
# estate: delivery access, controls, quarantine
# --------------------------------------------------------------------------

SEGMENTS = ['CARD', 'PLOAN', 'AUTO', 'MORT', 'OVDR', 'BNPL']
MARKET_CCY = {'GB': 'GBP', 'PL': 'PLN', 'SE': 'SEK', 'CZ': 'CZK',
              'HU': 'HUF', 'CH': 'CHF', 'DK': 'DKK', 'NO': 'NOK'}
CYCLE = '2026-Q2-MON'


class Estate(object):
    def __init__(self, root):
        self.root = root
        self._raw = {}
        self._ctrl = {}
        self._recs = {}
        self._load_manifest()
        self._load_quarantine()

    def path(self, name):
        return os.path.join(self.root, name)

    def raw(self, name):
        """All records of a delivery, in catalogue order."""
        if name not in self._raw:
            recs, ctrl = READERS[name](self.path(name))
            self._raw[name] = recs
            self._ctrl[name] = ctrl
        return self._raw[name]

    def control(self, name):
        self.raw(name)
        return self._ctrl[name]

    def records(self, name):
        """Records of a delivery with quarantined records removed."""
        if name in self._recs:
            return self._recs[name]
        recs = self.raw(name)
        drop = self.quarantine.get(name.lower())
        if drop:
            out = [r for i, r in enumerate(recs) if (i + 1) not in drop]
        else:
            out = list(recs)
        self._recs[name] = out
        return out

    def _load_manifest(self):
        recs = self.raw('delivery_manifest.json')
        self.deliveries = {}
        self.file_of = {}
        for r in recs:
            if (r.get('cycle') or '').strip() != CYCLE:
                continue
            did = canon_id(r.get('delivery_id'))
            fname = (r.get('file') or '').strip()
            self.deliveries[did] = {
                'file': fname,
                'delivered_at': parse_iso_instant(r.get('delivered_at')),
            }
            self.file_of[did] = fname
        self.delivered_at = {v['file']: v['delivered_at']
                             for v in self.deliveries.values()}
        with open(self.path('delivery_manifest.json'), 'rb') as fh:
            obj = json.loads(fh.read().decode('utf-8'))
        self.certified = []
        for c in obj.get('certified_snapshot_partitions') or []:
            self.certified.append({
                'period': parse_month(c['period']),
                'markets': set(ci(m) for m in c['markets']),
                'file': c['file'].strip(),
            })

    def _load_quarantine(self):
        valid = set(f.lower() for f in self.file_of.values())
        self.quarantine = {}
        for r in self.raw('data_quality_issue_log.md'):
            cells = r['_cells']
            if len(cells) < 4:
                continue
            delivery = cells[1].strip().lower()
            if delivery not in valid:
                continue
            if ci(cells[3]) != 'QUARANTINE':
                continue
            num = digits_int(cells[2])
            self.quarantine.setdefault(delivery, set()).add(num)

    # -- reconciliation ----------------------------------------------------
    def reconcile(self):
        counts = {}
        hashes = {}
        read = 0
        for did in sorted(self.deliveries):
            fname = self.deliveries[did]['file']
            try:
                recs = self.raw(fname)
            except Exception:
                continue
            read += 1
            counts[did] = len(recs)
            hashes[did] = sum(r['_hk'] for r in recs)
        failed = []
        for did in sorted(self.deliveries):
            info = self.deliveries[did]
            if did not in counts:
                failed.append(did)
                continue
            ctrl = self.control(info['file'])
            ok = True
            if ctrl is None:
                ok = False
            else:
                tr = ctrl['ack_rows_of']
                th = ctrl['ack_hash_of']
                if tr not in counts or counts[tr] != ctrl['ack_rows']:
                    ok = False
                if th not in hashes or hashes[th] != ctrl['ack_hash']:
                    ok = False
            cid = ctrl['control_id'] if ctrl else did
            if not ok:
                failed.append(cid)
        return {
            'status': 'RECONCILED' if not failed else 'UNRECONCILED',
            'files_checked': read,
            'failed_controls': sorted(set(failed)),
            'estate_record_total': sum(counts.values()),
            'estate_hash_total': sum(hashes.values()),
        }


# --------------------------------------------------------------------------
# time and markets
# --------------------------------------------------------------------------

def last_sunday(year, month):
    d = month_last_day((year, month))
    while d.weekday() != 6:
        d -= dt.timedelta(days=1)
    return d


_DST_CACHE = {}


def _dst_bounds(year):
    if year not in _DST_CACHE:
        _DST_CACHE[year] = (
            dt.datetime.combine(last_sunday(year, 3), dt.time(1, 0)),
            dt.datetime.combine(last_sunday(year, 10), dt.time(1, 0)))
    return _DST_CACHE[year]


def dst_active(utc_dt):
    start, end = _dst_bounds(utc_dt.year)
    return start <= utc_dt < end


def base_offset(market):
    return 0 if market == 'GB' else 1


def utc_to_local(utc_dt, market):
    off = base_offset(market) + (1 if dst_active(utc_dt) else 0)
    return utc_dt + dt.timedelta(hours=off)


def local_to_utc(local_dt, market):
    """Local wall clock to UTC; a time in the spring gap takes standard time."""
    b = base_offset(market)
    summer = local_dt - dt.timedelta(hours=b + 1)
    if dst_active(summer):
        return summer
    return local_dt - dt.timedelta(hours=b)


def fmt_utc(utc_dt):
    return utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')


# --------------------------------------------------------------------------
# registries
# --------------------------------------------------------------------------

class Registries(object):
    def __init__(self, est):
        self.est = est
        self._cr_status()
        self._errata()
        self._crosswalk()
        self._branches()
        self._calendar()
        self._fixings()
        self._model_doc()
        self._runs()
        self._customers()

    # -- change requests ---------------------------------------------------
    def _cr_status(self):
        latest = {}
        for i, r in enumerate(self.est.records('governance_precedence_policy.docx')):
            cells = r['_cells']
            if len(cells) < 4:
                continue
            cr = canon_id(cells[0])
            status = ci(cells[2])
            d = parse_date(cells[3])
            if cr is None:
                continue
            key = (d or dt.date.min, i)
            cur = latest.get(cr)
            if cur is None or key > cur[0]:
                latest[cr] = (key, status)
        self.cr_status = {k: v[1] for k, v in latest.items()}

    def cr_approved(self, cr):
        return self.cr_status.get(canon_id(cr)) == 'APPROVED'

    # -- errata ------------------------------------------------------------
    def _errata(self):
        self.rule_errata = []
        for heading, rows in md_tables(self.est.path('errata_register.md')):
            if 'rule errata' not in heading.lower():
                continue
            for r in rows[1:]:
                if len(r) < 4:
                    continue
                self.rule_errata.append({
                    'erratum': canon_id(r[0]), 'document': r[1],
                    'change': r[2], 'cr': canon_id(r[3]),
                    'in_force': self.cr_approved(r[3]),
                })
        best = {}
        for r in self.est.records('errata_register.md'):
            cells = r['_cells']
            if len(cells) < 6:
                continue
            if ci(cells[4]) != 'APPLIED':
                continue
            acct = canon_acct(cells[1])
            per = parse_month(cells[2])
            dpd = parse_decimal(cells[3])
            raised = parse_date(cells[5])
            eid = canon_id(cells[0])
            if acct is None or per is None or dpd is None:
                continue
            key = (acct, per)
            rank = (raised or dt.date.min, eid or '')
            cur = best.get(key)
            if cur is None or rank > cur[0]:
                best[key] = (rank, int(dpd))
        self.errata_dpd = {k: v[1] for k, v in best.items()}
        # DPD thresholds
        self.thresholds = dict((s, 90) for s in SEGMENTS)
        self.cut_overrides = []
        for e in self.rule_errata:
            if not e['in_force']:
                continue
            ch = e['change']
            doc = e['document'].lower()
            if 'bad_definition_standard' in doc and '2.1' in doc:
                m = re.search(r'threshold for (\w+) is (\d+)', ch)
                if m:
                    self.thresholds[m.group(1).upper()] = int(m.group(2))
            elif 'model_documentation' in doc:
                m = re.search(r'(\w+) cut point c(\d).*correct value is (\d+)', ch)
                if m:
                    self.cut_overrides.append(
                        (m.group(1).upper(), int(m.group(2)), int(m.group(3))))
        self.hold_to_inclusive = any(
            e['in_force'] and 'litigation hold' in e['change']
            for e in self.rule_errata)

    # -- product crosswalk -------------------------------------------------
    def _crosswalk(self):
        self.segment_of_code = {}
        for r in self.est.records('product_code_crosswalk.ini'):
            seg = ci(r['_section'])
            if seg not in SEGMENTS:
                continue
            self.segment_of_code[ci(r['key'])] = seg
        self.migrations = {}
        for r in self.est.records('product_migrations_2025.xlsx'):
            acct = canon_acct(r.get('account'))
            if acct is None:
                continue
            eff = parse_date(r.get('effective'))
            self.migrations.setdefault(acct, []).append(
                (eff, canon_id(r.get('migration_id')) or '',
                 ci(r.get('from_code'))))

    def code_at_decision(self, acct, code, decision_date):
        best = None
        for eff, mid, from_code in self.migrations.get(acct, ()):
            if eff is None or eff <= decision_date:
                continue
            key = (eff, mid)
            if best is None or key < best[0]:
                best = (key, from_code)
        if best is not None:
            return best[1]
        return code

    # -- branches ----------------------------------------------------------
    def _branches(self):
        self.recode = {}
        for r in self.est.records('branch_directory_2026.html'):
            cells = r['_cells']
            if len(cells) < 2:
                continue
            self.recode[canon_id(cells[0])] = canon_id(cells[1])
        self.branch_rows = {}
        for r in self.est.records('branch_directory.html'):
            cells = r['_cells']
            if len(cells) < 4:
                continue
            br = canon_id(cells[1])
            mkt = ci(cells[0])
            frm = parse_date(cells[2])
            to = parse_date(cells[3])
            self.branch_rows.setdefault(br, []).append((frm, to, mkt))

    def market_of(self, branch, when):
        br = canon_id(branch)
        if br and br.startswith('BR'):
            br = self.recode.get(br, br)
        rows = self.branch_rows.get(br)
        if not rows:
            return None
        for frm, to, mkt in rows:
            if frm is not None and when < frm:
                continue
            if to is not None and when > to:
                continue
            return mkt
        return None

    # -- market calendars --------------------------------------------------
    def _calendar(self):
        self.closed = {}
        for r in self.est.records('market_holidays.ics'):
            mkt = ci(r.get('X-MARKET'))
            cat = ci(r.get('CATEGORIES'))
            if cat not in ('PUBLIC-HOLIDAY', 'BANK-CLOSURE'):
                continue
            start = parse_date((r.get('DTSTART') or '').split('T')[0])
            if start is None:
                continue
            endraw = (r.get('DTEND') or '').split('T')[0]
            end = parse_date(endraw)
            s = self.closed.setdefault(mkt, set())
            if end is None or end <= start:
                s.add(start)
            else:
                d = start
                while d < end:
                    s.add(d)
                    d += dt.timedelta(days=1)

    def last_business_day(self, ym, market):
        d = month_last_day(ym)
        closed = self.closed.get(market, ())
        while True:
            if d.weekday() < 5 and d not in closed:
                return d
            d -= dt.timedelta(days=1)

    # -- treasury fixings and currency codes -------------------------------
    def _fixings(self):
        self.fixings = {}
        for r in self.est.records('treasury_fixings_2024_2026.xml'):
            ccy = ci(r.get('ccy'))
            d = parse_date(r.get('date'))
            if d is None:
                continue
            rev = digits_int(r.get('rev') or '1')
            per = parse_decimal(r.get('per') or '1')
            val = parse_decimal(r.get('_text'))
            if val is None or per is None or per == 0:
                continue
            key = (ccy, d)
            cur = self.fixings.get(key)
            if cur is None or rev > cur[0]:
                self.fixings[key] = (rev, val, per)
        self.fix_dates = {}
        for (ccy, d) in self.fixings:
            self.fix_dates.setdefault(ccy, []).append(d)
        for ccy in self.fix_dates:
            self.fix_dates[ccy].sort()
        self.iso_alpha = {}
        root = _xml_root(self.est.path('fx_rates_ecb_mirror.xml'))
        for el in root.iter():
            if isinstance(el.tag, str) and _lname(el) == 'currency':
                num = digits_int(el.get('numeric'))
                alpha = ci(el.get('alpha'))
                if num and alpha:
                    self.iso_alpha[num] = alpha
        self.redenom = {}
        for r in self.est.records('currency_redenomination.ini'):
            acct = canon_acct(r['key'])
            if acct:
                self.redenom[acct] = digits_int(r['value'])

    def rate_for(self, ccy, when):
        dates = self.fix_dates.get(ccy)
        if not dates:
            return None
        i = bisect.bisect_right(dates, when)
        if i == 0:
            return None
        rev, val, per = self.fixings[(ccy, dates[i - 1])]
        return (val, per)

    # -- model documentation ----------------------------------------------
    def _model_doc(self):
        lines = pdf_lines(self.est.path('model_documentation_v4.pdf'))
        self.cuts = {}
        for ln in lines:
            cells = [c.strip() for c in ln.split('|')]
            if len(cells) == 10 and ci(cells[0]) in SEGMENTS:
                try:
                    self.cuts[ci(cells[0])] = [int(c) for c in cells[1:]]
                except ValueError:
                    pass
        for seg, k, val in self.cut_overrides:
            if seg in self.cuts:
                self.cuts[seg][k - 1] = val
        self.pd_grid = {}
        for r in self.est.records('model_documentation_v4.pdf'):
            seg, score, pdv = r['_cells']
            seg = ci(seg)
            if seg not in SEGMENTS:
                continue
            self.pd_grid[(seg, digits_int(score))] = parse_decimal(pdv)
        # Appendix B retrospective corrections (last listed row stands)
        lines = pdf_lines(self.est.path('calibration_reissue_2026.pdf'))
        in_app = False
        for ln in lines:
            if ln.lower().startswith('appendix b'):
                in_app = True
                continue
            if not in_app:
                continue
            cells = [c.strip() for c in ln.split('|')]
            if len(cells) != 3:
                continue
            seg = ci(cells[0])
            if seg not in SEGMENTS:
                continue
            if not re.match(r'^\d+$', cells[1].replace(' ', '')):
                continue
            val = parse_decimal(cells[2])
            if val is None:
                continue
            self.pd_grid[(seg, digits_int(cells[1]))] = val
        # development distribution (specification appendix A)
        self.dev_counts = {}
        for r in self.est.records('monitoring_spec_v4.md'):
            cells = r['_cells']
            if len(cells) < 3:
                continue
            seg = ci(cells[0])
            if seg not in SEGMENTS:
                continue
            self.dev_counts[(seg, digits_int(cells[1]))] = digits_int(cells[2])

    def band_of(self, seg, score):
        cuts = self.cuts[seg]
        for i, c in enumerate(cuts):
            if score <= c:
                return i + 1
        return 10

    # -- run register and approvals ---------------------------------------
    def _runs(self):
        self.runs = {}
        self.run_model_raw = {}
        for fname in ('model_registry_v4.toml', 'scoring_runs_2025q2.toml'):
            for r in self.est.records(fname):
                rid = canon_id(r.get('run_id'))
                if rid is None:
                    continue
                self.runs[rid] = {
                    'node': ci(r.get('node')),
                    'model': ci(r.get('model')),
                    'status': ci(r.get('status')),
                }
                self.run_model_raw[rid] = str(r.get('model') or '').strip()
        doc = _toml_load(self.est.path('model_registry_v4.toml'))
        self.approvals = []
        for a in doc.get('approval') or []:
            eff = parse_date(a.get('effective_from'))
            segs = set(ci(s) for s in (a.get('segments') or []))
            self.approvals.append((ci(a.get('model')), segs, eff))
        self.withdrawals = {}
        for fname in ('model_registry_v4.toml', 'model_registry_v4_1.toml'):
            d = _toml_load(self.est.path(fname))
            for w in d.get('withdrawal') or []:
                if not self.cr_approved(w.get('change_request')):
                    continue
                model = ci(w.get('model'))
                wd = parse_date(w.get('withdrawn_from'))
                if wd is None:
                    continue
                cur = self.withdrawals.get(model)
                if cur is None or wd < cur:
                    self.withdrawals[model] = wd
        self.voided_runs = set()
        for r in self.est.records('scoring_engine_node9.log'):
            if r.get('_kind') == 'VOID':
                rid = canon_id(r.get('run'))
                if rid:
                    self.voided_runs.add(rid)
        self.clock = {}
        for r in self.est.records('score_clock_skew_corrections.json'):
            rid = canon_id(r.get('run'))
            off = r.get('offset_seconds')
            if rid is None:
                continue
            if isinstance(off, str):
                off = off.strip()
                sign = -1 if off.startswith('-') else 1
                off = sign * digits_int(off)
            self.clock[rid] = int(off or 0)

    def model_approved(self, model, seg, when):
        ok = False
        for m, segs, eff in self.approvals:
            if m != model or eff is None:
                continue
            if seg in segs and eff <= when:
                ok = True
        if not ok:
            return False
        wd = self.withdrawals.get(model)
        if wd is not None and when >= wd:
            return False
        return True

    # -- customers ---------------------------------------------------------
    def _customers(self):
        self.alias = {}
        for r in self.est.records('customer_master.db'):
            if r.get('_table') != 'customer_alias':
                continue
            a = canon_cust(r.get('alias'))
            m = canon_cust(r.get('master'))
            if a and m:
                self.alias[a] = m
        self.legacy_cust = {}
        for r in self.est.records('merge_candidates_ml.xlsx'):
            if r.get('_sheet') != 'legacy_refs':
                continue
            lc = canon_cust(r.get('legacy_customer'))
            c = canon_cust(r.get('customer'))
            if lc and c:
                self.legacy_cust[lc] = c
        merges = {}
        for i, r in enumerate(self.est.records('customer_merge_decisions.docx')):
            cells = r['_cells']
            if len(cells) < 4:
                continue
            if ci(cells[2]) != 'APPROVED':
                continue
            merged = self._cust(cells[0])
            surviving = self._cust(cells[1])
            d = parse_date(cells[3])
            if not merged or not surviving:
                continue
            key = (d or dt.date.min, 0, i)
            cur = merges.get(merged)
            if cur is None or key > cur[0]:
                merges[merged] = (key, surviving)
        for i, r in enumerate(self.est.records('customer_merges_2026.tsv')):
            if ci(r.get('decision')) != 'APPROVED':
                continue
            merged = self._cust(r.get('merged_customer'))
            surviving = self._cust(r.get('surviving_customer'))
            d = parse_date(r.get('decided_on'))
            if not merged or not surviving:
                continue
            key = (d or dt.date.min, 1, i)
            cur = merges.get(merged)
            if cur is None or key > cur[0]:
                merges[merged] = (key, surviving)
        self.merges = {k: v[1] for k, v in merges.items()}
        self._resolve_cache = {}

    def _cust(self, raw):
        c = canon_cust(raw)
        if c is None:
            return None
        if c.startswith('LCU'):
            return self.legacy_cust.get(c)
        return c

    def resolve_customer(self, raw):
        c = self._cust(raw)
        if c is None:
            return None
        hit = self._resolve_cache.get(c)
        if hit is not None:
            return hit
        cur = self.alias.get(c, c)
        seen = {cur}
        while True:
            nxt = self.merges.get(cur)
            if nxt is None or nxt in seen:
                break
            cur = nxt
            seen.add(cur)
        self._resolve_cache[c] = cur
        return cur


# --------------------------------------------------------------------------
# application partitions
# --------------------------------------------------------------------------

PARTITIONS = ['applications_2025_01.csv', 'applications_2025_02.tsv',
              'applications_2025_03.txt', 'applications_2025_04.csv',
              'applications_2025_05.xlsx', 'applications_2025_06.jsonl']


def _epoch_ms(v):
    if v is None:
        return None
    n = parse_decimal(v)
    if n is None:
        return None
    return dt.datetime(1970, 1, 1) + dt.timedelta(
        seconds=int(n) // 1000, milliseconds=int(n) % 1000)


def read_partition(est, name):
    """Normalised application records of one partition."""
    recs = est.records(name)
    out = []
    for idx, r in enumerate(recs):
        d = {'file': name, 'idx': idx, 'basis_current': False}
        if name == 'applications_2025_01.csv':
            d['acct'] = canon_acct(r.get('account_ref'))
            d['cust'] = r.get('customer_ref')
            d['branch'] = r.get('branch_code')
            d['code'] = ci(r.get('product_code'))
            d['limit'] = to_cents(r.get('limit_amount'))
            d['revision'] = digits_int(r.get('revision'))
            d['received'] = parse_iso_instant(r.get('received_at_utc'))
            d['app_id'] = canon_id(r.get('app_id'))
            d['local'] = parse_naive_dt(r.get('decided_at_local'))
        elif name == 'applications_2025_02.tsv':
            d['acct'] = canon_acct(r.get('acct'))
            d['cust'] = r.get('cust')
            d['branch'] = r.get('branch')
            d['code'] = ci(r.get('product'))
            d['limit'] = to_cents(r.get('limit'))
            d['revision'] = digits_int(r.get('rev'))
            d['received'] = parse_iso_instant(r.get('received_utc'))
            d['app_id'] = canon_id(r.get('app_id'))
            d['utc'] = parse_iso_instant(r.get('decision_utc'))
        elif name == 'applications_2025_03.txt':
            d['acct'] = canon_acct(r.get('account'))
            d['cust'] = r.get('customer')
            d['branch'] = r.get('branch')
            d['code'] = ci(r.get('product'))
            raw = (r.get('limit') or '').strip()
            d['limit'] = (Decimal(digits_int(raw)) / 100).quantize(CENT) \
                if raw else None
            d['revision'] = digits_int(r.get('revision'))
            d['received'] = parse_naive_dt(r.get('received'))
            d['app_id'] = canon_id(r.get('app_id'))
            d['local'] = parse_naive_dt(r.get('decided'))
        elif name == 'applications_2025_04.csv':
            d['acct'] = canon_acct(r.get('konto'))
            d['cust'] = r.get('kunde')
            d['branch'] = r.get('filial')
            d['code'] = ci(r.get('produkt'))
            d['limit'] = to_cents(r.get('limit'), comma_decimal=True)
            d['revision'] = digits_int(r.get('revision'))
            d['received'] = parse_iso_instant(r.get('eingang_utc'))
            d['app_id'] = None
            d['utc'] = parse_iso_instant(r.get('entscheidung'))
        elif name == 'applications_2025_05.xlsx':
            d['acct'] = canon_acct(r.get('account'))
            d['cust'] = r.get('customer')
            d['branch'] = r.get('branch')
            d['code'] = ci(r.get('product_code_current'))
            d['limit'] = to_cents(r.get('limit'))
            d['revision'] = digits_int(r.get('revision'))
            d['received'] = parse_iso_instant(r.get('received_utc'))
            d['app_id'] = canon_id(r.get('app_id'))
            d['local'] = excel_serial_to_dt(r.get('decided_local'))
            d['basis_current'] = True
        else:
            d['acct'] = canon_acct(r.get('acct'))
            d['cust'] = r.get('cust')
            d['branch'] = r.get('branch')
            d['code'] = ci(r.get('product'))
            d['limit'] = to_cents(r.get('limit'))
            d['revision'] = digits_int(r.get('rev'))
            d['received'] = _epoch_ms(r.get('received_ms'))
            d['app_id'] = canon_id(r.get('app'))
            d['utc'] = _epoch_ms(r.get('decided_ms'))
        if d['acct'] is None:
            continue
        out.append(d)
    return out


SNAP_FIELDS = {
    'snapshots_2025_02.csv': ('account', 'period', 'dpd', 'status'),
    'snapshots_2025_03.tsv': ('acct', 'period_yyyymm', 'days_past_due',
                              'status_cd'),
    'snapshots_2025_04.parquet': ('account', 'period', 'dpd', 'status'),
    'snapshots_2025_05.xlsx': ('account', 'period', 'dpd', 'status'),
    'snapshots_2025_06_a.csv': ('konto', 'okres', 'dpd', 'status'),
    'snapshots_2025_06_b.jsonl': ('a', 'p', 'dpd', 's'),
    'servicing_snapshots_2025q3.db': ('account', 'period', 'dpd', 'status'),
    'snapshots_2025_08_a.csv': ('account', 'period', 'dpd', 'status'),
    'snapshots_2025_08_b.tsv': ('acct', 'period_yyyymm', 'days_past_due',
                                'status_cd'),
    'snapshots_2025_09.xlsx': ('account', 'period', 'dpd', 'status'),
    'snapshots_2025_10_a.csv': ('account', 'period', 'dpd', 'status'),
    'snapshots_2025_10_b.tsv': ('acct', 'period_yyyymm', 'days_past_due',
                                'status_cd'),
    'snapshots_2025_11_a.csv': ('account', 'period', 'dpd', 'status'),
    'snapshots_2025_11_a_rev2.csv': ('account', 'period', 'dpd', 'status'),
    'snapshots_2025_11_b.parquet': ('account', 'period', 'dpd', 'status'),
    'snapshots_2025_12.xlsx': ('account', 'period', 'dpd', 'status'),
    'servicing_snapshots_2026q1.db': ('account', 'period', 'dpd', 'status'),
    'snapshots_2026_02_a.csv': ('account', 'period', 'dpd', 'status'),
    'snapshots_2026_02_b.jsonl': ('a', 'p', 'dpd', 's'),
    'snapshots_2026_03.xlsx': ('account', 'period', 'dpd', 'status'),
    'snapshots_2026_04.txt': ('account', 'period', 'dpd', 'status'),
    'snapshots_2026_05_a.parquet': ('account', 'period', 'dpd', 'status'),
    'snapshots_2026_05_b.txt': ('account', 'period', 'dpd', 'status'),
    'snapshots_2026_06.csv': ('account', 'period', 'dpd', 'status'),
}

NOT_REPORTED = {'', 'N/A', 'NULL', 'NONE', 'NA', '-', '?'}


def parse_dpd(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        n = v
    else:
        s = str(v).strip()
        if s.upper() in NOT_REPORTED:
            return None
        d = parse_decimal(s)
        if d is None:
            return None
        n = int(d)
    if n == -1 or n == 9999:
        return None
    return n


WRITTEN_OFF = {'CO', 'S', 'W', 'WRITTENOFF', 'WRITTEN-OFF', 'WO'}
CLOSED_ST = {'CLOSED', 'Z', 'C'}
OPEN_ST = {'OPEN', 'A', 'O'}


def parse_status(v):
    s = ci(v)
    if s in WRITTEN_OFF:
        return 'W'
    if s in CLOSED_ST:
        return 'C'
    if s in OPEN_ST:
        return 'O'
    return s


def parse_pi(v):
    """Inclusion probability: decimal, comma decimal, ratio or percentage."""
    if v is None:
        return None
    if isinstance(v, Fraction):
        return v
    s = str(v).strip()
    if not s:
        return None
    if s.endswith('%'):
        body = s[:-1]
        d = parse_decimal(body, comma_decimal=(',' in body and '.' not in body))
        return None if d is None else Fraction(d) / 100
    if '/' in s:
        parts = s.split('/', 1)
        try:
            return Fraction(int(parts[0].strip()), int(parts[1].strip()))
        except (ValueError, ZeroDivisionError):
            return None
    d = parse_decimal(s, comma_decimal=(',' in s and '.' not in s))
    return None if d is None else Fraction(d)


def parse_mail_date(s):
    if not s:
        return None
    from email.utils import parsedate_to_datetime
    try:
        d = parsedate_to_datetime(s.strip())
    except (TypeError, ValueError):
        return None
    if d is None:
        return None
    if d.tzinfo is not None:
        d = d.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return d


class Monitor(object):
    def __init__(self, root):
        self.est = Estate(root)
        self.reg = Registries(self.est)

    # ------------------------------------------------------------------
    def build_universe(self):
        est = self.est
        reg = self.reg
        april_app = {}
        for r in est.records('applications_2025_04_reextract.csv'):
            a = canon_acct(r.get('account'))
            app = canon_id(r.get('app_id'))
            if a and app:
                april_app[a] = app
        best = {}
        for name in PARTITIONS:
            delivered = est.delivered_at.get(name) or dt.datetime.min
            for d in read_partition(est, name):
                if name == 'applications_2025_04.csv':
                    d['app_id'] = april_app.get(d['acct'])
                rank = (d['revision'], d['received'] or dt.datetime.min,
                        delivered, d['idx'])
                cur = best.get(d['acct'])
                if cur is None or rank > cur[0]:
                    best[d['acct']] = (rank, d)
        apps = {}
        for acct, (rank, d) in best.items():
            rec = dict(d)
            rec['acct'] = acct
            if 'utc' in rec and rec['utc'] is not None:
                lookup_date = rec['utc'].date()
            elif rec.get('local') is not None:
                lookup_date = rec['local'].date()
            else:
                continue
            market = reg.market_of(rec['branch'], lookup_date)
            rec['market'] = market
            if market is None:
                rec['decision_utc'] = rec.get('utc')
                rec['decision_local'] = rec.get('local')
            elif rec.get('utc') is not None:
                rec['decision_utc'] = rec['utc']
                rec['decision_local'] = utc_to_local(rec['utc'], market)
            else:
                rec['decision_local'] = rec['local']
                rec['decision_utc'] = local_to_utc(rec['local'], market)
            apps[acct] = rec
        self.apps = apps
        return apps

    # ------------------------------------------------------------------
    def build_cohort(self):
        est = self.est
        reg = self.reg
        apps = self.apps
        excl = {}
        start = dt.date(2025, 1, 1)
        end = dt.date(2025, 7, 1)
        survivors = []
        for acct in sorted(apps):
            rec = apps[acct]
            ld = rec['decision_local'].date()
            if not (start <= ld < end):
                excl[acct] = 'WINDOW'
                continue
            rec['cohort_month'] = (ld.year, ld.month)
            code = rec['code']
            if rec['basis_current']:
                code = reg.code_at_decision(acct, code, ld)
            rec['segment'] = reg.segment_of_code.get(ci(code))
            rec['customer'] = reg.resolve_customer(rec['cust'])
            survivors.append(acct)
        # 3.5 withdrawals
        reversed_flag = {}
        for r in est.records('applications_master_2025h1.parquet'):
            a = canon_acct(r.get('account'))
            if a is None:
                continue
            reversed_flag[a] = bool(r.get('withdrawal_reversed'))
        withdrawals = {}
        for r in est.records('application_withdrawals.json'):
            a = canon_acct(r.get('account'))
            d = parse_date(r.get('withdrawn_on'))
            if a is None or d is None:
                continue
            withdrawals.setdefault(a, []).append(d)
        kept = []
        for acct in survivors:
            rec = apps[acct]
            ld = rec['decision_local'].date()
            hit = False
            for wd in withdrawals.get(acct, ()):
                delta = (wd - ld).days
                if 0 <= delta <= 14 and not reversed_flag.get(acct, False):
                    hit = True
                    break
            if hit:
                excl[acct] = 'WITHDRAWN'
            else:
                kept.append(acct)
        # 3.6 duplicates
        groups = {}
        for acct in kept:
            rec = apps[acct]
            groups.setdefault((rec['customer'], rec['segment']), []).append(acct)
        remaining = []
        for key in sorted(groups, key=lambda k: (str(k[0]), str(k[1]))):
            members = sorted(groups[key],
                             key=lambda a: (apps[a]['decision_utc'], a))
            last = None
            for acct in members:
                ld = apps[acct]['decision_local'].date()
                if last is not None and (ld - last).days <= 30:
                    excl[acct] = 'DUPLICATE'
                else:
                    last = ld
                    remaining.append(acct)
        self.exclusions = excl
        self.scored_candidates = sorted(remaining)
        return self.scored_candidates

    # ------------------------------------------------------------------
    def score_events(self):
        """All scoring events of the estate for candidate accounts."""
        est = self.est
        wanted = set(self.scored_candidates)
        out = {}
        for name in ('scoring_engine_node1.log', 'scoring_engine_node2.log',
                     'scoring_engine_node3.log', 'scoring_engine_node4.log',
                     'scoring_engine_node9.log'):
            for r in est.records(name):
                if r.get('_kind') != 'SCORE':
                    continue
                acct = canon_acct(r.get('acct'))
                if acct not in wanted:
                    continue
                ts = parse_iso_instant(r.get('_ts'))
                if ts is None:
                    continue
                out.setdefault(acct, []).append(
                    (canon_id(r.get('event')), canon_id(r.get('run')), ts,
                     digits_int(r.get('score'))))
        for r in est.records('score_events_node5.parquet'):
            acct = canon_acct(r.get('account'))
            if acct not in wanted:
                continue
            s = r.get('scored_at_s')
            if s is None:
                continue
            ts = dt.datetime(1970, 1, 1) + dt.timedelta(seconds=int(s))
            out.setdefault(acct, []).append(
                (canon_id(r.get('event_id')), canon_id(r.get('run_id')), ts,
                 digits_int(r.get('score'))))
        for r in est.records('score_events_node6.xml'):
            acct = canon_acct(r.get('account'))
            if acct not in wanted:
                continue
            ts = parse_iso_instant(r.get('scoredAt'))
            if ts is None:
                continue
            out.setdefault(acct, []).append(
                (canon_id(r.get('id')), canon_id(r.get('run')), ts,
                 digits_int(r.get('score'))))
        for r in est.records('score_events_node7.tsv'):
            acct = canon_acct(r.get('account'))
            if acct not in wanted:
                continue
            ts = excel_serial_to_dt(r.get('scored_at_serial_utc'))
            if ts is None:
                continue
            out.setdefault(acct, []).append(
                (canon_id(r.get('event_id')), canon_id(r.get('run_id')), ts,
                 digits_int(r.get('score'))))
        for name in ('score_batches_2025_q1.jsonl', 'score_batches_2025_q2_a.jsonl',
                     'score_batches_2025_q2_b.jsonl', 'score_batches_2025_q2_c.jsonl'):
            for r in est.records(name):
                acct = canon_acct(r.get('acct'))
                if acct not in wanted:
                    continue
                ts = _epoch_ms(r.get('ts_ms'))
                if ts is None:
                    continue
                out.setdefault(acct, []).append(
                    (canon_id(r.get('event')), canon_id(r.get('run')), ts,
                     digits_int(r.get('score'))))
        for r in est.records('score_events_backfill.csv'):
            acct = canon_acct(r.get('account'))
            if acct not in wanted:
                continue
            ts = parse_iso_instant(r.get('scored_at'))
            if ts is None:
                continue
            out.setdefault(acct, []).append(
                (canon_id(r.get('event_id')), canon_id(r.get('run_id')), ts,
                 digits_int(r.get('score'))))
        return out

    def select_scores(self):
        reg = self.reg
        apps = self.apps
        events = self.score_events()
        chosen = {}
        for acct in self.scored_candidates:
            rec = apps[acct]
            seg = rec['segment']
            ld = rec['decision_local'].date()
            limit_ts = rec['decision_utc']
            best = None
            for event_id, run_id, ts, score in events.get(acct, ()):
                run = reg.runs.get(run_id)
                if run is None:
                    continue
                if run['status'] != 'OK':
                    continue
                if run_id in reg.voided_runs:
                    continue
                if run['node'] == '9':
                    continue
                if not reg.model_approved(run['model'], seg, ld):
                    continue
                corrected = ts + dt.timedelta(
                    seconds=reg.clock.get(run_id, 0))
                if corrected > limit_ts:
                    continue
                rank = (corrected, digits_int(event_id))
                if best is None or rank > best[0]:
                    best = (rank, event_id, run_id, corrected, score,
                            reg.run_model_raw.get(run_id, ''))
            if best is not None:
                chosen[acct] = {
                    'event_id': best[1], 'run_id': best[2],
                    'score_ts': best[3], 'score': best[4],
                    'model_version': best[5],
                }
        self.scores = chosen
        self.after_score = []
        for acct in self.scored_candidates:
            if acct in chosen:
                self.after_score.append(acct)
            else:
                self.exclusions[acct] = 'NO_SCORE'
        return chosen

    # ------------------------------------------------------------------
    def build_snapshots(self):
        est = self.est
        wanted = {}
        for acct in self.after_score:
            wanted[acct] = self.apps[acct]['market']
        snap = {}
        for cert in est.certified:
            period = cert['period']
            markets = cert['markets']
            fname = cert['file']
            afield, pfield, dfield, sfield = SNAP_FIELDS[fname]
            for r in est.records(fname):
                acct = canon_acct(r.get(afield))
                mkt = wanted.get(acct)
                if mkt is None or mkt not in markets:
                    continue
                if parse_month(r.get(pfield)) != period:
                    continue
                snap[(acct, period)] = (parse_dpd(r.get(dfield)),
                                        parse_status(r.get(sfield)))
        # governance 3.12: SYSTEM_ERROR restatement voids the certified DPD
        for r in est.records('snapshots_2025_10_b_restated.tsv'):
            if ci(r.get('dpd_reason')) != 'SYSTEM_ERROR':
                continue
            acct = canon_acct(r.get('acct'))
            period = parse_month(r.get('period_yyyymm'))
            key = (acct, period)
            if key in snap:
                snap[key] = (0, snap[key][1])
        # governance 2: corrections, lowest precedence first
        mailbox = {}
        retracted = set()
        msgs = []
        for r in est.records('ops_corrections.mbox'):
            h = r['_headers']
            body = r['_body']
            mid = canon_id(h.get('message-id'))
            when = parse_mail_date(h.get('date'))
            m = re.search(r'retracts:\s*(\S+)', body)
            if m:
                retracted.add(canon_id(m.group(1)))
                continue
            acct = None
            period = None
            dpd = None
            for line in body.splitlines():
                if ':' not in line:
                    continue
                k, v = line.split(':', 1)
                k = k.strip().lower()
                v = v.strip()
                if k == 'account':
                    acct = canon_acct(v)
                elif k == 'period':
                    period = parse_month(v)
                elif k == 'dpd':
                    dpd = parse_decimal(v)
            if acct is None or period is None or dpd is None:
                continue
            msgs.append((mid, when, acct, period, int(dpd)))
        for mid, when, acct, period, dpd in msgs:
            if mid in retracted:
                continue
            key = (acct, period)
            rank = (when or dt.datetime.min, mid or '')
            cur = mailbox.get(key)
            if cur is None or rank > cur[0]:
                mailbox[key] = (rank, dpd)
        feed = {}
        for r in est.records('snapshot_corrections_feed.xml'):
            acct = canon_acct(r.get('account'))
            period = parse_month(r.get('period'))
            dpd = parse_decimal(r.get('dpd'))
            seq = digits_int(r.get('seq'))
            if acct is None or period is None or dpd is None:
                continue
            key = (acct, period)
            cur = feed.get(key)
            if cur is None or seq > cur[0]:
                feed[key] = (seq, int(dpd))
        for key, (rank, dpd) in mailbox.items():
            if key in snap:
                snap[key] = (dpd, snap[key][1])
        for key, (seq, dpd) in feed.items():
            if key in snap:
                snap[key] = (dpd, snap[key][1])
        for key, dpd in self.reg.errata_dpd.items():
            if key in snap:
                snap[key] = (dpd, snap[key][1])
        self.snap = snap
        return snap

    # ------------------------------------------------------------------
    def build_performance(self):
        est = self.est
        reg = self.reg
        # forbearance grants
        revoked = set()
        for r in est.records('bad_definition_standard_v5.docx'):
            cells = r['_cells']
            if len(cells) < 4:
                continue
            if ci(cells[3]) != 'REVOKED':
                continue
            g = canon_id(cells[0])
            if g:
                revoked.add(g)
        ext = {}
        for r in est.records('forbearance_extensions_register.pdf'):
            g = canon_id(r['_cells'][0])
            ym = parse_month(r['_cells'][1])
            if g is None or ym is None:
                continue
            cur = ext.get(g)
            if cur is None or ym > cur:
                ext[g] = ym
        forb = {}
        for r in est.records('bad_definition_standard.docx'):
            cells = r['_cells']
            if len(cells) < 4:
                continue
            g = canon_id(cells[0])
            if g in revoked:
                continue
            acct = canon_acct(cells[1])
            frm = parse_month(cells[2])
            to = parse_month(cells[3])
            if acct is None or frm is None:
                continue
            e = ext.get(g)
            if e is not None and (to is None or e > to):
                to = e
            if to is None:
                continue
            forb.setdefault(acct, []).append((frm, to))
        # charge-offs
        reversal = {}
        for r in est.records('status_events_consolidated.json'):
            if ci(r.get('type')) != 'CO_REVERSAL':
                continue
            ref = canon_id(r.get('ref'))
            d = parse_date(r.get('date'))
            if ref is None or d is None:
                continue
            cur = reversal.get(ref)
            if cur is None or d < cur:
                reversal[ref] = d
        legacy = {}
        for r in est.records('legacy_account_map.ini'):
            legacy[digits_int(r['key'])] = canon_acct(r['value'])

        def account_ref(raw):
            s = strip_ws(str(raw or '')).upper()
            if s.startswith('L') and not s.startswith('LC'):
                return legacy.get(digits_int(s))
            return canon_acct(s)
        chargeoffs = {}
        for name, afield in (('status_events_chargeoff_2025.csv', 'account_ref'),
                             ('chargeoff_events_2026.parquet', 'account')):
            for r in est.records(name):
                acct = account_ref(r.get(afield))
                d = parse_date(r.get('chargeoff_date'))
                eid = canon_id(r.get('event_id'))
                if acct is None or d is None:
                    continue
                chargeoffs.setdefault(acct, []).append((d, eid))
        # closures
        closures = {}
        for r in est.records('account_closures_2025.json'):
            acct = canon_acct(r.get('account'))
            d = parse_date(r.get('closed'))
            if acct is None or d is None:
                continue
            if acct not in closures or d < closures[acct]:
                closures[acct] = d
        for r in est.records('account_closures_2026h1.csv'):
            acct = canon_acct(r.get('account'))
            d = parse_date(r.get('closed_on'))
            if acct is None or d is None:
                continue
            if acct not in closures or d < closures[acct]:
                closures[acct] = d
        self.forb = forb
        self.chargeoffs = chargeoffs
        self.reversal = reversal
        self.closures = closures

    def classify(self, acct):
        reg = self.reg
        rec = self.apps[acct]
        cm = rec['cohort_month']
        seg = rec['segment']
        threshold = reg.thresholds.get(seg, 90)
        start = month_add(cm, 1)
        end = month_add(cm, 12)
        months = [month_add(cm, k) for k in range(1, 13)]
        intervals = self.forb.get(acct, ())
        observed = 0
        max_dpd = 0
        bad_month = None
        missing = []
        for ym in months:
            key = (acct, ym)
            val = self.snap.get(key)
            if val is None or val[0] is None:
                missing.append(ym)
                continue
            dpd, status = val
            observed += 1
            written_off = (status == 'W') or (dpd == 999)
            if dpd == 999:
                dpd = 180
            forborne = any(f <= ym <= t for f, t in intervals)
            eff = 0 if forborne else dpd
            if eff > max_dpd:
                max_dpd = eff
            if (eff >= threshold or written_off) and bad_month is None:
                bad_month = ym
        window_end_date = month_last_day(end)
        decision_date = rec['decision_local'].date()
        co_month = None
        for d, eid in self.chargeoffs.get(acct, ()):
            if not (decision_date < d <= window_end_date):
                continue
            rev = self.reversal.get(eid)
            if rev is not None and 0 <= (rev - d).days <= 60:
                continue
            ym = (d.year, d.month)
            if co_month is None or ym < co_month:
                co_month = ym
        if co_month is not None and (bad_month is None or co_month < bad_month):
            bad_month = co_month
        closure = self.closures.get(acct)
        if bad_month is not None:
            outcome = 'BAD'
        else:
            if closure is not None:
                cmonth = (closure.year, closure.month)
                required = [ym for ym in months if ym <= cmonth]
            else:
                required = months
            if any(ym in missing for ym in required):
                outcome = 'CENSORED'
            elif closure is not None and closure < month_first_day(
                    month_add(cm, 6)):
                outcome = 'INSUFFICIENT'
            elif max_dpd >= 30:
                outcome = 'INDETERMINATE'
            else:
                outcome = 'GOOD'
        return {
            'window_start': month_key(start),
            'window_end': month_key(end),
            'months_observed': observed,
            'max_dpd': max_dpd,
            'bad_month': month_key(bad_month) if bad_month else '',
            'outcome': outcome,
        }

    # ------------------------------------------------------------------
    def build_policy_registers(self):
        est = self.est
        reg = self.reg
        # 2.1 STAFF: employment intervals
        starts = {}
        emp_cust = {}
        for r in est.records('exclusion_policy.docx'):
            cells = r['_cells']
            if len(cells) < 3:
                continue
            emp = canon_id(cells[0])
            cust = reg.resolve_customer(cells[1])
            d = parse_date(cells[2])
            if emp is None or d is None:
                continue
            starts.setdefault(emp, []).append(d)
            if cust:
                emp_cust.setdefault(emp, set()).add(cust)
        leaves = {}
        for r in est.records('employee_leavers.tsv'):
            emp = canon_id(r.get('employee_id'))
            d = parse_date(r.get('leave_date'))
            if emp is None or d is None:
                continue
            leaves.setdefault(emp, []).append(d)
        staff = {}
        for emp, slist in starts.items():
            llist = sorted(leaves.get(emp, []))
            used = [False] * len(llist)
            for s in sorted(slist):
                end = None
                for i, lv in enumerate(llist):
                    if used[i] or lv <= s:
                        continue
                    used[i] = True
                    end = lv
                    break
                for cust in emp_cust.get(emp, ()):
                    staff.setdefault(cust, []).append((s, end))
        self.staff = staff
        # 2.2 LEGAL_HOLD
        holds = {}
        for r in est.records('litigation_hold_register.html'):
            cells = r['_cells']
            if len(cells) < 4:
                continue
            acct = canon_acct(cells[1])
            frm = parse_date(cells[2])
            to = parse_date(cells[3])
            if acct is None or frm is None:
                continue
            holds.setdefault(acct, []).append((frm, to))
        self.holds = holds
        # 2.3 INSOLVENCY
        insolvency = {}
        for r in est.records('regulatory_exclusion_letter_2026.pdf'):
            acct = canon_acct(r['_cells'][0])
            d = parse_date(r['_cells'][1])
            if acct is None or d is None:
                continue
            if acct not in insolvency or d < insolvency[acct]:
                insolvency[acct] = d
        self.insolvency = insolvency
        # 2.4 REDRESS
        self.redress = set()
        for r in est.records('consumer_redress_programme.pdf'):
            acct = canon_acct(r['_cells'][0])
            if acct:
                self.redress.add(acct)
        # 2.5 DECEASED
        deceased = {}

        def note(raw, d):
            cust = reg.resolve_customer(raw)
            if cust is None or d is None:
                return
            if cust not in deceased or d < deceased[cust]:
                deceased[cust] = d
        for r in est.records('deceased_notifications_register.pdf'):
            note(r['_cells'][0], parse_date(r['_cells'][1]))
        for r in est.records('deceased_notifications_feed.xml'):
            note(r.get('customer'), parse_date(r.get('notified')))
        for r in est.records('status_events_consolidated.json'):
            if ci(r.get('type')) != 'DECEASED':
                continue
            if ci(r.get('source')) != 'CIVIL_REGISTRY':
                continue
            ref = (r.get('ref') or '').strip()
            subject = ref if ref else r.get('subject')
            note(subject, parse_date(r.get('date')))
        self.deceased = deceased
        # 2.6 FRAUD
        disposition = {}
        for r in est.records('fraud_case_dispositions.json'):
            case = canon_id(r.get('case_id'))
            if case:
                disposition[case] = ci(r.get('disposition'))
        fraud = {}
        for r in est.records('fraud_alerts_2025.jsonl'):
            case = canon_id(r.get('case'))
            acct = canon_acct(r.get('account'))
            d = parse_date(r.get('alert_date'))
            if case is None or acct is None or d is None:
                continue
            if disposition.get(case) != 'CONFIRMED':
                continue
            if acct not in fraud or d < fraud[acct]:
                fraud[acct] = d
        for r in est.records('fraud_alerts_2026.xml'):
            case = canon_id(r.get('case'))
            acct = canon_acct(r.get('account'))
            d = parse_date(r.get('raised'))
            if case is None or acct is None or d is None:
                continue
            if disposition.get(case) != 'CONFIRMED':
                continue
            if acct not in fraud or d < fraud[acct]:
                fraud[acct] = d
        self.fraud = fraud
        # audit labels
        self.audit = {}
        for r in est.records('audit_label_confirmations.pdf'):
            acct = canon_acct(r['_cells'][0])
            label = ci(r['_cells'][1])
            if acct and label in ('BAD', 'GOOD'):
                self.audit[acct] = label

    def apply_policy_exclusions(self):
        self.build_policy_registers()
        remaining = []
        for acct in self.after_score:
            rec = self.apps[acct]
            cm = rec['cohort_month']
            window_end = month_last_day(month_add(cm, 12))
            ddate = rec['decision_local'].date()
            cust = rec['customer']
            reason = None
            for s, e in self.staff.get(cust, ()):
                if s <= ddate and (e is None or ddate < e):
                    reason = 'STAFF'
                    break
            if reason is None:
                for frm, to in self.holds.get(acct, ()):
                    if ddate < frm:
                        continue
                    if to is None:
                        reason = 'LEGAL_HOLD'
                        break
                    if self.reg.hold_to_inclusive:
                        if ddate <= to:
                            reason = 'LEGAL_HOLD'
                            break
                    elif ddate < to:
                        reason = 'LEGAL_HOLD'
                        break
            if reason is None:
                d = self.insolvency.get(acct)
                if d is not None and d <= window_end:
                    reason = 'INSOLVENCY'
            if reason is None and acct in self.redress:
                reason = 'REDRESS'
            if reason is None:
                d = self.deceased.get(cust)
                if d is not None and d <= window_end:
                    reason = 'DECEASED'
            if reason is None:
                d = self.fraud.get(acct)
                if d is not None and d <= window_end:
                    reason = 'FRAUD'
            if reason is None:
                remaining.append(acct)
            else:
                self.exclusions[acct] = reason
        self.after_policy = remaining
        return remaining

    # ------------------------------------------------------------------
    def build_weights(self):
        est = self.est
        reg = self.reg
        groups = {'GB': 'sampling_inclusion_gb_pl_se.yaml',
                  'PL': 'sampling_inclusion_gb_pl_se.yaml',
                  'SE': 'sampling_inclusion_gb_pl_se.yaml',
                  'CZ': 'sampling_inclusion_cz_hu_ch.yaml',
                  'HU': 'sampling_inclusion_cz_hu_ch.yaml',
                  'CH': 'sampling_inclusion_cz_hu_ch.yaml',
                  'DK': 'sampling_inclusion_dk_no.yaml',
                  'NO': 'sampling_inclusion_dk_no.yaml'}
        self.weight_groups = groups
        registers = {}
        for fname in sorted(set(list(groups.values()) +
                                ['sampling_design_v2.yaml'])):
            table = {}
            for r in est.records(fname):
                key = canon_register_key(r.get('key'))
                if key is None:
                    continue
                pi = parse_pi(r.get('pi'))
                if pi is None:
                    continue
                table[key] = pi
            registers[fname] = table
        self.registers = registers
        overrides = {}
        for r in est.records('sampling_methodology.docx'):
            cells = r['_cells']
            if len(cells) < 3:
                continue
            if ci(cells[2]) != 'APPROVED':
                continue
            acct = canon_acct(cells[0])
            pi = parse_pi(cells[1])
            if acct and pi is not None:
                overrides[acct] = pi
        self.pi_overrides = overrides

    def weight_of(self, acct):
        rec = self.apps[acct]
        cm = rec['cohort_month']
        pi = self.pi_overrides.get(acct)
        if pi is None:
            if cm == (2025, 6):
                table = self.registers['sampling_design_v2.yaml']
            else:
                table = self.registers[self.weight_groups[rec['market']]]
            if cm == (2025, 4) and rec.get('app_id'):
                pi = table.get(rec['app_id'])
                if pi is None:
                    pi = table.get(acct)
            else:
                pi = table.get(acct)
                if pi is None and rec.get('app_id'):
                    pi = table.get(rec['app_id'])
        if pi is None or pi == 0:
            return None
        w = Fraction(1, 1) / pi
        if w.denominator != 1:
            return None
        return int(w)

    # ------------------------------------------------------------------
    def build_exposure_registers(self):
        est = self.est
        amendments = {}
        for r in est.records('limit_amendments_2025.xlsx'):
            acct = canon_acct(r.get('account'))
            eff = excel_serial_to_date(r.get('effective_serial'))
            lim = to_cents(r.get('new_limit'))
            aid = canon_id(r.get('amendment_id')) or ''
            if acct is None or eff is None or lim is None:
                continue
            amendments.setdefault(acct, []).append((eff, aid, lim))
        for r in est.records('limit_management_policy.docx'):
            cells = r['_cells']
            if len(cells) < 4:
                continue
            acct = canon_acct(cells[1])
            eff = parse_date(cells[2])
            lim = to_cents(cells[3])
            aid = canon_id(cells[0]) or ''
            if acct is None or eff is None or lim is None:
                continue
            amendments.setdefault(acct, []).append((eff, aid, lim))
        self.amendments = amendments

    def exposure_of(self, acct):
        reg = self.reg
        rec = self.apps[acct]
        cm = rec['cohort_month']
        ddate = rec['decision_local'].date()
        last = month_last_day(cm)
        limit = rec['limit']
        if limit is None:
            return None
        best = None
        for eff, aid, lim in self.amendments.get(acct, ()):
            if eff < ddate or eff > last:
                continue
            key = (eff, aid)
            if best is None or key > best[0]:
                best = (key, lim)
        if best is not None:
            limit = best[1]
        market = rec['market']
        ccy = MARKET_CCY[market]
        num = reg.redenom.get(acct)
        if num:
            alt = reg.iso_alpha.get(num)
            if alt:
                ccy = alt
        fixing_date = reg.last_business_day(cm, market)
        rate = reg.rate_for(ccy, fixing_date)
        if rate is None:
            return None
        val, per = rate
        amount = (Decimal(limit) * val) / per
        return amount.quantize(CENT, rounding=ROUND_HALF_UP)

    # ------------------------------------------------------------------
    def run(self):
        self.build_universe()
        self.build_cohort()
        self.select_scores()
        self.build_snapshots()
        self.build_performance()
        self.apply_policy_exclusions()
        self.build_weights()
        self.build_exposure_registers()
        self.windows = {}
        cohort = []
        for acct in self.after_policy:
            w = self.classify(acct)
            self.windows[acct] = w
            if w['outcome'] in ('BAD', 'GOOD'):
                cohort.append(acct)
            else:
                self.exclusions[acct] = w['outcome']
        self.cohort = cohort
        self.rows = {}
        for acct in cohort:
            rec = self.apps[acct]
            sc = self.scores[acct]
            seg = rec['segment']
            label = self.audit.get(acct)
            if label is None:
                label = self.windows[acct]['outcome']
            self.rows[acct] = {
                'segment': seg,
                'market': rec['market'],
                'cohort_month': month_key(rec['cohort_month']),
                'decision_utc': fmt_utc(rec['decision_utc']),
                'score': sc['score'],
                'band': self.reg.band_of(seg, sc['score']),
                'bad': 1 if label == 'BAD' else 0,
                'weight': self.weight_of(acct),
                'exposure': self.exposure_of(acct),
            }
        return self


# --------------------------------------------------------------------------
# rounding and formatting
# --------------------------------------------------------------------------

def round_half_even(fr, places):
    """Round a Fraction to `places` decimals, half to even; -> Decimal."""
    scale = 10 ** places
    neg = fr < 0
    if neg:
        fr = -fr
    n = fr.numerator * scale
    d = fr.denominator
    q, r = divmod(n, d)
    if 2 * r > d or (2 * r == d and q % 2 == 1):
        q += 1
    if neg:
        q = -q
    return Decimal(q).scaleb(-places)


def fmt_n(value, places):
    if isinstance(value, Fraction):
        value = round_half_even(value, places)
    elif not isinstance(value, Decimal):
        value = Decimal(value)
    return str(value.quantize(Decimal(1).scaleb(-places),
                              rounding=ROUND_HALF_EVEN))


def ln_decimal(fr):
    """Natural logarithm of a positive Fraction, as a Decimal."""
    return (Decimal(fr.numerator) / Decimal(fr.denominator)).ln()


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------

ZERO = Fraction(0)


def population_metrics(mon):
    out = {}
    groups = {s: [] for s in SEGMENTS}
    groups['ALL'] = []
    for acct in mon.cohort:
        row = mon.rows[acct]
        groups[row['segment']].append(acct)
        groups['ALL'].append(acct)
    for key in SEGMENTS + ['ALL']:
        accts = groups[key]
        accounts = len(accts)
        bads = 0
        wacc = 0
        wbad = 0
        exposure = Decimal(0)
        exposure_bad = Decimal(0)
        for acct in accts:
            row = mon.rows[acct]
            w = row['weight']
            wacc += w
            exp = row['exposure'] * w
            exposure += exp
            if row['bad']:
                bads += 1
                wbad += w
                exposure_bad += exp
        bad_rate = Fraction(wbad, wacc) if wacc else ZERO
        ebr = (Fraction(exposure_bad) / Fraction(exposure)
               if exposure else ZERO)
        out[key] = {
            'accounts': accounts,
            'bads': bads,
            'weighted_accounts': wacc,
            'weighted_bads': wbad,
            'bad_rate': fmt_n(bad_rate, 6),
            'exposure_eur': fmt_n(exposure, 2),
            'exposure_bad_rate': fmt_n(ebr, 6),
        }
    return out


def discrimination_metrics(mon):
    out = {}
    groups = {s: [] for s in SEGMENTS}
    groups['ALL'] = []
    for acct in mon.cohort:
        row = mon.rows[acct]
        groups[row['segment']].append(acct)
        groups['ALL'].append(acct)
    for key in SEGMENTS + ['ALL']:
        bad_w = {}
        good_w = {}
        for acct in groups[key]:
            row = mon.rows[acct]
            tgt = bad_w if row['bad'] else good_w
            tgt[row['score']] = tgt.get(row['score'], 0) + row['weight']
        scores = sorted(set(bad_w) | set(good_w))
        tot_bad = sum(bad_w.values())
        tot_good = sum(good_w.values())
        if tot_bad == 0 or tot_good == 0:
            out[key] = {'auc': fmt_n(ZERO, 6), 'gini': fmt_n(ZERO, 6),
                        'ks': fmt_n(ZERO, 6), 'ks_score': 0}
            continue
        # auc: doubled numerator to keep integers
        suffix_good = 0
        num2 = 0
        for s in reversed(scores):
            b = bad_w.get(s, 0)
            g = good_w.get(s, 0)
            num2 += b * (2 * suffix_good + g)
            suffix_good += g
        auc = Fraction(num2, 2 * tot_bad * tot_good)
        gini = 2 * auc - 1
        cb = 0
        cg = 0
        best = None
        for s in scores:
            cb += bad_w.get(s, 0)
            cg += good_w.get(s, 0)
            diff = abs(Fraction(cb, tot_bad) - Fraction(cg, tot_good))
            if best is None or diff > best[0]:
                best = (diff, s)
        out[key] = {
            'auc': fmt_n(auc, 6),
            'gini': fmt_n(gini, 6),
            'ks': fmt_n(best[0], 6),
            'ks_score': best[1],
        }
    return out


FLOOR = Fraction(1, 10000)


def psi_metrics(mon):
    reg = mon.reg
    out = {}
    actual = {s: {} for s in SEGMENTS}
    for acct in mon.cohort:
        row = mon.rows[acct]
        d = actual[row['segment']]
        d[row['band']] = d.get(row['band'], 0) + row['weight']
    for seg in SEGMENTS:
        dev = {}
        total_dev = 0
        for (s, score), count in reg.dev_counts.items():
            if s != seg:
                continue
            band = reg.band_of(seg, score)
            dev[band] = dev.get(band, 0) + count
            total_dev += count
        tot_act = sum(actual[seg].values())
        bins = []
        psi = Decimal(0)
        for band in range(1, 11):
            e = Fraction(dev.get(band, 0), total_dev) if total_dev else ZERO
            a = Fraction(actual[seg].get(band, 0), tot_act) if tot_act else ZERO
            ef = e if e > FLOOR else FLOOR
            af = a if a > FLOOR else FLOOR
            diff = af - ef
            psi += (Decimal(diff.numerator) / Decimal(diff.denominator)
                    * ln_decimal(af / ef))
            bins.append({'band': band, 'expected': fmt_n(e, 6),
                         'actual': fmt_n(a, 6)})
        out[seg] = {'psi': fmt_n(psi, 6), 'bins': bins}
    return out


def calibration_rows(mon):
    reg = mon.reg
    agg = {}
    for acct in mon.cohort:
        row = mon.rows[acct]
        key = (row['segment'], row['band'])
        cur = agg.setdefault(key, [0, 0, 0, Fraction(0)])
        cur[0] += 1
        cur[1] += row['weight']
        if row['bad']:
            cur[2] += row['weight']
        pdv = reg.pd_grid.get((row['segment'], row['score']))
        if pdv is not None:
            cur[3] += Fraction(pdv) * row['weight']
    rows = []
    for seg in SEGMENTS:
        for band in range(1, 11):
            acc, wacc, wbad, exp = agg.get((seg, band),
                                           [0, 0, 0, Fraction(0)])
            if acc == 0:
                rows.append([seg, str(band), '0', '0', '0',
                             fmt_n(ZERO, 6), '', ''])
                continue
            rows.append([seg, str(band), str(acc), str(wacc), str(wbad),
                         fmt_n(exp, 6),
                         fmt_n(Fraction(wbad, wacc), 6),
                         fmt_n(exp / wacc, 6)])
    return rows


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------

CSV_HEADERS = {
    'cohort.csv': ['acct', 'segment', 'market', 'cohort_month', 'decision_utc',
                   'score', 'score_band', 'bad', 'weight', 'exposure_eur'],
    'exclusions.csv': ['acct', 'reason'],
    'score_selection.csv': ['acct', 'event_id', 'run_id', 'model_version',
                            'score_ts_utc', 'score'],
    'performance_windows.csv': ['acct', 'window_start', 'window_end',
                                'months_observed', 'max_dpd', 'bad_month',
                                'outcome'],
    'calibration.csv': ['segment', 'band', 'accounts', 'weighted_accounts',
                        'weighted_bads', 'expected_bads', 'actual_rate',
                        'expected_rate'],
}


def write_csv(path, name, rows):
    lines = [','.join(CSV_HEADERS[name])]
    for r in rows:
        lines.append(','.join(r))
    with open(os.path.join(path, name), 'w', encoding='utf-8',
              newline='') as fh:
        fh.write('\n'.join(lines))
        fh.write('\n')


def write_json(path, name, obj):
    with open(os.path.join(path, name), 'w', encoding='utf-8',
              newline='') as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)
        fh.write('\n')


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: monitor.py ESTATE_DIR OUT_DIR\n')
        return 2
    estate_dir, out_dir = argv[1], argv[2]
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    mon = Monitor(estate_dir)
    recon = mon.est.reconcile()
    write_json(out_dir, 'reconciliation.json', recon)
    status = recon['status']
    if status != 'RECONCILED':
        for name in CSV_HEADERS:
            write_csv(out_dir, name, [])
        for name in ('population_summary.json', 'discrimination.json',
                     'psi.json'):
            write_json(out_dir, name, {'segments': {},
                                       'status': 'UNRECONCILED'})
        return 0
    mon.run()

    cohort_rows = []
    for acct in mon.cohort:
        row = mon.rows[acct]
        cohort_rows.append([
            acct, row['segment'], row['market'], row['cohort_month'],
            row['decision_utc'], str(row['score']), str(row['band']),
            str(row['bad']), str(row['weight']),
            str(row['exposure'].quantize(CENT))])
    write_csv(out_dir, 'cohort.csv', cohort_rows)

    write_csv(out_dir, 'exclusions.csv',
              [[acct, mon.exclusions[acct]] for acct in sorted(mon.exclusions)])

    sel_rows = []
    for acct in mon.scored_candidates:
        sc = mon.scores.get(acct)
        if sc is None:
            sel_rows.append([acct, '', '', '', '', ''])
        else:
            sel_rows.append([acct, sc['event_id'], sc['run_id'],
                             sc['model_version'], fmt_utc(sc['score_ts']),
                             str(sc['score'])])
    write_csv(out_dir, 'score_selection.csv', sel_rows)

    win_rows = []
    for acct in mon.after_policy:
        w = mon.windows[acct]
        win_rows.append([acct, w['window_start'], w['window_end'],
                         str(w['months_observed']), str(w['max_dpd']),
                         w['bad_month'], w['outcome']])
    write_csv(out_dir, 'performance_windows.csv', win_rows)

    write_csv(out_dir, 'calibration.csv', calibration_rows(mon))
    write_json(out_dir, 'population_summary.json',
               {'segments': population_metrics(mon), 'status': status})
    write_json(out_dir, 'discrimination.json',
               {'segments': discrimination_metrics(mon), 'status': status})
    write_json(out_dir, 'psi.json',
               {'segments': psi_metrics(mon), 'status': status})
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

