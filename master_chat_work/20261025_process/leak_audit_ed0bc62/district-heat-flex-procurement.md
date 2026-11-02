# Leak audit: district-heat-flex-procurement

- Slug: `district-heat-flex-procurement`
- Bundle: `master_chat_work/bundles/district-heat-flex-procurement/`. Newest file `tests/*` 25 Oct 02:19; `environment/data/schema.md` 25 Oct 01:45; `instruction.md` 23 Oct 09:05.
- Trajectory: `jobs/district-heat-flex-procurement/trajectory/claude-opus-5/Run 1/` (agent started 25 Oct 06:00, finished 06:38, verifier 06:39). The run is newer than every bundle file. `agent/instruction.txt` is identical to `instruction.md` (`diff` printed nothing), so the run saw the current bundle.
- Probe score: tests 100 (47 positive passed; the 3 negatives did not fire), rubric 37.04 (judge fails R1, R2, R3, R10), overall 68.52.
- Latest diagnosis read: `20261025_district-heat-flex-procurement/redesign_r4/` (REDESIGN_REPORT.md fully, DESIGN_PROPOSAL.md sections 0-2). STACKING_CHECK.md was not read in full.
- Audit only. Nothing was written outside OUT. No docker, harbor, pip or git was run.

## Headline

The shipped data is cold, as W5 requires: out_of_range 0, duplicate 0, unknown_region 0, tie_decisions [], residual 0, chain depth 1, no profile row with both relief and recovery. Every hidden test is still covered by a plain schema sentence that states the whole rule, with amount, method and set.

Opus read `schema.md` plus every file comment (steps 4-6), then wrote the full program in ONE file create at step 15. That first write already contains:
- the `draws_from` root-resolution loop (file_text lines 293-309),
- the `kept = ... shares[b] >= minimum_grant_cents` second share (line 501),
- the per-region carry (lines 530 and 570).

Steps 16-55 were verification only. Step 31 was a pruning optimisation, steps 37-39 and 45 were tie/prune changes, and the real-data output stayed byte-identical (steps 32, 41, 46). No behavioural fix to a rule was ever needed.

The points that run lost are all on the judge side (conduct criteria R1-R3, R10), not on the tests.

## Step 1: agent-visible surface

`environment/Dockerfile` (the whole file is 18 lines):

```
FROM public.ecr.aws/docker/library/python:3.12-slim@sha256:646f...
RUN groupadd -g 1000 agent ... ; ENV HOME=/home/agent
RUN apt-get ... xxd file curl bash nodejs npm procps ca-certificates tmux
WORKDIR /app
RUN python3.12 -m venv /opt/openhands-sdk-venv && pip install openhands-sdk==1.55.1 ...
RUN mkdir -p /app && chown 1000:1000 /app
COPY data /app/data
```

`COPY data /app/data` is the only COPY. The build context is `environment/`, so `solution/`, `tests/` and `master_chat_work/bundles/_work/` are not reachable. I confirmed `_work/district-heat-flex-procurement/` (HARDEN_PROMPT.md, DESIGN.md, LEVERS.md, datagen.py, `wrong/`, `stub/`, ...) sits outside `bundles/<slug>/environment/`. `task.toml` has `[verifier] environment_mode = "separate"`, and `tests/Dockerfile` does `COPY . /tests/` into a separate verifier image. `tests/test.sh` runs `chmod -R go-rwx /tests` and `rewardkit /tests --workspace /app`. Tests are therefore not in the agent container, and `solution/` is in no Dockerfile.

Agent runs as `1000:1000` (task.toml `[agent] user`). Agent network is an allowlist of `api.anthropic.com` and `api.z.ai` only.

| Path in container | Size | Notes |
|---|---|---|
| /app/data/schema.md | 20,798 B, 358 lines | full rulebook |
| /app/data/program.ini | 600 B | has `[export] waiver_signed = Y` and `[grants]` |
| /app/data/export_manifest.tsv | 977 B | receipt, 14 data rows |
| /app/data/site_allowances.tsv | 20,654 B | 10-line governing comment |
| /app/data/rate_cards.xml | 812,624 B | 11-line governing comment, 10,000 cards, 226 overrides |
| /app/data/profiles.tsv | 3,204,214 B | 108,036 rows |
| offers.csv 977,889 B; site_state.jsonl 1,169,629 B; sites.csv 340,066 B; feeder_limits.txt 456,097 B | | |
| segment_floors.json 516,399 B; continuity_waivers.csv 267,454 B; targets.tsv 249,888 B; recipient_weights.tsv 176,065 B | | |
| events.json 116,089 B; pools.txt 54,070 B | | |
| /app/out | empty | writable, created by the agent |

