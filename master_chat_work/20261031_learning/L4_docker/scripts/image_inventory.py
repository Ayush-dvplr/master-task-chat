#!/usr/bin/env python3
"""Classify saved Docker image inventory without invoking Docker."""
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]
TB = Path('/Users/mac/Desktop/Terminal Bench')
rows = [line.rstrip('\n').split('|') for line in (OUT/'inventory/images.txt').open()]
registry = {x['slug']: x.get('pipeline', {}).get('stage', '') for x in json.load((TB/'master_chat_tasks/registry/tasks.json').open())['tasks']}
inputs = {p.name for p in (TB/'Terminal_2.0_Harbor_Harness/Tasks_INPUT').iterdir() if p.is_dir()}
aliases = {
    'b7c': 'b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042',
    'dhfp': 'district-heat-flex-procurement', 'smpr': 'schema-migration-plan-repair',
    'mrda': 'match-replay-desync-audit', 'spr': 'sentinel-policy-recompute',
    'ccbq': 'cold-chain-backbone-quote', 'owr': 'outage-window-replan',
    'wae': 'warrant-asof-entitlement-compiler', 'dpr': 'dispatch-plan-reoptimization',
    'mur': 'metered-usage-rating-pipeline', 'evs': 'emberforge-vault-settlement',
    'efvs': 'emberforge-vault-settlement', 'crr': 'cohort-retention-reconciliation',
    'snlsq': 'sensor-network-lsq-correlated-adjustment',
    'varr': 'vendor-archive-roundtrip-recovery', 'vart': 'vendor-archive-roundtrip-recovery',
    'frp': 'flood-repair-portfolio',
}
base = {'python', 'public.ecr.aws/docker/library/python', 'alpine', 'curlimages/curl', 'harbor-prebuilt'}
system = {}
for line in (OUT/'inventory/system_df_v.txt').open():
    parts = re.split(r'\s{2,}', line.strip())
    if len(parts) == 8 and re.fullmatch(r'[0-9a-f]{12}', parts[2]):
        system[parts[2]] = parts

def amount(s):
    m = re.fullmatch(r'([\d.]+)([kMGT]?B)', s)
    if not m: return 0
    return round(float(m[1]) * {'B':1,'kB':1000,'MB':10**6,'GB':10**9,'TB':10**12}[m[2]])

def identify(repo):
    if repo in base: return '', 'base image', 'base name'
    if repo == '<none>': return '', 'dangling', 'repository=<none>'
    if 'b7c42a8f' in repo: return aliases['b7c'], '', 'UUID prefix b7c42a8f in repository'
    for slug in sorted(registry.keys() | inputs, key=len, reverse=True):
        if slug in repo: return slug, '', 'full slug in repository'
    for marker, slug in [('metered','metered-usage-rating-pipeline'),('tariff','tariff-engine-audit-repair'),
                         ('sentinel','sentinel-policy-recompute'),('caldermoor','caldermoor-commitment-closure'),
                         ('emberforge','emberforge-vault-settlement'),('dispatch','dispatch-plan-reoptimization'),
                         ('cohort','cohort-retention-reconciliation'),('warrant','warrant-asof-entitlement-compiler'),
                         ('sprwarm','sentinel-policy-recompute'),('sprc','sentinel-policy-recompute'),
                         ('mu361674d','metered-usage-rating-pipeline'),('mu09963d3','metered-usage-rating-pipeline'),
                         ('fz-e317de1','data-product-config-compiler')]:
        if marker in repo: return slug, '', f'marker {marker} in repository'
    toks = re.split(r'[-_]+', repo)
    for tok in toks:
        if tok in aliases: return aliases[tok], '', f'alias {tok} in repository'
    # A few names are generic (plain, run, owner, stub, forge) and cannot
    # safely be assigned to a task from the inventory alone.
    return '', 'unresolved', 'no unambiguous task name'

out = []
for repo, tag, image_id, size, created in rows:
    slug, cat, evidence = identify(repo)
    stage = registry.get(slug, '')
    if not cat:
        cat = ('pushed task' if stage == 'pushed' else
               'parked/dropped task' if stage in ('parked','dropped','killed') else
               'live task' if slug in inputs and stage not in ('dropped','parked','killed') else
               'unresolved')
    df = system.get(image_id, [])
    out.append(dict(repository=repo,tag=tag,image_id=image_id,display_size=size,
                    created=created,unique_bytes=amount(df[6]) if df else '',
                    shared_bytes=amount(df[5]) if df else '',
                    containers=df[7] if df else '',category=cat,task_slug=slug,
                    registry_stage=stage,task_input=slug in inputs,evidence=evidence))
with (OUT/'IMAGES.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=out[0].keys()); w.writeheader(); w.writerows(out)
c=Counter(r['category'] for r in out)
u=defaultdict(int)
for r in out: u[r['category']] += int(r['unique_bytes'] or 0)
print('rows',len(out),'matched df',sum(bool(r['unique_bytes'] != '') for r in out))
for k,v in c.most_common(): print(k,v,'unique_GB',round(u[k]/1e9,3))
print('unresolved',[(r['repository'],r['image_id']) for r in out if r['category']=='unresolved'][:30])
