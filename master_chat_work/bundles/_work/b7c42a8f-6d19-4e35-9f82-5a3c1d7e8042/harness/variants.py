"""variants.py <solve.py> <dest_dir>: write one single-wrong-reading variant per lever."""
import sys
from pathlib import Path

PATCHES = {
    "L1_paid_col7": ('"paid_to_date": int(row[4]),',
                     '"paid_to_date": _dollars(row[7]) if len(row) >= 8 and row[7] else int(row[4]),'),
    "L2_individual_retention": ("if event_retention_consumed.get(event_id, False):", "if False:"),
    "L3_no_admission_bar": ("if _parse_instant(text) > bar:", "if False:"),
    "L4_single_precedence": ("table = precedence_post if inst and inst >= cutover else precedence_pre",
                             "table = precedence_pre"),
    "L5_no_epoch_split": ('return "%s#%d" % (rid, 2 if instant >= bound_dt else 1)', 'return "%s#1" % rid'),
    "L6_unclipped_factor": ("f = max(1.0, min(2.5, inc / p))", "f = inc / p"),
    "L7_remainder_tiebreak": ('-unmet.get(r["claim_ref"], 0),', "0,"),
}

src = Path(sys.argv[1]).read_text()
dest = Path(sys.argv[2])
dest.mkdir(parents=True, exist_ok=True)
for name, (old, new) in PATCHES.items():
    n = src.count(old)
    if n != 1:
        print("PATCH_MISS", name, n)
        continue
    (dest / (name + ".py")).write_text(src.replace(old, new))
    print("ok", name)
