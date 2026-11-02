# TRUTH.md - inference-gate-replay

## Defect

Nothing in this bundle is broken. What is missing is the program itself. A model
serving fleet ran an inference gate that turned each metered probe into a scored
verdict and rolled a shift up three ways, and when the serving controller was
replaced the gate went with it. The shipped directory holds the shape of the gate
and none of its numbers, so the solver has to induce every constant the stages
apply from one worked example shift and four sha256 digests, and then write the
gate back as a reusable program. These are the things the solver has to see.

1. Fifty six controller constants are named nowhere (focal). `gate.md` lists the
   fourteen stages, the carried state and the verdict ladder, and `reports.md`
   lists the key set and the byte form of the four reports, but neither file
   carries a single figure. The span factor, the replay offset, the gain, the
   four precision responses, the seven accelerator responses, the three phase
   responses, the four kernel responses, the three band edges, the four plan
   tolerances, the coarse accelerator and its scale, the reserved meter value,
   the trailing record size, the credit division, the backlog arithmetic, the
   drifting budget, the counted verdict set, the strike count, the throttle
   figure and both tie breaks all have to be recovered.
2. The `meter` column is not the meter (focal). Inside a segment it stores a
   first difference of a cumulative token counter, so the gate accumulates once
   to recover the level. Every stage downstream reads a figure that does not
   appear anywhere in the input file.
3. The accumulation is carried per phase as well as per endpoint (trap). An
   endpoint serving only `prefill` behaves identically under a single
   accumulator, so the rule stays invisible on most of the shift and only shows
   itself on the endpoints that interleave `prefill`, `decode` and `batch`. A
   solver who reads "per endpoint" and stops there reproduces most of the shift
   and still fails every digest.
4. One reserved meter value means repeat (trap). A probe carrying it takes the
   meter of the probe resolved before it on the same endpoint and the same phase
   and leaves the accumulation untouched. Read as an ordinary difference it
   drags the accumulator off by one step and every later probe on that track is
   wrong.
5. One accelerator records its meter on a coarser scale (trap). The recovered
   figure has to be multiplied back into tokens before the budget is taken off
   it. The worked example ships no endpoint on that accelerator, so nothing but
   the digests can confirm it.
6. The charged precision is inherited through the variant's base (drift). A
   `variants.csv` row carrying a `base` names another variant, and the precision
   the gate charges is the base's rather than the row's own. The experienced
   instinct is to read the precision column of the row in front of you, which is
   what the worked example rewards, because no example variant names a base.
7. The budget a segment boundary installs leaves the endpoint (drift). It is
   derived from the scores resolved across the whole shift up to that probe, not
   from the endpoint's own history, so an engine written to resolve one endpoint
   at a time is correct on every endpoint in isolation and wrong on the shift.
8. The evidence carries no partial signal (focal). `digest.json` holds one
   sha256 over each of the four reports and nothing else. There is no per
   endpoint figure and no per probe figure to climb, so a solver learns only
   that the whole shift is right or that it is not.

The reference implementation in `solution/solve.py` carries the whole gate as
one source string, confirms that reading against the worked example, the held
back block, a counterfactual input of its own and all four published digests,
installs the program at `/app/out/gate.py`, runs it over `/app/data` and prints
the ten closing figures. It is the author-side proof that every constant above is
recoverable from what the agent can see.

Out of bounds: the solver never edits anything under `/app/data`, never installs
a package outside the standard library, never keys behaviour on the name of the
input directory and never bakes an answer computed at authoring time into the
delivered program. The program has to work on shifts it has never seen, so every
figure it applies has to be a constant of the gate rather than a constant of the
recorded shift.

## Load-bearing work

One artifact is graded: `/app/out/gate.py`, declared in `task.toml` and copied
into the verifier at that exact path.

The content contract for that one file is the whole task. It takes two command
line arguments, an input directory and an output directory, and writes four
files into the output directory:

- `verdicts.jsonl`, one JSON object per probe in ascending `seq`, ten keys each,
  serialized with `sort_keys=True` and `separators=(",", ":")` and a trailing
  newline per line.
