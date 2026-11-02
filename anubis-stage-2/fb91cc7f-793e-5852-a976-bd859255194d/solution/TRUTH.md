# TRUTH.md - fb91cc7f-793e-5852-a976-bd859255194d

## Defect

The restoration lab's settlement run for cycle 47 was lost. The catalogue survives
in full: scanned elements, a lineage book, a cut list, a defect log, a repair log,
holder accounts, a vault charter and a lane charter, together with six subsystem
rulebooks, a statement of invariants, and a complete audited earlier cycle carried
under calibration-marked names. What does not survive is the settlement itself, and
what was never written down is the procedure that produces it. The agent has to
recover the procedure from the rules and the published control figures, then run
it, then reconcile it.

1. **(focal)** Three standing house conventions are named in shipped material but
   never valued: the quantisation applied when a frame count is converted between
   cadences, the order in which the three settlement operators compose, and the
   fraction of a repair ceiling that carries through to the next repair worked on
   the same defect. The space is
   four quantisations by six orders by eight fractions, 192 combinations. Exactly
   one reproduces every figure published for the calibration cycle: an exhaustive
   sweep over all 192 leaves one match, with per-figure collision counts of 1 for
   the four per-programme settled frames, 2 for the settled total, 24 for the
   recovered total and 192 for the impaired total. The true values are round half
   to even, the order impairment then cadence then credit, and three fifths.

2. **(focal)** Fourteen constraints must hold at once, and each is independently
   violable. Five demand sustained cross-record tracking: registration offsets
   accumulating along a multi-hop lineage chain, the union of folded spans under
   shift, impairment computed as a union rather than a sum, the pass ceiling
   decaying across a defect's repair history, and the admission draw closing as a
   prefix while the drawing set settles to a mutual fixpoint. Four are structural:
   shot tiling and void determination, print never governing while another class
   supplies the programme, repair state precedence, and canonical serialisation.
   Two are global couplings evaluable only when every stage has completed: the
   vault seating, which no greedy pass can reach, and the residual cascading
   through the lanes in rank order. One is the counterfactual. Two are binary.

3. **(focal)** The chain is fifteen stages deep and every edge carries a derived
   value. Identity resolution feeds usable spans, which feed the shot conform,
   which feeds void determination, which feeds the governing element, which feeds
   defect clipping, which feeds the impairment union, which feeds repair
   adjudication, which feeds recovery accrual, which feeds cadence conversion,
   which feeds the condition grade fixpoint, which feeds settled frames, which
   feeds the admission fixpoint, which feeds vault seating, which feeds the lane
   cascade and the reconciliation. Two convergence points sit inside it. Neither is
   described as iterative anywhere in shipped material; both are stated only as
   uniqueness properties, so a single forward pass produces silently wrong values
   rather than an error.

4. **(drift)** The rulebooks are named by subsystem and read in alphabetical order
   as allocation, cadence, conform, defect, identity, repair. The application order
   is identity, conform, defect, repair, cadence, allocation. Nothing states the
   sequence; it is derivable only from the invariants and from which figures the
   calibration slice can reproduce. An agent that applies rules in document order
   computes an allocation before it has a settled frame count.

5. **(drift)** Two rules do not fire on this cycle. The print-exclusion rule cannot
   fire because the only print element is retired before the settlement cycle, and
   the all-print fallback cannot fire for the same reason. Both are genuine
   in-domain rules that fire on neighbouring cycles, and both are exercised by
   mutated corpora inside the verifier, so neither is filler.

6. **(trap)** `rulebook_cadence.md` states once, plainly, and explicitly against
   the industry default, that a programme settles at its delivery cadence and not
   at the cadence of the element it was conformed from. Pulldown-added frames are
   billable; decimation-removed frames are not. Every one of the eight settled
   programmes changes value between the two readings. Every settled programme carries a
   delivery cadence that differs from its governing element's cadence, so the
   conventional reading changes all eight figures.

7. **(trap)** Vault capacities form an exact-fit instance. A greedy first-fit
   seating provably fails on this cycle; exactly one complete assignment satisfies
   every capacity, class and group condition simultaneously. Taken in descending settled
   frames a greedy walk seats pg01 and pg04 in arbor, leaving 16113 frames of
   headroom for pg03, whose 16114 frames fit no other vault, so it fails by one
   frame.

8. **(trap)** One vault carries a zero load and still requires its report. The
   count and names of the vault and lane reports are never stated; they are
   derivable only from the charters.

