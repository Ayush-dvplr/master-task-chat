# 09 ninefold-crown-settlement-recompute (claude-opus-5, run_1): overall 29.18 %, tests 15.29 %, rubric 43.06 %

T = `tasks_copy_20261022T0105/09_ninefold-crown-settlement-recompute/`. Notes: `notes/09.md`. "UNVERIFIED" marks guesses from static reading (no runs).

## 1. Shape
- Bundle: `instruction.md` (21 lines, 806 words), `task.toml`, `environment/Dockerfile` + `environment/data/` (58 files), `solution/` (solve.sh, solve.py 60 KB, TRUTH.md 28 KB), `tests/` (test_output.py 6849 lines / 299 KB, judge.toml 14.7 KB, reward.toml, test.sh, Dockerfile).
- Data: 22 `.md` (14 stage specs p01-p14, overview, lineage, glossary, traps register, schema reference, serialisation contract, program contract, worked examples ...), 10 csv, 5 toml, 4 json, 3 tsv, 2 yaml, 2 txt, 2 psv, 1 each xml, ndjson, jsonl, conf, db and three office papers (xlsx with 6 sheets, one live; pdf memo; docx directive). Largest: match_result_sheets.ndjson 125 KB, game_records.csv 78 KB (2304 lines). Three decoys that "govern nothing" (legacy_season_extract.csv, spectator_gate_returns.json, night_desk_audit.db; paper_lineage.md).
- Outputs (task.toml:2): 31 documents + `/app/out/crownsettle.py` (32 artifacts).
- Tests: 34 criteria = 27 positive (weight 85: shipped 18, contested 22, wide 22, thin 22, refuse-missing-paper 1) + 7 negative (-5, then six at -3; total -23) (registrations test_output.py:6816-6849). Judge: 35 criteria, positive 72, negative -13 (R3, R10, R32, R33, R35). reward.toml: 0.5/85 and 0.5/72, each channel half.
- Timeouts: agent 14400 s, verifier 5400 s, per program run 600 s (test_output.py:54). Run: 52 steps, 38 min, 2.27 M prompt tokens; verifier took 74 s.

## 2. Is the low score genuine? (static screen)
| check | class | deciding line (T/tests/test_output.py) |
| --- | --- | --- |
| all_artifacts_exist, core_documents_parse | READ | :6110-6113, :6116-6149 read `/app/out` files only |
| shipped_core/pairing/standings/prize/publication_exact | READ | `_shipped_family` :6152-6154 -> `_same_bytes(ref_dir, _delivered(), family)` :6020-6029 |
| shipped_manifest_consistent | READ | :6157-6159 |
| contested_*, wide_*, thin_* (6 each = 18) | EXEC | `_program_family`/`_program_manifest` :6162-6175 -> `_case_output` :5997-6017 -> `_launch` :5946-5981, `subprocess.Popen(_untrusted(command), ...)` :5964, `command = [sys.executable, str(_program()), ...]` :5961 |
| program_refuses_missing_paper | EXEC | :6178-6199 (`_launch` :6196) |
| 6 negatives that run the program, and negative_hardcoded_sample_answers | EXEC | via `_case_output`/`_launch`; hardcoded via `_is_replayer` :6370-6393 |

