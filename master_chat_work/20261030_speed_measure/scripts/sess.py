import sqlite3,csv,json,re,statistics as st
from datetime import datetime
db=sqlite3.connect('file:/Users/mac/.local/share/opencode/opencode.db?mode=ro',uri=True)
db.execute('pragma query_only=1')
sess=db.execute("select id,title,time_created,time_updated,agent,model from session where title glob '[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]' and parent_id is null").fetchall()
board={}
import json as j
for r in j.load(open('/Users/mac/Desktop/Terminal Bench/master_chat_tasks/board.json'))['rows']: board[r['sha']]=r
out=[];toolrows=[]
L=lambda ms: datetime.fromtimestamp(ms/1000).strftime('%Y-%m-%d %H:%M:%S')
for sid,title,tc,tu,ag,mo in sess:
    ms=[r[0] for r in db.execute("select time_created from message where session_id=? order by time_created",(sid,))]
    if not ms: continue
    gaps=[(b-a)/60000 for a,b in zip(ms,ms[1:])]
    big=[g for g in gaps if g>10]
    span=(ms[-1]-ms[0])/60000
    # tool parts
    tl=db.execute("""select json_extract(data,'$.tool'),json_extract(data,'$.state.time.start'),json_extract(data,'$.state.time.end'),json_extract(data,'$.state.input.command'),time_created from part where session_id=? and json_extract(data,'$.type')='tool'""",(sid,)).fetchall()
    tool_s=0;bash_s=0;poll_s=0;poll_n=0;docker_s=0;docker_n=0;ntool=len(tl);sleepcmd=0
    for tool,s,e,cmd,t in tl:
        if s is None or e is None: continue
        d=(e-s)/1000
        tool_s+=d
        if tool=='bash':
            bash_s+=d
            c=cmd or ''
            if re.search(r'\bsleep\s+\d+',c) and re.search(r'poll|docker ps|tail|result\.json',c):
                poll_s+=d;poll_n+=1
            if re.search(r'docker (ps|wait|logs)|harbor|docker run|docker build|docker compose|/run_gate|gate|oracle|verifier',c) and d>60:
                docker_s+=d;docker_n+=1
        toolrows.append([title,tool,L(s),round(d,1),(cmd or '')[:160].replace('\n',' ')]) if tool=='bash' and d>=120 else None
    b=board.get(title,{})
    out.append([title,b.get('slug',''),b.get('step','')[:50],L(ms[0]),L(ms[-1]),len(ms),round(span,1),len(big),round(sum(big),1),round(max(gaps) if gaps else 0,1),ntool,round(tool_s/60,1),round(bash_s/60,1),poll_n,round(poll_s/60,1),docker_n,round(docker_s/60,1)])
hdr=['sha','slug','board_step','first_msg','last_msg','n_msgs','span_min','n_gaps_gt10','sum_gaps_gt10_min','max_gap_min','n_tool_parts','tool_time_min','bash_time_min','n_sleep_poll_cmds','sleep_poll_min','n_long_docker_ish_cmds(>60s)','long_docker_ish_min']
csv.writer(open('opencode_sessions.csv','w')).writerows([hdr]+sorted(out,key=lambda r:r[3]))
csv.writer(open('opencode_long_bash_calls.csv','w')).writerows([['sha','tool','start','dur_s','cmd']]+[t for t in toolrows if t])
print(len(out))
