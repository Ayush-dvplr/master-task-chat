# DESIGN harden r4 (ea94780): flood-repair-portfolio off route 1

BUNDLE tree at start 931f8f817d76 (= attempt-3 bytes). No BUNDLE edits in Phase 0/1. Kit HEAD 5574d77e.
Why off route 1: r3 fuzz (1,500 books + 141 cases) found no WRONG fact for the a3 program; the time lever cannot
separate a3 (5-8 s) from the reference (1-3 s). Open move: one new documented rule (TRIP.md).

## Candidates
| id | doc sentence (contract.md) | interacts with | natural wrong program | hidden shape | verdict |
|---|---|---|---|---|---|
| A | L62, after sentence 1: "A crew whose mode is `shared` can work on at most four of the proposals in a portfolio." | portfolio definition + max-total + tie order (L62); crew source only for `exclusive` (L54-56); per-component optimisation | post-step (drop least-valuable pick of an over-full shared crew, re-plan), local filter (keep top-4 benefit members before planning), per-component cap | a shared crew with 6-8 members on two or more alternating paths m-x-m-x-m (x conflicts m via exclusions); capped optimum drops a middle pair and takes the x between them | CHOSEN |
| B | L62: "A portfolio holds at most two proposals that carry a risk override." | selection, override valuation | post-step trim | rounds with 3+ override picks | rejected: 31% of shipped rows carry an override, binds in nearly every shipped round (broad shipped change, W5) |
| C | L62: "The households of a portfolio's proposals add up to at most 400." | selection (knapsack) | greedy trim | large rounds | rejected: reference cost explodes on 160-row rounds; binds in shipped |
| D | L62 tie: "prefer the portfolio with fewer proposals before comparing ids" | tie order | none: a3's weight encoding change is natural and correct | tie paths | rejected: weak lever |

Cap value: with cap 3 the shipped round R62233 (the only shipped round where one shared crew has 4 members) changed
answer under the prototype reference; with cap 4 `SHIPPED_DIFF_ROUNDS []` (logs/shape300_cap4.log). Shipped answers,
shipped expected documents and TRUTH.md answers are unchanged; the rule never binds on shipped data.

Why A is determinate (IN-15/16, DS-21): a portfolio becomes "conflict-free AND every shared crew <= 4"; the existing
max-total and sorted-id-list tie order then fix one answer. No worked example needed (one reading); none planted on
the hidden shape (IN-17). Why it threads through the core: `shared` crews never form a conflict edge, so the cap couples
proposals that sit in different conflict components and changes which neighbours are worth taking; any trim before or
after the optimiser keeps the wrong neighbours. Correct = count state inside the optimiser or enumerate keep-sets.

## Prototype (WORK/h4_rule/proto/)
- solve.py: CAP=4 (L212); best_set frontier DP carries per-over-full-crew counts (state (mask, counts)); choose()
  solves the pieces touching an over-full shared crew in one call (L261-295). build() passes book (L305).
- Embedded reference (crosscheck.py, exact planned edit): `chosen = _portfolio(info, joined)` (test_output.py:923) ->
  `chosen = _capped(info, joined, self.mode)`; `_capped` enumerates four-subsets of each over-full shared crew and keeps
  (max total, min sorted ids). Independent of solve.py's DP. logs/crosscheck2.log: `SEEDS_SAME 0 300`, `BOOK_SAME` on
  H1c H2c H3c Mc and shipped data (ledger 7.6/7.5/6.4/0.1/0.4 s).
- capgen.py make_book2 = make_book + `spec["capped"]` rounds from own RNG `_Rng(seed*31+7177)` (old draws untouched).
  Per gadget asserts: uncapped optimum takes >= 6 members; capped optimum unique; every dropped member conflicts with a
  selected proposal or its crew is full; capped optimum differs from 7 shortcuts (filter top-benefit, filter first ids,
  post drop-lowest, post re-solve-lowest, post keep-top-4, post greedy-gain, per-component cap); diff touches a
  commercial or public proposal (rollups move). shape300.py: `SEEDS_OK 0 300 {k6 252, k7 106, k8 242, attempts_max 75}`.
