#!/usr/bin/env python3
"""Exact two-stage robust SNLSQ district geodetic network adjustment.

Reads an extract laid out per the SNLSQ data contract (schema.md) from DATA_DIR
and writes the complete report set into OUT_DIR.  Every reported figure is
derived from the extract with exact rational arithmetic (fractions.Fraction);
no floating point, square root or transcendental value enters any figure.

Usage:  python3 derive_report.py DATA_DIR OUT_DIR
"""

import csv
import json
import os
import re
import sys
import zipfile
from fractions import Fraction

WORKBOOK = 'adjustment_control_workbook.xlsx'
FULL_CIRCLE_GON = 400
DELIMS = {'.csv': ',', '.tsv': '\t', '.psv': '|'}
JSON_LINE_EXT = ('.jsonl', '.ndjson')
SHARD_KEYS = ('length_unit', 'angle_unit', 'sigma_stored_as',
              'sign_flip_rev', 'azimuth_wrap', 'transpose_ids')
# abbreviated -> canonical field names used by the JSON-lines shard
JSON_FIELDS = {'obs_id': 'id', 'kind': 'k', 'observed_value': 'v',
               'computed_nominal': 'c', 'apriori_sigma': 's', 'unit': 'u',
               'sigma_kind': 'sk', 'dir': 'd', 'partials': 'A', 'epoch': 'e',
               'region': 'reg'}
IGNORED_ROW_STATES = ('duplicate', 'void', 'superseded', 'retired',
                      'abandoned', 'decoy', 'stale', 'deprecated')


# ---------------------------------------------------------------------------
# exact rounding / rendering
# ---------------------------------------------------------------------------

def round_half_even(value):
    """Round an exact Fraction to the nearest integer, halves to even."""
    value = Fraction(value)
    num, den = value.numerator, value.denominator
    q, r = divmod(num, den)          # r is always non-negative
    twice = 2 * r
    if twice > den or (twice == den and q % 2):
        q += 1
    return q


def scaled_int(value, places):
    return round_half_even(Fraction(value) * (10 ** places))


def dec(value, places):
    """Render an exact value with `places` decimals, ROUND_HALF_EVEN."""
    i = scaled_int(value, places)
    sign = '-' if i < 0 else ''
    digits = str(abs(i)).rjust(places + 1, '0')
    if places == 0:
        return sign + digits
    return '%s%s.%s' % (sign, digits[:-places], digits[-places:])


def micro(value):
    """Signed integer micrometres of an exact metre/gon value."""
    return scaled_int(value, 6)


def quantize(value, places):
    scale = 10 ** places
    return Fraction(round_half_even(Fraction(value) * scale), scale)


# ---------------------------------------------------------------------------
# generic file readers (standard library only)
# ---------------------------------------------------------------------------

