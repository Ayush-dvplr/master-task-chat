import sqlite3,sys,csv,json
from datetime import datetime
db=sqlite3.connect('file:/Users/mac/.local/share/opencode/opencode.db?mode=ro',uri=True); db.execute('pragma query_only=1')
L=lambda ms: datetime.fromtimestamp(ms/1000).strftime('%m-%d %H:%M')
rows=[]
for sha in sys.argv[1:]:
    sid=db.execute("select id from session where title=? and parent_id is null",(sha,)).fetchone()[0]
    ms=db.execute("select id,time_created,json_extract(data,'$.role') from message where session_id=? order by time_created",(sid,)).fetchall()
    for a,b in zip(ms,ms[1:]):
        g=(b[1]-a[1])/60000
        if g>10:
            # last text/tool before gap
            p=db.execute("select json_extract(data,'$.type'),json_extract(data,'$.tool'),substr(coalesce(json_extract(data,'$.text'),json_extract(data,'$.state.input.command'),''),1,200) from part where message_id=? order by id desc limit 1",(a[0],)).fetchone()
            q=db.execute("select json_extract(data,'$.type'),substr(coalesce(json_extract(data,'$.text'),''),1,200) from part where message_id=? order by id limit 1",(b[0],)).fetchone()
            rows.append([sha,L(a[1]),L(b[1]),round(g,1),a[2],str(p).replace('\n',' ')[:200],b[2],str(q).replace('\n',' ')[:200]])
            print(sha,L(a[1]),'->',L(b[1]),round(g,1),'| before:',a[2],str(p).replace('\n',' ')[:170],'| after:',b[2],str(q).replace('\n',' ')[:170])
