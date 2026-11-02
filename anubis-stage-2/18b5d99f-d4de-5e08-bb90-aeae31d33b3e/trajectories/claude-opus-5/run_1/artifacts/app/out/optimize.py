#!/usr/bin/env python3
"""Exact rating aggregator for the usage rating desk extracts.

Reads one workload and the rules file it is given (plus the files that rules file
names), derives the kind weights from the rate card and the two legacy engine rules
from the closing journals, and rates the workload in a single pass.
"""

import csv
import json
import os
import sys
from fractions import Fraction

CONTROL_FLAGS = ('void', 'revive')
MEASURES = (None, 'charge', 'amount', 'units', 'weight')


# ---------------------------------------------------------------- file loading

def _read_csv(path):
    with open(path, 'r', encoding='utf-8-sig', newline='') as fh:
        return list(csv.reader(fh))


def _rows_as_dicts(path):
    table = _read_csv(path)
    if not table:
        return [], []
    header = table[0]
    out = []
    for line in table[1:]:
        if not line:
            continue
        if len(line) < len(header):
            line = line + [''] * (len(header) - len(line))
        out.append(dict(zip(header, line)))
    return header, out


def _load_json(path):
    with open(path, 'r', encoding='utf-8-sig') as fh:
        return json.load(fh)


# ------------------------------------------------------------------- weights

def _rate_card_equations(card_rows, figures, kinds):
    batches = {}
    for row in card_rows:
        batch = row['batch']
        if batch not in figures:
            continue
        coef = batches.setdefault(batch, {})
        k = row['kind']
        coef[k] = coef.get(k, 0) + int(row['amount']) * int(row['units'])
    eqs = []
    for batch in sorted(batches):
        eqs.append(([batches[batch].get(k, 0) for k in kinds], figures[batch]))
    return eqs


def _solve_linear(eqs, n):
    """Reduced row echelon form over the rationals.

    Returns (pivot columns, matrix rows) or None when the system is inconsistent.
    """
    mat = [[Fraction(c) for c in coef] + [Fraction(rhs)] for coef, rhs in eqs]
    pivots = []
    r = 0
    for c in range(n):
        p = None
        for i in range(r, len(mat)):
            if mat[i][c]:
                p = i
                break
        if p is None:
            continue
        mat[r], mat[p] = mat[p], mat[r]
        pv = mat[r][c]
        mat[r] = [x / pv for x in mat[r]]
        for i in range(len(mat)):
            if i != r and mat[i][c]:
                f = mat[i][c]
                mat[i] = [a - f * b for a, b in zip(mat[i], mat[r])]
        pivots.append(c)
        r += 1
        if r == len(mat):
            break
    for i in range(r, len(mat)):
        if any(mat[i][:n]):
            continue
        if mat[i][n]:
            return None
    return pivots, mat[:r]


def _weight_candidates(eqs, kinds, limit=200000):
    """Integer solutions with every weight a whole number from 2 to 40."""
    n = len(kinds)
    solved = _solve_linear(eqs, n)
    if solved is None:
        return []
    pivots, mat = solved
    free = [c for c in range(n) if c not in pivots]
    out = []
    values = [0] * n

    def emit():
        for i, c in enumerate(pivots):
            v = mat[i][n]
            for fc in free:
                coef = mat[i][fc]
                if coef:
                    v -= coef * values[fc]
            if v.denominator != 1:
                return
            iv = int(v)
            if iv < 2 or iv > 40:
                return
            values[c] = iv
        out.append(dict(zip(kinds, values)))

    def rec(i):
        if len(out) >= limit:
            return
        if i == len(free):
            emit()
            return
        for v in range(2, 41):
            values[free[i]] = v
            rec(i + 1)

    rec(0)
    return out


# ----------------------------------------------- legacy engine rule inference

def _measure_value(measure, row, weights):
    if measure == 'charge':
        return row[3] * row[4] * weights[row[2]]
    if measure == 'amount':
        return row[3]
    if measure == 'units':
        return row[4]
    if measure == 'weight':
        return weights[row[2]]
    return 0


