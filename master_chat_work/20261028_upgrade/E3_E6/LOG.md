# LOG 478e1df E3-E6 (IST)

## Setup
- 02:02 name_session.py 478e1df; auto.py sha16 993d072a96a351af, test_auto.py ced6f91e4b183d41 (match the brief).
- 02:03 backups OUT/bak/* and H/.master-queue/backup-20261029T0203-e3/master_queue.py. Baseline: auto 61 OK, tools 23 OK.

## E3
- wind_down -> still_running() gate (R5-09), write_still_running (R5-25), shutdown_children keeps a busy worker server (R5-20), stop --now (R5-11). 4 tests.

## E4
- tools/decide.py (+2 tests). No existing code reads decisions.jsonl, so there was no reader to change.

## E5
- AP: 5 workers, Docker advice, Last spawn, ## Budget, wind-down rows, decide.py in rule 4. PLAN_TEMPLATE: 5 fields.
- auto.py: plan_fields, paid-run cap 6/day, harness --wind-down, spawn cutoff + --wind-down. 5 tests.

## E6
- MQ gate runs not counted as slots (R5-12), cancel clears pause on empty queue (R5-14), board_set via board.py (R5-15), registry_check.py (R5-16; live exit 1, 2 fields), parse_plan start minute (R5-17; one old assertion changed), package main exit 3 (R5-21), permission regression test (R5-26).

## Verify
- 02:15 auto 73 OK, tools 30 OK; negatives on bak: auto 11 fail/error, tools 6 fail; R5-26 mutation fails.
- 02:18 docstring compacted so auto.py:65 = MAX_BUSY_WORKERS again; auto 73 OK rerun; report line refs updated.
- /tmp/E3-neg, /tmp/E3-negt, /tmp/E3-mut removed.