Not visible: `tests/` (2.3 MB `test_output.py` with embedded base64 shipped data and the reference implementation), `solution/` (solve.py, solve.sh, TRUTH.md), `judge.toml`, `reward.toml`.

Shipped files containing expected output, a digest of it, or a script that computes it: none.

Partial exception: `export_manifest.tsv` carries record counts for 14 files "counted the way data_quality.json counts the rows of that file". That is the expected value of `data_quality.rows` for every file listed (finding L08).

Extras: `find` shows no `__pycache__`, `.DS_Store`, `~` files or `.git` under the bundle. `grep -rniE "harbor|QC|lever|rubric|trap|decoy|hidden|grader|oracle|TRUTH|solution"` over `schema.md`, `program.ini`, `export_manifest.tsv` and `instruction.md` finds only the instruction's "hints specific to this task" boilerplate. The only meaningful word hit anywhere in `environment/data/` is `legacy` in `program.ini:32`.

## Step 2: checklist A-J

| | Y/N | Evidence |
|---|---|---|
| A names | N (weak Y) | Column names, enums and ids are neutral (`mode_label` in BOILER_BRIDGE, DHW_DEFER and similar; ids `W26-xxxx-HXnnnnn-<letter>`). Weak tell: all 14 orphan offers end `-X`, and `-X` appears on no other offer. All 36 orphan profile rows end `-Q`, and `-Q` is on no offer. The letters I, O and Q are skipped in the normal offer suffix alphabet (checked with python on `offers.csv` and `profiles.tsv`). Orphan handling is a plain join, so the tell is low value (L14). |
| B tone | N | No CAPS, bold, "careful" or "note". Navigational phrases do exist: `schema.md:3-8` "a comment that states how a file's own fields are read is binding"; `:98-100` "The comment at the top of the file says how an allowance is drawn and which allowance a site draws on"; `:89-90`; `:159-160` (L11). `instruction.md:3,7,9` announce fresh-extract grading and ask for a report of "how you checked it" (L12). |
| C separating-case rules | Y | `schema.md:235-241` (grants re-share), `site_allowances.tsv:3-5` (chain), `schema.md:205-207` (credited relief ticks), `:216-218` (carry), `rate_cards.xml:3-10` (rate and credit recipe). Quotes and test mapping below. |
| D shipped data showing the separating case | N for traps (W5 held), Y for hints | Cold counters in the agent's own output (step 17 `data_quality.json`): `duplicate_profile_rows 0`, `out_of_range_profile_rows 0`, `unknown_region_site_rows 0`, `tie_decisions []`, `residual_cents 0`, `residual_tie_pool_count 0`. Chain depth 1 only (agent step 11 printed `max depth 1`). Event order by instant equals order by text (python check: 0 position differences), though 57 of 500 events use +00:00 and 443 use +01:00. The manifest gives expected `data_quality.rows` (L08). |
| E visible tests, self-checks, validators | Y (partial) | `export_manifest.tsv:5` "A file whose lines here agree with it arrived whole". The agent reproduced every count and field sum (steps 10, 21, final message). No visible test or CI log. |
| F repo and history | N | No `.git`, no TODO/FIXME. |
| G leftovers | N | See the Step 1 extras. `program.ini:32` "Defaults the legacy export tool applies to fields it did not record." is the decoy itself, not a leftover (L06). |
| H cross-file consistency | Y | The same rule is said twice or three times: waiver signed-ness appears at `schema.md:81-82`, `:149-152`, `:349-350` and `program.ini:31-33`. Rate composition appears at `schema.md:39-40,140-143`, `program.ini:21-25` and `rate_cards.xml:3-10`. Chain appears at `schema.md:98-100,159-160` and `site_allowances.tsv:3-5`. Each file reaches the same conclusion, so no contradiction exists for the agent to notice. |
| I judge and conduct hints | weak Y | `schema.md:123-125` "binary floating point is never used for a reported figure" mirrors judge R6. `instruction.md:9` "reply with ... how you checked it" mirrors R7/R8. The R1-R4 criteria are NOT echoed anywhere visible, and the agent missed R1, R2, R3 and R10. |
| J agent usage | Y | See the trajectory column in the findings. |

## Test-to-leak map (50 checks; flags from `tests/test_output.py` ALL_FLAGS)

Each visible family `X` (w3) is on shipped data and its `X_hard` twin (w5) is on a seeded extract. Four format checks are w1, and three mutation checks (adder, allowance_ticks, minimum_grant) are w3.

