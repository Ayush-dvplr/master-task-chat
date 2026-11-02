# DOC_CHECK - our QC docs against kit 71a653b2 (board 5087cd2)

Kit paths are relative to `Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`; `FC` = Final_checklist.md, `01`..`05` = gate files.
Verdicts: OK = matches the kit; WRONG = contradicts the kit text; STALE = was right for an older kit; HOUSE = stricter house rule presented as kit; UNVERIFIED = depends on a QC report or Harbor behaviour I did not open.

## 1. QC_FIX_PLAYBOOK.md (`master_chat_tasks/knowledge/QC_FIX_PLAYBOOK.md`)

| Line | Row | Verdict | Evidence |
|---|---|---|---|
| L8 | dodges are findings ("Vagueness counts against the author" 01:45; "report the label as the defect" 04:92) | OK | both phrases present at 01:45 and 04:92 |
| L13 | "every graded rule stated in a file the agent can read (IN-15)" | WRONG | 01:45 scopes it: "Every graded rule of engagement is stated somewhere the agent can read it. If a test or a judged criterion grades HOW the agent worked". Outcome rules only need to be reachable: 01:39 IN-9 "Whatever the instruction holds back must still be discoverable from the shipped data"; FC:498 CL-10 "Derivation counts fully and is meant to". Same overstatement in `_COMMON_RULES_v2.md` Never 6 (L24) |
| L14 | IN-16 three parts | OK | 01:46 "First, something graded depends on the answer. Second ... two readings ... Third, nothing in any file the agent can read picks between them" |
| L15 | every promise graded by an input that triggers it (AL-2, AL-27) | OK | 05:22 "Everything promised is graded"; 05:27 "a rule only counts as graded when the test's input actually constructs the situation" |
| L16 | JD-7 oracle satisfies every criterion | OK | 04:76 |
| L17 | "one act <= -5 (AL-28, negatives only)" | WRONG (cross-layer) | 05:28 "Across layers it is one act subtracting in the tests and again in a negative-weight criterion" - any double subtraction, no -5 allowance |
| L17 | "does not demand fewer cascading whole-document tests (G1)" | WRONG (incomplete) | FC:491 CL-4 fails "a pile of separately weighted tests that all key off that same single comparison" unless "An instruction that states out loud that only an exact match counts". A cascade is safe only with that sentence (LEVER_RULES G5) and per-document observables |
| L18 | DS-4 no answers in data | OK | 02:20; note it also bans "a worked example carrying the graded values" |
| L19 | "<= 35 checks is a WARN, 70 is the cap (TS-23, 03:62)" | WRONG (citation) / HOUSE | 03:62 "at least 10 checks (fail), at most 35 (warn)"; the kit has no 70. Grep of kit md for "70" finds only the client anecdote at FC:491/493. 70 comes from LEVER_RULES L43 and _COMMON_RULES L42 |
| L27 | IN-15 fix | OK | 01:45 delegation clause "a task that says \"the operating rules are in /app/data/RULES.md\" is complete" |
| L28 | IN-16 fix | OK | 01:46 |
| L29 | AL-2 / CL-1 | OK | 05:22, FC:488 |
| L30 | AL-27 fixture inside every stated bound | OK | 05:27 + 03:50 TS-19 |
| L31 | AL-28 "lower one weight so the group sum <= 5" | WRONG for cross-layer, OK within one layer | 05:28 test groups use "a combined penalty above 5"; cross-layer has no sum test. Fix for cross-layer = remove one side |
| L32 | TS-26/JD-14 merge at the larger weight | OK | 03:53 "keep one side, or rewrite one to read a different observable"; 04:91 same |
| L33 | TS-13 | OK | 03:44; 03:135 minor "TS-13 doubled asserts with same observable" |
| L34 | TS-23 "Over 70 is always fixed" | HOUSE | kit has no upper fail; FC:448 warn needs tasker approval |
| L35 | TS-20 core 5 | OK | 03:51 weight semantics; 03:135 inversions fail |
| L36 | TS-16 | OK | 03:47 |
| L37 | TS-19 | OK | 03:50 |
| L38 | TS-25 | OK | 03:52 |
| L39 | JD-7 | OK | 04:76 |
| L40 | DS-22 | OK | 02:78 "a 'trap' nothing in the data can spring ... is a claim the bundle does not honour" |
| L41 | DS-20 | OK | 02:68 |
| L42 | JD-15/16 preference -> odds-raising at w1/w3 | OK | 04:92 "an odds-raising approach weighted 1 or 3 passes, and at 5 it is a minor" |
| L43 | JD-18 conduct, w1-3, no idiom/formatter | OK (w1-3 is house caution) | 04:99 "a criterion demanding one specific formatter, line length or idiom is a bare preference and fails JD-15"; kit sets no weight for JD-18 ("it passes the conduct test on its own terms") |
| L44 | DS-4 | OK | 02:20 |
| L45 | DS-6 KEEP as minor | OK | 02:117 minor "small data inconsistencies with no grading impact" |
| L46 | SUGGEST: KEEP (delegation / loose wording) | OK | 01:45, 01:46 "Wording you merely find loose, terse or unpolished is not this check"; FC:448 warns still need tasker approval |
| L50-77 | process sections | n/a | not kit claims |

