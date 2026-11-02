# TRUTH.md - dispatch-plan-reoptimization

## Defect

The shipped export set is internally consistent and complete: nothing is
corrupted, nothing is redacted, and no byte has to be recovered. What is broken
is a computation. A previous planning run published a dispatch plan, a headline
objective of `724451671` cents and a per key coefficient dump, all of which are
wrong because the run assembled its cost coefficients under assumptions the
operating contract forbids and then chose its plan with a policy the contract
does not sanction. The run publishes those assumptions in its own report, so the
defect is diagnosable rather than hidden. The agent has to rebuild every
coefficient from the registers, re-solve the three decision programmes to exact
optimality, and publish the corrected plan with its audit artifacts. The
corrected total objective is `446527364` cents.

1. (focal) The previous run used a sequence cutoff of `9999` rather than the
   contract cutoff `8140`, so post cutoff revisions of the demand, unit cost,
   capacity, handling, zone, shift, derate, eligibility, capex, savings and
   committed volume registers won rows they should never have won. Defeated by
   `hidden_*_coefficients`.
2. (focal) The previous run read EUR denominated cost rows and EUR denominated
   project savings as if they were United States cents, and never expanded the
   `kcents` scale on the capital cost register. The corrected path expands the
   scale first and then converts at the treasury rate whose effective sequence is
   the highest at or below the cutoff. Defeated by `hidden_*_totals`.
3. (focal) The previous run never opened the capital programme workbook. It used
   the `4200000` cent steering figure quoted in the operator notes as its capital
   envelope and valued projects at a flat planning volume, so it funded a
   different project set. The funded envelope of `2855000` cents and the per
   project committed volumes live only inside `capital_program.xlsx`. Defeated by
   `hidden_*_capital`.
4. (focal) The previous run charged carrying cost at `75` basis points against a
   pre correction coefficient and charged no shortfall at all. The carrying rate
   of `132` basis points and the shortfall charge of `418` cents per unit are
   published only inside the Flate compressed page streams of
   `penalty_schedule.pdf`, and the carrying coefficient is derived from the
   corrected unit cost, so an error in stage one cascades into stage three.
   Defeated by `hidden_*_plan` and `hidden_*_sourcing`.
5. (focal) The previous run applied a zero energy surcharge. The surcharge of
   `214` basis points lives only in `amendment_memo.docx` and adds to the period
   energy index before the uplift is rounded, so the index and the surcharge must
   be summed before the multiplication rather than applied one after the other.
   Defeated by `hidden_*_coefficients`.
6. (drift) A seasoned planner reaches for a value to capital ratio greedy on the
   capital programme, and for lot for lot production because it carries no
   inventory. Both are the previous run's policies and both are wrong here: the
   contract asks for an exact bounded selection over the capital grid and an
   exact lot sizing programme over contiguous coverage blocks, and the corrected
   answer opens far fewer setups than lot for lot does. Defeated by
   `hidden_*_capital` and `hidden_*_plan`.
7. (trap) The row lifecycle log binds to ledger rows through `row_uid` across
   file boundaries. A row that looks live can be voided by a log entry in another
   export, and a row that carries `void` history can be revived by a trailing
   `restore` entry. A solver that reads only the `void` column inside each
   register selects the wrong winner for a scattered set of keys. The superseded
   void register is a decoy channel that must change nothing. Defeated by
   `hidden_*_coefficients` and `hidden_*_quality`.
8. (trap) The planning horizon is ordered by the fiscal ordinal in the period
   window register and opens at `P05`, not at `P01`. Lot sizing over the lexical
   order produces a schedule that is internally consistent and completely wrong,
   and only the ordering artifacts expose it. Defeated by
   `hidden_*_plan`.
9. (trap) A key with no live setup row takes the `setup_fallback_cents` its item
   carries under the runbook `item_defaults` block; only an item that block does
   not list (K22) takes the control `default_setup_cents` of `96000`. The control
   default sits in both the runbook control block and the authority database, so
   it is the reflex answer. In the shipped set only K14 P06 has no live setup
   row, so its coefficient is `41000`; on the hidden sets voided setup rows put
   the fallback on opened keys, where it moves the plan. Defeated by
   `hidden_*_coefficients`, `hidden_*_plan` and `hidden_*_totals`.
