#!/usr/bin/env python3
"""Settle one card event from one directory of working papers.

The same program settles every event: no identifier, control value,
threshold, boundary, unit conversion, rung order, status list or key order
of an event sits inside it. Each is read from the directory --data names.
All derivation is exact rational arithmetic.
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import tomllib
import zipfile
import zlib
from collections import defaultdict
from fractions import Fraction
from xml.etree import ElementTree as ET

SSNS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
RELNS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
WPNS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

OPERATIVE = 'operative'


class PaperMissing(Exception):
    """A paper or a value the specifications require is not in the directory."""


class NegKey:
    """Sort wrapper inverting one key of a composite ordering."""

    __slots__ = ('value',)

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        return other.value < self.value

    def __eq__(self, other):
        return self.value == other.value


def rhe(value):
    """Round a rational half to even."""
    frac = Fraction(value)
    num, den = frac.numerator, frac.denominator
    if den == 1:
        return num
    quo, rem = divmod(num, den)
    twice = 2 * rem
    if twice > den:
        return quo + 1
    if twice < den:
        return quo
    return quo if quo % 2 == 0 else quo + 1


def ratio9(num, den):
    """A published ratio at exactly nine decimal places."""
    if den == 0:
        return '0.000000000'
    scaled = rhe(Fraction(num, den) * 10 ** 9)
    sign = '-' if scaled < 0 else ''
    mag = abs(scaled)
    return '%s%d.%09d' % (sign, mag // 10 ** 9, mag % 10 ** 9)


def col_letters(ref):
    out = ''
    for ch in ref:
        if not ch.isalpha():
            break
        out += ch
    return out


class Papers:
    """Reader over one directory of working papers."""

    def __init__(self, directory):
        self.dir = directory

    def path(self, name):
        full = os.path.join(self.dir, name)
        if not os.path.isfile(full):
            raise PaperMissing(name)
        return full

    def text(self, name):
        with open(self.path(name), encoding='utf-8') as handle:
            return handle.read()

    def delimited(self, name, delim):
        with open(self.path(name), newline='', encoding='utf-8') as handle:
            return list(csv.DictReader(handle, delimiter=delim))

    def ndjson(self, name):
        out = []
        for line in self.text(name).splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def json(self, name):
        return json.loads(self.text(name))

    def toml(self, name):
        with open(self.path(name), 'rb') as handle:
            return tomllib.load(handle)

    def yaml_scalars(self, name):
        out = {}
        for raw in self.text(name).splitlines():
            line = raw.split('#')[0].rstrip()
            if not line.strip():
                continue
            found = re.match(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(\S.*)$', line)
            if found:
                out.setdefault(found.group(1), found.group(2).strip())
        return out

    def conf(self, name):
        sections = []
        current = None
        for raw in self.text(name).splitlines():
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('[') and line.endswith(']'):
                current = (line[1:-1], {})
                sections.append(current)
            elif '=' in line and current is not None:
                key, val = line.split('=', 1)
                current[1][key.strip()] = val.strip()
        return sections

    def xml(self, name):
        return ET.parse(self.path(name)).getroot()

    def sheets(self, name):
        """Every sheet of a spreadsheet paper as rows of column letter to text."""
        with zipfile.ZipFile(self.path(name)) as archive:
            shared = []
            if 'xl/sharedStrings.xml' in archive.namelist():
                table = ET.fromstring(archive.read('xl/sharedStrings.xml'))
                for item in table.iter(SSNS + 'si'):
                    shared.append(''.join(t.text or '' for t in item.iter(SSNS + 't')))
            rels = {}
            for rel in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels')):
                rels[rel.get('Id')] = rel.get('Target')
            book = ET.fromstring(archive.read('xl/workbook.xml'))
            out = []
            for sheet in book.iter(SSNS + 'sheet'):
                target = rels[sheet.get(RELNS + 'id')]
                inner = target[1:] if target.startswith('/') else 'xl/' + target
                rows = []
                for row in ET.fromstring(archive.read(inner)).iter(SSNS + 'row'):
                    cells = {}
                    for cell in row.iter(SSNS + 'c'):
                        kind = cell.get('t')
                        vnode = cell.find(SSNS + 'v')
                        inline = cell.find(SSNS + 'is')
                        if kind == 's' and vnode is not None and vnode.text is not None:
                            val = shared[int(vnode.text)]
                        elif kind == 'inlineStr' and inline is not None:
                            val = ''.join(t.text or '' for t in inline.iter(SSNS + 't'))
                        elif vnode is not None:
                            val = vnode.text or ''
                        else:
                            val = ''
                        cells[col_letters(cell.get('r') or '')] = val
                    rows.append(cells)
                out.append((sheet.get('name'), rows))
            return out

    def docx_tables(self, name):
        """Every table of a word processing paper as rows keyed on its header."""
        with zipfile.ZipFile(self.path(name)) as archive:
            document = ET.fromstring(archive.read('word/document.xml'))
        tables = []
        for table in document.iter(WPNS + 'tbl'):
            rows = []
            for trow in table.findall(WPNS + 'tr'):
                cells = []
                for tcell in trow.findall(WPNS + 'tc'):
                    texts = []
                    for para in tcell.findall(WPNS + 'p'):
                        texts.append(''.join(t.text or '' for t in para.iter(WPNS + 't')))
                    cells.append(' '.join(texts).strip())
                rows.append(cells)
            if len(rows) > 1:
                head = rows[0]
                tables.append([dict(zip(head, row)) for row in rows[1:]])
        return tables

    def pdf_lines(self, name):
        """The printed lines of a portable document paper."""
        with open(self.path(name), 'rb') as handle:
            data = handle.read()
        pattern = rb'\((?:\\.|[^()\\])*\)\s*Tj|\[(?:[^\[\]]|\\.)*\]\s*TJ|T\*|Td|TD|ET'
        lines = []
        for match in re.finditer(rb'stream\r?\n', data):
            start = match.end()
            end = data.find(b'endstream', start)
            if end < 0:
                continue
            raw_body = data[start:end]
            try:
                body = zlib.decompress(raw_body)
            except zlib.error:
                body = raw_body
            parts = []
            for token in re.finditer(pattern, body):
                raw = token.group(0)
                if raw in (b'T*', b'Td', b'TD', b'ET'):
                    parts.append('\n')
                    continue
                text = ''
                for piece in re.findall(rb'\((?:\\.|[^()\\])*\)', raw):
                    inner = piece[1:-1]
                    inner = inner.replace(b'\\(', b'(').replace(b'\\)', b')')
                    inner = inner.replace(b'\\\\', b'\\')
                    text += inner.decode('latin-1')
                parts.append(text)
            lines.extend(''.join(parts).split('\n'))
        return lines


def delim_doc(header, rows, sep):
    out = [sep.join(header)]
    for row in rows:
        out.append(sep.join('' if x is None else str(x) for x in row))
    return '\n'.join(out) + '\n'


def json_doc(obj):
    return json.dumps(obj, indent=1, ensure_ascii=False) + '\n'


def jsonl_doc(objs):
    if not objs:
        return '\n'
    out = [json.dumps(o, separators=(',', ':'), ensure_ascii=False) for o in objs]
    return '\n'.join(out) + '\n'


class Rules:
    """Every control value, threshold and key order, read from the papers."""

    def __init__(self, papers):
        self.papers = papers
        topo = papers.xml('division_topology.xml')
        ident = topo.find('identity')
        if ident is None:
            raise PaperMissing('division_topology.xml identity')
        self.event_id = (ident.findtext('event_id') or '').strip()
        self.ref = (ident.findtext('event_reference') or '').strip()
        self.round_count = int((ident.findtext('round_count') or '').strip())
        self.rounds = list(range(1, self.round_count + 1))
        self.div_in_force = []
        for div in topo.find('divisions'):
            if div.get('in_force') == 'yes':
                self.div_in_force.append(div.get('id'))

        self.absent = papers.toml('settlement_form_rules.toml')['markers']['absent']
        self.revision = papers.toml('revision_precedence.toml')
        self.ticks_per_round = int(
            papers.yaml_scalars('boundary_conventions.yaml')['ticks_per_round'])

        units = papers.toml('unit_register_dictionary.toml')['unit']
        self.units = {}
        for name, body in units.items():
            self.units[name] = (int(body['numerator']), int(body['denominator']))

        ladder = papers.toml('pairing_precedence_policy.toml')
        self.levels = int(ladder['admission']['levels'])
        tol = ladder['tolerance']
        self.tol_bye = int(tol['bye_holder'])
        self.tol_unpaired = int(tol['unpaired'])
        self.tol_ineligible = int(tol['ineligible'])

        self.penalty_classes = list(
            papers.toml('penalty_precedence_policy.toml')['order']['sequence'])

        self.modifiers = {}
        for code in papers.json('round_modifier_rules.json')['codes']:
            self.modifiers[code['code']] = (int(code['numerator']), int(code['denominator']))

        tiebreak = papers.json('tiebreak_rules.json')
        self.rate_scale = int(tiebreak['rate_scale'])
        self.zero_strength = int(tiebreak['zero_strength_value'])
        self.direction = {}
        for item in tiebreak['ordering']:
            self.direction[item['key']] = item['direction']

        self.share_table = {}
        for row in papers.json('prize_rules.json')['share_table']:
            self.share_table[int(row['rank'])] = int(row['basis_points'])

        self._clauses(papers)
        self._directive(papers)
        self._live_sheet(papers)
        self._reporting(papers)
        self._void_levels(papers)
        self._evidence_order(papers)

        self.rungs = []
        index = 1
        while ('relaxation_rung_%d' % index) in self.clauses:
            self.rungs.append(self.clauses['relaxation_rung_%d' % index])
            index += 1

        applied = []
        index = 1
        while ('penalty_order_%d' % index) in self.clauses:
            applied.append(self.clauses['penalty_order_%d' % index])
            index += 1
        if applied != self.penalty_classes:
            raise PaperMissing('penalty order disagrees between papers')

        self.bye_points = int(self.clauses['bye_points'])
        self.bye_game_delta = int(self.clauses['bye_game_delta'])
        self.void_points = int(self.clauses['void_points'])
        self.unpaired_points = int(self.clauses['unpaired_points'])
        self.no_record_points = int(self.clauses['no_record_points'])
        self.round_floor = int(self.clauses['round_points_floor'])
        self.disqualify_units = int(self.clauses['prize_disqualify_units'])
        self.tie_group_depth = int(self.clauses['tie_group_depth'])

        self.score_band = int(self.capacity_value('score_band'))
        self.max_byes = int(self.capacity_value('max_byes'))
        self.pool_cents = int(self.capacity_value('pool_cents', 'cents'))
        self.strength_debit = int(self.capacity_value('strength_debit'))

        self.tiebreak_keys = self.families['tiebreak']
        self.pairing_keys = self.families['pairing_order']
        self.bye_keys = self.families['bye_order']
        self.void_order = self.families['void_reason']

    def _clauses(self, papers):
        self.clauses = {}
        pattern = re.compile(r'^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$')
        for line in papers.pdf_lines('appeals_procedure_memo.pdf'):
            found = pattern.match(line.strip())
            if not found:
                continue
            _tag, status, reference, key, value = found.groups()
            if status == OPERATIVE and reference == self.ref:
                self.clauses.setdefault(key, value)

    def _directive(self, papers):
        families = defaultdict(dict)
        self.div_rank = {}
        for table in papers.docx_tables('standings_precedence_directive.docx'):
            for row in table:
                if row.get('status') != OPERATIVE or row.get('event_reference') != self.ref:
                    continue
                if row.get('key_family'):
                    families[row['key_family']][int(row['key_position'])] = row['key_name']
                elif row.get('division_id'):
                    self.div_rank.setdefault(row['division_id'], int(row['division_rank']))
        self.families = {}
        for name, body in families.items():
            self.families[name] = [body[pos] for pos in sorted(body)]

    def _live_sheet(self, papers):
        for name, rows in papers.sheets('panel_capacity_workbook.xlsx'):
            key = None
            for row in rows:
                if row.get('A') == 'sheet_reference':
                    key = row.get('B')
                    break
            if key != self.ref:
                continue
            self.live_sheet_name = name
            self.live_sheet_key = key
            params = defaultdict(list)
            for row in rows:
                if row.get('D') != OPERATIVE:
                    continue
                label = row.get('A')
                value = row.get('B')
                if not label or value in (None, ''):
                    continue
                params[label].append((value, row.get('C')))
            self.capacity = params
            return
        raise PaperMissing('a live sheet of panel_capacity_workbook.xlsx')

    def capacity_value(self, name, unit=None):
        rows = self.capacity.get(name)
        if not rows:
            raise PaperMissing('capacity parameter %s' % name)
        if unit is not None:
            for value, got in rows:
                if got == unit:
                    return value
            raise PaperMissing('capacity parameter %s in %s' % (name, unit))
        return rows[0][0]

    def _reporting(self, papers):
        self.report_order = {}
        section = self.revision.get('reporting_roster', {})
        applicable = set(section.get('applicable_status', []))
        excluded = set(section.get('excluded_status', []))
        for header, body in papers.conf('reporting_division_roster.conf'):
            if not header.startswith('division:'):
                continue
            if body.get('event_reference') != self.ref:
                continue
            status = body.get('record_status')
            if status in excluded:
                continue
            if applicable and status not in applicable:
                continue
            self.report_order.setdefault(header.split(':', 1)[1], int(body['report_order']))

    def _void_levels(self, papers):
        self.void_levels = {}
        for line in papers.text('spec_stage_p08_admissibility_voids.md').splitlines():
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if len(cells) >= 3 and cells[0].startswith('`') and cells[1].isdigit():
                self.void_levels[cells[0].strip('`')] = int(cells[1])

    def _evidence_order(self, papers):
        rows = []
        for row in papers.delimited('source_priority_register.csv', ','):
            if row['event_reference'] == self.ref and row['record_status'] == OPERATIVE:
                rows.append((int(row['priority_rank']), row['source_code']))
        self.evidence_order = [code for _rank, code in sorted(rows)]

    def applicable(self, section, status):
        body = self.revision.get(section, {})
        if status in set(body.get('excluded_status', [])):
            return False
        allowed = body.get('applicable_status')
        return status in set(allowed) if allowed else True

    def convert(self, value, unit):
        if unit not in self.units:
            raise PaperMissing('unit register entry %s' % unit)
        num, den = self.units[unit]
        return rhe(Fraction(int(value) * num, den))


class Settlement:
    """The fourteen stages worked in order over one directory of papers."""

    def __init__(self, papers):
        self.papers = papers
        self.rules = Rules(papers)
        self.stage_p01()
        self.stage_p02()
        self.stage_p03()
        self.stage_p04()
        self.round_loop()
        self.stage_p12()
        self.stage_p13()
        self.stage_p14()

    # ---------------- P01 entry normalisation ----------------

    def stage_p01(self):
        rules = self.rules
        ref = rules.ref
        alias = {}
        for row in self.papers.delimited('entry_alias_register.csv', ','):
            if row['event_reference'] == ref:
                alias[row['alias_id']] = row['canonical_id']
        self.alias = alias
        self._resolved = {}

        self.admission = {}
        for row in self.papers.delimited('division_admission_matrix.csv', ','):
            if row['event_reference'] == ref:
                key = (row['division_id'], int(row['round_no']), row['parameter'])
                self.admission.setdefault(key, row['value'])

        self.config = {}
        for row in self.papers.delimited('round_configuration_register.csv', ','):
            if row['event_reference'] == ref:
                key = (int(row['round_no']), row['division_id'], row['parameter'])
                self.config.setdefault(key, row['value'])

        roster = []
        for row in self.papers.delimited('entry_roster_register.csv', ','):
            if row['event_reference'] != ref:
                continue
            if not rules.applicable('entry_roster', row['entry_status']):
                continue
            roster.append(row)

        clusters = defaultdict(list)
        for row in roster:
            clusters[self.resolve(row['entry_id'])].append(row)

        returns = defaultdict(list)
        for row in self.papers.delimited('rating_return_sheet.psv', '|'):
            if row['event_reference'] != ref:
                continue
            if not rules.applicable('rating_return', row['return_status']):
                continue
            returns[self.resolve(row['player_ref'])].append(row)

        self.entrants = {}
        for pid, rows in clusters.items():
            governing = max(rows, key=lambda r: (int(r['revision_seq']), int(r['entry_seq'])))
            division = governing['division_id']
            if division not in rules.div_in_force:
                continue
            folded = sorted({r['entry_id'] for r in rows} - {pid})
            filed = returns.get(pid)
            if filed:
                best = max(filed, key=lambda r: int(r['return_seq']))
                quoted, unit, source = best['quoted_value'], best['quoted_unit'], 'return'
            else:
                quoted, unit, source = governing['quoted_rating'], governing['rating_unit'], 'roster'
            if quoted == rules.absent:
                rating = int(self.admitted(division, 1, 'default_rating_mr'))
                source = 'default'
            else:
                rating = rules.convert(quoted, unit)
            self.entrants[pid] = {
                'player_id': pid,
                'division_id': division,
                'rating_mr': rating,
                'rating_source': source,
                'entry_seq': int(governing['entry_seq']),
                'folded_ids': folded,
                'membership_ref': governing['membership_ref'],
            }

        order = sorted(self.entrants.values(), key=lambda e: (-e['rating_mr'], e['player_id']))
        for seat, entry in enumerate(order, start=1):
            entry['seed_number'] = seat
        self.players = sorted(self.entrants)

    def resolve(self, identifier):
        """The player identifier of an entry identifier under the alias closure."""
        if identifier in self._resolved:
            return self._resolved[identifier]
        seen = []
        current = identifier
        while current in self.alias:
            if current in seen:
                current = min(seen[seen.index(current):])
                break
            seen.append(current)
            current = self.alias[current]
        self._resolved[identifier] = current
        return current

    def admitted(self, division, round_no, parameter):
        key = (division, round_no, parameter)
        if key not in self.admission:
            raise PaperMissing('admission parameter %s' % str(key))
        return self.admission[key]

    def configured(self, round_no, division, parameter):
        key = (round_no, division, parameter)
        if key not in self.config:
            raise PaperMissing('round configuration %s' % str(key))
        return self.config[key]

    # ---------------- P02 participation state ----------------

    def stage_p02(self):
        rules = self.rules
        ref = rules.ref
        journal = defaultdict(list)
        for row in self.papers.delimited('status_change_journal.tsv', '\t'):
            if row['event_reference'] != ref:
                continue
            pid = self.resolve(row['player_ref'])
            if pid not in self.entrants:
                continue
            tick = int(row['tick'])
            journal[pid].append({
                'round': tick // rules.ticks_per_round + 1,
                'code': row['change_code'],
                'seq': int(row['note_seq']),
            })
        for rows in journal.values():
            rows.sort(key=lambda r: (r['round'], r['seq']))

        standing = defaultdict(list)
        for row in self.papers.delimited('membership_standing_register.csv', ','):
            if row['event_reference'] != ref:
                continue
            if not rules.applicable('membership_standing', row['standing_code']):
                continue
            standing[row['membership_ref']].append(row)

        self.notices = []
        for row in self.papers.delimited('penalty_notice_register.psv', '|'):
            if row['event_reference'] != ref:
                continue
            if not rules.applicable('penalty_notice', row['notice_status']):
                continue
            pid = self.resolve(row['player_ref'])
            if pid not in self.entrants:
                continue
            self.notices.append({
                'player_id': pid,
                'class': row['penalty_class'],
                'magnitude': int(row['magnitude']),
                'round': int(row['effective_round']),
                'seq': int(row['notice_seq']),
            })

        expulsion = defaultdict(list)
        for notice in self.notices:
            if notice['class'] == 'expulsion':
                expulsion[notice['player_id']].append(notice)

        self.state = {}
        for pid in self.players:
            member = self.entrants[pid]['membership_ref']
            for round_no in rules.rounds:
                state = 'seated'
                code, seq = 'none', 0
                for row in journal.get(pid, ()):
                    if row['round'] > round_no:
                        break
                    if row['code'] == 'absence':
                        if row['round'] == round_no:
                            state, code, seq = 'absent', row['code'], row['seq']
                        continue
                    if row['code'] == 'drop':
                        state = 'dropped'
                    else:
                        state = 'seated'
                    code, seq = row['code'], row['seq']
                reaching = [r for r in standing.get(member, ())
                            if int(r['effective_round']) <= round_no]
                if reaching:
                    best = max(reaching, key=lambda r: (int(r['effective_round']),
                                                        int(r['notice_seq'])))
                    if best['standing_code'] == 'lapsed':
                        state = 'barred'
                        code, seq = 'lapsed', int(best['notice_seq'])
                bars = [n for n in expulsion.get(pid, ()) if n['round'] <= round_no]
                if bars:
                    first = min(bars, key=lambda n: (n['round'], n['seq']))
                    state = 'barred'
                    code, seq = 'expulsion', first['seq']
                self.state[(pid, round_no)] = (state, code, seq)

    # ---------------- P03 candidate board assembly ----------------

    def stage_p03(self):
        rules = self.rules
        groups = defaultdict(list)
        for row in self.papers.delimited('recorded_pairing_table.csv', ','):
            if row['event_reference'] != rules.ref:
                continue
            if not rules.applicable('recorded_pairing', row['pairing_status']):
                continue
            groups[(int(row['round_no']), int(row['table_no']))].append(row)

        self.candidates = {}
        for key, rows in groups.items():
            best = max(rows, key=lambda r: (int(r['sheet_revision']), int(r['source_seq'])))
            side_a = self.resolve(best['player_a'])
            side_b = self.resolve(best['player_b'])
            if side_a == side_b:
                continue
            if side_a not in self.entrants or side_b not in self.entrants:
                continue
            self.candidates[key] = {
                'round_no': key[0],
                'table_no': key[1],
                'player_a': side_a,
                'player_b': side_b,
                'sheet_revision': int(best['sheet_revision']),
                'source_seq': int(best['source_seq']),
            }
        self.candidate_keys = sorted(self.candidates)
        self.boards_of_round = defaultdict(list)
        for key in self.candidate_keys:
            self.boards_of_round[key[0]].append(key)

    # ---------------- P04 game evidence resolution ----------------

    def stage_p04(self):
        rules = self.rules
        sheets = defaultdict(list)
        for record in self.papers.ndjson('match_result_sheets.ndjson'):
            if record.get('event_reference') != rules.ref:
                continue
            if not rules.applicable('result_sheet', record['sheet_status']):
                continue
            sheets[(int(record['round_no']), int(record['table_no']))].append(record)
        governing = {}
        for key, rows in sheets.items():
            governing[key] = max(rows, key=lambda r: int(r['sheet_seq']))

        games = defaultdict(list)
        for row in self.papers.delimited('game_records.csv', ','):
            if row['event_reference'] == rules.ref:
                games[(int(row['round_no']), int(row['table_no']))].append(row)

        self.results = {}
        for key in self.candidate_keys:
            sheet = governing.get(key)
            rows = games.get(key, ())
            games_a = sum(1 for r in rows if r['outcome'] == 'won_a' and r['completed'] == 'yes')
            games_b = sum(1 for r in rows if r['outcome'] == 'won_b' and r['completed'] == 'yes')
            conceded_a = any(r['outcome'] == 'conceded_a' for r in rows)
            conceded_b = any(r['outcome'] == 'conceded_b' for r in rows)
            code, basis = None, None
            for source in rules.evidence_order:
                if source == 'sheet_adjudication':
                    if sheet and sheet['adjudicated_result'] != rules.absent:
                        code, basis = sheet['adjudicated_result'], source
                elif source == 'game_concession':
                    if conceded_a and conceded_b:
                        code, basis = 'double_loss', source
                    elif conceded_a:
                        code, basis = 'win_b', source
                    elif conceded_b:
                        code, basis = 'win_a', source
                elif source == 'completed_game':
                    if games_a or games_b:
                        if games_a > games_b:
                            code = 'win_a'
                        elif games_b > games_a:
                            code = 'win_b'
                        else:
                            code = 'draw'
                        basis = source
                elif source == 'declared_count':
                    if sheet and sheet['declared_games_a'] != rules.absent \
                            and sheet['declared_games_b'] != rules.absent:
                        left = int(sheet['declared_games_a'])
                        right = int(sheet['declared_games_b'])
                        if left > right:
                            code = 'win_a'
                        elif right > left:
                            code = 'win_b'
                        else:
                            code = 'draw'
                        basis = source
                elif source == 'no_evidence':
                    code, basis = 'double_loss', source
                if basis:
                    break
            if not basis:
                raise PaperMissing('an evidence level for board %s' % str(key))
            board = dict(self.candidates[key])
            board.update({
                'result_code': code,
                'basis': basis,
                'games_a': games_a,
                'games_b': games_b,
                'delta_a': games_a - games_b,
            })
            self.results[key] = board

    # ---------------- P05 to P11, one round at a time ----------------

    def round_loop(self):
        rules = self.rules
        self.running_points = dict.fromkeys(self.players, 0)
        self.running_delta = dict.fromkeys(self.players, 0)
        self.byes_taken = dict.fromkeys(self.players, 0)
        self.eligibility_rows = []
        self.bye_rows = []
        self.pairing_rows = []
        self.unpaired_rows = []
        self.void_rows = []
        self.score_rows = []
        self.penalty_rows = []
        self.history_rows = []
        self.round_report = []
        self.scores = {}
        self.met = defaultdict(set)
        self.meetings = defaultdict(list)
        self.counted = defaultdict(set)
        self.eligible_in = {}
        self.level_of = {}

        self.notice_index = defaultdict(lambda: defaultdict(list))
        for notice in self.notices:
            key = (notice['player_id'], notice['round'])
            self.notice_index[key][notice['class']].append(notice)

        for round_no in rules.rounds:
            self.work_round(round_no)

    def sort_key(self, keys, player, byes_taken=None):
        """The composite ordering key of a player under one key family."""
        entry = self.entrants[player]
        out = []
        for name in keys:
            if name == 'running_points_descending':
                out.append(NegKey(self.running_points[player]))
            elif name == 'running_points_ascending':
                out.append(self.running_points[player])
            elif name == 'running_differential_descending':
                out.append(NegKey(self.running_delta[player]))
            elif name == 'running_differential_ascending':
                out.append(self.running_delta[player])
            elif name == 'division_rank_ascending':
                out.append(self.rules.div_rank[entry['division_id']])
            elif name == 'seat_order_ascending':
                out.append(entry['seed_number'])
            elif name == 'seat_order_descending':
                out.append(NegKey(entry['seed_number']))
            elif name == 'byes_received_ascending':
                out.append(self.byes_taken[player])
            elif name == 'player_id_ascending':
                out.append(player)
            else:
                raise PaperMissing('ordering key %s' % name)
        return tuple(out)

    def admissible(self, first, second, level, round_no):
        rules = self.rules
        relaxed = set(rules.rungs[:level])
        div_a = self.entrants[first]['division_id']
        div_b = self.entrants[second]['division_id']
        if 'division' in relaxed:
            if div_a != div_b:
                for div in (div_a, div_b):
                    if self.admitted(div, round_no, 'cross_admitted') != 'yes':
                        return False
        elif div_a != div_b:
            return False
        if 'score_band' not in relaxed:
            band = rules.score_band + int(self.admitted(div_a, round_no, 'band_widening'))
            if abs(self.running_points[first] - self.running_points[second]) > band:
                return False
        if 'repeat_opponent' not in relaxed:
            if second in self.met[first]:
                return False
        return True

    def work_round(self, round_no):
        rules = self.rules

        # P05 round eligibility
        eligible = []
        for pid in self.players:
            state = self.state[(pid, round_no)][0]
            seated = state == 'seated'
            self.eligibility_rows.append([
                round_no, pid, self.entrants[pid]['division_id'],
                'yes' if seated else 'no', state,
                self.running_points[pid], self.running_delta[pid]])
            if seated:
                eligible.append(pid)
        eligible_set = set(eligible)
        self.eligible_in[round_no] = eligible_set

        # P06 bye assignment
        byes = {}
        for division in sorted(rules.div_in_force):
            seated = [p for p in eligible if self.entrants[p]['division_id'] == division]
            if len(seated) % 2 == 0:
                continue
            candidates = [p for p in seated if self.byes_taken[p] < rules.max_byes]
            basis = 'normal'
            if not candidates:
                if self.admitted(division, round_no, 'bye_override') != 'yes':
                    continue
                candidates = list(seated)
                basis = 'cap_override'
            chosen = min(candidates, key=lambda p: self.sort_key(rules.bye_keys, p))
            byes[division] = chosen
            self.bye_rows.append([round_no, division, chosen,
                                  self.byes_taken[chosen], basis])
        bye_players = set(byes.values())

        # P07 authoritative pairing
        pool = [p for p in eligible if p not in bye_players]
        pool.sort(key=lambda p: self.sort_key(rules.pairing_keys, p))
        taken = set()
        unpaired = []
        board_no = 0
        formed = []
        for index, player in enumerate(pool):
            if player in taken:
                continue
            partner = None
            found = None
            for level in range(rules.levels):
                for other in pool[index + 1:]:
                    if other in taken:
                        continue
                    if self.admissible(player, other, level, round_no):
                        partner, found = other, level
                        break
                if partner is not None:
                    break
            if partner is None:
                unpaired.append(player)
                self.unpaired_rows.append([
                    round_no, self.entrants[player]['division_id'], player,
                    self.running_points[player], 'no_admissible_partner'])
                continue
            taken.add(player)
            taken.add(partner)
            board_no += 1
            self.level_of[(round_no, player)] = found
            self.level_of[(round_no, partner)] = found
            formed.append((board_no, player, partner, found))
            self.pairing_rows.append([
                round_no, board_no, player, partner,
                self.entrants[player]['division_id'],
                self.entrants[partner]['division_id'], found,
                self.running_points[player], self.running_points[partner]])
        unpaired_set = set(unpaired)

        # P08 admissibility and voids
        tolerance = {}
        for pid in self.players:
            if pid not in eligible_set:
                tolerance[pid] = rules.tol_ineligible
            elif pid in bye_players:
                tolerance[pid] = rules.tol_bye
            elif pid in unpaired_set:
                tolerance[pid] = rules.tol_unpaired
            else:
                tolerance[pid] = self.level_of[(round_no, pid)]

        voided = {}
        for key in self.boards_of_round[round_no]:
            board = self.results[key]
            side_a, side_b = board['player_a'], board['player_b']
            reach = min(tolerance[side_a], tolerance[side_b])
            div_a = self.entrants[side_a]['division_id']
            band = rules.score_band + int(self.admitted(div_a, round_no, 'band_widening'))
            checks = {
                'ineligible_player': side_a not in eligible_set or side_b not in eligible_set,
                'holds_bye': side_a in bye_players or side_b in bye_players,
                'cross_division': div_a != self.entrants[side_b]['division_id'],
                'repeat_opponent': side_b in self.met[side_a],
                'score_band': abs(self.running_points[side_a]
                                  - self.running_points[side_b]) > band,
            }
            for name in rules.void_order:
                if checks.get(name) and rules.void_levels[name] > reach:
                    voided[key] = (name, rules.void_levels[name], reach)
                    break

        # P09 round scoring, with P10 collecting the applied notices
        board_of = {}
        for key in self.boards_of_round[round_no]:
            board = self.results[key]
            for side in ('player_a', 'player_b'):
                pid = board[side]
                if pid in eligible_set:
                    board_of.setdefault(pid, key)

        for pid in eligible:
            division = self.entrants[pid]['division_id']
            win = int(self.configured(round_no, division, 'win_points'))
            draw = int(self.configured(round_no, division, 'draw_points'))
            loss = int(self.configured(round_no, division, 'loss_points'))
            code = self.configured(round_no, division, 'modifier_code')

            if byes.get(division) == pid:
                basis, base, delta = 'bye', rules.bye_points, rules.bye_game_delta
            elif pid in board_of:
                key = board_of[pid]
                board = self.results[key]
                if key in voided:
                    basis, base, delta = 'void', rules.void_points, 0
                else:
                    basis = 'match'
                    on_a = board['player_a'] == pid
                    result = board['result_code']
                    if result == 'win_a':
                        base = win if on_a else loss
                    elif result == 'win_b':
                        base = loss if on_a else win
                    elif result == 'draw':
                        base = draw
                    else:
                        base = loss
                    delta = board['delta_a'] if on_a else -board['delta_a']
            elif pid in unpaired_set:
                basis, base, delta = 'unpaired', rules.unpaired_points, 0
            else:
                basis, base, delta = 'no_record', rules.no_record_points, 0

            applied = self.notice_index.get((pid, round_no), {})
            raw_delta = delta

            game = applied.get('game')
            if game:
                units = sum(n['magnitude'] for n in game)
                delta = raw_delta - units
                self.penalty_rows.append([
                    round_no, pid, 'game', units, min(n['seq'] for n in game),
                    raw_delta, delta, 0])

            match = applied.get('match')
            if match:
                units = sum(n['magnitude'] for n in match)
                self.penalty_rows.append([
                    round_no, pid, 'match', units, min(n['seq'] for n in match),
                    base, loss, 0])
                base = loss

            num, den = rules.modifiers[code]
            modified = rhe(Fraction(base * num, den))

            points = modified
            spell = applied.get('round')
            if spell:
                units = sum(n['magnitude'] for n in spell)
                points = modified - units
                shortfall = units - modified if units > modified else 0
            else:
                units, shortfall = 0, 0
            if points < rules.round_floor:
                points = rules.round_floor
            if spell:
                self.penalty_rows.append([
                    round_no, pid, 'round', units, min(n['seq'] for n in spell),
                    modified, points, shortfall])

            self.scores[(round_no, pid)] = {
                'basis': basis,
                'base_points': base,
                'modifier_code': code,
                'modified_points': modified,
                'round_points': points,
                'game_delta': delta,
                'raw_delta': raw_delta,
            }
            self.score_rows.append([
                round_no, pid, division, basis, base, code, modified, points, delta])

        for key in sorted(voided):
            reason, level, reach = voided[key]
            board = self.results[key]
            marks = []
            for side in ('player_a', 'player_b'):
                row = self.scores.get((round_no, board[side]))
                marks.append(row['base_points'] if row else rules.absent)
            self.void_rows.append([
                round_no, key[1], board['player_a'], board['player_b'],
                reason, level, reach, marks[0], marks[1]])

        # P11 opponent history
        repeat_boards = 0
        fresh = []
        for key in self.boards_of_round[round_no]:
            board = self.results[key]
            side_a, side_b = board['player_a'], board['player_b']
            if side_a not in eligible_set or side_b not in eligible_set:
                continue
            counts = 'no' if key in voided else 'yes'
            self.history_rows.append([round_no, side_a, side_b, counts, 'board'])
            self.history_rows.append([round_no, side_b, side_a, counts, 'board'])
            fresh.append((side_a, side_b, counts))
        for _no, side_a, side_b, _level in formed:
            if side_b in self.met[side_a]:
                repeat_boards += 1

        levels = {}
        for index in range(rules.levels):
            levels['level_%d' % index] = sum(1 for f in formed if f[3] == index)
        cross = 0
        for _no, side_a, side_b, _level in formed:
            if self.entrants[side_a]['division_id'] != self.entrants[side_b]['division_id']:
                cross += 1
        self.round_report.append({
            'round_no': round_no,
            'boards': len(formed),
            'byes': len(byes),
            'unpaired': len(unpaired),
            'level_counts': levels,
            'cross_division_boards': cross,
            'repeat_boards': repeat_boards,
            'voided_boards': len(voided),
        })

        for side_a, side_b, counts in fresh:
            self.met[side_a].add(side_b)
            self.met[side_b].add(side_a)
            self.meetings[(side_a, side_b)].append(round_no)
            self.meetings[(side_b, side_a)].append(round_no)
            if counts == 'yes':
                self.counted[side_a].add(side_b)
                self.counted[side_b].add(side_a)

        for pid in eligible:
            row = self.scores[(round_no, pid)]
            self.running_points[pid] += row['round_points']
            self.running_delta[pid] += row['game_delta']
        for pid in bye_players:
            self.byes_taken[pid] += 1

    # ---------------- P12 opponent strength ----------------

    def stage_p12(self):
        rules = self.rules
        self.rounds_counted = {}
        self.points_sum = {}
        self.raw_delta = {}
        for pid in self.players:
            rows = [self.scores[(r, pid)] for r in rules.rounds if (r, pid) in self.scores]
            self.rounds_counted[pid] = len(rows)
            self.points_sum[pid] = sum(r['round_points'] for r in rows)
            self.raw_delta[pid] = sum(r['raw_delta'] for r in rows)

        self.penalty_units = {}
        self.game_units = {}
        for pid in self.players:
            tournament = 0
            game = 0
            for notice in self.notices:
                if notice['player_id'] != pid:
                    continue
                if notice['class'] == 'tournament':
                    tournament += notice['magnitude']
                elif notice['class'] == 'game':
                    if pid in self.eligible_in.get(notice['round'], ()):
                        game += notice['magnitude']
            self.penalty_units[pid] = tournament
            self.game_units[pid] = game

        self.event_points = {}
        for pid in self.players:
            total = self.points_sum[pid] - self.penalty_units[pid]
            self.event_points[pid] = total if total > 0 else 0
            if self.penalty_units[pid]:
                before = self.points_sum[pid]
                after = self.event_points[pid]
                units = self.penalty_units[pid]
                shortfall = units - before if units > before else 0
                seqs = [n['seq'] for n in self.notices
                        if n['player_id'] == pid and n['class'] == 'tournament']
                self.penalty_rows.append([
                    0, pid, 'tournament', units, min(seqs), before, after, shortfall])

        self.adjusted_delta = {}
        for pid in self.players:
            self.adjusted_delta[pid] = self.raw_delta[pid] - self.game_units[pid]

        self.rate = {}
        for pid in self.players:
            counted = self.rounds_counted[pid] or 1
            self.rate[pid] = rhe(Fraction(self.event_points[pid] * rules.rate_scale, counted))

        self.strength = {}
        self.rate_sum = {}
        self.opponent_count = {}
        self.adjusted_strength = {}
        for pid in self.players:
            population = sorted(self.counted[pid])
            self.opponent_count[pid] = len(population)
            if population:
                total = sum(self.rate[o] for o in population)
                self.rate_sum[pid] = total
                self.strength[pid] = rhe(Fraction(total, len(population)))
            else:
                self.rate_sum[pid] = 0
                self.strength[pid] = rules.zero_strength
            debited = self.strength[pid] - rules.strength_debit * self.penalty_units[pid]
            self.adjusted_strength[pid] = debited if debited > 0 else 0

    # ---------------- P13 standings and tiebreaks ----------------

    def ordering_values(self, pid):
        return {
            'event_points': self.event_points[pid],
            'adjusted_game_differential': self.adjusted_delta[pid],
            'opponent_strength': self.strength[pid],
            'penalty_adjusted_strength': self.adjusted_strength[pid],
            'player_id': pid,
        }

    def stage_p13(self):
        rules = self.rules

        def key_of(pid):
            values = self.ordering_values(pid)
            out = []
            for name in rules.tiebreak_keys:
                value = values[name]
                if rules.direction.get(name) == 'descending':
                    out.append(NegKey(value))
                else:
                    out.append(value)
            return tuple(out)

        self.ranking = sorted(self.players, key=key_of)
        self.rank_of = {pid: index for index, pid in enumerate(self.ranking, start=1)}
        self.prize_eligible = {}
        for pid in self.players:
            reached = self.penalty_units[pid] >= rules.disqualify_units
            self.prize_eligible[pid] = 'no' if reached else 'yes'

        self.separations = []
        for index in range(len(self.ranking) - 1):
            here = self.ordering_values(self.ranking[index])
            there = self.ordering_values(self.ranking[index + 1])
            position, name = 0, ''
            for spot, key in enumerate(rules.tiebreak_keys, start=1):
                if here[key] != there[key]:
                    position, name = spot, key
                    break
            self.separations.append((index + 1, self.ranking[index],
                                     self.ranking[index + 1], position, name))

    # ---------------- P14 settlement ----------------

    def stage_p14(self):
        rules = self.rules
        depth = rules.tie_group_depth
        keys = rules.tiebreak_keys[:depth]

        self.groups = []
        current = []
        for pid in self.ranking:
            if current:
                here = self.ordering_values(current[-1])
                there = self.ordering_values(pid)
                if all(here[k] == there[k] for k in keys):
                    current.append(pid)
                    continue
                self.groups.append(current)
                current = [pid]
            else:
                current = [pid]
        if current:
            self.groups.append(current)

        self.awarded = dict.fromkeys(self.players, 0)
        self.group_detail = []
        for number, members in enumerate(self.groups, start=1):
            ranks = [self.rank_of[p] for p in members]
            basis = sum(rules.share_table.get(r, 0) for r in ranks)
            amount = rhe(Fraction(rules.pool_cents * basis, 10000))
            share, remainder = divmod(amount, len(members))
            ordered = sorted(members)
            cents = {p: 0 for p in members}
            for pid in ordered[:remainder]:
                cents[pid] = 1
            for pid in members:
                if self.prize_eligible[pid] == 'yes':
                    self.awarded[pid] = share + cents[pid]
            self.group_detail.append({
                'group_id': number,
                'members': members,
                'ranks': ranks,
                'basis': basis,
                'amount': amount,
                'share': share,
                'remainder': remainder,
                'cent': cents,
            })
        self.awarded_total = sum(self.awarded.values())
        self.residue = rules.pool_cents - self.awarded_total

    # ---------------- the delivered documents ----------------

    def documents(self):
        rules = self.rules
        ref = rules.ref
        docs = {}

        docs['normalised_entries.jsonl'] = jsonl_doc([{
            'player_id': pid,
            'division_id': self.entrants[pid]['division_id'],
            'seed_number': self.entrants[pid]['seed_number'],
            'rating_mr': self.entrants[pid]['rating_mr'],
            'rating_source': self.entrants[pid]['rating_source'],
            'entry_seq': self.entrants[pid]['entry_seq'],
            'folded_ids': self.entrants[pid]['folded_ids'],
        } for pid in self.players])

        rows = []
        for pid in self.players:
            for round_no in rules.rounds:
                state, code, seq = self.state[(pid, round_no)]
                rows.append([pid, round_no, state, code, seq])
        docs['participation_ledger.csv'] = delim_doc(
            ['player_id', 'round_no', 'state', 'governing_code', 'governing_seq'], rows, ',')

        rows = []
        for key in self.candidate_keys:
            board = self.candidates[key]
            rows.append([board['round_no'], board['table_no'], board['player_a'],
                         board['player_b'], board['sheet_revision'], board['source_seq']])
        docs['round_match_candidates.csv'] = delim_doc(
            ['round_no', 'table_no', 'player_a', 'player_b', 'sheet_revision',
             'source_seq'], rows, ',')

        rows = []
        for key in self.candidate_keys:
            board = self.results[key]
            rows.append([board['round_no'], board['table_no'], board['player_a'],
                         board['player_b'], board['result_code'], board['basis'],
                         board['games_a'], board['games_b'], board['delta_a']])
        docs['match_result_ledger.csv'] = delim_doc(
            ['round_no', 'table_no', 'player_a', 'player_b', 'result_code', 'basis',
             'games_a', 'games_b', 'delta_a'], rows, ',')

        docs['round_eligibility_ledger.csv'] = delim_doc(
            ['round_no', 'player_id', 'division_id', 'eligible', 'state',
             'running_points', 'running_delta'], self.eligibility_rows, ',')

        docs['bye_ledger.csv'] = delim_doc(
            ['round_no', 'division_id', 'player_id', 'byes_before', 'basis'],
            self.bye_rows, ',')

        docs['authoritative_pairing_ledger.csv'] = delim_doc(
            ['round_no', 'board_no', 'player_a', 'player_b', 'division_a', 'division_b',
             'admission_level', 'points_a', 'points_b'], self.pairing_rows, ',')

        docs['void_adjudication_ledger.csv'] = delim_doc(
            ['round_no', 'table_no', 'player_a', 'player_b', 'void_reason',
             'violation_level', 'tolerance', 'scored_a', 'scored_b'], self.void_rows, ',')

        docs['round_score_ledger.csv'] = delim_doc(
            ['round_no', 'player_id', 'division_id', 'basis', 'base_points',
             'modifier_code', 'modified_points', 'round_points', 'game_delta'],
            self.score_rows, ',')

        classes = {name: index for index, name in enumerate(rules.penalty_classes)}
        penalty = sorted(self.penalty_rows,
                         key=lambda r: (r[0], r[1], classes[r[2]]))
        docs['penalty_application_ledger.psv'] = delim_doc(
            ['round_no', 'player_id', 'penalty_class', 'magnitude', 'notice_seq',
             'value_before', 'value_after', 'shortfall'], penalty, '|')

        history = sorted(self.history_rows, key=lambda r: (r[0], r[1], r[2]))
        docs['opponent_history_ledger.csv'] = delim_doc(
            ['round_no', 'player_id', 'opponent_id', 'counts_for_strength', 'source'],
            history, ',')

        docs['opponent_strength_ledger.csv'] = delim_doc(
            ['player_id', 'opponent_count', 'rate_sum', 'opponent_strength',
             'penalty_units', 'penalty_adjusted_strength'],
            [[pid, self.opponent_count[pid], self.rate_sum[pid], self.strength[pid],
              self.penalty_units[pid], self.adjusted_strength[pid]]
             for pid in self.players], ',')

        docs['standings_ledger.csv'] = delim_doc(
            ['rank', 'player_id', 'division_id', 'event_points', 'adjusted_delta',
             'opponent_strength', 'penalty_adjusted_strength', 'penalty_units',
             'prize_eligible'],
            [[self.rank_of[pid], pid, self.entrants[pid]['division_id'],
              self.event_points[pid], self.adjusted_delta[pid], self.strength[pid],
              self.adjusted_strength[pid], self.penalty_units[pid],
              self.prize_eligible[pid]] for pid in self.ranking], ',')

        rows = []
        for row in self.pairing_rows:
            level = row[6]
            if level > 0:
                relaxed = '+'.join(rules.rungs[:level])
                rows.append([row[0], row[1], row[2], row[3], level, relaxed])
        docs['pairing_fallback_ledger.csv'] = delim_doc(
            ['round_no', 'board_no', 'player_a', 'player_b', 'admission_level',
             'relaxed_constraints'], rows, ',')

        rows = []
        for (side_a, side_b), met in sorted(self.meetings.items()):
            if len(met) > 1:
                rows.append([side_a, side_b, len(met),
                             '+'.join(str(r) for r in sorted(met))])
        docs['repeat_opponent_audit.tsv'] = delim_doc(
            ['player_id', 'opponent_id', 'meetings', 'rounds'], rows, '\t')

        docs['unpaired_ledger.tsv'] = delim_doc(
            ['round_no', 'division_id', 'player_id', 'running_points', 'reason'],
            sorted(self.unpaired_rows, key=lambda r: (r[0], r[2])), '\t')

        docs['pairing_constraint_report.json'] = json_doc({
            'event_reference': ref,
            'rounds': self.round_report,
        })

        docs['game_differential_ledger.psv'] = delim_doc(
            ['player_id', 'rounds_counted', 'raw_delta', 'game_penalty_units',
             'adjusted_delta'],
            [[pid, self.rounds_counted[pid], self.raw_delta[pid],
              self.game_units[pid], self.adjusted_delta[pid]]
             for pid in self.players], '|')

        docs['tiebreak_resolution_ledger.csv'] = delim_doc(
            ['rank', 'player_id', 'next_player_id', 'separating_position',
             'separating_key'], [list(s) for s in self.separations], ',')

        docs['final_ranking.json'] = json_doc({
            'event_id': rules.event_id,
            'event_reference': ref,
            'round_count': rules.round_count,
            'player_count': len(self.players),
            'ranking': [{
                'rank': self.rank_of[pid],
                'player_id': pid,
                'event_points': self.event_points[pid],
                'adjusted_delta': self.adjusted_delta[pid],
                'opponent_strength': self.strength[pid],
                'penalty_adjusted_strength': self.adjusted_strength[pid],
            } for pid in self.ranking],
        })

        trace = []
        for pid in self.players:
            rounds = []
            for round_no in rules.rounds:
                row = self.scores.get((round_no, pid))
                if row:
                    rounds.append({
                        'round_no': round_no,
                        'state': self.state[(pid, round_no)][0],
                        'basis': row['basis'],
                        'round_points': row['round_points'],
                        'game_delta': row['game_delta'],
                    })
                else:
                    rounds.append({
                        'round_no': round_no,
                        'state': self.state[(pid, round_no)][0],
                        'basis': 'none',
                        'round_points': 0,
                        'game_delta': 0,
                    })
            trace.append({
                'player_id': pid,
                'division_id': self.entrants[pid]['division_id'],
                'seed_number': self.entrants[pid]['seed_number'],
                'rounds': rounds,
                'event_points': self.event_points[pid],
                'adjusted_delta': self.adjusted_delta[pid],
                'opponent_strength': self.strength[pid],
                'rank': self.rank_of[pid],
                'awarded_cents': self.awarded[pid],
            })
        docs['player_audit_trace.jsonl'] = jsonl_doc(trace)

        rows = []
        splits = []
        for group in self.group_detail:
            if group['basis'] <= 0:
                continue
            for pid in sorted(group['members'], key=lambda p: self.rank_of[p]):
                rows.append([
                    self.rank_of[pid], pid, group['group_id'], group['basis'],
                    group['amount'], len(group['members']), group['share'],
                    group['cent'][pid], self.prize_eligible[pid], self.awarded[pid]])
            if len(group['members']) > 1:
                splits.append([
                    group['group_id'],
                    '%d+%d' % (min(group['ranks']), max(group['ranks'])),
                    len(group['members']), group['basis'], group['amount'],
                    group['share'], group['remainder'],
                    '+'.join(sorted(group['members']))])
        docs['prize_allocation_ledger.csv'] = delim_doc(
            ['rank', 'player_id', 'group_id', 'group_basis_points',
             'group_amount_cents', 'members', 'base_share_cents', 'remainder_cent',
             'prize_eligible', 'awarded_cents'], rows, ',')
        docs['prize_tie_split.tsv'] = delim_doc(
            ['group_id', 'rank_span', 'members', 'group_basis_points',
             'group_amount_cents', 'base_share_cents', 'remainder_cents',
             'player_ids'], splits, '\t')

        divisions = sorted(rules.div_in_force,
                           key=lambda d: (rules.report_order[d], d))
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append('<settlement event_id="%s" event_reference="%s">'
                     % (rules.event_id, ref))
        for division in divisions:
            seated = [p for p in self.ranking
                      if self.entrants[p]['division_id'] == division]
            head = 'id="%s" report_order="%d" entrants="%d"' % (
                division, rules.report_order[division], len(seated))
            if not seated:
                lines.append(' <division %s />' % head)
                continue
            lines.append(' <division %s>' % head)
            for pid in seated:
                lines.append(
                    '  <entrant rank="%d" player_id="%s" event_points="%d"'
                    ' adjusted_delta="%d" opponent_strength="%d"'
                    ' awarded_cents="%d" />' % (
                        self.rank_of[pid], pid, self.event_points[pid],
                        self.adjusted_delta[pid], self.strength[pid],
                        self.awarded[pid]))
            lines.append(' </division>')
        lines.append('</settlement>')
        docs['standings_by_division.xml'] = '\n'.join(lines) + '\n'

        boards_total = sum(r['boards'] for r in self.round_report)
        byes_total = sum(r['byes'] for r in self.round_report)
        voided_total = sum(r['voided_boards'] for r in self.round_report)
        unpaired_total = sum(r['unpaired'] for r in self.round_report)
        level_total = {}
        for index in range(rules.levels):
            level_total[index] = sum(r['level_counts']['level_%d' % index]
                                     for r in self.round_report)
        points_total = sum(r[7] for r in self.score_rows)
        delta_total = sum(self.adjusted_delta[p] for p in self.players)
        units_total = sum(self.penalty_units[p] for p in self.players)

        conf = ['[event]',
                'event_id = %s' % rules.event_id,
                'event_reference = %s' % ref,
                'round_count = %d' % rules.round_count,
                'player_count = %d' % len(self.players),
                '',
                '[totals]',
                'round_points_total = %d' % points_total,
                'game_delta_total = %d' % delta_total,
                'penalty_units_total = %d' % units_total,
                'points_per_round_ratio = %s' % ratio9(points_total, rules.round_count),
                '',
                '[pairing]',
                'boards_total = %d' % boards_total,
                'byes_total = %d' % byes_total,
                'voided_total = %d' % voided_total,
                'unpaired_total = %d' % unpaired_total]
        for index in range(1, rules.levels):
            conf.append('level_%d_boards = %d' % (index, level_total[index]))
        conf.extend(['',
                     '[prize]',
                     'pool_cents = %d' % rules.pool_cents,
                     'awarded_cents = %d' % self.awarded_total,
                     'residue_cents = %d' % self.residue,
                     'tie_groups = %d' % len(splits),
                     'award_share_ratio = %s' % ratio9(self.awarded_total,
                                                       rules.pool_cents)])
        docs['settlement_control_totals.conf'] = '\n'.join(conf) + '\n'

        shown = self.ranking[:10]
        summary = ['# Settlement summary %s' % ref,
                   '',
                   'Event %s settled over %d rounds with %d entrants seated.'
                   % (rules.event_id, rules.round_count, len(self.players)),
                   '',
                   '## Standings',
                   '',
                   '| rank | player_id | division_id | event_points | adjusted_delta |',
                   '|---|---|---|---|---|']
        for pid in shown:
            summary.append('| %d | %s | %s | %d | %d |' % (
                self.rank_of[pid], pid, self.entrants[pid]['division_id'],
                self.event_points[pid], self.adjusted_delta[pid]))
        pairing = 'Boards admitted at level 0: %d.' % level_total[0]
        for index in range(1, rules.levels):
            pairing += ' Level %d: %d.' % (index, level_total[index])
        summary.extend([
            '',
            '## Pairing',
            '',
            pairing,
            'Byes awarded: %d. Boards voided: %d. Entrants left unpaired: %d.'
            % (byes_total, voided_total, unpaired_total),
            '',
            '## Settlement',
            '',
            'Pool %d cents. Awarded %d cents. Residue %d cents.'
            % (rules.pool_cents, self.awarded_total, self.residue),
            'Tie groups holding more than one member: %d.' % len(splits),
        ])
        docs['event_settlement_summary.md'] = '\n'.join(summary) + '\n'

        division_names = []
        for division in sorted(rules.div_in_force):
            seated = [p for p in self.ranking
                      if self.entrants[p]['division_id'] == division]
            paired = sum(1 for r in self.pairing_rows
                         if self.entrants[r[2]]['division_id'] == division)
            byes = sum(1 for r in self.bye_rows if r[1] == division)
            voided = sum(1 for r in self.void_rows
                         if self.entrants[r[2]]['division_id'] == division)
            awarded = sum(self.awarded[p] for p in seated)
            name = 'division_report_%s.json' % division
            division_names.append(name)
            docs[name] = json_doc({
                'division_id': division,
                'in_force': True,
                'report_order': rules.report_order[division],
                'seated_players': len(seated),
                'paired_boards': paired,
                'byes_awarded': byes,
                'voided_boards': voided,
                'points_total': sum(self.event_points[p] for p in seated),
                'game_delta_total': sum(self.adjusted_delta[p] for p in seated),
                'awarded_cents': awarded,
                'award_share_ratio': ratio9(awarded, rules.pool_cents),
                'top_player': seated[0] if seated else rules.absent,
            })

        order = ['normalised_entries.jsonl',
                 'match_result_ledger.csv',
                 'authoritative_pairing_ledger.csv',
                 'round_score_ledger.csv',
                 'opponent_strength_ledger.csv',
                 'standings_ledger.csv',
                 'participation_ledger.csv',
                 'round_match_candidates.csv',
                 'round_eligibility_ledger.csv',
                 'bye_ledger.csv',
                 'void_adjudication_ledger.csv',
                 'penalty_application_ledger.psv',
                 'opponent_history_ledger.csv',
                 'pairing_fallback_ledger.csv',
                 'repeat_opponent_audit.tsv',
                 'unpaired_ledger.tsv',
                 'pairing_constraint_report.json',
                 'game_differential_ledger.psv',
                 'tiebreak_resolution_ledger.csv',
                 'final_ranking.json',
                 'player_audit_trace.jsonl',
                 'prize_allocation_ledger.csv',
                 'prize_tie_split.tsv',
                 'standings_by_division.xml',
                 'settlement_control_totals.conf',
                 'event_settlement_summary.md'] + division_names

        blobs = {}
        for name in order:
            blobs[name] = docs[name].encode('utf-8')

        core = b''.join(blobs[name] for name in order[:6])
        rest = b''.join(blobs[name] for name in order[6:])
        manifest = {
            'event_id': rules.event_id,
            'event_reference': ref,
            'round_count': rules.round_count,
            'player_count': len(self.players),
            'core_digest': hashlib.sha256(core).hexdigest(),
            'publication_digest': hashlib.sha256(rest).hexdigest(),
            'documents': [{
                'name': name,
                'sha256': hashlib.sha256(blobs[name]).hexdigest(),
                'bytes': len(blobs[name]),
            } for name in order],
        }
        blobs['settlement_manifest.json'] = json_doc(manifest).encode('utf-8')
        return blobs, order + ['settlement_manifest.json']


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument('--data', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    try:
        settlement = Settlement(Papers(args.data))
        blobs, order = settlement.documents()
    except PaperMissing as exc:
        sys.stderr.write('a paper or value the specifications require is absent: %s\n' % exc)
        return 1
    os.makedirs(args.out, exist_ok=True)
    for name in order:
        with open(os.path.join(args.out, name), 'wb') as handle:
            handle.write(blobs[name])
    return 0


if __name__ == '__main__':
    sys.exit(main())
