"""Rule coverage (G11): one mutant per contract rule, each a patch of solution/solve.py.

usage: python3 rule_mutants.py OUT_JSON SHARD NSHARDS
"""
import json
import sys
from pathlib import Path

from measure_variants import VARIANTS, run

C = "environment/ci/api_contract.md"
MUTANTS = {
    "M01_keep_visible_asserts": ("arbiter; visible tests corrected", f"{C}:3-5,132-134", VARIANTS["V_keep_asserts"]),
    "M02_socket_import": ("stdlib only, no network client", f"{C}:9-11",
        [("from decimal import ROUND_HALF_EVEN, Decimal", "import socket\nfrom decimal import ROUND_HALF_EVEN, Decimal")]),
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
    "M09_period_end_excluded": ("date ranges include both days", f"{C}:30-31,83",
        [('    if not period["start"] <= read["day"] <= period["end"]:',
          '    if not period["start"] <= read["day"] < period["end"]:')]),
    "M10_subtotal_number": ("amounts are JSON strings with two decimals", f"{C}:32-33",
        [('            "subtotal": f"{subtotal:.2f}",', '            "subtotal": float(subtotal),')]),
    "M11_bill_rejected_reads": ("only accepted reads are billed", f"{C}:37,45",
        [("    for read in accepted:\n", '    for read in [r for r in reads if r["quantity"] is not None]:\n')]),
    "M12_open_window_closed": ("empty active_to stays active", f"{C}:38-39",
        [("    return start <= day and (end is None or day <= end)",
          "    return start <= day and (end is not None and day <= end)")]),
    "M13_active_days_short": ("active days count both ends", f"{C}:40",
        [("    return max((end - start).days + 1, 0)", "    return max((end - start).days, 0)")]),
    "M14_strictly_above": ("credit when subtotal is at least commitment", f"{C}:41,123",
        [("    if subtotal >= commitment:", "    if subtotal > commitment:")]),
    "M15_half_up": ("line amount half to even", f"{C}:42,118", VARIANTS["V_half_up"]),
    "M16_calendar_month": ("month is the billing period", f"{C}:43-44,108-110", VARIANTS["V_month_calendar"]),
    "M17_quantity_max": ("period quantity is the sum of accepted reads", f"{C}:45",
        [('        usage[key] = usage.get(key, 0) + read["quantity"]',
          '        usage[key] = max(usage.get(key, 0), read["quantity"])')]),
    "M18_first_plan": ("plan named by billing_periods row", f"{C}:46,62-64",
        [('        plan = card["plans"][period["plan"]]', '        plan = card["plans"][sorted(card["plans"])[0]]')]),
    "M19_tiers_from_zero": ("tiers numbered from 1", f"{C}:47,104",
        [("    for number, tier in enumerate(tiers, start=1):", "    for number, tier in enumerate(tiers, start=0):")]),
    "M20_quoted_integer_coerced": ("quantity is a JSON integer; strings malformed", f"{C}:56,77-79",
        VARIANTS["V_qty_coerce"]),
    "M21_bool_negative_accepted": ("true, false and negative integers malformed", f"{C}:56,77-79",
        [("    if type(value) is int and value >= 0:", "    if isinstance(value, int):")]),
    "M22_integral_float_accepted": ("number with decimal point or exponent malformed", f"{C}:77-79",
        [("    if type(value) is int and value >= 0:\n        return value",
          "    if type(value) is float and value.is_integer() and value >= 0:\n        return int(value)\n"
          "    if type(value) is int and value >= 0:\n        return value")]),
    "M23_unknown_before_malformed": ("first applicable exception, malformed first", f"{C}:75,80-81",
        [('    if read["quantity"] is None:\n        return "malformed_quantity"\n'
          '    if key not in meters:\n        return "unknown_meter"\n',
          '    if key not in meters:\n        return "unknown_meter"\n'
          '    if read["quantity"] is None:\n        return "malformed_quantity"\n')]),
    "M24_outside_before_inactive": ("inactive_meter before outside_period", f"{C}:82-83",
        [('    if not _active(meters[key], read["day"]):\n        return "inactive_meter"\n'
          '    period = periods[read["account"]]\n'
          '    if not period["start"] <= read["day"] <= period["end"]:\n        return "outside_period"\n',
          '    period = periods[read["account"]]\n'
          '    if not period["start"] <= read["day"] <= period["end"]:\n        return "outside_period"\n'
          '    if not _active(meters[key], read["day"]):\n        return "inactive_meter"\n')]),
    "M25_outside_billed": ("outside_period reads rejected", f"{C}:83",
        [('    if not period["start"] <= read["day"] <= period["end"]:', "    if False:")]),
    "M26_duplicate_of_rejected": ("duplicate only of an earlier accepted read", f"{C}:84-85",
        [("    for read in reads:\n        reason = _reason(read, meters, periods, seen)",
          "    for read in reads:\n        reason = _reason(read, meters, periods, seen)\n"
          '        seen.add((read["account"], read["meter"], read["day"]))')]),
    "M27_exceptions_by_account": ("exceptions sorted by read_id", f"{C}:87-89",
        [('    exceptions.sort(key=lambda row: row["read_id"])',
          '    exceptions.sort(key=lambda row: (row["account"], row["read_id"]))')]),
    "M28_invoices_reversed": ("one invoice per row, sorted by account", f"{C}:93-94",
        [("    for account in sorted(periods):", "    for account in sorted(periods, reverse=True):")]),
    "M29_skip_unused_meters": ("every meter of the account is billed", f"{C}:97-98",
        [("        for key in sorted(k for k in meters if k[0] == account):",
          "        for key in sorted(k for k in meters if k[0] == account and k in usage):")]),
    "M30_tier_cap_exclusive": ("tier up to and including up_to", f"{C}:100-102",
        [("        top = quantity if cap is None else min(quantity, cap)",
          "        top = quantity if cap is None else min(quantity, cap - 1)")]),
    "M31_zero_unit_tier_line": ("tier with no units has no line", f"{C}:102-103",
        [("        if top > floor:", "        if top >= floor:")]),
    "M32_rate_rounded_first": ("exact energy value is units x rate", f"{C}:105-106",
        [('"amount": money(units * rate)}', '"amount": money(money(rate) * units)}')]),
    "M33_no_proration": ("standing_charge x active days / days in the month", f"{C}:108-110",
        [('    exact = plan["standing_charge"] * active_days / month_days', '    exact = plan["standing_charge"]')]),
    "M34_zero_day_standing": ("no standing line without an active day", f"{C}:111-112",
        [("            if days:", "            if True:")]),
    "M35_standing_first": ("energy lines by tier, then standing", f"{C}:114-115",
        [("            lines.extend(core.energy_lines(key[1], usage.get(key, 0), plan))\n"
          "            days = _active_days(meters[key], period)\n            if days:\n"
          "                lines.append(core.standing_line(key[1], plan, days, month_days))",
          "            days = _active_days(meters[key], period)\n            if days:\n"
          "                lines.append(core.standing_line(key[1], plan, days, month_days))\n"
          "            lines.extend(core.energy_lines(key[1], usage.get(key, 0), plan))")]),
    "M36_float_values": ("amounts from decimal values as written", f"{C}:117", VARIANTS["V_float_round"]),
    "M37_subtotal_energy_only": ("subtotal is the sum of the line amounts", f"{C}:119",
        [('    subtotal = sum((line["amount"] for line in lines), Decimal("0.00"))',
          '    subtotal = sum((line["amount"] for line in lines if line["kind"] == "energy"), Decimal("0.00"))')]),
    "M38_credit_base_energy_only": ("credit base: accepted, rated, prorated lines", f"{C}:121-123",
        [("    if subtotal >= commitment:",
          '    if sum((l["amount"] for l in lines if l["kind"] == "energy"), Decimal("0.00")) >= commitment:')]),
    "M39_credit_rounded": ("total rounded, credit = subtotal minus total", f"{C}:123-125",
        VARIANTS["V_credit_rounded"]),
    "M40_document_key": ("document keys invoices and exceptions", f"{C}:127-128",
        [('    return {"invoices": invoices, "exceptions": exceptions}',
          '    return {"invoices": invoices, "rejected": exceptions}')]),
    "M41_zip_deflated": ("archive follows build_config", f"{C}:138-144",
        [('    method = zipfile.ZIP_STORED if archive["compression"] == "stored" else zipfile.ZIP_DEFLATED',
          "    method = zipfile.ZIP_DEFLATED")]),
    "M42_no_check_passed": ("repair-report has a passed check", f"{C}:149-152",
        [('"checks": checks})', '"checks": [dict(c, passed=False) for c in checks]})')]),
    "M43_lint_all_severities": ("lint_errors counts severity error", f"{C}:156-158",
        [('issue["module"] == f"tariff.{module}" and issue["severity"] == "error")',
          'issue["module"] == f"tariff.{module}")')]),
    "M44_contract_terms_short": ("parser contract_terms", f"{C}:160-162",
        [('"parser": {"contract_terms": ["VERSION", "build_invoices", "render"]},',
          '"parser": {"contract_terms": ["build_invoices", "render"]},')]),
    "M45_deterministic_text": ("report deterministic is a bool", f"{C}:162-163",
        [('"report": {"deterministic": deterministic},', '"report": {"deterministic": "yes"},')]),
    "M46_corrected_tests_short": ("corrected_tests lists changed tests", f"{C}:164-165",
        [('"corrected_tests": CORRECTED_TESTS,', '"corrected_tests": CORRECTED_TESTS[:1],')]),
    "M47_failing_fail_only": ("previously_failing includes FAIL and ERROR", f"{C}:166-168",
        [('(line.endswith(" ... FAIL") or line.endswith(" ... ERROR"))', 'line.endswith(" ... FAIL")')]),
    "M48_expected_disputed": ("regression expected is customer_claim", f"{C}:170-179",
        [('        rows.append({"name": case["name"], "expected": case["customer_claim"],',
          '        rows.append({"name": case["name"], "expected": case["disputed_total"],')]),
    "M49_any_regression": ("all_regressions_passed", f"{C}:168-169",
        [('all(row["passed"] for row in rows)', 'any(row["passed"] for row in rows)')]),
    "M50_artifact_count": ("summary artifacts and count", f"{C}:180-183",
        [('"artifact_count": len(ARTIFACTS)', '"artifact_count": len(ARTIFACTS) - 1')]),
    "M51_inputs_partial": ("summary inputs_used every /app/ci file", f"{C}:180-183",
        [("sorted(p.name for p in CI.iterdir() if p.is_file())",
          'sorted(p.name for p in CI.iterdir() if p.is_file() and p.suffix != ".md")')]),
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
