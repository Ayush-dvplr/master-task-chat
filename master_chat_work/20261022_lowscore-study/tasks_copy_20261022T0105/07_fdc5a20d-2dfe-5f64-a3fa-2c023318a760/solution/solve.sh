#!/bin/bash
set -euo pipefail

cp /solution/solve.py /app/derive_report.py
python3 /app/derive_report.py /app/data/records.csv /app/data/model.json /app/data/feature_spec.json /app/data/scoring_policy.json /app/report.json
