# TRUTH.md - 7e0d8feb-b218-56cb-ab2f-c6e13f40fed9

Author side record. Kept out of the agent image by the environment Dockerfile, which
copies `data/` and nothing else.

Fourteen dependent stages derive one transmission day
of a regional playout channel from ingest, schedule, index, market, contract and
regulatory records. Every stage freezes a value the next stage consumes. No working
implementation ships. Every identifier and every value in the input data is specific to
this channel and exists nowhere else.

## Defect

The forty graded decisions, each behind a rule id the reference can revert in
isolation. The classification says what each one is for: `(focal)` is a spine decision the
whole day hangs off, `(drift)` is a decision that shifts a value without changing the
shape of the answer, `(trap)` is a decision whose wrong reading is what a fluent
implementation reaches for first.

1. R01 `(focal)` V1 clusters on the economic `content_ref`; the per attempt `ingest_id` is
   not an asset key.
2. R02 `(focal)` the canonical attempt is the greatest `revision_no` among the quality
   passed attempts, and a cluster with none is excluded from every downstream stage.
3. R03 `(drift)` a revision tie breaks on the `ingest_id` that sorts first.
4. R04 `(trap)` the published house number comes from the first received attempt, which is
   almost never the canonical one.
5. R05 `(trap)` the editorial rate is the exact rational from the rate register, and
   `nominal_fps` is a rounded display label.
6. R06 `(trap)` drop frame applies only where `df_allowed` permits it for that rate code,
   whatever the row claims.
7. R07 `(focal)` the settled workbook sheet is the one whose control set cell matches the
   channel configuration; the workbook carries three sheets and the other two carry terms
   of their own.
8. R08 `(drift)` the end of media timecode is exclusive, and an end below the start wraps
   one whole timecode day.
9. R10 `(focal)` every conversion into channel frames floors and carries the discarded
   fraction inside a named scope; nothing is rounded to nearest.
10. R11 `(drift)` conversions inside a scope run in the stated order, capacities in
    transmission order.
11. R12 `(trap)` only a head run and a tail run of black is trimmed; interior black is
    transmitted.
12. R13 `(drift)` an asset with no part rows transmits its whole source span as one part.
13. R14 `(focal)` a break snaps back within the tolerance and forward otherwise.
14. R15 `(focal)` the last break of a slot absorbs the displacements of the earlier breaks
    in that slot.
15. R16 `(focal)` the broadcast day opens at `06:00:00;00`, so the small hours sit at the
    end of the day.
16. R17 `(drift)` a slot whose asset has no canonical attempt is dropped from the day.
17. R18 `(focal)` a fixed junction overrun is trimmed from flexible parts backwards to the
    previous fixed junction inclusive, with a floor of zero.
18. R19 `(trap)` the filler is the first match in ascending predicate order among
    available stock.
19. R21 `(focal)` spot durations convert under the advertiser carry scope before any
    admission decision is taken.
20. R22 `(focal)` seven admission predicates are evaluated in the published order and the
    first match settles the deferral reason.
21. R23 `(drift)` the separation minimum is counted in admitted positions inside one
    break.
22. R24 `(drift)` the admission walk is ascending priority band and then ascending order
    reference.
23. R25 `(trap)` a blackout window is inclusive at both ends.
24. R26 `(trap)` a rule marked override overturns every rule before it, so the last
    overturning rule wins from a higher precedence number.
25. R27 `(trap)` billable grains are a ceiling over the frames one grain occupies.
26. R28 `(trap)` the rate card is the greatest effective date on or before the transmission
    date.
27. R29 `(drift)` the minor unit exponent is per currency and is zero for one of the four
    settlement currencies and three for another.
28. R30 `(trap)` commission comes from the settled workbook sheet at half even on the minor
    unit; the legacy percentage table is superseded.
29. R31 `(focal)` the make good cap is redistributed by largest remainder so that the
    allocated total equals the cap exactly.
30. R32 `(trap)` the clearance state comes from the greatest journal sequence, and the
    logged timestamp is backfilled.
31. R33 `(drift)` a spot contributes to each clock hour the frames that lie inside it.
32. R34 `(trap)` the regulatory cap is the exact conversion floored, and a breach is
    strictly above it.
