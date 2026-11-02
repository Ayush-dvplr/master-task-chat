# Harden round 2, Phase 2 and 3 report: tariff-engine-audit-repair (board 7f1d771)

Phase 1 was board 0dd7a8c. Its verdict was GENUINE, primary cause 4. Option A and Option B are dropped (master note 1).
Bundle tree after this round: `a8f9a3b35b42` (sha256 over sorted paths and bytes).
Session rename: `name_session.py 7f1d771` ran, and the opencode list shows `ses_e8dc62e62ffeYF3KhEguCguAye`. Codex had no match.
QC kit HEAD: `5574d77eb9f22c207ba05fd8f9ac31d42ba45271`, as expected.

## L11 shortlist and pick

| shape | fact type (list b) | witness | verdict |
|---|---|---|---|
| S1 plan codes | undefined symbol defined by a config value / alias register | `rate_card.json` `codes` lists | PICK: UNIQUENESS ONE, 0b passes |
| S2 re-installed meter rows | merge winner | duplicate `accounts.csv` rows | FAIL 0b: nothing in the input separates last-wins, first-wins and union (silence), and it contradicts the "one row per meter" text at :65-67 |
| S3 plan revisions with from-dates | flag versus date | dated plan entries | FAIL UNIQUENESS: start binding and end binding agree on every witness |
| S4 tier block sizes | undefined symbol | tier `block` key | FAIL W5: the witness and the data it governs sit in the same file, and it contradicts the energy-line wording at :107-113 |

- **Rule (no sentence anywhere).** An account's plan is the rate-card entry whose key equals the trimmed `plan` value. When no key matches, it is the one entry whose `codes` list (each code trimmed) holds that value. The invoice `plan` field is the row's trimmed value. That last point is a format statement at `api_contract.md:101-103`.
- **Witness.** `environment/ci/rate_card.json` lines 7-10, 29-31, 50-53, 72-74, 93 and 108-110 hold the `codes` lists. They govern `billing_periods.csv`: 503 of 2000 rows name their plan by a code, for example :2 `T3415` and :159 `T2319`, which is padded as `" T2319"` in the card. The witness is not labelled as a check, an example or an expected value, and no file or key name says what it proves.
- **Reflex reading.** `card["plans"][period["plan"]]` (probe-2 `report.py`) raises KeyError on the shipped data. The quiet variants are a default plan, a normalised key and untrimmed codes.
- **Hidden cases.** Every corpus card gets fresh codes. Each corpus has one padded card code, one plan with two codes, one plan with no codes, and two plans that share a 3-character code stem. The `recoded` family (seed H7, 30 accounts, at least 40% named by code, every code used, at least one padded billing value) is graded together with its mutated rerun `renamed`. `renamed` uses fresh codes with a new letter, a rotated plan order and rotated rows. `_assert_codes` enforces all of this, and 300 seeds give 0 failures.
- **UNIQUENESS (`WORK/UNIQUENESS.md`).** 18 readings were fitted against the shipped witness, `recoded`, `renamed` and 80 extra seeded witness sets.
  - Only R1 and its relaxations fit everywhere. The relaxations are R1b codes-first, R14 nearest digits, R16 casefold and R17 digits-only. They pick the same entry in 83 of 83 sets and produce byte-identical documents.
  - Every other reading is contradicted by the shipped witness and by both graded L11 corpora, and fits 0 of the 80 extra sets. These include key-only, casefold or alnum keys, first or last or most common plan, untrimmed codes, first-code or last-code only, and 3-character prefix.
  - Verdict: ONE.
- **Interaction with N1-N3.** N1, N2 and N3 are kept word for word. The recoded and renamed corpora stay neutral for them: allowance needs one pass, periods are whole months, and accounts stay within tier 1. Shipped invoices carry L11 alongside the shipped controls.

## Levers before and after

| lever | before (probe 2, d62ffe6) | after (7f1d771) | rule written at | alone loss (of 157) |
|---|---|---|---|---|
| N1 allowance re-share | counted, 60/127 | unchanged text, counted | api_contract.md:46-48, :124-130 | one or two passes 60 (38.2%); no share 68 (43.3%) |
| N2 calendar month | counted, 45/127 | unchanged text, counted | :43, :51, :115-119 | start month 45 (28.7%); period length 58 (36.9%) |
| N3 account tier position | counted, 45/127 | unchanged text, counted | :38-40, :107-113 | per meter 45 (28.7%) |
| L11 plan codes | none | new, counted | no sentence; witness rate_card.json:7-10 etc. | default plan 40 (25.5%); key-only or untrimmed crash loudly |
| LV-TR-4, LV-TR-2, LV-TR-1, COUPLING | gates | gates, unchanged | :63, :85-86; :49-50, :128-130; :3-5 | coerce 116 |

- Instruction line 1 (IN-17): the "pass only because they assert the drifted behaviour" clause is cut. In its place is the plain sentence "The package's unit tests are in `/app/repo/tests/test_visible.py`."
- Instruction line 13 (G5): the line now reads "Each invoice and each exception list is graded whole on fresh inputs, and only an exact match counts."
- W9 check:
  - I read every rule sentence literally and alone, and each still yields one computation.
  - I read the witness alone. It shows a list of strings on a plan entry that billing values match exactly, after trimming.
  - The correction duty is still stated at instruction :3.

## Counts and weight shares

