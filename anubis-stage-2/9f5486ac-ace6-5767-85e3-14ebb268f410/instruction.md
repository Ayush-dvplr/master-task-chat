Northbeam Payments' ML platform team needs training-set release TR-2026.09 of the Sentinel card-fraud model built from the exports under `/app/data`, together with a reusable builder that the platform will run again for the next release. Start with `/app/data/source_register.md`, which catalogs every delivered file and maps every column, and `/app/data/release_build_specification.docx`, which defines the build, the publication gate and the exact content of every output. The policies, standards, handbooks, registers and logs that the specification and the register point to are part of the same contract. Sources disagree in places; the governance charter and the topical policies decide which source governs, and some files that look authoritative are not.

Deliver the builder at `/app/out/transform.py`:

```bash
python3 /app/out/transform.py <DATA_DIR> <OUT_DIR> [--prior <PRIOR_OUT_DIR>]
```

Run it on `/app/data` to produce this release's outputs in `/app/out`:

- `/app/out/normalized.jsonl` - the released examples of every split
- `/app/out/product_summary.json` - the release state: fitted preprocessing, vocabularies, class weights, drift reference and account clusters
- `/app/out/summary.json` - split counts, baseline AUC, drift and imputation counts
- `/app/out/data_quality.json` - the release status, the per-file reconciliation and every excluded candidate record with its reason
- `/app/out/region_central.json`, `/app/out/region_east.json`, `/app/out/region_north.json`, `/app/out/region_south.json` and `/app/out/region_west.json` - evaluation slices by region group
- `/app/out/segment_consumer.json`, `/app/out/segment_corporate.json`, `/app/out/segment_enterprise.json` and `/app/out/segment_smb.json` - evaluation slices by segment group

Formats, key names, list order and rounding are defined by the specification and must be followed exactly; every value is compared exactly.

The platform will run your `/app/out/transform.py`, unchanged, on the next release's exports as a delta release, with `--prior` pointing at a copy of your `/app/out`, and compare its outputs with the expected ones. The builder must be deterministic, must read only the directories named on its command line, must not depend on where those directories are, and must finish one release within 25 minutes. It may use the Python standard library and the parsing libraries already installed in this environment.

Do not modify anything under `/app/data`. The environment has no network access; install nothing.

When you are done, tell us the release status and how many examples each split (train, val, test and oot) released.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