33. R36 `(drift)` the digest runs over the seven core artifacts in pipeline order.
34. R37 `(drift)` Section 2 of the memo sets the permitted minutes of the market hours it
    lists, replacing the Section 1 figure there; an unlisted market hour keeps Section 1.
    Three market hours per day differ from Section 1 and two are not listed.
35. R38 `(trap)` `journal_seq` compares as a whole number. About one order in nineteen has
    a journal of ten or eleven rows whose sequence 9 carries the opposite of the settled
    held state.
36. R39 `(trap)` two eligible cards of one reference on one date are settled by the greater
    `card_revision` as a whole number (10 over 9), never by file order; a card dated the
    calendar day after the transmission date prices none of the broadcast day.
37. R40 `(trap)` the timecode separator is not evidence of drop frame. Labels of some
    assets, of some parts and of two schedule slots are keyed with the other separator.
38. R41 `(focal)` V13 runs before V11: the frames above each breaching market hour's cap
    go unbilled, latest spots first; V11 bills the rest, and V12 owes the lost grains as
    `DF_OVER_CAP` obligations, which also lowers the day gross the make good cap is taken
    from.
39. R42 `(trap)` a workbook value stored as a rich text shared string is the
    concatenation of its runs. The snap tolerance on every sheet and the two digit
    commission numerators of every third advertiser are split into two runs.
40. R43 `(trap)` `received_at` carries an explicit UTC offset and the anchor is the
    earliest instant; compared as text the anchor flips in about a third of the clusters.

## Load-bearing work

The snap tolerance and the make good cap numerator and denominator live only in the
settled sheet of `contract_terms_workbook.xlsx`, beside the per advertiser commission
terms; the workbook carries three control sets and is a real OOXML package. The
separation minimum positions, the
billing grain seconds and the regulatory minutes per clock hour live only in
`regulatory_minutage_memo.pdf`, which is a real PDF 1.4 document. Its Section 2 table of
permitted minutes per market hour departs from the standing figure on three market hours
of every day, so it has to be parsed, not skipped. None of those six figures
is published in any plain text file of the corpus, every one of them gates a published artifact,
and `manifest.json` publishes all six, so a solver that skims the markdown alone cannot
converge.

Where a specification names a wrong reading, it names it only to rule it out. No document
in the corpus publishes aggregate counts a day can be checked against, and the worked
examples carry only the timecode and rate vectors. Every graded rule is stated once,
normatively, in the corpus specifications.

`playout_audit.sqlite` and `traffic_audit.db` corroborate the flat files.
`legacy_commission_table.csv`, `blackout_overlay_drafts.xml`, the two superseded workbook
sheets, the `nominal_fps` column and `prior_conform_register.csv` are the decoys, and every
one of them is disavowed in `data_lineage.md`.

## Verification

Channel A is `tests/test_output.py`. The verifier owns its corpus: it regenerates the whole
input tree from named seeds inside its own container and recomputes every expected artifact
from that regeneration, so it never reads the agent corpus, which does not exist there.

Positive weight total 85, negative weight total -26, across 29 graded criteria. Seventy
one of the eighty five positive points are spent on the delivered program: sixty on three
transmission days minted from seeds the agent never sees, one dense, one sparse and one
further standard day, each run with `--data` and `--out`, five on a further minted
standard day whose first scheduled slot is dropped, also run with `--data` and `--out`,
three on a run with neither flag over another minted day staged at `/app/data`, which no
other criterion grades, and three on the manifest digest of a run over one more minted
standard day, which no other criterion reads.

A spine of seventeen artifacts carries one published observable of every stage, and each of
the three families is compared on its own artifacts alone. A wrong reading forfeits the
spine on every graded day, even when it moves one column of one artifact, together with
whichever family publishes it, and leaves the families it does not touch earnable. A
reading that moves the placement of the day, such as the canonical attempt, the carry,
black part retention or the junction walk, reaches every family and leaves only presence
and parsing.

