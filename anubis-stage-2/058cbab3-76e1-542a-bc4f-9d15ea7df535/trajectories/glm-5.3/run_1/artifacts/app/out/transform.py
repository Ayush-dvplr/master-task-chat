#!/usr/bin/env python3
"""BY41 prepay-gated meter posting run.

Rebuilds the posting pipeline written down in the contract (``schema.md``)
inside an input directory and writes every artifact into an output directory.

    python3 transform.py <DATA_DIR> <OUT_DIR>
"""

import bisect
import configparser
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, \
    ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_UP

# ---------------------------------------------------------------------------
# contract constants
# ---------------------------------------------------------------------------

CONSUMPTION_FILE = 'consumption.csv'
REMITTANCE_FILE = 'remittances.tsv'
LEVY_FILE = 'levies.jsonl'
LEGACY_FILE = 'legacy_reads.txt'

# (file, csv delimiter); None marks the two non-CSV formats
READING_FILES = (
    (CONSUMPTION_FILE, ','),
    (REMITTANCE_FILE, '\t'),
    (LEVY_FILE, None),
    (LEGACY_FILE, None),
)

FILE_COLUMNS = {
    CONSUMPTION_FILE: ('reading_id', 'read_ts', 'account_id', 'tariff_code',
                       'meter_site', 'units_consumed', 'rate_per_unit',
                       'currency', 'collector'),
    REMITTANCE_FILE: ('reading_id', 'read_ts', 'account_id', 'tariff_code',
                      'meter_site', 'units_consumed', 'remit_amount',
                      'currency', 'collector', 'charge_reading_id'),
    LEVY_FILE: ('reading_id', 'read_ts', 'account_id', 'tariff_code', 'kind',
                'amount_minor', 'currency', 'note'),
    LEGACY_FILE: ('reading_id', 'read_ts', 'account_id', 'tariff_code',
                  'meter_site', 'kind', 'units_consumed', 'amount',
                  'currency', 'collector', 'memo'),
}

TOP_LEVEL_ZONES = ('central', 'east', 'north', 'south', 'west')
TARIFF_CLASSES = ('consumer', 'smb', 'corporate', 'enterprise')

UNITS_RE = re.compile(r'[0-9]+\Z')
INT_RE = re.compile(r'[+-]?[0-9]+\Z')
DECIMAL_RE = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\Z')
TS_LOCAL_RE = re.compile(r'([0-9]{4})-([0-9]{2})-([0-9]{2})'
                         r'T([0-9]{2}):([0-9]{2}):([0-9]{2})\Z')
TS_UTC_RE = re.compile(r'([0-9]{4})-([0-9]{2})-([0-9]{2})'
                       r'T([0-9]{2}):([0-9]{2}):([0-9]{2})Z\Z')
DATE_RE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}\Z')

ROUNDING = {
    'half_up': ROUND_HALF_UP,
    'half_even': ROUND_HALF_EVEN,
    'floor': ROUND_FLOOR,
    'ceiling': ROUND_CEILING,
    'down': ROUND_DOWN,
    'truncate': ROUND_DOWN,
    'up': ROUND_UP,
}

ONE = Decimal(1)
HUNDRED = Decimal(100)
HALF = Decimal('0.5')

LEVY_KINDS = ('surcharge', 'rebate')
LEGACY_SIGNS = {'consumption': -1, 'surcharge': -1,
                'remittance': 1, 'rebate': 1}


class Skip(Exception):
    """Raised for a reading that turns out malformed."""


# ---------------------------------------------------------------------------
# small parsing helpers
# ---------------------------------------------------------------------------

def parse_local_stamp(text):
    """Local wall clock timestamp -> datetime, else None."""
    match = TS_LOCAL_RE.match(text)
    if not match:
        return None
    try:
        return datetime(*(int(part) for part in match.groups()))
    except ValueError:
        return None


def parse_utc_stamp(text):
    """UTC timestamp carrying a trailing Z -> datetime, else None."""
    match = TS_UTC_RE.match(text)
    if not match:
        return None
    try:
        return datetime(*(int(part) for part in match.groups()))
    except ValueError:
        return None


