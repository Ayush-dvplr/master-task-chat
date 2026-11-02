#!/usr/bin/env python3
"""Render evidence-linked L5 cards from the read-only run inventory."""
import json
from collections import Counter
from pathlib import Path

OUT=Path(__file__).resolve().parents[1]
ROOT=Path('/Users/mac/Desktop/Terminal Bench/anubis-stage-2')
all_items=json.loads((OUT/'run_evidence.json').read_text())
items=sorted(all_items,key=lambda d:d['final'])[:10]
EVIDENCE_INDEX={d['id']:i for i,d in enumerate(all_items)}

# Curated after reading each instruction, TRUTH, shipped contract, test code, and score reasons.
NOTES={
'8defd7be':('Recover a broker probe accounting engine from lookup inputs and two rollups; deliver reusable broker.py and three reports, then twenty figures.',
 'Withheld numerical forms and state constants; 40/42 tests fail. The author truth lists about fifty missing decisions. The fitted run is real, but the finite evidence does not establish global uniqueness of the unspecified functional forms (INFERRED).',
 'Risky: the task asks for an open-ended inverse problem whose form class is unstated. The prior R4 audit separately flagged this design. Do not copy it as a fairness model.',
 'PASS','LIKELY FAIL','UNVERIFIED','LIKELY FAIL','UNVERIFIED',
 'instruction.md:1-17; solution/TRUTH.md:7-35; prior R4_teammate_repo/genuineness.md:8,27-30'),
'42e79476':('Rebuild cost coefficients from a mixed-format dispatch export, solve the exact plan, and publish 21 audit artifacts with a reusable solver.',
 'Four hidden input sets separate coefficients, capital, quality, plan, sourcing, totals and certificates. Coefficients/sourcing/totals/certificates fail while some capital/plan/quality checks pass. The final answer also misses objective figures.',
 'Mostly fair: the source authority and operating rules are in the shipped export set; a wrong objective is observable. Judge negatives have a documented quirk in the prior R4 audit. Inspect that separately before copying its judge.',
 'PASS','LIKELY PASS','LIKELY PASS','LIKELY PASS','UNVERIFIED',
 'instruction.md:1-15; solution/TRUTH.md:3-35; tests/test_output.py:18155-18190; prior R4_teammate_repo/genuineness.md:9-13,32'),
'59417607':('Build a reusable billing transform from cycle records and documents, create thirteen byte-exact reports, and answer eight changed-extract what-ifs.',
 'The shipped seven checks pass; all eighteen hidden extracts fail. The main lever is per-exchange-day clock offset recovery; contract timing, amendment and tie rules then cascade into reports. Several exact what-if judge figures fail.',
 'Fair under the prior audit: the offset domain is stated and each hidden day has a unique fit. Exact bundle checks create a steep score curve, but the instruction explicitly requires byte-for-byte reports.',
 'PASS','LIKELY PASS','LIKELY PASS','LIKELY PASS','PASS WITH EXACT-BAR EXCEPTION',
 'instruction.md:1-18; environment/data/record_dictionary.md:19; solution/TRUTH.md:7-29; prior R4_teammate_repo/genuineness.md:9-10'),
'98ed74c1':('Build a reusable PM2.5 report program for card readings, receipt journal, deployments and policy; create nine exact reports and answer ten what-ifs.',
 'All twenty held-out extracts fail while most shipped reports pass. Offsets must be inferred by matching card rows to journal receipts; hour-end and span-register rules spread errors across held-out reports and what-ifs.',
 'Likely fair: the shipped journal and documents determine the offsets and time semantics, though a full uniqueness proof for every hidden seed was not independently rerun. The exact-output bar is explicit.',
 'PASS','LIKELY PASS','LIKELY PASS','LIKELY PASS','PASS WITH EXACT-BAR EXCEPTION',
 'instruction.md:1-22; solution/TRUTH.md:5-34; tests/test_output.py:1931,2052'),
'75407a55':('Implement a royalty accounting engine from schema and ten small input files; create nine JSON reports and handle fresh conforming extracts.',
 'Eight fresh scenarios fail: revision tie, FX/withholding midpoint, pool and advance priority, largest remainder, period carry, signed adjustment. The judge also loses independent validation criteria.',
 'Contract-grounded rules and fixtures are strong, but each scenario compares one hash over all nine reports and _holds catches every exception. A one-field error can zero an entire scenario; wrong-vs-timeout is unrecoverable from CTRF.',
 'PASS','LIKELY PASS','LIKELY PASS','LIKELY PASS','LIKELY FAIL',
 'instruction.md:1-7; environment/data/schema.md:9-45; tests/test_output.py:54-115; solution/TRUTH.md:18-30'),
'a710b00e':('Reconcile a telemetry extract through clock, allocation, stream and amendment contracts; deliver nine deterministic reports and reusable code.',
 '209 positive checks fail, mainly corpus_NN per-report exacts. Eight visible report checks pass. The large 10.6 MB candidate input and multi-lane hidden corpora create scale and generalization pressure.',
 'Likely fair at contract level, but per-report whole-object equality repeated across corpora can magnify one shared error. No check-level error detail survives broad exception handling, so the precise loss cause is unverified.',
 'PASS','LIKELY PASS','UNVERIFIED','LIKELY PASS','UNVERIFIED',
 'instruction.md:1-24; solution/TRUTH.md:5-32; tests/test_output.py:1455-1480; environment/data/allocation_candidates.csv (10,553,443 bytes)'),
'aa314fee':('Reconstruct 24 cycles of foundry allocation from a large mixed corpus, produce nine artifacts, and answer eight two-number counterfactuals.',
 'Almost all exact ledger, shortfall, hidden-extract and what-if checks fail. The carried shortfall makes one early mistake propagate through the horizon; admission and substitution traps also matter.',
 'Design defect for our QC: TRUTH explicitly says two graded rules are withheld from every contract. Observation logs may suggest them, but no finite hypothesis class or uniqueness proof is supplied (INFERRED). The prior R4 audit called it genuine; our IN-8/AL-1 reading is stricter.',
 'PASS','LIKELY FAIL','LIKELY PASS','LIKELY FAIL','UNVERIFIED',
 'instruction.md:1-11; solution/TRUTH.md:5-16,20-35; tests/test_output.py:313-340; prior R4_teammate_repo/genuineness.md:9-17'),
'9bb234eb':('Implement a pension valuation engine from schema and ten small input files; output nine JSON reports and handle fresh extracts.',
 'Eight fresh scenarios fail: revision tie, overlapping leave, missing salary, same-day event order, salary cap, election-day and multiple-election boundaries, valuation clip. Judge validation probes also fail.',
 'Rules and trigger cases are documented, but each scenario hashes all nine reports and catches every runner exception. This fails our partial-credit check absent an explicit whole-bundle exact-match bar.',
 'PASS','LIKELY PASS','LIKELY PASS','LIKELY PASS','LIKELY FAIL',
 'instruction.md:1-7; environment/data/schema.md:3-21; tests/test_output.py:130-160; solution/TRUTH.md:18-30'),
'fa7c65bd':('Implement a spectrum-clearing engine with revisioned grants, half-open time-frequency rectangles, preemption and signed correction allocation.',
 'Eight fresh scenarios fail: revision cells/scalars, activation ID, half-open boundary, guard abutment, correction tie, half-up midpoint and exclusion span. Judge validation probes also fail.',
 'Contract and scenarios align, but each scenario compares all nine reports at once and catches every exception. It needs field or report-level credit and explicit failure causes for our QC.',
 'PASS','LIKELY PASS','LIKELY PASS','LIKELY PASS','LIKELY FAIL',
 'instruction.md:1-7; environment/data/schema.md:3-55; tests/test_output.py:342-384; solution/TRUTH.md:5-25'),
'f348165e':('Build a three-entry settlement program for binary request logs, a sharded register, OOXML/PDF evidence and nine frozen reports; answer what-ifs.',
 'Most valid hidden report groups fail, while invalid-extract rejection checks pass. The main levers are finite units-per-RU recovery, binary decoding, sharded authority and long settlement replay.',
 'Grounding is plausible from shipped documents, but grouped exact comparisons and 60-second calls need a one-fact perturbation and per-group failure-cause audit before treating its score curve as clean.',
 'PASS','LIKELY PASS','LIKELY PASS','LIKELY PASS','UNVERIFIED',
 'instruction.md:1-29; solution/TRUTH.md:5-32; tests/test_output.py:2660-2705'),
}

