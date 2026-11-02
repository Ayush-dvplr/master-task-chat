# XREF tariff-engine-audit-repair (harden round 1, d62ffe6; test-hardening round 78d433c)

Values that appear in more than one bundle file, and retired round-0 values. Checked by
`master_chat_tasks/tools/xref_check.py`.

```json
{
 "entries": [
  {
   "key": "task slug",
   "value": "tariff-engine-audit-repair",
   "files": [
    "task.toml",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "contract path",
   "value": "/app/ci/api_contract.md",
   "files": [
    "instruction.md",
    "solution/TRUTH.md",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "archive path",
   "value": "/app/out/patched-repo.zip",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "solution/TRUTH.md",
    "solution/solve.py",
    "environment/ci/build_config.json",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "repo path",
   "value": "/app/repo",
   "files": [
    "instruction.md",
    "tests/test_output.py",
    "tests/judge.toml",
    "solution/TRUTH.md",
    "solution/solve.py",
    "environment/Dockerfile",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "billing_periods header",
   "value": "account,start,end,plan,commitment,allowance",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/billing_periods.csv",
    "environment/ci/api_contract.md",
    "environment/repo/tests/test_visible.py"
   ],
   "retired": []
  },
  {
   "key": "allowance field",
   "value": "allowance",
   "files": [
    "tests/test_output.py",
    "tests/judge.toml",
    "solution/TRUTH.md",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "exception reason malformed_quantity",
   "value": "malformed_quantity",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md",
    "environment/repo/src/tariff/parser.py"
   ],
   "retired": []
  },
  {
   "key": "exception reason unknown_meter",
   "value": "unknown_meter",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md",
    "environment/repo/src/tariff/parser.py"
   ],
   "retired": []
  },
  {
   "key": "exception reason inactive_meter",
   "value": "inactive_meter",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md",
    "environment/repo/src/tariff/parser.py"
   ],
   "retired": []
  },
  {
   "key": "exception reason outside_period",
   "value": "outside_period",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md",
    "environment/repo/src/tariff/parser.py"
   ],
   "retired": []
  },
  {
   "key": "exception reason duplicate_read",
   "value": "duplicate_read",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md",
    "environment/repo/src/tariff/parser.py"
   ],
   "retired": []
  },
  {
   "key": "deliverable key corrected_tests",
   "value": "corrected_tests",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "deliverable key previously_failing",
   "value": "previously_failing",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "deliverable key all_regressions_passed",
   "value": "all_regressions_passed",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "deliverable key lint_errors",
   "value": "lint_errors",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "deliverable key contract_terms",
   "value": "contract_terms",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "corrected test test_commitment_credit_base",
   "value": "test_commitment_credit_base",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md",
    "solution/solve.py",
    "environment/repo/tests/test_visible.py"
   ],
   "retired": []
  },
  {
   "key": "corrected test test_partial_period_standing_charge",
   "value": "test_partial_period_standing_charge",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md",
    "solution/solve.py",
    "environment/repo/tests/test_visible.py"
   ],
   "retired": []
  },
  {
   "key": "artifact repair-report.json",
   "value": "repair-report.json",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "artifact module_core.json",
   "value": "module_core.json",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "artifact module_parser.json",
   "value": "module_parser.json",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "artifact module_report.json",
   "value": "module_report.json",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "artifact test_fixes.json",
   "value": "test_fixes.json",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "artifact summary.json",
   "value": "summary.json",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "api entry point",
   "value": "build_invoices",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/package_manifest.json",
    "environment/ci/api_contract.md",
    "environment/repo/src/tariff/report.py"
   ],
   "retired": []
  },
  {
   "key": "input file build_config.json",
   "value": "build_config.json",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "input file regression_cases.jsonl",
   "value": "regression_cases.jsonl",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "input file failing_tests.log",
   "value": "failing_tests.log",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "input file lint_report.json",
   "value": "lint_report.json",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "input file package_manifest.json",
   "value": "package_manifest.json",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "input file rate_card.json",
   "value": "rate_card.json",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "input file meter_reads.jsonl",
   "value": "meter_reads.jsonl",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "input file accounts.csv",
   "value": "accounts.csv",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "rate card key standing_charge",
   "value": "standing_charge",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/rate_card.json",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "rate card key credit_rate",
   "value": "credit_rate",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/rate_card.json",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "regression key customer_claim",
   "value": "customer_claim",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "missing input message",
   "value": "missing input: ",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "defined term Account position",
   "value": "Account position",
   "files": [
    "solution/TRUTH.md",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "defined term Energy share",
   "value": "Energy share",
   "files": [
    "solution/TRUTH.md",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "judge R11 self-check",
   "value": "check R11 ok",
   "files": [
    "solution/TRUTH.md",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "judge R12 self-check",
   "value": "check R12 ok",
   "files": [
    "solution/TRUTH.md",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "rescaled test names",
   "value": "rescaled_energy_lines_exact",
   "files": [
    "tests/test_output.py"
   ],
   "retired": [
    "rescaled_lines_exact"
   ]
  },
  {
   "key": "api test names",
   "value": "api_energy_lines_exact",
   "files": [
    "tests/test_output.py"
   ],
   "retired": [
    "api_lines_exact"
   ]
  },
  {
   "key": "quantity exception wording",
   "value": "is not what the `quantity` field rule",
   "files": [
    "environment/ci/api_contract.md"
   ],
   "retired": [
    "a JSON number written with a decimal point"
   ]
  },
  {
   "key": "Month definition",
   "value": "Month: a calendar month",
   "files": [
    "environment/ci/api_contract.md"
   ],
   "retired": [
    "the account's billing period, its row"
   ]
  },
  {
   "key": "test positive points",
   "value": "test points of 670",
   "files": [
    "solution/TRUTH.md"
   ],
   "retired": [
    "test points of 488"
   ]
  },
  {
   "key": "judge R13 self-check",
   "value": "check R13 ok",
   "files": [
    "solution/TRUTH.md",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "rate card plan code list key",
   "value": "\"codes\"",
   "files": [
    "environment/ci/rate_card.json",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "recoded test names",
   "value": "recoded_lines_exact",
   "files": [
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "renamed test names",
   "value": "renamed_lines_exact",
   "files": [
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "judge last id",
   "value": "id = \"R16\"",
   "files": [
    "tests/judge.toml"
   ],
   "retired": []
  },
  {
   "key": "invoice plan field format",
   "value": "the row's `plan` value",
   "files": [
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "instruction exactness clause",
   "value": "graded whole on fresh inputs, and only an exact match counts",
   "files": [
    "instruction.md"
   ],
   "retired": [
    "on the shipped files and on fresh corpora of other periods and sizes",
    "pass only because they assert the drifted behaviour"
   ]
  },
  {
   "key": "exception reason replaced_estimate",
   "value": "replaced_estimate",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "read key estimated",
   "value": "estimated",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "rate card key standing_changes",
   "value": "standing_changes",
   "files": [
    "tests/test_output.py",
    "solution/solve.py",
    "environment/ci/api_contract.md",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "billing rows per account",
   "value": "one or more rows per account",
   "files": [
    "environment/ci/api_contract.md"
   ],
   "retired": [
    "and one row per account"
   ]
  },
  {
   "key": "accounts rows per meter",
   "value": "one or\nmore rows per meter of an account",
   "files": [
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "allowance carried clause",
   "value": "is added to the allowance of the account's next",
   "files": [
    "environment/ci/api_contract.md"
   ],
   "retired": [
    "take is not used"
   ]
  },
  {
   "key": "invoice sort",
   "value": "and then by `start`",
   "files": [
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "owned-row test names",
   "value": "estimated_read_accounts_on_fresh_rescaled",
   "files": [
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "payments file",
   "value": "payments.csv",
   "files": [
    "environment/ci/api_contract.md",
    "tests/test_output.py",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "payments header",
   "value": "account,start,paid",
   "files": [
    "environment/ci/api_contract.md",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "cumulative read field",
   "value": "cumulative",
   "files": [
    "environment/ci/api_contract.md",
    "tests/test_output.py",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "plan revisions field",
   "value": "revisions",
   "files": [
    "environment/ci/api_contract.md",
    "tests/test_output.py",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "vouchers file",
   "value": "vouchers.csv",
   "files": [
    "environment/ci/api_contract.md",
    "tests/test_output.py",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "vouchers header",
   "value": "account,voucher,amount",
   "files": [
    "environment/ci/api_contract.md",
    "environment/ci/vouchers.csv",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "statements flag",
   "value": "--statements",
   "files": [
    "environment/ci/api_contract.md",
    "tests/test_output.py",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "statement redeemed key",
   "value": "redeemed",
   "files": [
    "environment/ci/api_contract.md",
    "tests/test_output.py",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "statement due key",
   "value": "\"due\"",
   "files": [
    "environment/ci/api_contract.md",
    "tests/test_output.py",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "statement list key",
   "value": "statements",
   "files": [
    "environment/ci/api_contract.md",
    "tests/test_output.py",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "split shipped settlement test names",
   "value": "shipped_energy_lines_exact",
   "files": [
    "tests/test_output.py"
   ],
   "retired": [
    "shipped_energy_and_settlement_exact",
    "archive_and_metadata_follow_build_config",
    "repair_report_and_failing_cases"
   ]
  },
  {
   "key": "split deliverable test names",
   "value": "previously_failing_matches_log",
   "files": [
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "deleted judge act",
   "value": "r10_opens_grader_paths",
   "files": [
    "tests/judge.toml"
   ],
   "retired": [
    "api_contract.md it edited",
    "r10_runs_on_edited_contract_copy"
   ]
  },
  {
   "key": "contract codes field",
   "value": "one of its `codes`",
   "files": [
    "environment/ci/api_contract.md"
   ],
   "retired": []
  },
  {
   "key": "judge R16 self-check",
   "value": "check R16 ok",
   "files": [
    "solution/TRUTH.md",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "batch statement test names",
   "value": "fresh_batch_statement_due_exact",
   "files": [
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "cycle statement test names",
   "value": "fresh_cycle_statement_due_exact",
   "files": [
    "tests/test_output.py"
   ],
   "retired": []
  }
 ]
}
```