- Planned hidden books: H1/H2/H3 gain `"capped": 3`, M gains `"capped": 2` (same seeds, new sha256; MS/MR/relocated
  follow M). Gadget rounds are small (<= 23 rows, < 40 records), inside every stated limit.

## Check changes (Phase 2)
- `_feasible` (test_output.py:1259-1281): add "no shared crew has more than four picks" and exempt from the "could still
  add" test a proposal whose shared crew already has four picks (the old maximality is false under the rule).
- `_BOOKS` H1/H2/H3/M entries: `capped` key + sha256. Embedded generator: capped branch (own RNG). `_Ledger._settle`
  one line + `_capped`. solve.py: count state. Weights, registrations, `_launch`/`_stop_untrusted` unchanged.
- Docs: contract.md:62 one sentence (above). instruction.md:15 one sentence (below). Shipped data files unchanged.

## Kill table (Docker, cap-aware feasible; logs/kill3_capfeas.log, kill2.log; timer cap 60 s, 20 s applied below)
| program | H1c s | H2c s | H3c s | Mc s | per-H checks | Mc | lever kept /89 |
|---|---|---|---|---|---|---|---|
| reference (proto solve.py) busy | 1.90 (2.52 max) | 1.19 | 0.96 | 0.05 | EXACT | EXACT | 89 |
| a3 natural (post-step, a3_natural.diff 21 lines) | 6.18 WRONG | 4.82 WRONG | 3.04 WRONG | 0.10 WRONG | 3/25 (data_quality) | WRONG | 12 |
| a3 prefilter (top-4 benefit, a3_prefilter.diff) | 7.11 WRONG | 4.80 WRONG | 3.02 WRONG | 0.10 WRONG | 3/25 | WRONG | 12 |
| a3 correct (enumerate keep-sets, a3_correct.diff) | 7.88 EXACT | 4.84 EXACT | 3.08 EXACT | 0.10 EXACT | 25/25 | EXACT | 89 |
| a3 unchanged | 6.81 WRONG | 4.78 WRONG | 3.05 WRONG | 0.09 WRONG | 3/25 | WRONG | 12 |
| a1 program | 60.07 TIMEOUT | 60.06 TIMEOUT | 59.27 (TIMEOUT@20) | 1.42 WRONG | 0 | WRONG | 0 |
| first-write | 60.10 TIMEOUT | 60.09 TIMEOUT | 60.11 TIMEOUT | 60.09 TIMEOUT | 0 | TIMEOUT | 0 |
| all-but-one | 60.07 TIMEOUT | 55.45 (TIMEOUT@20) | 33.90 (TIMEOUT@20) | 0.04 WRONG | 0 | WRONG | 0 |
Lever kept counts the 89 lever points (H1-H3 75 + reruns 3 + MS 5 + MR 3 + relocated 3); a3 rows keep data_quality 3x3
and reruns 3. Natural a3 loses 77/89 = 86.5% of lever points by WRONG (Law-1). a1 loses 11 by WRONG (M family) and 78
by TIMEOUT (v3.5 timeout lever, unchanged). Reference unbusy max 3.42 s (one noisy run), busy max 2.52 s <= 5 s (1/4).
Peak memory <= 73 MB programs, 52 MB reference (abo 606 MB), inside 4 GiB.

## Arithmetic (positive test weight 108, unchanged)
- Natural a3: artifacts 1 + shipped 15 + data_quality 3x3 + missing 3 + reruns 3 = 31/108 = 28.7%.
- a1: artifacts 1 + shipped 15 + missing 3 = 19/108 = 17.6% (H1-H3 TIMEOUT, M family WRONG, reruns TIMEOUT).
- Careful correct adaptation (a3_correct): 108/108 (recorded, not a blocker; note 6).
- Lever share: new rule lever (H1-H3 66 + M family 11 = 77) union timeout lever (H1-H3 75 + reruns 3) = 89/108 = 82.4% >= 40%.

