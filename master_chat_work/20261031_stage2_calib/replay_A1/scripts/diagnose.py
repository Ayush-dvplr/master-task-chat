import importlib.util
import json
import sys
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

TASK = sys.argv[1]
COUNTERFACTUAL = len(sys.argv) > 2 and sys.argv[2] == 'counterfactual'
DEST = Path('/evidence')
spec = importlib.util.spec_from_file_location('verifier', '/tests/test_output.py')
module = importlib.util.module_from_spec(spec)
sys.modules['verifier'] = module
spec.loader.exec_module(module)


def differences(expected, actual, path='$'):
    if type(expected) is not type(actual):
        return [{'path': path, 'expected': expected, 'actual': actual}]
    if isinstance(expected, dict):
        result = []
        for key in sorted(set(expected) | set(actual)):
            if key not in expected or key not in actual:
                result.append({'path': path + '.' + key, 'expected': expected.get(key, '<MISSING>'), 'actual': actual.get(key, '<MISSING>')})
            else:
                result.extend(differences(expected[key], actual[key], path + '.' + key))
        return result
    if isinstance(expected, list):
        result = []
        for index in range(max(len(expected), len(actual))):
            if index >= min(len(expected), len(actual)):
                result.append({'path': f'{path}[{index}]', 'expected': expected[index] if index < len(expected) else '<MISSING>', 'actual': actual[index] if index < len(actual) else '<MISSING>'})
            else:
                result.extend(differences(expected[index], actual[index], f'{path}[{index}]'))
        return result
    return [] if expected == actual else [{'path': path, 'expected': expected, 'actual': actual}]


def compare(expected, actual):
    reports = {}
    for name, payload in expected.items():
        other = actual.get(name)
        if isinstance(payload, str):
            payload = payload.encode()
        if other is None:
            reports[name] = {'missing': True, 'differences': [{'path': '$', 'expected': 'report', 'actual': '<MISSING>'}]}
            continue
        if name.endswith('.jsonl'):
            left = [json.loads(line) for line in payload.splitlines()]
            right = [json.loads(line) for line in other.splitlines()]
        else:
            left, right = json.loads(payload), json.loads(other)
        delta = differences(left, right)
        reports[name] = {'byte_equal': payload == other, 'fields_wrong': len(delta), 'differences': delta}
    return reports


