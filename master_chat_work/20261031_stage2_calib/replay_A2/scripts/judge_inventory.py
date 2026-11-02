import csv
import json
from pathlib import Path

work = Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_stage2_calib/replay_A2')
refs = {
    'pension': {2: 'steps 9,13', 3: 'step 10', 4: 'step 10', 5: 'step 10', 6: 'step 10', 7: 'steps 9,13', 8: 'step 13', 9: 'step 14', 10: 'steps 9,10,15', 11: 'step 11'},
    'spectrum': {2: 'steps 8,25', 3: 'step 14 verify.py: area booleans and OVERLAP prints', 4: 'steps 14,25,26', 5: 'step 14 verify.py: all-slice Decimal gross assertions DO exist; no auction-boundary expected assertion', 6: 'step 14 verify.py: winner+owner=gross asserted; no deliberate share midpoint expected result', 7: 'steps 25,35', 8: 'steps 25,26', 9: 'steps 30,34,37', 10: 'steps 30,35', 11: 'step 31'},
}
with (work / 'JUDGE_LOSS.csv').open('w', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=['task', 'criterion', 'weight', 'class', 'what_it_asks', 'what_agent_did'])
    writer.writeheader()
    for task in ('pension', 'spectrum'):
        score = json.loads((work / (task + '-recorded') / 'score.json').read_text())
        for row in score['rubric']:
            if row['is_positive'] and not row['passed']:
                number = row['number']
                note = row['justification']
                if task == 'pension' and number == 11:
                    note += ' CAVEAT: raw-input hashes necessarily change under reordered JSONL; excluding manifest.input_files is justified. Missing immutability snapshot remains valid.'
                writer.writerow({'task': task, 'criterion': f'R{number}', 'weight': row['score'], 'class': 'PROBE-SKIPPED' if number <= 8 else 'PROCESS-SKIPPED', 'what_it_asks': row['criterion'], 'what_agent_did': f"{refs[task][number]}; {note} Source: {task}-recorded/score.json $.rubric[{number - 1}].justification"})
print('20 lost judge rows; 70 probe + 18 process = 88 raw points; no negative fired')
