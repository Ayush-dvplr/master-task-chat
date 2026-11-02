#!/usr/bin/env python3
"""BY41 prepay-gated meter posting run.

Usage: python3 transform.py <DATA_DIR> <OUT_DIR>
"""
import bisect
import collections
import configparser
import csv
import json
import os
import re
import sys
from datetime import datetime, timedelta
from decimal import (Decimal, getcontext, ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR,
                     ROUND_HALF_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_UP)

getcontext().prec = 80

CONSUMPTION = 'consumption.csv'
REMITTANCES = 'remittances.tsv'
LEVIES = 'levies.jsonl'
LEGACY = 'legacy_reads.txt'
READING_FILES = [CONSUMPTION, REMITTANCES, LEVIES, LEGACY]

COLUMNS = {
    CONSUMPTION: ['reading_id', 'read_ts', 'account_id', 'tariff_code', 'meter_site',
                  'units_consumed', 'rate_per_unit', 'currency', 'collector'],
    REMITTANCES: ['reading_id', 'read_ts', 'account_id', 'tariff_code', 'meter_site',
                  'units_consumed', 'remit_amount', 'currency', 'collector',
                  'charge_reading_id'],
    LEVIES: ['reading_id', 'read_ts', 'account_id', 'tariff_code', 'kind',
             'amount_minor', 'currency', 'note'],
    LEGACY: ['reading_id', 'read_ts', 'account_id', 'tariff_code', 'meter_site', 'kind',
             'units_consumed', 'amount', 'currency', 'collector', 'memo'],
}

TOP_ZONES = ['central', 'east', 'north', 'south', 'west']
TARIFF_CLASSES = ['consumer', 'corporate', 'enterprise', 'smb']
LEGACY_KINDS = {'consumption', 'remittance', 'surcharge', 'rebate'}
LEVY_KINDS = {'surcharge', 'rebate'}

ROUNDING_MODES = {
    'half_up': ROUND_HALF_UP,
    'half_even': ROUND_HALF_EVEN,
    'half_down': ROUND_HALF_DOWN,
    'up': ROUND_UP,
    'down': ROUND_DOWN,
    'ceiling': ROUND_CEILING,
    'floor': ROUND_FLOOR,
}

TS_RE = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
UINT_RE = re.compile(r'[0-9]+')
INT_RE = re.compile(r'[+-]?[0-9]+')
DEC_RE = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)')
AMENDMENT_RE = re.compile(
    r'^(?P<ts>\S+)\s+(?P<level>\S+)\s+amendment\s+target=(?P<target>\S*)\s+'
    r'field=(?P<field>\S*)\s+value=(?P<value>.*)$')


def trim(value):
    return value.strip() if isinstance(value, str) else value


class Skip(Exception):
    """Raised when a reading is malformed."""


# --------------------------------------------------------------------------
# policy and reference data
# --------------------------------------------------------------------------

class Policy:
    def __init__(self, path):
        parser = configparser.ConfigParser()
        parser.read(path)
        self.opening_rate_date = parser.get('wallet', 'opening_rate_date').strip()
        self.floors = {}
        for cls in TARIFF_CLASSES:
            self.floors[cls] = int(parser.get('disconnection',
                                              'floor_%s_usd_cents' % cls).strip())
        self.rounding = ROUNDING_MODES[parser.get('rounding', 'mode').strip().lower()]
        self.money_scale = int(parser.get('rounding', 'money_scale').strip())
        self.volume_scale = int(parser.get('rounding', 'volume_scale').strip())
        self.litres_per_kilolitre = Decimal(
            parser.get('volume', 'litres_per_kilolitre').strip())
        self.unassigned_cycle = parser.get('labels', 'unassigned_cycle').strip()
        self.levy_route_group = parser.get('labels', 'levy_route_group').strip().lower()
        self.money_q = Decimal(1).scaleb(-self.money_scale)
        self.volume_q = Decimal(1).scaleb(-self.volume_scale)

    def quantize_money(self, value):
        return value.quantize(self.money_q, rounding=self.rounding)

    def quantize_volume(self, value):
        return value.quantize(self.volume_q, rounding=self.rounding)