| Hidden check or flag | Visible sentence or data that reveals the rule | Genuinely hidden? |
|---|---|---|
| grants_match_hard, grant_allocation_match_hard, residual_match_hard, minimum_grant_mutation (REENTRY, DROPLEFT, NODROP, CLAIM0, W0LIST, H4) | `schema.md:230-250` full three-branch apportionment. Second pass: "every cent of F is shared again, in proportion to weight by largest remainder, across only the beneficiaries whose share was `minimum_grant_cents` or more". `program.ini:27-29` gives the numbers. Separating case is in the hidden extract only. | No, the rule is complete |
| selection_match_hard, intervals_match_hard, tie_decisions_match_hard, ledger_quality_match_hard, allowance_ticks_mutation (CHAIN0, CHAIN1, LEDid, LEDstr, LEDtie, LEDnone, LEDstatic) | `site_allowances.tsv:2-11` and `schema.md:97-100,157-160`. The sentence "No `draws_from` chain returns to a site already on it" only makes sense for chains longer than one hop. Shipped chains are all depth 1. | No |
| credit_rows_match_hard, segment_credit_rows_match_hard, cap_binding_match_hard, segment_rate_adder_mutation (OVR0, OVRrate, ADD0, UPL0, H3, CAPpre, R7offer, R7up, R7offer_even, H5c) | `rate_cards.xml:3-10`, `program.ini:21-25`, `schema.md:39-40,140-143,208-209`. Shipped data has 226 overrides, uplift 1000/2000/3000 and adder 750. | No (the recipe is stated in full) |
| RELIEF (credit_rows_match_hard) | `rate_cards.xml:10-11` uses the term "credited relief ticks"; `schema.md:202-207` defines it. Shipped data has 0 rows with relief and recovery both non-zero in one interval. | No |
| funded_pool_match_hard, grants_match_hard (NOCARRY, DH3) | `schema.md:213-218`: "calculation order ... portfolio, then its credits, then the funded pool, then the apportionment"; the carried-cents definition. | No |
| labels_match_hard (H1, H1order, H1hc, H1pend, SIGNEDY) | `schema.md:145-152` ranking and "valid only when all four of these hold"; `:81-82` empty `waiver_signed`; `:30-31` and `program.ini:31-33` the `[export]` decoy. | No |
| quality_counts_match(_hard) (DH4*, unknown region, waiver_signed_missing) | `schema.md:46-50,60-67,338-358`; the manifest gives `rows` values. | No |
| selection_match_hard (C34, C45, C5drop, H2) | `schema.md:183-198` ordered components; `:132-138` ties. | No |
| quantise (H5t, DH2, MULT0, MULTtick, DH5raw) | `schema.md:55-59,114-130`. Shipped data has multipliers 2 and 5 (5,410 rows) and relief values such as 3001 Wh. | No |
| 4 format checks | `instruction.md:7`, `schema.md:252-258` | No |
| 3 negatives | `instruction.md:3,6` ("must not depend on the shipped records", "standard library") | n/a |
| Judge R1-R4 (own-extract conduct) | Nothing visible echoes the exact scenarios. The topics are signalled by L02/L04/L07 | Mostly hidden |

## Findings

(Severity: C = critical, H = high, M = medium, L = low. "Tests/data" = does the fix touch tests or data.)

