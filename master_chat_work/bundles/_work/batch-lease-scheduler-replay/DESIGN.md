# DESIGN 98c5c50 batch-lease-scheduler-replay (build-repair, software-engineering, seed 413927)

Core build (Ayush 25 Oct '2'): difficulty is the exact discrete-event replay. No secondary
stated-rule lever. Gate notes G-1..G-9 of IDEA.md applied. Measured pre-mortem: PREMORTEM.md C.

## 1. Spine

1. Repair the zipped package `leasebook` (project.zip): packaging defects (pyproject package
   dir, missing `__main__`, `main` not exported, version mismatch) and parser defects (tsv split
   on ",", ids sorted as strings, blank jsonl line crash, wrong ini section name).
2. Validate the book, in the stated rejection precedence (section 5).
3. Replay every set over the integer clock 0..last checkpoint with the stated instant order.
4. Derive module_core (checkpoint states, dispatch log, audit), module_metrics (per-job work and
   attempt totals), dependency_resolution (edge outcomes, releases, cascades) and summary
   (final state counts, executed, lost, dispatch_sha256) from that one timeline (COUPLING).
5. Ship out/package.zip; run the package's own tests (selftest.json); describe the archive
   (build_report.json); run the package on /app/data to write the four documents to /app/out.

## 2. Input files (flat in /app/data, 10 files, 8 formats)

| file | format | rows (shipped) | content |
|---|---|---|---|
| project.zip | zip | 12 members | src/leasebook/{__init__,__main__?,book,replay,report}.py, tests/test_*.py, pyproject.toml |
| replay_contract.md | md | ~170 lines | the one contract: inputs, bounds, states, instant order, dispatch, attempts, dependencies, outputs, errors |
| policy.ini | ini | 8 | [lease] ticks, [retry] delay (one policy per book) |
| pools.json | json | ~15 | {"pools":[{"pool","preempt"}]} 4-6 pools, one not preemptive |
| workers.csv | csv | ~2300 | set,worker,pool,state (up/down at t=0) |
| jobs.tsv | tsv | ~5500 | set job pool priority retry_limit |
| durations.csv | csv | ~5500 | set,job,work |
| dependencies.csv | csv | >=2000 | set,parent,child |
| events.jsonl | jsonl | ~19000 | {"set","id","t","type",...} |
| checkpoints.txt | txt | ~2500 | "set time" |

Book: 420 sets (A5 >= 20,000 lines; >= 2,000 per csv/tsv/jsonl/txt; datagen asserts).
Every file feeds a graded document. Ids are neutral integers (DS-4). Chains (>= 4 links):
- C1 policy.ini lease ticks -> lease deadline per run -> expiry -> attempt end/backoff -> retry dispatch -> module_core dispatches -> summary dispatch_sha256.
- C2 dependencies.csv -> waiting -> release at parent completion -> queued -> dispatch/preemption of a lower job -> module_metrics preemptions -> summary executed.
- C3 events.jsonl cancel -> cascade through dependents (waiting, unsubmitted) -> dependency_resolution broken/cascaded -> later submit audited finished -> module_core audit -> module_metrics totals.audit.
- C4 pools.json preempt flag + jobs.tsv priority + durations.csv work -> victim choice -> remaining kept -> completion time -> dependency release time -> checkpoint states.
- C5 workers.csv state + worker_down/up events -> eviction -> lost/evictions -> summary lost.

## 3. Levers (all rules in replay_contract.md, W2/W10; instruction states no rule)

### LV-BS-1 exact replay across timestamps
- Rule text (contract "Instants"): "The replay visits every integer time from 0 to the set's last
  checkpoint. At each time it runs, in this order: (1) completions, (2) lease expiries, (3)
  retry-ready, (4) external events in ascending event id, (5) dispatch. Dispatch runs once, at
  the end of every time." Plus dispatch order (priority desc, job id asc), victim (lowest
  priority, then latest start, then larger job id), "a job preempted during dispatch waits for
  the next time", checkpoint = state after the whole time.
