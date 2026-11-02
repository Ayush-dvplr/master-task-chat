# B: collateral-gated-settlement-ladder (Harsh Gupta), board 6c051f3

Verdict A: GENUINE. Run: 62.73 / tests 30.38 / rubric 95.08.
Paths are relative to the task folder; run = `trajectories/claude-opus-5/run_1/`.

## 1. Inventory
- **Domain:** wholesale settlement / FX / collateral ledger.
- **Archetype:** the agent writes a reusable stdlib program `/app/out/transform.py <DATA_DIR> <OUT_DIR>`. It produces 13 artifacts (normalized.jsonl, summary, 5 region, 4 segment, product_summary, data_quality), plus a closing message with 9 figures that appear in no artifact (`instruction.md` L25-35, L43-45).
- **Files the agent sees:** 14, in `environment/data/`, no decoys:
  - adjustments.jsonl 505 KB / 2,652 lines
  - sales.csv 4,900 rows; refunds.tsv 2,900; legacy.txt 2,710 lines (latin-1)
  - corrections.log (1,154 correction lines)
  - counterparties.csv 2,308 rows / 1,960 ids; regions 2,320; inventory 4,511; product_catalog 2,060
  - channels, fx_rates, fiscal_calendar.json, policy.ini 483 B
  - schema.md 16,407 B (the contract)
- **Instruction:** 411 words (`wc -w`). It delegates every rule to schema.md: "Deciding which file feeds which figure is part of the work."
- **Tests:** 22 checks.
  - 4 shape checks at 1 point.
  - 15 positive checks at 5 points: 6 whole-artifact, 2 hidden-book, 7 per-rule (subset checks).
  - 3 negatives: -5, -3, -3.
  - Positive total 79.
- **Isolated vs whole-output:** 4 of the per-rule checks are truly isolated (gate, half-cent, orphan, corrections; `tests/test_output.py` L755-875). 3 look per-rule but end with a whole event-set or whole-map equality (L812, L823, L832).
- **Hidden inputs:** yes, but no new rule cases.
  - `_clone_book`: same data, relocated (L876-881).
  - `_permute(EVAL_SEED)`: shuffles rows of every file and multiplies one currency's rate curve by 1.0375 (L686-712). L884-894 asserts the total differs from the shipped book.
- **Expected values:** an independent reference `_settle` (L435-593) recomputes them at test time.
- **Judge:** `tests/judge.toml`, batched, gpt-5.6-sol, 19 criteria (16 positive = 61, 2 negative, plus R19 code quality inside the 61).
- **Reward split:** 50/50 (`reward.toml`: 0.5/79 and 0.5/61).

## 2. Rule map (graded rules)
| Rule | Where stated (file:line) | Sentence form | Trap explained? | Shipped data separates readings? |
|---|---|---|---|---|
| Adjustment `amount_minor` must be a JSON integer, else malformed | schema.md L34 "`amount_minor` must be a JSON integer and carries its own sign"; L148-149 malformed list "an `amount_minor` that is not a JSON integer" | Plain sentence, repeated inside a long enumerated list. **Neighbour rules pull the other way:** L14 "Every field value is trimmed ... before it is used"; L92-94 corrections replace a field "with that text before any parsing" | No (string-digit case not named) | Yes: 40 string, 34 float, 18 bool rows (step 10 Counter) |
| Collateral ladder gate (running balance per counterparty, block without moving balance) | schema.md (ladder section); instruction L37-41 "a counterparty's running balance decides which of its later events are accepted" | Plain plus restated in instruction | Yes (TRUTH pitfalls L465-470 mirror the spec text) | Yes, ≥150 blocked |
| Fold in UTC-instant order, not file order; tie-break | schema.md L10-11 "Row order in an input file is never significant except..." | Plain, scoped "except" | Yes | Yes, files shipped shuffled |
| Half-cent rounds half-up, quantize once | schema.md (money section) + policy.ini `[rounding]` | Default + config file | Partly | Yes, 680 half-cent products |
| Orphan refunds judged on raw sales ids | schema.md (Orphan debit links) | Plain | Yes | Yes, ≥20 stale links |
| Corrections: latest utc_ts wins, file order on ties, before parsing, ignore foreign field | schema.md L88-100 | Plain, multi-clause | Yes | Yes |
| FX carry-forward to the most recent earlier rate date; unquoted currency is malformed | schema.md | Plain | Yes | Yes, ≥50 events |
| UTC day shift from the warehouse offset; fiscal period or `unassigned` | schema.md L80-90 | Plain | Yes | Yes, ≥100 events |
| Counterparty dedup winner → segment | schema.md | Plain | Yes | Yes |
| 9 closing figures defined in the contract | instruction L43-45 + schema.md | Split across files | n/a | n/a |

