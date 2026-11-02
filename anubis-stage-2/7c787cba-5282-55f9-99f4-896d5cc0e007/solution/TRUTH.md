# TRUTH.md - 7c787cba-5282-55f9-99f4-896d5cc0e007

The golden trajectory for the Aldermere regional working timetable path
calendar compile. The agent is handed `instruction.md`, the 4.2 build of the
compiler at `/app/repo` and the twenty seven file extract at `/app/wtt`, and
nothing else. This document records what the task is actually about, what
grading looks at, and where a competent solver still loses points.

## Defect

Nothing crashes. The shipped 4.2 build of `pathcal` runs to completion on the
shipped extract and writes all eighteen documents. What is wrong is that it
departs from the railway's own rulebook in thirteen places, spread over nine of
the ten stages, and the stages are coupled, so one wrong day anywhere moves the
running calendar, the admission walk that consumes it, every rollup and the
digest. The work is to find all thirteen by reading the rulebook against the
code, repair them, and hand over a build that compiles an extract it has never
seen.

1. (focal) `expand` builds one candidate list across every period of a rule and
   then applies the set positions to that list. Stage 3 applies them inside each
   period's own candidate set, so position 2 is the second candidate of its
   period and not the second candidate of the expansion. It also reports the
   size of the flattened list as the candidate count, which happens to be the
   right total. Defeats `set_positions_select_inside_each_period`.
2. (trap) `expand` reads a position below zero at index `size + position - 1`,
   one place earlier than the rulebook's `size + position`. No rule in the
   shipped extract carries a position below zero, so the shipped output is
   identical either way and the fault shows only on other periods. Defeats
   `positions_below_zero_count_from_the_period_end`.
3. (focal) `stage_exceptions` clips the expansion to the validity window and
   applies the cap before it applies the exclusions and the additions. Stage 4
   merges first, caps the merged sequence second and clips third, so a path
   whose exclusions bite loses days the cap would otherwise have kept, and the
   cap counts from the rule anchor rather than from the window. Defeats
   `the_cap_counts_after_the_exclusions` and `the_cap_counts_from_the_rule_anchor`.
4. (focal) `materialize` resolves a gap by subtracting the offset that applies
   after the transition, which moves the reading backward out of the gap. Stage
   6 subtracts the offset that applied before it, which moves the reading
   forward by the length of the gap. Defeats
   `gap_departures_shift_forward_by_the_gap`.
5. (trap) `materialize` resolves a fold to the first of the two instants. Stage
   6 takes the later one. The shipped extract's period ends before the one
   transition whose offset shrinks, so no shipped departure is ever a fold and
   the shipped output is identical either way. Defeats
   `fold_departures_take_the_later_offset`.
6. (focal) `_wins` reads the issue stamp before the priority. Stage 5 reads the
   priority first, then the issue stamp, then the identifier. Defeats
   `variant_precedence_follows_priority_then_stamp`.
7. (trap) `stage_overlay` never rejects a variant cycle. It walks the base chain
   with a hop limit and leaves both members of a cycle running, so the rejected
   list stays empty and the two paths keep their days. No `variant_of` column of
   the shipped extract forms a cycle, so the shipped output is identical either
   way. Defeats `supersession_chains_resolve_and_cycles_are_rejected`.
8. (focal) `Identity.walk` takes one alias hop. Stage 1 takes up to eight, so a
   chain two or more deep resolves to a retired identifier the register does not
   carry and every exception row behind it silently applies to nothing. Defeats
   `canonical_path_form_merges_wire_spellings` and
   `alias_chains_resolve_and_cycles_are_rejected`.
9. (trap) `Identity` never computes the set of identifiers that sit on a cycle,
   so no cycle is ever reported and no register path is ever rejected for one.
   The shipped alias map holds no cycle, so the shipped output is identical
   either way. Defeats `alias_chains_resolve_and_cycles_are_rejected`.
10. (drift) `_clears` treats a gap equal to the minimum headway as a conflict.
    Stage 7 clears it. The instinct that a minimum must be exceeded is what
    plants this one, and the shipped extract never lands on the bound, because
    every departure, every section offset and the deferral step are all an even
    number of minutes while the three minimum headways in force are odd.
    Defeats `a_gap_equal_to_the_minimum_headway_clears`.