def _ranking_specs():
    specs = []
    for measure in MEASURES:
        for direction in ((1,) if measure is None else (1, -1)):
            for posdir in (1, -1):
                specs.append((measure, direction, posdir))
    return specs


def _rankings():
    specs = _ranking_specs()
    out = [('all', s) for s in specs]
    for own_first in (True, False):
        for a in specs:
            for b in specs:
                out.append(('split', own_first, a, b))
    return out


def _sort_key(ranking, void_kind, row, weights):
    # row: (pos, id, kind, amount, units, flag, is_control)
    if ranking[0] == 'all':
        measure, direction, posdir = ranking[1]
        return (0, direction * _measure_value(measure, row, weights), posdir * row[0])
    own_first = ranking[1]
    if row[2] == void_kind:
        group = 0 if own_first else 1
        measure, direction, posdir = ranking[2]
    else:
        group = 1 if own_first else 0
        measure, direction, posdir = ranking[3]
    return (group, direction * _measure_value(measure, row, weights), posdir * row[0])


def _journal_accounts(path, with_state):
    _, rows = _rows_as_dicts(path)
    accounts = {}
    extra = {}
    for row in rows:
        control = row['flag'] in CONTROL_FLAGS
        rec = (0, row['row'], row['kind'],
               0 if control else int(row['amount']),
               0 if control else int(row['units']),
               row['flag'], control)
        accounts.setdefault(row['account'], []).append(
            [rec, row['state'] if with_state else None, row])
    for account, items in accounts.items():
        items.sort(key=lambda it: (int(it[2]['ts']), int(it[0][1][1:])))
        for i, it in enumerate(items):
            it[0] = (i + 1,) + it[0][1:]
    return accounts


def _simulate_withdrawals(rows, ranking, weights, table):
    """rows: list of row tuples in processing order. Returns (live ids, applied flags)."""
    live = []
    stack = []
    applied = []
    for row in rows:
        if not row[6]:
            live.append(row)
            applied.append(None)
            continue
        if row[5] == 'revive':
            if stack:
                live.append(stack.pop())
                applied.append(True)
            else:
                applied.append(False)
            continue
        void_kind = row[2]
        best = None
        best_key = None
        for cand in live:
            if cand[2] != void_kind and not table.get((void_kind, cand[2])):
                continue
            key = _sort_key(ranking, void_kind, cand, weights)
            if best_key is None or key < best_key:
                best_key = key
                best = cand
        if best is None:
            applied.append(False)
        else:
            live.remove(best)
            stack.append(best)
            applied.append(True)
    return set(r[1] for r in live), applied


class _Budget(Exception):
    """Raised when the search for a cancellation table outgrows its node budget."""


def _account_tables(items, ranking, weights, table, budget):
    """Yield the cancellation table extensions that reproduce one account's states."""
    rows = [it[0] for it in items]
    states = [it[1] for it in items]

    def step(i, live, stack, tbl):
        if i == len(rows):
            for row, state in zip(rows, states):
                if row[6]:
                    continue
                if ('live' if row[1] in live else 'withdrawn') != state:
                    return
            yield tbl
            return
        row = rows[i]
        if not row[6]:
            for res in step(i + 1, live | {row[1]}, stack, tbl):
                yield res
            return
        if row[5] == 'revive':
            if stack:
                if states[i] == 'applied':
                    for res in step(i + 1, live | {stack[-1]}, stack[:-1], tbl):
                        yield res
            elif states[i] == 'orphan':
                for res in step(i + 1, live, stack, tbl):
                    yield res
            return
        void_kind = row[2]
        cands = [r for r in rows[:i] if (not r[6]) and r[1] in live]
        cands.sort(key=lambda r: _sort_key(ranking, void_kind, r, weights))

        def walk(j, tbl):
            budget[0] -= 1
            if budget[0] < 0:
                raise _Budget()
            if j == len(cands):
                if states[i] == 'orphan':
                    for res in step(i + 1, live, stack, tbl):
                        yield res
                return
            cand = cands[j]
            if cand[2] == void_kind:
                if states[i] == 'applied':
                    for res in step(i + 1, live - {cand[1]}, stack + [cand[1]], tbl):
                        yield res
                return
            key = (void_kind, cand[2])
            known = tbl.get(key)
            if known is True:
                if states[i] == 'applied':
                    for res in step(i + 1, live - {cand[1]}, stack + [cand[1]], tbl):
                        yield res
            elif known is False:
                for res in walk(j + 1, tbl):
                    yield res
            else:
                if states[i] == 'applied':
                    allow = dict(tbl)
                    allow[key] = True
                    for res in step(i + 1, live - {cand[1]}, stack + [cand[1]], allow):
                        yield res
                deny = dict(tbl)
                deny[key] = False
                for res in walk(j + 1, deny):
                    yield res

        for res in walk(0, tbl):
            yield res

    for res in step(0, frozenset(), [], table):
        yield res


