#!/usr/bin/env python3
"""Reference solution: repair the close program in /app/repo in place and install it as /app/out/build.py.

The repair is a list of hunks (module, first line, end line, digest of the replaced lines, replacement lines) against the
shipped modules of /app/repo/src/helios_close. Each hunk makes one rule of the close contract hold, or removes a definition a
repair left unused. The repaired package is checked with the repository's unit tests and amalgamated with its own tool; solve.sh
then runs the complete close once. A repository that is already repaired is left as it is, so the script can run twice.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

REPO = Path("/app/repo")
OUT = Path("/app/out")
PKG = REPO / "src" / "helios_close"
PATCH = [
    ('domain', 154, 155, '33efac8d360dfb4b', ['        return (self.major, self.minor, self.patch, 0, self.pre[0], self.pre[1])\n']),
    ('domain', 216, 218, 'b70a0424d4c2dc4d', ['        if v.pre is not None:\n', '            return self.lo is not None and self.lo.pre is not None and (self.lo.core() == v.core())\n']),
    ('domain', 232, 233, 'ef6c97eb9a0c1f47', ['    if v.major > 0:\n']),
    ('domain', 233, 234, 'a08e541985cdfde1', ['        hi = Ver(v.major + 1, 0, 0)\n', '    elif v.minor > 0:\n', '        hi = Ver(0, v.minor + 1, 0)\n']),
    ('domain', 276, 277, 'd77b3830f3cc55cd', ["        ru = roundup30 if head == 'CVSS:3.0' else roundup31\n"]),
    ('domain', 414, 415, 'd97ec0a6c8a55e6a', ['        if v < hi or (inc and v == hi):\n']),
    ('domain', 419, 422, '0b8b9fb7c95ba746', []),
    ('formats', 452, 453, 'b27e227a28652295', ['    return rows\n', 'def pdf_prose(p):\n', '    """The prose of a PDF export (its text lines before the first batch) joined by single spaces."""\n', '    lines = []\n', '    for ln in _pdf_lines(Path(p).read_bytes()):\n', "        if ln.startswith('BATCH '):\n", '            break\n', '        if ln:\n', '            lines.append(ln)\n', "    return ' '.join(lines)\n"]),
    ('formats', 497, 498, '701195c3e77c0f59', ["        base = XL1900_DAY if kind == 'xl' else XL1904_DAY\n"]),
    ('formats', 502, 503, 'f031c97fca9d7540', ["        d, m = (a, b_) if kind == 'dmy' else (b_, a)\n"]),
    ('formats', 524, 525, '4126aa84843ad72b', ["        s = s.replace('.', '').replace(',', '.')\n"]),
    ('formats', 543, 544, '2d9672a7a37150f2', ['        return Decimal(int(s)) / Decimal(60)\n']),
    ('formats', 554, 555, '51e0065ba20fd0d8', ['    exp = CUR_EXP.get(cur, 2)\n']),
    ('formats', 570, 571, 'efb0cd9e6c3a44ca', ["    return not v if conv == 'neg' else v\n"]),
    ('formats', 587, 588, '5d98881af4b13a1b', ['    return s\n']),
    ('formats', 606, 607, 'd2c2f30268619b68', ["        return f'CVE-{y}-{int(n):04d}'\n"]),
    ('records', 100, 101, '8b4c88df707c1936', ['    def in_force(revs):\n']),
    ('records', 103, 104, '73ce8210d0101836', ["            if x.rec_at >= CUT or x.st == 'draft':\n"]),
    ('records', 117, 118, '32d92b9aca778c12', ['            x = self.in_force(groups[rid])\n']),
    ('records', 133, 134, '32d92b9aca778c12', ['            x = self.in_force(groups[rid])\n']),
    ('records', 147, 148, '4a777a338a27241f', ['            if vf <= z and (vt is None or z < vt):\n']),
    ('records', 205, 207, 'e4fb2ad5ffdb7775', ['                    except (ValueError, IndexError, KeyError, TypeError, AttributeError, ArithmeticError) as exc:\n', '                        raise InputError(f\'{fname}: field {f} of record {v.get("rid")} is not valid under convention {cv}: {s!r}\') from exc\n']),
    ('records', 225, 226, 'f0c98ed36ff79a0b', ["            if k not in best or (x.v['decided'], rid) > best[k][0]:\n"]),
    ('records', 231, 232, '4547aedc50c3d9bc', ["            if x is None or x.v['issued'] >= CUT or rid not in self.approved:\n"]),
    ('records', 286, 287, '42050b515725f44e', ["        notices = self.records('yank_notices.mbox', 'notices')\n", "        confirmed = {v['ref'] for v, x, _ in notices.values() if v['action'] == 'rename' and x.rec_at < CUT and v.get('ref')}\n"]),
    ('records', 291, 292, 'd51f0dccbe7c7234', ["            if v['kind'] == 'spelling' or (v['kind'] == 'rename' and x.rid in confirmed):\n", "                amap[v['eco'], v['alias']] = v['target']\n"]),
    ('records', 293, 294, '5daf205b5ca06952', ["            if v['kind'] == 'rename' and v['effective'] is not None and (v['effective'] < LEGACY_RENAME_CUTOFF):\n"]),
    ('cascade', 157, 158, 'af583bc638faec10', ["        r['pct_rank'] = qd(Decimal(below) / Decimal(n - 1), 6) if n > 1 else qd(0, 6)\n"]),
    ('cascade', 200, 201, 'f04ba351e35c78d1', ['    team_left = {t: Decimal(c) if c is not None else None for t, c in cap.items()}\n']),
    ('cascade', 210, 211, '32c382f7371f0a1e', ["        if slots[e['service']] <= SERVICE_SLOTS:\n"]),
    ('cascade', 228, 230, 'c5ff09701076cdd7', ['    for r in srow:\n', "        a = tagg.setdefault(r['team'], {'services': 0, 'open': 0})\n"]),
    ('cascade', 231, 232, 'd5e0e6bc78640a59', ["        a['open'] += r['open']\n"]),
    ('cascade', 243, 244, '4b090e897d8ac212', ["            if b + row['amount_cents'] < 0:\n"]),
    ('cascade', 259, 260, '291a427cfd167732', ["    rp = [p for p in p1['pins.jsonl'] if p['scope'] == 'runtime' and p['pinned'] is not None]\n"]),
    ('cascade', 275, 276, '717dd0dd21aed620', ["        days = sorted(e['days_open'] for e in sel if e['days_open'] is not None)\n"]),
    ('cascade', 281, 282, '5b3783ff8aee925f', ['            k = int((Decimal(pq) * n).to_integral_value(rounding=ROUND_CEILING))\n']),
    ('cascade', 297, 298, '3bce7017cf7b4986', ["    n_rank = _ceil(TOP_RISK_SHARE * len(p2['service_risk.json']['rows']))\n"]),
    ('cascade', 299, 300, '3318b0678254bee5', ["    unsat = {p['service'] for p in p1['pins.jsonl'] if p['scope'] == 'runtime' and p['disposition'] == 'unsatisfiable'}\n"]),
    ('cascade', 385, 386, '6bc4db2d28fb03d2', ["            s = sum((delta * svc[e['service']]['weight'] for e in openx if e['vuln'] == r['target']), Decimal('0'))\n"]),
    ('cascade', 391, 392, '339c011abe56e6ce', ["            after = closing.get(r['target'], 0) + imp if r['target'] is not None else None\n"]),
    ('cascade', 407, 409, '3434f730759f8bde', ['        util = qd(a / Decimal(c), 6) if c else None\n', "        score = qd(tr['risk'] * (Decimal(1) + Decimal(br.get(k, 0)) / Decimal(tr['open'] + 1)), 6)\n"]),
    ('rules', 4, 5, 'c6f68f3c6e0174bc', ["POLICY_SEVERITIES = ['critical', 'high', 'medium', 'low', 'none']\n", '\n', 'def policy(self):\n', '    """Holidays by region, SLA targets by severity and tier, base hours by severity and tier weights, read from the policy\n', '    documents of the input directory (sla_policy.pdf and scoring_methodology.pdf); another corpus may state other figures."""\n', "    if getattr(self, '_policy', None) is not None:\n", '        return self._policy\n', "    sla_text = pdf_prose(self.d / 'sla_policy.pdf')\n", '    matrix = {}\n', "    for sev, t0, t1, t2, t3 in re.findall('\\\\b(critical|high|medium|low|none): tier 0 (\\\\d+), tier 1 (\\\\d+), tier 2 (\\\\d+), tier 3 (\\\\d+) business days', sla_text):\n", '        matrix[sev] = [int(t0), int(t1), int(t2), int(t3)]\n', '    holidays = {}\n', "    m = re.search('Holidays: (.*?)(?: Overrides|$)', sla_text)\n", '    if m:\n', "        for reg, dates in re.findall('([a-z-]+): ((?:\\\\d{4}-\\\\d{2}-\\\\d{2}(?:, )?)*)', m.group(1)):\n", "            holidays[reg] = {dec_date(x, 'iso') for x in re.findall('\\\\d{4}-\\\\d{2}-\\\\d{2}', dates)}\n", '    base = {}\n', "    score_text = pdf_prose(self.d / 'scoring_methodology.pdf')\n", "    m = re.search('Base hours: (.*?)\\\\. The complexity factor', score_text)\n", '    if m:\n', "        for sev, h in re.findall('(critical|high|medium|low|none): (\\\\d+(?:\\\\.\\\\d+)?)', m.group(1)):\n", '            base[sev] = Decimal(h)\n', "    weights = {int(t): Decimal(w) for t, w in re.findall('tier ([0-3]): (\\\\d+(?:\\\\.\\\\d+)?)', score_text)}\n", '    if set(matrix) != set(POLICY_SEVERITIES) or set(base) != set(POLICY_SEVERITIES) or set(holidays) != set(REGIONS) or set(weights) != {0, 1, 2, 3}:\n', "        raise InputError('the policy documents do not state every SLA target, holiday list, base hours figure and tier weight')\n", '    self._policy = (holidays, matrix, base, weights)\n', '    return self._policy\n']),
    ('rules', 106, 107, 'd4e725fe6fa8e5eb', ["        if v['quarantined'] is True:\n"]),
    ('rules', 136, 137, '2f9591473f89a070', ["        if v['granted'] is not None and v['granted'] <= CUT_DATE and (not isinstance(rv, int) or rv > CUT_DATE):\n"]),
    ('rules', 189, 190, 'f19dae6a8da3b2cb', ["        if v['service'] not in has_life:\n"]),
    ('rules', 207, 208, 'ddefe51656eabf9c', ["            t = v['at'] - offs.get((v['host'], v['at'] // DAY), 0)\n"]),
    ('rules', 209, 210, '9789879cbd16ed7f', ["            if f == 'deploy_events_legacy.log' and (not (s and s['region'] == 'us-central' and (t < MIGRATION))):\n"]),
    ('rules', 211, 213, 'db81f271524f87bd', ['            if rid not in seen:\n', "                seen[rid] = (v['service'], v['outcome'], t)\n"]),
    ('rules', 216, 217, 'd20f35dc099884cd', ['            cnt[svc] = cnt.get(svc, 0) + 1\n', '    tier_weight = self.policy()[3]\n']),
    ('rules', 220, 221, '191a6606615371fa', ["        s['weight'] = qd(tier_weight[s['tier']] * factor, 4)\n"]),
    ('rules', 225, 226, '97c36d38b5b0a9fe', ["        if x.rid in self.approved and v['valid_from'] <= CUT_DATE < v['valid_to']:\n"]),
    ('rules', 250, 251, '57a86135c62938a4', ["        src = 'manifests_snapshot.csv' if s['archived'] else HOME_FILE[s['home']]\n"]),
    ('rules', 261, 262, 'a63ea9da189bb9a5', ["                    if not cons.exact and self.yanked_at(key, vs, v['locked']):\n"]),
    ('rules', 283, 284, 'd7d184fb81bf1732', ["    order = self.authority.get((c, 'cvss_vector'), ['nvd', 'ghsa'])\n"]),
    ('rules', 288, 289, 'a7806dcc6732203b', ["                return max(cands, key=lambda r: (r[0] == 'NVD', r[1], r[3]))[2]\n"]),
    ('rules', 323, 324, 'a778da8473484195', ["            ev = replay.get((v['osv'], key))\n"]),
    ('rules', 331, 332, '03b33e2640c7097d', ["        order = self.authority.get((c, 'published'), ['osv', 'ghsa'])\n"]),
    ('rules', 337, 339, '92b61d5fd4eb719d', []),
    ('rules', 354, 355, '0ff6adad89b24cba', ["        if x.rid in self.approved and v['granted'] < CUT <= v['expires']:\n"]),
    ('rules', 358, 360, '88973f98006ee39f', ["        freeze.setdefault(v['service'], set()).update(range(v['start'], v['end']))\n", '    holi, sla_matrix, base_hours, _ = self.policy()\n']),
    ('rules', 362, 363, '631e72054938cad1', ["        if v['effective'] <= CUT_DATE:\n"]),
    ('rules', 401, 402, 'f7a103ac5eefae7e', ["            if st and st[1] == 'not_affected':\n"]),
    ('rules', 410, 413, 'f3ba43242d632315', ["                pday = (pub + zone_offset(REGION_ZONE[s['region']], pub)) // DAY\n", "                days = business_days(pday + 1, CUT_DAY, freeze.get(p['service'], set()) | holi.get(s['region'], set()))\n", "            sla = sla_matrix[sev][s['tier']]\n"]),
    ('rules', 418, 419, 'a7ce8ec507e4c99d', ["            cands = sorted((r['ver'] for vs, r in self.rel.get(key, {}).items() if r['pub'] < CUT and ver < r['ver'] and (not self.yanked_at(key, vs, CUT))))\n"]),
    ('rules', 427, 428, '27d272905c18c9c7', ['                estimate = qd(base_hours[sev] * fac * mult, 2)\n']),
    ('rules', 432, 433, '000cc8d963cf449f', ['Close.stage1 = stage1\n', 'Close.policy = policy\n']),
    ('ledger', 42, 43, '77a89f4d25ec80f4', ['            cancelled.add(rid)\n', "            if v['reverses']:\n", "                cancelled.add(v['reverses'])\n"]),
    ('ledger', 65, 66, '176e7438a30cf1de', ['        if at <= t:\n']),
    ('ledger', 79, 80, '6812653d6c1fa6e7', ['    mo = m if (y, m) in ((2025, 7), (2025, 8), (2025, 9)) else 9 if (y, m) > (2025, 9) else 7\n']),
    ('ledger', 90, 91, '6a43782c5667af28', ['        if e == eng and start <= z and (end is None or z < end):\n']),
    ('ledger', 144, 145, '644e8ba3e52006a6', ["        if v['role'] == 'owner' and v['effective'] < CUT:\n"]),
    ('ledger', 153, 154, 'a2e477ccc9b8b724', ["        stable = [r['ver'] for vs, r in rels.items() if r['ver'].pre is None and vs not in yk]\n"]),
    ('ledger', 164, 165, '47c27528d17d6ac6', ["        cap = None if t['model'] == 'uncapped' else int(t['cap'] // 1)\n"]),
]
PRISTINE = {'cascade': '7b9322d76d971aad8cd57bd8c090aa04e2ca7b02f0502ba03b976bf8b7e73f52',
 'domain': 'd523547920414aea87c4e7f6e143d8e9e798c2e0c8aa9a25dd46bd4e397b9808',
 'formats': '17d475fd7ce885bc4f586d733f5ef124e5cb2a6ea42b21eb87a8cd8af9985150',
 'ledger': 'ef2e6289d488511f109ab71adef67be051a5b47092281098a426835bebcc0278',
 'records': '7426550fc94196fb7dd0e267ba3f2d26e91b863a9409cf21d019c5f202b2f01a',
 'rules': '18152faa4f6a08b8e37ae5defdef444bcbf275e8683ef88062f1c0eae1853c22'}
REPAIRED = {'cascade': '6fd1157c4a2286de10d4860f1da3058aeda8061faa2002d09970b9fe31cd259f',
 'domain': 'd8ff22e70c1e6e406fb10d08a81015b0eb8126d0ee94ae84397fb4c35a430127',
 'formats': 'fa21edc58b39de735f93204500d3e28e4dcd9d6534f3969adfad3d15b1716687',
 'ledger': 'fb102566d95a2aa271a0eee19501e32b13c1fdba28d4cac35175165ebf04e5be',
 'records': 'ea9fe814a0019d22d6574a8fb661dbd7c5dfdbf428a3419fe3b22e20dd4fb668',
 'rules': '121da9d2ba284244d2b6de49b0da3103ae1027fe726868ad2b2d15cc8fb8add8'}


def module_digest(name: str) -> str:
    return hashlib.sha256((PKG / f"{name}.py").read_bytes()).hexdigest()


def repair() -> None:
    by_module = {}
    for (name, i1, i2, digest, new) in PATCH:
        by_module.setdefault(name, []).append((i1, i2, digest, new))
    for name, hunks in by_module.items():
        p = PKG / f"{name}.py"
        lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
        for i1, i2, digest, new in sorted(hunks, reverse=True):
            if hashlib.sha256("".join(lines[i1:i2]).encode()).hexdigest()[:16] != digest:
                raise SystemExit(f"{name}.py line {i1 + 1} is not the shipped text the repair targets ({digest})")
            lines[i1:i2] = new
        p.write_text("".join(lines), encoding="utf-8")


def main() -> None:
    state = {name: module_digest(name) for name in PRISTINE}
    if state == PRISTINE:
        repair()
    elif state != REPAIRED:
        raise SystemExit("/app/repo is neither the shipped program nor its repaired form")
    if {name: module_digest(name) for name in PRISTINE} != REPAIRED:
        raise SystemExit("the repair did not produce the expected modules")
    env = dict(os.environ, PYTHONPATH=str(REPO / "src"), PYTHONDONTWRITEBYTECODE="1")
    res = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=REPO, env=env,
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise SystemExit(res.stderr[-3000:])
    OUT.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-B", str(REPO / "tools" / "amalgamate.py"), str(OUT / "build.py")], check=True, env=env)


if __name__ == "__main__":
    main()
