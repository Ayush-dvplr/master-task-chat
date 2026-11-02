"""helios_close.rules: part of the Q3 close program (see README.md)."""
from __future__ import annotations

from .cascade import *  # noqa: F401,F403
HOLIDAY = {'us-central': ['2025-07-04', '2025-09-01'], 'eu-west': ['2025-08-04'], 'ap-south': ['2025-08-15', '2025-09-17'], 'ap-north': ['2025-07-21', '2025-08-11', '2025-09-15', '2025-09-23'], 'global': ['2025-07-14', '2025-08-25'], 'ap-southeast': []}

def parse_cmp(tok):
    for op in ('>=', '<=', '>', '<', '='):
        if tok.startswith(op):
            return (op, parse_ver(tok[len(op):].strip()))
    return ('', parse_ver(tok))

def cons_from_cmps(cmps):
    c = Cons(None, True, None, False)
    for op, v in cmps:
        if op in ('>=', '>'):
            c.lo, c.lo_inc = (v, op == '>=')
        elif op in ('<', '<='):
            c.hi, c.hi_inc = (v, op == '<=')
        elif op == '=':
            return Cons(v, True, v, True, True)
    return c

def _wild(body):
    parts = body.split('.')
    if len(parts) == 2 or parts[1] in ('x', '*'):
        M = int(parts[0])
        if len(parts) >= 2 and parts[1] not in ('x', '*'):
            m = int(parts[1])
            return Cons(Ver(M, m, 0), True, Ver(M, m + 1, 0), False)
        return Cons(Ver(M, 0, 0), True, Ver(M + 1, 0, 0), False)
    M, m = (int(parts[0]), int(parts[1]))
    return Cons(Ver(M, m, 0), True, Ver(M, m + 1, 0), False)

def parse_cons(eco, raw):
    s = raw.strip()
    if eco == 'maven':
        if s[0] in '[(':
            inner = s[1:-1]
            if ',' not in inner:
                v = parse_ver(inner)
                return Cons(v, True, v, True, True)
            a, b = inner.split(',', 1)
            return Cons(parse_ver(a) if a.strip() else None, s[0] == '[', parse_ver(b) if b.strip() else None, s[-1] == ']')
        v = parse_ver(s)
        return Cons(v, True, v, True, True)
    if eco == 'pypi':
        parts = [p.strip() for p in s.split(',')]
        if len(parts) == 1 and parts[0].startswith('=='):
            body = parts[0][2:]
            if body.endswith('.*'):
                return _wild(body[:-2] + '.x')
            v = parse_ver(body)
            return Cons(v, True, v, True, True)
        if len(parts) == 1 and parts[0].startswith('~='):
            body = parts[0][2:]
            v = parse_ver(body)
            if body.count('.') == 1:
                return Cons(Ver(v.major, v.minor, 0), True, Ver(v.major + 1, 0, 0), False)
            return tilde(v)
        return cons_from_cmps([parse_cmp(p) for p in parts])
    if eco == 'cargo':
        parts = [p.strip() for p in s.split(',')]
        if len(parts) == 1:
            p = parts[0]
            if p.startswith('^'):
                return caret(parse_ver(p[1:]))
            if p.startswith('~'):
                return tilde(parse_ver(p[1:]))
            if p.startswith('='):
                v = parse_ver(p[1:])
                return Cons(v, True, v, True, True)
            if p.endswith('.*'):
                return _wild(p[:-2] + '.x')
            if p[0].isdigit():
                return caret(parse_ver(p))
        return cons_from_cmps([parse_cmp(p) for p in parts])
    if s.startswith('^'):
        return caret(parse_ver(s[1:]))
    if s.startswith('~'):
        return tilde(parse_ver(s[1:]))
    if s.endswith('.x') or s.endswith('.*'):
        return _wild(s[:-2] + '.x')
    toks = s.split()
    if len(toks) == 1 and toks[0][0].isdigit():
        v = parse_ver(toks[0])
        return Cons(v, True, v, True, True)
    return cons_from_cmps([parse_cmp(t) for t in toks])

def stage1(self):
    self._rec_cache = {}
    self.load_register()
    self.decode_all()
    self.load_errata()
    self.build_identity()
    self.build_vulns()
    self.build_releases()
    self.build_services()
    self.build_pins()
    self.build_exposures()
    self.build_ledger()
    return self.p1_rows()