count = {'billing': 18, 'pm25': 20, 'royalty': 8}[TASK]
summary = []
original_popen = subprocess.Popen
for index in range(count):
    started = time.monotonic()
    item = {'index': index + 1, 'exception': None}
    stderr_path = DEST / f"{'counterfactual' if COUNTERFACTUAL else 'case'}_{index + 1:02d}.stderr.txt"
    def logged_popen(*args, **kwargs):
        if kwargs.get('stderr') == subprocess.DEVNULL:
            with stderr_path.open('wb') as handle:
                kwargs['stderr'] = handle
                return original_popen(*args, **kwargs)
        return original_popen(*args, **kwargs)
    subprocess.Popen = logged_popen
    try:
        match TASK:
            case 'billing':
                files = module._hidden_files(index)
                debug = {}
                expected = module.compute(files, debug=debug)
                expected = {name: expected[name] for name in module.REPORT_NAMES}
                if COUNTERFACTUAL:
                    source = Path('/app/out/transform.py').read_text()
                    lookup = {(day + 10957, handset): offset for (day, handset), offset in debug['offset_of'].items()}
                    source = source.replace('offsets[c["handset"]]', f"{lookup!r}[(c['stamp'] // 86400, c['handset'])]")
                    patched = Path(tempfile.mkdtemp()) / 'transform.py'
                    patched.parent.chmod(0o755)
                    patched.write_text(source)
                    module.PROGRAM = patched
                run = module._run_extract(files, f'diag{index}')
                actual = run['reports']
                item['clock_truth'] = {str(key): value for key, value in debug.get('offset_of', {}).items()}
            case 'pm25':
                world = module.build_world(module.EVAL_SEED + index, module.HIDDEN_PROFILES[index])
                root = module.write_extract(world, Path(tempfile.mkdtemp()) / 'extract')
                offsets = module.truth_offsets(world)
                expected = module.reference_reports(root, offsets)
                if COUNTERFACTUAL:
                    cards = module.load_extract(root)['cards']
                    lookup = {}
                    for unit, segments in offsets.items():
                        rows = sorted((row for row in cards if row['unit_id'] == unit), key=lambda row: module.to_min(row['card_stamp']))
                        for number, row in enumerate(rows):
                            lookup[(unit, module.to_min(row['card_stamp']))] = [offset for start, offset in segments if start <= number][-1]
                    source = Path('/app/out/derive_report.py').read_text()
                    source = source.replace('offsets, received = clock_offsets(card_rows, channels, journal)', f"truth_offsets = {lookup!r}\n    received = {{unit: sum((channels[unit], row['card_stamp_minute'] - truth_offsets[(unit, row['card_stamp_minute'])], row['frame']) in journal for row in card_rows if row['unit_id'] == unit) for unit in channels}}")
                    source = source.replace('instant = row["card_stamp_minute"] - offsets[unit_id]', "instant = row['card_stamp_minute'] - truth_offsets[(unit_id, row['card_stamp_minute'])]")
                    patched = Path(tempfile.mkdtemp()) / 'derive_report.py'
                    patched.parent.chmod(0o755)
                    patched.write_text(source)
                    module.PROGRAM = patched
                run = module._execute(module._prepare(root, f'diag{index}'), 'audit.log')
                actual = run['files']
                item['clock_truth'] = offsets
            case 'royalty':
                scenario = module.SCENARIOS[index]
                root = Path(tempfile.mkdtemp())
                root.chmod(0o777)
                data = module._variant(root, scenario)
                module.SCRIPT = Path('/oracle/solve.py')
                oracle = root / 'oracle'
                module._run(data, oracle)
                oracle_hash = module._bundle(oracle)
                item.update(scenario=scenario, oracle_hash=oracle_hash, expected_hash=module._EXPECTED[scenario], oracle_hash_valid=oracle_hash == module._EXPECTED[scenario])
                expected = {name: (oracle / name).read_bytes() for name in module.REPORTS}
                module.SCRIPT = Path('/app/out/calculate_royalties.py')
                if COUNTERFACTUAL:
                    source = module.SCRIPT.read_text().replace('issues.add("INVALID_STATEMENT", winner["record_id"])', 'issues.add("INVALID_STATEMENT", statement_id)')
                    patched = root / 'calculate_royalties.py'
                    patched.write_text(source)
                    module.SCRIPT = patched
                out = root / 'agent'
                module._run(data, out)
                actual = {name: (out / name).read_bytes() for name in module.REPORTS}
                run = {'ok': True, 'elapsed': time.monotonic() - started}
        item['ok'] = run['ok']
        item['program_seconds'] = run['elapsed']
        item['stderr'] = stderr_path.read_text() if stderr_path.exists() else ''
        item['reports'] = compare(expected, actual)
        item['fields_wrong'] = sum(report.get('fields_wrong', 1) for report in item['reports'].values())
        item['reports_wrong'] = [name for name, report in item['reports'].items() if not report.get('byte_equal', False)]
    except Exception as exc:
        item['exception'] = {'type': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()}
    item['wall_seconds'] = time.monotonic() - started
    prefix = 'counterfactual' if COUNTERFACTUAL else 'case'
    (DEST / f'{prefix}_{index + 1:02d}.json').write_text(json.dumps(item, indent=2, sort_keys=True) + '\n')
    summary.append({key: value for key, value in item.items() if key not in ('reports', 'clock_truth')})
    print(json.dumps(summary[-1]), flush=True)
(DEST / ('counterfactual_summary.json' if COUNTERFACTUAL else 'diagnostics_summary.json')).write_text(json.dumps(summary, indent=2) + '\n')
print('DONE', flush=True)
