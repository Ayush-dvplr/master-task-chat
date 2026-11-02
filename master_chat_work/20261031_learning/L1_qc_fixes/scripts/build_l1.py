#!/usr/bin/env python3
"""Read-only QC report/fix-note indexer. Writes only beside this script's parent."""
from pathlib import Path
from collections import Counter,defaultdict
import csv,re,json
TB=Path('/Users/mac/Desktop/Terminal Bench'); OUT=Path(__file__).resolve().parents[1]
reports=sorted((TB/'QC/reports').glob('*/v*.md'),key=lambda p:(p.parent.name,int(p.stem[1:])))
notes=list((TB/'master_chat_work').glob('*/p12_fix_*/RECHECK_FIX.md'))
CODE=re.compile(r'\b(?:IN(?:-L\d+|-\d+)|DS-\d+(?:-\d+|[a-z])?|TS-(?:DOC|\d+(?:-\d+|[a-z])?)|JD-\d+(?:-\d+)?|AL-(?:F0[a-e]|\d+(?:-\d+|[a-z])?)|CL-\d+|COV-\d+|EXEC-\d+|X\d+|S5|F0[a-e]|W-\d+-\d+)\b')
PATH=re.compile(r'(?<![\w/])(?:environment/|solution/|tests/|instruction\.md|task\.toml|reward\.toml|judge\.toml|test_output\.py|TRUTH\.md|solve\.py|[A-Za-z][\w.-]+\.(?:md|py|toml|txt|csv|json|conf|ini|yml|yaml|xml|cfg))[^\s,;|)]*?(?::L?\d+(?:-L?\d+)?)?(?=[\s,;|)]|$)')

def clean(s):
 s=re.sub(r'\*\*|`','',s);s=re.sub(r'\s+',' ',s)
 return s.strip(' -:')
def section(lines):
 ix=next((i for i,l in enumerate(lines) if re.match(r'^#{2,3} Findings(?:\b|\s|$)',l)),None)
 if ix is None:return []
 n=2 if lines[ix].startswith('## ') else 3
 out=[]
 for l in lines[ix+1:]:
  if re.match(r'^#{1,'+str(n)+r'} ',l) and not re.match(r'^###? (?:❌|🟡|⚠️|Fails?|Minors?|Warns?|Acknowledged)',l,re.I):break
  if re.match(r'^###? (?:Acknowledged|Carry.over|Consolidated sign.off)',l,re.I):break
  if re.match(r'^Acknowledged \(carry.over\)|^Notes: grading',l,re.I):break
  out.append(l)
 return out

def candidates(lines):
 result=[];heading=''
 for i,l in enumerate(lines):
  if l.startswith('#'):heading=l;continue
  if re.match(r'^(?:Fails?|Minors?|Warns?)\b',l,re.I) or re.match(r'^[❌🟡⚠].*\b(?:fail|minor|warn)\b',l,re.I):heading=l;continue
  if re.match(r'^\s*(?:No findings|None\b)',l,re.I):continue
  m=re.match(r'^\s*(?:[-*]|\d+\.)\s+(.+)',l)
  if not m:m=re.match(r'^\s*(\*\*(?:G\d\d|F-?\d|(?:IN|DS|TS|JD|AL|CL)-)[^*]*\*\*.*)',l)
  if not m:continue
  body=m.group(1)
  if re.match(r'(?i)(?:fix|evidence|file(?: and line)?|quote|reason|status|decision|suggestion|changed|acknowledged|step 10|x1|a3)\s*:',body):continue
  if not (re.search(r'[❌🟡⚠]|\b(?:G\d\d|F-?\d|Gate \d\d|IN-|DS-|TS-|JD-|AL-|CL-)\b',body) or CODE.search(body)):continue
  if 'acknowledged' in heading.lower() or 'carry-over' in heading.lower():continue
  if re.search(r'\b(?:not yet shown to the tasker|earlier reason)\b',body,re.I):continue
  if re.search(r'\b(?:fixed|resolved|now pass|carry.over)\b',body[:75],re.I) and not re.search(r'[❌🟡⚠]',body[:35]):continue
  if 'acknowledged' in body[:120].lower() and not re.search(r'[❌🟡⚠]',body[:35]):continue
  result.append((i,body,heading))
 return result

