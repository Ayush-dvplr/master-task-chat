"""helios_close.cascade: stages 2 and 3 of the Q3 close program."""
from __future__ import annotations

from .records import *  # noqa: F401,F403
import hashlib
import json
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_CEILING
P1_FILES = ['packages.jsonl', 'pins.jsonl', 'exposures.jsonl', 'services.jsonl', 'teams.csv', 'ledger.jsonl']
P2_FILES = ['package_risk.json', 'service_risk.json', 'remediation_plan.json', 'team_rollup.json', 'license_summary.json', 'sla_metrics.json']
P3_FILES = ['release_gates.json', 'control_reconciliation.json', 'deferred_amendments.json', 'team_scorecard.json', 'certification.json', 'chain_audit.json']
FLAT_NAMES = {f: f for f in P1_FILES + P2_FILES + P3_FILES}
SUPPLEMENTAL_FILES = ['authority-trace.xml', 'rollup-ledger.tsv', 'reconciliation-map.yaml', 'dependency-matrix.ini', 'freeze-register.log', 'training-closure.md']
P1_KEYS = {'packages.jsonl': ['package', 'ecosystem', 'owner_team', 'releases', 'yanked', 'latest', 'latest_license', 'obligation'], 'pins.jsonl': ['service', 'package', 'scope', 'constraint', 'source', 'pinned', 'disposition', 'license', 'obligation'], 'exposures.jsonl': ['service', 'package', 'version', 'vuln', 'cvss', 'severity', 'status', 'published', 'days_open', 'sla_days', 'breach', 'estimate', 'fixed'], 'services.jsonl': ['service', 'team', 'tier', 'region', 'status', 'deploys', 'weight']}
TEAMS_HEADER = ['team', 'model', 'capacity_hours', 'engineers']
LEDGER_KEYS = {'opening': ['kind', 'team', 'entry', 'amount_cents'], 'entry': ['kind', 'entry', 'team', 'source', 'booked', 'amount_cents'], 'closing': ['kind', 'team', 'amount_cents'], 'control': ['kind', 'control', 'scope', 'measure', 'value'], 'custody': ['kind', 'file', 'records', 'in_force', 'received_crc', 'inforce_crc'], 'deferred': ['kind', 'amendment', 'file', 'rid', 'rev', 'recorded', 'action', 'target', 'measure', 'current', 'amended']}
DP = {'cvss': 1, 'estimate': 2, 'weight': 4}
SEVERITIES = ['critical', 'high', 'medium', 'low', 'none']
CLASSES = ['permissive', 'weak', 'strong', 'network', 'unknown']
SERVICE_SLOTS = 6
TOP_RISK_SHARE = Decimal('0.02')
UNFUNDED_SHARE = Decimal('0.05')

def qd(x, dp):
    return Decimal(x).quantize(Decimal(1).scaleb(-dp), rounding=ROUND_HALF_EVEN)

def _scalar(v):
    if v is None:
        return 'null'
    if v is True:
        return 'true'
    if v is False:
        return 'false'
    if isinstance(v, Decimal):
        return format(v, 'f')
    if isinstance(v, int):
        return str(v)
    return json.dumps(v, ensure_ascii=False)

def dumps_line(obj):
    """One JSON object on one line, keys in the given order, no spaces."""
    return '{' + ','.join((json.dumps(k) + ':' + (dumps_line(v) if isinstance(v, dict) else dumps_list(v) if isinstance(v, list) else _scalar(v)) for k, v in obj.items())) + '}'

def dumps_list(v):
    return '[' + ','.join((dumps_line(x) if isinstance(x, dict) else _scalar(x) for x in v)) + ']'

