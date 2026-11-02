#!/usr/bin/env python3
"""Result-cache capacity planning, per cache_planning_rulebook.md rev 5.

Usage: python3 plan_cache.py DATA_DIR OUT_DIR
"""
import csv
import datetime
import hashlib
import json
import os
import re
import sqlite3
import sys
from decimal import Decimal, ROUND_HALF_EVEN, getcontext
from xml.etree import ElementTree as ET

getcontext().prec = 60

UTC = datetime.timezone.utc
HOUR = datetime.timedelta(hours=1)
D0 = Decimal(0)


# ---------------------------------------------------------------- helpers

def norm_id(v):
    """P1.1: strip whitespace and leftover quotes, upper case."""
    if v is None:
        return ''
    s = str(v).strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        s = s[1:-1].strip()
    return s.upper()


def stripq(v):
    if v is None:
        return ''
    s = str(v).strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        s = s[1:-1].strip()
    return s


def jload(s):
    return json.loads(s, parse_float=Decimal)


def dec(v):
    """Exact decimal; a JSON number means the decimal it prints as."""
    if isinstance(v, Decimal):
        return v
    if isinstance(v, bool):
        raise ValueError('bool is not numeric')
    if isinstance(v, int):
        return Decimal(v)
    if isinstance(v, float):
        return Decimal(repr(v))
    s = stripq(v)
    if s == '':
        raise ValueError('empty number')
    return Decimal(s)


def plain(d):
    """Contract decimal string: no exponent, trailing zeros removed."""
    d = Decimal(d)
    if d == 0:
        return '0'
    return format(d.normalize(), 'f')


def qr(value, exp):
    return Decimal(value).quantize(Decimal(exp), rounding=ROUND_HALF_EVEN)


ROUND_MODES = {
    'half_even': ROUND_HALF_EVEN,
    'half-even': ROUND_HALF_EVEN,
    'bankers': ROUND_HALF_EVEN,
    'half_up': 'ROUND_HALF_UP',
    'half-up': 'ROUND_HALF_UP',
    'up': 'ROUND_HALF_UP',
    'half_down': 'ROUND_HALF_DOWN',
    'floor': 'ROUND_FLOOR',
    'down': 'ROUND_DOWN',
    'ceiling': 'ROUND_CEILING',
    'ceil': 'ROUND_CEILING',
}


def round_cents(value, mode):
    from decimal import (ROUND_HALF_UP, ROUND_HALF_DOWN, ROUND_FLOOR, ROUND_DOWN,
                         ROUND_CEILING, ROUND_HALF_EVEN)
    m = ROUND_MODES.get(str(mode).strip().lower())
    if isinstance(m, str):
        m = {'ROUND_HALF_UP': ROUND_HALF_UP, 'ROUND_HALF_DOWN': ROUND_HALF_DOWN,
             'ROUND_FLOOR': ROUND_FLOOR, 'ROUND_DOWN': ROUND_DOWN,
             'ROUND_CEILING': ROUND_CEILING, 'ROUND_HALF_EVEN': ROUND_HALF_EVEN}[m]
    if m is None:
        raise ValueError('unknown saving_rounding %r' % mode)
    return int(Decimal(value).quantize(Decimal(1), rounding=m))


def pct2(value):
    return str(qr(value, '0.01'))


def iso_utc(dt):
    return dt.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_offset(s):
    s = str(s).strip()
    m = re.match(r'^([+-])(\d{1,2}):?(\d{2})$', s)
    if not m:
        raise ValueError('bad offset %r' % s)
    sign = 1 if m.group(1) == '+' else -1
    return datetime.timezone(sign * datetime.timedelta(hours=int(m.group(2)),
                                                       minutes=int(m.group(3))))


# ---------------------------------------------------------------- YAML

def yaml_load(text):
    items = _yl(text.split('\n'))
    if not items:
        return None
    val, _ = _yblock(items, 0)
    return val


def _yl(lines):
    out = []
    for l in lines:
        if l.strip() == '' or re.match(r'^\s*#', l):
            continue
        out.append(l)
    return out


def _yind(l):
    return len(l) - len(l.lstrip(' '))


def _yscalar(s):
    s = s.strip()
    if s == '':
        return None
    if s in ('~', 'null', 'Null', 'NULL'):
        return None
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    if s.startswith('[') and s.endswith(']'):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_yscalar(x.strip()) for x in _ysplit(inner)]
    return s


def _ysplit(s):
    parts, cur, q = [], '', None
    for ch in s:
        if q:
            cur += ch
            if ch == q:
                q = None
            continue
        if ch in ('"', "'"):
            q = ch
            cur += ch
        elif ch == ',':
            parts.append(cur)
            cur = ''
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return parts


def _yblock(items, idx):
    n = len(items)
    if idx >= n:
        return None, idx
    base = _yind(items[idx])
    i = idx
    while i < n and _yind(items[i]) >= base:
        text = items[i].strip()
        if text == '-' or text.startswith('- '):
            return _yseq(items, i, base)
        if re.match(r'^[^:#\[\]{}]+:', text):
            return _ymap(items, i, base)
        return _yscalar(text), i + 1
    return None, idx


def _ystrip_comment(s):
    q = None
    for k, ch in enumerate(s):
        if q:
            if ch == q:
                q = None
            continue
        if ch in ('"', "'"):
            q = ch
        elif ch == '#':
            return s[:k].rstrip()
    return s


def _ymap(items, i, base):
    n = len(items)
    out = {}
    while i < n:
        ind = _yind(items[i])
        if ind < base:
            break
        if ind > base:
            raise ValueError('bad indent %r' % items[i])
        s = items[i].strip()
        m = re.match(r'^("[^"]*"|\'[^\']*\'|[^:#]+?)\s*:\s*(.*)$', s)
        if not m:
            raise ValueError('bad map line %r' % s)
        key = _yscalar(m.group(1))
        rest = m.group(2).strip()
        if rest == '' or rest in ('|', '>'):
            j = i + 1
            if j < n and _yind(items[j]) > base:
                val, j = _yblock(items, j)
                out[key] = val
                i = j
                continue
            if j < n and items[j].strip().startswith('-') and _yind(items[j]) == base:
                val, j = _yseq(items, j, base)
                out[key] = val
                i = j
                continue
            out[key] = None
            i += 1
            continue
        out[key] = _yscalar(_ystrip_comment(rest))
        i += 1
    return out, i


def _yseq(items, i, base):
    n = len(items)
    out = []
    while i < n:
        ind = _yind(items[i])
        if ind < base:
            break
        if ind > base:
            raise ValueError('bad seq indent %r' % items[i])
        s = items[i].strip()
        if not s.startswith('-'):
            break
        rest = s[1:].strip()
        if rest == '':
            j = i + 1
            if j < n and _yind(items[j]) > base:
                val, j = _yblock(items, j)
                out.append(val)
                i = j
                continue
            out.append(None)
            i += 1
            continue
        if ':' in rest and not _yquoted_key(rest):
            sub = [' ' * (base + 2) + rest] + items[i + 1:]
            val, used = _ymap(sub, 0, base + 2)
            out.append(val)
            i = i + used
            continue
        out.append(_yscalar(rest))
        i += 1
    return out, i


def _yquoted_key(s):
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return True
    return bool(re.match(r'^("[^"]*"|\'[^\']*\')\s*:', s))


# ---------------------------------------------------------------- xlsx

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
RID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


def read_workbook(path):
    import zipfile
    z = zipfile.ZipFile(path)
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    date1904 = False
    wbp = wb.find(NS + 'workbookPr')
    if wbp is not None and wbp.get('date1904') in ('1', 'true'):
        date1904 = True
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    relmap = {r.get('Id'): r.get('Target') for r in rels}
    strings = []
    if 'xl/sharedStrings.xml' in z.namelist():
        ss = ET.fromstring(z.read('xl/sharedStrings.xml'))
        for si in ss.iter(NS + 'si'):
            strings.append(''.join(t.text or '' for t in si.iter(NS + 't')))
    sheets = {}
    for sh in wb.iter(NS + 'sheet'):
        target = relmap[sh.get(RID)]
        if not target.startswith('xl/'):
            target = 'xl/' + target
        sheet = ET.fromstring(z.read(target))
        rows = []
        sd = sheet.find(NS + 'sheetData')
        if sd is not None:
            for row in sd.iter(NS + 'row'):
                cells = {}
                for c in row.iter(NS + 'c'):
                    ref = c.get('r') or ''
                    if not ref:
                        continue
                    m = re.match(r'([A-Z]+)', ref)
                    col = 0
                    for ch in m.group(1):
                        col = col * 26 + (ord(ch) - 64)
                    t = c.get('t')
                    v = c.find(NS + 'v')
                    isel = c.find(NS + 'is')
                    if t == 's':
                        val = strings[int(v.text)] if v is not None else None
                    elif t == 'inlineStr' or isel is not None:
                        val = ''.join(tt.text or '' for tt in isel.iter(NS + 't')) if isel is not None else None
                    else:
                        val = v.text if v is not None else None
                    cells[col] = val
                rows.append(cells)
        sheets[sh.get('name')] = rows
    return date1904, sheets


def sheet_table(rows):
    """Rows of cell values as lists indexed from 0."""
    out = []
    for cells in rows:
        if not cells:
            out.append([])
            continue
        width = max(cells)
        out.append([cells.get(i) for i in range(1, width + 1)])
    return out


def cell_num(v):
    if v is None:
        return None
    return int(Decimal(str(v).strip()))


