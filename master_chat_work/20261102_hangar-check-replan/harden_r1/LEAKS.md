# LEAKS (hangar-check-replan, harden r1, final after build)

Status: FINAL (Phase 2). Every row that was open in the Phase 1 draft is closed in the built tests/test_output.py; evidence column quotes the built line numbers and the Docker attack run (`_runs/20261102/hangar-check-replan/harden1-20261102T1341/attacks.out`, `attacks.jsonl`).

## Infra rows (master note 5)
| row | where checked | result | fix in build |
|---|---|---|---|
| hidden seeds / generator code in agent image | environment/Dockerfile copies `data` only; grep -rniE "seed\|hidden\|h[1-6]_\|solve\|TRUTH" environment/ instruction.md = 0 hits | closed | environment/ unchanged by the build; after build grep -rniE "sdt\|customXml\|AlternateContent\|h1[0-5]\|FORMS\|seed" environment/ instruction.md = 0 hits |
| expected values in shipped files | expected docs are built in memory by derive() inside tests/test_output.py; environment/data holds inputs only (W11) | closed | new variant folders keep expected in memory only |
| solution/ or TRUTH.md in agent image | Dockerfile has no COPY of solution or tests | closed | none |
| /tests reachable in agent phase | task.toml environment_mode "separate": verifier runs in its own tests image; test.sh `chmod -R go-rwx /tests` | closed | none |
| world-readable verifier temp dirs | tests/test_output.py L951-952, L1012-1013, L1244-1245: case roots chmod 0755, data sealed 0755/0644, kept for the whole session; work/out/cwd 0777 (L913-917) | closed | `_build_case` (test_output.py:1142-1176) keeps each case root 0700 while it is built, opens it 0755 only inside `_RUN_LOCK` for its own run and sets 0700 in `finally`; work dir removed in `finally` |
| untrusted run survives its call | `_run_program` L921-941 and `_check_stops_on_missing_input` L1250 use subprocess.run, no own session, no group kill, no sweep of uid nobody | closed | `_launch` :1035-1049 (Popen start_new_session=True, wait(timeout=RUN_LIMIT)) and `_stop_untrusted` :1001-1032 (killpg SIGKILL, then /proc sweep of uid nobody, 20 passes) in except and finally; `_check_stops_on_missing_input` :1388 uses `_launch`. Fork probe: built survivors=0, pre-build control survivors=1 |
| read-back before the kill | L938-940 reads /out right after subprocess.run returns; a forked child of the run may still be writing | closed | `_run_program` :1052-1073 reads the nine files after `_launch` returned, i.e. after the kill and sweep |
| overwrite into another run's out | out dirs 0777 under 0777 work dir; a survivor of run k can write into run k+1's out | closed | survivors are killed before `_launch` returns and only one untrusted run exists at a time (`_RUN_LOCK`), so no survivor sees a later run's out. Attack `overwrite` (double-fork setsid daemon, 300 s) scored 65/230 = a1's own score, lever 0/165 |
| run lock | `_check_program_runs_shipped` L1225-1231 calls `_run_program` outside `_CASE_LOCK` | closed | `_RUN_LOCK = threading.RLock()` (:921) held by `_launch` for every untrusted run |
| `__pycache__`, `.git`, `.DS_Store` in bundle | find BUNDLE = 0 hits | closed | python3 -B / PYTHONDONTWRITEBYTECODE=1 in every build step; re-find before gates |
| answers from file names or sizes | hidden folders use the same file names and generator sizes as shipped; new variant folders differ from plain ones only in Word markup | closed | none |
| hardcoded shipped answers | negative_hardcoded_sample_answers (-5, L1276) + shipped answers do not carry over to hidden folders | closed | attack `hardcoded` (shipped answers as literals): 11/230 with negative_hardcoded_sample_answers fired (-5), net 6/230 = 2.6 % |

## Attack programs (Docker, built tests, `WORK/h1_a1/attacks/`)
| attack | what it does | tests (positive 230) | lever kept | negatives |
|---|---|---|---|---|
| lift | a1 plus tries to import /tests test_output and call derive, scans /tmp/*/want.json, /logs/verifier, /tests | 65 (lift_found 0) | 0/165 | negative_reads_check_files -5, net 60 = 26.1 % |
| overwrite | a1 plus a setsid double-forked daemon copying its outputs over other runs' out dirs and copying readable /tmp/hangar-*/data | 65 = 28.3 % (a1 alone) | 0/165 | 0 |
| stub | nine empty documents | 1 = 0.4 % | 0/165 | 0 |
| forgery | nine documents with every figure zeroed and lists empty | 1 = 0.4 % | 0/165 | 0 |
| hardcoded | shipped answers written as literals | 11, net 6 = 2.6 % | 0/165 | negative_hardcoded_sample_answers -5 |

The overwrite daemon could copy only folders it may read during its own run (its own case data and the public shipped data); every other case root is 0700 at that time. No copied folder changed a score.

## LEAK_LIBRARY rows
| row | where checked | result |
|---|---|---|
| Common: one explicit sentence per rule (W2/W3) | new levers add no rule sentence; data_conventions.md:20-23 already says "WordprocessingML packages as ECMA-376 defines them" | no new leak (docs unchanged) |
| Common: trap spelled out (W1) | grep docs for sdt / content control / customXml / AlternateContent / markup = 0 hits | closed |
| Common: two-file read only (L4) | the Word rule sits in data_conventions.md; ECMA-376 row containers live in the standard, not in the bundle | n/a |
| Common: decoy refuted beside use | no decoy added | n/a |
| Common: shipped boundary rows (W5/W6) | shipped docx stay plain (one w:tr per row, one run per cell); variant markup is hidden-only | closed |
| Common: hidden cases only repeat coded rules | the variant folders fire a branch a1's own self-test (plain synth docx, step 27) never built | closed for a1 |
| Common: judge "states figure X" (J1) | no figure criterion; R17 is the -5 figure negative only | closed |
| Common: grader permission artefact | `_grant_read` widens /app modes before the uid drop (unchanged) | closed |
| CR-1 every reason per row | rejection order list data_conventions.md:34-43 (old, not a new lever) | unchanged |
| CR-2 plan in force decoy | no decoy | n/a |
| CR-3 single-reading rule | new levers need no new rule | n/a |
| CR-4 strict malformed | duration/date regex rules unchanged; not a lever here | n/a |
| CR-5 two duplicate notions | X1 kept (KEPT.md) | unchanged |
| V0-1 numbered cleaning order | rejection list is numbered (data_conventions.md:34-43); not graded as a lever in r1 | unchanged (old) |
| V0-2..V0-8 explicit one-line rules | settlement and plan rules are explicit; a1 implemented them all; r1 does not lean on them | n/a |
| RUN state beside use / shipped separates | no shipped variant markup | closed |
| REV decoy refuted on same line | none | n/a |
| REMAP numbered procedure | none added | n/a |
| STATE exception sentence | none added | n/a |
| ESC/EXT and SALV trap explained | no explanation of Word markup added | closed |
| ENC self-testable rule | variant reading is not self-testable from shipped data (shipped docx plain) | closed |
| REJ precedence numbered list | old list, not a lever in r1 | unchanged |
| judge R1-R4 figures | judge has no figure criteria | closed |
