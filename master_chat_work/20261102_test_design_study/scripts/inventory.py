import ast,csv,json,pathlib,re,subprocess,tomllib
ROOT=pathlib.Path('/Users/mac/Desktop/Terminal Bench/anubis-stage-2')
OUT=pathlib.Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/20261102_test_design_study')
def chunks(p):
 with p.open('r',encoding='utf-8',errors='replace') as f:
  while s:=f.read(50000): yield s
def read(p): return ''.join(chunks(p)) if p.exists() else ''
def data(p):
 try: return json.loads(read(p))
 except: return {}
def band(x):
 if x>=.875:return 'Trivial'
 if x>=.5:return 'Easy'
 if x>=.375:return 'Medium'
 if x>=.25:return 'Hard'
 return 'Expert'
def kind(c,stdout):
 name=c.get('name','')
 lines=[line.lower() for line in stdout.splitlines() if ('_check_'+name.lower()) in line.lower() or name.lower()+':' in line.lower()]
 if not lines:return 'UNRESOLVED'
 line=lines[0]
 if 'timed out' in line or 'timeout' in line:return 'TIMEOUT'
 if 'not published' in line or 'missing file' in line:return 'MISSING_FILE'
 if 'did not finish cleanly' in line:return 'RUN_FAILURE_UNKNOWN'
 if 'traceback' in line or 'exception' in line:return 'CRASH'
 if 'format' in line or 'parse' in line:return 'FORMAT'
 return 'WRONG'
