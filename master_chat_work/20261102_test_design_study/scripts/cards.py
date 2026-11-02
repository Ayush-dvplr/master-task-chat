import csv,json,pathlib,re
ROOT=pathlib.Path('/Users/mac/Desktop/Terminal Bench/anubis-stage-2');OUT=pathlib.Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/20261102_test_design_study')
def read(p):
 if not p.exists():return ''
 with p.open(encoding='utf-8',errors='replace') as f:return ''.join(iter(lambda:f.read(50000),''))
def pick(lines,regex,avoid=None):
 for i,l in enumerate(lines,1):
  if re.search(regex,l,re.I) and (not avoid or not re.search(avoid,l,re.I)):return i,l.strip()
 return None,''
def trunc(s,n=180):return s.replace('|','\\|').replace('`',"'")[:n]
def quoted(p,ln,s):return f'`{p}:{ln}` “{trunc(s)}”'
SPECIAL={
 '59417607':('P1','Shipped exact checks pass; 18 hidden whole-report checks fail (TRUTH.md:54-59). The hidden generator changes handset offsets by day (TRUTH.md:25-37); record_dictionary.md:19 says a handset clock is never adjusted. Our IN-16/TS-19 review should reject that hidden-only contradiction unless the docs define reissue or per-day offsets. ADAPT only after a contract repair.'),
 '8defd7be':('P3','TRUTH.md:3-20 withholds roughly fifty constants and functional forms; TRUTH.md:121-127 gives only a local sweep. The hypothesis space is not bounded in agent-visible files. AVOID under DS-21/IN-16, despite stage-2 acceptance.'),
 '05550e00':('P3','The agent gets empty-shift and byte-form checks, then misses isolated state and value checks. The hidden shape is in _case_for at tests/test_output.py:1134; TRUTH.md must be checked for a finite learnable constant family. ADAPT only if bounded.'),
 '28a29cf0':('P3','Related gate task: isolated meter and throughput checks partly pass; full unseen ledgers fail. Inspect _case_for at tests/test_output.py:1135 before assuming the same cause as 05550e00. ADAPT only if the learned family is bounded.'),
 'aa314fee':('P3','TRUTH.md:8 says shortfall carries across cycles, so one wrong decision reaches later ledgers. Its exact whole-ledger checks localise poorly; CL-4 requires independently graded partial views. ADAPT the carried-state fixture, not full-ledger stacking.'),
 '6d12f970':('P3','Prior stage-1 card reports cost_policy.md:8-13 may silently redefine the relevant rule and judge.toml version skew. Treat the low score as RISKY under IN-16 and JD-8; do not copy the silent redefinition.'),
 '80202e15':('P4','The instruction delegates authority to source_register.md and governance_charter.docx (instruction.md:1); tests regenerate next-month exports and share the _primary hidden run (tests/test_output.py:6009-6018). Shipped concept checks fail too, so hidden variation is not an isolated cause. 48 tests trigger TS-23 warning; ADAPT only authority ordering and a small number of distinct views.'),
 '9f5486ac':('P4','The next-release delta/--prior promise is explicit (instruction.md:1-16); multiple exact checks share a regenerated release. Shipped failure means a broad failure, not proof that hidden data alone caught the agent. Avoid all-or-nothing HELD gating under CL-4.'),
 '5048c412':('P2','The contract explicitly distinguishes byte-exact text from value-exact database/workbook reports (instruction.md:5). tests/test_output.py contains a source-length check, functions_at_most_sixty_lines, that our TS-27 would reject even though instruction.md:5 states the limit. ADAPT carrier diversity, AVOID source-shape scoring.'),
 'fabbe645':('P5','The instruction promises full-size completion under 60 seconds (instruction.md:19). Stdout says “the full size run did not finish cleanly”; that combines timeout, crash and missing output, so TIMEOUT is suspected but not proven. TS-11 requires a generous measured oracle margin.'),
 'a710b00e':('P1','A visible run passes while generated corpora fail; _case_make_data(seed, hidden, scale) at tests/test_output.py:19 varies seed and scale. This is the strongest isolation of hidden generalisation among the selected tasks. COPY the data variation only when each report is grounded in shipped contracts.'),
 '8eae0f87':('P1','Shipped ledger/summary/rollups pass, billing_reports_extract_N checks fail. The instruction delegates to documents; hidden generator _hidden(index) at tests/test_output.py:1751 supplies fresh extracts. COPY distinct per-extract report views with TS-26/CL-4 review.'),
 '98ed74c1':('P1','Shipped report views pass; held-out extracts planted by _hidden at tests/test_output.py:1380 fail. The test names “reports exact” per extract. COPY seeded fresh data after checking its policy overrides are explicitly grounded.'),
 '18b5d99f':('P1','Shipped analysis/report views pass while identity, standing, wide-kinds, errata and boundary extracts fail. This isolates unseen family members and rules better than a single monolithic hidden run. COPY only grounded variants.'),
 'f348165e':('P1','Invalid held-out extracts stop cleanly, while valid held-out report views fail. This separates error handling from substantive derivation; COPY separate valid/invalid fixture families, avoiding double payment.'),
 '3f39299a':('P1','Shipped all-reports check passes; generated corpus checks vary parameter versions, cutoff instants and identity. COPY controlled one-axis changes, with each branch-fire witness recorded.'),
 '9cc598a9':('P6','Only install and shipped package checks pass; visible/eval plans fail. A large repair task is not evidence that a particular hidden test design beat an otherwise correct solver. AVOID as a direct lever model.'),
 'f2d019d0':('P6','Only determinism and named-error checks pass; shipped substantive checks fail. AVOID attributing loss to hidden design alone.'),
}
for x in ['6285fcad','1d61e794','9d1784a5','ceadc676','37a0c3d6','b42c61b9']:
 SPECIAL[x]=('P2','Generated fresh packs vary seeds and carrier settings (generator anchor above); only form/manifest checks pass in the recorded run. The exact core reports fail, so the record does not prove the carrier variation alone defeated a correct solver. ADAPT one legal carrier variant at a time with a value-preservation proof; avoid hidden forms absent from the contract.')