- Reflex reading (PREMORTEM): repair keeps the shipped loop that drains internal events only
  when the next external event arrives (LAZY), or puts externals first (FW2), dispatches after
  each event (PEREVENT), guards completions by attempt only (FW1), copies stored remaining at a
  checkpoint (FW2R), ties dispatch by submission (SUBORDER).
- Hidden cases (generator plants against a live reference): heartbeat or fail at the exact lease
  deadline; completion and expiry and retry-ready at one time; higher-priority submit at a
  retry-ready time; preemption then resume before the old completion time; quiet stretches with
  internal events and no external line; equal-priority victims with equal start.
- Why visible data cannot confirm: no expected documents ship (W11); the shipped book has few
  coincident instants and the package tests use none; FW2 leaves all 420 shipped sets unchanged.
- Interactions: a late completion shifts every later dispatch, which moves LV-BS-2 attempt
  counts and LV-BS-3 release times in the same set.

### LV-BS-2 attempt accounting
- Rule text (contract "Attempts"): an attempt ends only by failure or lease expiry; preemption
  and eviction keep the attempt and the remaining work; an ended attempt adds work minus
  remaining to lost; attempt limit retry_limit+1 then dead; heartbeat/fail apply only to a
  running job whose current attempt equals the event's attempt; audit reason precedence
  redelivery > finished > stale_attempt > not_running.
- Reflex reading: PREFAIL (preemption ends the attempt, as the shipped code does), STALE (old
  token applied), FW3 (lost = current run ticks), FW3b (cancel uses remaining stored at run
  start), FW4 (heartbeat/fail on a preempted queued job with current token applies), PRECSWAP.
- Hidden cases: stale heartbeats and fails after a retry is dispatched; current-token heartbeat
  on a preempted job; cancel of a running job mid-run after a preemption; jobs preempted twice
  then expiring.
- Visible: no answers; STALE, FW3b, FW4 leave the shipped book unchanged.
- Interactions: an early dead job cascades (LV-BS-3); a wrongly renewed lease shifts dispatch.

### LV-BS-3 dependency outcomes
- Rule text (contract "Dependencies"): a child is released only when every parent completed;
  dead or cancelled parents cancel every non-terminal transitive dependent, including
  unsubmitted ones, at that time; a later submit of a cancelled job is audited finished; an
  identical copy of an event line has no effect beyond its audit row.
- Reflex reading: ANYTERM (release on any terminal parent, the shipped code), REDUP (boost or
  cancel copy applied twice, the shipped code), FW5 (cascade skips unsubmitted).
- Hidden cases: cancels on parents of unsubmitted children; deaths of parents with chains of 4;
  redelivered boosts (relative delta) and cancels.
- Visible: no answers; REDUP leaves the shipped book unchanged.
- Interactions: a wrong release frees a worker for another job, shifting LV-BS-1 dispatches.

No L5/L11 lever, so no separating case ships and no UNIQUENESS.md.

## 4. Stated bounds (contract) and generator
Per set <= 160 jobs, <= 24 workers, <= 1200 event lines, times 0..5000, work 1..60, priority
0..9 at submit (boosts may leave it anywhere), delta -3..3 nonzero, retry_limit 0..3; policy
lease 2..20, delay 1..10; each job submitted at most once apart from identical copies;
worker_down only names an up worker, worker_up only a down one; every event time <= last
checkpoint; >= 1 checkpoint per set; <= 500 sets per book. Time limit stated: one run of the
package on a book of up to 4 sets at these bounds finishes within 60 seconds.
Hidden generator (embedded in tests, seed only in tests): profile hidden in PREMORTEM C, asserts
every drawn value inside the bounds, branch counters assert every multi-branch rule fires
(phase pairs, victim tie levels, all 4 audit reasons, all 3 edge outcomes, eviction, dead,
redelivery of each type); 300 seeds survive (Phase 4).

