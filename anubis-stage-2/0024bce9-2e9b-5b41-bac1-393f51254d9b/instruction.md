The reliability team retrains the kestrel model, which predicts pump failures from condition monitoring data. The last training data rebuild, run KP-23, computed wrong numbers, so the model cannot be retrained until the training data is rebuilt correctly as run KP-24. Nobody wrote down why KP-23 went wrong; the model team only noticed that its labels, its scaler statistics and its baseline scores did not hold up when they spot checked a handful of pumps against the plant records. Your job is to rebuild the data correctly and to leave behind a program the team can run again on the next estate.

Everything you have is in `/app/data` and `/app/docs`: condition telemetry exports from gateways and historians, asset, sensor and calibration records, controller alarms, work orders, failure notifications and their reviews, site rosters, weather observations, a run sheet, an errata register, two export profile registers and the governing standard `/app/data/fps4_rules.md`. The exact shape of every output is fixed by `/app/docs/output_contract.md`, and that contract is part of this brief.

The sources overlap and conflict, and some of them hold values that are wrong or superseded on purpose. Do not trust a file because it looks newer, cleaner or more complete, and do not reuse anything KP-23 produced beyond the one narrow use the standard allows. The standard, read together with the export profile registry and the errata register, decides every value; when a source and the standard disagree, the standard wins. Outputs are compared exactly: keys, columns, value types, decimal places, row order and empty values all count, so a figure that is close is still wrong. Where the contract asks for a fixed number of decimal places, write exactly that many.

## What to deliver

Write one program, `/app/out/build.py`, with three stages:

```
python3 /app/out/build.py phase1 DATA_DIR P1_DIR
python3 /app/out/build.py phase2 P1_DIR P2_DIR
python3 /app/out/build.py phase3 P1_DIR P2_DIR P3_DIR
```

Run it so that these 18 files exist:

- Phase 1, built from the input directory: `/app/out/p1/asset_registry.csv` (one row per asset), `/app/out/p1/sensor_daily.csv` (one row per asset day), `/app/out/p1/failure_events.csv` (one row per failure notification), `/app/out/p1/maintenance_log.csv` (services and oil samples), `/app/out/p1/site_days.csv` (one row per site day) and `/app/out/p1/run_parameters.json` (run settings and source attestation).
- Phase 2, built from the six phase 1 files and nothing else: `/app/out/p2/label_table.json`, `/app/out/p2/feature_matrix.json`, `/app/out/p2/scaler_stats.json`, `/app/out/p2/class_balance.json`, `/app/out/p2/quarantine_summary.json` and `/app/out/p2/bin_edges.json`.
- Phase 3, built from the six phase 1 and the six phase 2 files and nothing else: `/app/out/p3/train_ready.json`, `/app/out/p3/baseline_metrics.json`, `/app/out/p3/drift_report.json`, `/app/out/p3/site_allocation.json`, `/app/out/p3/amendment_impact.json` and `/app/out/p3/release_manifest.json`.

Fields, types, decimal places, ordering, encoding, line endings, the final newline and the empty value form of every file are in the output contract; follow it to the letter. The meaning of every field is in the standard.

Who uses what: the data scientists load `train_ready.json` straight into training and use `feature_matrix.json`, `scaler_stats.json`, `class_balance.json` and `bin_edges.json` to reproduce it; the release board reads `baseline_metrics.json`, `drift_report.json` and `site_allocation.json` before it signs off the retrain and assigns label reviews to the sites; the reliability engineers read `amendment_impact.json` to see how the decisions still pending after the freeze would move the labels; and the audit team compares `run_parameters.json` and `release_manifest.json` with the sources and with the files each phase handed on. The phase 1 tables are also used on their own by the site teams, so they must be right in their own terms and not only good enough for the later phases.

What each file is for:

