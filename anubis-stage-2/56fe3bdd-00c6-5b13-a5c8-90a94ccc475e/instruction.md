The perception evaluation board needs the official Q3 2026 release review of the SKYE sidewalk-robot object detector: which frozen images are evaluated, what their ground truth is, what each candidate model detected on them, how each model scores, and whether a challenger replaces the incumbent. Everything the review uses was delivered to `/app/data`: one hundred files from the camera fleet, three labelling vendors, the inference cluster, the training team and the review board. The governing contract is `/app/data/eval_standard_v3.md` (PES-3). It defines every artifact and its exact layout, and it names the document that decides each question. The deliveries contradict each other in places, and some of them look more authoritative than they are; PES-3 and the documents it names say which source wins.

Build the review engine as one self-contained file at `/app/out/evalctl.py`. Running

```bash
python3 /app/out/evalctl.py ESTATE_DIR OUT_DIR
```

must read only `ESTATE_DIR`, which is laid out like `/app/data` (same file names, different contents), and write these eight files into `OUT_DIR`: `eval_images.csv`, `exclusions.csv`, `ground_truth.csv`, `detections.csv`, `class_metrics.csv`, `operating_points.csv`, `leaderboard.json` and `reconciliation.json`.

The engine must meet all of these:

- It uses only the Python 3.12 standard library and the packages already installed in the image (pyarrow, openpyxl, python-docx, pypdf, pdfplumber, lxml, PyYAML, icalendar, tomli), and it needs no network. Only these nine packages count; packages that are present only because one of them depends on them (such as pdfminer.six or python-dateutil) are not allowed.
- Two runs on the same estate produce byte-identical files, and the output does not depend on the names or locations of `ESTATE_DIR` and `OUT_DIR`.
- It finishes an estate as large as `/app/data` within 1800 seconds on 2 CPUs. A smaller estate gets the same time per record: 1800 seconds scaled by its share of the delivered records (as PES-3 section 15 counts them) in `/app/data`, plus a quarter for margin.
- It will be run on other estates of the same layout, so every value it writes has to be derived from the estate it is given.

Then run the engine on `/app/data` with `/app/out` as the output directory, so that the review artifacts of this cycle are in place at:

- `/app/out/eval_images.csv`
- `/app/out/exclusions.csv`
- `/app/out/ground_truth.csv`
- `/app/out/detections.csv`
- `/app/out/class_metrics.csv`
- `/app/out/operating_points.csv`
- `/app/out/leaderboard.json`
- `/app/out/reconciliation.json`

Every artifact is graded exactly as PES-3 specifies it: every row, key, value, type, ordering rule and rounding step. A value that is almost right is wrong, and a row that is right on all but one field is wrong.

Do not modify anything under `/app/data`.

When you finish, reply with a short summary that names the release candidate and the decision for each challenger run, lists the deliveries you treated as not authoritative with the rule that demoted each one, and says which checks you ran to confirm the artifacts.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
