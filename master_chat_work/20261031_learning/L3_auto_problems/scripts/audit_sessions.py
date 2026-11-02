#!/usr/bin/env python3
"""Read-only worker DB audit. Writes only alongside this script's parent OUT folder."""
import csv
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

TB = Path('/Users/mac/Desktop/Terminal Bench')
OUT = Path(__file__).resolve().parent.parent
DB = Path.home() / '.local/share/opencode/opencode.db'
IST = timezone(timedelta(hours=5, minutes=30))
con = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
con.execute('pragma query_only=1')
board = {x['sha']: x for x in json.loads((TB/'master_chat_tasks/board.json').read_text())['rows']}
states = {}
for f in sorted((TB/'master_chat_tasks/auto/runs').glob('*/state.json')):
    s = json.loads(f.read_text())
    for sha, w in s.get('workers', {}).items():
        states.setdefault(sha, []).append((f.parent.name, w))
session_rows = con.execute("select id,title,time_created,time_updated from session where parent_id is null and title glob '[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]' and time_created >= ? order by time_created", (int(datetime(2026,10,25,tzinfo=IST).timestamp()*1000),)).fetchall()
def iso(ms): return datetime.fromtimestamp(ms/1000, IST).strftime('%Y-%m-%d %H:%M:%S') if ms else ''
def clean(s):
    s = re.sub(r'(?i)(api[_-]?key|token|password|secret|authorization)[^\s,;]{0,60}', '[REDACTED]', str(s))
    return re.sub(r'\s+', ' ', s).strip()[:450]
poll_rows=[]; candidates=[]; summary=[]; final_turns=[]
for sid, sha, created, updated in session_rows:
    msgs = con.execute('select id,time_created,time_updated,data from message where session_id=? order by time_created,id', (sid,)).fetchall()
    parts = con.execute("select message_id,time_created,data from part where session_id=? and json_extract(data,'$.type') in ('text','tool','compaction') order by time_created,id", (sid,)).fetchall()
    bymsg=defaultdict(list)
    for mid, t, raw in parts: bymsg[mid].append((t,json.loads(raw)))
    polls=[]; repeated=0; prev_poll=None; all_tool=0; sleep_calls=0; sleep_ms=0; docker_ps=0; own=0; slot=0; unknown=0
    for mid,t,_,raw in msgs:
        m=json.loads(raw)
        for pt,p in bymsg[mid]:
            if p.get('type')!='tool': continue
            tool=p.get('tool',''); st=p.get('state') or {}; cmd=(st.get('input') or {}).get('command') or ''
            all_tool+=1
            start=(st.get('time') or {}).get('start') or pt
            end=(st.get('time') or {}).get('end') or start
            sleep=re.search(r'(?<![\w])sleep\s+([0-9]+)(?:\s|;|$)',cmd)
            if not sleep: continue
            sleep_calls+=1
            ms=max(0,end-start); sleep_ms+=ms
            if 'docker ps' in cmd: docker_ps+=1
            if prev_poll==cmd: repeated+=1
            prev_poll=cmd
            context=' '.join(x.get('text','') for _,x in bymsg[mid] if x.get('type')=='text').lower()
            # Session-level category: only explicit wording is counted as a slot wait.
            window=(cmd+' '+context).lower()
            if re.search(r'foreign container|other.{0,20}container|waiting.{0,20}slot|slot.{0,20}free|docker slot',window): cat='slot'; slot+=1
            elif re.search(r'own (?:job|chain|container)|gate|run\.log|lane|result\.json|tail|harbor|pid|nohup',window): cat='own_job'; own+=1
            else: cat='unclear'; unknown+=1
            polls.append((start,end,cmd,cat))
    total_poll_ms=sum(max(0,e-s) for s,e,_,_ in polls)
    run_names=','.join(x[0] for x in states.get(sha,[]))
    summary.append([sha,sid,board.get(sha,{}).get('slug',''),run_names,iso(created),len(msgs),all_tool,sleep_calls,round(sleep_ms/60000,1),round(total_poll_ms/60000,1),docker_ps,repeated,slot,own,unknown])
    for idx,(mid,t,upd,raw) in enumerate(msgs):
        m=json.loads(raw)
        if m.get('role')!='assistant' or not (m.get('time') or {}).get('completed') or m.get('finish')=='tool-calls': continue
        thistext=' '.join(p.get('text','') for _,p in bymsg[mid] if p.get('type')=='text')
        if not thistext: continue
        next_m=msgs[idx+1] if idx+1<len(msgs) else None
        next_t=next_m[1] if next_m else updated
        gap=max(0,next_t-((m.get('time') or {}).get('completed') or upd or t))
        if run_names:
            final_turns.append([sha,run_names,iso(t),iso(next_t),round(gap/60000,1),m.get('finish',''),(m.get('error') or {}).get('name',''),next_role,clean(thistext),clean(next_text)])
        if gap<10*60000: continue
        nearby_tools=[(p.get('state') or {}).get('input',{}).get('command','') for _,p in bymsg[mid] if p.get('type')=='tool']
        context=' '.join(nearby_tools[-3:])+' '+thistext
        if not re.search(r'(?i)nohup|background|running|poll|wait|continue|sleep|compact|retry|limit|docker|harbor|slot',context): continue
        next_text=''
        next_role=''
        if next_m:
            next_role=json.loads(next_m[3]).get('role','')
            next_text=' '.join(p.get('text','') for _,p in bymsg[next_m[0]] if p.get('type')=='text')
        candidates.append([sha,sid,run_names,iso(t),iso(next_t),round(gap/60000,1),m.get('finish',''),next_role,clean(thistext),clean(next_text)])
with (OUT/'POLL_STATS.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['sha','session_id','slug','auto_runs','created_ist','messages','tool_calls','sleep_calls','sleep_elapsed_min','poll_elapsed_min','docker_ps_sleep_calls','consecutive_identical_sleep_calls','explicit_slot_wait_calls','own_job_context_calls','unclear_calls']);w.writerows(summary)
with (OUT/'SLEEP_CANDIDATES.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['sha','session_id','auto_runs','assistant_at_ist','next_at_ist','idle_gap_min','finish','next_role','assistant_quote','next_quote']);w.writerows(candidates)
with (OUT/'FINAL_TURNS.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['sha','auto_runs','assistant_at_ist','next_at_ist','idle_gap_min','finish','error','next_role','assistant_quote','next_quote']);w.writerows(final_turns)
print('sessions',len(summary),'auto_linked',sum(bool(x[3]) for x in summary),'sleep_calls',sum(x[7] for x in summary),'sleep_elapsed_h',round(sum(x[8] for x in summary)/60,1),'candidates',len(candidates))