All rules are reachable in schema.md. None is hidden.

## 3. Lever table (failed checks and criteria)
| id | wt | Rule graded | Agent's reading (evidence) | Correct reading | Mechanism | Self-test on shipped data catches it? | Fully stated? | Family |
|---|---|---|---|---|---|---|---|---|
| normalized_stream_is_exact, summary, region, segment, product, data_quality (6 checks) | 5 each = 30 | Whole artifacts exact | Accepts 40 adjustments whose `amount_minor` is a digit string. `transform.py` L371-384 `adjustment_minor`: `parsed = json.loads(value.strip())` and accepts an int. Step 10 output showed `'str': 40` | Not a JSON integer means malformed: skip and count | **Tolerant-parse reflex against a strict type rule.** The agent saw the anomaly and "repaired" it. Neighbour rules (trim every value, corrections inject text before parsing) make string parsing look consistent (INFERRED: no reasoning text in the trajectory) | **N.** The agent's checks are interlocks (step 36 totals sum, step 37 closing = openings + total, reconciliation 10,998 + 1,283 + 529 + 112 = 12,922). They hold whatever the reject set is, and no expected malformed count is shipped | Yes, L34 + L148-149 | F (error path / rejection); NEW sub-name "type-strict rejection" |
| fx_carry_forward..., utc_day_shift..., counterparty_dedup_segment | 5 each = 15 | Named sub-rule, but each ends with a whole event-set equality (L812, L823, L832) | Same 40 extra ids | Same | Hidden whole-output gate inside a per-rule check. The agent got the named sub-rule right (local repro: 0 field diffs) | N, same reason | The sub-rule is stated; the extra gate is test design | Gate amplification of F |
| reusable_transform_settles_a_relocated_book, permuted_rows_and_shifted_rates_settle_identically | 5 each = 10 | Hidden books exact | Same defect, same 40 rows (permute only shuffles and rescales) | Same | No new rule; the shipped-data defect repeats | N | Yes | F |
| Judge R15 | 3 | "verifies the pipeline against a second copy of the book whose rows have been reordered" | Step 49 second corpus = copy with legacy.txt removed | Shuffled copy | Unstated conduct | n/a | **NOT stated as conduct.** schema.md L10-11 says only that order is not significant | Judge conduct (IN-15/JD-15 risk) |

Genuine points lost on tests: 55 of 79 (all from one root). Judge: 3 (unstated conduct).

## 4. Contrast: what passed and why it was easy
- **Passed, 4 isolated rule checks (20 pts) and 4 shape checks (4):** collateral gate, half-up rounding, orphan links on raw ids, corrections.
  - Each is written in schema.md with the wrong route nearby.
  - Each is mirrored in TRUTH pitfalls L465-537, and each is the "big idea" of a paragraph.
  - This is the same as our leaked levers (DIAGNOSIS s0: one explicit sentence, trap named, agent codes it at first write).
- **Failed rule:** it is *not* in TRUTH's pitfall list (grep: L493 covers only "Passing `amount_minor` through as if it were USD cents"). So the peer team did not plan it as a lever.
- **Why it still cost points:**
  - It is a dull validation clause buried in an enumerated malformed list.
  - It sits next to rules that tell the agent to treat values as text.
  - The shipped data carries the exact separating case (40 rows), so the rule is fully learnable.
  - The agent's self-checks are all conservation identities that are blind to *which* rows get rejected.

## 5. Agent behaviour
- 55 steps, 15:15:03 to 15:34:59 (about 20 min wall).
- **Read order:**
  - schema.md cat (step 3)
  - policy/fiscal/heads (4-5)
  - corrections stats (6-7, 19)
  - type and oddity census of every file (8-18): it counted the 40 string amounts at step 10
