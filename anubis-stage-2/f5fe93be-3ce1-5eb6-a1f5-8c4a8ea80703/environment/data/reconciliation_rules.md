# Reconciliation rules

These rules decide, for every scheduled spot of a workload, one disposition. They use the definitions of `timecode_and_clock.md` and `source_precedence.md`.

## Terms

The expected frames `E` of a spot are the expected frames, on the workload's channel, of the copy its scheduled `house_id` resolves to.

The reference play of a spot is chain A's governing play of the spot when chain A is on air at that play's instant. Otherwise it is chain B's governing play of the spot when chain B is on air at that play's instant. Otherwise the spot has no reference play.

The spot span is the half open interval of UTC instants from the reference play's instant to that instant plus `E * frame_ticks`.

The partner play is the governing play of the spot on the chain that did not give the reference play. The sync offset is the absolute difference, in frames, between the absolute indexes of the partner play and the reference play.

## Dispositions

A spot's disposition is the first of these that applies.

1. `UNRESOLVED` when its scheduled `house_id` does not resolve.
2. When it has no reference play: `PREEMPTED` when chain A's governing play exists and has a non chain source on air at its instant, or else when chain B's governing play does; otherwise `MISSED`.
3. `PREEMPTED` when a non chain source is on air at any instant of the spot span.
4. `PARTIAL` when the reference play's `frames` are fewer than `E`. A spot whose span also puts the other chain on air at some instant is `PARTIAL` or goes on to the next step as the prior close settled it; that settlement depends only on whether the partner play exists, whether the partner play's `frames` reach `E`, and how the sync offset compares with `sync_tolerance_frames`.
5. `UNRESOLVED` when the reference play's `house` does not resolve.
6. `WRONG_COPY` when it resolves to a different copy from the scheduled one.
7. `AIRED` when the reference play lies in the window of its governing order line's daypart, and `OUT_OF_WINDOW` otherwise. Window membership is settled by the prior close; it depends only on the reference play's broadcast clock count, `E` and the daypart's bounds.

These seven codes are the only dispositions. A spot's `chain` is the chain of its reference play; for a `PREEMPTED` spot without one it is the chain of the play that found the non chain source; a `MISSED` spot, and an `UNRESOLVED` spot of rule 1 without a reference play, have none. A spot's broadcast date is the broadcast date of the play that gave its chain, and its scheduled broadcast date when it has no chain.

An occupying spot is a spot with a reference play whose disposition is `AIRED`, `OUT_OF_WINDOW`, `WRONG_COPY` or `UNRESOLVED`. It occupies its scheduled break with its reference play's `frames`.

## The prior close

`prior_close_decisions.jsonl` records decisions the previous close made under these same rules, on another channel and week. Three points of these rules are settled only there: the step 4 outcome for a span that puts the other chain on air, window membership in step 7, and the tie between corrections that share the highest `rev`. Each point has exactly one reading that reproduces every record in the file, and that reading governs this close. Every record carries `case_id` and `kind`.

A `failover_straddle` record is a spot whose span put the other chain on air. It carries `rate`, `tolerance_frames`, `on_air_start_tc` (the reference play's corrected label), `other_start_tc` (the partner play's corrected label on the same local date), `other_complete` (whether the partner play's frames reached `E`) and `outcome`: `aired` when the spot went on to step 5, `partial` when it was `PARTIAL`.

A `window_edge` record is a reference play checked against a daypart of the `standard` set. It carries `rate`, `daypart`, `window` (`HH:MM-HH:MM` on the broadcast clock), `start_tc` (the reference play's label), `after_local_midnight` (true when that label falls on the local date after its broadcast date), `frames` (`E`) and `outcome` (`in_window` or `out_of_window`). Every `window_edge` record uses a 06:00:00 broadcast day start.

A `correction_tie` record carries `versions`, the competing admitted corrections of one spot, each with `desk`, `rev`, `recorded_at` and `order_line`, and `outcome_order_line`, the order line that governed.

In every record `rate` is `30000/1001` (drop frame) or `25` (non drop).
