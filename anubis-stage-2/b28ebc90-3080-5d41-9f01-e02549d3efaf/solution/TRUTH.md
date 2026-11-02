# TRUTH.md - b28ebc90-3080-5d41-9f01-e02549d3efaf

## Defect

The `daybreak` package under `environment/data/project.zip` is a complete
fourteen stage routing chain with twenty four catalogued departures from
the stage specifications and reading rules shipped beside it. Each
departure is a short reading a careful engineer plausibly writes, and
each one changes the published bytes of every corpus. Nothing is redacted:
every rule the grader exercises is written out in `environment/data`, one
paper per stage, plus the ten recording rules the registers are written
under, the reading rules for the working papers in the serialisation
contract, worked arithmetic examples and the full output schema. The two
reading aids (`readings_not_in_force.md`, `known_traps_and_footguns.md`)
are not answer keys: the first lists fifteen wrong readings of which only
two (DFC-01, DFC-08) are carried by the shipped source, and the second
names places in the data, never a rule or a module. The agent has to find the departures, repair the shipped
source at each anchor, deliver the repaired tree as an archive and drive
it over the working papers to publish the twenty eight derived documents
plus four repair records.

1. (focal) **DFC-01** `loading.live_rows` accepts every revision of a key and keeps the greatest, so the frozen revision named in `cycle_header.json` settles nothing. Defeats `stage_intake_exact`, `stage_policy_exact`, `shipped_intake_documents_exact` and every minted family.
2. (focal) **DFC-03** `stages.window_grid` reads each window's `start_delta_value` as an absolute start, so the RR6 delta chain is discarded and every window lands in the wrong place. Defeats `stage_intake_exact` and `shipped_intake_documents_exact`.
3. (focal) **DFC-07** `stages.demand_of` carries the first product unrounded into the second, so the stage r09 demand has one rounding point rather than the two the arithmetic policy places. Defeats `stage_binding_exact`, `stage_reconciliation_exact` and `shipped_binding_documents_exact`.
4. (focal) **DFC-10** `allocate.stage_r12` offers each reconciliation round to the proposed fallbacks alone rather than to the current holders and that round's proposals together, so no incumbent is ever overturned and the locally correct r10 allocation is never revisited. Defeats `stage_reconciliation_exact` and `shipped_reconciliation_documents_exact`.
5. (focal) **DFC-13** `loading.read_workbook` takes the first grid it meets as live. The workbook carries four grids of one shape: `grid_draft` first (key cell the cycle key in lower case), `grid_alpha` and `grid_beta` (one live, one `-SUPERSEDED`), and `grid_current` last (key cell the cycle key with a trailing space). A fix that strips or folds case before matching, or keeps the last match, still binds a decoy. Defeats `stage_loading_exact` and `shipped_binding_documents_exact`.
6. (drift) **DFC-09** `allocate._select` breaks out of the discretionary queue at the first candidate that does not fit, which is the instinct a packing loop teaches and which the binding policy forbids in one sentence. Defeats `stage_binding_exact` and `shipped_binding_documents_exact`.
7. (drift) **DFC-14** `stages._routine_cap` consults the routine layer before the memo cap table, which is the instinct a seven layer precedence stack teaches, and which the expansion policy overrides. Defeats `stage_intake_exact` and `shipped_intake_documents_exact`.
8. (drift) **DFC-12** `stages.stage_r07` ranks the removable cycle edge by the dependent's tier before the edge strength, which is the instinct a precedence task teaches and which part B of the directive contradicts. Defeats `stage_graph_exact` and `shipped_graph_documents_exact`.
9. (trap) **DFC-02** `stages._absent` treats a written zero as an absent field, which is invisible until a layer records an explicit zero. Defeats `stage_intake_exact` and `shipped_policy_documents_exact`.
10. (trap) **DFC-04** `stages.stage_r03` matches a trigger on a window end into that window. Only the boundary occurrences differ. Defeats `stage_intake_exact` and `shipped_intake_documents_exact`.
11. (trap) **DFC-05** `stages.resolve_policy` lets a one shot override apply at its expiry instant. One override in the shipped cycle expires exactly on a trigger. Defeats `stage_policy_exact` and `shipped_policy_documents_exact`.
12. (trap) **DFC-06** `stages._layer_records` reads the journal's own `remaining` field rather than the snapshot count, which agrees for every override whose two records agree. The shipped function never reads `state_snapshot.json.oneshot_remaining` at all (no unused lookup is left behind as a hint); the repair has to bring the snapshot in. Defeats `stage_policy_exact` and `shipped_policy_documents_exact`.
13. (trap) **DFC-08** `allocate._select` displaces a demand exactly equal to the pool. Only the exact fits differ, including a zero demand in a zero ceiling window. Defeats `stage_binding_exact` and `shipped_binding_documents_exact`.
14. (trap) **DFC-11** `publish.render` decrements the one shot counts from the first state pass rather than the pass over the survivors of r14, so consumption is settled a stage too early: every corpus carries a one shot settled instance (AC-175 under OV-902) that r14 closes by gate, so the first pass spends an override the survivors never did. Defeats `shipped_state_documents_exact`, `shipped_publication_documents_exact` and the reconciliation stage check.
15. (focal) **DFC-15** `stages.context_grid` starts the context delta chain at zero rather than at `origin_ms`. `origin_ms` is non zero on every corpus (18 to 42 minutes), so every context span shifts. Defeats `stage_intake_exact`, the policy families and every minted family.
16. (focal) **DFC-16** `stages.cooldown_floors` reads the class floors at `cycle_header.json.frozen_revision_window_grid` instead of `state_snapshot.json.frozen_revision_cooldown_register`. The two differ on every corpus (the cooldown register freezes at 4 to 9, the window grid at 15 or more), and the register carries a revision 13 row in the live token `stroke` whose denominator is zero, above every frozen revision, so the wrong reading picks it up. The class floor changes r04 cooldowns, which changes the r05 COOLDOWN set: r01 units, r04 floors and r05 eligibility are chained. Defeats `stage_policy_exact` and the policy, graph and binding families.
17. (focal) **DFC-17** `stages.window_grid` reads every window at the header's global `frozen_revision_window_grid` rather than at its own `window_frozen_revisions` entry. W01, W02 and W07 to W09 freeze at the global value, the rest lower, and non frozen revisions record a different start difference, so W03 to W06 and W10 to W12 move. Defeats `stage_intake_exact` and every family.
18. (drift) **DFC-18** `publish.run_chain` builds the r07 dependent tier over every r03 expanded instance rather than the r05 eligible ones. AC-178 carries a COOLDOWN instance at tier 2 in W04 beside its eligible tier 5 instance, and the cycle AC-177/AC-178 has two edges of equal strength 3300; the correct reading settles it on the third key (declared sequence), the wrong one on the second. The cycles AC-211 to AC-213 and AC-214 with AC-215 (all strengths tied) remove a different edge under the wrong reading. The stage harness computes its own tier index, so `stage_graph_exact` is untouched; the graph, binding and publication families on every corpus are defeated.
19. (trap) **DFC-19** `publish.render` takes the last ledger row per device as the prior consumption rather than the greatest cycle index. `energy_ledger_history.ndjson` stores each device's rows rotated, so the last row is rarely the latest cycle. Defeats `shipped_publication_documents_exact`, the publication families and the reconciliation stage check.
20. (trap) **DFC-20** `allocate.stage_r14` subtracts a kept fallback proposal's demand from the pool twice. The relay fixture (DV-16, W09) leaves a readmission candidate (AC-174) that fits the pool only when the proposal (AC-173) is drawn once. Defeats `stage_reconciliation_exact`, `stage_r14_challenge_exact` and the reconciliation, state and publication families.
21. (trap) **DFC-21** `util.read_text` decodes as plain UTF-8, so the byte order mark that opens `alias_crosswalk.tsv` becomes part of the first header field (`\ufeffalias`). The shipped reader hands that header back as it is and `stage_r02` reads each row's alias with `row.get("alias", "")`, skipping rows without one, so the chain does not raise: every crosswalk alias silently drops out of the pool and the alias decisions change. The serialisation contract states the mark is not part of the paper. Defeats `stage_loading_exact` and every family downstream of r02.
22. (trap) **DFC-22** `util.read_delim` splits records on `"\n"` and fields on the separator without honouring double quoted fields. `source_priority_register.csv` quotes the role of the supplement source (`"supplement, secondary"`), so the plain split shifts its status column and the supplement source silently drops out of force; `cooldown_register.psv` is written with CRLF line ends, so the carriage return stays on the last field (`floor_unit`), every class floor becomes unconvertible and the r04 class floors and r05 cooldowns move. The reference decodes bytes without newline translation, so the CR reaches the reader and the reading rule is load bearing. Defeats `stage_loading_exact` and the intake, policy and publication families.
23. (drift) **DFC-23** `stages.resolve_policy` consults the layers in the order the package was written with (mandatory, oneshot, context, device, action, routine, global) instead of the rank order of part A of `precedence_directive.docx`. The directive ranks the action layer 4 and the device layer 5 on the shipped cycle, and permutes the device, action and routine layers differently (never the written order) on every minted cycle, so the hardcoded order is a real departure that only reading the docx exposes. `config_resolution.json.layer_ranks` publishes the directive's ranks. No layer paper carries a rank of its own, and the r04 paper and the glossary name the layers without numbering them. Defeats `stage_policy_exact`, `stage_reconciliation_exact` (r11 resolves the synthetic fallbacks) and every family.
24. (focal) **DFC-24** `allocate.stage_r12` runs with a hardcoded `cap = 2` rounds instead of part C of the directive, which states 3 rounds on the shipped cycle and 4 or 5 on the minted ones (the memo records no round cap). Reconciliation is multi round: r10 is round one; each later round offers the current holders of a window and device together with that round's proposals to the r10 pool start; an r10 holder losing its place is overturned in that round and, if the round is not the last, consults its own fallback chain under the r11 rules (candidates proposed earlier stay taken) for the next round's proposals. The cascade fixture (AC-191 to AC-198 on DV-16 in W11) is built so that every extra round changes the outcome: caps 2, 3, 4 and 5 all publish different reconciliation documents. Defeats `stage_reconciliation_exact`, `stage_r12_challenge_exact` and the publication families.