def severity(s,h):
 t=s[:100].lower();h=h.lower()
 if '❌' in t or re.search(r'\bfail\b',t):return '❌'
 if '🟡' in t or re.search(r'\bminor\b',t) or 'minor' in h:return 'minor'
 if '⚠' in t or re.search(r'\bwarn\b',t) or 'warn' in h:return 'warn'
 if 'fail' in h:return '❌'
 return 'UNVERIFIED'

def locs(s):
 # retain directly named file:line as printed; strip Markdown punctuation
 arr=[]
 for x in PATH.findall(s):
  x=x.strip('`".');
  if ':' in x or '/' in x or x in ('instruction.md','task.toml'):arr.append(x)
 return list(dict.fromkeys(arr))[:8]

def primary(s):
 z=CODE.findall(s[:180]);return z[0] if z else 'UNVERIFIED'

def keyplace(s):
 z=locs(s)
 return re.sub(r':L?\d+(?:-L?\d+)?','',z[0]) if z else ''

def words(s):
 return set(re.findall(r'[a-z]{4,}',clean(s).lower()))-{'gate','file','line','with','from','that','this','under','also','same','fix','test','tests','solution','agent','code','error','check','rule','what','when','which','where'}

bytask=defaultdict(dict);rows=[];parse_issues=[]
for p in reports:
 lines=p.read_text(errors='replace').splitlines(); sec=section(lines); ver=int(p.stem[1:]); task=p.parent.name
 if not sec and not re.search(r'(?:0 fails?, 0 minors?, 0 warns?|\bPASS\b)', '\n'.join(lines[:40]),re.I):parse_issues.append(str(p))
 for ix,body,head in candidates(sec):
  # Convert a few long lines to one-line problem and retain report evidence.
  ident=re.search(r'\b(?:G\d\d-[MW]?\d+|F-\d\d-\d+|F-\d\d|F\d+)(?:\b|(?=\s))',body)
  row=dict(task=task,report_version=f'v{ver}',finding_id=ident.group(0) if ident else '',check_id=primary(body),severity=severity(body,head),problem=clean(body)[:420],named_file_line='; '.join(locs(body)),report_evidence='',status_next='',next_evidence='',fix_note='',edit='')
  # determine exact line by matching body after section header, even if repeated
  row['report_evidence']=f'{p}:{next((j+1 for j,x in enumerate(lines) if x.strip().endswith(body)),0)}'
  rows.append(row)
 bytask[task][ver]=lines

