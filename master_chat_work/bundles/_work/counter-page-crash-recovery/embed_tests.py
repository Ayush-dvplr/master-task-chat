"""Write BUNDLE/tests/test_output.py from test_template.py, bookgen.py and the shipped data files."""
import base64
import hashlib
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLE = HERE.parent.parent / "counter-page-crash-recovery"
DATA = BUNDLE / "environment" / "data"
EMBED = ["ci_config.yaml", "compiler_flags.json", "dependency_manifest.json", "expected_targets.json", "project.zip"]
BOOK = ["audit_queries.json", "checkpoint.toml", "disk_pages.bin", "journal.jsonl", "page_map.ini", "txn_catalog.csv"]


def main():
    lines = ["_SHIPPED_DATA = {"]
    for name in EMBED:
        blob = base64.b64encode(zlib.compress((DATA / name).read_bytes(), 9)).decode()
        lines.append("    %r: [" % name)
        lines += ["        %r," % blob[i:i + 96] for i in range(0, len(blob), 96)]
        lines.append("    ],")
    lines.append("}")
    lines.append("_SHIPPED_SHA = {")
    lines += ["    %r: %r," % (n, hashlib.sha256((DATA / n).read_bytes()).hexdigest()) for n in BOOK]
    lines.append("}")
    body = (HERE / "bookgen.py").read_text().split("# BODY\n", 1)[1]
    text = (HERE / "test_template.py").read_text()
    assert text.count("SHIPPED_DATA_LINE") == 1 and text.count("BOOKGEN_BODY_LINE") == 1
    text = text.replace("SHIPPED_DATA_LINE", "\n".join(lines)).replace("BOOKGEN_BODY_LINE", body.strip("\n"))
    (BUNDLE / "tests" / "test_output.py").write_text(text)
    print("test_output.py", text.count("\n"), "lines")


if __name__ == "__main__":
    main()