The multi hop dependency the relay fixture builds runs r10 to r14: AC-171
is displaced in r10, its fallback AC-173 is proposed in r11 and kept in r12
by overturning the incumbent AC-172; AC-173's state effect writes
`gate_42 = on` and AC-172's would write `off`; AC-174, suppressed in r05,
is readmitted in r14 only when the gate is on and the pool holds it. With
DFC-10 the incumbent survives, the gate closes, and the readmission count
and next state cooldowns change.

Two further reading traps carry no defect of their own and are settled by
the stage papers alone: two alias rings, `ring.a1..a8` of exactly the hop
cap (a cycle, hops 0) and `ring.b1..b9` one longer (the cap is used up
first, each name resolves to the name reached after eight hops), and a
workbook pair recording `0` (a ceiling of zero) beside a pair recording
`-` (absent, displaced under `UNKNOWN_CEILING`), with two ceilings in
`microwh` that half even round 0.5 to 0 and 2.5 to 2. A dense knot of nine
actions (AC-181 to AC-189, every ordered pair joined by a soft edge of
distinct strength) makes r07 settle some fifty cycles in sequence.
`cooldown_register.psv` is written with CRLF line ends, which the reading
rules cover and which DFC-22 breaks.

The r07 paper and `cycle_break_policy.toml` state one reading of
`key_settled_at`: the ordinal of the first key whose values are not all
equal across every edge of the cycle, 4 when the first three tie. It is a
property of the cycle, not of the removed edge. The fixed four cycle
AC-031 to AC-034 (every strength 2600, dependent tiers 5, 5, 2, 1) tells
the two readings apart deliberately: the cycle reading settles at 2, the
removed edge reading at 3. It is removed in round 7 on the shipped cycle
and round 3 on the eval and challenge cycles. Two further cycles carry
edges that share one declared sequence and one strength between actions
with no instance (AC-205 to AC-207, and AC-208 with AC-209), so key 4,
the text comparison, settles them; the declared sequence is not unique and
r06 keeps such rows. Two all strength tie cycles (AC-211 to AC-213 and
AC-214 with AC-215) are decided by the dependent tier over the eligible
instances: AC-212 carries a tier 2 instance withheld under COOLDOWN and
AC-215's only instance is SUPPRESSED (so its tier is the global tier), and
the reading over every expanded instance removes a different edge.