Rows wrong: L13, L17 (x2), L19, L31 (cross-layer half). House-only: L19 / L34 "70".

## 2. QC_RULINGS.md (`master_chat_tasks/knowledge/QC_RULINGS.md`)

| Line | Row | Verdict | Evidence |
|---|---|---|---|
| L9-17 | IN-15 rulings | OK | consistent with 01:45; L12/L13 FAIL rows are judge negatives whose rule was unstated, which 01:45 covers |
| L19-27 | IN-16 rulings | OK | L26 "ungraded gaps are not IN-16 failures" = 01:46 "If both readings would satisfy every test and every criterion, there is no defect here" |
| L29-38 | TS-13 MINOR/PASS | OK | 03:135 minor |
| L43 | hidden input outside bounds FAIL | OK | 03:50 TS-19 |
| L44 | vendor `nobody` runner over 0600 inputs, logged under TS-19 | STALE | now owned by TS-30 / H6 (03:59, tests_qc.py:950-1011), added in commit c9e3454a; old copy has no TS-30 |
| L48, L49 | AL-2, CL-5 | OK | 05:22, FC:492 |
| L50 | dispatch 400 s cap unstated -> WARN | UNVERIFIED | a graded cap the agent cannot read would be 05:21 AL-1 "a test asserting a property that appears in no file the agent can read" = fail; depends on whether the cap was graded |
| L57 | district-heat TS-20 inversion WARN | WRONG (kit stricter) | 03:135 "TS-20 core-vs-minor weight inversions and ordering contradictions" = fail; old copy 03:132 says the same, so the WARN was an under-call, not a kit change |
| L58-61 | TS-20 rest | OK | 03:135 minor "mild TS-20 imbalance within the correct ordering" |
| L63-72 | TS-26 | OK; L70 "G1 cascade accepted" OK for TS-26 but see CL-4 | 03:53 vs FC:491 |
| L74 | header "one act costs at most -5 across tests and judge" | WRONG | 05:28 cross-layer = any double subtraction |
| L77-79 | AL-28 FAILs | OK verdict, L79 reason wrong | L79 fails under 05:28 even at -1 + -1; "(-6)" is not the reason |
| L85-94 | JD-7 | OK | 04:76 |
| L96-110 | JD-15 | OK | 04:92 preference 1/3 minor, wrong kind = label defect, odds-raising w3 passes (L110) |
| L100 | "(also JD-2)" for absence positives | OK | absence example sits in the polarity table 04:60 "rewards an absence, nop earns it" |
| L115-119 | AL-27, AL-2/CL-1, JD-14, JD-18 | OK | 05:27, 05:22, 04:91, 04:99 |
| L120 | DS-4 `cap-`/`rej-` id prefixes WARN | WRONG (kit stricter) | 02:117 "fail: ... DS-4"; 02:20 "make trivially derivable the expected final output" |
| L121 | TS-23 38 checks WARN | OK | 03:62 |
| L124 | "QC accepts a natural cascade ... G1 is QC-safe as built" | WRONG (incomplete) | true for TS-26/AL-28; CL-4 FC:491 can still fail a cascade without a stated exact-match bar |
| L127 | negative trigger list matches a stated sentence word for word | HOUSE | kit asks for a quotable sentence (04:94 JD-16 cond 1, 01:45); "word for word" is stricter |
| all rows | precedent cites (v1:35 etc.) | UNVERIFIED | QC reports not opened (twin session's scope) |

## 3. Old copy (18-19 Oct, `QC assigned/Input_Bundle_QC/`) vs live 71a653b2

Unchanged: Starter.md, instruction_qc.py (diff empty).
- 01 IN-15 (01:45): reworded - lists criteria with `type = "instruction following"` (was `kind = "constraint"`); doubling justified as two sides; added "Reach your verdict here from the files, not from what the other gate concluded."
- 01 IN-S7 (01:58): widened from /app/data/ to "an input COPY destination (/app/data/, /app/repo/, ...)".
- 02 DS-1 (02:17): reworded - one or more named input directories, each non-empty and COPYed (was environment/data/ only).
- 02 DS-2 (02:18): stricter - "and so must deleting any single one of them".
- 02 DS-4, DS-9, DS-16 (02:20, 28, 64): reworded data/ -> any input directory.
- 03 two-container note (03:23), TS-1 (03:25), TS-S7 (03:85): /app/data -> any input COPY destination.
- 03 TS-2 (03:26): added litellm `==` pin (ref 1.105.0, 1.107.0 quarantined).
- 03 TS-S11 (03:89): added K8 litellm pin.
- 03 TS-30 (03:59): ADDED (agent file modes survive the privilege drop).
- 03 TS-S16 (03:94): ADDED (H6). Checklist 03:101 still says "TS-S1..TS-S15".
- 03 TS-28 (03:73): reworded (755 log dir).
- 03 checklist TS-2 (03:103) adds litellm pin; TS-30 line (03:131) added.
- 04 schema (04:27-50): annotations reduced to mode, type (now the category), evaluation_target, importance; REMOVED keys category, kind, serves, residue, evidence, contract_sentence, contract_file (now fail, 04:46); REMOVED effect enum VALUE/EFFECT/ABSENCE/INVARIANT/ORDERING/DIVERGENCE; REMOVED "kind and category agree" rule.
- 04 JD-15 (04:92): reworded - classification is the reader's, annotations no longer declare kind; mislabel = `type = "instruction following"` on a non-constraint or a constraint with another category.
- 04 JD-16 cond 2 (04:95): reworded to annotations `type`.
- 04 JD-S8, JD-S9 (04:112-113): reworded to the four-key table and category set; residue checks REMOVED.
- 04 checklist JD-16 (04:140): "annotations type" (was category).
- 05 AL-11 (05:41): reworded to input paths.
- FC tree (FC:15), FC:29, fact 1 (FC:35): any input directory names.
- FC fact 3 (FC:37) and template (FC:247, FC:256): litellm==1.105.0 pin ADDED.
- FC:105 and FC-S18 (FC:301): authors rule LOOSENED - any spelling/script/case passes, single word warn, domain ethara.ai or subdomain, email need only "relate" (was capitalised words, must be built from name).
- FC:111/116: judge mode "individual" -> "batched" with rationale.
- FC judge template (FC:133-148): annotations to four keys.
- FC test.sh template (FC:232): chmod 700 -> 755.
- FC Step 10 (FC:275, 342, 352, 364, 369): owner-only run ADDED.
- FC-S3 (FC:286): reworded to input directories.
- FC sign-off (FC:516): owner-only line ADDED; "three run lines" -> "four".
- judge_qc.py: J6/J7 rewritten (four keys, RETIRED_ANNOTATIONS fail); effect/kind/residue checks REMOVED.
- structure_qc.py: S3 trajectories/ warn ADDED; S4 any input dir + must be COPYed; S5 run records under trajectories/ warn; T14 name/email rules loosened (is_name_shaped, email_in_domain, single word warn).
- tests_qc.py: D1 any input mount; K8 ADDED; H5 755 (700 warns); H6 ADDED.
- exe_copy.py: `--owner-only` ADDED.

## 4. Kit template defects

1. R6 (task brief): UNVERIFIED as stated. Neither old nor live 04_Judge_QC.md contains "R6". The kit's grader-read criterion is the R2 template, 04:21 = FC:140 "The agent opens a file under /tests or /logs/verifier during its run." It names /tests and /logs/verifier, not /solution, and covers only "opens", not listing or copying (our emberforge R8 widens it to "opens, lists or copies"). Bigger problem: FC:498 says "`solution/` and `tests/` are not uploaded to it", and 03:23 says grading runs in a separate container. So whether this act can happen at all during the agent run is UNVERIFIED, and if it cannot, 04:88 JD-11 calls it residue: "Generic negatives copied from another task that cannot occur here are residue - flag them". The generator's eight `templates/*/tests/judge.toml` R6 rows are positive conduct/constraint criteria. None of them mentions /tests, /solution or /logs/verifier.
2. 03:101 checklist "TS-S1..TS-S15" omits TS-S16 (03:94).
3. 03:103 checklist "litellm==1.105.0" vs 03:26 "another exact version is a warn" vs FC:37 "Both pins are required" (K8 warns, tests_qc.py:661).
4. Starter.md:82 "minor = fix or get tasker approval" vs FC:447 minor "Fix quickly."; Starter.md:84 findings format lacks the `Fix:` line FC:459 requires.
5. FC-S24 (FC:293) "right after FROM" is not enforced (S10 passes ENV HOME at the end, probe env_home_moved_end).
6. JD-S13 sits in 04 (04:118) but is enforced by tests_qc.py R3, not judge_qc.py.
7. 01:35 IN-5 accepts RUN-created paths; instruction_qc.py:257 C4 fails them under /app/data/ (probe instr_run_created_path).

## 5. qc_authoring_checklist_9b8229f6.md (input listed in the prompt; not a Phase 5 table, stale items only)

- L1 "Input_Bundle_QC at GitHub 9b8229f6": STALE, live is 71a653b2.
- L75 "`chmod 700 /logs/verifier`": STALE. FC:232 template is `chmod 755 /logs/verifier`; 03:73 "Use 755 rather than 700 there ... A bundle that still uses 700 earns an H5 warn, not a fail."
- L74 tests/Dockerfile list has no `litellm==1.105.0`: STALE. FC:37 "Both pins are required (tests_qc.py K5, K8)"; a missing pin is a K8 fail.
- L95 "`contract_sentence`/`contract_file` on constraint criteria, `serves` on conduct criteria": WRONG now. 04:46 "`serves`, `residue`, `evidence`, `contract_sentence` and `contract_file` are retired and fail". Following it fails J6.
- L98 cites "04:79, 04:125, 04:156": STALE line numbers (04 has 148 lines; "some" is 04:69 JD-3 and 04:146 minor).
- L114 Step 10 lists oracle x5, nop, stub: STALE, missing the owner-only run (FC:275 "one owner-only oracle run"; FC:342, 03:59 TS-30 "must still read exactly 1.000").
- L101 "At least one code-quality criterion": stricter than kit; 04:99 JD-18 requires it only when the agent authors code. HOUSE, not wrong.
- L9 tree list: a shipped `trajectories/` is now an S3 warn, not a fail (structure_qc.py:293-296). Minor STALE.
- L46 "State every graded rule of engagement": OK, matches 01:45 scope (better than PLAYBOOK L13 and COMMON_RULES Never 6).