def build_releases(self):
    quar = set()
    for v, x, _ in self.records('registry_mirror.parquet', 'mirror').values():
        if v['quarantined'] == 'true':
            quar.add((self.pkey(v['eco'], v['name']), str(v['version'])))
    self.rel = {}
    for eco, f in REG.items():
        for rid, (v, x, revs) in self.records(f, 'releases').items():
            key = self.pkey(eco, v['name'])
            vs = str(v['version'])
            if (key, vs) in quar:
                continue
            hist = sorted(((r.rev, r.rec_at, r.v['yanked']) for r in revs if r.st != 'draft' and r.rec_at < CUT))
            self.rel.setdefault(key, {})[vs] = {'ver': v['version'], 'pub': v['published'], 'hist': hist}
    self.notes = {}
    for v, x, _ in self.records('yank_notices.mbox', 'notices').values():
        if v['action'] in ('yank', 'unyank') and v.get('version') is not None:
            k = (self.pkey(v['eco'], v['name']), str(v['version']))
            self.notes.setdefault(k, []).append((x.rec_at, v['action'] == 'yank'))
    self.lic_over = {}
    for v, x, _ in self.records('license_overrides.csv', 'overrides').values():
        if v['status'] == 'decided' and v['decided'] is not None and (v['decided'] < CUT):
            key = self.pkey(v['eco'], v['name'])
            self.lic_over.setdefault(key, []).append((v['decided'], parse_cons(v['eco'], v['range']), v['expression']))
    self.scans = {}
    for v, x, _ in self.records('license_scan.parquet', 'scans').values():
        if v['scanned'] is not None and v['scanned'] < CUT:
            k = (self.pkey(v['eco'], v['name']), str(v['version']))
            if k not in self.scans or v['scanned'] > self.scans[k][0]:
                self.scans[k] = (v['scanned'], v['expression'])
    self.lic_exc = {}
    for v, x, _ in self.records('license_policy.md', 'exceptions').values():
        rv = v['revoked']
        if v['granted'] is not None and v['granted'] <= CUT_DATE and (not isinstance(rv, int) or rv >= CUT_DATE):
            key = self.pkey(v['eco'], v['name'])
            self.lic_exc.setdefault(key, []).append((v['granted'], parse_cons(v['eco'], v['range']), v['class']))

def yanked_at(self, key, vs, t):
    r = self.rel[key][vs]
    best = None
    for rev, at, y in r['hist']:
        if at < t and (best is None or rev > best[0]):
            best = (rev, at, y)
    note = None
    for at, y in sorted(self.notes.get((key, vs), [])):
        if at < t:
            note = (at, y)
    if note is not None and (best is None or note[0] >= best[1]):
        return note[1]
    return bool(best[2]) if best else False

def license_of(self, key, ver):
    best = None
    for dt, cons, expr in self.lic_over.get(key, []):
        if cons.admits_any(ver) and (best is None or dt > best[0]):
            best = (dt, expr)
    if best:
        expr = best[1]
    else:
        sc = self.scans.get((key, str(ver)))
        expr = sc[1] if sc else 'NOASSERTION'
    cls = spdx_class(parse_spdx(expr))
    exc = None
    for g, cons, c in self.lic_exc.get(key, []):
        if cons.admits_any(ver) and (exc is None or g > exc[0]):
            exc = (g, c)
    return (expr, exc[1] if exc else cls)