The readmission fixture (AC-201 to AC-204 on DV-16 in W12) gives r14
three candidates gated on one key written by AC-201: AC-202 and AC-204 are
readmitted, and AC-203, between them in instance order, no longer fits the
pool AC-202 drew. With the relay's AC-174 the shipped cycle readmits
three instances.

The reference implementation is Python 3.12, standard library only, exact
rational arithmetic throughout. Grading runs on two channels that read
different observables. Channel A is `tests/test_output.py`: it grades the
bytes of every document, the shape of the delivered archive, the behaviour
of the delivered package on three cycles minted from seeds the agent never
sees (each with its own cycle key, origin, frozen revisions and decoy
grids), each delivered stage function fed the reference records of the
stages before it, the defect register against the departures the shipped
source actually carries, and the figures in the verification notes
against the reference documents. Channel B is `tests/judge.toml`: it grades how the agent
read the papers and checked its own results in the trajectory, and the
facts it reports in the final response. No judged criterion asks for a
value or a repair a test already grades.

Out of bounds: a delivered package that replays the shipped cycle's
documents whatever cycle it is pointed at is caught by
`negative_hardcoded_sample_answers` together with the nine minted
families, while a package that raises on a minted cycle is a chain with a
bug and is charged by those families alone; a package that reads the fixed
path /app/data in place of the directory it is handed is caught by
`negative_reads_fixed_paper_directory`, which plants a decoy cycle there
for one run and compares, and the replay detector stands down on it;
keying behaviour on the directory name is caught by
`negative_filename_dependent_behaviour`; a chain that varies between runs
is caught by `negative_nondeterministic_output`; writing into the paper
directory is caught by `negative_package_edits_its_paper_directory`;
digests that do not describe the bytes beside them are caught by
`negative_manifest_digest_mismatch`; dropping a module or a shipped test
file is caught by `delivered_package_shape`; smuggling a startup hook or a
standard library shadow into the delivered archive is caught by
`negative_rebinds_verifier_dependencies`; and importing a module that has
to be installed is caught by `negative_third_party_import`. Over fixing is
charged by `defect_register_matches_departures`: a register row naming a
shipped function that carries no departure fails it, as does a missing
departure or a wrong stage identifier. A wrong reading
of a paper is never charged by a negative; the positive families and the
stage checks withhold its weight.

## Load-bearing work

The graded artifacts, as declared in `task.toml`:

