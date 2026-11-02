"""Re-embed environment/data into tests/test_output.py as _SHIPPED_DATA (common rule 6)."""
import base64
import re
import sys
import zlib
from pathlib import Path

bundle = Path(sys.argv[1])
data = bundle / "environment" / "data"
blobs = {
    p.name: base64.b64encode(zlib.compress(p.read_bytes(), 9)).decode("ascii")
    for p in sorted(data.iterdir())
    if p.is_file()
}
body = ", ".join(f'"{k}": "{v}"' for k, v in blobs.items())
line = "_SHIPPED_DATA: dict[str, str] = {" + body + "}"
target = bundle / "tests" / "test_output.py"
text = target.read_text()
new, n = re.subn(r"^_SHIPPED_DATA: dict\[str, str\] = \{.*\}$", lambda _m: line, text, flags=re.M)
assert n == 1, n
target.write_text(new)
print(f"embedded {len(blobs)} files")