def parse_date(text):
    if not DATE_RE.match(text):
        return None
    year, month, day = (int(part) for part in text.split('-'))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def need_int(text):
    if not INT_RE.match(text):
        raise Skip('not an integer')
    return int(text)


def need_decimal(text):
    if not DECIMAL_RE.match(text):
        raise Skip('not a decimal')
    return Decimal(text)


def quantize(mode, amount):
    """Quantize an exact Decimal to a whole unit exactly once."""
    rounding = ROUNDING.get(mode)
    if rounding is None:
        raise ValueError('unknown rounding mode %r' % (mode,))
    return int(amount.quantize(ONE, rounding=rounding))


def fold_lower(text):
    return (text or '').strip().lower()


def fold_upper(text):
    return (text or '').strip().upper()


def read_csv_rows(path, delimiter):
    with open(path, encoding='utf-8', newline='') as handle:
        for row in csv.DictReader(handle, delimiter=delimiter):
            yield {key: value for key, value in row.items()
                   if key is not None}


# ---------------------------------------------------------------------------
# reference tables
# ---------------------------------------------------------------------------

class Reference:
    def __init__(self, data_dir, present):
        self.dir = data_dir
        self.present = present
        self.accounts = {}
        self.meter_postcode = {}
        self.meter_offset = {}
        self.capacity = {}
        self.catalogue = {}
        self.collectors = {}
        self.top_zone = {}
        self.prefix_currency = {}
        self.rate_dates = {}
        self.rate_values = {}
        self.cycles = []
        self.floors = {}
        self.opening_rate_date = None
        self.rounding_mode = 'half_up'
        self.litres_per_kilolitre = HUNDRED * Decimal(10)
        self.unassigned_cycle = 'uncycled'
        self.levy_route_group = 'levy'

    def path(self, name):
        return os.path.join(self.dir, name)

    def holds(self, name):
        return name in self.present

    def floor_for(self, tariff_class):
        return need_int(self.floors['floor_%s_usd_cents' % tariff_class])

    # -- loading --------------------------------------------------------
    def load_policy(self):
        parser = configparser.ConfigParser()
        parser.optionxform = str
        with open(self.path('policy.ini'), encoding='utf-8') as handle:
            parser.read_file(handle)
        self.opening_rate_date = parser.get(
            'wallet', 'opening_rate_date').strip()
        self.rounding_mode = parser.get('rounding', 'mode').strip().lower()
        self.litres_per_kilolitre = need_decimal(
            parser.get('volume', 'litres_per_kilolitre').strip())
        self.unassigned_cycle = parser.get(
            'labels', 'unassigned_cycle').strip()
        self.levy_route_group = fold_lower(
            parser.get('labels', 'levy_route_group'))
        for key, value in parser.items('disconnection'):
            self.floors[key.strip()] = value.strip()

    def load_accounts(self):
        best = {}
        order = 0
        for row in read_csv_rows(self.path('accounts.csv'), ','):
            order += 1
            account_id = row['account_id'].strip()
            rank = (row['revised_at'].strip(), order)
            current = best.get(account_id)
            if current is None or rank > current[0]:
                best[account_id] = (rank, row)
        for account_id, (_, row) in best.items():
            self.accounts[account_id] = {
                'tariff_class': fold_lower(row['tariff_class']),
                'postcode': row['service_postcode'].strip(),
                'opening_minor': need_int(
                    row['opening_credit_minor'].strip()),
                'opening_currency': fold_upper(row['opening_currency']),
            }

    def load_meter_sites(self):
        capacity = defaultdict(lambda: [0, 0])
        for row in read_csv_rows(self.path('meter_sites.csv'), ','):
            site = row['meter_site'].strip()
            if site not in self.meter_postcode:
                self.meter_postcode[site] = row['postcode'].strip()
                self.meter_offset[site] = need_int(
                    row['utc_offset_minutes'].strip())
            bucket = capacity[row['tariff_code'].strip()]
            bucket[0] += need_int(row['installed_litres'].strip())
            bucket[1] += need_int(row['service_floor_litres'].strip())
        self.capacity = dict(capacity)

    def load_catalogue(self):
        for row in read_csv_rows(self.path('tariff_catalogue.csv'), ','):
            code = row['tariff_code'].strip()
            self.catalogue[code] = {
                'category': fold_lower(row['category']),
                'unit_volume': need_decimal(
                    row['unit_volume_litres'].strip()),
            }

    def load_collectors(self):
        for row in read_csv_rows(self.path('collectors.csv'), ','):
            self.collectors[fold_lower(row['collector'])] = fold_lower(
                row['route_group'])

    def load_zones(self):
        rows = {}
        for row in read_csv_rows(self.path('service_zones.csv'), ','):
            rows[row['postcode_prefix'].strip()] = (
                fold_lower(row['zone']), fold_lower(row['parent_zone']),
                fold_upper(row['default_currency']))
        owner = {}
        for prefix, (zone, _parent, _currency) in rows.items():
            owner[zone] = prefix
        for prefix, (zone, parent, currency) in rows.items():
            top = None
            seen = set()
            current = zone
            while current not in seen:
                seen.add(current)
                if current in TOP_LEVEL_ZONES:
                    top = current
                    break
                holder = rows.get(owner.get(current, ''))
                if holder is None:
                    break
                step = holder[1]
                if not step:
                    break
                current = step
            if top is not None:
                self.top_zone[prefix] = top
                self.prefix_currency[prefix] = currency

    def load_rates(self):
        table = defaultdict(dict)
        for row in read_csv_rows(self.path('currency_rates.csv'), ','):
            when = parse_date(row['rate_date'].strip())
            if when is None:
                continue
            table[fold_upper(row['currency'])][when] = need_decimal(
                row['usd_rate'].strip())
        for currency, rows in table.items():
            dates = sorted(rows)
            self.rate_dates[currency] = dates
            self.rate_values[currency] = [rows[d] for d in dates]

    def load_calendar(self):
        with open(self.path('billing_calendar.json'), encoding='utf-8') as fh:
            doc = json.load(fh)
        cycles = []
        for cycle in doc.get('cycles', []):
            opens = parse_date(str(cycle['opens']).strip())
            closes = parse_date(str(cycle['closes']).strip())
            if opens is None or closes is None:
                continue
            cycles.append((opens, closes, str(cycle['cycle']).strip()))
        cycles.sort(key=lambda item: (item[0], item[1]))
        self.cycles = cycles

    # -- lookups --------------------------------------------------------
    def rate_for(self, currency, on_date):
        """(rate, carried date) for a posting date, else None."""
        dates = self.rate_dates.get(currency)
        if not dates:
            return None
        index = bisect.bisect_right(dates, on_date) - 1
        if index < 0:
            return None
        return self.rate_values[currency][index], dates[index]

    def cycle_for(self, on_date):
        for opens, closes, label in self.cycles:
            if opens <= on_date <= closes:
                return label
        return self.unassigned_cycle


