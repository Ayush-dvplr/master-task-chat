#!/usr/bin/env python3
"""Aggregate tool-part load without printing prompts or tool output."""
import csv
import json
import sqlite3
from collections import Counter

rows=list(csv.DictReader(open(__file__.replace('scripts/inspect_tool_load.py','worker_measurements.csv'))))
db=sqlite3.connect('file:/Users/mac/.local/share/opencode/opencode.db?mode=ro',uri=True)
for step in ('P11','P12','P13','P9','P2'):
    group=sorted((x for x in rows if x['step']==step),key=lambda x:float(x['output']))
    sample=[group[i] for i in sorted(set([0,len(group)//2,len(group)-1]))]
    for x in sample:
        sid=db.execute('select id from session where title=? and parent_id is null',(x['sha'],)).fetchone()[0]
        counts=Counter(); chars=Counter(); commands=Counter()
        for (raw,) in db.execute('select data from part where session_id=?',(sid,)):
            try: p=json.loads(raw)
            except json.JSONDecodeError: continue
            typ=p.get('type','?'); counts[typ]+=1; chars[typ]+=len(raw)
            if typ=='tool':
                inp=p.get('state',{}).get('input',{})
                if isinstance(inp,dict):
                    cmd=str(inp.get('command',''))
                    for name in ('cat','sed','rg','find','sleep','docker','harbor','sqlite3'):
                        if name in cmd: commands[name]+=1
        print(json.dumps({'step':step,'sha':x['sha'],'tool_count':counts['tool'],
              'tool_json_chars':chars['tool'],'reasoning_parts':counts['reasoning'],
              'step_finish_parts':counts['step-finish'],'command_mentions':dict(commands)}))
