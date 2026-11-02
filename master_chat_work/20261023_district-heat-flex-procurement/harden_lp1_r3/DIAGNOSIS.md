# DIAGNOSIS - harden lp1 r3, board 8cd7597

23 Oct 2026 IST. Phase 1 decision: **NO NATURAL TRAP; PILOT_WEAK**. No bundle edit.

## 1. Genuine blind-run check

The 27 files in BUNDLE, hashed as sorted relative path + NUL + file content, give `c3c5b97731b522dacb70b35e92842a189a9ad6e97e214858f106ea0afd5ac7a9` (first 12 `c3c5b97731b5`). This equals the blind run's recorded tree. There is no changed file to explain away the blind result. `blind_r1/SCORE.md` and `score_reward_details.json` record 30/30 positive checks and 98/98 points, tests-only 1.000; no negative fired. The blind program was fully written in about three minutes (`blind_r1/work/BLIND_REPORT.md:12-17`) and made no crash fix (`:25`). A byte-for-byte copy is in `agent_program_blind/derive_report.py` (SHA256 `b290a79137409af3efad2464536a5259740a8a9f904fc24e4864146f6cf5bb05`). The a5 reflex program remains at `harden_lp1_r2/agent_program/`.

The report's read order is `BLIND_REPORT.md:5-10`: instruction; program.ini and export_manifest.tsv; all of schema.md; then every data-file head and comment, including site_allowances.tsv and rate_cards.xml. It profiled manifest totals before writing. Thus every evidence file below was read before the program's first write. It did not read tests. Its own shipped-data checks (`:19-25`) checked integrity and conservation, not an alternative rule reading.

## 2. Per-lever leak table

Paths `schema.md`, `site_allowances.tsv`, `rate_cards.xml`, `program.ini`, and `export_manifest.tsv` below are under BUNDLE `environment/data/`. Program line numbers refer to `blind_r1/app/derive_report.py`. Class definitions are the prompt's (a) clear rule, (b) shipped separating example, (c) agent self-check, (d) hint or phrase, (e) other. Each row assigns one primary class.