- `/app/out/package.zip`
- `/app/out/build_report.json`
- `/app/out/selftest.json`
- `/app/out/defect_register.md`
- `/app/out/verification_notes.md`
- `/app/out/unit_normalization.json`
- `/app/out/alias_resolution.jsonl`
- `/app/out/expansion_ledger.csv`
- `/app/out/config_resolution.json`
- `/app/out/parameter_audit.csv`
- `/app/out/trigger_eligibility_index.json`
- `/app/out/dependency_graph.json`
- `/app/out/cycle_break_ledger.json`
- `/app/out/canonical_action_order.json`
- `/app/out/resource_demand.csv`
- `/app/out/window_capacity_report.csv`
- `/app/out/initial_allocation.json`
- `/app/out/displaced_action_queue.json`
- `/app/out/fallback_expansion.json`
- `/app/out/precedence_reconciliation.json`
- `/app/out/final_action_order.json`
- `/app/out/cooldown_state.csv`
- `/app/out/derived_state.json`
- `/app/out/suppression_ledger.csv`
- `/app/out/next_state_snapshot.json`
- `/app/out/per_context_manifest.json`
- `/app/out/per_device_manifest.csv`
- `/app/out/daily_automation_manifest.json`
- `/app/out/resource_utilization_report.csv`
- `/app/out/terminal_action_report.md`
- `/app/out/audit_ledger.jsonl`
- `/app/out/run_manifest.txt`
- `/app/out/summary.json`

Content contract, per family.

- **Intake** (`unit_normalization.json`, `alias_resolution.jsonl`,
  `expansion_ledger.csv`) records every unit token seen, the base totals,
  the quantities that could not be carried, every alias binding decision
  with its status, and one row per generated occurrence and per routine
  withheld before it generates any.
- **Policy** (`config_resolution.json`, `parameter_audit.csv`,
  `trigger_eligibility_index.json`) records the layer that settled each of
  the seven fields for each instance, the live device policy revisions,
  the class floors, and the eligible and withheld instances by reason.
- **Graph** (`dependency_graph.json`, `cycle_break_ledger.json`,
  `canonical_action_order.json`) records the kept and dropped edges, one
  entry per cycle removal naming the key that settled it, the action order
  and the instance order.
- **Binding** (`resource_demand.csv`, `window_capacity_report.csv`,
  `initial_allocation.json`, `displaced_action_queue.json`) records the
  two demand products, the ceiling, reserve, mandatory draw, allocation
  and remaining pool per window and device, and the displaced queue.
- **Reconciliation** (`fallback_expansion.json`,
  `precedence_reconciliation.json`, `final_action_order.json`) records the
  proposals, the second round per group and the instances it overturned,
  and the surviving order.
- **State** (`cooldown_state.csv`, `derived_state.json`,
  `suppression_ledger.csv`, `next_state_snapshot.json`) records the
  cooldowns, the derived keys with the instance that wrote each, every
  set aside with the stage that did it (the fallback terminals of r11 and
  r12 both under `r12`), and the carried state including
  the one shot counts left unspent.
- **Publication** (the manifests, the utilisation report, the terminal
  report, the audit ledger, `run_manifest.txt`, `summary.json`) records
  the plan by context, device, circuit and window, and both digests.
- **Repair records** (`build_report.json`, `selftest.json`,
  `defect_register.md`, `verification_notes.md`) record what was repaired,
  the shipped suite run and the checks the solver made. These are graded
  structurally, never byte for byte.

The `UNKNOWN_CEILING` branch is reached on every corpus by the absent
sentinel cell (W05, DV-06) in the live grid, and on the three minted ones
also by a dropped ceiling row (`_fixtures`). The r10 paper and the output
schema state both halves of the branch: the group is displaced under
`UNKNOWN_CEILING` and writes no capacity row, and the utilisation report
sums an absent cell as zero.

The minted corpora also freeze some devices at a revision for which
`device_policies.csv` carries no row, so the row in force under RR1 sits
one revision lower. `config_resolution.json` publishes that live row's
revision under `live_device_policy_revisions`, as the output schema
states; a solver that publishes the frozen revision from
`cycle_header.json` instead agrees on the shipped cycle and loses the
minted families.

The minted corpora differ from the shipped one in more than their figures.
Each has its own cycle key (HB-2042-257, HB-2036-357, HB-2043-252 for the
eval, challenge and probe seeds), its own `frozen_revision_cooldown_register`
(9, 5, 8 against 4 on the shipped cycle), its own permutation of the
device, action and routine ranks in directive part A and a round cap of 4
or 5 (the three graded seeds draw 4). The workbook's five sheets are
permuted with the live grid never first (`sheetperm`), and the rows of
`window_grid.csv`, `device_register.csv`, `device_policies.csv`,
`cooldown_register.psv` and `dependency_edges.tsv` arrive shuffled
(`_minted_shuffle`). Each minted cycle also carries two new ties: a decoy
row for `devices[2]` in `device_register.csv` and one for `devices[3]` in
`device_policies.csv`, each at that device's frozen revision and placed
ahead of the row in force (`_tied_before`). RR1 settles a key and revision
tie on the later row. A reader that keeps the first of two equal revisions
matches the shipped cycle, which has no such tie, and changes 9 to 21
documents on every minted cycle. The shipped corpus stays in id order and
has none of these features, so passing it shows nothing about order.

Every corpus, the shipped one included, also carries the equality
fixtures from `_boundary_fixtures`: a cooldown that elapses exactly at the
trigger (AC-161, eligible), a hard prerequisite firing at the same instant
as its dependent (AC-163 before AC-162, satisfied in r08 and in r14), a gate
key written at the gated trigger itself (AC-165 against AC-164, the gate
stays open) and a readmission key written at the withheld trigger itself
(AC-167 against AC-166, no readmission), plus a routine triggering
exactly on the end of W02, which overlaps W03 by twenty minutes (W03 takes
it under the half open rule), and the one shot OV-007 expiring exactly on
RT-004's trigger. Flipping any one of those
boundaries changes between 9 and 18 published documents on every cycle.