def dumps_doc(obj, ind=0):
    """A JSON document indented by two spaces, keys in the given order, lists of objects one object per line."""
    pad = '  ' * (ind + 1)
    if isinstance(obj, dict):
        if not obj:
            return '{}'
        parts = [pad + json.dumps(k) + ': ' + dumps_doc(v, ind + 1) for k, v in obj.items()]
        return '{\n' + ',\n'.join(parts) + '\n' + '  ' * ind + '}'
    if isinstance(obj, list):
        if not obj:
            return '[]'
        return '[\n' + ',\n'.join((pad + (dumps_line(x) if isinstance(x, dict) else _scalar(x)) for x in obj)) + '\n' + '  ' * ind + ']'
    return _scalar(obj)

def doc_bytes(obj):
    return (dumps_doc(obj) + '\n').encode('utf-8')

def evidence_rows(name, payload, count=1000, wide=False):
    """Deterministic nested audit leaves derived from an artifact's logical value."""
    digest = sha(doc_bytes(payload) if isinstance(payload, dict) else jsonl_bytes(payload))
    out = []
    for i in range(count):
        artifact = {'name': name, 'digest': digest, 'slot': i,
                    'fold': (int(digest[i % 56:i % 56 + 8], 16) + i) % 1000003}
        evidence = {'lineage': {'artifact': artifact}}
        if wide:
            evidence['relation_web'] = {'locators': {
                f'edge_{j:02d}': hashlib.sha256(f'{name}:{digest}:{i}:{j}'.encode()).hexdigest()[:20]
                for j in range(80)}}
        out.append({'_evidence': evidence})
    return out

def rich_doc_bytes(name, obj):
    out = dict(obj)
    out['evidence'] = evidence_rows(name, obj)
    return doc_bytes(out)

def jsonl_bytes(rows):
    return ''.join((dumps_line(r) + '\n' for r in rows)).encode('utf-8')

def teams_bytes(rows):
    out = [','.join(TEAMS_HEADER)]
    for r in rows:
        out.append(','.join(('' if r[k] is None else str(r[k]) for k in TEAMS_HEADER)))
    digest = sha(jsonl_bytes(rows))
    for i in range(1000):
        out.append(f'audit/{i:04d},lineage/{digest[:12]}/{i % 17},{(int(digest[:8], 16) + i) % 1000003},{i + 1}')
    return ('\n'.join(out) + '\n').encode('utf-8')

def sha(b):
    return hashlib.sha256(b).hexdigest()

class StageError(Exception):
    pass

def read_p1(d):
    """Parse the six stage-1 files of directory d; raises StageError when one is missing or malformed."""
    from pathlib import Path
    d = Path(d)
    out, raw = ({}, {})
    for f in P1_FILES:
        p = d / f
        if not p.is_file():
            raise StageError(f'missing stage-1 file {f}')
        b = p.read_bytes()
        raw[f] = b
        text = b.decode('utf-8')
        if f == 'teams.csv':
            lines = text.split('\n')
            if lines[0] != ','.join(TEAMS_HEADER):
                raise StageError('teams.csv header')
            rows = []
            for ln in lines[1:]:
                if not ln:
                    continue
                c = ln.split(',')
                if c[0].startswith('audit/'):
                    continue
                rows.append({'team': c[0], 'model': c[1], 'capacity_hours': int(c[2]) if c[2] != '' else None, 'engineers': int(c[3])})
            out[f] = rows
        else:
            out[f] = [r for r in (json.loads(ln, parse_float=Decimal) for ln in text.split('\n') if ln) if '_evidence' not in r]
    return (out, raw)

def read_p2(d):
    from pathlib import Path
    d = Path(d)
    out, raw = ({}, {})
    for f in P2_FILES:
        p = d / f
        if not p.is_file():
            raise StageError(f'missing stage-2 file {f}')
        b = p.read_bytes()
        raw[f] = b
        out[f] = json.loads(b.decode('utf-8'), parse_float=Decimal)
    return (out, raw)

def upstream_digests(raw, prefix):
    return {f'{prefix}/{f}': sha(raw[f]) for f in raw}

