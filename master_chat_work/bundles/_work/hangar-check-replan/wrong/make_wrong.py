"""Write one wrong program per slip: solution/solve.py with one reading changed.

Usage: python3 -B make_wrong.py SOLVE_PY OUTDIR
Each mutant is the reference text plus an override block placed before the
`if __name__ == "__main__":` line, or one exact text replacement.
"""
import sys
from pathlib import Path

SRC = Path(sys.argv[1]).read_text()
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
MAIN = 'if __name__ == "__main__":'
assert SRC.count(MAIN) == 1

SETTLE_HEAD = '''
def settle(rows, grants, shift_cost, due_of):
    left = sum(grants.values())
    own = dict(grants)
    paying = [row for row in rows if row["decision"] == "scheduled"]
'''
SETTLE_TAIL = '''
    for row in rows:
        shifts, covered = row["overtime_shifts"], taken.get(row["request_id"], 0)
        row["overtime_cost"] = shift_cost * shifts
        row["allowance_shifts"] = covered
        row["paid_shifts"] = shifts - covered
        row["allowance_credit"] = shift_cost * covered
        row["settled_overtime_cost"] = row["overtime_cost"] - row["allowance_credit"]
'''
RANKED = 'sorted(paying, key=lambda row: (CLASS_RANK[row["aircraft_class"]], due_of[row["request_id"]], row["request_id"]))'


def settle_variant(order, body):
    return SETTLE_HEAD + "    taken = {}\n    for row in %s:\n%s" % (order, body) + SETTLE_TAIL


TAKE = '        taken[row["request_id"]] = min(row["overtime_shifts"], left)\n        left -= taken[row["request_id"]]\n'

OVERRIDES = {
    # settlement slips
    "s_unordered": settle_variant('sorted(paying, key=lambda row: row["request_id"])', TAKE),
    "s_start_key": settle_variant('sorted(paying, key=lambda row: (CLASS_RANK[row["aircraft_class"]], row["start_date"], row["request_id"]))', TAKE),
    "s_per_base_cap": settle_variant(RANKED, '        taken[row["request_id"]] = min(row["overtime_shifts"], own[row["base"]])\n        own[row["base"]] -= taken[row["request_id"]]\n'),
    "s_whole_only": settle_variant(RANKED, '        taken[row["request_id"]] = row["overtime_shifts"] if row["overtime_shifts"] <= left else 0\n        left -= taken[row["request_id"]]\n'),
    "s_cap_not_subtracted": settle_variant(RANKED, TAKE) + '''
_settle_right = settle


def settle(rows, grants, shift_cost, due_of):
    _settle_right(rows, grants, shift_cost, due_of)
    for row in rows:
        row["paid_shifts"] = row["overtime_shifts"]
        row["settled_overtime_cost"] = row["overtime_cost"]
''',
    "s_granted_not_used": '''
_reports_right = build_reports


def build_reports(inputs, requests):
    reports = _reports_right(inputs, requests)
    cost = inputs.shift_cost
    for base in BASE_ORDER:
        part = reports["region_%s.json" % base]
        part["allowance_used"] = part["allowance_granted"]
        part["allowance_credit"] = cost * part["allowance_granted"]
        part["settled_overtime_cost"] = part["overtime_cost"] - part["allowance_credit"]
    summary = reports["summary.json"]
    for row in summary["bases"]:
        part = reports["region_%s.json" % row["base"]]
        row["allowance_used"] = part["allowance_used"]
        row["settled_overtime_cost"] = part["settled_overtime_cost"]
    s = summary["settlement"]
    s["allowance_used"] = s["allowance_granted"]
    s["allowance_left"] = 0
    s["allowance_credit"] = cost * s["allowance_granted"]
    s["settled_overtime_cost"] = s["overtime_cost"] - s["allowance_credit"]
    return reports
''',
    # universe slip: only bases and segments seen in the planned records
    "u_from_records": '''
_reports_right = build_reports


def build_reports(inputs, requests):
    reports = _reports_right(inputs, requests)
    seen_bases = {r.base for r in requests}
    seen_segments = {name for name, classes in SEGMENT_CLASSES for r in requests if r.aircraft_class in classes}
    for base in BASE_ORDER:
        if base not in seen_bases:
            del reports["region_%s.json" % base]
    for name, _ in SEGMENT_CLASSES:
        if name not in seen_segments:
            del reports["segment_%s.json" % name]
    summary = reports["summary.json"]
    summary["bases"] = [row for row in summary["bases"] if row["base"] in seen_bases]
    summary["segments"] = [row for row in summary["segments"] if row["segment"] in seen_segments]
    return reports
''',
}

REPLACE = {
    # duplicate test also counts ignored rows (other seasons, DONE, CANCELLED)
    "x_ids_from_ignored": [(
        '        if row.get("season") != inputs.season or row.get("status") != "OPEN":\n            continue\n        request_id = row.get("request_id")\n',
        '        request_id = row.get("request_id")\n        if row.get("season") != inputs.season or row.get("status") != "OPEN":\n            ids_read.add(request_id)\n            continue\n')],
    # plan readings
    "p_earliest_only": [(
        '            if request.published > early and self.can_start(request.published, length):\n                yield request.published, squeeze\n', '')],
    "p_first_found_tie": [(
        'if held is None or joined[:5] < held[:5]:', 'if held is None or joined[:3] < held[:3]:'),
        ('winner = min(combos.values(), key=lambda v: v[:5])', 'winner = min(combos.values(), key=lambda v: v[:3])'),
        ('if held is None or merged < held:', 'if held is None or merged[:3] < held[:3]:'),
        ('if used not in best or value < best[used]:', 'if used not in best or value[:3] < best[used][:3]:'),
        ('if record is None or best[used] < record:', 'if record is None or best[used][:3] < record[:3]:')],
    "p_defer_no_slot_only": [(
        '                        if choice is None:\n',
        '                        if choice is None and self.fits_alone(request):\n                            continue\n                        if choice is None:\n')],
    "p_pool_per_base": [(
        '                if used + extra > inputs.pool:', '                if extra > inputs.pool // 4:')],
    # data quality and value readings
    "q_line_from_one": [(
        'enumerate(inputs.request_rows, start=2)', 'enumerate(inputs.request_rows, start=1)')],
    "c_no_clip": [(
        'self.available = max(1, inputs.day_number(iso_day(available)))', 'self.available = inputs.day_number(iso_day(available))')],
    "p_no_revised": [(
        'available = inputs.revised.get(self.tail, row["available_from"])', 'available = row["available_from"]')],
}

for name, block in OVERRIDES.items():
    text = SRC.replace(MAIN, block.strip("\n") + "\n\n\n" + MAIN)
    (OUT / (name + ".py")).write_text(text)
for name, pairs in REPLACE.items():
    text = SRC
    for old, new in pairs:
        assert text.count(old) == 1, (name, old)
        text = text.replace(old, new)
    (OUT / (name + ".py")).write_text(text)
print("wrote", len(OVERRIDES) + len(REPLACE))
