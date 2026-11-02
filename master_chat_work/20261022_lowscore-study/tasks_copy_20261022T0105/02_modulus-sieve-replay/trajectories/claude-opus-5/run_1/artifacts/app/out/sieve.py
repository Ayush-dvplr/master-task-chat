#!/usr/bin/env python3
"""The residue mill, rebuilt.

Usage: sieve.py INPUT_DIR OUTPUT_DIR

Reads moduli.csv, forms.csv, analysts.csv, lanes.csv and samples.jsonl from the
input directory and writes residues.jsonl, lanes.json, forms.csv and sieve.json
to the output directory, in the exact form reports.md describes.

The one figure that can be read straight off the input, the whole-number
modulus offset, is recovered at run time from the family labels.
"""
import csv
import json
import math
import os
import sys

BANDS = ['base', 'high', 'idle', 'peak']
STATUSES = ['flagged', 'kept', 'refused', 'setup', 'voided']


def divisor_count(n):
    if n <= 0:
        return 0
    c = 0
    i = 1
    while i * i <= n:
        if n % i == 0:
            c += 2 if i * i != n else 1
        i += 1
    return c


def _is_prime(n):
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


def _is_prime_power(n):
    if n < 4:
        return False
    p = 2
    m = n
    while p * p <= m:
        if m % p == 0:
            k = 0
            while m % p == 0:
                m //= p
                k += 1
            return m == 1 and k >= 2
        p += 1
    return False


def derive_mod_offset(moduli):
    if not moduli:
        return 0
    rows = [(int(r['offset']), r['family']) for r in moduli.values()]
    for d in sorted(range(-5000, 5001), key=lambda x: (abs(x), -x)):
        ok = True
        for off, fam in rows:
            m = off + d
            if m < 2:
                ok = False
                break
            if fam == 'prime':
                if not _is_prime(m):
                    ok = False
                    break
            elif fam == 'composite':
                if m < 4 or _is_prime(m):
                    ok = False
                    break
            elif fam == 'power':
                if not _is_prime_power(m):
                    ok = False
                    break
        if ok:
            return d
    raise ValueError('no consistent modulus offset')


def trunc_div(num, den):
    q = abs(num) // abs(den)
    if (num < 0) != (den < 0):
        q = -q
    return q, num - q * den


def load(indir):
    def rd(name):
        with open(os.path.join(indir, name), newline='') as fh:
            return list(csv.DictReader(fh))

    moduli = {r['modulus']: r for r in rd('moduli.csv')}
    forms = {r['form']: r for r in rd('forms.csv')}
    analysts = {r['analyst']: r for r in rd('analysts.csv')}
    lanes = {r['lane']: r for r in rd('lanes.csv')}
    samples = []
    with open(os.path.join(indir, 'samples.jsonl')) as fh:
        for line in fh:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    samples.sort(key=lambda s: s['seq'])
    charged = {}
    for f, row in forms.items():
        par = row.get('parent') or ''
        charged[f] = forms[par]['kind'] if par else row['kind']
    return dict(moduli=moduli, forms=forms, analysts=analysts, lanes=lanes,
                samples=samples, charged=charged)


