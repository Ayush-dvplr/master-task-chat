import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

work = Path(__file__).resolve().parents[1]
for task in ('billing', 'pm25', 'pension'):
    for subject in ('blind', 'opus'):
        root = work / (subject + '-evidence') / (task + '-instrument')
        records = []
        for path in sorted(root.glob('*/diff.json')):
            record = json.loads(path.read_text())
            counts = {name: len(rows) for name, rows in record['diffs'].items() if rows}
            entry = {'case': path.parent.name, 'diff_count': record['diff_count'], 'counts': counts}
            if task == 'billing':
                offsets = defaultdict(set)
                for row in json.loads((path.parent / 'truth_offsets.json').read_text()):
                    offsets[row['handset']].add(row['offset'])
                entry['changed_handsets'] = {key: sorted(value) for key, value in offsets.items() if len(value) > 1}
            if task == 'pm25':
                rows = list(csv.DictReader((path.parent / 'data/receipt_journal.csv').open()))
                slots = Counter((row['channel'].strip().lower(), row['received_utc']) for row in rows)
                entry['duplicate_channel_minutes'] = sum(value > 1 for value in slots.values())
                offsets = json.loads((path.parent / 'truth_offsets.json').read_text())
                entry['stepped_units'] = {key: value for key, value in offsets.items() if len(value) > 1}
            if task == 'pension':
                entry['samples'] = {name: rows[:3] for name, rows in record['diffs'].items() if rows}
            records.append(entry)
        (root / 'analysis.json').write_text(json.dumps(records, indent=2, sort_keys=True) + '\n')
        print(task, subject, len(records), 'range', min(row['diff_count'] for row in records), max(row['diff_count'] for row in records))
        if task == 'pension':
            print(json.dumps(records, indent=2))
