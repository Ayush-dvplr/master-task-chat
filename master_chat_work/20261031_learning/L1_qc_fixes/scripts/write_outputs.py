#!/usr/bin/env python3
"""Summarize build_l1.py CSVs; writes only L1 OUT."""
from pathlib import Path
import csv,json,collections,re
OUT=Path(__file__).resolve().parents[1]
R=list(csv.DictReader((OUT/'QC_FINDINGS.csv').open())); E=list(csv.DictReader((OUT/'FIX_EFFECTS.csv').open())); S=json.loads((OUT/'parse_summary.json').read_text())
TB=Path('/Users/mac/Desktop/Terminal Bench')
def short(x):return x.replace(str(TB)+'/','TB/')
def ref(x):return f'`{short(x)}`'
def excerpt(x,n=200):
 s=x['problem'];s=re.sub(r'^\W*(?:G\d\d[-\w]*|F[-\w]*|Gate \d\d|(?:IN|DS|TS|JD|AL|CL)-\w+)[^:]*:\s*','',s);return s[:n].rstrip(' .;')
def source_line(x):
 try:
  p,lineno=x['report_evidence'].rsplit(':',1)
  return Path(p).read_text(errors='replace').splitlines()[int(lineno)-1]
 except (ValueError,IndexError,FileNotFoundError):return x['problem']
def fix_text(x):
 s=source_line(x);i=s.rfind('Fix:')
 return re.sub(r'[`*]','',s[i+4:].strip(' .;'))[:210] if i>=0 else 'UNVERIFIED exact edit; see P12 note or next report'

