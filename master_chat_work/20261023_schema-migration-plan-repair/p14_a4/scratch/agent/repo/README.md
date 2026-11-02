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

Field policy: a field whose `null_counts_as` column is empty in the field
policy falls back to `[presence] explicit_null` of `null_semantics.ini`, and a
field whose `fill` column is empty falls back to `[fill] mode` (N2, N3).

Planning searches over (schema, field states), so a graph with far too many
distinct paths to list is still planned in one pass.

Run the visible tests from the repository root:

    PYTHONPATH=src python -m unittest discover -s tests