| id | cat | sev | file:line + quote | evidence it helped the agent | proposed fix (not applied) | QC rule touched + risk | tests/data |
|---|---|---|---|---|---|---|---|
| L01 | C/H | HIGH | Structural: `schema.md` is a complete literal algorithm for all seven levers, with amount, method and set stated in plain sentences (lines 205-207, 213-218, 230-250, 97-100, `rate_cards.xml:3-10`). The redesign report says "stated step-by-step recipes" and kept this shape in r4. | Step 4 `cat schema.md`, steps 5-6 every comment. Step 15, first write, contains the chain loop (lines 293-309), survivors second share (501) and carry (530/570). Zero rule changes in steps 16-55. Tests 100. | Stop stating the rule as a recipe. Keep each lever's definition only in the data comment that governs it and let `schema.md` say the term without its computation. Alternatively make the right reading depend on joining two facts that no sentence combines (LEVER_RULES W3/W2). | W1-W3 stack; fairness QC (rules must be derivable): high risk, because removing too much makes the task ambiguous. | schema.md and comments, maybe data |
| L02 | C | HIGH | `schema.md:235-241` "every cent of F is shared again, in proportion to weight by largest remainder, across only the beneficiaries whose share was `minimum_grant_cents` or more, with W now the sum of their weights" | Step 56: "the `minimum_grant_cents` filter, the second share over the survivors, and the all-below-minimum case"; synthetic "minimum-grant exclusion with a second share". Step 15 line 501. Tests: grants_match_hard, minimum_grant_mutation pass. | Describe the programme's intent ("shares are funded and then paid only at or above the minimum") but remove the "shared again ... across only" recipe. The re-entry then must be inferred. | H7 wording rule (W1-W3): drop the sentence that names amount, method and set. Fairness risk: the reference needs one unambiguous rule. | Y (schema.md, solve.py doc unaffected) |
| L03 | C | HIGH | `site_allowances.tsv:3-5` "A site whose draws_from names another site draws on the allowance that the named site draws on ... No draws_from chain returns to a site already on it." and `schema.md:98-100` "which allowance a site draws on" | Step 11 printed `max depth 1`, `groups 1220`. Step 15 lines 293-309 resolve a chain to its root. Step 56 "draws_from chains resolved to a root allowance"; synthetic "two-level draws_from chain". Hidden tests (selection_match_hard, allowance_ticks_mutation) pass. | Drop the acyclicity sentence (it announces multi-hop chains). Say only that a site draws on the allowance of "its holder", with holder defined in the schema by a different phrase than the comment uses. | W5/H6; fairness: the acyclicity guarantee is needed by the reference. Risk: medium. | Y (comment + schema bullet) |
| L04 | C | HIGH | `schema.md:205-207` "credited relief ticks ... its relief ticks ... less its recovery ticks in that same interval, or 0 when its recovery ticks there are the larger" and `rate_cards.xml:10-11` uses the same term | Step 15 computes interval amount from credited ticks. Step 56 "credited ticks × wh_per_tick × rate". credit_rows_match_hard passes. | Define the term only in `rate_cards.xml`, and use a different term in `schema.md:205` for the quantity chosen offers deliver. | M3 lever shape; low risk, both places already exist. | Y (docs only) |
| L05 | C/D | HIGH | `schema.md:213-218` "The calculation order ... portfolio, then its credits, then the funded pool, then the apportionment" + carried cents definition | Step 56: "grant_funded_cents reaches 51 615 561 834 ... because section 7 carries each event-region's unallocated cents". The output looks absurd, and the agent still quoted the rule to defend it. | Remove the explicit calculation-order sentence (it removes DH3) and state carry through the allowance comment only. | W1; risk low. | Y (schema.md only) |
| L06 | A/H | HIGH | `program.ini:31-33` "[export] ... Defaults the legacy export tool applies to fields it did not record. waiver_signed = Y" and, on the same page, `schema.md:30-31` "`[export]` belongs to the export tool ... and carries no rule for this programme" | Step 56 first paragraph: "`[export]` deliberately ignored because the contract says it carries no rule - so an empty `waiver_signed` is not `Y`". labels_match_hard (SIGNEDY) passes. | Remove the sentence in `schema.md:30-31`; leave the `[export]` default in `program.ini` unexplained, or move the refutation to a place that is read only after the decoy is used (LEAK_LIBRARY: never ship a decoy with its refutation beside it). | W3/H-decoy rule; low risk. | Y (schema.md; maybe program.ini) |
| L07 | C | HIGH | `rate_cards.xml:3-10` "starts from the base ... override ... instead ... effective rate ... cap as the programme conventions say ... rounded half to even"; `schema.md:39-40` uplift; `program.ini:21-25` adder; `schema.md:140-143` cap | Step 56: "effective rate of override\|base + event uplift + segment adder, capped last". credit_rows_match_hard, cap_binding_match_hard and segment_rate_adder_mutation pass. | Spread: the adder and uplift stated only as column or option semantics without stating that they sum with the override; the cap statement points to "final rate" with no list of adjustments. | W2: remove enumeration; risk: reference reading becomes less obvious. | Y |
| L08 | D/E | MEDIUM | `export_manifest.tsv:1-5` receipt gives records and field sums for 14 files "counted the way data_quality.json counts the rows"; "A file whose lines here agree with it arrived whole" | Step 10 recomputed every count and sum, step 21 the fixed-width sums, final message "every record count and field_sum ... reproduces exactly". It is an answer key for `data_quality.rows` (14 values) and a parser validator. | Drop the manifest or make it counts-only for files that cannot fail parsing. | G8-style digest rule; risk low. | Y (data) |
| L09 | C/E | MEDIUM | `schema.md:162-164` "at most 8 sites ... at most 3 candidate offers per site. Each run ... must finish within 120 seconds." | Steps 28-47 built stress and tie extracts at exactly 500x4x8x3 (runs of 291 s, 23 s, 140 s, 114 s) and pruned the DFS. No score effect here, but it reveals the hidden extract scale. | State the limit only in `instruction.md` as "must run in reasonable time" without numbers, if QC allows. | Instruction-clarity QC: it asks for bounds, so keep them unless a ruling says otherwise. Risk: medium. | Y (docs) |
| L10 | D | MEDIUM | Shipped counters that are all zero: `duplicate_profile_rows 0`, `out_of_range_profile_rows 0`, `unknown_region_site_rows 0`, `tie_decisions []`, `residual_cents 0` (step 17 output) against a schema that defines each | Step 56: "exercising every branch the shipped data leaves cold". Agent built about 70 asserted synthetic values (steps 23-25), covering all hidden families except R1-R3 specifics. | Seed shipped data with a few non-separating instances of each (duplicates that are identical, out-of-range rows, one unknown-region row), so cold vs hot no longer maps to hidden vs visible. | W5 allows non-separating rows; risk: must not change the reference answer in a separating way. | Y (data) |
| L11 | B/H | MEDIUM | `schema.md:3-8`, `:89-90`, `:98-100`, `:159-160` signposts "the comment at the top of the file says ..." | Steps 5-6 read the comments in full right after the schema. | Remove the signposts; let `schema.md` name the field only. | Cross-file ruling: rules must be discoverable; keep one signpost at most. | Y (docs) |
| L12 | B | MEDIUM | `instruction.md:3` "It will also be run on other extracts", `:7` "graded whole on fresh inputs", `:9` "how you checked it" | Steps 23-25, 35-36 synthetic harnesses; final message lists them. | Instruction QC likely requires the "other extracts" sentence, so keep it. The "how you checked it" request is optional and can go, but judge R7/R8 depend on it. | Judge QC J9; risk: removes conduct evidence. | Y (instruction + judge) |
| L13 | C | MEDIUM | `schema.md:145-152` "valid only when all four of these hold: ... VALID ... Y ... critical ... public" | labels_match(_hard) pass, but the agent's final message does not quote it. INFERRED help. | Express the four conditions across two sections (status and signed in 2.6, segment and critical in 4). | W2; low risk. | Y (schema.md) |
| L14 | A | LOW | Orphan offers end `-X` (14/14, no other offer does); orphan profile rows end `-Q` (36/36, no offer does). | INFERRED; the agent uses a join (data_quality passes). | Re-draw the orphan suffix from the normal alphabet. | Data regeneration changes the answer files; touch tests (_SHIPPED_DATA). | Y (data and tests) |
| L15 | I | LOW | `schema.md:123-125` "binary floating point is never used for a reported figure" | Judge R6 passed; not discriminating. | None needed. | Low risk. | N |
| L16 | D | LOW | Mixed UTC offsets in `events.json` (+01:00 443, +00:00 57) while text order equals instant order | Step 11 printed `distinct instants 500`; no use of the offset otherwise. | None. | n/a | N |