def build_services(self):
    self.svc = {}
    for v, x, _ in self.records('service_catalog.xlsx', 'services').values():
        self.svc[v['service']] = {'tier': v['tier'], 'region': v['region'], 'home': v['manifest'], 'team': None, 'status': 'active', 'archived': False}
    own = {}
    for v, x, _ in self.records('service_catalog.xlsx', 'ownership').values():
        if v['effective'] < CUT:
            k = v['service']
            if k not in own or (v['effective'], x.rid) > own[k][0]:
                own[k] = ((v['effective'], x.rid), v['team'])
    for k, (_, t) in own.items():
        if k in self.svc:
            self.svc[k]['team'] = t
    has_life = {x.v['service'] for revs in self.revs['service_catalog.xlsx'].get('lifecycle', {}).values() for x in revs}
    events = []
    for v, x, _ in self.records('service_catalog.xlsx', 'lifecycle').values():
        events.append(v)
    for v, x, _ in self.records('service_catalog_final.xlsx', 'legacy_lifecycle').values():
        if v['service'] in has_life:
            events.append(v)
    for v in sorted(events, key=lambda e: (e['at'], e['rid'])):
        s = self.svc.get(v['service'])
        if s is None or v['at'] >= CUT:
            continue
        if v['event'] == 'decommissioned':
            s['status'] = 'decommissioned'
        elif v['event'] == 'restored':
            s['status'] = 'active'
        elif v['event'] == 'archived':
            s['archived'] = True
    offs = {}
    for v, x, _ in self.records('clock_offsets.txt', 'offsets').values():
        offs[v['host'], v['day']] = v['offset']
    seen = {}
    for f in AUTH_LOGS + ['deploy_events_legacy.log']:
        for rid, (v, x, _) in self.records(f, 'deploys').items():
            t = v['at'] + offs.get((v['host'], v['at'] // DAY), 0)
            s = self.svc.get(v['service'])
            if f == 'deploy_events_legacy.log' and not (s and s['region'] == 'us-central'):
                continue
            if (f, rid) not in seen:
                seen[f, rid] = (v['service'], v['outcome'], t)
    cnt = {}
    for rid, (svc, outcome, t) in seen.items():
        if outcome == 'succeeded' and Q_START <= t < CUT:
            cnt[svc] = cnt.get(svc, 0) + 1
    for k, s in self.svc.items():
        s['deploys'] = cnt.get(k, 0) if s['region'] != 'global' else None
        factor = min(Decimal(2), Decimal(1) + Decimal(s['deploys']) / Decimal(365)) if s['deploys'] is not None else Decimal(1)
        s['weight'] = qd(TIER_WEIGHT[s['tier']] * factor, 4)

def build_pins(self):
    ovr = {}
    for v, x, _ in self.records('lock_overrides.toml', 'overrides').values():
        if x.rid in self.approved and v['valid_from'] <= CUT_DATE <= v['valid_to']:
            key = self.pkey(v['eco'], v['name'])
            r = self.rel.get(key, {}).get(str(v['version']))
            if r is not None and r['pub'] < CUT:
                ovr[v['service'], key] = v['version']
    decl = {}
    for f in list(HOME_FILE.values()) + ['manifests_snapshot.csv']:
        for v, x, _ in self.records(f, 'declarations').values():
            decl.setdefault((f, v['service']), []).append(v)
    scans = {}
    for v, x, _ in self.records('scanner_findings.jsonl', 'findings').values():
        if v['seen'] < CUT:
            k = (v['service'], self.pkey(v['eco'], v['name']))
            if k not in scans or v['seen'] > scans[k][0]:
                scans[k] = (v['seen'], v['version'])
    self.pins = []
    for k in sorted(self.svc):
        s = self.svc[k]
        if s['status'] != 'active':
            continue
        if s['home'] == 'image':
            for (svc, key), (_, ver) in sorted(scans.items()):
                if svc == k:
                    self.pins.append({'service': k, 'package': key, 'scope': 'runtime', 'constraint': None, 'source': 'scanner_findings.jsonl', 'pinned': ver, 'disposition': 'observed'})
            continue
        src = HOME_FILE[s['home']]
        for v in decl.get((src, k), []):
            key = self.pkey(v['eco'], v['name'])
            cons = parse_cons(v['eco'], v['constraint'])
            if (k, key) in ovr:
                pinned, disp = (ovr[k, key], 'overridden')
            else:
                best = None
                for vs, r in self.rel.get(key, {}).items():
                    if r['pub'] >= v['locked'] or not cons.admits(r['ver']):
                        continue
                    if self.yanked_at(key, vs, v['locked']):
                        continue
                    if best is None or best < r['ver']:
                        best = r['ver']
                pinned = best
                disp = 'pinned' if best is not None else 'unsatisfiable'
            self.pins.append({'service': k, 'package': key, 'scope': v['scope'], 'constraint': cons.canon(), 'source': src, 'pinned': pinned, 'disposition': disp})
    self.pins.sort(key=lambda r: (r['service'], r['package'], r['scope']))
    for p in self.pins:
        if p['pinned'] is not None and p['scope'] == 'runtime':
            p['license'], p['obligation'] = self.license_of(p['package'], p['pinned'])
        else:
            p['license'], p['obligation'] = (None, None)

def vuln_vector(self, c):
    best = None
    for v, x, _ in self.records('advisory_rescores.parquet', 'rescores').values():
        if self.vid(v['vuln']) == c and v['approved'] is True and (v['scored'] < CUT):
            if best is None or v['scored'] > best[0]:
                best = (v['scored'], v['vector'])
    if best:
        return best[1]
    order = ['nvd', 'ghsa']
    for src in order:
        if src == 'nvd':
            cands = self.nvd.get(c, [])
            if cands:
                return max(cands, key=lambda r: (r[1], r[3]))[2]
        if src == 'ghsa':
            for rid, vec, gid, key in sorted(self.ghsa_vec.get(c, [])):
                if isinstance(vec, Sentinel):
                    vec = self.cache_vec.get((gid, key), vec if not isinstance(vec, Sentinel) else None)
                if vec:
                    return vec
    return None

def build_exposures(self):
    self.authority = {}
    for v, x, _ in self.records('precedence.yaml', 'authority').values():
        self.authority[self.vid(v['vuln']), v['field']] = v['order'].split('>')
    self.nvd = {}
    for v, x, _ in self.records('advisories_nvd.xml', 'nvd').values():
        self.nvd.setdefault(self.vid(v['cve']), []).append((v['source'], v['modified'], v['vector'], x.rid))
    self.cache_vec = {}
    for v, x, _ in self.records('advisories_feed_cache.json', 'cache').values():
        self.cache_vec[v['ghsa'], self.pkey(v['eco'], v['name'])] = v['vector']
    self.ghsa_vec, ghsa_pub = ({}, {})
    for v, x, _ in self.records('advisories_ghsa.json', 'ghsa').values():
        c = self.vid(v['ghsa'])
        self.ghsa_vec.setdefault(c, []).append((x.rid, v['vector'], v['ghsa'], self.pkey(v['eco'], v['name'])))
        ghsa_pub.setdefault(c, []).append((x.rid, v['published']))
    replay = {}
    replay_wd = set()
    for v, x, _ in self.records('advisories_osv_replay.jsonl', 'osv').values():
        replay[v['osv'], self.pkey(v['eco'], v['name'])] = v['events']
    osv = []
    osv_pub, withdrawn = ({}, set())
    for v, x, _ in self.records('advisories_osv.jsonl', 'osv').values():
        c = self.vid(v['osv'])
        key = self.pkey(v['eco'], v['name'])
        ev = v['events']
        if isinstance(ev, Sentinel):
            ev = None
        if isinstance(v['withdrawn'], int) and v['withdrawn'] < CUT:
            withdrawn.add(c)
        osv_pub.setdefault(c, []).append((x.rid, v['published']))
        osv.append((c, key, ev, x.rid))
    withdrawn |= replay_wd
    pubs = {}
    for c in set(osv_pub) | set(ghsa_pub):
        order = ['osv', 'ghsa']
        val = 'absent'
        for src in order:
            lst = osv_pub.get(c) if src == 'osv' else ghsa_pub.get(c)
            if lst:
                val = sorted(lst)[0][1]
                if isinstance(val, Sentinel):
                    continue
                break
        pubs[c] = None if val == 'absent' or isinstance(val, Sentinel) else val
    self.vpub = pubs
    pins_by = {}
    for p in self.pins:
        if p['scope'] == 'runtime' and p['pinned'] is not None:
            pins_by.setdefault(p['package'], []).append(p)
    vex = {}
    for v, x, _ in self.records('vex_statements.xml', 'vex').values():
        if v['issued'] < CUT:
            k = (v['service'], self.vid(v['vuln']))
            if k not in vex or (v['issued'], x.rid) > vex[k][0]:
                vex[k] = ((v['issued'], x.rid), v['status'])
    waived = set()
    for v, x, _ in self.records('waivers.db', 'waivers').values():
        if v['granted'] < CUT <= v['expires']:
            waived.add((v['service'], self.vid(v['vuln'])))
    freeze = {}
    for v, x, _ in self.records('change_freeze.ics', 'windows').values():
        freeze.setdefault(v['service'], set()).update(range(v['start'], v['end'] + 1))
    holi = {r: {days_from_civil(int(d[0:4]), int(d[5:7]), int(d[8:10])) for d in ds} for r, ds in HOLIDAY.items()}
    sla_over = {}
    for v, x, _ in self.records('sla_policy.pdf', 'sla_overrides').values():
        if v['effective'] < CUT_DATE:
            k = (v['service'], v['severity'])
            if k not in sla_over or (v['effective'], x.rid) > sla_over[k][0]:
                sla_over[k] = ((v['effective'], x.rid), v['days'])
    factors, est = ({}, {})
    for v, x, _ in self.records('scoring_methodology.pdf', 'factors').values():
        if v['effective'] <= CUT_DATE:
            k = (self.pkey(v['eco'], v['name']), v['major'])
            if k not in factors or (v['effective'], x.rid) > factors[k][0]:
                factors[k] = ((v['effective'], x.rid), v['factor'])
    for t, _ in SCHEMA['remediation_estimates.xlsx']:
        for v, x, _ in self.records('remediation_estimates.xlsx', t).values():
            if v['effective'] <= CUT_DATE:
                k = (self.pkey(v['eco'], v['name']), v['major'])
                if k not in est or (v['effective'], x.rid) > est[k][0]:
                    est[k] = ((v['effective'], x.rid), v['hours'])
    vec_cache = {}
    seen = set()
    out = []
    for c, key, ev, rid in osv:
        if c in withdrawn or ev is None:
            continue
        pub = pubs.get(c)
        if pub is not None and pub >= CUT:
            continue
        rng_ = parse_events(ev)
        for p in pins_by.get(key, []):
            if not affected(rng_, p['pinned']):
                continue
            k3 = (p['service'], key, c)
            if k3 in seen:
                continue
            seen.add(k3)
            if c not in vec_cache:
                vec_cache[c] = self.vuln_vector(c)
            score = cvss_base(vec_cache[c]) if vec_cache[c] else Decimal('0.0')
            sev = severity_of(score)
            s = self.svc[p['service']]
            st = vex.get((p['service'], c))
            if st and st[1] != 'affected':
                status = 'not_affected'
            elif (p['service'], c) in waived:
                status = 'waived'
            else:
                status = 'open'
            if pub is None:
                pday, days = (None, None)
            else:
                pday = pub // DAY
                days = business_days(pday, CUT_DAY, freeze.get(p['service'], set()) | holi.get(s['region'], set()))
            sla = SLA_MATRIX[sev][s['tier']]
            so = sla_over.get((p['service'], sev))
            if so:
                sla = so[1]
            breach = days is not None and days > sla
            ver = p['pinned']
            cands = sorted((r['ver'] for vs, r in self.rel.get(key, {}).items() if r['pub'] < CUT and ver < r['ver']))
            fixed = next((x for x in cands if not affected(rng_, x)), None)
            e_o = est.get((key, ver.major))
            if e_o:
                estimate = qd(e_o[1], 2)
            else:
                fo = factors.get((key, ver.major))
                fac = fo[1] if fo else Decimal(1)
                mult = Decimal(3) if fixed is None else Decimal(2) if fixed.major > ver.major else Decimal(1)
                estimate = qd(BASE_HOURS[sev] * fac * mult, 2)
            out.append({'service': p['service'], 'package': key, 'version': str(ver), 'vuln': c, 'cvss': qd(score, 1), 'severity': sev, 'status': status, 'published': iso_date(pday) if pday is not None else None, 'days_open': days, 'sla_days': sla, 'breach': breach, 'estimate': estimate, 'fixed': str(fixed) if fixed else None})
    out.sort(key=lambda e: (e['service'], e['package'], e['vuln']))
    self.exposures = out
    self.vec_cache = vec_cache
Close.stage1 = stage1
Close.build_releases = build_releases
Close.yanked_at = yanked_at
Close.license_of = license_of
Close.build_services = build_services
Close.build_pins = build_pins
Close.vuln_vector = vuln_vector
Close.build_exposures = build_exposures
