from pathlib import Path
import ast
import json
import shutil
import subprocess

BASE = Path('/Users/mac/Desktop/Terminal Bench')
BUNDLE = BASE / 'master_chat_work/bundles/sensor-network-lsq-correlated-adjustment'
WORK = BASE / 'master_chat_work/bundles/_work/sensor-network-lsq-correlated-adjustment'
RUN = BASE / '_runs/20261102/sensor-network-lsq-correlated-adjustment/fixv-20261102T224943'
KIT = BASE / 'Terminal_2.0_Harbor_Harness/Input_Bundle_QC'

source = (BUNDLE / 'tests/test_output.py').read_text()
tree = ast.parse(source)
assignment = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ARTIFACT_NAMES' for t in n.targets))
names_code = ast.get_source_segment(source, assignment)
witness_dir = WORK / 'fix_val1_witnesses'
witness_dir.mkdir(exist_ok=True)
acts = {
    'filename_dependent_behaviour': "value = Path(sys.argv[1]).name + str(Path.cwd())",
    'reads_training_corpus_at_runtime': "try:\n    value = (Path('/app/data') / 'schema.md').read_text()\nexcept PermissionError:\n    value = 'shipped tree hidden'",
    'nondeterministic_output': "value = os.environ.get('PYTHONHASHSEED', 'unset')",
    'rebinds_verifier_dependencies': "value = 'stable'",
}
for name, act in acts.items():
    program = "from pathlib import Path\nimport os\nimport sys\n" + names_code + '\n' + act + "\nout = Path(sys.argv[2])\nout.mkdir(parents=True, exist_ok=True)\nfor name in ARTIFACT_NAMES:\n    (out / name).write_text(value + '\\n')\n"
    ast.parse(program)
    (witness_dir / (name + '.py')).write_text(program)
(witness_dir / 'sitecustomize.py').write_text("import os\nos.environ['SNLSQ_SHADOW_HOOK'] = 'active'\n")

for copy, flags in (('plain', []), ('stub', ['--stub']), ('owner', ['--owner-only']), ('forgery', []), ('paid', [])):
    dest = RUN / 'copies' / copy
    proc = subprocess.run(['python3', '-B', str(KIT / 'exe_copy.py'), str(BUNDLE), str(dest), *flags], text=True, capture_output=True)
    (RUN / 'logs' / ('exe_copy_' + copy + '.log')).write_text(proc.stdout + proc.stderr)
    if proc.returncode:
        raise SystemExit(proc.returncode)

old = BASE / '_runs/20261102/sensor-network-lsq-correlated-adjustment/r0-2025-lanes/copies'
for name in ('forgery', 'paid'):
    shutil.copytree(old / name / 'solution', RUN / 'copies' / name / 'solution', dirs_exist_ok=True)
for d in ('jobs', 'scratch'):
    (RUN / d).mkdir(exist_ok=True)
print(json.dumps({'witnesses': sorted(acts), 'copies': ['plain', 'stub', 'owner', 'forgery', 'paid']}))
