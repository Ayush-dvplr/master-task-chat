# DESIGN 8d509b8: gate v3.6 judge-only harden (district-heat-flex-procurement)

Verdict: the master's target (rubric <= 20% mid, <= 25% upper on BOTH a10 and a11) cannot be
reached with judge.toml + TRUTH.md as the only changed files. Option B below reaches it, but it
needs one extra file unlocked: `solution/solve.sh` (own-extract / altered-copy stage only).
Tests, test weights, reward.toml, instruction, docs, data and solve.py stay byte-unchanged under
both options. Master decision needed: "go B" or "go A" (A = best in-brief, misses the gate).

## 1. TRIP summary (a11, OUT/TRIP.md; a10 evidence from its judge_response.txt + trajectory)
- a11: tests 173/237 = 73.00 (lost only wide_0..wide_3, 64 pts, all WRONG, silent);
  judge 15/24 = 62.5; final 67.75. Skipped R1-R3 only.
- a10: tests 173/205 (old tests); judge 9 positive - 5 (R7) = 4/24; without R7 9/24 = 37.5.
- Phase A: staged tests/ and environment/ vs BUNDLE `diff -rq` empty; task.toml differs only
  in allowed_hosts (host.docker.internal). Run graded the frozen bytes.
- Both runs already build synthetic extracts with hand figures (a11 step 27 /tmp/synth_check.py;
  a10 step 24 /app/synth_test.py) and both recompute shipped-data figures outside the program
  (a11 steps 33-34; a10 steps 27-28). Neither ever reran the program on an altered copy of
  /app/data (P-d), and neither had two half-cent intervals rounding in opposite directions.

## 2. Arithmetic
- Now: final 67.75 = (73.0 + 62.5)/2. Gate: final < 50 with tests 73.0 needs rubric < 27.0;
  master target rubric <= 20 mid / <= 25 upper -> a11 must earn <= 4.8 mid, <= 6 upper of 24.
- Positive judge total is locked at 24: reward.toml `judge = 0.020833333333333332` (= 0.5/24) is
  byte-locked (G7), so any re-weight must keep the positive sum at 24.
- JD-7 requires the oracle (solve.sh output) to show every positive criterion. With solve.sh
  locked, the oracle-shown acts are: own extracts E1 drawn allowance (solve.sh:337-346), E2 start
  order (:347-356), E3 composed rate above cap -> credit_cents (:365) and cap_binding_count (:366),
  E4 half-cent interval 0.5 -> 0 (:367-374); shipped-data self-checks grants+funded (:179-207,
  print :216), allowance (:148-167, :219), credit (:132-145, :222); plus R5/R6/R11 (non-probe).
- a11 did every one of these except E1, E2, E3. Best in-brief split: E1, E2, E3-credit, E3-cap as
  four w3 criteria = 12 skipped points; the other 12 points must sit on acts a11 did (E4, the
  three self-checks, R5, R6, R11, each >= w1). a11 floor = 12/24 = 50.0% -> final >= 61.5.
  (Splitting E3 also risks JD-14 one observable paid twice.) => in-brief infeasible.