# P12 notes are indexed to the QC version they explicitly follow.
fixes=defaultdict(list)
for p in notes:
 m=re.search(r'p12_fix_v(\d+)',str(p.parent));
 if not m:continue
 task=p.parent.parent.name;task=re.sub(r'^\d{8}_','',task)
 s=p.read_text(errors='replace'); files=[]
 change_lines=[]
 for l in s.splitlines():
  if re.search(r'^(?:Changed files|Files changed):|^\| Changed hunk|^\| files changed',l,re.I):change_lines.append(l.split('Not touched:',1)[0])
  elif re.search(r'^\|[^\n]*\| FIX(?:\s|:|\()',l,re.I):change_lines.append(l.rsplit('|',2)[-2])
 for x in re.findall(r'(?:environment|solution|tests)/[\w./-]+|\binstruction\.md\b|\btask\.toml\b','\n'.join(change_lines)):
  x=x.rstrip('.,:');
  if x not in files:files.append(x)
 header=next((l for l in s.splitlines() if re.search(r'^(?:Changed files|Files changed):',l,re.I)),'')
 decisions=[]
 file_edits=[]
 for l in s.splitlines():
  mfix=re.search(r'\|\s*(FIX(?:\s|:|\()[^|]{0,230})\|',l,re.I)
  if mfix and not re.match(r'FIX\s+(?:id|label)\b',mfix.group(1),re.I):
   d=clean(mfix.group(1));decisions.append(d)
   file_edits.append((re.findall(r'(?:environment|solution|tests)/[\w./-]+|\binstruction\.md\b|\btask\.toml\b',l.rsplit('|',2)[-2]),d))
 if not decisions and '## The fix' in s:
  tail=s.split('## The fix',1)[1].splitlines()
  decisions=[clean(l) for l in tail if l.strip() and not l.startswith('#')][:1]
 detail='; '.join(decisions) if decisions else header
 fixes[(task,int(m.group(1)))].append(dict(path=p,sha=p.parent.name.rsplit('_',1)[-1],files=files,edit=clean(detail)[:350],file_edits=file_edits))

# Changed paths in the new report, particularly its Changed hunk/Compared sections.
def changed_paths(lines):
 out=[];active=False
 for l in lines:
  if re.search(r'^\| Changed hunk|^Changed files\s*:|^\| File changed|^\| Changed file',l,re.I):active=True
  elif active and (l.startswith('##') or (not l.strip())):active=False
  if active:
   target=l.split('|')[1] if l.startswith('|') and '|' in l[1:] else l.split('Not touched:',1)[0]
   for x in re.findall(r'(?:environment|solution|tests)/[\w.-]+(?:/[\w.-]+)*|\binstruction\.md\b|\btask\.toml\b',target):
    if x not in out:out.append(x)
 return out

def changed_edit(lines,paths):
 for l in lines:
  if not l.startswith('|'):continue
  cells=[x.strip() for x in l.strip('|').split('|')]
  if len(cells)<2:continue
  if any(normpath(p) in {normpath(x) for x in re.findall(r'(?:environment|solution|tests)/[\w./-]+|\binstruction\.md\b|\btask\.toml\b',cells[0])} for p in paths):
   return clean(cells[0]+' '+cells[1])[:240]
 return ''

def normpath(p):return p.rsplit('/',1)[-1].split(':')[0]
def match(a,b):
 if a['check_id']!=b['check_id'] or a['check_id']=='UNVERIFIED':return -1
 wa,wb=words(a['problem']),words(b['problem']);sim=len(wa&wb)/max(1,len(wa|wb))
 same=keyplace(a['problem']) and keyplace(a['problem'])==keyplace(b['problem'])
 return sim+(0.45 if same else 0)

for task,vers in bytask.items():
 for v in sorted(vers):
  prev=[r for r in rows if r['task']==task and r['report_version']==f'v{v}']
  nxt=[r for r in rows if r['task']==task and r['report_version']==f'v{v+1}']
  if v+1 not in vers:
   for a in prev:a['status_next']='NOT RECHECKED'
   continue
  used=set()
  for a in prev:
   ranked=sorted(((match(a,b),i,b) for i,b in enumerate(nxt) if i not in used),reverse=True,key=lambda z:z[0])
   if ranked and ranked[0][0]>=0.18:
    _,i,b=ranked[0];used.add(i)
    a['status_next']='CAME BACK' if keyplace(a['problem'])==keyplace(b['problem']) and keyplace(a['problem']) else 'MOVED'
    a['next_evidence']=b['report_evidence']
   else:
    compare='\n'.join(vers[v+1]);compare=compare[compare.find('## Compared with'):] if '## Compared with' in compare else ''
    a['status_next']='FIXED' if re.search(re.escape(a['check_id'])+r'[^\n]{0,130}\b(?:fixed|resolved|closed|pass)\b',compare,re.I) else 'NOT RECHECKED'
    pos=next((j for j,l in enumerate(vers[v+1],1) if re.search(re.escape(a['check_id'])+r'[^\n]{0,130}\b(?:fixed|resolved|closed|pass)\b',l,re.I)),1)
    a['next_evidence']=f'{TB}/QC/reports/{task}/v{v+1}.md:{pos}'
   fs=fixes.get((task,v),[])
   if fs:
    a['fix_note']='; '.join(str(x['path']) for x in fs)
    a['edit']='; '.join(x['edit'] for x in fs)[:350]