The eight negative criteria are `negative_weight_hardcoded_sample_answers`,
`negative_weight_program_ignores_its_input`,
`negative_weight_nondeterministic_output`,
`negative_weight_filename_dependent_behaviour`,
`negative_weight_program_needs_a_third_party_package`,
`negative_weight_program_dirties_its_directories`,
`negative_weight_reads_training_corpus_at_runtime` and
`negative_weight_program_writes_outside_its_out_dir`. Each one names a delivery that cannot
have been computed from the day it was handed or that breaks a rule the instruction states
for the program, and each one refuses to fire on the oracle. A wrong reading of a stated
rule carries no negative charge of its own: it already forfeits the spine and the family
that publishes it, and charging it a second time would put an honest mistake below an
empty delivery. The copied answer detector requires the shipped spine to be byte exact and
all three minted days to be wrong, so a bug that only bites under one profile forfeits
weight without being charged as a copy. The standard library detector runs the second pass
over the probe day with every site-packages directory taken off the import path, and fires
only when that pass stops on an import the full interpreter satisfied. The directory name
detector stands down when two runs over the shipped day under one name already disagree,
so a nondeterministic delivery is charged once, by the nondeterminism detector.
`manifest_digest_matches_core` earns three points when the manifest the delivered program
writes for that digest day publishes a digest that is both the digest the derived core
entails and the digest of the core the program wrote, so a self consistent digest over a
wrong core earns nothing from it. It reads no file another check reads: the shipped
manifest, digest included, is paid once, by the spine.

Channel B is `tests/judge.toml`, thirty four criteria, one hundred and three positive points
and minus thirty one negative points, nine of them negative. No criterion compares a
published figure; Channel B owns process, evidence and the quality of the delivered code,
and Channel A owns the numbers. Six criteria are typed instruction following and each one
enforces a rule the instruction states: `/app/data` left unedited, every write kept inside
`/app`, `/app/out` left holding the twenty six named files, and the three rejected sources
kept out of the derivation. None of
them reads an observable a check in Channel A reads. One criterion,
`r34_program_code_quality`, judges how the delivered program is written, which no assertion
can decide and which Channel A pays identically whether the code is readable or not. Every
negative in Channel B names a triggering action no negative in Channel A shares, so one
wrong decision is never charged twice.

`tests/reward.toml` combines the two channels at half the reward each, test_output at
0.5/85 and judge at 0.5/103, so neither channel alone can carry a delivery.

Each minted-day run puts `--out` two levels below directories that do not exist, so the
program has to create the parents, and hands the program a private `HOME` and `TMPDIR`;
anything left in either, or beside the output directory, is charged by
`negative_weight_program_writes_outside_its_out_dir`.

Properties of the shipped grading:

- Range. The oracle delivery scores 1.000 on the test channel and an empty delivery scores
  0.000 on it. Both figures are test-channel figures and that channel is half of the
  reward; the judged channel carries the other half and is scored from the trajectory.
- Oracle independence. `solution/solve.py` is written from the stage specifications and the
  artifact contract rather than lifted out of `tests/test_output.py`, so the oracle and the
  verifier are two implementations that can disagree. They agree on all twenty five
  artifacts byte for byte over the seven graded days and thirty further minted days
  spanning all three profiles, standard, dense and sparse.
- Per rule separation. Every rule above changes at least one graded artifact on every day
  whose artifacts are graded: the shipped day, the three minted days, the lead drop day and
  the default path day. The digest day is graded on its manifest digest alone, which
  thirty five of the forty rules move; R11, R19, R22, R26 and R31 leave the seven core
  artifacts unchanged there.
- Alternative readings. Every rule's fluent alternative is implemented behind its rule id
  and measured as a mutant solver, so the corpus separates the two readings rather than
  leaving them indistinguishable.
- Float precision. On integer source rates the generator nudges up to two retained parts
  per scheduled asset so the exact V4 carry lands on a whole frame at the end of them,
  choosing each nudge so a float pipeline that has not yet misfloored on the day does.
  Six float orderings of the rate conversion, each with a held carry or a running sum,
  were measured: every one misfloors on at least four of the seven graded days, and a
  copy of `solve.py` whose conversion is rounded through a float in any of the six
  orderings fails all seven graded days.
- Trigger depth. Seven stated clauses that no rule id isolates are planted on every graded
  day: two ingest attempts of one asset received in the same second, two floating slots on
  one scheduled label written to the schedule in the opposite order, a two break slot whose
  last break has its adjusted target floored at zero, an advertiser whose every order is
  held so that it carries obligations against a cap of zero, two matching blackout rules at
  one precedence written out of rule_id order, a slot the prior register does not carry,
  and an order whose rate card reference has no row in the book. On a dense day the last
  slot is pinned a quarter of an hour before the next day start, so admitted spots run past
  the end of the broadcast day into `H29`. Every day also carries an admitted spot across a
  clock hour edge: when the written day has none, the generator moves the last break of a
  slot that spans an edge to sit just before it and keeps the move only when a spot then
  straddles the edge. Each of these clauses read the other way loses graded weight.
