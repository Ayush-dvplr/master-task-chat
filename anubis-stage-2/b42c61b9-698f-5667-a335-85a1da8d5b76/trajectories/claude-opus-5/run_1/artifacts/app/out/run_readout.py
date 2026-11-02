#!/usr/bin/env python3
"""Corrected WAVE experiment portfolio readout.

Usage: python3 run_readout.py DATA_DIR OUT_DIR

Everything is computed from the corpus in DATA_DIR following
readout_analysis_handbook.md (H-rules), the governance memo and the
experiment workbook; the shipped published readout is used only for the
comparison reports.
"""
import csv
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import zipfile
import zlib
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from statistics import NormalDist
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------- utilities

def nid(v):
    """H1.1 identifier normal form."""
    if v is None:
        return ''
    s = str(v).strip()
    while s and (s[0] in '\'"' or s[-1] in '\'"'):
        s = s.strip('\'"').strip()
    return s.upper()


def ntext(v):
    if v is None:
        return ''
    s = str(v).strip()
    while s and (s[0] in '\'"' or s[-1] in '\'"'):
        s = s.strip('\'"').strip()
    return s


def natural_key(s):
    """Sort key for ids like A1-203: digit runs compare as numbers."""
    return tuple((int(p), '') if p.isdigit() else (-1, p)
                 for p in re.split(r'(\d+)', str(s)) if p != '')


def q6(x):
    """Round an exact value half to even to six decimals, format fixed."""
    if isinstance(x, float) and not math.isfinite(x):
        return format(x, '.6f')
    f = Fraction(x)
    scaled = f * 1000000
    n, d = scaled.numerator, scaled.denominator
    q, r = divmod(n, d)
    r2 = 2 * r
    if r2 > d or (r2 == d and q % 2 == 1):
        q += 1
    sign = '-' if q < 0 else ''
    q = abs(q)
    s = '%s%d.%06d' % (sign, q // 1000000, q % 1000000)
    if s.startswith('-') and float(s) == 0.0:
        s = s[1:]
    return s


def e6(x):
    return format(float(x), '.6e')


def parse_offset(s):
    s = ntext(s)
    m = re.match(r'^([+-])(\d{2}):?(\d{2})$', s)
    if not m:
        if s in ('Z', 'UTC', ''):
            return timedelta(0)
        raise ValueError('offset %r' % s)
    sign = 1 if m.group(1) == '+' else -1
    return sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))


def parse_wall(s):
    s = ntext(s).replace('T', ' ')
    s = re.sub(r'Z$', '', s)
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    raise ValueError('wall time %r' % s)


