# XREF sensor-network-lsq-correlated-adjustment (harden r1, redesign r2 4d6dfe8)

```json
{
 "entries": [
  {
   "key": "program path",
   "value": "/app/out/derive_report.py",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "contract file",
   "value": "schema.md",
   "files": [
    "instruction.md",
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "provenance artifact",
   "value": "provenance_summary.json",
   "files": [
    "instruction.md",
    "task.toml",
    "environment/data/schema.md",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "superseded field",
   "value": "superseded_records",
   "files": [
    "environment/data/schema.md",
    "solution/solve.py",
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "centring column",
   "value": "centring_mm",
   "files": [
    "environment/data/schema.md",
    "environment/data/station_registry.csv",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": [
    "apriori_sigma_base",
    "boundary_crosser"
   ]
  },
  {
   "key": "revision token",
   "value": "revision=",
   "files": [
    "environment/data/obs_source_district_north.csv",
    "environment/data/obs_source_district_south.tsv",
    "environment/data/obs_source_district_west.psv",
    "tests/test_output.py"
   ],
   "retired": [
    "decoy_tuning_k"
   ]
  },
  {
   "key": "shipped vTPv",
   "value": "999.9232011672",
   "files": [
    "tests/judge.toml",
    "solution/TRUTH.md"
   ],
   "retired": [
    "1016.9199434352"
   ]
  },
  {
   "key": "shipped variance of unit weight",
   "value": "0.9812789020",
   "files": [
    "tests/judge.toml",
    "solution/TRUTH.md"
   ],
   "retired": [
    "0.9979587276"
   ]
  },
  {
   "key": "shipped signed residual sum",
   "value": "-444581",
   "files": [
    "tests/judge.toml",
    "solution/TRUTH.md"
   ],
   "retired": [
    "-413109"
   ]
  },
  {
   "key": "shipped trace",
   "value": "14059330.440663",
   "files": [
    "tests/judge.toml",
    "solution/TRUTH.md"
   ],
   "retired": [
    "14548610.757228"
   ]
  },
  {
   "key": "judge mode",
   "value": "mode = \"batched\"",
   "files": [
    "tests/judge.toml"
   ],
   "retired": [
    "mode = \"individual\""
   ]
  },
  {
   "key": "tests weight",
   "value": "0.005813953488372093",
   "files": [
    "tests/reward.toml"
   ],
   "retired": [
    "0.0078125",
    "0.008064516129032258"
   ]
  },
  {
   "key": "judge weight",
   "value": "0.01282051282051282",
   "files": [
    "tests/reward.toml"
   ],
   "retired": [
    "0.020833333333333332",
    "0.009615384615384616",
    "0.03333333333333333"
   ]
  },
  {
   "key": "litellm pin",
   "value": "harbor-rewardkit==0.2.1 litellm==1.105.0",
   "files": [
    "tests/Dockerfile"
   ],
   "retired": []
  },
  {
   "key": "author",
   "value": "Ayush Sah",
   "files": [
    "task.toml"
   ],
   "retired": []
  },
  {
   "key": "R5 name",
   "value": "r5_derive_report_py_maintainable",
   "files": [
    "tests/judge.toml"
   ],
   "retired": [
    "r5_writes_derive_report_py_maintainable",
    "r5_derive_report_py_uses_named_stage_functions"
   ]
  },
  {
   "key": "closure register",
   "value": "traverse_closure_register.csv",
   "files": [
    "environment/data/schema.md",
    "solution/solve.py",
    "solution/solve.sh",
    "tests/test_output.py",
    "tests/judge.toml"
   ],
   "retired": [
    "scale_closure_register.csv"
   ]
  },
  {
   "key": "mark register",
   "value": "control_mark_register.csv",
   "files": [
    "environment/data/schema.md",
    "environment/data/station_registry.csv",
    "solution/solve.py",
    "solution/solve.sh",
    "tests/test_output.py",
    "tests/judge.toml"
   ],
   "retired": []
  },
  {
   "key": "set-out column",
   "value": "set_out_from",
   "files": [
    "environment/data/schema.md",
    "environment/data/station_registry.csv",
    "environment/data/control_mark_register.csv",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "floor column",
   "value": "floor_micrometres",
   "files": [
    "environment/data/schema.md",
    "environment/data/traverse_closure_register.csv",
    "solution/solve.py",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "R9 name",
   "value": "r9_recomputes_traverse_closure_absorption",
   "files": [
    "tests/judge.toml"
   ],
   "retired": []
  },
  {
   "key": "R10 name",
   "value": "r10_recomputes_station_centring_variance",
   "files": [
    "tests/judge.toml"
   ],
   "retired": []
  },
  {
   "key": "R11 name",
   "value": "r11_recomputes_district_observation_count",
   "files": [
    "tests/judge.toml"
   ],
   "retired": []
  },
  {
   "key": "RFC 4180 sentence (R0 868afdf)",
   "value": "The CSV shard is written to RFC 4180, so any of its fields may be",
   "files": [
    "environment/data/schema.md",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "G1/G5 exact bar",
   "value": "Each output document is graded whole, and only an exact match counts.",
   "files": [
    "instruction.md"
   ],
   "retired": []
  }
 ]
}
```
