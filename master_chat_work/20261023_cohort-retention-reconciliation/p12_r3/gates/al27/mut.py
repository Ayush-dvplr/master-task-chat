import json, re, sys, types, tempfile, shutil
from pathlib import Path

import os
B = Path(os.environ.get("CRR_BUNDLE", "/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/cohort-retention-reconciliation"))
SRC = (B / "tests/test_output.py").read_text()

rk = types.ModuleType("rewardkit")
rk.criterion = lambda *a, **k: (lambda f: f)
class _C:
    def __getattr__(self, n):
        return lambda *a, **k: None
rk.criteria = _C()
sys.modules["rewardkit"] = rk

WEIGHTS = {m.group(1): int(m.group(2)) for m in re.finditer(r"criteria\.(\w+)\(weight=(-?\d+)\)", SRC)}


def load(src):
    ns = {"__name__": "t_" + str(id(src))}
    exec(compile(src, "test_output.py", "exec"), ns)
    return ns


def score(mutations):
    src = SRC
    for old, new in mutations:
        assert old in src, old
        src = src.replace(old, new, 1)
    agent = load(src)
    g = load(SRC)
    root = Path(tempfile.mkdtemp(prefix="crrmut-"))
    out_dir = root / "app_out"
    out_dir.mkdir()

    def write(docs, out):
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        for name, doc in docs.items():
            (out / name).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")

    def fake_run(command):
        write(agent["derive"](Path(command[2])), command[3])

    write(agent["derive"](B / "environment/data"), out_dir)
    shutil.copy(B / "solution/solve.py", out_dir / "derive_report.py")
    g["OUT"] = out_dir
    g["SCRIPT"] = out_dir / "derive_report.py"
    g["CORPUS"] = root / "corpus_absent"
    g["_run_untrusted"] = fake_run
    g["_LOCK_FILE"] = root / "lock"
    res = {}
    for name, w in WEIGHTS.items():
        res[name] = g[name](Path("/app"))
    shutil.rmtree(root, ignore_errors=True)
    pos = sum(w * res[n] for n, w in WEIGHTS.items() if w > 0)
    neg = sum(w * res[n] for n, w in WEIGHTS.items() if w < 0)
    lost = {n: round(res[n], 3) for n, w in WEIGHTS.items() if w > 0 and res[n] < 1}
    fired = {n: res[n] for n, w in WEIGHTS.items() if w < 0 and res[n] > 0}
    return pos, neg, lost, fired