def fmt_ts(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


EPOCH = datetime(1970, 1, 1)


# -------------------------------------------------------------- tiny parsers

def read_text(path):
    with open(path, 'r', encoding='utf-8-sig') as fh:
        return fh.read()


def yaml_simple(path):
    """Parse the small subset of YAML used by the corpus reference files."""
    lines = read_text(path).split('\n')
    scalars = {}
    lists = {}
    cur = None
    item = None
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if line.startswith('- '):
            body = line[2:]
            item = {}
            if cur is not None:
                lists.setdefault(cur, []).append(item)
            if ':' in body:
                k, v = body.split(':', 1)
                item[k.strip()] = ntext(v)
            continue
        if ':' in line:
            k, v = line.split(':', 1)
            k = k.strip()
            v = v.strip()
            if indent >= 4 and item is not None:
                item[k] = ntext(v)
            elif v == '':
                cur = k
                lists.setdefault(k, [])
                item = None
            else:
                scalars[k] = ntext(v)
                cur = None
                item = None
    return scalars, lists


def yaml_records(path, keys):
    """Flat list of mappings (one key per line) from a YAML-ish shard."""
    out = []
    cur = None
    for raw in read_text(path).split('\n'):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('- '):
            cur = {}
            out.append(cur)
            line = line[2:]
        if cur is None or ':' not in line:
            continue
        k, v = line.split(':', 1)
        k = k.strip()
        if k in keys:
            cur[k] = v.strip()
    return [r for r in out if r]


# -------------------------------------------------------------- xlsx reader

XNS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
DNS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def load_workbook(path):
    z = zipfile.ZipFile(path)
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = {r.get('Id'): r.get('Target')
            for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')):
            shared.append(''.join(t.text or '' for t in si.iter(XNS + 't')))
    date1904 = False
    pr = wb.find(XNS + 'workbookPr')
    if pr is not None and pr.get('date1904') in ('1', 'true'):
        date1904 = True
    sheets = {}
    for sh in wb.find(XNS + 'sheets'):
        target = rels[sh.get(DNS + 'id')]
        if target.startswith('/'):
            target = target[1:]
        elif not target.startswith('xl/'):
            target = 'xl/' + target
        sheets[sh.get('name')] = _sheet_rows(z.read(target), shared)
    return sheets, date1904


def _colnum(ref):
    n = 0
    for c in re.match(r'([A-Z]+)', ref).group(1):
        n = n * 26 + ord(c) - 64
    return n


def _sheet_rows(xml, shared):
    root = ET.fromstring(xml)
    rows = []
    for r in root.iter(XNS + 'row'):
        cells = {}
        for c in r.findall(XNS + 'c'):
            t = c.get('t')
            if t == 'inlineStr':
                isel = c.find(XNS + 'is')
                v = ''.join(x.text or '' for x in isel.iter(XNS + 't')) if isel is not None else ''
            else:
                vel = c.find(XNS + 'v')
                v = vel.text if vel is not None and vel.text is not None else ''
                if t == 's' and v != '':
                    v = shared[int(v)]
            cells[_colnum(c.get('r'))] = v
        if cells:
            rows.append([cells.get(i, '') for i in range(1, max(cells) + 1)])
    return rows


def sheet_dicts(rows, header_row):
    head = [ntext(h) for h in rows[header_row]]
    out = []
    for row in rows[header_row + 1:]:
        if not any(str(c).strip() for c in row):
            continue
        d = {}
        for i, h in enumerate(head):
            d[h] = row[i] if i < len(row) else ''
        out.append(d)
    return out


def cell_datetime(val, date1904):
    s = ntext(val)
    if re.match(r'^-?\d+(\.\d+)?$', s):
        base = datetime(1904, 1, 1) if date1904 else datetime(1899, 12, 30)
        f = Fraction(s)
        days = int(f)
        frac = f - days
        secs = int(frac * 86400)
        return base + timedelta(days=days, seconds=secs)
    return parse_wall(s)


# ---------------------------------------------------------------- pdf reader

def pdf_lines(path):
    data = open(path, 'rb').read()
    kids = re.search(rb'/Type\s*/Pages.*?/Kids\s*\[(.*?)\]', data, re.S).group(1)
    page_objs = [int(x) for x in re.findall(rb'(\d+)\s+0\s+R', kids)]
    objs = {}
    for m in re.finditer(rb'(\d+)\s+0\s+obj(.*?)endobj', data, re.S):
        objs[int(m.group(1))] = m.group(2)
    lines = []
    for pn in page_objs:
        cont = int(re.search(rb'/Contents\s+(\d+)\s+0\s+R', objs[pn]).group(1))
        body = objs[cont]
        raw = body[body.index(b'stream') + 6:body.rindex(b'endstream')]
        txt = zlib.decompress(raw.lstrip(b'\r\n'))
        runs = {}
        for m in re.finditer(rb'1 0 0 1 (-?[\d.]+) (-?[\d.]+) Tm(.*?)(?=1 0 0 1 |\Z)',
                             txt, re.S):
            x, y = float(m.group(1)), float(m.group(2))
            t = _pdf_run_text(m.group(3))
            runs.setdefault(y, []).append((x, t))
        for y in sorted(runs, reverse=True):
            lines.append([t for _, t in sorted(runs[y])])
    return lines


def _pdf_literal(b):
    res = bytearray()
    i = 0
    while i < len(b):
        c = b[i:i + 1]
        if c == b'\\':
            nxt = b[i + 1:i + 2]
            res += {b'n': b'\n', b'r': b'\r', b't': b'\t'}.get(nxt, nxt)
            i += 2
            continue
        res += c
        i += 1
    return res.decode('latin-1')


def _pdf_strings(seg):
    res = ''
    i = 0
    while i < len(seg):
        c = seg[i:i + 1]
        if c == b'(':
            depth = 1
            j = i + 1
            start = j
            while j < len(seg):
                ch = seg[j:j + 1]
                if ch == b'\\':
                    j += 2
                    continue
                if ch == b'(':
                    depth += 1
                elif ch == b')':
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            res += _pdf_literal(seg[start:j])
            i = j + 1
        elif c == b'<':
            j = seg.index(b'>', i)
            res += bytes.fromhex(re.sub(rb'\s', b'', seg[i + 1:j]).decode()).decode('latin-1')
            i = j + 1
        else:
            i += 1
    return res


def _pdf_run_text(rest):
    m = re.search(rb'(\[.*?\]\s*TJ|\(.*?\)\s*Tj|<[0-9A-Fa-f\s]*>\s*Tj)', rest, re.S)
    return _pdf_strings(m.group(1)) if m else ''


def memo_tables(path):
    """Tables of the memo: a title line, a header line, then same-width rows."""
    lines = [c for c in pdf_lines(path) if c]
    tables = {}
    i = 0
    while i < len(lines):
        cells = lines[i]
        m = re.match(r'^Table ([A-Z]+-\d+)\b', cells[0])
        if not (m and len(cells) == 1 and i + 1 < len(lines) and len(lines[i + 1]) >= 3):
            i += 1
            continue
        name = m.group(1)
        head = [c.strip() for c in lines[i + 1]]
        rows = tables.setdefault(name, [])
        i += 2
        while i < len(lines) and len(lines[i]) == len(head):
            rows.append({head[j]: lines[i][j].strip() for j in range(len(head))})
            i += 1
    return tables


# ------------------------------------------------------------ shard reading

def json_pairs_unique(pairs):
    """Keep every pair; duplicate o_json keys differ by leading spaces."""
    out = {}
    for k, v in pairs:
        key = k
        while key in out:
            key = ' ' + key
        out[key] = v
    return out


def dig(obj, path):
    cur = obj
    for part in path.split('.'):
        if cur is None:
            return None
        cur = cur.get(part)
    return cur


def read_shard_rows(path, layout):
    """Return a list of dicts with the logical field names of feed_layouts.md."""
    rows = []
    if layout == 'x_jsonl':
        for line in read_text(path).split('\n'):
            if not line.strip():
                continue
            o = json.loads(line)
            rows.append({'id': o.get('eid'), 'time': o.get('ts'), 'unit': o.get('unit'),
                         'experiment': o.get('exp'), 'variant': o.get('arm'),
                         'status': o.get('st'), 'revision': o.get('rev')})
    elif layout == 'x_ndjson':
        for line in read_text(path).split('\n'):
            if not line.strip():
                continue
            o = json.loads(line)
            rows.append({'id': dig(o, 'event.id'), 'revision': dig(o, 'event.rev'),
                         'time': dig(o, 'at.epoch'), 'unit': dig(o, 'subject.unit'),
                         'experiment': dig(o, 'assign.experiment'),
                         'variant': dig(o, 'assign.variant'), 'status': o.get('state')})
    elif layout == 'x_csv':
        for d in csv.DictReader(read_text(path).split('\n')):
            if d.get('exposure_id') is None:
                continue
            rows.append({'id': d['exposure_id'], 'time': d['logged_at'],
                         'unit': d['unit_token'], 'experiment': d['experiment'],
                         'variant': d['variant'], 'status': d['status'],
                         'revision': d['revision']})
    elif layout == 'x_tsv':
        lines = read_text(path).split('\n')
        head = lines[0].split('\t')
        for line in lines[1:]:
            if not line.strip():
                continue
            d = dict(zip(head, line.split('\t')))
            rows.append({'id': d['exposure'], 'time': d['ms'], 'unit': d['unit'],
                         'experiment': d['exp'], 'variant': d['variant'],
                         'status': d['state'], 'revision': d['rev']})
    elif layout == 'x_psv':
        lines = read_text(path).split('\n')
        head = [h.strip() for h in lines[0].split('|')]
        for line in lines[1:]:
            if not line.strip():
                continue
            d = dict(zip(head, line.split('|')))
            rows.append({'id': d['exposure'], 'time': d['local_time'], 'unit': d['unit'],
                         'experiment': d['experiment'], 'variant': d['variant'],
                         'status': d['status'], 'revision': d['rev']})
    elif layout == 'x_txt':
        for line in read_text(path).split('\n'):
            if not line.strip() or line.startswith('#'):
                continue
            rows.append({'id': line[0:12], 'time': line[12:26], 'unit': line[26:37],
                         'experiment': line[37:53], 'variant': line[53:77],
                         'status': line[77:78], 'revision': line[78:81]})
    elif layout == 'x_xml':
        root = ET.fromstring(read_text(path))
        for x in root.findall('x'):
            rows.append({'id': x.get('id'), 'time': x.get('t'), 'unit': x.get('u'),
                         'experiment': x.get('e'), 'variant': x.get('v'),
                         'status': x.get('s'), 'revision': x.get('r')})
    elif layout == 'x_yaml':
        for r in yaml_records(path, {'id', 'ts', 'unit', 'experiment', 'variant',
                                     'status', 'rev'}):
            rows.append({'id': r.get('id'), 'time': r.get('ts'), 'unit': r.get('unit'),
                         'experiment': r.get('experiment'), 'variant': r.get('variant'),
                         'status': r.get('status'), 'revision': r.get('rev')})
    elif layout == 'x_sqlite':
        con = sqlite3.connect(path)
        for r in con.execute('SELECT exposure_id, epoch_s, unit_token, experiment, '
                             'variant, status, revision FROM exposure'):
            rows.append({'id': r[0], 'time': r[1], 'unit': r[2], 'experiment': r[3],
                         'variant': r[4], 'status': r[5], 'revision': r[6]})
        con.close()
    elif layout == 'x_json':
        doc = json.loads(read_text(path))
        for o in doc['export']['rows']:
            rows.append({'id': o.get('exposureId'), 'time': o.get('epochMillis'),
                         'unit': o.get('unitToken'), 'experiment': o.get('experimentKey'),
                         'variant': o.get('variantKey'), 'status': o.get('state'),
                         'revision': o.get('revision')})
    elif layout == 'o_db':
        con = sqlite3.connect(path)
        for r in con.execute('SELECT oid, ep, uid, ccy, amt, st, rv FROM ord'):
            rows.append({'id': r[0], 'time': r[1], 'unit': r[2], 'currency': r[3],
                         'amount': r[4], 'status': r[5], 'revision': r[6]})
        con.close()
    elif layout == 'o_csv':
        for d in csv.DictReader(read_text(path).split('\n')):
            if d.get('order_id') is None:
                continue
            rows.append({'id': d['order_id'], 'time': d['placed_at'], 'unit': d['customer'],
                         'currency': d['currency'], 'amount': d['amount'],
                         'status': d['order_status'], 'revision': d['revision']})
    elif layout == 'o_xml':
        root = ET.fromstring(read_text(path))
        for o in root.findall('order'):
            g = lambda t: (o.findtext(t) or '')
            rows.append({'id': g('id'), 'time': g('at'), 'unit': g('customer'),
                         'currency': g('ccy'), 'amount': g('minor'), 'status': g('st'),
                         'revision': g('rev')})
    elif layout == 'o_yml':
        for r in yaml_records(path, {'order', 'local', 'cust', 'money', 's', 'rev'}):
            money = ntext(r.get('money', ''))
            parts = money.split()
            rows.append({'id': r.get('order'), 'time': r.get('local'),
                         'unit': r.get('cust'), 'amount': parts[0] if parts else '',
                         'currency': parts[1] if len(parts) > 1 else '',
                         'status': r.get('s'), 'revision': r.get('rev')})
    elif layout == 'o_json':
        doc = json.loads(read_text(path), object_pairs_hook=json_pairs_unique)
        for k, v in doc.items():
            rows.append({'id': k, 'time': v.get('ms'), 'unit': v.get('u'),
                         'currency': v.get('c'), 'amount': v.get('a'),
                         'status': v.get('s'), 'revision': v.get('v')})
    else:
        raise ValueError('layout %s' % layout)
    return rows


def to_utc(value, convention, exp_offsets, exp_code, reporting_offset):
    s = ntext(value)
    if convention == 'iso_z':
        return parse_wall(s)
    if convention == 'iso_offset':
        m = re.match(r'^(.*?)([+-]\d{2}:?\d{2}|Z)$', s)
        if not m:
            return parse_wall(s)
        base = parse_wall(m.group(1))
        off = timedelta(0) if m.group(2) == 'Z' else parse_offset(m.group(2))
        return base - off
    if convention == 'epoch_s':
        return EPOCH + timedelta(seconds=int(Fraction(s)))
    if convention == 'epoch_ms':
        return EPOCH + timedelta(seconds=int(Fraction(s) // 1000))
    if convention == 'compact_utc':
        return datetime.strptime(s, '%Y%m%d%H%M%S')
    if convention == 'local_experiment':
        return parse_wall(s) - exp_offsets.get(exp_code, timedelta(0))
    if convention == 'local_reporting':
        return parse_wall(s) - reporting_offset
    raise ValueError('ts_convention %s' % convention)


# ------------------------------------------------------------------- stats

def mean_f(vals):
    return Fraction(sum(vals), len(vals))


def var_f(vals):
    n = len(vals)
    if n < 2:
        return Fraction(0)
    m = mean_f(vals)
    return sum(((v - m) * (v - m) for v in vals), Fraction(0)) / (n - 1)


def cov_f(xs, ys):
    n = len(xs)
    if n < 2:
        return Fraction(0)
    mx, my = mean_f(xs), mean_f(ys)
    return sum(((x - mx) * (y - my) for x, y in zip(xs, ys)), Fraction(0)) / (n - 1)


def round6_frac(x):
    """Half-to-even rounding of an exact value to a Fraction with 1e-6 step."""
    f = Fraction(x) * 1000000
    n, d = f.numerator, f.denominator
    q, r = divmod(n, d)
    r2 = 2 * r
    if r2 > d or (r2 == d and q % 2 == 1):
        q += 1
    return Fraction(q, 1000000)


def chi2_sf(chi2, dof):
    """Upper tail of the chi-square distribution (H12)."""
    c = float(chi2)
    if dof <= 0:
        return 1.0
    if dof == 1:
        return math.erfc(math.sqrt(c / 2))
    if dof == 2:
        return math.exp(-c / 2)
    if dof == 3:
        return math.erfc(math.sqrt(c / 2)) + math.sqrt(2 * c / math.pi) * math.exp(-c / 2)
    # Q_{k+2}(x) = Q_k(x) + (x/2)^(k/2) exp(-x/2) / gamma(k/2 + 1)
    k = 1 if dof % 2 else 2
    q = math.erfc(math.sqrt(c / 2)) if k == 1 else math.exp(-c / 2)
    while k + 2 <= dof:
        q += (c / 2) ** (k / 2) * math.exp(-c / 2) / math.gamma(k / 2 + 1)
        k += 2
    return q


# =============================================================== main build

def main(data_dir, out_dir):
    ctx = {}
    P = lambda name: os.path.join(data_dir, name)

    # ---- profile
    prof_s, prof_l = yaml_simple(P('analysis_profile_w26.yml'))
    portfolio_id = prof_s['portfolio_id']
    registry_version = prof_s['registry_version']
    fx_sheet_name = prof_s['fx_sheet']
    cutoff = parse_wall(prof_s['data_cutoff_utc'])
    pre_period_days = int(prof_s['pre_period_days'])
    reporting_offset = parse_offset(prof_s['reporting_offset'])

    # ---- aliases
    al_s, al_l = yaml_simple(P('experiment_aliases.yaml'))
    exp_alias = {}
    for e in al_l.get('experiments', []):
        exp_alias[nid(e['alias'])] = nid(e['canonical'])
    variant_map = {}
    for v in al_l.get('variants', []):
        variant_map[(nid(v['experiment']), nid(v['variant']))] = ntext(v['arm']).upper()

    def canon_exp(token):
        t = nid(token)
        return exp_alias.get(t, t)

    scope = []
    for e in prof_l.get('experiments_in_scope', []):
        c = canon_exp(e['experiment'])
        if c not in scope:
            scope.append(c)
    internal_units_tokens = [nid(u['unit']) for u in prof_l.get('internal_units', [])]

    # ---- workbook
    sheets, date1904 = load_workbook(P('experiment_workbook_w26.xlsx'))
    exp_rows = sheet_dicts(sheets['Experiments'], 0)
    experiments = {}
    for r in exp_rows:
        code = nid(r['experiment'])
        experiments[code] = {
            'code': code,
            'tz_offset_text': ntext(r['tz_offset']),
            'tz': parse_offset(r['tz_offset']),
            'start_local': cell_datetime(r['start_local'], date1904),
            'end_local': cell_datetime(r['end_local'], date1904),
            'primary_metric': ntext(r['primary_metric']).lower(),
            'owner_team': ntext(r['owner_team']).lower(),
        }
    exp_offsets = {c: e['tz'] for c, e in experiments.items()}

    alloc = {}
    for r in sheet_dicts(sheets['Allocation'], 0):
        code = nid(r['experiment'])
        if code not in experiments:
            continue
        arm = ntext(r['arm']).upper()
        alloc.setdefault(code, {})[arm] = {
            'role': ntext(r['role']).lower(),
            'weight_text': ntext(r['weight_pct']),
            'weight': Fraction(ntext(r['weight_pct'])),
        }

    minor_units = {}
    for r in sheet_dicts(sheets['Currencies'], 0):
        minor_units[ntext(r['currency']).upper()] = int(ntext(r['minor_units']))

    fx = {}
    for r in sheet_dicts(sheets[fx_sheet_name], 1):
        cur = ntext(r['currency']).upper()
        if cur in ('', 'CURRENCY'):
            continue
        d = cell_datetime(r['date'], date1904).date()
        fx.setdefault(cur, []).append((d, ntext(r['quote']).upper(), Fraction(ntext(r['rate']))))
    for cur in fx:
        fx[cur].sort(key=lambda t: t[0])

    registry = {}
    for r in sheet_dicts(sheets[registry_version], 2):
        if ntext(r.get('section')).upper() != 'METRIC':
            continue
        code = ntext(r['metric']).lower()

        def opt(key):
            v = ntext(r[key])
            return None if v == '-' else v
        registry[code] = {
            'kind': ntext(r['kind']).lower(),
            'attribution_days': int(ntext(r['attribution_days'])),
            'winsor_pct': opt('winsor_pct'),
            'cuped': ntext(r['cuped']).upper() in ('Y', 'YES', 'TRUE'),
            'covariate': (lambda v: None if v is None else v.lower())(opt('covariate')),
            'role': ntext(r['role']).lower(),
            'higher_is_better': ntext(r['higher_is_better']).upper() in ('Y', 'YES', 'TRUE'),
            'numerator': (lambda v: None if v is None else v.lower())(opt('numerator')),
            'denominator': (lambda v: None if v is None else v.lower())(opt('denominator')),
        }

    # ---- memo
    tables = memo_tables(P('stats_governance_memo_w26.pdf'))
    params = {}
    for r in tables.get('P-1', []):
        params[r['parameter']] = r['value']
    alpha = Fraction(params['alpha_two_sided'])
    bh_q = Fraction(params['bh_q'])
    srm_alpha = Fraction(params['srm_alpha'])
    margins = {k.split('.', 1)[1].lower(): v for k, v in params.items()
               if k.startswith('guardrail_margin_pct.')}
    capacity = {}
    for r in tables.get('C-1', []):
        capacity[ntext(r['owner_team']).lower()] = int(ntext(r['max_ship']))

    amendments = []
    for r in tables.get('A-1', []):
        if r['status'].upper() != 'IN FORCE':
            continue
        scope_tok = ntext(r['experiment'])
        target = 'ALL' if scope_tok.upper() == 'ALL' else canon_exp(scope_tok)
        amendments.append({'id': r['amendment_id'], 'exp': target,
                           'metric': ntext(r['metric']).lower(), 'field': ntext(r['field']),
                           'value': ntext(r['new_value'])})

    rulings_x = {}
    for r in tables.get('X-1', []):
        if r['status'].upper() != 'IN FORCE':
            continue
        code = canon_exp(r['experiment'])
        rulings_x[code] = {'ruling': ntext(r['ruling']).upper(),
                           'revised_end': ntext(r['revised_end_local'])}

    u1_exclude, u1_reinstate = set(), set()
    for r in tables.get('U-1', []):
        if r['status'].upper() != 'IN FORCE':
            continue
        tok = nid(r['unit_token'])
        if ntext(r['ruling']).upper() == 'EXCLUDE':
            u1_exclude.add(tok)
        elif ntext(r['ruling']).upper() == 'REINSTATE':
            u1_reinstate.add(tok)

    # ---- identity links (H1.5)
    links = []  # (from_id, to_id, effective datetime)
    with open(P('identity_links.psv'), 'r', encoding='utf-8-sig') as fh:
        head = fh.readline().rstrip('\n').split('|')
        idx = {h.strip(): i for i, h in enumerate(head)}
        for line in fh:
            if not line.strip():
                continue
            parts = line.rstrip('\n').split('|')
            links.append((nid(parts[idx['from_id']]), nid(parts[idx['linked_to']]),
                          parse_wall(parts[idx['linked_on']])))
    links_by_from = {}
    for f, t, eff in links:
        links_by_from.setdefault(f, []).append((eff, t))

    resolve_cache = {}

    def resolve(token, when):
        key = (token, when)
        hit = resolve_cache.get(key)
        if hit is not None:
            return hit
        cur = token
        seen = [cur]
        seen_set = {cur}
        hops = 0
        while True:
            cands = links_by_from.get(cur)
            if not cands:
                break
            nxt = None
            for eff, t in cands:
                if when >= eff:
                    nxt = t
                    break
            if nxt is None:
                break
            if nxt in seen_set:
                i = seen.index(nxt)
                cycle = seen[i:]
                cur = min(cycle)
                break
            cur = nxt
            seen.append(cur)
            seen_set.add(cur)
            hops += 1
        resolve_cache[key] = (cur, hops)
        return cur, hops

    # ---- registries (H4)
    retired = set()
    for f, cands in links_by_from.items():
        if any(cutoff >= eff for eff, _ in cands):
            retired.add(f)

    account_type = {}
    legacy_rows = read_text(P('unit_registry_legacy.tsv')).split('\n')
    lhead = [h.strip() for h in legacy_rows[0].split('\t')]
    for line in legacy_rows[1:]:
        if not line.strip():
            continue
        d = dict(zip(lhead, line.split('\t')))
        uid = nid(d['UNIT'])
        if uid in retired:
            continue
        account_type[uid] = ntext(d['AccountType']).lower()
    with open(P('unit_registry_main.csv'), 'r', encoding='utf-8-sig') as fh:
        for d in csv.DictReader(fh):
            uid = nid(d['unit_id'])
            if uid in retired:
                continue
            account_type[uid] = ntext(d['account_type']).lower()

    internal_units = set()
    for tok in internal_units_tokens:
        internal_units.add(resolve(tok, cutoff)[0])
    u1_exclude_res = {resolve(t, cutoff)[0] for t in u1_exclude}
    u1_reinstate_res = {resolve(t, cutoff)[0] for t in u1_reinstate}

    def eligibility_reason(unit):
        if unit not in account_type:
            return 'UNREGISTERED'
        if unit in u1_exclude_res:
            return 'RULING_EXCLUDED'
        if unit in internal_units:
            return 'INTERNAL_LIST'
        at = 'human' if unit in u1_reinstate_res else account_type[unit]
        if at == 'human':
            return None
        return {'bot': 'BOT', 'internal': 'INTERNAL', 'test': 'TEST'}.get(at, at.upper())

    # ---- windows (H5)
    for code, e in experiments.items():
        r = rulings_x.get(code)
        ruling = r['ruling'] if r else 'NONE'
        end_local = e['end_local']
        if r and ruling in ('EXTENDED', 'SHORTENED') and r['revised_end'] not in ('', '-'):
            end_local = parse_wall(r['revised_end'])
        e['ruling'] = ruling
        e['aborted'] = (ruling == 'ABORTED')
        e['start_utc'] = e['start_local'] - e['tz']
        e['end_utc'] = end_local - e['tz']
    analysed = [c for c in scope if not experiments[c]['aborted']]

    # ---- shards
    catalog = json.loads(read_text(P('ingest_catalog_w26.json')))
    lineage = {}
    exp_versions = {}
    ord_versions = {}
    exp_rows_read = 0
    ord_rows_read = 0
    for shard in catalog['shards']:
        fname = shard['file']
        stream = shard['stream']
        rows = read_shard_rows(P(fname), shard['layout'])
        codes = shard['status_codes']
        for row in rows:
            rid = nid(row['id'])
            rev = int(Fraction(ntext(row['revision'])))
            status = codes.get(str(row['status']).strip())
            rec = {'shard': fname, 'id': rid, 'revision': rev, 'status': status,
                   'raw': row}
            if stream == 'exposure':
                ecode = canon_exp(row['experiment'])
                rec['experiment'] = ecode
                rec['variant'] = ntext(row['variant'])
                rec['unit_token'] = nid(row['unit'])
                rec['time'] = to_utc(row['time'], shard['ts_convention'], exp_offsets,
                                     ecode, reporting_offset)
                exp_versions.setdefault(rid, []).append(rec)
                exp_rows_read += 1
            else:
                rec['currency'] = ntext(row['currency']).upper()
                amount = Fraction(ntext(row['amount']))
                if shard['amount_unit'] == 'major':
                    amount = amount * (10 ** minor_units[rec['currency']])
                rec['amount_minor'] = amount
                rec['unit_token'] = nid(row['unit'])
                rec['time'] = to_utc(row['time'], shard['ts_convention'], exp_offsets,
                                     None, reporting_offset)
                ord_versions.setdefault(rid, []).append(rec)
                ord_rows_read += 1
        lineage[fname] = {'stream': stream, 'rows': len(rows), 'kept': 0}

    def winner(versions):
        best = versions[0]
        for v in versions[1:]:
            if v['revision'] > best['revision']:
                best = v
        return best

    exposures = {}
    exp_voided = 0
    for rid, versions in exp_versions.items():
        w = winner(versions)
        if w['status'] == 'LIVE':
            exposures[rid] = w
            lineage[w['shard']]['kept'] += 1
        else:
            exp_voided += 1
    orders_all = {}
    ord_cancelled = 0
    for rid, versions in ord_versions.items():
        w = winner(versions)
        orders_all[rid] = w
        if w['status'] == 'PLACED':
            lineage[w['shard']]['kept'] += 1
        else:
            ord_cancelled += 1

    out_of_scope = 0
    unmapped = 0
    live_exposures = []
    scope_set = set(scope)
    for rid, rec in exposures.items():
        if rec['experiment'] not in scope_set:
            out_of_scope += 1
            continue
        arm = variant_map.get((rec['experiment'], nid(rec['variant'])))
        if arm is None:
            unmapped += 1
            continue
        rec['arm'] = arm
        live_exposures.append(rec)

    dedup = {
        'exposure': {'rows_read': exp_rows_read,
                     'duplicate_rows_dropped': exp_rows_read - len(exp_versions),
                     'voided': exp_voided, 'live': len(exposures),
                     'out_of_scope': out_of_scope, 'unmapped_variant': unmapped},
        'order': {'rows_read': ord_rows_read,
                  'duplicate_rows_dropped': ord_rows_read - len(ord_versions),
                  'cancelled': ord_cancelled,
                  'live': len(orders_all) - ord_cancelled},
    }

    # ---- orders: unit attribution and refunds (H8)
    live_orders = {rid: r for rid, r in orders_all.items() if r['status'] == 'PLACED'}
    for rid, o in live_orders.items():
        o['unit'] = resolve(o['unit_token'], o['time'])[0]

    journal = []
    for line in read_text(P('refund_journal.jsonl')).split('\n'):
        if not line.strip():
            continue
        o = json.loads(line)
        journal.append({'journal': 'jsonl', 'seq': int(o['seq']),
                        'status': ntext(o.get('status')).upper(),
                        'kind': ntext(o.get('kind', 'refund')).lower(),
                        'refund_id': nid(o.get('refund_id')),
                        'order_id': nid(o.get('order_id')),
                        'amount': Fraction(ntext(o.get('amount_minor'))),
                        'posted': parse_wall(o.get('posted_utc'))})
    xroot = ET.fromstring(read_text(P('refund_journal_late.xml')))
    for r in xroot.findall('refund'):
        journal.append({'journal': 'xml', 'seq': int(ntext(r.get('seq'))),
                        'status': ntext(r.get('status')).upper(),
                        'kind': ntext(r.get('kind') or 'refund').lower(),
                        'refund_id': nid(r.findtext('id')),
                        'order_id': nid(r.findtext('order')),
                        'amount': Fraction(ntext(r.findtext('minor'))),
                        'posted': parse_wall(r.findtext('posted'))})
    journal.sort(key=lambda e: (e['seq'], 0 if e['journal'] == 'jsonl' else 1))

    held = {}
    refund_outcomes = []
    for e in journal:
        if e['status'] != 'POSTED':
            continue
        if e['posted'] >= cutoff:
            outcome = 'AFTER_CUTOFF'
        elif e['order_id'] not in orders_all:
            outcome = 'NO_ORDER'
        elif orders_all[e['order_id']]['status'] != 'PLACED':
            outcome = 'ORDER_CANCELLED'
        elif e['kind'] == 'reversal':
            if e['refund_id'] in held:
                del held[e['refund_id']]
                outcome = 'REVERSED'
            else:
                outcome = 'NOTHING_TO_REVERSE'
        else:
            outcome = 'REPLACED' if e['refund_id'] in held else 'APPLIED'
            held[e['refund_id']] = (e['order_id'], e['amount'])
        refund_outcomes.append({'journal': e['journal'], 'seq': e['seq'],
                                'kind': e['kind'], 'refund_id': e['refund_id'],
                                'order_id': e['order_id'], 'outcome': outcome})
    refunds_by_order = {}
    for rfid, (oid, amt) in held.items():
        refunds_by_order[oid] = refunds_by_order.get(oid, Fraction(0)) + amt

    # ---- valuation (H8.4)
    def fixing(currency, date):
        best = None
        for d, quote, rate in fx.get(currency, []):
            if d <= date:
                best = (d, quote, rate)
            else:
                break
        if best is None:
            raise ValueError('no fixing for %s on %s' % (currency, date))
        return best

    def to_usd_micro(minor, currency, date):
        """Exact major amount converted to USD, rounded half to even to 1e-6."""
        major = Fraction(minor, 10 ** minor_units[currency])
        if currency == 'USD':
            usd = major
            fx_date = ''
        else:
            d, quote, rate = fixing(currency, date)
            fx_date = d.isoformat()
            if quote == 'USD_PER_UNIT':
                usd = major * rate
            elif quote == 'UNIT_PER_USD':
                usd = major / rate
            elif quote == 'UNIT_PER_EUR':
                _, eq, erate = fixing('EUR', date)
                if eq == 'USD_PER_UNIT':
                    eur_usd = erate
                elif eq == 'UNIT_PER_USD':
                    eur_usd = 1 / erate
                else:
                    raise ValueError('EUR quote %s' % eq)
                usd = major / rate * eur_usd
            else:
                raise ValueError('quote %s' % quote)
        return round6_frac(usd), fx_date

    valuation = []
    orders_by_unit = {}
    for rid in sorted(live_orders):
        o = live_orders[rid]
        if o['time'] >= cutoff:
            continue
        refund_minor = refunds_by_order.get(rid, Fraction(0))
        net_minor = o['amount_minor'] - refund_minor
        if net_minor < 0:
            net_minor = Fraction(0)
        refunded_minor = o['amount_minor'] - net_minor
        date = o['time'].date()
        usd_net, fx_date = to_usd_micro(net_minor, o['currency'], date)
        usd_refunded, _ = to_usd_micro(refunded_minor, o['currency'], date)
        rec = {'order_id': rid, 'unit_id': o['unit'], 'currency': o['currency'],
               'amount_minor': o['amount_minor'], 'refund_minor': refund_minor,
               'net_minor': net_minor, 'fx_date': fx_date, 'usd_net': usd_net,
               'usd_refunded': usd_refunded, 'time': o['time']}
        valuation.append(rec)
        orders_by_unit.setdefault(o['unit'], []).append(rec)
    for lst in orders_by_unit.values():
        lst.sort(key=lambda r: r['time'])

    # ---- participants (H7)
    cand = {}
    for rec in live_exposures:
        code = rec['experiment']
        if code not in analysed:
            continue
        e = experiments[code]
        if rec['time'] >= e['end_utc']:
            continue
        unit = resolve(rec['unit_token'], rec['time'])[0]
        cand.setdefault((code, unit), []).append(rec)

    participants = {}
    excluded = []
    for (code, unit), recs in cand.items():
        reason = eligibility_reason(unit)
        if reason is None:
            arms = {r['arm'] for r in recs}
            if len(arms) > 1:
                reason = 'CROSSOVER'
            elif min(r['time'] for r in recs) < experiments[code]['start_utc']:
                reason = 'PRE_START'
        if reason is not None:
            excluded.append({'experiment': code, 'unit_id': unit, 'reason': reason})
            continue
        participants[(code, unit)] = {
            'experiment': code, 'unit_id': unit, 'arm': recs[0]['arm'],
            'fe': min(r['time'] for r in recs), 'exposures': len(recs)}

    # ---- metric configuration (H9.1, H9.2)
    metric_codes = sorted(registry)
    cfg = {}
    for code in analysed:
        cfg[code] = {}
        for mc in metric_codes:
            c = dict(registry[mc])
            c['amendments'] = []
            cfg[code][mc] = c
        for group in ('ALL', code):
            for am in sorted([a for a in amendments if a['exp'] == group],
                             key=lambda a: natural_key(a['id'])):
                mc = am['metric']
                if mc not in cfg[code]:
                    continue
                c = cfg[code][mc]
                field = am['field']
                if field == 'winsor_pct':
                    c['winsor_pct'] = am['value']
                elif field == 'attribution_days':
                    c['attribution_days'] = int(am['value'])
                elif field == 'cuped':
                    c['cuped'] = am['value'].upper() in ('Y', 'YES', 'TRUE')
                elif field == 'covariate':
                    c['covariate'] = am['value'].lower()
                elif field == 'role':
                    c['role'] = am['value'].lower()
                elif field == 'higher_is_better':
                    c['higher_is_better'] = am['value'].upper() in ('Y', 'YES', 'TRUE')
                elif field == 'kind':
                    c['kind'] = am['value'].lower()
                elif field == 'numerator':
                    c['numerator'] = am['value'].lower()
                elif field == 'denominator':
                    c['denominator'] = am['value'].lower()
                else:
                    raise ValueError('amendment field %s' % field)
                c['amendments'].append(am['id'])

    # ---- per participant metric values (H9.3, H9.4)
    BASE_METRICS = {
        'conv7': 'conv', 'pre_conv': 'conv',
        'rev14': 'rev', 'pre_rev': 'rev',
        'ord14': 'ord', 'pre_ord': 'ord',
        'rfd14': 'rfd',
    }

    def window_value(unit, lo, hi, kind):
        orders = orders_by_unit.get(unit, ())
        if kind == 'conv':
            for o in orders:
                if lo <= o['time'] < hi and o['net_minor'] > 0:
                    return Fraction(1)
            return Fraction(0)
        if kind == 'ord':
            return Fraction(sum(1 for o in orders
                                if lo <= o['time'] < hi and o['net_minor'] > 0))
        if kind == 'rev':
            return sum((o['usd_net'] for o in orders if lo <= o['time'] < hi),
                       Fraction(0))
        if kind == 'rfd':
            return sum((o['usd_refunded'] for o in orders if lo <= o['time'] < hi),
                       Fraction(0))
        raise ValueError(kind)

    for p in participants.values():
        p['values'] = {}
        code = p['experiment']
        fe = p['fe']
        for mc in metric_codes:
            c = cfg[code][mc]
            end = fe + timedelta(days=c['attribution_days'])
            if end > cutoff:
                continue
            entry = {}
            if c['kind'] == 'ratio':
                entry['num'] = window_value(p['unit_id'], fe, end,
                                            BASE_METRICS[c['numerator']])
                entry['den'] = window_value(p['unit_id'], fe, end,
                                            BASE_METRICS[c['denominator']])
            else:
                entry['y'] = window_value(p['unit_id'], fe, end, BASE_METRICS[mc])
                if c['cuped'] and c['covariate']:
                    pre_lo = fe - timedelta(days=pre_period_days)
                    entry['x'] = window_value(p['unit_id'], pre_lo, fe,
                                              BASE_METRICS[c['covariate']])
            p['values'][mc] = entry

    # ---- winsorization / CUPED / arm statistics (H10, H11)
    by_exp_arm = {}
    for p in participants.values():
        by_exp_arm.setdefault(p['experiment'], {}).setdefault(p['arm'], []).append(p)

    winsor_rows = []
    cuped_out = {}
    arm_stats = {}
    for code in analysed:
        arms = alloc[code]
        analysed_arms = sorted([a for a, v in arms.items() if v['role'] in ('control', 'treatment')])
        control = [a for a, v in arms.items() if v['role'] == 'control'][0]
        pool_by_arm = {a: by_exp_arm.get(code, {}).get(a, []) for a in analysed_arms}
        for mc in metric_codes:
            c = cfg[code][mc]
            counted = {a: [p for p in pool_by_arm[a] if mc in p['values']]
                       for a in analysed_arms}
            pooled = [p for a in analysed_arms for p in counted[a]]
            if c['kind'] == 'ratio':
                for a in analysed_arms:
                    ys = [p['values'][mc]['num'] for p in counted[a]]
                    xs = [p['values'][mc]['den'] for p in counted[a]]
                    n = len(ys)
                    if n == 0 or sum(xs) == 0:
                        arm_stats[(code, a, mc)] = None
                        continue
                    R = Fraction(sum(ys), 1) / Fraction(sum(xs), 1)
                    mx, my = mean_f(xs), mean_f(ys)
                    s_xx, s_yy, s_xy = var_f(xs), var_f(ys), cov_f(xs, ys)
                    V = (s_yy / mx ** 2 - 2 * my * s_xy / mx ** 3
                         + my ** 2 * s_xx / mx ** 4) / n
                    arm_stats[(code, a, mc)] = {'n': n, 'raw_mean': R, 'adj_mean': R,
                                                'variance': V}
                continue
            cap = None
            cov_cap = None
            use_winsor = (c['kind'] == 'mean' and c['winsor_pct'] is not None)
            has_cuped = bool(c['cuped'] and c['covariate'])
            if use_winsor and pooled:
                vals = sorted(p['values'][mc]['y'] for p in pooled)
                n = len(vals)
                pos = math.ceil(Fraction(c['winsor_pct']) * n / 100)
                pos = max(1, min(n, pos))
                cap = vals[pos - 1]
                capped = sum(1 for v in vals if v > cap)
                if has_cuped:
                    xvals = sorted(p['values'][mc]['x'] for p in pooled)
                    cov_cap = xvals[pos - 1]
                winsor_rows.append({'experiment': code, 'metric': mc,
                                    'winsor_pct': c['winsor_pct'], 'n_pooled': n,
                                    'cap': cap, 'covariate_cap': cov_cap,
                                    'capped_units': capped})
            ys = {}
            xs = {}
            for a in analysed_arms:
                ys[a] = []
                xs[a] = []
                for p in counted[a]:
                    y = p['values'][mc]['y']
                    if cap is not None and y > cap:
                        y = cap
                    ys[a].append(y)
                    if has_cuped:
                        x = p['values'][mc]['x']
                        if cov_cap is not None and x > cov_cap:
                            x = cov_cap
                        xs[a].append(x)
            pooled_y = [v for a in analysed_arms for v in ys[a]]
            pooled_x = [v for a in analysed_arms for v in xs[a]]
            theta = Fraction(0)
            mean_x = None
            if has_cuped and pooled_y:
                vx = var_f(pooled_x)
                raw_theta = Fraction(0) if vx == 0 else cov_f(pooled_y, pooled_x) / vx
                theta = round6_frac(raw_theta)
                mean_x = mean_f(pooled_x)
                adj_pooled = [y - theta * (x - mean_x)
                              for y, x in zip(pooled_y, pooled_x)]
                var_y = var_f(pooled_y)
                var_adj = var_f(adj_pooled)
                vrp = (Fraction(0) if var_y == 0
                       else 100 * (1 - var_adj / var_y))
                cuped_out.setdefault(code, {})[mc] = {
                    'theta': theta, 'mean_x': mean_x, 'variance_reduction_pct': vrp}
            for a in analysed_arms:
                n = len(ys[a])
                if n == 0:
                    arm_stats[(code, a, mc)] = None
                    continue
                if has_cuped:
                    adj = [y - theta * (x - mean_x) for y, x in zip(ys[a], xs[a])]
                else:
                    adj = ys[a]
                arm_stats[(code, a, mc)] = {'n': n, 'raw_mean': mean_f(ys[a]),
                                            'adj_mean': mean_f(adj),
                                            'variance': var_f(adj)}

    # ---- tests (H11)
    zcrit = NormalDist().inv_cdf(1 - float(alpha) / 2)
    tests = {}
    for code in analysed:
        arms = alloc[code]
        control = [a for a, v in arms.items() if v['role'] == 'control'][0]
        treats = sorted([a for a, v in arms.items() if v['role'] == 'treatment'])
        for a in treats:
            for mc in metric_codes:
                sc = arm_stats.get((code, control, mc))
                st = arm_stats.get((code, a, mc))
                if sc is None or st is None:
                    tests[(code, a, mc)] = None
                    continue
                diff = st['adj_mean'] - sc['adj_mean']
                se = math.sqrt(float(st['variance']) / st['n']
                               + float(sc['variance']) / sc['n'])
                diff_d = float(diff)
                if se == 0:
                    z = 0.0 if diff_d == 0 else math.copysign(float('inf'), diff_d)
                    p = 1.0 if diff_d == 0 else 0.0
                else:
                    z = diff_d / se
                    p = math.erfc(abs(z) / math.sqrt(2))
                ci_low = diff_d - zcrit * se
                ci_high = diff_d + zcrit * se
                base = sc['raw_mean']
                if base != 0:
                    lift = 100 * diff / base
                    lift_lo = 100 * ci_low / float(base)
                    lift_hi = 100 * ci_high / float(base)
                else:
                    lift = None
                    lift_lo = lift_hi = None
                tests[(code, a, mc)] = {
                    'n_c': sc['n'], 'n_t': st['n'], 'mean_c': sc['adj_mean'],
                    'mean_t': st['adj_mean'], 'diff': diff, 'se': se, 'z': z,
                    'p': p, 'ci_low': ci_low, 'ci_high': ci_high, 'lift': lift,
                    'lift_lo': lift_lo, 'lift_hi': lift_hi, 'base': base}

    # ---- SRM (H12)
    srm = {}
    for code in analysed:
        arms = alloc[code]
        names = sorted(arms)
        obs = {a: len([p for p in by_exp_arm.get(code, {}).get(a, [])]) for a in names}
        total = sum(obs.values())
        chi2 = Fraction(0)
        exp_counts = {}
        for a in names:
            e = Fraction(total) * arms[a]['weight'] / 100
            exp_counts[a] = e
            if e != 0:
                chi2 += (Fraction(obs[a]) - e) ** 2 / e
        dof = len(names) - 1
        pval = chi2_sf(chi2, dof)
        srm[code] = {'observed': obs, 'expected': exp_counts, 'chi2': chi2,
                     'dof': dof, 'p': pval,
                     'status': 'FAIL' if Fraction(pval) < srm_alpha else 'PASS'}

    # ---- BH family (H13.1)
    family = []
    for code in analysed:
        if srm[code]['status'] != 'PASS':
            continue
        pm = experiments[code]['primary_metric']
        for a in sorted([x for x, v in alloc[code].items() if v['role'] == 'treatment']):
            t = tests.get((code, a, pm))
            if t is None:
                continue
            family.append({'experiment': code, 'arm': a, 'metric': pm, 'p': t['p']})
    family.sort(key=lambda r: (r['p'], r['experiment'], r['arm']))
    m = len(family)
    qvals = []
    run = None
    for i in range(m, 0, -1):
        val = min(1.0, m * family[i - 1]['p'] / i)
        run = val if run is None else min(run, val)
        qvals.append(run)
    qvals.reverse()
    for i, rec in enumerate(family):
        rec['rank'] = i + 1
        rec['q'] = qvals[i]
        rec['significant'] = 'Y' if Fraction(rec['q']) <= bh_q else 'N'
    family_q = {(r['experiment'], r['arm']): r for r in family}

    # ---- guardrails (H13.2)
    guardrail_rows = []
    breaches = {}
    for code in analysed:
        pm = experiments[code]['primary_metric']
        for a in sorted([x for x, v in alloc[code].items() if v['role'] == 'treatment']):
            for mc in metric_codes:
                c = cfg[code][mc]
                if c['role'] != 'guardrail' or mc == pm:
                    continue
                t = tests.get((code, a, mc))
                margin = margins.get(mc)
                breach = False
                if t is not None and margin is not None and t['lift'] is not None:
                    M = Fraction(margin)
                    worse = (t['diff'] < 0) if c['higher_is_better'] else (t['diff'] > 0)
                    beyond = (t['lift'] < -M) if c['higher_is_better'] else (t['lift'] > M)
                    breach = bool(Fraction(t['p']) < alpha and worse and beyond)
                if breach:
                    breaches.setdefault((code, a), []).append(mc)
                guardrail_rows.append({'experiment': code, 'arm': a, 'metric': mc,
                                       'test': t, 'margin': margin,
                                       'breach': 'Y' if breach else 'N'})

    # ---- decisions (H13.3, H13.5)
    decisions = {}
    for code in scope:
        e = experiments[code]
        pm = e['primary_metric']
        treats = sorted([x for x, v in alloc[code].items() if v['role'] == 'treatment'])
        decisions[code] = {}
        for a in treats:
            qrec = family_q.get((code, a))
            entry = {'primary_metric': pm,
                     'q_value': None if qrec is None else qrec['q'],
                     'guardrail_breaches': sorted(breaches.get((code, a), []))}
            if e['aborted']:
                entry['decision'] = 'ABORTED'
                entry['q_value'] = None
                entry['guardrail_breaches'] = []
            elif srm[code]['status'] == 'FAIL':
                entry['decision'] = 'INVALID_SRM'
            elif entry['guardrail_breaches']:
                entry['decision'] = 'NO_SHIP_GUARDRAIL'
            else:
                t = tests.get((code, a, pm))
                sig = qrec is not None and qrec['significant'] == 'Y'
                if sig and t is not None:
                    c = cfg[code][pm]
                    better = (t['diff'] > 0) if c['higher_is_better'] else (t['diff'] < 0)
                    entry['decision'] = 'SHIP' if better else 'NO_SHIP'
                else:
                    entry['decision'] = 'INCONCLUSIVE'
            decisions[code][a] = entry
    ship_by_team = {}
    for code in scope:
        team = experiments[code]['owner_team']
        for a, entry in decisions[code].items():
            if entry['decision'] == 'SHIP':
                ship_by_team.setdefault(team, []).append((code, a))
    for team, arms in ship_by_team.items():
        if team not in capacity:
            continue
        limit = capacity[team]
        arms.sort(key=lambda ca: (decisions[ca[0]][ca[1]]['q_value'],
                                  '%s/%s' % (ca[0], ca[1])))
        for code, a in arms[limit:]:
            decisions[code][a]['decision'] = 'SHIP_DEFERRED'

    ctx.update(locals())
    write_outputs(ctx, out_dir)


# =============================================================== output

def write_outputs(C, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    files = []

    def write(name, text):
        path = os.path.join(out_dir, name)
        data = text.encode('utf-8')
        with open(path, 'wb') as fh:
            fh.write(data)
        files.append({'name': name, 'bytes': len(data),
                      'sha256': hashlib.sha256(data).hexdigest()})

    analysed = C['analysed']
    scope = C['scope']
    experiments = C['experiments']
    alloc = C['alloc']
    cfg = C['cfg']
    metric_codes = C['metric_codes']
    tests = C['tests']
    arm_stats = C['arm_stats']
    family = C['family']
    family_q = C['family_q']
    srm = C['srm']
    decisions = C['decisions']
    alpha = C['alpha']

    def treats(code):
        return sorted([a for a, v in alloc[code].items() if v['role'] == 'treatment'])

    def analysed_arms(code):
        return sorted([a for a, v in alloc[code].items()
                       if v['role'] in ('control', 'treatment')])

    # ---- readout.csv
    readout = []
    for code in sorted(analysed):
        pm = experiments[code]['primary_metric']
        for a in treats(code):
            for mc in metric_codes:
                t = tests.get((code, a, mc))
                is_primary = (mc == pm)
                qrec = family_q.get((code, a)) if is_primary else None
                if t is None:
                    sig = ''
                elif is_primary:
                    if srm[code]['status'] != 'PASS':
                        sig = ''
                    else:
                        sig = qrec['significant'] if qrec else 'N'
                else:
                    sig = 'Y' if Fraction(t['p']) < alpha else 'N'
                readout.append({
                    'experiment': code, 'arm': a, 'metric': mc,
                    'role': 'primary' if is_primary else cfg[code][mc]['role'],
                    'test': t, 'sig': sig,
                    'q': qrec['q'] if (is_primary and qrec) else None})
    lines = ['experiment,arm,metric,role,n_control,n_treatment,mean_control,'
             'mean_treatment,diff,lift_pct,se,z,p_value,ci_low,ci_high,q_value,significant']
    for r in readout:
        t = r['test']
        if t is None:
            lines.append(','.join([r['experiment'], r['arm'], r['metric'], r['role']]
                                  + [''] * 13))
            continue
        lines.append(','.join([
            r['experiment'], r['arm'], r['metric'], r['role'],
            str(t['n_c']), str(t['n_t']), q6(t['mean_c']), q6(t['mean_t']),
            q6(t['diff']), '' if t['lift'] is None else q6(t['lift']),
            q6(t['se']), q6(t['z']), e6(t['p']), q6(t['ci_low']), q6(t['ci_high']),
            '' if r['q'] is None else e6(r['q']), r['sig']]))
    write('readout.csv', '\n'.join(lines) + '\n')

    # ---- arm_metrics.tsv
    lines = ['experiment\tarm\tmetric\tn\traw_mean\tadj_mean\tvariance']
    for code in sorted(analysed):
        for a in analysed_arms(code):
            for mc in metric_codes:
                s = arm_stats.get((code, a, mc))
                if s is None:
                    lines.append('\t'.join([code, a, mc, '', '', '', '']))
                    continue
                lines.append('\t'.join([code, a, mc, str(s['n']), q6(s['raw_mean']),
                                        q6(s['adj_mean']), q6(s['variance'])]))
    write('arm_metrics.tsv', '\n'.join(lines) + '\n')

    # ---- winsor_caps.psv
    lines = ['experiment|metric|winsor_pct|n_pooled|cap|covariate_cap|capped_units']
    for r in sorted(C['winsor_rows'], key=lambda r: (r['experiment'], r['metric'])):
        lines.append('|'.join([r['experiment'], r['metric'], r['winsor_pct'],
                               str(r['n_pooled']), q6(r['cap']),
                               '' if r['covariate_cap'] is None else q6(r['covariate_cap']),
                               str(r['capped_units'])]))
    write('winsor_caps.psv', '\n'.join(lines) + '\n')

    # ---- cuped.json
    doc = {}
    for code in sorted(C['cuped_out']):
        doc[code] = {}
        for mc in sorted(C['cuped_out'][code]):
            v = C['cuped_out'][code][mc]
            doc[code][mc] = {'theta': q6(v['theta']), 'mean_x': q6(v['mean_x']),
                             'variance_reduction_pct': q6(v['variance_reduction_pct'])}
    write('cuped.json', json.dumps(doc, sort_keys=True, indent=1) + '\n')

    # ---- srm_report.csv
    lines = ['experiment,arm,role,weight_pct,observed,expected,chi2,dof,p_value,status']
    for code in sorted(analysed):
        s = srm[code]
        for a in sorted(alloc[code]):
            lines.append(','.join([code, a, alloc[code][a]['role'],
                                   alloc[code][a]['weight_text'],
                                   str(s['observed'][a]), q6(s['expected'][a]),
                                   q6(s['chi2']), str(s['dof']), e6(s['p']),
                                   s['status']]))
    write('srm_report.csv', '\n'.join(lines) + '\n')

    # ---- bh_family.csv
    lines = ['rank,experiment,arm,metric,p_value,q_value,significant']
    for r in family:
        lines.append(','.join([str(r['rank']), r['experiment'], r['arm'], r['metric'],
                               e6(r['p']), e6(r['q']), r['significant']]))
    write('bh_family.csv', '\n'.join(lines) + '\n')

    # ---- guardrails.csv
    lines = ['experiment,arm,metric,lift_pct,lift_ci_low,lift_ci_high,margin_pct,breach']
    for r in sorted(C['guardrail_rows'], key=lambda r: (r['experiment'], r['arm'], r['metric'])):
        t = r['test']
        if t is None or t['lift'] is None:
            lines.append(','.join([r['experiment'], r['arm'], r['metric'], '', '', '',
                                   r['margin'] or '', r['breach']]))
            continue
        lines.append(','.join([r['experiment'], r['arm'], r['metric'], q6(t['lift']),
                               q6(t['lift_lo']), q6(t['lift_hi']),
                               r['margin'] or '', r['breach']]))
    write('guardrails.csv', '\n'.join(lines) + '\n')

    # ---- decisions.json
    doc = {}
    for code in sorted(scope):
        doc[code] = {}
        for a in sorted(decisions[code]):
            e = decisions[code][a]
            doc[code][a] = {'decision': e['decision'],
                            'primary_metric': e['primary_metric'],
                            'q_value': None if e['q_value'] is None else e6(e['q_value']),
                            'guardrail_breaches': e['guardrail_breaches']}
    write('decisions.json', json.dumps(doc, sort_keys=True, indent=1) + '\n')

    # ---- unit_assignments.csv
    lines = ['experiment,unit_id,arm,first_exposure_utc,exposures']
    for (code, unit) in sorted(C['participants']):
        p = C['participants'][(code, unit)]
        lines.append(','.join([code, unit, p['arm'], fmt_ts(p['fe']), str(p['exposures'])]))
    write('unit_assignments.csv', '\n'.join(lines) + '\n')

    # ---- excluded_units.jsonl
    out = []
    for r in sorted(C['excluded'], key=lambda r: (r['experiment'], r['unit_id'])):
        out.append(json.dumps({'experiment': r['experiment'], 'reason': r['reason'],
                               'unit_id': r['unit_id']}, sort_keys=True))
    write('excluded_units.jsonl', ''.join(s + '\n' for s in out))

    # ---- identity_resolution.csv
    lines = ['from_id,unit_id,hops']
    for f in sorted(C['links_by_from']):
        unit, hops = C['resolve'](f, C['cutoff'])
        lines.append('%s,%s,%d' % (f, unit, hops))
    write('identity_resolution.csv', '\n'.join(lines) + '\n')

    # ---- dedup_report.json
    write('dedup_report.json', json.dumps(C['dedup'], sort_keys=True, indent=1) + '\n')

    # ---- source_lineage.json
    write('source_lineage.json', json.dumps(C['lineage'], sort_keys=True, indent=1) + '\n')

    # ---- refund_outcomes.jsonl
    out = []
    for r in C['refund_outcomes']:
        out.append(json.dumps(r, sort_keys=True))
    write('refund_outcomes.jsonl', ''.join(s + '\n' for s in out))

    # ---- order_valuation.psv
    lines = ['order_id|unit_id|currency|amount_minor|refund_minor|net_minor|fx_date|'
             'usd_net|usd_refunded']
    for r in C['valuation']:
        lines.append('|'.join([r['order_id'], r['unit_id'], r['currency'],
                               str(int(r['amount_minor'])), str(int(r['refund_minor'])),
                               str(int(r['net_minor'])), r['fx_date'],
                               q6(r['usd_net']), q6(r['usd_refunded'])]))
    write('order_valuation.psv', '\n'.join(lines) + '\n')

    # ---- metric_config_used.json
    doc = {'registry_version': C['registry_version'], 'fx_sheet': C['fx_sheet_name']}
    for code in sorted(analysed):
        d = {}
        for mc in metric_codes:
            c = cfg[code][mc]
            has_cuped = bool(c['cuped'] and c['covariate'])
            d[mc] = {'kind': c['kind'], 'attribution_days': c['attribution_days'],
                     'winsor_pct': c['winsor_pct'], 'cuped': has_cuped,
                     'covariate': c['covariate'], 'role': c['role'],
                     'higher_is_better': c['higher_is_better'],
                     'numerator': c['numerator'], 'denominator': c['denominator'],
                     'amendments': c['amendments']}
        doc[code] = d
    write('metric_config_used.json', json.dumps(doc, sort_keys=True, indent=1) + '\n')

    # ---- experiment_windows.xml
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<portfolio id="%s">' % C['portfolio_id']]
    for code in sorted(scope):
        e = experiments[code]
        lines.append('  <experiment code="%s" tz_offset="%s" owner_team="%s" '
                     'start_utc="%s" end_utc="%s" ruling="%s" status="%s"/>'
                     % (code, e['tz_offset_text'], e['owner_team'],
                        fmt_ts(e['start_utc']), fmt_ts(e['end_utc']), e['ruling'],
                        'ABORTED' if e['aborted'] else 'ANALYSED'))
    lines.append('</portfolio>')
    write('experiment_windows.xml', '\n'.join(lines) + '\n')

    # ---- portfolio_summary.json
    dec_counts = {}
    deferred = []
    for code in scope:
        for a, e in decisions[code].items():
            dec_counts[e['decision']] = dec_counts.get(e['decision'], 0) + 1
            if e['decision'] == 'SHIP_DEFERRED':
                deferred.append('%s/%s' % (code, a))
    usd_total = sum((r['usd_net'] for r in C['valuation']), Fraction(0))
    summary = {
        'portfolio_id': C['portfolio_id'],
        'registry_version': C['registry_version'],
        'experiments_analysed': len(analysed),
        'experiments_aborted': len([c for c in scope if experiments[c]['aborted']]),
        'srm_failures': len([c for c in analysed if srm[c]['status'] == 'FAIL']),
        'family_size': len(family),
        'decisions': dec_counts,
        'deferred_arms': sorted(deferred),
        'participants': len(C['participants']),
        'excluded_candidates': len(C['excluded']),
        'live_orders': len(C['valuation']),
        'usd_net_total': q6(usd_total),
    }
    write('portfolio_summary.json', json.dumps(summary, sort_keys=True, indent=1) + '\n')

    # ---- variance_vs_published.csv
    pub = {}
    with open(os.path.join(C['data_dir'], 'readout_published.csv'), 'r',
              encoding='utf-8-sig') as fh:
        for row in csv.DictReader(fh):
            if row['cut'] != 'ALL':
                continue
            pub[(nid(row['experiment']), ntext(row['arm']).upper(),
                 ntext(row['metric']).lower())] = row
    corrected = {}
    for r in readout:
        corrected[(r['experiment'], r['arm'], r['metric'])] = (
            None if r['test'] is None else r['test']['diff'], r['sig'])
    keys = sorted(set(pub) | set(corrected))
    lines = ['experiment,arm,metric,published_diff,corrected_diff,published_significant,'
             'corrected_significant,status']
    for k in keys:
        prow = pub.get(k)
        crow = corrected.get(k)
        pdiff = prow['diff'] if prow else ''
        psig = prow['significant'] if prow else ''
        cdiff = q6(crow[0]) if (crow and crow[0] is not None) else ''
        csig = crow[1] if crow else ''
        if prow and not crow:
            status = 'DROPPED'
        elif crow and not prow:
            status = 'NEW'
        else:
            status = 'FLIPPED' if (psig or 'N') != (csig or 'N') else 'SAME'
        lines.append(','.join([k[0], k[1], k[2], pdiff, cdiff, psig, csig, status]))
    write('variance_vs_published.csv', '\n'.join(lines) + '\n')

    # ---- reconciliation.md
    out = ['# Portfolio %s readout reconciliation' % C['portfolio_id'], '',
           '| experiment | arm | published_decision | corrected_decision |',
           '|---|---|---|---|']
    for code in sorted(scope):
        pm = experiments[code]['primary_metric']
        for a in treats(code):
            prow = pub.get((code, a, pm))
            if prow is None:
                pd = 'MISSING'
            elif prow['significant'] == 'Y':
                pd = 'SHIP' if float(prow['diff']) > 0 else 'NO_SHIP'
            else:
                pd = 'INCONCLUSIVE'
            out.append('| %s | %s | %s | %s |' % (code, a, pd,
                                                  decisions[code][a]['decision']))
    write('reconciliation.md', '\n'.join(out) + '\n')

    # ---- manifest.json
    manifest = {'files': files}
    path = os.path.join(out_dir, 'manifest.json')
    with open(path, 'wb') as fh:
        fh.write((json.dumps(manifest, sort_keys=True, indent=1) + '\n').encode('utf-8'))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
