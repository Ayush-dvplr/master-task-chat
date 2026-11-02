# district-heat-flex-procurement: redesign r4 lever proposal (board 7743264)

Phase 1 only. No BUNDLE edits made. Bundle tree sha `c3c5b97731b5` (27 files, same method as `tree_sha`) matches the last QC'd tree.
Session rename: `name_session.py 7743264` printed `codex: no match`, `opencode: ['ses_e90a38693ffew0WFLS99brnDIr']`.

## 0. Why the old levers never bit

The r3 diagnosis holds: L3 (season allowance), L4 (rate composition) and L7 (per-interval half-even) are each a stated
step-by-step recipe in a governing comment, keyed by the same field they read. A fresh claude-opus-5 read the whole
schema and every data-file comment before writing, then transliterated sentence by sentence; nothing made it revise.
The saved blind program (`agent_program/blind/derive_report.py`, 98/98) reproduces the old oracle exactly
(sanity `blind == old rules`: 240/240 corpora, section 3).

The three new levers below use shapes never tried on this task: H7 re-entry, H6 counter keyed by a recursive chain
(no depth sentence), H3 defined term that differs from every input column. Plus one stated COUPLING quantity that
carries a grant error forward through the season. None reuses an entity+mechanism of another live task (tariff
allowance re-share, config quota re-share, metered credit/shortfall re-share, sentinel timeout pool, caldermoor
second-pass allocation are all re-shares of a cap or allowance; M1 here is a minimum-grant drop inside a
claims-or-proportional apportionment, keyed by beneficiary; see the risk note in 6).

## 1. Levers

| id | habit | where the rule is written (Phase 2) | reflex reading (what a first write does) | separating case (hidden only) |
|---|---|---|---|---|
| M1 grants re-share | H7 re-entry | `schema.md` section 7 (now 207-231; new paragraph replaces 221-231), keys declared in section 1 `program.ini` entry (18-33) and in `program.ini` `[grants]` | one `apportion(F, members)` that first checks "claims fit -> pay claims", then calls it again for the survivors (REENTRY); or keeps first shares of survivors (DROPLEFT); or no drop (NODROP) | survivors' claims add up to F or less on the second pass: reference shares every cent of F again; re-entry pays claims and leaves the rest unallocated |
| M2 allowance holder | H6 counter keyed by recursive chain | `site_allowances.tsv` comment (now 1-7) gains `draws_from`; schema section 1 file entry (95-98) names the column | `remaining[site_id]` with the site's own figure (CHAIN0, which is what both saved programs do), or one hop `draws_from or site_id` (CHAIN1) | a chain of depth 2+ whose holder allowance binds |
| M3 credited relief | H3 defined term differs from every column | `rate_cards.xml` comment (now 2-12) uses "credited relief ticks"; schema section 6 (198-205) defines it | interval amount from the `relief_ticks` column/output field (RELIEF) | an interval where a chosen offer has both relief and recovery ticks |
| CARRY (coupling, counts 0) | stated quantity | schema section 7: unallocated cents of a region's event-region carry into the funded pool of the same region's next event in season order | (amplifier only; it is stated once, plainly) | every later event-region of the region |

### Proposed rule text (W1-W7; no warnings, no trap lists, H7 wording rule applied)

M1, schema section 7 (after the recipients paragraph):

> `program.ini` section `[grants]` gives `claim_cents_per_weight` and `minimum_grant_cents`. The claim of a beneficiary
> is its weight times `claim_cents_per_weight`.
>
> When there are no recipients, the whole funded pool is unallocated. When the claims of the beneficiaries with a
> positive weight add up to F or less, each of them receives its claim and the rest of F is unallocated. Otherwise F is
> shared by largest remainder: [existing largest-remainder sentences kept]. A beneficiary whose share is less than
> `minimum_grant_cents` receives nothing. When some beneficiaries receive nothing this way and others do not, every cent
> of F is shared again, in proportion to weight by largest remainder, across only the beneficiaries whose share was
> `minimum_grant_cents` or more; each of them receives this second share. When every beneficiary receives nothing this
> way, the whole of F is unallocated. A beneficiary with a positive weight that receives nothing is listed with 0 cents.
>
> The residual cents and the residual tie of a pool belong to its last largest-remainder share; a pool whose claims are
> paid has none.

The second-pass sentence names the amount (every cent of F), the method (in proportion to weight by largest
remainder) and the set; it never says "by the same rule" and never names or exemplifies the case where the survivors'
claims fit.

CARRY, schema section 7 (funded-pool sentence, 211-213):