def read_csv_rows(path, delimiter=','):
    with open(path, newline='', encoding='utf-8') as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            header = [trim(h) for h in next(reader)]
        except StopIteration:
            return []
        rows = []
        for raw in reader:
            if not raw:
                continue
            row = {}
            for index, name in enumerate(header):
                row[name] = raw[index] if index < len(raw) else ''
            rows.append(row)
        return rows


class Reference:
    def __init__(self, data_dir, policy):
        self.policy = policy
        self._load_accounts(os.path.join(data_dir, 'accounts.csv'))
        self._load_zones(os.path.join(data_dir, 'service_zones.csv'))
        self._load_sites(os.path.join(data_dir, 'meter_sites.csv'))
        self._load_collectors(os.path.join(data_dir, 'collectors.csv'))
        self._load_tariffs(os.path.join(data_dir, 'tariff_catalogue.csv'))
        self._load_rates(os.path.join(data_dir, 'currency_rates.csv'))
        self._load_calendar(os.path.join(data_dir, 'billing_calendar.json'))

    def _load_accounts(self, path):
        best = {}
        for index, row in enumerate(read_csv_rows(path)):
            account_id = trim(row.get('account_id', ''))
            revised_at = trim(row.get('revised_at', ''))
            key = (revised_at, index)
            if account_id in best and best[account_id][0] >= key:
                continue
            best[account_id] = (key, {
                'account_id': account_id,
                'tariff_class': trim(row.get('tariff_class', '')).lower(),
                'service_postcode': trim(row.get('service_postcode', '')),
                'opening_credit_minor': trim(row.get('opening_credit_minor', '')),
                'opening_currency': trim(row.get('opening_currency', '')).upper(),
            })
        self.accounts = {k: v[1] for k, v in best.items()}

    def _load_zones(self, path):
        self.zone_rows = {}
        self.zone_parent = {}
        for row in read_csv_rows(path):
            prefix = trim(row.get('postcode_prefix', ''))
            zone = trim(row.get('zone', '')).lower()
            parent = trim(row.get('parent_zone', '')).lower()
            self.zone_rows[prefix] = {
                'zone': zone,
                'default_currency': trim(row.get('default_currency', '')).upper(),
            }
            self.zone_parent[zone] = parent

    def top_zone(self, zone):
        seen = set()
        current = zone
        while True:
            parent = self.zone_parent.get(current, '')
            if not parent or parent in seen:
                return current
            seen.add(current)
            current = parent

    def _load_sites(self, path):
        self.sites = {}
        self.site_capacity = {}
        self.meter_rows = []
        for row in read_csv_rows(path):
            tariff_code = trim(row.get('tariff_code', ''))
            site = trim(row.get('meter_site', ''))
            installed = int(trim(row.get('installed_litres', '0')))
            floor = int(trim(row.get('service_floor_litres', '0')))
            self.sites.setdefault(site, {
                'postcode': trim(row.get('postcode', '')),
                'offset': int(trim(row.get('utc_offset_minutes', '0'))),
            })
            totals = self.site_capacity.setdefault(tariff_code, [0, 0])
            totals[0] += installed
            totals[1] += floor
            self.meter_rows.append((tariff_code, installed))

    def _load_collectors(self, path):
        self.collectors = {}
        for row in read_csv_rows(path):
            collector = trim(row.get('collector', '')).lower()
            self.collectors[collector] = trim(row.get('route_group', '')).lower()

    def _load_tariffs(self, path):
        self.tariffs = {}
        for row in read_csv_rows(path):
            code = trim(row.get('tariff_code', ''))
            self.tariffs[code] = {
                'category': trim(row.get('category', '')).lower(),
                'unit_volume_litres': Decimal(trim(row.get('unit_volume_litres', '0'))),
            }

    def _load_rates(self, path):
        table = collections.defaultdict(dict)
        for row in read_csv_rows(path):
            currency = trim(row.get('currency', '')).upper()
            rate_date = trim(row.get('rate_date', ''))
            table[currency][rate_date] = Decimal(trim(row.get('usd_rate', '0')))
        self.rates = {}
        for currency, by_date in table.items():
            dates = sorted(by_date)
            self.rates[currency] = (dates, [by_date[d] for d in dates])

    def lookup_rate(self, currency, posting_date):
        entry = self.rates.get(currency)
        if not entry:
            return None
        dates, values = entry
        index = bisect.bisect_right(dates, posting_date) - 1
        if index < 0:
            return None
        return dates[index], values[index]

    def _load_calendar(self, path):
        with open(path, encoding='utf-8') as handle:
            doc = json.load(handle)
        self.cycles = [(trim(c['opens']), trim(c['closes']), trim(c['cycle']))
                       for c in doc.get('cycles', [])]

    def billing_cycle(self, posting_date):
        for opens, closes, cycle in self.cycles:
            if opens <= posting_date <= closes:
                return cycle
        return self.policy.unassigned_cycle