## 3. Option B (recommended): retarget R4, R8, R9, R10 at acts both runs skipped
Unlock needed: `solution/solve.sh` gains four oracle demos inside the existing `|| true`
own-extract stage (after :374), printing plain lines via the existing report() (:331-332, DS-17,
no R numbers). solve.py and the self-check stage stay as they are; so does the exit code rule.
- D1 (for R4'): own extract, one chosen offer with intervals [1500, 2500] Wh at base 1000 ->
  1.5 -> 2 and 2.5 -> 2, credit_cents 4 by hand (half up would give 5; one rounding of the 4.0
  total would give 4, so the two halves are what separates the rules).
- D2 (for R8'): copy /app/data to a tempdir, lower one event-region's pools.txt pool below the
  claims of its beneficiaries, refresh that file's export_manifest receipt, rerun the program,
  recompute that event-region's grants with the self-check's grant routine, compare.
- D3 (for R9'): copy /app/data, set the allowance that one chosen offer's site draws on below that
  offer's relief, refresh the receipt, rerun, report whether the offer is still selected (by hand:
  no).
- D4 (for R10'): copy /app/data, raise one event's uplift_millicents_per_kwh in events.json so a
  chosen offer's rate goes above its card's cap, refresh the receipt, rerun, recompute that
  event-region's credit_cents with the self-check's credit routine, compare.
Draft wording (type "agent behavior", target trajectory, w3, one act each, tied to
instruction.md:3 "reusable ... other extracts" and :9 "how you checked it"):
- R4' The agent constructs its own extract in which one chosen offer has two interval amounts of
  exactly half a cent, one with an even whole cent below it and one with an odd whole cent below
  it, works out that offer's credit_cents by hand, runs derive_report.py on it, and compares.
- R8' The agent runs derive_report.py on a copy of /app/data in which it lowered one
  event-region's grant pool in pools.txt below the claims of its beneficiaries, and compares the
  grants reported for that event-region with grants it worked out outside derive_report.py.
- R9' The agent runs derive_report.py on a copy of /app/data in which it lowered the allowance a
  chosen offer's site draws on below that offer's relief, and checks whether the region document
  still selects that offer.
- R10' The agent runs derive_report.py on a copy of /app/data in which it raised one event's
  uplift so that a chosen offer's rate is above its card's cap, and compares that event-region's
  credit_cents with a figure it worked out outside derive_report.py.
R1, R2, R3, R5, R6, R7 (-5), R11 (J4) unchanged. Positive total 3*7 + 1*3 = 24 (unchanged).
J3a: the existing R7 (-5, critically_important) is the honesty negative carried from QC v8; it
stays as is (AL-28: only negative, disjoint). [If master wants the -3 J3a form, say so.]

## 4. Judge band table (positive criteria only; no negative assumed)
| id | w | a10 now | a11 now | a10 under B | a11 under B | evidence (quoted / step) |
|---|---|---|---|---|---|---|
| R1 | 3 | 0 | 0 | 0 | 0 | a10 "earlier event selects SA3 rather than the shared SA1 offer"; a11 "SITE1's later offer still fits exactly" |
| R2 | 3 | 0 | 0 | 0 | 0 | a10 "SA1's 1000-tick allowance covers both"; a11 "dispatch_start text also sorts earlier" |
| R3 | 3 | 0 | 0 | 0 | 0 | a10 "EV-A/SA3 ... zero uplift"; a11 "A-OFFER-3 belongs to EV-A, whose uplift is zero" |
| R4 / R4' | 3 | 1 | 1 | 0 | 0 | a10 one 1.5-cent interval ("expected ... 2 cents"); a11 one 0.5 interval + a 1-cent one; neither has two opposite halves |
| R5 | 1 | 1 | 1 | 1 | 1 | both Fraction/Decimal, no float |
| R6 | 1 | 1 | 1 | 1 | 1 | a11 "step 33 runs python3 out/derive_report.py data out"; a10 steps 36, 39 |
| R8 / R8' | 3 | 1 | 1 | 0 | 0 | now: a10 step 28, a11 step 33 grants recompute; B: no altered copy of /app/data in either run (a10 step 32/36 reran unaltered data to /tmp/o2, /tmp/o3) |
| R9 / R9' | 3 | 0 | 1 | 0 | 0 | now: a11 step 34 draws_from replay; a10 "aggregate counts"; B: no altered copy |
| R10 / R10' | 3 | 0 | 1 | 0 | 0 | now: a11 step 33 Fraction credit; a10 "compares to another in-memory calculation"; B: no altered copy |
| R11 | 1 | 1 | 1 | 1 | 1 | J4 kept |
| total /24 | | 9 (37.5%) | 15 (62.5%) | 3 (12.5%) | 3 (12.5%) | |
- Upper uncertainty under B: one w3 criterion read generously (e.g. R8' credited for a10's own
  shortfall extract) -> 6/24 = 25.0%.
- Predicted final under B: mid (73.0 + 12.5)/2 = 42.75; upper (73.0 + 25.0)/2 = 49.0 (< 50).
- Fresh-run band: P-d altered-copy probes pass ~25% per peer data (LEVER_RULES 4); 4 of 7 probes
  are new skipped acts, so a fresh careful run predicted 3 + ~6 = 9/24 = 37.5% upper, ~20% mid.
  Risk: R8'-R10' are one correlated habit (altered-copy rerun); an agent that has it earns 9 more.
- Option A (in-brief best): split R3, keep the rest -> a11 12/24 = 50%, final 61.5; fails the gate.

## 5. Touched-rule table (Option B; written again in HARDEN_REPORT after build)
| id | touched how | rules re-checked | verdict |
|---|---|---|---|
| R4' | retarget same family (own extract, half cent), w3 kept | JD-2 one judged act; JD-5 one act; JD-6 trajectory; JD-7 oracle D1 line; JD-9 no test covers trajectory acts; JD-13 no method named (hand figure, no algorithm); JD-14 differs from R3 (rate) and tests (outputs); JD-15 needs a constructed case, not satisfiable by any output; AL-2 tied to schema.md:120-121 + instruction.md:9; AL-28 no negative overlap; IN-15 no new instruction text | pass (planned) |
| R8' | retarget from shipped recompute to altered-copy rerun | same list; JD-7 oracle D2; JD-14 distinct from grants_match* tests (hidden outputs) and from R4'/R9'/R10' (different file altered); AL-2 schema.md:211-250 + instruction.md:3 | pass (planned) |
| R9' | as R8' | JD-7 oracle D3; AL-2 schema.md:97-100, :352-353 | pass (planned) |
| R10' | as R8' | JD-7 oracle D4; JD-14 vs R3: R3 = own extract composed override+uplift+adder; R10' = altered shipped copy; flag as the riskiest overlap, fallback: R10' alters a recipient weight to zero instead (schema.md:91-92) | pass (planned, flagged) |
G5 vacuity: an agent that changed nothing has no trajectory acts and no program -> earns 0
positive (R5, R6, R11 also need a program). G1/G2: no QC Fix text pasted, no weight moved to a conduct
criterion (all four stay w3 probes). G7 (Option B): byte diff vs b18d48a1deda limited to
tests/judge.toml, solution/solve.sh, solution/TRUTH.md.

## 6. Not run (per notes 5): kill test, cost table, blinds. Tests side restated 73.0 from a11.