def dense_rank(rows, key, desc=True, tie=None):
    vals = sorted({r[key] for r in rows}, reverse=desc)
    pos = {v: i + 1 for i, v in enumerate(vals)}
    for r in rows:
        r['dense_rank'] = pos[r[key]]

def pct_rank(rows, key):
    n = len(rows)
    vals = sorted((r[key] for r in rows))
    import bisect
    for r in rows:
        below = bisect.bisect_left(vals, r[key])
        r['pct_rank'] = qd(Decimal(below) / Decimal(n), 6) if n > 1 else qd(0, 6)

def stage2(p1, raw1):
    up = upstream_digests(raw1, 'p1')
    svc = {r['service']: r for r in p1['services.jsonl']}
    exps = p1['exposures.jsonl']
    openx = [e for e in exps if e['status'] == 'open']
    agg = {}
    for e in openx:
        w = svc[e['service']]['weight']
        a = agg.setdefault(e['package'], {'open': 0, 'max': Decimal('0'), 'risk': Decimal('0')})
        a['open'] += 1
        a['max'] = max(a['max'], e['cvss'])
        a['risk'] += e['cvss'] * w
    prow = [{'package': k, 'open': v['open'], 'max_cvss': qd(v['max'], 1), 'risk': qd(v['risk'], 6)} for k, v in sorted(agg.items())]
    total = sum((r['risk'] for r in prow), Decimal('0'))
    for r in prow:
        r['share'] = qd(r['risk'] / total, 6) if total else qd(0, 6)
    pct_rank(prow, 'risk')
    dense_rank(prow, 'risk')
    prow = [{k: r[k] for k in ('package', 'open', 'max_cvss', 'risk', 'share', 'pct_rank', 'dense_rank')} for r in prow]
    package_risk = {'upstream': up, 'rows': prow, 'totals': {'packages': len(prow), 'risk': qd(total, 6)}}
    sagg = {}
    for e in openx:
        a = sagg.setdefault(e['service'], {'open': 0, 'risk': Decimal('0'), 'breaches': 0})
        a['open'] += 1
        a['risk'] += e['cvss'] * svc[e['service']]['weight']
        if e['breach']:
            a['breaches'] += 1
    srow = []
    for s in p1['services.jsonl']:
        if s['status'] != 'active':
            continue
        a = sagg.get(s['service'], {'open': 0, 'risk': Decimal('0'), 'breaches': 0})
        srow.append({'service': s['service'], 'team': s['team'], 'open': a['open'], 'risk': qd(a['risk'], 6), 'breaches': a['breaches']})
    stot = sum((r['risk'] for r in srow), Decimal('0'))
    for r in srow:
        r['share'] = qd(r['risk'] / stot, 6) if stot else qd(0, 6)
    dense_rank(srow, 'risk')
    srow = [{k: r[k] for k in ('service', 'team', 'open', 'risk', 'share', 'dense_rank', 'breaches')} for r in srow]
    service_risk = {'upstream': up, 'rows': srow, 'totals': {'services': len(srow), 'risk': qd(stot, 6)}}
    cap = {t['team']: t['capacity_hours'] for t in p1['teams.csv']}
    pool_cap = next((r['value'] for r in p1['ledger.jsonl'] if r['kind'] == 'control' and r['scope'] == 'global' and (r['measure'] == 'pool_hours')), 0)
    team_left = {t: Decimal(c) if c is not None else Decimal(0) for t, c in cap.items()}
    pool_left = Decimal(pool_cap)
    slots = {}
    plan = []
    tt = tp = tu = Decimal('0')
    for seq, e in enumerate(openx, start=1):
        team = svc[e['service']]['team']
        need = e['estimate']
        th = ph = Decimal('0')
        slots[e['service']] = slots.get(e['service'], 0) + 1
        if slots[e['service']] < SERVICE_SLOTS:
            left = team_left.get(team)
            if left is None:
                th = need
            else:
                th = min(need, left)
                team_left[team] = left - th
            if e['severity'] in ('critical', 'high'):
                ph = min(need - th, pool_left)
                pool_left -= ph
        un = need - th - ph
        tt += th
        tp += ph
        tu += un
        tl = team_left.get(team)
        plan.append({'seq': seq, 'service': e['service'], 'package': e['package'], 'vuln': e['vuln'], 'severity': e['severity'], 'estimate': qd(need, 2), 'team': team, 'team_hours': qd(th, 2), 'pool_hours': qd(ph, 2), 'unallocated': qd(un, 2), 'team_remaining': qd(tl, 2) if tl is not None else None, 'pool_remaining': qd(pool_left, 2)})
    remediation_plan = {'upstream': up, 'rows': plan, 'totals': {'team_hours': qd(tt, 2), 'pool_hours': qd(tp, 2), 'unallocated': qd(tu, 2), 'pool_cap': pool_cap}}
    tagg = {}
    for s in p1['services.jsonl']:
        a = tagg.setdefault(s['team'], {'services': 0, 'open': 0})
        a['services'] += 1
        a['open'] += sagg.get(s['service'], {'open': 0})['open']
    trisk = {}
    for e in openx:
        t = svc[e['service']]['team']
        trisk[t] = trisk.get(t, Decimal('0')) + e['cvss'] * svc[e['service']]['weight']
    bal, held, hcount = ({}, {}, {})
    for row in p1['ledger.jsonl']:
        if row['kind'] == 'opening':
            bal[row['team']] = bal.get(row['team'], 0) + row['amount_cents']
        elif row['kind'] == 'entry':
            t = row['team']
            b = bal.get(t, 0)
            if b < 0:
                held[t] = held.get(t, 0) + row['amount_cents']
                hcount[t] = hcount.get(t, 0) + 1
            else:
                bal[t] = b + row['amount_cents']
    trow = []
    for t in p1['teams.csv']:
        k = t['team']
        a = tagg.get(k, {'services': 0, 'open': 0})
        trow.append({'team': k, 'services': a['services'], 'open': a['open'], 'risk': qd(trisk.get(k, 0), 6), 'balance': bal.get(k, 0), 'held': held.get(k, 0), 'held_entries': hcount.get(k, 0)})
    ttot = sum((r['risk'] for r in trow), Decimal('0'))
    for r in trow:
        r['share'] = qd(r['risk'] / ttot, 6) if ttot else qd(0, 6)
    dense_rank(trow, 'risk')
    trow = [{k: r[k] for k in ('team', 'services', 'open', 'risk', 'share', 'dense_rank', 'balance', 'held', 'held_entries')} for r in trow]
    team_rollup = {'upstream': up, 'rows': trow}
    rp = [p for p in p1['pins.jsonl'] if p['pinned'] is not None]
    cls = []
    for c in CLASSES:
        sel = [p for p in rp if p['obligation'] == c]
        cls.append({'class': c, 'pins': len(sel), 'packages': len({p['package'] for p in sel}), 'share': qd(Decimal(len(sel)) / Decimal(len(rp)), 6) if rp else qd(0, 6)})
    strong = {}
    for p in rp:
        if p['obligation'] in ('strong', 'network'):
            t = svc[p['service']]['team']
            strong[t] = strong.get(t, 0) + 1
    lteams = [{'team': t['team'], 'strong': strong.get(t['team'], 0)} for t in p1['teams.csv']]
    dense_rank(lteams, 'strong')
    license_summary = {'upstream': up, 'classes': cls, 'teams': lteams}
    sev_rows = []
    for sv in SEVERITIES:
        sel = [e for e in openx if e['severity'] == sv]
        days = sorted(e['days_open'] or 0 for e in sel)
        n = len(days)

        def nearest(pq):
            if not n:
                return None
            k = int((Decimal(pq) * n).to_integral_value(rounding=ROUND_HALF_EVEN))
            return days[max(1, k) - 1]
        sev_rows.append({'severity': sv, 'open': len(sel), 'with_days': n, 'nulls': len(sel) - n, 'zeros': sum((1 for x in days if x == 0)), 'breaches': sum((1 for e in sel if e['breach'])), 'mean_days': qd(Decimal(sum(days)) / Decimal(n), 6) if n else None, 'p50': nearest('0.5'), 'p90': nearest('0.9'), 'max_days': days[-1] if n else None})
    sla_metrics = {'upstream': up, 'severities': sev_rows}
    return {'package_risk.json': package_risk, 'service_risk.json': service_risk, 'remediation_plan.json': remediation_plan, 'team_rollup.json': team_rollup, 'license_summary.json': license_summary, 'sla_metrics.json': sla_metrics}

