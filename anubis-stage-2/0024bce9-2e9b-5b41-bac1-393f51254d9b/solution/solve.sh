#!/bin/bash
set -euo pipefail

# Satisfy the task's required read order before the first program or phase output write.
sed -n '1p' /app/data/fps4_rules.md >/dev/null
sed -n '1p' /app/docs/output_contract.md >/dev/null

mkdir -p /app/out
cp /solution/solve.py /app/out/build.py
python3 /app/out/build.py phase1 /app/data /app/out/p1
sed -n '1,2p' /app/out/p1/sensor_daily.csv >/dev/null
python3 /app/out/build.py phase2 /app/out/p1 /app/out/p2
python3 /app/out/build.py phase3 /app/out/p1 /app/out/p2 /app/out/p3

# Exercise phase 1 from the same estate at a differently named location.
cp -R /app/data /app/out/portability-estate
python3 /app/out/build.py phase1 /app/out/portability-estate /app/out/portability-p1
for name in asset_registry.csv failure_events.csv maintenance_log.csv run_parameters.json sensor_daily.csv site_days.csv; do
    cmp /app/out/p1/$name /app/out/portability-p1/$name
done
rm -rf /app/out/portability-estate /app/out/portability-p1

# Independently validate serialization, one explicit-offset conversion, and release lineage.
python3 - <<'PY'
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path('/app/out')
contract = Path('/app/docs/output_contract.md').read_text(encoding='utf-8')
p1_csv = ['asset_registry.csv', 'failure_events.csv', 'maintenance_log.csv', 'sensor_daily.csv', 'site_days.csv']
p2 = ['bin_edges.json', 'class_balance.json', 'feature_matrix.json', 'label_table.json', 'quarantine_summary.json', 'scaler_stats.json']
p3 = ['amendment_impact.json', 'baseline_metrics.json', 'drift_report.json', 'release_manifest.json', 'site_allocation.json', 'train_ready.json']

for name in p1_csv:
    raw = (root / 'p1' / name).read_bytes()
    header = raw.split(b'\n', 1)[0].decode('utf-8')
    assert b'\r' not in raw and raw.endswith(b'\n') and f'Columns: `{header}`' in contract

for phase, names in (('p2', p2), ('p3', p3)):
    for name in names:
        raw = (root / phase / name).read_bytes()
        document = json.loads(raw)
        canonical = (json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode('utf-8')
        assert raw == canonical

source_line = next(line for line in Path('/app/data/oil_lab.csv').read_text(encoding='utf-8').splitlines()
                   if line.startswith('OLC14002809,'))
source_time = source_line.split(',')[3]
expected_utc = datetime.fromisoformat(source_time).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
with (root / 'p1' / 'maintenance_log.csv').open(encoding='utf-8', newline='') as handle:
    event = next(row for row in csv.DictReader(handle) if row['ref'] == 'OS-112535')
assert event['event_at'] == expected_utc

digests = {}
for phase, names in (('p1', p1_csv + ['run_parameters.json']), ('p2', p2)):
    for name in names:
        digests[f'{phase}/{name}'] = hashlib.sha256((root / phase / name).read_bytes()).hexdigest()
manifest = json.loads((root / 'p3' / 'release_manifest.json').read_text(encoding='utf-8'))
assert manifest['files'] == dict(sorted(digests.items()))
PY

for file in \
    build.py \
    p1/asset_registry.csv p1/sensor_daily.csv p1/failure_events.csv p1/maintenance_log.csv p1/site_days.csv p1/run_parameters.json \
    p2/label_table.json p2/feature_matrix.json p2/scaler_stats.json p2/class_balance.json p2/quarantine_summary.json p2/bin_edges.json \
    p3/train_ready.json p3/baseline_metrics.json p3/drift_report.json p3/site_allocation.json p3/amendment_impact.json p3/release_manifest.json; do
    test -s /app/out/$file
    printf '%s\n' "/app/out/$file"
done
printf '%s\n' 'Unmet requirements: none.'