- `asset_registry.csv`: the pump fleet as it stands at the freeze, which later phases use for holdout, commissioning and criticality.
- `sensor_daily.csv`: the calibrated daily condition values of each pump with its availability, alarm count and reading counts; every feature is built from it.
- `failure_events.csv`: the failure notifications with their review outcome, which decide the labels, and the decisions that were still pending at the freeze.
- `maintenance_log.csv`: the services and oil samples that feed the service and oil features and the maintenance exclusions.
- `site_days.csv`: whether each site was operating and how warm it was, which later phases need for exclusions and temperature rise.
- `run_parameters.json`: the effective run settings and one attestation row per source file, so the audit team can see what was read.
- `label_table.json` and `feature_matrix.json`: the samples that go into the retrain with their split, label and raw features.
- `scaler_stats.json`, `class_balance.json` and `bin_edges.json`: the statistics fitted on the training split.
- `quarantine_summary.json`: per site, how many readings were quarantined and why candidate samples were left out.
- `train_ready.json`: the standardised, weighted rows the training job reads.
- `baseline_metrics.json` and `drift_report.json`: how the fixed baseline score ranks failures and how far the test split drifts from training.
- `site_allocation.json`: how the label review budget is shared across sites under the caps.
- `amendment_impact.json`: the label changes the pending decisions would cause.
- `release_manifest.json`: the digests and row counts that tie the release to the files it came from.

You are done when all 18 files exist, each was written by the program from the directories named above, each stage also runs on its own into a fresh output directory, a second run gives the same bytes, and your final message lists what you wrote.

## Stage boundaries

Keep the work of each stage in that stage: phase 1 decodes and reconciles the sources into clean tables, phase 2 builds the samples, features and fitted statistics, and phase 3 builds the training rows and the reports. Each stage reads only the directories it is given and writes only into its own output directory, which it creates when it is missing. Phase 2 must work from any phase 1 directory and phase 3 from any phase 1 and phase 2 directories, including directories another run produced, so everything a later phase needs has to be carried by the earlier phase's files. No stage may look at directory names, at `/app/data` when it was not given it, or at any fixed location. Running a stage again on the same input must give the same bytes and must not break anything it wrote before.

The team will keep using the program after this run, which is why the three stages stay separate: when a new estate arrives they run phase 1 on it, check the phase 1 tables with the site teams, and only then run phases 2 and 3. A stage that quietly reaches back past its own inputs, or that only works on the files you can see today, is of no use to them.

The program is also run on unseen estates laid out like `/app/data`. They follow the same standard and the same output contract but carry other identifiers, values and export profiles, and every stage must be exact there as well. Wrong arguments and unreadable directories end with the exit codes and the one-line `error:` message the output contract describes.

## Environment

The machine has Python 3.12 with its standard library and PyYAML, and no network access. `/app/out` is yours to write; `/app/data` and `/app/docs` are read only in spirit even where the file system would let you write. The program may later be run by a different, unprivileged user, from a different working directory, with input and output directories in other places; it needs only read access to the directories it reads and write access to the directory it writes, and it must not rely on anything else you left lying around. A full phase 1 run on `/app/data` should finish well inside a few minutes on this machine; phases 2 and 3 are quicker. Large outputs are expected: the feature matrix and the training rows hold one row per kept sample.

## Requirements

Phase 1:

1. The phase 1 CSV files carry the contract headers, LF line endings and row order, and `run_parameters.json` uses the contract JSON layout.
2. `asset_registry.csv` gives each asset its site, model, OEM and serial as they stand at the freeze.
3. `asset_registry.csv` gives each asset its commissioned date, its decommission instant and its holdout flag.
4. `asset_registry.csv` gives each asset its criticality, setpoint and rated flow as they stand at the freeze.
5. `sensor_daily.csv` holds exactly the asset days the standard defines, each with its site.
6. Every asset day carries its availability.
7. Every asset day carries its daily vibration mean and maximum.
8. Every asset day carries its daily temperature.
9. Every asset day carries its daily pressure.
10. Every asset day carries its daily flow.
11. Every asset day carries its daily motor current.
12. Every asset day carries the setpoint and rated flow in force that day.
13. Every asset day carries its count of counted alarms.
14. Every asset day carries its usable and quarantined reading counts.
15. `failure_events.csv` lists exactly the failure notifications, each with its instant, failure day and status.
16. Every failure event carries its mode and its deciding instant.
17. Every failure event carries its pending decision, pending mode and pending instant columns.
18. `maintenance_log.csv` holds exactly the service rows.
19. `maintenance_log.csv` holds exactly the oil sample rows.
20. `site_days.csv` gives every site day its operating shift count and its operating flag.
21. `site_days.csv` gives every site day its ambient temperature.
22. `run_parameters.json` carries the run id, freeze, telemetry window, effective run parameters, holdout assets and site regions.
23. In `run_parameters.json` every in-scope source carries its role and its attestation digest.
24. Every reference copy carries its role and its attestation digest.
25. Every source carries its data record count.
26. On an unseen estate, phase 1 writes the exact asset registry, site days, failure events and maintenance log.
27. On an unseen estate, phase 1 writes the exact `sensor_daily.csv`.
28. On an unseen estate, phase 1 writes the exact `run_parameters.json`.
29. An unknown stage or a wrong number of directories makes the program exit with status 2, print one line starting with `error:` to standard error and write nothing.

