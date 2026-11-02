# TRUTH.md - emberforge-vault-settlement

## Defect

The season ships complete but unsettled. Every rule that governs it is written
down in full across seven rulebooks, the invariants, the finding codes, the
convention register and the record shapes. What the documents never do is put
the rules that meet on one entry in one place. The conventions the guild
council draws for a council year are published only as a register of
candidates and a set of rulings, worked single cases that pin the draw without
settling any season. The delivered program has to recover the draw for every
season it is pointed at, because every season it is graded on is published
under a draw of its own, and nothing shipped confirms a settled season.

1. (focal) LV-EF-1. A forge can be refused by the charge cap and by the vault
   floor at once. A4 judges the cap on the charge the forge would carry if it
   settled, and N3 says every forge past the four gates is tested against the
   cap, the floor and every retired reagent alike, so the forge carries both
   findings and still closes its workshop. The composition is stated only by
   scope: N3's "every other forge" sentence. Testing the floor first and
   stopping there leaves the workshop open and every later forge of it settles.
2. (focal) LV-EF-2. A reagent the registry retires from a patch refuses every
   later forge whose edition calls for it (V9), beside the cap and the floor and
   never instead of them; a credited salvage still returns it; where an edition
   calls for two retired reagents the detail names the first in ascending
   order.
3. (focal) LV-EF-3. Under the `consumed` scarcity reference the index is read
   against the units called for by every forge the season tests against the
   floor, settled or not (the register and N3).
4. (focal) LV-EF-5, the decoy. S2 credits a salvage only against forges settled
   on days strictly before the salvage's own day. `clerks_digest.md`, which the
   instruction marks as subordinate to the rulebooks, says "the three most
   recent forges ... that the vault settled", which agrees with S2 except when
   a forge of the same smith and family settles earlier on the salvage's own
   day. The shipped season shows that boundary once (L0306 to L0310: L0310
   salvages L0306 on day 40, after L0309 settled on day 40); every graded
   season carries it. Reading the digest turns the salvage away, which moves
   the returns, the vault, the floor and everything after.
5. (focal) LV-EF-4. The requisition plan maximises granted units under Q2 to Q6
   and breaks ties by Q8, for up to 48 requisitions within 38 seconds on 2
   CPUs. In the graded ladder seasons the Q5 limit is the closing balance of a
   held reagent, so the plan sits downstream of every lever above.
6. (drift) Smith identity is a function of the day as well as the handle, and
   retirement attaches to the canonical identity (I2 to I4).
7. (trap) A salvage is governed by the edition in force on the day of the forge
   it salvages (E3); a forge is credited to one salvage at most, and a refused
   repeat is not tested against the window (S6).

The reference implementation is Python 3 using only the standard library, with
integer arithmetic throughout. It is written independently of the grader: the
verifier carries its own settlement engine and its own requisition search, and
the two agree only because both are right. Two grading channels score the run:
the weighted checks registered in `tests/test_output.py`, and the judged
criteria in `tests/judge.toml`.

Out of bounds: hardcoding this season's figures is caught by
`negative_hardcoded_sample_answers`; hardcoding this season's draw earns
nothing, because no positive check settles a season under it. Reading the
grader at run time is closed by construction: grading drops to an unprivileged
account that cannot open `/tests`. The season is synthetic, so no write-up of it
exists to be found, and the instruction forbids looking for one.

## Load-bearing work

Twelve artifacts are declared and all twelve are graded.

- `/app/out/settle_vault.py`: the settlement program. Every value check runs a
  grader-staged readable copy of it on a season the grader builds.
- `/app/out/summary.json`, `/app/out/vault_audit.json`,
  `/app/out/reconciliation.json`, `/app/out/data_quality.json`,
  `/app/out/allocation.json`, `/app/out/workshop_cinderhall.json`,
  `/app/out/workshop_gloamworks.json`, `/app/out/workshop_slagmoor.json`,
  `/app/out/workshop_verdigris.json`, `/app/out/guild_ashen_compact.json`,
  `/app/out/guild_tidebound_league.json`: the settled season the agent
  received, read for presence and written form; the same eleven record shapes
  are compared value for value on every reseeded season.

