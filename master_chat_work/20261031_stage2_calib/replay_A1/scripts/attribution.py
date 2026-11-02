import csv
import json
from pathlib import Path

WORK = Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_stage2_calib/replay_A1')
BASE = Path('/Users/mac/Desktop/Terminal Bench/anubis-stage-2')
IDS = {'billing': '59417607-2254-5165-b703-0d5a4aeb7367', 'pm25': '98ed74c1-19ac-5ec8-adaf-392a172d4600', 'royalty': '75407a55-6665-505e-95d8-5ff9bdb3384f'}
cause_rows, judge_rows = [], []
for task, task_id in IDS.items():
    root = BASE / task_id
    evidence = WORK / 'evidence' / task
    details = json.loads((evidence / 'reward-details.json').read_text())
    components = {component['name']: component['detail'] for component in details['reward']['components']}
    lost = [criterion for criterion in components['test_output']['criteria'] if criterion['weight'] > 0 and not criterion['value']]
    for index, criterion in enumerate(lost, 1):
        case_path = evidence / f'case_{index:02d}.json'
        case = json.loads(case_path.read_text())
        deltas = [(name, delta) for name, report in case['reports'].items() for delta in report.get('differences', [])]
        name, first = deltas[0]
        match task:
            case 'billing':
                fact = 'Reference permits a different handset offset each day; authoritative dictionary says never adjusted. All hidden profiles introduce changes.'
                doc = f'{root}/environment/data/record_dictionary.md:19; {root}/tests/test_output.py:935-961'
                agent = f'{root}/trajectories/claude-opus-5/run_1/artifacts/app/out/transform.py:217-299,344-346'
            case 'pm25':
                fact = 'Independent per-unit maximum-match voting chooses echoed shared-channel offsets for constant-clock units; correcting only stepped units still fails this check.'
                doc = f'{root}/environment/data/record_dictionary.md:40-44,85-90; {root}/tests/test_output.py:689-719,1142-1174'
                agent = f'{root}/trajectories/claude-opus-5/run_1/artifacts/app/out/derive_report.py:236-260,314-326'
            case 'royalty':
                fact = 'INVALID_STATEMENT issue ID is not specified: oracle chooses statement_id ST-BAD; agent chooses winner record_id ST-BAD-A. One fact is copied into two reports.'
                doc = f'{root}/environment/data/schema.md:9,39,51; {root}/solution/solve.py:51'
                agent = f'{root}/trajectories/claude-opus-5/run_1/artifacts/app/out/calculate_royalties.py:315'
        cf = json.loads((evidence / f'counterfactual_{index:02d}.json').read_text())
        notes = f'Full expected/actual fields: {case_path} $.reports; exception={case["exception"]}; ok={case.get("ok")}; program_seconds={case.get("program_seconds")}; AMPLIFIED is a secondary mechanism, not a second allocated weight; wrong reports={case["reports_wrong"]}; counterfactual fields_wrong={cf.get("fields_wrong")}, ok={cf.get("ok")}. Array counts are positional structural leaf deltas, not independent causal mistakes.'
        row = {'task': task, 'check': criterion['name'], 'weight': criterion['weight'], 'cause': 'UNFAIR', 'root_fact': fact, 'doc_ref': doc, 'agent_ref': agent, 'expected': f'{name} {first["path"]} = {json.dumps(first["expected"])}', 'actual': f'{name} {first["path"]} = {json.dumps(first["actual"])}', 'fields_wrong': case['fields_wrong'], 'notes': notes}
        if task == 'pm25':
            separation = json.loads((evidence / 'clock_separation.json').read_text())[index - 1]
            assert separation['constant_unit_errors'] and separation['probes']['stepped_only']['reports_wrong']
            row.update(cause='LATENT-WRONG', expected=json.dumps({unit: error['expected'] for unit, error in separation['constant_unit_errors'].items()}), actual=json.dumps({unit: error['actual'] for unit, error in separation['constant_unit_errors'].items()}))
            row['notes'] += f' Jointly sufficient failures: primary allocation to proven in-contract constant-unit offset error; coexisting UNFAIR clock-step cause below gets zero additional weight. Separation evidence: {evidence}/clock_separation.json index={index}; original fields_wrong counts all causes, not just this root.'
            secondary = dict(row)
            stepped = {unit: segments for unit, segments in separation['truth_offsets'].items() if len(segments) > 1}
            secondary.update(weight=0, cause='UNFAIR', root_fact='Coexisting within-card clock changes contradict the whole-card offset contract; zero allocated weight prevents double-counting the same failed +5 check.', doc_ref=f'{root}/environment/data/record_dictionary.md:40-44; {root}/tests/test_output.py:313-324,621-675', expected=json.dumps(stepped), actual=json.dumps({unit: separation['inferred_offsets'][unit] for unit in stepped}))
            cause_rows.append(secondary)
        cause_rows.append(row)
    for criterion in components['judge']['criteria']:
        weight, value = criterion['weight'], criterion['value']
        if not ((weight > 0 and not value) or (weight < 0 and value)):
            continue
        number = int(criterion['id'][1:])
        if weight < 0:
            classification = 'NEGATIVE-FIRED'
        elif task in ('billing', 'pm25') and number <= (8 if task == 'billing' else 10):
            classification = 'FIGURE-WRONG'
        elif task == 'royalty' and 2 <= number <= 8:
            classification = 'PROBE-SKIPPED'
        elif task == 'royalty' and number == 14:
            classification = 'OTHER'
        else:
            classification = 'PROCESS-SKIPPED'
        refs = {'billing': 'steps[37] (step_id 38, min-unexplained search); steps[56] (step_id 57, final figures/check claims); transform.py:95,217-299', 'pm25': 'steps[20] (step_id 21, what-if output); steps[42] (step_id 43, 19 cached factors); steps[48] (step_id 49, claims 55/66); derive_report.py:236-260,308-314', 'royalty': 'steps[12] (step_id 13, excludes manifest from shuffle comparison); steps[14] (step_id 15, synthetic outputs printed); steps[15] (step_id 16, serialization/audit assertions); steps[16] (step_id 17, final claims)'}[task]
        judge_rows.append({'task': task, 'criterion': criterion['id'] + ' ' + criterion['name'], 'weight': abs(weight), 'class': classification, 'what_it_asks': criterion['description'], 'what_agent_did': criterion.get('reasoning', '') + ' Evidence: ' + str(evidence / 'trajectory_readable.txt') + '; original agent/trajectory.json ' + refs})

for filename, rows in (('CAUSES.csv', cause_rows), ('JUDGE_LOSS.csv', judge_rows)):
    with (WORK / filename).open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(filename, len(rows), 'rows', sum(row['weight'] for row in rows), 'lost raw weight')