# A recorded KEEP or rebuttal overrides a naive same-ID recurrence.
for a in rows:
 task=a['task'];v=int(a['report_version'][1:])
 if v+1 not in bytask[task]:continue
 docs=[]
 for base in (TB/'master_chat_work').glob(f'*/p12_fix_v{v}*'):
  if re.sub(r'^\d{8}_','',base.parent.name)!=task:continue
  docs += [base/n for n in ('KEPT.md','PL_NOTE.md') if (base/n).exists()]
 qc_keep=TB/'QC/reports'/task/'KEPT.md'
 if qc_keep.exists():docs.append(qc_keep)
 next_ack=any(re.search(re.escape(a['check_id'])+r'[^\n]{0,100}\b(?:acknowledged|carry.over|KEPT|REBUT)\b|\b(?:acknowledged|carry.over|KEPT|REBUT)\b[^\n]{0,100}'+re.escape(a['check_id']),l,re.I) for l in bytask[task][v+1]) if a['check_id']!='UNVERIFIED' else False
 for p in docs:
  for j,l in enumerate(p.read_text(errors='replace').splitlines(),1):
   idhit=bool(a['finding_id'] and re.search(r'(?<!\w)'+re.escape(a['finding_id'])+r'(?!\w)',l))
   codehit=bool(a['check_id']!='UNVERIFIED' and re.search(r'(?<!\w)'+re.escape(a['check_id'])+r'(?!\w)',l) and next_ack)
   if not (idhit or codehit):continue
   if a['status_next']=='FIXED' and not idhit:continue
   if p.name=='PL_NOTE.md' and not re.search(r'\b(?:kept|keep|rebut)\b',l,re.I):continue
   if p==qc_keep and not next_ack:continue
   a['status_next']='REBUTTED' if re.search(r'\bREBUT\b',l,re.I) else 'KEPT'
   a['next_evidence']=f'{p}:{j}'
   break
  if a['status_next'] in ('REBUTTED','KEPT'):break

# New rows are those unmatched to preceding report; effects require edited-file match.
effects=[]
for task,vers in bytask.items():
 for v in sorted(vers):
  if v-1 not in vers:continue
  old=[r for r in rows if r['task']==task and r['report_version']==f'v{v-1}']
  new=[r for r in rows if r['task']==task and r['report_version']==f'v{v}']
  matched={r['next_evidence'] for r in old if r['status_next'] in ('CAME BACK','MOVED')}
  fs=fixes.get((task,v-1),[])
  changed=changed_paths(vers[v])
  for x in fs:
   for y in x['files']:
    if y not in changed:changed.append(y)
  for b in new:
   if b['report_evidence'] in matched:continue
   bfiles={normpath(x) for x in locs(b['problem'])}
   common=[x for x in changed if normpath(x) in bfiles]
   if not common:continue
   sha='; '.join(x['sha'] for x in fs if re.fullmatch(r'[0-9a-f]{7,40}',x['sha'])) or 'UNVERIFIED'
   targeted=[]
   for x in fs:
    targeted += [d for paths,d in x['file_edits'] if any(normpath(z) in {normpath(y) for y in common} for z in paths)]
   edit='; '.join(dict.fromkeys(targeted))[:300] if targeted else changed_edit(vers[v],common) or ('; '.join(x['edit'] for x in fs)[:220] if fs else f'changed path named in v{v} report')
   effects.append(dict(task=task,from_round=f'v{v-1}',to_round=f'v{v}',fix_sha=sha,edit=edit,new_finding_id=b['finding_id'],new_check_id=b['check_id'],new_severity=b['severity'],matched_file='; '.join(common),why_linked='NEW finding; named path matches changed path (temporal/path association, not proven code causality)',finding_evidence=b['report_evidence'],fix_evidence='; '.join(str(x['path']) for x in fs) if fs else f'{TB}/QC/reports/{task}/v{v}.md'))

