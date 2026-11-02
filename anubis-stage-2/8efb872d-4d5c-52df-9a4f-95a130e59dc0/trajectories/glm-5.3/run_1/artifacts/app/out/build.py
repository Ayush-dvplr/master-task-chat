#!/usr/bin/env python3
"""Edge cache capacity optimizer.

    python3 build.py phase1 <DATA_DIR> <P1_DIR>
    python3 build.py phase2 <P1_DIR> <P2_DIR>
    python3 build.py phase3 <P1_DIR> <P2_DIR> <P3_DIR>

Phase 1 freezes the fleet as of the planning cut following the edge capacity
standard revision 7.  Phase 2 rolls the fleet up, allocates the shield pools,
plans the RAM pins and ranks the nodes.  Phase 3 projects the already approved
amendments that take effect after the cut.
"""

import base64
import collections
import csv
import datetime
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from fractions import Fraction

FREEZE_UTC = '2024-10-01T18:00:00Z'
CUT = datetime.datetime(2024, 10, 1, 18, 0, 0, tzinfo=datetime.timezone.utc)
CUT_E = CUT.timestamp()
WINDOW_E = CUT_E - 7 * 86400

CODEC_DEFAULT_LEVEL = {'gzip': 6, 'zstd': 3, 'br': 4}
CODEC_ALIASES = {'brotli': 'br', 'zst': 'zstd'}
IN_SCOPE_STATUS = {'active', 'serving', 'maintenance'}
REFRESH_ORDER = {'hourly': 0, 'daily': 1, 'weekly': 2}
REFRESH_FACTOR = {'hourly': Fraction(1, 24), 'daily': Fraction(1), 'weekly': Fraction(7)}

P1_FILES = ['nodes.csv', 'properties.csv', 'policies.csv', 'footprints.csv',
            'pending.json', 'pops.json']
P2_FILES = ['pop_rollup.csv', 'class_rollup.csv', 'shield_alloc.csv', 'pin_plan.csv',
            'risk_rank.csv', 'manifest.json']


# --------------------------------------------------------------------------
# errors
# --------------------------------------------------------------------------

class UpstreamError(Exception):
    """A required input is missing, unreadable or inconsistent."""


class UsageError(Exception):
    """Wrong subcommand or wrong number of arguments."""


# --------------------------------------------------------------------------
# input helpers
# --------------------------------------------------------------------------

def read_bytes(path):
    try:
        with open(path, 'rb') as fh:
            return fh.read()
    except OSError as exc:
        raise UpstreamError(path) from exc


def read_text(path):
    data = read_bytes(path)
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise UpstreamError(path) from exc


def need_dir(path):
    if not os.path.isdir(path) or not os.access(path, os.R_OK | os.X_OK):
        raise UpstreamError(path)
    return path


def need_file(base, name):
    path = os.path.join(base, name)
    if not os.path.isfile(path) or not os.access(path, os.R_OK):
        raise UpstreamError(path)
    return path


# --------------------------------------------------------------------------
# arithmetic and formatting helpers
# --------------------------------------------------------------------------

def round_half_even(num, den=1):
    """Round num/den half to even; accepts ints, floats and Fractions."""
    value = Fraction(num) / Fraction(den)
    n, d = value.numerator, value.denominator
    if d == 1:
        return n
    q, r = divmod(n, d)
    if 2 * r > d or (2 * r == d and q % 2 == 1):
        q += 1
    return q


def to_kib(value_bytes):
    return round_half_even(value_bytes, 1024)


def to_mib(value_kib):
    return round_half_even(value_kib, 1024)


def dec(value, places):
    """Write value with exactly `places` decimals, rounded half to even."""
    if value is None:
        return ''
    scaled = round_half_even(Fraction(value) * (10 ** places))
    sign = '-' if scaled < 0 else ''
    text = str(abs(scaled)).rjust(places + 1, '0')
    if places:
        return sign + text[:-places] + '.' + text[-places:]
    return sign + text


def num(value):
    return '' if value is None else str(value)


def boolean(flag):
    return '1' if flag else '0'


def write_csv(path, header, rows):
    with open(path, 'wb') as fh:
        fh.write((','.join(header) + '\n').encode('utf-8'))
        for row in rows:
            fh.write((','.join(row) + '\n').encode('utf-8'))


def write_json(path, obj):
    with open(path, 'wb') as fh:
        fh.write((json.dumps(obj, indent=2, sort_keys=True) + '\n').encode('utf-8'))


def sha256_file(path):
    return hashlib.sha256(read_bytes(path)).hexdigest()


def iso_utc(epoch):
    moment = datetime.datetime.fromtimestamp(round(epoch), datetime.timezone.utc)
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ')


# --------------------------------------------------------------------------
# generic value parsing
# --------------------------------------------------------------------------

def _tz(offset):
    sign = 1 if offset[0] == '+' else -1
    rest = offset[1:]
    if ':' in rest:
        hours, minutes = rest.split(':')
        delta = datetime.timedelta(hours=int(hours), minutes=int(minutes or 0))
    else:
        delta = datetime.timedelta(hours=int(rest))
    return datetime.timezone(sign * delta)


def to_epoch(text):
    """Parse an instant in any of the forms the standard lists."""
    if text is None:
        return None
    s = str(text).strip()
    if s == '':
        return None
    if re.fullmatch(r'\d{13}(\.\d+)?', s):
        return float(s) / 1000.0
    if re.fullmatch(r'\d+(\.\d+)?', s):
        return float(s)
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
        return datetime.datetime(int(s[0:4]), int(s[5:7]), int(s[8:10]),
                                 tzinfo=datetime.timezone.utc).timestamp()
    m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})'
                     r'(?:\.(\d+))?\s*(Z|[+-]\d{2}(?::?\d{2})?)?', s)
    if m:
        y, mo, d, h, mi, sec, _frac, off = m.groups()
        tz = datetime.timezone.utc if (off is None or off == 'Z') else _tz(off)
        return datetime.datetime(int(y), int(mo), int(d), int(h), int(mi), int(sec),
                                 tzinfo=tz).timestamp()
    return None


def raw_value(value):
    """Parse a raw counter value, tolerating floats and scientific notation."""
    if value is None:
        return None
    s = str(value).strip()
    if s == '':
        return None
    try:
        return int(s)
    except ValueError:
        f = float(s)
        return int(f) if f == int(f) else int(round(f))


def size_bytes(text):
    """Capacity suffixes: none/B bytes; KiB..PiB powers of 1024; KB..PB powers of 1000."""
    s = str(text).strip()
    m = re.fullmatch(r'([\d.]+)\s*([A-Za-z]*)', s)
    if not m:
        raise ValueError('bad capacity: ' + s)
    unit = m.group(2)
    mult = {'': 1, 'B': 1,
            'KiB': 1024, 'MiB': 1024 ** 2, 'GiB': 1024 ** 3, 'TiB': 1024 ** 4,
            'PiB': 1024 ** 5,
            'KB': 1000, 'MB': 1000 ** 2, 'GB': 1000 ** 3, 'TB': 1000 ** 4,
            'PB': 1000 ** 5}[unit]
    return round_half_even(Fraction(m.group(1)) * mult)


def mem_bytes(text):
    """Memory sizes are binary whatever the suffix."""
    s = str(text).strip()
    m = re.fullmatch(r'(\d+)\s*([A-Za-z]*)', s)
    if not m:
        raise ValueError('bad memory: ' + s)
    n = int(m.group(1))
    unit = m.group(2)
    if unit in ('G', 'GB', 'GiB'):
        return n * 1024 ** 3
    if unit in ('M', 'MB', 'MiB'):
        return n * 1024 ** 2
    if unit in ('', 'B'):
        return n
    raise ValueError('bad memory: ' + s)


def offset_minutes(text):
    s = str(text).strip().upper().replace('UTC', '').replace('GMT', '')
    if s in ('', 'Z'):
        return 0
    m = re.fullmatch(r'([+-])(\d{1,2}):?(\d{2})?', s)
    if not m:
        raise ValueError('bad utc offset: ' + str(text))
    sign = 1 if m.group(1) == '+' else -1
    return sign * (int(m.group(2)) * 60 + int(m.group(3) or 0))


def parse_flag(value):
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in ('on', 'true', '1', 'yes'):
        return True
    if s in ('off', 'false', '0', 'no'):
        return False
    raise ValueError('bad flag: ' + str(value))


def whole_percent(text):
    s = str(text).strip().rstrip('%').strip()
    return int(s)


def whole_number(text):
    s = str(text).strip()
    return int(s)


# --------------------------------------------------------------------------
# phase 1 corpus
# --------------------------------------------------------------------------

def load_directory(data_dir):
    """Parse every file phase 1 needs into one dictionary."""
    corpus = {}
    corpus['data_dir'] = data_dir
    corpus['nodes'], corpus['alias'], corpus['renames'], corpus['follow'] = load_identity(data_dir)
    corpus['pops'], corpus['placements'], corpus['pop_alias'] = load_pop_registry(data_dir)
    corpus['status'] = load_status(data_dir, corpus)
    corpus['decom'] = load_decom(data_dir, corpus)
    corpus['class'] = load_class(data_dir, corpus)
    corpus['tier_class'], corpus['tier_node'] = load_tiers(data_dir, corpus)
    corpus['aliases'], corpus['catalog'], corpus['types'], corpus['node_paths'] = load_pathmap(data_dir, corpus)
    corpus['oldnames'] = load_2023_names(data_dir)
    corpus['conf'] = load_conf(data_dir)
    corpus['prop_changes'] = load_prop_changes(data_dir, corpus)
    by_node = collections.defaultdict(list)
    for (owner, prop), action in corpus['prop_changes'].items():
        by_node[owner].append((prop, action))
    corpus['prop_changes_by_node'] = dict(by_node)
    corpus['ratios'] = load_ratios(data_dir)
    corpus['prod'], corpus['bad_instances'] = load_scrape_targets(data_dir, corpus)
    corpus['stg_pairs'] = load_stg_pairs(data_dir)
    corpus['replay'] = load_replay(data_dir, corpus)
    corpus['sweep'] = load_sweeps(data_dir, corpus)
    corpus['disk'] = load_disk(data_dir, corpus)
    corpus['usage'] = load_usage(data_dir, corpus)
    corpus['prior_peak'] = load_prior_peak(data_dir, corpus)
    corpus['changes'] = load_changes(data_dir, corpus)
    return corpus


