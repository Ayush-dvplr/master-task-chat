#!/usr/bin/env python3
"""Result-cache node plan, computed per cache_planning_rulebook.md revision 5."""

import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
import zipfile
import zlib
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from decimal import (Decimal, ROUND_HALF_DOWN, ROUND_HALF_EVEN,
                     ROUND_HALF_UP, getcontext)

getcontext().prec = 80

HOUR = timedelta(hours=1)
D0 = Decimal(0)


# ---------------------------------------------------------------- helpers

def nid(v):
    """P1.1 identifier normalisation."""
    if v is None:
        return ''
    return str(v).strip().strip('"').strip("'").strip().upper()


def lid(v):
    return nid(v).lower()


def dstr(v):
    """Plain decimal string, no exponent, trailing zeros removed."""
    if isinstance(v, int):
        return str(v)
    d = Decimal(v)
    if d == 0:
        return '0'
    s = format(d.normalize(), 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s or '0'


ROUNDINGS = {'half_even': ROUND_HALF_EVEN, 'half_up': ROUND_HALF_UP,
             'half_down': ROUND_HALF_DOWN}


def q(v, places, rounding=ROUND_HALF_EVEN):
    return Decimal(v).quantize(Decimal(1).scaleb(-places), rounding=rounding)


def numval(v):
    """JSON number for a workbook constant."""
    d = Decimal(v)
    return int(d) if d == d.to_integral_value() else float(d)


def pct(v):
    return format(q(v, 2), 'f')


def utc(ts):
    return ts.strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_offset(text):
    m = re.match(r'^([+-])(\d{2}):?(\d{2})$', text.strip())
    sign = -1 if m.group(1) == '-' else 1
    return timedelta(minutes=sign * (int(m.group(2)) * 60 + int(m.group(3))))


def parse_wall(text):
    return datetime.strptime(text.strip().replace('T', ' '), '%Y-%m-%d %H:%M:%S')


# ---------------------------------------------------------------- mini YAML

def _yaml_lines(text):
    out = []
    for raw in text.split('\n'):
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        out.append((len(raw) - len(raw.lstrip(' ')), raw.strip()))
    return out


def _yaml_scalar(text):
    t = text.strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in '"\'':
        return t[1:-1]
    return t


def _yaml_block(lines, i, indent):
    if lines[i][1].startswith('- '):
        seq = []
        while i < len(lines) and lines[i][0] == indent and lines[i][1].startswith('- '):
            body = lines[i][1][2:]
            if re.match(r'^[A-Za-z_][\w\-]*\s*:', body):
                sub = [(indent + 2, body)]
                j = i + 1
                while j < len(lines) and lines[j][0] > indent:
                    sub.append((indent + 2, lines[j][1]))
                    j += 1
                val, _ = _yaml_block(sub, 0, indent + 2)
                seq.append(val)
                i = j
            else:
                seq.append(_yaml_scalar(body))
                i += 1
        return seq, i
    mapping = {}
    while i < len(lines) and lines[i][0] == indent and not lines[i][1].startswith('- '):
        key, _, rest = lines[i][1].partition(':')
        key = key.strip()
        if rest.strip():
            mapping[key] = _yaml_scalar(rest)
            i += 1
        else:
            i += 1
            if i < len(lines) and (lines[i][0] > indent or
                                   (lines[i][0] == indent and
                                    lines[i][1].startswith('- '))):
                val, i = _yaml_block(lines, i, lines[i][0])
                mapping[key] = val
            else:
                mapping[key] = None
    return mapping, i


def load_yaml(path):
    lines = _yaml_lines(open(path, encoding='utf-8').read())
    val, _ = _yaml_block(lines, 0, lines[0][0])
    return val


# ---------------------------------------------------------------- xlsx

XNS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
XREL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def _col_index(ref):
    n = 0
    for ch in re.match(r'([A-Za-z]+)', ref).group(1).upper():
        n = n * 26 + ord(ch) - 64
    return n


class Workbook:
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        self.shared = []
        try:
            root = ET.fromstring(self.z.read('xl/sharedStrings.xml'))
            for si in root.findall(XNS + 'si'):
                self.shared.append(''.join(t.text or '' for t in si.iter(XNS + 't')))
        except KeyError:
            pass
        rels = {}
        for rel in ET.fromstring(self.z.read('xl/_rels/workbook.xml.rels')):
            rels[rel.get('Id')] = rel.get('Target')
        wb = ET.fromstring(self.z.read('xl/workbook.xml'))
        pr = wb.find(XNS + 'workbookPr')
        d1904 = pr is not None and str(pr.get('date1904', '0')).lower() in ('1', 'true')
        self.epoch = datetime(1904, 1, 1) if d1904 else datetime(1899, 12, 30)
        self.sheets = {}
        for s in wb.find(XNS + 'sheets'):
            target = rels[s.get(XREL + 'id')]
            if not target.startswith('xl/'):
                target = 'xl/' + target.lstrip('/')
            self.sheets[s.get('name')] = target

    def rows(self, name):
        root = ET.fromstring(self.z.read(self.sheets[name]))
        out = []
        for row in root.iter(XNS + 'row'):
            cells = {}
            nxt = 1
            for c in row.findall(XNS + 'c'):
                t = c.get('t')
                v = c.find(XNS + 'v')
                if t == 's':
                    val = self.shared[int(v.text)]
                elif t == 'inlineStr':
                    val = ''.join(x.text or '' for x in c.iter(XNS + 't'))
                else:
                    val = v.text if v is not None else ''
                ref = c.get('ref') or c.get('r')
                idx = _col_index(ref) if ref else nxt
                nxt = idx + 1
                cells[idx] = val
            if cells:
                out.append([cells.get(i, '') for i in range(1, max(cells) + 1)])
        return out

    def serial_date(self, serial):
        return (self.epoch + timedelta(days=int(str(serial).strip()))).date()


# ---------------------------------------------------------------- pdf

def _pdf_unescape(raw):
    res = bytearray()
    i = 0
    while i < len(raw):
        c = raw[i]
        if c == 0x5c:
            i += 1
            n = raw[i]
            if n in b'nrtbf':
                res += {0x6e: b'\n', 0x72: b'\r', 0x74: b'\t',
                        0x62: b'\b', 0x66: b'\f'}[n]
                i += 1
            elif 0x30 <= n <= 0x37:
                digits = bytearray()
                while len(digits) < 3 and i < len(raw) and 0x30 <= raw[i] <= 0x37:
                    digits.append(raw[i])
                    i += 1
                res.append(int(digits, 8))
            else:
                res.append(n)
                i += 1
        else:
            res.append(c)
            i += 1
    return res.decode('latin-1')


def _pdf_strings(seg):
    out = []
    i = 0
    n = len(seg)
    while i < n:
        c = seg[i:i + 1]
        if c == b'(':
            depth = 1
            j = i + 1
            buf = bytearray()
            while j < n:
                ch = seg[j]
                if ch == 0x5c:
                    buf += seg[j:j + 2]
                    j += 2
                    continue
                if ch == 0x28:
                    depth += 1
                elif ch == 0x29:
                    depth -= 1
                    if depth == 0:
                        break
                buf.append(ch)
                j += 1
            out.append(_pdf_unescape(bytes(buf)))
            i = j + 1
        elif c == b'<' and seg[i + 1:i + 2] != b'<':
            j = seg.find(b'>', i)
            hx = re.sub(rb'\s', b'', seg[i + 1:j])
            if len(hx) % 2:
                hx += b'0'
            out.append(bytes.fromhex(hx.decode()).decode('latin-1'))
            i = j + 1
        else:
            i += 1
    return ''.join(out)


def _pdf_text_blocks(stream):
    segs = []
    i = 0
    n = len(stream)
    start = None
    while i < n:
        c = stream[i:i + 1]
        if c == b'(':
            depth = 1
            i += 1
            while i < n and depth:
                ch = stream[i]
                if ch == 0x5c:
                    i += 2
                    continue
                if ch == 0x28:
                    depth += 1
                elif ch == 0x29:
                    depth -= 1
                i += 1
            continue
        if c == b'<' and stream[i + 1:i + 2] != b'<':
            j = stream.find(b'>', i)
            i = (j + 1) if j >= 0 else n
            continue
        if stream[i:i + 2] == b'BT' and (i == 0 or stream[i - 1:i].isspace()):
            start = i + 2
            i += 2
            continue
        if stream[i:i + 2] == b'ET' and start is not None and \
                (i == 0 or stream[i - 1:i].isspace()):
            segs.append(stream[start:i])
            start = None
            i += 2
            continue
        i += 1
    return segs


def pdf_page_rows(path):
    data = open(path, 'rb').read()
    objs = {}
    for m in re.finditer(rb'(?:^|[\r\n])(\d+)\s+0\s+obj\b', data):
        objs[int(m.group(1))] = data[m.end():data.find(b'endobj', m.end())]
    pages = None
    for body in objs.values():
        if re.search(rb'/Type\s*/Pages\b', body):
            pages = body
            break
    kids = [int(x) for x in re.findall(
        rb'(\d+)\s+0\s+R', re.search(rb'/Kids\s*\[(.*?)\]', pages, re.S).group(1))]
    out = []
    for k in kids:
        body = objs[k]
        cnum = int(re.search(rb'/Contents\s+(\d+)\s+0\s+R', body).group(1))
        cbody = objs[cnum]
        sm = re.search(rb'stream\r?\n', cbody)
        raw = cbody[sm.end():cbody.find(b'endstream', sm.end())]
        if b'FlateDecode' in cbody:
            raw = zlib.decompress(raw)
        cells = {}
        for seg in _pdf_text_blocks(raw):
            cuts = [p for p in (seg.find(b'('), seg.find(b'<')) if p >= 0]
            cut = min(cuts) if cuts else len(seg)
            tm = re.search(rb'1\s+0\s+0\s+1\s+([-\d.]+)\s+([-\d.]+)\s+Tm', seg[:cut])
            if not tm:
                continue
            cells.setdefault(round(float(tm.group(2)), 3), []).append(
                (float(tm.group(1)), _pdf_strings(seg[tm.end():])))
        out.append([[t for _, t in sorted(cells[y])]
                    for y in sorted(cells, reverse=True)])
    return out


PDF_TABLES = {
    'R-1': ['family', 'cluster', 'scan_rate_cents', 'node_rate_cents'],
    'R-2': ['family', 'cluster', 'scan_rate_cents', 'node_rate_cents'],
    'E-1': ['erratum_id', 'family', 'cluster', 'field', 'new_value', 'status'],
    'C-1': ['reservation_id', 'ruling', 'revised_end_utc'],
    'M-0': ['cluster', 'min_nodes'],
    'M-1': ['cluster', 'min_nodes'],
}


def read_bulletin(path):
    tables = {k: [] for k in PDF_TABLES}
    current = None
    for rows in pdf_page_rows(path):
        for row in rows:
            if len(row) == 1:
                m = re.match(r'Table ([A-Z]-\d)\b', row[0].strip())
                if m and m.group(1) in tables:
                    current = m.group(1)
                continue
            if current is None:
                continue
            header = PDF_TABLES[current]
            cells = [c.strip() for c in row]
            if cells == header or len(cells) != len(header):
                continue
            tables[current].append(cells)
    return tables


# ---------------------------------------------------------------- feeds

def _rows_jsonl_flat(path):
    for line in open(path, encoding='utf-8'):
        if not line.strip():
            continue
        o = json.loads(line, parse_float=Decimal, parse_int=Decimal)
        yield (o['qid'], o['start'], o['proj'], o['clu'], o['tpl'], o['wh'],
               o['gib'], o['opt'], o['st'], o['rev'])


def _rows_ndjson_nested(path):
    for line in open(path, encoding='utf-8'):
        if not line.strip():
            continue
        o = json.loads(line, parse_float=Decimal, parse_int=Decimal)
        yield (o['query']['id'], o['scan']['start'], o['ctx']['project'],
               o['ctx']['cluster'], o['ctx']['template'], o['ctx']['size'],
               o['scan']['mib'], o['bill']['option'], o['bill']['status'],
               o['query']['rev'])


def _rows_csv_a(path):
    with open(path, encoding='utf-8-sig', newline='') as fh:
        for r in csv.DictReader(fh):
            yield (r['query_id'], r['started_utc'], r['project_id'], r['cluster'],
                   r['template_id'], r['wh_size'], r['scanned_gib'],
                   r['cache_option'], r['query_status'], r['revision'])


def _rows_tsv_epoch(path):
    with open(path, encoding='utf-8', newline='') as fh:
        for r in csv.DictReader(fh, delimiter='\t'):
            yield (r['id'], r['epoch_s'], r['proj'], r['clu'], r['tpl'], r['wh'],
                   r['scan_kib'], r['opt'], r['st'], r['rev'])


def _rows_psv_local(path):
    with open(path, encoding='utf-8', newline='') as fh:
        for r in csv.DictReader(fh, delimiter='|'):
            yield (r['id'], r['local_start'], r['proj'], r['clu'], r['tpl'],
                   r['wh'], r['gib'], r['opt'], r['st'], r['rev'])


def _rows_txt_fixed(path):
    cols = [(0, 12), (12, 26), (26, 38), (38, 63), (63, 73), (73, 77),
            (77, 89), (89, 91), (91, 92), (92, 95)]
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line.strip() or line.startswith('#'):
            continue
        yield tuple(line[a:b].strip() for a, b in cols)


def _rows_xml_attr(path):
    for el in ET.parse(path).getroot().iter('q'):
        yield (el.get('id'), el.get('t'), el.get('p'), el.get('c'), el.get('tp'),
               el.get('w'), el.get('g'), el.get('o'), el.get('s'), el.get('v'))


def _rows_xml_elem(path):
    for el in ET.parse(path).getroot().iter('query'):
        g = {c.tag: (c.text or '') for c in el}
        yield (g['id'], g['epoch'], g['project'], g['cluster'], g['template'],
               g['size'], g['gib'], g['option'], g['status'], g['rev'])


def _rows_yaml_list(path):
    for item in load_yaml(path)['records']:
        yield (item['id'], item['start'], item['project'], item['cluster'],
               item['template'], item['size'], item['gib'], item['option'],
               item['status'], item['rev'])


def _rows_yml_list(path):
    for item in load_yaml(path):
        size, _, tpl = str(item['shape']).partition('@')
        yield (item['qid'], item['local'], item['prj'], item['clu'], tpl, size,
               item['gib'], item['o'], item['s'], item['rev'])


def _rows_json_array(path):
    doc = json.load(open(path, encoding='utf-8'), parse_float=Decimal,
                    parse_int=Decimal)
    for r in doc['export']['rows']:
        yield (r['queryId'], r['epochMillis'], r['projectId'], r['clusterCode'],
               r['templateId'], r['whSize'], r['scannedMib'], r['option'],
               r['status'], r['revision'])


def _rows_json_keyed(path):
    doc = json.load(open(path, encoding='utf-8'), parse_float=Decimal,
                    parse_int=Decimal)
    for key, r in doc.items():
        yield (key, r['ms'], r['p'], r['c'], r['t'], r['w'], r['mib'], r['o'],
               r['s'], r['v'])


def _rows_sqlite(path, table, cols):
    con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
    try:
        for row in con.execute('SELECT %s FROM %s' % (','.join(cols), table)):
            yield tuple('' if v is None else v for v in row)
    finally:
        con.close()


def _rows_sqlite_rows(path):
    return _rows_sqlite(path, 'query_log', [
        'query_id', 'started_utc', 'project_id', 'cluster', 'template_id',
        'wh_size', 'scanned_gib', 'cache_option', 'query_status', 'revision'])


def _rows_db_rows(path):
    return _rows_sqlite(path, 'ql', [
        'qid', 'ep', 'prj', 'clu', 'tpl', 'wh', 'cg', 'oc', 'sc', 'rv'])


def _rows_csv_offset(path):
    with open(path, encoding='utf-8-sig', newline='') as fh:
        for r in csv.DictReader(fh):
            yield (r['query'], r['ts_offset'], r['project'], r['cluster'],
                   r['template'], r['size'], r['kib'], r['opt'], r['code'],
                   r['rev'])


KV_RE = re.compile(r'(\w+)=("[^"]*"|\S*)')


def _rows_txt_kv(path):
    for line in open(path, encoding='utf-8'):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        g = {k: v.strip('"') for k, v in KV_RE.findall(line)}
        yield (g['query'], g['at'], g['project'], g['cluster'], g['template'],
               g['size'], g['gib'], g['option'], g['state'], g['rev'])


READERS = {
    'jsonl_flat': _rows_jsonl_flat,
    'ndjson_nested': _rows_ndjson_nested,
    'csv_a': _rows_csv_a,
    'tsv_epoch': _rows_tsv_epoch,
    'psv_local': _rows_psv_local,
    'txt_fixed': _rows_txt_fixed,
    'xml_attr': _rows_xml_attr,
    'xml_elem': _rows_xml_elem,
    'yaml_list': _rows_yaml_list,
    'yml_list': _rows_yml_list,
    'json_array': _rows_json_array,
    'json_keyed': _rows_json_keyed,
    'sqlite_rows': _rows_sqlite_rows,
    'db_rows': _rows_db_rows,
    'csv_offset': _rows_csv_offset,
    'txt_kv': _rows_txt_kv,
}

QTY_DIVISOR = {'gib': Decimal(1), 'mib': Decimal(1024),
               'kib': Decimal(1048576), 'cgib': Decimal(100)}


# ---------------------------------------------------------------- planner

class Query:
    __slots__ = ('qid', 'start', 'proj', 'cluster', 'tpl', 'size', 'gib', 'opt')

    def __init__(self, qid, start, proj, cluster, tpl, size, gib, opt):
        self.qid = qid
        self.start = start
        self.proj = proj
        self.cluster = cluster
        self.tpl = tpl
        self.size = size
        self.gib = gib
        self.opt = opt


class Plan:
    def __init__(self, data_dir):
        self.data = data_dir
        self.load_reference()
        self.load_feeds()
        self.apply_adjustments()
        self.build_pools()
        self.optimise()

    def p(self, name):
        return os.path.join(self.data, name)

    # -- reference material ------------------------------------------------
    def load_reference(self):
        prof = load_yaml(self.p('plan_profile_qa4.yml'))
        self.profile = prof
        self.plan_id = prof['plan_id']
        self.org_id = nid(prof['org_id'])
        self.billing_offset = parse_offset(prof['billing_offset'])
        self.W0 = parse_wall(prof['lookback_start_local']) - self.billing_offset
        self.W1 = parse_wall(prof['lookback_end_local']) - self.billing_offset
        self.H = int((self.W1 - self.W0) // HOUR)
        self.horizon = datetime.strptime(prof['horizon_end_utc'],
                                         '%Y-%m-%dT%H:%M:%SZ')
        self.lookback_start_date = parse_wall(prof['lookback_start_local']).date()

        self.alias = {}
        for item in load_yaml(self.p('cluster_aliases.yaml'))['clusters']:
            self.alias[nid(item['alias'])] = nid(item['canonical'])
        self.clusters_in_scope = {self.canon(c['cluster'])
                                  for c in prof['clusters_in_scope']}

        self.ledger = {}
        with open(self.p('project_merges.psv'), encoding='utf-8', newline='') as fh:
            for r in csv.DictReader(fh, delimiter='|'):
                eff = (datetime.strptime(r['merged_on'].strip(), '%Y-%m-%d')
                       - self.billing_offset)
                self.ledger[nid(r['from_project'])] = (nid(r['merged_into']), eff)

        self.registry = {}
        with open(self.p('proj_registry_archive.tsv'), encoding='utf-8',
                  newline='') as fh:
            for r in csv.DictReader(fh, delimiter='\t'):
                closed = r['Closed'].strip()
                self.registry[nid(r['PROJ'])] = {
                    'org': nid(r['Org']), 'team': nid(r['Team']),
                    'status': r['Status'].strip(),
                    'closed': datetime.strptime(closed, '%d/%m/%Y').date()
                    if closed else None}
        with open(self.p('proj_registry_main.csv'), encoding='utf-8',
                  newline='') as fh:
            for r in csv.DictReader(fh):
                closed = r['closed_on'].strip()
                self.registry[nid(r['project_id'])] = {
                    'org': nid(r['org_id']), 'team': nid(r['team']),
                    'status': r['project_status'].strip(),
                    'closed': datetime.strptime(closed, '%Y-%m-%d').date()
                    if closed else None}

        self.dev_projects = {self.resolve(d['project'], self.W1)[0]
                             for d in prof['dev_projects']}

        wb = Workbook(self.p('capacity_workbook_fy26.xlsx'))
        track = nid(prof['ruleset_track'])
        best = None
        for row in wb.rows('Adoptions'):
            if len(row) < 5 or row[0].strip() == 'adoption_id':
                continue
            if nid(row[1]) != track or nid(row[4]) != 'ADOPTED':
                continue
            date = wb.serial_date(row[3])
            if date > self.lookback_start_date:
                continue
            if best is None or date > best[0]:
                best = (date, nid(row[0]), row[2].strip())
        self.sheet_date, self.adoption_id, self.sheet = best

        self.families = {}
        consts = {}
        for row in wb.rows(self.sheet):
            tag = row[0].strip() if row else ''
            if tag == 'PLAN':
                consts[row[1].strip()] = row[2].strip()
            elif tag == 'FAM':
                v = [c.strip() for c in row[1:10]]
                self.families[lid(v[0])] = {
                    'family': lid(v[0]),
                    'eligible': v[1].lower() in ('y', 'yes', 'true', '1'),
                    'node_units': int(v[2]),
                    'min_nodes': int(v[3]),
                    'family_cap': int(v[4]),
                    'growth_pct': Decimal(v[5]),
                    'tier_units': Decimal(v[6]),
                    'tier_discount_pct': Decimal(v[7]),
                    'mem_units_per_node': int(v[8]),
                }
        self.node_cap_total = int(consts['node_cap_total'])
        self.mem_budget_units = int(consts['mem_budget_units'])
        self.saving_rounding = consts['saving_rounding']
        self.rounding = ROUNDINGS[self.saving_rounding.strip().lower()]

        self.factors = {}
        for row in wb.rows('ScanFactors'):
            if len(row) >= 2 and row[0].strip() and row[0].strip() != 'engine':
                self.factors[lid(row[0])] = Decimal(row[1].strip())

        self.cluster_offset = {}
        for row in wb.rows('Clusters'):
            if len(row) >= 2 and row[0].strip() and row[0].strip() != 'cluster':
                self.cluster_offset[nid(row[0])] = parse_offset(row[1])

        self.outages = {}
        for win in prof['outage_windows']:
            self.outages.setdefault(self.canon(win['cluster']), []).append(
                (parse_wall(win['from_local']) - self.billing_offset,
                 parse_wall(win['to_local']) - self.billing_offset))

        self.tpl_family = {}
        text = open(self.p('feed_layouts.md'), encoding='utf-8').read()
        for line in text.split('## Appendix T', 1)[1].split('\n'):
            if not line.startswith('|'):
                continue
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if len(cells) < 2 or cells[0] == 'template_id' or \
                    set(cells[0]) <= set('-: '):
                continue
            self.tpl_family[nid(cells[0])] = lid(cells[1])

        tables = read_bulletin(self.p('pricing_bulletin_q4.pdf'))
        self.rates = {}
        for fam, clu, scan, node in tables['R-2']:
            self.rates[(lid(fam), self.canon(clu))] = {'scan': scan, 'node': node}
        self.errata = []
        for row in sorted(tables['E-1'], key=lambda r: r[0]):
            erratum, fam, clu, field, value, status = row
            key = (lid(fam), self.canon(clu))
            in_force = status.strip().upper() == 'IN FORCE'
            self.errata.append((erratum, key, field.strip(), value, status.strip()))
            if in_force and key in self.rates:
                self.rates[key]['scan' if field.strip() == 'scan_rate_cents'
                                 else 'node'] = value
        self.rulings = {}
        for rid, ruling, revised in tables['C-1']:
            self.rulings[nid(rid)] = (ruling.strip().upper(), revised.strip())
        self.commitments = {}
        for clu, mn in tables['M-1']:
            self.commitments[self.canon(clu)] = int(mn)

    def canon(self, token):
        key = nid(token)
        return self.alias.get(key, key)

    def resolve(self, token, instant):
        cur = nid(token)
        hops = 0
        path = [cur]
        seen = {cur: 0}
        while True:
            row = self.ledger.get(cur)
            if row is None or instant < row[1]:
                return cur, hops
            nxt = row[0]
            hops += 1
            if nxt in seen:
                return min(path[seen[nxt]:]), hops
            seen[nxt] = len(path)
            path.append(nxt)
            cur = nxt

    def project_reason(self, pid):
        info = self.registry.get(pid)
        if info is None:
            return 'UNKNOWN_PROJECT'
        if info['org'] != self.org_id:
            return 'OTHER_ORG'
        if info['status'].upper() == 'CLOSED' and info['closed'] is not None \
                and info['closed'] < self.lookback_start_date:
            return 'CLOSED_PROJECT'
        if pid in self.dev_projects:
            return 'DEV_PROJECT'
        return None

    # -- feeds -------------------------------------------------------------
    def load_feeds(self):
        manifest = json.load(open(self.p('ingest_manifest_r7.json'),
                                  encoding='utf-8'))
        self.lineage = {}
        rows_read = 0
        best = {}
        for shard in manifest['shards']:
            name = shard['file']
            opt_map = {k.strip(): v.strip() for k, v in shard['option_codes'].items()}
            st_map = {k.strip(): v.strip() for k, v in shard['status_codes'].items()}
            divisor = QTY_DIVISOR[shard['qty_unit'].strip().lower()]
            conv = shard['ts_convention'].strip()
            count = 0
            for raw in READERS[shard['layout']](self.p(name)):
                count += 1
                qid = nid(raw[0])
                cluster = self.canon(raw[3])
                rec = {
                    'qid': qid,
                    'start': self.to_utc(raw[1], conv, cluster),
                    'proj': nid(raw[2]), 'cluster': cluster, 'tpl': nid(raw[4]),
                    'size': lid(raw[5]),
                    'gib': Decimal(str(raw[6]).strip()) / divisor,
                    'opt': opt_map.get(str(raw[7]).strip()),
                    'status': st_map.get(str(raw[8]).strip()),
                    'rev': int(Decimal(str(raw[9]).strip())),
                    'shard': name,
                }
                prev = best.get(qid)
                if prev is None or rec['rev'] > prev['rev']:
                    best[qid] = rec
            rows_read += count
            self.lineage[name] = {'rows': count, 'kept': 0}

        voided = 0
        live = {}
        for qid, rec in best.items():
            if rec['status'] == 'V':
                voided += 1
                continue
            self.lineage[rec['shard']]['kept'] += 1
            live[qid] = Query(qid, rec['start'], rec['proj'], rec['cluster'],
                              rec['tpl'], rec['size'], rec['gib'], rec['opt'])
        self.dedup = {
            'rows_read': rows_read,
            'duplicate_rows_dropped': rows_read - len(best),
            'voided_rows': voided,
            'live_queries': len(live),
        }
        self.live = live

    def to_utc(self, raw, conv, cluster):
        text = str(raw).strip()
        if conv == 'iso_z':
            return datetime.strptime(text, '%Y-%m-%dT%H:%M:%SZ')
        if conv == 'iso_offset':
            return datetime.fromisoformat(text).astimezone(
                timezone.utc).replace(tzinfo=None)
        if conv == 'epoch_s':
            return datetime(1970, 1, 1) + timedelta(seconds=int(Decimal(text)))
        if conv == 'epoch_ms':
            return datetime(1970, 1, 1) + timedelta(
                milliseconds=int(Decimal(text)))
        if conv == 'compact_utc':
            return datetime.strptime(text, '%Y%m%d%H%M%S')
        if conv == 'local_cluster':
            return parse_wall(text) - self.cluster_offset[cluster]
        if conv == 'local_billing':
            return parse_wall(text) - self.billing_offset
        raise ValueError(conv)

    # -- adjustments -------------------------------------------------------
    def apply_adjustments(self):
        entries = []
        for line in open(self.p('scan_adjustments.jsonl'), encoding='utf-8'):
            if not line.strip():
                continue
            o = json.loads(line)
            entries.append(('jsonl', int(o['seq']), o))
        for el in ET.parse(self.p('scan_adjustments_late.xml')).getroot().iter(
                'entry'):
            o = {c.tag: (c.text or '') for c in el}
            o['status'] = el.get('status')
            o['query_id'] = o.pop('query', '')
            entries.append(('xml', int(el.get('seq')), o))
        entries.sort(key=lambda e: e[1])

        self.applied = []
        for journal, seq, o in entries:
            if str(o.get('status', '')).strip().lower() != 'posted':
                continue
            op = str(o['op']).strip().upper()
            qid = nid(o.get('query_id'))
            if op == 'ADD':
                if qid in self.live:
                    outcome = 'skipped_duplicate'
                else:
                    self.live[qid] = Query(
                        qid,
                        datetime.strptime(str(o['usage_start_utc']).strip(),
                                          '%Y-%m-%dT%H:%M:%SZ'),
                        nid(o['project']), self.canon(o['cluster']),
                        nid(o['template']), lid(o['size']),
                        Decimal(str(o['quantity_gib']).strip()),
                        str(o['option']).strip())
                    outcome = 'applied'
            elif qid not in self.live:
                outcome = 'skipped_missing'
            elif op == 'VOID':
                del self.live[qid]
                outcome = 'applied'
            elif op == 'SETQTY':
                self.live[qid].gib = Decimal(str(o['quantity_gib']).strip())
                outcome = 'applied'
            elif op == 'MOVE':
                self.live[qid].proj = nid(o['project'])
                outcome = 'applied'
            elif op == 'RETAG':
                self.live[qid].tpl = nid(o['template'])
                outcome = 'applied'
            else:
                outcome = 'applied'
            self.applied.append({'journal': journal, 'op': op,
                                 'outcome': outcome, 'query_id': qid,
                                 'seq': seq})

    # -- pools -------------------------------------------------------------
    def is_outage(self, cluster, hour):
        start = self.W0 + hour * HOUR
        for lo, hi in self.outages.get(cluster, ()):
            if lo <= start < hi:
                return True
        return False

    def build_pools(self):
        self.out_of_window = 0
        self.excluded = []
        included = []
        for qid in sorted(self.live):
            qr = self.live[qid]
            if not (self.W0 <= qr.start < self.W1):
                self.out_of_window += 1
                continue
            hour = int((qr.start - self.W0) // HOUR)
            family = self.tpl_family.get(qr.tpl)
            pid = self.resolve(qr.proj, qr.start)[0]
            reason = self.project_reason(pid)
            if reason is None:
                if qr.cluster not in self.clusters_in_scope:
                    reason = 'CLUSTER_OUT_OF_SCOPE'
                elif family not in self.families \
                        or not self.families[family]['eligible']:
                    reason = 'INELIGIBLE_FAMILY'
                elif qr.opt == 'B':
                    reason = 'BATCH_QUERY'
                elif self.is_outage(qr.cluster, hour):
                    reason = 'OUTAGE_HOUR'
            if reason is not None:
                self.excluded.append({'query_id': qid, 'reason': reason})
                continue
            included.append((qr, family, pid, hour))

        self.reservations = self.read_reservations()
        netted = {}
        for r in self.reservations:
            if r['status'] == 'NETTED':
                netted[r['pool_id']] = netted.get(r['pool_id'], D0) + r['units']
        self.netted_total = sum(netted.values(), D0)

        pools = {}
        for qr, family, pid, hour in included:
            pool_id = '%s@%s' % (family.upper(), qr.cluster)
            pool = pools.get(pool_id)
            if pool is None:
                pool = pools[pool_id] = {
                    'pool_id': pool_id, 'family': family, 'cluster': qr.cluster,
                    'usage': {}, 'proj_usage': {}}
            units = q(qr.gib * self.factors['%s.%s' % (family, qr.size)], 3)
            pool['usage'][hour] = pool['usage'].get(hour, D0) + units
            pool['proj_usage'][pid] = pool['proj_usage'].get(pid, D0) + units
        self.pools = pools

        for pool in pools.values():
            fam = self.families[pool['family']]
            hours = [h for h in range(self.H)
                     if not self.is_outage(pool['cluster'], h)]
            pool['valid_hours'] = hours
            net = netted.get(pool['pool_id'], D0)
            pool['net'] = net
            loads = {}
            for h in hours:
                grown = q(pool['usage'].get(h, D0) * (100 + fam['growth_pct'])
                          / 100, 2)
                loads[h] = max(D0, grown - net)
            pool['load'] = loads
            pool['max_load'] = max(loads.values()) if loads else D0
            pool['load_sum'] = sum(loads.values(), D0)
            pool['kmax'] = int(pool['max_load'] // fam['node_units'])

        self.excluded_pools = []
        self.candidates = []
        for pool_id in sorted(pools):
            pool = pools[pool_id]
            fam = self.families[pool['family']]
            if pool['max_load'] == 0:
                self.excluded_pools.append({'pool_id': pool_id,
                                            'reason': 'NO_RESIDUAL'})
            elif pool['kmax'] < fam['min_nodes']:
                self.excluded_pools.append({'pool_id': pool_id,
                                            'reason': 'BELOW_MIN_NODES'})
            else:
                self.candidates.append(pool)
                pool['levels'] = [0] + list(range(fam['min_nodes'],
                                                  pool['kmax'] + 1))
                pool['curve'] = {k: self.level(pool, k) for k in pool['levels']}

    def read_reservations(self):
        out = []
        for el in ET.parse(self.p('cache_reservations.xml')).getroot().iter(
                'reservation'):
            rid = nid(el.get('id'))
            family = lid(el.get('family'))
            cluster = self.canon(el.get('cluster'))
            owner = self.resolve(el.get('owner'), self.W1)[0]
            units = Decimal(el.get('units').strip())
            end = datetime.strptime(el.get('end_utc').strip(),
                                    '%Y-%m-%dT%H:%M:%SZ')
            ruling, revised = self.rulings.get(rid, (None, None))
            if ruling == 'EXTENDED' and revised and revised != '-':
                end = datetime.strptime(revised, '%Y-%m-%dT%H:%M:%SZ')
            fam = self.families.get(family)
            if ruling == 'CANCELLED':
                status = 'CANCELLED'
            elif el.get('state').strip().upper() != 'ACTIVE':
                status = 'NOT_ACTIVE'
            elif self.project_reason(owner) is not None:
                status = 'OWNER_OUT_OF_SCOPE'
            elif cluster not in self.clusters_in_scope or fam is None \
                    or not fam['eligible']:
                status = 'NO_POOL'
            elif end < self.horizon:
                status = 'LAPSES'
            else:
                status = 'NETTED'
            out.append({'reservation_id': rid,
                        'pool_id': '%s@%s' % (family.upper(), cluster),
                        'owner': owner, 'units': units, 'end': end,
                        'status': status})
        out.sort(key=lambda r: r['reservation_id'])
        return out

    def rate(self, family, cluster, which):
        return self.rates[(family, cluster)][which]

    def level(self, pool, k):
        fam = self.families[pool['family']]
        c = Decimal(k * fam['node_units'])
        served = D0
        for h in pool['valid_hours']:
            load = pool['load'][h]
            served += load if load < c else c
        node_rate = Decimal(self.rate(pool['family'], pool['cluster'], 'node'))
        if c >= fam['tier_units']:
            eff = q(node_rate * (100 - fam['tier_discount_pct']) / 100, 4)
        else:
            eff = node_rate
        scan_rate = Decimal(self.rate(pool['family'], pool['cluster'], 'scan'))
        return {'nodes': k, 'cache_units': k * fam['node_units'],
                'served': served, 'eff_rate': eff,
                'mem': k * fam['mem_units_per_node'],
                'saving': scan_rate * served - eff * len(pool['valid_hours']) * c}

    # -- optimisation ------------------------------------------------------
    def solve(self, closed):
        by_family = {}
        for pool in self.candidates:
            by_family.setdefault(pool['family'], []).append(pool)
        fam_order = sorted(by_family, key=lambda f: f.upper())

        fam_dp = {}
        for family in fam_order:
            fam = self.families[family]
            pools = sorted(by_family[family], key=lambda p: p['pool_id'])
            dp = {0: (D0, ())}
            for pool in pools:
                levels = [0] if pool['cluster'] in closed else pool['levels']
                nxt = {}
                for n, (sv, vec) in dp.items():
                    for k in levels:
                        tot = n + k
                        if tot > fam['family_cap'] or tot > self.node_cap_total:
                            continue
                        cand = (sv + pool['curve'][k]['saving'], vec + (k,))
                        cur = nxt.get(tot)
                        if cur is None or cand[0] > cur[0] or \
                                (cand[0] == cur[0] and cand[1] < cur[1]):
                            nxt[tot] = cand
                dp = nxt
            fam_dp[family] = (pools, fam['mem_units_per_node'], dp)

        states = {(0, 0): (D0, ())}
        for family in fam_order:
            mem_per = fam_dp[family][1]
            dp = fam_dp[family][2]
            nxt = {}
            for (nodes, mem), (sv, fvec) in states.items():
                for n, fval in dp.items():
                    tn = nodes + n
                    tm = mem + n * mem_per
                    if tn > self.node_cap_total or tm > self.mem_budget_units:
                        continue
                    cand = (sv + fval[0], fvec + (n,))
                    cur = nxt.get((tn, tm))
                    if cur is None or cand[0] > cur[0] or \
                            (cand[0] == cur[0] and cand[1] < cur[1]):
                        nxt[(tn, tm)] = cand
            states = nxt

        best = None
        for (nodes, mem), (sv, fvec) in states.items():
            key = (-sv, nodes, mem, fvec)
            if best is None or key < best[0]:
                best = (key, fvec)
        assignment = {}
        for family, n in zip(fam_order, best[1]):
            pools, _, dp = fam_dp[family]
            for pool, k in zip(pools, dp[n][1]):
                assignment[pool['pool_id']] = k
        return assignment

    def optimise(self):
        closed = set()
        self.rounds = []
        while True:
            assignment = self.solve(closed)
            by_cluster = {}
            for pool in self.candidates:
                k = assignment[pool['pool_id']]
                entry = by_cluster.setdefault(pool['cluster'], [0, D0])
                entry[0] += k
                entry[1] += pool['curve'][k]['saving']
            short = []
            for cluster, (nodes, saving) in by_cluster.items():
                mn = self.commitments.get(cluster)
                if mn is not None and 1 <= nodes < mn:
                    short.append((saving, cluster, nodes, mn))
            if not short:
                self.assignment = assignment
                return
            short.sort(key=lambda s: (s[0], s[1]))
            saving, cluster, nodes, mn = short[0]
            self.rounds.append({
                'round': len(self.rounds) + 1, 'cluster': cluster,
                'planned_nodes': nodes, 'min_nodes': mn,
                'saving_exact_cents': dstr(saving),
                'short_clusters': len(short)})
            closed.add(cluster)


# ---------------------------------------------------------------- reporting

CONTRACT_FILES = [
    'cache_plan.csv', 'pool_curves.psv', 'pool_hourly.tsv', 'hourly_rollup.tsv',
    'rates_used.csv', 'ruleset_used.json', 'dedup_report.json',
    'source_lineage.json', 'applied_adjustments.jsonl', 'project_resolution.csv',
    'scope_projects.csv', 'excluded_queries.jsonl',
    'reservation_dispositions.csv', 'excluded_pools.jsonl',
    'cluster_commitments.jsonl', 'family_rollup.json', 'cluster_rollup.xml',
    'chargeback.csv', 'team_rollup.json', 'plan_summary.json',
    'variance_vs_published.csv', 'reconciliation.md',
]


class Writer:
    def __init__(self, out_dir):
        self.out = out_dir
        os.makedirs(out_dir, exist_ok=True)

    def write(self, name, text):
        with open(os.path.join(self.out, name), 'w', encoding='utf-8',
                  newline='') as fh:
            fh.write(text)

    def lines(self, name, rows):
        self.write(name, ''.join(r + '\n' for r in rows))

    def jsonl(self, name, objs):
        self.write(name, ''.join(json.dumps(o, sort_keys=True) + '\n'
                                 for o in objs))

    def doc(self, name, obj):
        self.write(name, json.dumps(obj, sort_keys=True, indent=2) + '\n')


def report(plan, out_dir):
    w = Writer(out_dir)
    assignment = plan.assignment
    cand = sorted(plan.candidates, key=lambda p: p['pool_id'])
    allpools = [plan.pools[k] for k in sorted(plan.pools)]

    rows = ['pool_id,family,cluster,nodes,cache_units,mem_units,'
            'hourly_node_cents,saving_cents,served_pct,utilization_pct']
    plan_savings = {}
    for pool in cand:
        k = assignment[pool['pool_id']]
        lv = pool['curve'][k]
        plan_savings[pool['pool_id']] = int(q(lv['saving'], 0, plan.rounding))
        served_pct = (lv['served'] / pool['load_sum'] * 100
                      if pool['load_sum'] else D0)
        util = ''
        if k > 0:
            util = pct(lv['served'] / (Decimal(lv['cache_units'])
                                       * len(pool['valid_hours'])) * 100)
        rows.append(','.join([
            pool['pool_id'], pool['family'], pool['cluster'], str(k),
            str(lv['cache_units']), str(lv['mem']),
            dstr(lv['cache_units'] * lv['eff_rate']),
            str(plan_savings[pool['pool_id']]), pct(served_pct), util]))
    w.lines('cache_plan.csv', rows)

    rows = ['pool_id|nodes|cache_units|served_unit_hours|saving_exact_cents']
    for pool in cand:
        for k in pool['levels']:
            lv = pool['curve'][k]
            rows.append('|'.join([pool['pool_id'], str(k),
                                  str(lv['cache_units']), dstr(lv['served']),
                                  dstr(lv['saving'])]))
    w.lines('pool_curves.psv', rows)

    rows = ['pool_id\thour_index\thour_start_utc\tusage_units\tload_units']
    for pool in allpools:
        for h in pool['valid_hours']:
            rows.append('\t'.join([
                pool['pool_id'], str(h), utc(plan.W0 + h * HOUR),
                dstr(pool['usage'].get(h, D0)), dstr(pool['load'][h])]))
    w.lines('pool_hourly.tsv', rows)

    rows = ['hour_index\thour_start_utc\tpools_valid\tload_units\tcache_units\t'
            'served_units\toverflow_units']
    valid_set = {p['pool_id']: set(p['valid_hours']) for p in cand}
    for h in range(plan.H):
        n = 0
        load = cache = served = overflow = D0
        for pool in cand:
            if h not in valid_set[pool['pool_id']]:
                continue
            n += 1
            c = Decimal(pool['curve'][assignment[pool['pool_id']]]['cache_units'])
            ld = pool['load'][h]
            load += ld
            cache += c
            served += ld if ld < c else c
            if ld > c:
                overflow += ld - c
        rows.append('\t'.join([str(h), utc(plan.W0 + h * HOUR), str(n),
                               dstr(load), dstr(cache), dstr(served),
                               dstr(overflow)]))
    w.lines('hourly_rollup.tsv', rows)

    rows = ['pool_id,family,cluster,scan_rate_cents,node_rate_cents,node_units,'
            'min_nodes,growth_pct,tier_units,tier_discount_pct,'
            'mem_units_per_node,netted_units,valid_hours']
    for pool in allpools:
        fam = plan.families[pool['family']]
        rows.append(','.join([
            pool['pool_id'], pool['family'], pool['cluster'],
            plan.rate(pool['family'], pool['cluster'], 'scan'),
            plan.rate(pool['family'], pool['cluster'], 'node'),
            str(fam['node_units']), str(fam['min_nodes']),
            dstr(fam['growth_pct']), dstr(fam['tier_units']),
            dstr(fam['tier_discount_pct']), str(fam['mem_units_per_node']),
            dstr(pool['net']), str(len(pool['valid_hours']))]))
    w.lines('rates_used.csv', rows)

    w.doc('ruleset_used.json', {
        'sheet': plan.sheet,
        'adoption_id': plan.adoption_id,
        'effective_date': plan.sheet_date.isoformat(),
        'node_cap_total': plan.node_cap_total,
        'mem_budget_units': plan.mem_budget_units,
        'saving_rounding': plan.saving_rounding,
        'families': [{
            'family': f['family'], 'eligible': f['eligible'],
            'node_units': f['node_units'], 'min_nodes': f['min_nodes'],
            'family_cap': f['family_cap'], 'growth_pct': numval(f['growth_pct']),
            'tier_units': numval(f['tier_units']),
            'tier_discount_pct': numval(f['tier_discount_pct']),
            'mem_units_per_node': f['mem_units_per_node'],
        } for f in sorted(plan.families.values(),
                          key=lambda f: f['family'].upper())],
    })

    w.doc('dedup_report.json', plan.dedup)
    w.doc('source_lineage.json', plan.lineage)
    w.jsonl('applied_adjustments.jsonl', plan.applied)

    rows = ['alias,canonical,hops']
    for alias in sorted(plan.ledger):
        canonical, hops = plan.resolve(alias, plan.W1)
        rows.append('%s,%s,%d' % (alias, canonical, hops))
    w.lines('project_resolution.csv', rows)

    rows = ['project_id,team,project_status,scope']
    for pid in sorted(plan.registry):
        info = plan.registry[pid]
        if info['org'] != plan.org_id:
            continue
        if info['status'].upper() == 'CLOSED' and info['closed'] is not None \
                and info['closed'] < plan.lookback_start_date:
            scope = 'CLOSED'
        elif pid in plan.dev_projects:
            scope = 'DEV'
        else:
            scope = 'IN_SCOPE'
        rows.append('%s,%s,%s,%s' % (pid, info['team'], info['status'], scope))
    w.lines('scope_projects.csv', rows)

    w.jsonl('excluded_queries.jsonl',
            sorted(plan.excluded, key=lambda e: e['query_id']))

    rows = ['reservation_id,pool_id,owner_project,units,effective_end_utc,status']
    for r in plan.reservations:
        rows.append(','.join([r['reservation_id'], r['pool_id'], r['owner'],
                              dstr(r['units']), utc(r['end']), r['status']]))
    w.lines('reservation_dispositions.csv', rows)

    w.jsonl('excluded_pools.jsonl', plan.excluded_pools)
    w.jsonl('cluster_commitments.jsonl', plan.rounds)

    fam_roll = {}
    for pool in cand:
        k = assignment[pool['pool_id']]
        ent = fam_roll.setdefault(pool['family'].upper(), {
            'pools': 0, 'nodes': 0,
            'family_cap': plan.families[pool['family']]['family_cap'],
            'mem_units': 0, 'saving_cents': 0})
        ent['pools'] += 1
        ent['nodes'] += k
        ent['mem_units'] += pool['curve'][k]['mem']
        ent['saving_cents'] += plan_savings[pool['pool_id']]
    w.doc('family_rollup.json', fam_roll)

    clu_roll = {}
    for pool in cand:
        k = assignment[pool['pool_id']]
        ent = clu_roll.setdefault(pool['cluster'], {
            'pools': 0, 'nodes': 0, 'cache_units': 0, 'mem_units': 0,
            'saving_cents': 0})
        ent['pools'] += 1
        ent['nodes'] += k
        ent['cache_units'] += pool['curve'][k]['cache_units']
        ent['mem_units'] += pool['curve'][k]['mem']
        ent['saving_cents'] += plan_savings[pool['pool_id']]
    lines = ['<clusters plan="%s">' % plan.plan_id]
    for code in sorted(clu_roll):
        e = clu_roll[code]
        lines.append('<cluster code="%s" pools="%d" nodes="%d" cache_units="%d" '
                     'mem_units="%d" saving_cents="%d"/>'
                     % (code, e['pools'], e['nodes'], e['cache_units'],
                        e['mem_units'], e['saving_cents']))
    lines.append('</clusters>')
    w.lines('cluster_rollup.xml', lines)

    rows = ['pool_id,project_id,team,usage_units,allocated_cents']
    charge = []
    for pool in cand:
        k = assignment[pool['pool_id']]
        if k == 0:
            continue
        total = plan_savings[pool['pool_id']]
        usage = pool['proj_usage']
        tot_usage = sum(usage.values(), D0)
        parts = []
        for pid in sorted(usage):
            exact = Decimal(total) * usage[pid] / tot_usage
            floor = int(exact.to_integral_value(rounding='ROUND_FLOOR'))
            parts.append([pid, floor, exact - floor])
        left = total - sum(p[1] for p in parts)
        order = sorted(range(len(parts)),
                       key=lambda i: (-parts[i][2], parts[i][0]))
        for i in order[:left]:
            parts[i][1] += 1
        for pid, cents, _ in parts:
            team = plan.registry.get(pid, {}).get('team', '')
            charge.append((pool['pool_id'], pid, team, usage[pid], cents))
            rows.append('%s,%s,%s,%s,%d' % (pool['pool_id'], pid, team,
                                            dstr(usage[pid]), cents))
    w.lines('chargeback.csv', rows)

    team_roll = {}
    for _, pid, team, _, cents in charge:
        ent = team_roll.setdefault(team, {'projects': set(), 'allocated_cents': 0})
        ent['projects'].add(pid)
        ent['allocated_cents'] += cents
    w.doc('team_rollup.json', {t: {'projects': len(v['projects']),
                                   'allocated_cents': v['allocated_cents']}
                               for t, v in team_roll.items()})

    exact_total = sum((pool['curve'][assignment[pool['pool_id']]]['saving']
                       for pool in cand), D0)
    w.doc('plan_summary.json', {
        'plan_id': plan.plan_id,
        'ruleset_version': plan.sheet,
        'lookback_hours': plan.H,
        'out_of_window_queries': plan.out_of_window,
        'excluded_queries': len(plan.excluded),
        'candidate_pools': len(cand),
        'selected_pools': sum(1 for p in cand if assignment[p['pool_id']] > 0),
        'nodes_total': sum(assignment[p['pool_id']] for p in cand),
        'node_cap_total': plan.node_cap_total,
        'mem_units_total': sum(p['curve'][assignment[p['pool_id']]]['mem']
                               for p in cand),
        'mem_budget_units': plan.mem_budget_units,
        'total_saving_cents': int(q(exact_total, 0, plan.rounding)),
        'chargeback_total_cents': sum(c[4] for c in charge),
        'netted_units_total': dstr(plan.netted_total),
        'closure_rounds': len(plan.rounds),
    })

    pub_nodes = {}
    pub_saving = {}
    with open(os.path.join(plan.data, plan.profile['published_plan']),
              encoding='utf-8', newline='') as fh:
        for r in csv.DictReader(fh):
            pid = nid(r['pool_id'])
            pub_nodes[pid] = int(r['nodes'])
            pub_saving[pid] = pub_saving.get(pid, 0) + int(r['saving_cents'])
    corrected = {p['pool_id']: assignment[p['pool_id']] for p in cand}
    rows = ['pool_id,published_nodes,corrected_nodes,node_delta,'
            'published_saving_cents,corrected_saving_cents,status']
    for pid in sorted(set(pub_nodes) | set(corrected)):
        pn = pub_nodes.get(pid)
        cn = corrected.get(pid)
        if pn is None:
            status = 'NEW'
        elif cn is None:
            status = 'DROPPED'
        elif pn == cn:
            status = 'MATCH'
        else:
            status = 'CHANGED'
        rows.append(','.join([
            pid, '' if pn is None else str(pn), '' if cn is None else str(cn),
            str((cn or 0) - (pn or 0)),
            '' if pn is None else str(pub_saving[pid]),
            '' if cn is None else str(plan_savings[pid]), status]))
    w.lines('variance_vs_published.csv', rows)

    fam_pub = {}
    for pid, n in pub_nodes.items():
        key = pid.split('@')[0]
        fam_pub[key] = fam_pub.get(key, 0) + n
    fam_cor = {}
    for pid, n in corrected.items():
        key = pid.split('@')[0]
        fam_cor[key] = fam_cor.get(key, 0) + n
    lines = ['# Plan %s cache reconciliation' % plan.plan_id, '',
             '| family | published_nodes | corrected_nodes | delta_nodes |',
             '|---|---|---|---|']
    for family in sorted(set(fam_pub) | set(fam_cor)):
        p = fam_pub.get(family, 0)
        c = fam_cor.get(family, 0)
        lines.append('| %s | %d | %d | %d |' % (family, p, c, c - p))
    tp = sum(fam_pub.values())
    tc = sum(fam_cor.values())
    lines.append('| ALL | %d | %d | %d |' % (tp, tc, tc - tp))
    w.lines('reconciliation.md', lines)

    files = []
    for name in CONTRACT_FILES:
        blob = open(os.path.join(out_dir, name), 'rb').read()
        files.append({'name': name, 'bytes': len(blob),
                      'sha256': hashlib.sha256(blob).hexdigest()})
    w.doc('manifest.json', {'files': files})


def main():
    report(Plan(sys.argv[1]), sys.argv[2])


if __name__ == '__main__':
    main()