SPECIAL['275f885b']=('P3','The ledger spine and awards fail together; exact whole-document grading detects the wrong state but does not prove which upstream rule caused it. ADAPT a local branch trigger plus independent ledger slices under CL-4.')
def main():
 rows={r['id8']:r for r in csv.DictReader((OUT/'inventory.csv').open())}; details=json.loads(read(OUT/'scratch/details.json')); sel=json.loads(read(OUT/'scratch/selection.json'))['selected']
 for id8 in sel:
  p=next(ROOT.glob(id8+'-*')); d=details[p.name];r=rows[id8]; tests=read(p/'tests/test_output.py').splitlines();ins=read(p/'instruction.md').splitlines();j=read(p/'tests/judge.toml').splitlines()
  out=[]; add=out.append
  add(f'# {id8} — {r["author"]} ({r["band"]})')
  add(f'Stage-2 accepted; final {r["final_score"]}%, tests lost {r["lost_positive_weight"]}/{r["positive_test_weight"]} positive weight ({r["lost_pct"]}%), test/judge final contributions {r["test_contribution"]}/{r["judge_contribution"]} points (`inventory.csv`, reproduced by `scripts/inventory.py`).')
  add('## A. Lost checks and observed failure')
  fails=sorted(d['failed'],key=lambda c:-float(c['weight'])*(1-float(c.get('value',0))))
  for c in fails[:5]:
   name=c['name'];ln,_=pick(tests,r'^def (?:_check_|_impl_)?'+re.escape(name)+r'\(')
   if not ln:ln,_=pick(tests,r'criteria\.'+re.escape(name)+r'\(')
   add(f'- {name}: weight {c["weight"]}, earned {c["value"]}; {trunc(c.get("description",""),130)} (`tests/test_output.py:{ln or "?"}`; `reward-details.json`, criterion `{name}`).')
  stdout=d['stdout'].strip();add(f'- First verifier output: `{trunc(stdout,250)}` (`verifier/test-stdout.txt:1`).'+(' It contains no assertion difference; WRONG/TIMEOUT/CRASH is not separable from this log.' if stdout.startswith('reward:') else ' Inspect subsequent stdout for per-check evidence.'))
  # Trajectory step index, no complete trajectory printed.
  traj=json.loads(read(p/'trajectories/claude-opus-5/run_1/agent/trajectory.json'))
  docsteps=[];codes=[]
  for s in traj.get('steps',[]):
   for call in s.get('tool_calls',[]) or []:
    arg=call.get('arguments',{}); cmd=arg.get('command','') if isinstance(arg,dict) else ''
    if re.search(r'\b(cat|sed|head|less)\b.*(?:/app/data/|\.md\b|\.docx\b)',cmd) and len(docsteps)<4:docsteps.append(f'{s.get("step_id")}:{trunc(cmd,85)}')
    if re.search(r'(/app/out/|solve\.py|transform\.py|derive_report\.py)',cmd) and re.search(r'(cat >|tee |python3 |cp |sed -i)',cmd) and len(codes)<3:codes.append(f'{s.get("step_id")}:{trunc(cmd,85)}')
  add('- Trajectory indexed steps: document reads '+('; '.join(docsteps) if docsteps else 'none located by command search')+'; program/run '+('; '.join(codes) if codes else 'none located by command search')+'. Cause requires source-level review; no misread is established by the score alone.')
  add('## B. Test construction and measurement')
  funcs=[]
  for i,l in enumerate(tests,1):
   if re.match(r'\s*def (?:_.*(?:hidden|generate|corpus|case_for|case_make|build_one|plant|run_locked|run_delivered|run_program|run_extract)|_Ggenerate)',l,re.I):funcs.append((i,l.strip()))
  add('- Construction anchors: '+('; '.join(f'`tests/test_output.py:{i}` {trunc(s,90)}' for i,s in funcs[:5]) if funcs else 'no named generator located')+'.')
  cmp=[]
  for i,l in enumerate(tests,1):
   if re.search(r'(read_bytes\(\)|==\s*(?:expected|reference|ref\b)|_all_exact\(|_reports_match\(|_matches\()',l) and len(cmp)<2:cmp.append((i,l.strip()))
  add('- Comparison anchors: '+('; '.join(f'`tests/test_output.py:{i}` {trunc(s,110)}' for i,s in cmp) if cmp else 'inspect criterion bodies for exactness')+'.')
  add(f'- Criterion-name hidden lower bound {r["hidden_named_weight"]}/{r["positive_test_weight"]} positive weight; this is a lower bound only (names miss generated cases). Timeout literals in test code: {r["timeout_literals_sec"] or "none extracted"} s. Test count {r["test_count"]}; judge count {r["judge_count"]}.')
  add('## C. Wording and QC')
  il,iv=pick(ins,r'unseen|reusab|any |new |next |unchanged|rerun|another|different');
  if not il:il,iv=pick(ins,r'.+')
  add('- Instruction generalisation: '+quoted('instruction.md',il,iv))
  docs=sorted((p/'environment').rglob('*.md'))
  docq=None
  for dp in docs:
   ls=read(dp).splitlines();dl,dv=pick(ls,r'\b(?:must|each|when|if|wins|precedence|authority|carry|rounded|exact)\b',r'^#|^\|[- :]')
   if dl and len(dv)>30:docq=(dp.relative_to(p),dl,dv);break
  add('- Agent-visible document sample: '+(quoted(*docq) if docq else 'no Markdown rule sentence selected; inspect other formats')+'. This sampled line is not assumed to cause the failure.')
  cl,cv=pick(tests,r'@criterion\(description=');add('- Check wording: '+(quoted('tests/test_output.py',cl,cv) if cl else 'criterion description in reward details')+'.')
  jl,jv=pick(j,r'^description\s*=');add('- Judge wording: '+(quoted('tests/judge.toml',jl,jv) if jl else 'no judge description located')+'.')
  add('- QC mapping: IN-16/TS-19/DS-21 require a unique, learnable rule; IN-17 permits discovery from shipped data; AL-27 requires a firing witness; TS-11 applies to timing/seed stability; TS-26/JD-8/CL-4 require distinct observables and localised loss. Stage-2 presence is not evidence of a pass under our QC kit. Check TRUTH.md and shipped evidence before copying.')
  add('## D–F. Assessment')
  pat,note=SPECIAL.get(id8,('P1','No task-specific note recorded.'))
  add(f'- Pattern {pat}: {note}')
  passed=[c for c in json.loads(read(p/'trajectories/claude-opus-5/run_1/verifier/reward-details.json'))['reward']['components'] if c['name']=='test_output'][0]['detail']['criteria']
  passed=[c['name'] for c in passed if c['weight']>0 and c.get('value')]
  add('- Positive checks passed: '+(', '.join(passed[:12]) if passed else 'none')+(' (and more)' if len(passed)>12 else '')+'.')
  add('- QL/PL: no task-local QL or PL note file found in this repo tree; acceptance means inclusion in stage-2 only.')
  add('- Measured property: the named weighted checks above; whether shipped data triggers them needs the cited generator and input files. Hidden failure mechanism and first differing field remain UNRESOLVED where stdout is reward-only.')
  add('- Transfer: ADAPT only after proving the rule from agent-visible data, a branch-fire witness, oracle correctness, and per-check isolation. Avoid adopting unexplained oracle-only expectations.')
  (OUT/'cards'/f'{id8}.md').write_text('\n'.join(out)+'\n')
 print('cards',len(sel))
if __name__=='__main__':main()