# Explicit comparisons identify edits that a generic changed-hunk table misses.
# These are still operational links, not isolated causal experiments.
curated=[
 ('cold-chain-backbone-quote',4,5,'DS-22','solution/TRUTH.md','TRUTH corridor-span rewrite also tightened a cold-room range to 31 while an earlier line says 30',390),
 ('cold-chain-backbone-quote',4,5,'TS-23','tests/test_output.py','21 wide checks added; total rose from 33 to 54',391),
 ('cohort-retention-reconciliation',4,5,'DS-22','solution/TRUTH.md','provenance rewrite fixed old sha but left new refund wording mismatch',378),
 ('cohort-retention-reconciliation',4,5,'AL-27','tests/test_output.py','new fixtures fixed several branches but left and exposed other untriggered branches',379),
 ('district-heat-flex-procurement',9,10,'TS-14','tests/test_output.py','import negative narrowed to third-party imports; name still says _or_network',393),
 ('tariff-engine-audit-repair',2,3,'DS-22','solution/TRUTH.md','statement generator changed; Verification prose stayed on old statement grading',272),
 ('tariff-engine-audit-repair',2,3,'TS-11','tests/test_output.py','new scale/batch/cycle checks added with a 10-second wall bound',272),
 ('tariff-engine-audit-repair',2,3,'TS-20','tests/test_output.py','new statement checks put 369 of 670 points on one channel',272),
 ('tariff-engine-audit-repair',2,3,'TS-26','tests/test_output.py','batch and cycle statement groups reuse plain group with seed changes',272),
 ('b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042',1,2,'CL-5','environment/data/output_contract.md','changed output contract still omits null sort placement',374),
]
for task,oldv,newv,code,path,edit,line in curated:
 if any(x['task']==task and x['to_round']==f'v{newv}' and x['new_check_id']==code for x in effects):continue
 b=next((x for x in rows if x['task']==task and x['report_version']==f'v{newv}' and x['check_id']==code),None)
 if not b:continue
 effects.append(dict(task=task,from_round=f'v{oldv}',to_round=f'v{newv}',fix_sha='UNVERIFIED',edit=edit,new_finding_id=b['finding_id'],new_check_id=code,new_severity=b['severity'],matched_file=path,why_linked='New or newly exposed issue named in report comparison; same edited file/criterion (INFERRED fix effect)',finding_evidence=b['report_evidence'],fix_evidence=f'{TB}/QC/reports/{task}/v{newv}.md:{line}'))

with (OUT/'QC_FINDINGS.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
with (OUT/'FIX_EFFECTS.csv').open('w',newline='') as f:
 fields=['task','from_round','to_round','fix_sha','edit','new_finding_id','new_check_id','new_severity','matched_file','why_linked','finding_evidence','fix_evidence'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(effects)
summary={'reports':len(reports),'tasks':len(bytask),'findings':len(rows),'effects':len(effects),'severity':dict(Counter(r['severity'] for r in rows)),'status':dict(Counter(r['status_next'] for r in rows)),'check_tasks':Counter({k:len({r['task'] for r in rows if r['check_id']==k}) for k in {r['check_id'] for r in rows}}).most_common(30),'rounds':{k:len(v) for k,v in bytask.items()},'parse_issues':parse_issues,'notes':len(notes)}
(OUT/'parse_summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
