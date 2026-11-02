The Marrowgate district energy network settles metered interval events into a
published ledger. Six producing systems deliver revisions of those events in
batches, late and out of order, and a publication already went out for the
calendar they cover. That publication is now known to be wrong. Materialize the
calendar again from the delivered history and record the difference against what
was published rather than overwriting it.

Everything the run depends on sits in `/app/data`. The governing protocol, the
settlement calendar, the entity model, the closed vocabularies, the record
layouts, the deliverable contract and the glossary are all there, and so are the
configuration layers, the reference tables, the manifest and the batches
themselves. Which of those files govern which figure is part of the work, and so
is working out which batches belong to this materialization at all. Survey the
directory rather than reading it as a list handed to you. Where the protocol and
any other document disagree on membership, disposition, selection, arithmetic or
outcome, the protocol governs.

Several delivered rows can compete to define one event, so nothing about an
event is decided until that competition is. The instant an event is effective at
comes from the row that wins it, the site the event settles against is the one
that instant reaches through the merge history, and the zone, the tariff class,
the operational state and the interval ceiling are all read for that site at
that instant. The settlement day, the quantity, the tariff band, the partition
the event occupies and the zone cell it rolls into are each a consequence of
those, in that order.

Deliver a reusable program at `/app/out/materialize.py`. It accepts a `--data`
option naming a corpus directory and an `--out` option naming a destination
directory, it reads nothing outside the directory `--data` names, and it uses
only the Python standard library. Running it a second time over one corpus
produces byte identical output, and running it over a corpus held under a
different directory name produces the same figures. The same program is run
against corpora it has not seen, drawn from the same producing systems under the
same protocol, so every figure has to fall out of the rules rather than out of
the batches shipped here.

Run it against `/app/data` and `/app/out` and leave these behind:

```
/app/out/materialize.py
/app/out/canonical_ledger.jsonl
/app/out/revision_index.jsonl
/app/out/partition_20310308.csv
/app/out/partition_20310309.csv
/app/out/partition_20310310.csv
/app/out/partition_20310311.csv
/app/out/partition_20310312.csv
/app/out/partition_20310313.csv
/app/out/partition_20310314.csv
/app/out/partition_20310315.csv
/app/out/partition_manifest.json
/app/out/rejects.csv
/app/out/quarantine.jsonl
/app/out/dedup_ledger.csv
/app/out/deferred.jsonl
/app/out/unresolvable.json
/app/out/entity_resolution.json
/app/out/clamp_register.csv
/app/out/stack_register.csv
/app/out/restatement_adjustments.csv
/app/out/reconciliation.json
/app/out/validation_report.txt
/app/out/run_manifest.json
```

The deliverable contract in `/app/data` fixes the exact bytes of each one: the
columns and their order, the key sets, the orderings, the number formats, the
line endings and the trailing newline. Every value written into a field with a
closed vocabulary is drawn from that vocabulary and no other value appears
there. Nothing else may be written under `/app/out`, no artifact may carry a
timestamp or a host name or a path taken from the run, and every file under
`/app/data` is left exactly as it was found.

Three properties bind the set together and each of them is stated in the
protocol. The four dispositions a delivered row can receive account for every
body line read from an in scope batch and for no line twice. The settled
watt-hours the partitions carry equal the settled watt-hours the ledger carries,
and the partition manifest restates both. The watt-hours a prior publication
states for a zone cell, plus the adjustment this run records against that cell,
equal the watt-hours this run computes for it. Compute the residual of each of
the three and record what the check returned, because a run that computes
without checking has not finished.

Some conditions the rules do not decide. Report those under the code
the vocabulary defines for them rather than choosing a value for them, and
report a batch the manifest requires and the directory lacks in the same place.

Close by writing a short message that states thirteen figures, each one as an
exact integer or a named value rather than as a range or an approximation. None
of the thirteen appears in any of the files you leave behind, so each one has to
be worked out on its own.

Five of them the corpus states. How many rows in `site_merges.csv` carry an
instant that falls outside the settlement calendar. How many body lines the
batches held out of scope would have contributed had they been read. How many
events carry a settlement day that differs from the date portion of their
effective instant in UTC. How many rejected rows fail more than one of the
validation checks, and which reason code the precedence assigned to the largest
number of those rows, together with that count; for this figure evaluate each
check on its own against the row as delivered, and leave out a check whose input
an earlier field could not supply, so checks 4, 7 and 8 need a parsed instant and
check 8 also needs a registered site and a covering registration. How many rows
disposed as duplicates carry a `quantity` or a `revision_no` written with
different characters from the row they duplicate.

One is a question about the configuration layers: the value a last wins reading
of all three would have produced for `rounding.quantity_dp`.

The remaining seven ask what the run would have produced under the habitual
reading of a rule rather than the documented one. For each, state how many
events would carry a different watt-hour quantity in the ledger, counting an
event that appears in only one of the two runs as differing. Take them one at a
time, changing nothing else: the highest revision number alone deciding the
canonical revision; the settlement day taken from the date portion of the
effective instant; the adjustment family having its quantity field read and
converted as kilowatt hours, numeral grammar included; the interval ceiling
applied once after the restatement deltas rather than before and after them;
every merge applied regardless of its instant; the zone, tariff class,
operational state and interval ceiling read at the canonical revision's
`ingested_at` rather than at the effective instant; and the kilowatt hour to
watt-hour conversion rounded half up rather than half to even.

State the three residuals in that message as well.

This work needs nothing from the network. Retrieving a worked answer online is
out of bounds, and so is copying a prior submission.

You have 21600 seconds to complete this task.
