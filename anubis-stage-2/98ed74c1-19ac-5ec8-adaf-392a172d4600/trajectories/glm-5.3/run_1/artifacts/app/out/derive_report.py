#!/usr/bin/env python3
"""Derive the nine reports of one extract of the Harbourline PM2.5 network.

Usage: python3 derive_report.py DATA_DIR OUT_DIR

The extract in DATA_DIR is read as the extract's record dictionary describes,
the extract's monitoring standard is applied to it, and the nine reports the
extract's report layout names are written into OUT_DIR. Only the Python
standard library is used; nothing outside DATA_DIR is read and nothing outside
OUT_DIR is written.
"""

import csv
import io
import json
import os
import sys
from bisect import bisect_right
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

REPORTS = (
    'summary.json',
    'policy_audit.json',
    'data_quality.json',
    'region_North.json',
    'region_South.json',
    'region_West.json',
    'region_East.json',
    'segment_commercial.json',
    'segment_public.json',
)
DISTRICTS = ('North', 'South', 'West', 'East')
OPERATOR_CLASSES = ('commercial', 'public')
MAX_CLOCK_OFFSET = 19
HOURS_PER_DAY = 24
MINUTES_PER_HOUR = 60
MINUTES_PER_DAY = 24 * MINUTES_PER_HOUR
DESIGN_RANK_STEP = 50
EPOCH = datetime(1970, 1, 1)
TENTH = Decimal(1)


# ------------------------------------------------------------------ file input


def read_text(path):
    with open(path, 'rb') as handle:
        raw = handle.read()
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]
    return raw.decode('utf-8')


def read_csv(path):
    text = read_text(path)
    return list(csv.DictReader(io.StringIO(text)))


def read_json(path):
    return json.loads(read_text(path))


def field(row, name):
    """One CSV field, as text without surrounding spaces; empty when absent."""
    return (row.get(name) or '').strip()


def whole_number(text):
    """A written whole number, as an int; an empty field as None."""
    text = (text or '').strip()
    return int(text) if text else None


# ------------------------------------------------------------------- time text


def parse_minute(text):
    """A written time, as whole minutes since the start of 1970-01-01."""
    moment = datetime.strptime((text or '').strip(), '%Y-%m-%dT%H:%M')
    span = moment - EPOCH
    return span.days * MINUTES_PER_DAY + span.seconds // MINUTES_PER_HOUR


def parse_day(text):
    """A written date, as whole days since 1970-01-01."""
    return (datetime.strptime((text or '').strip(), '%Y-%m-%d') - EPOCH).days


def day_text(day):
    """A whole day since 1970-01-01, written YYYY-MM-DD."""
    moment = EPOCH + timedelta(days=day)
    return '%04d-%02d-%02d' % (moment.year, moment.month, moment.day)


# --------------------------------------------------------------------- labels


def channel_label(text):
    """A channel label's written form: capitals, no surrounding spaces."""
    return (text or '').strip().upper()


def id_number(identifier, prefix):
    """The whole number an id carries, or None when the id is not that form."""
    if not identifier.startswith(prefix):
        return None
    digits = identifier[len(prefix):]
    return int(digits) if digits.isdigit() else None


def id_sort_key(identifier, prefix):
    """Ids of the given form by their number, any other id after them."""
    number = id_number(identifier, prefix)
    if number is None:
        return (1, 0, identifier)
    return (0, number, identifier)


# ---------------------------------------------------------------------- times


class Zone:
    """The local standard time and the civil time of the network zone."""

    def __init__(self, rules):
        self.offset = int(rules['standard_offset_minutes'])
        self.saving = sorted(
            (parse_minute(period['begins']),
             parse_minute(period['ends']),
             int(period['shift_minutes']))
            for period in (rules.get('daylight_saving') or [])
        )

    def local_of(self, instant):
        """The local standard time of a true UTC instant."""
        return instant + self.offset

    def instant_of_civil(self, civil):
        """The true UTC instant that a civil time names."""
        local = civil
        for begins, ends, shift in reversed(self.saving):
            if begins <= civil < ends:
                local = civil - shift
                break
        return local - self.offset


# ------------------------------------------------------------ policy and spans


def load_policy(data_dir, revision):
    """The network policy in force."""
    for name in sorted(os.listdir(data_dir)):
        if not name.startswith('network_policy'):
            continue
        document = read_json(os.path.join(data_dir, name))
        if document.get('revision') == revision:
            return document
    raise SystemExit('no network policy of revision %s' % revision)


