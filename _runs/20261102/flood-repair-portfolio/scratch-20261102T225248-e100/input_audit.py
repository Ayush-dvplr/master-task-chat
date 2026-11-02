import configparser
import csv
import hashlib
import io
import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path

root = Path('/Users/mac/Desktop/Terminal Bench/QC/copies/688700c/flood-repair-portfolio/environment/data')
texts = {}
for path in sorted(root.iterdir()):
    chunks = []
    with path.open('rb') as handle:
        while chunk := handle.read(48000):
            chunks.append(chunk)
    raw = b''.join(chunks)
    texts[path.name] = raw.decode('utf-8')
    assert not any(mark in texts[path.name] for mark in ('\u2013', '\u2014'))
    print('FULL_READ', path.name, 'bytes', len(raw), 'lines', len(raw.splitlines()),
          'sha256', hashlib.sha256(raw).hexdigest())

def table(name, sep=','):
    reader = csv.DictReader(io.StringIO(texts[name]), delimiter=sep)
    result = list(reader)
    assert all(None not in row and all(v is not None for v in row.values()) for row in result)
    print('TABLE', name, 'header', reader.fieldnames, 'rows', len(result),
          'first', result[0], 'last', result[-1])
    return result

manifest = json.loads(texts['manifest.json'])
assert set(manifest['files']) == set(texts) - {'manifest.json', 'contract.md'}
p = table('proposals.csv')
s = table('segment_codes.tsv', '\t')
permits = table('permits.csv')
crews = table('crews.tsv', '\t')
regions = table('region_codes.csv')
sites = [json.loads(line) for line in texts['sites.jsonl'].splitlines() if line.strip()]
exclusions = json.loads(texts['exclusions.json'])
queries = [(i, line.split()) for i, line in enumerate(texts['audit_queries.txt'].splitlines(), 1) if line.strip()]
rates = configparser.ConfigParser()
rates.optionxform = str
rates.read_string(texts['benefits.ini'])
rate = dict(rates['segment_rate'])
uplift = dict(rates['risk_uplift'])
assert all(5 <= int(v) <= 60 for v in rate.values())
assert all(-10 <= int(v) <= 30 for v in uplift.values())
site = {r['site']: r for r in sites}
crew = {r['crew']: r['mode'] for r in crews}
region = {r['site']: r['region'] for r in regions}
assert len(site) == len(sites) == len(region) == len(regions)
assert len(crew) == len(crews)
assert set(crew.values()) <= {'shared', 'exclusive'}
assert set(region.values()) <= {'North', 'South', 'West', 'East'}
assert set(site) == set(region)
assert all(r['risk_class'] in uplift and 0 <= r['premium'] <= 800 for r in sites)
print('JSONL_ALL', len(sites), 'first', sites[0], 'last', sites[-1])
print('EXCLUSIONS_ALL', len(exclusions), 'first', exclusions[0], 'last', exclusions[-1])
print('QUERY_ALL', len(queries), 'first', queries[0], 'last', queries[-1], Counter(q[0] for _, q in queries))
byround = defaultdict(list)
for i, row in enumerate(p, 1):
    byround[row['round']].append((i, row))
