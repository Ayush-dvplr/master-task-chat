#!/usr/bin/env python3
"""Settle an Emberforge season using only its published records and rulebooks."""
import csv
import json
import sys
from collections import defaultdict, Counter
from itertools import permutations, product
from pathlib import Path


def read_csv(root, name):
    with (root / name).open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def read_json(root, name):
    with (root / name).open(encoding='utf-8') as f:
        return json.load(f)


def write_json(root, name, obj):
    (root / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def reduce_ratio(n, d, mode):
    q, r = divmod(n, d)
    if mode == 'floor':
        return q
    if mode == 'ceil':
        return q + (r != 0)
    if mode == 'half-up':
        return q + (2 * r >= d)
    if mode == 'half-down':
        return q + (2 * r > d)
    return q + (2 * r > d or (2 * r == d and q % 2 == 1))


def infer_conventions(rulings):
    schedules = [(40, 50, 60), (45, 55, 65), (50, 60, 70),
                 (35, 50, 65), (55, 55, 55), (30, 45, 60), (60, 50, 40)]
    modes = ('floor', 'ceil', 'half-up', 'half-down', 'half-even')
    choices = []
    for mode in modes:
        for schedule in schedules:
            if not all(reduce_ratio(int(r['committed_units']) * schedule[int(r['tier']) - 1], 100, mode)
                       == int(r['returned_units']) for r in rulings['return_rulings']):
                continue
            for order in map(''.join, permutations('FGS')):
                good_charge = True
                for r in rulings['charge_rulings']:
                    v = int(r['base_value'])
                    pct = {'F': int(r['family_percent']), 'G': int(r['grade_percent']),
                           'S': int(r['scarcity_percent'])}
                    for op in order:
                        v = reduce_ratio(v * pct[op], 100, mode)
                    if v != int(r['charge_ember']):
                        good_charge = False
                        break
                if not good_charge:
                    continue
                for ref in ('opening', 'opening-plus-acquired', 'consumed', 'acquired'):
                    if all(min(int(r['scarcity_ceiling']), reduce_ratio(
                        int(r['consumed_units']) * 100,
                        {'opening': int(r['opening_units']),
                         'opening-plus-acquired': int(r['opening_units']) + int(r['acquired_units']),
                         'consumed': int(r['called_for_units']),
                         'acquired': int(r['acquired_units'])}[ref], mode))
                           == int(r['scarcity_index']) if
                           {'opening': int(r['opening_units']),
                            'opening-plus-acquired': int(r['opening_units']) + int(r['acquired_units']),
                            'consumed': int(r['called_for_units']),
                            'acquired': int(r['acquired_units'])}[ref] else int(r['scarcity_index']) == 0
                           for r in rulings['scarcity_rulings']):
                        choices.append((schedule, mode, order, ref))
    if len(choices) != 1:
        raise ValueError('Council rulings do not identify exactly one convention draw')
    return choices[0]


def allocate(reqs, workshops, charter, reagents, balances):
    pool = int(charter['season_pool_units'])
    guild_names = sorted({workshops[w]['guild_id'] for w in workshops})
    scarce_names = sorted(r for r in reagents if int(reagents[r]['scarce']))
    guild_pos = {g: i for i, g in enumerate(guild_names)}
    scarce_pos = {r: i for i, r in enumerate(scarce_names)}
    g_caps = tuple(int(charter['guild_cap_units'].get(g, pool)) for g in guild_names)
    s_caps = tuple(max(0, balances[r]) for r in scarce_names)
    ordered = sorted(reqs, key=lambda x: (int(x['priority']), x['req_id']))
    rows = []
    for q in ordered:
        w = workshops.get(q['workshop_id'])
        cap = min(int(q['units_requested']), int(charter['tier_unit_cap'][str(w['charter_tier'])])) if w else 0
        minimum = int(q['min_units'])
        rows.append((q['req_id'], w['charter_id'] if w else None,
                     guild_pos[w['guild_id']] if w else -1,
                     scarce_pos.get(q['reagent_id'], -1), minimum,
                     cap if cap >= minimum else 0))
    n = len(rows)
    future_charters = [set() for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        future_charters[i] = future_charters[i + 1].copy()
        if rows[i][1] is not None:
            future_charters[i].add(rows[i][1])
    best = -1
    best_plan = None
    plan = [0] * n
    memo = set()

    def bound(i, left, gr, sr, used):
        # Every remaining charter can fund at most its largest eligible request.
        group_max = {}
        guild_max = [defaultdict(int) for _ in gr]
        scarce_max = [defaultdict(int) for _ in sr]
        nonscarce_max = [defaultdict(int) for _ in sr]
        for j in range(i, n):
            _, ch, gi, si, minimum, maximum = rows[j]
            if maximum == 0 or ch in used:
                continue
            maximum = min(maximum, gr[gi], sr[si] if si >= 0 else left, left)
            if maximum < minimum:
                continue
            group_max[ch] = max(group_max.get(ch, 0), maximum)
            guild_max[gi][ch] = max(guild_max[gi][ch], maximum)
            if si >= 0:
                scarce_max[si][ch] = max(scarce_max[si][ch], maximum)
            for k in range(len(sr)):
                if si != k:
                    nonscarce_max[k][ch] = max(nonscarce_max[k][ch], maximum)
        ub = min(left, sum(group_max.values()))
        ub = min(ub, sum(min(gr[k], sum(d.values())) for k, d in enumerate(guild_max)))
        for k, d in enumerate(scarce_max):
            # Non-scarce requests remain unrestricted by this reagent.
            non_this = sum(nonscarce_max[k].values())
            ub = min(ub, non_this + min(sr[k], sum(d.values())))
        return ub

    def visit(i, left, gr, sr, used, total):
        nonlocal best, best_plan
        if total + bound(i, left, gr, sr, used) <= best:
            return
        if i == n:
            if total > best:
                best, best_plan = total, plan.copy()
            return
        key = (i, left, gr, sr, tuple(sorted(used & future_charters[i])))
        if key in memo:
            return
        memo.add(key)
        _, ch, gi, si, minimum, maximum = rows[i]
        top = 0 if ch in used or maximum == 0 else min(maximum, left, gr[gi], sr[si] if si >= 0 else left)
        if top >= minimum:
            for v in range(top, minimum - 1, -1):
                plan[i] = v
                ngr = list(gr); ngr[gi] -= v
                nsr = list(sr)
                if si >= 0:
                    nsr[si] -= v
                visit(i + 1, left - v, tuple(ngr), tuple(nsr), used | {ch}, total + v)
        plan[i] = 0
        visit(i + 1, left, gr, sr, used, total)

    visit(0, pool, g_caps, s_caps, set(), 0)
    grants = {rows[i][0]: best_plan[i] for i in range(n)}
    assignments = [{'req_id': q['req_id'], 'workshop_id': q['workshop_id'],
                    'reagent_id': q['reagent_id'], 'allocated_units': grants[q['req_id']],
                    'served': grants[q['req_id']] > 0}
                   for q in sorted(reqs, key=lambda q: q['req_id'])]
    return {'pool_units': pool, 'assignments': assignments, 'allocated_total': best}


def main(data, output):
    patches = read_csv(data, 'patch_calendar.csv')
    patches.sort(key=lambda p: int(p['ordinal']))
    patch_ord = {p['patch_id']: int(p['ordinal']) for p in patches}
    day_patch = {d: p['patch_id'] for p in patches for d in range(int(p['opens_day']), int(p['closes_day']) + 1)}
    first_day = min(int(p['opens_day']) for p in patches)
    last_day = max(int(p['closes_day']) for p in patches)
    reagents = {r['reagent_id']: r for r in read_csv(data, 'reagent_registry.csv')}
    reagent_ids = sorted(reagents)
    scarce_ids = sorted(r for r in reagents if int(reagents[r]['scarce']))
    artifacts = {a['artifact_id']: a for a in read_csv(data, 'artifact_catalogue.csv')}
    recipes = defaultdict(dict)
    for row in read_csv(data, 'recipe_editions.csv'):
        if row.get('recalled', '').strip().lower() in ('1', 'true', 'yes'):
            continue
        key = (row['artifact_id'], patch_ord[row['from_patch']])
        recipes[key][row['reagent_id']] = int(row['units_per_craft'])
    recipe_lists = defaultdict(list)
    for (artifact, ordinal), lines in recipes.items():
        recipe_lists[artifact].append((ordinal, lines))
    for ls in recipe_lists.values():
        ls.sort()
    registry = {w['workshop_id']: w for w in read_csv(data, 'workshop_registry.csv')}
    workshops = {wid: w for wid, w in registry.items()
                 if int(w['opened_day']) <= first_day
                 and (not w['closed_day'] or int(w['closed_day']) >= last_day)
                 and int(w['charter_tier']) >= 2}
    workshop_ids = sorted(workshops)
    guild_ids = sorted({w['guild_id'] for w in workshops.values()})
    events = read_csv(data, 'smith_identity_events.csv')
    events.sort(key=lambda e: (int(e['day']), e['event_id']))
    ledger = read_csv(data, 'crafting_ledger.csv')
    ledger.sort(key=lambda e: (int(e['day']), e['entry_id']))
    by_id = {e['entry_id']: e for e in ledger}
    acquisitions = read_csv(data, 'reagent_acquisitions.csv')
    acqs_by_day = defaultdict(list)
    for a in acquisitions:
        if int(a['day']) in day_patch:
            acqs_by_day[int(a['day'])].append(a)
    for ls in acqs_by_day.values():
        ls.sort(key=lambda a: a['acq_id'])
    opening = {r['reagent_id']: int(r['opening_units']) for r in read_csv(data, 'vault_opening.csv')}
    reqs = read_json(data, 'requisitions.json')['requisitions']
    charter = read_json(data, 'season_charter.json')
    rulings = read_json(data, 'council_rulings.json')
    schedule, rounding, order, scarcity_ref = infer_conventions(rulings)
    retired_reagent_day = {r: int(next(p['opens_day'] for p in patches if p['patch_id'] == row['retired_patch']))
                           for r, row in reagents.items() if row['retired_patch']}

    def canonical(handle, day):
        redirects = {}
        for e in events:
            if int(e['day']) > day:
                break
            if e['kind'] in ('rename', 'merge'):
                redirects[e['from_ref']] = e['to_ref']
        seen = set()
        while handle in redirects and handle not in seen:
            seen.add(handle)
            handle = redirects[handle]
        return handle

    def retired(handle, day):
        identity = canonical(handle, day)
        status = False
        for e in events:
            if int(e['day']) > day:
                break
            if e['kind'] in ('retire', 'register') and canonical(e['from_ref'], int(e['day'])) == identity:
                status = e['kind'] == 'retire'
        return status

    registration_patch = {}
    for e in events:
        if e['kind'] == 'register':
            identity = canonical(e['from_ref'], int(e['day']))
            registration_patch.setdefault(identity, day_patch.get(int(e['day'])))

    def edition(artifact, day):
        if artifact not in artifacts or day not in day_patch:
            return None
        ordinal = patch_ord[day_patch[day]]
        result = None
        for start, lines in recipe_lists.get(artifact, ()):
            if start <= ordinal:
                result = lines
            else:
                break
        return result

    def settle(indices, full=False):
        vault = opening.copy()
        acquired = Counter(); consumed = Counter(); returned = Counter(); called = Counter()
        patch_flow = {p['patch_id']: {'acquired': Counter(), 'consumed': Counter(), 'returned': Counter(), 'opening': {}}
                      for p in patches}
        findings = []
        forge_state = {}
        credited = set()
        closed = set()
        cap_ledger = Counter()
        charges = Counter()
        workshop_admitted = Counter(); workshop_rejected = Counter()
        smiths = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
        flows = defaultdict(lambda: defaultdict(lambda: [0, 0]))
        admitted = 0; credited_count = 0
        current_day = None
        current_patch = None
        dated_entries = ledger + [{'_dummy': True, 'day': str(day), 'entry_id': ''} for day in day_patch]
        dated_entries.sort(key=lambda e: (int(e['day']), e['entry_id']))
        for entry in dated_entries:
            day = int(entry['day'])
            if day != current_day:
                current_day = day
                if day in day_patch and day_patch[day] != current_patch:
                    current_patch = day_patch[day]
                    patch_flow[current_patch]['opening'] = vault.copy()
                for a in acqs_by_day.get(day, ()):
                    r = a['reagent_id']; units = int(a['units'])
                    vault[r] += units; acquired[r] += units
                    patch_flow[day_patch[day]]['acquired'][r] += units
            if entry.get('_dummy'):
                continue
            eid = entry['entry_id']; wid = entry['workshop_id']
            smith = canonical(entry['smith_ref'], day)
            source = by_id.get(entry['forge_ref']) if entry['op'] == 'salvage' else None
            source_day = int(source['day']) if source is not None else day
            lines = edition(entry['artifact_id'], source_day)
            codes = []
            if wid not in workshops:
                codes.append(('OUT_OF_SCOPE_WORKSHOP', wid))
            if retired(entry['smith_ref'], day):
                codes.append(('RETIRED_SMITH', smith))
            if entry['op'] == 'salvage' and (source is None or source['op'] != 'forge'):
                codes.append(('MISSING_FORGE_REF', entry['forge_ref']))
            if lines is None:
                codes.append(('UNRESOLVED_EDITION', entry['artifact_id']))
            if wid in workshops:
                smiths[wid][smith]
            if not codes:
                if entry['op'] == 'forge':
                    art = artifacts[entry['artifact_id']]
                    family_pct = int(charter['family_multiplier'][art['family']])
                    grade_pct = 100 + int(charter['grade_step']) * max(int(reagents[r]['grade']) for r in lines)
                    scarcity_pct = 100 + sum(indices.get(r, 0) for r in lines if r in scarce_ids)
                    value = int(art['base_charge'])
                    for op in order:
                        value = reduce_ratio(value * {'F': family_pct, 'G': grade_pct,
                                                       'S': scarcity_pct}[op], 100, rounding)
                    charge = value * int(entry['units'])
                    if registration_patch.get(smith) == day_patch.get(day) and smith in registration_patch:
                        charge = reduce_ratio(charge * 80, 100, rounding)
                    w = workshops[wid]
                    tier = str(w['charter_tier'])
                    cap = int(charter['tier_charge_cap'][tier])
                    if w.get('provisional', '').strip().lower() in ('1', 'true', 'yes'):
                        cap //= 2
                    if charter.get('extension_patch'):
                        allowance = charter.get('tier_extension_allowance', charter.get('extension_allowance', {}))
                        cap += int(allowance.get(tier, 0))
                    if wid in closed or cap_ledger[wid] + charge > cap:
                        codes.append(('CAP_REACHED', wid))
                        closed.add(wid)
                    draws = {r: amount * int(entry['units']) for r, amount in lines.items()}
                    for r, amount in draws.items():
                        if r in scarce_ids:
                            called[r] += amount
                    shortage = sorted(r for r, amount in draws.items() if vault[r] < amount)
                    if shortage:
                        codes.append(('STOCK_FLOOR', shortage[0]))
                    retired_lines = sorted(r for r in lines if r in retired_reagent_day and day >= retired_reagent_day[r])
                    if retired_lines:
                        codes.append(('RETIRED_REAGENT', retired_lines[0]))
                    if not codes:
                        for r, amount in draws.items():
                            vault[r] -= amount; consumed[r] += amount
                            patch_flow[day_patch[day]]['consumed'][r] += amount
                            flows[wid][r][0] += amount
                        cap_ledger[wid] += charge
                        charges[wid] += charge
                        smiths[wid][smith][0] += 1
                        smiths[wid][smith][2] += charge
                        forge_state[eid] = {'entry': entry, 'charge': charge, 'lines': lines,
                                            'family': art['family'], 'day': day}
                else:
                    if entry['forge_ref'] in credited:
                        codes.append(('SALVAGE_ALREADY_CREDITED', entry['forge_ref']))
                    else:
                        state = forge_state.get(entry['forge_ref'])
                        eligible = False
                        if state is not None:
                            family = state['family']
                            prior = [fid for fid, f in forge_state.items()
                                     if fid not in credited and f['day'] < day and f['family'] == family
                                     and canonical(f['entry']['smith_ref'], day) == smith]
                            eligible = entry['forge_ref'] in prior[-3:]
                        if not eligible:
                            codes.append(('UNCREDITED_SALVAGE', entry['forge_ref']))
                    if not codes:
                        state = forge_state[entry['forge_ref']]
                        tier = int(artifacts[entry['artifact_id']]['tier'])
                        for r, amount in lines.items():
                            quantity = reduce_ratio(amount * int(state['entry']['units']) * schedule[tier - 1], 100, rounding)
                            vault[r] += quantity; returned[r] += quantity
                            patch_flow[day_patch[day]]['returned'][r] += quantity
                            flows[wid][r][1] += quantity
                        credited.add(entry['forge_ref'])
                        cap_ledger[state['entry']['workshop_id']] -= state['charge']
                        smiths[wid][smith][1] += 1
                        credited_count += 1
            for code, detail in codes:
                findings.append({'entry_id': eid, 'code': code, 'detail': detail})
            if codes:
                if wid in workshops:
                    workshop_rejected[wid] += 1
            else:
                admitted += 1
                if wid in workshops:
                    workshop_admitted[wid] += 1
        result_indices = {}
        for r in scarce_ids:
            reference = {'opening': opening[r], 'opening-plus-acquired': opening[r] + acquired[r],
                         'consumed': called[r], 'acquired': acquired[r]}[scarcity_ref]
            result_indices[r] = min(int(charter['scarcity_ceiling']),
                                    reduce_ratio(consumed[r] * 100, reference, rounding) if reference else 0)
        if not full:
            return result_indices
        for i, p in enumerate(patches):
            pid = p['patch_id']
            if not patch_flow[pid]['opening']:
                patch_flow[pid]['opening'] = opening.copy() if i == 0 else patch_flow[patches[i-1]['patch_id']]['closing'].copy()
            close = {}
            for r in reagent_ids:
                close[r] = (patch_flow[pid]['opening'][r] + patch_flow[pid]['acquired'][r]
                            + patch_flow[pid]['returned'][r] - patch_flow[pid]['consumed'][r])
            patch_flow[pid]['closing'] = close
        return locals()

    def fixed_point():
        ceiling = int(charter['scarcity_ceiling'])
        seeds = [tuple([0] * len(scarce_ids)), tuple([ceiling] * len(scarce_ids)),
                 tuple([ceiling // 2] * len(scarce_ids))]
        evaluated = {}
        def evaluate(v):
            if v not in evaluated:
                evaluated[v] = tuple(settle(dict(zip(scarce_ids, v)))[r] for r in scarce_ids)
            return evaluated[v]
        for seed in seeds:
            v = seed
            for _ in range(100):
                nxt = evaluate(v)
                if nxt == v:
                    return dict(zip(scarce_ids, v))
                if nxt in evaluated:
                    break
                v = nxt
        # The register bounds every coordinate. Search the finite remaining space
        # if feedback from caps and salvage prevents iteration from converging.
        for v in product(range(ceiling + 1), repeat=len(scarce_ids)):
            if evaluate(v) == v:
                return dict(zip(scarce_ids, v))
        raise ValueError('No scarcity fixed point')

    indices = fixed_point()
    s = settle(indices, full=True)
    if s['result_indices'] != indices:
        raise ValueError('Scarcity fixed point changed on final settlement')
    vault = s['vault']; acquired = s['acquired']; consumed = s['consumed']; returned = s['returned']
    allocation = allocate(reqs, workshops, charter, reagents, vault)
    allocated_workshop = Counter()
    for q in allocation['assignments']:
        allocated_workshop[q['workshop_id']] += q['allocated_units']
    season_charge = sum(s['charges'].values())
    patch_rows = []
    for p in patches:
        pf = s['patch_flow'][p['patch_id']]
        rr = []
        for r in reagent_ids:
            op = pf['opening'][r]; ac = pf['acquired'][r]; ret = pf['returned'][r]
            con = pf['consumed'][r]; close = pf['closing'][r]
            rr.append({'reagent_id': r, 'opening_units': op, 'acquired_units': ac,
                       'returned_units': ret, 'consumed_units': con, 'closing_units': close,
                       'residual': op + ac + ret - con - close})
        patch_rows.append({'patch_id': p['patch_id'], 'ordinal': int(p['ordinal']),
                           'reagents': rr, 'residual': sum(abs(x['residual']) for x in rr)})
    season_residual = sum(p['residual'] for p in patch_rows)
    guild_charge = {g: sum(s['charges'][w] for w in workshop_ids if workshops[w]['guild_id'] == g)
                    for g in guild_ids}
    summary = {'season': {'first_day': first_day, 'last_day': last_day, 'patch_count': len(patches)},
               'workshops_in_scope': workshop_ids, 'guilds_in_scope': guild_ids,
               'entries_total': len(ledger), 'entries_admitted': s['admitted'],
               'entries_rejected': len(ledger) - s['admitted'],
               'credited_salvages': s['credited_count'],
               'uncredited_salvages': sum(f['code'] == 'UNCREDITED_SALVAGE' for f in s['findings']),
               'scarcity_index': {r: indices[r] for r in scarce_ids},
               'season_charge_ember': season_charge,
               'allocated_units_total': allocation['allocated_total'],
               'conservation_residual': sum(abs(opening[r] + acquired[r] + returned[r] - consumed[r] - vault[r]) for r in reagent_ids)}
    vault_audit = {'reagents': [{'reagent_id': r, 'grade': int(reagents[r]['grade']),
                                 'scarce': bool(int(reagents[r]['scarce'])),
                                 'opening_units': opening[r], 'acquired_units': acquired[r],
                                 'returned_units': returned[r], 'consumed_units': consumed[r],
                                 'closing_units': vault[r], 'scarcity_index': indices.get(r, 0)}
                                for r in reagent_ids]}
    reconciliation = {'patches': patch_rows, 'season_residual': season_residual,
                      'charge_by_workshop': {w: s['charges'][w] for w in workshop_ids},
                      'charge_by_guild': guild_charge, 'charge_total': season_charge}
    findings = sorted(s['findings'], key=lambda f: (f['entry_id'], f['code']))
    counts = Counter(f['code'] for f in findings)
    data_quality = {'findings': findings, 'counts': {c: counts[c] for c in sorted(counts)}}
    output.mkdir(parents=True, exist_ok=True)
    write_json(output, 'summary.json', summary)
    write_json(output, 'vault_audit.json', vault_audit)
    write_json(output, 'reconciliation.json', reconciliation)
    write_json(output, 'data_quality.json', data_quality)
    write_json(output, 'allocation.json', allocation)
    for wid in workshop_ids:
        w = workshops[wid]
        tier = str(w['charter_tier'])
        cap = int(charter['tier_charge_cap'][tier])
        if w.get('provisional', '').strip().lower() in ('1', 'true', 'yes'):
            cap //= 2
        if charter.get('extension_patch'):
            allowance = charter.get('tier_extension_allowance', charter.get('extension_allowance', {}))
            cap += int(allowance.get(tier, 0))
        wf = s['flows'][wid]
        report = {'workshop_id': wid, 'guild_id': w['guild_id'], 'charter_id': w['charter_id'],
                  'charter_tier': int(w['charter_tier']),
                  'entries_admitted': s['workshop_admitted'][wid],
                  'entries_rejected': s['workshop_rejected'][wid],
                  'charge_ember': s['charges'][wid], 'cap_ember': cap,
                  'cap_reached': wid in s['closed'], 'allocated_units': allocated_workshop[wid],
                  'smiths': [{'canonical_smith': smith, 'admitted_forges': x[0],
                              'credited_salvages': x[1], 'charge_ember': x[2]}
                             for smith, x in sorted(s['smiths'][wid].items())],
                  'reagent_flow': [{'reagent_id': r, 'consumed_units': x[0],
                                    'returned_units': x[1], 'net_units': x[0] - x[1]}
                                   for r, x in sorted(wf.items())]}
        write_json(output, f'workshop_{wid}.json', report)
    for gid in guild_ids:
        members = [w for w in workshop_ids if workshops[w]['guild_id'] == gid]
        flow = defaultdict(lambda: [0, 0])
        for wid in members:
            for r, x in s['flows'][wid].items():
                flow[r][0] += x[0]; flow[r][1] += x[1]
        report = {'guild_id': gid, 'workshops': members,
                  'entries_admitted': sum(s['workshop_admitted'][w] for w in members),
                  'charge_ember': guild_charge[gid],
                  'allocated_units': sum(allocated_workshop[w] for w in members),
                  'reagent_flow': [{'reagent_id': r, 'consumed_units': x[0],
                                    'returned_units': x[1], 'net_units': x[0] - x[1]}
                                   for r, x in sorted(flow.items())]}
        write_json(output, f'guild_{gid}.json', report)


if __name__ == '__main__':
    main(Path(sys.argv[1] if len(sys.argv) > 1 else '/app/data'),
         Path(sys.argv[2] if len(sys.argv) > 2 else '/app/out'))
