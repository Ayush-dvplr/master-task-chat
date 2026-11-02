# TRUTH.md - emberforge-vault-settlement

## Defect

The season ships complete but unsettled. Every rule that governs it is written
down in full across seven rulebooks, the invariants and their terms, the
finding codes, the convention register and the record shapes. The conventions
the guild council draws for a council year are published only as a register of
candidates and a set of rulings, worked single cases that pin the draw without
settling any season. The delivered program has to recover the draw for every
season it is pointed at, because every graded season is published under a draw
of its own, and nothing shipped confirms a settled season.

Three rules carry this round's levers. Each is stated once, in the file that
governs its data, with no example in which the two readings differ.

1. (focal) L7, per-item unit. Charge is reduced per unit. H1 makes the base
   value of a forge the artifact's base charge; H5 applies the three operators
   to that base value, each reduced to a whole number, and multiplies the last
   result by the units the entry forges. The reflex reading multiplies by the
   units first and reduces the total, which moves almost every multi-unit
   forge's charge, so every charge figure, every cap closure near the line,
   and through them the vault, the findings and the plan.
2. (focal) L3, ordered ledger. The cap ledger is released by credited salvages.
   A4 sets the default: a workshop accrues settled charge and closes when a
   forge would carry it above the tier cap. S5, in the salvage rulebook, says a
   credited salvage takes its source forge's charge out of that accrued charge
   for every forge settled after it, while the charge stays in every reported
   charge figure. Reading A4 alone closes workshops too early; the workshop
   charge can end above its cap with `cap_reached` false. The shipped season
   shows this in verdigris (42960 ember against a 38000 cap).
3. (focal) L6, scope by definition. The credit window counts live forge
   entries. S2 reads "the last three live forge entries of the same artifact
   family settled for the same canonical smith on days strictly before the
   salvage's own day"; `invariants.md` defines a live forge entry under Terms
   as a settled forge entry no salvage has yet been credited against. The loud
   parts of S2 (strictly before, the canonical smith, one window per family)
   cover the older same-day trap. Counting every settled forge pushes a source
   out of the window when an already credited forge of the same smith and
   family sits among the last three.

4. (drift) The draw moves with the season. Every graded season is published
   under its own draw from the register, so the program recovers the draw from
   that season's `council_rulings.json` instead of carrying one draw.
5. (trap) `clerks_digest.md` restates three rules loosely (same-day stock,
   the salvage window, cap closure); the rulebooks govern over it.

Rules carried from earlier rounds and still graded inside every whole document:
the cap, the floor and a retired reagent are tested on the same forge (A4, V4,
V9, N3); the `consumed` scarcity reference counts every forge tested against
the floor (register, N3); the window is strictly before the salvage's day (S2;
`clerks_digest.md` is subordinate and blurs it); the plan maximises units under
Q2 to Q6 with Q8 ties for up to 48 requisitions inside 38 seconds; identity is
a function of the day (I2 to I4); a salvage is governed by its source forge's
edition (E3); one salvage per forge (S6).

The reference implementation is Python 3 using only the standard library, with
integer arithmetic throughout. It is written independently of the grader: the
verifier carries its own settlement engine and its own requisition search, and
the two agree only because both are right. Two grading channels score the run:
the weighted checks registered in `tests/test_output.py`, and the judged
criteria in `tests/judge.toml`.

Out of bounds: hardcoding this season's figures is caught by
`negative_hardcoded_sample_answers`; hardcoding this season's draw earns
nothing, because no positive value check settles a season under it. Reading
the grader at run time is closed by construction: grading drops to an
unprivileged account that cannot open `/tests`. The season is synthetic, so no
write-up of it exists to be found, and the instruction forbids looking for one.

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
  received, read for presence and written form; the same record shapes are
  compared value for value on every reseeded season.

The fields, order and written form of every record are stated in
`record_shapes.md`. `council_rulings.json` holds two charge, two return and two
scarcity rulings; together they leave exactly one of the 840 register draws
(RS-C, half-even, GFS, opening-plus-acquired for the shipped season), and none
of them is a figure of any season. A charge ruling's base value is one unit's
base charge, so the rulings agree with H1 and H5 under either reading of the
units and decide nothing about the L7 lever.

Shipped season, settled: 166 entries admitted, 144 rejected, 37 credited
salvages, 33 uncredited, season charge 135879 ember, 54 units granted, closing
balances R04 176, R05 270, R11 68, conservation residual 0.

## Verification

`tests/test.sh` runs `rewardkit /tests --workspace /app --output
/logs/verifier/reward.json`. `tests/test_output.py` registers 20 checks:
16 positive checks whose weights total **54**, and four negative checks
totalling -8. `tests/reward.toml` gives each channel half the reward.

| checks | weight each | what it grades |
|---|---|---|
| `whole_summary`, `whole_vault_audit`, `whole_reconciliation`, `whole_data_quality`, `whole_allocation`, `whole_workshop_reports`, `whole_guild_reports` | 5 | one output document each, compared whole on four reseeded hidden seasons (forge_a to forge_d); credit is the share of seasons matched |
| `unit_charge_season_total` | 3 | L7: season charge on an open season (no cap, no floor in reach) |
| `cap_release_closures` | 3 | L3: CAP_REACHED findings on a season whose tier cap sits between the released and unreleased peaks |
| `live_window_refusals` | 3 | L6: UNCREDITED_SALVAGE findings on an open season carrying a credited forge inside a later window |
| `mutation_family_multiplier`, `mutation_grade_step` | 3 | one charter constant changed: the charge ledger moves to the settled value and vault_audit.json stays identical to the unchanged run |
| `structure_program_delivered`, `structure_program_takes_directories` | 1 | the program exists and takes its data and output directories (shipped season) |
| `structure_canonical_serialisation`, `structure_reruns_byte_identical` | 1 | on forge_a: every record in the written form and key order of `record_shapes.md`, and a second run writes the same bytes (N8) |

