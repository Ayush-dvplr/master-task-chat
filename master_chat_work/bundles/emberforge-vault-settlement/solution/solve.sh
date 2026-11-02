#!/bin/bash
# Oracle dispatcher for emberforge-vault-settlement.
set -euo pipefail
mkdir -p /app/out
cp /solution/solve.py /app/out/settle_vault.py
python3 /app/out/settle_vault.py /app/data /app/out
python3 - <<'ORACLE_CHECKS_PY'
#!/usr/bin/env python3
"""Run three small settlement probes against the delivered oracle program."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

DATA = Path(os.environ.get('ORACLE_DATA', '/app/data'))
PROGRAM = Path(os.environ.get('ORACLE_PROGRAM', '/app/out/settle_vault.py'))
FIELDS = ('entry_id', 'patch_id', 'day', 'workshop_id', 'smith_ref',
          'op', 'artifact_id', 'units', 'forge_ref')


def table(path: Path) -> list[dict]:
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def put_table(path: Path, rows: list[dict], fields=FIELDS) -> None:
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def half_even(numerator: int, denominator: int = 100) -> int:
    quotient, remainder = divmod(numerator, denominator)
    if remainder * 2 > denominator or (remainder * 2 == denominator and quotient % 2):
        return quotient + 1
    return quotient


def charge_for_a01(data: Path) -> int:
    """H1-H5 on A01 under the council rulings' GFS, half-even draw."""
    art = next(row for row in table(data / 'artifact_catalogue.csv') if row['artifact_id'] == 'A01')
    recipe = [row for row in table(data / 'recipe_editions.csv')
              if row['artifact_id'] == 'A01' and row['from_patch'] == 'P01']
    reagents = {row['reagent_id']: row for row in table(data / 'reagent_registry.csv')}
    highest = max(int(reagents[row['reagent_id']]['grade']) for row in recipe)
    charter = json.loads((data / 'season_charter.json').read_text())
    value = int(art['base_charge'])
    value = half_even(value * (100 + int(charter['grade_step']) * highest))
    value = half_even(value * int(charter['family_multiplier'][art['family']]))
    return value  # S is 100 percent because this probe sets scarcity_ceiling to zero.


def forge(entry_id: str, day: int, units: int = 1) -> dict:
    return dict(entry_id=entry_id, patch_id='P01', day=day,
                workshop_id='cinderhall', smith_ref='S999', op='forge',
                artifact_id='A01', units=units, forge_ref='')


def salvage(entry_id: str, day: int, source: str) -> dict:
    row = forge(entry_id, day)
    row.update(op='salvage', units=1, forge_ref=source)
    return row


def run_case(root: Path, rows: list[dict], cap: int) -> dict:
    data, out = root / 'data', root / 'out'
    shutil.copytree(DATA, data)
    out.mkdir()
    put_table(data / 'crafting_ledger.csv', rows)
    artifacts = table(data / 'artifact_catalogue.csv')
    for row in artifacts:
        if row['artifact_id'] == 'A01':
            row['base_charge'] = '101'
    put_table(data / 'artifact_catalogue.csv', artifacts, tuple(artifacts[0]))
    opening = table(data / 'vault_opening.csv')
    for row in opening:
        row['opening_units'] = '50000'
    put_table(data / 'vault_opening.csv', opening, tuple(opening[0]))
    charter = json.loads((data / 'season_charter.json').read_text())
    charter['scarcity_ceiling'] = 0
    charter['tier_charge_cap'] = {'1': 0, '2': 1000000, '3': cap}
    (data / 'season_charter.json').write_text(json.dumps(charter, indent=2) + '\n')
    done = subprocess.run([sys.executable, str(PROGRAM), str(data), str(out)],
                          text=True, capture_output=True, timeout=38)
    if done.returncode:
        raise RuntimeError(done.stderr[-500:])
    return {path.name: json.loads(path.read_text()) for path in out.glob('*.json')}


def check(name: str, okay: bool, detail: str) -> bool:
    print('%s %s %s' % (name, 'PASS' if okay else 'FAIL', detail), flush=True)
    return okay


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='emberforge_oracle_checks_') as temporary:
        base = Path(temporary)
        # The copied council rulings select GFS and half-even. Each probe changes
        # only records and charter quantities that leave that draw in force.
        scratch = base / 'expected'
        shutil.copytree(DATA, scratch)
        artifacts = table(scratch / 'artifact_catalogue.csv')
        for row in artifacts:
            if row['artifact_id'] == 'A01':
                row['base_charge'] = '101'
        put_table(scratch / 'artifact_catalogue.csv', artifacts, tuple(artifacts[0]))
        unit_charge = charge_for_a01(scratch)
        r1 = run_case(base / 'r1', [forge('PX001', 5, 2)], 1000000)
        r1_figure = r1['workshop_cinderhall.json']['charge_ember']
        one = check('R1', r1_figure == 2 * unit_charge,
                    'workshop charge %s; H1-H5 figure %s' % (r1_figure, 2 * unit_charge))
        r2 = run_case(base / 'r2', [forge('PX001', 5), salvage('PX002', 6, 'PX001'),
                                    forge('PX003', 7)], unit_charge)
        r2_finding = any(row['entry_id'] == 'PX003' and row['code'] == 'CAP_REACHED'
                         for row in r2['data_quality.json']['findings'])
        two = check('R2', not r2_finding and r2['workshop_cinderhall.json']['entries_admitted'] == 3,
                    'later forge settled %s; cap equals first charge %s' % (not r2_finding, unit_charge))
        r3 = run_case(base / 'r3', [forge('PX001', 5), forge('PX002', 6),
                                    salvage('PX003', 7, 'PX002'), forge('PX004', 8),
                                    forge('PX005', 9), salvage('PX006', 10, 'PX001')], 1000000)
        r3_finding = any(row['entry_id'] == 'PX006' and row['code'] == 'UNCREDITED_SALVAGE'
                         for row in r3['data_quality.json']['findings'])
        three = check('R3', not r3_finding and r3['summary.json']['credited_salvages'] == 2,
                      'later salvage credited %s; credited total %s' %
                      (not r3_finding, r3['summary.json']['credited_salvages']))
        return 0 if one and two and three else 1


if __name__ == '__main__':
    raise SystemExit(main())
ORACLE_CHECKS_PY