def load_asset_tags(data_dir):
    """Each asset tag, as the unit it names over intervals of time."""
    tags = {}
    for row in read_csv(os.path.join(data_dir, 'asset_tags.csv')):
        end = field(row, 'valid_to_utc')
        tags.setdefault(field(row, 'asset_tag'), []).append(
            (parse_minute(field(row, 'valid_from_utc')),
             parse_minute(end) if end else None,
             field(row, 'unit_id')))
    return tags


def load_span_register(data_dir, revision, tags):
    """The span factor in force of each unit, over time.

    Each unit maps to parallel lists of effective instants and factors; the
    factor in force at an instant is the one of the latest live set entry at or
    before it, the entry of the higher number when two share an instant.
    """
    rows = None
    for name in sorted(os.listdir(data_dir)):
        if not name.startswith('span_register') or not name.endswith('.csv'):
            continue
        candidate = read_csv(os.path.join(data_dir, name))
        if candidate and all(field(row, 'revision') == revision for row in candidate):
            rows = candidate
            break
    if rows is None:
        raise SystemExit('no span register of revision %s' % revision)

    def resolve(reference, instant):
        """The unit a register entry's unit_ref names at an instant."""
        if id_number(reference, 'AQ') is not None:
            return reference
        for begin, end, unit in tags.get(reference, ()):
            if begin <= instant and (end is None or instant < end):
                return unit
        return None

    entries = []
    by_id = {}
    by_number = {}
    for row in rows:
        entry_id = field(row, 'entry_id')
        number = id_number(entry_id, 'E')
        effective = field(row, 'effective_utc')
        factor = field(row, 'span_factor')
        entry = {
            'id': entry_id,
            'number': number,
            'action': field(row, 'action'),
            'unit_ref': field(row, 'unit_ref'),
            'effective': parse_minute(effective) if effective else None,
            'factor': Decimal(factor) if factor else None,
            'target': field(row, 'target_entry'),
            'order': (0, number, entry_id) if number is not None else (1, 0, entry_id),
        }
        entries.append(entry)
        by_id.setdefault(entry_id, entry)
        if number is not None and number not in by_number:
            by_number[number] = entry

    def named(target):
        """The register entry an entry id names, or None."""
        if not target:
            return None
        if target in by_id:
            return by_id[target]
        return by_number.get(id_number(target, 'E'))

    void = set()
    for entry in entries:
        if entry['action'] != 'withdraw':
            continue
        target = named(entry['target'])
        if target is not None and target['action'] in ('set', 'amend'):
            void.add(id(target))

    live_sets = []
    for entry in entries:
        if entry['action'] != 'set' or id(entry) in void:
            continue
        if entry['effective'] is None or entry['factor'] is None:
            continue
        if resolve(entry['unit_ref'], entry['effective']) is None:
            continue
        live_sets.append(entry)
    live_ids = set(id(entry) for entry in live_sets)

    amends = {}
    for entry in entries:
        if entry['action'] != 'amend' or id(entry) in void or entry['factor'] is None:
            continue
        target = named(entry['target'])
        if target is None or id(target) not in live_ids:
            continue
        amends.setdefault(id(target), []).append(entry)

    register = {}
    for entry in live_sets:
        factor = entry['factor']
        candidates = amends.get(id(entry))
        if candidates:
            factor = max(candidates, key=lambda other: other['order'])['factor']
        unit = resolve(entry['unit_ref'], entry['effective'])
        register.setdefault(unit, []).append((entry['effective'], entry['order'], factor))
    factors = {}
    for unit, entries_of_unit in register.items():
        entries_of_unit.sort(key=lambda item: item[:2])
        factors[unit] = ([item[0] for item in entries_of_unit],
                         [item[2] for item in entries_of_unit])
    return factors


def factor_in_force(factors, instant):
    """The span factor in force for a unit at an instant, or None."""
    if not factors:
        return None
    instants, values = factors
    index = bisect_right(instants, instant) - 1
    if index < 0:
        return None
    return values[index]


# ------------------------------------------------------------------- the clock


def infer_offsets(cards, channels, journal):
    """Each unit's clock offset and the packets its card rows were sent as.

    A unit's clock offset is the whole number of minutes within the bound the
    record dictionary gives that lets the most of its card rows be sent as a
    journal entry on its channel, at the row's frame, in the true minute its
    averaging interval ends.
    """
    offsets = {}
    received = {}
    for unit, rows in cards.items():
        entries = journal.get(channels.get(unit) or '')
        if not entries:
            offsets[unit] = 0
            received[unit] = 0
            continue
        best_offset = 0
        best_count = 0
        for offset in range(-MAX_CLOCK_OFFSET, MAX_CLOCK_OFFSET + 1):
            count = 0
            for stamp, frame, _raw, _status in rows:
                if (stamp - offset, frame) in entries:
                    count += 1
            if count > best_count:
                best_offset, best_count = offset, count
        offsets[unit] = best_offset
        received[unit] = best_count
    return offsets, received


