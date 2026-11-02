#!/bin/bash
# Oracle: read the contract, deliver the planner, check it on hand-built fixtures,
# produce the plan with the delivered planner, then verify the plan and report.
set -euo pipefail
umask 077
export PYTHONDONTWRITEBYTECODE=1
scratch=$(mktemp -d /tmp/strata-author.XXXXXXXX)
trap 'rm -rf -- "$scratch"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Read the governing document before creating any plan artifacts.
python3 - <<'PY'
from pathlib import Path
print(Path('/app/data/SPEC-STRATA.md').read_text(encoding='utf-8'), flush=True)
PY

# Deliver the planner first; every run below executes the delivered file itself.
mkdir -p /app/out
python3 - <<'PY'
from pathlib import Path
allowed = {
    "object_inventory.jsonl", "device_topology.json", "extent_map.tsv",
    "symlink_topology.jsonl", "mutation_replay.jsonl", "scope_resolution.csv",
    "link_clusters.jsonl", "resume_state.jsonl", "xattr_ledger.csv",
    "special_nodes.tsv", "placement.csv", "sharing_expansion.jsonl",
    "allocation_projection.csv", "delta_workset.tsv", "metadata_workset.jsonl",
    "window_schedule.tsv", "split_ledger.jsonl", "descriptor_budget.csv",
    "cutover_sequence.txt", "rollback_plan.jsonl", "conservation.json",
    "cli_contract.json", "manifest.json", "summary.json", "stratactl.py",
}
extra = sorted(p.name for p in Path('/app/out').iterdir() if p.name not in allowed)
assert not extra, '/app/out holds undeclared entries: {}'.format(extra)
PY
cp /solution/solve.py /app/out/stratactl.py
planner=/app/out/stratactl.py

python3 - "$scratch" "$planner" <<'PY'
import csv
import json
import subprocess
import sys
from pathlib import Path

root, planner = Path(sys.argv[1]), sys.argv[2]
corpus, output = root / 'fixture', root / 'fixture-out'
corpus.mkdir()

def table(name: str, fields: str, rows: list[tuple]) -> None:
    records = [dict(zip(fields.split(), row, strict=True)) for row in rows]
    (corpus / name).write_text(json.dumps({'records': records}) + '\n', encoding='ascii')
    print('Given fixture', name, json.dumps(records), flush=True)

def lines(name: str) -> list:
    return [json.loads(line) for line in (output / name).read_text().splitlines()]

def check(label: str, expected, observed) -> None:
    passed = expected == observed
    print(label, 'SPEC expectation=', repr(expected), 'observed=', repr(observed),
          'PASS' if passed else 'FAIL', flush=True)
    assert passed, label

# Given: pool rounding is one byte, device split rounding is four bytes.
table('p', 'pool_id alloc_unit root_depth_cap region', [('p', 1, 20, 'fixture')])
table('b', 'pool_id rev barrier_seq effective_seq', [('p', 1, 10, 1)])
table('c', 'device_id rev capacity_raw capacity_unit existing_used_raw existing_used_unit reserve_ppm effective_seq',
      [(d, 1, 10000, 'B', 0, 'B', 0, 1) for d in ('C', 'D', 'S')])
table('g', 'slot_id device_id rev share_domain spill_device online alloc_unit effective_seq',
      [(d, d, 1, domain, d, 'true', 4, 1) for d, domain in
       [('C', 'alpha'), ('D', 'beta'), ('S', 'split')]])
table('w', 'device_id window_index io_budget_raw io_budget_unit descriptor_budget',
      [('S', 0, 10, 'B', 1), ('S', 1, 9, 'B', 1),
       ('C', 0, 1000, 'B', 20), ('D', 0, 1000, 'B', 20)])
table('r', 'route_id class pool_id device_id',
      [(c, c, 'p', d) for c, d in [('tin', 'S'), ('gold', 'C'), ('silver', 'D')]])
regular = [(1, 15, 'tin'), (2, 3, 'gold'), (3, 3, 'gold'), (4, 0, 'gold'),
           (5, 4, 'gold'), (6, 2, 'gold'), (7, 2, 'silver'), (8, 2, 'gold')]
links = {20: '/cycle-b', 21: '/cycle-a'}
links.update({ino: f'/chain-{ino + 1}' for ino in range(30, 38)})
links[38] = '/caf\u00e9/file'
table('o', 'ino kind size_raw size_unit mode_raw uid gid mtime_ns class_raw pool_id link_count state gen',
      [(ino, 'regular', size, 'B', '644', 0, 0, 0, cls, 'p', 1, 'live', 1)
       for ino, size, cls in regular] +
      [(ino, 'symlink', 0, 'B', '777', 0, 0, 0, 'gold', 'p', 1, 'live', 1)
       for ino in links])
