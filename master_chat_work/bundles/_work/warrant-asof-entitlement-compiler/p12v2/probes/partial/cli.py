"""Probe: the repaired tool, but a missing grant_corrections.jsonl is treated as empty."""
import shutil, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import warrant_main  # noqa: E402

argv = sys.argv[1:]
if "--data" in argv:
    i = argv.index("--data") + 1
    data = Path(argv[i])
    if not (data / "grant_corrections.jsonl").exists():
        tmp = Path(tempfile.mkdtemp(prefix="probe-"))
        for p in data.iterdir():
            shutil.copy2(p, tmp / p.name)
        (tmp / "grant_corrections.jsonl").write_text("")
        argv[i] = str(tmp)
sys.exit(warrant_main.main(argv))
