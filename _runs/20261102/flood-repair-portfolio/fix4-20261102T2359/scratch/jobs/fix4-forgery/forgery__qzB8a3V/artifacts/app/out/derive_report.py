import shutil
import sys
from pathlib import Path

saved = Path(__file__).resolve().parent / '_saved'
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
for source in saved.glob('*.json'):
    shutil.copyfile(source, out / source.name)
