#!/usr/bin/env python3
"""Read-only board result inventory, printing only counts and field frequencies."""
import collections
import json
from pathlib import Path
TB=Path('/Users/mac/Desktop/Terminal Bench')
rows=json.loads((TB/'master_chat_tasks/board.json').read_text())['rows']
counts=collections.Counter(); keys=collections.defaultdict(collections.Counter)
examples={}
for row in rows:
    p=Path(row['result'])
    if not p.is_absolute(): p=TB/p
    if not p.exists(): counts['missing']+=1; continue
    if p.is_dir(): counts['directory_result_path']+=1; continue
    if p.suffix != '.json': counts['non_json_result_path']+=1; continue
    try: d=json.loads(p.read_text())
    except (OSError,ValueError): counts['invalid']+=1; continue
    counts['parsed']+=1
    if not isinstance(d,dict): counts['nonobject']+=1; continue
    counts['sha_match' if d.get('sha',d.get('board'))==row['sha'] else 'sha_mismatch']+=1
    step=row['step'].split()[0]
    counts['step:'+step]+=1
    keys[step].update(d.keys())
    examples.setdefault(step,str(p))
print(json.dumps({'counts':counts,'fields_by_step':keys,'examples':examples},sort_keys=True))