def generated_by_code(code, criteria):
 try: tree=ast.parse(code)
 except SyntaxError:return set()
 defs={n.name:n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
 calls={}
 for name,node in defs.items():
  calls[name]={c.func.id for c in ast.walk(node) if isinstance(c,ast.Call) and isinstance(c.func,ast.Name)}
 def reaches(name,seen=None):
  seen=set() if seen is None else seen
  if name in seen:return False
  seen.add(name)
  if re.search(r'hidden|held.?out|_Ggenerate|_regenerate|_planted|_case_make_data|_fresh',name,re.I):return True
  return any(reaches(child,seen) for child in calls.get(name,()) if child in defs)
 result=set()
 for c in criteria:
  name=c['name']
  if re.search(r'hidden|held.?out|unseen|fresh|corpus|next.month|other.extract',name+' '+c.get('description',''),re.I):result.add(name);continue
  for candidate in (name,'_'+name,'_check_'+name,'_impl_'+name,'test_'+name):
   if candidate in defs and reaches(candidate):result.add(name);break
 return result

def main():
 changed=set()
 raw=subprocess.run(['git','-C',str(ROOT),'log','--since=2026-10-28 00:00:00','--name-only','--format='],capture_output=True,text=True,check=True).stdout
 for line in raw.splitlines():
  if re.match(r'^[0-9a-f-]{36}/',line):changed.add(line.split('/')[0])
 rows=[];details={}
 for task in sorted(p for p in ROOT.iterdir() if p.is_dir() and re.fullmatch('[0-9a-f-]{36}',p.name)):
  t=tomllib.loads(read(task/'task.toml'))
  v=task/'trajectories/claude-opus-5/run_1/verifier'
  d=data(v/'reward-details.json').get('reward',{})
  comps={c.get('name'):c for c in d.get('components',[])}
  tests=comps.get('test_output',{}).get('detail',{}).get('criteria',[])
  judge=comps.get('judge',{}).get('detail',{}).get('criteria',[])
  tw=sum(max(0,c.get('weight',0)) for c in tests)
  passed=sum(max(0,c.get('weight',0))*float(c.get('value',0)) for c in tests)
  fail=[c for c in tests if c.get('weight',0)>0 and float(c.get('value',0))<1]
  neg=[c for c in tests if c.get('weight',0)<0 and float(c.get('value',0))>0]
  stdout=read(v/'test-stdout.txt')
  hidden=[c for c in tests if c.get('weight',0)>0 and re.search('hidden|unseen|generated|synthetic|fresh|rerun|seed|new corpus|held.out|random|large|stress|other input',c.get('name','')+' '+c.get('description',''),re.I)]
  hw=sum(c['weight'] for c in hidden);hp=sum(c['weight']*float(c.get('value',0)) for c in hidden)
  lost={k:0 for k in ['WRONG','TIMEOUT','CRASH','MISSING_FILE','FORMAT','RUN_FAILURE_UNKNOWN','UNRESOLVED','NEGATIVE_FIRED']}
  for c in fail: lost[kind(c,stdout)]+=c['weight']*(1-float(c.get('value',0)))
  lost['NEGATIVE_FIRED']=sum(-c['weight']*float(c.get('value',0)) for c in neg)
  code=read(task/'tests/test_output.py')
  gen_names=generated_by_code(code,tests)
  codehidden=[c for c in tests if c.get('weight',0)>0 and c['name'] in gen_names]
  chw=sum(c['weight'] for c in codehidden); chp=sum(c['weight']*float(c.get('value',0)) for c in codehidden)
  timeouts=sorted(set(re.findall(r'(?:timeout(?:_sec)?\s*[=:]\s*|timeout\s*\(\s*)(\d+(?:\.\d+)?)',code,re.I)),key=float)
  authors='; '.join(a['name'] for a in t['task'].get('authors',[]))
  score=float(d.get('score',data(v/'reward.json').get('reward',0)) or 0)
  parts={k:round(float(comps[k].get('weight',0))*float(comps[k].get('detail',{}).get('score',0))*100,3) if k in comps else '' for k in ['test_output','judge']}
  row=dict(id=task.name,id8=task.name[:8],author=authors,band=band(score),final_score=round(score*100,3),test_contribution=parts['test_output'],judge_contribution=parts['judge'],test_count=len(tests),positive_test_weight=tw,passed_positive_weight=round(passed,4),lost_positive_weight=round(tw-passed,4),lost_pct=round((tw-passed)/tw*100,3) if tw else 0,hidden_named_weight=hw,hidden_named_share_pct=round(hw/tw*100,3) if tw else '',hidden_named_pass_pct=round(hp/hw*100,3) if hw else '',hidden_estimate='criterion-name lower bound; static code reach estimate also heuristic',hidden_code_est_weight=chw,hidden_code_est_share_pct=round(chw/tw*100,3) if tw else 0,hidden_code_est_pass_pct=round(chp/chw*100,3) if chw else 0,negative_weight=sum(-min(0,c.get('weight',0)) for c in tests),timeout_literals_sec=';'.join(timeouts),judge_count=len(judge),judge_positive_weight=sum(max(0,c.get('weight',0)) for c in judge),changed_since_28oct=task.name in changed,stdout_bytes=(v/'test-stdout.txt').stat().st_size if (v/'test-stdout.txt').exists() else 0,**{f'lost_{k.lower()}_weight':round(val,4) for k,val in lost.items()})
  rows.append(row)
  details[task.name]={'row':row,'failed':fail,'negative':neg,'stdout':stdout[:2000]}
 with (OUT/'inventory.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 qual=[r for r in rows if r['band'] in ('Hard','Expert') and r['lost_pct']>=30]
 medium=sorted((r for r in rows if r['band']=='Medium'),key=lambda r:r['lost_pct'],reverse=True)[:3]
 new=[r for r in rows if r['changed_since_28oct'] and r['lost_pct']>=30]
 allq={r['id']:r for r in qual+medium+new}
 selected=sorted(allq.values(),key=lambda r:r['lost_pct'],reverse=True)[:25]
 (OUT/'scratch/selection.json').write_text(json.dumps(dict(hard_expert=[r['id8'] for r in qual],medium_top3=[r['id8'] for r in medium],new=[r['id8'] for r in new],selected=[r['id8'] for r in selected],omitted=[r['id8'] for r in sorted(allq.values(),key=lambda r:r['lost_pct'],reverse=True)[25:]]),indent=2))
 (OUT/'scratch/details.json').write_text(json.dumps(details))
 print('tasks',len(rows),'hard_expert',len(qual),'medium',len(medium),'new',len(new),'selected',len(selected),'omitted',max(0,len(allq)-25))
 for r in selected:print(r['id8'],r['author'].split(';')[0],r['band'],r['lost_pct'],r['positive_test_weight'],r['test_contribution'],r['judge_contribution'])
if __name__=='__main__':main()