The oracle at `solution/solve.py` is an independent settlement engine authored
against the shipped rulebooks, the invariants and the calibration cycle: it shares
no function with `tests/test_output.py` and re-derives every stage in its own code,
so its agreement with the verifier is evidence that both are right rather than a
tautology. It reads a catalogue directory and writes a report directory, hardcodes
the three recovered standing conventions as constants (they hold for every cycle),
and uses the standard library alone. The verifier carries its own separate
reference implementation, which grades against the same recovered conventions
through an optional parameter block; the two implementations produce byte-identical
reports on the settled cycle and on every mutated corpus, which is the check that
the oracle is correct rather than merely echoing the grader.

The verifier runs in its own container, built from `tests/` alone, so
`/app/data` is not part of that image. `tests/test_output.py` therefore carries the
whole catalogue as a compressed archive literal and unpacks it to a private
directory at import; `_data_root()` points there and every reference
computation, every mutated corpus and every determinism rerun reads that copy. The agent's own
catalogue is declared as an artifact so the harness carries it into the grading
container, and it is read at exactly one place, `_catalogue_intact`, which compares
it byte for byte against the recorded digests. Tampering with `/app/data` can
therefore only lose a point, never win one.

Out of bounds: the agent is not asked to modify the catalogue, to reach the network
for any figure that affects the settlement, to install a third-party package, to
reproduce this cycle's expected outputs from memory, or to infer anything from
filenames. The catalogue is checked byte for byte after the run. Reaching outside
the standard library, branching on filenames, hardcoding figures, or writing
non-deterministic output are each detected by a dedicated negative test.

## Load-bearing work

Resolve identity first. Apply only those lineage events whose effective cycle is at
or before 47; one supersede is dated 51 and does not apply, and a solver that
ignores the date closes a loop that is not there. Walk each chain transitively,
accumulating the registration offset at every hop. Two chains here are two hops
long and carry non-zero offsets at both hops, so a solver that takes only the last
hop's offset is wrong by 750 frames on one element and 18000 on another. Fold
merged elements under the resolved canonical, not under the raw target of the merge
event, or a merge into an element that itself merges lands under the wrong key.

Take each live element's usable span as the union of what all its identifiers
supply after shifting. Photochemical stock excludes head and tail leader; tape
carries no leader and its leader columns are an artefact of a shared form.

Conform each programme by laying its shots onto the timeline in ascending ordinal
from zero. Void on any of six conditions. Two programmes void here, for two
different reasons: one has a shot that leaves its element's usable span, one has
ordinals that do not tile.

Clip each defect to its host shot and take the union per programme. Adjudicate
repairs in pass order, ties by repair id, applying the window test first, then the
node class test, then the ceiling. Compose the three operators in the recovered
order under the recovered quantisation, and find the one grade stable under its own
credit. Draw, seat by search, cascade, reconcile.

## Verification

Thirty-four rewardkit criteria in `tests/test_output.py`, each registered once
with `criteria.<name>(weight=W)`. **Positive weight total 124.** Six checks at
weight 1: the three structural checks, the identity and defect-clipping stages,
and canonical serialisation. Twelve at weight 5: the remaining settlement
stages, each owning one observable and carrying that stage's own invariant
alongside its agreement with the reference. One at weight 3: the cycle ledger
closure, which the lane cascade check used to carry alongside its own stage.
Eleven generalisation checks at weight 5, which run the delivered program over
a freshly mutated catalogue.

One checker per observable. A stage check owns its agreement and its invariant
together. A programme's settled frame count is the one figure several reports
carry, so altering it costs the four checks that read it in their own report
rather than one.

The negative-weight checks are `negative_hardcoded_sample_answers` at weight
-5, `negative_filename_dependent_behaviour` at weight -3,
`negative_nondeterministic_output` at weight -1 and
`negative_catalogue_modified` at weight -1. All four return False for an honest
solver and for the no-op baseline alike, so they contribute nothing to any
solution that is not actually cheating. The filename check compares two runs of
the delivered program over identical bytes at two different paths, so a
correctness slip cannot be mistaken for path-keyed behaviour.

Largest single check 4.03 percent of positive weight. Measured on the host by
running each candidate against the registered criteria: the oracle scores
1.000; the no-op baseline scores 0.000; a deliberate forgery, one hand-written
report per declared name filled with plausible values beside an inert program,
earns the 3.23 percent structural floor from `settlement_program_present`,
`core_reports_parse`, `partition_reports_present` and
`canonical_serialisation`, and nothing else; a correct settlement with one
settled figure altered across every report that carries it scores 0.839,
losing `settled_frames_fixed`, `admission_settled`, `vaults_seated` and
`admission_closes_as_a_prefix`. A program that recovers the
three conventions at run time from the published calibration cycle, which is
what the instruction asks for, also scores 1.000, because every graded
catalogue ships the complete 28 file corpus rather than the data files alone.

