# LEVERS - district-heat-flex-procurement

Round 0 table: `LEVERS_r0.md`. Round 1 table (41 checks, positive 139): `LEVERS_r1.md`.

## Round 2 (22 Oct 2026): 32 checks, positive total 100, negative total -16

Why: both real claude-opus-5 runs timed out at 7200 s while load-testing their own 20 and 22 site
stress cases against the stated 30 s limit (DIAGNOSIS.md). Round 2 removes the size lever LV-DH-1
(exact search at 22 sites in 30 s): an event-region now has at most 8 sites with at most 3 offers
(65,536 portfolios), the stated limit is 120 s, and the oracle's slowest graded case takes well under
a second. Difficulty comes from composition: four composed extracts are graded as whole documents.

Check layout (weight):
- Format, shipped /app/out (4): artifact set, canonical form, schema keys, array order (1 each).
  P12 r1 (22 Oct 2026): the canonical-form check also needs a JSON integer at every integer field of
  the shipped reports, so empty `{}` documents no longer earn it (TS-25).
- Composed extracts A grants, B search, C rejects, D mixed (72): per extract, four region files (5),
  both segment files (5), summary.json with policy_audit.json (5), data_quality.json (3).
- One rule family each (24): waiver_labels_case, tie_break_greatest_tuple_case, cap_after_uplift_case,
  residual_ties_descending_id_case, tick_feasibility_case, objective_component_order_case,
  rejected_profile_rows_case, unknown_region_site_rows_case (3 each).
- Negatives (-16): hardcoded sample (-5), reads grader (-5), external dependency (-3), hollow summary (-3).

Isolated weight share: 24 / 100 = 0.24. Shipped-data reads: 4 / 100 = 0.04. DH-3 (funded pool) is read
only through composed documents.

## Weight lost by one wrong reading (arithmetic, not a solver run)

Each row plays the verifier's own reference with exactly one wrong reading through the real check
functions (`lever_table.py`, raw output `harden_r2/lever_table.json`). "Isolated" is weight lost on the
eight single-rule checks, "composed" on the sixteen composed-extract checks. Shipped visibility is whether
the wrong reading changes any of the nine reports of the shipped data.

| Flag | Wrong reading | Lost (of 100) | Isolated | Composed | Shipped data |
|---|---|---|---|---|---|
| `C5drop` | LV-DH-7 offer count ignored | 63 | 3 | 60 | HIDDEN-ONLY |
| `H3` | LV-H03 cap applied to the base, uplift added after | 63 | 3 | 60 | HIDDEN-ONLY |
| `H5t` | LV-H05 energy sums rounded after adding raw Wh | 60 | 0 | 60 | HIDDEN-ONLY |
| `DH2` | LV-DH-2 raw Wh added inside the search | 48 | 3 | 45 | HIDDEN-ONLY |
| `H2` | LV-H02 smallest tuple wins a tie | 48 | 3 | 45 | HIDDEN-ONLY |
| `H5c` | LV-H05 credits summed before per-site rounding | 45 | 0 | 45 | HIDDEN-ONLY |
| `H1` | LV-H01 valid waiver never recognised | 43 | 3 | 40 | DERIVABLE |
| `H1order` | LV-H01 waived label ranked above a hold or cooldown | 43 | 3 | 40 | DERIVABLE |
| `H1pend` | LV-H01 pending certificate labelled CLEAR | 43 | 3 | 40 | DERIVABLE |
| `SIGNEDY` | LV-DH-6 blank waiver_signed read as Y (decoy `[export]` default) | 43 | 3 | 40 | DERIVABLE |
| `DH4range` | LV-DH-4 out-of-range interval wraps or is kept | 42 | 3 | 39 | HIDDEN-ONLY |
| `DH3` | LV-DH-3 raw pool shared (funded pool ignored) | 40 | 0 | 40 | DERIVABLE |
| `DH4unknown` | LV-DH-4 unknown-region site row kept | 35 | 3 | 32 | HIDDEN-ONLY |
| `C34` | LV-DH-7 overdelivery compared before cost | 33 | 3 | 30 | DERIVABLE |
| `C45` | LV-DH-7 offer count compared before overdelivery | 33 | 3 | 30 | DERIVABLE |
| `H1hc` | LV-H01 cooldown ranked above a hold | 33 | 3 | 30 | DERIVABLE |
| `DH4dup` | LV-DH-4 last duplicate profile row wins | 30 | 3 | 27 | HIDDEN-ONLY |
| `DH5raw` | LV-DH-5 weight doubled from the raw waiver fields | 30 | 0 | 30 | DERIVABLE |
| `H4` | LV-H04 leftover cents by ascending id | 23 | 3 | 20 | DERIVABLE |
| `W0LIST` | LV-H04 zero-weight beneficiaries listed | 23 | 3 | 20 | DERIVABLE |

