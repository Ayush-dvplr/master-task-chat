# TRUTH.md - b51a883e-3d78-5df9-b860-69399620a53a

## Defect

The studio's replay tool cannot reconstruct season 5 matches accurately. The
agent must build a deterministic, standard library engine, not patch a supplied
implementation. Its only authorities are the rule book, the seven errata and the
input tables, in that order of increasing precedence.

The difficult part is recovery of historical corrections, not just playing
one forward timeline. Section 16 defines compare-and-swap amendments against
immutable original order slots. Deletion leaves an addressable tombstone;
restoration, issuer changes, lag changes and applied no-ops advance revisions.
Unknown units take precedence over stale revisions. Malformed corrections do
not open the correction tail. Closed and unclosed matches have different
accounting boundaries.

Every applied revision requires a before/after audit of the full match. Absolute
keyframes remain unchanged, so corrected state can converge at a later keyframe
while earlier draw, damage and kill credits remain different. Correcting only
the final orders or restoring only the board cannot produce the required audit.

The forward engine still needs format 2 coordinate conversion, unbiased rejected
dice samples, per-turn reseeding after keyframe adoption, wounded initiative,
numeric tie breaks, lag resolution, terrain and ZOC, once-per-turn reactions,
line of sight, capped flank, shield walls, advantage before armour, poison,
rout, objective scoring and the file-ordered rating ladder.

## Load-bearing work

The agent submits one self-contained `/app/out/optimize.py`, invoked as
`python3 optimize.py <data_dir> <out_dir>`, plus the nine reports produced by
running it once on `/app/data`. Report schemas are in section 13 and section 16.

- Five scenario reports contain metadata, every turn digest, final results,
  standings and accepted revision audit lists.
- `perf_report.json` separates original transport order counts from late and
  superseded orders in the final corrected histories.
- `bottleneck_analysis.json` counts final-history generator steps by phase,
  including rejected samples, without counting replay attempts twice.
- `recommendations.json` aggregates deployments once and corrected direct
  damage and kill credits over all five exports.
- `data_quality.json` distinguishes malformed lines, unknown original orders,
  final keyframe divergences and applied/stale/unknown amendments.

Each audit records immutable addresses, the new revision, two full-timeline
FNV-1a fingerprints, changed ordinal digest indices, signed phase/damage/kill
deltas and both complete divergence histories. All unit types appear in delta
maps even when their value is zero. An accepted no-op still emits an entry.

Inputs in a different directory contain only the six machine-readable tables
and five logs, not the prose specifications. No result, match id or digest may
be hardcoded. File names select labels, not rules. Inputs are read-only, output
is confined to the argument directory, and every run must finish in 300 seconds.

## Verification

`tests/test.sh` is the sole scoring entrypoint. It clears stale rewards, locks
verifier-owned directories and invokes rewardkit once. The independent verifier
constructs fresh corpora without reading the agent's `/app/data`, stages a
readable copy of the submitted engine, drops to nobody, and runs with a 300 second
timeout with no new privileges. It kills the process group, checks for writes
outside out_dir, seals finished outputs, and reruns under different hash seeds
and renamed twin logs. A failed corpus build is cached and reported once, so
every criterion returns false instead of rebuilding.

There are 35 deterministic criteria: 30 positive with total weight 136, and
five inverted negative criteria with total magnitude 19. Channel weights are
`0.5 / 136` and `0.5 / 19`; each channel's criteria use weighted sums.

Eight recovery observables carry 40 positive points. One wrong audit field
fails exactly one of them:

- `eval_recovered_history`: final corrected digest vectors.
- `eval_revision_addresses`: accepted sequence, immutable addresses, revisions.
- `eval_revision_fingerprints`: before and after full-history fingerprints.
  The last entry's `after` fingerprint is a hash of the final digest vector,
  so it is compared only where that match's final digests are right; a wrong
  final vector is paid once, by `eval_recovered_history`.