assert len(byround) <= 200 and max(map(len, byround.values())) <= 160
seg = {(r['round'], r['proposal']): r['segment'] for r in s}
numbered = {'proposals.csv': p, 'segment_codes.tsv': s, 'permits.csv': permits, 'exclusions.json': exclusions}
rejects = []
source_counts = Counter()
reasons = Counter()
max_records = 0
ties = []
planned_values = []
shared_sizes = []
for rid, rows in sorted(byround.items()):
    ids = {r['proposal'] for _, r in rows}
    named = ids | {r['site'] for _, r in rows}
    hit = None
    records = sum(r['round'] == rid for r in permits) + sum(r['round'] == rid for r in exclusions)
    max_records = max(max_records, records)
    for filename in manifest['files']:
        seen = set()
        for number, row in enumerate(numbered.get(filename, []), 1):
            if row['round'] != rid:
                continue
            code = None
            if filename == 'proposals.csv':
                if row['proposal'] in seen:
                    code = 'DUPLICATE_PROPOSAL'
                elif not (row['households'].isascii() and row['households'].isdigit()
                          and 1 <= int(row['households']) <= 60
                          and row['site'] in site and row['crew'] in crew
                          and row['risk_override'] in ('', 'A', 'B', 'C', 'D')):
                    code = 'INVALID_INPUT'
                seen.add(row['proposal'])
            elif filename == 'segment_codes.tsv':
                code = 'UNKNOWN_PROPOSAL' if row['proposal'] not in ids else 'INVALID_INPUT' if row['segment'] not in rate else None
            elif filename == 'permits.csv':
                code = 'UNKNOWN_PROPOSAL' if row['proposal'] not in ids else 'INVALID_INPUT' if row['status'] not in ('held', 'applied', 'withdrawn') else None
            elif filename == 'exclusions.json':
                code = 'UNKNOWN_PROPOSAL' if row['first'] not in named or row['second'] not in named else 'INVALID_INPUT' if row['first'] == row['second'] else None
            if code:
                hit = {'round': rid, 'file': filename, 'row': number, 'code': code}
                break
        if hit:
            break
    if not hit:
        vals = {}
        for number, row in rows:
            cls = row['risk_override'] or site[row['site']]['risk_class']
            vals[row['proposal']] = int(row['households']) * (int(rate[seg[(rid, row['proposal'])]]) + int(uplift[cls])) + site[row['site']]['premium']
            if vals[row['proposal']] < 1 and not hit:
                hit = {'round': rid, 'file': 'proposals.csv', 'row': number, 'code': 'NONPOSITIVE_BENEFIT'}
        if not hit:
            planned_values.extend(vals.values())
    if hit:
        rejects.append(hit)
        reasons[(hit['file'], hit['code'])] += 1
        continue
    props = {r['proposal']: r for _, r in rows}
    groups = defaultdict(set)
    for row in permits:
        if row['round'] == rid and row['status'] != 'withdrawn':
            groups[row['permit']].add(row['proposal'])
    pairs = {}
    for a, b in itertools.combinations(sorted(ids), 2):
        found = set()
        if props[a]['crew'] == props[b]['crew'] and crew[props[a]['crew']] == 'exclusive':
            found.add('crew')
        if any({a, b} <= group for group in groups.values()):
            found.add('permit')
        na, nb = {a, props[a]['site']}, {b, props[b]['site']}
        if any(e['round'] == rid and ((e['first'] in na and e['second'] in nb) or (e['second'] in na and e['first'] in nb)) for e in exclusions):
            found.add('exclusion')
        if found:
            pairs[(a, b)] = found
            source_counts.update(found)
    loads = Counter(r['crew'] for _, r in rows if crew[r['crew']] == 'shared')
    shared_sizes.extend(loads.values())
    if len(ids) <= 16:
        best = -1
        winners = []
        ordered = sorted(ids)
        for mask in range(1 << len(ordered)):
            chosen = [pid for k, pid in enumerate(ordered) if mask & (1 << k)]
            if any(pair in pairs for pair in itertools.combinations(chosen, 2)):
                continue
            load = Counter(props[pid]['crew'] for pid in chosen if crew[props[pid]['crew']] == 'shared')
            if any(n > 4 for n in load.values()):
                continue
            score = sum(vals[pid] for pid in chosen)
            if score > best:
                best, winners = score, [chosen]
            elif score == best:
                winners.append(chosen)
        if len(winners) > 1:
            ties.append((rid, len(winners), min(winners)))
for line, query in queries:
    assert query[0] in ('VALUE', 'PAIR') and len(query) == (3 if query[0] == 'VALUE' else 4)
    assert query[1] in byround
    assert set(query[2:]) <= {r['proposal'] for _, r in byround[query[1]]}
assert max_records <= 900
print('BOOK', manifest['book'], 'rounds', len(byround), 'proposal_count_range', min(map(len, byround.values())), max(map(len, byround.values())), 'max_permit_plus_exclusion', max_records)
print('REJECTIONS', len(rejects), json.dumps(rejects, sort_keys=True))
print('FAULT_CATEGORIES', sorted(reasons.items()))
print('PLANNED_BENEFIT_RANGE', min(planned_values), max(planned_values))
print('CONFLICT_SOURCES', dict(source_counts), 'max_shared_members', max(shared_sizes))
print('SMALL_TIED_ROUNDS', len(ties), 'first', ties[:3])
print('ALL_INPUT_ROWS_PARSED_AND_CHECKED')