Phase 2, for any phase 1 directory it is given:

30. It keeps exactly the samples the standard defines.
31. It labels every kept sample.
32. It gives every kept sample its split.
33. It writes the sensor window features of every kept sample.
34. It writes the service, age, oil and alarm features of every kept sample.
35. It writes the scaler statistics.
36. It writes the split counts and the class weights.
37. It writes the decile bin edges.
38. It writes the per-site quarantine and exclusion counts.
39. Every phase 2 file carries the upstream controls of the phase 1 directory it read.
40. Every phase 2 file carries the upstream digest of the phase 1 directory it read.
41. On an unseen phase 1 directory it writes the exact label table and feature matrix.
42. On an unseen phase 1 directory it writes the exact statistics files.
43. A missing or unreadable upstream directory makes it exit with status 3, print one line starting with `error:` and write nothing.
44. The delivered phase 2 files are exactly what the program writes from the delivered phase 1 files.

Phase 3, for any phase 1 and phase 2 directories it is given:

45. It writes the standardised feature values of every training, validation and test row.
46. It writes the sample weight of every row.
47. It writes the validation and test AUC of the baseline score with their row and positive counts.
48. It picks the validation threshold and reports its F1.
49. It writes the test confusion counts, precision, recall and F1 at that threshold.
50. It writes the drift report.
51. It writes the review budget allocation.
52. It lists exactly the label changes that the pending amendments cause.
53. It writes the count of events with a pending amendment and the label flips per split.
54. It writes the release manifest.
55. Every phase 3 file carries the upstream controls of the twelve files it read.
56. Every phase 3 file carries the upstream digest of the twelve files it read.
57. On unseen upstream directories it writes the exact training rows.
58. On unseen upstream directories it writes the exact report files.
59. The delivered phase 3 files are exactly what the program writes from the delivered phase 1 and phase 2 files.
60. Every phase 2 and phase 3 file uses the contract JSON layout.

Rules for the program:

61. Every result comes from the directories given: nothing in the program depends on the identifiers or values of `/app/data`.
62. Its output does not depend on the name or location of the directories it is given.
63. Phase 1 reads only DATA_DIR, uses only the Python standard library and the packages already installed here (PyYAML is available), and works offline.
64. Two runs on the same input give byte-identical files.
65. Phase 2 and phase 3 never read the input estate, only the upstream directories they are given.
66. Phase 2 and phase 3 results follow from the upstream directories given; they never read a fixed location such as `/app/out`.
67. The upstream digest a phase 2 or phase 3 file states is the digest of the upstream files that phase actually read.
68. The program never changes anything inside a directory it reads.

How to work:

69. Read `/app/data/fps4_rules.md` before you write `/app/out/build.py`.
70. Read `/app/docs/output_contract.md` before you write any phase 1 file.
71. Run `build.py phase1` on `/app/data` yourself and look at what it wrote before you finish.
72. Produce `/app/out/p2` by running phase 2 on `/app/out/p1`, and `/app/out/p3` by running phase 3 on `/app/out/p1` and `/app/out/p2`.
73. Before you rely on decoded figures, check the record count and control sum of each segment you decode against the control that segment publishes.
74. Keep the program readable: segment decoding, phase 1, phase 2 and phase 3 each sit in their own named functions.
75. End with a short message that lists the files you wrote under `/app/out` and any requirement you could not meet.
76. Stay inside the task: work only with `/app/data`, `/app/docs` and `/app/out`.
77. Do not claim a check passed unless you ran it and it passed.
78. Leave `/app/data` and `/app/docs` unchanged.
79. Do not install packages or reach the network.
80. Do not copy labels, splits or counts from the KP-23 export into your outputs.
81. Handle errors on purpose: no bare `except` and no `except` block that only passes.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
