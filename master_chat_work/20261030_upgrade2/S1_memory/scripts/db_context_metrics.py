import sqlite3,json,re,collections,datetime,pathlib,statistics
D=pathlib.Path('/Users/mac/.local/share/opencode/opencode.db'); SID='ses_ea5ff5f97ffe6WB1VzP4StPOw6'
c=sqlite3.connect(f'file:{D}?mode=ro',uri=True)
rows=[(r[0],r[1],json.loads(r[2])) for r in c.execute('select id,time_created,data from part where session_id=? order by time_created,id',(SID,))]
comp=[i for i,r in enumerate(rows) if r[2].get('type')=='compaction']
pat=re.compile(r'(?:master_chat_tasks/(?:README\.md|GOALS\.md|state\.json|feedback\.jsonl|decisions\.jsonl|knowledge/INDEX\.md|knowledge/KNOWLEDGE\.md)|Input_Bundle_QC/(?:Starter\.md|Final_checklist\.md))')
def cmd(o):
 if o.get('type')!='tool':return ''
 s=o.get('state') or {}; inp=s.get('input') or {}
 return str(inp.get('command',inp.get('cmd',inp)))
def names(seq):
 return collections.Counter(n for _,_,o in seq for n in set(pat.findall(cmd(o))))
print('SUMMARY_LENGTHS')
for j,i in enumerate(comp):
 summary=next((o.get('text','') for _,_,o in rows[i+1:i+9] if o.get('type')=='text' and o.get('text','').startswith('## Objective')),'')
 print(j+1,rows[i][0],len(summary),'chars',len(summary.split()),'words')
 before=names(rows[max(0,i-300):i]); after=names(rows[i+1:i+301])
 print('BEFORE',before.most_common(8))
 print('AFTER',after.most_common(8))
 print('RE_READS',[(k,v,before[k]) for k,v in after.items() if before[k]])
 print('FIRST_READS',[(r[0],sorted(set(pat.findall(cmd(r[2]))))) for r in rows[i+1:i+80] if pat.search(cmd(r[2]))][:6])
print('TOOL_OUTPUT_METRICS')
for lo,hi,label in [(0,len(rows),'all'),(0,comp[-1]+1,'to_last_compaction'),(comp[-1]+1,len(rows),'after_last_compaction')]:
 tool=[o for _,_,o in rows[lo:hi] if o.get('type')=='tool']
 outs=[len(str((o.get('state') or {}).get('output',''))) for o in tool]
 cmds=[cmd(o) for o in tool]
 rule_reads=[(x,y) for x,y in zip(cmds,outs) if pat.search(x)]
 print(label,'tool_calls',len(tool),'output_chars',sum(outs),'outputs_gt_10000',sum(x>10000 for x in outs),'rule_read_calls',len(rule_reads),'rule_output_chars',sum(y for x,y in rule_reads))
 print('TOP_RULES',collections.Counter(n for x,y in rule_reads for n in set(pat.findall(x))).most_common(12))
print('ALL_SESSION_MESSAGES',c.execute('select count(*) from message where session_id=?',(SID,)).fetchone()[0])
c.close()
