# XREF: emberforge-vault-settlement (P12 r1, 22 Oct 2026)

Values that appear in more than one bundle file, plus the channel totals that must move together (judge.toml weights, reward.toml, TRUTH.md).

```json
{
 "entries": [
  {
   "key": "slug",
   "value": "emberforge-vault-settlement",
   "files": [
    "task.toml",
    "solution/TRUTH.md",
    "solution/solve.sh",
    "environment/Dockerfile",
    "tests/test_output.py"
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
    "environment/data/record_shapes.md",
    "tests/test_output.py",
    "solution/TRUTH.md",
    "solution/solve.py"
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
    "environment/data/record_shapes.md",
    "tests/test_output.py",
    "solution/TRUTH.md",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "record vault_audit.json",
   "value": "vault_audit.json",
   "files": [
    "instruction.md",
    "task.toml",
    "environment/data/record_shapes.md",
    "tests/test_output.py",
    "solution/TRUTH.md",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "record reconciliation.json",
   "value": "reconciliation.json",
   "files": [
    "instruction.md",
    "task.toml",
    "environment/data/record_shapes.md",
    "tests/test_output.py",
    "solution/TRUTH.md",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "record data_quality.json",
   "value": "data_quality.json",
   "files": [
    "instruction.md",
    "task.toml",
    "environment/data/record_shapes.md",
    "tests/test_output.py",
    "solution/TRUTH.md",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "record allocation.json",
   "value": "allocation.json",
   "files": [
    "instruction.md",
    "task.toml",
    "environment/data/record_shapes.md",
    "tests/test_output.py",
    "solution/TRUTH.md",
    "solution/solve.py"
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
   "key": "check closure_mix",
   "value": "closure_mix",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check consumed_cap_mix",
   "value": "consumed_cap_mix",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check consumed_retired_mix",
   "value": "consumed_retired_mix",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check plan48_mix",
   "value": "plan48_mix",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check plan24_mix",
   "value": "plan24_mix",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check requisitions_12_allocation",
   "value": "requisitions_12_allocation",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check priority_tie_allocation",
   "value": "priority_tie_allocation",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check cap_boundary_workshop_figures",
   "value": "cap_boundary_workshop_figures",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check partition_guild_reports",
   "value": "partition_guild_reports",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check temporal_boundary_vault_audit",
   "value": "temporal_boundary_vault_audit",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check merge_chain_smith_rows",
   "value": "merge_chain_smith_rows",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check quiet_rules_findings",
   "value": "quiet_rules_findings",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
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
   "retired": []
  },
  {
   "key": "check structure_records_delivered",
   "value": "structure_records_delivered",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
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
   "key": "check structure_findings_canonical_form",
   "value": "structure_findings_canonical_form",
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
   "key": "check negative_nondeterministic_output",
   "value": "negative_nondeterministic_output",
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
   "key": "check negative_imports_outside_standard_library",
   "value": "negative_imports_outside_standard_library",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "judge total charge",
   "value": "130027",
   "files": [
    "tests/judge.toml",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "judge credited salvages",
   "value": "35",
   "files": [
    "tests/judge.toml",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "judge R04 closing",
   "value": "176",
   "files": [
    "tests/judge.toml",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "judge R11 closing",
   "value": "76",
   "files": [
    "tests/judge.toml",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "judge units granted",
   "value": "54 units",
   "files": [
    "tests/judge.toml",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "judge weight",
   "value": "judge = 0.021739130434782608",
   "files": [
    "tests/reward.toml"
   ],
   "retired": [
    "judge = 0.025 }"
   ]
  },
  {
   "key": "test weight",
   "value": "test_output = 0.0049504950495049506",
   "files": [
    "tests/reward.toml"
   ],
   "retired": []
  },
  {
   "key": "test positive total",
   "value": "**101**",
   "files": [
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "judge positive total",
   "value": "summing to 23",
   "files": [
    "solution/TRUTH.md"
   ],
   "retired": [
    "summing to 20"
   ]
  },
  {
   "key": "judge R05 closing",
   "value": "270",
   "files": [
    "tests/judge.toml",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "judge R12 name",
   "value": "r12_states_closing_balance_r05",
   "files": [
    "tests/judge.toml"
   ],
   "retired": []
  },
  {
   "key": "judge R6 wording",
   "value": "recovering the council's draw",
   "files": [
    "tests/judge.toml"
   ],
   "retired": [
    "each settlement stage"
   ]
  },
  {
   "key": "test_output sha",
   "value": "7446ace5e3e2bb9a0a0ad87e0573b8fb879008f7a14b7df3e6b46368b865589d",
   "files": [
    "solution/TRUTH.md"
   ],
   "retired": [
    "aaa72b5cafe15190c5c5a87690f3308e0e6254104968c68e03f99cb02c3155cc",
    "802df196540a19abb9215e7cb57e0f8aeae546a38ab1a87aa953426e6998107c",
    "7345a32125ee04d2bdbb1e73ba7dc1aa7d6f3e72bf580feb6b276773e7338b95"
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
   "key": "solve sha",
   "value": "76db9c400747879397ae7fc615ac9b591dfd8da7e0e8e56892fdfc21852fa57b",
   "files": [
    "solution/TRUTH.md"
   ],
   "retired": [
    "a646fbacb08167925e82e3381ca6bf833c8753e0b3efc701bcaf775db87297f0"
   ]
  }
 ]
}
```
