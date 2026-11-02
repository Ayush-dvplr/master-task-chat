#!/usr/bin/env python3
"""Measure bootstrap record text bytes; pending is opened read-only."""
import json
import sqlite3
import subprocess
from pathlib import Path

MT=Path('/Users/mac/Desktop/Terminal Bench/master_chat_tasks')
def n(s): return len(s.encode())
status=subprocess.run(['python3',str(MT/'tools/status.py')],capture_output=True,text=True,check=True).stdout
con=sqlite3.connect(f'file:{MT/"pending.db"}?mode=ro',uri=True)
pending='\n'.join(' '.join(map(str,r)) for r in con.execute("SELECT id,status,kind,seq,priority,title,prompt FROM items WHERE status NOT IN ('done','dropped') ORDER BY seq,id"))
con.close()
dec=(MT/'decisions.jsonl').read_text().splitlines()[-10:]
feed=(MT/'feedback.jsonl').read_text()
less=(MT/'lessons.jsonl').read_text().splitlines()
proc=[x for x in less if json.loads(x).get('kind')=='master_process']
other=[x for x in less if json.loads(x).get('kind')!='master_process'][-10:]
state=(MT/'state.json').read_text()
parts={'status':status,'pending':pending,'decisions_last10':'\n'.join(dec),
       'feedback_all':feed,'lessons_process_plus10':'\n'.join(proc+other),'state':state}
print(json.dumps({'bytes':{k:n(v) for k,v in parts.items()},'total_bytes':sum(n(v) for v in parts.values()),'record_sources':len(parts)}))