- If at least one EXEC check passed: none did. All 8 READ positives passed (shipped event byte exact in all 31 documents) and all 19 EXEC positives failed.
- How the tests run the program: `_untrusted` (:5828-5835) prefixes `setpriv --reuid=nobody --regid=nogroup --clear-groups` (:5810) when root. The test chmods the work root and cwd to 0777 (:5847, :5865) and relaxes minted data to 666/777 (`_relax` :5870-5879). The program itself, `_program()` = `/app/out/crownsettle.py` (:5921-5925), is never chmodded; `tests/test.sh:5-8` touches only `/logs/verifier` and `/tests`; `tests/Dockerfile` only does `mkdir -p /app`.
- Agent side: `crownsettle.py` was written with the editor `create` (step 31) and `str_replace` (steps 32-34, 40). The failed first attempt at step 29 reports `Errno 2 ... '/app/out/.crownsettle.py.xemhsv2b.tmp'`, i.e. the editor writes through a temp file in the same directory and renames it; temp files made that way are normally mode 0600 (UNVERIFIED mechanism). The same editor in task 08 left `-rw------- agent agent` (08 traj steps 24, 35, 41). This trajectory never lists `crownsettle.py` with `ls -l` (steps 48, 51 use `ls -1`), so the delivered mode is UNVERIFIED.
- The strongest sign is the fired negative: `negative_hardcoded_sample_answers` (-5) fired. `_is_replayer` (:6383-6393) returns True when the shipped delivery is byte exact and the program gave no output, or different output, on the same event re-minted under another identity (EV-3C1D, NC-4417-K6, prefix PM-; :60). `_mechanically_broken` (:6341-6348) does not stand down when the program simply did not run, because `_nondeterministic` returns False if runs failed (:6258-6259). The delivered program holds no event literal (grep of crownsettle.py for `EV-`, `NC-6093`, `PL-`, `dv_` finds nothing), and the agent's own run of the shipped event under another directory name was byte identical (step 43: "same event under another directory name identical: True"). An honest, identity-free program branded a replayer is what an unrunnable program looks like here.
- Other breakers: no timing in the trajectory (UNVERIFIED) but limit is 600 s and the verifier finished in 74 s; `tomllib` needs Python 3.12 and the verifier image is `python:3.12-slim` (tests/Dockerfile:1); no hardcoded path in the program except the argument parser (crownsettle.py:1652-1671); stdlib only (crownsettle.py:10-22).
- Counter-evidence for a genuine low score: the program looks general (handles any change code other than drop/absence as `seated`, crownsettle.py:633-640, so `reinstate` is covered; excluded statuses read from rules, :413-442) and has no visible crash path except `PaperMissing`. A genuine failure on three different minted events at once, including the three manifest checks (which only need a clean exit and internally consistent digests, :6047-6086, the agent checked these digests at step 43), is unlikely.
Label: SUSPECT - all 18 hidden-event checks plus the missing-paper check (all EXEC) failed, including the 3 manifest checks that a clean exit would pass, while 8 of 8 READ checks passed byte exact; the false `negative_hardcoded_sample_answers` fire (test_output.py:6383-6393) shows the program produced no output on the re-minted shipped event; the file was made by the editor's temp-file write (traj step 29) and nothing in the tests chmods it (test_output.py:5921-5925).

## 3. Instruction anatomy
- Goal (instruction.md:1): "A Ninefold Crown card event has closed, ... the publication was withdrawn after the appeals panel found the hall software had worked the rounds in the wrong order ... Recompute the event and hand back the settlement documents and the program that produces them."
- Navigation (:3): "Start at `/app/data/open_this_first.txt`, then ... `crown_settlement_overview.md`, which names the fourteen stages ... File names describe a role, not the content, so open them."
- The three non-text papers (:5) are explained with how to read them, including "take the live sheet by matching its key cell against this event reference and not by name or position, and take a clause or a key row only where its status is operative and its reference is this event."
- Procedure (:7): one paragraph that names every stage in order ("Settle which register filing governs each entrant, resolve the identifier closure, convert every quoted rating ... Then work the rounds one at a time and close each round before the next opens: settle who is eligible, award the byes the cap and the override allow, pair the pool on the printed keys and set constraints aside only up the ladder, screen every recorded board ..."). It gives order and subject, not formulas; every rule is in the 14 stage specs and 8 policy files.
- Number form (:9): "every ratio at exactly nine decimal places ... exact rational arithmetic ... Keep binary floating point out."
- Deliverables (:11, :13, :15): 31 documents listed by absolute path, schema and serialisation pointers, program contract ("Hold nothing about this event inside it ... Two runs over one input directory have to produce identical bytes, and so does the same event under another directory name").
- Hidden-input hint (:17): "Read `/app/data/corpus_sentinel_note.txt` before deciding a branch is absent. This event leaves some documented branches unreached; implement those from their specifications."
- Report to give (:19): live sheet key and name, pool in cents, void counts per reason, unpaired entrants, bye cap override, five ordering keys; "from a reading of your delivered documents made after the last run of your program".
- Tone: long dense paragraphs, numbered nowhere; exact filenames throughout.
- Side by side with ours (350-571 words): this one is the longest and the most procedural. Ours state goals and rules of engagement, e.g. district "Write one reusable program ... must follow the rules in general", emberforge "Four conventions ... are written down nowhere"; none of ours lists the stage order of the work. 09 lists even the file names of all 31 outputs; ours list only the files (emberforge) or point at a schema (district).
- Hypothesis check ("ours tell the agent too precisely what to do"): AGAINST for this task. The instruction is more procedural than any of ours and the run still scored 29 %; the score gap is explained by the grader (all hidden-event checks unexecuted, a -5 false cheat brand) and by judge criteria that want narrated examples. UNVERIFIED beyond this one task and run.