10. (trap) Equal cost lot sizing schedules are compared by their production
    periods from the last one backwards, and the schedule whose period is
    earlier at the first difference wins. K13 ties in the shipped set (one lot at
    P23 covering P23 to P04 beats a second lot at P02), and each hidden set holds
    two constructed ties. A backward recursion that keeps the shorter block reads
    the tie the other way. Defeated by `hidden_*_plan`, `hidden_*_sourcing` and
    `hidden_*_totals`.

The reference implementation is Python 3 using the standard library only. Grading
is split across two channels: `tests/test_output.py` grades the artifacts the
delivered optimizer writes on hidden input sets, `tests/judge.toml` grades the
final reply, the trajectory and workspace state.

Out of bounds: baking the corrected shipped total into the delivered
program, or embedding the shipped item, plant and project codes rather than
reading them, is caught by `negative_shipped_results_baked_into_solver`; reaching the network or a third
party package, or starting another process, is caught by
`negative_network_dependency_or_shell_cheat`; drawing on a clock or a
random source is caught by `negative_nondeterminism_source_in_solver`; and
echoing the published faulty objective is caught by
`negative_trusts_incumbent_objective`; leaving files in scratch or shared temp
space outside the output directory is caught by
`negative_writes_outside_output_dir`, while touching `/app/data` is judged once,
by the judge's `/app/data` penalty. A literal module name passed to
`__import__` or `importlib.import_module` counts as an import of that module,
so a dynamic import of an allowed module costs nothing. The two network and nondeterminism checks
use, respectively, runtime audit events and executable source nodes; a comment,
docstring or diagnostic print string naming a package costs nothing. Reads outside
the supplied input directory are caught by `negative_reads_outside_input_dir`.
One act of embedding answers costs at most 5:
`negative_trusts_incumbent_objective` fires only when no shipped total and no
shipped identifier is baked in.

## Load-bearing work

The graded artifacts are the delivered optimizer plus twenty one published files:

- `/app/out/solver.py`
- `/app/out/corrected_coefficients.jsonl`
- `/app/out/objective.json`
- `/app/out/optimal_plan.jsonl`
- `/app/out/production_schedule.csv`
- `/app/out/sourcing_allocation.csv`
- `/app/out/holding_profile.csv`
- `/app/out/retrofit_selection.json`
- `/app/out/budget_utilization.json`
- `/app/out/period_costs.json`
- `/app/out/item_summary.json`
- `/app/out/plant_utilization.csv`
- `/app/out/shortfall_ledger.csv`
- `/app/out/binding_constraints.json`
- `/app/out/optimality_certificate.json`
- `/app/out/incumbent_delta.json`
- `/app/out/coefficient_corrections.csv`
- `/app/out/sensitivity_report.json`
- `/app/out/data_quality.json`
- `/app/out/rejected_records.csv`
- `/app/out/reconciliation.txt`
- `/app/out/audit_summary.md`

Content contract per deliverable. `solver.py` is a stdlib only program that
runs as `python3 solver.py <in> <out>` and takes an input directory and an
output directory. `corrected_coefficients.jsonl` carries one object per
in scope item and period with the rebuilt unit, setup and carrying coefficients,
the applied energy basis points and the provenance flag string.
`objective.json` carries the six cost components, the corrected total of
`446527364` cents and the scope counts. `optimal_plan.jsonl` and
`production_schedule.csv` carry the lot sizing decisions and the resulting
inventory. `holding_profile.csv` carries the carrying charge and its running
total. `sourcing_allocation.csv`, `plant_utilization.csv` and
`shortfall_ledger.csv` carry the cheapest first fill, the plant loading and the
uncovered volume of `33012` units. `retrofit_selection.json` and
`budget_utilization.json` carry the exact capital selection of `2635000` cents
against the `2855000` cent envelope. `period_costs.json` and `item_summary.json`
are the two roll ups. `binding_constraints.json`, `optimality_certificate.json`
and `sensitivity_report.json` carry the active constraints, the four optimality
checks and the marginal envelope value. `incumbent_delta.json` and
`coefficient_corrections.csv` carry the comparison against the published run.
`data_quality.json` and `rejected_records.csv` carry the source accounting, the
three stale count registers and the `1002` discarded rows.
`reconciliation.txt` and `audit_summary.md` close the audit with the same nine
figures in the same order.