# --------------------------------------------------------------------------
# amendments
# --------------------------------------------------------------------------

def load_amendments(path):
    """Return {(target, field): value} keeping the winning amendment."""
    if not os.path.exists(path):
        return {}
    best = {}
    with open(path, encoding='utf-8', errors='replace') as handle:
        for index, line in enumerate(handle):
            match = AMENDMENT_RE.match(line.rstrip('\n'))
            if not match:
                continue
            key = (trim(match.group('target')), trim(match.group('field')))
            rank = (trim(match.group('ts')), index)
            if key in best and best[key][0] > rank:
                continue
            best[key] = (rank, match.group('value'))
    return {k: v[1] for k, v in best.items()}


# --------------------------------------------------------------------------
# reading files
# --------------------------------------------------------------------------

def load_readings(data_dir):
    """Return (records, broken) where a record is (source, fields)."""
    records = []
    broken = collections.Counter()

    path = os.path.join(data_dir, CONSUMPTION)
    if os.path.exists(path):
        for row in read_csv_rows(path):
            records.append((CONSUMPTION,
                            {c: row.get(c, '') for c in COLUMNS[CONSUMPTION]}))

    path = os.path.join(data_dir, REMITTANCES)
    if os.path.exists(path):
        for row in read_csv_rows(path, delimiter='\t'):
            records.append((REMITTANCES,
                            {c: row.get(c, '') for c in COLUMNS[REMITTANCES]}))

    path = os.path.join(data_dir, LEVIES)
    if os.path.exists(path):
        with open(path, encoding='utf-8') as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    doc = json.loads(line)
                except ValueError:
                    broken[LEVIES] += 1
                    continue
                if not isinstance(doc, dict):
                    broken[LEVIES] += 1
                    continue
                records.append((LEVIES, {c: doc.get(c, '') for c in COLUMNS[LEVIES]}))

    path = os.path.join(data_dir, LEGACY)
    if os.path.exists(path):
        with open(path, encoding='latin-1') as handle:
            for line in handle:
                line = line.rstrip('\n').rstrip('\r')
                if not line.strip():
                    continue
                if line.lstrip()[0] == '#':
                    continue
                parts = line.split('|')
                if len(parts) != 11:
                    broken[LEGACY] += 1
                    continue
                records.append((LEGACY, dict(zip(COLUMNS[LEGACY], parts))))

    return records, broken


# --------------------------------------------------------------------------
# posting one reading
# --------------------------------------------------------------------------

def parse_units(value):
    text = trim(value)
    if not isinstance(text, str) or not UINT_RE.fullmatch(text):
        raise Skip()
    return int(text)


def parse_decimal(value):
    text = trim(value)
    if not isinstance(text, str) or not DEC_RE.fullmatch(text):
        raise Skip()
    return Decimal(text)


def parse_timestamp(value, utc=False):
    text = trim(value)
    if not isinstance(text, str):
        raise Skip()
    if utc and text.endswith('Z'):
        text = text[:-1]
    if not TS_RE.fullmatch(text):
        raise Skip()
    try:
        return datetime.strptime(text, '%Y-%m-%dT%H:%M:%S')
    except ValueError:
        raise Skip()