# Narrow build-time checklist descriptions, keyed to the live QC IDs.
prevent={
'DS-22':'Recompute every count, digest and claimed behaviour in TRUTH.md after the final edit.',
'JD-5':'Make each judge criterion test one observable.',
'AL-27':'Mutate each stated branch once and require at least one graded fixture to change.',
'TS-23':'Budget the check count before splitting fixtures; record a count-cap decision when needed.',
'TS-13':'Give unrelated properties separate checks and avoid repeated payment for one wrong fact.',
'DS-27':'Write TRUTH.md as task truth; remove build history and internal process notes.',
'AL-2':'Trace every instruction promise to an executable check or judged criterion.',
'JD-15':'Label conduct as agent behavior; put outcome requirements in visible instructions.',
'JD-7':'Run the oracle against each positive judged criterion before QC.',
'TS-24':'Start child programs in process groups and reap the entire group on every exit path.',
'TS-19':'Run an honest implementation against every fixture and compare fixture limits with the contract.',
'IN-16':'State tie-breaks, units and edge cases before writing exact-output checks.',
'DS-20':'Compare the oracle against the stated contract on adversarial in-limit cases.',
'AL-28':'Probe one cheating act against every negative and cap combined penalties.',
'TS-14':'Check that each criterion name and description describe its actual assertion.',
'IN-12':'Make category, description and tags match the dominant task work.',
'CL-5':'Specify every graded output detail, including null order and path form.',
'IN-8':'Map each judged outcome to an agent-visible rule or file.',
'AL-18':'Rescan prose, comments and TRUTH after any code, test or data change.',
'TS-20':'Weight core deliverables above cheap details and review point concentration.',
'X1':'Inspect every file the text sweep skipped as binary, including archive members.',
'TS-16':'Probe anti-cheat checks with honest code and with a real cheat.',
}
usual={
'DS-22':'TRUTH.md has a stale count, digest or description after code or test edits.',
'JD-5':'A judge item combines two or more independently gradable observations.',
'AL-27':'A stated rule has no graded input that activates it.',
'TS-23':'The number of test checks exceeds the kit’s 35-check warning cap.',
'TS-13':'One check bundles unrelated properties or repeats credit for one error.',
'DS-27':'TRUTH.md narrates authoring history instead of task truth.',
'AL-2':'An instruction promise has no corresponding grading check.',
'JD-15':'A judge item has the wrong kind or grades an unstated outcome.',
'JD-7':'The oracle fails or does not demonstrate a positive judge criterion.',
'TS-24':'A launched agent process can survive a timeout or hold the verifier past its budget.',
'TS-19':'A valid interpretation or honest agent fails a graded test.',
'IN-16':'The instruction or visible contract leaves a graded edge case open to two readings.',
'DS-20':'The oracle disagrees with a stated rule or in-limit performance promise.',
'AL-28':'One act triggers multiple negative penalties whose total is excessive.',
'TS-14':'A check’s name or description does not match its body.',
'IN-12':'Metadata misstates or underspecifies the dominant task work.',
'CL-5':'A graded exact detail is absent from the agent-visible contract.',
'IN-8':'A graded outcome is not learnable from an agent-visible source.',
'AL-18':'Prose or documentation no longer matches the shipped implementation.',
'TS-20':'Core outcomes receive less weight than cheap or peripheral checks.',
'X1':'The structure scanner skips binary files, so embedded text can escape the sweep.',
'TS-16':'A negative check catches innocent code or misses the forbidden act.',
}
top=[(k,n) for k,n in S['check_tasks'] if k!='UNVERIFIED'][:20]
lines=['# Fix recipes — 20 check IDs appearing in the most tasks','',f'Counts are distinct tasks, not report rows (`python3 scripts/build_l1.py`; `parse_summary.json:$.check_tasks`). “Reported fixed” means the next QC comparison says fixed; no scored agent rerun is implied. Shared-file side effects use the operational definition in `FIX_EFFECTS.csv`.','']
for c,n in top:
 a=[x for x in R if x['check_id']==c];f=next((x for x in a if x['status_next']=='FIXED' and 'Fix:' in source_line(x) and x['fix_note']),None) or next((x for x in a if x['status_next']=='FIXED' and 'Fix:' in source_line(x)),None) or next((x for x in a if x['status_next']=='FIXED'),None)
 e=next((x for x in E if x['new_check_id']==c),None)
 b=next((x for x in a if x['status_next'] in ('CAME BACK','MOVED')),None)
 example=a[0]
 lines += [f'## {c} — {n} tasks','',f'- Usual problem: {usual[c]} Example: {ref(example["report_evidence"])}.',]
 if f:
  fx=fix_text(f)
  stem='- Reported closed, exact edit UNVERIFIED' if fx.startswith('UNVERIFIED') else f'- Worked: {fx}'
  lines += [f'{stem}; {f["task"]} {f["report_version"]} to the next round. Evidence: {ref(f["report_evidence"])}, {ref(f["next_evidence"])}'+(f', {ref(f["fix_note"].split("; ")[0])}' if f['fix_note'] else '')+'.']
 else:lines += ['- Worked: UNVERIFIED; no explicit next-round “fixed” comparison was indexed for this ID.']
 if e:lines += [f'- Failed or broke: {e["edit"][:160]}; new {e["new_check_id"]} appeared in {e["task"]} {e["to_round"]}. This is a file/criterion link, not isolated causality. Evidence: {ref(e["finding_evidence"])}, {ref(e["fix_evidence"])}.']
 elif b:lines += [f'- Failed or returned: the criterion was still reported in {b["task"]} {b["report_version"]} and the next round; whether the identical defect survived is UNVERIFIED. Evidence: {ref(b["report_evidence"])}, {ref(b["next_evidence"])}.']
 else:lines += ['- Failed or broke: UNVERIFIED; no linked recurrence or new finding was indexed.']
 lines += [f'- Build time: {prevent[c]}','']
(OUT/'FIX_RECIPES.md').write_text('\n'.join(lines)+'\n')

# A round is an existing vN report. "Sole fail" counts unique active fail rows in the consolidated findings.
roundrows=[]; by=collections.defaultdict(list)
for x in R:by[x['task'],int(x['report_version'][1:])].append(x)
for t,n in S['rounds'].items():
 for v in range(1,n+1):
  a=by[t,v]; fails=[x for x in a if x['severity']=='❌']; sole=fails[0]['check_id'] if len(fails)==1 and v<n else ''
  roundrows.append(dict(task=t,round=f'v{v}',active_fail_findings=len(fails),active_minor_findings=sum(x['severity']=='minor' for x in a),active_warn_findings=sum(x['severity']=='warn' for x in a),sole_fail_forced_next_round=sole,report_evidence=str(TB/'QC/reports'/t/f'v{v}.md')))
