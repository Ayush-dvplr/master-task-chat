#!/usr/bin/env python3
"""Random tiny instances: compare derive_report.py with a brute force search."""
import csv, itertools, json, os, random, shutil, subprocess, sys
from datetime import datetime, timedelta

PROG = '/app/out/derive_report.py'
TMP = '/tmp/fuzz'


def gen(seed):
    rnd = random.Random(seed)
    root = f'{TMP}/data'
    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(root + '/docs')
    slot_minutes = 60
    per_day = 1440 // slot_minutes
    nslots = rnd.randint(3, 4)
    plan_day = datetime(2026, 5, rnd.randint(2, 20))
    start_hour = rnd.choice([12, 20, 22])
    first = plan_day + timedelta(hours=start_hour)
    plan_date = plan_day.strftime('%Y-%m-%d')
    next_date = (plan_day + timedelta(days=1)).strftime('%Y-%m-%d')
    slots = [first + timedelta(minutes=slot_minutes * i) for i in range(nslots)]
    snames = [s.strftime('%Y-%m-%dT%H:%M') for s in slots]
    feeder = rnd.randint(3, 9)
    with open(root + '/grid.ini', 'w') as f:
        f.write(f"[plan]\nplan_date = {plan_date}\nfirst_slot = "
                f"{first.strftime('%Y-%m-%dT%H:%M')}\nslot_minutes = {slot_minutes}\n"
                f"slots = {nslots}\n\n[feeder]\nfeeder_kwh_per_slot = {feeder}\n")
    ndep = rnd.randint(1, 2)
    dep_names = ['North', 'South', 'West', 'East'][:ndep]
    cabkwh = rnd.randint(2, 3)
    depots = {'cabinet_kwh_per_slot': cabkwh,
              'depots': [{'depot': d, 'cabinets': rnd.randint(1, 3)} for d in dep_names]}
    json.dump(depots, open(root + '/depots.json', 'w'), indent=2)
    types = {'T1': {'max_kwh_per_slot': rnd.randint(1, 3), 'reserve_kwh': rnd.randint(0, 3)},
             'T2': {'max_kwh_per_slot': rnd.randint(1, 3), 'reserve_kwh': rnd.randint(0, 3)}}
    json.dump(types, open(root + '/bus_types.json', 'w'), indent=2)
    wpub, wcom = rnd.randint(2, 5), 1
    open(root + '/service_classes.ini', 'w').write(
        f"[public]\nweight = {wpub}\n\n[commercial]\nweight = {wcom}\n")
    contracts = {'contracts': [{'contract_id': 'P1', 'class': 'public'},
                               {'contract_id': 'C1', 'class': 'commercial'}]}
    json.dump(contracts, open(root + '/contracts.json', 'w'), indent=2)

    nbus = rnd.randint(2, 4)
    bus_ids = ['B%03d' % (100 + i) for i in range(nbus)]
    fleet = []
    for b in bus_ids:
        fleet.append({'vehicle_id': b, 'type': rnd.choice(['T1', 'T2']),
                      'home_depot': rnd.choice(dep_names), 'status': 'active'})
    fleet.append({'vehicle_id': 'BRET', 'type': 'T1', 'home_depot': dep_names[0],
                  'status': 'retired'})
    with open(root + '/fleet_register.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, ['vehicle_id', 'type', 'home_depot', 'status'])
        w.writeheader()
        for r in fleet:
            w.writerow(r)

    roster_rows = []
    truth = []
    for b in bus_ids:
        lo = rnd.randint(0, nslots - 1)
        hi = rnd.randint(lo + 1, nslots)
        arrive = slots[lo]
        depart = slots[hi - 1] + timedelta(minutes=slot_minutes)
        soc = rnd.randint(0, 3)
        contract = rnd.choice(['P1', 'C1', '', 'ZZ'])
        depot = rnd.choice(dep_names)
        roster_rows.append({'plan_date': plan_date, 'bus_id': b, 'depot': depot,
                            'arrive': arrive.strftime('%Y-%m-%dT%H:%M'),
                            'depart': depart.strftime('%Y-%m-%dT%H:%M'),
                            'soc_arrival_kwh': soc, 'contract_id': contract})
        truth.append({'bus_id': b, 'depot': depot, 'lo': lo, 'hi': hi, 'soc': soc,
                      'contract': contract})
    # noise rows
    noise = [
        {'plan_date': plan_date, 'bus_id': 'BRET', 'depot': dep_names[0],
         'arrive': snames[0], 'depart': snames[-1], 'soc_arrival_kwh': 0,
         'contract_id': ''},
        {'plan_date': plan_date, 'bus_id': 'BXXX', 'depot': dep_names[0],
         'arrive': snames[0], 'depart': snames[-1], 'soc_arrival_kwh': 0,
         'contract_id': ''},
        {'plan_date': plan_date, 'bus_id': bus_ids[0], 'depot': dep_names[0],
         'arrive': snames[0], 'depart': snames[-1], 'soc_arrival_kwh': 0,
         'contract_id': ''},
        {'plan_date': plan_date, 'bus_id': bus_ids[-1], 'depot': dep_names[0],
         'arrive': snames[-1], 'depart': snames[0], 'soc_arrival_kwh': 0,
         'contract_id': ''},
        {'plan_date': (plan_day - timedelta(days=3)).strftime('%Y-%m-%d'),
         'bus_id': bus_ids[0], 'depot': dep_names[0],
         'arrive': (first - timedelta(days=3)).strftime('%Y-%m-%dT%H:%M'),
         'depart': (first - timedelta(days=3) + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
         'soc_arrival_kwh': 0, 'contract_id': ''},
    ]
    rows = roster_rows + noise
    rnd.shuffle(rows)
    with open(root + '/roster.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, ['plan_date', 'bus_id', 'depot', 'arrive', 'depart',
                               'soc_arrival_kwh', 'contract_id'])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    trips = []
    for t in truth:
        for _ in range(rnd.randint(0, 2)):
            trips.append({'trip_id': 'X%d' % len(trips), 'bus_id': t['bus_id'],
                          'service_date': next_date, 'kwh': rnd.randint(0, 4)})
        trips.append({'trip_id': 'Y%d' % len(trips), 'bus_id': t['bus_id'],
                      'service_date': plan_date, 'kwh': 9})
    rnd.shuffle(trips)
    with open(root + '/trips.jsonl', 'w') as f:
        for t in trips:
            f.write(json.dumps(t) + '\n')

    # tariff: bands on hour boundaries over the 24h day
    cuts = sorted(rnd.sample(range(0, per_day), rnd.randint(2, 4)))
    prices = [None] * per_day
    band_txt = []
    pricelist = rnd.sample(range(5, 40), len(cuts))
    for i, c in enumerate(cuts):
        nxt = cuts[(i + 1) % len(cuts)]
        band_txt.append('    <band from="%02d:00" to="%02d:00" cents_per_kwh="%d"/>'
                        % (c, nxt, pricelist[i]))
        j = c
        while True:
            prices[j % per_day] = pricelist[i]
            j += 1
            if j % per_day == nxt % per_day:
                break
    other = ('  <version valid_from="2026-01-01" valid_to="2026-04-30">\n'
             '    <band from="00:00" to="00:00" cents_per_kwh="7"/>\n  </version>\n')
    with open(root + '/tariff.xml', 'w') as f:
        f.write('<?xml version="1.0"?>\n<tariff>\n' + other +
                '  <version valid_from="2026-05-01" valid_to="2026-06-30">\n' +
                '\n'.join(band_txt) + '\n  </version>\n</tariff>\n')

    def price_at(dt, k):
        tod = (dt.hour * 60 + dt.minute) // slot_minutes
        return prices[(tod + k) % per_day]

    ks = {d: rnd.randrange(per_day) for d in dep_names}
    settle = []
    cands = {d: set(range(per_day)) for d in dep_names}
    tries = 0
    while any(len(cands[d]) > 1 for d in dep_names) and tries < 400:
        tries += 1
        d = rnd.choice(dep_names)
        if len(cands[d]) == 1:
            continue
        sd = plan_day - timedelta(days=rnd.randint(1, 10))
        st = sd + timedelta(hours=rnd.randrange(per_day))
        n = rnd.randint(1, 3)
        per = rnd.randint(1, 4)
        kwh = per * n
        cents = sum(per * price_at(st + timedelta(minutes=slot_minutes * i), ks[d])
                    for i in range(n))
        row = {'settled_date': sd.strftime('%Y-%m-%d'), 'depot': d, 'bus_id': 'B100',
               'start': st.strftime('%Y-%m-%dT%H:%M'),
               'end': (st + timedelta(minutes=slot_minutes * n)).strftime('%Y-%m-%dT%H:%M'),
               'kwh': kwh, 'cents': cents}
        if sd.strftime('%Y-%m-%d') < '2026-05-01':
            continue
        settle.append(row)
        keep = set()
        for k in cands[d]:
            tot = sum(per * price_at(st + timedelta(minutes=slot_minutes * i), k)
                      for i in range(n))
            if tot == cents:
                keep.add(k)
        cands[d] = keep
    if any(len(cands[d]) != 1 for d in dep_names):
        return None
    with open(root + '/settlements.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, ['settled_date', 'depot', 'bus_id', 'start', 'end',
                               'kwh', 'cents'])
        w.writeheader()
        for r in settle:
            w.writerow(r)

    pub = []
    pub_map = {}
    for t in truth:
        for s in range(nslots):
            if rnd.random() < 0.4:
                kwh = rnd.randint(1, 3)
                pub.append({'plan_date': plan_date, 'bus_id': t['bus_id'],
                            'slot_start': snames[s], 'kwh': kwh})
                if t['lo'] <= s < t['hi']:
                    pub_map[(t['bus_id'], s)] = pub_map.get((t['bus_id'], s), 0) + kwh
    pub.append({'plan_date': plan_date, 'bus_id': 'BZZZ', 'slot_start': snames[0], 'kwh': 1})
    with open(root + '/published_plan.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, ['plan_date', 'bus_id', 'slot_start', 'kwh'])
        w.writeheader()
        for r in pub:
            w.writerow(r)

    lines = ['# Disruption notice for %s' % plan_date, '', '## Cabinet outages', '']
    outages = []
    if rnd.random() < 0.6:
        d = rnd.choice(dep_names)
        a = rnd.randrange(nslots)
        b = rnd.randint(a + 1, nslots)
        n = rnd.randint(1, 2)
        lines.append('- %s: %d cabinets out of service from %s to %s'
                     % (d, n, snames[a],
                        (slots[b - 1] + timedelta(minutes=slot_minutes)).strftime('%Y-%m-%dT%H:%M')))
        outages.append((d, n, a, b))
    lines += ['', '## Feeder derating', '']
    derates = []
    if rnd.random() < 0.6:
        a = rnd.randrange(nslots)
        b = rnd.randint(a + 1, nslots)
        v = rnd.randint(1, feeder)
        lines.append('- from %s to %s: feeder limit %d kWh per slot'
                     % (snames[a],
                        (slots[b - 1] + timedelta(minutes=slot_minutes)).strftime('%Y-%m-%dT%H:%M'), v))
        derates.append((a, b, v))
    lines += ['', '## Extra trips', '']
    extras = {}
    for t in truth:
        if rnd.random() < 0.4:
            k = rnd.randint(1, 3)
            lines.append('- %s: extra trip on %s, %d kWh' % (t['bus_id'], next_date, k))
            extras[t['bus_id']] = extras.get(t['bus_id'], 0) + k
    open(root + '/disruption_notice.md', 'w').write('\n'.join(lines) + '\n')
    open(root + '/docs/charging_rules.md', 'w').write('rules\n')

    # ---- independent model
    tripneed = {}
    for t in trips:
        if t['service_date'] == next_date:
            tripneed[t['bus_id']] = tripneed.get(t['bus_id'], 0) + t['kwh']
    model = []
    for t in truth:
        ty = next(r for r in fleet if r['vehicle_id'] == t['bus_id'])['type']
        mk = types[ty]['max_kwh_per_slot']
        res = types[ty]['reserve_kwh']
        need = max(0, tripneed.get(t['bus_id'], 0) + extras.get(t['bus_id'], 0)
                   + res - t['soc'])
        cls = {'P1': 'public', 'C1': 'commercial'}.get(t['contract'], 'commercial')
        model.append({'bus_id': t['bus_id'], 'depot': t['depot'], 'lo': t['lo'],
                      'hi': t['hi'], 'need': need, 'max': mk,
                      'weight': wpub if cls == 'public' else wcom, 'cls': cls})
    model.sort(key=lambda m: m['bus_id'])
    cab_cap = {}
    for d in dep_names:
        c0 = next(x['cabinets'] for x in depots['depots'] if x['depot'] == d)
        for s in range(nslots):
            c = c0
            for od, on, a, b in outages:
                if od == d and a <= s < b:
                    c -= on
            cab_cap[(d, s)] = max(c, 0) * cabkwh
    feed = []
    for s in range(nslots):
        lim = feeder
        for a, b, v in derates:
            if a <= s < b:
                lim = v
        feed.append(lim)
    price = {}
    for d in dep_names:
        for s in range(nslots):
            price[(d, s)] = price_at(slots[s], ks[d])
    pub_idx = {}
    for (bid, s), v in pub_map.items():
        pub_idx[(bid, s)] = v
    return {'root': root, 'nslots': nslots, 'snames': snames, 'buses': model,
            'cab': cab_cap, 'feed': feed, 'price': price, 'pub': pub_idx,
            'dep_names': dep_names, 'plan_date': plan_date}


def brute(inst):
    buses = inst['buses']
    nslots = inst['nslots']
    opts = []
    for b in buses:
        choices = []
        span = range(b['lo'], b['hi'])
        for vec in itertools.product(range(b['max'] + 1), repeat=len(span)):
            if sum(vec) > b['need']:
                continue
            full = [0] * nslots
            for i, s in enumerate(span):
                full[s] = vec[i]
            choices.append(full)
        opts.append(choices)
    best = None
    bestplan = None
    for combo in itertools.product(*opts):
        ok = True
        for s in range(nslots):
            tot = 0
            dep = {}
            for b, vec in zip(buses, combo):
                dep[b['depot']] = dep.get(b['depot'], 0) + vec[s]
                tot += vec[s]
            if tot > inst['feed'][s]:
                ok = False
                break
            for d, v in dep.items():
                if v > inst['cab'][(d, s)]:
                    ok = False
                    break
            if not ok:
                break
        if not ok:
            continue
        wu = 0
        cost = 0
        moved = 0
        for b, vec in zip(buses, combo):
            wu += b['weight'] * (b['need'] - sum(vec))
            for s in range(nslots):
                cost += inst['price'][(b['depot'], s)] * vec[s]
                p = inst['pub'].get((b['bus_id'], s), 0)
                if p > vec[s]:
                    moved += p - vec[s]
        lex = tuple(-combo[bi][s] for s in range(nslots) for bi in range(len(buses)))
        key = (wu, cost, moved) + lex
        if best is None or key < best:
            best = key
            bestplan = combo
    return best, bestplan


def run(seed):
    inst = gen(seed)
    if inst is None:
        return 'skip'
    r = subprocess.run([sys.executable, PROG, '--data', inst['root'],
                        '--out', TMP + '/out'], capture_output=True, text=True)
    if r.returncode != 0:
        return 'program failed: %s' % r.stderr
    best, bestplan = brute(inst)
    if best is None:
        return 'no feasible plan in brute force'
    audit = json.load(open(TMP + '/out/policy_audit.json'))
    got = {}
    for b in audit['buses']:
        for c in b['charges']:
            got[(b['bus_id'], inst['snames'].index(c['slot']))] = c['kwh']
    want = {}
    for b, vec in zip(inst['buses'], bestplan):
        for s in range(inst['nslots']):
            if vec[s]:
                want[(b['bus_id'], s)] = vec[s]
    if got != want:
        return 'PLAN MISMATCH\n got %s\n want %s' % (sorted(got.items()), sorted(want.items()))
    summ = json.load(open(TMP + '/out/summary.json'))
    if (summ['weighted_unmet_kwh'], summ['energy_cost_cents'], summ['moved_kwh']) != best[:3]:
        return 'SUMMARY MISMATCH %s vs %s' % (
            (summ['weighted_unmet_kwh'], summ['energy_cost_cents'], summ['moved_kwh']), best[:3])
    return 'ok'


if __name__ == '__main__':
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    bad = 0
    for seed in range(lo, hi):
        res = run(seed)
        if res not in ('ok', 'skip'):
            bad += 1
            print(seed, res)
        else:
            print(seed, res)
    print('failures:', bad)