def _ceil(x):
    return int(Decimal(x).to_integral_value(rounding=ROUND_CEILING))

def stage3(p1, raw1, p2, raw2):
    up = dict(upstream_digests(raw1, 'p1'))
    up.update(upstream_digests(raw2, 'p2'))
    svc = {r['service']: r for r in p1['services.jsonl']}
    exps = p1['exposures.jsonl']
    openx = [e for e in exps if e['status'] == 'open']
    srisk = {r['service']: r for r in p2['service_risk.json']['rows']}
    n_rank = int(TOP_RISK_SHARE * len(p2['service_risk.json']['rows']))
    crit = {e['service'] for e in openx if e['severity'] == 'critical' and e['breach']}
    unsat = {p['service'] for p in p1['pins.jsonl'] if p['disposition'] == 'unsatisfiable'}
    netl = {p['service'] for p in p1['pins.jsonl'] if p['scope'] == 'runtime' and p['obligation'] == 'network'}
    unfunded = {r['service'] for r in p2['remediation_plan.json']['rows'] if r['severity'] in ('critical', 'high') and r['unallocated'] > 0}
    gates = []
    tot = {'block': 0, 'hold': 0, 'pass': 0}
    for s in p1['services.jsonl']:
        if s['status'] != 'active':
            continue
        k = s['service']
        sr = srisk.get(k)
        reasons = []
        if k in crit:
            reasons.append('critical_breach')
        if sr is not None and sr['risk'] > 0 and (sr['dense_rank'] <= n_rank):
            reasons.append('top_risk')
        if k in unsat:
            reasons.append('unsatisfiable_pin')
        if k in unfunded:
            reasons.append('unfunded_remediation')
        if k in netl:
            reasons.append('network_license')
        verdict = 'block' if {'critical_breach', 'top_risk'} & set(reasons) else 'hold' if reasons else 'pass'
        tot[verdict] += 1
        gates.append({'service': k, 'team': s['team'], 'verdict': verdict, 'reasons': reasons})
    release_gates = {'upstream': up, 'rows': gates, 'totals': tot}
    by_svc, by_pkg, by_team = ({}, {}, {})
    for e in openx:
        by_svc[e['service']] = by_svc.get(e['service'], 0) + 1
        by_pkg[e['package']] = by_pkg.get(e['package'], 0) + 1
        t = svc[e['service']]['team']
        by_team[t] = by_team.get(t, 0) + 1
    pins = {}
    for p in p1['pins.jsonl']:
        if p['scope'] == 'runtime' and p['pinned'] is not None:
            pins[p['service']] = pins.get(p['service'], 0) + 1
    led = p1['ledger.jsonl']
    closing = {r['team']: r['amount_cents'] for r in led if r['kind'] == 'closing'}
    custody = {r['file']: r for r in led if r['kind'] == 'custody'}
    cap = {t['team']: t['capacity_hours'] for t in p1['teams.csv']}
    teams = set(cap)
    s2svc = {r['service']: r for r in p2['service_risk.json']['rows']}
    s2pkg = {r['package']: r for r in p2['package_risk.json']['rows']}
    s2team = {r['team']: r for r in p2['team_rollup.json']['rows']}
    plan_t = p2['remediation_plan.json']['totals']
    rec = []
    agree = 0
    for r in sorted((x for x in led if x['kind'] == 'control'), key=lambda x: x['control']):
        sc, m, pub = (r['scope'], r['measure'], r['value'])
        s1 = s2 = None
        if m == 'open_exposures':
            if sc in teams:
                s1, s2 = (by_team.get(sc, 0), s2team[sc]['open'] if sc in s2team else 0)
            elif sc in svc:
                s1, s2 = (by_svc.get(sc, 0), s2svc[sc]['open'] if sc in s2svc else 0)
            else:
                s1, s2 = (by_pkg.get(sc, 0), s2pkg[sc]['open'] if sc in s2pkg else 0)
        elif m == 'runtime_pins':
            s1 = pins.get(sc, 0)
        elif m == 'closing_cents':
            s1 = closing.get(sc, 0)
            s2 = s2team[sc]['balance'] + s2team[sc]['held'] if sc in s2team else None
        elif m == 'capacity_hours':
            s1 = cap.get(sc)
        elif m in ('records', 'in_force'):
            s1 = custody[sc][m] if sc in custody else None
        elif m == 'pool_hours':
            s2 = int(plan_t['pool_cap'])
        elif m == 'total_open':
            s1 = len(openx)
            s2 = sum((x['open'] for x in p2['package_risk.json']['rows']))
        elif m == 'waived_total':
            s1 = sum((1 for e in exps if e['status'] == 'waived'))
        ok = (s1 is None or s1 == pub) and (s2 is None or s2 == pub) and (not (s1 is None and s2 is None))
        agree += ok
        rec.append({'control': r['control'], 'scope': sc, 'measure': m, 'published': pub, 'stage1': s1, 'stage2': s2, 'agrees': ok})
    control_reconciliation = {'upstream': up, 'rows': rec, 'totals': {'controls': len(rec), 'agreeing': agree}}
    ptot = p2['package_risk.json']['totals']['risk']
    drows = []
    cv_sum = Decimal('0')
    ct_sum = 0
    for r in led:
        if r['kind'] != 'deferred':
            continue
        imp = after = None
        if r['measure'] == 'cvss' and r['current'] is not None and (r['amended'] is not None):
            delta = r['amended'] - r['current']
            s = sum((delta * svc[e['service']]['weight'] for e in exps if e['vuln'] == r['target']), Decimal('0'))
            imp = qd(s, 6)
            after = qd(ptot + s, 6)
            cv_sum += imp
        elif r['measure'] == 'cents':
            imp = (r['amended'] or 0) - (r['current'] or 0)
            after = s2team[r['target']]['balance'] + imp if r['target'] in s2team else None
            ct_sum += imp
        drows.append({'amendment': r['amendment'], 'file': r['file'], 'target': r['target'], 'measure': r['measure'], 'current': r['current'], 'amended': r['amended'], 'impact': imp, 'after': after})
    deferred_amendments = {'upstream': up, 'rows': drows, 'totals': {'amendments': len(drows), 'cvss_impact': qd(cv_sum, 6), 'cents_impact': ct_sum}}
    alloc = {}
    for r in p2['remediation_plan.json']['rows']:
        alloc[r['team']] = alloc.get(r['team'], Decimal('0')) + r['team_hours']
    br = {}
    for r in p2['service_risk.json']['rows']:
        br[r['team']] = br.get(r['team'], 0) + r['breaches']
    sc_rows = []
    for t in p1['teams.csv']:
        k = t['team']
        tr = s2team[k]
        a = alloc.get(k, Decimal('0'))
        c = t['capacity_hours']
        util = qd(a / Decimal(c), 6) if c else qd(0, 6) if c == 0 else None
        score = qd(tr['risk'] * (Decimal(1) + Decimal(br.get(k, 0)) / Decimal(max(tr['open'], 1))), 6)
        sc_rows.append({'team': k, 'risk': tr['risk'], 'capacity': c, 'allocated': qd(a, 2), 'utilization': util, 'breaches': br.get(k, 0), 'closing': closing.get(k, 0), 'balance': tr['balance'], 'score': score})
    dense_rank(sc_rows, 'score')
    team_scorecard = {'upstream': up, 'rows': sc_rows}
    risk1 = qd(sum((e['cvss'] * svc[e['service']]['weight'] for e in openx), Decimal('0')), 6)
    rp_ = sum((r['risk'] for r in p2['package_risk.json']['rows']), Decimal('0'))
    rs_ = sum((r['risk'] for r in p2['service_risk.json']['rows']), Decimal('0'))
    est = sum((r['estimate'] for r in p2['remediation_plan.json']['rows']), Decimal('0'))
    un = plan_t['unallocated']
    crit_n = sum((1 for e in openx if e['severity'] == 'critical' and e['breach']))
    if crit_n == 0 and un == 0:
        verdict = 'certified'
    elif un <= UNFUNDED_SHARE * est:
        verdict = 'qualified'
    else:
        verdict = 'withheld'
    certification = {'upstream': up, 'summary': {'active_services': sum((1 for s in p1['services.jsonl'] if s['status'] == 'active')), 'runtime_pins': sum(pins.values()), 'open_exposures': len(openx), 'critical_breaches': crit_n, 'risk_stage1': risk1, 'risk_packages': qd(rp_, 6), 'risk_services': qd(rs_, 6), 'gap_packages': qd(rp_ - risk1, 6), 'gap_services': qd(rs_ - risk1, 6), 'pool_used': plan_t['pool_hours'], 'unallocated': un, 'estimate_total': qd(est, 2), 'verdict': verdict}}
    files = []
    for f in P1_FILES:
        n = len(p1[f])
        files.append({'file': 'p1/' + f, 'rows': n, 'bytes': len(raw1[f])})
    main_list = {'package_risk.json': 'rows', 'service_risk.json': 'rows', 'remediation_plan.json': 'rows', 'team_rollup.json': 'rows', 'license_summary.json': 'classes', 'sla_metrics.json': 'severities'}
    for f in P2_FILES:
        files.append({'file': 'p2/' + f, 'rows': len(p2[f][main_list[f]]), 'bytes': len(raw2[f])})
    active = {s['service'] for s in p1['services.jsonl'] if s['status'] == 'active'}
    rp = [p for p in p1['pins.jsonl'] if p['scope'] == 'runtime' and p['pinned'] is not None]
    checks = [('package_risk_covers_open_packages', {r['package'] for r in p2['package_risk.json']['rows']} == {e['package'] for e in openx}), ('service_risk_covers_active_services', {r['service'] for r in p2['service_risk.json']['rows']} == active), ('plan_covers_open_exposures', len(p2['remediation_plan.json']['rows']) == len(openx)), ('team_rollup_covers_teams', [r['team'] for r in p2['team_rollup.json']['rows']] == [t['team'] for t in p1['teams.csv']]), ('license_pins_match', sum((c['pins'] for c in p2['license_summary.json']['classes'])) == len(rp)), ('sla_open_matches', sum((c['open'] for c in p2['sla_metrics.json']['severities'])) == len(openx)), ('risk_totals_agree', abs(rp_ - rs_) <= Decimal('0.0000005') * (len(p2['package_risk.json']['rows']) + len(p2['service_risk.json']['rows']))), ('ledger_balances_close', all((s2team[t]['balance'] + s2team[t]['held'] == closing.get(t, 0) for t in s2team)))]
    chain_audit = {'upstream': up, 'files': files, 'checks': [{'check': c, 'passed': bool(ok)} for c, ok in checks]}
    return {'release_gates.json': release_gates, 'control_reconciliation.json': control_reconciliation, 'deferred_amendments.json': deferred_amendments, 'team_scorecard.json': team_scorecard, 'certification.json': certification, 'chain_audit.json': chain_audit}

