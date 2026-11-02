import hashlib, re, pathlib
B = pathlib.Path('/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cleanroom-window-schedule')
t = B/'solution/TRUTH.md'; s = t.read_text()
for key, f in (('fix_patch_sha256', 'solve.sh'), ('solve_py_sha256', 'solve.py')):
    h = hashlib.sha256((B/'solution'/f).read_bytes()).hexdigest()
    s = re.sub(rf'^{key}: [0-9a-f]{{64}}', f'{key}: {h}', s, flags=re.M)
t.write_text(s); print('ok')