## 5. Rejection paths (exactly one stdout line, exit 2, no document written)
Precedence: MISSING_INPUT > INVALID_POLICY > UNKNOWN_ENTITY > EVENT_ID_CONFLICT >
DEPENDENCY_CYCLE. `ERROR MISSING_INPUT <file>` (first missing in the contract's file list
order), the rest `ERROR <CODE>`. Each rejection test plants its target plus a lower-precedence
defect, on a hidden-generated book.

## 6. Test plan (LEVER_RULES G1-G12)
Expected documents come from the embedded unit-step reference run on verifier-generated books.
The agent's package is extracted from out/package.zip and run as `nobody` from /tmp (G8).

| id | check | w | family |
|---|---|---|---|
| H1..H4 x {core,metrics,deps,summary} | whole document exact on hidden corpus k (3 sets each) | 5 x16 | hidden whole-doc |
| M1 | rows of every file shuffled where order carries no meaning, event ids kept: module_core exact | 5 | mutation (G6 rotate rows) |
| M2 | policy.ini lease and delay changed on a 40-set slice of the shipped book: summary exact | 5 | content mutation (pairs J9) |
| M3 | run twice on hidden corpus 2: byte-identical documents | 3 | mutation (G6 run twice) |
| S1..S4 | /app/out documents equal the reference on the shipped book | 3 x4 | shipped |
| I1 | worker capacity on hidden outputs: one job per worker, worker up, pool matches | 3 | isolated |
| I2 | state invariants on hidden outputs: attempt <= limit+1, remaining in 1..work, states legal | 3 | isolated |
| R1..R5 | each rejection code with a lower defect planted | 3 x5 | isolated (R1 = G6 delete source) |
| P0 | all 7 outputs present | 1 | existence |
| P1 | package.zip imports leasebook, `main` and `python -m leasebook` agree | 3 | build |
| P2 | selftest.json equals a verifier run of the archive's tests | 3 | build |
| P3 | build_report.json lists the archive members and its sha256 | 3 | build |
| P4 | the shipped test files are in the archive unchanged | 3 | build |
| N1 | package source reads /tests or /logs/verifier | -5 | cheating act A |
| N2 | archive carries precomputed output documents | -3 | cheating act B |

Positive 139: whole-doc (H, M1, M2, S) 102 = 73%; hidden or mutated 114 = 82% (G3 >= 30%);
isolated 37 = 27%; shipped-only 12 = 9%. 36 checks -> WARN A3 recorded, never merged.
Messages give the first differing JSON path (G7). Whole-doc exactness stated in instruction
(G5, CL-4 FC:491). One-fact-wrong score (one dispatch moved on one hidden set): loses H-k x4
plus I-none = 20/139 tests points; reported in COST_TABLE.
Wrong implementations per lever (COST_TABLE): LV-BS-1 LAZY, LV-BS-2 PREFAIL, LV-BS-3 ANYTERM;
each alone predicted to lose >= 102/139 (73%); all-but-one overall = 0.5*27 + 0.5*90 = 58 < 70.

## 7. Judge plan (J1-J9), mode batched
- J2 x5 (w3): the agent independently recomputes, for every set, module_core checkpoint
  states / module_metrics totals / dependency outcomes / summary figures / archive members
  and sha256 outside its program and compares; solve.sh self-check prints `check <id> ok`.
- J9 (w3): altered-contents copy of the data, dependent figures move (`check J9 ok`).
- J4 (w3): one code-quality criterion with concrete conditions.
- J6 (w3): the response lists every package source file it changed, each by its path.
- J3 (w -3): honesty negative.
9 criteria. None restates an output figure (J1), none endorses a penalised reading (J5).

## 8. Expected loss per lever (compare with the probe's loss.py)
| lever | hidden input | checks a careful solver loses |
|---|---|---|
| LV-BS-1 | deadline heartbeats, coincident completion/expiry/ready, preempt-resume before old completion | H1-H4 all docs, M1, M2 (and S1-S4 under LAZY) |
| LV-BS-2 | stale tokens after retry, current token on preempted job, cancel mid-run after preemption | H1-H4 all docs, M1, M2 |
| LV-BS-3 | cascades to unsubmitted children, redelivered boosts and cancels | H1-H4 all docs, M1 |
