import sqlite3,csv,json,re
from datetime import datetime
db=sqlite3.connect('file:/Users/mac/.local/share/opencode/opencode.db?mode=ro',uri=True); db.execute('pragma query_only=1')
board={r['sha']:r for r in json.load(open('/Users/mac/Desktop/Terminal Bench/master_chat_tasks/board.json'))['rows']}
def union(iv):
    iv=sorted(iv);out=[]
    for s,e in iv:
        if out and s<=out[-1][1]: out[-1][1]=max(out[-1][1],e)
        else: out.append([s,e])
    return out
def tot(u): return sum(e-s for s,e in u)
def overlap(a,b,u):
    t=0
    for s,e in u:
        if e<=a: continue
        if s>=b: break
        t+=min(e,b)-max(s,a)
    return t
sess=db.execute("select id,title from session where title glob '[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]' and parent_id is null").fetchall()
res=[]
for sid,title in sess:
    ms=db.execute("select time_created,json_extract(data,'$.role') from message where session_id=? order by time_created",(sid,)).fetchall()
    if len(ms)<2: continue
    t0,t1=ms[0][0],ms[-1][0]
    poll=[];oth=[]
    for tool,s,e,cmd in db.execute("select json_extract(data,'$.tool'),json_extract(data,'$.state.time.start'),json_extract(data,'$.state.time.end'),json_extract(data,'$.state.input.command') from part where session_id=? and json_extract(data,'$.type')='tool'",(sid,)):
        if s is None or e is None or e<s: continue
        s=max(s,t0); e=min(e,t1+0)  # clip to session span
        if e<=s: continue
        c=cmd or ''
        if tool=='bash' and re.search(r'\bsleep\s+\d+',c) and re.search(r'poll|docker ps|tail|result\.json|echo|date',c): poll.append([s,e])
        else: oth.append([s,e])
    up=union(poll); uo=union(oth)
    ua=union(poll+oth)
    human=0;nh=0
    for a,b in zip(ms,ms[1:]):
        g=b[0]-a[0]
        if b[1]=='user' and g>180000:
            idle=g-overlap(a[0],b[0],ua)
            if idle>180000: human+=idle;nh+=1
    span=t1-t0
    pollt=tot(up)
    # other-tool minus any overlap with poll
    othonly=tot(union(poll+oth))-pollt
    resid=span-human-tot(ua)
    b=board.get(title,{})
    res.append([title,b.get('slug',''),datetime.fromtimestamp(t0/1000).strftime('%Y-%m-%d %H:%M'),round(span/60000,1),round(human/60000,1),nh,round(pollt/60000,1),round(othonly/60000,1),round(resid/60000,1)])
hdr=['sha','slug','first_msg','span_min','human_or_master_wait_min(gaps>3min before a user msg, not covered by tools)','n_such_waits','sleep_poll_tool_min(union)','other_tool_min(union)','model_gen_and_other_residual_min']
res.sort(key=lambda r:r[2])
csv.writer(open('opencode_wait_vs_work.csv','w')).writerows([hdr]+res)
import sys
for scope,flt in (('26-30 Oct',lambda r:r[2]>='2026-10-26'),('29-30 Oct',lambda r:r[2]>='2026-10-29'),('27-28 Oct',lambda r:'2026-10-27'<=r[2]<'2026-10-29')):
    R=[r for r in res if flt(r)]
    sp=sum(r[3] for r in R)
    print(scope,'sessions',len(R),'span h',round(sp/60,1),'human wait h',round(sum(r[4] for r in R)/60,1),'poll h',round(sum(r[6] for r in R)/60,1),'other tool h',round(sum(r[7] for r in R)/60,1),'resid h',round(sum(r[8] for r in R)/60,1))
for r in res:
    if r[0] in('ed621c7','b223662','6740572','4989b35','9111ecc','7d363c8','bdd41f8','a395eb2','145bdba','d21576c','0d8cf26'): print(r)