def load_amendments(path):
    """Winning value per (reading id, field) and the set of all targets."""
    winners = {}
    targets = set()
    with open(path, encoding='utf-8') as handle:
        lines = handle.read().split('\n')
    for order, line in enumerate(lines):
        line = line.rstrip('\r')
        if not line.strip():
            continue
        parts = line.split(' ', 2)
        if len(parts) < 3:
            continue
        stamp, _level, message = parts
        tokens = message.split()
        if not tokens or tokens[0].lower() != 'amendment':
            continue
        found = {}
        for token in tokens[1:]:
            if '=' in token:
                key, value = token.split('=', 1)
                if key not in found:
                    found[key] = value
        target = found.get('target')
        field = found.get('field')
        if target is None or field is None:
            continue
        targets.add(target)
        key = (target, field)
        rank = (stamp, order)
        current = winners.get(key)
        if current is None or rank > current[0]:
            winners[key] = (rank, found.get('value', ''))
    return {key: value for key, (_, value) in winners.items()}, targets


# ---------------------------------------------------------------------------
# reading rows
# ---------------------------------------------------------------------------

class Reading:
    __slots__ = ('reading_id', 'source', 'kind', 'units', 'gross',
                 'currency', 'account_id', 'tariff_code', 'meter_site',
                 'collector', 'local', 'utc', 'charge_reading_id',
                 'written_date')

    def __init__(self):
        self.reading_id = ''
        self.source = None
        self.kind = None
        self.units = 0
        self.gross = None
        self.currency = None
        self.account_id = ''
        self.tariff_code = ''
        self.meter_site = None
        self.collector = None
        self.local = None
        self.utc = None
        self.charge_reading_id = None
        self.written_date = None