- Graded surface coverage. Every member of every closed vocabulary the checks compare is
  emitted by the shipped day: two published quality states (all five input quality states
  occur in the shipped ingest register), four part kinds, three retention states, four snap
  sides, two placement states, two junction kinds, six correction reasons, eight deferral
  reasons (seven deferrals and the `DF_OVER_CAP` obligation reason), five separation classes, four currencies, two breach states, two break origins,
  two exception codes, seven rate codes, four markets and twenty four clock hour labels.
- Sensitivity. Every single rule revert forfeits the spine and every family that publishes
  the stage it touches, on the shipped day and on each minted day it reaches, and no revert
  scores below an empty delivery.

## Root cause

`prior_conform_register.csv` is the previous automated conform of the same transmission
day. It was produced before the index was published and before the carry rule was written
down, so it carries the scheduled offsets in place of the placed starts and a per part
rounding in place of a carried one, and it counts breaks that the conditioning moved. It
never carried the last slot of the day. It is reported against at stage V14 and is an input
to no other stage.

## Solution shape

Fourteen stages in order, exact rational arithmetic throughout, rounding only at write
time, and the same derivation delivered as a standard library only program that takes its
data and output directories from the command line.

## Ordered plan

1. Read the overview, the lineage map and every stage specification.
2. Open the workbook as a zip, match the control set cell against the configuration, and
   take the snap tolerance and the commission terms from the settled sheet.
3. Extract the memorandum text, take the three settlement constants, and take the
   Section 2 permitted minutes per market hour.
4. V1 to V3: cluster, canonicalise, anchor, resolve the rate and the drop frame flag, take
   the exclusive span with the day wrap.
5. V4 and V5: convert under the carry rule inside the slot scope, trim head and tail black,
   sum the material.
6. V6: convert the break offsets in the slot scope, snap by the tolerance, absorb the
   displacement in the last break of each slot.
7. V7 and V8: order the day from the six o'clock start, pin the fixed junctions, trim
   backwards on an overrun, fill by the first matching predicate on an underrun.
8. V10 then V9: settle the market break sets, convert every spot duration in advertiser
   order, walk the seven admission predicates.
9. V13: advertising frames per clock hour against each market hour's floored cap, and the
   frames above a breached cap left unbilled, latest spots first.
10. V11 and V12: grains as a ceiling over the billed frames, the card on or before the date
    with revision ties settled numerically, minor units per currency, commission at half
    even, deferrals and lost grains as obligations, the cap redistributed by largest
    remainder.
11. V14: the reconciliation and the digest in pipeline order.

## Pitfalls

- The rounded label is never the rate. `29.97` is not `30000/1001`.
- The anchor attempt is not the canonical attempt.
- The carry is scoped, and the scope name is part of the answer.
- The last break of a slot does not aim at its own nominal position.
- The broadcast day puts the small hours at the end.
- A deferred spot consumes no capacity and takes no position.
- An overturning blackout rule wins from a higher precedence number.
- The make good redistribution preserves mass.
- The workbook carries three sheets and two of them are superseded.
- A rich text cell is all of its runs.
- A separator is not a drop frame flag, a sequence is not a string, and an arrival time
  is an instant.
- Settlement runs after compliance, and the cap moves money.

## Provenance

```yaml
task_name: terminal-bench/7e0d8feb-b218-56cb-ab2f-c6e13f40fed9
instance_ref: inst-d05472199f
channel_ref: ch_regional_one
transmission_date: 2029-03-01
solve_py_sha256: e26484375f1caddb80fa1121652d35c1e2521d78b8eea44049fb832198d8bf76
category: Video Processing
language: python
artifacts: 26
graded_checks: 29
positive_total: 85
negative_total: -26
judge_criteria: 34
judge_positive_total: 103
judge_negative_total: -31
network: no-network for the environment, allowlist for the agent harness and the verifier's judge
```
