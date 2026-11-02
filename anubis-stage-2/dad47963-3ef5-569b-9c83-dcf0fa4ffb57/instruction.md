Model Monitoring hands over the 2026-Q2 performance review of the PD-RETAIL v4 retail scorecard. The full data estate of the cycle, 100 deliveries from servicing, scoring, treasury, governance and HR systems, is in `/app/data`. The binding contract is `/app/data/monitoring_spec_v4.md`: it defines every deliverable, its exact layout, and the policies and registers that decide each value. Expect the deliveries to disagree with each other; the specification and the policies it names say which source wins.

Deliver a monitoring engine at `/app/out/monitor.py`. Running

```bash
python3 /app/out/monitor.py ESTATE_DIR OUT_DIR
```

must read only `ESTATE_DIR`, which is laid out like `/app/data` (same delivery names, different contents), and write the nine artifacts below into `OUT_DIR`. The engine may use the Python standard library and the parsers already installed in the image. Its output must be byte-identical across runs and must not depend on where `ESTATE_DIR` lives. It will be run on other estates of the same layout, including one as large as `/app/data`, and must finish such an estate within 900 seconds on 2 CPUs.

Also run it on `/app/data` so that the artifacts of this cycle are in place at:

- `/app/out/cohort.csv`
- `/app/out/exclusions.csv`
- `/app/out/score_selection.csv`
- `/app/out/performance_windows.csv`
- `/app/out/population_summary.json`
- `/app/out/discrimination.json`
- `/app/out/psi.json`
- `/app/out/calibration.csv`
- `/app/out/reconciliation.json`

Every artifact is graded exactly: every row, key, value, type, ordering rule and rounding step as the specification states it. A value that is almost right is wrong, and a row that is right on most fields is wrong.

Do not modify anything under `/app/data`.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
