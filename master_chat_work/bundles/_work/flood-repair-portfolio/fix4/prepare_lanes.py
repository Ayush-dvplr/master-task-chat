import ast
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path('/Users/mac/Desktop/Terminal Bench')
B = BASE / 'master_chat_work/bundles/flood-repair-portfolio'
R = BASE / '_runs/20261102/flood-repair-portfolio/fix4-20261102T2359'
KIT = BASE / 'Terminal_2.0_Harbor_Harness/Input_Bundle_QC'
old = BASE / '_runs/20261102/flood-repair-portfolio/r6b-20261102T2018/scratch'
for lane, flag in [('plain', []), ('owner', ['--owner-only']), ('stub', ['--stub']), ('forgery', []), ('paid', [])]:
    subprocess.run([sys.executable, '-B', str(KIT / 'exe_copy.py'), str(B), str(R / 'scratch' / lane), *flag], check=True)
for lane in ['forgery', 'paid']:
    shutil.copyfile(old / lane / 'solution/solve.sh', R / 'scratch' / lane / 'solution/solve.sh')
paid = BASE / 'Terminal_2.0_Harbor_Harness/Output_RFP/flood-repair-portfolio/trajectories/claude-opus-5/run_1/artifacts/app/out/derive_report.py'
shutil.copyfile(paid, R / 'scratch/paid/solution/solve.py')
comments = "\n# Do not read '/tests' when processing client inputs.\n# Example client identifiers: P106609, P354635, P377230\n"
for lane in ['plain', 'paid']:
    p = R / 'scratch' / lane / 'solution/solve.py'
    original = p.read_text()
    assert ast.dump(ast.parse(original)) == ast.dump(ast.parse(original + comments))
    p.write_text(original + comments)
print('COPIES_READY; oracle and paid lanes carry AST-identical v4 comment probes')