def need_units(text):
    if not UNITS_RE.match(text):
        raise Skip('units are not an integer')
    return int(text)


def cell(row, name):
    """A csv cell as trimmed text; a missing or short column reads empty."""
    value = row.get(name)
    return '' if value is None else str(value)


def parse_consumption(row):
    reading = Reading()
    reading.reading_id = cell(row, 'reading_id').strip()
    reading.kind = 'consumption'
    reading.units = need_units(cell(row, 'units_consumed').strip())
    rate = need_decimal(cell(row, 'rate_per_unit').strip())
    reading.gross = -(Decimal(reading.units) * rate)
    reading.currency = fold_upper(cell(row, 'currency'))
    reading.account_id = cell(row, 'account_id').strip()
    reading.tariff_code = cell(row, 'tariff_code').strip()
    reading.meter_site = cell(row, 'meter_site').strip()
    reading.collector = fold_lower(cell(row, 'collector'))
    stamp = cell(row, 'read_ts').strip()
    reading.local = parse_local_stamp(stamp)
    if reading.local is None:
        raise Skip('bad read_ts')
    reading.written_date = stamp[:10]
    return reading


def parse_remitting(row):
    reading = Reading()
    reading.reading_id = cell(row, 'reading_id').strip()
    reading.kind = 'remittance'
    reading.units = need_units(cell(row, 'units_consumed').strip())
    reading.gross = abs(need_decimal(cell(row, 'remit_amount').strip()))
    reading.currency = fold_upper(cell(row, 'currency'))
    reading.account_id = cell(row, 'account_id').strip()
    reading.tariff_code = cell(row, 'tariff_code').strip()
    reading.meter_site = cell(row, 'meter_site').strip()
    reading.collector = fold_lower(cell(row, 'collector'))
    stamp = cell(row, 'read_ts').strip()
    reading.local = parse_local_stamp(stamp)
    if reading.local is None:
        raise Skip('bad read_ts')
    reading.written_date = stamp[:10]
    reading.charge_reading_id = cell(row, 'charge_reading_id').strip()
    return reading


def parse_levy(obj):
    def text(name, required=True):
        if name not in obj:
            if required:
                raise Skip('missing %s' % name)
            return None
        value = obj[name]
        if not isinstance(value, str):
            raise Skip('%s is not text' % name)
        return value.strip()

    reading = Reading()
    reading.reading_id = text('reading_id')
    reading.account_id = text('account_id')
    reading.tariff_code = text('tariff_code')
    reading.currency = fold_upper(text('currency'))
    stamp = text('read_ts')
    reading.utc = parse_utc_stamp(stamp)
    if reading.utc is None:
        raise Skip('bad read_ts')
    reading.written_date = stamp[:10]
    if 'amount_minor' not in obj:
        raise Skip('missing amount_minor')
    minor = obj['amount_minor']
    if isinstance(minor, bool) or not isinstance(minor, int):
        raise Skip('amount_minor is not an integer')
    reading.gross = Decimal(minor) / HUNDRED
    kind = text('kind')
    if kind.lower() not in LEVY_KINDS:
        raise Skip('unknown levy kind')
    reading.kind = kind.lower()
    reading.units = 0
    text('note', required=False)
    return reading


