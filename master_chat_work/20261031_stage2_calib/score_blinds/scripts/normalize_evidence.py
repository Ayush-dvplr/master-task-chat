import json
from pathlib import Path

work = Path(__file__).resolve().parents[1]
for subject in ('blind', 'opus'):
    root = work / (subject + '-evidence') / 'billing-instrument'
    summary = []
    for path in sorted(root.glob('*/diff.json')):
        record = json.loads(path.read_text())
        record['diffs'].pop('__stdout__', None)
        record['diff_count'] = sum(map(len, record['diffs'].values()))
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
        extra = path.parent / 'expected' / '__stdout__'
        extra.unlink(missing_ok=True)
        summary.append({key: value for key, value in record.items() if key != 'diffs'})
    (root / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
print('Normalized billing evidence to exactly REPORT_NAMES, excluding reference-only __stdout__.')
