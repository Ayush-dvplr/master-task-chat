import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

task = sys.argv[1]
result = Path('/evidence') / (task + '-instrument')
result.mkdir(exist_ok=True)
shutil.copytree('/captured/out', '/app/out', dirs_exist_ok=True)
spec = importlib.util.spec_from_file_location('checks', '/tests/test_output.py')
if spec is None or spec.loader is None:
    raise RuntimeError('test module unavailable')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


def differences(expected: object, actual: object, path: str = '$') -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(expected.keys() | actual.keys()):
            location = path + '.' + key
            if key not in expected:
                found.append({'path': location, 'expected': '<MISSING>', 'actual': actual[key]})
            elif key not in actual:
                found.append({'path': location, 'expected': expected[key], 'actual': '<MISSING>'})
            else:
                found.extend(differences(expected[key], actual[key], location))
    elif isinstance(expected, list) and isinstance(actual, list):
        for index in range(max(len(expected), len(actual))):
            location = f'{path}[{index}]'
            if index >= len(expected):
                found.append({'path': location, 'expected': '<MISSING>', 'actual': actual[index]})
            elif index >= len(actual):
                found.append({'path': location, 'expected': expected[index], 'actual': '<MISSING>'})
            else:
                found.extend(differences(expected[index], actual[index], location))
    elif type(expected) is not type(actual) or expected != actual:
        found.append({'path': path, 'expected': expected, 'actual': actual})
    return found


summary = []
for scenario in checks.SCENARIOS:
    start = time.monotonic()
    exception = None
    try:
        exact = checks._exact if task == 'pension' else checks._exact_scenario
        exact(scenario)
    except Exception as error:
        exception = {'type': type(error).__name__, 'message': str(error)}
    elapsed = time.monotonic() - start
    actual = checks._scenario_out(scenario)
    case = result / scenario
    case.mkdir(exist_ok=True)
    shutil.copytree(actual.parent / 'data', case / 'data', dirs_exist_ok=True)
    shutil.copytree(actual, case / 'actual', dirs_exist_ok=True)
    expected = case / 'expected'
    process = subprocess.run(
        [sys.executable, '-I', '-S', '/oracle/solve.py', str(actual.parent / 'data'), str(expected)],
        capture_output=True, text=True, timeout=120, check=True,
    )
    expected_hash = checks._bundle_hash(expected)
    frozen = checks._EXPECTED_BUNDLES[scenario]
    assert expected_hash == frozen, (scenario, expected_hash, frozen, process.stderr)
    files = {}
    for name in checks.REPORTS:
        files[name] = differences(json.loads((expected / name).read_text()), json.loads((actual / name).read_text()))
    altered = case / 'one-fact-wrong'
    shutil.copytree(expected, altered, dirs_exist_ok=True)
    manifest = json.loads((altered / 'manifest.json').read_text())
    manifest['engine_version'] += '-one-wrong-fact'
    (altered / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    record = {
        'scenario': scenario, 'wall_seconds': elapsed, 'exception': exception,
        'expected_hash': frozen, 'actual_hash': checks._bundle_hash(actual),
        'oracle_hash_verified': True, 'diffs': files,
        'diff_count': sum(map(len, files.values())),
        'one_fact_wrong_fails': checks._bundle_hash(altered) != frozen,
        'input_counts': {path.name: len(path.read_text().splitlines()) for path in (case / 'data').glob('*.jsonl')},
    }
    (case / 'diff.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    summary.append({key: value for key, value in record.items() if key != 'diffs'})
    print(scenario, record['diff_count'], {key: len(value) for key, value in files.items() if value}, flush=True)
(result / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
print('DONE', flush=True)