def parse_legacy(parts):
    if len(parts) != 11:
        raise Skip('legacy line does not carry eleven fields')
    (rid, stamp, account_id, tariff_code, meter_site, kind, units, amount,
     currency, collector, _memo) = parts
    reading = Reading()
    reading.reading_id = rid.strip()
    reading.account_id = account_id.strip()
    reading.tariff_code = tariff_code.strip()
    reading.meter_site = meter_site.strip()
    reading.collector = fold_lower(collector)
    reading.currency = fold_upper(currency)
    folded = kind.strip().lower()
    if folded not in LEGACY_SIGNS:
        raise Skip('unknown legacy kind')
    reading.kind = folded
    reading.gross = Decimal(LEGACY_SIGNS[folded]) * abs(
        need_decimal(amount.strip()))
    reading.units = need_units(units.strip())
    stamp = stamp.strip()
    reading.local = parse_local_stamp(stamp)
    if reading.local is None:
        raise Skip('bad read_ts')
    reading.written_date = stamp[:10]
    return reading


def raw_rows(ref, source, delimiter):
    """Yield (order, row) for every row of one reading file.

    ``row`` is a dict for the three keyed formats and a list for the pipe
    delimited legacy format. Lines that carry no reading are not yielded.
    """
    if source == LEGACY_FILE:
        with open(ref.path(source), encoding='latin-1') as handle:
            for order, line in enumerate(handle):
                line = line.rstrip('\n').rstrip('\r')
                stripped = line.strip()
                if not stripped or stripped[0] == '#':
                    continue
                yield order, line.split('|')
        return
    if source == LEVY_FILE:
        with open(ref.path(source), encoding='utf-8') as handle:
            for order, line in enumerate(handle):
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    yield order, None
                    continue
                yield order, obj if isinstance(obj, dict) else None
        return
    with open(ref.path(source), encoding='utf-8', newline='') as handle:
        for order, row in enumerate(csv.DictReader(handle,
                                                   delimiter=delimiter)):
            yield order, row


def apply_amendments(source, row, reading_id, amendments):
    """Return the row with every winning amendment for it applied."""
    columns = FILE_COLUMNS[source]
    if source == LEGACY_FILE:
        parts = list(row)
        for index, field in enumerate(columns):
            if field == 'reading_id':
                continue
            if (reading_id, field) in amendments:
                parts[index] = amendments[(reading_id, field)]
        return parts
    values = dict(row)
    for field in columns:
        if field == 'reading_id':
            continue
        if (reading_id, field) in amendments:
            values[field] = amendments[(reading_id, field)]
    return values


def row_reading_id(source, row):
    if row is None:
        return ''
    if source == LEGACY_FILE:
        return row[0].strip() if row else ''
    value = row.get('reading_id')
    if not isinstance(value, str):
        return ''
    return value.strip()


# ---------------------------------------------------------------------------
# the posting chain
# ---------------------------------------------------------------------------

