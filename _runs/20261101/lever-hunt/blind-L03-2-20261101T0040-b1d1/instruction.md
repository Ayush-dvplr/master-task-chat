The food safety authority needs its quarterly cold-storage contaminant panel
produced from laboratory transmission extracts.

Write `/app/derive_report.py`, run as

    python3 /app/derive_report.py <corpus_dir> <out_dir>

It reads one extract from `<corpus_dir>` and writes the panel files into
`<out_dir>`. Everything you need is in `/app/data/`:

- `panel_contract.md`: the declared depots, quarters and assays, validation,
  aggregation and the output files.
- `source_rules.md`: which lab result wins when several report the same sample.
- `output_schema.json`: exact keys and types of every output file.
- `corpus/`: one extract, laid out as every extract is.

Your program will also be run on other extracts governed by the same contract.
Use the Python 3 standard library only.
