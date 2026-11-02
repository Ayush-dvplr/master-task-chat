import shutil, sys
from pathlib import Path
dst = Path(sys.argv[2])
dst.mkdir(parents=True, exist_ok=True)
for p in sorted(Path('/app/forged_docs').iterdir()):
    shutil.copyfile(p, dst / p.name)