## 4. Every failed positive check and every fired negative
ctrf: 34 tests, 19 failed positives, 1 fired negative; all covered below. (Passed: 8 READ positives, 6 negatives not fired.)

Cause code P = verifier did not execute the program (permission, SUSPECT, UNVERIFIED). Each hidden-event check compares byte for byte against a reference minted in the test (`_same_bytes` :6020-6029, manifest `_manifest_consistent` :6047-6086). Predicted outcome if the program had run: UNVERIFIED for all; the agent's program matched the shipped event on all 31 documents.

| check (w) | what it checks / where the rule is written | what the agent did | cause |
| --- | --- | --- | --- |
| contested_core_exact (5) | the 13 spine documents (FAMILY_CORE :77-91) of unseen event EVAL_SEED; stage specs P01-P12 (P02 rules at spec_stage_p02:14-57, P08 voids at spec_stage_p08:6-45) | program derived the shipped event exactly (shipped_core_exact passed); sentinel branches read (step 5, judge R4 passed) | P |
| contested_pairing_exact (5) | 4 pairing documents (FAMILY_PAIRING :93-98); spec_stage_p07 ladder :14-41, search :42-60 | shipped pairing exact | P |
| contested_standings_exact (5) | 4 standings documents (:100-105); spec_stage_p13:3-24 | shipped standings exact | P |
| contested_prize_exact (3) | prize ledger, tie split, 4 division reports (:122-129); spec_stage_p14:3-57 | shipped prize exact | P |
| contested_publication_exact (3) | xml, control totals, summary (:131-135); spec_stage_p14:78-115, worked_examples.md | shipped publication exact | P |
| contested_manifest_consistent (1) | manifest describes the documents beside it (:6047-6086) | agent checked digests recompute (step 43) | P |
| wide_core_exact (5), wide_pairing_exact (5), wide_standings_exact (5), wide_prize_exact (3), wide_publication_exact (3), wide_manifest_consistent (1) | same six families on event CHALLENGE_SEED, program run with `--out` before `--data` (:6011) | agent tested both argument orders (step 43) | P |
| thin_core_exact (5), thin_pairing_exact (5), thin_standings_exact (5), thin_prize_exact (3), thin_publication_exact (3), thin_manifest_consistent (1) | same six families on event PROBE_SEED (thin profile) | none run | P |
| program_refuses_missing_paper (1) | non-zero exit and no document when `appeals_procedure_memo.pdf` is absent; program contract "Failure" crownsettle_program_contract.md:32-35 | program raises `PaperMissing` (crownsettle.py:31, 756) and main handles it (:1652-1671); never tested by the agent | P (it first needs a clean run of EVAL_SEED, :6185) |
| negative_hardcoded_sample_answers (-5, FIRED) | program reproduces the shipped event but not the same event re-minted under another identity (:6370-6393) | no event literal in the program (grep); own renamed-directory run identical (step 43); no runs under another identity | other: false brand caused by unrun program (UNVERIFIED); if P is false it would be a real identity-keyed bug (not seen) |
Points: 19 failed positives lose 67 of 85 (78.8 %); the fired negative costs 5 more. Points kept: 18 (shipped tier, 21.2 %) minus 5 = 13/85 = 15.29 %.
Checks a lazy agent also passes: `all_artifacts_exist` (1) and `core_documents_parse` (1) need only files with the right first column; the 5 shipped_*_exact families (15) are READ checks against a reference computed in the test, so a faithful replay of the visible event earns them too; 6 negatives are free for any program that runs.