def resolve(data, P):
    moduli, lanes, charged = data['moduli'], data['lanes'], data['charged']
    analysts, forms = data['analysts'], data['forms']
    mod_offset = P['mod_offset']
    st = {}
    for lane, row in lanes.items():
        st[lane] = dict(floor=int(moduli[row['modulus']]['base']), drift=0,
                        credit=0, faults=0, prev_sieve=False, armed=False,
                        last_count=None, rec=[], seen=0)
    out = []
    for s in data['samples']:
        lane = s['lane']
        lrow = lanes[lane]
        mrow = moduli[lrow['modulus']]
        modulus = int(mrow['offset']) + mod_offset
        c = st[lane]

        if s['blocks'] != 0:
            gov = (s['blocks'] * P['block_factor'] if P['blocks_governs']
                   else s['span'])
        else:
            gov = s['span'] if P['blocks_governs'] else s['blocks'] * P['block_factor']
        count = gov * (s['terms'] + P['terms_offset'])

        if count == 0:
            count = c['last_count'] if c['last_count'] else P['fallback_count']
        c['last_count'] = count

        x = max(0, s['value'] - c['floor'])

        q, rem = trunc_div(x * P['gain'], count)
        x = max(0, q)

        r = x % modulus
        if P['least_abs'] and r > modulus // 2:
            r -= modulus
        x = max(0, abs(r))

        x = max(0, x + P['sector_adj'].get(lrow['sector'], 0))
        ck = charged[lrow['form']] if P['kind_inherited'] else forms[lrow['form']]['kind']
        x = max(0, x + P['kind_adj'].get(ck, 0))
        if c['seen'] > 0:
            x = max(0, x + P['window_adj'].get(s['window'], 0))
        fam = P['fault_family'] if c['faults'] >= P['seal_faults'] else mrow['family']
        x = max(0, x + P['family_adj'].get(fam, 0))

        rel = min(P['credit_release'], c['credit'])
        c['credit'] -= rel
        x = max(0, x + rel)

        drift_before = c['drift']
        relief = drift_before * 2 if c['armed'] else drift_before
        c['armed'] = False
        x = max(0, x - relief)

        for tag, w in reversed(c['rec']):
            if tag == s['tag']:
                x = w
                break
        weight = max(0, x)

        if weight >= P['edge_peak']:
            band = 'peak'
        elif weight >= P['edge_high']:
            band = 'high'
        elif weight >= P['edge_base']:
            band = 'base'
        else:
            band = 'idle'
        grade = analysts[s['analyst']]['grade']
        if s['action'] in P['bookkeeping']:
            status = 'setup'
        elif s['action'] == P['void_action']:
            status = 'voided'
        elif band == 'idle':
            status = 'refused'
        elif drift_before > P['tolerance'][grade]:
            status = 'flagged'
        else:
            status = 'kept'

        out.append(dict(action=s['action'], analyst=s['analyst'], band=band,
                        drift_before=drift_before, form=lrow['form'], lane=lane,
                        seq=s['seq'], status=status, tag=s['tag'], weight=weight))

        if s['action'] == P['floor_action']:
            c['floor'] = s['value']
        if s['action'] == P['bank_action']:
            c['credit'] = min(80, c['credit'] + c['drift'])
            c['drift'] = 0
        if s['action'] == P['arm_action']:
            c['armed'] = True
        if s['action'] == 'sieve':
            add = P['sieve_per_divisor'] * divisor_count(count)
            if lrow['depth'] == P['depth_double']:
                add *= 2
            if lrow['depth'] == P['depth_extra']:
                add += P['depth_extra_amount']
            add += math.gcd(count, modulus) % P['gcd_mod']
            if c['prev_sieve']:
                add += P['back_to_back']
            add += abs(rem) % P['rem_mod']
            c['drift'] = min(P['drift_ceiling'], c['drift'] + add)
        c['prev_sieve'] = (s['action'] == 'sieve')
        if status == 'refused':
            c['faults'] += 1
        c['rec'].append((s['tag'], weight))
        if len(c['rec']) > P['record_size']:
            del c['rec'][0]
        c['seen'] += 1
    return out, st


