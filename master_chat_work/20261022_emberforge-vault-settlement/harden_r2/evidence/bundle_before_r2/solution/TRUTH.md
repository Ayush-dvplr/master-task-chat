# TRUTH.md - emberforge-vault-settlement

## Defect

The season ships complete but unsettled. Every rule that governs it is written
down in full across seven rulebooks, the invariants, the finding codes, the
convention register and the record shapes. What the documents never do is put
the rules that meet on one entry in one place. Four conventions the guild
council draws for a council year are published only as a register of
candidates; the slice the council published pins the draw, and the delivered
program has to find it again for every season it is pointed at, because every
season it is graded on is published under a draw of its own.

1. (focal) LV-EF-1. A forge can be refused by the charge cap and by the vault
   floor at once. A4 judges the cap on the charge the forge would carry, so the
   forge carries both findings and still closes its workshop; N3 says an entry
   carries a finding for every condition that holds of it. The rules sit in
   three files. Testing the floor first and stopping there records one finding
   and leaves the workshop open, so every later forge of that workshop settles
   and the whole season drifts. Owned by the `cap_and_floor_*` checks.
2. (focal) LV-EF-2. A reagent the registry retires from a patch refuses every
   later forge whose edition calls for it (V9). The refusal is a condition of the
   forge beside the cap and the floor, never instead of them, and retirement
   stops draws only: a credited salvage still returns a retired reagent. Treating
   retirement as an early refusal skips the cap, so a bulk order that the
   retired reagent and the cap both refuse never closes its workshop. Owned by
   the `retired_reagent_*` checks.
3. (focal) LV-EF-3. Under the `consumed` scarcity reference the index is read
   against the units called for by every forge the season tests against the
   floor. Forges at a closed workshop count; forges refused for scope, standing
   or an unresolved edition do not, as the register and N3 state. Counting every
   forge that resolves an edition moves every index, every charge and every
   closure. Owned by the `consumed_reference_*` checks.
4. (focal) LV-EF-4. The requisition plan maximises granted units under Q2 to Q6
   and breaks ties by Q8. A season can hold up to 48 requisitions and must
   settle within 38 seconds on 2 CPUs. Exhaustive search over grants
   passes 12 requisitions and cannot finish 24 or 48; the plan needs a bounded
   search that walks Q8 order. Owned by the `requisitions_*_allocation` checks.
5. (drift) Smith identity is a function of the day as well as the handle, and
   retirement attaches to the canonical identity (I2 to I4). Owned by
   `merge_chain_smith_rows`.
6. (trap) A salvage is governed by the edition in force on the day of the forge
   it salvages (E3), and a forge is credited to one salvage at most (S6). The
   published slice exercises both, so a wrong reading of either finds no draw
   and the program settles nothing.

The reference implementation is Python 3 using only the standard library, with
integer arithmetic throughout. It is written independently of the grader: the
verifier carries its own settlement engine and its own requisition search, and
the two agree only because both are right. Two grading channels score the run: the weighted checks
registered in `tests/test_output.py`, and the judged criteria in
`tests/judge.toml`.

Out of bounds: hardcoding this season's figures is caught by
`negative_hardcoded_sample_answers`; hardcoding this season's draw earns
nothing, because no positive check settles a season under it. Reading the
grader at run time is closed by construction: grading drops to an unprivileged
account that cannot open `/tests`. The season is synthetic, so no write-up of it
exists to be found, and the instruction forbids looking for one.

## Load-bearing work

Twelve artifacts are declared and all twelve are graded.

- `/app/out/settle_vault.py`: the settlement program. Every value check runs it
  on a season the grader builds.
- `/app/out/summary.json`, `/app/out/vault_audit.json`,
  `/app/out/reconciliation.json`, `/app/out/data_quality.json`,
  `/app/out/allocation.json`, `/app/out/workshop_cinderhall.json`,
  `/app/out/workshop_gloamworks.json`, `/app/out/workshop_slagmoor.json`,
  `/app/out/workshop_verdigris.json`, `/app/out/guild_ashen_compact.json`,
  `/app/out/guild_tidebound_league.json`: the settled season the agent
  received, read for presence and written form; the same eleven record shapes
  are compared value for value on every reseeded season.