Out of bounds by design: the agent may not rewrite anything under `/app/data`,
may not reach the network, and may not ship a program whose behaviour depends on
the identifiers or the row order of the shipped export set.

## Verification

`tests/test.sh` runs `rewardkit /tests --workspace /app`. `tests/test_output.py`
registers 35 `@criterion` checks. `tests/judge.toml` holds the judged criteria.
`tests/reward.toml` gives each channel half of the reward: the tests channel is
weighted 0.5 divided by its positive total (101) and the judge channel 0.5
divided by its positive total (19).

The tests channel grades what the delivered optimizer writes on four hidden
input sets, H1 to H4. Each set is the shipped export set with the governing
figures of the demand, unit cost, setup, capacity, handling and project saving
registers reseeded row by row, plus appended rows: setup rows of six opened keys
per set (always one K22 key, which `item_defaults` does not list, and one K14
key) voided through lifecycle log entries so the fallback rule decides them; a
repeated `amend_id` whose first copy is voided by the log and a repeated
`amend_id` with two live copies; one retired item spelling, one unknown item and
one sentinel quantity in the demand registers; and two constructed lot sizing
ties per set, where a later production period costs exactly the same as
covering it from the earlier lot. On H2 and H4 the figures held only in the
binary sources are re-authored as well: every revision row of the holding rate
and the shortfall penalty in `penalty_schedule.pdf`, of the energy surcharge in
`amendment_memo.docx`, and of the capital budget and the committed volumes in
`capital_program.xlsx`, each figure by one set wide factor. The manifest counts
follow the appended rows.
The sets are stored as overlay tarballs over the embedded shipped data
(`_SHIPPED_DATA`), and the expected artifacts per set were produced offline by
the oracle; the verifier holds no reference implementation.

The grader stages a readable copy of `/app/out/solver.py` (mode 0644 in a 0755
directory), runs it under `setpriv` as `nobody` in its own session with
`python -B` (so the interpreter writes no bytecode cache) through a
standard-library audit wrapper. Every run, including the scope run, removes
environment names containing KEY, TOKEN, SECRET or PASSWORD while preserving
PATH, LANG and the caller's TMPDIR. The wrapper logs file access, imports,
socket use and process starts to a grader-owned file. The grader holds a file
lock and kills the process group and any leftover `nobody` process. It compares
JSON values recursively with exact types (`1`, `1.0` and `true` differ, key order
free), JSON lines record by record, CSV row by row and text line by line. It
also checks the stated key ordering, indentation, compact JSONL, LF, UTF-8 and
terminal newlines. Numeric literal spelling and equivalent string escapes are
left free because the handbook does not specify them. Per set there are seven groups: `coefficients` (3),
`capital` (1), `quality` (3), `plan` (5), `sourcing` (5), `totals` (5) and
`certificate` (3), named `hidden_h1_coefficients` and so on. A group passes when
every artifact in it matches. `shipped_artifacts_match_contract` (1) compares all 21 shipped
artifacts against trusted goldens under the same rules. It is the only shipped
run check. Isolated groups (coefficients, capital, quality) carry 28 of 101.

The negative checks are `negative_shipped_results_baked_into_solver` (-5),
`negative_network_dependency_or_shell_cheat` (-3),
`negative_reads_outside_input_dir` (-3),
`negative_nondeterminism_source_in_solver` (-3),
`negative_trusts_incumbent_objective` (-3) and
`negative_writes_outside_output_dir` (-3). Each stands down unless the
optimizer ran cleanly on H1. A program that copies fixed files earns 1 of 101.

Channel B holds twelve judge criteria. R1 to R5 are five figures for the
shipped export set that the final reply must state: the corrected total
`446527364` (R1, weight 5), setup cost `19229000`, holding cost `31756967`,
75 production lots and `33012` uncovered units (R2 to R5, weight 1 each). R6
(weight 1) asks that money is computed with integer arithmetic on cents in
solver.py. R9 (weight 3) asks that solver.py is written to ordinary Python
practice. R11 (weight 3) asks that the agent's solver.py applies every
rejection reason before it decides that a row is out of scope. R12 (weight 3)
asks that, before finalising, the agent checks how its solver.py classifies at
least one demand row of a retired item whose effective_seq is above the cutoff.
The negatives are R7 (-5, a reply figure or claim that the agent's own output
contradicts), R8 (-3, touching `/app/data`) and R10 (-3, looking up a
task-specific online solution, write-up or answer key). Positive judge weight
is 19 and absolute negative weight is 11. No automated test reads the
trajectory and no judge criterion grades a hidden set.

