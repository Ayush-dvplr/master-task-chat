# XREF metered-usage-rating-pipeline (wave 2 hardening, 09963d3)

Literal values that must agree across bundle files, and wording retired in this round.

```json
{
 "entries": [
  {
   "key": "slug",
   "value": "metered-usage-rating-pipeline",
   "files": [
    "task.toml",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "program path",
   "value": "/app/out/transform.py",
   "files": [
    "instruction.md",
    "task.toml",
    "tests/test_output.py",
    "tests/judge.toml",
    "solution/solve.sh",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "whole-document sentence",
   "value": "graded whole on fresh inputs, and only an exact match counts",
   "files": [
    "instruction.md"
   ],
   "retired": []
  },
  {
   "key": "accounts header",
   "value": "account_id,segment,plan,parent",
   "files": [
    "environment/data/rating_contract.md",
    "environment/data/accounts.csv",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "committed account term",
   "value": "committed account",
   "files": [
    "environment/data/rating_contract.md",
    "solution/solve.sh"
   ],
   "retired": [
    "on the committed plan",
    "less than half of its region"
   ]
  },
  {
   "key": "tier counter term",
   "value": "tier counter",
   "files": [
    "environment/data/rating_contract.md",
    "solution/solve.sh"
   ],
   "retired": []
  },
  {
   "key": "billing group term",
   "value": "billing group",
   "files": [
    "environment/data/rating_contract.md",
    "tests/test_output.py"
   ],
   "retired": [
    "whose `parent` is empty",
    "or the account itself when that column is empty"
   ]
  },
  {
   "key": "minimum term",
   "value": "minimum",
   "files": [
    "environment/data/rating_contract.md",
    "environment/data/commitments.xml",
    "tests/test_output.py",
    "solution/solve.py",
    "solution/solve.sh"
   ],
   "retired": []
  },
  {
   "key": "re-share floor",
   "value": "held 0.50 or more",
   "files": [
    "environment/data/rating_contract.md"
   ],
   "retired": [
    "by the same rule"
   ]
  },
  {
   "key": "true_up key",
   "value": "true_up",
   "files": [
    "environment/data/rating_contract.md",
    "tests/test_output.py",
    "solution/solve.py",
    "solution/solve.sh",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "north units rule",
   "value": "a JSON integer, written with no fraction or exponent",
   "files": [
    "environment/data/rating_contract.md"
   ],
   "retired": [
    "(a JSON integer)",
    "except north",
    "written as an integer"
   ]
  },
  {
   "key": "missing input message",
   "value": "missing input: ",
   "files": [
    "environment/data/rating_contract.md",
    "tests/test_output.py",
    "solution/solve.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "control mismatch message",
   "value": "control mismatch: ",
   "files": [
    "environment/data/rating_contract.md",
    "tests/test_output.py",
    "solution/solve.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "solve.sh tier line",
   "value": "check line tiers ok",
   "files": [
    "solution/solve.sh"
   ],
   "retired": [
    "check tier_counter ok",
    "check R1 ok"
   ]
  },
  {
   "key": "solve.sh credit line",
   "value": "check line credits and true_ups ok",
   "files": [
    "solution/solve.sh"
   ],
   "retired": [
    "check credit_true_up ok",
    "check credit_base ok"
   ]
  },
  {
   "key": "run limit",
   "value": "within 15 seconds",
   "files": [
    "environment/data/rating_contract.md",
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "solve.sh run time line",
   "value": "check run time ok",
   "files": [
    "solution/solve.sh"
   ],
   "retired": []
  },
  {
   "key": "hidden seed",
   "value": "58213",
   "files": [
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "ladder tier count",
   "value": "LADDER_TIERS = 50000",
   "files": [
    "tests/test_output.py"
   ],
   "retired": []
  },
  {
   "key": "solve.sh long rate card line",
   "value": "check long rate card ok",
   "files": [
    "solution/solve.sh"
   ],
   "retired": []
  },
  {
   "key": "solve.sh deep chain line",
   "value": "check deep parent chain ok",
   "files": [
    "solution/solve.sh"
   ],
   "retired": []
  },
  {
   "key": "solve.sh reordered records line",
   "value": "check reordered records ok",
   "files": [
    "solution/solve.sh"
   ],
   "retired": []
  },
  {
   "key": "check missing_input_first_named",
   "value": "missing_input_first_named",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  },
  {
   "key": "check missing_reference_file",
   "value": "missing_reference_file",
   "files": [
    "tests/test_output.py",
    "solution/TRUTH.md"
   ],
   "retired": []
  }
 ]
}
```
