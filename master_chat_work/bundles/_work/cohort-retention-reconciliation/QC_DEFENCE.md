# QC_DEFENCE cohort-retention-reconciliation

Built for P12 r1 (board 0b8ac36) from LEVERS.md, DESIGN.md, solution/TRUTH.md and the bundle.
Kit HEAD 3fb1650b3b478fd02f11745bad0861ba685c1390. Entries marked INFERRED are my reading,
not written down by the author.

## CR-1 register lists every reason (family A)
- What: `data_quality.json.rejections[*].reasons` lists every reason true of the raw row tested on
  its own; field named in schema.md Outputs, defined only in environment/data/audit_policy.md
  "Rejection register".
- Why: punishes "one reason = the stage that removed the row" (mutant 0.867 QC-measured).
- QC check it could trip: DS-21 / IN-15 (rule only in a spec file), AL-4 hidden behaviour.
- Why not a defect: IN-8 "a specification or schema file shipped in `environment/`" is a valid
  source; the rule is stated in full in audit_policy.md, which schema.md points to.
- Safe fix if QC insists: add one schema.md sentence pointing at audit_policy.md "Rejection
  register" by name; keep the definition where it is.

## CR-2 plan in force on the event date (family B, decoy)
- What: weight from latest plan_history row with effective_from on/before the event date for the
  resolved account, later row on tie, else the accounts.csv opening plan (audit_policy.md Plans).
  accounts.csv `plan` column is the decoy; shipped boundary a002 enterprise 2026-02-12 = e009 date.
- Why: punishes accounts.csv plan (0.717), strict-after (measured by author), earlier-wins tie (0.733).
- QC check: DS-25 / IN-15 (decoy hiding a rule).
- Why not a defect: rule written out in audit_policy.md; IN-8 accepts shipped spec files.
- Safe fix: name audit_policy.md "Plans" in schema.md weighted-revenue line.

## CR-3 every non-purchase revenue type subtracts (family E, scope by omission)
- What: schema.md Revenue "A purchase adds its value_cents; every other revenue event type
  subtracts it." Hidden studies use chargeback, credit_note, reversal.
- Why: punishes "only refund subtracts" (0.733) and "all add".
- QC check: AL-4 undocumented edge case.
- Why not a defect: the sentence covers every type by quantifier; nothing is undocumented.
- Safe fix: none needed; if pressed, add "including types the shipped extract never uses".

## CR-4 strict malformed test (family F)
- What: date must be a real date written 4-2-2 digits YYYY-MM-DD; value a non-empty digit run.
  Lenient fromisoformat/int accept 20260110, +0, " 9900", 1_000.
- Why: punishes lenient parsing (author mutants 0.400 / 0.450, INFERRED still close).
- QC check: TS-17 honest agent loses.
- Why not a defect: schema.md Cleaning step 1 states the shape; the test follows the text.
- Safe fix: add one example of a rejected compact date to schema.md.

## CR-5 dedup among survivors of steps 1-2, raw key (family B)
- What: duplicates are tested only against rows that survived malformed and out_of_calendar; key is
  raw (account_id, event_date text, event_type); first kept. Register `duplicate` reason, by
  contrast, uses every earlier raw row (audit_policy.md).
- Why: punishes dedup over every raw row (0.433) and dedup on resolved account (0.65).
- QC check: IN-13 contradiction (count vs register definitions differ).
- Why not a defect: the two are different stated quantities (removal step vs reason test on its own);
  both are written out. INFERRED: deliberate contrast.
- Safe fix: one sentence in audit_policy.md saying the reason test differs from the removal stage.

## Hidden whole documents (42/60) and fixtures (17/60)
- What: 3 unseen generated studies graded per whole document; rule-isolating fixtures 17/60.
- Why: a program that memorises the shipped extract earns 1/60.
- QC check: TS-20 weight balance, CL-2 forgery price.
- Why not a defect: CL-2 "A small share is normal"; forgery price measured by QC 0.0833 before fix.
- Safe fix: make format/rerun checks require the full correct file set (done in P12, F-03-1).

## Six single-figure judge criteria (R1-R6) and R8 honesty negative (retired)
- Retired in harden r2 and P12 r2: the instruction no longer asks for any figure in the final
  reply (instruction.md line 7 deleted for AL-2). Kept below for history only.
- What (old): final reply must state six shipped figures; R8 -5 for presenting figures from a program
  never run after its last edit.