## What is clean

- Build context is `environment/` only (`COPY data /app/data`); `tests/`, `solution/` and `_work/` are not reachable. `HARDEN_PROMPT.md` and other `_work` files cannot be reached by the agent.
- No oracle outputs, TRUTH, reference code, or expected-output digests are shipped (the manifest is the sole partial exception, for `data_quality.rows`).
- No `.git`, `__pycache__`, `.DS_Store`, backups, TODO/FIXME, or words such as harbor, QC, lever, rubric, trap, hidden, grader or oracle in visible files.
- No emphatic wording (CAPS, bold, "be careful", "note that") in `instruction.md`, `schema.md` or any data comment.
- Record ids and column names do not encode the traps (except the weak orphan suffix tell, L14).
- Shipped data does not separate the wrong readings for REENTRY, CHAIN1, RELIEF or the equal-instant tie. The one thing it does show is that every cold counter is 0 (L10).
- The judge criteria R1-R4 are not echoed in any visible file, and that is where the agent lost points.
- The three negatives did not fire. The instruction's closing sentence matches the 7200 s agent timeout.

TOP_LEAK: L01 schema.md states every hidden rule (re-share, draws_from chain, credited ticks, carry, rate recipe, [export] decoy) as a complete literal recipe; Opus's first write at step 15 already implemented all of them and tests came out 100
COUNTS: C=0 H=7 M=6 L=3