| Graded lever | Blind program, correct reading | Class | Exact giveaway read before writing |
|---|---|---|---|
| L1 receipt control | `:283-285` reads the manifest only for its row count; no settlement uses `field_sum` | e | `export_manifest.tsv:2-5` says sums are of fields **as written** and agreement only means the file **arrived whole**; `schema.md:99-102` says **No report figure is taken from it**. The green receipt supplies no reason to change the computation. `BLIND_REPORT.md:24` confirms it was used only for row counts and written sums. |
| L3 season allowance | `:341-373` sorts by parsed instant, descending event ID on ties, excludes offers exceeding remaining ticks, and draws chosen relief | a | `site_allowances.tsv:2-7` spells out start-instant order, prior-event draw, and candidate exclusion; `schema.md:36-38` defines `dispatch_start` as an instant with UTC offset; `schema.md:132-136` gives descending order on equal service. |
| L4 rate composition | `:81-82`, `:164-166`, `:314-325` reads adders and override, adds uplift and adder, caps final rate | a | `rate_cards.xml:4-7` says override replaces base and cap applies to effective rate; `schema.md:36-38` says uplift is added to every site row; `program.ini:21-25` says the segment value is added; `schema.md:138-141` says the cap binds after every adjustment. Removing the old section-6 checklist did not make any piece hard to read. |
| L7 interval half-even | `:23-27`, `:322-325` rounds each interval half to even, then sums | a | `rate_cards.xml:8-11` directly names `credit_cents`, the **interval amount**, and **rounded half to even**; `schema.md:118-120` defines half to even. The shipped-data half-case removal did not matter because the rule is explicit. |
| L2 legacy multiplier, still graded through documents | `:217-218` multiplies each register reading before converting to ticks | a | `schema.md:53-57` directly states each Wh value is the reading times `register_multiplier`; `:124-128` says each derived Wh becomes ticks. |
| H1 compliance precedence | `:293-308` checks valid signed waiver and the ranked label ladder | a | `schema.md:145-150` gives the full ranking and all four waiver conditions. |
| H2 greatest final tuple | `:634-647` compares five components then takes the greater sorted-ID tuple | a | `schema.md:181-196` numbers every component; `:132-136` names the greatest identifier and sorted tuple rule. |
| H3 final rate cap | `:319-320` caps after uplift and adder | a | `schema.md:138-141` says cap binds **after every adjustment**. |
| H4 residual cents | `:437-445` uses positive weights and decreasing remainder, then ID | a | `schema.md:221-227` gives the largest-remainder steps and positive-weight scope; `:132-136` gives descending identifier order for equal candidates. |
| H5 quantise per record | `:92-93`, `:217-218`, `:239-254` rounds each record's Wh before sums | a | `schema.md:124-128` says **every Wh value of a record** becomes ticks **at the moment it is derived**, and sums are of ticks. |
| DH-2 ticks in optimisation | `:229-232`, `:619-634`, `:670-681` optimises tick vectors | a | `schema.md:176-179` defines portfolio relief and recovery as sums of offer **ticks** and compares ceilings in ticks. |
| DH-3 funded pool | `:418-421` calculates `max(0, pool - credit)` | a | `schema.md:209-213` states the calculation order and the exact difference. |
| DH-4 malformed profile rows | `:202-218` checks orphan, range, then earlier kept duplicate | a | `schema.md:57-65` numbers those three precedence cases and says the other rows are kept. |
| DH-5 label-based grant weight | `:425-430` doubles only for the final `CONTINUITY_WAIVED` label | a | `schema.md:215-219` explicitly names that final label as the condition for counting `grant_weight` twice. |
| DH-6 legacy `[export]` default | `:293-297` requires literal `Y` and never applies the INI default | d | `program.ini:27-29` offers the decoy, but `schema.md:28-29` explicitly says `[export]` **carries no rule for this programme**. The solver called this a **deliberate trap** in `BLIND_REPORT.md:31`. |
| DH-7 objective order and offer count | `:619-647` constructs the five-component key including `len(chosen)` | a | `schema.md:181-196` explicitly lists and orders all five components, including offer count. |

No shipped example where two readings differ was needed to find a correct reading (class b). The blind solver's checks, described at `BLIND_REPORT.md:19-25`, only confirmed parse totals and conservation; they did not expose a wrong reading (class c). The legacy default is the one class-d case, and the report explicitly noticed it.

## 3. Pattern and stop decision

Round 1's a5 diagnosis (`harden_lp1_r2/DIAGNOSIS.md:17-34`) found the multiplier, rate composition, rounding, and all older computational rules leaked mainly through class (a): plain sentences that gave the careful reading on the first write. Round 2 moved some text, removed a checklist and shipped half cases, and introduced an allowance ledger. The new blind solver still coded every rule directly from those sentences on its first write and passed 98/98. The L1 receipt remained class (e): a truthful parse control with no pull toward the wrong arithmetic. DH-6 remained an explicit class-d warning.

**NO NATURAL TRAP.** For this task's numeric contract, a careful first-contact reader who reads the named data-file comments has a single, direct implementation for each rule. The proposed wrong readings (event ID instead of start instant, static allowance, override as entire rate, cap before adders, per-offer or half-up rounding) contradict explicit words in the governing files. Hiding those words, leaving the override scope implicit, or making two plausible authorities disagree would violate IN-15/IN-16. Moving them farther away or relying on an old program's staleness has already failed to predict a fresh solver. L5/L6 are unused candidates, but there is no evidence here that a new strict-field or inherited-scope sentence would make this blind solver choose a wrong reading; adding them as points without a natural mechanism would repeat the same failure.

Per the Phase 1 stop rule, status is `PILOT_WEAK`. Phase 2 edits, stacking replays against new tests, QC and Docker gates were not run. The r2 bundle remains intact for review or a different task design.
