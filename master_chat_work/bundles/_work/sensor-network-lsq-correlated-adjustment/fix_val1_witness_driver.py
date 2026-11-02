from pathlib import Path
import importlib.util
import json
import shutil
import sys
import time

spec = importlib.util.spec_from_file_location('snlsq_witness_grader', '/tests/test_output.py')
assert spec is not None and spec.loader is not None
grader = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = grader
spec.loader.exec_module(grader)
shutil.copytree('/bundle/environment/data', '/app/data', dirs_exist_ok=True)
out = Path('/app/out')
out.mkdir(exist_ok=True)
suffixes = ('filename_dependent_behaviour', 'reads_training_corpus_at_runtime',
            'nondeterministic_output', 'rebinds_verifier_dependencies')
results = {}
for fixture in (*suffixes, 'oracle'):
    started = time.monotonic()
    for path in out.iterdir():
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    program = (Path('/bundle/solution/solve.py') if fixture == 'oracle' else
               Path('/work/fix_val1_witnesses') / (fixture + '.py'))
    shutil.copyfile(program, out / 'derive_report.py')
    (out / 'derive_report.py').chmod(0o644)
    if fixture == 'rebinds_verifier_dependencies':
        shutil.copyfile('/work/fix_val1_witnesses/sitecustomize.py', out / 'sitecustomize.py')
    grader._HIDDEN_CACHE.clear()
    grader._REFERENCE_CACHE.clear()
    grader._BEHAVIOUR_CACHE.clear()
    fired = []
    for name in suffixes:
        try:
            getattr(grader, 'test_negative_weight_' + name)()
        except AssertionError:
            continue
        fired.append(name)
    expected = [] if fixture == 'oracle' else [fixture]
    results[fixture] = {'fired': fired, 'seconds': round(time.monotonic() - started, 3)}
    print(json.dumps({fixture: results[fixture]}), flush=True)
    assert fired == expected, (fixture, fired, expected)
print('WITNESSES_PASS', flush=True)