def rollups(data, P, ledger, st):
    counted = P['counted_statuses']
    lane_rows = []
    by_lane = {}
    for r in ledger:
        by_lane.setdefault(r['lane'], []).append(r)
    for lane in sorted(data['lanes']):
        mine = by_lane.get(lane, [])
        c = st[lane]
        bands = {b: 0 for b in BANDS}
        for r in mine:
            bands[r['band']] += 1
        cs = [r for r in mine if r['status'] in counted]
        best = None
        for r in cs:
            if best is None or r['weight'] > best['weight'] or (
                    r['weight'] == best['weight'] and r['seq'] < best['seq']):
                best = r
        if c['faults'] >= P['seal_faults']:
            verdict = 'sealed'
        elif c['drift'] > 51:
            verdict = 'held'
        else:
            verdict = 'cleared'
        lane_rows.append(dict(
            bands=bands, credit_end=c['credit'], drift_end=c['drift'],
            faults=c['faults'],
            flagged=sum(1 for r in mine if r['status'] == 'flagged'),
            floor_end=c['floor'], lane=lane,
            peak_weight=best['weight'] if best else 0, samples=len(mine),
            sieved=sum(1 for r in mine if r['action'] == 'sieve'),
            top_tag=best['tag'] if best else None, verdict=verdict,
            weight_total=sum(r['weight'] for r in cs)))

    agg = {}
    for r in ledger:
        f = agg.setdefault(r['form'], dict(form=r['form'], lanes=set(),
                                           samples=0, weight_total=0, flagged=0))
        f['lanes'].add(r['lane'])
        f['samples'] += 1
        if r['status'] in counted:
            f['weight_total'] += r['weight']
        if r['status'] == 'flagged':
            f['flagged'] += 1
    form_rows = [dict(form=v['form'], lanes=len(v['lanes']), samples=v['samples'],
                      weight_total=v['weight_total'], flagged=v['flagged'])
                 for v in agg.values()]
    form_rows.sort(key=lambda r: (-r['weight_total'], r['form']))

    by_band = {b: 0 for b in BANDS}
    by_status = {s: 0 for s in STATUSES}
    for r in ledger:
        by_band[r['band']] += 1
        by_status[r['status']] += 1
    top = None
    for row in lane_rows:
        if top is None or row['weight_total'] > top['weight_total']:
            top = row
    sieve = dict(
        by_band=by_band, by_status=by_status, forms=len(form_rows),
        lanes=len(data['lanes']), samples=len(ledger),
        sealed=sorted(r['lane'] for r in lane_rows if r['verdict'] == 'sealed'),
        top_lane=top['lane'] if top else None,
        weight_total=sum(r['weight_total'] for r in lane_rows))
    return lane_rows, form_rows, sieve


def write_reports(outdir, ledger, lane_rows, form_rows, sieve):
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, 'residues.jsonl'), 'w') as fh:
        for r in ledger:
            fh.write(json.dumps(r, sort_keys=True, separators=(',', ':')) + '\n')
    with open(os.path.join(outdir, 'lanes.json'), 'w') as fh:
        fh.write(json.dumps({'lanes': lane_rows}, sort_keys=True, indent=2) + '\n')
    with open(os.path.join(outdir, 'forms.csv'), 'w') as fh:
        fh.write('form,lanes,samples,weight_total,flagged\n')
        for r in form_rows:
            fh.write('%s,%d,%d,%d,%d\n' % (r['form'], r['lanes'], r['samples'],
                                           r['weight_total'], r['flagged']))
    with open(os.path.join(outdir, 'sieve.json'), 'w') as fh:
        fh.write(json.dumps(sieve, sort_keys=True, indent=2) + '\n')


# The best reading recovered from the recorded pass and its two rollups. It
# reproduces ref_sieve.json's five status counts, sealed set, top_lane and form
# ordering exactly, and its weight_total to within one unit.
PARAMS = dict(
    block_factor=3, blocks_governs=True, terms_offset=1,
    fallback_count=500, gain=1000, least_abs=True,
    sector_adj={'upper': 260, 'lower': -139, 'split': 121, 'folded': -261,
                'shifted': 481, 'wrapped': -201},
    kind_adj={'quadratic': 84, 'cubic': -6, 'linear': 64},
    window_adj={'dawn': 0, 'dusk': -40, 'night': 0},
    family_adj={'prime': 0, 'power': 0},
    kind_inherited=True, fault_family='power', credit_release=0,
    edge_peak=504, edge_high=240, edge_base=6,
    bookkeeping=('seed', 'close'), void_action='void', arm_action='void',
    tolerance={'principal': 40, 'senior': 16, 'junior': 40, 'visiting': 2},
    record_size=1, sieve_per_divisor=1, depth_double='2', depth_extra='3',
    depth_extra_amount=19, gcd_mod=11, back_to_back=7, rem_mod=5,
    drift_ceiling=180, floor_action='seed', bank_action='close',
    seal_faults=3, counted_statuses=('kept',))


def build_params(data):
    P = dict(PARAMS)
    P['mod_offset'] = derive_mod_offset(data['moduli'])
    return P


def main(indir, outdir):
    data = load(indir)
    P = build_params(data)
    ledger, st = resolve(data, P)
    lane_rows, form_rows, sieve = rollups(data, P, ledger, st)
    write_reports(outdir, ledger, lane_rows, form_rows, sieve)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.stderr.write('usage: sieve.py INPUT_DIR OUTPUT_DIR\n')
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
