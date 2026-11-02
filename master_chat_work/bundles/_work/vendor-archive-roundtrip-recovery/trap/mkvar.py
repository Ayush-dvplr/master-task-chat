import sys
from pathlib import Path
EDITS = {
 "L2s": [('signed=rec["unit"] != "count")', 'signed=True)')],
 "L2u": [('signed=rec["unit"] != "count")', 'signed=False)')],
 "L2e": [('body += (int(rec["raw_value"]) % (1 << (8 * size))).to_bytes(size, "little")',
          'body += int(rec["raw_value"]).to_bytes(size, "little", signed=True)')],
 "L6": [('self.totals[rec["field"]] = rec["value"]', 'self.totals["_"] = rec["value"]'),
        ('rec["value"] = carry.totals.get(rec["field"], 0) + step', 'rec["value"] = carry.totals.get("_", 0) + step')],
 "L3": [('docs.append(decode_one(data, schema, run[0].clone()))\n            continue',
         'docs.append(decode_one(data, schema, run[0]))\n            open_runs[head["stream_id"]] = (run[0], head["seq_no"])\n            continue')],
 "L5c": [('keeps_open = flag if isinstance(flag, bool) else head["continues"]',
          'keeps_open = (flag.strip().lower() in ("true", "1", "yes")) if isinstance(flag, str) else (bool(flag) if flag is not None else head["continues"])')],
 "L5i": [('keeps_open = flag if isinstance(flag, bool) else head["continues"]', 'keeps_open = head["continues"]')],
 "L5n": [('exact = length if isinstance(length, int) and not isinstance(length, bool) else None',
          'exact = int(length) if length is not None else None')],
}
src, out, name = sys.argv[1], sys.argv[2], sys.argv[3]
text = Path(src).read_text()
for old, new in EDITS[name]:
    assert text.count(old) == 1, (name, old)
    text = text.replace(old, new)
Path(out).write_text(text)