- `endpoints.json`, one object with the single key `endpoints`, holding the per
  endpoint rows sorted by endpoint identifier, twelve keys each, serialized with
  `sort_keys=True, indent=2` and one trailing newline.
- `precision.csv`, a header line and one row per charged precision sorted by
  name, no quoting and no padding.
- `shift.json`, one object of seven keys in the same JSON form as
  `endpoints.json`.

The program has to hold for a shift with no endpoint and no probe at all, has to
stay inside the standard library, has to produce byte identical output on two
runs over one input directory, and has to behave the same whatever the input
directory is called. The ten closing figures go in the final message and stay out
of the four report files.

## Verification

`tests/test.sh` clears any earlier reward files, locks `/logs/verifier` and
`/tests` down to root and hands over to `rewardkit /tests --workspace /app`.
rewardkit grades two channels and `tests/reward.toml` adds them up: each
channel's weighted sum is divided by its own positive total and halved, with no
clamp, so the reward runs from about -0.13 up to 1.0.

Channel A is `tests/test_output.py`, 35 `@criterion` checks whose weights are
registered with `criteria.<name>(weight=W)` at the foot of the file. The
positive weight total is 93 and the negative weights sum to -14. Every check
runs its assertion body through `_holds`, which binds the paths to the workspace
and turns any exception into a failed check, so one broken artifact costs that
check and never aborts the run. Every launch of the delivered program runs in a
session of its own under a time budget, and its whole process group is killed
before the check returns. Thirty one positive checks carry that 93: eight at
weight 1, fifteen at weight 3 and eight at weight 5.

The eight weight-1 tests cover the report shape, the documented byte form, a
shift holding nothing, the batch width and gain together, and one response axis
each for precision, accelerator, phase and kernel. Each axis probe holds every
value of its axis at once, so one wrong entry in a response table fails the whole
probe.

The fifteen weight-3 tests each turn on one recovered mechanism, built over
endpoints left neutral on all three response axes so the probe measures the
mechanism rather than the chain: the first difference, the per phase
accumulation, the segment boundary, the reserved meter, the backlog step, the
tier that doubles it, the back to back extra, the ceiling, the trailing record,
the one shot credit, the shift wide budget, the ladder order, the four plan
tolerances, the counted verdict set and the two dispositions.

The eight weight-5 tests drive the delivered program over a distinct unseen
shift, generated inside the verifier from a seed, and compare all four reports
byte for byte against a reference derived in the test process. Every one of the
fifty six decisions fires in every one of those shifts, so a single wrong
constant costs all forty of those points together.

The four negative checks are `negative_hardcoded_sample_answers` at -5,
`negative_third_party_dependency` at -3, `negative_filename_dependent_behaviour`
at -3 and `negative_nondeterministic_output` at -3. Each is written with
inverted polarity: the check holds when the cheat is present, so an honest
program fails it and escapes the penalty. Each fires on a different action, so
no single decision is punished twice.

Channel B is `tests/judge.toml`, 16 criteria judged by a language model and
added up by weighted sum. Five are constraints in the instruction following
category and lead the file, each quoting the `instruction.md` sentence it
enforces: four positive trajectory criteria at weight 1 for the held back block,
the rival input, the second calculation and the digest check, and one negative
at -5 for editing a file inside the shipped input directory. Ten are outcome
criteria on the final message, one per closing figure over the recorded shift,
weighted 5, 5, 5, 5, 5, 3, 3, 3, 1, 1. The sixteenth is a conduct criterion at
weight 3 reading the delivered `/app/out/gate.py` as ordinary Python, which the
assertions leave unjudged because they all read what the program writes rather
than how it is written. The positive judged total is 43 and the negative is -5.
No criterion restates a test: no test ever reads the recorded shift, and no
assertion can reach the command history or the agent's own copy of the input
directory.

## Root cause

**The meter column stores a difference, not a level.** Every stage after the
warmup draw reads a figure that appears nowhere in `probes.jsonl`. The
accumulation is the first thing that has to be right, because nothing downstream
can be checked until it is, and it carries three separate rules at once: the
first difference itself, the track being keyed on the phase as well as the
endpoint, and the reserved value that means repeat.

