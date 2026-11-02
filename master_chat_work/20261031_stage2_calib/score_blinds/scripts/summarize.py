import csv
import json
from collections import Counter
from pathlib import Path
import shutil

W = Path(__file__).resolve().parents[1]
B = Path('/Users/mac/Desktop/Terminal Bench')
S = B / '_runs/20261031/stage2-calib/score-b366e00'
NAMES = ('billing', 'pm25', 'pension')
SHAS = dict(zip(NAMES, ('d830ccb', '5c1644a', 'de212ed')))


def load(path):
    return json.loads(path.read_text())


def component(document, name):
    return next(item['detail'] for item in document['reward']['components'] if item['name'] == name)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


task_results = []
rows_by_task = {}
instrument_inventory = {}
for task in NAMES:
    observed = {}
    for kind in ('blind', 'oracle'):
        job = S / 'jobs' / f'b366e00-{task}-{kind}'
        verifiers = list(job.glob('*/verifier/reward-details.json'))
        assert len(verifiers) == 1, (task, kind, verifiers)
        target = W / f'{task}-{kind}-run'
        target.mkdir(exist_ok=True)
        shutil.copytree(verifiers[0].parent, target / 'verifier', dirs_exist_ok=True)
        shutil.copy2(job / 'result.json', target / 'job-result.json')
        observed[kind] = component(load(verifiers[0]), 'test_output')
    recorded = load(W / f'{task}-recorded/reward-details.json')
    opus = component(recorded, 'test_output')
    judge = component(recorded, 'judge')
    contract = load(W / f'{task}-contract.json')
    assert contract['test_source_unchanged']
    total = sum(item['weight'] for item in observed['blind']['criteria'] if item['weight'] > 0)
    assert observed['oracle']['score'] == total
    assert observed['blind']['score'] == opus['score']
    opus_criteria = {item['name']: item for item in opus['criteria']}
    ctrf = {item['name']: item for item in load(W / f'{task}-recorded/ctrf.json')['results']['tests']}
    rows = []
    cause_points = Counter()
    same_reports = 0
    case_records = []
    for item in observed['blind']['criteria']:
        name, weight = item['name'], item['weight']
        original = opus_criteria[name]
        assert weight == original['weight'] == ctrf[name]['weight']
        assert bool(original['raw']) == (ctrf[name]['status'] == 'passed')
        blind_lost = not bool(item['raw']) if weight > 0 else bool(item['raw'])
        opus_lost = not bool(original['raw']) if weight > 0 else bool(original['raw'])
        notes = []
        cause = ''
        if weight < 0:
            notes.append('Negative detector: raw=false / CTRF failed means penalty AVOIDED, not lost.')
        if blind_lost:
            case = name.removeprefix('scenario_') if task == 'pension' else name.split('_')[2 if task == 'billing' else 3]
            folder = W / 'blind-evidence' / f'{task}-instrument' / case
            diff = load(folder / 'diff.json')
            other_folder = W / 'opus-evidence' / f'{task}-instrument' / case
            other = load(other_folder / 'diff.json')
            cause = 'RULE-MISREAD' if task == 'pension' else 'UNFAIR'
            cause_points[cause] += abs(weight)
            exception = diff['exception']
            notes.append(f"wall={diff['wall_seconds']:.6f}s; exception={json.dumps(exception)}")
            if 'program_wall_seconds' in diff:
                assert diff['ok'] and exception is None
                notes.append(f"program_wall={diff['program_wall_seconds']:.6f}s; exact predicate returns false without raising")
            notes.append(f"AMPLIFIED: {diff['diff_count']} positional field-path mismatches, not independent root facts")
            root = 'per-day handset offsets contradict constant-clock contract' if task == 'billing' else 'piecewise unit offsets contradict constant-card contract'
            counts = {key: len(value) for key, value in diff['diffs'].items() if value}
            equality = all((folder / 'actual' / report).read_bytes() == (other_folder / 'actual' / report).read_bytes() for report in diff['diffs'])
            same_reports += equality
            if task == 'pension':
                assert diff['oracle_hash_verified'] and diff['one_fact_wrong_fails']
                expected = load(folder / 'expected/cola_ledger.json')
                actual = load(folder / 'actual/cola_ledger.json')
                filtered = {'events': [row for row in actual['events'] if row['event_kind'] != 'ACCRUAL']}
                assert filtered == expected
                financial = ('manifest.json', 'accrual_ledger.json', 'member_benefits.json', 'plan_rollups.json', 'audit_trace.json')
                assert all(not diff['diffs'][report] for report in financial)
                root = 'blind includes ACCRUAL rows in COLA ledger; removing only those rows makes that report exact'
                notes.append('Shared UNFAIR roots with Opus: unspecified record_counts/revision_decisions shapes and service issue-ID scope; valuation_clip also rejects valid future events. Additional ledger root is blind-only; no extra lost check because bundle predicate already fails.')
                notes.append(f"ACCRUAL rows extra={len(actual['events']) - len(expected['events'])}; COLA ledger field mismatches={len(diff['diffs']['cola_ledger.json'])}")
            else:
                assert equality, (task, case, 'blind/Opus output differs')
                analysis = next(row for row in load(folder.parent / 'analysis.json') if row['case'] == case)
                assert analysis['changed_handsets'] if task == 'billing' else analysis['stepped_units']
                notes.append('same_root_as_opus=YES; all actual report bytes identical in independent instrumentation')
            notes.append('root=' + root)
            notes.append('field_counts=' + json.dumps(counts, sort_keys=True))
            notes.append('evidence=' + str(folder / 'diff.json'))
            sample = next(({'report': report, **values[0]} for report, values in diff['diffs'].items() if values), None)
            notes.append('first_difference=' + json.dumps(sample, sort_keys=True))
            case_records.append({'check': name, 'case': case, 'blind_field_mismatches': diff['diff_count'], 'opus_field_mismatches': other['diff_count'], 'blind_wall_seconds': diff['wall_seconds'], 'exception': exception, 'field_counts': counts, 'same_report_bytes_as_opus': equality, 'root': root, 'evidence': str(folder / 'diff.json')})
        rows.append({'task': task, 'check': name, 'weight': weight, 'opus': 'LOST' if opus_lost else ('PASSED' if weight > 0 else 'AVOIDED'), 'blind': 'LOST' if blind_lost else ('PASSED' if weight > 0 else 'AVOIDED'), 'both_lost': str(blind_lost and opus_lost).lower(), 'cause_blind': cause, 'notes': '; '.join(notes)})
    with (W / f'CHECKS_{task}.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['task', 'check', 'weight', 'opus', 'blind', 'both_lost', 'cause_blind', 'notes'])
        writer.writeheader()
        writer.writerows(rows)
    estimate = load(W / f'{task}-blind-work' / f'result_{SHAS[task]}.json')
    entry = {'task': task, 'opus_tests': 100 * opus['score'] / total, 'blind_tests': 100 * observed['blind']['score'] / total, 'oracle_tests': 100.0, 'test_points_earned': opus['score'], 'test_points_possible': total, 'both_lost': sum(row['both_lost'] == 'true' for row in rows), 'only_opus': sum(row['opus'] == 'LOST' and row['blind'] != 'LOST' for row in rows), 'only_blind': sum(row['blind'] == 'LOST' and row['opus'] != 'LOST' for row in rows), 'blind_by_cause': dict(cause_points), 'blind_cause_units': 'raw lost test weight, mutually exclusive primary attribution', 'same_shared_root_as_opus': True, 'all_roots_same_as_opus': task != 'pension', 'blind_judge_estimate': {'lower': estimate['judge_lower'], 'upper': estimate['judge_upper']}, 'opus_judge_raw': judge['score'], 'opus_judge_possible': sum(item['weight'] for item in judge['criteria'] if item['weight'] > 0), 'instrumented_lost_checks': len(case_records), 'all_report_bytes_equal_to_opus_on_checks': same_reports}
    if task == 'pm25':
        entry['blind_judge_estimate']['note'] = 'Own JSON says 11-11; own Markdown flags an uncertain -3 R17 penalty, giving sensitivity 8-11.'
    task_results.append(entry)
    instrument_inventory[task] = case_records
    rows_by_task[task] = rows

write_json(W / 'INSTRUMENTATION.json', instrument_inventory)
result = {'sha': 'b366e00', 'step': 'stage2-score-blinds', 'status': 'DONE', 'score_units': 'percent of deterministic test component, not combined judge reward', 'tasks': task_results, 'report': str(W / 'FINDINGS.md')}
write_json(W / 'result_b366e00.json', result)

lines = [
    'VERDICT: All three blinds exactly match Opus scores and lost checks, but pension has an additional ledger mismatch, so score calibration does not establish complete root-cause equivalence.',
    '', '## Scores', '',
    '| task | Opus tests | blind tests | checks lost by both | only Opus | only blind | blind judge est | Opus judge |',
    '|---|---:|---:|---:|---:|---:|---:|---:|',
]
for entry in task_results:
    estimate = entry['blind_judge_estimate']
    judge_text = f"{estimate['lower']}-{estimate['upper']}/{entry['opus_judge_possible']:g}"
    if entry['task'] == 'pm25':
        judge_text = '11/58 (8-11 sensitivity)'
    score = f"{entry['test_points_earned']:g}/{entry['test_points_possible']:g} ({entry['opus_tests']:.4f}%)"
    lines.append(f"| {entry['task']} | {score} | {score} | {entry['both_lost']} | {entry['only_opus']} | {entry['only_blind']} | {judge_text} | {entry['opus_judge_raw']:g}/{entry['opus_judge_possible']:g} |")
lines += [
    '', 'All three independent oracle runs scored 100% (97/97, 110/110, 52/52). No judge was run. Blind estimates above are copied from each blind work folder, not newly scored; PM2.5 preserves both its JSON estimate and its Markdown penalty caveat. The original combined rewards (0.1568, 0.1661, 0.2225) are not test scores.',
    '', '## Causes And Calibration', '',
    '- Billing: same root as Opus YES, with all 13 report bytes identical on all 18 hidden extracts. Every generated extract changes at least one handset offset by day, contradicting `record_dictionary.md:19` (clock never adjusted). Example hidden 01 H-16 requires offsets -1 and +5. Both programs assume one fixed offset. Region gross/segment net threshold handling is explicitly correct, not a separate defect.',
    '- PM2.5: same root as Opus YES, with all nine report bytes identical on all 20 held-out extracts. Every extract has one or more offset steps, contradicting `record_dictionary.md:40-44` (offset holds for every card row). Example held-out 01 AQ525 changes from -3 to -12 at row 560; its received_packets expects 1749 versus 1256. Do not interpret every downstream mismatch as an independent clock or arithmetic mistake.',
    '- Pension: shared root as Opus YES, all roots identical NO. Both choose metadata schemas the contract leaves unspecified (`schema.md:27,29`), and both use SR-BAD where the frozen oracle requires SVC-BAD. A2 independently names these P-COUNTS, P-DECISIONS and P-INVALID-ID. The blind additionally writes ACCRUAL rows into the COLA ledger, unlike Opus. Removing only those rows makes that entire report match in every scenario. We attribute this to RULE-MISREAD of the revaluation-recording distinction in `schema.md:19`; the report stanza at line 33 does not explicitly enumerate allowed event kinds, so this attribution has residual contract ambiguity. In every scenario, manifest, accrual ledger, member benefits, plan rollups and audit trace match exactly. Valuation clipping also exposes the reference rejecting otherwise valid future events instead of merely ignoring them (schema lines 11,19).',
    '', 'Primary loss attribution counts each failed check once: billing UNFAIR 90/90 (100%), PM2.5 UNFAIR 100/100 (100%), pension RULE-MISREAD 40/40 (100%), with shared UNFAIR metadata blockers on those same 40 pension points. Overall: UNFAIR 190/230 = 82.61%; RULE-MISREAD 40/230 = 17.39%; other primary codes 0%. This is a transparent attribution convention, not a uniquely identifiable split: fixing only the blind COLA ledger still leaves all eight pension checks lost. If its event-kind omission is treated as under-specification too, UNFAIR rises to 230/230 (100%). No paid-run quality conclusion should hinge on that labeling choice.',
    '', 'AMPLIFIED is secondary, never added again to lost points. One clock assumption or one extra ledger event family expands into many positional field differences, and one bundle mismatch costs all five points. N below counts recursive field paths, including list displacement, not N independent semantic defects.',
    '', '| task | lost checks instrumented | blind mismatched field paths per check | execution |',
    '|---|---:|---:|---|',
]
for task in NAMES:
    records = instrument_inventory[task]
    counts = [row['blind_field_mismatches'] for row in records]
    times = [row['blind_wall_seconds'] for row in records]
    exception = 'AssertionError, empty message; program itself exits successfully' if task == 'pension' else 'No exception; successful program, exact predicate returns false'
    lines.append(f"| {task} | {len(records)} | {min(counts)}-{max(counts)} | {min(times):.3f}-{max(times):.3f}s per instrumentation case; {exception} |")
lines += [
    '', 'Every lost check has expected/actual report files, a field-level `diff.json`, exception type/message (null when no exception occurred), wall time, and truth offsets or a verified frozen oracle hash under `blind-evidence/<task>-instrument/<case>/`. Independent Opus runs are under `opus-evidence/`. `INSTRUMENTATION.json` indexes all 46 checks; each CSV links its exact trace and records its own N and root. No observed crash or timeout. Billing reference-only `__stdout__` is excluded to match the real REPORT_NAMES predicate; normalization script documents this instrumentation correction.',
    '', '## Gate Recommendation And Provenance', '',
    'Use a blind as a cheap directional gate for these test scores: all 46 lost positive checks agree and there are zero one-sided losses. Do not use shipped-data self-check PASS, exact score equality, or the blind judge estimate as evidence of fair hidden coverage or identical solution quality. Audit the task contract first, then inspect roots and financial invariants. Pension demonstrates a blind-only mismatch that the already-failing whole-bundle checks completely mask. These three cases do not establish calibration on unrelated tasks or a judge-score predictor.',
    '', 'All source tasks and blind folders were read-only. Harbor used only `--agent oracle`: frozen blind program copied to the exact instruction path and run on shipped data, or the original solution on the oracle copy. QC exe_copy disabled the judge and normalized deterministic weights; task check modules remain byte-identical. Infrastructure-only changes use cached local `python:3.12-slim`, remove the unused OpenHands installation and permit Docker Desktop network metadata. Instrumentation containers were network-disabled and unprivileged program runners remained unchanged. A2 instrument.py was copied unchanged and executed for pension; A1 scripts did not exist when clock instrumentation was authored, and its later diagnose.py was read for cross-checking. Original logs and captured verifier results are retained. The first instrumentation attempt failed before container creation because A2 had removed its image; rebuilding an owned cached image resolved it without grading edits.',
    '', 'Session rename was attempted first and returned NOT RENAMED (no matching board session). No subagents, paid agents, host pip, git, or web were used. Python/Bash language servers were unavailable; syntax checks, six real Harbor runs and six real instrumentation runs provide execution validation instead. See `VALIDATION.json` and `CLEANUP.json` for final validation and resource cleanup.',
]
(W / 'FINDINGS.md').write_text('\n'.join(lines) + '\n')
print(json.dumps(result, indent=2))
