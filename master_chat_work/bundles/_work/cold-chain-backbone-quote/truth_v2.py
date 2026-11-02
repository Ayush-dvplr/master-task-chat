"""P12 v2 (905cf6e): rewrite TRUTH.md timing table from runs/v2_time_books.json and the measured line from scores.
python3 -B truth_v2.py <BUNDLE> <dw_global> <kmb> <perlink> <report_only>"""
import json
import re
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent
truth = Path(sys.argv[1]) / "solution" / "TRUTH.md"
dw, kmb, perlink, report_only = sys.argv[2:6]
text = truth.read_text(encoding="utf-8")
times = json.loads((WORK / "runs" / "v2_time_books.json").read_text())
rows = ["| book | projects | limit (s) | oracle (s) |", "|---|---|---|---|"]
for name in ("fresh_1", "fresh_2", "fresh_3", "rescaled", "relocated", "rejections", "ties", "wide_1", "wide_2", "wide_3"):
    n, limit, sec, rc = times[name]
    assert rc == 0 and limit == 4 * n + 10, name
    rows.append("| %s | %d | %d | %.2f |" % (name, n, limit, sec))
table = re.compile(r"\| book \| projects \| limit \(s\) \| oracle \(s\) \|\n\|---\|---\|---\|---\|\n(?:\|[^\n]*\|\n)+")
assert len(table.findall(text)) == 1
text = table.sub("\n".join(rows) + "\n", text)
old = re.compile(r"Measured in Docker on these tests \(points of 109\): oracle 109 with both negatives silent; Dreyfus-Wagner\n"
                 r"over all cold rooms \d+; terminal-metric tree \d+; activation charged per booked link \d+; report lines\n"
                 r"charged per booked link with the quote right \d+\.")
assert len(old.findall(text)) == 1
text = old.sub("Measured in Docker on these tests (points of 109): oracle 109 with both negatives silent; Dreyfus-Wagner\n"
               "over all cold rooms %s; terminal-metric tree %s; activation charged per booked link %s; report lines\n"
               "charged per booked link with the quote right %s." % (dw, kmb, perlink, report_only), text)
truth.write_text(text, encoding="utf-8")
print("TRUTH rewritten")