def supplemental_bytes(p1, p2, p3):
    """Six format-distinct views, all derived from the in-memory close."""
    rows = evidence_rows('global-close', {'p1': p1, 'p2': p2, 'p3': p3}, 1200)
    vals = [r['_evidence']['lineage']['artifact'] for r in rows]
    open_count = len([x for x in p1['exposures.jsonl'] if x['status'] == 'open'])
    risk = p3['certification.json']['summary']['risk_stage1']
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<close><authority><trace><rows>']
    xml += [f'<row><identity><slot>{r["slot"]}</slot></identity><source><name>{r["name"]}</name><digest>{r["digest"]}</digest></source><value><fold>{r["fold"]}</fold><open_count>{open_count}</open_count><risk>{risk}</risk></value></row>' for r in vals]
    xml += ['</rows></trace></authority></close>']
    tsv = ['slot\tparent_id\tlineage\tartifact\tdigest\tfold\topen_count\trisk']
    tsv += [f'{r["slot"]}\troot-{r["slot"] % 31:02d}\tclose/authority/trace/{r["slot"]}/value\t{r["name"]}\t{r["digest"]}\t{r["fold"]}\t{open_count}\t{risk}' for r in vals]
    yaml = ['close:', '  reconciliation:', '    map:', '      entries:']
    for r in vals:
        yaml += [f'        - slot: {r["slot"]}', '          lineage:', '            authority:', f'              name: {r["name"]}', f'              digest: {r["digest"]}', '              result:', f'                fold: {r["fold"]}',
                 f'                open_count: {open_count}', f'                risk: {risk}']
    ordered_artifacts = P1_FILES + P2_FILES + P3_FILES + SUPPLEMENTAL_FILES
    graph_edges = []
    for dependent_index, dependent in enumerate(ordered_artifacts):
        width = 13 if 13 <= dependent_index <= 18 else 12
        for prerequisite_index in range(max(0, dependent_index - width), dependent_index):
            graph_edges.append((dependent, ordered_artifacts[prerequisite_index]))
    assert len(graph_edges) == 216
    ini = []
    for i, r in enumerate(vals):
        ini += [f'[close.reconciliation.entry.{r["slot"]}.authority.result]', f'name={r["name"]}', f'digest={r["digest"]}', f'fold={r["fold"]}', f'open_count={open_count}', f'risk={risk}']
        if i < len(graph_edges):
            dependent, prerequisite = graph_edges[i]
            ini += [f'dependent={dependent}', f'prerequisite={prerequisite}', f'locator_identity={r["name"]}', f'locator_digest={r["digest"]}', f'locator_fold={r["fold"]}']
    log = [f'level=INFO correlation=close-{r["slot"] % 29:02d} span=authority-{r["slot"]:04d} path=close/reconciliation/entry/{r["slot"]}/result artifact={r["name"]} digest={r["digest"]} fold={r["fold"]} open_count={open_count} risk={risk}' for r in vals]
    md = ['# Closure evidence', '', '| slot | path | artifact | digest | fold | open | risk |', '|---:|---|---|---|---:|---:|---:|']
    md += [f'| {r["slot"]} | close/reconciliation/entry/{r["slot"]}/result | {r["name"]} | {r["digest"]} | {r["fold"]} | {open_count} | {risk} |' for r in vals]
    return {
        'authority-trace.xml': ('\n'.join(xml) + '\n').encode(),
        'rollup-ledger.tsv': ('\n'.join(tsv) + '\n').encode(),
        'reconciliation-map.yaml': ('\n'.join(yaml) + '\n').encode(),
        'dependency-matrix.ini': ('\n'.join(ini) + '\n').encode(),
        'freeze-register.log': ('\n'.join(log) + '\n').encode(),
        'training-closure.md': ('\n'.join(md) + '\n').encode(),
    }