## 5. Levers
| lever | family | where documented | weight share lost | triggered |
| --- | --- | --- | --- | --- |
| Hidden-event run under dropped uid, program file written by the editor | NEW (harness/permission) | not visible to the agent; test_output.py:5810, :5828-5835, :5921-5925 | tests: 67/85 = 78.8 % (39.4 pp overall) + 5 neg (UNVERIFIED) | probably yes |
| Replayer detector turns an execution failure into a cheat charge | NEW (detector coupling) | test_output.py:6370-6393 | 5/85 = 5.9 % of tests (2.9 pp) | yes (fired) |
| "Narrate one concrete example" judge criteria (R11-R26, R28, R30) | NEW (conduct evidence not asked for) | judge.toml; instruction.md:19 asks for six aggregate figures only | 41/72 = 56.9 % of judge (28.5 pp) | yes |
| 14-stage dependent chain, round loop where voids move next round's running points | B dependent chain | crown_settlement_overview.md:29-37; instruction.md:7 | 0 lost on shipped (byte exact) | handled |
| Live sheet by key cell, operative status rows, reference match across xlsx/pdf/docx | A hidden composition | instruction.md:5; spec_stage_p14:9-18 | 0 lost (judge R5 met) | handled |
| Unreached branches (reinstate, voided entry status) | D/F unreached branch | corpus_sentinel_note.txt:9-17 | unknown, in hidden events | UNVERIFIED |
| Decoy papers that govern nothing | E stacked constraints | paper_lineage.md "Papers that govern nothing" | 0 (R33 not fired) | no |
| Floating point ban, exact rationals | E | instruction.md:9 | 0 (R35 not fired) | no |

## 6. Judge
Rubric 31/72 = 43.06 %; negatives (R3, R10, R32, R33, R35) not fired (arithmetic matches).
| id | w | met | note |
| --- | --- | --- | --- |
| R1 navigation first | 1 | yes | steps 4-5 |
| R2 rounds closed in order | 5 | yes | loop implemented |
| R4 sentinel note read | 1 | yes | step 5 |
| R5 live sheet key + sheet name | 3 | yes | final message |
| R6 void counts per reason | 3 | yes | final message table |
| R7 unpaired | 1 | yes | |
| R8 bye override | 1 | yes | |
| R9 run elsewhere | 1 | yes | steps 43 |
| R11 live-sheet score band cell with status | 3 | NO | named the sheet and described the filter, not the cell value |
| R12 pdf clause numbers | 3 | yes | |
| R13 docx five bye order keys with revision | 3 | NO | showed the five tiebreak keys (R31) not the bye keys |
| R14 out-of-force entrant named | 1 | NO | dv_ember excluded, no entrant named |
| R15 tolerance of a named board | 3 | NO | only aggregate void counts |
| R16 voided board with counts_for_strength | 3 | NO | aggregate only |
| R17 entrant whose strength population drops an opponent | 3 | NO | aggregate only |
| R18 double rounding example | 3 | NO | not shown |
| R19 bye-cap override named | 3 | yes | |
| R20 withdrawn revision entrant | 3 | NO | no named entrant |
| R21 alias fold with entry_seq | 3 | NO | folded_ids shown, no entry_seq |
| R22 boundary tick | 3 | yes | |
| R23 crown_grade conversion named | 3 | NO | implemented, not shown |
| R24 evidence-level overturn board | 3 | NO | aggregate only |
| R25 round penalty shortfall | 3 | yes | |
| R26 ineligible member in paying group | 3 | NO | PL-BR-0112 found but group amount etc. not given |
| R27 code quality | 3 | NO | `rhe` opaque name; unused `byes_taken` in `sort_key`; `stage_p01` names |
| R28 effective band reconciled | 3 | NO | not shown |
| R29 lineage before program | 1 | yes | |
| R30 disposed notice | 1 | NO | |
| R31 five ordering keys | 1 | yes | |
| R34 pool | 1 | yes | |
Why they cost points: 13 failed criteria of weight 3 (R11, R13, R15, R16, R17, R18, R20, R21, R23, R24, R26, R27, R28) + R14 + R30 = 41. The agent verified aggregate consistency with scripts (steps 43-47) but narrated no single concrete case. Instruction asks only for six aggregate items (:19). Avoiding double pay: criteria read the trajectory (R15-R26 `evaluation_target = trajectory`), figures that land in documents are graded by tests, not by the judge; each asks for an "example" so it cannot be satisfied by copying doc text; weights 3 each give them 57 % of the channel.