def post_reading(source, fields, amended, ref, policy):
    """Return posting details, or raise Skip when the reading is malformed."""
    reading_id = trim(fields.get('reading_id', ''))
    account_id = trim(fields.get('account_id', ''))
    account = ref.accounts.get(account_id)
    if account is None:
        raise Skip()
    tariff_code = trim(fields.get('tariff_code', ''))
    tariff = ref.tariffs.get(tariff_code)
    if tariff is None:
        raise Skip()

    if source == LEVIES:
        kind = trim(fields.get('kind', ''))
        kind = kind.lower() if isinstance(kind, str) else ''
        if kind not in LEVY_KINDS:
            raise Skip()
        raw_amount = fields.get('amount_minor', '')
        if 'amount_minor' in amended:
            # an amendment writes text, which is read back as a signed integer
            if not isinstance(raw_amount, str) or not INT_RE.fullmatch(raw_amount.strip()):
                raise Skip()
            amount_minor = int(raw_amount.strip())
        elif isinstance(raw_amount, int) and not isinstance(raw_amount, bool):
            amount_minor = raw_amount
        else:
            raise Skip()
        units = 0
        gross = Decimal(amount_minor) / Decimal(100)
        meter_site = None
        route_group = policy.levy_route_group
        postcode = account['service_postcode']
        local = parse_timestamp(fields.get('read_ts', ''), utc=True)
        instant = local
    else:
        meter_site = trim(fields.get('meter_site', ''))
        site = ref.sites.get(meter_site)
        if site is None:
            raise Skip()
        collector = trim(fields.get('collector', ''))
        collector = collector.lower() if isinstance(collector, str) else ''
        route_group = ref.collectors.get(collector)
        if route_group is None:
            raise Skip()
        units = parse_units(fields.get('units_consumed', ''))
        if source == CONSUMPTION:
            kind = 'consumption'
            gross = -(Decimal(units) * parse_decimal(fields.get('rate_per_unit', '')))
        elif source == REMITTANCES:
            kind = 'remittance'
            gross = abs(parse_decimal(fields.get('remit_amount', '')))
        else:
            kind = trim(fields.get('kind', ''))
            kind = kind.lower() if isinstance(kind, str) else ''
            if kind not in LEGACY_KINDS:
                raise Skip()
            amount = abs(parse_decimal(fields.get('amount', '')))
            gross = -amount if kind in ('consumption', 'surcharge') else amount
        postcode = site['postcode']
        local = parse_timestamp(fields.get('read_ts', ''))
        instant = local - timedelta(minutes=site['offset'])

    prefix = postcode.split('-', 1)[0].strip() if isinstance(postcode, str) else ''
    zone_row = ref.zone_rows.get(prefix)
    if zone_row is None:
        raise Skip()
    zone = ref.top_zone(zone_row['zone'])

    currency = trim(fields.get('currency', ''))
    currency = currency.upper() if isinstance(currency, str) else ''
    if not currency:
        currency = zone_row['default_currency']

    posting_date = instant.strftime('%Y-%m-%d')
    found = ref.lookup_rate(currency, posting_date)
    if found is None:
        raise Skip()
    rate_date, usd_rate = found

    product = gross * usd_rate * Decimal(100)
    posted_usd_cents = int(policy.quantize_money(product))

    return {
        'record': {
            'account_id': account_id,
            'billing_cycle': ref.billing_cycle(posting_date),
            'category': tariff['category'],
            'currency': currency,
            'kind': kind,
            'meter_site': meter_site,
            'posted_usd_cents': posted_usd_cents,
            'posting_date': posting_date,
            'reading_id': reading_id,
            'route_group': route_group,
            'source': source,
            'tariff_class': account['tariff_class'],
            'tariff_code': tariff_code,
            'units': units,
            'utc_instant': instant.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'zone': zone,
        },
        'instant': instant,
        'carry_back': rate_date != posting_date,
        'day_shift': posting_date != local.strftime('%Y-%m-%d'),
        'half_cent': (abs(product) % Decimal(1)) == Decimal('0.5'),
    }


def net_units(record):
    if record['kind'] == 'consumption':
        return record['units']
    if record['kind'] == 'remittance':
        return -record['units']
    return 0


# --------------------------------------------------------------------------
# serialization helpers
# --------------------------------------------------------------------------

def write_json(path, payload):
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, sort_keys=True, indent=2)
        handle.write('\n')


