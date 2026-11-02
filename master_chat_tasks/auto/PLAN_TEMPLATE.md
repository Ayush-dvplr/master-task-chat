# PLAN for this auto run (written by the master from Ayush's words; wins over AUTO_POLICY.md)

Until: HH:MM IST
Paid runs: 6 (a whole number, or the exact words "no cap"; any other text makes auto.py refuse `harness`)
Workers/harness/Docker: 5 / 2 / 2 Docker-heavy (start --workers/--harness set the first two; Docker is advice)
Budget: paid run only with no LIMIT and <= 2 busy workers; <= 3 busy while it runs; fresh window -> paid run first
Wind-down: none (tasks, shas or slugs allowed after AUTO STOP via `harness --wind-down` / in the last-spawn window via `spawn --wind-down`)
Last spawn: 20 min before Until (or HH:MM)
Ayush's words (verbatim):
> ...

## Do, in this order
1. ...

## Do not
- ...

## Timed steps (the watcher delivers each at its time)
- at HH:MM: ...