The fields, order and written form of every record are stated in
`record_shapes.md`. `council_rulings.json` holds two charge, two return and two
scarcity rulings; together they leave exactly one of the 840 register draws
(RS-C, half-even, GFS, opening-plus-acquired for the shipped season), and none
of them is a figure of any season.

## Verification

`tests/test.sh` runs `rewardkit /tests --workspace /app --output
/logs/verifier/reward.json`. `tests/test_output.py` registers 33 checks:
27 positive checks whose weights total **101**, and six negative checks
totalling -14. `tests/reward.toml` gives each channel half the reward.

| checks | weight each | season and what it grades |
|---|---|---|
| `structure_program_delivered`, `structure_records_delivered`, `structure_program_takes_directories`, `structure_canonical_serialisation`, `structure_findings_canonical_form` | 1 | presence, arguments, written form and key order, finding order |
| `closure_mix_{settlement,findings_and_workshops,guilds_and_allocation}` | 5 | LV-EF-1, LV-EF-2 (retired pair), LV-EF-5 |
| `consumed_cap_mix_{...}` | 5 | LV-EF-3, LV-EF-1, LV-EF-5 |
| `consumed_retired_mix_{...}` | 5 | LV-EF-3, LV-EF-2, LV-EF-5 |
| `plan48_mix_{...}` | 5 | LV-EF-4 (48 requisitions), LV-EF-2, LV-EF-5 |
| `plan24_mix_{...}` | 5 | LV-EF-4 (24 requisitions, one workshop filing a second), LV-EF-3 with early closures, LV-EF-5 |
| `requisitions_12_allocation` | 3 | Q1 to Q8 on 12 requisitions, nothing else |
| `priority_tie_allocation`, `cap_boundary_workshop_figures`, `partition_guild_reports`, `temporal_boundary_vault_audit`, `merge_chain_smith_rows`, `quiet_rules_findings` | 3 | one documented rule each |

Each `*_settlement` check compares the summary, the vault audit and the
per-patch reconciliation together; `*_findings_and_workshops` compares the
finding record and every workshop report; `*_guilds_and_allocation` compares
every guild report and the allocation. The 15 mixed checks carry 75 of the 101
points; the 12 single-rule and structure checks carry 26 (25.7 percent). The
isolated-rule seasons have four requisitions, except cl_partition (two) and
cl_quiet (five).

Negative checks, each inverted so that it holds only when the cheat is present:
`negative_hardcoded_sample_answers` (-3) replays this season's summary on
another corpus; `negative_filename_dependent_behaviour` (-1) settles one corpus
differently under another directory name; `negative_nondeterministic_output`
(-1) disagrees with itself; `negative_reads_training_corpus_at_runtime` (-1)
follows `/app/data` when pointed elsewhere; `negative_rebinds_verifier_dependencies`
(-5) plants an import hook; `negative_imports_outside_standard_library` (-3)
finds a top-level import outside `sys.stdlib_module_names` in the program. The
five run-based negatives stand down when the program does not run cleanly. All
six fail against an honest solution.

Grading executes agent-written code, so the verifier is hardened for it: the
image installs `util-linux` and creates an unprivileged `sandbox` account;
`test.sh` clears stale reward files, locks `/logs/verifier` and closes `/tests`;
every run copies the program into a fresh grader-made folder at mode 0644 and
runs that copy through `setpriv` in a new process group with a 38 second limit,
then kills the group and everything the sandbox account still owns.

The judge channel is `tests/judge.toml`: twelve criteria, nine positive
summing to 23 and three negative summing to -11. R1 to R5 and R12 are single
figures of the season the agent received that the instruction asks the final
message to state and that no file holds as that quantity: total charge 130027,
35 credited salvages, closing balances R04 176, R11 76 and R05 270, and
54 units granted. R6 to R8 judge the code, one fact each. R9 and R10 are the
stated rules of engagement; R11 fires on a claimed check the trajectory never
ran.

## Root cause

**Composition, not omission.** Every rule is stated. The cap, the floor and a
retired reagent are each stated where they belong; that one forge is tested
against all three is stated by N3's scope sentence and A4's "judged on the
charge a forge would carry". The consumed reference is stated in the register
and bounded by N3. The window is stated in S2; the digest that blurs it is
marked subordinate by the instruction.

