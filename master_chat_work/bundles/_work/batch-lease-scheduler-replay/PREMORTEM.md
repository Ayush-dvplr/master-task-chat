# PREMORTEM: batch-lease-scheduler-replay (board 98c5c50)

Written before any other WORK file. Part A is the reflex walk-through; Part B is
the measured run of the first-write program on the hidden corpora (appended after
`engine/premortem_run.py` ran).

## A. How claude-opus-5 solves this in its first 10 minutes

1. `ls /app/data`, reads `instruction.md` again, opens `replay_contract.md` in full
   (it is the only rules file), then `unzip -l project.zip`, unzips to a scratch dir,
   reads `pyproject.toml`, `src/leasebook/*.py` and `tests/test_*.py` in that order.
2. Runs the shipped tests: they pass or fail on packaging (wrong package dir in
   pyproject, missing `__main__`, version mismatch). It fixes packaging first, then
   runs `python -m leasebook /app/data /tmp/o` and hits the parser defects
   (tsv split on commas, blank jsonl line crash, wrong ini section, ids sorted as text).
   It fixes those in place.
3. It then compares `replay.py` against the contract sentence by sentence. Two
   sub-paths:
   - (R) repair in place: it keeps the shipped event loop and patches what it sees
     contradict a sentence. The shipped loop drains internal events only when an
     external event arrives, counts preemption as an attempt end, applies stale
     tokens, releases dependents on any terminal parent and has no redelivery check.
     Opus spots most of these by reading, because each one contradicts a plain
     sentence. What it keeps is the loop structure: a heap of scheduled internal
     events plus the sorted external stream.
   - (W) rewrite: it writes its own event-heap replay from the contract (this is the
     "first-write program" below). Opus prefers a heap over a unit-step loop because
     times run to 5000 and it "is cleaner".
4. Its first-write heap program: a heap of `(t, phase, seq, kind, job, token)`;
   completions are scheduled at `start + remaining`, expiries at `deadline`,
   retry-ready at `t + delay`; external events are merged by `(t, 4, id)`; after the
   last entry of each instant it runs dispatch; checkpoints are sampled after the
   dispatch of their instant. Stale heap entries are skipped with a guard.
5. Self-tests it runs: the shipped package tests (tiny fixtures, no coincident
   instants, no preemption during a lease); `python -m leasebook /app/data /tmp/o`
   on the shipped book and eyeballing a few sets; 2 or 3 hand-made 3-job examples;
   invariants it thinks of: no worker runs two jobs, completed + dead + cancelled +
   other = job count, executed = sum of run lengths. None of these has an oracle for
   the exact documents; the shipped book has no expected output (W11).

## B. Where the first-write program goes wrong, per lever

The first-write slips are the natural bugs of a heap replay of these rules. Every
one contradicts a stated sentence; none is caught by the self-tests in A5 because
each needs two internal events of the same job to interleave with an external one.

- LV-BS-1 (exact replay across timestamps)
  - FW-1 completion guard: a completion entry is skipped unless `state == running
    and attempt == token`. Preemption keeps the attempt, so after preempt + resume
    the old completion entry fires at its old time and completes the job early.
    Shipped book: preemption only in a few small sets and resumes rarely land before
    the old completion time; the job still "completes", counts stay plausible.
  - FW-2 heartbeat at the lease deadline: opus reads "heartbeat renews the lease" and
    "expiry at the deadline"; with the heap it pushes the expiry entry when the lease
    is set and, when a heartbeat arrives, records the new deadline; the old expiry at
    `t == old deadline` is in phase 2 and the heartbeat in phase 4 of the same instant.
    The contract order settles it (expiry first, heartbeat then stale). The reflex
    reading "a heartbeat at the deadline saves the lease" survives in programs that
    check `deadline <= t` lazily when the next entry pops, after the external event.
  - The (R) path keeps lazy draining of internal events in quiet stretches for one
    of the three internal kinds (typically retry-ready, which is pushed into the
    external stream in the shipped code).
- LV-BS-2 (attempt accounting)
  - FW-3 lost work: `lost += ticks of the current run` at attempt end, instead of
    `work - remaining`; differs only when the attempt was preempted or evicted before
    it ended. FW-3b cancel of a running job uses the stored remaining from the start
    of the run (heap programs only update remaining at preemption).
  - FW-4 heartbeat or fail on a preempted (queued) job with the current token: the
    guard `attempt == token` passes and the event applies (renews a lease that does
    not exist or ends an attempt that is not running).
- LV-BS-3 (dependency outcomes)
  - FW-5 cascade skips unsubmitted dependents (opus cascades over "jobs in the
    system" and rejects the later submit instead of auditing it as finished).
  - PRECSWAP audit precedence: a heartbeat for a preempted job with an old attempt
    token is audited `not_running` (state checked first) instead of `stale_attempt`.
    The contract states the precedence; the reflex guard order is "is it running?".

FW-6 (release one instant late) was dropped: the stated order releases at the
completion phase and at submit, and a heap program gets it right by construction.

Self-tests miss every slip: the shipped book has no expected documents, the package's
own tests have no coincident instants, and every invariant opus checks holds under
each slip (worker capacity holds; state counts sum; executed equals run lengths).

## C. Measured (engine/premortem_run.py, 23:29-23:45)

Hidden corpora: 5 seeds (11, 22, 33, 44, 55) x 3 sets, 80-140 jobs, 8-24 workers,
525-905 events, 10-20 checkpoints. Reference (unit-step) and clean heap agree on
every hidden and shipped set. Documents per corpus: core, metrics, deps, summary.

| program | hidden corpus docs wrong (of 4) per seed | hidden set-docs wrong (of 60) | shipped 400-set book sets differing |
|---|---|---|---|
| clean heap | 0 0 0 0 0 | 0 | 0 |
| FW1 completion guard by attempt | 4 4 4 4 4 | 59 | 72 |
| FW2 external before internal | 4 4 4 4 4 | 60 | 0 |
| FW2R checkpoint remaining not interpolated | 1 1 1 1 1 (core) | 15 | 397 |
| FW3 lost = current run ticks | 2 2 2 2 2 (metrics, summary) | 30 | 13 |
| FW3b cancel uses stored remaining | 3 3 3 3 3 | 45 | 0 |
| FW4 heartbeat/fail on preempted job applies | 4 4 4 4 4 | 60 | 0 |
| FW5 cascade skips unsubmitted | 4 4 4 4 4 | 60 | 4 |
| LAZY internal events at next external t | 4 4 4 3 4 | 59 | 399 |
| PREFAIL preemption = attempt end | 4 4 4 4 4 | 60 | 149 |
| STALE stale token applied | 4 4 4 4 4 | 60 | 0 |
| ANYTERM release on any terminal | 4 4 4 4 4 | 60 | 37 |
| SUBORDER dispatch tie by submit order | 4 4 4 4 4 | 60 | 41 |
| REDUP redelivery applied twice | 4 4 4 4 4 | 60 | 0 |
| PEREVENT dispatch after each event | 4 4 4 4 4 | 60 | 88 |
| PRECSWAP audit precedence swapped | 2 2 2 2 2 (core, metrics) | 30 | 0 |
| FIRSTWRITE = FW3b + FW4 + FW5 | 4 4 4 4 4 | 60 | n/a |

Verdict: the first-write program is wrong on every hidden set and every document;
no redesign needed. The shipped book cannot confirm any slip (no answers ship);
FW2, FW3b, FW4, STALE, REDUP leave the shipped book unchanged (hidden-only).
A careful unit-step simulator would be exact: hardness rests on interaction slips
and anchored repair of the shipped loop; the probe decides real hardness.