- Tests: 39 checks. 37 are positive, worth 157 points. 2 negatives are worth -8: hardcode -5 and visible test removed -3.
- Judge: 14 criteria, 33 positive points and 13 negative, batched. R14 (w3) is the L11 recompute conduct criterion; solve.py prints `check R14 ok`.
- Shares, by code:

| share | points | percent of 157 |
|---|---|---|
| L11 owned (recoded + renamed + 2 shipped checks) | 40 | 25.5% |
| hidden or mutated reruns | 126 | 80.3% |
| mutated reruns only | 50 | 31.8% |
| shipped only | 14 | 8.9% |
| deliverable checks | 17 | 10.8% |
| whole-corpus exact figure checks | 136 | 86.6% |

  - Each whole-corpus exact check covers one component (lines, heads or settlement) of every invoice in a corpus. No single check compares the full document byte for byte.
  - Kit WARN A3 (39 checks against a cap of 35) is recorded, not capped.

## Cost table (G10, measured, `WORK/COST_TABLE.md`)

| lever | slip | tests | lost | overall (rubric 90 / measured 3.33) |
|---|---|---|---|---|
| L11 | default first or last plan | 0.7452 | 40 | 82.3 / 38.9 |
| N1 | one or two passes | 0.6178 | 60 | 75.9 / 32.6 |
| N2 | start month | 0.7134 | 45 | 80.7 / 37.3 |
| N3 | per-meter tiers | 0.7134 | 45 | 80.7 / 37.3 |
| one fact wrong (CL-4) | recoded P0389 +0.01 | 0.8089 | 30 | 85.4 / 42.1 |
| one fact wrong | shipped A0001 / api N0054 | 0.9682 / 0.9045 | 5 / 15 | - |

- Every lever alone costs at least 25%.
- The all-but-one-right overall stays below 70 only at the measured probe-2 rubric (3.33). At a rubric of 90 it fails (73-82). This is reported as measured, not gamed.
- Rule coverage: 61 mutants, 61 killed, and no negative fires. The L11 mutants are M58, M59 and M60 (8 tests each) and M62 (2 tests). AL-27 does not apply: this is a lookup, not an ordering.

## Gates

| gate | result |
|---|---|
| STACKING_CHECK | `STACKING PASS` (tool hints for G3, AL-28 and TS-26 corrected by reading the code) |
| PRECHECK last line | `PRECHECK CLEAN` (0 IN17/G5 warns) |
| structure / instruction / tests / judge QC | 17/0/0, 5/0/0, 35 pass with 1 warn (A3) and 0 fail, 19/0/0 |
| validator `--archetype repo-patch` | 40 passed, 0 failed, GATE PASS |
| xref_check | 53 entries, 0 findings |
| Docker oracle x3 | 1.0, 1.0, 1.0 |
| owner-only | 1.0 |
| nop / stub | 0.0 / 0.0 |
| forgery (shipped replay) | 0.1656: 26/157 from deliverable, shipped and determinism checks, with the hardcode negative fired (-5) |

Kit diff `976c1666..5574d77e`:

| check | result | why |
|---|---|---|
| IN-14 | PASS | |
| IN-15 | PASS | rules of engagement are stated in the instruction or the contract |
| IN-17 | FIXED | line 1 clause cut, line 13 exactness only, codes never announced |
| DS-19 | PASS | |
| TS-19 | PASS | L11 is determinate per EVIDENCE_MAP, and the generator asserts it |
| JD-15 | PASS | |
| AL-1 | PASS | determinate fact, per EVIDENCE_MAP and UNIQUENESS |
| AL-2 | PASS | |
| AL-3 | PASS | |
| AL-4 | PASS | |
| AL-27 | PASS | 61 rows |
| CL-5 | PASS | FC:492; the plan format is stated at :101-103 |
| Final_checklist / Starter | PASS | |

Docker logs and result files are in `docker/`. Raw run: `/tmp/opencode-logs/tariff-engine-audit-repair-7f1d771-20261025T152406-748b`.

## Tasks_INPUT sync

These 9 changed files were copied with `cp -p` over `Tasks_INPUT/tariff-engine-audit-repair/`:
- api_contract.md, billing_periods.csv, rate_card.json
- instruction.md
- TRUTH.md, solve.py
- judge.toml, reward.toml, test_output.py

`diff -rq BUNDLE Tasks_INPUT/tariff-engine-audit-repair` printed nothing (exit 0; `tasks_input_diff.txt` is empty).

## Not run

- No reflex gate and no fuzz of the probe-2 program as evidence (LEVER_RULES section 6; the master issues 3 blind reads).
- Oracle x5: Ayush asked for x3.
- No judge-channel run: Docker ran tests only.
- Not re-measured on 157 points: V_month_30, V_half_up, V_float_round, V_credit_rounded, V_keep_asserts.
- Forgery is still above the 0.05 target and was not fixed this round (deliverable checks pay without a program).

## Lessons for the master
- A closed contract leaves L11 almost only the lookup or alias shape; the habit crashes loudly, so its bite comes from silent defaults (25.5%) | no change: one pilot is too little evidence
- Prefix and stem readings fit unless the generator plants two codes that share a stem; UNIQUENESS caught it before any test was written | template_change: LEVER_RULES_v2.md:33 add "plant a near-miss pair for every looser matching reading"
- Replay forgery still earns 16.6% from deliverable and shipped checks | no change: closing it means tying reports to hidden results