paths = [(1, '/split', 0, 'nfc'), (2, '/nil', 0, 'nfc'), (3, '/zero', 0, 'nfc'),
         (4, '/caf\u00e9//./file', 0, 'nfc'),
         (4, 'cafe\u0301/x/../file/', 1, 'nfd'),
         (5, '/a', 0, 'nfc'), (6, '/z', 0, 'nfc'),
         (7, '/b', 0, 'nfc'), (8, '/a', 0, 'nfc'),
         (20, '/cycle-a', 0, 'nfc'), (21, '/cycle-b', 0, 'nfc')]
paths += [(ino, f'/chain-{ino}', 0, 'nfc') for ino in range(30, 39)]
table('paths', 'ino path_raw ordinal form', paths)
table('claims', 'claim_id ino set_name', [(str(ino), ino, 'fixture')
      for ino in [r[0] for r in regular] + list(links)])
table('links', 'ino target_raw form', [(ino, target, 'nfc') for ino, target in links.items()])
extents = [(1, 0, 0, 13, 'B', 'split', 'none', 1), (1, 1, 13, 2, 'B', 'reuse', 'none', 1),
           (2, 0, 0, 3, 'B', 'nil', 'none', 1), (3, 0, 0, 3, 'B', 'zero', 'none', 1)]
extents += [(ino, index, index * 2, 2, 'B', 'shared', 'shared', 1)
            for ino, index in [(5, 0), (5, 1), (6, 0), (7, 0), (8, 0)]]
table('e', 'ino ext_index offset length_raw length_unit physical_id flags gen', extents)
table('j', 'ino ext_index bytes_committed seq pool_id',
      [(2, 0, 'NIL', 10, 'p'), (3, 0, 0, 10, 'p')])
# When: run the delivered planner as a command, without importing it.
command = [sys.executable, planner, str(corpus), str(output)]
print('When fixture execution:', command, flush=True)
subprocess.run(command, check=True)
# Then: NFC plus removal of empty/dot/parent segments gives this common path.
cluster = next(r for r in lines('link_clusters.jsonl') if r['ino'] == 4)
check('canonical equivalence of raw paths ' + repr(paths[3:5]),
      ('/caf\u00e9/file', [], 1),
      (cluster['primary_path'], cluster['member_paths'], cluster['arrival_forms']))
resume = {r['ino']: r for r in lines('resume_state.jsonl')}
for ino, committed, status in [(2, -1, 'never_started'), (3, 0, 'zeroed')]:
    check(f'NIL versus zero: ino={ino} raw committed={"NIL" if ino == 2 else 0} length=3 pool_unit=1 barrier=10',
          (3, committed, status), (resume[ino]['expected'], resume[ino]['committed'], resume[ino]['status']))
topology = {r['ino']: r for r in lines('symlink_topology.jsonl')}
# The cycle visits B,A,B: two followed links, then repeated target, no extra hop.
check('symlink cycle /cycle-a -> /cycle-b -> /cycle-a -> /cycle-b(repeated)',
      ('cyclic', 2), (topology[20]['resolution'], topology[20]['hops']))
for start in (30, 31):
    chain = list(range(start + 1, 39))
    expected = ('capped', 8) if len(chain) >= 8 else ('inside', len(chain))
    check(f'symlink hop cap: start=/chain-{start} followed symlinks={chain} then regular=/cafe\\u0301/file; cap before next target',
          expected, (topology[start]['resolution'], topology[start]['hops']))
with (output / 'window_schedule.tsv').open() as handle:
    schedule = list(csv.DictReader(handle, delimiter='\t'))