## Root cause

**Configuration precedence.** Every figure in this corpus exists in more than one
place: a primary register, a stale mirror, a superseded channel, an
informational dump, and sometimes a document. The manifest's `authority` column
is the only thing that resolves them, and the previous run resolved them by
convenience.

**Sequence discipline.** Revisions are ordered by `rev` inside a key but scoped
by `effective_seq` against a cutoff. Raising the cutoff does not add information,
it lets unratified future revisions decide the plan.

**Unit closure.** Scale, currency and basis point conversions each have exactly
one place in the pipeline. Applying the surcharge after the index rather than
summing them, or converting before expanding the scale, produces values that look
plausible and are wrong by a few cents per unit, which the volume then multiplies
into the objective.

**Stage dependency.** The workbook envelope decides the capital selection, the
selection decides plant handling rates, the rates decide the sourcing fill and the
shortfall, and the rebuilt unit cost decides the carrying rate that decides where
production opens. There is no way to get the objective right while getting an
earlier stage wrong. The test cascade is intended: one wrong upstream figure
fails every artifact that depends on it, so a single wrong capacity figure costs
most of the tests channel on every hidden set.

**Exactness.** The three programmes are exactly solvable, so approximation is a
defect rather than a trade off. The certificate artifact exists to make that
claim checkable.

**Red lines.** No hardcoded answers, no embedded shipped identifiers, no network
or third party dependency, no clock or random source, and no echo of the
published faulty objective.

## Solution shape

1. Read the SQLite source manifest, group the 55 exports by role and authority,
   and read the cutoff control table for the cutoff, the capital grid, the control
   setup default and the minimum handling rate, and the runbook `item_defaults`
   block for the per item setup fallback.
2. Build the lifecycle state by folding the log entries at or below the cutoff per
   `row_uid` and letting the last void or restore decide.
3. Resolve the horizon from the period window register by fiscal ordinal, the
   item scope from the item status register, and the plant and period scope from
   the plant status register.
4. Rebuild the unit coefficient per key: expand the scale, convert the currency at
   the cutoff rate, accumulate amendments on identity with credits negative, let
   an override replace the accumulation, then add the rounded energy uplift built
   from the period index plus the memorandum surcharge. Derive the carrying
   coefficient from the result and the schedule rate.
5. Rebuild capacity and handling per plant and period from base rows, accumulated
   adjustments, the shift pattern, the holiday derate, the mothballed status and
   the zone uplift.
6. Solve the capital selection as an exact bounded selection over the capital
   grid using the workbook envelope and committed volumes, with the documented
   value, capital and indicator tie break, and apply the funded savings to the
   plant rates.
7. Solve each item's lot sizing as an exact dynamic programme over contiguous
   coverage blocks; among equal cost schedules compare production periods from
   the last one backwards and keep the schedule whose period is earlier at the
   first difference.
8. Fill plants cheapest first per period, split the assigned units across items in
   ascending code order, charge the residue at the shortfall rate, and assemble
   the objective, the certificates, the sensitivity figures and the audit
   accounting.

## Ordered plan

1. Survey `/app/data`, find the manifest database, and read the sources table
   before opening anything else, sampling rows of several register formats
   before writing any parser.
2. Read the handbook end to end and pin the stage order, the tie breaks, the
   fallbacks and the output contract.
3. Open the workbook, the schedule document and the memorandum with `zipfile` and
   `zlib` and pull the envelope, the committed volumes, the shortfall charge, the
   carrying rate and the energy surcharge.
4. Establish the horizon, the item scope, the lifecycle state and the sentinel
   rejection rules (tokens read from the nomenclature contract) before any
   arithmetic, and write the accounting sweep so that every rejection reason is
   applied before a row is counted out of scope (R11).
5. Rebuild the coefficients stage by stage and check one key by hand against the
   worked examples in the handbook.
