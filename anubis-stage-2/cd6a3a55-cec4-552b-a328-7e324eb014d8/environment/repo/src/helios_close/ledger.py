"""helios_close.ledger: part of the Q3 close program (see README.md)."""
from __future__ import annotations

from .rules import *  # noqa: F401,F403
def build_ledger(self):
    self.teams = {}
    for v, x, _ in self.records('engineer_roster.ini', 'teams').values():
        self.teams[v['team']] = {'model': v['model'], 'cap': Decimal(0), 'engs': set()}
    self.allocs = []
    for v, x, _ in self.records('engineer_roster.ini', 'alloc').values():
        end = v['end'] if isinstance(v['end'], int) else None
        self.allocs.append((v['engineer'], v['team'], v['fte'], v['oncall'], v['start'], end))
        t = self.teams.get(v['team'])
        if t is None:
            continue
        a = max(v['start'], Q_START_DAY)
        b = min(end if end is not None else CUT_DAY, CUT_DAY)
        if b > a:
            t['cap'] += v['fte'] * Decimal(8) * Decimal(weekdays_between(a, b)) * (Decimal(1) - v['oncall'])
        if v['start'] < CUT_DAY and (end is None or end > Q_START_DAY):
            t['engs'].add(v['engineer'])
    self.fx = {}
    for v, x, _ in self.records('fx_fixings.tsv', 'fixings').values():
        self.fx.setdefault(v['currency'], []).append((v['at'], v['rate']))
    for k in self.fx:
        self.fx[k].sort()
    self.rates = {}
    for t, _ in SCHEMA['engineer_rates.xlsx']:
        for v, x, _ in self.records('engineer_rates.xlsx', t).values():
            self.rates[v['engineer'], civil_from_days(v['month'])[1]] = (v['rate'], v['currency'])
    entries, openings = ([], [])
    for rid, (v, x, _) in self.records('remediation_timesheets.csv', 'timesheets').items():
        if v['worked'] >= CUT:
            continue
        team = self.team_on(v['engineer'], v['worked'])
        if team is None:
            continue
        entries.append({'kind': 'entry', 'entry': rid, 'team': team, 'source': 'remediation_timesheets.csv', 'booked': v['worked'], 'amount_cents': self.ts_cents(v)})
    jr = self.records('ledger_journal.db', 'entries')
    cancelled = set()
    for rid, (v, x, _) in jr.items():
        if v['kind'] == 'reversal' and v['booked'] < CUT:
            cancelled.add(rid)
    self.cancelled = cancelled
    for rid, (v, x, _) in jr.items():
        if rid in cancelled or v['booked'] >= CUT:
            continue
        cents = self.to_cents(v['amount'], v['currency'], v['booked'])
        if v['kind'] == 'opening':
            openings.append({'kind': 'opening', 'team': v['team'], 'entry': rid, 'amount_cents': cents})
        else:
            entries.append({'kind': 'entry', 'entry': rid, 'team': v['team'], 'source': 'ledger_journal.db', 'booked': v['booked'], 'amount_cents': cents})
    openings.sort(key=lambda r: (r['team'], r['entry']))
    entries.sort(key=lambda r: (r['booked'], r['entry']))
    clos = {}
    for r in openings + entries:
        clos[r['team']] = clos.get(r['team'], 0) + r['amount_cents']
    self.openings, self.entries = (openings, entries)
    self.closings = [{'kind': 'closing', 'team': t, 'amount_cents': clos.get(t, 0)} for t in sorted(self.teams)]

def fx_at(self, cur, t):
    if cur == 'EUR':
        return Decimal(1)
    best = None
    for at, rate in self.fx.get(cur, []):
        if at < t:
            best = rate
        else:
            break
    if best is None:
        best = self.fx[cur][0][1] if self.fx.get(cur) else Decimal(1)
    return best

def to_cents(self, minor, cur, t):
    major = Decimal(minor) / Decimal(10) ** CUR_EXP[cur]
    return int(qd(major * self.fx_at(cur, t) * 100, 0))