# Fresh empty windows admit one inode each. 13>max(10,9); floor(10/4)*4=8,
# residual 5 fits unrounded room 9 and must not be rounded down to 4.
expected_chunks = [(0, 10 // 4 * 4), (1, 13 - 10 // 4 * 4)]
check('non-aligned split: size=13 unit=4 budgets=[10,9] descriptors=[1,1] initially empty/open sets={}',
      expected_chunks, [(int(r['window_index']), int(r['bytes'])) for r in schedule
                        if r['ino'] == '1' and r['ext_index'] == '0'])
split = next(r for r in lines('split_ledger.jsonl') if r['ino'] == 1 and r['ext_index'] == 0)
check('non-aligned split: final remainder=5 indivisible by unit=4; fully placed', (13, 0),
      (split['placed_bytes'], split['residual_bytes']))
# Independent holder ordering: path, inode, extent index, separately per domain.
holders = [('alpha', '/a', 5, 0), ('alpha', '/a', 5, 1),
           ('alpha', '/z', 6, 0), ('beta', '/b', 7, 0), ('alpha', '/a', 8, 0)]
owners = [min(h[1:] for h in holders if h[0] == domain) for domain in ('alpha', 'beta')]
sharing = next(r for r in lines('sharing_expansion.jsonl') if r['physical_id'] == 'shared')
check('cross-domain ownership: physical_id=shared holders(domain,path,ino,index)=' + repr(holders),
      (['alpha', 'beta'], [h[1] for h in owners]), (sharing['domains'], sharing['owners']))
with (output / 'delta_workset.tsv').open() as handle:
    work = list(csv.DictReader(handle, delimiter='\t'))
check('cross-domain ownership: only per-domain lowest(path,inode,index) copies; other holders reflink',
      [(h[1], h[2]) for h in owners],
      [(int(r['ino']), int(r['ext_index'])) for r in work if r['physical_id'] == 'shared'])
# Extent 0 leaves room 2 in window 0, with inode 1 already open and budget full.
check('descriptor reuse: S/window0 descriptor_budget=1: inode1 ext0 bytes8 then ext1 bytes2, reuse despite full descriptor budget',
      [(0, 8, 1), (1, 2, 0)],
      [(int(r['ext_index']), int(r['bytes']), int(r['descriptor_opened'])) for r in schedule
       if r['device_id'] == 'S' and r['window_index'] == '0'])
with (output / 'descriptor_budget.csv').open() as handle:
    budget = next(r for r in csv.DictReader(handle) if r['device_id'] == 'S' and r['window_index'] == '0')
check('descriptor reuse: two placements, one distinct inode => one opening', 1, int(budget['descriptors_used']))
PY

# Final generation with the delivered planner, then two repeat runs outside delivery.
printf '%s\n' "Final generation: python3 $planner /app/data /app/out"
python3 "$planner" /app/data /app/out
for run in a b; do
    printf '%s\n' "Repeat run $run: python3 $planner /app/data $scratch/repeat-$run"
    python3 "$planner" /app/data "$scratch/repeat-$run"
done
python3 - "$scratch/repeat-a" "$scratch/repeat-b" <<'PY'
import csv
import hashlib
import json
import stat
import sys
from pathlib import Path

out, repeats = Path('/app/out'), [Path(argument) for argument in sys.argv[1:]]

def rows(name: str) -> list:
    with (out / name).open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle, delimiter='\t' if name.endswith('.tsv') else ','))

def records(name: str) -> list:
    return [json.loads(line) for line in (out / name).read_text(encoding='utf-8').splitlines()]

def check(label: str, expected, observed) -> None:
    passed = expected == observed
    print(label, 'independent expectation=', repr(expected), 'observed=', repr(observed),
          'PASS' if passed else 'FAIL', flush=True)
    assert passed, label

artifacts = '''object_inventory.jsonl device_topology.json extent_map.tsv symlink_topology.jsonl
mutation_replay.jsonl scope_resolution.csv link_clusters.jsonl resume_state.jsonl xattr_ledger.csv
special_nodes.tsv placement.csv sharing_expansion.jsonl allocation_projection.csv delta_workset.tsv
metadata_workset.jsonl window_schedule.tsv split_ledger.jsonl descriptor_budget.csv cutover_sequence.txt
rollback_plan.jsonl conservation.json cli_contract.json manifest.json summary.json'''.split()
delivered = artifacts + ['stratactl.py']
check(f'flat delivery {out}', sorted(delivered), sorted(p.name for p in out.iterdir()))
assert all(stat.S_ISREG((out / name).lstat().st_mode) for name in delivered)
for repeat in repeats:
    check(f'repeat run writes exactly the artifacts {repeat}', sorted(artifacts),
          sorted(p.name for p in repeat.iterdir()))
for name in artifacts:
    payloads = [(directory / name).read_bytes() for directory in (out, *repeats)]
    check(f'byte comparison across {out} and both repeat runs: {name}', True,
          all(payload == payloads[0] for payload in payloads))
manifest = json.loads((out / 'manifest.json').read_text())['artifacts']
for entry in manifest:
    payload = (out / entry['name']).read_bytes()
    check('manifest entry recomputed from written bytes ' + str(out / entry['name']),
          (hashlib.sha256(payload).hexdigest()[:16], len(payload), payload.count(b'\n')),
          (entry['digest'], entry['bytes'], entry['rows']))
digest = hashlib.sha256('\n'.join(entry['digest'] for entry in manifest).encode()).hexdigest()[:16]
check('summary manifest_digest recomputed from the manifest', digest,
      json.loads((out / 'summary.json').read_text())['manifest_digest'])
placements = {int(r['ino']): r for r in rows('placement.csv')}
primary = {r['ino']: r['primary_path'] for r in records('link_clusters.jsonl')}
extents = rows('extent_map.tsv')
groups = {}
for r in extents:
    ino = int(r['ino'])
    if ino in placements and r['physical_class'] in ('data', 'reserved'):
        groups.setdefault((r['physical_id'], placements[ino]['share_domain']), []).append(r)