6. Solve the three programmes exactly and publish the certificate.
7. Reconcile the published run against the rebuild.
8. Before finalising, pick one demand row of a retired item whose
   `effective_seq` is above the cutoff (K07 and K19 have such rows) and check
   that the optimizer reports it in `rejected_records.csv` as `retired_item`
   and leaves it out of `out_of_scope_rows` (R12).
9. Run the optimizer on a modified copy of the inputs, leave `/app/data`
   untouched, and state the five requested figures in the final reply (R1 to R5).

## Pitfalls

- Sorting the horizon by period code rather than fiscal ordinal. Fails
  `hidden_*_plan`.
- Taking the steering envelope from the operator notes. Fails
  `hidden_*_capital` and `hidden_*_totals`.
- Reading the schedule document with a plain byte scan and missing the Flate
  compressed pages, then falling back to the legacy figures in the audit trail.
  Fails `hidden_*_sourcing` and `hidden_*_plan`.
- Applying the energy index and the memorandum surcharge as two successive
  roundings. Fails `hidden_*_coefficients`.
- Treating the amendment register as a superseding register. Fails
  `hidden_*_coefficients`.
- Ignoring the cross file lifecycle log and trusting the `void` column alone.
  Fails `hidden_*_quality`.
- Dropping the `VOI` flag on a key whose winning row was voided and then
  revived by a `restore` entry. Fails `hidden_*_coefficients`.
- Scoping an `adj_id` per plant and period, or adding a later copy of a
  repeated `adj_id` rather than the first live one: every capacity and handling
  `adj_id` appears in both shard files, mostly on different pairs. Fails
  `hidden_*_sourcing`, `hidden_*_totals` and six more.
- Treating K31, K44 and K57 as known items: their only item status rows sit
  above the cutoff, so they have no live row and their demand rows are
  `unknown_item` rejections. Fails `hidden_*_quality` and `hidden_*_totals`.
- Ignoring a stated tie or fallback rule. RP02, RP04 and RP26 carry equal value
  (lowest capital, then the smallest indicator, keep RP02), RP17 and RP25 tie
  for the top unfunded ratio (RP17), K13 P02 ties with covering that demand
  earlier (the earlier production wins), K14 P06 has no live setup row (its
  `item_defaults` fallback of `41000`, not the control `96000`), S10 P05 drops below the minimum handling rate after its
  savings (the floor), and the K02 family rows tie on `rev` and `effective_seq`
  inside one file (the later row). The hidden sets add two constructed lot ties
  each and void setup rows so the fallback decides opened keys; a tie read the
  other way fails the plan, sourcing and totals groups, and the control default
  in place of `item_defaults` fails the coefficients, plan, totals and
  certificate groups.
- Breaking an equal `rev` and `effective_seq` tie by row position inside each
  file rather than by canonical order (file name, then row). The two setup
  charge exports tie on K03 P01, and only the row in the later file is right.
  Fails `hidden_*_coefficients`.
- Choosing capital projects by a ratio greedy. Fails
  `hidden_*_capital`.
- Producing lot for lot. Fails `hidden_*_plan`.
- Counting the stale mirror registers as authoritative. Fails
  `hidden_*_sourcing`.
- Copying the previous run's coefficient dump. Fails
  `hidden_*_coefficients`, and fires
  `negative_trusts_incumbent_objective` when the total is echoed.

## Provenance

```yaml
uuid: 2b89435a-5d1c-4f2a-9b3e-701600000001
instance_id: dispatch-plan-reoptimization
task_name: terminal-bench/dispatch-plan-reoptimization
language: python3
corrected_total_objective_cents: 446527364
published_faulty_objective_cents: 724451671
data_files: 55
artifacts: 22
hidden_sets: [H1, H2, H3, H4]
solve_py_sha256: 73bf2bd1a1b7bee8be7eeebb3582dd0521cd467f6cae80e2515b04a37529b3c4
fixtures_sha256:
  handbook_ops_v9.md: effd146ddea2f4431810a6797553420b74a2f620ff4b42a1e28119115b7bf5c2
  runbook_params.yaml: 8c68a2739a61438fe2baf815d9c3cfb050493b597fac89795d1a488a1f550c5d
  xref_manifest.db: 3398a018b636cd33d0f835c98a594a237f22e4f0a402c0168e88ace2019fa919
  test_output.py: 0d0e02f0f0e8a976a9aef2dab99284552759bc116d6dd879a495220a4473b537
```