11. (drift) `stage_headway` sorts the walk by identifier and service date only,
    dropping the operator rank weight and the path priority that the rulebook
    puts first, and `stage_timepoints` measures a midnight crossing against the
    UTC date rather than the local date of the zone. Both read as tidying up.
    Defeats `the_admission_walk_follows_the_canonical_order` and
    `midnight_crossings_keep_the_service_date`.
12. (focal) `_read_zones` reads `zone_transitions_proposed.csv` and
    `applied_headway` applies every mailbox message whatever its subject prefix.
    The role index names `zone_transitions.csv` as the file of record and the
    rulebook binds only the `APPROVED-HEADWAY` prefix. Defeats
    `approved_mailbox_headway_revision_is_applied` and
    `superseded_sources_change_no_compiled_figure`.
13. (focal) `stage_calendars` packs the bits of a byte highest first, and the
    JSON writer leaves the keys unsorted and omits the trailing newline. Stage 9
    packs the earliest day of a byte into the lowest bit, and the schema fixes
    the serialization. Defeats
    `canonical_calendars_encode_the_admitted_days` and
    `declared_outputs_are_present_and_canonical`.

The reference implementation at `solution/solve.py` is the engine written
against the shipped documents alone. It parses the eight file formats the
extract uses with the standard library, walks the ten stages in the rulebook's
order and writes the eighteen documents exactly as `report_schema.md` defines
them. The verifier in `tests/test_output.py` holds a second, independently
structured derivation: it builds each extract as a set of model objects and
compiles the model rather than the files, so the two sides share no parsing code
and catch each other's mistakes. Their agreement is checked on the shipped
extract and on forty nine generated extracts.

Out of bounds: the agent is never asked to repair the extract, to reconcile
against the leftovers of the stopped run, to produce anything outside
`/app/out`, or to reach the network. Nothing in the task depends on a value that
lives only in `solution/` or `tests/`; every rule a graded figure needs is
written out in the shipped documents, and `worked_reference_slice.md` compiles a
tiny invented extract stage by stage so a solver can confirm its machinery one
stage at a time without any figure of this extract being copyable from
anywhere. Embedding this extract's digest or its path minute total fires
`negative_hardcoded_sample_answers`; reaching for the shipped extract from
inside the delivered tool fires
`negative_reads_training_corpus_at_runtime`; writing beside the output
directory fires `negative_writes_outside_the_argument_directories`.

## Load-bearing work

Twenty graded artifacts, every one of them under `/app/out`:

- `ttc.py`, the command line entry, and `pathcal.py`, the engine. The pair is
  graded by being run: the checks execute it against generated extracts it has
  never seen and compare its documents to the figures the rulebook defines.
- `identity_resolution.json`, the stage 1 canonical path count, the alias row
  count, the count of spellings that resolved through an alias, the cycle
  members, the malformed spellings and the unresolved spellings.
- `authority_resolution.json`, the stage 2 source of record for five contested
  fields with the divergence count of each, and the superseded file count.
- `expansion_audit.json`, the stage 3 period count, candidate count, selected
  count and first and last selected day per path, plus the rules that selected
  nothing.
- `exception_merge.json`, the stage 4 exclusion, addition and dropped addition
  counts, the pre cap and post cap counts, the cap, and the window bounds per
  path.
- `overlay_resolution.json`, the stage 5 chain root, chain depth, lost day count
  and kept day count per path, the edge count and the rejected cycle paths.
- `timepoint_materialization.json`, the stage 6 gap, fold, shifted minute and
  midnight crossing counts and the first and last departure instant per path.
- `headway_resolution.json`, the stage 7 admitted, deferred and withheld totals,
  the deferral histogram and the admitted entry count per section.
- `withheld_paths.json`, every withheld movement with its reason and every
  rejected path with its reason.
- `compiled_timetable.json`, the stage 8 admitted, deferred and withheld day
  counts, the deferral minute total and the path minutes per path.
- `canonical_calendars.json`, the stage 9 base day, bit length and hex string
  per path and the set bit total.
- `timetable_digest.json`, the stage 10 digest, its modulus, its term count and
  its leading three terms.
- `data_quality.json`, the seven issue codes with their counts and subjects.
- `operator_rollup.tsv`, `section_rollup.psv`, `path_rollup.csv`,
  `flagged_paths.xml`, `compile_report.md` and `run_status.txt`, the delimited,
  XML and prose rollups.