Through the real harness with `--env docker`, on a tests-only copy that drops
the judged channel and scores the test channel at `1 / 124`: five oracle runs
read 1.000, 1.000, 1.000, 1.000 and 1.000, the no-op baseline reads 0.000, and
a stub whose solution creates the two declared artifact directories and nothing
else reads 0.000, paying no check and firing no negative. These are test
channel figures; the judged channel is validated against the rewardkit 0.2.1
schema and is never executed by that gate, because oracle, nop and stub leave
no trajectory for a judge to read.

`tests/judge.toml` carries twenty-one criteria for a positive score total of 57
and two negatives at -5 each. `tests/reward.toml` gives each channel half the
final score, at `0.5` divided by that channel's positive total. The judged
criteria read the final message, the trajectory and the delivered program's
code, none of which the deterministic checks read. Eleven are constraint
criteria quoting the instruction sentence they enforce, covering the
disclosure of the three recovered conventions, one criterion for each of the
seven settlement items the final message must state, and the
standard-library-only rule. Ten are conduct criteria grading how the work was
done, including the maintainability of the settlement program. Two of those
are negative: one fires when the agent reports having taken a figure or a
convention from outside the delivered catalogue, the other when the response
claims a closing cycle that the reconciliation report it delivered denies.
The three disclosure criteria assert the value of a convention that the
deterministic channel also settles indirectly, since exactly one combination
reproduces the published figures; they are kept because the instruction
requires the disclosure out loud and the final message is invisible to the
tests.

## Root cause

There is no defect to repair in the ordinary sense. The task is a reconstruction:
the settlement was lost, the procedure was never written down, and the corpus is
sufficient to recover both but only by correlating the rulebooks against the
invariants against the published control figures. The difficulty is that fourteen
constraints must hold simultaneously across a fifteen-stage serial computation with
two fixpoints, while three conventions are unknown and one stated domain rule
contradicts what a practitioner would assume.

## Solution shape

One program at `/app/out/cadence_settle.py`, taking a catalogue directory and an
output directory positionally, standard library only, deterministic, writing
fifteen reports on this cycle: nine fixed reports plus one report per vault the
charter opens and one per lane it opens. Reports are serialised with sorted keys,
two-space indent and a single trailing newline. The field names and the
presentation order of every document are published in
`environment/data/delivery_schedule.md`, and one fully formed example artifact from
the control cycle ships beside it; neither carries a value, an identifier or a rule
belonging to the cycle under settlement.

## Ordered plan

1. Read every file in the catalogue before writing any code.
2. Separate the current cycle from the calibration cycle by the marked names.
3. Recover the three conventions by searching the interpretation space against the
   published control figures until one combination reproduces all of them.
4. Resolve identity: filter events by effective cycle, walk chains transitively,
   accumulate offsets, fold under the resolved canonical, retire what is retired.
5. Compute usable spans as unions under shift, honouring stock class.
6. Conform each programme; determine voids on the six conditions.
7. Choose governing elements, skipping print while another class supplies.
8. Clip defects to their shots and take the union per programme.
9. Adjudicate repairs pass by pass with window, node class and decaying ceiling.
10. Convert cadence, compose the three operators, settle the grade fixpoint.
11. Run the admission draw with prefix close and settle the drawing fixpoint.
12. Seat the admitted programmes by search, not by greed.
13. Cascade the residual through the lanes in rank order; shed what does not fit.
14. Write every report, including one for the vault that carries nothing.
15. Reconcile all five stages; confirm the residual is zero; rerun and diff.

## Pitfalls

Applying a lineage event dated after the settlement cycle. Taking only the last
hop's registration offset. Keying folded elements on the raw merge target. Treating
tape leader columns as real. Summing overlapping defects instead of taking their
union. Applying the pass ceiling by pass index rather than by rank within a defect.
Settling at element cadence instead of delivery cadence. Taking a single forward
pass at the condition grade instead of finding the stable one. Running the
admission draw as skip-and-continue instead of closing the group at the first
refusal. Seating greedily. Omitting the report for the empty vault. Emitting
unsorted keys or a different indent. Reading the rulebooks in document order.

## Provenance

```yaml
uuid: fb91cc7f-793e-5852-a976-bd859255194d
instance_id: fb91cc7f-793e-5852-a976-bd859255194d
task_name: terminal-bench/fb91cc7f-793e-5852-a976-bd859255194d
fix_patch_sha256: 8902ab4dcca67148583fff628128a865ea7e5d295d11aaf8eaf53e9a984e07f4
solve_py_sha256: 1241bcd44277f5a73ef0855e826ed88f066c566d25a35a75ba95d6f7d65aa785
language: python
status: ready
```