## Judge rebuild (tests/judge.toml)
Kept probes (a3 skipped them; type process, w3, trajectory): R1 recompute VALUE rows by hand, R2 PAIR sources, R4 region
rollups, R5 segment rollups, R6 small rounds by enumeration without importing the program, R7 rerun on an altered copy.
New probes: R12 "The agent runs its program on a book it built in which one shared crew has more than four proposals in
a round, and shows the portfolio the program chose for that round." (serves the new rule); R13 "The agent shows one round
of the shipped book in which more than one portfolio reaches the greatest total benefit, with the id list its program
chose for it." (serves the tie order). Dropped: R3 rejection codes (a3 borderline), R8 timing on the shipped book
(restates the time limit; a3 did it). Kept non-probe: R9 maintainable program (the one J4 code-quality criterion) w6,
R10 final reply lists rejected rounds w5 (completion, not graded by tests). Negatives: R11 J3a -5 kept unchanged;
new R14 J3b -5 "the final reply names a rejected round id that /app/out/data_quality.json does not list".
Positive 24 probes + 11 = 35; probe share 24/35 = 68.6% (band 55-70%); 8 probes (band 8-16). solve.sh self-check adds
`check R12 ok` (copies the shipped book, adds five proposals of one shared crew to a round, prints the chosen ids) and
`check R13 ok` (prints a shipped tie round and its ids); R3/R8 stages stay as plain self-checks. JUDGE_MAP rows for all.
| program | low | mid | high |
|---|---|---|---|
| natural a3 (finishes) | R9, R11 fires: 1/35 = 2.9 | R9+R10 11/35 = 31.4 | +R12 14/35 = 40.0 |
| a1 | R9, R11 fires: 2.9 | R9+R10 31.4 | +R6 14/35 = 40.0 |
Probe mid = 0 for both (<= 20). a3 at attempt 3 never finished (no trajectory.json); mid assumes it finishes.

## Instruction sentence
instruction.md:15 becomes "You have 7200 seconds to complete this task. Leave enough of that time to finish and write
your final reply. Do not cheat by using online solutions or hints specific to this task." C1 regex
`[Yy]ou have ([\d,]+) seconds` still matches; no speed/size/performance/20 s words.

## Predicted scores
| program | tests | judge mid | final |
|---|---|---|---|
| natural a3 | 28.7 | 31.4 | 30.1 |
| a1 | 17.6 | 31.4 | 24.5 |
| careful correct a3 | 100 | 40.0 (high) | 70.0 (recorded) |
Gate for natural a3 and a1: tests < 85, rubric < 85, final <= 35 met.

## Verifier worst case
13 program launches (shipped, H1-H3, M, MS, MR, relocated, 3 missing, 2 reruns) x 20 s = 260 s + embedded reference
(7.6+7.5+6.4+3x0.1+0.4 s ~ 22 s) + generation ~ 30 s = ~315 s <= 2,430 s (90% of 2,700). Measured in Phase 3.

## Changed in Phase 2 (complete list)
contract.md:62 (one sentence); instruction.md:15 (one sentence); solution/solve.py (count state, CAP); solution/solve.sh
(R12, R13 stages); solution/TRUTH.md (rule row, regenerated by script; shipped answers unchanged); tests/test_output.py
(_feasible cap, capped generator branch, _BOOKS H1/H2/H3/M capped+sha, _Ledger one line + _capped); tests/judge.toml.
Shipped expected answers changed: none. Shipped data files changed: none.

## Risks
A blind that threads the cap correctly (enumerate keep-sets) keeps 100+ tests; the lever then rests on the judge and
on how often a careful agent writes the post-step. The gadget defeats 7 shortcut programs by generator assert.

## Blind brief
- Give each fresh blind: instruction.md, environment/data/ (incl. contract.md with the new L62 sentence), task.toml; no
  tests/, no solution/, no WORK files, no mention of the cap gadget or this design.
- Ask for /app/out/derive_report.py as the task states; take the program file only.
- Score it with WORK/h4_rule/proto/drive4.sh (PROGS=blind, P map entry added; KH=3, KM=2, CAP=20) and docscore.py,
  against proto/solve.py on H1c H2c H3c Mc.
- Expected match: a post-step or filter adaptation -> kill-table row "a3 natural"/"a3 prefilter" (3/25 per book,
  tests ~31/108); a cap-ignoring program -> "a3 unchanged"; an enumeration or count-state program -> "a3 correct".
- Report per blind: seconds, verdict per book, which row it matches, and the lines where it applies the cap.

DESIGN READY: /Users/mac/Desktop/Terminal Bench/master_chat_work/20261101_flood-repair-portfolio/harden_r4/DESIGN.md
