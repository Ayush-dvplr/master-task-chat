A federated catalogue search broker ran a small program called the probe accounting engine. Every run it read the whole stream of metered partition lookups, resolved each lookup into a probe line, and then rolled the run up per partition and for the catalogue as a whole. When the broker controller was retired the engine went with it, and so did the per-lookup probe ledger for the last recorded run. What survives is that run's input and the two rollups the engine wrote for it, and all of it is in `/app/data`.

The written notes in `/app/data/broker.md` and `/app/data/reports.md` describe the shape of the engine and the shape of its three reports. They give the input columns, the ten pieces of carried index state, the fourteen stages in order, the status ladder, the key set of every report and the byte form each report is written in. What they do not give is any of the numbers. The gain and the governing count rule, the four keyed adjustment tables (the form of every entry as well as its figures, and how they round below zero), the credit release and its ceiling, the band edges, the two one-shot marks and what they do, the lock and its ratio, the size of the trailing record, the verb sets each rung of the ladder tests, the per-clearance tolerances, the whole debt subsystem, the figure a fetch adds to the baseline, the disposition thresholds, the counted status set, the order the partition rows run in and the two tie-breaks were firmware constants nobody wrote down. Those two notes bound what you are looking for.

The evidence you fit against is the run itself together with the two rollups the engine produced for it. The file `/app/data/lookups.jsonl` and the four tables beside it are the input, and `/app/data/ref_partitions.json` and `/app/data/ref_catalog.json` are what the engine wrote for exactly that input. There is no reference for the per-lookup probe ledger, so a wrong constant shows up only as a wrong total, count or disposition somewhere in those two rollups, and it will not tell you which lookup or which stage it came from. Neither rollup carries an index's debt or credit, so the debt subsystem has to be fitted through what it does to costs, statuses and dispositions. On top of that, no partition sits on more than one of the three plain keyed values at once, so no partition isolates a single adjustment and the constants have to be fitted together.

Rebuild the engine as a single reusable program at this path:

```text
/app/out/broker.py
```

The program takes two command-line arguments, the input directory first and the output directory second, and it writes `probes.jsonl`, `partitions.json` and `catalog.json` into the output directory in the exact form `/app/data/reports.md` describes, down to the key order, the row order, the separators and the trailing newline of every file. It has to work on any catalogue run in this schema rather than on the shipped one alone, because it will be driven over runs you have never seen, and the per-lookup ledger it writes on those runs is read as closely as the two rollups are. A run whose three files are not all byte-exact counts as wrong for that run. Use only the Python standard library. Work every figure out from the input files at run time and keep precomputed answers out of the program. Running it twice over the same input directory must write byte-identical files. Treat everything in `/app/data` as read-only input and leave it unchanged.

Check your fit rather than settling on the first reading that reproduces a few rollup rows. Set a block of the recorded run aside while you work the constants out, then replay that held-back block and check it too. For at least one constant on which two readings both fit what you have looked at, build a small input of your own on which they disagree and run both over it. Where two partitions share two of the three keyed columns and differ on the third, use that pair to narrow the adjustment on the column they differ on. Work at least one of the figures below out a second time through a calculation separate from the program you deliver. Before you finish, compare both of your own rollups against the two shipped reference files byte for byte.

Run your finished program over `/app/data` and give a closing report in your final message. State each of these twenty figures, using these names, as plain whole numbers measured over the shipped run, each of them a sum of the quantity named beside it, and keep every one of them out of the report files themselves:

```text
total_cost           cost over every lookup
ok_cost              cost over lookups resolving to ok
dropped_cost         cost over lookups resolving to dropped
setup_cost           cost over lookups resolving to setup
locked_cost          cost over lookups resolving to locked
heavy_band_cost      cost over lookups in the heavy band
warm_band_cost       cost over lookups in the warm band
light_band_cost      cost over lookups in the light band
fetch_cost           cost over lookups carrying the fetch verb
peak_phase_cost      cost over lookups in the peak phase
shoulder_phase_cost  cost over lookups in the shoulder phase
sparse_cost          cost over lookups on sparse charged partitions
stream_cost          cost over lookups on stream plan partitions
turbo_cost           cost over lookups on turbo pool partitions
cold_cost            cost over lookups on cold pool partitions
shared_index_cost    cost over lookups on partitions whose index another partition also names
derived_view_cost    cost over lookups on partitions whose index names a parent
replica3_cost        cost over lookups on replica 3 partitions
total_debt           debt_before over every lookup
flagged_debt         debt_before over lookups resolving to flagged
```

A partial engine that is written down and reported on is worth far more than a perfect one that never gets written, so put the program in place before refining the constants you are still unsure of. Once your last few attempts have taught you nothing new, state the twenty figures and end your turn.

You have 5400 seconds to complete this task.
