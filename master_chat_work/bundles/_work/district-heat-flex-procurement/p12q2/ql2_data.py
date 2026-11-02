"""One-shot QL2-F5 edit of the shipped export_manifest.tsv: drop the records column and its comment clause.
Already applied 29 Oct 2026 (P12 19f8e1f); never re-run on the edited bundle."""
from pathlib import Path

P = Path("/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/district-heat-flex-procurement/environment/data/export_manifest.tsv")
lines = P.read_text(encoding="utf-8").split("\n")
assert lines[1].startswith("# Each line names a file and gives its records"), lines[1]
assert lines[5] == "file\trecords\tfield\tfield_sum", lines[5]
head = [lines[0],
        "# Each line names a file. Where a field is named, field_sum is the sum of that field's values as",
        "# they are written in the file, over all of its records; otherwise field and field_sum are empty.",
        lines[4], "file\tfield\tfield_sum"]
rows = []
for x in lines[6:]:
    if not x:
        continue
    f = x.split("\t")
    assert len(f) == 4, x
    rows.append("\t".join([f[0], f[2], f[3]]))
P.write_text("\n".join(head + rows) + "\n", encoding="utf-8")
