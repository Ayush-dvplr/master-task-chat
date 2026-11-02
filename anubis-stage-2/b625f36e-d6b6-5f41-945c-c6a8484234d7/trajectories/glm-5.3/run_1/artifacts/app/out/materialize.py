#!/usr/bin/env python3
"""Materialize the Marrowgate interval settlement ledger from delivered batches.

Usage: materialize.py --data <corpus directory> --out <destination directory>

Everything the run depends on is read from the corpus directory and nothing
else is read. Only the Python standard library is used.
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_EVEN

FIELD_NAMES = [
    'event_key', 'revision_no', 'revision_class', 'site_ref', 'meter_id',
    'occurred_at', 'ingested_at', 'quantity', 'delta_flag', 'supersedes_revision',
]

LEGACY_WIDTHS = [12, 4, 12, 16, 10, 22, 22, 14, 2, 4]

REVISION_CLASSES = ['ORIGINAL', 'AMENDMENT', 'CORRECTION', 'RESTATEMENT', 'REVERSAL']
CLASS_RANK = {'ORIGINAL': 0, 'AMENDMENT': 1, 'CORRECTION': 2, 'REVERSAL': 3, 'RESTATEMENT': 4}

KWH_GRAMMAR = re.compile(r'^[+-]?[0-9]+(?:\.[0-9]+)?$')
WH_GRAMMAR = re.compile(r'^[+-]?[0-9]+$')
ASCII_DIGITS = re.compile(r'^[0-9]+$')
Z_FORM = re.compile(r'^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})Z$')
OFFSET_FORM = re.compile(
    r'^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})'
    r'([+-])([0-9]{2}):([0-9]{2})$')

DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

CALENDAR_LINE = re.compile(
    r'^([0-9]{8})\s+opens\s+([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)$')

CONFIG_LAYERS = ['settlement_defaults.ini', 'network_policy.conf', 'site_overrides.properties']

PARTITION_COLUMNS = ['sequence_no', 'event_key', 'canonical_site', 'zone',
                      'tariff_band', 'outcome', 'quantity_wh']


# --------------------------------------------------------------------------- #
# text helpers
# --------------------------------------------------------------------------- #

def read_text(path):
    with open(path, 'rb') as handle:
        raw = handle.read()
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]
    return raw.decode('utf-8')


def split_lines(text):
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    return [line[:-1] if line.endswith('\r') else line for line in lines]


def read_delimited(path, delimiter):
    """Read a header and body rows mapping field name to the delivered characters."""
    lines = split_lines(read_text(path))
    header = lines[0].split(delimiter)
    body = []
    for line in lines[1:]:
        parts = line.split(delimiter)
        row = {}
        for index, name in enumerate(header):
            row[name] = parts[index] if index < len(parts) else ''
        body.append(row)
    return body


def read_csv_rows(path):
    if not os.path.exists(path):
        return []
    lines = split_lines(read_text(path))
    if not lines:
        return []
    header = lines[0].split(',')
    rows = []
    for line in lines[1:]:
        parts = line.split(',')
        row = {}
        for index, name in enumerate(header):
            row[name] = parts[index] if index < len(parts) else ''
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- #
# instants
# --------------------------------------------------------------------------- #

def is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def days_in_month(year, month):
    if month == 2 and is_leap(year):
        return 29
    return DAYS_IN_MONTH[month - 1]


def days_from_civil(year, month, day):
    y = year - 1
    return (y * 365 + y // 4 - y // 100 + y // 400
            + sum(days_in_month(year, m) for m in range(1, month)) + day - 1)


def parse_instant(text):
    """Parse a written instant into a UTC instant, or None when it is not one.

    The instant is an integer count of seconds from 0001-01-01T00:00:00Z.
    """
    match = Z_FORM.match(text)
    offset_seconds = 0
    if match is None:
        match = OFFSET_FORM.match(text)
        if match is None:
            return None
        sign = -1 if match.group(7) == '-' else 1
        offset_seconds = sign * (int(match.group(8)) * 3600 + int(match.group(9)) * 60)
    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
    hour, minute, second = int(match.group(4)), int(match.group(5)), int(match.group(6))
    if month < 1 or month > 12:
        return None
    if day < 1 or day > days_in_month(year, month):
        return None
    if hour > 23 or minute > 59 or second > 59:
        return None
    total = days_from_civil(year, month, day) * 86400 + hour * 3600 + minute * 60 + second
    return total - offset_seconds


def instant_date(total):
    """The calendar date portion of a UTC instant, as eight digits."""
    days = total // 86400
    year = 1
    while True:
        length = 366 if is_leap(year) else 365
        if days < length:
            break
        days -= length
        year += 1
    month = 1
    while True:
        length = days_in_month(year, month)
        if days < length:
            break
        days -= length
        month += 1
    return '%04d%02d%02d' % (year, month, days + 1)


# --------------------------------------------------------------------------- #
# entity normalization and reference data
# --------------------------------------------------------------------------- #

def normalize_ref(value):
    text = unicodedata.normalize('NFC', value)
    text = text.replace('\t', ' ')
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s*-\s*', '-', text)
    return text.strip().upper()


class EffectiveDated:
    """Half open effective dated rows for one entity key.

    Where more than one row covers an instant the row with the latest
    valid_from governs and, on a tie, the one with the earliest valid_to.
    """

    def __init__(self):
        self.rows = defaultdict(list)

    def add(self, key, valid_from, valid_to, value):
        self.rows[key].append((valid_from, valid_to, value))

    def lookup(self, key, instant):
        best = None
        for valid_from, valid_to, value in self.rows.get(key, ()):
            if valid_from is None or valid_to is None:
                continue
            if valid_from <= instant < valid_to:
                if best is None or valid_from > best[0] or \
                        (valid_from == best[0] and valid_to < best[1]):
                    best = (valid_from, valid_to, value)
        return best[2] if best is not None else None


def covering_registration(registrations, meter_id, instant):
    """The registration row that covers an instant for a meter."""
    best = None
    for valid_from, valid_to, multiplier, site_id in registrations.get(meter_id, ()):
        if valid_from is None or valid_to is None:
            continue
        if valid_from <= instant < valid_to:
            if best is None or valid_from > best[0] or \
                    (valid_from == best[0] and valid_to < best[1]):
                best = (valid_from, valid_to, multiplier, site_id)
    return best


def walk_merges(merges, source_site, instant):
    """Walk the merge chain from a source site at an instant.

    Returns (canonical_site, hops_taken).
    """
    site = source_site
    hops = 0
    seen = {site}
    while True:
        applicable = [row for row in merges.get(site, ()) if row[0] <= instant]
        if not applicable:
            return site, hops
        applicable.sort(key=lambda row: (row[0], row[1]))
        survivor = applicable[-1][1]
        if survivor in seen:
            return site, hops
        site = survivor
        hops += 1
        seen.add(site)


def load_reference(data_dir):
    sites = EffectiveDated()
    registered = set()
    for row in read_csv_rows(os.path.join(data_dir, 'sites_effective.csv')):
        registered.add(row['site_id'])
        sites.add(row['site_id'], parse_instant(row['valid_from']),
                  parse_instant(row['valid_to']), (row['tariff_class'], row['zone']))

    states = EffectiveDated()
    for row in read_csv_rows(os.path.join(data_dir, 'operational_state.csv')):
        states.add(row['site_id'], parse_instant(row['valid_from']),
                   parse_instant(row['valid_to']), row['state'])

    ceilings = EffectiveDated()
    for row in read_csv_rows(os.path.join(data_dir, 'max_interval_limits.csv')):
        ceilings.add(row['site_id'], parse_instant(row['valid_from']),
                     parse_instant(row['valid_to']), int(row['max_interval_wh']))

    meters = defaultdict(list)
    for row in read_csv_rows(os.path.join(data_dir, 'meter_registry.csv')):
        multiplier = row['pulse_multiplier']
        if not ASCII_DIGITS.match(multiplier) or int(multiplier) <= 0:
            continue
        meters[row['meter_id']].append(
            (parse_instant(row['valid_from']), parse_instant(row['valid_to']),
             int(multiplier), row['site_id']))

    tariff = defaultdict(list)
    for row in read_csv_rows(os.path.join(data_dir, 'tariff_classes.csv')):
        tariff[row['tariff_class']].append((int(row['threshold_wh']), row['band']))
    for bands in tariff.values():
        bands.sort(key=lambda item: (item[0], item[1]))

    merges = defaultdict(list)
    for row in read_csv_rows(os.path.join(data_dir, 'site_merges.csv')):
        merges[row['absorbed_site']].append(
            (parse_instant(row['merge_instant']), row['survivor_site']))

    baseline_path = os.path.join(data_dir, 'published_baseline.json')
    baseline = {}
    if os.path.exists(baseline_path):
        with open(baseline_path, 'r', encoding='utf-8') as handle:
            baseline = json.load(handle)

    return {
        'sites': sites,
        'registered': registered,
        'states': states,
        'ceilings': ceilings,
        'meters': meters,
        'tariff': tariff,
        'merges': merges,
        'baseline': baseline,
    }


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #

def parse_config_layer(path):
    values = {}
    if not os.path.exists(path):
        return values
    for line in split_lines(read_text(path)):
        line = line.strip()
        if not line or line[0] in ';#[':
            continue
        if '=' not in line:
            continue
        key, _, value = line.partition('=')
        values[key.strip()] = value.strip()
    return values


def resolve_config(data_dir):
    """Last layer wins outside the rounding namespace, smallest value wins inside it."""
    layers = []
    for name in CONFIG_LAYERS:
        layers.append((name, parse_config_layer(os.path.join(data_dir, name))))
    keys = []
    for _name, values in layers:
        for key in values:
            if key not in keys:
                keys.append(key)
    resolved = {}
    winner = {}
    for key in keys:
        setters = [(name, values[key]) for name, values in layers if key in values]
        if key.startswith('rounding.'):
            chosen = None
            for name, value in setters:
                try:
                    number = Decimal(value)
                except Exception:
                    continue
                if chosen is None or number < chosen[0]:
                    chosen = (number, name, value)
            if chosen is None:
                chosen = (None, setters[-1][0], setters[-1][1])
        else:
            chosen = (None, setters[-1][0], setters[-1][1])
        resolved[key] = chosen[2]
        winner[key] = chosen[1]
    return resolved, winner


# --------------------------------------------------------------------------- #
# calendar and batches
# --------------------------------------------------------------------------- #

def load_calendar(data_dir):
    days = []
    text = read_text(os.path.join(data_dir, 'settlement-calendar.md'))
    for line in text.split('\n'):
        match = CALENDAR_LINE.match(line.strip())
        if match:
            opening = parse_instant(match.group(2))
            if opening is not None:
                days.append((match.group(1), opening, opening + 24 * 3600))
    days.sort(key=lambda item: item[0])
    return days


def in_calendar(instant, calendar):
    return any(opening <= instant < closing for _day, opening, closing in calendar)


def settlement_day_of(instant, calendar):
    for day, opening, closing in calendar:
        if opening <= instant < closing:
            return day
    return None


def family_of(filename):
    for family in ('desk', 'import', 'relay', 'partner', 'legacy'):
        if filename.startswith('readings_%s_' % family):
            return family
    if filename.startswith('adjustments_'):
        return 'adjustment'
    return None


def build_batches(data_dir):
    """A filename carrying an ACTIVE manifest row is read exactly once."""
    manifest = read_csv_rows(os.path.join(data_dir, 'batch_manifest.csv'))
    by_filename = defaultdict(list)
    for row in manifest:
        by_filename[row['filename']].append(row)
    scope = []
    for filename, rows in by_filename.items():
        active = [row for row in rows if row['status'] == 'ACTIVE']
        if not active:
            continue
        active.sort(key=lambda row: (int(row['batch_seq']), row['batch_id']))
        chosen = active[0]
        scope.append({
            'filename': filename,
            'batch_id': chosen['batch_id'],
            'batch_seq': int(chosen['batch_seq']),
            'expected_rows': int(chosen['expected_rows']),
            'present': os.path.exists(os.path.join(data_dir, filename)),
            'ingested_ids': [row['batch_id'] for row in active],
        })
    scope.sort(key=lambda item: (item['batch_seq'], item['batch_id']))
    withdrawn = sorted(row['batch_id'] for row in manifest if row['status'] != 'ACTIVE')
    return scope, withdrawn


def read_batch_rows(data_dir, filename, family):
    path = os.path.join(data_dir, filename)
    if family in ('desk', 'relay', 'partner'):
        delimiter = {'desk': ',', 'relay': '\t', 'partner': '|'}[family]
        return read_delimited(path, delimiter)
    lines = split_lines(read_text(path))
    if family in ('import', 'adjustment'):
        rows = []
        for line in lines:
            try:
                obj = json.loads(line)
            except ValueError:
                obj = {}
            if not isinstance(obj, dict):
                obj = {}
            row = {}
            for name in FIELD_NAMES:
                value = obj.get(name, '')
                row[name] = value if isinstance(value, str) else str(value)
            rows.append(row)
        return rows
    if family == 'legacy':
        offsets = []
        cursor = 0
        for width in LEGACY_WIDTHS:
            offsets.append(cursor)
            cursor += width
        rows = []
        for line in lines:
            row = {}
            for index, name in enumerate(FIELD_NAMES):
                start = offsets[index]
                row[name] = line[start:start + LEGACY_WIDTHS[index]]
            rows.append(row)
        return rows
    return []


def clean_field(value, family):
    """The padding a fixed width column carries is not part of the field."""
    return value.strip() if family == 'legacy' else value


# --------------------------------------------------------------------------- #
# validation, disposition and quantity arithmetic
# --------------------------------------------------------------------------- #

def validate_row(row, family, reference, calendar):
    """Apply the eight checks in order and stop at the first failure."""
    if row['revision_class'] not in REVISION_CLASSES:
        return 'MALFORMED_ROW'

    revision_no = row['revision_no']
    if not ASCII_DIGITS.match(revision_no) or int(revision_no) <= 0:
        return 'MALFORMED_ROW'

    instant = parse_instant(row['occurred_at'])
    if instant is None:
        return 'BAD_TIMESTAMP'
    row['_instant'] = instant

    if not in_calendar(instant, calendar):
        return 'OUT_OF_CALENDAR'

    quantity = row['quantity']
    if quantity != '':
        grammar = WH_GRAMMAR if family == 'adjustment' else KWH_GRAMMAR
        if not grammar.match(quantity):
            return 'BAD_QUANTITY'

    if row['_site'] not in reference['registered']:
        return 'UNKNOWN_SITE'

    registration = covering_registration(reference['meters'], row['meter_id'], instant)
    if registration is None:
        return 'UNKNOWN_METER'

    if registration[3] != row['_site']:
        return 'METER_SITE_MISMATCH'
    return None


def revision_wh(row, reference):
    """The watt hour value of a revision as delivered.

    The numeral is read in the batch unit, multiplied by the pulse multiplier
    of the registration covering the row's own occurred_at, and quantized once
    under round half to even. A revision without a quantity carries no value.
    """
    if row['_quantity'] is None:
        return None
    registration = covering_registration(reference['meters'], row['meter_id'], row['_instant'])
    multiplier = Decimal(registration[2]) if registration is not None else Decimal(1)
    value = row['_quantity'] * multiplier
    if row['_family'] == 'adjustment':
        return int(value)
    return int((value * Decimal(1000)).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def read_rows(data_dir, scope, reference, calendar):
    """Read every in scope batch and dispose every body line exactly once."""
    rows = []
    rejects = []
    duplicates = []
    conflicts = []
    row_exceptions = []
    total = 0
    identities = {}

    for batch in scope:
        if not batch['present']:
            continue
        family = family_of(batch['filename'])
        if family is None:
            continue
        body = read_batch_rows(data_dir, batch['filename'], family)
        observed = len(body)
        if observed != batch['expected_rows']:
            row_exceptions.append({
                'batch_id': batch['batch_id'],
                'declared_rows': batch['expected_rows'],
                'filename': batch['filename'],
                'observed_rows': observed,
            })
        for index, raw in enumerate(body, 1):
            total += 1
            row = {name: clean_field(raw.get(name, ''), family) for name in FIELD_NAMES}
            row['_batch_id'] = batch['batch_id']
            row['_batch_seq'] = batch['batch_seq']
            row['_filename'] = batch['filename']
            row['_family'] = family
            row['_line_no'] = index
            row['_site'] = normalize_ref(row['site_ref'])

            reason = validate_row(row, family, reference, calendar)
            if reason is not None:
                row['_reason'] = reason
                rejects.append(row)
                continue

            revision_no = int(row['revision_no'])
            row['_revision_no'] = revision_no
            supersedes = row['supersedes_revision']
            row['_supersedes'] = int(supersedes) if ASCII_DIGITS.match(supersedes) else None
            quantity = row['quantity']
            row['_quantity'] = Decimal(quantity) if quantity != '' else None

            identity = (row['event_key'], revision_no, row['revision_class'], family)
            payload = (row['_site'], row['meter_id'], row['_instant'],
                       row['_quantity'], row['_supersedes'])
            if identity not in identities:
                identities[identity] = payload
                rows.append(row)
            elif identities[identity] == payload:
                duplicates.append(row)
            else:
                conflicts.append(row)

    return {
        'rows': rows,
        'rejects': rejects,
        'duplicates': duplicates,
        'conflicts': conflicts,
        'row_exceptions': sorted(row_exceptions, key=lambda item: item['batch_id']),
        'total': total,
    }


# --------------------------------------------------------------------------- #
# event resolution
# --------------------------------------------------------------------------- #

def canonical_order(row):
    """Class rank first, then revision number, then the earliest batch."""
    return (-CLASS_RANK[row['revision_class']], -row['_revision_no'],
            row['_batch_seq'], row['_line_no'])


def select(revisions, exclude_restatement=False):
    pool = [row for row in revisions
            if not (exclude_restatement and row['revision_class'] == 'RESTATEMENT')]
    if not pool:
        return None
    return sorted(pool, key=canonical_order)[0]


def displaced_nos(revisions):
    """Revision numbers an admitted RESTATEMENT of the event displaces."""
    restatements = [row for row in revisions if row['revision_class'] == 'RESTATEMENT']
    carried = {row['_revision_no'] for row in restatements}
    displaced = set()
    for row in restatements:
        named = row['_supersedes']
        if named is not None and named in carried:
            displaced.add(named)
    return displaced


def quantity_chain(revisions, base, reference, ceiling):
    """Clamp the base into range, add the surviving deltas, clamp again."""
    base_wh = revision_wh(base, reference)
    if base_wh is None:
        return None
    displaced = displaced_nos(revisions)
    stack = [row for row in revisions
             if row['revision_class'] == 'RESTATEMENT' and row['_revision_no'] not in displaced]
    stack.sort(key=lambda row: (row['_revision_no'], row['_batch_seq'], row['_line_no']))
    delta = sum(revision_wh(row, reference) or 0 for row in stack)
    if ceiling is None:
        return {'base': base_wh, 'clamped': base_wh, 'delta': delta,
                'final': base_wh + delta, 'stage': None}
    clamped = min(max(base_wh, 0), ceiling)
    final = min(max(clamped + delta, 0), ceiling)
    base_changed = clamped != base_wh
    sum_changed = final != clamped + delta
    stage = None
    if base_changed and sum_changed:
        stage = 'BOTH'
    elif base_changed:
        stage = 'BASE'
    elif sum_changed:
        stage = 'SUM'
    return {'base': base_wh, 'clamped': clamped, 'delta': delta,
            'final': final, 'stage': stage}


def tariff_band_of(tariff, tariff_class, quantity):
    if quantity == 0 or tariff_class is None:
        return 'UNBANDED'
    best = None
    for threshold, name in tariff.get(tariff_class, ()):
        if threshold <= quantity and (best is None or threshold > best[0]):
            best = (threshold, name)
    return best[1] if best is not None else 'UNBANDED'


def attribute_instant(canonical):
    """The instant the effective dated attributes of an event are read at."""
    return canonical['_instant']


def resolve_events(reference, calendar, read_result):
    events = defaultdict(list)
    for row in read_result['rows']:
        events[row['event_key']].append(row)

    ledger = []
    clamp_register = []
    stack_register = []
    entity_resolutions = []
    deferred = []
    unresolvable = []
    index_rows = []

    for event_key in sorted(events):
        revisions = events[event_key]
        canonical = select(revisions)
        base = select(revisions, exclude_restatement=True)

        source_site = canonical['_site']
        canonical_site, hops = walk_merges(reference['merges'], source_site, canonical['_instant'])
        effective = canonical['_instant']
        settlement_day = settlement_day_of(effective, calendar)

        if source_site in reference['merges']:
            entity_resolutions.append({
                'canonical_site': canonical_site,
                'event_key': event_key,
                'merge_applied': hops > 0,
                'source_site': source_site,
            })

        attributes_instant = attribute_instant(canonical)
        attributes = reference['sites'].lookup(canonical_site, attributes_instant)
        tariff_class = attributes[0] if attributes else None
        zone = attributes[1] if attributes else None
        ceiling = reference['ceilings'].lookup(canonical_site, attributes_instant)
        state = reference['states'].lookup(canonical_site, attributes_instant)

        carried = {row['_revision_no'] for row in revisions}
        canonical_class = canonical['revision_class']
        supersedes = canonical['_supersedes']
        reversal_count = sum(1 for row in revisions if row['revision_class'] == 'REVERSAL')

        outcome = 'SETTLED'
        reason = None
        if canonical_class in ('CORRECTION', 'RESTATEMENT') and \
                supersedes is not None and supersedes not in carried:
            outcome, reason = 'UNRESOLVABLE', 'ORPHAN_SUPERSEDE'
        elif base is None:
            outcome, reason = 'UNRESOLVABLE', 'MISSING_BASE'
        elif ceiling is None:
            outcome, reason = 'UNRESOLVABLE', 'MISSING_CEILING'
        elif revision_wh(base, reference) is None:
            outcome, reason = 'DEFERRED', None
        elif canonical_class == 'REVERSAL' and reversal_count % 2 == 1:
            outcome, reason = 'VOIDED', None
        elif state == 'SUSPENDED':
            outcome, reason = 'EXCLUDED', None

        chain = None
        if outcome in ('SETTLED', 'EXCLUDED'):
            chain = quantity_chain(revisions, base, reference, ceiling)
            quantity = chain['final']
            if chain['stage'] is not None:
                clamp_register.append({
                    'event_key': event_key,
                    'canonical_site': canonical_site,
                    'max_interval_wh': ceiling,
                    'base_wh': chain['base'],
                    'base_clamped_wh': chain['clamped'],
                    'stack_delta_wh': chain['delta'],
                    'final_wh': chain['final'],
                    'clamp_stage': chain['stage'],
                })
        else:
            quantity = 0

        if outcome == 'UNRESOLVABLE':
            unresolvable.append({
                'canonical_site': canonical_site,
                'event_key': event_key,
                'reason_code': reason,
                'settlement_day': settlement_day,
            })
        elif outcome == 'DEFERRED':
            deferred.append({
                'canonical_site': canonical_site,
                'event_key': event_key,
                'revision_no': canonical['_revision_no'],
                'settlement_day': settlement_day,
            })

        ledger.append({
            'canonical_site': canonical_site,
            'event_key': event_key,
            'outcome': outcome,
            'quantity_wh': quantity,
            'revision_class': canonical_class,
            'revision_no': canonical['_revision_no'],
            'settlement_day': settlement_day,
            'source_site': source_site,
            'tariff_band': tariff_band_of(reference['tariff'], tariff_class, quantity),
            'tariff_class': tariff_class,
            'zone': zone,
        })

        displaced = displaced_nos(revisions)
        for row in revisions:
            if row['revision_class'] == 'RESTATEMENT':
                if row['_revision_no'] in displaced:
                    stack_state = 'DISPLACED'
                elif outcome not in ('SETTLED', 'EXCLUDED'):
                    stack_state = 'WITHHELD'
                elif row['_quantity'] is None:
                    stack_state = 'ABSENT'
                else:
                    stack_state = 'APPLIED'
                stack_register.append({
                    'event_key': event_key,
                    'revision_no': row['_revision_no'],
                    'family': row['_family'],
                    'delta_wh': revision_wh(row, reference) or 0,
                    'stack_state': stack_state,
                })

            if row is canonical:
                role = 'CANONICAL'
            elif row is base:
                role = 'BASE'
            elif row['revision_class'] == 'RESTATEMENT' and row['_revision_no'] in displaced:
                role = 'DISPLACED'
            elif row['revision_class'] == 'RESTATEMENT':
                role = 'RESTATEMENT_STACK'
            else:
                role = 'SUPERSEDED'
            index_rows.append((row, role))

    ledger.sort(key=lambda item: (item['settlement_day'], item['canonical_site'], item['event_key']))
    return {
        'events': events,
        'ledger': ledger,
        'clamp_register': sorted(clamp_register, key=lambda item: item['event_key']),
        'stack_register': sorted(
            stack_register, key=lambda item: (item['event_key'], item['revision_no'], item['family'])),
        'entity_resolutions': sorted(entity_resolutions, key=lambda item: item['event_key']),
        'deferred': sorted(deferred, key=lambda item: item['event_key']),
        'unresolvable': sorted(unresolvable, key=lambda item: item['event_key']),
        'index_rows': index_rows,
    }


# --------------------------------------------------------------------------- #
# serialization
# --------------------------------------------------------------------------- #

def present_kwh(wh, dp):
    """Kilowatt hour presentation derived from the integer watt hour value."""
    value = (Decimal(wh) / Decimal(1000)).quantize(
        Decimal(1).scaleb(-dp), rounding=ROUND_HALF_EVEN)
    return str(value)


def dump_jsonl(path, entries):
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        for entry in entries:
            handle.write(json.dumps(entry, sort_keys=True, separators=(',', ':')))
            handle.write('\n')


def dump_json(path, document):
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(document, sort_keys=True, indent=2))
        handle.write('\n')


def dump_csv(path, header, rows):
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(','.join(header) + '\n')
        for row in rows:
            handle.write(','.join(row) + '\n')


# --------------------------------------------------------------------------- #
# the run
# --------------------------------------------------------------------------- #

def materialize(data_dir):
    calendar = load_calendar(data_dir)
    reference = load_reference(data_dir)
    resolved, winner = resolve_config(data_dir)
    scope, withdrawn = build_batches(data_dir)

    missing_batches = sorted(
        ({'batch_id': batch['batch_id'], 'filename': batch['filename'],
          'reason_code': 'MISSING_BATCH'}
         for batch in scope if not batch['present']),
        key=lambda item: item['batch_id'])

    read_result = read_rows(data_dir, scope, reference, calendar)
    events = resolve_events(reference, calendar, read_result)

    quantity_dp = int(resolved.get('rounding.quantity_dp', 2))
    total_dp = int(resolved.get('rounding.total_dp', 2))
    exclusion_policy = resolved.get('settlement.exclusion_policy', 'omit')

    index_entries = []
    for row, role in events['index_rows']:
        index_entries.append({
            'batch_id': row['_batch_id'],
            'event_key': row['event_key'],
            'family': row['_family'],
            'is_canonical': role == 'CANONICAL',
            'quantity_wh': revision_wh(row, reference),
            'revision_class': row['revision_class'],
            'revision_no': row['_revision_no'],
            'role': role,
        })
    index_entries.sort(key=lambda item: (
        item['event_key'], item['revision_no'], item['revision_class'], item['family']))

    partitions = []
    for day, _opening, _closing in calendar:
        rows = [item for item in events['ledger'] if item['settlement_day'] == day]
        if exclusion_policy == 'omit':
            rows = [item for item in rows if item['outcome'] != 'EXCLUDED']
        partition_rows = []
        for sequence, item in enumerate(rows, 1):
            partition_rows.append([str(sequence), item['event_key'], item['canonical_site'],
                                   item['zone'] or '', item['tariff_band'], item['outcome'],
                                   str(item['quantity_wh'])])
        settled = [item for item in rows if item['outcome'] == 'SETTLED']
        partitions.append({
            'settlement_day': day,
            'rows': partition_rows,
            'row_count': len(partition_rows),
            'settled_event_count': len(settled),
            'settled_wh': sum(item['quantity_wh'] for item in settled),
        })

    baseline_cells = {}
    for cell in reference['baseline'].get('cells', []):
        baseline_cells[(cell['settlement_day'], cell['zone'])] = cell

    computed_cells = defaultdict(lambda: {'wh': 0, 'events': 0})
    for item in events['ledger']:
        if item['outcome'] == 'SETTLED':
            cell = computed_cells[(item['settlement_day'], item['zone'])]
            cell['wh'] += item['quantity_wh']
            cell['events'] += 1

    adjustments = []
    for key in sorted(set(baseline_cells) | set(computed_cells)):
        day, zone = key
        stated = baseline_cells.get(key)
        computed = computed_cells.get(key)
        baseline_wh = stated['settled_wh'] if stated else 0
        baseline_count = stated['event_count'] if stated else 0
        restated_wh = computed['wh'] if computed else 0
        restated_count = computed['events'] if computed else 0
        delta_wh = restated_wh - baseline_wh
        delta_events = restated_count - baseline_count
        if delta_wh == 0 and delta_events == 0:
            continue
        if delta_wh > 0:
            kind = 'INCREASE'
        elif delta_wh < 0:
            kind = 'DECREASE'
        else:
            kind = 'COUNT_ONLY'
        adjustments.append({
            'settlement_day': day,
            'zone': zone,
            'adjustment_kind': kind,
            'baseline_settled_wh': baseline_wh,
            'restated_settled_wh': restated_wh,
            'delta_wh': delta_wh,
            'baseline_event_count': baseline_count,
            'restated_event_count': restated_count,
            'delta_events': delta_events,
        })
    adjustments.sort(key=lambda item: (item['settlement_day'], item['zone']))

    ledger_settled_wh = sum(
        item['quantity_wh'] for item in events['ledger'] if item['outcome'] == 'SETTLED')
    partition_settled_wh = sum(item['settled_wh'] for item in partitions)

    identity_class_partition = {
        'admitted': len(read_result['rows']),
        'conflict': len(read_result['conflicts']),
        'duplicate': len(read_result['duplicates']),
        'rejected': len(read_result['rejects']),
        'residual': (len(read_result['rows']) + len(read_result['conflicts'])
                     + len(read_result['duplicates']) + len(read_result['rejects'])
                     - read_result['total']),
        'total_rows': read_result['total'],
    }
    identity_partition_rollup = {
        'ledger_settled_wh': ledger_settled_wh,
        'partition_settled_wh': partition_settled_wh,
        'residual': partition_settled_wh - ledger_settled_wh,
    }
    baseline_total = sum(cell['settled_wh'] for cell in baseline_cells.values())
    restated_total = sum(cell['wh'] for cell in computed_cells.values())
    adjustment_total = sum(item['delta_wh'] for item in adjustments)
    identity_restatement = {
        'adjustment_delta_wh': adjustment_total,
        'baseline_settled_wh': baseline_total,
        'restated_settled_wh': restated_total,
        'residual': baseline_total + adjustment_total - restated_total,
    }

    ingested = sorted({batch_id for batch in scope if batch['present']
                       for batch_id in batch['ingested_ids']})

    run_manifest = {
        'batches_ingested': ingested,
        'batches_withdrawn': withdrawn,
        'config_resolved': resolved,
        'config_winner': winner,
        'row_exceptions': read_result['row_exceptions'],
    }

    return {
        'calendar': calendar,
        'reference': reference,
        'resolved': resolved,
        'scope': scope,
        'withdrawn': withdrawn,
        'missing_batches': missing_batches,
        'read': read_result,
        'events': events,
        'index_entries': index_entries,
        'partitions': partitions,
        'adjustments': adjustments,
        'reconciliation': {
            'identity_class_partition': identity_class_partition,
            'identity_partition_rollup': identity_partition_rollup,
            'identity_restatement': identity_restatement,
        },
        'run_manifest': run_manifest,
        'quantity_dp': quantity_dp,
        'total_dp': total_dp,
        'exclusion_policy': exclusion_policy,
    }


def write_outputs(result, out_dir):
    reference = result['reference']
    read = result['read']
    events = result['events']

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    ledger_entries = []
    for item in events['ledger']:
        ledger_entries.append({
            'canonical_site': item['canonical_site'],
            'event_key': item['event_key'],
            'outcome': item['outcome'],
            'quantity_kwh': present_kwh(item['quantity_wh'], result['quantity_dp']),
            'quantity_wh': item['quantity_wh'],
            'revision_class': item['revision_class'],
            'revision_no': item['revision_no'],
            'settlement_day': item['settlement_day'],
            'source_site': item['source_site'],
            'tariff_band': item['tariff_band'],
            'tariff_class': item['tariff_class'],
            'zone': item['zone'],
        })
    dump_jsonl(os.path.join(out_dir, 'canonical_ledger.jsonl'), ledger_entries)
    dump_jsonl(os.path.join(out_dir, 'revision_index.jsonl'), result['index_entries'])

    for partition in result['partitions']:
        dump_csv(os.path.join(out_dir, 'partition_%s.csv' % partition['settlement_day']),
                 PARTITION_COLUMNS, partition['rows'])

    dump_json(os.path.join(out_dir, 'partition_manifest.json'), {'partitions': [
        {
            'row_count': item['row_count'],
            'settled_event_count': item['settled_event_count'],
            'settled_kwh': present_kwh(item['settled_wh'], result['total_dp']),
            'settled_wh': item['settled_wh'],
            'settlement_day': item['settlement_day'],
        } for item in result['partitions']
    ]})

    rejects = sorted(read['rejects'], key=lambda row: (row['_batch_id'], row['_line_no']))
    dump_csv(os.path.join(out_dir, 'rejects.csv'),
             ['batch_id', 'filename', 'line_no', 'event_key', 'reason_code'],
             [[row['_batch_id'], row['_filename'], str(row['_line_no']),
               row['event_key'], row['_reason']] for row in rejects])

    dump_jsonl(os.path.join(out_dir, 'quarantine.jsonl'), [
        {'batch_id': row['_batch_id'], 'event_key': row['event_key'],
         'line_no': row['_line_no'], 'revision_class': row['revision_class'],
         'revision_no': row['_revision_no']}
        for row in sorted(read['conflicts'], key=lambda row: (row['_batch_id'], row['_line_no']))])

    dump_csv(os.path.join(out_dir, 'dedup_ledger.csv'),
             ['batch_id', 'line_no', 'event_key', 'revision_no', 'revision_class'],
             [[row['_batch_id'], str(row['_line_no']), row['event_key'],
               str(row['_revision_no']), row['revision_class']]
              for row in sorted(read['duplicates'], key=lambda row: (row['_batch_id'], row['_line_no']))])

    dump_jsonl(os.path.join(out_dir, 'deferred.jsonl'), events['deferred'])

    dump_json(os.path.join(out_dir, 'unresolvable.json'), {
        'events': events['unresolvable'],
        'missing_batches': result['missing_batches'],
    })

    dump_json(os.path.join(out_dir, 'entity_resolution.json'),
              {'resolutions': events['entity_resolutions']})

    dump_csv(os.path.join(out_dir, 'clamp_register.csv'),
             ['event_key', 'canonical_site', 'max_interval_wh', 'base_wh', 'base_clamped_wh',
              'stack_delta_wh', 'final_wh', 'clamp_stage'],
             [[item['event_key'], item['canonical_site'], str(item['max_interval_wh']),
               str(item['base_wh']), str(item['base_clamped_wh']), str(item['stack_delta_wh']),
               str(item['final_wh']), item['clamp_stage']]
              for item in events['clamp_register']])

    dump_csv(os.path.join(out_dir, 'stack_register.csv'),
             ['event_key', 'revision_no', 'family', 'delta_wh', 'stack_state'],
             [[item['event_key'], str(item['revision_no']), item['family'],
               str(item['delta_wh']), item['stack_state']]
              for item in events['stack_register']])

    dump_csv(os.path.join(out_dir, 'restatement_adjustments.csv'),
             ['settlement_day', 'zone', 'adjustment_kind', 'baseline_settled_wh',
              'restated_settled_wh', 'delta_wh', 'baseline_event_count',
              'restated_event_count', 'delta_events'],
             [[item['settlement_day'], item['zone'], item['adjustment_kind'],
               str(item['baseline_settled_wh']), str(item['restated_settled_wh']),
               str(item['delta_wh']), str(item['baseline_event_count']),
               str(item['restated_event_count']), str(item['delta_events'])]
              for item in result['adjustments']])

    dump_json(os.path.join(out_dir, 'reconciliation.json'), result['reconciliation'])

    reconciliation = result['reconciliation']
    report = [
        'CLASS_PARTITION residual=%d' % reconciliation['identity_class_partition']['residual'],
        'PARTITION_ROLLUP residual=%d' % reconciliation['identity_partition_rollup']['residual'],
        'RESTATEMENT residual=%d' % reconciliation['identity_restatement']['residual'],
        'ROUNDING quantity_dp=%d total_dp=%d' % (result['quantity_dp'], result['total_dp']),
        'EXCLUSION policy=%s' % result['exclusion_policy'],
        'CLAMPED events=%d' % len(events['clamp_register']),
        'UNRESOLVED events=%d' % len(events['unresolvable']),
        'DISPLACED revisions=%d' % sum(
            1 for item in events['stack_register'] if item['stack_state'] == 'DISPLACED'),
    ]
    with open(os.path.join(out_dir, 'validation_report.txt'), 'w',
              encoding='utf-8', newline='\n') as handle:
        handle.write('\n'.join(report) + '\n')

    dump_json(os.path.join(out_dir, 'run_manifest.json'), result['run_manifest'])


def main(argv=None):
    parser = argparse.ArgumentParser(description='Materialize the Marrowgate settlement ledger')
    parser.add_argument('--data', required=True, help='corpus directory')
    parser.add_argument('--out', required=True, help='destination directory')
    args = parser.parse_args(argv)
    result = materialize(os.path.abspath(args.data))
    write_outputs(result, os.path.abspath(args.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