def cell_dec(v):
    if v is None:
        return None
    return Decimal(str(v).strip())


def flag(v):
    return stripq(v).lower() in ('y', 'yes', 'true', '1')


def serial_date(serial, date1904):
    n = int(Decimal(str(serial).strip()))
    base = datetime.date(1904, 1, 1) if date1904 else datetime.date(1899, 12, 30)
    return base + datetime.timedelta(days=n)


# ---------------------------------------------------------------- PDF

def pdf_unescape(s):
    out = bytearray()
    i = 0
    while i < len(s):
        c = s[i]
        if c == 0x5c:
            i += 1
            if i >= len(s):
                break
            c2 = s[i]
            if c2 == 0x6e:
                out.append(10)
            elif c2 == 0x72:
                out.append(13)
            elif c2 == 0x74:
                out.append(9)
            elif c2 == 0x62:
                out.append(8)
            elif c2 == 0x66:
                out.append(12)
            elif c2 == 0x5c:
                out.append(0x5c)
            elif c2 == 0x28:
                out.append(0x28)
            elif c2 == 0x29:
                out.append(0x29)
            elif 0x30 <= c2 <= 0x37:
                oc = ''
                k = i
                while k < len(s) and len(oc) < 3 and 0x30 <= s[k] <= 0x37:
                    oc += chr(s[k])
                    k += 1
                out.append(int(oc, 8) & 0xFF)
                i = k - 1
            else:
                out.append(c2)
        else:
            out.append(c)
        i += 1
    return bytes(out)


def pdf_literal(s, i):
    depth, j = 1, i + 1
    while j < len(s):
        c = s[j]
        if c == 0x5c:
            j += 2
            continue
        if c == 0x28:
            depth += 1
        elif c == 0x29:
            depth -= 1
            if depth == 0:
                return pdf_unescape(s[i + 1:j]), j + 1
        j += 1
    raise ValueError('unterminated string')


def pdf_hex(s, i):
    j = s.index(b'>', i)
    h = re.sub(rb'\s', b'', s[i + 1:j])
    if len(h) % 2:
        h += b'0'
    return bytes.fromhex(h.decode('latin-1')), j + 1


PDFTOK = re.compile(rb'BT|Tm|\(|<|Tj|TJ|ET')


def pdf_cells(stream):
    cells = []
    i, n, cur = 0, len(stream), None
    while i < n:
        m = PDFTOK.search(stream, i)
        if not m:
            break
        t = m.group(0)
        if t == b'BT':
            i = m.end()
            cur = None
        elif t == b'Tm':
            pre = stream[max(0, m.start() - 200):m.start()]
            nums = re.findall(rb'(-?\d+\.?\d*)', pre)
            if len(nums) >= 6:
                cur = (float(nums[-2]), float(nums[-1]))
            i = m.end()
        elif t == b'(':
            s2, i2 = pdf_literal(stream, m.start())
            if stream[i2:i2 + 8].lstrip().startswith(b'Tj'):
                cells.append((cur, s2.decode('latin-1')))
            i = i2
        elif t == b'<':
            close = stream.find(b'>', m.start())
            seg = stream[m.start() + 1:close]
            if b'<' in seg or b'/' in seg or b'[' in seg or b']' in seg:
                i = m.end()
                continue
            h = re.sub(rb'\s', b'', seg)
            if len(h) % 2:
                h += b'0'
            try:
                s2 = bytes.fromhex(h.decode('latin-1'))
            except Exception:
                i = close + 1
                continue
            if stream[close + 1:close + 9].lstrip().startswith(b'Tj'):
                cells.append((cur, s2.decode('latin-1')))
            i = close + 1
        elif t == b'TJ':
            k = stream.rfind(b'[', max(0, m.start() - 4000), m.start())
            if k >= 0:
                arr = stream[k:m.start()]
                text, p = '', 0
                while p < len(arr):
                    c = arr[p]
                    if c == 0x28:
                        s2, p = pdf_literal(arr, p)
                        text += s2.decode('latin-1')
                    elif c == 0x3c:
                        s2, p = pdf_hex(arr, p)
                        text += s2.decode('latin-1')
                    else:
                        p += 1
                cells.append((cur, text))
            i = m.end()
        else:
            i = m.end()
    return cells


def pdf_read(path):
    import zlib
    data = open(path, 'rb').read()
    objs = {}
    for m in re.finditer(rb'(\d+)\s+(\d+)\s+obj\b', data):
        objs[int(m.group(1))] = data[m.end():data.find(b'endobj', m.end())]
    kids = re.search(rb'/Kids\s*\[([^\]]*)\]', objs[2]).group(1)
    kid_nums = [int(x) for x in re.findall(rb'(\d+)\s+\d+\s+R', kids)]
    pages = []
    for kn in kid_nums:
        body = objs[kn]
        sc = re.search(rb'/Contents\s+(\d+)\s+\d+\s+R', body)
        cells = []
        if sc:
            cb = objs[int(sc.group(1))]
            si = cb.find(b'stream')
            j = si + len(b'stream')
            if cb[j:j + 2] == b'\r\n':
                j += 2
            elif cb[j:j + 1] in (b'\n', b'\r'):
                j += 1
            raw = cb[j:cb.rfind(b'endstream')]
            if b'FlateDecode' in cb[:si]:
                raw = zlib.decompress(raw)
            cells = pdf_cells(raw)
        pages.append(cells)
    return pages


def pdf_rows(cells):
    rows = {}
    for (pos, text) in cells:
        if pos is None:
            continue
        rows.setdefault(round(pos[1], 3), []).append((pos[0], text))
    out = []
    for y in sorted(rows, reverse=True):
        out.append([t for _, t in sorted(rows[y])])
    return out


# ---------------------------------------------------------------- feeds

def read_csv_rows(path, delim=','):
    """CSV/TSV/PSV reader keeping raw strings."""
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        rd = csv.reader(f, delimiter=delim)
        return list(rd)


def read_xml(path):
    return ET.parse(path).getroot()


def parse_dt(value, conv, cluster_tz, billing_tz):
    """Return a UTC datetime per the shard's ts_convention."""
    v = stripq(value)
    if conv == 'iso_z':
        return datetime.datetime.strptime(v, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC)
    if conv == 'iso_offset':
        return datetime.datetime.fromisoformat(v).astimezone(UTC)
    if conv == 'epoch_s':
        return datetime.datetime.fromtimestamp(int(Decimal(v)), UTC)
    if conv == 'epoch_ms':
        ms = int(Decimal(v))
        return (datetime.datetime.fromtimestamp(ms // 1000, UTC)
                + datetime.timedelta(milliseconds=ms % 1000))
    if conv == 'compact_utc':
        return datetime.datetime.strptime(v, '%Y%m%d%H%M%S').replace(tzinfo=UTC)
    if conv == 'local_cluster':
        dt = _wall(v)
        return dt.replace(tzinfo=cluster_tz).astimezone(UTC)
    if conv == 'local_billing':
        dt = _wall(v)
        return dt.replace(tzinfo=billing_tz).astimezone(UTC)
    raise ValueError('unknown ts convention %r' % conv)


def _wall(v):
    v = v.replace('T', ' ')
    try:
        return datetime.datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?$',
                     v.strip())
        if m:
            return datetime.datetime(int(m.group(1)), int(m.group(2)),
                                      int(m.group(3)), int(m.group(4)),
                                      int(m.group(5)), int(m.group(6) or 0))
        raise


