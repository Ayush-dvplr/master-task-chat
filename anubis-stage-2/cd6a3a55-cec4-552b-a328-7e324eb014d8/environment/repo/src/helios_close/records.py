"""helios_close.records: part of the Q3 close program (see README.md)."""
from __future__ import annotations

from .formats import *  # noqa: F401,F403
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
            if x.rec_at >= CUT and register or x.st == 'draft':
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
                    except (ValueError, IndexError, KeyError, TypeError, AttributeError, ArithmeticError):
                        v[f] = None
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
            if k not in best or (x.v['decided'], rid) < best[k][0]:
                best[k] = ((x.v['decided'], rid), x.v['decision'])
        self.approved = {k for k, (_, d) in best.items() if d == 'approve'}
        rows = []
        for rid, revs in self.revs['errata_register.docx']['errata'].items():
            x = self.in_force(revs)
            if x is None or x.v['issued'] >= CUT:
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
        notices = self.records('yank_notices.mbox', 'notices')
        amap = {}
        for v, x, _ in self.records('name_aliases.tsv', 'aliases').values():
            if v['effective'] is None or v['effective'] >= CUT:
                continue
            amap[v['eco'], v['alias']] = v['target']
        for v, x, _ in self.records('name_aliases_legacy.tsv', 'aliases').values():
            if v['kind'] == 'rename' and v['effective'] is not None and (v['effective'] < LEGACY_RENAME_CUTOFF) or (v['effective'] is not None and v['effective'] < CUT):
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
