#!/usr/bin/env python3
"""Print a redacted worker transcript timeline from the read-only OpenCode DB."""
import json, re, sqlite3, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
IST=timezone(timedelta(hours=5, minutes=30))
db=sqlite3.connect(f"file:{Path.home() / '.local/share/opencode/opencode.db'}?mode=ro",uri=True)
db.execute('pragma query_only=1')
sha=sys.argv[1]
lo=sys.argv[2] if len(sys.argv)>2 else '0000-00-00 00:00'
hi=sys.argv[3] if len(sys.argv)>3 else '9999-99-99 99:99'
sidrow=db.execute('select id from session where title=? order by time_created desc limit 1',(sha,)).fetchone()
if not sidrow: raise SystemExit('no session')
sid=sidrow[0]
def fmt(t):return datetime.fromtimestamp(t/1000,IST).strftime('%Y-%m-%d %H:%M:%S')
def safe(s):
    s=re.sub(r'(?i)(api[_-]?key|token|password|secret|authorization)[^\s,;]{0,80}','[REDACTED]',str(s))
    return re.sub(r'\s+',' ',s).strip()[:230]
for mid,t,raw in db.execute('select id,time_created,data from message where session_id=? order by time_created,id',(sid,)):
    if not lo<=fmt(t)<=hi:continue
    m=json.loads(raw)
    parts=[json.loads(x[0]) for x in db.execute('select data from part where message_id=? order by time_created,id',(mid,))]
    texts=[safe(p.get('text','')) for p in parts if p.get('type')=='text' and p.get('text')]
    tools=[]
    for p in parts:
        if p.get('type')!='tool':continue
        st=p.get('state') or {};c=(st.get('input') or {}).get('command') or ''
        ti=st.get('time') or {}
        tools.append(f"{p.get('tool')} {st.get('status')} {fmt(ti.get('start')) if ti.get('start') else ''}-{fmt(ti.get('end')) if ti.get('end') else ''} {safe(c)}")
    print(fmt(t),m.get('role'),m.get('finish'),(m.get('error') or {}).get('name'), 'completed',fmt((m.get('time') or {}).get('completed')) if (m.get('time') or {}).get('completed') else '')
    for x in texts[-2:]:print('  TEXT',x)
    for x in tools[-3:]:print('  TOOL',x)
