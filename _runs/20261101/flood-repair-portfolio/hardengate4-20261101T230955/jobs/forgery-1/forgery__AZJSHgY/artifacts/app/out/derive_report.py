import shutil, sys
from pathlib import Path
src = Path(__file__).resolve().parent / "_saved"
dst = Path(sys.argv[2])
dst.mkdir(parents=True, exist_ok=True)
for p in sorted(src.glob("*.json")):
    shutil.copyfile(p, dst / p.name)