The fields, order and written form of every record are stated in
`record_shapes.md`. The calibration slice publishes its summary
(`calibration_controls.json`) and, for one workshop, the units its salvages
returned (`example_workshop_report.json`); that is the least publication that
leaves exactly one of the 840 draws, and nothing else the slice settled ships.

## Verification

`tests/test.sh` runs `rewardkit /tests --workspace /app --output
/logs/verifier/reward.json`. `tests/test_output.py` registers 50 checks:
45 positive checks whose weights total **155**, and five
negative checks totalling -7. `tests/reward.toml` gives each channel half the
reward.

Ownership map (each reseeded season exercises one lever and no other):

| checks | weight each | season and lever |
|---|---|---|
| `structure_program_delivered`, `structure_records_delivered`, `structure_program_takes_directories`, `structure_canonical_serialisation`, `structure_findings_canonical_form` | 1 | presence, arguments, written form, finding order |
| `cap_and_floor_{one,two}_{findings,workshop_figures}` | 5 | LV-EF-1 |
| `cap_and_floor_{one,two}_{vault_audit,reconciliation,guild_reports}` | 3 | LV-EF-1 |
| `retired_reagent_{one,two}_{findings,workshop_figures}` | 5 | LV-EF-2 |
| `retired_reagent_{one,two}_{vault_audit,reconciliation,guild_reports}` | 3 | LV-EF-2 |
| `consumed_reference_{one,two}_{findings,workshop_figures}` | 5 | LV-EF-3 |
| `consumed_reference_{one,two}_{vault_audit,reconciliation,guild_reports}` | 3 | LV-EF-3 |
| `requisitions_12_allocation` | 3 | LV-EF-4, the rung exhaustive search still passes |
| `requisitions_24_allocation`, `requisitions_48_first_allocation`, `requisitions_48_second_allocation` | 5 | LV-EF-4 |
| `priority_tie_allocation`, `cap_boundary_workshop_figures`, `partition_guild_reports`, `temporal_boundary_vault_audit`, `merge_chain_smith_rows`, `quiet_rules_findings` | 3 | one documented rule each, no composition lever present |

Every reseeded season keeps the levers it does not own out of reach: V4 by
abundant stock or A4 by caps no workshop reaches, no retired reagent, a
reference other than `consumed`, and four requisitions. Downstream records are
therefore graded on seasons whose upstream stages carry no other lever.

Negative checks, each inverted so that it holds only when the cheat is present:
`negative_hardcoded_sample_answers` (-3) replays this season's summary on
another corpus; `negative_filename_dependent_behaviour` (-1) settles one corpus
differently under another directory name; `negative_nondeterministic_output`
(-1) disagrees with itself; `negative_reads_training_corpus_at_runtime` (-1)
follows `/app/data` when pointed elsewhere; `negative_rebinds_verifier_dependencies`
(-1) plants an import hook. All five fail against an honest solution.

Grading executes agent-written code, so the verifier is hardened for it: the
image installs `util-linux` and creates an unprivileged `sandbox` account;
`test.sh` clears stale reward files, locks `/logs/verifier` and closes `/tests`;
every agent subprocess runs through `setpriv` in a fresh process group with a
38 second limit and is killed with everything the sandbox account
still owns.

The judge channel is `tests/judge.toml`: nine criteria, five positive summing to
19 and four negative summing to -14. R1 to R4 are facts the instruction asks the
final message to state about the season the agent received, which no test reads:
the four conventions, the total charge, the entry that closed each capped
workshop, and the forges that carry more than one finding. R5 judges the code.
R6 to R8 are the stated rules of engagement; R9 fires on a claimed check the
trajectory never ran.

## Root cause

