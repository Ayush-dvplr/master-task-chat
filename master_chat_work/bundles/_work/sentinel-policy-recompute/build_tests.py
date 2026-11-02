"""Assemble tests/test_output.py from test_body.py plus a deterministic base64 zip of environment/data."""
import base64
import io
import zipfile
from pathlib import Path

WORK = Path(__file__).resolve().parent
BUNDLE = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/sentinel-policy-recompute")
DATA = BUNDLE / "environment" / "data"

buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(p for p in DATA.rglob("*") if p.is_file()):
        info = zipfile.ZipInfo(path.relative_to(DATA).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        zf.writestr(info, path.read_bytes())
encoded = base64.b64encode(buf.getvalue()).decode("ascii")
body = (WORK / "test_body.py").read_text()
assert body.endswith("\n")
(BUNDLE / "tests" / "test_output.py").write_text(body + f'REFERENCE_CORPUS_B64 = "{encoded}"\n')
print("members", len(zipfile.ZipFile(io.BytesIO(buf.getvalue())).namelist()), "b64", len(encoded))