Out of bounds by design: the verifier never reads `/app/data`. It remints
its own corpus from `SAMPLE_SEED` for the shipped cycle and from three
further seeds for the minted cycles, so no graded value depends on the
directory the agent was handed.

## Verification

`tests/test.sh` clears any stale reward file, locks `/logs/verifier`, makes
`/tests` unreadable to the sandbox user and hands over to
`rewardkit /tests --workspace /app`. rewardkit scores two inputs and
`tests/reward.toml` combines them, each counting for half:
`weights = { test_output = 0.5 / 132, judge = 0.5 / 55 }`. Every positive
passing and no negative firing reads 1.0; doing nothing reads 0.0.

The oracle locates each of the twenty four departures and writes the
repair from the stage paper in its own form (DFC-22 with `csv.reader`
rather than the reference's own field splitter, DFC-17 through
`per_window.get`, DFC-20 by skipping instances r09 never bound), so the
repaired modules differ textually from the reference this verifier holds; the published
documents agree byte for byte on all four corpora. Where a rule admits one
edit only (DFC-11, DFC-12, DFC-14) the edit is that one. The papers state
the r02 decision fields, the r03 ledger rows, the r10 capacity rows, the
stage named for a fallback terminal and the r13 consumption rule the way
the graded chain behaves, and the r13 paper states that consumption never
changes `remaining` within the cycle. Measured on the test channel, a
delivery written to the opposite reading of the r02 fields or of the r13
rule loses several families.

Every check that drives agent code holds one shared lock and sweeps the
sandbox user's processes before it returns, so nothing the delivery forks
outlives the check that started it. The corpora a graded reference is taken
from are read only to the sandbox user; every run of the delivered package
works on its own writable copy, so the score never depends on the order
rewardkit runs the checks in.

The stage checks feed each delivered stage function, on the probe cycle,
the reference records of the stages before it and compare its return value
with the reference stage's. Each delivered stage runs in its own sandboxed
process that receives its arguments on stdin and nothing else: the
reference source stays in a directory the sandbox user cannot read, r02's
resolver is rebuilt by the harness rather than passed as reference code,
and no later stage's record is in reach. One stage left unrepaired
therefore costs that stage's check and the documents downstream of it, and
keeps the rest: measured on the test channel, a delivery repairing
twenty three of the twenty four anchors (with the oracle's repair records
left in place) scores between 44 and 107 of 132 (DFC-02 lowest, DFC-19
highest; DFC-23 53, DFC-24 94), against 15 for the shipped package
delivered unrepaired beside complete repair records and 132 for the
oracle. Five single stage checks (r03, r07, r10, r12, r14) repeat
the stage harness on the challenge cycle, so a stage repaired for the
probe cycle's data alone is still caught.