> The funded pool F is the grant pool plus the carried cents, minus the event-region's credit cents, or 0 when that is
> negative. The carried cents of an event-region are the unallocated cents of the same region in the event reached just
> before it in season order (the order the `site_allowances.tsv` comment sets); the first event of a region carries
> nothing. `grant_pool_cents` stays the `pools.txt` figure.

M2, `site_allowances.tsv` comment:

> `draws_from` is blank or names another site_id of this file. A site whose `draws_from` is blank draws on its own
> `allowance_ticks`. A site whose `draws_from` names another site draws on the allowance that the named site draws on,
> and its own `allowance_ticks` figure carries no rule. The remaining allowance of an offer's site is the allowance it
> draws on less the relief ticks of the offers chosen, in events reached before, at every site that draws on that
> allowance. No `draws_from` chain returns to a site already on it.

(The last sentence is a data guarantee, not a depth sentence. Shipped data has chains of depth 1 only.)

M3, `rate_cards.xml` comment: "An interval amount is the offer's credited relief ticks in that interval times
wh_per_tick, ..." (rest unchanged). Schema section 6 adds:

> An offer's credited relief ticks in an interval are its relief ticks in that interval less its recovery ticks in that
> same interval, or 0 when its recovery ticks there are the larger.

The term is keyed in one file and defined in another (W-rule: key the rule from a different file than the field it
reads); `relief_ticks` remains the output field and the profile-derived quantity everywhere else.

## 2. Reflex pre-mortem (fresh claude-opus-5, first 10 minutes)

The r3 trajectory: reads instruction, `program.ini`, manifest, the whole schema, every data head and comment, then
writes one 700-line program in ~3 minutes and runs it once. Where each lever lands in that first write:

- M1: the schema paragraph is read as a recipe with three branches. The measured habit (caldermoor CM-B, TEST_DEPTH
  lines 21-67) is a helper `apportion(F, members)` that holds all three branches and is called again on the
  survivors; on that call the claims-fit branch fires when the survivors' claims fit. The sentence names the method
  for the second pass, so a careful reader writes a bare largest-remainder call; the honest chance of the re-entry
  slip is moderate (30-50%). DROPLEFT and NODROP are lower-probability slips.
- M2: the recursive sentence "draws on the allowance that the named site draws on" is the whole rule. A first write
  is either `holder = draws_from or site_id` (one hop, CHAIN1) or a `while` loop. Shipped data has depth-1 chains
  only, so a one-hop program passes every visible test and nothing prompts revision. Risk: a while-loop is a natural
  first write, so this lever may measure REVEALING (0% on a fresh solver). It is kept because it is cheap and
  independent, not because it is certain.
- M3: the term "credited relief ticks" contains "relief ticks", which every reader already maps to the profile column
  and the output field; the definition sits in schema section 6, one section away from the comment that uses it.
  Shipped profiles have 0 rows with relief and recovery in the same interval, so the relief-ticks reading passes every
  visible check. Opus reads the whole schema, so the chance is moderate.
- The saved programs (blind and harness) implement none of the three, by construction (they predate them).

Predicted fresh-Opus tests channel: all three right -> ~100 (park); M1 re-entry only -> ~73; M3 only -> ~65;
M1 + M3 -> ~40. Central estimate 70-80 with real variance; overall at judge 62.5 then 66-71.

## 3. Prototype results (OUT/proto/, scratch only)

Files: `proto_oracle.py` (solve.py + `PROTO_ON` = M1,M2,M3,CARRY and `PROTO_WRONG` = REENTRY, DROPLEFT, NODROP, CHAIN0,
CHAIN1, RELIEF; with `PROTO_ON=` it is byte-identical to the shipped solve.py output on shipped data), `gen.py`
(hidden corpora from the existing `_composed_spec` of `WORK/test_output.src.py` + `[grants]`, `draws_from` chains of
depth 1-4 with binding holder allowances, and per-region planting of the M1 separating pool: first season event-region
with a separating option gets F, earlier pools of that region set to 0), `fuzz.py`, `shrunk.py`, `ship_probe.py`.

Points use the proposed Phase 2 test layout (section 4): 173 test points.

240 corpora (seeds 2000-2239, each an H1 + H2 + open-allowance H2 copy; `proto/fuzz_2000_240.json`,
`proto/fuzz_2000_240.log`). Sanity: blind program == old rules on 240/240; harness program == old rules on 240/240
open-allowance copies (it predates the allowance rule, so it is measured on M1 and M3 only).

