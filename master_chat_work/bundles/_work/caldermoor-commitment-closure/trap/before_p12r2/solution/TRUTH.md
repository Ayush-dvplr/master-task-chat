# TRUTH.md - caldermoor-commitment-closure

## Defect

The task breaks two assumptions at once. Identity is not a global partition:
an alias assertion is valid only in its half open interval, so the same folded
surface may denote different principals at different instants or become
ambiguous where intervals overlap. And a row does not carry one instant: the
obligor of an assertion resolves at its `observed_at`, its obligee at its
`due_at`, a dependency edge at its `asserted_at`, and a cadence obligor at its
`anchor_at`. Every one of those four is named by a different rule in a
different document.

The focal rules are scoped alias resolution, per reference resolving instants,
edge time endpoint resolution, the two inverting precedence classes, terminal
state transitions, and circular holding components. The drift rules are the
04:00 day boundary, the hour units in two layouts, the exact spelling of the
unit field, per assertion effort clamping, and time scoped project renames. The
traps are half open interval ends, waiver streak preservation, the second
allocation pass, retired feed timing, malformed row ordering ahead of every
later code, canonical tie ordering, cadences owned by nobody, the four part
escalation predicate, the blocked predicate that ignores the dependent's own
state, the first-match cadence walk that never counts a discharged period as
waived, and one waiver allowance per principal shared by its cadences and drawn
by every waiver in an elapsed period. A reserve taken from each envelope for
blocked commitments and waived periods carries those three into allocation and
every deliverable that reports allocated minutes. Each rule changes records in the supplied extract and is
checked by exact or rule specific verification.

## Load-bearing work

The solver must parse eight feed layouts and the governing registers; normalize
principal surfaces, project codes, effort, and days at the correct instants,
which differ per reference; apply the ordered rejection rules with every
malformed row condition ahead of retirement and the window; walk legal state
transitions under two classes that read their rank backwards; partition
dependency edges; compute reachability and circular components; classify
commitments; calculate cadence debt and attribute it to the principal each
cadence obligor stands for at its anchor, spending each principal's waiver
allowance in period start order; take the reserve from each envelope and
distribute the rest of monthly attention by largest remainder with a floor and
one redistribution pass; then derive the
escalation queue, rollups, provenance, audit totals, and five identities.

The stages are coupled. Identity changes edge liveness, edge liveness changes
the closure, the closure changes commitment class, the 04:00 boundary changes
the settlement month, clamped effort changes allocation, cadence ownership
changes the debt that gates escalation, and all of them feed escalation. A
locally plausible shortcut therefore produces a coherent but globally wrong
closure.

## Verification

The verifier has an independent extract builder and rules engine. It recomputes
the twenty-eight generated output artifacts for the supplied extract and
compares them byte for byte. It also runs the delivered program on three
held-back extracts, where fourteen checks each compare one family of
deliverables, and on thirteen separate hidden rule probe extracts, so a solver
tuned to a single corpus passes none of the others. The shipped extract leaves
out the edges and waivers on which the blocked predicate, the waived count and
the allowance readings part; every held-back and probe extract keeps them. Each
program run is bounded, its process group is terminated on timeout, and Linux
runs execute as `nobody` with no privilege to modify verifier files or rewards.
Every successful held-back run must contain exactly the twenty-nine declared
artifacts and no directory or file beyond them, the reusable program included.

Grading runs `rewardkit /tests --workspace /app` from `tests/test.sh`.
`tests/test_output.py` registers 49 checks, one `@criterion` check per test,
and each check passes when its test raises nothing. They are 44 positive checks
worth 162 points and five negative checks. The positive distribution is sixteen
checks at weight 5 (the fourteen held-back family checks, the escalation queue
and the class partition), twenty-seven at weight 3 (the fourteen shipped family
checks among them), and one at weight 1. One positive check makes publication impossible by
occupying the `run_manifest.json` path in a pre-existing output directory and
passes when the run either replaces the directory whole or exits nonzero
leaving no file behind. The negative checks are
`negative_hardcoded_sample_answers`,
`negative_filename_dependent_behaviour`,
`negative_mutates_input_extract`,
`negative_environment_dependent_output`, and
`negative_directory_iteration_order`. The last three compare runs made at one
workspace path and first repeat the unperturbed run, so only the perturbation
itself can fire them, and a program that varies between identical runs loses
the determinism check alone.

`tests/judge.toml` holds 12 judged criteria in batched mode, worth 22 positive
points and 12 negative points, and `tests/reward.toml` gives the tests channel
and the judge channel half of the reward each: the tests weight is 0.5 divided
by the 162 positive test points and the judge weight is 0.5 divided by the 22
positive judge points. The positive criteria cover the two stated rules of
engagement (staging before publication, standard library alone), one concrete
code quality criterion on the delivered program, four self checks the agent
runs on inputs it builds itself (a settled or withdrawn commitment holding a
live edge to a holding blocker, a waiver in a discharged period, a second
extract placed outside `/app/data`, and one principal's cadence carrying more
waivers than its allowance), and a final answer that lists every file
written under `/app/out`. The four negative criteria penalize a stated closing
figure that no command computed, a completion claim the trajectory contradicts,
rerunning one failing command three or more times, and a claim that a check
passed with no run after the last edit to the program (R11 stands down when
R9 already prices the same completion claim, so one act costs at most 3). No criterion pays for a
figure any deliverable carries or restates a rule the tests grade.

The reference shows each judged act: `solution/solve.sh` stages and publishes
through the program, which imports the standard library alone, then runs a
self check that builds four small extracts in a temporary directory, runs the
delivered program on each, prints the line it checked, and lists every file it
wrote under `/app/out`. The self check writes nothing under `/app/out`.