def rate_major(self, eng, t):
    y, m, d = civil_from_days(t // DAY)
    mo = m if (y, m) in ((2025, 7), (2025, 8), (2025, 9)) else 7
    minor, cur = self.rates.get((eng, mo), (0, 'EUR'))
    return (Decimal(minor) / Decimal(10) ** CUR_EXP[cur], cur)

def ts_cents(self, v):
    rate, cur = self.rate_major(v['engineer'], v['worked'])
    return -int(qd(v['hours'] * rate * self.fx_at(cur, v['worked']) * 100, 0))

def team_on(self, eng, t):
    z = t // DAY
    for e, team, fte, oncall, start, end in self.allocs:
        if e == eng and start <= z and (end is None or z <= end):
            return team
    return None

def deferred(self):
    out = []
    for fname in AMEND:
        t = SCHEMA[fname][0][0]
        recs = self.records(fname, t)
        for rid, revs in sorted(self.revs[fname][t].items()):
            applicable = [r for r in revs if r.st != 'draft' and r.rec_at < CUT]
            for r in revs:
                if r.rec_at < CUT or r.st == 'draft':
                    continue
                v = r.v
                action = 'new' if not applicable else 'void' if r.st == 'void' else 'revise'
                target = measure = cur = amd = None
                if fname == 'advisory_rescores.parquet':
                    target = self.vid(v['vuln'])
                    if v['approved'] is True and r.st != 'void':
                        measure = 'cvss'
                        if target not in self.vec_cache:
                            self.vec_cache[target] = self.vuln_vector(target)
                        cv = self.vec_cache[target]
                        cur = cvss_base(cv) if cv else None
                        amd = cvss_base(v['vector'])
                    else:
                        measure = 'none'
                elif fname == 'remediation_timesheets.csv':
                    measure = 'cents'
                    target = self.team_on(v['engineer'], v['worked'])
                    cur = self.ts_cents(recs[rid][0]) if rid in recs else None
                    amd = None if r.st == 'void' else self.ts_cents(v)
                elif fname == 'ledger_journal.db':
                    measure = 'cents'
                    target = v['team']
                    if rid in recs and rid not in self.cancelled:
                        iv = recs[rid][0]
                        cur = self.to_cents(iv['amount'], iv['currency'], iv['booked'])
                    amd = None if r.st == 'void' else self.to_cents(v['amount'], v['currency'], v['booked'])
                else:
                    target = v['service']
                    measure = 'none'
                if measure == 'cvss':
                    cur = qd(cur, 1) if cur is not None else None
                    amd = qd(amd, 1)
                out.append({'kind': 'deferred', 'amendment': f'{fname}#{rid}#{r.rev}', 'file': fname, 'rid': rid, 'rev': r.rev, 'recorded': iso(r.rec_at), 'action': action, 'target': target, 'measure': measure, 'current': cur, 'amended': amd})
    out.sort(key=lambda d: (d['recorded'], d['amendment']))
    return out

def p1_rows(self):
    pk = []
    owners = {}
    for v, x, _ in self.records('package_owners.json', 'owners').values():
        if v['role'] != 'reviewer' and v['effective'] < CUT:
            k = self.pkey(v['eco'], v['name'])
            if k not in owners or (v['effective'], x.rid) > owners[k][0]:
                owners[k] = ((v['effective'], x.rid), v['team'])
    for key in sorted(self.rel):
        rels = {vs: r for vs, r in self.rel[key].items() if r['pub'] < CUT}
        if not rels:
            continue
        yk = [vs for vs in rels if self.yanked_at(key, vs, CUT)]
        stable = [r['ver'] for vs, r in rels.items() if r['ver'].pre is None]
        latest = max(stable) if stable else None
        lic = obl = None
        if latest is not None:
            lic, obl = self.license_of(key, latest)
        pk.append({'package': key, 'ecosystem': key.split(':', 1)[0], 'owner_team': owners[key][1] if key in owners else None, 'releases': len(rels), 'yanked': len(yk), 'latest': str(latest) if latest else None, 'latest_license': lic, 'obligation': obl})
    pins = [{'service': p['service'], 'package': p['package'], 'scope': p['scope'], 'constraint': p['constraint'], 'source': p['source'], 'pinned': str(p['pinned']) if p['pinned'] is not None else None, 'disposition': p['disposition'], 'license': p['license'], 'obligation': p['obligation']} for p in self.pins]
    sv = [{'service': k, 'team': s['team'], 'tier': s['tier'], 'region': s['region'], 'status': s['status'], 'deploys': s['deploys'], 'weight': s['weight']} for k, s in sorted(self.svc.items())]
    tm = []
    for k in sorted(self.teams):
        t = self.teams[k]
        cap = None if t['model'] == 'uncapped' else int(qd(t['cap'], 0))
        tm.append({'team': k, 'model': t['model'], 'capacity_hours': cap, 'engineers': len(t['engs'])})
    led = list(self.openings)
    led += [dict(e, booked=iso(e['booked'])) for e in self.entries]
    led += self.closings
    ctl = []
    for rid, (v, x, _) in self.records('control_totals.html', 'controls').items():
        ctl.append({'kind': 'control', 'control': v['control'], 'scope': v['scope'], 'measure': v['measure'], 'value': v['value']})
    led += sorted(ctl, key=lambda r: r['control'])
    led += self.custody()
    led += self.deferred()
    return {'packages.jsonl': pk, 'pins.jsonl': pins, 'exposures.jsonl': self.exposures, 'services.jsonl': sv, 'teams.csv': tm, 'ledger.jsonl': led}
Close.build_ledger = build_ledger
Close.fx_at = fx_at
Close.to_cents = to_cents
Close.rate_major = rate_major
Close.ts_cents = ts_cents
Close.team_on = team_on
Close.deferred = deferred
Close.p1_rows = p1_rows
