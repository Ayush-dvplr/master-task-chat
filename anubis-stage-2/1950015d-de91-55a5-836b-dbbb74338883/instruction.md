The quarter four settlement drop for the LedgerPort distribution network has
landed in `/app/data` as one flat directory of a hundred files. Finance needs
the quarter normalized and rolled up, and the drop is the only thing you get:
no upstream system is reachable and nothing in it is a clean export.

The written contract for the work is `/app/data/settlement_contract.md`. It
defines the canonical identifier form, the reference registries and how their
shards fit together, how to read each transaction feed, the ordered chain that
turns one raw row into one settlement record, the rejection code of every step,
how duplicates and reversals are resolved, and the exact field set of every
deliverable. Read it before you write any code. It names further files that
carry the pieces it does not restate, and those files name others. Which file
feeds which figure is part of the work, so treat the directory as something to
survey rather than a list handed to you. Several files look like the primary
input and are not, and several that look like noise hold a fact nothing else
carries. The drop also publishes its own declared counts and windows, so a
wrong reading of it can be caught before you ship.

Deliver a reusable program as one self-contained file at
`/app/out/transform.py`. It runs as a script
taking an input directory and an output directory, and it writes every
deliverable below under the output directory, so the same code gives correct
results for a drop it has never seen:

```bash
python3 /app/out/transform.py <DATA_DIR> <OUT_DIR>
```

It must work offline from the packages already installed in this image, must
read nothing outside the input directory it is given, must write nothing
outside the output directory it is given, and must produce byte-identical
output on repeated runs over the same input. Nothing in its logic may turn on
the particular identifiers, totals, file sizes or register values present in
this drop. A run has to finish within 1200 seconds on a drop the size of this
one, and within 300 seconds on a drop with a twenty-fifth of its rows. Do not
install anything while you work; use only what this image already has.

Run it once over `/app/data` into `/app/out`. The normalized ledger goes to
`/app/out/normalized.jsonl`, the quarter roll-up to `/app/out/summary.json`,
the data health report to `/app/out/data_quality.json` and the per-item
roll-up to `/app/out/product_summary.json`. Write one file per canonical
region at `/app/out/region_central.json`, `/app/out/region_east.json`,
`/app/out/region_north.json`, `/app/out/region_south.json` and
`/app/out/region_west.json`, and one per customer segment at
`/app/out/segment_consumer.json`, `/app/out/segment_corporate.json`,
`/app/out/segment_enterprise.json` and `/app/out/segment_smb.json`. Keep any
scratch files you make while exploring out of `/app/out`.

Every field name, value convention, ordering rule and rounding rule inside
those files is fixed by the contract and by the policy registers it points at.
Each one is compared field for field and type for type, so an integer field
carries an integer, a money field is a whole number of USD cents, and every
row of every output is checked rather than a sample. Write them
deterministically, with no timestamps, no durations and no run identifiers.

When you finish, report the accepted and rejected row counts your run
produced, name the policy registers your pipeline took its rules from, and say
which parts of the drop, if any, you could not interpret.

You have 14400 seconds to complete this task. Do not cheat by using online
solutions or hints specific to this task.