- `eval_revision_changed_indices`: ordinal changed-index lists.
- `eval_revision_draw_credits`: signed per-phase draw adjustments.
- `eval_revision_damage_credits`: signed direct damage adjustments.
- `eval_revision_kill_credits`: signed direct kill adjustments.
- `eval_revision_divergence_histories`: before and after divergence histories.
  The last entry's `divergences_after` equals the match's final divergence
  list, so it is compared only where that list is right; a wrong final list is
  paid once, by `lever_keyframe_divergences`.

The remaining core criteria cover baseline and keyframe adoption, coordinates,
lag, dice rejection, reseeding, initiative order, movement, shield walls, line of
sight, status effects, objectives, final result, combat, turn flow and ladder.
For unamended matches the verifier independently switches individual rules to
plausible incorrect readings. Reached-state evidence attributes digest errors
to their rule pool rather than charging every downstream turn again. Amended
matches are evaluated separately; they cannot stand in for rule-pool evidence.
Final divergence lists are checked exactly, for both rulesets and in file order.
The evaluation corpus also places a discarded unknown unit order before every
third keyframe of the matches without a correction tail in the four
full-grammar exports, so the section 6.3 rule that such an order does not block
a later `K` in its block is exercised. An engine that rejects those keyframes as
malformed loses the baseline, final divergence, quality count, phase total and
balance criteria (19/136); the recovery audit criteria are left untouched.
Each rule-pool criterion reads one pool. A pool owns every naive variant of its
rule family (initiative owns side alternation and numeric tie breaks, movement
owns zone of control, status owns rout, the baseline owns keyframe adoption,
combat owns armour order and turn flow owns reactions), and it pays only when
none of its variants is charged and each part of the family was observed on a
reached digest. The format 2 origin pool also requires a right digest after
turn 0 that the flip variant touches, so a deployment-only digest cannot pay it.

One weight-1 criterion ties the shipped reports to the submitted engine: the
verifier rebuilds the shipped exports, runs the engine into an output directory
that does not exist yet, and requires each of the nine reports under /app/out to
hold the same JSON value as that run, with its top level section non-empty. Five weight-3 criteria cover important
sub-goals: match metadata and per-match keys, phase totals, balance totals,
quality counts and performance counters. The phase totals criterion includes
the section 13.3 dominant phase rule on a twin export whose burst log holds only
evaluation matches with `attack == damage > reaction` and whose latency log
holds only evaluation matches with `damage == reaction > attack`, so the
alphabetically first phase must win in both shapes; an engine that resolves ties
by last or highest name, by a fixed phase preference or by reversed order fails
it. All six together are 16/136 of the tests channel, so they cannot by
themselves produce a passing implementation. Missing or malformed reports return false rather than raising.
JSON comparisons preserve types and list order.

Five negative criteria detect wrong-corpus ids, filename-dependent behavior,
nonstandard engine imports (import statements and `__import__` or
`import_module` calls with a literal module name), nondeterministic bytes and
writes outside out_dir.
Shipped and decoy ids share one detector so the same input-directory violation
does not stack two penalties.

The judged channel has 13 criteria, nine positive totaling 19 and four negative
totaling 12. R1 requires the section 14 demo digest vector to be checked on code
identical to the final engine; R2 requires values from all nine reports of the
last /app/data run to be printed after that run; R3 judges whether every
section 16.3 history version is a full replay from freshly built state, without
rescoring output values; R4 grades the instruction rule that every table number,
unit type and terrain symbol is read from `<data_dir>`, which the tests cannot
see because evaluation tables equal the shipped ones. R12 judges error handling
in the engine (specific exception types, no handler that hides an error) and R13
judges that each game rule is written once, so copies of a rule cannot drift.
R6-R8 inspect the requested final note. R5 covers helper imports, R9 immutable
inputs, R10 package installs, and R11 note claims that no output of the final
engine code supports, including checks last run before a later engine edit. An
import of a package that the same command tries to install is charged once,
under R10, so one act never costs more than 3 judged points.
These observables are distinct from deterministic output checks.