Content contract per deliverable. Every JSON document is one object serialized
with sorted keys, two space indentation and a trailing newline. Dates are
`YYYY-MM-DD` and instants are `YYYY-MM-DDTHH:MM:SSZ`. The delimited rollups
carry the documented header line, one row per key in the stated order, no
quoting, a single newline between rows and one at the end.
`flagged_paths.xml` carries a `count` attribute and one `path` child per flag
ordered by identifier then reason. `compile_report.md` is twelve lines and
`run_status.txt` is one, both in the line shapes the shipped reporting helpers
already write, which `INTERFACE.md` names and the repair leaves alone.

Out of bounds by design: a delivered tool that needs a third file of the
agent's own, a tool that reads the shipped extract rather than its first
argument, and any document written outside the second argument.

## Verification

`tests/test.sh` hardens the verifier and hands over to rewardkit, which scores
two channels and combines them in `tests/reward.toml`, each at half weight.

Channel A is `tests/test_output.py`: fifty six checks, forty nine positive and
seven negative. The positive weights total 195, so the channel weight is
`0.5 / 195`. One check weighs 1 and grades that the tool, its engine and the
eighteen documents are present and that each JSON document is canonically
serialized. One weighs 5 and grades every document of the shipped extract.
Twenty three weigh 3 each and are graded on freshly generated extracts: each one
builds its own extract with one rule turned up, runs the delivered tool on it
under a dropped uid, and compares the document that rule governs, so one missed
rule costs one check rather than the whole channel. Twenty four weigh 5 each and
are the held-out tier: each is a complete extract with its own seed and its own
fault profile, compared document by document across all eighteen. Existence,
shape and shipped extract checks together carry 6 of the 195 positive weight,
which is 3.1 percent, and the held-out tier carries 120 of it, which is 61.5
percent.

The weighting says what the task is for. Repairing a fault the shipped extract
reveals is an important sub-goal and pays 3. Compiling an extract the agent has
never seen is the deliverable itself and pays 5, twenty four times over, because
the instruction promises exactly that and because a build that reproduces this
period while failing the next one has not done the work.

Every generated extract carries the whole documented rule set, traps included,
so a build that keeps twelve of the thirteen faults repaired still loses the
check that reads the stage the thirteenth sits in and most of the held-out tier.

The seven negative checks are `negative_hardcoded_sample_answers` at -5,
`negative_writes_outside_the_argument_directories` at -5,
`negative_deliverable_names_the_grading_surface` at -3,
`negative_nondeterministic_output` at -3,
`negative_filename_dependent_behaviour` at -3,
`negative_reads_training_corpus_at_runtime` at -3 and
`negative_rebinds_verifier_dependencies` at -1, for 23 of negative weight
against 195 of positive. The two that read the delivered source read the
literals the code evaluates rather than the raw file text, so a path or a total
named in a comment or a docstring is documentation and not a cheat.

Channel B is `tests/judge.toml`: eleven criteria, six positive totalling 18 and
five negative totalling 15, so the channel weight is `0.5 / 18`. Every one of
them judges how the agent worked, because what was produced is already graded
document by document in channel A and grading it twice would pay once for one
observable. Three weigh 3 and watch the method: reproducing the worked reference
slice, probing a fold on an extract the agent built itself, and recording each
fault against the rulebook stage it departs from. One weighs 5 and judges the
repaired engine as code a reviewer would accept. One weighs 3 for running the
tool twice and diffing the output, and one weighs 1 for reading the rulebook
before editing. The negatives cover opening the grading surface, stating a total
with no derivation behind it, claiming a reconciliation the trajectory never
ran, editing the shipped extract, and looping on one failing command.

Neither channel grades the same observable twice. Channel A reads the written
documents and nothing else; channel B reads the trajectory and the delivered
source, and asks only how the work was done, never what it came out as. No
criterion asks the response to restate a figure any document carries.

## Root cause

**A position is a property of a period.** Stage 3 is a two level construction:
periods first, then a candidate set inside each one, then a selection inside
that set. Flattening the two levels into one list produces a selection that is
plausible, monotone and wrong everywhere, and the candidate count comes out
right, which is why the fault survives a sanity check on totals.