- Why: forces the agent to run its program and report it; punishes hand-computed claims.
- QC check: JD-8 overlap with tests (the figures also sit in shipped output, but no test grades the
  shipped figures: artifact_set only checks presence).
- Why not a defect: JD-8 is double payment; tests grade unseen studies, judge grades the reply.
- Safe fix: none needed.

## R7 code-quality criterion (replaced in P12)
- Old R7 prescribed separated cleaning/writing functions (JD-15 preference, JD-18 missing quality).
- Now judges ordinary code quality (JD-18 conduct criterion). Safe fix if QC objects to weight:
  keep weight 1.

## Independent oracle (DS-24)
- solve.py must not restate test_output.py `derive`. P12 rewrote solve.py as a per-row tagging pass
  plus per-artifact builders; the grader keeps its single-loop reference.

## Harden round 2 additions (23 Oct)
- CR2-L1 manifest: the note states exactly what each figure counts (W7); the control is honest and matches the shipped files under its own definition. A mismatch is reported, not fatal (schema data_quality paragraph).
- CR2-L2 identifiers: one reading. The Identifiers section lists which fields are identifiers and says every other field is read exactly as written, so ` 4500` is malformed and the duplicate key uses normalised ids with the date as written. The shipped extract carries the bare-property separating row e035 only (W5).
- CR2-L3 ledger: fully stated in the Revenue section; order is the cleaned order already defined by the Cleaning section; ties between same-type events of one resolved account do not change any total (min chain is order-invariant).
- CR2-L4 override: names the field `weight_override` exactly (W4) and the segment source (accounts.csv of the resolved account). schema.md states the default; the exception lives in the audit policy, which schema.md says governs.
- Judge: no figure criteria (J1). R1-R5 grade conduct on cases the shipped data lacks and endorse no reading the tests penalise; R6 is a named shape (typed except clauses that raise or report); R8 is the honesty negative. Penalty groups by act all <= 5 (OUT/STACKING_CHECK.md).
- Whole-document checks return the share of the three hidden studies matched (rewardkit accepts float criteria); failure text is printed as `check note:` lines (G7).

## P12 r2 additions (23 Oct, board f6164ef)
- JD-7 / DS-22: solve.py validates dates with calendar.monthrange and has no except clause, so R6 holds for the oracle. Safe fix if QC objects again: never loosen R6; keep the oracle free of try blocks.
- AL-2 / CL-1: no figure is requested in the final reply; R7 and R8 grade conduct and honesty only.
- AL-27: every regenerated study carries a same-day same-type purchase pair from two pre-merge ids of one resolved account and a repeated in-calendar row for the excluded account. Measured: a resolved-key duplicate solver 0.7418, an exclusion-before-duplicate solver 0.9296 (tests channel, local scorer). Safe fix: none needed.
- AL-27 (v4, r3): seven rules named untriggered. Six now triggered by side rows from a second seeded stream (study otherwise unchanged): same-day purchase then refund undrained (date-only and type-descending order 56/71), last-period cohort with no revenue (dropping zero entries 66/71), offset_zero_is_full false in the first hidden study (always-full 70/71), events value_cents_sum fault in every study equal to minus the padded values (constant-zero and sign-flip residual 68/71), period numbers crossing 9 to 10 (lexical calendar 45/71), three faulty files written unsorted (manifest order 66/71, reversed 66/71). Rate 0/0 (schema.md:15-16) left UNSURE: only weighted_share can hit it and a zero weighted total removes L4 grading from that study. Mutants in p12_r3/gates/al27/mut.py. Safe fix if QC objects again: add triggering rows, never state the figure.
- IN-16 (v4, r3): merge tie on equal effective_from now settled in schema.md:41 (later row in the file wins, same words as audit_policy.md for plans) and graded by a hidden tie row placed before the winning row (earlier-row reading 36.667/71).
- DS-22 (v4, r3): solve_py_sha256 and line count recomputed after the last solve.py edit; check `shasum -a 256 solution/solve.py` against TRUTH.md before shipping.
- TS-13 (kept): the cohorts gate in `_written_study` stops format and rerun credit (6/71) for programs whose cohorts are wrong. Splitting it pays a wrong program for formatting. The a2 program scores the same with or without the gate (0.0563).
- TS-29 (recorded): hidden-document checks return a share in {0, 1/3, 2/3, 1}; TRUTH.md Verification states the deviation. Safe fix if QC insists: one bool check per seed at weight 5/3 each.