def _search_tables(order, accounts, index, table, ranking, weights, budget):
    if index == len(order):
        return table
    for extended in _account_tables(accounts[order[index]], ranking, weights, table,
                                    budget):
        found = _search_tables(order, accounts, index + 1, extended, ranking, weights,
                               budget)
        if found is not None:
            return found
    return None


def _infer_withdrawal_rule(accounts, weights, budget=400000):
    order = sorted(accounts, key=lambda a: (-len(accounts[a]), a))
    for ranking in _rankings():
        try:
            table = _search_tables(order, accounts, 0, {}, ranking, weights, [budget])
        except _Budget:
            continue
        if table is not None:
            return ranking, table
    return None, None


def _account_stats(items, live_ids, weights, region_offsets, flag_penalties,
                   latency_quantum, region_of_row):
    ordinary = 0
    live = 0
    unwaived = 0
    carried = 0
    penalty = 0
    for it in items:
        row = it[0]
        if row[6]:
            continue
        ordinary += 1
        if row[1] not in live_ids:
            continue
        live += 1
        raw = it[2]
        base = (row[3] * row[4] * weights[row[2]] + region_offsets[region_of_row(raw)]
                - int(raw['latency_ms']) // latency_quantum)
        pen = flag_penalties.get(row[5], 0)
        carried += base
        penalty += pen
        unwaived += base - pen
    return ordinary, live, unwaived, penalty, carried


def _premium_set(stats, sponsors, floor, policy):
    count_field, total_field, strict, direction = policy
    judged = [a for a in stats if stats[a][0] > 0]
    judged_set = set(judged)

    def passes(account, members):
        o, live, unwaived, penalty, carried = stats[account]
        n = o if count_field == 'O' else live
        if n <= 0:
            return False
        if total_field == 'U':
            total = unwaived
        elif total_field == 'C':
            total = carried
        else:
            sponsor = sponsors.get(account)
            total = unwaived + penalty if (sponsor in members) else unwaived
        limit = floor * n
        return total > limit if strict else total >= limit

    if total_field != 'UW':
        return set(a for a in judged if passes(a, ()))
    members = set() if direction == 'least' else set(judged_set)
    while True:
        nxt = set(a for a in judged if passes(a, members))
        if nxt == members:
            return members
        members = nxt


def _standing_policies():
    out = []
    for count_field in ('O', 'L'):
        for total_field in ('U', 'C', 'UW'):
            for strict in (False, True):
                for direction in (('least', 'greatest') if total_field == 'UW' else (None,)):
                    out.append((count_field, total_field, strict, direction))
    return out


def _infer_standing_policy(accounts, sponsors, standing, weights, rules, ranking, table):
    region_offsets = rules['region_offsets']
    flag_penalties = rules['flag_penalties']
    latency_quantum = rules['latency_quantum']
    stats = {}
    for account, items in accounts.items():
        live_ids, _ = _simulate_withdrawals([it[0] for it in items], ranking, weights, table)
        stats[account] = _account_stats(items, live_ids, weights, region_offsets,
                                        flag_penalties, latency_quantum,
                                        lambda raw: raw['region'])
    want = set(a for a in standing if standing[a] == 'premium')
    for policy in _standing_policies():
        if _premium_set(stats, sponsors, 2000, policy) == want:
            return policy
    return None


# ------------------------------------------------------------------- identity

class Identity(object):
    def __init__(self, registry_rows, export, merge_rows):
        governing = {}
        for row in registry_rows:
            account = row['account']
            prev = governing.get(account)
            if prev is None or row['updated'] >= prev['updated']:
                governing[account] = row
        self.records = {}
        for account, row in governing.items():
            self.records[account] = (row['home_region'], row['sponsor'])
        for row in export.get('accounts', []):
            account = row['account']
            if account not in self.records:
                self.records[account] = (row['home_region'], row['sponsor'])
        merges = {}
        for row in merge_rows:
            merges.setdefault(row['account'], []).append(
                (int(row['effective_ts']), row['merged_into']))
        for account in merges:
            merges[account].sort()
        self.merges = merges
        self._cache = {}
        self._final = {}

    def resolve(self, account, ts):
        key = (account, ts)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        seen = account
        current = account
        while True:
            records = self.merges.get(current)
            target = ''
            if records:
                for eff, into in records:
                    if eff < ts:
                        target = into
                    else:
                        break
            if not target:
                break
            current = target
        self._cache[key] = current
        return current

    def resolve_final(self, account):
        hit = self._final.get(account)
        if hit is not None:
            return hit
        current = account
        while True:
            records = self.merges.get(current)
            if not records:
                break
            target = records[-1][1]
            if not target:
                break
            current = target
        self._final[account] = current
        return current

    def sponsor(self, account):
        record = self.records.get(account)
        if not record or not record[1]:
            return None
        return self.resolve_final(record[1])

    def region(self, account):
        record = self.records.get(account)
        return record[0] if record else None


# ------------------------------------------------------------------- amendments

def _net_amendments(path):
    reverted = set()
    entries = []
    with open(path, 'r', encoding='utf-8-sig') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if 'reverts' in entry:
                reverted.add(entry['reverts'])
            else:
                entries.append(entry)
    entries.sort(key=lambda e: int(e['erratum'].split('-')[1]))
    named = {}
    fields = {}
    for entry in entries:
        if entry['erratum'] in reverted:
            continue
        key = (entry['booked_account'], int(entry['ts']))
        named.setdefault(key, True)
        slot = fields.setdefault(key, {})
        if entry['field'] not in slot:
            slot[entry['field']] = entry['value']
    return fields


# ------------------------------------------------------------------- context

def _build_context(rules, base_dir):
    _, card_rows = _rows_as_dicts(os.path.join(base_dir, rules['rate_card_file']))
    figures = _load_json(os.path.join(base_dir, rules['rate_figures_file']))['figures']
    kinds = list(rules['kinds'])
    eqs = _rate_card_equations(card_rows, figures, kinds)
    candidates = _weight_candidates(eqs, kinds)
    withdraw_accounts = _journal_accounts(
        os.path.join(base_dir, rules['withdrawals_journal_file']), True)
    stand_path = os.path.join(base_dir, rules['standing_journal_file'])
    _, stand_rows = _rows_as_dicts(stand_path)
    stand_accounts = _journal_accounts(stand_path, False)
    sponsors = {}
    standing = {}
    for row in stand_rows:
        sponsors[row['account']] = row['sponsor'] or None
        standing[row['account']] = row['standing']

    for weights in candidates:
        ranking, table = _infer_withdrawal_rule(withdraw_accounts, weights)
        if ranking is None:
            continue
        policy = _infer_standing_policy(stand_accounts, sponsors, standing, weights,
                                        rules, ranking, table)
        if policy is None:
            continue
        return {
            'weights': weights,
            'ranking': ranking,
            'table': table,
            'policy': policy,
            'identity': Identity(
                _rows_as_dicts(os.path.join(base_dir, rules['registry_file']))[1],
                _load_json(os.path.join(base_dir, rules['export_file'])),
                _rows_as_dicts(os.path.join(base_dir, rules['merges_file']))[1]),
            'amendments': _net_amendments(os.path.join(base_dir, rules['errata_file'])),
        }
    raise ValueError('no consistent legacy rules found for this extract')


# ----------------------------------------------------------------- the rating

def _compute(events_path, rules_path):
    rules = _load_json(rules_path)
    base_dir = os.path.dirname(os.path.abspath(rules_path))
    ctx = _build_context(rules, base_dir)
    weights = ctx['weights']
    identity = ctx['identity']
    amendments = ctx['amendments']
    region_offsets = rules['region_offsets']
    flag_penalties = rules['flag_penalties']
    latency_quantum = rules['latency_quantum']
    carry_modulus = rules['carry_modulus']

    table = _read_csv(events_path)
    header = table[0]
    idx = {name: i for i, name in enumerate(header)}
    i_id = idx['id']
    i_ts = idx['ts']
    i_account = idx['account']
    i_kind = idx['kind']
    i_amount = idx['amount']
    i_units = idx['units']
    i_flag = idx['flag']
    micro = 'latency_us' in idx
    i_lat = idx['latency_us'] if micro else idx['latency_ms']

    event_count = 0
    processed = []
    unpriced_rows = 0
    unregistered_rows = 0
    rebooked_rows = 0
    for line in table[1:]:
        if not line:
            continue
        event_count += 1
        written = line[i_account].strip().upper()
        ts = int(line[i_ts])
        booked = identity.resolve(written, ts)
        region = identity.region(booked)
        if region is None:
            unregistered_rows += 1
            continue
        amend = amendments.get((booked, ts))
        amount = line[i_amount]
        units = line[i_units]
        kind = line[i_kind].strip().lower()
        flag = line[i_flag].strip().lower()
        amended = False
        if amend:
            amended = True
            if 'amount' in amend:
                amount = amend['amount']
            if 'units' in amend:
                units = amend['units']
            if 'flag' in amend:
                flag = amend['flag'].strip().lower()
        if amount.strip() == '':
            unpriced_rows += 1
            continue
        control = flag in CONTROL_FLAGS
        if control:
            amount_v = 0
            units_v = 0
        else:
            amount_v = int(amount)
            units_v = int(units)
        lat = int(line[i_lat])
        if micro:
            lat = (lat + 500) // 1000
        if booked != written:
            rebooked_rows += 1
        processed.append([ts, int(line[i_id][1:]), line[i_id], booked, region, kind,
                          amount_v, units_v, flag, lat, control, amended])

    processed.sort(key=lambda r: (r[0], r[1]))

    carries = {}
    accounts = {}
    rows = []
    for position, rec in enumerate(processed, 1):
        (ts, idnum, rid, booked, region, kind, amount_v, units_v, flag, lat,
         control, amended) = rec
        base = (amount_v * units_v * weights[kind] + region_offsets[region]
                - lat // latency_quantum)
        if control:
            carried = base
        else:
            carried = base + carries.get(region, 0)
            carries[region] = carried % carry_modulus
        penalty = flag_penalties.get(flag, 0)
        row = {
            'pos': position, 'id': rid, 'num': idnum, 'account': booked,
            'region': region, 'kind': kind, 'amount': amount_v, 'units': units_v,
            'flag': flag, 'control': control, 'amended': amended,
            'carried': carried, 'penalty': penalty,
        }
        rows.append(row)
        accounts.setdefault(booked, []).append(row)

    # withdrawals
    ranking = ctx['ranking']
    tbl = ctx['table']
    live_ids = set()
    orphan_voids = 0
    orphan_revives = 0
    for account, items in accounts.items():
        tuples = []
        for i, row in enumerate(items):
            tuples.append((i + 1, row['id'], row['kind'], row['amount'], row['units'],
                           row['flag'], row['control']))
        live, applied = _simulate_withdrawals(tuples, ranking, weights, tbl)
        for row, ok in zip(items, applied):
            if ok is False:
                if row['flag'] == 'void':
                    orphan_voids += 1
                else:
                    orphan_revives += 1
        for row in items:
            if not row['control'] and row['id'] in live:
                live_ids.add(row['id'])

    # standing
    stats = {}
    for account, items in accounts.items():
        ordinary = live = unwaived = carried_total = penalty_total = 0
        for row in items:
            if row['control']:
                continue
            ordinary += 1
            if row['id'] in live_ids:
                live += 1
                carried_total += row['carried']
                penalty_total += row['penalty']
                unwaived += row['carried'] - row['penalty']
        stats[account] = (ordinary, live, unwaived, penalty_total, carried_total)
    sponsors = {a: identity.sponsor(a) for a in accounts}
    policy = ctx['policy']
    premium = _premium_set(stats, sponsors, rules['premium_floor'], policy)

    waived_penalty = 0
    checksum = 0
    account_totals = {}
    region_totals = {}
    kind_totals = {}
    flag_counts = {}
    cancelled_score = 0
    amended_rows = []
    total_live = 0
    for row in rows:
        waived = (not row['control']) and sponsors.get(row['account']) in premium
        if waived:
            waived_penalty += row['penalty']
        final = row['carried'] if waived else row['carried'] - row['penalty']
        checksum = (checksum * 1315423911 + final * row['pos'] + row['num']) & 0xFFFFFFFF
        if row['amended']:
            amended_rows.append([row['id'], final])
        if row['control']:
            flag_counts[row['flag']] = flag_counts.get(row['flag'], 0) + 1
            continue
        account_totals.setdefault(row['account'], 0)
        region_totals.setdefault(row['region'], 0)
        kind_totals.setdefault(row['kind'], 0)
        flag_counts.setdefault(row['flag'], 0)
        if row['id'] in live_ids:
            total_live += 1
            account_totals[row['account']] += final
            region_totals[row['region']] += final
            kind_totals[row['kind']] += final
            flag_counts[row['flag']] += 1
        else:
            cancelled_score += final

    premium_accounts = sorted(premium)
    ranked = sorted(account_totals.items(), key=lambda kv: (-kv[1], kv[0]))
    top_accounts = [[a, t] for a, t in ranked[:rules['top_n']]]
    total_score = sum(account_totals.values())
    average_score = total_score // total_live if total_live else 0

    rescued = []
    count_field, total_field, strict, direction = policy
    for account in premium:
        ordinary, live, unwaived, penalty_total, carried_total = stats[account]
        n = ordinary if count_field == 'O' else live
        if total_field == 'U':
            total = unwaived
        elif total_field == 'C':
            total = carried_total
        else:
            total = unwaived
        limit = rules['premium_floor'] * n
        ok = n > 0 and (total > limit if strict else total >= limit)
        if not ok:
            rescued.append(account)
    rescued.sort()

    result = {
        'label': rules['label'],
        'event_count': event_count,
        'account_totals': account_totals,
        'region_totals': region_totals,
        'kind_totals': kind_totals,
        'flag_counts': flag_counts,
        'premium_accounts': premium_accounts,
        'top_accounts': top_accounts,
        'checksum': checksum,
    }
    group_keys = (len(account_totals) + len(region_totals) + len(kind_totals)
                  + len(flag_counts))
    detail = {
        'result': result,
        'metrics': {
            'total_score': total_score,
            'average_score': average_score,
            'top_account': top_accounts[0][0] if top_accounts else None,
            'top_account_score': top_accounts[0][1] if top_accounts else 0,
        },
        'quality': {
            'unpriced_rows': unpriced_rows,
            'unregistered_rows': unregistered_rows,
            'rebooked_rows': rebooked_rows,
            'orphan_voids': orphan_voids,
            'orphan_revives': orphan_revives,
            'cancelled_score': cancelled_score,
            'amendments': amended_rows,
        },
        'recommendations': {
            'rescued_accounts': rescued,
            'waived_penalty': waived_penalty,
        },
        'bottleneck': {
            'group_keys': group_keys,
            'processed_rows': len(rows),
            'baseline_row_scans': group_keys * len(rows),
        },
    }
    return detail


def aggregate(events_path, rules_path):
    """Rate the workload at events_path with the rules file at rules_path."""
    return _compute(events_path, rules_path)['result']


def main(argv):
    if len(argv) != 3:
        sys.stderr.write('usage: optimize.py EVENTS_CSV RULES_JSON\n')
        return 2
    sys.stdout.write(json.dumps(aggregate(argv[1], argv[2]), sort_keys=True) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