def load_identity(data_dir):
    text = read_text(need_file(data_dir, 'nodedir_export.ldif'))
    entries = []
    current = None
    pending = None
    for line in text.split('\n'):
        line = line.rstrip('\r')
        if line.startswith('dn:'):
            current = {}
            entries.append(current)
            pending = None
            continue
        if not line.strip():
            pending = None
            continue
        if line.startswith(' ') and pending is not None:
            current[pending] += line.strip()
            continue
        m = re.match(r'^(cn|assetTag|dNSName|legacyName|serialNumber|objectClass|version)(::|:)\s*(.*)$', line)
        if m:
            key, sep, value = m.groups()
            if key in ('objectClass', 'version'):
                continue
            if sep == '::':
                try:
                    value = base64.b64decode(value.strip()).decode('utf-8')
                except (ValueError, UnicodeDecodeError) as exc:
                    raise UpstreamError(need_file(data_dir, 'nodedir_export.ldif')) from exc
            current[key] = value.strip()
            pending = key
        else:
            pending = None
    alias = {}
    names = set()
    for entry in entries:
        cn = entry['cn'].lower()
        names.add(cn)
        for key in ('cn', 'assetTag', 'dNSName', 'legacyName', 'serialNumber'):
            if key in entry:
                alias[entry[key].lower()] = cn

    best = {}
    for line in read_text(need_file(data_dir, 'ident_overrides.properties')).split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = re.match(r'^(alias\.[A-Za-z]+\.[^=:\s]+|rename\.[^=:\s]+)\s*[=:]\s*(.+?)\s*;\s*rev=(\d+)\s*$', line)
        if not m:
            raise UpstreamError(need_file(data_dir, 'ident_overrides.properties'))
        key = m.group(1).lower()
        value = m.group(2).lower()
        rev = int(m.group(3))
        if key not in best or rev > best[key][0]:
            best[key] = (rev, value)
    renames = {}
    for key, (_rev, value) in best.items():
        if key.startswith('rename.'):
            renames[key[len('rename.'):]] = value
        else:
            alias[key.split('.', 2)[2]] = value

    def follow(name):
        seen = set()
        current = name
        while True:
            nxt = renames.get(current)
            if nxt is None or nxt == current or current in seen:
                return current
            seen.add(current)
            current = nxt

    return {follow(n) for n in names}, alias, renames, follow


def load_pop_registry(data_dir):
    text = read_text(need_file(data_dir, 'pop_registry.toml'))
    pops = {}
    placements = {}
    section = None
    for line in text.split('\n'):
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        m = re.match(r'^\[pops\.([A-Za-z0-9_-]+)\]$', s)
        if m:
            section = ('pop', m.group(1).lower())
            pops[section[1]] = {}
            continue
        m = re.match(r'^\[placement\.([A-Za-z0-9_-]+)\]$', s)
        if m:
            section = ('pl', m.group(1))
            placements[section[1]] = {}
            continue
        if s.startswith('['):
            section = None
            continue
        if section and '=' in s:
            key, value = s.split('=', 1)
            key = key.strip()
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            if section[0] == 'pop':
                pops[section[1]][key] = value
            else:
                placements[section[1]][key] = value
    pop_alias = {}
    for code, table in pops.items():
        pop_alias[code.lower()] = code
        for alias in re.findall(r'"([^"]+)"', table.get('aliases', '')):
            pop_alias[alias.lower()] = code
    return pops, placements, pop_alias


def load_status(data_dir, corpus):
    nodes = corpus['nodes']
    alias = corpus['alias']
    follow = corpus['follow']
    best = {}
    path = need_file(data_dir, 'asset_status_hist.csv')
    for row in csv.DictReader(read_text(path).split('\n')):
        moment = to_epoch(row.get('recorded_at'))
        if moment is None or moment > CUT_E:
            continue
        node = resolve_ref(row.get('node_ref'), None, nodes, alias, follow, corpus['pop_alias'])
        if node is None:
            continue
        key = (moment, row.get('recorded_at', ''))
        if node not in best or key >= best[node][0]:
            best[node] = (key, row.get('status', '').strip().lower(), row.get('mem', ''))
    return {n: (v[1], v[2]) for n, v in best.items()}


def load_decom(data_dir, corpus):
    nodes = corpus['nodes']
    alias = corpus['alias']
    follow = corpus['follow']
    out = collections.defaultdict(list)
    for event in read_text(need_file(data_dir, 'decom_cal.ics')).split('BEGIN:VEVENT')[1:]:
        m = re.search(r'^STATUS:([A-Za-z]+)', event, re.M)
        status = m.group(1).strip().lower() if m else ''
        m = re.search(r'^X-NODE:(.*)$', event, re.M)
        ref = m.group(1).strip() if m else ''
        m = re.search(r'^DTSTART([^:\n]*):([^\n\r]+)', event, re.M)
        if not m:
            continue
        param = m.group(1).strip(';')
        value = m.group(2).strip()
        if param == 'VALUE=DATE':
            moment = to_epoch(value[0:4] + '-' + value[4:6] + '-' + value[6:8])
        else:
            moment = ics_moment(value, param[5:] if param.startswith('TZID=') else None)
        if moment is None:
            continue
        node = resolve_ref(ref, None, nodes, alias, follow, corpus['pop_alias'])
        if node is None:
            continue
        out[node].append((moment, status))
    return out


def ics_moment(value, zone):
    m = re.fullmatch(r'(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(Z?)', value)
    if not m:
        return None
    y, mo, d, h, mi, s, zulu = m.groups()
    stamp = datetime.datetime(int(y), int(mo), int(d), int(h), int(mi), int(s),
                              tzinfo=datetime.timezone.utc).timestamp()
    if zulu == 'Z':
        return stamp
    if zone:
        m = re.fullmatch(r'Etc/GMT([+-])(\d+)', zone)
        if m:
            sign = -1 if m.group(1) == '-' else 1
            return stamp - sign * int(m.group(2)) * 3600
        m = re.fullmatch(r'(?:UTC|GMT)([+-])(\d{1,2})(?::(\d{2}))?', zone)
        if m:
            sign = 1 if m.group(1) == '+' else -1
            return stamp - sign * (int(m.group(2)) * 3600 + int(m.group(3) or 0) * 60)
    return stamp


def load_class(data_dir, corpus):
    nodes = corpus['nodes']
    alias = corpus['alias']
    follow = corpus['follow']
    text = read_text(need_file(data_dir, 'hwclass_ledger.sql'))
    best = {}
    pattern = re.compile(r"INSERT INTO hw_class_ledger \(node_ref, hw_class, eff_at, voided, note\) "
                         r"VALUES \('([^']*)', '([^']*)', '([^']*)', (\d+), '([^']*)'\);")
    for m in pattern.finditer(text):
        ref, hw_class, eff, voided, _note = m.groups()
        if int(voided) != 0:
            continue
        moment = to_epoch(eff)
        if moment is None or moment > CUT_E:
            continue
        node = resolve_ref(ref, None, nodes, alias, follow, corpus['pop_alias'])
        if node is None:
            continue
        key = (moment, eff)
        if node not in best or key >= best[node][0]:
            best[node] = (key, hw_class.strip().lower())
    return {n: v[1] for n, v in best.items()}


def load_tiers(data_dir, corpus):
    nodes = corpus['nodes']
    alias = corpus['alias']
    follow = corpus['follow']
    root = ET.fromstring(read_text(need_file(data_dir, 'tier_assign.xml')))
    class_default = {}
    for element in root.findall('class'):
        class_default[element.get('name').strip().lower()] = element.get('tier').strip().lower()
    best = {}
    for element in root.findall('node'):
        node = resolve_ref(element.get('ref'), None, nodes, alias, follow, corpus['pop_alias'])
        if node is None:
            continue
        for tier in element.findall('tier'):
            moment = to_epoch(tier.get('since'))
            if moment is None or moment > CUT_E:
                continue
            key = (moment, tier.get('since'))
            if node not in best or key >= best[node][0]:
                best[node] = (key, (tier.text or '').strip().lower())
    return class_default, {n: v[1] for n, v in best.items()}


def load_pathmap(data_dir, corpus):
    text = read_text(need_file(data_dir, 'pathmap.ini'))
    sections = collections.OrderedDict()
    current = None
    for line in text.split('\n'):
        s = line.strip()
        if not s or s.startswith(';') or s.startswith('#'):
            continue
        m = re.match(r'^\[(.+)\]$', s)
        if m:
            current = m.group(1).strip()
            sections.setdefault(current, [])
            continue
        if current and '=' in s:
            key, value = s.split('=', 1)
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            sections[current].append((key.strip().lower(), value))
    aliases = {}
    catalog = collections.OrderedDict()
    types = {}
    for key, value in sections.get('aliases', []):
        aliases[key] = value
    for key, value in sections.get('catalog', []):
        catalog[key] = value
    for key, value in sections.get('types', []):
        types[key] = value
    node_paths = {}
    for name, items in sections.items():
        if name in ('aliases', 'catalog', 'types'):
            continue
        node = resolve_ref(name, None, corpus['nodes'], corpus['alias'], corpus['follow'],
                           corpus['pop_alias'])
        if node is None:
            continue
        node_paths.setdefault(node, []).append(collections.OrderedDict(items))
    return aliases, dict(catalog), types, node_paths


def load_2023_names(data_dir):
    out = {}
    for line in read_text(need_file(data_dir, 'edgecache_2023.conf')).split('\n'):
        m = re.match(r'^#\s*renamed\s+(\S+)\s*->\s*(\S+)\s*$', line.strip())
        if m:
            out[m.group(1).lower()] = m.group(2).lower()
    return out


def resolve_ref(ref, pop, nodes, alias, follow, pop_alias):
    """Map any node reference to its canonical id, or None."""
    if ref is None:
        return None
    token = str(ref).strip().lower()
    if token == '':
        return None
    target = alias.get(token)
    if target is None and pop:
        code = str(pop).strip().lower()
        for candidate in (code, pop_alias.get(code, code)):
            target = alias.get(token + '@' + candidate)
            if target is not None:
                break
    if target is None:
        target = token
    final = follow(target)
    if final in nodes:
        return final
    return None


def prop_name(token, aliases, catalog, oldnames):
    """Resolve a property reference to a canonical property name."""
    if token is None:
        return None
    token = str(token).strip().lower()
    if token == '':
        return None
    if token in catalog:
        return token
    if token in aliases:
        return aliases[token]
    if token in oldnames:
        return oldnames[token]
    for name, path in catalog.items():
        if path == token:
            return name
    return None


def scan_conf(text):
    """Parse an edgecache configuration file.

    Returns (global_directives, class_blocks, node_blocks, includes) with
    blocks in file order.  Block entries are ('loc', path, entries) or
    ('dir', name, value).
    """
    lines = text.split('\n')
    count = len(lines)
    includes = []

    def parse_block(index):
        entries = []
        while index < count:
            line = lines[index].strip()
            if line == '' or line.startswith('#'):
                index += 1
                continue
            if line == '}':
                return entries, index + 1
            m = re.match(r'^location\s+(\S+?)\s*\{\s*$', line)
            if m:
                sub, index = parse_block(index + 1)
                entries.append(('loc', m.group(1), sub))
                continue
            m = re.match(r'^include\s+(\S+?)\s*;\s*$', line)
            if m:
                includes.append(m.group(1))
                index += 1
                continue
            m = re.match(r'^(\S+)\s+(.+?)\s*;\s*$', line)
            if m:
                entries.append(('dir', m.group(1), m.group(2)))
            index += 1
        return entries, index

    globals_directives = []
    classes = []
    node_blocks = []
    i = 0
    while i < count:
        line = lines[i].strip()
        if line == '' or line.startswith('#'):
            i += 1
            continue
        m = re.match(r'^(class|node)\s+(\S+)\s*\{\s*$', line)
        if m:
            entries, i = parse_block(i + 1)
            if m.group(1) == 'class':
                classes.append((m.group(2).lower(), entries))
            else:
                node_blocks.append((m.group(2), entries))
            continue
        m = re.match(r'^include\s+(\S+?)\s*;\s*$', line)
        if m:
            includes.append(m.group(1))
            i += 1
            continue
        if line in ('{', '}'):
            i += 1
            continue
        m = re.match(r'^(\S+)\s+(.+?)\s*;\s*$', line)
        if m:
            globals_directives.append(('dir', m.group(1), m.group(2)))
        i += 1
    return globals_directives, classes, node_blocks, includes


