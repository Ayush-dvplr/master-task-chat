# Source precedence

## The on air source

The switcher log is the only authority on what went to air. A `BUS=PGM` line puts its `SRC` on air from its instant up to, but not including, the instant of the next `BUS=PGM` line. A `BUS=PGM` line naming the source already on air changes nothing. `BUS=PST` lines describe the preview bus and never put anything on air, whatever source they name. `A` and `B` are the two playout chains; `LIVE1`, `LIVE2` and `SLATE` are non chain sources. Before the first `BUS=PGM` line nothing is on air.

The as-run logs say what each chain played. They do not say whether it went to air.

## As-run lines

A line repeated byte for byte in the same log is one line. Only `type=SPOT` lines describe spots; `PROG` and `PROMO` lines are ignored by every rule.

An admitted `retract` correction removes every `type=SPOT` line of its chain whose `evt` equals the target's event id. A removed line is neither rejected nor played.

Every remaining `type=SPOT` line is checked, and the first failing check gives its reason code:

1. `MISSING_FIELD` when any of `seq`, `date`, `tc`, `evt`, `spot`, `house`, `frames` or `status` is absent or blank.
2. `BAD_TIMECODE` when `tc` is not a valid label for the channel as defined in `timecode_and_clock.md`.
3. `DROPPED_LABEL` when `tc` is a drop frame label that drop frame counting never emits.

These are the only three reason codes. A rejected line carries no play of any kind. Among the lines that pass, those with `status=PLAYED` are plays; `CUED` and `SKIPPED` lines are not.

The governing play of a spot on a chain is its play on that chain with the earliest UTC instant, the lower `seq` breaking a tie. Its other plays on that chain are re-airs and earn nothing.

## Corrections

A correction or an amendment is admitted when its `recorded_at` is strictly before the workload's `cutoff_utc` in `close_policy.json`. One recorded at or after the cutoff is late and has no effect at all.

For `reattribute` and `restore` corrections a `rev` of 0 marks a draft that never governs. Among the admitted non draft corrections of a spot, the highest `rev` governs. When two or more share the highest `rev`, which one governs is settled by the prior close (see `reconciliation_rules.md`); if that still leaves a tie, the later `recorded_at` governs, then the greater `correction_id`. A governing `reattribute` sets the spot's order line to its payload's `order_line`; a governing `restore` sets it to the scheduled order line. A spot with no governing correction keeps its scheduled order line. This order line is the spot's governing order line in every later rule.

## Amendments

The amendments of an order line are admitted against the cutoff of its own workload. The amendment that governs broadcast date `d` is the admitted one with the greatest `effective_from` that is not after `d`, the later `recorded_at` and then the larger `spots_per_day` breaking a tie; its `spots_per_day` replaces the order line's own figure for `d`. An amendment recorded after the date it governs still governs it.

## Copies

A house id is normalized by trimming it, upper casing it and deleting every space and hyphen. The result must be three letters followed by one to five digits, and its canonical form is the three letters, a hyphen and the digits left padded with zeros to five; anything else never resolves. Ids in `house_aliases.csv` are normalized the same way.

A house id resolves as of a broadcast date `d`: starting from its canonical form, while the current id is an `old_house_id` whose `effective_from` is not after `d`, replace it with that row's `new_house_id`. The id resolves when the id reached is a `house_id` of `copy_registry.csv`; otherwise it does not resolve. Every house id of a spot, scheduled or logged, resolves as of the spot's scheduled broadcast date.

The expected frames of a copy on a channel are `ceil(frames * nominal / master_rate)`, with `frames` and `master_rate` from the registry and `nominal` the channel's nominal rate.
