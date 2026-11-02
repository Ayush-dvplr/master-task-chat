import importlib.util
import json
import sys
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location('verifier', '/tests/test_output.py')
verifier = importlib.util.module_from_spec(spec)
sys.modules['verifier'] = verifier
spec.loader.exec_module(verifier)
summary = []
for index in range(3):
    profile = dict(verifier.HIDDEN_PROFILES[index], steps=())
    seed = verifier.EVAL_SEED + index
    world = verifier.build_world(seed, profile)
    root = verifier.write_extract(world, Path(tempfile.mkdtemp()) / 'extract')
    truth = verifier.truth_offsets(world)
    assert all(len(segments) == 1 for segments in truth.values())
    expected = {name: payload.encode() if isinstance(payload, str) else payload for name, payload in verifier.reference_reports(root, truth).items()}
    run = verifier._execute(verifier._prepare(root, f'conforming{index}'), 'audit.log')
    dq_expected = json.loads(expected['data_quality.json'])['units']
    dq_actual = json.loads(run['files']['data_quality.json'])['units']
    item = {'index': index + 1, 'seed': seed, 'profile': profile, 'truth_offsets': truth, 'echoes': world.echo, 'countmatch_wrong': world.countmatch_wrong, 'ok': run['ok'], 'seconds': run['elapsed'], 'reports_wrong': [name for name, payload in expected.items() if payload != run['files'].get(name)], 'dq_differences': [{'unit_id': left['unit_id'], 'expected': left, 'actual': right} for left, right in zip(dq_expected, dq_actual) if left != right]}
    summary.append(item)
    print(json.dumps(item), flush=True)
Path('/evidence/conforming_echo_probes.json').write_text(json.dumps(summary, indent=2) + '\n')
print('DONE', flush=True)
