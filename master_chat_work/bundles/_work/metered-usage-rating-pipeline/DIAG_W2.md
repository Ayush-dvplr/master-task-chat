# Wave 2 diagnosis (probe 3, 25 Oct, after e2dc50b): tests 247/247, judge 22/34, final 82.35

| Phase | Steps | Time (min) | What the agent did | Outcome |
|---|---|---|---|---|
| Inspect data | 3-12 | 0-4 | ls, head, awk counts, python peeks, accounts.csv | read every file once |
| First write | 13-15 | 4-5 | transform.py 630 lines in one write | exact on every check at first write (LV-MU-5/6/7 included) |
| Recompute | 16-18 | 5-6 | /tmp/verify.py recomputes lines, credits, segments, units | judge R1-R4, R6, R15, R16 kept |
| Altered copy | 19 | 6 | /tmp/mod: tiny pool, 300 accounts given parents, rate change | judge R7 kept |
| Last content edit | 23 | 7 | rounding import | after this no rerun of error paths |
| Tiny input | 24-26 | 7-8 | hand-made tiny month, outputs shown | not graded |
| Error paths | 27 | 8 | rm rate_card / collector_north, control count changed, `echo exit=$?` | no observation recorded; R11 fired (-3) |
| Synthetic month | 29-30 | 8-9 | subsampled month, 7889 lines (smaller than shipped 15154) | never ran input larger than /app/data |
| Final rerun | 31-35 | 9-11 | foreign cwd, md5, py_compile | R10 kept |
| Wrap up | 36-41 | 11-12 | rm __pycache__, AGENTS.md, final reply | R9 kept; R12 fired (-3, "16,160 records / 160 duplicates" never computed) |

Lost judge criteria: R5 (summary totals from normalized lines; it recomputed from its own reconstruction), R8 (main 267 lines), R11 (-3), R12 (-3).
Never done: timed a run; ran a larger input than /app/data; showed exit status of an error path; summed normalized.jsonl fields against summary.json.
Program complexity: linear everywhere except billing_groups() (per-account parent walk, no memo: accounts x depth).
Tests: 63/64 checks passed, the one miss is the negative (not fired). No check exercised a deep parent line or run time (RUN_LIMIT_SEC 600, unstated).
