# migrakit

Upgrades historical partner records to the canonical schema of their domain
through a graph of migration edges. Standard library only, Python 3.12.

Layout:

- `src/migrakit/parser/`: contract folder reader, feed reader, correction log
  reader, partner identity.
- `src/migrakit/core/`: field states (`records.py`), edge operations,
  planner, executor, replay fingerprint.
- `src/migrakit/report/`: record classification and the run summary.
- `src/migrakit/pipeline.py`: the end-to-end run.
- `src/migrakit/cli.py`: `python -m migrakit run ...`.

Field policy: an empty column of the field policy falls back to
`null_semantics.ini`, so an explicit null on a field whose `null_counts_as`
column is empty counts as `[presence] explicit_null` says, and a field whose
`fill` column is empty is filled as `[fill] mode` says (`core/records.py`).

Run the visible tests from the repository root:

    PYTHONPATH=src python -m unittest discover -s tests
