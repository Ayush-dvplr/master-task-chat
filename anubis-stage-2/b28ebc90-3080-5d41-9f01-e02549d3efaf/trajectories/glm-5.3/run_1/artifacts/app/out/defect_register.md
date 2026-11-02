# Defect register

Repairs made to the shipped `daybreak` package for routing cycle
HB-2034-231. One row per departure from the working papers, naming the
function that carried it and the stage whose paper states the rule.

| defect | stage | function | rule restored |
| --- | --- | --- | --- |
| byte order mark read as part of the paper | r02 | util.read_text | a paper may open with a UTF-8 byte order mark and the mark never belongs to the first line, the first header name or the first field, so `alias_crosswalk.tsv` lost its alias column and every binding decision |
| quoted fields split on the separator inside them | r02 | util.read_delim | in a delimited register a field that opens with a double quote runs to its closing double quote, a separator inside the quotes is text and the enclosing quotes are not part of the value, so the `status` column of `source_priority_register.csv` shifted and a live identifier source was dropped |
| carriage return left on the last field | r04 | util.read_delim | a line may end with a carriage return and a line feed, and the carriage return is not part of the last field, so the cooldown register's floor units read as unconvertible |
| frozen revision never applied to the live row | r02 | loading.live_rows | the row in force for a key is the row with the greatest revision that does not exceed that key's frozen revision, not the greatest revision the register carries |
| live workbook grid taken by sheet position | r10 | loading.read_workbook | the live grid is the grid whose key cell equals `cycle_header.json.cycle_key` byte for byte, and sheet name and sheet position say nothing about which grid is live |
| edge strengths summed row by row | r01 | stages.stage_r01 | an edge strength is recorded once per declared sequence, so `totals.weight_bp` sums the recorded strengths and not every converting row |
| window start read as an offset from the origin | r02 | stages.window_grid | `window_grid.csv` records each window's start as the difference from the previous window's start, read in ascending ordinal, the first difference being taken from `origin_ms` |
| window grid live row taken against the scalar revision | r02 | stages.window_grid | each window's live row is the greatest revision that does not exceed that window's own frozen revision, and not the one scalar revision the header also carries |
| context span chain started at zero | r02 | stages.context_grid | `context_activity_spans.tsv` records start differences in file order and its first difference is also taken from `origin_ms`, never from zero |
| written zero treated as an absent field | r04 | stages._absent | a written zero records an explicit zero and settles the field where it is written, while a hyphen or an empty cell alone records an absent field |
| occurrence cap read from the routine layer first | r03 | stages._routine_cap | the occurrence cap resolves from the memo cap table first, then the routine layer `max_occurrences`, then the memo default, the first source that records a cap settling it |
| window end treated as inclusive | r03 | stages.stage_r03 | the occurrence is placed in the window whose start is at or below the trigger and whose end is above it, so a trigger on a window end belongs to the next window |
| one shot remaining read from the journal | r04 | stages._layer_records | the remaining of an override is read from `state_snapshot.json.oneshot_remaining`, which outranks the journal's own field |
| cooldown floor read against the wrong frozen revision | r04 | stages.cooldown_floors | the live floor row of the cooldown register is chosen under RR1 against `state_snapshot.json.frozen_revision_cooldown_register` |
| policy layers resolved in a fixed order | r04 | stages.resolve_policy | for each field the strongest applicable layer that records it settles it, the strength of a layer being the rank the directive part A gives it, which puts the action layer above the device layer |
| one shot applied up to and including its expiry | r04 | stages.resolve_policy | the one shot layer applies only while the override has remaining above zero and the trigger is strictly before its expiry |
| settlement key read in the wrong order | r07 | stages.stage_r07 | `key_settled_at` is the ordinal of the first key in the directive part B order whose values are not all equal across all of the cycle's edges, that order being strength, dependent tier, declared sequence, then the text key |
| first demand product carried unrounded | r09 | stages.demand_of | the demand is `half_even(half_even(energy * effective_intensity / 10000) * window_scale / 10000)`, both roundings happening and the first result never carried unrounded into the second product |
| pool fit test excluded equality | r10 | allocate._select | a demand at or below the pool fits and reduces it, so a demand exactly equal to the pool binds the pool and does not displace |
| candidate scan stopped at the first misfit | r10 | allocate._select | a demand above the pool displaces that instance and the next candidate is still considered |
| reconciliation round cap held inside the package | r12 | allocate.stage_r12 | the round cap is the directive part C figure and it counts every binding of the chain, the first binding counted as round one, so a cap of three means two rounds here |
| round offered the proposals alone | r12 | allocate.stage_r12 | each round takes its current holders together with the round's proposals for a window and device and offers them the same pool r10 offered at the start of its discretionary phase |
| one shot consumed once per applying instance | r13 | allocate.stage_r13 | an instance to which a one shot override applied in r04 marks that override as consumed once, whichever layer settled its tier |
| next state consumption taken from the first pass | r13 | publish.render | a one shot override is consumed only by the second pass, so the next state's remaining is the snapshot's less the consumption of the recomputed pass |
| gate tested against the day's final value | r14 | allocate.stage_r14 | a gate closes on the value the first pass wrote strictly before the instance's own trigger, and not on the value the key holds after later writes |
| kept proposals drawn from the pool twice | r14 | allocate.stage_r14 | every discretionary survivor of r14, a kept fallback proposal included, draws its demand from its pool exactly once |
| prior cycle consumption taken from the last differing row | r14 | publish.render | `prior_cycle_mwh` is the consumption recorded for that device at the greatest cycle index in the energy ledger, or zero when the ledger carries none |
| dependent tier taken over every expanded instance | r07 | publish.run_chain | the tier of a dependent action is the least resolved tier over the eligible instances of that action, and an action with no eligible instance takes the global tier |