**Coupling.** Scarcity, charge, cap and consumption form a cycle; a closure that
happens or fails to happen changes every later entry of the workshop; a
credited salvage changes the vault; the vault's closing balance limits the
plan; the guild reports roll the workshops up. A slip at one entry moves every
record of the season, and every mixed check compares whole documents.

**No confirming oracle.** The rulings decide the draw case by case and settle
nothing, and the identities an agent can check (conservation, agreement of
totals, finding tallies) hold under every wrong reading above.

**Red lines.** No graded quantity depends on the network, the clock, or any
file outside the corpus a run is pointed at. Every point lost is a record that
differs from the settled season.

## Solution shape

`solution/solve.py` is an independent implementation written from the
documents.

1. `Corpus` loads a season's nine tables and two documents. `Calendar`,
   `Roster` and `RecipeBook` resolve days, canonical identity and governing
   editions; V9's retirement days are read from the registry.
2. `recover` tests each of the 840 register draws against every ruling in
   `council_rulings.json` and keeps the one that agrees with all of them.
3. `Settlement._sweep` walks the ledger in day then entry order. `_forge`
   judges the cap on the charge the forge would carry, then the floor, then
   every retired reagent, records every condition that holds, and closes the
   workshop when the cap is passed whatever else refuses the forge. The draw a
   forge calls for is counted before those tests, which is the `consumed`
   reference. A salvage is refused as a repeat before the window is read, and
   the window holds settled forges from days strictly before the salvage.
4. `Settlement.stable` climbs to the scarcity fixed point from the ceiling and
   from zero and requires both to agree.
5. `Requests.best_total` is a branch and bound over charter groups with guild,
   vault and pool bounds; `fund` takes its maximum (Q7) and then fixes each
   requisition in Q8 order at the largest grant that still reaches it.
6. `compile_records` assembles the records and `write` emits them in the form
   `record_shapes.md` states.

## Ordered plan

1. Read every document under `/app/data`, including `record_shapes.md` and the
   register's account of the rulings.
2. Recover the draw from the rulings.
3. Judge every forge against the cap, the floor and every retired reagent
   together, and close a workshop whenever the cap is passed.
4. Read S2 for the window, not the digest: settled forges of the smith and
   family from days strictly before the salvage.
5. Count the `consumed` reference over the forges the season tests against the
   floor.
6. Solve the plan with a bounded search, so 48 requisitions settle well inside
   the time limit.
7. Settle the season, write the eleven records, and report the total charge,
   the credited salvages, the closing balance of each scarce reagent and the
   units granted.

## Pitfalls

- Testing the floor or a retired reagent before the cap and stopping at the
  first refusal; fails closure_mix and consumed_cap_mix whole.
- Treating a retired reagent as an early refusal, holding back its returns, or
  naming the last of two retired reagents; fails the closure, consumed_retired
  and plan48 documents.
- Counting only settled forges, or every forge with an edition, in the
  `consumed` reference; fails consumed_cap_mix, consumed_retired_mix and
  plan24_mix whole.
- Counting a same-day settled forge in the credit window, as the digest reads;
  fails every mixed check and moves the shipped season's credited salvages and
  R04 balance.
- Keeping one requisition's grant per workshop instead of the sum over its
  requisitions; fails the plan24_mix workshop and guild checks.
- Searching every plan exhaustively; runs past the time limit on 24 and 48
  requisitions.
- Hardcoding this season's draw; every graded season uses another.
- Writing records with another indent, without the trailing newline or with
  keys in another order; fails `structure_canonical_serialisation`.
- Refusing a forge that lands exactly on its cap, or leaving out a workshop
  opened on the first day or closed on the last day; fails
  `cap_boundary_workshop_figures` or `quiet_rules_findings`.

## Provenance

```yaml
uuid: 9c54291e-e724-4d52-a44b-b3faad128884
instance_id: emberforge-vault-settlement
task_name: terminal-bench/emberforge-vault-settlement
solve_py_sha256: 76db9c400747879397ae7fc615ac9b591dfd8da7e0e8e56892fdfc21852fa57b
test_output_sha256: 7446ace5e3e2bb9a0a0ad87e0573b8fb879008f7a14b7df3e6b46368b865589d
language: python
```