def resolve_record(ref, reading):
    """Steps 2 to 10 of the contract; raises Skip on a broken chain."""
    account = ref.accounts.get(reading.account_id)
    if account is None:
        raise Skip('unknown account')
    entry = ref.catalogue.get(reading.tariff_code)
    if entry is None:
        raise Skip('unknown tariff code')

    if reading.source == LEVY_FILE:
        postcode = account['postcode']
        utc = reading.utc
    else:
        postcode = ref.meter_postcode.get(reading.meter_site)
        if postcode is None:
            raise Skip('unknown meter site')
        utc = reading.local + timedelta(
            minutes=ref.meter_offset[reading.meter_site])

    prefix = postcode.split('-', 1)[0]
    zone = ref.top_zone.get(prefix)
    if zone is None:
        raise Skip('unknown postcode prefix')

    currency = reading.currency or ref.prefix_currency.get(prefix)
    if not currency:
        raise Skip('no currency')

    posting_date = utc.date()
    found = ref.rate_for(currency, posting_date)
    if found is None:
        raise Skip('no usable rate')
    rate, carried = found

    if reading.source == LEVY_FILE:
        route_group = ref.levy_route_group
    else:
        route_group = ref.collectors.get(reading.collector)
        if route_group is None:
            raise Skip('unknown collector')

    exact = reading.gross * rate * HUNDRED
    cents = quantize(ref.rounding_mode, exact)

    record = {
        'reading_id': reading.reading_id,
        'posting_date': posting_date.isoformat(),
        'utc_instant': utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'billing_cycle': ref.cycle_for(posting_date),
        'account_id': reading.account_id,
        'tariff_class': account['tariff_class'],
        'zone': zone,
        'tariff_code': reading.tariff_code,
        'category': entry['category'],
        'kind': reading.kind,
        'units': reading.units,
        'posted_usd_cents': cents,
        'currency': currency,
        'source': reading.source,
        'route_group': route_group,
        'meter_site': None if reading.source == LEVY_FILE
        else reading.meter_site,
    }
    flags = {
        'carry_back': carried != posting_date,
        'half_cent': (abs(exact) - abs(exact).to_integral_value()) == HALF,
        'day_shift': reading.written_date != posting_date.isoformat(),
        'charge_reading_id': reading.charge_reading_id,
    }
    return record, flags


def open_wallet(ref, account):
    found = ref.rate_for(account['opening_currency'],
                         parse_date(ref.opening_rate_date))
    if found is None:
        return 0
    rate, _carried = found
    exact = (Decimal(account['opening_minor']) / HUNDRED) * rate * HUNDRED
    return quantize(ref.rounding_mode, exact)


def net_units(record):
    if record['kind'] == 'consumption':
        return record['units']
    if record['kind'] == 'remittance':
        return -record['units']
    return 0


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------

def write_json(path, document):
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(json.dumps(document, indent=2, sort_keys=True))
        handle.write('\n')


def write_jsonl(path, records):
    with open(path, 'w', encoding='utf-8') as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True,
                                    separators=(',', ':')))
            handle.write('\n')


def money_sum(records):
    return sum(record['posted_usd_cents'] for record in records)


def unit_sum(records):
    return sum(net_units(record) for record in records)


def money_by(records, field):
    out = defaultdict(int)
    for record in records:
        out[record[field]] += record['posted_usd_cents']
    return dict(out)