def shard_records(path, layout, meta):
    """Yield raw field dicts per data row of a shard.

    Fields: qid, start, project, cluster, template, size, volume, option, status, rev.
    `cluster_tz` and `billing_tz` are supplied through meta for time conversion later;
    the start is left raw here and converted by the caller.
    """
    if layout == 'csv_a':
        rows = read_csv_rows(path, ',')
        hdr = [h.strip() for h in rows[0]]
        idx = {h: i for i, h in enumerate(hdr)}
        for r in rows[1:]:
            if not r:
                continue
            yield dict(qid=r[idx['query_id']], start=r[idx['started_utc']],
                       project=r[idx['project_id']], cluster=r[idx['cluster']],
                       template=r[idx['template_id']], size=r[idx['wh_size']],
                       volume=r[idx['scanned_gib']], option=r[idx['cache_option']],
                       status=r[idx['query_status']], rev=r[idx['revision']])
    elif layout == 'tsv_epoch':
        rows = read_csv_rows(path, '\t')
        hdr = [h.strip() for h in rows[0]]
        idx = {h: i for i, h in enumerate(hdr)}
        for r in rows[1:]:
            if not r:
                continue
            yield dict(qid=r[idx['id']], start=r[idx['epoch_s']],
                       project=r[idx['proj']], cluster=r[idx['clu']],
                       template=r[idx['tpl']], size=r[idx['wh']],
                       volume=r[idx['scan_kib']], option=r[idx['opt']],
                       status=r[idx['st']], rev=r[idx['rev']])
    elif layout == 'psv_local':
        rows = read_csv_rows(path, '|')
        hdr = [h.strip() for h in rows[0]]
        idx = {h: i for i, h in enumerate(hdr)}
        for r in rows[1:]:
            if not r:
                continue
            yield dict(qid=r[idx['id']], start=r[idx['local_start']],
                       project=r[idx['proj']], cluster=r[idx['clu']],
                       template=r[idx['tpl']], size=r[idx['wh']],
                       volume=r[idx['gib']], option=r[idx['opt']],
                       status=r[idx['st']], rev=r[idx['rev']])
    elif layout == 'csv_offset':
        rows = read_csv_rows(path, ',')
        hdr = [h.strip() for h in rows[0]]
        idx = {h: i for i, h in enumerate(hdr)}
        for r in rows[1:]:
            if not r:
                continue
            yield dict(qid=r[idx['query']], start=r[idx['ts_offset']],
                       project=r[idx['project']], cluster=r[idx['cluster']],
                       template=r[idx['template']], size=r[idx['size']],
                       volume=r[idx['kib']], option=r[idx['opt']],
                       status=r[idx['code']], rev=r[idx['rev']])
    elif layout == 'jsonl_flat':
        for line in open(path, 'r', encoding='utf-8'):
            if not line.strip():
                continue
            d = jload(line)
            yield dict(qid=d['qid'], start=d['start'], project=d['proj'],
                       cluster=d['clu'], template=d['tpl'], size=d['wh'],
                       volume=d['gib'], option=d['opt'], status=d['st'], rev=d['rev'])
    elif layout == 'ndjson_nested':
        for line in open(path, 'r', encoding='utf-8'):
            if not line.strip():
                continue
            d = jload(line)
            yield dict(qid=d['query']['id'], start=d['scan']['start'],
                       project=d['ctx']['project'], cluster=d['ctx']['cluster'],
                       template=d['ctx']['template'], size=d['ctx']['size'],
                       volume=d['scan']['mib'], option=d['bill']['option'],
                       status=d['bill']['status'], rev=d['query']['rev'])
    elif layout == 'json_array':
        d = jload(open(path, 'r', encoding='utf-8').read())
        rows = d['export']['rows'] if 'export' in d else d['rows']
        for r in rows:
            yield dict(qid=r['queryId'], start=r['epochMillis'],
                      project=r['projectId'], cluster=r['clusterCode'],
                      template=r['templateId'], size=r['whSize'],
                      volume=r['scannedMib'], option=r['option'],
                      status=r['status'], rev=r['revision'])
    elif layout == 'json_keyed':
        d = jload(open(path, 'r', encoding='utf-8').read())
        for k, r in d.items():
            yield dict(qid=k, start=r['ms'], project=r['p'], cluster=r['c'],
                       template=r['t'], size=r['w'], volume=r['mib'],
                       option=r['o'], status=r['s'], rev=r['v'])
    elif layout == 'yaml_list':
        d = yaml_load(open(path, 'r', encoding='utf-8').read())
        recs = d['records'] if isinstance(d, dict) else d
        for r in recs:
            yield dict(qid=r['id'], start=r['start'], project=r['project'],
                       cluster=r['cluster'], template=r['template'], size=r['size'],
                       volume=r['gib'], option=r['option'], status=r['status'],
                       rev=r['rev'])
    elif layout == 'yml_list':
        d = yaml_load(open(path, 'r', encoding='utf-8').read())
        recs = d if isinstance(d, list) else d.get('records')
        for r in recs:
            shape = stripq(r['shape'])
            size, tpl = shape.split('@', 1)
            yield dict(qid=r['qid'], start=r['local'], project=r['prj'],
                       cluster=r['clu'], template=tpl, size=size,
                       volume=r['gib'], option=r['o'], status=r['s'], rev=r['rev'])
    elif layout == 'xml_attr':
        root = read_xml(path)
        for q in root.iter('q'):
            yield dict(qid=q.get('id'), start=q.get('t'), project=q.get('p'),
                       cluster=q.get('c'), template=q.get('tp'), size=q.get('w'),
                       volume=q.get('g'), option=q.get('o'), status=q.get('s'),
                       rev=q.get('v'))
    elif layout == 'xml_elem':
        root = read_xml(path)
        for q in root.iter('query'):
            g = lambda tag: (q.findtext(tag) or '').strip() if q.find(tag) is not None else ''
            yield dict(qid=g('id'), start=g('epoch'), project=g('project'),
                       cluster=g('cluster'), template=g('template'), size=g('size'),
                       volume=g('gib'), option=g('option'), status=g('status'),
                       rev=g('rev'))
    elif layout == 'txt_fixed':
        for line in open(path, 'r', encoding='utf-8'):
            line = line.rstrip('\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            yield dict(qid=line[0:12].strip(), start=line[12:26].strip(),
                       project=line[26:38].strip(), cluster=line[38:63].strip(),
                       template=line[63:73].strip(), size=line[73:77].strip(),
                       volume=line[77:89].strip(), option=line[89:91].strip(),
                       status=line[91:92].strip(), rev=line[92:95].strip())
    elif layout == 'txt_kv':
        for line in open(path, 'r', encoding='utf-8'):
            line = line.rstrip('\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            yield txt_kv_parse(line)
    elif layout == 'sqlite_rows':
        con = sqlite3.connect(path)
        try:
            for r in con.execute('SELECT query_id, started_utc, project_id, cluster, '
                                 'template_id, wh_size, scanned_gib, cache_option, '
                                 'query_status, revision FROM query_log'):
                yield dict(qid=r[0], start=r[1], project=r[2], cluster=r[3],
                           template=r[4], size=r[5], volume=r[6], option=r[7],
                           status=r[8], rev=r[9])
        finally:
            con.close()
    elif layout == 'db_rows':
        con = sqlite3.connect(path)
        try:
            for r in con.execute('SELECT qid, ep, prj, clu, tpl, wh, cg, oc, sc, rv FROM ql'):
                yield dict(qid=r[0], start=r[1], project=r[2], cluster=r[3],
                           template=r[4], size=r[5], volume=r[6], option=r[7],
                           status=r[8], rev=r[9])
        finally:
            con.close()
    else:
        raise ValueError('unknown layout %r' % layout)


def txt_kv_parse(line):
    out = {}
    i = 0
    n = len(line)
    while i < n:
        if line[i] == ' ':
            i += 1
            continue
        j = line.index('=', i)
        key = line[i:j]
        k = j + 1
        if k < n and line[k] == '"':
            e = line.index('"', k + 1)
            val = line[k + 1:e]
            i = e + 1
        else:
            e = line.find(' ', k)
            if e < 0:
                e = n
            val = line[k:e]
            i = e + 1
        out[key] = val
    return dict(qid=out['query'], start=out['at'], project=out['project'],
                cluster=out['cluster'], template=out['template'], size=out['size'],
                volume=out['gib'], option=out['option'], status=out['state'],
                rev=out['rev'])


# ---------------------------------------------------------------- pipeline

class Ctx(object):
    pass


def build(data_dir):
    c = Ctx()
    c.data_dir = data_dir
    c.paths = reference_paths(data_dir)
    profile = yaml_load(open(c.paths['profile'], 'r', encoding='utf-8').read())
    c.profile = profile
    c.plan_id = stripq(profile['plan_id'])
    c.org = norm_id(profile['org_id'])
    c.billing_tz = parse_offset(stripq(profile['billing_offset']))

    def local_to_utc(s):
        v = stripq(s)
        dt = datetime.datetime.strptime(v.replace('T', ' '), '%Y-%m-%d %H:%M:%S')
        return dt.replace(tzinfo=c.billing_tz).astimezone(UTC)

    c.W0 = local_to_utc(profile['lookback_start_local'])
    c.W1 = local_to_utc(profile['lookback_end_local'])
    c.H = int((c.W1 - c.W0) / HOUR)
    c.horizon_end = datetime.datetime.strptime(stripq(profile['horizon_end_utc']),
                                               '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC)

    # cluster aliases
    aliases = yaml_load(open(c.paths['aliases'], 'r', encoding='utf-8').read())
    alias_map = {}
    for item in aliases.get('clusters') or []:
        alias_map[norm_id(item['alias'])] = stripq(item['canonical'])
    c.alias_map = alias_map

    def canon(token):
        return alias_map.get(norm_id(token), norm_id(token))
    c.canon = canon

    c.scope_clusters = set(canon(x['cluster']) for x in profile.get('clusters_in_scope') or [])

    # outages, per canonical cluster
    outages = {}
    for w in profile.get('outage_windows') or []:
        cl = canon(w['cluster'])
        f = local_to_utc(w['from_local'])
        t = local_to_utc(w['to_local'])
        outages.setdefault(cl, []).append((f, t))
    c.outages = outages

    # ruleset in force
    rs = load_ruleset(c, profile)
    c.rs = rs
    c.factors = rs['factors']
    c.cluster_offsets = rs['offsets']
    c.fams = {f['family']: f for f in rs['families']}
    c.node_cap_total = int(Decimal(stripq(rs['plan']['node_cap_total'])))
    c.mem_budget = int(Decimal(stripq(rs['plan']['mem_budget_units'])))
    c.saving_rounding = stripq(rs['plan'].get('saving_rounding', 'half_even'))

    # template families (Appendix T)
    c.tpl_family = load_template_families(c.paths['layouts'])

    # rates in force
    rates, errata, rulings, commitments = load_bulletin(c.paths['bulletin'])
    c.rates = {}
    for (fam, clu), (scan, node) in rates.items():
        c.rates[(fam, canon(clu))] = (scan, node)
    c.errata = errata
    c.rulings = rulings
    c.commitments = {canon(k): v for k, v in commitments.items()}
    for e in c.errata:                      # P11.2: ascending erratum_id, in force wins
        if norm_id(e['status']) != 'IN FORCE':
            continue
        key = (e['family'].lower(), canon(e['cluster']))
        if e['field'] == 'scan_rate_cents':
            c.rates[key] = (e['new_value'], c.rates[key][1])
        elif e['field'] == 'node_rate_cents':
            c.rates[key] = (c.rates[key][0], e['new_value'])
        else:
            raise ValueError('unknown erratum field %r' % e['field'])

    # registry
    c.registry = load_registry(c)[0]

    # merge ledger
    c.ledger = []
    rows = read_csv_rows(c.paths['merges'], '|')
    hdr = [h.strip() for h in rows[0]]
    ix = {h: i for i, h in enumerate(hdr)}
    for r in rows[1:]:
        if not r:
            continue
        eff = datetime.datetime.strptime(stripq(r[ix['merged_on']]), '%Y-%m-%d')
        eff = eff.replace(tzinfo=c.billing_tz).astimezone(UTC)
        c.ledger.append((norm_id(r[ix['from_project']]), norm_id(r[ix['merged_into']]), eff))
    c.ledger_by_from = {}
    for f, t, eff in c.ledger:
        c.ledger_by_from[f] = (t, eff)

    # dev projects resolved as of W1 (P1.5)
    c.dev_resolved = set()
    for item in profile.get('dev_projects') or []:
        pid, _ = resolve_project(c, item['project'], c.W1)
        c.dev_resolved.add(pid)
    return c


def resolve_project(ctx, token, instant):
    """P1.4/P1.5: resolve a project token as of an instant."""
    cur = norm_id(token)
    seen = [cur]
    hops = 0
    while True:
        nxt = ctx.ledger_by_from.get(cur)
        if nxt is None or nxt[1] > instant:
            return cur, hops
        new = nxt[0]
        hops += 1
        if new in seen:
            cycle = seen[seen.index(new):]
            return min(cycle), hops
        seen.append(new)
        cur = new


def project_scope(ctx, pid):
    """P6 checks; returns None when in scope, else the reason."""
    if pid not in ctx.registry:
        return 'UNKNOWN_PROJECT'
    r = ctx.registry[pid]
    if r['org'] != ctx.org:
        return 'OTHER_ORG'
    if r['status'].lower() == 'closed':
        start_date = ctx.profile['lookback_start_local'][:10]
        if r['closed'] and r['closed'] < start_date:
            return 'CLOSED_PROJECT'
    if pid in ctx.dev_resolved:
        return 'DEV_PROJECT'
    return None


# ---------------------------------------------------------------- queries

QTY_DIV = {'gib': Decimal(1), 'mib': Decimal(1024), 'kib': Decimal(1048576),
           'cgib': Decimal(100)}


def load_queries(ctx):
    manifest = jload(open(ctx.paths['manifest'], 'r', encoding='utf-8').read())
    shards = manifest['shards']
    rows_read = 0
    dup_dropped = 0
    voided = 0
    kept_by_shard = {s['file']: 0 for s in shards}
    rows_by_shard = {s['file']: 0 for s in shards}
    best = {}          # qid -> (rev, record, shard)
    for s in shards:
        fname = s['file']
        path = os.path.join(ctx.data_dir, fname)
        optmap = {str(k).strip(): v for k, v in (s['option_codes'] or {}).items()}
        stmap = {str(k).strip(): v for k, v in (s['status_codes'] or {}).items()}
        qty = s['qty_unit']
        conv = s['ts_convention']
        layout = s['layout']
        for raw in shard_records(path, layout, s):
            qid = norm_id(raw['qid'])
            if qid == '':
                continue
            rows_read += 1
            rows_by_shard[fname] += 1
            rev = int(dec(raw['rev']))
            prev = best.get(qid)
            if prev is not None:
                if rev > prev[0]:
                    dup_dropped += 1
                    best[qid] = (rev, raw, fname, optmap, stmap, qty, conv)
                else:
                    dup_dropped += 1
                continue
            best[qid] = (rev, raw, fname, optmap, stmap, qty, conv)
    # live queries
    live = {}
    for qid, (rev, raw, fname, optmap, stmap, qty, conv) in best.items():
        stcode = str(raw['status']).strip()
        if stmap.get(stcode) == 'V':
            voided += 1
            continue
        cluster = ctx.canon(raw['cluster'])
        cluster_tz = parse_offset(ctx.cluster_offsets.get(cluster, '+00:00'))
        try:
            start = parse_dt(raw['start'], conv, cluster_tz, ctx.billing_tz)
        except Exception as e:
            raise ValueError('bad start in %s for %s: %s (%r)' % (fname, qid, e, raw['start']))
        opt = str(raw['option']).strip()
        gib = dec(raw['volume']) / QTY_DIV[qty]
        live[qid] = dict(qid=qid, start=start, project=norm_id(raw['project']),
                         cluster=cluster, template=norm_id(raw['template']),
                         size=canon_lower(raw['size']), gib=gib,
                         option=optmap.get(opt, opt), rev=rev)
        kept_by_shard[fname] += 1
    ctx.dedup = dict(rows_read=rows_read, duplicate_rows_dropped=dup_dropped,
                     voided_rows=voided, live_queries=len(live))
    ctx.lineage = {s['file']: dict(rows=rows_by_shard[s['file']],
                                   kept=kept_by_shard[s['file']]) for s in shards}
    return live


def canon_lower(v):
    if v is None:
        return ''
    s = stripq(v)
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        s = s[1:-1].strip()
    return s.lower()


def apply_adjustments(ctx, live):
    entries = []
    if os.path.exists(ctx.paths['adj_jsonl']):
        for line in open(ctx.paths['adj_jsonl'], 'r', encoding='utf-8'):
            if not line.strip():
                continue
            d = jload(line)
            d['_journal'] = 'jsonl'
            d['_query_id'] = d.get('query_id')
            entries.append(d)
    if os.path.exists(ctx.paths['adj_xml']):
        root = read_xml(ctx.paths['adj_xml'])
    else:
        root = ET.fromstring('<adjustments/>')
    for e in root.iter('entry'):
        d = {'_journal': 'xml', 'seq': e.get('seq'), 'status': e.get('status'),
             '_query_id': e.findtext('query')}
        d['op'] = e.findtext('op')
        for tag in ('quantity_gib', 'project', 'usage_start_utc', 'cluster',
                    'template', 'size', 'option'):
            t = e.find(tag)
            if t is not None and t.text is not None:
                d[tag] = t.text.strip()
        entries.append(d)
    posted = [e for e in entries if stripq(e.get('status')).lower() == 'posted']
    posted.sort(key=lambda e: int(dec(e['seq'])))
    applied = []
    for e in posted:
        op = stripq(e['op']).upper()
        qid = norm_id(e['_query_id'])
        journal = e['_journal']
        out = None
        if op == 'ADD':
            if qid in live:
                out = 'skipped_duplicate'
            else:
                cluster = ctx.canon(e.get('cluster', ''))
                start = datetime.datetime.strptime(stripq(e['usage_start_utc']),
                                                   '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC)
                live[qid] = dict(qid=qid, start=start,
                                 project=norm_id(e.get('project')),
                                 cluster=cluster, template=norm_id(e.get('template')),
                                 size=canon_lower(e.get('size')),
                                 gib=dec(e.get('quantity_gib')),
                                 option=stripq(e.get('option')).upper(), rev=None)
                out = 'applied'
        else:
            q = live.get(qid)
            if q is None:
                out = 'skipped_missing'
            else:
                if op == 'VOID':
                    del live[qid]
                elif op == 'SETQTY':
                    q['gib'] = dec(e.get('quantity_gib'))
                elif op == 'MOVE':
                    q['project'] = norm_id(e.get('project'))
                elif op == 'RETAG':
                    q['template'] = norm_id(e.get('template'))
                else:
                    raise ValueError('unknown op %r' % op)
                out = 'applied'
        applied.append(dict(journal=journal, query_id=qid, op=op, outcome=out,
                            seq=int(dec(e['seq']))))
    ctx.applied = applied
    return live


# ---------------------------------------------------------------- pools

def hour_index(ctx, t):
    return int((t - ctx.W0) / HOUR)


def is_outage(ctx, cluster, h):
    hs = ctx.W0 + h * HOUR
    for (f, t) in ctx.outages.get(cluster, ()):        # half-open [from, to)
        if f <= hs < t:
            return True
    return False


def valid_hours(ctx, cluster):
    out = []
    for h in range(ctx.H):
        if not is_outage(ctx, cluster, h):
            out.append(h)
    return out


def pool_id(family, cluster):
    return family.upper() + '@' + cluster


def compute_pools(ctx, live):
    """P5-P10: window, exclusions, usage, netting, load."""
    out_of_window = 0
    excluded = []
    included = []
    for qid in sorted(live):
        q = live[qid]
        if not (ctx.W0 <= q['start'] < ctx.W1):
            out_of_window += 1
            continue
        fam = ctx.tpl_family.get(q['template'])
        if fam is None:
            raise ValueError('template %s not in Appendix T' % q['template'])
        q['family'] = fam
        pid, _ = resolve_project(ctx, q['project'], q['start'])
        q['proj'] = pid
        q['hour'] = hour_index(ctx, q['start'])
        reason = project_scope(ctx, pid)
        if reason:
            excluded.append((qid, reason))
            continue
        if q['cluster'] not in ctx.scope_clusters:
            excluded.append((qid, 'CLUSTER_OUT_OF_SCOPE'))
            continue
        f = ctx.fams.get(fam)
        if f is None or not f['eligible']:
            excluded.append((qid, 'INELIGIBLE_FAMILY'))
            continue
        if q['option'] == 'B':
            excluded.append((qid, 'BATCH_QUERY'))
            continue
        if is_outage(ctx, q['cluster'], q['hour']):
            excluded.append((qid, 'OUTAGE_HOUR'))
            continue
        engine = fam + '.' + q['size']
        factor = ctx.factors.get(engine)
        if factor is None:
            raise ValueError('no factor for engine %s' % engine)
        q['usage'] = qr(q['gib'] * factor, '0.001')
        included.append(qid)
    ctx.out_of_window = out_of_window
    ctx.excluded = excluded
    ctx.included = included

    # pools
    pools = {}
    for qid in included:
        q = live[qid]
        pid = pool_id(q['family'], q['cluster'])
        p = pools.get(pid)
        if p is None:
            p = pools[pid] = dict(pool_id=pid, family=q['family'],
                                  cluster=q['cluster'], usage={}, proj_usage={})
        p['usage'].setdefault(q['hour'], D0)
        p['usage'][q['hour']] += q['usage']
        p['proj_usage'].setdefault(q['proj'], D0)
        p['proj_usage'][q['proj']] += q['usage']
    ctx.pools = pools

    # reservations
    ctx.reservations = load_reservations(ctx)
    netted = {}
    for r in ctx.reservations:
        if r['status'] == 'NETTED':
            netted.setdefault(r['pool_id'], D0)
            netted[r['pool_id']] += r['units']
    for pid, p in pools.items():
        p['netted'] = netted.get(pid, D0)
        f = ctx.fams[p['family']]
        p['valid_hours'] = valid_hours(ctx, p['cluster'])
        growth = f['growth_pct']
        load = {}
        for h in p['valid_hours']:
            u = p['usage'].get(h, D0)
            grown = qr(u * (Decimal(100) + growth) / Decimal(100), '0.01')
            load[h] = max(D0, grown - p['netted'])
        p['load'] = load
    ctx.netted_total = sum((r['units'] for r in ctx.reservations
                            if r['status'] == 'NETTED'), D0)
    return pools


def load_reservations(ctx):
    if os.path.exists(ctx.paths['reservations']):
        root = read_xml(ctx.paths['reservations'])
    else:
        root = ET.fromstring('<reservations/>')
    out = []
    for e in root.iter('reservation'):
        rid = norm_id(e.get('id'))
        fam = canon_lower(e.get('family'))
        cluster = ctx.canon(e.get('cluster'))
        owner = norm_id(e.get('owner'))
        units = dec(e.get('units'))
        end = datetime.datetime.strptime(stripq(e.get('end_utc')),
                                        '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC)
        state = stripq(e.get('state'))
        ruling = ctx.rulings.get(rid)
        eff_end = end
        if ruling and norm_id(ruling[0]) == 'EXTENDED' and ruling[1]:
            eff_end = datetime.datetime.strptime(ruling[1], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=UTC)
        resolved_owner, _ = resolve_project(ctx, owner, ctx.W1)
        pid = pool_id(fam, cluster)
        if ruling and norm_id(ruling[0]) == 'CANCELLED':
            status = 'CANCELLED'
        elif state.upper() != 'ACTIVE':
            status = 'NOT_ACTIVE'
        elif project_scope(ctx, resolved_owner):
            status = 'OWNER_OUT_OF_SCOPE'
        elif cluster not in ctx.scope_clusters or fam not in ctx.fams \
                or not ctx.fams[fam]['eligible']:
            status = 'NO_POOL'
        elif eff_end < ctx.horizon_end:
            status = 'LAPSES'
        else:
            status = 'NETTED'
        out.append(dict(reservation_id=rid, pool_id=pid, owner=resolved_owner,
                        units=units, effective_end=eff_end, status=status,
                        family=fam, cluster=cluster, state=state))
    return out


# ---------------------------------------------------------------- candidates

def compute_candidates(ctx):
    """P12: kmax, allowed levels, saving at each level."""
    candidates = {}
    excluded_pools = []
    for pid in sorted(ctx.pools):
        p = ctx.pools[pid]
        fam = ctx.fams[p['family']]
        scan_s, node_s = ctx.rates[(p['family'], p['cluster'])]
        scan_rate = dec(scan_s)
        node_rate = dec(node_s)
        node_units = fam['node_units']
        min_nodes = fam['min_nodes']
        tier_units = fam['tier_units']
        disc = fam['tier_discount_pct']
        vh = p['valid_hours']
        loads = [p['load'][h] for h in vh]
        maxload = max(loads) if loads else D0
        p['maxload'] = maxload
        p['load_total'] = sum(loads, D0)
        p['scan_rate'] = scan_rate
        p['node_rate'] = node_rate
        if maxload == 0:
            excluded_pools.append(dict(pool_id=pid, reason='NO_RESIDUAL'))
            continue
        kmax = int((maxload / Decimal(node_units)).to_integral_value(rounding='ROUND_FLOOR'))
        if kmax < min_nodes:
            excluded_pools.append(dict(pool_id=pid, reason='BELOW_MIN_NODES'))
            continue
        levels = [0] + list(range(min_nodes, kmax + 1))
        curves = {}
        for k in levels:
            c = k * node_units
            served = sum((min(l, Decimal(c)) for l in loads), D0)
            if Decimal(c) < Decimal(tier_units):
                eff = node_rate
            else:
                eff = qr(node_rate * (Decimal(100) - disc) / Decimal(100), '0.0001')
            saving = scan_rate * served - eff * Decimal(len(vh)) * Decimal(c)
            curves[k] = dict(cache_units=c, served=served, saving=saving, eff=eff)
        candidates[pid] = dict(pool=pid, family=p['family'], cluster=p['cluster'],
                               kmax=kmax, levels=levels, curves=curves,
                               valid_hours=vh, node_units=node_units,
                               mem_per_node=fam['mem_units_per_node'],
                               family_cap=fam['family_cap'])
    ctx.candidates = candidates
    ctx.excluded_pools = excluded_pools
    return candidates


# ---------------------------------------------------------------- optimiser

def solve_plan(ctx, closed_clusters):
    """P13: maximise the total exact saving subject to all limits.

    Returns (assignment, total saving). Closed clusters are held at 0 nodes.
    """
    cands = ctx.candidates
    fams = {}
    for pid in sorted(cands):
        fams.setdefault(cands[pid]['family'], []).append(pid)
    node_cap = ctx.node_cap_total
    mem_budget = ctx.mem_budget

    # Per family: best assignment using exactly n nodes, n <= family_cap.
    fam_best = {}
    for f in sorted(fams):
        caps = ctx.fams[f]['family_cap']
        pools = fams[f]
        closed_pools = set(p for p in pools if cands[p]['cluster'] in closed_clusters)
        dp = {0: (D0, ())}                   # n -> (saving, per-pool node vector)
        for pid in pools:
            cd = cands[pid]
            nxt = {}
            for used, (sav, vec) in dp.items():
                for k in cd['levels']:
                    if k and pid in closed_pools:
                        continue
                    n = used + k
                    if n > caps:
                        continue
                    s = sav + cd['curves'][k]['saving']
                    v = vec + (k,)
                    cur = nxt.get(n)
                    if cur is None or better(s, v, cur[0], cur[1]):
                        nxt[n] = (s, v)
            dp = nxt
            if not dp:
                raise RuntimeError('no feasible assignment in family %s' % f)
        fam_best[f] = (dp, ctx.fams[f]['mem_units_per_node'])

    # Combine families over (total nodes, total memory).
    comb = {(0, 0): (D0, ())}                # (nodes, mem) -> (saving, per-family counts)
    for f in sorted(fam_best):
        dp, mem_node = fam_best[f]
        nxt = {}
        for (nodes, mem), (sav, vec) in comb.items():
            for n, (s, _) in dp.items():
                nn = nodes + n
                if nn > node_cap:
                    continue
                nm = mem + n * mem_node
                if nm > mem_budget:
                    continue
                ns = sav + s
                nv = vec + (n,)
                cur = nxt.get((nn, nm))
                if cur is None or better(ns, nv, cur[0], cur[1]):
                    nxt[(nn, nm)] = (ns, nv)
        comb = nxt
    best = None
    for key, (sav, vec) in comb.items():
        cand = (sav, -key[0], -key[1], vec)
        if best is None:
            best = cand
        else:
            if cand[:3] > best[:3] or (cand[:3] == best[:3] and cand[3] < best[3]):
                best = cand
    sav, negnodes, negmem, vec = best
    fam_counts = dict(zip(sorted(fam_best), vec))
    result = {}
    for f in sorted(fam_best):
        dp, _ = fam_best[f]
        for pid, k in zip(fams[f], dp[fam_counts[f]][1]):
            result[pid] = k
    return result, sav


def better(s1, v1, s2, v2):
    """P13 tie-breaking: more saving, then fewer nodes, less memory, then
    lexicographic node vector (family order, then pool order)."""
    if s1 != s2:
        return s1 > s2
    n1 = sum(v1)
    n2 = sum(v2)
    if n1 != n2:
        return n1 < n2
    if v1 != v2:
        return v1 < v2
    return False


def run_commitments(ctx):
    """P13A: settle cluster commitments round by round."""
    closed = set()
    rounds = []
    while True:
        plan, total = solve_plan(ctx, closed)
        short = []
        cluster_savings = {}
        cluster_nodes = {}
        for pid, k in plan.items():
            cd = ctx.candidates[pid]
            cl = cd['cluster']
            cluster_nodes[cl] = cluster_nodes.get(cl, 0) + k
            cluster_savings[cl] = cluster_savings.get(cl, D0) + cd['curves'][k]['saving']
        for cl in sorted(cluster_nodes):
            if cl in closed:
                continue
            need = ctx.commitments.get(cl)
            if need is None:
                continue
            if cluster_nodes[cl] >= 1 and cluster_nodes[cl] < need:
                short.append(cl)
        if not short:
            ctx.plan = plan
            ctx.plan_total = total
            break
        victim = sorted(short, key=lambda cl: (cluster_savings[cl], cl))[0]
        rounds.append(dict(round=len(rounds) + 1, cluster=victim,
                           planned_nodes=cluster_nodes[victim],
                           min_nodes=ctx.commitments[victim],
                           saving_exact_cents=cluster_savings[victim],
                           short_clusters=len(short)))
        closed.add(victim)
    ctx.closure_rounds = rounds
    ctx.closed_clusters = closed
    return ctx.plan


# ---------------------------------------------------------------- reports

REPORTS = ['cache_plan.csv', 'pool_curves.psv', 'pool_hourly.tsv', 'hourly_rollup.tsv',
           'rates_used.csv', 'ruleset_used.json', 'dedup_report.json',
           'source_lineage.json', 'applied_adjustments.jsonl', 'project_resolution.csv',
           'scope_projects.csv', 'excluded_queries.jsonl', 'reservation_dispositions.csv',
           'excluded_pools.jsonl', 'cluster_commitments.jsonl', 'family_rollup.json',
           'cluster_rollup.xml', 'chargeback.csv', 'team_rollup.json',
           'plan_summary.json', 'variance_vs_published.csv', 'reconciliation.md',
           'manifest.json']


class Out(object):
    def __init__(self, out_dir):
        self.dir = out_dir

    def text(self, name, s):
        with open(os.path.join(self.dir, name), 'w', encoding='utf-8', newline='') as f:
            f.write(s)

    def table(self, name, header, rows, delim=','):
        buf = []
        if delim == ',':
            buf.append(','.join(header))
            for r in rows:
                buf.append(','.join(csv_escape(x, delim) for x in r))
        elif delim == '|':
            buf.append('|'.join(header))
            for r in rows:
                buf.append('|'.join(csv_escape(x, delim) for x in r))
        else:
            buf.append('\t'.join(header))
            for r in rows:
                buf.append('\t'.join(csv_escape(x, delim) for x in r))
        self.text(name, '\n'.join(buf) + '\n')

    def json(self, name, obj):
        self.text(name, json.dumps(obj, sort_keys=True, indent=2) + '\n')

    def jsonl(self, name, objs):
        s = ''.join(json.dumps(o, sort_keys=True) + '\n' for o in objs)
        self.text(name, s)


def csv_escape(v, delim):
    if v is None:
        return ''
    s = str(v)
    if delim == ',' and (',' in s or '"' in s or '\n' in s):
        return '"' + s.replace('"', '""') + '"'
    return s


def write_cache_plan(ctx, out):
    rows = []
    for pid in sorted(ctx.candidates):
        cd = ctx.candidates[pid]
        k = ctx.plan[pid]
        cur = cd['curves'][k]
        fam = ctx.fams[cd['family']]
        mem = k * fam['mem_units_per_node']
        hourly = cur['eff'] * Decimal(cur['cache_units'])
        served = cur['served']
        p = ctx.pools[pid]
        if p['load_total'] == 0:
            spct = '0.00'
        else:
            spct = pct2(served / p['load_total'] * 100)
        if k == 0:
            upct = ''
        else:
            upct = pct2(served / (Decimal(cur['cache_units']) * Decimal(len(cd['valid_hours']))) * 100)
        rows.append([pid, cd['family'], cd['cluster'], k, cur['cache_units'], mem,
                     plain(hourly), round_cents(cur['saving'], ctx.saving_rounding), spct, upct])
    out.table('cache_plan.csv',
              ['pool_id', 'family', 'cluster', 'nodes', 'cache_units', 'mem_units',
               'hourly_node_cents', 'saving_cents', 'served_pct', 'utilization_pct'], rows)


def write_pool_curves(ctx, out):
    rows = []
    for pid in sorted(ctx.candidates):
        cd = ctx.candidates[pid]
        for k in cd['levels']:
            cur = cd['curves'][k]
            rows.append([pid, k, cur['cache_units'], plain(cur['served']),
                         plain(cur['saving'])])
    out.table('pool_curves.psv',
              ['pool_id', 'nodes', 'cache_units', 'served_unit_hours',
               'saving_exact_cents'], rows, '|')


def write_pool_hourly(ctx, out):
    rows = []
    for pid in sorted(ctx.pools):
        p = ctx.pools[pid]
        for h in p['valid_hours']:
            rows.append([pid, h, iso_utc(ctx.W0 + h * HOUR),
                         plain(p['usage'].get(h, D0)), plain(p['load'][h])])
    out.table('pool_hourly.tsv',
              ['pool_id', 'hour_index', 'hour_start_utc', 'usage_units', 'load_units'],
              rows, '\t')


def write_hourly_rollup(ctx, out):
    rows = []
    for h in range(ctx.H):
        pools_valid = 0
        load = D0
        units = 0
        served = D0
        overflow = D0
        for pid in sorted(ctx.candidates):
            cd = ctx.candidates[pid]
            if h not in cd['valid_hours_set']:
                continue
            pools_valid += 1
            p = ctx.pools[pid]
            l = p['load'][h]
            c = ctx.plan[pid] * cd['node_units']
            load += l
            units += c
            served += min(l, Decimal(c))
            overflow += max(D0, l - Decimal(c))
        rows.append([h, iso_utc(ctx.W0 + h * HOUR), pools_valid, plain(load), units,
                     plain(served), plain(overflow)])
    out.table('hourly_rollup.tsv',
              ['hour_index', 'hour_start_utc', 'pools_valid', 'load_units',
               'cache_units', 'served_units', 'overflow_units'], rows, '\t')


def find_file(data_dir, name, pattern):
    """Exact file name when present, else a unique glob match."""
    p = os.path.join(data_dir, name)
    if os.path.exists(p):
        return p
    import glob
    matches = sorted(glob.glob(os.path.join(data_dir, pattern)))
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise FileNotFoundError(name)
    raise RuntimeError('ambiguous match for %s: %s' % (name, matches))


PROFILE_FILE = 'plan_profile_qa4.yml'
ALIASES_FILE = 'cluster_aliases.yaml'
WORKBOOK_FILE = 'capacity_workbook_fy26.xlsx'
BULLETIN_FILE = 'pricing_bulletin_q4.pdf'
MANIFEST_FILE = 'ingest_manifest_r7.json'
LAYOUTS_FILE = 'feed_layouts.md'
ADJ_JSONL = 'scan_adjustments.jsonl'
ADJ_XML = 'scan_adjustments_late.xml'
MERGES_FILE = 'project_merges.psv'
RESERVATIONS_FILE = 'cache_reservations.xml'
REGISTRY_MAIN = 'proj_registry_main.csv'
REGISTRY_ARCHIVE = 'proj_registry_archive.tsv'


def reference_paths(data_dir):
    return {
        'profile': find_file(data_dir, PROFILE_FILE, 'plan_profile*.y*ml'),
        'aliases': find_file(data_dir, ALIASES_FILE, 'cluster_aliases*.ya?ml'),
        'workbook': find_file(data_dir, WORKBOOK_FILE, 'capacity_workbook*.xlsx'),
        'bulletin': find_file(data_dir, BULLETIN_FILE, 'pricing_bulletin*.pdf'),
        'manifest': find_file(data_dir, MANIFEST_FILE, 'ingest_manifest*.json'),
        'layouts': find_file(data_dir, LAYOUTS_FILE, 'feed_layouts.md'),
        'adj_jsonl': find_file(data_dir, ADJ_JSONL, 'scan_adjustments*.jsonl'),
        'adj_xml': find_file(data_dir, ADJ_XML, 'scan_adjustments*late*.xml'),
        'merges': find_file(data_dir, MERGES_FILE, 'project_merges*.psv'),
        'reservations': find_file(data_dir, RESERVATIONS_FILE, 'cache_reservations*.xml'),
        'registry_main': find_file(data_dir, REGISTRY_MAIN, 'proj_registry_main*.csv'),
        'registry_archive': find_file(data_dir, REGISTRY_ARCHIVE, 'proj_registry_archive*.tsv'),
    }


def write_rates_used(ctx, out):
    rows = []
    for pid in sorted(ctx.pools):
        p = ctx.pools[pid]
        fam = ctx.fams[p['family']]
        scan_s, node_s = ctx.rates[(p['family'], p['cluster'])]
        rows.append([pid, p['family'], p['cluster'], scan_s, node_s,
                     fam['node_units'], fam['min_nodes'], pct2(fam['growth_pct']),
                     fam['tier_units'], pct2(fam['tier_discount_pct']),
                     fam['mem_units_per_node'], plain(p['netted']),
                     len(p['valid_hours'])])
    out.table('rates_used.csv',
              ['pool_id', 'family', 'cluster', 'scan_rate_cents', 'node_rate_cents',
               'node_units', 'min_nodes', 'growth_pct', 'tier_units',
               'tier_discount_pct', 'mem_units_per_node', 'netted_units',
               'valid_hours'], rows)


def write_ruleset_used(ctx, out):
    fams = []
    for f in sorted(ctx.rs['families'], key=lambda x: x['family'].upper()):
        fams.append(dict(family=f['family'], eligible=f['eligible'],
                         node_units=f['node_units'], min_nodes=f['min_nodes'],
                         family_cap=f['family_cap'],
                         growth_pct=pct2(f['growth_pct']),
                         tier_units=f['tier_units'],
                         tier_discount_pct=pct2(f['tier_discount_pct']),
                         mem_units_per_node=f['mem_units_per_node']))
    out.json('ruleset_used.json', dict(
        sheet=ctx.rs['sheet'], adoption_id=ctx.rs['adoption_id'],
        effective_date=ctx.rs['effective_date'],
        node_cap_total=ctx.node_cap_total, mem_budget_units=ctx.mem_budget,
        saving_rounding=ctx.saving_rounding, families=fams))


def write_project_resolution(ctx, out):
    rows = []
    for f, t, eff in sorted(ctx.ledger):
        can, hops = resolve_project(ctx, f, ctx.W1)
        rows.append([f, can, hops])
    out.table('project_resolution.csv', ['alias', 'canonical', 'hops'], rows)


def write_scope_projects(ctx, out):
    rows = []
    for pid in sorted(ctx.registry):
        r = ctx.registry[pid]
        if r['org'] != ctx.org:
            continue
        if r['status'].lower() == 'closed' and r['closed'] \
                and r['closed'] < ctx.profile['lookback_start_local'][:10]:
            scope = 'CLOSED'
        elif pid in ctx.dev_resolved:
            scope = 'DEV'
        else:
            scope = 'IN_SCOPE'
        rows.append([pid, r['team'], r['status'], scope])
    out.table('scope_projects.csv', ['project_id', 'team', 'project_status', 'scope'], rows)


def write_reservation_dispositions(ctx, out):
    rows = []
    for r in sorted(ctx.reservations, key=lambda r: r['reservation_id']):
        rows.append([r['reservation_id'], r['pool_id'], r['owner'], plain(r['units']),
                     iso_utc(r['effective_end']), r['status']])
    out.table('reservation_dispositions.csv',
              ['reservation_id', 'pool_id', 'owner_project', 'units',
               'effective_end_utc', 'status'], rows)


def write_family_rollup(ctx, out):
    res = {}
    for fam in sorted(set(c['family'] for c in ctx.candidates.values()),
                      key=lambda f: f.upper()):
        pools = sorted(pid for pid, c in ctx.candidates.items() if c['family'] == fam)
        nodes = sum(ctx.plan[pid] for pid in pools)
        mem = sum(ctx.plan[pid] * ctx.fams[fam]['mem_units_per_node'] for pid in pools)
        sav = sum(round_cents(ctx.candidates[pid]['curves'][ctx.plan[pid]]['saving'], ctx.saving_rounding)
                  for pid in pools)
        res[fam.upper()] = dict(pools=len(pools), nodes=nodes,
                                family_cap=ctx.fams[fam]['family_cap'],
                                mem_units=mem, saving_cents=sav)
    out.json('family_rollup.json', res)


def write_cluster_rollup(ctx, out):
    lines = ['<clusters plan="%s">' % ctx.plan_id]
    clusters = {}
    for pid, cd in ctx.candidates.items():
        clusters.setdefault(cd['cluster'], []).append(pid)
    for cl in sorted(clusters):
        pools = sorted(clusters[cl])
        nodes = sum(ctx.plan[pid] for pid in pools)
        cu = sum(ctx.plan[pid] * ctx.candidates[pid]['node_units'] for pid in pools)
        mem = sum(ctx.plan[pid] * ctx.fams[ctx.candidates[pid]['family']]['mem_units_per_node']
                  for pid in pools)
        sav = sum(round_cents(ctx.candidates[pid]['curves'][ctx.plan[pid]]['saving'], ctx.saving_rounding)
                  for pid in pools)
        lines.append('<cluster code="%s" pools="%d" nodes="%d" cache_units="%d" '
                     'mem_units="%d" saving_cents="%d"/>'
                     % (cl, len(pools), nodes, cu, mem, sav))
    lines.append('</clusters>')
    out.text('cluster_rollup.xml', '\n'.join(lines) + '\n')


def compute_chargeback(ctx):
    rows = []
    for pid in sorted(ctx.candidates):
        k = ctx.plan[pid]
        if k < 1:
            continue
        saving = round_cents(ctx.candidates[pid]['curves'][k]['saving'], ctx.saving_rounding)
        p = ctx.pools[pid]
        projs = sorted(p['proj_usage'])
        total = sum(p['proj_usage'][x] for x in projs)
        if total == 0 or saving == 0:
            for pr in projs:
                rows.append([pid, pr, ctx.registry[pr]['team'], plain(p['proj_usage'][pr]), 0])
            continue
        shares = []
        left = saving
        for pr in projs:
            exact = Decimal(saving) * p['proj_usage'][pr] / total
            base = int(exact.to_integral_value(rounding='ROUND_FLOOR'))
            left -= base
            shares.append((pr, base, exact - base))
        order = sorted(range(len(shares)), key=lambda i: (-shares[i][2], shares[i][0]))
        extra = [0] * len(shares)
        for i in order[:max(left, 0)]:
            extra[i] = 1
        for i, pr in enumerate(projs):
            rows.append([pid, pr, ctx.registry[pr]['team'], plain(p['proj_usage'][pr]),
                         shares[i][1] + extra[i]])
    return rows


def write_chargeback(ctx, out):
    rows = compute_chargeback(ctx)
    out.table('chargeback.csv',
              ['pool_id', 'project_id', 'team', 'usage_units', 'allocated_cents'], rows)
    teams = {}
    for pid, pr, team, usage, cents in rows:
        t = teams.setdefault(team, dict(projects=set(), allocated_cents=0))
        t['projects'].add(pr)
        t['allocated_cents'] += cents
    out.json('team_rollup.json',
             {t: dict(projects=len(v['projects']), allocated_cents=v['allocated_cents'])
              for t, v in teams.items()})


def load_published(ctx):
    name = ctx.profile.get('published_plan')
    if not name:
        return {}, {}
    path = os.path.join(ctx.data_dir, stripq(name))
    if not os.path.exists(path):
        return {}, {}
    rows = read_csv_rows(path, ',')
    hdr = [h.strip() for h in rows[0]]
    ix = {h: i for i, h in enumerate(hdr)}
    nodes = {}
    saving = {}
    for r in rows[1:]:
        if not r:
            continue
        pid = norm_id(r[ix['pool_id']])
        n = int(dec(r[ix['nodes']]))
        if pid in nodes:
            if nodes[pid] != n:
                raise ValueError('inconsistent published nodes for %s' % pid)
        else:
            nodes[pid] = n
        saving[pid] = saving.get(pid, 0) + int(dec(r[ix['saving_cents']]))
    return nodes, saving


def write_variance(ctx, out):
    pub_nodes, pub_saving = load_published(ctx)
    rows = []
    for pid in sorted(set(list(pub_nodes) + list(ctx.candidates))):
        pn = pub_nodes.get(pid, 0)
        cn = ctx.plan.get(pid, 0)
        ps = pub_saving.get(pid, '')
        cs = round_cents(ctx.candidates[pid]['curves'][cn]['saving'], ctx.saving_rounding) if pid in ctx.candidates else ''
        if pid not in pub_nodes:
            status = 'NEW'
        elif pid not in ctx.candidates:
            status = 'DROPPED'
        elif pn == cn:
            status = 'MATCH'
        else:
            status = 'CHANGED'
        rows.append([pid, pn if pid in pub_nodes else '', cn, cn - pn, ps, cs, status])
    out.table('variance_vs_published.csv',
              ['pool_id', 'published_nodes', 'corrected_nodes', 'node_delta',
               'published_saving_cents', 'corrected_saving_cents', 'status'], rows)


def write_reconciliation(ctx, out):
    pub_nodes, _ = load_published(ctx)
    fams_pub = {}
    for pid, n in pub_nodes.items():
        f = pid.split('@', 1)[0]
        fams_pub[f] = fams_pub.get(f, 0) + n
    fams_new = {}
    for pid, cd in ctx.candidates.items():
        fams_new[cd['family'].upper()] = fams_new.get(cd['family'].upper(), 0) + ctx.plan[pid]
    lines = ['# Plan %s cache reconciliation' % ctx.plan_id, '', '| family | published_nodes | corrected_nodes | delta_nodes |',
             '|---|---|---|---|']
    for f in sorted(set(list(fams_pub) + list(fams_new))):
        lines.append('| %s | %d | %d | %d |'
                     % (f, fams_pub.get(f, 0), fams_new.get(f, 0),
                        fams_new.get(f, 0) - fams_pub.get(f, 0)))
    lines.append('| ALL | %d | %d | %d |'
                 % (sum(fams_pub.values()), sum(fams_new.values()),
                    sum(fams_new.values()) - sum(fams_pub.values())))
    out.text('reconciliation.md', '\n'.join(lines) + '\n')


def write_plan_summary(ctx, out):
    total = sum(ctx.candidates[pid]['curves'][k]['saving'] for pid, k in ctx.plan.items())
    chargeback = compute_chargeback(ctx)
    out.json('plan_summary.json', dict(
        plan_id=ctx.plan_id, ruleset_version=ctx.rs['sheet'],
        lookback_hours=ctx.H, out_of_window_queries=ctx.out_of_window,
        excluded_queries=len(ctx.excluded), candidate_pools=len(ctx.candidates),
        selected_pools=sum(1 for k in ctx.plan.values() if k >= 1),
        nodes_total=sum(ctx.plan.values()), node_cap_total=ctx.node_cap_total,
        mem_units_total=sum(ctx.plan[pid] * ctx.fams[ctx.candidates[pid]['family']]['mem_units_per_node']
                            for pid in ctx.plan),
        mem_budget_units=ctx.mem_budget,
        total_saving_cents=round_cents(total, ctx.saving_rounding),
        chargeback_total_cents=sum(r[4] for r in chargeback),
        netted_units_total=plain(ctx.netted_total),
        closure_rounds=len(ctx.closure_rounds)))


def write_manifest(ctx, out):
    files = []
    for name in REPORTS:
        if name == 'manifest.json':
            continue
        path = os.path.join(out.dir, name)
        data = open(path, 'rb').read()
        files.append(dict(name=name, bytes=len(data),
                          sha256=hashlib.sha256(data).hexdigest()))
    out.json('manifest.json', dict(files=files))


# ---------------------------------------------------------------- reference data

def load_template_families(path):
    """Appendix T of feed_layouts.md: template_id -> family (lower case)."""
    fam = {}
    txt = open(path, 'r', encoding='utf-8').read()
    start = txt.index('## Appendix T')
    for line in txt[start:].split('\n'):
        line = line.strip()
        if not line.startswith('|'):
            continue
        parts = [p.strip() for p in line.strip('|').split('|')]
        if len(parts) < 2 or parts[0] == 'template_id':
            continue
        if not re.match(r'^[A-Za-z]+-\d+$', parts[0]):
            continue
        fam[norm_id(parts[0])] = parts[1].lower()
    return fam


def load_bulletin(path):
    """Rates, errata, rulings and commitments from the pricing bulletin PDF."""
    pages = pdf_read(path)
    rates = {}
    errata = []
    rulings = {}
    commitments = {}
    mode = None
    header = None
    for page in pages:
        for row in pdf_rows(page):
            cells = [c.strip() for c in row if c.strip() != '']
            if not cells:
                continue
            first = cells[0]
            if first.startswith('Table R-2'):
                mode, header = 'R2', None
                continue
            if first.startswith('Table R-1'):
                mode, header = 'R1', None
                continue
            if first.startswith('Table E-1'):
                mode, header = 'E1', None
                continue
            if first.startswith('Table C-1'):
                mode, header = 'C1', None
                continue
            if first.startswith('Table M-0'):
                mode, header = 'M0', None
                continue
            if first.startswith('Table M-1'):
                mode, header = 'M1', None
                continue
            if first.startswith('Table '):
                mode, header = None, None
                continue
            if mode is None or re.match(r'^Bulletin .* page \d+ of \d+$', first):
                continue
            low = [c.lower() for c in cells]
            if len(cells) >= 2 and low[0] == 'family' and low[1] == 'cluster':
                header = cells
                continue
            if len(cells) >= 2 and (low[0] == 'erratum_id' or low[0] == 'reservation_id'
                                   or (low[0] == 'cluster' and low[1] == 'min_nodes')):
                header = cells
                continue
            if header is None:
                continue
            if mode == 'R2' and len(cells) >= 4:
                rates[(cells[0].lower(), cells[1])] = (cells[2], cells[3])
            elif mode == 'E1' and len(cells) >= 6:
                errata.append(dict(erratum_id=cells[0], family=cells[1].lower(),
                                   cluster=cells[2], field=cells[3],
                                   new_value=cells[4], status=cells[5]))
            elif mode == 'C1' and len(cells) >= 3:
                rulings[cells[0]] = (cells[1], None if cells[2] == '-' else cells[2])
            elif mode == 'M1' and len(cells) >= 2:
                commitments[cells[0]] = int(cells[1])
    errata.sort(key=lambda e: e['erratum_id'])
    return rates, errata, rulings, commitments


def load_ruleset(ctx, profile):
    """The ruleset sheet in force and the workbook's reference sheets."""
    date1904, sheets = read_workbook(ctx.paths['workbook'])
    lookback_date = datetime.datetime.strptime(
        stripq(profile['lookback_start_local'])[:10], '%Y-%m-%d').date()
    track = norm_id(profile['ruleset_track'])
    best = None
    for row in sheet_table(sheets.get('Adoptions', []))[1:]:
        if not row or len(row) < 5 or row[0] is None:
            continue
        if norm_id(row[1]) != track or norm_id(row[4]) != 'ADOPTED':
            continue
        eff = serial_date(row[3], date1904)
        if eff <= lookback_date and (best is None or eff > best[0]):
            best = (eff, row)
    if best is None:
        raise RuntimeError('no adopted ruleset for track %s' % track)
    sheet_name = stripq(best[1][2])
    plan = {}
    fams = []
    for row in sheet_table(sheets[sheet_name]):
        if not row or row[0] is None:
            continue
        section = stripq(row[0])
        if section == 'PLAN':
            plan[stripq(row[1])] = stripq(row[2])
        elif section == 'FAM':
            fams.append(dict(family=stripq(row[1]).lower(), eligible=flag(row[2]),
                             node_units=cell_num(row[3]), min_nodes=cell_num(row[4]),
                             family_cap=cell_num(row[5]), growth_pct=cell_dec(row[6]),
                             tier_units=cell_num(row[7]),
                             tier_discount_pct=cell_dec(row[8]),
                             mem_units_per_node=cell_num(row[9])))
    factors = {}
    for row in sheet_table(sheets.get('ScanFactors', []))[1:]:
        if row and row[0] is not None:
            factors[stripq(row[0]).lower()] = cell_dec(row[1])
    offsets = {}
    for row in sheet_table(sheets.get('Clusters', []))[1:]:
        if row and row[0] is not None:
            offsets[stripq(row[0])] = stripq(row[1])
    return dict(sheet=sheet_name, adoption_id=norm_id(best[1][0]),
                effective_date=best[0].isoformat(), plan=plan, families=fams,
                factors=factors, offsets=offsets)


def load_registry(ctx):
    """Project registry rows, main export taking precedence."""
    main = {}
    rows = read_csv_rows(ctx.paths['registry_main'], ',')
    hdr = [h.strip() for h in rows[0]]
    ix = {h: i for i, h in enumerate(hdr)}
    for r in rows[1:]:
        if not r or not r[ix['project_id']].strip():
            continue
        main[norm_id(r[ix['project_id']])] = dict(
            org=norm_id(r[ix['org_id']]), team=stripq(r[ix['team']]),
            status=stripq(r[ix['project_status']]), closed=stripq(r[ix['closed_on']]))
    arch = {}
    rows = read_csv_rows(ctx.paths['registry_archive'], '\t')
    hdr = [h.strip() for h in rows[0]]
    ix = {h: i for i, h in enumerate(hdr)}
    for r in rows[1:]:
        if not r or not r[ix['PROJ']].strip():
            continue
        closed = stripq(r[ix['Closed']])
        if closed:
            d, m, y = closed.split('/')
            closed = '%s-%s-%s' % (y, m, d)
        arch[norm_id(r[ix['PROJ']])] = dict(org=norm_id(r[ix['Org']]),
                                           team=stripq(r[ix['Team']]),
                                           status=stripq(r[ix['Status']]),
                                           closed=closed)
    reg = dict(arch)
    reg.update(main)
    return reg, main, arch


def main(data_dir, out_dir):
    ctx = build(data_dir)
    live = load_queries(ctx)
    live = apply_adjustments(ctx, live)
    compute_pools(ctx, live)
    compute_candidates(ctx)
    for cd in ctx.candidates.values():
        cd['valid_hours_set'] = set(cd['valid_hours'])
    run_commitments(ctx)
    os.makedirs(out_dir, exist_ok=True)
    out = Out(out_dir)
    write_cache_plan(ctx, out)
    write_pool_curves(ctx, out)
    write_pool_hourly(ctx, out)
    write_hourly_rollup(ctx, out)
    write_rates_used(ctx, out)
    write_ruleset_used(ctx, out)
    out.json('dedup_report.json', dict(rows_read=ctx.dedup['rows_read'],
                                      duplicate_rows_dropped=ctx.dedup['duplicate_rows_dropped'],
                                      voided_rows=ctx.dedup['voided_rows'],
                                      live_queries=ctx.dedup['live_queries']))
    out.json('source_lineage.json', ctx.lineage)
    out.jsonl('applied_adjustments.jsonl', ctx.applied)
    write_project_resolution(ctx, out)
    write_scope_projects(ctx, out)
    out.jsonl('excluded_queries.jsonl',
              [dict(query_id=q, reason=r) for q, r in sorted(ctx.excluded)])
    write_reservation_dispositions(ctx, out)
    out.jsonl('excluded_pools.jsonl', ctx.excluded_pools)
    out.jsonl('cluster_commitments.jsonl',
              [dict(round=r['round'], cluster=r['cluster'],
                    planned_nodes=r['planned_nodes'], min_nodes=r['min_nodes'],
                    saving_exact_cents=plain(r['saving_exact_cents']),
                    short_clusters=r['short_clusters']) for r in ctx.closure_rounds])
    write_family_rollup(ctx, out)
    write_cluster_rollup(ctx, out)
    write_chargeback(ctx, out)
    write_plan_summary(ctx, out)
    write_variance(ctx, out)
    write_reconciliation(ctx, out)
    write_manifest(ctx, out)
    return ctx


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('usage: plan_cache.py DATA_DIR OUT_DIR', file=sys.stderr)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