- **Plan:** none written (messages empty).
- **Write:** one-shot create at step 22 (15:24:31, about 9.5 min in), after a failed create at step 20 (dir missing) and mkdir at step 21.
- **Self-tests:**
  - instrumented reject-reason census (step 27)
  - half-cent census (28)
  - interlocks (36-37)
  - one counterparty ladder trace (46)
  - rerun diff (41, 44)
  - second corpus with legacy.txt removed (49)
  - None compares against an independent expected value, and none targets the string amounts.
- **Edits after first write (38-40, 43):** encoding and timestamp parsing only. No change to `amount_minor`.
- **Did not notice the defect.** Final message (step 54) says "Verified end to end: 12 922 input events reconcile exactly as 10 998 accepted + ...". The reference accepts 10,958.

## 6. Test design
- **Expected values:** independent reference at test time (`_settle`) on the embedded shipped book, on a relocated clone, and on a permuted, rate-scaled book.
- **No partial credit:** `_same` is exact equality.
- **Negatives:** memorized shipped answers (-5), network/shell (-3), nondeterminism (-3). None fired.
- **Anti-cheat:** permuted book total must differ from the shipped one (L884-894). Writes outside the out dir are asserted during `_run_transform`.
- **Whole downstream documents graded:** 6 artifacts on shipped data, 2 hidden books, plus 3 per-rule checks with a whole-set assert.
- **Shipped-data-only share:** 69 of 79 positive points (87%). The hidden books (10) add no new rule cases.

## 7. Judge design
- **Failed criterion:** R15 only, an unstated conduct.
- **Reusable patterns:**
  - R18 (-5): "states a closing report figure that differs from the value its own pipeline produced" (honesty, checkable from the trajectory).
  - R17 (-3): same error 3 turns in a row.
  - R19: code quality with named helpers and specific exception types (meets JD-18).
- **Weakness:** R1-R9 pay 31 points for merely *stating* nine figures. The agent's figures may be wrong (it included the 40 rows) and still pass. JD-8 is fine because no test reads these, but correctness is ungraded.
- **QC rule check:**
  - JD-15 (04_Judge_QC.md L92-97: a conduct criterion "must hold for every competent route"; a constraint must quote a contract sentence). R15 breaks this: it demands a specific verification method the contract never asks for. R13 "inspects every input file ... before it designs" is borderline for the same reason.
  - JD-7: the oracle meets them.

## 8. QC safety of the lever that worked
- **Type-strict rejection rule** (rule stated in spec, case shipped in data, neighbour rules imply text): **SAFE.**
  - IN-15 met (schema.md L34, L148-149).
  - TS-19 learnable.
  - No negatives involved, so TS-16 and AL-28 are not touched.
- **Gate amplification via whole-set asserts inside per-rule checks:** **RISKY.**
  - TS-13 "One property per test" is broken by fx/day/dedup checks that assert two properties.
  - TS-26 double payment: these three plus normalized_stream_is_exact all read the same observable (the accepted event-id set), so one decision is paid four times.
  - TS-20: weight is not semantic when one validation clause is worth 55 points.
- **Whole-artifact exactness checks** (stated in instruction L37-41): **SAFE** when stated, as here.

## 9. Writing style (technique, not content)
1. schema.md L34: "`amount_minor` must be a JSON integer and carries its own sign". A type constraint is stated as a plain property of the field. It does not say "strings are malformed" or show an example, so the separating rows in the data stay unflagged.
2. schema.md L148-150: the malformed definition is one long enumerated sentence. Each clause carries equal visual weight, so the type clause is clause 8 of 10.
3. schema.md L10-11: "Row order in an input file is never significant except in the two places this contract names file order as the tie-break." A global default plus a counted exception: it forces the reader to find both places.
4. schema.md L13: "Every field value is trimmed ... before it is used". A global normalisation rule creates a plausible but wrong generalisation for typed JSON fields (INFERRED contributor).
5. instruction L37-41: states the all-or-nothing exactness and the interlock up front, so whole-file grading is a fair, stated rule rather than a hidden gate.
