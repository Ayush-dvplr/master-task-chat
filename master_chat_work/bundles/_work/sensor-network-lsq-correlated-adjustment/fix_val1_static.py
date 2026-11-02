from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import tomllib

base = Path('/Users/mac/Desktop/Terminal Bench')
bundle = base / 'master_chat_work/bundles/sensor-network-lsq-correlated-adjustment'
work = base / 'master_chat_work/bundles/_work/sensor-network-lsq-correlated-adjustment'
out = base / 'master_chat_work/20261102_sensor-network-lsq-correlated-adjustment/fix_val1'
kit = base / 'Terminal_2.0_Harbor_Harness/Input_Bundle_QC'
tools = base / 'master_chat_tasks/tools'
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', IBG_MEMORY_PATH=str(base / 'master_chat_work/gen_memory/ideas.jsonl'))
commands = [
    ('xref.txt', ['python3', '-B', str(tools / 'xref_check.py'), str(bundle), str(work / 'XREF.md')]),
    ('STACKING_CHECK.md', ['python3', '-B', str(tools / 'stacking_check.py'), str(bundle)]),
    ('precheck.txt', ['bash', str(tools / 'precheck.sh'), str(bundle)]),
    *((name + '.txt', ['python3', '-B', str(kit / (name + '.py')), str(bundle)]) for name in ('structure_qc', 'instruction_qc', 'tests_qc', 'judge_qc')),
    ('validator_after.txt', ['python3', '-B', str(base / 'Terminal_2.0_Harbor_Harness/Input Bundle Generator New/validate_bundle.py'), str(bundle)]),
]
codes = {}
for filename, command in commands:
    proc = subprocess.run(command, env=env, cwd='/tmp', text=True, capture_output=True)
    (out / filename).write_text(proc.stdout + proc.stderr)
    codes[filename] = proc.returncode
    print(filename, proc.returncode, '\n'.join((proc.stdout + proc.stderr).splitlines()[-4:]), flush=True)
(out / 'static_exit_codes.json').write_text(json.dumps(codes, indent=2) + '\n')
ast.parse((bundle / 'tests/test_output.py').read_text())
tomllib.loads((bundle / 'tests/reward.toml').read_text())
paid = base / 'Terminal_2.0_Harbor_Harness/Output_RFP/sensor-network-lsq-correlated-adjustment/trajectories/claude-opus-5/run_1/artifacts/app/out/derive_report.py'
copy = base / '_runs/20261102/sensor-network-lsq-correlated-adjustment/fixv-20261102T224943/copies/paid/solution/paid.py'
assert hashlib.sha256(paid.read_bytes()).digest() == hashlib.sha256(copy.read_bytes()).digest()
print('AST_TOML_PAID_DIGEST_PASS')