The reference entrypoint reads both prose authorities, installs the engine at
`/app/out/optimize.py` and runs it on `/app/data`, then loads that installed
file to run the book's section 14 demo and compare the printed digest vector,
prints values from all nine generated reports, and writes a note that names the
engine path and its recovery mechanisms and states the keyframe divergence
counts and the demo outcome read from that final run. Verification of outputs
does not establish a judged score for an agent trajectory.

## Root cause

Sparse checkpoint intervals and correction tails require reconstruction across
long histories. A checkpoint repairs board
state, but cannot supply overwritten historical credits or intermediate audits.
Replaying only final slot contents misses deletion/restoration history, while
naively accumulating every replay overcounts damage, kills, draws and deployments.

All recovery obligations are agent-visible in section 16. The season 4 values printed
in the book remain explicitly superseded by the season 5 errata and JSON tables.
Two table precedence traps are live in graded data: errata E-7 prices the
outrider at 5 points while `units.json` keeps 4, and the book's printed roster
prices the crossbow at 6 while `units.json` keeps 5. The JSON table wins in both
cases (instruction, errata header and book introduction all say so); the cost
feeds match scores and `per_cost_permille`.
No hidden convention or verifier-only constant is required to solve the task.

## Solution shape

`solution/solve.py` is intentionally one file because the delivery contract is
one self-contained engine. Its parser retains original slot lists and accepted
amendment records. `recover_match` maintains per-slot revisions, tombstones and
the currently resolved timeline, replaying from deployment after every applied
change. Each replay owns fresh board state and cumulative credits. Consecutive
complete replays yield the audit; only the final replay feeds ordinary reports.

The verifier uses a separate tuple-based parser, simulation and sparse override
map, reconstructing resolved turns independently for each version. It does not
import, execute or derive expected answers from the oracle implementation.
Generated fixtures are inputs, never precomputed graded report answers.

## Ordered plan

1. Read report schemas, precedence rules and the recovery address model.
2. Implement strict parsing and preserve original known-roster slots before
   lag resolution; distinguish syntax counters from closed-match decisions.
3. Implement dice, coordinates and digests; verify the book's worked examples.
4. Implement turn phases, combat and keyframe comparison/adoption in order.
5. Add revision checks, tombstones and replay-owned credits. Check deletion,
   restoration, stale/unknown precedence, no-ops and keyframe convergence.
6. Derive intermediate audits and corrected aggregate reports independently.
7. Run the engine on the inputs, inspect reports and provide the requested note.

## Pitfalls

- Renumbering slots after DROP changes later addresses.
- Checking revisions before roster membership misclassifies unknown/stale ties.
- Resolving lag once before amendments prevents a newly exposed order acting.
- Double-flipping replacement MOVE coordinates corrupts format 2 recovery.
- Resetting credits at K loses prefix effects even if final state converges.
- Rewriting K from a corrected prefix hides required divergence changes.
- Using only the last digest cannot fingerprint a complete history.
- Letting a discarded unknown unit order block the block's `K` rejects a valid
  keyframe and loses its adoption and divergence.
- Treating no-ops as ignored amendments produces wrong revisions and list length.
- Counting amendments as ordinary transport orders corrupts performance counts.
- Including an unclosed match's amendment decisions corrupts quality counts.
- Caching mutable marks or counters across replays leaks poison/reaction state.
- Taking the outrider cost from E-7 or the crossbow cost from the printed
  roster instead of `units.json` breaks scores and balance verdicts.
- Resolving a dominant phase tie by the last or highest name, or by a fixed
  phase preference, breaks the bottleneck report.
- String-sorting ids, dropping rejected draws, or using printed stale values
  still breaks the underlying game engine.

## Provenance

```yaml
uuid: b51a883e-3d78-5df9-b860-69399620a53a
instance_id: b51a883e-3d78-5df9-b860-69399620a53a
task_name: terminal-bench/b51a883e-3d78-5df9-b860-69399620a53a
language: python
solve_py_sha256: 9539df03358508995a2b3ced2880ac4d1f3f782d8088c6a41e8aafb9a5584e6e
```