**Order decides a cap.** A cap applied to a raw expansion and a cap applied to
the merged sequence keep different days whenever an exclusion bites, and a cap
counted from a window keeps different days from a cap counted from an anchor.
Both reorderings look like tidying and both change the running calendar. The
rulebook therefore fixes the order of all three operations rather than their
definitions alone.

**A wall clock reading is not an instant.** A local reading is a question about
a zone's offset history, and the history answers it with one instant, two, or
none. Two is a fold and none is a gap, and each has one documented resolution.
A reader that subtracts a single offset gets the ordinary readings right and the
two interesting ones wrong, which is the shape the shipped extract hides and a
generated one does not.

**Admission is a walk, so the order is the answer.** The admitted set grows as
the walk proceeds, so which movement meets an empty section and which meets a
full one is decided entirely by the walk order. That is why the rulebook states
four ordering keys rather than leaving the order to the file, and why a gap
exactly on the bound has to be settled in writing.

**Authority is declared, not inferred.** Five fields ship twice, and both copies
are well formed and plausible. Only `file_role_index.md` distinguishes them, and
only the subject prefix distinguishes a binding mailbox revision from a
proposal. A compile is wrong in exactly the places a reader trusted the wrong
copy.

**A document contract is part of the deliverable.** Sorted keys, a trailing
newline, a bit order and a header line are not cosmetics here: the documents are
compared as values and as bytes, so the writer is graded alongside the stages.

## Solution shape

1. Parse the extract: the period bounds, the operator table out of the HTML
   register, the sections, the routes out of the pipe separated file, the zone
   transitions out of the file of record, the rules, the register, the alias
   map, the exception rows, the headway policy and the mailbox.
2. Build identity: canonicalise every spelling, walk the alias map up to eight
   hops, collect the identifiers whose walk returns to them, and drop the
   register rows that sit on one.
3. Resolve authority: name the file of record for each of the five contested
   fields, count how far each superseded copy diverges, and apply the approved
   mailbox revision to the headway table.
4. Expand each rule period by period, building each period's candidate set and
   selecting inside it.
5. Merge the exceptions, drop the additions that collide with an exclusion, cap
   the merged sequence from the anchor, then clip to the window.
6. Resolve the variant forest, reject the cycles, and take the edges in base
   depth, base identifier and variant identifier order.
7. Turn each surviving day into a departure instant, resolving gaps forward and
   folds to the later instant, then add the section offsets.
8. Walk the movements in rank, priority, identifier and date order, trying
   deferral counts in ascending order and admitting at the first that clears.
9. Roll the admitted set up per path, re-encode it as a bit calendar lowest bit
   first, and reduce the digest over the paths in identifier order.
10. Render the twelve JSON documents with sorted keys and the six text
    documents in the shapes the schema and the reporting helpers fix.

## Ordered plan

1. Read `timetable_rulebook.md` end to end before touching the engine, then
   `file_role_index.md`, `report_schema.md` and the four primers. This is what
   criteria R6 and R3 watch for, and it is the only way to learn that a
   position is scoped to its period and that a fold takes the later instant.
2. Run the shipped build on the shipped extract and keep its output. It is the
   baseline every later comparison is made against.
3. Reproduce the worked reference slice with the shipped build. Several stage
   figures will disagree, and each disagreement names the stage to read next.
   Criterion R1 watches this.
4. Read the engine function by function against the stage it implements, and
   write down each departure with the function and the stage. Criterion R3
   watches this, and it is the only way to catch the four faults the shipped
   extract hides.
5. Repair the identity walk and the authority reads first, because every later
   stage consumes them.
6. Repair stage 3 and stage 4, then confirm the reference slice selection and
   cap figures reproduce exactly.
7. Repair stage 5, stage 6 and stage 7, building a small extract of the agent's
   own that carries a variant cycle, a fold reading and a pair of movements
   exactly the minimum headway apart. Criterion R2 watches the fold probe.
8. Repair stage 9 and the JSON writer, then run the tool twice and diff the two
   output sets, which criterion R5 watches.
9. Confirm the build on extracts it has never seen before calling it done.
   Generate a few of the agent's own, vary the knobs the shipped documents
   describe, and compile each one. The held-out tier carries 61.5 percent of the
   test channel, so a build that only reproduces this period scores far below one
   that generalises.

## Pitfalls

