# Billing Mechanism Card

Task: `59417607-2254-5165-b703-0d5a4aeb7367`. All task-relative references below resolve under `/Users/mac/Desktop/Terminal Bench/anubis-stage-2/59417607-2254-5165-b703-0d5a4aeb7367/`. Evidence files are under this report's `evidence/billing/` directory. No original files were edited.

## Actual Cause

The dictionary says a handset is set at issue and **never adjusted afterwards**, with one whole-minute offset in -19..19 (`environment/data/record_dictionary.md:19`). Opus implements exactly that temporal scope: `trajectories/claude-opus-5/run_1/artifacts/app/out/transform.py:217` searches one offset per handset across the extract; lines 344-346 use it for every closing.

Every hidden profile instead changes one or more handset offsets during the extract (`tests/test_output.py:66`, generator offset function at 445-463). The reference independently solves offsets **per exchange day**, then indexes `(day, handset)` at 935-961. This is not merely an undiscovered value: the reference uses a model the authoritative contract excludes. Classify the lost 90 raw test weight as UNFAIR, not RULE-MISREAD or LATENT-WRONG.

The controlled counterfactual injects only the reference's day/handset offset map into the captured program's completion-time expression; it leaves its existing inference call and all billing, amendments, serialization, and report code intact. All 18 cases become exact. A stricter separation probe corrects ONLY handsets whose offsets change and leaves every constant handset's inferred value alone: again all 18 cases become exact (`evidence/billing/clock_separation.json`). Epochs are explicitly converted: verifier epoch 2000-01-01 versus agent epoch 1970-01-01, a 10,957-day difference (`tests/test_output.py:755`; `transform.py:14`). See `scripts/diagnose.py`, `scripts/billing_separation.py`, and `evidence/billing/counterfactual_summary.json`. This is diagnostic truth injection, NOT a fair agent solution and NOT the replay submission.

## Hidden Inputs

There are 18 deterministic hidden extracts, not 18 checks of the shipped data. `HIDDEN_EXTRACTS` holds seed/profile pairs at `tests/test_output.py:66-220`; `build` starts at 294; `_hidden_files` at 1200 also supplies the shipped documentation and chooses a minimum that separates gross and net scope at 1184-1197. Common plants exercise exact 08:00/18:00 boundaries, cycle rejection before void/unknown, equal-time allowance ordering, amendments/reverts, conflicting CSV/legacy duplicates, and lost-call echoes (485-697).

| Hidden Check | Seed | Distinctive Additional Targets |
|---|---:|---|
| 01 | 1312105 | 21 days, 8 handsets, 40 clients; one +6 minute change, base zones |
| 02 | 1215295 | 18 days; two changes on one handset; Meridian spring zone step |
| 03 | 1432672 | 10 handsets, 5 sharing lines; three independent changes |
| 04 | 1335862 | Change then return; rate-card boundary |
| 05 | 3438361 | 11 handsets, 7 sharing; -6 change; header-selected final current card |
| 06 | 1665887 | Three changes; unrated service; legacy durations in minutes |
| 07 | 1464348 | Change/return; shared lines; UTF-8 BOM |
| 08 | 2729015 | Two negative changes; Levant zone step; 21 days |
| 09 | 3679495 | 12 handsets, 9 sharing; change and rate boundary; final current card |
| 10 | 1278647 | Three changes; autumn zone fallback; exact tier edges |
| 11 | 2752772 | 20 days, 14 handsets, 11 sharing; deeper revert chains, 60 edges, 30 edge amendments |
| 12 | 2446504 | Two negative changes; unrated rows; BOM |
| 13 | 6329396 | 11 handsets, 8 sharing; three changes; legacy minutes |
| 14 | 2776529 | -8 change; six completion ties; final current card |
| 15 | 1422971 | 21 days; change/return; rate boundary |
| 16 | 1849806 | 12 handsets, 10 sharing; two changes and zone step |
| 17 | 1438809 | Three changes, rate boundary, unrated rows, legacy minutes, BOM, final current card |
| 18 | 1656186 | -7 change; shared lines, unrated rows, legacy minutes |

Each row also includes the common plants, so its name is not an isolated causal diagnosis. The actual field deltas for every row are in `case_01.json` through `case_18.json`; `CAUSES.csv` gives a first expected/actual field and links the complete set. Positional JSONL deltas include ordering cascades and must not be interpreted as independent bugs.

## Rule Density And Burial

The input has two short but dense authoritative documents: 55 lines each in `record_dictionary.md` and `billing_standard.md`. Using operational families rather than counting sentences, there are at least 16 interacting obligations: CSV/BOM normalization, source precedence, clock recovery, local zone transitions, cycle eligibility, amendment issue-time eligibility, revert cancellation, equal-time action choice, service aliases, rate-card selection, rate effective intervals, holiday/tier precedence, allowance ordering, credit application, scope thresholds, and cent rounding/serialization. This is an analyst count, not a claim of 16 separately scored facts.