M = {
 "baseline": [],
 "id_no_strip": [('return text.strip().lower()', 'return text.lower()')],
 "id_no_lower": [('return text.strip().lower()', 'return text.strip()')],
 "date_strip_accepted": [('if _DAY.fullmatch(text) is None:', 'if _DAY.fullmatch(text.strip()) is None:'), ('return date.fromisoformat(text)\n', 'return date.fromisoformat(text.strip())\n')],
 "date_loose_iso": [('if _DAY.fullmatch(text) is None:\n        return None\n', '')],
 "cents_strip": [('_CENTS.fullmatch(row["value_cents"]) is None', '_CENTS.fullmatch(row["value_cents"].strip()) is None')],
 "cents_signed": [('_CENTS.fullmatch(row["value_cents"]) is None', 're.fullmatch(r"[+-]?[0-9]+", row["value_cents"]) is None')],
 "cents_underscore": [('_CENTS.fullmatch(row["value_cents"]) is None', 're.fullmatch(r"[0-9][0-9_]*", row["value_cents"]) is None')],
 "order_ooc_before_malformed": [('        if broken:\n            removed_by = "malformed"\n        elif period is None:\n            removed_by = "out_of_calendar"\n', '        if day is not None and period is None:\n            removed_by = "out_of_calendar"\n        elif broken:\n            removed_by = "malformed"\n')],
 "dup_counts_removed_rows": [('        elif key in survivors:\n', '        elif "duplicate" in tags:\n')],
 "dup_key_after_merge": [('        key = (account, row["event_date"], kind)\n', '        key = (owner_on(account, _real_day(row["event_date"])) if _real_day(row["event_date"]) else account, row["event_date"], kind)\n')],
 "excluded_before_dup": [('        elif key in survivors:\n            removed_by = "duplicate"\n        else:\n            survivors.add(key)\n            removed_by = "excluded" if who in barred else ("unknown_account" if who not in accounts else "")\n', '        elif who in barred:\n            removed_by = "excluded"\n        elif key in survivors:\n            removed_by = "duplicate"\n        else:\n            survivors.add(key)\n            removed_by = "unknown_account" if who not in accounts else ""\n')],
 "unknown_before_excluded": [('removed_by = "excluded" if who in barred else ("unknown_account" if who not in accounts else "")', 'removed_by = "unknown_account" if who not in accounts else ("excluded" if who in barred else "")')],
 "merge_strictly_after": [('nxt = _in_force(merges, account, day)', 'nxt = _in_force(merges, account, day - timedelta(days=1))')],
 "merge_single_hop": [('            visited.add(nxt)\n            account = nxt\n', '            return nxt\n')],
 "merge_earliest_wins": [('nxt = _in_force(merges, account, day)', 'nxt = next((v for o, s, p, v in sorted(merges, key=lambda r: (r[1], r[2])) if o == account and s <= day), None)')],
 "merge_ignores_date": [('nxt = _in_force(merges, account, day)', 'nxt = _in_force(merges, account, date.max)')],
 "plan_tie_earlier_row": [('_in_force(plan_rows, account, day)', '_in_force([(o, s, -p, v) for o, s, p, v in plan_rows], account, day)')],
 "plan_ignores_date": [('_in_force(plan_rows, account, day)', '_in_force(plan_rows, account, date.max)')],
 "plan_strictly_after": [('_in_force(plan_rows, account, day)', '_in_force(plan_rows, account, day - timedelta(days=1))')],
 "plan_no_opening": [('or _id(accounts[account]["plan"])', 'or ""')],
 "override_ignored": [('if segment_of(account) in overrides:', 'if False:')],
 "minimum_strict": [('cents >= floor', 'cents > floor')],
 "minimum_ignored": [('cents >= floor', 'True')],
 "cohort_latest_qualifier": [('cents >= floor and who not in cohort_of', 'cents >= floor')],
 "pre_cohort_not_counted": [('early += 1', 'early += 0')],
 "pre_cohort_in_matrix": [('        if rank[period] < rank[cohort_of[who]]:\n            early += 1\n        else:\n            seen_in.add((who, period))\n', '        if rank[period] < rank[cohort_of[who]]:\n            early += 1\n        seen_in.add((who, period))\n')],
 "offset_past_end_zero": [('                break\n            target', '                counts[str(offset)] = 0\n                continue\n            target')],
 "survival_equals_retention": [('floor_so_far = v if floor_so_far is None else min(floor_so_far, v)', 'floor_so_far = v')],
 "revenue_from_cohort_period_only": [('        if who in cohort_of:\n            plain[who] += booked', '        if who in cohort_of and rank[period] >= rank[cohort_of[who]]:\n            plain[who] += booked')],
 "no_balance_cap": [('booked = -min(cents, balance.get(who, 0))', 'booked = -cents')],
 "one_global_balance": [('balance[who] = balance.get(who, 0) + booked', 'balance["*"] = balance.get("*", 0) + booked'), ('booked = -min(cents, balance.get(who, 0))', 'booked = -min(cents, balance.get("*", 0))')],
 "clean_order_date_only": [('kept.sort(key=lambda item: (item[0], item[1], item[2]))', 'kept.sort(key=lambda item: item[0])')],
 "clean_order_file": [('kept.sort(key=lambda item: (item[0], item[1], item[2]))', 'pass')],
 "clean_order_type_desc": [('kept.sort(key=lambda item: (item[0], item[1], item[2]))', 'kept.sort(key=lambda item: item[2], reverse=True); kept.sort(key=lambda item: (item[0], item[1]))')],
 "control_zero": [('return sorted(off), residual', 'return sorted(off), 0')],
 "merge_tie_earlier_row": [('nxt = _in_force(merges, account, day)', 'nxt = _in_force([(o, s, -p, v) for o, s, p, v in merges], account, day)')],
 "zero_revenue_cohort_dropped": [('"revenue_cents_by_cohort": revenue,', '"revenue_cents_by_cohort": {k: v for k, v in revenue.items() if v},')],
 "totals_include_uncohorted": [('    balance: dict[str, int] = {}\n', '    balance: dict[str, int] = {}\n    _extra = []\n'), ('        balance[who] = balance.get(who, 0) + booked\n', '        balance[who] = balance.get(who, 0) + booked\n        if who not in cohort_of:\n            _extra.append(booked)\n'), ('total = sum(revenue.values())', 'total = sum(revenue.values()) + sum(_extra)')],
 "unhonored_include_uncohorted": [('    balance: dict[str, int] = {}\n', '    balance: dict[str, int] = {}\n    _lost = []\n'), ('        balance[who] = balance.get(who, 0) + booked\n', '        balance[who] = balance.get(who, 0) + booked\n        if who not in cohort_of:\n            _lost.append(lost)\n'), ('"unhonored_cents": sum(short.values()),', '"unhonored_cents": sum(short.values()) + sum(_lost),')],
 "offset_zero_flag_ignored": [('if rules["offset_zero_is_full"]:', 'if False:')],
 "offset_zero_always": [('if rules["offset_zero_is_full"]:', 'if True:')],
 "control_no_strip": [('(row.get("value_cents") or "").strip()', '(row.get("value_cents") or "")')],
 "control_sign_flipped": [('residual = recorded - counted["value_cents_sum"]', 'residual = counted["value_cents_sum"] - recorded')],
 "mismatches_unsorted_reversed": [('return sorted(off), residual', 'return off[::-1], residual')],
 "mismatches_manifest_order": [('return sorted(off), residual', 'return off, residual')],
 "excluded_count_rows": [('"excluded_account_count": len(barred),', '"excluded_account_count": len(_table(root / "exclusions.csv")),')],
 "merge_count_resolving_only": [('"merge_rule_count": len(merge_table),', '"merge_rule_count": len({r[0] for r in merges}),')],
 "register_dup_survivors_only": [('        if key in seen:\n', '        if key in survivors:\n')],
 "register_dup_not_on_malformed": [('        if key in seen:\n', '        if key in seen and not broken:\n')],
 "register_only_removing_reason": [('register.append({"event_id": row["event_id"], "reasons": sorted(tags)})', 'register.append({"event_id": row["event_id"], "reasons": [removed_by]})')],
 "register_file_order": [('register.sort(key=lambda item: item["event_id"])', 'pass')],
 "per_cohort_all": [('for c in cohorts[:2]:', 'for c in cohorts:')],
 "per_cohort_lexical": [('for c in cohorts[:2]:', 'for c in sorted(cohorts)[:2]:')],
 "calendar_file_order": [('order = [period for _, _, period in calendar]', 'order = [row["period"] for row in _table(root / "period_calendar.csv")]')],
 "calendar_lexical_order": [('order = [period for _, _, period in calendar]', 'order = sorted(period for _, _, period in calendar)')],
 "audit_lists_file_order": [('"qualifying_event_types": sorted(qualifying),', '"qualifying_event_types": [_id(k) for k in rules["qualifying_event_types"]],')],
 "audit_activity_file_order": [('"activity_event_types": sorted(activity),', '"activity_event_types": [_id(k) for k in rules["activity_event_types"]],')],
 "audit_revenue_file_order": [('"revenue_event_types": sorted(revenue_types),', '"revenue_event_types": [_id(k) for k in rules["revenue_event_types"]],')],
 "audit_raw_spelling": [('"qualifying_event_types": sorted(qualifying),', '"qualifying_event_types": sorted(rules["qualifying_event_types"]),')],
 "plan_weight_keys_raw": [('weights = {_id(k): int(v)', 'weights = {k: int(v)')],
 "override_keys_raw": [('        _id(row["segment"]): int(row["weight_override"].strip())', '        row["segment"]: int(row["weight_override"].strip())')],
 "rate_unreduced": [('return "0" if denominator == 0 else str(Fraction(numerator, denominator))', 'import math\n    g = math.gcd(numerator, denominator) or 1\n    return "0" if denominator == 0 else (str(numerator // g) if denominator == g else f"{numerator}/{denominator}")')],
 "rate_zero_denominator_text": [('return "0" if denominator == 0 else', 'return "0/0" if denominator == 0 else')],
 "segment_includes_uncohorted": [('    for account in cohort_of:\n        entry', '    for account in sorted(set(cohort_of) | {w for _, w, _, _, _ in kept}):\n        entry')],
}

if __name__ == "__main__":
    pick = sys.argv[1:] or list(M)
    for name in pick:
        try:
            pos, neg, lost, fired = score(M[name])
            print(f"{name}: pos {pos:.3f}/71 ({pos/71:.3f}) neg {neg} lost {lost} fired {fired}")
        except Exception as e:
            print(f"{name}: ERROR {type(e).__name__}: {e}")
