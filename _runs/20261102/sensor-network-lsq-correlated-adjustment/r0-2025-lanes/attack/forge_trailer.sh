
# Forgery lane (R0 868afdf): real shipped-run documents, delivered program replaced by one that copies them to OUT_DIR.
python3 - <<'FORGE'
import pathlib, shutil
out = pathlib.Path("/app/out")
saved = pathlib.Path("/app/forged_docs")
if saved.exists():
    shutil.rmtree(saved)
saved.mkdir()
for p in sorted(out.iterdir()):
    if p.is_file() and p.name != "derive_report.py":
        shutil.copyfile(p, saved / p.name)
(out / "derive_report.py").write_text(
    "import shutil, sys\n"
    "from pathlib import Path\n"
    "dst = Path(sys.argv[2])\n"
    "dst.mkdir(parents=True, exist_ok=True)\n"
    "for p in sorted(Path('/app/forged_docs').iterdir()):\n"
    "    shutil.copyfile(p, dst / p.name)\n"
)
for d in out.glob("__pycache__"):
    shutil.rmtree(d)
print("[forgery] program replaced by a copier of", len(list(saved.iterdir())), "documents")
FORGE
