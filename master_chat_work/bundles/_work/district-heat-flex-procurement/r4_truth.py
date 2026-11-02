"""Assemble BUNDLE/solution/TRUTH.md from TRUTH_r4_body.md + provenance with sha256 lines (run as last edit)."""
import hashlib
from pathlib import Path
W = Path(__file__).resolve().parent
S = W.parent.parent / "district-heat-flex-procurement" / "solution"
def sha(name): return hashlib.sha256((S / name).read_bytes()).hexdigest()
prov = f"""## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: district-heat-flex-procurement
task_name: terminal-bench/district-heat-flex-procurement
fix_patch_sha256: {sha('solve.sh')}  # sha256 of solution/solve.sh
solve_py_sha256: {sha('solve.py')}  # sha256 of solution/solve.py
language: python
golden_score_measured: null  # no Harbor run recorded in this file
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null
golden_score_verified_by: >
  Not measured here. Oracle and nop figures come from runs on the
  tests-only copy and cover the test channel only; the judged channel has
  no oracle score.
```
"""
(S / "TRUTH.md").write_text((W / "TRUTH_r4_body.md").read_text() + prov, encoding="utf-8")
print("TRUTH.md written")
