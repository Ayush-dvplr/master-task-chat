import importlib.util
import json
import sys
import tempfile
from pathlib import Path


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


verifier = load('verifier', '/tests/test_output.py')
agent = load('agent', '/app/out/derive_report.py')
source = Path('/app/out/derive_report.py').read_text()
summary = []
for index, profile in enumerate(verifier.HIDDEN_PROFILES):
    world = verifier.build_world(verifier.EVAL_SEED + index, profile)
    root = verifier.write_extract(world, Path(tempfile.mkdtemp()) / 'extract')
    truth = verifier.truth_offsets(world)
    expected = {name: payload.encode() if isinstance(payload, str) else payload for name, payload in verifier.reference_reports(root, truth).items()}
    cards = agent.read_csv(str(root / 'card_readings.csv'))
    for row in cards:
        row['card_stamp_minute'] = agent.parse_minute(row['card_stamp'])
    _, channels = agent.load_deployments(agent.read_csv(str(root / 'unit_deployments.csv')))
    journal = {(agent.channel_label(row['channel']), agent.parse_minute(row['received_utc']), row['frame']) for row in agent.read_csv(str(root / 'receipt_journal.csv'))}
    inferred, received = agent.clock_offsets(cards, channels, journal)
    result = {'index': index + 1, 'echoes': world.echo, 'countmatch_wrong': world.countmatch_wrong, 'inferred_offsets': inferred, 'truth_offsets': truth, 'constant_unit_errors': {unit: {'expected': segments[0][1], 'actual': inferred[unit]} for unit, segments in truth.items() if len(segments) == 1 and inferred[unit] != segments[0][1]}, 'probes': {}}
    for mode in ('stepped_only', 'constant_only'):
        lookup = {}
        for unit, segments in truth.items():
            rows = sorted((row for row in cards if row['unit_id'] == unit), key=lambda row: row['card_stamp_minute'])
            for number, row in enumerate(rows):
                correct_this = (len(segments) > 1) == (mode == 'stepped_only')
                offset = [offset for start, offset in segments if start <= number][-1] if correct_this else inferred[unit]
                lookup[(unit, row['card_stamp_minute'])] = offset
        patched_source = source.replace('offsets, received = clock_offsets(card_rows, channels, journal)', f"truth_offsets = {lookup!r}\n    received = {{unit: sum((channels[unit], row['card_stamp_minute'] - truth_offsets[(unit, row['card_stamp_minute'])], row['frame']) in journal for row in card_rows if row['unit_id'] == unit) for unit in channels}}")
        patched_source = patched_source.replace('instant = row["card_stamp_minute"] - offsets[unit_id]', "instant = row['card_stamp_minute'] - truth_offsets[(unit_id, row['card_stamp_minute'])]")
        patched = Path(tempfile.mkdtemp()) / 'derive_report.py'
        patched.parent.chmod(0o755)
        patched.write_text(patched_source)
        verifier.PROGRAM = patched
        run = verifier._execute(verifier._prepare(root, f'{mode}{index}'), 'audit.log')
        result['probes'][mode] = {'ok': run['ok'], 'seconds': run['elapsed'], 'reports_wrong': [name for name, payload in expected.items() if payload != run['files'].get(name)]}
    summary.append(result)
    print(json.dumps(result), flush=True)
Path('/evidence/clock_separation.json').write_text(json.dumps(summary, indent=2) + '\n')
print('DONE', flush=True)
