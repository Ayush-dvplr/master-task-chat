#!/usr/bin/env python3
"""Summarize retained BuildKit warm logs and saved cache inventory."""
import csv
import re
from pathlib import Path

OUT=Path(__file__).resolve().parents[1]
logs=Path('/tmp/opencode-logs')
rows=[]
for p in logs.rglob('*.log'):
    try: s=p.read_text(errors='replace')
    except OSError: continue
    if '#0 building with' not in s: continue
    stages={}
    for line in s.splitlines():
        m=re.match(r'#(\d+) \[.*\] (RUN |COPY |FROM |WORKDIR )(.*)',line)
        if m: stages[m[1]]=m[2]+m[3]
    cached=set(re.findall(r'^#(\d+) CACHED$',s,re.M))
    done={a:float(b) for a,b in re.findall(r'^#(\d+) DONE ([\d.]+)s$',s,re.M)}
    work=[(k,desc,done.get(k,0)) for k,desc in stages.items() if k not in cached and k in done and (desc.startswith('RUN ') or desc.startswith('COPY '))]
    rows.append(dict(log=str(p),cached_stages=len(cached),uncached_work_stages=len(work),
                     uncached_work_seconds=round(sum(x[2] for x in work),1),
                     longest_uncached_stage_seconds=round(max((x[2] for x in work),default=0),1),
                     downloaded='Downloading ' in s or 'Get:' in s,
                     uncached_stages='; '.join(f'{x[1][:75]} [{x[2]}s]' for x in work)))
with (OUT/'BUILD_LOGS.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
print('build logs',len(rows),'cold (uncached RUN)',sum(any('RUN ' in part for part in r['uncached_stages'].split('; ')) for r in rows),'downloaded',sum(r['downloaded'] for r in rows))
for r in rows: print(Path(r['log']).name,r['uncached_work_stages'],r['uncached_work_seconds'],r['longest_uncached_stage_seconds'],r['downloaded'])

s=(OUT/'inventory/buildx_du_verbose.txt').read_text()
blocks=re.split(r'(?=^ID:\s+)',s,flags=re.M)
blocks=[x for x in blocks if x.startswith('ID:')]
print('cache_entries',len(blocks),'reclaimable',sum('Reclaimable:  true' in b for b in blocks))
def size_bytes(block):
    match=re.search(r'^Size:\s*([\d.]+)([kMGT]?B)',block,re.M)
    return float(match[1])*{'B':1,'kB':1e3,'MB':1e6,'GB':1e9,'TB':1e12}[match[2]] if match else 0
old=[b for b in blocks if (m:=re.search(r'^Last used:\s*(\d+) days ago',b,re.M)) and int(m[1])>=8]
print('cache_last_used_8plus_days',len(old),'accounted_GB',round(sum(map(size_bytes,old))/1e9,3))