## 7. How it passes QC and still beats the agent
- Everything is documented: stage specs state every rule; the traps register lists 40 decisions with owning stages and "states nothing about how the rule reads" (known_traps_and_footguns.md:3-7); sentinel note names unreached branches (corpus_sentinel_note.txt:9-17); the instruction states reading order, live-sheet rule, number form and report items.
- What makes the task hard to match exactly: 31 byte-exact documents, round-by-round feedback, three office formats parsed by hand, values only in xlsx/pdf/docx, six-sheet workbook where the live sheet is found by a key cell, 40 decisions across 14 stages.
- QC gap, same as task 08: the oracle's solve.sh produces a readable program (T/solution/solve.sh) but an editor-written file is not guaranteed readable by `nobody`; Step 10 never exercises that path. The replayer detector converts a non-run into a -5 brand.
- Anti-cheat design (strong): events minted from seeds in the test with own memorandum constants, key positions, ranks and unit conversions (test_output.py header :12-19); replayer detector re-mints the shipped event under another identity (:6370-6393); names-shipped-event literal scan (:6429-6438); input-blind, nondeterminism, filename dependence, dirtied directories, module shadowing detectors with disjoint ownership (:6203-6230).

## 8. Trajectory story
- 52 steps, 38 min, no gaps. Read navigation, overview, lineage, glossary, sentinel note, traps register (step 5), schema/serialisation/program contract (6), all 14 stage specs (7-8), file listing and tiny policies (9-11), parsed xlsx, docx, pdf with `zipfile`/`re` (12-14), profiled every register (15-28).
- Decoys never opened (legacy_season_extract, night_desk_audit); spectator_gate_returns only listed (step 9). No doc skipped.
- First write attempt at step 29 failed (`/app/out` missing), program (70 KB) created at step 31, edited at 32-34. First run (step 35) printed "a paper or value the specifications require is absent: penalty order disagrees between papers"; steps 36-41 debugged the PDF stream parsing (escape handling), step 40 fixed it.
- Self-tests: steps 42-47 wrote three audit scripts (program contract, schema, internal consistency, bye/void interaction, prize split) and ran the program on the shipped data only; checked both argument orders and a renamed directory (step 43). Never tested a different event (none available) and never tested the missing-paper refusal.
- Final run (48) wrote `/app/out`; `figures.py` (49-50) took the reported figures from delivered documents; cleanup (51).
- Final message (52) reports the six requested figures correctly per judge (R5-R8, R31, R34 met). It claims the program "holds no value of this event inside it" and lists verification; nothing false is evident. It omits examples the judge wanted.

## 9. Reusable patterns / things to avoid
- Hidden-event execution grading (3 minted events, each with its own constants) is a strong anti-replay lever, but make the program runnable by construction: chmod/copy the program to a root-owned readable path in the test before dropping uid, or the lever turns into noise.
- Do not let a cheat detector fire on "the program did not run": `_is_replayer` should require a clean run on the re-minted event (test_output.py:6391).
- Cross-document values (xlsx/pdf/docx) with status and reference rows are a good hidden-composition lever; the agent matched them (judge R5, R12, R19), so they cost effort rather than points.
- "Show one concrete named example" judge criteria are heavy (41/72) yet not requested by the instruction (it asks for six aggregate figures); they reward narration, not correctness. Use sparingly and only when the instruction says to explain.
- Having 18/85 test weight on shipped READ checks gave this agent 21 % for a replay-level result; keep shipped-tier weight low (08 used 4/139).
- A 806-word, stage-by-stage instruction did not prevent a low score; the instruction style is not the lever in this task.