# Reconstruct ownership, rather than counting every holder's resumed/reserved bytes.
owned = [min(group, key=lambda r: (primary[int(r['ino'])], int(r['ino']), int(r['ext_index'])))
         for group in groups.values()]
durable = {(r['ino'], r['ext_index']) for r in records('resume_state.jsonl') if r['status'] == 'durable'}
schedule, splits = rows('window_schedule.tsv'), records('split_ledger.jsonl')
devices = json.loads((out / 'device_topology.json').read_text())['devices']
conservation = json.loads((out / 'conservation.json').read_text())
for device in devices:
    name = device['device_id']
    attributed = sum(int(r['attributed_bytes']) for r in placements.values() if r['device'] == name)
    copied = sum(int(r['bytes']) for r in schedule if r['device_id'] == name)
    local = [r for r in owned if placements[int(r['ino'])]['device'] == name]
    resumed = sum(int(r['raw_physical_bytes']) for r in local
                  if r['physical_class'] == 'data' and (int(r['ino']), int(r['ext_index'])) in durable)
    reserved = sum(int(r['raw_physical_bytes']) for r in local if r['physical_class'] == 'reserved')
    deferred = sum(r['residual_bytes'] for r in splits if r['device_id'] == name)
    residual = attributed - copied - resumed - reserved - deferred
    expected = dict(zip(('device_id', 'attributed_bytes', 'copied_bytes', 'resumed_bytes',
                         'reserved_bytes', 'deferred_bytes', 'residual_bytes'),
                        (name, attributed, copied, resumed, reserved, deferred, residual), strict=True))
    check('conservation recomputed from placement, schedule, ownership and resume state', expected,
          next(r for r in conservation['devices'] if r['device_id'] == name))
    check('independently computed residual device=' + name, 0, residual)
check('all devices balanced', (len(devices), 0),
      (conservation['balanced_devices'], conservation['unbalanced_devices']))

budget, work = rows('descriptor_budget.csv'), rows('delta_workset.tsv')
metadata, sharing = records('metadata_workset.jsonl'), records('sharing_expansion.jsonl')
allocation = rows('allocation_projection.csv')
cutover = (out / 'cutover_sequence.txt').read_text(encoding='utf-8').splitlines()
last_round = max(int(r['round']) for r in placements.values())
figures = [
    ('Sum of utilisation figures in parts per million', sum(int(r['utilisation_ppm']) for r in budget)),
    ('Window placements that opened a descriptor', sum(int(r['descriptor_opened']) for r in schedule)),
    ('Total scheduled bytes across every window', sum(int(r['bytes']) for r in schedule)),
    ('Total copy bytes in delta work set', sum(int(r['copy_bytes']) for r in work)),
    ('Total bytes recorded against metadata operations', sum(r['bytes'] for r in metadata)),
    ('Total attributed bytes across every device', sum(int(r['attributed_bytes']) for r in placements.values())),
    ('Sum of headroom across every device', sum(int(r['headroom_bytes']) for r in allocation)),
    ('Inode on five hundredth data row of window schedule', int(schedule[499]['ino'])),
    ('Total scheduled bytes in window index zero', sum(int(r['bytes']) for r in schedule if int(r['window_index']) == 0)),
    ('Total extra bytes from cross-domain sharing', sum(r['expanded_bytes'] for r in sharing)),
    ('Total deferred bytes across every device', sum(r['residual_bytes'] for r in splits)),
    ('Total UTF-8 path bytes in cutover sequence', sum(len(p.encode('utf-8')) for p in cutover)),
    ('Rollback rows with step zero', sum(r['step'] == 0 for r in records('rollback_plan.jsonl'))),
    ('Metadata operations with verb reflink', sum(r['op'] == 'reflink' for r in metadata)),
    (f'Objects shed in last shedding round (round {last_round})',
     sum(int(r['round']) == last_round for r in placements.values())),
    ('Devices ending overcommitted', sum(int(r['over_committed']) for r in allocation)),
    ('Shared physical ranges materialised into three or more copies', sum(r['copies'] >= 3 for r in sharing)),
    ('Total bytes resumed from durable checkpoint entries', sum(int(r['raw_physical_bytes']) for r in owned
      if r['physical_class'] == 'data' and (int(r['ino']), int(r['ext_index'])) in durable)),
    ('Hard link clusters settled at fourth key', sum(r['tiebreak_level'] == 4 for r in records('link_clusters.jsonl'))),
    ('Path on first line of cutover sequence', cutover[0]),
]
print('\nDelivered files:')
for name in delivered:
    print(out / name)
print('\nClosing figures (current /app/out artifacts):')
for name, value in figures:
    print(f'{name}: {value}')
PY
