"""Build BUNDLE/tests/test_output.py from WORK/test_template.py plus the shipped ci files."""
import base64
import zlib
from pathlib import Path

WORK = Path(__file__).resolve().parent
BUNDLE = WORK.parents[1] / "cold-chain-backbone-quote"
NAMES = ("sites.csv", "layout.tsv", "links.jsonl", "access_rules.toml", "activation.ini",
         "regression_cases.jsonl", "failing_tests.log", "build_config.json")

lines = ["_SHIPPED_DATA: dict[str, str] = {"]
for name in NAMES:
    blob = base64.b64encode(zlib.compress((BUNDLE / "environment" / "ci" / name).read_bytes(), 9)).decode()
    lines.append('    "%s": (' % name)
    for k in range(0, len(blob), 96):
        lines.append('        "%s"' % blob[k:k + 96])
    lines.append("    ),")
lines.append("}")
template = (WORK / "test_template.py").read_text(encoding="utf-8")
assert template.count("SHIPPED_DATA_LINE") == 1
(BUNDLE / "tests" / "test_output.py").write_text(template.replace("SHIPPED_DATA_LINE", "\n".join(lines)), encoding="utf-8")
print("embedded", len(NAMES), "files")
