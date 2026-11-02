"""Write the shipped data folder of data-product-config-compiler (seeded, stdlib only)."""
import io
import os
import sys
import zipfile
from pathlib import Path

WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(WORK))
from gen_core import gen_corpus  # noqa: E402
from ref_core import ref_compute  # noqa: E402

SEED = 724163
DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else WORK.parent.parent / "data-product-config-compiler" / "environment" / "data"
TOOL_FILES = ("cli.py", "loaders.py", "resolve.py", "quota.py", "emit.py", "README.md")


def tool_zip(src: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in TOOL_FILES:
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, (src / name).read_bytes())
    return buf.getvalue()


def main() -> None:
    files = gen_corpus(SEED, 600, False, "2026-09-30", "2026.10-r3", ref_compute)
    files["config_contract.md"] = (WORK / "config_contract.md").read_bytes()
    files["tool.zip"] = tool_zip(WORK / "tool_src")
    DATA.mkdir(parents=True, exist_ok=True)
    for old in DATA.iterdir():
        if old.name not in files:
            old.unlink()
    total = 0
    for name, blob in sorted(files.items()):
        (DATA / name).write_bytes(blob)
        if name == "tool.zip":
            continue
        n = len(blob.decode("utf-8").splitlines())
        total += n
        if name.rsplit(".", 1)[-1] in ("csv", "tsv", "jsonl", "txt", "log"):
            assert n >= 2000, (name, n)
        assert b"\r" not in blob and not any(ord(c) > 126 for c in blob.decode("utf-8")), name
        print(f"{name}: {n}")
    assert total >= 20000, total
    print(f"TOTAL lines {total}; files {len(files)}")


if __name__ == "__main__":
    main()
