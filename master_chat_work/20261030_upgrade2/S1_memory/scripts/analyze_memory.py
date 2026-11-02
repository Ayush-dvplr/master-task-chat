import json, sqlite3, datetime, collections, pathlib
R=pathlib.Path('/Users/mac/Desktop/Terminal Bench/master_chat_tasks')
D=pathlib.Path('/Users/mac/.local/share/opencode/opencode.db')
SID='ses_ea5ff5f97ffe6WB1VzP4StPOw6'
board=json.loads((R/'board.json').read_text())['rows']
tasks={x['slug']:x for x in json.loads((R/'registry/tasks.json').read_text())['tasks']}
decisions=[json.loads(x) for x in (R/'decisions.jsonl').read_text().splitlines()]
con=sqlite3.connect(f'file:{R}/pending.db?mode=ro',uri=True)
con.row_factory=sqlite3.Row
pending={r['id']:dict(r) for r in con.execute('select * from items')}
print('COUNTS board',len(board),'tasks',len(tasks),'pending',len(pending),'decisions',len(decisions))
for day in ('2026-10-28','2026-10-29','2026-10-30'):
 print('DECISIONS',day,sum(str(x.get('ist','')).startswith(day) for x in decisions))
recent=[r for r in board if str(r.get('updated',''))[:10]>='2026-10-28']
print('RECENT_BOARD',len(recent),collections.Counter(x['status'] for x in recent))
print('RECENT_MISSING_PENDING',[(x['sha'],x['slug'],x['status'],x['pending_id']) for x in recent if x.get('pending_id') and x['pending_id'] not in pending][:20])
print('RECENT_BOARD_PENDING_STATUS_MISMATCH',[(x['sha'],x['slug'],x['status'],x['pending_id'],pending[x['pending_id']]['status']) for x in recent if x.get('pending_id') in pending and x['status']!=pending[x['pending_id']]['status']][:30])
print('RECENT_RUNNING_NO_PENDING',[(x['sha'],x['slug'],x['step']) for x in recent if x['status']=='running' and not x.get('pending_id')][:20])
print('CURRENT_BOARD_RUNNING',[(x['sha'],x['slug'],x['step'],x.get('pending_id')) for x in board if x['status']=='running'])
print('CURRENT_PENDING_RUNNING',[(p['id'],p['title']) for p in pending.values() if p['status']=='running'])
print('REGISTRY_STAGES',collections.Counter((t.get('pipeline') or {}).get('stage') for t in tasks.values()))
print('BOARD_SLUGS_ABSENT_REGISTRY',[(s, len([x for x in board if x['slug']==s])) for s in sorted({x['slug'] for x in board}-set(tasks))])
con.close()
con=sqlite3.connect(f'file:{D}?mode=ro',uri=True)
con.row_factory=sqlite3.Row
parts=[dict(r) for r in con.execute('select id,time_created,data from part where session_id=? order by time_created,id',(SID,))]
print('MASTER_PARTS',len(parts))
comp=[]
for i,r in enumerate(parts):
 o=json.loads(r['data'])
 if o.get('type')=='compaction':
  comp.append((i,r['id'],r['time_created'],o))
print('COMPACTIONS',len(comp))
for i,pid,ms,o in comp:
 print('COMPACTION',pid,datetime.datetime.fromtimestamp(ms/1000,datetime.timezone.utc).isoformat(),json.dumps(o)[:500])
 for r in parts[i+1:i+9]:
  p=json.loads(r['data']); typ=p.get('type'); t=p.get('text','')
  if typ=='tool':
   s=p.get('state',{}); inp=s.get('input',{}); t=str(inp.get('command',inp.get('cmd',inp)))[:350]
  print('AFTER',r['id'],typ,t[:450].replace('\n',' '))
con.close()
