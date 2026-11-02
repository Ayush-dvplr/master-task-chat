# XREF: emberforge-vault-settlement (P12 v3 r2, 24 Oct 2026)

Values that appear in more than one bundle file, plus the channel totals that must move together (judge.toml, reward.toml, TRUTH.md). Earlier table kept in XREF.before_lp1.md. TRUTH.md shas are checked by the tool itself.

```json
{
 "entries": [
  {
   "key": "slug",
   "value": "emberforge-vault-settlement",
   "files": [
    "task.toml",
    "tests/test_output.py",
    "solution/TRUTH.md",
    "solution/solve.sh",
    "environment/Dockerfile"
   ],
   "retired": []
  },
  {
   "key": "program path",
   "value": "settle_vault.py",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "tests/judge.toml",
    "solution/TRUTH.md",
    "solution/solve.sh",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "output dir",
   "value": "/app/out",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "tests/judge.toml",
    "solution/TRUTH.md",
    "solution/solve.sh",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "data dir",
   "value": "/app/data",
   "files": [
    "instruction.md",
    "tests/test_output.py",
    "tests/judge.toml",
    "solution/TRUTH.md",
    "solution/solve.sh",
    "solution/solve.py",
    "environment/Dockerfile"
   ],
   "retired": []
  },
  {
   "key": "record shapes doc",
   "value": "record_shapes.md",
   "files": [
    "instruction.md",
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "rulings file",
   "value": "council_rulings.json",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md",
    "solution/solve.py",
    "environment/data/record_shapes.md"
   ],
   "retired": []
  },
  {
   "key": "digest file",
   "value": "clerks_digest.md",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "record summary.json",
   "value": "summary.json",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "solution/TRUTH.md",
    "solution/solve.py",
    "environment/data/record_shapes.md"
   ],
   "retired": []
  },
  {
   "key": "record vault_audit.json",
   "value": "vault_audit.json",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "solution/TRUTH.md",
    "solution/solve.py",
    "environment/data/record_shapes.md"
   ],
   "retired": []
  },
  {
   "key": "record reconciliation.json",
   "value": "reconciliation.json",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "solution/TRUTH.md",
    "solution/solve.py",
    "environment/data/record_shapes.md"
   ],
   "retired": []
  },
  {
   "key": "record data_quality.json",
   "value": "data_quality.json",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "tests/judge.toml",
    "solution/TRUTH.md",
    "solution/solve.py",
    "environment/data/record_shapes.md"
   ],
   "retired": []
  },
  {
   "key": "record allocation.json",
   "value": "allocation.json",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "solution/TRUTH.md",
    "solution/solve.py",
    "environment/data/record_shapes.md"
   ],
   "retired": []
  },
  {
   "key": "record workshop_cinderhall.json",
   "value": "workshop_cinderhall.json",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "record workshop_gloamworks.json",
   "value": "workshop_gloamworks.json",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "record workshop_slagmoor.json",
   "value": "workshop_slagmoor.json",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "record workshop_verdigris.json",
   "value": "workshop_verdigris.json",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "record guild_ashen_compact.json",
   "value": "guild_ashen_compact.json",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "record guild_tidebound_league.json",
   "value": "guild_tidebound_league.json",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "time limit",
   "value": "7200",
   "files": [
    "instruction.md",
    "task.toml"
   ],
   "retired": []
  },
  {
   "key": "graded whole sentence",
   "value": "graded whole on fresh inputs",
   "files": [
    "instruction.md"
   ],
   "retired": []
  },
  {
   "key": "live forge term",
   "value": "live forge entr",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md",
    "environment/data/rulebook_salvage.md"
   ],
   "retired": []
  },
  {
   "key": "check structure_program_delivered",
   "value": "structure_program_delivered",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": [
    "closure_mix",
    "consumed_cap_mix",
    "consumed_retired_mix",
    "plan48_mix",
    "plan24_mix",
    "requisitions_12_allocation",
    "cap_boundary_workshop_figures",
    "partition_guild_reports",
    "temporal_boundary_vault_audit",
    "structure_findings_canonical_form",
    "negative_nondeterministic_output",
    "negative_imports_outside_standard_library",
    "structure_records_delivered",
    "priority_tie_allocation",
    "merge_chain_smith_rows"
   ]
  },
  {
   "key": "check structure_program_takes_directories",
   "value": "structure_program_takes_directories",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check structure_canonical_serialisation",
   "value": "structure_canonical_serialisation",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check structure_reruns_byte_identical",
   "value": "structure_reruns_byte_identical",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check program_names_missing_input",
   "value": "program_names_missing_input",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check whole_summary",
   "value": "whole_summary",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check whole_vault_audit",
   "value": "whole_vault_audit",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check whole_reconciliation",
   "value": "whole_reconciliation",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check whole_data_quality",
   "value": "whole_data_quality",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check whole_allocation",
   "value": "whole_allocation",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check whole_workshop_reports",
   "value": "whole_workshop_reports",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check whole_guild_reports",
   "value": "whole_guild_reports",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check unit_charge_season_total",
   "value": "unit_charge_season_total",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check cap_release_closures",
   "value": "cap_release_closures",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check live_window_refusals",
   "value": "live_window_refusals",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check quiet_rules_findings_and_funding",
   "value": "quiet_rules_findings_and_funding",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check mutation_family_multiplier",
   "value": "mutation_family_multiplier",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check mutation_grade_step",
   "value": "mutation_grade_step",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check negative_hardcoded_sample_answers",
   "value": "negative_hardcoded_sample_answers",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check negative_filename_dependent_behaviour",
   "value": "negative_filename_dependent_behaviour",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check negative_reads_training_corpus_at_runtime",
   "value": "negative_reads_training_corpus_at_runtime",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check negative_rebinds_verifier_dependencies",
   "value": "negative_rebinds_verifier_dependencies",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "judge r1_checks_multi_unit_forge_charge",
   "value": "r1_checks_multi_unit_forge_charge",
   "files": [
    "tests/judge.toml"
   ],
   "retired": []
  },
  {
   "key": "judge r2_checks_cap_after_credited_salvage",
   "value": "r2_checks_cap_after_credited_salvage",
   "files": [
    "tests/judge.toml"
   ],
   "retired": []
  },
  {
   "key": "judge r3_checks_window_after_credited_forge",
   "value": "r3_checks_window_after_credited_forge",
   "files": [
    "tests/judge.toml"
   ],
   "retired": []
  },
  {
   "key": "judge r4_program_code_quality",
   "value": "r4_program_code_quality",
   "files": [
    "tests/judge.toml"
   ],
   "retired": [
    "r4_program_reports_every_caught_error",
    "r4_program_names_missing_input"
   ]
  },
  {
   "key": "judge r5_writes_under_app_data",
   "value": "r5_writes_under_app_data",
   "files": [
    "tests/judge.toml"
   ],
   "retired": []
  },
  {
   "key": "judge r6_online_solution_lookup",
   "value": "r6_online_solution_lookup",
   "files": [
    "tests/judge.toml"
   ],
   "retired": [
    "r6_program_opens_network_connection"
   ]
  },
  {
   "key": "judge r7_claims_check_passed_against_output",
   "value": "r7_claims_check_passed_against_output",
   "files": [
    "tests/judge.toml"
   ],
   "retired": []
  },
  {
   "key": "judge r8_reads_grader_files",
   "value": "r8_reads_grader_files",
   "files": [
    "tests/judge.toml"
   ],
   "retired": []
  },
  {
   "key": "judge weight",
   "value": "judge = 0.041666666666666664",
   "files": [
    "tests/reward.toml"
   ],
   "retired": [
    "judge = 0.021739130434782608",
    "judge = 0.025 }",
    "judge = 0.045454545454545456"
   ]
  },
  {
   "key": "test weight",
   "value": "test_output = 0.008620689655172414",
   "files": [
    "tests/reward.toml"
   ],
   "retired": [
    "test_output = 0.0049504950495049506",
    "test_output = 0.006172839506172839",
    "test_output = 0.006097560975609756",
    "test_output = 0.00909090909090909",
    "test_output = 0.009259259259259259"
   ]
  },
  {
   "key": "test positive total",
   "value": "**58**",
   "files": [
    "solution/TRUTH.md"
   ],
   "retired": [
    "**82**",
    "**55**",
    "**54**"
   ]
  },
  {
   "key": "judge retired figures",
   "value": "r1_checks_multi_unit_forge_charge",
   "files": [
    "tests/judge.toml"
   ],
   "retired": [
    "r12_states_closing_balance_r05",
    "130027",
    "recovering the council's draw",
    "each settlement stage"
   ]
  },
  {
   "key": "dead timeout",
   "value": "_AGENT_TIMEOUT = TIME_LIMIT_SECONDS",
   "files": [
    "tests/test_output.py"
   ],
   "retired": [
    "_AGENT_TIMEOUT = 180",
    "earlier matches the settled",
    "narrowed season matches",
    "merge chain matches"
   ]
  },
  {
   "key": "giveaways removed",
   "value": "rulebook_salvage.md",
   "files": [
    "tests/test_output.py"
   ],
   "retired": [
    "This is deliberate",
    "never stands in",
    "last three admitted forges",
    "Your final message must state"
   ]
  },
  {
   "key": "charge default",
   "value": "accrued settled charge",
   "files": [
    "tests/test_output.py",
    "environment/data/rulebook_salvage.md",
    "environment/data/rulebook_admission.md"
   ],
   "retired": []
  },
  {
   "key": "check negative_imports_third_party_module",
   "value": "negative_imports_third_party_module",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": [
    "program_imports_stdlib_only"
   ]
  },
  {
   "key": "check negative_program_opens_network",
   "value": "negative_program_opens_network",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": [
    "r9_program_opens_network_connection"
   ]
  },
  {
   "key": "requisition ladder helper",
   "value": "_requisition_ladder",
   "files": [
    "tests/test_output.py"
   ],
   "retired": [
    "_lever_ladder"
   ]
  },
  {
   "key": "missing input rule",
   "value": "the missing file",
   "files": [
    "instruction.md",
    "tests/test_output.py"
   ],
   "retired": [
    "every except clause"
   ]
  },
  {
   "key": "judge criterion count",
   "value": "eight criteria",
   "files": [
    "solution/TRUTH.md"
   ],
   "retired": [
    "nine criteria"
   ]
  }
 ]
}
```
