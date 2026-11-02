import importlib.util
import json
import sys
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location('verifier', '/tests/test_output.py')
verifier = importlib.util.module_from_spec(spec)
sys.modules['verifier'] = verifier
spec.loader.exec_module(verifier)
source = Path('/app/out/transform.py').read_text()
summary = []
for index in range(18):
    files = verifier._hidden_files(index)
    debug = {}
    expected = {name: payload.encode() if isinstance(payload, str) else payload for name, payload in verifier.compute(files, debug=debug).items()}
    choices = {}
    for (day, handset), offset in debug['offset_of'].items():
        choices.setdefault(handset, set()).add(offset)
    changed = {handset for handset, offsets in choices.items() if len(offsets) > 1}
    lookup = {(day + 10957, handset): offset for (day, handset), offset in debug['offset_of'].items() if handset in changed}
    replacement = f"({lookup!r}[(c['stamp'] // 86400, c['handset'])] if c['handset'] in {changed!r} else offsets[c['handset']])"
    patched_source = source.replace('offsets[c["handset"]]', replacement)
    patched = Path(tempfile.mkdtemp()) / 'transform.py'
    patched.parent.chmod(0o755)
    patched.write_text(patched_source)
    verifier.PROGRAM = patched
    run = verifier._run_extract(files, f'stepfix{index}')
    result = {'index': index + 1, 'changed_handsets': sorted(changed), 'ok': run['ok'], 'seconds': run['elapsed'], 'reports_wrong': [name for name in verifier.REPORT_NAMES if expected[name] != run['reports'].get(name)]}
    summary.append(result)
    print(json.dumps(result), flush=True)
Path('/evidence/clock_separation.json').write_text(json.dumps(summary, indent=2) + '\n')
print('DONE', flush=True)
