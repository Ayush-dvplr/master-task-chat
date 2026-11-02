"""Write every hidden statement corpus, its reference statement document, and an oracle-repaired repo.

usage: python3 -B dump_corpora.py TARGET_DIR
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from load import BUNDLE, load  # noqa: E402

target = Path(sys.argv[1])
shutil.rmtree(target, ignore_errors=True)
m = load()
for corpus in ["shipped", "fresh", "rescaled", "relocated", "rotated", "api", "recoded", "renamed"]:
    texts = m._statement_texts_of(corpus)
    folder = target / "corpora" / corpus
    folder.mkdir(parents=True)
    for name, text in texts.items():
        (folder / name).write_text(text, encoding="utf-8")
    (target / "corpora" / f"{corpus}.want.json").write_text(json.dumps(m._statements(texts), sort_keys=True))
root = Path(tempfile.mkdtemp(prefix="t3-oracle-"))
app = root / "app"
shutil.copytree(BUNDLE / "environment" / "ci", app / "ci")
shutil.copytree(BUNDLE / "environment" / "repo", app / "repo")
env = dict(os.environ, APP_ROOT=str(app), PYTHONDONTWRITEBYTECODE="1")
subprocess.run([sys.executable, "-B", str(BUNDLE / "solution" / "solve.py")], env=env, check=True,
               capture_output=True)
shutil.copytree(app / "repo", target / "oracle_repo")
shutil.rmtree(root)
print("dumped", sorted(p.name for p in (target / "corpora").iterdir()))