- Repairing only what the shipped extract reveals. The five faults this period
  hides stay in place, and every hidden check behind them fails while
  `shipped_extract_compiles_exactly` goes green.
- Keeping the flattened candidate list and only renaming the loop. Fails
  `set_positions_select_inside_each_period` and every later stage.
- Repairing the positive positions and leaving the negative index one place
  early. Fails `positions_below_zero_count_from_the_period_end`, which no
  shipped figure would have caught.
- Leaving the window clip in front of the cap. Fails
  `the_cap_counts_from_the_rule_anchor` and `the_cap_counts_after_the_exclusions`.
- Treating a short month as a clamp onto its last day. Fails
  `month_day_rules_select_nothing_in_short_months`.
- Starting an ISO week period at the anchor rather than at the Monday of the
  anchor's week. Fails `iso_week_periods_use_the_week_numbering_year`.
- Applying an addition that collides with an exclusion. Fails
  `exclusions_outrank_additions_on_one_date`.
- Reading the issue stamp before the priority on a variant edge. Fails
  `variant_precedence_follows_priority_then_stamp`.
- Taking the edges in register order rather than base depth order. Same check,
  because a three deep chain resolves differently.
- Leaving a variant cycle running. Fails
  `supersession_chains_resolve_and_cycles_are_rejected`.
- Subtracting the offset that applies after a gap transition. Fails
  `gap_departures_shift_forward_by_the_gap`.
- Taking the first of the two fold instants. Fails
  `fold_departures_take_the_later_offset`.
- Measuring a midnight crossing against the UTC date. Fails
  `midnight_crossings_keep_the_service_date`.
- Walking the alias map one hop. Fails
  `canonical_path_form_merges_wire_spellings` and
  `alias_chains_resolve_and_cycles_are_rejected`.
- Reporting no cycle members. Same second check.
- Treating a gap equal to the minimum headway as a conflict. Fails
  `a_gap_equal_to_the_minimum_headway_clears`.
- Dropping the rank weight and the priority from the walk order. Fails
  `the_admission_walk_follows_the_canonical_order` and
  `movements_that_never_clear_are_withheld`.
- Reading the proposed transition table. Fails
  `superseded_sources_change_no_compiled_figure` and every stage 6 check.
- Applying the proposed mailbox revision. Fails
  `approved_mailbox_headway_revision_is_applied`.
- Packing the calendar bits highest first. Fails
  `canonical_calendars_encode_the_admitted_days`.
- Leaving the JSON keys unsorted or the trailing newline off. Fails
  `declared_outputs_are_present_and_canonical`.
- Hardcoding this extract's digest after computing it once. Fires
  `negative_hardcoded_sample_answers` and fails every
  `unseen_extract_NN_compiles_exactly` check.
- Reading `/app/wtt` from inside the delivered tool rather than its first
  argument. Fires `negative_reads_training_corpus_at_runtime`.
- Leaving a scratch module beside the engine whose name shadows a standard
  library import. Fires `negative_rebinds_verifier_dependencies`.
- Writing a scratch file beside the output directory. Fires
  `negative_writes_outside_the_argument_directories`.
- Iterating a set without sorting it. Fires `negative_nondeterministic_output`.
- Keying any behaviour on the input directory's name. Fires
  `negative_filename_dependent_behaviour`.
- Counting a divergence over a row only one of the two files carries, or naming
  the policy file rather than the mailbox for the headway field. Fails
  `authority_resolution_names_the_sources_of_record`.
- Recording a deferral as a step count rather than as minutes, or trying the
  counts in any order but ascending. Fails
  `the_deferral_ladder_stops_at_the_first_clearing_step`.
- Rendering a rollup with its own header, its own ordering or a quoted field.
  Fails `rollups_and_the_digest_are_exact`.

## Provenance

```yaml
uuid: 7c787cba-5282-55f9-99f4-896d5cc0e007
instance_id: 7c787cba-5282-55f9-99f4-896d5cc0e007
task_name: terminal-bench/7c787cba-5282-55f9-99f4-896d5cc0e007
fix_patch_sha256: ea2124f7c4f76b9dd0ec46445c3fe608ef11a8cd2ae31e1f771fd68c399b5e75
solve_py_sha256: 09bfad8587b8f5bc2c43135ceeb055bd89c86389efbda31cab2bf0fe6a0848ca
language: python
```
