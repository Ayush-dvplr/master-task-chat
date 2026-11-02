# DESIGN: sensor-network-lsq-correlated-adjustment

## v0 (reconstructed from the converted bundle and conversion notes)
Mathematics task: exact two-stage robust least-squares adjustment of a 6-station network from four shards with per-shard conventions, correlated sessions, workbook control values, data-snooping, datum shift and global model test; 31 reports from `/app/out/derive_report.py`. Generator, reference solver and grader all live in `tests/test_output.py` (`python3 tests/test_output.py DIR` re-emits the shipped extract). v0 tests: 24 checks, 22 positive (64), 54 of 64 on shipped data; judge 21 criteria, mode individual.

## Harden round 1
Baseline: claude-opus-5 run scored tests 1.0 (24/24), judge 22/52, reward 0.7115; every v0 lever leaked because each file carried its trap with the exact inverse and the acceptance table confirmed the shipped answer (`verdict=PASS`).

Changes:
- Format: K8 litellm pin in tests/Dockerfile (apt line aligned with the batch so the warm image caches), `_grant_read` copy of the program (0644 in a 0755 temp dir) run as nobody under an fcntl lock with killpg and leftover kill by uid while the lock is held, judge `mode = "batched"`.
- Leak removal: trap blocks and inverse text deleted from every generated file, schema.md rewritten without trap labels or printed answers, irregular acceptance centres (shipped verdict REJECT_LOW, no single wrong reading lands in the band), base-unit sigma restatements removed.
- New levers H1-H4 (see LEVERS.md): tripod centring split between schema.md and station_registry.csv, angle misclosure reduction on rare boundary rows, revision-ranked duplicate records with superseded_records report, dependent chain graded on three regenerated extracts (challenge, eval, new audit seed).
- Tests: 21 positive checks, positive weight 62; 54 on whole documents from hidden extracts, isolated 7 (11.3%), shipped-only 1 (1.6%). Negatives stand down unless the program ran cleanly.
- Judge: 8 criteria (positive 15): four shipped figures asked for in the instruction, one code-quality criterion, three negatives.
- Instruction: short, names schema.md as the authority, no rule or trap list, no list of what varies, asks for the four figures.

Expected: careful solver missing one lever about 0.08-0.13 tests; full chain 1.0.

## Redesign (r2, board 4d6dfe8, 25 Oct)
Parked after P14 (NO NATURAL TRAP). Three new rules, each a measured Opus habit shape not tried on this task: A H7 second-pass traverse closure (schema 8b, new `traverse_closure_register.csv`), B H6 recursive set-out chain (schema 1, new `control_mark_register.csv` and `set_out_from` column), C H3 defined term district = kept shard (schema 2). Each separating case in one hidden extract (eval, challenge, audit); shipped extract separates none. Tests 30 (28 positive, P = 86: old 62 plus visible w3 and hidden `_hard` w5 per lever); judge 11 criteria (R1-R4 figures recomputed, R9-R11 recompute conduct w3, positive 24). Local real-test scores: oracle 1.0, one lever wrong 0.733, two 0.465, three 0.198, a2 program 0.093.
