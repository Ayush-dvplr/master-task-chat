# TRUTH.md - batch-lease-scheduler-replay

## Defect

The zipped package `leasebook` (`/app/data/project.zip`) replays books of batch
scheduler logs, and `/app/data/replay_contract.md` is its contract. The shipped
package breaks the contract in its replay core, in its loader and in its
packaging. Its own replay tests pass, because their tiny fixtures never put two
kinds of event on one instant and never preempt a job during a lease.

- (focal) Lazy replay loop. `replay.py` visits only the times that carry an
  external event or a checkpoint. At such a time it applies the external events
  first and only then pops the completions, lease expiries and retry-ready times
  that fell due, so a job that finished between two log lines frees its worker
  late, a heartbeat sent at the exact lease deadline rescues a lease that has
  already expired, and dispatch sees a stale queue. The contract (section 4)
  makes every whole-number time an instant with four phases: completion,
  expiry and retry, external events by ascending id, dispatch.
- (focal) Attempt accounting. A preemption ends the attempt (retry limits run
  out early and work restarts from zero), heartbeat and fail rows are applied
  whatever attempt token they carry, and a completion timer is guarded by the
  attempt number only, so a job preempted and resumed inside one attempt
  completes at its old, earlier time. Contract section 3 keeps remaining work
  and the attempt across preemption and eviction; section 5 audits a token that
  differs as `stale_attempt` and a row for a job that is not running as
  `not_running`.
- (focal) Dependency outcomes. Dependents are released when every parent is
  terminal in any way, a dead or cancelled job cascades to nothing, and a
  redelivered copy of an event is applied again (a copied `boost` adds its delta
  twice). The contract releases only on completed parents, cascades cancellation
  to every direct or indirect non-terminal dependent and audits copies as
  `redelivery`.
- (drift) Smaller replay and report faults: cancelling a running job charges the
  lost work from the remaining work stored at the start of the run, dispatch
  breaks priority ties on the text form of the job id, and `dispatch_sha256`
  hashes lines joined with commas instead of single spaces.
- (drift) Loader faults: `jobs.tsv` is read with a comma delimiter, a blank line
  in `events.jsonl` crashes the reader, the retry delay is read from a
  `[backoff]` section with a fallback of 3 (the shipped policy says 4), event id
  conflicts are never detected, and the cycle check runs before the unknown
  entity check, which inverts the stated refusal order.
- (drift) Packaging faults: `pyproject.toml` looks for packages under `lib`,
  there is no `__main__.py`, `main` is not exported from the package, and
  `__version__` is 1.3.2 while `[project] version` is 1.4.0.
- (trap) The shipped replay tests (`tests/test_replay.py`) pass on the broken
  engine, and the shipped book never contradicts a lazy reading in a way the
  package can see, so green shipped tests and plausible documents prove nothing
  about the replay core.

## Load-bearing work

1. Rebuild the replay loop so that every instant from 0 to the last checkpoint
   runs the four phases in the stated order, with timers firing at their own
   time even when no log line carries that time.
2. Track a run token per start, so a completion or expiry belonging to an
   earlier run of the same attempt never fires after a preemption or eviction.
3. Keep the attempt and remaining work across preemption and eviction; end an
   attempt only on fail or lease expiry; charge lost work as work minus the
   remaining work at the moment the attempt ends or the job is cancelled.
4. Apply section 5 as an ordered table: redelivery, worker rows, finished,
   submit, boost, cancel, stale_attempt, not_running, heartbeat, fail.
5. Release dependents only when all parents completed; cascade cancellation from
   dead and cancelled jobs through waiting and unsubmitted dependents.
6. Fix the loader and the refusal order (MISSING_INPUT, INVALID_POLICY,
   UNKNOWN_ENTITY, EVENT_ID_CONFLICT, DEPENDENCY_CYCLE), then the packaging,
   and ship `/app/out/package.zip` with `selftest.json` and `build_report.json`.

## Verification

The test channel (tests/test_output.py) has 37 checks: 35 positive checks with a
positive weight total of 139 and two negative checks,
`negative_package_reads_grader_paths` (-5) and
`negative_hardcoded_sample_answers` (-3). The package is extracted from
`/app/out/package.zip` and run as `nobody` from a foreign working directory
with `python -I`, under a 60 second limit per book.

- Four hidden books of three sets each are drawn verifier-side by an embedded
  seeded generator inside the contract's bounds (asserted per value), with
  coincident completions, expiries and retry-ready times, heartbeats and fails
  at lease deadlines, preemption then resume, double preemption followed by
  expiry, tokens on preempted jobs, stale tokens after a retry starts, cancels
  of resumed and preempted jobs, cascades through chains of four or more,
  redelivered boosts and cancels, and equal-priority victims with equal start
  times. Each of the four documents of each hidden book is compared whole
  (16 checks, weight 5 each); the expected documents come from an embedded
  unit-step replay of the written files.