**Composition, not omission.** Every rule is stated. The cap, the floor and a
retired reagent are each stated where they belong; that they are judged on one
forge together is stated in A4, V9 and N3, three files apart. The consumed
reference is stated in the register and bounded by N3. The plan's size bound and
time limit are stated in the instruction.

**Coupling.** Scarcity, charge, cap and consumption form a cycle; a closure that
happens or fails to happen changes every later entry of the workshop; the
vault's closing balance limits the plan; the guild reports roll the workshops
up. A slip at one forge moves every record of the season.

**Hidden composition.** The published slice raises neither the cap and floor
together nor a retired reagent, and it is published under a reference other than
`consumed`, so a program can reproduce the slice exactly and still read each of
these compositions wrongly. Only reseeded seasons tell them apart.

**Red lines.** No graded quantity depends on the network, the clock, or any
file outside the corpus a run is pointed at. Every point lost is a record that
differs from the settled season.

## Solution shape

`solution/solve.py` is an independent implementation written from the
documents.

1. `Corpus` loads a season's nine tables and two documents, and the same
   eleven records prefixed `calibration_` for the slice. `Calendar`, `Roster` and
   `RecipeBook` resolve days, canonical identity and governing editions; V9's
   retirement days are read from the registry.
2. `recover` settles the slice under each of the 840 draws and keeps the one
   whose summary equals `calibration_controls.json` and whose returned units for
   the published workshop equal `example_workshop_report.json`.
3. `Settlement._sweep` walks the ledger in day then entry order. `_forge` judges
   the cap on the charge the forge would carry, then the floor, then a retired
   reagent, records every condition that holds, and closes the workshop when the
   cap is passed whatever else refuses the forge. The draw a forge calls for is
   counted before any of those tests, which is the `consumed` reference.
4. `Settlement.stable` climbs to the scarcity fixed point from the ceiling and
   from zero and requires both to agree.
5. `Requests.best_total` is a branch and bound over charter groups with guild,
   vault and pool bounds; `fund` takes its maximum (Q7) and then fixes each
   requisition in Q8 order at the largest grant that still reaches it.
6. `compile_records` assembles the records and `write` emits them in the form
   `record_shapes.md` states.

## Ordered plan

1. Read every document under `/app/data`, including `record_shapes.md`.
2. Build the engine against the slice and recover the draw by exhaustive search
   over the register.
3. Judge every forge against the cap, the floor and a retired reagent together,
   and close a workshop whenever the cap is passed.
4. Count the `consumed` reference over the forges the season tests against the
   floor.
5. Solve the plan with a bounded search, so 48 requisitions settle well inside
   the time limit.
6. Settle the season, write the eleven records, and report in the final message
   the four conventions, the total charge, the closing entry of each capped
   workshop and every forge with more than one finding.

## Pitfalls

- Testing the floor before the cap and stopping at the first refusal; fails the
  `cap_and_floor_*` checks.
- Treating a retired reagent as an early refusal, or holding back the returns of
  a retired reagent; fails the `retired_reagent_*` checks.
- Counting every forge with an edition, only settled forges, or no forge at a
  closed workshop in the `consumed` reference; fails the `consumed_reference_*`
  checks.
- Searching every plan exhaustively; passes `requisitions_12_allocation` and
  runs past the time limit on 24 and 48 requisitions.
- Governing a salvage by its own filing day, or crediting a forge twice; the
  slice then admits no draw and nothing settles.
- Hardcoding this season's draw; every graded season uses another.
- Writing records with another indent or without the trailing newline; fails
  `structure_canonical_serialisation`.

## Provenance

```yaml
uuid: 9c54291e-e724-4d52-a44b-b3faad128884
instance_id: emberforge-vault-settlement
task_name: terminal-bench/emberforge-vault-settlement
solve_py_sha256: 043fa52706174134f09173ba0e6d5b54e654fa2131bd2a8c282a0c72f5701df8
test_output_sha256: 13dfb9f9570404ec5141685f01bf77e5fbb010250beba9bc45de2518ac81d916
language: python
```
