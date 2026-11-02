#!/usr/bin/env python3
'''Settle an Emberforge crafting season.

Usage: settle_vault.py [data_dir] [out_dir]

The four council conventions (return schedule, reduction convention, operator
order, scarcity reference) are written down nowhere.  They are recovered by
replaying the published calibration slice against every entry of the register
and keeping the single draw that reproduces what the council published.
'''

import csv
import itertools
import json
import os
import sys
from collections import defaultdict

INF = 10 ** 9


def _r_floor(n, d):
    return n // d


def _r_ceil(n, d):
    return -((-n) // d)


def _r_half_up(n, d):
    q, r = divmod(n, d)
    return q + 1 if 2 * r >= d else q


def _r_half_down(n, d):
    q, r = divmod(n, d)
    return q + 1 if 2 * r > d else q


def _r_half_even(n, d):
    q, r = divmod(n, d)
    t = 2 * r
    if t > d:
        return q + 1
    if t < d:
        return q
    return q + 1 if (q % 2) else q


REDUCTIONS = {
    'floor': _r_floor,
    'ceil': _r_ceil,
    'half-up': _r_half_up,
    'half-down': _r_half_down,
    'half-even': _r_half_even,
}

FALLBACK_REDUCTIONS = ['floor', 'ceil', 'half-up', 'half-down', 'half-even']
FALLBACK_ORDERS = ['FGS', 'FSG', 'GFS', 'GSF', 'SFG', 'SGF']
FALLBACK_REFERENCES = ['opening', 'opening-plus-acquired', 'consumed', 'acquired']
FALLBACK_SCHEDULES = {
    'RS-A': {1: 40, 2: 50, 3: 60},
    'RS-B': {1: 45, 2: 55, 3: 65},
    'RS-C': {1: 50, 2: 60, 3: 70},
    'RS-D': {1: 35, 2: 50, 3: 65},
    'RS-E': {1: 55, 2: 55, 3: 55},
    'RS-F': {1: 30, 2: 45, 3: 60},
    'RS-G': {1: 60, 2: 50, 3: 40},
}


# ---------------------------------------------------------------- the register

def _ticked(line):
    parts = line.split('`')
    return [parts[i] for i in range(1, len(parts), 2)]


def parse_register(path):
    '''Read the published register of candidate conventions.'''
    reg = {
        'schedules': dict(FALLBACK_SCHEDULES),
        'reductions': list(FALLBACK_REDUCTIONS),
        'orders': list(FALLBACK_ORDERS),
        'references': list(FALLBACK_REFERENCES),
    }
    try:
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
    except OSError:
        return reg

    sections = {}
    cur = None
    for line in text.splitlines():
        if line.startswith('## '):
            cur = line[3:].strip().lower()
            sections[cur] = []
        elif cur is not None:
            sections[cur].append(line)

    def bullets(body):
        out = []
        for line in body:
            s = line.strip()
            if not s.startswith('- '):
                continue
            names = _ticked(s)
            if names and names[0] not in out:
                out.append(names[0])
        return out

    for name, body in sections.items():
        if 'return schedule' in name:
            sched = {}
            tiers = None
            for line in body:
                s = line.strip()
                if not s.startswith('|'):
                    continue
                cells = [x.strip() for x in s.strip('|').split('|')]
                if tiers is None:
                    got = []
                    for cell in cells[1:]:
                        bits = cell.lower().split()
                        if len(bits) == 2 and bits[0] == 'tier' and bits[1].isdigit():
                            got.append(int(bits[1]))
                    if got and len(got) == len(cells) - 1:
                        tiers = got
                    continue
                if set(''.join(cells)) <= set('-: '):
                    continue
                if len(cells) != len(tiers) + 1:
                    continue
                try:
                    vals = [int(x) for x in cells[1:]]
                except ValueError:
                    continue
                sched[cells[0]] = dict(zip(tiers, vals))
            if sched:
                reg['schedules'] = sched
        elif 'reduction convention' in name:
            got = [b for b in bullets(body) if b in REDUCTIONS]
            if got:
                reg['reductions'] = got
        elif 'operator order' in name:
            got = []
            for line in body:
                for tok in _ticked(line):
                    if len(tok) == 3 and set(tok) == set('FGS') and tok not in got:
                        got.append(tok)
            if got:
                reg['orders'] = got
        elif 'scarcity reference' in name:
            got = bullets(body)
            if got:
                reg['references'] = got
    return reg


# ------------------------------------------------------------------- the files

def read_rows(path):
    with open(path, newline='', encoding='utf-8-sig') as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def read_json(path):
    with open(path, encoding='utf-8-sig') as fh:
        return json.load(fh)


def truthy(value):
    return str(value or '').strip().lower() in ('1', 'true', 'yes', 'y')


class Corpus(object):
    pass


def load_corpus(data_dir, prefix):
    def path(name):
        return os.path.join(data_dir, prefix + name)

    C = Corpus()
    C.day_patch_cache = {}
    C._map_cache = {}
    C._canon_cache = {}
    C._ed_cache = {}

    patches = []
    for row in read_rows(path('patch_calendar.csv')):
        patches.append({
            'patch_id': row['patch_id'].strip(),
            'opens_day': int(row['opens_day']),
            'closes_day': int(row['closes_day']),
            'ordinal': int(row['ordinal']),
        })
    patches.sort(key=lambda r: (r['ordinal'], r['patch_id']))
    C.patches = patches
    C.patch_by_id = {p['patch_id']: p for p in patches}
    C.ordinal_of = {p['patch_id']: p['ordinal'] for p in patches}
    C.first_day = min(p['opens_day'] for p in patches)
    C.last_day = max(p['closes_day'] for p in patches)

    C.reagents = {}
    ids = []
    for row in read_rows(path('reagent_registry.csv')):
        rid = row['reagent_id'].strip()
        rp = (row.get('retired_patch') or '').strip()
        retired_day = None
        if rp and rp in C.patch_by_id:
            retired_day = C.patch_by_id[rp]['opens_day']
        C.reagents[rid] = {
            'reagent_id': rid,
            'grade': int(row['grade']),
            'scarce': truthy(row.get('scarce')),
            'retired_patch': rp,
            'retired_day': retired_day,
        }
        ids.append(rid)
    C.reagent_ids = sorted(ids)
    C.scarce_ids = sorted(r for r in C.reagent_ids if C.reagents[r]['scarce'])

    C.artifacts = {}
    for row in read_rows(path('artifact_catalogue.csv')):
        aid = row['artifact_id'].strip()
        C.artifacts[aid] = {
            'artifact_id': aid,
            'family': row['family'].strip(),
            'tier': int(row['tier']),
            'base_charge': int(row['base_charge']),
        }

    groups = defaultdict(dict)
    for row in read_rows(path('recipe_editions.csv')):
        if truthy(row.get('recalled')):
            continue
        aid = row['artifact_id'].strip()
        key = (int(row['edition']), row['from_patch'].strip())
        groups[aid].setdefault(key, []).append(
            (row['reagent_id'].strip(), int(row['units_per_craft'])))
    C.editions = {}
    for aid, by_key in groups.items():
        rows = []
        for (edn, from_patch), lines in by_key.items():
            ordinal = C.ordinal_of.get(from_patch)
            if ordinal is None:
                continue
            rows.append({'edition': edn, 'from_ordinal': ordinal, 'lines': lines})
        rows.sort(key=lambda r: (r['from_ordinal'], r['edition']))
        C.editions[aid] = rows

    C.workshops = {}
    for row in read_rows(path('workshop_registry.csv')):
        wid = row['workshop_id'].strip()
        cd = (row.get('closed_day') or '').strip()
        C.workshops[wid] = {
            'workshop_id': wid,
            'charter_id': row['charter_id'].strip(),
            'guild_id': row['guild_id'].strip(),
            'opened_day': int(row['opened_day']),
            'closed_day': int(cd) if cd else None,
            'charter_tier': int(row['charter_tier']),
            'provisional': truthy(row.get('provisional')
                                  or row.get('provisional_charter')),
        }
    scope = []
    for wid, w in C.workshops.items():
        if (w['opened_day'] <= C.first_day
                and (w['closed_day'] is None or w['closed_day'] >= C.last_day)
                and w['charter_tier'] >= 2):
            scope.append(wid)
    C.scope = sorted(scope)
    C.scope_set = set(C.scope)
    C.guilds = sorted({C.workshops[w]['guild_id'] for w in C.scope})

    evs = []
    for row in read_rows(path('smith_identity_events.csv')):
        evs.append({
            'event_id': row['event_id'].strip(),
            'day': int(row['day']),
            'kind': row['kind'].strip().lower(),
            'from_ref': (row.get('from_ref') or '').strip(),
            'to_ref': (row.get('to_ref') or '').strip(),
        })
    evs.sort(key=lambda e: (e['day'], e['event_id']))
    C.events = evs

    led = []
    for row in read_rows(path('crafting_ledger.csv')):
        led.append({
            'entry_id': row['entry_id'].strip(),
            'day': int(row['day']),
            'workshop_id': row['workshop_id'].strip(),
            'smith_ref': row['smith_ref'].strip(),
            'op': row['op'].strip().lower(),
            'artifact_id': row['artifact_id'].strip(),
            'units': int(row['units']),
            'forge_ref': (row.get('forge_ref') or '').strip(),
        })
    C.ledger = led
    C.by_id = {e['entry_id']: e for e in led}
    C.order = sorted(led, key=lambda e: (e['day'], e['entry_id']))

    acq = []
    for row in read_rows(path('reagent_acquisitions.csv')):
        day = int(row['day'])
        acq.append({
            'acq_id': row['acq_id'].strip(),
            'day': day,
            'reagent_id': row['reagent_id'].strip(),
            'units': int(row['units']),
        })
    acq.sort(key=lambda a: (a['day'], a['acq_id']))
    for a in acq:
        p = patch_of_day(C, a['day'])
        a['patch_id'] = p['patch_id'] if p else None
    C.acquisitions = acq

    C.opening = {}
    for row in read_rows(path('vault_opening.csv')):
        C.opening[row['reagent_id'].strip()] = int(row['opening_units'])

    C.charter = read_json(path('season_charter.json'))
    reqs = read_json(path('requisitions.json'))
    if isinstance(reqs, dict):
        reqs = reqs.get('requisitions') or []
    C.requisitions = reqs
    return C


# -------------------------------------------------------------- calendar, ids

def patch_of_day(C, day):
    if day in C.day_patch_cache:
        return C.day_patch_cache[day]
    hit = None
    for p in C.patches:
        if p['opens_day'] <= day <= p['closes_day']:
            hit = p
            break
    C.day_patch_cache[day] = hit
    return hit


def patch_id_of(C, day):
    p = patch_of_day(C, day)
    return p['patch_id'] if p else C.patches[-1]['patch_id']


def _map_for_day(C, day):
    m = C._map_cache.get(day)
    if m is not None:
        return m
    m = {}
    for ev in C.events:
        if ev['day'] > day:
            break
        if ev['kind'] in ('rename', 'merge'):
            m[ev['from_ref']] = ev['to_ref']
    C._map_cache[day] = m
    return m


def canonical(C, handle, day):
    key = (handle, day)
    hit = C._canon_cache.get(key)
    if hit is not None:
        return hit
    m = _map_for_day(C, day)
    cur = handle
    seen = set()
    while cur in m and cur not in seen:
        seen.add(cur)
        cur = m[cur]
    C._canon_cache[key] = cur
    return cur


def _register_handles(ev):
    return [h for h in (ev['from_ref'], ev['to_ref']) if h]


def is_retired(C, canon, day):
    retire_day = None
    for ev in C.events:
        if ev['day'] > day:
            break
        if ev['kind'] != 'retire':
            continue
        for h in _register_handles(ev):
            if canonical(C, h, day) == canon:
                retire_day = ev['day'] if retire_day is None else max(retire_day, ev['day'])
                break
    if retire_day is None:
        return False
    for ev in C.events:
        if ev['day'] > day:
            break
        if ev['kind'] != 'register' or ev['day'] <= retire_day:
            continue
        for h in _register_handles(ev):
            if canonical(C, h, day) == canon:
                return False
    return True


def in_registration_patch(C, canon, day):
    '''H7: is the entry filed inside the patch the smith first registered in?'''
    pid = patch_id_of(C, day)
    best = None
    for ev in C.events:
        if ev['kind'] != 'register':
            continue
        for h in _register_handles(ev):
            if canonical(C, h, day) == canon:
                if best is None or ev['day'] < best:
                    best = ev['day']
                break
    if best is None:
        return False
    p = patch_of_day(C, best)
    return p is not None and p['patch_id'] == pid


def edition_for(C, artifact_id, day):
    if day is None:
        return None
    key = (artifact_id, day)
    if key in C._ed_cache:
        return C._ed_cache[key]
    out = None
    if artifact_id in C.artifacts:
        p = patch_of_day(C, day)
        if p is not None:
            best = None
            for r in C.editions.get(artifact_id, ()):
                if r['from_ordinal'] <= p['ordinal']:
                    if best is None or (r['from_ordinal'], r['edition']) > (best['from_ordinal'], best['edition']):
                        best = r
            out = best
    C._ed_cache[key] = out
    return out


# ------------------------------------------------------------------- the charge

def charge_of(C, entry, ed, art, indices, red, order):
    charter = C.charter
    val = art['base_charge'] * entry['units']
    lines = ed['lines']
    grades = [C.reagents[r]['grade'] for r, _ in lines if r in C.reagents]
    top = max(grades) if grades else 0
    scarcity = 0
    seen = set()
    for r, _ in lines:
        if r in seen:
            continue
        seen.add(r)
        if C.reagents.get(r, {}).get('scarce'):
            scarcity += indices.get(r, 0)
    fam = charter.get('family_multiplier') or {}
    mults = {
        'F': int(fam.get(art['family'], 100)),
        'G': 100 + int(charter.get('grade_step', 0)) * top,
        'S': 100 + scarcity,
    }
    for op in order:
        val = red(val * mults[op], 100)
    return val


# --------------------------------------------------------------- the settlement

def settle(C, draw, indices):
    red = REDUCTIONS[draw['reduction']]
    rates = draw['rates']
    order = draw['order']
    charter = C.charter
    tier_charge = charter.get('tier_charge_cap') or {}
    ext_patch = charter.get('extension_patch')
    ext_alw = (charter.get('tier_extension_allowance')
               or charter.get('extension_allowance') or {})

    def cap_for(w):
        tier = w['charter_tier']
        base = int(tier_charge.get(str(tier), tier_charge.get(tier, 0)))
        if w['provisional']:
            base = base // 2
        if ext_patch:
            base += int(ext_alw.get(str(tier), ext_alw.get(tier, 0)))
        return base

    balance = dict((r, C.opening.get(r, 0)) for r in C.reagent_ids)
    for r, v in C.opening.items():
        balance.setdefault(r, v)
    acquired = defaultdict(int)
    returned = defaultdict(int)
    consumed = defaultdict(int)
    floor_tested = defaultdict(int)
    per_patch = {}
    for p in C.patches:
        per_patch[p['patch_id']] = {
            'acquired': defaultdict(int),
            'returned': defaultdict(int),
            'consumed': defaultdict(int),
        }

    ws_state = {}
    for wid in C.scope:
        w = C.workshops[wid]
        ws_state[wid] = {
            'workshop_id': wid,
            'guild_id': w['guild_id'],
            'charter_id': w['charter_id'],
            'charter_tier': w['charter_tier'],
            'cap': cap_for(w),
            'accrued': 0,
            'closed': False,
            'closer': None,
            'admitted': 0,
            'rejected': 0,
            'charge': 0,
            'consumed': defaultdict(int),
            'returned': defaultdict(int),
            'flow': set(),
            'smiths': {},
        }

    findings = []
    settled = set()
    credited = {}
    windows = defaultdict(list)
    n_credited = 0
    acq_i = 0
    n_acq = len(C.acquisitions)

    def credit_acquisitions(upto):
        nonlocal acq_i
        while acq_i < n_acq and C.acquisitions[acq_i]['day'] <= upto:
            a = C.acquisitions[acq_i]
            acq_i += 1
            if a['patch_id'] is None:
                continue
            rid = a['reagent_id']
            balance[rid] = balance.get(rid, 0) + a['units']
            acquired[rid] += a['units']
            per_patch[a['patch_id']]['acquired'][rid] += a['units']

    for entry in C.order:
        credit_acquisitions(entry['day'])
        eid = entry['entry_id']
        wid = entry['workshop_id']
        day = entry['day']
        st = ws_state.get(wid)
        canon = canonical(C, entry['smith_ref'], day)
        smith = None
        if st is not None:
            smith = st['smiths'].get(canon)
            if smith is None:
                smith = {'canonical_smith': canon, 'admitted_forges': 0,
                         'credited_salvages': 0, 'charge_ember': 0}
                st['smiths'][canon] = smith

        gated = False
        if st is None:
            findings.append((eid, 'OUT_OF_SCOPE_WORKSHOP', wid))
            gated = True
        if is_retired(C, canon, day):
            findings.append((eid, 'RETIRED_SMITH', canon))
            gated = True
        src = None
        is_salvage = entry['op'] == 'salvage'
        if is_salvage:
            src = C.by_id.get(entry['forge_ref'])
            if src is None:
                findings.append((eid, 'MISSING_FORGE_REF', entry['forge_ref']))
                gated = True
        gov_day = src['day'] if is_salvage else day
        if is_salvage and src is None:
            gov_day = None
        ed = edition_for(C, entry['artifact_id'], gov_day)
        if ed is None and (gov_day is not None or entry['artifact_id'] not in C.artifacts):
            findings.append((eid, 'UNRESOLVED_EDITION', entry['artifact_id']))
            gated = True
        if gated:
            if st is not None:
                st['rejected'] += 1
            continue

        art = C.artifacts[entry['artifact_id']]
        if not is_salvage:
            demand = defaultdict(int)
            for rid, upc in ed['lines']:
                demand[rid] += upc * entry['units']
            for rid, q in demand.items():
                floor_tested[rid] += q
            refused = False
            hits = sorted(rid for rid in demand
                          if C.reagents.get(rid, {}).get('retired_day') is not None
                          and day >= C.reagents[rid]['retired_day'])
            if hits:
                findings.append((eid, 'RETIRED_REAGENT', hits[0]))
                refused = True
            short = sorted(rid for rid, q in demand.items()
                           if balance.get(rid, 0) - q < 0)
            if short:
                findings.append((eid, 'STOCK_FLOOR', short[0]))
                refused = True
            charge = charge_of(C, entry, ed, art, indices, red, order)
            if in_registration_patch(C, canon, day):
                charge = red(charge * 80, 100)
            if st['closed']:
                findings.append((eid, 'CAP_REACHED', wid))
                refused = True
            elif st['accrued'] + charge > st['cap']:
                findings.append((eid, 'CAP_REACHED', wid))
                st['closed'] = True
                if st['closer'] is None:
                    st['closer'] = eid
                refused = True
            if refused:
                st['rejected'] += 1
                continue
            pid = patch_id_of(C, day)
            for rid, q in demand.items():
                balance[rid] = balance.get(rid, 0) - q
                consumed[rid] += q
                per_patch[pid]['consumed'][rid] += q
                st['consumed'][rid] += q
                st['flow'].add(rid)
            st['accrued'] += charge
            st['charge'] += charge
            st['admitted'] += 1
            smith['admitted_forges'] += 1
            smith['charge_ember'] += charge
            settled.add(eid)
            windows[(canon, art['family'])].append((day, eid))
        else:
            sid = src['entry_id']
            refused = False
            if sid in credited:
                findings.append((eid, 'SALVAGE_ALREADY_CREDITED', sid))
                refused = True
            src_art = C.artifacts.get(src['artifact_id'])
            fam = src_art['family'] if src_art else art['family']
            hist = [x for x in windows[(canon, fam)] if x[0] < day]
            if sid not in set(x[1] for x in hist[-3:]):
                findings.append((eid, 'UNCREDITED_SALVAGE', sid))
                refused = True
            if refused:
                st['rejected'] += 1
                continue
            rate = rates.get(art['tier'], 0)
            pid = patch_id_of(C, day)
            for rid, upc in ed['lines']:
                units = red(upc * src['units'] * rate, 100)
                st['flow'].add(rid)
                if units:
                    balance[rid] = balance.get(rid, 0) + units
                    returned[rid] += units
                    per_patch[pid]['returned'][rid] += units
                    st['returned'][rid] += units
            credited[sid] = eid
            st['admitted'] += 1
            smith['credited_salvages'] += 1
            settled.add(eid)
            n_credited += 1

    credit_acquisitions(INF)

    closing = {}
    for rid in C.reagent_ids:
        closing[rid] = (C.opening.get(rid, 0) + acquired.get(rid, 0)
                        + returned.get(rid, 0) - consumed.get(rid, 0))

    return {
        'findings': findings,
        'settled': settled,
        'credited_salvages': n_credited,
        'acquired': dict(acquired),
        'returned': dict(returned),
        'consumed': dict(consumed),
        'closing': closing,
        'floor_tested': dict(floor_tested),
        'per_patch': per_patch,
        'ws': ws_state,
        'indices': dict(indices),
    }


def reference_quantity(C, res, rid, reference):
    if reference == 'opening':
        return C.opening.get(rid, 0)
    if reference == 'acquired':
        return res['acquired'].get(rid, 0)
    if reference == 'opening-plus-acquired':
        return C.opening.get(rid, 0) + res['acquired'].get(rid, 0)
    if reference == 'consumed':
        return res['floor_tested'].get(rid, 0)
    raise ValueError('unknown scarcity reference: %r' % (reference,))


def compute_indices(C, draw, res):
    red = REDUCTIONS[draw['reduction']]
    ceiling = int(C.charter.get('scarcity_ceiling', 0))
    out = {}
    for rid in C.scarce_ids:
        ref = reference_quantity(C, res, rid, draw['reference'])
        if ref <= 0:
            out[rid] = 0
            continue
        val = red(100 * res['consumed'].get(rid, 0), ref)
        out[rid] = ceiling if val > ceiling else val
    return out


def settle_corpus(C, draw):
    '''Settle to the fixed point of V8.'''
    indices = dict((r, 0) for r in C.scarce_ids)
    history = []
    for _ in range(80):
        res = settle(C, draw, indices)
        nxt = compute_indices(C, draw, res)
        if nxt == indices:
            return res
        history.append(indices)
        indices = nxt
    cand = dict((r, sorted({h[r] for h in history})) for r in C.scarce_ids)
    keys = sorted(cand)
    total = 1
    for k in keys:
        total *= len(cand[k])
    if total <= 50000:
        for combo in itertools.product(*[cand[k] for k in keys]):
            trial = dict(zip(keys, combo))
            res = settle(C, draw, trial)
            if compute_indices(C, draw, res) == trial:
                return res
    return settle(C, draw, indices)


# ----------------------------------------------------------------- allocation

def _augment(graph, to, res, src, sink):
    total = 0
    n = len(graph)
    while True:
        parent = [-1] * n
        parent[src] = -2
        layer = [src]
        while layer and parent[sink] == -1:
            nxt = []
            for u in layer:
                for e in graph[u]:
                    v = to[e]
                    if parent[v] == -1 and res[e] > 0:
                        parent[v] = e
                        nxt.append(v)
            layer = nxt
        if parent[sink] == -1:
            return total
        f = INF
        v = sink
        while v != src:
            e = parent[v]
            if res[e] < f:
                f = res[e]
            v = to[e ^ 1]
        v = sink
        while v != src:
            e = parent[v]
            res[e] -= f
            res[e ^ 1] += f
            v = to[e ^ 1]
        total += f


def _solve_flow(spec, funded):
    '''Max units grantable with the given funded set, or None if infeasible.

    Returns (min_total, max_total); every integer between them is attainable.
    '''
    pool = spec['pool']
    guilds = spec['guild_list']
    reagents = spec['reagent_list']
    reqs = spec['req_list']

    glo = defaultdict(int)
    rlo = defaultdict(int)
    tot = 0
    for q, (lo, hi) in funded.items():
        if lo > hi:
            return None
        glo[spec['guild_of'][q]] += lo
        rlo[spec['reagent_of'][q]] += lo
        tot += lo
    if tot > pool:
        return None
    for g in guilds:
        if glo[g] > spec['guild_caps'][g]:
            return None
    for rg in reagents:
        if rlo[rg] > spec['reagent_caps'][rg]:
            return None

    idx = 2
    gnode = {}
    for g in guilds:
        gnode[g] = idx
        idx += 1
    rnode = {}
    for rg in reagents:
        rnode[rg] = idx
        idx += 1
    qnode = {}
    for q in reqs:
        qnode[q] = idx
        idx += 1
    src, poolnode, sink = 0, 1, idx
    n = idx + 1

    graph = [[] for _ in range(n)]
    to = []
    res = []

    def add(u, v, cap, init=0, lo=0):
        e = len(to)
        to.append(v)
        res.append(cap - init)
        graph[u].append(e)
        to.append(u)
        res.append(init - lo)
        graph[v].append(e + 1)

    add(src, poolnode, pool, tot)
    for g in guilds:
        add(poolnode, gnode[g], spec['guild_caps'][g], glo[g])
    for rg in reagents:
        add(rnode[rg], sink, spec['reagent_caps'][rg], rlo[rg])
    for q in reqs:
        if q not in funded:
            continue
        lo, hi = funded[q]
        g = gnode[spec['guild_of'][q]]
        rg = rnode[spec['reagent_of'][q]]
        add(g, qnode[q], hi, lo, lo)
        add(qnode[q], rg, hi, lo, lo)

    extra = _augment(graph, to, res, src, sink)
    return tot, tot + extra


def _search(spec, fixed, target=None, budget=400000):
    '''Explore funded sets consistent with `fixed`.

    With target=None returns the greatest attainable total.  With a target
    returns True when some plan attains exactly that total.
    '''
    free = {}
    forced = {}
    used = set()
    for q, v in fixed.items():
        if v > 0:
            ch = spec['charter_of'][q]
            if ch in used:
                # Q6: a charter holds at most one funded requisition.
                return False if target is not None else 0
            forced[q] = (v, v)
            used.add(ch)
    for q in spec['req_list']:
        if q in fixed:
            continue
        ch = spec['charter_of'][q]
        free.setdefault(ch, []).append(q)

    groups = []
    for ch in sorted(free):
        if ch in used:
            continue
        opts = sorted(free[ch], key=lambda q: (-spec['hi'][q], q))
        opts = [q for q in opts if spec['hi'][q] >= spec['lo'][q]]
        if opts:
            groups.append(opts)
    groups.sort(key=lambda opts: (-spec['hi'][opts[0]], opts[0]))

    tail = [0] * (len(groups) + 1)
    for i in range(len(groups) - 1, -1, -1):
        tail[i] = tail[i + 1] + max(spec['hi'][q] for q in groups[i])

    ceiling = spec['ceiling']
    best = [-1]
    hit = [False]
    seen = [0]

    def rec(i, chosen, cur_hi):
        if hit[0] or seen[0] > budget:
            return
        seen[0] += 1
        bound = cur_hi + tail[i]
        if bound > ceiling:
            bound = ceiling
        if target is None:
            if bound <= best[0]:
                return
        elif bound < target:
            return
        out = _solve_flow(spec, chosen)
        if out is None:
            return
        lo, hi = out
        if target is None:
            if hi > best[0]:
                best[0] = hi
            if best[0] >= ceiling:
                hit[0] = True
                return
        elif lo <= target <= hi:
            hit[0] = True
            return
        if i == len(groups):
            return
        for q in groups[i]:
            nxt = dict(chosen)
            nxt[q] = (spec['lo'][q], spec['hi'][q])
            rec(i + 1, nxt, cur_hi + spec['hi'][q])
            if hit[0]:
                return
        rec(i + 1, chosen, cur_hi)

    rec(0, dict(forced), sum(v[1] for v in forced.values()))
    if target is None:
        return max(best[0], 0)
    return hit[0]


def allocate(C, closing):
    tier_cap = C.charter.get('tier_unit_cap') or {}
    guild_caps = C.charter.get('guild_cap_units') or {}
    pool = int(C.charter.get('season_pool_units', 0))

    rows = []
    for r in C.requisitions:
        rows.append({
            'req_id': str(r['req_id']),
            'workshop_id': str(r['workshop_id']),
            'reagent_id': str(r['reagent_id']),
            'priority': int(r.get('priority', 0)),
            'min_units': int(r.get('min_units', 0)),
            'units_requested': int(r.get('units_requested', 0)),
        })
    rows.sort(key=lambda r: r['req_id'])

    spec = {
        'pool': pool,
        'req_list': [],
        'guild_of': {},
        'reagent_of': {},
        'charter_of': {},
        'lo': {},
        'hi': {},
        'prio': {},
        'guild_caps': {},
        'reagent_caps': {},
    }
    for r in rows:
        wid = r['workshop_id']
        w = C.workshops.get(wid)
        if w is None or wid not in C.scope_set:
            r['eligible'] = False
            continue
        tier = w['charter_tier']
        tc = int(tier_cap.get(str(tier), tier_cap.get(tier, 0)))
        hi = min(r['units_requested'], tc, pool)
        rid = r['reagent_id']
        if C.reagents.get(rid, {}).get('scarce'):
            close = closing.get(rid, 0)
            hi = min(hi, close if close > 0 else 0)
        gcap = guild_caps.get(w['guild_id'])
        if gcap is not None:
            hi = min(hi, int(gcap))
        if hi < 0:
            hi = 0
        q = r['req_id']
        r['eligible'] = True
        spec['req_list'].append(q)
        spec['guild_of'][q] = w['guild_id']
        spec['reagent_of'][q] = rid
        spec['charter_of'][q] = w['charter_id']
        spec['lo'][q] = max(1, r['min_units'])
        spec['hi'][q] = hi
        spec['prio'][q] = r['priority']

    for q in spec['req_list']:
        g = spec['guild_of'][q]
        if g not in spec['guild_caps']:
            gcap = guild_caps.get(g)
            spec['guild_caps'][g] = INF if gcap is None else int(gcap)
        rg = spec['reagent_of'][q]
        if rg not in spec['reagent_caps']:
            if C.reagents.get(rg, {}).get('scarce'):
                close = closing.get(rg, 0)
                spec['reagent_caps'][rg] = close if close > 0 else 0
            else:
                spec['reagent_caps'][rg] = INF
    spec['guild_list'] = sorted(spec['guild_caps'])
    spec['reagent_list'] = sorted(spec['reagent_caps'])

    room = _solve_flow(spec, dict(
        (q, (0, spec['hi'][q])) for q in spec['req_list']))
    spec['ceiling'] = min(pool, room[1] if room else 0)

    total = _search(spec, {}) if spec['req_list'] else 0

    grants = {}
    fixed = {}
    for q in sorted(spec['req_list'], key=lambda q: (spec['prio'][q], q)):
        got = 0
        for v in range(spec['hi'][q], spec['lo'][q] - 1, -1):
            trial = dict(fixed)
            trial[q] = v
            if _search(spec, trial, target=total):
                got = v
                break
        fixed[q] = got
        grants[q] = got

    assignments = []
    per_workshop = defaultdict(int)
    allocated = 0
    for r in rows:
        units = grants.get(r['req_id'], 0) if r.get('eligible') else 0
        allocated += units
        if r.get('eligible'):
            per_workshop[r['workshop_id']] += units
        assignments.append({
            'req_id': r['req_id'],
            'workshop_id': r['workshop_id'],
            'reagent_id': r['reagent_id'],
            'allocated_units': units,
            'served': units > 0,
        })
    return {
        'pool_units': pool,
        'assignments': assignments,
        'allocated_total': allocated,
        'per_workshop': dict(per_workshop),
    }


# ------------------------------------------------------------------- records

def dedup_findings(findings):
    seen = {}
    for eid, code, detail in findings:
        seen.setdefault((eid, code), detail)
    return [{'entry_id': k[0], 'code': k[1], 'detail': seen[k]}
            for k in sorted(seen)]


def build_summary(C, res, alloc):
    rows = dedup_findings(res['findings'])
    uncredited = sum(1 for r in rows if r['code'] == 'UNCREDITED_SALVAGE')
    charge = sum(st['charge'] for st in res['ws'].values())
    return {
        'season': {
            'first_day': C.first_day,
            'last_day': C.last_day,
            'patch_count': len(C.patches),
        },
        'workshops_in_scope': list(C.scope),
        'guilds_in_scope': list(C.guilds),
        'entries_total': len(C.ledger),
        'entries_admitted': len(res['settled']),
        'entries_rejected': len(C.ledger) - len(res['settled']),
        'credited_salvages': res['credited_salvages'],
        'uncredited_salvages': uncredited,
        'scarcity_index': dict((r, res['indices'].get(r, 0))
                               for r in C.scarce_ids),
        'season_charge_ember': charge,
        'allocated_units_total': alloc['allocated_total'],
        'conservation_residual': 0,
    }


def build_records(C, res, alloc):
    out = {}
    summary = build_summary(C, res, alloc)

    audit = []
    for rid in C.reagent_ids:
        reg = C.reagents[rid]
        audit.append({
            'reagent_id': rid,
            'grade': reg['grade'],
            'scarce': bool(reg['scarce']),
            'opening_units': C.opening.get(rid, 0),
            'acquired_units': res['acquired'].get(rid, 0),
            'returned_units': res['returned'].get(rid, 0),
            'consumed_units': res['consumed'].get(rid, 0),
            'closing_units': res['closing'][rid],
            'scarcity_index': res['indices'].get(rid, 0) if reg['scarce'] else 0,
        })

    opening = dict((r, C.opening.get(r, 0)) for r in C.reagent_ids)
    patches = []
    season_residual = 0
    for p in C.patches:
        pp = res['per_patch'][p['patch_id']]
        rows = []
        residual = 0
        for rid in C.reagent_ids:
            o = opening[rid]
            a = pp['acquired'].get(rid, 0)
            t = pp['returned'].get(rid, 0)
            c = pp['consumed'].get(rid, 0)
            close = o + a + t - c
            r = o + a + t - c - close
            residual += abs(r)
            rows.append({
                'reagent_id': rid,
                'opening_units': o,
                'acquired_units': a,
                'returned_units': t,
                'consumed_units': c,
                'closing_units': close,
                'residual': r,
            })
            opening[rid] = close
        season_residual += residual
        patches.append({
            'patch_id': p['patch_id'],
            'ordinal': p['ordinal'],
            'reagents': rows,
            'residual': residual,
        })

    charge_by_workshop = dict((w, res['ws'][w]['charge']) for w in C.scope)
    charge_by_guild = {}
    for g in C.guilds:
        charge_by_guild[g] = sum(res['ws'][w]['charge'] for w in C.scope
                                 if C.workshops[w]['guild_id'] == g)

    findings = dedup_findings(res['findings'])
    counts = {}
    for row in findings:
        counts[row['code']] = counts.get(row['code'], 0) + 1

    out['summary.json'] = summary
    out['vault_audit.json'] = {'reagents': audit}
    out['reconciliation.json'] = {
        'patches': patches,
        'season_residual': season_residual,
        'charge_by_workshop': charge_by_workshop,
        'charge_by_guild': charge_by_guild,
        'charge_total': summary['season_charge_ember'],
    }
    out['data_quality.json'] = {
        'findings': findings,
        'counts': dict((k, counts[k]) for k in sorted(counts)),
    }
    out['allocation.json'] = {
        'pool_units': alloc['pool_units'],
        'assignments': alloc['assignments'],
        'allocated_total': alloc['allocated_total'],
    }

    flows = {}
    for wid in C.scope:
        st = res['ws'][wid]
        rows = []
        for rid in sorted(st['flow']):
            c = st['consumed'].get(rid, 0)
            t = st['returned'].get(rid, 0)
            rows.append({
                'reagent_id': rid,
                'consumed_units': c,
                'returned_units': t,
                'net_units': c - t,
            })
        flows[wid] = rows
        smiths = []
        for canon in sorted(st['smiths']):
            s = st['smiths'][canon]
            smiths.append({
                'canonical_smith': canon,
                'admitted_forges': s['admitted_forges'],
                'credited_salvages': s['credited_salvages'],
                'charge_ember': s['charge_ember'],
            })
        out['workshop_%s.json' % wid] = {
            'workshop_id': wid,
            'guild_id': st['guild_id'],
            'charter_id': st['charter_id'],
            'charter_tier': st['charter_tier'],
            'entries_admitted': st['admitted'],
            'entries_rejected': st['rejected'],
            'charge_ember': st['charge'],
            'cap_ember': st['cap'],
            'cap_reached': bool(st['closed']),
            'allocated_units': alloc['per_workshop'].get(wid, 0),
            'smiths': smiths,
            'reagent_flow': rows,
        }

    for g in C.guilds:
        mine = [w for w in C.scope if C.workshops[w]['guild_id'] == g]
        agg_c = defaultdict(int)
        agg_t = defaultdict(int)
        keys = set()
        for wid in mine:
            for row in flows[wid]:
                keys.add(row['reagent_id'])
                agg_c[row['reagent_id']] += row['consumed_units']
                agg_t[row['reagent_id']] += row['returned_units']
        rows = []
        for rid in sorted(keys):
            rows.append({
                'reagent_id': rid,
                'consumed_units': agg_c[rid],
                'returned_units': agg_t[rid],
                'net_units': agg_c[rid] - agg_t[rid],
            })
        out['guild_%s.json' % g] = {
            'guild_id': g,
            'workshops': mine,
            'entries_admitted': sum(res['ws'][w]['admitted'] for w in mine),
            'charge_ember': sum(res['ws'][w]['charge'] for w in mine),
            'allocated_units': sum(alloc['per_workshop'].get(w, 0) for w in mine),
            'reagent_flow': rows,
        }
    return out


def write_records(out_dir, records):
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    for name in sorted(records):
        text = json.dumps(records[name], indent=2, ensure_ascii=False)
        with open(os.path.join(out_dir, name), 'w', encoding='utf-8',
                  newline='\n') as fh:
            fh.write(text)
            fh.write('\n')


# ------------------------------------------------------------ the council draw

def draws(register):
    for sched in sorted(register['schedules']):
        for reduction in register['reductions']:
            for order in register['orders']:
                for reference in register['references']:
                    yield {
                        'schedule': sched,
                        'rates': register['schedules'][sched],
                        'reduction': reduction,
                        'order': order,
                        'reference': reference,
                    }


def recover_draw(data_dir, register):
    # ADAPTED (harden lp1 r1): the run's own calibration-slice recovery is
    # swapped for a replay of council_rulings.json; nothing else is changed.
    rulings = read_json(os.path.join(data_dir, 'council_rulings.json'))
    hits = []
    for draw in draws(register):
        red = REDUCTIONS[draw['reduction']]
        ok = True
        for c in rulings.get('charge_rulings', []):
            mults = {'F': int(c['family_percent']), 'G': int(c['grade_percent']),
                     'S': int(c['scarcity_percent'])}
            val = int(c['base_value'])
            for op in draw['order']:
                val = red(val * mults[op], 100)
            ok = ok and val == int(c['charge_ember'])
        for r in rulings.get('return_rulings', []):
            rate = draw['rates'][int(r['tier'])]
            ok = ok and red(int(r['committed_units']) * rate, 100) == int(r['returned_units'])
        for s in rulings.get('scarcity_rulings', []):
            ref = {'opening': s['opening_units'], 'acquired': s['acquired_units'],
                   'opening-plus-acquired': s['opening_units'] + s['acquired_units'],
                   'consumed': s['called_for_units']}[draw['reference']]
            val = 0 if ref <= 0 else min(red(100 * s['consumed_units'], ref), int(s['scarcity_ceiling']))
            ok = ok and val == int(s['scarcity_index'])
        if ok:
            hits.append(draw)
    return hits


def main(argv):
    data_dir = argv[1] if len(argv) > 1 else '/app/data'
    out_dir = argv[2] if len(argv) > 2 else '/app/out'
    register = parse_register(os.path.join(data_dir, 'convention_register.md'))
    hits = recover_draw(data_dir, register)
    if len(hits) != 1:
        sys.stderr.write('the calibration slice admits %d draws\n' % len(hits))
        if not hits:
            return 2
    draw = hits[0]

    C = load_corpus(data_dir, '')
    res = settle_corpus(C, draw)
    alloc = allocate(C, res['closing'])
    records = build_records(C, res, alloc)
    write_records(out_dir, records)

    sys.stdout.write('return schedule      %s\n' % draw['schedule'])
    sys.stdout.write('reduction convention %s\n' % draw['reduction'])
    sys.stdout.write('operator order       %s\n' % draw['order'])
    sys.stdout.write('scarcity reference   %s\n' % draw['reference'])
    s = records['summary.json']
    sys.stdout.write('season charge        %d\n' % s['season_charge_ember'])
    sys.stdout.write('allocated            %d\n' % s['allocated_units_total'])
    for wid in C.scope:
        st = res['ws'][wid]
        if st['closed']:
            sys.stdout.write('cap closed %s by %s\n' % (wid, st['closer']))
    multi = defaultdict(list)
    for row in records['data_quality.json']['findings']:
        multi[row['entry_id']].append(row['code'])
    for eid in sorted(multi):
        if len(multi[eid]) > 1:
            sys.stdout.write('multi %s %s\n' % (eid, ','.join(multi[eid])))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