- Mutated reruns: rows reshuffled with blank lines and an unrelated file (core
  document, 5), lease and retry delay changed on a 40-set slice of the shipped
  book (summary, 5), two runs with a different hash seed and directory (3).
- The four shipped documents in `/app/out` against the reference (3 each),
  worker capacity and state invariants on hidden output (3 each), one refusal
  check per code with a lower-precedence defect planted alongside (3 each), and
  package checks: artifacts present (1), call and `python -m` agree (3),
  `selftest.json` equals a rerun of the archive's tests (3), `build_report.json`
  members, digest and versions (3), shipped test files kept unchanged (3).
- The judged channel (tests/judge.toml) has 9 criteria with a positive total of
  24 and one negative, `claims_unshown_pass` (-3). Each half of the reward is
  that channel's weighted sum divided by its positive total.
- Timing in Docker (python:3.12-slim, digest
  sha256:cb33f7f771ecec2ef1225cf39b159591a040391bd73e4c01f00fdfc4c47611d2) on a
  four-set book at the stated bounds (160 jobs, 24 workers, 1100 event lines,
  last checkpoint 5000 per set): reference package 0.36 s, plain unit-step
  simulator 1.47 s, against the stated 60 second limit.

## Root cause

The shipped engine was written as a log-driven loop: it treats the event log as
the clock. That works on the shipped package's own fixtures, where every
internal event happens to sit on a logged time, but the contract defines time
by instants, not by log lines. Every later document of a set is computed from
the replayed timeline, so one deferred completion moves the dispatch order, the
attempt counts, the dependency outcomes and the summary digest of that set.

## Solution shape

`solution/solve.py` unpacks `project.zip`, writes the repaired package sources
(a timer-heap engine with run tokens, a strict loader and the stated refusal
order, `__main__.py`, an exported `main`, matching versions), packs
`/app/out/package.zip` deterministically, extracts it again, runs its unit
tests to write `selftest.json`, writes `build_report.json`, and runs
`python -m leasebook /app/data /app/out`. A self-check stage then recomputes
worker occupancy, run counts, edge outcomes, the dispatch digest and the archive
digest from the written files and prints `check C1 ok` to `check C5 ok`, and
reruns the package on a copy of the book with an edited policy, printing
`check J9 ok` when the summary moves. solve.py has 843 lines.

## Ordered plan

1. Read the contract in full; unzip the package and run its tests.
2. Fix packaging and loader faults until the shipped tests run.
3. Rewrite the replay loop around instants and the four phases.
4. Add run tokens; fix preemption, eviction, attempt ends and lost work.
5. Implement section 5 in order, the cascade and the completed-only release.
6. Fix the refusal order and messages.
7. Write the archive, selftest.json and build_report.json; replay the book.
8. Recompute figures outside the package and rerun on an edited copy.

## Pitfalls

- (trap) Trusting the shipped replay tests or the look of the shipped
  documents: neither separates the lazy loop from the contract.
- Guarding completion timers by attempt only: a resumed job completes early.
- Processing a heartbeat at the lease deadline before the expiry.
- Treating a token heartbeat on a preempted job as a renewal.
- Cancelling an unsubmitted dependent only when its submit arrives, instead of
  at the cascade time.
- Reading `remaining` at a checkpoint as the value stored at run start.

## Provenance

Digests, computed after the last edit under tests/ and solution/:

solve.sh: 5360d68661ba101b6964906da09ff00b8e84af6ff034fbc22cc3c6f87a611062
solve.py: 3adb97b47ddf9145b6ccb4f9505da4702fc731674571e95ed546551b295906b2
test_output.py: de68a12dd01ebe3c6b2867b564db0045f9e898b37aafe939168fcd44b8fc8ebf
judge.toml: 678a81a6d5e7bca268b053035e769bfc831e6395b8886f85c1549593560408a0
project.zip: a9458b5ee8e2e7f65ea92c77611aaa3648b8447008c74438c390c4c2f83dfc2e
replay_contract.md: 7c99061749ebae263641912a2b64888ccd7620c566f5196992dadf1f2d78f618

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: batch-lease-scheduler-replay
task_name: terminal-bench/batch-lease-scheduler-replay
fix_patch_sha256: 5360d68661ba101b6964906da09ff00b8e84af6ff034fbc22cc3c6f87a611062  # sha256 of solution/solve.sh
solve_py_sha256: 3adb97b47ddf9145b6ccb4f9505da4702fc731674571e95ed546551b295906b2
language: python
golden_score_measured: 1.0
golden_score_channel_a_pct: 100.0
golden_score_channel_b_pct: null
golden_score_runs: 3
golden_score_trial_id: null
golden_score_verified_by: >
  Harbor oracle runs on the test channel only, with the judged channel removed
  from a temporary copy: oracle rewards 1.0, 1.0, 1.0, no-op reward 0.0.
caveat: >
  The test channel carries 35 positive checks worth 139 and 2 negative checks
  worth -8; the judged channel carries 8 positive criteria worth 24 and one
  negative worth -3. tests/reward.toml divides each channel by its positive
  total and gives each half of the reward.
```
