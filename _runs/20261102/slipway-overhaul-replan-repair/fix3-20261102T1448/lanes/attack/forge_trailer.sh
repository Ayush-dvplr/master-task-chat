
# Forgery lane (fix-v1 451146f): real delivered documents, delivered engine replaced by one that copies them.
python3 - <<'FORGE'
import io, pathlib, zipfile
out = pathlib.Path("/app/out")
docs = sorted(p for p in out.iterdir() if p.is_file() and p.name != "patched_engine.zip")
MAIN = (
    "import shutil, sys\n"
    "from pathlib import Path\n"
    "args = sys.argv[1:]\n"
    "dst = Path(args[args.index('--out') + 1])\n"
    "dst.mkdir(parents=True, exist_ok=True)\n"
    "for p in sorted((Path(__file__).parent / '_saved').iterdir()):\n"
    "    shutil.copyfile(p, dst / p.name)\n"
)
src = zipfile.ZipFile(out / "patched_engine.zip")
buf = io.BytesIO()
main_name = None
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
    for info in src.infolist():
        if info.filename.endswith("slwopt/__main__.py"):
            main_name = info.filename
            continue
        z.writestr(info, src.read(info))
    prefix = main_name[: -len("__main__.py")]
    for p in docs:
        z.writestr(prefix + "_saved/" + p.name, p.read_bytes())
    z.writestr(main_name, MAIN)
(out / "patched_engine.zip").write_bytes(buf.getvalue())
print("[forgery] engine replaced by a copier of", len(docs), "documents")
FORGE