Shares of the 54 positive points: whole documents on hidden seasons 35 (64.8
percent), isolated rule checks 15 (27.8 percent), structure 4 (7.4 percent, of
which shipped-only 1 point, 1.9 percent, and program presence 1 point). Every
check that fails writes a `check note:` line naming the season and the document
that differed, so the reason reaches the ctrf record.

Each hidden season carries every lever: forge_a (RS-C, half-up, FSG, opening,
16 requisitions), forge_b (RS-E, ceil, SFG, consumed, 24), forge_c (RS-G,
ceil, FSG, consumed, 32), forge_d (RS-G, ceil, SFG, opening, 48). Each has caps
set near the workshops' charge, a planted live-window block, the same-day
window block, a retired reagent and a held reagent whose closing balance binds
the plan, so a misreading of any lever changes all seven documents.

Negative checks, each inverted so that it holds only when the cheat is present:
`negative_hardcoded_sample_answers` (-3) replays this season's summary on
another corpus; `negative_filename_dependent_behaviour` (-1) settles one corpus
differently under another directory name; `negative_reads_training_corpus_at_runtime`
(-1) follows `/app/data` when pointed elsewhere; `negative_rebinds_verifier_dependencies`
(-3) plants an import hook. The run-based negatives stand down when the
program does not run cleanly. All four fail against an honest solution.

Grading executes agent-written code, so the verifier is hardened for it: the
image installs `util-linux` and creates an unprivileged `sandbox` account;
`test.sh` clears stale reward files, locks `/logs/verifier` and closes `/tests`;
every run copies the program into a fresh grader-made folder at mode 0644 and
runs that copy through `setpriv` in a new process group with a 38 second limit,
then kills the group and everything the sandbox account still owns.

The judge channel is `tests/judge.toml`, batched: eight criteria, four
positive summing to 12 and four negative summing to -10. R1 to R3 are conduct
criteria, one per lever: the agent builds its own season carrying the case and
checks the observable the lever moves. R4 is one named code shape (no except
clause that discards an error and carries on). R5 (writes under `/app/data`,
-1), R6 (network or online lookup, -3), R7 (claims a check passed against its
own output, -3) and R8 (reads grader files, -3) are the negatives. Penalties by
act across both channels: replaying the shipped season 5, editing outside
scope 4, network 3, honesty 3, reading the grader 3.

## Root cause

**Composition, not omission.** Every rule is stated once, where its data is
governed. The per-unit reduction is in H1 and H5; the cap release is in S5, an
exception to A4 in another rulebook; the live window is a term S2 uses and the
invariants define.

**Coupling.** Scarcity, charge, cap and consumption form a cycle; a closure
that happens or fails to happen changes every later entry of the workshop; a
credited salvage changes the vault and the cap ledger; the vault's closing
balance limits the plan; the guild reports roll the workshops up.

**No confirming oracle.** The rulings decide the draw and settle nothing, and
the identities an agent can check (conservation, agreement of totals, finding
tallies) hold under every wrong reading above.

**Red lines.** No graded quantity depends on the network, the clock, or any
file outside the corpus a run is pointed at.

## Solution shape

`solution/solve.py` is an independent implementation written from the
documents.

1. `Corpus` loads a season's tables and documents. `Calendar`, `Roster` and
   `RecipeBook` resolve days, canonical identity and governing editions.
2. `recover` tests each of the 840 register draws against every ruling in
   `council_rulings.json` and keeps the one that agrees with all of them.
3. `Settlement._charge` applies the operators to the artifact's base charge,
   reducing at each, and multiplies by the units.
4. `Settlement._sweep` walks the ledger in day then entry order. `_forge`
   judges the cap on accrued less released charge plus the forge's charge,
   then the floor, then every retired reagent, and records every condition
   that holds. `_salvage` refuses repeats, reads the window over live forges
   from days strictly before the salvage, and on credit adds the source
   forge's charge to its workshop's released ledger.
5. `Settlement.stable` climbs to the scarcity fixed point from the ceiling and
   from zero and requires both to agree.
6. `Requests.best_total` is a branch and bound over charter groups; `fund`
   takes its maximum (Q7) and fixes each requisition in Q8 order.
7. `compile_records` assembles the records and `write` emits them.

## Ordered plan

1. Read every document under `/app/data`, including the Terms of
   `invariants.md` and `record_shapes.md`.
2. Recover the draw from the rulings.
3. Charge each forge per unit, then multiply by its units.
4. Keep the cap ledger in settlement order, releasing a source forge's charge
   when a salvage of it is credited.
5. Read the credit window over live forges only.
6. Settle, solve the plan with a bounded search, and write the eleven records.

## Pitfalls

- Multiplying by units before the operators; fails every whole document and
  `unit_charge_season_total` and both mutation checks.
- Accruing charge without the S5 release; fails every whole document and
  `cap_release_closures`.
- Counting credited forges in the window; fails every whole document and
  `live_window_refusals`.
- Hardcoding this season's draw or figures; every graded season uses another.
- Writing records with another indent, without the trailing newline or with
  keys in another order; fails `structure_canonical_serialisation`.

## Provenance

```yaml
uuid: 9c54291e-e724-4d52-a44b-b3faad128884
instance_id: emberforge-vault-settlement
task_name: terminal-bench/emberforge-vault-settlement
solve_py_sha256: 58ec3992788e5574b9601f414bf0e28894b5672b945bcd738e077478e06722d8
test_output_sha256: 53303c696525df67334f54a668c3934bc92df3c676e062de1115099f33fdae09
language: python
```