def read_lines(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        return fh.read().splitlines()


def delimited(path, delimiter):
    rows = [ln for ln in read_lines(path)
            if ln.strip() and not ln.lstrip().startswith('#')]
    return list(csv.DictReader(rows, delimiter=delimiter))


def row_is_ignored(row, extra_fields=()):
    """True when a registry row is flagged as a non-authoritative restatement."""
    fields = ('status', 'mark_status', 'provenance', 'ledger_status') + tuple(extra_fields)
    for field in fields:
        val = (row.get(field) or '').strip().lower()
        if val in IGNORED_ROW_STATES:
            return True
    return False


def read_simple_yaml(path):
    """Flat `key: value` reader; first occurrence of a key wins."""
    out = {}
    for line in read_lines(path):
        s = line.strip()
        if not s or s.startswith('#') or s.startswith('-'):
            continue
        m = re.match(r'^([A-Za-z_][\w.]*)\s*:\s*(.*)$', s)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if len(val) > 1 and val[0] == val[-1] and val[0] in '\'"':
            val = val[1:-1]
        if key not in out:
            out[key] = val
    return out


def truth(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ('true', 'yes', 'y', '1', 'on')


# ---------------------------------------------------------------------------
# minimal xlsx reader (the binary control workbook)
# ---------------------------------------------------------------------------

def xml_attrs(text):
    return dict(re.findall(r'([A-Za-z_:][-\w:.]*)\s*=\s*"([^"]*)"', text))


def xml_unescape(text):
    for a, b in (('&lt;', '<'), ('&gt;', '>'), ('&quot;', '"'),
                 ('&apos;', "'"), ('&amp;', '&')):
        text = text.replace(a, b)
    return text


def col_number(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


def read_workbook(path):
    """Return [(sheet_name, [ {column_letter: text}, ... ]), ...]."""
    zf = zipfile.ZipFile(path)
    names = set(zf.namelist())

    shared = []
    if 'xl/sharedStrings.xml' in names:
        blob = zf.read('xl/sharedStrings.xml').decode('utf-8')
        for si in re.findall(r'<si\b[^>]*>(.*?)</si>', blob, re.S):
            shared.append(xml_unescape(''.join(
                re.findall(r'<t\b[^>]*>(.*?)</t>', si, re.S))))

    relmap = {}
    if 'xl/_rels/workbook.xml.rels' in names:
        blob = zf.read('xl/_rels/workbook.xml.rels').decode('utf-8')
        for m in re.finditer(r'<Relationship\b([^>]*?)/?>', blob):
            a = xml_attrs(m.group(1))
            if 'Id' in a and 'Target' in a:
                relmap[a['Id']] = a['Target']

    sheets = []
    wb = zf.read('xl/workbook.xml').decode('utf-8')
    for m in re.finditer(r'<sheet\b([^>]*?)/?>', wb):
        a = xml_attrs(m.group(1))
        name = a.get('name')
        target = relmap.get(a.get('r:id') or a.get('id') or '')
        if name is None or target is None:
            continue
        target = target.lstrip('/')
        if not target.startswith('xl/'):
            target = 'xl/' + target
        if target in names:
            sheets.append((name, target))
    if not sheets:
        sheets = [(n, n) for n in sorted(names)
                  if n.startswith('xl/worksheets/') and n.endswith('.xml')]

    result = []
    for name, target in sheets:
        blob = zf.read(target).decode('utf-8')
        rows = []
        for rm in re.finditer(r'<row\b[^>]*>(.*?)</row>', blob, re.S):
            cells = {}
            for cm in re.finditer(r'<c\b([^>]*?)(?:/>|>(.*?)</c>)', rm.group(1), re.S):
                attrs = xml_attrs(cm.group(1))
                inner = cm.group(2) or ''
                ref = re.match(r'([A-Z]+)', attrs.get('r', '') or '')
                if not ref:
                    continue
                if attrs.get('t') == 's':
                    vs = re.findall(r'<v>(.*?)</v>', inner, re.S)
                    idx = int(vs[0]) if vs else -1
                    text = shared[idx] if 0 <= idx < len(shared) else ''
                else:
                    ts = re.findall(r'<t\b[^>]*>(.*?)</t>', inner, re.S)
                    if ts:
                        text = xml_unescape(''.join(ts))
                    else:
                        vs = re.findall(r'<v>(.*?)</v>', inner, re.S)
                        text = xml_unescape(vs[0]) if vs else ''
                cells[ref.group(1)] = text.strip()
            if cells:
                rows.append(cells)
        result.append((name, rows))
    return result


def workbook_control(sheets, label, preferred='datum'):
    """Read the value cell next to `label`, preferring the named sheet."""
    ordered = ([s for s in sheets if s[0].strip().lower() == preferred] +
               [s for s in sheets if s[0].strip().lower() != preferred])
    for _name, rows in ordered:
        for cells in rows:
            cols = sorted(cells, key=col_number)
            if not cols or cells[cols[0]] != label:
                continue
            for c in cols[1:]:
                if cells[c] != '':
                    return cells[c]
    raise KeyError('control value %r not present in %s' % (label, WORKBOOK))


# ---------------------------------------------------------------------------
# extract loading
# ---------------------------------------------------------------------------

def load_stations(data_dir):
    rows = delimited(os.path.join(data_dir, 'station_registry.csv'), ',')
    stations = {}
    for r in rows:
        if row_is_ignored(r):
            continue
        name = (r.get('station') or '').strip()
        if not name or name in stations:
            continue
        stations[name] = int(r['ordinal'])
    order = sorted(stations, key=lambda s: stations[s])
    labels = []
    for name in order:
        labels.append(name + '.x')
        labels.append(name + '.y')
    return order, labels


def load_unit_factors(data_dir):
    rows = delimited(os.path.join(data_dir, 'reference_unit_registry.csv'), ',')
    chosen = {}
    for r in rows:
        if (r.get('status') or '').strip().lower() != 'authoritative':
            continue
        unit = (r.get('unit') or '').strip()
        if not unit:
            continue
        scope = (r.get('unit_scope') or '').strip().lower()
        factor = Fraction(int(r['factor_num']), int(r['factor_den']))
        current = chosen.get(unit)
        if current is None or (current[1] != 'load_bearing' and scope == 'load_bearing'):
            chosen[unit] = (factor, scope)
    return dict((u, v[0]) for u, v in chosen.items())


def find_shards(data_dir):
    out = []
    for name in sorted(os.listdir(data_dir)):
        if not name.startswith('obs_source'):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in DELIMS or ext in JSON_LINE_EXT:
            out.append(name)
    return out


def shard_header_conventions(path):
    """Pull `key=value` convention tokens out of a shard's comment header."""
    conv = {}
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if not line.lstrip().startswith('#'):
                break
            for m in re.finditer(r'\b([A-Za-z_]\w*)\s*=\s*([^\s,;)]+)', line):
                key, val = m.group(1), m.group(2)
                if key in SHARD_KEYS and key not in conv:
                    conv[key] = val
    return conv


def normalise_json_record(obj):
    rec = {}
    for long_name, short_name in JSON_FIELDS.items():
        if long_name in obj:
            rec[long_name] = obj[long_name]
        elif short_name in obj:
            rec[long_name] = obj[short_name]
    return rec


def read_shard(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in JSON_LINE_EXT:
        lines = [ln for ln in read_lines(path) if ln.strip()]
        conv = {}
        start = 0
        if lines:
            first = json.loads(lines[0])
            if 'id' not in first and 'obs_id' not in first:
                conv = dict((k, first[k]) for k in SHARD_KEYS if k in first)
                start = 1
        records = [normalise_json_record(json.loads(ln)) for ln in lines[start:]]
        return conv, records
    return shard_header_conventions(path), delimited(path, DELIMS[ext])


def sigma_manifest(data_dir):
    """Per-shard convention mirror; the JSON manifest is authoritative."""
    out = {}
    path = os.path.join(data_dir, 'sigma_convention_manifest.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as fh:
            blob = json.load(fh)
        for entry in blob.get('shards', []):
            name = entry.get('file')
            if name:
                out[name] = entry
    return out


def make_observation(row, shard, units, conv, n_unknowns):
    kind = str(row['kind']).strip()
    epoch = int(str(row['epoch']).strip())
    obs_id = str(row['obs_id']).strip()
    if conv['transpose_ids'] and epoch == 2 and len(obs_id) > 3:
        obs_id = obs_id[-3:] + obs_id[:-3]

    unit = str(row.get('unit') or '').strip()
    if not unit:
        unit = conv['angle_unit'] if kind == 'angle' else conv['length_unit']
    if unit not in units:
        raise KeyError('no authoritative unit factor for %r' % unit)
    factor = units[unit]

    value = Fraction(str(row['observed_value']).strip()) * factor
    nominal = Fraction(str(row['computed_nominal']).strip()) * factor

    if conv['sign_flip_rev'] and str(row.get('dir') or 'F').strip().upper() == 'R':
        value = -value
        nominal = -nominal

    if kind == 'angle' and conv['azimuth_wrap']:
        value %= FULL_CIRCLE_GON
        nominal %= FULL_CIRCLE_GON

    misclosure = value - nominal

    sigma_kind = str(row.get('sigma_kind') or '').strip().lower()
    if not sigma_kind:
        sigma_kind = str(conv.get('sigma_stored_as') or 'stddev').strip().lower()
    sigma = Fraction(str(row['apriori_sigma']).strip())
    if sigma_kind == 'variance':
        variance = sigma * factor * factor
    else:
        variance = (sigma * factor) ** 2
    if variance <= 0:
        raise ValueError('non-positive variance for %s' % obs_id)

    partials = {}
    for token in str(row['partials']).split(';'):
        token = token.strip()
        if not token:
            continue
        idx_text, coef_text = token.split(':')
        idx = int(idx_text)
        if not 0 <= idx < n_unknowns:
            raise ValueError('partial index %d out of range' % idx)
        partials[idx] = partials.get(idx, Fraction(0)) + Fraction(coef_text)

    return {'obs_id': obs_id, 'kind': kind, 'l': misclosure,
            'variance': variance, 'partials': partials, 'epoch': epoch,
            'region': str(row.get('region') or '').strip(), 'shard': shard}


def load_observations(data_dir, units, n_unknowns):
    manifest = sigma_manifest(data_dir)
    observations = []
    seen = set()
    for name in find_shards(data_dir):
        path = os.path.join(data_dir, name)
        raw_conv, rows = read_shard(path)
        mirror = manifest.get(name, {})
        conv = {}
        for key in SHARD_KEYS:
            if key in raw_conv:
                conv[key] = raw_conv[key]
            elif key in mirror:
                conv[key] = mirror[key]
        for flag in ('sign_flip_rev', 'azimuth_wrap', 'transpose_ids'):
            conv[flag] = truth(conv.get(flag), False)
        conv.setdefault('length_unit', None)
        conv.setdefault('angle_unit', None)
        for row in rows:
            obs = make_observation(row, name, units, conv, n_unknowns)
            if obs['obs_id'] in seen:
                raise ValueError('duplicate obs_id %s' % obs['obs_id'])
            seen.add(obs['obs_id'])
            observations.append(obs)
    observations.sort(key=lambda o: o['obs_id'])
    return observations


def load_sessions(data_dir, by_id):
    path = os.path.join(data_dir, 'session_correlation.csv')
    if not os.path.exists(path):
        return []
    sessions = []
    claimed = set()
    for r in delimited(path, ','):
        if (r.get('status') or '').strip().lower() != 'authoritative':
            continue
        a = (r.get('member_a_obs_id') or '').strip()
        b = (r.get('member_b_obs_id') or '').strip()
        if a not in by_id or b not in by_id or a == b:
            continue
        if a in claimed or b in claimed:
            continue          # an observation belongs to at most one session
        claimed.add(a)
        claimed.add(b)
        sessions.append({'session_id': (r.get('session_id') or '').strip(),
                         'a': a, 'b': b,
                         'cov': Fraction(int(r['cov_num']), int(r['cov_den']))})
    return sessions


def load_first_wins_map(path, key_field, value_field, delimiter=','):
    out = {}
    for r in delimited(path, delimiter):
        if row_is_ignored(r):
            continue
        key = (r.get(key_field) or '').strip()
        val = (r.get(value_field) or '').strip()
        if key and key not in out:
            out[key] = val
    return out


def load_chi_bounds(data_dir):
    bounds = {}
    for r in delimited(os.path.join(data_dir, 'chi_square_bounds_table.csv'), ','):
        if row_is_ignored(r):
            continue
        dof = int(r['dof'])
        if dof in bounds:
            continue
        bounds[dof] = Fraction(int(r['center_num']), int(r['center_den']))
    return bounds


# ---------------------------------------------------------------------------
# exact weighted least squares
# ---------------------------------------------------------------------------

def block_inverse(var_a, var_b, cov, places):
    det = var_a * var_b - cov * cov
    if det <= 0:
        raise ValueError('session covariance matrix is not positive definite')
    c00 = quantize(var_b / det, places)
    c01 = quantize(-cov / det, places)
    c11 = quantize(var_a / det, places)
    return [[c00, c01], [c01, c11]]


def assemble(diag_obs, weights, blocks, n_unknowns):
    zero = Fraction(0)
    N = [[zero] * n_unknowns for _ in range(n_unknowns)]
    b = [zero] * n_unknowns
    for obs in diag_obs:
        w = weights[obs['obs_id']]
        if w == 0:
            continue
        items = list(obs['partials'].items())
        l = obs['l']
        for i, ai in items:
            wa = w * ai
            b[i] += wa * l
            row = N[i]
            for j, aj in items:
                row[j] += wa * aj
    for obs_a, obs_b, cinv in blocks:
        pair = (obs_a, obs_b)
        for pi in (0, 1):
            left = pair[pi]
            left_items = list(left['partials'].items())
            for qi in (0, 1):
                right = pair[qi]
                c = cinv[pi][qi]
                if c == 0:
                    continue
                right_items = list(right['partials'].items())
                rl = right['l']
                for i, ai in left_items:
                    coef = ai * c
                    b[i] += coef * rl
                    row = N[i]
                    for j, aj in right_items:
                        row[j] += coef * aj
    return N, b


def solve_exact(N, b):
    n = len(b)
    M = [list(N[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        pivot = None
        for r in range(col, n):
            if M[r][col] != 0:
                pivot = r
                break
        if pivot is None:
            raise ValueError('normal matrix is singular at column %d' % col)
        if pivot != col:
            M[col], M[pivot] = M[pivot], M[col]
        pv = M[col][col]
        prow = M[col]
        for r in range(n):
            if r == col or M[r][col] == 0:
                continue
            f = M[r][col] / pv
            row = M[r]
            for c in range(col, n + 1):
                row[c] -= f * prow[c]
    return [M[i][n] / M[i][i] for i in range(n)]


def residual(obs, x):
    total = Fraction(0)
    for i, ai in obs['partials'].items():
        total += ai * x[i]
    return total - obs['l']


def prepare_stage(observations, sessions, places):
    by_id = dict((o['obs_id'], o) for o in observations)
    blocks = []
    members = set()
    for s in sessions:
        a, b = s['a'], s['b']
        if a in by_id and b in by_id:
            cinv = block_inverse(by_id[a]['variance'], by_id[b]['variance'],
                                 s['cov'], places)
            blocks.append((by_id[a], by_id[b], cinv))
            members.add(a)
            members.add(b)
    diag = [o for o in observations if o['obs_id'] not in members]
    return diag, blocks, members


def robust_stage(observations, diag, blocks, base_weights, k2, iterations,
                 places, n_unknowns):
    """Initial weighted solve followed by exactly `iterations` IRLS passes."""
    weights = dict((o['obs_id'], base_weights[o['obs_id']]) for o in diag)
    downweighted = set()
    N, b = assemble(diag, weights, blocks, n_unknowns)
    x = solve_exact(N, b)
    for _ in range(iterations):
        res = dict((o['obs_id'], residual(o, x)) for o in observations)
        weights = {}
        downweighted = set()
        for obs in diag:
            oid = obs['obs_id']
            p = base_weights[oid]
            v = res[oid]
            t = v * v * p
            if t > k2:
                weights[oid] = quantize(p * (k2 / t), places)
                downweighted.add(oid)
            else:
                weights[oid] = p
        N, b = assemble(diag, weights, blocks, n_unknowns)
        x = solve_exact(N, b)
    res = dict((o['obs_id'], residual(o, x)) for o in observations)
    return {'x': x, 'weights': weights, 'downweighted': downweighted,
            'N': N, 'residuals': res}


def quadratic_form(diag, blocks, weights, res):
    total = Fraction(0)
    for obs in diag:
        v = res[obs['obs_id']]
        total += weights[obs['obs_id']] * v * v
    for obs_a, obs_b, cinv in blocks:
        va = res[obs_a['obs_id']]
        vb = res[obs_b['obs_id']]
        total += (cinv[0][0] * va * va + 2 * cinv[0][1] * va * vb
                  + cinv[1][1] * vb * vb)
    return total


# ---------------------------------------------------------------------------
# output helpers
# ---------------------------------------------------------------------------

def write_text(path, text):
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


def write_json(path, obj):
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(obj, fh, sort_keys=True, indent=2)
        fh.write('\n')


def write_jsonlines(path, records):
    chunks = []
    for rec in records:
        chunks.append(json.dumps(rec, sort_keys=True, separators=(',', ':')))
        chunks.append('\n')
    write_text(path, ''.join(chunks))


def write_rows(path, header, rows, delimiter):
    lines = [delimiter.join(header)]
    for row in rows:
        lines.append(delimiter.join(str(c) for c in row))
    write_text(path, '\n'.join(lines) + '\n')


def xml_escape(text):
    return (str(text).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: derive_report.py DATA_DIR OUT_DIR\n')
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)

    # --- iteration policy (decoy_tuning_k inside it is deliberately unused) --
    policy = read_simple_yaml(os.path.join(data_dir, 'iteration_policy.yaml'))
    iterations = int(policy['irls_iterations'])
    places = int(policy['weight_quant_decimal_places'])
    rounding = (policy.get('weight_quant_rounding') or 'ROUND_HALF_EVEN').strip()
    if rounding.upper() != 'ROUND_HALF_EVEN':
        raise ValueError('unsupported weight quantisation rounding %r' % rounding)

    # --- control values: workbook only --------------------------------------
    sheets = read_workbook(os.path.join(data_dir, WORKBOOK))
    u_constrained = int(Fraction(workbook_control(sheets, 'u_constrained')))
    tuning_k = Fraction(workbook_control(sheets, 'tuning_k'))
    blunder_crit = Fraction(workbook_control(sheets, 'blunder_crit'))
    origin_index = int(Fraction(workbook_control(sheets, 'datum_origin_station')))
    k2 = tuning_k * tuning_k
    crit2 = blunder_crit * blunder_crit

    # --- network, units, observations ---------------------------------------
    station_order, labels = load_stations(data_dir)
    n_unknowns = 2 * len(station_order)
    if not 0 <= origin_index < len(station_order):
        raise ValueError('datum origin station index out of range')
    origin_station = station_order[origin_index]

    units = load_unit_factors(data_dir)
    observations = load_observations(data_dir, units, n_unknowns)
    by_id = dict((o['obs_id'], o) for o in observations)
    sessions = load_sessions(data_dir, by_id)

    base_weights = dict((o['obs_id'], quantize(1 / o['variance'], places))
                        for o in observations)

    # --- stage 1: robust solve over the full network ------------------------
    diag1, blocks1, _members1 = prepare_stage(observations, sessions, places)
    stage1 = robust_stage(observations, diag1, blocks1, base_weights, k2,
                          iterations, places, n_unknowns)

    # --- data snooping: remove gross errors --------------------------------
    blunders = []
    for obs in observations:
        oid = obs['obs_id']
        v = stage1['residuals'][oid]
        if v * v * base_weights[oid] > crit2:
            blunders.append(oid)
    blunder_set = set(blunders)
    blunders.sort()

    # --- stage 2: re-solve the reduced network -----------------------------
    kept = [o for o in observations if o['obs_id'] not in blunder_set]
    if not kept:
        raise ValueError('every observation was rejected as a blunder')
    sessions2 = [s for s in sessions
                 if s['a'] not in blunder_set and s['b'] not in blunder_set]
    diag2, blocks2, members2 = prepare_stage(kept, sessions2, places)
    stage2 = robust_stage(kept, diag2, blocks2, base_weights, k2, iterations,
                          places, n_unknowns)

    res = stage2['residuals']
    free_x = stage2['x']
    vtpv = quadratic_form(diag2, blocks2, stage2['weights'], res)

    n_obs = len(kept)
    dof = n_obs - u_constrained
    if dof <= 0:
        raise ValueError('non-positive degrees of freedom')
    sigma0_sq = vtpv / dof

    bounds = load_chi_bounds(data_dir)
    if dof not in bounds:
        raise KeyError('no acceptance interval tabulated for dof=%d' % dof)
    centre = bounds[dof]
    lo = centre - Fraction(1, 2)
    hi = centre + Fraction(1, 2)
    if vtpv < lo:
        verdict = 'REJECT_LOW'
    elif vtpv > hi:
        verdict = 'REJECT_HIGH'
    else:
        verdict = 'PASS'

    # --- datum S-transformation --------------------------------------------
    shift_x = free_x[2 * origin_index]
    shift_y = free_x[2 * origin_index + 1]
    shifted_x = []
    for t in range(len(station_order)):
        shifted_x.append(free_x[2 * t] - shift_x)
        shifted_x.append(free_x[2 * t + 1] - shift_y)

    # --- reporting weights --------------------------------------------------
    report_weights = {}
    for obs in diag2:
        report_weights[obs['obs_id']] = stage2['weights'][obs['obs_id']]
    for obs_a, obs_b, cinv in blocks2:
        report_weights[obs_a['obs_id']] = cinv[0][0]
        report_weights[obs_b['obs_id']] = cinv[1][1]

    downweighted = sorted(stage2['downweighted'])
    down_set = stage2['downweighted']

    # --- rollup keys --------------------------------------------------------
    frame_of = load_first_wins_map(
        os.path.join(data_dir, 'station_frame_map.csv'), 'station', 'frame')
    campaign_of = load_first_wins_map(
        os.path.join(data_dir, 'epoch_campaign_map.csv'), 'epoch', 'campaign')

    def primary_frame(obs):
        idx = min(obs['partials'])
        station = station_order[idx // 2]
        if station not in frame_of:
            raise KeyError('no frame mapped for station %s' % station)
        return frame_of[station]

    def obs_campaign(obs):
        key = str(obs['epoch'])
        if key not in campaign_of:
            raise KeyError('no campaign mapped for epoch %s' % key)
        return campaign_of[key]

    # --- group accumulation (exact sums, rounded once) ----------------------
    def new_group():
        return {'count': 0, 'down': 0, 'abs': Fraction(0)}

    districts = {}
    epochs = {}
    derived = {}
    for obs in kept:
        oid = obs['obs_id']
        v = res[oid]
        av = v if v >= 0 else -v
        is_down = 1 if oid in down_set else 0

        g = districts.setdefault(obs['region'], new_group())
        g['count'] += 1
        g['down'] += is_down
        g['abs'] += av

        g = epochs.setdefault(obs['epoch'], new_group())
        g['count'] += 1
        g['down'] += is_down
        g['abs'] += av

        g = derived.setdefault((primary_frame(obs), obs_campaign(obs)), new_group())
        g['count'] += 1
        g['down'] += is_down
        g['abs'] += av

    # ------------------------------------------------------------------ files
    unknowns_metres = dict((labels[i], dec(shifted_x[i], 10))
                           for i in range(n_unknowns))
    unknowns_micro = dict((labels[i], micro(shifted_x[i]))
                          for i in range(n_unknowns))
    vtpv_text = dec(vtpv, 10)
    sigma_text = dec(sigma0_sq, 10)
    k_text = dec(tuning_k, 6)
    crit_text = dec(blunder_crit, 6)

    write_json(os.path.join(out_dir, 'adjusted_state.json'), {
        'unknowns': unknowns_metres,
        'unknowns_micrometres': unknowns_micro,
        'n_observations': n_obs,
        'u_constrained': u_constrained,
        'degrees_of_freedom': dof,
        'variance_of_unit_weight': sigma_text,
        'quadratic_form_vtpv': vtpv_text,
        'tuning_constant_k': k_text,
        'blunder_critical_value': crit_text,
        'blunders_removed': len(blunders),
        'datum_origin_station': origin_station,
        'model_test_verdict': verdict,
    })

    write_json(os.path.join(out_dir, 'model_test.json'), {
        'degrees_of_freedom': dof,
        'quadratic_form_vtpv': vtpv_text,
        'acceptance_low': dec(lo, 6),
        'acceptance_high': dec(hi, 6),
        'verdict': verdict,
        'passed': verdict == 'PASS',
    })

    write_json(os.path.join(out_dir, 'downweighted_observations.json'), {
        'count': len(downweighted),
        'obs_ids': downweighted,
    })

    write_json(os.path.join(out_dir, 'removed_blunders.json'), {
        'count': len(blunders),
        'obs_ids': blunders,
        'critical_value': crit_text,
    })

    write_json(os.path.join(out_dir, 'datum_transformation.json'), {
        'origin_station': origin_station,
        'origin_station_index': origin_index,
        'free_corrections_micrometres': dict(
            (labels[i], micro(free_x[i])) for i in range(n_unknowns)),
        'shifted_corrections_micrometres': unknowns_micro,
    })

    signed_sum = Fraction(0)
    max_abs = None
    max_abs_id = ''
    for obs in kept:
        v = res[obs['obs_id']]
        signed_sum += v
        av = v if v >= 0 else -v
        if max_abs is None or av > max_abs:
            max_abs = av
            max_abs_id = obs['obs_id']
    write_json(os.path.join(out_dir, 'residual_summary.json'), {
        'n': n_obs,
        'sum_signed_micrometres': micro(signed_sum),
        'max_abs_residual_micrometres': micro(max_abs),
        'max_abs_residual_obs_id': max_abs_id,
    })

    write_rows(os.path.join(out_dir, 'unknowns.csv'),
               ['unknown_index', 'label', 'correction_metres',
                'correction_micrometres'],
               [[i, labels[i], dec(shifted_x[i], 10), micro(shifted_x[i])]
                for i in range(n_unknowns)], ',')

    write_rows(os.path.join(out_dir, 'residuals.csv'),
               ['obs_id', 'kind', 'residual_micrometres', 'downweighted'],
               [[o['obs_id'], o['kind'], micro(res[o['obs_id']]),
                 1 if o['obs_id'] in down_set else 0] for o in kept], ',')

    write_rows(os.path.join(out_dir, 'residuals.tsv'),
               ['obs_id', 'residual_micrometres'],
               [[o['obs_id'], micro(res[o['obs_id']])] for o in kept], '\t')

    write_rows(os.path.join(out_dir, 'final_weights.psv'),
               ['obs_id', 'weight_num', 'weight_den'],
               [[o['obs_id'], report_weights[o['obs_id']].numerator,
                 report_weights[o['obs_id']].denominator] for o in kept], '|')

    for district in sorted(districts):
        g = districts[district]
        write_json(os.path.join(out_dir, 'district_%s.json' % district), {
            'district': district,
            'observation_count': g['count'],
            'downweighted_count': g['down'],
            'sum_abs_residual_micrometres': micro(g['abs']),
        })

    for epoch in sorted(epochs):
        g = epochs[epoch]
        write_json(os.path.join(out_dir, 'epoch_%d.json' % epoch), {
            'epoch': epoch,
            'observation_count': g['count'],
            'sum_abs_residual_micrometres': micro(g['abs']),
        })

    all_frames = sorted(set(frame_of.values()))
    all_campaigns = sorted(set(campaign_of.values()))
    for frame in all_frames:
        for campaign in all_campaigns:
            g = derived.get((frame, campaign)) or new_group()
            write_json(os.path.join(out_dir, 'rollup_%s_%s.json' % (frame, campaign)), {
                'frame': frame,
                'campaign': campaign,
                'observation_count': g['count'],
                'downweighted_count': g['down'],
                'sum_abs_residual_micrometres': micro(g['abs']),
            })

    trace = Fraction(0)
    for i in range(n_unknowns):
        trace += stage2['N'][i][i]
    write_json(os.path.join(out_dir, 'normal_matrix_trace.json'), {
        'trace_num': trace.numerator,
        'trace_den': trace.denominator,
        'trace_decimal': dec(trace, 6),
    })

    write_json(os.path.join(out_dir, 'provenance_summary.json'), {
        'control_values_source': WORKBOOK,
        'u_constrained': u_constrained,
        'tuning_constant_k': k_text,
        'blunder_critical_value': crit_text,
        'datum_origin_station': origin_station,
        'decoys_ignored': [
            'archive_backfill.db',
            'azimuth_reference_table.tsv:grad_alias',
            'deprecated_precorrection_coords.csv',
            'iteration_policy.yaml:decoy_tuning_k',
            'legacy_orientation_offsets.tsv',
            'observation_provenance.psv:status',
            'observation_weight_manifest.csv:naive_weight',
            'reference_unit_registry.csv:status',
            'residual_prior_epoch.tsv',
            'scale_factor_table.csv:scale_bp',
            'scale_factor_table.csv:scale_ppm',
            'session_correlation.csv:status',
            'stale_cached_solution.json',
            'station_registry.csv:display_coord_x',
            'station_registry.csv:display_coord_y',
        ],
    })

    write_text(os.path.join(out_dir, 'status.txt'),
               'verdict=%s dof=%d u=%d n=%d blunders_removed=%d '
               'datum_origin=%s sigma0_sq=%s downweighted=%d\n'
               % (verdict, dof, u_constrained, n_obs, len(blunders),
                  origin_station, sigma_text, len(downweighted)))

    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<adjustment>',
                 '  <verdict>%s</verdict>' % xml_escape(verdict),
                 '  <degrees_of_freedom>%d</degrees_of_freedom>' % dof,
                 '  <u_constrained>%d</u_constrained>' % u_constrained,
                 '  <variance_of_unit_weight>%s</variance_of_unit_weight>'
                 % xml_escape(sigma_text),
                 '  <unknowns>']
    for i in range(n_unknowns):
        xml_lines.append('    <unknown label="%s" correction_micrometres="%d"/>'
                         % (xml_escape(labels[i]), micro(shifted_x[i])))
    xml_lines.append('  </unknowns>')
    xml_lines.append('</adjustment>')
    write_text(os.path.join(out_dir, 'adjustment_report.xml'),
               '\n'.join(xml_lines) + '\n')

    write_text(os.path.join(out_dir, 'adjustment_summary.yaml'),
               'model_test_verdict: %s\n'
               'degrees_of_freedom: %d\n'
               'u_constrained: %d\n'
               'variance_of_unit_weight: %s\n'
               'downweighted_count: %d\n'
               'tuning_constant_k: %s\n'
               % (verdict, dof, u_constrained, sigma_text,
                  len(downweighted), k_text))

    write_text(os.path.join(out_dir, 'adjustment_report.md'),
               '# District Sensor-Network Adjustment Report\n\n'
               'Two-stage robust minimal-constraint adjustment, re-derived from the\n'
               'extract with exact rational arithmetic.  All figures below are the\n'
               'stage-2 (post blunder-removal) figures.\n\n'
               '- Global model test verdict: **%s**\n'
               '- Degrees of freedom: %d\n'
               '- Variance of unit weight: %s\n'
               '- Downweighted count: %d\n'
               '- Tuning constant: %s\n\n'
               'Observations in the stage-2 network: %d (%d removed as gross errors,\n'
               'critical value %s).  Constrained components u = %d.  Quadratic form\n'
               'vTPv = %s.  Datum origin station: %s.\n'
               % (verdict, dof, sigma_text, len(downweighted), k_text,
                  n_obs, len(blunders), crit_text, u_constrained, vtpv_text,
                  origin_station))

    write_jsonlines(os.path.join(out_dir, 'observation_stream.jsonl'),
                    [{'obs_id': o['obs_id'], 'kind': o['kind'],
                      'residual_micrometres': micro(res[o['obs_id']]),
                      'downweighted': o['obs_id'] in down_set} for o in kept])

    write_jsonlines(os.path.join(out_dir, 'observation_stream.ndjson'),
                    [{'id': o['obs_id'], 'r': micro(res[o['obs_id']])}
                     for o in kept])

    sys.stdout.write(
        'verdict=%s dof=%d u=%d n=%d blunders=%d downweighted=%d '
        'sigma0_sq=%s vtpv=%s origin=%s\n'
        % (verdict, dof, u_constrained, n_obs, len(blunders),
           len(downweighted), sigma_text, vtpv_text, origin_station))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