def bucket_report(records, held_records, field, label_key, label, extra=None):
    chosen = [r for r in records if r[field] == label]
    held = [r for r in held_records if r[field] == label]
    by_kind = collections.Counter()
    by_category = collections.Counter()
    for record in chosen:
        by_kind[record['kind']] += record['posted_usd_cents']
        by_category[record['category']] += record['posted_usd_cents']
    payload = {
        label_key: label,
        'event_count': len(chosen),
        'total_usd_cents': sum(r['posted_usd_cents'] for r in chosen),
        'net_units': sum(net_units(r) for r in chosen),
        'held_count': len(held),
        'accounts': sorted({r['account_id'] for r in chosen}),
        'by_kind': dict(by_kind),
        'by_category': dict(by_category),
    }
    if extra:
        payload.update(extra)
    return payload


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def run(data_dir, out_dir):
    policy = Policy(os.path.join(data_dir, 'policy.ini'))
    ref = Reference(data_dir, policy)
    amendments = load_amendments(os.path.join(data_dir, 'amendments.log'))
    records, broken = load_readings(data_dir)

    present_files = [name for name in READING_FILES
                     if os.path.isfile(os.path.join(data_dir, name))]

    known_ids = {trim(fields.get('reading_id', '')) for source, fields in records}

    amended_ids = set()
    amended_fields = []
    for source, fields in records:
        reading_id = trim(fields.get('reading_id', ''))
        applied = set()
        for column in COLUMNS[source]:
            if column == 'reading_id':
                continue
            value = amendments.get((reading_id, column))
            if value is not None:
                fields[column] = value
                applied.add(column)
                amended_ids.add(reading_id)
        amended_fields.append(applied)

    unmatched = sorted({target for target, field in amendments
                        if target not in known_ids})

    consumption_ids = {trim(f.get('reading_id', '')) for s, f in records
                       if s == CONSUMPTION}

    skipped_by_source = collections.Counter({name: 0 for name in present_files})
    for name, count in broken.items():
        skipped_by_source[name] += count
    held_by_source = collections.Counter({name: 0 for name in present_files})

    orphan_ids = []
    postings = []
    skipped_consumption_ids = set()

    for (source, fields), applied in zip(records, amended_fields):
        reading_id = trim(fields.get('reading_id', ''))
        if source == REMITTANCES:
            link = trim(fields.get('charge_reading_id', ''))
            if isinstance(link, str) and link and link not in consumption_ids:
                orphan_ids.append(reading_id)
                continue
        try:
            posting = post_reading(source, fields, applied, ref, policy)
        except Skip:
            skipped_by_source[source] += 1
            if source == CONSUMPTION:
                skipped_consumption_ids.add(reading_id)
            continue
        posting['link'] = (trim(fields.get('charge_reading_id', ''))
                           if source == REMITTANCES else '')
        postings.append(posting)

    # ---- prepay wallet gate -------------------------------------------
    by_account = collections.defaultdict(list)
    for posting in postings:
        by_account[posting['record']['account_id']].append(posting)

    wallet_closing = 0
    underfunded = 0
    posted = []
    held = []
    for account_id in sorted(ref.accounts):
        account = ref.accounts[account_id]
        opening_gross = Decimal(account['opening_credit_minor']) / Decimal(100)
        found = ref.lookup_rate(account['opening_currency'], policy.opening_rate_date)
        rate = found[1] if found else Decimal(0)
        balance = int(policy.quantize_money(opening_gross * rate * Decimal(100)))
        floor = policy.floors[account['tariff_class']]
        if balance < floor:
            underfunded += 1
        entries = by_account.get(account_id, [])
        entries.sort(key=lambda p: (p['instant'], p['record']['reading_id']))
        for posting in entries:
            amount = posting['record']['posted_usd_cents']
            if amount >= 0 or balance + amount >= floor:
                balance += amount
                posted.append(posting)
            else:
                held.append(posting)
        wallet_closing += balance

    held_records = [p['record'] for p in held]
    for record in held_records:
        held_by_source[record['source']] += 1

    posted_records = sorted((p['record'] for p in posted),
                            key=lambda r: r['reading_id'])

    # ---- artifacts ----------------------------------------------------
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, 'normalized.jsonl'), 'w', encoding='utf-8') as handle:
        for record in posted_records:
            handle.write(json.dumps(record, sort_keys=True,
                                    separators=(',', ':')) + '\n')

    field_of = {'by_zone': 'zone', 'by_tariff_class': 'tariff_class', 'by_kind': 'kind',
                'by_category': 'category', 'by_route_group': 'route_group',
                'by_billing_cycle': 'billing_cycle', 'by_source': 'source'}
    maps = {name: collections.Counter() for name in field_of}
    records_by_source = collections.Counter()
    for record in posted_records:
        for name, field in field_of.items():
            maps[name][record[field]] += record['posted_usd_cents']
        records_by_source[record['source']] += 1

    summary = {
        'event_count': len(posted_records),
        'skipped_count': sum(skipped_by_source.values()),
        'held_count': len(held_records),
        'orphan_remittance_count': len(orphan_ids),
        'total_usd_cents': sum(r['posted_usd_cents'] for r in posted_records),
        'net_units': sum(net_units(r) for r in posted_records),
        'wallet_closing_usd_cents': wallet_closing,
    }
    for name in maps:
        summary[name] = dict(maps[name])
    write_json(os.path.join(out_dir, 'summary.json'), summary)

    input_files = sorted(name for name in os.listdir(data_dir)
                         if os.path.isfile(os.path.join(data_dir, name)))
    data_quality = {
        'input_files': input_files,
        'records_by_source': dict(records_by_source),
        'skipped_by_source': dict(skipped_by_source),
        'held_by_source': dict(held_by_source),
        'skipped_count': sum(skipped_by_source.values()),
        'held_count': len(held_records),
        'orphan_remittance_count': len(orphan_ids),
        'held_reading_ids': sorted({r['reading_id'] for r in held_records}),
        'orphan_remittance_ids': sorted(set(orphan_ids)),
        'unmatched_amendment_targets': unmatched,
    }
    write_json(os.path.join(out_dir, 'data_quality.json'), data_quality)

    tariff_stats = collections.defaultdict(
        lambda: {'event_count': 0, 'total_usd_cents': 0, 'net_units': 0})
    for record in posted_records:
        stats = tariff_stats[record['tariff_code']]
        stats['event_count'] += 1
        stats['total_usd_cents'] += record['posted_usd_cents']
        stats['net_units'] += net_units(record)
    tariffs = []
    for code in sorted(ref.tariffs):
        info = ref.tariffs[code]
        stats = tariff_stats.get(code, {'event_count': 0, 'total_usd_cents': 0,
                                        'net_units': 0})
        installed, floor = ref.site_capacity.get(code, (0, 0))
        volume = (Decimal(stats['net_units']) * info['unit_volume_litres']
                  * policy.litres_per_kilolitre)
        tariffs.append({
            'tariff_code': code,
            'category': info['category'],
            'event_count': stats['event_count'],
            'total_usd_cents': stats['total_usd_cents'],
            'net_units': stats['net_units'],
            'installed_litres': installed,
            'service_floor_litres': floor,
            'net_volume_litres': int(policy.quantize_volume(volume)),
        })
    write_json(os.path.join(out_dir, 'product_summary.json'), {'tariffs': tariffs})

    for zone in TOP_ZONES:
        payload = bucket_report(posted_records, held_records, 'zone', 'zone', zone)
        write_json(os.path.join(out_dir, 'region_%s.json' % zone), payload)

    for cls in TARIFF_CLASSES:
        payload = bucket_report(
            posted_records, held_records, 'tariff_class', 'tariff_class', cls,
            extra={'disconnection_floor_usd_cents': policy.floors[cls]})
        write_json(os.path.join(out_dir, 'segment_%s.json' % cls), payload)

    # ---- closing report ------------------------------------------------
    stale = sum(1 for p in posted
                if p['record']['source'] == REMITTANCES and p['link']
                and p['link'] in skipped_consumption_ids)
    return {
        'held_value_usd_cents': sum(r['posted_usd_cents'] for r in held_records),
        'held_accounts': len({r['account_id'] for r in held_records}),
        'carry_back_rate_events': sum(1 for p in posted if p['carry_back']),
        'day_shift_events': sum(1 for p in posted if p['day_shift']),
        'amended_readings': len(amended_ids),
        'half_cent_events': sum(1 for p in posted if p['half_cent']),
        'underfunded_accounts': underfunded,
        'uncatalogued_capacity_litres': sum(
            litres for code, litres in ref.meter_rows if code not in ref.tariffs),
        'stale_link_remittances': stale,
    }


def main(argv):
    if len(argv) != 3:
        print('usage: transform.py <DATA_DIR> <OUT_DIR>', file=sys.stderr)
        return 2
    report = run(argv[1], argv[2])
    for key in sorted(report):
        print('%s: %s' % (key, report[key]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
