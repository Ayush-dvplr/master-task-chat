"""Write LEVERS.md from the registered weights, the lever map below and the wrong-solver sweep.

    python3 make_levers.py SWEEP_SUMMARY_JSON
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

WORK = Path(__file__).resolve().parent

# check -> (levers it needs, rule homes, observable)
LEVERS = {
    "artifacts_exist": (["STRUCT"], "K19", "seven files exist"),
    "archive_members_safe_src_layout": (["STRUCT"], "K1, K19", "zip member names"),
    "api_entry_points_importable": (["STRUCT"], "K1", "callables on migrakit"),
    "cli_module_runs_from_foreign_cwd": (["C"], "K10", "CLI output files, relative paths"),
    "visible_repo_tests_pass_from_archive": (["C"], "K1", "unittest result of delivered tests"),
    "summary_json_matches_delivered_run": (["HONESTY"], "K19", "summary.json vs delivered run"),
    "module_core_claims_match_archive": (["HONESTY"], "K19", "module_core.json vs archive AST"),
    "module_parser_claims_match_archive": (["HONESTY"], "K19", "module_parser.json vs archive AST"),
    "module_report_claims_match_archive": (["HONESTY"], "K19", "module_report.json vs archive AST"),
    "test_fixes_matches_visible_test_runs": (["HONESTY"], "K19", "test_fixes.json vs real runs"),
    "repair_report_well_formed": (["HONESTY"], "K19", "repair-report.json shape"),
    "signature_keeps_explicit_null": (["LV-MR-6"], "M10, N1", "state_signature result"),
    "plan_tracks_field_dropped_earlier": (["LV-MR-1"], "M6", "plan, gadget P1"),
    "plan_uses_edge_enabled_earlier": (["LV-MR-1"], "M6, N4", "plan, gadget P2"),
    "plan_revisits_schema_with_new_state": (["LV-MR-1"], "M6, M7", "plan, gadget P3"),
    "plan_renamed_null_satisfies_has": (["LV-MR-1", "LV-MR-6"], "M6 + N1/N5", "plan, gadget P4"),
    "plan_tie_first_edge_decides": (["LV-MR-2"], "M8", "plan, gadget P6"),
    "plan_tie_longer_plan_wins": (["LV-MR-2"], "M8", "plan, gadget P7"),
    "plan_unreachable_by_state": (["F", "LV-MR-1"], "K12 + M6", "error code, gadget P8"),
    "ladder_small": (["LV-MR-1", "LV-MR-2"], "M6 + M8", "plan, 6x3 ladder"),
    "ladder_medium_state": (["D", "LV-MR-1"], "K14 + M6", "plan, 16x4 ladder"),
    "ladder_large_state": (["D", "LV-MR-1"], "K14 + M6", "plan, 45x3 ladder"),
    "ladder_large_tie": (["D", "LV-MR-2"], "K14 + M8", "plan, 45x3 tie ladder"),
    "ladder_large_null": (["D", "LV-MR-6"], "K14 + N1/N2", "plan, 45x3 null ladder"),
    "exec_add_fill_absent_vs_null": (["LV-MR-4"], "N4", "executor payload"),
    "exec_operations_apply_in_order": (["B"], "M4, M5", "executor payload"),
    "exec_correction_unset_breaks_step2": (["LV-MR-7"], "C4, M11", "executor result"),
    "exec_correction_null_blocks_lacks": (["LV-MR-7", "LV-MR-6"], "C4 + N1/N2", "executor result"),
    "exec_correction_null_counted_absent": (["LV-MR-7", "LV-MR-4"], "C4 + N2 (field_policy)", "executor result"),
    "exec_correction_first_arrival_only": (["LV-MR-7"], "C4", "executor result"),
    "exec_correction_at_source_enables_step1": (["LV-MR-7"], "C4", "executor result"),
    "identity_merge_chain": (["F"], "P2", "resolve_partner values"),
    "identity_merge_loop_rejected": (["F"], "P3", "resolve_partner values"),
    "pipe_rejection_codes": (["F"], "K12, K15", "codes of rejected lines"),
    "pipe_bad_lines_run_continues": (["F"], "K15", "status and payload of every line"),
    "pipe_replay_across_aliases": (["LV-MR-5", "F"], "K16 + P2", "statuses"),
    "pipe_token_vs_json_null_conflict": (["LV-MR-5", "LV-MR-4"], "K16 + N6/N8", "statuses"),
    "pipe_edit_dropped_by_migration_conflict": (["LV-MR-5"], "K16", "statuses"),
    "pipe_reissue_supersedes_holder": (["LV-MR-5"], "K16 + C7", "statuses and payloads"),
    "pipe_received_seq_decides_holder": (["LV-MR-5"], "K13", "statuses"),
    "pipe_mid_path_failure_record": (["LV-MR-7", "F"], "C3/C4 + P2", "record fields"),
    "pipe_attempted_vs_migrated_counts": (["LV-MR-7", "REPORT"], "C4/M11 + K18", "summary attempted and by_status"),
    "pipe_invalid_corrections_listed": (["F"], "C8", "summary invalid_corrections"),
    "pipe_partner_token_list_replaces_default": (["LV-MR-4"], "N7", "migrated payload"),
    "summary_categories_from_taxonomy": (["REPORT"], "T1, T2", "build_summary by_category"),
    "summary_partner_order": (["REPORT"], "T3", "build_summary partners"),
    "negative_hardcoded_sample_answers": (["CHEAT"], "", "seed or hidden edge ids in archive source"),
    "negative_filename_dependent_behaviour": (["CHEAT"], "", "records under two feed names"),
    "negative_deleted_visible_tests": (["CHEAT"], "", "visible test file content"),
    "negative_nondeterministic_output": (["CHEAT"], "", "two identical runs"),
}


def main() -> None:
    src = (WORK / "test_output.src.py").read_text(encoding="utf-8")
    weights = {m.group(1): int(m.group(2)) for m in re.finditer(r"^criteria\.(\w+)\(weight=(-?\d+)\)$", src, re.M)}
    missing = set(weights) ^ set(LEVERS)
    if missing:
        raise SystemExit(f"lever map and registrations differ: {sorted(missing)}")
    sweep = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")) if len(sys.argv) > 1 else {}
    positive = sum(w for w in weights.values() if w > 0)
    lines = ["# LEVERS: schema-migration-plan-repair", "",
             f"{len(weights)} checks; positive total {positive}; negative total {-sum(w for w in weights.values() if w < 0)}. "
             "A check counts for every lever it needs. Rule homes: K = repository_contract.md, M = migration_semantics.md, "
             "N = null_semantics.ini header, C = correction_log.txt header, P = partner_aliases.xml header, T = report_taxonomy.json rules.", "",
             "| check | w | levers | rule homes | observable | lost by (wrong solvers, measured) |", "|---|---|---|---|---|---|"]
    lost_by = defaultdict(list)
    for name, info in sweep.items():
        for check in info["lost"]:
            lost_by[check].append(name)
    for name, w in weights.items():
        levers, homes, observable = LEVERS[name]
        lines.append(f"| {name} | {w:+d} | {', '.join(levers)} | {homes} | {observable} | {', '.join(lost_by[name]) or '-'} |")
    share = defaultdict(int)
    for name, w in weights.items():
        if w > 0:
            for lever in LEVERS[name][0]:
                share[lever] += w
    lines += ["", "## Weight per lever (positive, needed-by)", "", "| lever | weight | share of positive |", "|---|---|---|"]
    for lever, w in sorted(share.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {lever} | {w} | {100 * w / positive:.1f}% |")
    if sweep:
        lines += ["", "## Wrong solvers (tests-only, measured with the real checks, local runner)", "",
                  "| solver | lever reverted | score | weight lost | checks lost | negatives fired |", "|---|---|---|---|---|---|"]
        for name, info in sweep.items():
            lines.append(f"| {name} | {info['lever']} | {info['score']:.4f} | {info['lost_weight']} | {', '.join(info['lost']) or 'none'} | {', '.join(info['negatives_fired']) or 'none'} |")
    (WORK / "LEVERS.md").write_text("\n".join(lines).replace("| - |", "| none |") + "\n", encoding="utf-8")
    print("LEVERS.md written")


if __name__ == "__main__":
    main()
