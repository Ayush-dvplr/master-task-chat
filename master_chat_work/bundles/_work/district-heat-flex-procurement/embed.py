"""Write tests/test_output.py = test_output.src.py with _SHIPPED_DATA filled from environment/data."""
import base64
import zlib
from pathlib import Path

HERE = Path(__file__).parent
BUNDLE = HERE.parent.parent / "district-heat-flex-procurement"
src = (HERE / "test_output.src.py").read_text(encoding="utf-8")
marker = "_SHIPPED_DATA: dict[str, str] = {}"
assert src.count(marker) == 1
items = []
for p in sorted((BUNDLE / "environment" / "data").iterdir()):
    blob = base64.b64encode(zlib.compress(p.read_bytes(), 9)).decode("ascii")
    items.append(f"    {p.name!r}: {blob!r},")
literal = "_SHIPPED_DATA: dict[str, str] = {\n" + "\n".join(items) + "\n}"
(BUNDLE / "tests" / "test_output.py").write_text(src.replace(marker, literal), encoding="utf-8")
print("embedded", len(items), "files")
