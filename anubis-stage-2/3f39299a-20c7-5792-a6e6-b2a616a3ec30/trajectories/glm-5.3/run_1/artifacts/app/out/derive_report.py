#!/usr/bin/env python3
"""Derive the road-salt season reports from a cooperative extract.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import csv
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from fractions import Fraction

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

UNIT_KG = {
    'short_ton': Fraction(90718474, 100000),
    'metric_tonne': Fraction(1000),
    'long_ton': Fraction(10160469088, 10000000),
}
ROUNDINGS = ('half_up', 'down', 'up')

STANDING_DEFAULTS = {
    'public_weight': 2,
    'commercial_weight': 1,
    'allocation_unit_kg': 500,
    'tie_break': 'lowest_customer_id',
    'deficit_threshold': '0.50',
    'bonus_composition': 'additive',
    'review_floor': '0.40',
    'review_round_limit': 1,
}
PARAM_NAMES = (
    'public_weight', 'commercial_weight', 'allocation_unit_kg', 'tie_break',
    'deficit_threshold', 'bonus_composition', 'review_floor', 'review_round_limit',
)


# --------------------------------------------------------------------------
# time
# --------------------------------------------------------------------------

def instant_key(dt):
    d = dt - EPOCH
    return d.days * 86400000000 + d.seconds * 1000000 + d.microseconds


def parse_instant(text):
    s = text.strip()
    if s.endswith('Z') or s.endswith('z'):
        s = s[:-1] + '+00:00'
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return instant_key(dt)


def parse_offset(text):
    s = text.strip()
    sign = -1 if s.startswith('-') else 1
    return sign * timedelta(hours=int(s[1:3]), minutes=int(s[4:6]))


def parse_wall(text):
    return datetime.strptime(text.strip(), '%Y-%m-%d %H:%M')


class CoopClock(object):
    def __init__(self, periods):
        self.periods = sorted(periods, key=lambda p: p[0])

    def instant(self, wall):
        chosen = self.periods[0][1] if self.periods else timezone.utc
        for frm, off in self.periods:
            if frm <= wall:
                chosen = off
            else:
                break
        return instant_key(wall.replace(tzinfo=timezone(chosen)))


# --------------------------------------------------------------------------
# io helpers
# --------------------------------------------------------------------------

def read_csv(path):
    with open(path, 'r', encoding='utf-8-sig', newline='') as fh:
        return list(csv.DictReader(fh))


def read_json(path):
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def read_jsonl(path):
    out = []
    with open(path, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def tonnes_to_kg(text):
    return int(Fraction(text.strip()) * 1000)


def round_half_up_fraction(value):
    return int(value + Fraction(1, 2))


def round_fraction(value, mode):
    if mode == 'half_up':
        return int(value + Fraction(1, 2))
    if mode == 'down':
        return int(value)
    if mode == 'up':
        if value.denominator == 1:
            return int(value)
        return int(value) + 1
    raise ValueError(mode)


def credited_kg(quantity_text, settings):
    unit, moisture, rounding = settings
    value = Fraction(quantity_text.strip()) * UNIT_KG[unit] * Fraction(100 - moisture, 100)
    return round_fraction(value, rounding)


def normalize_ref(text):
    return text.strip().upper()


# --------------------------------------------------------------------------
# weighbridge settings
# --------------------------------------------------------------------------

def _least_squares(rows, carriers, targets):
    n = len(carriers)
    m = len(rows)
    if n == 0 or m == 0:
        return None
    ata = [[sum(rows[b][carriers[i]] * rows[b][carriers[j]] for b in range(m)) for j in range(n)]
           for i in range(n)]
    aty = [sum(rows[b][carriers[i]] * targets[b] for b in range(m)) for i in range(n)]
    aug = [ata[i] + [aty[i]] for i in range(n)]
    for col in range(n):
        piv = None
        for r in range(col, n):
            if aug[r][col] != 0:
                piv = r
                break
        if piv is None:
            return None
        aug[col], aug[piv] = aug[piv], aug[col]
        pv = aug[col][col]
        aug[col] = [x / pv for x in aug[col]]
        for r in range(n):
            if r != col and aug[r][col] != 0:
                f = aug[r][col]
                aug[r] = [a - f * b for a, b in zip(aug[r], aug[col])]
    return [aug[i][n] for i in range(n)]


def derive_carrier_settings(batches):
    carriers = sorted({load['carrier'] for b in batches for load in b['loads']})
    if not carriers:
        return {}
    per_batch = []
    targets = []
    for b in batches:
        q = {}
        for load in b['loads']:
            q.setdefault(load['carrier'], []).append(Fraction(load['quantity']))
        per_batch.append(q)
        targets.append(b['credited_kg'])
    nb = len(batches)
    sums = [{c: sum(per_batch[b].get(c, [])) for c in carriers} for b in range(nb)]
    rows = [dict((c, sums[b][c]) for c in carriers) for b in range(nb)]
    est = _least_squares(rows, carriers, targets)
    estimates = None
    if est is not None:
        estimates = dict(zip(carriers, est))

    def contribution(c, settings, b):
        unit, moisture, rounding = settings
        total = 0
        for q in per_batch[b].get(c, []):
            total += round_fraction(q * UNIT_KG[unit] * Fraction(100 - moisture, 100), rounding)
        return total

    order = list(carriers)
    for tol in (4, 8, 16, 32, 64, 128, 256, 512, 1024, None):
        pre = {}
        for c in order:
            lst = []
            for unit in sorted(UNIT_KG):
                for moisture in range(10):
                    for rounding in ROUNDINGS:
                        if estimates is not None and tol is not None:
                            approx = float(UNIT_KG[unit] * Fraction(100 - moisture, 100))
                            if abs(approx - float(estimates[c])) > tol:
                                continue
                        settings = (unit, moisture, rounding)
                        lst.append((settings, [contribution(c, settings, b) for b in range(nb)]))
            if not lst:
                for unit in sorted(UNIT_KG):
                    for moisture in range(10):
                        for rounding in ROUNDINGS:
                            settings = (unit, moisture, rounding)
                            lst.append((settings,
                                        [contribution(c, settings, b) for b in range(nb)]))
            pre[c] = lst
        rem_max = [[0] * nb for _ in range(len(order) + 1)]
        rem_min = [[0] * nb for _ in range(len(order) + 1)]
        for i in range(len(order) - 1, -1, -1):
            for b in range(nb):
                vals = [v[1][b] for v in pre[order[i]]]
                rem_max[i][b] = rem_max[i + 1][b] + max(vals)
                rem_min[i][b] = rem_min[i + 1][b] + min(vals)
        found = []

        def dfs(i, acc, chosen):
            if found:
                return
            if i == len(order):
                if acc == targets:
                    found.append(list(chosen))
                return
            for settings, vec in pre[order[i]]:
                ok = True
                for b in range(nb):
                    v = acc[b] + vec[b]
                    if (v > targets[b] or v + rem_max[i + 1][b] < targets[b]
                            or v + rem_min[i + 1][b] > targets[b]):
                        ok = False
                        break
                if ok:
                    dfs(i + 1, [acc[b] + vec[b] for b in range(nb)],
                        chosen + [(order[i], settings)])

        dfs(0, [0] * nb, [])
        if found:
            return dict(found[0])
    raise RuntimeError('weighbridge settings could not be derived')


# --------------------------------------------------------------------------
# allocation procedure
# --------------------------------------------------------------------------

def make_divisor(family, p, q):
    if family == 'A':
        return (lambda n, p=p: p if n == 0 else (2 * n + 1) * 1000), (lambda n: 1000)
    if family == 'B':
        return (lambda n, p=p: n * 1000 + p), (lambda n: 1000)
    if family == 'C':
        return ((lambda n, p=p: p * 10 if n == 0 else 100 * n + q),
                (lambda n: 1000 if n == 0 else 100))
    if family == 'D':
        return ((lambda n, p=p: p * 10 if n == 0 else 200 * n + q),
                (lambda n: 1000 if n == 0 else 100))
    raise ValueError(family)


def all_divisor_candidates():
    cands = []
    for k in range(1000, 2001):
        cands.append(('A', k, 0))
    for k in range(100, 1001):
        cands.append(('B', k, 0))
    for a in range(40, 101):
        for b in range(30, 71):
            cands.append(('C', a, b))
    for a in range(100, 200):
        for b in range(0, 150):
            cands.append(('D', a, b))
    return cands


def allocate_units(caps, weights, allocable, dnum, dden, keys):
    n = len(caps)
    counts = [0] * n
    if allocable <= 0:
        return counts
    dn = [dnum(0) for _ in range(n)]
    dd = [dden(0) for _ in range(n)]
    remaining = allocable
    while remaining > 0:
        best = -1
        best_num = None
        best_den = None
        best_key = None
        for i in range(n):
            if counts[i] >= caps[i]:
                continue
            num = weights[i] * dd[i]
            den = dn[i]
            if best < 0:
                best, best_num, best_den, best_key = i, num, den, keys[i]
                continue
            lhs = num * best_den
            rhs = best_num * den
            if lhs > rhs or (lhs == rhs and keys[i] < best_key):
                best, best_num, best_den, best_key = i, num, den, keys[i]
        if best < 0:
            break
        counts[best] += 1
        remaining -= 1
        dn[best] = dnum(counts[best])
        dd[best] = dden(counts[best])
    return counts


def level_and_fairs(caps, weights, allocable):
    n = len(caps)
    if sum(caps) <= allocable:
        return None, list(caps)
    order = sorted(range(n), key=lambda i: Fraction(caps[i], weights[i]))
    sum_cap = 0
    sum_w = sum(weights)
    prev = Fraction(0)
    for k in range(n + 1):
        level = Fraction(allocable - sum_cap, sum_w)
        nxt = Fraction(caps[order[k]], weights[order[k]]) if k < n else None
        if level >= prev and (nxt is None or level <= nxt):
            fairs = [min(Fraction(caps[i]), weights[i] * level) for i in range(n)]
            if sum(fairs) == allocable:
                return level, fairs
        if k < n:
            sum_cap += caps[order[k]]
            sum_w -= weights[order[k]]
            prev = Fraction(caps[order[k]], weights[order[k]])
    raise RuntimeError('allocation level not found')


def floor_frac(x):
    return x.numerator // x.denominator


def ceil_frac(x):
    return -((-x.numerator) // x.denominator)


def review_tests():
    return [
        ('B_lt', lambda g, B, C, P, K, D, U, F, A, W, w: B > 0 and g < F * B),
        ('B_le', lambda g, B, C, P, K, D, U, F, A, W, w: B > 0 and g <= F * B),
        ('B_fl', lambda g, B, C, P, K, D, U, F, A, W, w: B > 0 and g < F * floor_frac(B)),
        ('B_ce', lambda g, B, C, P, K, D, U, F, A, W, w: B > 0 and g < F * ceil_frac(B)),
        ('C_lt', lambda g, B, C, P, K, D, U, F, A, W, w: C > 0 and g < F * C),
        ('C_le', lambda g, B, C, P, K, D, U, F, A, W, w: C > 0 and g <= F * C),
        ('C_fl', lambda g, B, C, P, K, D, U, F, A, W, w: C > 0 and g < F * floor_frac(C)),
        ('C_ce', lambda g, B, C, P, K, D, U, F, A, W, w: C > 0 and g < F * ceil_frac(C)),
        ('P_fair', lambda g, B, C, P, K, D, U, F, A, W, w: P is not None and P > 0 and g < F * P),
        ('K_lt', lambda g, B, C, P, K, D, U, F, A, W, w: K >= 1 and g < F * K),
        ('K_le', lambda g, B, C, P, K, D, U, F, A, W, w: K >= 1 and g <= F * K),
        ('K_fl', lambda g, B, C, P, K, D, U, F, A, W, w: K >= 1 and g < floor_frac(F * K)),
        ('D_lt', lambda g, B, C, P, K, D, U, F, A, W, w: D > 0 and g * U < F * D),
        ('AW_lt', lambda g, B, C, P, K, D, U, F, A, W, w: K >= 1 and g < F * A * w / W),
    ]


def customer_weight(base, bonuses, composition):
    if composition == 'additive':
        return base + bonuses
    weight = base
    for _ in range(bonuses):
        weight *= 2
    return weight


class Party(object):
    """A customer taking part in one depot-week allocation."""

    __slots__ = ('cid', 'segment', 'critical', 'deficit', 'demand', 'oldest', 'cap')

    def __init__(self, cid, segment, critical, deficit, demand, oldest):
        self.cid = cid
        self.segment = segment
        self.critical = critical
        self.deficit = deficit
        self.demand = demand
        self.oldest = oldest
        self.cap = 0


def run_depot_week(parties, allocable, unit_kg, params, divisor, test):
    """Run one rationed depot-week allocation, including its review rounds."""
    dnum, dden = divisor
    composition = params['bonus_composition']
    pw = params['public_weight']
    cw = params['commercial_weight']
    tie_break = params['tie_break']
    floor = Fraction(str(params['review_floor']))
    limit = params['review_round_limit']
    n = len(parties)
    caps = [p.cap for p in parties]
    demands = [p.demand for p in parties]

    def weight_of(i, listed):
        base = pw if parties[i].segment == 'public' else cw
        bonuses = (1 if parties[i].critical else 0) + (1 if parties[i].deficit else 0)
        if listed:
            bonuses += 1
        return customer_weight(base, bonuses, composition)

    def keys_for(weights):
        keys = []
        for i in range(n):
            if tie_break == 'lowest_customer_id':
                keys.append((parties[i].cid,))
            elif tie_break == 'highest_weight':
                keys.append((-weights[i], parties[i].cid))
            else:
                keys.append((parties[i].oldest, parties[i].cid))
        return keys

    weights0 = [weight_of(i, False) for i in range(n)]
    _, fairs_before = level_and_fairs(caps, weights0, allocable)
    review = set()
    rounds = 0
    prev_fairs = None
    while True:
        weights = [weight_of(i, i in review) for i in range(n)]
        keys = keys_for(weights)
        counts = allocate_units(caps, weights, allocable, dnum, dden, keys)
        level, fairs_now = level_and_fairs(caps, weights, allocable)
        total_w = sum(weights)
        added = []
        for i in range(n):
            if i in review:
                continue
            if test[0] == 'P_fair':
                p_val = fairs_now[i] if rounds == 0 else prev_fairs[i]
            else:
                p_val = None
            if test[1](counts[i], fairs_before[i], fairs_now[i], p_val, caps[i],
                       demands[i], unit_kg, floor, allocable, total_w, weights[i]):
                added.append(i)
        if not added:
            return dict(counts=counts, weights=weights, fairs=fairs_now, level=level,
                        review=set(review), rounds=rounds, settled=True)
        if rounds >= limit:
            return dict(counts=counts, weights=weights, fairs=fairs_now, level=level,
                        review=set(review), rounds=rounds, settled=False)
        prev_fairs = fairs_now
        review.update(added)
        rounds += 1


# --------------------------------------------------------------------------
# journal fitting
# --------------------------------------------------------------------------

def journal_frame(entry):
    params = {
        'public_weight': entry['parameters']['public_weight'],
        'commercial_weight': entry['parameters']['commercial_weight'],
        'bonus_composition': entry['parameters']['bonus_composition'],
        'tie_break': entry['parameters']['tie_break'],
        'review_floor': str(entry['parameters']['review_floor']),
        'review_round_limit': entry['parameters']['review_round_limit'],
    }
    unit = entry['unit_kg']
    allocable = entry['available_kg'] // unit
    parties = []
    for c in entry['customers']:
        party = Party(c['customer'], c['segment'], bool(c['critical_route']),
                      bool(c['in_deficit']), c['open_demand_kg'],
                      parse_instant(c['oldest_lot_at']))
        party.cap = c['open_demand_kg'] // unit
        parties.append(party)
    return parties, allocable, unit, params


def journal_first_matches(entry, divisor):
    parties, allocable, unit, params = journal_frame(entry)
    dnum, dden = divisor
    composition = params['bonus_composition']
    pw = params['public_weight']
    cw = params['commercial_weight']
    tie_break = params['tie_break']
    caps = [p.cap for p in parties]
    weights = []
    for party in parties:
        base = pw if party.segment == 'public' else cw
        bonuses = (1 if party.critical else 0) + (1 if party.deficit else 0)
        weights.append(customer_weight(base, bonuses, composition))
    keys = []
    for i, party in enumerate(parties):
        if tie_break == 'lowest_customer_id':
            keys.append((party.cid,))
        elif tie_break == 'highest_weight':
            keys.append((-weights[i], party.cid))
        else:
            keys.append((party.oldest, party.cid))
    counts = allocate_units(caps, weights, allocable, dnum, dden, keys)
    granted = {parties[i].cid: counts[i] * unit for i in range(len(parties))}
    return granted == entry['granted_kg']


def journal_full_matches(entry, divisor, test):
    parties, allocable, unit, params = journal_frame(entry)
    result = run_depot_week(parties, allocable, unit, params, divisor, test)
    granted = {parties[i].cid: result['counts'][i] * unit for i in range(len(parties))}
    return (granted == entry['granted_kg'] and len(result['review']) == entry['reviewed_count']
            and result['rounds'] == entry['review_rounds'] and result['settled'] == entry['settled'])


def derive_allocation_policy(journal_rows):
    entries = list(journal_rows)
    plain = [e for e in entries if e['review_rounds'] == 0]

    def cost(e):
        return (e['available_kg'] // e['unit_kg']) * max(1, len(e['customers']))

    plain_sorted = sorted(plain, key=cost)
    all_sorted = sorted(entries, key=cost)
    survivors = []
    for cand in all_divisor_candidates():
        divisor = make_divisor(*cand)
        ok = True
        for e in plain_sorted:
            if not journal_first_matches(e, divisor):
                ok = False
                break
        if ok:
            survivors.append(cand)
    if not survivors:
        raise RuntimeError('no admissible divisor sequence fits the journal')
    tests = review_tests()
    for cand in survivors:
        divisor = make_divisor(*cand)
        for test in tests:
            ok = True
            for e in all_sorted:
                if not journal_full_matches(e, divisor, test):
                    ok = False
                    break
            if ok:
                return divisor, test, cand, test[0]
    raise RuntimeError('no admissible review test fits the journal')


# --------------------------------------------------------------------------
# extract
# --------------------------------------------------------------------------

class Extract(object):
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.load()

    def load(self):
        d = self.data_dir
        self.calendar_rows = read_csv(os.path.join(d, 'season_calendar.csv'))
        coop = read_json(os.path.join(d, 'cooperative_time.json'))
        self.clock = CoopClock([(parse_wall(p['from_local']), parse_offset(p['utc_offset']))
                                for p in coop['periods']])

        root = ET.parse(os.path.join(d, 'depots.xml')).getroot()
        self.depots = {}
        for node in root.findall('depot'):
            code = node.attrib['code']
            self.depots[code] = {
                'region': node.attrib['region'],
                'opening_kg': int(node.findtext('opening_stock_kg').strip()),
            }
        self.critical_routes = set()
        for node in root.findall('routes/route'):
            if node.attrib['critical'].strip().lower() == 'yes':
                self.critical_routes.add(node.attrib['code'])

        self.contracts = {}
        for row in read_csv(os.path.join(d, 'contracts.csv')):
            self.contracts[row['customer_id']] = {
                'segment': row['segment'].strip(),
                'contract_min_kg': tonnes_to_kg(row['contract_min_t']),
                'route_code': row['route_code'].strip(),
            }

        self.crm = {}
        for row in read_json(os.path.join(d, 'crm_accounts.json'))['accounts']:
            self.crm.setdefault(row['customer_id'], []).append(row)
        for cid in self.crm:
            self.crm[cid].sort(key=lambda r: (parse_instant(r['updated_at']), r['revision']))

        self.events = []
        for row in read_csv(os.path.join(d, 'identity_events.csv')):
            self.events.append({
                'event_id': row['event_id'],
                'eff': parse_instant(row['effective_at']),
                'kind': row['kind'].strip(),
                'code': row['code'].strip(),
                'target': (row['target'] or '').strip(),
            })
        self.events.sort(key=lambda e: (e['eff'], e['event_id']))

        self.areas = {}
        for row in read_json(os.path.join(d, 'service_areas.json'))['assignments']:
            self.areas.setdefault(row['customer_id'], []).append(row)
        for cid in self.areas:
            self.areas[cid].sort(key=lambda r: parse_instant(r['effective_from']))

        self.classes = {}
        for row in read_csv(os.path.join(d, 'order_classes.csv')):
            self.classes[row['class_code'].strip()] = {
                'offer_weeks': int(row['offer_weeks']),
                'basis': row['entitlement_basis'].strip(),
            }

        self.orders = []
        for row in read_csv(os.path.join(d, 'orders.csv')):
            self.orders.append({
                'order_id': row['order_id'],
                'po_number': row['po_number'].strip(),
                'ref_raw': row['customer_ref'],
                'ref': normalize_ref(row['customer_ref']),
                'placed': parse_instant(row['placed_at']),
                'qty_kg': tonnes_to_kg(row['quantity_t']),
                'order_class': row['order_class'].strip(),
            })

        self.amendments = read_jsonl(os.path.join(d, 'order_amendments.jsonl'))
        self.amendments.sort(key=lambda a: a['seq'])
        self.board = read_csv(os.path.join(d, 'dispatch_board_final.csv'))
        self.receipt_rows = read_csv(os.path.join(d, 'receipts.csv'))
        self.calibration = read_json(os.path.join(d, 'carrier_calibration.json'))['batches']
        self.versions = read_json(os.path.join(d, 'allocation_parameters.json'))['versions']
        self.journal = read_jsonl(os.path.join(d, 'rationing_journal_2024-25.jsonl'))

        self.weeks = []
        for row in self.calendar_rows:
            self.weeks.append({
                'id': row['week_id'],
                'open': self.clock.instant(parse_wall(row['opens_at'])),
                'close': self.clock.instant(parse_wall(row['closes_at'])),
            })
        for i, week in enumerate(self.weeks):
            week['index'] = i
        self.nweeks = len(self.weeks)
        self.season_open = self.weeks[0]['open']
        self.season_close = self.weeks[-1]['close']

        self.settings = derive_carrier_settings(self.calibration)
        self.divisor, self.test, self.divisor_candidate, self.test_name = \
            derive_allocation_policy(self.journal)

    def week_of(self, instant):
        if instant <= self.season_open or instant > self.season_close:
            return None
        lo = 0
        hi = self.nweeks - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.weeks[mid]['open'] < instant:
                lo = mid
            else:
                hi = mid - 1
        week = self.weeks[lo]
        if week['open'] < instant <= week['close']:
            return week
        return None

    def in_season(self, instant):
        return self.season_open < instant <= self.season_close

    def params_at(self, instant):
        chosen = []
        for version in self.versions:
            eff = parse_instant(version['effective_at'])
            if eff <= instant:
                chosen.append((eff, version['version_id'], version))
        chosen.sort(key=lambda item: (item[0], item[1]))
        current = dict(STANDING_DEFAULTS)
        last = None
        for _, _, version in chosen:
            if version['mode'] == 'replace':
                current = dict(STANDING_DEFAULTS)
            for key in sorted(version['values']):
                current[key] = version['values'][key]
            last = version['version_id']
        return current, last

    def _alias_target(self, code, instant):
        best = None
        for ev in self.events:
            if ev['kind'] != 'alias' or ev['code'] != code or ev['eff'] > instant:
                continue
            if best is None or (ev['eff'], ev['event_id']) >= (best['eff'], best['event_id']):
                best = ev
        return best['target'] if best else None

    def _merge_target(self, code, instant):
        best = None
        for ev in self.events:
            if ev['kind'] != 'merge' or ev['code'] != code or ev['eff'] > instant:
                continue
            if best is None or (ev['eff'], ev['event_id']) >= (best['eff'], best['event_id']):
                best = ev
        return best['target'] if best else None

    def resolve(self, ref, instant):
        if ref in self.contracts:
            cid = ref
        else:
            target = self._alias_target(ref, instant)
            if target is None:
                return None
            cid = target
        for _ in range(64):
            nxt = self._merge_target(cid, instant)
            if nxt is None or nxt == cid:
                break
            cid = nxt
        return cid

    def retired(self, cid, instant):
        best = None
        for ev in self.events:
            if ev['kind'] not in ('retire', 'reactivate') or ev['code'] != cid:
                continue
            if ev['eff'] > instant:
                continue
            if best is None or (ev['eff'], ev['event_id']) >= (best['eff'], best['event_id']):
                best = ev
        if best is None:
            return False
        return best['kind'] == 'retire'

    def crm_row(self, cid, instant):
        best = None
        for row in self.crm.get(cid, ()):
            upd = parse_instant(row['updated_at'])
            if upd > instant:
                continue
            key = (upd, row['revision'])
            if best is None or key >= best[0]:
                best = (key, row)
        return best[1] if best else None

    def critical_route(self, cid, instant):
        row = self.crm_row(cid, instant)
        if row is None:
            return False
        if row['route_source'] == 'crm':
            return bool(row['critical_route'])
        contract = self.contracts.get(cid)
        if contract is None:
            return False
        return contract['route_code'] in self.critical_routes

    def depot_for(self, cid, instant):
        best = None
        for row in self.areas.get(cid, ()):
            eff = parse_instant(row['effective_from'])
            if eff > instant:
                continue
            if best is None or eff >= best[0]:
                best = (eff, row)
        return best[1]['depot'] if best else None

    def carrier_settings(self, carrier, instant=None):
        return self.settings[carrier]


# --------------------------------------------------------------------------
# orders and lots
# --------------------------------------------------------------------------

class Lot(object):
    __slots__ = ('order_id', 'po_number', 'ref_raw', 'class_code', 'basis', 'offer_weeks',
                 'depot', 'holder', 'placed', 'week', 'qty', 'delivered_total',
                 'deliveries', 'lapsed_week', 'lapsed_kg', 'withdrawn_week', 'withdrawn_kg')

    def __init__(self, order, depot, holder, week_index, qty, cls):
        self.order_id = order['order_id']
        self.po_number = order['po_number']
        self.ref_raw = order['ref_raw']
        self.class_code = order['order_class']
        self.basis = cls['basis']
        self.offer_weeks = cls['offer_weeks']
        self.depot = depot
        self.holder = holder
        self.placed = order['placed']
        self.week = week_index
        self.qty = qty
        self.delivered_total = 0
        self.deliveries = []
        self.lapsed_week = None
        self.lapsed_kg = 0
        self.withdrawn_week = None
        self.withdrawn_kg = 0

    def open_qty(self):
        if self.lapsed_week is not None or self.withdrawn_week is not None:
            return 0
        return self.qty - self.delivered_total

    def add_delivery(self, week_index, kg):
        self.delivered_total += kg
        self.deliveries.append((week_index, kg))

    def delivered_before(self, week_index):
        return sum(kg for (w, kg) in self.deliveries if w < week_index)

    def last_offer_week(self):
        return self.week + self.offer_weeks - 1


class OrderBook(object):
    """Void marks, amendment effects and the lots that orders become."""

    def __init__(self, extract):
        self.extract = extract
        self.orders_by_po = {}
        for order in extract.orders:
            self.orders_by_po.setdefault(order['po_number'], []).append(order)
        self.voided = self._apply_board()
        self.matched_po = set()
        for po, group in self.orders_by_po.items():
            if any(o['order_id'] not in self.voided for o in group):
                self.matched_po.add(po)
        self.amendments_by_order = {}
        self.unmatched_amendments = []
        self._apply_amendments()
        self.final_qty = {}
        self.cancelled = {}
        for oid, ams in self.amendments_by_order.items():
            qty = None
            canc = False
            for am in ams:
                if am['action'] == 'set_quantity':
                    qty = tonnes_to_kg(str(am['quantity_t']))
                elif am['action'] == 'cancel':
                    canc = True
                elif am['action'] == 'reinstate':
                    canc = False
            self.final_qty[oid] = qty
            self.cancelled[oid] = canc

    def _apply_board(self):
        voided = set()
        lines = [r for r in self.extract.board if r['status'].strip() == 'VOID-DUP']
        lines.sort(key=lambda r: r['board_line'])
        for line in lines:
            po = line['po_number'].strip()
            pool = [o for o in self.orders_by_po.get(po, ()) if o['order_id'] not in voided]
            if not pool:
                continue
            pool.sort(key=lambda o: o['order_id'])
            voided.add(pool[-1]['order_id'])
        return voided

    def _apply_amendments(self):
        for am in self.extract.amendments:
            po = am['po_number'].strip()
            if po not in self.matched_po:
                self.unmatched_amendments.append(po)
                continue
            for order in self.orders_by_po[po]:
                if order['order_id'] in self.voided:
                    continue
                self.amendments_by_order.setdefault(order['order_id'], []).append(am)

    def build(self):
        extract = self.extract
        orphans = []
        lots = []
        for order in extract.orders:
            oid = order['order_id']
            if oid in self.voided or self.cancelled.get(oid, False):
                continue
            placed = order['placed']
            if not extract.in_season(placed):
                orphans.append((oid, order['ref_raw'], 'out_of_season'))
                continue
            cid = extract.resolve(order['ref'], placed)
            if cid is None:
                orphans.append((oid, order['ref_raw'], 'unknown_reference'))
                continue
            if extract.retired(cid, placed):
                orphans.append((oid, order['ref_raw'], 'retired_reference'))
                continue
            depot = extract.depot_for(cid, placed)
            if depot is None:
                orphans.append((oid, order['ref_raw'], 'unserved'))
                continue
            if order['order_class'] not in extract.classes:
                orphans.append((oid, order['ref_raw'], 'unknown_class'))
                continue
            week = extract.week_of(placed)
            qty = self.final_qty.get(oid)
            if qty is None:
                qty = order['qty_kg']
            lots.append(Lot(order, depot, cid, week['index'], qty,
                            extract.classes[order['order_class']]))
        lots.sort(key=lambda lot: (lot.placed, lot.order_id))
        orphans.sort(key=lambda o: o[0])
        self.orphans = [{'order_id': o[0], 'customer_ref': o[1], 'reason': o[2]} for o in orphans]
        self.lots = lots
        return lots


# --------------------------------------------------------------------------
# season simulation
# --------------------------------------------------------------------------

class Simulation(object):
    def __init__(self, extract):
        self.x = extract
        self.book = OrderBook(extract)
        self.lots = self.book.build()
        self.nweeks = extract.nweeks
        self.depot_codes = sorted(extract.depots)
        self.by_depot = dict((d, []) for d in self.depot_codes)
        for lot in self.lots:
            self.by_depot.setdefault(lot.depot, []).append(lot)
        self.receipts_by_week = {}
        self.receipt_kg_depot = dict((d, 0) for d in self.depot_codes)
        self.receipt_rows_in_force = []
        self._load_receipts()
        self.rationed = []
        self.rationed_set = set()
        self.events_out = []
        self.rationed_allocations = []
        self.delivered_by_week_depot = {}
        self.lapsed_records = []
        self.withdrawn_records = []
        self.params_by_week = []
        self.deficit_flags = []
        self.week_delivered = [0] * self.nweeks
        self.week_receipts = [0] * self.nweeks
        self.week_lapsed = [0] * self.nweeks
        self.week_withdrawn = [0] * self.nweeks
        self.week_rationed = [0] * self.nweeks
        self.week_unsettled = [0] * self.nweeks

    def _load_receipts(self):
        last = {}
        for row in self.x.receipt_rows:
            last[row['receipt_id']] = row
        names = {}
        for carrier in self.x.settings:
            names.setdefault(carrier.strip().lower(), carrier)
        for rid in sorted(last):
            row = last[rid]
            instant = parse_instant(row['arrived_at'])
            depot = row['depot'].strip()
            carrier = names.get(row['carrier'].strip().lower())
            if carrier is None:
                continue
            settings = self.x.carrier_settings(carrier, instant)
            kg = credited_kg(row['quantity'], settings)
            self.receipt_rows_in_force.append({'row': row, 'instant': instant,
                                               'depot': depot, 'carrier': carrier,
                                               'credited': kg, 'settings': settings})
            week = self.x.week_of(instant)
            if week is None:
                continue
            entry = self.receipts_by_week.setdefault(week['index'], {})
            entry[depot] = entry.get(depot, 0) + kg
            self.receipt_kg_depot[depot] = self.receipt_kg_depot.get(depot, 0) + kg

    def run(self):
        x = self.x
        carried = dict((d, x.depots[d]['opening_kg']) for d in self.depot_codes)
        week_events = {}
        for ev in x.events:
            if ev['kind'] not in ('merge', 'retire'):
                continue
            week = x.week_of(ev['eff'])
            if week is None:
                continue
            week_events.setdefault(week['index'], []).append(ev)

        for widx in range(self.nweeks):
            week = x.weeks[widx]
            alloc_instant = week['close']
            params, version_id = x.params_at(alloc_instant)
            self.params_by_week.append((week['id'], version_id, params))
            threshold = Fraction(str(params['deficit_threshold']))

            for ev in week_events.get(widx, ()):
                if ev['kind'] == 'merge':
                    self._apply_merge(ev)
                else:
                    self._apply_retire(ev, widx)

            for depot, kg in self.receipts_by_week.get(widx, {}).items():
                self.week_receipts[widx] += kg

            deficit = self._deficit_status(widx, threshold)
            self.deficit_flags.append(deficit)

            available = {}
            demand_map = {}
            for depot in self.depot_codes:
                avail = carried.get(depot, 0) + self.receipts_by_week.get(widx, {}).get(depot, 0)
                available[depot] = avail
                groups = {}
                for lot in self.by_depot.get(depot, ()):
                    if lot.week > widx or widx > lot.last_offer_week():
                        continue
                    op = lot.open_qty()
                    if op <= 0:
                        continue
                    entry = groups.setdefault(lot.holder, [0, []])
                    entry[0] += op
                    entry[1].append(lot)
                demand_map[depot] = groups

            unit = params['allocation_unit_kg']
            rationed_count = 0
            unsettled_count = 0
            for depot in self.depot_codes:
                groups = demand_map[depot]
                total_demand = sum(g[0] for g in groups.values())
                avail = available[depot]
                if total_demand > avail:
                    rationed_count += 1
                    self.rationed.append((widx, depot))
                    allocable = avail // unit
                    parties = []
                    for cid in sorted(groups):
                        demand, lot_list = groups[cid]
                        oldest = min(lot.placed for lot in lot_list)
                        segment = x.contracts[cid]['segment'] if cid in x.contracts else None
                        party = Party(cid, segment, x.critical_route(cid, alloc_instant),
                                      cid in deficit, demand, oldest)
                        party.cap = demand // unit
                        parties.append(party)
                    result = run_depot_week(parties, allocable, unit, params,
                                             x.divisor, x.test)
                    counts = result['counts']
                    if not result['settled']:
                        unsettled_count += 1
                    self.events_out.append({
                        'week': week['id'], 'depot': depot, 'available_kg': avail,
                        'demand_kg': total_demand, 'allocable_units': allocable,
                        'level': result['level'],
                        'whole_part_units': sum(floor_frac(f) for f in result['fairs']),
                        'units_granted': sum(counts),
                        'review_rounds': result['rounds'],
                        'settled': result['settled'],
                    })
                    grants = {}
                    for i, party in enumerate(parties):
                        grants[party.cid] = counts[i] * unit
                        self.rationed_allocations.append({
                            'week': week['id'], 'depot': depot, 'customer_id': party.cid,
                            'demand_kg': party.demand, 'weight': result['weights'][i],
                            'reviewed': i in result['review'],
                            'allocated_kg': counts[i] * unit, 'week_index': widx,
                        })
                    self._deliver(widx, depot, groups, grants)
                else:
                    grants = dict((cid, g[0]) for cid, g in groups.items())
                    self._deliver(widx, depot, groups, grants)

            self.week_rationed[widx] = rationed_count
            self.week_unsettled[widx] = unsettled_count
            for depot in self.depot_codes:
                carried[depot] = available[depot] - self.delivered_by_week_depot.get((widx, depot), 0)
            self._lapse(widx)

        self.rationed_set = set(self.rationed)
        self.closing = dict(carried)

    def _apply_merge(self, ev):
        final = ev['target']
        for _ in range(64):
            nxt = self.x._merge_target(final, ev['eff'])
            if nxt is None or nxt == final:
                break
            final = nxt
        for lot in self.lots:
            if lot.holder == ev['code'] and lot.placed < ev['eff']:
                lot.holder = final

    def _apply_retire(self, ev, widx):
        for lot in self.lots:
            if lot.holder != ev['code'] or lot.placed >= ev['eff']:
                continue
            op = lot.open_qty()
            if op <= 0:
                continue
            lot.withdrawn_week = widx
            lot.withdrawn_kg = op
            self.withdrawn_records.append(lot)
            self.week_withdrawn[widx] += op

    def _deficit_status(self, widx, threshold):
        status = {}
        for lot in self.lots:
            if lot.week >= widx:
                continue
            bucket = status.setdefault(lot.holder, [Fraction(0), Fraction(0)])
            if lot.basis == 'ordered':
                bucket[0] += lot.qty
                bucket[1] += lot.delivered_before(widx)
            elif lot.basis == 'delivered':
                delivered = lot.delivered_before(widx)
                bucket[0] += delivered
                bucket[1] += delivered
        return set(cid for cid, (entitled, delivered) in status.items()
                    if entitled > 0 and delivered < threshold * entitled)

    def _deliver(self, widx, depot, groups, grants):
        for cid in sorted(grants):
            grant = grants[cid]
            if grant <= 0:
                continue
            lot_list = groups[cid][1]
            lot_list.sort(key=lambda lot: (lot.placed, lot.order_id))
            remaining = grant
            for lot in lot_list:
                if remaining <= 0:
                    break
                op = lot.open_qty()
                if op <= 0:
                    continue
                take = op if op <= remaining else remaining
                lot.add_delivery(widx, take)
                remaining -= take
                self.delivered_by_week_depot[(widx, depot)] = \
                    self.delivered_by_week_depot.get((widx, depot), 0) + take
                self.week_delivered[widx] += take

    def _lapse(self, widx):
        for lot in self.lots:
            if lot.lapsed_week is not None or lot.withdrawn_week is not None:
                continue
            if lot.last_offer_week() != widx:
                continue
            op = lot.open_qty()
            if op > 0:
                lot.lapsed_week = widx
                lot.lapsed_kg = op
                self.lapsed_records.append(lot)
                self.week_lapsed[widx] += op


# --------------------------------------------------------------------------
# reports
# --------------------------------------------------------------------------

def format_ratio(numerator, denominator):
    if denominator == 0:
        return '0.0000'
    scaled = round_half_up_fraction(Fraction(numerator, denominator) * 10000)
    return '%d.%04d' % (scaled // 10000, scaled % 10000)


def build_reports(extract, sim):
    weeks = extract.weeks
    nweeks = extract.nweeks
    lots = sim.lots

    summary = {'depots': [], 'weeks': [], 'true_up': []}
    for depot in sim.depot_codes:
        delivered = 0
        for (widx, d), kg in sim.delivered_by_week_depot.items():
            if d == depot:
                delivered += kg
        summary['depots'].append({
            'depot': depot,
            'region': extract.depots[depot]['region'],
            'opening_kg': extract.depots[depot]['opening_kg'],
            'receipts_kg': sim.receipt_kg_depot.get(depot, 0),
            'delivered_kg': delivered,
            'closing_kg': sim.closing.get(depot, 0),
            'rationed_weeks': [weeks[w]['id'] for (w, d) in sim.rationed if d == depot],
        })
    for widx in range(nweeks):
        summary['weeks'].append({
            'week': weeks[widx]['id'],
            'receipts_kg': sim.week_receipts[widx],
            'delivered_kg': sim.week_delivered[widx],
            'lapsed_kg': sim.week_lapsed[widx],
            'withdrawn_kg': sim.week_withdrawn[widx],
            'rationed_depots': sim.week_rationed[widx],
            'unsettled_depots': sim.week_unsettled[widx],
        })

    holder_lots = {}
    for lot in lots:
        holder_lots.setdefault(lot.holder, []).append(lot)
    for cid in sorted(extract.contracts):
        contract = extract.contracts[cid]
        if contract['segment'] != 'public' or contract['contract_min_kg'] <= 0:
            continue
        if extract.resolve(cid, extract.season_close) != cid:
            continue
        if extract.retired(cid, extract.season_close):
            continue
        held = holder_lots.get(cid, ())
        ordered = sum(lot.qty for lot in held)
        delivered = sum(lot.delivered_total for lot in held)
        credit = min(contract['contract_min_kg'], ordered) - delivered
        if credit > 0:
            summary['true_up'].append({
                'customer_id': cid,
                'contract_min_kg': contract['contract_min_kg'],
                'delivered_kg': delivered,
                'credit_kg': credit,
            })

    carrier_settings = []
    for carrier in sorted(extract.settings):
        unit, moisture, rounding = extract.settings[carrier]
        carrier_settings.append({'carrier': carrier, 'unit': unit,
                                 'moisture_deduction': moisture, 'rounding': rounding})
    parameters = []
    for week_id, version_id, params in sim.params_by_week:
        row = {'week': week_id, 'version_id': version_id}
        for name in PARAM_NAMES:
            row[name] = params[name]
        parameters.append(row)
    rationing_events = []
    for ev in sim.events_out:
        rationing_events.append({
            'depot': ev['depot'], 'week': ev['week'], 'available_kg': ev['available_kg'],
            'demand_kg': ev['demand_kg'], 'allocable_units': ev['allocable_units'],
            'level': None if ev['level'] is None else str(ev['level']),
            'whole_part_units': ev['whole_part_units'],
            'units_granted': ev['units_granted'],
            'review_rounds': ev['review_rounds'], 'settled': ev['settled'],
        })
    rationed_customers = set()
    for alloc in sim.rationed_allocations:
        rationed_customers.add((alloc['week_index'], alloc['customer_id']))
    deficit_by_week = {}
    for widx, cid in rationed_customers:
        if cid in sim.deficit_flags[widx]:
            deficit_by_week.setdefault(widx, set()).add(cid)
    deficit_boosts = []
    for widx in sorted(deficit_by_week):
        for cid in sorted(deficit_by_week[widx]):
            deficit_boosts.append({'week': weeks[widx]['id'], 'customer_id': cid})
    policy_audit = {
        'carrier_settings': carrier_settings,
        'parameters': parameters,
        'rationing_events': rationing_events,
        'deficit_boosts': deficit_boosts,
    }

    orphan_orders = list(sim.book.orphans)
    voided_orders = sorted(sim.book.voided)
    amendments = []
    for oid in sorted(sim.book.amendments_by_order):
        if oid in sim.book.voided:
            continue
        order = None
        for candidate in extract.orders:
            if candidate['order_id'] == oid:
                order = candidate
                break
        if order is None:
            continue
        final = sim.book.final_qty.get(oid)
        if final is None:
            final = order['qty_kg']
        amendments.append({'po_number': order['po_number'], 'order_id': oid,
                           'final_quantity_kg': final,
                           'cancelled': bool(sim.book.cancelled.get(oid, False))})
    amendments.sort(key=lambda a: (a['po_number'], a['order_id']))
    lapsed_lots = [{'order_id': lot.order_id, 'customer_id': lot.holder, 'depot': lot.depot,
                    'week': weeks[lot.lapsed_week]['id'], 'lapsed_kg': lot.lapsed_kg}
                   for lot in sorted(sim.lapsed_records, key=lambda l: l.order_id)]
    withdrawn_lots = [{'order_id': lot.order_id, 'customer_id': lot.holder, 'depot': lot.depot,
                       'week': weeks[lot.withdrawn_week]['id'],
                       'withdrawn_kg': lot.withdrawn_kg}
                      for lot in sorted(sim.withdrawn_records, key=lambda l: l.order_id)]
    opening = sum(extract.depots[d]['opening_kg'] for d in sim.depot_codes)
    receipts = sum(sim.receipt_kg_depot.get(d, 0) for d in sim.depot_codes)
    delivered_all = sum(sim.week_delivered)
    closing = sum(sim.closing.get(d, 0) for d in sim.depot_codes)
    ordered_kg = sum(lot.qty for lot in lots)
    delivered_lots = sum(lot.delivered_total for lot in lots)
    lapsed_kg = sum(lot.lapsed_kg for lot in lots)
    withdrawn_kg = sum(lot.withdrawn_kg for lot in lots)
    open_at_close = sum(lot.open_qty() for lot in lots)
    rationed_kg = 0
    unrationed_kg = 0
    for (widx, depot), kg in sim.delivered_by_week_depot.items():
        if (widx, depot) in sim.rationed_set:
            rationed_kg += kg
        else:
            unrationed_kg += kg
    data_quality = {
        'orphan_orders': orphan_orders,
        'voided_orders': voided_orders,
        'amendments': amendments,
        'unmatched_amendments': sorted(set(sim.book.unmatched_amendments)),
        'lapsed_lots': lapsed_lots,
        'withdrawn_lots': withdrawn_lots,
        'reconciliation': {
            'stock': {'opening_kg': opening, 'receipts_kg': receipts,
                      'delivered_kg': delivered_all, 'closing_kg': closing,
                      'residual_kg': opening + receipts - delivered_all - closing},
            'demand': {'ordered_kg': ordered_kg, 'delivered_kg': delivered_lots,
                       'lapsed_kg': lapsed_kg, 'withdrawn_kg': withdrawn_kg,
                       'open_at_close_kg': open_at_close,
                       'residual_kg': ordered_kg - delivered_lots - lapsed_kg
                       - withdrawn_kg - open_at_close},
            'allocation': {'rationed_kg': rationed_kg, 'unrationed_kg': unrationed_kg,
                           'delivered_kg': delivered_all,
                           'residual_kg': delivered_all - rationed_kg - unrationed_kg},
        },
    }

    regions = {}
    for depot in sim.depot_codes:
        regions.setdefault(extract.depots[depot]['region'], []).append(depot)
    rationed_by_region = {}
    for (widx, depot) in sim.rationed:
        region = extract.depots[depot]['region']
        rationed_by_region[region] = rationed_by_region.get(region, 0) + 1
    regional = {}
    for region in ('North', 'South', 'West', 'East'):
        depots = sorted(regions.get(region, ()))
        if rationed_by_region.get(region, 0) <= 0:
            regional[region] = {'region': region, 'in_scope': False}
            continue
        customers = []
        for cid in sorted(set(lot.holder for lot in lots if lot.depot in depots)):
            held = [lot for lot in lots if lot.depot in depots and lot.holder == cid]
            ordered_c = sum(lot.qty for lot in held)
            delivered_c = sum(lot.delivered_total for lot in held)
            lapsed_c = sum(lot.lapsed_kg for lot in held)
            withdrawn_c = sum(lot.withdrawn_kg for lot in held)
            open_c = sum(lot.open_qty() for lot in held)
            customers.append({
                'customer_id': cid,
                'segment': extract.contracts[cid]['segment'] if cid in extract.contracts else None,
                'ordered_kg': ordered_c, 'delivered_kg': delivered_c, 'lapsed_kg': lapsed_c,
                'withdrawn_kg': withdrawn_c, 'open_at_close_kg': open_c,
                'fill_ratio': format_ratio(delivered_c, ordered_c),
            })
        weekly = {}
        for widx in range(nweeks):
            total = 0
            for depot in depots:
                total += sim.delivered_by_week_depot.get((widx, depot), 0)
            weekly[weeks[widx]['id']] = total
        regional[region] = {'region': region, 'in_scope': True, 'depots': depots,
                            'rationed_depot_weeks': rationed_by_region[region],
                            'customers': customers, 'weekly_delivered_kg': weekly}

    segment_lots = {}
    for cid in sorted(set(lot.holder for lot in lots)):
        segment = extract.contracts[cid]['segment'] if cid in extract.contracts else None
        if segment is None:
            continue
        held = [lot for lot in lots if lot.holder == cid]
        bucket = segment_lots.setdefault(segment, [0, 0, 0, 0])
        bucket[0] += 1
        bucket[1] += sum(lot.qty for lot in held)
        bucket[2] += sum(lot.delivered_total for lot in held)
        bucket[3] += sum(lot.lapsed_kg for lot in held)
    segment_reports = {}
    for segment in ('commercial', 'public'):
        ids = set()
        for alloc in sim.rationed_allocations:
            cid = alloc['customer_id']
            contract = extract.contracts.get(cid)
            if contract is not None and contract['segment'] == segment:
                ids.add(cid)
        if not ids:
            segment_reports[segment] = {'segment': segment, 'in_scope': False}
            continue
        bucket = segment_lots.get(segment, [0, 0, 0, 0])
        rows = []
        for alloc in sim.rationed_allocations:
            cid = alloc['customer_id']
            contract = extract.contracts.get(cid)
            if contract is None or contract['segment'] != segment:
                continue
            rows.append({'week': alloc['week'], 'depot': alloc['depot'],
                         'customer_id': cid, 'demand_kg': alloc['demand_kg'],
                         'weight': alloc['weight'], 'reviewed': alloc['reviewed'],
                         'allocated_kg': alloc['allocated_kg'],
                         'week_index': alloc['week_index']})
        rows.sort(key=lambda r: (r['week_index'], r['depot'], r['customer_id']))
        for row in rows:
            del row['week_index']
        segment_reports[segment] = {
            'segment': segment, 'in_scope': True, 'customer_count': bucket[0],
            'ordered_kg': bucket[1], 'delivered_kg': bucket[2], 'lapsed_kg': bucket[3],
            'rationed_allocations': rows,
        }

    return {
        'summary.json': summary,
        'policy_audit.json': policy_audit,
        'data_quality.json': data_quality,
        'region_North.json': regional['North'],
        'region_South.json': regional['South'],
        'region_West.json': regional['West'],
        'region_East.json': regional['East'],
        'segment_commercial.json': segment_reports['commercial'],
        'segment_public.json': segment_reports['public'],
    }


def write_reports(out_dir, reports):
    for name in sorted(reports):
        text = json.dumps(reports[name], indent=2, sort_keys=True) + '\n'
        with open(os.path.join(out_dir, name), 'w', encoding='utf-8') as fh:
            fh.write(text)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: derive_report.py DATA_DIR OUT_DIR\n')
        return 2
    data_dir = argv[1]
    out_dir = argv[2]
    os.makedirs(out_dir, exist_ok=True)
    extract = Extract(data_dir)
    sim = Simulation(extract)
    sim.run()
    reports = build_reports(extract, sim)
    write_reports(out_dir, reports)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
