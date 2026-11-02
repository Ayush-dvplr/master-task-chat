import csv
import json
from pathlib import Path

BASE = Path('/Users/mac/Desktop/Terminal Bench')
WORK = BASE / 'master_chat_work/20261031_stage2_calib/replay_A2'
GUIDS = {'pension': '9bb234eb-e964-5e0b-b8a9-37e9d58b887c', 'spectrum': 'fa7c65bd-ff01-50e7-b3ba-34fbd5df860d'}
FIELDS = ['task', 'check', 'weight', 'cause', 'root_fact', 'doc_ref', 'agent_ref', 'expected', 'actual', 'fields_wrong', 'notes']
rows = []
inventory = {}
for task, guid in GUIDS.items():
    source = BASE / 'anubis-stage-2' / guid
    agent = source / 'trajectories/claude-opus-5/run_1/artifacts/app/out'
    schema = str(source / 'environment/data/schema.md')
    oracle = str(source / 'solution/solve.py')
    summaries = json.loads((WORK / (task + '-instrument/summary.json')).read_text())
    inventory[task] = {'shipped_counts': {p.name: len(p.read_text().splitlines()) for p in (source / 'environment/data').glob('*.jsonl')}, 'cases': []}
    for case in summaries:
        name = case['scenario']
        evidence = WORK / (task + '-instrument') / name
        diff = json.loads((evidence / 'diff.json').read_text())
        actual = {p.name: json.loads(p.read_text()) for p in (evidence / 'actual').glob('*.json')}
        expected = {p.name: json.loads(p.read_text()) for p in (evidence / 'expected').glob('*.json')}
        facts = []
        if task == 'pension':
            facts.extend([
                ('P-COUNTS', schema + ':27', str(agent / 'calculate_pension.py') + ':158',
                 expected['data_quality.json']['record_counts'], actual['data_quality.json']['record_counts'],
                 'data_quality.json $.record_counts (16 missing/extra keys)',
                 'Child keys and inclusion of policy/plans are unspecified; inputs cannot establish output key names. Oracle ' + oracle + ':244'),
                ('P-DECISIONS', schema + ':29; ' + schema + ':9', str(agent / 'calculate_pension.py') + ':249',
                 expected['service_ledger.json']['revision_decisions'], actual['service_ledger.json']['revision_decisions'],
                 'service_ledger.json $.revision_decisions[*] (60 missing/extra key paths)',
                 'Only effective-service row keys are specified. Decision rows are 3 oracle keys versus 11 agent keys; winner_record_id versus winning_record_id; discarded_record_ids absent. Oracle ' + oracle + ':52'),
                ('P-INVALID-ID', schema + ':9; ' + schema + ':27', str(agent / 'calculate_pension.py') + ':237',
                 {'code': 'INVALID_SERVICE', 'record_id': 'SVC-BAD'}, {'code': 'INVALID_SERVICE', 'record_id': 'SR-BAD'},
                 'data_quality.json $.issues[code=INVALID_SERVICE].record_id; exception_register.json $.exceptions[code=INVALID_SERVICE].record_id',
                 'Rule names the issue but not whether record_id denotes the service or revision record. Oracle ' + oracle + ':98'),
            ])
            if name == 'revision_tie':
                facts.append(('P-TIE-ISSUE', schema + ':9; ' + schema + ':27', str(agent / 'calculate_pension.py') + ':215',
                              ['SVC-102'], ['SR-102B', 'SR-102Z'],
                              'data_quality.json $.issue_count and $.issues[code=REVISION_TIE_CONFLICT]; exception_register.json matching issues',
                              'Group-level singleton versus one issue per conflicting peer is not specified. Winning service itself matches. Oracle ' + oracle + ':51'))
            if name == 'valuation_clip':
                facts.append(('P-FUTURE-ISSUES', schema + ':11; ' + schema + ':19', str(agent / 'calculate_pension.py') + ':324; :340; :495',
                              ['INVALID_COLA:COLA-A-24', 'INVALID_REBASE:RB-102'], [],
                              'data_quality.json $.issue_count and $.issues; exception_register.json $.exceptions (insertion shifts downstream indices)',
                              'Oracle incorrectly labels valid future events invalid, while contract says ignore events after valuation; balance and benefit reports match. Oracle ' + oracle + ':119; :129'))
        else:
            facts.append(('S-GRANT-ROW', schema + ':53; ' + schema + ':13', str(agent / 'clear_spectrum.py') + ':927',
                          expected['grant_ledger.json']['effective_grants'], actual['grant_ledger.json']['effective_grants'],
                          'grant_ledger.json $.effective_grants[*].revision, .recorded_at, .status',
                          'Output effective-grant row fields are unspecified; input has 14 fields, agent projects 11 usable-grant fields. Oracle retains raw rows at ' + oracle + ':130; :318'))
            if name == 'revision_cells':
                facts.append(('S-CELL-ORDER', schema + ':13; ' + schema + ':53', str(agent / 'clear_spectrum.py') + ':927',
                              ['C2', 'C1'], ['C1', 'C2'], 'grant_ledger.json $.effective_grants[0].cells[0..1]',
                              'Cells are explicitly set-valued for comparison; no effective-row cell ordering is specified. No false conflict occurred. Oracle preserves raw winner order at ' + oracle + ':130'))
        for fact, doc, code, want, got, paths, note in facts:
            rows.append(dict(zip(FIELDS, [task, 'scenario_' + name, 5, 'UNFAIR', fact, doc, code,
                                         json.dumps(want, sort_keys=True), json.dumps(got, sort_keys=True), paths,
                                         note + '; Evidence ' + str(evidence / 'diff.json') + ' $.diffs. Weight is full check weight, NONADDITIVE across roots; deduplicate (task,check). AMPLIFIED is a secondary mechanism.'])))
        rows.append(dict(zip(FIELDS, [task, 'scenario_' + name, 5, 'AMPLIFIED', 'ALL-NINE-REPORT-HASH',
                                     str(source / 'tests/test_output.py') + (':104; :111; :157' if task == 'pension' else ':283; :298; :383'),
                                     str(evidence / 'diff.json'), case['expected_hash'], case['actual_hash'],
                                     str(case['diff_count']) + ' differing JSON path events; roots=' + ','.join(f[0] for f in facts),
                                     'SECONDARY NONADDITIVE, zero additional lost points. One changed manifest.engine_version also fails this hash on otherwise exact oracle reports. All roots above are nonbusiness details; array insertion shifts inflate path counts.'])))
        inventory[task]['cases'].append({**case, 'exact_reports': [key for key, value in diff['diffs'].items() if not value]})
with (WORK / 'CAUSES.csv').open('w', newline='') as output:
    writer = csv.DictWriter(output, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)
(WORK / 'inventory.json').write_text(json.dumps(inventory, indent=2, sort_keys=True) + '\n')
print('CAUSES:', len(rows), 'rows;', len({(r['task'], r['check']) for r in rows}), 'checks; primary UNFAIR=80 raw; secondary AMPLIFIED=80 overlapping raw')
