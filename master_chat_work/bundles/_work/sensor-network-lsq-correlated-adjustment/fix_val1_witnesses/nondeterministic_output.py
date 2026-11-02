from pathlib import Path
import os
import sys
ARTIFACT_NAMES = [
    "adjusted_state.json", "model_test.json", "downweighted_observations.json",
    "residual_summary.json", "unknowns.csv", "residuals.csv", "residuals.tsv",
    "final_weights.psv", "district_North.json", "district_South.json",
    "district_West.json", "district_East.json", "epoch_1.json", "epoch_2.json",
    "epoch_3.json", "adjustment_report.xml", "adjustment_summary.yaml",
    "adjustment_report.md", "observation_stream.jsonl", "observation_stream.ndjson",
    "normal_matrix_trace.json", "provenance_summary.json", "status.txt",
    "removed_blunders.json", "datum_transformation.json",
] + [f"rollup_Frame{f}_Campaign{c}.json" for f in "ABC" for c in (1, 2)]
value = os.environ.get('PYTHONHASHSEED', 'unset')
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
for name in ARTIFACT_NAMES:
    (out / name).write_text(value + '\n')