Load-bearing details are not only in the instruction. Examples: CSV wins duplicate identities (`billing_standard.md:27`); regional minimum uses gross while segment minimum uses net (35); half-even cents (39); rate card comes from the cycle header (43); 08:00/18:00 tier boundaries (55); allowance consumes latest completion first and reverse lexical references on ties (7). Discovering and combining these is legitimate difficulty. Overriding the explicit never-adjusted clock rule is not.

## Checks And Lost Weight

Seven shipped-artifact/stdout checks earn +1 each. Eighteen `hidden_extract_*_exact` checks earn +5 each: 90/97 positive weight. Six negative checks did not fire. Recorded score is 7/97 = 7.216495%, exported as 7.22%. The hidden predicate requires runtime success within 60 seconds AND exact bytes for all 13 reports (`tests/test_output.py:1357-1366`). `_run_extract` stages new paths, executes the captured `transform.py` under an audited unprivileged child, and returns runtime/audit/report information (1245-1315).

`_hidden_exact` catches every exception and returns False (1361-1362); the subprocess discards stderr (1255). The diagnostic wrapper redirects that discarded stream to evidence and records exception type/message/traceback and wall time without changing expected data or equality. The captured program succeeds on all diagnostic hidden cases; these are neither crashes nor timeouts. The score-level whole-extract gate amplifies the wrong temporal model into all eighteen lost checks.

Judge: 14/58 earned, 44 lost raw weight. R1 and R3-R8 lose 35 on wrong what-if figures; R13-R15 lose 9 on actual-open tracing, ambiguous-fit error, and empty-fit behavior. All expected/actual integers, verbatim reasons, and JSON paths are in `RECORDED_CHECKS.csv`; the ten lost criteria and trajectory references are in `JUDGE_LOSS.csv`. Final figures/check sizes appear in trajectory `steps[56]`, step_id 57. The same clock-scope mismatch is a strong explanation for changed-extract figure discrepancies, but absent a separate field-level replay of each what-if this extension is **INFERRED**, unlike the hidden-test attribution.

## Careful Engineer Versus Trap

Opus did not simply skip validation: it reports a 23-extract/35,328-closing independent cross-check, BOM/quoted/order perturbations, path checks, and small brute-force clock checks (`evidence/billing/trajectory_readable.txt:2440`, original step_id 57). A careful engineer following the explicit constant-clock contract could make the same hidden-test choice. The default tie-breaking and best-fit fallback are more legitimately questionable: ambiguity should not silently become invented certainty. Listing directory contents is not proof of actual file opens, explaining R13 independently of arithmetic.

## QC Fit

Kit root: `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`.

| Gate | Fit | Evidence And Reason |
|---|---|---|
| IN-8 | LIKELY FAIL | `01_Instruction_QC.md:38`: hidden outputs require daily offset changes forbidden by dictionary line 19. Prompt delegation to docs does not authorize contradicting them. |
| IN-17 | PASS | `01_Instruction_QC.md:47`: pointing to the authoritative documents is orientation, not pre-announcing a data discovery. The needed clock-model correction would be a requirement, not an illicit hint. |
| AL-1 | LIKELY FAIL | `05_Alignment_Integrity_QC.md:21`: all hidden checks depend on a temporal rule not established by shipped data and opposite the stated rule. |
| AL-27 | PASS for inspected load-bearing targets | `05_Alignment_Integrity_QC.md:38`: concrete both-fault plants exist for outside-cycle+unknown and outside-cycle+void (514-520,600-604, amendment generation); allowance ties, edge timestamps, reverts and conflicting duplicates are actually constructed. This limited trigger-depth finding is not a certificate that every sentence in the bundle was mutation-tested. |
| CL-4 | PASS by explicit-exact-match exception | `Final_checklist.md:491`: instruction line 3 deliberately requires every report byte-for-byte. One wrong fact can therefore lose a whole +5 extract by the kit's express exception. This does not cure IN-8/AL-1. |

One-fact sensitivity: changing one scalar in one otherwise exact hidden report loses that extract's +5/97, or 5.154639 percentage points; changing one global temporal assumption can lose +90/97. The latter is propagation, not 18 independently demonstrated reasoning failures.

## Copy Into Another Domain

For a service-reconciliation task, use 12-18 deterministic extracts and about 12-16 interacting, fully grounded rule families across two compact source documents. Combine amendments with eligibility timing, authoritative revision selection with tempting stale files, and threshold scope with credits. Place paired defects in precedence fixtures. If clocks can change, state their temporal granularity or supply determinate calibration evidence; never describe them as immutable. Grade normalization, amendment decisions, amounts, and scopes separately, reserving a small final integration gate for canonical bytes. Add three lightweight conduct probes: an independently calculated boundary case, a conflicting-source case, and actual file-open audit evidence. Deduplicate any repeated root error across report copies.