def load_conf(data_dir):
    main = read_text(need_file(data_dir, 'edgecache_main.conf'))
    parsed = scan_conf(main)
    includes = []
    for name in parsed[3]:
        includes.append(scan_conf(read_text(need_file(data_dir, name))))
    return {'global': parsed[0], 'classes': parsed[1], 'nodes': parsed[2], 'includes': includes}


def load_prop_changes(data_dir, corpus):
    nodes = corpus['nodes']
    alias = corpus['alias']
    follow = corpus['follow']
    best = {}
    for row in csv.DictReader(read_text(need_file(data_dir, 'prop_changes.csv')).split('\n')):
        moment = to_epoch(row.get('effective'))
        if moment is None or moment > CUT_E:
            continue
        node = resolve_ref(row.get('node_ref'), None, nodes, alias, follow, corpus['pop_alias'])
        prop = prop_name(row.get('property'), corpus['aliases'], corpus['catalog'], corpus['oldnames'])
        if node is None or prop is None:
            continue
        key = (moment, row.get('effective', ''))
        if (node, prop) not in best or key >= best[(node, prop)][0]:
            best[(node, prop)] = (key, row.get('action', '').strip().lower())
    return {k: v[1] for k, v in best.items()}


def load_ratios(data_dir):
    text = read_text(need_file(data_dir, 'codec_bench.csv'))
    totals = collections.defaultdict(list)
    for row in csv.DictReader(text.split('\n')):
        if row.get('status', '').strip().lower() != 'ok':
            continue
        if row.get('corpus', '').strip().lower() != 'edge24':
            continue
        ctype = row.get('content_type', '').strip().lower()
        codec = row.get('codec', '').strip().lower()
        codec = CODEC_ALIASES.get(codec, codec)
        totals[(ctype, codec)].append(Fraction(int(row['in_bytes']), int(row['out_bytes'])))
    ratios = {}
    for key, values in totals.items():
        mean = sum(values) / len(values)
        ratios[key] = Fraction(round_half_even(mean * 100), 100)
    return ratios


def load_scrape_targets(data_dir, corpus):
    mirror = set()
    for entry in json.loads(read_text(need_file(data_dir, 'mirror_twins.json'))):
        instance = entry.get('mirror_instance')
        if instance:
            mirror.add(instance)
    lab = set()
    for i, line in enumerate(read_text(need_file(data_dir, 'labnodes.tsv')).split('\n')):
        if i == 0:
            continue
        fields = line.split('\t')
        if len(fields) > 1 and fields[1].strip():
            lab.add(fields[1].strip())
    bad = mirror | lab
    prod = {}
    for line in read_text(need_file(data_dir, 'scrape_targets.toml')).split('\n'):
        s = line.strip()
        if not s or s.startswith('#') or s == '[targets]' or s.startswith('['):
            continue

        def grab(key):
            m = re.search(key + r' = "([^"]*)"', s)
            return m.group(1) if m else None

        instance = grab('instance')
        if instance is None or instance in bad:
            continue
        node = resolve_ref(grab('node'), None, corpus['nodes'], corpus['alias'], corpus['follow'],
                           corpus['pop_alias'])
        prop = prop_name(grab('property'), corpus['aliases'], corpus['catalog'], corpus['oldnames'])
        if node is None or prop is None:
            continue
        prod[(node, prop)] = {'instance': instance, 'job': grab('job'),
                              'unit': grab('counter_unit'), 'scraper': grab('scraper')}
    return prod, bad


def load_stg_pairs(data_dir):
    pairs = set()
    current = None
    fields = {}
    for line in read_text(need_file(data_dir, 'stg_jobs.toml')).split('\n'):
        s = line.strip()
        m = re.match(r'^\[scrape\.(\w+)\]$', s)
        if m:
            current = m.group(1)
            fields = {}
            continue
        if s.startswith('['):
            current = None
            fields = {}
            continue
        if current and '=' in s and not s.startswith('#'):
            key, value = s.split('=', 1)
            fields[key.strip()] = value.strip().strip('"')
            if 'job' in fields and 'instance' in fields:
                pairs.add((fields['job'], fields['instance']))
    return pairs


def load_replay(data_dir, corpus):
    out = set()
    for line in read_text(need_file(data_dir, 'replay_inject_q3.prom')).split('\n'):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        m = re.match(r'^\S+\{([^}]*)\}\s+(\S+)(?:\s+(\S+))?$', line.strip())
        if not m:
            continue
        labels = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        value = raw_value(m.group(2))
        moment = to_epoch(m.group(3)) if m.group(3) else None
        node = resolve_ref(labels.get('node'), labels.get('pop'), corpus['nodes'], corpus['alias'],
                           corpus['follow'], corpus['pop_alias'])
        prop = prop_name(labels.get('prop'), corpus['aliases'], corpus['catalog'], corpus['oldnames'])
        if node is None or prop is None or value is None or moment is None:
            continue
        out.add((node, prop, labels.get('instance'), moment, value))
    return out


def load_sweeps(data_dir, corpus):
    """node -> sweep interval (hourly, daily, weekly)."""
    text = read_text(need_file(data_dir, 'sweeper.crontab'))
    by_node = collections.defaultdict(list)
    for line in text.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        fields = line.split()
        if 'root' not in fields:
            continue
        user = fields.index('root')
        if user < 2:
            continue
        command = fields[user + 1:]
        if '/usr/local/sbin/cache-sweep' not in command:
            continue
        if '/etc/edgecache/edgecache.conf' not in command:
            continue
        if '--dry-run' in command:
            continue
        node = resolve_ref(fields[0], None, corpus['nodes'], corpus['alias'], corpus['follow'],
                           corpus['pop_alias'])
        if node is None:
            continue
        by_node[node].append(tuple(fields[1:user]))
    out = {}
    for node, specs in by_node.items():
        best = None
        for spec in specs:
            interval = schedule_interval(spec)
            if interval is None:
                continue
            if best is None or REFRESH_ORDER[interval] < REFRESH_ORDER[best]:
                best = interval
        out[node] = best or 'daily'
    return out


def schedule_interval(spec):
    """Classify a cron schedule as hourly, daily or weekly (None when it never fires)."""
    if len(spec) != 1 or not spec[0].startswith('@'):
        return cron_interval(spec)
    name = spec[0].lower()
    if name == '@reboot':
        return None
    if name == '@hourly':
        return 'hourly'
    if name in ('@daily', '@midnight'):
        return 'daily'
    if name in ('@weekly', '@monthly', '@yearly', '@annually'):
        return 'weekly'
    return None


def cron_interval(spec):
    if len(spec) != 5:
        return None
    minutes = cron_field(spec[0], 0, 59)
    hours = cron_field(spec[1], 0, 23)
    days = cron_field(spec[2], 1, 31)
    months = cron_field(spec[3], 1, 12)
    dows = cron_field(spec[4], 0, 6)
    if minutes is None or hours is None or days is None or months is None or dows is None:
        return None
    dom_open = spec[2] == '*'
    dow_open = spec[4] == '*'
    start = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    gaps = []
    previous = None
    for offset in range(0, 60 * 24 * 60):
        moment = start + datetime.timedelta(minutes=offset)
        if moment.minute not in minutes or moment.hour not in hours or moment.month not in months:
            continue
        weekday = (moment.weekday() + 1) % 7
        if dom_open and dow_open:
            pass
        elif dom_open:
            if weekday not in dows:
                continue
        elif dow_open:
            if moment.day not in days:
                continue
        else:
            if moment.day not in days and weekday not in dows:
                continue
        if previous is not None:
            gaps.append(offset - previous)
        previous = offset
    if not gaps:
        return None
    least = min(gaps)
    if least <= 60:
        return 'hourly'
    if least <= 60 * 24:
        return 'daily'
    return 'weekly'