# ---------------------------------------------------------------------- derive


def derive(data_dir):
    """Read one extract and apply the monitoring standard to it."""
    manifest = read_json(os.path.join(data_dir, 'extract_manifest.json'))
    policy = load_policy(data_dir, manifest['policy_revision'])
    zone = Zone(read_json(os.path.join(data_dir, 'zone_rules.json')))
    tags = load_asset_tags(data_dir)
    factors = load_span_register(data_dir, manifest['span_register_revision'], tags)

    first_day = parse_day(manifest['first_day'])
    days = int(manifest['days'])
    beyond_day = first_day + days
    daily_standard = int(Decimal(policy['daily_standard']) * 10)
    hour_min_readings = int(policy['hour_min_readings'])
    day_min_hours = int(policy['day_min_hours'])
    required_valid_days = -(-days * int(policy['site_min_valid_day_percent']) // 100)

    sites = []
    for row in read_csv(os.path.join(data_dir, 'site_register.csv')):
        sites.append({
            'site_id': field(row, 'site_id'),
            'site_name': field(row, 'site_name'),
            'district': field(row, 'district'),
            'operator_class': field(row, 'operator_class'),
        })
    sites.sort(key=lambda site: id_sort_key(site['site_id'], 'S'))
    known_sites = set(site['site_id'] for site in sites)

    channels = {}
    deployments = {}
    for row in read_csv(os.path.join(data_dir, 'unit_deployments.csv')):
        unit = field(row, 'unit_id')
        removed = field(row, 'removed_utc')
        channels.setdefault(unit, channel_label(field(row, 'channel')))
        deployments.setdefault(unit, []).append(
            (parse_minute(field(row, 'installed_utc')),
             parse_minute(removed) if removed else None,
             field(row, 'site_id')))
    starts = {}
    for unit, periods in deployments.items():
        periods.sort(key=lambda period: (period[0], period[2]))
        starts[unit] = [period[0] for period in periods]

    def site_of(unit, instant):
        """The site a unit stood at at an instant, or None."""
        periods = deployments.get(unit)
        if not periods:
            return None
        index = bisect_right(starts[unit], instant) - 1
        if index < 0:
            return None
        installed, removed, site = periods[index]
        if removed is not None and instant >= removed:
            return None
        return site

    maintenance = {}
    log = read_json(os.path.join(data_dir, 'maintenance_log.json'))
    for entry in log.get('entries') or []:
        begins = parse_minute(entry['begins'])
        ends = parse_minute(entry['ends'])
        if log.get('time_basis') == 'civil':
            begins = zone.instant_of_civil(begins)
            ends = zone.instant_of_civil(ends)
        maintenance.setdefault(field(entry, 'site_id'), []).append((begins, ends))

    cards = {}
    card_rows = 0
    for row in read_csv(os.path.join(data_dir, 'card_readings.csv')):
        unit = field(row, 'unit_id')
        cards.setdefault(unit, []).append(
            (parse_minute(field(row, 'card_stamp')),
             whole_number(field(row, 'frame')),
             whole_number(field(row, 'pm25_raw')),
             field(row, 'status')))
        card_rows += 1

    journal = {}
    journal_entries = 0
    for row in read_csv(os.path.join(data_dir, 'receipt_journal.csv')):
        label = channel_label(field(row, 'channel'))
        journal.setdefault(label, set()).add(
            (parse_minute(field(row, 'received_utc')), whole_number(field(row, 'frame'))))
        journal_entries += 1

    offsets, received = infer_offsets(cards, channels, journal)

    # --- the readings, their hours and their exclusions
    exclusions = {reason: 0 for reason in
                  ('outside_window', 'undeployed', 'missing_value',
                   'flagged', 'uncalibrated', 'maintenance')}
    valid_readings = 0
    excluded_readings = 0
    site_hours = {}
    site_valid_readings = {}
    for unit, rows in cards.items():
        offset = offsets[unit]
        unit_factors = factors.get(unit)
        for stamp, _frame, raw, status in rows:
            instant = stamp - offset
            local = zone.local_of(instant)
            hour = local // MINUTES_PER_HOUR
            if local % MINUTES_PER_HOUR == 0:
                hour -= 1  # the reading closes the hour its interval ends
            if not first_day <= hour // HOURS_PER_DAY < beyond_day:
                exclusions['outside_window'] += 1
                excluded_readings += 1
                continue
            site = site_of(unit, instant)
            factor = factor_in_force(unit_factors, instant)
            kept = True
            if site is None or site not in known_sites:
                exclusions['undeployed'] += 1
                kept = False
            if raw is None:
                exclusions['missing_value'] += 1
                kept = False
            if status:
                exclusions['flagged'] += 1
                kept = False
            if factor is None:
                exclusions['uncalibrated'] += 1
                kept = False
            if site is not None and any(
                    begins <= instant < ends
                    for begins, ends in maintenance.get(site, ())):
                exclusions['maintenance'] += 1
                kept = False
            if not kept:
                excluded_readings += 1
                continue
            value = int((Decimal(raw) * factor).quantize(TENTH, rounding=ROUND_HALF_UP))
            valid_readings += 1
            site_valid_readings[site] = site_valid_readings.get(site, 0) + 1
            hours = site_hours.setdefault(site, {})
            bucket = hours.get(hour)
            if bucket is None:
                hours[hour] = bucket = [0, 0]
            bucket[0] += value
            bucket[1] += 1

    # --- hours to days, days to findings
    site_results = []
    for site in sites:
        site_id = site['site_id']
        day_counts = {}
        day_totals = {}
        valid_hours = 0
        for hour, (total, count) in site_hours.get(site_id, {}).items():
            if count < hour_min_readings:
                continue
            valid_hours += 1
            day = hour // HOURS_PER_DAY
            day_counts[day] = day_counts.get(day, 0) + 1
            day_totals[day] = day_totals.get(day, 0) + total // count
        daily_values = {}
        complete_days = 0
        exceedance_days = 0
        for day, count in day_counts.items():
            mean = day_totals[day] // count
            if count < day_min_hours and mean <= daily_standard:
                continue
            daily_values[day] = mean
            if count >= day_min_hours:
                complete_days += 1
            if mean > daily_standard:
                exceedance_days += 1
        ranked = sorted(daily_values.values(), reverse=True)
        if ranked:
            design_rank = 1 + (len(ranked) - 1) // DESIGN_RANK_STEP
            design_value = ranked[design_rank - 1]
        else:
            design_rank = None
            design_value = None
        if design_value is not None and design_value > daily_standard:
            status = 'nonattainment'
        elif len(ranked) >= required_valid_days:
            status = 'attainment'
        else:
            status = 'incomplete'
        site_results.append({
            'site_id': site_id,
            'site_name': site['site_name'],
            'district': site['district'],
            'operator_class': site['operator_class'],
            'valid_hours': valid_hours,
            'valid_days': len(daily_values),
            'complete_days': complete_days,
            'exceedance_days': exceedance_days,
            'design_rank': design_rank,
            'design_value': design_value,
            'status': status,
            'valid_readings': site_valid_readings.get(site_id, 0),
            'daily_values': daily_values,
        })

    return {
        'manifest': manifest,
        'policy': policy,
        'first_day': first_day,
        'days': days,
        'beyond_day': beyond_day,
        'daily_standard': daily_standard,
        'hour_min_readings': hour_min_readings,
        'day_min_hours': day_min_hours,
        'required_valid_days': required_valid_days,
        'card_rows': card_rows,
        'valid_readings': valid_readings,
        'excluded_readings': excluded_readings,
        'exclusions': exclusions,
        'journal_entries': journal_entries,
        'units': sorted(cards),
        'channels': channels,
        'card_counts': {unit: len(rows) for unit, rows in cards.items()},
        'received': received,
        'offsets': offsets,
        'site_results': site_results,
    }


# --------------------------------------------------------------------- reports


def rollup(members, key, name):
    """One district or operator rollup, as a report object."""
    report = {key: name}
    in_scope = any(member['status'] != 'incomplete' for member in members)
    if not in_scope:
        report['in_scope'] = False
        return report
    ranked = [member for member in members if member['design_value'] is not None]
    worst = None
    if ranked:
        best = min(ranked, key=lambda member: (-member['design_value'],
                                               id_sort_key(member['site_id'], 'S')))
        worst = {'site_id': best['site_id'], 'design_value': best['design_value']}
    report.update({
        'in_scope': True,
        'sites': [
            {
                'site_id': member['site_id'],
                'status': member['status'],
                'valid_readings': member['valid_readings'],
                'daily_values': {day_text(day): value
                                 for day, value in sorted(member['daily_values'].items())},
            }
            for member in members
        ],
        'valid_readings': sum(member['valid_readings'] for member in members),
        'exceedance_days': sum(member['exceedance_days'] for member in members),
        'worst_site': worst,
        'status': ('nonattainment'
                   if any(member['status'] == 'nonattainment' for member in members)
                   else 'attainment'),
    })
    return report


def build_reports(state):
    """The nine report objects, in the order the report layout gives."""
    sites = state['site_results']
    manifest = state['manifest']
    in_scope_by_site = {}

    district_reports = {}
    for district in DISTRICTS:
        members = [site for site in sites if site['district'] == district]
        report = rollup(members, 'district', district)
        district_reports[district] = report
        if report['in_scope']:
            for member in members:
                in_scope_by_site[member['site_id']] = True

    rolled_up = sum(site['valid_readings'] for site in sites
                    if in_scope_by_site.get(site['site_id']))

    with_design_value = [site for site in sites if site['design_value'] is not None]
    highest = None
    if with_design_value:
        best = min(with_design_value,
                   key=lambda site: (-site['design_value'],
                                     id_sort_key(site['site_id'], 'S')))
        highest = {'site_id': best['site_id'], 'value': best['design_value']}

    summary = {
        'report_id': manifest['report_id'],
        'first_day': manifest['first_day'],
        'days': state['days'],
        'card_rows': state['card_rows'],
        'valid_readings': state['valid_readings'],
        'valid_hours': sum(site['valid_hours'] for site in sites),
        'valid_days': sum(site['valid_days'] for site in sites),
        'exceedance_days': sum(site['exceedance_days'] for site in sites),
        'site_status_counts': {
            status: sum(1 for site in sites if site['status'] == status)
            for status in ('attainment', 'incomplete', 'nonattainment')
        },
        'highest_design_value': highest,
        'reconciliation': {
            'card_rows': state['card_rows'],
            'excluded_readings': state['excluded_readings'],
            'valid_readings': state['valid_readings'],
            'rolled_up_valid_readings': rolled_up,
            'residual': state['valid_readings'] - rolled_up,
        },
    }

    policy_audit = {
        'policy_revision': manifest['policy_revision'],
        'span_register_revision': manifest['span_register_revision'],
        'daily_standard_tenths': state['daily_standard'],
        'hour_min_readings': state['hour_min_readings'],
        'day_min_hours': state['day_min_hours'],
        'required_valid_days': state['required_valid_days'],
        'sites': [
            {
                'site_id': site['site_id'],
                'district': site['district'],
                'operator_class': site['operator_class'],
                'valid_days': site['valid_days'],
                'complete_days': site['complete_days'],
                'exceedance_days': site['exceedance_days'],
                'design_rank': site['design_rank'],
                'design_value': site['design_value'],
                'status': site['status'],
            }
            for site in sites
        ],
    }

    units = state['units']
    data_quality = {
        'journal_entries': state['journal_entries'],
        'excluded_readings': state['excluded_readings'],
        'exclusions': {reason: state['exclusions'][reason] for reason in
                       ('outside_window', 'undeployed', 'missing_value',
                        'flagged', 'uncalibrated', 'maintenance')},
        'units': [
            {
                'unit_id': unit,
                'channel': state['channels'].get(unit) or '',
                'card_rows': state['card_counts'].get(unit, 0),
                'received_packets': state['received'].get(unit, 0),
            }
            for unit in units
        ],
    }

    reports = [summary, policy_audit, data_quality]
    reports.extend(district_reports[district] for district in DISTRICTS)
    for operator_class in OPERATOR_CLASSES:
        members = [site for site in sites if site['operator_class'] == operator_class]
        reports.append(rollup(members, 'operator_class', operator_class))
    return reports


def write_reports(out_dir, reports):
    """Write each report and print its file name and byte count."""
    for name, report in zip(REPORTS, reports):
        payload = json.dumps(report, sort_keys=True, indent=2,
                             ensure_ascii=True) + '\n'
        blob = payload.encode('utf-8')
        with open(os.path.join(out_dir, name), 'wb') as handle:
            handle.write(blob)
        sys.stdout.write('%s %d\n' % (name, len(blob)))
        sys.stdout.flush()


def main(argv):
    if len(argv) != 2:
        sys.stderr.write('usage: derive_report.py DATA_DIR OUT_DIR\n')
        return 2
    data_dir, out_dir = argv
    if not os.path.isdir(data_dir):
        sys.stderr.write('no data directory %s\n' % data_dir)
        return 2
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    state = derive(data_dir)
    reports = build_reports(state)
    write_reports(out_dir, reports)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