## Root cause

The raw feeds describe assertions, not final entities or states. Their meaning
depends on the observation or assertion instant named by each rule, and the
rules name four different instants for the four kinds of reference. Treating
aliases, project names, feeds, cadence owners or dependencies as timeless
erases distinctions the protocol deliberately preserves. The correct closure
therefore requires temporal resolution before graph construction and requires
every later total to be derived from that resolved graph.

## Solution shape

The reference is one Python standard-library program. It reads only the
supplied input directory, computes the closure in memory, writes the program
artifact plus twenty-eight generated artifacts into a sibling staging
directory, and atomically replaces the requested output directory only after
all files are complete. If computation or emission fails, the staging directory
is removed and any prior output directory is restored.

The alias resolver walks live arcs breadth first, so the first path that
reaches the unique canonical handle carries the fewest hops. Graph components
and reachability are computed after edge scoping. Serialization is
deterministic, uses the contract orders, LF line endings, trailing newlines,
compact sorted-key JSONL, and indented sorted-key JSON.

## Ordered plan

1. Read the protocol and the seven documents it names.
2. Load the roster, aliases, project registry, rename events, feed manifest,
   cadence register, waivers, and attention budgets.
3. Implement the comparison fold and the temporal alias resolver.
4. Parse all feed layouts while retaining file and row provenance.
5. Normalize commitments, resolving the obligor at `observed_at` and the
   obligee at `due_at`, and apply the rejection order with every malformed row
   condition tested first.
6. Choose commitment winners and walk state transitions in charter order, with
   the journal class inverted everywhere and the sweep class inverted for state
   rows alone.
7. Resolve edge endpoints at the claim instant and partition live and dropped
   edges.
8. Compute blocking reachability, frontier depth, and circular components.
9. Classify commitments and calculate cadence debt, attributing each cadence to
   the principal its obligor resolves to at the anchor and spending that
   principal's allowance of four waivers by period start, then cadence id.
10. Take the reserve from each envelope, then allocate the rest of monthly
    attention with largest remainder, floor, and second pass.
11. Build escalation, rollups, provenance, audits, and validation identities.
12. Serialize all artifacts to staging, copy the program in, and publish the
    directory atomically.
13. Run the program on the supplied extract, then on small extracts built in a
    temporary directory: one keeping only a live edge from a settled or
    withdrawn commitment to a holding blocker, one keeping only a waiver in a
    discharged period, one copy without the eight documents, and one keeping
    only the waivers of one cadence with more than four, and check the blocked
    line, the inert waiver, byte equal outputs and the lapsed waivers.

## Pitfalls

A global alias merge silently assigns valid rows to the wrong principals.
Resolving the obligee at the row instant, or the edge endpoints at commitment
observation time, keeps claims that were out of scope. Uniform precedence
changes terminal states, and so does inverting the sweep class where its
commitment rows compete. Reading unitless layouts as minutes shrinks effort
before clamping, and folding the case of the unit field accepts rows the
protocol refuses. Midnight settlement moves pre-dawn commitments into the wrong
day and sometimes the wrong month. Resetting a streak on waiver, closing
interval ends, flattening cycles into ordinary blocks, matching a cadence
obligor by its handle alone, testing retirement ahead of the malformed row
conditions, omitting the allocation floor, or dropping the last escalation
predicate each yields plausible output that exact cross artifact checks reject.
Taking the blocked set from the class alone drops settled and withdrawn
dependents that still carry a block; counting a discharged period as waived, or
letting only suppressing waivers draw on the allowance, shifts the waived count
and the lapses; each of those moves the reserve and so every allocated figure.

The output directory is also contractual data. Extra files, empty directories,
environment-derived bytes, input mutation, filename-dependent behavior,
non-deterministic traversal, partial publication, or omission of the reusable
program from the output directory violate the task even when individual tables
look correct.

## Provenance

Task `caldermoor-commitment-closure`. SHA-256 of the shipped files this
document describes:

```
64feac86a5076eee581f2cc6566478c3b3edb9bdc5390e7e305c5e137997459c  instruction.md
dc2f7f7c4606bdfc60ad57729b4887b9d46ce6dabe635d160e42d0cdf68b5c80  task.toml
b11079d416d14c9b2768f46908c1a744cd812fb8deec469973db1c1a54d31638  environment/Dockerfile
7c4b1c0ffc39760f188647093120d23070b0281924265d1b7a13c972a9159db4  solution/solve.sh
b1d4e9fa8dfd5f20479f3630111611fc9576fced04a67728c5792bdb80310fa0  solution/solve.py
fed10417e97b6746957a942dcc1a378c72378671075674d54ef72fb5c6577feb  tests/Dockerfile
5302b9b87341ed25694888cd4c3392a46a6bd25b6f1a31fd1c6e9e109d46efd8  tests/test.sh
b128d666998e499a981a4d9324000493dab3856eb3b1b3cb4113deab12d5a27e  tests/test_output.py
7f88a812edaff351e9cff352e673d4c9c3ce70ed9a0378219d73368639accbc1  tests/judge.toml
ba426acc5bbfa2397083b29d988500a8caccad6a4c50948d2c940aeb30e1e806  tests/reward.toml
```

`environment/data` holds 54 files. The SHA-256 of the `shasum -a 256` listing of
those files, taken inside that directory in byte order of their `./` paths, is
`1f80c1cc753126b3b32186b7160ab1cfc4be49416138cfae5936e9ba8b169b77`.