| measure | differing | mean points lost / 173 | share | max | families hit |
|---|---|---|---|---|---|
| agent alone M1 (blind vs M1 only, no carry) | 240/240 | 42.6 | 24.6% | 43 | grants, allocation, residual, summary, region totals x4 |
| agent alone M2 (blind vs M2 only) | 240/240 | 55.7 | 32.2% | 58 | selection, intervals, ledger quality, segment rows/totals, summary, region totals x4, tie 133/240 |
| agent alone M3 (blind vs M3 only) | 240/240 | 57.9 | 33.5% | 66 | credit rows, segment credit, funded, grants, allocation, residual, totals |
| agent, all new rules (blind vs reference) | 240/240 | 91.8 | 53.0% | 94 | 17 of 20 families |
| absent M1 (all on except M1; the lever alone in the shipped configuration, carry on) | 240/240 | 47.6 | 27.5% | 48 | + funded pool |
| absent M2 | 240/240 | 55.7 | 32.2% | 58 | as agent alone M2 |
| absent M3 | 240/240 | 58.6 | 33.9% | 66 | as agent alone M3 + funded |
| one-fact-wrong REENTRY (H7 re-entry) | 240/240 | 46.7 | 27.0% | 48 | funded, allocation, grants, summary, totals, residual 209/240 |
| one-fact-wrong DROPLEFT | 240/240 | 48.0 | 27.7% | 48 | same |
| one-fact-wrong NODROP | 240/240 | 35.5 | 20.5% | 48 | grants, residual, allocation 213, funded 211 |
| one-fact-wrong CHAIN0 (column ignored) | 240/240 | 55.7 | 32.2% | 58 | as M2 |
| one-fact-wrong CHAIN1 (one hop) | 239/240 | 51.4 | 29.7% | 58 | selection, ledger quality, intervals, segment rows/totals, summary, totals ~200 |
| one-fact-wrong RELIEF (relief ticks, not credited) | 240/240 | 58.6 | 33.9% | 66 | credit, segment credit, funded, allocation, totals, grants 209 |
| REENTRY without CARRY (vs reference without carry) | 240/240 | 41.0 | 23.7% | 43 | CARRY adds 5.7 points (funded pool + region totals reach) |
| harness program, open copy, M1 | 240/240 | | | | allocation, grants, residual |
| harness program, open copy, M3 | 240/240 | | | | credit rows, segment credit, funded 238, grants 238, residual 207 |

Every main wrong reading sits in the honest 25-45% band (CL-4); NODROP (20.5%) is a secondary slip that only drops the
minimum rule. G10 holds on the shipped configuration (absent M1 27.5%, M2 32.2%, M3 33.9%); M1 measured without its
CARRY amplifier is 24.6%, which is why CARRY is part of the design (and counts 0 as a lever). "All but one right"
-> tests ~66-73, overall at judge 62.5 ~64-68 (< 70).

100% differing is by construction: the generator plants every branch per region (G12): the M1 separating pool in the
first season event-region that admits one (earlier pools of that region zeroed; 0 regions of 240 left unplanted in the
30-seed check), chains of depth 1-4 with binding holder allowances in H1, and the existing generator's same-interval
relief/recovery overlap for M3.

### Shrunk corpora (`proto/shrunk/{M1,M2,M3}/`, results in `proto/shrunk/RESULT.json`)

- M1: one event, North; BEN-A weight 1, BEN-B weight 3; `[grants]` claim 30, minimum 26; pool 100; no offers.
  Claims 120 > 100, first share 25/75, BEN-A dropped (25 < 26); survivors' claim 90 <= 100.
  Reference A 0, B 100. Blind program A 25, B 75. REENTRY B 90 + 10 unallocated. DROPLEFT B 75 + 25 unallocated.
