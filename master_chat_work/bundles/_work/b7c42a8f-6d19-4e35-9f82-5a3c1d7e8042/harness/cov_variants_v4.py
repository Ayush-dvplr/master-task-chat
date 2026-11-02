"""variants.py <solve.py> <dest_dir>: write one single-wrong-reading variant per lever."""
import sys
from pathlib import Path

PATCHES = {
    "R_paren_negative": ('_paren_num = _re.compile(r"\\(\\d[\\d,]*\\)")', '_paren_num = _re.compile(r"\\(-\\d+\\)")'),
    "R_block_unit": ('r["paid_to_date"] % 1000 == 0', 'r["paid_to_date"] % 1000 == 1'),
    "R_identical_duplicate": ('"duplicate_identical": max(0, collapsed_count - disambiguated),', '"duplicate_identical": 0,'),
    "R_cycle_gap": ("return min(later)[1], True", "return None, False"),
    "R_zero_capacity": ("if cap == 0:", "if False:"),
    "R_no_qualified_layer": ('r["reason"] = "NO_QUALIFIED_LAYER"', 'r["reason"] = "NONE"'),
    "R_retract_over_excluded": ('        if ref in retractions:\n            canonical = resolve_reinsurer_identity(', '        if ref in retractions and resolve_reinsurer_identity(g["reinsurer_raw"], g["recorded_instant"], alias_map, reinsurer_master) is not None:\n            canonical = resolve_reinsurer_identity('),
    "R_zero_over_excluded": ('"outcome": "EXCLUDED", "reason": "UNRESOLVABLE_CHAIN",\n                "ceded_hours": 0,\n                "_retracted": True,', '"outcome": "EXCLUDED", "reason": "UNRESOLVABLE_CHAIN",\n                "ceded_hours": 0,\n                "_retracted": False,'),
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