CRON_NAMES = {'sun': 0, 'mon': 1, 'tue': 2, 'wed': 3, 'thu': 4, 'fri': 5, 'sat': 6,
              'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6, 'jul': 7,
              'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}


def cron_field(text, low, high):
    if text == '*':
        return set(range(low, high + 1))
    values = set()
    for part in text.split(','):
        part = part.strip().lower()
        if not part:
            return None
        step = 1
        if '/' in part:
            part, step_text = part.split('/', 1)
            step = int(step_text)
            if part == '':
                part = '*'
        if part == '*':
            start, end = low, high
        elif '-' in part:
            a, b = part.split('-', 1)
            start = cron_value(a, low, high)
            end = cron_value(b, low, high)
            if start is None or end is None:
                return None
        else:
            start = cron_value(part, low, high)
            if start is None:
                return None
            end = high if '/' in text else start
        for v in range(start, end + 1, step):
            values.add(v)
    return values


def cron_value(text, low, high):
    text = text.strip().lower()
    if text in CRON_NAMES:
        return CRON_NAMES[text]
    if not re.fullmatch(r'\d+', text):
        return None
    value = int(text)
    if value == 7 and low == 0:
        return 0
    return value


def load_disk(data_dir, corpus):
    """node -> (media, usable_bytes)."""
    best = {}
    for row in csv.DictReader(read_text(need_file(data_dir, 'blkdev_audit.tsv')).split('\n'),
                              delimiter='\t'):
        if row.get('mount', '').strip() != '/var/cache/edge':
            continue
        moment = to_epoch(row.get('audited'))
        if moment is None or moment > CUT_E:
            continue
        node = resolve_ref(row.get('node'), None, corpus['nodes'], corpus['alias'], corpus['follow'],
                           corpus['pop_alias'])
        if node is None:
            continue
        key = (moment, row.get('audited', ''))
        if node not in best or key >= best[node][0]:
            best[node] = (key, row)
    out = {}
    for node, (_key, row) in best.items():
        blocks = int(row['blocks'])
        bsize_field = row['bsize'].strip().lower()
        if bsize_field.endswith('k'):
            bsize = int(bsize_field[:-1]) * 1024
        else:
            bsize = int(bsize_field)
        media = row['media'].strip().lower()
        reserved = reserved_blocks(row.get('reserve', ''), media, blocks)
        usable = (blocks - reserved) * bsize
        out[node] = (media, usable)
    return out


def reserved_blocks(spec, media, blocks):
    if media == 'sata':
        return 0
    spec = (spec or '').strip().lower()
    if spec in ('', '-'):
        return blocks * 7 // 100
    m = re.match(r'^rb=(\d+)$', spec)
    if m:
        return int(m.group(1))
    m = re.match(r'^op=(\d+)$', spec)
    if m:
        return blocks * int(m.group(1)) // 100
    raise ValueError('bad reserve: ' + spec)


def load_usage(data_dir, corpus):
    """Snapshots of df output: list of (epoch, node, cmd, fields) sorted by epoch."""
    snapshots = []
    for name in ('ducollect_a.log', 'ducollect_b.log', 'ducollect_late.log'):
        text = read_text(need_file(data_dir, name))
        lines = text.split('\n')
        i = 0
        while i < len(lines):
            m = re.match(r'^=== node=(\S+) at=(\S+) cmd=(df -\w+)$', lines[i])
            if not m:
                i += 1
                continue
            ref, stamp, cmd = m.groups()
            node = resolve_ref(ref, None, corpus['nodes'], corpus['alias'], corpus['follow'],
                               corpus['pop_alias'])
            moment = to_epoch(stamp)
            i += 2
            mounts = {}
            while i < len(lines) and lines[i] and not lines[i].startswith('===') \
                    and not lines[i].startswith('---'):
                fields = lines[i].split()
                if len(fields) >= 6:
                    mounts[fields[-1]] = fields
                i += 1
            if node is None or moment is None:
                continue
            edge = mounts.get('/var/cache/edge')
            snapshots.append((moment, name, node, cmd, edge))
    snapshots.sort(key=lambda s: (s[0], s[1]))
    return snapshots


def usage_bytes(fields, cmd):
    """Used bytes of a df -k / df -h line."""
    used = fields[2]
    if cmd == 'df -k':
        return int(used) * 1024
    m = re.fullmatch(r'([\d.]+)([KMGT]?)', used.strip())
    if not m:
        raise ValueError('bad df -h used: ' + used)
    unit = {'': 1, 'K': 1024, 'M': 1024 ** 2, 'G': 1024 ** 3, 'T': 1024 ** 4}[m.group(2)]
    return int(Fraction(m.group(1)) * unit)


def load_prior_peak(data_dir, corpus):
    totals = collections.defaultdict(int)
    seen = collections.defaultdict(bool)
    for row in csv.DictReader(read_text(need_file(data_dir, 'optplan_prev.csv')).split('\n')):
        if row.get('run_id', '').strip() != 'q2-final':
            continue
        node = resolve_ref(row.get('node_ref'), None, corpus['nodes'], corpus['alias'],
                           corpus['follow'], corpus['pop_alias'])
        if node is None:
            continue
        text = row.get('peak_kib', '').strip()
        m = re.match(r'^(\d+)(?:\.\d+)?\s*(KiB|MiB)?$', text)
        if not m:
            continue
        value = int(m.group(1))
        if m.group(2) == 'MiB':
            value *= 1024
        totals[node] += value
        seen[node] = True
    return {n: totals[n] for n in totals if seen[n]}


# --------------------------------------------------------------------------
# phase 1 counter readings
# --------------------------------------------------------------------------

def iter_readings(name, text):
    """Yield (node_ref, prop_ref, instance, job, stamp, value, pop) for a scraper file."""
    base = name.rsplit('/', 1)[-1]
    if base.endswith('.jsonl') or base.endswith('.ndjson'):
        for line in text.split('\n'):
            if not line.strip():
                continue
            item = json.loads(line)
            if 'labels' in item:
                labels = item['labels']
                stamp = item.get('ts')
                value = item.get('value')
            else:
                labels = item
                stamp = item.get('t', item.get('ts'))
                value = item.get('v', item.get('value'))
            yield (labels.get('node'), labels.get('prop'),
                   labels.get('instance', labels.get('inst')), labels.get('job'),
                   stamp, value, labels.get('pop'))
    elif base.endswith('.log'):
        for line in text.split('\n'):
            m = re.match(r'^(\S+) sample node=(\S+)(?: pop=(\S+))? prop=(\S+) '
                         r'inst=(\S+) job=(\S+) v=(\S+)$', line)
            if m:
                yield (m.group(2), m.group(4), m.group(5), m.group(6),
                       m.group(1), m.group(7), m.group(3))
    elif base.endswith('.prom'):
        for line in text.split('\n'):
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            m = re.match(r'^(\S+)\{([^}]*)\}\s+(\S+)(?:\s+(\S+))?$', line.strip())
            if not m:
                continue
            labels = dict(re.findall(r'(\w+)="([^"]*)"', m.group(2)))
            yield (labels.get('node'), labels.get('prop'), labels.get('instance'),
                   labels.get('job'), m.group(4) if m.group(4) else None,
                   m.group(3), labels.get('pop'))
    elif base.endswith('.xml'):
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            raise UpstreamError(name) from exc
        for sample in root:
            yield (sample.get('n'), sample.get('p'), sample.get('i'), sample.get('j'),
                   sample.get('t'), sample.get('v'), sample.get('pop'))
    elif base.endswith('.html'):
        for row in re.findall(r'<tr>(.*?)</tr>', text, re.S):
            cells = [re.sub(r'<[^>]+>', '', cell).strip()
                     for cell in re.findall(r'<td>(.*?)</td>', row, re.S)]
            if len(cells) >= 7:
                yield (cells[0], cells[1], cells[2], cells[3], cells[5], cells[6], cells[4])
    elif base.endswith('.sql'):
        pattern = re.compile(r"VALUES \('([^']*)', '([^']*)', '([^']*)', '([^']*)', "
                             r"(NULL|'[^']*'), '([^']*)', ([0-9.eE+-]+)\)")
        for m in pattern.finditer(text):
            node, prop, inst, job, pop, stamp, value = m.groups()
            yield (node, prop, inst, job, stamp, value, None if pop == 'NULL' else pop.strip("'"))
    elif base.endswith('.tsv'):
        lines = text.split('\n')
        for line in lines[1:]:
            fields = line.split('\t')
            if len(fields) < 7:
                continue
            yield (fields[1], fields[3], fields[4], fields[5], fields[0], fields[6], fields[2])
    elif base.endswith('.csv'):
        for row in csv.DictReader(text.split('\n')):
            yield (row.get('node'), row.get('property'), row.get('instance'), row.get('job'),
                   row.get('timestamp'), row.get('value'), row.get('pop'))


def collect_readings(corpus, node_pop):
    """Return {(node, property): [(instant, raw_value), ...]} for kept in-window readings."""
    alias = corpus['alias']
    follow = corpus['follow']
    nodes = corpus['nodes']
    pop_alias = corpus['pop_alias']
    aliases = corpus['aliases']
    catalog = corpus['catalog']
    oldnames = corpus['oldnames']
    target = {}
    for (node, prop), info in corpus['prod'].items():
        target[(node, prop, info['instance'], info['job'])] = info['unit']
    series = {}
    offset_of_node = {n: corpus['pops'][p].get('_offset_min', 0)
                      for n, p in node_pop.items() if p in corpus['pops']}
    scrapers = sorted({info['scraper'] for info in corpus['prod'].values()})
    for name in scrapers:
        text = read_text(need_file(corpus['data_dir'], name))
        for node_ref, prop_ref, instance, job, stamp, value, pop in iter_readings(name, text):
            node = resolve_ref(node_ref, pop, nodes, alias, follow, pop_alias)
            if node is None:
                continue
            prop = prop_name(prop_ref, aliases, catalog, oldnames)
            if prop is None:
                prop = path_to_prop(corpus, node, prop_ref)
            if prop is None:
                continue
            if (node, prop, instance, job) not in target:
                continue
            if (job, instance) in corpus['stg_pairs']:
                continue
            if stamp is None:
                continue
            stamp = str(stamp).strip()
            if re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', stamp):
                moment = to_epoch(stamp + '+00') - offset_of_node.get(node, 0) * 60
            else:
                moment = to_epoch(stamp)
            if moment is None or not WINDOW_E <= moment <= CUT_E:
                continue
            value = raw_value(value)
            if value is None:
                continue
            if (node, prop, instance, moment, value) in corpus['replay']:
                continue
            bucket = series.setdefault((node, prop), {})
            if moment not in bucket:
                bucket[moment] = value
    return {key: sorted(bucket.items()) for key, bucket in series.items()}


def path_to_prop(corpus, node, path):
    """Resolve a cache path through the node's pathmap sections, then the catalog."""
    if path is None:
        return None
    text = str(path).strip().lower()
    for section in corpus['node_paths'].get(node, []):
        for key, value in section.items():
            if value.strip().lower() == text:
                name = prop_name(key, corpus['aliases'], corpus['catalog'], corpus['oldnames'])
                if name:
                    return name
    for name, value in corpus['catalog'].items():
        if value.strip().lower() == text:
            return name
    return None


def daily_volume(readings, unit):
    """Daily volume in bytes over the kept in-window readings."""
    if readings is None or len(readings) < 2:
        return None
    mult = 1024 if (unit or '').strip().lower() == 'kib' else 1
    values = [(t, v * mult) for (t, v) in readings]
    increase = 0
    for (_t0, v0), (_t1, v1) in zip(values, values[1:]):
        increase += (v1 - v0) if v1 >= v0 else v1
    span = values[-1][0] - values[0][0]
    if span == 0:
        return 0 if increase == 0 else None
    return round_half_even(increase * 86400, span)


# --------------------------------------------------------------------------
# phase 1 policy
# --------------------------------------------------------------------------

def class_templates(corpus):
    """class -> {property: location entries} for the class block locations."""
    templates = {}
    for name, entries in corpus['conf']['classes']:
        block = {}
        for entry in entries:
            if entry[0] != 'loc':
                continue
            for prop, default in corpus['catalog'].items():
                if default == entry[1]:
                    block[prop] = entry[2]
        templates[name] = block
    return templates


def served_properties(corpus, node, hw_class, templates):
    """The properties a node serves: class template adjusted by property changes."""
    props = set(templates.get(hw_class, {}))
    for prop in list(props):
        if corpus['prop_changes'].get((node, prop)) == 'remove':
            props.discard(prop)
    for prop, action in corpus['prop_changes_by_node'].get(node, []):
        if action == 'add':
            props.add(prop)
    return props


def new_policy():
    return {'versions': None, 'refresh': None, 'store_compressed': None,
            'hot_raw': None, 'codec': None, 'level': None}


def apply_directive(policy, name, value):
    name = name.strip().lower()
    if name == 'versions':
        policy['versions'] = int(str(value).strip())
    elif name == 'refresh':
        policy['refresh'] = str(value).strip().lower()
    elif name == 'store-compressed':
        policy['store_compressed'] = parse_flag(value)
    elif name == 'hot-raw':
        policy['hot_raw'] = parse_flag(value)
    elif name == 'codec':
        codec = str(value).strip().lower()
        codec = CODEC_ALIASES.get(codec, codec)
        policy['codec'] = codec
        policy['level'] = CODEC_DEFAULT_LEVEL[codec]
    elif name == 'codec-level':
        policy['level'] = int(str(value).strip())


def apply_entries(policy, entries):
    for entry in entries:
        if entry[0] == 'dir':
            apply_directive(policy, entry[1], entry[2])


def apply_amendment(policy, field, value):
    field = field.strip().lower()
    if field == 'versions':
        policy['versions'] = int(str(value).strip())
    elif field == 'refresh':
        policy['refresh'] = str(value).strip().lower()
    elif field == 'store_compressed':
        policy['store_compressed'] = parse_flag(value)
    elif field == 'hot_raw':
        policy['hot_raw'] = parse_flag(value)
    elif field == 'codec':
        text = str(value).strip().lower()
        if ':' in text:
            codec, level = text.split(':', 1)
            codec = CODEC_ALIASES.get(codec, codec)
            policy['codec'] = codec
            policy['level'] = int(level)
        else:
            codec = CODEC_ALIASES.get(text, text)
            policy['codec'] = codec
            policy['level'] = CODEC_DEFAULT_LEVEL[codec]


def amendment_sort_key(change):
    return (change['effective'], change['id'])


def classify_changes(corpus, in_scope, served, hw_class_of):
    """Split approved amendments into those applying at the cut and pending ones."""
    class_nodes = collections.defaultdict(list)
    for node in in_scope:
        class_nodes[hw_class_of[node]].append(node)
    applied = {'class': collections.defaultdict(list), 'node': collections.defaultdict(list)}
    pending = []
    for change in corpus['changes']:
        if change['status'] not in ('approved', 'approve'):
            continue
        if change['effective'] is None:
            continue
        prop = prop_name(change['property'], corpus['aliases'], corpus['catalog'], corpus['oldnames'])
        if prop is None:
            continue
        if change['scope'] == 'node':
            node = resolve_ref(change['target'], None, corpus['nodes'], corpus['alias'],
                               corpus['follow'], corpus['pop_alias'])
            if node is None or node not in in_scope or prop not in served[node]:
                continue
            scope, key = 'node', node
        elif change['scope'] == 'class':
            cls = change['target'].strip().lower()
            if cls not in class_nodes:
                continue
            if not any(prop in served[n] for n in class_nodes[cls]):
                continue
            scope, key = 'class', cls
        else:
            continue
        entry = dict(change)
        entry['prop'] = prop
        entry['scope_kind'] = scope
        entry['key'] = key
        if change['effective'] <= CUT_E:
            applied[scope][(key, prop)].append(entry)
        else:
            pending.append(entry)
    for table in applied.values():
        for entries in table.values():
            entries.sort(key=amendment_sort_key)
    pending.sort(key=lambda e: (e['effective'], e['id']))
    return applied, pending


def node_block_map(corpus):
    """node -> location entries in layer order (main file, then includes in order)."""
    out = collections.defaultdict(list)
    order = [corpus['conf']['nodes']] + [parsed[2] for parsed in corpus['conf']['includes']]
    for blocks in order:
        for ref, entries in blocks:
            node = resolve_ref(ref, None, corpus['nodes'], corpus['alias'], corpus['follow'],
                               corpus['pop_alias'])
            if node is None:
                continue
            locations = [entry for entry in entries if entry[0] == 'loc']
            if locations:
                out[node].extend(locations)
    return out


def pair_policy(corpus, node, prop, hw_class, applied, node_blocks, node_paths):
    """Effective layered policy of a (node, property) pair."""
    policy = new_policy()
    apply_entries(policy, corpus['conf']['global'])
    catalog_path = corpus['catalog'].get(prop)
    for cls, entries in corpus['conf']['classes']:
        if cls != hw_class:
            continue
        for entry in entries:
            if entry[0] == 'loc' and entry[1] == catalog_path:
                apply_entries(policy, entry[2])
    for entry in applied['class'].get((hw_class, prop), []):
        apply_amendment(policy, entry['field'], entry['value'])
    own_path = None
    for section in node_paths.get(node, []):
        for key, value in section.items():
            if prop_name(key, corpus['aliases'], corpus['catalog'], corpus['oldnames']) == prop:
                own_path = value
    if own_path is None:
        own_path = catalog_path
    for entry in node_blocks.get(node, []):
        if entry[1] == own_path:
            apply_entries(policy, entry[2])
    for entry in applied['node'].get((node, prop), []):
        apply_amendment(policy, entry['field'], entry['value'])
    return policy


def coarser(a, b):
    return a if REFRESH_ORDER[a] >= REFRESH_ORDER[b] else b


def footprint(policy, daily, ratio):
    """(cycle_bytes, hot_kib, stale_kib, peak_kib) for a pair with a daily volume."""
    if daily is None:
        return (None, None, None, None)
    cycle = round_half_even(daily * REFRESH_FACTOR[policy['effective_refresh']])
    generation = -((-cycle) // ratio) if ratio > 0 else cycle
    store = bool(policy['store_compressed'])
    hot_raw = bool(policy['hot_raw'])
    hot = generation if (store and not hot_raw) else cycle
    stale_count = max(int(policy['versions']) - 1, 0)
    stale = stale_count * generation if store else stale_count * cycle
    peak = hot + stale + cycle
    return (cycle, to_kib(hot), to_kib(stale), to_kib(peak))


def load_changes(data_dir, corpus):
    """Read the change register, the CAB minutes and the tuning proposals."""
    decisions = collections.defaultdict(list)
    for line in read_text(need_file(data_dir, 'cab_minutes.md')).split('\n'):
        m = re.match(r'^\|\s*([^|]+?)\s*\|\s*(CR-\d+)\s*\|\s*([^|]+?)\s*\|', line)
        if not m:
            continue
        moment = to_epoch(m.group(1))
        if moment is None:
            continue
        decisions[m.group(2)].append((moment, m.group(3).strip().lower()))
    proposals = {}
    for line in read_text(need_file(data_dir, 'tuning_drafts.jsonl')).split('\n'):
        if not line.strip():
            continue
        item = json.loads(line)
        proposals[item.get('proposal')] = item
    out = []
    for line in read_text(need_file(data_dir, 'cr_export.jsonl')).split('\n'):
        if not line.strip():
            continue
        item = json.loads(line)
        change = item.get('change')
        status = item.get('status', '').strip().lower()
        chosen = None
        for index, (moment, decision) in enumerate(decisions.get(change, [])):
            if moment is None or moment > CUT_E:
                continue
            if decision not in ('approved', 'approve', 'rejected', 'reject'):
                continue
            if chosen is None or moment >= chosen[0]:
                chosen = (moment, decision)
        if chosen is not None:
            status = chosen[1]
        value = item.get('value')
        if value is None and item.get('value_ref'):
            value = proposals.get(item['value_ref'], {}).get('value')
        out.append({
            'id': change,
            'scope': item.get('scope', '').strip().lower(),
            'target': item.get('target', ''),
            'property': item.get('property', ''),
            'field': item.get('field', '').strip().lower(),
            'value': value,
            'status': status,
            'effective': to_epoch(item.get('effective')),
        })
    return out


# --------------------------------------------------------------------------
# phase 1
# --------------------------------------------------------------------------

def phase1(data_dir, out_dir):
    need_dir(data_dir)
    corpus = load_directory(data_dir)
    for code, table in corpus['pops'].items():
        table['_offset_min'] = offset_minutes(table.get('utc_offset', '+00:00'))
        table['_shield_kib'] = size_bytes(table.get('shield_pool', '0'))
        table['_spill_kib'] = size_bytes(table.get('spill_budget', '0'))
        table['_quota'] = whole_number(table.get('ticket_quota', '0'))
        table['_pin_pct'] = whole_percent(table.get('ram_pin_pct', '0'))

    node_pop = place_nodes(corpus)
    served = {}
    templates = class_templates(corpus)
    hw_class_of = {}
    in_scope = set()
    tier_of = {}
    mem_of = {}
    for node in corpus['nodes']:
        status_row = corpus['status'].get(node)
        if status_row is None or status_row[0] not in IN_SCOPE_STATUS:
            continue
        pop = node_pop.get(node)
        if pop is None or pop not in corpus['pops']:
            continue
        if corpus['pops'][pop].get('scope', '').strip().lower() != 'prod':
            continue
        if any(moment <= CUT_E and state == 'confirmed'
               for moment, state in corpus['decom'].get(node, [])):
            continue
        hw_class = corpus['class'].get(node)
        if hw_class is None or hw_class == 'retired':
            continue
        tier = corpus['tier_node'].get(node, corpus['tier_class'].get(hw_class))
        if tier is None or tier == 'x':
            continue
        served[node] = served_properties(corpus, node, hw_class, templates)
        hw_class_of[node] = hw_class
        tier_of[node] = tier
        mem_of[node] = mem_bytes(status_row[1])
        if any((node, prop) in corpus['prod'] for prop in served[node]):
            in_scope.add(node)

    applied, pending = classify_changes(corpus, in_scope, served, hw_class_of)
    node_blocks = node_block_map(corpus)

    pairs = sorted((node, prop) for node in in_scope for prop in served[node]
                   if (node, prop) in corpus['prod'])
    pairs_of_node = collections.defaultdict(list)
    for node, prop in pairs:
        pairs_of_node[node].append(prop)
    readings = collect_readings(corpus, node_pop)

    usage_base, usage_after = usage_of_node(corpus)

    node_rows = []
    prop_rows = []
    policy_rows = []
    foot_rows = []
    pair_state = {}
    for node in sorted(in_scope):
        pop = node_pop[node]
        media, usable = corpus['disk'].get(node, (None, None))
        base = usage_base.get(node)
        after = usage_after.get(node)
        prior = corpus['prior_peak'].get(node)
        sweep = corpus['sweep'].get(node, 'daily')
        node_rows.append([node, pop, hw_class_of[node], tier_of[node],
                          media if media else '', num(usable), num(base), num(after),
                          num(prior), sweep, num(mem_of[node])])
        for prop in pairs_of_node[node]:
            info = corpus['prod'][(node, prop)]
            series = readings.get((node, prop), [])
            daily = daily_volume(series, info['unit'])
            prop_rows.append([node, prop, info['instance'], str(len(series)), num(daily)])
            policy = pair_policy(corpus, node, prop, hw_class_of[node], applied,
                                 node_blocks, corpus['node_paths'])
            policy['effective_refresh'] = coarser(policy['refresh'], sweep)
            ctype = corpus['types'].get(prop, '')
            ratio = corpus['ratios'].get((ctype, policy['codec']))
            pair_state[(node, prop)] = {'policy': policy, 'daily': daily, 'ratio': ratio}
            cycle, hot, stale, peak = footprint(policy, daily, ratio)
            policy_rows.append([node, prop, num(policy['versions']), policy['refresh'],
                                policy['effective_refresh'],
                                boolean(policy['store_compressed']), boolean(policy['hot_raw']),
                                policy['codec'] + ':' + str(policy['level']),
                                dec(ratio, 2)])
            foot_rows.append([node, prop, num(cycle), num(hot), num(stale), num(peak)])

    os.makedirs(out_dir, exist_ok=True)
    write_csv(os.path.join(out_dir, 'nodes.csv'),
              ['node_id', 'pop', 'class', 'tier', 'media', 'usable_bytes', 'base_used_bytes',
               'post_cut_used_bytes', 'prior_peak_kib', 'sweep_interval', 'ram_bytes'], node_rows)
    write_csv(os.path.join(out_dir, 'properties.csv'),
              ['node_id', 'property', 'instance', 'samples', 'daily_bytes'], prop_rows)
    write_csv(os.path.join(out_dir, 'policies.csv'),
              ['node_id', 'property', 'versions', 'refresh', 'effective_refresh',
               'store_compressed', 'hot_raw', 'codec', 'ratio'], policy_rows)
    write_csv(os.path.join(out_dir, 'footprints.csv'),
              ['node_id', 'property', 'cycle_bytes', 'hot_kib', 'stale_kib', 'peak_kib'], foot_rows)

    write_json(os.path.join(out_dir, 'pending.json'), pending_json(pending))
    write_json(os.path.join(out_dir, 'pops.json'), pops_json(corpus, in_scope, node_pop, mem_of))
    return {'corpus': corpus, 'pair_state': pair_state, 'in_scope': in_scope,
            'node_pop': node_pop, 'hw_class_of': hw_class_of, 'pending': pending}


def place_nodes(corpus):
    """node -> pop code, latest installed placement at or before the cut."""
    best = {}
    for key in sorted(corpus['placements']):
        entry = corpus['placements'][key]
        if entry.get('state', '').strip().lower() != 'installed':
            continue
        moment = to_epoch(entry.get('since'))
        if moment is None or moment > CUT_E:
            continue
        node = resolve_ref(entry.get('node'), None, corpus['nodes'], corpus['alias'],
                          corpus['follow'], corpus['pop_alias'])
        if node is None:
            continue
        candidate = (moment, key)
        if node not in best or candidate > best[node][0]:
            best[node] = (candidate, entry.get('pop', '').strip().lower())
    out = {}
    for node, (_key, pop) in best.items():
        code = corpus['pop_alias'].get(pop, pop)
        if code in corpus['pops']:
            out[node] = code
    return out


def usage_of_node(corpus):
    """Base and post-cut cache usage in bytes per node."""
    base = {}
    after = {}
    for moment, _name, node, cmd, fields in corpus['usage']:
        if fields is None:
            continue
        if moment <= CUT_E:
            if node not in base or moment >= base[node][0]:
                base[node] = (moment, usage_bytes(fields, cmd))
        else:
            if node not in after or moment < after[node][0]:
                after[node] = (moment, usage_bytes(fields, cmd))
    return ({n: v[1] for n, v in base.items()}, {n: v[1] for n, v in after.items()})


def amendment_value(field, value):
    """Normalise an amendment value to the contract's JSON type."""
    field = (field or '').strip().lower()
    if field == 'versions':
        return int(str(value).strip())
    if field == 'refresh':
        return str(value).strip().lower()
    if field in ('store_compressed', 'hot_raw'):
        return parse_flag(value)
    return str(value).strip().lower()


def pending_json(pending):
    entries = []
    for change in pending:
        entries.append({
            'id': change['id'],
            'scope': change['scope'],
            'node_id': change['key'] if change['scope_kind'] == 'node' else None,
            'class': change['key'] if change['scope_kind'] == 'class' else None,
            'property': change['prop'],
            'field': change['field'],
            'value': amendment_value(change['field'], change['value']),
            'effective_utc': iso_utc(change['effective']),
        })
    return {'freeze_utc': FREEZE_UTC, 'amendments': entries}


def pops_json(corpus, in_scope, node_pop, mem_of):
    pops = []
    for code in sorted(corpus['pops']):
        table = corpus['pops'][code]
        if table.get('scope', '').strip().lower() != 'prod':
            continue
        nodes = [n for n in in_scope if node_pop.get(n) == code]
        pin_budget = 0
        for node in nodes:
            pin_budget += to_kib(mem_of[node]) * table['_pin_pct'] // 100
        pops.append({
            'pop': code,
            'utc_offset_minutes': table['_offset_min'],
            'shield_pool_kib': table['_shield_kib'],
            'ticket_quota': table['_quota'],
            'spill_budget_kib': table['_spill_kib'],
            'ram_pin_pct': table['_pin_pct'],
            'pin_budget_kib': pin_budget,
            'nodes': len(nodes),
        })
    return {'pops': pops}




# --------------------------------------------------------------------------
# reading phase 1 outputs
# --------------------------------------------------------------------------

def read_csv_rows(base, name, header):
    path = need_file(base, name)
    text = read_text(path)
    lines = text.split('\n')
    if not lines or lines[0] != ','.join(header) or not text.endswith('\n'):
        raise UpstreamError(path)
    out = []
    for line in lines[1:]:
        if line == '':
            continue
        fields = line.split(',')
        if len(fields) != len(header):
            raise UpstreamError(path)
        out.append(fields)
    return out


def as_int(text):
    return None if text == '' else int(text)


def as_ratio(text):
    return None if text == '' else Fraction(text)


def load_p1(p1_dir):
    need_dir(p1_dir)
    nodes = read_csv_rows(p1_dir, 'nodes.csv',
                          ['node_id', 'pop', 'class', 'tier', 'media', 'usable_bytes',
                           'base_used_bytes', 'post_cut_used_bytes', 'prior_peak_kib',
                           'sweep_interval', 'ram_bytes'])
    props = read_csv_rows(p1_dir, 'properties.csv',
                          ['node_id', 'property', 'instance', 'samples', 'daily_bytes'])
    pol = read_csv_rows(p1_dir, 'policies.csv',
                        ['node_id', 'property', 'versions', 'refresh', 'effective_refresh',
                         'store_compressed', 'hot_raw', 'codec', 'ratio'])
    feet = read_csv_rows(p1_dir, 'footprints.csv',
                         ['node_id', 'property', 'cycle_bytes', 'hot_kib', 'stale_kib', 'peak_kib'])
    pending = json.loads(read_text(need_file(p1_dir, 'pending.json')))
    pops = json.loads(read_text(need_file(p1_dir, 'pops.json')))
    return {'nodes': nodes, 'props': props, 'policies': pol, 'feet': feet,
            'pending': pending, 'pops': pops}


def load_p2(p2_dir):
    need_dir(p2_dir)
    pop_rollup = read_csv_rows(p2_dir, 'pop_rollup.csv',
                               ['pop', 'nodes', 'measured_pairs', 'null_pairs', 'compressed_pairs',
                                'peak_mib', 'usable_mib', 'headroom_mib', 'pending_nodes',
                                'shield_mib'])
    class_rollup = read_csv_rows(p2_dir, 'class_rollup.csv',
                                 ['class', 'nodes', 'pops', 'daily_mib', 'mean_ratio', 'peak_mib',
                                  'pending_pairs', 'shield_share_mib'])
    shield = read_csv_rows(p2_dir, 'shield_alloc.csv',
                           ['node_id', 'pop', 'demand_kib', 'granted_kib', 'cumulative_kib', 'state'])
    pins = read_csv_rows(p2_dir, 'pin_plan.csv',
                         ['node_id', 'property', 'density', 'hot_kib', 'cumulative_kib', 'pinned'])
    risk = read_csv_rows(p2_dir, 'risk_rank.csv',
                         ['node_id', 'pop', 'headroom_kib', 'daily_kib', 'days_to_full',
                          'full_date_local', 'pin_share', 'pending', 'rank'])
    manifest = json.loads(read_text(need_file(p2_dir, 'manifest.json')))
    return {'pop_rollup': pop_rollup, 'class_rollup': class_rollup, 'shield': shield,
            'pins': pins, 'risk': risk, 'manifest': manifest}


# --------------------------------------------------------------------------
# phase 2
# --------------------------------------------------------------------------

def phase2(p1_dir, out_dir):
    return run_phase2(load_p1(p1_dir), p1_dir, out_dir)


def pending_effect(pairs, node_class, pending):
    """(node, property) -> the pending amendments affecting the pair, in pending order."""
    by_node = collections.defaultdict(list)
    pairs_of_prop = collections.defaultdict(list)
    pair_set = set(pairs)
    for key in pairs:
        pairs_of_prop[key[1]].append(key)
    affected = collections.defaultdict(list)
    for entry in pending:
        prop = entry['property']
        if entry['scope'] == 'node':
            key = (entry['node_id'], prop)
            if key in pair_set:
                affected[key].append(entry)
        else:
            cls = entry['class']
            for key in pairs_of_prop.get(prop, ()):
                if node_class[key[0]] == cls:
                    affected[key].append(entry)
    return affected


def run_phase2(p1, p1_dir, out_dir):
    node_order = [row[0] for row in p1['nodes']]
    pops = p1['pops']['pops']
    pending = p1['pending']['amendments']

    per_node = {}
    for row in p1['nodes']:
        per_node[row[0]] = {
            'pop': row[1], 'class': row[2], 'tier': as_int(row[3]),
            'usable_kib': to_kib(as_int(row[5])), 'base_kib': to_kib(as_int(row[6])),
            'post_kib': None if row[7] == '' else to_kib(as_int(row[7])),
            'sweep': row[9], 'ram_kib': to_kib(as_int(row[10])),
            'peak': 0, 'daily_bytes': 0, 'daily_seen': False, 'hot_total': 0,
            'demand': 0, 'measured': False, 'pairs': 0, 'compressed': 0,
        }
    node_class = {row[0]: row[2] for row in p1['nodes']}
    pairs = [(row[0], row[1]) for row in p1['props']]
    prop_daily = {(row[0], row[1]): as_int(row[4]) for row in p1['props']}
    policy_of = {(row[0], row[1]): row for row in p1['policies']}
    foot_of = {(row[0], row[1]): row for row in p1['feet']}

    affected = pending_effect(pairs, node_class, pending)
    pending_nodes = {node for (node, _prop) in affected}

    for (node, prop) in pairs:
        info = per_node[node]
        info['pairs'] += 1
        daily = prop_daily[(node, prop)]
        if daily is None:
            continue
        info['measured'] = True
        info['daily_seen'] = True
        info['daily_bytes'] += daily
        foot = foot_of[(node, prop)]
        info['peak'] += as_int(foot[5]) or 0
        info['hot_total'] += as_int(foot[3]) or 0
        if policy_of[(node, prop)][5] == '1':
            info['compressed'] += 1
            stale = foot_of[(node, prop)][4]
            if stale != '':
                info['demand'] += as_int(stale)
    for node, info in per_node.items():
        info['daily_kib'] = to_kib(info['daily_bytes']) if info['daily_seen'] else None
        info['headroom'] = info['usable_kib'] - info['base_kib'] - info['peak']
        info['pending'] = node in pending_nodes

    pop_nodes = collections.defaultdict(list)
    for node, info in per_node.items():
        pop_nodes[info['pop']].append(node)

    pop_rows = []
    pop_peak_kib = {}
    for entry in pops:
        code = entry['pop']
        members = pop_nodes.get(code, [])
        pop_peak_kib[code] = sum(per_node[n]['peak'] for n in members)
        measured = nulls = compressed = 0
        for (node, prop) in pairs:
            if node not in members:
                continue
            if prop_daily[(node, prop)] is None:
                nulls += 1
            else:
                measured += 1
            if policy_of[(node, prop)][5] == '1':
                compressed += 1
        usable = sum(per_node[n]['usable_kib'] for n in members)
        headroom = sum(per_node[n]['headroom'] for n in members)
        pend = sum(1 for n in members if per_node[n]['pending'])
        pop_rows.append([code, str(len(members)), str(measured), str(nulls), str(compressed),
                         num(to_mib(pop_peak_kib[code])), num(to_mib(usable)),
                         num(to_mib(headroom)), str(pend), num(to_mib(entry['shield_pool_kib']))])

    class_members = collections.defaultdict(list)
    for node, info in per_node.items():
        class_members[info['class']].append(node)
    class_rows = []
    for cls in sorted(class_members):
        members = class_members[cls]
        measured_bytes = 0
        seen = False
        ratios = []
        for (node, prop) in pairs:
            if node not in members:
                continue
            daily = prop_daily[(node, prop)]
            if daily is not None:
                seen = True
                measured_bytes += daily
            if policy_of[(node, prop)][5] == '1':
                ratios.append(as_ratio(policy_of[(node, prop)][8]))
        pops_of_class = sorted({per_node[n]['pop'] for n in members})
        pending_pairs = sum(1 for key in affected if key[0] in members)
        share = Fraction(0)
        for code, peak in pop_peak_kib.items():
            if peak <= 0:
                continue
            pool = next(e['shield_pool_kib'] for e in pops if e['pop'] == code)
            cls_at_pop = sum(per_node[n]['peak'] for n in members if per_node[n]['pop'] == code)
            share += Fraction(pool) * Fraction(cls_at_pop, peak)
        class_rows.append([cls, str(len(members)), str(len(pops_of_class)),
                           num(round_half_even(measured_bytes, 1048576)) if seen else '',
                           dec(sum(ratios) / len(ratios), 3) if ratios else '',
                           num(to_mib(sum(per_node[n]['peak'] for n in members))),
                           str(pending_pairs), num(to_mib(share))])

    order_index = {node: i for i, node in enumerate(node_order)}
    shield_rows = []
    for entry in pops:
        code = entry['pop']
        members = sorted(pop_nodes.get(code, []),
                         key=lambda n: (per_node[n]['tier'],
                                        0 if not per_node[n]['pending'] else 1, order_index[n]))
        remaining = entry['shield_pool_kib']
        cumulative = 0
        for node in members:
            info = per_node[node]
            if not info['measured']:
                shield_rows.append([node, code, '0', '0', str(cumulative), 'unmeasured'])
                continue
            demand = info['demand']
            grant = demand if demand < remaining else remaining
            if grant < 0:
                grant = 0
            remaining -= grant
            cumulative += grant
            if demand == 0:
                state = 'zero'
            elif grant == demand:
                state = 'full'
            elif grant > 0:
                state = 'partial'
            else:
                state = 'none'
            shield_rows.append([node, code, str(demand), str(grant), str(cumulative), state])

    pin_rows = []
    pinned_kib = {}
    for node in node_order:
        info = per_node[node]
        pct = next(e['ram_pin_pct'] for e in pops if e['pop'] == info['pop'])
        budget = info['ram_kib'] * pct // 100
        candidates = []
        for (n, prop) in pairs:
            if n != node:
                continue
            daily = prop_daily[(n, prop)]
            if daily is None:
                continue
            if policy_of[(n, prop)][4] == 'hourly':
                continue
            if affected.get((n, prop)):
                continue
            hot = as_int(foot_of[(n, prop)][3]) or 0
            candidates.append((prop, hot, daily))
        zero = sorted([c for c in candidates if c[1] == 0], key=lambda c: c[0])
        rest = sorted([c for c in candidates if c[1] > 0],
                      key=lambda c: (-Fraction(c[2], c[1]), c[0]))
        cumulative = 0
        for prop, hot, daily in zero + rest:
            if cumulative + hot <= budget:
                pinned = '1'
                cumulative += hot
            else:
                pinned = '0'
            pin_rows.append([node, prop, dec(Fraction(daily, hot), 2) if hot else '',
                             str(hot), str(cumulative), pinned])
        pinned_kib[node] = cumulative

    days_of = {}
    for node in node_order:
        info = per_node[node]
        if info['daily_kib'] is None:
            days = None
        elif info['daily_kib'] == 0:
            days = 'never'
        elif info['headroom'] <= 0:
            days = Fraction(0)
        else:
            days = Fraction(info['headroom'], info['daily_kib'])
        days_of[node] = days
        info['days'] = days
    ordered_nodes = sorted(node_order, key=lambda n: (days_sort_key(days_of[n]), n))
    rank_of = {node: index + 1 for index, node in enumerate(ordered_nodes)}
    rank_rows = []
    for node in node_order:
        info = per_node[node]
        days = info['days']
        offset = next(e['utc_offset_minutes'] for e in pops if e['pop'] == info['pop'])
        if isinstance(days, Fraction):
            days_text = dec(days, 2)
            date_text = local_date(days, offset)
        elif days == 'never':
            days_text = 'never'
            date_text = ''
        else:
            days_text = ''
            date_text = ''
        share = dec(Fraction(pinned_kib[node], info['hot_total']), 4) if info['hot_total'] else ''
        rank_rows.append([node, info['pop'], str(info['headroom']),
                          '' if info['daily_kib'] is None else str(info['daily_kib']),
                          days_text, date_text, share,
                          '1' if info['pending'] else '0', str(rank_of[node])])
    rank_rows.sort(key=lambda row: int(row[8]))

    numeric = sorted(d for d in days_of.values() if isinstance(d, Fraction))
    if not numeric:
        median = None
    elif len(numeric) % 2 == 1:
        median = dec(numeric[len(numeric) // 2], 2)
    else:
        median = dec((numeric[len(numeric) // 2 - 1] + numeric[len(numeric) // 2]) / 2, 2)
    headrooms = sorted(info['headroom'] for info in per_node.values())
    p90 = headrooms[-(-9 * len(headrooms) // 10) - 1] if headrooms else None

    totals = {
        'nodes': len(node_order),
        'pairs_measured': sum(1 for key in pairs if prop_daily[key] is not None),
        'pairs_null': sum(1 for key in pairs if prop_daily[key] is None),
        'pairs_compressed': sum(1 for key in pairs if policy_of[key][5] == '1'),
        'peak_kib': sum(info['peak'] for info in per_node.values()),
        'daily_kib': to_kib(sum(info['daily_bytes'] for info in per_node.values())),
        'pending_amendments': len(pending),
        'shield_kib': sum(e['shield_pool_kib'] for e in pops),
        'pinned_kib': sum(pinned_kib.values()),
    }
    manifest = {
        'phase': 2,
        'inputs': {name: sha256_file(os.path.join(p1_dir, name)) for name in P1_FILES},
        'totals': totals,
        'median_days_to_full': median,
        'p90_headroom_kib': p90,
    }

    os.makedirs(out_dir, exist_ok=True)
    write_csv(os.path.join(out_dir, 'pop_rollup.csv'),
              ['pop', 'nodes', 'measured_pairs', 'null_pairs', 'compressed_pairs', 'peak_mib',
               'usable_mib', 'headroom_mib', 'pending_nodes', 'shield_mib'], pop_rows)
    write_csv(os.path.join(out_dir, 'class_rollup.csv'),
              ['class', 'nodes', 'pops', 'daily_mib', 'mean_ratio', 'peak_mib', 'pending_pairs',
               'shield_share_mib'], class_rows)
    write_csv(os.path.join(out_dir, 'shield_alloc.csv'),
              ['node_id', 'pop', 'demand_kib', 'granted_kib', 'cumulative_kib', 'state'],
              shield_rows)
    write_csv(os.path.join(out_dir, 'pin_plan.csv'),
              ['node_id', 'property', 'density', 'hot_kib', 'cumulative_kib', 'pinned'], pin_rows)
    write_csv(os.path.join(out_dir, 'risk_rank.csv'),
              ['node_id', 'pop', 'headroom_kib', 'daily_kib', 'days_to_full', 'full_date_local',
               'pin_share', 'pending', 'rank'], rank_rows)
    write_json(os.path.join(out_dir, 'manifest.json'), manifest)
    return {'p1': p1, 'per_node': per_node, 'pairs': pairs, 'prop_daily': prop_daily,
            'affected': affected, 'pinned_kib': pinned_kib, 'rank_of': rank_of,
            'days_of': days_of, 'manifest': manifest}


def local_date(days, offset_minutes):
    """PoP-local date of the cut plus `days` days."""
    total = Fraction(round(CUT_E)) + Fraction(days) * 86400 + offset_minutes * 60
    moment = datetime.datetime.fromtimestamp(int(total // 1), datetime.timezone.utc)
    return moment.strftime('%Y-%m-%d')


def days_sort_key(days):
    if isinstance(days, Fraction):
        return (0, days)
    if days == 'never':
        return (1, Fraction(0))
    return (2, Fraction(0))


# --------------------------------------------------------------------------
# phase 3
# --------------------------------------------------------------------------

def phase3(p1_dir, p2_dir, out_dir):
    p1 = load_p1(p1_dir)
    p2 = load_p2(p2_dir)
    manifest_path = os.path.join(p2_dir, 'manifest.json')
    if p2['manifest'].get('phase') != 2:
        raise UpstreamError(manifest_path)
    expect = {name: sha256_file(os.path.join(p1_dir, name)) for name in P1_FILES}
    if p2['manifest'].get('inputs') != expect:
        raise UpstreamError(manifest_path)
    return run_phase3(p1, p2, p1_dir, p2_dir, out_dir)


def run_phase3(p1, p2, p1_dir, p2_dir, out_dir):
    node_order = [row[0] for row in p1['nodes']]
    node_row = {row[0]: row for row in p1['nodes']}
    pops = p1['pops']['pops']
    pending = p1['pending']['amendments']

    prop_daily = {(row[0], row[1]): as_int(row[4]) for row in p1['props']}
    policy_of = {(row[0], row[1]): row for row in p1['policies']}
    foot_of = {(row[0], row[1]): row for row in p1['feet']}
    pairs = sorted(prop_daily)

    affected = pending_effect(pairs, {row[0]: row[2] for row in p1['nodes']}, pending)

    grant_of = {row[0]: as_int(row[3]) or 0 for row in p2['shield']}
    shield_granted = collections.defaultdict(int)
    for row in p2['shield']:
        shield_granted[row[1]] += as_int(row[3]) or 0
    pinned_of = collections.defaultdict(int)
    for row in p2['pins']:
        if row[5] == '1':
            pinned_of[row[0]] += as_int(row[3])
    daily_of = {row[0]: as_int(row[3]) for row in p2['risk']}
    rank_of = {row[0]: as_int(row[8]) for row in p2['risk']}
    median = p2['manifest']['median_days_to_full']
    median_value = Fraction(median) if median is not None else None
    p90 = p2['manifest']['p90_headroom_kib']
    pop_headroom_mib = {row[0]: as_ratio(row[7]) for row in p2['pop_rollup']}
    class_peak_mib = {row[0]: as_ratio(row[5]) for row in p2['class_rollup']}
    class_order = [row[0] for row in p2['class_rollup']]

    peak_now = {}
    peak_after = {}
    prior_gap = {}
    headroom_after = {}
    days_after = {}
    flags = {}
    pop_share = {}
    class_share = {}
    for node in node_order:
        row = node_row[node]
        usable = to_kib(as_int(row[5]))
        base = to_kib(as_int(row[6]))
        post = None if row[7] == '' else to_kib(as_int(row[7]))
        observed = post if post is not None else base
        prior = as_int(row[8])
        sweep = row[9]
        total_now = 0
        total_after = 0
        for (n, prop) in pairs:
            if n != node:
                continue
            foot = foot_of[(node, prop)]
            total_now += as_int(foot[5]) or 0
            daily = prop_daily[(node, prop)]
            if daily is None:
                total_after += as_int(foot[5]) or 0
                continue
            pol = policy_of[(node, prop)]
            state = {'versions': as_int(pol[2]), 'refresh': pol[3],
                     'store_compressed': pol[5] == '1', 'hot_raw': pol[6] == '1',
                     'codec': pol[7].split(':')[0], 'level': int(pol[7].split(':')[1])}
            for entry in affected.get((node, prop), []):
                apply_amendment(state, entry['field'], entry['value'])
            state['effective_refresh'] = coarser(state['refresh'], sweep)
            _cycle, _hot, _stale, peak = footprint(state, daily, as_ratio(pol[8]))
            total_after += peak or 0
        peak_now[node] = total_now
        peak_after[node] = total_after
        prior_gap[node] = None if prior is None else total_after - prior
        headroom = usable - observed + (grant_of.get(node) or 0) \
            + pinned_of.get(node, 0) - total_after
        headroom_after[node] = headroom
        daily = daily_of.get(node)
        if daily is None:
            days = None
        elif daily == 0:
            days = 'never'
        elif headroom <= 0:
            days = Fraction(0)
        else:
            days = Fraction(headroom, daily)
        days_after[node] = days
        if isinstance(days, Fraction) and median_value is not None and days < median_value:
            flags[node] = 'at-risk'
        elif total_after > total_now:
            flags[node] = 'watch'
        else:
            flags[node] = 'ok'
        offset = next(e['utc_offset_minutes'] for e in pops if e['pop'] == row[1])
        denom = pop_headroom_mib.get(row[1])
        pop_share[node] = dec(Fraction(headroom) / (denom * 1024), 4) \
            if denom is not None and denom > 0 else ''
        cdenom = class_peak_mib.get(row[2])
        class_share[node] = dec(Fraction(total_after) / (cdenom * 1024), 4) \
            if cdenom is not None and cdenom > 0 else ''

    projection_rows = []
    running = 0
    running_min = None
    for node in node_order:
        row = node_row[node]
        days = days_after[node]
        offset = next(e['utc_offset_minutes'] for e in pops if e['pop'] == row[1])
        if isinstance(days, Fraction):
            days_text = dec(days, 2)
            date_text = local_date(days, offset)
        elif days == 'never':
            days_text = 'never'
            date_text = ''
        else:
            days_text = ''
            date_text = ''
        running += headroom_after[node]
        if running_min is None or running < running_min:
            running_min = running
        projection_rows.append([node, row[1], row[2], str(peak_now[node]), str(peak_after[node]),
                                '' if prior_gap[node] is None else str(prior_gap[node]),
                                str(headroom_after[node]), days_text, str(rank_of[node]),
                                flags[node], pop_share[node], class_share[node],
                                date_text, str(running), str(running_min)])

    spill_rows = []
    spill_granted = collections.defaultdict(int)
    deficit_nodes = [n for n in node_order if headroom_after[n] < 0]
    for entry in pops:
        code = entry['pop']
        members = [n for n in deficit_nodes if node_row[n][1] == code]
        pop_headroom = pop_headroom_mib.get(code)

        def class_key(n):
            share = class_share[n]
            return (0, -Fraction(share)) if share != '' else (1, Fraction(0))

        members.sort(key=lambda n: (class_key(n), -(-headroom_after[n]), n))
        remaining = entry['spill_budget_kib']
        for node in members:
            daily = daily_of.get(node)
            daily_text = '' if daily is None else str(daily)
            if as_int(node_row[node][3]) == 3 and pop_headroom is not None and pop_headroom > 0:
                spill_rows.append([node, code, str(-headroom_after[node]), daily_text,
                                  '0', str(remaining), 'deferred'])
                continue
            deficit = -headroom_after[node]
            grant = min(deficit, remaining)
            if p90 is not None and p90 > 0:
                grant = min(grant, p90)
            remaining -= grant
            spill_granted[code] += grant
            if grant == deficit:
                state = 'full'
            elif grant > 0:
                state = 'partial'
            else:
                state = 'none'
            spill_rows.append([node, code, str(deficit), daily_text,
                               str(grant), str(remaining), state])

    at_risk_by_pop = collections.defaultdict(list)
    for node in node_order:
        if flags[node] == 'at-risk':
            at_risk_by_pop[node_row[node][1]].append(node)
    outlook_rows = []
    for entry in pops:
        code = entry['pop']
        members = [n for n in node_order if node_row[n][1] == code]
        pending_here = set()
        for (node, prop) in pairs:
            if node_row[node][1] != code:
                continue
            for e in affected.get((node, prop), []):
                pending_here.add(e['id'])
        values = [days_after[n] for n in members if isinstance(days_after[n], Fraction)]
        worst = ''
        if at_risk_by_pop.get(code):
            totals = collections.defaultdict(Fraction)
            for n in at_risk_by_pop[code]:
                share = class_share[n]
                totals[node_row[n][2]] += Fraction(share) if share != '' else Fraction(0)
            worst = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        outlook_rows.append([code,
                             num(pop_headroom_mib.get(code)),
                             num(to_mib(sum(headroom_after[n] for n in members))),
                             str(len(at_risk_by_pop.get(code, []))),
                             num(to_mib(entry['shield_pool_kib'] - shield_granted[code])),
                             num(to_mib(entry['spill_budget_kib'] - spill_granted[code])),
                             str(len(pending_here)),
                             dec(sum(values) / len(values), 2) if values else '',
                             worst])

    ticket_rows = []
    for entry in pops:
        code = entry['pop']
        quota = entry['ticket_quota']
        pop_headroom = pop_headroom_mib.get(code)
        if pop_headroom is not None and pop_headroom <= 0:
            quota = quota * 2
        members = [n for n in node_order if node_row[n][1] == code
                   and flags[n] in ('at-risk', 'watch')]

        def order_key(n):
            share_c = class_share[n]
            share_p = pop_share[n]
            return (0 if flags[n] == 'at-risk' else 1, days_sort_key(days_after[n]),
                    (0, -Fraction(share_c)) if share_c != '' else (1, Fraction(0)),
                    (0, -Fraction(share_p)) if share_p != '' else (1, Fraction(0)), n)

        members.sort(key=order_key)
        for index, node in enumerate(members[:quota], start=1):
            days = days_after[node]
            if isinstance(days, Fraction):
                days_text = dec(days, 2)
            elif days == 'never':
                days_text = 'never'
            else:
                days_text = ''
            ticket_rows.append(['T-%s-%02d' % (code, index), code, node, flags[node],
                                days_text, str(rank_of[node])])

    class_members = collections.defaultdict(list)
    for node in node_order:
        class_members[node_row[node][2]].append(node)
    drift_rows = []
    for cls in class_order:
        members = class_members.get(cls, [])
        now = class_peak_mib.get(cls)
        after_mib = to_mib(sum(peak_after[n] for n in members))
        gaps = [prior_gap[n] for n in members if prior_gap[n] is not None]
        shares = [Fraction(pop_share[n]) for n in members if pop_share[n] != '']
        share_after = Fraction(0)
        for code in pop_headroom_mib:
            pop_total = sum(peak_after[n] for n in node_order if node_row[n][1] == code)
            if pop_total <= 0:
                continue
            pool = next(e['shield_pool_kib'] for e in pops if e['pop'] == code)
            cls_at = sum(peak_after[n] for n in members if node_row[n][1] == code)
            share_after += Fraction(pool) * Fraction(cls_at, pop_total)
        drift_rows.append([cls, num(now), num(after_mib),
                           num(after_mib - now) if now is not None else '',
                           num(to_mib(sum(gaps))) if gaps else '',
                           str(sum(1 for n in members if flags[n] == 'at-risk')),
                           dec(sum(shares) / len(shares), 4) if shares else '',
                           num(to_mib(share_after))])

    totals = {
        'nodes': len(node_order),
        'at_risk': sum(1 for n in node_order if flags[n] == 'at-risk'),
        'watch': sum(1 for n in node_order if flags[n] == 'watch'),
        'peak_after_kib': sum(peak_after.values()),
        'headroom_after_kib': sum(headroom_after.values()),
        'spill_granted_kib': sum(as_int(row[4]) or 0 for row in spill_rows),
        'tickets': len(ticket_rows),
        'pending_applied': len({e['id'] for key in pairs for e in affected.get(key, [])}),
    }
    inputs = {}
    for name in P1_FILES:
        inputs['p1/' + name] = sha256_file(os.path.join(p1_dir, name))
    for name in P2_FILES:
        inputs['p2/' + name] = sha256_file(os.path.join(p2_dir, name))
    chain = '0' * 64
    for row in projection_rows:
        chain = hashlib.sha256((chain + ','.join(row)).encode('utf-8')).hexdigest()

    os.makedirs(out_dir, exist_ok=True)
    write_csv(os.path.join(out_dir, 'projection.csv'),
              ['node_id', 'pop', 'class', 'peak_now_kib', 'peak_after_kib', 'prior_gap_kib',
               'headroom_after_kib', 'days_after', 'rank_before', 'flag', 'pop_share',
               'class_peak_share', 'full_date_after', 'running_kib', 'running_min_kib'],
              projection_rows)
    write_csv(os.path.join(out_dir, 'pop_outlook.csv'),
              ['pop', 'headroom_mib_now', 'headroom_mib_after', 'at_risk_nodes',
               'shield_left_mib', 'spill_left_mib', 'pending_applied', 'mean_days_after',
               'worst_class'], outlook_rows)
    write_csv(os.path.join(out_dir, 'spill_alloc.csv'),
              ['node_id', 'pop', 'deficit_kib', 'daily_kib', 'granted_kib', 'remaining_kib',
               'state'], spill_rows)
    write_csv(os.path.join(out_dir, 'tickets.csv'),
              ['ticket', 'pop', 'node_id', 'flag', 'days_after', 'rank_before'], ticket_rows)
    write_csv(os.path.join(out_dir, 'class_drift.csv'),
              ['class', 'peak_mib_now', 'peak_mib_after', 'drift_mib', 'prior_gap_mib',
               'at_risk_nodes', 'mean_pop_share', 'shield_share_after_mib'], drift_rows)
    write_json(os.path.join(out_dir, 'manifest.json'),
               {'phase': 3, 'inputs': inputs, 'totals': totals, 'chain': chain})
    return {'totals': totals}


# --------------------------------------------------------------------------
# command line
# --------------------------------------------------------------------------

def main(argv):
    if len(argv) < 1:
        raise UsageError('missing subcommand')
    command = argv[0]
    if command == 'phase1':
        if len(argv) != 3:
            raise UsageError('phase1 <DATA_DIR> <P1_DIR>')
        phase1(argv[1], argv[2])
    elif command == 'phase2':
        if len(argv) != 3:
            raise UsageError('phase2 <P1_DIR> <P2_DIR>')
        phase2(argv[1], argv[2])
    elif command == 'phase3':
        if len(argv) != 4:
            raise UsageError('phase3 <P1_DIR> <P2_DIR> <P3_DIR>')
        phase3(argv[1], argv[2], argv[3])
    else:
        raise UsageError('unknown subcommand ' + command)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except UsageError as exc:
        print('error: usage: ' + str(exc), file=sys.stderr)
        sys.exit(2)
    except UpstreamError as exc:
        print('error: upstream: ' + str(exc), file=sys.stderr)
        sys.exit(3)
