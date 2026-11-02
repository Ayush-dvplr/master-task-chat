# Lease replay contract

This file is the contract for the `leasebook` package in `project.zip` and for the documents it writes. A book is a directory holding the eight input files below; other files in it are ignored. The package replays every set of a book and reports what happened.

Every reported figure of a set is computed from the replayed timeline that produced it.

## 1. Input files

All files are UTF-8 with LF line ends. Every id (set, job, worker, event) is a whole number and ids are compared as numbers. The row order of a table carries no meaning. Blank lines in `events.jsonl` carry no meaning.

1. `policy.ini`: section `[lease]` with key `ticks` (lease length, 2 to 20) and section `[retry]` with key `delay` (retry delay, 1 to 10). Both values are whole numbers. One policy holds for the whole book.
2. `pools.json`: an object whose key `pools` is a non-empty list of objects, each with a string `pool` (the pool name, unique in the list) and a boolean `preempt`. Pools are shared by all sets.
3. `workers.csv`: header `set,worker,pool,state`. One row per worker of a set; `state` is `up` or `down` and gives the worker's state at time 0.
4. `jobs.tsv`: tab separated, header `set`, `job`, `pool`, `priority`, `retry_limit`. One row per job of a set; `priority` is the starting priority.
5. `durations.csv`: header `set,job,work`. One row per job of a set; `work` is the units of work the job needs.
6. `dependencies.csv`: header `set,parent,child`. One row per edge; the child depends on the parent. Each edge appears once.
7. `events.jsonl`: one JSON object per line with keys `set`, `id`, `t`, `type` and the fields of its type:
   - `submit` with `job`;
   - `heartbeat` with `job` and `attempt`;
   - `fail` with `job` and `attempt`;
   - `cancel` with `job`;
   - `boost` with `job` and `delta` (a whole number added to the job's priority);
   - `worker_down` with `worker`;
   - `worker_up` with `worker`.
   Event ids are scoped to their set. A line whose id was already used in the same set with identical content is a redelivered copy.
8. `checkpoints.txt`: lines `<set> <time>`. The sets of the book are the set ids listed here; the times of a set are distinct.

## 2. Bounds

A book has at most 500 sets. Per set: at most 160 jobs, at most 24 workers and at most 1200 event lines including redelivered copies; times are 0 to 5000; `work` is 1 to 60; starting priority is 0 to 9; `delta` is -3 to 3 and never 0; `retry_limit` is 0 to 3. Each job has at most one `submit` event apart from redelivered copies. A `worker_down` event names a worker that is up and a `worker_up` event names a worker that is down. Every event time of a set is at most the set's last checkpoint, and each set has at least one checkpoint. `leasebook.main` replays a book of up to 4 sets at these bounds within 60 seconds.

## 3. Jobs, workers and attempts

A job is in exactly one state: `unsubmitted`, `waiting`, `queued`, `running`, `backoff`, `completed`, `dead` or `cancelled`. The last three are terminal. Every job starts `unsubmitted` with attempt 1 and remaining equal to its work. A worker is up or down, and is idle or holds one running job. A job only runs on a worker of its own pool.

When a job starts on a worker at time `s`, it is `running`, a dispatch row `[s, job, worker, attempt]` is recorded, its run count grows by 1, and its lease deadline is `s + ticks`. A running job's remaining falls by 1 at every instant after `s`; each such unit counts as one executed unit of the job.

An attempt ends when a `fail` event applies or the lease expires. When an attempt ends at time `t`, the worker becomes idle, the job's lost units grow by its work minus its remaining, and its ended-attempt count grows by 1. If the attempt number equals `retry_limit + 1` the job becomes `dead` and keeps its attempt number and remaining. Otherwise the attempt number grows by 1, remaining returns to the job's work, the job becomes `backoff`, and it becomes ready at `t + delay`.

A preemption or an eviction takes a running job off its worker: the job becomes `queued` and keeps its remaining and its attempt number, and its lease is dropped. Neither ends the attempt.

When a job becomes `dead` or `cancelled`, every job that depends on it directly or through other jobs and is not terminal becomes `cancelled` at the same time; each such job is a cascaded job.

## 4. The replay

The replay of a set steps through every whole-number time from 0 to the set's last checkpoint; each such time is an instant. At each instant `t` the replay runs these four phases in this order, and nothing else happens at `t`:

1. Completion. Each running job's remaining falls by 1 (not at `t = 0`). Each running job whose remaining is now 0 becomes `completed` and its worker becomes idle. Then each `waiting` job whose parents are all `completed` becomes `queued`; it is released at `t`.
2. Expiry and retry. Each `running` job whose lease deadline is `t` ends its attempt, and each `backoff` job whose ready time is `t` becomes `queued`.
3. External events. The set's events with time `t` are applied one by one in ascending event id, as stated in section 5.
4. Dispatch, as stated in section 6.

Within a phase, the order in which jobs are handled never changes the result. If `t` is a checkpoint of the set, the state after phase 4 is the checkpoint's state.

## 5. External events

An event is applied as follows. The first matching row of this list decides; an event that lands in an audit row has no other effect. An audit row is `[t, event id, reason]`.

1. Its id was used by an event handled earlier in the set (a redelivered copy): audit `redelivery`.
2. `worker_up`: the worker becomes up. `worker_down`: the worker becomes down; a job running on it is evicted (section 3) and its eviction count grows by 1.
3. The event names a job that is terminal: audit `finished`.
4. `submit`: the job becomes `queued` if all its parents are `completed` (a job with at least one parent is then released at `t`), and `waiting` otherwise.
5. `boost`: the job's priority grows by `delta`.
6. `cancel`: if the job is running, its worker becomes idle; its lost units grow by its work minus its remaining; it becomes `cancelled`.
7. `heartbeat` or `fail` whose `attempt` differs from the job's attempt number: audit `stale_attempt`.
8. `heartbeat` or `fail` for a job that is not `running`: audit `not_running`.
9. `heartbeat`: the lease deadline becomes `t + ticks`.
10. `fail`: the attempt ends.

## 6. Dispatch

Dispatch takes the jobs that are `queued` when it begins, ordered by priority from high to low and then by job id from low to high, and handles each in turn:

1. If an up, idle worker of the job's pool exists, the job starts on the one with the lowest worker id.
2. Otherwise, if the pool has `preempt` true and a running job of the pool has a lower priority than this job, the victim is the running job of the pool with the lowest priority, then the latest start time, then the highest job id. The victim is preempted (section 3) and its preemption count grows by 1; this job starts on the victim's worker.
3. Otherwise the job stays `queued`.

## 7. Output documents

`leasebook.main([book_dir, out_dir])` replays the book and writes four JSON documents into `out_dir` (created if absent), then returns 0. `python -m leasebook <book_dir> <out_dir>` does the same and exits with that status. Documents are compared as parsed JSON values. Set, job and worker ids used as object keys are decimal strings; ids inside values are numbers. Times are whole numbers.

`module_core.json`: `{"sets": {set: {"checkpoints": [...], "dispatches": [...], "audit": [...]}}}`.
- `checkpoints`: one entry per checkpoint in ascending time: `{"t": time, "jobs": {job: {"state", "priority", "attempt", "remaining", "worker"}}, "workers": {worker: {"up", "job"}}}`. Every job and worker of the set appears. `remaining` is the job's remaining after phase 4; `worker` is the worker of a running job and `null` otherwise; a worker's `job` is its running job or `null`.
- `dispatches`: the dispatch rows in the order they were recorded.
- `audit`: the audit rows in the order they were recorded.

`module_metrics.json`: `{"sets": {set: {"jobs": {job: counts}, "totals": totals}}}`. `counts` has the integer keys `runs`, `executed`, `lost`, `preemptions`, `evictions` and `attempts_ended`, counted from time 0 to the last checkpoint. `totals` has the sum over the set's jobs of each of these keys, plus `audit`: `{"redelivery", "finished", "stale_attempt", "not_running"}`, the number of audit rows with each reason.

`dependency_resolution.json`: `{"sets": {set: {"edges": [...], "released": {job: t}, "cascaded": {job: t}}}}`.
- `edges`: one object `{"parent", "child", "outcome", "t"}` per edge, ordered by parent id then child id. At the last checkpoint, `outcome` is `satisfied` when the parent is `completed`, `broken` when the parent is `dead` or `cancelled`, and `open` otherwise; `t` is the time the parent became terminal, or `null` for `open`.
- `released`: each job released during the replay, with its release time.
- `cascaded`: each cascaded job, with the time it was cancelled.

`summary.json`: `{"set_count": n, "sets": {set: {"final", "executed", "lost", "dispatch_sha256"}}}`. `final` is `{"completed", "dead", "cancelled", "other"}`, the number of jobs in each terminal state at the last checkpoint and of all other jobs. `executed` and `lost` are the set totals of `module_metrics.json`. `dispatch_sha256` is the lowercase hex SHA-256 of the dispatch rows written as lines `t job worker attempt` (single spaces, decimal, each line ending with LF) in recorded order.

## 8. Refusing a book

The package refuses a book that breaks one of these rules. It checks them in this order and reports the first one broken:

1. `MISSING_INPUT`: one of the eight input files is absent. The first absent file in the order of section 1 is named.
2. `INVALID_POLICY`: `policy.ini` or `pools.json` does not have the shape and bounds of sections 1 and 2.
3. `UNKNOWN_ENTITY`: a row or event names a set absent from `checkpoints.txt`, a pool absent from `pools.json`, or a job or worker that the set does not define.
4. `EVENT_ID_CONFLICT`: two events of a set share an id and differ in any field.
5. `DEPENDENCY_CYCLE`: the edges of a set form a cycle.

A refused book makes the package print exactly one line to standard output, `ERROR MISSING_INPUT <file name>` or `ERROR <CODE>` for the other codes, write no document, and return (or exit with) status 2.

## 9. Package and build

`package.zip` holds the package source with `pyproject.toml` at the archive root, the package under `src/leasebook/`, and its tests under `tests/`. Every test file shipped in `project.zip` is kept unchanged; tests may be added. `leasebook.__version__` equals the `version` of `[project]` in `pyproject.toml`. The tests run with `python -m unittest discover -s tests` from the extracted archive root.

`selftest.json`: `{"package": "leasebook", "version", "tests_run", "tests_passed"}` from that unittest run of the archive; `tests_passed` is `tests_run` minus failures, errors and skips.

`build_report.json`: `{"package": "leasebook", "version", "files", "archive_sha256"}`; `files` is the sorted list of member names of `package.zip` and `archive_sha256` is the lowercase hex SHA-256 of `package.zip`.
