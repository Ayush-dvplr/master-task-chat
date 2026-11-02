#!/usr/bin/env python3
"""Create reviewed episode table; gap times are recalculated from the read-only DB."""
import csv,json,sqlite3
from datetime import datetime,timezone,timedelta
from pathlib import Path
OUT=Path(__file__).resolve().parent.parent
db=sqlite3.connect(f"file:{Path.home() / '.local/share/opencode/opencode.db'}?mode=ro",uri=True)
db.execute('pragma query_only=1')
IST=timezone(timedelta(hours=5,minutes=30))
def fmt(ms):return datetime.fromtimestamp(ms/1000,IST).strftime('%Y-%m-%d %H:%M:%S')
auto='master_chat_tasks/auto/runs/'
rows=[]
early=['361674d','9a85fdc','4e298da','f0331ad','217875e']
late=['361674d','7d4de68','4fef871','dcd21a3','f26bda6']
for episode,shas,run,trigger,wake,job in [
 ('A',early,'20261027T2239_overnight','shared worker progress gap; deliverables incomplete','tools resumed at 02:50; watcher delivered from 02:53',{'361674d':'incomplete design','9a85fdc':'incomplete fix','4e298da':'QC gate/report incomplete','f0331ad':'incomplete harden','217875e':'incomplete harden/gate'}),
 ('B',late,'20261027T2239_overnight','shared worker progress gap; deliverables incomplete','tools resumed at 07:50; watcher delivered from 07:52',{'361674d':'own Step 10 chain running','7d4de68':'QC only at setup','4fef871':'QC recheck incomplete','dcd21a3':'design incomplete','f26bda6':'QC recheck incomplete'})]:
 for sha in shas:
  data=db.execute("select m.id,m.time_created,min(json_extract(p.data,'$.state.time.start')) from session s join message m on m.session_id=s.id join part p on p.message_id=m.id where s.title=? and json_extract(p.data,'$.type')='tool' and json_extract(p.data,'$.state.time.start')-m.time_created>600000 group by m.id order by m.time_created",(sha,)).fetchall()
  mid,t,u=data[0 if episode=='A' else -1]
  rows.append([episode,'shared_progress_gap',run,sha,fmt(t),fmt(u),round((u-t)/60000,1),job[sha],wake,trigger,f'opencode.db session.title={sha} message.id={mid} -> part.state.time.start; {auto}{run}/events.jsonl', 'UNVERIFIED cause; no assistant final turn'])
def add(ep,kind,run,sha,start,end,mins,job,wake,quote,evidence,caveat=''):
 rows.append([ep,kind,run,sha,start,end,mins,job,wake,quote,evidence,caveat])
add('C','provider_limit_retry','20261027T0107_smoketest','t1smoke','2026-10-27 01:08:34','2026-10-27 01:14:00',5.4,'no deliverable; empty assistant response','Ayush stop/abort 01:14','"Sessions still show BUSY with an empty assistant message"',auto+'20261027T0107_smoketest/REPORT.md:4,14','Exact abort seconds UNVERIFIED')
add('C','provider_limit_retry','20261027T0107_smoketest','t2smoke','2026-10-27 01:08:34','2026-10-27 01:14:00',5.4,'no deliverable; empty assistant response','Ayush stop/abort 01:14','"never replied; aborted at 01:14"',auto+'20261027T0107_smoketest/REPORT.md:4,14','Exact abort seconds UNVERIFIED')
add('C2','provider_limit_retry','20261028T1553_evening','ac12c0b','2026-10-28 17:44:10','2026-10-28 18:55:00',70.8,'own Step 10 chain finished 18:42; QC report unfinished','Ayush stopped work at 18:55','"both workers stuck in retry"',auto+'20261028T1553_evening/REPORT.md:5,49','Stop exact seconds UNVERIFIED')
add('C2','provider_limit_retry','20261028T1553_evening','a4f790c','2026-10-28 17:43:40','2026-10-28 18:55:00',71.3,'cost containers still running; harden unfinished','Ayush stopped work at 18:55','"cost containers a4f790c_costA/B still running"',auto+'20261028T1553_evening/REPORT.md:5,49','Stop exact seconds UNVERIFIED')
add('C3','network_retry','20261029T0355_night','ed621c7','2026-10-29 04:39:26','2026-10-29 04:42:45',3.3,'diagnosis/build in progress','master continue 04:42:45','"PAUSED ed621c7: network"',auto+'20261029T0355_night/events.jsonl:18-19; opencode.db session.title=ed621c7 message.error.name=APIError')
add('D','doom_guard','20261028T1553_evening','ac12c0b','2026-10-28 16:53:25','2026-10-28 16:55:41',2.3,'own Step 10 chain still running','master send at 16:55:41','"same tool call repeated 3 times"',auto+'20261028T1553_evening/events.jsonl:9-10; opencode.db session.title=ac12c0b message.error.name=UnknownError')
add('E','doom_guard','20261029T0355_night','cc541be','2026-10-29 06:43:10','2026-10-29 06:44:23',1.2,'own Step 10 chain still running','watcher automatic continue 06:44:23','"same poll ran 3 times"',auto+'20261029T0355_night/events.jsonl:31-32; opencode.db session.title=cc541be message.error.name=UnknownError')
add('F','context_overflow','20261030T0100_night','6740572','2026-10-30 03:35:20','2026-10-30 03:36:44',1.4,'background score jobs running; build incomplete','external continue prompt 03:36:44','"ContextOverflowError" after compression #34','opencode.db session.title=6740572 message.error.name=ContextOverflowError; next user text','Tool transcript shows a synthetic continuation; sender UNVERIFIED')
add('G','manual_abort_with_children','20261030T0100_night','4989b35','2026-10-30 10:23:55','2026-10-30 11:31:03',67.1,'s3/s5/gate3 children ran until 10:27','master continue 11:31:03','"Master stopped this session at 10:23 ... killed your background scripts ... at 10:27"','opencode.db session.title=4989b35 next user text; '+auto+'20261030T0100_night/REPORT.md:35-38,100-108','Intentional stop; 67.1 min is continuation gap, not lost compute')
add('H','content_filter_stop','20261027T2239_overnight','361674d','2026-10-27 23:07:55','2026-10-27 23:08:16',0.3,'design incomplete','master corrective send 23:08:16','"ContentFilterError"',auto+'20261027T2239_overnight/events.jsonl:16-17; opencode.db session.title=361674d message.error.name=ContentFilterError')
with (OUT/'SLEEP_CASES.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['episode','root_cause_group','auto_run','sha','inactive_from_ist','next_action_ist','minutes','job_or_deliverable_state','what_woke_it','transcript_quote_or_signal','evidence','limits']);w.writerows(rows)
print('cases',len(rows),'shared',sum(r[1]=='shared_progress_gap' for r in rows))