Removed in round 2: LV-DH-1 (exact search at 20 and 22 sites within 30 s) and its six checks (26 of 139),
the five standalone tick checks except tick_feasibility_case, the five funded_pool_* checks, the two waived
weight checks, the one-case-per-count rejected-row checks (merged), `per_value_tick_quantisation_case`
(now read through the composed segment documents), and `ordinary_extract_*` (replaced by the composed
extracts). New: SIGNEDY (decoy), H1hc, H1pend, W0LIST, C34, C45, C5drop.

## P12 r1 judge change (22 Oct 2026)

R7 is now the negative `r7_bare_or_swallowing_except` (-1, important): the final derive_report.py has a
bare except clause or one that discards the caught error. R8 (+1) stays the positive code-quality
criterion. Judge positive total 19, negative total -11; reward.toml judge weight 0.5 / 19.

## Harden lp1 r1 (23 Oct 2026, LEVER_PLAN_v1, board 0154d63): 38 checks, positive 113, negative -13

Levers for this task are L1, L2, L4 and L7. The old rules (H1-H5, DH-2 to DH-7) stay graded inside the composed documents.
Weight lost by one wrong reading below comes from `lever_table.py` (the verifier's reference plays the wrong reading through the
real check functions); the raw output is `harden_lp1_r1/lever_table_lp1.json`. Paths are relative to `environment/data/`.

### L1 Green control, wrong answer (export receipt)
- Rule text: `export_manifest.tsv:1-5` (header comment: per-file records and the sum of a field "as they are written in the file").
  Also `schema.md:95-98`: it is a receipt, "No report figure is taken from it". Plus `schema.md:320`: its data rows are counted in `data_quality.json` rows.
- Reflex reading: "every receipt line agrees with my parse, so my reading of the files is right". The receipt sums `relief_wh`,
  `recovery_wh` and `base` as written, so it agrees with a program that drops the register multiplier and ignores overrides
  (flags MULT0 + OVR0).
- Hidden cases: every composed extract and every hand-built case writes a truthful receipt (`_write_receipt`). The receipt agrees with the
  files while multipliers and overrides change the graded values.
- Checks the wrong reading fails: L1 reading (MULT0+OVR0) loses 76 of 113, failing 20 checks. These are all 20 composed
  documents except some data_quality files, plus `register_multiplier_case`, `rate_composition_case` and both mutations.

