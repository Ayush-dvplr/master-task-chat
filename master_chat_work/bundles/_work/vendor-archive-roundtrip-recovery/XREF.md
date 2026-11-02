# XREF - vendor-archive-roundtrip-recovery

Values that appear in more than one file (plus the stated judge figures and weights). Checked by master_chat_tasks/tools/xref_check.py.

```json
{
 "entries": [
  {
   "key": "slug",
   "value": "vendor-archive-roundtrip-recovery",
   "files": [
    "task.toml",
    "environment/Dockerfile",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "format name",
   "value": "VARC1",
   "files": [
    "instruction.md",
    "task.toml",
    "environment/data/format_contract.md",
    "solution/TRUTH.md",
    "tests/test_output.py",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "vendor loader name",
   "value": "Sluicegate",
   "files": [
    "instruction.md",
    "environment/data/format_contract.md",
    "environment/data/loader_notes.md"
   ],
   "retired": []
  },
  {
   "key": "contract file",
   "value": "format_contract.md",
   "files": [
    "instruction.md",
    "solution/TRUTH.md",
    "environment/data/loader_notes.md",
    "environment/data/escape_rules.md"
   ],
   "retired": []
  },
  {
   "key": "appendix file",
   "value": "decoder_appendix.md",
   "files": [
    "instruction.md",
    "environment/data/format_contract.md",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "loader notes file",
   "value": "loader_notes.md",
   "files": [
    "environment/data/format_contract.md",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "revision map file",
   "value": "revision_map.ini",
   "files": [
    "environment/data/format_contract.md",
    "solution/TRUTH.md",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "field table file",
   "value": "field_layouts.csv",
   "files": [
    "environment/data/format_contract.md",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "alias table file",
   "value": "symbol_table.tsv",
   "files": [
    "environment/data/format_contract.md",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "catalog file",
   "value": "capture_catalog.jsonl",
   "files": [
    "environment/data/format_contract.md",
    "environment/data/decoder_appendix.md",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "stream 3 file capture_alpha.varc",
   "value": "capture_alpha.varc",
   "files": [
    "environment/data/format_contract.md",
    "environment/data/stream3_manifest.json",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "stream 3 file capture_beta.varc",
   "value": "capture_beta.varc",
   "files": [
    "environment/data/format_contract.md",
    "environment/data/stream3_manifest.json",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "stream 3 file capture_gamma.varc",
   "value": "capture_gamma.varc",
   "files": [
    "environment/data/format_contract.md",
    "environment/data/stream3_manifest.json",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "decoder path",
   "value": "/app/decode.py",
   "files": [
    "instruction.md",
    "task.toml",
    "solution/solve.sh",
    "solution/TRUTH.md",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "encoder path",
   "value": "/app/encode.py",
   "files": [
    "instruction.md",
    "task.toml",
    "solution/solve.sh",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "report decoded_examples.jsonl",
   "value": "decoded_examples.jsonl",
   "files": [
    "instruction.md",
    "task.toml",
    "environment/data/decoder_appendix.md",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "report format_report.json",
   "value": "format_report.json",
   "files": [
    "instruction.md",
    "task.toml",
    "environment/data/decoder_appendix.md",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "report roundtrip_report.json",
   "value": "roundtrip_report.json",
   "files": [
    "instruction.md",
    "task.toml",
    "environment/data/decoder_appendix.md",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "report error_analysis.json",
   "value": "error_analysis.json",
   "files": [
    "instruction.md",
    "task.toml",
    "environment/data/decoder_appendix.md",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "stream flag",
   "value": "--stream",
   "files": [
    "instruction.md",
    "environment/data/decoder_appendix.md",
    "solution/TRUTH.md",
    "tests/test_output.py",
    "tests/judge.toml"
   ],
   "retired": []
  },
  {
   "key": "salvage flag",
   "value": "--salvage",
   "files": [
    "instruction.md",
    "environment/data/decoder_appendix.md",
    "solution/TRUTH.md",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "run bit",
   "value": "stream_continues",
   "files": [
    "environment/data/format_contract.md",
    "environment/data/decoder_appendix.md",
    "solution/TRUTH.md",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "delta length key",
   "value": "delta_raw_len",
   "files": [
    "environment/data/decoder_appendix.md",
    "solution/TRUTH.md",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "error bad_magic",
   "value": "bad_magic",
   "files": [
    "environment/data/format_contract.md",
    "environment/data/decoder_appendix.md",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "error unsupported_version",
   "value": "unsupported_version",
   "files": [
    "environment/data/format_contract.md",
    "environment/data/decoder_appendix.md",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "error reserved_not_zero",
   "value": "reserved_not_zero",
   "files": [
    "environment/data/format_contract.md",
    "environment/data/decoder_appendix.md",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "error record_count_overflow",
   "value": "record_count_overflow",
   "files": [
    "environment/data/format_contract.md",
    "environment/data/decoder_appendix.md",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "reserved offset rule",
   "value": "first non zero reserved byte (14 or 15)",
   "files": [
    "environment/data/format_contract.md"
   ],
   "retired": []
  },
  {
   "key": "canonical id key",
   "value": "canonical_id",
   "files": [
    "environment/data/format_contract.md",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "test positive total",
   "value": "positive weight total of 107",
   "files": [
    "solution/TRUTH.md"
   ],
   "retired": [
    "positive weight total of 100"
   ]
  },
  {
   "key": "test positive count",
   "value": "27 positive checks",
   "files": [
    "solution/TRUTH.md"
   ],
   "retired": [
    "24 positive checks"
   ]
  },
  {
   "key": "judge positive count (TRUTH)",
   "value": "6 positive criteria",
   "files": [
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "judge weight in reward.toml",
   "value": "judge = 0.03125",
   "files": [
    "tests/reward.toml"
   ],
   "retired": [
    "judge = 0.019230769230769232",
    "judge = 0.021739130434782608",
    "judge = 0.020833333333333332"
   ]
  },
  {
   "key": "test weight in reward.toml",
   "value": "test_output = 0.004672897196261682",
   "files": [
    "tests/reward.toml"
   ],
   "retired": [
    "test_output = 0.005"
   ]
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
   "key": "check id reject_precedence",
   "value": "reject_precedence",
   "files": [
    "tests/test_output.py"
   ],
   "retired": [
    "reject_reserved_offset15"
   ]
  },
  {
   "key": "judge criterion R5",
   "value": "r5_code_quality",
   "files": [
    "tests/judge.toml"
   ],
   "retired": [
    "r5_decoder_structure"
   ]
  },
  {
   "key": "judge criterion R6",
   "value": "r6_catalog_roundtrip_check",
   "files": [
    "tests/judge.toml"
   ],
   "retired": [
    "r6_encoder_structure",
    "r6_unbacked_validation_claim",
    "r6_method_lines"
   ]
  },
  {
   "key": "judge criterion R7",
   "value": "r7_unbacked_validation_claim",
   "files": [
    "tests/judge.toml"
   ],
   "retired": [
    "r7_reads_grader_paths"
   ]
  },
  {
   "key": "fixture both_reserved",
   "value": "both_reserved",
   "files": [
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "judge positive total (TRUTH)",
   "value": "positive\ntotal of 16",
   "files": [
    "solution/TRUTH.md"
   ],
   "retired": [
    "positive\ntotal of 26",
    "positive\ntotal of 23",
    "positive\ntotal of 24"
   ]
  },
  {
   "key": "judge criterion R8",
   "value": "r8_reads_grader_paths",
   "files": [
    "tests/judge.toml"
   ],
   "retired": []
  },
  {
   "key": "manifest file",
   "value": "stream3_manifest.json",
   "files": [
    "environment/data/format_contract.md",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "catalog control key",
   "value": "value_sum",
   "files": [
    "environment/data/format_contract.md",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "count unit",
   "value": "count",
   "files": [
    "environment/data/format_contract.md",
    "environment/data/field_layouts.csv",
    "tests/test_output.py",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "override key",
   "value": "stream_continues",
   "files": [
    "environment/data/decoder_appendix.md",
    "environment/data/stream3_manifest.json",
    "tests/judge.toml",
    "tests/test_output.py",
    "solution/solve.py"
   ],
   "retired": []
  },
  {
   "key": "instruction grading sentence",
   "value": "Each output document is graded whole on fresh inputs.",
   "files": [
    "instruction.md"
   ],
   "retired": []
  },
  {
   "key": "judge criterion R1",
   "value": "r1_builds_count_unit_case",
   "files": [
    "tests/judge.toml"
   ],
   "retired": [
    "r1_gamma_last_value"
   ]
  },
  {
   "key": "judge criterion R2",
   "value": "r2_builds_alternating_fields_case",
   "files": [
    "tests/judge.toml"
   ],
   "retired": [
    "r2_beta_last_value"
   ]
  },
  {
   "key": "judge criterion R3",
   "value": "r3_builds_resend_case",
   "files": [
    "tests/judge.toml"
   ],
   "retired": [
    "r3_canonical_id_sum"
   ]
  },
  {
   "key": "judge criterion R4",
   "value": "r4_builds_override_type_case",
   "files": [
    "tests/judge.toml"
   ],
   "retired": [
    "r4_catalog_value_sum"
   ]
  },
  {
   "key": "Terms section",
   "value": "## Terms",
   "files": [
    "environment/data/format_contract.md"
   ],
   "retired": []
  },
  {
   "key": "Runs section",
   "value": "## Runs",
   "files": [
    "environment/data/decoder_appendix.md"
   ],
   "retired": []
  },
  {
   "key": "catalog id field",
   "value": "capture_id",
   "files": [
    "environment/data/format_contract.md",
    "tests/test_output.py",
    "environment/data/capture_catalog.jsonl"
   ],
   "retired": [
    "rej-"
   ]
  }
 ],
 "retired_entries": [
  {
   "key": "judge figure R1",
   "value": "-786"
  },
  {
   "key": "judge figure R2",
   "value": "-23254"
  },
  {
   "key": "judge figure R3",
   "value": "3869"
  },
  {
   "key": "judge figure R4",
   "value": "-247191366"
  },
  {
   "key": "instruction method clause",
   "value": "each with one line saying how you got it"
  }
 ]
}
```
