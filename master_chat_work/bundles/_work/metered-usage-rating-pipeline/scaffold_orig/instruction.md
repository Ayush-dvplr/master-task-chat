The flat files under `/app/data` are exports from a small commerce data pipeline that a  left behind, and your job is to build a deterministic pipeline that normalizes every transaction and rolls the results up by region and by customer segment. The written contract for the task lives at `/app/data/schema.md`; it describes the input files, their column layouts, the parsing and currency rules, the canonical normalized record, and the shape of every aggregate you must emit. Part of the work is reading that contract and the data together and deciding which files feed which figure, so treat the directory as something to explore rather than a list handed to you.

Deliver a reusable transform program at `/app/out/transform.py`. It must run as a script that takes an input directory and an output directory and writes all of the JSON artifacts under the output directory, so that the same code produces correct results for input directories it has never seen. The verifier runs it against freshly generated data drawn from the same schema, so nothing about your logic may depend on the particular identifiers or values present in the shipped sample.

```bash
python3 /app/out/transform.py <DATA_DIR> <OUT_DIR>
```

When invoked without arguments it should fall back to reading `/app/data` and writing `/app/out`. Start the file with the line `#!/usr/bin/env python3` and leave it executable, so it can also be run directly. Use only the Python standard library, and be aware that anything you pip install here will not be present at grading time. Every JSON artifact is written with sorted keys, and all money is expressed in integer USD cents as the contract describes.

The normalized transaction stream goes to `/app/out/normalized.jsonl`, one JSON object per accepted transaction, ordered as the contract specifies. The overall roll-up goes to `/app/out/summary.json`, the data-health report goes to `/app/out/data_quality.json`, and the per-product roll-up goes to `/app/out/product_summary.json`. Emit one file per canonical region at `/app/out/region_central.json`, `/app/out/region_east.json`, `/app/out/region_north.json`, `/app/out/region_south.json`, and `/app/out/region_west.json`, and one file per customer segment at `/app/out/segment_consumer.json`, `/app/out/segment_corporate.json`, `/app/out/segment_enterprise.json`, and `/app/out/segment_smb.json`. The exact keys inside each of these files are defined by the contract.

You have 7200 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