**Scale is a property of the accelerator, not of the column.** One accelerator
records its meter on a wider unit than the others, so two endpoints carrying the
same stored differences resolve to different token levels. Nothing in the column
says so and the worked example never shows it.

**Identity is indirect.** The precision an endpoint is charged at is not always
the precision written beside its variant. A variant that names a base is charged
at the base's precision, so the join runs one step further than the obvious
reading of `variants.csv`.

**State crosses the endpoint boundary once.** Every other piece of carried state
belongs to its endpoint alone, which makes the one exception easy to miss: the
budget a segment boundary installs is derived from the running total of scores
across the whole shift. That single rule makes a per endpoint decomposition of
the work wrong.

**Order inside the chain is load bearing.** Each stage clamps at zero before the
next runs, so a subtracting response followed by an adding one gives a different
answer than the same two applied without the clamp. The verdict ladder consults
its conditions in one order and stops at the first that holds, so a probe that
meets several at once resolves by precedence rather than by combination.

## Solution shape

1. Load the five files of a shift into lookup tables and a probe list, and
   resolve probes in ascending `seq` across the whole shift.
2. Recover the meter per endpoint and per phase: the first probe of a segment
   carries the counter, later probes carry the change from the one before,
   the reserved value repeats the previous level, and a segment boundary clears
   every track the endpoint holds. Scale the result up on the coarse
   accelerator.
3. Compute the batch width from the two count columns and the replay count, take
   the endpoint's budget off the meter, and normalise against the width with the
   fixed gain, truncating towards zero.
4. Apply the precision, accelerator, phase and kernel responses in that order,
   clamping at zero between every pair.
5. Take the endpoint's backlog off the figure, report it as `backlog_before`,
   then apply the trailing record lookup and the one shot credit to reach
   `score`.
6. Band the score, settle the verdict by mode where the mode settles it and by
   the ordered ladder otherwise.
7. Move the endpoint state on: reinstall the budget from the shift running
   total, clear the backlog, arm the credit, or add the backlog step with its
   tier doubling, its back to back extra and its ceiling. Add a strike on a
   rejected probe and push the tag and score into the trailing record.
8. Roll the resolved probes up per endpoint, per charged precision and for the
   whole shift, breaking both ties the documented way, and render the four
   reports in their exact byte forms.

## Ordered plan

1. Read `gate.md` and `reports.md` end to end and write down every stage, every
   piece of carried state and every place the notes say a figure is missing.
2. Resolve the worked example shift against a first reading of the chain and
   compare the rendered verdicts byte for byte with `example_verdicts.jsonl`.
   Iterate on the response tables, the gain, the width and the band edges until
   they reproduce exactly. This settles everything the example can settle and
   nothing that depends on carried state.
3. Set a block of the recorded shift aside, work the carried state rules out on
   the rest, then replay the held back block and check the whole shift against
   the published verdicts digest. This is judge criterion R1.
4. Where two readings both fit, build a small input of your own on which they
   disagree and run both over it rather than guessing. This is judge criterion
   R2.
5. Check the endpoint, precision and shift rollups against their three published
   digests, which settles the counted verdict set, the dispositions and both tie
   breaks.
6. Install the program at `/app/out/gate.py`, run it over `/app/data`, and take
   the sha256 of each of the four files it writes against `digest.json`. This is
   judge criterion R4.
7. Recompute one of the ten closing figures a second time through a walk that
   shares no code with the delivered program. This is judge criterion R3.
8. State the ten figures in the final message, keeping them out of the report
   files. These are judge criteria R6 through R15.

## Pitfalls

- Reading the `meter` column as the meter. Nothing downstream can be right and
  every whole shift test fails, starting with
  `meter_accumulates_as_a_first_difference`.
- Carrying one accumulator per endpoint instead of one per endpoint and phase.
  The shift mostly reproduces and `meter_accumulates_per_phase` fails, as
  does every one of the eight whole shift tests.
- Treating the reserved meter value as an ordinary difference. The accumulator
  drifts from that probe onward and
  `reserved_meter_repeats_the_previous_probe` fails.