- M2: S3 draws_from S2, S2 draws_from S1 (S1 allowance 100, S2/S3 figure 0); event 10:00 offers S3 60 ticks; event
  11:00 offers S2 60 ticks. Reference: S3 chosen (100 -> 40), S2 blocked. Blind / CHAIN0: both blocked.
  CHAIN1: S3 blocked (one hop reaches S2's 0), S2 chosen.
- M3: one offer, relief readings 600/400, recovery 200/0 (ticks 60/40 and 20/0), base = cap = 9000. Reference credit
  4 + 4 = 8 (credited 40/40 ticks, 3.6 -> 4 half-even); blind / RELIEF 5 + 4 = 9.
- The harness program differs on all three as well.

### Shipped data probe (W5, `proto/ship_probe.py`)

Shipped data plus `[grants]` (claim 40, minimum 1 / 10 / 25) and 120 depth-1 `draws_from` pairs: REENTRY, DROPLEFT,
NODROP, CHAIN1 and RELIEF reproduce the reference on shipped data (no drop arises once carry makes pools large; shipped
profiles have 0 of 108036 rows with relief and recovery in the same interval). CHAIN0 differs in 15 visible families,
no-carry in 7, the saved blind program in 17 of 20 (it passes labels, quality counts, tie decisions).

Reading: "agent alone X" = saved blind program vs the oracle with only X switched on (the program lacks X; every other
new rule dormant). "one-fact-wrong" = all new rules on with one wrong reading vs the reference. "absent X" = all on except
X. CARRY is the amplifier: REENTRY without carry costs REENTRY_NOCARRY.

## 4. Proposed test layout (G1 owned rows; Phase 2)

Two hidden extracts from a seeded generator embedded in tests (G8): H1 "season" (chains planted, all rules live) and
H2 "settlement" (no `draws_from` rows, so M2 cannot cascade into money rows; M1, M3, CARRY live). Each family is one
visible test w3 on shipped data and one hidden `_hard` test w5 (owned rows, exact equality, first differing path in the
message):

- on H1 (13): selection (selected_offer_ids, candidate_offer_count), intervals, tie_decisions, segment rows (non-money),
  ledger quality (allowance_blocked_offer_count, empty_candidate_groups), region totals x4 (one per region file),
  segment totals, summary, labels (site_labels + compliance_counts), quality counts.
- on H2 (7): credit rows, segment credit rows, funded pool (grant_pool, grant_funded), grants lists, grant allocation
  (allocated, unallocated), residual (residual_cents, residual_tie_pool_count, unallocated_pool_count), cap binding.
- format 4 x w1 (non-core); mutations 3 x w3: segment_rate_adder (credit rows), allowance_ticks (selection rows), new
  minimum_grant (grants rows). Total 20 x 8 + 4 + 9 = 173. Hidden/mutated share 109/173 = 63% (G3).
- Negatives unchanged (hardcoded -5, reads tests -5, external dep -3). Core weights 3/5 only.
- If the reflex gate comes out above 0.20 because of the always-pass controls (labels, quality counts, cap binding,
  tie decisions, format), Phase 2 merges labels into quality counts (one family) before any strengthening.

## 5. Judge plan

Keep the 8 existing criteria (J3 honesty, J4 code quality kept). Add one conduct criterion w3 per new lever family,
own-input recompute, each with a `check <id> ok` line in solve.sh (JD-7):
- grants: "independently recomputes every beneficiary's grant cents for at least three event-regions outside its
  program and compares them with its region documents";
- allowance holder: "independently recomputes the remaining allowance each chosen offer drew on outside its program
  and compares it with its selections";
- credited relief: "independently recomputes the credit_cents of chosen offers outside its program and compares them
  with its region documents".
`[judge] mode = "batched"`; WORK/JUDGE_MAP.md updated.

## 6. Risks and open points for the master

- M1 vs other live H7 levers: tariff/config/metered/caldermoor all re-share a capped or forfeited amount; here the
  entity is a beneficiary grant and the trigger is a minimum-grant drop under a claims-fit branch. If the master reads
  this as the same entity+mechanism as caldermoor's second-pass allocation, swap the second pass for a re-share across
  survivors in proportion to claim instead of weight (same habit, different quantity) before Phase 2.
- M2 may be REVEALING on a fresh solver (a while-loop is a likely first write). Kept for independence; cost is honest.
- W5: shipped data with `[grants]` (claim 40, minimum 1-25) and 120 depth-1 pairs: REENTRY, DROPLEFT, NODROP, CHAIN1
  and RELIEF all reproduce the reference on shipped data; CHAIN0 (column ignored) differs in 15 visible families,
  which is intended (the column is plainly visible and used).
- Reflex gate estimate for the saved blind program on the new tests: ~28-33/173 = 0.16-0.19 (passes labels, quality
  counts, cap binding, tie decisions, format). Tight; see the merge fallback in 4.

## 7. Files Phase 2 touches

BUNDLE: `environment/data/schema.md` (sections 1, 6, 7), `environment/data/program.ini` (`[grants]`),
`environment/data/site_allowances.tsv` (`draws_from` column + comment; depth-1 chains only),
`environment/data/rate_cards.xml` (comment), `environment/data/export_manifest.tsv` (receipt figures re-derived),
`solution/solve.py` (+ `solve.sh` self-check lines), `solution/TRUTH.md`, `tests/test_output.py` (rebuilt from
`WORK/test_output.src.py`: reference flags REENTRY/DROPLEFT/NODROP/CHAIN0/CHAIN1/RELIEF/NOCARRY, generator planting,
new families, embedded shipped data), `tests/judge.toml`, `tests/reward.toml`, `instruction.md` only if the G5 sentence
needs the new keys (no other change). WORK: DESIGN.md (Redesign), LEVERS.md, TRUTH.src.md, QC_DEFENCE.md, XREF.md,
COST_TABLE.md, RULE_COVERAGE.md, JUDGE_MAP.md. Domain, slug, input families and deliverable shape unchanged.
