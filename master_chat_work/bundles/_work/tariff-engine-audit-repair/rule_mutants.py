"""Rule coverage (G11): one mutant per contract rule, each a patch of solution/solve.py.

usage: python3 rule_mutants.py OUT_JSON SHARD NSHARDS
"""
import json
import sys
from pathlib import Path

from measure_variants import VARIANTS, run

C = "environment/ci/api_contract.md"
MUTANTS = {
    "M01_keep_visible_asserts": ("arbiter; visible tests corrected", f"{C}:3-5,174-176", VARIANTS["V_keep_asserts"]),
    "M02_socket_import": ("stdlib only, no network client", f"{C}:9-11",
        [('import calendar\nfrom datetime import date, timedelta', 'import calendar\nimport socket\nfrom datetime import date, timedelta')]),
    "M03_version_unchanged": ("VERSION equals manifest version", f"{C}:12-13",
        [('    (PKG / "__init__.py").write_text(init, encoding="utf-8")', "    pass")]),
    "M04_dependencies_kept": ("pyproject dependencies empty", f"{C}:13-15",
        [('line = "dependencies = []"', "line = line")]),
    "M05_api_rejects_text_path": ("build_invoices(data_dir) returns the document", f"{C}:16-17",
        [("    reads, meters, periods, card = _load(data_dir)",
          '    if isinstance(data_dir, str):\n        raise TypeError("data_dir must be a Path")\n'
          "    reads, meters, periods, card = _load(data_dir)")]),
    "M06_render_prefix": ("render returns JSON text; CLI writes it", f"{C}:18-20",
        [("    return json.dumps(document, indent=2, sort_keys=True)",
          '    return "document " + json.dumps(document, indent=2, sort_keys=True)')]),
    "M07_missing_exit_1": ("missing input exit 2 and message", f"{C}:21-24",
        [("            return 2", "            return 1")]),
    "M08_no_trim": ("text values trimmed", f"{C}:28-29",
        [("def _text(value):\n    return str(value).strip()", "def _text(value):\n    return str(value)")]),
    "M09_period_end_excluded": ("date ranges include both days", f"{C}:30-31,80,110",
        [('        if row["start"] <= day <= row["end"]:', '        if row["start"] <= day < row["end"]:')]),
    "M10_subtotal_number": ("amounts are JSON strings with two decimals", f"{C}:32-33",
        [('            "subtotal": f"{subtotal:.2f}",', '            "subtotal": float(subtotal),')]),
    "M11_bill_rejected_reads": ("only accepted reads are billed", f"{C}:37,53",
        [("    for read in accepted:\n", '    for read in [r for r in reads if r["quantity"] is not None]:\n'),
         ('        key = (read["account"], parser._row(periods[read["account"]], read["day"])["start"], read["meter"])',
          '        key = (read["account"], (parser._row(periods.get(read["account"], []), read["day"]) or {"start": None})["start"], read["meter"])')]),
    "M12_open_window_closed": ("empty active_to stays active", f"{C}:41-43",
        [('    return any(start <= day and (end is None or day <= end) for start, end in windows)', '    return any(start <= day and (end is not None and day <= end) for start, end in windows)')]),
    "M13_active_days_short": ("active days count both ends", f"{C}:44,145",
        [('"units": units, "exact": exact}', '"units": units - 1, "exact": exact}')]),
    "M14_strictly_above": ("credit when subtotal is at least commitment", f"{C}:165",
        [("    if subtotal >= commitment:", "    if subtotal > commitment:")]),
    "M15_half_up": ("line amount half to even", f"{C}:50-51,159-160", VARIANTS["V_half_up"]),
    "M16_month_is_period": ("month is a calendar month, not the billing period", f"{C}:52,142-143", VARIANTS["N2_period_length"]),
    "M17_quantity_max": ("period quantity is the sum of accepted reads", f"{C}:53",
        [('        usage[key] = usage.get(key, 0) + read["quantity"]',
          '        usage[key] = max(usage.get(key, 0), read["quantity"])')]),
    "M18_first_plan": ("plan named by billing_periods row", f"{C}:54",
        [('        plan = _plan_entry(card["plans"], period["plan"])', '        plan = card["plans"][sorted(card["plans"])[0]]')]),
    "M19_tiers_from_zero": ("tiers numbered from 1", f"{C}:55",
        [("    for number, tier in enumerate(tiers, start=1):", "    for number, tier in enumerate(tiers, start=0):")]),
    "M20_quoted_integer_coerced": ("quantity is a JSON integer; strings malformed", f"{C}:64,105-106",
        VARIANTS["V_qty_coerce"]),
    "M21_bool_negative_accepted": ("true, false and negative integers malformed", f"{C}:64,105-106",
        [("    if type(value) is int and value >= 0:", "    if isinstance(value, int):")]),
    "M22_integral_float_accepted": ("number with decimal point or exponent malformed", f"{C}:64,105-106",
        [("    if type(value) is int and value >= 0:\n        return value",
          "    if type(value) is float and value.is_integer() and value >= 0:\n        return int(value)\n"
          "    if type(value) is int and value >= 0:\n        return value")]),
    "M23_unknown_before_malformed": ("first applicable exception, malformed first", f"{C}:103-106",
        [('    if read["quantity"] is None:\n        return "malformed_quantity"\n'
          '    if key not in meters:\n        return "unknown_meter"\n',
          '    if key not in meters:\n        return "unknown_meter"\n'
          '    if read["quantity"] is None:\n        return "malformed_quantity"\n')]),
    "M24_outside_before_inactive": ("inactive_meter before outside_period", f"{C}:103,109-110",
        [('    if not _active(meters[key], read["day"]):\n        return "inactive_meter"\n    if _row(periods.get(read["account"], []), read["day"]) is None:\n        return "outside_period"\n', '    if _row(periods.get(read["account"], []), read["day"]) is None:\n        return "outside_period"\n    if not _active(meters[key], read["day"]):\n        return "inactive_meter"\n')]),
    "M25_outside_billed": ("outside_period reads rejected", f"{C}:110",
        [('    if _row(periods.get(read["account"], []), read["day"]) is None:\n        return "outside_period"\n', ''),
         ('        key = (read["account"], parser._row(periods[read["account"]], read["day"])["start"], read["meter"])',
          '        key = (read["account"], (parser._row(periods.get(read["account"], []), read["day"]) or {"start": None})["start"], read["meter"])')]),
    "M26_duplicate_of_rejected": ("duplicate only of an earlier accepted read", f"{C}:111-112",
        [('        reason = _reason(read, meters, periods, seen, actual)\n', '        reason = _reason(read, meters, periods, seen, actual)\n        seen.add((read["account"], read["meter"], read["day"], read["estimated"]))\n')]),
    "M27_exceptions_by_account": ("exceptions sorted by read_id", f"{C}:121-123",
        [('    exceptions.sort(key=lambda row: row["read_id"])',
          '    exceptions.sort(key=lambda row: (row["account"], row["read_id"]))')]),
    "M28_invoices_reversed": ("one invoice per row, sorted by account", f"{C}:127-128",
        [("    for account in sorted(periods):", "    for account in sorted(periods, reverse=True):")]),
    "M29_skip_unused_meters": ("every meter of the account is billed", f"{C}:131-132",
        [("        for key in sorted(k for k in meters if k[0] == account):",
          "        for key in sorted(k for k in meters if k[0] == account and k in usage):")]),
    "M30_tier_cap_exclusive": ("tier up to and including up_to", f"{C}:134-137",
        [("        high = last if cap is None else min(last, cap)",
          "        high = last if cap is None else min(last, cap - 1)")]),
    "M31_zero_unit_tier_line": ("tier with no units has no line", f"{C}:137",
        [("        if high >= low:", "        if high >= low - 1:")]),
    "M32_rate_rounded_first": ("exact energy value is units x rate", f"{C}:140",
        [('"exact": units * Fraction(rate)}', '"exact": units * Fraction(money(rate))}')]),
    "M33_no_proration": ("standing_charge x active days / days in the month", f"{C}:142-143",
        [('            exact += standing_charge(plan, day) / length', '            exact = standing_charge(plan, day)')]),
    "M34_zero_day_standing": ("no standing line without an active day", f"{C}:145-146",
        [('                if spans:\n                    lines.append(core.standing_line(key[1], plan, spans))\n', '                lines.append(core.standing_line(key[1], plan, spans))\n')]),
    "M35_standing_first": ("energy lines by tier, then standing", f"{C}:148-149",
        [('                lines.extend(core.energy_lines(key[1], position, quantity, plan))\n                position += quantity\n                spans = _active_spans(meters[key], period)\n                if spans:\n                    lines.append(core.standing_line(key[1], plan, spans))\n', '                spans = _active_spans(meters[key], period)\n                if spans:\n                    lines.append(core.standing_line(key[1], plan, spans))\n                lines.extend(core.energy_lines(key[1], position, quantity, plan))\n                position += quantity\n')]),
    "M36_float_values": ("amounts from decimal values as written", f"{C}:151-152", VARIANTS["V_float_round"]),
    "M37_subtotal_energy_only": ("subtotal is the sum of the line amounts", f"{C}:160-161",
        [('    subtotal = sum((line["amount"] for line in lines), Decimal("0.00"))',
          '    subtotal = sum((line["amount"] for line in lines if line["kind"] == "energy"), Decimal("0.00"))')]),
    "M38_credit_base_energy_only": ("credit base: accepted, rated, prorated lines", f"{C}:163-164",
        [("    if subtotal >= commitment:",
          '    if sum((l["amount"] for l in lines if l["kind"] == "energy"), Decimal("0.00")) >= commitment:')]),
    "M39_credit_rounded": ("total rounded, credit = subtotal minus total", f"{C}:165-167",
        VARIANTS["V_credit_rounded"]),
    "M40_document_key": ("document keys invoices and exceptions", f"{C}:169-170",
        [('    return {"invoices": invoices, "exceptions": exceptions}',
          '    return {"invoices": invoices, "rejected": exceptions}')]),
    "M41_zip_deflated": ("archive follows build_config", f"{C}:180-186",
        [('    method = zipfile.ZIP_STORED if archive["compression"] == "stored" else zipfile.ZIP_DEFLATED',
          "    method = zipfile.ZIP_DEFLATED")]),
    "M42_no_check_passed": ("repair-report has a passed check", f"{C}:191-194",
        [('"checks": checks})', '"checks": [dict(c, passed=False) for c in checks]})')]),
    "M43_lint_all_severities": ("lint_errors counts severity error", f"{C}:198-200",
        [('issue["module"] == f"tariff.{module}" and issue["severity"] == "error")',
          'issue["module"] == f"tariff.{module}")')]),
    "M44_contract_terms_short": ("parser contract_terms", f"{C}:202-204",
        [('"parser": {"contract_terms": ["VERSION", "build_invoices", "render"]},',
          '"parser": {"contract_terms": ["build_invoices", "render"]},')]),
    "M45_deterministic_text": ("report deterministic is a bool", f"{C}:204-205",
        [('"report": {"deterministic": deterministic},', '"report": {"deterministic": "yes"},')]),
    "M46_corrected_tests_short": ("corrected_tests lists changed tests", f"{C}:206-207",
        [('"corrected_tests": CORRECTED_TESTS,', '"corrected_tests": CORRECTED_TESTS[:1],')]),
    "M47_failing_fail_only": ("previously_failing includes FAIL and ERROR", f"{C}:208-210",
        [('(line.endswith(" ... FAIL") or line.endswith(" ... ERROR"))', 'line.endswith(" ... FAIL")')]),
    "M48_expected_disputed": ("regression expected is customer_claim", f"{C}:212-216",
        [('        rows.append({"name": case["name"], "expected": case["customer_claim"],',
          '        rows.append({"name": case["name"], "expected": case["disputed_total"],')]),
    "M49_any_regression": ("all_regressions_passed", f"{C}:210-211",
        [('all(row["passed"] for row in rows)', 'any(row["passed"] for row in rows)')]),
    "M50_artifact_count": ("summary artifacts and count", f"{C}:222-225",
        [('"artifact_count": len(ARTIFACTS)', '"artifact_count": len(ARTIFACTS) - 1')]),
    "M51_inputs_partial": ("summary inputs_used every /app/ci file", f"{C}:222-224",
        [("sorted(p.name for p in CI.iterdir() if p.is_file())",
          'sorted(p.name for p in CI.iterdir() if p.is_file() and p.suffix != ".md")')]),
    "M52_allowance_ignored": ("allowance and energy share", f"{C}:45,47-51", VARIANTS["N1_no_share"]),
    "M53_share_one_pass": ("unshared allowance shared again", f"{C}:151-154", VARIANTS["N1_one_pass"]),
    "M54_tiers_per_meter": ("tiers by account position", f"{C}:38-40,134-136", VARIANTS["N3_per_meter"]),
    "M55_allowance_on_standing": ("energy share only on energy lines", f"{C}:47-51,159-160",
        [('    live = [line for line in lines if line["kind"] == "energy"]', "    live = list(lines)")]),
    "M56_share_exceeds_line": ("never more than a line's exact value", f"{C}:47-49,152-153",
        [('            take = min(part, line["exact"])', "            take = part")]),
    "M57_month_of_start": ("each calendar month has its own days", f"{C}:52,142-143", VARIANTS["N2_start_month"]),
    "M58_code_defaults_first": ("L11 plan value that is no key: first entry", "environment/ci/rate_card.json:7-10",
        VARIANTS["L11_first_plan"]),
    "M59_code_defaults_last": ("L11 plan value that is no key: last entry", "environment/ci/rate_card.json:7-10",
        VARIANTS["L11_last_plan"]),
    "M60_codes_untrimmed": ("L11 codes compared untrimmed (padded code)", f"environment/ci/rate_card.json:50-53;{C}:28-29",
        [("if name in [str(code).strip() for code in plan.get", "if name in [str(code) for code in plan.get"),
         ('        raise ValueError(f"plan {name!r} names {len(owners)} rate card entries")',
          "        return next(iter(plans.values()))")]),
    "M62_output_plan_key": ("invoice plan is the row's plan value", f"{C}:130",
        [('            "plan": period["plan"],', '            "plan": next(k for k, v in card["plans"].items() if v is plan),'),
         ('        assert doc["invoices"][0]["plan"] == value.strip(), doc["invoices"][0]["plan"]\n', "")]),
    "M63_estimated_ignored": ("estimated field, duplicate per estimated, replaced_estimate", f"{C}:65,111-119", VARIANTS["Q1_off"]),
    "M64_estimate_file_order": ("estimate replaced wherever the actual read stands", f"{C}:113-115",
        [('    for read in [r for r in reads if not r["estimated"]] + [r for r in reads if r["estimated"]]:', "    for read in reads:")]),
    "M65_changes_ignored": ("standing charge of a day from standing_changes", f"{C}:92-99,142-143", VARIANTS["Q2_off"]),
    "M66_changes_list_order": ("entry with the latest from on or before the day", f"{C}:94-96",
        [("        if since <= day and (found is None or since > found[0]):", "        if since <= day:")]),
    "M67_last_billing_row": ("one or more billing rows, each its own invoice", f"{C}:75-85,110,127-128", VARIANTS["Q3_off"]),
    "M68_rows_file_order": ("invoices sorted by account then start", f"{C}:127-128",
        [("    for rows in periods.values():\n        rows.sort(key=lambda row: row[\"start\"])\n", "")]),
    "M69_allowance_not_carried": ("unused allowance added to the next invoice", f"{C}:154-159", VARIANTS["Q4_off"]),
    "M70_last_accounts_row": ("one or more accounts rows per meter", f"{C}:41-43,67-73", VARIANTS["Q5_off"]),
}


def main():
    target, shard, nshards = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    results = json.loads(target.read_text()) if target.exists() else {}
    for index, (name, (rule, where, patches)) in enumerate(MUTANTS.items()):
        if index % nshards != shard or name in results:
            continue
        result = run(name, patches)
        result.update(rule=rule, where=where)
        results[name] = result
        target.write_text(json.dumps(results, indent=1))
        failed = [k for k, v in result.get("checks", {}).items() if not k.startswith("negative") and not v["pass"]]
        print(name, result.get("score"), len(failed), result.get("error", "")[-200:], flush=True)
    print("ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
