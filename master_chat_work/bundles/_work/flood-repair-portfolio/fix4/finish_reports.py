import hashlib
import json
from pathlib import Path


BASE = Path('/Users/mac/Desktop/Terminal Bench')
W = BASE / 'master_chat_work/bundles/_work/flood-repair-portfolio'
B = BASE / 'master_chat_work/bundles/flood-repair-portfolio'
T = BASE / 'Terminal_2.0_Harbor_Harness/Tasks_INPUT/flood-repair-portfolio'
OUT = BASE / 'master_chat_work/20261102_flood-repair-portfolio/fix_qcv4'
R = BASE / '_runs/20261102/flood-repair-portfolio/fix4-20261102T2359'
receipts = json.loads((OUT / 'lane_receipts.json').read_text())
lanes = receipts['lanes']


def files(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def tree_sha(contents):
    records = ''.join(hashlib.sha256(contents[name]).hexdigest() + '  ./' + name + '\n'
                      for name in sorted(contents, key=lambda value: ('./' + value).encode()))
    return hashlib.sha256(records.encode()).hexdigest()[:12]


current = files(B)
synced = files(T)
assert current == synced
assert not any('__pycache__' in name.split('/') or name.endswith('.pyc') for name in current)
before = files(W / 'fix4/before')
changed = sorted(name for name in current if current[name] != before[name])
assert changed == ['solution/TRUTH.md', 'tests/judge.toml', 'tests/test_output.py']
sha = tree_sha(current)
assert (OUT / 'cleanup_verified.txt').read_text().strip() == 'No own running containers or workers; all eight lanes ALL_DONE.'
precheck = (R / 'logs/precheck.log').read_text().splitlines()[-1]
assert precheck == 'PRECHECK CLEAN'
validator = (R / 'logs/validator.log').read_text()
assert '41 passed' in validator and '0 failed' in validator
xref = (R / 'logs/xref.log').read_text()
assert '0 findings' in xref
probe = (R / 'logs/predicate-probes-local.log').read_text()
assert 'ALL_DONE' in probe
live_cheat = (R / 'logs/live-cheat.log').read_text()
assert '"negative_fired": true' in live_cheat and 'ALL_DONE' in live_cheat
rows = '\n'.join(f"| {name} | {v['trial']} | {v['points']}/108 | {v['reward']} | {v['verifier_seconds']:.6f} | {v['negative_fired']} |"
                 for name, v in lanes.items())
judge = '/'.join(f'{v:.6f}' for v in receipts['pred_judge'])
final = '/'.join(f'{v:.6f}' for v in receipts['pred_final'])
report = f'''# Fix Report: flood-repair-portfolio, 420bf9a

## Scope and Findings
Fixed only TS-16, TS-19 and DS-27. TS-26 and AL-27 are KEPT under Ayush's 2 Nov 23:4x ruling, "2. Fix only items 1, 2 and 5"; see KEPT.md for current behavior, v4 references, v3 passes and the two carry-over exceptions. No instruction, contract, fixture, hidden book, generator, solver, positive weight or reward normalization changed. Only three bundle files changed: `{', '.join(changed)}`.

| Finding | Old text or behavior | New text or behavior and location | Playbook row |
|---|---|---|---|
| TS-16 access | `negative_program_reads_verifier_files` scanned source tokens, including honest comments, for -5. | Removed that helper, wrapper and registration. `tests/judge.toml:207` adds R16, `accesses_verifier_files`, -5, judged trajectory: executed reads/lists/copies of actual root `/tests` verifier files require a cited step id; comments, messages, repository-owned tests and absent evidence stand down. R14/R15 final-answer claims remain separate. | TS-16, AL-28, JD-8; G3 replacement owner R16 |
| TS-16 hardcoding | Three shipped identifiers or the shipped total in source could trigger -3. | `tests/test_output.py:1638` checks the cached H1 summary for shipped selected lists or shipped total replacing H1's different answers. Name and -3 registration at :1859 retained. `_holds` makes failed/absent runs silent. No new run or source inspection. | TS-16, AL-28 |
| TS-19 | Reruns compared raw document text (`first == second`), making whitespace and object-key serialization observable. | `tests/test_output.py:1628` parses each of nine JSON documents, then uses existing strict typed recursive equality; :1817 describes identical JSON values. Weight 3 remains. | TS-19: relax only stricter-than-contract serialization requirement |
| DS-27 | TRUTH described "r6", "harden_r6" and "Three r6 Harbor tests-only oracle lanes". | `solution/TRUTH.md:121` retains the 20 s limit and measured 1.5842-2.1044 / 1.9030-2.2411 s ranges without review narration; :240 retains three measured scores, verifier durations and trial binding without the history label. Digest fields at :231 were refreshed by script as the final bundle edit. | NEW (review-history wording), DS-22; no runtime or lever change |

Evidence maps, judge map, QC_DEFENCE and XREF are current. `WORK/fix4/scope_proof.json` verifies all other bundle files byte-identical, all untargeted function ASTs unchanged, R1-R15 unchanged and positive judge total 41. TRUTH's previously measured trial identifier and durations are deliberately retained, as required, not relabeled as this round's receipts.

## Rechecks and Witnesses
`WORK/RECHECK_FIX.md` records one row per touched owner. Rechecked tests TS-13/14/16/20/25/26 and CL-2/4; judge JD-2/5/6/7/9/13/15 and AL-28; documentation DS-22, IN-15/16/17, DS-21, AL-2/27 and CL-3. Changed tests retain one observable each and unchanged weights. R16 owns only verifier access; hardcoding owns substituted hidden answers; R14 and R15 own distinct final claims. Static stacking reports negative groups <=5; its heuristic positive-overlap hints do not overturn the explicit TS-26 KEPT ruling.

The separate self-contained shipped-answer cheat executes on real hidden H1, emits the independently computed shipped documents there, and fires the -3 negative using that cached run. The standard Harbor forgery still scores 16/108: its undeclared `_saved` sidecar is absent from the separate verifier, so hidden execution fails without output and correctly leaves the negative silent. Oracle and P both include the v4 identifier comment and the quoted `/tests` comment in executable copies, with AST identity checked against their originals; neither fires the negative. P's recorded trajectory contains no executed verifier-access step, so R16 stands down; generic system policy text is not an access event.

Fourteen Docker predicate probes pass: correct hidden output and unrelated wrong answers are silent; copied total, copied lists and both together fire; cached crash/timeout failure strings are silent; whitespace and object-key order pass rerun equality; bool-versus-int, list order, changed values, missing/invalid documents and failed runs do not. Crash/timeout probes exercise cached failure results, not separately executed crashing/timing-out solver programs. The helper uses the cached H1 result and the probe forbids a replacement run.

Vacuity: nop earns zero positive points; stub earns only the artifact-presence point. Review of unchanged positive judge R1-R13 finds no conduct, maintainability or rejection-list credit earned by an agent that supplies no program and performs no work. No positive tests were removed to obtain these results.

## Gates and Runtime
Live kit 5574d77e: structure_qc, instruction_qc, tests_qc and judge_qc each exit 0, zero warnings in their gate summaries. Validator: 41 passed, 0 failed, 0 warnings. Xref: 36 entries, 0 findings. PRECHECK last line: `{precheck}`. The precheck's extra informational JD-5 warnings concern unchanged R9/R10/R11; it also notes the historical absence of SELF_CHECKS.md. No new R16 warning.

Every lane used a live `exe_copy.py` copy, tests-only normalization, 4 GiB / 2 CPU caps, dockfree START=yes and a 4200-second outer alarm. No `--delete` Harbor flag or image pruning was used. All lane logs contain HARBOR_RC 0 and ALL_DONE. Every verifier duration is below 2430 seconds, 90% of the 2700-second verifier limit.

| Lane | Trial | Raw points | Tests-only reward | Verifier seconds | Hardcode negative |
|---|---|---|---|---|---|
{rows}

The first oracle2 admission lost a shared-resource race before creating a job; the retry queue waited for capacity and did not repeat a completed lane. The first lightweight probe tried an image already removed by normal Harbor cleanup; it was rerun successfully using the existing python:3.12-slim image under a fresh admission and the same caps. These are preserved in logs, not hidden failures.

### Trap survival
| Lever/probe | Before positive loss | After positive loss | Ratio | Separating cases kept | Verdict |
|---|---|---|---|---|---|
| Crowd lever against paid P | 57/108 | 57/108 | 100% | Yes; H1/H2/H3 six large rounds and generator unchanged | PASS |

P earns 51/108 = {receipts['paid_tests_percent']:.6f}% and fails the same fifteen optimal/summary/policy/regions/segments checks. Predicted judge lo/mid/hi: {judge}%; predicted final: {final}%. These are manual estimates using judge raw points 12/41, 12/41, 23/41, not executed model-judge results. Mid remains below 40, so no PAUSED threshold is reached.

## Handoff
Initial bundle tree: d4059c875b73. Final BUNDLE tree: {sha}. Tasks_INPUT tree: {sha}. `rsync -a --delete` completed; `diff -rq` is empty; neither tree has bytecode. No own running containers or workers remain; all eight lanes are complete. No protected harness, QC-kit, QC-copy, historical job or Anubis files were edited, and no git write operations occurred.

Not run: model-judge channel, paid attempt 5 and QC v5. Python and shell LSP servers are not installed (installation previously declined); TOML/Markdown LSPs are unconfigured. No clean-LSP claim is made; Python AST parsing, shell syntax checks, live static gates and real Docker runs supply the verification. Session rename used only 420bf9a; the helper reported no Codex match and matched the current OpenCode session. Next action belongs to the master: QC v5 recheck, then freeze and paid attempt 5.

Logs: `{R / 'logs'}`. Structured lane receipts: `lane_receipts.json`. Scope proof and probe source: `WORK/fix4/`.

## Lessons for the master
Keep source mentions separate from executed access evidence; retain the explicit TS-26/AL-27 KEPT authority in QC v5.
Keep resource-admission retries before job creation, and never repeat an ALL_DONE lane.
'''
(OUT / 'FIX_REPORT.md').write_text(report)
result = {'sha': '420bf9a', 'slug': 'flood-repair-portfolio', 'step': 'fix-qcv4', 'status': 'DONE',
          'fixed': ['TS-16', 'TS-19', 'DS-27'], 'kept': ['TS-26', 'AL-27'], 'changed_files': changed,
          'oracle': [lanes[f'oracle{i}']['reward'] for i in (1, 2, 3)],
          'owner': lanes['owner']['reward'], 'nop': lanes['nop']['reward'],
          'stub': lanes['stub']['reward'], 'forgery': lanes['forgery']['reward'],
          'paid_tests': receipts['paid_tests_percent'], 'pred_judge': receipts['pred_judge'],
          'pred_final': receipts['pred_final'],
          'verifier_seconds': {name: value['verifier_seconds'] for name, value in lanes.items()},
          'validator': 'P', 'xref_findings': 0, 'tree_sha': sha, 'tasks_input_synced': True,
          'report': str(OUT / 'FIX_REPORT.md')}
(OUT / 'result_420bf9a.json').write_text(json.dumps(result, indent=2) + '\n')
assert json.loads((OUT / 'result_420bf9a.json').read_text()) == result
print('REPORTS PASS', sha)