### L2 Make-it-match repair (register multiplier)
- Rule text: `schema.md:53-57` (profiles.tsv description: the row's Wh is the reading times `register_multiplier`). `schema.md:120-122`
  (2.3: every Wh value becomes ticks when it is derived). This is far from the receipt (`export_manifest.tsv:3-4`).
- Reflex reading: the honest reading fails the receipt on the 5,410 shipped rows with multiplier 2 or 5. Dropping the multiplier
  ("relief_wh is Wh, the receipt proves it") turns the receipt green by construction (MULT0). A second wrong reading multiplies the
  reading's ticks instead of its Wh (MULTtick).
- Hidden cases: case `multiplier` (readings 5 and 3000 with multipliers 3 and 2 against a 30 Wh ceiling). Composed extracts
  carry multipliers 2, 3 or 5 on 8-12% of rows (`mix["mult"]`), and the mutation pairs carry them too. Shipped products are all
  multiples of 10, so MULTtick never shows on shipped data.
- Checks the wrong reading fails: MULT0 loses 73 (19 checks), MULTtick loses 64 (16 checks). Both fail `register_multiplier_case`,
  `wh_per_tick_mutation` and `segment_rate_adder_mutation`.

### L4 Multi-document composition (rate before cap)
- Rule text, one piece per file:
  - `rate_cards.xml:4-5`: the start rate is the override when present, else the base;
  - `schema.md:36-37`: the events.json uplift is added to every site row of the event;
  - `program.ini:21-22` with `schema.md:23-25`: the segment adder is added to every site row of the segment;
  - `schema.md:134-135` (2.5): the cap binds the final rate;
  - `schema.md:193-201` (section 6) only points at the three files and defines cap binding.
- Reflex reading: the override is the whole rate (OVRrate), the adder is skipped (ADD0), the override is ignored (OVR0, which the
  receipt's base sum invites), the adder is added after the cap (CAPpre), or the base is capped first (H3).
- Hidden cases: case `rate` (public card: override 3000, cap 4000, uplift 500, adder 750, so 4000 and binding; commercial card:
  override 5000, base 2000, cap 9000, so 5500). Composed extracts put overrides on 10-25% of cards, with public adders of 500, 750
  or 1250 and commercial adders of 0 or 250. The mutation pair `mut_adder` changes the public adder from 500 to 1500. Shipped data
  holds 226 overrides, all on commercial cards (adder 0), so no shipped row combines an override with a non-zero adder.
- Checks the wrong reading fails: OVR0 70 (18), ADD0 70 (18), H3 67 (17), CAPpre 64 (16), OVRrate 57 (15).

### L7 Rounding unit per item (interval credit, half to even)
- Rule text: `rate_cards.xml:6-9`: each interval amount is rounded half to even to whole cents, and the credit is their sum. The global
  default stays half up (`schema.md` 2.2). The old per-site money sentence of 2.3 was removed.
- Reflex reading: round once per offer half up (the round-2 rule, R7offer), per offer half to even (R7offer_even), per interval
  half up (R7up), or once per event-region (H5c).
- Hidden cases: case `rounding` (interval amounts 0.5+0.5 cents, giving 0, and 1.5+0.5, giving 2; the readings give 1, 2 or 3).
  Composed extracts with uplifts 250-2000 and adders produce exact halves. No shipped file shows a credit figure.
- Checks the wrong reading fails: R7offer 67 (17), R7offer_even 67 (17), H5c 67 (17), R7up 48 (12).

### Weights
| Group | Checks | Weight | Share |
|---|---|---|---|
| Format on shipped /app/out | 4 x 1 | 4 | 3.5% |
| Whole documents on 4 composed hidden extracts (regions 5, segments 5, summary 3, audit 3, quality 3) | 20 | 76 | 67.3% |
| Isolated rule cases | 9 x 3 | 27 | 23.9% |
| Mutations of governed constants | 2 x 3 | 6 | 5.3% |
| Isolated total (cases + mutations) | 11 | 33 | 29.2% |
| Negatives (hardcoded -5, grader path -5, external import -3) | 3 | -13 | |

Removed: `cap_after_uplift_case` (replaced by `rate_composition_case`), `unknown_region_site_rows_case` (still graded in the composed
C/D documents), `negative_missing_substantive_sections` (it graded a hollow summary, not cheating). The 4 composed checks
`*_summary_and_audit_match` were split into summary and policy_audit checks (one document per check, G1).
The real a4 agent program scores 20/113 = 0.177 (STACKING_CHECK.md).

## P12 r2 (23 Oct 2026, QC v4 53c71e3, board a3aeb84)

- New wrong reading `DH4seen` (LV-DH-4, L7 family of malformed rows): a repeated out-of-range profile row is counted as a
  duplicate, not out of range. Rule text: `schema.md:62-63` (a duplicate needs an earlier row that was kept). Case `rejected` now
  has interval 3 twice for `T9-0002-S1-A` (interval_count 2); expected duplicate 1, out of range 3. Graded by
  `rejected_profile_rows_case` (3). Not in GUARDS or SEARCH_FLAGS (it changes counts only). Effect on L7: harder.
- Judge: R1 now checks the grant shares of an uneven pool on the agent's own extract (no longer any figure, no manifest
  condition); R5 is "instruction following" (exact arithmetic, schema.md:114-115); R6 names rate_cards.xml and program.ini only;
  new R9 (+1) named functions for reading, search, settlement and writing. Judge positive 16, negative -5; reward judge 0.5/16.
  Tests unchanged in count: 38 checks, positive 113, negative -13.

## Harden lp1 r2 (23 Oct 2026, LEVER_PLAN_v1, board eb6f232)

Trajectory a5 (fresh claude-opus-5, tests 100) coded every r1 lever on its first write (step 12/14). Leak classes
(OUT/DIAGNOSIS.md): L1 receipt (e, punished a reading nobody takes), L2 multiplier (a), L4 composition (a + d, the section 6
checklist), L7 interval credit (a, then c: the agent's own count of shipped exact halves). r2 levers: L1, L3 (new, replaces L2),
L4, L7. The multiplier rule stays as a plain data rule (MULT0 still fails 21 checks) but is no longer a lever.
Single-reading losses below are of 98 positive points, from `OUT/lever_table_lp2.json` (lever_table.py on the oracle workspace).

### L1 Green control (export receipt)
- Rule text: `export_manifest.tsv:1-5` (receipt written after the other files; records counted as data_quality counts rows; field_sum
  is the sum as written; "A file whose lines here agree with it arrived whole."). `schema.md` export_manifest bullet: no report
  figure is taken from it. The receipt now also covers `site_allowances.tsv` (records 1280, allowance_ticks sum).
- Reflex reading: the receipt agrees with `allowance_ticks` as written, so the allowance is read as a static per-event budget
  (LEDstatic): the control is green and nothing is drawn down.
- Hidden cases: case `allowance_consumption` (site AL-3 allowance 150, 100 ticks chosen in the earlier event, the later offer of
  100 ticks no longer fits); composed extracts with tight allowances (20-80% of the site's season need).
- Checks the wrong reading fails: LEDstatic loses 85 (23 checks: allowance_consumption_case, allowance_order_case,
  allowance_ticks_mutation and every composed document).

### L3 Stateful stream (season allowance ledger), new
- Rule text: `site_allowances.tsv:1-7` (allowance drawn by the events one at a time in the order of the instants they start,
  `dispatch_start`; equal instants follow the programme conventions; remaining = allowance_ticks less the relief ticks over all
  intervals of the site's offers chosen in events reached before; an offer whose relief ticks are more than what remains is not a
  candidate). `schema.md:36-38` (dispatch_start is an instant with its UTC offset), `schema.md:95-98` (file bullet),
  `schema.md:130-136` (2.4: equal candidates served in descending identifier order), `schema.md:152-158` (section 3 candidates),
  `schema.md:334-335` (allowance_blocked_offer_count).
- Reflex reading: walk events in event_id order, the order every output uses (LEDid); sort by the dispatch_start text (LEDstr);
  break equal instants by ascending id (LEDtie); ignore the allowance (LEDnone, the a5 program).
- Shipped data never separates the order readings: start order differs from id order (262 adjacent inversions), but every
  allowance is either below every offer of its site (54 sites) or above the sum of all its offers (1226 sites), and string order
  equals instant order. LEDstatic, LEDid, LEDstr, LEDtie and R7up give the shipped oracle reports byte for byte.
- Hidden cases: case `allowance_order` (T5-0002 starts 09:30+01:00, before T5-0001 at 09:00+00:00; T5-0003 12:00+01:00 and
  T5-0004 11:00+00:00 are the same instant, served descending id); composed extracts reuse ten site ids per region across events,
  with mixed offsets (+00:00, +01:00, +02:00, -05:00) and tight allowances; mutation pair `mut_allowance` (one allowance 130 to 190).
- Checks the wrong reading fails: LEDnone 85 (23), LEDid 82 (22), LEDstr 82 (22), LEDtie 47 (13).

### L4 Multi-document composition (rate before cap)
- Rule text, one piece per file: `rate_cards.xml:4-5` start rate (override else base); `schema.md:37-38` uplift added to every site
  row of the event; `program.ini:21-22` with `[segment_rate_adders]` (23-25) adder added to every site row of the segment;
  `rate_cards.xml:6-7` effective rate is the rate with the card's cap applied as the conventions say; `schema.md:138-141` (2.5)
  the cap binds the final rate after every adjustment. The section 6 checklist that named the three files was removed (class d);
  section 6 now only says the credit is defined in the rate_cards.xml comment and defines cap binding.
- Reflex reading: OVR0, OVRrate, UPL0 (uplift missed, new), ADD0, CAPpre, H3.
- Hidden cases: case `rate`; composed overrides on 10-25% of cards with public adders 500-1250; mutation `mut_adder`.
- Checks the wrong reading fails: OVR0 70 (18), OVRrate 67 (17), UPL0 67 (17), H3 67 (17), ADD0 57 (15), CAPpre 48 (12).

### L7 Rounding unit per item (interval credit, half to even)
- Rule text: `rate_cards.xml:8-11` (each interval amount rounded half to even, credit is the sum); `schema.md:118-120` (2.2 defines
  "rounded half to even"; the global default stays half up). The gloss "(an exact half goes to the even neighbour)" was removed from
  the comment.
- Class (c) fix: shipped relief_wh was raised by 10 Wh steps (3720 steps, lp2_data.py) until no shipped interval amount is an exact
  half, so an agent counting exact halves on shipped data finds none and per-interval half up (R7up) equals the oracle on shipped.
- Hidden cases: case `rounding`; composed extracts produce exact halves.
- Checks the wrong reading fails: R7offer 70 (18), R7offer_even 70 (18), H5c 70 (18), R7up 29 (7).

### Weights (r2)
| Group | Checks | Weight | Share |
|---|---|---|---|
| Format on shipped /app/out | 4 x 1 | 4 | 4.1% |
| Whole documents on 4 composed hidden extracts | 20 | 76 | 77.6% |
| Isolated rule cases (rate, rounding, allowance order, allowance consumption) | 4 x 3 | 12 | 12.2% |
| Mutations (segment_rate_adder_mutation, allowance_ticks_mutation) | 2 x 3 | 6 | 6.1% |
| Isolated total | 6 | 18 | 18.4% |
| Negatives (hardcoded -5, grader path -5, external import -3) | 3 | -13 | |

Dropped as checks (their cases stay planted in the composed extracts): waiver_labels_case, tie_break_greatest_tuple_case,
residual_ties_descending_id_case, tick_feasibility_case, objective_component_order_case, rejected_profile_rows_case,
register_multiplier_case, wh_per_tick_mutation (replaced by allowance_ticks_mutation).
Local programs: oracle 98/98; a5 program 11/98 = 0.112; a5 plus ledger in event_id order 16/98 = 0.163; r1 program 2/98 = 0.020.

## Redesign r4 (25 Oct 2026, board 7743264): 50 checks, positive 173, negative -13

r3 found no natural trap: every r2 lever was a stated recipe keyed by the field it reads (class a). r4 adds three levers of
shapes not tried on this task plus one coupling. Numbers are from the real embedded tests (`OUT/redesign_r4/variant_grades.log`)
and the 320+320 corpus fuzz on the final generator (`OUT/redesign_r4/proto/fuzz_final_6000_320.log`).

### M1 grants minimum drop and second share (H7 re-entry)
- Rule text: `schema.md` section 7 (lines ~226-251): claims (`weight x claim_cents_per_weight`) paid when they add up to F or less;
  otherwise largest remainder; a share below `minimum_grant_cents` receives nothing; "every cent of F is shared again, in proportion
  to weight by largest remainder, across only the beneficiaries whose share was `minimum_grant_cents` or more, with W now the sum
  of their weights". Keys: `program.ini` `[grants]` (40, 25), declared in schema section 1.
- Reflex reading: one apportion helper holding the claims-fit branch, called again for the survivors (REENTRY); keep first shares
  (DROPLEFT); no drop (NODROP). Saved programs: no grants keys at all.
- Hidden cases: `_plant_grants` sets, per region of each hidden extract, the first season event-region that admits it to a funded
  pool where some but not all beneficiaries drop and the survivors' claims fit (earlier pools of that region 0). Shipped data never
  drops (claims fit once carry builds up), so W5 holds. Mutation `minimum_grant_mutation` (minimum 20 -> 26).
- Checks failed: REENTRY 128/173 (lost 26.0%, 9 tests: funded_pool, grant_allocation, grants, residual, region totals x4,
  summary `_hard`); DROPLEFT 125; NODROP 150. Fuzz: REENTRY differs on 640/640 corpora.

### CARRY (coupling; counts 0)
- Rule text: `schema.md` section 7 funded-pool sentence (carried cents = unallocated cents of the same region's previous event in
  season order). NOCARRY 107/173 (16 tests, visible and hidden). Lifts M1 from 23.7% (proto, no carry) to 26.0%.

### M2 allowance holder by draws_from chain (H6, recursive key)
- Rule text: `site_allowances.tsv` comment lines 2-5 (recursive "draws on the allowance that the named site draws on", no depth
  sentence) and lines 6-11 (drawn per allowance); schema section 1 header names the column.
- Reflex reading: own `site_id` key (CHAIN0, both saved programs) or one hop (CHAIN1).
- Shipped: 60 one-link chains only (CHAIN1 equals the reference there). Hidden H1: 1-2 chains of 2-5 sites per region, holder
  allowance 35-100% of the chain's need. Mutation `allowance_ticks_mutation`.
- Checks failed: CHAIN1 118/173 (lost 31.8%, 11 tests); CHAIN0 73. Fuzz: CHAIN1 differs on 320/320 H1 corpora.

### M3 credited relief ticks (H3 defined term)
- Rule text: `rate_cards.xml` comment ("credited relief ticks"); definition `schema.md` section 6 (relief less recovery of the same
  interval, or 0).
- Reflex reading: relief ticks (RELIEF), the column and output field of the same name.
- Shipped: 0 of 108,036 profile rows hold relief and recovery in one interval. Hidden H1/H2 overlap often.
- Checks failed: RELIEF 115/173 (lost 33.5%, 12 tests incl. `segment_rate_adder_mutation`). Fuzz 640/640.

### Pairs and saved programs
REENTRY+CHAIN1 98, REENTRY+RELIEF 110, CHAIN1+RELIEF 85, all three 85. Saved blind program 31/173 = 0.179, harness program
28/173 = 0.162 (reflex gate <= 0.20).

### Weights (r4)
| Group | Checks | Weight | Share |
|---|---|---|---|
| Format on shipped /app/out | 4 x 1 | 4 | 2.3% |
| Families on shipped data (visible) | 20 x 3 | 60 | 34.7% |
| Families on hidden season/settlement extracts (`_hard`) | 20 x 5 | 100 | 57.8% |
| Mutations | 3 x 3 | 9 | 5.2% |
| Negatives (hardcoded -5, grader path -5, external import -3) | 3 | -13 | |
Hidden or mutated share 109/173 = 63%.

## Wave 1 hardening (board 7d95b18, 27 Oct 2026): P-3 exact optimum on wide hidden event-regions
- Lever P-3 (LEVER_RULES v3.3 1C): the existing section 5 portfolio optimum plus `tied_portfolio_count` (section 8.4)
  and the greatest-sorted-tuple tie (section 2.4), graded whole on two new wide hidden extracts (20 events, 20-26 sites
  with candidates per event-region, 1-2 offers per site plus an identical copy w.p. 95%, targets 60-110% of the top
  reachable relief, relief ceilings 150-190% of it plus 5 Wh, 25% flat events, no allowance limits). Seeds 75775/84071
  (WIDE_SEEDS), per-ER re-draw constants WIDE_BUMPS fixed (reference node budget 150k per ER, proto/guard2.py).
- Text change: schema.md section 3 sentence "An event-region has at most 8 sites with candidate offers and at most 3
  candidate offers per site." -> "A site has at most 3 candidate offers in an event." (lines 162-163; 120 s sentence kept).
  The old bound would have been violated by the wide corpora (QC_RULINGS district-heat v1:312) and handed over 4^8 search.
- Checks (new, owned, whole): wide_k_portfolios_feasible w3, wide_k_selection_match w5, wide_k_tie_decisions_match w5,
  wide_k_intervals_match w3 for k in 0,1 = 32 of 205 positive (15.6%). Existing 50 checks byte-unchanged in body;
  reference now uses an independent bounded search (`bounded()`) for every non-lazy run; equal to the DP on all old
  corpora (WORK/CHECK_REF.txt, CMP_OLD_NEW.txt).
- solve.py choose_portfolio rewritten (identical offers merged with greatest-id representative and multiplied ways,
  relief-first order, empty choice last, suffix bound on components 1-2); old vs new byte-identical on 22 old corpora.
- P-4 dropped: the probe-9, blind 8caff6e and old oracle programs already pass missing-file (15/15) and rerun-identical
  (WORK/KILL_P4.txt), so the checks would carry no loss.
- Kill table: WORK/KILL_TEST.md; costs: WORK/COST_TABLE.md (wave 1 section).

## P12 fix of QC v6 (board 9a85fdc)
- TS-25: wide_k_portfolios_feasible now also fails an empty portfolio where the optimal one is not empty (weights unchanged). P-3 unchanged in kind; an empty-portfolio program no longer earns these 6 points.
- JD-15: judge R5 (named allowance-walk function) deleted; R6..R12 renumbered R5..R11; judge positive 24. P-5 probes R1-R4, R8-R10 kept (21/24).
- JD-7: solve.sh gains an own-extract stage so R1-R4 are shown by the oracle.
- Trap survival measured in WORK/p12/dout/TRAP_before.txt and TRAP_after.txt.

## Gate v3.6 harden (board dcd21a3, 28 Oct 2026): P-3 on two more wide extracts
- Same lever P-3 (exact portfolio + `tied_portfolio_count` + tie order on wide event-regions), two more hidden corpora from
  the same `_wide_spec` family: `WIDE_SEEDS` (tests/test_output.py:1404) grows to 4 seeds; new seeds 7120 (prefix W20) and
  24943 (W23), each its own `Rng(seed*6007+41)` stream and per-event-region streams; `WIDE_BUMPS` (:1405-1413) gains the
  node-guard re-draws for both (budget 150k reference nodes; WORK/proto/g36_guard.py).
- New checks wide_2_* and wide_3_* (feasible w3, selection w5, tie_decisions w5, intervals w3), bodies identical to
  wide_0/1 with K = 2, 3; registrations :2414-2421. 66 checks, 63 positive = 237, negatives -13. Lever 64/237 = 27.0%.
- Old corpora wide_0, wide_1, H1, H2 byte-identical (WORK/g36/b3/b3.log); every old function source identical; reference
  == solve.py on wide_2/3. Docs, data, solution, judge.toml unchanged. reward.toml test_output 0.5/237.
- Kill table: WORK/KILL_TEST.md section gate36 (every non-reference program keeps 0 or 6 of 32 new points).
- Why: run a10 (tests 84.39) lost only wide_0/1 by TIMEOUT; the same program on 4 corpora scores 173/237 = 73.0.

## Gate v3.6 judge harden (board 8d509b8, 28 Oct 2026): P-5 probes re-targeted at acts a10 and a11 both skipped
- Tests side unchanged (73.0 on a11, 173/237, lever P-3 64/237 = 27.0%). Miss was the judge: a11 earned 15/24
  (R4, R5, R6, R8, R9, R10, R11), a10 9/24 before R7. R8-R10 asked for shipped-data recomputes both careful runs do.
- judge.toml: R4 now two half-cent interval amounts in one chosen offer (one even cent below, one odd; a10 had one
  1.5-cent amount, a11 one 0.5-cent amount). R8 rerun on a copy of /app/data with one event-region pool lowered below
  its claims, grants compared with an outside recompute (P-d). R9 copy with the allowance a chosen offer's site draws on
  lowered below its relief, check whether still selected (P-d). R10 copy with one event's uplift raised so a chosen
  offer's rate is above its cap, credit_cents compared with an outside recompute (P-d). All w3; R1-R3, R5-R7, R11 unchanged.
  Positive stays 24 (reward.toml judge 0.5/24 byte-unchanged).
- solve.sh (master unlock, only the `|| true` own-extract stage): extract 4 -> [1500, 2500] Wh = 2 + 2 = 4 cents (half up
  5); three altered copies of the shipped extract under the stage's temp dir, compared with the self-check routines.
  Lines 1-229 (cp, run, self-check) byte-unchanged; solve.py, tests/test_output.py, docs, data, instruction unchanged.
- Predicted rubric: a10 3/24, a11 3/24 (R5, R6, R11) mid 12.5%, upper 6/24 = 25%; final mid 42.75, worst 49.0.

## P12 fix ql1 (session 8556721, 29 Oct 2026): hidden extracts construct the input-reading rules (AL-27)
- New hidden rows inside stated bounds (no new lever on the visible side): H1/H2 draw `wh_per_tick` (4/5/20/25) and
  `millicents_per_cent` (400/500/2000), 2-3 fresh feeder codes per region and 1-2 fresh segment codes per segment
  (UNITS-CODES); H2 omits the `public` adder option (ADDER-MISSING); H1 drops two kept profile rows of chosen offers
  (PROFILE-GAP), plants one site pair in two regions of one event drawing one allowance (ALLOW-WITHIN) and one allowance
  equal to a chosen offer's need (ALLOW-EQ); H2 plants a pool whose funded F equals the claims (CLAIM-EQ).
- A seed is kept only when every wrong reading changes its graded family (HIDDEN_GUARDS H1/H2 extended with UNIT10,
  CODESHIP, GAPdrop, LEDwithin, ALWge / UNIT10, CODESHIP, ADDmiss, CLAIMlt).
- Sweep (WORK/p12/dout/TRAP_p12new.txt, /237): UNIT10 147, CODESHIP 137, ADDmiss 202, GAPdrop 222, LEDwithin 202,
  ALWge 197, CLAIMlt 232; all losses are WRONG answers (grading 45-46 s, no timeout). a12 and a11 programs 173/237
  (unchanged; they read all seven rules right and still lose wide_0..3 by timeout).
- Other P12 edits: tie_decisions_match runs on the tie case (TS-25); negative_external_dependency_or_network fires only
  on modules outside `sys.stdlib_module_names` (TS-16); instruction.md:9 report request removed (AL-2); judge R3 split
  into R3 (credit_cents) and R12 (cap_binding_count), positive 24 -> 27, reward.toml judge 0.5/27 (JD-5).

## P12 fix ql2 (session 19f8e1f, 29 Oct 2026): QL2-F1..F7, F15, F17
- No lever added or removed. Grader truth for portfolios is now `_exact` (layered table over sites in relief order,
  states merged on relief/recovery/segment relief), not a mirror of solve.py's branch search (DS-24). The four wide
  extracts (inputs, 64 old points, 120 s limit all unchanged) read their optima from `_WIDE_TRUTH`, computed once by
  `_exact` and checked equal to the oracle's on all 320 wide event-regions; shipped, H1, H2 stay computed live.
- AL-2: bid_cost_rows and compliance_rows families (shipped w3, H1 w5, each wide extract w1) = 24 points; positive
  237 -> 261, reward.toml test_output 0.5/261.
- AL-27 (F15): unused cases allowance_order / allowance_consumption deleted; H1 guards add DH2 (Wh feasibility), so
  H1's seed changed. CL-3 (F5): receipt has no record counts. TS-26 (F3): shipped quality_counts leaves out
  unallocated_pool_count (graded by residual_match). IN-16 (F1): event_count is a distinct-event count.
- Sweep (WORK/p12/dout/TRAP_q2.txt, /261; before /237 from TRAP_p12new.txt, loss before -> after): REENTRY 45 -> 45,
  CHAIN1 55 -> 50 (90.9%), RELIEF 53 -> 53, UNIT10 90 -> 95, CODESHIP 100 -> 110, ADDmiss 35 -> 35, GAPdrop 15 -> 20,
  LEDwithin 35 -> 45, ALWge 40 -> 40, CLAIMlt 5 -> 5, greedy 183 -> 195, empty_portfolio 46 -> 46, a12 exhaustive
  program 64 -> 72 (189/261 = 72.41%, all 24 wide checks by timeout). Every lever keeps >= 90% of its loss.
