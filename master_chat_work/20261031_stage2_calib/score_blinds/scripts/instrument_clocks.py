import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time


def differences(expected, actual, path='$'):
    found = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(expected.keys() | actual.keys()):
            location = path + '.' + key
            if key not in expected or key not in actual:
                found.append({'path': location, 'expected': expected.get(key, '<MISSING>'), 'actual': actual.get(key, '<MISSING>')})
            else:
                found.extend(differences(expected[key], actual[key], location))
    elif isinstance(expected, list) and isinstance(actual, list):
        for index in range(max(len(expected), len(actual))):
            location = f'{path}[{index}]'
            if index >= len(expected) or index >= len(actual):
                found.append({'path': location, 'expected': expected[index] if index < len(expected) else '<MISSING>', 'actual': actual[index] if index < len(actual) else '<MISSING>'})
            else:
                found.extend(differences(expected[index], actual[index], location))
    elif type(expected) is not type(actual) or expected != actual:
        found.append({'path': path, 'expected': expected, 'actual': actual})
    return found


task = sys.argv[1]
destination = Path('/evidence') / (task + '-instrument')
destination.mkdir(exist_ok=True)
shutil.copytree('/captured/out', '/app/out', dirs_exist_ok=True)
spec = importlib.util.spec_from_file_location('checks', '/tests/test_output.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)
summary = []
count = len(checks.HIDDEN_EXTRACTS if task == 'billing' else checks.HIDDEN_PROFILES)
for index in range(count):
    case_dir = destination / f'{index + 1:02d}'
    case_dir.mkdir(exist_ok=True)
    start = time.monotonic()
    exception = None
    try:
        if task == 'billing':
            source = checks._hidden_files(index)
            debug = {}
            computed = checks.compute(source, debug=debug)
            expected = {name: computed[name] for name in checks.REPORT_NAMES}
            run = checks._hidden_run(index)
            actual = run['reports']
            offsets = [{'day': checks.fmt_day(day), 'handset': handset, 'offset': offset} for (day, handset), offset in sorted(debug['offset_of'].items())]
            (case_dir / 'truth_offsets.json').write_text(json.dumps(offsets, indent=2) + '\n')
        else:
            # Inline the unchanged factory so exceptions aren't swallowed by _cached.
            world = checks.build_world(checks.EVAL_SEED + index, checks.HIDDEN_PROFILES[index])
            root = checks.write_extract(world, Path(tempfile.mkdtemp(prefix='instrument-pm25-')) / 'extract')
            offsets = checks.truth_offsets(world)
            expected = {name: text.encode() for name, text in checks.reference_reports(root, offsets).items()}
            run = checks._execute(checks._prepare(root, f'h{index:02d}'), 'audit.log')
            actual = run['files']
            (case_dir / 'truth_offsets.json').write_text(json.dumps(offsets, indent=2) + '\n')
        shutil.copytree(run['data_dir'], case_dir / 'data', dirs_exist_ok=True)
        for label, reports in [('expected', expected), ('actual', actual)]:
            folder = case_dir / label
            folder.mkdir(exist_ok=True)
            for name, blob in reports.items():
                (folder / name).write_bytes(blob)
        diffs = {}
        for name, blob in expected.items():
            if name not in actual:
                diffs[name] = [{'path': '$', 'expected': 'report present', 'actual': '<MISSING>'}]
            else:
                parse = (lambda text: [json.loads(line) for line in text.splitlines()]) if name.endswith('.jsonl') else json.loads
                diffs[name] = differences(parse(blob), parse(actual[name]))
                if blob != actual[name] and not diffs[name]:
                    diffs[name] = [{'path': '$bytes', 'expected': repr(blob), 'actual': repr(actual[name])}]
        record = {'index': index + 1, 'ok': run['ok'], 'program_wall_seconds': run['elapsed'], 'exception': None,
                  'diffs': diffs, 'diff_count': sum(map(len, diffs.values())),
                  'exception_note': 'Exact predicate returns False on differing reports; no exception raised. Runner discards program stderr.'}
    except Exception as error:
        record = {'index': index + 1, 'exception': {'type': type(error).__name__, 'message': str(error)}, 'diff_count': None}
    record['wall_seconds'] = time.monotonic() - start
    (case_dir / 'diff.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    summary.append({key: value for key, value in record.items() if key != 'diffs'})
    print(task, index + 1, record['diff_count'], record['exception'], flush=True)
(destination / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
print('DONE', flush=True)