The defect register is parsed as a table whose header names `stage` and
`function` columns. Each real departure is the set of top level functions
the reference anchor spans up to its last non-blank line (so DFC-22 accepts
`util.read_delim` or the reference's helper `util._split_fields`); a
function the delivered module adds is accepted in their place only when one
of the departure's own functions calls it. Each departure must be booked in
a row of its own (a function carrying two departures, `allocate._select`
with DFC-08 and DFC-09, `publish.render` with DFC-11 and DFC-19,
`stages.window_grid` with DFC-03 and DFC-17, takes two rows) under exactly
one stage, and every remaining row must not name a shipped function.
DFC-22 breaks two separately stated reading rules of
`serialisation_and_digest_contract.md`, the quoted field (first met at r02
in `source_priority_register.csv`) and the carriage return (first met at
r04 in `cooldown_register.psv`), so, following "a function that departs
from two rules takes two rows", it must be booked once under r02 and once
more under r04 (`DEFECT_SECOND_RULE_STAGES`); a lone r02 row, a lone r04
row, two r02 rows or a third row all fail. The
stage column is scored strictly against one stage per departure
(`DEFECT_STAGES`), following the rule the instruction states: the stage
whose paper states the rule; for a helper several stages call, the
earliest stage in chain order whose result the departure changes; for a
reader every paper passes through, the first stage that reads a paper
carrying the trap by the paper to stage map in `data_lineage.md`. The
stages are DFC-01 r02, 02 r03, 03 r02, 04 r03, 05 r04, 06 r04, 07 r09,
08 r10, 09 r10, 10 r12, 11 r13, 12 r07, 13 r10, 14 r03, 15 r02, 16 r04,
17 r02, 18 r07, 19 r14, 20 r14, 21 r02, 22 r02 (and r04 for its second rule), 23 r04, 24 r12. The verification notes must state `last_window_start_ms` and one
`set_aside <REASON> <n>` line for every reason in the reference
`suppression_ledger.csv`, with no extra reason.

Channel A, `tests/test_output.py`, carries 42 rewardkit criteria: 34 positive summing to 132 and 8 negative summing to -28.

Positive criteria:

- `stage_loading_exact` (5)
- `stage_intake_exact` (5)
- `stage_policy_exact` (5)
- `stage_graph_exact` (5)
- `stage_binding_exact` (5)
- `stage_reconciliation_exact` (5)
- `shipped_reconciliation_documents_exact` (5)
- `shipped_state_documents_exact` (5)
- `shipped_publication_documents_exact` (5)
- `package_eval_intake_exact` (5)
- `package_eval_binding_exact` (5)
- `package_eval_publication_exact` (5)
- `package_challenge_intake_exact` (5)
- `package_challenge_binding_exact` (5)
- `package_challenge_publication_exact` (5)
- `package_probe_intake_exact` (5)
- `package_probe_binding_exact` (5)
- `package_probe_publication_exact` (5)
- `defect_register_matches_departures` (5)
- `stage_r03_challenge_exact` (3)
- `stage_r07_challenge_exact` (3)
- `stage_r10_challenge_exact` (3)
- `stage_r12_challenge_exact` (3)
- `stage_r14_challenge_exact` (3)
- `verification_notes_state_figures` (3)
- `shipped_intake_documents_exact` (3)
- `shipped_policy_documents_exact` (3)
- `shipped_graph_documents_exact` (3)
- `shipped_binding_documents_exact` (3)
- `package_runs_from_module_entry_point` (3)
- `all_artifacts_exist` (1)
- `documents_parse_and_conform` (1)
- `repair_records_conform` (1)
- `delivered_package_shape` (1)

Negative criteria:

- `negative_hardcoded_sample_answers` (-5)
- `negative_reads_fixed_paper_directory` (-5)
- `negative_filename_dependent_behaviour` (-3)
- `negative_nondeterministic_output` (-3)
- `negative_package_edits_its_paper_directory` (-3)
- `negative_manifest_digest_mismatch` (-3)
- `negative_rebinds_verifier_dependencies` (-3)
- `negative_third_party_import` (-3)

Channel B, `tests/judge.toml`, carries 29 criteria: 25 positive summing to 55 and 4 negative summing to -12. They read how the agent worked in the trajectory and what it reports in the final response; none asks for a published value or a repair that a test already grades.

- R1 (constraint, trajectory, 1) The agent extracts and reads the contents of all three of capacity_and_intensity_workbook.xlsx, household_operations_memo.pdf and precedence_directive.docx under /app/data.
- R2 (constraint, trajectory, 1) The agent opens /app/data/00_start_here.txt and then /app/data/assistant_program_contract.md before it opens any stage specification paper.
- R3 (constraint, trajectory, 3) The agent applies each repair as a targeted edit to the shipped daybreak module that holds the departure.
- R4 (constraint, trajectory, -3) The agent writes, renames or deletes a working paper under /app/data with an editor or shell command of its own, outside any run of python3 -m daybreak.
- R5 (conduct, trajectory, 1) The agent runs the shipped tests directory of the daybreak package against its repaired source and reads the outcome.
- R6 (conduct, trajectory, 1) The agent opens at least one document that its repaired package published under python3 -m daybreak over /app/data before it declares any repair complete.
- R7 (conduct, trajectory, 1) The agent works out at least two window starts independently of its package, by hand or with a separate computation of its own, from the live rows of /app/data/window_grid.csv and origin_ms in /app/data/cycle_header.json and compares them with the starts its package uses.
- R8 (conduct, trajectory, 1) The agent names at least one register key whose greatest revision exceeds its frozen revision, quotes a field value that differs between the row in force at the frozen revision and the row at the greatest revision, and confirms from a document its package published that the frozen-revision value is the one carried.
- R9 (conduct, trajectory, 3) The agent reproduces at least one row of resource_demand.csv independently of its package, by hand or with a separate computation of its own, from the catalogue energy, the resolved intensity, the class surcharge and the window scale, naming the instance, device and window of that row, and compares the figure with the row its package published.
- R10 (conduct, trajectory, 3) The agent works at least one group of precedence_reconciliation.json independently of its package, by hand or with a separate computation of its own, under /app/data/spec_stage_r12_precedence_overturn.md and compares the kept instances with what its package published.
- R11 (conduct, trajectory, 1) The agent works out independently of its package, by hand or with a separate computation of its own, over oneshot_remaining in /app/data/state_snapshot.json and the instances that survive r14, the count next_state_snapshot.json should carry for at least one one shot override whose instance was withdrawn or overturned after the first state pass, states the snapshot count, the spends and the resulting count, and compares that count with the one its package published.
- R12 (conduct, trajectory, 3) The agent quotes a live row of /app/data/device_policies.csv that leaves a policy cell empty and states both the value that empty cell resolves to and the value a written zero in the same cell would resolve to.
- R13 (conduct, trajectory, 1) The agent finds at least one override whose remaining field in /app/data/override_journal.jsonl differs from its count in /app/data/state_snapshot.json and names both values.
- R14 (conduct, trajectory, 3) The agent checks independently of its package, by hand or with a separate computation of its own, at least one removal in its cycle_break_ledger.json whose key_settled_at is 2, showing that the edge strengths tie and that the resolved tier of the dependent under the part B order of /app/data/precedence_directive.docx settles it.
- R15 (conduct, trajectory, 3) The agent locates in the shipped papers at least one instance whose trigger lands exactly on the instant its cooldown elapses, quotes the sentence of the stage paper that settles it, and compares it with the outcome its package published for that instance.
- R16 (outcome, final_answer, 3) The response states, for each reason code, a count of instances set aside that equals the per reason row count of suppression_ledger.csv from the agent's own last package run as the trajectory shows it.
- R17 (outcome, final_answer, 3) The response names grid_beta as the live workbook grid and HB-2034-231 as the key cell value it was matched on.
- R18 (conduct, final_answer, 1) The response states a start of the last window in milliseconds that equals the last_window_start_ms figure the agent wrote into verification_notes.md in the trajectory.
- R19 (outcome, final_answer, 3) The response lists every repair the agent made, each beside the stage identifier from r01 to r14 that its defect_register.md row names for it.
- R20 (conduct, trajectory, 1) The agent writes each repair to the standard of the surrounding daybreak module code, with names that say what they hold and no debug residue left in.
- R21 (conduct, final_answer, -5) The response states that the repaired package reproduces the papers while the last run of python3 -m daybreak in the trajectory exited with a non-zero status.
- R22 (conduct, trajectory, -1) The agent runs the same failing command unchanged on three or more consecutive turns.
- R23 (constraint, trajectory, -3) The agent writes a float conversion or a float literal into the arithmetic of a repaired daybreak module.
- R24 (conduct, trajectory, 3) The agent works at least one readmission independently of its package, by hand or with a separate computation of its own, under /app/data/spec_stage_r14_feedback_and_publication.md, naming the instance, the remaining pool and the demand it is readmitted against, and compares the result with the READMITTED rows its package published.
- R25 (conduct, trajectory, 3) The agent works out independently of its package, by hand or with a separate computation of its own, the remaining pool of at least one device window that holds a fallback proposal kept at r14, drawing that proposal's demand exactly once, and compares the figure with the pool its package published for that window.
- R26 (conduct, trajectory, 3) The agent traces, independently of its package, at least one instance that r10 allocated, that a round of /app/data/spec_stage_r12_precedence_overturn.md overturns, and whose own fallback is proposed for the next round, and compares each link with the precedence_reconciliation.json its package published.
- R27 (conduct, trajectory, 3) The agent checks independently of its package, by hand or with a separate computation of its own, at least one removal in its cycle_break_ledger.json whose key_settled_at is 3 or 4, showing that every earlier key in the part B order of /app/data/precedence_directive.docx ties among the actions of that cycle.
- R28 (conduct, trajectory, 3) The agent checks independently of its package, by hand or with a separate computation of its own, that the removals its cycle_break_ledger.json records for the largest knot of mutually dependent actions leave no dependency cycle among those actions.
- R29 (conduct, trajectory, 3) The agent locates in the shipped papers at least one instance whose trigger lands on the same instant as the trigger of its prerequisite, quotes the sentence of the stage paper that settles it, and compares it with the outcome its package published for that instance.

## Root cause

**Placed rounding.** The arithmetic policy places a rounding after every
conversion and after every product, and forbids carrying an unrounded
value into the next stage. DFC-07 violates the second half of that
sentence while looking like an optimisation.

**Frozen revisions.** A register is a history, and the row in force is
the greatest revision at or below the frozen one. DFC-01 replaces that
with the greatest revision present, which agrees whenever the frozen
revision happens to be the maximum and disagrees everywhere else.

**Cross record state.** The window grid records differences, not starts,
and both delta chains begin at `origin_ms`. DFC-03 reads a row in
isolation and DFC-15 starts the context chain at zero, which RR6 forbids.
DFC-16 and DFC-17 read a register at the wrong frozen revision.

**One strength per declared sequence.** The r01 paper records edge
strength once per declared sequence (the last convertible row in file
order) and r06 gives every edge that shares the sequence that strength.
The shipped package already does this, so it is not a departure.

**Half open intervals.** Windows, contexts and override expiries are all
half open. DFC-04 and DFC-05 each close one end.

**Reading the directive.** The directive is the authority for the layer
order and for the number of reconciliation rounds, and the package was
written with both fixed. DFC-23 keeps the written layer order and DFC-24
keeps two rounds; each agrees with the papers only where the directive
happens to agree with the code, which it never does.

**Absence against zero.** Four layers rely on the difference. DFC-02
collapses it.

**Deferred capacity.** The binding in r10 is correct on its own inputs
and provisional by design. DFC-09, DFC-08, DFC-10 and DFC-24 each freeze
it early, in four different ways; DFC-20 double counts the second round's
draw in the feedback stage.

**Consumption on survival.** A one shot override is spent by the state
pass over the survivors of the feedback stage. DFC-11 spends it a stage
too early, which is invisible until the feedback stage withdraws
something.

**Reading the papers.** A byte order mark, a CRLF line end and a double
quoted field are all covered by the serialisation contract's reading
rules. DFC-21 ignores the first and DFC-22 the other two; DFC-19 lets file order
settle what the greatest cycle index settles.

**Red lines.** The delivered package holds nothing about a cycle, reads
only the directory it is pointed at, writes only the derived documents,
leaves the paper directory untouched, uses no binary floating point and
produces identical bytes on repeated runs.

## Solution shape

1. Extract `environment/data/project.zip` into a working tree.
2. Read `assistant_program_contract.md`, then the fourteen stage papers,
   then `data_lineage.md` and the serialisation contract's reading rules.
3. Open the workbook, the memo and the directive and pull the values that
   live only there.
4. Apply the twenty four targeted repairs (twenty five edits, since DFC-06 takes two) in
   `util.py`, `loading.py`, `stages.py`, `allocate.py` and `publish.py`.
5. Archive the repaired tree as `/app/out/package.zip` with
   `pyproject.toml` at the root, `src/daybreak` beside it and the shipped
   `tests` tree carried through unchanged.
6. Drive `python3 -m daybreak --data /app/data --out /app/out`.
7. Run the shipped suite and write the four repair records: the register
   with one row per departure (defect, stage, `module.function`, rule) and
   the notes with the figures read off the published documents.

## Ordered plan

1. Read `00_start_here.txt` and the programme contract, then the stage
   papers in order, implementing the branches this cycle never reaches
   from their own specifications. Earns R2.
2. Open the three papers that are not plain text and take the load
   bearing values each one carries, choosing the live grid by its key cell.
   Earns R1, R17.
3. Extract the archive and read the shipped modules against the papers.
4. Run the shipped suite, then drive the package over /app/data and
   inspect a published document before calling any repair done. Earns
   R5, R6.
5. Work the recording rules on the shipped data: hand compute two window
   starts, find a key whose frozen revision sits below its greatest and
   quote a field value that differs between the two rows, find
   a device policy row with an empty cell and state what it and a
   written zero would resolve to, find an
   override whose journal and snapshot counts differ. Earns R7, R8, R12,
   R13.
6. Locate the boundary instances in the papers, at least one cooldown
   expiry and one same instant prerequisite, and quote the settling
   sentence for each. Earns R15, R29.
7. Repair each anchor in place, to the standard of the code around it,
   exact rationals throughout. Earns R3, R20; avoids R23.
8. Drive the package in both option orders, twice over one directory, and
   check its output independently, by hand or with a separate computation: one demand row, one reconciliation group, one
   cycle removal, one one shot override, one readmission, one relay pool,
   one overturned instance whose fallback is proposed in the next round,
   one removal settled on a later key and the
   removals of the largest knot. Earns R9, R10, R11, R14, R24, R25, R26,
   R27, R28.
9. Report the live grid, the start of the last window as its own notes
   state it, the per reason
   counts from its own suppression ledger and each repair beside the stage
   its register names for it.
   Earns R16, R17, R18, R19.
   R4 is avoided throughout by leaving the papers as they were found, R21
   by reporting only what the last run showed, and R22 by changing course
   after a failure.

## Pitfalls

- Reading the plain text papers alone and never opening the workbook.
  Fails every binding and publication family.
- Taking the first workbook grid as live, or matching the key cell after
  stripping or case folding. Fails `stage_loading_exact` and the binding
  families.
- Treating the reading aids as a defect list and "repairing" functions
  that are correct. Fails `defect_register_matches_departures`.
- Starting the context chain at zero, or reading every window or the
  cooldown register at the window grid's global frozen revision. Fails the
  intake and policy families.
- Rounding the demand once. Fails `stage_binding_exact` and the
  binding families.
- Settling capacity in r10 and treating it as final. Fails
  `stage_reconciliation_exact` and the reconciliation families.
- Spending a one shot override on an instance r14 withdraws. Fails
  `shipped_state_documents_exact`.
- Taking the greatest revision in a register. Fails the intake and policy
  families and the intake and policy stage checks.
- Consulting the policy layers in the package's written order, or taking
  the round cap from anywhere but part C of the directive. Fails the
  policy or reconciliation stage checks and every minted family.
- Booking two departures in one function as one register row, booking
  DFC-22 under r02 alone, or naming a stage the departure merely passes
  through. Fails
  `defect_register_matches_departures`.
- Displacing a demand exactly equal to the pool. Fails the binding family
  and `stage_binding_exact`.
- Reading an empty cell as zero. Fails
  `shipped_policy_documents_exact`.
- Delivering something that republishes the shipped cycle whatever cycle
  it is handed, rather than a package that derives any cycle. Fails all nine
  minted families and fires
  `negative_hardcoded_sample_answers`.
- Rewriting a module wholesale and dropping a shipped test file. Fails
  `delivered_package_shape`; renaming a stage function or changing its
  arguments fails the stage checks.

## Provenance

```yaml
uuid: b28ebc90-3080-5d41-9f01-e02549d3efaf
instance_id: b28ebc90-3080-5d41-9f01-e02549d3efaf
task_name: terminal-bench/b28ebc90-3080-5d41-9f01-e02549d3efaf
solve_sh_sha256: 11468de52c3c0e9d396cf3d3ed4b0088f5a1393224f7fd1f11f9b1de7fcc9251
solve_py_sha256: 74ee837b797b047ca692fa5c42ea61c539536f33a1e05f7c7c1f67c0717f6a07
language: python
status: ready
corpus_files: 60
artifacts: 33
channel_a_positive_total: 132
channel_a_negative_total: -28
judge_criteria: 29
measured_oracle_test_channel: 1.000
measured_nop_test_channel: 0.000
```