- Charging the precision written beside the variant when the variant names a
  base. The worked example never punishes this and all eight whole shift tests
  do.
- Resolving each endpoint on its own. The budget a segment boundary installs
  comes out wrong and `segment_budget_reads_the_whole_shift` fails along
  with the whole shift tests.
- Applying the responses without clamping at zero between them. Only a
  subtracting response followed by an adding one shows it, which the unseen
  shifts construct deliberately.
- Reading the trailing record from the wrong end, or sizing it wrong.
  `repeated_tag_takes_the_recorded_score` fails.
- Reading the throttle comparison as inclusive. An endpoint sitting exactly on
  the figure moves the wrong way and
  `endpoint_dispositions_follow_strikes_and_backlog` fails.
- Baking the recorded shift's answers into the program.
  `negative_hardcoded_sample_answers` fires at -5.
- Reaching for a third party library. `negative_third_party_dependency`
  fires at -3.
- Keying behaviour on the input directory name, or emitting output that varies
  run to run. `negative_filename_dependent_behaviour` and
  `negative_nondeterministic_output` fire at -3 each.

## Notes

- Agent-visible data is flat and holds fourteen files under `environment/data`.
  Expected outputs are never stored under `tests/`; the verifier derives them
  from corpora it generates itself from a seed.
- The worked example holds 130 verdicts over 26 endpoints and the recorded shift
  holds 231 probes over 47 endpoints.
- The worked example is quiet on carried state: every probe on it carries one
  mode, no endpoint builds a backlog, no tag repeats, no variant names a base, no
  segment opens and the coarse accelerator is absent. It settles twenty eight of
  the fifty six decisions, and only as a system, because every one of its twenty
  six endpoints is loaded on at least two of the precision, accelerator and
  kernel axes, so no constant can be divided out of a single score.
- Every band edge, the throttle figure and the sort of the endpoint rollup are
  each met exactly by a fixture, so a boundary moved by one or an order inherited
  from the input file is caught rather than passed.
- Every hidden decision was swept for decidability: 61 live mutations covering
  all fifty six decisions were each applied on their own and replayed. For fifty
  five of them the mutated reading either breaks the published example verdicts
  or leaves at least one of the four digests red; twenty eight break the example
  and the digests together and twenty seven break only the digests. The fifty
  sixth, the end of the trailing record the replay lookup reads from, is one no
  shipped file can settle, because no tag in either shipped shift is held in the
  record twice at once, so `gate.md` states that end outright and the checks
  grade it directly. The sweep also flips every strict against inclusive
  comparison in the gate.
- One ordering carries no information and is deliberately not claimed as a
  decision: a probe cannot be both a bookkeeping mode and the abandoning mode, so
  the relative order of the `setup` and `void` outcomes is unobservable and any
  reading of it scores the same.
- The oracle holds nine endpoints back and fits the constants on the other
  thirty eight, separates two rival trailing record depths on a five probe shift
  of its own, and recomputes `total_backlog` through a second walk over the
  probes that shares no code with the gate.
- Score shape of Channel A, as a fraction of its positive total of 93 with no
  negative firing: every live single-decision mutant keeps between 0.0323 and
  0.5699, and the top of that range is what matters, because the eight whole
  shift checks are all or nothing and every decision fires in every one of them.
  Reading the wrong end of the trailing record reproduces every shipped file and
  keeps 0.5376. A solver that reproduces the worked example byte for byte and
  gets everything the example cannot teach wrong keeps 0.1398. A three-decision
  miss keeps 0.4839, a five-decision miss 0.3871 and a ten-decision miss 0.0968.
  `tests/reward.toml` halves each of these before adding Channel B.

## Provenance

```yaml
uuid: ddaa03ec-f499-5df6-985e-483b7532b985
instance_id: inference-gate-replay
task_name: terminal-bench/inference-gate-replay
fix_patch_sha256: 5f8fbe5714df66ab1b8fb7eaab48e4ad1a57a97f8f53a4f563c20077de7c95c5
solve_py_sha256: 4c978c4c83cdc9bdf95b8080d6a52c02228a8326da359b81fa44cb951c617a41
language: python
status: ready
```
