"""One contract rule dropped per mutant: writes WORK/rule_mut/<id>.py from solution/solve.py."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOLVE = HERE.parent.parent / "flood-repair-portfolio" / "solution" / "solve.py"
DEST = HERE / "rule_mut"

# (id, rule, contract line, old text, new text)
RULES = [
    ("missing_file_silent", "missing declared file: no documents, ERROR MISSING_FILE, exit 1", "19",
     '            raise InputError("ERROR MISSING_FILE " + name)', '            continue'),
    ("row_numbers_from_zero", "row numbers count data rows of the whole file from 1", "21",
     '    for number, row in enumerate(book["permits"], 1):', '    for number, row in enumerate(book["permits"], 0):'),
    ("dup_unchecked", "DUPLICATE_PROPOSAL", "37",
     '            if proposal in seen:', '            if False:'),
    ("households_range_unchecked", "INVALID_INPUT households whole number 1..60", "37",
     '            elif not (households.isdigit() and households.isascii() and 1 <= int(households) <= 60):',
     '            elif not households.lstrip("-").isdigit():'),
    ("unknown_site_unchecked", "INVALID_INPUT unknown site", "37",
     '            elif site not in book["sites"] or crew not in book["crews"]:',
     '            elif crew not in book["crews"]:'),
    ("unknown_crew_unchecked", "INVALID_INPUT unknown crew", "37",
     '            elif site not in book["sites"] or crew not in book["crews"]:',
     '            elif site not in book["sites"]:'),
    ("override_unchecked", "INVALID_INPUT risk_override not empty and not A-D", "37",
     '            elif override not in ("",) + CLASSES:', '            elif False:'),
    ("segment_unknown_unchecked", "segment_codes UNKNOWN_PROPOSAL", "38",
     '            if fields[0] not in ids:\n                code = "UNKNOWN_PROPOSAL"\n            elif fields[1] not in book["segment_rate"]:',
     '            if fields[1] not in book["segment_rate"]:'),
    ("segment_invalid_unchecked", "segment_codes INVALID_INPUT segment not a key", "38",
     '            elif fields[1] not in book["segment_rate"]:\n                code = "INVALID_INPUT"\n        elif name == "permits.csv":',
     '        elif name == "permits.csv":'),
    ("permit_unknown_unchecked", "permits UNKNOWN_PROPOSAL", "39",
     '            if fields[1] not in ids:\n                code = "UNKNOWN_PROPOSAL"\n            elif fields[2] not in STATUSES:',
     '            if fields[2] not in STATUSES:'),
    ("permit_status_unchecked", "permits INVALID_INPUT status", "39",
     '            elif fields[2] not in STATUSES:\n                code = "INVALID_INPUT"\n        else:',
     '        else:'),
    ("exclusion_unknown_unchecked", "exclusions UNKNOWN_PROPOSAL", "40",
     '            if any(x not in ids and x not in site_ids for x in (first, second)):\n                code = "UNKNOWN_PROPOSAL"\n            elif first == second:',
     '            if first == second:'),
    ("exclusion_same_unchecked", "exclusions INVALID_INPUT first equals second", "40",
     '            elif first == second:\n                code = "INVALID_INPUT"', '            elif False:\n                code = "INVALID_INPUT"'),
    ("nonpositive_unchecked", "NONPOSITIVE_BENEFIT", "42",
     '        if benefit < 1 and rnd.fault is None:', '        if benefit < 0 and rnd.fault is None:'),
    ("nonpositive_last_row", "NONPOSITIVE_BENEFIT reports the first such row", "42",
     '        if benefit < 1 and rnd.fault is None:', '        if benefit < 1 and (rnd.fault is None or rnd.fault["code"] == "NONPOSITIVE_BENEFIT"):'),
    ("exclusion_one_order", "exclusion joins the pair in either order", "58",
     '        mark(by_site.get(first, [first]) if first not in rnd.detail else [first],',
     '        if first > second:\n            continue\n        mark(by_site.get(first, [first]) if first not in rnd.detail else [first],'),
    ("audit_sources_unordered", "PAIR sources in order crew, permit, exclusion", "73",
     '"sources": [s for s in ("crew", "permit", "exclusion") if s in found],',
     '"sources": sorted(found),'),
    ("audit_line_skips_blank", "policy_audit line is the 1-based line number in the file", "72",
     '    for line_no, line in enumerate(book["queries"], 1):\n        parts = line.split()\n        if not parts:\n            continue',
     '    for line_no, line in enumerate([q for q in book["queries"] if q.split()], 1):\n        parts = line.split()'),
    ("withdrawn_rows_all_rounds", "withdrawn_permit_rows counts planned rounds only", "74",
     '"withdrawn_permit_rows": sum(1 for r in planned for p in r.permits if p[2] == "withdrawn"),',
     '"withdrawn_permit_rows": sum(1 for r in ordered for p in r.permits if p[2] == "withdrawn"),'),
    ("conflict_pairs_by_source_sum", "conflict_pairs counts distinct pairs", "74",
     '"conflict_pairs": sum(len(r.pairs) for r in planned),',
     '"conflict_pairs": sum(len(v) for r in planned for v in r.pairs.values()),'),
    ("rounds_in_file_order", "rounds listed in ascending round id", "68",
     '    return [rounds[rid] for rid in sorted(rounds)]', '    return list(rounds.values())'),
    ("region_skips_empty_rounds", "region rounds: one object for every planned round", "76",
     '                entries.append({"round": r.rid, "selected": mine,',
     '                if not mine:\n                    continue\n                entries.append({"round": r.rid, "selected": mine,'),
    ("rejected_round_keeps_count", "rejected round proposals row count kept, selected empty, total 0", "70",
     '"selected": [] if r.fault else r.selected, "total_benefit": 0 if r.fault else r.total}',
     '"selected": [] if r.fault else r.selected, "total_benefit": 0 if r.fault else r.total, "fault": r.fault}'),
    ("third_party_import", "one self-contained file, python3 and its standard library only", "5",
     'import sys\n', 'import sys\nimport numpy  # a package outside the standard library\n'),
    ("rollups_from_other_portfolio", "every figure of a round comes from the one chosen portfolio", "64",
     '                mine = [p for p in r.selected if r.detail[p][field] == name]',
     '                mine = [p for p in r.selected[:-1] if r.detail[p][field] == name]'),
]


def main():
    src = SOLVE.read_text()
    DEST.mkdir(exist_ok=True)
    for rid, _rule, _line, old, new in RULES:
        assert src.count(old) == 1, rid
        (DEST / (rid + ".py")).write_text(src.replace(old, new))
    print(len(RULES), "rule mutants")


if __name__ == "__main__":
    main()