def bucket(records, held, label, value, extra=None):
    document = {
        label: value,
        'event_count': len(records),
        'total_usd_cents': money_sum(records),
        'net_units': unit_sum(records),
        'held_count': len(held),
        'accounts': sorted({r['account_id'] for r in records}),
        'by_kind': money_by(records, 'kind'),
        'by_category': money_by(records, 'category'),
    }
    if extra:
        document.update(extra)
    return document


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: transform.py <DATA_DIR> <OUT_DIR>\n')
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)

    present = sorted(
        name for name in os.listdir(data_dir)
        if os.path.isfile(os.path.join(data_dir, name)))

    ref = Reference(data_dir, set(present))
    ref.load_policy()
    ref.load_accounts()
    ref.load_meter_sites()
    ref.load_catalogue()
    ref.load_collectors()
    ref.load_zones()
    ref.load_rates()
    ref.load_calendar()

    amendments, targets = load_amendments(ref.path('amendments.log'))

    # which file every reading id lives in, and the ids of consumption.csv.
    # A legacy line that does not carry exactly eleven fields is malformed
    # and yields no reading at all, so it matches nothing.
    id_file = {}
    consumption_ids = set()
    for source, delimiter in READING_FILES:
        if not ref.holds(source):
            continue
        for _order, row in raw_rows(ref, source, delimiter):
            if source == LEGACY_FILE and (row is None or len(row) != 11):
                continue
            reading_id = row_reading_id(source, row)
            if not reading_id:
                continue
            id_file[reading_id] = source
            if source == CONSUMPTION_FILE:
                consumption_ids.add(reading_id)

    # amendments that name a column of their target's own reading file
    unmatched = {reading_id for reading_id in targets
                 if reading_id not in id_file}
    applied = {
        (reading_id, field): value
        for (reading_id, field), value in amendments.items()
        if reading_id in id_file and field in FILE_COLUMNS[id_file[reading_id]]
    }
    amended_ids = {reading_id for reading_id, _field in applied}

    # -- parse every reading file ---------------------------------------
    parsed = []
    skipped_by_source = defaultdict(int)
    skipped_ids = defaultdict(set)
    orphans = []

    for source, delimiter in READING_FILES:
        if not ref.holds(source):
            continue
        for _order, row in raw_rows(ref, source, delimiter):
            reading_id = row_reading_id(source, row)
            if source == REMITTANCE_FILE:
                # the orphan test reads the amended charge link and runs
                # before any other field of the remittance is parsed
                link = ''
                if row is not None:
                    value = row.get('charge_reading_id')
                    link = value.strip() if isinstance(value, str) else ''
                if (reading_id, 'charge_reading_id') in applied:
                    link = applied[(reading_id, 'charge_reading_id')]
                if link and link not in consumption_ids:
                    orphans.append(reading_id)
                    continue
            try:
                if row is None:
                    raise Skip('unusable row')
                values = apply_amendments(source, row, reading_id, applied)
                if source == CONSUMPTION_FILE:
                    reading = parse_consumption(values)
                elif source == REMITTANCE_FILE:
                    reading = parse_remitting(values)
                elif source == LEVY_FILE:
                    reading = parse_levy(values)
                else:
                    reading = parse_legacy(values)
                reading.source = source
                parsed.append(reading)
            except Skip:
                skipped_by_source[source] += 1
                if reading_id:
                    skipped_ids[source].add(reading_id)

    # -- resolve the posting chain ---------------------------------------
    staged = []
    for reading in parsed:
        try:
            record, flags = resolve_record(ref, reading)
        except Skip:
            skipped_by_source[reading.source] += 1
            skipped_ids[reading.source].add(reading.reading_id)
            continue
        staged.append((record, flags))

    # -- prepay wallet gate ----------------------------------------------
    by_account = defaultdict(list)
    for record, flags in staged:
        by_account[record['account_id']].append((record, flags))

    posted = []
    posted_flags = []
    held = []
    closing = {}
    for account_id, account in ref.accounts.items():
        group = by_account.get(account_id)
        balance = open_wallet(ref, account)
        if group is None:
            closing[account_id] = balance
            continue
        floor = ref.floor_for(account['tariff_class'])
        group.sort(key=lambda item: (item[0]['utc_instant'],
                                     item[0]['reading_id']))
        for record, flags in group:
            cents = record['posted_usd_cents']
            if cents >= 0 or balance + cents >= floor:
                balance += cents
                posted.append(record)
                posted_flags.append(flags)
            else:
                held.append(record)
        closing[account_id] = balance

    # -- normalized.jsonl -------------------------------------------------
    write_jsonl(os.path.join(out_dir, 'normalized.jsonl'),
                sorted(posted, key=lambda record: record['reading_id']))

    # -- summary.json ------------------------------------------------------
    summary = {
        'event_count': len(posted),
        'skipped_count': sum(skipped_by_source.values()),
        'held_count': len(held),
        'orphan_remittance_count': len(orphans),
        'total_usd_cents': money_sum(posted),
        'net_units': unit_sum(posted),
        'wallet_closing_usd_cents': sum(closing.values()),
        'by_zone': money_by(posted, 'zone'),
        'by_tariff_class': money_by(posted, 'tariff_class'),
        'by_kind': money_by(posted, 'kind'),
        'by_category': money_by(posted, 'category'),
        'by_route_group': money_by(posted, 'route_group'),
        'by_billing_cycle': money_by(posted, 'billing_cycle'),
        'by_source': money_by(posted, 'source'),
    }
    write_json(os.path.join(out_dir, 'summary.json'), summary)

    # -- data_quality.json --------------------------------------------------
    reading_files_present = [source for source, _ in READING_FILES
                             if ref.holds(source)]
    posted_source = defaultdict(int)
    held_source = defaultdict(int)
    for record in posted:
        posted_source[record['source']] += 1
    for record in held:
        held_source[record['source']] += 1
    data_quality = {
        'input_files': present,
        'records_by_source': {source: posted_source[source]
                              for source in reading_files_present
                              if source in posted_source},
        'skipped_by_source': {source: skipped_by_source.get(source, 0)
                              for source in reading_files_present},
        'held_by_source': {source: held_source.get(source, 0)
                           for source in reading_files_present},
        'skipped_count': sum(skipped_by_source.values()),
        'held_count': len(held),
        'orphan_remittance_count': len(orphans),
        'held_reading_ids': sorted({r['reading_id'] for r in held}),
        'orphan_remittance_ids': sorted(set(orphans)),
        'unmatched_amendment_targets': sorted(unmatched),
    }
    write_json(os.path.join(out_dir, 'data_quality.json'), data_quality)

    # -- product_summary.json ------------------------------------------------
    by_code = defaultdict(list)
    for record in posted:
        by_code[record['tariff_code']].append(record)
    tariffs = []
    for code in sorted(ref.catalogue):
        rows = by_code.get(code, [])
        installed, service_floor = ref.capacity.get(code, [0, 0])
        units = unit_sum(rows)
        exact = (Decimal(units) * ref.catalogue[code]['unit_volume'] *
                 ref.litres_per_kilolitre)
        tariffs.append({
            'tariff_code': code,
            'category': ref.catalogue[code]['category'],
            'event_count': len(rows),
            'total_usd_cents': money_sum(rows),
            'net_units': units,
            'installed_litres': installed,
            'service_floor_litres': service_floor,
            'net_volume_litres': quantize(ref.rounding_mode, exact),
        })
    write_json(os.path.join(out_dir, 'product_summary.json'),
               {'tariffs': tariffs})

    # -- region_*.json ---------------------------------------------------------
    held_by_zone = defaultdict(list)
    held_by_class = defaultdict(list)
    for record in held:
        held_by_zone[record['zone']].append(record)
        held_by_class[record['tariff_class']].append(record)
    for zone in TOP_LEVEL_ZONES:
        rows = [r for r in posted if r['zone'] == zone]
        write_json(os.path.join(out_dir, 'region_%s.json' % zone),
                   bucket(rows, held_by_zone.get(zone, []), 'zone', zone))

    # -- segment_*.json ----------------------------------------------------------
    for tariff_class in TARIFF_CLASSES:
        rows = [r for r in posted if r['tariff_class'] == tariff_class]
        write_json(os.path.join(out_dir, 'segment_%s.json' % tariff_class),
                   bucket(rows, held_by_class.get(tariff_class, []),
                          'tariff_class', tariff_class,
                          {'disconnection_floor_usd_cents':
                           ref.floor_for(tariff_class)}))

    # -- the nine closing figures -----------------------------------------------
    malformed_consumption = skipped_ids.get(CONSUMPTION_FILE, set())
    closing_report = {
        'held_value_usd_cents': money_sum(held),
        'held_accounts': len({r['account_id'] for r in held}),
        'carry_back_rate_events': sum(1 for flags in posted_flags
                                      if flags['carry_back']),
        'day_shift_events': sum(1 for flags in posted_flags
                                if flags['day_shift']),
        'amended_readings': len(amended_ids),
        'half_cent_events': sum(1 for flags in posted_flags
                                if flags['half_cent']),
        'underfunded_accounts': sum(
            1 for account in ref.accounts.values()
            if open_wallet(ref, account) < ref.floor_for(
                account['tariff_class'])),
        'uncatalogued_capacity_litres': sum(
            installed for code, (installed, _floor) in ref.capacity.items()
            if code not in ref.catalogue),
        'stale_link_remittances': sum(
            1 for record, flags in zip(posted, posted_flags)
            if record['source'] == REMITTANCE_FILE and
            flags['charge_reading_id'] and
            flags['charge_reading_id'] in malformed_consumption),
    }
    print(json.dumps(closing_report, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