def compact_tests(tests, idx):
    if len(tests)<=25:
        return ', '.join(f"`{t['name']}` ({t['weight']})" for t in tests)
    names=[t['name'] for t in tests]
    prefix=Counter(n.split('_')[0] for n in names)
    return f"{len(tests)} failed positive tests; frequent first tokens: {dict(prefix.most_common(8))}. Examples: " + ', '.join(f"`{t['name']}` ({t['weight']})" for t in tests[:12]) + f'. Full list: `run_evidence.json:$[{idx}].failed_tests`.'

for d in items:
    uid=d['id']; short=uid[:8]; ask,lever,fair,in17,al1,al27,in8,cl4,refs=NOTES[short]
    b=f'anubis-stage-2/{uid}'
    run=f'{b}/trajectories/claude-opus-5'
    idx=EVIDENCE_INDEX[uid]
    testnames=compact_tests(d['failed_tests'],idx)
    judge=', '.join(f"J{c['number']}({c['score']:g}, {c['target']}): {c['criterion'][:100].rstrip()}…" for c in d['failed_criteria']) or 'none'
    neg=', '.join(f"J{c['number']}({c['score']:g}): {c['criterion'][:100].rstrip()}…" for c in d['fired_negatives']) or 'none'
    evidence=f'`{run}/pass_summary.json:$.per_run[0]`; `{run}/run_1/verifier/ctrf.json:$.results`; `{run}/run_1/verifier/score.json:$.rubric`; `{run}/run_1/result.json:$.verifier,$.exception_info`; `{run}/run_1/artifacts/manifest.json`'
    source_refs=[]
    for ref in refs.split('; '):
        source_refs.append('`'+('master_chat_work/20261028_upgrade/'+ref.removeprefix('prior ') if ref.startswith('prior R4_') else b+'/'+ref)+'`')
    source_refs='; '.join(source_refs)
    text=f'''# {uid}: {d['category']}

## Assignment and score

{ask} Evidence: `{b}/instruction.md:1`.

Opus tests **{d['tests']}**, rubric **{d['rubric']}**, final **{d['final']}**; {d['check_count']} test checks and {d['judge_count']} judge criteria. Reward and summary agree, verifier finished, exception_info is null, and all {len(d['outputs'])} captured `/app/out` artifacts have status `ok`. Evidence: {evidence}.

## Where points went

{lever} Evidence: {source_refs}; `{run}/run_1/verifier/ctrf.json:$.results.tests`; `{run}/run_1/verifier/score.json:$.rubric`.

Failed positive test names: {testnames}

Failed positive judge criteria: {judge}. Fired negative criteria: {neg}. Complete names, weights and justifications: `run_evidence.json:$[{idx}].failed_criteria`; `run_evidence.json:$[{idx}].fired_negatives`.

**WRONG vs timeout/crash.** {len(d['failed_tests'])} positive checks failed and {len(d['passed_tests'])} passed. The agent produced captured outputs and no top-level infra exception is recorded (`result.json:$.exception_info`; manifest). Test CTRF has no assertion messages; test wrappers often convert exceptions to `False`. Thus the exact WRONG/TIMEOUT/CRASH split is **UNVERIFIED**. The main wrong-answer mechanism above is **INFERRED** from the check names, output, author truth and judge reasons. A declared time limit in a final message is not a recorded infrastructure timeout.

## Fairness and QC fit

{fair} Evidence: {source_refs}.

| Check | Fit | Reason |
|---|---|---|
| IN-17 | {in17} | The instruction gives the deliverable and contract pointer; compare any input-specific hint against shipped data. |
| AL-1 | {al1} | The contract/data grounding and any withheld rule are described above. |
| AL-27 | {al27} | Named checks construct relevant fresh/hidden cases; full adjacent-pair trace was not rerun. |
| IN-8 | {in8} | Same reachability question as AL-1, including judged outcomes. |
| CL-4 | {cl4} | Compare whole-object/group equality with a one-fact perturbation; explicit exact-output wording counts as an exception. |

QC authority: `Terminal_2.0_Harbor_Harness/Input_Bundle_QC/01_Instruction_QC.md:38,47`; `05_Alignment_Integrity_QC.md:21,38`; `Final_checklist.md:491`. No task-local QC report was found (`run_evidence.json:$[{idx}].qc_files=[]`). These are read-only fit judgments, not a full QC run.
'''
    (OUT/'cards'/f'{uid}.md').write_text(text)
print('cards',len(items))
