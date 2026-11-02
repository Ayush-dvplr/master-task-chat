import hashlib, re, pathlib
B = pathlib.Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/flood-repair-portfolio')
t = B/'solution/TRUTH.md'; s = t.read_text()
for key, f in (('fix_patch_sha256', 'solve.sh'), ('solve_py_sha256', 'solve.py')):
    h = hashlib.sha256((B/'solution'/f).read_bytes()).hexdigest()
    s, k = re.subn(rf'^{key}: ([0-9a-f]{{64}}|pending)', f'{key}: {h}', s, flags=re.M)
    assert k == 1, key
t.write_text(s); print('ok')
