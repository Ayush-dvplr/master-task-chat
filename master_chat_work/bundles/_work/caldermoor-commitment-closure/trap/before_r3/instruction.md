A shared assistant held one household's commitments for nine months across
eight local feeds that disagree with each other, and the closure it once
published was never reproduced. What is left of it is in `/app/data`. The
governing protocol is `/app/data/commitment-protocol.md`, and it names the
identity register, the precedence charter, the dependency semantics, the
cadence register, the record layouts, the output contract and the glossary that
carry the rest. Survey the extract rather than reading it as a list handed to
you, because working out which feeds govern which figure is part of the work.

Deliver a reusable program at `/app/out/reconcile.py` that reads one extract
directory and writes the whole closure into another.

```bash
python3 /app/out/reconcile.py DATA_DIR OUT_DIR
```

Run it over `/app/data` so that `/app/out` holds the closure for the shipped
extract. The same program is run again over further extracts drawn to these
layouts that you have not seen, which carry the data files alone and none of
the eight documents, so every figure has to come from the rules, not from the
numbers in the shipped files. Build it from the Python
standard library alone, and make a second run over one extract produce output
identical to the first byte for byte, carrying no clock reading, no host name
and no path from the machine it ran on. Every deliverable is held to its exact
bytes on each of those unseen extracts as well as on the shipped one.

These twenty-nine are the deliverables. The output contract states what each
one holds, states the order of its rows, and states that the directory the
program is handed carries these twenty-nine and nothing else once the run
finishes, whichever directory that is:

```
/app/out/reconcile.py
/app/out/normalized_assertions.jsonl
/app/out/rejects.csv
/app/out/alias_resolution.jsonl
/app/out/actor_roster.csv
/app/out/project_lineage.csv
/app/out/assertion_contests.csv
/app/out/commitment_ledger.jsonl
/app/out/state_resolution.csv
/app/out/live_edges.csv
/app/out/dropped_edges.csv
/app/out/blocking_closure.jsonl
/app/out/blocked_commitments.csv
/app/out/actionable_queue.tsv
/app/out/deferred_queue.psv
/app/out/withdrawn_register.csv
/app/out/unresolvable.jsonl
/app/out/cadence_debt.csv
/app/out/waiver_trace.jsonl
/app/out/attention_allocation.csv
/app/out/month_load_index.csv
/app/out/escalation_queue.csv
/app/out/actor_rollup.json
/app/out/project_rollup.json
/app/out/provenance_index.jsonl
/app/out/audit_totals.csv
/app/out/reconciliation.txt
/app/out/validation_report.json
/app/out/run_manifest.json
```

The protocol and the documents it names fix the window, the boundary that
decides a commitment day, the fold that decides when two references are one,
the intervals inside which an alias holds, the instant at which each reference
is resolved and which reference takes which instant, the rank order that
decides which assertion governs and which classes read that order backwards,
the closed vocabularies every field is drawn from, the canonical order of every
row, and the exact bytes of every file listed above. Where a rule and a habit
disagree, the rule stands, and no reading outside those documents governs
anything.

Each of the five identities the protocol states is checked by the run and
carries its residual into the validation report. A condition the rules leave
undecided is reported under the reason code the protocol gives it rather than
answered.

Nothing in the extract is edited, moved, added to or removed. Every file under
`/app/data` is left exactly as it was found, and a run that cannot finish
leaves no partial file behind. Build the closure in a staging directory and
publish it into the requested output directory only after every deliverable is
complete.

Every rule that decides the closure is inside the extract, and these feeds
were made for this one household's settlement, so nothing outside `/app/data`
settles any part of it.

You have 28800 seconds to complete this task.
