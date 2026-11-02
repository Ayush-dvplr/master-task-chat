#!/usr/bin/env python3
"""Read-only field/count inventory for S3. Emits no record values."""
import collections
import glob
import json
import sqlite3
from pathlib import Path

TB = Path('/Users/mac/Desktop/Terminal Bench')
MT = TB / 'master_chat_tasks'
GROUPS = {
    'tasks': [MT/'registry/tasks.json'],
    'board': [MT/'board.json'],
    'decisions': [MT/'decisions.jsonl'],
    'feedback': [MT/'feedback.jsonl'],
    'lessons': [MT/'lessons.jsonl'],
    'scores': [MT/'registry/scores.jsonl'],
    'ideas': [MT/'registry/ideas.jsonl'],
    'log': [MT/'log.jsonl'],
    'levers': [MT/'registry/levers.json'],
    'peer_tasks': [MT/'registry/peer_tasks.json'],
    'open_questions': [MT/'open_questions.json'],
    'state': [MT/'state.json'],
    'auto_state': list((MT/'auto/runs').glob('*/state.json')),
    'auto_events': list((MT/'auto/runs').glob('*/events.jsonl')),
    'auto_night_log': list((MT/'auto/runs').glob('*/night_log.jsonl')),
    'queue_state': [TB/'Terminal_2.0_Harbor_Harness/.master-queue/state.json'],
    'auto_hold': [TB/'Terminal_2.0_Harbor_Harness/.master-queue/auto_hold.json'],
    'auto_scheduled': [MT/'auto/SCHEDULED.json'],
    'generator_ideas': [TB/'master_chat_work/gen_memory/ideas.jsonl'],
    'fingerprint_qc': [MT/'knowledge/fingerprints/qc.json'],
    'fingerprint_generator': [MT/'knowledge/fingerprints/pl_generator.json'],
    'knowledge_intake': list((MT/'knowledge/intake').glob('*.json')),
    'qc_result': list((TB/'QC/reports').glob('*/result_*.json')),
}

def fields(rows):
    c = collections.Counter()
    types = collections.defaultdict(set)
    for row in rows:
        if not isinstance(row, dict):
            c['<non-object>'] += 1
            continue
        for k,v in row.items():
            c[k] += 1
            types[k].add(type(v).__name__)
    return {k: {'count':n, 'types': sorted(types[k])} for k,n in sorted(c.items())}

for name, paths in GROUPS.items():
    rows=[]; roots=[]; nested=collections.defaultdict(list); errors=[]
    for p in paths:
        if not p.exists():
            errors.append(f'missing:{p}')
            continue
        try:
            if p.suffix == '.jsonl':
                for line in p.read_text().splitlines():
                    if line.strip(): rows.append(json.loads(line))
            else:
                obj=json.loads(p.read_text())
                roots.append(obj)
                if isinstance(obj,list): rows.extend(obj)
                elif isinstance(obj,dict):
                    # Capture root keys and common collections separately.
                    rows.append(obj)
                    for k,v in obj.items():
                        if isinstance(v,list): nested[k].extend(v)
                    if name=='tasks':
                        nested['pipeline'].extend(x['pipeline'] for x in obj.get('tasks',[]) if isinstance(x,dict) and isinstance(x.get('pipeline'),dict))
        except (OSError,ValueError) as e:
            errors.append(f'{p}:{type(e).__name__}')
    output={'group':name,'files':len(paths),'root_or_rows':len(rows),'fields':fields(rows),'nested':{k:{'rows':len(v),'fields':fields(v)} for k,v in nested.items()},'errors':errors}
    print(json.dumps(output,sort_keys=True))

p=MT/'pending.db'
con=sqlite3.connect(f'file:{p}?mode=ro',uri=True)
for (table,) in con.execute("select name from sqlite_master where type='table' order by name"):
    cols=[r[1] for r in con.execute(f'pragma table_info({table})')]
    count=con.execute(f'select count(*) from {table}').fetchone()[0]
    print(json.dumps({'group':'pending.'+table,'rows':count,'columns':cols}))
con.close()