```json
[
  {"task":"09_ninefold-crown-settlement-recompute","name":"hidden_event_execution_under_dropped_uid","family":"NEW","mechanism":"18 hidden-event checks and the missing-paper check run the delivered program as nobody; the editor-written program is never chmodded by the tests","where_documented":"tests/test_output.py:5810,5828-5835,5921-5925 (not agent-visible)","weight_share":0.788,"triggered":true,"cause_of_failure":"other: program not executed by verifier (UNVERIFIED)","evidence":"8/8 READ checks passed byte exact, 19/19 EXEC checks failed incl. 3 manifest checks; editor writes via temp file (traj step 29 error text)"},
  {"task":"09_ninefold-crown-settlement-recompute","name":"replayer_detector_brands_unrun_program","family":"NEW","mechanism":"re-mint of shipped event under another identity; no output counts as replay, so an execution failure costs -5","where_documented":"tests/test_output.py:6370-6393,6341-6348","weight_share":0.059,"triggered":true,"cause_of_failure":"other: false cheat brand from unrun program (UNVERIFIED)","evidence":"negative_hardcoded_sample_answers fired though crownsettle.py holds no EV-/NC-/PL-/dv_ literal and its own renamed-directory run was identical (step 43)"},
  {"task":"09_ninefold-crown-settlement-recompute","name":"narrate_one_example_judge_criteria","family":"NEW","mechanism":"15 judge criteria require a named concrete case from the session or final message though the instruction asks for six aggregates only","where_documented":"judge.toml R11-R26,R28,R30; instruction.md:19","weight_share":0.569,"triggered":true,"cause_of_failure":"other: output/narration not asked for","evidence":"score.json R11,R13-R18,R20,R21,R23,R24,R26-R28,R30 failed; agent reported only aggregates"},
  {"task":"09_ninefold-crown-settlement-recompute","name":"fourteen_stage_round_loop_chain","family":"B","mechanism":"voids move running points that the next round pairs on, so one misread stage moves everything downstream","where_documented":"crown_settlement_overview.md:29-37","weight_share":0.0,"triggered":false,"cause_of_failure":"none on shipped; hidden events unverified","evidence":"shipped_core/pairing/standings/prize/publication all passed byte exact"},
  {"task":"09_ninefold-crown-settlement-recompute","name":"live_sheet_by_key_cell_across_office_papers","family":"A","mechanism":"values live only in xlsx/pdf/docx; live sheet found by key cell; clause rows by status and reference","where_documented":"instruction.md:5; spec_stage_p14.md:9-18","weight_share":0.0,"triggered":false,"cause_of_failure":"none","evidence":"judge R5, R12, R19 met; pool 1284501 matched documents"},
  {"task":"09_ninefold-crown-settlement-recompute","name":"unreached_branches_sentinel","family":"F","mechanism":"shipped event leaves STANDING_REINSTATE and ENTRY_STATUS_VOIDED unreached while hidden events reach them","where_documented":"corpus_sentinel_note.txt:9-17; spec_stage_p02.md:21-23; spec_stage_p01.md:36","weight_share":0.0,"triggered":false,"cause_of_failure":"unknown (UNVERIFIED)","evidence":"program treats any non-drop/absence change as seated (crownsettle.py:633-640) and reads excluded statuses from rules (:413-442)"}
]
```

## Phase B: Docker replay of the saved run (tests only)

Method: Harbor 0.24.0 on Docker, QC Step 10 copies built by `exe_copy.py` (judge removed, tests-only weights, network opened). `solution/solve.sh` was replaced by a script that copies the saved `trajectories/claude-opus-5/run_1/artifacts/app/` files into `/app` as the oracle agent (uid 1000, the same uid as the real agent), then sets modes. V600: every delivered `.py` 0600, other files 0644. V644: every file 0644. One run per variant, 22 Oct 2026 09:19-09:24 IST (03:49-03:54 UTC). The oracle log of each trial confirms the mode (`-rw-------` in V600, `-rw-r--r--` in V644). No trial raised an exception. The judge was not run, so the rubric figure below is the recorded one.

| variant | tests reward | per-check result vs recorded ctrf.json |
|---|---|---|
| V600 | 0.1529 | identical (0 of 34 checks differ): faithful replay |
| V644 | 1.0000 | 20 checks change: all 18 `contested_*`/`wide_*`/`thin_*` hidden-event checks and `program_refuses_missing_paper` fail -> pass, and `negative_hardcoded_sample_answers` (-5) goes from fired to not fired |

Verdict: BROKEN GRADE, confirmed, including the false cheat brand. With a readable program the agent settles all three unseen minted events byte-exactly and refuses the missing paper correctly, and the replayer detector stands down. Corrected overall: 0.5 x 100 + 0.5 x 43.06 = 71.53 %, not 29.18 %. The 09/10 template's tests did not beat this agent. Its genuine loss in 09 is entirely the judge's "name one concrete example" criteria (41/72).