with (OUT/'ROUNDS.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(roundrows[0]));w.writeheader();w.writerows(roundrows)
sole=[x for x in roundrows if x['sole_fail_forced_next_round']]
roundtable='\n'.join(f'| {t} | {n} |' for t,n in sorted(S['rounds'].items()))
soletable='\n'.join(f'| {x["task"]} {x["round"]} | {x["sole_fail_forced_next_round"]} | {ref(x["report_evidence"])} |' for x in sole)
issues='; '.join(short(x) for x in S['parse_issues']) or 'none'
findings=f'''VERDICT: QC fixes closed many reported defects, but subsequent rounds repeatedly found new contract, test, judge and prose errors; the documented file links do not prove isolated causality.

# 1. All QC findings

**Finding.** `QC_FINDINGS.csv` indexes {S['findings']} active finding rows from {S['reports']} `v*.md` reports across {S['tasks']} tasks: {S['severity'].get('❌',0)} fails, {S['severity'].get('minor',0)} minors and {S['severity'].get('warn',0)} warns. Method: `python3 scripts/build_l1.py` reads the first consolidated Findings section, takes numbered, bulleted and bold finding entries, applies the local severity heading or emoji, captures the first QC check ID and named file:line, and excludes explicitly acknowledged or fixed-only entries. Each row has a report path:line. `parse_summary.json:$.parse_issues` = {issues}. A report can have zero active findings; `ROUNDS.csv` retains it. **UNVERIFIED:** {sum(x['check_id']=='UNVERIFIED' for x in R)} rows lack a standard check ID, and some reports repeat the same root in different gates; these are separate report entries rather than deduplicated defects. Evidence: `scripts/build_l1.py`, `parse_summary.json:$.reports`, `$.findings`, `$.severity`, `QC_FINDINGS.csv:report_evidence`.

**Change:** Make `master_chat_tasks/tools/` ingest the CSV after each QC round and require a primary check ID plus source line for each consolidated finding. **Expected gain:** query all rounds and spot repeated defects without rereading 95 reports. **Could break:** irregular report prose can be misparsed; `check_id=UNVERIFIED` rows need hand classification. **Check:** compare per-report CSV counts to the report's Overall row and inspect every `UNVERIFIED` ID before promoting the index. Evidence: `scripts/build_l1.py`, `QC_FINDINGS.csv`, `parse_summary.json:$.check_tasks`.

# 2. What happened after each fix

**Finding.** `QC_FINDINGS.csv:status_next` links each active row to the next numbered report for its task. The current index has {S['status'].get('FIXED',0)} “FIXED”, {S['status'].get('CAME BACK',0)} “CAME BACK”, {S['status'].get('MOVED',0)} “MOVED”, {S['status'].get('KEPT',0)} “KEPT”, {S['status'].get('REBUTTED',0)} “REBUTTED” and {S['status'].get('NOT RECHECKED',0)} “NOT RECHECKED” rows. It uses same check ID plus text and named place for recurrence; “FIXED” requires explicit fixed/resolved/pass wording in the next report's comparison. A matching P12 `KEPT.md` or `PL_NOTE.md` line, or a task KEPT line acknowledged in the next report, overrides recurrence. P12 `RECHECK_FIX.md` notes are linked where their folder names identify the QC version; {S['notes']} such notes were found. **UNVERIFIED:** absence of a finding is not counted as fixed, and a shared check ID may describe a different defect. Evidence: `scripts/build_l1.py:match`, `QC_FINDINGS.csv:status_next,next_evidence,fix_note`, `parse_summary.json:$.status, $.notes`.

**Change:** Add a per-finding stable key (check ID, rule phrase, file, observable) and a fix receipt to `master_chat_tasks/prompts/templates/` and each P12 `RECHECK_FIX.md`: exact files and hunks changed, prior finding ID, disposition and next report link. **Expected gain:** separate true closure from renamed or moved problems. **Could break:** more bookkeeping and unstable line numbers. **Check:** rerun this linkage on a new round and manually verify all same-ID pairs and all NOT RECHECKED rows. Evidence: `QC_FINDINGS.csv`, `FIX_EFFECTS.csv`, `scripts/build_l1.py`.

# 3. New errors after fixes

**Finding.** `FIX_EFFECTS.csv` has {len(E)} links from a new or newly exposed next-round finding to a file/criterion documented as edited. The match is by task, adjacent round, new finding, and the same named file in a P12 change note or changed-hunk table; explicit report comparisons supplement this. This is the requested operational “caused by fix” label; **INFERRED**, because the record does not isolate a single edit. It extends S4's 11-row `FIX_MAP.csv` without copying its broad score-history rows. The sharp examples are: cold-chain v4→v5 corrected corridor prose but created a 30/31 cold-room contradiction and took checks from 33 to 54 (`QC/reports/cold-chain-backbone-quote/v5.md:386-393`); schema v13→v14 removed the planner give-up and bounded child time but introduced TS-11 scheduling-dependent scoring and a stale DS-14 note (`QC/reports/schema-migration-plan-repair/v14.md:348-353`); district v9→v10 narrowed an import negative and left `_or_network` in its name (`QC/reports/district-heat-flex-procurement/v10.md:389-393`). Evidence: `FIX_EFFECTS.csv`, `scripts/build_l1.py`, S4 `FIX_MAP.csv`.

**Change:** Add a side-effect receipt to `QC_FIX_PLAYBOOK_v3.md`: for every edited file, recheck its contract statement, oracle, test name/weight, judge overlap and TRUTH prose, then run the next QC comparison. **Expected gain:** catch the documented stale-prose and weight/count regressions before a new round. **Could break:** broad receipt scope can slow small fixes. **Check:** replay the {len(E)} indexed links against source diffs; keep `INFERRED` until a hunk directly changes the faulty behavior. Evidence: `FIX_EFFECTS.csv:matched_file,why_linked,fix_evidence`.

# 4. Recurring check recipes

**Finding.** `FIX_RECIPES.md` covers the top 20 check IDs by distinct tasks, excluding unclassified IDs; its examples cite the report, next-round disposition and any P12 note. The highest-frequency IDs are DS-22 and JD-5 (14 tasks each), AL-27 (13), TS-23 (12), then DS-27, AL-2, TS-13 and JD-15 (11 each). Evidence: `parse_summary.json:$.check_tasks`, `FIX_RECIPES.md`, `scripts/write_outputs.py`.

**Change:** Put each recipe's one-line build-time action in `master_chat_tasks/knowledge/QC_FIX_PLAYBOOK_v3.md`, with a required cross-file recheck for DS-22, AL-27 and AL-28. **Expected gain:** fewer repeated QC rounds on common faults. **Could break:** applying an old example mechanically to a new task can create wrong fixtures or weights. **Check:** require a live kit rule citation and one task-specific counterexample for each applied recipe. Evidence: `FIX_RECIPES.md`, `QC_FINDINGS.csv`.

# 5. Rounds and sole blockers

**Finding.** Report counts by task are below. These count existing QC report versions, not necessarily all build/fix attempts. Evidence: `find TB/QC/reports -maxdepth 2 -name 'v*.md'` (95 files), `parse_summary.json:$.rounds`, `ROUNDS.csv`.

| Task | QC reports |
|---|---:|
{roundtable}

A sole active fail appeared in {len(sole)} rounds with a later report; it was the only fail in that round, though minors/warns and other work may also have motivated the recheck. Evidence: `ROUNDS.csv:sole_fail_forced_next_round`.

| Round | Sole fail ID | Report |
|---|---|---|
{soletable}

**Change:** Record `next_round_reason` in each QC report and board decision; label a check “forced” only when the decision explicitly says it blocked progress. **Expected gain:** a defensible round-cost ranking. **Could break:** retroactively calling a sole fail causal would overstate the evidence. **Check:** compare each next-round reason to its prior report and P12 note. Evidence: `ROUNDS.csv`, `QC_FINDINGS.csv`, `master_chat_tasks/decisions.jsonl` (not independently matched here, **UNVERIFIED**).
'''
(OUT/'FINDINGS.md').write_text(findings)
(OUT/'QUESTIONS.md').write_text('None.\n')
files=['FINDINGS.md','QUESTIONS.md','result.json','QC_FINDINGS.csv','FIX_EFFECTS.csv','FIX_RECIPES.md','ROUNDS.csv','parse_summary.json','scripts/build_l1.py','scripts/write_outputs.py']
result={'session':'L1','status':'DONE','findings':5,'recommendations':5,'questions':0,'unverified':sum(x['check_id']=='UNVERIFIED' for x in R)+sum(x['fix_sha']=='UNVERIFIED' for x in E),'files':files}
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(f"wrote {len(files)} files; {len(sole)} sole-fail rounds; {len(E)} effects")
